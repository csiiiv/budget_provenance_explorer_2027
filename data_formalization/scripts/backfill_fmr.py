#!/usr/bin/env python3
"""FMR pilot backfill (§12 step 0 of data_formalization/docs/DATA_MODEL.md).

Registers trusted FMR sources and snapshots as lineage nodes, then backfills
the per-line-item ledger:

  line.observed   one per project per snapshot (nep, hgab, da nov5, da nov12)
                  subject = per-snapshot locator, EXCEPT DA rows whose stable
                  identity is control_no (row ids shift between drafts:
                  1021/1021 changed, control_no drift 0) → da_fmr:ctrl:<R..>
  match.asserted  from workbench comparison (nep→house pairs, 609) and DA
                  draft match sides
  line.observed   senate fmr rows (964 carry our comparison-row house_ids)

Ledger stores interpretation-grade fields only (locators, region, amounts,
disposition); full row content stays in the snapshot JSONs.

Identity rules encoded here (§12/§5):
  * nep_fmr:*, ib:*      locators minted per printed annex (stable per doc)
  * da_fmr:ctrl:*        control_no-keyed DA subjects across drafts
  * senate:<id>          colleague import row ids (senate-fmr-####)

Run:  python3 data_formalization/scripts/backfill_fmr.py [--check]
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

FMR_DIR = ROOT / 'other-analysis' / 'data'
SENATE_CSV = (ROOT / 'Senate_report_data' / 'data' / 'bettergov-senate-2027-dataset'
              / 'senate-2027-dataset' / 'senate-2027-projects.csv')

SOURCES = [
    ('source/fmr/nep_annex_pdf', 'dbm-other-nep-line-data/FMR.pdf'),
    ('source/fmr/hgab_vol_ib_pdf', 'HB_BUDGET/2 - HB 10858 VOL IB.pdf'),
    ('source/fmr/da_xlsx_nov5',
     'DA_FMR_DATA/Working Draft as of Nov 5_63627eee-5ce6-4da9-bfc5-52c25db9e375 (1).xlsx'),
    ('source/fmr/da_xlsx_nov12', 'DA_FMR_DATA/REVISED NEP as of Nov 12 2026, 920pm.xlsx'),
]
SNAPSHOTS = [
    # node_id, rel path, inputs, builder note
    ('snapshot/fmr/nep', 'other-analysis/data/nep_fmr_final_dataset.json',
     ['source/fmr/nep_annex_pdf'], 'other-analysis trusted NEP extraction'),
    ('snapshot/fmr/hgab', 'other-analysis/data/hgab_fmr_final_dataset.json',
     ['source/fmr/hgab_vol_ib_pdf'], 'other-analysis trusted HGAB extraction'),
    ('snapshot/fmr/da_draft_nov5', 'other-analysis/data/da_fmr_draft.json',
     ['source/fmr/da_xlsx_nov5'], 'other-analysis extract_da_fmr.py (xlsx sha-pinned)'),
    ('snapshot/fmr/da_draft_nov12', 'other-analysis/data/da_fmr_draft_nov12.json',
     ['source/fmr/da_xlsx_nov12'], 'other-analysis extract_da_fmr.py (xlsx sha-pinned)'),
]
IMPORT = ('import/senate_bettergov_2027', str(SENATE_CSV.relative_to(ROOT)),
          'colleague dataset (verified: Senate_report_data/docs/VERIFICATION.md)')


def da_subject(p: dict) -> str:
    return f"da_fmr:ctrl:{p['control_no']}" if p.get('control_no') else p['id']


def register_nodes():
    for node_id, rel in SOURCES:
        G.register(node_id, 'source_doc', rel, [], 'byte-identical acquisition')
    for node_id, rel, inputs, builder in SNAPSHOTS:
        G.register(node_id, 'snapshot', rel, inputs, builder)
    G.register(IMPORT[0], 'import', IMPORT[1], [], IMPORT[2])


def emit(subject, rtype, actor, payload, provenance, sink, counts, key):
    counts[key] = counts.get(key, 0) + 1
    if not sink:
        return
    L.append('fmr', subject, rtype, actor, payload, provenance)


def backfill(sink: bool) -> dict:
    wb = json.load(open(FMR_DIR / 'fmr_workbench.json'))
    counts: dict = {}

    # 1. line.observed — NEP + House snapshots (per-snapshot locators)
    for stage_key, snap in (('nep', 'snapshot/fmr/nep'), ('house', 'snapshot/fmr/hgab')):
        for p in wb['stages'][stage_key]['projects']:
            src = p.get('source') or {}
            emit(p['id'], 'line.observed', 'pipeline',
                 {'region_key': p.get('region_key'), 'amount_php': p.get('amount_php')},
                 {'snapshot': snap, 'pdf_page': src.get('pdf_page'),
                  'printed_page': src.get('printed_page'), 'table_row': src.get('table_row')},
                 sink, counts, f'observed_{stage_key}')

    # 2. line.observed — DA drafts (control_no-keyed subjects)
    for snap_key, fname in (('da_draft_nov5', 'da_fmr_draft.json'),
                            ('da_draft_nov12', 'da_fmr_draft_nov12.json')):
        d = json.load(open(FMR_DIR / fname))
        for p in d['projects']:
            emit(da_subject(p), 'line.observed', 'pipeline',
                 {'control_no': p.get('control_no'), 'kind': p.get('kind'),
                  'disposition': p.get('disposition'), 'region_key': p.get('region_key'),
                  'from_amount_php': p.get('from_amount_php'),
                  'proposed_amount_php': p.get('proposed_amount_php'),
                  'effective_amount_php': p.get('effective_amount_php')},
                 {'snapshot': f'snapshot/fmr/{snap_key}', 'excel_row': p.get('excel_row'),
                  'row_locator': p['id']},
                 sink, counts, f'observed_{snap_key}')

    # 3. match.asserted — workbench nep→house pairs
    for row in wb['comparison']:
        if row['status'] != 'paired' or not row.get('nep_id'):
            continue
        emit(row['nep_id'], 'match.asserted', 'pipeline',
             {'to': row['house_id'], 'method': row.get('method'),
              'basis': 'fmr_workbench comparison'},
             {'snapshot': 'snapshot/fmr/nep'}, sink, counts, 'match_nep_house')

    # 4. match.asserted — DA draft match sides (from comparison rows' da refs)
    for row in wb['comparison']:
        da = row.get('da') or {}
        if not da.get('matched') or 'from' not in da:
            continue
        src = da['from']
        subj = f"da_fmr:ctrl:{src['control_no']}" if src.get('control_no') else src['id']
        # Edge target = the side DA actually matched: 'nep' → the NEP locator
        # (chain continues via the nep→house edge), 'house' → the ib: locator.
        if da.get('match_side') == 'house' and row.get('house_id'):
            target = row['house_id']
        elif da.get('match_side') == 'nep' and row.get('nep_id'):
            target = row['nep_id']
        elif row.get('nep_id') or row.get('house_id'):
            target = row['nep_id'] or row['house_id']
        else:
            continue
        emit(subj, 'match.asserted', 'pipeline',
             {'to': target, 'method': da.get('match_method'),
              'match_side': da.get('match_side'),
              'basis': 'fmr_workbench da linkage'},
             {'snapshot': 'snapshot/fmr/da_draft_nov5'}, sink, counts, 'match_da')

    # 5. line.observed — senate import rows (fmr program)
    with open(SENATE_CSV, encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            if r['program'] != 'fmr':
                continue
            emit(f"senate:{r['id']}", 'line.observed', 'bettergov',
                 {'status': r.get('status'), 'matched_by': r.get('matched_by'),
                  'house_ref': r['house_id'] or None,
                  'senate_php': _num(r.get('senate_php'))},
                 {'snapshot': IMPORT[0], 'senate_doc': r.get('senate_doc'),
                  'senate_page': r.get('senate_page')}, sink, counts, 'observed_senate')
    return counts


def _num(v):
    return int(v) if v and v.lstrip('-').isdigit() else (float(v) if _isfloat(v) else None) if v else None


def _isfloat(v):
    try:
        float(v); return True
    except (TypeError, ValueError):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='count only; write nothing')
    ap.add_argument('--force', action='store_true',
                    help='allow rerun even if ledger already has fmr records')
    args = ap.parse_args()

    if not args.check and not args.force and L.ledger_path('fmr').exists():
        n = sum(1 for _ in open(L.ledger_path('fmr'), encoding='utf-8'))
        raise SystemExit(
            f'fmr ledger already has {n} records; rerunning would duplicate. '
            f'Use --force only after deliberately clearing the ledger.')

    counts = backfill(sink=not args.check)
    if args.check:
        print(json.dumps(counts, indent=1))
        print('(check mode: nothing written)')
        return
    register_nodes()
    print(json.dumps(counts, indent=1))
    print(L.verify('fmr'))
    problems = G.verify(None)
    print('lineage: FAIL\n' + '\n'.join(problems) if problems else 'lineage: OK: all nodes verify')


if __name__ == '__main__':
    main()
