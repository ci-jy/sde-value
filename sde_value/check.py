"""Recalculate a workbook in headless LibreOffice and compare every output cell
with the Python engine.

The engine is fed the input cells read back from the workbook, not the deal
file, so the check still holds after someone flips add-back toggles or edits
inputs by hand.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from .deal import PNL_LINES, DCFTerms, LoanTerms
from .engine import AddBackInput, ModelInputs, evaluate

CENT = 0.005
RATIO_TOL = 1e-9
RATIO_SUFFIXES = ("_margin", "_pct", "_gap", "_factor", "_deal", "_recommend", "_df",
                  "_share", "_multiple", "_dscr")


class RecalcError(RuntimeError):
    pass


def soffice_binary() -> str:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    raise RecalcError("LibreOffice (soffice) is not installed; apt-get install libreoffice-calc")


def recalculate(path: str | Path, out_dir: str | Path | None = None) -> Path:
    """Open the workbook in headless LibreOffice, recalculate and save a copy.

    openpyxl writes formulas without cached results, so LibreOffice has to
    compute every formula on load; the saved copy carries those values.
    """
    path = Path(path).resolve()
    out_dir = Path(out_dir or tempfile.mkdtemp(prefix="sde-recalc-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    # A private profile keeps us away from any LibreOffice the user has open.
    profile = out_dir / "lo-profile"
    cmd = [soffice_binary(), "--headless", "--norestore", "--nolockcheck",
           f"-env:UserInstallation={profile.as_uri()}",
           "--convert-to", "xlsx:Calc Office Open XML", "--outdir", str(out_dir), str(path)]
    env = dict(os.environ)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
    result = out_dir / path.name
    if proc.returncode != 0 or not result.exists():
        raise RecalcError(f"LibreOffice failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return result


def named_cells(path: str | Path) -> tuple[dict[str, object], dict[str, str]]:
    """Value and sheet of every single-cell defined name in a workbook (cached results)."""
    wb = load_workbook(path, data_only=True)
    values, sheets = {}, {}
    for name, dn in wb.defined_names.items():
        dests = list(dn.destinations)
        if len(dests) != 1:
            continue
        sheet, ref = dests[0]
        values[name] = wb[sheet][ref.replace("$", "")].value
        sheets[name] = sheet
    return values, sheets


def named_values(path: str | Path) -> dict[str, object]:
    """Value of every single-cell defined name in a workbook (cached results)."""
    return named_cells(path)[0]


def _yes(value) -> bool:
    return str(value).strip().lower() in ("yes", "1", "true")


def inputs_from_values(v: dict[str, object]) -> ModelInputs:
    n_ab = sorted(int(m.group(1)) for k in v if (m := re.fullmatch(r"i_ab(\d+)_amount", k)))
    n_mult = sorted(int(m.group(1)) for k in v if (m := re.fullmatch(r"i_mult(\d+)", k)))
    num = lambda k: float(v[k] or 0)  # noqa: E731
    addbacks = [
        AddBackInput(item=f"#{i}", line="", label=str(v[f"i_ab{i}_label"]).strip(),
                     amount=num(f"i_ab{i}_amount"), years_seen=int(num(f"i_ab{i}_years")),
                     continues=_yes(v[f"i_ab{i}_continues"]),
                     documented=_yes(v[f"i_ab{i}_documented"]),
                     accept=num(f"i_ab{i}_accept") == 1)
        for i in n_ab
    ]
    soi = {k[len("i_soi_"):]: num(k) for k in v if k.startswith("i_soi_")}
    # The DCF's column count is layout, not an input: count the year columns.
    years = len([k for k in v if re.fullmatch(r"o_dcf_y\d+_fcf", k)])
    n_acc = sorted(int(m.group(1)) for k in v if (m := re.fullmatch(r"i_sens_acc(\d+)", k)))
    dcf = DCFTerms(years=years, **{f: num(f"i_dcf_{f}") for f in (
        "growth", "capex_pct", "nwc_pct", "tax_rate", "discount_rate", "terminal_growth")})
    loan = LoanTerms(**{f: num(f"i_fin_{f}") for f in LoanTerms.__dataclass_fields__})
    return ModelInputs(
        revenue=num("i_revenue"), expenses={line: num(f"i_{line}") for line in PNL_LINES},
        addbacks=addbacks, industry_wage=num("i_industry_wage"),
        national_wage=num("i_national_wage"), state_wage=num("i_state_wage"),
        fte=num("i_fte"), benefits_load=num("i_benefits_load"),
        asking_multiple=num("i_asking_multiple"), multiples=[num(f"i_mult{j}") for j in n_mult],
        soi=soi, dcf=dcf, loan=loan, acceptance=[num(f"i_sens_acc{k}") for k in n_acc],
    )


@dataclass
class Mismatch:
    name: str
    workbook: object
    engine: object


@dataclass
class CheckResult:
    compared: int
    mismatches: list[Mismatch]
    missing: list[str]
    engine: dict
    workbook: dict

    @property
    def ok(self) -> bool:
        return not self.mismatches and not self.missing


def compare(values: dict[str, object], sheets: dict[str, str] | None = None,
            tabs: list[str] | None = None) -> CheckResult:
    """Compare output cells with the engine; ``tabs`` limits it to cells on those sheets.

    With ``tabs``, engine keys are matched to sheets through ``sheets`` (name ->
    sheet title), so an engine value with no cell anywhere still counts as missing.
    """
    expected = evaluate(inputs_from_values(values))
    if tabs is not None:
        sheets = sheets or {}
        unknown = set(tabs) - set(sheets.values())
        if unknown:
            raise RecalcError(f"no such tab(s): {', '.join(sorted(unknown))}")
        on_tabs = lambda name: sheets.get(name) in tabs  # noqa: E731
        expected = {k: v for k, v in expected.items()
                    if f"o_{k}" not in sheets or on_tabs(f"o_{k}")}
        values = {k: v for k, v in values.items() if not k.startswith("o_") or on_tabs(k)}
    mismatches, missing = [], []
    compared = 0
    for key, want in expected.items():
        name = f"o_{key}"
        if name not in values:
            missing.append(name)
            continue
        got = values[name]
        compared += 1
        if isinstance(want, str):
            if str(got) != want:
                mismatches.append(Mismatch(name, got, want))
            continue
        if not isinstance(got, (int, float)):
            mismatches.append(Mismatch(name, got, want))
            continue
        tol = RATIO_TOL if key.endswith(RATIO_SUFFIXES) else CENT
        if abs(float(got) - want) > tol:
            mismatches.append(Mismatch(name, got, want))
    # Output cells the engine does not know about are a mismatch too.
    extra = sorted(k for k in values if k.startswith("o_") and k[2:] not in expected)
    missing.extend(f"{k} (no engine value)" for k in extra)
    return CheckResult(compared, mismatches, missing, expected, values)


def check_workbook(path: str | Path, keep_dir: str | Path | None = None,
                   tabs: list[str] | None = None) -> CheckResult:
    with tempfile.TemporaryDirectory(prefix="sde-check-") as tmp:
        recalced = recalculate(path, keep_dir or tmp)
        return compare(*named_cells(recalced), tabs=tabs)
