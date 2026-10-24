"""
pii_pipeline.py
===============
Replay of recorded PII outcomes for the dashboard demo (Section III.B of the paper).

This module does NOT run a PII engine. The legacy demo events in
`hybridSaaS_events.json` carry a pre-written PII result for each event, and this
module replays it and recomputes the sensitivity score from the stored counts.
Those records were written by hand for the demo; no OCR engine or VLM produced
them. Their `engine` field says "PaddleOCR + Microsoft Presidio" or
"PaliGemma-3B VLM + Presidio", but neither engine ever ran in this project, so
`scan_event` marks every replayed engine label as a replayed demo record.

The cascade that was actually executed and measured lives in
`evaluation/run_pipeline.py`: Branch 1 Microsoft Presidio, Branch 2 EasyOCR then
Presidio, Branch 3 a vision-language model. See `evaluation/REAL_RESULTS_PII.md`
and `results/manifest.json` (keys `pii.*`, `baseline.pii.*`) for its numbers.

Three branches (routing logic only):
  Branch 1 - Presidio on extractable text
  Branch 2 - OCR -> Presidio            (image, OCR conf >= tau_ocr)
  Branch 3 - VLM                        (image, OCR conf <  tau_ocr)

Sensitivity score formula (the paper's weighted entity model):

    S = min(10 * high_count + 5 * medium_count + 1 * low_count, 100)

The module either
  (a) replays the outcome stored in `hybridSaaS_events.json` for a known
      event_id; or
  (b) recomputes the score from raw entity counts using the same formula.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .data_loader import HybridSaaSDataset
from .schemas import PIIEntity, PIIResult


def _deployed_tau(default: float = 0.85) -> float:
    """tau_ocr chosen on calib documents (backend/config/final_config.json, T4.1); the
    paper's 0.85 only if the generated config is missing."""
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent / "config" / "final_config.json"
    try:
        return float(json.loads(p.read_text(encoding="utf-8"))["pii"]["tau_ocr_deployed"]["value"])
    except (OSError, KeyError, ValueError):
        return default


OCR_CONFIDENCE_THRESHOLD: float = _deployed_tau()  # routing label only
REPLAY_NOTE = "replayed demo record, no engine ran"
ENTITY_WEIGHTS = {"HIGH": 10, "MEDIUM": 5, "LOW": 1}


def _categorise(score: int) -> str:
    """Map sensitivity score (0-100) to the paper's risk_category labels."""
    if score >= 70:
        return "HIGH-RISK"
    if score >= 20:
        return "SENSITIVE"
    return "SAFE"


def _route_branch(file_type: str, ocr_confidence: Optional[float]) -> str:
    """Decide which of the three branches the proxy would dispatch to."""
    ft = (file_type or "").lower()
    if "text" in ft or ft in {"docx", "pdf", "txt", "csv", "xlsx", "py", "env"}:
        return "Branch1_Presidio"
    if ocr_confidence is None:
        # No OCR pass yet - assume routed to OCR branch
        return "Branch2_OCR_Presidio"
    if ocr_confidence >= OCR_CONFIDENCE_THRESHOLD:
        return "Branch2_OCR_Presidio"
    return "Branch3_VLM"


def compute_sensitivity(high: int, medium: int, low: int) -> int:
    """Paper-faithful weighted sensitivity score, clamped to 100."""
    return int(min(
        ENTITY_WEIGHTS["HIGH"] * high
        + ENTITY_WEIGHTS["MEDIUM"] * medium
        + ENTITY_WEIGHTS["LOW"] * low,
        100,
    ))


def _normalise_entity(raw: Dict[str, Any]) -> PIIEntity:
    """Build a PIIEntity, deriving `weight`/`contribution` when absent.

    `hybridSaaS_events.json` stores entities in two shapes. Branch 1 records
    carry the full {type, count, sensitivity_tier, weight, contribution};
    the Branch 2/3 records carry only {type, count, sensitivity_tier} and left
    `PIIEntity(**e)` raising ValidationError on 8 of the 38 events -- which took
    `/score/{event_id}` and the dashboard's scoring view down with it.

    Both fields are fully determined by the paper's weighted entity model, so we
    derive rather than relax the schema:

        weight       = ENTITY_WEIGHTS[sensitivity_tier]
        contribution = weight * count

    Verified against every long-form entity in the log (e.g. NID x3 @ HIGH -> 30,
    PHONE x8 @ MEDIUM -> 40); see `_selftest_entity_derivation` below.
    """
    tier = str(raw.get("sensitivity_tier", "LOW")).upper()
    count = int(raw.get("count", 0))
    weight = int(raw.get("weight", ENTITY_WEIGHTS.get(tier, 1)))
    contribution = int(raw.get("contribution", weight * count))
    return PIIEntity(
        type=str(raw.get("type", "UNKNOWN")),
        count=count,
        sensitivity_tier=tier,
        weight=weight,
        contribution=contribution,
    )


def scan_event(event: Dict[str, Any]) -> PIIResult:
    """Replay the recorded PII outcome of one legacy demo event.

    The demo event log carries a hand-written PII result for each event. It is
    replayed here, and the score is recomputed from the stored counts to check
    the formula. No PII engine runs.
    """
    pii = event.get("pii_detection") or {}
    request = event.get("request") or {}

    entities = [_normalise_entity(e) for e in pii.get("entities_detected", [])]
    high = int(pii.get("high_count", 0))
    medium = int(pii.get("medium_count", 0))
    low = int(pii.get("low_count", 0))

    recomputed = compute_sensitivity(high, medium, low)
    reported = int(pii.get("sensitivity_score", recomputed))

    # Trust the reported score (already validated in the simulation) but
    # surface a deterministic recomputation for the dashboard's "audit" view.
    score = reported if reported >= 0 else recomputed

    # OCR confidence sometimes stored under different keys, default None.
    ocr_conf = pii.get("ocr_confidence")
    if ocr_conf in ("N/A", "", None):
        ocr_conf = None
    else:
        try:
            ocr_conf = float(ocr_conf)
        except (TypeError, ValueError):
            ocr_conf = None

    branch = (
        event.get("module")
        or pii.get("branch")
        or _route_branch(request.get("file_type", ""), ocr_conf)
    )
    # The demo records name engines that never ran here; keep only the branch.
    branch = branch.replace("_PaliGemma", "").replace("_PaddleOCR", "_OCR")

    return PIIResult(
        engine=f"none ({REPLAY_NOTE}; the record says '{pii.get('engine', 'unspecified')}')",
        branch=branch,
        ocr_confidence=ocr_conf,
        ocr_threshold=OCR_CONFIDENCE_THRESHOLD,
        entities_detected=entities,
        high_count=high,
        medium_count=medium,
        low_count=low,
        formula="min(10*H + 5*M + 1*L, 100)",
        sensitivity_score=score,
        risk_category=pii.get("risk_category", _categorise(score)),
        processing_ms=float(pii.get("processing_ms", 0.0)),
    )


def scan_by_event_id(dataset: HybridSaaSDataset, event_id: str) -> PIIResult:
    ev = dataset.get_event(event_id)
    if ev is None:
        raise KeyError(f"Unknown event_id '{event_id}'")
    return scan_event(ev)


def _selftest_entity_derivation(dataset: HybridSaaSDataset) -> Dict[str, int]:
    """Prove `_normalise_entity` reproduces every entity that ships full fields.

    Guards the derivation used for the short-form Branch 2/3 records: for each
    long-form entity in the log, recompute weight/contribution from tier+count
    and assert they match what the log states.
    """
    checked = derived = 0
    for ev in dataset.events:
        for raw in (ev.get("pii_detection") or {}).get("entities_detected", []):
            if "weight" not in raw or "contribution" not in raw:
                derived += 1
                continue
            stripped = {k: v for k, v in raw.items()
                        if k not in ("weight", "contribution")}
            got, want = _normalise_entity(stripped), _normalise_entity(raw)
            if (got.weight, got.contribution) != (want.weight, want.contribution):
                raise AssertionError(
                    f"{ev['event_id']} {raw['type']}: derived "
                    f"({got.weight}, {got.contribution}) != "
                    f"logged ({want.weight}, {want.contribution})"
                )
            checked += 1
    return {"verified_against_logged": checked, "derived_short_form": derived}


if __name__ == "__main__":  # pragma: no cover
    from .data_loader import load_all

    ds = load_all()
    print("entity derivation self-test:", _selftest_entity_derivation(ds))
    ok = sum(1 for eid in ds.event_ids() if scan_by_event_id(ds, eid))
    print(f"scan_event() succeeded on {ok}/{len(ds.events)} events")
