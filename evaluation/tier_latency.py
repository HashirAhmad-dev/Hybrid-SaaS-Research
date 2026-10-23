"""
tier_latency.py
===============
Paper-v2 task T3.6: measure the two-tier design INSIDE the running proxy.

Tier 1: start `uvicorn backend.main:app` as a separate process, send real
payloads to POST /tier1/score over HTTP, and time each request on the client
(wall clock, includes HTTP on localhost) and on the server (per-stage timings
returned by backend/tier1.py).
  * cold: the first request after a fresh server start (loads Presidio/spaCy,
    the LSTM and the forest), repeated over COLD_RESTARTS fresh processes
  * warm: WARM_N requests after WARMUP requests, sequential, one client
Payloads: text = the text documents of the PII corpus (v2 and v1), behaviour =
TEST-split sessions of dataset 42 with their previous 23 hours of history.

Tier 2: POST /tier2/submit for TIER2_N images (scanned and handwritten, v2),
one at a time, polling /tier2/<job> until done; reports the hold time (upload
held until release or escalation) and processing time.

No GPU work runs during this measurement. The machine is described in
docs/ENVIRONMENT.md.

    python -m evaluation.tier_latency
Outputs: results/latency/tier_latency.json, manifest keys latency.tier1.*, latency.tier2.*
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from evaluation.common import FEATURES, SEQ_LEN
from tools.manifest import PROJECT_ROOT, provenance, record

PORT = 8765
URL = f"http://127.0.0.1:{PORT}"
COLD_RESTARTS = 5
WARMUP = 20
WARM_N = 1000
TIER2_N = 20
OUT = PROJECT_ROOT / "results" / "latency"


def start_server() -> subprocess.Popen:
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(PORT),
                          "--log-level", "warning"], cwd=PROJECT_ROOT,
                         env={**os.environ, "PYTHONUTF8": "1"},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(600):
        try:
            if httpx.get(f"{URL}/docs", timeout=1.0).status_code == 200:
                return p
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    p.kill()
    raise RuntimeError("server did not start")


def payloads(n: int):
    sess = pd.read_csv(PROJECT_ROOT / "evaluation" / "data" / "sessions_raw.csv")
    sess = sess.sort_values(["user_id", "hour_index"])
    gt = json.loads((PROJECT_ROOT / "evaluation" / "pii_testset_v2" / "ground_truth.json").read_text(encoding="utf-8"))
    texts = [d["text"] for d in gt["documents"] if d["category"] == "text_extractable"]
    test = sess[(sess.split == "test") & sess.active]
    rng = np.random.default_rng(7)
    rows = test.iloc[rng.choice(len(test), size=n, replace=len(test) < n)]
    by_user = {u: g.set_index("hour_index") for u, g in sess.groupby("user_id")}
    out = []
    for i, (_, r) in enumerate(rows.iterrows()):
        g = by_user[r.user_id]
        hist = g.loc[max(0, r.hour_index - (SEQ_LEN - 1)):r.hour_index - 1, list(FEATURES)].to_numpy().tolist()
        out.append({"user_id": r.user_id, "text": texts[i % len(texts)],
                    "features": [float(r[f]) for f in FEATURES], "history": hist})
    return out


def pct(v):
    v = np.asarray(v, float)
    return {"n": int(len(v)), "mean": float(v.mean()), "p50": float(np.percentile(v, 50)),
            "p95": float(np.percentile(v, 95)), "p99": float(np.percentile(v, 99)), "max": float(v.max())}


def main() -> None:
    P = payloads(WARMUP + WARM_N + COLD_RESTARTS)
    res = {"tier1": {}, "tier2": {}}
    cold_client, cold_server = [], []
    for k in range(COLD_RESTARTS):
        srv = start_server()
        try:
            t0 = time.perf_counter()
            r = httpx.post(f"{URL}/tier1/score", json=P[k], timeout=300).json()
            cold_client.append((time.perf_counter() - t0) * 1e3)
            cold_server.append(r["timing_ms"]["total"])
        finally:
            srv.kill(); srv.wait()
        print(f"  cold {k + 1}/{COLD_RESTARTS}: {cold_client[-1]:.0f} ms", flush=True)
    res["tier1"]["cold_client_ms"] = pct(cold_client)
    res["tier1"]["cold_server_ms"] = pct(cold_server)

    srv = start_server()
    try:
        with httpx.Client(timeout=60) as c:
            for p in P[COLD_RESTARTS:COLD_RESTARTS + WARMUP]:
                c.post(f"{URL}/tier1/score", json=p)
            cl, st = [], {"pii_text": [], "anomaly": [], "sbrs": [], "total": []}
            actions = {}
            for p in P[COLD_RESTARTS + WARMUP:]:
                t0 = time.perf_counter()
                r = c.post(f"{URL}/tier1/score", json=p).json()
                cl.append((time.perf_counter() - t0) * 1e3)
                for kk in st:
                    st[kk].append(r["timing_ms"][kk])
                actions[r["action"]] = actions.get(r["action"], 0) + 1
            res["tier1"]["warm_client_ms"] = pct(cl)
            res["tier1"]["warm_server_ms"] = {k: pct(v) for k, v in st.items()}
            res["tier1"]["warm_actions"] = actions
            print(f"  warm: p50 {res['tier1']['warm_client_ms']['p50']:.1f} ms  "
                  f"p95 {res['tier1']['warm_client_ms']['p95']:.1f}  p99 {res['tier1']['warm_client_ms']['p99']:.1f}",
                  flush=True)

            gt = json.loads((PROJECT_ROOT / "evaluation" / "pii_testset_v2" / "ground_truth.json").read_text(encoding="utf-8"))
            imgs = [d for d in gt["documents"] if d["subset"] == "v2" and d["category"] != "text_extractable"]
            rng = np.random.default_rng(11)
            pick = [imgs[i] for i in rng.choice(len(imgs), TIER2_N, replace=False)]
            hold, proc, rel = [], [], {}
            for d in pick:
                path = str(PROJECT_ROOT / "evaluation" / d["root"] / d["path"])
                j = c.post(f"{URL}/tier2/submit", json={"image_path": path, "a_hybrid": 0.1}).json()
                assert j["inline_action"] == "HOLD"
                while True:
                    s = c.get(f"{URL}/tier2/{j['job_id']}").json()
                    if s["state"] == "DONE":
                        break
                    time.sleep(0.05)
                hold.append(s["hold_ms"]); proc.append(s["processing_ms"])
                rel[s["release"]] = rel.get(s["release"], 0) + 1
            res["tier2"] = {"engine": "EasyOCR (CPU) + Presidio+", "hold_ms": pct(hold),
                            "processing_ms": pct(proc), "outcomes": rel,
                            "note": "first job includes EasyOCR model load"}
            print(f"  tier2 hold p50 {res['tier2']['hold_ms']['p50']:.0f} ms", flush=True)
    finally:
        srv.kill(); srv.wait()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tier_latency.json").write_text(json.dumps(
        {"provenance": provenance("evaluation/tier_latency.py", {"payloads": 7, "tier2_pick": 11}, "cpu"),
         **res}, indent=1), encoding="utf-8")
    record("latency", res, script="evaluation/tier_latency.py", seeds={"payloads": 7, "tier2_pick": 11},
           device="cpu")
    print(f"  -> {OUT / 'tier_latency.json'}")


if __name__ == "__main__":
    main()
