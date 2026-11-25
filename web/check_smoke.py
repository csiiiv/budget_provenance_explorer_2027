"""Verify the built FMR bundles and exercise the dashboard in Chromium."""
import argparse
from collections import Counter
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshot', type=Path)
    args = parser.parse_args()

    dist = Path(__file__).resolve().parent / 'dist'
    data = dist / 'data' / 'fmr'

    def read(name):
        return json.loads((data / f'{name}.json').read_text())

    manifest = read('manifest')
    projects = read('projects')
    localities = read('localities')
    assert read('regions')
    assert read('lineage')['mermaid']
    assert len(projects) == manifest['records']
    totals = manifest['totals']['actions']
    for stage, counts in totals.items():
        assert Counter(p['actions'][stage] for p in projects if p['actions'].get(stage)) == counts

    paired_insertions = {p['restated_by']['id'] for p in projects if p.get('restated_by')}
    paired_insertions.update(
        p['possible_senate_restatement']['id'] for p in projects
        if 'amount_m' in p.get('possible_senate_restatement', {})
    )
    paired_insertions.update(p['da_replacement']['id'] for p in projects if p.get('da_replacement'))
    visible_projects = [
        p for p in projects if p['id'] not in paired_insertions and not p.get('possible_senate_match')
    ]
    locality_counts = Counter(
        (p['province'], p['municipality']) for p in visible_projects if p['municipality']
    )
    assert locality_counts == {
        (row['province'], row['municipality']): row['chains'] for row in localities
    }

    from playwright.sync_api import expect, sync_playwright

    handler = partial(SimpleHTTPRequestHandler, directory=str(dist))
    with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server, sync_playwright() as playwright:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            chrome = Path('/usr/bin/google-chrome')
            browser = playwright.chromium.launch(executable_path=str(chrome) if chrome.exists() else None)
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.set_default_timeout(6000)
            errors = []
            page.on('pageerror', lambda exc: errors.append(str(exc)))
            page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
            page.goto(f'http://127.0.0.1:{server.server_port}/')

            explorer = page.locator('#explorer')
            expect(explorer.get_by_role('searchbox')).to_be_visible()
            heading = explorer.get_by_role('heading')
            expect(heading).to_contain_text(f"{len(visible_projects):,} chains")
            expect(page.locator('#flow canvas')).to_be_visible()
            assert explorer.evaluate(
                "(el) => Boolean(el.compareDocumentPosition(document.getElementById('flow')) & Node.DOCUMENT_POSITION_FOLLOWING)"
            )
            expect(page.get_by_text('Realigned projects', exact=True).locator('..')).to_contain_text(
                str(totals['house_senate']['realigned'])
            )

            legend = explorer.get_by_text('Action color legend', exact=True)
            legend.click()
            expect(explorer.locator('details[open]')).to_contain_text('list revision')
            legend.click()

            for group_name in ('NEP → House', 'House → DA', 'House → Senate', 'Senate status'):
                group = explorer.get_by_role('group', name=group_name, exact=True)
                chip = group.locator('button[aria-pressed="false"]').first
                expect(chip).to_have_css('background-color', 'rgb(28, 35, 46)')
                chip.click()
                selected = group.locator('button[aria-pressed="true"]').first
                expect(selected).to_have_css('background-color', 'rgb(38, 60, 88)')
                expect(selected).to_have_css('color', 'rgb(224, 237, 255)')
                selected.click()

            insertion_count = totals['nep_house']['house_insertion']
            insertion = explorer.get_by_text(f'house insertion ({insertion_count})', exact=True)
            insertion.click()
            expect(heading).to_contain_text(f'{insertion_count:,} chains')
            expect(explorer.get_by_role('button', name=f'Any review status ({insertion_count})')).to_be_visible()

            house_insertion = explorer.locator('tbody tr').first.locator('.stage-status')
            expect(house_insertion.locator('.stage-status-label')).to_have_text(
                ['NEP', 'HGAB', 'DA Nov 5', 'DA Nov 12', 'Senate']
            )
            expect(house_insertion.nth(0).locator('.act-pill')).to_have_text('N/A')
            expect(house_insertion.nth(1).locator('.act-pill')).to_have_text('house insertion')

            grouping = page.locator('#localities')
            grouping.get_by_label('Grouping stage').select_option('house_da')
            row = grouping.locator('tbody tr').first
            municipality = row.locator('td').nth(0).inner_text()
            province = row.locator('td').nth(1).inner_text()
            count = locality_counts[province, municipality]
            row.get_by_role('button').click()
            expect(heading).to_contain_text(f'{count:,} chains · {municipality}')
            # The original drop and revised DA listing remain on one House chain.
            explorer.get_by_role('combobox').nth(1).select_option('')
            search = explorer.get_by_role('searchbox')
            rows = explorer.locator('tbody tr')
            search.fill('cabungaan')
            expect(rows).to_have_count(2)
            expect(rows.nth(0)).to_contain_text('Cabungaan A FMR')
            expect(rows.nth(1)).to_contain_text('Cabungaan B FMR')
            expect(rows.first.locator('.act-pill:not(.stage-note)')).to_have_text(
                ['proposed⚑', 'carried⚑', 'list revision✓', 'list revision✓', 'Realigned']
            )
            expect(rows.first.locator('.stage-note')).to_have_text(
                ['Title corrected', 'Title corrected', 'Title revised']
            )
            search.fill('cabungaan north')
            expect(rows).to_have_count(1)
            expect(rows.first).to_contain_text('Cabungaan A FMR')

            search.fill('cabungaan')
            chain_type = explorer.get_by_role('combobox').nth(2)
            chain_type.select_option('senate_insertion')
            expect(rows).to_have_count(0)
            expect(explorer.get_by_role('status')).to_have_text('2 results outside current filters')
            expect(explorer.locator('.search-filter-feedback + .tablewrap')).to_have_count(1)
            chain_type.select_option('')
            inserted = explorer.get_by_role('group', name='House → Senate', exact=True).get_by_role(
                'button', name='inserted (0)', exact=True
            )
            inserted.click()
            expect(rows).to_have_count(0)
            search.fill('sitio rango')
            expect(rows).to_have_count(0)
            expect(explorer.get_by_role('status')).to_have_text('1 result outside current filters')
            inserted.click()
            expect(rows).to_have_count(1)
            expect(explorer.get_by_role('status')).to_be_empty()
            expect(rows.first).to_contain_text('Realigned')
            search.fill('senate_a1:p7:r59')
            expect(rows).to_have_count(1)
            expect(rows.first).to_contain_text('Cabungaan North FMR')

            search.fill('R1-L-0006')
            expect(heading).to_contain_text('1 chains')
            explorer.locator('tbody tr').click()
            drawer = page.locator('.detail')
            drawer.get_by_role('button', name='DA Nov 12', exact=False).click()
            expect(drawer.get_by_role('button', name='DA Nov 12', exact=False)).to_have_attribute(
                'aria-pressed', 'true'
            )
            expect(drawer.get_by_role('heading', name='NEP — National Expenditure Program')).to_have_count(0)
            expect(drawer).to_contain_text('FIXED — REPLACED BY CORRECTED ENTRY (TITLE)')
            drawer_rail = drawer.locator('.drawer-rail')
            expect(drawer_rail.get_by_role('img', name='Flagged')).to_have_count(2)
            expect(drawer_rail.get_by_role('img', name='Fixed')).to_have_count(2)
            expect(drawer_rail.get_by_role('img', name='Fixed').first).to_be_visible()
            expect(drawer).to_contain_text('Correction carried forward from Nov 5')
            drawer.get_by_role('button', name='Compare drafts').click()
            expect(drawer.locator('.draft-comparison').get_by_role('table')).to_be_visible()
            drawer.get_by_text('Source evidence', exact=True).click()
            expect(drawer.get_by_text('R1-0046', exact=False).first).to_be_visible()
            expect(drawer).to_contain_text('R1-L-0006')
            expect(drawer).to_contain_text('Cabungaan North')
            drawer.get_by_role('button', name='Senate', exact=False).click()
            drawer.get_by_role('button', name='Open paired insertion', exact=False).click()
            expect(drawer).to_contain_text('senate_a1:p7:r59')

            drawer.get_by_role('button', name='Close project details').click()
            search.fill('sitio rango')
            expect(rows).to_have_count(1)
            expect(rows.first).to_contain_text('coordinate correction')
            rows.first.get_by_role('button', name='DA Nov 5', exact=False).click()
            expect(drawer.get_by_role('button', name='DA Nov 5', exact=False)).to_have_attribute(
                'aria-pressed', 'true'
            )
            expect(drawer.get_by_text('DA coordinate correction', exact=True)).to_be_visible()
            drawer.get_by_text('Source evidence', exact=True).click()
            expect(drawer).to_contain_text('R1-NEW-0001')
            expect(drawer).to_contain_text('18.279797')
            expect(drawer).to_contain_text('18.287494')

            drawer.get_by_role('button', name='Close project details').click()
            search.fill('bobonan')
            expect(rows).to_have_count(1)
            expect(rows.first).to_contain_text('DA-documented replacement')
            expect(rows.first).to_contain_text('Possible Senate restatement')
            expect(rows.first.get_by_role('cell').nth(4)).to_have_text('15M')
            expect(rows.first.get_by_role('cell').nth(5)).to_have_text('15M')
            rows.first.get_by_role('button', name='DA Nov 12', exact=False).click()
            drawer.get_by_text('Source evidence', exact=True).click()
            expect(drawer).to_contain_text('R1-NEW-0006')
            drawer.get_by_role('button', name='Senate', exact=False).click()
            expect(drawer).to_contain_text('cut row amount: ₱0')
            drawer.get_by_role('button', name='Open corrected entry').click()
            expect(drawer).to_contain_text('senate_a1:p16:r144')
            drawer.get_by_role('button', name='Open original entry').click()
            expect(drawer).to_contain_text('ib:p668:r2')
            drawer.get_by_role('button', name='Close project details').click()

            search.fill('ib:p668:r2')
            rows.first.get_by_role('button', name='NEP', exact=False).click()
            findings = drawer.locator('.source-findings')
            expect(findings).to_contain_text('START point is not in the stated town')
            expect(findings.get_by_role('listitem')).to_have_count(1)
            drawer.get_by_role('button', name='HGAB', exact=False).click()
            expect(findings).to_contain_text('Pozorrubio, Pangasinan')
            drawer.get_by_role('button', name='Close project details').click()

            search.fill('ib:p673:r3')
            pending = rows.first.locator('.stage-status').nth(3).get_by_role('img', name='Pending')
            expect(pending).to_be_visible()
            for query, label in (
                ('R3-0085', 'Reinstated'),
                ('R3-0108', 'Reinstated'),
                ('R3-NEW-0023', 'Realigned'),
            ):
                search.fill(query)
                expect(rows).to_have_count(1)
                expect(rows.first).to_contain_text(label)

            search.fill('nagpalangan')
            expect(rows).to_have_count(1)
            expect(rows.first).to_contain_text('Nagpalanga FMR')
            expect(rows.first).to_contain_text('Possible Senate restatement')
            expect(rows.first.get_by_role('cell').nth(2)).to_have_text('5M')
            rows.first.get_by_role('button', name='Senate', exact=False).click()
            expect(drawer).to_contain_text('Both DA drafts list the title correction')
            drawer.get_by_role('button', name='Close project details').click()

            search.fill('R1-NEW-0029')
            expect(rows).to_have_count(1)
            expect(rows.first).to_contain_text('Nancalabasaan')
            expect(rows.first).to_contain_text('Realigned')
            expect(rows.first.get_by_role('cell').nth(4)).to_have_text('15M')
            rows.first.get_by_role('button', name='Senate', exact=False).click()
            expect(drawer).to_contain_text('agree on title, amount, and both endpoints')
            expect(drawer).to_contain_text('senate_a1:p14:r132')
            drawer.get_by_role('button', name='Close project details').click()

            search.fill('Brgy. 27 FMR, Laoag City')
            expect(rows).to_have_count(1)
            expect(rows.first).to_contain_text('DA-documented replacement')
            expect(rows.first.get_by_role('cell').nth(4)).to_have_text('10M')
            search.fill('alimang')
            expect(rows.filter(has_text='Possible Senate restatement')).to_have_count(1)
            expect(rows.first.get_by_role('cell').nth(5)).to_have_text('15M')
            rows.first.get_by_role('button', name='Senate', exact=False).click()
            expect(drawer).to_contain_text('cut row amount: ₱0')
            expect(drawer).to_contain_text('possible paired insertion amount: ₱15M')
            drawer.get_by_role('button', name='Open related Senate entry').click()
            expect(drawer).to_contain_text('senate_a1:p18:r163')
            drawer.get_by_role('button', name='Close project details').click()

            search.fill('Comon to Brgy. Amolongin')
            expect(rows).to_have_count(1)
            expect(rows.first.get_by_role('cell').nth(4)).to_have_text('10M')
            rows.first.get_by_role('button', name='Senate', exact=False).click()
            expect(drawer).to_contain_text('agree on title, amount, and both endpoints')
            expect(drawer).to_contain_text('R4A-NEW-0028')
            drawer.get_by_role('button', name='Close project details').click()

            search.fill('kalubkob')
            expect(rows).to_have_count(2)
            corrected = rows.filter(has_text='Construction of Brgy. Kalubkob FMR')
            expect(corrected).to_contain_text('Reinstated')
            expect(corrected).to_contain_text('coordinate correction')
            expect(corrected.get_by_role('cell').nth(4)).to_have_text('15M')
            supok = rows.filter(has_text='Sitio Supok')
            expect(supok.get_by_role('cell').nth(4)).to_have_text('20M')
            expect(supok).to_contain_text('Senate inserted')
            search.fill('senate_a1:p65:r601')
            expect(rows).to_have_count(1)
            expect(rows.first).to_contain_text('Reinstated')

            search.fill('corocor')
            expect(rows).to_have_count(1)
            expect(explorer.locator('thead th').get_by_text('DA', exact=True)).to_be_visible()
            comparisons = explorer.get_by_role('group', name='DA to Senate comparison')
            comparisons.get_by_role('button', name='Exact DA match', exact=False).click()
            expect(rows).to_have_count(0)
            comparisons.get_by_role('button', name='Possible DA → Senate match', exact=False).click()
            expect(rows).to_have_count(1)
            comparisons.get_by_role('button', name='Any comparison').click()
            senate_corocor = rows.first
            expect(senate_corocor).to_contain_text('Possible DA → Senate match')
            expect(senate_corocor.get_by_role('cell').nth(4)).to_have_text('28M')
            expect(senate_corocor.get_by_role('cell').nth(5)).to_have_text('28M')
            senate_corocor.get_by_role('button', name='Senate', exact=False).click()
            expect(drawer).to_contain_text('same amount and both endpoints; title differs')
            drawer.get_by_role('button', name='Open DA Nov 12 entry').click()
            expect(drawer).to_contain_text('Brgy. Corocor to Brgy. Cabaruan')
            drawer.get_by_text('Source evidence', exact=True).click()
            expect(drawer.get_by_role('row', name='Excel row 163')).to_be_visible()
            expect(drawer).to_contain_text('₱28M')
            drawer.get_by_role('button', name='Close project details').click()

            search.fill('Ilocos Sur Provincial Trading Center')
            expect(rows).to_have_count(1)
            expect(rows.first).to_contain_text('Reinstated')
            expect(rows.first).to_contain_text('modified')
            search.fill('senate_a1:p4:r28')
            expect(rows).to_have_count(1)
            rows.first.get_by_role('button', name='Senate', exact=False).click()
            expect(drawer.get_by_role('row', name='annex action inserted')).to_be_visible()
            expect(drawer).to_contain_text('agree on title, amount, and both endpoints')
            drawer.get_by_role('button', name='Close project details').click()

            search.fill('CAR-NEW-0007')
            expect(rows).to_have_count(1)
            expect(rows.first).to_contain_text('DA insertion')
            comparisons = explorer.get_by_role('group', name='DA to Senate comparison')
            expect(comparisons.get_by_role('button', name='Any comparison')).to_have_css(
                'background-color', 'rgb(38, 60, 88)'
            )
            expect(comparisons.get_by_role('button', name='Exact DA match', exact=False)).to_have_css(
                'background-color', 'rgb(28, 35, 46)'
            )
            comparisons.get_by_role('button', name='No DA match', exact=False).click()
            expect(rows).to_have_count(0)
            expect(explorer.get_by_role('status')).to_have_text('1 result outside current filters')
            comparisons.get_by_role('button', name='Exact DA match', exact=False).click()
            expect(rows).to_have_count(1)
            comparisons.get_by_role('button', name='Any comparison').click()
            rows.first.get_by_role('button', name='Senate', exact=False).click()
            expect(drawer).to_contain_text('DA → Senate comparison')
            expect(drawer).to_contain_text('agree on title, amount, and both endpoints')
            expect(drawer.get_by_text('DA-documented replacement', exact=True)).to_have_count(0)
            drawer.get_by_role('button', name='Close project details').click()
            search.fill('ib:p673:r3')

            page.set_viewport_size({'width': 390, 'height': 844})
            rows.first.locator('td').first.click()
            rail = drawer.locator('.drawer-rail')
            expect(rail.get_by_role('button')).to_have_count(5)
            rail.get_by_role('button', name='DA Nov 12', exact=False).click()
            expect(drawer.get_by_role('heading', name='DA working draft · November 12')).to_be_visible()
            assert rail.evaluate('(el) => el.scrollWidth <= el.clientWidth')

            drawer.get_by_role('button', name='Close project details').click()
            page.set_viewport_size({'width': 1440, 'height': 1000})
            reviews = explorer.get_by_role('group', name='Review status')
            expect(reviews.get_by_role('button', name='Any review status', exact=False)).to_have_css(
                'background-color', 'rgb(38, 60, 88)'
            )
            reviews.get_by_role('button', name='Pending review (', exact=False).click()
            expect(rows).to_have_count(1)
            reviews.get_by_role('button', name='Documented fix (', exact=False).click()
            expect(rows).to_have_count(0)
            expect(explorer.get_by_role('status')).to_have_text('1 result outside current filters')
            search.fill('sitio rango')
            expect(rows).to_have_count(1)
            reviews.get_by_role('button', name='Flagged in review (', exact=False).click()
            expect(rows).to_have_count(0)
            search.fill('cabungaan')
            expect(rows).to_have_count(2)

            findings_filter = explorer.get_by_role('group', name='Finding type')
            fixes_filter = explorer.get_by_role('group', name='Fix type')
            expect(findings_filter).to_be_visible()
            expect(fixes_filter).to_be_visible()
            findings_filter.get_by_role('button', name='PSGC verification', exact=False).click()
            expect(rows).to_have_count(2)
            fixes_filter.get_by_role('button', name='Title correction (', exact=False).click()
            expect(rows).to_have_count(2)
            fixes_filter.get_by_role('button', name='Coordinate correction', exact=False).click()
            expect(rows).to_have_count(0)
            findings_filter.get_by_role('button', name='Any finding').click()
            reviews.get_by_role('button', name='Any review status', exact=False).click()
            search.fill('sitio rango')
            expect(rows).to_have_count(1)

            assert not errors, errors

            if args.screenshot:
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.screenshot(path=args.screenshot, full_page=True)
            browser.close()
        finally:
            server.shutdown()
    print(f"Verified {len(projects):,} chains and {len(localities):,} localities in Chromium")


if __name__ == '__main__':
    main()
