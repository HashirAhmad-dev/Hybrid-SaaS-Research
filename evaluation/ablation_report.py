"""
ablation_report.py
==================
Builds the T2.1 ablation table (CSV + LaTeX) and figure FROM THE MANIFEST ONLY
(keys ablation.ds<s>.*), so every cell traces to a recorded run.

Cells are mean ± sample sd across the independently generated datasets
(evaluation/config/seeds.json). Cluster-bootstrap intervals are added by T2.2.

    python -m evaluation.ablation_report
Outputs: results/ablation/ablation_table.csv, results/ablation/ablation_table.tex,
         results/ablation/ablation_auc_f1.pdf (+ .svg)
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

import numpy as np

from evaluation.ablation import DETECTORS
from evaluation.common import THREAT_CLASSES
from evaluation.multiseed import seeds_from_config
from tools.manifest import PROJECT_ROOT, load

OUT = PROJECT_ROOT / "results" / "ablation"

LABELS = {
    "ewma": "EWMA (rate only)", "zscore": "Per-user z-score", "lstm": "LSTM memory bank",
    "lstm_nextstep": "LSTM next-step error", "iforest": "Isolation Forest",
    "lof": "LOF (k on val)", "hybrid_weighted": "Hybrid, weighted mean",
    "hybrid_max": "Hybrid, max", "hybrid_rankavg": "Hybrid, rank average",
}
COLUMNS = [
    ("auc", "AUC"), ("average_precision", "AP"),
    ("recall_at_fpr01_testcurve", "R@1%FPR"), ("recall_at_fpr05_testcurve", "R@5%FPR"),
    ("valf1_f1", "F1 (val thr.)"), ("valf1_fpr", "FPR (val thr.)"),
    ("benign_burst_flag_rate", "Burst flag rate"),
    *[(f"per_class.{c}.auc", f"AUC {c}") for c in THREAT_CLASSES],
    *[(f"per_class.{c}.recall", f"Recall {c}") for c in THREAT_CLASSES],
]


def collect(seeds: List[int]) -> Dict[str, Dict[str, np.ndarray]]:
    e = load()["entries"]
    out: Dict[str, Dict[str, np.ndarray]] = {}
    for d in DETECTORS:
        out[d] = {}
        for key, _ in COLUMNS:
            vals = []
            for s in seeds:
                k = f"ablation.ds{s}.{d}.{key}"
                vals.append(float(e[k]["value"]) if k in e else np.nan)
            out[d][key] = np.array(vals)
    return out


def fmt(v: np.ndarray, pct: bool = False) -> str:
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return "n/a"
    m, sd = v.mean(), (v.std(ddof=1) if len(v) > 1 else 0.0)
    return f"{m:.3f} ± {sd:.3f}"


def main() -> None:
    seeds = seeds_from_config()
    data = collect(seeds)
    OUT.mkdir(parents=True, exist_ok=True)

    with open(OUT / "ablation_table.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["detector", *[f"{lab} mean" for _, lab in COLUMNS],
                    *[f"{lab} sd" for _, lab in COLUMNS], "n_datasets"])
        for d in DETECTORS:
            means = [np.nanmean(data[d][k]) for k, _ in COLUMNS]
            sds = [np.nanstd(data[d][k], ddof=1) for k, _ in COLUMNS]
            w.writerow([d, *[f"{x:.4f}" for x in means], *[f"{x:.4f}" for x in sds],
                        int(np.isfinite(data[d]["auc"]).sum())])

    from tools.manifest import record
    record("ablation.summary", {d: {k: {"mean": float(np.nanmean(data[d][k])),
                                         "sd": float(np.nanstd(data[d][k], ddof=1)),
                                         "n": int(np.isfinite(data[d][k]).sum())}
                                     for k, _ in COLUMNS} for d in DETECTORS},
           script="evaluation/ablation_report.py", seeds={"datasets": seeds})

    main_cols = COLUMNS[:7]
    lines = [r"\begin{table*}[t]", r"\centering", r"\small",
             r"\caption{Detector and fusion ablation on identical chronological splits. "
             r"Mean $\pm$ sample s.d.\ over %d independently generated datasets. "
             r"Thresholds for F1, FPR and burst flag rate are chosen on validation; "
             r"R@1\%%/5\%% FPR are read off the test ROC curve.}" % len(seeds),
             r"\label{tab:ablation}",
             r"\begin{tabular}{l" + "c" * len(main_cols) + "}", r"\hline",
             "Detector & " + " & ".join(lab.replace("%", r"\%") for _, lab in main_cols) + r" \\",
             r"\hline"]
    for d in DETECTORS:
        cells = [fmt(data[d][k]).replace("±", r"$\pm$") for k, _ in main_cols]
        lines.append(f"{LABELS[d]} & " + " & ".join(cells) + r" \\")
    lines += [r"\hline", r"\end{tabular}", r"\end{table*}"]
    (OUT / "ablation_table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6), sharey=True)
    order = list(DETECTORS)
    yy = np.arange(len(order))
    for ax, (key, title) in zip(axes, (("auc", "Test AUC"), ("valf1_f1", "Test F1 at validation threshold"))):
        for i, d in enumerate(order):
            v = data[d][key]
            ax.scatter(v, np.full(len(v), i), s=8, color="0.6", zorder=2)
            ax.errorbar(np.nanmean(v), i, xerr=np.nanstd(v, ddof=1), fmt="o", color="k",
                        ms=4, capsize=2, zorder=3)
        ax.set_title(title)
        ax.set_xlim(0, 1)
        ax.grid(axis="x", color="0.9")
    axes[0].set_yticks(yy, [LABELS[d] for d in order])
    axes[0].invert_yaxis()
    fig.text(0.99, 0.005, f"grey: one dataset each (n={len(seeds)}); black: mean ± s.d.",
             ha="right", fontsize=6)
    fig.tight_layout(rect=(0, 0.05, 1, 1))          # F8: keep the note clear of the tick labels
    for ext in ("pdf", "svg"):
        fig.savefig(OUT / f"ablation_auc_f1.{ext}")
    print(f"  -> {OUT / 'ablation_table.csv'}\n  -> {OUT / 'ablation_table.tex'}\n"
          f"  -> {OUT / 'ablation_auc_f1.pdf'}")


if __name__ == "__main__":
    main()
