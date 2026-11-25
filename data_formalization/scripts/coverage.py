#!/usr/bin/env python3
"""Domain connection coverage + bridge probes (§14 of docs/DATA_MODEL.md).

Reads the ledgers and source files — writes nothing except a report to
stdout. Use after any backfill/import to recompute §14's evidence:

  1. per-domain ledger coverage: subjects per snapshot, match edges between
     stages, senate rows and their house_ref dialects
  2. NIA agency-recon probe: leaf counts (identical/changed/cut) and title
     overlap with our NEP extraction
  3. DPWH bridge probe: senate house-reading:N → review-set HB10858-3-*
     title-match rate (sampled)

Run:  python3 data_formalization/scripts/coverage.py [--skip-probes]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGERS = ROOT / 'data_formalization' / 'data' / 'ledger'
SENATE = ROOT / 'Senate_report_data' / 'data' / 'bettergov-senate-2027-dataset' / 'senate-2027-dataset'
REVIEW_SET = ROOT / 'dpwh_HGAB_REVIEW_SET'


def norm_title(t: str) -> str:
    return re.sub(r'[^a-z0-9]', '', str(t).lower())[:80]


def ledger_coverage():
    print('=' * 72)
    print('1. LEDGER COVERAGE (subjects per snapshot; edges between stages)')
    print('=' * 72)
    for dom in ('fmr', 'hfep', 'nia', 'dpwh'):
        p = LEDGERS / f'{dom}.jsonl'
        if not p.exists():
            print(f'\n{dom.upper()}: no ledger')
            continue
        stage_of, edges, senate_rows = {}, Counter(), []
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            if r['type'] == 'line.observed':
                subj = r['subject']
                if subj.startswith('senate:'):
                    senate_rows.append(r)
                else:
                    stage_of[subj] = (r.get('provenance') or {}).get('snapshot', '?')
            elif r['type'] == 'match.asserted':
                pl = r['payload']
                edges[(stage_of.get(r['subject'], r['subject'].split(':')[0] + ':*'),
                       stage_of.get(pl.get('to'), str(pl.get('to')).split(':')[0] + ':*'))] += 1
        by_snap = Counter(stage_of.values())
        print(f'\n{dom.upper()} ledger')
        for s, n in sorted(by_snap.items()):
            print(f'  subjects {s}: {n}')
        if senate_rows:
            dialects = Counter(((r['payload'].get('house_ref') or 'NONE')
                                .split(':')[0]) for r in senate_rows)
            print(f'  senate rows: {len(senate_rows)} | house_ref dialects: {dict(dialects)}')
        if edges:
            for (a, b), n in sorted(edges.items()):
                print(f'  edges {a} -> {b}: {n}')
        else:
            print('  edges: NONE (matching gap — see §14)')


def nia_probe():
    import openpyxl
    print('\n' + '=' * 72)
    print('2. NIA AGENCY-RECON PROBE (NIA_DATA/NIA_NEP_2026-11-13.xlsx)')
    print('=' * 72)
    wb = openpyxl.load_workbook(ROOT / 'NIA_DATA' / 'NIA_NEP_2026-11-13.xlsx',
                                read_only=True, data_only=True)
    ws = wb['DETAILS 2027']
    leaves = []
    for row in ws.iter_rows(min_row=1, values_only=True):
        g = row[6] if len(row) > 6 else None
        h = row[7] if len(row) > 7 else None
        i = row[8] if len(row) > 8 else None
        if g and isinstance(h, (int, float)) and isinstance(i, (int, float)):
            leaves.append((str(g), h, i))
    wb.close()
    ident = sum(1 for _, h, i in leaves if h == i)
    cut = sum(1 for _, h, i in leaves if i == 0 and h > 0)
    changed = len(leaves) - ident - cut
    print(f'numeric leaves: {len(leaves)} | identical: {ident} | '
          f'changed(nonzero): {changed} | cut-to-zero: {cut}')
    d = json.load(open(ROOT / 'analysis-nia' / 'data' / 'nep_nia_dataset.json'))
    ours = {norm_title(p['label']) for p in d['projects']}
    theirs = {norm_title(t) for t, _, _ in leaves}
    print(f'title overlap with nep_nia_dataset: {len(ours & theirs)}/{len(theirs)} '
          f'agency items ({len(ours & theirs)/max(len(theirs),1):.0%})')


def dpwh_bridge_probe(sample=3000):
    print('\n' + '=' * 72)
    print('3. DPWH BRIDGE PROBE (senate house-reading:N -> review-set HB10858-3-*)')
    print('=' * 72)
    with open(SENATE / 'senate-2027-projects.csv', encoding='utf-8-sig') as fh:
        senate = [r for r in csv.DictReader(fh)
                  if r['program'] == 'dpwh' and r['house_id']]
    with open(REVIEW_SET / 'house-bill-2027-dpwh-projects.csv',
              encoding='utf-8-sig') as fh:
        review = {norm_title(r['title']): r['hgab_id']
                  for r in csv.DictReader(fh)}
    hit = sum(1 for r in senate[:sample] if norm_title(r['title']) in review)
    n = min(sample, len(senate))
    print(f'sample {n}/{len(senate)} senate dpwh rows: {hit} title-matched '
          f'({hit/max(n,1):.0%}) -> bridge feasible; ambiguous titles need '
          f'amount tie-breaking')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-probes', action='store_true')
    args = ap.parse_args()
    ledger_coverage()
    if not args.skip_probes:
        try:
            nia_probe()
        except ImportError:
            print('\n(openpyxl unavailable — NIA probe skipped)')
        dpwh_bridge_probe()


if __name__ == '__main__':
    main()
