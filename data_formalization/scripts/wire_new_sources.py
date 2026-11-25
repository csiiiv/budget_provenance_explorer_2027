#!/usr/bin/env python3
"""Wire the newly decoded sources into the registry and ledgers (§14 plan):

  1. NIA agency recon (both vintages) → snapshots + line.observed (one
     subject per leaf, keyed by stable-ish title_key; excel_row/leaf_index
     in provenance) + match.asserted edges nep_nia:* ↔ agency leaves
     (exact title_key), giving NIA its first corroborated nep↔hgab linkage
  2. DPWH review set → import node + line.observed (subjects hgab3:<id>) +
     validation.finding for every red flag (actor bettergov) + review
     import of ambiguous document ties (matched_by tracker)
  3. DPWH bridge A: stage_trace house records → review-set hgab3: subjects,
     title-key exact matches, unique-both-sides only, method recorded
  4. DPWH bridge B: senate house-reading:N rows → hgab3: subjects (title)
  5. NIA cross-vintage diff view (oct10 → nov13, title_key-keyed)

Idempotent: every emit checks existing ledger keys first.

Run:  python3 data_formalization/scripts/wire_new_sources.py [--check]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger as L   # noqa: E402
import lineage as G  # noqa: E402

SENATE = ROOT / 'Senate_report_data' / 'data' / 'bettergov-senate-2027-dataset' / 'senate-2027-dataset'
REVIEW = ROOT / 'dpwh_HGAB_REVIEW_SET'
NIA_RECON = ROOT / 'analysis-nia' / 'data'


def norm_title(t: str) -> str:
    return re.sub(r'[^a-z0-9]', '', str(t).lower())[:80]


class Idempotent:
    """Loads (subject, type, discriminator) keys once per domain."""

    def __init__(self):
        self._keys: dict[str, set] = {}

    def seen(self, domain: str, subject: str, rtype: str, disc: str) -> bool:
        keys = self._keys.get(domain)
        if keys is None:
            keys = set()
            p = L.ledger_path(domain)
            if p.exists():
                for line in open(p, encoding='utf-8'):
                    r = json.loads(line)
                    if r['type'] == 'line.observed':
                        keys.add((r['subject'], 'obs',
                                  (r.get('provenance') or {}).get('snapshot')))
                    elif r['type'] == 'match.asserted':
                        keys.add((r['subject'], 'match', r['payload'].get('to')))
                    elif r['type'] == 'validation.finding':
                        keys.add((r['subject'], 'finding',
                                  r['payload'].get('check')))
                    elif r['type'] == 'review.requested':
                        keys.add((r['subject'], 'review',
                                  r['payload'].get('question')))
            self._keys[domain] = keys
        key = (subject, {'line.observed': 'obs', 'match.asserted': 'match',
                         'validation.finding': 'finding',
                         'review.requested': 'review'}[rtype], disc)
        if key in keys:
            return True
        keys.add(key)
        return False


IDE = Idempotent()


def emit(domain, subject, rtype, actor, payload, provenance, sink, counts, key, disc=None):
    if IDE.seen(domain, subject, rtype, disc or provenance.get('snapshot')):
        counts[f'skip_{key}'] = counts.get(f'skip_{key}', 0) + 1
        return
    counts[key] = counts.get(key, 0) + 1
    if sink:
        L.append(domain, subject, rtype, actor, payload, provenance)


# ------------------------------------------------------------------ NIA ----
def wire_nia(sink: bool, counts: dict):
    recons = {}
    for vintage in ('oct10', 'nov13'):
        d = json.load(open(NIA_RECON / f'nia_agency_recon_{vintage}.json'))
        snap = f'snapshot/nia/agency_recon_{vintage}'
        recons[vintage] = d
        for leaf in d['leaves']:
            # subject: agency leaf, keyed by title_key (stable across
            # vintages; row numbers shift like DA drafts)
            subj = f'nia_agency:{leaf["title_key"]}'
            emit('nia', subj, 'line.observed', 'pipeline',
                 {'title': leaf['title'],
                  'nep_amount_php': leaf['nep_amount_php'],
                  'hgab_amount_php': leaf['hgab_amount_php']},
                 {'snapshot': snap, 'leaf_index': leaf['leaf_index']},
                 sink, counts, f'nia_recon_observed_{vintage}')

    # match our NEP extraction leaves <-> agency nov13 leaves (title exact)
    d = json.load(open(ROOT / 'analysis-nia' / 'data' / 'nep_nia_dataset.json'))
    nov13 = {l['title_key']: l for l in recons['nov13']['leaves']}
    for p in d['projects']:
        k = norm_title(p['label'])
        if k in nov13:
            emit('nia', p['id'], 'match.asserted', 'pipeline',
                 {'to': f'nia_agency:{k}', 'method': 'title_key_exact',
                  'basis': 'agency recon title overlap (§14 probe 79%)'},
                 {'snapshot': 'snapshot/nia/nep'},
                 sink, counts, 'nia_match_ours_to_agency')


# ---------------------------------------------------------------- DPWH ----
def wire_dpwh(sink: bool, counts: dict):
    # review set: projects as observations in their vocabulary
    with open(REVIEW / 'house-bill-2027-dpwh-projects.csv', encoding='utf-8-sig') as fh:
        projects = list(csv.DictReader(fh))
    by_title = {}
    dup_titles = set()
    for r in projects:
        k = norm_title(r['title'])
        if k in by_title:
            dup_titles.add(k)
        else:
            by_title[k] = r
    for r in projects:
        emit('dpwh', f"hgab3:{r['hgab_id']}", 'line.observed', 'bettergov',
             {'title': r['title'], 'amount_php': _int(r.get('amount_php')),
              'region': r.get('region'), 'program': r.get('program'),
              'pap': r.get('pap'),
              'house_insertion': r.get('house_insertion') == 'true',
              'red_flags': _int(r.get('red_flags')) or 0,
              'key_documents_found': r.get('key_documents_found')},
             {'snapshot': 'import/dpwh_hgab_review_set',
              'bill_pdf_page': r.get('bill_pdf_page'),
              'bill_row': r.get('bill_row')},
             sink, counts, 'dpwh_review_observed')

    # red flags → validation.finding
    with open(REVIEW / 'house-bill-2027-dpwh-red-flags.csv',
              encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            emit('dpwh', f"hgab3:{r['hgab_id']}", 'validation.finding',
                 'bettergov',
                 {'check': f'red-flag:{r["flag_code"]}',
                  'result': 'flagged',
                  'family': r.get('family'), 'source': r.get('source'),
                  'value_php': _int(r.get('value_php')),
                  'note': (r.get('evidence') or '')[:200]},
                 {'snapshot': 'import/dpwh_hgab_review_set'},
                 sink, counts, 'dpwh_red_flags',
                 disc=f'red-flag:{r["flag_code"]}')

    # bridge A: stage_trace house side -> review set (title exact, unique)
    t = json.load(open(ROOT / 'analysis' / 'data' / 'stage_trace_2027.json'))
    for p in t['projects']:
        h = p.get('house')
        if not (isinstance(h, dict) and h.get('id')):
            continue
        k = norm_title(h.get('title') or p.get('title') or '')
        if not k or k in dup_titles:
            counts['dpwh_bridgeA_ambiguous'] = \
                counts.get('dpwh_bridgeA_ambiguous', 0) + 1
            continue
        rr = by_title.get(k)
        if not rr:
            counts['dpwh_bridgeA_miss'] = counts.get('dpwh_bridgeA_miss', 0) + 1
            continue
        emit('dpwh', f"house:{h['id']}", 'match.asserted', 'pipeline',
             {'to': f'hgab3:{rr["hgab_id"]}', 'method': 'title_exact_unique',
              'basis': 'bridge A: stage_trace Vol I-C ids ↔ review set '
                       '(§14: same-bill 3rd-reading dialect)'},
             {'snapshot': 'snapshot/dpwh/stage_trace'},
             sink, counts, 'dpwh_bridgeA')

    # bridge B: senate house-reading rows -> review set (two-pass title:
    # senate title, then their recorded house_title for renamed rows)
    with open(SENATE / 'senate-2027-projects.csv', encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            if r['program'] != 'dpwh' or not r['house_id']:
                continue
            k1 = norm_title(r['title'])
            k2 = norm_title(r.get('house_title') or '')
            target, method = None, None
            if k1 and k1 not in dup_titles and k1 in by_title:
                target, method = by_title[k1], 'title_exact_unique'
            elif k2 and k2 not in dup_titles and k2 in by_title:
                target, method = by_title[k2], 'house_title_exact_unique'
            if not target:
                emit('dpwh', f"senate:{r['id']}", 'review.requested', 'bettergov',
                     {'question': 'bridge-b-unresolved',
                      'note': f"senate title / house_title both unmatched or "
                              f"ambiguous vs review set (status={r['status']})",
                      'senate_status': r['status']},
                     {'snapshot': 'import/senate_bettergov_2027'},
                     sink, counts, 'dpwh_bridgeB_unresolved',
                     disc='bridge-b-unresolved')
                continue
            emit('dpwh', f"senate:{r['id']}", 'match.asserted', 'bettergov',
                 {'to': f'hgab3:{target["hgab_id"]}',
                  'method': method,
                  'basis': 'bridge B: senate ↔ review set two-pass title '
                           '(house_title rescues renamed rows)'},
                 {'snapshot': 'import/senate_bettergov_2027'},
                 sink, counts, 'dpwh_bridgeB', disc=f'hgab3:{target["hgab_id"]}')


def _int(v):
    try:
        return int(str(v).replace(',', ''))
    except (TypeError, ValueError):
        return None


def register_nodes():
    G.register('source/nia/agency_recon_xlsx_oct10', 'source_doc',
               'NIA_DATA/NIA%20FY%202027%20NEP%20OCTOBER%2010%201043PM.xlsx',
               [], 'agency-supplied workbook (sha-pinned)')
    G.register('source/nia/agency_recon_xlsx_nov13', 'source_doc',
               'NIA_DATA/NIA_NEP_2026-11-13.xlsx',
               [], 'agency-supplied workbook (sha-pinned)')
    G.register('snapshot/nia/agency_recon_oct10', 'snapshot',
               'analysis-nia/data/nia_agency_recon_oct10.json',
               ['source/nia/agency_recon_xlsx_oct10'],
               'extract_nia_recon.py')
    G.register('snapshot/nia/agency_recon_nov13', 'snapshot',
               'analysis-nia/data/nia_agency_recon_nov13.json',
               ['source/nia/agency_recon_xlsx_nov13'],
               'extract_nia_recon.py')
    G.register('import/dpwh_hgab_review_set', 'import',
               'dpwh_HGAB_REVIEW_SET/house-bill-2027-dpwh-projects.csv',
               [], 'bettergov review set (own README manifest; 3 CSVs)')
    # NIA cross-vintage diff view
    a = json.load(open(NIA_RECON / 'nia_agency_recon_oct10.json'))
    b = json.load(open(NIA_RECON / 'nia_agency_recon_nov13.json'))
    ka = {l['title_key']: l for l in a['leaves']}
    kb = {l['title_key']: l for l in b['leaves']}
    diff = {
        'added': sorted(kb.keys() - ka.keys()),
        'removed': sorted(ka.keys() - kb.keys()),
        'amount_changed': sorted(
            k for k in ka.keys() & kb.keys()
            if (ka[k]['nep_amount_php'], ka[k]['hgab_amount_php'])
            != (kb[k]['nep_amount_php'], kb[k]['hgab_amount_php'])),
    }
    out = NIA_RECON / 'nia_recon_oct10_to_nov13_diff.json'
    out.write_text(json.dumps({
        'schema_version': 1, 'type': 'view',
        'compares': ['snapshot/nia/agency_recon_oct10',
                     'snapshot/nia/agency_recon_nov13'],
        'key': 'title_key',
        'summary': {k_: len(v) for k_, v in diff.items()},
        'diff': diff}, indent=1, ensure_ascii=False) + '\n')
    G.register('view/nia/agency_recon_oct10_to_nov13_diff', 'view',
               'analysis-nia/data/nia_recon_oct10_to_nov13_diff.json',
               ['snapshot/nia/agency_recon_oct10',
                'snapshot/nia/agency_recon_nov13'],
               'wire_new_sources.py')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    counts: dict = {}
    wire_nia(sink=not args.check, counts=counts)
    wire_dpwh(sink=not args.check, counts=counts)
    if args.check:
        print(json.dumps(counts, indent=1))
        print('(check mode: nothing written)')
        return
    register_nodes()
    print(json.dumps(counts, indent=1))
    for dom in ('fmr', 'hfep', 'nia', 'dpwh'):
        print(L.verify(dom))
    problems = G.verify(None)
    print('lineage:', 'FAIL\n' + '\n'.join(problems) if problems
          else 'lineage: OK: all nodes verify')


if __name__ == '__main__':
    main()
