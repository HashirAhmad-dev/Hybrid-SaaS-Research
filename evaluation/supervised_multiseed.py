"""
supervised_multiseed.py
=======================
Supervised probes on the 10 generated datasets (D-028): does a model trained on
labelled TRAIN incidents beat the unsupervised detectors on our own generator, as it
does on CERT (N-062), and does it catch slow malicious-insider drift?

    python -m evaluation.supervised_multiseed

Probe settings, thresholds and metrics are those of evaluation/cert_rich.py (D-027).
"""
from __future__ import annotations

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
from tools.manifest import PROJECT_ROOT, load, provenance, record

RUNS = PROJECT_ROOT / "results" / "runs"
OUT = PROJECT_ROOT / "results" / "supervised"
SEEDS = json.loads((PROJECT_ROOT / "evaluation" / "config" / "seeds.json").read_text(encoding="utf-8"))["data_seeds"]
DETECTORS = ("iforest", "zscore", "probe_logistic", "probe_boosting")


def load_rows(seed: int) -> pd.DataFrame:
    cols = ["user_id", "hour_index", "active", "is_true_threat", "threat_class", "episode_id",
            "is_benign_burst", "split", *FEATURES]
    df = pd.read_csv(RUNS / f"data_seed_{seed}" / "data" / "sessions_raw.csv", usecols=cols, low_memory=False)
    H = int(df.hour_index.max()) + 1
    df = df[df.active].sort_values(["user_id", "hour_index"]).reset_index(drop=True)
    df["threat_class"] = df["threat_class"].where(df["threat_class"].notna(), None)
    df.attrs["H"] = H
    return df


def evaluate_seed(seed: int) -> dict:
    df = load_rows(seed)
    b = time_boundaries(df.attrs["H"])
    df = df[df.hour_index >= SEQ_LEN - 1].reset_index(drop=True)
    y = df.is_true_threat.to_numpy(dtype=bool)
    split = df.split.to_numpy()
    tc, eid = df.threat_class.to_numpy(), df.episode_id.to_numpy()
    bb = df.is_benign_burst.to_numpy(dtype=bool)
    fit = df.hour_index.to_numpy() < b["fit_end"]
    tr, te = split == "train", split == "test"
    feats = list(FEATURES)

    X = df[feats].to_numpy(dtype=float)
    sc = StandardScaler().fit(X[fit])
    iso = IsolationForest(n_estimators=200, contamination="auto", random_state=SEED, n_jobs=-1).fit(sc.transform(X[fit]))
    Z = personal_z(df, feats, fit)
    P = np.hstack([Z, lagged(df, Z)])
    scores = {
        "iforest": -iso.score_samples(sc.transform(X)),
        "zscore": np.abs(Z).max(axis=1),
        "probe_logistic": LogisticRegression(max_iter=2000, class_weight="balanced").fit(P[tr], y[tr]).predict_proba(P)[:, 1],
        "probe_boosting": HistGradientBoostingClassifier(random_state=SEED, class_weight="balanced")
        .fit(P[tr], y[tr]).predict_proba(P)[:, 1],
    }
    neg_te = te & ~y
    pos = df[df.is_true_threat]
    tr_users = set(pos[pos.split == "train"].user_id)
    unseen = te & ~df.user_id.isin(tr_users).to_numpy()          # users never attacked in TRAIN
    res = {}
    for d, s in scores.items():
        t = val_threshold(s, y, split)
        flag = s >= t
        m = binary_metrics(y[te], flag[te])
        r = {"auc": selection.auc_rank(s[te], y[te]), "average_precision": float(average_precision_score(y[te], s[te])),
             **{k: m[k] for k in ("precision", "recall", "f1", "fpr")},
             "benign_burst_flag_rate": float(flag[te & bb].mean()) if (te & bb).any() else np.nan,
             "per_class": {}}
        for c in THREAT_CLASSES:
            sel = te & (tc == c)
            if not sel.any():
                continue
            eps = pd.unique(eid[sel])
            r["per_class"][c] = {
                "auc": selection.auc_rank(np.r_[s[sel], s[neg_te]],
                                          np.r_[np.ones(sel.sum(), bool), np.zeros(neg_te.sum(), bool)]),
                "recall": float(flag[sel].mean()),
                "episode_recall": float(np.mean([flag[te & (eid == e)].any() for e in eps]))}
        ue = pd.unique(eid[unseen & y])
        r["unseen_user"] = {"episodes": int(len(ue)), "detected": int(sum(flag[te & (eid == e)].any() for e in ue)),
                            "hour_recall": float(flag[unseen & y].mean()) if (unseen & y).any() else np.nan}
        se = pd.unique(eid[te & y & ~unseen])
        r["seen_user"] = {"episodes": int(len(se)), "detected": int(sum(flag[te & (eid == e)].any() for e in se)),
                          "hour_recall": float(flag[te & y & ~unseen].mean())}
        res[d] = r

    # does a test attack episode share a user with a TRAIN attack episode?
    te_eps = pos[pos.split == "test"].groupby("episode_id").agg(user=("user_id", "first"), cls=("threat_class", "first"))
    res["_overlap"] = {"test_episodes": int(len(te_eps)),
                       "test_episodes_user_attacked_in_train": int(te_eps.user.isin(tr_users).sum()),
                       "test_malicious_episodes": int((te_eps.cls == "malicious_insider").sum()),
                       "test_malicious_episodes_user_attacked_in_train":
                           int(((te_eps.cls == "malicious_insider") & te_eps.user.isin(tr_users)).sum())}
    return res


def main() -> None:
    t0 = time.time()
    man = load()["entries"]
    per = {}
    for s in SEEDS:
        per[s] = evaluate_seed(s)
        hw = {k: man[f"ablation.ds{s}.hybrid_weighted.{k}"]["value"] for k in ("auc", "valf1_f1")}
        per[s]["hybrid_weighted_t21"] = {"auc": hw["auc"], "f1": hw["valf1_f1"],
                                         "malicious_insider_auc": man[f"ablation.ds{s}.hybrid_weighted.per_class.malicious_insider.auc"]["value"],
                                         "malicious_insider_episode_recall": man[f"ablation.ds{s}.hybrid_weighted.per_class.malicious_insider.episode_recall"]["value"]}
        p = per[s]
        print(f"ds{s:<5d} " + "  ".join(f"{d} AUC {p[d]['auc']:.3f} F1 {p[d]['f1']:.3f}" for d in DETECTORS)
              + f"  | hybrid AUC {p['hybrid_weighted_t21']['auc']:.3f} F1 {p['hybrid_weighted_t21']['f1']:.3f}", flush=True)

    def stat(vals):
        v = np.array(vals, dtype=float)
        return {"mean": float(np.nanmean(v)), "sd": float(np.nanstd(v, ddof=1)), "min": float(np.nanmin(v)),
                "max": float(np.nanmax(v))}

    summ = {}
    for d in DETECTORS:
        summ[d] = {k: stat([per[s][d][k] for s in SEEDS])
                   for k in ("auc", "average_precision", "f1", "precision", "recall", "fpr", "benign_burst_flag_rate")}
        summ[d]["per_class"] = {c: {k: stat([per[s][d]["per_class"][c][k] for s in SEEDS])
                                    for k in ("auc", "recall", "episode_recall")} for c in THREAT_CLASSES}
    summ["hybrid_weighted_t21"] = {k: stat([per[s]["hybrid_weighted_t21"][k] for s in SEEDS])
                                   for k in per[SEEDS[0]]["hybrid_weighted_t21"]}
    summ["boosting_beats_hybrid"] = {
        "auc_datasets": int(sum(per[s]["probe_boosting"]["auc"] > per[s]["hybrid_weighted_t21"]["auc"] for s in SEEDS)),
        "f1_datasets": int(sum(per[s]["probe_boosting"]["f1"] > per[s]["hybrid_weighted_t21"]["f1"] for s in SEEDS)),
        "malicious_auc_datasets": int(sum(per[s]["probe_boosting"]["per_class"]["malicious_insider"]["auc"] >
                                          per[s]["hybrid_weighted_t21"]["malicious_insider_auc"] for s in SEEDS)),
        "n_datasets": len(SEEDS)}
    summ["overlap"] = {k: int(sum(per[s]["_overlap"][k] for s in SEEDS)) for k in per[SEEDS[0]]["_overlap"]}
    for d in DETECTORS:                       # pooled over the 10 datasets
        for grp in ("seen_user", "unseen_user"):
            ep = sum(per[s][d][grp]["episodes"] for s in SEEDS)
            det = sum(per[s][d][grp]["detected"] for s in SEEDS)
            summ[d][grp] = {"episodes": ep, "detected": det, "episode_recall": det / ep if ep else np.nan}
    summ["_meta"] = {"minutes": (time.time() - t0) / 60, "decision": "docs/DECISIONS.md D-028"}

    OUT.mkdir(parents=True, exist_ok=True)
    seeds = {"data_seeds": SEEDS, "models": SEED}
    (OUT / "supervised_multiseed.json").write_text(json.dumps(
        {"summary": summ, "per_dataset": {str(s): v for s, v in per.items()},
         "provenance": provenance("evaluation/supervised_multiseed.py", seeds)}, indent=1, default=float), encoding="utf-8")
    record("supervised.summary", summ, script="evaluation/supervised_multiseed.py", seeds=seeds)
    record("supervised", {f"ds{s}": {k: v for k, v in per[s].items()} for s in SEEDS},
           script="evaluation/supervised_multiseed.py", seeds=seeds)
    for d in (*DETECTORS, "hybrid_weighted_t21"):
        print(f"{d:20s} AUC {summ[d]['auc']['mean']:.3f} ± {summ[d]['auc']['sd']:.3f}   F1 "
              f"{summ[d]['f1']['mean']:.3f} ± {summ[d]['f1']['sd']:.3f}")
    for d in DETECTORS:
        pc = summ[d]["per_class"]["malicious_insider"]
        print(f"{d:20s} malicious AUC {pc['auc']['mean']:.3f}  episode recall {pc['episode_recall']['mean']:.3f}")
    print(summ["boosting_beats_hybrid"], summ["overlap"])
    for d in DETECTORS:
        print(f"{d:20s} seen-user episodes {summ[d]['seen_user']}  unseen-user episodes {summ[d]['unseen_user']}")


if __name__ == "__main__":
    main()
