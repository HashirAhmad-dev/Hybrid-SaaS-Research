"""
pii_v2.py
=========
Paper-v2 PII track on the v2 corpus (T3.1 to T3.5). Stages, each cached and
resumable, all outputs under evaluation/data/pii_v2/:

  ocr-easyocr   EasyOCR over every image document -> ocr_easyocr_cpu.json
                (PaddleOCR is produced by evaluation/paddle_ocr_runner.py in .venv-paddle,
                 same record format -> ocr_paddleocr_<device>.json)
  presidio      Presidio on text documents and on every OCR transcript, with the
                original recognisers ("presidio") and with the T3.5 additions
                ("presidio_plus": street addresses, all Mastercard ranges)
  vlm           a LOCAL vision-language model through LM Studio's OpenAI-compatible
                server (http://localhost:1234/v1). Temperature 0, fixed prompt,
                JPEG data URL (LM Studio issue #1752 concerns webp), one image per
                request, timeout, cache keyed by (model id, prompt hash, image hash).
                Records seconds per image, tokens per second and peak GPU memory.
  score         entity-level scoring on a fixed calib / eval document split
                (25 percent calib, stratified by subset x modality x difficulty,
                seed 2610). Every threshold and the router are chosen on CALIB through
                evaluation/selection.py; every reported number is on EVAL. Writes
                manifest keys pii2.* and results/pii_v2/*.csv.

    python -m evaluation.pii_v2 ocr-easyocr
    python -m evaluation.pii_v2 presidio
    python -m evaluation.pii_v2 vlm --model <lmstudio model id>
    python -m evaluation.pii_v2 score
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import random
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from evaluation import selection
from evaluation.pii_common import ENTITY_TYPES, match_entities, prf
from evaluation.run_pipeline import (PRESIDIO_MAP, PRESIDIO_MIN_SCORE, _clean_vlm_entities,
                                     _dedupe_overlaps, _extract_json_array, build_analyzer)
from tools.manifest import PROJECT_ROOT, provenance, record

ROOT = PROJECT_ROOT
GT = ROOT / "evaluation" / "pii_testset_v2" / "ground_truth.json"
DATA = ROOT / "evaluation" / "data" / "pii_v2"
OUT = ROOT / "results" / "pii_v2"
LMSTUDIO = "http://localhost:1234/v1"
SPLIT_SEED = 2610
CALIB_SHARE = 0.25

VLM_PROMPT_V2 = """You are a PII detection engine. Look at this document image and extract every piece of personally identifiable information about a person that you can read.

Return ONLY a JSON array, no prose, no markdown fences. Each element must be:
  {"type": "<TYPE>", "value": "<exact text as it appears in the image>"}

Allowed TYPE values (use these exactly):
  PERSON        a person's full name (not a company or place)
  NID           a national identity number (CNIC format #####-#######-#)
  CREDIT_CARD   a payment card number
  PHONE         a person's telephone number
  EMAIL         a person's email address
  DOB           a date of birth (not other dates)
  ADDRESS       a street address of a person
  PASSWORD      a password or credential

Invoice numbers, order or tracking references, employee codes, document dates,
company names and extension numbers are NOT PII; do not list them.
Do not include field labels (e.g. "Name:") in the value. Do not invent entities.
If the image contains no PII, return [].
"""
PROMPT_HASH = hashlib.sha256(VLM_PROMPT_V2.encode()).hexdigest()[:12]


def load_docs() -> List[dict]:
    return json.loads(GT.read_text(encoding="utf-8"))["documents"]


def doc_path(d: dict) -> Path:
    return ROOT / "evaluation" / d["root"] / d["path"]


def assign_split(docs: List[dict]) -> Dict[str, str]:
    """Fixed calib/eval split, stratified by subset x category x difficulty."""
    r = random.Random(SPLIT_SEED)
    strata: Dict[tuple, List[str]] = {}
    for d in docs:
        strata.setdefault((d["subset"], d["category"], d.get("difficulty")), []).append(d["doc_id"])
    out = {}
    for key in sorted(strata, key=str):
        ids = sorted(strata[key])
        r.shuffle(ids)
        k = int(round(len(ids) * CALIB_SHARE))
        for i, x in enumerate(ids):
            out[x] = "calib" if i < k else "eval"
    return out


def save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=0, default=float), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# OCR (EasyOCR)
# ---------------------------------------------------------------------------
def stage_ocr_easyocr(limit: int = 0) -> None:
    import easyocr
    import torch
    from PIL import Image
    from evaluation.run_pipeline import ocr_document

    out = DATA / "ocr_easyocr_cpu.json"
    res = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    docs = [d for d in load_docs() if d["category"] != "text_extractable"]
    if limit:
        docs = docs[:limit]
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    ocr_document(reader, doc_path(docs[0]))                 # warm-up
    for i, d in enumerate(docs, 1):
        if d["doc_id"] in res:
            continue
        p = doc_path(d)
        w, h = Image.open(p).size
        t0 = time.perf_counter()
        txt, conf, nbox = ocr_document(reader, p)
        res[d["doc_id"]] = {"transcript": txt, "confidence": conf, "boxes": nbox,
                            "elapsed_ms": (time.perf_counter() - t0) * 1000.0, "width": w, "height": h}
        if i % 20 == 0:
            save(out, res)
            print(f"  easyocr {i}/{len(docs)}", flush=True)
    res["_meta"] = {"engine": "EasyOCR", "device": "cpu", "torch_threads": torch.get_num_threads()}
    save(out, res)


# ---------------------------------------------------------------------------
# Presidio (original and T3.5 additions)
# ---------------------------------------------------------------------------
MASTERCARD_RE = (r"\b(?:5[1-5]\d{2}|222[1-9]|22[3-9]\d|2[3-6]\d{2}|27[01]\d|2720)"
                 r"(?:[ -]?\d{4}){3}\b")
STREET_SUFFIX = (r"(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Court|Ct|Boulevard|Blvd|Way|"
                 r"Walk|Place|Pl|Square|Sq|Terrace|Crescent|Close|Gardens|Grove|Park|Parkway|Hill|"
                 r"Ridge|Trail|Circle|Mews|Row|Green|Plaza|Highway|Hwy|Loop|Path|Pike|Point|Port|"
                 r"Ramp|Run|Shoal|Spring|Station|Summit|Throughway|Turnpike|Union|Valley|View|Villages?|"
                 r"Vista|Well|Wells|Expressway|Extension|Falls|Ferry|Field|Fields|Flat|Ford|Forest|Forge|"
                 r"Fork|Fort|Freeway|Glen|Harbor|Haven|Heights|Hollow|Inlet|Island|Junction|Key|Knoll|"
                 r"Lake|Landing|Light|Lock|Manor|Meadows?|Mill|Mission|Motorway|Mount|Mountain|Neck|"
                 r"Orchard|Oval|Pass|Pine|Plains?|Prairie|Radial|Ranch|Rapids?|Rest|River|Shore|Skyway|"
                 r"Stream|Streets|Track|Trafficway|Tunnel|Underpass|Viaduct|Ville|Brook|Burg|Bypass|"
                 r"Camp|Canyon|Cape|Causeway|Center|Centre|Cliff|Club|Common|Corner|Course|Cove|Creek|"
                 r"Crossing|Crossroad|Curve|Dale|Dam|Divide|Estates?|Bridge|Bluff|Bottom|Branch|Burgs)")
ADDRESS_RE = (r"\b\d{1,6}\s+(?:[A-Z][a-zA-Z'\-]+\s+){1,4}" + STREET_SUFFIX +
              r"\.?(?:\s*,?\s*(?:Apt\.?|Suite|Unit|Flat|Ste\.?)\s*[A-Za-z0-9\-]+)?"
              r"(?:\s*,\s*[A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+){0,2})?")


def build_analyzer_plus():
    """T3.5: the original analyzer plus two recognisers for its measured gaps."""
    from presidio_analyzer import Pattern, PatternRecognizer
    a = build_analyzer()
    a.registry.add_recognizer(PatternRecognizer(
        supported_entity="CREDIT_CARD", name="MastercardAllRanges",
        patterns=[Pattern("mastercard_51_55_2221_2720", MASTERCARD_RE, 0.6)],
        context=["card", "credit", "mastercard", "billed", "charged"]))
    a.registry.add_recognizer(PatternRecognizer(
        supported_entity="STREET_ADDRESS", name="StreetAddress",
        patterns=[Pattern("number_name_suffix", ADDRESS_RE, 0.6)],
        context=["address", "lives", "residence", "courier", "street"]))
    return a


PLUS_MAP = {**PRESIDIO_MAP, "STREET_ADDRESS": "ADDRESS"}


def dedupe_deterministic(results) -> list:
    """Like run_pipeline._dedupe_overlaps, but ties (same score, same start) are broken
    by longer span, then entity-type name. Presidio returns recogniser results in an
    order that varies between processes, so the original tie-break was not repeatable
    (found in T3.2: one document flipped PASSWORD/ADDRESS between two runs)."""
    kept = []
    for r in sorted(results, key=lambda x: (-x.score, x.start, -(x.end - x.start), x.entity_type)):
        if any(r.start < k.end and k.start < r.end for k in kept):
            continue
        kept.append(r)
    return sorted(kept, key=lambda x: x.start)


def analyse(analyzer, text: str, plus: bool, luhn_check: bool = True) -> List[Dict[str, str]]:
    from evaluation.build_pii_corpus_v2 import luhn_ok
    m = PLUS_MAP if plus else PRESIDIO_MAP
    res = analyzer.analyze(text=text, language="en", entities=list(m.keys()),
                           score_threshold=PRESIDIO_MIN_SCORE)
    out = []
    for r in dedupe_deterministic(res):
        t = m.get(r.entity_type)
        v = text[r.start:r.end].strip()
        if not t:
            continue
        if plus and t == "CREDIT_CARD" and luhn_check:
            digits = "".join(c for c in v if c.isdigit())
            if not luhn_ok(digits):
                continue                                   # the custom regex has no checksum
        out.append({"type": t, "value": v})
    return out


def stage_presidio() -> None:
    docs = load_docs()
    out = {}
    engines = {"presidio": (build_analyzer(), False), "presidio_plus": (build_analyzer_plus(), True)}
    ocr_files = sorted(DATA.glob("ocr_*.json"))
    for name, (an, plus) in engines.items():
        res: Dict[str, dict] = {"text": {}}
        for d in docs:
            if d["category"] == "text_extractable":
                t0 = time.perf_counter()
                ents = analyse(an, d["text"], plus)
                res["text"][d["doc_id"]] = {"entities": ents, "elapsed_ms": (time.perf_counter() - t0) * 1000}
        for f in ocr_files:
            ocr = json.loads(f.read_text(encoding="utf-8"))
            eng = f.stem.removeprefix("ocr_")
            res[eng] = {}
            for did, rec in ocr.items():
                if did.startswith("_"):
                    continue
                t0 = time.perf_counter()
                ents = analyse(an, rec["transcript"], plus)
                res[eng][did] = {"entities": ents, "elapsed_ms": (time.perf_counter() - t0) * 1000}
        out[name] = res
        print(f"  {name}: text {len(res['text'])}, ocr engines {[k for k in res if k != 'text']}", flush=True)
    save(DATA / "presidio_predictions.json", out)


# ---------------------------------------------------------------------------
# Local VLM through LM Studio
# ---------------------------------------------------------------------------
class GPUSampler(threading.Thread):
    """Polls nvidia-smi for used GPU memory; keeps the peak."""

    def __init__(self, interval: float = 0.5):
        super().__init__(daemon=True)
        self.interval, self.peak, self.stop_flag, self.ok = interval, 0, False, True

    def run(self):
        while not self.stop_flag:
            try:
                v = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
                self.peak = max(self.peak, int(v[0]))
            except Exception:
                self.ok = False
            time.sleep(self.interval)


def stage_vlm(model: str, limit: int = 0, timeout: float = 300.0) -> None:
    import openai
    from PIL import Image
    client = openai.OpenAI(base_url=LMSTUDIO, api_key="lm-studio", timeout=timeout, max_retries=0)
    ids = [m.id for m in client.models.list().data]
    if model not in ids:
        raise SystemExit(f"model {model!r} not served by LM Studio; available: {ids}")
    slug = "".join(c if c.isalnum() else "-" for c in model)
    cache_dir = DATA / "vlm_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    docs = [d for d in load_docs() if d["category"] != "text_extractable"]
    if limit:
        docs = docs[:limit]
    sampler = GPUSampler()
    sampler.start()
    results = {}
    for i, d in enumerate(docs, 1):
        p = doc_path(d)
        raw = p.read_bytes()
        key = hashlib.sha256(f"{model}|{PROMPT_HASH}|{hashlib.sha256(raw).hexdigest()}".encode()).hexdigest()[:20]
        c = cache_dir / f"{slug}-{key}.json"
        if c.exists():
            results[d["doc_id"]] = json.loads(c.read_text(encoding="utf-8"))
            continue
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            raise SystemExit(f"{p}: only JPEG/PNG are sent (LM Studio #1752)")
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        msg = [{"role": "user", "content": [
            {"type": "text", "text": VLM_PROMPT_V2},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(raw).decode()}"}}]}]
        t0 = time.perf_counter()
        status, ents, usage, text = "error", [], {}, ""
        try:
            r = client.chat.completions.create(model=model, messages=msg, temperature=0.0,
                                               max_tokens=1024, seed=0)
            text = r.choices[0].message.content or ""
            if r.usage:
                usage = {"prompt_tokens": r.usage.prompt_tokens, "completion_tokens": r.usage.completion_tokens}
            parsed = _extract_json_array(text)
            status = "ok" if parsed is not None else "malformed_json"
            ents = _clean_vlm_entities(parsed or [])
        except openai.APITimeoutError:
            status = "timeout"
        except openai.APIError as e:
            status = f"error:{type(e).__name__}"
        el = time.perf_counter() - t0
        rec = {"doc_id": d["doc_id"], "model": model, "prompt_hash": PROMPT_HASH, "status": status,
               "entities": ents, "seconds": el, "usage": usage,
               "tokens_per_second": (usage.get("completion_tokens", 0) / el) if el > 0 else None,
               "raw": text[:3000]}
        c.write_text(json.dumps(rec, indent=0), encoding="utf-8")
        results[d["doc_id"]] = rec
        if i % 10 == 0:
            print(f"  {model}: {i}/{len(docs)}  last {el:.1f}s  gpu peak {sampler.peak} MiB", flush=True)
    sampler.stop_flag = True
    meta = {"model": model, "prompt_hash": PROMPT_HASH, "endpoint": LMSTUDIO,
            "gpu_peak_mib_during_run": sampler.peak if sampler.ok else None,
            "n": len(results)}
    save(DATA / f"vlm_{slug}.json", {"_meta": meta, **results})
    print(json.dumps(meta))


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def counts(gold, pred):
    tp, fp, fn, _ = match_entities(gold, pred)
    return np.array([tp, fp, fn])


def f1_of(c) -> float:
    tp, fp, fn = c
    return 2 * tp / (2 * tp + fp + fn) if tp else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("ocr-easyocr", "presidio", "vlm", "score"))
    ap.add_argument("--model", default=None)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if args.stage == "ocr-easyocr":
        stage_ocr_easyocr(args.limit)
    elif args.stage == "presidio":
        stage_presidio()
    elif args.stage == "vlm":
        if not args.model:
            raise SystemExit("--model required")
        stage_vlm(args.model, args.limit)
    else:
        from evaluation.pii_v2_score import score_all
        score_all()


if __name__ == "__main__":
    main()
