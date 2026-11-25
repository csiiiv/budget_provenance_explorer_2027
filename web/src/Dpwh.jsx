import { senateOutcome } from './lib.jsx'
import DpwhBudgetControls, { billions } from './DpwhBudgetControls.jsx'
import React, { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Kpi, ProvenancePage } from './App.jsx'
import { DeltaBar, DetailTable, FieldDiff, Flags, Meta, ProjectDrawer, Remark } from './Detail.jsx'
import { fmtBudget } from './lib.jsx'
import { BudgetStageRail } from './StageRail.jsx'
import AnnexTrail from './AnnexTrail.jsx'
import './styles.css'

const DpwhStageFlow = lazy(() => import('./Flow.jsx').then((module) => ({ default: module.DpwhStageFlow })))

const stages = [
  ['nep', 'NEP'], ['house', 'House I-C'], ['review', 'HGAB review'], ['senate', 'Senate'],
]
const amount = (value) => fmtBudget(value, '₱')
const humanize = (key) => (key || '').replaceAll('_', ' ')
const regionKeyOf = (value) => value?.toUpperCase().replace(/^REGION 0+(?=\d)/, 'REGION ') || ''

const stageActions = [
  { key: 'nep_house', label: 'NEP → House' },
  { key: 'house_senate', label: 'House → Senate' },
]
const typeOptions = [
  ['house', 'House project rows'], ['nep_only', 'NEP without House link'],
  ['senate_only', 'Senate A-4 row without House link'], ['control', 'House control or FAP total'],
]
const KEY_DOCS = [
  ['has_pow', 'Program of Work'], ['has_bp202', 'BP 202'],
  ['has_development_council', 'Development council endorsement'],
  ['has_geotagged_photos', 'Geotagged photos'],
  ['has_certificate_of_implementability', 'Certificate of implementability'],
]
const flagFamily = {
  documents: 'Documents', nep: 'NEP comparison', cost: 'Amount and cost',
  history: 'Repeats and history', location: 'Location and map',
}

function title(row) {
  return row.house?.title || row.nep?.title || row.senate?.hb_title || row.senate?.senate_title
}

function senateAction(s) {
  if (!s) return null
  if (s.sv_php == null) return 'Cut to zero'
  if (s.sv_php > s.gab_php) return 'Increase'
  if (s.sv_php < s.gab_php) return 'Decrease'
  if (s.senate_title && s.hb_title && normTitle(s.senate_title) !== normTitle(s.hb_title)) return 'Revised description'
  return 'No amount change'
}

function normTitle(text) {
  return (text || '').replace(/\s+/g, ' ').trim()
}

function adapt(row) {
  const region = row.house?.region_key || row.nep?.region_key
    || regionKeyOf(row.senate?.region_key || row.senate?.region)
  const actions = {
    nep_house: row.nep && row.house
      ? (row.nep.amount_php === row.house.amount_php ? 'Same amount' : 'Amount changed')
      : row.house ? 'House without NEP link' : row.nep ? 'NEP without House link' : null,
    house_senate: senateAction(row.senate) ?? (row.house ? 'No Senate record' : null),
  }
  const notes = {
    house_senate: [
      row.senate?.senate_title && row.senate.hb_title && normTitle(row.senate.senate_title) !== normTitle(row.senate.hb_title)
        ? 'Title revised' : null,
      row.senate?.is_fap ? 'Foreign-assisted' : null,
      row.house && !row.nep ? 'House insertion candidate' : null,
    ].filter(Boolean),
  }
  const review = row.review
  const type = row.house?.allocation_kind === 'control' ? 'control'
    : row.house ? 'house'
    : row.nep ? 'nep_only' : 'senate_only'
  return {
    id: row.id, raw: row, title: title(row), region, municipality: null, province: region,
    actions, stageNotes: notes, type,
    nep: row.nep && { amount_m: row.nep.amount_php / 1e6 },
    house_m: row.house ? row.house.amount_php / 1e6 : null,
    senate: row.senate && {
      sv_m: row.senate.sv_php == null ? 0 : row.senate.sv_php / 1e6,
      status: { 'Cut to zero': 'cut', 'Revised description': 'renamed',
        Increase: 'raised', Decrease: 'reduced' }[actions.house_senate] ?? 'restated',
    },
    reviewStatus: {
      flagged: !!review?.red_flags || (row.flags?.length ?? 0) > 0,
      pending: false,
      fixed: false,
      no_key_documents: review && review.key_documents_found === 0,
      all_key_documents: review && review.key_documents_found === 5,
      ...Object.fromEntries((row.flags ?? []).map(([code, family]) => [`${family}:${code}`, true])),
      ...review ? Object.fromEntries(KEY_DOCS
        .filter(([key]) => review[key] === false)
        .map(([key, label]) => [`missing:${key}`, true])) : [],
    },
    searchText: [
      row.id, region, row.house?.id, row.nep?.id, row.senate?.id,
      row.house?.title, row.nep?.title, row.house?.office, row.nep?.office, row.house?.program, row.nep?.program,
      row.house?.pap, row.nep?.pap, row.senate?.office, row.senate?.program,
      row.senate?.hb_title, row.senate?.senate_title,
      review?.hgab_id, review?.dpwh_proposal_code, review?.legislative_districts,
      row.comparison?.id,
    ].filter(Boolean).join(' ').toLowerCase(),
  }
}

function AgencyAmount({ project }) {
  const review = project.raw.review
  if (!review) return '—'
  return <span title="Key documents found (of 5)">{review.key_documents_found}/5</span>
}

function railAction(row, key) {
  if (key === 'nep') return row.nep ? 'Proposed' : null
  if (key === 'house') return row.actions.nep_house
  if (key === 'review') {
    if (!row.review) return null
    if (row.review.key_documents_found === 5) return 'All key documents'
    if (row.review.red_flags === 0) return 'No red flags'
    return `${row.review.red_flags} red flags`
  }
  return row.actions.house_senate ?? (row.house ? 'No Senate record' : null)
}

function Rail({ project, onSelect, selected }) {
  const { raw, actions } = project
  return <BudgetStageRail ids={stages.map(([key]) => key)} agency="DPWH"
    stages={[
      ['NEP', raw.nep ? 'Proposed' : null],
      ['House I-C', actions.nep_house],
      ['HGAB review', railAction(raw, 'review'), raw.review ? [{ status: raw.review.red_flags ? 'PENDING REVIEW' : 'RESOLVED' }] : null],
      ['Senate', senateOutcome(project)],
    ]} onSelect={onSelect} selected={selected} />
}

function amountChange(before, after, note) {
  const delta = before != null && after != null ? after - before : null
  return {
    chips: [{ text: delta == null ? amount(after) : `${delta > 0 ? '+' : ''}${amount(delta)}`,
      cls: delta > 0 ? 'up' : delta < 0 ? 'down' : 'muted' }],
    note,
  }
}

// A-4 heading rows print the unit's full budget (GAB → SV including lines the
// annex does not list), so the trail shows the printed full totals plus the
// verified net change — never a recomputed delta over listed rows only.
function AnnexTrailWrap({ s, amount: fmt }) {
  if (!s?.rollup) return null
  const { office, region } = s.rollup
  if (!office && !region) return null
  const change = (sub) => sub.net_php
    ? `${sub.net_php > 0 ? '+' : ''}${fmt(sub.net_php)} net` : 'no net change'
  const fullBudget = (sub) => `House ${fmt(sub.gab_php)} → Senate ${fmt(sub.sv_php)}`
  const geoRow = (name, sub, note) => ({
    name,
    amounts: `${fullBudget(sub)} · ${change(sub)}`,
    note: `${note} · annex p.${sub.pdf_page}`,
  })
  return <AnnexTrail
    steps={office?.path?.slice(2, -1).filter(Boolean)}
    rows={[
      ...(region ? [geoRow(region.name, region, 'region full budget (verified)')] : []),
      ...(office ? [geoRow(office.name, office, 'office full budget (verified)')] : []),
    ]}
    note={!office && !region
      ? 'Heading subtotal not verified for this block — printed amounts withheld.' : undefined}
  />
}

function Evidence({ rec, initialStage, onClose, onJump }) {
  const row = rec.raw
  const [selected, setSelected] = useState(initialStage ??
    (row.nep ? 'nep' : row.house ? 'house' : 'senate'))

  return <ProjectDrawer rec={rec} selected={selected} onSelect={setSelected} onClose={onClose}
    Rail={Rail} typeLabel={typeLabels[rec.type]}>
    {row.house?.note && <div className="callout">
      <div className="kind">House control observation</div>
      <p>{row.house.note}</p>
    </div>}
    {row.senate?.bridge_note && <div className="callout">
      <div className="kind">Unresolved bridge</div>
      <p>{row.senate.bridge_note}</p>
    </div>}
    {selected === 'nep' && <section className="stage">
      <h4 style={{ color: 'var(--nep)' }}>NEP — FY2027 Volume 2B</h4>
      {row.nep ? <>
        <FieldDiff label="Project title" to={row.nep.title} />
        <DetailTable label="Source reference" pairs={[
          ['Source ID', row.nep.id], ['amount', amount(row.nep.amount_php)],
          ['PDF page', row.nep.pdf_page], ['region (normalized)', row.nep.region_key],
          ['printed region', row.nep.region_key !== row.nep.region ? row.nep.region : null],
          ['office', row.nep.office], ['PAP', row.nep.pap], ['program', row.nep.program],
          ['zone', row.nep.zone === 'fap' ? 'foreign-assisted' : null],
        ]} />
        {row.house && <DeltaBar label="NEP → House"
          {...amountChange(row.nep.amount_php, row.house.amount_php, actionsLabel(row))} />}
      </> : <div className="empty">
        {row.house ? 'No linked NEP row — the comparison classifies this as a House-only candidate.' : 'No NEP record.'}
      </div>}
    </section>}
    {selected === 'house' && <section className="stage">
      <h4 style={{ color: 'var(--house)' }}>House — HB 10858 Vol I-C, third reading</h4>
      {row.house ? <>
        <FieldDiff label="Project title"
          from={row.nep && normTitle(row.nep.title) !== normTitle(row.house.title) ? row.nep.title : null}
          to={row.house.title} />
        <DetailTable label="Source reference" pairs={[
          ['Source ID', row.house.id], ['amount', amount(row.house.amount_php)],
          ['PDF page', row.house.pdf_page],
          ['region (normalized)', row.house.region_key],
          ['printed region', row.house.region_key !== row.house.region ? row.house.region : null],
          ['office', row.house.office],
          ['PAP', row.house.pap], ['program', row.house.program],
          ['expense class', row.house.expense_class],
          ['record kind', row.house.node_kind === 'control' ? 'control / FAP total' : null],
        ]} />
        {row.comparison && <details className="source-evidence">
          <summary>Reading comparison evidence</summary>
          <DetailTable label="Comparison" pairs={[
            ['comparison ID', row.comparison.id],
            ['match status', humanize(row.comparison.match_status)],
            ['reading status', humanize(row.comparison.reading_status)],
            ['Transparency PHP', amount(row.comparison.transparency_php)],
            ['NEP PDF page', row.comparison.nep_pdf_page],
            ['House PDF page', row.comparison.house_pdf_page],
          ]} />
        </details>}
      </> : <div className="empty">
        {row.nep ? 'No House row — the reading comparison left this NEP record unmatched.' : 'No House record on this chain.'}
      </div>}
    </section>}
    {selected === 'review' && <section className="stage">
      <h4 style={{ color: 'var(--da)' }}>HGAB review set — documents and red flags</h4>
      {row.review ? <>
        <p><b>{row.review.hgab_id}</b> · {row.review.key_documents_found}/5 key documents · {row.review.red_flags} red flags</p>
        <div className="flagrow">
          {KEY_DOCS.map(([key, label]) => (
            <span key={key} className={row.review[key] ? 'review-fixed' : 'review-open'}
                  title={label}>{row.review[key] ? '✓' : '⚑'} {label.split(' ').slice(-1)[0]}</span>
          ))}
        </div>
        <Meta pairs={[
          ['Senate files', row.review.senate_files],
          ['redacted', row.review.senate_files_redacted],
          ['DPWH Transparency files', row.review.dpwh_transparency_files],
          ['proposal code', row.review.dpwh_proposal_code],
          ['legislative districts', row.review.legislative_districts],
          ['office scope', humanize(row.review.office_scope)],
        ]} />
        {(row.review.project_page || row.review.reviewer_page) && <p>
          {row.review.project_page && <a href={row.review.project_page} target="_blank" rel="noreferrer">Project page ↗</a>}
          {' '}{row.review.reviewer_page && <a href={row.review.reviewer_page} target="_blank" rel="noreferrer">Reviewer page ↗</a>}
        </p>}
      </> : <div className="empty">
        No bridged review row for this chain. The bridge joins on page, amount, and title;
        {row.house ? ' this leaf did not match uniquely.' : ' review rows join House leaves only.'}
      </div>}
      {(row.flags ?? []).slice(0, 30).map(([code, family, value], i) => (
        <div className="repbox evidence" key={code + i}>
          <div className="lab">{flagFamily[family] ?? family} · {humanize(code)}</div>
          {value != null && <Meta pairs={[['flag amount', amount(value)]]} />}
        </div>
      ))}
      {(row.flags?.length ?? 0) > 30 && <p className="sflow">
        +{row.flags.length - 30} more flags on the project reviewer page
      </p>}
    </section>}
    {selected === 'senate' && <section className="stage">
      <h4 style={{ color: 'var(--senate)' }}>Senate — Committee Report Annex A-4</h4>
      {row.senate ? <>
        <p>{senateAction(row.senate)} · match: {humanize(row.senate.match)}</p>
        <FieldDiff label="Project title (House text → Senate text)" mono
          from={row.senate.hb_title} to={row.senate.senate_title || row.senate.hb_title} />
        <AnnexTrailWrap s={row.senate} amount={amount} />
        <DeltaBar label="House → Senate"
          {...amountChange(row.senate.gab_php, row.senate.sv_php, senateAction(row.senate))} />
        <DetailTable label="Annex A-4 source" pairs={[
          ['Source ID', row.senate.id], ['PDF page', row.senate.pdf_page],
          ['cited HB page', row.senate.hb_page_cited], ['office', row.senate.office],
          ['region (normalized)', row.senate.region_key],
          ['printed region', row.senate.region_key !== row.senate.region
            ? row.senate.region : null],
          ['program', row.senate.program],
          ['GAB amount', amount(row.senate.gab_php)],
          ['Senate amount', amount(row.senate.sv_php)],
          ['net change', amount(row.senate.net_php)],
          ['foreign-assisted', row.senate.is_fap ? 'yes' : null],
        ]} />
      </> : <div className="empty">
        Not listed in Annex A-4. The annex is change-only; absence means the Senate
        committee left the House amount as-is.
      </div>}
    </section>}
  </ProjectDrawer>
}

const typeLabels = Object.fromEntries(typeOptions)

function actionsLabel(row) {
  return row.nep && row.house
    ? (row.nep.amount_php === row.house.amount_php ? 'Same amount' : 'Amount changed') : null
}

function aggregate(projects) {
  const regions = new Map()
  for (const p of projects) {
    for (const [key, value] of [
      ['nep_m', p.nep?.amount_m], ['house_m', p.house_m], ['senate_m', p.senate?.sv_m],
    ]) {
      if (value == null) continue
      const group = p.region || 'UNSPECIFIED'
      if (!regions.has(group)) regions.set(group, { key: group, label: group })
      const region = regions.get(group)
      region[key] = (region[key] ?? 0) + value
    }
  }
  return {
    regions: [...regions.values()].sort((a, b) => a.key.localeCompare(b.key)),
    localities: [],
  }
}

function App() {
  const [bundle, setBundle] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    fetch(new URL('data/dpwh.json', window.location.href)).then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      return response.json()
    }).then(setBundle).catch((err) => setError(err.message))
  }, [])

  const projects = useMemo(() => (bundle?.chains ?? []).map(adapt), [bundle])
  const geography = useMemo(() => aggregate(projects), [projects])
  const config = useMemo(() => {
    const counts = new Map()
    for (const p of projects) {
      for (const flag of p.raw.flags ?? []) {
        const [code, family] = flag
        counts.set(`${family}:${code}`, (counts.get(`${family}:${code}`) ?? 0) + 1)
      }
    }
    const families = [...new Set([...counts.keys()].map((k) => k.split(':')[0]))]
    const flagOptions = [
      ['', 'Any finding'],
      ['no_key_documents', 'No key documents found', 'Key documents'],
      ['all_key_documents', 'All five key documents', 'Key documents'],
      ...families.flatMap((family) =>
        [...counts.entries()].filter(([k]) => k.startsWith(`${family}:`))
          .sort((a, b) => b[1] - a[1]).slice(0, 8)
          .map(([k, n]) => [k, `${humanize(k.split(':').slice(1).join(':'))} (${n})`,
                            flagFamily[family] ?? humanize(family)])),
    ]
    return {
      stages: stageActions, typeOptions, typeLabels,
      grouping: null,
      comparisonOptions: [],
      agencyHeading: 'Key docs',
      AgencyAmount, Rail, flagOptions, fixOptions: [],
      Evidence: (props) => <Evidence {...props} />,
    }
  }, [projects])

  if (error) return <p role="alert">Unable to load the DPWH export ({error}).</p>
  if (!bundle) return <div className="loading" role="status">Loading DPWH records…</div>

  const t = bundle.totals
  const totals = {
    nep_m: t.nep.amount_php / 1e6,
    house_m: t.house.amount_php / 1e6,
    senate_m: t.senate.amount_php / 1e6,
    counts: t.counts,
    actions: t.actions,
  }
  const review = bundle.review_totals
  const operations = bundle.budget_controls?.operations
  const uncoveredProjects = t.counts.house_projects_without_senate
    ?? projects.filter((project) => project.type === 'house' && !project.senate).length
  const uncoveredControls = t.counts.house_controls_without_senate
    ?? projects.filter((project) => project.type === 'control' && !project.senate).length
  const delta = t.senate.amount_php - t.senate.gab_php
  return <ProvenancePage current="dpwh" budgetFlow={bundle.budget_controls && (
      <Suspense fallback={<div className="panel">Loading stage flow…</div>}>
        <DpwhStageFlow controls={bundle.budget_controls} projects={projects} totals={totals} />
      </Suspense>
    )} senateScope="Annex A-4 listed rows" data={{ projects, ...geography, manifest: { totals } }} config={config}
    header={<>
      <h1>DPWH Provenance Explorer — FY2027 budget chain</h1>
      <span className="sub">NEP Vol 2B · House HB 10858 I-C 3rd reading · HGAB review set · Senate Annex A-4</span>
      <div className="badges">
        <span className="badge">{t.nep.rows.toLocaleString()} NEP · {t.house.rows.toLocaleString()} House · {t.senate.rows.toLocaleString()} A-4 rows</span>
        <span className="badge">{review.hgab_rows.toLocaleString()} review rows · {review.flag_entries.toLocaleString()} red flags</span>
      </div>
    </>}
    footer={`DPWH export · ${bundle.inputs['analysis/data/dpwh_comparison_all_2027.csv'].slice(0, 8)} inputs · ${projects.length.toLocaleString()} chain records`}>
    {bundle.budget_controls && <DpwhBudgetControls controls={bundle.budget_controls}
      listed={t.senate.amount_php} />}
    <div className="kpirow">
      <Kpi lab="NEP operations" val={{ v: billions(operations?.nep_php ?? t.nep.amount_php), color: 'var(--nep)' }}
        note={`${t.nep.rows.toLocaleString()} source records in NEP Vol. II-B`} />
      <Kpi lab="House operations" val={{ v: billions(operations?.house_php), color: 'var(--house)' }}
        note={`${t.house.rows.toLocaleString()} project records · ${t.controls.rows.toLocaleString()} control records in the explorer`} />
      <Kpi lab="Senate committee operations" val={{ v: billions(operations?.senate_php), color: 'var(--senate)' }}
        note={`${t.senate.rows.toLocaleString()} A-4 rows totaling ${billions(t.senate.amount_php)}`} />
      <Kpi lab="Annex A-4 net change" val={{ v: `${delta < 0 ? '−' : delta > 0 ? '+' : ''}${billions(Math.abs(delta))}`,
        color: delta < 0 ? 'var(--cut)' : delta > 0 ? 'var(--raised)' : 'var(--text)' }}
        note={<>
          {`${t.counts.cuts.toLocaleString()} cuts to zero · ${t.counts.senate_insertion} A-4 rows without a House link`}
          <br />
          {`No Senate row in A-4 for ${uncoveredProjects.toLocaleString()} House projects and ${uncoveredControls.toLocaleString()} House controls`}
        </>} />
      <Kpi lab="HGAB review bridge" val={`${review.bridged.toLocaleString()}/${review.hgab_rows.toLocaleString()}`}
        note={`${review.ambiguous} ambiguous · ${review.missing} unbridged chains`} />
      <Kpi lab="Red flags carried" val={review.chains_with_flags.toLocaleString()}
        note={`${review.flag_entries.toLocaleString()} entries from the retained review set`} />
    </div>
  </ProvenancePage>
}

createRoot(document.getElementById('app')).render(<App />)
