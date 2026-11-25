# DPWH Provenance Explorer

Run from the repository root.

```bash
python3 data_formalization/scripts/export_dpwh_web.py
npm --prefix web run dev
```

Open `http://localhost:5180/dpwh.html` or follow the DPWH link from the FMR
or NIA dashboards. All three pages build with `npm --prefix web run build`.
With Playwright and Chromium available, run
`python3 web/check_dpwh_smoke.py` after the build.

## Shared project explorer

DPWH uses the same dashboard, project table, counted filter chips, stage
rail, and drawer shell as FMR and NIA. The chain unit is the House Vol I-C
third-reading **project leaf**; the stage rail shows NEP → House I-C →
HGAB review → Senate Annex A-4. Grouping by municipality does not apply —
DPWH geography resolves to region and implementing office, so the locality
panel is off and the region panel carries the stage totals. The agency
column shows the review set's key-document count (0–5) instead of an
amount.

The [traceability guide](provenance_chaining_considerations.md) defines the
shared model. The rules below describe the DPWH implementation.

## Sources and link evidence

- The NEP side comes from the [source projects extract]
  (../analysis/data/nep_2027_source_projects.json) (FY2027 Vol 2B
  operations; foreign-assisted projects at their printed totals). The
  [reading comparison](../analysis/data/dpwh_comparison_all_2027.csv)
  supplies the NEP→House candidate edges and match statuses. Each source
  row appears exactly once in the bundle.
- The House side is the [native I-C third-reading tree]
  (../analysis/data/hb_dpwh_native_ic_projects_3rd_reading.json):
  15,977 project leaves plus controls. Comparison rows that anchor on an
  office, region, allocation, or foreign-assisted project node become
  **control chains** shown at their own level; their amounts are never
  summed with the leaves. The five third-reading-only Caloocan rows and
  the three repeated-key groups retain their comparison evidence.
- Senate evidence is [mapped Annex A-4]
  (../Senate_report_data/data/derived/senate_annex_a4_dpwh_mapped.json),
  joined to House leaves through the verified printed-page crosswalk
  (+8 offset for Vol I-C). The printed action columns classify each row:
  an empty Senate amount with a decrease is **Cut to zero**, increases
  are **Increase**, equal amounts with a revised title are **Revised
  description**. The eight unmatched A-4 rows stay as their own chains
  with the bridge note visible. A-4 is change-only: absence of a Senate
  record means the Senate left the House amount as-is, and the rail says
  so rather than showing zero.
- The [HGAB review set](../dpwh_HGAB_REVIEW_SET/README.md) bridges to
  House leaves on (PDF page, amount, title): 15,972 of 15,979 rows join
  uniquely; 2 rows are ambiguous and 301 chains (mostly controls and
  FAP totals, which the review set does not cover at leaf level) have no
  bridged review. Key-document indicators, linked file counts, and red
  flags are separate measures and are shown separately. The first 30
  flag entries render in the drawer; the project and reviewer pages on
  budget.bettergov.ph are linked for the full evidence.
- Senate drawer rows render the printed A‑4 hierarchy with the shared
  `AnnexTrail`: the program/sub-program breadcrumb, then the region and
  implementing-office rows with their printed **full-budget** totals
  (House → Senate, including lines the change-only annex does not list)
  and net change, with the annex page cited. Only blocks whose change
  columns reconcile exactly with Σ listed projects in the [raw A‑4
  snapshot](../Senate_report_data/data/derived/senate_annex_a4_dpwh.json)
  are shown (752 verified heading instances; 20 named exceptions are
  recorded in the snapshot's `rollup` section instead of displayed).
  The source table carries the normalized `region_key` alongside the
  printed region spelling.

## Limits

- The Transparency API snapshot is a separate comparison source with its
  own coverage; its amount travels on the comparison evidence, not as a
  chain stage.
- Volunteer verdicts and flag-to-fix history are not published and are
  not part of this explorer.
- Senate comparisons cover only rows Annex A-4 prints. Region totals for
  the Senate stage therefore cover A-4 rows, not the whole program —
  including the trail's full-budget subtotals, which are the annex's
  own accounting for the unit, not a Senate-vs-House regional delta.
- A-4 heading subtotals are not shown for the 20 heading instances
  whose change columns do not reconcile with Σ listed projects
  (trailing right-aligned region subtotals and office blocks printed
  before their region heading). The snapshot records each exception
  with printed and summed amounts for review.
