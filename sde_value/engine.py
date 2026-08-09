"""Reference valuation engine.

Every number the workbook calculates is calculated here a second time, in
plain Python, under the same key the workbook uses for the cell's defined
name. The checker compares the two after LibreOffice recalculates the file.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import addbacks as ab_rules
from .data import benefits_load, market_wage, soi_ratios, soi_title
from .deal import DEFAULT_ACCEPTANCE, PNL_LINES, DCFTerms, Deal, LoanTerms

CLASSES = ("owner compensation", "discretionary", "one-time", "recurring-disguised",
           "non-cash", "financing")

# Lines compared with the industry on the baseline sheet.
BASELINE_LINES = ["cogs", "officer_comp", "salaries_wages", "rent", "other_deductions"]

# Purchase prices tested on the financing tab, in column order.
PRICE_CASES = {"asking": "Seller's asking value", "repriced": "Repriced value",
               "dcf": "DCF value"}


@dataclass
class AddBackInput:
    item: str
    line: str
    label: str
    amount: float
    years_seen: int
    continues: bool
    documented: bool
    accept: bool


@dataclass
class ModelInputs:
    """Everything the workbook's formulas depend on, and nothing else."""
    revenue: float
    expenses: dict[str, float]
    addbacks: list[AddBackInput]
    industry_wage: float
    national_wage: float
    state_wage: float
    fte: float
    benefits_load: float
    asking_multiple: float
    multiples: list[float]
    soi: dict[str, float] = field(default_factory=dict)
    dcf: DCFTerms = field(default_factory=DCFTerms)
    loan: LoanTerms = field(default_factory=LoanTerms)
    acceptance: list[float] = field(default_factory=lambda: list(DEFAULT_ACCEPTANCE))


def inputs_from_deal(deal: Deal) -> tuple[ModelInputs, dict]:
    """Resolve the deal's market data and return model inputs plus source details."""
    wage = market_wage(deal.replacement_soc, deal.naics, deal.state, deal.wage_percentile)
    load = benefits_load(deal.benefits_group)
    ratios = soi_ratios(deal.soi_industry)
    dcf = DCFTerms(**vars(deal.dcf))
    if dcf.capex_pct is None:
        # Maintenance capex taken as what the seller already depreciates.
        dcf.capex_pct = round(deal.expenses["depreciation"] / deal.revenue, 4)
    items = [
        AddBackInput(item=a.item, line=a.line, label=a.label, amount=a.amount,
                     years_seen=a.years_seen, continues=a.continues,
                     documented=a.documented, accept=ab_rules.accepted(a))
        for a in deal.addbacks
    ]
    inputs = ModelInputs(
        revenue=deal.revenue, expenses=dict(deal.expenses), addbacks=items,
        industry_wage=wage.industry_wage, national_wage=wage.national_wage,
        state_wage=wage.state_wage, fte=deal.replacement_fte, benefits_load=load.load,
        asking_multiple=deal.asking_multiple, multiples=list(deal.multiples), soi=ratios,
        dcf=dcf, loan=LoanTerms(**vars(deal.loan)), acceptance=list(deal.acceptance),
    )
    sources = {"wage": wage, "benefits": load, "soi_title": soi_title(deal.soi_industry)}
    return inputs, sources


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def payment_factor(rate: float, years: float) -> float:
    """Annual debt service per dollar borrowed, paid monthly.

    Same as the workbook's ``PMT(rate/12, years*12, -1)*12``.
    """
    n = years * 12
    if rate == 0:
        return 12 / n
    r = rate / 12
    return 12 * r / (1 - (1 + r) ** -n)


def evaluate(m: ModelInputs) -> dict[str, float | str]:
    """Return every output keyed by the workbook's defined name (without the ``o_`` prefix)."""
    out: dict[str, float | str] = {}
    total_expenses = sum(m.expenses[line] for line in PNL_LINES)
    net_income = m.revenue - total_expenses
    out["total_expenses"] = total_expenses
    out["net_income"] = net_income
    out["net_margin"] = _safe_div(net_income, m.revenue)

    claimed = {c: 0.0 for c in CLASSES}
    kept = {c: 0.0 for c in CLASSES}
    for i, a in enumerate(m.addbacks, 1):
        cls = ab_rules.classify(a.label, a.years_seen, a.continues)
        out[f"ab{i}_class"] = cls
        out[f"ab{i}_recommend"] = 1.0 if ab_rules.recommend(cls, a.documented) else 0.0
        accepted_amount = a.amount if a.accept else 0.0
        out[f"ab{i}_accepted"] = accepted_amount
        claimed[cls] += a.amount
        kept[cls] += accepted_amount

    for c in CLASSES:
        key = c.replace(" ", "_").replace("-", "_")
        out[f"claimed_{key}"] = claimed[c]
        out[f"accepted_{key}"] = kept[c]
    claimed_total = sum(claimed.values())
    accepted_total = sum(kept.values())
    out["claimed_total"] = claimed_total
    out["accepted_total"] = accepted_total
    out["rejected_total"] = claimed_total - accepted_total

    seller_sde = net_income + claimed_total
    normalised_sde = net_income + accepted_total
    out["seller_sde"] = seller_sde
    out["normalised_sde"] = normalised_sde

    annual_wage = m.industry_wage * _safe_div(m.state_wage, m.national_wage)
    replacement_wage = annual_wage * m.fte
    replacement_benefits = replacement_wage * m.benefits_load
    replacement_cost = replacement_wage + replacement_benefits
    normalised_ebitda = normalised_sde - replacement_cost
    out["state_factor"] = _safe_div(m.state_wage, m.national_wage)
    out["market_wage"] = annual_wage
    out["replacement_wage"] = replacement_wage
    out["replacement_benefits"] = replacement_benefits
    out["replacement_cost"] = replacement_cost
    out["normalised_ebitda"] = normalised_ebitda
    out["seller_sde_margin"] = _safe_div(seller_sde, m.revenue)
    out["normalised_sde_margin"] = _safe_div(normalised_sde, m.revenue)
    out["normalised_ebitda_margin"] = _safe_div(normalised_ebitda, m.revenue)

    asking_value = seller_sde * m.asking_multiple
    repriced_value = normalised_ebitda * m.asking_multiple
    out["asking_value"] = asking_value
    out["repriced_value"] = repriced_value
    out["value_cut"] = asking_value - repriced_value
    out["value_cut_pct"] = _safe_div(asking_value - repriced_value, asking_value)
    out["value_from_rejected"] = (claimed_total - accepted_total) * m.asking_multiple
    out["value_from_replacement"] = replacement_cost * m.asking_multiple

    for j, mult in enumerate(m.multiples, 1):
        out[f"mult{j}_seller_sde"] = seller_sde * mult
        out[f"mult{j}_normalised_sde"] = normalised_sde * mult
        out[f"mult{j}_normalised_ebitda"] = normalised_ebitda * mult

    for line in BASELINE_LINES:
        deal_ratio = _safe_div(m.expenses[line], m.revenue)
        out[f"base_{line}_deal"] = deal_ratio
        out[f"base_{line}_gap"] = deal_ratio - m.soi.get(line, 0.0)
    out["base_net_margin_gap"] = out["net_margin"] - m.soi.get("net_income", 0.0)
    # Industry corporations already pay their officers, so net income plus
    # interest, depreciation and amortisation is the like-for-like benchmark
    # for normalised EBITDA.
    industry_ebitda = sum(m.soi.get(k, 0.0) for k in
                          ("net_income", "interest", "depreciation", "amortization"))
    out["base_industry_ebitda_margin"] = industry_ebitda
    out["base_ebitda_margin_gap"] = out["normalised_ebitda_margin"] - industry_ebitda

    _dcf(m, out)
    _financing(m, out)
    _sensitivity(m, out)
    return out


def _dcf(m: ModelInputs, out: dict) -> None:
    """Unlevered free cash flow from normalised EBITDA, held at today's margin."""
    d = m.dcf
    capex_pct = d.capex_pct or 0.0
    margin = out["normalised_ebitda_margin"]
    prev_revenue = m.revenue
    pv_sum = fcf = df = 0.0
    for t in range(1, d.years + 1):
        revenue = prev_revenue * (1 + d.growth)
        ebitda = revenue * margin
        capex = revenue * capex_pct
        nwc = (revenue - prev_revenue) * d.nwc_pct
        tax = max(0.0, ebitda - capex) * d.tax_rate
        fcf = ebitda - capex - nwc - tax
        df = 1 / (1 + d.discount_rate) ** t
        for k, v in [("revenue", revenue), ("ebitda", ebitda), ("capex", capex),
                     ("nwc", nwc), ("tax", tax), ("fcf", fcf), ("df", df), ("pv", fcf * df)]:
            out[f"dcf_y{t}_{k}"] = v
        pv_sum += fcf * df
        prev_revenue = revenue
    terminal = fcf * (1 + d.terminal_growth) / (d.discount_rate - d.terminal_growth)
    value = pv_sum + terminal * df
    out["dcf_pv_sum"] = pv_sum
    out["dcf_terminal_value"] = terminal
    out["dcf_pv_terminal"] = terminal * df
    out["dcf_value"] = value
    out["dcf_terminal_share"] = _safe_div(terminal * df, value)
    out["dcf_ebitda_multiple"] = _safe_div(value, out["normalised_ebitda"])
    out["dcf_vs_asking_pct"] = _safe_div(value - out["asking_value"], out["asking_value"])
    out["dcf_vs_repriced_pct"] = _safe_div(value - out["repriced_value"], out["repriced_value"])


def _financing(m: ModelInputs, out: dict) -> None:
    """Debt service coverage on an acquisition loan at each candidate price.

    Coverage uses the buyer's cash flow (normalised EBITDA less maintenance
    capex), whatever price is paid: the price does not change what the
    business earns.
    """
    loan = m.loan
    senior_share = 1 - loan.down_payment - loan.seller_note
    out["fin_capex"] = m.revenue * (m.dcf.capex_pct or 0.0)
    cfads = out["normalised_ebitda"] - out["fin_capex"]
    out["fin_cfads"] = cfads
    out["fin_senior_factor"] = sf = payment_factor(loan.senior_rate, loan.senior_years)
    out["fin_note_factor"] = nf = payment_factor(loan.note_rate, loan.note_years)
    for case in PRICE_CASES:
        price = out[f"{case}_value"]
        senior = price * senior_share
        note = price * loan.seller_note
        service = senior * sf + note * nf
        dscr = _safe_div(cfads, service)
        out[f"fin_{case}_price"] = price
        out[f"fin_{case}_equity"] = price * loan.down_payment
        out[f"fin_{case}_note"] = note
        out[f"fin_{case}_senior"] = senior
        out[f"fin_{case}_senior_payment"] = senior * sf
        out[f"fin_{case}_note_payment"] = note * nf
        out[f"fin_{case}_debt_service"] = service
        out[f"fin_{case}_dscr"] = dscr
        out[f"fin_{case}_financeable"] = "yes" if service > 0 and dscr >= loan.min_dscr else "no"
    service_factor = senior_share * sf + loan.seller_note * nf
    out["fin_service_factor"] = service_factor
    out["fin_debt_capacity"] = max(0.0, cfads / loan.min_dscr)
    out["fin_max_price"] = _safe_div(out["fin_debt_capacity"], service_factor)
    out["fin_max_seller_multiple"] = _safe_div(out["fin_max_price"], out["seller_sde"])
    out["fin_max_vs_asking_pct"] = _safe_div(out["fin_max_price"] - out["asking_value"],
                                             out["asking_value"])


def _sensitivity(m: ModelInputs, out: dict) -> None:
    """Value and coverage for each share of rejected add-backs given back, by multiple."""
    for k, share in enumerate(m.acceptance, 1):
        earnings = out["normalised_ebitda"] + share * out["rejected_total"]
        out[f"sens_{k}_ebitda"] = earnings
        for j, mult in enumerate(m.multiples, 1):
            value = earnings * mult
            service = value * out["fin_service_factor"]
            out[f"sens_{k}_{j}_value"] = value
            out[f"sens_{k}_{j}_dscr"] = out["fin_cfads"] / service if service > 0 else 0.0


def value_deal(deal: Deal) -> dict[str, float | str]:
    return evaluate(inputs_from_deal(deal)[0])
