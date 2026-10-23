#!/usr/bin/env bash
# reproduce.sh - regenerate every paper-v2 result from scratch and check it.
# Same stages as reproduce.ps1 (the Windows entry point). Usage: ./reproduce.sh [--quick]
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1
if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then PY=.venv/bin/python
else PY=python; fi
QUICK=0; [ "${1:-}" = "--quick" ] && QUICK=1
mkdir -p logs

stage() {
  local name="$1"; shift
  echo "== $name"
  if ! "$PY" "$@" > "logs/reproduce_${name}.log" 2>&1; then
    tail -30 "logs/reproduce_${name}.log"; echo "stage '$name' failed"; exit 1
  fi
  tail -3 "logs/reproduce_${name}.log"
}

t0=$(date +%s)
stage pytest            -m pytest -q tests
stage baseline_manifest -m tools.ingest_baseline
stage generate_s42      -m evaluation.generate_sessions --seed 42
stage train_s42         -m evaluation.train_and_evaluate --seed 42
stage calibrate_sbrs    -m evaluation.calibrate_sbrs
if [ "$QUICK" = 0 ]; then
  stage multiseed       -m evaluation.multiseed   # T1.4, 10 datasets, ~13 min
fi
stage ablation          -m evaluation.ablation          # T2.1, ~3.5 min
stage ablation_report   -m evaluation.ablation_report
stage drift_detector    -m evaluation.drift_detector    # T2.4, ~2 min
stage sbrs_fusion       -m evaluation.sbrs_fusion       # T2.5, <1 min
stage operating_points  -m evaluation.operating_points  # T2.7, <1 min
if [ "$QUICK" = 0 ]; then
  stage bootstrap       -m evaluation.bootstrap_stats   # T2.2, ~35 min
  stage difficulty_sweep -m evaluation.difficulty_sweep # T2.3, ~45 min
fi
# Later paper-v2 stages are appended here as their tasks land.

if [ "${WITH_PII:-0}" = 1 ]; then   # Phase 3 PII track; slow OCR stages
  stage pii_corpus_v2   -m evaluation.build_pii_corpus_v2
  stage pii_easyocr     -m evaluation.pii_v2 ocr-easyocr
  [ -x .venv-paddle/Scripts/python.exe ] && .venv-paddle/Scripts/python.exe evaluation/paddle_ocr_runner.py > logs/reproduce_pii_paddleocr.log 2>&1
  [ -n "${VLM_MODEL:-}" ] && stage pii_vlm -m evaluation.pii_v2 vlm --model "$VLM_MODEL"
  stage pii_presidio    -m evaluation.pii_v2 presidio
  stage pii_score       -m evaluation.pii_v2 score
fi
stage check_numbers     tools/check_numbers.py results/claims --quiet
echo "reproduce.sh finished in $(( ($(date +%s) - t0) / 60 )) min (quick=$QUICK)"
