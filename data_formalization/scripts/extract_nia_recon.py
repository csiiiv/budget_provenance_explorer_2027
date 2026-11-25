#!/usr/bin/env python3
"""Extract NIA agency-side NEP↔HGAB reconciliation workbooks into JSON
snapshots (one per vintage), for registration as
snapshot/nia/agency_recon_{oct10,nov13}.

Leaf grain: col G title with numeric NEP (H) and HGAB (I) values, formulas
resolved from the workbook's cached results (data_only). Sub-total and
header rows (formulas or blanks) are skipped; their structure lives in the
workbook itself.

Output: analysis-nia/data/nia_agency_recon_{oct10,nov13}.json
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'analysis-nia' / 'data'

VINTAGES = [
    ('oct10', 'NIA_DATA/NIA%20FY%202027%20NEP%20OCTOBER%2010%201043PM.xlsx',
     'FY 2027 NEP October 10 1043PM'),
    ('nov13', 'NIA_DATA/NIA_NEP_2026-11-13.xlsx', 'NIA NEP 2026-11-13'),
]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def norm_title(t: str) -> str:
    return re.sub(r'[^a-z0-9]', '', str(t).lower())[:80]


def extract(vintage: str, rel: str, label: str) -> dict:
    src = ROOT / rel
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    ws = wb['DETAILS 2027']
    leaves = []
    for excel_row, row in enumerate(ws.iter_rows(min_row=1, values_only=True), 1):
        g = row[6] if len(row) > 6 else None
        h = row[7] if len(row) > 7 else None
        i = row[8] if len(row) > 8 else None
        if g and isinstance(h, (int, float)) and isinstance(i, (int, float)):
            leaves.append({
                'id': f'nia_agency_{vintage}:r{len(leaves) + 1}',
                'excel_row': excel_row,
                'title': str(g).strip(),
                'title_key': norm_title(g),
                'nep_amount_php': int(h),
                'hgab_amount_php': int(i),
            })
    wb.close()
    for k, leaf in enumerate(leaves, 1):
        leaf['leaf_index'] = k
    return {
        'schema_version': 1,
        'program': 'nia',
        'role': 'agency_working_reconciliation',
        'label': f'NIA agency NEP↔HGAB reconciliation ({label})',
        'note': 'Agency-side FROM(NEP)→TO(HGAB) per leaf; formulas resolved '
                'from cached values. Sub-total rows skipped.',
        'metadata': {
            'source_xlsx': rel,
            'source_xlsx_sha256': sha256(src),
            'source_sheet': 'DETAILS 2027',
            'extractor': 'data_formalization/scripts/extract_nia_recon.py',
        },
        'summary': {
            'leaves': len(leaves),
            'identical': sum(1 for x in leaves
                             if x['nep_amount_php'] == x['hgab_amount_php']),
            'changed_nonzero': sum(1 for x in leaves
                                   if x['nep_amount_php'] != x['hgab_amount_php']
                                   and x['hgab_amount_php'] != 0),
            'cut_to_zero': sum(1 for x in leaves
                               if x['hgab_amount_php'] == 0
                               and x['nep_amount_php'] > 0),
        },
        'leaves': leaves,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for vintage, rel, label in VINTAGES:
        d = extract(vintage, rel, label)
        out = OUT / f'nia_agency_recon_{vintage}.json'
        out.write_text(json.dumps(d, indent=1, ensure_ascii=False) + '\n')
        print(f'{out.name}: {d["summary"]}')


if __name__ == '__main__':
    sys.exit(main())
