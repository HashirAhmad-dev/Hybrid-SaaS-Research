# paper_inputs

Built by `python -m tools.build_paper_inputs`. Every number is in `numbers.json` with its manifest key, script and run; `docs/CLAIM_EVIDENCE.md` is the readable version.

| File | Content | Made by |
|---|---|---|
| `tables/ablation.tex` | Detector and fusion ablation, 10 datasets | `evaluation/ablation_report.py` |
| `csv/ablation.csv` | same, CSV | `evaluation/ablation_report.py` |
| `tables/operating_points.tex` | Labelled operating points | `evaluation/operating_points.py` |
| `csv/operating_points.csv` | same, CSV | `evaluation/operating_points.py` |
| `csv/multiseed_summary.csv` | 10-dataset mean, sd, min, max | `evaluation/multiseed.py` |
| `csv/bootstrap_intervals.csv` | Cluster-bootstrap 95% intervals | `evaluation/bootstrap_stats.py` |
| `csv/paired_vs_hybrid.csv` | Paired differences vs hybrid | `evaluation/bootstrap_stats.py` |
| `csv/confusion_hybrid_by_class.csv` | Hybrid confusion by class | `evaluation/bootstrap_stats.py` |
| `csv/sweep_summary.csv` | Difficulty sweep | `evaluation/difficulty_sweep.py` |
| `csv/drift_summary.csv` | Drift detector summary | `evaluation/drift_detector.py` |
| `csv/fusion_summary.csv` | SBRS fusion forms | `evaluation/sbrs_fusion.py` |
| `csv/fusion_corners.csv` | Action of each form at (S, A) corners | `evaluation/sbrs_fusion.py` |
| `csv/pii_cascade_summary.csv` | PII cascade per OCR x VLM | `evaluation/pii_v2_score.py` |
| `csv/tier_latency.json` | Two-tier latency | `evaluation/tier_latency.py` |
| `figures/ablation_auc_f1.pdf` | Ablation figure | `evaluation/ablation_report.py` |
| `figures/ablation_auc_f1.svg` | same, SVG | `evaluation/ablation_report.py` |
| `figures/detection_vs_intensity.pdf` | Detection vs attack intensity | `evaluation/difficulty_sweep.py` |
| `figures/detection_vs_intensity.svg` | same, SVG | `evaluation/difficulty_sweep.py` |
| `figures/architecture.pdf` | Figure 1, architecture (source figures/architecture.dot) | `tools/render_figures.py` |
| `figures/architecture.svg` | same, SVG | `tools/render_figures.py` |
| `tables/sbrs_fusion.tex` | Fusion forms (from manifest `fusion.summary.*`) | `tools/build_paper_inputs.py` |
| `tables/drift.tex` | Drift detectors (from `drift.summary.*`) | `tools/build_paper_inputs.py` |
| `tables/paired_bootstrap.tex` | Paired hybrid-vs-alternative intervals (from `stats.*`) | `tools/build_paper_inputs.py` |
| `tables/latency.tex` | Two-tier latency (from `latency.*`) | `tools/build_paper_inputs.py` |
| `numbers.json` | Every claimed number with key, script, run, git hash | `tools/claim_evidence.py` |
