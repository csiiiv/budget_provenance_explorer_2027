// Query-string routing works with a static GitHub Pages entrypoint.
import {useEffect,useState} from 'react'

const defaults={group:'pap',region:'',officeType:'',stage:'senate',mode:'documents',q:'',flag:'any',sort:'total',dir:'desc',metric:'php',scale:'absolute',chart:'12',cell:'',rowGroup:'',rowName:'',all:'',recordQ:'',recordSort:'amount-desc',recordPage:'1'}
const choices={group:['pap','office'],stage:['house','senate'],mode:['documents','families','flags'],dir:['asc','desc'],metric:['php','count'],scale:['absolute','percentage'],chart:['12','all'],all:['','1'],recordSort:['amount-desc','amount-asc','title']}
const modalDefaults={cell:'',rowGroup:'',rowName:'',all:'',recordQ:'',recordSort:'amount-desc',recordPage:'1'}

export function readRoute(search){
  const params=new URLSearchParams(search)
  const out={...defaults}
  for(const key of Object.keys(defaults)){
    const v=params.get(key)
    if(v!==null&&(!choices[key]||choices[key].includes(v)))out[key]=v
  }
  if(!/^[1-9]\d{0,8}$/.test(out.recordPage))out.recordPage='1'
  if(out.group!=='office'){out.region='';out.officeType=''}
  if(!out.cell)Object.assign(out,modalDefaults)
  return out
}
export function routeUrl(current,route){
  const url=new URL(current)
  for(const key of Object.keys(defaults)){
    const value=String(route[key]??defaults[key])
    if(value===defaults[key])url.searchParams.delete(key)
    else url.searchParams.set(key,value)
  }
  return url
}
export function useFindingsRoute(){
  const [route,setRoute]=useState(()=>readRoute(location.search))
  useEffect(()=>{
    const onPop=()=>setRoute(readRoute(location.search))
    window.addEventListener('popstate',onPop)
    return ()=>window.removeEventListener('popstate',onPop)
  },[])
  function update(patch,{replace=false,modalEntry=false}={}){
    const next={...readRoute(location.search),...patch}
    const url=routeUrl(location.href,next)
    if(url.href!==location.href){
      const state=replace?history.state:{dpwhModalEntry:modalEntry}
      history[replace?'replaceState':'pushState'](state,'',url)
    }
    setRoute(readRoute(location.search))
  }
  function openCell(r,key,all){
    update({...modalDefaults,cell:key,rowGroup:all?'':r.program,rowName:all?'':r.pap,all:all?'1':''},{modalEntry:true})
  }
  function closeCell(){
    if(history.state?.dpwhModalEntry)history.back()
    else update(modalDefaults,{replace:true})
  }
  return {route,update,openCell,closeCell}
}
