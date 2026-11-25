import React from 'react'
import { createRoot } from 'react-dom/client'
import NiaSectionNav, { niaPages } from './NiaSectionNav.jsx'
import './styles.css'
import './niaSection.css'

const icons = {
  provenance: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><path d="M10 6.5h4a3 3 0 0 1 3 3V14M6.5 10v7a1 1 0 0 0 1 1H14"/></>,
  titles: <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16M6 8h3m-3 4h3m-3 4h3m6-8h3m-3 4h3m-3 4h3"/></>,
  documents: <><path d="M13 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10zM13 3v7h7M8 14h8m-8 3h5"/><path d="m8 10 1 1 2-2"/></>,
  coordinates: <><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 1v5m0 12v5M1 12h5m12 0h5"/></>,
  map: <><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0z"/><circle cx="12" cy="10" r="2.5"/></>,
}
function Landing() {
  return <>
    <header className="nia-hub-top"><span className="sub">FY2027 Budget Provenance Explorers</span><nav aria-label="Other explorers"><a href="./index.html">FMR</a><a href="./dpwh.html">DPWH</a><a href="./about.html">About & methodology</a></nav></header>
    <main className="nia-hub">
      <section className="nia-hub-intro">
        <p className="nia-hub-eyebrow">National Irrigation Administration · FY2027</p>
        <h1>NIA Budget Explorer</h1>
        <p>Explore how irrigation project proposals, allocations and supporting evidence change across the budget process. Choose a tool to investigate the data from a different perspective.</p>
        <div className="nia-hub-stages" aria-label="Budget sources"><span>NEP</span><span aria-hidden="true">→</span><span>House bill</span><span aria-hidden="true">→</span><span>NIA workbooks</span><span aria-hidden="true">→</span><span>Senate committee</span></div>
      </section>
      <section aria-labelledby="tools-heading">
        <h2 id="tools-heading" className="nia-hub-section-title">Analysis tools</h2>
        <div className="nia-hub-grid">{niaPages.filter(p => p.key !== 'home').map(p => <a className="nia-hub-card" key={p.key} href={p.href} style={{'--tool-accent':p.accent}}>
          <div className="nia-hub-card-top"><span className="nia-hub-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{icons[p.key]}</svg></span><span className="nia-hub-index">{p.index}</span></div>
          <h3>{p.label}</h3><p>{p.description}</p>
          <ul>{p.features.map(f => <li key={f}>{f}</li>)}</ul>
          <span className="nia-hub-open">Open {p.label.toLowerCase()} <span aria-hidden="true">↗</span></span>
        </a>)}</div>
      </section>
      <section className="panel nia-hub-note"><h2>Sources and methodology</h2><p>These views use retained budget and agency records. Document attribution, project matching and coordinate evidence have limitations; a missing match is not proof of a missing project or document.</p><a href="./about.html">Read the methodology and source guides ↗</a></section>
    </main>
  </>
}
// Preserve old project-search bookmarks while making the plain URL the hub.
const url = new URL(window.location.href)
if (url.searchParams.get('q')) {
  window.location.replace('./nia-provenance.html' + url.search + url.hash)
} else {
  createRoot(document.getElementById('app')).render(<Landing/>)
}
