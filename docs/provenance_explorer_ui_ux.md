# Budget provenance explorer UI/UX

FMR, NIA, and DPWH share the dashboard, project table, filter chips, stage rail,
and drawer shell. Keep those interactions familiar across programs. Adapt
the terms, evidence, and grouping to the records users are tracing.
[FMR cases](fmr_budget_chain_edge_cases.md) ·
[NIA implementation](nia_provenance_explorer.md) ·
[DPWH implementation](dpwh_provenance_explorer.md)

## Project table and amounts

- Keep the main columns predictable. FMR and NIA show **Project,
  Region, NEP, House, Agency, Senate, and Actions by stage**. Use the
  actual agency name in the Agency column. Give each workbook edition a
  label when the value depends on the edition or the amounts disagree.
  DPWH uses the equivalent slot for key-document coverage. Use a
  label that makes the measure clear and distinguish zero documents
  found from missing review coverage.
- Display amounts using their magnitude, such as **250K**, **100M**, and
  **1.2B**. Preserve meaningful decimal precision. Show explicit zero as
  **0** and a missing amount as **—**. Keep source totals in pesos for
  reconciliation and label fixed units on charts that use them. Place a
  minus sign before the currency symbol on negative amounts
  (**-₱147M**, never **₱-147M**).
- Count a displayed chain once in the table and grouping panel. Keep
  related source rows accessible by original title or exact locator.
  When a possible restatement combines a cut and insertion in the
  explorer, retain both annex rows and the original source totals.

## Stage labels and review marks

- Name the baseline behind a comparison. House compares with NEP.
  For NIA, October compares its workbook House amount with the linked
  House bill, and November compares its workbook House amount with
  October. Senate actions use the baseline printed in the annex.
  A repeated NEP-to-House change inside two workbooks is a single
  change, even if both books report it.
- Show the main action alongside material changes supported by source
  evidence. **Same amount**, **Title revised**, and **Province
  reassigned** can all describe the same stage. Keep amount changes,
  wording and scope changes, coordinate differences, and documented
  corrections distinguishable. If only one edition provides the
  evidence needed for a comparison, label what is available.
- Distinguish **N/A**, **No prior amount**, and **Review evidence**.
  Check linked workbook evidence before showing an unavailable amount
  or action. A finding can still be valid when an amount is missing.
- Pair color with a readable label or accessible name. Red flags mark
  pending or flagged findings. Green checks mark documented corrections.
  In NIA, the **No coordinates · system or station only** finding uses
  a yellow flag. Show each applicable mark when a stage has more than
  one kind of finding. Explain the colors in the legend and retain the
  finding's actual status in the drawer.

## Search, filters, and drill-down

- Search the titles and IDs a reader can find in the source. Include
  original and revised titles, workbook controls, and annex locators.
  Tell readers when other filters hide search matches.
- Put each question in one filter row. NIA combines amount changes and
  unlinked sides under **NEP → House**, and puts Senate actions under
  **House → Senate**. Stage filters should include visible material
  notes, such as **Region reassigned**, when the program supports them.
- Keep **Review status**, **Finding type**, and **Fix type** distinct.
  Separate a documented fix from a finding **Resolved by evidence**.
  For November GPS coverage, distinguish both endpoints, one coordinate
  pair, and no pair. Keep missing or multiple workbook links explicit.
  Within **Finding type**, group related chips under small subheaders so
  the row stays scannable: FMR uses Location / Coordinates; NIA uses No
  coordinates / Geography checks / Workbook defects; DPWH uses Key
  documents plus each review-set flag family (Documents, NEP comparison,
  Amount and cost, Repeats and history, Location and map). Pass an
  optional third element on each `[value, label, group]` option; the
  shared chip row puts each group on its own line (subheader + chips),
  in first-appearance order, and leaves the “Any finding” chip on a
  line above them.
- Chip counts measure chains that would match the choice with the
  current search and other filters applied. Count a chain once per chip
  even when multiple findings support it. Counts across chips can
  overlap. Use the same grouping key for the group summary and the
  resulting filtered table. FMR uses municipalities and NIA uses
  provinces. DPWH uses regional totals and implementing-office
  evidence at the grain its sources support.

## Evidence drawer

- Use the shared stage rail and open the selected stage from its table
  badge. Keep the project title, chain type, ID, and location easy to
  scan. Give header fields consistent spacing and allow long IDs and
  titles to wrap.
- Give original and revised titles clear labels. Use small tables for
  amounts and source references so each value has a row label. Separate
  the official allocation, workbook amount, and submission amount.
  Reserve prose for a finding, justification, or explanation of the
  link.
- Render the annex hierarchy as a trail, not a joined string. Show the
  program → sub-program → activity breadcrumb, then one row per printed
  geography step with its roll-up subtotal as printed (House → Senate
  with the annex page). Include the row’s share of its deepest subtotal
  so readers can size a line item against its province or region.
  NIA shows region and province rows (MARIIS/UPRIIS print as region-
  level offices); FMR shows the region row only. DPWH shows the region
  and implementing-office rows with their **full-budget** House →
  Senate totals and printed net change (Central Office prints at office
  level). A row printed without geography gets an explicit note instead
  of a silent blank, and the source-reference table carries the
  normalized region key when the printed spelling differs from the
  grouping key. For change-only annexes, label verified subtotals as
  the annex’s own accounting and do not derive per-region deltas from
  listed rows alone.
- Show normalized GPS in decimal **latitude, longitude** with endpoint
  roles where supported. Keep printed coordinates and location-review
  evidence accessible. Compare equivalent fields across editions in a
  draft comparison. Show source IDs, workbook rows, PDF pages, and
  match methods near the details they support.
- Preserve the distinction between a printed action and an inferred
  chain relationship. Label tentative matches and let readers open
  the related record. A title change, coordinate clue, or equal amount
  should be visible with enough context for review.

## Dashboard and review scope

Show stage totals and match coverage with the relevant denominator.
An explorer chain count, a finding count, and a count of distinct
corrected projects each answer a different question. NIA's public review
summary covers workbook records beyond those linked into the explorer.
When displaying that summary, use the workbook denominator and make
unlinked evidence available at workbook level. In DPWH, distinguish
the key-document count (0–5), linked files, and red flag entries.
Describe files as missing from the covered sources when the review
could not find them. Label Senate figures that cover only printed
Annex A-4 adjustments.
[NIA review source and coverage notes](nia_review_data_sources.md)

## Check the experience before release

- Find a project by both its title and a source ID. Confirm filters,
  chip counts, hidden-result feedback, and geographic drill-down.
- Open each stage from the table. Check a long title and ID, a zero
  amount, a missing amount, and amounts across K, M, and B. Check a
  narrow viewport and keyboard access to the controls and drawer.
- Inspect a row with several notes at one stage and a row with review
  evidence but incomplete amounts. Confirm each note uses the right
  baseline and each review mark has a readable label.
- Open the Senate stage for a row in each geography shape: regioned,
  office-level (NIA MARIIS/UPRIIS, DPWH Central Office), and — where
  present — a national row with no roll-up. Check the trail’s subtotal
  amounts against the cited annex page and confirm the share percentage
  is present (share applies where the annex prints scope-only subtotals;
  DPWH A‑4 prints full-budget headings, so its trail shows net change
  instead of a share). Search and filter by region to confirm
  normalized keys did not fragment buckets (one Region 4A bucket, not
  IV-A and 4A; one NCR bucket across NEP, House, and A‑4 spellings).
- Trace a correction and a tentative match to their original records.
  Check that coordinate order, paired source rows, and raw evidence
  remain visible. Run the production build and check each affected
  explorer when changing a shared component.

[Build and verification guide](provenance_explorer_build_guide.md) ·
[Budget explorer design guide](budget_provenance_explorer_design_guide.md)
