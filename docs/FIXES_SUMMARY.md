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
| T2.1 | DONE | No ablation; LSTM-only and IF-only were scored at the hybrid's threshold, not their own | `evaluation/ablation.py` (9 detectors and fusions, val-chosen thresholds, recomputation checked against the trained runs to 1e-4), `evaluation/ablation_report.py`, `results/ablation/ablation_table.{csv,tex}`, `results/ablation/ablation_auc_f1.{pdf,svg}`, `evaluation/selection.py` (`choose_by_val_auc`), `results/claims/ablation.claims` | `python -m evaluation.ablation; python -m evaluation.ablation_report` | seed 42: hybrid F1 0.629 vs IF 0.634 at one shared threshold | 10 datasets: AUC LSTM 0.869, z-score 0.849, hybrid-max 0.855, hybrid-weighted 0.821, IF 0.779, LOF 0.779, EWMA 0.612; F1 hybrid-weighted 0.629, IF 0.626, hybrid-max 0.605, z-score 0.554, LSTM 0.528; rerun identical |
| T2.2 | DONE | Wilson intervals treated correlated windows as independent; no paired comparisons; no confusion matrices | `evaluation/bootstrap_stats.py` (two-stage cluster bootstrap: users, then attack episodes; 10000 resamples; seed 20261023; metric averaged over 10 datasets per replicate; paired differences vs hybrid), `tests/test_bootstrap.py`, `results/stats/{bootstrap_summary.json,bootstrap_intervals.csv,paired_vs_hybrid.csv,confusion_hybrid_by_class.csv}`, `results/claims/stats.claims` | `python -m evaluation.bootstrap_stats` (about 35 min) | seed 42 Wilson only: malicious recall 0.020 [0.003, 0.103] | hybrid F1 0.629 [0.564, 0.702]; AUC 0.821 [0.794, 0.865]; hybrid minus IF F1 0.003 [-0.013, 0.020]; hybrid minus LSTM AUC -0.048 [.., -0.024]; Wilson kept as secondary (dataset 42); two 300-resample runs identical |
| T2.3 | DONE | No evidence on how detection depends on attack strength; data too easy (three classes AUC about 1.0) | `evaluation/generate_sessions.py` (`--intensity`, `--benign-overlap`; defaults byte-identical, extra randomness from a separate stream), `evaluation/difficulty_sweep.py`, `tests/test_generator_defaults.py`, `results/sweep/{sweep_summary.csv,detection_vs_intensity.pdf,svg}`, `results/claims/sweep.claims` | `python -m evaluation.difficulty_sweep` (about 45 min) | only intensity 1.0 | 5 intensities x 2 overlaps x 3 seeds: AUC at intensity 0.25: hybrid 0.739, IF 0.728, LSTM 0.715; at 1.5: LSTM 0.895, hybrid 0.865, IF 0.820; malicious-insider AUC at 0.25 is about 0.5 for every detector; default cell identical to T2.1 |
| T2.4 | DONE | Slow insider drift undetected (episode recall 0.133 across 10 datasets); reviewer 4 asked for a concrete fix | `evaluation/drift_detector.py` (two-sided CUSUM and Page-Hinkley on per-user personal z over active hours; k, h chosen on validation for max malicious episode recall at <=1 percent validation false-alarm rate; supervised logistic probe as upper bound), `evaluation/selection.py` (`choose_drift_params`), `tests/test_drift.py`, `results/drift/drift_summary.csv`, `results/claims/drift.claims` | `python -m evaluation.drift_detector` (about 2 min) | hybrid malicious episode recall 0.133 | hybrid OR CUSUM: malicious episode recall 0.567, median time to detect 8.9 h, FPR 0.25 -> 0.80 percent, F1 0.635 -> 0.619, burst false alarms 20 percent; supervised probe malicious AUC 0.870; rerun identical |
| T2.5 | DONE | Multiplicative SBRS never compared with alternatives; reviewer 2's low-S/high-A case unmeasured | `evaluation/sbrs_fusion.py` (5 forms, same benign budget: ALERT at benign val p95, BLOCK at p99.5; beta, w on val; logistic fitted on train), `results/sbrs_fusion/{fusion_summary.csv,fusion_corners_seed42.csv}`, `results/claims/fusion.claims` | `python -m evaluation.sbrs_fusion` | only multiplicative, seed 42: recall 0.604 | 10 datasets at equal budget: recall gated 0.642, additive 0.630, logistic 0.627, multiplicative 0.589, max 0.320; low-S/high-A threats escalated: multiplicative 1/35, gated 35/35; burst flag multiplicative 0, gated 1.5 percent; rerun identical |
| T2.7 | DONE | Thresholds appeared without names; three operating points mixed in prose | `evaluation/operating_points.py`, `results/operating_points/operating_points.{csv,tex}`, `results/claims/oppoints.claims` | `python -m evaluation.operating_points` | seed-42 numbers in three places | One labelled table, 10 datasets: F1-optimal flag R 0.494 FPR 0.25 percent F1 0.635; insider-oriented R 0.663 FPR 5.0 percent F1 0.471; SBRS shipped bands R 0.574 FPR 4.4 percent F1 0.441; BLOCK only R 0.345 FPR 0.55 percent; per-dataset bands F1 0.438; hybrid OR CUSUM R 0.532 FPR 0.8 percent F1 0.619. Shipped-band F1 matches the T1.4 key computed by another path |
| T3.5 | DONE | Presidio cannot find street addresses and misses most Mastercard numbers | `evaluation/pii_v2.py` (`build_analyzer_plus`: Mastercard 51-55 and 2221-2720 with Luhn check, street-address pattern), `tests/test_recognisers.py`, `results/claims/pii_v2_branch1_ocr.claims` | `python -m evaluation.pii_v2 presidio; python -m evaluation.pii_v2 score` | v2 eval text: ADDRESS recall 0.05, CREDIT_CARD recall 0.80, F1 0.728 | ADDRESS recall 0.47 (precision 0.35), CREDIT_CARD recall 1.00 (precision 1.00), F1 0.769; FPs on PII-free docs 49 -> 50; OCR+Presidio F1 0.486 -> 0.516 |
| T3.6 | DONE | Paper promised 300 ms end to end; only anomaly scoring (17 ms) was measured, outside the proxy | `backend/tier1.py` (Tier 1 inline scorer with per-stage timing; Tier 2 hold-then-release job queue), `/tier1/score`, `/tier2/submit`, `/tier2/{job}` in `backend/main.py`, `evaluation/tier_latency.py`, `results/latency/tier_latency.json`, `results/claims/latency.claims`, README section | `python -m evaluation.tier_latency` (about 3 min) | 300 ms goal, unmeasured | Tier 1 in proxy over HTTP: p50 33.7 ms, p95 40.5, p99 44.6 (n=1000 warm; server: PII 13.7 ms, anomaly 17.9 ms at p50); cold first request about 9 s; Tier 2 hold p50 3.4 s, p95 5.3 s (n=20). Latency varies run to run; not part of the bit-for-bit check |

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

All values are means over the 10 independently generated datasets unless marked. Every value is in a claims file under `results/claims/`, and `docs/CLAIM_EVIDENCE.md` lists the script and run for each.

### May make (with evidence)

| Claim | Evidence |
|---|---|
| A rate-only EWMA baseline is weak on this data (flag F1 0.106) and flags 66.8 percent of benign bursts; the hybrid flags 1.5 percent. | `results/claims/multiseed.claims` |
| The hybrid's flag F1 (0.629, 95 percent cluster-bootstrap CI 0.564 to 0.702) is significantly higher than LSTM alone (+0.100), per-user z-score (+0.075), LOF (+0.179) and EWMA (+0.518). | `results/claims/stats.claims` |
| The hybrid's F1 is statistically indistinguishable from Isolation Forest alone (difference 0.003, CI -0.013 to 0.020). Fusion adds average precision, not F1. | `results/claims/stats.claims`, `ablation.claims` |
| Slow insider drift is the hard case: at the F1-optimal point the hybrid finds 13 percent of malicious-insider episodes. A dedicated CUSUM detector beside it raises this to 57 percent, median 8.9 hours to detection, at a false-positive rate of 0.8 percent instead of 0.25 percent. | `results/claims/drift.claims` |
| At an equal benign alert budget, gated fusion (escalate when A is high regardless of S) catches more threats than the multiplicative SBRS (0.642 vs 0.589) and escalates all 35 low-sensitivity, high-anomaly threats, against 1 for the multiplicative form. | `results/claims/fusion.claims` |
| Detection degrades smoothly as attacks get quieter; at intensity 0.25 all detectors sit at AUC 0.72 to 0.74 and none separates slow drift (AUC about 0.5). | `results/claims/sweep.claims` |
| Text-only DLP sees nothing in images; Presidio on clean text reaches F1 0.769 on the harder v2 corpus with the two added recognisers (0.728 without). | `results/claims/pii_v2_branch1_ocr.claims` |
| Adding a Mastercard-range recogniser with a Luhn check closes Presidio's card gap (recall 0.80 to 1.00, precision 1.00). | same |
| Every threshold, weight and band is chosen on validation data; selection code rejects test rows (unit-tested). | `evaluation/selection.py`, `tests/test_selection.py` |
| Results reproduce bit-for-bit with one command. | `reproduce.ps1`, gate records below |

### Must not make

- That the LSTM + Isolation Forest hybrid outperforms its components overall. It does not beat IF on F1 and is below the LSTM, the z-score and max fusion on AUC (N-018 to N-024).
- That the multiplicative SBRS is the best fusion, or that low content sensitivity safely suppresses alerts (N-033, N-034).
- That benign bursts are suppressed on every dataset (one dataset: 14.8 percent, N-016).
- Any single-dataset number (seed 42) as the headline; use the 10-dataset mean with its interval.
- The old draft figures: EWMA FPR 42.7 percent vs hybrid 11.2 percent, SBRS F1 0.93, PII coverage 0.91, 279 ms end to end.
- "Real-time 300 ms end to end". Replace with the measured Tier 1 budget (T3.6).
- That PaddleOCR, PaliGemma-3B or an on-box VLM was evaluated, unless T3.2 / T3.3 results exist in the manifest.
- That federated learning, differential privacy or a usability study was done.
- That "existing DLP ignores behaviour" (Microsoft Purview Adaptive Protection uses insider-risk levels in DLP).
- That OCR confidence never ranks difficulty: on v2 it does (AUC 0.884); on v1 it did not.
- That the data are realistic enterprise traffic or real handwriting. All data are synthetic; handwriting is font-rendered.
- The value beta = 2.5 as a general constant: the validation knee ranges from 2.0 to 8.0 across datasets (N-017).

## 6. New or remaining limitations

- All behavioural data and all PII documents are synthetic (Faker, font-rendered handwriting). No real scans were evaluated (FUNSD not downloaded, Q-004). CERT external validation was not feasible (T2.6 SKIPPED, D-011).
- Each test split holds about 6 malicious-insider episodes, so per-dataset episode recall moves in steps of 1/6; the 10-dataset mean and the cluster bootstrap carry this uncertainty.
- The attack generator's "slow drift" spans about 12 hours, not days.
- The CUSUM drift detector fires on 20 percent of benign-burst hours.
- The street-address recogniser has low precision (0.35).
- LSTM training uses CPU torch; GPU training was not used (D-003).
- The LOF neighbour grid was widened after looking at seed-42 validation and test AUC (D-008, disclosed).
- Network bandwidth on this laptop (50 to 300 KB/s to Hugging Face and figshare) limited which local VLMs could be downloaded (D-012).

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

### Phase 2 gate (2026-10-23)
- a. pytest: 95 passed.
- b. `pwsh -NoProfile -File .\reproduce.ps1` (full): exit 0 in 20.1 min; `check_numbers` 360/360. All 34,681 non-latency manifest keys under `anomaly`, `sbrs`, `generation`, `ablation`, `stats`, `sweep`, `drift`, `fusion`, `oppoints` identical to the snapshot taken before the run (`logs/manifest_before_gate2.json`). Caveat: the difficulty-sweep stage reuses cells already recorded in the manifest and only rebuilds the summary and figure; its cells were reproduced independently by the check that the default cell equals the T2.1 ablation exactly.
- c. git status: only run outputs (timestamps, latency) and Phase 3 work pending; `.env` untouched.
- d. FIXES_SUMMARY rows exist for T2.1 to T2.5 and T2.7; T2.6 SKIPPED with reason (D-011).
- e. H-R4 scan: T2.1 thresholds by `threshold_max_f1` / `threshold_at_fpr` on validation; LOF k by validation AUC (grid peek disclosed, D-008); calibrators and ECDFs on CALIB. T2.2 resamples test rows only with thresholds fixed from validation. T2.3 grid fixed before results. T2.4 (k, h) by `choose_drift_params` on validation; probe trained on train, threshold on validation. T2.5 beta and w on validation, logistic fitted on train, bands from benign validation percentiles. Recall at 1 and 5 percent FPR read off the test ROC curve is labelled as a curve summary, not a tuned threshold. H-R5: every dataset and every sweep cell reported; N-018 to N-035 added.
