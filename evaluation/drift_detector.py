"""
drift_detector.py
=================
Paper-v2 task T2.4: a dedicated detector for slow malicious-insider drift, run
NEXT TO the hybrid engine (reviewer 4 asked for a concrete architectural fix,
for example "a secondary dedicated detector").

Signal: each user's personal z-scores (the same FIT-period frame the LSTM uses)
on the six features, taken over that user's ACTIVE hours in time order. Idle
hours are skipped: they carry no transaction.

Detectors (both generic: no feature is singled out by hand)
  cusum  two-sided CUSUM per feature, S+ = max(0, S+ + z - k), S- = max(0, S- - z - k);
         alarm when max over features and sides exceeds h; all statistics of
         that user reset to 0 after an alarm.
  ph     Page-Hinkley per feature: cumulative deviation of z from its running
         mean, two-sided, drift allowance k, alarm at h, reset after alarm.

The statistics run continuously over the whole timeline (as in deployment).
(k, h) are chosen on VALIDATION ONLY by `selection.choose_drift_params`:
maximise validation malicious-insider EPISODE recall subject to a false-alarm
budget on validation negative active hours (default 1 percent of them), ties
broken by fewer false alarms.

Reported on TEST: episode recall per class, time to detect in hours (first
alarm hour minus first hour of the episode, alarms inside the episode only),
false-alarm rate on ordinary negative active hours and on benign-burst hours,
and the combined system "hybrid flag OR drift alarm" (recall, FPR, F1).

Supervised-probe upper bound: a logistic regression trained WITH labels on the
TRAIN split (current personal z plus the mean personal z of the user's previous
8 active hours, 12 features), threshold chosen on validation. It shows how much
signal is in the data for a detector that is allowed to see labels; it is not a
deployable unsupervised method.

    python -m evaluation.drift_detector [--seeds ...]
Outputs: <run>/drift/drift_metrics.json, manifest keys drift.ds<s>.*, drift.summary.*,
         results/drift/drift_summary.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import pickle
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from evaluation import selection
from evaluation.common import FEATURES, THREAT_CLASSES, binary_metrics, time_boundaries
from evaluation.multiseed import RUNS, seeds_from_config
from evaluation.train_and_evaluate import build_personal_grids
from tools.manifest import PROJECT_ROOT, load, provenance, record

OUT = PROJECT_ROOT / "results" / "drift"
K_GRID = (0.25, 0.5, 1.0, 1.5)
H_GRID = tuple(float(x) for x in np.arange(2.0, 40.01, 1.0))
FALSE_ALARM_BUDGET = 0.01            # share of validation negative active hours
PROBE_LAGS = 8


def run_detector(z: np.ndarray, k: float, h: float, kind: str) -> np.ndarray:
    """Alarm flags for one user's active-hour sequence z (T, 6)."""
    T, F = z.shape
    alarm = np.zeros(T, dtype=bool)
    sp, sn = np.zeros(F), np.zeros(F)
    mean, n, cum_p, cum_n = np.zeros(F), 0, np.zeros(F), np.zeros(F)
    for t in range(T):
        x = z[t]
        if kind == "cusum":
            sp = np.maximum(0.0, sp + x - k)
            sn = np.maximum(0.0, sn - x - k)
            stat = max(sp.max(), sn.max())
        else:                                   # Page-Hinkley, two-sided
            n += 1
            mean = mean + (x - mean) / n
            cum_p = np.maximum(0.0, cum_p + x - mean - k)
            cum_n = np.maximum(0.0, cum_n - (x - mean) - k)
            stat = max(cum_p.max(), cum_n.max())
        if stat > h:
            alarm[t] = True
            sp[:], sn[:], cum_p[:], cum_n[:] = 0.0, 0.0, 0.0, 0.0
            mean[:], n = 0.0, 0
    return alarm


def personal_active_z(base: Path) -> Tuple[pd.DataFrame, Dict[str, np.ndarray], dict]:
    df = pd.read_csv(base / "data" / "sessions_raw.csv")
    df["threat_class"] = df["threat_class"].where(df["threat_class"].notna(), None)
    b = time_boundaries(int(df.hour_index.max()) + 1)
    grids, _ = build_personal_grids(df, b["fit_end"])
    act = df[df.active].sort_values(["user_id", "hour_index"]).copy()
    zs = {u: grids[u][g.hour_index.to_numpy()] for u, g in act.groupby("user_id", sort=False)}
    return act, zs, b


def run_detector_batch(Z: np.ndarray, valid: np.ndarray, k: float, h: float, kind: str) -> np.ndarray:
    """Vectorised over users: Z (U, T, F) padded, valid (U, T). Same arithmetic as run_detector."""
    U, T, F = Z.shape
    alarm = np.zeros((U, T), dtype=bool)
    sp, sn = np.zeros((U, F)), np.zeros((U, F))
    mean, n = np.zeros((U, F)), np.zeros((U, 1))
    for t in range(T):
        v = valid[:, t][:, None]
        x = Z[:, t]
        if kind == "cusum":
            sp = np.where(v, np.maximum(0.0, sp + x - k), sp)
            sn = np.where(v, np.maximum(0.0, sn - x - k), sn)
        else:
            n = np.where(v, n + 1, n)
            mean = np.where(v, mean + (x - mean) / np.maximum(n, 1), mean)
            sp = np.where(v, np.maximum(0.0, sp + x - mean - k), sp)
            sn = np.where(v, np.maximum(0.0, sn - (x - mean) - k), sn)
        stat = np.maximum(sp.max(axis=1), sn.max(axis=1))
        fire = (stat > h) & valid[:, t]
        alarm[:, t] = fire
        if fire.any():
            sp[fire] = 0.0; sn[fire] = 0.0; mean[fire] = 0.0; n[fire] = 0
    return alarm


def alarms_for(act: pd.DataFrame, zs: Dict[str, np.ndarray], k: float, h: float, kind: str,
               _cache: dict = {}) -> np.ndarray:
    key = id(act)
    if key not in _cache:
        users = list(dict.fromkeys(act.user_id))          # groupby order (sorted df)
        lens = [len(zs[u]) for u in users]
        Z = np.zeros((len(users), max(lens), len(FEATURES)))
        valid = np.zeros((len(users), max(lens)), dtype=bool)
        for i, u in enumerate(users):
            Z[i, :lens[i]] = zs[u]
            valid[i, :lens[i]] = True
        _cache.clear()
        _cache[key] = (Z, valid, lens)
    Z, valid, lens = _cache[key]
    A = run_detector_batch(Z, valid, k, h, kind)
    return np.concatenate([A[i, :n] for i, n in enumerate(lens)])


def episode_stats(act: pd.DataFrame, alarm: np.ndarray, mask: np.ndarray, cls: str) -> dict:
    sel = mask & (act.threat_class.to_numpy() == cls)
    eids = pd.unique(act.episode_id.to_numpy()[sel])
    hours = act.hour_index.to_numpy()
    eid_all = act.episode_id.to_numpy()
    det, ttd = 0, []
    for e in eids:
        m = mask & (eid_all == e)
        if alarm[m].any():
            det += 1
            ttd.append(float(hours[m][alarm[m]].min() - hours[m].min()))
    return {"episodes": int(len(eids)), "detected": det,
            "episode_recall": det / len(eids) if len(eids) else np.nan,
            "window_recall": float(alarm[sel].mean()) if sel.any() else np.nan,
            "ttd_hours_median": float(np.median(ttd)) if ttd else np.nan,
            "ttd_hours_mean": float(np.mean(ttd)) if ttd else np.nan}


def supervised_probe(act: pd.DataFrame, zs: Dict[str, np.ndarray]) -> dict:
    feats = []
    for u, g in act.groupby("user_id", sort=False):
        z = zs[u]
        lag = np.zeros_like(z)
        for t in range(len(z)):
            lo = max(0, t - PROBE_LAGS)
            lag[t] = z[lo:t].mean(axis=0) if t > lo else 0.0
        feats.append(np.hstack([z, lag]))
    X = np.vstack(feats)
    y = act.is_true_threat.to_numpy(dtype=bool)
    tc = act.threat_class.to_numpy()
    split = act.split.to_numpy()
    tr, va, te = split == "train", split == "val", split == "test"
    clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(X[tr], y[tr])
    p = clf.predict_proba(X)[:, 1]
    t, _ = selection.threshold_max_f1(p[va], y[va], split[va])
    mal_te = te & (tc == "malicious_insider")
    neg_te = te & ~y
    m = binary_metrics(y[te], p[te] >= t)
    return {"test_auc_all": selection.auc_rank(p[te], y[te]),
            "test_auc_malicious": selection.auc_rank(np.r_[p[mal_te], p[neg_te]],
                                                     np.r_[np.ones(mal_te.sum(), bool),
                                                           np.zeros(neg_te.sum(), bool)]),
            "test_malicious_window_recall": float((p[mal_te] >= t).mean()) if mal_te.any() else np.nan,
            "test_f1": m["f1"], "test_fpr": m["fpr"],
            "note": "supervised upper bound: trained with labels on TRAIN; not deployable as an "
                    "unsupervised detector"}


def evaluate_seed(s: int) -> dict:
    base = RUNS / f"data_seed_{s}"
    act, zs, b = personal_active_z(base)
    y = act.is_true_threat.to_numpy(dtype=bool)
    split = act.split.to_numpy()
    bb = act.is_benign_burst.to_numpy(dtype=bool)
    va, te = split == "val", split == "test"

    # hybrid flags (from the trained run) aligned to active rows; rows without 24 h history are unflagged
    sc = pd.read_csv(base / "run" / "scored_all_splits.csv", usecols=["event_id", "hybrid_anomaly_flagged"])
    hyb = act.event_id.map(dict(zip(sc.event_id, sc.hybrid_anomaly_flagged))).fillna(False).to_numpy(dtype=bool)

    res = {}
    for kind in ("cusum", "ph"):
        alarms = {(k, h): alarms_for(act, zs, k, h, kind) for k in K_GRID for h in H_GRID}
        params, table = selection.choose_drift_params(
            {p: a[va] for p, a in alarms.items()}, y[va], act.threat_class.to_numpy()[va],
            act.episode_id.to_numpy()[va], split[va], FALSE_ALARM_BUDGET)
        a = alarms[params]
        r = {"k": params[0], "h": params[1],
             "val_fa_rate": table[params]["fa_rate"],
             "val_malicious_episode_recall": table[params]["episode_recall"],
             "test_false_alarm_rate_ordinary_negatives": float(a[te & ~y & ~bb].mean()),
             "test_false_alarm_rate_benign_bursts": float(a[te & bb].mean()) if (te & bb).any() else np.nan,
             "per_class": {c: episode_stats(act, a, te, c) for c in THREAT_CLASSES}}
        comb = hyb | a
        for name, flag in (("hybrid_only", hyb), ("hybrid_or_drift", comb)):
            m = binary_metrics(y[te], flag[te])
            r[name] = {**{k: m[k] for k in ("precision", "recall", "f1", "fpr")},
                       "malicious_episode_recall": episode_stats(act, flag, te, "malicious_insider")["episode_recall"],
                       "benign_burst_flag_rate": float(flag[te & bb].mean()) if (te & bb).any() else np.nan}
        res[kind] = r
    res["supervised_probe"] = supervised_probe(act, zs)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    args = ap.parse_args()
    seeds = args.seeds or seeds_from_config()
    for s in seeds:
        res = evaluate_seed(s)
        d = RUNS / f"data_seed_{s}" / "drift"
        d.mkdir(parents=True, exist_ok=True)
        (d / "drift_metrics.json").write_text(json.dumps(
            {"provenance": provenance("evaluation/drift_detector.py", {"data_and_train": s}, "cpu"),
             **res}, indent=1, default=float), encoding="utf-8")
        record(f"drift.ds{s}", res, script="evaluation/drift_detector.py", seeds={"data_and_train": s})
        c = res["cusum"]
        print(f"[seed {s}] CUSUM k={c['k']} h={c['h']}: malicious ep recall "
              f"{c['per_class']['malicious_insider']['episode_recall']:.2f}, ttd "
              f"{c['per_class']['malicious_insider']['ttd_hours_median']}, FA {c['test_false_alarm_rate_ordinary_negatives']:.4f}; "
              f"hybrid|drift F1 {c['hybrid_or_drift']['f1']:.3f} vs hybrid {c['hybrid_only']['f1']:.3f}", flush=True)

    if len(seeds) > 1:
        e = load()["entries"]
        keys = []
        for kind in ("cusum", "ph"):
            keys += [f"{kind}.per_class.{c}.episode_recall" for c in THREAT_CLASSES]
            keys += [f"{kind}.per_class.malicious_insider.ttd_hours_median",
                     f"{kind}.test_false_alarm_rate_ordinary_negatives",
                     f"{kind}.test_false_alarm_rate_benign_bursts",
                     f"{kind}.hybrid_or_drift.f1", f"{kind}.hybrid_or_drift.recall",
                     f"{kind}.hybrid_or_drift.fpr", f"{kind}.hybrid_or_drift.malicious_episode_recall",
                     f"{kind}.hybrid_only.f1", f"{kind}.hybrid_only.recall", f"{kind}.hybrid_only.fpr",
                     f"{kind}.hybrid_only.malicious_episode_recall", f"{kind}.k", f"{kind}.h"]
        keys += ["supervised_probe.test_auc_malicious", "supervised_probe.test_malicious_window_recall",
                 "supervised_probe.test_auc_all", "supervised_probe.test_f1"]
        summ = {}
        for k in keys:
            v = np.array([e.get(f"drift.ds{s}.{k}", {}).get("value", np.nan) for s in seeds], dtype=float)
            summ[k] = {"mean": float(np.nanmean(v)), "sd": float(np.nanstd(v, ddof=1)),
                       "min": float(np.nanmin(v)), "max": float(np.nanmax(v)),
                       "n": int(np.isfinite(v).sum())}
        record("drift.summary", summ, script="evaluation/drift_detector.py", seeds={"datasets": seeds})
        OUT.mkdir(parents=True, exist_ok=True)
        with open(OUT / "drift_summary.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["metric", "mean", "sd", "min", "max", "n"])
            for k, d in summ.items():
                w.writerow([k, f"{d['mean']:.4f}", f"{d['sd']:.4f}", f"{d['min']:.4f}", f"{d['max']:.4f}", d["n"]])
        print(f"  -> {OUT / 'drift_summary.csv'}")


if __name__ == "__main__":
    main()
