"""Validate shipped browser bundles, not upstream extraction inputs.

Run after npm --prefix web run build. A missing required bundle is a failure.
No snapshot-specific record counts are used as application requirements.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

DATA = Path(__file__).resolve().parents[1] / 'dist' / 'data'


def load(path):
    assert path.is_file(), f'Required deployment artifact missing: {path}'
    return json.loads(path.read_text(encoding='utf-8'))


def unique(rows, label):
    ids = [row['id'] for row in rows]
    assert all(isinstance(i, str) and i for i in ids), f'{label}: empty ID'
    assert len(ids) == len(set(ids)), f'{label}: duplicate IDs'
    return set(ids)


def reconcile(rows, control, field, label):
    unique(rows, label)
    assert len(rows) == control['rows'], f'{label}: row count differs from control'
    assert sum(row[field] or 0 for row in rows) == control['amount_php'], (
        f'{label}: amount differs from control')


def actions(rows, controls):
    for stage, expected in controls.items():
        actual = Counter(r['actions'][stage] for r in rows if r['actions'].get(stage))
        assert actual == expected, f'{stage}: action counts do not reconcile'


def downloads(program):
    directory = DATA / 'export' / program
    sums = directory / 'SHA256SUMS.txt'
    assert sums.is_file(), f'Missing checksum manifest: {sums}'
    listed = set()
    for line in sums.read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        assert re.fullmatch(r'[0-9a-f]{64}', digest), line
        assert Path(name).name == name and name not in listed, line
        listed.add(name)
        path = directory / name
        assert path.is_file(), f'Missing download: {path}'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'Checksum mismatch: {path}'
    required = {'chains-simple.csv', 'chains-full.csv', 'findings.csv', 'rollups.csv', 'full.json'}
    if program == 'nia':
        required.add('supporting-docs.csv')
    assert required <= listed, f'Unlisted required downloads: {required - listed}'


def fmr():
    directory = DATA / 'fmr'
    manifest = load(directory / 'manifest.json')
    rows = load(directory / 'projects.json')
    ids = unique(rows, 'FMR chains')
    assert rows and len(rows) == manifest['records']
    totals = manifest['totals']
    actions(rows, totals['actions'])
    assert load(directory / 'regions.json')
    assert load(directory / 'lineage.json')['mermaid']
    by_id = {row['id']: row for row in rows}
    hidden = set()
    for row in rows:
        for key in ('restated_by', 'da_replacement', 'possible_senate_restatement', 'possible_senate_match'):
            edge = row.get(key)
            if not edge:
                continue
            assert edge['id'] in ids, f"{row['id']}: dangling {key} -> {edge['id']}"
            assert edge['id'] != row['id'], f"{row['id']}: self-reference in {key}"
            if key == 'restated_by':
                reverse = by_id[edge['id']]['replaces']
                assert reverse['house_id'] == row['id'], f"{row['id']}: missing reverse realignment link"
                assert by_id[edge['id']]['senate']['sv_m'] == edge['sv_m'], f"{row['id']}: realignment amount differs"
            if key in ('restated_by', 'da_replacement') or (key == 'possible_senate_restatement' and 'amount_m' in edge):
                hidden.add(edge['id'])
            if key == 'possible_senate_match':
                hidden.add(row['id'])
    locality_counts = Counter((r['province'], r['municipality']) for r in rows
                             if r['id'] not in hidden and r['municipality'])
    assert locality_counts == {(r['province'], r['municipality']): r['chains']
                              for r in load(directory / 'localities.json')}
    downloads('fmr')
    print(f'FMR: {len(rows)} chains; action, link, locality and download checks passed')


def nia():
    bundle = load(DATA / 'nia.json')
    rows = bundle['chains']
    assert rows
    unique(rows, 'NIA chains')
    for side, field in [('nep', 'amount_php'), ('house', 'amount_php'), ('senate', 'sv_php')]:
        reconcile([r[side] for r in rows if r.get(side)], bundle['totals'][side], field, side)
    for vintage, controls in bundle['agency_totals'].items():
        leaves = [r['agency'][vintage] for r in rows if vintage in r.get('agency', {})]
        unique(leaves, vintage)
        assert len(leaves) == controls['leaves'], f'{vintage}: agency leaf count differs'
    supported = [r for r in rows if r.get('supporting_docs')]
    for row in supported:
        docs = row['supporting_docs']
        packages = docs['packages']
        assert packages, f"{row['id']}: attribution without package"
        assert docs['drive_url'].startswith('https://'), f"{row['id']}: missing upstream URL"
        assert all(p['name'] and p['path'] for p in packages), f"{row['id']}: incomplete package reference"
        for field in ('doc_count', 'pdf_count', 'image_count', 'pow_pdf_count', 'photo_count'):
            assert docs[field] == sum(p[field] for p in packages), f"{row['id']}: {field} differs from package totals"
    downloads('nia')
    print(f'NIA: {len(rows)} chains; {len(supported)} supporting-document attributions')


def dpwh():
    bundle = load(DATA / 'dpwh.json')
    rows = bundle['chains']
    assert rows
    unique(rows, 'DPWH chains')
    totals = bundle['totals']
    actions(rows, totals['actions'])
    reconcile([r['nep'] for r in rows if r.get('nep')], totals['nep'], 'amount_php', 'NEP')
    house = [r['house'] for r in rows if r.get('house')]
    reconcile([r for r in house if r.get('allocation_kind') != 'control'], totals['house'], 'amount_php', 'House leaves')
    reconcile([r for r in house if r.get('allocation_kind') == 'control'], totals['controls'], 'amount_php', 'House controls')
    senate = [r['senate'] for r in rows if r.get('senate')]
    reconcile(senate, totals['senate'], 'sv_php', 'Senate A-4')
    assert sum(r['gab_php'] or 0 for r in senate) == totals['senate']['gab_php']
    for field in ('gab_php', 'sv_php'):
        assert sum(r[field] or 0 for r in senate if r['match'] != 'unmatched') == totals['senate']['matched_' + field]
    print(f'DPWH: {len(rows)} chains; leaves, controls and Annex A-4 reconcile')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('program', choices=('fmr', 'nia', 'dpwh'))
    globals()[parser.parse_args().program]()
