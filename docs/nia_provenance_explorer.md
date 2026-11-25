# NIA Provenance Explorer

Run from the repository root.

```bash
python3 data_formalization/scripts/export_nia_web.py
npm --prefix web run dev
```

Open `http://localhost:5180/nia-provenance.html` or follow the NIA link from the FMR
dashboard. Both pages build with `npm --prefix web run build`.

## Shared project explorer

NIA uses the same dashboard, project table, counted filter chips, and
stage drawer as FMR. The grouping panel drills into provinces using workbook
geography. The stage flow uses workbench NEP–House links and mapped Annex A-3
records. Its agency column is **NIA**. NIA finding and fix chips use the
November flag ledger, and the NEP → House chips cover link coverage and amount changes.

The [traceability guide](provenance_chaining_considerations.md) explains the
shared source and link model. The rules below describe the NIA implementation.

See [NIA review data sources](nia_review_data_sources.md) for the public
review baseline, source choices, and current coverage gaps.

## Sources and link evidence

- The [NIA workbench](../analysis-nia/NIA_WORKBENCH.md) supplies NEP and
  House project rows and their comparison. The exporter pairs spelling
  variants when each record identifies the other as its sole counterpart
  and both are independently linked by the same October workbook row.
  The drawer shows the matching method and the strict comparison result.
  The [reviewed reconciliation records](../analysis-nia/data/nia_chain_reconciliation.json)
  also record complete NEP titles recovered from the PDF, reviewed joins,
  and discrepancies that still need review. The title comparison uses the
  recovered NEP title while the drawer and full export retain both versions.
  Use **Chain link needs review** to find the unresolved pairs.
- October 10 and November 13 agency reconciliation extracts are parallel
  accounts of NEP and House amounts. The exporter first uses a unique
  ledger-linked NEP candidate, a unique title key, and agreement on the
  NEP amount. It can also attach an agency row when its full normalized
  title and both amounts uniquely identify workbook evidence for one chain.
  The evidence drawer shows the extracted leaf and the matching Excel row
  when the link uses workbook evidence.
  A unique reconciliation title and both budget amounts can pair two
  standalone agency observations or attach a November observation to its
  October House-only cut chain when the workbook submission title is blank.
  The drawer records the October agency source ID for the November link.
  Agency extracts retain their original Excel row numbers. The exporter
  uses a verified row locator with original title and amounts before
  title-only fallback. A one-to-one crosswalk can pair repeated agency
  titles across dates while their budget attribution is still in review.
- The [October hearing workbook extract](../analysis-nia/data/senate_nia_dataset.json)
  adds Excel rows, agency submission details, and the match method and
  similarity for each linked PDF record. The
  [submitted-list crosswalk](../analysis-nia/data/nia_submitted_list_status_nov13.csv)
  supplies November row references. The
  [November annex](../analysis-nia/data/nia_nep_annex_full_nov13.csv) and
  [flag ledger](../analysis-nia/data/nia_flags_ledger_nov13.csv) supply
  review details and recorded fixes.
  The NIA columns show the revision submitted at each date, with the
  original workbook label retained in the evidence drawer. The Senate
  drawer compares the annex's Senate title with each available submission
  after typography normalization and identifies the supporting workbook
  rows. Use **Senate description differs from latest NIA submission** to inspect
  discrepancies. This comparison leaves the existing House-to-Senate
  attribution in place.
- The [mapped Senate Annex A-3](../Senate_report_data/data/derived/senate_annex_a3_nia_mapped.json)
  supplies Senate rows and the exporter checks the House mapping against
  the [NIA ledger](../data_formalization/data/ledger/nia.jsonl). Senate
  insertions can link back to NEP through the October and November NIA
  submissions when both workbooks show zero House funding and the full
  submission title, region, province, and amount uniquely agree with
  Annex A-3. The exporter links case- and whitespace-only matches first.
  It then checks remaining rows with normalized punctuation spacing,
  typographic quotes and dashes, and the use of “@” for “at”. Station values,
  coordinates, and unit counts remain part of the comparison. A final
  pass allows a single barangay name before an identical coordinate pair to
  differ when all other match criteria agree. The explorer
  shows these as restorations of NEP funding. The
  Annex action remains an insertion relative to House. A later pass uses
  the latest verified November submission and matches a unique scope,
  booked geography, and amount. It accepts a coordinate change when the
  stated locality agrees, or a locality wording change when the coordinate
  pair and any stated jurisdiction agree. The drawer retains both titles
  and flags the difference. The
  [reverse-review decisions](../analysis-nia/data/nia_senate_reverse_review.json)
  record additional reviewed joins, unresolved candidates, and rows for
  which the search found no candidate. Use **Senate–NIA candidate needs
  review** to open the two source chains for a candidate. Submission-only
  workbook rows can document a Senate insertion such as Luttuad without
  creating a NEP or House entry. The drawer links the recipient and donor
  when the workbook justification documents a matching Senate reduction
  and insertion. Each Senate row also
  carries the printed region and province roll-up subtotals joined from the
  [raw A-3 snapshot](../Senate_report_data/data/derived/senate_annex_a3_nia.json)
  (`province_subtotal` / `region_subtotal`, 939 of 940 rows — the national
  watershed line has none), plus a normalized `region_key` that folds the
  annex's inconsistent `REGION IV-A`/`IV-B` spellings into the House's
  `Region 4A`/`4B`. Subtotals pair with their leaf groups in document
  order, so a province that prints twice under one region keeps each
  group's own subtotal. The Senate stage drawer shows the program →
  sub-program → activity trail with those subtotals and each row's share
  of its province total.
- The [exporter](../data_formalization/scripts/export_nia_web.py) writes
  `web/public/data/nia.json` and includes the input hashes. It also writes
  the [download set](#download-exports) under `web/public/data/export/nia/`.
  Missing links
  display a dash, while explicit zero funding displays ₱0. Agency table
  cells show the workbook House amount. October action badges compare that
  amount with the linked House bill. November badges compare with October.
  Senate actions use the House baseline printed in Annex A-3. The detail drawer shows both
  workbook amounts. GPS is shown in decimal degrees as latitude, longitude.
  The October view uses the hearing workbook's existing normalized title
  points, the November view uses the review annex's decimal endpoints, and
  the Senate view uses the shared coordinate parser on the annex text.
  The drawer retains source wording and coordinate review findings.

## Coverage

The export preserves 791 NEP, 828 House, and 940 Senate source rows. Each
workbook contains 803 numeric leaves, including 108 with House funding
reduced to zero. Each vintage has 624 links and 179 standalone leaves.
The 1,483 explorer rows include unmatched source records as well as linked
chains. Totals cover project annex rows in the export.

## Download exports

Both explorers link a static download set written by their exporters
(`data_formalization/scripts/export_downloads.py` provides the shared
writers) under `web/public/data/export/<program>/`:

| File | Contents |
|---|---|
| `chains-simple.csv` | One row per chain — the explorer table view: ids, title, geography, stage amounts in integer pesos, senate citation and status, actions, review flags. |
| `chains-full.csv` | Wide CSV — every scalar field stage-prefixed; coordinate and evidence arrays JSON-encoded per cell. |
| `findings.csv` | One row per review finding, keyed by chain id (FMR: DA review annex findings by vintage; NIA: November flag ledger). |
| `rollups.csv` | The annex's printed heading subtotals (NIA: per region/province group in document order; FMR: per region) with leaf sums and a `reconciles` check per row. NIA sums to ₱17,648,181,000 Senate across all 343 province groups; the ₱100M watershed activity prints without geography. |
| `full.json` | Verbatim chain records plus manifest (input hashes, totals) — the lossless export. |
| `SHA256SUMS.txt` | Hashes of every file above. |

Conventions: amounts are integer pesos, explicit zero prints `0`, missing
stays empty. Files are deterministic given the same inputs and reconcile
with the browser bundles at build time.
