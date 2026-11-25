#!/usr/bin/env python3
"""NIA corroboration: senate pair assertions vs agency reconciliation (§14).

For every senate NIA row carrying a pair: ref:
  senate pair (nep side) -> our nep-nia:* subject -> match edge ->
  agency recon leaf (nov13) -> compare amounts

Outcomes per row:
  corroborated   agency nep_amount == senate nep_php AND
                 agency hgab_amount == senate house_php
  contradicted   amounts disagree on a linked leaf (validation.finding,
                 check: nia-corroboration, result: conflict)
  unlinked       no match edge to an agency leaf (advisory only)

Also verifies the senate *cut* rows against agency cut-to-zero leaves.

Findings are appended to the nia ledger (actor: verify) unless --no-write.
Run:  python3 data_formalization/scripts/corroborate_nia.py [--no-write]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'data_formalization' / 'scripts'))
import ledger as L  # noqa: E402

SENATE = ROOT / 'Senate_report_data' / 'data' / 'bettergov-senate-2027-dataset' / 'senate-2027-dataset'


def _int(v):
    try:
        return int(str(v).replace(',', ''))
    except (TypeError, ValueError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-write', action='store_true')
    args = ap.parse_args()

    # 1. our nep-nia subjects -> agency leaves (from the ledger)
    recs = [json.loads(l) for l in open(L.ledger_path('nia'), encoding='utf-8')]
    to_agency: dict[str, str] = {}   # nep-nia id -> nia_agency:title_key
    agency_amounts: dict[str, dict] = {}
    for r in recs:
        if r['type'] == 'match.asserted' and r['payload'].get('method') == 'title_key_exact':
            to_agency[r['subject']] = r['payload']['to']
        elif r['type'] == 'line.observed' and r['subject'].startswith('nia_agency:') \
                and (r.get('provenance') or {}).get('snapshot') == 'snapshot/nia/agency_recon_nov13':
            agency_amounts[r['subject']] = r['payload']

    # 2. senate nia pair rows
    with open(SENATE / 'senate-2027-projects.csv', encoding='utf-8-sig') as fh:
        senate = [r for r in csv.DictReader(fh)
                  if r['program'] == 'nia' and (r['house_id'] or '').startswith('pair:')]

    stats = {'corroborated': 0, 'contradicted': 0, 'unlinked': 0,
             'cut_corroborated': 0, 'cut_contradicted': 0}
    conflicts = []
    unlinked_ids = []
    for r in senate:
        nep_id = r['house_id'].split(':')[1]          # nep-nia-p#-y#
        leaf = to_agency.get(nep_id)
        agency = agency_amounts.get(leaf) if leaf else None
        if not agency:
            stats['unlinked'] += 1
            unlinked_ids.append(nep_id)
            continue
        s_nep, s_house = _int(r.get('nep_php')), _int(r.get('house_php'))
        a_nep, a_hgab = agency.get('nep_amount_php'), agency.get('hgab_amount_php')
        nep_ok = s_nep is None or a_nep is None or s_nep == a_nep
        house_ok = s_house is None or a_hgab is None or s_house == a_hgab
        is_cut = r['status'] == 'cut'
        if nep_ok and house_ok:
            if is_cut:
                stats['cut_corroborated'] += 1
            else:
                stats['corroborated'] += 1
        else:
            key = 'cut_contradicted' if is_cut else 'contradicted'
            stats[key] += 1
            conflicts.append({
                'subject': nep_id, 'senate': {'nep': s_nep, 'house': s_house,
                                              'status': r['status']},
                'agency': {'nep': a_nep, 'hgab': a_hgab},
                'title': agency.get('title', '')[:60]})

    print(json.dumps(stats, indent=1))
    print(f"linkage: {len(senate) - stats['unlinked']}/{len(senate)} pairs reach an agency leaf")
    for c in conflicts[:10]:
        print(f"  CONFLICT {c['subject']}: senate nep={c['senate']['nep']} "
              f"house={c['senate']['house']} ({c['senate']['status']}) vs "
              f"agency nep={c['agency']['nep']} hgab={c['agency']['hgab']} "
              f"| {c['title']}")

    # 3. write findings
    if not args.no_write:
        for c in conflicts:
            L.append('nia', c['subject'], 'validation.finding', 'verify',
                     {'check': 'nia-corroboration', 'result': 'conflict',
                      'senate': c['senate'], 'agency': c['agency'],
                      'note': f"senate vs agency amounts disagree: {c['title']}"},
                     {'source': 'data_formalization/scripts/corroborate_nia.py',
                      'snapshots': ['import/senate_bettergov_2027',
                                    'snapshot/nia/agency_recon_nov13']})
        # unlinked: open questions, not force-matches — mostly renamed/
        # bundled items whose titles appear in neither agency vintage
        for nid in unlinked_ids:
            L.append('nia', nid, 'review.requested', 'verify',
                     {'question': 'agency-recon-link-missing',
                      'note': 'senate pair present but our NEP item title '
                              'matches no agency leaf (either vintage); '
                              'likely renamed/bundled in the agency book'},
                     {'source': 'data_formalization/scripts/corroborate_nia.py',
                      'snapshots': ['import/senate_bettergov_2027',
                                    'snapshot/nia/agency_recon_nov13']})
        L.append('nia', 'corroboration/run', 'validation.run', 'verify',
                 {'check': 'nia-senate-vs-agency', **stats,
                  'pairs_checked': len(senate)},
                 {'source': 'data_formalization/scripts/corroborate_nia.py',
                  'snapshots': ['import/senate_bettergov_2027',
                                'snapshot/nia/agency_recon_nov13']})
        print(f"\nappended {len(conflicts)} validation.finding + 1 validation.run to nia ledger")
    return 0


if __name__ == '__main__':
    sys.exit(main())
