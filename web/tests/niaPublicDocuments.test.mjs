import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { withoutLocalDocumentRoots } from '../niaPublicDocuments.mjs'

test('remove local roots without altering evidence', () => {
  const bundle = {chains:[{id:'a',supporting_docs:{source_path:'/local/mirror',drive_url:'https://drive.google.com/folder',packages:[{name:'A',path:'REGION 1/A'}],doc_count:1}}]}
  assert.deepEqual(withoutLocalDocumentRoots(bundle),{chains:[{id:'a',supporting_docs:{drive_url:'https://drive.google.com/folder',packages:[{name:'A',path:'REGION 1/A'}],doc_count:1}}]})
})
test('published NIA bundles do not contain supporting document roots and download checksum is valid', () => {
  const base = new URL('../dist/data/', import.meta.url)
  for(const file of ['nia.json','export/nia/full.json']) {
    const raw = JSON.parse(readFileSync(new URL(file,base),'utf8'))
    const docs = raw.chains.filter(c=>c.supporting_docs).map(c=>c.supporting_docs)
    assert(docs.length > 0)
    for (const d of docs) {
      assert(!Object.hasOwn(d,'source_path'))
      assert(d.drive_url.startsWith('https://drive.google.com/'))
      assert(d.packages.every(p=>p.name && p.path && !/^(?:\/|[a-z]:|file:)/i.test(p.path)))
    }
  }
  const full = readFileSync(new URL('export/nia/full.json',base))
  const sums = readFileSync(new URL('export/nia/SHA256SUMS.txt',base),'utf8')
  assert(sums.includes(createHash('sha256').update(full).digest('hex')+'  full.json'))
})
