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
| N-011 | The hybrid's flag-level F1 at the deployed threshold (0.635 ± 0.049) is within one sd of Isolation Forest alone (0.622 ± 0.060). The hybrid advantage over IF is not established. | `anomaly.multiseed.f1_hybrid`, `.f1_if_only` |
| N-012 | The validation-chosen alpha is unstable across datasets: mean 0.235, range 0.00 to 0.80. In some datasets the hybrid is exactly Isolation Forest (alpha 0). | `anomaly.multiseed.alpha.*` |
| N-013 | Hybrid AUC (0.821) stays below LSTM-only AUC (0.869) on average across datasets. | `anomaly.multiseed.auc_*` |
| N-014 | Slow malicious-insider drift: mean window recall 0.029, mean episode recall 0.133 at the deployed F1-optimal threshold. Isolation Forest AUC on this class is 0.551, near chance. | `anomaly.multiseed.recall_malicious_insider`, `.auc_if_malicious_insider` |
| N-015 | Enforcement F1 at the shipped bands averages 0.441 ± 0.060, below the single seed-42 value 0.475 the paper would otherwise quote. | `anomaly.multiseed.enf_f1_shipped_bands` |
| N-016 | Benign-burst suppression is not perfect on every dataset: the hybrid flags 14.8 percent of bursts in one dataset (mean 1.5 percent; EWMA mean 66.8 percent at its deployed threshold). | `anomaly.multiseed.benign_burst_flag_rate_hybrid.max` |
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
| N-029 | Adding a CUSUM drift detector next to the hybrid raises malicious-insider episode recall from 0.133 to 0.567 (both at the deployed hybrid threshold), but lowers overall F1 from 0.635 to 0.619 and triples the false-positive rate (0.25 to 0.80 percent). It is a trade, not a free gain. | `drift.summary.cusum.hybrid_or_drift.*`, `.hybrid_only.*` |
| N-030 | The drift detector fires on 20 percent of benign-burst hours, partly undoing the hybrid's burst suppression. | `drift.summary.cusum.test_false_alarm_rate_benign_bursts` |
| N-031 | Page-Hinkley is worse than CUSUM on every summary metric (malicious episode recall 0.433, combined F1 0.586). | `drift.summary.ph.*` |
| N-032 | Each test split holds only about 6 malicious episodes; per-dataset episode recall moves in steps of 1/6 and ranges 0.33 to 0.83 for CUSUM. | per-dataset keys `drift.ds<s>.cusum.per_class.malicious_insider.*` |

The supervised probe (labels used for training, not deployable) reaches malicious-insider AUC 0.870 but only 0.214 window recall at its validation-F1 threshold. The unsupervised LSTM reaches AUC 0.744 on the same class. The signal is in the data; a threshold that serves all classes does not extract it.

## T2.5: SBRS fusion study (keys `fusion.summary.*`, `results/sbrs_fusion/`)

| ID | Result | Evidence key |
|---|---|---|
| N-033 | Reviewer 2 was right: the multiplicative SBRS escalates only 1 of 35 threats that have low content sensitivity (S < 30) and a high anomaly score (A at or above the hybrid's threshold), across 10 datasets. Additive fusion escalates 33 of 35. Gated fusion escalates 35 of 35, but only by construction: these threats are defined by A at or above tau_A, which is the gate (F13). | `fusion.summary.*.low_S_high_A_escalated.sum` |
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

## T2.6: CERT r4.2, a second synthetic benchmark (keys `cert.*`)

CERT test split: 65,249 active user-hours, 330 positive hours (0.5 percent), 7 insiders. Every threshold and parameter was chosen on validation. CERT is reported separately and never pooled with our datasets.

| ID | Result | Evidence key |
|---|---|---|
| N-051 | The engine performs far worse on CERT than on our generator. Weighted hybrid test AUC 0.733 and F1 0.057 (precision 0.031, recall 0.388, FPR 6.3 percent), against a mean F1 near 0.63 on our data. The near-1.0 AUCs on our loud attack classes do not carry over to this benchmark. | `cert.ablation.hybrid_weighted.*` |
| N-052 | The LSTM adds nothing to the deployed fusion on CERT. Validation chose alpha 0.00, so the weighted hybrid is Isolation Forest alone. LSTM-only AUC is 0.707 against 0.733 for Isolation Forest. Rank-average fusion scores highest on test (AUC 0.751, F1 0.065), but it was not the validated choice and seven insiders cannot separate it from the others. | `cert.ablation.*` |
| N-053 | Episode recall on CERT is not evidence of skill. The hybrid reaches episode recall 1.00 on scenario 2, but an episode has about 54 positive hours on average, so a flagger unrelated to the attack, at the same 6.3 percent FPR, would hit an average-length episode with probability about 0.97 if its flags were independent. Report hour-level precision and recall with it. | `cert.ablation.hybrid_weighted.per_class.cert_scenario_2.episode_recall` |
| N-054 | The drift detectors do not improve the combined result on CERT. Adding Page-Hinkley lowers hybrid F1 from 0.057 to 0.054 and adding CUSUM lowers it to 0.052, with no gain in recall. Alone, Page-Hinkley finds 5 of 6 scenario 2 episodes at a 0.66 percent false-alarm rate, with median detection after 147 hours and hour-level recall 0.031; CUSUM finds 2 of 6 (validation had 0.82, so its choice did not hold on test). | `cert.drift.*` |
| N-055 | A supervised probe, trained with labels on TRAIN and not deployable, reaches only AUC 0.754 and F1 0.104 on CERT. The six mapped hourly features therefore limit what any detector here can do. **Corrected by N-062:** a nonlinear probe on the same six features reaches AUC 0.987, so the limit was the linear probe, not the features. The mapping is our own approximation (`docs/CERT_MAPPING.md`), and these results depend on it. | `cert.drift.supervised_probe.*` |
| N-056 | The CERT test split is small: 7 insiders, 6 scenario 2 episodes and 1 scenario 3 episode, with no scenario 1 positives. Insiders are 70 of the 200 sampled users, a higher share than in the full release, and their earlier attack hours stay unlabelled in the fitting data. | `cert.mapping.*` |

## T3.3 addendum: Qwen2.5-VL-7B run locally (keys `pii2.*.vlm.qwen2-5-vl-7b-instruct.*`)

Qwen2.5-VL-7B-Instruct Q4_K_M with its vision projector, served by LM Studio on the RTX 3060 (context 4096, one request at a time, model reloaded every 100 images). Same prompt, cache and scoring as the other local VLMs. All 519 answers were valid JSON.

| ID | Result | Evidence key |
|---|---|---|
| N-057 | The larger Qwen model does not beat gemma-3-4b-it. Eval F1 for Qwen2.5-VL-7B against gemma: v1 images 0.789 against 0.971, v2 images 0.727 against 0.845, FUNSD 0.132 against 0.407. It is far better than Qwen2.5-VL-3B (0.325, 0.121, 0.000). | `pii2.*.vlm.*.all.f1` |
| N-058 | Qwen2.5-VL-7B is precise but omits fields. Precision is 0.929 on v1 and 0.944 on v2, but recall is 0.686 and 0.590. It almost never reports addresses (recall 0.17 on v1, 0.07 on v2), card numbers (0.12, 0.03) or passwords (0.09, 0.04). We read a sample of answers: they are well-formed JSON lists that leave these fields out, and some card numbers are labelled PHONE. The low recall is the model's output, not a parsing fault. | `pii2.v1.vlm.qwen2-5-vl-7b-instruct.by_type.*`, `pii2.v2.vlm.qwen2-5-vl-7b-instruct.by_type.*` |
| N-059 | The 7B model only just fits the 6 GB card and is slow. Peak whole-card GPU memory was 5,980 MiB of 6,144. Mean time per image is 27.3 s on v1, 36.0 s on v2 and 41.7 s on FUNSD, against 7.4, 4.5 and 21.5 s for gemma (two to eight times slower). That is far outside any inline latency budget and slow even for the asynchronous Tier 2. | `pii2.*.vlm.qwen2-5-vl-7b-instruct.seconds_per_image_mean`, `pii2.*.vlm.qwen2-5-vl-7b-instruct.gpu_peak_mib` |
| N-060 | The cascade with the 7B model is worse than with gemma at every calib-chosen tau. Eval F1 with EasyOCR: v2 0.719 against 0.843, FUNSD 0.122 against 0.331. With PaddleOCR: v2 0.720 against 0.845, FUNSD 0.138 against 0.397. On v1 with PaddleOCR the chosen tau sends no image to the VLM, so both reach 0.955. | `pii2.*.cascade.*.qwen2-5-vl-7b-instruct.eval_at_calib_tau.f1` |

## CERT richer-features experiment (keys `cert.rich.*`, `cert.rich_importance.*`, D-027)

Same 200 users, hours, labels and splits as T2.6. BASE is the six mapped features; RICH adds 18 generic counts from the raw logs. Thresholds on validation. Paired user-level bootstrap, 2,000 resamples, for the AUC difference. The refitted BASE Isolation Forest gives test AUC 0.732, against 0.733 in T2.6.

| ID | Result | Evidence key |
|---|---|---|
| N-061 | Richer features do not help the unsupervised detectors. Isolation Forest test AUC falls from 0.732 to 0.692 (difference -0.040, CI -0.051 to -0.026) and F1 from 0.058 to 0.035. The per-user z-score is unchanged (0.678 to 0.674, CI -0.028 to 0.029). | `cert.rich.base.*`, `cert.rich.rich.*`, `cert.rich.auc_diff_rich_minus_base.*` |
| N-062 | The six BASE features already carry the signal. A gradient-boosting probe trained with labels on TRAIN reaches test AUC 0.987 and F1 0.339 (precision 0.236, recall 0.600, FPR 1.0 percent) on BASE. No test episode has positive hours in TRAIN, so it generalises across insiders. RICH does not improve it (AUC 0.980, difference -0.007, CI -0.016 to 0.000). Only the linear probe gains from RICH (0.776 to 0.854). This overturns the reading of N-055 and our earlier advice that features were the bottleneck: the gap is between unsupervised anomaly scores and what is actually malicious. | `cert.rich.base.probe_boosting.*`, `cert.rich.auc_diff_rich_minus_base.*` |
| N-063 | The boosting probe relies mainly on removable-media file copies. Shuffling `file_type_category` lowers validation AUC by 0.348; after-hours activity by 0.053; every other feature by 0.022 or less. CERT scenario 2 is data theft over USB, so the probe has learned the scenario's signature, which an unsupervised detector treats as one rare event among many. | `cert.rich_importance.*` |
| N-064 | Even the best probe flags 0.236 correct hours per flag at 1 percent FPR, because positives are 0.5 percent of test hours. It needs labelled incidents to train, which a new deployment does not have. | `cert.rich.base.probe_boosting.precision` |

## Supervised probes on the 10 generated datasets (keys `supervised.*`, D-028)

Logistic regression and gradient boosting, trained with labels on TRAIN, on the same six features. Thresholds on validation. The main result is positive (FIXES_SUMMARY section 5); the entries below are its limits and the results that go against the unsupervised design.

| ID | Result | Evidence key |
|---|---|---|
| N-065 | Every unsupervised detector loses to a supervised model on the same features, on all 10 datasets. Gradient boosting: AUC 0.951 ± 0.021, F1 0.785 ± 0.043; the weighted hybrid: AUC 0.821 ± 0.048, F1 0.629 ± 0.054. Boosting beats the hybrid on AUC, F1 and malicious-insider AUC in 10 of 10 datasets. | `supervised.summary.*` |
| N-066 | Slow malicious-insider drift is learnable from these features. Boosting finds 0.900 of malicious-insider episodes (malicious AUC 0.901) where the hybrid finds 0.117 and Isolation Forest 0.033. The unsupervised design's weakness on this class is a weakness of anomaly scoring, not of the data. | `supervised.summary.probe_boosting.per_class.malicious_insider.*` |
| N-067 | The supervised result is optimistic for three reasons. (a) Training and test attacks come from the same generator templates, so the probe can learn the generator's signature. (b) 283 of 310 test episodes belong to users who were also attacked in TRAIN; on the other 27 episodes boosting still finds 25 (0.926), so it does not only memorise users, but that subset is small. (c) A real deployment starts with no labelled incidents. On CERT, where attacks come from a different simulator, the same probe reached AUC 0.987 (N-062). | `supervised.summary.overlap.*`, `supervised.summary.probe_boosting.unseen_user.*` |

## Label learning curve (keys `labelcurve.*` at a 1 percent alert budget, `labelcurve_b5.*` at 5 percent, D-029)

k labelled TRAIN episodes out of 143, 5 random draws, 10 datasets. Unchosen attack hours are treated as benign. The threshold is a percentile of validation scores, so no validation label is used. The 5 percent budget was added after the 1 percent results were seen (D-029 amendment 2).

| ID | Result | Evidence key |
|---|---|---|
| N-068 | The supervised layer needs tens of labelled incidents, not a handful. With 1 to 5 incidents both probes rank attacks worse than the unsupervised Isolation Forest (AUC 0.530 to 0.769 against 0.783). Logistic regression passes it at about 10 incidents (AUC 0.819) and gradient boosting only at about 50 (0.882). | `labelcurve_b5.summary.k*_*.auc.mean` |
| N-069 | Gradient boosting is unstable with few labels. At a 5 percent budget and 1 to 5 incidents its test FPR is 0.43 to 0.46, because its validation scores do not transfer to test. Logistic regression stays near the budget (FPR 0.04). With few labels, use the simpler model. | `labelcurve_b5.summary.k1_boosting.fpr.mean`, `labelcurve_b5.summary.k1_logistic.fpr.mean` |
| N-070 | The operating point decides whether slow drift is caught. At a 1 percent alert budget, which is below the share (about 4 percent) of attack hours, even boosting trained on all 143 incidents finds 0.000 of malicious-insider episodes: the loud classes use up the budget. At 5 percent it finds 1.000. The 0.900 of D-028 used a threshold chosen with validation labels, not a fixed budget. | `labelcurve.summary.kall_boosting.malicious_episode_recall.mean`, `labelcurve_b5.summary.kall_boosting.malicious_episode_recall.mean` |

## Transfer tests for the supervised probes (keys `transfer.*`, D-031, task F1)

| ID | Result | Evidence key |
|---|---|---|
| N-071 | The supervised layer does not detect an attack type it was not trained on. With malicious-insider hours removed from TRAIN and VALIDATION, boosting's AUC on held-out slow drift falls from 0.901 to 0.510 and logistic regression's from 0.875 to 0.314, below chance; both find 0.000 of its episodes. Isolation Forest, which needs no labels, has AUC 0.560 on the same class. Held-out negligent insiders: logistic AUC 0.313 and episode recall 0.045, boosting 0.998 and 0.873. Held-out compromised accounts: boosting episode recall 0.544. | `transfer.loco.*` |
| N-072 | The supervised layer does not transfer between environments. Trained on all 10 simulator datasets and applied unchanged to CERT r4.2, boosting reaches AUC 0.246 and logistic regression 0.365, both below chance, and neither flags a single attack hour at a label-free 1 percent budget. Isolation Forest fitted on CERT's own FIT hours reaches AUC 0.732 and finds all 6 scenario 2 episodes under the same rule. | `transfer.sim_to_cert.*` |
| N-073 | Consequence for the design: the supervised layer adds detection only for attack types the deployment has already seen and labelled, in that deployment. It cannot replace the unsupervised detectors or the CUSUM drift detector, which must stay on to cover new attack types. N-062 and N-065 (supervised wins) hold in-distribution only. | `transfer.loco.*`, `transfer.sim_to_cert.*` |

## Qwen2.5-VL-3B diagnosis (keys `vlmdiag.*`, task F5)

| ID | Result | Evidence key |
|---|---|---|
| N-074 | Qwen2.5-VL-3B's F1 of 0.000 on FUNSD is the model answering "no PII", not a parsing or input fault. Of 199 FUNSD answers, 183 are valid JSON and every one of them is the empty list `[]` (median 2 completion tokens); the other 16 are degenerate runs of one repeated character. The image was not cut off: the median prompt is 1,222 tokens (maximum 1,366) in a 4,096-token context, so the whole image was encoded. 109 of the 199 forms have derived gold entities. The same model returns an empty list for 177 of 203 valid v2 answers. Qwen2.5-VL-7B, with the same image encoding (same prompt-token counts), returns a non-empty list for 37 FUNSD forms. gemma-3-4b-it encodes every image in a fixed 511-token prompt and answers 182 FUNSD forms with entities. All three run as Q4_K_M weights with an F16 vision projector; quantisation was not varied, so a higher-precision 3B might behave differently. | `vlmdiag.qwen2-5-vl-3b-instruct.funsd.*`, `results/pii_v2/vlm_diagnosis.json` |

## Difficulty sweep on 10 seeds (keys `sweep.summary10.*`, D-030, task F6)

| ID | Result | Evidence key |
|---|---|---|
| N-075 | Benign look-alikes hurt flag-level detection, not ranking. At intensity 1.0, adding look-alike episodes (overlap 0.5) moves hybrid AUC only from 0.821 to 0.817, because look-alikes are about 2 percent of test negatives, but hybrid F1 falls from 0.629 to 0.535, precision from 0.918 to 0.597 and FPR rises from 0.002 to 0.014. Isolation Forest behaves the same (F1 0.626 to 0.540, precision 0.937 to 0.622). The overlap condition must be reported with F1, precision and FPR; AUC alone hides it. | `sweep.summary10.o0p0.i1p0.*`, `sweep.summary10.o0p5.i1p0.*` |
| N-076 | On 10 seeds, at intensity 0.25 no detector separates slow drift: malicious-insider AUC is 0.481 for the hybrid, 0.477 for Isolation Forest and 0.501 for the LSTM. Overall AUC is 0.729, 0.726 and 0.697. The 3-seed result (N-026) holds. | `sweep.summary10.o0p0.i0p25.*` |

## Latency under load, payload size and the VLM Tier 2 (keys `latency_extra.*`, task F7)

Measured on the laptop with no other job running, LM Studio serving gemma-3-4b-it on the GPU. Latency varies from run to run.

| ID | Result | Evidence key |
|---|---|---|
| N-077 | Tier 1 time grows with the text size, almost all of it in Presidio: client p50 73 ms at 1 KB, 211 ms at 4 KB, 859 ms at 16 KB and 4,944 ms at 64 KB. The inline budget holds only for small text payloads; large text needs the asynchronous path or a size limit. | `latency_extra.payload.*` |
| N-078 | Tier 1 throughput saturates at about 9 requests per second on this laptop. With 16 concurrent clients the client p50 is 197 ms and p99 845 ms (1 client: p50 60 ms, p99 76 ms). This test opens a new connection per request, so its single-client p50 is above the 33.7 ms of T3.6. | `latency_extra.concurrency.*` |
| N-079 | With the local VLM live, Tier 2 holds an image for 9.9 s at p50 and 11.3 s at p95, against 3.4 s for the OCR-only measurement of T3.6. All 20 images were routed to the VLM, because the deployed tau_ocr (0.95) sends almost every image there (N-049). | `latency_extra.tier2_vlm.*` |
| N-080 | Before F7, Tier 2 decided with the multiplicative SBRS bands while Tier 1 used the gated fusion. Tier 2 now calls the same configured decision (`backend/final_config.decide`); a test checks both tiers. Earlier Tier 2 outputs (T3.6, T4.1 demo) used the old rule; with the low anomaly scores used there both rules give the same action. | `tests/test_backend_fusion.py` |

## Qwen2.5-VL-3B diagnosis in detail (keys `vlmdiag.*`, task F13; summary in N-074)

| ID | Result | Evidence key |
|---|---|---|
| N-081 | Status counts of every cached answer, per model and corpus (all answers, calib and eval). Qwen2.5-VL-3B: v1 80 valid (67 empty `[]`, 13 with entities); v2 203 valid (177 empty, 26 with entities) and 37 malformed; FUNSD 183 valid (all 183 empty) and 16 malformed. gemma-3-4b-it: v1 80 valid (11 empty); v2 238 valid (5 empty) and 2 request errors; FUNSD 193 valid (11 empty) and 6 request errors. Qwen2.5-VL-7B: v1 80 valid (12 empty); v2 240 valid (31 empty); FUNSD 199 valid (162 empty, 37 with entities). | `vlmdiag.*.status_*`, `vlmdiag.*.ok_empty_list`, `vlmdiag.*.ok_nonempty` |
| N-082 | Raw outputs. Every valid Qwen2.5-VL-3B answer on FUNSD is the two-token string `[]` (median 2 completion tokens). Every malformed answer is a run of the letter "G" (for example V2-0229: "GGGG..."), a degenerate output; all 53 malformed 3B answers are of this kind. When the 3B model does answer, its answers are well formed, for example V2-0121: PERSON "Nathan Peters", DOB "1962-09-02", PHONE "+923050114896". | `results/pii_v2/vlm_diagnosis.json` (samples), `vlmdiag.qwen2-5-vl-3b-instruct.*.degenerate_repeated_char` |
| N-083 | Quantisation and image encoding. All three models ran as Q4_K_M GGUF weights with an F16 vision projector (lmstudio-community builds) in LM Studio with a 4,096-token context. The Qwen models encode an image at near native resolution: median prompt 1,222 tokens on FUNSD (maximum 1,366), so no image was cut off. gemma uses a fixed 511-token prompt per image. Only Q4_K_M was tried; a higher-precision 3B build might answer differently, and this was not tested. | `vlmdiag.*.prompt_tokens_*`, `results/pii_v2/vlm_diagnosis.json` (quantisation) |
