# sde-value

sde-value takes a small-business deal file (the seller's P&L plus the broker's list of add-backs) and builds an Excel workbook where every add-back is its own row with a 1/0 toggle, and the owner's job is priced at what it would cost to hire a manager. I wanted this because a broker's recast usually adds back the owner's whole salary and anything that can be called "one-time", applies a multiple, and never puts back the cost of someone to run the business. A $31,000 "one-time" warranty problem that shows up every year costs a buyer $124,000 at a multiple of four.

The value updates as you flip toggles. A separate Python engine recomputes every output, so the spreadsheet can be checked instead of trusted.

## Running it

You need Python 3.10+, plus LibreOffice for the `check` step and the recalculation tests.

```bash
sudo apt-get install -y libreoffice-calc
pip install -e ".[test]"

python3 -m sde_value build --deal deals/hvac_service.yaml --out out/hvac_service.xlsx
python3 -m sde_value check out/hvac_service.xlsx
python3 -m sde_value summary deals/*.yaml
python3 -m pytest
```

For the HVAC sample, the first two print:

```
Wrote out/hvac_service.xlsx
  Lone Star Comfort Air (sample)
  Seller's SDE            $386,800   (add-backs claimed $291,800)
  Normalised SDE          $294,100   (rejected $92,700)
  Owner replacement       $138,045
  Normalised EBITDA       $156,055
  Asking value          $1,547,200   at 4.0x
  Repriced value          $624,220   (59.7% below asking)

OK: 105 output cells compared after LibreOffice recalculation, 0 mismatches, 0 missing
```

![Add-back register for the HVAC sample deal](docs/addback-register.png)

Everything runs offline from the extracts in `data/`. `fetch-data` downloads the BLS and IRS files again, which was more annoying than it should have been. The BLS CDN returned 403 to Python's urllib even with browser headers, so the fetcher shells out to curl when it can.

The deal file format is in [docs/deal-file.md](docs/deal-file.md), commands and options in [docs/commands.md](docs/commands.md), and data sources in [data/SOURCES.md](data/SOURCES.md).

## How it works

Each add-back records which P&L line it comes out of, what the seller calls it, how many of the last three years it appeared in, whether the cost would continue under a new owner, and whether there are documents for it. The rule had to be short enough to fit in one Excel formula. Owner pay, depreciation and interest keep their labels. A "one-time" item seen in two or more years, or anything that carries on after the sale, becomes recurring-disguised and is rejected. Undocumented discretionary or one-time items are rejected too. You can override any row in the deal file, or just flip the toggle in Excel.

The replacement manager's cost comes from BLS OES wages. OES doesn't publish wages by industry and state together, so I take the national wage for the role in the 4-digit NAICS industry and scale it by the state's cross-industry wage relative to the national one. Benefits go on top from BLS ECEC data for small private employers. Normalised SDE is net income plus accepted add-backs, normalised EBITDA subtracts the manager, and both sit next to IRS SOI ratios for the same industry as a sanity check.

The workbook writes inputs as values and everything else as formulas, each with a defined name, and the engine computes the same names in Python. `check` recalculates the file in headless LibreOffice, reads the inputs back out, runs the engine on them and compares every output. Since it reads the workbook and not the deal file, it still works after you've flipped toggles. One test breaks a formula on purpose to make sure the checker notices.

## Sample deals

The three deals in `deals/` are made up, but each P&L line is revenue times the IRS SOI ratio for that industry, and a test checks this.

| Deal | Seller's SDE | Normalised EBITDA | Asking | Repriced | Cut |
|---|---:|---:|---:|---:|---:|
| HVAC service, TX, 4.0x | $386,800 | $156,055 | $1,547,200 | $624,220 | 59.7% |
| Landscaping, NC, 3.5x | $240,800 | $73,612 | $842,800 | $257,640 | 69.4% |
| Laundromat, OH, 4.5x | $157,500 | $77,705 | $708,750 | $349,673 | 50.7% |

The laundromat only needs a half-time manager, which is why it loses the least.

## Known issues

- The repriced value applies the broker's SDE multiple to normalised EBITDA. Real EBITDA multiples for small companies are often different, so read the cut as how much of the price rests on the recast, not as a fair price.
- SOI ratios cover all corporations in a minor industry, which skews bigger than a typical listing. Some SOI cells are withheld and count as zero, and landscaping has to use a broader category than its NAICS code.
- Only expense add-backs are modelled. Unreported cash, working capital and capex normalisation aren't in yet.
- Next I'd like to add a DCF cross-check with loan coverage, and a way to compare deals side by side in one workbook.

Project period: 2026-07-13 to 2026-07-17.
