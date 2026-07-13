"""Deal files: the seller's P&L, the claimed add-backs and the buyer's
assumptions, read from YAML and validated before anything is built."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .data import BENEFIT_GROUPS, PERCENTILES, SOI_EXPENSE_ITEMS

# P&L lines in the order they appear on the Inputs sheet; same keys as SOI.
PNL_LINES = SOI_EXPENSE_ITEMS

PNL_LABELS = {
    "cogs": "Cost of goods sold",
    "officer_comp": "Owner / officer compensation",
    "salaries_wages": "Salaries and wages",
    "repairs": "Repairs and maintenance",
    "rent": "Rent",
    "taxes_licenses": "Taxes and licenses",
    "interest": "Interest",
    "depreciation": "Depreciation",
    "amortization": "Amortization",
    "advertising": "Advertising",
    "pension": "Pension and profit-sharing",
    "employee_benefits": "Employee benefits",
    "other_deductions": "Other operating expenses",
}

# What the seller or broker calls each add-back.
SELLER_LABELS = ("owner compensation", "discretionary", "one-time", "non-cash", "financing")

DEFAULT_MULTIPLES = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]


class DealError(ValueError):
    pass


@dataclass
class AddBack:
    item: str
    line: str
    label: str
    amount: float
    support: str = ""
    documented: bool = True
    years_seen: int = 1
    continues: bool = False       # would the expense carry on under a new owner?
    accept: bool | None = None    # buyer override; None means use the recommendation
    note: str = ""


@dataclass
class Deal:
    name: str
    description: str
    soi_industry: str
    naics: str
    state: str
    revenue: float
    expenses: dict[str, float]
    addbacks: list[AddBack]
    asking_multiple: float
    replacement_soc: str = "11-1021"
    wage_percentile: str = "median"
    replacement_fte: float = 1.0
    benefits_group: str = "small_establishment"
    multiples: list[float] = field(default_factory=lambda: list(DEFAULT_MULTIPLES))
    fiscal_year_label: str = "Most recent fiscal year"
    notes: list[str] = field(default_factory=list)
    path: Path | None = None

    @property
    def slug(self) -> str:
        return self.path.stem if self.path else "deal"


def _num(value, where: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise DealError(f"{where}: expected a number, got {value!r}") from None


def parse_deal(raw: dict, path: Path | None = None) -> Deal:
    try:
        pnl = raw["pnl"]
        expenses = {line: _num(pnl.get(line, 0), f"pnl.{line}") for line in PNL_LINES}
        unknown = set(pnl) - set(PNL_LINES) - {"revenue"}
        if unknown:
            raise DealError(f"unknown P&L lines: {sorted(unknown)}")
        addbacks = []
        for i, ab in enumerate(raw.get("addbacks", []), 1):
            where = f"addbacks[{i}]"
            label = str(ab["label"]).strip().lower()
            if label not in SELLER_LABELS:
                raise DealError(f"{where}: label must be one of {SELLER_LABELS}, got {label!r}")
            if ab["line"] not in PNL_LINES:
                raise DealError(f"{where}: unknown P&L line {ab['line']!r}")
            addbacks.append(AddBack(
                item=str(ab["item"]), line=ab["line"], label=label,
                amount=_num(ab["amount"], f"{where}.amount"),
                support=str(ab.get("support", "")), documented=bool(ab.get("documented", True)),
                years_seen=int(ab.get("years_seen", 1)), continues=bool(ab.get("continues", False)),
                accept=ab.get("accept"), note=str(ab.get("note", "")),
            ))
        repl = raw.get("replacement", {})
        deal = Deal(
            name=str(raw["name"]), description=str(raw.get("description", "")),
            soi_industry=str(raw["industry"]["soi"]), naics=str(raw["industry"]["naics"]),
            state=str(raw["state"]).upper(), revenue=_num(pnl["revenue"], "pnl.revenue"),
            expenses=expenses, addbacks=addbacks,
            asking_multiple=_num(raw["asking"]["multiple"], "asking.multiple"),
            replacement_soc=str(repl.get("soc", "11-1021")),
            wage_percentile=str(repl.get("percentile", "median")),
            replacement_fte=_num(repl.get("fte", 1.0), "replacement.fte"),
            benefits_group=str(repl.get("benefits_group", "small_establishment")),
            multiples=[_num(m, "multiples") for m in raw.get("multiples", DEFAULT_MULTIPLES)],
            fiscal_year_label=str(raw.get("fiscal_year_label", "Most recent fiscal year")),
            notes=list(raw.get("notes", [])), path=path,
        )
    except KeyError as exc:
        raise DealError(f"missing required field {exc}") from None
    validate(deal)
    return deal


def validate(deal: Deal) -> None:
    if deal.revenue <= 0:
        raise DealError("revenue must be positive")
    if deal.wage_percentile not in PERCENTILES:
        raise DealError(f"replacement.percentile must be one of {list(PERCENTILES)}")
    if deal.benefits_group not in BENEFIT_GROUPS:
        raise DealError(f"replacement.benefits_group must be one of {list(BENEFIT_GROUPS)}")
    if not 0 < deal.replacement_fte <= 2:
        raise DealError("replacement.fte must be between 0 and 2")
    if not deal.multiples:
        raise DealError("at least one multiple is needed")
    # An add-back can only come out of an expense that is actually on the P&L.
    by_line: dict[str, float] = {}
    for ab in deal.addbacks:
        if ab.amount <= 0:
            raise DealError(f"add-back {ab.item!r} must have a positive amount")
        by_line[ab.line] = by_line.get(ab.line, 0) + ab.amount
    for line, total in by_line.items():
        if total > deal.expenses[line] + 0.005:
            raise DealError(
                f"add-backs against {line} total {total:,.0f}, more than the "
                f"{deal.expenses[line]:,.0f} on the P&L")


def load_deal(path: str | Path) -> Deal:
    path = Path(path)
    with open(path) as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise DealError(f"{path}: not a deal file")
    return parse_deal(raw, path)
