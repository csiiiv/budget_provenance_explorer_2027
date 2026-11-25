# NIA November 13 review data for the explorer

The [public message](../analysis-nia/data/NIA_PUBLIC_MESSAGE_nov13.md)
provides the scope and public-facing claims for the November 13 review.
Use the structured extracts below for counts and project evidence. Keep
this review scoped to the October 10 and November 13 agency workbooks.
Senate Annex A-3 records separate legislative actions.

| What to show | Source and counting rule |
|---|---|
| Reviewed projects and NEP funding | [Full November annex](../analysis-nia/data/nia_nep_annex_full_nov13.csv), counted once per November Excel row. There are 792 rows totaling ₱17,598,181,000, including one unfunded row. The legislative NEP extract has 791 funded rows. |
| Publicly reported corrections | [Corrected projects](../analysis-nia/data/nia_nep_corrected_projects_nov13.csv), counted once per November Excel row. There are 43 rows totaling ₱1,972,655,000. Keep fixed projects and projects resolved by evidence distinguishable. The five possible duplicate pairs account for ten project rows. |
| Public findings and fixes | [NEP findings](../analysis-nia/data/nia_nep_findings_nov13.csv) provides 90 finding records with categories, evidence, and outcomes. Use the finding ID for the detail record and link all listed project rows where applicable. Title, justification, and region corrections can overlap on the same project. |
| Coordinate coverage | Use the [coordinate verification extract](../analysis-nia/data/nia_coord_verification_nov13.csv) for the 410 rows with a recorded location check. The remaining 382 rows total ₱5,040,005,000. The full annex has complete start and end pairs on 22 rows and only one populated pair on 388. Label the 410 as rows with coordinate evidence and show endpoint completeness separately. |
| Open items and boundary evidence | The [action items](../analysis-nia/data/nia_nep_action_items_nov13.csv) summarize priorities and requests. The [boundary extract](../analysis-nia/data/nia_coord_boundary_dist_nov13.csv) supplies point-level evidence, including distance and verdict. Use November row and point role for detail. Count distinct projects for summary amounts. |
| Broader workbook QA | The [flag ledger](../analysis-nia/data/nia_flags_ledger_nov13.csv) contains 453 entries across the workbook review. Keep its issue categories and dispositions available as additional evidence. The pending and flagged CSVs are alternate review views with their own scope and statuses. Use flag IDs when comparing those views and avoid adding their counts together. |

## Coverage and presentation

- Join to the November annex by verified November Excel row. Use the
  [submitted-list crosswalk](../analysis-nia/data/nia_submitted_list_status_nov13.csv)
  when tracing back to October. Keep ambiguous or missing links visible in
  the workbook review. Workbook header and formula findings belong in
  workbook-level evidence.
- Count fixes by distinct project for the public headline, and by finding
  for the evidence list. The findings file records 31 title refinements,
  including Santa Maria. The public message groups Santa Maria with the
  three region reassignments and describes 30 further title refinements.
- Keep these public-review counts scoped to the workbook. The current
  explorer bundle surfaces 445 of 453 flag IDs, 791 of 792 November annex
  rows, and 42 of the 43 publicly reported corrected rows through its
  existing links. Keep the public denominator when displaying coverage and
  expose review records with missing chain links at workbook level. The
  unmatched correction is `2382H`, a House-side twin with no NEP amount.
  Preserve the suffix and resolve the reference with the pair evidence
  before linking it. Four of the five repeated-title findings have blank
  row references in the findings CSV. Use the corrected-project pair
  evidence to validate any links. Coverage summaries and workbook row ranges
  also belong at workbook level.
