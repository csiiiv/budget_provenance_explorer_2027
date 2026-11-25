# FMR budget-chain web app — Vite + React migration & per-stage actions

Updated 23 November 2026. This document covers the web app, the matching
rules tested against specific roads, and the remaining work.

---

## Part 1 — What we did

### 1.1 From single-file CDN app to Vite + React dev server

The app started as one `web/index.html` with Preact + `htm` + ECharts pulled
from jsDelivr and a `python3 -m http.server` behind it. As the UI grew
(drawer diffs, grouping panel, evidence boxes) that setup lost us hot
reloading, real modules, and type-checked deps. The repo already ran the
identical stack in `analysis/web` (React 19 + Vite 6), so `web/` was
migrated to match.

**New layout**

```
web/
  index.html            # shell only
  vite.config.js        # react plugin; copies public/data into dist/ on build
  package.json          # react 19, react-dom 19, echarts 5, vite 6
  src/
    main.jsx            # React entry point
    App.jsx             # header KPIs + panel composition + drill-down state
    lib.jsx             # labels/colors, fmt helpers, stage-chip logic, useLedger()
    Flow.jsx            # ECharts sankey: NEP → House → Senate money flow
    Regions.jsx         # per-region stage bars
    Localities.jsx      # grouping analysis (municipality-level)
    Explorer.jsx        # filterable chain table + drawer trigger
    Detail.jsx          # per-stage drawer (NEP / House / DA / Senate cards,
                        #   FieldDiff strike-throughs, callouts, evidence boxes)
    styles.css          # dark theme, status + action pills
  public/data/fmr/      # exporter output (moved from web/data via git mv)
```

### Data and build entry points

| Layer | Location and role |
|---|---|
| NEP and House | [`fmr_workbench.json`](../other-analysis/data/fmr_workbench.json) supplies project records and region labels. [`build_fmr_workbench.py`](../other-analysis/build_fmr_workbench.py) builds the workbench from upstream extracts in `other-analysis/`. |
| DA working drafts | [Nov 5](../other-analysis/data/da_fmr_draft.json) and [Nov 12](../other-analysis/data/da_fmr_draft_nov12.json) JSON extracts come from [`extract_da_fmr.py`](../other-analysis/extract_da_fmr.py). |
| Senate | The [mapped Annex A-1 rows](../Senate_report_data/data/derived/senate_annex_a1_fmr_mapped.json) supply regional and action details. [`wire_senate_annexes.py`](../data_formalization/scripts/wire_senate_annexes.py) wires annex evidence into the ledger. |
| Provenance | The [FMR ledger](../data_formalization/data/ledger/fmr.jsonl) holds observations and link assertions. The [snapshot manifests](../data_formalization/data/nodes/snapshot/fmr/) record artifact lineage. |
| Web export | [`export_web.py`](../data_formalization/scripts/export_web.py) folds the ledger and enriches records with the upstream JSON above. It currently supports FMR. |
| Browser and build | [`web/public/data/fmr/`](../web/public/data/fmr/) contains the generated bundles. [`web/src/lib.jsx`](../web/src/lib.jsx) loads `manifest.json`, `projects.json`, `regions.json`, and `localities.json`. The exporter also writes `lineage.json`. [Vite](../web/vite.config.js) serves the bundles locally and copies them into the production build. |
| Verification | The [FMR workflow](../.github/workflows/fmr-budget-chain.yml) builds the app and runs [`check_smoke.py`](../web/check_smoke.py) against the checked-in bundles. |

**Commands**

```bash
python3 data_formalization/scripts/export_web.py --program fmr  # rebuild bundles
cd web && npm install        # first run
CHOKIDAR_USEPOLLING=1 npm run dev   # http://localhost:5180/ (HMR)
npm run build && npm run preview    # production check (dist/)
```

`CHOKIDAR_USEPOLLING=1` is required in sandboxed environments where inotify
returns EMFILE — including Vite's own config watcher, which starts before
`server.watch` options apply. Outside a sandbox plain `npm run dev` works.

### 1.2 Locality stamped at the source (drill-down counts match)

The first grouping panel guessed municipality by regex-matching titles in
the browser; Guimba's drill-down showed 30 chains while the table said 28.
The exporter now parses `province` + `municipality` per record and the
Explorer filters on the exact field — 28 = 28, always in sync.

Parser details (`locality_of` in `export_web.py`):

- Province hints list (~60 provinces) validates the last comma-part.
- Senate titles print coordinates *after* place names
  (`"...Ilocos Norte Section 2: 120.607, 18.195..."`); coordinate tails are
  stripped and parsing falls back to the plain record title.
- Highly-urbanized cities (`Baguio City`, `Zamboanga City`, `Laoag City`,
  …) are their own top-level unit and are checked **before** province
  hints — otherwise "Zamboanga City" falsely matches province Zamboanga
  and the barangay gets rejected as a municipality.
- OCR typos in the source PDFs are covered where seen (`lloilo`, `Cagaya
  de Oro`); 22 of 1,796 records remain unstamped (genuinely malformed
  titles, e.g. `Mabini Batangas` without a comma). Unstamped records stay
  visible in the Explorer; they only fall out of the grouping panel.

### 1.3 Per-stage actions (not just "Senate action")

Previously only Annex A-1 status (cut/realigned/renamed/…) was classified;
NEP→House and House→DA changes were buried inside drawer chips. The
exporter now stamps an `actions` object on every record:

| Stage | Key | Values (counts in FY2027 FMR export) |
|---|---|---|
| NEP → House | `nep_house` | carried (609) · house_insertion (355) · reinstated (76) · dropped (22) |
| House → DA draft | `house_da` | retain (287) · modified (165) · new (236) · dropped (253) · list_revision (81) · no_da (459) |
| House → Senate | `house_senate` | renamed (382) · cut (423) · realigned (154) · inserted (315) · reinstated (76) · raised (3) · reduced (2) · left_at_nep (22) · unchanged (419) |

- `unchanged` = a House road not listed in the change-only Annex A-1.
- `left_at_nep` = NEP-only road; it left the pipeline before the Senate.
- `no_da` = chain has no linked DA working-draft row (DA coverage is
  partial) — an explicit value so "missing" is filterable, not invisible.
- Senate insertion records carry `house_senate: inserted`; realignment
  delete+insert pairs show `realigned` on the House chain and `inserted`
  on the paired new row, joined by `replaces` / `restated_by`.

**UI surface**

- Explorer: one chip row per stage (any + each action with live counts,
  AND-combined across stages) plus an "Actions by stage" pill column
  replacing the old single Senate-action and DA-draft columns.
- Localities (grouping analysis): a stage picker decides which stage's
  action mix the bars + column header show; the header totals the chosen
  stage across all 591 municipalities.
- Detail drawer: unchanged behavior (Glance chips already described the
  transitions); the drawer additionally shows the stamped locality.

**Verified end-to-end:** Guimba drill-down 28 = 28; "house insertion"
filter → 355 chains; grouping bars switch with the stage picker; no
console errors; HMR applies edits without full reloads.

### Commits

| Commit | Content |
|---|---|
| `49c429d` | grouping analysis panel + municipality drill-down |
| `1d46d1e` | Vite + React migration; locality stamping; parser fixes |
| `8fe3a17` | per-stage actions (filters, pills, grouping stage picker) |

---

## Part 2 — Follow-up work

### 2.1 Follow-up shipped (23 November 2026)

1. **Dashboard KPIs** read the manifest's stage actions, match coverage,
   and latest validation results. House insertion lines total ₱5.969B.
   The House bill is ₱3.628B above the NEP after all changes.
2. **PSGC locality fallback** recovers 14 of the 22 previously unstamped
   chains by requiring an explicit municipality and province in the title.
   Those recovery counts describe the initial export. The grouping filter
   and sort follow the selected stage, and drill-down uses both province
   and municipality.
3. **Action legend** is available under the Explorer filters.
4. **Browser and build verification** runs in the FMR budget-chain CI
   workflow. Run `python3 web/check_smoke.py` after building and
   installing Playwright and Chromium. Add `--screenshot /tmp/fmr.png` to
   capture a screenshot independently of the IDE webview.
5. **Bundle splitting** loads the Sankey chart separately and only
   registers the ECharts modules it uses. The production build emits a
   261 kB entry script and a 417 kB chart chunk before compression.

### 2.2 Matching and data quality

See [FMR budget-chain edge cases](fmr_budget_chain_edge_cases.md) for the implemented matching
rules and the examples that motivated them. A loose substitution candidate
within 2 km remains evidence for review in `subst_candidates`. Treating these
candidates as a confirmed DA action is still open.

### 2.3 Architecture

1. **Multi-program support** — exporter is `--program fmr` only; HFEP /
   NIA / DPWH ledgers exist in `data_formalization/data/ledger/`. The UI
   needs a program switcher reading `manifest.json` per program.
2. **Deploy target** — decide whether the app ships via the existing
    GitHub Pages pipeline (`scripts/build_pages.py`) or its own Pages
    project; the build already emits a self-contained `dist/`.

### 2.4 FMR directory rename and NIA follow-on

The FMR app currently lives in `web/`. The proposed directory name is
`FMR-Provenance-Explorer/`. Update the exporter output path, CI path filters,
CI working directory and npm cache path, and documentation commands together
when moving it. Search for other references to the old path and rerun the
export, production build, and browser smoke checks from the renamed layout.

NIA already has a [ledger](../data_formalization/data/ledger/nia.jsonl),
[agency reconciliation extraction](../data_formalization/scripts/extract_nia_recon.py),
and [mapped Senate Annex A-3 rows](../Senate_report_data/data/derived/senate_annex_a3_nia_mapped.json).
These are the starting inputs for an NIA export and a similar explorer.
Use the [traceability guide](provenance_chaining_considerations.md)
to check workbook coverage, computed amounts, and link evidence before
defining the NIA view.


### Open questions

- Should `list_revision` count as churn? It changes text but not money;
  currently excluded from the churn figure.
- Should grouping-panel churn weight actions by peso delta rather than
  raw counts (₱ realigned vs ₱ cut)? The columns exist (`senate_m`,
  `senate_from_m`) but the sort is count-based.
