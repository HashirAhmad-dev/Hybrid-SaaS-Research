# LOOP_STATE.md

After any restart or context compaction: re-read CLAUDE.md, this file and docs/FIXES_SUMMARY.md first.

- Iteration: 7
- Current task: T2.3
- Last evidence path: results/stats/
- Open gates: Q-001 (CERT, default skip applied). Phase 1 gate PASSED 2026-10-23.
- Python for all project commands: `.venv/Scripts/python.exe` (PowerShell: `.venv\Scripts\python.exe`), with `PYTHONUTF8=1`

## Current plan (three lines)
- Goal: T2.3 difficulty sweep (5 intensities x 2 benign overlaps x 3 seeds), plot detection vs intensity.
- Smallest change: generator knobs (done, defaults byte-identical) + evaluation/difficulty_sweep.py.
- Verify: tests/test_generator_defaults.py; one cell rerun identical; figure check.

## Next action
Start T2.3.

## Status table

| Task | Priority | Status | Note |
|---|---|---|---|
| T0.1 | M | DONE | |
| T1.1 | M | DONE | |
| T1.2 | M | DONE | |
| T1.3 | M | DONE | |
| T1.4 | M | DONE | |
| T1.5 | M | DONE | |
| T2.1 | M | DONE | |
| T2.2 | M | DONE | |
| T2.3 | M | PENDING | |
| T2.4 | M | PENDING | |
| T2.5 | M | PENDING | |
| T2.6 | S | SKIPPED | every CERT release with insiders > 2 GB; figshare link ~1 KB/s here (D-011); default of Q-001 applied, can be reopened |
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
