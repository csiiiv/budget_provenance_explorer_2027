import { fmtM, stageColor } from './lib.jsx'

export default function Regions({ regions, senateScope }) {
  const max = Math.max(1, ...regions.flatMap((r) => [r.nep_m ?? 0, r.house_m ?? 0, r.senate_m ?? 0]))
  const short = (lab, key) => (lab || key || '').replace(/^REGION\s+/i, '').replace(/\s+-\s+/, ' · ')
  const row = (label, v, color) => (
    <div className="rrow" key={label}>
      <div className="rlab" title={label}>{label}</div>
      <div className="rbar">
        <div className="rfill" style={{ width: Math.max(0, 100 * (v ?? 0) / max) + '%', background: color }}></div>
        <span className="rval">{fmtM(v)}</span>
      </div>
    </div>
  )
  return (
    <div className="panel">
      <h2>By region (₱)</h2>
      {senateScope && <p className="sflow">Senate amounts include {senateScope.toLowerCase()} only.</p>}
      <div className="rgrid">
        {[['nep_m', 'NEP', 'nep'], ['house_m', 'House', 'house'], ['senate_m', senateScope || 'Senate', 'senate']].map(
          ([k, lab, c]) => (
            <div className="rcol" key={k}>
              <div className="rh" style={{ color: stageColor[c] }}>{lab}</div>
              {regions.map((r) => row(short(r.label, r.key), r[k], stageColor[c]))}
            </div>
          ),
        )}
      </div>
    </div>
  )
}
