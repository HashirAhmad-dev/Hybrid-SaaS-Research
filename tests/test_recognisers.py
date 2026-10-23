"""T3.5 custom recognisers: Mastercard 51-55 and 2221-2720 with Luhn, street addresses."""
import re

import pytest

from evaluation.build_pii_corpus_v2 import luhn_complete, luhn_ok
from evaluation.pii_v2 import ADDRESS_RE, MASTERCARD_RE


def test_luhn():
    assert luhn_ok("4111111111111111") and not luhn_ok("4111111111111112")
    import random
    r = random.Random(0)
    for p in ("51", "55", "2221", "2720", "4"):
        assert luhn_ok(luhn_complete(p, 16, r))


@pytest.mark.parametrize("s,ok", [
    ("5105105105105100", True), ("5555 5555 5555 4444", True), ("2221-0000-0000-0009", True),
    ("2720999999999996", True), ("2721000000000000", False), ("5011000000000000", False),
    ("4111111111111111", False),
])
def test_mastercard_ranges(s, ok):
    assert bool(re.search(MASTERCARD_RE, s)) == ok


@pytest.mark.parametrize("s,ok", [
    ("767 Thompson Walk Suite 688", True), ("12 Baker Street", True), ("4 Oak Rd, Leeds", True),
    ("Order Ref ORD-8949-001632", False), ("the 3 managers met", False),
])
def test_address_pattern(s, ok):
    assert bool(re.search(ADDRESS_RE, s)) == ok
