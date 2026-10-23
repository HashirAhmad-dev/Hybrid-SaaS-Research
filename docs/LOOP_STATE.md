# LOOP_STATE.md

After any restart or context compaction: re-read CLAUDE.md, this file and docs/FIXES_SUMMARY.md first.

- Iteration: 11
- Current task: PHASE2-GATE
- Last evidence path: results/operating_points/
- Open gates: Q-001 (CERT, default skip applied). Phase 1 gate PASSED 2026-10-23.
- Python for all project commands: `.venv/Scripts/python.exe` (PowerShell: `.venv\Scripts\python.exe`), with `PYTHONUTF8=1`

## Current plan (three lines)
- Goal: Phase 2 gate (pytest, full reproduce, check_numbers, git status, FIXES entries, H-R4/H-R5 scan).
- Smallest change: run full reproduce in background while Phase 3 OCR work runs.
- Verify: five checks recorded in FIXES_SUMMARY gate records.

## Next action (written 2026-10-23 when the session's usage limit was reached)
1. Phase 2 gate: run full `reproduce.ps1` (about 2 h), compare manifest with `logs/` snapshot, write gate record (H-R4/H-R5 scan notes: LOF peek D-008 disclosed; all other selection on validation via evaluation/selection.py).
2. T3.1: corpus v2 built (evaluation/build_pii_corpus_v2.py, 360 docs, seed 2610, byte-identical on rebuild); commit and record.
3. T3.2: EasyOCR v2 run was in progress (evaluation/data/pii_v2/ocr_easyocr_cpu.json, resumable). PaddleOCR install attempt 2 (uv, Python 3.12, .venv-paddle) was downloading; then run evaluation/paddle_ocr_runner.py.
4. T3.3: Qwen2.5-VL-3B Q4_K_M downloading by curl -C - into ~/.lmstudio/models/lmstudio-community/Qwen2.5-VL-3B-Instruct-GGUF (*.partial, ~50 KB/s). When done: rename, `lms load`, `python -m evaluation.pii_v2 vlm --model <id>`.
5. Then `python -m evaluation.pii_v2 presidio` and `score` (T3.4, T3.5), `python -m evaluation.tier_latency` (T3.6; backend/tier1.py and /tier1, /tier2 endpoints drafted, untested).
6. Phase 4.

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
| T2.6 | S | SKIPPED | every CERT release with insiders > 2 GB; figshare link ~1 KB/s here (D-011); default of Q-001 applied, can be reopened |
| T2.7 | M | DONE | |
| T3.1 | M | IN_PROGRESS | corpus built, not yet committed/scored |
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
