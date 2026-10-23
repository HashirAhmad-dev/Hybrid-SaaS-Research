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
