# FIXES_SUMMARY.md

Human-readable report of the paper-v2 work. Updated at the end of every task.

## 1. Status

Phase 0 is complete. Work happens on branch `paper-v2`; the starting commit 2521134 is tagged
`baseline-pre-v2` and its outputs are preserved in `results/baseline_20261023/`. The environment is
recorded in `docs/ENVIRONMENT.md`. The headline numbers in context.md were checked against the metrics
files; five corrections are listed in section 3. No code has changed yet.

## 2. Task table

| Task | Status | What was wrong | What changed (files) | Reproduce | Before | After |
|---|---|---|---|---|---|---|
| T0.1 | DONE | No branch, no preserved baseline, no environment record, context.md unchecked | `docs/ENVIRONMENT.md`, `docs/LOOP_STATE.md`, `docs/DECISIONS.md`, `docs/OPEN_QUESTIONS.md`, `docs/FIXES_SUMMARY.md`, `results/negative_results.md`, `results/baseline_20261023/*`, `CLAUDE.md` | `git diff baseline-pre-v2` | n/a | Baseline frozen; 5 context.md corrections found |

## 3. Corrections to context.md

Checked 2026-10-23 against `evaluation/data/metrics.json`, `sbrs_calibration.json` and the
`pii_metrics_*.json` files (copies in `results/baseline_20261023/`). Every number not listed here matched.

1. **"Old doc bands (beta 0.5, 0.20/0.60): F1 0.131, FPR 50.1 percent" is mislabelled.** The value comes from
   `metrics.json` key `test_enforcement_bands.paper_doc_bands_alert_or_block`. `evaluation/refresh_sbrs_columns.py`
   recomputes `sbrs_value` at beta 2.5 and then applies the 0.50/1.00 bands, so the row is "beta 2.5 with
   bands 0.50/1.00", which matches neither old configuration. The real old configurations, from
   `sbrs_calibration.json`, are: old code (beta 0.5, bands 0.20/0.60) F1 0.087, benign flag rate 85.9 percent;
   old doc (beta 0.5, bands 0.50/1.00) F1 0.134, FPR 47.7 percent.
2. **`evaluation/data/pii_metrics.json` is not a headline file.** It is an early partial run (Qwen2.5-VL-72B
   with only 8 images through the VLM; overall micro F1 0.649 at tau 0.85). The headline PII numbers come from
   `pii_metrics_google-gemma-3-4b-it-deepinfra.json` and `pii_metrics_Qwen-Qwen2-5-VL-72B-Instruct-ovhcloud.json`.
   `pii_metrics_Qwen-Qwen2-5-VL-72B-Instruct.json` is a second partial run.
3. **The calibrated-tau cascade numbers (F1 0.908 gemma, 0.949 Qwen72B) are not held out.** tau = 0.98 was
   chosen on 20 calibration documents, and the reported F1 is computed over all 120 documents, which include
   those 20 (`results.calibrated_tau.executed_only.n_docs = 120`). Task T3.4 replaces this with a clean split.
4. **Source of the "F1 0.479, fp 88" drift (E1).** `sbrs_calibration.json` scores test at the unrounded
   derived cut-points (1.22382 / 1.84367): F1 0.4793, fp 88. `metrics.json` scores the shipped rounded
   cut-points (1.22 / 1.84): F1 0.4754, fp 90. Both are real; they are different thresholds. The paper must
   cite one, labelled.
5. **Branch 3 latency.** context.md says "about 3.1 s per image". The files give 3.12 s mean (Qwen72B,
   ovhcloud) and 3.47 s mean (gemma-3-4b-it, deepinfra). Both are network round trips to hosted models.

Also found, outside context.md: `evaluation/REAL_RESULTS.md` section 4 labels its per-class AUC column
"seed 42" (malicious insider 0.761 / 0.620 / 0.702), but the seed-42 file gives 0.744 / 0.615 / 0.674.
Handled in T1.2.

## 4. Results that went against the design

See `results/negative_results.md` (N-001 to N-010 so far).

## 5. Claims the paper may make / must not make

Filled in from T1.1 onward, each with its manifest key.

## 6. New or remaining limitations

To be filled as tasks complete.

## 7. Open questions and BLOCKED tasks

See `docs/OPEN_QUESTIONS.md`. No task is BLOCKED.

## 8. How to reproduce everything

Not yet available (task T1.3).
