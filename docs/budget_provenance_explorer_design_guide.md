# Design a provenance explorer for budget data

A budget provenance explorer should let someone find an allocation, see
how its wording or funding changed, and inspect the records supporting
that account. FMR and NIA use the same browsing pattern with different
evidence. Apply the pattern to a new budget dataset after defining which
questions the source documents can answer.

The [explorer UI/UX guide](provenance_explorer_ui_ux.md) records the
interaction and presentation decisions from FMR and NIA.

## Start with the budget question and the record grain

Identify what readers are trying to follow. A project explorer can use
road contracts or irrigation works as its browsing unit. A health
budget might be easier to browse by facility, with equipment, construction,
and other appropriations shown as separate lines within each facility.
A program budget might start at program or activity level and drill
down to line items when the documents support that detail.

For each source, record its edition, role, coverage, fiscal year, unit
of account, hierarchy, and row locator. If sources use different
levels of detail, link them at the level they support. For instance,
a facility-level appropriation can link to a group of itemized
allocations while each child retains its own amount and source ID.
Keep subtotals and details distinguishable so they can be reconciled
without double-counting.

## Define the stages and what a link can claim

- **Official snapshots** show allocations as printed in a proposal,
  bill, or enacted budget. **Amendment schedules** may show only
  changes or may supply both before and after values. Establish the
  coverage and baseline before treating omission as unchanged.
- **Agency workbooks and review files** can corroborate a match,
  explain a correction, or show a proposed change. Place parallel
  editions side by side in the evidence drawer. Show a legislative
  adoption claim only when the legislative source supports it.
- **Identity links** can come from explicit references, strong
  agreement on domain fields, or partial agreement requiring review.
  Keep each source action visible even when a chain joins several
  observations. For splits and merges, expose all source lines and
  show only the allocation path the evidence establishes.
- **Missing and zero values** need separate display states. Distinguish
  an explicit cut to zero, a stage outside scope, an unavailable
  amount, and an unresolved link. A finding can still be visible when
  the amounts needed to compute a stage action are unavailable.

## Choose views that fit the evidence

| View | Use it for |
|---|---|
| Summary cards | Show source-stage totals and coverage with denominators. Label the scope of a change or finding count. |
| Searchable table | Use one row per browsing unit. Include amounts for comparable stages and action badges. Search original and revised titles, source IDs, and useful program identifiers. |
| Evidence drawer | Show the original title, amount, locator, and any relevant normalized values. Explain link methods, reveal disagreements, and link related records. Use stage colors and written status labels together. |
| Filters | Offer independent dimensions such as program, geography, stage action, and review status. Combine overlapping choices in one row. Define what each count measures and apply the other active filters to it. |
| Grouping and drill-down | Use the hierarchy the sources support, such as agency, facility, district, or province. Reuse the grouping key in the table filter and show the chosen group in the results. |
| Flow or change summary | Use a flow view where allocation paths can be represented faithfully. Where relationships are partial or ambiguous, use stage totals and a change table, with unresolved amounts visible. |

Program-specific fields should help explain the budget trace. Roads
may need ordered endpoints, irrigation work may need stationing and
workbook findings, and a facility budget may need facility IDs and
funding components. Display comparable fields in shared controls and
keep specialized evidence in the drawer.

## Verify before publishing

1. Reconcile counts and peso amounts by source stage. Test that grouped
   records, splits, and repeated findings preserve source totals.
2. Verify a representative set of links against the source documents.
   Include an explicit change, a likely match, an ambiguous match,
   and an unmatched record. Check editions where a row moved or a
   source identifier changed.
3. Walk through the explorer by title and source ID. Check filter
   counts, drill-down results, explicit zero versus missing values,
   and the ability to reach the supporting rows from the drawer.
4. Label gaps in source or link coverage. Where a public summary uses
   a broader review scope than the linked explorer rows, retain its
   denominator and keep the additional evidence accessible at the
   appropriate level.

Use the [provenance chaining considerations](provenance_chaining_considerations.md)
for source and matching rules. Use the
[web app build guide](provenance_explorer_build_guide.md) to implement the
design in this repository.
