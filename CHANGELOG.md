# Changelog

## 0.3.0 - Buyer memo and batch comparison

- Dashboard tab: asking, repriced, DCF and largest financeable price side by side with a bar chart, the earnings bridge, DSCRs and a financing verdict. The workbook opens on it.
- Supported value: the repriced value capped at the largest financeable price. It's computed in the engine and as dashboard formulas, along with the rejected add-back count and the verdict, and `check` compares them (269 cells on the HVAC workbook, up from 264).
- `memo` writes a two-page Word memo per deal with python-docx: bottom line, asking vs supported value, earnings bridge, each rejected add-back with the reason, and the financing verdict.
- `batch` values every deal file in a folder into a workbook and memo each, plus `summary.xlsx` with formula price columns and links to the files. Bad deal files are skipped and reported, and `--check` recalculates every workbook.
- `dashboard` prints the Dashboard tab to a one-page PDF; `docs/` has the HVAC dashboard as PDF and PNG, a memo page, the summary sheet and a worked example.
- README images and the dashboard PDF no longer carry export timestamps.

## 0.2.0 - DCF cross-check, loan coverage and sensitivity

- DCF tab: five-year free cash flow from normalised EBITDA, a terminal value, and the implied multiple compared with the asking and repriced values.
- Financing tab: bank loan plus optional seller note, debt service and DSCR at the asking, repriced and DCF prices, and the largest price the buyer's cash flow can carry at the minimum DSCR.
- Sensitivity tab: price and DSCR for each share of rejected add-backs given back against each multiple, all formulas off the row and column headers.
- Optional `dcf`, `financing` and `sensitivity` sections in deal files; the HVAC sample has a 10% seller note.
- `check --tabs` limits the LibreOffice comparison to the named tabs. The HVAC workbook now has 264 checked output cells, up from 105.

## 0.1.0 - Add-back register and repriced value

- Deal files, add-back classification, owner replacement at BLS OES wages plus an ECEC benefits load, normalised SDE and EBITDA, multiple valuation and an IRS SOI baseline, written as a live-formula workbook and checked against the Python engine in headless LibreOffice.
