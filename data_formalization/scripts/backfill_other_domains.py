#!/usr/bin/env python3
"""Backfill the remaining domains into the formalization model:

  HFEP   snapshots: nep_hfep_data_list.json (464), hgab_hfep_data_list.json
         (513); matches: hfep_workbench comparison.pairs (341, similarity)
  NIA    snapshots: nep_nia_dataset.json (791 projects, embedded-OCR
         provenance), hgab_nia_projects.csv (828); matches: none yet (only
         control totals exist) — registered as open gap
  DPWH   snapshot: stage_trace_2027.json projects (17,610 with trace +
         house_match + confidence) — registered as the core monolith node;
         full decomposition deferred (monolith payloads stay referenced)
  Senate full import across all four domains:
         - projects rows → line.observed per domain ledger (senate:* subjects)
         - status != unchanged → match.asserted/match.retracted style edges
           are NOT fabricated: senate rows carry house_ref; edges recorded as
           review-flagged observations where matched_by is weak
         - pairings.csv (281) → review.requested (actor: bettergov)
         - page-misses.csv (2) → validation.finding on nep_hfep:p10:r16
         - checks.csv (38) → validation.run on the import node

Subject rules:
  hfep: nep_hfep:p#:r#, ib:p#:r#      per-snapshot locators
  nia:  nep-nia-p##-y### (their ids), ib:p#:r#
  dpwh: house-reading:# (their ids)   bridge transition pending
  senate rows: senate:<id> everywhere (their id vocabulary)

Run:  python3 data_formalization/scripts/backfill_other_domains.py [--check]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger as L   # noqa: E402
import lineage as G  # noqa: E402

SENATE = ROOT / 'Senate_report_data' / 'data' / 'bettergov-senate-2027-dataset' / 'senate-2027-dataset'
H = ROOT / 'analysis-hfep' / 'data'
N = ROOT / 'analysis-nia' / 'data'
A = ROOT / 'analysis' / 'data'


def emit(domain, subject, rtype, actor, payload, provenance, sink, counts, key):
    counts[key] = counts.get(key, 0) + 1
    if sink:
        L.append(domain, subject, rtype, actor, payload, provenance)


def _int(v):
    try:
        return int(str(v).replace(',', ''))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- HFEP ----
def backfill_hfep(sink: bool, counts: dict):
    for stage, fname in (('nep', 'nep_hfep_data_list.json'),
                         ('house', 'hgab_hfep_data_list.json')):
        d = json.load(open(H / fname))
        snap = f'snapshot/hfep/{stage}'
        for it in d['items']:
            src = it.get('source') or {}
            emit('hfep', it['id'], 'line.observed', 'pipeline',
                 {'label_raw': it.get('label_raw'),
                  'amounts_php': it.get('amounts_php'),
                  'hierarchy': it.get('hierarchy')},
                 {'snapshot': snap, 'pdf_page': src.get('pdf_page'),
                  'printed_page': src.get('printed_page'),
                  'table_row': src.get('table_row')},
                 sink, counts, f'observed_hfep_{stage}')
    wb = json.load(open(ROOT / 'other-analysis' / 'data' / 'hfep_workbench.json'))
    for pair in wb['comparison']['pairs']:
        emit('hfep', pair['nep_id'], 'match.asserted', 'pipeline',
             {'to': pair['house_id'], 'method': 'title-similarity',
              'similarity': pair.get('similarity'),
              'basis': 'hfep_workbench comparison.pairs'},
             {'snapshot': f'snapshot/hfep/nep'}, sink, counts, 'match_hfep')


# ----------------------------------------------------------------- NIA ----
def backfill_nia(sink: bool, counts: dict):
    d = json.load(open(N / 'nep_nia_dataset.json'))
    for p in d['projects']:
        prov = p.get('provenance') or {}
        emit('nia', p['id'], 'line.observed', 'pipeline',
             {'sub_program': p.get('sub_program'), 'label': p.get('label'),
              'amount_php': p.get('amount_php')},
             {'snapshot': 'snapshot/nia/nep', 'pdf_page': prov.get('page'),
              'extraction_method': prov.get('extraction_method')},
             sink, counts, 'observed_nia_nep')
    with open(N / 'hgab_nia_projects.csv', encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            emit('nia', r['id'], 'line.observed', 'pipeline',
                 {'subprogram': r.get('subprogram'), 'title': r.get('title'),
                  'amount_php': _int(r.get('amount_php'))},
                 {'snapshot': 'snapshot/nia/hgab', 'pdf_page': r.get('pdf_page'),
                  'printed_page': r.get('printed_page'),
                  'row_number': r.get('row_number')},
                 sink, counts, 'observed_nia_hgab')


# ---------------------------------------------------------------- DPWH ----
def backfill_dpwh(sink: bool, counts: dict):
    d = json.load(open(A / 'stage_trace_2027.json'))
    for p in d['projects']:
        # stage_trace records are fused traces; subjects use the first
        # available native side id (house hb:* > nep p*:r* > api id), with
        # all side ids carried in the payload. Bridge transitions to our
        # ib: locator space are deliberately deferred (§12 step 5).
        subject = None
        side_used = None
        for side in ('house', 'nep', 'api'):
            v = p.get(side)
            if isinstance(v, dict) and v.get('id'):
                subject, side_used = f'{side}:{v["id"]}', side
                break
        if not subject:
            counts['skipped_dpwh_no_id'] = counts.get('skipped_dpwh_no_id', 0) + 1
            continue
        side_ids = {s: p[s].get('id') for s in ('api', 'nep', 'house')
                    if isinstance(p.get(s), dict) and p.get(s, {}).get('id')}
        emit('dpwh', subject, 'line.observed', 'pipeline',
             {'trace': p.get('trace'), 'house_match': p.get('house_match'),
              'api_presence': p.get('api_presence'),
              'confidence': p.get('confidence'),
              'house_minus_nep_php': p.get('house_minus_nep_php'),
              'side_ids': side_ids, 'subject_side': side_used},
             {'snapshot': 'snapshot/dpwh/stage_trace'},
             sink, counts, 'observed_dpwh')
    for g in d.get('transparency_gaps', []):
        emit('dpwh', f"gap:{g['source_id']}", 'line.observed', 'pipeline',
             {'kind': 'transparency_gap', 'title': g.get('title'),
              'amount_php': g.get('amount_php'), 'pap': g.get('pap'),
              'region': g.get('region')},
             {'snapshot': 'snapshot/dpwh/stage_trace',
              'pdf_page': g.get('pdf_page')},
             sink, counts, 'observed_dpwh_gaps')


# -------------------------------------------------------------- Senate ----
SENATE_DOMAIN = {'fmr': 'fmr', 'hfep': 'hfep', 'nia': 'nia', 'dpwh': 'dpwh'}

def _existing_keys(domain: str) -> set[tuple]:
    """(subject, type, snapshot|question) keys already in a ledger, so
    senate-import reruns are idempotent instead of duplicating rows."""
    keys = set()
    p = L.ledger_path(domain)
    if not p.exists():
        return keys
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        if r['type'] == 'line.observed':
            keys.add((r['subject'], 'obs',
                      (r.get('provenance') or {}).get('snapshot')))
        elif r['type'] == 'review.requested':
            keys.add((r['subject'], 'review',
                      (r.get('payload') or {}).get('question')))
    return keys

def backfill_senate(sink: bool, counts: dict):
    seen = {d: _existing_keys(d) for d in ('fmr', 'hfep', 'nia', 'dpwh')}
    # projects rows → line.observed in each domain's ledger
    with open(SENATE / 'senate-2027-projects.csv', encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            dom = SENATE_DOMAIN[r['program']]
            key = (f"senate:{r['id']}", 'obs', 'import/senate_bettergov_2027')
            if key in seen[dom]:
                counts[f'senate_obs_skipped_{dom}'] = \
                    counts.get(f'senate_obs_skipped_{dom}', 0) + 1
                continue
            seen[dom].add(key)
            payload = {'status': r['status'], 'matched_by': r['matched_by'],
                       'house_ref': r['house_id'] or None,
                       'senate_php': _int(r.get('senate_php')),
                       'vs_house_php': _int(r.get('vs_house_php')),
                       'nep_php': _int(r.get('nep_php'))}
            prov = {'snapshot': 'import/senate_bettergov_2027',
                    'senate_doc': r.get('senate_doc'),
                    'senate_page': r.get('senate_page')}
            emit(dom, f"senate:{r['id']}", 'line.observed', 'bettergov',
                 payload, prov, sink, counts, f'senate_observed_{dom}')

    # pairings.csv → review.requested (their open questions)
    with open(SENATE / 'senate-2027-pairings.csv', encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            dom = SENATE_DOMAIN[r['program']]
            key = (f"senate:{r['id']}", 'review', r.get('matched_by'))
            if key in seen[dom]:
                counts[f'senate_rev_skipped_{dom}'] = \
                    counts.get(f'senate_rev_skipped_{dom}', 0) + 1
                continue
            seen[dom].add(key)
            emit(dom, f"senate:{r['id']}", 'review.requested', 'bettergov',
                 {'question': r.get('matched_by'),
                  'note': (r.get('check_note') or '')[:200],
                  'paired_title': r.get('paired_title'),
                  'senate_page': r.get('senate_page')},
                 {'snapshot': 'import/senate_bettergov_2027'},
                 sink, counts, f'senate_review_{dom}')

    # page-misses.csv → validation.finding on our HFEP locator
    with open(SENATE / 'senate-2027-page-misses.csv', encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            if r['program'] != 'hfep':
                continue
            subject = r['id'].split('|')[0]  # nep_hfep:p10:r16|infrastructure
            emit('hfep', subject, 'validation.finding', 'bettergov',
                 {'check': 'senate-page-link', 'result': 'miss',
                  'note': f"title '{r['title']}' not found on NEP pdf page "
                          f"{r['page']} — OCR-garbled upstream (see EDGE_CASES.md)",
                  'column': r['id'].split('|')[1] if '|' in r['id'] else None},
                 {'snapshot': 'import/senate_bettergov_2027'},
                 sink, counts, 'senate_page_misses')

    # checks.csv → one validation.run on the import node (node-scoped, logged
    # into the fmr ledger only as the registry anchor domain)
    p = L.ledger_path('fmr')
    already = p.exists() and any(
        (r.get('type') == 'validation.run'
         and r.get('payload', {}).get('check') == 'senate-checks-suite')
        for r in map(json.loads, open(p, encoding='utf-8')))
    if already:
        counts['senate_checks_run_skipped'] = 1
        return
    with open(SENATE / 'senate-2027-checks.csv', encoding='utf-8-sig') as fh:
        rows = list(csv.DictReader(fh))
        rows = list(csv.DictReader(fh))
    passed = sum(1 for r in rows if r['ok'].lower() in ('true', '1', 'yes'))
    emit('fmr', 'import/senate_bettergov_2027', 'validation.run', 'bettergov',
         {'check': 'senate-checks-suite', 'total': len(rows), 'passed': passed,
          'failed': len(rows) - passed,
          'note': 'checks.csv: sha, control totals, arithmetic; 1 advisory '
                  'fail rooted in upstream NEP OCR (cYanmGtalo Tab])'},
         {'snapshot': 'import/senate_bettergov_2027'},
         sink, counts, 'senate_checks_run')


def register_nodes():
    # HFEP
    G.register('source/hfep/nep_annex_json', 'source_doc',
               'dbm-other-nep-line-data/HFEP.pdf_by_PP-StructrueV3.json', [],
               'PP-StructureV3 OCR of HFEP.pdf (trusted extraction input)')
    G.register('snapshot/hfep/nep', 'snapshot',
               'analysis-hfep/data/nep_hfep_data_list.json',
               ['source/hfep/nep_annex_json'], 'analysis-hfep extraction')
    G.register('snapshot/hfep/house', 'snapshot',
               'analysis-hfep/data/hgab_hfep_data_list.json',
               ['source/fmr/hgab_vol_ib_pdf'], 'analysis-hfep extraction')
    G.register('transition/hfep/nep_to_house', 'transition',
               'other-analysis/data/hfep_workbench.json',
               ['snapshot/hfep/nep', 'snapshot/hfep/house'],
               'build_hfep_workbench.py comparison.pairs (341)')
    # NIA
    G.register('snapshot/nia/nep', 'snapshot',
               'analysis-nia/data/nep_nia_dataset.json',
               ['source/nia/nep_annex_pdf'], 'analysis-nia v9 extraction')
    G.register('snapshot/nia/hgab', 'snapshot',
               'analysis-nia/data/hgab_nia_projects.csv',
               ['source/fmr/hgab_vol_ib_pdf'], 'analysis-nia extraction')
    G.register('source/nia/nep_annex_pdf', 'source_doc',
               'dbm-other-nep-line-data/NIA.pdf', [],
               'NIA FY2027 NEP annex (embedded OCR text layer)')
    # DPWH
    G.register('snapshot/dpwh/stage_trace', 'snapshot',
               'analysis/data/stage_trace_2027.json', [],
               'analysis/builders/build_stage_trace.py (NEP API+PDF, House extract)')
    G.register('snapshot/dpwh/comparison_projects', 'snapshot',
               'analysis/data/comparison_projects_2027.json',
               ['snapshot/dpwh/stage_trace'], 'stage_trace sibling artifact')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    if not args.check:
        for dom in ('hfep', 'nia', 'dpwh'):
            if L.ledger_path(dom).exists():
                n = sum(1 for _ in open(L.ledger_path(dom), encoding='utf-8'))
                raise SystemExit(f'{dom} ledger exists with {n} records; '
                                 f'clear deliberately before rerunning')
        # fmr already has senate observations from backfill_fmr; the senate
        # import adds review/checks records — allowed to append

    counts: dict = {}
    backfill_hfep(sink=not args.check, counts=counts)
    backfill_nia(sink=not args.check, counts=counts)
    backfill_dpwh(sink=not args.check, counts=counts)
    backfill_senate(sink=not args.check, counts=counts)

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
