<!-- Copied from docs/FIXES_SUMMARY.md section 5 by tools/build_paper_inputs.py. Edit the source. -->

## 5. Claims the paper may make / must not make

All values are means over the 10 independently generated datasets unless marked. Every value is in a claims file under `results/claims/`, and `docs/CLAIM_EVIDENCE.md` lists the script and run for each.

### May make (with evidence)

| Claim | Evidence |
|---|---|
| A rate-only EWMA baseline is weak on this data (flag F1 0.111) and flags 61.3 percent of benign bursts; the hybrid flags 1.5 percent. | `results/claims/ablation.claims` |
| The hybrid's flag F1 (0.629, 95 percent cluster-bootstrap CI 0.564 to 0.702) is significantly higher than LSTM alone (+0.100), per-user z-score (+0.075), LOF (+0.179) and EWMA (+0.518). | `results/claims/stats.claims` |
| The hybrid's F1 is statistically indistinguishable from Isolation Forest alone (difference 0.003, CI -0.013 to 0.020). Fusion adds a little average precision: AP 0.578 against 0.552, paired difference 0.026 (95 percent cluster-bootstrap CI 0.013 to 0.037); rank-average fusion gives the same AP (difference 0.000, CI -0.012 to 0.014). | `results/claims/stats.claims`, `results/claims/stats_extra.claims` |
| Slow insider drift is the hard case: at the deployed threshold the hybrid finds 13 percent of malicious-insider episodes. A dedicated CUSUM detector beside it raises this to 57 percent, median 8.9 hours to detection, at a false-positive rate of 0.8 percent instead of 0.25 percent, and the detector fires on 20.3 percent of benign-burst hours. | `results/claims/drift.claims`, `results/claims/stats_extra.claims` |
| At an equal benign alert budget, gated fusion (escalate when A is high regardless of S) catches more threats than the multiplicative SBRS (0.642 vs 0.589; paired difference 0.053, 95 percent cluster-bootstrap CI 0.033 to 0.079, with no difference in benign alert rate, CI -0.000 to 0.001; F1 difference 0.030, CI 0.018 to 0.043) and escalates all 35 low-sensitivity, high-anomaly threats, against 1 for the multiplicative form. | `results/claims/fusion.claims` |
| Detection degrades smoothly as attacks get quieter; at intensity 0.25 all detectors sit at AUC 0.72 to 0.74 and none separates slow drift (AUC about 0.5). | `results/claims/sweep.claims` |
| Text-only DLP sees nothing in images; Presidio on clean text reaches F1 0.769 on the harder v2 corpus with the two added recognisers (0.728 without). | `results/claims/pii_v2_branch1_ocr.claims` |
| Adding a Mastercard-range recogniser with a Luhn check closes Presidio's card gap (recall 0.80 to 1.00, precision 1.00). | same |
| Every threshold, weight and band is chosen on validation data; selection code rejects test rows (unit-tested). | `evaluation/selection.py`, `tests/test_selection.py` |
| Results reproduce bit-for-bit with one command. | `reproduce.ps1`, gate records below |
| Tier 1 inline decisions (text PII, anomaly scoring and fusion) take 44.6 ms at p99 inside the running proxy; images go to an asynchronous Tier 2 that holds the upload. | `results/claims/latency.claims` |
| PaddleOCR, the designed OCR engine, was run and beats the EasyOCR substitute on accuracy (v2 images F1 0.701 against 0.516), at about 5 times the CPU time. | `results/claims/pii_v2_ocr_engines.claims` |
| Small VLMs were run on-box on a 6 GB laptop GPU. The best, gemma-3-4b-it, reaches F1 0.845 on the harder v2 images and 0.407 on real FUNSD forms; Qwen2.5-VL-3B and 7B score lower. | `results/claims/pii_v2_vlm_cascade.claims`, `results/claims/pii_v2_vlm_7b.claims` |
| A cost-ordered cascade gives no cost saving at equal accuracy on these corpora, because OCR confidence is too weak a signal (v2 cascade F1 0.843 against VLM-only 0.845, with almost every image routed to the VLM). | `results/claims/pii_v2_vlm_cascade.claims` |
| On CERT r4.2, a community benchmark mapped onto our features, the engine is much weaker (hybrid F1 0.057, AUC 0.733), which bounds how far our simulator results generalise. | `results/claims/cert.claims` |
| On CERT the six features carry the signal, but unsupervised anomaly scores do not find it: a gradient-boosting model trained on labelled TRAIN incidents reaches test AUC 0.987 (F1 0.339) on the same features, against 0.732 for Isolation Forest. Adding 18 richer features does not help either kind of detector. The gap is between "unusual" and "malicious", not a lack of features. | `results/claims/cert_rich.claims` |
| The same holds on our 10 generated datasets: a gradient-boosting model trained on labelled TRAIN incidents reaches AUC 0.951 ± 0.021 and F1 0.785 ± 0.043, against 0.821 and 0.629 for the hybrid, and wins in 10 of 10 datasets. It finds 0.900 of slow malicious-insider episodes, where the hybrid finds 0.117. On users never attacked in TRAIN it finds 25 of 27 episodes. Labelled incidents, not a different unsupervised model, are what closes the slow-drift gap. | `results/claims/supervised.claims` |
| A supervised layer trained on one attack type does not catch another, and a layer trained on the simulator does not work on CERT (held-out slow drift: 0.000 of episodes; simulator to CERT AUC 0.246); unsupervised detectors and CUSUM must stay on. | `results/claims/transfer.claims` |
| About 10 to 20 labelled incidents are enough for a simple supervised layer. With 10 confirmed incidents, logistic regression ranks attacks better than Isolation Forest (AUC 0.819 against 0.783) and, at a 5 percent label-free alert budget, finds 0.657 of slow-insider episodes against 0.283; with 20 it reaches F1 0.525 against 0.470. Gradient boosting needs about 50 incidents and is unstable below that. | `results/claims/label_curve.claims` |

### Must not make

- That the LSTM + Isolation Forest hybrid outperforms its components overall. It does not beat IF on F1 and is below the LSTM, the z-score and max fusion on AUC (N-018 to N-024).
- That the multiplicative SBRS is the best fusion, or that low content sensitivity safely suppresses alerts (N-033, N-034).
- That benign bursts are suppressed on every dataset (one dataset: 14.8 percent, N-016).
- Any single-dataset number (seed 42) as the headline; use the 10-dataset mean with its interval.
- The old draft figures: EWMA FPR 42.7 percent vs hybrid 11.2 percent, SBRS F1 0.93, PII coverage 0.91, 279 ms end to end.
- "Real-time 300 ms end to end". Replace with the measured Tier 1 budget (T3.6).
- That PaliGemma-3B was evaluated (it was not), or that any local VLM matches the hosted Qwen2.5-VL-72B (the 72B ran only on the old v1 corpus).
- That a bigger local model is better: Qwen2.5-VL-7B is below gemma-3-4b-it on every corpus (N-057).
- That the cascade saves cost by sending only hard images to the VLM (N-049, N-050).
- That the system performs well on CERT, or that CERT is real enterprise data (it is synthetic, and the feature mapping is ours; N-051, N-055, N-056).
- That episode recall alone shows skill on CERT (N-053).
- That richer features or a bigger unsupervised model would fix CERT detection (N-061, N-062), or that the supervised probe is deployable without labelled incidents (N-064).
- That the supervised scores (AUC 0.951, 0.987 on CERT) are what a deployment would see: the probes learn from the same simulator's attacks, and a new deployment has no labels (N-067).
- That the supervised layer detects new attack types or transfers between environments (N-071, N-072), or that it can replace the unsupervised detectors (N-073).
- That a few labelled incidents suffice: 1 to 5 make the supervised layer worse than Isolation Forest (N-068). Also not that slow drift is caught at any alert budget: at 1 percent, below the attack share, it is missed entirely (N-070).
- That federated learning, differential privacy or a usability study was done.
- That "existing DLP ignores behaviour" (Microsoft Purview Adaptive Protection uses insider-risk levels in DLP).
- That OCR confidence never ranks difficulty: on v2 it does (AUC 0.884); on v1 it did not.
- That the data are realistic enterprise traffic or real handwriting. All data are synthetic; handwriting is font-rendered.
- The value beta = 2.5 as a general constant: the validation knee ranges from 2.0 to 8.0 across datasets (N-017).
