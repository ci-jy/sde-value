from pathlib import Path

import pytest

from sde_value.deal import load_deal

ROOT = Path(__file__).resolve().parent.parent
DEALS = sorted((ROOT / "deals").glob("*.yaml"))


@pytest.fixture(params=DEALS, ids=lambda p: p.stem)
def deal_path(request):
    return request.param


@pytest.fixture
def hvac():
    return load_deal(ROOT / "deals" / "hvac_service.yaml")
