import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { fmtBudget, statusLabel, statusOrder, typeShort,
         actionStages, actionLabel, actionColor } from './lib.jsx'
import Detail from './Detail.jsx'
import StageRail from './StageRail.jsx'

const PAGE = 60
const REVIEW_OPTIONS = [
  ['', 'Any review status'],
  ['flagged', 'Flagged in review'],
  ['pending', 'Pending review'],
  ['fixed', 'Documented fix'],
]

const FLAG_OPTIONS = [
  ['', 'Any finding'],
  ['location_check', 'PSGC verification', 'Location'],
  ['location_mismatch', 'Location mismatch', 'Location'],
  ['unknown_locality', 'Locality missing from PSGC', 'Location'],
  ['outside_endpoint', 'Endpoint outside locality', 'Location'],
  ['invalid_gps', 'Invalid coordinates', 'Coordinates'],
  ['gps_check', 'Coordinate check', 'Coordinates'],
  ['reversed_gps', 'Reversed latitude/longitude', 'Coordinates'],
  ['gps_typo', 'Printed coordinate typo', 'Coordinates'],
]

const FIX_OPTIONS = [
  ['', 'Any fix'],
  ['title_fix', 'Title correction'],
  ['coordinate_fix', 'Coordinate correction'],
  ['combined_fix', 'Title and coordinates'],
  ['other_fix', 'Other documented correction'],
]

const FLAG_TYPE_KEYS = {
  'PSGC location check (verify manually)': 'location_check',
  'PSGC location mismatch (barangay/town/province/region)': 'location_mismatch',
  'Locality not found in PSGC list': 'unknown_locality',
  'Endpoint outside title locality (Nov 14 boundary review)': 'outside_endpoint',
  'Invalid coordinates (impossible span / at sea / missing endpoint)': 'invalid_gps',
  'Coordinate check (reversed or over 15 km span)': 'gps_check',
  'Printed lat/long reversed': 'reversed_gps',
  'Printed coordinate typo corrected in reading': 'gps_typo',
}

function fixType(description) {
  const title = /\btitle\b/i.test(description)
  const coordinates = /\bcoordinates\b/i.test(description)
  if (title && coordinates) return 'combined_fix'
  if (title) return 'title_fix'
  if (coordinates) return 'coordinate_fix'
  return 'other_fix'
}

const COMPARISON_OPTIONS = [
  ['', 'Any comparison'],
  ['exact', 'Exact DA match'],
  ['title_differs', 'Possible DA → Senate match'],
  ['possible', 'Title or GPS clue'],
  ['unmatched', 'No DA match'],
]

function daSenateMatch(project) {
  if (project.da_revision || project.da_evidence?.exact) return 'exact'
  if (project.da_evidence?.id) return 'title_differs'
  if (project.da_evidence) return 'possible'
  if (project.type === 'senate_insertion') return 'unmatched'
  return ''
}

function pairedSenateEntry(project) {
  const match = project.da_replacement || project.possible_senate_restatement
  return match?.amount_m != null ? match : undefined
}

const tableAmount = (value) => fmtBudget(value == null ? null : Math.round(value * 1e6))

function DaAmount({ project }) {
  const nov5 = (project.da_revision?.da5 ?? project.da5)?.proposed_m
  const nov12 = (project.da_revision?.da12 ?? project.da12)?.proposed_m
  if (nov5 == null && nov12 == null) return '—'
  if (nov5 == null || nov5 === nov12) return tableAmount(nov12)
  if (nov12 == null) return (
    <>{tableAmount(nov5)} <small className="amount-draft">Nov 5</small></>
  )
  return (
    <>
      {tableAmount(nov12)} <small className="amount-draft">Nov 12</small>
      <div className="amount-draft">{tableAmount(nov5)} Nov 5</div>
    </>
  )
}

function stageValues(project, key) {
  return [...new Set([project.actions?.[key], ...(project.stageNotes?.[key] ?? [])].filter(Boolean))]
}

// Chip row for a facet. Options are [value, label, group?] tuples. Each group
// is its own line (subheader + chips); ungrouped options (the "any" reset)
// sit on a line of their own above. Groups keep first-appearance order.
function ChipRow({ options, selected, setSelected, countLabel, facetKey, ariaLabel }) {
  const ungrouped = options.filter(([, , group]) => !group)
  const groups = []
  for (const [, , group] of options) {
    if (group && !groups.includes(group)) groups.push(group)
  }
  const chip = ([value, text]) => (
    <button type="button" key={value} className="chip" aria-pressed={selected === value}
            onClick={() => setSelected(selected === value ? '' : value)}>
      {text} ({countLabel(facetKey, value)})
    </button>
  )
  return <div className="chip-groups" role="group" aria-label={ariaLabel}>
    {ungrouped.length > 0 && <div className="chips">{ungrouped.map(chip)}</div>}
    {groups.map((group) => (
      <div className="chips chip-group" key={group}>
        <span className="chip-sub">{group}</span>
        {options.filter(([, , g]) => g === group).map(chip)}
      </div>
    ))}
  </div>
}

const titleCollator = new Intl.Collator('en', { sensitivity: 'base', ignorePunctuation: true, numeric: true })

export default function Explorer({ projects, regions, localities, locality, setLocalityKey, config }) {
  const stages = config?.stages ?? actionStages
  const reviewOptions = config?.reviewOptions ?? REVIEW_OPTIONS
  const coverageOptions = config?.coverageOptions
  const titleDiffOptions = config?.titleDiffOptions
  const compareTitles = config?.compareTitles
  const infiniteScroll = !!config?.infiniteScroll
  const flagOptions = config?.flagOptions ?? FLAG_OPTIONS
  const fixOptions = config?.fixOptions ?? FIX_OPTIONS
  const comparisonOptions = config?.comparisonOptions ?? COMPARISON_OPTIONS
  const actionNames = config?.actionNames ?? actionLabel
  const Rail = config?.Rail ?? StageRail
  const Evidence = config?.Evidence ?? Detail
  const AgencyAmount = config?.AgencyAmount ?? DaAmount
  const SupportingDocsCell = config?.SupportingDocsCell
  const Coordinates = config?.Coordinates
  const senateOptions = config?.senateOptions ?? statusOrder.map((key) => [key, statusLabel[key]])
  const typeOptions = config?.typeOptions ?? [
    ['house', 'House project'], ['nep_only', 'NEP without House link'],
    ['senate_insertion', 'Senate insertion'], ['da_only', 'DA without NEP/House link'],
  ]
  const [q, setQ] = useState(() => new URLSearchParams(window.location.search).get('q') || '')
  const [region, setRegion] = useState('')
  const [status, setStatus] = useState('')
  const [type, setType] = useState('')
  const [review, setReview] = useState('')
  const [flagType, setFlagType] = useState('')
  const [fix, setFix] = useState('')
  const [coverage, setCoverage] = useState('')
  const [titleDiff, setTitleDiff] = useState('')
  const [titleSort, setTitleSort] = useState(config?.defaultTitleSort ?? '')
  const [comparison, setComparison] = useState('')
  const [acts, setActs] = useState({})   // stage key -> action key
  const [page, setPage] = useState(0)
  const [visible, setVisible] = useState(PAGE)
  const [sel, setSel] = useState(null)
  const scrollRoot = useRef(null)
  const sentinel = useRef(null)

  // municipalities visible under current region filter
  const muniOptions = useMemo(
    () => localities.filter((l) => !region || l.region === region),
    [localities, region])

  const explorerProjects = useMemo(() => {
    if (config) return projects
    const byId = new Map(projects.map((project) => [project.id, project]))
    return projects.map((project) => {
      const source = byId.get(project.da_evidence?.id)
      if (pairedSenateEntry(project)) {
        const actions = { ...project.actions, house_senate: 'possible_restatement' }
        const replacement = byId.get(project.da_replacement?.id)
        if (!replacement) return { ...project, actions }
        return {
          ...project, actions: { ...actions, house_da: replacement.actions.house_da },
          da_evidence: replacement.da_evidence,
          da_revision: {
            ctrl: project.da_replacement.ctrl, senate_id: replacement.id,
            da5: replacement.da5, da12: replacement.da12,
          },
        }
      }
      if (source?.possible_senate_match?.id !== project.id) return project
      return {
        ...project, da5: source.da5, da12: source.da12,
        actions: { ...source.actions, ...project.actions },
      }
    })
  }, [projects, config])

  const pairedInsertions = useMemo(
    () => new Set(config ? [] : projects.flatMap((project) => [
      project.restated_by?.id, project.da_evidence?.id,
      pairedSenateEntry(project)?.id,
    ]).filter(Boolean)),
    [projects, config]
  )

  const stageActions = useMemo(() => stages.map((stage) => {
    const counts = {}
    for (const project of explorerProjects) {
      if (pairedInsertions.has(project.id)) continue
      for (const action of stageValues(project, stage.key)) counts[action] = (counts[action] || 0) + 1
    }
    const options = Object.keys(counts).sort((a, b) => counts[b] - counts[a])
    return { ...stage, counts, options }
  }), [explorerProjects, pairedInsertions, stages])

  const reviewStatuses = useMemo(() => new Map(explorerProjects.map((project) => {
    if (config) return [project.id, project.reviewStatus]
    const findings = [...(project.da_reviews?.nov5 || []), ...(project.da_reviews?.nov12 || [])]
    const types = new Set(findings.flatMap((finding) => (finding.types || [])
      .map((type) => FLAG_TYPE_KEYS[type]).filter(Boolean)))
    const fixes = new Set(findings.filter((finding) => finding.status.startsWith('FIXED'))
      .map((finding) => fixType(finding.status)))
    const correction = project.da_revision?.da12
      || (project.da_replacement_of ? project.da12 : undefined)
    if (correction) {
      fixes.add(fixType(correction.remark || (correction.disposition === 'list_revision' ? 'title' : 'coordinates')))
    }
    return [project.id, {
      flagged: findings.length > 0,
      pending: (project.da_reviews?.nov12 || project.da_reviews?.nov5 || [])
        .some((finding) => finding.status.startsWith('PENDING')),
      fixed: fixes.size > 0,
      ...Object.fromEntries([...types, ...fixes].map((key) => [key, true])),
    }]
  })), [explorerProjects, config])

  const needle = q.trim().toLowerCase()
  const searchMatches = useMemo(() => explorerProjects.filter((r) => {
    const id = r.id.toLowerCase()
    if (needle !== id && pairedInsertions.has(r.id)) return false
    if (pairedSenateEntry(r)?.id === needle) return false
    if (!needle) return true
    if (config) return r.searchText.includes(needle)
    return [r.title, id, r.senate?.id, r.restated_by?.title, r.da_revision?.da12.title,
      r.da_revision?.ctrl, r.da_evidence?.title, pairedSenateEntry(r)?.title, r.da12?.ctrl, r.da5?.ctrl]
      .some((value) => value?.toLowerCase().includes(needle))
  }), [needle, explorerProjects, pairedInsertions, config])

  const { filtered, counts } = useMemo(() => {
    const facetKeys = [
      'review', 'flagType', 'fix',
      ...(senateOptions.length ? ['status'] : []), ...(coverageOptions ? ['coverage'] : []),
      ...(titleDiffOptions ? ['titleDiff'] : []),
      ...(comparisonOptions.length ? ['comparison'] : []), ...stages.map(({ key }) => key),
    ]
    const counts = Object.fromEntries(facetKeys.map((key) => [key, new Map()]))
    const filtered = []
    const selected = { status, review, flagType, fix, comparison, coverage, titleDiff, ...acts }

    for (const project of searchMatches) {
      const place = project.municipality ? `${project.province}|${project.municipality}` : ''
      if (region && project.region !== region) continue
      if (locality && place !== locality.key) continue
      if (type && project.type !== type) continue

      const review = reviewStatuses.get(project.id)
      const reviewValues = (options) => options.map(([key]) => key).filter((key) => review[key])
      const values = {
        status: [project.actions?.house_senate],
        review: reviewValues(reviewOptions),
        flagType: reviewValues(flagOptions),
        fix: reviewValues(fixOptions),
        coverage: [project.coordinateCoverage],
        titleDiff: [project.titleDiff],
        comparison: [daSenateMatch(project)],
        ...Object.fromEntries(stages.map(({ key }) => [key, stageValues(project, key)])),
      }
      const mismatches = facetKeys.filter((key) => selected[key] && !values[key].includes(selected[key]))
      if (!mismatches.length) filtered.push(project)
      for (const key of mismatches.length === 1 ? mismatches : mismatches.length ? [] : facetKeys) {
        const facet = counts[key]
        for (const value of ['', ...values[key].filter(Boolean)]) {
          facet.set(value, (facet.get(value) || 0) + 1)
        }
      }
    }
    return { filtered, counts }
  }, [region, locality, type, status, review, flagType, fix, comparison, coverage, titleDiff, acts, searchMatches, reviewStatuses, stages, flagOptions, fixOptions, comparisonOptions, reviewOptions, coverageOptions, titleDiffOptions, senateOptions.length])
  const hiddenMatches = needle ? searchMatches.length - filtered.length : 0
  const countLabel = (key, value) => (counts[key].get(value) || 0).toLocaleString()
  useEffect(() => {
    setPage(0)
    setVisible(PAGE)
  }, [q, region, locality, type, status, review, flagType, fix, comparison, coverage, titleDiff, acts])

  useEffect(() => {
    if (!infiniteScroll || !sentinel.current || !scrollRoot.current) return
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return
      setVisible((count) => Math.min(count + PAGE, filtered.length))
    }, { root: scrollRoot.current, rootMargin: '160px' })
    observer.observe(sentinel.current)
    return () => observer.disconnect()
  }, [infiniteScroll, filtered.length, visible])

  const sorted = useMemo(() => {
    if (!titleSort) return filtered
    const [key, direction] = titleSort.split(':')
    const sortTitle = (row) => key === 'project' ? row.title
      : key === 'base' ? row.baseTitle : row.stageTitles?.[key]
    return [...filtered].sort((a, b) => {
      const first = sortTitle(a)?.trim()
      const second = sortTitle(b)?.trim()
      if (!first || !second) return Number(!first) - Number(!second)
      const order = titleCollator.compare(first, second)
      return direction === 'desc' ? -order : order
    })
  }, [filtered, titleSort])

  const pageRows = infiniteScroll
    ? sorted.slice(0, visible)
    : sorted.slice(page * PAGE, page * PAGE + PAGE)
  const maxPage = Math.max(0, Math.ceil(filtered.length / PAGE) - 1)

  return (
    <div className="panel">
      <h2>{config?.explorerHeading ?? 'Project explorer'} — {filtered.length.toLocaleString()} chains {locality && <span className="sflow">· {locality.municipality}</span>}</h2>
      <div className="filters">
        <input type="search" aria-label="Search projects" placeholder={config?.searchPlaceholder ?? "search title or id… (Tubburan, ib:p667)"}
               value={q} onInput={(e) => setQ(e.target.value)} />
        {config?.titleSorting && <select aria-label="Sort by title" value={titleSort} onChange={(e) => {
          setTitleSort(e.target.value)
          setPage(0)
          setVisible(PAGE)
          if (scrollRoot.current) scrollRoot.current.scrollTop = 0
        }}>
          <option value="">Sort by: Source order</option>
          {[{ key: 'project', label: 'Project title' }, ...(compareTitles ?? [{ key: 'senate', label: 'Senate title' }])].map(({ key, label }) => (
            <Fragment key={key}>
              <option value={key + ':asc'}>{label} (A–Z)</option>
              <option value={key + ':desc'}>{label} (Z–A)</option>
            </Fragment>
          ))}
        </select>}
        <select aria-label="Region" value={region} onChange={(e) => {
          const next = e.target.value
          setRegion(next)
          if (next && locality && locality.region !== next) setLocalityKey('')
        }}>
          <option value="">All regions</option>
          {regions.map((r) => <option key={r.key} value={r.key}>{r.label || r.key}</option>)}
        </select>
        {(!config || config.grouping) && <select value={locality?.key ?? ''} onChange={(e) => setLocalityKey(e.target.value)}>
          <option value="">{config?.grouping ? 'All provinces' : 'All municipalities'}</option>
          {muniOptions.map((l) => (
            <option key={l.key} value={l.key}>
              {l.municipality} — {l.province} ({l.chains})
            </option>
          ))}
        </select>}
        <select aria-label="Chain type" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All chain types</option>
          {typeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        {senateOptions.length > 0 && <div className="chips" role="group" aria-label="Senate status">
          {senateOptions.map(([value, label]) => (
            <button type="button" key={value} className="chip" aria-pressed={status === value}
                    onClick={() => setStatus(status === value ? '' : value)}>
              {label} ({countLabel('status', value)})
            </button>
          ))}
        </div>}
      </div>
      <div className="actionrows">
        <div className="filters">
          <span className="sflow">Review status</span>
          <div className="chips" role="group" aria-label="Review status">
            {reviewOptions.map(([value, label]) => (
              <button type="button" key={value} className="chip"
                      aria-pressed={review === value}
                      onClick={() => setReview(review === value ? '' : value)}>
                {label} ({countLabel('review', value)})
              </button>
            ))}
          </div>
        </div>
        {[
          ['Finding type', 'flagType', flagOptions, flagType, setFlagType],
          ['Fix type', 'fix', fixOptions, fix, setFix],
          ...(coverageOptions ? [['November GPS coverage', 'coverage', coverageOptions, coverage, setCoverage]] : []),
          ...(titleDiffOptions ? [['Title across stages', 'titleDiff', titleDiffOptions, titleDiff, setTitleDiff]] : []),
        ].map(([label, key, options, selected, setSelected]) => (
          <div className="filters" key={label}>
            <span className="sflow">{label}</span>
            <ChipRow options={options} selected={selected} setSelected={setSelected}
                     countLabel={countLabel} facetKey={key} ariaLabel={label} />
          </div>
        ))}
        {comparisonOptions.length > 0 && (
          <div className="filters">
            <span className="sflow">DA → Senate</span>
            <div className="chips" role="group" aria-label="DA to Senate comparison">
              {comparisonOptions.map(([value, label]) => (
                <button type="button" key={value} className="chip"
                        aria-pressed={comparison === value}
                        onClick={() => setComparison(comparison === value ? '' : value)}>
                  {label} ({countLabel('comparison', value)})
                </button>
              ))}
            </div>
          </div>
        )}
        {stageActions.map(({ key, label, options }) => {
          const val = acts[key] || ''
          return (
            <div className="filters" key={key} style={{ marginBottom: 4 }}>
              <span className="sflow" style={{ minWidth: 96, marginTop: 0 }}>{label}</span>
              <div className="chips" role="group" aria-label={label}>
                <button type="button" className="chip" aria-pressed={!val}
                        onClick={() => setActs((s) => ({ ...s, [key]: '' }))}>Any ({countLabel(key, '')})</button>
                {options.map((o) => (
                  <button type="button" key={o} className="chip" aria-pressed={val === o}
                          onClick={() => setActs((s) => ({ ...s, [key]: val === o ? '' : o }))}>
                    {actionNames[o] || o} ({countLabel(key, o)})
                  </button>
                ))}
              </div>
            </div>
          )
        })}
      </div>
      <details className="action-legend">
        <summary>Action color legend</summary>
        <div className="filters">
          <span className="review-open">⚑ Flagged or pending</span>
          {config?.stationOnlyWarning && <span className="review-warning">⚑ No coordinates · system or station only</span>}
          <span className="review-fixed">✓ Correction recorded</span>
          <span className="review-removed">− Dropped or omitted</span>
        </div>
        {stageActions.map(({ key, label, options }) => (
          <div className="filters" key={key}>
            <span>{label}</span>
            {options.map((action) => (
              <span key={action} className="st act-pill"
                    style={{ color: actionColor[action] || '#8b96a8',
                             borderColor: actionColor[action] || '#8b96a8' }}>
                {actionNames[action] || action}
              </span>
            ))}
          </div>
        ))}
      </details>
      <div role="status" className="search-filter-feedback">
        {hiddenMatches > 0 && (
          <span>{hiddenMatches.toLocaleString()} {hiddenMatches === 1 ? 'result' : 'results'} outside current filters</span>
        )}
      </div>
      <div className={`tablewrap${compareTitles ? ' title-compare' : ''}`} ref={scrollRoot}><table>
        <thead><tr>
          {compareTitles
            ? compareTitles.map(({ key, label, derived }) => <th scope="col" key={key}
                className={derived ? 'title-col title-base' : 'title-col'}>{label}</th>)
            : <th scope="col">Project</th>}
          <th scope="col" className="region-col">Region</th>
          {!compareTitles && <>
            <th scope="col" className="num">NEP</th><th scope="col" className="num">House</th>
            <th scope="col" className="num">{config?.agencyHeading ?? 'DA'}</th>
            <th scope="col" className="num">Senate</th>
          </>}
          {Coordinates && <th scope="col">Coordinates</th>}
          {SupportingDocsCell && <th scope="col">Supporting docs</th>}
          {!compareTitles && <th scope="col">Actions by stage</th>}
        </tr></thead>
        <tbody>
          {pageRows.map((r) => (
              <tr className="row" key={r.id} onClick={() => setSel({ record: r })}>
                {compareTitles
                  ? compareTitles.map(({ key, derived }, i) => {
                      if (derived) {
                        return <td key={key} className="title-col title-base">
                          {r.baseTitle || <span className="title-missing">—</span>}
                          {r.baseTitleVaries && <span className="tag">heading varies</span>}
                          {r.type !== 'house' && (
                            <span className="tag">{config?.typeLabels[r.type] ?? typeShort[r.type]}</span>
                          )}
                        </td>
                      }
                      const text = r.stageTitles?.[key]
                      const prev = compareTitles.slice(0, i)
                        .map(({ key: k, derived: d }) => d ? null : r.stageTitles?.[k])
                        .filter(Boolean).at(-1)
                      const changed = text && prev && text.replace(/\s+/g, ' ').trim().toLowerCase()
                        !== prev.replace(/\s+/g, ' ').trim().toLowerCase()
                      const value = r.stageAmounts?.[key]
                      const ref = r.stageRefs?.[key]
                      const baselineRef = r.baselineTitleRefs?.[key]
                      return <td key={key} className={`title-col${changed ? ' title-changed' : ''}`}>
                        {text || <span className="title-missing">—</span>}
                        {value != null && <div className="title-amount">{fmtBudget(value, '₱')}</div>}
                        {ref && <div className="title-ref">{ref}</div>}
                        {baselineRef && <div className="title-ref">{baselineRef}</div>}
                        <Rail project={r} onlyStage={key} onSelect={(stage) => setSel({ record: r, stage })} />
                      </td>
                    })
                  : <td style={{ maxWidth: 420 }}>{r.title}
                      {r.restated_by && <span className="tag">realigned</span>}
                      {r.da_evidence?.id && <span className="tag possible-match-tag">Possible DA → Senate match</span>}
                      {r.da_replacement && <span className="tag possible-match-tag">DA-documented replacement</span>}
                      {pairedSenateEntry(r) && <span className="tag possible-match-tag">Possible Senate restatement</span>}
                      {r.replaces && <span className="tag">realigns cut</span>}
                      {r.type !== 'house' && <span className="tag">{config?.typeLabels[r.type] ?? typeShort[r.type]}</span>}
                    </td>}
                <td className="region-col">{r.region || '—'}</td>
                {!compareTitles && <>
                  <td className="num m">{tableAmount(r.nep?.amount_m)}</td>
                  <td className="num m">{tableAmount(r.house_m)}</td>
                  <td className="num m"><AgencyAmount project={r} /></td>
                  <td className="num m">{tableAmount(pairedSenateEntry(r)?.amount_m ?? r.senate?.sv_m
                      ?? (r.senate?.status === 'cut' ? 0 : null))}</td>
                </>}
                {Coordinates && <td className="nia-coordinate-cell"><Coordinates project={r} /></td>}
                {SupportingDocsCell && <td className="pow-docs-cell"><SupportingDocsCell docs={r.supportingDocs} /></td>}
                {!compareTitles && <td><Rail project={r} onSelect={(stage) => setSel({ record: r, stage })} /></td>}
              </tr>
          ))}
        </tbody>
      </table>
        {infiniteScroll && visible < filtered.length && (
          <div ref={sentinel} className="scroll-sentinel" aria-hidden="true" />
        )}
      </div>
      {infiniteScroll ? (
        <div className="pagination" role="status">
          Showing {pageRows.length.toLocaleString()} of {filtered.length.toLocaleString()}
          {visible < filtered.length ? ' · scroll for more' : ''}
        </div>
      ) : (
        <div className="pagination">
          <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>‹ prev</button>
          <span>{filtered.length ? page * PAGE + 1 : 0}–{Math.min(filtered.length, (page + 1) * PAGE)} of {filtered.length.toLocaleString()}</span>
          <button disabled={page >= maxPage} onClick={() => setPage((p) => p + 1)}>next ›</button>
        </div>
      )}
      {sel && <Evidence key={sel.record.id + ':' + (sel.stage || '')} rec={sel.record} initialStage={sel.stage} projects={projects}
        onClose={() => setSel(null)}
        onJump={(id, stage = 'senate') => { const t = explorerProjects.find((p) => p.id === id); if (t) setSel({ record: t, stage }) }} />}
    </div>
  )
}
