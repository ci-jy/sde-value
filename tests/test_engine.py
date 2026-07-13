import pytest

from sde_value.data import benefits_load, market_wage, soi_ratios
from sde_value.deal import DealError, PNL_LINES, load_deal, parse_deal
from sde_value.engine import AddBackInput, ModelInputs, evaluate, inputs_from_deal, value_deal


def simple_inputs(**over):
    expenses = {line: 0.0 for line in PNL_LINES}
    expenses.update(cogs=500_000, officer_comp=80_000, other_deductions=300_000,
                    depreciation=20_000)
    base = dict(
        revenue=1_000_000, expenses=expenses,
        addbacks=[
            AddBackInput("Owner salary", "officer_comp", "owner compensation", 80_000, 3,
                         False, True, True),
            AddBackInput("Depreciation", "depreciation", "non-cash", 20_000, 3, False, True,
                         True),
            AddBackInput("Boat", "other_deductions", "discretionary", 10_000, 3, False, False,
                         False),
        ],
        industry_wage=100_000, national_wage=100_000, state_wage=90_000, fte=1.0,
        benefits_load=0.3, asking_multiple=4.0, multiples=[3.0, 4.0],
        soi={"net_income": 0.05, "interest": 0.01, "depreciation": 0.02, "amortization": 0.0},
    )
    base.update(over)
    return ModelInputs(**base)


def test_sde_methods_by_hand():
    o = evaluate(simple_inputs())
    assert o["net_income"] == 100_000
    # seller adds back everything claimed
    assert o["seller_sde"] == 100_000 + 80_000 + 20_000 + 10_000
    # buyer drops the boat
    assert o["normalised_sde"] == 200_000
    assert o["rejected_total"] == 10_000


def test_replacement_cost_deduction():
    o = evaluate(simple_inputs())
    # 100k industry wage scaled by the state factor 0.9, plus 30% benefits
    assert o["market_wage"] == pytest.approx(90_000)
    assert o["replacement_cost"] == pytest.approx(117_000)
    assert o["normalised_ebitda"] == pytest.approx(200_000 - 117_000)


def test_part_time_replacement_scales_cost():
    o = evaluate(simple_inputs(fte=0.5))
    assert o["replacement_cost"] == pytest.approx(58_500)


def test_valuation_and_cut():
    o = evaluate(simple_inputs())
    assert o["asking_value"] == 210_000 * 4
    assert o["repriced_value"] == pytest.approx(83_000 * 4)
    assert o["value_cut"] == pytest.approx(o["value_from_rejected"] + o["value_from_replacement"])
    assert o["mult1_normalised_ebitda"] == pytest.approx(83_000 * 3)


def test_toggle_moves_value_by_the_multiple():
    base = simple_inputs()
    flipped = simple_inputs()
    flipped.addbacks[2].accept = True
    delta = evaluate(flipped)["repriced_value"] - evaluate(base)["repriced_value"]
    assert delta == pytest.approx(10_000 * 4)


def test_baseline_ebitda_benchmark():
    o = evaluate(simple_inputs())
    assert o["base_industry_ebitda_margin"] == pytest.approx(0.08)
    assert o["base_ebitda_margin_gap"] == pytest.approx(0.083 - 0.08)


def test_market_wage_uses_state_factor():
    w = market_wage("11-1021", "238200", "TX")
    assert w.industry_wage > 0 and w.state_wage > 0
    assert w.annual_wage == pytest.approx(w.industry_wage * w.state_wage / w.national_wage,
                                          abs=0.01)


def test_unknown_wage_cell_raises():
    with pytest.raises(KeyError):
        market_wage("11-1021", "999999", "TX")


def test_benefits_load_is_plausible():
    load = benefits_load()
    assert 0.2 < load.load < 0.6


def test_sample_deals_follow_soi_ratios(deal_path):
    deal = load_deal(deal_path)
    ratios = soi_ratios(deal.soi_industry)
    for line, amount in deal.expenses.items():
        assert amount == pytest.approx(deal.revenue * ratios[line], abs=50.01), line


def test_sample_deals_value_below_asking(deal_path):
    o = value_deal(load_deal(deal_path))
    assert 0 < o["repriced_value"] < o["asking_value"]
    assert o["normalised_sde"] <= o["seller_sde"]


def test_inputs_from_deal_resolves_market_data(hvac):
    m, src = inputs_from_deal(hvac)
    assert m.industry_wage == src["wage"].industry_wage
    assert m.soi["cogs"] > 0.5


def test_addbacks_cannot_exceed_their_line():
    raw = {
        "name": "x", "industry": {"soi": "plumbing_hvac", "naics": "238200"}, "state": "TX",
        "asking": {"multiple": 4},
        "pnl": {"revenue": 100_000, "officer_comp": 10_000},
        "addbacks": [{"item": "Owner", "line": "officer_comp", "label": "owner compensation",
                      "amount": 12_000}],
    }
    with pytest.raises(DealError, match="more than"):
        parse_deal(raw)


def test_unknown_label_rejected():
    raw = {
        "name": "x", "industry": {"soi": "plumbing_hvac", "naics": "238200"}, "state": "TX",
        "asking": {"multiple": 4}, "pnl": {"revenue": 100_000, "rent": 10_000},
        "addbacks": [{"item": "Rent", "line": "rent", "label": "personal", "amount": 1_000}],
    }
    with pytest.raises(DealError, match="label"):
        parse_deal(raw)
