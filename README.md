# sde-value

On the three sample deals in this repo, the price the business's cash flow can actually support comes out 62.1% below the broker's asking price on average. The deals are made up but built from IRS industry ratios, and the cut comes from two things brokers tend to skip. They add back "one-time" costs that show up every year, and they add back the owner's whole salary without paying anyone to replace them.

sde-value takes a deal file (the seller's P&L plus the broker's list of add-backs) and builds an Excel workbook where every add-back is its own row with a 1/0 toggle. The owner's job is priced at what it would cost to hire a manager.

## The HVAC sample

`build` followed by `check` on `deals/hvac_service.yaml` prints:

```
Wrote out/hvac_service.xlsx
  Lone Star Comfort Air (sample)
  Seller's SDE            $386,800   (add-backs claimed $291,800)
  Normalised SDE          $294,100   (rejected $92,700)
  Owner replacement       $138,045
  Normalised EBITDA       $156,055
  Asking value          $1,547,200   at 4.0x
  Repriced value          $624,220   (59.7% below asking)
  DCF value               $486,172   (3.1x normalised EBITDA)
  Largest financeable     $593,621   (DSCR at asking 0.48x, needs 1.25x)
  Supported value         $593,621   (capped at the largest financeable price; neither price can be financed at these terms)

OK: 269 output cells compared after LibreOffice recalculation, 0 mismatches, 0 missing
```

The workbook opens on a dashboard ([PDF](docs/dashboard.pdf)):

![Dashboard for the HVAC sample deal](docs/dashboard.png)

The part I didn't expect was the last line of numbers. None of the three asking prices can be financed at the default loan terms, and even the repriced values fall a little short, so the loan sets the price every time, not the multiple.

Results for all three deals are in [docs/sample-deals.md](docs/sample-deals.md), and the HVAC deal is followed from file to memo in [docs/worked-example.md](docs/worked-example.md).

## How it decides

Each add-back says which P&L line it comes from, what the seller calls it, how many of the last three years it appeared in, whether the cost carries on under a new owner, and whether there's paperwork. The rule had to fit in one Excel formula, so it's short. A "one-time" item seen in two or more years is rejected. So is anything that continues after the sale, and anything discretionary or one-time with no documents. The HVAC sample has $31,000 of "one-time" compressor warranty callbacks that turn up in all three years. You can override any row in the deal file or flip the toggle in Excel.

The manager's cost comes from BLS data. OES doesn't publish wages by industry and state together, so I take the national wage for the role in that industry, scale it by how the state compares to the country across all industries, and add benefits from ECEC. Normalised EBITDA is net income plus the accepted add-backs minus that manager. From there the workbook prices the business three ways: the broker's multiple, a five-year DCF and an SBA-style loan.

The checking is what I'm happiest with. Inputs go into the workbook as values and everything else as named formulas, and a Python engine computes the same names. `check` recalculates the file in headless LibreOffice, reads the inputs back out, runs the engine on them and compares every output. Because it reads the workbook and not the deal file, it still works after you flip toggles. One test breaks a formula on purpose to make sure it notices.

The deal file format is in [docs/deal-file.md](docs/deal-file.md) and the DCF, Financing and Sensitivity tabs in [docs/valuation-tabs.md](docs/valuation-tabs.md).

## Running it

You need Python 3.10+, and LibreOffice for `check` and the recalculation tests.

```bash
sudo apt-get install -y libreoffice-calc
pip install -e ".[test]"

python3 -m sde_value build --deal deals/hvac_service.yaml --out out/hvac_service.xlsx
python3 -m sde_value check out/hvac_service.xlsx
python3 -m sde_value memo --deal deals/hvac_service.yaml
python3 -m sde_value batch deals/ --out out/
python3 -m pytest
```

`memo` writes a two-page Word memo for whoever has to make the call, and `batch` runs a whole folder and adds a `summary.xlsx` with the deals side by side. Everything works offline from the extracts in `data/` ([sources](data/SOURCES.md)). The BLS CDN turned away Python's own HTTP client even with browser headers copied in, so `fetch-data` uses curl when it's installed.

All commands and options are in [docs/commands.md](docs/commands.md).

## What's still wrong

- The repriced value applies the broker's SDE multiple to normalised EBITDA. Small-company EBITDA multiples are often different, so read the cut as how much of the price rests on the recast, not as a fair price.
- The memo is built from the deal file, not the workbook. Toggles flipped in Excel reach the dashboard but not the memo until you set `accept:` in the deal file and rerun.
- Only expense add-backs are modelled. Unreported cash, working capital and capex are what I'd add next.

The rest are in [docs/known-issues.md](docs/known-issues.md).

Project period: 2026-07-13 to 2026-10-06.
