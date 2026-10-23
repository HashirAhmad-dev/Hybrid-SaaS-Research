# LOOP_STATE.md

After any restart or context compaction: re-read CLAUDE.md, this file and docs/FIXES_SUMMARY.md first.

- Iteration: 4
- Current task: T1.5
- Last evidence path: results/multiseed_summary.csv, logs/t1.4_rerun_seed7.log
- Open gates: none yet (Q-001..Q-003 in OPEN_QUESTIONS.md are asked when their tasks are reached)
- Python for all project commands: `.venv/Scripts/python.exe` (PowerShell: `.venv\Scripts\python.exe`), with `PYTHONUTF8=1`

## Current plan (three lines)
- Goal: T1.5 pytest for SBRS, metrics, matching, validation-only selection (H-R4), splits; wire selection.py into train/calibrate.
- Smallest change: tests/ (already drafted, 74 pass); replace inline selectors in train_and_evaluate.py and calibrate_sbrs.py with evaluation/selection.py calls that pass split labels.
- Verify: pytest; reproduce quick gives identical s42 numbers; selector guard tests fail on test rows.

## Next action
Start T1.5.

## Status table

| Task | Priority | Status | Note |
|---|---|---|---|
| T0.1 | M | DONE | |
| T1.1 | M | DONE | |
| T1.2 | M | DONE | |
| T1.3 | M | DONE | |
| T1.4 | M | DONE | |
| T1.5 | M | PENDING | |
| T2.1 | M | PENDING | |
| T2.2 | M | PENDING | |
| T2.3 | M | PENDING | |
| T2.4 | M | PENDING | |
| T2.5 | M | PENDING | |
| T2.6 | S | PENDING | gate G-DATA (Q-001) |
| T2.7 | M | PENDING | |
| T3.1 | M | PENDING | |
| T3.2 | M | PENDING | |
| T3.3 | M | PENDING | |
| T3.4 | M | PENDING | |
| T3.5 | M | PENDING | |
| T3.6 | M | PENDING | |
| T3.7 | C | PENDING | gate G-SPEND (Q-002) |
| T4.1 | M | PENDING | |
| T4.2 | M | PENDING | gate G-DOCS (Q-003) |
| T4.3 | M | PENDING | |
| T4.4 | M | PENDING | |
| T4.5 | M | PENDING | |
| T4.6 | C | PENDING | only if everything else is DONE |
