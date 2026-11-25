"""Verify the built DPWH bundle and exercise the explorer in Chromium."""

from collections import Counter
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread


def main():
    dist = Path(__file__).resolve().parent / 'dist'
    data = dist / 'data' / 'dpwh.json'

    bundle = json.loads(data.read_text())
    chains = bundle['chains']
    totals = bundle['totals']
    assert len(chains) == 15977 + totals['controls']['rows'] + \
        totals['counts']['nep_only'] + totals['counts']['senate_only']
    for stage, counts in totals['actions'].items():
        assert Counter(c['actions'][stage] for c in chains if c['actions'].get(stage)) == counts
    # Every A-4 row is carried exactly once.
    senate = [c['senate'] for c in chains if c.get('senate')]
    assert len(senate) == totals['senate']['rows'] == 8713
    assert sum(r['gab_php'] or 0 for r in senate if r['match'] != 'unmatched') \
        == totals['senate']['matched_gab_php']

    from playwright.sync_api import expect, sync_playwright

    handler = partial(SimpleHTTPRequestHandler, directory=str(dist))
    with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server, sync_playwright() as playwright:
        Thread(target=server.serve_forever, daemon=True).start()
        try:
            chrome = Path('/usr/bin/google-chrome')
            browser = playwright.chromium.launch(executable_path=str(chrome) if chrome.exists() else None)
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.set_default_timeout(30000)
            errors = []
            page.on('pageerror', lambda exc: errors.append(str(exc)))
            page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
            page.goto(f'http://127.0.0.1:{server.server_port}/dpwh.html')

            explorer = page.locator('#explorer')
            explorer.scroll_into_view_if_needed()
            search = explorer.get_by_role('searchbox')
            expect(search).to_be_visible()
            heading = explorer.get_by_role('heading')
            expect(heading).to_contain_text(f'{len(chains):,} chains')
            expect(page.locator('#flow canvas')).to_be_visible()

            # A full chain: NEP → House → review → Senate cut.
            search.fill('hb:ic:c0211')
            rows = page.locator('tbody tr')
            expect(rows).to_have_count(1)
            rows.first.locator('.stage-status').nth(1).click()
            drawer = page.locator('aside.detail')
            expect(drawer.get_by_text('House — HB 10858 Vol I-C, third reading')
                   ).to_be_visible(timeout=15000)
            drawer.locator('.stage-status').nth(3).click()
            expect(drawer.get_by_text('Cut to zero · match:')).to_be_visible(timeout=15000)
            drawer.locator('.stage-status').nth(2).click()
            expect(drawer.get_by_text('HGAB review set')).to_be_visible(timeout=15000)
            expect(drawer.get_by_text('HB10858-3-')).to_be_visible()
            drawer.get_by_role('button', name='Close project details').click()
            expect(page.locator('aside.detail')).to_have_count(0)

            # Filters count visible chains with other filters applied.
            search.fill('')
            senate_group = page.get_by_role('group', name='Senate status')
            chip = senate_group.get_by_role('button', name='Cut to zero (3,480)')
            chip.click()
            expect(heading).to_contain_text('3,480 chains')
            chip.click()

            # Unmatched and NEP-only records stay searchable.
            search.fill('senate_a4:p114:r213')
            expect(rows).to_have_count(1)
            search.fill('stage:16270')
            expect(rows).to_have_count(1)

            assert not errors, errors
            browser.close()
        finally:
            server.shutdown()
    print(f'Verified {len(chains):,} DPWH chains in Chromium')


if __name__ == '__main__':
    main()
