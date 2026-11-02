# LOOP_STATE.md

After any restart or context compaction: re-read CLAUDE.md, this file and docs/FIXES_SUMMARY.md first.

- Iteration: 15
- Current task: Phase 3 gate, then FINAL gate
- Last evidence path: logs/gate3_reproduce_full.log
- Open gates: G-SPEND (T3.7) default no. Phase 1 and Phase 2 gates PASSED 2026-10-23.
- Python for all project commands: `.venv/Scripts/python.exe` (PowerShell: `.venv\Scripts\python.exe`), with `PYTHONUTF8=1`

## Current plan (three lines)
- Goal: pass the Phase 3 and FINAL gates and write the final report.
- Smallest change: run reproduce.ps1 from a clean shell, compare non-latency manifest keys with logs/manifest_before_gate3.json.
- Verify: pytest, check_numbers, git status, H-R4/H-R5 scan recorded in FIXES_SUMMARY.

## Next action
Record the Phase 3 gate in FIXES_SUMMARY, then the FINAL gate.

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
| T2.6 | S | DONE | CERT r4.2: hybrid test F1 0.057, AUC 0.733 (N-051 to N-056); separate table `paper_inputs/tables/cert.tex` |
| T2.7 | M | DONE | |
| T3.1 | M | DONE | v2 + FUNSD subset; strongest local VLM (gemma-4B) v2 F1 0.845 < 1.000 |
| T3.2 | M | DONE | |
| T3.3 | M | DONE | Qwen2.5-VL-3B, gemma-3-4b-it and Qwen2.5-VL-7B local; 7B below gemma on every set (N-057 to N-060) |
| T3.4 | M | DONE | Pareto CSVs, calib tau, router; figure results/pii_v2/pareto_v2.pdf |
| T3.5 | M | DONE | |
| T3.6 | M | DONE | |
| T3.7 | C | NOT RUN | gate G-SPEND (Q-002), default no |
| T4.1 | M | DONE | config generated from manifest incl. tau_ocr; real backend scored end to end (results/e2e/e2e_demo.json) |
| T4.2 | M | DONE | user approved G-DOCS on 2026-10-24; docs/proposed/T4.2_Context.diff applied to 9 Context files |
| T4.3 | M | DONE | figures/architecture.dot shows the deployed configuration; all figures vector, each from a script |
| T4.4 | M | DONE | paper_inputs/ incl. claims_may_must_not.md copied from FIXES_SUMMARY section 5 |
| T4.5 | M | DONE | FIXES_SUMMARY sections 1 to 8 complete |
| T4.6 | C | NOT RUN | optional; federated learning stays future work |
