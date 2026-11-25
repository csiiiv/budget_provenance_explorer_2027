"""Public-site checks against the built app at its GitHub Pages subpath.

Each route runs in isolation. External basemap tiles are stubbed so an external
service outage cannot hide a local regression. No local source files are used.
"""
import argparse
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
from threading import Thread
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

DIST = Path(__file__).resolve().parents[1] / 'dist'
PREFIX = '/budget_provenance_explorer_2027/'
PAGES = {
    'fmr': ('index.html', 'Farm-to-Market Roads', 'fmr/projects.json'),
    'nia': ('nia.html', 'NIA Provenance Explorer', 'nia.json'),
    'nia-titles': ('nia-titles.html', 'NIA Title Comparison', 'nia.json'),
    'nia-map': ('nia_map.html', 'NIA Project Map', 'nia.json'),
    'dpwh': ('dpwh.html', 'DPWH Provenance Explorer', 'dpwh.json'),
    'about': ('about.html', 'How the budget provenance explorers work', None),
    'public-docs': ('nia-titles.html', 'NIA Title Comparison', 'nia.json'),
}
TILE = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR1sAAAAASUVORK5CYII=')


def check_explorer(page):
    explorer = page.locator('#explorer')
    explorer.scroll_into_view_if_needed()
    search = explorer.get_by_role('searchbox')
    expect(search).to_be_visible(timeout=30000)
    rows = explorer.locator('tbody tr')
    expect(rows.first).to_be_visible(timeout=30000)
    search.fill('__no_budget_project_matches_this_test__')
    expect(rows).to_have_count(0)
    search.fill('')
    expect(rows.first).to_be_visible(timeout=30000)
    rows.first.click()
    drawer = page.locator('.detail')
    expect(drawer).to_be_visible()
    drawer.get_by_role('button', name='Close project details').click()
    expect(drawer).to_have_count(0)


def check_public_docs(page, data):
    explorer = page.locator('#explorer')
    explorer.scroll_into_view_if_needed()
    search = explorer.get_by_role('searchbox')
    expect(search).to_be_visible(timeout=30000)
    # Use a retained, documented regression example, not a global count.
    example = next(r for r in data['chains'] if r.get('supporting_docs') and
                   any(w['id'] == 'sen:r1456' for w in r.get('workbook', [])))
    search.fill('sen:r1456')
    rows = explorer.locator('tbody tr')
    expect(rows).to_have_count(1)
    cell = rows.first.locator('td.pow-docs-cell')
    expect(cell.locator('strong')).to_have_text(f"{example['supporting_docs']['doc_count']:,}")
    rows.first.click()
    drawer = page.locator('.detail')
    expect(drawer.get_by_text('Supporting documents · [POW FOR REVIEW]')).to_be_visible()
    upstream = drawer.get_by_role('link', name='PBC Google Drive folder')
    expect(upstream).to_have_attribute('href', example['supporting_docs']['drive_url'])
    local_links = page.locator('a[href^="file:"]')
    assert local_links.count() == 0, (
        'Public HTTP page exposes local filesystem links. Preserve package attribution '
        'as text and provide a public upstream link rather than file://.')
    # We validate link scheme/attribution, not external Drive access permissions.


def check(case, base, browser):
    file, title, bundle = PAGES[case]
    if bundle:
        path = DIST / 'data' / bundle
        assert path.is_file(), f'{case}: required data/{bundle} absent from deployment artifact'
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    page.set_default_timeout(15000)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('response', lambda response: errors.append(f'HTTP {response.status}: {response.url}')
            if response.url.startswith(base) and response.status >= 400 else None)
    page.on('request', lambda request: errors.append(f'Escaped Pages subpath: {request.url}')
            if request.url.startswith(base) and not urlsplit(request.url).path.startswith(PREFIX) else None)
    page.on('requestfailed', lambda request: errors.append(f'Failed local request: {request.url}')
            if request.url.startswith(base) and request.failure != 'net::ERR_ABORTED' else None)
    if case == 'nia-map':
        page.route('https://services.arcgisonline.com/**', lambda route:
                   route.fulfill(status=200, content_type='image/png', body=TILE,
                                 headers={'Access-Control-Allow-Origin': '*'}))
    try:
        response = page.goto(base + PREFIX + file, wait_until='domcontentloaded')
        assert response and response.ok, f'{file}: HTTP load failed'
        expect(page.get_by_role('heading', level=1)).to_contain_text(title, timeout=30000)
        expect(page.get_by_role('alert')).to_have_count(0)
        if case == 'nia-map':
            expect(page.get_by_role('group', name='Basemap')).to_be_visible(timeout=30000)
            expect(page.locator('.nia-map-canvas canvas')).to_be_visible(timeout=30000)
            expect(page.locator('header')).to_contain_text('workbook points')
        elif case == 'about':
            expect(page.get_by_role('heading', name='Methodology guides')).to_be_visible()
            downloads = page.locator('a[download]')
            assert downloads.count() > 0, 'No methodology downloads'
            for link in downloads.all():
                href = link.evaluate('(a) => a.href')
                assert href.startswith(base + PREFIX), href
                assert page.request.get(href).ok, f'Missing guide asset: {href}'
        elif case == 'public-docs':
            check_public_docs(page, json.loads((DIST / 'data' / bundle).read_text()))
        else:
            check_explorer(page)
        # Validate internal navigation targets, without following external evidence links.
        for link in page.locator('a[href]').all():
            href = link.evaluate('(a) => a.href')
            parsed = urlsplit(href)
            if href.startswith(base) and parsed.path.endswith('.html'):
                assert parsed.path.startswith(PREFIX), href
                assert (DIST / parsed.path.removeprefix(PREFIX)).is_file(), f'Missing page: {href}'
        assert not errors, '\n'.join(errors)
        print(f'{case}: public subpath and application checks passed')
    finally:
        page.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('page', choices=PAGES)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / PREFIX.strip('/')).symlink_to(DIST, target_is_directory=True)
        handler = partial(SimpleHTTPRequestHandler, directory=tmp)
        with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server, sync_playwright() as playwright:
            Thread(target=server.serve_forever, daemon=True).start()
            chrome = Path('/usr/bin/google-chrome')
            try:
                browser = playwright.chromium.launch(executable_path=str(chrome) if chrome.exists() else None,
                    args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
                try:
                    check(args.page, f'http://127.0.0.1:{server.server_port}', browser)
                finally:
                    browser.close()
            finally:
                server.shutdown()


if __name__ == '__main__':
    main()
