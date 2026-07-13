# Commands

All commands run as `python3 -m sde_value <command>`.

## build

```bash
python3 -m sde_value build --deal deals/hvac_service.yaml [--out out/hvac_service.xlsx]
```

Writes the workbook and prints a short summary. `--out` defaults to `out/<deal file name>.xlsx`.

## check

```bash
python3 -m sde_value check out/hvac_service.xlsx [--keep DIR]
```

Recalculates the workbook in headless LibreOffice (with a private profile, so it doesn't touch a running instance), runs the Python engine on the recalculated inputs and compares every named output: strings exactly, money to half a cent, ratios to 1e-9. Prints each mismatch or missing cell and exits 1 if there are any. `--keep` saves the recalculated copy in `DIR`.

## summary

```bash
python3 -m sde_value summary deals/*.yaml
```

Prints seller's SDE, normalised EBITDA, asking value, repriced value and the cut for each deal, plus the average cut. Doesn't need LibreOffice.

## fetch-data

```bash
python3 -m sde_value fetch-data
```

Downloads the BLS OES, BLS ECEC and IRS SOI files and rewrites the extracts in `data/`. Uses curl if it's installed (the BLS CDN rejects urllib) and falls back to urllib otherwise. See [data/SOURCES.md](../data/SOURCES.md) for the URLs and what's kept.

## Screenshots

```bash
PYTHONPATH=. python3 scripts/screenshots.py out/hvac_service.xlsx docs/
```

Regenerates the PNGs in `docs/`.

## Workbook names

Inputs are named `i_*` (for example `i_revenue`) and outputs `o_*` (for example `o_normalised_ebitda`, `o_ab7_class`). The engine uses the same keys, which is how `check` pairs them up.
