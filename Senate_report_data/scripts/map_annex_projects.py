#!/usr/bin/env python3
"""Structurally map Senate Annex A-1/A-3 project rows to our House bill rows,
and link insertions to the cut rows they replace.

Unlike A-4 (page-citation anchored), A-1/A-3 print no House page citation, so
the join is title+amount keyed — but against OUR snapshots (FMR workbench
house projects, NIA hgab_nia_projects.csv), with bettergov's published
house_ids as an independent cross-check, not as the source.

Match passes (one-to-one, a House row used once; adapted from
bettergovph/ai-budget map_projects.py, MIT):
  exact    same name (letters+digits) and same House amount
  fuzzy    name >= 90 similar, same House amount
  prefix   one name starts with the other, same amount (>= 25 chars)

Reinstatement pass (A-1 amendment rows): rows printing a House-style title
+ Senate title + Senate amount with NO GAB amount are NEP roads the House
dropped and the Senate restored (the "hb" title is the NEP text verbatim).
Join (norm title + amount) against the NEP snapshot -> house chain gets a
senate row with status 'reinstated' + senate_title = the new name.

Replacement linking (the annex's delete+insert pattern) — full within-region
scored match, not a look-back window:
  candidates = same region + same municipality; similarity floor 85 when
  amounts match, 93 when only titles match
  rank by similarity (+boost same amount, +boost cut-before-insert)
  greedy one-to-one; cut normally precedes insertion (exception: sim>=95
  and same amount). Catches cross-page pairs (e.g. San Lorenzo Bangui).

Usage: map_annex_projects.py fmr|nia
Output: Senate_report_data/data/derived/senate_annex_a{1,3}_{fmr,nia}_mapped.json
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP = {
    'fmr': ROOT / 'Senate_report_data' / 'data' / 'derived' / 'senate_annex_a1_fmr.json',
    'nia': ROOT / 'Senate_report_data' / 'data' / 'derived' / 'senate_annex_a3_nia.json',
}
OUT = {k: v.with_name(v.stem + '_mapped.json') for k, v in SNAP.items()}
ANNEX = {'fmr': 'a1', 'nia': 'a3'}
BG = ROOT / 'Senate_report_data' / 'data' / 'bettergov-senate-2027-dataset' / 'senate-2027-dataset' / 'senate-2027-projects.csv'

GENERIC = re.compile(
    r"\b(construction|concreting|rehabilitation|improvement|repair|of|the|and|to|from|in|at|along|"
    r"fmr|farm|market|road|roads|brgy|barangay|barangays|sitio|purok|phase|ris|cis|nis|irrigation|"
    r"system|systems)\b\.?", re.I)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def distinct(s):
    return re.sub(r"\s+", " ", GENERIC.sub(" ", re.sub(r"[^\w\s]", " ", s or ""))).strip().lower()


def site(s):
    parts = [p for p in (s or "").split(",") if p.strip()]
    return distinct(",".join(parts[:-2]) if len(parts) >= 3 else s)


def same_place(a, b):
    for x, y in ((a, b), (b, a)):
        parts = [p.strip() for p in (x or "").split(",") if p.strip()]
        if len(parts) >= 3 and norm(parts[-2]) and norm(parts[-2]) in norm(y):
            return True
    return False


def sim(a, b):
    return SequenceMatcher(None, a or '', b or '').ratio() * 100


def token_set_ratio(a, b):
    # cheap stand-in for fuzz.token_set_ratio: ratio over the sorted word sets
    wa, wb = sorted(set((a or '').split())), sorted(set((b or '').split()))
    return sim(" ".join(wa), " ".join(wb))


def load_house(kind):
    """Our house rows: (id, title, region, amount_php)."""
    if kind == 'fmr':
        d = json.load(open(ROOT / 'other-analysis' / 'data' / 'fmr_workbench.json'))
        return [{'id': p['id'], 'title': p['title'],
                 'region': p.get('region_key'), 'amount': p['amount_php']}
                for p in d['stages']['house']['projects']]
    rows = []
    with open(ROOT / 'analysis-nia' / 'data' / 'hgab_nia_projects.csv',
              encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            amt = r.get('amount_php') or ''
            rows.append({'id': r['id'], 'title': r['title'],
                         'region': (r.get('path') or '').split('/')[-1],
                         'amount': int(amt.replace(',', '')) if amt else 0})
    return rows


def region_of(kind, row):
    if kind == 'fmr':
        return next((p for p in reversed(row.get('path', [])) if re.match(
            r"^(REGION|CORDILLERA|NATIONAL CAPITAL|BANGSAMORO|NEGROS ISLAND|MARIIS|UPRIIS)", p.upper())), '')
    return next((p for p in reversed(row.get('path', [])) if re.match(
        r"^(REGION|CORDILLERA|NATIONAL CAPITAL|BANGSAMORO|NEGROS ISLAND|MARIIS|UPRIIS)", p.upper())), '')


def main(kind: str) -> int:
    annex = json.load(open(SNAP[kind]))
    sen = [r for r in annex['rows'] if r['kind'] == 'project']
    for r in sen:
        r['region'] = region_of(kind, r)
    house = load_house(kind)
    for h in house:
        h['_n'] = norm(h['title'])

    by_key, by_amt = defaultdict(list), defaultdict(list)
    for h in house:
        by_key[(h['_n'], h['amount'])].append(h)
        by_amt[h['amount']].append(h)
    used, match = set(), {}

    def take(i, cands, how):
        cands = [h for h in cands if h['id'] not in used]
        if not cands:
            return
        reg = norm(sen[i]['region'])[:8]
        cands.sort(key=lambda h: norm(h['region'] or '')[:8] != reg)
        used.add(cands[0]['id'])
        match[i] = (cands[0], how)

    for i, r in enumerate(sen):
        if r['gab']:
            take(i, by_key.get((norm(r['hb_title']), r['gab']), []), 'exact')
    for i, r in enumerate(sen):
        if r['gab'] and i not in match:
            scored = sorted(((sim(r['hb_title'], h['title']), h)
                             for h in by_amt.get(r['gab'], []) if h['id'] not in used),
                            key=lambda t: -t[0])
            if scored and scored[0][0] >= 90:
                take(i, [scored[0][1]], 'fuzzy')
    for i, r in enumerate(sen):
        if r['gab'] and i not in match and len(norm(r['hb_title'])) >= 25:
            a = norm(r['hb_title'])
            take(i, [h for h in by_amt.get(r['gab'], [])
                     if h['_n'].startswith(a) or a.startswith(h['_n'])], 'prefix')

    # Reinstatement pass (A-1): amendment rows print House-style title +
    # Senate title + Senate amount with NO GAB — the Senate restoring NEP
    # roads the House dropped. The 'hb_title' is the NEP text verbatim, so
    # join (norm title, amount) against the NEP snapshot, then attach to the
    # house chain via the nep->house edge if one exists.
    reinstated = {}
    if kind == 'fmr':
        wb = json.load(open(ROOT / 'other-analysis' / 'data' / 'fmr_workbench.json'))
        nep = {p['id']: p for p in wb['stages']['nep']['projects']}
        nep_by_key = {(norm(p['title']), p['amount_php']): p for p in nep.values()}
        # nep -> house locator from the ledger's match edges
        nep_to_house = {}
        for line in open(ROOT / 'data_formalization' / 'data' / 'ledger' / 'fmr.jsonl'):
            e = json.loads(line)
            if e['type'] == 'match.asserted' and e['subject'].startswith('nep_fmr:'):
                nep_to_house[e['subject']] = e['payload'].get('to')
        for i, r in enumerate(sen):
            if r['gab'] or not r.get('senate_title') or not r.get('hb_title'):
                continue
            p = nep_by_key.get((norm(r['hb_title']), r['sv']))
            if not p:
                # fallback: annex corrected NEP typos (e.g. 'Tiocos Sur' ->
                # 'Ilocos Sur'), so exact title fails; try same place + sim
                cands = [q for q in nep.values()
                         if q['amount_php'] == r['sv']
                         and sim(r['hb_title'], q['title']) >= 85
                         and same_place(r['hb_title'], q['title'])]
                if len(cands) == 1:
                    p = cands[0]
            if not p:
                continue
            reinstated[i] = {'nep_id': p['id'],
                             'house_id': nep_to_house.get(p['id'])}

    # Replacement linking: full within-region scored match (no row window).
    # Annex A-1 often prints a correction as cut+insert far apart (different
    # pages); a look-back window misses those. Score every insertion against
    # every cut in the same region that shares a municipality, then take
    # pairs greedily one-to-one by descending score.
    # Amount-matched pairs can be looser on title (GPS/name corrections);
    # title-only pairs need a higher floor to avoid Edy↔Estacion-style misses.
    # Matching is hierarchical: region -> municipality -> barangay. Within a
    # municipality (title place field), a shared barangay token boosts the
    # score; roads in different municipalities never pair (Bobonan
    # Villasis≠Pozorrubio even though both are "Bobonan").
    SIM_AMT, SIM_TITLE = 85, 93

    def place_parts(s):
        """'..., Brgy. X, Municipality, Province' -> (municipality, barangay tokens)."""
        parts = [p.strip() for p in (s or '').split(',') if p.strip()]
        if len(parts) < 2:
            return None
        muni = parts[-2]
        # some titles print only (barangay, province): municipality slot then
        # holds a barangay marker -> treat as unknown municipality
        if re.match(r'^(brgy|barangay|sitio|purok)\b', muni, re.I):
            return None
        brgy = ' '.join(parts[:-2])
        return norm(muni), brgy.lower()

    def brgy_overlap(a, b):
        STOP = {'brgy', 'barangay', 'sitio', 'purok', 'and', 'the', 'to', 'of',
                'fmr', 'farm', 'market', 'road', 'roads', 'phase', 'construction',
                'concreting', 'rehabilitation', 'improvement', 'repair', 'leading',
                'from', 'extension', 'opening', 'graveling', 'upgrading'}
        ta = set(re.findall(r'[a-z]+', a)) - STOP
        tb = set(re.findall(r'[a-z]+', b)) - STOP
        if not ta or not tb:
            return 0
        return len(ta & tb) / min(len(ta), len(tb))

    def pair_score(ins, cut, i, j):
        name = ins['senate_title'] or ins['hb_title'] or ''
        old = cut['hb_title'] or cut['senate_title'] or ''
        if not same_place(name, old):
            return None
        # municipality gate: realignments happen within one municipality
        # (None = municipality not printed -> no gate); prefix-aware so
        # renamed municipalities (Don Victoriano[ Chiongbian]) still match
        pi, pc = place_parts(name), place_parts(old)
        if pi is None or pc is None:
            muni_match = True
        else:
            a, b = pi[0], pc[0]
            muni_match = a == b or a.startswith(b) or b.startswith(a)
        score = max(token_set_ratio(site(name), site(old)),
                    token_set_ratio(distinct(name), distinct(old)),
                    token_set_ratio(name.lower(), old.lower()))
        boosted = False
        if pi and pc and (pi[0] == pc[0] or pi[0].startswith(pc[0]) or pc[0].startswith(pi[0])):
            ov = brgy_overlap(pi[1], pc[1])
            if ov > 0:
                score = max(score, score * 0.6 + 40 * ov)
                boosted = True
            else:
                # same municipality but disjoint barangays (Hagupit vs
                # Libertad) — never a realignment
                return None
        same_amt = bool(ins.get('sv') and cut.get('gab') and ins['sv'] == cut['gab'])
        floor = (SIM_AMT - 5 if boosted else SIM_AMT) if same_amt else \
                (SIM_TITLE - 8 if boosted else SIM_TITLE)
        if score < floor:
            return None
        before = j < i  # cut normally precedes insert in annex order
        # allow reverse only when near-identical + same amount
        if not before and not (score >= 95 and same_amt):
            return None
        method = 'full_amt' if same_amt else 'full_title'
        if not muni_match:
            method += '_xmuni'
        rank = (score + (8 if same_amt else 0) + (2 if before else 0)
                + (3 if muni_match else 0), score, 1 if before else 0)
        return {'sim': score, 'same_amt': same_amt, 'before': before,
                'method': method, 'rank': rank}

    cands = []
    for i, r in enumerate(sen):
        if r['gab']:
            continue
        for j, c in enumerate(sen):
            if not c['gab'] or c['sv']:
                continue
            if r['region'] != c['region']:
                continue
            sc = pair_score(r, c, i, j)
            if sc:
                cands.append((sc['rank'], sc, i, j))
    cands.sort(key=lambda t: t[0], reverse=True)
    replaces, used_ins, used_cut = {}, set(), set()
    for _rank, sc, i, j in cands:
        if i in used_ins or j in used_cut:
            continue
        replaces[i] = (j, sc['sim'], sc['method'])
        used_ins.add(i)
        used_cut.add(j)

    # Cross-check vs bettergov published rows (they embed our ib: locators).
    bg = [r for r in csv.DictReader(open(BG, encoding='utf-8-sig'))
          if r['program'] == kind]
    bg_by_locator = {}
    for r in bg:
        hid = r['house_id'] or ''
        m = re.search(r'(ib:p\d+:r\d+)', hid)
        if m:
            bg_by_locator.setdefault(m.group(1), []).append(r)
    agree = disagree = 0
    disagree_list = []
    for i, r in enumerate(sen):
        h, how = match.get(i, (None, None))
        if not h:
            continue
        bg_rows = bg_by_locator.get(h['id'])
        if not bg_rows:
            continue
        # any bettergov row with this house locator must have our amount too
        if any((b['house_php'] and int(b['house_php']) == r['gab']) for b in bg_rows):
            agree += 1
        else:
            disagree += 1
            if len(disagree_list) < 8:
                disagree_list.append((h['id'], r['gab'],
                                      [b['house_php'] for b in bg_rows]))

    out_rows = []
    stats = defaultdict(int)
    for i, r in enumerate(sen):
        h, how = match.get(i, (None, None))
        if not how:
            how = 'insertion' if not r['gab'] else 'unmatched'
        stats[how] += 1
        rep = replaces.get(i)
        rep_h = match.get(rep[0], (None,))[0] if rep else None
        rein = reinstated.get(i)
        out_rows.append({
            'id': r['id'], 'pdf_page': r['pdf_page'], 'row_index': r['row_index'],
            'region': r['region'], 'path': r['path'],
            'hb_title': r['hb_title'],
            'senate_title': r['senate_title'] or None,
            'hb_coords': r['hb_coords'], 'senate_coords': r['senate_coords'],
            'gab_php': r['gab'], 'inc_php': r['inc'], 'dec_php': r['dec'],
            'net_php': r['net'], 'sv_php': r['sv'],
            'match': how,
            'house_id': h['id'] if h else None,
            'house_title': h['title'] if h else None,
            'house_amount_php': h['amount'] if h else None,
            'replaces_id': sen[rep[0]]['id'] if rep else None,
            'replaces_house_id': rep_h['id'] if rep_h else None,
            'replaces_similarity': round(rep[1]) if rep else None,
            'replaces_method': rep[2] if rep else None,
            'reinstated_nep_id': rein['nep_id'] if rein else None,
            'reinstated_house_id': rein['house_id'] if rein else None,
        })
    doc = {
        'schema_version': 1,
        'program': kind,
        'role': 'senate_annex_structural_map',
        'label': f'Senate Annex {ANNEX[kind].upper()} ({kind}) mapped to our '
                 f'house rows, with replacement links',
        'note': 'Title+amount join against OUR snapshots (no page citations '
                'in A-1/A-3), one-to-one; insertions linked to cut rows via '
                'full within-region scored match (same municipality; sim '
                '>= 85 with same amount, >= 93 title-only; prefer cut-'
                'before-insert; greedy 1-1). Cross-checked against '
                'bettergov house locators.',
        'inputs': {
            'annex': str(SNAP[kind].relative_to(ROOT)),
            'house_source': ('other-analysis/data/fmr_workbench.json '
                             'stages.house.projects' if kind == 'fmr' else
                             'analysis-nia/data/hgab_nia_projects.csv'),
            'crosscheck': str(BG.relative_to(ROOT)),
        },
        'summary': {
            'annex_projects': len(sen),
            'matched': len(used),
            'house_rows': len(house),
            'match_stats': dict(stats),
            'insertions_linked_to_cut': len(replaces),
            'reinstated_from_nep': len(reinstated),
            'crosscheck': {'locator_amount_agree': agree,
                           'locator_amount_disagree': disagree},
        },
        'rows': out_rows,
    }
    OUT[kind].write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n')
    s = doc['summary']
    print(f'{kind}: {s["match_stats"]}; replacements={s["insertions_linked_to_cut"]}; '
          f'crosscheck agree={agree} disagree={disagree}')
    for d in disagree_list:
        print('  DISAGREE', d)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
