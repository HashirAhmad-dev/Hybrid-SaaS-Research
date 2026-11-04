<!-- Copied from docs/FIXES_SUMMARY.md section 1 by tools/build_paper_inputs.py. Edit the source. -->

### Primary claim (replaces "the hybrid LSTM plus Isolation Forest engine detects threats")

> Unsupervised anomaly detection, including our LSTM plus Isolation Forest hybrid, cannot tell unusual behaviour from malicious behaviour, and it misses almost all slow insider drift. The same six behavioural features, given to a supervised layer trained on a deployment's own analyst-confirmed incidents, separate the attack types it has seen, and about 10 to 20 confirmed incidents are enough. The supervised layer does not detect attack types it has not seen and does not transfer to another environment, so it complements the unsupervised detectors and the drift detector rather than replacing them. We therefore propose a layered design: unsupervised detection and CUSUM drift detection always on, plus a supervised layer trained on the deployment's confirmed alerts, with slow drift given its own alert budget.

Evidence, in the order the paper should present it:

| Step | Finding | Numbers | Evidence |
|---|---|---|---|
| 1 | The unsupervised hybrid is no better than its parts | hybrid F1 0.629 [0.564, 0.702]; hybrid minus Isolation Forest 0.003 [-0.013, 0.020]; slow-insider episode recall 0.117 | `results/claims/stats.claims`, `results/claims/supervised.claims` |
| 2 | The features carry the signal; anomaly scoring does not find it | supervised gradient boosting on the same features: AUC 0.951 ± 0.021, F1 0.785 ± 0.043, slow-insider episode recall 0.900, wins in 10 of 10 datasets; 25 of 27 episodes of users never attacked in TRAIN | `results/claims/supervised.claims` |
| 3 | The same holds on a second benchmark | CERT r4.2: supervised boosting AUC 0.987 against Isolation Forest 0.732; 18 richer features help neither | `results/claims/cert_rich.claims` |
| 4 | Few labels are needed | 10 incidents: logistic AUC 0.819 against 0.783 for Isolation Forest, slow-insider episode recall 0.657 against 0.283 at a 5 percent label-free budget; 20 incidents: F1 0.525 against 0.470 | `results/claims/label_curve.claims` |
| 5 | The supervised layer covers only what it has seen | trained without slow-drift examples, boosting finds 0.000 of slow-insider episodes (held-out AUC 0.510, logistic 0.314); trained on the simulator and applied to CERT, AUC 0.246 (boosting) and 0.365 (logistic) against 0.732 for Isolation Forest fitted on CERT | `results/claims/transfer.claims` |
| 6 | Slow drift needs its own budget | at a 1 percent shared budget a fully trained model catches no slow-insider episode; at 5 percent it catches all | `results/claims/label_curve.claims` |
| 7 | The decision layer matters too | gated fusion recall 0.642 against 0.589 for the multiplicative SBRS at an equal benign budget (paired difference 0.053, CI 0.033 to 0.079) | `results/claims/fusion.claims` |
| 8 | It runs inline for small payloads | Tier 1 p99 44.6 ms in the running proxy (single client); about 9 requests per second at saturation; text above a few KB takes 0.2 to 5 s; images held 9.9 s at p50 in Tier 2 with the local VLM | `results/claims/latency.claims`, `results/claims/latency_extra.claims` |

Supporting contributions: the measured on-device PII track (PaddleOCR against EasyOCR, three local VLMs, the cascade's failed cost rationale), the CUSUM drift detector as the label-free option for slow drift, and one-command reproducibility with every threshold chosen on validation.

Limits the paper must state with this claim: all behavioural data are synthetic (our generator and CERT); the supervised layer fails on attack types it has not been trained on and does not transfer from the simulator to CERT (N-071, N-072); the supervised layer learns from attacks produced by the same simulator it is tested on (N-067); a new deployment has no labels on its first day, and 1 to 5 labels make the layer worse than Isolation Forest (N-068); gradient boosting is unstable below about 50 labels (N-069); CERT has 7 test insiders.

Suggested title: "From Anomalous to Malicious: Label-Efficient Behavioural Risk Scoring for SaaS Data-Loss Prevention, with a Reproducible Evaluation". This is a suggestion for the writing assistant; the title is the authors' decision.
