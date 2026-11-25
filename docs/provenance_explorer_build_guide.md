# Build a provenance explorer web app

FMR, NIA, and DPWH have separate entry pages in one Vite app. They use
the same dashboard, project table, filter chips,
stage rail, and drawer shell. A program supplies its own data adapter,
source evidence, and labels. Use the
[provenance chaining considerations](provenance_chaining_considerations.md)
to define what each link means before wiring it into the UI.

For a new dataset, use the [budget explorer design guide](budget_provenance_explorer_design_guide.md)
to choose the record grain, stages, and views before implementing them.

The [explorer UI/UX guide](provenance_explorer_ui_ux.md) records the
interaction and presentation decisions across the explorers.

## 1. Build and verify the program export

1. Inventory existing extracts, workbooks, review files, and ledger
   entries. Identify official budget stages, parallel agency workbook
   editions, and derived review evidence. Choose the unit for each
   summary, such as a source row, chain, unique project, or finding.
2. Create a deterministic exporter that reads those inputs and writes
   static JSON under `web/public/data/`. Keep original source IDs,
   locators, typed link evidence, review status, and missing and zero
   values. Record input hashes and check that each source row appears
   once in its stage totals. Keep unmatched records accessible.
3. Carry the annex’s printed structure, not just leaf rows. Join the
   heading rows retained in the raw snapshot back onto each mapped row:
   the full hierarchy path plus the printed region/province subtotals
   (NIA `province_subtotal`/`region_subtotal`, FMR `region_subtotal`).
   For a change-only annex whose headings print the unit’s full budget
   (DPWH A‑4), attach only subtotals whose change columns reconcile
   with Σ listed projects and keep the reconciliation result in the
   snapshot. Reconcile leaves against the controls at the same level
   and scope. Include the raw snapshot as a bundle input and stamp a
   normalized region key where the source’s spellings vary (NIA
   `REGION IV-A` vs `4A`; DPWH `NCR`/`CAR` vs full region names).
4. Reuse existing source crosswalks and normalized fields. For NIA, the
   October hearing workbook supplies Excel rows and match methods. The
   submitted-list crosswalk supplies verified November row references.
   The drawer uses existing decimal coordinates from those extracts and
   the shared parser for Senate Annex A-3 text.

[FMR exporter](../data_formalization/scripts/export_web.py) ·
[NIA exporter](../data_formalization/scripts/export_nia_web.py) ·
[DPWH exporter](../data_formalization/scripts/export_dpwh_web.py) ·
[NIA review data sources](nia_review_data_sources.md)

## 2. Connect the data to the shared UI

| Component | Program wiring |
|---|---|
| [Dashboard](../web/src/App.jsx) | Pass `manifest.totals`, `projects`, `regions`, and `localities` to `ProvenancePage`. Supply header, KPI cards, footer, and explorer configuration. |
| [Project explorer](../web/src/Explorer.jsx) | Adapt records to the shared table shape. Supply stable IDs, title, region, type, stage amounts in millions, actions by stage, searchable source aliases, and review statuses. Keep the source amounts in pesos for evidence and totals. |
| [Stage rail](../web/src/StageRail.jsx) | Use `BudgetStageRail` for stage labels, actions, and review marks. Use the same stable stage IDs in the table buttons and the drawer. Map program actions to the shared colors for increases, cuts, revisions, and insertions. |
| [Project drawer](../web/src/Detail.jsx) | Use `ProjectDrawer` for the shell and navigation. Build stage contents with `FieldDiff`, `DetailTable`, `DeltaBar`, `Flags`, and `Remark`. Show the alternate workbook or annex row and its match basis where a related record can be opened. For the Senate stage, render the shared [AnnexTrail](../web/src/AnnexTrail.jsx) with the printed hierarchy steps and region/province roll-up subtotals. |
| [Flow](../web/src/Flow.jsx), [regions](../web/src/Regions.jsx), and [grouping](../web/src/Localities.jsx) | Supply stage totals and source geography. Use the same grouping keys for the aggregation and explorer drill-down. Give unmatched rows flow labels consistent with the link evidence. |

Use [the NIA entry module](../web/src/Nia.jsx) as the worked adapter.
It loads the generated bundle, builds table and geography records, and
supplies program callbacks and labels through the explorer configuration.
The shared components still contain FMR defaults and some NIA-specific
branches. When adding a program, check those defaults and pass the
relevant behavior explicitly, especially flow labels, grouping, and
comparison filters.

## 3. Fit the program's evidence into the UI

- **Agency stages.** Change the agency column heading and stage stops to
  match the sources. NIA shows the House amounts reported by the October
  10 and November 13 reconciliation workbooks. The drawer shows both
  NEP and House workbook amounts. DPWH uses the corresponding column
  for the count of key documents found (0–5). An explicit zero stays
  visible and an unlinked review record has a separate display state.
- **Formatting and transitions.** Keep the adapter's numeric fields in
  their expected units and format only at render time. Use `fmtBudget`
  for pesos and `fmtM` for values stored in millions. Set a main
  action for each stage and add material notes supported by comparable
  fields. Feed notes into the stage facet when users should be able
  to filter on them, as NIA does with `stageNotes`.
- **Flags and fixes.** Define finding categories and fix outcomes from
  the program's review data. NIA currently uses the November flag ledger
  for filters. Its public review summary has a separate scope described
  in the review data notes. If linked workbook evidence exists outside
  the lightweight reconciliation extract, use it for the stage badge
  and amount. A flag with unavailable amounts can show **Review evidence**.
- **Filter counts.** Count visible chains for each option with all other
  active filters applied. Combine options that answer the same question.
  NIA uses one **NEP → House** row for amount changes and unlinked sides.
- **Coordinates and geography.** Show decimal latitude, longitude in
  the appropriate stage, with raw coordinate text and findings in source
  evidence. Preserve point roles where supplied. NIA groups by province
  using workbook geography. FMR groups by municipality.
- **Legislative actions.** Follow the program's annex and mapping
  evidence. FMR presents some cut and insertion pairs as possible
  restatements. NIA keeps Annex A-3 insertions separate and exposes
  workbook evidence where it connects records listed on separate chains.

## 4. Add the entry page and verify the build

Add the program HTML page and React entry module, register the HTML page
in [Vite's build inputs](../web/vite.config.js), and link it from the
existing app where appropriate. Verify the browser loads the generated
bundle when served from the production output.

Run from the repository root. Install the web dependencies once with
`npm --prefix web ci`.

```bash
python3 data_formalization/scripts/export_web.py --program fmr
python3 data_formalization/scripts/export_nia_web.py
python3 data_formalization/scripts/export_dpwh_web.py
npm --prefix web run dev
npm --prefix web run build
```

The dev server serves FMR at `/`, the NIA landing page at `/nia.html` (provenance at `/nia-provenance.html`), and DPWH at
`/dpwh.html` on port 5180.
The production output is `web/dist/`. With Playwright and Chromium
available, run `python3 web/check_smoke.py` for FMR and
`python3 web/check_dpwh_smoke.py` for DPWH after building. For NIA,
check its own entry page and representative workbook and annex IDs.
For a new program, repeat the same browser checks against its own entry
page and representative source IDs.

- Check direct source ID and title search, stage filters, counts, and
  province or municipality drill-down.
- Open each stage from the table. Check amounts and missing values,
  coordinate order, review badges, related-record links, and drawer
  close behavior.
- Include a known fix, an unresolved finding, a zero amount, an
  unmatched record, and a record with evidence from multiple editions.
- Check the Senate stage trail on a regioned row, a row under a
  national/system office (NIA MARIIS/UPRIIS; DPWH Central Office), and —
  where the program has one — a row printed without geography (NIA
  watershed). Confirm the roll-up amounts match the annex page as
  printed and that region-key buckets are not fragmented by spelling
  variants. For DPWH, confirm the trail shows full-budget subtotals
  with net change, only for blocks the snapshot marked verified.
- Rebuild the export from the same inputs and reconcile row counts and
  stage totals. Exercise all programs affected by edits to shared
  components. With multiple action badges or tables, scope each
  assertion to its stage, named table, or row.

[FMR web implementation](fmr_budget_chain_web.md) ·
[NIA explorer implementation](nia_provenance_explorer.md) ·
[DPWH explorer implementation](dpwh_provenance_explorer.md)

## 5. Download exports

Each exporter also writes a static download set (shared writers in
[export_downloads.py](../data_formalization/scripts/export_downloads.py))
under `web/public/data/export/<program>/`: `chains-simple.csv` (table
view), `chains-full.csv` (wide, all scalars), `findings.csv` (one row
per finding), `rollups.csv` (printed annex subtotals with per-row
reconciliation), `full.json` (verbatim records + manifest), and
`SHA256SUMS.txt`. Amounts are integer pesos; explicit zero prints `0`
and missing stays empty. The UI links the set through the shared
`Downloads` component in the page header. Regenerate exports together
with the bundle — they share the exporter run, so they stay consistent
with the displayed totals.
