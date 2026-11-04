"""
tier1.py
========
Two-tier enforcement (paper-v2 task T3.6). The single "300 ms end to end" goal
of the original design is replaced by two tiers with separate budgets:

Tier 1, inline (the proxy waits for it):
    text payload -> Presidio (+ the T3.5 recognisers) -> sensitivity S
    6-d behaviour vector (+ up to 23 h of history) -> trained LSTM + Isolation
    Forest -> A_hybrid
    SBRS(S, A) -> PERMIT / ALERT / BLOCK
    Every stage is timed and returned, so latency is measured inside the proxy.

Tier 2, asynchronous (the proxy does not wait):
    image payload -> OCR (EasyOCR) -> Presidio, or the local VLM -> S_image.
    While Tier 2 runs the upload is HELD (quarantined). When Tier 2 finishes the
    hold is released (PERMIT) or converted to ALERT/BLOCK by re-banding SBRS with
    the image's S. Implemented with an in-process thread pool and a job table;
    `tier2_status(job_id)` reports state and timings.

This module is used by the /tier1/score and /tier2/* endpoints in backend/main.py
and by evaluation/tier_latency.py. It needs the evaluation extras (presidio,
easyocr); the dashboard deployment does not import it.
"""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any, Dict, List, Optional

import numpy as np

from . import anomaly_engine
from .risk_orchestrator import DEFAULT_BETA, compute_sbrs

ENTITY_TIER = {"NID": "HIGH", "CREDIT_CARD": "HIGH", "PASSWORD": "HIGH",
               "PHONE": "MEDIUM", "EMAIL": "MEDIUM", "DOB": "MEDIUM", "ADDRESS": "MEDIUM",
               "PERSON": "LOW"}


@lru_cache(maxsize=1)
def analyzer():
    from evaluation.pii_v2 import build_analyzer_plus
    return build_analyzer_plus()


def sensitivity(entities: List[Dict[str, str]]) -> int:
    h = sum(ENTITY_TIER.get(e["type"]) == "HIGH" for e in entities)
    m = sum(ENTITY_TIER.get(e["type"]) == "MEDIUM" for e in entities)
    l = sum(ENTITY_TIER.get(e["type"]) == "LOW" for e in entities)
    return int(min(10 * h + 5 * m + l, 100))


def text_cutoff_bytes() -> Optional[int]:
    """F12 (D-035): text above this size skips inline PII and goes to the Tier 2 queue.
    HYBRIDSAAS_TIER1_MAX_TEXT_BYTES overrides the configured value (0 = no cutoff);
    without either, there is no cutoff (the T3.6 behaviour)."""
    import os
    env = os.getenv("HYBRIDSAAS_TIER1_MAX_TEXT_BYTES")
    if env is not None:
        return int(env) or None
    from .final_config import config
    c = config().get("tier1", {}).get("max_text_bytes")
    return int(c["value"]) if c else None


def tier1_score(text: str, user_id: Optional[str], features: List[float],
                history: Optional[List[List[float]]] = None,
                beta: float = DEFAULT_BETA) -> Dict[str, Any]:
    from evaluation.pii_v2 import analyse
    t0 = time.perf_counter()
    cut = text_cutoff_bytes()
    if cut and len((text or "").encode("utf-8")) > cut:
        return _tier1_large_text(text, user_id, features, history, t0)
    ents = analyse(analyzer(), text or "", plus=True)
    S = sensitivity(ents)
    t1 = time.perf_counter()
    art = anomaly_engine.load_engine()
    sc = anomaly_engine.score_features(np.asarray(features, dtype=float), user_id,
                                       float(art["alpha"]),
                                       history=np.asarray(history, dtype=float) if history else None)
    t2 = time.perf_counter()
    sb = compute_sbrs(S, sc["a_hybrid"], beta=beta)
    # T4.1: configured decision (gated fusion + per-user CUSUM drift), with sources
    from .final_config import DRIFT, decide
    mu, sd = art["user_stats"].get(user_id, art["global_stats"])
    z = np.clip((np.asarray(features, dtype=float) - mu) / sd, -art["z_clip"], art["z_clip"])
    drift = DRIFT.update(user_id or "_unknown", z)
    final = decide(S, sc["a_hybrid"], drift_alarm=drift)
    t3 = time.perf_counter()
    return {"tier": 1, "entities": ents, "sensitivity": S, "a_lstm": sc["a_lstm"], "a_if": sc["a_if"],
            "a_hybrid": sc["a_hybrid"], "sbrs": sb.sbrs_value, "sbrs_action": sb.enforcement_action,
            "drift_alarm": drift, "action": final["action"], "decision": final,
            "timing_ms": {"pii_text": (t1 - t0) * 1e3, "anomaly": (t2 - t1) * 1e3,
                          "sbrs": (t3 - t2) * 1e3, "total": (t3 - t0) * 1e3}}


def _tier1_large_text(text, user_id, features, history, t0) -> Dict[str, Any]:
    """Behaviour now, content later: score A inline, BLOCK if A >= tau_A, otherwise HOLD
    and scan the text in Tier 2 (F12, D-035)."""
    art = anomaly_engine.load_engine()
    sc = anomaly_engine.score_features(np.asarray(features, dtype=float), user_id, float(art["alpha"]),
                                       history=np.asarray(history, dtype=float) if history else None)
    t1 = time.perf_counter()
    from .final_config import DRIFT, val
    mu, sd = art["user_stats"].get(user_id, art["global_stats"])
    z = np.clip((np.asarray(features, dtype=float) - mu) / sd, -art["z_clip"], art["z_clip"])
    drift = DRIFT.update(user_id or "_unknown", z)
    blocked = sc["a_hybrid"] >= val("enforcement", "tau_A")
    job = None if blocked else tier2_submit_text(text, sc["a_hybrid"], drift)
    t2 = time.perf_counter()
    return {"tier": 1, "routed_to_tier2": not blocked, "job_id": job, "sensitivity": None,
            "a_lstm": sc["a_lstm"], "a_if": sc["a_if"], "a_hybrid": sc["a_hybrid"], "drift_alarm": drift,
            "action": "BLOCK" if blocked else "HOLD",
            "reason": "A >= tau_A (behaviour alone)" if blocked else "text above the Tier 1 size cutoff; held for Tier 2",
            "timing_ms": {"pii_text": 0.0, "anomaly": (t1 - t0) * 1e3, "sbrs": (t2 - t1) * 1e3,
                          "total": (t2 - t0) * 1e3}}


def _run_tier2_text(job_id: str, text: str, a_hybrid: float, drift: bool) -> None:
    from evaluation.pii_v2 import analyse
    from .final_config import decide
    j = _JOBS[job_id]
    j["state"], j["started"] = "RUNNING", time.perf_counter()
    ents = analyse(analyzer(), text, plus=True)
    S = sensitivity(ents)
    final = decide(S, a_hybrid, drift_alarm=drift)
    with _LOCK:
        j.update(state="DONE", branch="Tier2_text_Presidio", entities=ents, sensitivity=S, decision=final,
                 final_action=final["action"], release="RELEASE" if final["action"] == "PERMIT" else final["action"],
                 finished=time.perf_counter())
        j["hold_ms"] = (j["finished"] - j["submitted"]) * 1e3
        j["processing_ms"] = (j["finished"] - j["started"]) * 1e3


def tier2_submit_text(text: str, a_hybrid: float, drift: bool = False) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _LOCK:
        _JOBS[job_id] = {"job_id": job_id, "state": "HELD", "submitted": time.perf_counter(), "inline_action": "HOLD"}
    _POOL.submit(_run_tier2_text, job_id, text, a_hybrid, drift)
    return job_id


# ---------------------------------------------------------------------------
# Tier 2: hold, scan asynchronously, then release or escalate
# ---------------------------------------------------------------------------
_POOL = ThreadPoolExecutor(max_workers=1)        # one OCR at a time on a laptop CPU
_JOBS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _ocr_reader():
    import easyocr
    return easyocr.Reader(["en"], gpu=False, verbose=False)


def _vlm_entities(path) -> Optional[list]:
    """Branch 3 through a local LM Studio VLM (model id from HYBRIDSAAS_VLM_MODEL,
    default gemma-3-4b-it, the best local model in T3.3). None if unreachable or unparseable."""
    import base64
    import os
    import httpx
    from evaluation.pii_v2 import LMSTUDIO, VLM_PROMPT_V2, _clean_vlm_entities, _extract_json_array
    model = os.getenv("HYBRIDSAAS_VLM_MODEL", "gemma-3-4b-it")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    msg = [{"role": "user", "content": [
        {"type": "text", "text": VLM_PROMPT_V2},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"}}]}]
    try:
        r = httpx.post(f"{LMSTUDIO}/chat/completions", timeout=300,
                       json={"model": model, "messages": msg, "temperature": 0.0, "max_tokens": 1024, "seed": 0})
        r.raise_for_status()
        parsed = _extract_json_array(r.json()["choices"][0]["message"]["content"] or "")
    except (httpx.HTTPError, KeyError, ValueError):
        return None
    return None if parsed is None else _clean_vlm_entities(parsed)


def _run_tier2(job_id: str, image_path: str, a_hybrid: float, beta: float) -> None:
    from pathlib import Path
    from evaluation.pii_v2 import analyse
    from evaluation.run_pipeline import ocr_document
    j = _JOBS[job_id]
    j["state"], j["started"] = "RUNNING", time.perf_counter()
    from backend.pii_pipeline import OCR_CONFIDENCE_THRESHOLD
    txt, conf, _ = ocr_document(_ocr_reader(), Path(image_path))
    branch = "Branch2_OCR_Presidio"
    ents = analyse(analyzer(), txt, plus=True)
    if conf < OCR_CONFIDENCE_THRESHOLD:
        branch = "Branch3_VLM"
        vlm = _vlm_entities(Path(image_path))
        if vlm is None:
            branch = "Branch3_VLM_unavailable"      # fail closed (D-023): quarantine, never release unscanned
        else:
            ents = vlm
    S = sensitivity(ents)
    sb = compute_sbrs(S, a_hybrid, beta=beta)
    # F7: Tier 2 decides with the same configured gated fusion as Tier 1 (before F7 it used
    # the multiplicative bands of compute_sbrs; that action is kept as `sbrs_action`)
    from .final_config import decide
    final = decide(S, a_hybrid)
    action = "QUARANTINE" if branch == "Branch3_VLM_unavailable" else final["action"]
    with _LOCK:
        j.update(state="DONE", ocr_confidence=conf, tau_ocr=OCR_CONFIDENCE_THRESHOLD, branch=branch,
                 entities=ents, sensitivity=S, sbrs=sb.sbrs_value, sbrs_action=sb.enforcement_action,
                 decision=final, final_action=action,
                 release="RELEASE" if action == "PERMIT" else action,
                 finished=time.perf_counter())
        j["hold_ms"] = (j["finished"] - j["submitted"]) * 1e3
        j["processing_ms"] = (j["finished"] - j["started"]) * 1e3


def tier2_submit(image_path: str, a_hybrid: float, beta: float = DEFAULT_BETA) -> Dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    with _LOCK:
        _JOBS[job_id] = {"job_id": job_id, "state": "HELD", "submitted": time.perf_counter(),
                         "inline_action": "HOLD"}
    _POOL.submit(_run_tier2, job_id, image_path, a_hybrid, beta)
    return {"job_id": job_id, "inline_action": "HOLD"}


def tier2_status(job_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        j = _JOBS.get(job_id)
        return None if j is None else {k: v for k, v in j.items() if k not in ("submitted", "started", "finished")}
