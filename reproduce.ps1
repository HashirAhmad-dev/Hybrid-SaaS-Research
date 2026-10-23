# reproduce.ps1 - regenerate every paper-v2 result from scratch and check it.
#
#   powershell -ExecutionPolicy Bypass -File .\reproduce.ps1            # full run
#   powershell -ExecutionPolicy Bypass -File .\reproduce.ps1 -Quick     # skip the slow multi-seed stages
#
# Uses .venv\Scripts\python.exe when it exists, otherwise `python`.
# Every stage writes its numbers into results\manifest.json (with run id, seeds,
# git hash and library versions). The last stage checks every claims file in
# results\claims against the manifest and fails the script on any mismatch.
param([switch]$Quick)

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
Stage "baseline_manifest"  @("-m", "tools.ingest_baseline")
Stage "generate_s42"       @("-m", "evaluation.generate_sessions", "--seed", "42")
Stage "train_s42"          @("-m", "evaluation.train_and_evaluate", "--seed", "42")
Stage "calibrate_sbrs"     @("-m", "evaluation.calibrate_sbrs")
# Later paper-v2 stages (multi-seed datasets, ablation, statistics, PII) are
# appended below as their tasks land.

Stage "check_numbers"      @("tools\check_numbers.py", "results\claims", "--quiet")
Write-Host ("reproduce.ps1 finished in {0:N1} min" -f ((Get-Date) - $t0).TotalMinutes)
