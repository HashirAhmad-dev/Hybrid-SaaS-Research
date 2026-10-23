# HybridSaaS-Sec - Interactive Demo

An interactive, paper-faithful demonstration of the framework introduced in:

> **Mir & Hashir,** _A Scalable Framework for Privacy-Preserving API Monitoring
> and Multimodal Data Leakage Prevention in Enterprise Cloud Environments_,
> Software Design and Architecture Research Paper, 2026.

The framework is a Man-in-the-Middle (MITM) proxy design that intercepts
SaaS API traffic, runs a **multimodal PII pipeline**, evaluates **hybrid
behavioural anomalies** (LSTM h=128 + Isolation Forest), and orchestrates a
unified **Semantic-Behavioral Risk Score (SBRS)** for enforcement.

What was actually run: Branch 1 is Microsoft Presidio, Branch 2 is EasyOCR
followed by Presidio, and Branch 3 is a vision-language model (evaluated so
far: gemma-3-4b-it and Qwen2.5-VL-72B through a hosted router). The design
names PaddleOCR and an on-box PaliGemma-3B; neither has been run yet. All data
is synthetic.

The numbers the dashboard shows are read from the measured evaluation files
(`evaluation/data/metrics.json`), not from the paper draft. The earlier draft
figures (EWMA FPR 42.7 % vs hybrid 11.2 %, SBRS F1 0.93, PII coverage 0.91) did
not reproduce. Every number the paper may quote is recorded in
`results/manifest.json` and can be checked with `tools/check_numbers.py`.

---

## Reproduce every result (one command)

```powershell
# one-time: project venv with the exact versions used for the paper
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt

# regenerate data, train, evaluate, calibrate, write results\manifest.json, check all numbers
pwsh -ExecutionPolicy Bypass -File .
eproduce.ps1
```

`reproduce.sh` does the same from bash. Each stage logs to `logs
eproduce_*.log`.
The last stage runs `tools/check_numbers.py` over every claims file in
`results/claims/` and fails on any mismatch. Seeds are fixed in the scripts
(data seed 42, training seed 42); the run is bit-for-bit repeatable on CPU.
Runtime on the authors' laptop (i7-11370H, CPU torch): under 1 minute for the
current stages. Later stages (multi-seed datasets, ablation, statistics, PII)
are added to the same scripts as they land; see `docs/FIXES_SUMMARY.md`.

---

## Latency: two tiers instead of one 300 ms goal

Measured inside the running FastAPI proxy (`python -m evaluation.tier_latency`,
CPU, laptop described in `docs/ENVIRONMENT.md`):

* **Tier 1, inline** (`POST /tier1/score`: Presidio on the text payload, LSTM +
  Isolation Forest on the behaviour vector, SBRS band): p50 33.7 ms, p95 40.5 ms,
  p99 44.6 ms over 1,000 warm requests. The first request after a cold start takes
  about 9 s (loading spaCy, the LSTM and the forest).
* **Tier 2, asynchronous** (`POST /tier2/submit`, `GET /tier2/{job}`: OCR then
  Presidio on an image while the upload is held): hold time p50 3.4 s, p95 5.3 s
  with EasyOCR on CPU.

Numbers: `results/latency/tier_latency.json`, manifest keys `latency.tier1.*`, `latency.tier2.*`.

---

## Project layout

```
SDA Research Project/
+-- backend/                       # FastAPI + scoring core
|   +-- __init__.py
|   +-- data_loader.py             # Pandas ingestion of CSV/JSON artefacts
|   +-- pii_pipeline.py            # replays the recorded PII result of each demo event
|   +-- anomaly_engine.py          # trained LSTM + Isolation Forest, real inference
|   +-- risk_orchestrator.py       # SBRS = S * (1 + beta * A_hybrid) / 100
|   +-- schemas.py                 # Pydantic models
|   +-- main.py                    # FastAPI service
+-- frontend/
|   +-- app.py                     # Streamlit dashboard (3 tabs)
+-- pii_scan_results.csv
+-- anomaly_detection_comparison.csv
+-- ewma_user_baselines.csv
+-- blocked_events_audit.csv
+-- hybridSaaS_events.json
+-- hybridSaaS_system.log
+-- requirements.txt
+-- README.md
```

---

## Setup (Windows / PowerShell)

```powershell
# 1. Create + activate a virtual environment (Python >= 3.11 recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
python -m pip install -U pip
python -m pip install -r requirements.txt
```

> **Note on Python 3.14:** pre-built wheels for pandas / numpy may not be
> available yet for 3.14. If installation tries to build pandas from source,
> use Python 3.11 / 3.12 instead.

---

## Run

In **two separate terminals**, both with the venv activated:

```powershell
# Terminal 1 - FastAPI backend (http://127.0.0.1:8000/docs)
uvicorn backend.main:app --reload --port 8000
```

```powershell
# Terminal 2 - Streamlit dashboard (http://localhost:8501)
streamlit run frontend/app.py
```

The Streamlit app imports the backend modules directly, so it works even
if the FastAPI process isn't running. Start uvicorn only if you want to
exercise the REST surface (e.g. via `curl` or the Swagger UI at `/docs`).

---

## REST endpoints (FastAPI)

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/`                        | Health + dataset summary |
| `GET`  | `/metrics`                 | Measured metrics next to the earlier paper claims |
| `GET`  | `/events?limit=N`          | List of intercepted events |
| `GET`  | `/events/{event_id}`       | Raw event payload |
| `GET`  | `/score/{event_id}`        | Full pipeline result (PII + Anomaly + SBRS) |
| `POST` | `/score`                   | Score an arbitrary event payload |
| `GET`  | `/baselines`               | Legacy EWMA per-user baselines (8 windows) |
| `GET`  | `/audit/blocked`           | Audit trail of BLOCK enforcement actions |
| `GET`  | `/comparison`              | Tidy EWMA vs Hybrid per-event evaluation |

Query parameters `alpha` (LSTM weight; default read from the trained
artefacts, 0.25 for the shipped engine) and `beta` (enterprise risk
multiplier, default 2.5) on `/score` let you score an event under different
SBRS configurations.

---

## Mathematical core (Section IV of the paper)

```
A_hybrid = alpha * a_LSTM + (1 - alpha) * a_IF
SBRS     = S * (1 + beta * A_hybrid) / 100
```

* `S`         in `[0, 100]` from `min(10*high + 5*medium + 1*low, 100)`.
* `a_LSTM`    in `[0, 1]` - cosine similarity vs user's 24h memory bank.
* `a_IF`      in `[0, 1]` - Isolation Forest outlier score vs global pop.
* `alpha`     LSTM weight, chosen on the validation split (0.25 for the shipped engine).
* `beta`      enterprise risk multiplier, 2.5 (validation-calibrated, see
  `evaluation/SBRS_RECALIBRATION.md`).

Enforcement bands (95th and 99.5th percentile of benign validation SBRS,
`evaluation/calibrate_sbrs.py`):

| SBRS range | Category   | Action |
|------------|------------|--------|
| `< 1.22`   | SAFE       | PERMIT |
| `< 1.84`   | SENSITIVE  | ALERT  |
| `>= 1.84`  | HIGH-RISK  | BLOCK  |

---

## Verifying the data loader

The data loader (`backend/data_loader.py`) ships with a smoke test:

```powershell
python -m backend.data_loader
```

Expected output (counts may differ if the dataset is updated):

```
DATA_DIR : c:\Users\...\SDA Research Project
Events   : 38 | metadata: EVAL-2026-04-13-001
PII scans rows / cols : (40, 21)
Anomaly  rows / cols  : (50, 24)
EWMA     rows / cols  : (80, 11)
Blocked  rows / cols  : (8, 12)
First event id        : EVT-00001
```
