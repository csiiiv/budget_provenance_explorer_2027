# NIA PBC Drop — [POW FOR REVIEW] Program of Works Mapping

**Built:** 25 November 2026  
**Source (local):** `NIA_DATA/[POW FOR REVIEW] PROGRAM OF WORKS AND PICTURES/` (17 region folders; 1,583 files; 910 PDFs; 620 site images)  
**Source (Drive):** [PEOPLE'S BUDGET COALITION REQUIREMENTS](https://drive.google.com/drive/u/0/folders/1orH0hcmtfTuYRz4qdOBXwcYhIKk1Yt-m)  
**Target records:** NIA Senate hearing workbook project rows (`senate_nia_dataset.json`, 937 rows, submission titles)  
**Artifact:** [`data/program_of_works/pow_review_availability.json`](data/program_of_works/pow_review_availability.json)  
**Extractor:** [`data/program_of_works/extract_pow_review_availability.py`](data/program_of_works/extract_pow_review_availability.py)  
**Tests:** [`tests/test_pow_review_availability.py`](tests/test_pow_review_availability.py)  

Follow-up to the first PBC POW mapping ([POW_AVAILABILITY_FINDINGS.md](POW_AVAILABILITY_FINDINGS.md), 62 packages → 61 Senate rows, Nov 12 2026). The FOR REVIEW drop is ~25× larger and nests deeper.

---

## 1. Coverage scale (current extract)

| Bucket | Senate submitted projects | vs first drop |
|---|---:|---:|
| With POW | 491 | 61 |
| With geotagged photos | 249 | 34 |
| No supporting docs in drop | 434 | 876 |

649 packages; match strength after guards: **553 strong / 84 weak / 11
unmatched / 1 review**. Only strong matches attribute coverage. Absence of a
package means it was missing from this PBC upload — not that no POW exists.

## 2. How the drop is parsed

Folder names carry `work-type / system / amount`, one level deeper than the
first drop: `REGION → IMO or province → category → project`. Layouts vary by
region (see [data/program_of_works/README.md](data/program_of_works/README.md)
for the table). Category-only folders (including allocation-group folders
like `120M - SPIP` whose children are individual 60M/5M projects) expand to
their children; picture sheets attach to the sibling document groups.

## 3. Matching: filename score, then PDF confirmation

Region-scoped scoring on system name + amount + category hint, plus two new
signals from the deeper layout:

- **Province boost** from IMO/province folder names (Cagayan-Batanes IMO →
  Cagayan rows).
- **Acronym expansion** for one-token systems (`VIS` → Visitacion
  Irrigation System) via an unambiguous acronym index built from Senate
  base-title heads; full credit requires the amount to agree.

Weak/unmatched packages are re-checked against POW PDF text (native layer;
tesseract OCR when installed — this machine has no tesseract, so
image-only POWs rely on filenames). PDF confirmation can promote to strong.

### Guards added after validation

| Guard | Case it fixed |
|---|---|
| Amount veto (≥2× / ≤0.5×) on filename and PDF confirmation | Pantingan SRIP ₱200M POW attaching to a ₱20M SPIP row via a ₱20.07M cost-line; MARIIS EPIP packages attaching to Magat sheetpile rows |
| Exact-amount override only | Cabiao WIP ₱500M not PDF-confirming onto PDRIS ₱200M via generic words |
| Generic site-word filter | `water`, `ground`, `diversion`, `sitio` … can no longer confirm identity alone |
| Title-evidence requirement for amount-based strong | `DRIS` (Dummun) not sliding to a Visitacion row that shares ₱3M; `Resurreccion SPIP` demoted (no Senate row exists) |
| Conflict resolution per Senate row | Padada RIS 4M/10M split correctly; r1795 keeps only the ₱20M package |

## 4. Validation anchors

Calibration anchors from the first drop all hold: LARPIS/Aupagan ₱300M →
sen:r1456; Bantog SPIP → sen:r1874; Consuelo CIS → sen:r740; Labangan RIS
₱200M → sen:r414 (the ₱10M resto package maps to the ₱10M Labangan row
sen:r628 — two distinct folders, two distinct rows). Random strong samples
show name+amount alignment (see tests).

## 5. Known limits

- **OCR absent** — image-only POWs (e.g. some Region 11/Kidawa PDFs) confirm
  on filenames only; install tesseract to enable OCR promotion.
- **Region 4A weak cluster** — `QIP-LAT-A-*` chainage-fragment folders and
  similar plan-file names score weak; they are plans of matching systems but
  not full POW packages.
- **MARIIS EPIP packages** (D1–D4 solar EGPIPs) largely have no Senate
  counterpart in this workbook; they stay weak rather than being attributed.
- Matches remain triage labels, not certified identity.

## 6. Rebuild

```bash
# defaults to NIA_DATA/[POW FOR REVIEW] PROGRAM OF WORKS AND PICTURES
# export NIA_POW_ROOT=/path/to/…  to point elsewhere
python3 analysis-nia/data/program_of_works/extract_pow_review_availability.py
python3 -m unittest analysis-nia.tests.test_pow_review_availability -v
```

The artifact keeps the `pow_availability.json` schema (schema_version 1), so
the PBC-NIA-APP document-availability view can render it by repointing its
fetch (`NiaApp.jsx` → `analysis-nia/data/program_of_works/…json`) or by
adding a drop selector.
