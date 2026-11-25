# FMR budget-chain edge cases

The Explorer presents road chains. The exported source records and drawer
keep the sheet controls, Senate annex row IDs, and original actions
available for tracing a match. A paired Senate source row can be opened from
the drawer or by exact annex ID.

For the general model, evidence standards, and verification workflow, see
[Chaining budget records for traceability](provenance_chaining_considerations.md).

## Evidence used for linking

- **Exact DA to Senate match.** Require a unique match on region, normalized
  title, amount in pesos, and both ordered endpoints. Endpoint matching
  ignores trailing decimal zeros. The Explorer shows the DA proposal and
  Senate action on the same chain. Agreement documents what appears in
  both sources. The Senate’s decision process remains unverified.
- **Possible DA to Senate match.** A unique DA proposal and Senate insertion
  agree on region, amount, and both endpoints, with different normalized
  titles. The Explorer groups them on one labeled row and shows both
  amounts. Each source record retains its own title and action. Use the
  drawer links to inspect the difference in scope.
- **Title or GPS clue.** A title-only or GPS-only match is weaker evidence.
  It remains a drawer clue and has a separate Explorer filter. A shared
  barangay, nearby road, or single common endpoint can justify review.
- **DA-documented replacement.** A unique review-annex replacement control
  connects a dropped original to a DA correction. The correction and
  Senate insertion must agree on region, normalized title, amount, and all
  endpoints. This applies across municipalities. The combined row shows
  **DA-documented replacement** and **Possible Senate restatement**.
- **Title correction documented in both DA drafts.** When the review annex
  has no explicit replacement control, a consecutive Senate cut and
  insertion can still be grouped. They must be the unique pair with the
  same region, amount, and endpoints. In each DA draft, the list revision
  must immediately follow the dropped original, explicitly say it corrects
  the title, and agree with the Senate amount and endpoints. The Nov 12
  proposal also matches the Senate insertion by normalized title. The
  drawer identifies the DA workbook rows as the evidence for the pairing.
- **Possible Senate restatement from adjacent annex rows.** A unique cut
  and insertion appear consecutively and agree on region, amount, and
  endpoints. The insertion extends the original route title. This is
  enough to group the rows for review with the **Possible Senate
  restatement** warning.

For all possible Senate restatement paths, the Explorer counts one chain
under the original road’s municipality and shows the paired insertion
amount in the Senate column. When a DA correction is linked, the DA column
shows the corrected proposal and the DA drawer preserves the dropped
control. The Senate drawer shows both source actions and amounts, with a
link to the insertion. The Senate actions filter includes **Possible
restatement**, and the insertion’s exact annex ID still opens its source
row. Source-level Senate totals continue to use the original annex rows.

## Roads that exposed matching gaps

| Case | What the sources showed | How the app handles it |
| --- | --- | --- |
| **Cabungaan A and B, Laoag City** | Each original road carried ₱5M. DA dropped the original titles and issued list revisions. The Senate cut and reinserted each road with its own matching endpoints. North and South have different endpoints. | Each road has its own House chain. The drawer retains the original DA drop and revised control. Search `cabungaan` for two chains, or `cabungaan north` for A. A links `R1-0046`, `R1-L-0006`, and `senate_a1:p7:r59`. B links `R1-0047`, `R1-L-0007`, and `senate_a1:p7:r61`. |
| **Sitio Rango, Tubburan, Bacarra** | The original ₱15M line was dropped in DA, and `R1-NEW-0001` was classified as new. Its remark documents a GPS correction. The corrected endpoints match Senate insertion `senate_a1:p1:r3`, paired with cut `senate_a1:p1:r2`. | The general correction rule links the DA replacement to the existing realignment on `ib:p667:r5`. Both DA stops say **Coordinate correction**. The drawer shows original and revised endpoints. This correction has no review-annex flag entry. |
| **Bobonan–Nama–Palacpalac, Villasis → Bobonan, Pozorrubio** | The review annex flags a location mismatch and names `R1-NEW-0006` as the replacement for `R1-0018`. The corrected DA proposal matches the ₱15M Senate insertion `senate_a1:p16:r144` on title, amount, and endpoints. | Search `bobonan` for one chain anchored to the Villasis cut `ib:p668:r2`, with ₱15M in both DA and Senate and the possible restatement warning. The drawer shows the DA-documented replacement and preserves both Senate rows. Municipal drill-down uses the original Villasis locality. The NEP and HGAB stops show the underlying location finding. |
| **Cata’lapan–Saramais, Anonat, Paracelis** | DA drops `CAR-0021` to ₱0 in both drafts. The Nov 5 review annex pairs it with ₱25M Paracelis control `CAR-NEW-0005`. The Nov 12 annex instead pairs it with ₱5M Tabuk control `CAR-NEW-0007`. The latter appears on separate workbook row 31, while the ₱250M drop is on row 28. Both rows use the same reprioritization remark. | Keep the ₱250M line and ₱5M Tabuk line separate. The Nov 12 draft and Senate row `senate_a1:p21:r190` agree on the Tabuk road. The annex's candidate pairing and workbook rows are visible in DA source evidence. A keyword in a remark or proximity within the workbook does not establish that ₱250M became ₱5M. |
| **Danuman West Trading Center, Sta. Maria** | The ₱15M NEP title wrapped into the extracted GPS field. The road skipped HGAB. DA control `R1-0022` and the Senate insertion `senate_a1:p4:r28` agree with the restored NEP title, amount, and endpoints. | Recover the wrapped locality and join the three records under `nep_fmr:p2:r9`. Show **Reinstated** as the chain action and **Inserted** as the annex action. The ₱5M Danuman West road has different endpoints and remains separate under `nep_fmr:p2:r8`. |
| **Corocor to Cabaruan, Bacarra** | DA control `R1-L-0024` first appears in the Nov 12 draft at Excel row 163. The ₱28M Senate row `senate_a1:p17:r151` shares both endpoints, but its title names only Corocor. | Export unmatched controls from either DA draft. Show both ₱28M amounts on one Explorer row labeled **Possible DA → Senate match**. Both source titles and the workbook row remain available in the drawer. |
| **Kalubkob and Supok–Maynilaan, Silang** | Senate printed `REGION IVA`, which the exporter previously missed. Both Senate insertions match their DA proposals exactly. For the ₱15M Kalubkob road, both DA drafts place GPS correction `R4A-NEW-0003` immediately after dropped control `R4A-0011`. | Normalize `IVA` and `IV-A` to the same region key, likewise for IVB. The ₱15M NEP road uses the repeated DA correction evidence to bridge the old endpoints to Senate row `senate_a1:p65:r601`. The ₱20M Supok–Maynilaan road is a separate DA insertion (`R4A-NEW-0036`) and Senate insertion (`senate_a1:p84:r770`). |
| **Comon to Amolongin, Infanta** | Both DA drafts and Senate row `senate_a1:p83:r762` list the same ₱10M road with two numbered START/END pairs. The DA extractor previously missed the bare numeric labels and emitted empty GPS fields. | Parse and compare all numbered segments by their labels. DA control `R4A-NEW-0028` and the Senate insertion appear on one exact-match chain. |
| **Alimang, Sablan and Burgos** | The DA drafts retained the original road. Adjacent Senate cut and insertion rows share ₱15M and both endpoints, and the insertion extends the route title to Libtong. | Show one Explorer chain with the **Possible Senate restatement** warning and the paired ₱15M amount. Keep both Senate source rows and the pending DA review accessible in the drawer. |
| **Barangay 27, Laoag** | Senate extraction moved the two Section 2 longitudes into the title. Restoring them reproduces the DA coordinates for `R1-NEW-0014`. | Recover the coordinates when an exact DA match corroborates the repair. The review annex links the corrected insertion to the dropped original. The Explorer shows one ₱10M chain with both replacement and restatement warnings. |
| **Zaragoza and Quezon, Nueva Ecija** | The DA revision for San Isidro–Sta. Cruz–Pantoc matches its Senate insertion. Sta. Rita's NEP coordinates use degree symbols, and DA trims ₱500 before the Senate inserts the revised amount. Pantoc–Carmen matches the DA proposal and an existing Senate realignment. | Use DA's original and proposed fields to bridge the first two NEP reinstatements. Attach exact DA evidence to the existing Gen. Luna–Carmen realignment. Keep Concepcion–Pantoc and San Miguel–Sta. Rita as separate cuts. |
| **Nancalabasaan–Don Montano, Umingan** | The Senate paired the House cut with a ₱15M insertion that changes the title and end coordinate. DA control `R1-NEW-0029` matches the insertion `senate_a1:p14:r132` on title, amount, and both revised endpoints. | Attach the DA proposal to the existing realignment under `ib:p672:r5`. Searching the DA control shows one chain with ₱15M in both the DA and Senate columns. |
| **Nagpalanga → Nagpalangan, Binmaley** | NEP and House list the ₱5M original. In both DA drafts, the explicit title revision `R1-L-0005` immediately follows dropped control `R1-0032`. The consecutive Senate cut and insertion (`senate_a1:p5:r40` and `senate_a1:p5:r41`) share the amount and both endpoints. | Group the records on `ib:p668:r13` with **Possible Senate restatement**. Searching the corrected spelling finds the full chain. The drawer attributes the title correction to the DA workbook evidence. |
| **Lower Balacbac, Baguio City** | House cut `ib:p673:r5` (Annex A-1 p18 r165) and Senate insertion `senate_a1:p18:r166` share a start coordinate, ₱15M, and closely related titles. The end coordinate differs. | Leave the rows unlinked pending source review. This was the only shared-endpoint candidate found in a check of the ten localities with the most possible unmatched cut and insertion pairs. |

The [DA review annex generator](../other-analysis/build_fmr_flags_annex.py)
can propose a replacement from nearby workbook rows when title matching
fails. For Anonat, consult the [Nov 12 review annex](../other-analysis/data/fmr_flags_annex_nov12.csv)
and the [Nov 12 draft extract](../other-analysis/data/da_fmr_draft_nov12.json)
together to see which fields came from the workbook and which came from the
review pairing.

## Explorer and review behavior

| Edge case | Current behavior |
| --- | --- |
| **House insertion or an absent stage** | Always show NEP, HGAB, DA Nov 5, DA Nov 12, and Senate. A House insertion shows **N/A** at NEP. **No draft** means a DA link is missing for a road with earlier-stage evidence. **Unchanged** is explicit for a House road that the Senate annex leaves unchanged. |
| **DA amounts differ or one draft is missing** | The **DA (₱M)** column shows the proposed amount. Nov 12 takes precedence, with both vintages labeled when amounts differ. A Nov 5-only amount is labeled. A dash marks a missing amount and **0** marks proposed zero funding. |
| **Flag icon appears but finding is hard to locate** | Clicking a stage badge opens that drawer stop. Original review findings appear on the flagged NEP or HGAB stop. The DA stops show draft-specific outcomes, **Compare drafts**, and expandable **Source evidence** for controls, workbook evidence, remarks, and endpoints. |
| **Review status colors and filters** | A red flag marks a source finding or pending DA review. A green check marks a correction recorded in a draft's review annex. A gray minus marks a drop or omission. Counted chips cover **Flagged in review**, **Pending review**, and **Documented fix**. The fix chip also includes linked DA corrections supported by draft evidence. All filter chips have dark selected, unselected, and keyboard-focus styles. |
| **Review status is too broad for a targeted check** | The **Finding type** and **Fix type** chip rows are visible directly below **Review status**. Findings use the review annex categories, including PSGC checks, location mismatches, endpoints outside the stated locality, invalid coordinates, reversed axes, and printed coordinate typos. Fixes distinguish title, coordinate, combined, and other documented corrections. Counts use distinct Explorer chains matching the search and other applied filters. A chain may appear in several category counts. The three filter rows combine, so a chain must meet each selected criterion. |
| **Inserted filter used to expose only the Senate half of a chain** | Stage filters use the chain's action. Sitio Rango appears under **Realigned**. **Inserted** selects chains classified as Senate insertions. Source row access remains available via the drawer or exact annex ID. |
| **DA and Senate both add the road** | Keep **DA insertion** and Senate **Inserted** as separate stage actions on the chain. The comparison chips count **Exact DA match**, **Possible DA → Senate match**, **Title or GPS clue**, and **No DA match**. The last category applies to Senate insertion chains with no identified DA match. |
| **Filter changes and chip counts** | Search and filter changes update the table and counts immediately. Each chip count shows how many chains would match that choice alongside the search and all other active filters. |
| **Search appears to miss a road when filters are active** | Search uses source aliases and DA control IDs. An amber banner directly above the table reports the number of matching chains hidden by the active filters. Grouping and drill-down count the combined presentation row once. |
| **Explorer costs time on initial load** | The Explorer and drawer are split into a separate bundle that loads near the viewport or on municipality drill-down. The shared projects bundle still loads for the stage-flow chart. |

Use [web/check_smoke.py](../web/check_smoke.py) to reproduce the search, filter,
and drawer checks for Cabungaan, Sitio Rango, Bobonan, Danuman West, Tabuk,
Corocor, and Nagpalangan after rebuilding the app. The checks also cover
finding and fix chips for Cabungaan and Sitio Rango.
