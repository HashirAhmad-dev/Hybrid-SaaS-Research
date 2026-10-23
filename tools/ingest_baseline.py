"""
ingest_baseline.py
==================
Record the pre-paper-v2 results (frozen in results/baseline_20261023/) in
results/manifest.json under the `baseline.*` prefix, so every number that the
submitted paper or context.md quoted can be checked by tools/check_numbers.py.

These files were produced before the manifest existed, by commits 69ef162
(2026-07-09) and 9b4f86b (2026-07-12). The run entry records that, and the
tagged baseline commit 2521134 that contains them.

    python -m tools.ingest_baseline
"""
from __future__ import annotations

import json
from pathlib import Path

from tools.manifest import PROJECT_ROOT, record

BASE = PROJECT_ROOT / "results" / "baseline_20261023"

FILES = {
    # prefix                              file                          what it is
    "baseline.anomaly.s42":               "metrics.json",               # current, SBRS refreshed to beta 2.5
    "baseline.anomaly.seedfile.s42":      "metrics_seed42.json",        # pre-refresh, enforcement at beta 0.5
    "baseline.anomaly.seedfile.s7":       "metrics_seed7.json",
    "baseline.anomaly.seedfile.s2024":    "metrics_seed2024.json",
    "baseline.generation":                "generation_config.json",
    "baseline.sbrs":                      "sbrs_calibration.json",
    "baseline.pii.gemma4b":               "pii_metrics_google-gemma-3-4b-it-deepinfra.json",
    "baseline.pii.qwen72b":               "pii_metrics_Qwen-Qwen2-5-VL-72B-Instruct-ovhcloud.json",
    "baseline.pii.partial_qwen72b":       "pii_metrics_Qwen-Qwen2-5-VL-72B-Instruct.json",
    "baseline.pii.partial_default":       "pii_metrics.json",
}


def main() -> None:
    git = {"git_hash": "25211343bf8a3bd6840fd4250974e7ce74dbb4e9", "git_dirty": False}
    for prefix, name in FILES.items():
        data = json.loads((BASE / name).read_text(encoding="utf-8"))
        seed = data.get("args", {}).get("seed") if name == "generation_config.json" else None
        record(prefix, data, script=f"results/baseline_20261023/{name}",
               run_id="baseline_20261023", git=git,
               date_utc="2026-07-12T13:04:30+00:00",
               seeds={"data": 42, "train": seed or "see file"},
               note="Ingested from files produced before paper-v2 (commits 69ef162, 9b4f86b). "
                    "Tag baseline-pre-v2 = 2521134 contains them unchanged.")
        print(f"recorded {prefix} <- {name}")

    # The 3-seed summary quoted in REAL_RESULTS.md section 4: mean and POPULATION
    # standard deviation (numpy default, ddof=0) over the seed files 42 / 7 / 2024.
    # Only training varied across those seeds; the dataset was the seed-42 one.
    import numpy as np
    from tools.manifest import flatten
    flats = [flatten(json.loads((BASE / f"metrics_seed{s}.json").read_text(encoding="utf-8")))
             for s in (42, 7, 2024)]
    keys = [k for k in flats[0] if all(k in f for f in flats)
            and not k.startswith(("tuning.alpha_grid", "lstm_val_mse_history"))]
    summary = {}
    for k in keys:
        v = np.array([f[k] for f in flats], dtype=float)
        summary[k] = {"mean": float(v.mean()), "sd_pop": float(v.std()),
                      "sd_sample": float(v.std(ddof=1))}
    record("baseline.anomaly.train3seed", summary,
           script="tools/ingest_baseline.py (summary of metrics_seed{42,7,2024}.json)",
           run_id="baseline_20261023", git=git, date_utc="2026-07-12T13:04:30+00:00",
           seeds={"data": 42, "train": [42, 7, 2024]},
           note="Training-seed spread only; one generated dataset (data seed 42).")
    print(f"recorded baseline.anomaly.train3seed ({len(summary)} keys)")


if __name__ == "__main__":
    main()
