"""T4.1: the backend's configured decision equals the evaluated gated form, and every value cites the manifest."""
import csv
import json
from pathlib import Path

import pytest

from backend.final_config import config, decide

ROOT = Path(__file__).resolve().parent.parent


def test_every_value_has_a_manifest_source():
    man = json.loads((ROOT / "results" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    def walk(d):
        for k, v in d.items():
            if isinstance(v, dict) and "value" in v:
                assert "source" in v, k
                if "run_id" in v:                       # copied numbers must equal the manifest
                    assert man[v["source"]]["value"] == v["value"], k
            elif isinstance(v, dict):
                walk(v)
            elif isinstance(v, list):
                for x in v:
                    walk({"x": x})
    walk({k: v for k, v in config().items() if not k.startswith("_")})


def test_decide_matches_evaluated_gated_corners():
    rows = list(csv.DictReader(open(ROOT / "results" / "sbrs_fusion" / "fusion_corners_seed42.csv", encoding="utf-8")))
    assert rows
    for r in rows:
        assert decide(float(r["S"]), float(r["A"]))["action"] == r["gated"], r


def test_drift_alarm_raises_permit_to_alert_only():
    assert decide(10, 0.1, drift_alarm=True)["action"] == "ALERT"
    assert decide(95, 0.9, drift_alarm=True)["action"] == "BLOCK"


def test_vlm_unreachable_returns_none(monkeypatch, tmp_path):
    """Branch 3 must report 'unavailable' (so Tier 2 quarantines) when no VLM server answers."""
    import evaluation.pii_v2 as pv
    from backend.tier1 import _vlm_entities
    monkeypatch.setattr(pv, "LMSTUDIO", "http://127.0.0.1:9/v1")
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert _vlm_entities(img) is None


def test_deployed_tau_comes_from_config():
    import json
    from backend.final_config import CONFIG_PATH
    from backend.pii_pipeline import OCR_CONFIDENCE_THRESHOLD
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert OCR_CONFIDENCE_THRESHOLD == cfg["pii"]["tau_ocr_deployed"]["value"]
