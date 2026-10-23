# HybridSaaS-Sec: Project Context (read this first, every session)

Save this file in the repo as `CLAUDE.md` (Claude Code reads it automatically) and keep a copy at `docs/context.md`.
Last updated: 2026-10-23. Numbers below come from `evaluation/data/metrics.json` (seed 42) and `evaluation/data/pii_metrics*.json`. If a number here disagrees with those files, the files win. Fix this document, not the files.

---

## 1. What this project is

A course research project for Software Design and Architecture.
Authors: Hashir Ahmad (BSSE24073) and Ahnuf Mir (BSSE24004).
Paper title: "HybridSaaS-Sec: A Scalable Framework for Privacy-Preserving API Monitoring and Multimodal Data Leakage Prevention in Enterprise Cloud Environments".

The system sits as a proxy in front of SaaS API traffic and decides PERMIT / ALERT / BLOCK for each user session by combining two signals:

1. **Content sensitivity S** (0 to 100): how much PII the document or text contains, found by a three-branch cost-ordered cascade.
2. **Behavioural anomaly A** (0 to 1): how unusual this user's behaviour is, from a hybrid anomaly engine.

They are fused into the Semantic-Behavioural Risk Score (SBRS), and bands on SBRS give the action.

### Submission history
- Submitted to IEEE FIT26 as submission 192. **Rejected** with mixed reviews: scores -2, -1, +2, 0, +1. Full text is in `docs/reviews/FIT26_reviews.txt`.
- The submitted PDF was altered for IEEE format and then run through paraphrasing or "humanizer" tools. That damaged the prose (uniform, flattened wording). The last good text is the "agreed" docx (`docs/paper/HybridSaaS-Sec_agreed.docx`). It is read-only reference material. **Do not edit it.** The paper will be rewritten by the user's writing assistant after the project work is done, using the results you produce.
- Policy: no AI-detector evasion, no "stealth" tools, ever. The paper will carry an honest AI-use disclosure (IEEE requires one in the acknowledgments).

---

## 2. Architecture (as implemented, not as designed)

```
client -> MITM proxy (backend/main.py, FastAPI)
            |-- PII pipeline (backend/pii_pipeline.py)     -> S
            |      Branch 1: Presidio on extractable text
            |      Branch 2: OCR (EasyOCR in practice) when OCR confidence >= tau_ocr, then Presidio
            |      Branch 3: vision-language model (VLM) when OCR confidence < tau_ocr
            |-- Anomaly engine (backend/anomaly_engine.py) -> A
            |      LSTM (h=128) per-user memory bank, score = 1 - mean top-10 cosine
            |      Isolation Forest (200 trees)
            |      A_hybrid = alpha*a_LSTM + (1-alpha)*a_IF
            |      EWMA baseline (lambda=0.3) kept as the comparison baseline
            `-- Risk orchestrator (backend/risk_orchestrator.py)
                   SBRS = S * (1 + beta*A) / 100, beta = 2.5
                   bands: >= 1.84 BLOCK, >= 1.22 ALERT, else PERMIT
frontend/app.py (Streamlit, 1,633 lines) is the dashboard.
```

`backend/anomaly_engine.py` does real inference from saved artifacts and raises `EngineUnavailable` if they are missing. `backend/lstm_infer.py` is a NumPy LSTM encoder for inference.

### Design vs reality (the central problem the reviewers hit)

| Item | Paper design | What was actually run |
|---|---|---|
| OCR | PaddleOCR | EasyOCR (no paddlepaddle wheel for Python 3.14) |
| VLM | PaliGemma-3B INT8, on-box | gemma-3-4b-it and Qwen2.5-VL-72B through a hosted Hugging Face router |
| Latency goal G5 | 300 ms end to end | OCR about 2.5 to 2.8 s per document, hosted VLM about 3.1 s per image |
| Federated learning, DP | FedAvg with differential privacy | **Never built.** Design proposal only |
| Data | real enterprise traffic implied | 100 percent synthetic (Faker), fonts for "handwriting" |
| Usability study | mentioned | never done |

Rule: every claim in the final paper must trace to something that was run, or be labelled future work.

---

## 3. Verified results (seed 42 unless stated)

### 3.1 Anomaly engine and SBRS (`evaluation/data/metrics.json`)

Dataset: 50 synthetic users, 21 days, hourly. 16,297 active sessions, 641 positives (3.93 percent). Chronological split 70/15/15. Test: 2,352 sessions, 96 threats, 27 labelled benign bursts.
Attack classes: malicious_insider (slow drift), compromised_account, negligent_insider, overscoped_thirdparty. benign_burst is a labelled negative.

| Quantity (test) | Value |
|---|---|
| Flag-level F1: EWMA tuned / LSTM only / IF only / hybrid | 0.116 / 0.350 / **0.634** / 0.629 |
| AUC: LSTM / IF / hybrid | **0.859** / 0.795 / 0.827 |
| Hybrid tuned on validation | alpha = 0.25, tau = 0.75 |
| Enforcement (ALERT or BLOCK) with beta 2.5, bands 1.22/1.84 | P 0.392, R 0.604, F1 0.475, FPR 3.99 percent (tp 58, fp 90, fn 38, tn 2166) |
| BLOCK only | P 0.743, R 0.271, F1 0.397, FPR 0.40 percent |
| Old doc bands (beta 0.5, 0.20/0.60) | F1 0.131, FPR 50.1 percent |
| Benign-burst flag rate: EWMA / hybrid | 59.3 percent / 0 percent (27 of 27 PERMIT) |
| Insider-oriented operating point (alpha 0.85, tau 0.39) | R 0.625, FPR 4.9 percent, F1 0.451, malicious-insider recall 0.294, but benign-burst flag rate rises to 37 percent |
| Anomaly scoring latency (CPU, 500 calls) | mean 16.9 ms, p95 18.2 ms (scoring only, excludes PII) |

Per-class hybrid recall at the F1-optimal threshold: compromised_account 1.00, negligent_insider 0.89, overscoped_thirdparty 1.00, **malicious_insider 0.02** (1 of 51 windows; 1 of 6 episodes). Per-class AUC for the three loud classes is about 1.0, which means the injected attacks are **too easy to separate**. Malicious-insider AUC: LSTM 0.744, IF 0.615, hybrid 0.674.

SBRS calibration (`evaluation/calibrate_sbrs.py`, `evaluation/SBRS_RECALIBRATION.md`): beta is the knee at 99 percent of the maximum validation AUC (0.839, plateau capped by malicious insiders). Bands are the benign-validation p95 (1.22) and p99.5 (1.84).

### 3.2 PII pipeline (`evaluation/data/pii_metrics*.json`, `evaluation/REAL_RESULTS_PII.md`)

Corpus: 120 synthetic documents (40 text, 40 scanned, 40 "handwritten" via handwriting fonts), 368 gold entities, 19 PII-free. Entity types: PERSON, EMAIL, PHONE, ADDRESS, CREDIT_CARD, DOB, PASSWORD, NID. Matching: type exact, value normalised, SequenceMatcher >= 0.85.

| Quantity | Value |
|---|---|
| Branch 1 (Presidio, text) | P 0.891, R 0.828, F1 0.858, 11 to 12 ms per document |
| OCR + Presidio on the 80 images | F1 0.699 |
| VLM on the 80 images | gemma-3-4b-it F1 0.936 (scanned 0.948, handwritten 0.920); Qwen2.5-VL-72B F1 **1.000** (240 of 240 entities) |
| Cascade at tau_ocr 0.85 | overall micro F1 0.857 (gemma) / 0.877 (Qwen72B) |
| Cascade at calibrated tau_ocr 0.98 | 0.908 (gemma) / 0.949 (Qwen72B) |
| Text-only baseline weighted recall | 0.276; recall on every image is 0.000 |
| EasyOCR mean confidence | scanned 0.844, handwritten 0.820, pristine render 0.804 |
| Total hosted-API spend | about 0.083 USD |

Findings that matter for the paper:
- **tau_ocr = 0.85 does not transfer to EasyOCR.** The F1-optimal threshold is about 0.98, which routes nearly everything to the VLM. That inverts the cost rationale of the cascade (the VLM was meant to be the rare fallback).
- **OCR confidence does not rank difficulty**: some degraded images score higher than clean ones.
- Presidio cannot detect street addresses (recall about 0.02 over 44) and misses most valid Mastercard numbers (about 6 of 20).
- gemma-4B drops long numerics (NID recall 0.53, credit card 0.79) and hallucinates some emails and addresses. Qwen-72B made no errors, so **the test set is probably too easy** (ceiling effect).

---

## 4. Known problems (the fix list, with IDs used by the startup prompt)

### Science and methodology
- **A1 No ablation.** IF-only (0.634) is as good as the hybrid (0.629), and the hybrid AUC (0.827) is below LSTM-only (0.859). The value of the hybrid is unproven.
- **A2 Statistics.** Window-level Wilson CIs overstate certainty because windows within one attack episode are correlated. Seeds vary only model training, not data generation. Need cluster bootstrap over episodes and users, and several independently generated datasets.
- **A3 Data too easy.** Three of four attack classes have AUC about 1.0. Need an intensity or difficulty sweep and overlap with benign behaviour.
- **A4 Slow insider drift is undetected** (recall 0.02). Reviewer 4 asked for a concrete architectural fix.
- **A5 SBRS multiplicative form is unjustified.** Reviewer 2 wants a comparison with additive, max and gated fusion, and notes S near zero suppresses any anomaly.
- **A6 Only synthetic data.** Need at least one external or more realistic validation (candidate: CERT Insider Threat Test Dataset, CC BY 4.0, DOI 10.1184/R1/12841247; it is itself synthetic but is a community benchmark).
- **P1 PII test set is too easy and small** (120 documents, 72B scores 1.000). Need larger, harder, partly real scans (candidates: FUNSD, 199 real scanned forms; SROIE, 1,000 scanned receipts; check licences and what PII-like fields they actually contain before use).
- **P2 Intended models never evaluated**: PaddleOCR and a small on-box VLM. Run them locally (RTX 3060 6 GB, LM Studio) and report honestly, even if worse.
- **P3 Cascade cost rationale broken.** Replace the single threshold with a cost versus accuracy Pareto curve over tau, and test a lightweight router that predicts "needs VLM".
- **P4 Latency goal mismatch.** Replace "300 ms end to end" with a two-tier design: Tier 1 inline (regex/Presidio + anomaly scoring, must meet a budget), Tier 2 asynchronous (OCR/VLM with hold, then release or quarantine). Measure Tier 1 end to end in the real proxy.
- **P5 Presidio gaps** (addresses, Mastercard): add custom recognisers and report before and after.

### Engineering hygiene
- **E1 Number drift.** Paper said F1 0.479 and fp 88; `metrics.json` says 0.4754 and fp 90. `REAL_RESULTS.md` section 4 (3-seed table) differs from `metrics.json`. `backend/risk_orchestrator.py` docstring is stale (0.479 / 3.9 percent).
- **E2 Stale labels.** `backend/pii_pipeline.py` still says "(simulated)" and uses a literal "PaddleOCR" label. `README.md`, `DEPLOYMENT.md`, `.env.example` (mentions a 7B model) are stale.
- **E3 No single command reproduces the results.** Add one script, pinned requirements, recorded seeds and git hash in every results file.
- **E4 No tests** for scoring, banding and metric code.
- **E5 Figure 1** (architecture) was criticised as schematic and AI-looking. Produce a proper vector figure source (draw.io/Graphviz/TikZ) plus exported PDF and SVG.

### Paper-level (done later by the writing assistant, but you must supply the inputs)
- Federated learning and DP move to "future work / architectural vision" and leave the contributions list. A small simulation is optional (Could-have), not required.
- Add a threats-to-validity section (synthetic data, font handwriting, hosted proxies).
- Re-position against Microsoft Purview. Verified: Purview Adaptive Protection feeds insider-risk levels (Elevated/Moderate/Minor) into DLP, Conditional Access and retention (learn.microsoft.com/en-us/purview/insider-risk-management-adaptive-protection and /dlp-adaptive-protection-learn). Purview also documents OCR for images in DLP; re-fetch that page and record the URL before anyone cites it. So "legacy DLP is blind to images and behaviour" is no longer a safe claim. The defensible novelty is narrower: an open, auditable, per-user cascade with measured trade-offs, plus the honest negative results.
- Reference list has 9 entries and several are wrong. Corrections are in `docs/REFERENCES_VERIFIED.md`.

---

## 5. Repository map

```
backend/        main.py, anomaly_engine.py, lstm_infer.py, pii_pipeline.py, risk_orchestrator.py,
                schemas.py, data_loader.py, measured_metrics.py
frontend/       app.py (Streamlit dashboard)
evaluation/     generate_sessions.py, train_and_evaluate.py (782 lines), calibrate_sbrs.py,
                refresh_sbrs_columns.py, build_pii_testset.py, run_pipeline.py (862 lines),
                common.py, pii_common.py, REAL_RESULTS.md, REAL_RESULTS_PII.md,
                SBRS_RECALIBRATION.md, data/ (metrics*.json, scored_all_splits.csv, sessions_raw.csv,
                user_profiles.csv, pii_metrics*.json, pii_predictions*.json, vlm_cache/), artifacts/, pii_testset/
Context/        design documents (01-Research-Paper/...). Update only in task T4.2.
*.csv, *.json   legacy demo data (anomaly_detection_comparison*.csv, pii_scan_results*.csv, ...)
requirements.txt, requirements-eval.txt, .env.example, README.md, DEPLOYMENT.md
```

---

## 6. Environment

- Windows, repo at `C:\Users\loons\Documents\GitHub\SDA-Research-Project`, PowerShell. Use `python -m` and forward-slash-safe paths in code. Do not assume bash.
- Laptop: ASUS TUF, RTX 3060 **6 GB VRAM**.
- Python 3.14 has **no paddlepaddle wheel**. Create a separate 3.11 or 3.12 venv (for example `.venv-paddle`) for PaddleOCR work. Check `python --version` and `py -0` first. torch must be the CUDA build if the GPU is used.
- LM Studio runs an OpenAI-compatible server (default `http://localhost:1234/v1`). Query `/v1/models` for the exact model id. Send images as PNG or JPEG data URLs; there is an open LM Studio issue (#1752) about base64 data URIs with webp. The user's assistant branding inside LM Studio is called "Bionic".
- Whether a quantised PaliGemma or Qwen2.5-VL fits in 6 GB has **not** been verified. Measure it. Candidates to check in the LM Studio catalogue: a Qwen2.5-VL 3B or 7B GGUF, gemma-3-4b-it. PaliGemma is gated on Hugging Face and may need licence acceptance.
- Hugging Face token lives in `.env` (gitignored). **Never read, print, log or commit `.env`.** If you need to know whether a key is set, check `bool(os.getenv(...))` only.
- Hosted inference costs money and the free tier is capped (HTTP 402). Do not spend without explicit user approval (gate H1). Prefer local models.

---

## 7. Rules for working on this repo

1. **Honesty over scores.** If an experiment makes the system look worse, keep it and report it. Never tune on the test split. Never change a result to match the paper; change the paper-facing text instead.
2. **Evidence trail.** Every claim you produce needs a command, a script path, a seed, and an output file. Results files must record git hash, seeds, date, library versions.
3. **No fabricated citations.** Any reference you add must be confirmed against Crossref, arXiv or the publisher page, and recorded in `docs/REFERENCES_VERIFIED.md` with the check you did. If you cannot verify, mark it UNVERIFIED and do not use it.
4. Do not edit the paper docx or anything in `docs/paper/`. Do not touch `Context/` except in T4.2.
5. Work on branch `paper-v2`. Local commits are fine. **Never push.** Never rewrite history.
6. Do not delete user data. Large generated files go under `evaluation/data/` or `results/` and stay out of git if over 5 MB.
7. Keep the old behaviour reproducible: new code goes beside the old, with the old numbers preserved as `results/baseline_*`.
8. No em dashes in any prose you write for the paper inputs (the user's style requirement). Plain, direct sentences.
9. Ask the user only at the human gates listed in the startup prompt. Otherwise decide, record the decision in `docs/DECISIONS.md`, and continue.

---

## 8. Deliverable you must produce at the end: `FIXES_SUMMARY.md`

A plain-language report the user can read in five minutes and hand to the writing assistant. For every task ID it states: what was wrong, what you changed (files), the command that reproduces it, the headline numbers before and after, what stayed unresolved, and any new limitation. Also include a table "claims the paper may now make" versus "claims it must not make", each with its evidence file. Update it at every gate, not only at the end.
