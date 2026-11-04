"""
latency_cutoff.py
=================
Task F12 (D-035): reconcile the single-client Tier 1 latency figures and choose and
check a text-size cutoff that sends large text to Tier 2.

  A  decompose  {persistent, new connection} x {corpus texts, 1 KB text}, cutoff off
  B  calibrate  text sizes 0.25 to 8 KB, cutoff off; cutoff = largest size whose server
                p95 is within BUDGET_MS
  C  check      cutoff on: corpus texts, 16 KB and 64 KB texts, and the Tier 2 hold of
                the routed texts

    python -m evaluation.latency_cutoff
Outputs: results/latency/latency_cutoff.json, manifest keys latency_cutoff.*
"""
from __future__ import annotations

import json
import os
import time

import httpx
import numpy as np

from evaluation.tier_latency import URL, payloads, pct, start_server
from tools.manifest import PROJECT_ROOT, provenance, record

OUT = PROJECT_ROOT / "results" / "latency"
BUDGET_MS = 100.0
N_DECOMP, N_CAL, N_BIG, N_HOLD = 300, 100, 50, 10
CAL_KB = (0.25, 0.5, 1, 2, 4, 8)


def text_of(base: str, nbytes: int) -> str:
    t = (base + "\n") * (nbytes // (len(base) + 1) + 1)
    return t.encode("utf-8")[:nbytes].decode("utf-8", "ignore")


def run(P, client_factory, text=None, n=100):
    cl_ms, srv_total, srv_pii, jobs = [], [], [], []
    shared = client_factory() if client_factory is not None else None
    try:
        for p in P[:n]:
            c = shared or httpx.Client(timeout=300)
            t0 = time.perf_counter()
            r = c.post(f"{URL}/tier1/score", json={**p, "text": text if text is not None else p["text"]}).json()
            cl_ms.append((time.perf_counter() - t0) * 1e3)
            srv_total.append(r["timing_ms"]["total"]); srv_pii.append(r["timing_ms"]["pii_text"])
            if r.get("job_id"):
                jobs.append(r["job_id"])
            if shared is None:
                c.close()
    finally:
        if shared is not None:
            shared.close()
    return {"client_ms": pct(cl_ms), "server_total_ms": pct(srv_total), "server_pii_ms": pct(srv_pii)}, jobs


def with_server(env_cut: int, fn):
    os.environ["HYBRIDSAAS_TIER1_MAX_TEXT_BYTES"] = str(env_cut)
    srv = start_server()
    try:
        with httpx.Client(timeout=120) as c:
            for p in WARM:
                c.post(f"{URL}/tier1/score", json=p)
        return fn()
    finally:
        srv.kill(); srv.wait()


def main() -> None:
    global WARM
    P = payloads(N_DECOMP + 20)
    WARM = P[-20:]
    base = max((p["text"] for p in P), key=len)
    res = {"corpus_text_bytes": {"median": float(np.median([len(p["text"].encode()) for p in P])),
                                 "max": float(max(len(p["text"].encode()) for p in P))}}
    persistent = lambda: httpx.Client(timeout=300)

    def decompose():
        out = {}
        for conn, fac in (("persistent", persistent), ("new_connection", None)):
            for size, txt in (("corpus", None), ("1kb", text_of(base, 1024))):
                out[f"{conn}_{size}"] = run(P, fac, txt, N_DECOMP)[0]
                print(f"  {conn:15s} {size:6s} client p50 {out[f'{conn}_{size}']['client_ms']['p50']:.1f} ms  "
                      f"server PII p50 {out[f'{conn}_{size}']['server_pii_ms']['p50']:.1f} ms", flush=True)
        return out

    def calibrate():
        out = {}
        for kb in CAL_KB:
            out[f"kb{kb:g}".replace(".", "p")] = run(P, persistent, text_of(base, int(kb * 1024)), N_CAL)[0]
            v = out[f"kb{kb:g}".replace(".", "p")]
            print(f"  {kb:5g} KB server total p95 {v['server_total_ms']['p95']:.1f} ms", flush=True)
        return out

    res["decompose"] = with_server(0, decompose)
    res["calibrate"] = with_server(0, calibrate)
    ok = [kb for kb in CAL_KB if res["calibrate"][f"kb{kb:g}".replace(".", "p")]["server_total_ms"]["p95"] <= BUDGET_MS]
    chosen = int(max(ok) * 1024) if ok else int(CAL_KB[0] * 1024)
    res["chosen_bytes"], res["budget_ms"] = chosen, BUDGET_MS
    print(f"  cutoff {chosen} bytes", flush=True)

    def check():
        out = {"corpus": run(P, persistent, None, N_DECOMP)[0]}
        with httpx.Client(timeout=600) as c:
            def wait(j):
                while True:
                    s = c.get(f"{URL}/tier2/{j}").json()
                    if s["state"] == "DONE":
                        return s["hold_ms"]
                    time.sleep(0.1)
            for kb in (16, 64):
                r, jobs = run(P, persistent, text_of(base, kb * 1024), N_BIG)     # inline latency, burst
                for j in jobs:                                                      # drain the queue
                    wait(j)
                hold = []                                                           # Tier 2 hold, one at a time
                for p in P[:N_HOLD]:
                    j = c.post(f"{URL}/tier1/score", json={**p, "text": text_of(base, kb * 1024)}).json().get("job_id")
                    if j:
                        hold.append(wait(j))
                out[f"kb{kb}"] = {**r, "routed_in_burst": len(jobs), "tier2_hold_ms_sequential": pct(hold) if hold else None}
                print(f"  cutoff on, {kb} KB: Tier 1 client p50 {r['client_ms']['p50']:.1f} ms; routed {len(jobs)} of {N_BIG}; "
                      f"Tier 2 hold p50 {np.median(hold) if hold else float('nan'):.0f} ms", flush=True)
        return out

    res["check"] = with_server(chosen, check)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "latency_cutoff.json").write_text(json.dumps(
        {"provenance": provenance("evaluation/latency_cutoff.py", {"payloads": 7}, "cpu"), **res}, indent=1),
        encoding="utf-8")
    record("latency_cutoff", res, script="evaluation/latency_cutoff.py", seeds={"payloads": 7})
    print(f"  -> {OUT / 'latency_cutoff.json'}")


if __name__ == "__main__":
    main()
