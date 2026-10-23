# ENVIRONMENT.md

Recorded 2026-10-23 during task T0.1. Update this file when the environment changes.

## Machine

| Item | Value |
|---|---|
| Laptop | ASUS TUF (per context.md) |
| OS | Windows 10 Home 10.0.19045 |
| CPU | 11th Gen Intel Core i7-11370H @ 3.30GHz |
| RAM | 15.7 GB |
| GPU | NVIDIA GeForce RTX 3060 Laptop GPU, 6144 MiB, driver 610.74 |
| Shells | PowerShell 7 (primary for the user), Git Bash (used by the agent) |

## Python interpreters

| Interpreter | Path | Notes |
|---|---|---|
| CPython 3.14.4 (default `python`) | `C:\Python314\python.exe` | Runs all evaluation code today. No paddlepaddle wheel. |
| CPython 3.13.5 | `C:\Users\loons\AppData\Local\Programs\Python\Python313\python.exe` | Listed by `py -0`. |
| CPython 3.14.5 (uv managed) | `%APPDATA%\uv\python\...` | Present. |
| CPython 3.11 / 3.12 | not installed | `uv python list` offers 3.11.15 and 3.12.13 as downloads (needed for PaddleOCR, T3.2). |

`py -0` output:

```
 -V:3.14 *        Python 3.14 (64-bit)
 -V:3.13          Python 3.13 (64-bit)
 -V:Astral/CPython3.14.5 CPython 3.14.5 (64-bit)
```

## Project virtual environment

`.venv` (gitignored) was created with `python -m venv --system-site-packages .venv` from CPython 3.14.4.
It inherits the scientific stack from the system interpreter and adds only what the project needs
on top (pytest so far). Nothing was installed into the system interpreter. The exact package
versions are pinned in `requirements-lock.txt` (written in T1.3 from `pip freeze`).

## Key library versions (system interpreter, 2026-10-23)

| Package | Version |
|---|---|
| torch | 2.13.0+cpu (CPU build) |
| numpy | 2.4.6 |
| pandas | 3.0.3 |
| scikit-learn | 1.9.0 |
| scipy | 1.18.0 |
| presidio_analyzer | 2.2.363 |
| spacy | 3.8.13 (model en_core_web_lg installed) |
| easyocr | 1.7.2 |
| Faker | 40.28.1 |
| pillow | 12.2.0 |
| opencv-python-headless | 5.0.0.93 |
| matplotlib | 3.10.9 |
| fastapi | 0.139.0 |
| uvicorn | 0.50.2 |
| openai | 2.44.0 |
| streamlit | 1.58.0 |
| pytest (in .venv) | 9.1.1 |

## GPU and torch

`torch.cuda.is_available()` returns **False**: the installed torch is the CPU build. The GPU is present
(RTX 3060 Laptop, 6 GB). Decision D-003 in `docs/DECISIONS.md`: the LSTM keeps training on CPU, because
the model is small and CPU training is bit-for-bit repeatable, which the determinism checks need.
Every results file records `device: cpu`. The GPU is used for the local VLM through LM Studio (T3.3).

## LM Studio

| Item | Value |
|---|---|
| CLI | `C:\Users\loons\.lmstudio\bin\lms.exe` |
| Server | ON at `http://localhost:1234` after `lms` woke the service (it was not answering before) |
| Models on disk | `qwen/qwen3-4b` (text), `qwen2.5-coder-7b-instruct` (text), `text-embedding-nomic-embed-text-v1.5` |
| Vision models on disk | **none** at 2026-10-23. A VLM must be downloaded for T3.3 (free, local). |

## Secrets

`.env` exists and is matched by `.gitignore` line 2 (`git check-ignore -v .env` confirms). It was not opened.
