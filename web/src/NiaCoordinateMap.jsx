import React, { useEffect, useRef, useState } from 'react'
import './NiaCoordinateMap.css'

const DEFAULT_BASEMAP = 'satellite'

const BASEMAPS = {
  street: {
    label: 'Street',
    style: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
  },
  satellite: {
    label: 'Satellite',
    style: {
      version: 8,
      sources: {
        imagery: {
          type: 'raster',
          tiles: ['https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
          tileSize: 256,
          maxzoom: 23,
          attribution: 'Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community',
        },
      },
      layers: [{ id: 'imagery', type: 'raster', source: 'imagery' }],
    },
  },
}

import { workbookMapPoints } from './niaCoordinateCoverage.mjs'
export { workbookMapPoints }

export function formatMapPoint({ latitude, longitude }) {
  return `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`
}

export function NiaMapCanvas({ points, onSelectProject }) {
  const container = useRef(null)
  const mapRef = useRef(null)
  const basemapRef = useRef(DEFAULT_BASEMAP)
  const [basemap, setBasemap] = useState(DEFAULT_BASEMAP)
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    let active = true
    let map
    let observer
    async function renderMap() {
      try {
        const [lib, { default: workerUrl }] = await Promise.all([
          import('maplibre-gl'),
          import('maplibre-gl/dist/maplibre-gl-worker.mjs?url'),
          import('maplibre-gl/dist/maplibre-gl.css'),
        ])
        if (!active) return
        lib.setWorkerUrl(workerUrl)
        const bounds = new lib.LngLatBounds()
        for (const point of points) bounds.extend([point.longitude, point.latitude])
        map = new lib.Map({
          container: container.current,
          style: BASEMAPS[basemapRef.current].style,
          bounds,
          fitBoundsOptions: { padding: 44, maxZoom: 15 },
          renderWorldCopies: false,
        })
        mapRef.current = map
        map.addControl(new lib.NavigationControl({ showCompass: false }))
        map.addControl(new lib.ScaleControl())
        map.on('idle', () => setStatus((current) => current === 'loading' ? 'ready' : current))
        map.on('error', () => setStatus('error'))

        if (onSelectProject) addProjectDots(map, points, onSelectProject)
        for (const [index, point] of (onSelectProject ? [] : points).entries()) {
          const marker = document.createElement('button')
          marker.type = 'button'
          marker.className = 'nia-map-marker'
          marker.textContent = index + 1
          marker.setAttribute('aria-label', `Point ${index + 1}, ${formatMapPoint(point)}`)
          new lib.Marker({ element: marker })
            .setLngLat([point.longitude, point.latitude])
            .setPopup(new lib.Popup({ offset: 14 }).setText(formatMapPoint(point)))
            .addTo(map)
        }
        observer = new ResizeObserver(() => map.resize())
        observer.observe(container.current)
      } catch {
        if (active) setStatus('error')
      }
    }
    renderMap()
    return () => {
      active = false
      observer?.disconnect()
      mapRef.current = null
      map?.remove()
    }
  }, [points, onSelectProject])

  function switchBasemap(next) {
    if (next === basemapRef.current) return
    basemapRef.current = next
    setBasemap(next)
    if (mapRef.current) {
      setStatus('loading')
      mapRef.current.setStyle(BASEMAPS[next].style, { diff: false })
    }
  }

  return <>
    <div className="nia-map-basemaps" role="group" aria-label="Basemap">
      {Object.entries(BASEMAPS).map(([key, { label }]) =>
        <button key={key} className="chip" type="button" aria-pressed={basemap === key}
          onClick={() => switchBasemap(key)}>{label}</button>)}
    </div>
    <div className="nia-map-canvas" ref={container} aria-label="Map of project coordinates" />
    {status === 'loading' && <p className="nia-map-status" role="status">Loading map…</p>}
    {status === 'error' && <p className="nia-map-status" role="status">The basemap could not load.</p>}
  </>
}

function addProjectDots(map, points, onSelectProject) {
  const layer = 'nia-project-dots'
  const data = {
    type: 'FeatureCollection',
    features: points.map((point, index) => ({
      type: 'Feature',
      id: index,
      geometry: { type: 'Point', coordinates: [point.longitude, point.latitude] },
      properties: {},
    })),
  }

  map.on('style.load', () => {
    map.addSource(layer, { type: 'geojson', data })
    map.addLayer({
      id: layer, type: 'circle', source: layer,
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 5, 3, 14, 6],
        'circle-color': '#35a5ff',
        'circle-stroke-color': '#fff',
        'circle-stroke-width': 1,
      },
    })
  })
  map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer' })
  map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = '' })
  map.on('click', layer, ({ features: [feature] }) => {
    onSelectProject(points[feature.id])
  })
}

export default function NiaCoordinateMap({ project, onClose }) {
  const dialog = useRef(null)
  const points = project.coordinatePoints

  useEffect(() => {
    const element = dialog.current
    element.showModal()
    return () => element.close()
  }, [])

  return <dialog ref={dialog} className="nia-coordinate-dialog" aria-labelledby="nia-map-title" onClose={onClose}>
    <div className="nia-map-heading">
      <div>
        <h2 id="nia-map-title">Project coordinates</h2>
        <p>{project.title}</p>
      </div>
      <form method="dialog"><button type="submit" autoFocus>Close</button></form>
    </div>
    <NiaMapCanvas points={points} />
    <ol className="nia-map-points" aria-label="Workbook coordinates in latitude, longitude order">
      {points.map((point, index) => <li key={index}>
        <strong>{[point.section_label, point.role !== 'unspecified' && point.role].filter(Boolean).join(' · ') || 'Site'}</strong>
        <span>{formatMapPoint(point)}</span>
        <small>NIA coordinate workbook · Y{point.row}</small>
      </li>)}
    </ol>
  </dialog>
}
