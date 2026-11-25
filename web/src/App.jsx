import { lazy, Suspense, useEffect, useState } from 'react'
import { useLedger, fmtM } from './lib.jsx'
import { Downloads } from './Detail.jsx'
import Regions from './Regions.jsx'
import Localities from './Localities.jsx'

const Flow = lazy(() => import('./Flow.jsx'))
const Explorer = lazy(() => import('./Explorer.jsx'))

function ExplorerSection({ drillCount, config, ...props }) {
  const [nearViewport, setNearViewport] = useState(false)
  const [anchor, setAnchor] = useState(null)
  const shouldLoad = nearViewport || drillCount > 0
  const heading = config?.explorerHeading ?? 'Project explorer'
  const loadLabel = config?.explorerLoadLabel ?? 'Load project explorer'
  useEffect(() => {
    if (!anchor || shouldLoad) return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) setNearViewport(true)
    }, { rootMargin: '240px' })
    observer.observe(anchor)
    return () => observer.disconnect()
  }, [anchor, shouldLoad])

  return (
    <section id="explorer" ref={setAnchor} aria-label={heading}>
      {shouldLoad ? (
        <Suspense fallback={<div className="panel" role="status">Loading {heading.toLowerCase()}…</div>}>
          <Explorer key={drillCount} config={config} {...props} />
        </Suspense>
      ) : (
        <div className="panel">
          <h2>{heading}</h2>
          <button type="button" onClick={() => setNearViewport(true)}>{loadLabel}</button>
        </div>
      )}
    </section>
  )
}

export function Kpi({ lab, val, note }) {
  return (
    <div className="kpi">
      <div className="lab">{lab}</div>
      <div className="val" style={{ color: val?.color || 'var(--text)' }}>{val?.v ?? val}</div>
      {note && <div className="note">{note}</div>}
    </div>
  )
}

export default function App() {
  const data = useLedger()
  if (!data) return <div className="loading">loading ledger bundles…</div>
  const { manifest, projects } = data
  const t = manifest.totals, c = t.counts
  const senate = t.actions?.house_senate ?? {
    cut: t.true_cuts, realigned: t.realigned_house, inserted: c.senate_insertion,
  }
  const latestCheck = (check) => manifest.validation_runs?.findLast((run) => run.check === check)?.result
  const integrity = latestCheck('integrity-fmr')
  const crossCheck = latestCheck('senate_a1_vs_bettergov_2027')
  const senateDelta = Math.round((t.senate_m - t.house_m) * 10) / 10
  const deltaLabel = (senateDelta < 0 ? '−' : senateDelta > 0 ? '+' : '') + fmtM(Math.abs(senateDelta))
  const houseNote = t.house_insertion_m == null ? `${c.house} roads`
    : `${c.house} roads · ${fmtM(t.house_insertion_m)} in insertions`
  const houseMatches = t.house_annex_matches ?? projects.filter(
    (project) => project.type === 'house' && project.senate
  ).length
  return <ProvenancePage data={data}
    header={<>
        <h1>DA Farm-to-Market Roads — FY2027 budget chain</h1>
        <span className="sub">NEP → House HB 10858 → DA drafts → Senate CR · own-extraction ledgers</span>
        <div className="badges">
          <span className={`badge${integrity === 'pass' ? ' ok' : ''}`}>Integrity {integrity ?? 'pending'}</span>
          <span className={`badge${crossCheck === 'clean' ? ' ok' : ''}`}>Senate cross-check {crossCheck ?? 'pending'}</span>
          <span className="badge">{c.nep} NEP · {c.house} house · {c.senate_rows} senate rows</span>
        </div>
        <a href="./nia.html">NIA Budget Explorer</a>
        {' · '}
        <a href="./dpwh.html">DPWH Provenance Explorer</a>
        <Downloads program="fmr" />
    </>}
    footer={<>FMR ledger {manifest.ledger_sha256?.slice(0, 8)} · validation {manifest.generated_at ?? 'pending'}
      {' · '}{manifest.records.toLocaleString()} chain records</>}>
        <div className="kpirow">
          <Kpi lab="NEP proposal" val={{ v: fmtM(t.nep_m), color: 'var(--nep)' }} note={`${c.nep} roads`} />
          <Kpi lab="House bill" val={{ v: fmtM(t.house_m), color: 'var(--house)' }} note={houseNote} />
          <Kpi lab="Senate committee" val={{ v: fmtM(t.senate_m), color: 'var(--senate)' }}
               note={`${senate.cut ?? 0} true cuts · ${senate.realigned ?? 0} realigned · ${senate.inserted ?? 0} insertions`} />
          <Kpi lab="Senate vs House"
               val={{ v: deltaLabel, color: senateDelta < 0 ? 'var(--cut)' : senateDelta > 0 ? 'var(--raised)' : 'var(--text)' }}
               note={t.senate_m === t.nep_m ? 'back to the NEP level' : undefined} />
          <Kpi lab="Realigned projects" val={String(senate.realigned ?? 0)} note="paired House and Senate rows" />
          <Kpi lab="Match audit" val={`${houseMatches}/${c.house}`} note="House roads linked to Annex A-1" />
        </div>
  </ProvenancePage>
}

export function ProvenancePage({ data, header, footer, config, children }) {
  const { manifest, regions, projects, localities } = data
  const [localityKey, setLocalityKey] = useState('')
  const [drillCount, setDrillCount] = useState(0)
  const locality = localities.find((entry) => entry.key === localityKey)
  const explorerOnly = !!config?.explorerOnly
  const onDrill = (key) => {
    setLocalityKey(key)
    setDrillCount((count) => count + 1)
    document.getElementById('explorer')?.scrollIntoView({ behavior: 'smooth' })
  }
  return (
    <div>
      <header>{header}</header>
      <main>
        {children}
        <ExplorerSection drillCount={config?.explorerEager ? Math.max(drillCount, 1) : drillCount}
                         projects={projects} regions={regions}
                         localities={localities} locality={locality} setLocalityKey={setLocalityKey}
                         config={config} />
        {!explorerOnly && <>
          <Suspense fallback={<div className="panel">Loading stage flow…</div>}>
            <Flow projects={projects} totals={manifest.totals} nia={!!config} />
          </Suspense>
          <Regions regions={regions} />
          <Localities localities={localities} onDrill={onDrill}
                      stages={config?.stages} grouping={config?.grouping} />
        </>}
      </main>
      <footer>{footer}</footer>
    </div>
  )
}
