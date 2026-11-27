import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import SiteNav from './SiteNav.jsx'
import DpwhCellRecords from './DpwhCellRecords.jsx'
import {useFindingsRoute} from './dpwhFindingsRoute.js'
import './styles.css'
import './dpwhFindings.css'

const buckets = [['none','0 of 5'],['partial','1–4 of 5'],['complete','5 of 5'],['unchecked','Unknown']]
const num = new Intl.NumberFormat('en-PH')
const money = new Intl.NumberFormat('en-PH', {style:'currency',currency:'PHP',maximumFractionDigits:0})
const empty = {house_count:0,house_php:0,senate_count:0,senate_php:0}

const coverageLabels = {none:'0 of 5 — No key documents',partial:'1–4 of 5 — Incomplete',complete:'5 of 5 — Complete',unchecked:'Unknown / unchecked'}
const compactMoney = value => value>=1e9?'₱'+(value/1e9).toFixed(2)+'B':value>=1e6?'₱'+(value/1e6).toFixed(2)+'M':money.format(value)
function CoverageBars({rows,stage,metric,groupLabel,display,showAll,setDisplay,setShowAll}){
  const value = m => (m??empty)[stage+'_'+metric]
  const format = v => metric==='php'?compactMoney(v):num.format(v)
  const full = v => metric==='php'?money.format(v):num.format(v)+' projects'
  const plotted = showAll?rows:rows.slice(0,12)
  const max = Math.max(0,...rows.map(r=>value(r.total)))
  const percent = (v,total) => total>0?100*v/total:0
  const ticks = display==='percentage'?[0,25,50,75,100]:[0,.25,.5,.75,1].map(f=>f*max)
  return <section className="pap-coverage-chart" aria-labelledby="pap-coverage-heading">
    <div className="pap-chart-heading"><div><h3 id="pap-coverage-heading">Document coverage by {groupLabel}</h3><p>{stage==='senate'?'Senate committee · surviving House-linked projects':'House third reading'} · {metric==='php'?'Allocation':'Project count'}</p></div>
      <div className="pap-chart-switch" role="group" aria-label="Bar scale">
        <button type="button" aria-pressed={display==='absolute'} onClick={()=>setDisplay('absolute')}>Absolute</button>
        <button type="button" aria-pressed={display==='percentage'} onClick={()=>setDisplay('percentage')}>Percentage</button>
      </div>
    </div>
    <div className="pap-chart-legend">{buckets.map(([key])=><span key={key}><i className={'coverage-swatch coverage-'+key}/>{coverageLabels[key]}</span>)}</div>
    {plotted.length===0?<p>No matching groups.</p>:<>
      <div className="pap-chart-axis" aria-hidden="true">{ticks.map((tick,i)=><span key={i}>{display==='percentage'?tick+'%':format(Math.round(tick))}</span>)}</div>
      <div className="pap-chart-rows">{plotted.map(r=>{
        const total=value(r.total)
        const description=buckets.map(([k])=>coverageLabels[k]+': '+full(value(r.documents[k]))+' ('+percent(value(r.documents[k]),total).toFixed(1)+'%)').join('; ')
        return <div className="pap-chart-row" key={r.program+'|'+r.pap}>
          <div className="pap-chart-label"><span><small>{r.program}</small><strong>{r.pap}</strong></span><strong className="pap-chart-total" title={full(total)}>{format(total)}</strong></div>
          <div className="pap-chart-track" role="img" aria-label={r.pap+'; total '+full(total)+'; '+description}>
            {buckets.map(([key])=>{
              const v=value(r.documents[key]), share=percent(v,total), width=percent(v,display==='percentage'?total:max)
              return v>0?<div key={key} className={'pap-chart-segment coverage-'+key} style={{width:width+'%'}} title={coverageLabels[key]+' · '+full(v)+' · '+share.toFixed(1)+'% of group'}>{width>=12?<span>{display==='percentage'?share.toFixed(1)+'%':format(v)}</span>:null}</div>:null
            })}
          </div>
        </div>
      })}</div>
      <p className="pap-chart-note">Showing {plotted.length} of {rows.length} matching {groupLabel} groups in the table's current sort order. {display==='percentage'?'Shares are relative to each group total.':'All bars use the same scale.'} Hover a segment for its exact value and share. Complete documentation is not technical clearance.</p>
      {rows.length>12&&<button type="button" className="pap-chart-more" aria-expanded={showAll} onClick={()=>setShowAll(!showAll)}>{showAll?'Show first 12 groups':'Show all '+rows.length+' groups'}</button>}
    </>}
  </section>
}

function App(){
  const [report,setReport] = useState(null)
  const [error,setError] = useState('')
  const [scopeOpen,setScopeOpen] = useState(()=>!window.matchMedia('(max-width: 760px)').matches)
  const {route,update,openCell,closeCell}=useFindingsRoute()
  const {group:grouping,region,officeType,stage,mode,q:query,flag:selected,sort:requestedSort,dir:direction,metric}=route
  const isOffice=grouping==='office'
  const groupLabel=isOffice?'implementing office / DEO':'PAP'
  const stem=isOffice?'dpwh-deo-flags':'dpwh-pap-flags'
  const currentReport=report?.grouping===grouping?report:null
  useEffect(()=>{
    const controller = new AbortController()
    setReport(null);setError('')
    fetch(new URL('data/'+stem+'.json',location.href),{signal:controller.signal}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(setReport).catch(e=>{if(e.name!=='AbortError')setError(e.message)})
    return ()=>controller.abort()
  },[stem])
  const regions = [...new Set((currentReport?.groups??[]).map(r=>r.region).filter(Boolean))].sort()
  const officeTypes = [...new Set((currentReport?.groups??[]).map(r=>r.office_type).filter(Boolean))].sort()
  const cols = useMemo(()=>{
    if(mode==='documents')return buckets
    if(mode==='families')return Object.keys(currentReport?.total.families??{}).sort().map(k=>[k,k])
    return [['any','Any automated flag'], ...Object.entries(currentReport?.flag_catalog??{}).sort((a,b)=>a[1].flag.localeCompare(b[1].flag)).map(([k,v])=>[k,v.flag])]
  },[currentReport,mode])
  const amount = m => (m??empty)[stage+'_php']
  const count = m => (m??empty)[stage+'_count']
  const get = (r,k) => mode==='flags'&&k==='any'?r.flagged:r[mode][k]??empty
  const effectiveFlag=cols.some(([k])=>k===selected)?selected:'any'
  const visible=mode==='flags'?cols.filter(([k])=>k===effectiveFlag):cols
  const mobileLabel=(key,label)=>mode==='documents'&&key!=='unchecked'?label+' documents':label
  const sort=['name','total',...visible.map(([k])=>k)].includes(requestedSort)?requestedSort:'total'
  const chooseSort=key=>update({sort:key,dir:key===sort?(direction==='asc'?'desc':'asc'):(key==='name'?'asc':'desc')})
  const modalRow=route.cell&&currentReport?(route.all==='1'?currentReport.total:currentReport.groups.find(r=>r.program===route.rowGroup&&r.pap===route.rowName)):null
  const modalLabel=route.cell==='total'?'Total':cols.find(([k])=>k===route.cell)?.[1]
  const modalMetric=modalRow&&modalLabel?(route.cell==='total'?modalRow.total:get(modalRow,route.cell)):null
  const drill=modalMetric?{grouping,stage,mode,key:route.cell,label:modalLabel,all:route.all==='1',program:modalRow.program,pap:modalRow.pap,expectedCount:count(modalMetric),expectedAmount:amount(modalMetric),inputs:currentReport.inputs}:null
  const nameCompare = (a,b) => (a.program+' '+a.pap).localeCompare(b.program+' '+b.pap)
  const sortValue = r => (sort==='total'?r.total:get(r,sort))[stage+'_'+metric]
  const rows = (currentReport?.groups??[]).filter(r=>(!isOffice||((!region||r.region===region)&&(!officeType||r.office_type===officeType)))&&(r.program+' '+r.pap).toLowerCase().includes(query.toLowerCase())).sort((a,b)=>{
    const delta = sort==='name'?nameCompare(a,b):sortValue(a)-sortValue(b)
    return delta*(direction==='asc'?1:-1)||nameCompare(a,b)
  })
  const sortHeader = (key,label,className) => <th key={key} role="columnheader" scope="col" className={className} aria-sort={sort===key?(direction==='asc'?'ascending':'descending'):'none'}><button type="button" onClick={()=>chooseSort(key)} title={'Sort '+label+(key==='name'?' alphabetically':' by '+(metric==='php'?'allocation':'project count'))} style={{font:'inherit',color:'inherit',background:'transparent',border:0,padding:'4px 0',cursor:'pointer',textAlign:'inherit',whiteSpace:'inherit'}}>{label} <span aria-hidden="true">{sort===key?(direction==='asc'?'↑':'↓'):'↕'}</span></button></th>
  const cell = (m,r,key,label,all=false) => <><strong>{num.format(count(m))}</strong><small>{money.format(amount(m))}</small><button type="button" className="pap-explore-cell" aria-label={'Explore records: '+(all?(isOffice?'All offices':'All PAPs'):r.pap)+' — '+label} onClick={()=>openCell(r,key,all)}>Explore records</button></>
  const download = () => {
    const header=[...(isOffice?['Region','Implementing office','Office type']:['Program','PAP']),'Category','Project count','Allocation PHP','Stage']
    const csv=[header,...rows.flatMap(r=>[['Total',r.total],...visible.map(([k,label])=>[label,get(r,k)])].map(([label,m])=>[r.program,r.pap,...(isOffice?[r.office_type]:[]),label,count(m),amount(m),stage]))].map(r=>r.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\n')
    const u=URL.createObjectURL(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'}))
    const a=document.createElement('a');a.href=u;a.download='dpwh-'+(isOffice?'deo':'pap')+'-'+stage+'-'+mode+'.csv';a.click();URL.revokeObjectURL(u)
  }
  return <><SiteNav current="dpwh"/><header><h1>DPWH — Document coverage and flag breakdown</h1><p>FY2027 House third reading and Senate Committee Report · project-level documentary evidence and automated flags</p><a href="./dpwh.html">← DPWH provenance explorer</a></header><main>
    <section className="panel pap-tools"><label>Group by<select value={grouping} onChange={e=>update({group:e.target.value,region:'',officeType:'',q:'',sort:'total',dir:'desc'})}><option value="pap">Program / PAP</option><option value="office">Implementing office / DEO</option></select></label></section>
    {error?<p role="alert">Unable to load the findings: {error}</p>:!currentReport?<p role="status">Loading summaries…</p>:<>
    <details className="panel pap-methodology" open={scopeOpen} onToggle={e=>setScopeOpen(e.currentTarget.open)}><summary>Scope and methodology</summary><p>House project leaves grouped by official program and PAP or by the printed House region and implementing office, preserving uncategorized rows. Office grouping is not a legislative-district assignment; regional, central and unspecified offices are kept separately. Senate amounts reflect the linked Annex A-4 amendment; an unlisted House project is carried forward. Senate counts include only projects with a positive surviving allocation. This is a House-anchored estimate, not the entire Senate DPWH budget.</p><p>Document categories are based on the five key documents found in the HGAB review snapshot: zero, one to four, five, or unknown. Zero key documents does not necessarily mean no other documents exist. Five documents does not establish technical clearance. Automated flags and families overlap; each project is counted once per code or family, so their allocations must not be added.</p><p>Excluded: {num.format(report.excluded.house_controls)} House control chains; {num.format(report.excluded.senate_unlinked_rows)} Senate rows outside the House-leaf population ({money.format(report.excluded.senate_unlinked_php)}). Linked House amount mismatches: {num.format(report.excluded.linked_house_amount_mismatches)}. No risk status is inferred for these exclusions.</p></details>
    <section className="panel pap-findings"><h2>Counts and allocations per {groupLabel}</h2>
    <div className="pap-tools"><label>Budget stage<select value={stage} onChange={e=>update({stage:e.target.value})}><option value="senate">Senate (surviving)</option><option value="house">House</option></select></label>
    <label>Breakdown<select value={mode} onChange={e=>update({mode:e.target.value,flag:'any',sort:'total',dir:'desc'})}><option value="documents">Key document coverage</option><option value="families">Automated flag families</option><option value="flags">Individual automated flags</option></select></label>
    {mode==='flags'&&<label>Flag<select value={effectiveFlag} onChange={e=>update({flag:e.target.value,sort:'total',dir:'desc'})}>{cols.map(([k,label])=><option key={k} value={k}>{label}</option>)}</select></label>}
    {isOffice&&<><label>Region<select value={region} onChange={e=>update({region:e.target.value})}><option value="">All regions</option>{regions.map(r=><option key={r} value={r}>{r}</option>)}</select></label><label>Office type<select value={officeType} onChange={e=>update({officeType:e.target.value})}><option value="">All office types</option>{officeTypes.map(t=><option key={t} value={t}>{t}</option>)}</select></label></>}
    <label>Search {groupLabel}<input type="search" value={query} onChange={e=>update({q:e.target.value},{replace:true})} placeholder={isOffice?'e.g. Quezon City':'e.g. Multi-Purpose'}/></label>
    <label>Chart metric / column sorting<select value={metric} onChange={e=>update({metric:e.target.value})}><option value="php">Allocation (PHP)</option><option value="count">Project count</option></select></label></div>
    <div className="pap-export-tools"><button type="button" onClick={download}>Export displayed rows (CSV)</button><a href={"./data/"+stem+".csv"} download>Full breakdown CSV</a><a href={"./data/"+stem+".json"}>JSON</a>{mode==='documents'&&<a href="#pap-coverage-heading">Jump to chart ↓</a>}</div>
    <div className="pap-mobile-sort"><label>Sort by<select value={sort} onChange={e=>chooseSort(e.target.value)}><option value="name">{isOffice?'Region / office':'Program / PAP'}</option><option value="total">Total</option>{visible.map(([k,label])=><option key={k} value={k}>{mobileLabel(k,label)}</option>)}</select></label><button type="button" onClick={()=>update({dir:direction==='asc'?'desc':'asc'})} aria-label={direction==='asc'?'Sort descending':'Sort ascending'}>{direction==='asc'?'↑ Ascending':'↓ Descending'}</button></div>
    <div className="pap-table" tabIndex={0} role="region" aria-label="Findings summary"><table role="table"><thead role="rowgroup"><tr role="row">{sortHeader('name',isOffice?'Region / Implementing office':'Program / PAP')}{sortHeader('total','Total')}{visible.map(([k,label])=>sortHeader(k,label,'pap-'+k))}</tr></thead><tbody role="rowgroup">
    {!query&&!region&&!officeType&&<tr className="pap-total" role="row"><th role="rowheader" scope="row">{isOffice?"All offices":"All PAPs"}</th><td role="cell" data-label="Total">{cell(report.total.total,report.total,'total','Total',true)}</td>{visible.map(([k,label])=><td key={k} role="cell" data-label={mobileLabel(k,label)} className={'pap-cell-'+k}>{cell(get(report.total,k),report.total,k,label,true)}</td>)}</tr>}
    {rows.map(r=><tr key={r.program+'|'+r.pap} role="row"><th role="rowheader" scope="row"><small>{r.program}{isOffice?' · '+r.office_type:''}</small>{r.pap}</th><td role="cell" data-label="Total">{cell(r.total,r,'total','Total')}</td>{visible.map(([k,label])=><td key={k} role="cell" data-label={mobileLabel(k,label)} className={'pap-cell-'+k}>{cell(get(r,k),r,k,label)}</td>)}</tr>)}
    </tbody></table></div><p>{rows.length} {groupLabel} groups. Each category shows project count and allocation in pesos. Use the sort controls or click a column heading to change the order. The total row stays fixed.</p>
    {mode==='documents'&&<CoverageBars key={grouping} rows={rows} stage={stage} metric={metric} groupLabel={groupLabel} display={route.scale} showAll={route.chart==='all'} setDisplay={scale=>update({scale})} setShowAll={all=>update({chart:all?'all':'12'})}/>}
    </section>
    {route.cell&&!drill&&<p role="alert">The requested record group or category is unavailable in the current dataset. <button type="button" onClick={closeCell}>Clear record selection</button></p>}
    </>}</main>{drill&&<DpwhCellRecords key={JSON.stringify([grouping,stage,mode,route.cell,route.rowGroup,route.rowName,route.all])} selection={drill} onClose={closeCell} route={route} updateRoute={patch=>update(patch,{replace:true})}/>}</>
}
createRoot(document.getElementById('app')).render(<App/>)
