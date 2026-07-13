"""Pin the sample-deal results quoted in the README so a data or rule change shows up."""

import pytest

from sde_value.cli import main
from sde_value.deal import load_deal
from sde_value.engine import value_deal

EXPECTED_CUT = {"hvac_service": 0.597, "landscaping": 0.694, "laundromat": 0.507}


def test_sample_deal_cuts(deal_path):
    o = value_deal(load_deal(deal_path))
    assert o["value_cut_pct"] == pytest.approx(EXPECTED_CUT[deal_path.stem], abs=0.0005)


def test_average_cut_across_samples(capsys, deal_path):
    paths = sorted(deal_path.parent.glob("*.yaml"))
    assert main(["summary", *map(str, paths)]) == 0
    assert "Average cut across 3 deals: 59.9%" in capsys.readouterr().out
