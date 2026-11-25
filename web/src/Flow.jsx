import { useEffect, useRef, useState } from 'react'
import { init, use } from 'echarts/core'
import { SankeyChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { billions, controlLabels } from './DpwhBudgetControls.jsx'
import { fmtM, stageColor, statusColor } from './lib.jsx'

use([SankeyChart, TooltipComponent, CanvasRenderer])

function flowAmounts(ps, annexCoverage) {
  const f = { nepHouse: 0, nepDrop: 0, houseInsert: 0, cut: 0, renamed: 0, raised: 0, reduced: 0,
              renamedSv: 0, raisedSv: 0, reducedSv: 0, inserted: 0, restated: 0, restatedSv: 0, outsideAnnex: 0 }
  for (const r of ps) {
    const nep = r.nep?.amount_m || 0, house = r.house_m || 0
    const st = r.senate?.status, sv = r.senate?.sv_m || 0
    if (r.type === 'house') {
      if (nep) f.nepHouse += nep; else f.houseInsert += house
      if (annexCoverage && !r.senate) f.outsideAnnex += house
      if (st === 'cut') f.cut += house
      else if (st === 'renamed') { f.renamed += house; f.renamedSv += sv }
      else if (st === 'raised') { f.raised += house; f.raisedSv += sv }
      else if (st === 'restated') { f.restated += house; f.restatedSv += sv }
      else if (st === 'reduced') { f.reduced += house; f.reducedSv += sv }
    } else if (r.type === 'nep_only') {
      f.nepDrop += nep
      if (r.senate?.source_status === 'inserted') f.inserted += sv
    }
    else if (r.type === 'senate_insertion' || (annexCoverage && r.type === 'senate_only')) f.inserted += sv
  }
  return f
}

function signedBudget(amount) {
  return `${amount < 0 ? '−' : amount > 0 ? '+' : ''}${fmtM(Math.abs(amount) / 1e6)}`
}

function StageChangeSummary({ changes }) {
  const rows = [
    ['Insertions / new funding', 'insertions'],
    ['Removals / cuts to zero', 'removals'],
    ['Increases to funded lines', 'increases'],
    ['Decreases to funded lines', 'decreases'],
  ]
  return <div className="flow-change-summary">
    <h3 id="flow-change-title">What changed at each stage</h3>
    <div className="control-table" tabIndex={0} role="region" aria-labelledby="flow-change-title">
      <table>
        <thead><tr><th scope="col">Budget movement</th><th scope="col">NEP to House</th>
          <th scope="col">House to Senate</th></tr></thead>
        <tbody>
          {rows.map(([label, key]) => <tr key={key}>
            <th scope="row">{label}</th>
            <td>{signedBudget(changes.nep_house[key])}</td>
            <td>{signedBudget(changes.house_senate[key])}</td>
          </tr>)}
        </tbody>
        <tfoot><tr><th scope="row">Net change</th>
          {[changes.nep_house.net, changes.house_senate.net].map((amount, index) =>
            <td key={index}>{amount > 0 ? 'Increase ' : amount < 0 ? 'Decrease ' : ''}{signedBudget(amount)}</td>)}
        </tr></tfoot>
      </table>
    </div>
    <p className="sflow">NEP-to-House amounts use the explorer’s project links. Unlinked records contribute
      to insertions or removals in this comparison. House-to-Senate amounts use the printed annex rows,
      so a replacement can appear as both a cut and an insertion.</p>
  </div>
}

export default function Flow({ projects, totals, nia = false, senateScope, stageChanges }) {
  const ref = useRef(null)
  useEffect(() => {
    const f = flowAmounts(projects, Boolean(senateScope))
    const chart = init(ref.current)
    const nepOnly = nia ? 'NEP without House link' : 'dropped (NEP-only)'
    const houseOnly = nia ? 'House without NEP link' : 'House insertions'
    const outsideAnnex = 'House projects outside A-4'
    const nodes = [
      { name: 'NEP', itemStyle: { color: stageColor.nep } },
      { name: 'House', itemStyle: { color: stageColor.house } },
      { name: nepOnly, itemStyle: { color: '#6b7380' } },
      { name: houseOnly, itemStyle: { color: '#c48a1a' } },
      ...(f.outsideAnnex ? [{ name: outsideAnnex, itemStyle: { color: '#6b7380' } }] : []),
      { name: 'cut', itemStyle: { color: statusColor.cut } },
      { name: 'renamed', itemStyle: { color: statusColor.renamed } },
      { name: 'raised', itemStyle: { color: statusColor.raised } },
      { name: 'reduced', itemStyle: { color: statusColor.reduced } },
      { name: 'inserted', itemStyle: { color: statusColor.inserted } },
      ...(nia ? [{ name: 'same amount', itemStyle: { color: '#6b7380' } }] : []),
      { name: 'Senate', itemStyle: { color: stageColor.senate } },
    ]
    const flowValue = nia ? (value) => value : Math.round
    const links = [
      { source: 'NEP', target: 'House', value: flowValue(f.nepHouse) },
      { source: 'NEP', target: nepOnly, value: flowValue(f.nepDrop) },
      { source: houseOnly, target: 'House', value: flowValue(f.houseInsert) },
      { source: 'House', target: outsideAnnex, value: f.outsideAnnex },
      { source: 'House', target: 'cut', value: flowValue(f.cut) },
      { source: 'House', target: 'renamed', value: flowValue(f.renamed) },
      { source: 'House', target: 'raised', value: flowValue(f.raised) },
      { source: 'House', target: 'reduced', value: flowValue(f.reduced) },
      { source: 'renamed', target: 'Senate', value: flowValue(f.renamedSv) },
      { source: 'raised', target: 'Senate', value: flowValue(f.raisedSv) },
      { source: 'reduced', target: 'Senate', value: flowValue(f.reducedSv) },
      ...(nia ? [
        { source: 'House', target: 'same amount', value: f.restated },
        { source: 'same amount', target: 'Senate', value: f.restatedSv },
      ] : []),
      { source: 'inserted', target: 'Senate', value: flowValue(f.inserted) },
    ].filter((l) => l.value > 0)
    const connected = new Set(links.flatMap(({ source, target }) => [source, target]))
    const visibleNodes = nodes.filter(({ name }) => connected.has(name))
    // Keep each ribbon within one column pair. Putting the NEP-only exit above
    // House lets the second source feed House without crossing that exit.
    const orderedColumns = [
      ['NEP', houseOnly],
      [nepOnly, 'House'],
      ['renamed', 'raised', 'reduced', 'same amount', 'cut', 'inserted'],
      ['Senate'],
    ]
    const layoutNodes = senateScope ? nodes : orderedColumns.flatMap((names, depth) =>
      names.flatMap((name) => {
        const node = visibleNodes.find((candidate) => candidate.name === name)
        return node ? [{ ...node, depth }] : []
      }))
    chart.setOption({
      tooltip: { trigger: 'item', formatter: (p) => {
        if (p.dataType === 'edge') return `${p.data.source} → ${p.data.target}: ₱${p.data.value.toLocaleString()}M`
        return `${p.name}`
      } },
      series: [{ type: 'sankey', left: 20, right: 120, top: 18, bottom: 18,
        nodeGap: 12, nodeWidth: 14, orient: 'horizontal',
        ...(senateScope ? {} : { layoutIterations: 0, draggable: false }),
        label: { color: '#dbe2ec', fontSize: 11.5 },
        lineStyle: { color: 'gradient', curveness: 0.5, opacity: .4 },
        emphasis: { focus: 'adjacency' },
        data: layoutNodes, links }],
    })
    const ro = new ResizeObserver(() => chart.resize())
    ro.observe(ref.current)
    return () => { ro.disconnect(); chart.dispose() }
  }, [projects, nia, senateScope])
  return (
    <div className="panel">
      <h2>Stage flow — {senateScope ? "explorer records" : "whole program"} (₱M)</h2>
      <div id="flow" ref={ref}></div>
      <div className="sflow">
        NEP ₱{(totals.nep_m ?? 0).toLocaleString()}M → House ₱{(totals.house_m ?? 0).toLocaleString()}M
        {totals.house_insertion_m != null && ` (${fmtM(totals.house_insertion_m)} in insertions)`} → Senate{senateScope && ` (${senateScope})`} ₱{(totals.senate_m ?? 0).toLocaleString()}M.
        {totals.counts.senate_insertion} {senateScope ? 'A-4 rows without a House link' : 'Senate insertions'}{nia
          ? '. NEP and House flow uses the workbench comparison links.'
          : `; ${totals.replaces_links} replace a cut row.`}
      </div>
      {stageChanges && <StageChangeSummary changes={stageChanges} />}
    </div>
  )
}

export function DpwhStageFlow({ controls, projects, totals }) {
  const [view, setView] = useState('controls')
  return <section className="panel dpwh-stage-flow" aria-labelledby="dpwh-stage-flow-title">
    <h2 id="dpwh-stage-flow-title">DPWH stage flow</h2>
    <label htmlFor="dpwh-flow-view">View</label>
      <select id="dpwh-flow-view" value={view} onChange={(event) => setView(event.target.value)}>
        <option value="controls">Printed budget controls</option>
        <option value="projects">Project actions and links</option>
      </select>
    {view === 'controls' ? <DpwhControlFlow controls={controls} /> : <>
      <p>The project flow follows the explorer’s links from NEP to House and shows
        cuts, revisions, increases, and other actions on the project rows listed in Annex A-4.</p>
      <Flow projects={projects} totals={totals} nia senateScope="Annex A-4 listed rows" />
    </>}
  </section>
}

function DpwhControlFlow({ controls }) {
  const [scope, setScope] = useState('operations')
  const ref = useRef(null)
  const { nep_php: nep, house_php: house, senate_php: senate } = controls[scope]

  useEffect(() => {
    const chart = init(ref.current)
    const stages = [
      { name: 'NEP', depth: 0, itemStyle: { color: stageColor.nep } },
      { name: 'House', depth: 1, itemStyle: { color: stageColor.house } },
      { name: 'Senate committee', depth: 2, itemStyle: { color: stageColor.senate } },
    ]
    const amounts = { NEP: nep, House: house, 'Senate committee': senate }
    const links = [
      { source: 'NEP', target: 'House', value: Math.min(nep, house) },
      { source: 'House', target: 'Senate committee', value: Math.min(house, senate) },
    ]
    for (const [from, to, prior, next, depth] of [
      ['NEP', 'House', nep, house, 0],
      ['House', 'Senate committee', house, senate, 1],
    ]) {
      if (prior === next) continue
      const increase = next > prior
      const name = increase ? `Net increase at ${to}` : `Net reduction at ${to}`
      const value = Math.abs(next - prior)
      amounts[name] = value
      stages.push({ name, depth: increase ? depth : depth + 1,
        itemStyle: { color: increase ? statusColor.raised : statusColor.cut } })
      links.push({ source: increase ? name : from, target: increase ? to : name, value })
    }
    chart.setOption({
      tooltip: { trigger: 'item', formatter: (p) => p.dataType === 'edge'
        ? `${p.data.source} → ${p.data.target}: ${billions(p.data.value)}`
        : `${p.name}: ${billions(amounts[p.name])}` },
      series: [{ type: 'sankey', left: 48, right: 48, top: 26, bottom: 16,
        nodeWidth: 13, nodeGap: 15, draggable: false,
        label: { color: '#dbe2ec', position: 'top', fontSize: 11, width: 93, overflow: 'truncate' },
        lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.45 },
        data: stages, links }],
    })
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(ref.current)
    return () => { observer.disconnect(); chart.dispose() }
  }, [nep, house, senate])

  return <div className="dpwh-control-flow">
    <label htmlFor="dpwh-flow-scope">Budget scope</label>
      <select id="dpwh-flow-scope" value={scope} onChange={(event) => setScope(event.target.value)}>
        <option value="operations">Operations</option>
        <option value="department">Department-wide new appropriations</option>
      </select>
    <p>Ribbons show budget totals and net changes between stages. Project-level links appear in the explorer table.</p>
    <div className="dpwh-flow-chart" ref={ref} aria-hidden="true" />
    <ul className="dpwh-flow-totals">
      <li>NEP <strong>{billions(nep)}</strong></li>
      <li>House <strong>{billions(house)}</strong></li>
      <li>Senate committee <strong>{billions(senate)}</strong></li>
      <li>Senate vs. House <strong>{senate < house ? '−' : senate > house ? '+' : ''}{billions(Math.abs(senate - house))}</strong></li>
    </ul>
    <div className="control-table" tabIndex={0} role="region" aria-label="House-to-Senate program breakdown">
      <table>
        <caption>Where the House-to-Senate change came from</caption>
        <thead><tr><th scope="col">Budget component</th><th scope="col">House</th>
          <th scope="col">Senate committee</th><th scope="col">Net change</th>
          <th scope="col">Carried forward outside A-4</th></tr></thead>
        <tbody>
          {controls.components.map((row) => {
            const change = row.senate_php - row.house_php
            return <tr key={row.name}>
              <th scope="row">{controlLabels[row.name] ?? row.name} <small>p. {row.pdf_page}</small></th>
              <td>{billions(row.house_php)}</td><td>{billions(row.senate_php)}</td>
              <td>{change < 0 ? '−' : change > 0 ? '+' : ''}{billions(Math.abs(change))}</td>
              <td>{billions(row.senate_php - row.listed_php)}</td>
            </tr>
          })}
          {scope === 'department' && <tr>
            <th scope="row">General administration and support to operations</th>
            <td>{billions(controls.department.house_php - controls.operations.house_php)}</td>
            <td>{billions(controls.department.senate_php - controls.operations.senate_php)}</td>
            <td>{billions(0)}</td>
            <td>{billions(controls.department.senate_php - controls.operations.senate_php)}</td>
          </tr>}
        </tbody>
      </table>
    </div>
    <p>Program controls come from Annex A-4. The carried-forward column shows the portion
      of each Senate control outside the listed project rows.</p>
  </div>
}
