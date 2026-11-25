"""Verify the supporting-docs column on nia-titles.html (built bundle)."""
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


def main():
    dist = Path(__file__).resolve().parent / 'dist'
    data = json.loads((dist / 'data' / 'nia.json').read_text())

    from playwright.sync_api import expect, sync_playwright

    handler = partial(SimpleHTTPRequestHandler, directory=str(dist))
    with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server, sync_playwright() as playwright:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            chrome = Path('/usr/bin/google-chrome')
            browser = playwright.chromium.launch(executable_path=str(chrome) if chrome.exists() else None)
            page = browser.new_page(viewport={'width': 1600, 'height': 1000})
            page.set_default_timeout(8000)
            errors = []
            page.on('pageerror', lambda exc: errors.append(str(exc)))
            page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
            page.goto(f'http://127.0.0.1:{server.server_port}/nia-titles.html')

            heading = page.locator('#explorer h2')
            expect(heading).to_contain_text('Title comparison')

            # the new column header exists
            expect(page.get_by_role('columnheader', name='Supporting docs')).to_be_visible()

            # search for a known supported project (AUPAGAN, sen:r1456)
            page.get_by_role('searchbox').fill('sen:r1456')
            rows = page.locator('tbody tr')
            expect(rows).to_have_count(1)
            cell = rows.first.locator('td.pow-docs-cell')
            expect(cell.locator('strong')).to_have_text('2')
            expect(cell.get_by_text('REPAIRPIS-LARPIS(AUPAGAN)-300M')).to_be_visible()
            link = cell.get_by_role('link', name='PBC source folder')
            expect(link).to_have_attribute('href', data['chains'][next(i for i, r in enumerate(data['chains']) if any(w['id'] == 'sen:r1456' for w in r.get('workbook', [])))]['supporting_docs']['drive_url'])
            assert cell.locator('a[href^="file:"]').count() == 0

            # unsupported row shows an em dash (Kabulnan RIS, sen:r2463)
            page.get_by_role('searchbox').fill('sen:r2463')
            rows = page.locator('tbody tr')
            expect(rows).to_have_count(1)
            expect(rows.first.locator('td.pow-docs-cell .title-missing')).to_have_text('—')

            # the evidence drawer renders the supporting-docs callout
            page.get_by_role('searchbox').fill('sen:r1456')
            rows = page.locator('tbody tr')
            rows.first.click()
            drawer = page.locator('.detail.open')
            expect(drawer.get_by_text('Supporting documents · [POW FOR REVIEW]')).to_be_visible()
            expect(drawer.get_by_text('REPAIRPIS-LARPIS(AUPAGAN)-300M').first).to_be_visible()
            expect(drawer.get_by_role('link', name='PBC Google Drive folder')).to_be_visible()
            assert page.locator('a[href^="file:"]').count() == 0
            assert 'Local mirror:' not in drawer.inner_text()
            assert 'local root' not in drawer.inner_text()

            # KPI is present
            expect(page.get_by_text('chains with [POW FOR REVIEW] packages attributed')).to_be_visible()

            assert not errors, errors
            page.screenshot(path='/tmp/nia-supporting-docs.png', full_page=False)
            print('nia-titles supporting docs: OK')
        finally:
            try:
                browser.close()
            except NameError:
                pass
            server.shutdown()


if __name__ == '__main__':
    main()
