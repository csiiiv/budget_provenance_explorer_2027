import { lazy, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const NiaExplorerApp = lazy(() =>
  import('./Nia.jsx').then((module) => ({ default: module.NiaExplorerApp })))

createRoot(document.getElementById('app')).render(
  <Suspense fallback={<div className="loading" role="status">Loading title comparison…</div>}>
    <NiaExplorerApp mode="titles" />
  </Suspense>)
