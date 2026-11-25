import React, { useCallback, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { formatMapPoint, NiaMapCanvas, workbookMapPoints } from './NiaCoordinateMap.jsx'
import { adapt, Evidence } from './Nia.jsx'
import './styles.css'

function NiaMapPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [selection, setSelection] = useState(null)
  const onSelectProject = useCallback((point) => {
    setSelection((current) => ({
      id: point.projectId,
      stage: current?.id === point.projectId ? current.stage : 'oct10',
      point,
    }))
  }, [])
  const selectedProject = selection && data?.byId.get(selection.id)
  const point = selection?.point

  useEffect(() => {
    const request = new AbortController()
    fetch(new URL('data/nia.json', window.location.href), { signal: request.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
      })
      .then(({ chains, agency_sources: sources }) => {
        const workbook = new Map(chains.flatMap((chain) =>
          (chain.workbook ?? []).map((entry) => [entry.id, { entry, projectId: chain.id }])))
        const points = []
        let projectCount = 0
        for (const { entry, projectId } of workbook.values()) {
          const sites = workbookMapPoints([entry])
          if (!sites.length) continue
          projectCount++
          points.push(...sites.map((point) => ({ ...point, projectId })))
        }
        const projects = chains.map(adapt)
        const byId = new Map(projects.map((project) => [project.id, project]))
        setData({ projects, projectCount, points, sources, byId })
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setError(err.message)
      })
    return () => request.abort()
  }, [])

  return <>
    <header>
      <h1>NIA Project Map — FY 2027</h1>
      <a href="./nia.html">Provenance Explorer</a>
      <a href="./nia-titles.html">Title Comparison</a>
      {data?.points.length > 0 && <span className="sub">
        {data.projectCount.toLocaleString()} projects · {data.points.length.toLocaleString()} workbook points
      </span>}
    </header>
    <main className="nia-map-page">
      {error ? <p role="alert">Unable to load NIA projects ({error}).</p>
        : !data ? <p role="status">Loading NIA projects…</p>
        : data.points.length ? <NiaMapCanvas points={data.points} onSelectProject={onSelectProject} />
        : <p>No linked workbook coordinates are available.</p>}
    </main>
    {selectedProject && <Evidence key={`${selection.id}:${selection.stage}`}
      rec={selectedProject} initialStage={selection.stage} sources={data.sources} projects={data.projects}
      titleDetails={point && <div className="drawer-current-point" role="status">
        <span>Current point:</span>{' '}
        {point.coordinate_pair_text && <><mark>{point.coordinate_pair_text}</mark>{' | '}</>}
        <span>{formatMapPoint(point)}</span>
      </div>}
      onClose={() => setSelection(null)} onJump={(id, stage) => setSelection({ id, stage })} />}
  </>
}

createRoot(document.getElementById('app')).render(<NiaMapPage />)
