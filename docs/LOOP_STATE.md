# LOOP_STATE.md

After any restart or context compaction: re-read CLAUDE.md, this file and docs/FIXES_SUMMARY.md first.

- Iteration: 8
- Current task: T2.4
- Last evidence path: results/sweep/
- Open gates: Q-001 (CERT, default skip applied). Phase 1 gate PASSED 2026-10-23.
- Python for all project commands: `.venv/Scripts/python.exe` (PowerShell: `.venv\Scripts\python.exe`), with `PYTHONUTF8=1`

## Current plan (three lines)
- Goal: T2.4 dedicated slow-drift detector (CUSUM, Page-Hinkley) next to the hybrid; episode recall, time to detect, false alarms; supervised-probe upper bound.
- Smallest change: evaluation/drift_detector.py (drafted, vectorised, unit-tested) with guarded selection on validation.
- Verify: tests/test_drift.py; rerun one seed identical; claims.

## Next action
Start T2.4.

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
| T2.3 | M | DONE | |
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
