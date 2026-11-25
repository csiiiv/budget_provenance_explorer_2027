const formatAmount = new Intl.NumberFormat('en-PH', {
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
})

export function billions(amount) {
  return amount == null ? '—' : `₱${formatAmount.format(amount / 1e9)}B`
}

export const controlLabels = {
  'ORGANIZATIONAL OUTCOME 1 : Ensure Safe and Reliable National Road System': 'National road system',
  'ORGANIZATIONAL OUTCOME 2 : Protect Lives and Properties Against Major Floods': 'Major flood protection',
  'CONVERGENCE AND SPECIAL SUPPORT PROGRAM': 'Convergence and Special Support Program',
  'LOCALLY-FUNDED PROJECTS': 'Locally funded projects',
  'FOREIGN-ASSISTED PROJECTS': 'Foreign-assisted projects',
}

export default function DpwhBudgetControls({ controls, listed }) {
  const { department, operations, components } = controls
  const outsideOperations = department.senate_php - operations.senate_php
  const rows = [
    ...components,
    { name: 'Operations subtotal', senate_php: operations.senate_php, listed_php: listed },
    { name: 'General administration and support to operations', senate_php: outsideOperations },
  ]

  return <section className="panel budget-controls" aria-labelledby="dpwh-budget-controls">
    <h2 id="dpwh-budget-controls">DPWH budget controls</h2>
    <p>The Senate committee recorded {billions(department.senate_php)} for DPWH. Annex A-4 lists
      { ' ' }{billions(listed)} in Senate project amounts and accounts for the full House-to-Senate change.
      The printed controls also include amounts carried forward from the House.</p>
    <div className="control-table" tabIndex={0} role="region" aria-label="Printed budget controls">
      <table>
        <thead><tr><th scope="col">Scope</th><th scope="col">NEP</th>
          <th scope="col">House</th><th scope="col">Senate committee</th></tr></thead>
        <tbody>
          {[['New general appropriations', department], ['Operations', operations]].map(([label, row]) =>
            <tr key={label}><th scope="row">{label}</th><td>{billions(row.nep_php)}</td>
              <td>{billions(row.house_php)}</td><td>{billions(row.senate_php)}</td></tr>)}
        </tbody>
      </table>
    </div>
    <details>
      <summary>See the Annex A-4 reconciliation by budget component</summary>
      <div className="control-table" tabIndex={0} role="region" aria-label="Annex A-4 reconciliation">
        <table>
          <thead><tr><th scope="col">Budget component</th><th scope="col">Senate control</th>
            <th scope="col">Listed A-4</th><th scope="col">Outside listed rows</th></tr></thead>
          <tbody>
            {rows.map((row) => <tr key={row.name}>
              <th scope="row">{controlLabels[row.name] ?? row.name}{row.pdf_page && <> <small>p. {row.pdf_page}</small></>}</th>
              <td>{billions(row.senate_php)}</td><td>{billions(row.listed_php)}</td>
              <td>{billions(row.senate_php - (row.listed_php ?? 0))}</td>
            </tr>)}
          </tbody>
          <tfoot><tr><th scope="row">DPWH total</th><td>{billions(department.senate_php)}</td>
            <td>{billions(listed)}</td><td>{billions(department.senate_php - listed)}</td></tr></tfoot>
        </table>
      </div>
      <p>Sources are NEP Vol. II-B, printed pp. 2–3, and Senate Annex A-4, p. 1 and the component pages above.</p>
    </details>
    <details>
      <summary>Where to find DPWH amendments in the Senate report</summary>
      <ul className="dpwh-source-list">
        <li><strong>Annex A, Line-by-Line Amendments, printed pp. 115–118 (PDF pp. 125–128).</strong>
          {" "}The DPWH section shows activity and project changes and the same department net reduction,
          rounded to thousands of pesos.</li>
        <li><strong>Annex A-4, project details, p. 1 and following.</strong>
          {" "}Lists DPWH project amendments and their printed controls in pesos. Annex A and A-4
          report the same department-level adjustment, so count it once.</li>
        <li><strong>Committee Report General Summary, PDF p. 5.</strong>
          {" "}The DPWH line confirms the same department total and net reduction in thousands of pesos.</li>
        <li><strong>Annex B, Special and General Provisions, SP–Vol. I-B–1 (PDF p. 63).</strong>
          {" "}The DPWH entry deletes the project-modification provision. It records a change to the
          bill’s text.</li>
      </ul>
    </details>
  </section>
}
