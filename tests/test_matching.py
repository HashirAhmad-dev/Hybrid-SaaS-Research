"""PII entity matching rules (type exact, normalised value, fuzzy >= 0.85, one-to-one)."""
import pytest

from evaluation.pii_common import match_entities, normalise, prf, similarity, sensitivity_score


def E(t, v):
    return {"type": t, "value": v}


def test_normalise():
    assert normalise("Sara.Malik@Example.com") == "saramalik@examplecom"
    assert normalise("4111-1111 1111 1111") == "4111111111111111"
    assert normalise("José") == "jose"


def test_similarity_bounds():
    assert similarity("abc", "abc") == 1.0
    assert similarity("", "abc") == 0.0
    assert 0.0 < similarity("4111111111111111", "4111111111111112") < 1.0


def test_exact_after_normalisation_matches():
    tp, fp, fn, _ = match_entities([E("EMAIL", "sara.malik@x.com")],
                                   [E("EMAIL", "sara malik@x.com")])
    assert (tp, fp, fn) == (1, 0, 0)


def test_type_must_match():
    tp, fp, fn, _ = match_entities([E("PERSON", "Ali Khan")], [E("ADDRESS", "Ali Khan")])
    assert (tp, fp, fn) == (0, 1, 1)


def test_duplicates_are_false_positives():
    g = [E("PHONE", "+92 300 1234567")]
    p = [E("PHONE", "+92 300 1234567"), E("PHONE", "+923001234567")]
    assert match_entities(g, p)[:3] == (1, 1, 0)


def test_fuzzy_threshold_and_exact_mode():
    g = [E("PERSON", "Muhammad Abdullah")]
    near = [E("PERSON", "Muhammad Abdulah")]          # one letter missing
    assert match_entities(g, near)[:3] == (1, 0, 0)
    assert match_entities(g, near, exact=True)[:3] == (0, 1, 1)
    far = [E("PERSON", "Ahmed Raza")]
    assert match_entities(g, far)[:3] == (0, 1, 1)


def test_prf_and_sensitivity():
    m = prf(3, 1, 2)
    assert m["precision"] == pytest.approx(0.75) and m["recall"] == pytest.approx(0.6)
    assert m["f1"] == pytest.approx(2 * 0.75 * 0.6 / 1.35)
    assert sensitivity_score(2, 3, 4) == 20 + 15 + 4
    assert sensitivity_score(20, 0, 0) == 100
