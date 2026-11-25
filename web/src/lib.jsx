import { useEffect, useMemo, useRef, useState } from 'react'

// ---- shared helpers / labels ------------------------------------------------

export function fmtBudget(value, currency = '') {
  if (value == null) return '—'
  const magnitude = Math.abs(value)
  const [divisor, suffix] = magnitude >= 1e9 ? [1e9, 'B']
    : magnitude >= 1e6 ? [1e6, 'M']
    : magnitude >= 1e3 ? [1e3, 'K'] : [1, '']
  const digits = Math.log10(divisor)
  const num = (Math.abs(value) / divisor).toLocaleString('en-US', { maximumFractionDigits: digits })
  return (value < 0 ? '-' : '') + currency + num + suffix
}

export const fmtM = (value) => fmtBudget(value == null ? null : Math.round(value * 1e6), '₱')

export const stageColor = { nep: '#4f8ff7', house: '#f5a623', da: '#9b59d0', senate: '#2fbf71' }
export const statusOrder = ['cut', 'realigned', 'possible_restatement', 'renamed', 'raised', 'reduced', 'inserted', 'reinstated']
export const statusLabel = {
  cut: 'cut', realigned: 'realigned', possible_restatement: 'possible restatement', renamed: 'renamed', restated: 'relisted',
  raised: 'raised', reduced: 'reduced', inserted: 'inserted',
  reinstated: 'reinstated', none: '—',
}
export const reasonLabel = {
  coords: 'GPS coordinates corrected (title unchanged)',
  title: 'project name corrected',
  title_and_coords: 'name and GPS coordinates corrected',
  restatement: 'restated with the same title and coordinates',
}
export const typeLabel = {
  house: 'House chain',
  nep_only: 'NEP only — never made the House bill',
  senate_insertion: 'Senate insertion — new annex row',
  da_only: 'DA draft only — not linked to NEP/House',
}
export const typeShort = {
  house: 'House chain', nep_only: 'NEP only',
  senate_insertion: 'Senate insertion', da_only: 'DA only',
}
export const statusColor = {
  cut: '#e05252', realigned: '#c27ae0', possible_restatement: '#ffd19a', renamed: '#4f8ff7', raised: '#2fbf71',
  reduced: '#e08e37', inserted: '#f5a623', dropped: '#6b7380',
  reinstated: '#35c9c0', 'House insertions': '#c48a1a',
}

// per-stage action vocabularies (exporter stamps rec.actions per record)
export const actionStages = [
  { key: 'nep_house', label: 'NEP → House' },
  { key: 'house_da', label: 'House → DA' },
  { key: 'house_senate', label: 'House → Senate' },
]
export const senateOutcomeLabels = {
  cut: 'Cut to zero',
  raised: 'Increase',
  reduced: 'Decrease',
  renamed: 'Title revised',
  inserted: 'Senate inserted',
  realigned: 'Realigned',
  reinstated: 'Reinstated',
  left_at_nep: 'Left at NEP',
  possible_restatement: 'Possible restatement',
  restated: 'Restated',
  unchanged: 'No amount change',
  no_senate_record: 'No Senate record',
  'NEP restored': 'NEP funding restored',
}

export const senateInsertedDescription = 'The Senate committee added funding for a project with no NEP or House allocation found in the records.'

const senateOutcomeAliases = {
  'Cut to zero': 'cut', Increase: 'raised', Decrease: 'reduced',
  'Revised description': 'renamed', Insertion: 'inserted',
  'No amount change': 'unchanged', 'No Senate record': 'no_senate_record',
}

export function senateOutcome(project) {
  const action = project.actions?.house_senate
  if (!project.senate) {
    if (action === 'left_at_nep' || action === 'possible_restatement') return action
    return project.house_m != null ? 'no_senate_record' : undefined
  }
  return senateOutcomeAliases[action] ?? action
}

export const senateFlagLabels = {
  'Title revised': 'Title revised',
  'Foreign-assisted': 'Foreign-assisted',
  'House insertion candidate': 'House insertion candidate',
}

export function senateFlags(project) {
  const flags = project.stageNotes?.house_senate ?? []
  const senate = project.raw?.senate ?? project.senate
  const before = senate?.hb_title
  const after = senate?.senate_title
  return [...new Set([
    ...flags,
    (senateOutcome(project) === 'renamed' || titlesDiffer(before, after)) && 'Title revised',
  ].filter((label) => Object.hasOwn(senateFlagLabels, label)))]
}

export const actionLabel = {
  // NEP → House
  carried: 'carried', dropped: 'dropped', house_insertion: 'house insertion',
  reinstated: 'reinstated',
  // House → DA (DA dispositions)
  retain: 'retain', modified: 'modified', new: 'DA insertion', list_revision: 'list revision',
  no_da: 'no draft', none: '—',
  // House → Senate (Annex A-1) + shared
  cut: 'cut', realigned: 'realigned', possible_restatement: 'possible restatement', renamed: 'renamed', raised: 'raised',
  reduced: 'reduced', restated: 'restated', inserted: 'inserted', 'NEP restored': 'NEP restored',
  unchanged: 'unchanged', left_at_nep: 'left at NEP',
}
export const actionColor = {
  Proposed: 'var(--nep)', 'Same amount': 'var(--nep)', 'Amount changed': 'var(--reduced)',
  'House without NEP link': 'var(--inserted)', 'NEP without House link': 'var(--dim)',
  Reconciled: 'var(--raised)', 'Cut to zero': 'var(--cut)', Insertion: 'var(--inserted)',
  Increase: 'var(--raised)', Decrease: 'var(--reduced)', 'Revised description': 'var(--renamed)',
  'No amount change': 'var(--dim)', 'No Senate record': 'var(--dim)',
  'NEP restored': 'var(--reinstated)',
  carried: '#4f8ff7', dropped: '#6b7380', house_insertion: '#c48a1a',
  reinstated: '#35c9c0',
  retain: '#2fbf71', modified: '#e08e37', new: '#f5a623',
  list_revision: '#8b96a8', no_da: '#6b7380',
  cut: '#e05252', realigned: '#c27ae0', possible_restatement: '#ffd19a', renamed: '#4f8ff7', raised: '#2fbf71',
  reduced: '#e08e37', restated: '#8b96a8', inserted: '#f5a623',
  unchanged: '#6b7380', no_senate_record: '#8b96a8', left_at_nep: '#6b7380',
}
// actions that actually moved money / changed the project (for churn)
export const actionChurn = new Set(['dropped', 'reinstated', 'house_insertion',
  'cut', 'realigned', 'reinstated', 'reduced', 'modified', 'new', 'inserted'])

export function actionsOf(rec) {
  return rec.actions || {}
}

export function useLedger() {
  const [data, setData] = useState(null)
  useEffect(() => {
    const load = async (p) => (await fetch(p)).json()
    Promise.all([
      load('data/fmr/manifest.json'), load('data/fmr/regions.json'),
      load('data/fmr/projects.json'), load('data/fmr/localities.json'),
    ]).then(([manifest, regions, projects, localities]) =>
      setData({ manifest, regions, projects, localities }))
      .catch((e) => console.error('ledger load failed', e))
  }, [])
  return data
}

// ---- diff helpers -----------------------------------------------------------

export function normTitle(s) {
  return (s || '').replace(/\s+/g, ' ').trim().toLowerCase()
}
export function titlesDiffer(a, b) {
  if (a == null || b == null) return false
  return normTitle(a) !== normTitle(b)
}
export function coordsKey(arr) {
  return Array.isArray(arr) && arr.length ? arr.join('|') : ''
}
export function coordsDiffer(a, b) {
  const ka = coordsKey(a), kb = coordsKey(b)
  return ka && kb && ka !== kb
}
export function amtDelta(from, to) {
  if (from == null || to == null) return null
  const d = Number(to) - Number(from)
  if (!d) return { kind: 'same', text: 'amount unchanged ' + fmtM(to) }
  const sign = d > 0 ? '+' : '−'
  return { kind: d > 0 ? 'up' : 'down',
    text: `amount ${sign}${fmtM(Math.abs(d))} (${fmtM(from)} → ${fmtM(to)})` }
}
export function fmtCoords(arr) {
  return Array.isArray(arr) && arr.length ? arr.join('\n') : null
}

export function Chip({ text, cls }) {
  return <span className={'dchip ' + (cls || '')}>{text}</span>
}

// ---- chips per stage transition --------------------------------------------

export function nepHouseChips(rec) {
  const chips = []
  if (rec.type === 'nep_only') {
    chips.push({ text: 'dropped — never reached House', cls: 'down' })
    return chips
  }
  if (rec.house_m == null) return chips
  if (!rec.nep) {
    chips.push({ text: 'House insertion (not in NEP)', cls: 'warn' })
    chips.push({ text: fmtM(rec.house_m), cls: 'info' })
    return chips
  }
  const d = amtDelta(rec.nep.amount_m, rec.house_m)
  if (d) chips.push({ text: d.text, cls: d.kind === 'same' ? 'muted' : d.kind })
  if (titlesDiffer(rec.nep.title, rec.title)) chips.push({ text: 'title revised', cls: 'info' })
  else chips.push({ text: 'title same', cls: 'muted' })
  if (rec.nep.match) chips.push({ text: 'match: ' + rec.nep.match, cls: 'muted' })
  return chips
}

export function houseDaChips(rec) {
  const chips = []
  const da = rec.da12 || rec.da5
  if (!da) {
    chips.push({ text: 'no DA draft linked', cls: 'muted' })
    return chips
  }
  const disp = da.disposition || '—'
  const cls = disp === 'dropped' ? 'down'
    : disp === 'retain' ? 'muted'
    : disp === 'modify' || disp === 'new' ? 'warn' : 'info'
  chips.push({ text: 'DA ' + disp, cls })
  const d = amtDelta(da.from_m, da.proposed_m)
  if (d && d.kind !== 'same') chips.push({ text: d.text, cls: d.kind })
  else if (d) chips.push({ text: d.text, cls: 'muted' })
  if (rec.da5 && rec.da12) {
    if (rec.da5.disposition !== rec.da12.disposition)
      chips.push({ text: `Nov5 ${rec.da5.disposition} → Nov12 ${rec.da12.disposition}`, cls: 'warn' })
    else if ((rec.da5.proposed_m ?? null) !== (rec.da12.proposed_m ?? null))
      chips.push({ text: `Nov5 ${fmtM(rec.da5.proposed_m)} → Nov12 ${fmtM(rec.da12.proposed_m)}`, cls: 'info' })
    else chips.push({ text: 'Nov5 = Nov12', cls: 'muted' })
  }
  if (rec.da_revision) chips.push({ text: 'DA revised listing', cls: 'info' })
  return chips
}

export function houseSenateChips(rec) {
  const chips = []
  if (!rec.senate) {
    chips.push({ text: 'unchanged (not listed in Annex A-1)', cls: 'muted' })
    return chips
  }
  const st = rec.senate.status
  const stCls = st === 'cut' ? 'down' : st === 'realigned' ? 'purple'
    : st === 'raised' ? 'up' : st === 'reduced' ? 'down'
    : st === 'renamed' ? 'info' : 'muted'
  chips.push({ text: 'Senate ' + (statusLabel[st] || st), cls: stCls })

  const fromAmt = rec.senate.gab_m ?? rec.house_m
  const toAmt = st === 'realigned' && rec.restated_by
    ? rec.restated_by.sv_m
    : rec.senate.sv_m
  const d = amtDelta(fromAmt, toAmt)
  if (d) chips.push({ text: d.text, cls: d.kind === 'same' ? 'muted' : d.kind })

  if (st === 'realigned' && rec.restated_by) {
    const why = reasonLabel[rec.restated_by.reason] || 'corrected'
    chips.push({ text: why, cls: 'purple' })
  } else {
    const hb = rec.senate.hb_title, sv = rec.senate.senate_title
    if (titlesDiffer(hb, sv)) chips.push({ text: 'title revised', cls: 'info' })
    if (coordsDiffer(rec.senate.hb_coords, rec.senate.senate_coords))
      chips.push({ text: 'GPS corrected', cls: 'info' })
  }
  return chips
}
