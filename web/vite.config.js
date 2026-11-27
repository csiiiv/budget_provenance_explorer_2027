import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import niaCoverageData from './niaCoverageData.mjs'
import { cpSync } from 'node:fs'
import { sanitizePublishedNia } from './niaPublicDocuments.mjs'
import { fileURLToPath } from 'node:url'

// The Python exporter (data_formalization/scripts/export_web.py) writes
// bundles straight into web/data/<program>/ — served as static files by the
// dev server, and copied into dist/ on build so `vite preview` works too.
// Relative base keeps the bundle working under any subpath, including
// GitHub Pages project sites (/<repo>/).
export default defineConfig({
  base: './',
  plugins: [
    react(),
    niaCoverageData(),
    {
      name: 'copy-ledger-data',
      apply: 'build',
      closeBundle() {
        cpSync(
          new URL('./public/data', import.meta.url),
          new URL('./dist/data', import.meta.url),
          { recursive: true },
        )
        sanitizePublishedNia(new URL('./dist/data/', import.meta.url))
      },
    },
  ],
  build: {
    rollupOptions: {
      input: {
        fmr: fileURLToPath(new URL('./index.html', import.meta.url)),
        about: fileURLToPath(new URL('./about.html', import.meta.url)),
        nia: fileURLToPath(new URL('./nia.html', import.meta.url)),
        'nia-provenance': fileURLToPath(new URL('./nia-provenance.html', import.meta.url)),
        'nia-map': fileURLToPath(new URL('./nia_map.html', import.meta.url)),
        'nia-coordinates': fileURLToPath(new URL('./nia-coordinates.html', import.meta.url)),
        'nia-documents': fileURLToPath(new URL('./nia-documents.html', import.meta.url)),
        'nia-titles': fileURLToPath(new URL('./nia-titles.html', import.meta.url)),
        'dpwh-findings': fileURLToPath(new URL('./dpwh-findings.html', import.meta.url)),
        dpwh: fileURLToPath(new URL('./dpwh.html', import.meta.url)),
      },
    },
  },
  // `allowedHosts` permits access through reverse proxies / Cloudflare
  // tunnels that forward an external Host header to the dev server.
  // `true` allows any host (needed for random quick-tunnel hostnames);
  // to lock it down, use an explicit list instead, e.g.
  //   allowedHosts: ['g7-test-2.simple-systems.dev']
  server: {
    port: 5180,
    allowedHosts: true,
  },
  // inotify watches fail under this sandbox (EMFILE); polling keeps HMR alive
  watch: { usePolling: true, interval: 300 },
})
