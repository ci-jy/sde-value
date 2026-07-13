# Deal file format

A deal is a YAML file. `deals/hvac_service.yaml` is a commented example. Loading a deal fails with a `deal error:` message if a required field is missing, a value isn't a number, a label or P&L line is unknown, or the add-backs against a line add up to more than that line.

## Top level

```yaml
name: Lone Star Comfort Air (sample)        # required
description: Residential HVAC service ...   # optional
industry:
  soi: plumbing_hvac                        # required, IRS SOI industry key
  naics: "238200"                           # required, 4-digit NAICS (6 characters) for OES
state: TX                                   # required
fiscal_year_label: Trailing twelve months   # optional, default "Most recent fiscal year"
asking:
  multiple: 4.0                             # required, the broker's SDE multiple
multiples: [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]   # optional, range shown on the valuation tab
notes: []                                   # optional
```

SOI industry keys in the cached data: `plumbing_hvac`, `other_admin_support`, `personal_laundry`, `specialty_trade_other`.

NAICS codes in the cached OES extract: `238200`, `561700`, `812300`. Other codes need `fetch-data` with the fetcher's industry list extended.

## replacement

```yaml
replacement:
  soc: "11-1021"                  # default; General and Operations Managers
  percentile: median              # pct25, median, mean or pct75
  fte: 1.0                        # more than 0, at most 2
  benefits_group: small_establishment   # small_establishment, management or all_private
```

Occupations in the cached OES extract: 11-1021, 49-1011, 37-1012, 37-1011 and 39-1022.

## pnl

`revenue` is required and must be positive. Expense lines default to 0:

`cogs`, `officer_comp`, `salaries_wages`, `repairs`, `rent`, `taxes_licenses`, `interest`, `depreciation`, `amortization`, `advertising`, `pension`, `employee_benefits`, `other_deductions`.

These match the IRS SOI line items, so the baseline tab can compare them directly.

## addbacks

A list of items:

```yaml
- item: Compressor warranty callbacks   # required
  line: cogs                            # required, one of the P&L lines above
  label: one-time                       # required, see below
  amount: 31000                         # required, positive
  support: Parts invoices               # optional, shown in the register
  years_seen: 3                         # optional, default 1 (of the last three years)
  continues: false                      # optional, would the cost carry on under a new owner?
  documented: true                      # optional, default true
  accept: null                          # optional, true/false overrides the recommendation
  note: Shows up in all three years     # optional
```

`label` is what the seller or broker calls it: `owner compensation`, `discretionary`, `one-time`, `non-cash` or `financing`.

How the label becomes a classification and recommendation:

- `owner compensation`, `non-cash` and `financing` keep their label and are accepted.
- Anything with `continues: true`, or a `one-time` item with `years_seen` of 2 or more, becomes `recurring-disguised` and is rejected.
- A `discretionary` or `one-time` item with `documented: false` is rejected.
- Everything else is accepted.
