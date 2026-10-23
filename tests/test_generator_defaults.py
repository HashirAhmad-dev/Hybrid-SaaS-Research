"""T2.3: the difficulty knobs at their defaults reproduce the original dataset byte for byte."""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# sha256 of evaluation/data/sessions_raw.csv at tag baseline-pre-v2 (results/baseline_20261023/SHA256SUMS_large_files.txt)
BASELINE_SEED42 = "0519d04e9026a70dcb22b66ba9e5afebc7a72b3368c13ff2461186177579e94a"


def test_default_knobs_reproduce_baseline_dataset(tmp_path):
    out = tmp_path / "gen"
    r = subprocess.run([sys.executable, "-m", "evaluation.generate_sessions", "--seed", "42",
                        "--intensity", "1.0", "--benign-overlap", "0.0", "--out-dir", str(out)],
                       cwd=ROOT, capture_output=True, text=True,
                       env={**__import__("os").environ, "PYTHONUTF8": "1",
                            "HYBRIDSAAS_MANIFEST_READONLY": "1"})
    assert r.returncode == 0, r.stderr[-2000:]
    digest = hashlib.sha256((out / "sessions_raw.csv").read_bytes()).hexdigest()
    assert digest == BASELINE_SEED42
