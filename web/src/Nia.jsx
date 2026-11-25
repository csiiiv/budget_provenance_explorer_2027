import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Kpi, ProvenancePage } from './App.jsx'
import Trail from './AnnexTrail.jsx'
import { DeltaBar, DetailTable, Downloads, FieldDiff, Flags, ProjectDrawer, Remark } from './Detail.jsx'
import { fmtBudget, fmtM } from './lib.jsx'
import { BudgetStageRail } from './StageRail.jsx'
import NiaCoordinateMap, { formatMapPoint, workbookMapPoints } from './NiaCoordinateMap.jsx'
import './styles.css'
import NiaSectionNav from './NiaSectionNav.jsx'

const stages = [
  ['nep', 'NEP'], ['house', 'House'], ['oct10', 'NIA Oct 10'],
  ['nov13', 'NIA Nov 13'], ['senate', 'Senate'],
]
const TITLE_COMPARE = [
  { key: 'base', label: 'Base title', derived: true },
  { key: 'nep', label: 'NEP title' },
  { key: 'house', label: 'House title' },
  { key: 'oct10', label: 'NIA Oct 10' },
  { key: 'nov13', label: 'NIA Nov 13' },
  { key: 'senate', label: 'Senate title' },
]
const amount = (value) => fmtBudget(value, '₱')
const record = (row, stage) => row[stage] ?? row.agency[stage]
function stageTitles(row) {
  const oct = row.workbook?.length === 1 ? row.workbook[0] : null
  const nov = row.november_review?.length === 1 ? row.november_review[0] : null
  return {
    nep: row.nep ? row.reconciliation?.full_nep_title || row.nep.title : null,
    house: row.reconciliation?.full_house_title || row.house?.title || null,
    oct10: row.nia_submission_only?.oct10?.submission_title || oct?.submission_label || oct?.label || record(row, 'oct10')?.title || null,
    nov13: row.nia_submission_only?.nov13?.submission_title || nov?.submission_title || nov?.title_nov13 || record(row, 'nov13')?.title || null,
    senate: row.senate?.senate_title || row.senate?.hb_title || null,
  }
}

function titleDiffOf(titles) {
  const linked = Object.values(titles).filter(Boolean)
  if (linked.length < 2) return 'single'
  const norm = (text) => text.replace(/\s+/g, ' ').trim().toLowerCase()
  const first = norm(linked[0])
  return linked.every((text) => norm(text) === first) ? 'same' : 'changed'
}

// The exporter's budget_heading_key convention: the project/system name is
// the text before the first ':' or ';'. Derived per stage; the row's base
// title prefers the latest stage that printed one.
function baseTitleOf(titles) {
  const heading = (text) => (text || '').split(/[:;]/)[0].replace(/\s+/g, ' ').trim()
  for (const key of ['senate', 'nov13', 'oct10', 'house', 'nep']) {
    const value = heading(titles[key])
    if (value) return { value, varies: baseTitleVaries(titles, value) }
  }
  return { value: null, varies: false }
}

function baseTitleVaries(titles, chosen) {
  const norm = (text) => (text || '').split(/[:;]/)[0].replace(/\s+/g, ' ').trim().toLowerCase()
  return Object.values(titles).some((text) => text && norm(text) && norm(text) !== norm(chosen))
}

// Prefer the latest printed stage: Annex A-3 Senate text (revised title when
// present, otherwise the annex's House column), then earlier stages.
const title = (row) => {
  const titles = stageTitles(row)
  return titles.senate || titles.nov13 || titles.oct10 || titles.house || titles.nep
}
const regionKeyOf = (value) => value?.toUpperCase()
  .replace(/^REGION (IV-A|IV-B|IV)\b/, (_, roman) => `REGION ${{ 'IV-A': '4A', 'IV-B': '4B', IV: '4' }[roman]}`)
  .replace(/^REGION 0+(?=\d)/, 'REGION ') || ''
const region = (row) => row.house?.region || row.nep?.region || row.senate?.region_key || row.senate?.region
const senateAction = (r, restoration) => {
  if (!r) return 'No Senate record'
  if (!r.house_id) return restoration ? 'NEP restored' : 'Insertion'
  if (r.sv_php === 0 && r.gab_php > 0) return 'Cut to zero'
  if (r.sv_php > r.gab_php) return 'Increase'
  if (r.sv_php < r.gab_php) return 'Decrease'
  if (r.senate_title && r.hb_title !== r.senate_title) return 'Revised description'
  return 'No amount change'
}
const stageActions = [
  { key: 'nep_house', label: 'NEP → House' },
  { key: 'oct10', label: 'House → NIA Oct 10' },
  { key: 'nov13', label: 'NIA Oct 10 → Nov 13' },
  { key: 'house_senate', label: 'House → Senate' },
]
const typeOptions = [
  ['house', 'House project'], ['nep_only', 'NEP without House link'],
  ['senate_restoration', 'NEP funding restored by Senate'],
  ['senate_insertion', 'Senate insertion'], ['agency_only', 'Agency without NEP/House link'],
]
const reviewOptions = [
  ['', 'Any review status'], ['flagged', 'Flagged in review'],
  ['pending', 'Pending review'], ['fixed', 'Documented fix'],
  ['resolved', 'Resolved by evidence'], ['chain_review', 'Chain link needs review'],
  ['senate_nia_title_differs', 'Senate description differs from latest NIA submission'],
  ['senate_candidate_review', 'Senate–NIA candidate needs review'],
  ['senate_no_candidate', 'Senate insertion with no NIA candidate'],
]
const coverageOptions = [
  ['', 'Any coverage'], ['both', 'Both endpoints'], ['one', 'One coordinate pair'],
  ['none', 'No coordinate pair'], ['unlinked', 'No linked November row'],
  ['multiple', 'Multiple linked November rows'],
]
const humanize = (key) => key.replaceAll('_', ' ')
const stationOnlyFlag = 'no_coordinates_system_station_only'
const flagCategories = {
  no_coordinates_system_station_only: 'No coordinates · system or station only',
  no_coordinates_place_named: 'No coordinates · named locality',
  coordinate_region_mismatch: 'Coordinates outside booked region',
  workbook_defect_ref_errors: 'Workbook reference errors',
}
const flagCategoryGroups = {
  no_coordinates_system_station_only: 'No coordinates',
  no_coordinates_place_named: 'No coordinates',
  coordinate_region_mismatch: 'Geography checks',
  workbook_defect_ref_errors: 'Workbook defects',
}
const fixCategories = {
  re_assigned: 'Region or province reassigned',
  justification_added: 'Justification added',
  justification_refined: 'Justification refined',
}


function workbookAmount(row, key, side) {
  const nov = row.november_review?.length === 1 ? row.november_review[0] : null
  const oct = row.workbook?.length === 1 ? row.workbook[0] : null
  const value = key === 'nov13'
    ? nov?.[`${side}_amount_php`]
    : oct?.[`${side}_amount`]
  const parsed = value == null || value === '' ? null : Number(value)
  return Number.isFinite(parsed) ? parsed : record(row, key)?.[`${side}_amount_php`]
}

// Public table cell: package names and upstream source, not local filesystem links.
function SupportingDocsCell({ docs }) {
  if (!docs) return <span className="title-missing" aria-label="No supporting docs">—</span>
  return <div className="pow-docs-cell">
    <strong>{docs.doc_count.toLocaleString()}</strong>
    <small>{docs.pdf_count} PDF · {docs.image_count} photo{docs.image_count === 1 ? '' : 's'}</small>
    {docs.packages.map((p, i) => (
      <span className="pow-package-name" key={i}>{p.name}</span>
    ))}
    <a href={docs.drive_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>PBC source folder ↗</a>
  </div>
}

function AgencyAmount({ project: { raw } }) {
  if (raw.nia_submission_only) {
    return amount(raw.nia_submission_only.nov13.submission_amount_php)
  }
  const oct = workbookAmount(raw, 'oct10', 'hgab')
  const nov = workbookAmount(raw, 'nov13', 'hgab')
  if (oct == null && nov == null) return '—'
  if (oct === nov) return fmtBudget(nov)
  return <>
    {nov != null && <div>{fmtBudget(nov)} <small className="amount-draft">Nov 13</small></div>}
    {oct != null && <div>{fmtBudget(oct)} <small className="amount-draft">Oct 10</small></div>}
  </>
}

// Per-stage allocation shown under each title cell in the comparison view.
// NEP/House use the chain records; NIA stages use the workbook HGAB amount
// (the submission amount when the row is submission-only); Senate uses sv_php.
const TITLE_STAGES = ['nep', 'house', 'oct10', 'nov13', 'senate']
function stageAmount(row, key) {
  if (key === 'nep') return row.nep?.amount_php ?? null
  if (key === 'house') return row.house?.amount_php ?? null
  if (key === 'senate') return row.senate?.sv_php ?? null
  if (row.nia_submission_only?.[key]) return row.nia_submission_only[key].submission_amount_php ?? null
  return workbookAmount(row, key, 'hgab')
}

// Source locator shown under the amount: NEP-p1 · HB-IB-p896-r18 ·
// NIA-Oct-10-R2299 · NIA-Nov-13-R2306 · Senate-A3-p34-r493.
// NIA stages fall back from the linked workbook row to a submission-only row
// and finally the agency leaf's Excel row.
function stageRef(row, key) {
  if (key === 'nep') {
    const page = row.nep?.source?.pdf_page
    return page != null ? `NEP-p${page}` : null
  }
  if (key === 'house') {
    const { pdf_page, row_number } = row.house?.source ?? {}
    return pdf_page != null && row_number != null ? `HB-IB-p${pdf_page}-r${row_number}` : null
  }
  if (key === 'senate') {
    const { pdf_page, row_index } = row.senate ?? {}
    return pdf_page != null && row_index != null ? `Senate-A3-p${pdf_page}-r${row_index}` : null
  }
  const submission = row.nia_submission_only?.[key]
  if (submission) return `NIA-${key === 'oct10' ? 'Oct-10' : 'Nov-13'}-R${submission.row}`
  const agencyRow = record(row, key)?.excel_row
  const workbookRow = key === 'oct10' ? row.workbook?.[0]?.row : row.november_review?.[0]?.nov13_row
  const ref = workbookRow ?? agencyRow
  return ref != null ? `NIA-${key === 'oct10' ? 'Oct-10' : 'Nov-13'}-R${ref}` : null
}

function baselineTitleRef(row, key) {
  const projectId = row[key]?.id
  if (!projectId) return null
  const workbookRow = row.workbook?.find((entry) => entry[`${key}_join`]?.id === projectId)?.row
  return workbookRow != null ? `NIA-Oct-10-G${workbookRow} (From)` : null
}

function railAction(row, key) {
  const submission = row.nia_submission_only?.[key]
  if (submission) {
    return key === 'oct10' ? 'NIA submitted' : 'Same submission amount'
  }
  const previous = key === 'oct10' ? row.house?.amount_php : workbookAmount(row, 'oct10', 'hgab')
  const current = workbookAmount(row, key, 'hgab')
  if (current == null) return key === 'nov13' && row.findings?.length ? 'Review evidence' : null
  if (previous == null) return 'No prior amount'
  if (current === 0 && previous > 0) return 'Cut to zero'
  return current === previous ? 'Same amount' : 'Amount changed'
}

const senateAttributionNeedsReview = (row) =>
  row.reconciliation?.basis === 'workbook_pair_senate_attribution_review' &&
  row.reconciliation?.decision === 'review'

// November takes precedence when its submission is available for comparison.
const latestNiaRevision = (row) =>
  row.senate_revision_comparison?.nov13 ?? row.senate_revision_comparison?.oct10

function stageChanges(row) {
  const badges = { house: [], oct10: [], nov13: [], senate: [] }
  const key = (value) => value?.trim().replace(/\s+/g, ' ').toLowerCase()
  const differs = (before, after) => key(before) && key(after) && key(before) !== key(after)
  if (differs(row.nep?.title, row.reconciliation?.full_house_title || row.house?.title)) badges.house.push('Title revised')
  if (row.reconciliation?.detail_difference === 'nep_house_station') badges.house.push('Station description differs from NEP')
  if (row.reconciliation?.basis === 'documented_replacement') badges.oct10.push('Replacement proposed')
  if (row.reconciliation?.basis === 'funding_restoration') badges.senate.push('NEP amount restored')
  if (row.nia_reallocation || row.nia_submission_only) badges.senate.push('Documented reallocation')
  if (row.workbook?.length === 1 &&
      differs(row.house?.title, row.workbook[0].submission_label)) {
    badges.oct10.push('Submission title differs')
  }
  if (row.november_review?.length === 1) {
    const nov = row.november_review[0]
    if (differs(nov.title_oct10, nov.title_nov13) ||
        differs(nov.submission_title_oct10, nov.submission_title)) badges.nov13.push('Title revised')
    if (row.workbook?.length === 1) {
      const oct = row.workbook[0]
      if (differs(oct.region_canonical || oct.region, nov.region)) badges.nov13.push('Region reassigned')
      if (differs(oct.province, nov.province)) badges.nov13.push('Province reassigned')
      const before = coordinates(oct.title_parse?.coordinates?.points)
      const after = novemberCoords(nov)
      const pairs = (text) => text.split('\n').map((line) => line.replace(/^.*?: /, ''))
      if (before && after) {
        const oldPairs = pairs(before)
        const newPairs = pairs(after)
        if (oldPairs.length === newPairs.length && oldPairs.some((point, i) => point !== newPairs[i])) {
          badges.nov13.push('Coordinates differ')
        }
      }
    }
  }
  for (const flag of row.findings ?? []) {
    if (flag.status_nov13 === 'FIXED') {
      if (flag.disposition === 'justification_added') badges.nov13.push('Justification added')
      if (flag.disposition === 'justification_refined') badges.nov13.push('Justification revised')
      if (flag.disposition === 're_assigned' && !badges.nov13.some((x) => x.endsWith('reassigned'))) {
        badges.nov13.push('Location reassigned')
      }
    }
    if (flag.status_nov13 === 'RESOLVED-BY-EVIDENCE' && flag.disposition === 'distinct_confirmed') {
      badges.nov13.push('Confirmed distinct')
    }
  }
  const revision = row.senate_revision_comparison
  if (senateAttributionNeedsReview(row)) badges.senate.push('Senate attribution needs review')
  if (row.reconciliation?.detail_difference === 'senate_locality') {
    badges.senate.push('Locality description differs from NIA')
  } else if (row.senate_restoration?.barangay_wording_differs) {
    badges.senate.push('Description differs from NIA: barangay wording')
  } else if (row.senate_reverse_review?.decision === 'join' &&
      row.senate_reverse_review.detail_difference === 'coordinates') {
    badges.senate.push('Coordinates differ from NIA')
  } else if (row.senate_reverse_review?.decision === 'join' &&
      row.senate_reverse_review.detail_difference === 'locality') {
    badges.senate.push('Locality description differs from NIA')
  } else if (revision?.oct10?.matches && revision.nov13?.matches) {
    badges.senate.push('Matches both NIA submissions')
  } else if (revision?.nov13?.matches) {
    badges.senate.push('Matches NIA Nov 13')
  } else if (revision?.oct10?.matches) {
    badges.senate.push('Matches NIA Oct 10')
  }
  if (row.reconciliation?.detail_difference !== 'senate_locality' && !row.senate_restoration?.barangay_wording_differs &&
      !row.senate_reverse_review?.detail_difference && latestNiaRevision(row)?.matches === false) {
    badges.senate.push('Description differs from NIA')
  }
  if (row.senate?.house_id && differs(row.senate.hb_title, row.senate.senate_title)
      && senateAction(row.senate) !== 'Revised description') badges.senate.push('Description revised')
  return Object.fromEntries(Object.entries(badges).map(([stage, labels]) => [stage, [...new Set(labels)]]))
}

function Rail({ project, onSelect, selected, onlyStage }) {
  const { raw, actions, changes } = project
  return <BudgetStageRail ids={stages.map(([key]) => key)} agency="NIA" onlyStage={onlyStage}
    stages={[
      ['NEP', raw.nep ? 'Proposed' : null],
      ['House', raw.senate_restoration ? 'No House funding' : actions.nep_house, null, false, changes.house],
      ['NIA Oct 10', actions.oct10, null, false, changes.oct10],
      ['NIA Nov 13', actions.nov13, raw.findings?.map((f) => ({ status: f.status_nov13, warning: f.flag_category === stationOnlyFlag })), false, changes.nov13],
      ['Senate', raw.senate ? actions.house_senate : null,
        null, false, changes.senate],
    ]} onSelect={onSelect} selected={selected} />
}

function coordinateCoverage(rows = []) {
  if (!rows.length) return 'unlinked'
  if (rows.length > 1) return 'multiple'
  const [row] = rows
  const start = row.start_lat && row.start_lon
  const end = row.end_lat && row.end_lon
  return start && end ? 'both' : start || end ? 'one' : 'none'
}

// [POW FOR REVIEW] supporting docs attached by the exporter: file counts
// plus the attributed package names and upstream source URL.
function supportingDocsOf(row) {
  const docs = row.supporting_docs
  if (!docs || !docs.packages?.length) return null
  return docs
}

function adapt(row) {
  const findings = row.findings ?? []
  const fixes = findings.filter((f) => f.status_nov13 === 'FIXED')
  const changes = stageChanges(row)
  const regionKey = regionKeyOf(region(row))
  const province = (row.house?.province || row.nep?.province || row.senate?.path?.at(-1))?.toUpperCase()
  const municipality = regionKey && province && province !== regionKey ? province : null
  const docs = supportingDocsOf(row)
  const actions = {
    nep_house: row.nep && row.house
      ? (row.nep.amount_php === row.house.amount_php ? 'Same amount' : 'Amount changed')
      : row.house ? 'House without NEP link' : row.nep ? 'NEP without House link' : null,
    oct10: railAction(row, 'oct10'),
    nov13: railAction(row, 'nov13'),
    house_senate: senateAction(row.senate, row.senate_restoration),
  }
  const titles = stageTitles(row)
  const baseTitle = baseTitleOf(titles)
  return {
    id: row.id, raw: row, title: title(row), stageTitles: titles, titleDiff: titleDiffOf(titles),
    baseTitle: baseTitle.value, baseTitleVaries: baseTitle.varies,
    region: regionKey, municipality, province: regionKey, actions, changes,
    stageAmounts: Object.fromEntries(TITLE_STAGES.map((key) => [key, stageAmount(row, key)])),
    stageRefs: Object.fromEntries(TITLE_STAGES.map((key) => [key, stageRef(row, key)])),
    baselineTitleRefs: { nep: baselineTitleRef(row, 'nep'), house: baselineTitleRef(row, 'house') },
    coordinateCoverage: coordinateCoverage(row.november_review),
    coordinatePoints: [...workbookMapPoints(row.workbook), ...submissionMapPoints(row.nia_submission_only)],
    supportingDocs: docs,
    stageNotes: { nep_house: changes.house, oct10: changes.oct10,
      nov13: changes.nov13, house_senate: changes.senate },
    type: row.senate_restoration ? 'senate_restoration'
      : row.house ? 'house' : row.nep ? 'nep_only' : row.senate ? 'senate_insertion' : 'agency_only',
    nep: row.nep && { amount_m: row.nep.amount_php / 1e6 },
    house_m: row.house ? row.house.amount_php / 1e6 : null,
    senate: row.senate && {
      sv_m: row.senate.sv_php / 1e6,
      status: { 'Cut to zero': 'cut', 'Revised description': 'renamed',
        Increase: 'raised', Decrease: 'reduced' }[actions.house_senate] ?? 'restated',
    },
    searchText: [
      row.id, regionKey, row.house?.province, row.house?.subprogram_key, row.nep?.subprogram_key,
      ...Object.values(titles), row.reconciliation?.note, row.senate_reverse_review?.note, ...(row.senate?.path ?? []),
      ...stages.flatMap(([key]) => {
        const r = record(row, key)
        return [r?.id, r?.title, ...(r?.candidate_nep_ids ?? [])]
      }),
      ...(row.workbook ?? []).flatMap((r) => [r.id, r.label, r.submission_label]),
      ...(row.november_review ?? []).flatMap((r) => [r.title_nov13, r.submission_title]),
      ...(docs?.packages ?? []).map((p) => p.name),
    ].join(' ').toLowerCase(),
    reviewStatus: {
      chain_review: row.reconciliation?.decision === 'review',
      senate_candidate_review: row.senate_reverse_review?.decision === 'review',
      senate_no_candidate: row.senate_reverse_review?.decision === 'unmatched',
      senate_nia_title_differs: latestNiaRevision(row)?.matches === false,
      flagged: findings.length > 0 || !!row.review?.length,
      pending: findings.some((f) => f.status_nov13.startsWith('PENDING')) || !!row.review?.length,
      fixed: fixes.length > 0,
      resolved: findings.some((f) => f.status_nov13 === 'RESOLVED-BY-EVIDENCE'),
      ...Object.fromEntries(findings.map((f) => [f.flag_category, true])),
      ...Object.fromEntries(fixes.map((f) => [f.disposition, true])),
    },
  }
}

const stageColors = {
  nep: 'var(--nep)', house: 'var(--house)', oct10: 'var(--da)',
  nov13: 'var(--da)', senate: 'var(--senate)',
}

function coordinates(points) {
  return points?.filter((p) => p.latitude != null && p.longitude != null).map((p) => {
    const role = p.role && p.role !== 'unspecified' ? `${p.role}: ` : ''
    return `${role}${Number(p.latitude).toFixed(6)}, ${Number(p.longitude).toFixed(6)}`
  }).join('\n') || null
}

function CoordinateWorkbookEvidence({ evidence }) {
  if (!evidence) return null
  const { row, map_url: mapUrl } = evidence
  const points = evidence.coordinates?.points ?? []
  const inBounds = points.filter((point) => !point.issues?.includes('outside_philippines_screening_bounds'))
  const outsideCount = points.length - inBounds.length
  const mapMismatch = evidence.map_points_over_100m_from_supplied
  const mapLink = /^https?:\/\//i.test(mapUrl ?? '') ? mapUrl : null
  return <details className="source-evidence">
    <summary>NIA coordinate workbook · Excel row {row}</summary>
    <FieldDiff label="Revised NIA project description" to={evidence.revised_title} />
    <FieldDiff label={`Geographical coordinates · Y${row}`}
      to={evidence.coordinate_text} mono />
    <FieldDiff label="Parsed coordinates (latitude, longitude)"
      to={coordinates(inBounds)} mono />
    {outsideCount > 0 && <p>{outsideCount} parsed coordinate {outsideCount === 1 ? 'pair falls' : 'pairs fall'} outside the Philippine screening bounds.</p>}
    {mapMismatch > 0 && <p>{mapMismatch} map cell {mapMismatch === 1 ? 'point is' : 'points are'} more than 100 m from the nearest supplied point.</p>}
    <DetailTable label="Workbook fields" pairs={[
      [`CORPLAN checking · Z${row}`, evidence.corplan_checking],
      ['Region', evidence.region], ['Province', evidence.province],
      ['Match method', evidence.match_method],
    ]} />
    <FieldDiff label={`Map link cell · AA${row}`} to={evidence.map_link_text} mono />
    {mapLink && <a href={mapLink} target="_blank" rel="noopener noreferrer">Open workbook map link</a>}
    {evidence.geography_review && <p>{evidence.geography_review.note}</p>}
    <Remark label="Workbook justification" text={evidence.justification} />
  </details>
}

function novemberCoords(row) {
  return coordinates(['start', 'end'].flatMap((role) =>
    row[`${role}_lat`] && row[`${role}_lon`] ? [{
      role, latitude: row[`${role}_lat`], longitude: row[`${role}_lon`],
    }] : []))
}

function amountChange(before, after, note) {
  const delta = before != null && after != null ? after - before : null
  return {
    chips: [{ text: delta == null ? amount(after) : `${delta > 0 ? '+' : ''}${amount(delta)}`,
      cls: delta > 0 ? 'up' : delta < 0 ? 'down' : 'muted' }],
    note,
  }
}

// Annex A-3 prints every line under a five-deep hierarchy whose region and
// province steps carry their own printed subtotals; show the trail and the
// roll-up amounts instead of a joined string.
function AnnexTrailWrap({ r, amount }) {
  const [, program, subprogram, activity, regionName, provinceName] = r.path ?? []
  if (!program) return null
  const region = r.region_subtotal
  const province = r.province_subtotal
  const share = (subtotal) => subtotal?.sv_php
    ? `this row is ${Math.round(r.sv_php / subtotal.sv_php * 1000) / 10}% of it` : null
  const geoRow = (name, sub, note) => ({
    name,
    amounts: `House ${amount(sub.gab_php)} → Senate ${amount(sub.sv_php)}`,
    note: `${note} · annex p.${sub.pdf_page}`,
  })
  return <Trail
    steps={[program, subprogram, activity]}
    rows={[
      ...(region ? [geoRow(regionName, region, 'region subtotal')] : []),
      ...(province ? [geoRow(provinceName, province, share(province) || 'province subtotal')] : []),
    ]}
    note={!region && !province ? 'National line — printed without a region/province roll-up.' : undefined}
  />
}

function SupportingDocsEvidence({ docs }) {
  if (!docs) return null
  return <div className="callout">
    <div className="kind">Supporting documents · [POW FOR REVIEW]</div>
    <p>{docs.doc_count.toLocaleString()} file{docs.doc_count === 1 ? '' : 's'} attributed to this chain's
      Senate workbook row — {docs.pdf_count} PDF{docs.pdf_count === 1 ? '' : 's'} ·{' '}
      {docs.image_count} photo{docs.image_count === 1 ? '' : 's'}
      {docs.match_strength && ` · ${docs.match_strength} filename match`}
      {docs.pdf_confirmed ? ' · PDF text confirmed' : ''}.</p>
    <DetailTable label="Attributed packages" pairs={docs.packages.map((p) => [
      p.name,
      `${p.doc_count} file${p.doc_count === 1 ? '' : 's'} · ${p.pdf_count} PDF · ${p.image_count} photo${p.image_count === 1 ? '' : 's'}${p.score != null ? ` · score ${Math.round(p.score * 100)}%` : ''}`,
    ])} />
    <p>Source: <a href={docs.drive_url} target="_blank" rel="noopener noreferrer">PBC Google Drive folder</a></p>
    <p>Package names identify the attributed evidence; the source link opens the shared folder, not an individual file.</p>
  </div>
}

function Evidence({ rec, initialStage, sources, onClose, onJump, projects, titleDetails }) {
  const row = rec.raw
  const [selected, setSelected] = useState(initialStage ??
    (row.nep ? 'nep' : row.house ? 'house' : row.senate ? 'senate' : row.agency.nov13 ? 'nov13' : 'oct10'))

  const agencyStage = selected === 'oct10' || selected === 'nov13'
  const reverseReview = row.senate_reverse_review
  const reallocationTarget = row.nia_reallocation?.senate_id ?? reverseReview?.donor_senate_id
  const reallocatedProject = reallocationTarget && projects.find((p) => p.raw.senate?.id === reallocationTarget)
  const candidate = reverseReview?.decision === 'review' && projects.find((p) =>
    p.id !== rec.id && (row.senate
      ? p.raw.nep?.id === reverseReview.nep_id
      : p.raw.senate?.id === reverseReview.senate_id))

  const linkedProject = (id) => projects.find((p) => p.id !== rec.id &&
    (p.raw.nep?.id === id || p.raw.house?.id === id))

  return <ProjectDrawer rec={rec} selected={selected} onSelect={setSelected} onClose={onClose}
    Rail={Rail} typeLabel={typeLabels[rec.type]} titleDetails={titleDetails}>
    {row.comparison?.method && <div className="callout">
      <div className="kind">NEP and House comparison</div>
      <DetailTable label="Source details" pairs={[['method', humanize(row.comparison.method)],
        ['strict result', humanize(row.comparison.strict_status)]]} />
    </div>}
    <SupportingDocsEvidence docs={rec.supportingDocs} />
    {row.senate_restoration && <div className="callout">
      <div className="kind">NEP funding restored by Senate</div>
      <p>{reverseReview?.decision === 'join' ? reverseReview.note : row.senate_restoration.barangay_wording_differs
        ? 'Both NIA workbooks show zero House funding. The scope, coordinates, region, province, and amount match the Senate insertion. The barangay names differ.'
        : 'Both NIA workbooks show zero House funding. The NIA submission title, region, province, and amount match the Senate insertion.'}</p>
      <DetailTable label="NIA to Senate evidence" pairs={[
        ['October workbook row', row.senate_restoration.oct10_row],
        ['November workbook row', row.senate_restoration.nov13_row],
        ['Annex action relative to House', 'Senate inserted'],
      ]} />
    </div>}
    {reallocationTarget && <div className="callout">
      <div className="kind">Documented NIA reallocation</div>
      {row.nia_reallocation
        ? <p>{amount(row.nia_reallocation.amount_php)} reallocated to {row.nia_reallocation.title}</p>
        : <p>{reverseReview.note}</p>}
      {reallocatedProject && <button className="linkish" onClick={() => onJump(reallocatedProject.id, 'senate')}>
        {row.nia_reallocation ? 'Open recipient project' : 'Open donor project'}
      </button>}
    </div>}
    {reverseReview && ['review', 'unmatched'].includes(reverseReview.decision) && <div className="callout">
      <div className="kind">{reverseReview.decision === 'review'
        ? 'Senate–NIA candidate needs review' : 'No NIA candidate found'}</div>
      <p>{reverseReview.note}</p>
      <DetailTable label="Reverse review evidence" pairs={[
        ['Senate source ID', reverseReview.senate_id],
        ['NEP candidate ID', reverseReview.nep_id],
        ['October workbook row', reverseReview.oct10_row],
        ['November workbook row', reverseReview.nov13_row],
      ]} />
      {candidate && <button className="linkish" onClick={() => onJump(candidate.id, row.senate ? 'nov13' : 'senate')}>
        {row.senate ? 'Open NIA candidate' : 'Open Senate candidate'}
      </button>}
    </div>}
    {row.reconciliation && <div className="callout">
      <div className="kind">{senateAttributionNeedsReview(row) ? 'Senate attribution needs review'
        : row.reconciliation.decision === 'join' ? 'Chain link verified' : 'Chain link needs review'}</div>
      <DetailTable label="Reconciliation evidence" pairs={[
        ['October workbook row', row.reconciliation.workbook_row], ['NEP PDF page', row.reconciliation.pdf_page],
      ]} />
      <p>{row.reconciliation.note}</p>
      {row.reconciliation.full_nep_title && <FieldDiff label="Full NEP title from PDF"
        from={row.nep?.title} to={row.reconciliation.full_nep_title} />}
    </div>}
    {row.comparison?.variant_mark && <p>Review candidates · {row.comparison.variant_mark.counterpart_ids.join(', ')}</p>}
    {row.review?.map(({ question, note }, i) => <p key={i}>{question} · {note}</p>)}
    <div>
      {stages.filter(([key]) => key === selected).map(([key, label]) => {
        const r = record(row, key)
        const submission = row.nia_submission_only?.[key]
        return <section className="stage" key={key}>
          <h4 style={{ color: stageColors[key] }}>{label}</h4>
          {submission ? <>
            <FieldDiff label="NIA submission title" to={submission.submission_title} />
            <DetailTable label="Workbook source" pairs={[
              ['Excel row', submission.row], ['NIA submission amount', amount(submission.submission_amount_php)],
              ['Region', submission.region], ['Province', submission.province],
            ]} />
            <CoordinateWorkbookEvidence evidence={submission.coordinate_workbook} />
          </> : !r ? <div className="empty">{(key === 'oct10' && row.workbook?.length) ||
            (key === 'nov13' && row.november_review?.length)
            ? 'Workbook row evidence below' : 'No linked record'}</div> : <>
            <FieldDiff label="Project title"
              from={key === 'house' ? rec.stageTitles.nep : key === 'senate' ? r.hb_title : null}
              to={key === 'house' ? rec.stageTitles.house : r.title || r.senate_title || r.hb_title} />
            {r.source && <DetailTable label="Source reference" pairs={[
              ['Source ID', r.id],
              ['source', r.source.source_pdf], ['PDF page', r.source.pdf_page],
              ['printed page', r.source.printed_page], ['row', r.source.row_number],
              ['vertical position', r.source.y0], ['category', r.category], ['province', r.province],
            ]} />}
            <Flags flags={r.extraction_flags} />
            {key === 'senate' ? <>
              <AnnexTrailWrap r={r} amount={amount} />
              {row.senate_revision_comparison && <DetailTable label="Comparison with NIA submission titles"
                pairs={Object.entries(row.senate_revision_comparison).map(([stage, evidence]) => [
                  `NIA ${stage === 'oct10' ? 'Oct 10' : 'Nov 13'} · row ${evidence.row}`,
                  evidence.matches ? 'Title matches' : 'Title differs',
                ])} />}
              {latestNiaRevision(row)?.matches === false && <FieldDiff
                label={row.senate_revision_comparison.nov13
                  ? 'November NIA submission → Senate description' : 'October NIA submission → Senate description'}
                from={row.senate_revision_comparison.nov13 ? rec.stageTitles.nov13 : rec.stageTitles.oct10}
                to={r.senate_title} />}
              <DetailTable label="Annex A-3 source" pairs={[
                ['Source ID', r.id], ['PDF page', r.pdf_page], ['Row', r.row_index],
                ['Region (normalized)', r.region_key || null],
                ['Linked House row', r.house_id], ['Match method', r.house_id && r.match],
              ]} />
              <DeltaBar label="House → Senate" {...amountChange(r.gab_php, r.sv_php, senateAction(r, row.senate_restoration))} />
              <DetailTable label="Amounts" pairs={[[ 'House amount', amount(r.gab_php)], ['Senate amount', amount(r.sv_php)]]} />
              <FieldDiff label="Annex GPS coordinates (latitude, longitude)" mono
                from={coordinates(r.hb_gps?.points)} to={coordinates(r.senate_gps?.points)} />
              {!!(r.hb_coords.length || r.senate_coords.length) && <details className="source-evidence">
                <summary>Source evidence</summary>
                <FieldDiff label="Printed coordinates" mono from={r.hb_coords.join('\n') || null}
                  to={r.senate_coords.join('\n') || null} />
              </details>}
            </> : r.leaf_index != null ? <>
              <DetailTable label="Workbook source" pairs={[
                ['Source ID', r.id], ['Workbook', sources[key].source_xlsx],
                ['Sheet', sources[key].source_sheet], ['Extracted leaf', r.leaf_index],
                ['Source Excel row', r.excel_row],
                ['Matched Excel row', r.matched_workbook_row],
                ['Paired October agency record', r.paired_agency_id],
              ]} />
              <DetailTable label="Amounts" pairs={[[ 'Workbook NEP', amount(r.nep_amount_php)], ['Workbook House', amount(r.hgab_amount_php)]]} />
              <p>{r.link_status}{r.house_amount_agrees === false && ' · Workbook House amount differs from the linked House record'}</p>
              {!!r.candidate_nep_ids.length && <p>NEP evidence · {r.candidate_nep_ids.join(', ')}</p>}
            </> : <>
              <DetailTable label="Amount" pairs={[[ 'Allocation', amount(r.amount_php)]]} />
              {key === 'house' && row.nep && <DeltaBar label="NEP → House"
                {...amountChange(row.nep.amount_php, r.amount_php)} />}
            </>}
          </>}
        </section>
      })}
    </div>
    {agencyStage && (row.workbook?.length || row.november_review?.length) > 0 &&
      <details className="draft-compare">
        <summary>Compare drafts</summary>
        <div className="draft-comparison">
          <FieldDiff label="Submission title"
            from={row.workbook?.length === 1 ? row.workbook[0].submission_label : null}
            to={row.november_review?.length === 1 ? row.november_review[0].submission_title : null} />
          {row.workbook?.length === 1 && row.november_review?.length === 1 && <FieldDiff
            label="GPS coordinates (latitude, longitude)" mono
            from={coordinates(row.workbook[0].title_parse?.coordinates?.points)}
            to={novemberCoords(row.november_review[0])} />}
          <DetailTable label="Workbook amount comparison" pairs={['oct10', 'nov13'].map((key) => [
            key === 'oct10' ? 'Oct 10 House amount' : 'Nov 13 House amount',
            amount(workbookAmount(row, key, 'hgab')),
          ])} />
        </div>
      </details>}
    {selected === 'oct10' && row.workbook?.map((r) => <section className="stage" key={r.id}>
      <h4 style={{ color: stageColors.oct10 }}>October 10 hearing workbook · Excel row {r.row}</h4>
      <FieldDiff label="Workbook project title" to={r.label} />
      <FieldDiff label="NIA submission title" to={r.submission_label} />
      <DetailTable label="Workbook amounts" pairs={[
        ['NEP', amount(r.nep_amount)], ['House', amount(r.hgab_amount)],
        ['NIA submission', r.submission_amount == null ? null : amount(r.submission_amount)],
      ]} />
      <FieldDiff label={r.title_parse?.source === 'submission_label'
        ? 'Submission GPS coordinates (latitude, longitude)' : 'Workbook listing GPS coordinates (latitude, longitude)'}
        to={coordinates(r.title_parse?.coordinates?.points)} mono />
      <DetailTable label="Source details" pairs={[[ 'chainage length', r.title_parse?.chainage?.length_m != null
        ? `${r.title_parse.chainage.length_m} m` : null], ['coordinate parse', r.title_parse?.coordinates?.status]]} />
      <Flags flags={[...new Set((r.title_parse?.coordinates?.points ?? []).flatMap((p) => p.issues ?? []))]} />
      <Remark label="NIA justification" text={r.justification} />
      <CoordinateWorkbookEvidence evidence={r.coordinate_workbook} />
      {['nep', 'house'].map((side) => {
        const join = r[`${side}_join`]
        if (!join) return null
        const linked = linkedProject(join.id)
        return <p key={side}>{join.id} · {humanize(join.method)}
          {join.similarity != null && ` · ${Math.round(join.similarity * 100)}% title similarity`}
          {linked && <> · <button className="linkish" onClick={() => onJump(linked.id, side)}>Open {side === 'nep' ? 'NEP' : 'House'} chain</button></>}
        </p>
      })}
    </section>)}
    {selected === 'nov13' && <>
      {row.november_review?.map((r) => <section className="stage" key={r.nov13_row}>
        <h4 style={{ color: stageColors.nov13 }}>November 13 workbook · Excel row {r.nov13_row}</h4>
        <FieldDiff label="Workbook project title" to={r.title_nov13} />
        <FieldDiff label="NIA submission title" to={r.submission_title} />
        <DetailTable label="Workbook amounts" pairs={[
          ['NEP', amount(r.nep_amount_php || null)], ['House', amount(r.hgab_amount_php || null)],
        ]} />
        <DetailTable label="Review status" pairs={[['Outcome', r.status_nov13]]} />
        <FieldDiff label="Workbook GPS coordinates (latitude, longitude)" to={novemberCoords(r)} mono />
        <DetailTable label="Source details" pairs={[[ 'booked province', r.province], ['start locality', r.psgc_where_start], ['end locality', r.psgc_where_end]]} />
        <Remark label="Coordinate review" text={r.coordinate_evidence} />
        <Remark label="NIA review remarks" text={r.remarks} />
        {r.coordinates_raw && <details className="source-evidence">
          <summary>Source evidence</summary>
          <FieldDiff label="Printed coordinates" to={r.coordinates_raw} mono />
        </details>}
      </section>)}
      {row.findings?.map((f) => <section className="stage" key={f.flag_id}>
        <h4>{flagCategories[f.flag_category] ?? humanize(f.flag_category)}</h4>
        <span className={f.status_nov13.startsWith('PENDING')
          ? (f.flag_category === stationOnlyFlag ? 'review-warning' : 'review-open') : 'review-fixed'}>
          {f.status_nov13}
        </span>
        <Remark label="Finding" text={f.issue_detail} />
        <Remark label="Resolution" text={f.resolution_detail} />
        <DetailTable label="Source details" pairs={[[ 'Oct 10 row', f.workbook_row_oct10], ['Nov 13 row', f.workbook_row_nov13], ['evidence', f.evidence]]} />
      </section>)}
    </>}
  </ProjectDrawer>
}

const typeLabels = Object.fromEntries(typeOptions)
const grouping = { unit: 'Province', parent: 'Region' }

function aggregate(projects) {
  const regions = new Map()
  const localities = new Map()
  for (const p of projects) {
    for (const [key, value, location] of [
      ['nep_m', p.nep?.amount_m, p.raw.nep?.region],
      ['house_m', p.house_m, p.raw.house?.region],
      ['senate_m', p.senate?.sv_m, p.raw.senate?.region_key ?? p.raw.senate?.region],
    ]) {
      if (value == null) continue
      const group = regionKeyOf(location) || p.region || 'UNSPECIFIED'
      if (!regions.has(group)) regions.set(group, { key: group })
      const region = regions.get(group)
      region[key] = (region[key] ?? 0) + value
    }
    if (!p.municipality) continue
    const key = `${p.province}|${p.municipality}`
    if (!localities.has(key)) localities.set(key, {
      key, municipality: p.municipality, province: p.province, region: p.region,
      chains: 0, house_m: 0, senate_m: 0, actions: {},
    })
    const group = localities.get(key)
    group.chains++
    group.house_m += p.house_m ?? 0
    group.senate_m += p.senate?.sv_m ?? 0
    for (const [stage, action] of Object.entries(p.actions)) {
      if (!action || ['Same amount', 'No prior amount', 'Review evidence', 'No amount change', 'No Senate record'].includes(action)) continue
      const counts = group.actions[stage] ??= {}
      counts[action] = (counts[action] ?? 0) + 1
    }
  }
  return {
    regions: [...regions.values()].sort((a, b) => a.key.localeCompare(b.key)),
    localities: [...localities.values()].sort((a, b) => a.municipality.localeCompare(b.municipality)),
  }
}

const TITLE_DIFF_OPTIONS = [
  ['', 'Any title pattern'],
  ['changed', 'Title differs across stages'],
  ['same', 'Same title across linked stages'],
  ['single', 'Only one stage has a title'],
]

function App({ mode = 'explorer' } = {}) {
  const compare = mode === 'titles'
  const [bundle, setBundle] = useState(null)
  const [mapProject, setMapProject] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    fetch(new URL('data/nia.json', window.location.href)).then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      return response.json()
    }).then(setBundle).catch((err) => setError(err.message))
  }, [])

  const projects = useMemo(() => (bundle?.chains ?? []).map(adapt), [bundle])
  const geography = useMemo(() => aggregate(projects), [projects])
  const config = useMemo(() => {
    const options = (field, names, any) => [
      ['', any],
      ...[...new Set((bundle?.chains ?? []).flatMap((r) => (r.findings ?? [])
        .filter((f) => field !== 'disposition' || f.status_nov13 === 'FIXED').map((f) => f[field])))].sort()
        .map((key) => [key, names[key] ?? humanize(key)]),
    ]
    return {
      stages: stageActions, typeOptions, typeLabels, grouping,
      comparisonOptions: [], senateOptions: [], reviewOptions, coverageOptions, stationOnlyWarning: true,
      searchPlaceholder: 'search title or id… (Abra River, senate_a3:p1:r6)',
      agencyHeading: 'NIA', AgencyAmount, Rail,
      SupportingDocsCell,
      Coordinates: ({ project }) => {
        const [first, ...rest] = project.coordinatePoints
        if (!first) return <span aria-label="No linked workbook coordinates">—</span>
        return <>
          <small>{formatMapPoint(first)}{rest.length ? ` +${rest.length}` : ''}</small>
          <button type="button" className="linkish" aria-haspopup="dialog" onClick={(event) => {
            event.stopPropagation()
            setMapProject(project)
          }}>View on map</button>
        </>
      },
      titleSorting: true, defaultTitleSort: 'senate:asc',
      flagOptions: options('flag_category', flagCategories, 'Any finding')
        .map(([value, text]) => [value, text, flagCategoryGroups[value]]),
      fixOptions: options('disposition', fixCategories, 'Any fix'),
      Evidence: (props) => <Evidence {...props} sources={bundle.agency_sources} />,
      ...(compare ? {
        explorerOnly: true,
        explorerEager: true,
        infiniteScroll: true,
        compareTitles: TITLE_COMPARE,
        titleDiffOptions: TITLE_DIFF_OPTIONS,
        explorerHeading: 'Title comparison',
      } : {}),
    }
  }, [bundle, compare])

  if (error) return <p role="alert">Unable to load the NIA export ({error}).</p>
  if (!bundle) return <div className="loading" role="status">Loading NIA records…</div>

  const totals = Object.fromEntries(Object.entries(bundle.totals).map(([stage, data]) =>
    [`${stage}_m`, data.amount_php / 1e6]))
  const counts = {
    senate_insertion: projects.filter((p) => p.actions.house_senate === 'Insertion').length,
    senate_restoration: projects.filter((p) => p.actions.house_senate === 'NEP restored').length,
    cuts: projects.filter((p) => p.senate?.status === 'cut').length,
    matched: projects.filter((p) => p.type === 'house' && p.senate).length,
    titleChanged: projects.filter((p) => p.titleDiff === 'changed').length,
    withDocs: projects.filter((p) => p.supportingDocs).length,
  }
  const delta = (bundle.totals.senate.amount_php - bundle.totals.house.amount_php) / 1e6
  return <><ProvenancePage data={{ projects, ...geography, manifest: { totals: { ...totals, counts } } }}
    config={config}
    header={<>
      <h1>{compare
        ? 'NIA Title Comparison — FY2027 stages'
        : 'NIA Provenance Explorer — FY2027 budget chain'}</h1>
      <span className="sub">{compare
        ? 'Side-by-side titles across NEP · House · NIA workbooks · Senate Annex A-3'
        : 'NEP · House HB 10858 · NIA workbooks · Senate Annex A-3'}</span>
      <div className="badges"><span className="badge">{bundle.totals.nep.rows} NEP · {bundle.totals.house.rows} House · {bundle.totals.senate.rows} Senate rows</span></div>
      <a href="./index.html">FMR Provenance Explorer</a>
      {' · '}
      <a href="./dpwh.html">DPWH Provenance Explorer</a>
      {' · '}
      <NiaSectionNav current={compare ? 'titles' : 'provenance'} />
      <Downloads program="nia" />
    </>}
    footer={`NIA ledger ${bundle.inputs['data_formalization/data/ledger/nia.jsonl'].slice(0, 8)} · ${projects.length.toLocaleString()} chain records`}>
    <div className="kpirow">
      {compare ? <>
        <Kpi lab="Chains" val={projects.length.toLocaleString()} note="all NIA explorer records" />
        <Kpi lab="Title differs" val={counts.titleChanged.toLocaleString()}
          note="linked stages disagree on the project title" />
        <Kpi lab="House ↔ Senate" val={`${counts.matched}/${bundle.totals.house.rows}`}
          note="House projects linked to Annex A-3" />
        <Kpi lab="Supporting docs" val={counts.withDocs.toLocaleString()}
          note="chains with [POW FOR REVIEW] packages attributed" />
      </> : <>
        <Kpi lab="NEP proposal" val={{ v: fmtM(totals.nep_m), color: 'var(--nep)' }} note={`${bundle.totals.nep.rows} projects`} />
        <Kpi lab="House bill" val={{ v: fmtM(totals.house_m), color: 'var(--house)' }} note={`${bundle.totals.house.rows} projects`} />
        <Kpi lab="Senate committee" val={{ v: fmtM(totals.senate_m), color: 'var(--senate)' }}
          note={`${counts.cuts} cuts to zero · ${counts.senate_restoration} NEP restorations · ${counts.senate_insertion} insertions`} />
        <Kpi lab="Senate vs House" val={{ v: `${delta < 0 ? '−' : delta > 0 ? '+' : ''}${fmtM(Math.abs(delta))}`,
          color: delta < 0 ? 'var(--cut)' : delta > 0 ? 'var(--raised)' : 'var(--text)' }} />
        <Kpi lab="NIA workbook links" val={`${bundle.agency_totals.nov13.linked}/${bundle.agency_totals.nov13.leaves}`}
          note="November 13 numeric leaves linked to NEP" />
        <Kpi lab="Match audit" val={`${counts.matched}/${bundle.totals.house.rows}`} note="House projects linked to Annex A-3" />
      </>}
    </div>
  </ProvenancePage>
    {mapProject && <NiaCoordinateMap project={mapProject} onClose={() => setMapProject(null)} />}
  </>
}

export {
  adapt, aggregate, AgencyAmount, Rail, Evidence, stageActions, typeOptions, typeLabels,
  grouping, reviewOptions, coverageOptions, flagCategories, flagCategoryGroups, fixCategories,
  humanize, stationOnlyFlag, SupportingDocsCell, SupportingDocsEvidence,
}

export function NiaExplorerApp({ mode = 'explorer' } = {}) {
  return <App mode={mode} />
}

if (document.documentElement.dataset.page === 'nia') {
  createRoot(document.getElementById('app')).render(<App />)
}
