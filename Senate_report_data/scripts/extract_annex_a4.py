#!/usr/bin/env python3
"""Extract Senate Annex A-4 (DPWH changes to House Vol I-C) from the born-digital
PDF into a model snapshot (R1 of the Senate-DPWH re-derivation).

Adapted from bettergovph/ai-budget scripts/senate-cr/parse_annex_a4.py (MIT):
same column geometry (REV_X=326, AMT_X=545, PROJECT_X=104), same heading-stack
context, same FAP fund-row handling — wrapped in our snapshot envelope with
per-row provenance (pdf page, HB page citation, x0, top) and stripped
coordinate lines kept separately.

Output: Senate_report_data/data/derived/senate_annex_a4_dpwh.json
        (project rows plus heading rows with their printed subtotals —
        the annex's own roll-up evidence, per the provenance chaining guide)
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import re
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / 'Senate_report_data' / 'data' / 'senate_pdf' / \
    "Annex A-4 Details of DPWH's Programs-Projects (FY 2027 General Appropriations Bill Volume I-C).pdf"
OUT = ROOT / 'Senate_report_data' / 'data' / 'derived' / 'senate_annex_a4_dpwh.json'

COLS = ("gab", "inc", "dec", "net", "sv")
REV_X = 326
AMT_X = 545
PROJECT_X = 104
COORD = re.compile(r"^(Start|End)\s*:", re.I)
NUM_RE = re.compile(r"^\(?-?[\d,]+(\.\d+)?\)?$")


def amount(tok):
    t = tok.strip()
    if t in ("-", "–", "—"):
        return 0
    if not NUM_RE.match(t) or not re.search(r"\d", t):
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


def page_words(page, gap=0.8):
    ws = page.extract_words(keep_blank_chars=False, use_text_flow=False,
                            x_tolerance=1.5)
    out = []
    for ln in visual_lines(ws):
        for w in ln['words']:
            if out and -1.5 < w['x0'] - out[-1]['x1'] < gap \
                    and not (out[-1]['x0'] < REV_X <= w['x0'] + 1) \
                    and not (out[-1]['x0'] < AMT_X <= w['x0'] + 1):
                p = out[-1]
                p['text'] += w['text']
                p['x1'] = w['x1']
                continue
            out.append(dict(w))
    return out


def columns(words):
    hdr = {w['text']: w for w in words if w['top'] < 34}
    return {'gab': hdr['10858)']['x1'] + 7, 'inc': hdr['Increase']['x1'] + 18,
            'dec': hdr['Decrease']['x1'] + 23, 'net': hdr['Change']['x1'] + 13,
            'sv': hdr['REPORT)']['x1']}


def heading_kind(text, x0):
    t = text.lower()
    if re.search(r"(district engineering office|central office|regional office|engineering office|\boffice\b)", t):
        return 'office'
    if re.search(r"(\bregion\b|national capital region|cordillera|barmm|bangsamoro|mimaropa|calabarzon|caraga|\bncr\b|\bcar\b)", t):
        return 'region'
    return 'program'


def join(lines):
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def strip_coords(lines):
    return join([l for l in lines if not COORD.match(l)])


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    pdf = pdfplumber.open(PDF)
    items = []
    hb_page = None
    for pi, page in enumerate(pdf.pages):
        words = page_words(page)
        cols = columns(words)
        body = [w for w in words if w['top'] > 33]
        foot = [w for w in body if w['text'] == 'Page' and w['top'] > page.height - 40]
        if foot:
            body = [w for w in body if w['top'] < foot[0]['top'] - 2]
        for ln in visual_lines(body):
            pref = None
            hb, rev, amts = [], [], {}
            for w in ln['words']:
                if w['x1'] < 41 and re.match(r"^\d{1,4}$", w['text']):
                    pref = int(w['text'])
                    continue
                if w['x0'] >= AMT_X:
                    a = amount(w['text'])
                    if a is not None:
                        amts[min(COLS, key=lambda k: abs(cols[k] - w['x1']))] = a
                        continue
                (rev if w['x0'] >= REV_X else hb).append(w)
            if pref is not None:
                hb_page = pref
            if amts and not hb and items and all(not v for v in amts.values()):
                amts = {}
            if amts:
                x0 = (hb or rev)[0]['x0'] if (hb or rev) else None
                items.append({'pdf_page': pi + 1, 'hb_page': hb_page, 'x0': x0,
                              'top': ln['top'],
                              'hb': [" ".join(w['text'] for w in hb)] if hb else [],
                              'rev': [" ".join(w['text'] for w in rev)] if rev else [],
                              'hb_x0': hb[0]['x0'] if hb else None,
                              **{k: amts.get(k) for k in COLS}})
            elif items and (hb or rev):
                it = items[-1]
                if hb:
                    it['hb'].append(" ".join(w['text'] for w in hb))
                    if it['hb_x0'] is None:
                        it['hb_x0'] = hb[0]['x0']
                if rev:
                    it['rev'].append(" ".join(w['text'] for w in rev))

    FUND = ("GOP", "GOP Counterpart", "Loan Proceeds", "Grant Proceeds")
    for i, it in enumerate(items):
        it['fund_of'] = None
        if join(it['hb']) in FUND:
            j = i - 1
            while j >= 0 and join(items[j]['hb']) in FUND:
                j -= 1
            head = items[j]
            hx = head['hb_x0'] if head['hb_x0'] is not None else head['x0']
            if j >= 0 and hx is not None and hx < PROJECT_X and not re.search(r"office$", join(head['hb']), re.I):
                it['fund_of'] = j
                head['fap_project'] = True
            else:
                it['fund_total'] = True

    stack = []
    projects, headings = [], []
    for it in items:
        name = join(it['hb'])
        rev = join(it['rev'])
        x0 = it['hb_x0'] if it['hb_x0'] is not None else it['x0']
        is_project = (x0 is not None and x0 >= PROJECT_X or not it['hb']) \
            and it['fund_of'] is None and not it.get('fund_total') \
            or it.get('fap_project')
        if it.get('fund_total') or it['fund_of'] is not None:
            continue  # funds tracked in aggregate only
        if is_project:
            if it.get('fap_project'):
                name_clean = re.sub(r"^[a-z]\.\s*", "", name, flags=re.I)
                while stack and stack[-1]['x0'] >= x0 - 0.5:
                    stack.pop()
            else:
                name_clean = name
            projects.append({
                'id': f'senate_a4:p{it["pdf_page"]}:r{round(it["top"])}',
                'hb_page_cited': it['hb_page'],
                'pdf_page': it['pdf_page'],
                'office': next((s['name'] for s in reversed(stack) if s['kind'] == 'office'), None),
                'region': next((s['name'] for s in reversed(stack) if s['kind'] == 'region'), None),
                'program': next((s['name'] for s in reversed(stack) if s['kind'] == 'program'), None),
                'office_heading': next((s['hid'] for s in reversed(stack) if s['kind'] == 'office'), None),
                'region_heading': next((s['hid'] for s in reversed(stack) if s['kind'] == 'region'), None),
                'hb_title': strip_coords(it['hb']),
                'senate_title': strip_coords(it['rev']) or None,
                'hb_coords': [c for c in it['hb'] if COORD.match(c)] or None,
                'senate_coords': [c for c in it['rev'] if COORD.match(c)] or None,
                'gab_php': it['gab'], 'inc_php': it['inc'], 'dec_php': it['dec'],
                'net_php': it['net'], 'sv_php': it['sv'],
                'is_fap': bool(it.get('fap_project')),
            })
        else:
            while stack and stack[-1]['x0'] >= x0 - 0.5:
                stack.pop()
            kind = heading_kind(name, x0)
            path = [s['name'] for s in stack if s['kind'] == 'program'] \
                + [s['name'] for s in stack if s['kind'] == 'region'] \
                + [s['name'] for s in stack if s['kind'] == 'office']
            heading = {'hid': f'h{len(headings)}', 'x0': x0, 'kind': kind, 'name': name,
                       'path': path,
                       'gab_php': it['gab'], 'inc_php': it['inc'], 'dec_php': it['dec'],
                       'net_php': it['net'], 'sv_php': it['sv'], 'pdf_page': it['pdf_page']}
            stack.append(heading)
            headings.append(heading)

    out = {
        'schema_version': 1,
        'program': 'dpwh',
        'role': 'senate_committee_report_annex',
        'label': 'Senate CR Annex A-4 — DPWH changes to House Vol I-C (FY2027)',
        'note': 'Independent extraction from the born-digital PDF; adapted '
                'from bettergovph/ai-budget parse_annex_a4.py (MIT), same '
                'column geometry, plus per-row provenance and coordinate split.',
        'metadata': {
            'source_pdf': str(PDF.relative_to(ROOT)),
            'source_pdf_sha256': sha256(PDF),
            'pdf_pages': len(pdf.pages),
            'extractor': 'Senate_report_data/scripts/extract_annex_a4.py',
            'borrowed_from': 'bettergovph/ai-budget@main scripts/senate-cr/parse_annex_a4.py',
        },
        'summary': {
            'projects': len(projects),
            'renamed': sum(1 for p in projects if p['senate_title']),
            'cut_to_zero': sum(1 for p in projects if (p['sv_php'] or 0) == 0 and (p['gab_php'] or 0) > 0),
            'fap_projects': sum(1 for p in projects if p['is_fap']),
            'headings': len(headings),
            'gab_total_php': sum(p['gab_php'] or 0 for p in projects),
            'sv_total_php': sum(p['sv_php'] or 0 for p in projects),
        },
        'headings': [{'hid': h['hid'], 'kind': h['kind'], 'name': h['name'],
                      'path': h['path'], 'gab_php': h['gab_php'], 'inc_php': h['inc_php'],
                      'dec_php': h['dec_php'], 'net_php': h['net_php'], 'sv_php': h['sv_php'],
                      'pdf_page': h['pdf_page']} for h in headings],
        'projects': projects,
    }
    pdf.close()

    # Roll-up reconciliation. A-4 prints subtotals per program block, so the
    # control key is the heading instance, not the name. Σ projects stamped
    # with an office/region heading id must equal that instance's printed
    # subtotal.
    # Heading rows print the unit's FULL budget (GAB → SV, including lines the
    # annex does not list because the Senate left them unchanged), so Σ listed
    # projects reconciles on the change columns only: inc, dec, and net.
    sums = defaultdict(lambda: [0, 0, 0])
    for p in projects:
        for field in ('office_heading', 'region_heading'):
            hid = p.get(field)
            if hid is not None:
                sums[field, hid][0] += p['inc_php'] or 0
                sums[field, hid][1] += p['dec_php'] or 0
                sums[field, hid][2] += p['net_php'] or 0
    by_id = {h['hid']: h for h in headings}
    exceptions = []
    verified = set()
    for field in ('office_heading', 'region_heading'):
        for (kind, hid), (inc, dec, net) in sorted(sums.items()):
            h = by_id[hid]
            printed = (h.get('inc_php') or 0, h.get('dec_php') or 0, h.get('net_php') or 0)
            if printed == (inc, dec, net):
                verified.add(hid)
            else:
                exceptions.append({
                    'hid': hid, 'kind': h['kind'], 'name': h['name'],
                    'pdf_page': h['pdf_page'],
                    'printed': {'inc_php': h.get('inc_php'), 'dec_php': h.get('dec_php'),
                                'net_php': h.get('net_php')},
                    'sum_projects': {'inc_php': inc, 'dec_php': dec, 'net_php': net},
                })
    # Headings with no stamped projects (fund-only or page-break repeats) are
    # structural, not exceptions.
    out['rollup'] = {
        'verified_subtotal_hids': sorted(verified),
        'exceptions': exceptions,
        'note': ('Heading rows print the unit full budget (GAB → SV including '
                  'unchanged lines); Σ listed projects reconciles on inc/dec/net '
                  'only. Instances marked verified reconcile exactly. Exceptions '
                  'are trailing right-aligned region subtotals and office blocks '
                  'that print before their region heading — ambiguous stamping, '
                  'kept visible rather than forced.'),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
    print(f"{OUT.name}: {out['summary']}")
    print(f"roll-up check: {len(verified)} verified subtotal instances, "
          f"{len(exceptions)} exceptions recorded")
    return 0


if __name__ == '__main__':
    sys.exit(main())
