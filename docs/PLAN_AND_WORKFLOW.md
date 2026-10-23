# PLAN_AND_WORKFLOW.md

Save as `docs/PLAN_AND_WORKFLOW.md`. Written 2026-10-23 after reading the five FIT26 reviews, auditing the repo (code, metrics files, reports), re-verifying the nine references, and checking related work and tooling.

Nobody can guarantee acceptance. What this plan does is remove every weakness a reviewer can find by reading the paper against the repo, and it makes each remaining weakness something the paper states openly.

---

## 1. Where the project really stands

### What is solid
- Real code that runs end to end, real numbers, fixed splits, honest negative findings. Reviewers 4 and 5 both praised the candour. Keep it.
- The benign-burst result is the strongest practical point: EWMA flags 59.3 percent of 27 benign bursts, the hybrid with calibrated bands flags 0 percent.
- The PII finding that a text-only tool has 0.000 recall on every image, and that Presidio cannot find street addresses (recall about 0.02), is clean and reproducible.

### What a careful reviewer can still attack (found in the repo, beyond the reviews)
1. **The hybrid is not shown to be better than its parts.** On the test set, IF-only F1 is 0.634 and hybrid F1 is 0.629. Hybrid AUC (0.827) is below LSTM-only (0.859). There is no ablation in the paper.
2. **The attack data is too easy.** Three of four attack classes reach AUC of about 1.0. Results on easy data say little about the method.
3. **Confidence intervals are too narrow.** Windows inside one attack episode are correlated, but the Wilson intervals treat them as independent. Seeds change training only, never the generated data.
4. **Number drift.** The paper said F1 0.479 and 88 false positives. The metrics file says 0.4754 and 90. One report has a three-seed table that differs again.
5. **The PII benchmark has a ceiling.** The 72B model scored 240 of 240. A test that the strongest model passes perfectly cannot separate good designs from bad ones. It is also 120 synthetic documents with font-rendered handwriting.
6. **The intended system was never evaluated** (PaddleOCR, on-box 3B VLM, federated learning, 300 ms goal). The paper has to describe the evaluated system as the system.
7. **Positioning.** Microsoft Purview already documents behaviour-driven DLP (Adaptive Protection: Elevated/Moderate/Minor insider risk levels feeding DLP and Conditional Access). A claim that existing DLP ignores behaviour is not safe. A directly related 2026 paper (Abibulaiev et al., MDPI MAKE, cloud API traffic, ML + NLP, risk level using data sensitivity) must be read and compared.
8. **References.** Nine entries; three were wrong (6, 7, 9), two had author or title errors (4, 5). Corrected in `REFERENCES_VERIFIED.md`. Thirty or more verified references is a realistic target for a conference paper.
9. **The submitted PDF was damaged** by paraphrasing tools and format conversion. That is a writing problem, fixed at the rewrite by working from the agreed docx, not from the PDF.

---

## 2. The plan

Priority key: **M** must (paper is not publishable without it), **S** should, **C** could. Task IDs match the startup prompt.

### Phase 1: Make the numbers trustworthy (M)
| ID | Task | Done when |
|---|---|---|
| T1.1 | One results manifest (`results/manifest.json`) written by the scripts, plus `tools/check_numbers.py` that compares any list of "paper number -> manifest key" pairs | Script exits non-zero on any mismatch |
| T1.2 | Fix drift and stale text: docstring in `risk_orchestrator.py`, "(simulated)" and PaddleOCR label in `pii_pipeline.py`, README, DEPLOYMENT, `.env.example`, reconcile REAL_RESULTS section 4 with `metrics.json` | grep finds no stale number or label; every report cites one run id |
| T1.3 | One-command reproduction (`reproduce.ps1` and `reproduce.sh`), pinned requirements, seed and git hash and library versions stored in every output | A clean clone reproduces the manifest within tolerance |
| T1.4 | Data-level seeds: regenerate the dataset for each seed (at least 10), not only retrain | Metrics reported as mean and interval across independent datasets |
| T1.5 | Unit tests for scoring, banding, metrics, matching | `pytest` passes |

### Phase 2: Anomaly science (M unless marked)
| ID | Task | Done when |
|---|---|---|
| T2.1 | **Ablation grid.** Detectors: EWMA, per-user z-score, LSTM only, IF only, hybrid, plus one more sequence baseline (for example an LSTM autoencoder or next-step predictor) and one more unsupervised baseline (for example LOF or One-Class SVM). Fusion variants: weighted mean, max, rank average. Report AUC, average precision, recall at 1 percent and 5 percent FPR, F1 at a validation-chosen threshold | One table, one figure, all on the same splits |
| T2.2 | **Statistics.** Cluster bootstrap over attack episodes and users; paired comparison of hybrid versus each baseline; report intervals for every headline number; confusion matrices per class | Every claim in the paper has an interval from the cluster bootstrap |
| T2.3 | **Difficulty sweep.** Attack intensity from barely visible to obvious, plus overlap with benign behaviour. Plot detection against intensity for each detector | Curve per detector; shows where each fails |
| T2.4 | **Slow-insider detector.** Add a dedicated drift detector (candidates: CUSUM or Page-Hinkley on per-user residuals, multi-day aggregation) and report episode recall and time to detect, with false alarms on benign bursts | Honest result either way; reviewer 4's request answered with a measured design |
| T2.5 | **SBRS fusion study.** Multiplicative (current), additive, max, independently gated (escalate if A is high regardless of S), and a small logistic model. Evaluate on the (S, A) cases the reviewer named, including low S with high A. Bands calibrated on validation only | Table with the same budget (benign FPR) for each form |
| T2.6 | **External validation on CERT** (S, gate H2 for the download). Feature mapping documented; report in a separate table; clearly labelled as another synthetic benchmark | If infeasible in time, document why and move to threats-to-validity |
| T2.7 | Keep the old operating points (F1-optimal, insider-oriented, enforcement bands) in one clearly labelled table | No unlabelled threshold anywhere |

Expected outcomes and how the paper changes (decide after T2.1, do not pre-commit):
- Hybrid beats both parts with an interval that excludes zero on the harder data: keep the "hybrid" contribution.
- Hybrid is about equal to IF-only: say so. Reframe the contribution as the evaluation of fusion and enforcement (benign-burst suppression, SBRS calibration, slow-drift gap) rather than the superiority of the hybrid. This is a legitimate and honest paper.
- The slow-insider detector helps: it becomes a contribution. If not, it is a documented negative result with a time-to-detect analysis.

### Phase 3: PII science (M unless marked)
| ID | Task | Done when |
|---|---|---|
| T3.1 | **Harder, larger corpus.** At least 300 documents; three difficulty levels; more varied layouts; PII-free documents and near-miss strings (numbers that look like cards); real scans where licences allow (FUNSD forms, check what PII-like fields exist) as a separate reported subset | No model scores a perfect 1.000 on the main set |
| T3.2 | **PaddleOCR in a Python 3.11/3.12 venv.** Run it, report its confidence behaviour against EasyOCR | Table: both OCR engines on the same images |
| T3.3 | **Local small VLM through LM Studio** on the 6 GB GPU (check what fits: a Qwen2.5-VL 3B or 7B quantised model, gemma-3-4b-it, others in the catalogue). Record VRAM, tokens per second, time per image, accuracy. Use PNG or JPEG data URLs (LM Studio issue #1752 concerns base64 with webp). Use a seeded, temperature-0 prompt | The paper's "on-box VLM" claim is either measured or removed |
| T3.4 | **Cascade Pareto curve** (cost versus F1 across tau, for both OCR engines) and a **lightweight router** that predicts "this document needs the VLM" from cheap features (OCR confidence, text length, entity density, image size, Presidio hit count). Train on one split, test on another | Pareto figure; router beats the single confidence threshold or the paper says it does not |
| T3.5 | **Presidio gap fixes** (address recogniser, Mastercard ranges) with before and after numbers | Measured change per entity type |
| T3.6 | **Two-tier latency design and measurement.** Tier 1 inline: regex/Presidio on text + anomaly scoring, measured end to end inside the running proxy (p50, p95, p99). Tier 2 asynchronous: OCR and VLM, with hold-then-release or quarantine. Replace "300 ms end to end" with the Tier 1 budget that was measured | Measured Tier 1 numbers; Tier 2 reported separately |
| T3.7 (C) | Run the hosted Qwen-72B again as an "upper bound" only if the new corpus needs it; record cost; needs gate H1 | Cost logged |

### Phase 4: Integration, figures, handoff (M)
| ID | Task | Done when |
|---|---|---|
| T4.1 | Wire final configurations (beta, bands, tau or router, drift detector) into `backend/` with measured-source labels | Backend starts, scores a sample session, and cites its config source |
| T4.2 | Update `Context/` design docs and README/DEPLOYMENT to the new reality (diff listed first, applied after approval) | Docs and code agree |
| T4.3 | **Figures.** Architecture diagram as editable source (draw.io or Graphviz or TikZ) and exported vector PDF/SVG; plots as vector PDF with readable fonts at column width; no stock AI-looking graphics | Figure files plus the scripts that generate them |
| T4.4 | `paper_inputs/`: LaTeX tables, CSVs, JSON of every number, figure files, a claim-evidence matrix (claim -> manifest key -> script -> seed) | Matrix complete |
| T4.5 | `FIXES_SUMMARY.md` | See `context.md` section 8 |
| T4.6 (C) | Tiny federated simulation (FedAvg on per-tenant IF/LSTM) if and only if everything above is finished | Otherwise federated learning stays future work |

### What not to do
- Do not add federated learning or differential privacy to the contributions. It is not built. It belongs in a short "future work" paragraph (cite McMahan et al.; DP-SGD only after verifying the Abadi citation).
- Do not present the usability study as done.
- Do not tune any threshold on the test split.
- Do not use AI "humanizer" or "stealth" tools on the final paper. They flattened the style of the submitted version and add no integrity. The honest route is: write it yourselves from the results, use an AI assistant only for allowed help such as checking grammar, and disclose it (below).

---

## 3. End-to-end workflow, from here to submission

```
Week 0   Repo work (this plan, phases 1-4)              -> FIXES_SUMMARY.md, paper_inputs/
         Independent audit (Codex, local model, you)    -> audit_findings.md, fixes applied
Week 1   Paper rewrite from paper_inputs/ and the agreed docx
         (new structure, threats to validity, 30+ verified references, new Figure 1)
         Your own read-through, co-author read-through, instructor check
Week 1+  Format in the venue template (IEEE conference LaTeX/Word template as required)
         Reference check script; number check script; AI-use disclosure; submission
```

Compressed 7-day version (only if the deadline is truly one week). Do all M tasks in this order and skip S and C:
- Day 1: T1.1 to T1.5.
- Day 2: T2.1, T2.2.
- Day 3: T2.3, T2.5, T2.4 (start).
- Day 4: T3.1, T3.2, T3.5.
- Day 5: T3.3, T3.4.
- Day 6: T3.6, T4.1, T4.3.
- Day 7: T4.4, T4.5, audit, paper rewrite starts.
This is tight. If the deadline is firm and one week, drop T2.6 and T3.7, and shorten T2.4 to a CUSUM baseline plus an honest negative or positive result.

Venue: the deadline and venue are not known to me. Pick by checking, for each candidate, scope fit, page limit, deadline, whether the proceedings are indexed where your instructor requires, and the AI-disclosure rule. One candidate that turned up during research is ICAIC 2027 (deadline listed as 30 Dec 2026); I could not verify its scope or indexing, so treat it as a lead and check the official call for papers. The FIT26 reviews are usable as-is for a resubmission elsewhere since the paper was rejected, not withdrawn under review.

IEEE rule to follow: IEEE expects use of AI-generated text to be disclosed in the acknowledgments section. Put an honest sentence there at the rewrite stage (what tools, which parts, that the authors take responsibility). Re-read the current policy on the venue's author page before submitting.

---

## 4. AI tools: who does what

| Tool | Best use here | Do not use it for |
|---|---|---|
| **Claude Code** (repo open) | Implement the plan, run experiments, write tests, produce `paper_inputs/` and `FIXES_SUMMARY.md` | Deciding what the paper may claim without the evidence matrix |
| **Codex (ChatGPT Plus)** | Independent code audit in a separate worktree or branch: reproduce the headline numbers from scratch, review splits for leakage, check the stats code, try to break the scoring. A different model family catches different mistakes | Editing the same branch at the same time as Claude Code |
| **LM Studio local models** | (a) The small VLM that Branch 3 is supposed to be (T3.3). (b) A second reader for prose: ask a local text model to list sentences in the draft that are not supported by the claim-evidence matrix | Producing numbers. A language model must never be the source of a metric. Judge-by-LLM is not a substitute for the scripts |
| **ChatGPT web / deep research** | Finding literature leads | Citing anything unverified. Every lead goes through `REFERENCES_VERIFIED.md` rules |
| **Firecrawl / Crossref / arXiv** | Verifying a reference record | Trusting a snippet without opening the record |
| **Claude chat (me)** | Rewriting the paper from the verified inputs, structure, consistency pass, reviewer-response mapping | Inventing results |
| **draw.io, Graphviz, Inkscape, matplotlib (PDF/SVG output)** | Figure 1 and plots | Raster screenshots |
| **Zotero + Better BibTeX (optional)** | Keeping the bibliography clean | Importing entries unchecked |

Cross-check habit that works well: after each phase, give Codex the phase's `FIXES_SUMMARY` section plus the repo and ask it to find one thing wrong in each claim. Fix, rerun, move on.

### Audit prompt for Codex (paste as is)

```
You are an independent reviewer of a research repository. Do not trust any markdown report; trust only code and data files.
1. Read docs/context.md and docs/FIXES_SUMMARY.md.
2. Run the reproduction script and compare its output to results/manifest.json. List every number that differs.
3. Check evaluation code for: train/val/test leakage (time order, per-user history, buffer between splits), thresholds tuned on test data, metrics computed on the wrong subset, cluster bootstrap grouped incorrectly, random seeds that are fixed in one place but not another.
4. For the PII evaluation, check the matching rule, double counting, and whether gold entities leak into prompts.
5. Report findings as: file:line, what is wrong, how to reproduce, severity. Do not fix anything. Do not claim a problem unless you reproduced it. If you find nothing in an area, say what you checked.
```

### Using local models inside the pipeline (rules)
- Query `http://localhost:1234/v1/models` and pin the exact model id in the config; record it in the results file.
- Temperature 0, fixed prompt, PNG/JPEG only, one image per request, a timeout, and a cache keyed by (model id, prompt hash, image hash).
- Record VRAM use, tokens per second, and per-image latency. Report the machine (RTX 3060 6 GB, CPU, RAM, driver) in the paper.
- If a model does not fit or is too slow, say so in the paper. That is itself a finding about the on-box claim.

---

## 5. Publication-readiness checklist (the gate for the rewrite)

- [ ] Every number in the paper maps to a manifest key and a script (claim-evidence matrix complete).
- [ ] Ablation present; hybrid claim matches what it shows.
- [ ] Intervals from cluster bootstrap; several independently generated datasets.
- [ ] At least one harder or external validation, labelled as such.
- [ ] No result scored 1.000 on the main PII set; real-scan subset reported separately.
- [ ] Evaluated system equals described system, or every difference is stated in one place.
- [ ] Latency claims split into Tier 1 (measured inline) and Tier 2 (asynchronous).
- [ ] Federated learning and usability study appear only as future work.
- [ ] Threats-to-validity section written (synthetic data, font handwriting, hosted proxies, single OCR and VLM families, small user count).
- [ ] Related work includes Purview Adaptive Protection and the 2026 cloud-API-traffic paper, with an honest difference statement.
- [ ] 30 or more references, each in `REFERENCES_VERIFIED.md` with a check.
- [ ] Reproduction works from a clean clone.
- [ ] AI-use disclosure written.

---

## 6. Things I could not verify (so you know)

- Whether a quantised Qwen2.5-VL or PaliGemma fits and runs acceptably on 6 GB VRAM under LM Studio on Windows. T3.3 measures it.
- The venue, its deadline, and indexing (ICAIC 2027 is only a lead).
- That Purview's OCR-in-DLP documentation says exactly what the paper needs; Claude Code should re-fetch the page and record the URL and date before the claim is used.
- The DP-SGD (Abadi et al.) record, a handful of author lists marked CHECK in `REFERENCES_VERIFIED.md`.
- Whether FUNSD or SROIE contain person-type PII that makes them useful for this task. Look at the annotations first.
- Your real deadline, and whether the two added co-authors in the submitted PDF stay on the paper (agree this with the instructor and co-authors; do not guess).
