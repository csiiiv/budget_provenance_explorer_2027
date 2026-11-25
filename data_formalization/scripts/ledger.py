#!/usr/bin/env python3
"""Append-only per-line-item ledger for the data-formalization model (§6 of
docs/DATA_MODEL.md).

Storage: data_formalization/data/ledger/<domain>.jsonl — one JSON record per
line, append-only. Records carry a per-subject `seq`; there is no global
ordering. Current truth for a subject = fold(records in seq order).

Record types: line.observed · match.asserted · match.retracted ·
validation.finding · validation.run · review.requested · review.resolved ·
defect.repair · deliverable.published

Commands:
  append       --domain fmr --subject S --type T --actor A --payload JSON
               [--provenance JSON] [--supersedes N]
  fold         --domain fmr --subject S        # current state
  timeline     --domain fmr --subject S        # all records
  open-reviews --domain fmr
  verify       --domain fmr                    # seq monotonic, valid JSON

Guardrails: refuses non-monotonic seq per subject, refuses to append to a
file that fails to parse (append-only enforcement), never rewrites lines.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER_DIR = ROOT / 'data' / 'ledger'

_TYPES = {'line.observed', 'match.asserted', 'match.retracted',
          'validation.finding', 'validation.run', 'review.requested',
          'review.resolved', 'defect.repair', 'deliverable.published'}

# in-process seq cache so batch appends stay O(1) per record
_seq_cache: dict[tuple[str, str], int] = {}
_cache_loaded_domains: set[str] = set()


def ledger_path(domain: str) -> Path:
    return LEDGER_DIR / f'{domain}.jsonl'


def load(domain: str) -> list[dict]:
    p = ledger_path(domain)
    if not p.exists():
        return []
    recs = []
    for i, line in enumerate(p.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            recs.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f'ledger corrupt at {p.name}:{i}: {e} '
                             f'(refusing to proceed — append-only file was modified)')
    return recs


def next_seq(recs: list[dict], subject: str) -> int:
    seqs = [r['seq'] for r in recs if r['subject'] == subject]
    return (max(seqs) + 1) if seqs else 1


def append(domain: str, subject: str, rtype: str, actor: str,
           payload: dict, provenance: dict | None = None,
           supersedes: int | None = None) -> dict:
    if rtype not in _TYPES:
        raise SystemExit(f'unknown record type {rtype!r}; one of {sorted(_TYPES)}')
    if domain not in _cache_loaded_domains:
        for r in load(domain):
            key = (domain, r['subject'])
            if r['seq'] > _seq_cache.get(key, 0):
                _seq_cache[key] = r['seq']
        _cache_loaded_domains.add(domain)
    ledger_path(domain).parent.mkdir(parents=True, exist_ok=True)
    rec = {
        'seq': _seq_cache.get((domain, subject), 0) + 1,
        'ts': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'subject': subject,
        'type': rtype,
        'actor': actor,
        'payload': payload,
    }
    if provenance:
        rec['provenance'] = provenance
    if supersedes is not None:
        rec['supersedes'] = supersedes
    with open(ledger_path(domain), 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
    _seq_cache[(domain, subject)] = rec['seq']
    return rec


def fold_subject(recs: list[dict], subject: str) -> dict:
    """Current truth: apply the subject's records in seq order."""
    state = {'subject': subject, 'observed': None, 'matches': {},
             'findings': {}, 'review': None, 'repairs': [], 'published': []}
    for r in sorted((r for r in recs if r['subject'] == subject),
                    key=lambda r: r['seq']):
        t, p = r['type'], r.get('payload', {})
        sup = r.get('supersedes')
        if t == 'line.observed':
            state['observed'] = {**p, '_seq': r['seq']}
        elif t == 'match.asserted':
            if sup is not None:
                state['matches'] = {k: v for k, v in state['matches'].items()
                                    if v['_seq'] != sup}
            state['matches'][p['to']] = {**p, '_seq': r['seq'],
                                         '_method': p.get('method')}
        elif t == 'match.retracted':
            state['matches'].pop(p.get('to'), None)
            if sup is not None:
                state['matches'] = {k: v for k, v in state['matches'].items()
                                    if v['_seq'] != sup}
        elif t in ('validation.finding', 'validation.run'):
            # last write wins per check key; supersedes drops the prior record
            if sup is not None:
                state['findings'].pop(p.get('check'), None)
            state['findings'][p.get('check', t)] = {**p, '_seq': r['seq'], '_type': t}
        elif t == 'review.requested':
            state['review'] = {'status': 'open', '_seq': r['seq'], **p}
        elif t == 'review.resolved':
            state['review'] = {'status': 'resolved', '_seq': r['seq'], **p}
        elif t == 'defect.repair':
            state['repairs'].append({**p, '_seq': r['seq']})
        elif t == 'deliverable.published':
            state['published'].append({**p, '_seq': r['seq']})
    return state


def open_reviews(recs: list[dict]) -> list[dict]:
    open_ids = set()
    for r in sorted(recs, key=lambda r: (r['subject'], r['seq'])):
        if r['type'] == 'review.requested':
            open_ids.add(r['subject'])
        elif r['type'] == 'review.resolved':
            open_ids.discard(r['subject'])
    return sorted(open_ids)


def verify(domain: str) -> str:
    recs = load(domain)
    last: dict[str, int] = {}
    for r in recs:
        s = r['subject']
        if r['seq'] <= last.get(s, 0):
            return (f'FAIL {domain}: subject {s} seq {r["seq"]} not monotonic '
                    f'(previous {last.get(s)})')
        last[s] = r['seq']
    return f'OK {domain}: {len(recs)} records, {len(last)} subjects, seq monotonic'


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    a = sub.add_parser('append')
    for name, req in [('domain', True), ('subject', True), ('type', True),
                      ('actor', True), ('payload', True)]:
        a.add_argument(f'--{name}', required=req)
    a.add_argument('--provenance')
    a.add_argument('--supersedes', type=int)

    f = sub.add_parser('fold'); f.add_argument('--domain', required=True)
    f.add_argument('--subject', required=True)
    t = sub.add_parser('timeline'); t.add_argument('--domain', required=True)
    t.add_argument('--subject', required=True)
    o = sub.add_parser('open-reviews'); o.add_argument('--domain', required=True)
    v = sub.add_parser('verify'); v.add_argument('--domain', required=True)

    args = ap.parse_args()
    if args.cmd == 'append':
        rec = append(args.domain, args.subject, args.type, args.actor,
                     json.loads(args.payload),
                     json.loads(args.provenance) if args.provenance else None,
                     args.supersedes)
        print(json.dumps(rec, indent=1))
    elif args.cmd == 'fold':
        print(json.dumps(fold_subject(load(args.domain), args.subject), indent=1))
    elif args.cmd == 'timeline':
        for r in load(args.domain):
            if r['subject'] == args.subject:
                print(json.dumps(r, ensure_ascii=False))
    elif args.cmd == 'open-reviews':
        for s in open_reviews(load(args.domain)):
            print(s)
    elif args.cmd == 'verify':
        print(verify(args.domain))


if __name__ == '__main__':
    main()
