# Senate verification — edge-case ledger

Every anomaly encountered while verifying the bettergov senate-2027 dataset
against the source PDFs (2026-11-22), with exact locations. Each case was
investigated at the PDF level; **none is a dataset error**. Class labels:

- **[print-defect]** — the PDF itself prints wrong/truncated/garbled content
- **[layout-artifact]** — the PDF's layout defeats naive text extraction
- **[dataset-normalization]** — the dataset intentionally differs from print
- **[source-ocr]** — defect inherited from the upstream NEP PDF's OCR layer

Source PDFs live in `data/senate_pdf/`; the dataset in
`data/bettergov-senate-2027-dataset/senate-2027-dataset/`.

---

## A-4 DPWH annex — struck-through replacement overlays

### 1. `house-reading:13` — PMRCIP Phase IV [layout-artifact]

- **PDF**: `Annex A-4 Details of DPWH's Programs-Projects (FY 2027 General Appropriations Bill Volume I-C).pdf` — **p. 209 of 210**
- **Row**: `Pasig - Marikina River Channel Improvement Project (PMRCIP), Phase IV, JICA Loan Nos. PHP271 and PH-P283` · 3,039,933,000
- **Symptom**: reading-order extraction garbles the row into
  `aa.nd PParsiingc -i pMaal rRikiivnea rRsiver Channel…` — two text runs
  interleaved character-by-character.
- **Root cause**: the annex prints some rows as **struck-through text with the
  replacement printed directly over it**. pdftotext (and any reading-order
  extractor) merges the overlapping spans.
- **Resolution**: PyMuPDF span extraction separates them — the clean
  replacement title sits at y≈612 (black, 5.3 pt), amount on the same page.
  The dataset cites the correct row. Recorded in `KNOWN_EXCEPTIONS`.

Similar struck-through rows exist elsewhere in A-4; any future extractor for
this annex must handle overlays (span/color/size disambiguation).

## A-2 HFEP annex — Excel export artifacts

### 2. Letter-spaced facility names throughout [layout-artifact]

- **PDF**: `Annex A-2 DOH Health Facilities Enhancement Program (HFEP).pdf` — all 5 pages (e.g. p. 1 `Br g y Fab r ica, San Vicen t e, Cam ar in es No r t e BHS`; p. 3 `Ro d r ig u ez`)
- **Root cause**: Excel 365 PDF export positions glyphs individually;
  `pdftotext` inserts spurious spaces. Producer: "Microsoft® Excel® for
  Microsoft 365" (tagged PDF).
- **Resolution**: pdfplumber `x_tolerance=3` merges the glyphs
  (`Brgy Fabrica, San Vicente, Camarines Norte BHS`). Our verifier uses this;
  any future extractor for A-2 / General Summary should too.

### 3. `ib:p886:r38` — "North Samar" vs printed "Northern Samar" [dataset-normalization]

- **PDF**: A-2 — **p. 3**, under the printed heading `Northern Samar`:
  `No r t h er n Sam ar Pr o vin cial Ho sp it al` · 106,150,000
- **Dataset title**: "North Samar Provincial Hospital" (medical_equipment)
- **Root cause**: the dataset normalizes the province name to its PSGC-style
  form. Cosmetic; row present, amounts verified.

### 4. `ib:p887:r25` — Kapalong prints the increase, not the final [dataset-normalization]

- **PDF**: A-2 — **p. 4**: `Davao d el No r t e Ho sp it al - Kap alo n g` with
  **15,000,000** printed
- **Dataset**: house 2,900,000 → senate 17,900,000 (status `raised`)
- **Root cause**: A-2 is an *amendment schedule* — it prints increases on top
  of the House figure, not final amounts. 2,900,000 + 15,000,000 =
  17,900,000. **Do not sum A-2's printed column as final HFEP amounts.**

### 5. `ib:p888:r43` — truncated "Sanitarium" [print-defect]

- **PDF**: A-2 — **p. 5**: `Dr . Jo se N. Ro d r ig u ez Mem o r ial Ho sp it al an d San it ar iu (100,000,000)` — final "m" missing in print
- **Dataset title**: "Dr. Jose N. Rodriguez Memorial Hospital and Sanitarium" (infrastructure, house 610,000,000 → senate 510,000,000)
- **Root cause**: the PDF's own print truncation. The dataset spells the name
  fully. Recorded in `KNOWN_EXCEPTIONS`.

## A-1 FMR annex — two-column layout artifacts

### 6. Interleaved GAB/Committee titles at wrap points [layout-artifact]

- **PDF**: `Annex A-1 DA Farm-to-Market Roads.pdf` — e.g. **p. 47**
  (`Construction of Brgy. Baloy FMR, Brgy. Baloy, Cuyapo, Nueva Ecija
  Construction of Brgy. Baloy FMR Phase II…`), **p. 110** (Manlingay row),
  and throughout the 148 pages
- **Root cause**: A-1 prints the 2027 GAB description and Committee Report
  description side-by-side; when either wraps, reading-order extraction
  interleaves fragments of both columns.
- **Resolution**: our verifier's `interleave_contains()` two-run test;
  pdfplumber word coordinates (x-banding) resolve the columns properly.

### 7. Region headers CAR/NIR print in long form [layout-artifact]

- **PDF**: A-1 — **p. 17** `CORDILLERA ADMINISTRATIVE REGION (CAR)` ·
  1,565,000,000 → 639,000,000; **p. 107** `NEGROS ISLAND REGION (NIR)` ·
  665,000,000 → 418,500,000
- **Symptom**: region-header matching that expects `REGION [IVX]+` or
  short-form `CAR`/`NIR` finds only 14 of 16 region rows.
- **Root cause**: two regions print their full names in the header row.
  (Dataset uses `CAR` and `NIR` as region labels — correct.)

## Upstream NEP — OCR defect

### 8. `nep_hfep:p10:r16` — garbled facility title [source-ocr] — RESOLVED

- **PDF**: the **NEP** HFEP annex (not in this folder; the dataset's page
  link points at budget-assets.bettergov.ph `nep2027-hfep.pdf` **p. 10**,
  printed p. 728, table row 16)
- **Symptom**: title garbles to `cYanmGtalo  Tab]`; the colleague's full
  -population page-link check reports it as 2 misses (560/562) — their only
  failing check (advisory).
- **Root cause**: defect in the NEP PDF's **OCR text layer**. Confirmed
  independently: our own NEP HFEP extraction
  (`analysis-hfep/data/nep_hfep_source_rows.json`) contains the same row
  with the same `label_raw: "cYanmGtalo  Tab]"` and clean amounts
  (infrastructure 10,000,000 · medical_equipment 30,000,000 · total
  40,000,000). Two independent pipelines, identical garble.
- **RESOLUTION (manual page read + `HFEP_2.pdf`, 2026-11-22)**: the true
  facility name is **"Governor Benjamin T. Romualdez General Hospital and
  Schistosomiasis Center"** (Leyte, Region VIII). Confirmed two ways:
  manual reading of the NEP page image, and
  `dbm-other-nep-line-data/HFEP_2.pdf` (clean text layer) which prints the
  identical block: Leyte → Eastern Visayas Medical Center → *Governor
  Benjamin T. Romualdez General Hospital and Schistosomiasis Center* →
  Samar. The garble `cYanmGtalo Tab]` is the OCR mangling of
  "…ualdez… Center" fragments.
- **Follow-up**: our `nep_hfep_*` extractions and the bettergov dataset all
  inherit the garbled text — the correction should be recorded as a
  **defect-repair edge on the NEP HFEP snapshot** in the lineage model
  (supersedes the garbled observation at the same locator), and
  `HFEP_2.pdf` noted as a cross-reference source for NEP HFEP title
  verification.
- **Find-it cheat sheet** (printed page 728, Leyte block):

  | # | role | label | amounts |
  |---|---|---|---|
  | r13 | region | Region VIII | |
  | r14 | province | Leyte | |
  | r15 | facility | Eastern Visayas Medical Center | med equip 80,000,000 |
  | **r16** | **facility** | **Governor Benjamin T. Romualdez General Hospital and Schistosomiasis Center** (OCR: `cYanmGtalo Tab]`) | 10,000,000 / 30,000,000 / 40,000,000 |
  | r17 | province | Samar | 80,000,000 / 100,000,000 / 180,000,000 |

  The row is the last facility under Leyte, immediately above the Samar
  province subtotal.

## Extraction guidance by producer (summary)

| Producer | Files | Handle with |
|---|---|---|
| Adobe Acrobat (tagged) | Annex B | straightforward |
| Excel 365 (tagged) | A-2, General Summary | `x_tolerance=3`; increases-not-finals semantics (A-2) |
| Word 365 (tagged) | A-5 | straightforward |
| macOS Quartz (Excel) | A-1 | word x-banding for the two description columns |
| OpenPDF | Annex A | clean text runs; respect `kind`/`is_total_row` semantics |
| iLovePDF | A-3 | clean |
| Ghostscript (PScript5) | A-4 | span-level extraction; struck-through overlays |
| (upstream NEP OCR) | nep2027-hfep p10 | defect at r16 RESOLVED: Gov. Benjamin T. Romualdez GH & Schistosomiasis Center; `HFEP_2.pdf` is a clean cross-reference |
