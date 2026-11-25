// Coverage is measured in original workbook rows, not provenance chains.
// The two inventory drops are independent; never sum them as distinct files.
export const number = n => Number(n || 0)
export const ratio = (n, d) => d ? n / d : null
export const pct = (n, d) => d ? (100 * n / d).toFixed(1) + '%' : '—'
export const groupName = x => x || 'Unspecified'
export const bucket = r => !r.supported ? 'none' : r.has_pow && r.has_photos ? 'both'
  : r.has_pow ? 'pow' : r.has_photos ? 'photos' : 'other'
export const buckets = {
  both: 'POW + pictures', pow: 'POW only', photos: 'Pictures only',
  other: 'Other attributed files', none: 'No attributed package',
}
export function summarize(rows) {
  const s = { total: rows.length, supported: 0, pow: 0, photos: 0, pdfConfirmed: 0,
    amount: 0, supportedAmount: 0, unknownAmount: 0, files: 0, buckets: Object.fromEntries(Object.keys(buckets).map(k => [k, 0])) }
  for (const r of rows) {
    s.buckets[bucket(r)]++
    if (r.supported) { s.supported++; s.files += number(r.doc_count) }
    if (r.has_pow) s.pow++
    if (r.has_photos) s.photos++
    if (r.pdf_confirmed) s.pdfConfirmed++
    if (typeof r.amount === 'number' && Number.isFinite(r.amount)) {
      s.amount += r.amount
      if (r.supported) s.supportedAmount += r.amount
    } else s.unknownAmount++
  }
  return s
}
export function groupRows(rows, field) {
  const groups = new Map()
  for (const r of rows) {
    const name = groupName(r[field])
    if (!groups.has(name)) groups.set(name, [])
    groups.get(name).push(r)
  }
  return [...groups].map(([name, values]) => ({ name, ...summarize(values) }))
    .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name))
}
export function selectDrop(raw) {
  if (raw.schema_version !== 1 || !Array.isArray(raw.coverage) || !Array.isArray(raw.packages))
    throw new Error('Unrecognized document inventory schema')
  const coverage = raw.coverage.map(r => ({
    senate_id: r.senate_id, title: r.title, region: r.region, category: r.category, status: r.status,
    amount: r.amount, supported: r.supported, has_pow: r.has_pow, has_photos: r.has_photos,
    pdf_confirmed: !!r.pdf_confirmed, match_strength: r.match_strength, doc_count: r.doc_count,
    pdf_count: r.pdf_count, image_count: r.image_count, pow_pdf_count: r.pow_pdf_count, photo_count: r.photo_count,
    packages: (r.packages || []).map(p => ({
      package_id: p.package_id, package_name: p.package_name, package_path: p.package_path,
      score: p.score, pdf_confirmed: !!p.pdf_confirmed, doc_count: p.doc_count,
      pow_pdf_count: p.pow_pdf_count, photo_count: p.photo_count,
    })),
  }))
  const packages = raw.packages.map(p => ({
    id: p.id, name: p.name, path: p.path, region_folder: p.region_folder, province_folder: p.province_folder,
    amount_php: p.amount_php, doc_count: p.doc_count, pdf_count: p.pdf_count, image_count: p.image_count,
    pow_pdf_count: p.pow_pdf_count, photo_count: p.photo_count, other_count: p.other_count,
    match_strength: p.match_strength, best_match: p.best_match && {
      senate_id: p.best_match.senate_id, title: p.best_match.title, score: p.best_match.score,
      amount: p.best_match.amount, pdf_confirmed: !!p.best_match.pdf_confirmed,
    },
  }))
  return { label: raw.source_subfolder, drive_url: raw.source_drive_url, coverage, packages }
}
export function csv(rows, fields) {
  // Prevent spreadsheet formula interpretation of user/source-derived text.
  const cell = v => {
    let s = v == null ? '' : String(v)
    if (typeof v === 'string' && /^[\s]*[=+\-@]/.test(s)) s = "'" + s
    return '"' + s.replaceAll('"', '""') + '"'
  }
  return [fields.map(([name]) => cell(name)).join(','), ...rows.map(r =>
    fields.map(([, get]) => cell(get(r))).join(','))].join('\r\n') + '\r\n'
}
