#!/usr/bin/env python3
"""Materialize FMR transition nodes and the DA draft-diff view, then register
them in the lineage registry (§12 steps 1–2 of docs/DATA_MODEL.md).

Nodes produced:
  transition/fmr/nep_to_hgab       the 609 nep→house match edges,
                                   rebuilt FROM THE LEDGER (first half of the
                                   step-3 replay proof: ledger ⊇ transitions)
  transition/fmr/da_nov5_linkage   the 699 DA control_no→prior-stage edges,
                                   from the ledger
  view/fmr/da_nov5_to_nov12_diff   graph diff between the two DA drafts keyed
                                   by control_no: added/removed controls,
                                   moved FROM amounts, disposition changes,
                                   and match-basis-affected controls

Run:  python3 data_formalization/scripts/transitions_fmr.py [--check]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger as L   # noqa: E402
import lineage as G  # noqa: E402

FMR_DIR = ROOT / 'other-analysis' / 'data'
TRANS_DIR = ROOT / 'data_formalization' / 'data' / 'transitions' / 'fmr'


def load_ledger_edges() -> tuple[dict, list[dict]]:
    recs = [json.loads(line) for line in
            open(L.ledger_path('fmr'), encoding='utf-8')]
    nep2house, da_edges = {}, []
    for r in recs:
        if r['type'] != 'match.asserted':
            continue
        p = r['payload']
        if p.get('match_side'):
            da_edges.append({'from': r['subject'], 'to': p['to'],
                             'method': p.get('method'),
                             'match_side': p['match_side']})
        else:
            nep2house[r['subject']] = {'to': p['to'], 'method': p.get('method')}
    return nep2house, da_edges


def write_json(name: str, obj: dict, check: bool) -> Path:
    TRANS_DIR.mkdir(parents=True, exist_ok=True)
    p = TRANS_DIR / name
    if not check:
        p.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + '\n')
    return p


def build_nep_to_hgab(check: bool) -> Path:
    nep2house, _ = load_ledger_edges()
    return write_json('nep_to_hgab.json', {
        'schema_version': 1,
        'type': 'transition',
        'from_snapshot': 'snapshot/fmr/nep',
        'to_snapshot': 'snapshot/fmr/hgab',
        'method_note': 'fmr_workbench comparison (title_and_coordinates / '
                       'title_and_amount), replayed from ledger match.asserted',
        'edge_count': len(nep2house),
        'edges': nep2house,
    }, check)


def build_da_linkage(check: bool) -> Path:
    _, da_edges = load_ledger_edges()
    return write_json('da_nov5_linkage.json', {
        'schema_version': 1,
        'type': 'transition',
        'from_snapshot': 'snapshot/fmr/da_draft_nov5',
        'to_snapshots': ['snapshot/fmr/nep', 'snapshot/fmr/hgab'],
        'method_note': 'fmr_workbench da linkage; subjects keyed by control_no '
                       '(row locators unstable across drafts)',
        'edge_count': len(da_edges),
        'edges': da_edges,
    }, check)


def build_draft_diff(check: bool) -> tuple[Path, dict]:
    nov5 = {p['control_no']: p for p in
            json.load(open(FMR_DIR / 'da_fmr_draft.json'))['projects']
            if p.get('control_no')}
    nov12 = {p['control_no']: p for p in
             json.load(open(FMR_DIR / 'da_fmr_draft_nov12.json'))['projects']
             if p.get('control_no')}
    _, da_edges = load_ledger_edges()
    matched = {e['from'] for e in da_edges}  # da_fmr:ctrl:* subjects

    def ctrl_subject(c):
        return f'da_fmr:ctrl:{c}'

    diff = {
        'added_controls': sorted(nov12.keys() - nov5.keys()),
        'removed_controls': sorted(nov5.keys() - nov12.keys()),
        'disposition_changed': [],
        'from_amount_changed': [],
        'from_title_changed': [],
        'proposed_amount_changed': [],
        'match_basis_affected': [],  # matched controls whose from-basis moved
    }
    for c in sorted(nov5.keys() & nov12.keys()):
        a, b = nov5[c], nov12[c]
        if a.get('disposition') != b.get('disposition'):
            diff['disposition_changed'].append(
                {'control_no': c, 'from': a['disposition'], 'to': b['disposition']})
        if a.get('from_amount_php') != b.get('from_amount_php'):
            diff['from_amount_changed'].append(
                {'control_no': c, 'from': a['from_amount_php'],
                 'to': b['from_amount_php']})
        if a.get('from_title') != b.get('from_title'):
            diff['from_title_changed'].append({'control_no': c})
        if a.get('proposed_amount_php') != b.get('proposed_amount_php'):
            diff['proposed_amount_changed'].append(
                {'control_no': c, 'from': a.get('proposed_amount_php'),
                 'to': b.get('proposed_amount_php')})
        if ctrl_subject(c) in matched and (
                a.get('from_title') != b.get('from_title')
                or a.get('from_amount_php') != b.get('from_amount_php')):
            diff['match_basis_affected'].append({'control_no': c})
    p = write_json('da_nov5_to_nov12_diff.json', {
        'schema_version': 1,
        'type': 'view',
        'compares': ['snapshot/fmr/da_draft_nov5', 'snapshot/fmr/da_draft_nov12'],
        'key': 'control_no',
        'summary': {k: len(v) for k, v in diff.items()},
        'diff': diff,
    }, check)
    return p, {k: len(v) for k, v in diff.items()}


def register_all(nep_hgab: Path, da_link: Path, diff: Path):
    G.register('transition/fmr/nep_to_hgab', 'transition',
               str(nep_hgab.relative_to(ROOT)),
               ['snapshot/fmr/nep', 'snapshot/fmr/hgab'],
               'transitions_fmr.py replay from ledger')
    G.register('transition/fmr/da_nov5_linkage', 'transition',
               str(da_link.relative_to(ROOT)),
               ['snapshot/fmr/da_draft_nov5', 'snapshot/fmr/nep',
                'snapshot/fmr/hgab'],
               'transitions_fmr.py replay from ledger')
    G.register('view/fmr/da_nov5_to_nov12_diff', 'view',
               str(diff.relative_to(ROOT)),
               ['snapshot/fmr/da_draft_nov5', 'snapshot/fmr/da_draft_nov12',
                'transition/fmr/da_nov5_linkage'],
               'transitions_fmr.py')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='build in memory; write nothing')
    args = ap.parse_args()

    nep_hgab = build_nep_to_hgab(args.check)
    da_link = build_da_linkage(args.check)
    diff, summary = build_draft_diff(args.check)
    print('nep→hgab edges:', len(json.loads(nep_hgab.read_text())['edges'])
          if not args.check else '(check)')
    print('da linkage edges:', len(json.loads(da_link.read_text())['edges'])
          if not args.check else '(check)')
    print('nov5→nov12 diff:', json.dumps(summary))
    if not args.check:
        register_all(nep_hgab, da_link, diff)
        problems = G.verify(None)
        print('lineage:', 'FAIL\n' + '\n'.join(problems) if problems
              else 'lineage: OK: all nodes verify')


if __name__ == '__main__':
    main()
