# LOOP_STATE.md

After any restart or context compaction: re-read CLAUDE.md, this file and docs/FIXES_SUMMARY.md first.

- Iteration: 13
- Current task: T3.2
- Last evidence path: results/latency/
- Open gates: Q-001 (CERT), Q-004 (FUNSD), defaults applied. Phase 1 and Phase 2 gates PASSED 2026-10-23.
- Python for all project commands: `.venv/Scripts/python.exe` (PowerShell: `.venv\Scripts\python.exe`), with `PYTHONUTF8=1`

## Current plan (three lines)
- Goal: T3.2 PaddleOCR vs EasyOCR on identical images.
- Smallest change: finish uv install, run paddle_ocr_runner.py, rerun presidio + score.
- Verify: same doc ids; manifest keys pii2.*.ocr.paddleocr_cpu.*

## Next action
Start T3.2.

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
| T3.1 | M | IN_PROGRESS | corpus built and scored for Presidio/OCR; acceptance (strongest available model < 1.000) waits for a VLM |
| T3.2 | M | PENDING | |
| T3.3 | M | PENDING | |
| T3.4 | M | PENDING | |
| T3.5 | M | DONE | |
| T3.6 | M | DONE | |
| T3.7 | C | PENDING | gate G-SPEND (Q-002) |
| T4.1 | M | PENDING | |
| T4.2 | M | PENDING | gate G-DOCS (Q-003) |
| T4.3 | M | PENDING | |
| T4.4 | M | PENDING | |
| T4.5 | M | PENDING | |
| T4.6 | C | PENDING | only if everything else is DONE |
