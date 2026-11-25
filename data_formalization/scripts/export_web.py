#!/usr/bin/env python3
"""Export folded ledger data as static JSON bundles for the web app.

Program: fmr (first). One bundle per program under web/public/data/<program>/:

  manifest.json  build info, ledger shas, counts, validation runs
  regions.json   per-region stage aggregates + flow classification counts
  projects.json  one record per chain: house rows (hub) + nep-only rows +
                 senate insertions; stage amounts/titles/provenance, match
                 methods, replaces chain, DA dispositions, locality
                 (province/municipality parsed from the best title)
  lineage.json   the mermaid DAG text + node table (from lineage.py graph)

The fold reads ONLY the ledger + registered snapshots (no re-extraction):
titles come from the workbench/snapshot JSONs keyed by locator.

Run:  python3 data_formalization/scripts/export_web.py [--program fmr]
Then: cd web && npm run dev   (Vite; or `npm run build && npm run preview`)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lineage as G  # noqa: E402
from export_downloads import write_csv, write_sums, pesos  # noqa: E402

from stage_changes import linked_budget_pairs, summarize_budget_changes

WEB = ROOT / 'web'
REG_PHP = 1_000_000


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def php(v):
    """full pesos -> rounded millions, null-safe"""
    return None if v is None else round(v / REG_PHP, 3)


def load_ledger(domain: str) -> list[dict]:
    p = ROOT / 'data_formalization' / 'data' / 'ledger' / f'{domain}.jsonl'
    return [json.loads(l) for l in open(p)]


def region_sort_key(k):
    order = ['NCR', 'I', 'II', 'III', 'IVA', 'IVB', 'V', 'VI', 'VII', 'VIII',
             'IX', 'X', 'XI', 'XII', 'XIII', 'CAR', 'BARMM', 'NIR']
    return (order.index(k) if k in order else 99, k)


def export_fmr() -> dict:
    # ---- source snapshots for titles -------------------------------------
    wb = json.load(open(ROOT / 'other-analysis' / 'data' / 'fmr_workbench.json'))
    nep_title = {p['id']: p for p in wb['stages']['nep']['projects']}
    house_proj = {p['id']: p for p in wb['stages']['house']['projects']}
    da5 = {p['control_no']: p for p in
           json.load(open(ROOT / 'other-analysis' / 'data' / 'da_fmr_draft.json'))['projects']}
    da12 = {p['control_no']: p for p in
            json.load(open(ROOT / 'other-analysis' / 'data' / 'da_fmr_draft_nov12.json'))['projects']}
    region_label = {r['id']: r['label'] for r in wb['regions']}
    # senate A-1 mapped view for region normalization + status detail
    a1 = {r['id']: r for r in json.load(open(
        ROOT / 'Senate_report_data' / 'data' / 'derived' /
        'senate_annex_a1_fmr_mapped.json'))['rows']}

    # printed region roll-ups from the raw A-1 snapshot: heading rows carry
    # the annex's own subtotals (reconciled: grand total = Σregions = Σrows)
    a1_rollups = {}
    for row in json.load(open(
            ROOT / 'Senate_report_data' / 'data' / 'derived' /
            'senate_annex_a1_fmr.json'))['rows']:
        if row['kind'] == 'heading' and row.get('level') == 1:
            name = (row['hb_title'] or row['senate_title']).strip()
            a1_rollups[name] = {'name': name,
                                'gab_php': row['gab'], 'sv_php': row['sv'],
                                'pdf_page': row['pdf_page']}
    for row in a1.values():
        if row.get('region') in a1_rollups:
            row['region_subtotal'] = a1_rollups[row['region']]

    def coords_raw_list(p):
        """'START: lat, lon\\nEND: ...' -> ['START: ...','END: ...'] (or None)."""
        s = (p or {}).get('coordinates_raw')
        if not s:
            return None
        return [l.strip() for l in s.splitlines() if l.strip()] or None

    def flags_of(p):
        if not p:
            return None
        out = []
        for k in ('review_flags', 'original_review_flags'):
            v = p.get(k) or []
            out.extend(v if isinstance(v, list) else [v])
        st = p.get('status')
        if st and st not in ('normalized', 'ok', 'clean'):
            out.append(st)
        return out or None

    def da_new_matches_insertion(row, da_new_title, da_new_coords):
        """Exact title or exact-GPS match of a Senate insertion vs a DA 'new' row."""
        t = (row.get('senate_title') or '').strip().lower()
        if t and t in da_new_title:
            p = da_new_title[t]
            return {'ctrl': p['control_no'], 'basis': 'exact title',
                    'remark': (p.get('remarks') or '').strip() or None,
                    'kind': p.get('kind')}
        c = coords_key('\n'.join(row.get('senate_coords') or []))
        if c and c in da_new_coords:
            p = da_new_coords[c]
            return {'ctrl': p['control_no'], 'basis': 'exact GPS',
                    'remark': (p.get('remarks') or '').strip() or None,
                    'kind': p.get('kind')}
        return None

    import re as _re  # noqa: F401 (kept for gps_km below)
    def coords_key(s):
        if not s:
            return ''
        nums = _re.findall(r'\d+\.?\d*', s)
        return ','.join(f'{float(n):.6f}' for n in nums)

    # index DA nov12 'new' rows for insertion-evidence joins
    da12_new = [p for p in da12.values() if p.get('kind') == 'new']
    da_new_title = {(p.get('to_title') or '').strip().lower(): p for p in da12_new}
    da_new_coords = {coords_key(p.get('to_coordinates_raw')): p
                     for p in da12_new if coords_key(p.get('to_coordinates_raw'))}

    def gps_km(a, b):
        """km between two 'lat, lon' strings (or None)."""
        import math
        def parse(s):
            m = _re.search(r'(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)', s or '')
            return (float(m.group(1)), float(m.group(2))) if m else None
        pa, pb = parse(a), parse(b)
        if not pa or not pb:
            return None
        lat1, lon1, lat2, lon2 = map(math.radians, (pa[0], pa[1], pb[0], pb[1]))
        h = (math.sin((lat2-lat1)/2)**2 +
             math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2)
        return 2*6371*math.asin(math.sqrt(h))

    def coord_first(c):
        if not c:
            return None
        s = c[0] if isinstance(c, list) else str(c)
        return s

    def substitution_candidates(cut_row, sv):
        """DA-new rows near the cut row's GPS in the same region (km-capped)."""
        cc = cut_row.get('hb_coords') or cut_row.get('senate_coords') or []
        if not cc:
            return []
        anchor = coord_first(cc)
        out = []
        for p in da12_new:
            if p.get('region_key') != cut_row.get('region_key') and p.get('region') != cut_row.get('region'):
                continue
            pc = p.get('to_coordinates_raw') or ''
            for line in pc.splitlines():
                km = gps_km(anchor, line)
                if km is not None and km <= 2.0:
                    out.append({'ctrl': p['control_no'],
                                'title': p.get('to_title'),
                                'km': round(km, 2),
                                'da_proposed_m': php(p.get('proposed_amount_php')),
                                'remark': (p.get('remarks') or '').strip() or None})
                    break
        out.sort(key=lambda x: x['km'])
        return out[:3]

    # senate region name -> region_key
    def senate_region_key(name):
        if not name:
            return None
        n = re.sub(r'^REGION IV([AB])\b', r'REGION IV-\1', name.strip().upper())
        m = {
            'REGION I -': 'I', 'REGION II -': 'II', 'REGION III -': 'III',
            'REGION IV-A': 'IVA', 'REGION IV-B': 'IVB', 'REGION V -': 'V',
            'REGION VI -': 'VI', 'REGION VII -': 'VII', 'REGION VIII -': 'VIII',
            'REGION IX -': 'IX', 'REGION X -': 'X', 'REGION XI -': 'XI',
            'REGION XII -': 'XII', 'REGION XIII -': 'XIII',
            'CORDILLERA': 'CAR', 'NATIONAL CAPITAL': 'NCR',
            'BANGSAMORO': 'BARMM', 'NEGROS ISLAND': 'NIR',
        }
        for pre, key in m.items():
            if n.startswith(pre):
                return key
        return None

    # reinstatement edges: amendment annex row -> NEP row ( Senate restored)
    ledger = load_ledger('fmr')
    rein = {}
    for e in ledger:
        if e['type'] == 'match.asserted' and e['payload'].get('method') == 'reinstates':
            rein[e['subject']] = e['payload']['to']

    obs = defaultdict(dict)     # subject -> {'obs': latest, 'prov': {...}}
    edges = defaultdict(list)   # subject -> [(to, payload)]
    runs = []
    for e in ledger:
        s, t = e['subject'], e['type']
        if t == 'line.observed':
            o = obs[s]
            o['obs'] = e['payload']
            o['prov'] = e['provenance']
            o['actor'] = e.get('actor')
        elif t == 'match.asserted':
            edges[s].append((e['payload'].get('to'), e['payload']))
        elif t == 'validation.run':
            runs.append({'subject': s, 'check': e['payload'].get('check'),
                         'result': e['payload'].get('result'),
                         'at': e.get('ts')})

    # index edges by target for reverse lookup
    rev_edges = defaultdict(list)  # to -> [(from_subject, payload)]
    for s, lst in edges.items():
        for to, pl in lst:
            rev_edges[to].append((s, pl))

    # ---- chain records: house hub ----------------------------------------
    records = []
    used_senate = set()
    used_nep = set()
    used_da5 = set()
    used_da12 = set()

    def senate_status(row):
        gab, sv = row.get('gab_php') or 0, row.get('sv_php') or 0
        renamed = bool(row.get('senate_title'))
        if gab > 0 and sv == 0:
            return 'cut'  # may be upgraded to 'realigned' after replaces reverse-link
        if renamed:
            return 'renamed' if sv == gab else ('reduced' if sv < gab else 'raised')
        if sv > gab:
            return 'raised'
        if sv < gab:
            return 'reduced'
        return 'restated'

    def coords_of(row, side='hb'):
        c = row.get(f'{side}_coords') or []
        return c or None

    def realign_reason(cut_row, ins_row):
        """Why Annex A-1 used delete+insert instead of an in-place rename."""
        cut_t = (cut_row.get('hb_title') or cut_row.get('senate_title') or '').strip()
        ins_t = (ins_row.get('senate_title') or ins_row.get('hb_title') or '').strip()
        cut_c = cut_row.get('hb_coords') or cut_row.get('senate_coords') or []
        ins_c = ins_row.get('senate_coords') or ins_row.get('hb_coords') or []
        same_t = cut_t.lower() == ins_t.lower()
        same_c = cut_c == ins_c
        if same_t and not same_c:
            return 'coords'
        if (not same_t) and (not same_c) and cut_c and ins_c:
            return 'title_and_coords'
        if not same_t:
            return 'title'
        return 'restatement'

    def da_disp(ctrl, draft):
        p = draft.get(ctrl)
        if not p:
            return None
        d = p.get('disposition')
        return {'disposition': d, 'excel_row': p.get('excel_row'),
                'kind': p.get('kind'),
                'from_m': php(p.get('from_amount_php')),
                'proposed_m': php(p.get('proposed_amount_php')),
                'title': p.get('to_title') or p.get('from_title'),
                'from_coords': [l.strip() for l in (p.get('from_coordinates_raw') or '').splitlines() if l.strip()] or None,
                'to_coords': [l.strip() for l in (p.get('to_coordinates_raw') or '').splitlines() if l.strip()] or None,
                'remark': (p.get('remarks') or '').strip() or None}

    for hid, hp in house_proj.items():
        o = obs.get(hid, {}).get('obs', {})
        region = hp.get('region_key')
        rec = {
            'id': hid, 'type': 'house', 'region': region,
            'region_label': region_label.get(region),
            'title': hp['title'],
            'house_m': php(hp['amount_php']),
            'house_page': hp.get('source', {}).get('pdf_page'),
            'nep': None, 'senate': None, 'da5': None, 'da12': None,
            'replaces': None,
        }
        # nep upstream: nep_fmr -> ib edge
        for src, pl in rev_edges.get(hid, []):
            if src.startswith('nep_fmr:'):
                np = nep_title.get(src, {})
                rec['nep'] = {'id': src, 'title': np.get('title'),
                              'amount_m': php(np.get('amount_php', o.get('amount_php'))),
                              'page': np.get('source', {}).get('pdf_page'),
                              'match': pl.get('method'),
                              'coords': coords_raw_list(np),
                              'flags': flags_of(np)}
                used_nep.add(src)
        # senate downstream: senate_a1 -> ib edge
        for src, lst in edges.items():
            for to, pl in lst:
                if to == hid and src.startswith('senate_a1:'):
                    row = a1.get(src, {})
                    rec['senate'] = {
                        'id': src, 'status': senate_status(row),
                        'hb_title': row.get('hb_title'),
                        'senate_title': row.get('senate_title'),
                        'gab_m': php(row.get('gab_php')),
                        'sv_m': php(row.get('sv_php')),
                        'page': row.get('pdf_page'),
                        'match': pl.get('method') if pl.get('method') != 'replaces' else None,
                        'hb_coords': coords_of(row, 'hb'),
                        'senate_coords': coords_of(row, 'senate'),
                        'region_label': row.get('region'),
                        'region_subtotal': row.get('region_subtotal'),
                    }
                    used_senate.add(src)
        # DA via nep (da_fmr -> nep edge)
        if rec['nep']:
            for src, pl in rev_edges.get(rec['nep']['id'], []):
                if src.startswith('da_fmr:ctrl:'):
                    ctrl = src.split(':', 2)[2]
                    d5, d12 = da_disp(ctrl, da5), da_disp(ctrl, da12)
                    side = pl.get('match_side')
                    tgt = {'id': src, 'ctrl': ctrl, 'match_side': side,
                           'match': pl.get('method')}
                    if d5:
                        tgt.update(d5)
                        used_da5.add(ctrl)
                    rec['da5'] = tgt
                    if d12:
                        rec['da12'] = {'id': src, 'ctrl': ctrl, **d12}
                        used_da12.add(ctrl)
        # House-side coords/flags
        rec['house_coords'] = coords_raw_list(hp)
        rec['house_flags'] = flags_of(hp)
        # substitution evidence: DA-new row matching this cut's Senate insertion
        if rec['senate'] and rec['senate']['status'] == 'cut':
            rec['subst_candidates'] = substitution_candidates(
                a1.get(rec['senate']['id'], {}), rec['senate'].get('sv_m'))
        records.append(rec)

    # nep-only rows
    for nid, np in nep_title.items():
        if nid in used_nep:
            continue
        records.append({
            'id': nid, 'type': 'nep_only',
            'region': np.get('region_key'),
            'region_label': region_label.get(np.get('region_key')),
            'title': np['title'],
            'nep': {'id': nid, 'title': np['title'],
                    'amount_m': php(np.get('amount_php')),
                    'page': np.get('source', {}).get('pdf_page'),
                    'coords': coords_raw_list(np),
                    'flags': flags_of(np)},
            'house_m': None, 'senate': None, 'da5': None, 'da12': None,
            'replaces': None,
        })

    # reinstatements: Senate restored a NEP road the House dropped
    rein_by_nep = {}
    for sid, nid in rein.items():
        rein_by_nep.setdefault(nid, []).append(sid)
    for nid, sids in rein_by_nep.items():
        np = nep_title.get(nid)
        if not np:
            continue
        target = next((r for r in records if r['id'] == nid), None)
        sid = sids[0]
        row = a1.get(sid, {})
        sen = {'id': sid, 'status': 'reinstated',
               'hb_title': row.get('hb_title'),
               'senate_title': row.get('senate_title'),
               'sv_m': php(row.get('sv_php')),
               'page': row.get('pdf_page'),
               'match': 'reinstates',
               'hb_coords': row.get('hb_coords') or None,
               'senate_coords': row.get('senate_coords') or None,
               'region_label': row.get('region'),
               'region_subtotal': row.get('region_subtotal')}
        if target is not None:
            # upgrade the nep_only record in place
            target['senate'] = sen
            target['restated_by'] = None
        else:
            records.append({
                'id': nid, 'type': 'nep_only',
                'region': np.get('region_key'),
                'region_label': region_label.get(np.get('region_key')),
                'title': np['title'],
                'nep': {'id': nid, 'title': np['title'],
                        'amount_m': php(np.get('amount_php')),
                        'page': np.get('source', {}).get('pdf_page'),
                        'coords': coords_raw_list(np),
                        'flags': flags_of(np)},
                'house_m': None, 'senate': sen, 'da5': None, 'da12': None,
                'replaces': None,
            })
        used_senate.add(sid)

    # senate insertions (+ replaces chain)
    by_id = {r['id']: r for r in records}
    for sid, row in a1.items():
        if sid in used_senate or row.get('gab_php'):
            continue
        rec = {
            'id': sid, 'type': 'senate_insertion',
            'region': senate_region_key(row.get('region')),
            'region_label': row.get('region'),
            'title': row.get('senate_title') or row.get('hb_title'),
            'senate': {'id': sid, 'status': 'inserted',
                       'senate_title': row.get('senate_title'),
                       'sv_m': php(row.get('sv_php')),
                       'page': row.get('pdf_page'),
                       'senate_coords': coords_of(row, 'senate'),
                       'region_label': row.get('region'),
                       'region_subtotal': row.get('region_subtotal')},
            'house_m': None, 'nep': None, 'da5': None, 'da12': None,
            'replaces': None,
        }
        # DA evidence: exact title/GPS match to a DA working-draft 'new' row
        da_ev = da_new_matches_insertion(row, da_new_title, da_new_coords)
        if da_ev:
            rec['da_evidence'] = da_ev
        if row.get('replaces_id'):
            old = a1.get(row['replaces_id'], {})
            reason = realign_reason(old, row)
            rec['replaces'] = {
                'id': row['replaces_id'],
                'hb_title': old.get('hb_title'),
                'gab_m': php(old.get('gab_php')),
                'similarity': row.get('replaces_similarity'),
                'house_id': row.get('replaces_house_id'),
                'reason': reason,
                'from_coords': coords_of(old, 'hb') or coords_of(old, 'senate'),
                'to_coords': coords_of(row, 'senate'),
            }
            # reverse-link on the House chain: cut was actually a realignment
            hid = row.get('replaces_house_id')
            hub = by_id.get(hid)
            if hub and hub.get('senate'):
                hub['senate']['status'] = 'realigned'
                hub['senate']['sv_m'] = php(row.get('sv_php'))  # effective Senate amt after restatement
                hub['restated_by'] = {
                    'id': sid,
                    'title': row.get('senate_title'),
                    'sv_m': php(row.get('sv_php')),
                    'page': row.get('pdf_page'),
                    'reason': reason,
                    'from_coords': coords_of(old, 'hb') or coords_of(old, 'senate'),
                    'to_coords': coords_of(row, 'senate'),
                    'similarity': row.get('replaces_similarity'),
                    'cut_id': row['replaces_id'],
                }
        records.append(rec)
        by_id[sid] = rec

    def revision_key(region, title, amount, coordinates):
        # Keep the exact endpoint values and direction. Decimal ignores
        # differences in trailing zeros between the source documents.
        endpoints = {}
        point = r'(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)'
        for line in coordinates or ():
            match = re.fullmatch(r'\s*(START|END)\s*:\s*(.*?)\s*', line, re.I)
            if not match or match[1].upper() in endpoints:
                return None
            values_text = re.sub(r'(?i)\bSection\s+', '', match[2])
            values_text = re.sub(r',(?=\s*\d+\s*:)', ' ', values_text)
            single = re.fullmatch(point, values_text)
            if not single:
                single = re.fullmatch(r'(-?\d+\.\d+)°\s+(-?\d+\.\d+)°', values_text)
            if single:
                values = ((1, Decimal(single[1]), Decimal(single[2])),)
            elif re.fullmatch(rf'(?:\d+\s*:\s*{point}\s*)+', values_text):
                values = tuple(sorted(
                    (int(number), Decimal(lat), Decimal(lon))
                    for number, lat, lon in re.findall(rf'(\d+)\s*:\s*{point}', values_text)
                ))
                if len({value[0] for value in values}) != len(values):
                    return None
            else:
                return None
            endpoints[match[1].upper()] = values
        if not (region and title and amount and endpoints.keys() == {'START', 'END'}):
            return None
        if [p[0] for p in endpoints['START']] != [p[0] for p in endpoints['END']]:
            return None
        # Normalize punctuation and spacing, including "48- A" and "48-A".
        title_key = tuple(re.findall(r'\w+', title.casefold()))
        return region, title_key, amount, endpoints['START'], endpoints['END']

    def is_draft_correction(draft):
        return (draft.get('disposition') == 'list_revision'
                or 'correction of project coordinates' in (draft.get('remarks') or '').casefold())

    revisions = defaultdict(list)
    for ctrl, draft in da12.items():
        if draft.get('disposition') not in ('new', 'list_revision'):
            continue
        key = revision_key(
            draft.get('region_key'), draft.get('to_title'), draft.get('proposed_amount_php'),
            (draft.get('to_coordinates_raw') or '').splitlines(),
        )
        if key:
            revisions[key].append(ctrl)

    insertions = defaultdict(list)
    for rec in records:
        if rec['type'] != 'senate_insertion':
            continue
        row = a1[rec['id']]
        key = revision_key(rec['region'], row.get('senate_title'), row.get('sv_php'),
                           rec['senate']['senate_coords'])
        if not key:
            # A PDF extraction can move a trailing longitude into the title.
            # Restore only when each endpoint ends with an empty longitude.
            title = re.fullmatch(r'(.+?)\s+(\d{3}\.\d+)\s+(\d{3}\.\d+)', rec['title'])
            coordinates = rec['senate']['senate_coords'] or []
            if (title and len(coordinates) == 2
                    and all(re.search(r'\b1[4-9]\.\d+,\s*$', line) for line in coordinates)):
                repaired = [line.rstrip() + ' ' + longitude
                            for line, longitude in zip(coordinates, title.groups()[1:])]
                candidate = revision_key(rec['region'], title[1], row.get('sv_php'), repaired)
                if candidate and len(revisions.get(candidate, [])) == 1:
                    key = candidate
                    rec['title'] = title[1]
                    rec['senate'].update(senate_title=title[1], senate_coords=repaired,
                                         match='coordinates_recovered_from_title')
        if key:
            insertions[key].append(rec)

    for key, matches in revisions.items():
        targets = insertions.get(key, [])
        if len(matches) != 1 or len(targets) != 1:
            continue
        ctrl = matches[0]
        insertion = targets[0]
        house_id = (insertion.get('replaces') or {}).get('house_id')
        house = by_id.get(house_id)
        if (not house or (house.get('restated_by') or {}).get('id') != insertion['id']
                or ctrl in used_da5 or ctrl in used_da12):
            continue
        original = house.get('da12') or house.get('da5') or {}
        if original.get('disposition') != 'dropped' or not is_draft_correction(da12[ctrl]):
            continue
        if da12[ctrl]['disposition'] == 'new' and insertion['replaces']['reason'] not in ('coords', 'title_and_coords'):
            continue
        house['da_revision'] = {
            'ctrl': ctrl,
            'senate_id': insertion['id'],
            'da5': da_disp(ctrl, da5),
            'da12': da_disp(ctrl, da12),
        }
        used_da5.add(ctrl)
        used_da12.add(ctrl)

    # Recover exact continuations when NEP rows bypassed the House bill.
    nep_only_keys = defaultdict(list)
    for rec in records:
        if rec['type'] != 'nep_only':
            continue
        np = nep_title[rec['id']]
        title = np['title']
        coordinates = coords_raw_list(np) or []
        # A wrapped locality sometimes lands in the extracted GPS field.
        if (title.rstrip().endswith(',') and len(coordinates) == 3
                and ',' in coordinates[0] and ':' not in coordinates[0]):
            title = f'{title.rstrip()} {coordinates[0]}'
            coordinates = coordinates[1:]
        key = revision_key(rec['region'], title, np['amount_php'], coordinates)
        if key:
            nep_only_keys[key].append((rec, title, coordinates))

    original_da_keys = defaultdict(list)
    for ctrl, draft in da12.items():
        if draft.get('kind') == 'original':
            coords = draft.get('from_coordinates_raw')
            if not coords and draft.get('from_title') == draft.get('to_title'):
                coords = draft.get('to_coordinates_raw')
            key = revision_key(draft.get('region_key'), draft.get('from_title'),
                               draft.get('from_amount_php'), (coords or '').splitlines())
            if key:
                original_da_keys[key].append(ctrl)

    merged_senate_ids = set()
    for key, candidates in nep_only_keys.items():
        if len(candidates) != 1:
            continue
        rec, title, coordinates = candidates[0]
        rec['title'] = title
        rec['nep'].update(title=title, coords=coordinates)
        targets = insertions.get(key, [])
        if not rec['senate'] and len(targets) == 1 and not targets[0].get('replaces'):
            insertion = targets[0]
            rec['senate'] = {**insertion['senate'], 'status': 'reinstated',
                             'source_status': 'inserted', 'match': 'title_amount_endpoints'}
            merged_senate_ids.add(insertion['id'])

        controls = original_da_keys.get(key, [])
        if len(controls) != 1 or controls[0] in used_da5 or controls[0] in used_da12:
            continue
        ctrl = controls[0]
        for vintage, drafts in (('da5', da5), ('da12', da12)):
            if ctrl in drafts:
                rec[vintage] = {'ctrl': ctrl, **da_disp(ctrl, drafts)}
        used_da5.add(ctrl)
        used_da12.add(ctrl)
        draft = da12[ctrl]
        proposal = revision_key(draft.get('region_key'), draft.get('to_title'),
                                draft.get('proposed_amount_php'),
                                (draft.get('to_coordinates_raw') or '').splitlines())
        targets = insertions.get(proposal, [])
        if (not rec['senate'] and proposal and proposal[3:] == key[3:]
                and len(targets) == 1 and not targets[0].get('replaces')
                and targets[0]['id'] not in merged_senate_ids
                and not revisions.get(proposal)):
            insertion = targets[0]
            rec['senate'] = {**insertion['senate'], 'status': 'reinstated',
                             'source_status': 'inserted', 'match': 'da_revision_matches_senate'}
            merged_senate_ids.add(insertion['id'])
        if rec['senate']:
            senate_key = revision_key(rec['region'], rec['senate']['senate_title'],
                                      a1[rec['senate']['id']].get('sv_php'),
                                      rec['senate']['senate_coords'])
            if proposal and proposal == senate_key:
                rec['da_evidence'] = {'ctrl': ctrl, 'exact': True}

    records = [rec for rec in records if rec['id'] not in merged_senate_ids]

    # Include controls first introduced in November 12.
    for ctrl in dict.fromkeys([*da5, *da12]):
        if ctrl in used_da5 or ctrl in used_da12:
            continue
        p = da5.get(ctrl) or da12[ctrl]
        source = 'da5' if ctrl in da5 else 'da12'
        draft5 = da_disp(ctrl, da5)
        draft12 = da_disp(ctrl, da12)
        records.append({
            'id': f'{source}:{ctrl}', 'type': 'da_only',
            'region': p.get('region_key'),
            'region_label': region_label.get(p.get('region_key')),
            'title': p.get('to_title') or p.get('from_title'),
            'da5': {'id': ctrl, 'ctrl': ctrl, **draft5} if draft5 else None,
            'da12': {'id': ctrl, 'ctrl': ctrl, **draft12} if draft12 else None,
            'house_m': None, 'nep': None, 'senate': None, 'replaces': None,
        })

    # The annex records review outcomes against source lines and DA vintages.
    def flag_key(document, region, title, amount):
        return document, region, tuple(re.findall(r'\w+', (title or '').casefold())), amount

    flag_sources = defaultdict(list)
    flag_controls = defaultdict(list)
    for rec in records:
        nep = nep_title.get((rec.get('nep') or {}).get('id'))
        house = house_proj.get(rec['id'])
        for document, source in (('2027 NEP', nep), ('2027 GAB', house)):
            if source:
                key = flag_key(document, rec['region'], source['title'], source['amount_php'])
                flag_sources[key].append(rec)
        for ctrl in {draft['ctrl'] for draft in (rec.get('da5'), rec.get('da12')) if draft}:
            flag_controls[ctrl].append(rec)

    for vintage in ('nov5', 'nov12'):
        path = ROOT / 'other-analysis' / 'data' / f'fmr_flags_annex_{vintage}.csv'
        with path.open(newline='', encoding='utf-8-sig') as source:
            for flag in csv.DictReader(source):
                key = flag_key(flag['document'], senate_region_key(flag['region']),
                               flag['title'], int(flag['amount_php']))
                candidates = flag_sources.get(key) or flag_controls.get(flag['da_control_no'], [])
                if len(candidates) != 1:
                    continue
                candidates[0].setdefault('da_reviews', {}).setdefault(vintage, []).append({
                    'id': flag['flag_id'],
                    'document': flag['document'],
                    'issue': flag['issue_detail'],
                    'types': [item.strip() for item in flag['flag_types'].split(';') if item.strip()],
                    'status': flag['status'],
                    'remarks': flag['remarks'],
                    'evidence': flag['evidence'],
                    'endpoint_review': flag['endpoint_review'],
                    'replacement_ctrl': flag['da_replacement_control_no'],
                    'original_ctrl': flag['da_control_no'],
                })

    # A review annex can document a DA replacement across municipalities.
    # Preserve the Senate cut and insertion as separate source actions.
    replacement_sources = defaultdict(set)
    da_only_by_control = {}
    for rec in records:
        if rec['type'] == 'da_only':
            da_only_by_control[(rec['da12'] or rec['da5'])['ctrl']] = rec
        if (rec.get('senate') or {}).get('status') != 'cut':
            continue
        for finding in rec.get('da_reviews', {}).get('nov12', []):
            if (finding['replacement_ctrl'] and finding['status'].startswith('FIXED')
                    and finding['original_ctrl'] == (rec.get('da12') or {}).get('ctrl')
                    and (rec.get('da12') or {}).get('disposition') == 'dropped'):
                replacement_sources[finding['replacement_ctrl']].add(rec['id'])

    replacements_by_source = Counter(source for sources in replacement_sources.values() for source in sources)
    merged_da_ids = set()
    for key, controls in revisions.items():
        targets = insertions.get(key, [])
        if len(controls) != 1 or len(targets) != 1:
            continue
        ctrl = controls[0]
        target = targets[0]
        sources = replacement_sources.get(ctrl, set())
        da_only = da_only_by_control.get(ctrl)
        if target['id'] in merged_senate_ids or ctrl in used_da5 or ctrl in used_da12:
            continue
        if target.get('replaces'):
            house = by_id.get(target['replaces'].get('house_id')) or {}
            if ((house.get('restated_by') or {}).get('id') != target['id']
                    or house.get('da5') or house.get('da12')):
                continue
            target = house
        if ctrl in da5:
            target['da5'] = {'ctrl': ctrl, **da_disp(ctrl, da5)}
        target['da12'] = {'ctrl': ctrl, **da_disp(ctrl, da12)}
        target['da_evidence'] = {
            'ctrl': ctrl,
            'basis': 'normalized title, amount, and both endpoints',
            'remark': target['da12']['remark'],
            'kind': target['da12']['kind'],
            'exact': True,
        }
        if target['type'] == 'senate_insertion' and len(sources) == 1 and is_draft_correction(da12[ctrl]):
            original = by_id[next(iter(sources))]
            if replacements_by_source[original['id']] == 1:
                target['da_replacement_of'] = {'id': original['id'], 'title': original['title']}
                original['da_replacement'] = {
                    'id': target['id'], 'title': target['title'], 'ctrl': ctrl,
                    'amount_m': target['senate']['sv_m'],
                }
        if da_only:
            merged_da_ids.add(da_only['id'])

    # A dropped NEP control and the adjacent GPS correction in both drafts
    # can bridge the original endpoints to an exact DA–Senate match.
    original_nep_by_title = defaultdict(list)
    for key, candidates in nep_only_keys.items():
        original_nep_by_title[key[:3]].extend(rec for rec, _, _ in candidates)

    for key, targets in insertions.items():
        if len(targets) != 1:
            continue
        target = targets[0]
        if target['id'] in merged_senate_ids or target.get('da_replacement_of'):
            continue
        if not (target.get('da_evidence') or {}).get('exact'):
            continue
        originals = original_nep_by_title.get(key[:3], [])
        if len(originals) != 1 or originals[0].get('senate'):
            continue
        original = originals[0]
        for vintage in ('da5', 'da12'):
            dropped = original.get(vintage) or {}
            replacement = target.get(vintage) or {}
            if (dropped.get('disposition') != 'dropped'
                    or replacement.get('disposition') != 'new'
                    or not dropped.get('excel_row') or not replacement.get('excel_row')
                    or replacement['excel_row'] != dropped['excel_row'] + 1
                    or 'correction of project coordinates' not in (replacement.get('remark') or '').casefold()
                    or revision_key(target['region'], replacement.get('title'), key[2],
                                    replacement.get('to_coords')) != key
                    or (da5 if vintage == 'da5' else da12)[replacement['ctrl']]['proposed_amount_php'] != key[2]):
                break
        else:
            original['senate'] = {**target['senate'], 'status': 'reinstated',
                                  'source_status': 'inserted', 'match': 'da_coordinate_correction'}
            original['da_revision'] = {
                'ctrl': target['da12']['ctrl'], 'senate_id': target['id'],
                'da5': target['da5'], 'da12': target['da12'],
            }
            merged_senate_ids.add(target['id'])

    # Matching amounts and endpoints can surface a title or scope change.
    # Keep the source entries separate when the normalized titles differ.
    da_by_site = defaultdict(list)
    senate_by_site = defaultdict(list)
    for key, controls in revisions.items():
        da_by_site[(key[0], *key[2:])].extend((key, ctrl) for ctrl in controls)
    for key, targets in insertions.items():
        senate_by_site[(key[0], *key[2:])].extend((key, target) for target in targets)
    for site, drafts in da_by_site.items():
        targets = senate_by_site.get(site, [])
        if len(drafts) != 1 or len(targets) != 1:
            continue
        draft_key, ctrl = drafts[0]
        senate_key, target = targets[0]
        source = da_only_by_control.get(ctrl)
        if (draft_key == senate_key or not source or source['id'] in merged_da_ids
                or target['id'] in merged_senate_ids or target.get('replaces')
                or (target.get('da_evidence') or {}).get('exact')):
            continue
        target['da_evidence'] = {
            'ctrl': ctrl, 'basis': 'same amount and both endpoints; title differs',
            'id': source['id'], 'title': source['da12']['title'],
        }
        source['possible_senate_match'] = {'id': target['id'], 'title': target['title']}

    records = [rec for rec in records if rec['id'] not in merged_da_ids | merged_senate_ids]

    # Flag adjacent Senate cut/insert pairs whose route name was extended
    # while the amount and endpoints remained identical.
    senate_by_site = defaultdict(list)
    for rec in records:
        senate = rec.get('senate') or {}
        status = senate.get('status')
        if status not in ('cut', 'inserted') or rec.get('replaces') or rec.get('da_replacement_of') or rec.get('da_replacement'):
            continue
        row = a1[senate['id']]
        key = revision_key(rec['region'], rec['title'],
                           row.get('gab_php') if status == 'cut' else row.get('sv_php'),
                           (senate.get('hb_coords') if status == 'cut' else senate.get('senate_coords')))
        if key:
            senate_by_site[(key[0], *key[2:])].append((status, rec, row['row_index']))

    for site, candidates in senate_by_site.items():
        if len(candidates) != 2:
            continue
        cut, insertion = sorted(candidates, key=lambda item: item[2])
        if cut[0] != 'cut' or insertion[0] != 'inserted' or insertion[2] != cut[2] + 1:
            continue
        original, revised = cut[1], insertion[1]
        evidence = revised.get('da_evidence') or {}
        if evidence.get('exact'):
            ctrl = evidence['ctrl']
            for vintage, drafts in (('da5', da5), ('da12', da12)):
                dropped = original.get(vintage) or {}
                revision = revised.get(vintage) or {}
                draft = drafts.get(ctrl) or {}
                draft_key = revision_key(draft.get('region_key'), draft.get('to_title'),
                                         draft.get('proposed_amount_php'),
                                         (draft.get('to_coordinates_raw') or '').splitlines())
                if (dropped.get('disposition') != 'dropped'
                        or revision.get('disposition') != 'list_revision'
                        or revision.get('ctrl') != ctrl
                        or not dropped.get('excel_row')
                        or revision.get('excel_row') != dropped['excel_row'] + 1
                        or 'correction of project title' not in (revision.get('remark') or '').casefold()
                        or not draft_key or (draft_key[0], *draft_key[2:]) != site):
                    break
            else:
                basis = 'adjacent title correction in both DA drafts'
                original['da_replacement'] = {
                    'id': revised['id'], 'title': revised['title'], 'ctrl': ctrl,
                    'amount_m': revised['senate']['sv_m'], 'basis': basis,
                }
                revised['da_replacement_of'] = {
                    'id': original['id'], 'title': original['title'], 'basis': basis,
                }
                continue

        original_route = re.split(r'\bfmr\b', original['title'].casefold(), maxsplit=1)[0].strip()
        revised_route = re.split(r'\bfmr\b', revised['title'].casefold(), maxsplit=1)[0].strip()
        if revised_route.startswith(original_route + ' to '):
            original['possible_senate_restatement'] = {
                'id': revised['id'], 'title': revised['title'], 'amount_m': revised['senate']['sv_m'],
            }
            revised['possible_senate_restatement'] = {'id': original['id'], 'title': original['title']}

    # ---- localities: municipality-level grouping -------------------------
    # Parse '..., Brgy X[, Municipality], Province' from each record's best
    # title; group chains + senate actions per municipality for the
    # grouping-analysis panel (where realignments actually happen).
    PROVINCE_HINTS = (
        'ilocos', 'pangasinan', 'la union', 'cagayan', 'isabela', 'nueva',
        'tarlac', 'pampanga', 'bulacan', 'bataan', 'zambales', 'aurora',
        'quezon', 'laguna', 'batangas', 'cavite', 'rizal', 'marinduque',
        'occidental mindoro', 'oriental mindoro', 'palawan', 'romblon',
        'albay', 'camarines', 'catanduanes', 'masbate', 'sorsogon',
        'iloilo', 'lloilo', 'capiz', 'aklan', 'antique', 'guimaras', 'negros',
        'cebu', 'bohol', 'siquijor', 'biliran', 'leyte', 'samar',
        'western samar', 'eastern samar', 'northern samar', 'southern leyte',
        'davao', 'agusan', 'surigao', 'zamboanga', 'basilan', 'sulu',
        'tawi-tawi', 'camiguin', 'misamis', 'bukidnon', ' Lanao', 'lanao',
        'north cotabato', 'cotabato', 'sultan kudarat', 'sarangani',
        'south cotabato', 'maguindanao', 'sulu', 'dinagat', 'compostela',
        'ifugao', 'kalinga', 'apayao', 'abra', 'benguet', 'mountain province',
        'batanes', 'quirino', 'metro manila', 'ncr',
    )

    CITY_HINTS = (
        'baguio city', 'zamboanga city', 'butuan city', 'iligan city',
        'cagayan de oro city', 'cagaya de oro city', 'isabela city',
        'bacolod city', 'iloilo city', 'lloilo city', 'batangas city',
        'laoag city', 'dagupan city', 'san carlos city', ' Angeles city',
        'angeles city', 'ozamiz city', 'tangub city', 'orca city', 'oroc city',
        'navotas city', 'makati city', 'davao city', 'cebu city', 'quezon city',
        'lapu-lapu city', 'mandaue city', 'tagbilaran city', 'tacloban city',
        'pagadian city', 'dipolog city', 'digos city', 'kidapawan city',
        'cotabato city', 'marawi city', 'general santos city', 'samal city',
        'tagum city', 'mati city', 'santiago city', ' cabanatuan city',
        'cabanatuan city', 'gapan city', 'palayan city', 'san jose city',
        'science city of munoz', 'munoz city', 'olongapo city', 'tarlac city',
        'malolos city', 'meycauayan city', 'san jose del monte city',
        'city of san jose del monte', 'vigan city', 'candon city', 'batac city',
        'alaminos city', 'usta cruz city', 'santa cruz city', 'lucena city',
        'tuguegarao city', 'tabuk city', 'naga city', 'iriga city',
        'legazpi city', 'ligao city', 'masbate city', 'sorsogon city',
        'roxas city', 'passi city', 'himamaylan city', 'kabankalan city',
        'cadiz city', 'sagay city', 'san carlos city, negros', 'bogo city',
        'toledo city', 'danao city', 'carcar city', 'bais city', 'bayawan city',
        'canlaon city', 'dumaguete city', 'guihulngan city', 'tanjay city',
        'Ormoc city', 'ormoc city', 'baybay city', 'borongan city',
        'calbayog city', 'catbalogan city', 'maasin city', 'bogo', 'escalante',
        'himamaylan', 'san carlos', 'silay city', 'talisay city', 'victorias',
        'sipalay city', 'hiniñgan city', 'la carlota city', 'san carlos city',
    )

    def locality_tokens(name):
        name = re.sub(r'\bmt\.?(?=\s)', 'mountain', name.casefold())
        return ' '.join(re.findall(r'\w+', name))

    catalog = {}
    with (ROOT / 'PSGC2LEG/data/psgc_locations.jsonl').open() as source:
        for line in source:
            if line.strip():
                place = json.loads(line)
                catalog[place['code']] = place

    province_municipalities = defaultdict(set)
    for place in catalog.values():
        parent = catalog.get(place['parent_code'])
        if place['level'] in ('city', 'municipality') and parent and parent['level'] == 'province':
            province = parent['name'].lower()
            municipality = place['name']
            name = locality_tokens(f'{municipality} {province}')
            province_municipalities[name].add((province, municipality))

    def catalog_locality(title):
        # Require an explicit municipality and province at the end of the
        # title. A barangay name alone cannot establish its municipality.
        tokens = locality_tokens(title).split()
        matches = set()
        for index in range(len(tokens)):
            matches.update(province_municipalities.get(' '.join(tokens[index:]), ()))
        if len(matches) == 1:
            return next(iter(matches))
        return None

    def locality_of(rec):
        """(province, municipality) from the record's best title."""
        def parse(t):
            if not t:
                return None
            parts = [p.strip() for p in t.split(',') if p.strip()]
            if len(parts) < 2:
                return None
            # last part must look like a province, else the title is malformed
            prov = parts[-1].lower()
            # strip trailing coordinate junk the Senate prints after the title
            prov_clean = re.split(r'\b\d{2,}\.\d', prov)[0].strip()
            # highly-urbanized cities stand alone: '..., Brgy. X, Baguio City'
            # (must be checked before provinces — 'Zamboanga City' contains
            # the province hint 'zamboanga' but is its own unit)
            if any(c in prov_clean for c in CITY_HINTS):
                muni = parts[-1].strip()
                return prov_clean, muni
            if any(h in prov_clean for h in PROVINCE_HINTS):
                muni = None
                if len(parts) >= 3 and not re.match(r'^(brgy|barangay|sitio|purok)\b',
                                                    parts[-2], re.I):
                    muni = parts[-2].strip()
                return prov_clean, muni
            return None
        # prefer the senate's final title, but fall back to the plain record
        # title when the annex prints coordinates after the place names
        t = None
        if rec.get('senate'):
            t = (rec['senate'].get('senate_title')
                 or rec['senate'].get('hb_title'))
        loc = parse(t) or parse(rec.get('title'))
        if not loc or not loc[1]:
            for title in (t, rec.get('title')):
                if title:
                    fallback = catalog_locality(title)
                    if fallback:
                        return fallback
            return None
        return loc

    # ---- per-stage actions: classify each transition on this chain ------
    # actions.nep_house: what the House did to the NEP line
    # actions.house_da:  the DA working draft's disposition (Nov 12 wins)
    # actions.house_senate: the Senate annex action (same vocabulary as
    #     senate.status; 'unchanged' = not listed in Annex A-1)
    for rec in records:
        acts = {}
        if rec['type'] == 'nep_only':
            acts['nep_house'] = ('reinstated'
                                 if (rec.get('senate') or {}).get('status') == 'reinstated'
                                 else 'dropped')
        elif rec['type'] == 'house':
            acts['nep_house'] = 'house_insertion' if not rec.get('nep') else 'carried'
        da = rec.get('da12') or rec.get('da5')
        if rec.get('da_revision'):
            acts['house_da'] = rec['da_revision']['da12']['disposition']
        elif da:
            acts['house_da'] = da.get('disposition') or None
        elif rec.get('nep') or rec.get('house_m') is not None:
            acts['house_da'] = 'no_da'
        sen = rec.get('senate')
        if sen:
            acts['house_senate'] = sen.get('status')
        elif rec['type'] == 'house':
            acts['house_senate'] = 'unchanged'
        elif rec['type'] == 'nep_only':
            acts['house_senate'] = 'left_at_nep'
        rec['actions'] = acts

    action_totals = {stage: Counter() for stage in ('nep_house', 'house_da', 'house_senate')}
    for rec in records:
        for stage, action in rec['actions'].items():
            if action:
                action_totals[stage][action] += 1

    paired_insertions = {rec['restated_by']['id'] for rec in records if rec.get('restated_by')}
    possible_da_sources = {rec['id']: rec for rec in records if rec.get('possible_senate_match')}
    paired_corrections = {
        rec['id']: match for rec in records
        if 'amount_m' in (match := rec.get('da_replacement') or rec.get('possible_senate_restatement', {}))
    }
    possible_insertions = {match['id'] for match in paired_corrections.values()}
    records_by_id = {rec['id']: rec for rec in records}
    locs = {}
    for rec in records:
        loc = locality_of(rec)
        # stamp the parsed locality on the record so the web UI filters on
        # exact fields instead of regex-guessing from titles
        rec['province'] = loc[0] if loc else None
        rec['municipality'] = loc[1] if loc else None
        if (not loc or not loc[1] or rec['id'] in paired_insertions
                or rec['id'] in possible_da_sources or rec['id'] in possible_insertions):
            continue
        prov, muni = loc
        key = f'{prov}|{muni}'
        e = locs.setdefault(key, {'key': key, 'province': prov,
                                  'municipality': muni,
                                  'region': rec.get('region'),
                                  'region_label': rec.get('region_label'),
                                  'chains': 0, 'nep_m': 0.0, 'house_m': 0.0,
                                  'senate_m': 0.0, 'senate_from_m': 0.0,
                                  'status': Counter(), 'actions': {
                                      'nep_house': Counter(),
                                      'house_da': Counter(),
                                      'house_senate': Counter(),
                                  }, 'links': []})
        e['chains'] += 1
        e['nep_m'] += (rec.get('nep') or {}).get('amount_m') or 0
        e['house_m'] += rec.get('house_m') or 0
        sen = rec.get('senate')
        if sen:
            eff = (rec.get('restated_by') or {}).get('sv_m', sen.get('sv_m'))
            possible_amount = paired_corrections.get(rec['id'], {}).get('amount_m')
            e['senate_m'] += (eff if possible_amount is None else possible_amount) or 0
            e['senate_from_m'] += sen.get('gab_m') or rec.get('house_m') or 0
            e['status'][sen.get('status', 'none')] += 1
        # per-stage action counts for the grouping panel
        source = possible_da_sources.get((rec.get('da_evidence') or {}).get('id'), {})
        display_actions = {**source.get('actions', {}), **rec['actions']}
        if rec['id'] in paired_corrections:
            display_actions['house_senate'] = 'possible_restatement'
        if rec.get('da_replacement'):
            replacement = records_by_id[rec['da_replacement']['id']]
            display_actions['house_da'] = replacement['actions']['house_da']
        for stage, act in display_actions.items():
            if act:
                e['actions'][stage][act] += 1
        # capture linked-pair ids for grouping analysis
        if rec.get('restated_by'):
            e['links'].append({'kind': 'realigned',
                               'house_id': rec['id'],
                               'senate_id': rec['restated_by']['id']})
        elif rec.get('replaces'):
            e['links'].append({'kind': 'realigned',
                               'house_id': rec['replaces'].get('house_id'),
                               'senate_id': rec['id']})
        if (sen or {}).get('status') == 'reinstated':
            e['links'].append({'kind': 'reinstated',
                               'nep_id': rec['id'], 'senate_id': sen['id']})
    loc_rows = []
    for e in locs.values():
        d = dict(e)
        d['status'] = dict(e['status'])
        d['actions'] = {stage: dict(cnt) for stage, cnt in e['actions'].items()}
        d['nep_m'] = round(d['nep_m'], 1)
        d['house_m'] = round(d['house_m'], 1)
        d['senate_m'] = round(d['senate_m'], 1)
        d['senate_from_m'] = round(d['senate_from_m'], 1)
        d['churn'] = sum(v for k, v in d['status'].items()
                         if k in ('cut', 'realigned', 'reinstated', 'reduced'))
        d['total_links'] = len(d.pop('links'))
        loc_rows.append(d)
    loc_rows.sort(key=lambda x: -x['churn'])

    # ---- regions aggregate ------------------------------------------------
    regs = {}
    for r in wb['regions']:
        regs[r['id']] = {'key': r['id'], 'label': r['label'],
                         'nep_m': php(r.get('nep_php')),
                         'house_m': php(r.get('house_php')),
                         'da_m': php(r.get('da_php'))}
    # senate totals per region_key from a1 rows
    sen_tot = defaultdict(lambda: [0, 0, Counter()])
    for row in a1.values():
        rk = senate_region_key(row.get('region'))
        if not rk:
            continue
        sen_tot[rk][0] += row.get('gab_php') or 0
        sen_tot[rk][1] += row.get('sv_php') or 0
        sen_tot[rk][2][senate_status(row)] += 1
    for rk, (gab, sv, cnt) in sen_tot.items():
        e = regs.setdefault(rk, {'key': rk, 'label': region_label.get(rk, rk)})
        e['senate_from_m'] = php(gab)
        e['senate_m'] = php(sv)
        e['senate_status'] = dict(cnt)
    # status counts over records (house-hub view: realigned supersedes cut)
    rec_status = Counter(r['senate']['status'] for r in records
                         if r.get('senate') and r['type'] == 'house')
    type_counts = Counter(r['type'] for r in records)
    totals = {
        'nep_m': php(sum(p['amount_php'] for p in nep_title.values())),
        'house_m': php(sum(p['amount_php'] for p in house_proj.values())),
        'senate_from_m': php(sum(r['gab_php'] or 0 for r in a1.values())),
        'senate_m': php(sum(r['sv_php'] or 0 for r in a1.values())),
        'counts': {
            'nep': len(nep_title), 'house': len(house_proj),
            'senate_rows': len(a1),
            **{k: v for k, v in type_counts.items()},
            'senate_insertion': type_counts['senate_insertion'] + len(merged_senate_ids),
        },
        'actions': action_totals,
        'house_insertion_m': round(sum(r['house_m'] for r in records
                                      if r['actions'].get('nep_house') == 'house_insertion'), 1),
        'house_annex_matches': sum(1 for r in records if r['type'] == 'house' and r.get('senate')),
        'senate_status': dict(rec_status),
        'replaces_links': sum(1 for r in records if r.get('replaces')),
        'realigned_house': sum(1 for r in records if r.get('restated_by')),
        'true_cuts': rec_status.get('cut', 0),
        'reinstated_nep': sum(1 for r in records
                              if (r.get('senate') or {}).get('status') == 'reinstated'),
    }

    nep_amounts = {key: row['amount_php'] for key, row in nep_title.items()}
    house_amounts = {key: row['amount_php'] for key, row in house_proj.items()}
    house_to_nep = {row['id']: row['nep']['id'] for row in records
                    if row['type'] == 'house' and row.get('nep')}
    stage_changes = {
        'nep_house': summarize_budget_changes(
            linked_budget_pairs(nep_amounts, house_amounts, house_to_nep),
            sum(nep_amounts.values()), sum(house_amounts.values())),
        'house_senate': summarize_budget_changes(
            ((row['gab_php'], row['sv_php']) for row in a1.values()),
            sum(house_amounts.values()), sum(row['sv_php'] or 0 for row in a1.values())),
    }

    out_dir = WEB / 'public' / 'data' / 'fmr'
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_p = ROOT / 'data_formalization' / 'data' / 'ledger' / 'fmr.jsonl'

    manifest = {
        'program': 'fmr',
        'generated_at': runs[-1]['at'] if runs else None,
        'ledger_sha256': sha256(ledger_p),
        'records': len(records),
        'validation_runs': runs,
        'totals': totals,
        'stage_changes': stage_changes,
    }
    (out_dir / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    (out_dir / 'projects.json').write_text(json.dumps(records, ensure_ascii=False) + '\n')
    (out_dir / 'localities.json').write_text(
        json.dumps(loc_rows, ensure_ascii=False, indent=1) + '\n')
    (out_dir / 'regions.json').write_text(
        json.dumps([regs[k] for k in sorted(regs, key=region_sort_key)],
                   ensure_ascii=False, indent=1) + '\n')
    # lineage mermaid
    try:
        (out_dir / 'lineage.json').write_text(json.dumps(
            {'mermaid': G.graph()}, ensure_ascii=False, indent=1) + '\n')
    except Exception as ex:  # noqa: BLE001
        (out_dir / 'lineage.json').write_text(json.dumps({'error': str(ex)}) + '\n')
    # ---- static download exports (CSV set + JSON) ------------------------
    export_dir = WEB / 'public' / 'data' / 'export' / 'fmr'
    export_dir.mkdir(parents=True, exist_ok=True)

    simple_cols = ['id', 'chain_type', 'title', 'region', 'region_label',
                   'province', 'municipality',
                   'nep_amount_php', 'house_amount_php',
                   'da5_proposed_php', 'da12_proposed_php',
                   'senate_id', 'senate_pdf_page', 'senate_status',
                   'senate_gab_php', 'senate_sv_php',
                   'senate_region_printed', 'senate_region_key',
                   'action_nep_house', 'action_house_da', 'action_house_senate',
                   'match_house_senate', 'review_flagged', 'review_fixed']

    def chain_simple(rec):
        sen = rec.get('senate') or {}
        return {
            'id': rec['id'], 'chain_type': rec['type'], 'title': rec.get('title'),
            'region': rec.get('region'), 'region_label': rec.get('region_label'),
            'province': rec.get('province'), 'municipality': rec.get('municipality'),
            'nep_amount_php': pesos((rec.get('nep') or {}).get('amount_m')),
            'house_amount_php': pesos(rec.get('house_m')),
            'da5_proposed_php': pesos((rec.get('da5') or {}).get('proposed_m')),
            'da12_proposed_php': pesos((rec.get('da12') or {}).get('proposed_m')),
            'senate_id': sen.get('id'), 'senate_pdf_page': sen.get('page'),
            'senate_status': sen.get('status'),
            'senate_gab_php': pesos(sen.get('gab_m')), 'senate_sv_php': pesos(sen.get('sv_m')),
            'senate_region_printed': sen.get('region_label'),
            'senate_region_key': rec.get('region'),
            'action_nep_house': rec.get('actions', {}).get('nep_house'),
            'action_house_da': rec.get('actions', {}).get('house_da'),
            'action_house_senate': rec.get('actions', {}).get('house_senate'),
            'match_house_senate': sen.get('match'),
            'review_flagged': bool(rec.get('da_reviews')),
            'review_fixed': any(f.get('status', '').startswith('FIXED')
                                for vintage in (rec.get('da_reviews') or {}).values()
                                for f in vintage),
        }

    n_simple = write_csv(export_dir / 'chains-simple.csv',
                         (chain_simple(r) for r in records), simple_cols)

    # full: every scalar, stage-prefixed, arrays JSON-encoded
    SKIP = {'actions', 'subst_candidates', 'da_reviews', 'links'}
    NEST_SUB = {'nep': 'nep_', 'senate': 'senate_', 'da5': 'da5_', 'da12': 'da12_',
                'replaces': 'replaces_', 'restated_by': 'restated_by_'}

    def flatten(rec, prefix=''):
        out = {}
        for key, value in rec.items():
            if key in SKIP:
                continue
            if key in NEST_SUB and isinstance(value, dict):
                out.update(flatten(value, NEST_SUB[key]))
            else:
                out[prefix + key] = value
        return out

    full_rows = [flatten(r) for r in records]
    full_cols = sorted({k for r in full_rows for k in r})
    # put identity columns first for readability
    for lead in ('id', 'type', 'title', 'region', 'region_label'):
        full_cols.remove(lead)
        full_cols.insert(0, lead)
    full_rows = [{**f, 'actions': json.dumps(r.get('actions'), ensure_ascii=False)}
                 for f, r in zip(full_rows, records)]
    full_cols.append('actions')
    n_full = write_csv(export_dir / 'chains-full.csv', full_rows, full_cols)

    # findings: one row per review finding
    finding_rows = []
    for rec in records:
        for vintage, findings in (rec.get('da_reviews') or {}).items():
            for f in findings:
                finding_rows.append({'chain_id': rec['id'], 'vintage': vintage,
                                     **{k: f.get(k) for k in
                                        ('id', 'document', 'issue', 'types', 'status',
                                         'remarks', 'evidence', 'endpoint_review')}})
    finding_cols = ['chain_id', 'vintage', 'id', 'document', 'issue', 'types',
                    'status', 'remarks', 'evidence', 'endpoint_review']
    n_findings = write_csv(export_dir / 'findings.csv', finding_rows, finding_cols)

    # rollups: the annex's printed heading subtotals with leaf reconciliation
    rollup_rows = []
    for name, sub in sorted(a1_rollups.items()):
        leaves = [r for r in a1.values() if r.get('region') == name]
        rollup_rows.append({
            'program': 'fmr', 'annex': 'A-1', 'level': 'region',
            'name_printed': name,
            'gab_php': sub['gab_php'], 'sv_php': sub['sv_php'],
            'pdf_page': sub['pdf_page'], 'leaf_rows': len(leaves),
            'leaf_gab_sum_php': sum(r.get('gab_php') or 0 for r in leaves),
            'leaf_sv_sum_php': sum(r.get('sv_php') or 0 for r in leaves),
            'reconciles': (sum(r.get('gab_php') or 0 for r in leaves) == sub['gab_php']
                           and sum(r.get('sv_php') or 0 for r in leaves) == sub['sv_php']),
        })
    rollup_cols = ['program', 'annex', 'level', 'name_printed', 'gab_php', 'sv_php',
                   'pdf_page', 'leaf_rows', 'leaf_gab_sum_php', 'leaf_sv_sum_php', 'reconciles']
    n_rollups = write_csv(export_dir / 'rollups.csv', rollup_rows, rollup_cols)

    full_doc = {
        'program': 'fmr',
        'description': 'FMR provenance explorer full export — verbatim chain '
                       'records plus manifest. See chains-simple.csv for the '
                       'table view and SHA256SUMS.txt for file hashes.',
        'manifest': manifest,
        'chains': records,
    }
    (export_dir / 'full.json').write_text(
        json.dumps(full_doc, ensure_ascii=False) + '\n', encoding='utf-8')
    write_sums(export_dir, ['chains-simple.csv', 'chains-full.csv',
                            'findings.csv', 'rollups.csv', 'full.json'])
    print(f'exports: simple={n_simple} full={n_full} findings={n_findings} '
          f'rollups={n_rollups} -> {export_dir.relative_to(ROOT)}')

    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--program', default='fmr')
    args = ap.parse_args()
    if args.program == 'fmr':
        m = export_fmr()
    else:
        raise SystemExit(f'program {args.program} not yet wired')
    print(json.dumps(m['totals'], indent=1))
    print(f"records={m['records']} -> web/public/data/{args.program}/")
    return 0


if __name__ == '__main__':
    sys.exit(main())
