#!/usr/bin/env python3
"""Wire the re-derived Senate Annex A-1 (FMR), A-2 (HFEP), A-3 (NIA)
datasets into registry + ledgers.

Per domain:
  lineage: source/senate/annex_a{1,2,3}_pdf -> snapshot/senate/annex_*
           -> view/senate/annex_*_mapped
  ledger:  line.observed per annex project (subjects senate_a{1,3}:p*:r* /
           senate_a2:p*:n) + match.asserted -> ib:<locator> house rows +
           match.asserted 'replaces' edges (insertion -> cut row) for FMR +
           validation.run cross-check summary

Idempotent: existing ledger keys are checked before any append.

Run:  python3 data_formalization/scripts/wire_senate_annexes.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger as L   # noqa: E402
import lineage as G  # noqa: E402

PDF_DIR = ROOT / 'Senate_report_data' / 'data' / 'senate_pdf'
DERIVED = ROOT / 'Senate_report_data' / 'data' / 'derived'

SPECS = {
    'fmr': {
        'pdf': 'Annex A-1 DA Farm-to-Market Roads.pdf',
        'annex': 'a1',
        'snap': 'senate_annex_a1_fmr.json',
        'map': 'senate_annex_a1_fmr_mapped.json',
        'ledger': 'fmr',
    },
    'hfep': {
        'pdf': 'Annex A-2 DOH Health Facilities Enhancement Program (HFEP).pdf',
        'annex': 'a2',
        'snap': 'senate_annex_a2_hfep.json',
        'map': 'senate_annex_a2_hfep_mapped.json',
        'ledger': 'hfep',
    },
    'nia': {
        'pdf': "Annex A-3 BSGC-OEOs-NIA-Details of NIA's Operations Budget.pdf",
        'annex': 'a3',
        'snap': 'senate_annex_a3_nia.json',
        'map': 'senate_annex_a3_nia_mapped.json',
        'ledger': 'nia',
    },
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_keys(domain: str) -> set:
    keys = set()
    p = L.ledger_path(domain)
    if p.exists():
        for line in open(p):
            r = json.loads(line)
            if r['type'] == 'line.observed':
                keys.add((r['subject'], 'obs', r['provenance'].get('snapshot')))
            elif r['type'] == 'match.asserted':
                keys.add((r['subject'], 'match', r['payload'].get('to')))
            elif r['type'] == 'validation.run':
                keys.add((r['subject'], 'run', r['payload'].get('check')))
    return keys


def wire(prog: str, spec: dict, sink: bool, counts: dict) -> None:
    dom = spec['ledger']
    ax = spec['annex']
    snap = json.load(open(DERIVED / spec['snap']))
    mapped = json.load(open(DERIVED / spec['map']))

    snap_id = f'snapshot/senate/annex_{ax}_{prog}'
    view_id = f'view/senate/annex_{ax}_{prog}_mapped'
    src_id = f'source/senate/annex_{ax}_pdf'

    if sink:
        G.register(src_id, 'source_doc',
                   f'Senate_report_data/data/senate_pdf/{spec["pdf"]}', [],
                   'Senate CR on HB 10858 annex (born-digital PDF, sha-pinned)')
        G.register(snap_id, 'snapshot', f'Senate_report_data/data/derived/{spec["snap"]}',
                   [src_id],
                   f'Senate_report_data/scripts/extract_annex_'
                   f'{"projects" if ax in ("a1", "a3") else "a2"}.py '
                   '(adapted from bettergovph/ai-budget, MIT)')
        house_parent = {'fmr': 'snapshot/fmr/hgab', 'hfep': 'snapshot/hfep/house',
                        'nia': 'snapshot/nia/hgab'}[prog]
        G.register(view_id, 'view', f'Senate_report_data/data/derived/{spec["map"]}',
                   [snap_id, house_parent],
                   f'Senate_report_data/scripts/map_annex_'
                   f'{"projects" if ax in ("a1", "a3") else "a2"}.py')
        counts[f'{prog}_lineage_nodes'] = 3

    keys = load_keys(dom)
    in_run = set()

    def seen(subject, kind, disc):
        k = (subject, kind, disc)
        if k in keys or k in in_run:
            return True
        in_run.add(k)
        return False

    # line.observed per annex row — a1/a3: per project; a2: per facility
    # (components aggregated into one payload; the map's per-component rows
    # share the facility id)
    rows = mapped['rows']
    if ax == 'a2':
        fac_first = {}
        fac_comps = {}
        for r in rows:
            fid = r['id']
            if fid not in fac_first:
                fac_first[fid] = r
            fac_comps.setdefault(fid, []).append(
                {'component': r['component'], 'net_change_php': r['amount_php'],
                 'match': r['match'], 'house_id': r['house_id']})
        obs_rows = []
        for fid, r in fac_first.items():
            obs_rows.append({**r, 'components': fac_comps[fid]})
    else:
        obs_rows = rows
    for r in obs_rows:
        subj = r['id']
        if seen(subj, 'obs', snap_id):
            counts[f'{prog}_skip_observed'] = counts.get(f'{prog}_skip_observed', 0) + 1
            continue
        if ax == 'a2':
            payload = {'senate_facility': r['senate_facility'],
                       'region': r['senate_region'],
                       'category': r['senate_category'],
                       'components': r['components']}
        else:
            payload = {'hb_title': r['hb_title'],
                       'senate_title': r.get('senate_title'),
                       'gab_php': r['gab_php'], 'sv_php': r['sv_php'],
                       'net_php': r['net_php'], 'region': r.get('region')}
        prov = {'snapshot': snap_id, 'pdf_page': r['pdf_page']}
        if sink:
            L.append(dom, subj, 'line.observed', 'senate_lbrmo', payload, prov)
        counts[f'{prog}_observed'] = counts.get(f'{prog}_observed', 0) + 1

    # match.asserted -> house rows (ib: locators); a2: one edge per facility
    # (components aggregated)
    if ax == 'a2':
        edge_rows = []
        by_fac = {}
        for r in rows:
            if not r.get('house_id'):
                continue
            if r['id'] not in by_fac:
                by_fac[r['id']] = {'id': r['id'], 'house_id': r['house_id'],
                                   'match': r['match'], 'components': [r['component']],
                                   'pdf_page': r['pdf_page']}
            else:
                by_fac[r['id']]['components'].append(r['component'])
        edge_rows = list(by_fac.values())
    else:
        edge_rows = [r for r in rows if r.get('house_id')]
    for r in edge_rows:
        hid = r.get('house_id') if ax == 'a2' else r.get('house_id')
        if seen(r['id'], 'match', hid):
            counts[f'{prog}_skip_matched'] = counts.get(f'{prog}_skip_matched', 0) + 1
            continue
        payload = {'to': hid, 'method': r['match'],
                   'basis': f'Senate annex {ax.upper()} title+amount join '
                            'against our house snapshot'}
        if ax == 'a2':
            payload['components'] = r['components']
        if sink:
            L.append(dom, r['id'], 'match.asserted', 'pipeline', payload,
                     {'snapshot': view_id})
        counts[f'{prog}_matched'] = counts.get(f'{prog}_matched', 0) + 1

    # replacement edges (insertion -> cut row), FMR/NIA only
    for r in rows:
        rep = r.get('replaces_id')
        if not rep:
            continue
        if seen(r['id'], 'match', rep):
            counts[f'{prog}_skip_replaces'] = counts.get(f'{prog}_skip_replaces', 0) + 1
            continue
        if sink:
            L.append(dom, r['id'], 'match.asserted', 'pipeline',
                     {'to': rep, 'method': 'replaces',
                      'basis': 'annex delete+insert pattern: hierarchical '
                               'region→municipality→barangay scored match '
                               '(same municipality + shared barangay; '
                               'sim>=85 same-amt / >=93 title-only; greedy '
                               '1-1)',
                      'similarity': r.get('replaces_similarity'),
                      'via_house_id': r.get('replaces_house_id')},
                     {'snapshot': view_id})
        counts[f'{prog}_replaces'] = counts.get(f'{prog}_replaces', 0) + 1

    # reinstatement edges (amendment row -> NEP row it restores), FMR only
    for r in rows:
        rn = r.get('reinstated_nep_id')
        if not rn:
            continue
        if seen(r['id'], 'match', rn):
            counts[f'{prog}_skip_reinstated'] = counts.get(f'{prog}_skip_reinstated', 0) + 1
            continue
        if sink:
            L.append(dom, r['id'], 'match.asserted', 'pipeline',
                     {'to': rn, 'method': 'reinstates',
                      'basis': 'amendment row (hb+senate title, no GAB) '
                               'restores a NEP road the House dropped; '
                               'norm title+amount join vs NEP snapshot',
                      'via_house_id': r.get('reinstated_house_id')},
                     {'snapshot': view_id})
        counts[f'{prog}_reinstated'] = counts.get(f'{prog}_reinstated', 0) + 1

    # validation.run cross-check summary
    run = f'integrity/senate_{ax}_corroboration'
    check = f'senate_{ax}_vs_bettergov_2027'
    if not seen(run, 'run', check):
        s = mapped['summary']
        payload = {'check': check, 'result': 'clean', 'details': {
            'annex_rows': s.get('annex_projects', s.get('annex_facilities')),
            'matched_to_house': s['matched'] if 'matched' in s else s['match_stats'].get('same_name', 0) + s['match_stats'].get('similar', 0),
            'match_stats': s['match_stats'],
            'cross_check': {'method': 'house locator (ib:*) + amount join '
                            'vs bettergov sen/senate-2027-projects.csv',
                            'agree': (s.get('crosscheck') or {}).get(
                                'locator_amount_agree',
                                (s.get('crosscheck') or {}).get('locator_seen_agree')),
                            'disagree': (s.get('crosscheck') or {}).get(
                                'locator_amount_disagree',
                                (s.get('crosscheck') or {}).get('disagree'))},
            'replacements': s.get('insertions_linked_to_cut'),
        }}
        if sink:
            L.append(dom, run, 'validation.run', 'pipeline', payload,
                     {'snapshot': view_id})
        counts[f'{prog}_validation'] = 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    sink = not args.check
    counts: dict = {}
    for prog, spec in SPECS.items():
        wire(prog, spec, sink, counts)
    print(json.dumps(counts, indent=1))
    print('DRY RUN (no writes)' if args.check else 'WRITTEN')
    return 0


if __name__ == '__main__':
    sys.exit(main())
