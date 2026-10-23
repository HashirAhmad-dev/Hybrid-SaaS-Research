"""
propose_doc_changes.py
======================
Paper-v2 task T4.2 (gate G-DOCS). Builds the proposed edits to the design docs in
Context/ WITHOUT touching them: edited copies go to a scratch folder and the
unified diff is written to docs/proposed/T4.2_Context.diff for review. Apply only
after the user approves (gate G-DOCS):

    python -m tools.propose_doc_changes            # write the review diff only
    python -m tools.propose_doc_changes --apply    # after approval: edit Context/ in place
"""
from __future__ import annotations

import difflib
from pathlib import Path

from tools.manifest import PROJECT_ROOT

CTX = PROJECT_ROOT / "Context"
OUT = PROJECT_ROOT / "docs" / "proposed" / "T4.2_Context.diff"

V2_NOTE = ("\n> **paper-v2 update (2026-10-23).** Numbers on this page from the seed-42 run are superseded by "
           "means over 10 independently generated datasets with cluster-bootstrap intervals. "
           "See `docs/FIXES_SUMMARY.md` and `docs/CLAIM_EVIDENCE.md`; every number is in `results/manifest.json`.\n")

EDITS = {
    "01-Research-Paper/Abstract.md": [
        ("a real-time interception architecture built around three components:",
         "an inline interception architecture with a two-tier latency budget, built around three components:"),
        ("A federated learning module lets multiple tenants train shared models without exchanging raw logs.",
         "Federated multi-tenant training is future work and was not built."),
        ("__APPEND__", V2_NOTE),
    ],
    "01-Research-Paper/Federated Learning.md": [
        ("# Federated Learning\n",
         "# Federated Learning (future work, not built)\n\n> Nothing on this page was implemented or evaluated. It is an architectural "
         "vision only and is not a contribution of the paper.\n"),
        ("HybridSaaS-Sec uses a federated learning module.", "A future version could use a federated learning module."),
    ],
    "01-Research-Paper/Introduction.md": [
        ("4. A **federated learning module** for multi-tenant model training without moving raw logs across boundaries.",
         "4. (Removed from the contributions: federated multi-tenant training was not built; see [[Federated Learning]] as future work.)"),
        ("__APPEND__", V2_NOTE),
    ],
    "01-Research-Paper/Threat Model and Goals.md": [
        ("| **G5** | Fast enforcement (end-to-end budget < 300 ms). |",
         "| **G5** | Fast enforcement, in two tiers: Tier 1 inline (text PII, behaviour, risk fusion) within a few tens of ms; Tier 2 asynchronous for images, with the upload held. |"),
        ("**Partially.** Anomaly scoring is 16.9 ms and the text PII branch 11.3 ms, comfortably inside budget. The image branches (OCR 2.4 s, VLM 3.5 s as a hosted call) are **not** — they would have to run asynchronously or on-box, as the design intends. |",
         "**Tier 1 met:** measured inside the running proxy over 1,000 warm requests, p50 33.7 ms, p95 40.5 ms, p99 44.6 ms (`latency.tier1.*`). **Tier 2:** hold time p50 3.4 s, p95 5.3 s with EasyOCR on CPU (`latency.tier2.*`). The old single 300 ms end-to-end goal is withdrawn. |"),
    ],
    "03-Running-the-Demo/REST Endpoints.md": [
        ("You can use query parameters `alpha` (LSTM weight, default 0.5) and `beta` (enterprise risk multiplier, default 0.5) on `/score` to replay the simulation under different SBRS configurations.",
         "You can use query parameters `alpha` (LSTM weight; default read from the trained engine, 0.25) and `beta` (enterprise risk multiplier, default 2.5) on `/score` to replay the simulation under different SBRS configurations.\n\n"
         "Two-tier endpoints (paper-v2): `POST /tier1/score` (inline decision with per-stage timings and the configured gated enforcement), "
         "`POST /tier2/submit` and `GET /tier2/{job_id}` (hold an image upload, scan it asynchronously, then release or escalate). "
         "The configuration and the manifest key behind every value are in `backend/config/final_config.json`."),
    ],
    "01-Research-Paper/Semantic-Behavioral Risk Score (SBRS).md": [
        ("__APPEND__",
         "\n## Fusion form comparison (paper-v2, T2.5)\n\nAt the same benign budget (ALERT at the 95th, BLOCK at the 99.5th percentile of benign "
         "validation scores), across 10 generated datasets: threat recall gated 0.642, additive 0.630, logistic 0.627, "
         "multiplicative 0.589, max 0.320. The multiplicative form escalates 1 of 35 threats with low S and high A; gated "
         "fusion escalates all 35. The backend now runs gated fusion (escalate when A is at or above the hybrid's validation "
         "threshold, whatever S is) and keeps the multiplicative score for reference. The validation knee for beta ranges from "
         "2.0 to 8.0 across datasets, so beta = 2.5 is a property of one dataset, not a constant. Keys: `fusion.summary.*`, "
         "`anomaly.multiseed.sbrs_beta_recalibrated.*`.\n"),
    ],
    "01-Research-Paper/Hybrid Anomaly Engine.md": [
        ("__APPEND__",
         "\n## paper-v2 results (10 datasets, cluster bootstrap)\n\nThe hybrid's flag F1 (0.629, CI 0.564 to 0.702) is not different "
         "from Isolation Forest alone (difference 0.003, CI -0.013 to 0.020); its AUC is below the LSTM alone and a per-user z-score. "
         "A CUSUM drift detector beside the hybrid raises malicious-insider episode recall from 0.133 to 0.567 (median 8.9 h to "
         "detection) at a false-positive rate of 0.8 percent instead of 0.25 percent. Keys: `stats.*`, `ablation.summary.*`, `drift.summary.*`.\n"),
    ],
    "01-Research-Paper/Evaluation.md": [("__APPEND__", V2_NOTE)],
    "01-Research-Paper/Multimodal PII Detection.md": [("__APPEND__", V2_NOTE)],
}


def main() -> None:
    import sys
    apply = "--apply" in sys.argv
    patches = []
    for rel, edits in EDITS.items():
        p = CTX / rel
        old = p.read_text(encoding="utf-8")
        new = old
        for a, b in edits:
            if a == "__APPEND__":
                new = new.rstrip("\n") + "\n" + b
            else:
                if a not in new:
                    raise SystemExit(f"{rel}: anchor not found: {a[:60]!r}")
                new = new.replace(a, b, 1)
        if apply:
            raw = p.read_bytes()
            crlf = b"\r\n" in raw
            p.write_bytes((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
        patches += difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        fromfile=f"a/Context/{rel}", tofile=f"b/Context/{rel}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(patches), encoding="utf-8")
    print(f"{len(EDITS)} files, diff -> {OUT}" + ("  (APPLIED to Context/)" if apply else "  (review only)"))


if __name__ == "__main__":
    main()
