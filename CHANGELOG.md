# Changelog

## 0.2.0 - DCF cross-check, loan coverage and sensitivity

- DCF tab: five-year free cash flow from normalised EBITDA, a terminal value, and the implied multiple compared with the asking and repriced values.
- Financing tab: bank loan plus optional seller note, debt service and DSCR at the asking, repriced and DCF prices, and the largest price the buyer's cash flow can carry at the minimum DSCR.
- Sensitivity tab: price and DSCR for each share of rejected add-backs given back against each multiple, all formulas off the row and column headers.
- Optional `dcf`, `financing` and `sensitivity` sections in deal files; the HVAC sample has a 10% seller note.
- `check --tabs` limits the LibreOffice comparison to the named tabs. The HVAC workbook now has 264 checked output cells, up from 105.

## 0.1.0 - Add-back register and repriced value

- Deal files, add-back classification, owner replacement at BLS OES wages plus an ECEC benefits load, normalised SDE and EBITDA, multiple valuation and an IRS SOI baseline, written as a live-formula workbook and checked against the Python engine in headless LibreOffice.
