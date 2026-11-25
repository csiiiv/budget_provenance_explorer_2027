#!/usr/bin/env python3
"""Build the FMR red-flags annex: senate-workbook flags vs DA corrective action.

Inputs (read directly; no workbench dependency):
  * external_work/senate_data/FMR_2027_NEP_vs_GAB_PY LandMask.xlsx
      sheets 'NEP extracted' / 'GAB extracted' — per-row coordinate-validity
      and PSGC location-check statuses produced for the Senate statement.
  * other-analysis/data/da_fmr_draft.json           (Nov 5 vintage)
  * other-analysis/data/da_fmr_draft_nov12.json     (Nov 12 vintage, default)

Every flagged printed row is joined one-to-one to a DA working-draft FROM
original inside the same region: (canonical title, amount), then canonical
title, then best difflib similarity within the (region, amount) bucket with a
uniqueness margin. DA action is then classified from disposition + FROM→TO
diffs + remarks; dropped originals inherit the corrective action of the
nearby NEW/L replacement row that supersedes them (same rule as the workbench
linker: next 3 rows, same region, unused, positive proposed amount).

Output: data/fmr_flags_annex_<vintage>.csv / .xlsx — one row per flagged
printed observation with a short `status` and a `remarks` column, mirroring
the NIA flags ledger format.
"""
from __future__ import annotations

import argparse
import collections
import csv
import difflib
import json
import re
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
SENATE = ROOT / 'external_work/senate_data/FMR_2027_NEP_vs_GAB_PY LandMask.xlsx'
DATA = Path(__file__).resolve().parent / 'data'
ENDPOINT_REVIEW = ROOT / 'DA_FMR_DATA' / (
    'bad_endpoints_with_boundary_dist - bad_endpoints_with_boundary_dist latest_2026-11-14.csv')

DA_VINTAGES = {
    'nov5': DATA / 'da_fmr_draft.json',
    'nov12': DATA / 'da_fmr_draft_nov12.json',
}
DEFAULT_VINTAGE = 'nov12'
SIMILARITY_FLOOR = 0.75       # below this, no match at all
SIMILARITY_MARGIN = 0.05      # best must beat runner-up by this to be unique

COORD_STATUS_LABEL = {
    'Invalid': 'Invalid coordinates (impossible span / at sea / missing endpoint)',
    'Check': 'Coordinate check (reversed or over 15 km span)',
    'Valid (lat/long reversed)': 'Printed lat/long reversed',
    'Valid (typo corrected)': 'Printed coordinate typo corrected in reading',
}
LOC_STATUS_LABEL = {
    'Check': 'PSGC location check (verify manually)',
    'Mismatch': 'PSGC location mismatch (barangay/town/province/region)',
    'Not found': 'Locality not found in PSGC list',
}


def clean_title(text) -> str:
    """Strip embedded coordinate blocks from a printed project cell."""
    value = re.sub(r'\s+', ' ', str(text or '')).strip()
    value = re.split(r'\s*START\b', value, flags=re.I)[0].strip(' ,')
    # Numbered-list coordinate blocks, e.g. 'START: (1) 16.75, 121.85, (2) …'
    value = re.split(r'\s*\(\s*\d+\s*\)\s*[-\d.]', value)[0].strip(' ,')
    return value


def canonical_title(text) -> str:
    lowered = clean_title(text).lower().replace('brgy', 'barangay')
    return ' '.join(re.findall(r'[a-z0-9]+', lowered))


def ocr_key(text) -> str:
    """OCR-confusion-normalized key: i/l/1 collapse (e.g. 'Iiocos' ≡ 'Ilocos')."""
    return canonical_title(text).translate(str.maketrans('i1', 'll'))


def senate_region_key(label) -> str | None:
    upper = str(label or '').upper()
    if 'CORDILLERA' in upper:
        return 'CAR'
    if 'NEGROS ISLAND' in upper:
        return 'NIR'
    match = re.match(r'REGION\s+([IVX]+[AB]?)\b', upper)
    return match.group(1) if match else None


def load_senate_flags():
    """Flagged rows from the two extracted sheets of the Senate workbook."""
    wb = openpyxl.load_workbook(SENATE, read_only=True, data_only=True)
    try:
        flags = []
        for sheet, doc in (('NEP extracted', '2027 NEP'), ('GAB extracted', '2027 GAB')):
            for row in wb[sheet].iter_rows(values_only=True):
                seq = row[0]
                if seq is None or str(row[1] or '').startswith('Region') and not str(row[1] or '').strip():
                    continue
                if not isinstance(seq, (int, float)) or str(row[0]).strip().lower() == 'seq':
                    continue
                (valid, coord_note, loc, loc_note) = row[9], row[10], row[11], row[12]
                coord_flag = valid if valid and valid != 'Valid' else None
                loc_flag = loc if loc and loc != 'Verified' else None
                if not coord_flag and not loc_flag:
                    continue
                flags.append({
                    'doc': doc,
                    'seq': int(seq),
                    'region_label': str(row[1] or '').strip(),
                    'region_key': senate_region_key(row[1]),
                    'title': clean_title(row[3]),
                    'amount_php': int(row[6]) if row[6] is not None else None,
                    'pdf_page': int(row[7]) if row[7] is not None else None,
                    'length_km': row[8],
                    'coord_flag': coord_flag,
                    'coord_note': str(coord_note).strip() if coord_note else '',
                    'loc_flag': loc_flag,
                    'loc_note': str(loc_note).strip() if loc_note else '',
                })
    finally:
        wb.close()
    return flags


def load_endpoint_review():
    """Nov 14 PSGC boundary-distance review of DA-retained endpoints.

    Groups the per-endpoint CSV by DA control: each entry carries the endpoint
    findings (verdict, where it actually falls, metres outside the title
    municipality), the GAB title when it names the cross-LGU barangay, and any
    manual verification note. Returns {} when the review file is absent.
    """
    if not ENDPOINT_REVIEW.is_file():
        return {}
    raw = list(csv.reader(ENDPOINT_REVIEW.open(encoding='utf-8')))
    # Column layout (0-based): 0 amount, 1 source, 2 ctrl, 3 nep_id, 4 role,
    # 5 point_id, 6 lon, 7 lat, 8 verdict, 9 psgc_where, 10 bad_reason,
    # 11 title_locality, 12 nep_title, 13 nov12_submitted_title, 14 gab_title
    # (unnamed), 15 manual note (unnamed), 16 nov12_to_cell, 17 nov12_from_cell,
    # 18+ boundary-distance evidence columns.
    review = collections.defaultdict(lambda: {
        'amount': None, 'nep_title': '', 'gab_title': '', 'note': '',
        'endpoints': [], 'source': ''})
    for cells in raw[1:]:
        cells += [''] * (18 - len(cells))
        ctrl = cells[2]
        if not ctrl:
            continue
        entry = review[ctrl]
        entry['amount'] = int(cells[0]) if cells[0] else None
        entry['source'] = cells[1] or entry['source']
        entry['nep_title'] = cells[12] or entry['nep_title']
        if cells[14].strip():
            entry['gab_title'] = cells[14]
        if cells[15].strip():
            entry['note'] = cells[15].strip()
        entry['endpoints'].append({
            'role': cells[4],
            'verdict': cells[8],
            'where': cells[9],
            'reason': cells[10],
            'outside_m': cells[22] or cells[21],
        })
    return dict(review)


def load_da(vintage: str):
    path = DA_VINTAGES[vintage]
    if not path.is_file():
        raise SystemExit(f'Missing {path}; run extract_da_fmr.py --vintage {vintage} first')
    da = json.loads(path.read_text())
    # L-rows parsed with a literal 'None' FROM title when the cell is empty.
    for project in da['projects']:
        if project.get('from_title') in (None, 'None', ''):
            project['from_title'] = None
    return da


def link_replacements(da_projects):
    """Pair dropped ORIGINAL rows with the nearby NEW/L row that replaces them.

    Two passes: first require canonical-title agreement between the dropped
    FROM title and the candidate TO title (catches retitled corrections like
    Bauco→Bauko); then a fallback for dropped rows with no usable FROM title.
    """
    replacements, used = {}, set()

    def candidates_after(index, region):
        for nxt in da_projects[index + 1:index + 4]:
            if nxt['region_key'] != region:
                break
            if nxt['id'] in used:
                continue
            if nxt['kind'] in ('new', 'list_revision') and (nxt.get('effective_amount_php') or 0) > 0:
                yield nxt

    for require_title in (True, False):
        for index, project in enumerate(da_projects):
            if project['disposition'] != 'dropped' or project['id'] in replacements:
                continue
            from_key = canonical_title(project.get('from_title') or '')
            if require_title and not from_key:
                continue
            for nxt in candidates_after(index, project['region_key']):
                if require_title:
                    ratio = difflib.SequenceMatcher(
                        None, from_key, canonical_title(nxt.get('to_title') or '')).ratio()
                    if ratio < 0.6:
                        continue
                replacements[project['id']] = nxt
                used.add(nxt['id'])
                break
    return replacements


def match_flag_to_da(flag, originals):
    """Return (da_row, method) for one flagged printed row, or (None, reason)."""
    key_title = canonical_title(flag['title'])
    if not key_title or flag['region_key'] is None:
        return None, 'unparseable'
    bucket = [p for p in originals
              if p['region_key'] == flag['region_key'] and p.get('from_title')]

    # Pass 1 — canonical title + amount.
    if flag['amount_php'] is not None:
        hits = [p for p in bucket
                if canonical_title(p['from_title']) == key_title
                and p.get('from_amount_php') == flag['amount_php']]
        if len(hits) == 1:
            return hits[0], 'title_and_amount'
        if len(hits) > 1:
            return None, 'ambiguous'

    # Pass 2 — canonical title alone.
    hits = [p for p in bucket if canonical_title(p['from_title']) == key_title]
    if len(hits) == 1:
        return hits[0], 'title'
    if len(hits) > 1:
        return None, 'ambiguous'

    # Pass 2b — OCR-confusion-normalized title (i/l/1 collapse) + amount.
    if flag['amount_php'] is not None:
        ocr_hits = [p for p in bucket
                    if ocr_key(p['from_title']) == ocr_key(flag['title'])
                    and p.get('from_amount_php') == flag['amount_php']]
        if len(ocr_hits) == 1:
            return ocr_hits[0], 'title_ocr_normalized'
        if len(ocr_hits) > 1:
            return None, 'ambiguous'

    # Pass 3 — best similarity inside the (region, amount) bucket, unique margin.
    if flag['amount_php'] is None:
        return None, 'no_match'
    scored = sorted(
        ((difflib.SequenceMatcher(
            None, key_title, canonical_title(p['from_title'])).ratio(), p)
         for p in bucket if p.get('from_amount_php') == flag['amount_php']),
        key=lambda pair: -pair[0])
    if not scored:
        return None, 'no_match'
    best_ratio, best = scored[0]
    runner = scored[1][0] if len(scored) > 1 else 0.0
    if best_ratio < SIMILARITY_FLOOR:
        return None, 'no_match'
    if best_ratio - runner < SIMILARITY_MARGIN:
        return None, 'ambiguous'
    return best, f'similarity:{best_ratio:.2f}'


def raw_coord_signature(raw) -> list | None:
    """Ordered numeric signature of a raw START/END block, hemisphere-suffix agnostic.

    Detects value changes AND axis-order fixes: 'START: 120.58, 18.17' vs
    'START: 18.17, 120.58' produce different signatures, while hemisphere
    suffixes ('18.17N, 120.58E') are ignored.
    """
    if not raw:
        return None
    numbers = []
    for token in re.findall(r'[-\d.]+', str(raw)):
        try:
            numbers.append(round(float(token), 6))
        except ValueError:
            return None
    return numbers or None


def coordinates_differ(a, b) -> bool:
    """True when the raw START/END blocks differ beyond hemisphere suffixes.

    Catches both value changes and axis-order corrections (e.g. the NEP's
    'START: 120.58, 18.17' re-issued by DA as 'START: 18.17, 120.58')."""
    sig_a, sig_b = raw_coord_signature(a), raw_coord_signature(b)
    if sig_a is None or sig_b is None:
        return (a or []) != (b or [])
    return sig_a != sig_b


def classify(flag, da_row, method, replacement, da_meta, proposed_index=None, similarity_pool=None):
    """Short status + remarks + correction detail for one flagged row."""
    issue_bits = []
    if flag['coord_flag']:
        issue_bits.append(COORD_STATUS_LABEL.get(flag['coord_flag'], flag['coord_flag']))
    if flag['loc_flag']:
        issue_bits.append(LOC_STATUS_LABEL.get(flag['loc_flag'], flag['loc_flag']))
    issue = '; '.join(issue_bits)
    details = [b for b in (flag['coord_note'], flag['loc_note']) if b]
    evidence = []

    if da_row is None:
        if method in ('ambiguous', 'unparseable'):
            status = 'REVIEW — AMBIGUOUS DA MATCH' if method == 'ambiguous' else 'NO DA LINK FOUND'
        else:
            # No FROM original: for GAB rows this means a House-only insertion
            # that the DA draft (built from the NEP list) never carried.
            status = 'NOT CARRIED IN DA DRAFT (House insertion; not adopted)'
        if flag['doc'] == '2027 GAB':
            # House-only insertion: check whether DA adopted it as a proposed row.
            adopted = None
            if proposed_index is not None:
                key = (canonical_title(flag['title']), flag['amount_php'])
                candidates = [p for p in proposed_index.get(key, [])
                              if p['kind'] in ('new', 'list_revision')]
                if len(candidates) == 1:
                    adopted = candidates[0]
                elif candidates:
                    return ('REVIEW — AMBIGUOUS DA ADOPTION',
                            'Multiple DA proposed rows match this House insertion exactly; needs manual disambiguation.',
                            issue, {'flag_types': issue_bits, 'detail': ' | '.join(details), 'da': None,
                                    'evidence': 'Senate workbook sheet, seq ' + str(flag['seq'])})
                elif similarity_pool is not None:
                    # High-confidence adoption: same region + amount, corrected
                    # title ≥ 0.93 similar, and a DA correction remark present.
                    sim_candidates = [
                        p for p in similarity_pool
                        if p['kind'] in ('new', 'list_revision')
                        and p.get('effective_amount_php') == flag['amount_php']
                        and p['region_key'] == flag['region_key']
                        and 'Correction' in (p.get('remarks') or '')
                        and difflib.SequenceMatcher(
                            None, canonical_title(flag['title']),
                            canonical_title(p.get('effective_title') or '')).ratio() >= 0.93]
                    if len(sim_candidates) == 1:
                        adopted = sim_candidates[0]
            if adopted is not None:
                status = 'FIXED — ADOPTED BY DA WITH CORRECTIONS'
                adopted_bits = []
                if adopted.get('to_coordinates_raw'):
                    adopted_bits.append('with GPS-surveyed coordinates')
                remarks_bits = [
                    f"House insertion adopted into the DA revised list as {adopted['control_no']} "
                    f"(workbook row {adopted['excel_row']})."]
                remark_text = (adopted.get('remarks') or '').strip()
                if remark_text:
                    remarks_bits.append(f'DA remark: {remark_text}')
                evidence.append(f"DA control {adopted['control_no']} (workbook row {adopted['excel_row']})")
                return status, ' '.join(remarks_bits), issue, \
                    {'flag_types': issue_bits, 'detail': ' | '.join(details),
                     'da': {'control_no': adopted['control_no'], 'excel_row': adopted['excel_row'],
                            'disposition': adopted['disposition'],
                            'replacement': None},
                     'evidence': '; '.join(evidence)}
            status = 'NOT CARRIED IN DA DRAFT (House insertion; not adopted)'
            note = ('Flagged House insertion with no NEP counterpart and no DA FROM row. '
                    'DA did not adopt this entry in the revised list.')
        else:
            note = 'No corresponding FROM row in the DA working draft.'
        return status, note, issue, \
            {'flag_types': issue_bits, 'detail': ' | '.join(details), 'da': None,
             'evidence': 'Senate workbook sheet, seq ' + str(flag['seq'])}

    source = f"DA control {da_row['control_no']} (workbook row {da_row['excel_row']})"
    remarks_bits = []
    effective = da_row
    if da_row['disposition'] == 'dropped':
        if replacement is not None:
            effective = replacement
            fixed_bits = []
            if replacement.get('to_coordinates_raw') and da_row.get('from_coordinates_raw') is None:
                fixed_bits.append('coordinates')
            elif coordinates_differ(da_row.get('from_coordinates_raw'),
                                    replacement.get('to_coordinates_raw')):
                fixed_bits.append('coordinates')
            if canonical_title(replacement.get('to_title') or '') != canonical_title(da_row.get('from_title') or ''):
                fixed_bits.append('title')
            corrected = ' + '.join(fixed_bits) if fixed_bits else 'entry'
            status = f'FIXED — REPLACED BY CORRECTED ENTRY ({corrected.upper()})'
            remarks_bits.append(
                f"Dropped FROM row replaced by {replacement['control_no']} "
                f"(workbook row {replacement['excel_row']}).")
            evidence.append(source + f" → {replacement['control_no']} (row {replacement['excel_row']})")
        else:
            status = 'RESOLVED — DROPPED FROM DA LIST'
            remarks_bits.append('Project removed from the DA proposed list; no replacement row.')
            evidence.append(source)
    else:
        from_title = da_row.get('from_title') or ''
        to_title = da_row.get('to_title')
        if da_row.get('is_retain'):
            # RETAIN rows keep the FROM entry verbatim; the TO cells are empty.
            title_fixed = False
            coord_fixed = False
        else:
            title_fixed = canonical_title(to_title or '') != canonical_title(from_title)
            coord_fixed = (to_title is not None
                           and coordinates_differ(da_row.get('from_coordinates_raw'),
                                                  da_row.get('to_coordinates_raw')))
        if coord_fixed and title_fixed:
            status = 'FIXED — TITLE + COORDINATES CORRECTED BY DA'
        elif coord_fixed:
            status = 'FIXED — COORDINATES CORRECTED BY DA'
        elif title_fixed:
            status = 'FIXED — TITLE CORRECTED BY DA'
        else:
            status = 'PENDING — RETAINED WITHOUT CHANGE'
        evidence.append(source)

    remark_text = (effective.get('remarks') or '').strip()
    if remark_text and remark_text != 'REMARKS':
        remarks_bits.append(f'DA remark: {remark_text}')
    if effective['id'] != da_row['id']:
        if effective.get('to_coordinates') and not da_row.get('from_coordinates'):
            remarks_bits.append('Replacement row carries GPS-surveyed coordinates.')
        if canonical_title(effective.get('to_title') or '') != canonical_title(da_row.get('from_title') or ''):
            remarks_bits.append(f"Corrected title: {clean_title(effective.get('to_title'))}")
    elif da_row['disposition'] != 'dropped' and da_row.get('to_title') and canonical_title(da_row['to_title']) != canonical_title(da_row.get('from_title') or ''):
        remarks_bits.append(f"Corrected title: {clean_title(da_row['to_title'])}")

    return status, ' '.join(remarks_bits) or 'No DA remark recorded.', issue, \
        {'flag_types': issue_bits, 'detail': ' | '.join(details),
         'da': {'control_no': da_row['control_no'], 'excel_row': da_row['excel_row'],
                'disposition': da_row['disposition'],
                'replacement': replacement['control_no'] if replacement else None},
         'evidence': '; '.join(evidence)}


def build(vintage: str):
    flags = load_senate_flags()
    da = load_da(vintage)
    endpoint_review = load_endpoint_review()
    originals = [p for p in da['projects'] if p['kind'] != 'new' and p.get('from_title')]
    replacements = link_replacements(da['projects'])
    proposed_index = collections.defaultdict(list)
    for p in da['projects']:
        et, ea = p.get('effective_title'), p.get('effective_amount_php')
        if et and (ea or 0) > 0:
            proposed_index[(canonical_title(et), ea)].append(p)

    # Cross-document twin detection (same canonical title+amount flagged twice).
    by_key = collections.defaultdict(list)
    for flag in flags:
        by_key[(flag['doc'], canonical_title(flag['title']), flag['amount_php'])].append(flag)
    twin_of = {}
    for (doc, title, amount), group in by_key.items():
        other = '2027 GAB' if doc == '2027 NEP' else '2027 NEP'
        twins = by_key.get((other, title, amount), [])
        if twins:
            twin_of[(doc, title, amount)] = f"Also flagged in {other} (seq {twins[0]['seq']})"

    rows = []
    used_da = collections.defaultdict(list)
    for flag in flags:
        da_row, method = match_flag_to_da(flag, originals)
        replacement = replacements.get(da_row['id']) if da_row else None
        status, remarks, issue, extra = classify(flag, da_row, method, replacement, da['metadata'],
                                                 proposed_index=proposed_index,
                                                 similarity_pool=da['projects'])
        if da_row:
            used_da[da_row['id']].append(flag['doc'] + '#' + str(flag['seq']))
        row = {
            'flag_id': len(rows) + 1,
            'document': flag['doc'],
            'seq': flag['seq'],
            'region': flag['region_label'],
            'title': flag['title'],
            'amount_php': flag['amount_php'],
            'pdf_page': flag['pdf_page'],
            'flag_types': '; '.join(extra['flag_types']),
            'issue_detail': extra['detail'],
            'status': status,
            'remarks': remarks,
            'counterpart': twin_of.get((flag['doc'], canonical_title(flag['title']), flag['amount_php']), ''),
            'da_control_no': extra['da']['control_no'] if extra['da'] else '',
            'da_excel_row': extra['da']['excel_row'] if extra['da'] else '',
            'da_disposition': extra['da']['disposition'] if extra['da'] else '',
            'da_replacement_control_no': extra['da']['replacement'] if extra['da'] else '',
            'match_method': method if da_row else method,
            'evidence': extra['evidence'],
            'endpoint_review': '',
        }
        # Enrich with the Nov 14 endpoint review when this DA control appears there.
        ev = endpoint_review.get(da_row['control_no']) if da_row else None
        if ev:
            bits = [f"{(e['role'] or '').upper()} falls in {e['where']}"
                    + (f" ({e['outside_m']} m outside the title municipality)" if e['outside_m'] else '')
                    for e in ev['endpoints']]
            row['endpoint_review'] = ' | '.join(bits)
            if ev.get('note') and ev['note'].lower() != 'none':
                row['endpoint_review'] += f" — note: {ev['note']}"
            row['evidence'] += '; Nov 14 endpoint boundary review'
        rows.append(row)

    # Endpoint-review controls never flagged in the Senate statement: new rows.
    flagged_controls = {r['da_control_no'] for r in rows if r['da_control_no']}
    for ctrl in sorted(set(endpoint_review) - flagged_controls):
        ev = endpoint_review[ctrl]
        da_row = next((p for p in da['projects'] if p['control_no'] == ctrl), None)
        if da_row is None:
            continue
        bits = [f"{(e['role'] or '').upper()} falls in {e['where']}"
                + (f" ({e['outside_m']} m outside the title municipality)" if e['outside_m'] else '')
                for e in ev['endpoints']]
        note = f" — note: {ev['note']}" if ev.get('note') and ev['note'].lower() != 'none' else ''
        gab_names_brgy = ev.get('gab_title') and canonical_title(ev['gab_title']) != canonical_title(ev.get('nep_title') or '')
        rows.append({
            'flag_id': len(rows) + 1,
            'document': '2027 NEP' if ev['source'] in ('nep', 'both') else '2027 GAB',
            'seq': '',
            'region': da_row.get('region') or '',
            'title': clean_title(ev.get('nep_title') or da_row.get('from_title')),
            'amount_php': ev.get('amount'),
            'pdf_page': '',
            'flag_types': 'Endpoint outside title locality (Nov 14 boundary review)',
            'issue_detail': ' | '.join(f"{e['reason']}" for e in ev['endpoints']),
            'status': 'PENDING — RETAINED WITHOUT CHANGE',
            'remarks': (
                'Not part of the original statement flags; surfaced by the Nov 14 endpoint '
                'boundary review. DA retained the entry and its coordinates unchanged in the '
                'revised list.'
                + (' The House GAB title names the second barangay: '
                   f'"{clean_title(ev.get("gab_title"))}".' if gab_names_brgy else '')),
            'counterpart': '',
            'da_control_no': ctrl,
            'da_excel_row': da_row['excel_row'],
            'da_disposition': da_row['disposition'],
            'da_replacement_control_no': '',
            'match_method': 'endpoint_review',
            'evidence': 'Nov 14 endpoint boundary review; DA control ' + ctrl,
            'endpoint_review': ' | '.join(bits) + note,
        })

    summary = {
        'flag_rows': len(rows),
        'by_doc': dict(collections.Counter(r['document'] for r in rows)),
        'by_status': dict(collections.Counter(r['status'] for r in rows)),
        'by_flag_type': dict(collections.Counter(
            t.strip() for r in rows for t in r['flag_types'].split(';') if t.strip())),
        'da_rows_linked': len(used_da),
        'da_rows_linked_twice': sum(1 for v in used_da.values() if len(v) > 1),
        'senate_workbook': str(SENATE.relative_to(ROOT)),
        'da_draft': str(DA_VINTAGES[vintage].relative_to(ROOT)),
        'da_label': da['label'],
        'endpoint_review_rows': sum(1 for r in rows if r['match_method'] == 'endpoint_review'),
        'endpoint_review_enriched': sum(
            1 for r in rows if r['endpoint_review'] and r['match_method'] != 'endpoint_review'),
    }
    return rows, summary


COLUMNS = ['flag_id', 'document', 'seq', 'region', 'title', 'amount_php', 'pdf_page',
           'flag_types', 'issue_detail', 'status', 'remarks', 'counterpart',
           'da_control_no', 'da_excel_row', 'da_disposition', 'da_replacement_control_no',
           'match_method', 'evidence', 'endpoint_review']


def write_csv(rows, path: Path):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def write_xlsx(rows, path: Path, summary):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'FMR red flags annex'
    ws.append(COLUMNS)
    for row in rows:
        ws.append([row[c] for c in COLUMNS])
    widths = {'A': 7, 'B': 10, 'C': 6, 'D': 28, 'E': 60, 'F': 14, 'G': 9, 'H': 34,
              'I': 60, 'J': 38, 'K': 70, 'L': 26, 'M': 12, 'N': 10, 'O': 12, 'P': 14,
              'Q': 16, 'R': 44, 'S': 60}
    for column, width in widths.items():
        ws.column_dimensions[column].width = width
    from openpyxl.styles import Font, PatternFill, Alignment
    header_fill = PatternFill('solid', fgColor='1F4E79')
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = header_fill
    status_fills = {
        'FIXED': PatternFill('solid', fgColor='C6EFCE'),
        'RESOLVED': PatternFill('solid', fgColor='DDEBF7'),
        'PENDING': PatternFill('solid', fgColor='FFEB9C'),
        'NO DA LINK': PatternFill('solid', fgColor='FCE4D6'),
        'REVIEW': PatternFill('solid', fgColor='FCE4D6'),
    }
    for row_index in range(2, ws.max_row + 1):
        status = str(ws.cell(row_index, COLUMNS.index('status') + 1).value or '')
        for prefix, fill in status_fills.items():
            if status.startswith(prefix):
                ws.cell(row_index, COLUMNS.index('status') + 1).fill = fill
                break
        ws.cell(row_index, COLUMNS.index('title') + 1).alignment = Alignment(wrap_text=True, vertical='top')
        ws.cell(row_index, COLUMNS.index('issue_detail') + 1).alignment = Alignment(wrap_text=True, vertical='top')
        ws.cell(row_index, COLUMNS.index('remarks') + 1).alignment = Alignment(wrap_text=True, vertical='top')
        ws.cell(row_index, COLUMNS.index('endpoint_review') + 1).alignment = Alignment(wrap_text=True, vertical='top')
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions

    info = wb.create_sheet('Summary')
    info.append(['FMR red-flags annex — Senate statement flags vs DA corrective action'])
    info.append(['Generated from', summary['senate_workbook']])
    info.append(['DA draft', summary['da_label'] + ' — ' + summary['da_draft']])
    info.append([])
    info.append(['Flag rows', summary['flag_rows']])
    info.append(['By document', json.dumps(summary['by_doc'])])
    info.append([])
    info.append(['Status', 'Count'])
    for status, count in sorted(summary['by_status'].items(), key=lambda kv: -kv[1]):
        info.append([status, count])
    info.append([])
    info.append(['Flag type', 'Count'])
    for flag_type, count in sorted(summary['by_flag_type'].items(), key=lambda kv: -kv[1]):
        info.append([flag_type, count])
    info.append([])
    info.append(['DA FROM rows linked', summary['da_rows_linked']])
    info.append(['DA FROM rows linked from both documents', summary['da_rows_linked_twice']])
    info.append([])
    info.append(['Endpoint review (Nov 14 boundary file)', ''])
    info.append(['New rows added (not in statement flags)', summary['endpoint_review_rows']])
    info.append(['Existing rows enriched with boundary evidence', summary['endpoint_review_enriched']])
    info.column_dimensions['A'].width = 72
    info.column_dimensions['B'].width = 60
    wb.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vintage', choices=sorted(DA_VINTAGES), default=DEFAULT_VINTAGE)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()

    rows, summary = build(args.vintage)
    csv_path = DATA / f'fmr_flags_annex_{args.vintage}.csv'
    xlsx_path = DATA / f'fmr_flags_annex_{args.vintage}.xlsx'

    if args.check:
        import io
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        if not csv_path.exists() or csv_path.read_text() != buffer.getvalue():
            raise SystemExit(f'{csv_path} missing or stale; rerun build_fmr_flags_annex.py')
        print(f'FMR flags annex verified: {csv_path}')
        return

    write_csv(rows, csv_path)
    write_xlsx(rows, xlsx_path, summary)
    print(f'FMR flags annex ({args.vintage}): {csv_path.name} + {xlsx_path.name}')
    print(f"  flag rows: {summary['flag_rows']} ({summary['by_doc']})")
    for status, count in sorted(summary['by_status'].items(), key=lambda kv: -kv[1]):
        print(f'  {status}: {count}')


if __name__ == '__main__':
    main()
