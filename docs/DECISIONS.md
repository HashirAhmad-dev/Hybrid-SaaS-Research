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
