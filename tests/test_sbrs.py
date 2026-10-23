"""SBRS computation and banding: hand-computable cases, both implementations agree."""
import pytest

from backend import risk_orchestrator as ro
from evaluation import common


@pytest.mark.parametrize("S,A,beta,expected", [
    (50, 0.4, 2.5, 1.0),        # 50 * (1 + 1.0) / 100
    (80, 0.5, 2.5, 1.8),        # 80 * 2.25 / 100
    (100, 1.0, 2.5, 3.5),
    (0, 1.0, 2.5, 0.0),         # zero content sensitivity kills any anomaly (the reviewer's point)
    (40, 0.0, 2.5, 0.4),
    (60, 0.2, 0.5, 0.66),
])
def test_sbrs_formula(S, A, beta, expected):
    assert common.sbrs(S, A, beta) == pytest.approx(expected)
    assert ro.compute_sbrs(S, A, beta).sbrs_value == pytest.approx(round(expected, 4))


def test_sbrs_clamps_inputs():
    assert common.sbrs(150, 0.5, 2.5) == pytest.approx(100 * 2.25 / 100)
    assert common.sbrs(50, -3.0, 2.5) == pytest.approx(0.5)
    assert common.sbrs(50, 7.0, 2.5) == pytest.approx(50 * 3.5 / 100)
    r = ro.compute_sbrs(150, 7.0)
    assert r.sensitivity_score == 100 and r.hybrid_anomaly_score == 1.0


@pytest.mark.parametrize("value,action", [
    (0.0, "PERMIT"), (1.2199, "PERMIT"), (1.22, "ALERT"), (1.8399, "ALERT"),
    (1.84, "BLOCK"), (3.5, "BLOCK"),
])
def test_bands_boundaries(value, action):
    assert common.band(value)[1] == action
    assert ro._band(value)[1] == action


def test_backend_and_evaluation_constants_agree():
    assert ro.DEFAULT_BETA == common.SBRS_BETA
    assert [tuple(b) for b in ro.SBRS_BANDS] == [tuple(b) for b in common.SBRS_BANDS]


def test_doc_bands_use_their_own_beta():
    # D-005: the old documented bands are applied at beta 0.5, not at the shipped beta.
    assert common.PAPER_DOC_BETA == 0.5
    v = common.sbrs(60, 0.5, common.PAPER_DOC_BETA)      # 0.75
    assert common.band(v, common.PAPER_DOC_BANDS)[1] == "ALERT"


def test_compute_sbrs_end_to_end_action():
    r = ro.compute_sbrs(80, 0.5)          # 1.8 at beta 2.5 -> ALERT
    assert (r.sbrs_category, r.enforcement_action) == ("SENSITIVE", "ALERT")
    r = ro.compute_sbrs(90, 0.9)          # 0.9 * 3.25 = 2.925 -> BLOCK
    assert r.enforcement_action == "BLOCK"
