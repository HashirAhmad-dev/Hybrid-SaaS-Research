"""
bootstrap_extra.py
==================
Task F4: paired cluster-bootstrap intervals that T2.2 did not cover.

  1. Average precision (AP) for every detector, and the paired difference
     hybrid minus each detector (the question: does fusion add AP over Isolation Forest?).
  2. The five SBRS fusion forms of T2.5 at their equal benign budget: threat recall,
     benign ALERT-or-BLOCK rate and F1, with paired differences against the
     multiplicative form.

Same resampling as evaluation/bootstrap_stats.py (users, then attack episodes within
user; metric averaged over the 10 datasets per replicate). Thresholds and fusion
parameters are the validation choices of T2.1 and T2.5; only test rows are resampled.

    python -m evaluation.bootstrap_extra [--resamples 10000]
Outputs: results/stats/bootstrap_extra.json, manifest keys stats_extra.*
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from evaluation.ablation import DETECTORS
from evaluation.bootstrap_stats import OUT, REFERENCE, Dataset
from evaluation.multiseed import RUNS, seeds_from_config
from evaluation.sbrs_fusion import FORMS, fit_forms
from tools.manifest import load, provenance, record

BOOT_SEED = 20261103
FUSION_REF = "multiplicative"


def fast_ap(score: np.ndarray, y: np.ndarray) -> float:
    """Average precision, equal to sklearn.metrics.average_precision_score (ties grouped)."""
    n1 = int(y.sum())
    if n1 == 0:
        return np.nan
    o = np.argsort(-score, kind="mergesort")
    s, t = score[o], y[o]
    last = np.r_[np.flatnonzero(np.diff(s)), len(s) - 1]       # end of each tie group
    tp = np.cumsum(t)[last]
    fp = (last + 1) - tp
    prec = tp / (tp + fp)
    rec = tp / n1
    return float(np.sum(np.diff(np.r_[0.0, rec]) * prec))


def fusion_actions(seed: int, e: dict) -> dict:
    rows = pd.read_csv(RUNS / f"data_seed_{seed}" / "ablation" / "row_scores.csv")
    tau_a = float(e[f"ablation.ds{seed}.hybrid_weighted.val_threshold_f1"]["value"])
    forms = fit_forms(rows, tau_a)
    te = rows[rows.split == "test"].reset_index(drop=True)      # same row order as Dataset
    S, A = te.pii_sensitivity_score.to_numpy(float), te.score_hybrid_weighted.to_numpy(float)
    return {n: forms[n].action(S, A) != "PERMIT" for n in FORMS}


def fusion_metrics(flag: np.ndarray, y: np.ndarray) -> dict:
    tp = int((flag & y).sum()); fp = int((flag & ~y).sum()); fn = int((~flag & y).sum())
    return {"threat_recall": tp / max(int(y.sum()), 1), "benign_alert_rate": fp / max(int((~y).sum()), 1),
            "f1": 2 * tp / (2 * tp + fp + fn) if tp else 0.0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resamples", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=BOOT_SEED)
    args = ap.parse_args()
    seeds = seeds_from_config()
    e = load()["entries"]
    data = [Dataset(s) for s in seeds]
    acts = [fusion_actions(s, e) for s in seeds]
    for ds, a in zip(data, acts):
        assert len(next(iter(a.values()))) == len(ds.y)

    def all_metrics(idxs):
        ap_ = {d: np.nanmean([fast_ap(ds.scores[d][ix], ds.y[ix]) for ds, ix in zip(data, idxs)]) for d in DETECTORS}
        fu = {}
        for n in FORMS:
            per = [fusion_metrics(a[n][ix], ds.y[ix]) for ds, a, ix in zip(data, acts, idxs)]
            fu[n] = {k: float(np.mean([p[k] for p in per])) for k in per[0]}
        return ap_, fu

    full = [np.arange(len(ds.y)) for ds in data]
    p_ap, p_fu = all_metrics(full)
    rng = np.random.default_rng(args.seed)
    r_ap = {d: np.empty(args.resamples) for d in DETECTORS}
    r_fu = {n: {k: np.empty(args.resamples) for k in p_fu[n]} for n in FORMS}
    for b in range(args.resamples):
        a_, f_ = all_metrics([ds.resample(rng) for ds in data])
        for d in DETECTORS:
            r_ap[d][b] = a_[d]
        for n in FORMS:
            for k in f_[n]:
                r_fu[n][k][b] = f_[n][k]
        if (b + 1) % 2000 == 0:
            print(f"  {b + 1}/{args.resamples}", flush=True)

    ci = lambda r: {"ci_lo": float(np.percentile(r[np.isfinite(r)], 2.5)),
                    "ci_hi": float(np.percentile(r[np.isfinite(r)], 97.5))}
    out = {"ap": {d: {"point": float(p_ap[d]), **ci(r_ap[d])} for d in DETECTORS},
           "ap_paired_hybrid_minus": {d: {"point": float(p_ap[REFERENCE] - p_ap[d]),
                                          **ci(r_ap[REFERENCE] - r_ap[d]),
                                          "share_hybrid_not_better": float(((r_ap[REFERENCE] - r_ap[d]) <= 0).mean())}
                                      for d in DETECTORS if d != REFERENCE},
           "fusion": {n: {k: {"point": p_fu[n][k], **ci(r_fu[n][k])} for k in p_fu[n]} for n in FORMS},
           "fusion_paired_minus_multiplicative": {
               n: {k: {"point": p_fu[n][k] - p_fu[FUSION_REF][k], **ci(r_fu[n][k] - r_fu[FUSION_REF][k])}
                   for k in p_fu[n]} for n in FORMS if n != FUSION_REF},
           "_meta": {"resamples": args.resamples, "bootstrap_seed": args.seed, "datasets": seeds,
                     "unit": "two-stage cluster bootstrap as T2.2; metric averaged over datasets per replicate"}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bootstrap_extra.json").write_text(json.dumps(
        {"provenance": provenance("evaluation/bootstrap_extra.py", {"bootstrap": args.seed, "datasets": seeds}), **out},
        indent=1), encoding="utf-8")
    record("stats_extra", out, script="evaluation/bootstrap_extra.py", seeds={"bootstrap": args.seed, "datasets": seeds})
    print("AP:", {d: round(v["point"], 3) for d, v in out["ap"].items()})
    for d, v in out["ap_paired_hybrid_minus"].items():
        print(f"  AP hybrid - {d:16s} {v['point']:+.3f} [{v['ci_lo']:+.3f}, {v['ci_hi']:+.3f}]")
    for n, v in out["fusion_paired_minus_multiplicative"].items():
        print(f"  {n:10s} - multiplicative: " + "  ".join(
            f"{k} {x['point']:+.3f} [{x['ci_lo']:+.3f}, {x['ci_hi']:+.3f}]" for k, x in v.items()))


if __name__ == "__main__":
    main()
