# Known issues

- The repriced value applies the broker's SDE multiple to normalised EBITDA. Small-company EBITDA multiples are often different, so read the cut as how much of the price rests on the recast, not as a fair price.
- SOI ratios cover all corporations in a minor industry, which skews bigger than a typical listing. Some SOI cells are withheld and count as zero (see [data/SOURCES.md](../data/SOURCES.md)), and landscaping has to use a broader category than its NAICS code.
- Only expense add-backs are modelled. Unreported cash, working capital and capex normalisation are what I'd add next.
- The memo is written from the deal file, not the workbook, so toggles flipped in Excel show on the dashboard but not in the memo. Set `accept:` in the deal file and rerun `memo` or `batch`.
- The summary sheet copies each deal's engine values and only recomputes the price columns, so edits inside a deal's workbook don't reach it until `batch` runs again.
- The DCF tab has a fixed number of year columns once built, so changing `dcf.years` means rebuilding.
