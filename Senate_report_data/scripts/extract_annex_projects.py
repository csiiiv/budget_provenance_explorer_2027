#!/usr/bin/env python3
"""Extract Senate Annex A-1 (DA FMR) and A-3 (NIA operations) from the
born-digital PDFs into model snapshots.

Adapted from bettergovph/ai-budget scripts/senate-cr/parse_two_col.py (MIT):
same column geometry (per-kind rev_x/amt_x/rights), same heading/level
heuristics, same NIA activity-first-line rule — wrapped in our snapshot
envelope with per-row provenance (pdf page) and coordinate lines split out.

Both annexes print, per project: the House bill description, the committee
report (Senate) description, and five amounts (gab / inc / dec / net / sv)
in pesos. Corrections print as a cut row (sv=0) followed by an insertion
row (gab empty) — the removal+insertion pattern the replacement linker
resolves downstream.

Usage: extract_annex_projects.py fmr|nia
Output: Senate_report_data/data/derived/senate_annex_a{1,3}_{fmr,nia}.json
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
PDFS = {
    'fmr': ROOT / 'Senate_report_data' / 'data' / 'senate_pdf' /
           'Annex A-1 DA Farm-to-Market Roads.pdf',
    'nia': ROOT / 'Senate_report_data' / 'data' / 'senate_pdf' /
           "Annex A-3 BSGC-OEOs-NIA-Details of NIA's Operations Budget.pdf",
}
ANNEX = {'fmr': 'a1', 'nia': 'a3'}
OUT = {k: ROOT / 'Senate_report_data' / 'data' / 'derived' /
          f'senate_annex_{v}_{k}.json' for k, v in ANNEX.items()}

COLS = ("gab", "inc", "dec", "net", "sv")
CONF = {
    "fmr": {"rev_x": 262, "amt_x": 530,
            "rights": {"gab": 598, "inc": 677, "dec": 761, "net": 841, "sv": 921}},
    "nia": {"rev_x": 278, "amt_x": 548,
            "rights": {"gab": 621, "inc": 695, "dec": 771, "net": 848, "sv": 920}},
}
COORD = re.compile(r"^(START|END)\s*:", re.I)
NIA_HEAD = re.compile(
    r"(Sub-Program$|^Improvement of Service Roads in (National|Communal) Irrigation Systems$|"
    r"^(Repair|Restoration) of (National|Communal|Pump) Irrigation Systems$|^Climate Change Adaptation Works|"
    r"^Establishment of Pump Irrigation Projects$|^Rehabilitation and Protection of Watershed Management$|"
    r"^Extension/Expansion of Existing (National|Communal) Irrigation Systems$|"
    r"Program$|Projects$)")


def amount(tok):
    t = tok.strip()
    if t in ("-", "–", "—"):
        return 0
    if not re.match(r"^\(?-?[\d,]+(\.\d+)?\)?$", t) or not re.search(r"\d", t):
        return None
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(",", "")
    v = float(t)
    v = -v if neg else v
    return int(v) if v.is_integer() else v


def visual_lines(words, tol=3.0):
    lines = []
    for w in sorted(words, key=lambda w: (w['top'], w['x0'])):
        for ln in lines[-3:]:
            if abs(ln['top'] - w['top']) <= tol:
                ln['words'].append(w)
                break
        else:
            lines.append({'top': w['top'], 'words': [w]})
    for ln in lines:
        ln['words'].sort(key=lambda w: w['x0'])
    return lines


def page_words(page, splits, gap=0.8):
    ws = page.extract_words(keep_blank_chars=False, use_text_flow=False,
                            x_tolerance=1.5)
    out = []
    for ln in visual_lines(ws):
        for w in ln['words']:
            if out and -1.5 < w['x0'] - out[-1]['x1'] < gap \
                    and not any(out[-1]['x0'] < x <= w['x0'] + 1 for x in splits):
                p = out[-1]
                p['text'] += w['text']
                p['x1'] = w['x1']
                continue
            out.append(dict(w))
    return out


def is_heading(kind, hb, rev):
    t = hb or rev
    letters = re.sub(r"[^A-Za-z]", "", t)
    caps = bool(letters) and letters.upper() == letters
    if kind == "fmr":
        return caps
    return caps or (bool(NIA_HEAD.search(hb or "")) and not rev) or t.startswith("GRAND TOTAL")


def heading_level(kind, name):
    n = name.upper()
    if n.startswith("GRAND TOTAL"):
        return 0
    if kind == "fmr":
        return 1 if n.startswith(("REGION", "NATIONAL CAPITAL", "CORDILLERA", "BANGSAMORO",
                                  "NEGROS ISLAND", "MIMAROPA", "CALABARZON", "CARAGA")) else 0
    if "PROGRAM" in n and "SUB-PROGRAM" not in n:
        return 1
    if "SUB-PROGRAM" in n:
        return 2
    if name != n:
        return 3
    if n.startswith(("REGION", "CORDILLERA", "NATIONAL CAPITAL", "BANGSAMORO", "NEGROS ISLAND",
                     "MIMAROPA", "CALABARZON", "CARAGA")) or n in ("MARIIS", "UPRIIS"):
        return 4
    return 5


def join(lines):
    return re.sub(r"Sub- Program", "Sub-Program",
                  re.sub(r"\s+", " ", " ".join(lines))).strip()


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main(kind: str) -> int:
    cf = CONF[kind]
    pdf = pdfplumber.open(PDFS[kind])
    items = []
    for pi, page in enumerate(pdf.pages):
        words = page_words(page, splits=(cf['rev_x'], cf['amt_x']))
        if any(w['text'] == 'A-3B.' for w in words[:40]):
            break  # Annex A-3B watershed list: a different table, not ours
        hdr = [w for w in words if w['text'] in ('Description', '(Amount)')]
        top = max((w['bottom'] for w in hdr), default=0)
        body = [w for w in words if w['top'] > top + 2 and w['text'] != 'Page']
        body = [w for w in body if not (w['top'] > page.height - 45)]
        for ln in visual_lines(body):
            hb, rev, amts = [], [], {}
            for w in ln['words']:
                if w['x0'] >= cf['amt_x']:
                    a = amount(w['text'])
                    if a is not None:
                        amts[min(COLS, key=lambda k: abs(cf['rights'][k] - w['x1']))] = a
                        continue
                (rev if w['x0'] >= cf['rev_x'] else hb).append(w)
            hbt = " ".join(w['text'] for w in hb)
            rvt = " ".join(w['text'] for w in rev)
            if amts and not hbt and not rvt and all(not v for v in amts.values()):
                continue
            if amts:
                items.append({'pdf_page': pi + 1, 'hb': [hbt] if hbt else [],
                              'rev': [rvt] if rvt else [],
                              **{k: amts.get(k) for k in COLS}})
            elif items and (hbt or rvt):
                if hbt:
                    items[-1]['hb'].append(hbt)
                if rvt:
                    items[-1]['rev'].append(rvt)
            elif hbt or rvt:
                items.append({'pdf_page': pi + 1, 'hb': [hbt] if hbt else [],
                              'rev': [rvt] if rvt else [], '_pending': True,
                              **{k: None for k in COLS}})
    merged = []
    for it in items:
        if merged and merged[-1].get('_pending') and not (it['hb'] and it['rev']):
            p = merged.pop()
            it = {**it, 'hb': p['hb'] + it['hb'], 'rev': p['rev'] + it['rev']}
        merged.append(it)
    if kind == 'nia':
        for i, it in enumerate(merged[:-1]):
            nxt = merged[i + 1]
            hb, nhb, nrv = join(it['hb']), join(nxt['hb']), join(nxt['rev'])
            if hb and not it['rev'] and not is_heading(kind, hb, "") and (
                    is_heading(kind, nhb, nrv) and heading_level(kind, nhb or nrv) == 4
                    and all(it[k] == nxt[k] for k in ('gab', 'sv'))
                    or nhb == hb and nrv and all(it[k] == nxt[k] for k in ('gab', 'sv'))):
                it['_activity'] = True

    out, path = [], []
    for idx, it in enumerate(merged):
        hb = join([l for l in it['hb'] if not COORD.match(l)])
        rev = join([l for l in it['rev'] if not COORD.match(l)])
        rec = {'id': f'senate_{ANNEX[kind]}:p{it["pdf_page"]}:r{idx}',
               'pdf_page': it['pdf_page'], 'row_index': idx,
               'hb_title': hb, 'senate_title': rev,
               'hb_coords': [l for l in it['hb'] if COORD.match(l)],
               'senate_coords': [l for l in it['rev'] if COORD.match(l)],
               **{k: it[k] for k in COLS}}
        if it.get('_activity') or is_heading(kind, hb, rev):
            rec['kind'] = 'heading'
            name = hb or rev
            level = 3 if it.get('_activity') else heading_level(kind, name)
            path = (path + [''] * level)[:level] + [name]
            rec['path'] = [p for p in path[:-1] if p]
            rec['level'] = level
        else:
            rec['kind'] = 'project'
            rec['path'] = [p for p in path if p]
        out.append(rec)

    projects = [r for r in out if r['kind'] == 'project']
    doc = {
        'schema_version': 1,
        'program': kind,
        'role': 'senate_committee_report_annex',
        'label': f'Senate CR Annex {ANNEX[kind].upper()} — '
                 + ('DA farm-to-market roads' if kind == 'fmr'
                    else "NIA operations budget") + ' (FY2027)',
        'note': 'Independent extraction from the born-digital PDF; adapted '
                'from bettergovph/ai-budget parse_two_col.py (MIT), same '
                'column geometry, plus per-row ids and coordinate split.',
        'metadata': {
            'source_pdf': str(PDFS[kind].relative_to(ROOT)),
            'source_pdf_sha256': sha256(PDFS[kind]),
            'pdf_pages_read': out[-1]['pdf_page'] if out else 0,
            'extractor': 'Senate_report_data/scripts/extract_annex_projects.py',
            'borrowed_from': 'bettergovph/ai-budget@main scripts/senate-cr/parse_two_col.py',
        },
        'summary': {
            'rows': len(out),
            'projects': len(projects),
            'cut_to_zero': sum(1 for p in projects
                               if (p['gab'] or 0) > 0 and (p['sv'] or 0) == 0),
            'insertions': sum(1 for p in projects if not p['gab']),
            'renamed': sum(1 for p in projects if p['senate_title']),
            'gab_total_php': sum(p['gab'] or 0 for p in projects),
            'sv_total_php': sum(p['sv'] or 0 for p in projects),
        },
        'rows': out,
    }
    OUT[kind].parent.mkdir(parents=True, exist_ok=True)
    OUT[kind].write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n')
    print(f'{OUT[kind].name}: {doc["summary"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
