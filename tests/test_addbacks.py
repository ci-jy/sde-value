import pytest

from sde_value.addbacks import accepted, classify, classify_addback, recommend
from sde_value.deal import AddBack


@pytest.mark.parametrize("label", ["owner compensation", "non-cash", "financing"])
def test_standard_addbacks_keep_their_label(label):
    # even if they show up every year, owner pay and D&A are legitimate SDE add-backs
    assert classify(label, years_seen=3, continues=False) == label
    assert recommend(label, documented=False) is True


def test_one_time_seen_once_stays_one_time():
    assert classify("one-time", 1, False) == "one-time"


@pytest.mark.parametrize("years", [2, 3])
def test_one_time_that_repeats_is_recurring(years):
    assert classify("one-time", years, False) == "recurring-disguised"


def test_discretionary_that_continues_is_recurring():
    assert classify("discretionary", 1, True) == "recurring-disguised"
    assert classify("discretionary", 3, False) == "discretionary"


def test_recurring_disguised_is_rejected_even_with_documents():
    assert recommend("recurring-disguised", documented=True) is False


@pytest.mark.parametrize("label", ["discretionary", "one-time"])
def test_undocumented_items_are_rejected(label):
    assert recommend(label, documented=False) is False
    assert recommend(label, documented=True) is True


def test_buyer_override_beats_recommendation():
    ab = AddBack(item="Truck", line="other_deductions", label="discretionary", amount=1000,
                 continues=True)
    assert classify_addback(ab) == ("recurring-disguised", False)
    assert accepted(ab) is False
    ab.accept = True
    assert accepted(ab) is True


def test_hvac_register_classifications(hvac):
    got = {ab.item: classify_addback(ab) for ab in hvac.addbacks}
    assert got["Owner salary"] == ("owner compensation", True)
    assert got["Compressor warranty callbacks"] == ("recurring-disguised", False)
    assert got["Owner F-250 lease and fuel"] == ("recurring-disguised", False)
    assert got["Settlement of a customer property-damage claim"] == ("one-time", True)
    assert got["Trade show trip to Las Vegas"] == ("discretionary", False)
