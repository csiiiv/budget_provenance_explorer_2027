import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import SiteNav from './SiteNav.jsx'
import './styles.css'
import './dpwhFindings.css'

const buckets = [['none','0 of 5'],['partial','1–4 of 5'],['complete','5 of 5'],['unchecked','Unknown']]
const num = new Intl.NumberFormat('en-PH')
const money = new Intl.NumberFormat('en-PH', {style:'currency',currency:'PHP',maximumFractionDigits:0})
const empty = {house_count:0,house_php:0,senate_count:0,senate_php:0}
function App(){
  const [report,setReport] = useState(null)
  const [error,setError] = useState('')
  const [stage,setStage] = useState('senate')
  const [mode,setMode] = useState('documents')
  const [query,setQuery] = useState('')
  const [selected,setSelected] = useState('any')
  const [sort,setSort] = useState('total')
  useEffect(()=>{fetch(new URL('data/dpwh-pap-flags.json',location.href)).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(setReport).catch(e=>setError(e.message))},[])
  const cols = useMemo(()=>{
    if(mode==='documents')return buckets
    if(mode==='families')return Object.keys(report?.total.families??{}).sort().map(k=>[k,k])
    return [['any','Any automated flag'], ...Object.entries(report?.flag_catalog??{}).sort((a,b)=>a[1].flag.localeCompare(b[1].flag)).map(([k,v])=>[k,v.flag])]
  },[report,mode])
  const amount = m => (m??empty)[stage+'_php']
  const count = m => (m??empty)[stage+'_count']
  const get = (r,k) => mode==='flags'&&k==='any'?r.flagged:r[mode][k]??empty
  const visible = mode==='flags'?cols.filter(([k])=>k===selected):cols
  const rows = (report?.groups??[]).filter(r=>(r.program+' '+r.pap).toLowerCase().includes(query.toLowerCase())).sort((a,b)=>sort==='name'?(a.program+' '+a.pap).localeCompare(b.program+' '+b.pap):amount(sort==='total'?b.total:get(b,sort))-amount(sort==='total'?a.total:get(a,sort)))
  const cell = m => <><strong>{num.format(count(m))}</strong><small>{money.format(amount(m))}</small></>
  const download = () => {
    const header=['Program','PAP','Category','Project count','Allocation PHP','Stage']
    const csv=[header,...rows.flatMap(r=>[['Total',r.total],...visible.map(([k,label])=>[label,get(r,k)])].map(([label,m])=>[r.program,r.pap,label,count(m),amount(m),stage]))].map(r=>r.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\n')
    const u=URL.createObjectURL(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'}))
    const a=document.createElement('a');a.href=u;a.download='dpwh-pap-'+stage+'-'+mode+'.csv';a.click();URL.revokeObjectURL(u)
  }
  return <><SiteNav current="dpwh"/><header><h1>DPWH — PAP risk breakdown</h1><p>FY2027 House third reading and Senate Committee Report · project-level documentary evidence and automated flags</p><a href="./dpwh.html">← DPWH provenance explorer</a></header><main>
    {error?<p role="alert">Unable to load the findings: {error}</p>:!report?<p role="status">Loading PAP summaries…</p>:<>
    <section className="panel"><h2>Scope and methodology</h2><p>House project leaves grouped by their official program and PAP, preserving uncategorized rows. Senate amounts reflect the linked Annex A-4 amendment; an unlisted House project is carried forward. Senate counts include only projects with a positive surviving allocation. This is a House-anchored estimate, not the entire Senate DPWH budget.</p><p>Document categories are based on the five key documents found in the HGAB review snapshot: zero, one to four, five, or unknown. Zero key documents does not necessarily mean no other documents exist. Five documents does not establish technical clearance. Automated flags and families overlap; each project is counted once per code or family, so their allocations must not be added.</p><p>Excluded: {num.format(report.excluded.house_controls)} House control chains; {num.format(report.excluded.senate_unlinked_rows)} Senate rows outside the House-leaf population ({money.format(report.excluded.senate_unlinked_php)}). Linked House amount mismatches: {num.format(report.excluded.linked_house_amount_mismatches)}. No risk status is inferred for these exclusions.</p></section>
    <section className="panel pap-findings"><h2>Counts and allocations per PAP</h2>
    <div className="pap-tools"><label>Budget stage<select value={stage} onChange={e=>setStage(e.target.value)}><option value="senate">Senate (surviving)</option><option value="house">House</option></select></label>
    <label>Breakdown<select value={mode} onChange={e=>{setMode(e.target.value);setSort('total');setSelected('any')}}><option value="documents">Key document coverage</option><option value="families">Automated flag families</option><option value="flags">Individual automated flags</option></select></label>
    {mode==='flags'&&<label>Flag<select value={selected} onChange={e=>{setSelected(e.target.value);setSort('total')}}>{cols.map(([k,label])=><option key={k} value={k}>{label}</option>)}</select></label>}
    <label>Search PAP<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="e.g. Multi-Purpose"/></label>
    <label>Sort<select value={sort} onChange={e=>setSort(e.target.value)}><option value="total">Total allocation</option><option value="name">Program / PAP</option>{visible.map(([k,label])=><option key={k} value={k}>{label} allocation</option>)}</select></label></div>
    <p><button onClick={download}>Export displayed rows (CSV)</button> · <a href="./data/dpwh-pap-flags.csv" download>Full breakdown CSV</a> · <a href="./data/dpwh-pap-flags.json">JSON</a></p>
    <div className="pap-table" tabIndex={0}><table><thead><tr><th>Program / PAP</th><th>Total</th>{visible.map(([k,label])=><th key={k} className={'pap-'+k}>{label}</th>)}</tr></thead><tbody>
    {!query&&<tr className="pap-total"><th>All PAPs</th><td>{cell(report.total.total)}</td>{visible.map(([k])=><td key={k}>{cell(get(report.total,k))}</td>)}</tr>}
    {rows.map(r=><tr key={r.program+'|'+r.pap}><th><small>{r.program}</small>{r.pap}</th><td>{cell(r.total)}</td>{visible.map(([k])=><td key={k}>{cell(get(r,k))}</td>)}</tr>)}
    </tbody></table></div><p>{rows.length} PAP groups. Each cell shows project count and allocation in pesos.</p></section>
    </>}</main></>
}
createRoot(document.getElementById('app')).render(<App/>)
