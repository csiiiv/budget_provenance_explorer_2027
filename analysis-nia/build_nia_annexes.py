#!/usr/bin/env python3
"""Build the two annex CSVs for the PBC/BetterGov message on NIA FY2027 NEP.

Mirrors the DA-FMR annex discipline (PBC_DA_FMR_NEP_active_778_validated.csv):

  nia_nep_annex_full_nov13.csv        every NEP-existent submitted row (792)
                                     with program/subprogram, amounts, funding
                                     side, full submission-title lifecycle
                                     (oct10 -> nov13), start/end coordinates
                                     where printed, PSGC-where evidence,
                                     boundary-distance adjudication, status,
                                     and remarks

  nia_nep_annex_flagged_nov13.csv     only rows with >=1 flag (fixed, pending,
                                     resolved-by-evidence), one row per row x
                                     flag-category with disposition, issue and
                                     resolution remarks, evidence, coordinates
                                     and boundary adjudication

Sources: submitted-list, flags ledger, boundary-distance artifacts, and the
Oct 10 / Nov 13 NIA workbooks (all agency-provided).
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).resolve().parent / 'data'

COORD = re.compile(
    r"(\d{1,2})[°˚]\s?(\d{1,2})[′']\s?([\d.]+)[″\"]*\s?([NS])[,\s]+"
    r"(\d{1,3})[°˚]\s?(\d{1,2})[′']\s?([\d.]+)[″\"]*\s?([EW])")
START = re.compile(r"Start\s*[-–:]?\s*" + COORD.pattern, re.I)
END = re.compile(r"End\s*[-–:]?\s*" + COORD.pattern, re.I)


def dms(m):
    lat = int(m.group(1)) + int(m.group(2)) / 60 + float(m.group(3)) / 3600
    lon = int(m.group(5)) + int(m.group(6)) / 60 + float(m.group(7)) / 3600
    if m.group(4) == 'S':
        lat = -lat
    if m.group(8) == 'W':
        lon = -lon
    return lat, lon


def load_workbook(path, sheet='DETAILS 2027', *, submission_only):
    """row -> (label, submission_title, region, province, nep, hgab)"""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet]
    ctx = {'region': '', 'province': ''}
    out = {}
    for i, row in enumerate(ws.iter_rows(min_row=9, max_col=25, values_only=True), start=9):
        for f, ci in (('region', 4), ('province', 5)):
            v = row[ci]
            if isinstance(v, str) and v.strip():
                ctx[f] = v.strip()
        label, sub = row[6], row[21] if len(row) > 21 else None
        if not label and not row[7] and not row[8] and isinstance(sub, str) and sub.strip() and row[22]:
            submission_only.append({
                'row': i, 'submission_title': re.sub(r'\s+', ' ', sub.strip()),
                'submission_amount_php': row[22], **ctx,
            })
        if isinstance(label, str) and label.strip():
            out[i] = {
                'label': re.sub(r'\s+', ' ', label.strip()),
                'sub': re.sub(r'\s+', ' ', sub.strip()) if isinstance(sub, str) else '',
                'region': ctx['region'], 'province': ctx['province'] or '',
                'nep': row[7] or 0, 'hgab': row[8] or 0,
            }
    return out


def split_coords(sub):
    """-> (start_lat, start_lon, end_lat, end_lon, coords_raw)"""
    if not sub:
        return '', '', '', '', ''
    m = COORD.search(sub)
    if not m:
        return '', '', '', '', ''
    lat1, lon1 = dms(m)
    ms, me = START.search(sub), END.search(sub)
    lat2 = lon2 = ''
    if ms and me:
        lat2, lon2 = dms(me)
    raw = m.group(0)
    if ms:
        raw = ms.group(0)
    if me:
        raw = (raw + ' / ' + me.group(0)).strip(' /')
    return (f'{lat1:.6f}', f'{lon1:.6f}',
            f'{lat2:.6f}' if lat2 != '' else '', f'{lon2:.6f}' if lon2 != '' else '',
            raw)


def main():
    submitted = list(csv.DictReader((DATA / 'nia_submitted_list_status_nov13.csv').open()))
    ledger = list(csv.DictReader((DATA / 'nia_flags_ledger_nov13.csv').open()))
    bd = list(csv.DictReader((DATA / 'nia_coord_boundary_dist_nov13.csv').open()))

    submission_only = {'oct10': [], 'nov13': []}
    nov13 = load_workbook(ROOT / 'NIA_DATA' / 'NIA_NEP_2026-11-13.xlsx',
                          submission_only=submission_only['nov13'])
    oct10 = {}
    for cand in (ROOT / 'NIA_DATA' / 'NIA FY 2027 NEP OCTOBER 10 1043PM.xlsx',
                 ROOT / 'NIA_DATA' / 'NIA%20FY%202027%20NEP%20OCTOBER%2010%201043PM.xlsx'):
        if cand.exists():
            oct10 = load_workbook(cand, submission_only=submission_only['oct10'])
            break
    (DATA / 'nia_submission_only.json').write_text(
        json.dumps(submission_only, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )

    bd_by_row = defaultdict(list)
    for p in bd:
        if p['verdict'] != 'ok':
            bd_by_row[p['nov13_row']].append(p)

    def canon(t):
        return ' '.join(''.join(c for c in (t or '').lower() if c.isalnum() or c.isspace()).split())

    def remarks_for(status, open_flags, coord_ev, fixes):
        parts = []
        if fixes:
            parts.append(fixes)
        if status == 'PENDING' and open_flags:
            parts.append('Pending: ' + open_flags.replace(';', ', '))
        if coord_ev and 'outside_booked' in coord_ev:
            parts.append('Coordinates contradict booking')
        return '; '.join(parts)

    # ---------------- Annex 1: full NEP list ----------------
    ledger_by_row = defaultdict(list)
    for l in ledger:
        if l['workbook_row_nov13']:
            ledger_by_row[l['workbook_row_nov13']].append(l)

    full_out = []
    for r in submitted:
        row = r['nov13_row']
        wb = nov13.get(int(row)) if row.isdigit() else None
        sub = wb['sub'] if wb else ''
        slat, slon, elat, elon, craw = split_coords(sub)
        ev = bd_by_row.get(row, [])
        parts = []
        for p in ev[:2]:
            d = p['dist_to_booked_boundary_m'] or '-'
            if p['verdict'] in ('outside_booked', 'near_boundary'):
                parts.append(f"{p['role']}: {p['verdict']} ({d} m outside booked {p['province']}, in {p['psgc_where']})")
            else:
                parts.append(f"{p['role']}: {p['verdict']} ({p['bad_reason']})")
        coord_ev = ' | '.join(parts)
        oct = oct10.get(int(r['oct10_row'])) if r.get('oct10_row', '').isdigit() else None
        fixes = '; '.join(l['resolution_detail'] for l in ledger_by_row.get(row, [])
                          if l['disposition'] in ('re_assigned', 'justification_added',
                                                  'justification_refined', 'distinct_confirmed'))
        sub_revised = 'yes' if (oct and wb and canon(oct['sub']) != canon(wb['sub'])) else ('no' if oct else '')
        title_revised = 'yes' if (oct and wb and (canon(oct['label']) != canon(wb['label'])
                                                   or sub_revised == 'yes')) else ('no' if oct else '')
        if fixes and bd_by_row.get(row):
            fixes += " — but NIA's own Start/End coordinates contradict the booking"
        full_out.append({
            'nov13_row': row,
            'status_nov13': r['status_nov13'],
            'program': r['program'], 'subprogram': r['subprogram'],
            'category': r['category'],
            'region': r['region'], 'province': r['province'],
            'title_nov13': r['title'],
            'title_oct10': oct['label'] if oct else '',
            'title_revised': title_revised,
            'submission_title_oct10': oct['sub'] if oct else '',
            'submission_title': sub,
            'nep_amount_php': r['nep_amount_php'],
            'hgab_amount_php': r['hgab_amount_php'],
            'funding_side': r['funding_side'],
            'start_lat': slat, 'start_lon': slon,
            'end_lat': elat, 'end_lon': elon,
            'coordinates_raw': craw,
            'psgc_where_start': next((p['psgc_where'] for p in ev if p['role'] == 'start'), ''),
            'psgc_where_end': next((p['psgc_where'] for p in ev if p['role'] == 'end'), ''),
            'coordinate_evidence': coord_ev,
            'open_flags': r['open_flags'],
            'remarks': remarks_for(r['status_nov13'], r['open_flags'], coord_ev, fixes),
        })

    with (DATA / 'nia_nep_annex_full_nov13.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(full_out[0].keys()))
        w.writeheader()
        w.writerows(full_out)

    # ---------------- Annex 2: flagged list ----------------
    sub_by_row = {r['nov13_row']: r for r in submitted}

    def canon(t):
        return ' '.join(''.join(c for c in (t or '').lower() if c.isalnum() or c.isspace()).split())
    sub_by_title = defaultdict(list)
    for r in submitted:
        sub_by_title[(canon(r['title']), r['region'])].append(r)

    ledger_by_row2 = defaultdict(list)
    for l in ledger:
        if l['workbook_row_nov13']:
            ledger_by_row2[l['workbook_row_nov13']].append(l)
    sub_rows = {r['nov13_row'] for r in submitted}
    orphan_flags = [l for l in ledger
                    if not l['workbook_row_nov13'] or l['workbook_row_nov13'] not in sub_rows]
    for l in orphan_flags:
        key = (canon(l['title']), l['region_nov13'] or '')
        cands = sub_by_title.get(key) or [r for r in submitted if canon(r['title']) == canon(l['title'])]
        if cands:
            l2 = dict(l)
            if len(cands) > 1:
                l2['issue_detail'] = (l2['issue_detail'] + ' [pair/cluster flag: rows '
                                      + ','.join(sorted(c['nov13_row'] for c in cands)) + ']').strip()
            ledger_by_row2[cands[0]['nov13_row']].append(l2)

    status_order = {'PENDING': 0, 'FIXED': 1, 'RESOLVED-BY-EVIDENCE': 2}
    flagged_out = []
    for row, flags in ledger_by_row2.items():
        s = sub_by_row.get(row, {})
        wb = nov13.get(int(row)) if row.isdigit() else None
        slat, slon, elat, elon, craw = split_coords(wb['sub'] if wb else '')
        ev = bd_by_row.get(row, [])
        parts = []
        for p in ev[:2]:
            d = p['dist_to_booked_boundary_m'] or '-'
            if p['verdict'] in ('outside_booked', 'near_boundary'):
                parts.append(f"{p['role']}: {d} m outside booked {p['province']}, in {p['psgc_where']}")
            else:
                parts.append(f"{p['role']}: {p['bad_reason']}")
        coord_ev = ' | '.join(parts)
        for l in flags:
            flagged_out.append({
                'nov13_row': row,
                'flag_id': l['flag_id'],
                'status_nov13': l['status_nov13'],
                'disposition': l['disposition'],
                'flag_category': l['flag_category'],
                'title': l['title'] or s.get('title', ''),
                'region': l['region_nov13'] or s.get('region', ''),
                'province': l['province_nov13'] or s.get('province', ''),
                'nep_amount_php': l['nep_amount_php'],
                'start_lat': slat, 'start_lon': slon,
                'end_lat': elat, 'end_lon': elon,
                'issue_remarks': l['issue_detail'],
                'resolution_remarks': l['resolution_detail'],
                'evidence': l['evidence'],
                'coordinate_evidence': coord_ev,
            })

    flagged_out.sort(key=lambda x: (
        status_order.get(x['status_nov13'], 9),
        {'coordinate_province_mismatch': 0, 'reassigned_to_different_province': 0,
         'coordinate_region_mismatch': 1, 'location_conflict': 2, 'region_misfiling': 3,
         'repeated_title': 4, 'wrong_region': 5, 'missing_justification': 6,
         'justification_quality': 7, 'no_coordinates_place_named': 8,
         'no_coordinates_system_station_only': 9, 'no_submission_title': 10,
         'workbook_defect_ref_errors': 11}.get(x['flag_category'], 99),
        -float(x['nep_amount_php'] or 0)))

    with (DATA / 'nia_nep_annex_flagged_nov13.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(flagged_out[0].keys()))
        w.writeheader()
        w.writerows(flagged_out)

    from collections import Counter
    print(f"full annex: {len(full_out)} rows")
    print(f"flagged annex: {len(flagged_out)} rows")
    print(f"  by disposition: {dict(Counter(r['disposition'] for r in flagged_out))}")
    n_coord = sum(1 for r in full_out if r['start_lat'])
    n_rev = sum(1 for r in full_out if r['title_revised'] == 'yes')
    print(f"full annex: {n_coord} rows with coordinates, {n_rev} titles revised Oct10->Nov13")


if __name__ == '__main__':
    main()
