# DCF, Financing and Sensitivity tabs

All the defaults below can be changed in the deal file (see [deal-file.md](deal-file.md)) or in the yellow input cells of the workbook.

## DCF

Revenue grows at 3% a year for five years and the normalised EBITDA margin is held flat. Each year takes off:

- maintenance capex, at the seller's own depreciation / revenue unless `dcf.capex_pct` is set
- working capital, 5% of each year's new revenue
- tax at 25% on EBITDA less capex, never below zero

Cash flows are discounted at 20% with a Gordon terminal value growing at 2.5%. 20% sounds high, but it's in the range people quote for small private companies. Treat the result as a second opinion: if the DCF and the repriced multiple are far apart, one of them is wrong about growth or risk.

The tab has a fixed number of year columns once built, so changing `dcf.years` means rebuilding the workbook.

## Financing

An SBA 7(a)-style loan: 10% down, ten years at 10.5% with monthly payments, and an optional seller note (6% over five years by default, off unless `financing.seller_note` is set).

The tab works out debt service at the asking price, the repriced value and the DCF value, and divides the buyer's cash flow (normalised EBITDA less maintenance capex) by it. The result is checked against a 1.25x minimum. It also solves the other way round for the largest price that cash flow can carry.

The cash flow stays the buyer's view whatever the price, because paying more doesn't make the business earn more.

Coverage uses one year of trailing cash flow. Lenders also look at the buyer's own living costs, personal guarantees and collateral, none of which are modelled, and SBA rates move with prime, so the 10.5% default needs updating by hand.

## Sensitivity

A 5 x 7 grid. Rows give back 0%, 25%, 50%, 75% or 100% of the add-backs the register rejected (0% is the buyer's view, 100% is the broker's recast). Columns are the multiples from the valuation tab. Each cell is a formula off its row and column headers.

A second grid underneath shows DSCR for each of those prices, and anything below the minimum coverage is shaded red.

![Sensitivity tab for the HVAC sample deal](sensitivity.png)

Other screenshots: [DCF](dcf.png), [Financing](financing.png), [Normalised Earnings](normalised-earnings.png), [Multiple Valuation](multiple-valuation.png).
