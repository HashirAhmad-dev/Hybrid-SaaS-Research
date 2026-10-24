# REST Endpoints (FastAPI)

The FastAPI backend exposes the following REST endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/`                        | Health + dataset summary |
| `GET`  | `/metrics`                 | Paper-published metrics (FPR, F1, coverage) |
| `GET`  | `/events?limit=N`          | List of intercepted events |
| `GET`  | `/events/{event_id}`       | Raw event payload |
| `GET`  | `/score/{event_id}`        | Full pipeline result (PII + Anomaly + SBRS) |
| `POST` | `/score`                   | Score an arbitrary event payload |
| `GET`  | `/baselines`               | Legacy EWMA per-user baselines (8 windows) |
| `GET`  | `/audit/blocked`           | Audit trail of BLOCK enforcement actions |
| `GET`  | `/comparison`              | Tidy EWMA vs Hybrid per-event evaluation |

You can use query parameters `alpha` (LSTM weight; default read from the trained engine, 0.25) and `beta` (enterprise risk multiplier, default 2.5) on `/score` to replay the simulation under different SBRS configurations.

Two-tier endpoints (paper-v2): `POST /tier1/score` (inline decision with per-stage timings and the configured gated enforcement), `POST /tier2/submit` and `GET /tier2/{job_id}` (hold an image upload and scan it asynchronously: OCR, then the local VLM when OCR confidence is below the calibrated tau_ocr; release, escalate, or quarantine if the VLM is unreachable). The configuration and the manifest key behind every value are in `backend/config/final_config.json`.
