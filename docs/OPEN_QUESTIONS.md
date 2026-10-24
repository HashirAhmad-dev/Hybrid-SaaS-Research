# OPEN_QUESTIONS.md

Questions waiting on the user. Each has the default that is applied if there is no answer.

| ID | Gate | Question | Default if unanswered | Status |
|---|---|---|---|---|
| Q-001 | G-DATA | T2.6: CERT (CC BY 4.0) releases with insider scenarios start at 4.25 GB (r3.1); r4.2 is 4.82 GB. Figshare throughput from this laptop was about 1 KB/s (D-011). Do you want to download r4.2 yourself (browser) into `external/cert/` so I can map it? | Skip CERT (T2.6 SKIPPED), describe as future external validation. | ANSWERED 2026-10-24: user said large data goes to D: instead of being skipped (D-020). Downloading r4.2 to D:\datasets\cert. |
| Q-002 | G-SPEND | T3.7: hosted upper-bound VLM run on the new PII corpus (Hugging Face router, paid). | No hosted calls. | OPEN (asked when T3.7 is reached) |
| Q-003 | G-DOCS | T4.2: review `docs/proposed/T4.2_Context.diff` (9 files in `Context/`: federated learning moved to future work, 300 ms goal replaced by measured two-tier budget, REST defaults, fusion and paper-v2 result notes). Approve? Then I run `python -m tools.propose_doc_changes --apply`. README and DEPLOYMENT were already corrected for stale numbers in T1.2/T3.6. | Leave `Context/` unchanged; diff stays ready. | OPEN, default applied |
| Q-004 | G-DATA | T3.1: FUNSD (199 real scanned forms, about 16 MB) requires you to accept its non-commercial research terms (18+, binding). Its labels are not PII types, so the PII gold would be heuristic and partial (D-013). Accept and want it as a real-scan subset? | Skip; state in threats to validity that no real scans were evaluated. | OPEN, default applied |
