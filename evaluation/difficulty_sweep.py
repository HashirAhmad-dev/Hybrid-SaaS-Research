"""
difficulty_sweep.py
===================
Paper-v2 task T2.3: how detection degrades as attacks get quieter and as benign
behaviour starts to look like attacks.

Grid: attack intensity in INTENSITIES x benign overlap in OVERLAPS, for the data
seeds in SWEEP_SEEDS. Each cell regenerates the dataset with
`generate_sessions --intensity I --benign-overlap O`, retrains the engine, and
runs the T2.1 ablation (all detectors, validation-chosen thresholds). At
intensity 1.0 and overlap 0.0 the generator reproduces the original dataset
byte for byte (checked by `tests/test_generator_defaults.py`), so that cell
reuses results/runs/data_seed_<s>/.

Episode positions do not depend on the knobs (all extra randomness comes from a
separate stream), so cells differ only in how loud the same episodes are: a
paired design.

    python -m evaluation.difficulty_sweep          # runs missing cells, then plots
    python -m evaluation.difficulty_sweep --plot-only
Outputs: results/runs/sweep/i<I>_o<O>/ds<s>/, manifest keys sweep.i<I>.o<O>.ds<s>.*,
         results/sweep/sweep_summary.csv, results/sweep/detection_vs_intensity.{pdf,svg}
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from evaluation.ablation import DETECTORS, compute_scores, evaluate
from evaluation.ablation_report import LABELS
from evaluation.multiseed import RUNS, run
from tools.manifest import PROJECT_ROOT, load, provenance, record

INTENSITIES = (0.25, 0.5, 0.75, 1.0, 1.5)
OVERLAPS = (0.0, 0.5)
SWEEP_SEEDS = (42, 7, 2024)
OUT = PROJECT_ROOT / "results" / "sweep"
PLOT_DETECTORS = ("ewma", "zscore", "lstm", "iforest", "lof", "hybrid_weighted", "hybrid_max")


def key_prefix(i: float, o: float, s: int) -> str:
    return f"sweep.i{str(i).replace('.', 'p')}.o{str(o).replace('.', 'p')}.ds{s}"


def cell_dir(i: float, o: float, s: int) -> Path:
    if i == 1.0 and o == 0.0:
        return RUNS / f"data_seed_{s}"
    return RUNS / "sweep" / f"i{i:g}_o{o:g}" / f"ds{s}"


def run_cell(i: float, o: float, s: int) -> None:
    base = cell_dir(i, o, s)
    pre = key_prefix(i, o, s)
    if f"{pre}.hybrid_weighted.auc" in load()["entries"]:
        return
    if not (i == 1.0 and o == 0.0):
        data, out = base / "data", base / "run"
        run(["-m", "evaluation.generate_sessions", "--seed", str(s), "--intensity", str(i),
             "--benign-overlap", str(o), "--out-dir", str(data)], base / "generate.log")
        run(["-m", "evaluation.train_and_evaluate", "--seed", str(s), "--data-dir", str(data),
             "--out-dir", str(out), "--manifest-prefix", f"{pre}.engine",
             "--latency-samples", "0"], base / "train.log")
    rows = compute_scores(base)
    res = evaluate(rows)
    (base / "ablation").mkdir(parents=True, exist_ok=True)
    rows.to_csv(base / "ablation" / "row_scores.csv", index=False)
    (base / "ablation" / "ablation_metrics.json").write_text(json.dumps(
        {"provenance": provenance("evaluation/difficulty_sweep.py",
                                  {"data_and_train": s, "intensity": i, "overlap": o}, "cpu"),
         "detectors": res}, indent=1, default=float), encoding="utf-8")
    record(pre, res, script="evaluation/difficulty_sweep.py",
           seeds={"data_and_train": s, "intensity": i, "overlap": o}, device="cpu")
    print(f"[I={i} O={o} seed {s}] hybrid AUC {res['hybrid_weighted']['auc']:.3f} "
          f"IF {res['iforest']['auc']:.3f} LSTM {res['lstm']['auc']:.3f}", flush=True)


def summarise_and_plot() -> None:
    e = load()["entries"]
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for o in OVERLAPS:
        for i in INTENSITIES:
            for d in DETECTORS:
                for metric in ("auc", "valf1_f1", "valf1_recall", "valf1_fpr",
                               "recall_at_fpr05_valthreshold", "fpr_realised_at_fpr05_valthreshold",
                               "per_class.malicious_insider.auc"):
                    v = [e.get(f"{key_prefix(i, o, s)}.{d}.{metric}", {}).get("value", np.nan)
                         for s in SWEEP_SEEDS]
                    v = np.array(v, dtype=float)
                    rows.append({"overlap": o, "intensity": i, "detector": d, "metric": metric,
                                 "mean": float(np.nanmean(v)), "sd": float(np.nanstd(v, ddof=1)),
                                 "n": int(np.isfinite(v).sum())})
    with open(OUT / "sweep_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    record("sweep.summary", {f"o{str(r['overlap']).replace('.', 'p')}.i{str(r['intensity']).replace('.', 'p')}"
                             f".{r['detector']}.{r['metric']}": {"mean": r["mean"], "sd": r["sd"], "n": r["n"]}
                             for r in rows},
           script="evaluation/difficulty_sweep.py", seeds={"datasets": list(SWEEP_SEEDS)})

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, axes = plt.subplots(len(OVERLAPS), 2, figsize=(7.0, 2.4 * len(OVERLAPS)), sharex=True)
    styles = dict(zip(PLOT_DETECTORS, ["o-", "s-", "^-", "v-", "D-", "x-", "+-"]))
    for r_i, o in enumerate(OVERLAPS):
        for c_i, (metric, title) in enumerate((("auc", "Test AUC"),
                                               ("recall_at_fpr05_valthreshold",
                                                "Recall, 5% val-FPR threshold"))):
            ax = axes[r_i, c_i]
            for d in PLOT_DETECTORS:
                pts = [next(x for x in rows if x["overlap"] == o and x["intensity"] == i
                            and x["detector"] == d and x["metric"] == metric) for i in INTENSITIES]
                ax.errorbar(INTENSITIES, [p["mean"] for p in pts], yerr=[p["sd"] for p in pts],
                            fmt=styles[d], ms=3, lw=1, capsize=2, label=LABELS[d])
            ax.set_title(f"{title} (overlap {o:g})")
            ax.set_ylim(0, 1.02)
            ax.grid(color="0.9")
            if r_i == len(OVERLAPS) - 1:
                ax.set_xlabel("attack intensity (1.0 = original dataset)")
    axes[0, 1].legend(fontsize=6, loc="lower right")
    fig.text(0.99, 0.003, f"mean ± s.d. over data seeds {', '.join(map(str, SWEEP_SEEDS))}",
             ha="right", fontsize=6)
    fig.tight_layout()
    for ext in ("pdf", "svg"):
        fig.savefig(OUT / f"detection_vs_intensity.{ext}")
    print(f"  -> {OUT}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot-only", action="store_true")
    args = ap.parse_args()
    if not args.plot_only:
        for o in OVERLAPS:
            for i in INTENSITIES:
                for s in SWEEP_SEEDS:
                    run_cell(i, o, s)
    summarise_and_plot()


if __name__ == "__main__":
    main()
