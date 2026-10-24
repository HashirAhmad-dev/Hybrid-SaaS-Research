# LOOP_STATE.md

After any restart or context compaction: re-read CLAUDE.md, this file and docs/FIXES_SUMMARY.md first.

- Iteration: 14
- Current task: T3.3
- Last evidence path: results/pii_v2/
- Open gates: Q-001 (CERT), Q-004 (FUNSD), defaults applied. Phase 1 and Phase 2 gates PASSED 2026-10-23.
- Python for all project commands: `.venv/Scripts/python.exe` (PowerShell: `.venv\Scripts\python.exe`), with `PYTHONUTF8=1`

## Current plan (three lines)
- Goal: T3.3 local VLM via LM Studio (Qwen2.5-VL-3B Q4_K_M), accuracy per entity type, VRAM, tokens/s, s/image.
- Smallest change: finish append-only download (tools/fetch_resumable.py), lms load, python -m evaluation.pii_v2 vlm --model <id>.
- Verify: cache keyed by model/prompt/image; rerun from cache identical; record GPU peak.

## Next action
Start T3.3.

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
| T2.4 | M | DONE | |
| T2.5 | M | DONE | |
| T2.6 | S | IN_PROGRESS | reopened by D-020: CERT r4.2 downloading to D:/datasets/cert |
| T2.7 | M | DONE | |
| T3.1 | M | DONE | v2 + FUNSD subset; strongest local VLM (gemma-4B) v2 F1 0.845 < 1.000 |
| T3.2 | M | DONE | |
| T3.3 | M | DONE | Qwen2.5-VL-3B and gemma-3-4b-it local; Qwen2.5-VL-7B added when its download finishes |
| T3.4 | M | DONE | Pareto CSVs, calib tau, router; figure results/pii_v2/pareto_v2.pdf |
| T3.5 | M | DONE | |
| T3.6 | M | DONE | |
| T3.7 | C | PENDING | gate G-SPEND (Q-002) |
| T4.1 | M | PENDING | |
| T4.2 | M | BLOCKED | waiting on gate G-DOCS (Q-003); diff ready at docs/proposed/T4.2_Context.diff; default (leave unchanged) applied |
| T4.3 | M | PENDING | |
| T4.4 | M | PENDING | |
| T4.5 | M | PENDING | |
| T4.6 | C | PENDING | only if everything else is DONE |
