"""Attach NIA coordinate workbook evidence to October hearing workbook IDs."""

from collections import Counter, defaultdict
from hashlib import sha256
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
import re
import unicodedata

import openpyxl

from extract_nia_senate_workbook import clean, number
from scan_gps_inventory import analyze_text

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    'NIA_DATA/WITH%20COORDINATES%20-%20NIA%20FY%202027%20NEP%20-%20'
    'PROJECT%20DESCRIPTION%20IMPROVEMENT.xlsx'
)
SHEET = 'DETAILS 2027'
MAP_POINT_TOLERANCE_M = 100

# Title normalization used for revised-title matching. Mirrors the
# typography-insensitive comparison in export_nia_web (title_typography_key)
# so NFC/typography variants of the same submission title still join.
TITLE_TYPOGRAPHY = str.maketrans({
    '′': "'", '’': "'", '″': '"', '“': '"', '”': '"',
    '–': '-', '—': '-', '−': '-',
})


def revised_title_key(title):
    """Casefold + typography-tolerant key for revised-title comparisons."""
    text = unicodedata.normalize('NFC', title or '').casefold().translate(TITLE_TYPOGRAPHY)
    return re.sub(r"""\s*([+.,:;()°'"-])\s*""", r'\1', ' '.join(text.split())) or None


def parse_coordinate_column(raw):
    parsed = analyze_text(raw, dedicated_field=True, include_pair_text=True)
    if parsed is None:
        return None
    for point in parsed['points']:
        lat, lon = point['latitude'], point['longitude']
        if lat is not None and lon is not None and not (4 <= lat <= 22 and 116 <= lon <= 127):
            point['issues'].append('outside_philippines_screening_bounds')
            parsed['status'] = 'parsed_with_issues'
    return parsed


def usable_points(parsed):
    return [
        (point['latitude'], point['longitude'])
        for point in (parsed or {}).get('points', [])
        if point['latitude'] is not None and point['longitude'] is not None
        and 'outside_philippines_screening_bounds' not in point['issues']
    ]


def point_distance_m(first, second):
    lat1, lon1 = map(radians, first)
    lat2, lon2 = map(radians, second)
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 12_742_000 * asin(sqrt(min(1, a)))


def compare_map_points(coordinates, map_coordinates):
    # Map links can represent a subset, so compare each map point to its nearest supplied point.
    supplied = usable_points(coordinates)
    mapped = usable_points(map_coordinates)
    if not supplied or not mapped:
        return None
    return sum(all(point_distance_m(point, target) > MAP_POINT_TOLERANCE_M
                   for target in supplied) for point in mapped)


def project_key(title, nep, house):
    return clean(title), nep, house


def read_source():
    workbook = openpyxl.load_workbook(SOURCE, data_only=True)
    try:
        sheet = workbook[SHEET]
        headers = tuple(clean(sheet[cell].value) for cell in ('X7', 'Y7', 'Z7', 'AA7'))
        if headers != ('JUSTIFICATION', 'Geographical Coordinates', 'CORPLAN CHECKING',
                       'GOOGLE MAP LINK (CLICK-ABLE)'):
            raise ValueError(f'Unexpected NIA coordinate workbook headers: {headers}')

        projects, evidence = defaultdict(list), {}
        region = province = None
        for cells in sheet.iter_rows(min_row=9, max_col=27):
            row = cells[6].row
            if any(clean(cell.value) for cell in cells[1:4]):
                region = province = None
            elif region_label := clean(cells[4].value):
                region, province = region_label, None
            elif province_label := clean(cells[5].value):
                province = province_label

            title = clean(cells[6].value)
            revised_title = cells[21].value
            if title:
                key = project_key(title, number(cells[7].value), number(cells[8].value))
                projects[key].append((row, clean(revised_title)))

            raw, checking, map_text = (cell.value for cell in cells[24:27])
            hyperlink = cells[26].hyperlink
            map_url = hyperlink.target if hyperlink else None
            if not any(clean(value) for value in (raw, checking, map_text, map_url)):
                continue
            coordinates = parse_coordinate_column(raw)
            map_coordinates = parse_coordinate_column(map_text)
            evidence[row] = {
                'row': row,
                'printed_title': cells[6].value,
                'revised_title': revised_title,
                'revised_amount': number(cells[22].value),
                'justification': cells[23].value,
                'region': region,
                'province': province,
                'coordinate_text': raw,
                'coordinates': coordinates,
                'corplan_checking': checking,
                'map_link_text': map_text,
                'map_link_coordinates': map_coordinates,
                'map_points_over_100m_from_supplied': compare_map_points(coordinates, map_coordinates),
                'map_url': map_url,
            }
        return projects, evidence
    finally:
        workbook.close()


def build_coordinate_evidence(october_projects):
    """Return project evidence and the source audit, including held rows."""
    october = defaultdict(list)
    for project in october_projects:
        key = project_key(project['label'], project['nep_amount'], project['hgab_amount'])
        october[key].append(project)

    source, evidence = read_source()
    if Counter({k: len(v) for k, v in source.items()}) != Counter(
        {k: len(v) for k, v in october.items()}
    ):
        raise ValueError('NIA coordinate workbook differs from October in project titles or amounts')

    attached, review = {}, []
    # Index October rows by typography-tolerant submission label + submission
    # amount. Held rows whose printed title is empty (inserted rows carrying
    # only a revised title) resolve through this index.
    by_submission = defaultdict(list)
    for project in october_projects:
        if project.get('submission_label') and project.get('submission_amount') is not None:
            key = (revised_title_key(project['submission_label']), project['submission_amount'])
            if key[0]:
                by_submission[key].append(project)

    for key, source_rows in source.items():
        targets = october[key]
        titles = Counter(title for _, title in source_rows)
        for row, revised_title in source_rows:
            if row not in evidence:
                continue
            entry = evidence.pop(row)
            candidates = targets
            method = 'printed_title_and_amounts'
            if len(targets) > 1:
                method = 'printed_title_amounts_and_revised_title'
                candidates = [
                    project for project in targets
                    if revised_title and titles[revised_title] == 1
                    and clean(project['submission_label']) == revised_title
                ]
            if len(candidates) != 1:
                review.append({**entry, 'reason': 'repeated_project_key',
                               'candidate_october_ids': [project['id'] for project in targets]})
                continue

            project = candidates[0]
            if any(clean(entry[field]) != clean(project[field]) for field in ('region', 'province')):
                review.append({**entry, 'reason': 'geography_differs',
                               'candidate_october_ids': [project['id']],
                               'october_region': project['region'],
                               'october_province': project['province']})
                continue
            if project['id'] in attached:
                raise ValueError(f"Multiple coordinate workbook rows matched {project['id']}")
            attached[project['id']] = {**entry, 'match_method': method}

    # Held rows with an empty printed title never enter `source`. Their
    # revised title + submission amount must resolve uniquely against October
    # submission labels; geography must agree. Documented reassignments
    # (workbook printed geography vs. revised submission geography) keep the
    # evidence with a note rather than dropping it.
    no_printed_title = list(evidence.values())
    evidence.clear()
    for entry in no_printed_title:
        key = (revised_title_key(entry.get('revised_title')), entry.get('revised_amount'))
        candidates = by_submission.get(key, []) if key[0] else []
        project = candidates[0] if len(candidates) == 1 and candidates[0]['id'] not in attached else None
        if project is None:
            review.append({**entry, 'reason': 'no_printed_project_title'})
            continue
        geography_note = {}
        if any(clean(entry[field]) != clean(project[field]) for field in ('region', 'province')):
            geography_note = {
                'geography_review': {
                    'october_region': clean(project['region']),
                    'october_province': clean(project['province']),
                    'coordinate_row_region': clean(entry['region']),
                    'coordinate_row_province': clean(entry['province']),
                    'note': 'Workbook printed title is booked in {oct_region} / {oct_province}; '
                            'the revised submission row carrying the coordinates is booked in '
                            '{row_region} / {row_province}.'.format(
                                oct_region=clean(project['region']),
                                oct_province=clean(project['province']),
                                row_region=clean(entry['region']),
                                row_province=clean(entry['province'])),
                }
            }
        attached[project['id']] = {
            **entry, 'match_method': 'revised_title_and_submission_amount',
            **geography_note,
        }
    review.sort(key=lambda entry: entry['row'])
    metadata = {
        'source_xlsx': str(SOURCE.relative_to(ROOT)),
        'source_sha256': sha256(SOURCE.read_bytes()).hexdigest(),
        'sheet': SHEET,
        'columns': {'printed_title': 'G', 'revised_title': 'V', 'justification': 'X',
                    'coordinate_text': 'Y', 'corplan_checking': 'Z', 'map_link': 'AA'},
        'map_point_tolerance_m': MAP_POINT_TOLERANCE_M,
        'matched_rows': len(attached),
        'review_rows': review,
    }
    return attached, metadata


def attach_submission_only_evidence(metadata, submission_only):
    """Join held coordinate rows to NIA submission-only workbook entries.

    A submission-only row (an inserted revised title with an amount but no
    printed NEP/House budget, e.g. a reallocation recipient) never became an
    October project, so its coordinate row stays in review. Join a vintage's
    submission entry to a held row only when the Excel row number, revised
    title, amount, region, and province all agree. Joined rows leave the
    review list; unmatched rows stay held.

    Returns {(vintage, excel_row): evidence} with match_method
    'submission_only_row_title_amount_and_geography'.
    """
    held = {entry['row']: entry for entry in metadata['review_rows']
            if entry['reason'] == 'no_printed_project_title'}
    joined = {}
    for vintage, entries in (submission_only or {}).items():
        for entry in entries:
            title = revised_title_key(entry.get('submission_title'))
            candidates = [
                held_row for row, held_row in held.items()
                if row == entry.get('row')
                and revised_title_key(held_row.get('revised_title')) == title
                and held_row.get('revised_amount') == entry.get('submission_amount_php')
                and clean(held_row.get('region')) == clean(entry.get('region'))
                and clean(held_row.get('province')) == clean(entry.get('province'))
            ]
            if len(candidates) == 1:
                evidence = {k: v for k, v in candidates[0].items() if k != 'reason'}
                evidence['match_method'] = 'submission_only_row_title_amount_and_geography'
                joined[(vintage, entry['row'])] = evidence
    if joined:
        joined_rows = {evidence['row'] for evidence in joined.values()}
        metadata['review_rows'] = [
            entry for entry in metadata['review_rows'] if entry['row'] not in joined_rows
        ]
        metadata['submission_only_matched_rows'] = len(joined_rows)
    return joined
