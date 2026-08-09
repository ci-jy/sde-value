"""Formula/engine agreement: build each deal, recalculate in LibreOffice, compare."""

import shutil

import pytest
from openpyxl import load_workbook

from sde_value.check import check_workbook, compare, named_values, recalculate
from sde_value.deal import load_deal
from sde_value.engine import value_deal
from sde_value.workbook import build_workbook

needs_lo = pytest.mark.skipif(not (shutil.which("soffice") or shutil.which("libreoffice")),
                              reason="LibreOffice is required for the recalculation check")


def test_every_calculated_cell_is_a_formula(tmp_path, hvac):
    path = build_workbook(hvac, tmp_path / "hvac.xlsx")
    wb = load_workbook(path)
    outputs = [n for n in wb.defined_names if n.startswith("o_")]
    assert len(outputs) > 80
    for name in outputs:
        sheet, ref = next(iter(wb.defined_names[name].destinations))
        value = wb[sheet][ref.replace("$", "")].value
        assert isinstance(value, str) and value.startswith("="), name
    assert wb.sheetnames[:4] == ["Inputs", "Add-back Register", "Normalised Earnings",
                                 "Multiple Valuation"]


@needs_lo
def test_libreoffice_matches_engine(tmp_path, deal_path):
    deal = load_deal(deal_path)
    path = build_workbook(deal, tmp_path / f"{deal.slug}.xlsx")
    result = check_workbook(path)
    assert result.ok, (result.mismatches, result.missing)
    if deal.slug == "hvac_service":
        # 12 add-backs and 7 multiples give 105 earnings and valuation cells; a 5-year
        # DCF adds 48, the financing tab 36 and a 5 x 7 sensitivity grid 75
        assert result.compared == 105 + 48 + 36 + 75
    # and the workbook agrees with the engine run straight from the deal file
    direct = value_deal(deal)
    assert result.workbook["o_repriced_value"] == pytest.approx(direct["repriced_value"], abs=0.005)


@needs_lo
def test_toggling_an_addback_changes_value(tmp_path, hvac):
    path = build_workbook(hvac, tmp_path / "hvac.xlsx")
    before = named_values(recalculate(path, tmp_path / "before"))

    # Buyer gives the seller the benefit of the doubt on the trade show trip.
    wb = load_workbook(path)
    idx = next(i for i, ab in enumerate(hvac.addbacks, 1) if "Las Vegas" in ab.item)
    sheet, ref = next(iter(wb.defined_names[f"i_ab{idx}_accept"].destinations))
    assert wb[sheet][ref.replace("$", "")].value == 0
    wb[sheet][ref.replace("$", "")].value = 1
    wb.save(path)

    after_values = named_values(recalculate(path, tmp_path / "after"))
    result = compare(after_values)
    assert result.ok, result.mismatches
    delta = after_values["o_repriced_value"] - before["o_repriced_value"]
    assert delta == pytest.approx(5200 * hvac.asking_multiple, abs=0.005)


@needs_lo
def test_checker_catches_a_broken_formula(tmp_path, hvac):
    path = build_workbook(hvac, tmp_path / "hvac.xlsx")
    wb = load_workbook(path)
    sheet, ref = next(iter(wb.defined_names["o_replacement_benefits"].destinations))
    wb[sheet][ref.replace("$", "")].value = "=0"   # someone forgets the benefits load
    wb.save(path)
    result = check_workbook(path)
    assert not result.ok
    names = {m.name for m in result.mismatches}
    assert "o_replacement_benefits" in names and "o_repriced_value" in names
