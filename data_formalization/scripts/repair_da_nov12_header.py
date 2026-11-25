#!/usr/bin/env python3
"""Close the da_fmr:ctrl:Control No. defect loop (Path E, §7).

Upstream extractor fixed (mid-sheet banner guard) and nov12 re-extracted
(1032→1031 rows). This script propagates the repair through the model:

  1. re-register snapshot/fmr/da_draft_nov12 with the new content sha
     (deliberate drift: the registry refuses silent changes, so the old
     entry is removed and re-registered with a repair note)
  2. rebuild view/fmr/da_nov5_to_nov12_diff (added_controls 11→10) and
     re-register it likewise
  3. append the defect.repair record to the fmr ledger for subject
     da_fmr:ctrl:Control No.
  4. verify lineage + ledgers

Run:  python3 data_formalization/scripts/repair_da_nov12_header.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'data_formalization' / 'scripts'))
import ledger as L   # noqa: E402
import lineage as G  # noqa: E402

NOTE = ('re-registered 2026-11-22: extractor fix removed a mid-sheet banner '
        'row (excel row 34) that leaked in as control "Control No."; '
        'see fmr ledger defect.repair on da_fmr:ctrl:Control No.')


def reregister(node_id: str, ntype: str, path: str, inputs: list[str], builder: str):
    reg = G.load_registry()
    reg['nodes'].pop(node_id, None)
    G.save_registry(reg)
    G.manifest_path(node_id).unlink(missing_ok=True)
    m = G.register(node_id, ntype, path, inputs, builder, {'repair': NOTE})
    print(f're-registered {node_id}: sha={m["content_sha256"][:12]}')


def main() -> int:
    # 1. snapshot re-registration
    reregister('snapshot/fmr/da_draft_nov12', 'snapshot',
               'other-analysis/data/da_fmr_draft_nov12.json',
               ['source/fmr/da_xlsx_nov12'],
               'other-analysis extract_da_fmr.py (banner-row guard fix)')

    # 2. rebuild + re-register the diff view (added_controls 11 -> 10)
    FMR = ROOT / 'other-analysis' / 'data'
    nov5 = {p['control_no']: p for p in
            json.load(open(FMR / 'da_fmr_draft.json'))['projects']
            if p.get('control_no')}
    nov12 = {p['control_no']: p for p in
             json.load(open(FMR / 'da_fmr_draft_nov12.json'))['projects']
             if p.get('control_no')}
    diff = {
        'added_controls': sorted(nov12.keys() - nov5.keys()),
        'removed_controls': sorted(nov5.keys() - nov12.keys()),
        'disposition_changed': [
            {'control_no': c, 'from': nov5[c]['disposition'],
             'to': nov12[c]['disposition']}
            for c in sorted(nov5.keys() & nov12.keys())
            if nov5[c]['disposition'] != nov12[c]['disposition']],
        'from_amount_changed': [
            {'control_no': c, 'from': nov5[c]['from_amount_php'],
             'to': nov12[c]['from_amount_php']}
            for c in sorted(nov5.keys() & nov12.keys())
            if nov5[c]['from_amount_php'] != nov12[c]['from_amount_php']],
        'proposed_amount_changed': [
            {'control_no': c, 'from': nov5[c].get('proposed_amount_php'),
             'to': nov12[c].get('proposed_amount_php')}
            for c in sorted(nov5.keys() & nov12.keys())
            if nov5[c].get('proposed_amount_php') != nov12[c].get('proposed_amount_php')],
    }
    out = ROOT / 'data_formalization' / 'data' / 'transitions' / 'fmr' / \
        'da_nov5_to_nov12_diff.json'
    out.write_text(json.dumps({
        'schema_version': 2,
        'type': 'view',
        'compares': ['snapshot/fmr/da_draft_nov5',
                     'snapshot/fmr/da_draft_nov12'],
        'key': 'control_no',
        'summary': {k: len(v) for k, v in diff.items()},
        'diff': diff}, indent=1, ensure_ascii=False) + '\n')
    print('diff rebuilt:', {k: len(v) for k, v in diff.items()})
    reregister('view/fmr/da_nov5_to_nov12_diff', 'view',
               'data_formalization/data/transitions/fmr/da_nov5_to_nov12_diff.json',
               ['snapshot/fmr/da_draft_nov5', 'snapshot/fmr/da_draft_nov12',
                'transition/fmr/da_nov5_linkage'],
               'repair_da_nov12_header.py (post-fix rebuild)')

    # 3. defect.repair record (subject stays in history; repair closes it)
    L.append('fmr', 'da_fmr:ctrl:Control No.', 'defect.repair', 'pipeline',
             {'repair': 'upstream extractor fixed (mid-sheet banner guard); '
                        'nov12 re-extracted: 1032 -> 1031 rows, originals '
                        '705 -> 704; totals unchanged at PHP 16B',
              'code_change': 'other-analysis/extract_da_fmr.py '
                             '(original_rows expectation 705->704)',
              'evidence': ['fmr ledger validation.finding '
                           'spurious-header-row (seq 2)',
                           'view diff added_controls 11->10']},
             {'source': 'data_formalization/scripts/repair_da_nov12_header.py',
              'snapshot': 'snapshot/fmr/da_draft_nov12'})

    # 4. verify
    problems = G.verify(None)
    print('lineage:', 'FAIL\n' + '\n'.join(problems) if problems
          else 'lineage: OK: all nodes verify')
    print(L.verify('fmr'))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
