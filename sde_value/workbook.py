"""Build the valuation workbook with openpyxl.

Inputs are plain values; everything else is a live formula. Each input cell
gets a defined name ``i_<key>`` and each calculated cell ``o_<key>``, where
``<key>`` matches the engine's output keys, so the checker can find every
cell without knowing the layout.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

from .data import PERCENTILES
from .deal import PNL_LABELS, PNL_LINES, Deal
from .engine import BASELINE_LINES, CLASSES, PRICE_CASES, ModelInputs, inputs_from_deal
from .fetch import URLS

MONEY = '"$"#,##0;[Red]-"$"#,##0'
MONEY_C = '"$"#,##0.00;[Red]-"$"#,##0.00'
PCT = "0.0%;[Red]-0.0%"
MULT = '0.0"x"'

TITLE = Font(bold=True, size=14)
BOLD = Font(bold=True)
NOTE = Font(italic=True, color="666666", size=9)
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")   # yellow: change me
TOTAL_FILL = PatternFill("solid", fgColor="DDEBF7")
HEAD_FILL = PatternFill("solid", fgColor="1F4E78")
HEAD_FONT = Font(bold=True, color="FFFFFF")
TOP = Border(top=Side(style="thin"))

S_IN = "Inputs"
S_AB = "Add-back Register"
S_NE = "Normalised Earnings"
S_MV = "Multiple Valuation"
S_DCF = "DCF"
S_FIN = "Financing"
S_SENS = "Sensitivity"
S_IB = "Industry Baseline"
S_SRC = "Sources"


def class_key(cls: str) -> str:
    return cls.replace(" ", "_").replace("-", "_")


class Builder:
    def __init__(self) -> None:
        self.wb = Workbook()
        self.wb.remove(self.wb.active)
        self.addr: dict[str, str] = {}

    def sheet(self, title: str, widths: dict[str, float]):
        ws = self.wb.create_sheet(title)
        for col, w in widths.items():
            ws.column_dimensions[col].width = w
        return ws

    def put(self, ws, ref: str, value, name: str | None = None, fmt: str | None = None,
            fill=None, font=None):
        cell = ws[ref]
        cell.value = value
        if fmt:
            cell.number_format = fmt
        if fill:
            cell.fill = fill
        if font:
            cell.font = font
        if name:
            col = "".join(ch for ch in ref if ch.isalpha())
            row = "".join(ch for ch in ref if ch.isdigit())
            absolute = f"'{ws.title}'!${col}${row}"
            self.wb.defined_names[name] = DefinedName(name, attr_text=absolute)
            self.addr[name] = absolute
        return cell

    def ref(self, name: str) -> str:
        """Absolute sheet reference to a named cell, for use inside formulas."""
        return self.addr[name]

    def header(self, ws, row: int, labels: list[str]) -> None:
        for i, label in enumerate(labels):
            c = ws.cell(row=row, column=i + 1, value=label)
            c.fill, c.font = HEAD_FILL, HEAD_FONT
            c.alignment = Alignment(wrap_text=True, vertical="center")


def build_workbook(deal: Deal, out_path: str | Path) -> Path:
    m, src = inputs_from_deal(deal)
    b = Builder()
    _inputs_sheet(b, deal, m, src)
    _register_sheet(b, deal, m)
    _earnings_sheet(b)
    _valuation_sheet(b, m)
    _dcf_sheet(b, m)
    _financing_sheet(b, m)
    _sensitivity_sheet(b, m)
    _baseline_sheet(b, src)
    _sources_sheet(b, deal, src)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    b.wb.save(out_path)
    return out_path


def _inputs_sheet(b: Builder, deal: Deal, m: ModelInputs, src: dict) -> None:
    ws = b.sheet(S_IN, {"A": 38, "B": 18, "C": 70})
    b.put(ws, "A1", deal.name, font=TITLE)
    b.put(ws, "A2", deal.description, font=NOTE)
    b.put(ws, "A3", "Yellow cells are inputs. Everything on the other tabs is a formula.", font=NOTE)

    b.put(ws, "A5", "Seller's P&L", font=BOLD)
    b.put(ws, "B5", deal.fiscal_year_label, font=NOTE)
    b.put(ws, "A6", "Revenue")
    b.put(ws, "B6", m.revenue, name="i_revenue", fmt=MONEY, fill=INPUT_FILL)
    row = 7
    for line in PNL_LINES:
        b.put(ws, f"A{row}", PNL_LABELS[line])
        b.put(ws, f"B{row}", m.expenses[line], name=f"i_{line}", fmt=MONEY, fill=INPUT_FILL)
        row += 1
    first, last = 7, row - 1
    b.put(ws, f"A{row}", "Total expenses", font=BOLD)
    b.put(ws, f"B{row}", f"=SUM(B{first}:B{last})", name="o_total_expenses", fmt=MONEY,
          font=BOLD).border = TOP
    b.put(ws, f"A{row + 1}", "Pre-tax net income", font=BOLD)
    b.put(ws, f"B{row + 1}", f"=B6-B{row}", name="o_net_income", fmt=MONEY, font=BOLD,
          fill=TOTAL_FILL)
    b.put(ws, f"A{row + 2}", "Net margin")
    b.put(ws, f"B{row + 2}", f"=IF(B6=0,0,B{row + 1}/B6)", name="o_net_margin", fmt=PCT)

    wage, load = src["wage"], src["benefits"]
    row += 4
    b.put(ws, f"A{row}", "Owner replacement (BLS)", font=BOLD)
    rows = [
        ("i_industry_wage", f"{wage.percentile.title()} wage, {wage.occupation}, national",
         m.industry_wage, MONEY, f"OES May 2024, SOC {wage.soc}, NAICS {wage.naics} "
         f"({wage.industry})"),
        ("i_national_wage", "Same occupation, all industries, national", m.national_wage,
         MONEY, f"OES May 2024 national file, {PERCENTILES[wage.percentile]}"),
        ("i_state_wage", f"Same occupation, all industries, {wage.state}", m.state_wage,
         MONEY, "OES May 2024 state file; scales the industry wage to the state"),
        ("i_fte", "Replacement manager FTE", m.fte, "0.00",
         "1.0 = full-time manager; less for a semi-absentee owner"),
        ("i_benefits_load", "Benefits load (benefits / wages)", m.benefits_load, PCT,
         f"BLS ECEC {load.period}: ${load.benefits_per_hour:.2f} benefits per "
         f"${load.wages_per_hour:.2f} wages, {load.group}"),
    ]
    for name, label, value, fmt, note in rows:
        row += 1
        b.put(ws, f"A{row}", label)
        b.put(ws, f"B{row}", value, name=name, fmt=fmt, fill=INPUT_FILL)
        b.put(ws, f"C{row}", note, font=NOTE)

    row += 2
    b.put(ws, f"A{row}", "Pricing", font=BOLD)
    row += 1
    b.put(ws, f"A{row}", "Asking multiple (broker, on seller's SDE)")
    b.put(ws, f"B{row}", m.asking_multiple, name="i_asking_multiple", fmt=MULT, fill=INPUT_FILL)

    row += 2
    b.put(ws, f"A{row}", f"Industry ratios (IRS SOI, {src['soi_title']})", font=BOLD)
    b.put(ws, f"C{row}", "Share of business receipts, all active corporations, tax year 2022",
          font=NOTE)
    for item in BASELINE_LINES + ["net_income", "interest", "depreciation", "amortization"]:
        if f"i_soi_{item}" in b.addr:
            continue
        row += 1
        label = PNL_LABELS.get(item, "Net income (less deficit)")
        b.put(ws, f"A{row}", label)
        b.put(ws, f"B{row}", m.soi.get(item, 0.0), name=f"i_soi_{item}", fmt="0.00%",
              fill=INPUT_FILL)


def _register_sheet(b: Builder, deal: Deal, m: ModelInputs) -> None:
    ws = b.sheet(S_AB, {"A": 4, "B": 40, "C": 24, "D": 18, "E": 8, "F": 11, "G": 11,
                        "H": 42, "I": 20, "J": 12, "K": 9, "L": 13, "M": 13, "N": 60})
    b.put(ws, "A1", "Add-back register", font=TITLE)
    b.put(ws, "A2", "Set Accept? to 1 or 0 to keep or reject an add-back; every total and "
          "value downstream follows.", font=NOTE)
    b.header(ws, 4, ["#", "Item", "Comes out of", "Seller's label", "Years seen (of 3)",
                     "Continues after sale?", "Documented?", "Support", "Classification",
                     "Recommended", "Accept?", "Claimed", "Accepted", "Note"])
    ws.row_dimensions[4].height = 44
    toggle = DataValidation(type="list", formula1='"1,0"', allow_blank=False)
    yesno = DataValidation(type="list", formula1='"yes,no"', allow_blank=False)
    ws.add_data_validation(toggle)
    ws.add_data_validation(yesno)
    start = 5
    for i, (a, src) in enumerate(zip(m.addbacks, deal.addbacks), 1):
        r = start + i - 1
        b.put(ws, f"A{r}", i)
        b.put(ws, f"B{r}", a.item)
        b.put(ws, f"C{r}", PNL_LABELS[a.line])
        b.put(ws, f"D{r}", a.label, name=f"i_ab{i}_label", fill=INPUT_FILL)
        b.put(ws, f"E{r}", a.years_seen, name=f"i_ab{i}_years", fill=INPUT_FILL)
        b.put(ws, f"F{r}", "yes" if a.continues else "no", name=f"i_ab{i}_continues",
              fill=INPUT_FILL)
        b.put(ws, f"G{r}", "yes" if a.documented else "no", name=f"i_ab{i}_documented",
              fill=INPUT_FILL)
        b.put(ws, f"H{r}", src.support)
        b.put(ws, f"I{r}",
              f'=IF(OR(D{r}="owner compensation",D{r}="non-cash",D{r}="financing"),D{r},'
              f'IF(OR(F{r}="yes",AND(D{r}="one-time",E{r}>=2)),"recurring-disguised",D{r}))',
              name=f"o_ab{i}_class")
        b.put(ws, f"J{r}",
              f'=IF(I{r}="recurring-disguised",0,'
              f'IF(AND(OR(I{r}="discretionary",I{r}="one-time"),G{r}="no"),0,1))',
              name=f"o_ab{i}_recommend")
        b.put(ws, f"K{r}", 1 if a.accept else 0, name=f"i_ab{i}_accept", fill=INPUT_FILL)
        b.put(ws, f"L{r}", a.amount, name=f"i_ab{i}_amount", fmt=MONEY, fill=INPUT_FILL)
        b.put(ws, f"M{r}", f"=IF(K{r}=1,L{r},0)", name=f"o_ab{i}_accepted", fmt=MONEY)
        b.put(ws, f"N{r}", src.note, font=NOTE)
        toggle.add(f"K{r}")
        yesno.add(f"F{r}:G{r}")
    end = max(start, start + len(m.addbacks) - 1)
    tot = end + 1
    b.put(ws, f"B{tot}", "Total", font=BOLD)
    b.put(ws, f"L{tot}", f"=SUM(L{start}:L{end})", fmt=MONEY, font=BOLD).border = TOP
    b.put(ws, f"M{tot}", f"=SUM(M{start}:M{end})", fmt=MONEY, font=BOLD).border = TOP
    # Grey out rejected rows so the toggles are visible at a glance.
    ws.conditional_formatting.add(
        f"A{start}:N{end}",
        FormulaRule(formula=[f"$K{start}=0"], fill=PatternFill("solid", fgColor="F2DCDB"),
                    font=Font(color="9C0006")))
    ws.freeze_panes = "C5"
    b.register_rows = (start, end)


def _earnings_sheet(b: Builder) -> None:
    ws = b.sheet(S_NE, {"A": 46, "B": 18, "C": 18, "D": 50})
    start, end = b.register_rows
    reg = f"'{S_AB}'!"
    b.put(ws, "A1", "Normalised earnings", font=TITLE)
    b.header(ws, 3, ["", "Seller's recast", "Buyer's view", "How"])
    b.put(ws, "A4", "Pre-tax net income")
    b.put(ws, "B4", f"={b.ref('o_net_income')}", fmt=MONEY)
    b.put(ws, "C4", "=B4", fmt=MONEY)
    b.put(ws, "D4", "From the seller's P&L on Inputs", font=NOTE)
    row = 5
    for cls in CLASSES:
        k = class_key(cls)
        b.put(ws, f"A{row}", f"Add back: {cls}")
        b.put(ws, f"B{row}", f'=SUMIFS({reg}$L${start}:$L${end},{reg}$I${start}:$I${end},"{cls}")',
              name=f"o_claimed_{k}", fmt=MONEY)
        b.put(ws, f"C{row}", f'=SUMIFS({reg}$M${start}:$M${end},{reg}$I${start}:$I${end},"{cls}")',
              name=f"o_accepted_{k}", fmt=MONEY)
        row += 1
    first, last = 5, row - 1
    b.put(ws, f"A{row}", "Total add-backs", font=BOLD)
    b.put(ws, f"B{row}", f"=SUM(B{first}:B{last})", name="o_claimed_total", fmt=MONEY,
          font=BOLD).border = TOP
    b.put(ws, f"C{row}", f"=SUM(C{first}:C{last})", name="o_accepted_total", fmt=MONEY,
          font=BOLD).border = TOP
    tot = row
    row += 1
    b.put(ws, f"A{row}", "Add-backs rejected")
    b.put(ws, f"C{row}", f"=B{tot}-C{tot}", name="o_rejected_total", fmt=MONEY)
    row += 1
    b.put(ws, f"A{row}", "Seller's discretionary earnings (SDE)", font=BOLD)
    b.put(ws, f"B{row}", f"=B4+B{tot}", name="o_seller_sde", fmt=MONEY, font=BOLD,
          fill=TOTAL_FILL)
    b.put(ws, f"C{row}", f"=C4+C{tot}", name="o_normalised_sde", fmt=MONEY, font=BOLD,
          fill=TOTAL_FILL)
    b.put(ws, f"D{row}", "Seller: every claimed add-back. Buyer: only accepted ones.", font=NOTE)
    sde = row

    row += 2
    b.put(ws, f"A{row}", "Owner replacement at market pay", font=BOLD)
    steps = [
        ("o_state_factor", "State wage factor",
         f"=IF({b.ref('i_national_wage')}=0,0,{b.ref('i_state_wage')}/{b.ref('i_national_wage')})",
         "0.0000", "State cross-industry wage / national"),
        ("o_market_wage", "Market wage for the role",
         f"={b.ref('i_industry_wage')}*C{{prev}}", MONEY_C, "Industry wage x state factor"),
        ("o_replacement_wage", "Replacement wage", f"=C{{prev}}*{b.ref('i_fte')}", MONEY_C,
         "x FTE"),
        ("o_replacement_benefits", "Employer benefits and payroll taxes",
         f"=C{{prev}}*{b.ref('i_benefits_load')}", MONEY_C, "x ECEC benefits load"),
    ]
    for name, label, formula, fmt, note in steps:
        row += 1
        b.put(ws, f"A{row}", label)
        b.put(ws, f"C{row}", formula.replace("{prev}", str(row - 1)), name=name, fmt=fmt)
        b.put(ws, f"D{row}", note, font=NOTE)
    row += 1
    b.put(ws, f"A{row}", "Owner replacement cost", font=BOLD)
    b.put(ws, f"C{row}", f"=C{row - 2}+C{row - 1}", name="o_replacement_cost", fmt=MONEY_C,
          font=BOLD).border = TOP
    rc = row
    row += 2
    b.put(ws, f"A{row}", "Normalised EBITDA (SDE less market-rate manager)", font=BOLD)
    b.put(ws, f"C{row}", f"=C{sde}-C{rc}", name="o_normalised_ebitda", fmt=MONEY_C, font=BOLD,
          fill=TOTAL_FILL)
    ebitda = row
    row += 2
    rev = b.ref("i_revenue")
    for name, label, col, src_row in [
        ("o_seller_sde_margin", "Seller's SDE margin", "B", sde),
        ("o_normalised_sde_margin", "Normalised SDE margin", "C", sde),
        ("o_normalised_ebitda_margin", "Normalised EBITDA margin", "C", ebitda),
    ]:
        b.put(ws, f"A{row}", label)
        b.put(ws, f"{col}{row}", f"=IF({rev}=0,0,{col}{src_row}/{rev})", name=name, fmt=PCT)
        row += 1


def _valuation_sheet(b: Builder, m: ModelInputs) -> None:
    ws = b.sheet(S_MV, {"A": 44, "B": 18, "C": 20, "D": 22})
    b.put(ws, "A1", "Multiple valuation", font=TITLE)
    b.put(ws, "A2", "The broker's multiple applied to the seller's SDE, then the same multiple "
          "applied to earnings after tested add-backs and a paid manager.", font=NOTE)
    mult = b.ref("i_asking_multiple")
    rows = [
        ("Asking multiple", f"={mult}", None, MULT),
        ("Asking value (seller's SDE x multiple)", f"={b.ref('o_seller_sde')}*{mult}",
         "o_asking_value", MONEY_C),
        ("Repriced value (normalised EBITDA x multiple)",
         f"={b.ref('o_normalised_ebitda')}*{mult}", "o_repriced_value", MONEY_C),
        ("Difference", "=B5-B6", "o_value_cut", MONEY_C),
        ("Difference, % of asking", "=IF(B5=0,0,B7/B5)", "o_value_cut_pct", PCT),
        ("  of which: rejected add-backs", f"={b.ref('o_rejected_total')}*{mult}",
         "o_value_from_rejected", MONEY_C),
        ("  of which: paying a manager", f"={b.ref('o_replacement_cost')}*{mult}",
         "o_value_from_replacement", MONEY_C),
    ]
    for r, (label, formula, name, fmt) in enumerate(rows, 4):
        b.put(ws, f"A{r}", label, font=BOLD if name in ("o_asking_value", "o_repriced_value") else None)
        b.put(ws, f"B{r}", formula, name=name, fmt=fmt,
              fill=TOTAL_FILL if name == "o_repriced_value" else None)

    top = 13
    b.header(ws, top, ["Multiple", "On seller's SDE", "On normalised SDE",
                       "On normalised EBITDA"])
    for j, mlt in enumerate(m.multiples, 1):
        r = top + j
        b.put(ws, f"A{r}", mlt, name=f"i_mult{j}", fmt=MULT, fill=INPUT_FILL)
        b.put(ws, f"B{r}", f"={b.ref('o_seller_sde')}*A{r}", name=f"o_mult{j}_seller_sde",
              fmt=MONEY)
        b.put(ws, f"C{r}", f"={b.ref('o_normalised_sde')}*A{r}",
              name=f"o_mult{j}_normalised_sde", fmt=MONEY)
        b.put(ws, f"D{r}", f"={b.ref('o_normalised_ebitda')}*A{r}",
              name=f"o_mult{j}_normalised_ebitda", fmt=MONEY)
    last = top + len(m.multiples)
    ws.conditional_formatting.add(
        f"A{top + 1}:D{last}",
        FormulaRule(formula=[f"$A{top + 1}={mult}"], font=Font(bold=True),
                    fill=PatternFill("solid", fgColor="E2EFDA")))


def _assumptions(b: Builder, ws, row: int, rows: list) -> int:
    """Write labelled input cells in A/B with a note in C; return the last row used."""
    for name, label, value, fmt, note in rows:
        b.put(ws, f"A{row}", label)
        b.put(ws, f"B{row}", value, name=name, fmt=fmt, fill=INPUT_FILL)
        b.put(ws, f"C{row}", note, font=NOTE)
        row += 1
    return row - 1


def _dcf_sheet(b: Builder, m: ModelInputs) -> None:
    d = m.dcf
    years = d.years
    last_col = get_column_letter(2 + years)
    ws = b.sheet(S_DCF, {"A": 40, "B": 16, "C": 16, **{get_column_letter(3 + t): 14
                                                         for t in range(years)}})
    b.put(ws, "A1", "DCF cross-check", font=TITLE)
    b.put(ws, "A2", "Free cash flow from normalised EBITDA, held at today's margin, "
          "discounted at a buyer's required return. A second opinion on the multiple, not "
          "a replacement for it.", font=NOTE)
    end = _assumptions(b, ws, 4, [
        ("i_dcf_growth", "Revenue growth per year", d.growth, PCT, ""),
        ("i_dcf_capex_pct", "Maintenance capex, % of revenue", d.capex_pct, PCT,
         "Defaults to the seller's depreciation / revenue"),
        ("i_dcf_nwc_pct", "Working capital, % of new revenue", d.nwc_pct, PCT,
         "Receivables and stock tied up as revenue grows"),
        ("i_dcf_tax_rate", "Tax rate on EBITDA less capex", d.tax_rate, PCT,
         "Owner-level rate for a pass-through entity"),
        ("i_dcf_discount_rate", "Discount rate", d.discount_rate, PCT,
         "Required return on a small private company, well above public-market rates"),
        ("i_dcf_terminal_growth", "Growth after the last year", d.terminal_growth, PCT, ""),
    ])
    margin_row = end + 1
    b.put(ws, f"A{margin_row}", "Normalised EBITDA margin (held flat)")
    b.put(ws, f"B{margin_row}", f"={b.ref('o_normalised_ebitda_margin')}", fmt=PCT)
    b.put(ws, f"C{margin_row}", "From Normalised Earnings", font=NOTE)
    margin = f"$B${margin_row}"
    g, capex, nwc, tax, r, tg = (b.ref(f"i_dcf_{k}") for k in (
        "growth", "capex_pct", "nwc_pct", "tax_rate", "discount_rate", "terminal_growth"))

    top = margin_row + 2
    b.header(ws, top, ["Year"] + ["Today"] + [f"Year {t}" for t in range(1, years + 1)])
    yr = top + 1
    b.put(ws, f"A{yr}", "Years from today", font=NOTE)
    labels = [("revenue", "Revenue"), ("ebitda", "Normalised EBITDA"),
              ("capex", "Less maintenance capex"), ("nwc", "Less working capital build"),
              ("tax", "Less tax"), ("fcf", "Free cash flow"), ("df", "Discount factor"),
              ("pv", "Present value")]
    rows = {k: yr + 1 + i for i, (k, _) in enumerate(labels)}
    for k, label in labels:
        b.put(ws, f"A{rows[k]}", label, font=BOLD if k == "fcf" else None)
    b.put(ws, f"B{yr}", 0)
    b.put(ws, f"B{rows['revenue']}", f"={b.ref('i_revenue')}", fmt=MONEY)
    b.put(ws, f"B{rows['ebitda']}", f"={b.ref('o_normalised_ebitda')}", fmt=MONEY)
    for t in range(1, years + 1):
        c, p = get_column_letter(2 + t), get_column_letter(1 + t)
        R = {k: f"{c}{v}" for k, v in rows.items()}
        b.put(ws, f"{c}{yr}", t)
        formulas = {
            "revenue": (f"={p}{rows['revenue']}*(1+{g})", MONEY),
            "ebitda": (f"={R['revenue']}*{margin}", MONEY),
            "capex": (f"={R['revenue']}*{capex}", MONEY),
            "nwc": (f"=({R['revenue']}-{p}{rows['revenue']})*{nwc}", MONEY),
            "tax": (f"=MAX(0,{R['ebitda']}-{R['capex']})*{tax}", MONEY),
            "fcf": (f"={R['ebitda']}-{R['capex']}-{R['nwc']}-{R['tax']}", MONEY),
            "df": (f"=1/(1+{r})^{c}{yr}", "0.0000"),
            "pv": (f"={R['fcf']}*{R['df']}", MONEY),
        }
        for k, (formula, fmt) in formulas.items():
            b.put(ws, R[k], formula, name=f"o_dcf_y{t}_{k}", fmt=fmt,
                  font=BOLD if k == "fcf" else None)
        ws[R["fcf"]].border = TOP

    row = rows["pv"] + 2
    pv_row = rows["pv"]
    summary = [
        ("o_dcf_pv_sum", "Present value of the forecast years",
         f"=SUM(C{pv_row}:{last_col}{pv_row})", MONEY),
        ("o_dcf_terminal_value", "Terminal value at the end of the forecast",
         f"={last_col}{rows['fcf']}*(1+{tg})/({r}-{tg})", MONEY),
        ("o_dcf_pv_terminal", "Present value of the terminal value",
         f"=B{{1}}*{last_col}{rows['df']}", MONEY),
        ("o_dcf_value", "DCF value of the business", "=B{0}+B{2}", MONEY),
        ("o_dcf_terminal_share", "Share of value from the terminal value",
         "=IF(B{3}=0,0,B{2}/B{3})", PCT),
        ("o_dcf_ebitda_multiple", "Implied multiple of normalised EBITDA",
         f"=IF({b.ref('o_normalised_ebitda')}=0,0,B{{3}}/{b.ref('o_normalised_ebitda')})", MULT),
        ("o_dcf_vs_asking_pct", "DCF value vs asking value",
         f"=IF({b.ref('o_asking_value')}=0,0,B{{3}}/{b.ref('o_asking_value')}-1)", PCT),
        ("o_dcf_vs_repriced_pct", "DCF value vs repriced value",
         f"=IF({b.ref('o_repriced_value')}=0,0,B{{3}}/{b.ref('o_repriced_value')}-1)", PCT),
    ]
    refs = [row + i for i in range(len(summary))]
    for i, (name, label, formula, fmt) in enumerate(summary):
        bold = name == "o_dcf_value"
        b.put(ws, f"A{row + i}", label, font=BOLD if bold else None)
        b.put(ws, f"B{row + i}", formula.format(*refs), name=name, fmt=fmt,
              font=BOLD if bold else None, fill=TOTAL_FILL if bold else None)
    b.put(ws, f"C{refs[1]}", "Last year's cash flow grown once, over (discount rate - growth)",
          font=NOTE)
    ws.freeze_panes = "B1"


def _financing_sheet(b: Builder, m: ModelInputs) -> None:
    loan = m.loan
    ws = b.sheet(S_FIN, {"A": 42, "B": 18, "C": 18, "D": 18, "E": 44})
    b.put(ws, "A1", "Acquisition financing", font=TITLE)
    b.put(ws, "A2", "Can the price be borrowed? Debt service coverage (DSCR) is the "
          "buyer's cash flow over the year's loan payments; lenders want it at or above "
          "the minimum.", font=NOTE)
    end = _assumptions(b, ws, 4, [
        ("i_fin_down_payment", "Buyer's equity, % of price", loan.down_payment, PCT,
         "SBA 7(a) acquisitions need at least 10%"),
        ("i_fin_seller_note", "Seller note, % of price", loan.seller_note, PCT,
         "Part of the price the seller lends back"),
        ("i_fin_senior_rate", "Bank loan rate", loan.senior_rate, PCT,
         "Near the SBA 7(a) cap of prime plus three points"),
        ("i_fin_senior_years", "Bank loan term (years)", loan.senior_years, "0",
         "Ten years is the usual SBA term for a business purchase"),
        ("i_fin_note_rate", "Seller note rate", loan.note_rate, PCT, ""),
        ("i_fin_note_years", "Seller note term (years)", loan.note_years, "0", ""),
        ("i_fin_min_dscr", "Minimum DSCR", loan.min_dscr, '0.00"x"',
         "Typical lender floor for small-business loans"),
    ])
    rate = lambda k: b.ref(f"i_fin_{k}")  # noqa: E731
    row = end + 2
    b.put(ws, f"A{row}", "Cash available for debt service", font=BOLD)
    b.put(ws, f"A{row + 1}", "Normalised EBITDA")
    b.put(ws, f"B{row + 1}", f"={b.ref('o_normalised_ebitda')}", fmt=MONEY)
    b.put(ws, f"A{row + 2}", "Less maintenance capex")
    b.put(ws, f"B{row + 2}", f"={b.ref('i_revenue')}*{b.ref('i_dcf_capex_pct')}",
          name="o_fin_capex", fmt=MONEY)
    b.put(ws, f"C{row + 2}", "Capex rate from the DCF tab", font=NOTE)
    b.put(ws, f"A{row + 3}", "Cash flow for debt service", font=BOLD)
    b.put(ws, f"B{row + 3}", f"=B{row + 1}-B{row + 2}", name="o_fin_cfads", fmt=MONEY,
          font=BOLD, fill=TOTAL_FILL).border = TOP
    b.put(ws, f"C{row + 3}", "The buyer's view, whatever price is paid", font=NOTE)
    cfads = b.ref("o_fin_cfads")
    row += 5
    b.put(ws, f"A{row}", "Annual payment per $1 borrowed (bank)")
    b.put(ws, f"B{row}", f"=PMT({rate('senior_rate')}/12,{rate('senior_years')}*12,-1)*12",
          name="o_fin_senior_factor", fmt="0.0000")
    b.put(ws, f"C{row}", "Monthly payments, fully amortising", font=NOTE)
    b.put(ws, f"A{row + 1}", "Annual payment per $1 borrowed (seller note)")
    b.put(ws, f"B{row + 1}", f"=PMT({rate('note_rate')}/12,{rate('note_years')}*12,-1)*12",
          name="o_fin_note_factor", fmt="0.0000")
    sf, nf = b.ref("o_fin_senior_factor"), b.ref("o_fin_note_factor")

    top = row + 3
    b.header(ws, top, ["Price tested"] + list(PRICE_CASES.values()))
    labels = [("price", "Purchase price"), ("equity", "Buyer's equity"),
              ("note", "Seller note"), ("senior", "Bank loan"),
              ("senior_payment", "Bank payments per year"),
              ("note_payment", "Seller note payments per year"),
              ("debt_service", "Total debt service"), ("dscr", "DSCR"),
              ("financeable", "Meets the minimum DSCR?")]
    rows = {k: top + 1 + i for i, (k, _) in enumerate(labels)}
    for k, label in labels:
        b.put(ws, f"A{rows[k]}", label, font=BOLD if k in ("dscr", "financeable") else None)
    for col, case in zip("BCD", PRICE_CASES):
        R = {k: f"{col}{v}" for k, v in rows.items()}
        formulas = {
            "price": (f"={b.ref(f'o_{case}_value')}", MONEY),
            "equity": (f"={R['price']}*{rate('down_payment')}", MONEY),
            "note": (f"={R['price']}*{rate('seller_note')}", MONEY),
            "senior": (f"={R['price']}-{R['equity']}-{R['note']}", MONEY),
            "senior_payment": (f"={R['senior']}*{sf}", MONEY),
            "note_payment": (f"={R['note']}*{nf}", MONEY),
            "debt_service": (f"={R['senior_payment']}+{R['note_payment']}", MONEY),
            "dscr": (f"=IF({R['debt_service']}=0,0,{cfads}/{R['debt_service']})", '0.00"x"'),
            "financeable": (f'=IF(AND({R["debt_service"]}>0,{R["dscr"]}>={rate("min_dscr")}),'
                            f'"yes","no")', None),
        }
        for k, (formula, fmt) in formulas.items():
            b.put(ws, R[k], formula, name=f"o_fin_{case}_{k}", fmt=fmt,
                  font=BOLD if k in ("dscr", "financeable") else None)
        ws[R["debt_service"]].border = TOP
    ok_row = rows["financeable"]
    ws.conditional_formatting.add(
        f"B{ok_row}:D{ok_row}", FormulaRule(formula=[f'B{ok_row}="no"'],
                                            fill=PatternFill("solid", fgColor="F8CBAD")))
    ws.conditional_formatting.add(
        f"B{ok_row}:D{ok_row}", FormulaRule(formula=[f'B{ok_row}="yes"'],
                                            fill=PatternFill("solid", fgColor="E2EFDA")))

    row = ok_row + 2
    b.put(ws, f"A{row}", "Largest price the cash flow supports", font=BOLD)
    steps = [
        ("o_fin_service_factor", "Debt service per $1 of price",
         f"=(1-{rate('down_payment')}-{rate('seller_note')})*{sf}+{rate('seller_note')}*{nf}",
         "0.0000", "Bank share x bank payment + note share x note payment"),
        ("o_fin_debt_capacity", "Debt service the cash flow carries",
         f"=MAX(0,{cfads}/{rate('min_dscr')})", MONEY, "Cash flow / minimum DSCR"),
        ("o_fin_max_price", "Largest financeable price", "=IF(B{0}=0,0,B{1}/B{0})", MONEY,
         ""),
        ("o_fin_max_seller_multiple", "As a multiple of the seller's SDE",
         f"=IF({b.ref('o_seller_sde')}=0,0,B{{2}}/{b.ref('o_seller_sde')})", MULT,
         "Compare with the broker's asking multiple"),
        ("o_fin_max_vs_asking_pct", "Largest financeable price vs asking value",
         f"=IF({b.ref('o_asking_value')}=0,0,B{{2}}/{b.ref('o_asking_value')}-1)", PCT, ""),
    ]
    refs = [row + 1 + i for i in range(len(steps))]
    for i, (name, label, formula, fmt, note) in enumerate(steps):
        r = refs[i]
        bold = name == "o_fin_max_price"
        b.put(ws, f"A{r}", label, font=BOLD if bold else None)
        b.put(ws, f"B{r}", formula.format(*refs), name=name, fmt=fmt,
              font=BOLD if bold else None, fill=TOTAL_FILL if bold else None)
        b.put(ws, f"C{r}", note, font=NOTE)


def _sensitivity_sheet(b: Builder, m: ModelInputs) -> None:
    n_mult = len(m.multiples)
    last_col = get_column_letter(2 + n_mult)
    ws = b.sheet(S_SENS, {"A": 26, "B": 18, **{get_column_letter(3 + j): 13
                                               for j in range(n_mult)}})
    b.put(ws, "A1", "Sensitivity: add-backs given back x multiple", font=TITLE)
    b.put(ws, "A2", "Rows give back a share of the add-backs the register rejects (0% is the "
          "buyer's view, 100% the broker's recast); columns are the multiples on the "
          "valuation tab.", font=NOTE)
    rejected, ebitda = b.ref("o_rejected_total"), b.ref("o_normalised_ebitda")
    max_price, min_dscr = b.ref("o_fin_max_price"), b.ref("i_fin_min_dscr")

    def grid(top: int, title: str, cell_label: str, kind: str) -> tuple[int, int]:
        b.put(ws, f"A{top - 1}", title, font=BOLD)
        b.header(ws, top, ["Add-backs given back", "EBITDA used"] + [""] * n_mult)
        for j in range(1, n_mult + 1):
            c = ws.cell(row=top, column=2 + j, value=f"={b.ref(f'i_mult{j}')}")
            c.number_format = MULT
        first = top + 1
        for k, share in enumerate(m.acceptance, 1):
            r = top + k
            if kind == "value":
                b.put(ws, f"A{r}", share, name=f"i_sens_acc{k}", fmt="0%", fill=INPUT_FILL)
                b.put(ws, f"B{r}", f"={ebitda}+A{r}*{rejected}", name=f"o_sens_{k}_ebitda",
                      fmt=MONEY)
            else:
                b.put(ws, f"A{r}", f"={b.ref(f'i_sens_acc{k}')}", fmt="0%")
                b.put(ws, f"B{r}", f"={b.ref(f'o_sens_{k}_ebitda')}", fmt=MONEY)
            for j in range(1, n_mult + 1):
                col = get_column_letter(2 + j)
                if kind == "value":
                    formula, fmt = f"=$B{r}*{col}${top}", MONEY
                else:
                    value = b.ref(f"o_sens_{k}_{j}_value")
                    formula = (f"=IF({value}*{b.ref('o_fin_service_factor')}>0,"
                               f"{b.ref('o_fin_cfads')}/({value}*{b.ref('o_fin_service_factor')}),0)")
                    fmt = '0.00"x"'
                b.put(ws, f"{col}{r}", formula, name=f"o_sens_{k}_{j}_{kind}", fmt=fmt)
        b.put(ws, f"C{top + len(m.acceptance) + 1}", cell_label, font=NOTE)
        return first, top + len(m.acceptance)

    first, last = grid(5, "Price", "Red: more than the cash flow can finance at the "
                       "minimum DSCR. Bold: the asking multiple.", "value")
    rng = f"C{first}:{last_col}{last}"
    ws.conditional_formatting.add(rng, FormulaRule(
        formula=[f"C{first}>{max_price}"], fill=PatternFill("solid", fgColor="F8CBAD")))
    ws.conditional_formatting.add(rng, FormulaRule(
        formula=[f"C$5={b.ref('i_asking_multiple')}"], font=Font(bold=True)))

    top = last + 4
    first, last = grid(top, "DSCR if the business earns only the buyer's normalised EBITDA",
                       "Red: below the minimum DSCR on the Financing tab.", "dscr")
    rng = f"C{first}:{last_col}{last}"
    ws.conditional_formatting.add(rng, FormulaRule(
        formula=[f"C{first}<{min_dscr}"], fill=PatternFill("solid", fgColor="F8CBAD")))
    ws.conditional_formatting.add(rng, FormulaRule(
        formula=[f"C{first}>={min_dscr}"], fill=PatternFill("solid", fgColor="E2EFDA")))
    ws.freeze_panes = "C1"


def _baseline_sheet(b: Builder, src: dict) -> None:
    ws = b.sheet(S_IB, {"A": 36, "B": 14, "C": 14, "D": 14, "E": 50})
    b.put(ws, "A1", "Industry baseline", font=TITLE)
    b.put(ws, "A2", f"Seller's P&L as a share of revenue against IRS SOI ratios for "
          f"{src['soi_title']}.", font=NOTE)
    b.header(ws, 4, ["Line", "This deal", "Industry", "Gap", "Reading"])
    rev = b.ref("i_revenue")
    r = 5
    for line in BASELINE_LINES:
        b.put(ws, f"A{r}", PNL_LABELS[line])
        b.put(ws, f"B{r}", f"=IF({rev}=0,0,{b.ref('i_' + line)}/{rev})",
              name=f"o_base_{line}_deal", fmt=PCT)
        b.put(ws, f"C{r}", f"={b.ref('i_soi_' + line)}", fmt=PCT)
        b.put(ws, f"D{r}", f"=B{r}-C{r}", name=f"o_base_{line}_gap", fmt=PCT)
        r += 1
    b.put(ws, f"A{r}", "Pre-tax net margin")
    b.put(ws, f"B{r}", f"={b.ref('o_net_margin')}", fmt=PCT)
    b.put(ws, f"C{r}", f"={b.ref('i_soi_net_income')}", fmt=PCT)
    b.put(ws, f"D{r}", f"=B{r}-C{r}", name="o_base_net_margin_gap", fmt=PCT)
    r += 2
    b.put(ws, f"A{r}", "Normalised EBITDA margin", font=BOLD)
    b.put(ws, f"B{r}", f"={b.ref('o_normalised_ebitda_margin')}", fmt=PCT)
    b.put(ws, f"C{r}", "=" + "+".join(b.ref(f"i_soi_{k}") for k in
                                       ("net_income", "interest", "depreciation", "amortization")),
          name="o_base_industry_ebitda_margin", fmt=PCT)
    b.put(ws, f"D{r}", f"=B{r}-C{r}", name="o_base_ebitda_margin_gap", fmt=PCT)
    b.put(ws, f"E{r}", "Industry: net income + interest + D&A, officers already paid",
          font=NOTE)
    b.put(ws, f"E{r + 1}", "A large positive gap means the recast earnings beat what "
          "corporations in this industry actually report: ask why.", font=NOTE)
    ws.conditional_formatting.add(
        f"D{r}", FormulaRule(formula=[f"D{r}>0.05"], fill=PatternFill("solid", fgColor="F8CBAD")))


def _sources_sheet(b: Builder, deal: Deal, src: dict) -> None:
    ws = b.sheet(S_SRC, {"A": 30, "B": 110})
    b.put(ws, "A1", "Sources and method", font=TITLE)
    wage, load = src["wage"], src["benefits"]
    lines = [
        ("Deal file", str(deal.path) if deal.path else ""),
        ("Replacement role", f"SOC {wage.soc} {wage.occupation}, {wage.percentile} annual wage"),
        ("Industry wage", f"OES May 2024, NAICS {wage.naics} {wage.industry}: ${wage.industry_wage:,.0f}"),
        ("State adjustment", f"{wage.state} ${wage.state_wage:,.0f} / national ${wage.national_wage:,.0f} "
         "(OES does not publish industry by state)"),
        ("Benefits load", f"BLS ECEC {load.period}, {load.group}"),
        ("Industry ratios", f"IRS SOI Table 5.1, tax year 2022, {src['soi_title']}"),
        ("OES national", URLS["oes_national"]),
        ("OES state", URLS["oes_state"]),
        ("OES industry", URLS["oes_industry"]),
        ("ECEC", URLS["ecec_data"]),
        ("IRS SOI", URLS["soi_minor"]),
        ("Classification rule", "Owner pay, non-cash and financing items keep their label. A "
         "'one-time' item seen in 2+ of 3 years, or anything that continues after the sale, is "
         "recurring-disguised. Undocumented discretionary or one-time items are not recommended."),
        ("Not advice", "A first-pass screening model, not tax structuring, legal advice or a "
         "formal appraisal."),
    ]
    for r, (k, v) in enumerate(lines, 3):
        b.put(ws, f"A{r}", k, font=BOLD)
        b.put(ws, f"B{r}", v).alignment = Alignment(wrap_text=True)
    for r, note in enumerate(deal.notes, len(lines) + 4):
        b.put(ws, f"B{r}", note)
