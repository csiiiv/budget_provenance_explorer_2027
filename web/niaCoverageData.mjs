import { readFileSync } from 'node:fs'
import { selectDrop } from './src/niaCoverageModel.mjs'

const files = {
  review: 'pow_review_availability.json',
  initial: 'pow_availability.json',
}
const output = 'data/nia-document-coverage.json'

export default function niaCoverageData() {
  const payload = () => JSON.stringify(Object.fromEntries(Object.entries(files).map(([id, file]) => [
    id, selectDrop(JSON.parse(readFileSync(new URL('../analysis-nia/data/program_of_works/' + file, import.meta.url), 'utf8'))),
  ])))
  return {
    name: 'nia-document-coverage-data',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url?.split('?')[0] !== '/' + output) return next()
        try {
          res.setHeader('Content-Type', 'application/json; charset=utf-8')
          res.end(payload())
        } catch (err) {
          res.statusCode = 500
          res.end('Unable to load coverage inventory: ' + err.message)
        }
      })
    },
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: output, source: payload() })
    },
  }
}
