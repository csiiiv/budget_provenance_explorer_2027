import { actionColor, actionLabel, coordsDiffer, titlesDiffer, senateOutcome, senateOutcomeLabels } from './lib.jsx'

function ReviewMarks({ reviews = [], original = false, agency = 'DA' }) {
  const fixed = reviews.some((review) => review.status.startsWith('FIXED'))
  const pending = original || reviews.some((review) => review.status.startsWith('PENDING') && !review.warning)
  const warning = reviews.some((review) => review.status.startsWith('PENDING') && review.warning)
  const removed = !original && reviews.some((review) =>
    /^(RESOLVED|NOT CARRIED)/.test(review.status)
  )
  return (
    <>
      {pending && <span className="review-open" role="img" aria-label={original ? 'Flagged' : 'Pending'} title={original ? 'Flagged in source review' : 'Pending review'}>⚑</span>}
      {warning && <span className="review-warning" role="img" aria-label="System or station only" title="No coordinates · system or station only">⚑</span>}
      {!original && fixed && <span className="review-fixed" role="img" aria-label="Fixed" title={`Correction recorded in ${agency} review`}>✓</span>}
      {removed && <span className="review-removed" role="img" aria-label="Removed or not carried" title={`Dropped or not carried in the ${agency} draft`}>−</span>}
    </>
  )
}

export default function StageRail({ project, onSelect, selected }) {
  const actions = project.actions || {}
  const reviews = project.da_reviews || {}
  const flagged = [...(reviews.nov5 || []), ...(reviews.nov12 || [])]
  const daAction = (vintage) =>
    (project.da_revision?.[vintage]?.disposition === 'new' ? 'coordinate correction'
      : project.da_revision?.[vintage]?.disposition)
    || project[vintage]?.disposition
    || (project.nep || project.house_m != null ? 'no_da' : null)
  const earlier = project.da_revision?.da5 ?? project.da5
  const later = project.da_revision?.da12 ?? project.da12
  const senate = project.senate
  const insertion = project.restated_by
  const changes = (before, after) => {
    if (!before || !after) return []
    return [
      titlesDiffer(before.title, after.title) && 'Title revised',
      coordsDiffer(before.coords, after.coords) && 'Coordinates differ',
      before.amount != null && after.amount != null && before.amount !== after.amount
        && 'Amount changed',
    ].filter(Boolean)
  }
  const houseNotes = project.house_m == null ? [] : changes(
    project.nep && { title: project.nep.title, coords: project.nep.coords, amount: project.nep.amount_m },
    { title: project.title, coords: project.house_coords, amount: project.house_m }
  )
  const draftNotes = (draft, prior, vintage) => {
    const notes = changes(
      prior ? { title: prior.title, coords: prior.to_coords, amount: prior.proposed_m }
        : draft && { coords: draft.from_coords, amount: draft.from_m },
      draft && { title: draft.title, coords: draft.to_coords, amount: draft.proposed_m }
    )
    const fixes = (reviews[vintage] ?? []).filter((finding) => finding.status.startsWith('FIXED'))
    if (fixes.some((finding) => /title/i.test(finding.status))) notes.push('Title corrected')
    if (fixes.some((finding) => /coordinate/i.test(finding.status))) notes.push('Coordinates corrected')
    return [...new Set(notes)].filter((note) =>
      !(note === 'Title revised' && notes.includes('Title corrected')) &&
      !(note === 'Coordinates differ' && notes.includes('Coordinates corrected')))
  }
  const senateNotes = senate ? changes(
    { title: senate.hb_title, coords: insertion?.from_coords ?? senate.hb_coords, amount: senate.gab_m },
    { title: insertion?.title ?? senate.senate_title, coords: insertion?.to_coords ?? senate.senate_coords,
      amount: insertion?.sv_m ?? senate.sv_m }
  ).filter((note) => !(note === 'Title revised' && actions.house_senate === 'renamed') &&
    !(note === 'Amount changed' && ['cut', 'raised', 'reduced'].includes(actions.house_senate))) : []
  const stages = [
    ['NEP', project.nep ? 'proposed' : null, null, flagged.some((r) => r.document === '2027 NEP')],
    ['HGAB', actions.nep_house === 'reinstated' ? 'dropped' : actions.nep_house,
      null, flagged.some((r) => r.document === '2027 GAB'), houseNotes],
    ['DA Nov 5', daAction('da5'), reviews.nov5, false, draftNotes(earlier, null, 'nov5')],
    ['DA Nov 12', daAction('da12'), reviews.nov12, false, draftNotes(later, earlier, 'nov12')],
    ['Senate', senateOutcome(project), null, false, senateNotes],
  ]

  return <BudgetStageRail stages={stages} ids={['nep', 'house', 'da5', 'da12', 'senate']}
    onSelect={onSelect} selected={selected} />
}

export function BudgetStageRail({ stages, ids, onSelect, selected, agency, onlyStage, labels = actionLabel }) {
  const colors = ['var(--nep)', 'var(--house)', '#b27be2', '#b27be2', 'var(--senate)']
  return (
    <div className={selected ? 'stage-statuses drawer-rail' : onlyStage ? 'stage-statuses title-stage' : 'stage-statuses'}
      aria-label={onlyStage ? undefined : 'Budget stages'}>
      {stages.map(([stage, action, findings, original, notes = []], index) => {
        const id = ids[index]
        if (onlyStage && id !== onlyStage) return null
        const marks = <ReviewMarks reviews={findings ?? undefined} original={original} agency={agency} />
        const content = <>
          {!onlyStage && <span className="stage-status-label">{stage}</span>}
          <span className="st act-pill" style={{ color: actionColor[action] || 'var(--dim)' }}>
            {action ? (id === 'senate' ? senateOutcomeLabels[action === 'Insertion' ? 'inserted' : action] : undefined) || labels[action] || action : 'N/A'}
            {!selected && marks}
          </span>
          {notes.map((note) => <span className="st act-pill stage-note" key={note}>{note}</span>)}
        </>
        return onSelect ? (
          <button type="button" key={id} className="stage-status" aria-pressed={selected ? selected === id : undefined}
                  style={{ '--stop-color': colors[index] }}
                  onClick={(event) => { event.stopPropagation(); onSelect(id) }}>
            {selected && <>
              <span className="rail-stop" aria-hidden="true" />
              <span className="rail-review">{marks}</span>
            </>}
            {content}
          </button>
        ) : <div className="stage-status" key={id}>{content}</div>
      })}
    </div>
  )
}
