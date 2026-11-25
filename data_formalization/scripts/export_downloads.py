"""Static download exports for the provenance explorers.

Each program exporter writes a self-describing file set under
web/public/data/export/<program>/:

  chains-simple.csv  one row per chain — the explorer table view
  chains-full.csv    wide CSV — every scalar field, stage-prefixed
  findings.csv       one row per review finding (when the program has any)
  rollups.csv        the annex's printed heading subtotals with leaf sums
  full.json          verbatim chain records + manifest (inputs, totals)
  SHA256SUMS.txt     hashes of every file above

Conventions: amounts are integer pesos (missing = empty cell, explicit
zero = 0), ids and locators stay as printed, and the files are
deterministic given the same inputs so they reconcile with the bundles.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


def csv_field(value):
    """Flatten a value into a CSV cell."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return value


def write_csv(path: Path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    with path.open('w', newline='', encoding='utf-8') as out:
        writer = csv.writer(out)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([csv_field(row.get(col)) for col in columns])
    return len(rows)


def write_summaries(dir_path: Path, files: dict):
    """files: name -> row/record count, for the manifest."""
    manifest = {'files': {name: {'rows': count} for name, count in files.items()}}
    return manifest


def write_sums(dir_path: Path, names):
    lines = []
    for name in names:
        digest = hashlib.sha256((dir_path / name).read_bytes()).hexdigest()
        lines.append(f'{digest}  {name}')
    (dir_path / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def pesos(millions):
    """Bundle millions -> integer pesos (None-safe)."""
    return None if millions is None else round(millions * 1_000_000)
