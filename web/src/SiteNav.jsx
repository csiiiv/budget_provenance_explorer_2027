const pages = [
  ['fmr', './index.html', 'FMR', 'Farm-to-Market Roads'],
  ['nia', './nia.html', 'NIA', 'National Irrigation Administration'],
  ['dpwh', './dpwh.html', 'DPWH', 'Department of Public Works and Highways'],
  ['about', './about.html', 'About'],
]

export default function SiteNav({ current }) {
  return (
    <div className="site-bar">
      <nav className="site-nav" aria-label="Main">
        <span className="site-name">FY2027 Budget Explorers</span>
        <ul className="site-links">
          {pages.map(([key, href, label, title]) => (
            <li key={key}>
              <a href={href} title={title} aria-current={current === key ? 'page' : undefined}>
                {label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}
