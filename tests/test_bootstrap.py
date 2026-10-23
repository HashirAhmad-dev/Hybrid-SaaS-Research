"""Cluster bootstrap mechanics: users move as a whole, attack episodes move as a whole."""
import numpy as np

from evaluation.bootstrap_stats import Dataset, fast_auc
from evaluation.selection import auc_rank


def _toy():
    ds = Dataset.__new__(Dataset)
    # user A: 3 normal rows (0,1,2) + episode e1 rows (3,4); user B: 2 normal rows (5,6) + episode e2 (7)
    ds.y = np.array([0, 0, 0, 1, 1, 0, 0, 1], bool)
    ds.users = np.array(["A", "B"])
    ds.user_other = {"A": np.array([0, 1, 2]), "B": np.array([5, 6])}
    ds.user_eps = {"A": [np.array([3, 4])], "B": [np.array([7])]}
    return ds


def test_resample_keeps_clusters_whole():
    ds = _toy()
    rng = np.random.default_rng(0)
    for _ in range(200):
        idx = ds.resample(rng)
        # every drawn copy of episode e1 contributes both of its rows
        assert (idx == 3).sum() == (idx == 4).sum()
        # a user's normal rows always come together
        assert (idx == 0).sum() == (idx == 1).sum() == (idx == 2).sum()
        assert (idx == 5).sum() == (idx == 6).sum()
        # number of users drawn is always 2
        assert (idx == 0).sum() + (idx == 5).sum() == 2


def test_fast_auc_matches_reference():
    rng = np.random.default_rng(1)
    s = np.round(rng.uniform(size=300), 2)       # many ties
    y = rng.uniform(size=300) < 0.2
    assert abs(fast_auc(s, y) - auc_rank(s, y)) < 1e-12
