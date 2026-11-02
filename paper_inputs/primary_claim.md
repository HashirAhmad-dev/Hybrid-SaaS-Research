<!-- Copied from docs/FIXES_SUMMARY.md section 1 by tools/build_paper_inputs.py. Edit the source. -->

### Primary claim (replaces "the hybrid LSTM plus Isolation Forest engine detects threats")

> Unsupervised anomaly detection, including our LSTM plus Isolation Forest hybrid, cannot tell unusual behaviour from malicious behaviour, and it misses almost all slow insider drift. The same six behavioural features, given to a supervised layer trained on analyst-confirmed incidents, separate them well, and about 10 to 20 confirmed incidents are enough. We therefore propose a two-stage design: unsupervised detection from the first day, then a supervised layer trained on confirmed alerts, with slow drift given its own alert budget.

Evidence, in the order the paper should present it:

| Step | Finding | Numbers | Evidence |
|---|---|---|---|
| 1 | The unsupervised hybrid is no better than its parts | hybrid F1 0.629 [0.564, 0.702]; hybrid minus Isolation Forest 0.003 [-0.013, 0.020]; slow-insider episode recall 0.117 | `results/claims/stats.claims`, `results/claims/supervised.claims` |
| 2 | The features carry the signal; anomaly scoring does not find it | supervised gradient boosting on the same features: AUC 0.951 ± 0.021, F1 0.785 ± 0.043, slow-insider episode recall 0.900, wins in 10 of 10 datasets; 25 of 27 episodes of users never attacked in TRAIN | `results/claims/supervised.claims` |
| 3 | The same holds on a second benchmark | CERT r4.2: supervised boosting AUC 0.987 against Isolation Forest 0.732; 18 richer features help neither | `results/claims/cert_rich.claims` |
| 4 | Few labels are needed | 10 incidents: logistic AUC 0.819 against 0.783 for Isolation Forest, slow-insider episode recall 0.657 against 0.283 at a 5 percent label-free budget; 20 incidents: F1 0.525 against 0.470 | `results/claims/label_curve.claims` |
| 5 | Slow drift needs its own budget | at a 1 percent shared budget a fully trained model catches no slow-insider episode; at 5 percent it catches all | `results/claims/label_curve.claims` |
| 6 | The decision layer matters too | gated fusion recall 0.642 against 0.589 for the multiplicative SBRS at an equal benign budget; escalates 35 of 35 low-sensitivity, high-anomaly threats against 1 | `results/claims/fusion.claims` |
| 7 | It runs inline | Tier 1 p99 44.6 ms in the running proxy; images handled asynchronously in Tier 2 | `results/claims/latency.claims` |

Supporting contributions: the measured on-device PII track (PaddleOCR against EasyOCR, three local VLMs, the cascade's failed cost rationale), the CUSUM drift detector as the label-free option for slow drift, and one-command reproducibility with every threshold chosen on validation.

Limits the paper must state with this claim: all behavioural data are synthetic (our generator and CERT); the supervised layer learns from attacks produced by the same simulator it is tested on (N-067); a new deployment has no labels on its first day, and 1 to 5 labels make the layer worse than Isolation Forest (N-068); gradient boosting is unstable below about 50 labels (N-069); CERT has 7 test insiders.

Suggested title: "From Anomalous to Malicious: Label-Efficient Behavioural Risk Scoring for SaaS Data-Loss Prevention, with a Reproducible Evaluation". This is a suggestion for the writing assistant; the title is the authors' decision.
