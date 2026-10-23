"""Drift detector arithmetic: hand case, batch == per-user loop, guarded parameter choice."""
import numpy as np
import pytest

from evaluation.drift_detector import run_detector, run_detector_batch
from evaluation import selection as sel


def test_cusum_hand_case():
    # one feature, k = 0.5, h = 2: S+ = 0.5, 1.0, 1.5, 2.0, 2.5 -> alarm at t=4, then reset
    z = np.ones((7, 1))
    a = run_detector(z, 0.5, 2.0, "cusum")
    assert list(np.flatnonzero(a)) == [4]
    # a negative shift triggers the lower side
    a = run_detector(-np.ones((5, 1)) * 3, 0.5, 4.0, "cusum")   # S- = 2.5, 5.0 -> alarm at t=1
    assert list(np.flatnonzero(a)) == [1, 3]


@pytest.mark.parametrize("kind", ["cusum", "ph"])
def test_batch_equals_loop(kind):
    rng = np.random.default_rng(0)
    lens = [30, 17, 25]
    Z = np.zeros((3, 30, 6)); valid = np.zeros((3, 30), bool)
    seqs = []
    for i, n in enumerate(lens):
        x = rng.normal(size=(n, 6)) + (np.arange(n)[:, None] > n // 2) * 1.5
        Z[i, :n] = x; valid[i, :n] = True; seqs.append(x)
    A = run_detector_batch(Z, valid, 0.5, 4.0, kind)
    for i, n in enumerate(lens):
        assert (A[i, :n] == run_detector(seqs[i], 0.5, 4.0, kind)).all()
        assert not A[i, n:].any()


def test_choose_drift_params_respects_budget_and_split():
    y = np.array([0, 0, 0, 0, 1, 1], bool)
    tc = np.array([None] * 4 + ["malicious_insider"] * 2, object)
    eid = np.array([None] * 4 + ["E1", "E1"], object)
    alarms = {"noisy": np.array([1, 1, 0, 0, 1, 0], bool),     # recall 1, FA 0.5
              "quiet": np.array([0, 0, 0, 0, 0, 1], bool)}      # recall 1, FA 0
    p, _ = sel.choose_drift_params(alarms, y, tc, eid, np.array(["val"] * 6), 0.1)
    assert p == "quiet"
    with pytest.raises(sel.TestSplitLeak):
        sel.choose_drift_params(alarms, y, tc, eid, np.array(["val"] * 5 + ["test"]), 0.1)
