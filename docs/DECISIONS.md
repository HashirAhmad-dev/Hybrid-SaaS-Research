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
