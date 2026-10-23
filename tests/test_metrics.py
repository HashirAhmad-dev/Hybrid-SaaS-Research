"""Metric functions against hand-computed values."""
import math

import numpy as np
import pytest

from evaluation import common
from evaluation.calibrate_sbrs import auc as auc_calib, prf
from evaluation.selection import auc_rank
from evaluation.train_and_evaluate import roc_auc


def test_binary_metrics_hand_case():
    y = np.array([1, 1, 1, 0, 0, 0, 0, 0], dtype=bool)
    p = np.array([1, 1, 0, 1, 0, 0, 0, 0], dtype=bool)
    m = common.binary_metrics(y, p)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (2, 1, 1, 4)
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)
    assert m["f1"] == pytest.approx(2 / 3)
    assert m["fpr"] == pytest.approx(1 / 5)
    assert prf(p, y)["f1"] == pytest.approx(m["f1"])


def test_binary_metrics_degenerate():
    m = common.binary_metrics(np.zeros(4, bool), np.zeros(4, bool))
    assert m["precision"] == 0.0 and m["recall"] == 0.0 and m["f1"] == 0.0 and m["fpr"] == 0.0


def test_auc_hand_case_and_ties():
    pos, neg = np.array([0.9, 0.4]), np.array([0.5, 0.1])
    # pairs: 0.9>0.5, 0.9>0.1, 0.4<0.5, 0.4>0.1 -> 3/4
    assert roc_auc(pos, neg) == pytest.approx(0.75)
    score = np.concatenate([pos, neg]); lab = np.array([1, 1, 0, 0], bool)
    assert auc_calib(score, lab) == pytest.approx(0.75)
    assert auc_rank(score, lab) == pytest.approx(0.75)
    # all tied -> 0.5
    assert roc_auc(np.array([0.3, 0.3]), np.array([0.3])) == pytest.approx(0.5)
    assert math.isnan(roc_auc(np.array([]), np.array([0.1])))


def test_wilson_matches_reported_interval():
    # metrics.json: malicious insider 1/51 -> [0.003469..., 0.103048...]
    lo, hi = common.wilson_ci(1, 51)
    assert lo == pytest.approx(0.003469603253442241)
    assert hi == pytest.approx(0.10304807675589372)
    lo, hi = common.wilson_ci(13, 13)
    assert hi == 1.0 and lo == pytest.approx(0.7718981569447083)


def test_ewma_stream_hand_case():
    prev, new, dev = common.ewma_stream([10, 20, 10], lam=0.3)
    # state 10 -> dev(20) = 1.0, state 13 -> dev(10) = -3/13, state 12.1
    assert list(prev) == pytest.approx([10, 10, 13])
    assert list(new) == pytest.approx([10, 13, 12.1])
    assert list(dev) == pytest.approx([0.0, 1.0, -3 / 13])


def test_robust_calibrator():
    cal = common.RobustCalibrator().fit(np.arange(0, 201, dtype=float))  # p50=100, p99.5=199
    assert cal.lo == pytest.approx(100.0) and cal.hi == pytest.approx(199.0)
    assert list(cal.transform(np.array([50.0, 100.0, 149.5, 199.0, 500.0]))) == \
        pytest.approx([0.0, 0.0, 0.5, 1.0, 1.0])
