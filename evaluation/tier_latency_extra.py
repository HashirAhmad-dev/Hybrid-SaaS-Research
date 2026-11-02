"""
tier_latency_extra.py
=====================
Task F7: latency beyond the single-client numbers of T3.6, inside the running proxy.

  concurrency  Tier 1 with 1, 2, 4, 8 and 16 concurrent clients (REQS_PER_LEVEL each
               level): client latency percentiles and throughput.
  payload      Tier 1 with text payloads of about 1, 4, 16 and 64 KB (a v2 text
               document repeated), sequential: client latency and server PII time.
  tier2_vlm    Tier 2 with the local VLM branch live (LM Studio serving gemma-3-4b-it):
               hold time per image and which branch handled it. Skipped and recorded as
               such when LM Studio is not reachable.

Run with no other heavy job on the machine. Results vary with load and are not part of
the bit-for-bit reproduction check.

    python -m evaluation.tier_latency_extra
Outputs: results/latency/tier_latency_extra.json, manifest keys latency_extra.*
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import numpy as np

from evaluation.tier_latency import URL, payloads, pct, start_server
from tools.manifest import PROJECT_ROOT, provenance, record

OUT = PROJECT_ROOT / "results" / "latency"
LEVELS = (1, 2, 4, 8, 16)
REQS_PER_LEVEL = 200
SIZES_KB = (1, 4, 16, 64)
REQS_PER_SIZE = 50
TIER2_N = 20
LMSTUDIO = "http://localhost:1234/v1"


def concurrency(P) -> dict:
    out = {}
    for c in LEVELS:
        lat = []

        def one(p):
            with httpx.Client(timeout=120) as cl:
                t0 = time.perf_counter()
                r = cl.post(f"{URL}/tier1/score", json=p)
                r.raise_for_status()
                return (time.perf_counter() - t0) * 1e3

        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=c) as ex:
            lat = list(ex.map(one, P[:REQS_PER_LEVEL]))
        wall = time.perf_counter() - t0
        out[f"c{c}"] = {"client_ms": pct(lat), "throughput_rps": REQS_PER_LEVEL / wall}
        print(f"  concurrency {c:2d}: p50 {out[f'c{c}']['client_ms']['p50']:.0f} ms  p99 "
              f"{out[f'c{c}']['client_ms']['p99']:.0f} ms  {out[f'c{c}']['throughput_rps']:.1f} req/s", flush=True)
    return out


def payload_sizes(P) -> dict:
    base = max((p["text"] for p in P), key=len)
    out = {}
    with httpx.Client(timeout=300) as cl:
        for kb in SIZES_KB:
            text = (base + "\n") * (kb * 1024 // (len(base) + 1) + 1)
            text = text[:kb * 1024]
            cli, pii = [], []
            for p in P[:REQS_PER_SIZE]:
                t0 = time.perf_counter()
                r = cl.post(f"{URL}/tier1/score", json={**p, "text": text}).json()
                cli.append((time.perf_counter() - t0) * 1e3)
                pii.append(r["timing_ms"]["pii_text"])
            out[f"kb{kb}"] = {"chars": len(text), "client_ms": pct(cli), "server_pii_ms": pct(pii)}
            print(f"  payload {kb:2d} KB: client p50 {out[f'kb{kb}']['client_ms']['p50']:.0f} ms, "
                  f"PII p50 {out[f'kb{kb}']['server_pii_ms']['p50']:.0f} ms", flush=True)
    return out


def tier2_vlm() -> dict:
    model = os.getenv("HYBRIDSAAS_VLM_MODEL", "gemma-3-4b-it")
    try:
        ids = [m["id"] for m in httpx.get(f"{LMSTUDIO}/models", timeout=5).json()["data"]]
    except (httpx.HTTPError, KeyError, ValueError):
        return {"skipped": "LM Studio not reachable"}
    if model not in ids and not any(i.endswith("/" + model) for i in ids):
        return {"skipped": f"{model} not served"}
    gt = json.loads((PROJECT_ROOT / "evaluation" / "pii_testset_v2" / "ground_truth.json").read_text(encoding="utf-8"))
    imgs = [d for d in gt["documents"] if d["subset"] == "v2" and d["category"] != "text_extractable"]
    rng = np.random.default_rng(11)                      # same pick rule as T3.6
    pick = [imgs[i] for i in rng.choice(len(imgs), TIER2_N, replace=False)]
    hold, proc, branches, outcomes = [], [], {}, {}
    with httpx.Client(timeout=600) as cl:
        for d in pick:
            path = str(PROJECT_ROOT / "evaluation" / d["root"] / d["path"])
            j = cl.post(f"{URL}/tier2/submit", json={"image_path": path, "a_hybrid": 0.1}).json()
            while True:
                s = cl.get(f"{URL}/tier2/{j['job_id']}").json()
                if s["state"] == "DONE":
                    break
                time.sleep(0.1)
            hold.append(s["hold_ms"]); proc.append(s["processing_ms"])
            branches[s["branch"]] = branches.get(s["branch"], 0) + 1
            outcomes[s["release"]] = outcomes.get(s["release"], 0) + 1
    return {"model": model, "hold_ms": pct(hold), "processing_ms": pct(proc), "branches": branches,
            "outcomes": outcomes, "note": "first job includes EasyOCR and VLM warm-up; a_hybrid fixed at 0.1"}


def main() -> None:
    P = payloads(REQS_PER_LEVEL + 20)
    srv = start_server()
    res = {}
    try:
        with httpx.Client(timeout=120) as cl:                  # warm the models
            for p in P[-20:]:
                cl.post(f"{URL}/tier1/score", json=p)
        res["concurrency"] = concurrency(P)
        res["payload"] = payload_sizes(P)
        res["tier2_vlm"] = tier2_vlm()
        print(f"  tier2: {res['tier2_vlm']}", flush=True)
    finally:
        srv.kill(); srv.wait()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tier_latency_extra.json").write_text(json.dumps(
        {"provenance": provenance("evaluation/tier_latency_extra.py", {"payloads": 7, "tier2_pick": 11}, "cpu+gpu"),
         **res}, indent=1), encoding="utf-8")
    record("latency_extra", res, script="evaluation/tier_latency_extra.py", seeds={"payloads": 7, "tier2_pick": 11})
    print(f"  -> {OUT / 'tier_latency_extra.json'}")


if __name__ == "__main__":
    main()
