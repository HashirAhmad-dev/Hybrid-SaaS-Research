"""
pii_v2_plots.py
===============
T3.4(a): cost versus F1 Pareto curves of the OCR -> VLM cascade, one curve per
(OCR engine, VLM) pair, on the v2 EVAL documents (from results/pii_v2/pareto_v2_*.csv,
written by pii_v2_score.py). The CALIB-chosen tau of each pair is marked, plus
the router (if trained) and the design's tau = 0.85.

    python -m evaluation.pii_v2_plots
Outputs: results/pii_v2/pareto_v2.{pdf,svg}
"""
from __future__ import annotations

import csv
import json

from evaluation.pii_v2 import OUT


NAMES = {"easyocr": "EasyOCR", "paddleocr": "PaddleOCR",
         "gemma-3-4b-it": "gemma-3-4B", "qwen2-5-vl-3b-instruct": "Qwen2.5-VL-3B",
         "qwen2-5-vl-7b-instruct": "Qwen2.5-VL-7B"}


def pretty(pair: str) -> str:
    """'easyocr_cpu_gemma-3-4b-it' -> 'EasyOCR + gemma-3-4B'"""
    ocr, _, vlm = pair.partition("_cpu_")
    return f"{NAMES.get(ocr, ocr)} + {NAMES.get(vlm, vlm)}"


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "pdf.fonttype": 42, "svg.fonttype": "none"})
    metrics = json.loads((OUT / "pii_v2_metrics.json").read_text(encoding="utf-8"))["v2"]
    files = sorted(OUT.glob("pareto_v2_*.csv"))
    if not files:
        raise SystemExit("no pareto_v2_*.csv; run `python -m evaluation.pii_v2 score` after a VLM stage")
    fig, ax = plt.subplots(figsize=(3.4, 3.1))
    markers = "osD^v<>"
    for i, f in enumerate(files):
        pair = f.stem.removeprefix("pareto_v2_")
        rows = list(csv.DictReader(open(f, encoding="utf-8")))
        x = [float(r["seconds_per_image"]) for r in rows]
        y = [float(r["f1"]) for r in rows]
        ax.plot(x, y, "-", lw=0.8, label=pretty(pair))
        ocr, vlm = None, None
        for k, v in metrics.items():
            if k.startswith("cascade.") and k.replace("cascade.", "").replace(".", "_", 1) == pair:
                ax.plot(v["eval_seconds_per_image"], v["eval_at_calib_tau"]["f1"], markers[i % 7], ms=4,
                        color=ax.lines[-1].get_color())
                r = v.get("router", {})
                if "eval" in r:
                    ax.plot(r["eval_seconds_per_image"], r["eval"]["f1"], "*", ms=7, color=ax.lines[-1].get_color())
    ax.set_xlabel("mean seconds per image\n(OCR always, VLM when routed)")
    ax.set_ylabel("entity F1 (v2 eval images)")
    ax.grid(color="0.9")
    ax.legend(fontsize=6, loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=2, frameon=False)
    ax.set_title("Cascade cost vs accuracy over tau", fontsize=8)
    fig.text(0.01, 0.005, "marker: tau chosen on calib; star: router", fontsize=6)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    for ext in ("pdf", "svg"):
        fig.savefig(OUT / f"pareto_v2.{ext}")
    print(f"  -> {OUT / 'pareto_v2.pdf'}")


if __name__ == "__main__":
    main()
