# Verification cross-comparison: their checks vs. our re-verification

Compared 2026-11-22. Sources:

- **Theirs**: `data/bettergov-senate-2027-dataset/senate-2027-dataset/senate-2027-checks.csv`
  (38 checks run by their build; 37 pass, 1 advisory fail)
- **Ours**: `docs/verification_report.json` (36 checks run by
  `scripts/verify_senate_dataset.py`; 35 pass + 1 advisory pass, 0 failures)

## Headline

Both validation suites agree. Every control total both sides check reconciles
identically. Their single advisory failure is confirmed by our independent
extraction to be a **defect in the NEP OCR source**, not in their pipeline.

## Check-by-check comparison

### Integrity — identical conclusion, different anchors

| Aspect | Theirs | Ours |
|---|---|---|
| PDF sha256 | 8/8 pass — vs. **published budget-assets copies** | 8/8 pass — vs. **manifest pins** (and all dataset files vs. SHA256SUMS.txt) |

Complementary: they prove the PDFs match what they published; we prove the
copies in this repo match what they pinned. Together: the local PDFs are the
Senate's bytes.

### Program totals — exact agreement on every overlapping figure

| Annex | Figure | Theirs | Ours |
|---|---|---|---|
| A-1 FMR | House ₱19,628,100,000 | PASS | PASS |
| A-1 FMR | Senate ₱16,000,000,000 | PASS | PASS |
| A-2 HFEP | House ₱10,021,659,000 | PASS | PASS |
| A-2 HFEP | Senate ₱15,513,059,000 | PASS | PASS (via house + printed grand total) |
| A-3 NIA | House ₱17,999,305,000 | PASS | PASS |
| A-3 NIA | Senate ₱17,748,181,000 | PASS | PASS |
| A-4 DPWH | House ₱587,075,661,000 | PASS | PASS |
| A-4 DPWH | Senate ₱520,876,384,250 | PASS | PASS |

### Row arithmetic — same property, different scope

- Theirs: `house + change = senate` per project (blocking, full population —
  16,272 DPWH, 1,177 FMR, 728 HFEP, 940 NIA rows pass) plus Annex A row
  arithmetic (1,986 + 2,705 rows).
- Ours: `vs_house_php` / `vs_nep_php` column identities across all 20,835
  rows. Equivalent conclusions.

### Page links — complementary coverage

- Theirs: **full population** (e.g. 8,712 DPWH senate-page links, 16,271
  house, 11,419 NEP), counting title-found-on-page per link. Result: all
  pass except one advisory.
- Ours: **stratified sample** (252 rows) but against our *independent*
  extraction (pdfplumber word coordinates), also verifying the **senate
  amount** appears on the page — a dimension their checks don't cover.
  Result: 0 unexplained misses; 3 documented print artifacts.

### General Summary — same totals, different angles

- Theirs: agencies→department rollups (35), departments+SPF=programmed,
  programmed+unprogrammed=total, Annex-A lines→GS departments (43).
- Ours: csv total row and all 43 department rows vs. our re-extraction of
  the printed PDF; printed internal arithmetic. Same numbers.

## Their one failure, independently diagnosed

> `DOH HFEP (Annex A-2): NEP page links print their project — ours 560, printed 562` (advisory)

Their two misses are `nep_hfep:p10:r16|infrastructure` and
`|medical_equipment`, garbled title `cYanmGtalo Tab]`. **Our own NEP HFEP
extraction** (`analysis-hfep/data/nep_hfep_source_rows.json`) contains the
same row with the same garbled `label_raw: "cYanmGtalo  Tab]"` and clean
amounts (infrastructure 10,000,000 · medical 30,000,000 · total 40,000,000).
Two independent pipelines reading the same NEP OCR page produce the same
garbling — the defect is in the **NEP PDF's OCR text layer**, not in their
build. Correctly classified by them as advisory (non-blocking).

## What each side caught that the other didn't

| Finding | Caught by | Notes |
|---|---|---|
| Senate amount present on cited page (sampled) | **ours only** | their page checks are title-only |
| A-4 struck-through rows cite correctly (`house-reading:13`) | **ours only** | span-level analysis; their title check also misses overlaid strikethrough, so they must handle it elsewhere |
| "Northern Samar" → "North Samar" normalization | **ours only** | cosmetic normalization on their side; consistent with their README ("names as printed" has documented exceptions) |
| NEP OCR garble at `nep_hfep:p10:r16` | **theirs only** (as page-link miss) | full-population coverage surfaced it; we confirmed the root cause |
| Annex A multi-level double-count hazard | **theirs only** (README + arithmetic checks) | their annex-a file keeps rows "as printed"; we didn't independently verify Annex A row-by-row |

## Residual risk (both suites)

- Neither side does exact cell-coordinate matching of title↔amount; both use
  string/word containment on the cited page. (Our pdfplumber upgrade keeps
  coordinates, so tightening this is now possible.)
- Their `under_citizen_review: true` flag remains open on the dataset node;
  the two HFEP page-misses should be recorded as review items against the
  **NEP snapshot** in the lineage model, not against this dataset.

## Verdict

The colleague's dataset passes both its own validation and our independent
re-verification. The one advisory failure is a source-OCR defect, confirmed
by two independent extractions. No blocking issues. The dataset is safe to
use as the Senate-stage import under the data-formalization model.
