# reproduce.ps1 - regenerate every paper-v2 result from scratch and check it.
#
#   powershell -ExecutionPolicy Bypass -File .\reproduce.ps1            # full run
#   powershell -ExecutionPolicy Bypass -File .\reproduce.ps1 -Quick     # skip the slow multi-seed stages
#
# Uses .venv\Scripts\python.exe when it exists, otherwise `python`.
# Every stage writes its numbers into results\manifest.json (with run id, seeds,
# git hash and library versions). The last stage checks every claims file in
# results\claims against the manifest and fails the script on any mismatch.
param([switch]$Quick, [switch]$WithPII, [string]$VlmModel = "")

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$env:PYTHONUTF8 = "1"
$py = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
New-Item -ItemType Directory -Force -Path logs | Out-Null

function Stage([string]$name, [string[]]$pyArgs) {
    Write-Host "== $name"
    $log = "logs\reproduce_$($name -replace '[^A-Za-z0-9_.-]', '_').log"
    & $py @pyArgs *> $log
    if ($LASTEXITCODE -ne 0) {
        Get-Content $log -Tail 30
        throw "stage '$name' failed (exit $LASTEXITCODE); full log: $log"
    }
    Get-Content $log -Tail 3
}

$t0 = Get-Date
Stage "pytest"             @("-m", "pytest", "-q", "tests")
Stage "baseline_manifest"  @("-m", "tools.ingest_baseline")
Stage "generate_s42"       @("-m", "evaluation.generate_sessions", "--seed", "42")
Stage "train_s42"          @("-m", "evaluation.train_and_evaluate", "--seed", "42")
Stage "calibrate_sbrs"     @("-m", "evaluation.calibrate_sbrs")
if (-not $Quick) {
    # T1.4: 10 independently generated datasets (seeds in evaluation\config\seeds.json), ~13 min
    Stage "multiseed"      @("-m", "evaluation.multiseed")
}
Stage "ablation"           @("-m", "evaluation.ablation")          # T2.1, ~3.5 min
Stage "ablation_report"    @("-m", "evaluation.ablation_report")
Stage "drift_detector"     @("-m", "evaluation.drift_detector")    # T2.4, ~2 min
Stage "sbrs_fusion"        @("-m", "evaluation.sbrs_fusion")       # T2.5, <1 min
Stage "operating_points"   @("-m", "evaluation.operating_points")  # T2.7, <1 min
if (-not $Quick) {
    Stage "bootstrap"      @("-m", "evaluation.bootstrap_stats")   # T2.2, 10000 resamples, ~35 min
    Stage "difficulty_sweep" @("-m", "evaluation.difficulty_sweep") # T2.3, 27 new runs, ~45 min
}
# Later paper-v2 stages (ablation, statistics, PII) are appended below as their tasks land.

if ($WithPII) {
    # Phase 3 PII track (T3.1-T3.5). OCR stages are slow on CPU (EasyOCR ~20 min, PaddleOCR ~90 min).
    Stage "pii_corpus_v2"  @("-m", "evaluation.build_pii_corpus_v2")
    Stage "pii_easyocr"    @("-m", "evaluation.pii_v2", "ocr-easyocr")
    if (Test-Path ".venv-paddle\Scripts\python.exe") {
        Write-Host "== pii_paddleocr"
        & ".venv-paddle\Scripts\python.exe" "evaluation\paddle_ocr_runner.py" *> logs\reproduce_pii_paddleocr.log
    }
    if ($VlmModel) { Stage "pii_vlm" @("-m", "evaluation.pii_v2", "vlm", "--model", $VlmModel) }  # needs LM Studio running
    Stage "pii_presidio"   @("-m", "evaluation.pii_v2", "presidio")
    Stage "pii_score"      @("-m", "evaluation.pii_v2", "score")
}
Stage "check_numbers"      @("tools\check_numbers.py", "results\claims", "--quiet")
Write-Host ("reproduce.ps1 finished in {0:N1} min" -f ((Get-Date) - $t0).TotalMinutes)
