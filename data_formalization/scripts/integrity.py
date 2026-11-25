#!/usr/bin/env python3
"""Cross-ledger integrity validation (§6 guards, run before any commit).

Checks per domain ledger:
  1. seq monotonic per subject (ledger.verify already does this)
  2. schema: every record has seq/ts/subject/type/actor; known types only
  3. dangling match edges: match.asserted.to / review payloads referencing
     subjects that were never observed in ANY domain ledger
  4. duplicate records: same (subject, type, payload-signature) appearing
     twice (backfill double-append detection)
  5. snapshot references: provenance.snapshot must be a registered lineage
     node (or import:* which is registered separately)

Findings are printed and, unless --no-write, appended to the domain ledger
as validation.run records (check name: integrity-<domain>), actor: verify.

Run:  python3 data_formalization/scripts/integrity.py [--no-write]
Exit non-zero if blocking problems found.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ledger as L   # noqa: E402
import lineage as G  # noqa: E402

DOMAINS = ('fmr', 'hfep', 'nia', 'dpwh')
KNOWN_TYPES = {'line.observed', 'match.asserted', 'match.retracted',
               'validation.finding', 'validation.run', 'review.requested',
               'review.resolved', 'defect.repair', 'deliverable.published'}


def load(domain: str) -> list[dict]:
    p = L.ledger_path(domain)
    if not p.exists():
        return []
    return [json.loads(l) for l in open(p, encoding='utf-8')]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-write', action='store_true',
                    help='report only; do not append validation.run records')
    args = ap.parse_args()

    reg = G.load_registry()
    all_subjects = set()
    per_domain: dict[str, list[dict]] = {}
    for dom in DOMAINS:
        recs = load(dom)
        per_domain[dom] = recs
        all_subjects |= {r['subject'] for r in recs}

    report: dict[str, list[str]] = {}
    any_blocking = False

    for dom in DOMAINS:
        recs = per_domain[dom]
        problems: list[str] = []

        # 1+2. seq monotonic & schema
        last: dict[str, int] = {}
        for i, r in enumerate(recs, 1):
            for f in ('seq', 'ts', 'subject', 'type', 'actor'):
                if f not in r:
                    problems.append(f'record {i}: missing field {f}')
            if r.get('type') not in KNOWN_TYPES:
                problems.append(f'record {i}: unknown type {r.get("type")!r}')
            s = r.get('subject', '?')
            if r.get('seq', 0) <= last.get(s, 0):
                problems.append(f'record {i}: seq {r.get("seq")} not monotonic '
                                f'for {s} (prev {last.get(s)})')
            last[s] = r.get('seq', 0)

        # 3. dangling match edges
        for r in recs:
            if r['type'] == 'match.asserted':
                to = r['payload'].get('to')
                if to and to not in all_subjects:
                    problems.append(f'dangling edge @{r["subject"]}#{r["seq"]}: '
                                    f'to={to} never observed')

        # 4. duplicate signatures (same subject+type+key payload fields)
        seen_sigs: dict[tuple, int] = {}
        for r in recs:
            if r['type'] == 'line.observed':
                sig = (r['subject'], r['type'],
                       (r.get('provenance') or {}).get('snapshot'))
            elif r['type'] == 'match.asserted':
                sig = (r['subject'], r['type'], r['payload'].get('to'))
            else:
                continue  # findings/reviews legitimately repeat per check
            if sig in seen_sigs:
                problems.append(f'duplicate {r["type"]} for {r["subject"]} '
                                f'(snapshot/to={sig[2]}) at seq {r["seq"]} '
                                f'and {seen_sigs[sig]}')
            seen_sigs[sig] = r['seq']

        # 5. snapshot references registered
        for r in recs:
            snap = (r.get('provenance') or {}).get('snapshot')
            if snap and snap not in reg['nodes']:
                problems.append(f'unregistered snapshot ref {snap!r} '
                                f'@{r["subject"]}#{r["seq"]}')

        report[dom] = problems
        blocking = [p for p in problems if not p.startswith('unregistered')]
        any_blocking = any_blocking or bool(blocking)
        status = 'OK' if not problems else f'{len(problems)} problems'
        print(f'{dom}: {len(recs)} records — {status}')
        for p in problems[:10]:
            print(f'  - {p}')
        if len(problems) > 10:
            print(f'  ... and {len(problems)-10} more')

        if not args.no_write:
            L.append(dom, 'integrity/run', 'validation.run', 'verify',
                     {'check': f'integrity-{dom}',
                      'result': 'pass' if not problems else 'fail',
                      'records_checked': len(recs),
                      'problems': problems[:20]},
                     {'source': 'data_formalization/scripts/integrity.py',
                      'ran_at': time.strftime('%Y-%m-%dT%H:%M:%S%z')})

    print('\nRESULT:', 'FAIL' if any_blocking else 'ALL CLEAN'
          if all(not v for v in report.values()) else 'ADVISORY ONLY')
    return 1 if any_blocking else 0


if __name__ == '__main__':
    sys.exit(main())
