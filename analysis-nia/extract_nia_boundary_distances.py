#!/usr/bin/env python3
"""Coordinate-to-PSGC adjudication for NIA NEP 2027 (Nov 13 workbook).

Follows the FMR bad_endpoints pattern (one row per point, flat evidence
columns), reusing the repo's existing machinery:

  coords -> PSGC   : dpwh_coor2psgc_geomapping/geomap_r_tree CoordToPSGCMapper
                     (bulk R-tree point-in-polygon, 2023 barangay layer)
  booked unit      : the workbook's region/province booking
  boundary distance: UTM (EPSG:326xx) metres to the booked province polygon,
                     computed only for points whose PSGC province differs

Everything derives from NIA's own submission titles + official 2023
PSA/NAMRIA-derived PSGC shapefiles. No external datasets.
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
SHP = ROOT / 'dpwh_coor2psgc_geomapping' / 'philippines-psgc-shapefiles' / 'data' / '2023'
GEOMAP = ROOT / 'dpwh_coor2psgc_geomapping'
OUT = ROOT / 'analysis-nia' / 'data'

sys.path.insert(0, str(GEOMAP / 'geomap_r_tree'))
from coord_to_psgc_rtree import CoordToPSGCMapper  # noqa: E402
sys.path.insert(0, str(ROOT / 'master_list' / 'scripts'))
import build_coordinate_psgc as bcp  # noqa: E402

COORD = re.compile(
    r"(\d{1,2})[°˚]\s?(\d{1,2})[′']\s?([\d.]+)[″\"]*\s?([NS])[,\s]+"
    r"(\d{1,3})[°˚]\s?(\d{1,2})[′']\s?([\d.]+)[″\"]*\s?([EW])")
START = re.compile(r"Start\s*[-–:]?\s*" + COORD.pattern, re.I)
END = re.compile(r"End\s*[-–:]?\s*" + COORD.pattern, re.I)

REGION_MAP_NUM = {
    'Region 1': '1', 'Region 2': '2', 'Region 3': '3', 'Region 4A': '4',
    'Region 4B': '17', 'Region 5': '5', 'Region 6': '6', 'Region 7': '7',
    'Region 8': '8', 'Region 9': '9', 'Region 10': '10', 'Region 11': '11',
    'Region 12': '12', 'Region 13': '16',
    'Cordillera Administrative Region': '14',
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


def utm_epsg(lon):
    return 32600 + int((lon + 180) // 6) + 1


def load_points():
    """One record per project; points list holds start (always) + end (if any)."""
    wb = openpyxl.load_workbook(ROOT / 'NIA_DATA' / 'NIA_NEP_2026-11-13.xlsx', data_only=True)
    ws = wb['DETAILS 2027']
    ctx = {'region': '', 'province': ''}
    out = []
    for i, row in enumerate(ws.iter_rows(min_row=9, max_col=25, values_only=True), start=9):
        for f, ci in (('region', 4), ('province', 5)):
            v = row[ci]
            if isinstance(v, str) and v.strip():
                ctx[f] = v.strip()
        label, sub = row[6], row[21] if len(row) > 21 else None
        if not (isinstance(label, str) and label.strip() and isinstance(sub, str)):
            continue
        m = COORD.search(sub)
        if not m:
            continue
        points = [('start',) + dms(m)]
        ms, me = START.search(sub), END.search(sub)
        if ms and me:
            points.append(('end',) + dms(me))
        out.append({
            'row': i, 'region': ctx['region'], 'province': (ctx['province'] or '').strip(),
            'title': re.sub(r'\s+', ' ', label.strip()),
            'nep': row[7] or 0, 'points': points,
        })
    return out


def main():
    mapper = CoordToPSGCMapper(shapefile_dir=str(GEOMAP / 'philippines-psgc-shapefiles'),
                               simplify_tolerance=0)
    catalog = bcp.load_catalog()
    provs = gpd.read_file(SHP / 'Provdists' / 'PH_Adm2_ProvDists.shp.shp')
    munis = gpd.read_file(SHP / 'Municities' / 'PH_Adm3_MuniCities.shp.shp')
    prov_by_name = {str(n).lower(): n for n in provs['adm2_en'] if n}
    dc = munis[munis['adm3_en'] == 'City of Davao']  # HUC booked by city name

    projects = load_points()
    flat = []
    for p in projects:
        for role, lat, lon in p['points']:
            flat.append({**p, 'role': role, 'lat': lat, 'lon': lon})

    # ---- bulk coords -> PSGC via existing mapper ----
    import pandas as pd
    df = mapper.map_dataframe(
        pd.DataFrame({'lat': [f['lat'] for f in flat], 'lon': [f['lon'] for f in flat]}),
        lat_col='lat', lon_col='lon', how='left')
    df = df[~df.index.duplicated(keep='first')]

    def chain_of(rr):
        if not rr.get('matched'):
            return {}
        hit = {'matched': True, 'barangay': rr.get('barangay'),
               'barangay_psgc': rr.get('barangay_psgc'),
               'municipality_psgc': rr.get('municipality_psgc'),
               'province_psgc': rr.get('province_psgc'),
               'region_psgc': rr.get('region_psgc')}
        chain = bcp.chain_for(catalog, hit) or {}
        return {lvl: chain[lvl].get('name') or '' for lvl in chain}

    out, stats = [], Counter()
    for i, f in enumerate(flat):
        rr = df.iloc[i]
        ch = chain_of(rr)
        psgc_where = ' / '.join(v for v in (ch.get('barangay'), ch.get('municipality'),
                                            ch.get('province'), ch.get('region')) if v)
        wb_prov = f['province']
        wb_reg_num = REGION_MAP_NUM.get(f['region'], '')
        hit_reg_num = ''
        if rr.get('matched') and rr.get('region_psgc') is not None:
            try:
                hit_reg_num = str(int(rr['region_psgc']) // 100000000)
            except (TypeError, ValueError):
                pass

        # ---- inside-booked test + boundary distance (only when outside) ----
        def booked_polygon(name):
            booked = prov_by_name.get(name.lower())
            if booked:
                return provs[provs['adm2_en'] == booked], 'province'
            if name.lower() == 'davao city':
                return dc, 'huc_city'
            if 'cabanatuan' in name.lower():
                return provs[provs['adm2_en'] == 'Nueva Ecija'], 'alias'
            return None, 'none'

        epsg = utm_epsg(f['lon'])
        pt = gpd.GeoSeries([Point(f['lon'], f['lat'])], crs='EPSG:4326').to_crs(epsg).iloc[0]
        inside = dist = containing = reason = ''
        if not rr.get('matched'):
            dd = provs.to_crs(epsg).geometry.distance(pt)
            nearest = provs.iloc[dd.idxmin()]
            verdict = 'unmatched_point'
            containing, reason = nearest['adm2_en'], f"no PSGC polygon contains point; {dd.min():,.0f} m from {nearest['adm2_en']}"
        else:
            poly, layer = booked_polygon(wb_prov)
            g = poly.to_crs(epsg).geometry.iloc[0] if poly is not None else None
            inside_bool = bool(g is not None and g.contains(pt))
            prov_name_match = bool(ch.get('province')) and (
                ch['province'].lower().replace('-', ' ') == wb_prov.lower().replace('-', ' ')
                or wb_prov.lower() in ch['province'].lower()
                or ch['province'].lower() in wb_prov.lower())
            muni_is_booked = bool(ch.get('municipality')) and (
                wb_prov.lower() in ch['municipality'].lower().replace('city of', ''))
            inside = 'yes' if (inside_bool or prov_name_match or muni_is_booked) else 'no'
            if inside == 'yes':
                verdict = 'ok'
            else:
                d = g.distance(pt) if g is not None else None
                dist = f'{d:.0f}' if d is not None else ''
                containing = ch.get('province', '')
                if d is None:
                    verdict, reason = 'no_booked_polygon', f"booked '{wb_prov}' has no polygon"
                elif d <= 2000:
                    verdict = 'near_boundary'
                    reason = f"{d:,.0f} m outside booked {wb_prov}; point is in {ch.get('municipality', '?')}, {containing}"
                else:
                    verdict = 'outside_booked'
                    reason = f"{d:,.0f} m outside booked {wb_prov}; point is in {ch.get('municipality', '?')}, {containing}"
            # region check rides along (CAR cluster case: province ok, region off)
            reg_ok = bool(hit_reg_num) and bool(wb_reg_num) and hit_reg_num == wb_reg_num
            if verdict == 'ok' and not reg_ok:
                verdict = 'region_mismatch'
                reason = f"province ok but PSGC region {ch.get('region', '?')} != booked {f['region']}"
        stats[verdict] += 1
        out.append({
            'nov13_row': f['row'], 'role': f['role'],
            'region': f['region'], 'province': wb_prov,
            'title': f['title'], 'nep_amount_php': f['nep'],
            'lat': f"{f['lat']:.6f}", 'lon': f"{f['lon']:.6f}",
            'psgc_where': psgc_where,
            'inside_booked': inside,
            'dist_to_booked_boundary_m': dist,
            'containing_province': containing,
            'verdict': verdict, 'bad_reason': reason,
        })

    with open(OUT / 'nia_coord_boundary_dist_nov13.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    summ = {'method': 'fmr_bad_endpoints_pattern_mapper_v5', 'points': len(out),
            'verdicts': dict(stats)}
    json.dump(summ, open(OUT / 'nia_coord_boundary_dist_summary.json', 'w'), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    main()
