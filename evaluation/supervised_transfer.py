"""
supervised_transfer.py
======================
Transfer tests for the supervised probes (D-031, task F1).

    python -m evaluation.supervised_transfer loco     # leave one attack class out, 10 datasets
    python -m evaluation.supervised_transfer cert     # train on the simulator, test on CERT r4.2

Probe settings are those of evaluation/supervised_multiseed.py (D-028).
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import StandardScaler

from evaluation import selection
from evaluation.cert_rich import SEED, lagged, personal_z, val_threshold
from evaluation.common import FEATURES, SEQ_LEN, THREAT_CLASSES, binary_metrics, time_boundaries
from evaluation.supervised_multiseed import SEEDS, load_rows
from tools.manifest import PROJECT_ROOT, load, provenance, record

OUT = PROJECT_ROOT / "results" / "supervised"
CERT_BASE = PROJECT_ROOT / "results" / "runs" / "cert_r4.2"
MODELS = ("probe_logistic", "probe_boosting")


def fit_models(P, y, seed=SEED):
    return {"probe_logistic": LogisticRegression(max_iter=2000, class_weight="balanced").fit(P, y),
            "probe_boosting": HistGradientBoostingClassifier(random_state=seed, class_weight="balanced").fit(P, y)}


def prepared(df: pd.DataFrame):
    b = time_boundaries(df.attrs["H"])
    df = df[df.hour_index >= SEQ_LEN - 1].reset_index(drop=True)
    fit = df.hour_index.to_numpy() < b["fit_end"]
    Z = personal_z(df, list(FEATURES), fit)
    return df, np.hstack([Z, lagged(df, Z)]), fit


# ---------------------------------------------------------------------------
def loco_seed(seed: int) -> dict:
    df, P, _ = prepared(load_rows(seed))
    y = df.is_true_threat.to_numpy(dtype=bool)
    split = df.split.to_numpy()
    tc, eid = df.threat_class.to_numpy(), df.episode_id.to_numpy()
    te = split == "test"
    out = {}
    for held in THREAT_CLASSES:
        h = tc == held
        keep = ~h | te                                   # held-out hours leave TRAIN and VALIDATION
        tr = (split == "train") & keep
        models = fit_models(P[tr], y[tr])
        neg = te & ~y
        sel = te & h
        eps = pd.unique(eid[sel])
        for name, m in models.items():
            s = m.predict_proba(P)[:, 1]
            vmask = keep & (split != "test")             # validation without the held-out class
            t = val_threshold(np.where(vmask, s, np.nan)[vmask], y[vmask], split[vmask])
            flag = s >= t
            out.setdefault(name, {})[held] = {
                "auc": selection.auc_rank(np.r_[s[sel], s[neg]], np.r_[np.ones(sel.sum(), bool), np.zeros(neg.sum(), bool)]),
                "recall": float(flag[sel].mean()),
                "episode_recall": float(np.mean([flag[te & (eid == e)].any() for e in eps])),
                "test_fpr": float(flag[neg].mean())}
    return out


def stage_loco() -> None:
    t0 = time.time()
    man = load()["entries"]
    per = {s: loco_seed(s) for s in SEEDS}
    summ = {}
    for m in MODELS:
        for c in THREAT_CLASSES:
            loco = {k: [per[s][m][c][k] for s in SEEDS] for k in ("auc", "recall", "episode_recall", "test_fpr")}
            ind = {k: [man[f"supervised.ds{s}.{m}.per_class.{c}.{k}"]["value"] for s in SEEDS]
                   for k in ("auc", "recall", "episode_recall")}
            summ.setdefault(m, {})[c] = {
                "held_out": {k: {"mean": float(np.mean(v)), "sd": float(np.std(v, ddof=1))} for k, v in loco.items()},
                "in_distribution": {k: {"mean": float(np.mean(v)), "sd": float(np.std(v, ddof=1))} for k, v in ind.items()}}
    for c in THREAT_CLASSES:
        summ.setdefault("iforest_reference", {})[c] = {
            k: {"mean": float(np.mean([man[f"supervised.ds{s}.iforest.per_class.{c}.{k}"]["value"] for s in SEEDS]))}
            for k in ("auc", "episode_recall")}
    summ["_meta"] = {"minutes": (time.time() - t0) / 60, "decision": "docs/DECISIONS.md D-031"}
    seeds = {"data_seeds": SEEDS, "models": SEED}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "loco.json").write_text(json.dumps({"summary": summ, "per_dataset": {str(s): v for s, v in per.items()},
                                               "provenance": provenance("evaluation/supervised_transfer.py", seeds)},
                                              indent=1), encoding="utf-8")
    record("transfer.loco", summ, script="evaluation/supervised_transfer.py", seeds=seeds)
    print(f"{'model':16s} {'held-out class':22s} {'AUC in-dist':>11s} {'AUC held':>9s} {'ep.rec in':>9s} {'ep.rec held':>11s} {'FPR':>6s} | IF AUC")
    for m in MODELS:
        for c in THREAT_CLASSES:
            v = summ[m][c]
            print(f"{m:16s} {c:22s} {v['in_distribution']['auc']['mean']:11.3f} {v['held_out']['auc']['mean']:9.3f} "
                  f"{v['in_distribution']['episode_recall']['mean']:9.3f} {v['held_out']['episode_recall']['mean']:11.3f} "
                  f"{v['held_out']['test_fpr']['mean']:6.3f} | {summ['iforest_reference'][c]['auc']['mean']:.3f}")


# ---------------------------------------------------------------------------
def cert_rows() -> pd.DataFrame:
    cols = ["user_id", "hour_index", "active", "is_true_threat", "threat_class", "episode_id", "split", *FEATURES]
    df = pd.read_csv(CERT_BASE / "data" / "sessions_raw.csv", usecols=cols, low_memory=False)
    H = int(df.hour_index.max()) + 1
    df = df[df.active].sort_values(["user_id", "hour_index"]).reset_index(drop=True)
    df["threat_class"] = df["threat_class"].where(df["threat_class"].notna(), None)
    df.attrs["H"] = H
    return df


def label_free(s, y, split, eid, tc, target="cert_scenario_2") -> dict:
    va, te = split == "val", split == "test"
    t = float(np.percentile(s[va], 99.0))
    flag = s >= t
    m = binary_metrics(y[te], flag[te])
    sel = te & (tc == target)
    eps = pd.unique(eid[sel])
    return {"auc": selection.auc_rank(s[te], y[te]), "average_precision": float(average_precision_score(y[te], s[te])),
            **{k: m[k] for k in ("precision", "recall", "f1", "fpr")},
            "scenario2_episode_recall": float(np.mean([flag[te & (eid == e)].any() for e in eps]))}


def stage_cert() -> None:
    t0 = time.time()
    Ps, ys = [], []
    for s in SEEDS:
        df, P, _ = prepared(load_rows(s))
        tr = df.split.to_numpy() == "train"
        Ps.append(P[tr]); ys.append(df.is_true_threat.to_numpy(dtype=bool)[tr])
    models = fit_models(np.vstack(Ps), np.concatenate(ys))
    cdf, CP, cfit = prepared(cert_rows())
    y = cdf.is_true_threat.to_numpy(dtype=bool)
    split, eid, tc = cdf.split.to_numpy(), cdf.episode_id.to_numpy(), cdf.threat_class.to_numpy()
    res = {name: label_free(m.predict_proba(CP)[:, 1], y, split, eid, tc) for name, m in models.items()}
    X = cdf[list(FEATURES)].to_numpy(dtype=float)
    sc = StandardScaler().fit(X[cfit])
    iso = IsolationForest(n_estimators=200, contamination="auto", random_state=SEED, n_jobs=-1).fit(sc.transform(X[cfit]))
    res["iforest_on_cert"] = label_free(-iso.score_samples(sc.transform(X)), y, split, eid, tc)
    res["_meta"] = {"train_hours_simulator": int(sum(len(v) for v in ys)), "train_positive_hours_simulator": int(sum(v.sum() for v in ys)),
                    "minutes": (time.time() - t0) / 60, "decision": "docs/DECISIONS.md D-031"}
    seeds = {"data_seeds": SEEDS, "models": SEED}
    (OUT / "sim_to_cert.json").write_text(json.dumps({"results": res, "provenance": provenance(
        "evaluation/supervised_transfer.py", seeds)}, indent=1), encoding="utf-8")
    record("transfer.sim_to_cert", res, script="evaluation/supervised_transfer.py", seeds=seeds)
    for k, v in res.items():
        if not k.startswith("_"):
            print(f"{k:18s} AUC {v['auc']:.3f} AP {v['average_precision']:.4f} P {v['precision']:.3f} R {v['recall']:.3f} "
                  f"F1 {v['f1']:.3f} FPR {v['fpr']:.4f} S2 episodes {v['scenario2_episode_recall']:.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["loco", "cert"])
    stage_loco() if ap.parse_args().stage == "loco" else stage_cert()


if __name__ == "__main__":
    main()
