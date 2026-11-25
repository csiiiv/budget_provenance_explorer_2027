#!/usr/bin/env python3
"""Lineage registry for the data-formalization model (§5, §10 of
docs/DATA_MODEL.md).

Nodes are content-addressed artifacts (source docs, snapshots, transitions,
validations, views, imports, deliverables) described by manifests under
data_formalization/data/nodes/, indexed by data_formalization/data/registry.json.

Commands:
  register   --node ID --type T --path P [--input ID ...] [--builder ...]
              [--meta JSON]        # idempotent if sha unchanged, refuses drift
  list       [--type T]
  verify     [--node ID]           # recompute content sha; check inputs exist
  stale      [--node ID]           # nodes whose inputs' content changed on disk
  graph                          # mermaid of the registered DAG
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # data_formalization/
REPO = ROOT.parent                                  # workspace root
NODES_DIR = ROOT / 'data' / 'nodes'
REGISTRY = ROOT / 'data' / 'registry.json'

NODE_TYPES = {'source_doc', 'snapshot', 'transition', 'validation', 'view',
              'reference', 'deliverable', 'import'}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_registry() -> dict:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text())
    return {'nodes': {}}


def save_registry(reg: dict) -> None:
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + '\n')


def manifest_path(node_id: str) -> Path:
    return NODES_DIR / f'{node_id}.manifest.json'


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (REPO / p)


def register(node_id: str, ntype: str, path: str, inputs: list[str],
             builder: str | None = None, meta: dict | None = None) -> dict:
    if ntype not in NODE_TYPES:
        raise SystemExit(f'unknown node type {ntype!r}; one of {sorted(NODE_TYPES)}')
    p = resolve(path)
    if not p.exists():
        raise SystemExit(f'content path not found: {p}')
    digest = sha256(p)
    reg = load_registry()
    if node_id in reg['nodes']:
        if reg['nodes'][node_id]['content_sha256'] == digest:
            return json.loads(manifest_path(node_id).read_text())  # idempotent
        raise SystemExit(f'node {node_id} already registered with different '
                         f'content; deliberate re-registration requires editing '
                         f'the registry by hand')
    manifest = {
        'node': node_id,
        'type': ntype,
        'path': str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p),
        'content_sha256': digest,
        'built_by': builder or 'unknown',
        'inputs': inputs,
        'registered': datetime.datetime.now().isoformat(timespec='seconds'),
    }
    if meta:
        manifest['meta'] = meta
    NODES_DIR.mkdir(parents=True, exist_ok=True)
    mp = manifest_path(node_id)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False) + '\n')
    reg['nodes'][node_id] = {
        'type': ntype, 'path': manifest['path'],
        'content_sha256': digest,
        'inputs': inputs, 'manifest': str(manifest_path(node_id).relative_to(ROOT))}
    save_registry(reg)
    return manifest


def verify(node_id: str | None) -> list[str]:
    reg = load_registry()
    problems = []
    for nid in ([node_id] if node_id else list(reg['nodes'])):
        info = reg['nodes'][nid]
        p = resolve(info['path'])
        if not p.exists():
            problems.append(f'{nid}: content missing ({p})')
            continue
        if sha256(p) != info['content_sha256']:
            problems.append(f'{nid}: content sha256 MISMATCH (file changed on disk)')
        for dep in info['inputs']:
            if dep not in reg['nodes']:
                problems.append(f'{nid}: input {dep} not registered')
    return problems


def stale(node_id: str | None) -> list[str]:
    reg = load_registry()
    out = []
    for nid in ([node_id] if node_id else list(reg['nodes'])):
        for dep in reg['nodes'][nid]['inputs']:
            dinfo = reg['nodes'].get(dep)
            if not dinfo:
                continue
            dp = resolve(dinfo['path'])
            if dp.exists() and sha256(dp) != dinfo['content_sha256']:
                out.append(f'{nid} <- {dep} (input content changed on disk)')
    return out


def graph() -> str:
    reg = load_registry()
    safe = lambda s: ''.join(c if c.isalnum() else '_' for c in s)
    lines = ['graph TD']
    for nid, info in reg['nodes'].items():
        lines.append(f'    {safe(nid)}["{nid}<br/>{info["type"]}"]')
    for nid, info in reg['nodes'].items():
        for dep in info['inputs']:
            lines.append(f'    {safe(dep)} --> {safe(nid)}')
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    r = sub.add_parser('register')
    r.add_argument('--node', required=True)
    r.add_argument('--type', required=True)
    r.add_argument('--path', required=True)
    r.add_argument('--input', action='append', default=[])
    r.add_argument('--builder')
    r.add_argument('--meta')

    l = sub.add_parser('list'); l.add_argument('--type')
    v = sub.add_parser('verify'); v.add_argument('--node')
    s = sub.add_parser('stale'); s.add_argument('--node')
    sub.add_parser('graph')

    args = ap.parse_args()
    if args.cmd == 'register':
        m = register(args.node, args.type, args.path, args.input, args.builder,
                     json.loads(args.meta) if args.meta else None)
        print(json.dumps(m, indent=1))
    elif args.cmd == 'list':
        reg = load_registry()
        for nid, info in sorted(reg['nodes'].items()):
            if args.type and info['type'] != args.type:
                continue
            print(f'{nid:40s} {info["type"]:12s} sha={info["content_sha256"][:12]} '
                  f'inputs={info["inputs"]}')
    elif args.cmd == 'verify':
        problems = verify(args.node)
        print('\n'.join(problems) if problems else 'OK: all nodes verify')
        sys.exit(1 if problems else 0)
    elif args.cmd == 'stale':
        out = stale(args.node)
        print('\n'.join(out) if out else 'OK: nothing stale')
    elif args.cmd == 'graph':
        print(graph())


if __name__ == '__main__':
    main()
