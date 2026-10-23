# LOOP_STATE.md

After any restart or context compaction: re-read CLAUDE.md, this file and docs/FIXES_SUMMARY.md first.

- Iteration: 3
- Current task: T1.4
- Last evidence path: logs/reproduce_*.log, results/runs/repro_s42/
- Open gates: none yet (Q-001..Q-003 in OPEN_QUESTIONS.md are asked when their tasks are reached)
- Python for all project commands: `.venv/Scripts/python.exe` (PowerShell: `.venv\Scripts\python.exe`), with `PYTHONUTF8=1`

## Current plan (three lines)
- Goal: T1.4 regenerate the dataset for 10 data seeds (42, 7, 2024 + 7 fixed in config), retrain, evaluate; report mean and spread.
- Smallest change: evaluation/multiseed.py that loops generate+train into results/runs/data_seed_<s>/ and summarises from the manifest; seeds in evaluation/config/seeds.json.
- Verify: run twice for one seed identical; summary mean/sd hand-checked; reproduce stage added; check_numbers passes.

## Next action
Start T1.4.

## Status table

| Task | Priority | Status | Note |
|---|---|---|---|
| T0.1 | M | DONE | |
| T1.1 | M | DONE | |
| T1.2 | M | DONE | |
| T1.3 | M | DONE | |
| T1.4 | M | PENDING | |
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
