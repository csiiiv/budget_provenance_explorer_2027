// Same point eligibility as the NIA title comparison and map.
export function workbookMapPoints(workbook = []) {
  return workbook.flatMap(({ coordinate_workbook: evidence }) =>
    (evidence?.coordinates?.points ?? [])
      .filter(p => Number.isFinite(p.latitude) && Number.isFinite(p.longitude)
        && !p.issues?.includes('outside_philippines_screening_bounds'))
      .map(p => ({ ...p, row: evidence.row })))
}

// Chains without workbook rows can still carry coordinate evidence on their
// NIA submission-only entries (e.g. reallocation recipients). Both vintage
// entries may reference the same coordinate workbook row — dedupe on it.
export function submissionEvidence(submissions = {}) {
  const byRow = new Map()
  for (const sub of Object.values(submissions ?? {})) {
    const evidence = sub?.coordinate_workbook
    if (evidence?.row != null && !byRow.has(evidence.row)) byRow.set(evidence.row, evidence)
  }
  return [...byRow.values()]
}

export function submissionMapPoints(submissions = {}) {
  return submissionEvidence(submissions).flatMap((evidence) =>
    (evidence?.coordinates?.points ?? [])
      .filter(p => Number.isFinite(p.latitude) && Number.isFinite(p.longitude)
        && !p.issues?.includes('outside_philippines_screening_bounds'))
      .map(p => ({ ...p, row: evidence.row })))
}

export function submissionCoordinateText(submissions = {}) {
  return submissionEvidence(submissions)
    .filter(evidence => evidence?.coordinate_text?.trim())
    .map(evidence => ({ id: 'NIA submission · row ' + evidence.row, text: String(evidence.coordinate_text) }))
}

export const classes = {
  usable: 'Usable workbook coordinates',
  unparsed: 'Workbook text, no usable point',
  title: 'Coordinates in descriptions only',
  none: 'No coordinate evidence detected',
}
export const funding = { positive: 'Positive Senate allocation', zero: 'Zero Senate allocation', absent: 'No Senate record', other: 'Other / unknown Senate amount' }
// Detection only, not geographic validation. Retain raw text even when
// the current point parser cannot interpret it.
const dms = /\d{1,2}\s*[°º˚][\s\S]{0,40}?[Nn][\s\S]{0,20}?(?:[Ee]\s*)?\d{2,3}\s*[°º˚][\s\S]{0,40}?[Ee]/
const decimal = /\b(?:[4-9]|1\d|2[0-2])\.\d{3,}\s*,?\s+1(?:1[6-9]|2[0-7])\.\d{3,}/
export const hasTitleCoordinates = text => typeof text === 'string' && (dms.test(text) || decimal.test(text))
export function classify(chain) {
  const workbook = chain.workbook ?? []
  const submissions = chain.nia_submission_only ?? {}
  const raw = [
    ...workbook.flatMap(w => {
      const value = w.coordinate_workbook?.coordinate_text
      return value != null && String(value).trim() ? [{id:w.id,text:String(value)}] : []
    }),
    ...submissionCoordinateText(submissions),
  ]
  const points = [...workbookMapPoints(workbook), ...submissionMapPoints(submissions)]
  const titles = [
    ['Senate',chain.senate?.senate_title], ['Senate House column',chain.senate?.hb_title],
    ['House',chain.house?.title], ['NEP',chain.nep?.title],
    ...workbook.flatMap(w=>[['October '+w.id,w.label],['October submission '+w.id,w.submission_label]]),
    ...(chain.november_review??[]).flatMap(w=>[['November '+w.nov13_row,w.title_nov13],['November submission '+w.nov13_row,w.submission_title]]),
  ]
  const titleEvidence = titles.filter(([,text])=>hasTitleCoordinates(text)).map(([source,text])=>({source,text}))
  const status = points.length ? 'usable' : raw.length ? 'unparsed' : titleEvidence.length ? 'title' : 'none'
  const amount = chain.senate?.sv_php ?? null
  const fund = !chain.senate ? 'absent' : typeof amount !== 'number' || !Number.isFinite(amount) || amount < 0 ? 'other' : amount > 0 ? 'positive' : 'zero'
  return {
    id:chain.id, senateId:chain.senate?.id, page:chain.senate?.pdf_page,
    title:chain.senate?.senate_title || chain.senate?.hb_title || chain.house?.title || chain.nep?.title || workbook[0]?.submission_label || chain.agency?.oct10?.title || chain.agency?.nov13?.title || chain.id,
    region:chain.senate?.region_key || chain.house?.region || chain.nep?.region || workbook[0]?.region || 'Unspecified / aggregate',
    category:chain.house?.category || chain.nep?.category || workbook[0]?.category || chain.senate?.path?.[3] || 'Unspecified',
    amount, fund, status, raw, points, titleEvidence, workbookIds:workbook.map(w=>w.id),
    aggregate:/watershed management of the 46 river basins across 46 provinces/i.test(chain.senate?.senate_title??''),
  }
}
export function summarize(rows) {
  const matrix=Object.fromEntries(Object.keys(classes).map(k=>[k,Object.fromEntries(Object.keys(funding).map(f=>[f,0]))]))
  const amounts=Object.fromEntries(Object.keys(classes).map(k=>[k,0]))
  let total=0, positive=0, evidence=0, mapped=0, missingAmount=0, pointCount=0
  for(const r of rows) {
    matrix[r.status][r.fund]++
    pointCount+=r.points.length
    if (r.fund==='positive') {
      positive++; total+=r.amount; amounts[r.status]+=r.amount
      if(r.status!=='none') evidence++
      else missingAmount+=r.amount
      if(r.status==='usable') mapped++
    }
  }
  return {matrix,amounts,total,positive,evidence,mapped,missingAmount,pointCount,records:rows.length}
}
