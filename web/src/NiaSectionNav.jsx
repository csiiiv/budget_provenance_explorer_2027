import './niaSection.css'

export const niaPages = [
  { key: 'home', href: './nia.html', label: 'NIA overview' },
  { key: 'provenance', href: './nia-provenance.html', label: 'Provenance explorer', index: '01', accent: 'var(--nep)', description: 'Trace projects through the NEP, House bill, NIA reconciliation workbooks and Senate committee report.', features: ['Budget changes and stage flows', 'Project chains and source evidence', 'Review findings and regional totals'] },
  { key: 'titles', href: './nia-titles.html', label: 'Title comparison', index: '02', accent: 'var(--house)', description: 'Compare project descriptions side by side across budget stages and agency submissions.', features: ['Title changes and scope differences', 'Workbook and annex references', 'Supporting document attribution'] },
  { key: 'documents', href: './nia-documents.html', label: 'Document coverage', index: '03', accent: 'var(--senate)', description: 'Assess Program of Works and picture-package coverage against the original Senate hearing workbook.', features: ['Regional and category coverage', 'Budget amounts without attributed packages', 'Match review and filtered CSV exports'] },
  { key: 'coordinates', href: './nia-coordinates.html', label: 'Coordinate coverage', index: '04', accent: 'var(--reinstated)', description: 'Compare geographic coordinate evidence with Senate committee allocations and identify funded records needing location review.', features: ['Funding and coordinate cross-tabulation', 'Budget-weighted coverage and exceptions', 'Regional breakdowns and record-level evidence'] },
  { key: 'map', href: './nia_map.html', label: 'Project map', index: '05', accent: 'var(--da)', description: 'Locate projects using coordinates from the NIA workbook and inspect the associated project evidence.', features: ['Interactive geographic view', 'Workbook site coordinates', 'Project evidence drawer'] },
]

export default function NiaSectionNav({ current }) {
  return <nav className="nia-section-nav" aria-label="NIA tools">
    {niaPages.map(p => <a key={p.key} href={p.href} aria-current={p.key === current ? 'page' : undefined}>{p.label}</a>)}
  </nav>
}
