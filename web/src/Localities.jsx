import { useMemo, useState } from 'react'
import { fmtM, actionStages, actionChurn, actionLabel, actionColor } from './lib.jsx'

export default function Localities({ localities, onDrill, stages = actionStages, grouping }) {
  const [prov, setProv] = useState('')
  const [minChurn, setMinChurn] = useState(1)
  const [sort, setSort] = useState('churn')
  const [stage, setStage] = useState('house_senate')
  const provinces = useMemo(
    () => [...new Set(localities.map((l) => l.province))].sort(), [localities])

  const stageLabel = stages.find((entry) => entry.key === stage).label
  const rows = useMemo(() => {
    const churn = (l) => stage === 'house_senate' && !grouping ? l.churn
      : Object.entries(l.actions?.[stage] || {}).reduce(
        (total, [action, count]) => total + (grouping || actionChurn.has(action) ? count : 0), 0
      )
    const ls = localities.filter((l) => churn(l) >= minChurn && (!prov || l.province === prov))
    const key = sort === 'churn' ? churn
      : sort === 'chains' ? (l) => l.chains
      : sort === 'delta' ? (l) => (l.senate_m ?? 0) - (l.house_m ?? 0)
      : churn
    return [...ls].sort((a, b) => key(b) - key(a)).slice(0, 25)
  }, [localities, prov, minChurn, sort, stage, grouping])

  // per-stage action totals for the column header
  const stageTotals = useMemo(() => {
    const t = {}
    for (const l of localities) {
      for (const [act, n] of Object.entries((l.actions || {})[stage] || {})) {
        t[act] = (t[act] || 0) + n
      }
    }
    return t
  }, [localities, stage])

  const stageColor = (act) =>
    actionColor[act] || '#6b7380'

  return (
    <div className="panel" id="localities">
      <h2>Grouping analysis — {grouping ? "provinces where any stage acted" : "municipalities where any stage acted"}</h2>
      <div className="filters">
        <select value={prov} onChange={(e) => setProv(e.target.value)}>
          <option value="">{grouping ? "all regions" : "all provinces"}</option>
          {provinces.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select value={minChurn} onChange={(e) => setMinChurn(+e.target.value)}>
          <option value={1}>≥1 action</option>
          <option value={3}>≥3 actions</option>
          <option value={5}>≥5 actions</option>
          <option value={10}>≥10 actions</option>
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="churn">sort: most actions</option>
          <option value="chains">sort: most chains</option>
          <option value="delta">sort: largest Senate Δ₱</option>
        </select>
        <select value={stage} onChange={(e) => setStage(e.target.value)} aria-label="Grouping stage">
          {stages.map((s) => <option key={s.key} value={s.key}>{s.label} actions</option>)}
        </select>
        <span className="sflow" style={{ marginLeft: 'auto' }}>
          {localities.length} {grouping ? "province groups" : "municipalities · realignments happen within these units"}
        </span>
      </div>
      <div className="tablewrap" style={{ maxHeight: 480 }}>
        <table>
          <thead><tr>
            <th>{grouping?.unit ?? "Municipality"}</th><th>{grouping?.parent ?? "Province"}</th><th className="num">Chains</th>
            <th className="num">House ₱</th><th className="num">Senate ₱</th>
            <th className="num">Δ ₱</th><th>
              {stageLabel} actions
              {Object.keys(stageTotals).length > 0 && (
                <span className="sflow" style={{ marginLeft: 6 }}>
                  {Object.entries(stageTotals).sort((a, b) => b[1] - a[1]).slice(0, 3)
                    .map(([a, n]) => `${n} ${actionLabel[a] || a}`).join(' · ')}
                </span>
              )}
            </th><th></th>
          </tr></thead>
          <tbody>
            {rows.map((l) => {
              const delta = (l.senate_m ?? 0) - (l.house_m ?? 0)
              const acts = (l.actions || {})[stage] || {}
              const total = Object.values(acts).reduce((x, y) => x + y, 0)
              return (
                <tr className="row" key={l.key}>
                  <td style={{ fontWeight: 600 }}>{l.municipality}</td>
                  <td style={{ color: 'var(--dim)' }}>{l.province}</td>
                  <td className="num m">{l.chains}</td>
                  <td className="num m">{fmtM(l.house_m)}</td>
                  <td className="num m">{fmtM(l.senate_m)}</td>
                  <td className="num m"
                      style={{ color: delta < 0 ? 'var(--cut)' : delta > 0 ? 'var(--raised)' : 'var(--dim)' }}>
                    {delta ? (delta > 0 ? '+' : '−') + fmtM(Math.abs(delta)) : '—'}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 2, height: 16, minWidth: 140 }}>
                      {Object.entries(acts).sort((a, b) => b[1] - a[1]).map(([act, n]) => (
                        <div key={act} title={`${actionLabel[act] || act}: ${n}`}
                             style={{ width: (100 * n / total) + '%', minWidth: 4,
                                      background: stageColor(act),
                                      borderRadius: 3, opacity: .85 }}></div>
                      ))}
                    </div>
                    <div className="sflow">
                      {Object.entries(acts).filter(([act]) => act !== 'none' && act !== 'carried' && act !== 'unchanged')
                        .sort((a, b) => b[1] - a[1]).slice(0, 3)
                        .map(([act, n]) => `${n} ${actionLabel[act] || act}`).join(' · ')}
                    </div>
                  </td>
                  <td>
                    <button className="linkish" onClick={() => onDrill(l.key)}>
                      {l.chains} chains →
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
