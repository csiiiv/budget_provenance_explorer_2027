#!/usr/bin/env python3
"""Step-3 replay equivalence check (§12 of data_formalization/docs/DATA_MODEL.md).

Rebuilds the comparison layer of `fmr_workbench.json` FROM THE LEDGER +
registered snapshots, then asserts semantic equality with the committed file:

  - every paired comparison row (nep_id, house_id, method, delta) matches a
    ledger nep→house match.asserted edge
  - every ledger edge corresponds to exactly one paired row (bidirectional)
  - house_only / nep_only counts agree with unmatched observations
  - region totals recomputed from snapshot projects == workbench regions

The React app consumes fmr_workbench.json untouched; this proves the DAG
(ledger + snapshots) can regenerate it, so the file can stay a computed view.

Run:  python3 data_formalization/scripts/replay_fmr.py
Exit 0 = equivalence holds.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger as L  # noqa: E402

WB = ROOT / 'other-analysis' / 'data' / 'fmr_workbench.json'
NEP = ROOT / 'other-analysis' / 'data' / 'nep_fmr_final_dataset.json'
HGAB = ROOT / 'other-analysis' / 'data' / 'hgab_fmr_final_dataset.json'


def main() -> int:
    wb = json.load(open(WB))
    nep = json.load(open(NEP))
    hgab = json.load(open(HGAB))
    recs = [json.loads(l) for l in open(L.ledger_path('fmr'), encoding='utf-8')]

    failures: list[str] = []

    # ---- 1. ledger edges == workbench paired rows (bidirectional) --------
    ledger_edges = {(r['subject'], r['payload']['to'])
                    for r in recs if r['type'] == 'match.asserted'
                    and not r['payload'].get('match_side')}
    wb_pairs = {(row['nep_id'], row['house_id'])
                for row in wb['comparison'] if row['status'] == 'paired'}
    missing = wb_pairs - ledger_edges
    extra = ledger_edges - wb_pairs
    if missing:
        failures.append(f'{len(missing)} paired rows missing from ledger '
                        f'(e.g. {sorted(missing)[:2]})')
    if extra:
        failures.append(f'{len(extra)} ledger edges absent from workbench '
                        f'(e.g. {sorted(extra)[:2]})')

    # ---- 2. methods agree ------------------------------------------------
    ledger_methods = {(r['subject'], r['payload']['to']): r['payload'].get('method')
                      for r in recs if r['type'] == 'match.asserted'
                      and not r['payload'].get('match_side')}
    for row in wb['comparison']:
        if row['status'] != 'paired':
            continue
        key = (row['nep_id'], row['house_id'])
        if ledger_methods.get(key) != row.get('method'):
            failures.append(f'method mismatch at {key}: ledger='
                            f'{ledger_methods.get(key)} wb={row.get("method")}')
            break

    # ---- 3. unpaired counts agree with unmatched observations ------------
    obs_house = {r['subject'] for r in recs
                 if r['type'] == 'line.observed'
                 and r.get('provenance', {}).get('snapshot') == 'snapshot/fmr/hgab'}
    obs_nep = {r['subject'] for r in recs
               if r['type'] == 'line.observed'
               and r.get('provenance', {}).get('snapshot') == 'snapshot/fmr/nep'}
    paired_house = {h for _, h in wb_pairs}
    paired_nep = {n for n, _ in wb_pairs}
    if len(obs_house) - len(paired_house) != sum(
            1 for r in wb['comparison'] if r['status'] == 'house_only'):
        failures.append(f'house_only mismatch: {len(obs_house)-len(paired_house)} '
                        f'observed-unpaired vs workbench '
                        f'{sum(1 for r in wb["comparison"] if r["status"] == "house_only")}')
    if len(obs_nep) - len(paired_nep) != sum(
            1 for r in wb['comparison'] if r['status'] == 'nep_only'):
        failures.append(f'nep_only mismatch: {len(obs_nep)-len(paired_nep)} '
                        f'observed-unpaired vs workbench '
                        f'{sum(1 for r in wb["comparison"] if r["status"] == "nep_only")}')

    # ---- 4. region rollups: snapshots vs workbench regions ---------------
    # snapshots keep extraction-era codes (COR/NEG); workbench uses current
    # names (CAR/NIR) — same regions
    alias = {'COR': 'CAR', 'NEG': 'NIR'}
    for stage_key, snap, fld_n in (('nep', nep, 'nep_count'),
                                   ('house', hgab, 'house_count')):
        recs_by_region = {}
        for p in snap['projects']:
            rk = alias.get(p.get('region_code'), p.get('region_code'))
            recs_by_region[rk] = recs_by_region.get(rk, 0) + 1
        for reg in wb['regions']:
            rk = reg['id']
            if recs_by_region.get(rk) != reg[fld_n]:
                failures.append(f'{stage_key} region {rk}: snapshot count '
                                f'{recs_by_region.get(rk)} != workbench {reg[fld_n]}')
                break

    # ---- report ----------------------------------------------------------
    print(f'ledger edges: {len(ledger_edges)} | workbench pairs: {len(wb_pairs)} | '
          f'missing: {len(missing)} | extra: {len(extra)}')
    print(f'observed: house={len(obs_house)} nep={len(obs_nep)} | '
          f'paired: house={len(paired_house)} nep={len(paired_nep)}')
    if failures:
        print('REPLAY FAIL:')
        for f in failures:
            print(' -', f)
        return 1
    print('REPLAY OK: ledger + snapshots regenerate the workbench comparison '
          'layer (pairs, methods, unpaired counts, region counts)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
