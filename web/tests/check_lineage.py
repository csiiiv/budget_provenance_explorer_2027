"""Read-only lineage audit for a deliberately partial standalone checkout.

Known omitted inputs are reported, not silently considered verified.
All present artifacts are hashed against the original registry; no hashes
are updated by this audit. Unexpected omissions and mismatches fail the job.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
FORMAL = ROOT / 'data_formalization'
OMITTED = {
    'source/fmr/hgab_vol_ib_pdf',
    'import/senate_bettergov_2027',
    'snapshot/dpwh/stage_trace',
    'snapshot/dpwh/comparison_projects',
    'import/dpwh_hgab_review_set',
    'source/dpwh/hb_ic_3rd_reading_pdf',
    'snapshot/dpwh/hb_ic_3rd_reading_tree',
}


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict', action='store_true', help='also fail on intentionally omitted inputs')
    args = parser.parse_args()
    nodes = json.loads((FORMAL / 'data/registry.json').read_text())['nodes']
    issues = []
    omitted = []
    verified = 0
    active, done = set(), set()

    def visit(node):
        if node in active:
            issues.append(f'Cycle at {node}')
            return
        if node in done:
            return
        active.add(node)
        for parent in nodes[node]['inputs']:
            if parent not in nodes:
                issues.append(f'{node}: unregistered input {parent}')
            else:
                visit(parent)
        active.remove(node)
        done.add(node)

    for node, record in nodes.items():
        visit(node)
        path = ROOT / record['path']
        if not path.is_file():
            msg = f"{node}: missing {record['path']}"
            if node in OMITTED and not args.strict:
                omitted.append(msg)
            else:
                issues.append(msg)
            continue
        actual = sha256(path)
        if actual != record['content_sha256']:
            issues.append(f"{node}: SHA256 mismatch\n  recorded {record['content_sha256']}\n  actual   {actual}")
        else:
            verified += 1
    for msg in omitted:
        print('OMITTED (standalone checkout):', msg)
    for msg in issues:
        print('ERROR:', msg)
    print(f'{verified} verified; {len(omitted)} intentionally omitted; {len(issues)} issues')
    return bool(issues)


if __name__ == '__main__':
    sys.exit(main())
