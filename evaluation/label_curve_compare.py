"""
label_curve_compare.py
======================
Task F10 (D-032): the label curve of D-029 compared with Isolation Forest under two
threshold rules, with paired cluster-bootstrap intervals at k = 10 and k = 20.

    rule "budget"  label-free: alert on the top 5 percent of validation scores
    rule "valf1"   labelled validation: the threshold maximising F1 on validation hours

    python -m evaluation.label_curve_compare [--resamples 2000]
Outputs: results/supervised/label_curve_compare.json, manifest keys lccompare.*
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from evaluation.cert_rich import SEED, lagged, personal_z, val_threshold
from evaluation.common import FEATURES, SEQ_LEN, time_boundaries
from evaluation.label_curve import DRAWS, K_GRID
from evaluation.supervised_multiseed import SEEDS, load_rows
from tools.manifest import PROJECT_ROOT, provenance, record

OUT = PROJECT_ROOT / "results" / "supervised"
TARGET = "malicious_insider"
BOOT_SEED = 20261104
BOOT_K = (10, 20)
MODELS = ("logistic", "boosting")


def thresholds(s, y, split):
    va = split == "val"
    return {"budget": float(np.percentile(s[va], 95.0)), "valf1": float(val_threshold(s, y, split))}


def flag_metrics(flag, y, eps_rows):
    tp = int((flag & y).sum()); fp = int((flag & ~y).sum()); fn = int((~flag & y).sum())
    return {"precision": tp / (tp + fp) if tp + fp else 0.0, "recall": tp / (tp + fn) if tp + fn else 0.0,
            "f1": 2 * tp / (2 * tp + fp + fn) if tp else 0.0, "fpr": fp / max(int((~y).sum()), 1),
            "malicious_episode_recall": float(np.mean([flag[r].any() for r in eps_rows])) if eps_rows else np.nan}


def auc(s, y):
    n1 = int(y.sum()); n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return np.nan
    r = rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


class TestRows:
    """Test rows of one dataset with the T2.2 cluster structure (users, then attack episodes)."""

    def __init__(self, df: pd.DataFrame):
        te = (df.split == "test").to_numpy()
        self.idx = np.flatnonzero(te)
        sub = df.iloc[self.idx]
        self.y = sub.is_true_threat.to_numpy(bool)
        self.tc = sub.threat_class.to_numpy()
        self.eid = sub.episode_id.fillna("").to_numpy()
        users = sub.user_id.to_numpy()
        self.users = np.unique(users)
        self.other = {u: np.flatnonzero((users == u) & ~self.y) for u in self.users}
        self.eps = {u: [np.flatnonzero((users == u) & self.y & (self.eid == e))
                        for e in np.unique(self.eid[(users == u) & self.y])] for u in self.users}

    def mal_episode_rows(self, pos: np.ndarray) -> list:
        """Row positions (into `pos`) of each malicious-insider episode in a resample."""
        tc, eid = self.tc[pos], self.eid[pos]
        out = []
        for k, e in enumerate(pd.unique(eid[tc == TARGET])):
            out.append(np.flatnonzero((eid == e) & (tc == TARGET)))
        return out

    def resample(self, rng) -> np.ndarray:
        parts = []
        for u in rng.choice(self.users, size=len(self.users), replace=True):
            parts.append(self.other[u])
            eps = self.eps[u]
            for k in rng.integers(0, len(eps), size=len(eps)) if eps else []:
                parts.append(eps[k])
        return np.concatenate(parts)


def evaluate_seed(seed: int):
    df = load_rows(seed)
    b = time_boundaries(df.attrs["H"])
    df = df[df.hour_index >= SEQ_LEN - 1].reset_index(drop=True)
    y = df.is_true_threat.to_numpy(bool)
    split = df.split.to_numpy()
    tc, eid = df.threat_class.to_numpy(), df.episode_id.to_numpy()
    fit = df.hour_index.to_numpy() < b["fit_end"]
    tr = split == "train"
    T = TestRows(df)
    yt = y[T.idx]
    full = np.arange(len(T.idx))
    eps_full = T.mal_episode_rows(full)

    def point(s):
        th = thresholds(s, y, split)
        st = s[T.idx]
        return {"auc": auc(st, yt), **{f"{r}_{k}": v for r in th for k, v in flag_metrics(st >= th[r], yt, eps_full).items()}}, th

    X = df[list(FEATURES)].to_numpy(float)
    sc = StandardScaler().fit(X[fit])
    s_if = -IsolationForest(n_estimators=200, contamination="auto", random_state=SEED, n_jobs=-1).fit(
        sc.transform(X[fit])).score_samples(sc.transform(X))
    res = {"k0_iforest": point(s_if)[0]}
    keep = {"iforest": (s_if[T.idx], point(s_if)[1])}               # test scores + thresholds for the bootstrap

    Z = personal_z(df, list(FEATURES), fit)
    P = np.hstack([Z, lagged(df, Z)])
    tr_eps = np.array(sorted(pd.unique(eid[tr & y])))
    for k in K_GRID:
        n = len(tr_eps) if k == "all" else k
        per = {m: [] for m in MODELS}
        for d in range(1 if k == "all" else DRAWS):
            rng = np.random.default_rng(1000 * seed + 10 * n + d)          # D-029 draw rule
            chosen = tr_eps if k == "all" else rng.choice(tr_eps, n, replace=False)
            ylab = tr & np.isin(eid, chosen) & y
            few = int(ylab[tr].sum()) < 2
            models = {"logistic": LogisticRegression(max_iter=2000, class_weight="balanced"),
                      "boosting": HistGradientBoostingClassifier(random_state=SEED, class_weight="balanced",
                                                                 early_stopping=False if few else "auto")}
            for m, est in models.items():
                s = est.fit(P[tr], ylab[tr]).predict_proba(P)[:, 1]
                pt, th = point(s)
                per[m].append(pt)
                if k in BOOT_K:
                    keep.setdefault(f"k{k}_{m}", []).append((s[T.idx], th))
        for m in MODELS:
            res[f"k{k}_{m}"] = {key: float(np.mean([p[key] for p in per[m]])) for key in per[m][0]}
    return res, T, yt, keep


def boot_metrics(T, yt, scores_th, pos):
    """Metric dict for one model (list of draws, or one) on resample `pos`, averaged over draws."""
    items = scores_th if isinstance(scores_th, list) else [scores_th]
    y = yt[pos]
    eps = T.mal_episode_rows(pos)
    out = []
    for s, th in items:
        sp = s[pos]
        m = {"auc": auc(sp, y)}
        for r in ("budget", "valf1"):
            fm = flag_metrics(sp >= th[r], y, eps)
            m[f"{r}_f1"], m[f"{r}_malicious_episode_recall"] = fm["f1"], fm["malicious_episode_recall"]
        out.append(m)
    return {k: float(np.nanmean([o[k] for o in out])) for k in out[0]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resamples", type=int, default=2000)
    args = ap.parse_args()
    t0 = time.time()
    per, boot = {}, []
    for s in SEEDS:
        res, T, yt, keep = evaluate_seed(s)
        per[s] = res
        boot.append((T, yt, keep))
        print(f"ds{s}: IF budget F1 {res['k0_iforest']['budget_f1']:.3f} valf1 F1 {res['k0_iforest']['valf1_f1']:.3f} | "
              f"LR k10 {res['k10_logistic']['budget_f1']:.3f} / {res['k10_logistic']['valf1_f1']:.3f}", flush=True)
    summ = {cfg: {key: {"mean": float(np.nanmean([per[s][cfg][key] for s in SEEDS])),
                        "sd": float(np.nanstd([per[s][cfg][key] for s in SEEDS], ddof=1))}
                  for key in per[SEEDS[0]][cfg]} for cfg in per[SEEDS[0]]}

    rng = np.random.default_rng(BOOT_SEED)
    names = [f"k{k}_{m}" for k in BOOT_K for m in MODELS]
    keys = ("auc", "budget_f1", "valf1_f1", "budget_malicious_episode_recall", "valf1_malicious_episode_recall")
    diffs = {n: {k: [] for k in keys} for n in names}
    for b in range(args.resamples):
        pos = [T.resample(rng) for T, _, _ in boot]
        base = [boot_metrics(T, yt, keep["iforest"], p) for (T, yt, keep), p in zip(boot, pos)]
        for n in names:
            mm = [boot_metrics(T, yt, keep[n], p) for (T, yt, keep), p in zip(boot, pos)]
            for k in keys:
                diffs[n][k].append(np.nanmean([a[k] for a in mm]) - np.nanmean([c[k] for c in base]))
        if (b + 1) % 200 == 0:
            print(f"  {b + 1}/{args.resamples}", flush=True)
    paired = {}
    for n in names:
        paired[n] = {}
        for k in keys:
            v = np.array(diffs[n][k]); v = v[np.isfinite(v)]
            pointd = summ[n][k]["mean"] - summ["k0_iforest"][k]["mean"]
            paired[n][k] = {"point": pointd, "ci_lo": float(np.percentile(v, 2.5)), "ci_hi": float(np.percentile(v, 97.5))}
    out = {"summary": summ, "paired_minus_iforest": paired,
           "_meta": {"resamples": args.resamples, "bootstrap_seed": BOOT_SEED, "minutes": (time.time() - t0) / 60,
                     "decision": "docs/DECISIONS.md D-032"}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "label_curve_compare.json").write_text(json.dumps(
        {**out, "per_dataset": {str(s): v for s, v in per.items()},
         "provenance": provenance("evaluation/label_curve_compare.py", {"data_seeds": SEEDS, "bootstrap": BOOT_SEED})},
        indent=1), encoding="utf-8")
    record("lccompare", out, script="evaluation/label_curve_compare.py",
           seeds={"data_seeds": SEEDS, "models": SEED, "bootstrap": BOOT_SEED})
    print(f"{'config':16s} {'AUC':>6s} {'F1 budg':>8s} {'F1 valF1':>8s} {'malEp budg':>10s} {'malEp valF1':>11s}")
    for cfg, v in summ.items():
        print(f"{cfg:16s} {v['auc']['mean']:6.3f} {v['budget_f1']['mean']:8.3f} {v['valf1_f1']['mean']:8.3f} "
              f"{v['budget_malicious_episode_recall']['mean']:10.3f} {v['valf1_malicious_episode_recall']['mean']:11.3f}")
    for n, v in paired.items():
        print(n, "  ".join(f"{k} {x['point']:+.3f} [{x['ci_lo']:+.3f},{x['ci_hi']:+.3f}]" for k, x in v.items()))


if __name__ == "__main__":
    main()
