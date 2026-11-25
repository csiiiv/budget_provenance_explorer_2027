"""Build the NIA provenance explorer from existing extracts and ledger links."""

from collections import Counter, defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gps-analysis'))
sys.path.insert(0, str(ROOT / 'analysis-nia'))
from nia_coordinate_workbook import SOURCE as COORDINATE_WORKBOOK, build_coordinate_evidence
from scan_gps_inventory import analyze_text

DATA = ROOT / 'analysis-nia/data'
RECONCILIATION = DATA / 'nia_chain_reconciliation.json'
SENATE_REVERSE_REVIEW = DATA / 'nia_senate_reverse_review.json'
SUBMISSION_ONLY = DATA / 'nia_submission_only.json'
POW_REVIEW = DATA / 'program_of_works' / 'pow_review_availability.json'
NEP_PDF = ROOT / 'dbm-other-nep-line-data/NIA.pdf'
from stage_changes import summarize_budget_changes

OUT = ROOT / 'web/public/data/nia.json'
ANNEX = ROOT / 'Senate_report_data/data/derived/senate_annex_a3_nia_mapped.json'
ANNEX_RAW = ROOT / 'Senate_report_data/data/derived/senate_annex_a3_nia.json'
LEDGER = ROOT / 'data_formalization/data/ledger/nia.jsonl'

# The annex prints REGION IV-A/IV-B on some pages and REGION 4A/4B on others;
# normalize to the House/NEP spelling (Region 4A) so grouping doesn't fragment.
ROMAN = {'IV-A': '4A', 'IV-B': '4B', 'IV': '4'}


def region_key_of(name):
    if not name:
        return ''
    key = re.sub(r'\s+', ' ', name).strip().upper()
    key = re.sub(r'^REGION\s+(IV-A|IV-B|IV)\b', lambda m: 'REGION ' + ROMAN[m.group(1)], key)
    return key


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def senate_rollups():
    """Printed region/province subtotal rows from the raw A-3 snapshot.

    Headings are keyed by row_index and assigned to the leaves that follow
    them in document order: the annex can print the same province lineage
    twice under one region (e.g. TARLAC in Region 3 Restoration appears as
    two separate headings with different subtotals), so a pure path lookup
    would attach the wrong subtotal to one of the groups.
    """
    raw = read(ANNEX_RAW)['rows']
    headings = {}    # row_index -> heading row
    leaf_head = {}   # leaf row_index -> (region heading idx, province heading idx)
    cur4 = cur5 = None
    for row in raw:
        if row['kind'] == 'heading':
            level = row.get('level')
            headings[row['row_index']] = row
            if level == 4:
                cur4, cur5 = row['row_index'], None
            elif level == 5:
                cur5 = row['row_index']
            else:
                cur4 = cur5 = None
        else:
            leaf_head[row['row_index']] = (cur4, cur5)
    return headings, leaf_head


def attach_rollups(senate, headings, leaf_head):
    """Give each mapped project its printed province and region subtotals."""
    for row in senate:
        reg_idx, prov_idx = leaf_head.get(row['row_index'], (None, None))
        province = region = None
        if prov_idx is not None:
            h = headings[prov_idx]
            province = {'name': (h['hb_title'] or h['senate_title']).strip(),
                        'gab_php': h['gab'], 'sv_php': h['sv'], 'pdf_page': h['pdf_page']}
        if reg_idx is not None:
            h = headings[reg_idx]
            region = {'name': (h['hb_title'] or h['senate_title']).strip(),
                      'gab_php': h['gab'], 'sv_php': h['sv'], 'pdf_page': h['pdf_page']}
        row['province_subtotal'] = province
        row['region_subtotal'] = region
        row['region_key'] = region_key_of(row.get('region'))


def agency_link(leaf, neps, leaf_count, projects):
    if not neps:
        return None, 'No NEP ledger link'
    if len(neps) != 1 or leaf_count != 1:
        return None, 'Ambiguous title key'
    nep = neps[0]
    if leaf['nep_amount_php'] is None or leaf['nep_amount_php'] != projects[nep]['amount_php']:
        return None, 'NEP amount unverified'
    return nep, 'Ledger title key and NEP amount agree'


def csv_rows(name):
    with (DATA / name).open(encoding='utf-8-sig', newline='') as source:
        return list(csv.DictReader(source))


def workbook_crosswalk():
    forward = defaultdict(set)
    reverse = defaultdict(set)
    for row in csv_rows('nia_submitted_list_status_nov13.csv'):
        oct10, nov13 = row['oct10_row'], row['nov13_row']
        if oct10.isdigit() and nov13.isdigit():
            forward[oct10].add(nov13)
            reverse[nov13].add(oct10)
    return {oct10: nov13 for oct10, targets in forward.items() if len(targets) == 1
            for nov13 in targets if reverse[nov13] == {oct10}}


def attach_workbook_evidence(chains, crosswalk):
    workbook = read(DATA / 'senate_nia_dataset.json')['projects']
    by_pdf = defaultdict(list)
    for row in workbook:
        for side in ('nep', 'house'):
            if join := row.get(f'{side}_join'):
                by_pdf[join['id']].append(row)

    annex = {row['nov13_row']: row for row in csv_rows('nia_nep_annex_full_nov13.csv')}
    findings = defaultdict(dict)
    for row in csv_rows('nia_flags_ledger_nov13.csv'):
        for vintage in ('oct10', 'nov13'):
            if locator := row[f'workbook_row_{vintage}']:
                findings[vintage, locator][row['flag_id']] = row

    for chain in chains:
        observations = {}
        for side in ('nep', 'house'):
            if source := chain.get(side):
                for row in by_pdf[source['id']]:
                    if row['nep_amount' if side == 'nep' else 'hgab_amount'] == source['amount_php']:
                        observations[row['id']] = row
        if not observations:
            continue
        chain['workbook'] = list(observations.values())
        november = {}
        flags = {}
        for row in observations.values():
            oct10 = str(row['row'])
            flags.update(findings['oct10', oct10])
            if nov13 := crosswalk.get(oct10):
                if nov13 in annex:
                    november[nov13] = annex[nov13]
                flags.update(findings['nov13', nov13])
        chain['november_review'] = list(november.values())
        chain['findings'] = list(flags.values())


def budget_heading_key(title, region, province, amount):
    heading = re.split(r'[:;]', title or '', maxsplit=1)[0]
    return text_key(heading), region_key_of(region), text_key(province), amount


def merge_workbook_pairs(chains):
    """Join workbook-backed spelling variants and reviewed PDF continuations."""
    reviewed = {row['workbook_row']: row for row in read(RECONCILIATION)}
    observations = defaultdict(list)
    for chain in chains:
        for row in chain.get('workbook', []):
            observations[row['id']].append(chain)

    by_heading = {stage: Counter() for stage in ('nep', 'house', 'senate')}
    for chain in chains:
        for stage, index in by_heading.items():
            if not (record := chain.get(stage)):
                continue
            if stage == 'senate':
                key = budget_heading_key(record['senate_title'], record['region_key'],
                                         record['path'][-1], record['sv_php'])
            else:
                key = budget_heading_key(record['title'], record['region'], record['province'], record['amount_php'])
            index[key] += 1

    merged_nep_ids = set()
    reviewed_rows = set()
    for candidates in observations.values():
        if len(candidates) != 2:
            continue
        nep_chain, house_chain = sorted(candidates, key=lambda chain: bool(chain.get('house')))
        nep, house = nep_chain.get('nep'), house_chain.get('house')
        if not nep or not house or nep_chain.get('house') or house_chain.get('nep'):
            continue
        if len(nep_chain['workbook']) != 1 or len(house_chain['workbook']) != 1:
            continue
        workbook_row = nep_chain['workbook'][0]['row']
        evidence = reviewed.get(workbook_row)
        if evidence:
            if (nep['id'], house['id'], nep['source']['pdf_page']) != (
                evidence['nep_id'], evidence['house_id'], evidence['pdf_page'],
            ):
                raise ValueError(f'Workbook row {workbook_row} no longer matches reconciliation evidence')
            reviewed_rows.add(workbook_row)
            nep_chain['reconciliation'] = house_chain['reconciliation'] = evidence
            basis = evidence.get('basis')
            if evidence['decision'] == 'review':
                if basis != 'workbook_pair_senate_attribution_review':
                    continue
                october = house_chain['workbook'][0]
                november, = house_chain['november_review']
                if not (
                    (october['nep_join'] or {}).get('id') == nep['id']
                    and (october['house_join'] or {}).get('id') == house['id']
                    and october['nep_amount'] == nep['amount_php'] == int(november['nep_amount_php'])
                    and october['hgab_amount'] == house['amount_php'] == int(november['hgab_amount_php'])
                    and (house_chain.get('senate') or {}).get('house_id') == house['id']
                ):
                    raise ValueError(f'Workbook pair evidence no longer agrees at row {workbook_row}')
                method = 'workbook_pair_senate_attribution_review'
            elif evidence['decision'] != 'join' or (basis != 'funding_restoration' and nep['amount_php'] != house['amount_php']):
                raise ValueError(f'Invalid reviewed match for workbook row {workbook_row}')
            elif basis == 'funding_restoration':
                senate = house_chain.get('senate') or {}
                october = house_chain['workbook'][0]
                november, = house_chain['november_review']
                full_title = title_typography_key(evidence['full_house_title'])
                if not (
                    full_title == title_typography_key(nep['title'])
                    and full_title.startswith(title_typography_key(house['title']))
                    and title_typography_key(november['submission_title']) == title_typography_key(senate.get('senate_title'))
                    and nep['amount_php'] == october['submission_amount'] == senate.get('sv_php')
                    and house['amount_php'] == senate.get('gab_php') < nep['amount_php']
                ):
                    raise ValueError(f'Funding restoration evidence no longer agrees at workbook row {workbook_row}')
                method = 'reviewed_workbook_funding_restoration'
            elif basis in ('workbook_original_title_variant', 'workbook_distinct_coordinates'):
                october = house_chain['workbook'][0]
                november, = house_chain['november_review']
                senate = house_chain.get('senate') or {}
                if not (
                    region_key_of(nep['region']) == region_key_of(house['region']) == region_key_of(october['region_canonical'])
                    and text_key(nep['province']) == text_key(house['province']) == text_key(october['province'])
                    and (october['nep_join'] or {}).get('id') == nep['id']
                    and (october['house_join'] or {}).get('id') == house['id']
                    and str(nep['amount_php']) == november['nep_amount_php']
                    and str(house['amount_php']) == november['hgab_amount_php']
                    and senate.get('house_id') == house['id']
                    and senate.get('gab_php') == house['amount_php'] == senate.get('sv_php')
                ):
                    raise ValueError(f'Workbook anchor no longer agrees at row {workbook_row}')
                if basis == 'workbook_distinct_coordinates':
                    nia_gps = (october['title_parse'].get('coordinates') or {}).get('points', [])
                    senate_gps = (senate.get('senate_gps') or {}).get('points', [])
                    if not (len(nia_gps) == len(senate_gps) == 1
                            and all(round(nia_gps[0][k], 6) == round(senate_gps[0][k], 6)
                                    for k in ('latitude', 'longitude'))
                            and round(nia_gps[0]['latitude'], 6) == float(november['start_lat'])
                            and round(nia_gps[0]['longitude'], 6) == float(november['start_lon'])):
                        raise ValueError(f'Workbook site no longer agrees at row {workbook_row}')
                method = f'reviewed_{basis}'
            elif basis == 'unique_workbook_base_title_and_amount':
                october = house_chain['workbook'][0]
                november, = house_chain['november_review']
                senate = house_chain.get('senate') or {}
                key = budget_heading_key(nep['title'], nep['region'], nep['province'], nep['amount_php'])
                if not (
                    all(key)
                    and key == budget_heading_key(house['title'], house['region'], house['province'], house['amount_php'])
                    and all(index[key] == 1 for index in by_heading.values())
                    and senate.get('house_id') == house['id']
                    and senate['gab_php'] == senate['sv_php'] == house['amount_php']
                    and key == budget_heading_key(senate['senate_title'], senate['region_key'],
                                                 senate['path'][-1], senate['sv_php'])
                    and key == budget_heading_key(october['label'], october['region_canonical'],
                                                 october['province'], october['submission_amount'])
                    and key == budget_heading_key(november['submission_title'], november['region'],
                                                 november['province'], int(november['hgab_amount_php']))
                    and november['nep_amount_php'] == str(nep['amount_php'])
                ):
                    raise ValueError(f'Base title and amounts no longer identify workbook row {workbook_row} uniquely')
                method = 'reviewed_unique_workbook_base_title_and_amount'
            elif basis == 'documented_replacement':
                october = house_chain['workbook'][0]
                november, = house_chain['november_review']
                senate = house_chain.get('senate') or {}
                if not (
                    evidence.get('full_nep_title') and october['justification']
                    and title_typography_key(november['submission_title']) == title_typography_key(senate.get('senate_title'))
                    and october['submission_amount'] == nep['amount_php'] == senate.get('sv_php')
                ):
                    raise ValueError(f'Replacement evidence no longer agrees at workbook row {workbook_row}')
                method = 'reviewed_workbook_project_replacement'
            elif basis == 'title_abbreviation':
                expanded = re.sub(r'\brehab\b', 'rehabilitation', title_typography_key(nep['title']))
                if expanded != title_typography_key(house['title']):
                    raise ValueError(f'Abbreviation no longer explains workbook row {workbook_row}')
                method = 'reviewed_workbook_title_abbreviation'
            elif evidence.get('basis') == 'house_location_added':
                house_title = title_typography_key(house['title'])
                base_title = re.sub(r' in brgy\.[a-z]+(?:[ -]+[a-z]+)*$', '', house_title)
                nep_title = re.sub(r'\bal monitoring\b', 'ai monitoring', title_typography_key(nep['title']))
                if not (
                    base_title != house_title and base_title == nep_title
                    and region_key_of(nep['region']) == region_key_of(house['region'])
                    and text_key(nep['province']) == text_key(house['province'])
                    and len(house_chain.get('november_review', [])) == 1
                    and (house_chain.get('senate') or {}).get('house_id') == house['id']
                ):
                    raise ValueError(f'House location evidence no longer supports workbook row {workbook_row}')
                method = 'reviewed_workbook_house_location_added'
            elif evidence.get('full_nep_title'):
                method = 'reviewed_nep_pdf_continuation'
            else:
                raise ValueError(f'Missing source title evidence for workbook row {workbook_row}')
        else:
            nep_mark = nep_chain['comparison']['variant_mark'] or {}
            house_mark = house_chain['comparison']['variant_mark'] or {}
            if (nep_mark.get('mark'), house_mark.get('mark')) != ('spelling_variant', 'spelling_variant'):
                continue
            if nep_mark['counterpart_ids'] != [house['id']] or house_mark['counterpart_ids'] != [nep['id']]:
                continue
            method = 'workbook_corroborated_spelling_variant'
        house_chain.update(
            nep=nep,
            review=nep_chain['review'],
            comparison={
                'status': 'paired',
                'strict_status': 'split_pair',
                'method': method,
                'variant_mark': None,
                'ambiguous_title': bool(evidence and evidence['decision'] == 'review'),
            },
        )
        merged_nep_ids.add(nep_chain['id'])
    if missing := reviewed.keys() - reviewed_rows:
        raise ValueError(f'Reviewed workbook rows missing from comparison: {sorted(missing)}')
    return [chain for chain in chains if chain['id'] not in merged_nep_ids]


TITLE_TYPOGRAPHY = str.maketrans({
    '′': "'", '’': "'", '″': '"', '“': '"', '”': '"',
    '–': '-', '—': '-', '−': '-', '@': ' at ',
})


def text_key(value):
    return ' '.join(unicodedata.normalize('NFKC', value or '').casefold().split())


def title_typography_key(title):
    title = unicodedata.normalize('NFC', title or '').casefold().translate(TITLE_TYPOGRAPHY)
    return re.sub(r"""\s*([+.,:;()°'"-])\s*""", r'\1', ' '.join(title.split()))


def attach_senate_revision_comparisons(chains):
    """Compare the Senate title to each available NIA submission on its chain."""
    for chain in chains:
        raw_senate_title = (chain.get('senate') or {}).get('senate_title')
        senate_title = title_typography_key(raw_senate_title)
        if not senate_title:
            continue
        comparison = {}
        for stage, collection, locator, field in (
            ('oct10', 'workbook', 'row', 'submission_label'),
            ('nov13', 'november_review', 'nov13_row', 'submission_title'),
        ):
            rows = chain.get(collection, [])
            if len(rows) != 1:
                continue
            row = rows[0]
            title = title_typography_key(row[field])
            if title:
                comparison[stage] = {
                    'row': int(row[locator]),
                    'matches': title == senate_title or text_key(row[field]) == text_key(raw_senate_title),
                }
        for stage, row in chain.get('nia_submission_only', {}).items():
            comparison[stage] = {
                'row': row['row'],
                'matches': title_typography_key(row['submission_title']).rstrip('.') == senate_title.rstrip('.'),
            }
        if comparison:
            chain['senate_revision_comparison'] = comparison


# Limit this comparison to a barangay label immediately before a terminal DMS
# coordinate pair. A number or punctuation in the label stays significant.
BARANGAY_BEFORE_GPS = re.compile(
    r"""\b(?:barangay|brgy\.)\s+[a-z]+(?:[ -]+(?!(?:and|or|barangay)\b)[a-z]+)*\s+"""
    r"""(?=\d{1,2}\s*°\s*\d{1,2}\s*['′]\s*\d{1,2}(?:\.\d+)?\s*["″]\s*[ns]"""
    r"""\s*,?\s*\d{1,3}\s*°\s*\d{1,2}\s*['′]\s*\d{1,2}(?:\.\d+)?\s*["″]\s*[ew]\s*$)""",
    re.IGNORECASE,
)


def link_senate_restorations(chains, *, normalize_typography=False, compare_without_barangay=False):
    """Use NIA submission titles to link Senate insertions to NEP-only lines."""
    def match_key(title, region, province, amount):
        if compare_without_barangay:
            title, substitutions = BARANGAY_BEFORE_GPS.subn('Barangay [name] ', title or '')
            if substitutions != 1:
                title = ''
        title = title_typography_key(title) if normalize_typography else text_key(title)
        return title, region_key_of(region), text_key(province), amount

    submissions = {'oct10': defaultdict(list), 'nov13': defaultdict(list)}
    insertions = defaultdict(list)
    for chain in chains:
        if chain.get('senate_reverse_review'):
            continue
        nep, house, senate = (chain.get(stage) for stage in ('nep', 'house', 'senate'))
        if senate and not (nep or house) and not senate['house_id'] and senate['gab_php'] == 0 and senate['sv_php'] > 0:
            key = match_key(senate['senate_title'], senate['region_key'], senate['path'][-1], senate['sv_php'])
            insertions[key].append(chain)
        if not nep or house or senate:
            continue

        october = chain.get('workbook', [])
        november = chain.get('november_review', [])
        if len(october) != 1 or len(november) != 1:
            continue
        oct10, nov13 = october[0], november[0]
        amount = nep['amount_php']
        if not (oct10['nep_join']['id'] == nep['id'] and not oct10['house_join']
                and amount == oct10['nep_amount'] == oct10['submission_amount']
                and str(amount) == nov13['nep_amount_php']
                and oct10['hgab_amount'] == 0 and nov13['hgab_amount_php'] == '0'):
            continue
        if not (region_key_of(nep['region']) == region_key_of(oct10['region_canonical']) == region_key_of(nov13['region'])
                and text_key(nep['province']) == text_key(oct10['province']) == text_key(nov13['province'])):
            continue
        for vintage, title in (('oct10', oct10['submission_label']), ('nov13', nov13['submission_title'])):
            key = match_key(title, nep['region'], nep['province'], amount)
            submissions[vintage][key].append(chain)

    linked_insertions = set()
    for key, candidates in insertions.items():
        oct10 = submissions['oct10'].get(key, [])
        nov13 = submissions['nov13'].get(key, [])
        if not all(key[:3]) or len(candidates) != 1 or len(oct10) != 1 or len(nov13) != 1 or oct10[0] is not nov13[0]:
            continue
        chain, insertion = oct10[0], candidates[0]
        chain['senate'] = insertion['senate']
        chain['senate_restoration'] = {
            'method': 'unique_nia_submission_title_region_province_and_amount',
            'normalized_typography': normalize_typography,
            **({'barangay_wording_differs': True} if compare_without_barangay else {}),
            'oct10_row': chain['workbook'][0]['row'],
            'nov13_row': int(chain['november_review'][0]['nov13_row']),
        }
        linked_insertions.add(insertion['id'])
    return [chain for chain in chains if chain['id'] not in linked_insertions]


def attach_reviewed_reallocation(chains_by_senate, insertion, evidence, submission_only):
    recipient = insertion['senate']
    donor_chain = chains_by_senate[evidence['donor_senate_id']]
    donor = donor_chain['senate']
    matches = [row for row in donor_chain.get('workbook', []) if row['row'] == evidence['donor_oct10_row']]
    if len(matches) != 1:
        raise ValueError(f'Missing donor workbook row for {recipient["id"]}')
    workbook = matches[0]
    amount = recipient['sv_php']
    project_name = recipient['senate_title'].partition(':')[0].casefold()
    if not (
        recipient['gab_php'] == 0 and amount > 0 and donor['gab_php'] - donor['sv_php'] == amount
        and donor['path'] == recipient['path'] and workbook['submission_amount'] == donor['sv_php']
        and project_name in (workbook['justification'] or '').casefold()
    ):
        raise ValueError(f'Reallocation evidence no longer matches {recipient["id"]}')

    submissions = {}
    for vintage in ('oct10', 'nov13'):
        matches = [row for row in submission_only[vintage] if row['row'] == evidence[f'{vintage}_row']]
        if len(matches) != 1:
            raise ValueError(f'Missing {vintage} submission for {recipient["id"]}')
        row = matches[0]
        if not (
            title_typography_key(row['submission_title']).rstrip('.') == title_typography_key(recipient['senate_title']).rstrip('.')
            and row['submission_amount_php'] == amount
            and region_key_of(row['region']) == recipient['region_key']
            and text_key(row['province']) == text_key(recipient['path'][-1])
        ):
            raise ValueError(f'NIA submission no longer matches {recipient["id"]}')
        submissions[vintage] = row

    insertion['nia_submission_only'] = submissions
    insertion['senate_reverse_review'] = evidence
    donor_chain['nia_reallocation'] = {'senate_id': recipient['id'], 'title': recipient['senate_title'], 'amount_php': amount}


def attach_supporting_docs(chains):
    """Attach [POW FOR REVIEW] package availability to chains.

    The availability artifact keys support by the Senate workbook row id
    (``sen:rNNNN``). Chains carry that id on their October workbook rows; the
    one agency-only chain without a workbook row resolves through the agency
    leaf's Excel row, which indexes the same workbook. Each supported row lists
    its attributed packages with file counts, relative inventory paths, and
    the upstream Drive folder. The local mirror root is not exported.
    """
    art = read(POW_REVIEW)
    by_row = {r['senate_id']: r for r in art['coverage'] if r.get('supported')}
    rows_by_excel = {p['row']: p['id'] for p in read(DATA / 'senate_nia_dataset.json')['projects']}

    attached = 0
    for chain in chains:
        rows = [row['id'] for row in chain.get('workbook', [])]
        if not rows:
            # agency-only chains carry no workbook row; resolve through the
            # agency leaf's Excel row, which indexes the same workbook
            for vintage in ('oct10', 'nov13'):
                entry = chain.get('agency', {}).get(vintage)
                if entry and entry.get('excel_row') in rows_by_excel:
                    rows = [rows_by_excel[entry['excel_row']]]
                    break
        if not rows:
            continue
        support = next((by_row[rid] for rid in rows if rid in by_row), None)
        if not support:
            continue
        docs = {
            'source': 'POW FOR REVIEW',
            'drive_url': art['source_drive_url'],
            'match_strength': support.get('match_strength'),
            'pdf_confirmed': support.get('pdf_confirmed') or False,
            'doc_count': support.get('doc_count', 0),
            'pdf_count': support.get('pdf_count', 0),
            'image_count': support.get('image_count', 0),
            'pow_pdf_count': support.get('pow_pdf_count', 0),
            'photo_count': support.get('photo_count', 0),
            'packages': [
                {
                    'name': pk.get('package_name'),
                    'path': pk.get('package_path'),
                    'score': pk.get('score'),
                    'doc_count': pk.get('doc_count', 0),
                    'pdf_count': pk.get('pdf_count', 0),
                    'image_count': pk.get('image_count', 0),
                    'pow_pdf_count': pk.get('pow_pdf_count', 0),
                    'photo_count': pk.get('photo_count', 0),
                }
                for pk in support.get('packages', [])
            ],
        }
        chain['supporting_docs'] = docs
        attached += 1
    return attached


DMS_PAIR_AT_END = re.compile(
    r"""(?<![\d+.-])\d{1,2}°\d{1,2}'\d{1,2}(?:\.\d+)?"[ns]"""
    r"""[, ]*\d{1,3}°\d{1,2}'\d{1,2}(?:\.\d+)?"[ew]$""",
)


def apply_senate_reverse_review(chains):
    """Apply reviewed links and expose unresolved candidates with their source locators."""
    insertions = {
        c['senate']['id']: c for c in chains
        if c.get('senate') and not (c.get('nep') or c.get('house')) and not c['senate']['house_id']
    }
    nep_only = {c['nep']['id']: c for c in chains if c.get('nep') and not (c.get('house') or c.get('senate'))}
    chains_by_senate = {c['senate']['id']: c for c in chains if c.get('senate')}
    submission_only = read(SUBMISSION_ONLY)
    joined = set()
    reviewed = set()
    candidate_ids = set()
    for evidence in read(SENATE_REVERSE_REVIEW):
        senate_id = evidence['senate_id']
        insertion = insertions.get(senate_id)
        if not insertion or senate_id in reviewed:
            raise ValueError(f'Invalid Senate reverse review source: {senate_id}')
        reviewed.add(senate_id)
        senate = insertion['senate']
        decision = evidence['decision']
        if decision == 'reallocation':
            attach_reviewed_reallocation(chains_by_senate, insertion, evidence, submission_only)
            continue
        if decision == 'unmatched':
            insertion['senate_reverse_review'] = evidence
            continue

        nep_id = evidence['nep_id']
        candidate = nep_only.get(nep_id)
        if not candidate or nep_id in candidate_ids or decision not in ('join', 'review'):
            raise ValueError(f'Invalid NEP candidate for Senate reverse review: {senate_id}')
        candidate_ids.add(nep_id)
        nep = candidate['nep']
        oct10 = candidate.get('workbook', [])
        nov13 = candidate.get('november_review', [])
        if len(oct10) != 1 or len(nov13) != 1:
            raise ValueError(f'Missing workbook evidence for {senate_id}')
        oct10, nov13 = oct10[0], nov13[0]
        amount = nep['amount_php']
        if not (
            oct10['row'] == evidence['oct10_row'] and int(nov13['nov13_row']) == evidence['nov13_row']
            and oct10['nep_join']['id'] == nep_id and not oct10['house_join']
            and senate['gab_php'] == 0 and oct10['hgab_amount'] == 0 and nov13['hgab_amount_php'] == '0'
            and amount == senate['sv_php'] == oct10['nep_amount'] == oct10['submission_amount']
            and str(amount) == nov13['nep_amount_php']
            and region_key_of(nep['region']) == senate['region_key']
            and text_key(nep['province']) == text_key(senate['path'][-1])
        ):
            raise ValueError(f'Source records no longer support reverse review for {senate_id}')

        if evidence.get('detail_difference') == 'coordinates':
            titles = tuple(map(title_typography_key, (
                oct10['submission_label'], nov13['submission_title'], senate['senate_title'],
            )))
            bases = [DMS_PAIR_AT_END.sub('', title).strip() for title in titles]
            if not (
                len(set(bases)) == 1 and titles[0] == titles[1] != titles[2]
                and all(DMS_PAIR_AT_END.search(title) for title in titles)
            ):
                raise ValueError(f'Coordinate-only review no longer agrees for {senate_id}')

        candidate['senate_reverse_review'] = evidence
        if decision == 'review':
            insertion['senate_reverse_review'] = evidence
            continue
        candidate['senate'] = senate
        candidate['senate_restoration'] = {
            'method': 'reviewed_senate_to_nia_submission',
            'oct10_row': evidence['oct10_row'],
            'nov13_row': evidence['nov13_row'],
        }
        joined.add(insertion['id'])

    return [chain for chain in chains if chain['id'] not in joined]


def restoration_title_parts(title):
    """Split a title with a terminal coordinate pair into scope, locality, and site."""
    title = title_typography_key(title).replace('""', '"')
    site = DMS_PAIR_AT_END.search(title)
    if not site:
        return None
    description = title[:site.start()].rstrip(' ,')
    parts = re.split(r' at (?:barangay |brgy\.)', description, maxsplit=1)
    if len(parts) != 2 or not all(parts):
        return None
    scope, locality = parts
    _, _, jurisdiction = locality.partition(',')
    return scope, locality, jurisdiction, re.sub(r'[, ]', '', site[0])


def link_senate_restorations_with_detail_differences(chains):
    """Use the latest verified NIA revision and record any Senate site or locality change."""
    removed = set()
    for difference in ('coordinates', 'locality'):
        proposals = defaultdict(list)
        insertions = defaultdict(list)

        def match_key(title, region, province, amount):
            if not (parts := restoration_title_parts(title)):
                return None
            scope, locality, jurisdiction, site = parts
            detail = locality if difference == 'coordinates' else (jurisdiction, site)
            return scope, detail, region_key_of(region), text_key(province), amount

        for chain in chains:
            if chain['id'] in removed:
                continue
            nep, house, senate = (chain.get(stage) for stage in ('nep', 'house', 'senate'))
            if senate and not (nep or house) and not senate['house_id'] and senate['gab_php'] == 0 and senate['sv_php'] > 0:
                if chain.get('nia_submission_only'):
                    continue
                key = match_key(senate['senate_title'], senate['region_key'], senate['path'][-1], senate['sv_php'])
                if key:
                    insertions[key].append(chain)
            if not nep or house or senate:
                continue
            october = chain.get('workbook', [])
            november = chain.get('november_review', [])
            if len(october) != 1 or len(november) != 1:
                continue
            oct10, nov13 = october[0], november[0]
            amount = nep['amount_php']
            if not (oct10['nep_join']['id'] == nep['id'] and not oct10['house_join']
                    and amount == oct10['nep_amount'] == oct10['submission_amount']
                    and str(amount) == nov13['nep_amount_php']
                    and oct10['hgab_amount'] == 0 and nov13['hgab_amount_php'] == '0'
                    and region_key_of(nep['region']) == region_key_of(oct10['region_canonical'])
                    and text_key(nep['province']) == text_key(oct10['province'])):
                continue
            key = match_key(nov13['submission_title'], nep['region'], nep['province'], amount)
            if key:
                proposals[key].append((chain, oct10, nov13))

        for key, rows in insertions.items():
            matches = proposals.get(key, [])
            if len(rows) != 1 or len(matches) != 1:
                continue
            insertion = rows[0]
            chain, oct10, nov13 = matches[0]
            senate = insertion['senate']
            previous = insertion.get('senate_reverse_review') or {}
            prior_candidate = chain.get('senate_reverse_review') or {}
            if (previous.get('nep_id', chain['nep']['id']) != chain['nep']['id']
                    or prior_candidate.get('senate_id', senate['id']) != senate['id']):
                continue
            _, nia_locality, _, nia_site = restoration_title_parts(nov13['submission_title'])
            _, senate_locality, _, senate_site = restoration_title_parts(senate['senate_title'])
            if difference == 'coordinates' and nia_site == senate_site:
                continue
            if difference == 'locality' and nia_locality == senate_locality:
                continue
            note = previous.get('note') if previous.get('decision') == 'review' else None
            chain['senate'] = senate
            chain['senate_restoration'] = {
                'method': f'unique_november_nia_base_title_with_{difference}_difference',
                'oct10_row': oct10['row'],
                'nov13_row': int(nov13['nov13_row']),
            }
            chain['senate_reverse_review'] = {
                **chain['senate_restoration'], 'decision': 'join',
                'senate_id': senate['id'], 'nep_id': chain['nep']['id'],
                'detail_difference': difference,
                'note': note or ('The November NIA submission and the Senate agree on the project and allocation. '
                                 f'The {difference} differ in their published descriptions.'),
            }
            removed.add(insertion['id'])

    return [chain for chain in chains if chain['id'] not in removed]


def workbook_project_key(title, nep_amount, house_amount):
    title = unicodedata.normalize('NFKC', title or '').casefold()
    title = ''.join(char for char in title if char.isalnum())
    return title, int(nep_amount or 0), int(house_amount or 0)


def agency_workbook_targets(chains, vintage):
    targets = defaultdict(list)
    for chain in chains:
        if vintage == 'oct10':
            rows = ((row['label'], row['nep_amount'], row['hgab_amount'], row['row'])
                    for row in chain.get('workbook', []))
        else:
            rows = ((row['title_nov13'], row['nep_amount_php'], row['hgab_amount_php'], int(row['nov13_row']))
                    for row in chain.get('november_review', []))
        for title, nep_amount, house_amount, workbook_row in rows:
            targets[workbook_project_key(title, nep_amount, house_amount)].append((chain, workbook_row))
    return targets


def workbook_anchor_targets(chains, vintage):
    targets = defaultdict(list)
    for chain in chains:
        collection, locator, title, nep, house = (
            ('workbook', 'row', 'label', 'nep_amount', 'hgab_amount') if vintage == 'oct10'
            else ('november_review', 'nov13_row', 'title_nov13', 'nep_amount_php', 'hgab_amount_php')
        )
        for row in chain.get(collection, []):
            key = workbook_project_key(row[title], row[nep], row[house])
            targets[int(row[locator]), key].append(chain)
    return targets


def pair_agency_reconciliations(chains, crosswalk):
    """Pair unique budget observations across agency vintages."""
    by_vintage = {'oct10': defaultdict(list), 'nov13': defaultdict(list)}
    for chain in chains:
        for vintage, entry in chain['agency'].items():
            title = workbook_project_key(entry['title'], None, None)[0]
            key = title, entry['nep_amount_php'], entry['hgab_amount_php']
            by_vintage[vintage][key].append((chain, entry))

    def agency_only(chain):
        return not (chain.get('nep') or chain.get('house') or chain.get('senate'))

    consumed = set()
    november_by_row = defaultdict(list)
    for observations in by_vintage['nov13'].values():
        for chain, entry in observations:
            if agency_only(chain):
                november_by_row[str(entry.get('excel_row'))].append((chain, entry))

    for key, observations in by_vintage['oct10'].items():
        for chain, entry in observations:
            nov13 = crosswalk.get(str(entry.get('excel_row')))
            targets = november_by_row.get(nov13, [])
            if not agency_only(chain) or 'nov13' in chain['agency'] or len(targets) != 1:
                continue
            later_chain, later_entry = targets[0]
            later_key = (workbook_project_key(later_entry['title'], None, None)[0],
                         later_entry['nep_amount_php'], later_entry['hgab_amount_php'])
            if later_chain['id'] in consumed or key != later_key:
                continue
            later_entry['link_status'] = 'Verified workbook crosswalk and original budget amounts agree'
            later_entry['paired_agency_id'] = entry['id']
            chain['agency']['nov13'] = later_entry
            consumed.add(later_chain['id'])

    for key, november in by_vintage['nov13'].items():
        october = by_vintage['oct10'].get(key, [])
        if not key[0] or len(october) != 1 or len(november) != 1 or november[0][0]['id'] in consumed:
            continue
        oct_chain, oct_entry = october[0]
        nov_chain, nov_entry = november[0]
        if not agency_only(nov_chain) or 'oct10' in nov_chain['agency'] or 'nov13' in oct_chain['agency']:
            continue

        if agency_only(oct_chain):
            nov_entry['link_status'] = 'Unique October agency title and budget amounts agree'
        else:
            house = oct_chain.get('house')
            senate = oct_chain.get('senate') or {}
            workbook = oct_chain.get('workbook', [])
            if not (
                house and not oct_chain.get('nep') and not oct_chain.get('november_review')
                and senate.get('sv_php') == 0 and len(workbook) == 1
                and key[1] == 0 and key[2] == house['amount_php'] == senate['gab_php']
                and workbook[0]['row'] == oct_entry.get('matched_workbook_row')
                and not workbook[0]['submission_label']
            ):
                continue
            nov_entry['link_status'] = 'Unique October agency record linked to the House cut'
            nov_entry['house_amount_agrees'] = True

        nov_entry['paired_agency_id'] = oct_entry['id']
        oct_chain['agency']['nov13'] = nov_entry
        consumed.add(nov_chain['id'])
    return [chain for chain in chains if chain['id'] not in consumed]


def write_downloads(chains, senate_mapped, totals, bundle):
    """Static download exports under web/public/data/export/nia/."""
    import sys
    sys.path.insert(0, str(ROOT / 'data_formalization' / 'scripts'))
    from export_downloads import write_csv, write_sums

    export_dir = ROOT / 'web' / 'public' / 'data' / 'export' / 'nia'
    export_dir.mkdir(parents=True, exist_ok=True)

    def php_of(value):
        return value

    simple_cols = ['id', 'chain_type', 'title', 'region', 'region_label',
                   'province',
                   'nep_amount_php', 'house_amount_php',
                   'nia_oct10_hgab_php', 'nia_nov13_hgab_php',
                   'senate_id', 'senate_pdf_page', 'senate_status',
                   'senate_gab_php', 'senate_sv_php',
                   'senate_region_printed', 'senate_region_key',
                   'action_nep_house', 'action_house_senate',
                   'match_house_senate', 'review_flagged', 'review_fixed']

    sen_status = {0: 'cut_to_zero'}
    def senate_action(r):
        if not r:
            return None
        if not r.get('house_id'):
            return 'insertion'
        gab, sv = r.get('gab_php'), r.get('sv_php')
        if gab and sv == 0:
            return 'cut_to_zero'
        if sv > gab:
            return 'increase'
        if sv < gab:
            return 'decrease'
        if r.get('senate_title') and r['senate_title'] != r['hb_title']:
            return 'revised_description'
        return 'no_amount_change'

    def chain_simple(row):
        sen = row.get('senate') or {}
        findings = row.get('findings') or []
        return {
            'id': row['id'],
            'chain_type': ('senate_restoration' if row.get('senate_restoration') else
                           'house' if row.get('house') else
                           'nep_only' if row.get('nep') else
                           'senate_insertion' if row.get('senate') else 'agency_only'),
            'title': (row.get('house') or {}).get('title') or (row.get('nep') or {}).get('title')
                     or sen.get('senate_title') or (row.get('agency', {}).get('nov13') or {}).get('title'),
            'region': ((row.get('house') or {}).get('region') or (row.get('nep') or {}).get('region')
                       or sen.get('region_key') or sen.get('region') or '').upper() or None,
            'region_label': ((row.get('house') or {}).get('region') or
                             (row.get('nep') or {}).get('region')),
            'province': ((row.get('house') or {}).get('province') or
                         (row.get('nep') or {}).get('province') or
                         (sen.get('path') or [None])[-1]),
            'nep_amount_php': (row.get('nep') or {}).get('amount_php'),
            'house_amount_php': (row.get('house') or {}).get('amount_php'),
            'nia_oct10_hgab_php': (row.get('agency', {}).get('oct10') or {}).get('hgab_amount_php'),
            'nia_nov13_hgab_php': (row.get('agency', {}).get('nov13') or {}).get('hgab_amount_php'),
            'senate_id': sen.get('id'), 'senate_pdf_page': sen.get('pdf_page'),
            'senate_status': senate_action(sen),
            'senate_gab_php': sen.get('gab_php'), 'senate_sv_php': sen.get('sv_php'),
            'senate_region_printed': sen.get('region'),
            'senate_region_key': sen.get('region_key'),
            'action_nep_house': (None if not row.get('nep') and not row.get('house') else
                                 'same_amount' if row.get('nep') and row.get('house') and
                                 row['nep']['amount_php'] == row['house']['amount_php']
                                 else 'amount_changed' if row.get('nep') and row.get('house')
                                 else 'house_without_nep' if row.get('house') else 'nep_without_house'),
            'action_house_senate': senate_action(sen),
            'match_house_senate': sen.get('match') if sen.get('house_id') else None,
            'review_flagged': bool(findings),
            'review_fixed': any((f.get('status_nov13') or '').startswith('FIXED') for f in findings),
        }

    n_simple = write_csv(export_dir / 'chains-simple.csv',
                         (chain_simple(c) for c in chains), simple_cols)

    SKIP = {'comparison', 'review', 'workbook', 'november_review', 'findings', 'agency', 'supporting_docs'}
    NEST_SUB = {'nep': 'nep_', 'house': 'house_', 'senate': 'senate_'}

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

    full_rows = [flatten(c) for c in chains]
    full_cols = sorted({k for r in full_rows for k in r})
    for lead in reversed(('id', 'title', 'region', 'province')):
        if lead in full_cols:
            full_cols.remove(lead)
            full_cols.insert(0, lead)
    # findings back as JSON arrays for the full export
    full_rows = [{**f,
                  'findings': json.dumps(c.get('findings') or [], ensure_ascii=False),
                  'workbook': json.dumps(c.get('workbook') or [], ensure_ascii=False),
                  'november_review': json.dumps(c.get('november_review') or [], ensure_ascii=False)}
                 for f, c in zip(full_rows, chains)]
    full_cols += ['findings', 'workbook', 'november_review']
    n_full = write_csv(export_dir / 'chains-full.csv', full_rows, full_cols)

    # supporting docs: one row per attributed POW package
    support_rows = []
    for row in chains:
        docs = row.get('supporting_docs') or {}
        for pk in docs.get('packages', []):
            support_rows.append({
                'chain_id': row['id'],
                'senate_workbook_row': next((w['id'] for w in row.get('workbook', [])), ''),
                'package_name': pk.get('name'),
                'package_path': pk.get('path'),
                'score': pk.get('score'),
                'doc_count': pk.get('doc_count', 0),
                'pdf_count': pk.get('pdf_count', 0),
                'image_count': pk.get('image_count', 0),
                'pow_pdf_count': pk.get('pow_pdf_count', 0),
                'photo_count': pk.get('photo_count', 0),
            })
    support_cols = ['chain_id', 'senate_workbook_row', 'package_name', 'package_path',
                    'score', 'doc_count', 'pdf_count', 'image_count', 'pow_pdf_count', 'photo_count']
    n_support = write_csv(export_dir / 'supporting-docs.csv', support_rows, support_cols)

    finding_rows = []
    for row in chains:
        for f in row.get('findings') or []:
            finding_rows.append({'chain_id': row['id'],
                                 **{k: f.get(k) for k in
                                    ('flag_id', 'flag_category', 'status_nov13', 'disposition',
                                     'issue_detail', 'resolution_detail', 'evidence')}})
    finding_cols = ['chain_id', 'flag_id', 'flag_category', 'status_nov13', 'disposition',
                    'issue_detail', 'resolution_detail', 'evidence']
    n_findings = write_csv(export_dir / 'findings.csv', finding_rows, finding_cols)

    # rollups: printed province + region subtotals joined from the raw snapshot
    # (document-order pairing — the same lineage can print twice; keep each
    # heading with its own leaf group)
    raw = read(ANNEX_RAW)['rows']
    cur4 = cur5 = None
    leaves_of = []  # [kind, heading row, leaves] in document order
    for row in raw:
        if row['kind'] == 'heading':
            level = row.get('level')
            if level == 4:
                cur4, cur5 = row, None
                leaves_of.append(['region', row, []])
            elif level == 5:
                cur5 = row
                leaves_of.append(['province', row, []])
            else:
                cur4 = cur5 = None
        else:
            if cur5 is not None and leaves_of:
                leaves_of[-1][2].append(row)
            elif cur4 is not None and leaves_of:
                # leaves directly under a region (no province step)
                for entry in reversed(leaves_of):
                    if entry[0] == 'region':
                        entry[2].append(row)
                        break
    rollup_rows = []
    for kind, h, leaves in leaves_of:
        lineage = [p.strip() for p in h['path']] + [(h['hb_title'] or h['senate_title']).strip()]
        leaf_gab = sum(r.get('gab') or 0 for r in leaves) if leaves else None
        leaf_sv = sum(r.get('sv') or 0 for r in leaves) if leaves else None
        rollup_rows.append({
            'program': 'nia', 'annex': 'A-3',
            'level': kind,
            'program_line': ' / '.join(lineage[1:4]) if kind == 'region' else ' / '.join(lineage[1:5]),
            'parent_printed': lineage[-2] if kind == 'province' else None,
            'name_printed': lineage[-1],
            'region_key': region_key_of(lineage[-2] if kind == 'province' else lineage[-1]),
            'gab_php': h['gab'], 'sv_php': h['sv'], 'pdf_page': h['pdf_page'],
            'leaf_rows': len(leaves),
            'leaf_gab_sum_php': leaf_gab, 'leaf_sv_sum_php': leaf_sv,
            'reconciles': (leaf_gab == h['gab'] and leaf_sv == h['sv']) if leaves else None,
        })
    rollup_cols = ['program', 'annex', 'level', 'program_line', 'parent_printed',
                   'name_printed', 'region_key', 'gab_php', 'sv_php', 'pdf_page',
                   'leaf_rows', 'leaf_gab_sum_php', 'leaf_sv_sum_php', 'reconciles']
    n_rollups = write_csv(export_dir / 'rollups.csv', rollup_rows, rollup_cols)

    full_doc = {
        'program': 'nia',
        'description': 'NIA provenance explorer full export — verbatim chain '
                       'records plus manifest. See chains-simple.csv for the '
                       'table view and SHA256SUMS.txt for file hashes.',
        'totals': totals,
        'stage_changes': bundle['stage_changes'],
        'inputs': read_inputs(bundle),
        'coordinate_workbook': bundle['coordinate_workbook'],
        'chains': chains,
    }
    (export_dir / 'full.json').write_text(
        json.dumps(full_doc, ensure_ascii=False) + '\n', encoding='utf-8')
    write_sums(export_dir, ['chains-simple.csv', 'chains-full.csv',
                            'findings.csv', 'rollups.csv', 'supporting-docs.csv', 'full.json'])
    print(f'exports: simple={n_simple} full={n_full} findings={n_findings} '
          f'rollups={n_rollups} supporting_docs={n_support} -> {export_dir.relative_to(ROOT)}')


def build():
    workbench = read(DATA / 'nia_workbench.json')
    projects = {
        side: {r['id']: {k: r.get(k) for k in
                        ('id', 'title', 'amount_php', 'source', 'region', 'province', 'subprogram_key', 'category', 'extraction_flags')}
               for r in workbench['stages'][side]['projects']}
        for side in ('nep', 'house')
    }
    agency_targets = defaultdict(set)
    review = defaultdict(list)
    senate_links = {}
    for line in LEDGER.read_text(encoding='utf-8').splitlines():
        event = json.loads(line)
        payload = event['payload']
        subject = event['subject']
        if event['type'] == 'match.asserted':
            if payload['method'] == 'title_key_exact':
                agency_targets[payload['to']].add(subject)
            elif event['provenance'].get('snapshot') == 'view/senate/annex_a3_nia_mapped':
                senate_links[subject] = payload['to']
        if event['type'] == 'review.requested':
            review[subject].append(payload)

    senate = read(ANNEX)['rows']
    headings, leaf_head = senate_rollups()
    attach_rollups(senate, headings, leaf_head)
    for row in senate:
        for side in ('hb', 'senate'):
            # The extractor may split a single title's coordinates across columns.
            text = '\n'.join(filter(None, [row[f'{side}_title'], *row[f'{side}_coords']]))
            if result := analyze_text(text):
                row[f'{side}_gps'] = {
                    'status': result['status'],
                    'points': [p for p in result.get('points', [])
                               if p.get('latitude') is not None and p.get('longitude') is not None],
                }
    senate_by_house = {}
    for row in senate:
        house = row['house_id']
        if house is not None:
            if senate_links.get(row['id']) != house or house in senate_by_house:
                raise ValueError(f"Inconsistent Senate mapping for {row['id']}")
            senate_by_house[house] = row
        elif row['id'] in senate_links:
            raise ValueError(f"Missing House locator for {row['id']}")

    chains = []
    for comparison in workbench['comparison']:
        nep = projects['nep'].get(comparison['nep_id'])
        house = projects['house'].get(comparison['house_id'])
        row = {
            'id': comparison['id'], 'nep': nep, 'house': house,
            'senate': senate_by_house.get(comparison['house_id']),
            'comparison': {k: comparison.get(k) for k in
                           ('status', 'strict_status', 'method', 'variant_mark', 'ambiguous_title')},
            'agency': {}, 'review': review[comparison['nep_id']],
        }
        chains.append(row)
    chains.extend({'id': r['id'], 'senate': r, 'agency': {}} for r in senate if not r['house_id'])

    crosswalk = workbook_crosswalk()
    attach_workbook_evidence(chains, crosswalk)
    chains = merge_workbook_pairs(chains)
    chains = apply_senate_reverse_review(chains)
    chains = link_senate_restorations(chains)
    chains = link_senate_restorations(chains, normalize_typography=True)
    chains = link_senate_restorations(chains, normalize_typography=True, compare_without_barangay=True)
    chains = link_senate_restorations_with_detail_differences(chains)
    attach_senate_revision_comparisons(chains)
    by_nep = {chain['nep']['id']: chain for chain in chains if chain.get('nep')}

    agency_totals = {}
    agency_sources = {}
    for vintage in ('oct10', 'nov13'):
        data = read(DATA / f'nia_agency_recon_{vintage}.json')
        keys = Counter(r['title_key'] for r in data['leaves'])
        agency_totals[vintage] = data['summary']
        agency_sources[vintage] = data['metadata']
        leaves = data['leaves']
        project_keys = {
            leaf['id']: workbook_project_key(leaf['title'], leaf['nep_amount_php'], leaf['hgab_amount_php'])
            for leaf in leaves
        }
        project_key_counts = Counter(project_keys.values())
        anchors = workbook_anchor_targets(chains, vintage)
        workbook_targets = agency_workbook_targets(chains, vintage)
        pending = []
        for leaf in leaves:
            neps = sorted(agency_targets['nia_agency:' + leaf['title_key']])
            nep, status = agency_link(leaf, neps, keys[leaf['title_key']], projects['nep'])
            entry = {**leaf, 'link_status': status, 'candidate_nep_ids': neps}
            key = project_keys[leaf['id']]
            row_number = leaf.get('excel_row')
            matches = anchors.get((row_number, key), [])
            if len(matches) == 1:
                chain = matches[0]
                if ((not key[1] or chain.get('nep')) and (not key[2] or chain.get('house'))
                        and vintage not in chain['agency'] and (not nep or by_nep[nep] is chain)):
                    entry['link_status'] = 'Workbook row locator, original title and budget amounts agree'
                    entry['matched_workbook_row'] = row_number
                    chain['agency'][vintage] = entry
                    continue
            if nep:
                by_nep[nep]['agency'][vintage] = entry
            else:
                pending.append(entry)

        fallback = defaultdict(list)
        for entry in pending:
            key = project_keys[entry['id']]
            targets = workbook_targets.get(key, [])
            if key[0] and project_key_counts[key] == 1 and len(targets) == 1:
                chain, workbook_row = targets[0]
                # A workbook row for both budget stages must resolve to both
                # records in the same chain before it can place an agency leaf.
                if ((not key[1] or chain.get('nep')) and (not key[2] or chain.get('house'))
                        and vintage not in chain['agency']):
                    fallback[chain['id']].append((entry, chain, workbook_row))

        attached = set()
        for matches in fallback.values():
            if len(matches) == 1:
                entry, chain, workbook_row = matches[0]
                entry['link_status'] = 'Unique workbook title and budget amounts agree'
                entry['matched_workbook_row'] = workbook_row
                chain['agency'][vintage] = entry
                attached.add(entry['id'])

        for chain in chains:
            if chain.get('house') and vintage in chain['agency']:
                entry = chain['agency'][vintage]
                entry['house_amount_agrees'] = entry['hgab_amount_php'] == chain['house']['amount_php']
        chains.extend({'id': entry['id'], 'agency': {vintage: entry}}
                      for entry in pending if entry['id'] not in attached)

    chains = pair_agency_reconciliations(chains, crosswalk)
    attach_supporting_docs(chains)

    october_projects = read(DATA / 'senate_nia_dataset.json')['projects']
    coordinate_by_id, coordinate_source = build_coordinate_evidence(october_projects)
    exported_coordinate_ids = set()
    for chain in chains:
        for workbook_row in chain.get('workbook', []):
            if evidence := coordinate_by_id.get(workbook_row['id']):
                workbook_row['coordinate_workbook'] = evidence
                exported_coordinate_ids.add(workbook_row['id'])
    if exported_coordinate_ids != coordinate_by_id.keys():
        raise ValueError('NIA web export is missing matched coordinate workbook evidence')

    totals = {}
    for side, source, field in (
        ('nep', projects['nep'].values(), 'amount_php'),
        ('house', projects['house'].values(), 'amount_php'),
        ('senate', senate, 'sv_php'),
    ):
        expected = {r['id']: r[field] for r in source}
        actual = [r[side] for r in chains if r.get(side)]
        if len(actual) != len(expected) or {r['id']: r[field] for r in actual} != expected:
            raise ValueError(f'{side} export dropped or duplicated source records')
        totals[side] = {'rows': len(actual), 'amount_php': sum(expected.values())}
    for vintage, controls in agency_totals.items():
        actual = [r['agency'][vintage] for r in chains if vintage in r['agency']]
        if len(actual) != controls['leaves'] or len({r['id'] for r in actual}) != len(actual):
            raise ValueError(f'{vintage} export dropped or duplicated agency leaves')
        controls['linked'] = sum(vintage in r['agency'] and bool(r.get('nep') or r.get('house')) for r in chains)

    stage_changes = {
        'nep_house': summarize_budget_changes(
            (((row.get('nep') or {}).get('amount_php'), (row.get('house') or {}).get('amount_php'))
             for row in chains),
            totals['nep']['amount_php'], totals['house']['amount_php']),
        'house_senate': summarize_budget_changes(
            ((row['gab_php'], row['sv_php']) for row in senate),
            totals['house']['amount_php'], totals['senate']['amount_php']),
    }

    inputs = [LEDGER, ANNEX, ANNEX_RAW, RECONCILIATION, SENATE_REVERSE_REVIEW, SUBMISSION_ONLY, NEP_PDF, DATA / 'nia_workbench.json',
              ROOT / 'gps-analysis/scan_gps_inventory.py', ROOT / 'gps-analysis/coordinate_parse.py']
    inputs.extend(DATA / name for name in (
        'senate_nia_dataset.json', 'nia_submitted_list_status_nov13.csv',
        'nia_nep_annex_full_nov13.csv', 'nia_flags_ledger_nov13.csv',
    ))
    inputs.append(POW_REVIEW)
    inputs.extend(DATA / f'nia_agency_recon_{v}.json' for v in agency_totals)
    inputs.append(COORDINATE_WORKBOOK)
    return {
        'totals': totals, 'agency_totals': agency_totals, 'stage_changes': stage_changes,
        'agency_sources': agency_sources, 'chains': chains,
        'coordinate_workbook': coordinate_source,
        'inputs': {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in inputs},
    }


def read_inputs(bundle):
    return bundle['inputs']


if __name__ == '__main__':
    bundle = build()
    write_downloads(bundle['chains'], read(ANNEX)['rows'], bundle['totals'], bundle)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({'chains': len(bundle['chains']), **bundle['totals'], **bundle['agency_totals']}, indent=2))
