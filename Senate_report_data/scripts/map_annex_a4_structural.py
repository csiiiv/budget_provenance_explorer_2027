#!/usr/bin/env python3
"""R2: structurally map Senate Annex A-4 rows to the House Vol I-C native tree.

Join key: the A-4's cited printed HB page (+8 = PDF page in the 3rd-reading
Vol I-C extract). Within the page, tie-break by exact title+amount, then
amount+office, then amount-unique, then fuzzy>=90. Every A-4 row keeps its
provenance; every match records how it was made.

Output: Senate_report_data/data/derived/senate_annex_a4_dpwh_mapped.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
A4 = ROOT / 'Senate_report_data' / 'data' / 'derived' / 'senate_annex_a4_dpwh.json'
TREE = ROOT / 'analysis' / 'data' / 'hb_dpwh_native_ic_projects_3rd_reading.json'
OUT = ROOT / 'Senate_report_data' / 'data' / 'derived' / 'senate_annex_a4_dpwh_mapped.json'

PAGE_OFFSET = 8  # printed HB page + 8 = Vol I-C PDF page (verified: mode 8, uniform)


def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def office_key(s):
    s = (s or '').lower().replace('district engineering office', 'deo').replace('engineering office', 'eo')
    return re.sub(r'[^a-z0-9]', '', s)


def sim(a, b):
    return SequenceMatcher(None, a or '', b or '').ratio() * 100


def main() -> int:
    a4 = json.load(open(A4))['projects']
    tree = json.load(open(TREE))

    leaves = []

    def walk(n, path):
        # fap_project nodes are internal (funding children) but are the unit the
        # Senate A-4 rows cite; their printed amount is the GOP-side figure.
        if n.get('kind') in ('project', 'fap_project'):
            office = next((p['label'] for p in reversed(path) if p.get('kind') == 'office'), None)
            region = next((p['label'] for p in reversed(path) if p.get('kind') == 'region'), None)
            leaves.append({'node': n, 'office': office, 'region': region})
        for c in n.get('children') or []:
            walk(c, path + [n])

    walk(tree['root'], [])

    for l in leaves:
        n = l['node']
        l['_n'] = norm(n['label'])
        l['_o'] = office_key(l['office'])
        l['_amt'] = n.get('printed_amount_php')
        l['_pg'] = n['source']['pdf_page']

    by_page = defaultdict(list)
    by_amt_page = defaultdict(list)
    for l in leaves:
        by_page[l['_pg']].append(l)
        by_amt_page[(l['_amt'], l['_pg'])].append(l)

    used = set()
    match = {}

    def take(i, l, how):
        used.add(l['node']['id'])
        match[i] = (l, how)

    # Pass 1: cited page + exact title + amount
    order = sorted(range(len(a4)), key=lambda i: len(
        by_amt_page.get(((a4[i].get('gab_php') or 0), (a4[i].get('hb_page_cited') or 0) + PAGE_OFFSET), [])))
    for i in order:
        r = a4[i]
        if not r.get('gab_php') or not r.get('hb_page_cited'):
            continue
        cands = [l for l in by_amt_page.get((r['gab_php'], r['hb_page_cited'] + PAGE_OFFSET), [])
                 if l['node']['id'] not in used and l['_n'] == norm(r['hb_title'])]
        if len(cands) == 1:
            take(i, cands[0], 'page_exact')
        elif len(cands) > 1:
            o = office_key(r.get('office'))
            same = [l for l in cands if l['_o'] == o]
            if len(same) == 1:
                take(i, same[0], 'page_exact_office')
    # Pass 2: cited page + amount + office, single candidate (title garbled by overprint)
    for i, r in enumerate(a4):
        if i in match or not r.get('gab_php') or not r.get('hb_page_cited'):
            continue
        o = office_key(r.get('office'))
        cands = [l for l in by_amt_page.get((r['gab_php'], r['hb_page_cited'] + PAGE_OFFSET), [])
                 if l['node']['id'] not in used and l['_o'] == o]
        if len(cands) == 1:
            take(i, cands[0], 'page_amount_office')
    # Pass 3: cited page ±1 + exact title + amount (citation off-by-one)
    for i, r in enumerate(a4):
        if i in match or not r.get('gab_php') or not r.get('hb_page_cited'):
            continue
        nt, g = norm(r['hb_title']), r['gab_php']
        for pg in (r['hb_page_cited'] + PAGE_OFFSET - 1, r['hb_page_cited'] + PAGE_OFFSET + 1):
            cands = [l for l in by_amt_page.get((g, pg), [])
                     if l['node']['id'] not in used and l['_n'] == nt]
            if len(cands) == 1:
                take(i, cands[0], 'page_pm1_exact')
                break
    # Pass 4: anywhere — exact title + amount (A-4's own citation wrong)
    by_key = defaultdict(list)
    for l in leaves:
        by_key[(l['_n'], l['_amt'])].append(l)
    for i, r in enumerate(a4):
        if i in match or not r.get('gab_php'):
            continue
        cands = [l for l in by_key.get((norm(r['hb_title']), r['gab_php']), []) if l['node']['id'] not in used]
        if len(cands) == 1:
            take(i, cands[0], 'global_exact')
    # Pass 5: fuzzy >= 90 on title, same amount, same office, anywhere
    by_amt = defaultdict(list)
    for l in leaves:
        by_amt[l['_amt']].append(l)
    for i, r in enumerate(a4):
        if i in match or not r.get('gab_php'):
            continue
        o = office_key(r.get('office'))
        cands = [l for l in by_amt.get(r['gab_php'], []) if l['node']['id'] not in used and l['_o'] == o]
        scored = sorted(((sim(r['hb_title'], l['node']['label']), l) for l in cands), key=lambda t: -t[0])
        if scored and scored[0][0] >= 90:
            take(i, scored[0][1], 'fuzzy90_amount_office')
    # Pass 6: large amount unique among unused rows anywhere (>=100M)
    for i, r in enumerate(a4):
        if i in match or not r.get('gab_php') or r['gab_php'] < 100_000_000:
            continue
        cands = [l for l in by_amt.get(r['gab_php'], []) if l['node']['id'] not in used]
        if len(cands) == 1:
            take(i, cands[0], 'amount_unique')

    out_rows, stats = [], defaultdict(int)
    for i, r in enumerate(a4):
        l, how = match.get(i, (None, None))
        if not how:
            how = 'senate_insertion' if not r['hb_title'] and not r.get('gab_php') else 'unmatched'
        stats[how] += 1
        out_rows.append({
            **{k: v for k, v in r.items()},
            'match': how,
            'tree_id': l['node']['id'] if l else None,
            'tree_title': l['node']['label'] if l else None,
            'tree_amount_php': l['_amt'] if l else None,
            'tree_pdf_page': l['_pg'] if l else None,
            'tree_office': l['office'] if l else None,
            'tree_region': l['region'] if l else None,
            'amount_agrees': (l['_amt'] == r.get('gab_php')) if l and r.get('gab_php') else None,
        })
    doc = {
        'schema_version': 1,
        'program': 'dpwh',
        'role': 'senate_annex_a4_structural_map',
        'label': 'Senate Annex A-4 mapped to House Vol I-C 3rd-reading native tree',
        'note': 'Join anchored on the A-4 printed HB page citation (+8 = Vol I-C '
                'PDF page, offset verified uniform across the document by 4,530 '
                'strict exact-name+amount anchors).',
        'inputs': {
            'annex_a4': str(A4.relative_to(ROOT)),
            'house_tree': str(TREE.relative_to(ROOT)),
            'page_offset': PAGE_OFFSET,
        },
        'summary': {
            'a4_rows': len(a4),
            'matched': len(used),
            'house_leaves': len(leaves),
            'match_stats': dict(stats),
            'gab_php_matched': sum(r['gab_php'] or 0 for r in out_rows if r['tree_id']),
            'sv_php_matched': sum(r['sv_php'] or 0 for r in out_rows if r['tree_id']),
        },
        'rows': out_rows,
    }
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n')
    s = doc['summary']
    print(f"rows={s['a4_rows']} matched={s['matched']}/{s['house_leaves']} leaves; {dict(stats)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
