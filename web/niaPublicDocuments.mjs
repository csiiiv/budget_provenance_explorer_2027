import { readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'

export function withoutLocalDocumentRoots(bundle) {
  for (const chain of bundle.chains) {
    if (chain.supporting_docs) delete chain.supporting_docs.source_path
  }
  return bundle
}
const hash = bytes => createHash('sha256').update(bytes).digest('hex')

// Old retained exports contain the analyst's absolute mirror root. Remove
// it only from public build output, preserving the raw snapshots and hashes.
export function sanitizePublishedNia(dataDir) {
  const publicBundle = new URL('nia.json', dataDir)
  const full = new URL('export/nia/full.json', dataDir)
  const checksums = new URL('export/nia/SHA256SUMS.txt', dataDir)
  const original = readFileSync(full)
  const sums = readFileSync(checksums, 'utf8')
  const entry = /^[a-f0-9]{64}  full\.json$/m
  if (!entry.test(sums) || sums.match(entry)[0] !== hash(original) + '  full.json')
    throw new Error('Original NIA full.json checksum does not match; refusing to replace it')
  const bundle = withoutLocalDocumentRoots(JSON.parse(readFileSync(publicBundle, 'utf8')))
  const fullBundle = withoutLocalDocumentRoots(JSON.parse(original.toString('utf8')))
  const output = JSON.stringify(fullBundle) + '\n'
  writeFileSync(publicBundle, JSON.stringify(bundle) + '\n')
  writeFileSync(full, output)
  writeFileSync(checksums, sums.replace(entry, hash(output) + '  full.json'))
}
