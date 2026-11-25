// Shared annex hierarchy trail with printed roll-up subtotals.
// steps:  printed program → sub-program → activity breadcrumb strings
// rows:   [{ name, amounts, note }] geo roll-up rows (region/province)
// note:   fallback line when the annex prints no geography for the row
export default function AnnexTrail({ steps = [], rows = [], note }) {
  if (!steps.length && !rows.length && !note) return null
  return (
    <div className="annex-trail" aria-label="Annex budget hierarchy">
      {steps.length > 0 && <div className="trail-steps">
        {steps.filter(Boolean).map((step, i) => (
          <span className="trail-step" key={i}>{step}</span>
        ))}
      </div>}
      {rows.length > 0 && <div className="trail-geo">
        {rows.map((row, i) => (
          <div className="geo-row" key={i}>
            <span className="geo-name">{row.name}</span>
            <span className="geo-amt">{row.amounts}</span>
            <span className="geo-note">{row.note}</span>
          </div>
        ))}
      </div>}
      {note && rows.length === 0 && <div className="geo-note">{note}</div>}
    </div>
  )
}
