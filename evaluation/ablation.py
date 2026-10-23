"""
ablation.py
===========
Paper-v2 task T2.1: detector and fusion ablation on IDENTICAL splits.

For one run folder (results/runs/data_seed_<s>/, produced by multiseed.py) this
reloads the trained artefacts of that run, recomputes every detector score for
every scoreable session WITHOUT rounding, and evaluates all detectors the same
way:

  detectors   ewma            univariate EWMA relative deviation (legacy comparator)
              zscore          per-user z-score: max_j |z_j| of x_t in the user's FIT frame
              lstm            memory-bank cosine of the LSTM encoding (paper's a_LSTM)
              lstm_nextstep   next-step prediction error of the same LSTM (sequence baseline)
              iforest         Isolation Forest (paper's a_IF)
              lof             Local Outlier Factor, novelty mode, fitted on FIT (unsupervised baseline)
  fusions     hybrid_weighted alpha*a_LSTM + (1-alpha)*a_IF, alpha from the val search (current)
              hybrid_max      max(a_LSTM, a_IF)
              hybrid_rankavg  mean of the two scores' empirical CDFs, CDFs fitted on CALIB

All continuous scores are mapped to [0,1] by a RobustCalibrator fitted on the
CALIB window (train period), exactly like a_LSTM and a_IF. Every threshold is
chosen on VAL by evaluation/selection.py (which rejects test rows). TEST is
scored once per detector.

Metrics (test): AUC, average precision, recall at 1% and 5% FPR read off the
test ROC curve (threshold-free curve summaries, like AUC), recall and realised
FPR at thresholds set on VAL for 1% and 5% FPR (the operational version), and
precision/recall/F1/FPR at the VAL-F1-optimal threshold. Per attack class:
AUC, window recall and episode recall at the VAL-F1 threshold. Benign bursts:
flag rate at the VAL-F1 threshold.

Sanity check: the recomputed a_LSTM, a_IF and hybrid must equal the rounded
columns of that run's scored_all_splits.csv to within 1e-4; the script fails
otherwise.

Outputs: <run>/ablation/row_scores.csv (per-row scores, used by the bootstrap
in T2.2), <run>/ablation/ablation_metrics.json, manifest keys ablation.ds<s>.*

    python -m evaluation.ablation --seeds 42 7 ...     (default: config seeds)
"""
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_curve
from sklearn.neighbors import LocalOutlierFactor

from evaluation.common import (EWMA_LAMBDA, FEATURES, SEQ_LEN, THREAT_CLASSES,
                               RobustCalibrator, binary_metrics, ewma_stream,
                               time_boundaries)
from evaluation.multiseed import RUNS, seeds_from_config
from evaluation.selection import (auc_rank, choose_by_val_auc, threshold_at_fpr,
                                  threshold_max_f1)
from evaluation.train_and_evaluate import (BehaviouralLSTM, build_personal_grids,
                                           l2norm, memory_bank_distance,
                                           windows_ending_at)
from tools.manifest import provenance, record

DETECTORS = ("ewma", "zscore", "lstm", "lstm_nextstep", "iforest", "lof",
             "hybrid_weighted", "hybrid_max", "hybrid_rankavg")
# LOF neighbour count, chosen per run by validation AUC (selection.choose_by_val_auc).
# The grid was widened after a first seed-42 run at the sklearn default k=20 gave
# below-chance AUC: injected attack episodes inside FIT form small dense clusters,
# so small-k LOF sees attacks as locally normal. See docs/DECISIONS.md D-008.
LOF_GRID = (20, 50, 100, 200, 300, 500)


class ECDF:
    """Empirical CDF fitted on calibration scores (rank transform without test data)."""

    def __init__(self, ref: np.ndarray):
        self.ref = np.sort(np.asarray(ref, dtype=float))

    def __call__(self, x: np.ndarray) -> np.ndarray:
        return np.searchsorted(self.ref, np.asarray(x, dtype=float), side="right") / len(self.ref)


def recall_at_fpr_curve(y: np.ndarray, s: np.ndarray, target: float) -> float:
    fpr, tpr, _ = roc_curve(y, s)
    ok = fpr <= target + 1e-12
    return float(tpr[ok].max()) if ok.any() else 0.0


def compute_scores(base: Path) -> pd.DataFrame:
    data, run = base / "data", base / "run"
    df = pd.read_csv(data / "sessions_raw.csv", parse_dates=["timestamp"])
    df["threat_class"] = df["threat_class"].where(df["threat_class"].notna(), None)
    total = int(df.hour_index.max()) + 1
    b = time_boundaries(total)

    with open(run / "artifacts" / "engine.pkl", "rb") as f:
        art = pickle.load(f)
    ckpt = torch.load(run / "artifacts" / "lstm.pt", map_location="cpu", weights_only=False)
    model = BehaviouralLSTM()
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    grids, stats = build_personal_grids(df, b["fit_end"])
    for u, (mu, sd) in stats.items():                  # same frame as the trained engine
        assert np.allclose(mu, art["user_stats"][u][0]) and np.allclose(sd, art["user_stats"][u][1])

    df["scoreable"] = df.active & (df.hour_index >= SEQ_LEN - 1)
    rows = df[df.scoreable].copy()
    users, hours = rows.user_id.to_numpy(), rows.hour_index.to_numpy().astype(int)

    W = np.stack([windows_ending_at(grids[u], t) for u, t in zip(users, hours)])
    with torch.no_grad():
        H = l2norm(torch.cat([model.encode(torch.from_numpy(W[i:i + 2048]))
                              for i in range(0, len(W), 2048)]).numpy())
        has_prev = hours >= SEQ_LEN
        Wp = np.stack([grids[u][t - SEQ_LEN:t] for u, t in zip(users[has_prev], hours[has_prev])])
        Yp = np.stack([grids[u][t] for u, t in zip(users[has_prev], hours[has_prev])])
        pe = torch.cat([((model(torch.from_numpy(Wp[i:i + 2048])) -
                          torch.from_numpy(Yp[i:i + 2048])) ** 2).mean(dim=1)
                        for i in range(0, len(Wp), 2048)]).numpy()
    pred_err = np.full(len(rows), np.nan)
    pred_err[has_prev] = pe

    lstm_raw = np.zeros(len(rows))
    for u in np.unique(users):
        m = users == u
        lstm_raw[m] = memory_bank_distance(H[m], art["banks"][u], int(art["topk"]))
    Xg = art["scaler"].transform(rows[list(FEATURES)].to_numpy())
    if_raw = -art["iforest"].score_samples(Xg)
    z = np.stack([grids[u][t] for u, t in zip(users, hours)])
    z_raw = np.abs(z).max(axis=1)

    fit_rows = df[(df.hour_index < b["fit_end"]) & df.active]
    Xfit = art["scaler"].transform(fit_rows[list(FEATURES)].to_numpy())
    val = (hours >= b["train_end"]) & (hours < b["val_end"])
    yv = rows.is_true_threat.to_numpy(dtype=bool)[val]
    lof_by_k = {k: -LocalOutlierFactor(n_neighbors=k, novelty=True).fit(Xfit).score_samples(Xg)
                for k in LOF_GRID}
    lof_k, lof_val_aucs = choose_by_val_auc({k: v[val] for k, v in lof_by_k.items()}, yv,
                                            rows.split.to_numpy()[val])
    lof_raw = lof_by_k[lof_k]

    ewma_dev = np.full(len(df), np.nan)
    for _, g in df[df.active].groupby("user_id", sort=False):
        g = g.sort_values("hour_index")
        ewma_dev[g.index.to_numpy()] = ewma_stream(g.activity_rate_per_hr.to_numpy(), EWMA_LAMBDA)[2]
    rows["score_ewma"] = ewma_dev[rows.index.to_numpy()]

    calib = (hours >= b["calib_lo"]) & (hours < b["train_end"])
    a_lstm = art["cal_lstm"].transform(lstm_raw)
    a_if = art["cal_if"].transform(if_raw)
    rows["score_lstm"] = a_lstm
    rows["score_iforest"] = a_if
    pe_ok = calib & ~np.isnan(pred_err)
    rows["score_lstm_nextstep"] = RobustCalibrator().fit(pred_err[pe_ok]).transform(
        np.nan_to_num(pred_err, nan=np.nanmedian(pred_err[pe_ok])))
    rows["score_zscore"] = RobustCalibrator().fit(z_raw[calib]).transform(z_raw)
    rows["score_lof"] = RobustCalibrator().fit(lof_raw[calib]).transform(lof_raw)
    alpha = float(art["alpha"])
    rows["score_hybrid_weighted"] = alpha * a_lstm + (1 - alpha) * a_if
    rows["score_hybrid_max"] = np.maximum(a_lstm, a_if)
    e_l, e_i = ECDF(lstm_raw[calib]), ECDF(if_raw[calib])
    rows["score_hybrid_rankavg"] = 0.5 * (e_l(lstm_raw) + e_i(if_raw))

    # sanity: recomputed scores reproduce the trained run's scored CSV
    sc = pd.read_csv(run / "scored_all_splits.csv").set_index("event_id")
    chk = rows.set_index("event_id").loc[sc.index]
    for col, ref in (("score_lstm", "lstm_score"), ("score_iforest", "isolation_forest_score"),
                     ("score_hybrid_weighted", "hybrid_anomaly_score")):
        err = float(np.abs(chk[col].to_numpy() - sc[ref].to_numpy()).max())
        if err > 1e-4 + 1e-9:
            raise SystemExit(f"{base}: recomputed {col} differs from {ref} by {err}")
    rows["alpha"] = alpha
    rows["lof_k"] = lof_k
    # raw (unclipped) single-detector scores: the RobustCalibrator clips everything
    # below the CALIB median to 0, which creates ties and changes AUC slightly
    rows["raw_lstm"], rows["raw_iforest"], rows["raw_zscore"] = lstm_raw, if_raw, z_raw
    rows["raw_lof"], rows["raw_lstm_nextstep"] = lof_raw, pred_err
    keep = ["event_id", "user_id", "hour_index", "split", "is_true_threat", "threat_class",
            "is_benign_burst", "episode_id", "pii_sensitivity_score", "alpha", "lof_k",
            *[f"score_{d}" for d in DETECTORS],
            "raw_lstm", "raw_iforest", "raw_zscore", "raw_lof", "raw_lstm_nextstep"]
    return rows[keep].reset_index(drop=True)


def evaluate(rows: pd.DataFrame) -> Dict[str, dict]:
    split = rows.split.to_numpy()
    y = rows.is_true_threat.to_numpy(dtype=bool)
    tc = rows.threat_class.to_numpy()
    eid = rows.episode_id.to_numpy()
    bb = rows.is_benign_burst.to_numpy(dtype=bool)
    v, te = split == "val", split == "test"
    out = {"_params": {"alpha": float(rows.alpha.iloc[0]), "lof_k": int(rows.lof_k.iloc[0])}}
    for d in DETECTORS:
        s = rows[f"score_{d}"].to_numpy(dtype=float)
        t_f1, val_f1 = threshold_max_f1(s[v], y[v], split[v])
        t1 = threshold_at_fpr(s[v], y[v], split[v], 0.01)
        t5 = threshold_at_fpr(s[v], y[v], split[v], 0.05)
        yt, st = y[te], s[te]
        flag = s >= t_f1
        m = binary_metrics(yt, flag[te])
        raw_col = f"raw_{d}"
        res = {
            "auc": auc_rank(st, yt),
            "auc_raw_unclipped": (auc_rank(rows[raw_col].to_numpy(dtype=float)[te & np.isfinite(rows[raw_col].to_numpy(dtype=float))],
                                           yt[np.isfinite(rows[raw_col].to_numpy(dtype=float))[te]])
                                  if raw_col in rows else float("nan")),
            "average_precision": float(average_precision_score(yt, st)),
            "recall_at_fpr01_testcurve": recall_at_fpr_curve(yt, st, 0.01),
            "recall_at_fpr05_testcurve": recall_at_fpr_curve(yt, st, 0.05),
            "recall_at_fpr01_valthreshold": float((st[yt] >= t1).mean()),
            "fpr_realised_at_fpr01_valthreshold": float((st[~yt] >= t1).mean()),
            "recall_at_fpr05_valthreshold": float((st[yt] >= t5).mean()),
            "fpr_realised_at_fpr05_valthreshold": float((st[~yt] >= t5).mean()),
            "val_threshold_f1": t_f1, "val_f1": val_f1,
            "threshold_fpr01": t1, "threshold_fpr05": t5,
            **{f"valf1_{k}": m[k] for k in ("tp", "fp", "fn", "tn", "precision", "recall", "f1", "fpr")},
            "benign_burst_flag_rate": float(flag[te & bb].mean()) if (te & bb).any() else float("nan"),
            "per_class": {},
        }
        neg_te = te & ~y
        for c in THREAT_CLASSES:
            sel = te & (tc == c)
            if not sel.any():
                continue
            eps = pd.unique(eid[sel])
            res["per_class"][c] = {
                "windows": int(sel.sum()), "episodes": int(len(eps)),
                "auc": auc_rank(np.r_[s[sel], s[neg_te]],
                                np.r_[np.ones(sel.sum(), bool), np.zeros(neg_te.sum(), bool)]),
                "recall": float(flag[sel].mean()),
                "episode_recall": float(np.mean([flag[te & (eid == e)].any() for e in eps])),
            }
        out[d] = res
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    args = ap.parse_args()
    seeds = args.seeds or seeds_from_config()
    for s in seeds:
        base = RUNS / f"data_seed_{s}"
        rows = compute_scores(base)
        res = evaluate(rows)
        outd = base / "ablation"
        outd.mkdir(parents=True, exist_ok=True)
        rows.to_csv(outd / "row_scores.csv", index=False)
        (outd / "ablation_metrics.json").write_text(json.dumps(
            {"provenance": provenance("evaluation/ablation.py", {"data_and_train": s}, "cpu"),
             "detectors": res}, indent=1, default=float), encoding="utf-8")
        record(f"ablation.ds{s}", res, script="evaluation/ablation.py",
               seeds={"data_and_train": s}, device="cpu")
        print(f"[seed {s}] " + "  ".join(f"{d}:AUC={res[d]['auc']:.3f}/F1={res[d]['valf1_f1']:.3f}"
                                         for d in DETECTORS), flush=True)


if __name__ == "__main__":
    main()
