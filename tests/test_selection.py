"""H-R4: selection functions accept validation rows only, and pick the right optimum."""
import numpy as np
import pytest

from evaluation import selection as sel
from evaluation.selection import TestSplitLeak


def _val(n):
    return np.array(["val"] * n)


ALL_SELECTORS = [
    lambda sp: sel.tune_ewma_tau(np.zeros(len(sp)), np.zeros(len(sp), bool), sp),
    lambda sp: sel.tune_alpha_tau(np.zeros(len(sp)), np.zeros(len(sp)), np.zeros(len(sp), bool), sp),
    lambda sp: sel.tune_alpha_tau_constrained(np.zeros(len(sp)), np.zeros(len(sp)),
                                              np.zeros(len(sp), bool), np.array([None] * len(sp)),
                                              sp, "malicious_insider", 0.05),
    lambda sp: sel.threshold_max_f1(np.zeros(len(sp)), np.zeros(len(sp), bool), sp),
    lambda sp: sel.threshold_at_fpr(np.arange(len(sp), dtype=float), np.zeros(len(sp), bool), sp, 0.1),
    lambda sp: sel.choose_beta_knee(np.ones(len(sp)), np.ones(len(sp)),
                                    np.arange(len(sp)) % 2 == 0, sp, [0.5, 1.0]),
    lambda sp: sel.derive_bands(np.ones(len(sp)), np.ones(len(sp)), np.zeros(len(sp), bool), 2.5, sp),
    lambda sp: sel.percentile_threshold(np.ones(len(sp)), np.zeros(len(sp), bool), sp, 95),
]


@pytest.mark.parametrize("selector", ALL_SELECTORS)
@pytest.mark.parametrize("bad", [["val", "test"], ["test"], ["train", "val"]])
def test_every_selector_rejects_non_validation_rows(selector, bad):
    sp = np.array((bad * 5)[:10])
    with pytest.raises(TestSplitLeak):
        selector(sp)


@pytest.mark.parametrize("selector", ALL_SELECTORS)
def test_every_selector_accepts_validation_rows(selector):
    selector(_val(10))


def test_empty_rejected():
    with pytest.raises(TestSplitLeak):
        sel.require_selection_split([])


def test_pii_selection_split():
    sel.require_selection_split(["calib", "calib"], allowed=sel.PII_SELECTION_SPLITS)
    with pytest.raises(TestSplitLeak):
        sel.require_selection_split(["calib", "eval"], allowed=sel.PII_SELECTION_SPLITS)


def test_misaligned_rejected():
    with pytest.raises(ValueError):
        sel.threshold_max_f1(np.zeros(3), np.zeros(4, bool), _val(4))


def test_threshold_max_f1_finds_separating_cut():
    score = np.array([0.1, 0.2, 0.3, 0.8, 0.9])
    y = np.array([0, 0, 0, 1, 1], bool)
    t, f1 = sel.threshold_max_f1(score, y, _val(5))
    assert f1 == 1.0 and 0.3 < t <= 0.8


def test_threshold_at_fpr():
    score = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], float)
    y = np.zeros(10, bool)
    t = sel.threshold_at_fpr(score, y, _val(10), 0.2)   # flag at most 2 of 10 negatives
    assert t == 9.0 and (score >= t).mean() == pytest.approx(0.2)


def test_tune_alpha_tau_prefers_informative_component():
    rng = np.random.default_rng(0)
    y = np.r_[np.ones(20, bool), np.zeros(200, bool)]
    good = np.r_[rng.uniform(0.7, 1.0, 20), rng.uniform(0.0, 0.3, 200)]
    noise = rng.uniform(0, 1, 220)
    best, _ = sel.tune_alpha_tau(good, noise, y, _val(220))
    # any alpha that puts enough weight on the informative score separates perfectly;
    # the grid search returns the first such alpha
    assert best["f1"] == 1.0 and best["alpha"] >= 0.5


def test_derive_bands_percentiles():
    S = np.full(1000, 100.0); A = np.linspace(0, 1, 1000)    # SBRS = 1 + 2.5 A
    y = np.zeros(1000, bool)
    t_alert, t_block, _ = sel.derive_bands(S, A, y, 2.5, _val(1000))
    assert t_alert == pytest.approx(1 + 2.5 * np.percentile(A, 95))
    assert t_block == pytest.approx(1 + 2.5 * np.percentile(A, 99.5))


def test_beta_knee_is_smallest_near_max():
    S = np.array([10, 90, 10, 90], float); A = np.array([0.9, 0.1, 0.8, 0.0])
    y = np.array([1, 0, 1, 0], bool)
    knee, aucs, amax = sel.choose_beta_knee(S, A, y, _val(4), [0.0, 5.0, 50.0])
    # beta 0 and 5: both threats score below both benign rows (AUC 0); beta 50: AUC 0.5
    assert aucs[0.0] == 0.0 and aucs[5.0] == 0.0 and amax == 0.5 and knee == 50.0


def test_scripts_use_guarded_selectors_only():
    """No evaluation script defines its own tuning function; every selection call passes splits."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "evaluation"
    for name in ("train_and_evaluate.py", "calibrate_sbrs.py", "ablation.py"):
        src = (root / name).read_text(encoding="utf-8")
        assert not re.search(r"^def (tune_|derive_bands|choose_)", src, re.M), name
        for call in re.findall(r"selection\.(\w+)\(", src):
            assert hasattr(sel, call), (name, call)
