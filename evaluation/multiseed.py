"""
multiseed.py
============
Paper-v2 task T1.4: spread across INDEPENDENTLY GENERATED datasets.

The original 3-seed study varied only the training seed on one dataset, so its
spread said nothing about how much the numbers depend on the particular draw of
users, attacks and benign bursts. Here every seed in
`evaluation/config/seeds.json` gets:

    1. a fresh dataset      generate_sessions --seed s
    2. a fresh model        train_and_evaluate --seed s          (val-tuned, test once)
    3. fresh SBRS bands     calibrate_sbrs on that run's val split

Each step runs in its own process and writes into results/runs/data_seed_<s>/,
never into the canonical evaluation/data files. Numbers go to the manifest under
`anomaly.ds<s>.*`, `sbrs.ds<s>.*`, `generation.s<s>.*`; the summary goes under
`anomaly.multiseed.<metric>.{mean,sd,min,max,n}` and to
results/multiseed_summary.{json,csv}.

    python -m evaluation.multiseed              # all seeds
    python -m evaluation.multiseed --seeds 42   # one seed (used by the determinism check)
    python -m evaluation.multiseed --summarise-only
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np

from tools.manifest import PROJECT_ROOT, load, provenance, record

SEEDS_FILE = PROJECT_ROOT / "evaluation" / "config" / "seeds.json"
RUNS = PROJECT_ROOT / "results" / "runs"
SUMMARY_JSON = PROJECT_ROOT / "results" / "multiseed_summary.json"
SUMMARY_CSV = PROJECT_ROOT / "results" / "multiseed_summary.csv"

CLASSES = ("malicious_insider", "compromised_account", "negligent_insider",
           "overscoped_thirdparty")

# metric name -> manifest key suffix under anomaly.ds<s>. / sbrs.ds<s>.
HEADLINE = {
    "positives_total": "anomaly:dataset.positives_total",
    "positive_rate": "anomaly:dataset.positive_rate",
    "test_positives": "anomaly:dataset.per_split.test.positives",
    "test_benign_bursts": "anomaly:dataset.per_split.test.benign_bursts",
    "alpha": "anomaly:tuning.alpha",
    "tau_hybrid": "anomaly:tuning.tau_hybrid",
    **{f"f1_{d}": f"anomaly:test_flag_level.{d}.f1"
       for d in ("ewma_tuned", "lstm_only", "if_only", "hybrid")},
    **{f"fpr_{d}": f"anomaly:test_flag_level.{d}.fpr"
       for d in ("ewma_tuned", "lstm_only", "if_only", "hybrid")},
    **{f"recall_{d}": f"anomaly:test_flag_level.{d}.recall"
       for d in ("ewma_tuned", "lstm_only", "if_only", "hybrid")},
    **{f"auc_{d}": f"anomaly:test_auc_overall.{d}" for d in ("lstm", "if", "hybrid")},
    "enf_f1_shipped_bands": "anomaly:test_enforcement_bands.hybrid_alert_or_block.f1",
    "enf_fpr_shipped_bands": "anomaly:test_enforcement_bands.hybrid_alert_or_block.fpr",
    "enf_recall_shipped_bands": "anomaly:test_enforcement_bands.hybrid_alert_or_block.recall",
    "sbrs_beta_recalibrated": "sbrs:beta.chosen",
    "sbrs_t_alert_recalibrated": "sbrs:bands.t_alert",
    "sbrs_t_block_recalibrated": "sbrs:bands.t_block",
    "enf_f1_recalibrated": "sbrs:test.new_calibrated.flagged_f1",
    "enf_fpr_recalibrated": "sbrs:test.new_calibrated.flagged.fpr",
    "enf_recall_recalibrated": "sbrs:test.new_calibrated.flagged.recall",
    "insider_op_f1": "anomaly:test_insider_oriented_operating_point.f1",
    "insider_op_fpr": "anomaly:test_insider_oriented_operating_point.fpr",
    "insider_op_malicious_recall": "anomaly:test_insider_oriented_operating_point.malicious_insider_recall",
    "insider_op_benign_burst_flag_rate": "anomaly:test_insider_oriented_operating_point.benign_burst_flag_rate",
    "benign_burst_flag_rate_ewma": "anomaly:benign_burst.ewma_flag_rate",
    "benign_burst_flag_rate_hybrid": "anomaly:benign_burst.hybrid_flag_rate",
    **{f"recall_{c}": f"anomaly:per_class_recall.{c}.hybrid_recall" for c in CLASSES},
    **{f"episode_recall_{c}": f"anomaly:per_class_recall.{c}.hybrid_episode_recall" for c in CLASSES},
    **{f"auc_lstm_{c}": f"anomaly:per_class_recall.{c}.auc_lstm" for c in CLASSES},
    **{f"auc_if_{c}": f"anomaly:per_class_recall.{c}.auc_if" for c in CLASSES},
    **{f"auc_hybrid_{c}": f"anomaly:per_class_recall.{c}.auc_hybrid" for c in CLASSES},
    "latency_mean_ms": "anomaly:latency.mean_ms",
}


def seeds_from_config() -> List[int]:
    return list(json.loads(SEEDS_FILE.read_text(encoding="utf-8"))["data_seeds"])


def run(cmd: List[str], log: Path) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        r = subprocess.run([sys.executable, *cmd], cwd=PROJECT_ROOT, stdout=f,
                           stderr=subprocess.STDOUT, env={**__import__("os").environ,
                                                          "PYTHONUTF8": "1"})
    if r.returncode != 0:
        raise SystemExit(f"failed ({r.returncode}): {' '.join(cmd)}; see {log}")


def run_seed(s: int) -> None:
    base = RUNS / f"data_seed_{s}"
    data, out = base / "data", base / "run"
    print(f"[seed {s}] generate -> train -> calibrate", flush=True)
    run(["-m", "evaluation.generate_sessions", "--seed", str(s), "--out-dir", str(data)],
        base / "generate.log")
    run(["-m", "evaluation.train_and_evaluate", "--seed", str(s), "--data-dir", str(data),
         "--out-dir", str(out), "--manifest-prefix", f"anomaly.ds{s}"], base / "train.log")
    run(["-m", "evaluation.calibrate_sbrs", "--scored", str(out / "scored_all_splits.csv"),
         "--out", str(out / "sbrs_calibration.json"), "--manifest-prefix", f"sbrs.ds{s}"],
        base / "calibrate.log")


def summarise(seeds: List[int]) -> Dict[str, dict]:
    entries = load()["entries"]
    per_seed: Dict[str, List[float]] = {}
    for name, spec in HEADLINE.items():
        kind, key = spec.split(":", 1)
        vals = []
        for s in seeds:
            k = f"{kind}.ds{s}.{key}"
            if k not in entries:
                raise KeyError(f"{k} missing; run the seed first")
            vals.append(float(entries[k]["value"]))
        per_seed[name] = vals
    summary = {}
    for name, vals in per_seed.items():
        v = np.array(vals, dtype=float)
        finite = v[np.isfinite(v)]
        summary[name] = {
            "n": int(len(finite)),
            "mean": float(finite.mean()) if len(finite) else float("nan"),
            "sd": float(finite.std(ddof=1)) if len(finite) > 1 else float("nan"),
            "min": float(finite.min()) if len(finite) else float("nan"),
            "max": float(finite.max()) if len(finite) else float("nan"),
            "values": {str(s): x for s, x in zip(seeds, vals)},
        }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--summarise-only", action="store_true")
    args = ap.parse_args()
    seeds = args.seeds or seeds_from_config()

    if not args.summarise_only:
        for s in seeds:
            run_seed(s)

    if args.seeds is not None and len(seeds) < 2:
        print("single seed run: no summary written")
        return
    summary = summarise(seeds)
    prov = provenance("evaluation/multiseed.py", {"data_and_train": seeds}, device="cpu")
    SUMMARY_JSON.write_text(json.dumps({"provenance": prov, "seeds": seeds,
                                        "spread": "sample sd (ddof=1) across datasets",
                                        "metrics": summary}, indent=1), encoding="utf-8")
    with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "n", "mean", "sd", "min", "max", *[f"seed_{s}" for s in seeds]])
        for name, d in summary.items():
            w.writerow([name, d["n"], f"{d['mean']:.6g}", f"{d['sd']:.6g}", f"{d['min']:.6g}",
                        f"{d['max']:.6g}", *[f"{d['values'][str(s)]:.6g}" for s in seeds]])
    record("anomaly.multiseed", {k: {kk: vv for kk, vv in d.items() if kk != "values"}
                                 for k, d in summary.items()},
           script="evaluation/multiseed.py", seeds={"data_and_train": seeds}, device="cpu")

    print(f"\n{'metric':<36}{'mean':>9}{'sd':>9}{'min':>9}{'max':>9}")
    for name, d in summary.items():
        print(f"{name:<36}{d['mean']:>9.4f}{d['sd']:>9.4f}{d['min']:>9.4f}{d['max']:>9.4f}")
    print(f"\n  -> {SUMMARY_JSON}\n  -> {SUMMARY_CSV}")


if __name__ == "__main__":
    main()
