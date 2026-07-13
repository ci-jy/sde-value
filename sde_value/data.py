"""Loaders for the cached BLS and IRS SOI extracts in ``data/``."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PERCENTILES = {"pct25": "a_pct25", "median": "a_median", "mean": "a_mean", "pct75": "a_pct75"}

BENEFIT_GROUPS = {
    "small_establishment": "Private industry, establishments with 1-49 workers",
    "management": "Private industry, management, professional, and related",
    "all_private": "Private industry, all workers",
}


@lru_cache(maxsize=None)
def oes_table(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    df = pd.read_csv(data_dir / "bls_oes_wages.csv", dtype=str)
    for col in PERCENTILES.values():
        # OES marks suppressed or top-coded cells with "*", "#" or "**".
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@lru_cache(maxsize=None)
def ecec_table(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    return pd.read_csv(data_dir / "bls_ecec.csv", dtype={"year": str})


@lru_cache(maxsize=None)
def soi_table(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    return pd.read_csv(data_dir / "irs_soi_minor_industry.csv")


@dataclass(frozen=True)
class MarketWage:
    soc: str
    occupation: str
    naics: str
    industry: str
    state: str
    percentile: str
    industry_wage: float      # national wage for the occupation in this industry
    national_wage: float      # national cross-industry wage for the occupation
    state_wage: float         # state cross-industry wage for the occupation
    annual_wage: float        # industry wage scaled by the state/national ratio

    @property
    def state_factor(self) -> float:
        return self.state_wage / self.national_wage


def market_wage(soc: str, naics: str, state: str, percentile: str = "median",
                data_dir: Path = DATA_DIR) -> MarketWage:
    """Annual wage for ``soc`` in industry ``naics`` adjusted to ``state``.

    OES does not publish industry-by-state cells, so the national industry
    wage is scaled by how the state's cross-industry wage for the same
    occupation compares with the national one.
    """
    col = PERCENTILES[percentile]
    df = oes_table(data_dir)
    occ = df[df.occ_code == soc]
    if occ.empty:
        raise KeyError(f"occupation {soc} is not in the OES extract")
    ind = occ[(occ.scope == "industry") & (occ.naics == naics)]
    nat = occ[occ.scope == "national"]
    st = occ[(occ.scope == "state") & (occ.prim_state == state.upper())]
    if ind.empty or pd.isna(ind[col].iloc[0]):
        raise KeyError(f"no OES {percentile} wage for {soc} in NAICS {naics}")
    if st.empty or pd.isna(st[col].iloc[0]):
        raise KeyError(f"no OES {percentile} wage for {soc} in {state}")
    industry_wage = float(ind[col].iloc[0])
    national_wage = float(nat[col].iloc[0])
    state_wage = float(st[col].iloc[0])
    return MarketWage(
        soc=soc, occupation=occ.occ_title.iloc[0], naics=naics,
        industry=ind.naics_title.iloc[0], state=state.upper(), percentile=percentile,
        industry_wage=industry_wage, national_wage=national_wage, state_wage=state_wage,
        annual_wage=round(industry_wage * state_wage / national_wage, 2),
    )


@dataclass(frozen=True)
class BenefitsLoad:
    group: str
    period: str
    wages_per_hour: float
    benefits_per_hour: float

    @property
    def load(self) -> float:
        """Benefits as a fraction of wages, rounded to 4 places for the workbook."""
        return round(self.benefits_per_hour / self.wages_per_hour, 4)


def benefits_load(group: str = "small_establishment", data_dir: Path = DATA_DIR) -> BenefitsLoad:
    df = ecec_table(data_dir)
    df = df[df.group == BENEFIT_GROUPS[group]].sort_values(["year", "period"])
    latest = df.iloc[-1][["year", "period"]]
    cur = df[(df.year == latest.year) & (df.period == latest.period)].set_index("measure").value
    return BenefitsLoad(group=BENEFIT_GROUPS[group], period=f"{latest.year} {latest.period}",
                        wages_per_hour=float(cur["wages"]), benefits_per_hour=float(cur["benefits"]))


SOI_EXPENSE_ITEMS = [
    "cogs", "officer_comp", "salaries_wages", "repairs", "rent", "taxes_licenses",
    "interest", "depreciation", "amortization", "advertising", "pension",
    "employee_benefits", "other_deductions",
]


def soi_ratios(industry: str, data_dir: Path = DATA_DIR) -> dict[str, float]:
    """Each SOI line item as a share of business receipts, for one minor industry."""
    df = soi_table(data_dir)
    sub = df[df.industry == industry].set_index("item").value
    if sub.empty:
        raise KeyError(f"SOI industry {industry!r} is not in the extract")
    receipts = sub["business_receipts"]
    # Suppressed cells are treated as zero; they are always small items.
    return {item: round(float(sub[item]) / float(receipts), 4) if pd.notna(sub[item]) else 0.0
            for item in SOI_EXPENSE_ITEMS + ["net_income"]}


def soi_title(industry: str, data_dir: Path = DATA_DIR) -> str:
    df = soi_table(data_dir)
    return str(df[df.industry == industry].soi_title.iloc[0])
