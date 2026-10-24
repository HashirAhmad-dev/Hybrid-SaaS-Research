# negative_results.md

Every result that went against the design or against the submitted paper. Nothing here is removed
when a later run looks better; later runs are added below with their own run id.

## Inherited from the baseline (before paper-v2), verified against the metrics files in T0.1

| ID | Result | Evidence |
|---|---|---|
| N-001 | The hybrid does not beat Isolation Forest alone on flag-level F1 (test, seed 42: hybrid 0.629 vs IF-only 0.634). | `results/baseline_20261023/metrics.json` keys `test_flag_level.hybrid.f1`, `test_flag_level.if_only.f1` |
| N-002 | Hybrid AUC (0.827) is below LSTM-only AUC (0.859) on test. | same file, `test_auc_overall` |
| N-003 | Slow malicious-insider drift is almost undetected at the F1-optimal point: window recall 1/51 = 0.020, episode recall 1/6. EWMA catches 2/6 episodes. | same file, `per_class_recall.malicious_insider` |
| N-004 | Enforcement-band recall is 0.604; 38 of 96 test threats are PERMITted, most of them malicious insiders. | same file, `test_enforcement_bands.hybrid_alert_or_block` |
| N-005 | The EasyOCR confidence threshold tau_ocr = 0.85 does not transfer; the F1-optimal tau is 0.98, which sends almost every image to the VLM. | `pii_metrics_google-gemma-3-4b-it-deepinfra.json` `tau_calibration` |
| N-006 | OCR confidence does not rank difficulty: a pristine render scores 0.804, below the scanned mean 0.844. | same file, `ocr` |
| N-007 | Presidio ADDRESS recall on clean text is about 0.02; most valid Mastercard numbers are missed. | `evaluation/REAL_RESULTS_PII.md` section 6 |
| N-008 | gemma-3-4b-it on images: NID recall 0.53, CREDIT_CARD recall 0.79, 9 spurious EMAILs. | gemma metrics file, `head_to_head_on_images_the_vlm_saw.by_entity_type_vlm` |
| N-009 | The PII benchmark has a ceiling: Qwen2.5-VL-72B scores 240/240 on the 80 images. | Qwen ovhcloud metrics file, `head_to_head_on_images_the_vlm_saw.vlm` |
| N-010 | Three of four attack classes reach AUC about 1.0, so the synthetic attacks are too easy to separate. | baseline `per_class_recall.*.auc_*` |

## T1.4: ten independently generated datasets (keys `anomaly.multiseed.*`, file `results/multiseed_summary.csv`)

| ID | Result | Evidence key |
|---|---|---|
| N-011 | The hybrid's flag-level F1 (0.635 ± 0.049) is within one sd of Isolation Forest alone (0.622 ± 0.060). The hybrid advantage over IF is not established. | `anomaly.multiseed.f1_hybrid`, `.f1_if_only` |
| N-012 | The validation-chosen alpha is unstable across datasets: mean 0.235, range 0.00 to 0.80. In some datasets the hybrid is exactly Isolation Forest (alpha 0). | `anomaly.multiseed.alpha.*` |
| N-013 | Hybrid AUC (0.821) stays below LSTM-only AUC (0.869) on average across datasets. | `anomaly.multiseed.auc_*` |
| N-014 | Slow malicious-insider drift: mean window recall 0.029, mean episode recall 0.133 at the F1-optimal point. Isolation Forest AUC on this class is 0.551, near chance. | `anomaly.multiseed.recall_malicious_insider`, `.auc_if_malicious_insider` |
| N-015 | Enforcement F1 at the shipped bands averages 0.441 ± 0.060, below the single seed-42 value 0.475 the paper would otherwise quote. | `anomaly.multiseed.enf_f1_shipped_bands` |
| N-016 | Benign-burst suppression is not perfect on every dataset: the hybrid flags 14.8 percent of bursts in one dataset (mean 1.5 percent; EWMA mean 66.8 percent). | `anomaly.multiseed.benign_burst_flag_rate_hybrid.max` |
| N-017 | The validation-calibrated beta is not stable: it ranges from 2.0 to 8.0 across datasets (knee rule). The single value 2.5 is a property of seed 42. | `anomaly.multiseed.sbrs_beta_recalibrated.*` |

## T2.1: detector and fusion ablation, 10 datasets (keys `ablation.summary.*`, `results/ablation/ablation_table.csv`)

| ID | Result | Evidence key |
|---|---|---|
| N-018 | Weighted-mean hybrid F1 at the validation threshold (0.629) equals Isolation Forest alone (0.626). Fusion adds AP (0.578 vs 0.552) but no F1. | `ablation.summary.hybrid_weighted.valf1_f1`, `.iforest.valf1_f1` |
| N-019 | A simple per-user z-score (max absolute personal z) reaches AUC 0.849, above the weighted hybrid (0.821) and the forest (0.779). The deep component is not needed to beat the forest on ranking. | `ablation.summary.zscore.auc` |
| N-020 | Max fusion beats the paper's weighted mean on AUC (0.855 vs 0.821) and on R@5%FPR, but loses on F1 (0.605 vs 0.629). No fusion form wins on every metric. | `ablation.summary.hybrid_max.*` |
| N-021 | The LSTM is the only component with signal on slow drift (malicious-insider AUC 0.744, recall 0.170 at its own F1 threshold), and the weighted fusion throws most of it away (hybrid malicious recall 0.027). | `ablation.summary.lstm.per_class.malicious_insider.*` |
| N-022 | LOF at the sklearn default k=20 is below chance on this data (injected training-period attacks form dense clusters); with k chosen on validation (200 to 500) it reaches AUC 0.779 but AP only 0.246. | `ablation.summary.lof.*`, D-008 |

## T2.2: cluster bootstrap, paired comparisons (keys `stats.*`, `results/stats/paired_vs_hybrid.csv`)

| ID | Result | Evidence key |
|---|---|---|
| N-023 | Hybrid minus Isolation Forest F1 = 0.003, 95 percent cluster-bootstrap CI [-0.013, 0.020]. The hybrid is not shown to beat the forest on F1. | `stats.iforest.paired_vs_hybrid.f1.*` |
| N-024 | The hybrid's AUC is significantly BELOW three alternatives: LSTM alone (-0.048, CI upper bound -0.024), per-user z-score (-0.027, CI upper bound -0.002), and max fusion (-0.034, CI upper bound -0.016). | `stats.lstm/zscore/hybrid_max.paired_vs_hybrid.auc.*` |
| N-025 | With honest clustering, hybrid malicious-insider window recall is 0.027 with CI [0.008, 0.048]. | `stats.hybrid_weighted.recall_malicious_insider.*` |

For balance (not negative): the hybrid's F1 is significantly above LSTM alone (+0.100, CI lower 0.062), per-user z-score (+0.075, CI lower 0.046), LOF (+0.179) and EWMA (+0.518, CI lower 0.454).

## T2.3: difficulty sweep (keys `sweep.summary.*`, `results/sweep/`)

| ID | Result | Evidence key |
|---|---|---|
| N-026 | At attack intensity 0.25 every detector falls to AUC 0.72 to 0.74, and malicious-insider AUC is at chance for all of them (LSTM 0.500, hybrid 0.507). The three "loud" classes stay separable only because their default signatures are strong. | `sweep.summary.o0p0.i0p25.*` |
| N-027 | The weighted hybrid is never the best detector by AUC at intensity 0.75 or above; the LSTM alone leads (0.895 at intensity 1.5 vs hybrid 0.865). At 0.25 and 0.5 the differences between hybrid, z-score, IF and LSTM are within one sd. | `sweep.summary.o0p0.*.auc` |
| N-028 | Isolation Forest gains least from louder attacks (0.728 to 0.820 from intensity 0.25 to 1.5) and stays near chance on the malicious-insider class (0.641 even at 1.5). | `sweep.summary.o0p0.*.iforest.*` |

Neutral: adding benign look-alike episodes (overlap 0.5) lowers AUC by at most about 0.03 for any detector at default intensity.

## T2.4: dedicated drift detector (keys `drift.summary.*`, `results/drift/drift_summary.csv`)

| ID | Result | Evidence key |
|---|---|---|
| N-029 | Adding a CUSUM drift detector next to the hybrid raises malicious-insider episode recall from 0.133 to 0.567, but lowers overall F1 from 0.635 to 0.619 and triples the false-positive rate (0.25 to 0.80 percent). It is a trade, not a free gain. | `drift.summary.cusum.hybrid_or_drift.*`, `.hybrid_only.*` |
| N-030 | The drift detector fires on 20 percent of benign-burst hours, partly undoing the hybrid's burst suppression. | `drift.summary.cusum.test_false_alarm_rate_benign_bursts` |
| N-031 | Page-Hinkley is worse than CUSUM on every summary metric (malicious episode recall 0.433, combined F1 0.586). | `drift.summary.ph.*` |
| N-032 | Each test split holds only about 6 malicious episodes; per-dataset episode recall moves in steps of 1/6 and ranges 0.33 to 0.83 for CUSUM. | per-dataset keys `drift.ds<s>.cusum.per_class.malicious_insider.*` |

The supervised probe (labels used for training, not deployable) reaches malicious-insider AUC 0.870 but only 0.214 window recall at its validation-F1 threshold. The unsupervised LSTM reaches AUC 0.744 on the same class. The signal is in the data; a threshold that serves all classes does not extract it.

## T2.5: SBRS fusion study (keys `fusion.summary.*`, `results/sbrs_fusion/`)

| ID | Result | Evidence key |
|---|---|---|
| N-033 | Reviewer 2 was right: the multiplicative SBRS escalates only 1 of 35 threats that have low content sensitivity (S < 30) and a high anomaly score (A at or above the hybrid's threshold), across 10 datasets. Gated fusion escalates 35 of 35, additive 33 of 35. | `fusion.summary.*.low_S_high_A_escalated.sum` |
| N-034 | At the same benign budget (about 4.7 percent of benign sessions ALERT or BLOCK), the multiplicative form catches fewer threats (recall 0.589) than gated (0.642), additive (0.630) or logistic (0.627) fusion. The shipped design is not the best of the forms tested. | `fusion.summary.*.threat_recall.mean` |
| N-035 | Max fusion is the worst form (recall 0.320): S/100 alone puts many benign sensitive-file sessions above the budget. | `fusion.summary.max.*` |

For balance: the multiplicative form never flags a benign burst (0 percent), gated flags 1.5 percent, additive 5.6 percent, logistic 9.5 percent.

## T3.1 / T3.5: PII corpus v2 (keys `pii2.*`, `results/pii_v2/pii_v2_metrics.json`, EVAL documents)

| ID | Result | Evidence key |
|---|---|---|
| N-036 | On the harder v2 corpus Branch 1 (Presidio on clean text) falls from F1 0.856 (v1) to 0.728, mainly through false positives on near-miss strings: DOB precision 0.41 (document dates), PERSON precision 0.62 (company names), 49 false entities on PII-free documents. | `pii2.v2.branch1.presidio.*` |
| N-037 | OCR+Presidio on v2 images reaches F1 0.486 overall and 0.211 on hard images. | `pii2.v2.ocr.easyocr_cpu.presidio.*` |
| N-038 | The T3.5 street-address recogniser raises ADDRESS recall from 0.05 to 0.47 but its precision is only 0.35; the Mastercard recogniser closes the gap fully (recall 0.80 to 1.00, precision 1.00). Overall Branch 1 F1 rises 0.728 to 0.769. | `pii2.v2.branch1.presidio_plus.by_type.*` |

Reversal of an earlier finding: on v2, EasyOCR confidence DOES rank difficulty (AUC 0.884 easy vs hard, Spearman 0.552 with per-document F1), unlike on v1 (Spearman 0.187). The v1 statement "confidence does not rank difficulty" held for v1's narrow degradation range only.

## T3.6: two-tier latency (keys `latency.*`)

| ID | Result | Evidence key |
|---|---|---|
| N-039 | The design's single "300 ms end to end" goal cannot hold for image payloads: Tier 2 (EasyOCR + Presidio on CPU) holds an upload for 3.4 s at p50 and 5.3 s at p95. Only the inline text-and-behaviour tier meets a sub-300 ms budget (p99 44.6 ms). | `latency.tier2.hold_ms.*`, `latency.tier1.warm_client_ms.*` |
| N-040 | A cold proxy process needs about 9 s for its first Tier 1 decision (model loading); a deployment must pre-load. | `latency.tier1.cold_client_ms.*` |

## T3.2: PaddleOCR vs EasyOCR (keys `pii2.*.ocr.*`)

| ID | Result | Evidence key |
|---|---|---|
| N-041 | Substituting EasyOCR for the designed PaddleOCR cost a lot of accuracy: on v2 images OCR+Presidio+ F1 is 0.516 with EasyOCR and 0.701 with PaddleOCR (hard images 0.223 vs 0.554; v1 images 0.793 vs 0.955). The original evaluation understated what the designed OCR branch can do. | `pii2.v2.ocr.*.presidio_plus.all.f1` |
| N-042 | PaddleOCR is about 5 times slower on this CPU (mean 19.8 s per image vs 3.7 s; oneDNN had to be disabled, D-017). GPU latency was not measured. | `pii2.v2.ocr.paddleocr_cpu.confidence.seconds_per_image_mean` |
| N-043 | PaddleOCR's confidence is nearly saturated (mean 0.986 easy, 0.961 hard), so it separates easy from hard documents worse than EasyOCR's (AUC 0.762 vs 0.884). A fixed tau_ocr = 0.85 would send almost nothing to the VLM with PaddleOCR. | `pii2.v2.ocr.*.confidence.*` |

## T3.1: FUNSD real scanned forms (keys `pii2.funsd.*`, derived partial gold, D-021)

| ID | Result | Evidence key |
|---|---|---|
| N-044 | On real scanned forms (FUNSD eval split) the OCR branch finds only part of the derived PII: recall 0.573 with PaddleOCR+Presidio and 0.324 with EasyOCR+Presidio (PERSON 0.533 vs 0.246, PHONE 0.783 vs 0.650). F1 is 0.190 and 0.116. Precision (0.114 and 0.070) is a lower bound because the gold covers only linked form fields. | `pii2.funsd.ocr.*.presidio.all.*` |
| N-045 | The custom recognisers (Presidio+) give no gain on real forms (PaddleOCR F1 0.186 vs 0.190) and find no FUNSD address. | `pii2.funsd.ocr.*.presidio_plus.*` |

## T3.3: local VLMs through LM Studio (keys `pii2.*.vlm.*`)

| ID | Result | Evidence key |
|---|---|---|
| N-046 | Qwen2.5-VL-3B (Q4_K_M, local, RTX 3060, peak about 4.3 GB VRAM) is far below every other image path. Eval F1: v1 images 0.325, v2 images 0.121, v2 hard 0.000, FUNSD 0.000. Precision is 1.000 on v1 and v2, so it rarely invents entities; it returns an empty list for most images. The model closest in size to the paper's PaliGemma-3B design is therefore not usable as the Branch 3 fallback. | `pii2.*.vlm.qwen2-5-vl-3b-instruct.all.*` |
| N-047 | 53 of 519 Qwen-3B answers were not valid JSON; many are a run of the letter "G", a known degenerate output of this model under llama.cpp. They count as no prediction. LM Studio downsizes each image to about 800 to 1,300 prompt tokens, which may limit legibility of small print; this was not varied. | `pii2.*.vlm.qwen2-5-vl-3b-instruct.status_counts.*` |
| N-048 | gemma-3-4b-it run locally (Q4_K_M) reaches F1 0.971 on v1 images (the hosted run in the original study had 0.936 on all 80 v1 images; ours is the 60-image eval split) but drops to 0.845 on the harder v2 images (hard level 0.682) and 0.407 on FUNSD. Long numerics remain its weakness: v2 credit-card recall 0.443 and password recall 0.587. 8 of 519 requests were rejected by the server (HTTP 400; probably the image did not fit the 4096-token context we set, not verified) and count as no prediction. | `pii2.*.vlm.gemma-3-4b-it.*` |

## T3.4: cascade cost versus accuracy (keys `pii2.*.cascade.*`)

| ID | Result | Evidence key |
|---|---|---|
| N-049 | The cost rationale of the cascade does not hold with a 4B VLM. With gemma, the calib-chosen tau sends almost every image to the VLM (eval share 0.99 with EasyOCR on v2, 1.00 with PaddleOCR), so the cascade is never cheaper than "VLM always", and its F1 equals the VLM's alone (v2 0.843 vs 0.845). The design's tau = 0.85 is worse than both on v2 (0.798 EasyOCR, 0.708 PaddleOCR). | `pii2.v2.cascade.*.gemma-3-4b-it.*` |
| N-050 | The learned "needs VLM" router (logistic regression, cut chosen on calib) also learns to route everything (eval VLM share 1.00 on v2 and v1) and so saves no cost. It routes 0.73 of FUNSD images with EasyOCR, at F1 0.241 against 0.407 for "VLM always". | `pii2.*.cascade.*.router.*` |
