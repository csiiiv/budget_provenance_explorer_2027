import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { bucket, buckets, csv, groupName, groupRows, pct, summarize } from './niaCoverageModel.mjs'
import SiteNav from './SiteNav.jsx'
import NiaSectionNav from './NiaSectionNav.jsx'
import './styles.css'
import './niaCoverage.css'

const n = v => (v ?? 0).toLocaleString('en-PH')
const money = v => v == null ? '—' : '₱' + v.toLocaleString('en-PH', { maximumFractionDigits: 2 })
const shortMoney = v => '₱' + (v / 1e9).toLocaleString('en-PH', { maximumFractionDigits: 2 }) + 'B'
const labels = { review: '[POW FOR REVIEW]', initial: 'Ongoing uploading (initial drop)' }
const strengths = ['strong', 'weak', 'review', 'unmatched']
const options = (rows, field) => [...new Set(rows.map(r => groupName(r[field])))].sort((a,b) => a.localeCompare(b, undefined, {numeric:true}))
const explorerUrl = id => './nia-titles.html?q=' + encodeURIComponent(id)
function download(name, text) {
  const url = URL.createObjectURL(new Blob(['\ufeff', text], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url; a.download = name; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
function KPI({ label, value, note }) {
  return <div className="kpi"><div className="lab">{label}</div><div className="val">{value}</div><div className="note">{note}</div></div>
}
function Select({ label, value, set, values }) {
  return <label className="coverage-filter">{label}<select value={value} onChange={e => set(e.target.value)}>
    <option value="">All</option>{values.map(x => <option key={x} value={x}>{x}</option>)}
  </select></label>
}
function SplitBar({ data }) {
  return <div className="coverage-bar" aria-label={Object.entries(buckets).map(([k,l]) => l + ': ' + data.buckets[k]).join(', ')}>
    {Object.keys(buckets).map(k => <span key={k} className={'coverage-' + k} style={{width: pct(data.buckets[k], data.total) === '—' ? 0 : pct(data.buckets[k], data.total)}} title={buckets[k] + ': ' + n(data.buckets[k])}/>)}
  </div>
}
function GroupTable({ rows, field, onPick }) {
  return <section className="panel"><h2>{field === 'region' ? 'Regional coverage' : 'Coverage by project category'}</h2>
    <div className="tablewrap"><table className="coverage-summary"><thead><tr><th scope="col">{field}</th><th scope="col">Rows</th><th scope="col">Any docs</th><th scope="col">POW</th><th scope="col">Pictures</th><th scope="col">No package</th><th scope="col">Coverage</th><th scope="col">Amount without package</th></tr></thead>
    <tbody>{groupRows(rows, field).map(g => <tr key={g.name}><td><button className="linkish" onClick={() => onPick(g.name)}>{g.name}</button></td><td>{n(g.total)}</td><td>{n(g.supported)}</td><td>{n(g.pow)}</td><td>{n(g.photos)}</td><td>{n(g.buckets.none)}</td><td><SplitBar data={g}/>{pct(g.supported,g.total)}</td><td>{money(g.amount-g.supportedAmount)}</td></tr>)}</tbody></table></div></section>
}
function Dashboard({ data }) {
  const [drop, setDrop] = useState('review')
  const [region, setRegion] = useState('')
  const [category, setCategory] = useState('')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState('gap')
  const [view, setView] = useState('projects')
  const [strength, setStrength] = useState('')
  const [folder, setFolder] = useState('')
  const [pkgQuery, setPkgQuery] = useState('')
  const [page, setPage] = useState(1)
  const active = data[drop]
  const rows = active.coverage
  const scope = useMemo(() => rows.filter(r => (!region || groupName(r.region)===region) && (!category || groupName(r.category)===category)), [rows,region,category])
  const summary = summarize(scope)
  const projects = useMemo(() => scope.filter(r => (!status || bucket(r) === status) &&
    [r.senate_id,r.title,r.region,r.category,...r.packages.map(p=>p.package_name)].join(' ').toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a,b) => sort==='gap' ? Number(a.supported)-Number(b.supported) || (b.amount??-1)-(a.amount??-1)
      : sort==='amount' ? (b.amount??-1)-(a.amount??-1) : sort==='files' ? b.doc_count-a.doc_count : (a.title||'').localeCompare(b.title||'')), [scope,status,query,sort])
  const packages = useMemo(() => active.packages.filter(p => (!strength || p.match_strength===strength) &&
    (!folder || groupName(p.region_folder)===folder) && [p.name,p.path,p.best_match?.title,p.best_match?.senate_id].join(' ').toLowerCase().includes(pkgQuery.trim().toLowerCase()))
    .sort((a,b)=>a.match_strength.localeCompare(b.match_strength) || (a.name||'').localeCompare(b.name||'')), [active,strength,folder,pkgQuery])
  const items = view==='projects' ? projects : packages
  const maxPage = Math.max(1,Math.ceil(items.length/50))
  const current = Math.min(page,maxPage)
  const visible = items.slice((current-1)*50,current*50)
  const change = setter => value => {setter(value); setPage(1)}
  const resetDrop = value => {setDrop(value);setRegion('');setCategory('');setFolder('');setStatus('');setStrength('');setPage(1)}
  const projectCsv = [['workbook_id',r=>r.senate_id],['title',r=>r.title],['region',r=>r.region],['category',r=>r.category],['workbook_amount_php',r=>r.amount],['coverage',r=>buckets[bucket(r)]],['pdf_confirmed',r=>r.pdf_confirmed],['files',r=>r.doc_count],['pow_pdfs',r=>r.pow_pdf_count],['picture_files_or_sheets',r=>r.photo_count],['packages',r=>r.packages.map(p=>p.package_path).join(' | ')]]
  const packageCsv = [['package_id',p=>p.id],['name',p=>p.name],['relative_path',p=>p.path],['region_folder',p=>p.region_folder],['filename_amount_php',p=>p.amount_php],['match_strength',p=>p.match_strength],['candidate_workbook_id',p=>p.best_match?.senate_id],['candidate_title',p=>p.best_match?.title],['score',p=>p.best_match?.score],['files',p=>p.doc_count],['pow_pdfs',p=>p.pow_pdf_count],['picture_files_or_sheets',p=>p.photo_count]]
  return <main className="coverage-main">
    <section className="panel"><h2>Document source and scope</h2><div className="filters">
      <label className="coverage-filter">Document drop<select value={drop} onChange={e=>resetDrop(e.target.value)}>{Object.entries(labels).map(([k,l])=><option key={k} value={k}>{l}</option>)}</select></label>
      <Select label="Workbook region" value={region} set={change(setRegion)} values={options(rows,'region')}/>
      <Select label="Project category" value={category} set={change(setCategory)} values={options(rows,'category')}/>
      <button className="chip" onClick={()=>{setRegion('');setCategory('');setPage(1)}}>Clear scope</button>
      <a href={active.drive_url} target="_blank" rel="noopener noreferrer">Open PBC source folder ↗</a>
    </div><p className="coverage-note">Selected source: {active.label}. Coverage is based on original Senate hearing workbook rows, not the number of provenance chains. Missing attribution means no qualifying package was mapped in this inventory, not proof that a document does not exist. Strong/PDF-confirmed matches are not certified identity or document completeness. Pictures include image files and picture PDFs; geotags are not independently verified.</p></section>
    <div className="kpirow">
      <KPI label="Workbook rows" value={n(summary.total)} note="Current region/category scope"/>
      <KPI label="Any attributed package" value={pct(summary.supported,summary.total)} note={n(summary.supported)+' of '+n(summary.total)+' rows'}/>
      <KPI label="With POW" value={n(summary.pow)} note={pct(summary.pow,summary.total)+' of rows'}/>
      <KPI label="With pictures" value={n(summary.photos)} note={pct(summary.photos,summary.total)+' of rows'}/>
      <KPI label="No attributed package" value={n(summary.buckets.none)} note={pct(summary.buckets.none,summary.total)+' of rows'}/>
      <KPI label="Known amount without package" value={shortMoney(summary.amount-summary.supportedAmount)} note={pct(summary.amount-summary.supportedAmount,summary.amount)+' of known workbook amount'}/>
    </div>
    <section className="panel"><h2>Coverage composition · current scope</h2><SplitBar data={summary}/><div className="coverage-legend">{Object.entries(buckets).map(([k,l])=><button key={k} className="chip" aria-pressed={status===k} onClick={()=>{setStatus(status===k?'':k);setView('projects');setPage(1)}}><i className={'coverage-'+k}/>{l}: {n(summary.buckets[k])} ({pct(summary.buckets[k],summary.total)})</button>)}</div>
      <p className="coverage-note">Workbook amount uses the extractor's House amount when nonzero, otherwise NEP amount; it is not the Senate-approved total. {n(summary.unknownAmount)} rows have an unknown amount. {n(summary.pdfConfirmed)} rows have a PDF-confirmed match signal.</p></section>
    <div className="coverage-groups"><GroupTable rows={scope} field="region" onPick={change(setRegion)}/><GroupTable rows={scope} field="category" onPick={change(setCategory)}/></div>
    <section className="panel"><h2>Compare the two document inventories · all workbook rows</h2><div className="tablewrap"><table><thead><tr><th scope="col">Drop</th><th scope="col">Rows</th><th scope="col">Any docs</th><th scope="col">POW</th><th scope="col">Pictures</th><th scope="col">No package</th><th scope="col">Packages</th><th scope="col">Strong</th><th scope="col">Other match status</th></tr></thead><tbody>{Object.entries(data).map(([k,d])=>{const s=summarize(d.coverage);const strong=d.packages.filter(p=>p.match_strength==='strong').length;return <tr key={k}><td>{labels[k]}</td><td>{n(s.total)}</td><td>{n(s.supported)} ({pct(s.supported,s.total)})</td><td>{n(s.pow)}</td><td>{n(s.photos)}</td><td>{n(s.buckets.none)}</td><td>{n(d.packages.length)}</td><td>{n(strong)}</td><td>{n(d.packages.length-strong)}</td></tr>})}</tbody></table></div><p className="coverage-note">Inventories may overlap; figures are not added or treated as a deduplicated combined collection.</p></section>
    <section className="panel" id="coverage-records"><h2>Coverage records</h2><div className="chips" role="group" aria-label="Analysis view">
      <button className="chip" aria-pressed={view==='projects'} onClick={()=>{setView('projects');setPage(1)}}>Workbook projects</button><button className="chip" aria-pressed={view==='packages'} onClick={()=>{setView('packages');setPage(1)}}>Document packages</button></div>
      {view==='projects' ? <div className="filters coverage-controls"><input type="search" aria-label="Search workbook projects" placeholder="Title, workbook ID, package…" value={query} onChange={e=>change(setQuery)(e.target.value)}/><label className="coverage-filter">Coverage<select value={status} onChange={e=>change(setStatus)(e.target.value)}><option value="">All</option>{Object.entries(buckets).map(([k,l])=><option key={k} value={k}>{l}</option>)}</select></label><label className="coverage-filter">Sort<select value={sort} onChange={e=>change(setSort)(e.target.value)}><option value="gap">No package first, amount descending</option><option value="amount">Amount descending</option><option value="files">Files descending</option><option value="title">Title A–Z</option></select></label></div>
      : <><p className="coverage-note">Package filters are independent of workbook region/category scope. Weak, review and unmatched packages remain visible; candidates are not attributed coverage.</p><div className="chips">{strengths.map(s=><button key={s} className="chip" aria-pressed={strength===s} onClick={()=>change(setStrength)(strength===s?'':s)}>{s}: {n(active.packages.filter(p=>p.match_strength===s).length)}</button>)}</div><div className="filters coverage-controls"><input type="search" aria-label="Search document packages" placeholder="Package, path, candidate…" value={pkgQuery} onChange={e=>change(setPkgQuery)(e.target.value)}/><Select label="Region folder" value={folder} set={change(setFolder)} values={options(active.packages,'region_folder')}/></div></>}
      <div className="coverage-toolbar"><span role="status">{n(items.length)} {view==='projects'?'workbook rows':'packages'} · page {current} of {maxPage}</span><button className="chip" onClick={()=>download('nia-'+drop+'-'+view+'.csv',csv(items,view==='projects'?projectCsv:packageCsv))}>Export filtered CSV</button></div>
      <div className="tablewrap coverage-record-table">{view==='projects'?<table><thead><tr><th scope="col">Workbook project</th><th scope="col">Region / category</th><th scope="col">Workbook amount</th><th scope="col">Coverage</th><th scope="col">Files / POW / pictures</th><th scope="col">Attributed packages</th></tr></thead><tbody>{visible.map(r=><tr key={r.senate_id}><td><strong>{r.title}</strong><div><a href={explorerUrl(r.senate_id)}>{r.senate_id} · View provenance ↗</a></div></td><td>{groupName(r.region)}<br/>{groupName(r.category)}</td><td>{money(r.amount)}</td><td><span className={'coverage-dot coverage-'+bucket(r)}/>{buckets[bucket(r)]}{r.pdf_confirmed&&<div className="coverage-note">PDF match signal</div>}</td><td>{n(r.doc_count)} / {n(r.pow_pdf_count)} / {n(r.photo_count)}</td><td>{r.packages.length?<details><summary>{r.packages.length} package(s)</summary>{r.packages.map(p=><p key={p.package_id}><strong>{p.package_name}</strong><br/><small>{p.package_path}</small><br/>{n(p.doc_count)} files · {p.pdf_confirmed?'PDF-confirmed match signal':'filename match'}</p>)}</details>:'—'}</td></tr>)}</tbody></table>
      :<table><thead><tr><th scope="col">Package / inventory reference</th><th scope="col">Region folder</th><th scope="col">Filename amount</th><th scope="col">Match strength</th><th scope="col">Candidate workbook row</th><th scope="col">Files / POW / pictures</th></tr></thead><tbody>{visible.map(p=><tr key={p.id}><td><strong>{p.name}</strong><div className="coverage-note">{p.path}</div></td><td>{groupName(p.region_folder)}<br/>{p.province_folder}</td><td>{money(p.amount_php)}</td><td>{p.match_strength}{p.best_match?.pdf_confirmed&&<div className="coverage-note">PDF match signal</div>}</td><td>{p.best_match?<><a href={explorerUrl(p.best_match.senate_id)}>{p.best_match.senate_id}</a><div>{p.best_match.title}</div><small>Score: {p.best_match.score ?? '—'} · workbook amount {money(p.best_match.amount)}</small></>:'—'}</td><td>{n(p.doc_count)} / {n(p.pow_pdf_count)} / {n(p.photo_count)}</td></tr>)}</tbody></table>}</div>
      {!items.length&&<p>No records match the selected filters.</p>}<div className="coverage-toolbar"><button className="chip" disabled={current===1} onClick={()=>setPage(current-1)}>Previous</button><button className="chip" disabled={current===maxPage} onClick={()=>setPage(current+1)}>Next</button></div>
    </section>
    <section className="panel"><h2>Methodology and limits</h2><p>Coverage is an inventory and attribution measure only. It does not verify document sufficiency, signatures, authenticity, technical validity, RDC endorsement, or compliance with procurement requirements. Package references identify folders within the selected PBC drop, not local filesystem locations or direct public file URLs. Use the source folder to request or locate evidence.</p><a href="https://github.com/csiiiv/budget_provenance_explorer_2027/blob/main/analysis-nia/POW_REVIEW_FINDINGS.md" target="_blank" rel="noopener noreferrer">Review-drop matching methodology ↗</a>{' · '}<a href="https://github.com/csiiiv/budget_provenance_explorer_2027/blob/main/analysis-nia/POW_AVAILABILITY_FINDINGS.md" target="_blank" rel="noopener noreferrer">Initial-drop methodology ↗</a></section>
  </main>
}
function App() {
  const [data,setData]=useState(null)
  const [error,setError]=useState('')
  useEffect(()=>{fetch(new URL('data/nia-document-coverage.json',window.location.href)).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(setData).catch(e=>setError(e.message))},[])
  return <><SiteNav current="nia"/><header><h1>NIA Document Coverage Analysis — FY2027</h1><NiaSectionNav current="documents"/></header>{error?<main><p role="alert">Unable to load document inventory: {error}</p></main>:data?<Dashboard data={data}/>:<main role="status">Loading document inventories…</main>}</>
}
createRoot(document.getElementById('app')).render(<App/>)
