"""
sbrs_fusion.py
==============
Paper-v2 task T2.5: is the multiplicative SBRS justified? Reviewer 2: "when S is
zero or very low, even highly abnormal behavior produces a negligible risk
score ... compare with additive, maximum-based, and independently gated fusion".

Five ways to turn content sensitivity S (0..100) and behavioural anomaly A
(the weighted hybrid score, 0..1) into one risk score r:

  multiplicative  r = S (1 + beta A) / 100, beta by the validation AUC knee (current design)
  additive        r = w S/100 + (1 - w) A, w by validation AUC
  max             r = max(S/100, A)
  gated           r = multiplicative, but any session with A >= tau_A is moved above
                  every non-gated session (escalated regardless of S); tau_A is the
                  hybrid's validation-F1 threshold from T2.1
  logistic        r = P(threat | S, A, S*A), logistic regression fitted on the TRAIN split

SAME BUDGET for every form: ALERT at the 95th and BLOCK at the 99.5th percentile
of that form's score on BENIGN VALIDATION sessions (the rule the shipped bands
use). All parameters are chosen on validation (or fitted on train for the
logistic form) through evaluation/selection.py; test is scored once.

Reported on TEST per form: threat recall (ALERT or BLOCK), BLOCK recall, benign
ALERT-or-BLOCK rate, benign BLOCK rate, action counts for threats and for benign
sessions, per-class recall, and the reviewer's case: threats with LOW S
(S < 30) and HIGH A (A >= tau_A) and how many each form escalates. A synthetic
3 x 3 grid of (S, A) corners shows each form's action with dataset-42 settings.

    python -m evaluation.sbrs_fusion
Outputs: results/sbrs_fusion/*.csv, manifest keys fusion.ds<s>.*, fusion.summary.*
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from evaluation import selection
from evaluation.common import THREAT_CLASSES
from evaluation.multiseed import RUNS, seeds_from_config
from tools.manifest import PROJECT_ROOT, load, record

OUT = PROJECT_ROOT / "results" / "sbrs_fusion"
FORMS = ("multiplicative", "additive", "max", "gated", "logistic")
BETAS = np.round(np.concatenate([np.arange(0, 5.01, 0.5), np.arange(6, 21, 2)]), 2)
W_GRID = np.round(np.arange(0.0, 1.001, 0.05), 2)
LOW_S = 30
ALERT_PCTL, BLOCK_PCTL = 95.0, 99.5
CORNERS_S = (5, 50, 95)
CORNERS_A = (0.05, 0.5, 0.95)


class Form:
    """A fitted fusion form: score(S, A) plus validation-percentile bands."""

    def __init__(self, name, fn, params):
        self.name, self.fn, self.params = name, fn, params
        self.t_alert = self.t_block = None

    def fit_bands(self, S, A, y, splits):
        r = self.fn(S, A)
        self.t_alert = selection.percentile_threshold(r, y, splits, ALERT_PCTL)
        self.t_block = selection.percentile_threshold(r, y, splits, BLOCK_PCTL)
        return self

    def action(self, S, A):
        r = self.fn(np.asarray(S, float), np.asarray(A, float))
        return np.where(r >= self.t_block, "BLOCK", np.where(r >= self.t_alert, "ALERT", "PERMIT"))


def fit_forms(rows: pd.DataFrame, tau_a: float):
    split = rows.split.to_numpy()
    S = rows.pii_sensitivity_score.to_numpy(float)
    A = rows.score_hybrid_weighted.to_numpy(float)
    y = rows.is_true_threat.to_numpy(bool)
    v, tr = split == "val", split == "train"

    beta, _, _ = selection.choose_beta_knee(S[v], A[v], y[v], split[v], BETAS)
    mult = lambda S, A, b=beta: S * (1 + b * A) / 100.0
    w, _ = selection.choose_by_val_auc({float(w): w * S[v] / 100 + (1 - w) * A[v] for w in W_GRID},
                                       y[v], split[v])
    add = lambda S, A, w=w: w * S / 100.0 + (1 - w) * A
    mx = lambda S, A: np.maximum(S / 100.0, A)
    top = 100.0 * (1 + beta) / 100.0                      # max possible multiplicative score
    gated = lambda S, A, b=beta, t=tau_a, top=top: np.where(A >= t, top + A, S * (1 + b * A) / 100.0)
    X = lambda S, A: np.c_[S / 100.0, A, S * A / 100.0]
    lr = LogisticRegression(max_iter=1000).fit(X(S[tr], A[tr]), y[tr])   # labels of TRAIN only
    logi = lambda S, A, m=lr: m.predict_proba(X(np.asarray(S, float), np.asarray(A, float)))[:, 1]

    forms = {
        "multiplicative": Form("multiplicative", mult, {"beta": beta}),
        "additive": Form("additive", add, {"w": w}),
        "max": Form("max", mx, {}),
        "gated": Form("gated", gated, {"beta": beta, "tau_A": tau_a}),
        "logistic": Form("logistic", logi, {"coef": lr.coef_.ravel().tolist(),
                                             "intercept": float(lr.intercept_[0])}),
    }
    for f in forms.values():
        f.fit_bands(S[v], A[v], y[v], split[v])
    return forms


def evaluate_forms(rows: pd.DataFrame, forms, tau_a: float) -> dict:
    te = rows[rows.split == "test"]
    S, A = te.pii_sensitivity_score.to_numpy(float), te.score_hybrid_weighted.to_numpy(float)
    y = te.is_true_threat.to_numpy(bool)
    tc = te.threat_class.to_numpy()
    bb = te.is_benign_burst.to_numpy(bool)
    low_high = y & (S < LOW_S) & (A >= tau_a)
    out = {}
    for name, f in forms.items():
        act = f.action(S, A)
        flag, blk = act != "PERMIT", act == "BLOCK"
        r = {"params": f.params, "t_alert": f.t_alert, "t_block": f.t_block,
             "threat_recall": float(flag[y].mean()), "threat_block_recall": float(blk[y].mean()),
             "benign_alert_or_block_rate": float(flag[~y].mean()),
             "benign_block_rate": float(blk[~y].mean()),
             "benign_burst_alert_or_block_rate": float(flag[bb].mean()) if bb.any() else np.nan,
             "threat_actions": {a: int((act[y] == a).sum()) for a in ("PERMIT", "ALERT", "BLOCK")},
             "benign_actions": {a: int((act[~y] == a).sum()) for a in ("PERMIT", "ALERT", "BLOCK")},
             "low_S_high_A_threats": int(low_high.sum()),
             "low_S_high_A_escalated": int(flag[low_high].sum()),
             "per_class_recall": {c: float(flag[tc == c].mean()) for c in THREAT_CLASSES if (tc == c).any()}}
        tp = int(flag[y].sum()); fp = int(flag[~y].sum()); fn = int((~flag[y]).sum())
        r["f1"] = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
        out[name] = r
    out["_low_S_high_A_definition"] = f"is_true_threat and S < {LOW_S} and A >= tau_A ({tau_a:.3f})"
    return out


def main() -> None:
    seeds = seeds_from_config()
    e = load()["entries"]
    OUT.mkdir(parents=True, exist_ok=True)
    per_seed = {}
    corners = None
    for s in seeds:
        rows = pd.read_csv(RUNS / f"data_seed_{s}" / "ablation" / "row_scores.csv")
        tau_a = float(e[f"ablation.ds{s}.hybrid_weighted.val_threshold_f1"]["value"])
        forms = fit_forms(rows, tau_a)
        res = evaluate_forms(rows, forms, tau_a)
        per_seed[s] = res
        record(f"fusion.ds{s}", res, script="evaluation/sbrs_fusion.py", seeds={"data_and_train": s})
        if s == 42:
            corners = [{"S": S_, "A": A_, **{n: str(f.action([S_], [A_])[0]) for n, f in forms.items()}}
                       for S_ in CORNERS_S for A_ in CORNERS_A]
        print(f"[seed {s}] " + "  ".join(f"{n}: R={res[n]['threat_recall']:.2f} "
                                         f"benign={res[n]['benign_alert_or_block_rate']:.3f}"
                                         for n in FORMS), flush=True)

    summ = {}
    for n in FORMS:
        summ[n] = {}
        for k in ("threat_recall", "threat_block_recall", "benign_alert_or_block_rate",
                  "benign_block_rate", "benign_burst_alert_or_block_rate", "f1",
                  "low_S_high_A_threats", "low_S_high_A_escalated",
                  *[f"per_class_recall.{c}" for c in THREAT_CLASSES]):
            def get(d, path):
                for p in path.split("."):
                    d = d.get(p, np.nan) if isinstance(d, dict) else np.nan
                return d
            v = np.array([get(per_seed[s][n], k) for s in seeds], float)
            summ[n][k] = {"mean": float(np.nanmean(v)), "sd": float(np.nanstd(v, ddof=1)),
                          "sum": float(np.nansum(v))}
        for grp in ("threat_actions", "benign_actions"):
            for a in ("PERMIT", "ALERT", "BLOCK"):
                summ[n][f"{grp}.{a}"] = {"sum": float(sum(per_seed[s][n][grp][a] for s in seeds))}
    record("fusion.summary", summ, script="evaluation/sbrs_fusion.py", seeds={"datasets": seeds})

    with open(OUT / "fusion_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["form", "threat_recall_mean", "threat_recall_sd", "block_recall_mean",
                    "benign_alert_or_block_mean", "benign_block_mean", "burst_flag_mean", "f1_mean",
                    "malicious_recall_mean", "low_S_high_A_threats_total", "low_S_high_A_escalated_total",
                    "threat PERMIT/ALERT/BLOCK (all datasets)", "benign PERMIT/ALERT/BLOCK (all datasets)"])
        for n in FORMS:
            d = summ[n]
            w.writerow([n, f"{d['threat_recall']['mean']:.4f}", f"{d['threat_recall']['sd']:.4f}",
                        f"{d['threat_block_recall']['mean']:.4f}",
                        f"{d['benign_alert_or_block_rate']['mean']:.4f}", f"{d['benign_block_rate']['mean']:.4f}",
                        f"{d['benign_burst_alert_or_block_rate']['mean']:.4f}", f"{d['f1']['mean']:.4f}",
                        f"{d['per_class_recall.malicious_insider']['mean']:.4f}",
                        int(d["low_S_high_A_threats"]["sum"]), int(d["low_S_high_A_escalated"]["sum"]),
                        "/".join(str(int(d[f"threat_actions.{a}"]["sum"])) for a in ("PERMIT", "ALERT", "BLOCK")),
                        "/".join(str(int(d[f"benign_actions.{a}"]["sum"])) for a in ("PERMIT", "ALERT", "BLOCK"))])
    with open(OUT / "fusion_corners_seed42.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["S", "A", *FORMS])
        w.writeheader()
        w.writerows(corners or [])
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
