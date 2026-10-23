"""
operating_points.py
===================
Paper-v2 task T2.7: every operating point of the anomaly engine in ONE labelled
table, so no threshold appears in the paper without its name and its selection
rule. All settings are chosen on validation; numbers are test, mean ± sample sd
over the 10 independently generated datasets.

  F1-optimal flag        alpha, tau maximise validation F1 of A_hybrid >= tau
  insider-oriented flag  alpha, tau maximise validation malicious-insider recall
                         subject to validation FPR <= 5 percent
  enforcement, shipped   SBRS beta 2.5, ALERT 1.22 / BLOCK 1.84 (calibrated once on
                         dataset 42's validation split), ALERT or BLOCK counts as a flag
  enforcement, per-dataset  beta and bands re-derived on each dataset's own validation split
  BLOCK only, shipped    the auto-block band alone
  hybrid OR drift (CUSUM) T2.4: F1-optimal flag combined with the drift detector
                         (only if T2.4 has run)

    python -m evaluation.operating_points
Outputs: results/operating_points/operating_points.{csv,tex}, manifest keys oppoints.*
"""
from __future__ import annotations

import csv

import numpy as np
import pandas as pd

from evaluation.multiseed import RUNS, seeds_from_config
from tools.manifest import PROJECT_ROOT, load, record

OUT = PROJECT_ROOT / "results" / "operating_points"
METRICS = ("recall", "fpr", "precision", "f1", "malicious_recall", "benign_burst_flag_rate")


def from_scored(s: int, col: str, positive_values) -> dict:
    d = pd.read_csv(RUNS / f"data_seed_{s}" / "run" / "scored_all_splits.csv",
                    usecols=["split", "is_true_threat", "threat_class", "is_benign_burst", col])
    t = d[d.split == "test"]
    y = t.is_true_threat.to_numpy(bool)
    f = t[col].isin(positive_values).to_numpy()
    tp, fp, fn = int((f & y).sum()), int((f & ~y).sum()), int((~f & y).sum())
    return {"recall": tp / (tp + fn), "fpr": float(f[~y].mean()),
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "f1": 2 * tp / (2 * tp + fp + fn) if tp else 0.0,
            "malicious_recall": float(f[(t.threat_class == "malicious_insider").to_numpy()].mean()),
            "benign_burst_flag_rate": float(f[t.is_benign_burst.to_numpy(bool)].mean())}


def main() -> None:
    seeds = seeds_from_config()
    e = load()["entries"]
    g = lambda k: e[k]["value"] if k in e else np.nan
    points = {}
    for s in seeds:
        a = f"anomaly.ds{s}"
        sb = f"sbrs.ds{s}.test"
        pts = {
            "f1_optimal_flag": {
                "recall": g(f"{a}.test_flag_level.hybrid.recall"), "fpr": g(f"{a}.test_flag_level.hybrid.fpr"),
                "precision": g(f"{a}.test_flag_level.hybrid.precision"), "f1": g(f"{a}.test_flag_level.hybrid.f1"),
                "malicious_recall": g(f"{a}.per_class_recall.malicious_insider.hybrid_recall"),
                "benign_burst_flag_rate": g(f"{a}.benign_burst.hybrid_flag_rate"),
                "alpha": g(f"{a}.tuning.alpha"), "tau": g(f"{a}.tuning.tau_hybrid")},
            "insider_oriented_flag": {
                **{k: g(f"{a}.test_insider_oriented_operating_point.{k}") for k in ("recall", "fpr", "precision", "f1")},
                "malicious_recall": g(f"{a}.test_insider_oriented_operating_point.malicious_insider_recall"),
                "benign_burst_flag_rate": g(f"{a}.test_insider_oriented_operating_point.benign_burst_flag_rate"),
                "alpha": g(f"{a}.test_insider_oriented_operating_point.alpha"),
                "tau": g(f"{a}.test_insider_oriented_operating_point.tau")},
            "enforcement_shipped_alert_or_block": from_scored(s, "hybrid_action", ("ALERT", "BLOCK")),
            "enforcement_shipped_block_only": from_scored(s, "hybrid_action", ("BLOCK",)),
            "enforcement_per_dataset_alert_or_block": {
                "recall": g(f"{sb}.new_calibrated.flagged.recall"), "fpr": g(f"{sb}.new_calibrated.flagged.fpr"),
                "precision": g(f"{sb}.new_calibrated.flagged.precision"), "f1": g(f"{sb}.new_calibrated.flagged_f1"),
                "malicious_recall": g(f"sbrs.ds{s}.test_per_class_recall_new.malicious_insider.alert_or_block_recall"),
                "benign_burst_flag_rate": g(f"{sb}.new_calibrated.benign_burst_alert_or_block_rate"),
                "beta": g(f"sbrs.ds{s}.beta.chosen"), "t_alert": g(f"sbrs.ds{s}.bands.t_alert"),
                "t_block": g(f"sbrs.ds{s}.bands.t_block")},
        }
        if f"drift.ds{s}.cusum.hybrid_or_drift.f1" in e:
            d = f"drift.ds{s}.cusum.hybrid_or_drift"
            pts["hybrid_or_cusum_drift"] = {
                **{k: g(f"{d}.{k}") for k in ("recall", "fpr", "precision", "f1")},
                "malicious_recall": np.nan,
                "malicious_episode_recall": g(f"{d}.malicious_episode_recall"),
                "benign_burst_flag_rate": g(f"{d}.benign_burst_flag_rate")}
        points[s] = pts
    names = list(points[seeds[0]])
    summ = {}
    for n in names:
        summ[n] = {}
        for k in sorted({k for s in seeds for k in points[s][n]}):
            v = np.array([points[s][n].get(k, np.nan) for s in seeds], float)
            summ[n][k] = {"mean": float(np.nanmean(v)) if np.isfinite(v).any() else np.nan,
                          "sd": float(np.nanstd(v, ddof=1)) if np.isfinite(v).sum() > 1 else np.nan}
    record("oppoints", {**{f"ds{s}": points[s] for s in seeds}, "summary": summ},
           script="evaluation/operating_points.py", seeds={"datasets": seeds})

    OUT.mkdir(parents=True, exist_ok=True)
    label = {"f1_optimal_flag": "F1-optimal flag (val)", "insider_oriented_flag": "Insider-oriented flag (val, FPR at most 5%)",
             "enforcement_shipped_alert_or_block": "SBRS ALERT or BLOCK, shipped bands",
             "enforcement_shipped_block_only": "SBRS BLOCK only, shipped bands",
             "enforcement_per_dataset_alert_or_block": "SBRS ALERT or BLOCK, per-dataset val bands",
             "hybrid_or_cusum_drift": "F1-optimal flag OR CUSUM drift alarm (malicious: episode recall)"}
    with open(OUT / "operating_points.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["operating_point", "selection", *[f"{m}_mean" for m in METRICS], *[f"{m}_sd" for m in METRICS]])
        for n in names:
            w.writerow([n, label[n], *[f"{summ[n].get(m, {}).get('mean', np.nan):.4f}" for m in METRICS],
                        *[f"{summ[n].get(m, {}).get('sd', np.nan):.4f}" for m in METRICS]])
    fmt = lambda d: "n/a" if not np.isfinite(d.get("mean", np.nan)) else f"{d['mean']:.3f} $\\pm$ {d['sd']:.3f}"
    lines = [r"\begin{table}[t]", r"\centering", r"\scriptsize",
             r"\caption{Operating points of the anomaly engine. Every setting is chosen on validation; "
             r"values are test, mean $\pm$ s.d.\ over %d generated datasets.}" % len(seeds),
             r"\label{tab:oppoints}", r"\begin{tabular}{lcccc}", r"\hline",
             r"Operating point & Recall & FPR & F1 & Malicious recall \\", r"\hline"]
    for n in names:
        mr = summ[n].get("malicious_recall", {})
        if not np.isfinite(mr.get("mean", np.nan)) and "malicious_episode_recall" in summ[n]:
            mr = summ[n]["malicious_episode_recall"]
        lines.append(f"{label[n].replace('%', chr(92) + '%')} & {fmt(summ[n]['recall'])} & {fmt(summ[n]['fpr'])} & "
                     f"{fmt(summ[n]['f1'])} & {fmt(mr)} \\\\")
    lines += [r"\hline", r"\end{tabular}", r"\end{table}"]
    (OUT / "operating_points.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for n in names:
        print(f"{n:<42} R {summ[n]['recall']['mean']:.3f}  FPR {summ[n]['fpr']['mean']:.4f}  F1 {summ[n]['f1']['mean']:.3f}")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
