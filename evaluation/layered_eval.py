"""
layered_eval.py
===============
Task F9 (D-034): end-to-end layered detection, hybrid OR CUSUM OR supervised probe,
with each attack class held out of the probe's training in turn.

    python -m evaluation.layered_eval [--resamples 2000]
Outputs: results/supervised/layered_eval.json, manifest keys layered.*
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from evaluation.cert_rich import SEED, lagged, personal_z, val_threshold
from evaluation.common import FEATURES, SEQ_LEN, THREAT_CLASSES
from evaluation.drift_detector import alarms_for, personal_active_z
from evaluation.multiseed import RUNS
from evaluation.supervised_multiseed import SEEDS
from tools.manifest import PROJECT_ROOT, load, provenance, record

OUT = PROJECT_ROOT / "results" / "supervised"
BOOT_SEED = 20261105
SYSTEMS = ("hybrid", "hybrid_or_cusum", "sup_lr", "sup_gb", "layered_lr", "layered_gb")
METRICS = ("unseen_episode_recall", "seen_episode_recall", "precision", "f1", "fpr", "burst_alarm_rate")


class Clusters:
    """Per-dataset sufficient statistics for fast cluster resampling (users, then episodes)."""

    def __init__(self, users, y, bb, eid, tc):
        self.users = np.unique(users)
        self.neg = {u: np.flatnonzero((users == u) & ~y) for u in self.users}
        self.burst = {u: np.flatnonzero((users == u) & bb) for u in self.users}
        self.eps = {u: [(np.flatnonzero((users == u) & y & (eid == e)), tc[(users == u) & y & (eid == e)][0])
                        for e in pd.unique(eid[(users == u) & y])] for u in self.users}

    def draw(self, rng, full=False):
        us = self.users if full else rng.choice(self.users, len(self.users), replace=True)
        negs, bursts, eps = [], [], []
        for u in us:
            negs.append(self.neg[u]); bursts.append(self.burst[u])
            e = self.eps[u]
            pick = range(len(e)) if full else (rng.integers(0, len(e), len(e)) if e else [])
            eps += [e[k] for k in pick]
        return np.concatenate(negs), np.concatenate(bursts), eps


def metrics(flag, draw, held) -> dict:
    neg, burst, eps = draw
    det = [(flag[r].any(), c, flag[r].sum(), len(r)) for r, c in eps]
    tp = sum(d[2] for d in det); fn = sum(d[3] - d[2] for d in det); fp = int(flag[neg].sum())
    un = [d[0] for d in det if d[1] == held]
    se = [d[0] for d in det if d[1] != held]
    return {"unseen_episode_recall": float(np.mean(un)) if un else np.nan,
            "seen_episode_recall": float(np.mean(se)) if se else np.nan,
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "f1": 2 * tp / (2 * tp + fp + fn) if tp else 0.0,
            "fpr": fp / max(len(neg), 1),
            "burst_alarm_rate": float(flag[burst].mean()) if len(burst) else np.nan}


def dataset_flags(seed: int, e: dict):
    base = RUNS / f"data_seed_{seed}"
    act, zs, _ = personal_active_z(base)
    act = act.reset_index(drop=True)
    cus = alarms_for(act, zs, float(e[f"drift.ds{seed}.cusum.k"]["value"]), float(e[f"drift.ds{seed}.cusum.h"]["value"]), "cusum")
    sc = pd.read_csv(base / "run" / "scored_all_splits.csv", usecols=["event_id", "hybrid_anomaly_flagged"])
    hyb = act.event_id.map(dict(zip(sc.event_id, sc.hybrid_anomaly_flagged))).fillna(False).to_numpy(bool)
    keep = (act.hour_index >= SEQ_LEN - 1).to_numpy()
    df = act[keep].reset_index(drop=True)
    hyb, cus = hyb[keep], cus[keep]
    from evaluation.common import time_boundaries
    b = time_boundaries(int(pd.read_csv(base / "data" / "sessions_raw.csv", usecols=["hour_index"]).hour_index.max()) + 1)
    fit = df.hour_index.to_numpy() < b["fit_end"]
    Z = personal_z(df, list(FEATURES), fit)
    P = np.hstack([Z, lagged(df, Z)])
    y = df.is_true_threat.to_numpy(bool)
    split = df.split.to_numpy()
    tc = df.threat_class.to_numpy()
    te = split == "test"
    folds = {}
    for held in THREAT_CLASSES:
        keepc = (tc != held) | te
        tr = (split == "train") & keepc
        vm = keepc & (split != "test")
        sup = {}
        for name, est in (("lr", LogisticRegression(max_iter=2000, class_weight="balanced")),
                          ("gb", HistGradientBoostingClassifier(random_state=SEED, class_weight="balanced"))):
            s = est.fit(P[tr], y[tr]).predict_proba(P)[:, 1]
            sup[name] = s >= val_threshold(s[vm], y[vm], split[vm])
        folds[held] = {"hybrid": hyb, "hybrid_or_cusum": hyb | cus, "sup_lr": sup["lr"], "sup_gb": sup["gb"],
                       "layered_lr": hyb | cus | sup["lr"], "layered_gb": hyb | cus | sup["gb"]}
    t = df[te]
    cl = Clusters(t.user_id.to_numpy(), t.is_true_threat.to_numpy(bool), t.is_benign_burst.to_numpy(bool),
                  t.episode_id.fillna("").to_numpy(), t.threat_class.fillna("").to_numpy())
    folds = {h: {s: f[te] for s, f in v.items()} for h, v in folds.items()}
    return cl, folds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resamples", type=int, default=2000)
    args = ap.parse_args()
    t0 = time.time()
    e = load()["entries"]
    data = []
    for s in SEEDS:
        data.append(dataset_flags(s, e))
        print(f"  ds{s} ready ({time.time() - t0:.0f} s)", flush=True)

    def summarise(draws):
        per = {sy: {m: [] for m in METRICS} for sy in SYSTEMS}
        by_fold = {sy: {h: [] for h in THREAT_CLASSES} for sy in SYSTEMS}
        for (cl, folds), dr in zip(data, draws):
            for h in THREAT_CLASSES:
                for sy in SYSTEMS:
                    m = metrics(folds[h][sy], dr, h)
                    for k in METRICS:
                        per[sy][k].append(m[k])
                    by_fold[sy][h].append(m["unseen_episode_recall"])
        return ({sy: {k: float(np.nanmean(v)) for k, v in per[sy].items()} for sy in SYSTEMS},
                {sy: {h: float(np.nanmean(v)) for h, v in by_fold[sy].items()} for sy in SYSTEMS})

    rng = np.random.default_rng(BOOT_SEED)
    point, fold_point = summarise([cl.draw(rng, full=True) for cl, _ in data])
    reps = {sy: {k: [] for k in METRICS} for sy in SYSTEMS}
    for b in range(args.resamples):
        r, _ = summarise([cl.draw(rng) for cl, _ in data])
        for sy in SYSTEMS:
            for k in METRICS:
                reps[sy][k].append(r[sy][k])
        if (b + 1) % 250 == 0:
            print(f"  {b + 1}/{args.resamples}", flush=True)
    ci = lambda v: {"ci_lo": float(np.nanpercentile(v, 2.5)), "ci_hi": float(np.nanpercentile(v, 97.5))}
    out = {sy: {k: {"point": point[sy][k], **ci(np.array(reps[sy][k]))} for k in METRICS} for sy in SYSTEMS}
    out["unseen_episode_recall_by_held_out_class"] = fold_point
    out["paired"] = {}
    for a, bsys in (("layered_lr", "hybrid_or_cusum"), ("layered_gb", "hybrid_or_cusum"),
                    ("layered_lr", "hybrid"), ("layered_gb", "hybrid")):
        out["paired"][f"{a}_minus_{bsys}"] = {
            k: {"point": point[a][k] - point[bsys][k], **ci(np.array(reps[a][k]) - np.array(reps[bsys][k]))}
            for k in METRICS}
    out["_meta"] = {"resamples": args.resamples, "bootstrap_seed": BOOT_SEED, "minutes": (time.time() - t0) / 60,
                    "decision": "docs/DECISIONS.md D-034"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "layered_eval.json").write_text(json.dumps(
        {**out, "provenance": provenance("evaluation/layered_eval.py", {"data_seeds": SEEDS, "bootstrap": BOOT_SEED})},
        indent=1), encoding="utf-8")
    record("layered", out, script="evaluation/layered_eval.py", seeds={"data_seeds": SEEDS, "models": SEED, "bootstrap": BOOT_SEED})
    for sy in SYSTEMS:
        print(f"{sy:16s} " + "  ".join(f"{k} {out[sy][k]['point']:.3f} [{out[sy][k]['ci_lo']:.3f},{out[sy][k]['ci_hi']:.3f}]"
                                        for k in METRICS))
    for sy in SYSTEMS:
        print(f"{sy:16s} unseen by class " + "  ".join(f"{h[:10]} {v:.2f}" for h, v in fold_point[sy].items()))
    for n, v in out["paired"].items():
        print(n, "  ".join(f"{k} {x['point']:+.3f} [{x['ci_lo']:+.3f},{x['ci_hi']:+.3f}]" for k, x in v.items()))


if __name__ == "__main__":
    main()
