# Commands

All commands run as `python3 -m sde_value <command>`.

## build

```bash
python3 -m sde_value build --deal deals/hvac_service.yaml [--out out/hvac_service.xlsx]
```

Writes the workbook and prints a short summary, including the DCF value and the largest price the cash flow can finance. `--out` defaults to `out/<deal file name>.xlsx`.

## check

```bash
python3 -m sde_value check out/hvac_service.xlsx [--keep DIR] [--tabs DCF,Financing,Sensitivity]
```

Recalculates the workbook in headless LibreOffice (with a private profile, so it doesn't touch a running instance), runs the Python engine on the recalculated inputs and compares every named output: strings exactly, money to half a cent, ratios to 1e-9. Prints each mismatch or missing cell and exits 1 if there are any. `--keep` saves the recalculated copy in `DIR`. `--tabs` only compares output cells that sit on the named tabs (the engine still reads every input); an unknown tab name exits with 2.

## memo

```bash
python3 -m sde_value memo --deal deals/hvac_service.yaml [--out out/hvac_service-memo.docx]
```

Writes a short Word memo: the bottom line, asking vs supported value, the earnings bridge, each rejected add-back with the reason, and the financing verdict. Numbers come from the engine with the deal file's toggles, so edit `accept:` in the deal file rather than the workbook if you want the memo to follow. `--out` defaults to `out/<deal file name>-memo.docx`.

## batch

```bash
python3 -m sde_value batch deals/ [--out out/] [--check]
```

For every `.yaml` in the folder, writes `<name>.xlsx` and `<name>-memo.docx` to the output folder, then `summary.xlsx` with one row per deal. In the summary, asking value, repriced value, supported value and the gap to asking are formulas over the row's own cells, and the workbook and memo columns are relative links. A deal file that fails to load is reported on stderr and skipped; the rest still run and the command exits 1. `--check` also runs the LibreOffice check on each workbook (about a second per deal) and exits 1 if any fails.

## dashboard

```bash
python3 -m sde_value dashboard out/hvac_service.xlsx --pdf docs/dashboard.pdf
```

Prints the Dashboard tab to a one-page PDF. LibreOffice prints every visible sheet, so it works on a copy with the other tabs hidden. The creation timestamps LibreOffice writes into the PDF are blanked.

## summary

```bash
python3 -m sde_value summary deals/*.yaml
```

Prints seller's SDE, normalised EBITDA, asking value, repriced value and the cut for each deal, plus the average cut, without writing any files. Doesn't need LibreOffice.

## fetch-data

```bash
python3 -m sde_value fetch-data
```

Downloads the BLS OES, BLS ECEC and IRS SOI files and rewrites the extracts in `data/`. Uses curl if it's installed (the BLS CDN rejects urllib) and falls back to urllib otherwise. See [data/SOURCES.md](../data/SOURCES.md) for the URLs and what's kept.

## Screenshots

```bash
python3 -m sde_value batch deals/ --out out/
PYTHONPATH=. python3 scripts/screenshots.py out/hvac_service.xlsx docs/ out/hvac_service-memo.docx out/summary.xlsx
```

Regenerates the PNGs and `dashboard.pdf` in `docs/`. Needs `pdftoppm` (poppler-utils) and ImageMagick's `convert`.

## Workbook names

Inputs are named `i_*` (for example `i_revenue`, `i_fin_senior_rate`) and outputs `o_*` (for example `o_normalised_ebitda`, `o_ab7_class`, `o_dcf_y3_fcf`, `o_fin_asking_dscr`, `o_sens_2_5_value`, `o_supported_value`). Sensitivity cells are `o_sens_<row>_<column>_value` and `_dscr`. The engine uses the same keys, which is how `check` pairs them up.
