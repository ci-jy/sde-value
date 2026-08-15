# sde-value

sde-value takes a small-business deal file (the seller's P&L plus the broker's list of add-backs) and builds an Excel workbook where every add-back gets its own row with a 1/0 toggle, and the owner's job is priced at what it would cost to hire a manager. I built it because a broker's recast usually adds back the owner's whole salary and anything that can be called "one-time", applies a multiple, and never puts back the cost of someone to run the business. A $31,000 "one-time" warranty problem that shows up every year costs a buyer $124,000 at a multiple of four.

## Running it

You need Python 3.10+, plus LibreOffice for the `check` step and the recalculation tests.

```bash
sudo apt-get install -y libreoffice-calc
pip install -e ".[test]"

python3 -m sde_value build --deal deals/hvac_service.yaml --out out/hvac_service.xlsx
python3 -m sde_value check out/hvac_service.xlsx
python3 -m sde_value check out/hvac_service.xlsx --tabs DCF,Financing,Sensitivity
python3 -m sde_value summary deals/*.yaml
python3 -m pytest
```

For the HVAC sample, `build` and the first `check` print:

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

OK: 264 output cells compared after LibreOffice recalculation, 0 mismatches, 0 missing
```

![Add-back register for the HVAC sample deal](docs/addback-register.png)

Screenshots of the other tabs are in `docs/`.

Everything runs offline from the extracts in `data/`. `fetch-data` downloads the BLS and IRS files again, which was more annoying than it should have been. The BLS CDN returned 403 to Python's urllib even with browser headers, so the fetcher shells out to curl when it can.

Commands and options: [docs/commands.md](docs/commands.md)
Deal file format: [docs/deal-file.md](docs/deal-file.md)
DCF, Financing and Sensitivity tabs: [docs/valuation-tabs.md](docs/valuation-tabs.md)
Full sample results: [docs/sample-deals.md](docs/sample-deals.md)
Data sources: [data/SOURCES.md](data/SOURCES.md)

## How it works

Each add-back records which P&L line it comes out of, what the seller calls it, how many of the last three years it appeared in, whether the cost would continue under a new owner, and whether there are documents for it. The classification rule had to be short enough to fit in one Excel formula. Owner pay, depreciation and interest keep their labels. A "one-time" item seen in two or more years, or anything that carries on after the sale, becomes recurring-disguised and is rejected. So are undocumented discretionary or one-time items. You can override any row in the deal file, or just flip the toggle in Excel.

The manager's cost comes from BLS OES wages. OES doesn't publish wages by industry and state together, so I take the national wage for the role in the 4-digit NAICS industry and scale it by the state's cross-industry wage relative to the national one. Benefits go on top from BLS ECEC data. Normalised EBITDA is net income plus accepted add-backs minus that manager, and it sits next to IRS SOI ratios for the same industry as a sanity check.

Three more tabs come at the price from other directions: a five-year DCF, an SBA-style acquisition loan with debt service coverage, and a grid of price and coverage across multiples and how much of the rejected add-backs you give back. Every assumption is a yellow cell.

The workbook writes inputs as values and everything else as named formulas, and a Python engine computes the same names. `check` recalculates the file in headless LibreOffice, reads the inputs back out, runs the engine on them and compares every output. It reads the workbook rather than the deal file, so it still works after you've flipped toggles. The tests break formulas on purpose to make sure the checker notices.

## Sample deals

The three deals in `deals/` are made up, but each P&L line is revenue times the IRS SOI ratio for that industry (a test checks this).

| Deal | Seller's SDE | Normalised EBITDA | Asking | Repriced | Cut |
|---|---:|---:|---:|---:|---:|
| HVAC service, TX, 4.0x | $386,800 | $156,055 | $1,547,200 | $624,220 | 59.7% |
| Landscaping, NC, 3.5x | $240,800 | $73,612 | $842,800 | $257,640 | 69.4% |
| Laundromat, OH, 4.5x | $157,500 | $77,705 | $708,750 | $349,673 | 50.7% |

The laundromat only needs a half-time manager, which is why it loses the least. What surprised me more was the loan side: none of the three asking prices can be borrowed. At the default terms they cover their debt service 0.38 to 0.56 times, and even the repriced values miss 1.25x by a little.

## Known issues

- The repriced value applies the broker's SDE multiple to normalised EBITDA. Real EBITDA multiples for small companies are often different, so read the cut as how much of the price rests on the recast, not as a fair price.
- SOI ratios cover all corporations in a minor industry, which skews bigger than a typical listing. Some SOI cells are withheld and count as zero, and landscaping has to use a broader category than its NAICS code.
- Only expense add-backs are modelled. Unreported cash, working capital and capex normalisation aren't in the recast yet, and that's what I'd add next, along with comparing deals side by side in one workbook.
- The DCF has a fixed number of year columns once the workbook is built, so changing `dcf.years` means rebuilding.

Project period: 2026-07-13 to 2026-08-15.
