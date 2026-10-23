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
