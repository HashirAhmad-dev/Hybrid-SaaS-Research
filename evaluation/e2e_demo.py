"""
e2e_demo.py
===========
Paper-v2 task T4.1: start the real backend (`uvicorn backend.main:app`) with the
generated config (backend/config/final_config.json) and score sample TEST
sessions end to end over HTTP: one session per threat class plus one benign
burst and one ordinary benign session (Tier 1), and one v2 image through
Tier 2 (hold, OCR, release or quarantine). Responses are saved verbatim.

    python -m evaluation.e2e_demo
Output: results/e2e/e2e_demo.json
"""
from __future__ import annotations

import json
import time

import httpx
import numpy as np
import pandas as pd

from evaluation.common import FEATURES, SEQ_LEN
from evaluation.tier_latency import URL, start_server
from tools.manifest import PROJECT_ROOT, provenance, record

OUT = PROJECT_ROOT / "results" / "e2e"
SEED = 11


def pick_sessions() -> list:
    sess = pd.read_csv(PROJECT_ROOT / "evaluation" / "data" / "sessions_raw.csv").sort_values(["user_id", "hour_index"])
    gt = json.loads((PROJECT_ROOT / "evaluation" / "pii_testset_v2" / "ground_truth.json").read_text(encoding="utf-8"))
    text = next(d["text"] for d in gt["documents"] if d["category"] == "text_extractable" and d["entities"])
    test = sess[(sess.split == "test") & sess.active]
    rng = np.random.default_rng(SEED)
    picks = []
    for cls in sorted(test.threat_class.dropna().unique()):
        rows = test[test.threat_class == cls]
        picks.append((f"threat:{cls}", rows.iloc[rng.integers(len(rows))]))
    bb = test[test.is_benign_burst]
    picks.append(("benign_burst", bb.iloc[rng.integers(len(bb))]))
    normal = test[~test.is_true_threat & ~test.is_benign_burst]
    picks.append(("benign", normal.iloc[rng.integers(len(normal))]))
    by_user = {u: g.set_index("hour_index") for u, g in sess.groupby("user_id")}
    out = []
    for label, r in picks:
        g = by_user[r.user_id]
        hist = g.loc[max(0, r.hour_index - (SEQ_LEN - 1)):r.hour_index - 1, list(FEATURES)].to_numpy().tolist()
        out.append((label, r.event_id, {"user_id": r.user_id, "text": text,
                                        "features": [float(r[f]) for f in FEATURES], "history": hist}))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sessions = pick_sessions()
    gt = json.loads((PROJECT_ROOT / "evaluation" / "pii_testset_v2" / "ground_truth.json").read_text(encoding="utf-8"))
    img = next(d for d in gt["documents"] if d["subset"] == "v2" and d["category"] == "scanned" and d["entities"])
    img_path = str(PROJECT_ROOT / "evaluation" / img["root"] / img["path"])
    srv = start_server()
    try:
        cfg = json.loads((PROJECT_ROOT / "backend" / "config" / "final_config.json").read_text(encoding="utf-8"))
        res = {"config_used": {"enforcement_form": cfg["enforcement"]["form"]["value"],
                               "tau_ocr_deployed": cfg["pii"]["tau_ocr_deployed"]["value"]},
               "tier1": [], "tier2": {}}
        with httpx.Client(timeout=300) as c:
            for label, eid, p in sessions:
                r = c.post(f"{URL}/tier1/score", json=p)
                r.raise_for_status()
                res["tier1"].append({"case": label, "event_id": eid, "user_id": p["user_id"], "response": r.json()})
            j = c.post(f"{URL}/tier2/submit", json={"image_path": img_path, "a_hybrid": 0.1}).json()
            for _ in range(600):
                s = c.get(f"{URL}/tier2/{j['job_id']}").json()
                if s.get("state") in ("DONE", "ERROR"):
                    break
                time.sleep(0.5)
            res["tier2"] = {"doc_id": img["doc_id"], "gold_entities": len(img["entities"]), "status": s}
    finally:
        srv.kill()
    res["provenance"] = provenance("evaluation/e2e_demo.py", {"session_pick": SEED}, "cpu")
    (OUT / "e2e_demo.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    summary = {t["case"]: t["response"].get("action") for t in res["tier1"]}
    summary["tier2_state"] = res["tier2"]["status"].get("state")
    record("e2e.demo", summary, script="evaluation/e2e_demo.py", seeds={"session_pick": SEED})
    print(json.dumps(summary, indent=1))
    print(f"  -> {OUT / 'e2e_demo.json'}")


if __name__ == "__main__":
    main()
