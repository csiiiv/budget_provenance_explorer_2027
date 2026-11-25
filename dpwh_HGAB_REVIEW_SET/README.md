# DPWH projects in the FY2027 House bill: documents and red flags

Built 2026-11-15 by budget.bettergov.ph (`npm run build:hgab-review-dataset`). Project reviewer: https://budget.bettergov.ph/hgab/2027/review

Independent and unofficial: our reading of the published documents, not an official record. Amounts are as published, not spending. A red flag is a reason to look, not a finding, and a document tied to a project is a match that can be wrong.

## What's here

- 15,979 DPWH projects in the House bill (HB 10858, third reading, Vol. I-C), ₱540,798,450,000 in all.
- 69,085 documents tied to them: 22,748 Senate copies (20,575 redacted, with a link) and 46,337 DPWH Transparency files.
- 90,285 red flags.

Not here: volunteers' reviews of the projects, which are not published. Join the three files on `hgab_id`.

## Sources

- House Bill 10858, General Appropriations Bill FY2027, third reading, Vol. I-C (Senate Budget Transparency Portal); copies at budget-assets.bettergov.ph/hgab/2027/pdf/.
- research.bettergov.ph (nep-preview): document coverage, red flags and DPWH Transparency records for every House bill DPWH row.
- The documents DPWH gave the Senate for the House bill ("Senate copies"), listed in supporting-documents-file-links.jsonl on budget-assets.bettergov.ph.
- DPWH Transparency (s3.infrawatch.ph): DPWH's documents for its NEP proposals.
- Documents and flags as built 2026-11-13; Senate redaction status as of 2026-11-15.

## Conventions

- Amounts are integer pesos. An empty cell means none or not known, not zero.
- Names and titles are as published, including the documents' own spelling.
- CSVs are UTF-8 with a byte-order mark, comma-separated. The Parquet files hold the same rows with their types (whole numbers, true/false).
- Lists inside a cell are separated by "; " (evidence by " | ").
- Signatures and handwriting in the Senate copies are being redacted for privacy, region by region. Until a copy is redacted its row has `redacted` false and no link. Redacted copies replace the originals at the same address.
- A region whose redacted copies are still being checked is held back: its copies have no link yet. Held back on 2026-11-15: none.
- `matched_by` says how a file was tied to its project (see the documents file's columns). `reviewed` means we settled a disputed folder by reading its program of work; it has nothing to do with volunteers' reviews.

## Files

### house-bill-2027-dpwh-projects.csv (also house-bill-2027-dpwh-projects.parquet)

Every DPWH project in the FY2027 House bill (HB 10858, third reading, Vol. I-C), one row each, with the documents found for it and its red flags. No review data. 15,979 rows.

| Column | Meaning |
| --- | --- |
| `hgab_id` | The project's row in the House bill: HB10858-3-<PDF page>-<row>. Stable; join the other files on it. |
| `bill_pdf_page` | PDF page of Vol. I-C that prints the project. |
| `bill_row` | Row number in the bill's DPWH list. |
| `title` | Project title, as published. |
| `amount_php` | Amount in the House bill, in pesos. |
| `region` | Region, as the bill groups the project. |
| `dpwh_office` | DPWH implementing office (district engineering office, regional office or Central Office). |
| `office_scope` | lone_district: the office serves one legislative district; shared_districts: several; no_district: Central Office or a regional office. |
| `legislative_districts` | Legislative districts the office serves, separated by "; ". Where the office serves several, the project is not split among them. |
| `program` | DPWH program. |
| `pap` | Program, activity or project line it sits under. |
| `house_insertion` | true when our comparison finds the project in the House bill only, not in the NEP: a candidate insertion, not a finding. |
| `red_flags` | How many red flags the project has (rows in the red-flags file). |
| `red_flag_codes` | Its red-flag codes, separated by "; ". |
| `key_documents_found` | How many of the five key documents were found: program of work, BP 202, development council endorsement, geotagged photos, certificate of implementability. |
| `has_pow` | Program of work found. |
| `has_bp202` | BP 202 (project profile) found. |
| `has_development_council` | Regional or local development council endorsement found. |
| `has_geotagged_photos` | Geotagged photos found. |
| `has_certificate_of_implementability` | Certificate of implementability found. |
| `senate_files` | Documents DPWH gave the Senate for this project (Senate copies). |
| `senate_files_redacted` | Of those, how many have had signatures redacted (the ones with a link in the documents file). |
| `dpwh_transparency_files` | Documents DPWH published for its NEP proposal, on DPWH Transparency. |
| `dpwh_proposal_code` | DPWH Transparency proposal code paired with the project (2027DPWH-Proposal-…). |
| `house_bill_pdf` | The House bill page that prints the project. |
| `project_page` | The project's page on budget.bettergov.ph: NEP and House bill side by side. |
| `reviewer_page` | The project in the project reviewer, with its documents. |

### house-bill-2027-dpwh-documents.csv (also house-bill-2027-dpwh-documents.parquet)

Every document tied to a project: the Senate copies (documents DPWH gave the Senate for the House bill) and DPWH Transparency files (DPWH's documents for its NEP proposals). A file can be tied to more than one project. 69,085 rows.

| Column | Meaning |
| --- | --- |
| `hgab_id` | The project (projects file). |
| `source` | senate_copy or dpwh_transparency. |
| `folder_code` | The folder: 2027DPWH-HGAB-… for Senate copies (DPWH's numbering, not the bill row), 2027DPWH-Proposal-… for DPWH Transparency. |
| `document_type` | POW, BP 202, Development Council, Geotagged photos, Certificate of Implementability, or Other. |
| `label_in_source` | The type as the source labels it. |
| `file_name` | File name. |
| `earlier_copy` | true for an earlier copy kept beside the current one. |
| `matched_by` | How the file was tied to the project: research (matched by research.bettergov.ph); pow_title (its program of work names this project); tracker (listed for this project by DPWH Region IV-A); reviewed (checked by reading its program of work); proposal (dPWH Transparency record paired with this project). tracker is the weakest. Matches can be wrong. |
| `redacted` | Senate copies: true once signatures and handwriting are redacted. Empty for DPWH Transparency files. |
| `url` | Where to get the file. Senate copies have one only once redacted (and their region isn't held back while it is checked). |
| `bytes` | Senate copies: size of the file served today. |
| `sha256` | Senate copies: SHA-256 of the file served today. |
| `senate_file_id` | Senate copies: the file's id in the Senate file list. |

### house-bill-2027-dpwh-red-flags.csv (also house-bill-2027-dpwh-red-flags.parquet)

Every red flag on every project: research.bettergov.ph's, and ours (missing documents after our matching; our NEP comparison). A red flag is a reason to look, not a finding. 90,285 rows.

| Column | Meaning |
| --- | --- |
| `hgab_id` | The project (projects file). |
| `flag_code` | Stable code of the flag. |
| `flag` | The flag, in words. |
| `family` | Kind of flag: documents (Documents), nep (NEP comparison), cost (Amount and cost), location (Location and map), history (Repeats and history). |
| `source` | research.bettergov.ph, or budget.bettergov.ph for ours. |
| `value_php` | An amount the flag is about, in pesos, where it has one. |
| `evidence` | The source's evidence or note for the flag; several separated by " \| ". |

### house-bill-2027-dpwh-dataset.zip

The three CSVs and this README in one file.

## Licence and credit

Free to use, with credit to budget.bettergov.ph and research.bettergov.ph. The government documents are public records.
