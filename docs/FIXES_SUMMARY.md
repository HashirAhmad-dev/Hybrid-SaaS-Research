# FIXES_SUMMARY.md

Human-readable report of the paper-v2 work. Updated at the end of every task.

## 1. Status

Phase 0 is complete. T1.1 is complete: every evaluation script now writes its numbers, with run id, seeds, date, git hash and library versions, into `results/manifest.json`, and `tools/check_numbers.py` checks quoted numbers against it. Work happens on branch `paper-v2`; the starting commit 2521134 is tagged
`baseline-pre-v2` and its outputs are preserved in `results/baseline_20261023/`. The environment is
recorded in `docs/ENVIRONMENT.md`. The headline numbers in context.md were checked against the metrics
files; five corrections are listed in section 3. No code has changed yet.

## 2. Task table

| Task | Status | What was wrong | What changed (files) | Reproduce | Before | After |
|---|---|---|---|---|---|---|
| T0.1 | DONE | No branch, no preserved baseline, no environment record, context.md unchecked | `docs/ENVIRONMENT.md`, `docs/LOOP_STATE.md`, `docs/DECISIONS.md`, `docs/OPEN_QUESTIONS.md`, `docs/FIXES_SUMMARY.md`, `results/negative_results.md`, `results/baseline_20261023/*`, `CLAUDE.md` | `git diff baseline-pre-v2` | n/a | Baseline frozen; 5 context.md corrections found |
| T1.1 | DONE | No single source of truth for numbers; nothing checked quoted numbers | `tools/manifest.py`, `tools/check_numbers.py`, `tools/ingest_baseline.py`, `results/manifest.json`, `results/claims/context_md_baseline.claims`; manifest hooks in `generate_sessions.py`, `train_and_evaluate.py`, `calibrate_sbrs.py`, `refresh_sbrs_columns.py`, `run_pipeline.py` | `python -m tools.ingest_baseline`; `python tools/check_numbers.py results/claims/context_md_baseline.claims` | n/a | 63/63 context.md numbers match the manifest (after the 5 corrections); a wrong value or missing key exits 1; repeat run of calibrate_sbrs gives identical manifest values |
| T1.2 | DONE | Stale docstring numbers (0.479 / 3.9%), PII module said "(simulated)" and labelled replayed demo records PaddleOCR/PaliGemma, README/DEPLOYMENT quoted unreproduced draft numbers (42.7%, 11.2%, 0.93, 0.91) and old bands 0.20/0.60, .env.example named a 7B model, REAL_RESULTS section 4 mixed 3-seed means with seed-42 labels; also a code bug: the 'paper doc bands' row applied 0.50/1.00 to SBRS at beta 2.5 | `backend/risk_orchestrator.py`, `backend/pii_pipeline.py`, `backend/schemas.py`, `README.md`, `DEPLOYMENT.md`, `.env.example`, `evaluation/REAL_RESULTS.md`, `evaluation/common.py`, `evaluation/train_and_evaluate.py`, `evaluation/refresh_sbrs_columns.py`, `evaluation/data/metrics.json`, `tools/ingest_baseline.py` (3-seed summary), `results/claims/*.claims` | `python tools/check_numbers.py results/claims/*.claims`; `python -m evaluation.refresh_sbrs_columns` | doc-bands row F1 0.131 (wrong beta) | doc-bands row F1 0.134 (beta 0.5, matches sbrs_calibration.json exactly); 131/131 claims in 3 claims files match; grep finds only historically labelled old numbers |
| T1.3 | DONE | No single command reproduced the results; no pinned versions; runs overwrote canonical files | `reproduce.ps1`, `reproduce.sh`, `requirements-lock.txt`, `README.md` (reproduce section), `--out-dir`/`--data-dir` options in `generate_sessions.py`, `train_and_evaluate.py`, `calibrate_sbrs.py`; `results/claims/reproduce_expected.claims`; `check_numbers.py` accepts a folder | `pwsh -File .\reproduce.ps1` | not reproducible by one command | Clean pwsh and bash runs both pass 161/161 claims; seed-42 data regenerates byte-identical (sha256 0519d04e...); retrained LSTM/forest artefacts byte-identical to the baseline; two runs give identical values on all 436 non-latency keys; runtime 0.8 min |
| T1.4 | DONE | Seeds varied only training on one dataset, so spreads ignored data randomness | `evaluation/multiseed.py`, `evaluation/config/seeds.json`, `results/multiseed_summary.{json,csv}`, `results/claims/multiseed.claims`, reproduce stage | `python -m evaluation.multiseed` (about 13 min) | seed 42 only: hybrid F1 0.629, IF 0.634, enforcement F1 0.475, malicious recall 0.020 | 10 datasets, mean ± sd: hybrid F1 0.635 ± 0.049, IF 0.622 ± 0.060, LSTM AUC 0.869 vs hybrid 0.821, enforcement F1 0.441 ± 0.060, malicious recall 0.029, alpha 0.00 to 0.80, recalibrated beta 2.0 to 8.0; rerun of seed 7 identical on 436 keys; ds42 equals the reproduced s42 |
| T1.5 | DONE | No tests for scoring, banding, metrics, matching or splits; tuning helpers had no guard against test rows | `tests/test_sbrs.py`, `tests/test_metrics.py`, `tests/test_matching.py`, `tests/test_selection.py`, `tests/test_splits.py`, `evaluation/selection.py` (guarded selectors), `evaluation/common.py` (`time_boundaries`), `train_and_evaluate.py` and `calibrate_sbrs.py` now call the guarded selectors; pytest stage in reproduce scripts | `python -m pytest -q tests` | 0 tests | 75 tests pass; every selector raises `TestSplitLeak` on non-validation rows; seed-42 manifest values unchanged on 401 keys after the rewiring |

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

## Gate records

### Phase 1 gate (2026-10-23)
- a. `python -m pytest -q tests`: 75 passed.
- b. `pwsh -NoProfile -File .\reproduce.ps1` from a clean shell (full, with the 10-dataset stage): exit 0 in 11.9 min, `check_numbers` 188/188 claims. First attempt failed on a transient Windows lock of `results/manifest.json` (WinError 5 in `os.replace`); `tools/manifest.py` now retries the replace. After the rerun, all 5041 non-latency manifest keys under `anomaly.*`, `sbrs.*`, `generation.*` are identical to the values before the run. Log: `logs/gate1_reproduce_full.log`.
- c. `git status`: only re-written run outputs (provenance timestamps, latency), the manifest, and the T2 drafts are pending. `.env` last modified 2026-07-09, never opened, never in git history (`git log --all -- .env` is empty).
- d. FIXES_SUMMARY has rows for T0.1 and T1.1 to T1.5.
- e. H-R4 / H-R5 scan:
  - All anomaly-track thresholds, alpha, the insider operating point, beta and the bands are now chosen by `evaluation/selection.py`, which raises on non-validation rows; `tests/test_selection.py` proves it and scans the scripts for unguarded tuning functions.
  - LSTM early stopping uses the validation next-step loss (no labels). Scaler, forest and memory banks are fitted on FIT; calibrators on CALIB. Test is scored once.
  - Known historical issue, not yet fixed: the PII cascade's calibrated tau (0.98) is reported on all 120 documents including the 20 calibration documents (context.md correction 3). Fixed in T3.4.
  - Unclear historical issue: `SBRS_RECALIBRATION.md` says an F1-maximising t_alert "was tried and rejected" because it permits 66 percent of threats, without saying on which split that was observed. The shipped bands do not depend on it (they are percentile rules fixed on validation), so no number moves; the wording must not be repeated in the paper as a test-free choice.
  - Disclosed peek: LOF neighbour grid widened after seeing seed-42 val and test AUC (D-008).
  - H-R5: the 10 data seeds were fixed in `evaluation/config/seeds.json` before any multi-seed result was seen and all 10 are reported. Every result that went against the design is in `results/negative_results.md` (N-001 to N-017). Latency values from the multi-seed run are marked as not quotable (D-010).
