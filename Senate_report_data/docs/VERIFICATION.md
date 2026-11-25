# Senate report dataset verification

Verified 2026-11-22, from the source PDFs in `data/senate_pdf/`.

**Verdict: the bettergov senate-2027 dataset passes independent verification.
35/35 blocking checks and 1 advisory check pass; 0 failures.** Every control
total the annexes print reconciles exactly with the dataset's aggregates;
page-citation sampling finds every cited row; the only string-check misses
are three individually-investigated print artifacts, documented below.

```
python3 scripts/verify_senate_dataset.py --sample 40
# 36 checks: 35 passed, 0 failed (blocking), 1 passed (advisory)
```

## What was verified, and how

### 1. Byte integrity (17 checks)

- All 8 source PDFs match the SHA-256 pins in the dataset's `manifest.json`
  (the pins also match budget-assets.bettergov.ph published copies).
- All dataset CSV/parquet/README/manifest files match `SHA256SUMS.txt`.

### 2. Control totals, re-extracted from the PDFs (14 checks)

Totals were **independently re-extracted** from the annex PDFs (see
Extraction method) and compared against dataset aggregates — no reuse of the
colleague's build code:

| Annex | Printed | Dataset aggregate | Result |
|---|---|---|---|
| A-1 FMR program | ₱19,628,100,000 house → ₱16,000,000,000 committee | identical | PASS |
| A-1 FMR regions | 16 REGION rows (house, committee) pairs | multiset-identical | PASS |
| A-2 HFEP | grand total ₱5,491,400,000 = senate − house | 10,021,659,000 + 5,491,400,000 = 15,513,059,000 | PASS |
| A-3 NIA | ₱17,999,305,000 → ₱17,748,181,000 | identical | PASS |
| A-4 DPWH operations | ₱587,075,661,000 → ₱520,876,384,250 | identical | PASS |
| General Summary | TOTAL NEW ₱4,605,253,699,000; 43 department rows | row-wise identical | PASS |
| General Summary | printed internal arithmetic (house + net = committee) | holds | PASS |
| Row arithmetic | `vs_house_php`, `vs_nep_php` columns | 0 mismatches in 20,835 rows | PASS |

### 3. Page-citation sampling (2 checks, 252 sampled rows)

A deterministic, stratified sample (40 rows per status class) was checked
against the cited Senate annex page: the project title and its Senate amount
must appear on that page. **252 titles, 0 unexplained misses; 252 amounts,
0 misses.** Three title misses were individually investigated and are
documented exceptions, not dataset errors:

| Row | Symptom | Investigation finding |
|---|---|---|
| `house-reading:13` (DPWH p209) | title not string-matched | A-4 prints this row as **struck-through text overlapped by its replacement**; PyMuPDF span extraction shows the clean title (`Pasig - Marikina River Channel Improvement Project (PMRCIP), Phase IV…`) at y≈612 with the amount on the same page. The dataset cites the correct row. |
| `ib:p886:r38` (HFEP p3) | "North Samar" not found | The annex prints **"Northern Samar"** Provincial Hospital; the dataset normalizes the province name. Row present. |
| `ib:p888:r43` (HFEP p5) | "Sanitarium" not found | **Print defect in the PDF itself**: the facility name truncates to "Sanitar iu" (missing final m). The dataset spells it fully. Row present. |

These live in `KNOWN_EXCEPTIONS` in the script — each carries its evidence.
Any *new* page-citation miss remains a blocking failure.

## Extraction method

The 8 PDFs are heterogeneous (checked via `pdfinfo`):

| Producer | Files | Notes |
|---|---|---|
| Adobe Acrobat (tagged) | Annex B | best structure |
| Microsoft Excel 365 (tagged) | A-2 HFEP, General Summary | letter-spacing artifact (see below) |
| Microsoft Word 365 (tagged) | A-5 | clean |
| macOS Quartz (from Excel) | A-1 FMR | untagged; two description columns |
| OpenPDF | Annex A | programmatic, clean text runs |
| iLovePDF | A-3 NIA | re-processed wrapper |
| PScript5 → Ghostscript 9.06 | A-4 DPWH | print-to-PDF; strikethrough overlays |

Extraction pipeline (`scripts/verify_senate_dataset.py`):

1. **pdfplumber word extraction** with `x_tolerance=3` — merges the Excel
   export's per-glyph positioning that pdftotext renders as spurious spaces
   (`Br g y Fab r ica` → `Brgy Fabrica`). Words carry coordinates
   (`x0`, `top`), enabling row banding and future cell-level provenance.
2. **Stratified title match**: squashed-string containment (whitespace,
   commas, hyphens, case folded — tolerates letter-spacing and hyphenation
   line breaks), then a two-run interleave test (two-column wrap artifacts),
   then ±1 page boundary tolerance (recorded separately).
3. **Amount match**: the Senate figure directly, or the delta-over-house
   (HFEP annexes print increases, not finals), or parenthesized decreases;
   struck-through A-4 rows fall back to a digit-multiset match.
4. Falls back to `pdftotext` raw mode if pdfplumber is unavailable.

Dependencies: `pdfplumber`, `pymupdf`, `pyarrow` (user-install:
`pip install --user --break-system-packages pdfplumber pymupdf pyarrow`;
this box's system pip is PEP 668-blocked and `python3-venv` is missing).
`pdftotext`/`pdfinfo` from poppler-utils are used for fallback and metadata.

## Known limitations

- Page-citation checks verify that title and amount **appear on the cited
  page**, not their exact table cell. A coincidence with another figure on
  the same page would pass (bounded by totals checks, but not zero).
- Sampling is 252 of 20,835 rows (~1.2%), stratified by status class.
  Full-population citation checks would take ~30× longer.
- The Advisory check (`A-4 DPWH department house row`) confirms the annex
  prints the department total ₱654,102,015,000 while the dataset correctly
  aggregates only the OPERATIONS program (₱587,075,661,000) — documented,
  not a mismatch.

## Files

- `scripts/verify_senate_dataset.py` — the verifier (re-run any time)
- `docs/verification_report.json` — machine-readable results, including
  sample composition, boundary wraps, known exceptions, and every check
- `docs/CROSS_COMPARISON.md` — their 38 build checks vs. our 36 re-verification
  checks, side by side, including the independent diagnosis of their one
  advisory failure
- `docs/EDGE_CASES.md` — ledger of every edge case with page numbers, source
  PDFs, and root causes (print defects, layout artifacts, normalizations,
  upstream OCR)
- `data/senate_pdf/` — the 8 source PDFs (sha-verified)
- `data/bettergov-senate-2027-dataset/` — the colleague's dataset as shipped
