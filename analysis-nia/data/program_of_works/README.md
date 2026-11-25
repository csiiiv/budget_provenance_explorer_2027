# Program of Works availability

Two PBC drops are inventoried and matched to the Senate workbook:

1. **PROGRAM OF WORKS AND PICTURES (ONGOING UPLOADING)** — the first,
   smaller drop. Artifact: `pow_availability.json` (built by
   `extract_pow_availability.py`).
2. **[POW FOR REVIEW] PROGRAM OF WORKS AND PICTURES** — the larger "FOR
   REVIEW" drop (1,583 files; 910 PDFs; shipped under `NIA_DATA/`). Artifact:
   `pow_review_availability.json` (built by
   `extract_pow_review_availability.py`).

Both are region-scoped fuzzy matches of parsed package names (work-type /
system / amount) against Senate workbook submission titles — triage
candidates, not certified identity.

**Upstream (Drive):** [PEOPLE'S BUDGET COALITION REQUIREMENTS](https://drive.google.com/drive/u/0/folders/1orH0hcmtfTuYRz4qdOBXwcYhIKk1Yt-m)  
**Method note:** [POW_AVAILABILITY_FINDINGS.md](../../POW_AVAILABILITY_FINDINGS.md)

## [POW FOR REVIEW] drop — layout handled

The FOR REVIEW drop nests deeper than the first one. The extractor expands
region → IMO / province → category → project:

| Layout | Regions |
|---|---|
| REGION → IMO → loose PDFs | REGION 6 |
| REGION → IMO → category → project dirs | CAR, REGION 1, 2, 5, 11 |
| REGION → category → project dirs | REGION 7, 9, 10, 12, 13 |
| REGION → category → loose PDFs + PICTURES dir | REGION 8 |
| REGION → province → category → project dirs | REGION 3 |
| REGION → category → DIVISION → loose PDFs | UPRIIS |
| REGION → category → loose PDFs | MARIIS |

Allocation-group folders (`120M - SPIP`, `50M - SPIP`, `454M - RESTO_REPAIR
NIS_CIS`, `LineProjects-SRIP`) expand to their per-project children instead of
forming one giant package. Photo sheets (`GEOTAGGED PICTURES.pdf`,
`PICTURES/` folders) attach to the folder's document groups.

## Matching additions over the first drop

- **Acronym expansion** — one-token system guesses (`VIS`, `BCIS`, `ZRIS`)
  expand via an unambiguous acronym index built from Senate base-title heads
  (e.g. VIS → Visitacion Irrigation System); full credit requires amount
  agreement.
- **Province boost** — IMO/province folders (Cagayan-Batanes IMO, BULACAN,
  PAMBAT IMO) add a small score boost when Senate province matches.
- **Amount veto** — filename amounts that contradict the Senate row (≥2× or
  ≤0.5×) block strong and PDF-confirmed matches; only an exact amount print
  in the PDF overrides.
- **Strong-only attribution** — only strong matches count toward coverage;
  weak/unmatched/review packages stay in the packages table.
- **Conflict resolution** — a Senate row that collected packages with
  mutually inconsistent amounts keeps only amount-consistent / PDF-confirmed
  packages; the rest are demoted to review.
- **Generic-word guard** — site words that appear in every POW form (water,
  ground, diversion, sitio …) cannot PDF-confirm an identity alone.

## Rebuild

```bash
# defaults to NIA_DATA/[POW FOR REVIEW] PROGRAM OF WORKS AND PICTURES
# override with NIA_POW_ROOT when the drop lives elsewhere
python3 analysis-nia/data/program_of_works/extract_pow_review_availability.py
python3 -m unittest analysis-nia.tests.test_pow_review_availability -v
```

Requires `pymupdf` for PDF-text confirmation (OCR via tesseract only when
installed).

## Artifact

`pow_review_availability.json` — same schema as `pow_availability.json`
(schema_version 1; `packages`, `projects`, `coverage`, `by_region`,
`summary.support_scale`). Loose-file groups suffix ` :: <group key>` to their
package id to stay unique within a folder.

## UI

The PBC-NIA-APP view Analysis → **Document availability** reads
`pow_availability.json`; point its fetch at `pow_review_availability.json`
(or add a drop selector) to browse this drop with the same controls.

The provenance-explorers **NIA Title Comparison** page
(`web/nia-titles.html`) renders a *Supporting docs* column: per-chain file
count with a PDF/photo breakdown, plus a link to each attributed package's
local folder path (`file://<source>/<package_path>`). The web exporter
(`data_formalization/scripts/export_nia_web.py`) joins `coverage` rows to
chains by Senate workbook row id (`sen:rNNNN`, the workbook rows on each
chain); the one agency-only chain resolves through its agency leaf's Excel
row. Tests: `analysis-nia/tests/test_nia_supporting_docs.py`, browser check
`web/check_nia_supporting_docs.py` (built bundle).

