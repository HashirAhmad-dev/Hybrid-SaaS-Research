# DECISIONS.md

One entry per non-obvious decision. Format: date, task, options, choice, reason.

## D-001 (2026-10-23, T0.1) CLAUDE.md
- Options: (a) leave CLAUDE.md absent; (b) copy docs/context.md to CLAUDE.md as context.md section 0 asks.
- Choice: (b). The root `context.md` is an untracked duplicate of `docs/context.md`; it is left untouched and uncommitted.
- Reason: context.md says to save it as CLAUDE.md. Copying is non-destructive.

## D-002 (2026-10-23, T0.1) Project virtual environment
- Options: (a) pip install into the system CPython 3.14; (b) a full fresh venv (re-downloads torch, spaCy model, EasyOCR); (c) a venv with `--system-site-packages`.
- Choice: (c) `.venv` (gitignored), created from CPython 3.14.4.
- Reason: H-R1/G-DESTRUCT forbid system-wide installs without approval. (c) adds packages such as pytest without touching the system interpreter and without multi-GB downloads. Exact versions go into `requirements-lock.txt` so a clean clone can rebuild a full venv.

## D-003 (2026-10-23, T0.1) CPU vs GPU for the LSTM
- Options: (a) install a CUDA torch build and train on the GPU; (b) keep the installed CPU torch.
- Choice: (b).
- Reason: The LSTM is small (hidden 128, about 12k training windows, 20 epochs). CPU training is repeatable run to run; cuDNN LSTM kernels are not bit-exact, which would break the determinism check the loop requires. Replacing torch would also change the environment that produced the baseline. Results files record `device: cpu`.

## D-004 (2026-10-23, T0.1) Branch and tag
- Branch `paper-v2` created from `main` at 2521134. Tag `baseline-pre-v2` points at 2521134. Baseline outputs copied to `results/baseline_20261023/` (JSON and markdown committed; CSVs and model artefacts under `large/` stay out of git, with SHA-256 sums committed).

## D-005 (2026-10-23, T1.2) Doc-bands comparison row
- Options: (a) keep `paper_doc_bands_alert_or_block` as computed (bands 0.50/1.00 on SBRS at beta 2.5); (b) compute it at the beta the doc bands were written for (0.5).
- Choice: (b), new constant `PAPER_DOC_BETA = 0.5` in `evaluation/common.py`, used by `train_and_evaluate.py` and `refresh_sbrs_columns.py`.
- Reason: the row is labelled as the documented old configuration. (a) matched no configuration that ever existed. After the fix the row equals `sbrs_calibration.json` `doc_beta0.5_bands0.50_1.00` exactly (tp 84, fp 1077, F1 0.1337). The old value stays in the baseline manifest keys.

## D-006 (2026-10-23, T1.2) Engine labels in the backend PII replay
- Options: (a) edit `hybridSaaS_events.json` to remove the PaddleOCR/PaliGemma labels; (b) keep the data file, and relabel at replay time.
- Choice: (b). `scan_event` reports `engine = "none (replayed demo record, no engine ran; the record says '...')"` and strips `_PaliGemma` / `_PaddleOCR` from branch labels.
- Reason: the data file is the user's demo data (no deletion or rewriting of user data). The replay output no longer claims an engine ran.

## D-007 (2026-10-23, T1.4) Seeds for independently generated datasets
- Options: vary only the training seed (old study); vary only the data seed; vary both.
- Choice: vary both, with the same integer, for 10 seeds fixed in `evaluation/config/seeds.json` before any result was seen: 42, 7, 2024, 1, 13, 99, 123, 314, 777, 1001. Each seed also gets its own validation-calibrated SBRS bands.
- Reason: the reviewers' question is whether the numbers survive a different draw of users and attacks; varying both is the deployment-like case. Seeds are never filtered (H-R5). Spread is the sample sd (ddof 1) across the 10 datasets.

## D-008 (2026-10-23, T2.1) LOF neighbour count
- Options: sklearn default k=20; a fixed large k; k chosen on validation.
- Choice: k chosen per run by validation AUC from {20, 50, 100, 200, 300, 500} (`selection.choose_by_val_auc`).
- Reason: a first seed-42 dry run at k=20 gave AUC about 0.5 on both val and test. Injected attack episodes inside the FIT period form small dense clusters, so small-k LOF treats attacks as locally normal. I looked at val and test AUC for k in {5, 20, 50, 100, 300} on seed 42 before fixing the grid; the choice itself is made on validation only. This peek is disclosed here.

## D-009 (2026-10-23, T2.1) AUC on calibrated vs raw scores
- The deployed scores are RobustCalibrator outputs, clipped to [0, 1]; about half of all rows sit at exactly 0. AUC on clipped scores differs slightly from AUC on raw scores (seed 42 Isolation Forest: 0.795 clipped vs 0.786 raw).
- Choice: the ablation reports AUC on the calibrated (deployed) scores as the primary column, so fused and single detectors are compared on the same footing, and adds `auc_raw_unclipped` for single detectors as a labelled secondary column.

## D-010 (2026-10-23, T1.4) Latency inside the multi-seed run is not a clean measurement
- While the 10-seed run executed, I ran other CPU-heavy diagnostics on the same laptop. The per-seed `latency.mean_ms` values recorded during that run are therefore contaminated by concurrent load and must not be quoted. Tier 1 latency is measured separately and under controlled conditions in T3.6.

## D-011 (2026-10-23, T2.6) CERT feasibility
- Checked (no data download): figshare record 12841247, licence CC BY 4.0. Release archives: r1 0.09 GB, r2 8.66 GB, r3.1 4.25 GB, r3.2 4.29 GB, r4.1 5.02 GB, r4.2 4.82 GB, r5.x about 11 GB, r6.x 20 to 24 GB. The answer key (1.25 MB) lists insider scenarios for r3.x and later only, so every usable release exceeds the 2 GB G-DATA limit.
- Measured throughput from this machine to figshare: the 1.25 MB answer file arrived truncated twice (about 0.5 MB in 10 minutes). A 4 to 5 GB release is not feasible over this link even with approval.
- Choice: T2.6 SKIPPED with this reason unless the user approves (Q-001) and fetches a release by another route (for example a browser download into `external/cert/`). CERT is described as future external validation in the threats-to-validity input.

## D-012 (2026-10-23, T3.3) Which local VLMs, given the network
- Measured download throughput to Hugging Face from this laptop: 80 to 200 KB/s, and the LM Studio downloader timed out on the first 3.27 GB model. Free disk: 13 GB.
- Options: download Qwen2.5-VL-3B, gemma-3-4b-it and a 7B in parallel; or one model at a time with a resumable downloader.
- Choice: Qwen2.5-VL-3B-Instruct Q4_K_M plus its f16 vision projector first (3.27 GB, closest to the paper's 3B design), fetched with `curl -C -` in a retry loop into the LM Studio models folder. gemma-3-4b-it Q4_K_M (3.34 GB) second if time allows. A 7B model is skipped: about 6 GB with projector does not fit the 6 GB VRAM next to the display and would take about 8 hours to download here. PaliGemma GGUF builds are not in the lmstudio-community catalogue and the original weights are gated; not attempted.

## D-013 (2026-10-23, T3.1) FUNSD real-scan subset
- Checked the FUNSD terms page: use is "solely for non-commercial, research and educational purposes", the user must be 18 or older and accept the terms, and the images carry their own copyright (RVL-CDIP). FUNSD labels are question/answer/header/other, not PII types, so a PII gold list would have to be derived heuristically and would be incomplete.
- Choice: not downloaded. Accepting licence terms is the user's call (Q-004). Default: skip; the threats-to-validity input states that no real scans were evaluated.

## D-014 (2026-10-23, T3.1) Corpus v2 is the main PII set
- 360 new documents (3 modalities x 3 difficulty levels x 40), seed 2610, 1428 gold entities, 49 PII-free documents, near-miss strings at medium and hard. The v1 corpus (120 documents) is included in the same ground-truth file as subset "v1" and reported separately. A fixed 25/75 calib/eval split, stratified by subset x modality x difficulty, is used for every PII selection (tau, router).

## D-015 (2026-10-23, T3.2) EasyOCR timings
- The EasyOCR pass over the 320 corpus images ran partly while other jobs (drift, fusion, a package install) used the CPU, and was resumed after an out-of-memory stop. Mean 3.46 s per image (3.74 s on v2 eval images) is therefore an upper estimate for this laptop. It is used only as the cost axis of the cascade Pareto curve; Tier 2 latency is measured separately in T3.6.

## D-016 (2026-10-23, T4.3) Figure tool
- Options: Graphviz, draw.io XML, TikZ. No Graphviz, LaTeX or draw.io was installed; a system-wide install needs gate G-DESTRUCT.
- Choice: Graphviz. The portable Windows zip (Graphviz 12.2.1, 9.6 MB) was unpacked into `external/graphviz/` (gitignored), not installed. `tools/render_figures.py` finds `dot` on PATH or there. Editable source: `figures/architecture.dot`.

## D-017 (2026-10-23, T3.2) PaddleOCR runtime
- paddlepaddle 3.3.1 (CPU) with paddleocr 3.4.0 in `.venv-paddle` (CPython 3.12.13 via uv). The default oneDNN path fails on Windows with "ConvertPirAttribute2RuntimeAttribute not support"; `enable_mkldnn=False` works but runs at about 14 s per image on this CPU. No GPU paddle build was installed (about 1 GB more over a slow link); PaddleOCR GPU latency is therefore not measured.

## D-018 (2026-10-23, T4.1) Enforcement shipped in the backend
- Options: keep the multiplicative SBRS (paper design); switch to the form that measured best at equal budget (gated, T2.5).
- Choice: gated fusion with dataset-42 validation settings (beta 2.5, tau_A 0.7507, t_alert 1.2238, t_block 1.8437), plus a per-user CUSUM drift alarm (k 1.0, h 8.0) that can only raise PERMIT to ALERT. The multiplicative `compute_sbrs` stays available and is still reported (`sbrs_action`) so the old behaviour remains reproducible (H-R10).
- Reason: gated fusion caught more threats at the same benign budget on 10 datasets and is the only form that handles the reviewer's low-S/high-A case; the drift alarm costs FPR, so it routes to review, not auto-block. Values come from `backend/config/final_config.json`, generated from the manifest; `tests/test_final_config.py` checks both.

## D-019 (2026-10-24, T3.2) Presidio tie-break made deterministic
- Found by the determinism check: two Presidio runs on identical text disagreed on one v2 document (a password recognised as PASSWORD in one run and as LOCATION/ADDRESS in the other). Both results had the same span and score; `_dedupe_overlaps` kept whichever came first, and Presidio's recogniser order varies between processes.
- Fix: `evaluation/pii_v2.dedupe_deterministic` breaks ties by longer span, then entity-type name. Two consecutive runs now give identical entities on all 160 text and 640 OCR transcripts. The v1 helper in `run_pipeline.py` is unchanged so the old numbers stay reproducible as they were; the v1 subset inside the v2 scorer uses the new tie-break.
- Effect: the deterministic result equals the first run (v2 Branch 1 F1 0.7275 / 0.7686), so the T3.5 numbers already recorded stand.

## D-020 (2026-10-24, user instruction) Large models and datasets go to D:, not skipped
- User instruction: low space on C: must not reduce project quality; large models or datasets go to D: or G: with the tools pointed there.
- Done: `D:\ai-models\lmstudio\lmstudio-community\{gemma-3-4b-it-GGUF, Qwen2.5-VL-7B-Instruct-GGUF}` hold the new VLM downloads. LM Studio has no models-folder setting in its config files, so each repo folder is linked into `%USERPROFILE%\.lmstudio\models\lmstudio-community\` with an NTFS directory junction (`mklink /J`, no admin, removable without touching the data). Qwen2.5-VL-3B stays on C: (download already 64 percent done; 2 GB fits).
- Datasets: CERT r4.2 (4.82 GB, CC BY 4.0) plus answers, README and checksums go to `D:\datasets\cert\` (outside the repo, so never committed). This reverses the size reason in D-011; T2.6 is reopened. The second reason in D-011 (slow figshare link) is retested with the append-only downloader `tools/fetch_resumable.py`.
- The 7B VLM is added back to T3.3 (D-012 had skipped it for disk and time). Whether it fits 6 GB VRAM is measured, not assumed.
- Not changed by this instruction: FUNSD still needs the user to accept its licence terms (Q-004); hosted paid calls still need G-SPEND (Q-002).

## D-021 (2026-10-24, T3.1, user answer to Q-004) FUNSD real-scan subset
- The user accepted the FUNSD terms (non-commercial research and education use) on 2026-10-24 and asked for the download to D:. Source: https://guillaumejaume.github.io/FUNSD/dataset.zip (16.8 MB), stored at `D:\datasets\funsd\` (outside the repo; images are RVL-CDIP documents with their own copyright and are never committed).
- FUNSD labels are header / question / answer / other with question-to-answer links, not PII types. Plan: derive a PII gold list from linked question-answer pairs whose question text names a PII field (name, phone, fax, address, date of birth, e-mail), with the answer text as the value. This gold is partial: PII in free text or unlinked fields is missed, so precision on FUNSD is a lower bound and recall is measured only against the derived fields. The subset is reported separately and labelled as such; it never enters the v2 main-set numbers.
- CERT r4.2: the first download attempt failed with HTTP 403. Cause: the figshare redirect was resolved with a HEAD request, and the signed S3 URL is signed for that method. `tools/fetch_resumable.py --resolve-redirect` now resolves with GET each attempt and retries the size probe (the link drops DNS and connections intermittently).
- (D-021 addendum, before any model was scored on FUNSD) Derived gold: 199 forms, 438 entities (PERSON 365, PHONE 63, ADDRESS 10), 90 forms with no derived PII field. Comma-separated name lists are split into one PERSON per name. Visible noise kept as is: "to"/"from" answers that are departments, job titles or postal addresses. Rules are in `evaluation/funsd_subset.py` and were fixed before any model output on FUNSD existed.

## D-022 (2026-10-24, T3.1/T3.3) PII calib/eval split restored after FUNSD was added
- Found by check_numbers: after FUNSD was added to the ground truth, `assign_split` processed the FUNSD stratum first with the shared `random.Random(2610)`, which shifted every later shuffle and moved v1/v2 documents between calib and eval. 66 previously verified claims changed. This broke the rule that a split is never changed.
- Fix: FUNSD strata are shuffled after all v1/v2 strata (`evaluation/pii_v2.assign_split`). The v1/v2 split is identical to the pre-FUNSD split (480 of 480 documents checked against the code at 15a955a~1), and `tests/test_splits.py::test_pii_split_unchanged_by_funsd` guards it. All earlier claims match again.
- FUNSD and VLM numbers recorded before the fix (commits 2afa0b5 and 6433178, N-044 to N-047) were computed on the shifted split and are replaced by the corrected values. No result was chosen by looking at either version; the rule was fixed by the invariant, not by the numbers.
- LM Studio settings for the local VLM runs: `--parallel 1`, context 4096, model unloaded and reloaded every 100 images, because the server's RAM grew to 8.4 GB with the default 4 parallel slots and the background jobs were killed for low memory.

## D-023 (2026-10-24, T4.1) Deployed tau_ocr and Branch 3 in the proxy
- The backend reads tau_ocr from `backend/config/final_config.json` (`pii.tau_ocr_deployed`), generated from the manifest key `pii2.v2.cascade.easyocr_cpu.gemma-3-4b-it.calib_tau` (0.95, chosen on calib documents). EasyOCR because that is the OCR engine of the proxy's Tier 2; gemma-3-4b-it because it is the best local VLM (T3.3). The paper's 0.85 is used only if the generated config is missing.
- Tier 2 now calls Branch 3 (local LM Studio VLM, model id from `HYBRIDSAAS_VLM_MODEL`, default gemma-3-4b-it) when OCR confidence is below tau_ocr. Before this change Tier 2 always used OCR+Presidio and the VLM branch existed only in the offline evaluation.
- If the VLM is unreachable or its answer cannot be parsed, the held upload is quarantined, not released (fail closed). Tested in `tests/test_final_config.py`.

## D-024 (2026-10-25, T2.6) CERT r4.2 run settings
- Data: `D:/datasets/cert/r4.2.tar.bz2` (4,824,287,500 bytes), SHA-256 586446b0...0122556c, which matches `CHECKSUMS-sha256.txt`. Extracted to `D:/datasets/cert/extract/r4.2`.
- Mapping result (`results/runs/cert_r4.2/data/generation_config.json`): 200 users (70 insiders, 130 normals drawn with seed 42), 12,000 hours, 590,482 active user-hours, 4,358 positive hours. Test split: 330 positive hours from 7 insiders (scenario 2: 6 episodes, 324 hours; scenario 3: 1 episode, 6 hours). Scenario 1 has no test positives, so no test number is reported for it.
- The scripts used to hard-code our four generator classes. `evaluation/common.observed_classes` now returns the generator classes for our data and the labels actually present otherwise. Old runs give the same output (tests pass).
- The insider-oriented operating point and the drift (k, h) choice target `cert_scenario_2` on validation. Reason: scenario 2 (data theft over weeks before leaving) is the slow-drift case that our `malicious_insider` class models, and it is the only scenario with enough validation episodes (11). This was fixed before any CERT model output existed.
- LSTM training uses a random 100,000-window subsample of FIT windows (`--max-fit-windows 100000`, seed 42), because the full FIT set does not fit the CPU time budget. Memory banks and Isolation Forest are fitted as usual.
- CERT is reported in its own table, labelled as a second synthetic benchmark, and never pooled with our datasets. SBRS enforcement is not evaluated on CERT (no PII payloads; S is constant).
- Validation loss on CERT is computed in batches of 4,096 because a single pass over its 360,000 validation windows needed 19 GB. The mean is the same, and a test checks this. Datasets with at most 50,000 validation windows keep the original single pass, so our earlier runs are unaffected.

## D-025 (2026-11-02, T3.3) One Qwen2.5-VL-7B timing re-measured after laptop sleep
- Problem: the laptop slept from 03:49 to 19:45 while image V2-0351 was being processed. Its cached time was 57,332 s, which is the sleep, not inference. It raised the v2 mean from about 36 s to 354 s per image and distorted the cascade cost axis.
- Choice: the original cache file was kept unchanged in `evaluation/data/pii_v2/vlm_cache_suspended/`, and only that image was sent again with the same model, prompt, temperature 0 and seed 0. The new answer is byte-identical to the old one (same raw text, same entities), and the new time is 37.3 s. Scoring was then rerun.
- Only timing changed. No accuracy number moved, and no other image was re-run.

## D-026 (2026-11-02, Phase 3 gate) Cache-only VLM reruns keep the measured GPU peak
- Problem: checking the LM Studio namespaced ids, `pii_v2 vlm --model gemma-3-4b-it` answered all 519 images from the cache, but still overwrote the recorded GPU peak of the real run (5,976 MiB) with the idle reading of that run (4,284 MiB). The gate comparison found this as the only changed non-latency value.
- Choice: `stage_vlm` now keeps the earlier peak when no image was sent to the model. The gemma file was restored to the value recorded in the manifest before the gate (`pii2.v2.vlm.gemma-3-4b-it.gpu_peak_mib` = 5976, run `pii_v2_score-20261102T180205Z`). The overwritten file is kept in `evaluation/data/pii_v2/vlm_cache_suspended/`. No accuracy value was affected.

## D-027 (2026-11-02, T2.6 follow-up) CERT richer-features experiment, fixed before any result
- Question: is detection on CERT limited by the six mapped features or by the detector? (FIXES_SUMMARY section 5 suggests the features.)
- Data: the same 200 users, hour grid, labels and 70/15/15 splits as `results/runs/cert_r4.2/data/sessions_raw.csv`. Scored rows: active hours with at least 23 earlier hours (the ablation's rule).
- Feature sets. BASE: the six mapped features. RICH: BASE plus 18 generic per-user-hour counts from the raw logs: logons, logoffs, distinct PCs, PCs never used before by the user, device connects, files copied, distinct file extensions copied, executable or archive files copied (.exe, .zip), e-mails sent, external recipients, recipients never mailed before, total e-mail size, attachments, e-mails with an attachment to an external recipient, web visits, distinct web domains, web domains never visited before, weekend flag. "Never before" is causal: first appearance in the user's own history up to that hour. No URL keyword lists and no content fields are used. The features were chosen with knowledge of CERT's public scenario descriptions (USB copying, job sites, external mail); they are generic DLP signals, but this knowledge is disclosed.
- Detectors, identical settings for both sets: Isolation Forest (200 trees, contamination auto, seed 42, StandardScaler, both fitted on FIT active hours, counts log1p-transformed); per-user z-score (max absolute z against the user's FIT active-hour mean and sd, sd floor 0.1, clip 10); two supervised probes as upper bounds, logistic regression and histogram gradient boosting (seed 42), trained with labels on TRAIN on the per-user z features plus their mean over the previous 8 active hours.
- Every threshold is chosen on validation (`selection.threshold_max_f1`). Reported on test: AUC, average precision, F1, precision, recall, FPR, scenario 2 episode recall. Paired user-level bootstrap (2,000 resamples, seed 20261102, insiders and non-insiders resampled separately) for the AUC difference RICH minus BASE.
- The LSTM is not retrained on RICH (CPU cost on CERT is several hours). The BASE Isolation Forest is a refit and is compared with the T2.6 value as a check.
- All results are reported whatever their direction (H-R5).

## D-028 (2026-11-03) Supervised probes on the 10 generated datasets, fixed before any result
- Question: does the CERT finding (N-062: a supervised model on the same features beats every unsupervised detector) hold on our own generator, and does it fix slow malicious-insider drift?
- Data: the 10 datasets of T1.4 (`evaluation/config/seeds.json`), `results/runs/data_seed_<s>/data/sessions_raw.csv`, active hours with at least 23 earlier hours (the ablation's rows). Only the six engine features exist here, so there is no RICH set.
- Detectors, settings copied from D-027 (`evaluation/cert_rich.py` helpers): logistic regression and histogram gradient boosting (seed 42, class_weight balanced) trained with labels on TRAIN on per-user z features plus their mean over the previous 8 active hours. Isolation Forest and per-user z-score refits as the same-pipeline unsupervised reference. The weighted hybrid's per-dataset values are read from the T2.1 manifest keys (`ablation.ds<s>.hybrid_weighted.*`).
- Thresholds on validation (max F1, 4,001 validation quantiles). Test: AUC, AP, F1, precision, recall, FPR, benign-burst flag rate, per-class AUC and episode recall. Summary: mean and sd over the 10 datasets, and the number of datasets where boosting beats the hybrid.
- Recorded alongside: how many test attack episodes share a user with a TRAIN attack episode, because a supervised model can learn a user's own attack pattern.
- All 10 datasets are reported whatever the outcome (H-R5).

## D-029 (2026-11-03) Label learning curve, fixed before any result
- Question: how many labelled incidents does the supervised layer of D-028 need before it beats the unsupervised detectors?
- Data and features: the 10 datasets and probe inputs of D-028. Each TRAIN split holds 143 attack episodes.
- Labels: k labelled TRAIN episodes, k in {1, 3, 5, 10, 20, 50, all}, drawn uniformly at random without replacement from all TRAIN episodes, 5 independent draws per k and dataset (draw seed = 1000 x dataset seed + 10 x k + draw; for k = all one draw). The hours of the k chosen episodes are positives. Every other TRAIN hour, including hours of attack episodes not chosen, is treated as benign, as in a deployment where only confirmed incidents carry labels.
- Models: logistic regression and gradient boosting as in D-027 and D-028.
- Operating point without labels: the alert threshold is the 99th percentile of the model's scores on all VALIDATION hours (a 1 percent alert budget), so no validation label is used. The unsupervised Isolation Forest refit (k = 0) gets the same rule as the baseline.
- Reported on test: AUC; precision, recall, F1 and FPR at the 1 percent budget; malicious-insider AUC and episode recall; whether the k draws contained a malicious-insider episode. Mean over draws, then mean and sd over the 10 datasets.
- All draws and datasets are reported (H-R5).
- Amendment (before any result was produced): with k = 1 a chosen episode can have a single positive hour, and gradient boosting's automatic early stopping (a stratified 10 percent hold-out) then fails. For draws with fewer than 2 positive hours early stopping is switched off; the number of such draws is recorded per k (`draws_without_early_stopping`).
- Amendment 2 (added after the 1 percent results were seen, and labelled as such): the 1 percent budget is below the share of attack hours in test (about 4 percent), so it caps recall near 0.25 for every model. The same curve is also reported at a 5 percent budget (`--budget-pctl 95`, keys `labelcurve_b5.*`). Both are reported; neither replaces the other.

## D-030 (2026-11-03, F6) Difficulty sweep on all 10 data seeds
- Diagnosis of "overlap 0.5 has almost no effect", from the existing 3-seed cells: the look-alike episodes are generated and score like attacks (dataset 42, intensity 1.0, test: mean hybrid score 0.483 on 49 look-alike hours, 0.456 on 96 attack hours, 0.090 on other negatives). They are only about 2 percent of test negatives, so AUC, which averages over all negatives, hardly moves (hybrid 0.839 to 0.834); flag-level metrics do move (hybrid F1 0.614 to 0.510, FPR 0.001 to 0.013). The paper must report F1, precision and FPR for the overlap condition, not AUC alone.
- Rerun: the same grid (5 intensities x 2 overlaps) on all 10 seeds of `evaluation/config/seeds.json`, `python -m evaluation.difficulty_sweep --seeds 42 7 2024 1 13 99 123 314 777 1001`. New cells only; the 3-seed cells are reused. Outputs `results/sweep/*_10seeds.*`, manifest `sweep.summary10.*`; the 3-seed record (T2.3) is unchanged. Precision is added to the summary metrics.
