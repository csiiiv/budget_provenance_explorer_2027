export const downloads = import.meta.glob("../../docs/*.md", {
  eager: true, import: "default", query: "?url&no-inline",
})

export const guides = [
  ["Concepts and worked examples", [
    ["provenance_chaining_considerations", "Chaining budget records"],
    ["budget_provenance_explorer_design_guide", "Designing a provenance explorer"],
  ]],
  ["Program evidence", [
    ["fmr_budget_chain_web", "FMR budget chain and web app"],
    ["fmr_budget_chain_edge_cases", "FMR matching edge cases"],
    ["nia_provenance_explorer", "NIA explorer methodology"],
    ["nia_review_data_sources", "NIA November review sources"],
    ["dpwh_provenance_explorer", "DPWH explorer methodology"],
  ]],
  ["Implementation", [
    ["provenance_explorer_build_guide", "Building an explorer"],
    ["provenance_explorer_ui_ux", "Explorer interface guidelines"],
  ]],
]

export function guideUrl(name) {
  return `./about.html?guide=${encodeURIComponent(name)}`
}

export function guideDownload(name) {
  return downloads[`../../docs/${name}.md`]
}

export function scrollToFragment() {
  const fragment = window.location.hash.slice(1)
  if (!fragment) return
  let id
  try {
    id = decodeURIComponent(fragment)
  } catch {
    return
  }
  document.getElementById(id)?.scrollIntoView()
}
