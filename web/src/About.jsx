import { createRoot } from "react-dom/client"
import "./styles.css"
import "./about.css"
import SiteNav from "./SiteNav.jsx"

import { lazy, Suspense, useEffect } from "react"
import { guides, guideDownload, guideUrl, scrollToFragment } from "./guides.js"

const GuideReader = lazy(() => import("./GuideReader.jsx"))

function About() {
  const guide = new URLSearchParams(window.location.search).get("guide")
  const selected = guides.flatMap(([, links]) => links).find(([name]) => name === guide)

  useEffect(() => {
    if (!selected) scrollToFragment()
  }, [selected])

  return (
    <>
      <SiteNav current="about" />
      {selected ? (
        <Suspense fallback={<main className="about" role="status">Loading guide…</main>}>
          <GuideReader name={selected[0]} title={selected[1]} />
        </Suspense>
      ) : <main className="about">
        <div className="about-intro">
          <h1>How the budget provenance explorers work</h1>
          <p>Follow a Philippine FY2027 budget item from the National Expenditure Program (NEP) through
            the House bill and Senate committee amendments. Agency drafts and review records add evidence
            about proposed revisions, flagged issues, and how they were resolved.</p>
        </div>

        <div className="about-layout">
          <nav className="about-contents" aria-labelledby="about-contents-title">
            <h2 id="about-contents-title">On this page</h2>
            <a href="#records">Records and links</a>
            <a href="#using">Using the explorer</a>
            <a href="#edge-cases">Edge cases</a>
            <a href="#docs">Methodology guides</a>
          </nav>

          <div className="about-body">
            <section id="records" className="about-section">
              <h2>From source records to project chains</h2>
              <dl className="about-concepts">
                <div><dt>Source observation</dt><dd>A row in a particular PDF edition, annex, or workbook.
                  Its locator can include a control number, printed page, PDF page, or workbook row.</dd></div>
                <div><dt>Link</dt><dd>A recorded relationship between two observations. A source citation
                  can establish a link. A unique combination of title, amount, geography, and route
                  endpoints can also support a match. Partial or competing matches stay visible as
                  candidates or unresolved records.</dd></div>
                <div><dt>Project chain</dt><dd>The observations and links grouped for exploration. A chain can
                  skip a stage. The drawer keeps source actions and match evidence visible so you can
                  trace each connection.</dd></div>
              </dl>
              <p>Each comparison has its own baseline. Senate amendments use the cited House amounts.
                Agency drafts can propose changes against the same earlier baseline even when shown
                in date order. The evidence drawer shows the amounts and fields behind each comparison.</p>
            </section>

            <section id="using" className="about-section">
              <h2>Inspect a budget item</h2>
              <ol>
                <li>Search the project table by title or source identifier. Use the action and geography
                  filters to narrow the results.</li>
                <li>Open a row or select a stage in the table. Compare the titles, amounts, source
                  references, and review findings in the drawer.</li>
                <li>Check the match basis and any warnings before interpreting a change. Where available,
                  the Senate trail shows the printed hierarchy, page citation, and verified subtotals.</li>
              </ol>
              <p>The dashboards count several things. Table counts refer to displayed chains, source totals
                refer to the covered budget lines or controls, and review counts refer to findings or
                reviewed rows. A single chain can have multiple findings.</p>
            </section>

            <section id="edge-cases" className="about-section">
              <h2>Edge cases to look for</h2>
              <dl className="about-cases">
                <div><dt>A blank stage and an explicit zero</dt><dd>A blank can indicate an unresolved link,
                  a stage that does not apply, or a coverage gap. A recorded zero is an amount. When a
                  change-only annex omits a covered item, the House amount can carry forward if the
                  source’s omission rules support that reading.</dd></div>
                <div><dt>FMR roads with the same amount and locality</dt><dd>Cabungaan A and B each have a
                  ₱5 million allocation. Their distinct endpoints support separate chains. A possible
                  replacement elsewhere can retain both a printed cut and a printed insertion while
                  the relationship remains under review.</dd></div>
                <div><dt>NIA projects that move between workbook rows</dt><dd>The October and November
                  workbooks can reorder and rename projects. The submitted-list crosswalk and project
                  details help trace records across versions. A title, location, or review finding can
                  change while the allocation stays the same.</dd></div>
                <div><dt>DPWH citations and subtotal rows</dt><dd>Annex A-4 cites printed pages from the
                  third-reading House Volume I-C. The verified eight-page offset applies to that PDF
                  edition. Region and office controls stay at their printed level so adding them to
                  project amounts does not count the same allocations twice.</dd></div>
              </dl>
            </section>

            <section id="docs" className="about-section">
              <h2>Methodology guides</h2>
              <p>Start with <a href={guideUrl("provenance_chaining_considerations")}>Chaining budget records</a>
                {" "}for the matching rules and worked examples. For program-specific evidence, choose the guide
                for FMR, NIA, or DPWH. Each guide can be read here or downloaded as Markdown.</p>
              <div className="about-guides">
                {guides.map(([group, links]) => (
                  <div key={group}>
                    <h3>{group}</h3>
                    <ul>
                      {links.map(([name, title]) => (
                        <li key={name}>
                          <a href={guideUrl(name)}>{title}</a>
                          <a className="about-download" href={guideDownload(name)} download={`${name}.md`}
                            aria-label={`Download ${title} as Markdown`}>Markdown</a>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
      </main>}
    </>
  )
}

createRoot(document.getElementById("app")).render(<About />)
