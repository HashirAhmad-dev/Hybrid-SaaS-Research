"""
cert_rich_importance.py
=======================
Which inputs the BASE boosting probe of evaluation/cert_rich.py relies on (D-027 follow-up).
Permutation importance on VALIDATION hours (drop in validation AUC when one feature's
current and lagged columns are shuffled together), so the test split is not used.

    python -m evaluation.cert_rich_importance
"""
from __future__ import annotations

import json

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from evaluation import cert_rich as c
from evaluation import selection
from evaluation.common import FEATURES, SEQ_LEN, time_boundaries
from tools.manifest import provenance, record

N_REPEATS = 5


def main() -> None:
    df = c.load_rows()
    b = time_boundaries(df.attrs["H"])
    df = df[df.hour_index >= SEQ_LEN - 1].reset_index(drop=True)
    y = df.is_true_threat.to_numpy(dtype=bool)
    split = df.split.to_numpy()
    fit = df.hour_index.to_numpy() < b["fit_end"]
    feats = list(FEATURES)
    Z = c.personal_z(df, feats, fit)
    P = np.hstack([Z, c.lagged(df, Z)])
    tr, va = split == "train", split == "val"
    gb = HistGradientBoostingClassifier(random_state=c.SEED, class_weight="balanced").fit(P[tr], y[tr])
    base_auc = selection.auc_rank(gb.predict_proba(P[va])[:, 1], y[va])
    rng = np.random.default_rng(c.SEED)
    imp = {}
    F = len(feats)
    for j, f in enumerate(feats):
        drops = []
        for _ in range(N_REPEATS):
            Q = P[va].copy()
            perm = rng.permutation(len(Q))
            Q[:, [j, F + j]] = Q[perm][:, [j, F + j]]
            drops.append(base_auc - selection.auc_rank(gb.predict_proba(Q)[:, 1], y[va]))
        imp[f] = float(np.mean(drops))
        print(f"  {f:24s} val AUC drop {imp[f]:+.4f}", flush=True)
    out = {"val_auc": base_auc, "val_auc_drop_when_shuffled": imp}
    (c.OUT / "rich_importance.json").write_text(json.dumps(
        {"results": out, "provenance": provenance("evaluation/cert_rich_importance.py", {"model_and_shuffle": c.SEED})},
        indent=1), encoding="utf-8")
    record("cert.rich_importance", out, script="evaluation/cert_rich_importance.py", seeds={"model_and_shuffle": c.SEED})
    print(f"val AUC {base_auc:.3f}")


if __name__ == "__main__":
    main()
