# Cached data extracts

These CSVs are small cuts of public files so the tests and the workbook build
run offline. `python -m sde_value fetch-data` downloads the originals again
(with a browser User-Agent, which BLS requires) and rewrites them.

| File | Source | What is kept |
|---|---|---|
| `bls_oes_wages.csv` | BLS OES May 2024 national file, https://www.bls.gov/oes/special-requests/oesm24nat.zip | Cross-industry wage percentiles for the five replacement occupations |
| | BLS OES May 2024 state file, https://www.bls.gov/oes/special-requests/oesm24st.zip | Same occupations, every state |
| | BLS OES May 2024 4-digit NAICS file, https://www.bls.gov/oes/special-requests/oesm24in4.zip | Same occupations in NAICS 2382, 5617 and 8123 |
| `bls_ecec.csv` | BLS ECEC time series, https://download.bls.gov/pub/time.series/cm/cm.data.0.Current | Wages and total benefits per hour worked, private industry: all workers, establishments with 1-49 workers, and management/professional occupations |
| `irs_soi_minor_industry.csv` | IRS SOI Corporation Complete Report, Table 5.1, tax year 2022, https://www.irs.gov/pub/irs-soi/22co51ccr.xlsx | Business receipts and income-statement lines (thousands of dollars) for four minor industries |

Notes:

- OES values are annual wages in dollars; `*` and `#` (suppressed or top-coded)
  are read as missing.
- SOI marks some cells `d` (withheld to avoid disclosing a single company).
  Those are blank in the CSV and count as zero in the ratios. For plumbing/HVAC
  this hits "Total deductions" and "Total receipts less total deductions",
  which is why the model uses "Net income (less deficit)" for the industry
  margin.
- Occupations: 11-1021 General and Operations Managers, 49-1011, 37-1012,
  37-1011 and 39-1022 first-line supervisors.
