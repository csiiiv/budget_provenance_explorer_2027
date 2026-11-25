import { useEffect, useRef, useState } from "react"
import Markdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeSlug from "rehype-slug"
import { guides, guideDownload, guideUrl, scrollToFragment } from "./guides.js"

const documents = import.meta.glob("../../docs/*.md", { import: "default", query: "?raw" })
const guideNames = new Set(guides.flatMap(([, links]) => links.map(([name]) => name)))
const repository = "https://github.com/csiiiv/DPWH-NEP-HB-2027-ANALYSIS"

function referenceUrl(href) {
  if (href.startsWith("#") || /^[a-z][a-z\d+.-]*:/i.test(href)) return href
  const [path, hash] = href.split("#")
  const fragment = hash ? `#${hash}` : ""
  const guide = path.replace(/^\.\//, "").replace(/\.md$/, "")
  if (guideNames.has(guide)) return guideUrl(guide) + fragment
  if (path.startsWith("../")) {
    const kind = path.endsWith("/") ? "tree" : "blob"
    return `${repository}/${kind}/main/${path.slice(3)}${fragment}`
  }
  return href
}

const components = {
  a: ({ node, href, ...props }) => <a href={href && referenceUrl(href)} {...props} />,
  table: ({ node, ...props }) => (
    <div className="guide-table" tabIndex={0} role="region" aria-label="Guide table">
      <table {...props} />
    </div>
  ),
}

export default function GuideReader({ name, title }) {
  const article = useRef(null)
  const [source, setSource] = useState(null)
  const [headings, setHeadings] = useState([])
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    document.title = `${title} | FY2027 Budget Explorers`
    let active = true
    documents[`../../docs/${name}.md`]().then((text) => {
      if (active) setSource(text)
    }).catch(() => {
      if (active) setFailed(true)
    })
    return () => { active = false }
  }, [name, title])

  useEffect(() => {
    if (!source) return
    setHeadings(Array.from(article.current.querySelectorAll("h2[id]"), (heading) => ({
      id: heading.id,
      label: heading.textContent,
    })))
    scrollToFragment()
  }, [source])

  return (
    <main className="about guide">
      <div className="guide-tools">
        <a href="./about.html#docs">All methodology guides</a>
        <a href={guideDownload(name)} download={`${name}.md`}>Download Markdown</a>
      </div>
      <div className="about-layout">
        {headings.length > 0 && (
          <nav className="about-contents" aria-labelledby="guide-contents-title">
            <h2 id="guide-contents-title">In this guide</h2>
            {headings.map(({ id, label }) =>
              <a key={id} href={`#${encodeURIComponent(id)}`}>{label}</a>
            )}
          </nav>
        )}
        <article ref={article} className="guide-article" aria-label={title}>
          {failed && <p role="alert">The guide could not load. Use the Markdown download above.</p>}
          {!failed && source == null && <p role="status">Loading guide…</p>}
          {source && <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}
            components={components}>{source}</Markdown>}
        </article>
      </div>
    </main>
  )
}
