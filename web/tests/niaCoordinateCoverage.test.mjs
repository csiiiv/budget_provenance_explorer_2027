import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {classify,summarize,workbookMapPoints,hasTitleCoordinates} from '../src/niaCoordinateCoverage.mjs'
const bundle=JSON.parse(readFileSync(new URL('../public/data/nia.json',import.meta.url),'utf8'))
test('all chains and Senate records reconcile',()=>{
  const rows=bundle.chains.map(classify),s=summarize(rows)
  assert.equal(new Set(rows.map(r=>r.id)).size,rows.length)
  const senate=rows.filter(r=>r.senateId)
  assert.equal(new Set(senate.map(r=>r.senateId)).size,bundle.totals.senate.rows)
  assert.equal(senate.length,bundle.totals.senate.rows)
  assert.equal(rows.filter(r=>r.fund==='other').length,0)
  assert.equal(s.total,bundle.totals.senate.amount_php)
  assert.equal(Object.values(s.matrix).flatMap(Object.values).reduce((a,b)=>a+b,0),rows.length)
  assert.equal(Object.values(s.amounts).reduce((a,b)=>a+b,0),s.total)
  // Historical FY2027 snapshot baseline, not a generic deployment constraint.
  console.log(JSON.stringify({matrix:s.matrix,amounts:s.amounts,records:s.records,positive:s.positive,evidence:s.evidence,missingAmount:s.missingAmount}))
})
test('class precedence, absent vs zero, map eligibility',()=>{
  const w=coordinate_workbook=>[{id:'test',coordinate_workbook}]
  const c=(workbook,amount,title)=>({id:'x',workbook,senate:amount===null?null:{sv_php:amount,senate_title:title}})
  const point={latitude:15,longitude:121,issues:[]}
  assert.equal(classify(c(w({coordinate_text:'15,121',coordinates:{points:[point]}}),1)).status,'usable')
  assert.equal(classify(c(w({coordinate_text:'raw',coordinates:{points:[{...point,issues:['outside_philippines_screening_bounds']}]}}),0)).status,'unparsed')
  assert.equal(classify(c([],1,'Site 15°28\'24.8"N, 121°2\'20"E')).status,'title')
  assert.equal(classify(c([],0,'Sta. 0+100')).fund,'zero')
  assert.equal(classify(c([],null,'')).fund,'absent')
  assert.equal(classify(c([],1,'Sta. 0+100')).status,'none')
  assert.equal(workbookMapPoints(w({coordinates:{points:[{latitude:null,longitude:121}]}})).length,0)
  assert(hasTitleCoordinates('8˚22\'22.22"N, 126˚19\'26.14"E'))
})
