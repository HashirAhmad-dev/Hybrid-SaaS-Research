"""Split construction: chronological, no overlap, episodes inside one split, FIT/CALIB buffer."""
import numpy as np
import pandas as pd
import pytest
from faker import Faker

from evaluation import generate_sessions as gs
from evaluation.common import SEQ_LEN, time_boundaries


@pytest.fixture(scope="module")
def small_dataset():
    rng = np.random.default_rng(123)
    Faker.seed(123)
    fake = Faker()
    days = 21
    prof = gs.build_profiles(12, rng, fake)
    df = gs.simulate_normal(prof, days, pd.Timestamp("2026-04-01"), rng, fake)
    df = gs.assign_splits(df, days)
    plan = {"malicious_insider": 6, "compromised_account": 8, "negligent_insider": 8,
            "overscoped_thirdparty": 6, "benign_burst": 8}
    df = gs.inject_episodes(df, prof, rng, plan)
    return df, days


def test_chronological_and_disjoint(small_dataset):
    df, days = small_dataset
    hours = {s: set(df.loc[df.split == s, "hour_index"]) for s in ("train", "val", "test")}
    assert not (hours["train"] & hours["val"]) and not (hours["val"] & hours["test"])
    assert not (hours["train"] & hours["test"])
    assert max(hours["train"]) < min(hours["val"]) and max(hours["val"]) < min(hours["test"])
    assert set().union(*hours.values()) == set(range(days * 24))
    # every user's hour is in exactly one split
    assert df.groupby(["user_id", "hour_index"]).split.nunique().max() == 1


def test_split_fractions(small_dataset):
    df, days = small_dataset
    total = days * 24
    tr, va, te = (df.loc[df.split == s, "hour_index"] for s in ("train", "val", "test"))
    assert tr.max() + 1 == int(total * 0.70) and va.max() + 1 == int(total * 0.85)


def test_episodes_stay_inside_one_split(small_dataset):
    df, _ = small_dataset
    ep = df.dropna(subset=["episode_id"])
    assert len(ep) > 0
    assert ep.groupby("episode_id").split.nunique().max() == 1
    assert ep.groupby("episode_id").user_id.nunique().max() == 1


def test_benign_bursts_are_negative(small_dataset):
    df, _ = small_dataset
    bb = df[df.is_benign_burst]
    assert len(bb) > 0 and not bb.is_true_threat.any()


def test_fit_calib_buffer():
    total = 21 * 24
    b = time_boundaries(total)
    assert b["train_end"] == int(np.floor(total * 0.70))
    assert b["fit_end"] == int(np.floor(b["train_end"] * 0.75))
    # a CALIB window ending at calib_lo spans [calib_lo-23, calib_lo]; its first hour
    # must come after the last FIT hour (fit_end - 1), so no FIT hour is inside it
    assert b["calib_lo"] - (SEQ_LEN - 1) > b["fit_end"] - 1
    assert b["fit_end"] < b["calib_lo"] < b["train_end"] <= b["val_end"] < total
