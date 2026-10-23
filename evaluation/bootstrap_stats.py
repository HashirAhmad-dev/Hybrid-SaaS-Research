"""
bootstrap_stats.py
==================
Paper-v2 task T2.2: honest uncertainty for every headline anomaly number.

Why: windows inside one attack episode, and sessions of one user, are not
independent. Wilson intervals over windows treat them as independent and are too
narrow. Here the TEST rows of each dataset are resampled in clusters:

    stage 1  resample USERS with replacement (all of a user's test rows move together)
    stage 2  inside each drawn user, resample that user's ATTACK EPISODES with
             replacement (all windows of an episode move together); the user's
             non-attack rows are kept as drawn in stage 1

Thresholds are the ones chosen on validation (T2.1); only test rows are
resampled, so no selection is repeated. For every replicate the metric is
computed per dataset and then averaged over the datasets, giving a 95 %
percentile interval for the mean-over-datasets number the paper quotes. A
paired version applies the SAME resample to two detectors and gives an interval
for their difference (hybrid minus baseline).

Wilson intervals (window level, dataset 42 only) are kept as a labelled
secondary column. Confusion matrices per class are written for the hybrid.

    python -m evaluation.bootstrap_stats [--resamples 10000] [--seed 20261023]
Outputs: results/stats/bootstrap_summary.json, results/stats/*.csv, manifest keys stats.*
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Callable, Dict, List

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from evaluation.ablation import DETECTORS
from evaluation.common import THREAT_CLASSES, wilson_ci
from evaluation.multiseed import RUNS, seeds_from_config
from tools.manifest import PROJECT_ROOT, load, provenance, record

OUT = PROJECT_ROOT / "results" / "stats"
BOOT_SEED = 20261023
REFERENCE = "hybrid_weighted"


def fast_auc(score: np.ndarray, y: np.ndarray) -> float:
    """Rank AUC with average ranks for ties (equals selection.auc_rank)."""
    n1 = int(y.sum()); n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return np.nan
    r = rankdata(score)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def f1_from(flag: np.ndarray, y: np.ndarray) -> float:
    tp = int((flag & y).sum()); fp = int((flag & ~y).sum()); fn = int((~flag & y).sum())
    return 2 * tp / (2 * tp + fp + fn) if tp else 0.0


class Dataset:
    """Test rows of one generated dataset, with cluster indices for resampling."""

    def __init__(self, seed: int):
        rows = pd.read_csv(RUNS / f"data_seed_{seed}" / "ablation" / "row_scores.csv")
        thr = load()["entries"]
        self.seed = seed
        te = rows[rows.split == "test"].reset_index(drop=True)
        self.y = te.is_true_threat.to_numpy(dtype=bool)
        self.tc = te.threat_class.fillna("").to_numpy()
        self.bb = te.is_benign_burst.to_numpy(dtype=bool)
        self.scores = {d: te[f"score_{d}"].to_numpy(dtype=float) for d in DETECTORS}
        self.flags = {d: self.scores[d] >= float(thr[f"ablation.ds{seed}.{d}.val_threshold_f1"]["value"])
                      for d in DETECTORS}
        users = te.user_id.to_numpy()
        eps = te.episode_id.fillna("").to_numpy()
        self.user_rows: Dict[str, np.ndarray] = {}
        self.user_eps: Dict[str, List[np.ndarray]] = {}
        self.user_other: Dict[str, np.ndarray] = {}
        for u in np.unique(users):
            m = users == u
            att = m & self.y
            self.user_eps[u] = [np.flatnonzero(att & (eps == e)) for e in np.unique(eps[att])]
            self.user_other[u] = np.flatnonzero(m & ~self.y)
        self.users = np.unique(users)

    def resample(self, rng: np.random.Generator) -> np.ndarray:
        idx = []
        for u in rng.choice(self.users, size=len(self.users), replace=True):
            idx.append(self.user_other[u])
            eps = self.user_eps[u]
            if eps:
                for k in rng.integers(0, len(eps), size=len(eps)):
                    idx.append(eps[k])
        return np.concatenate(idx)


def metrics_for(ds: Dataset, d: str, idx: np.ndarray) -> Dict[str, float]:
    y, s, f = ds.y[idx], ds.scores[d][idx], ds.flags[d][idx]
    tc = ds.tc[idx]
    out = {"auc": fast_auc(s, y), "f1": f1_from(f, y),
           "recall": float(f[y].mean()) if y.any() else np.nan,
           "fpr": float(f[~y].mean()) if (~y).any() else np.nan}
    for c in THREAT_CLASSES:
        m = tc == c
        out[f"recall_{c}"] = float(f[m].mean()) if m.any() else np.nan
    bb = ds.bb[idx]
    out["benign_burst_flag_rate"] = float(f[bb].mean()) if bb.any() else np.nan
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resamples", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=BOOT_SEED)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--manifest-prefix", default="stats")
    args = ap.parse_args()
    out = args.out_dir
    seeds = seeds_from_config()
    data = [Dataset(s) for s in seeds]
    rng = np.random.default_rng(args.seed)
    names = list(metrics_for(data[0], REFERENCE, np.arange(len(data[0].y))).keys())

    point = {d: {k: float(np.nanmean([metrics_for(ds, d, np.arange(len(ds.y)))[k] for ds in data]))
                 for k in names} for d in DETECTORS}
    reps = {d: {k: np.empty(args.resamples) for k in names} for d in DETECTORS}
    for b in range(args.resamples):
        idxs = [ds.resample(rng) for ds in data]          # one draw shared by all detectors (paired)
        for d in DETECTORS:
            per = [metrics_for(ds, d, ix) for ds, ix in zip(data, idxs)]
            for k in names:
                reps[d][k][b] = np.nanmean([p[k] for p in per])
        if (b + 1) % 1000 == 0:
            print(f"  {b + 1}/{args.resamples} resamples", flush=True)

    summary = {"_meta": {"resamples": args.resamples, "bootstrap_seed": args.seed,
                         "datasets": seeds, "reference": REFERENCE,
                         "unit": "two-stage cluster bootstrap: users, then attack episodes within user; "
                                 "metric averaged over datasets per replicate; 95% percentile interval"}}
    for d in DETECTORS:
        summary[d] = {}
        for k in names:
            r = reps[d][k][np.isfinite(reps[d][k])]
            summary[d][k] = {"point": point[d][k],
                             "ci_lo": float(np.percentile(r, 2.5)) if len(r) else np.nan,
                             "ci_hi": float(np.percentile(r, 97.5)) if len(r) else np.nan}
        if d != REFERENCE:
            summary[d]["paired_vs_hybrid"] = {}
            for k in ("auc", "f1", "recall", "fpr", "recall_malicious_insider"):
                diff = reps[REFERENCE][k] - reps[d][k]
                diff = diff[np.isfinite(diff)]
                summary[d]["paired_vs_hybrid"][k] = {
                    "hybrid_minus_this": point[REFERENCE][k] - point[d][k],
                    "ci_lo": float(np.percentile(diff, 2.5)), "ci_hi": float(np.percentile(diff, 97.5)),
                    # lower FPR is better, higher is better for everything else
                    "share_of_resamples_hybrid_not_better":
                        float((diff >= 0).mean() if k == "fpr" else (diff <= 0).mean())}

    # Wilson (secondary, window level, dataset 42) and per-class confusion matrices for the hybrid
    ds42 = data[seeds.index(42)] if 42 in seeds else data[0]
    wil, conf = {}, {}
    for d in DETECTORS:
        f = ds42.flags[d]
        wil[d] = {}
        for c in THREAT_CLASSES:
            m = ds42.tc == c
            k, n = int(f[m].sum()), int(m.sum())
            lo, hi = wilson_ci(k, n)
            wil[d][c] = {"k": k, "n": n, "recall": k / n if n else np.nan, "wilson_lo": lo, "wilson_hi": hi}
    for ds in data:
        f = ds.flags[REFERENCE]
        cm = {}
        for c in THREAT_CLASSES:
            m = ds.tc == c
            cm[c] = {"detected": int(f[m].sum()), "missed": int((~f[m]).sum())}
        neg_plain = ~ds.y & ~ds.bb
        cm["ordinary_negative"] = {"flagged": int(f[neg_plain].sum()), "not_flagged": int((~f[neg_plain]).sum())}
        cm["benign_burst"] = {"flagged": int(f[ds.bb].sum()), "not_flagged": int((~f[ds.bb]).sum())}
        conf[str(ds.seed)] = cm
    summary["_wilson_secondary_dataset42"] = wil
    summary["_confusion_hybrid_by_dataset"] = conf

    out.mkdir(parents=True, exist_ok=True)
    (out / "bootstrap_summary.json").write_text(json.dumps(
        {"provenance": provenance("evaluation/bootstrap_stats.py",
                                  {"bootstrap": args.seed, "datasets": seeds}), **summary},
        indent=1, default=float), encoding="utf-8")
    with open(out / "bootstrap_intervals.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["detector", "metric", "point_mean_over_datasets", "ci95_lo", "ci95_hi"])
        for d in DETECTORS:
            for k in names:
                v = summary[d][k]
                w.writerow([d, k, f"{v['point']:.4f}", f"{v['ci_lo']:.4f}", f"{v['ci_hi']:.4f}"])
    with open(out / "paired_vs_hybrid.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["baseline", "metric", "hybrid_minus_baseline", "ci95_lo", "ci95_hi",
                    "share_hybrid_not_better"])
        for d in DETECTORS:
            for k, v in summary[d].get("paired_vs_hybrid", {}).items():
                w.writerow([d, k, f"{v['hybrid_minus_this']:.4f}", f"{v['ci_lo']:.4f}",
                            f"{v['ci_hi']:.4f}", f"{v['share_of_resamples_hybrid_not_better']:.4f}"])
    with open(out / "confusion_hybrid_by_class.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["dataset_seed", "row_group", "flagged_or_detected", "not_flagged_or_missed"])
        for s, cm in conf.items():
            for g, v in cm.items():
                a, b = list(v.values())
                w.writerow([s, g, a, b])
    record(args.manifest_prefix, summary, script="evaluation/bootstrap_stats.py",
           seeds={"bootstrap": args.seed, "datasets": seeds})
    print(f"  -> {out}")


if __name__ == "__main__":
    main()
