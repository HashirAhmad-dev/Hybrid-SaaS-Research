"""
transfer_standardise.py
=======================
Task F11 (D-033): simulator to CERT transfer of the supervised probes under three
per-user standardisations (z, robust z, rank), with the sign flip made explicit and
the coefficient signs of simulator-trained and CERT-trained logistic regression compared.

    python -m evaluation.transfer_standardise
Outputs: results/supervised/transfer_standardise.json, manifest keys transfer_std.*
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from evaluation import selection
from evaluation.cert_rich import SEED, lagged
from evaluation.common import FEATURES, SEQ_LEN, time_boundaries
from evaluation.supervised_multiseed import SEEDS, load_rows
from evaluation.supervised_transfer import cert_rows
from tools.manifest import PROJECT_ROOT, provenance, record

OUT = PROJECT_ROOT / "results" / "supervised"
SD_FLOOR, CLIP = 0.1, 10.0


def per_user(df: pd.DataFrame, fit: np.ndarray, kind: str) -> np.ndarray:
    X = df[list(FEATURES)].to_numpy(float)
    Z = np.zeros_like(X)
    for _, idx in df.groupby("user_id", sort=False).indices.items():
        f = idx[fit[idx]]
        ref = X[f] if len(f) else X[idx]
        if kind == "z":
            mu, sd = ref.mean(0), np.maximum(ref.std(0), SD_FLOOR)
            Z[idx] = np.clip((X[idx] - mu) / sd, -CLIP, CLIP)
        elif kind == "robust_z":
            med = np.median(ref, 0)
            iqr = np.percentile(ref, 75, 0) - np.percentile(ref, 25, 0)
            Z[idx] = np.clip((X[idx] - med) / np.maximum(iqr / 1.349, SD_FLOOR), -CLIP, CLIP)
        else:                                             # rank against the user's FIT values
            srt = np.sort(ref, 0)
            for j in range(X.shape[1]):
                lo = np.searchsorted(srt[:, j], X[idx, j], side="left")
                hi = np.searchsorted(srt[:, j], X[idx, j], side="right")
                Z[idx, j] = (lo + hi) / (2.0 * len(srt)) - 0.5
    return np.hstack([Z, lagged(df, Z)])


def prepared(df: pd.DataFrame):
    b = time_boundaries(df.attrs["H"])
    df = df[df.hour_index >= SEQ_LEN - 1].reset_index(drop=True)
    return df, df.hour_index.to_numpy() < b["fit_end"]


def main() -> None:
    t0 = time.time()
    sims = [prepared(load_rows(s)) for s in SEEDS]
    cdf, cfit = prepared(cert_rows())
    cy = cdf.is_true_threat.to_numpy(bool)
    csplit = cdf.split.to_numpy()
    te, tr_c = csplit == "test", csplit == "train"
    res = {}
    coef = {}
    for kind in ("z", "robust_z", "rank"):
        Ps, ys = [], []
        for df, fit in sims:
            P = per_user(df, fit, kind)
            tr = df.split.to_numpy() == "train"
            Ps.append(P[tr]); ys.append(df.is_true_threat.to_numpy(bool)[tr])
        Ptr, ytr = np.vstack(Ps), np.concatenate(ys)
        CP = per_user(cdf, cfit, kind)
        models = {"logistic": LogisticRegression(max_iter=2000, class_weight="balanced").fit(Ptr, ytr),
                  "boosting": HistGradientBoostingClassifier(random_state=SEED, class_weight="balanced").fit(Ptr, ytr)}
        for m, est in models.items():
            a = selection.auc_rank(est.predict_proba(CP)[:, 1][te], cy[te])
            res.setdefault(kind, {})[m] = {"auc": a, "auc_of_negated_score": 1.0 - a, "sign_flipped": float(a < 0.5)}
            print(f"  {kind:9s} {m:9s} CERT test AUC {a:.3f}  (negated {1 - a:.3f})", flush=True)
        if kind == "z":
            coef["simulator"] = models["logistic"].coef_.ravel()[:len(FEATURES)]
            cert_lr = LogisticRegression(max_iter=2000, class_weight="balanced").fit(CP[tr_c], cy[tr_c])
            coef["cert"] = cert_lr.coef_.ravel()[:len(FEATURES)]
            res["cert_trained_logistic_auc"] = selection.auc_rank(cert_lr.predict_proba(CP)[:, 1][te], cy[te])
    res["coefficients_current_hour"] = {
        f: {"simulator": float(coef["simulator"][j]), "cert": float(coef["cert"][j]),
            "same_sign": float(np.sign(coef["simulator"][j]) == np.sign(coef["cert"][j]))}
        for j, f in enumerate(FEATURES)}
    res["n_features_sign_flipped"] = float(sum(1 - v["same_sign"] for v in res["coefficients_current_hour"].values()))
    res["_meta"] = {"minutes": (time.time() - t0) / 60, "decision": "docs/DECISIONS.md D-033"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "transfer_standardise.json").write_text(json.dumps(
        {"results": res, "provenance": provenance("evaluation/transfer_standardise.py", {"data_seeds": SEEDS, "models": SEED})},
        indent=1), encoding="utf-8")
    record("transfer_std", res, script="evaluation/transfer_standardise.py", seeds={"data_seeds": SEEDS, "models": SEED})
    for f, v in res["coefficients_current_hour"].items():
        print(f"  {f:24s} sim {v['simulator']:+.3f}  cert {v['cert']:+.3f}  {'same' if v['same_sign'] else 'FLIPPED'}")
    print(f"  CERT-trained logistic AUC {res['cert_trained_logistic_auc']:.3f}")


if __name__ == "__main__":
    main()
