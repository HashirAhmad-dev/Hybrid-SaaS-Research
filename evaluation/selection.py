"""
selection.py
============
Every threshold, weight, band and router in paper-v2 is chosen by a function in
this module, and every one of them refuses data that is not from a selection
split (hard rule H-R4: nothing is ever tuned on the test split).

Each selector takes a `splits` array aligned with its data and calls
`require_selection_split(splits)`, which raises `TestSplitLeak` if any row is
labelled anything other than an allowed selection split. Callers pass
`split[mask]` alongside `values[mask]`, so a mistaken mask that pulls in test
rows fails loudly instead of quietly producing an optimistic number.
`tests/test_selection.py` proves the guard fires.

The arithmetic of the original selectors (formerly inline in
train_and_evaluate.py and calibrate_sbrs.py) is unchanged; reproduce.ps1 checks
that the seed-42 numbers did not move.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

SELECTION_SPLITS = ("val",)          # anomaly track
PII_SELECTION_SPLITS = ("calib",)    # PII track (documents used to choose tau / router)


class TestSplitLeak(AssertionError):
    """A selection function was handed rows that are not from a selection split."""
    __test__ = False      # not a pytest test class


def require_selection_split(splits: Sequence, allowed: Iterable[str] = SELECTION_SPLITS,
                            what: str = "selection") -> None:
    s = np.asarray(splits).astype(str)
    if s.size == 0:
        raise TestSplitLeak(f"{what}: no rows given")
    bad = sorted(set(np.unique(s)) - set(allowed))
    if bad:
        raise TestSplitLeak(f"{what}: received rows from split(s) {bad}; "
                            f"only {list(allowed)} may be used for selection (H-R4)")


def _check_aligned(splits, *arrays) -> None:
    n = len(np.asarray(splits))
    for a in arrays:
        if len(np.asarray(a)) != n:
            raise ValueError("splits and data arrays must be aligned")


# ---------------------------------------------------------------------------
# Metrics used inside selection (kept local so this module has no side effects)
# ---------------------------------------------------------------------------
def _f1(y: np.ndarray, pred: np.ndarray) -> float:
    y = np.asarray(y, dtype=bool)
    pred = np.asarray(pred, dtype=bool)
    tp = int(np.sum(y & pred)); fp = int(np.sum(~y & pred)); fn = int(np.sum(y & ~pred))
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def auc_rank(score: np.ndarray, pos: np.ndarray) -> float:
    """Rank AUC with average ranks for ties (same as calibrate_sbrs.auc)."""
    from scipy.stats import rankdata
    pos = np.asarray(pos, dtype=bool)
    if pos.sum() == 0 or (~pos).sum() == 0:
        return float("nan")
    r = rankdata(score)
    return float((r[pos].sum() - pos.sum() * (pos.sum() + 1) / 2)
                 / (pos.sum() * (~pos).sum()))


# ---------------------------------------------------------------------------
# Anomaly-track selectors (validation split only)
# ---------------------------------------------------------------------------
def tune_ewma_tau(dev: np.ndarray, y: np.ndarray, splits: Sequence,
                  default_tau: float = 2.0) -> Tuple[float, float]:
    """EWMA relative-deviation threshold maximising F1. Returns (tau, f1)."""
    require_selection_split(splits, what="tune_ewma_tau")
    _check_aligned(splits, dev, y)
    best = (default_tau, -1.0)
    for tau in np.arange(0.25, 12.01, 0.25):
        f1 = _f1(y, dev > tau)
        if f1 > best[1]:
            best = (float(tau), f1)
    return best


ALPHA_GRID = np.round(np.arange(0.0, 1.001, 0.05), 3)
TAU_GRID = np.round(np.arange(0.02, 0.99, 0.01), 3)


def tune_alpha_tau(a_lstm: np.ndarray, a_if: np.ndarray, y: np.ndarray, splits: Sequence,
                   default_tau: float = 0.5):
    """(alpha, tau) maximising F1 of alpha*a_lstm + (1-alpha)*a_if >= tau."""
    require_selection_split(splits, what="tune_alpha_tau")
    _check_aligned(splits, a_lstm, a_if, y)
    best = {"alpha": 0.5, "tau": default_tau, "f1": -1.0}
    grid = []
    for alpha in ALPHA_GRID:
        fused = alpha * a_lstm + (1 - alpha) * a_if
        row = {"alpha": float(alpha), "best_f1": -1.0, "best_tau": 0.5}
        for tau in TAU_GRID:
            f1 = _f1(y, fused >= tau)
            if f1 > row["best_f1"]:
                row["best_f1"], row["best_tau"] = f1, float(tau)
            if f1 > best["f1"]:
                best = {"alpha": float(alpha), "tau": float(tau), "f1": f1}
        grid.append(row)
    return best, grid


def tune_alpha_tau_constrained(a_lstm: np.ndarray, a_if: np.ndarray, y: np.ndarray,
                               tc: np.ndarray, splits: Sequence, target: str,
                               fpr_budget: float):
    """Maximise recall on one threat class subject to FPR <= budget."""
    require_selection_split(splits, what="tune_alpha_tau_constrained")
    _check_aligned(splits, a_lstm, a_if, y, tc)
    y = np.asarray(y, dtype=bool)
    sel = np.asarray(tc) == target
    best = {"alpha": 1.0, "tau": 0.5, "recall": -1.0, "fpr": 1.0}
    for alpha in ALPHA_GRID:
        fused = alpha * a_lstm + (1 - alpha) * a_if
        for tau in TAU_GRID:
            pred = fused >= tau
            fpr = float(pred[~y].mean()) if (~y).any() else 1.0
            if fpr > fpr_budget:
                continue
            rec = float(pred[sel].mean()) if sel.any() else 0.0
            if rec > best["recall"] or (rec == best["recall"] and fpr < best["fpr"]):
                best = {"alpha": float(alpha), "tau": float(tau), "recall": rec, "fpr": fpr}
    return best


def threshold_max_f1(score: np.ndarray, y: np.ndarray, splits: Sequence,
                     grid: np.ndarray | None = None) -> Tuple[float, float]:
    """Generic detector threshold: maximise F1 of score >= t. Returns (t, f1).

    Default grid = the unique validation scores (plus +inf so "flag nothing" is
    a candidate), which makes the choice independent of the score's scale.
    """
    require_selection_split(splits, what="threshold_max_f1")
    _check_aligned(splits, score, y)
    score = np.asarray(score, dtype=float)
    if grid is None:
        grid = np.unique(score[np.isfinite(score)])
    best = (float("inf"), -1.0)
    for t in grid:
        f1 = _f1(y, score >= t)
        if f1 > best[1]:
            best = (float(t), f1)
    return best


def threshold_at_fpr(score: np.ndarray, y: np.ndarray, splits: Sequence,
                     fpr: float) -> float:
    """Smallest threshold whose FPR on the selection negatives is <= fpr."""
    require_selection_split(splits, what="threshold_at_fpr")
    _check_aligned(splits, score, y)
    neg = np.sort(np.asarray(score, dtype=float)[~np.asarray(y, dtype=bool)])
    if len(neg) == 0:
        raise ValueError("no negatives")
    for t in np.unique(neg):
        if (neg >= t).mean() <= fpr:
            return float(t)
    return float(np.nextafter(neg[-1], np.inf))


# ---------------------------------------------------------------------------
# SBRS selectors (validation split only)
# ---------------------------------------------------------------------------
def sbrs_values(S: np.ndarray, A: np.ndarray, beta: float) -> np.ndarray:
    return np.asarray(S, dtype=float) * (1.0 + beta * np.asarray(A, dtype=float)) / 100.0


def choose_beta_knee(S, A, y, splits, betas: Sequence[float],
                     frac_of_max: float = 0.99) -> Tuple[float, Dict[float, float], float]:
    """Smallest beta reaching frac_of_max of the max validation AUC(SBRS vs threat)."""
    require_selection_split(splits, what="choose_beta_knee")
    _check_aligned(splits, S, A, y)
    aucs = {float(b): auc_rank(sbrs_values(S, A, b), y) for b in betas}
    auc_max = max(aucs.values())
    knee = min(b for b, a in aucs.items() if a >= frac_of_max * auc_max)
    return knee, aucs, auc_max


def derive_bands(S, A, y, beta, splits, alert_pctl: float = 95.0,
                 block_pctl: float = 99.5) -> Tuple[float, float, float]:
    """Band cut-points = upper percentiles of BENIGN validation SBRS.

    Returns (t_alert, t_block, validation flagged-F1 at t_alert).
    """
    require_selection_split(splits, what="derive_bands")
    _check_aligned(splits, S, A, y)
    v = sbrs_values(S, A, beta)
    y = np.asarray(y, dtype=bool)
    benign = v[~y]
    t_alert = float(np.percentile(benign, alert_pctl))
    t_block = float(np.percentile(benign, block_pctl))
    return t_alert, t_block, _f1(y, v >= t_alert)


def percentile_threshold(score, y, splits, pctl: float) -> float:
    """Threshold = pctl-th percentile of a score on BENIGN selection rows."""
    require_selection_split(splits, what="percentile_threshold")
    _check_aligned(splits, score, y)
    return float(np.percentile(np.asarray(score, dtype=float)[~np.asarray(y, dtype=bool)], pctl))


def choose_by_val_auc(scores_by_param: Dict, y: np.ndarray, splits: Sequence):
    """Pick the hyper-parameter whose score has the highest selection-split AUC.

    `scores_by_param` maps parameter value -> score array (selection rows only).
    Ties go to the first parameter in insertion order. Returns (param, {param: auc}).
    """
    require_selection_split(splits, what="choose_by_val_auc")
    aucs = {}
    for p, s in scores_by_param.items():
        _check_aligned(splits, s, y)
        aucs[p] = auc_rank(np.asarray(s, dtype=float), np.asarray(y, dtype=bool))
    best = max(aucs, key=lambda p: (aucs[p], -list(aucs).index(p)))
    return best, aucs


def choose_drift_params(alarms_by_param: Dict, y: np.ndarray, threat_class: np.ndarray,
                        episode_id: np.ndarray, splits: Sequence, fa_budget: float,
                        target: str = "malicious_insider"):
    """Drift-detector (k, h): maximise TARGET-class episode recall on the selection
    split subject to false-alarm rate (alarms on negative rows) <= fa_budget.
    Ties: fewer false alarms, then grid order. Returns (param, table)."""
    require_selection_split(splits, what="choose_drift_params")
    y = np.asarray(y, dtype=bool)
    tc, eid = np.asarray(threat_class), np.asarray(episode_id)
    eps = [e for e in dict.fromkeys(eid[tc == target]) if e is not None and e == e]
    table, best, best_key = {}, None, None
    for p, a in alarms_by_param.items():
        _check_aligned(splits, a, y)
        a = np.asarray(a, dtype=bool)
        fa = float(a[~y].mean()) if (~y).any() else 0.0
        rec = float(np.mean([a[eid == e].any() for e in eps])) if eps else 0.0
        table[p] = {"fa_rate": fa, "episode_recall": rec}
        if fa > fa_budget:
            continue
        key = (rec, -fa)
        if best is None or key > best_key:
            best, best_key = p, key
    if best is None:                       # nothing meets the budget: the quietest setting
        best = min(table, key=lambda q: table[q]["fa_rate"])
    return best, table
