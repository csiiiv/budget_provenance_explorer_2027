import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { bucket, buckets, groupRows, selectDrop, summarize, csv } from '../src/niaCoverageModel.mjs'

for (const name of ['pow_review_availability.json','pow_availability.json']) {
  test(name + ' reconciles with original inventory', () => {
    const raw = JSON.parse(readFileSync(new URL('../../analysis-nia/data/program_of_works/'+name, import.meta.url), 'utf8'))
    const drop = selectDrop(raw)
    const s = summarize(drop.coverage)
    assert.equal(new Set(drop.coverage.map(r=>r.senate_id)).size, s.total)
    assert.equal(s.total, raw.summary.senate_projects)
    assert.equal(s.supported, raw.summary.senate_projects_with_docs)
    assert.equal(s.pow, raw.summary.senate_projects_with_pow)
    assert.equal(s.photos, raw.summary.senate_projects_with_photos)
    assert.equal(s.buckets.none, raw.summary.senate_projects_unsupported)
    assert.equal(s.files,raw.summary.senate_docs_attributed)
    assert.equal(Object.values(s.buckets).reduce((a,b)=>a+b,0),s.total)
    assert.equal(drop.packages.length,raw.summary.packages)
    assert.equal(groupRows(drop.coverage,'region').reduce((a,b)=>a+b.total,0),s.total)
    assert.equal(groupRows(drop.coverage,'category').reduce((a,b)=>a+b.supported,0),s.supported)
    assert(!Object.hasOwn(drop,'source'))
    const byId = new Map(drop.packages.map(p=>[p.id,p]))
    assert.equal(byId.size,drop.packages.length)
    for(const r of drop.coverage) {
      assert.equal(r.supported,r.packages.length>0)
      if (name.includes('review')) for(const p of r.packages) assert.equal(byId.get(p.package_id).match_strength,'strong')
    }
  })
}
test('buckets mutually exclusive and unknown amounts not silently converted to zero',()=>{
  const rows=[{supported:true,has_pow:true,has_photos:true,amount:10},{supported:false,amount:null}]
  assert.equal(bucket(rows[0]),'both')
  assert.equal(bucket(rows[1]),'none')
  assert.equal(summarize(rows).unknownAmount,1)
  assert.equal(summarize(rows).supportedAmount,10)
})
test('CSV escaping',()=>assert.equal(csv([{x:'=1+1'},{x:'a"b'}],[['x',r=>r.x]]),'"x"\r\n"\'=1+1"\r\n"a""b"\r\n'))
