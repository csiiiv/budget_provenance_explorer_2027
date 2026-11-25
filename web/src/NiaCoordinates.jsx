import React,{useEffect,useMemo,useState} from 'react'
import {createRoot} from 'react-dom/client'
import NiaSectionNav from './NiaSectionNav.jsx'
import {classes,funding,classify,summarize} from './niaCoordinateCoverage.mjs'
import {csv} from './niaCoverageModel.mjs'
import './styles.css'
import './niaCoverage.css'
import './niaCoordinateCoverage.css'

const count=n=>n.toLocaleString('en-PH')
const peso=n=>n==null?'—':'₱'+n.toLocaleString('en-PH')
const pct=(n,d)=>d?(100*n/d).toFixed(2)+'%':'—'
const keys=Object.keys(classes)
const fundKeys=Object.keys(funding)
const rowTotal=r=>Object.values(r).reduce((a,b)=>a+b,0)
const colors={usable:'var(--senate)',unparsed:'var(--house)',title:'var(--nep)',none:'var(--cut)'}
const url=r=>'./nia-titles.html?q='+encodeURIComponent(r.senateId||r.workbookIds[0]||r.id)
function KPI({label,value,note}){return <div className="kpi"><div className="lab">{label}</div><div className="val">{value}</div><div className="note">{note}</div></div>}
function Filter({label,value,onChange,options}){return <label className="coverage-filter">{label}<select value={value} onChange={e=>onChange(e.target.value)}><option value="">All</option>{options.map(([k,l])=><option key={k} value={k}>{l}</option>)}</select></label>}
function Bar({summary,amount=false}){
  const denominator=amount?summary.total:summary.positive
  return <div className="coverage-bar coordinate-bar" aria-label={keys.map(k=>classes[k]+': '+pct(amount?summary.amounts[k]:summary.matrix[k].positive,denominator)).join(', ')}>{keys.map(k=><span key={k} style={{background:colors[k],width:denominator?(100*(amount?summary.amounts[k]:summary.matrix[k].positive)/denominator)+'%':'0%'}} title={classes[k]}/>)}</div>
}
function Dashboard({bundle}){
  const all=useMemo(()=>bundle.chains.map(classify),[bundle])
  const [region,setRegion]=useState('')
  const [category,setCategory]=useState('')
  const [fund,setFund]=useState('')
  const [status,setStatus]=useState('')
  const [q,setQ]=useState('')
  const [page,setPage]=useState(1)
  const change=setter=>v=>{setter(v);setPage(1)}
  const scope=all.filter(r=>(!region||r.region===region)&&(!category||r.category===category))
  const s=summarize(scope)
  const overall=summarize(all)
  const gaps=scope.filter(r=>r.fund==='positive'&&r.status==='none').sort((a,b)=>b.amount-a.amount)
  const siteGaps=gaps.filter(r=>!r.aggregate)
  const filtered=scope.filter(r=>(!fund||r.fund===fund)&&(!status||r.status===status)&&[r.title,r.id,r.senateId,r.region,r.category,...r.workbookIds].join(' ').toLowerCase().includes(q.trim().toLowerCase())).sort((a,b)=>(b.amount??-1)-(a.amount??-1)||a.id.localeCompare(b.id))
  const maxPage=Math.max(1,Math.ceil(filtered.length/50)), current=Math.min(page,maxPage)
  const pick=(f,k)=>{setFund(f);setStatus(k);setPage(1);document.getElementById('coordinate-records')?.scrollIntoView({behavior:'smooth'})}
  const options=field=>[...new Set(all.map(r=>r[field]))].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true})).map(v=>[v,v])
  const regions=[...new Set(scope.map(r=>r.region))].map(name=>({name,s:summarize(scope.filter(r=>r.region===name))})).sort((a,b)=>b.s.missingAmount-a.s.missingAmount||b.s.positive-a.s.positive)
  const exportRows=()=>{const fields=[['chain_id',r=>r.id],['senate_id',r=>r.senateId],['annex_page',r=>r.page],['title',r=>r.title],['region',r=>r.region],['category',r=>r.category],['senate_amount_php',r=>r.amount],['funding_status',r=>funding[r.fund]],['coordinate_evidence',r=>classes[r.status]],['usable_point_count',r=>r.points.length],['workbook_ids',r=>r.workbookIds.join(' | ')],['raw_coordinate_text',r=>r.raw.map(x=>x.text).join(' | ')],['description_evidence',r=>r.titleEvidence.map(x=>x.source+': '+x.text).join(' | ')],['aggregate_allocation',r=>r.aggregate]]
    const blob=new Blob(['\ufeff',csv(filtered,fields)],{type:'text/csv;charset=utf-8'}), href=URL.createObjectURL(blob), a=document.createElement('a');a.href=href;a.download='nia-coordinate-coverage.csv';a.click();setTimeout(()=>URL.revokeObjectURL(href),1000)}
  return <main className="coverage-main">
    <section className="panel"><h2>Analysis scope</h2><p className="coverage-note">Same retained data/nia.json used by Title Comparison. Counts are project chains; Senate amounts are Annex A-3 committee-report allocations, not final enacted GAA amounts. Usable means the existing map accepts at least one workbook point, not that the location is verified. Coordinate text in a description is a detection signal only.</p><div className="filters"><Filter label="Region" value={region} onChange={change(setRegion)} options={options('region')}/><Filter label="Category" value={category} onChange={change(setCategory)} options={options('category')}/><button className="chip" onClick={()=>{setRegion('');setCategory('');setPage(1)}}>Clear scope</button><a href="./data/nia.json" target="_blank" rel="noopener noreferrer">View source data ↗</a></div></section>
    <div className="kpirow">
      <KPI label="Project chains" value={count(s.records)} note={count(overall.records)+' total in the dataset'}/>
      <KPI label="Positive Senate allocation" value={count(s.positive)} note={peso(s.total)}/>
      <KPI label="Funded with coordinate evidence" value={pct(s.evidence,s.positive)} note={count(s.evidence)+' of '+count(s.positive)+' funded records'}/>
      <KPI label="Funded with usable points" value={pct(s.mapped,s.positive)} note={count(s.mapped)+' map-ready records'}/>
      <KPI label="Funded with no evidence detected" value={count(gaps.length)} note={peso(s.missingAmount)}/>
      <KPI label="Site-specific gaps" value={count(siteGaps.length)} note={peso(siteGaps.reduce((a,r)=>a+r.amount,0))+' · excludes identified aggregate'}/>
    </div>
    <section className="panel"><h2>Coordinate evidence vs. Senate funding</h2><div className="tablewrap"><table className="coordinate-matrix"><thead><tr><th scope="col">Coordinate evidence</th>{fundKeys.map(f=><th key={f} scope="col">{funding[f]}</th>)}<th scope="col">Total</th></tr></thead><tbody>{keys.map(k=><tr key={k}><th scope="row"><span className="coverage-dot" style={{background:colors[k]}}/>{classes[k]}</th>{fundKeys.map(f=><td key={f}><button className="linkish" onClick={()=>pick(f,k)}>{count(s.matrix[k][f])}</button></td>)}<td>{count(rowTotal(s.matrix[k]))}</td></tr>)}<tr className="coordinate-total"><th scope="row">Total</th>{fundKeys.map(f=><td key={f}>{count(keys.reduce((a,k)=>a+s.matrix[k][f],0))}</td>)}<td>{count(s.records)}</td></tr></tbody></table></div><p className="coverage-note">Click any count to inspect those records. The 4 evidence categories are mutually exclusive. Zero and missing Senate records are distinct.</p><h3>Funded records by evidence type</h3><Bar summary={s}/><div className="coverage-legend">{keys.map(k=><span key={k}><i style={{background:colors[k]}}/>{classes[k]}: {count(s.matrix[k].positive)} ({pct(s.matrix[k].positive,s.positive)})</span>)}</div></section>
    <section className="panel"><h2>Senate budget by coordinate evidence</h2><Bar summary={s} amount/><div className="tablewrap coordinate-amount"><table><thead><tr><th scope="col">Evidence</th><th scope="col">Funded records</th><th scope="col">Senate amount</th><th scope="col">Share of funded amount</th></tr></thead><tbody>{keys.map(k=><tr key={k}><td>{classes[k]}</td><td>{count(s.matrix[k].positive)}</td><td>{peso(s.amounts[k])}</td><td>{pct(s.amounts[k],s.total)}</td></tr>)}<tr className="coordinate-total"><th scope="row">Total</th><td>{count(s.positive)}</td><td>{peso(s.total)}</td><td>{pct(s.total,s.total)}</td></tr></tbody></table></div></section>
    <section className="panel"><h2>Funded records with no coordinate evidence detected</h2><p className="coverage-note">These are exceptions in the current table, not proof that coordinates do not exist elsewhere. The identified multi-province watershed allocation is listed separately as an aggregate reference to Annex A-3B.</p><div className="tablewrap"><table><thead><tr><th scope="col">Project</th><th scope="col">Senate allocation</th><th scope="col">Annex A-3 page</th><th scope="col">Note</th></tr></thead><tbody>{gaps.map(r=><tr key={r.id}><td><a href={url(r)}>{r.title}</a></td><td>{peso(r.amount)}</td><td>{r.page??'—'}</td><td>{r.aggregate?'Aggregate · Annex A-3B':'Site-specific record'}</td></tr>)}</tbody></table></div>{!gaps.length&&<p>No exceptions in this scope.</p>}</section>
    <section className="panel"><h2>Regional breakdown</h2><div className="tablewrap"><table><thead><tr><th scope="col">Region</th><th scope="col">Funded</th><th scope="col">Usable</th><th scope="col">Workbook text only</th><th scope="col">Description only</th><th scope="col">No evidence</th><th scope="col">Evidence coverage</th><th scope="col">Amount without evidence</th></tr></thead><tbody>{regions.map(({name,s})=><tr key={name}><td><button className="linkish" onClick={()=>change(setRegion)(name)}>{name}</button></td><td>{count(s.positive)}</td>{keys.map(k=><td key={k}>{count(s.matrix[k].positive)}</td>)}<td>{pct(s.evidence,s.positive)}</td><td>{peso(s.missingAmount)}</td></tr>)}</tbody></table></div></section>
    <section className="panel" id="coordinate-records"><h2>Project records</h2><div className="filters"><input type="search" aria-label="Search projects" placeholder="Title or record ID…" value={q} onChange={e=>change(setQ)(e.target.value)}/><Filter label="Senate funding" value={fund} onChange={change(setFund)} options={Object.entries(funding)}/><Filter label="Coordinate evidence" value={status} onChange={change(setStatus)} options={Object.entries(classes)}/><button className="chip" onClick={()=>{setFund('');setStatus('');setQ('');setPage(1)}}>Reset record filters</button></div><div className="coverage-toolbar"><span role="status">{count(filtered.length)} records · page {current} of {maxPage}</span><button className="chip" onClick={exportRows}>Export filtered CSV</button></div>
    <div className="tablewrap coverage-record-table"><table><thead><tr><th scope="col">Project / source</th><th scope="col">Region</th><th scope="col">Senate amount</th><th scope="col">Coordinate evidence</th><th scope="col">Raw evidence</th></tr></thead><tbody>{filtered.slice((current-1)*50,current*50).map(r=><tr key={r.id}><td><strong>{r.title}</strong><div><a href={url(r)}>{r.senateId||r.id} · View provenance ↗</a></div><small>Annex page {r.page??'—'} · {r.workbookIds.join(', ')}</small></td><td>{r.region}</td><td>{peso(r.amount)}<div className="coverage-note">{funding[r.fund]}</div></td><td><span className="coverage-dot" style={{background:colors[r.status]}}/>{classes[r.status]}<div className="coverage-note">{count(r.points.length)} usable point(s)</div></td><td>{r.raw.length||r.titleEvidence.length?<details><summary>Inspect evidence</summary>{r.raw.map((x,i)=><p key={i}><strong>{x.id}</strong><br/><span className="coordinate-raw">{x.text}</span></p>)}{r.titleEvidence.map((x,i)=><p key={'t'+i}><strong>{x.source}</strong><br/>{x.text}</p>)}{r.points.length>0&&<p>{r.points.map(p=>p.latitude.toFixed(6)+', '+p.longitude.toFixed(6)).join(' · ')}</p>}</details>:'—'}</td></tr>)}</tbody></table></div>{!filtered.length&&<p>No matching records.</p>}<div className="coverage-toolbar"><button className="chip" disabled={current===1} onClick={()=>setPage(current-1)}>Previous</button><button className="chip" disabled={current===maxPage} onClick={()=>setPage(current+1)}>Next</button></div></section>
    <section className="panel"><h2>Interpretation and limitations</h2><p>Evidence is classified in this order: at least one eligible linked workbook point; nonempty raw linked workbook coordinate cell; coordinate-pattern detection in NEP, House, Senate or linked workbook descriptions; otherwise no detected evidence. Held workbook matches are not automatically attributed. The text-pattern test is not a complete coordinate parser and may miss unusual formats. Chainage alone is not geographic coordinates.</p><p>Coverage does not establish accuracy, completeness, formal funding criteria or causation. The relationship between coordinate evidence and funding is descriptive. The map uses only eligible workbook points; other evidence remains available for review.</p></section>
  </main>
}
function App(){const [bundle,setBundle]=useState(null),[error,setError]=useState('');useEffect(()=>{fetch(new URL('data/nia.json',window.location.href)).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(setBundle).catch(e=>setError(e.message))},[]);return <><header><h1>NIA Coordinate Coverage Analysis — FY2027</h1><NiaSectionNav current="coordinates"/></header>{error?<main role="alert">Unable to load NIA data: {error}</main>:bundle?<Dashboard bundle={bundle}/>:<main role="status">Loading NIA records…</main>}</>}
createRoot(document.getElementById('app')).render(<App/>)
