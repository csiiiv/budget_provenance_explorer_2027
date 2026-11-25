#!/usr/bin/env python3
"""NIA submission-title coordinate verification against PSGC boundaries.

Independent adjudication layer for the NIA Senate workbook (Nov 13 revision):
parses coordinates embedded in the FOR SUBMISSION TO SENATE titles, then
tests each point against the 2023 PSA/NAMRIA-derived PSGC province and
region polygons retained in dpwh_coor2psgc_geomapping.

Evidence philosophy (workbook-only): every input here comes from NIA's own
submission column; boundary polygons are official geography, not third-party
assessments. Verdicts are review pointers, never certified errors.

Outputs (analysis-nia/data/):
  nia_coord_verification_nov13.csv   per-row verdicts
  nia_coord_verification_summary.json
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import geopandas as gpd
import openpyxl
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
WB = ROOT / 'NIA_DATA' / 'NIA_NEP_2026-11-13.xlsx'
SHP_BASE = ROOT / 'dpwh_coor2psgc_geomapping' / 'philippines-psgc-shapefiles' / 'data' / '2023'
OUT_DIR = ROOT / 'analysis-nia' / 'data'

COORD = re.compile(
    r'(\d{1,2})[°˚]\s?(\d{1,2})[′\']\s?([\d.]+)[″"]*\s?([NS])[,\s]+'
    r'(\d{1,3})[°˚]\s?(\d{1,2})[′\']\s?([\d.]+)[″"]*\s?([EW])')

# workbook region label -> adm1_psgc prefix
REGION_MAP = {
    'Region 1': '100000000', 'Region 2': '200000000', 'Region 3': '300000000',
    'Region 4A': '400000000', 'Region 4B': '170000000', 'Region 5': '500000000',
    'Region 6': '600000000', 'Region 7': '700000000', 'Region 8': '800000000',
    'Region 9': '900000000', 'Region 10': '1000000000', 'Region 11': '1100000000',
    'Region 12': '1200000000', 'Region 13': '1600000000',
    'Cordillera Administrative Region': '150000000',
}
REGION_MAP_NUM = {
    'Region 1': '1', 'Region 2': '2', 'Region 3': '3', 'Region 4A': '4',
    'Region 4B': '17', 'Region 5': '5', 'Region 6': '6', 'Region 7': '7',
    'Region 8': '8', 'Region 9': '9', 'Region 10': '10', 'Region 11': '11',
    'Region 12': '12', 'Region 13': '16', 'Cordillera Administrative Region': '14',
    # NIA integrated units: assessed via host region (province match is the
    # primary check for these rows)
    'MARIIS': '2', 'UPRIIS': '3',
}


def dms(m):
    lat = int(m.group(1)) + int(m.group(2)) / 60 + float(m.group(3)) / 3600
    lon = int(m.group(5)) + int(m.group(6)) / 60 + float(m.group(7)) / 3600
    if m.group(4) == 'S':
        lat = -lat
    if m.group(8) == 'W':
        lon = -lon
    return lat, lon


def load_workbook_rows():
    wb = openpyxl.load_workbook(WB, data_only=True)
    ws = wb['DETAILS 2027']
    ctx = {'region': '', 'province': ''}
    out = []
    for i, row in enumerate(ws.iter_rows(min_row=9, max_col=25, values_only=True), start=9):
        for f, ci in (('region', 4), ('province', 5)):
            v = row[ci]
            if isinstance(v, str) and v.strip():
                ctx[f] = v.strip()
        label = row[6]
        if isinstance(label, str) and label.strip():
            out.append({
                'r': i, 'region': ctx['region'], 'province': ctx['province'],
                'label': re.sub(r'\s+', ' ', label.strip()),
                'nep': row[7] or 0, 'hgab': row[8] or 0,
                'submit': str(row[21] or ''),
            })
    return out


def main():
    rows = load_workbook_rows()

    provs = gpd.read_file(SHP_BASE / 'Provdists' / 'PH_Adm2_ProvDists.shp.shp').to_crs('EPSG:4326')
    regions = gpd.read_file(SHP_BASE / 'Regions' / 'PH_Adm1_Regions.shp.shp').to_crs('EPSG:4326')
    prov_sindex = provs.sindex
    reg_sindex = regions.sindex

    def match_poly(point, gdf, sidx, name_col, psgc_col, prefix):
        cand = list(sidx.query(point, predicate='within'))
        if not cand:
            cand = list(sidx.query(point.buffer(0.005), predicate='intersects'))
        best = None
        for i in cand:
            row = gdf.iloc[i]
            if prefix and not str(row[psgc_col]).startswith(prefix):
                continue
            if row.geometry.contains(point) or row.geometry.buffer(0).intersects(point.buffer(0.001)):
                best = row[name_col]
                break
        return best

    out = []
    stats = Counter()
    for r in rows:
        m = COORD.search(r['submit'])
        if not m:
            continue
        lat, lon = dms(m)
        pt = Point(lon, lat)
        reg_num = REGION_MAP_NUM.get(r['region'], '')
        reg_prefix = reg_num[0] if reg_num else ''
        hit_prov = None
        for i in prov_sindex.query(pt, predicate='within'):
            hit_prov = provs.iloc[i]['adm2_en']
            break
        if hit_prov is None:
            for i in prov_sindex.query(pt.buffer(0.01), predicate='intersects'):
                if provs.iloc[i].geometry.buffer(0.002).contains(pt):
                    hit_prov = provs.iloc[i]['adm2_en']
                    break
        hit_reg = None
        hit_reg_psgc = ''
        for i in reg_sindex.query(pt, predicate='within'):
            hit_reg = regions.iloc[i]['adm1_en']
            hit_reg_psgc = str(regions.iloc[i]['adm1_psgc'])
            break
        wb_reg_num = REGION_MAP_NUM.get(r['region'], '')
        try:
            hit_reg_num = str(int(hit_reg_psgc) // 100000000) if hit_reg_psgc else ''
        except ValueError:
            hit_reg_num = ''
        reg_ok = bool(hit_reg_num) and bool(wb_reg_num) and hit_reg_num == wb_reg_num

        wb_prov = (r['province'] or '').strip()
        prov_ok = bool(hit_prov) and (
            hit_prov.lower().replace('-', ' ') == wb_prov.lower().replace('-', ' ')
            or wb_prov.lower() in hit_prov.lower() or hit_prov.lower() in wb_prov.lower())

        if prov_ok and reg_ok:
            v = 'ok'
        elif prov_ok and not reg_ok:
            v = 'province_ok_region_mismatch'
        elif hit_prov is None:
            v = 'outside_ph_boundaries'
        else:
            v = 'province_mismatch'
        stats[v] += 1
        out.append({
            'nov13_row': r['r'], 'region': r['region'], 'province': wb_prov,
            'title': r['label'], 'nep_amount_php': r['nep'], 'hgab_amount_php': r['hgab'],
            'lat': f'{lat:.6f}', 'lon': f'{lon:.6f}',
            'boundary_province': hit_prov or '', 'boundary_region': hit_reg or '',
            'verdict': v,
        })

    out.sort(key=lambda x: (x['verdict'] != 'ok', -float(x['nep_amount_php'] or 0)))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / 'nia_coord_verification_nov13.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    summary = {
        'method': 'submission_title_coords_vs_psqc_polygons_v1',
        'workbook': str(WB.name),
        'rows_with_coords': len(out),
        'verdicts': dict(stats),
        'note': 'Points parsed from FOR SUBMISSION TO SENATE titles; polygons are '
                '2023 PSA/NAMRIA-derived PSGC shapes. Mismatch verdicts are review '
                'pointers, not certified errors.',
    }
    with open(OUT_DIR / 'nia_coord_verification_summary.json', 'w') as f:
        json.dump(summary, f, indent=1)

    print(f'rows with coords: {len(out)}')
    for k, v in stats.most_common():
        print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
