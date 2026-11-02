"""
build_paper_inputs.py
=====================
Paper-v2 task T4.4: assembles paper_inputs/ from finished results. Nothing here
computes a new number; tables are formatted from results/manifest.json or copied
from the results folders, and figures are copied from their generating scripts'
outputs.

    python -m tools.build_paper_inputs
Layout:
    paper_inputs/tables/*.tex     LaTeX tables (booktabs-free, plain tabular)
    paper_inputs/csv/*.csv        the same data as CSV
    paper_inputs/figures/*.pdf|svg vector figures
    paper_inputs/numbers.json     every claimed number with its source (tools/claim_evidence.py)
    paper_inputs/README.md        what each file is and which script made it
"""
from __future__ import annotations

import csv
import shutil

import numpy as np

from evaluation.ablation_report import LABELS
from tools.manifest import PROJECT_ROOT, load

R = PROJECT_ROOT / "results"
P = PROJECT_ROOT / "paper_inputs"


def f3(x) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.3f}"


def table(name: str, caption: str, label: str, header, rows) -> None:
    (P / "tables").mkdir(parents=True, exist_ok=True)
    (P / "csv").mkdir(parents=True, exist_ok=True)
    lines = [r"\begin{table}[t]", r"\centering", r"\scriptsize", rf"\caption{{{caption}}}", rf"\label{{{label}}}",
             r"\begin{tabular}{l" + "c" * (len(header) - 1) + "}", r"\hline",
             " & ".join(header) + r" \\", r"\hline"]
    lines += [" & ".join(str(c).replace("%", r"\%") for c in r) + r" \\" for r in rows]
    lines += [r"\hline", r"\end{tabular}", r"\end{table}"]
    (P / "tables" / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(P / "csv" / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    e = load()["entries"]
    g = lambda k: e[k]["value"] if k in e else None
    P.mkdir(exist_ok=True)
    readme = ["# paper_inputs", "", "Built by `python -m tools.build_paper_inputs`. Every number is in `numbers.json` with its "
              "manifest key, script and run; `docs/CLAIM_EVIDENCE.md` is the readable version.", "", "| File | Content | Made by |",
              "|---|---|---|"]

    # copied tables / csv / figures
    copies = [
        (R / "ablation" / "ablation_table.tex", "tables/ablation.tex", "Detector and fusion ablation, 10 datasets", "evaluation/ablation_report.py"),
        (R / "ablation" / "ablation_table.csv", "csv/ablation.csv", "same, CSV", "evaluation/ablation_report.py"),
        (R / "operating_points" / "operating_points.tex", "tables/operating_points.tex", "Labelled operating points", "evaluation/operating_points.py"),
        (R / "operating_points" / "operating_points.csv", "csv/operating_points.csv", "same, CSV", "evaluation/operating_points.py"),
        (R / "multiseed_summary.csv", "csv/multiseed_summary.csv", "10-dataset mean, sd, min, max", "evaluation/multiseed.py"),
        (R / "stats" / "bootstrap_intervals.csv", "csv/bootstrap_intervals.csv", "Cluster-bootstrap 95% intervals", "evaluation/bootstrap_stats.py"),
        (R / "stats" / "paired_vs_hybrid.csv", "csv/paired_vs_hybrid.csv", "Paired differences vs hybrid", "evaluation/bootstrap_stats.py"),
        (R / "stats" / "confusion_hybrid_by_class.csv", "csv/confusion_hybrid_by_class.csv", "Hybrid confusion by class", "evaluation/bootstrap_stats.py"),
        (R / "sweep" / "sweep_summary.csv", "csv/sweep_summary.csv", "Difficulty sweep", "evaluation/difficulty_sweep.py"),
        (R / "drift" / "drift_summary.csv", "csv/drift_summary.csv", "Drift detector summary", "evaluation/drift_detector.py"),
        (R / "sbrs_fusion" / "fusion_summary.csv", "csv/fusion_summary.csv", "SBRS fusion forms", "evaluation/sbrs_fusion.py"),
        (R / "sbrs_fusion" / "fusion_corners_seed42.csv", "csv/fusion_corners.csv", "Action of each form at (S, A) corners", "evaluation/sbrs_fusion.py"),
        (R / "pii_v2" / "cascade_summary.csv", "csv/pii_cascade_summary.csv", "PII cascade per OCR x VLM", "evaluation/pii_v2_score.py"),
        (R / "latency" / "tier_latency.json", "csv/tier_latency.json", "Two-tier latency", "evaluation/tier_latency.py"),
        (R / "ablation" / "ablation_auc_f1.pdf", "figures/ablation_auc_f1.pdf", "Ablation figure", "evaluation/ablation_report.py"),
        (R / "ablation" / "ablation_auc_f1.svg", "figures/ablation_auc_f1.svg", "same, SVG", "evaluation/ablation_report.py"),
        (R / "sweep" / "detection_vs_intensity.pdf", "figures/detection_vs_intensity.pdf", "Detection vs attack intensity", "evaluation/difficulty_sweep.py"),
        (R / "sweep" / "detection_vs_intensity.svg", "figures/detection_vs_intensity.svg", "same, SVG", "evaluation/difficulty_sweep.py"),
        (PROJECT_ROOT / "figures" / "architecture.pdf", "figures/architecture.pdf", "Figure 1, architecture (source figures/architecture.dot)", "tools/render_figures.py"),
        (PROJECT_ROOT / "figures" / "architecture.svg", "figures/architecture.svg", "same, SVG", "tools/render_figures.py"),
    ]
    for pdf in sorted((R / "pii_v2").glob("pareto_*.pdf")) + sorted((R / "pii_v2").glob("pareto_*.svg")):
        copies.append((pdf, f"figures/{pdf.name}", "PII cascade cost vs F1", "evaluation/pii_v2_plots.py"))
    for src, dst, what, by in copies:
        if not src.exists():
            readme.append(f"| `{dst}` | MISSING ({what}) | `{by}` |")
            continue
        (P / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, P / dst)
        readme.append(f"| `{dst}` | {what} | `{by}` |")

    # formatted tables from the manifest
    def ms(k):
        m, s = g(k + ".mean"), g(k + ".sd")
        return "n/a" if m is None else f"{m:.3f} $\\pm$ {s:.3f}"
    forms = ("multiplicative", "additive", "max", "gated", "logistic")
    table("sbrs_fusion", "Risk-fusion forms at the same benign budget (ALERT at benign validation p95, BLOCK at p99.5), "
          "mean $\\pm$ s.d.\\ over 10 datasets. Low-S/high-A: threats with S below 30 and A at or above the hybrid threshold, summed.",
          "tab:fusion", ["Form", "Threat recall", "Benign alert rate", "F1", "Malicious recall", "Low-S/high-A escalated"],
          [[f, ms(f"fusion.summary.{f}.threat_recall"), ms(f"fusion.summary.{f}.benign_alert_or_block_rate"),
            ms(f"fusion.summary.{f}.f1"), ms(f"fusion.summary.{f}.per_class_recall.malicious_insider"),
            f"{int(g(f'fusion.summary.{f}.low_S_high_A_escalated.sum'))}/{int(g(f'fusion.summary.{f}.low_S_high_A_threats.sum'))}"]
           for f in forms])
    readme.append("| `tables/sbrs_fusion.tex` | Fusion forms (from manifest `fusion.summary.*`) | `tools/build_paper_inputs.py` |")

    d = "drift.summary."
    table("drift", "Slow-drift detectors beside the hybrid, mean $\\pm$ s.d.\\ over 10 datasets. "
          "Episode recall is the share of malicious-insider episodes with at least one alarm.",
          "tab:drift", ["System", "Malicious episode recall", "Median time to detect (h)", "FPR", "F1", "Burst alarm rate"],
          [["Hybrid only", ms(d + "cusum.hybrid_only.malicious_episode_recall"), "n/a", ms(d + "cusum.hybrid_only.fpr"),
            ms(d + "cusum.hybrid_only.f1"), "n/a"],
           ["Hybrid OR CUSUM", ms(d + "cusum.hybrid_or_drift.malicious_episode_recall"),
            ms(d + "cusum.per_class.malicious_insider.ttd_hours_median"), ms(d + "cusum.hybrid_or_drift.fpr"),
            ms(d + "cusum.hybrid_or_drift.f1"), ms(d + "cusum.test_false_alarm_rate_benign_bursts")],
           ["Hybrid OR Page-Hinkley", ms(d + "ph.hybrid_or_drift.malicious_episode_recall"),
            ms(d + "ph.per_class.malicious_insider.ttd_hours_median"), ms(d + "ph.hybrid_or_drift.fpr"),
            ms(d + "ph.hybrid_or_drift.f1"), ms(d + "ph.test_false_alarm_rate_benign_bursts")]])
    readme.append("| `tables/drift.tex` | Drift detectors (from `drift.summary.*`) | `tools/build_paper_inputs.py` |")

    s = "stats."
    rows = []
    for det in ("ewma", "zscore", "lstm", "lstm_nextstep", "iforest", "lof", "hybrid_max", "hybrid_rankavg"):
        rows.append([LABELS[det], f"{g(s + det + '.paired_vs_hybrid.f1.hybrid_minus_this'):+.3f} [{g(s + det + '.paired_vs_hybrid.f1.ci_lo'):+.3f}, {g(s + det + '.paired_vs_hybrid.f1.ci_hi'):+.3f}]",
                     f"{g(s + det + '.paired_vs_hybrid.auc.hybrid_minus_this'):+.3f} [{g(s + det + '.paired_vs_hybrid.auc.ci_lo'):+.3f}, {g(s + det + '.paired_vs_hybrid.auc.ci_hi'):+.3f}]"])
    table("paired_bootstrap", "Weighted hybrid minus each alternative, mean over 10 datasets, 95\\% two-stage cluster-bootstrap "
          "interval (users, then attack episodes; 10,000 resamples). Positive favours the hybrid.",
          "tab:paired", ["Alternative", "$\\Delta$F1", "$\\Delta$AUC"], rows)
    readme.append("| `tables/paired_bootstrap.tex` | Paired hybrid-vs-alternative intervals (from `stats.*`) | `tools/build_paper_inputs.py` |")

    lt = "latency."
    if g(lt + "tier1.warm_client_ms.p50") is not None:
        table("latency", "Two-tier latency measured inside the running proxy (CPU laptop).", "tab:latency",
              ["Tier", "n", "p50 (ms)", "p95 (ms)", "p99 (ms)"],
              [["Tier 1 inline, warm", int(g(lt + "tier1.warm_client_ms.n")), f"{g(lt + 'tier1.warm_client_ms.p50'):.1f}",
                f"{g(lt + 'tier1.warm_client_ms.p95'):.1f}", f"{g(lt + 'tier1.warm_client_ms.p99'):.1f}"],
               ["Tier 1, first request after start", int(g(lt + "tier1.cold_client_ms.n")), f"{g(lt + 'tier1.cold_client_ms.p50'):.0f}",
                f"{g(lt + 'tier1.cold_client_ms.p95'):.0f}", f"{g(lt + 'tier1.cold_client_ms.p99'):.0f}"],
               ["Tier 2 hold (EasyOCR)", int(g(lt + "tier2.hold_ms.n")), f"{g(lt + 'tier2.hold_ms.p50'):.0f}",
                f"{g(lt + 'tier2.hold_ms.p95'):.0f}", f"{g(lt + 'tier2.hold_ms.p99'):.0f}"]])
        readme.append("| `tables/latency.tex` | Two-tier latency (from `latency.*`) | `tools/build_paper_inputs.py` |")

    # PII image paths, eval documents; FUNSD gold is partial (D-021) so its precision is a lower bound
    def pf(k):
        return f3(g(k)) if g(k) is not None else "n/a"
    pii_rows = []
    for name, base in [("EasyOCR + Presidio+", "ocr.easyocr_cpu.presidio_plus.all.f1"),
                       ("PaddleOCR + Presidio+", "ocr.paddleocr_cpu.presidio_plus.all.f1"),
                       ("Qwen2.5-VL-3B (local)", "vlm.qwen2-5-vl-3b-instruct.all.f1"),
                       ("gemma-3-4B (local)", "vlm.gemma-3-4b-it.all.f1"),
                       ("Qwen2.5-VL-7B (local)", "vlm.qwen2-5-vl-7b-instruct.all.f1"),
                       ("EasyOCR $\\rightarrow$ gemma, calib $\\tau$", "cascade.easyocr_cpu.gemma-3-4b-it.eval_at_calib_tau.f1"),
                       ("EasyOCR $\\rightarrow$ gemma, $\\tau=0.85$", "cascade.easyocr_cpu.gemma-3-4b-it.eval_at_tau_085.f1")]:
        hard = base.replace(".all.f1", ".by_difficulty.hard.f1") if ".all.f1" in base else None
        row = [name, pf(f"pii2.v1.{base}"), pf(f"pii2.v2.{base}"), pf(f"pii2.v2.{hard}") if hard else "n/a",
               pf(f"pii2.funsd.{base}")]
        if any(c != "n/a" for c in row[1:]):
            pii_rows.append(row)
    table("pii_images", "Entity F1 on image documents (eval split). v1: the original 80 images; v2: 240 new images at "
          "three difficulty levels; FUNSD: 199 real scanned forms with a derived partial gold list, so its precision "
          "and F1 are lower bounds. All models run locally on one laptop.", "tab:pii",
          ["Method", "v1", "v2", "v2 hard", "FUNSD"], pii_rows)
    readme.append("| `tables/pii_images.tex` | PII image-path F1 per corpus (from `pii2.*`) | `tools/build_paper_inputs.py` |")

    # CERT r4.2: a second synthetic benchmark, never pooled with our datasets (D-024)
    cert_rows = [[name, pf(f"cert.ablation.{d}.auc"), f"{g(f'cert.ablation.{d}.average_precision'):.4f}",
                  pf(f"cert.ablation.{d}.valf1_f1"), pf(f"cert.ablation.{d}.valf1_precision"),
                  pf(f"cert.ablation.{d}.valf1_recall"), pf(f"cert.ablation.{d}.valf1_fpr")]
                 for name, d in [("EWMA", "ewma"), ("z-score", "zscore"), ("LOF", "lof"), ("LSTM memory bank", "lstm"),
                                 ("LSTM next-step", "lstm_nextstep"), ("Isolation Forest", "iforest"),
                                 ("Hybrid weighted", "hybrid_weighted"), ("Hybrid max", "hybrid_max"),
                                 ("Hybrid rank average", "hybrid_rankavg")]
                 if g(f"cert.ablation.{d}.auc") is not None]
    if cert_rows:
        table("cert", "Detectors on CERT r4.2, a second synthetic benchmark mapped onto our six features. Test split: "
              "65,249 active user-hours, 330 positive hours, 7 insiders. Each F1 threshold was chosen on validation. "
              "Not pooled with our datasets.", "tab:cert",
              ["Detector", "AUC", "AP", "F1", "Precision", "Recall", "FPR"], cert_rows)
        readme.append("| `tables/cert.tex` | CERT r4.2 detector results (from `cert.*`) | `tools/build_paper_inputs.py` |")

    # supervised probes vs unsupervised detectors on our 10 datasets (D-028)
    ms = lambda k: f"{f3(g(k + '.mean'))} $\\pm$ {f3(g(k + '.sd'))}" if g(k + ".mean") is not None else "n/a"
    sup_rows = [[name, ms(f"supervised.summary.{d}.auc"), ms(f"supervised.summary.{d}.f1"),
                 f3(g(f"supervised.summary.{d}.per_class.malicious_insider.auc.mean")),
                 f3(g(f"supervised.summary.{d}.per_class.malicious_insider.episode_recall.mean"))]
                for name, d in [("Isolation Forest (refit)", "iforest"), ("Per-user z-score (refit)", "zscore"),
                                ("Logistic probe (labels)", "probe_logistic"),
                                ("Gradient boosting probe (labels)", "probe_boosting")]]
    if g("supervised.summary.probe_boosting.auc.mean") is not None:
        sup_rows.append(["Weighted hybrid (T2.1)", ms("supervised.summary.hybrid_weighted_t21.auc"),
                         ms("supervised.summary.hybrid_weighted_t21.f1"),
                         f3(g("supervised.summary.hybrid_weighted_t21.malicious_insider_auc.mean")),
                         f3(g("supervised.summary.hybrid_weighted_t21.malicious_insider_episode_recall.mean"))])
        table("supervised", "Unsupervised detectors and supervised probes trained on labelled TRAIN incidents, "
              "same six features, 10 generated datasets (mean $\\pm$ sd). Thresholds chosen on validation.",
              "tab:supervised", ["Detector", "AUC", "F1", "Malicious AUC", "Malicious episode recall"], sup_rows)
        readme.append("| `tables/supervised.tex` | Supervised probes vs unsupervised detectors (from `supervised.summary.*`) | `tools/build_paper_inputs.py` |")

    # label learning curve at a 5 percent label-free alert budget (D-029)
    if g("labelcurve_b5.summary.k0_iforest.auc.mean") is not None:
        lc = lambda c, k: f3(g(f"labelcurve_b5.summary.{c}.{k}.mean"))
        lc_rows = [["0 (Isolation Forest)", lc("k0_iforest", "auc"), lc("k0_iforest", "f1"),
                    lc("k0_iforest", "malicious_episode_recall"), "", "", ""]]
        for k in ("1", "3", "5", "10", "20", "50", "all"):
            lc_rows.append([k, lc(f"k{k}_logistic", "auc"), lc(f"k{k}_logistic", "f1"),
                            lc(f"k{k}_logistic", "malicious_episode_recall"),
                            lc(f"k{k}_boosting", "auc"), lc(f"k{k}_boosting", "f1"),
                            lc(f"k{k}_boosting", "malicious_episode_recall")])
        table("label_curve", "Supervised layer trained on k labelled TRAIN incidents (of 143); other TRAIN hours "
              "treated as benign. Alert threshold: 95th percentile of validation scores (no labels). Mean over 5 draws "
              "and 10 datasets. Columns: logistic AUC, F1, malicious episode recall; boosting AUC, F1, malicious "
              "episode recall.", "tab:labelcurve",
              ["k", "LR AUC", "LR F1", "LR mal. ep. rec.", "GB AUC", "GB F1", "GB mal. ep. rec."], lc_rows)
        readme.append("| `tables/label_curve.tex` | Label learning curve, 5 percent alert budget (from `labelcurve_b5.summary.*`) | `tools/build_paper_inputs.py` |")

    # the may / must-not claim lists live in docs/FIXES_SUMMARY.md section 5; copy them, never edit the copy
    fs = (PROJECT_ROOT / "docs" / "FIXES_SUMMARY.md").read_text(encoding="utf-8")
    sec = fs[fs.index("## 5. Claims the paper may make"):fs.index("## 6.")].rstrip()
    (P / "claims_may_must_not.md").write_text(
        "<!-- Copied from docs/FIXES_SUMMARY.md section 5 by tools/build_paper_inputs.py. Edit the source. -->\n\n"
        + sec + "\n", encoding="utf-8")
    readme.append("| `claims_may_must_not.md` | Claims the paper may and must not make, with evidence files | `tools/build_paper_inputs.py` |")
    pc = fs[fs.index("### Primary claim"):fs.index("## 2. Task table")].rstrip()
    (P / "primary_claim.md").write_text(
        "<!-- Copied from docs/FIXES_SUMMARY.md section 1 by tools/build_paper_inputs.py. Edit the source. -->\n\n"
        + pc + "\n", encoding="utf-8")
    readme.append("| `primary_claim.md` | The paper's primary claim, its evidence chain and the limits to state with it | `tools/build_paper_inputs.py` |")

    from tools.claim_evidence import main as ce
    ce()
    readme.append("| `numbers.json` | Every claimed number with key, script, run, git hash | `tools/claim_evidence.py` |")
    (P / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(f"  -> {P}")


if __name__ == "__main__":
    main()
