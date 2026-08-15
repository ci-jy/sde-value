# Sample deal results

The three deals in `deals/` are made up. Each P&L line is revenue times the IRS SOI ratio for that industry. `tests/test_sample_results.py` pins the cuts so a data or rule change shows up.

## Recast

| Deal | Seller's SDE | Normalised EBITDA | Asking | Repriced | Cut |
|---|---:|---:|---:|---:|---:|
| HVAC service, TX, 4.0x | $386,800 | $156,055 | $1,547,200 | $624,220 | 59.7% |
| Landscaping, NC, 3.5x | $240,800 | $73,612 | $842,800 | $257,640 | 69.4% |
| Laundromat, OH, 4.5x | $157,500 | $77,705 | $708,750 | $349,673 | 50.7% |

Average cut across the three: 59.9%.

## DCF and financing

At the default loan terms:

| Deal | DCF value | DCF / normalised EBITDA | DSCR at asking | Largest financeable price | As a multiple of seller's SDE |
|---|---:|---:|---:|---:|---:|
| HVAC service | $486,172 | 3.1x | 0.48x | $593,621 | 1.5x (asks 4.0x) |
| Landscaping | $197,393 | 2.7x | 0.38x | $254,479 | 1.1x (asks 3.5x) |
| Laundromat | $254,453 | 3.3x | 0.56x | $319,062 | 2.0x (asks 4.5x) |

On the HVAC sensitivity grid, 12 of the 35 cells clear 1.25x and none of them is at the broker's 4.0x.

`check --tabs DCF,Financing,Sensitivity` on the HVAC workbook prints:

```
OK: 159 output cells on DCF, Financing, Sensitivity compared after LibreOffice recalculation, 0 mismatches, 0 missing
```
