"""Browser tests for coordinate counts, drilldowns and filtered CSV."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import json
from playwright.sync_api import sync_playwright, expect

DIST=Path(__file__).resolve().parents[1]/'dist'
PREFIX='/budget_provenance_explorer_2027/'
with TemporaryDirectory() as tmp:
    (Path(tmp)/PREFIX.strip('/')).symlink_to(DIST,target_is_directory=True)
    with ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=tmp)) as server:
        Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}'+PREFIX
        with sync_playwright() as p:
            chrome=Path('/usr/bin/google-chrome')
            browser=p.chromium.launch(executable_path=str(chrome) if chrome.exists() else None)
            page=browser.new_page(viewport={'width':1400,'height':900},accept_downloads=True)
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'nia-coordinates.html')
            expect(page.get_by_role('heading',level=1)).to_contain_text('NIA Coordinate Coverage Analysis')
            matrix=page.locator('.coordinate-matrix')
            expect(matrix).to_be_visible(timeout=30000)
            data=json.loads((DIST/'data/nia.json').read_text())
            expect(matrix.locator('tbody tr').last.locator('td').last).to_have_text(f"{len(data['chains']):,}")
            row=matrix.get_by_role('row').filter(has_text='No coordinate evidence detected')
            expected=int(row.get_by_role('button').first.inner_text().replace(',',''))
            row.get_by_role('button').first.click()
            records=page.locator('#coordinate-records')
            expect(records.get_by_role('combobox',name='Senate funding')).to_have_value('positive')
            expect(records.get_by_role('combobox',name='Coordinate evidence')).to_have_value('none')
            expect(records.get_by_role('status')).to_contain_text(f'{expected:,} records')
            with page.expect_download() as d:
                records.get_by_role('button',name='Export filtered CSV').click()
            assert d.value.suggested_filename=='nia-coordinate-coverage.csv'
            records.get_by_role('searchbox').fill('__impossible_search__')
            expect(records.get_by_role('status')).to_contain_text('0 records')
            assert not errors, errors
            browser.close()
        server.shutdown()
print('NIA coordinate coverage counts, drilldown and export passed')
