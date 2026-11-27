import React, {useEffect,useMemo,useRef,useState} from 'react'

const num = new Intl.NumberFormat('en-PH')
const money = new Intl.NumberFormat('en-PH',{style:'currency',currency:'PHP',maximumFractionDigits:0})
const pageSize=50
const documentLabels={has_pow:'POW',has_bp202:'BP 202',has_development_council:'LDC',has_geotagged_photos:'Photos',has_certificate_of_implementability:'Implementability'}
let indexPromise
function loadIndex(){
  if(!indexPromise)indexPromise=fetch(new URL('data/dpwh-finding-records.json',location.href)).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).catch(e=>{indexPromise=null;throw e})
  return indexPromise
}
function matches(r,s){
  if(!s.all&&(s.grouping==='office'?(r.region!==s.program||r.office!==s.pap):(r.program!==s.program||r.pap!==s.pap)))return false
  if(s.stage==='senate'&&r.senate_php<=0)return false
  if(s.key==='total')return true
  if(s.mode==='documents')return r.bucket===s.key
  if(s.mode==='families')return r.families.includes(s.key)
  return s.key==='any'?r.flagged:r.flags.includes(s.key)
}
function safeUrl(value){
  if(!value)return null
  try{const u=new URL(value, 'https://budget.bettergov.ph/');return ['https:','http:'].includes(u.protocol)?u.href:null}catch{return null}
}
function exportCsv(rows,stage){
  const columns=['Chain ID','HGAB ID','House title','Senate title','Program','PAP','Region','Office','House PHP','Senate PHP','Selected stage PHP','Key documents found','Coverage','Senate disposition','House PDF page','Senate PDF page','Flag codes','Project page']
  const body=rows.map(r=>[r.id,r.hgab_id,r.title,r.senate_title,r.program,r.pap,r.region,r.office,r.house_php,r.senate_php,r[stage+'_php'],r.key_documents_found,r.bucket,r.senate_action,r.house_page,r.senate_page,r.flags.join('; '),r.project_page])
  const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"'
  const csv=[columns,...body].map(row=>row.map(quote).join(',')).join('\r\n')
  const url=URL.createObjectURL(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'}))
  const a=document.createElement('a');a.href=url;a.download='dpwh-'+stage+'-cell-records.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
}
export default function DpwhCellRecords({selection:s,onClose}){
  const ref=useRef(null)
  const [index,setIndex]=useState(null)
  const [error,setError]=useState('')
  const [query,setQuery]=useState('')
  const [sort,setSort]=useState('amount-desc')
  const [page,setPage]=useState(0)
  useEffect(()=>{
    const dialog=ref.current
    const previous=document.activeElement
    dialog.showModal()
    let active=true
    loadIndex().then(data=>{if(active)setIndex(data)}).catch(e=>{if(active)setError(e.message)})
    return ()=>{active=false;if(dialog.open)dialog.close();previous?.focus()}
  },[])
  const matched=useMemo(()=>(index?.records??[]).filter(r=>matches(r,s)),[index,s])
  const field=s.stage+'_php'
  const total=matched.reduce((a,r)=>a+r[field],0)
  const snapshotMatches=!index||Object.keys(s.inputs??{}).every(k=>index.inputs?.[k]===s.inputs[k])
  const filtered=useMemo(()=>matched.filter(r=>[r.title,r.senate_title,r.id,r.hgab_id,r.program,r.pap,r.region,r.office].join(' ').toLowerCase().includes(query.trim().toLowerCase())).sort((a,b)=>sort==='title'?(a.title??'').localeCompare(b.title??''):(sort==='amount-asc'?a[field]-b[field]:b[field]-a[field])||a.id.localeCompare(b.id)),[matched,query,sort,field])
  const pageCount=Math.max(1,Math.ceil(filtered.length/pageSize))
  return <dialog ref={ref} className="pap-record-dialog" aria-labelledby="pap-record-heading" onClose={onClose} onClick={e=>{if(e.target===ref.current)ref.current.close()}}>
    <div className="pap-record-inner">
      <div className="pap-record-header"><div><h2 id="pap-record-heading">Explore records — {s.label}</h2><p>{s.program} · {s.pap} · {s.stage==='senate'?'Senate surviving allocation':'House third reading'}</p></div><button autoFocus type="button" onClick={()=>ref.current.close()} aria-label="Close records">Close ×</button></div>
      <div className="pap-record-summary"><strong>{num.format(s.expectedCount)} projects</strong><strong>{money.format(s.expectedAmount)}</strong><span>Selected cell</span></div>
      {error?<p role="alert">Could not load records: {error}. Close and reopen to retry.</p>:!index?<p role="status">Loading project records…</p>:<>
        {(!snapshotMatches||matched.length!==s.expectedCount||total!==s.expectedAmount)&&<p role="alert" className="pap-record-warning">The record index does not reconcile with this cell. Loaded {num.format(matched.length)} projects totaling {money.format(total)}. Refresh the page before relying on these results.</p>}
        <div className="pap-record-tools"><label>Search records<input type="search" value={query} onChange={e=>{setQuery(e.target.value);setPage(0)}} placeholder="Project, office, ID…"/></label><label>Sort records<select value={sort} onChange={e=>{setSort(e.target.value);setPage(0)}}><option value="amount-desc">Allocation: high to low</option><option value="amount-asc">Allocation: low to high</option><option value="title">Project title A–Z</option></select></label><button type="button" onClick={()=>exportCsv(filtered,s.stage)}>Export matching records (CSV)</button></div>
        <p>{num.format(filtered.length)} matching records · {money.format(filtered.reduce((a,r)=>a+r[field],0))}</p>
        <div className="pap-record-scroll" tabIndex={0} role="region" aria-label="Selected project records"><table><thead><tr><th>Project / source ID</th><th>Region / office / PAP</th><th>House</th><th>Senate</th><th>Key documents</th><th>Senate disposition / sources</th></tr></thead><tbody>
        {filtered.slice(page*pageSize,(page+1)*pageSize).map(r=><tr key={r.id}><th scope="row">{r.title}{r.senate_title&&r.senate_title!==r.title&&<small>Senate: {r.senate_title}</small>}<small>{r.hgab_id??r.id}</small></th><td>{r.region}<small>{r.office}</small><small>{r.pap}</small></td><td>{money.format(r.house_php)}</td><td>{money.format(r.senate_php)}</td><td><strong>{r.key_documents_found==null?'Unknown':r.key_documents_found+'/5'}</strong>{Object.entries(documentLabels).map(([k,label])=><small key={k}>{r.documents[k]==null?'?':r.documents[k]?'✓':'✗'} {label}</small>)}</td><td>{r.senate_action}<small>House PDF p. {r.house_page??'—'} · A-4 PDF p. {r.senate_page??'—'}</small>{safeUrl(r.project_page)&&<a href={safeUrl(r.project_page)} target="_blank" rel="noreferrer">Project page ↗</a>}{safeUrl(r.reviewer_page)&&<small><a href={safeUrl(r.reviewer_page)} target="_blank" rel="noreferrer">Review evidence ↗</a></small>}</td></tr>)}
        {!filtered.length&&<tr><td colSpan={6}>No matching records.</td></tr>}</tbody></table></div>
        <div className="pap-record-pagination"><button type="button" disabled={page===0} onClick={()=>setPage(p=>p-1)}>Previous</button><span>Page {page+1} of {pageCount} · {filtered.length?num.format(page*pageSize+1)+'–'+num.format(Math.min((page+1)*pageSize,filtered.length)):'0'} records</span><button type="button" disabled={page+1>=pageCount} onClick={()=>setPage(p=>p+1)}>Next</button></div>
      </>}
    </div>
  </dialog>
}
