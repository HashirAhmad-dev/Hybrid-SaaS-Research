"""
label_curve.py
==============
Label learning curve (D-029): how many labelled TRAIN incidents does the supervised
layer of D-028 need before it beats the unsupervised detectors?

    python -m evaluation.label_curve

Only the k chosen episodes are positives; all other TRAIN hours are treated as benign.
The alert threshold is the 99th percentile of validation scores (no validation labels).
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from evaluation import selection
from evaluation.cert_rich import SEED, lagged, personal_z
from evaluation.common import FEATURES, SEQ_LEN, binary_metrics, time_boundaries
from evaluation.supervised_multiseed import SEEDS, load_rows
from tools.manifest import PROJECT_ROOT, provenance, record

OUT = PROJECT_ROOT / "results" / "supervised"
K_GRID = (1, 3, 5, 10, 20, 50, "all")
DRAWS = 5
BUDGET_PCTL = 99.0
TARGET = "malicious_insider"


def operating_point(s, y, split, tc, eid) -> dict:
    va, te = split == "val", split == "test"
    t = float(np.percentile(s[va], BUDGET_PCTL))          # label-free: 1 percent of validation hours alerted
    flag = s >= t
    m = binary_metrics(y[te], flag[te])
    neg = te & ~y
    sel = te & (tc == TARGET)
    eps = pd.unique(eid[sel])
    return {"auc": selection.auc_rank(s[te], y[te]), **{k: m[k] for k in ("precision", "recall", "f1", "fpr")},
            "malicious_auc": selection.auc_rank(np.r_[s[sel], s[neg]],
                                                np.r_[np.ones(sel.sum(), bool), np.zeros(neg.sum(), bool)]),
            "malicious_episode_recall": float(np.mean([flag[te & (eid == e)].any() for e in eps]))}


def evaluate_seed(seed: int) -> dict:
    df = load_rows(seed)
    b = time_boundaries(df.attrs["H"])
    df = df[df.hour_index >= SEQ_LEN - 1].reset_index(drop=True)
    y = df.is_true_threat.to_numpy(dtype=bool)
    split = df.split.to_numpy()
    tc, eid = df.threat_class.to_numpy(), df.episode_id.to_numpy()
    fit = df.hour_index.to_numpy() < b["fit_end"]
    tr = split == "train"
    feats = list(FEATURES)

    X = df[feats].to_numpy(dtype=float)
    sc = StandardScaler().fit(X[fit])
    iso = IsolationForest(n_estimators=200, contamination="auto", random_state=SEED, n_jobs=-1).fit(sc.transform(X[fit]))
    out = {"k0_iforest": operating_point(-iso.score_samples(sc.transform(X)), y, split, tc, eid)}

    Z = personal_z(df, feats, fit)
    P = np.hstack([Z, lagged(df, Z)])
    tr_eps = np.array(sorted(pd.unique(eid[tr & y])))
    ep_class = dict(zip(eid[tr & y], tc[tr & y]))
    for k in K_GRID:
        n = len(tr_eps) if k == "all" else k
        runs = {"logistic": [], "boosting": []}
        has_mal = []
        fallbacks = 0
        for d in range(1 if k == "all" else DRAWS):
            rng = np.random.default_rng(1000 * seed + 10 * n + d)
            chosen = tr_eps if k == "all" else rng.choice(tr_eps, n, replace=False)
            has_mal.append(any(ep_class[e] == TARGET for e in chosen))
            ylab = tr & np.isin(eid, chosen) & y                 # only confirmed incidents are positive
            Ptr, ytr = P[tr], ylab[tr]
            lr = LogisticRegression(max_iter=2000, class_weight="balanced").fit(Ptr, ytr)
            # boosting's automatic early stopping holds out a stratified 10 percent, which needs at least
            # 2 positive hours; with fewer, early stopping is switched off for that draw (counted, D-029)
            few = int(ytr.sum()) < 2
            fallbacks += few
            gb = HistGradientBoostingClassifier(random_state=SEED, class_weight="balanced",
                                                early_stopping=False if few else "auto").fit(Ptr, ytr)
            runs["logistic"].append(operating_point(lr.predict_proba(P)[:, 1], y, split, tc, eid))
            runs["boosting"].append(operating_point(gb.predict_proba(P)[:, 1], y, split, tc, eid))
        for mname, rs in runs.items():
            out[f"k{k}_{mname}"] = {key: float(np.mean([r[key] for r in rs])) for key in rs[0]}
            out[f"k{k}_{mname}"]["draws_with_malicious_episode"] = float(np.mean(has_mal))
        out[f"k{k}_boosting"]["draws_without_early_stopping"] = float(fallbacks)
    return out


def main() -> None:
    global BUDGET_PCTL
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-pctl", type=float, default=BUDGET_PCTL,
                    help="99 = 1 percent alert budget (D-029); 95 = 5 percent, added after the 1 percent run")
    BUDGET_PCTL = ap.parse_args().budget_pctl
    tag = "" if BUDGET_PCTL == 99.0 else f"_b{int(100 - BUDGET_PCTL)}"
    t0 = time.time()
    per = {}
    for s in SEEDS:
        per[s] = evaluate_seed(s)
        print(f"ds{s:<5d} IF F1 {per[s]['k0_iforest']['f1']:.3f}  " + "  ".join(
            f"k={k}: {per[s][f'k{k}_boosting']['f1']:.3f}" for k in K_GRID) + "  (boosting F1)", flush=True)
    summ = {}
    for cfg in per[SEEDS[0]]:
        summ[cfg] = {key: {"mean": float(np.nanmean([per[s][cfg][key] for s in SEEDS])),
                           "sd": float(np.nanstd([per[s][cfg][key] for s in SEEDS], ddof=1))}
                     for key in per[SEEDS[0]][cfg]}
    summ["_meta"] = {"minutes": (time.time() - t0) / 60, "decision": "docs/DECISIONS.md D-029",
                     "train_episodes_per_dataset": 143, "budget_percentile_val": BUDGET_PCTL}
    seeds = {"data_seeds": SEEDS, "models": SEED, "draw_seed_rule": "1000*dataset+10*k+draw"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"label_curve{tag}.json").write_text(json.dumps(
        {"summary": summ, "per_dataset": {str(s): v for s, v in per.items()},
         "provenance": provenance("evaluation/label_curve.py", seeds)}, indent=1), encoding="utf-8")
    record(f"labelcurve{tag}.summary", summ, script="evaluation/label_curve.py", seeds=seeds)
    print(f"{'config':18s} {'AUC':>6s} {'F1':>6s} {'P':>6s} {'R':>6s} {'FPR':>6s} {'malAUC':>7s} {'malEp':>6s} {'drawsMal':>8s}")
    for cfg, v in summ.items():
        if cfg.startswith("_"):
            continue
        print(f"{cfg:18s} {v['auc']['mean']:6.3f} {v['f1']['mean']:6.3f} {v['precision']['mean']:6.3f} "
              f"{v['recall']['mean']:6.3f} {v['fpr']['mean']:6.3f} {v['malicious_auc']['mean']:7.3f} "
              f"{v['malicious_episode_recall']['mean']:6.3f} "
              f"{v.get('draws_with_malicious_episode', {'mean': float('nan')})['mean']:8.2f}")


if __name__ == "__main__":
    main()
