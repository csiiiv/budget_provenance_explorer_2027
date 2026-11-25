"""Check the NIA hub and its destinations under the Pages subpath."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from playwright.sync_api import sync_playwright, expect

DIST = Path(__file__).resolve().parents[1] / 'dist'
PREFIX = '/budget_provenance_explorer_2027/'
TOOLS = {
    'nia-provenance.html': 'NIA Provenance Explorer',
    'nia-titles.html': 'NIA Title Comparison',
    'nia-documents.html': 'NIA Document Coverage Analysis',
    'nia_map.html': 'NIA Project Map',
}

with TemporaryDirectory() as tmp:
    (Path(tmp) / PREFIX.strip('/')).symlink_to(DIST, target_is_directory=True)
    with ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=tmp)) as server:
        Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}' + PREFIX
        with sync_playwright() as p:
            chrome = Path('/usr/bin/google-chrome')
            browser = p.chromium.launch(executable_path=str(chrome) if chrome.exists() else None)
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            for path, heading in TOOLS.items():
                page.goto(base + 'nia.html')
                expect(page.get_by_role('heading', level=1)).to_have_text('NIA Budget Explorer')
                card = page.locator(f'.nia-hub-card[href="./{path}"]')
                expect(card).to_be_visible()
                card.click()
                expect(page).to_have_url(base + path)
                expect(page.get_by_role('heading', level=1)).to_contain_text(heading, timeout=30000)
                nav = page.get_by_role('navigation', name='NIA tools')
                expect(nav.get_by_role('link', name='NIA overview')).to_be_visible()
                nav.get_by_role('link', name='NIA overview').click()
                expect(page.get_by_role('heading', level=1)).to_have_text('NIA Budget Explorer')
            page.set_viewport_size({'width': 390, 'height': 844})
            expect(page.locator('.nia-hub-card')).to_have_count(4)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile page overflows'
            page.goto(base + 'nia.html?q=sen%3Ar1456')
            expect(page).to_have_url(base + 'nia-provenance.html?q=sen%3Ar1456')
            explorer = page.locator('#explorer')
            explorer.scroll_into_view_if_needed()
            expect(explorer.get_by_role('searchbox')).to_have_value('sen:r1456', timeout=30000)
            assert not errors, errors
            browser.close()
        server.shutdown()
print('NIA hub, four tool routes, return navigation, mobile layout and legacy search link passed')
