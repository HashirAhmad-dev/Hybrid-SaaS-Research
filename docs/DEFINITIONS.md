# DEFINITIONS.md

One definition for each quantity that appears with more than one value (task F3). The machine-readable version is `results/claims/definitions.json`. `python -m tools.check_numbers results/claims` checks it: a line in a paper-facing file (`docs/FIXES_SUMMARY.md`, `results/negative_results.md`, `paper_inputs/*.md`, `README.md`) that quotes a variant value without naming the variant fails.

## Two threshold rules for the unsupervised detectors

Two scripts score the same 10 datasets with the same trained models but choose the flag threshold differently, so their flag-level numbers differ slightly.

| Rule | Where | How the threshold is chosen | Used for |
|---|---|---|---|
| **Comparison rule (canonical)** | `evaluation/ablation.py` (T2.1) | For each detector separately, the threshold that maximises F1 over all distinct validation scores. Rows: active hours with at least 23 earlier hours. | Every comparison between detectors, the bootstrap intervals (T2.2), the supervised comparison (D-028). This is what "hybrid F1" means without a qualifier. |
| Deployed rule | `evaluation/train_and_evaluate.py` (T1.4), reused by `evaluation/drift_detector.py` (T2.4) | alpha and tau tuned jointly on validation over a grid (alpha step 0.05, tau step 0.01); EWMA tau on a 0.25 grid. | The engine as shipped (`backend/config/final_config.json`), the T1.4 multi-seed table, and the CUSUM add-on, which is combined with the deployed hybrid flags. Always written "at the deployed threshold". |

| Quantity | Comparison rule (canonical) | Deployed rule |
|---|---|---|
| Hybrid flag F1, 10-dataset mean | 0.629 (`ablation.summary.hybrid_weighted.valf1_f1.mean`) | 0.635 (`anomaly.multiseed.f1_hybrid.mean`) |
| Isolation Forest flag F1 | 0.626 (`ablation.summary.iforest.valf1_f1.mean`) | 0.622 (`anomaly.multiseed.f1_if_only.mean`) |
| Hybrid malicious-insider episode recall | 0.117 (`supervised.summary.hybrid_weighted_t21.malicious_insider_episode_recall.mean`, from the T2.1 keys) | 0.133 (`anomaly.multiseed.episode_recall_malicious_insider.mean`, also `drift.summary.cusum.hybrid_only.malicious_episode_recall.mean`) |
| EWMA flag F1 | 0.111 (`ablation.summary.ewma.valf1_f1.mean`) | 0.106 (`anomaly.multiseed.f1_ewma_tuned.mean`) |
| EWMA benign-burst flag rate | 61.3 percent (`ablation.summary.ewma.benign_burst_flag_rate.mean`) | 66.8 percent (`anomaly.multiseed.benign_burst_flag_rate_ewma.mean`) |

The CUSUM result (0.133 to 0.567) is stated at the deployed threshold because the drift detector is OR-combined with the deployed hybrid flags.

## Two threshold rules for the supervised probes

| Rule | Where | How the threshold is chosen | Meaning |
|---|---|---|---|
| **Labelled-validation rule (canonical for D-028)** | `evaluation/supervised_multiseed.py`, `evaluation/cert_rich.py` | Maximise F1 on validation hours, using validation labels (4,001 validation-score quantiles searched). | The best a supervised layer can do when labels exist for both training and threshold setting. "Boosting F1 0.785" and "slow-insider episode recall 0.900" use this rule. |
| Label-free budget rule | `evaluation/label_curve.py` (D-029) | The 99th (1 percent budget) or 95th (5 percent budget) percentile of the model's scores on all validation hours. No validation label is used. | What a deployment with only k confirmed incidents can set. Always written with its budget. |

| Quantity (boosting, all TRAIN labels) | Labelled-validation rule | 5 percent budget | 1 percent budget |
|---|---|---|---|
| Flag F1 | 0.785 | 0.697 | 0.456 |
| Malicious-insider episode recall | 0.900 | 1.000 | 0.000 |

## "Incident" in the label curve

See section "Label curve" in `docs/DECISIONS.md` (D-029) and the F2 entry below it: an incident is one attack episode (a run of consecutive attack hours on one user); all hours of a chosen episode become positive labels.
