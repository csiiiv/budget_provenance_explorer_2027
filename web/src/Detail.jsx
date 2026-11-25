import { useState } from 'react'
import Trail from './AnnexTrail.jsx'
import StageRail from './StageRail.jsx'
import {
  Chip, coordsDiffer, fmtCoords, fmtM, nepHouseChips, houseSenateChips, actionLabel,
  reasonLabel, statusLabel, titlesDiffer, typeLabel, typeShort,
} from './lib.jsx'

function explainRec(rec) {
  if (rec.type === 'senate_insertion' && rec.replaces) {
    const why = reasonLabel[rec.replaces.reason] || 'corrected'
    return { kind: 'Senate realignment (delete + insert)',
      body: `Annex A-1 cut the House road to ₱0, then printed this new row for ${fmtM(rec.senate?.sv_m)} — ${why}. Same project, not a brand-new road. NEP / House / DA live on the House chain (${rec.replaces.house_id}).` }
  }
  if (rec.type === 'senate_insertion') {
    return { kind: 'Documented Senate addition',
      body: `This row appears only on the Senate side of Annex A-1 (no House/GAB amount). It was not linked to a preceding cut in the same region, so we treat it as a net new Senate road rather than a realignment.` }
  }
  if (rec.type === 'nep_only') {
    if (rec.senate?.status === 'reinstated') {
      return { kind: 'NEP road dropped by the House, restored by the Senate',
        body: rec.senate.match === 'da_revision_matches_senate'
          ? `The Senate annex lists a ${fmtM(rec.senate.sv_m)} insertion matching the DA proposal for this NEP road.`
          : rec.senate.match === 'da_coordinate_correction'
          ? `The Senate annex lists a ${fmtM(rec.senate.sv_m)} insertion with the corrected DA coordinates for this NEP road.`
          : rec.senate.source_status === 'inserted'
          ? `The Senate annex lists a ${fmtM(rec.senate.sv_m)} insertion with the same title, amount, and endpoints as the NEP road.`
          : `The House bill did not carry this NEP road forward, but the Senate committee restored it as ${fmtM(rec.senate.sv_m)} — printing the old (NEP) title alongside the corrected title on one amendment line. The Senate even fixed the NEP's own typos (e.g. "Tiocos Sur" → "Ilocos Sur", "Nagsantaan" endpoint reflected in the new name).` }
    }
    return { kind: 'Dropped between NEP and House',
      body: `Present in the NEP at ${fmtM(rec.nep?.amount_m)}, but no matching House Vol I-B row. The House bill did not carry this road forward.` }
  }
  if (rec.type === 'da_only') {
    return { kind: 'DA draft row without NEP/House link',
      body: `Appears in the DA working draft (control ${rec.da12?.ctrl || rec.da5?.ctrl || '—'}) but we have no match edge into our NEP or House locators yet.` }
  }
  if (rec.type === 'house' && rec.restated_by) {
    const why = reasonLabel[rec.restated_by.reason] || 'corrected'
    return { kind: 'House road realigned by the Senate',
      body: `Annex A-1 prints this as a cut (₱0) plus a paired insertion (${fmtM(rec.restated_by.sv_m)}) — ${why}. Effective Senate funding stays ${fmtM(rec.restated_by.sv_m)}; it is not a net removal.` }
  }
  if (rec.type === 'house' && rec.senate?.status === 'cut') {
    return { kind: 'House road cut by the Senate (true cut)',
      body: `This House road (${fmtM(rec.house_m)}) is listed in Annex A-1 with Senate amount ₱0, and no paired insertion restates it. Net removal from the Senate version.` }
  }
  if (rec.type === 'house' && rec.senate) {
    return { kind: 'Full NEP → House → Senate chain',
      body: `Matched across stages. Senate action: ${statusLabel[rec.senate.status] || rec.senate.status}.` }
  }
  if (rec.type === 'house') {
    return { kind: 'House road not listed in Annex A-1',
      body: `In the House bill${rec.nep ? ' and the NEP' : ' only (House insertion)'}. Annex A-1 does not mention it, so the Senate committee left it unchanged.` }
  }
  return { kind: typeLabel[rec.type] || rec.type, body: '' }
}

function emptyNep(rec) {
  if (rec.type === 'senate_insertion' && rec.replaces)
    return `Not on this card — this is only the Senate insertion. Open the replaced House chain (${rec.replaces.house_id}) for the NEP row.`
  if (rec.type === 'senate_insertion')
    return `No NEP match. A true Senate addition has no Executive proposal behind it.`
  if (rec.type === 'da_only')
    return `No NEP locator linked to this DA control yet.`
  if (rec.house_m != null)
    return `No NEP row — this is a House insertion (added in HB 10858, not in the Executive proposal).`
  return `No NEP row linked.`
}

function emptyHouse(rec) {
  if (rec.type === 'senate_insertion' && rec.replaces)
    return `Not on this card — the House amount sits on the cut row’s chain (${rec.replaces.house_id}, ${fmtM(rec.replaces.gab_m)}).`
  if (rec.type === 'senate_insertion')
    return `No House/GAB amount printed — Annex A-1 marks this as a Senate-side insertion.`
  if (rec.type === 'nep_only') {
    if (rec.senate?.status === 'reinstated')
      return `Never appeared in HB 10858 Vol I-B — the House dropped this NEP road. The Senate amendment below restores it at ${fmtM(rec.senate.sv_m)}.`
    return `Never appeared in HB 10858 Vol I-B. Dropped (or never paired) between NEP and House.`
  }
  if (rec.type === 'da_only')
    return `No House locator linked to this DA control yet.`
  return `Not in the House bill.`
}

function emptyDa(rec) {
  if (rec.type === 'senate_insertion' && rec.replaces)
    return `DA drafts are attached to the House/NEP chain, not to Senate insertion cards. Check ${rec.replaces.house_id}.`
  if (rec.type === 'senate_insertion')
    return `DA working drafts only cover House/NEP roads; a pure Senate insertion has no DA row.`
  if (rec.type === 'nep_only')
    return `No DA draft linked — the road never reached the House pairing that DA keys off.`
  return `No DA working-draft row linked to this chain (DA coverage is partial).`
}

function emptySenate(rec) {
  if (rec.type === 'nep_only') {
    if (rec.senate?.status === 'reinstated')
      return `This chain HAS a Senate amendment — see the stage below.`
    return `Not in Annex A-1 — the Senate only lists roads it changes; this one already left at NEP.`
  }
  if (rec.type === 'da_only')
    return `Not in Annex A-1.`
  return `Not listed in Annex A-1. For FMR the annex is change-only, so this usually means the Senate left the House amount as-is.`
}

// Annex A-1 groups roads under one program heading and 16 region
// sub-headings whose printed subtotals are the roll-up evidence.
function AnnexTrailWrap({ rec }) {
  const s = rec.senate || {}
  const sub = s.region_subtotal
  if (!sub) return null
  const eff = rec.restated_by?.sv_m ?? s.sv_m
  const share = sub.sv_php ? `${Math.round((eff * 1e6) / sub.sv_php * 1000) / 10}%` : null
  return <Trail
    rows={[{
      name: sub.name || s.region_label,
      amounts: `House ${fmtM(sub.gab_php / 1e6)} → Senate ${fmtM(sub.sv_php / 1e6)}`,
      note: `${share ? `this row is ${share} of it` : 'region subtotal'} · annex p.${sub.pdf_page}`,
    }]}
  />
}

export function DeltaBar({ label, chips, note }) {
  const changed = chips.some((c) => c.cls && c.cls !== 'muted')
  return (
    <div className={'delta ' + (changed ? 'changed' : 'same')}>
      <div className="dlab">{label}</div>
      <div className="chips">{chips.map((c, i) => <Chip key={i} text={c.text} cls={c.cls} />)}</div>
      {note && <div className="empty" style={{ marginTop: 5 }}>{note}</div>}
    </div>
  )
}

export function FieldDiff({ label, from, to, mono }) {
  if (from == null && to == null) return null
  const same = from != null && to != null && String(from) === String(to)
  const cls = mono ? 'coords' : ''
  if (same || from == null || to == null) {
    const v = to ?? from
    return (
      <div className="field">
        <div className="flab">{label}</div>
        <div className={'fsame ' + cls}>{v}</div>
      </div>
    )
  }
  return (
    <div className="field">
      <div className="flab">{label} — changed</div>
      <div className={'fold ' + cls}>{from}</div>
      <div className={'fnew ' + cls}>{to}</div>
    </div>
  )
}

export function Flags({ flags }) {
  if (!flags || !flags.length) return null
  return <div className="flagrow">{flags.map((f, i) => <span key={i} className="flag">⚑ {f}</span>)}</div>
}

export function Remark({ text, label }) {
  if (!text) return null
  return <div className="remark"><span className="rlab">{label || 'DA remark'}</span>{text}</div>
}

export function DetailTable({ label, pairs }) {
  const rows = pairs.filter(([, value]) => value != null && value !== '')
  if (!rows.length) return null
  return (
    <table className="detail-table">
      <caption>{label}</caption>
      <tbody>{rows.map(([name, value]) => (
        <tr key={name}><th scope="row">{name}</th><td>{value}</td></tr>
      ))}</tbody>
    </table>
  )
}

export function Meta({ pairs }) {
  return (
    <div className="meta">
      {pairs.filter(([k, v]) => v != null && v !== '')
        .map(([k, v], i) => <span key={i}><b style={{ color: 'var(--faint)' }}>{k}:</b> {v}</span>)}
    </div>
  )
}

function SourceFindings({ reviews, document }) {
  const issues = [...new Set(
    [...(reviews?.nov5 || []), ...(reviews?.nov12 || [])]
      .filter((finding) => finding.document === document)
      .map((finding) => finding.issue)
      .filter(Boolean)
  )]
  if (!issues.length) return null
  return (
    <div className="source-findings">
      <h5 className="review-open">⚑ Review findings</h5>
      <ul>{issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
    </div>
  )
}

function DaDraft({ rec, vintage }) {
  const [compare, setCompare] = useState(false)
  const draftName = vintage === 'da5' ? 'November 5' : 'November 12'
  const original = rec[vintage]
  const revision = rec.da_revision?.[vintage]
  const draft = revision || original
  const findings = rec.da_reviews?.[vintage === 'da5' ? 'nov5' : 'nov12'] || []
  const issues = [...new Set(findings.map((finding) => finding.issue).filter(Boolean))]
  const outcomes = [...new Set(findings.map((finding) => finding.status))]
  const earlier = rec.da_revision?.da5 || rec.da5
  const later = rec.da_revision?.da12 || rec.da12
  const sameDraft = earlier && later && earlier.disposition === later.disposition
    && (earlier.title || rec.title) === (later.title || rec.title)
    && earlier.proposed_m === later.proposed_m
    && JSON.stringify(earlier.to_coords ?? null) === JSON.stringify(later.to_coords ?? null)
  const correction = revision?.disposition === 'new' ? 'DA coordinate correction' : 'DA revised listing'
  const disposition = (row) => row ? actionLabel[row.disposition] || row.disposition || '—' : 'No draft'

  return (
    <section className="stage">
      <h4>DA working draft · {draftName}</h4>
      {issues.map((issue) => <p className="draft-finding" key={issue}>{issue}</p>)}
      {outcomes.length > 0 && <div className="draft-outcome">
        {outcomes.map((outcome) => <div key={outcome}>{outcome}</div>)}
      </div>}
      {draft ? <>
        <FieldDiff label={revision ? correction : 'Project title'} to={draft.title || rec.title} />
        <DetailTable label="Draft allocation" pairs={[
          ['Disposition', revision ? disposition(original) + ' → ' + disposition(revision) : disposition(draft)],
          ['Baseline amount', draft.from_m == null ? null : fmtM(draft.from_m)],
          ['Proposed amount', fmtM(draft.proposed_m)],
        ]} />
        {vintage === 'da12' && sameDraft && revision && <p>Correction carried forward from Nov 5.</p>}
      </> : <p className="empty">{emptyDa(rec)}</p>}
      {(earlier || later) && <button type="button" className="draft-compare"
        aria-expanded={compare} onClick={() => setCompare(!compare)}>Compare drafts</button>}
      {compare && <div className="draft-comparison">
        <table>
          <thead><tr><th scope="col">Field</th><th scope="col">Nov 5</th><th scope="col">Nov 12</th></tr></thead>
          <tbody>
            <tr><th scope="row">Disposition</th><td>{disposition(earlier)}</td><td>{disposition(later)}</td></tr>
            <tr><th scope="row">Proposed amount</th><td>{fmtM(earlier?.proposed_m)}</td><td>{fmtM(later?.proposed_m)}</td></tr>
            <tr><th scope="row">Title</th><td>{earlier ? earlier.title || rec.title : '—'}</td><td>{later ? later.title || rec.title : '—'}</td></tr>
            {coordsDiffer(earlier?.to_coords, later?.to_coords) && <tr>
              <th scope="row">Endpoints</th><td className="coords">{fmtCoords(earlier.to_coords)}</td>
              <td className="coords">{fmtCoords(later.to_coords)}</td>
            </tr>}
            <tr><th scope="row">Review</th>{['nov5', 'nov12'].map((key) => <td key={key}>
              {[...new Set(rec.da_reviews?.[key]?.map((finding) => finding.status))].join(' · ') || '—'}
            </td>)}</tr>
          </tbody>
        </table>
      </div>}
      {(draft || findings.length > 0) && <details className="source-evidence">
        <summary>Source evidence</summary>
        {original && <>
          <FieldDiff label="Original listing" to={original.title || rec.title} />
          <DetailTable label="Workbook source" pairs={[['Control', original.ctrl], ['disposition', disposition(original)],
                        ['proposed amount', fmtM(original.proposed_m)], ['Excel row', original.excel_row], ['match side', original.match_side]]} />
          <Remark text={original.remark} />
        </>}
        {draft && <FieldDiff label="GPS coordinates" mono
          from={coordsDiffer(original?.from_coords, draft.to_coords) ? fmtCoords(original.from_coords) : null}
          to={fmtCoords(draft.to_coords || draft.from_coords)} />}
        {revision && <>
          <Meta pairs={[['corrected control', rec.da_revision.ctrl], ['Senate row', rec.da_revision.senate_id]]} />
          <Remark text={revision.remark} />
        </>}
        {findings.map((finding) => <div key={finding.id} className="repbox evidence">
          <div className="lab">{finding.status}</div>
          <p>{finding.issue}</p>
          <Remark text={finding.remarks} />
          <Remark label="Endpoint review" text={finding.endpoint_review} />
          <Meta pairs={[['flag', finding.id], ['source', finding.document], ['evidence', finding.evidence]]} />
        </div>)}
      </details>}
    </section>
  )
}

export function Downloads({ program }) {
  const [open, setOpen] = useState(false)
  const base = `data/export/${program}/`
  const files = [
    ['chains-simple.csv', 'Chains — simple CSV', 'One row per chain: the explorer table view with ids, geography, stage amounts in integer pesos, senate citation, actions, review flags.'],
    ['chains-full.csv', 'Chains — full CSV', 'Every scalar field, stage-prefixed; coordinates and evidence arrays JSON-encoded per cell.'],
    ['findings.csv', 'Findings CSV', 'One row per review finding, keyed by chain id.'],
    ['rollups.csv', 'Printed roll-ups CSV', 'The annex\'s own region/province subtotals with leaf sums and a per-row reconciliation check.'],
    ['full.json', 'Full JSON + manifest', 'Verbatim chain records plus input hashes and totals — the lossless export.'],
    ['SHA256SUMS.txt', 'SHA256SUMS', 'Hashes of every file above.'],
  ]
  return (
    <>
      <button type="button" className="dlbtn" onClick={() => setOpen(true)}>
        ⬇ Download Data
      </button>
      {open && <div className="dlmodal" role="dialog" aria-modal="true"
        aria-label="Download data" onClick={() => setOpen(false)}
        onKeyDown={(event) => { if (event.key === 'Escape') setOpen(false) }}>
        <div className="dlcard" onClick={(event) => event.stopPropagation()}>
          <button type="button" className="close" autoFocus aria-label="Close download dialog"
            onClick={() => setOpen(false)}>✕</button>
          <h3>Download {program.toUpperCase()} data</h3>
          <p className="dlsub">Static files generated with this explorer's bundle —
            amounts in integer pesos, explicit zero prints 0, missing stays empty.
            Verify integrity with SHA256SUMS.</p>
          <ul>
            {files.map(([name, label, note]) => (
              <li key={name}>
                <a href={base + name} download onClick={() => setOpen(false)}>{label}</a>
                <span className="dlnote">{note}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>}
    </>
  )
}

export default function Detail({ rec, initialStage, projects, onClose, onJump }) {
  const [selected, setSelected] = useState(initialStage ??
    (rec.type === 'senate_insertion' ? 'senate' : rec.type === 'da_only' ? 'da12' : rec.nep ? 'nep' : 'house'))
  const stage = (title, color, body, missing) => (
    <div className={'stage' + (missing ? ' missing' : '')} key={title}>
      <h4 style={{ color: missing ? undefined : color }}>{title}</h4>{body}
    </div>
  )
  const empty = (text) => <div className="empty">{text}</div>
  const expl = explainRec(rec)
  const linked = rec.replaces?.house_id
    ? projects.find((p) => p.id === rec.replaces.house_id) : null
  const statusBlurb = {
    cut: 'Senate amount set to ₱0 with no paired insertion — a true net removal.',
    realigned: 'Annex prints a cut + insertion pair; effective Senate funding continues after correction.',
    inserted: 'New Senate-side row (no House/GAB amount on this annex line).',
    renamed: 'Same peso amount; committee prints a revised project name (and often coordinates).',
    raised: 'Senate amount higher than the House/GAB amount.',
    reduced: 'Senate amount lower than the House/GAB amount, but not zero.',
    restated: 'Relisted in the annex with the same amount.',
    reinstated: 'NEP road the House dropped — the Senate restored it (amendment row: old title + new title, no House amount).',
  }
  const effSenateAmt = rec.senate?.status === 'realigned' && rec.restated_by
    ? rec.restated_by.sv_m : rec.senate?.sv_m

  return (
    <ProjectDrawer rec={rec} selected={selected} onSelect={setSelected} onClose={onClose}>
      {(selected === 'da5' || selected === 'da12' || selected === 'senate') &&
        (rec.da_replacement || rec.da_replacement_of) && (
          <div className="callout">
            <div className="kind">DA-documented replacement</div>
            <div>{(rec.da_replacement || rec.da_replacement_of).title}</div>
            {selected === 'senate' && rec.da_replacement && (
              <>
                <p>{rec.da_replacement.basis
                  ? 'Both DA drafts list the title correction immediately after the dropped original.'
                  : 'The DA review annex links the original and corrected road.'}
                  {' '}The Senate annex records a cut and an insertion.</p>
                <Meta pairs={[['cut row amount', fmtM(rec.senate?.sv_m)],
                              ['paired insertion amount', fmtM(rec.da_replacement.amount_m)]]} />
              </>
            )}
            <button type="button" className="linkish"
              onClick={() => onJump((rec.da_replacement || rec.da_replacement_of).id)}>
              {rec.da_replacement ? 'Open corrected entry' : 'Open original entry'}
            </button>
          </div>
        )}

      {(selected === 'da5' || selected === 'da12') && rec.da_evidence?.id && (
        <div className="callout">
          <div className="kind">Possible DA → Senate match</div>
          <p>Same amount and both endpoints. The titles differ.</p>
        </div>
      )}
      {(selected === 'da5' || selected === 'da12') && rec.possible_senate_match && (
        <div className="callout">
          <div className="kind">Possible Senate match</div>
          <p>Same amount and endpoints. The Senate title differs.</p>
          <div>{rec.possible_senate_match.title}</div>
          <button type="button" className="linkish"
            onClick={() => onJump(rec.possible_senate_match.id)}>Open Senate entry</button>
        </div>
      )}
      {selected === 'nep' && stage('NEP — National Expenditure Program', '#4f8ff7',
        <>
        <SourceFindings reviews={rec.da_reviews} document="2027 NEP" />
        {rec.nep ? <>
          <FieldDiff label="Project title" from={null} to={rec.nep.title} />
          <FieldDiff label="GPS coordinates" mono={true}
            from={coordsDiffer(rec.nep.coords, rec.house_coords) ? fmtCoords(rec.nep.coords) : null}
            to={fmtCoords(rec.nep.coords)} />
          <Flags flags={rec.nep.flags} />
          <DetailTable label="Allocation" pairs={[[ 'NEP amount', fmtM(rec.nep.amount_m)]]} />
          <DetailTable label="Source reference" pairs={[
            ['Source ID', rec.nep.id], ['PDF page', rec.nep.page], ['Match method', rec.nep.match],
          ]} />
        </> : empty(emptyNep(rec))}</>, !rec.nep)}

      {selected === 'house' && <>
      <DeltaBar label="NEP → House" chips={nepHouseChips(rec)}
        note={rec.nep?.match ? 'Join method: ' + rec.nep.match : null} />

      {stage('House — HB 10858 Vol I-B (2nd reading)', '#f5a623',
        <>
        <SourceFindings reviews={rec.da_reviews} document="2027 GAB" />
        {rec.house_m != null ? <>
          <FieldDiff label="Project title"
            from={titlesDiffer(rec.nep?.title, rec.title) ? rec.nep.title : null}
            to={rec.title} />
          <DetailTable label="Amounts" pairs={[
            ['NEP', rec.nep && fmtM(rec.nep.amount_m)], ['House', fmtM(rec.house_m)],
          ]} />
          <FieldDiff label="GPS coordinates" mono={true}
            from={coordsDiffer(rec.nep?.coords, rec.house_coords) ? fmtCoords(rec.nep.coords) : null}
            to={fmtCoords(rec.house_coords)} />
          <Flags flags={rec.house_flags} />
          <DetailTable label="Source reference" pairs={[[ 'PDF page', rec.house_page]]} />
        </> : empty(emptyHouse(rec))}</>, rec.house_m == null)}

      </>}
      {(selected === 'da5' || selected === 'da12') && <DaDraft rec={rec} vintage={selected} />}

      {selected === 'senate' && <>
      <div className="callout">
        <div className="kind">{expl.kind}</div>
        <div>{expl.body}</div>
      </div>

      {rec.possible_senate_restatement && (
        <div className="callout">
          <div className="kind">Possible Senate restatement</div>
          <p>The adjacent annex rows share the amount and endpoints. The insertion extends the route title.</p>
          <div>{rec.possible_senate_restatement.title}</div>
          {rec.possible_senate_restatement.amount_m != null && (
            <Meta pairs={[['cut row amount', fmtM(rec.senate?.sv_m)],
                          ['possible paired insertion amount', fmtM(rec.possible_senate_restatement.amount_m)]]} />
          )}
          <button type="button" className="linkish"
            onClick={() => onJump(rec.possible_senate_restatement.id)}>Open related Senate entry</button>
        </div>
      )}
      <DeltaBar label="House → Senate (Annex A-1)" chips={houseSenateChips(rec)}
        note={statusBlurb[rec.senate?.status] || null} />

      {stage('Senate — Committee Report Annex A-1', '#2fbf71',
        rec.senate ? <>
          <AnnexTrailWrap rec={rec} />
          <FieldDiff label="Project title (House text → Senate text)"
            from={titlesDiffer(rec.senate.hb_title, rec.senate.senate_title)
              ? rec.senate.hb_title
              : (rec.restated_by && titlesDiffer(rec.senate.hb_title, rec.restated_by.title)
                  ? rec.senate.hb_title : null)}
            to={rec.restated_by?.title || rec.senate.senate_title || rec.senate.hb_title} />
          <DetailTable label="Amounts" pairs={[
            ['House', rec.senate.gab_m == null ? null : fmtM(rec.senate.gab_m)],
            ['Senate', fmtM(effSenateAmt)],
          ]} />
          <FieldDiff label="GPS coordinates" mono={true}
            from={coordsDiffer(
                rec.restated_by?.from_coords || rec.senate.hb_coords,
                rec.restated_by?.to_coords || rec.senate.senate_coords)
              ? fmtCoords(rec.restated_by?.from_coords || rec.senate.hb_coords) : null}
            to={fmtCoords(rec.restated_by?.to_coords || rec.senate.senate_coords
              || rec.senate.hb_coords)} />
          <DetailTable label="Annex A-1 source" pairs={[['Status', statusLabel[rec.senate.status]],
                        ['annex action', rec.senate.source_status], ['annex page', rec.senate.page], ['match', rec.senate.match],
                        ['annex row', rec.senate.id]]} />
        </> : empty(emptySenate(rec)), !rec.senate)}

      {rec.restated_by && (
        <div className="repbox">
          <div className="lab">⇄ Paired Senate insertion (realignment)</div>
          <div className="empty" style={{ marginTop: 6 }}>
            {reasonLabel[rec.restated_by.reason] || 'Corrected'}. Annex deleted this House line
            and re-inserted it as <b>{rec.restated_by.id}</b> for {fmtM(rec.restated_by.sv_m)}.
            Effective Senate funding is the insertion amount, not ₱0.
          </div>
          <FieldDiff label="Title" from={null} to={rec.restated_by.title} />
          <FieldDiff label="GPS (cut → insertion)" mono={true}
            from={fmtCoords(rec.restated_by.from_coords)}
            to={fmtCoords(rec.restated_by.to_coords)} />
          <Meta pairs={[['reason', rec.restated_by.reason],
                        ['similarity', rec.restated_by.similarity + '%'],
                        ['cut annex row', rec.restated_by.cut_id],
                        ['insertion annex row', rec.restated_by.id]]} />
          <div style={{ marginTop: 8 }}>
            <button className="linkish" onClick={() => onJump(rec.restated_by.id)}>
              Open paired insertion ({rec.restated_by.id}) →
            </button>
          </div>
        </div>
      )}

      {rec.subst_candidates?.length > 0 && (
        <div className="repbox evidence">
          <div className="lab">⚠ Possible substitution (not asserted)</div>
          <div className="empty" style={{ marginTop: 6 }}>
            This House road was cut by the Senate with no linked insertion, but DA’s working
            draft already proposed dropping it and adding nearby new roads
            ({rec.subst_candidates.length === 1 ? 'this one is' : 'these are'}) within
            2 km of the cut GPS. Circumstantial only — the Senate annex prints them as
            separate lines with different locations.
          </div>
          {rec.subst_candidates.map((c, i) => (
            <div key={i} style={{ marginTop: 8, borderTop: '1px dashed var(--line)', paddingTop: 8 }}>
              <div className="t">{c.title}</div>
              <Meta pairs={[['DA control', c.ctrl], ['distance', c.km + ' km from cut GPS'],
                            ['DA proposed', c.da_proposed_m != null ? fmtM(c.da_proposed_m) : null]]} />
              <Remark text={c.remark} />
            </div>
          ))}
        </div>
      )}

      {(rec.da_evidence || rec.da_revision || rec.type === 'senate_insertion') && (
        <div className="repbox evidence">
          <div className="lab">DA → Senate comparison</div>
          {rec.da_evidence?.exact || rec.da_revision ? (
            <>
              <p>The DA Nov 12 proposal and the Senate line agree on title, amount, and both endpoints.</p>
              <Meta pairs={[
                ['DA control', rec.da_evidence?.ctrl || rec.da_revision?.ctrl],
                ['DA proposal', fmtM((rec.da_revision?.da12 || rec.da12)?.proposed_m)],
                ['Senate amount', fmtM(rec.da_replacement?.amount_m ?? rec.restated_by?.sv_m ?? rec.senate?.sv_m)],
              ]} />
            </>
          ) : rec.da_evidence ? (
            <>
              <p>Possible DA match on {rec.da_evidence.basis} ({rec.da_evidence.ctrl}).</p>
              {rec.da_evidence.id && <>
                <div>{rec.da_evidence.title}</div>
                <button type="button" className="linkish"
                  onClick={() => onJump(rec.da_evidence.id, 'da12')}>Open DA Nov 12 entry</button>
              </>}
            </>
          ) : (
            <p>No matching DA proposal was identified in the available drafts.</p>
          )}
        </div>
      )}

      {rec.replaces && (
        <div className="repbox">
          <div className="lab">⇄ Realigns a cut House road</div>
          <div className="empty" style={{ marginTop: 6 }}>
            Annex pattern: print the House road as a <b>cut</b> (Senate ₱0), then print this
            <b>insertion</b> ({fmtM(rec.senate?.sv_m)}) — {reasonLabel[rec.replaces.reason] || 'corrected'}.
            Similarity {rec.replaces.similarity}% vs the cut title.
          </div>
          <FieldDiff label="Title (cut → this insertion)"
            from={titlesDiffer(rec.replaces.hb_title, rec.title) ? rec.replaces.hb_title : null}
            to={rec.title} />
          <FieldDiff label="GPS (cut → insertion)" mono={true}
            from={fmtCoords(rec.replaces.from_coords)}
            to={fmtCoords(rec.replaces.to_coords)} />
          <Meta pairs={[['reason', rec.replaces.reason],
                        ['cut GAB amount', fmtM(rec.replaces.gab_m)],
                        ['cut annex row', rec.replaces.id],
                        ['House locator', rec.replaces.house_id]]} />
          {rec.replaces.house_id && (
            <div style={{ marginTop: 8 }}>
              <button className="linkish" onClick={() => onJump(rec.replaces.house_id)}>
                Open full NEP → House → DA → realigned chain ({rec.replaces.house_id}) →
              </button>
            </div>
          )}
          {linked && (
            <div className="empty" style={{ marginTop: 8 }}>
              On that chain: NEP {fmtM(linked.nep?.amount_m)} · House {fmtM(linked.house_m)} ·
              DA {linked.da5?.disposition || '—'} · Senate {statusLabel[linked.senate?.status] || '—'}
            </div>
          )}
        </div>
      )}
      </>}
    </ProjectDrawer>
  )
}

export function ProjectDrawer({ rec, selected, onSelect, onClose, Rail = StageRail, typeLabel, titleDetails, children }) {
  return (
    <aside className="detail open" aria-label="Project details" onKeyDown={(event) => { if (event.key === 'Escape') onClose() }}>
      <div className="drawer-header">
      <button className="close" autoFocus aria-label="Close project details" onClick={onClose}>✕</button>
      <h3>{rec.title}</h3>
      {titleDetails}
      <div className="meta drawer-meta">
        <span className="typepill">{typeLabel || typeShort[rec.type] || rec.type}</span>
        <span><b style={{ color: 'var(--faint)' }}>id:</b> {rec.id}</span>
        <span><b style={{ color: 'var(--faint)' }}>region:</b> {rec.region_label || rec.region || '—'}</span>
        {rec.municipality && (
          <span><b style={{ color: 'var(--faint)' }}>locality:</b> {rec.municipality}, {rec.province}</span>
        )}
      </div>

      <Rail project={rec} selected={selected} onSelect={onSelect} />
      </div>
      <div className="drawer-body" key={selected}>
        {children}
      </div>
    </aside>
  )
}
