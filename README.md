# FY2027 budget provenance explorers

Explore how Farm-to-Market Roads (FMR), National Irrigation Administration
(NIA), and Department of Public Works and Highways (DPWH) budget items changed
across the Philippine FY2027 budget process. The three explorers share a
React/Vite app and use program-specific data exports.

## Run locally

Run these commands from this folder. Use Node.js 22 or newer and npm.

```sh
npm --prefix web ci
npm --prefix web run dev
```

| Program | Local URL | Evidence and matching |
| --- | --- | --- |
| FMR | http://localhost:5180/ | [Budget-chain notes](docs/fmr_budget_chain_web.md) · [Matching edge cases](docs/fmr_budget_chain_edge_cases.md) |
| NIA overview | http://localhost:5180/nia.html | Landing page for all five NIA analysis tools |
| NIA provenance | http://localhost:5180/nia-provenance.html | [Explorer notes](docs/nia_provenance_explorer.md) · [Workbook review evidence](docs/nia_review_data_sources.md) |
| NIA titles | http://localhost:5180/nia-titles.html | Side-by-side titles across NEP · House · workbooks · Senate |
| NIA document coverage | http://localhost:5180/nia-documents.html | Workbook-level POW/picture coverage, regional breakdowns, package matching, CSV exports |
| NIA coordinate coverage | http://localhost:5180/nia-coordinates.html | Senate funding vs. coordinate evidence, exceptions, regional breakdown and CSV |
| NIA map | http://localhost:5180/nia_map.html | Workbook site coordinates on an interactive map |
| DPWH | http://localhost:5180/dpwh.html | [Explorer notes](docs/dpwh_provenance_explorer.md) |

Read the methodology and download the original guides at
http://localhost:5180/about.html.

Build the explorer pages and About page with `npm --prefix web run build`. Serve
`web/dist/` as a static site at the host root, or run
`npm --prefix web run preview` locally.

### GitHub Pages

Pushes to `main` that touch `web/` (or the deploy workflow) build `web/dist/`
and publish it via GitHub Pages. After the first successful run, the site is
at `https://csiiiv.github.io/budget_provenance_explorer_2027/` (FMR index,
`nia.html`, `nia-provenance.html`, `nia-titles.html`, `nia-documents.html`, `nia-coordinates.html`, `nia_map.html`, `dpwh.html`). The Vite `base`
is `./` so asset paths work under the project-pages subpath.

## Regenerate explorer data

The three exporters run with Python 3.12 and its standard library. The
bundled data under `web/public/data/` lets you build the frontend before
running them.

```sh
python3 data_formalization/scripts/export_web.py --program fmr
python3 data_formalization/scripts/export_nia_web.py
python3 data_formalization/scripts/export_dpwh_web.py
npm --prefix web run build
```

FMR and NIA also export downloadable CSVs, full JSON and SHA-256 checksums
under `web/public/data/export/`. DPWH publishes its browser bundle as
`web/public/data/dpwh.json`.

## Evidence and source layout

- `data_formalization/` holds the three ledgers, lineage manifests and
  registry, web exporters, and ledger tooling. Registry nodes are scoped to
  the included programs and their shared Senate import.
- `analysis/`, `analysis-nia/`, and `other-analysis/` hold the retained
  project snapshots, workbenches, comparison data, and review evidence.
- `Senate_report_data/`, `NIA_DATA/`, `DA_FMR_DATA/`, the House and NEP PDF
  folders, and `dpwh_HGAB_REVIEW_SET/` hold source documents and supporting
  evidence. `PSGC2LEG/` supplies the FMR locality lookup.
- The [build guide](docs/provenance_explorer_build_guide.md),
  [chaining guide](docs/provenance_chaining_considerations.md), and
  [UI/UX guide](docs/provenance_explorer_ui_ux.md) describe shared conventions.

### Not in git (no LFS)

To keep the repository lean, large source and derived artifacts are
gitignored rather than stored with Git LFS:

- `NIA_DATA/[POW FOR REVIEW] PROGRAM OF WORKS AND PICTURES/` — the 8.2G PBC
  Program of Works drop. Its inventory and project attribution live in
  `analysis-nia/data/program_of_works/pow_review_availability.json`; the
  upstream folder is the
  [PBC Google Drive](https://drive.google.com/drive/u/0/folders/1orH0hcmtfTuYRz4qdOBXwcYhIKk1Yt-m).
- House bill PDFs, the 72M OCR'd NEP volume, the DPWH review-set CSVs, the
  80M DPWH ledger, and a handful of >20M derived JSON/CSV bundles — see
  `.gitignore` for the full list; each is re-acquirable upstream or
  regenerable with the exporters in this repo.

The standalone build starts from retained snapshots. Upstream extraction
and ledger maintenance scripts are included for reference. Historical
pipeline commands can require additional original-repository inputs,
including the PSGC geometry submodule for NIA boundary work, and Python
packages such as openpyxl, PyMuPDF, and pdfplumber.

The copy uses the source working tree, including local edits. Lineage
verification currently reports four inherited hash mismatches for the two
FMR DA draft extracts and the raw and mapped Senate Annex A-4 snapshots.
The registry retains the original recorded hashes.

## Browser smoke checks

After building, install Playwright 1.55.0 in your Python environment.
The checks use Google Chrome at `/usr/bin/google-chrome` when available.
Otherwise install Chromium with `python3 -m playwright install chromium`.

```sh
python3 web/check_smoke.py
python3 web/check_dpwh_smoke.py
```
