"""Build the DPWH provenance explorer from existing extracts and review sets.

Chain unit: the House Vol I-C third-reading project leaf. Stages joined per
the provenance guide — NEP source rows via the reading comparison, Senate
Annex A-4 via the verified printed-page crosswalk, HGAB review evidence via
the (pdf page, amount, title) bridge. Every source row must appear exactly
once; the exporter refuses to write a bundle that drops or duplicates rows.
"""

from collections import Counter, defaultdict
from hashlib import sha256
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'web/public/data/dpwh.json'

NEP = ROOT / 'analysis/data/nep_2027_source_projects.json'
COMPARISON = ROOT / 'analysis/data/dpwh_comparison_all_2027.csv'
TREE = ROOT / 'analysis/data/hb_dpwh_native_ic_projects_3rd_reading.json'
ANNEX = ROOT / 'Senate_report_data/data/derived/senate_annex_a4_dpwh_mapped.json'
RAW_ANNEX = ROOT / 'Senate_report_data/data/derived/senate_annex_a4_dpwh.json'
HGAB = ROOT / 'dpwh_HGAB_REVIEW_SET/house-bill-2027-dpwh-projects.csv'
FLAGS = ROOT / 'dpwh_HGAB_REVIEW_SET/house-bill-2027-dpwh-red-flags.csv'

REGION_KEYS = {
    'National Capital Region': 'NCR',
    'Cordillera Administrative Region': 'CAR',
    'MIMAROPA Region': 'MIMAROPA',
    'Negros Island Region': 'NIR',
}


def region_key(label):
    return REGION_KEYS.get(label, label)


def norm_title(text):
    return ' '.join((text or '').split())


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as source:
        return list(csv.DictReader(source))


def pesos(value):
    return int(value) if value not in (None, '') else None


def page_field(value):
    """Page cells hold a single number or a comma list for split-page rows."""
    if value in (None, ''):
        return None
    return int(value) if value.isdigit() else value


def house_nodes(tree):
    """Index every tree node with its ancestor context; project leaves anchor chains."""
    nodes = {}
    leaves = {}

    def walk(node, context):
        kind = node.get('kind')
        ctx = dict(context)
        if kind in ('expense_class', 'program', 'region', 'office', 'pap', 'section'):
            ctx[kind] = node.get('label')
        record = {
            'id': node['id'],
            'kind': kind,
            'title': node.get('label'),
            'amount_php': node.get('printed_amount_php'),
            'pdf_page': node['source'].get('pdf_page') if isinstance(node.get('source'), dict) else None,
            'expense_class': ctx.get('expense_class'),
            'program': ctx.get('program'),
            'pap': ctx.get('pap'),
            'region': ctx.get('region'),
            'region_key': region_key(ctx.get('region')),
            'office': ctx.get('office'),
        }
        nodes[node['id']] = record
        if kind == 'project' and not node.get('children'):
            leaves[node['id']] = record
            return
        for child in node.get('children', []):
            walk(child, ctx)

    walk(tree['root'], {})
    return nodes, leaves


def senate_action(row):
    """A-4 printed columns → shared action vocabulary."""
    if row['sv_php'] is None:
        return 'Cut to zero'
    if row['sv_php'] > row['gab_php']:
        return 'Increase'
    if row['sv_php'] < row['gab_php']:
        return 'Decrease'
    if norm_title(row['senate_title']) != norm_title(row['hb_title']):
        return 'Revised description'
    return 'No amount change'


def nep_house_action(chain):
    nep, house = chain.get('nep'), chain.get('house')
    if nep and house:
        return 'Same amount' if nep['amount_php'] == house['amount_php'] else 'Amount changed'
    if house:
        return 'House without NEP link'
    if nep:
        return 'NEP without House link'
    return None


def build():
    nep_source = read(NEP)
    nep_by_id = {p['source_id']: p for p in nep_source['projects']}
    tree = read(TREE)
    nodes, leaves = house_nodes(tree)
    comparison = csv_rows(COMPARISON)
    annex = read(ANNEX)

    chains = {}
    comparison_by_leaf = defaultdict(list)

    # -- House-anchored chains -------------------------------------------------
    for leaf_id, leaf in leaves.items():
        chains[f'hb:ic:{leaf_id}'] = {'id': f'hb:ic:{leaf_id}', 'house': leaf}

    for row in comparison:
        raw_ids = row.get('house_third_source_id') or row.get('house_source_id') or ''
        evidence = {
            'id': row['ID'],
            'match_status': row['Match status'],
            'reading_status': row['House reading status'],
            'house_minus_nep_php': pesos(row['HGAB3 minus HGAB2 PHP']) or None,
            'transparency_php': pesos(row['Transparency PHP']),
            'nep_pdf_page': page_field(row['nep_pdf_page']),
            'house_pdf_page': page_field(row['house_pdf_page']),
        }
        if not raw_ids:
            continue  # NEP-only comparison rows handled below
        anchor_id = raw_ids.split(',')[0].split(':')[-1]
        anchor = nodes[anchor_id]
        chain_id = f'hb:ic:{anchor_id}'
        chain = chains.get(chain_id)
        if anchor['kind'] != 'project':
            # Allocation/control rows: NEP-to-control observations, kept at their
            # own level per the guide (controls are not summed with their leaves).
            chain = chains.setdefault(chain_id, {
                'id': chain_id,
                'house': {**anchor, 'allocation_kind': 'control',
                          'node_kind': anchor['kind'],
                          'note': ('NEP observation reconciles to a House control or '
                                   'foreign-assisted project total, not a project leaf.')},
            })
        if chain.get('comparison'):
            raise ValueError(f'Two comparison rows anchor on {chain_id}')
        chain['comparison'] = evidence
        comparison_by_leaf[anchor_id].append(evidence)

    # -- NEP side ---------------------------------------------------------------
    for row in comparison:
        nep_id = row['nep_source_id']
        if not nep_id:
            continue
        source = nep_by_id[nep_id]
        nep = {
            'id': source['source_id'],
            'title': source['title'],
            'amount_php': source['amount_php'],
            'pdf_page': source['pdf_page'],
            'region': region_key(source['region']),
            'office': source['office'],
            'pap': source.get('pap3'),
            'program': source.get('program'),
            'zone': source.get('zone'),
            'allocation_kind': source.get('allocation_kind'),
        }
        raw_ids = row.get('house_third_source_id') or row.get('house_source_id') or ''
        if raw_ids:
            anchor_id = raw_ids.split(',')[0].split(':')[-1]
            anchor = nodes[anchor_id]
            chain_id = f'hb:ic:{anchor_id}'
            if anchor['kind'] != 'project':
                # Allocation/control rows: NEP-to-control observations, kept at their
                # own level per the guide (controls are not summed with their leaves).
                chain = chains.setdefault(chain_id, {
                    'id': chain_id,
                    'house': {**anchor, 'allocation_kind': 'control',
                              'node_kind': anchor['kind'],
                              'note': ('NEP observation reconciles to a House control or '
                                       'foreign-assisted project total, not a project leaf.')},
                })
            else:
                chain = chains[chain_id]
            if chain.get('nep'):
                raise ValueError(f'Comparison row lists two NEP rows for {chain_id}')
            chain['nep'] = nep
        else:
            chains[row['ID']] = {
                'id': row['ID'], 'nep': nep,
                'comparison': {'match_status': row['Match status'],
                               'reading_status': row['House reading status']},
            }

    # -- Senate Annex A-4 ---------------------------------------------------------
    # The raw snapshot carries the printed heading structure; attach the
    # verified roll-up subtotals and heading lineage to each Senate row.
    raw_annex = read(RAW_ANNEX)
    heading_by_id = {h['hid']: h for h in raw_annex.get('headings', [])}
    verified = set(raw_annex.get('rollup', {}).get('verified_subtotal_hids', []))

    operations = next(h for h in heading_by_id.values()
                      if h['name'] == 'OPERATIONS' and not h['path'])
    department = next(h for h in heading_by_id.values()
                      if h['name'] == 'DEPARTMENT OF PUBLIC WORKS AND HIGHWAYS' and not h['path'])
    components = {
        h['name']: {**h, 'listed_gab_php': 0, 'listed_sv_php': 0}
        for h in heading_by_id.values() if h['kind'] == 'program' and h['path'] == ['OPERATIONS']
    }
    road_system = next(name for name in components if name.startswith('ORGANIZATIONAL OUTCOME 1'))
    for row in raw_annex['projects']:
        heading = heading_by_id.get(row['region_heading']) or heading_by_id.get(row['office_heading'])
        name = next((name for name in (heading or {}).get('path', []) if name in components), None)
        if row['is_fap']:
            name = 'FOREIGN-ASSISTED PROJECTS'
        elif name is None and row['program'] in ('Replacement of Permanent Weak Bridges',
                                                 'Construction of New Bridges'):
            # These bridge rows have no enclosing region or office heading.
            name = road_system
        if name is None:
            raise ValueError(f"Missing A-4 operations category for {row['id']}")
        components[name]['listed_gab_php'] += row['gab_php'] or 0
        components[name]['listed_sv_php'] += row['sv_php'] or 0
    for control in components.values():
        if control['sv_php'] - control['listed_sv_php'] != control['gab_php'] - control['listed_gab_php']:
            raise ValueError(f"A-4 listed changes do not reconcile for {control['name']}")
    for key in ('gab_php', 'sv_php'):
        if sum(row[key] for row in components.values()) != operations[key]:
            raise ValueError(f'A-4 operations components do not reconcile for {key}')

    budget_controls = {
        # NEP Vol. II-B printed p. 2 (new general appropriations) and p. 3 (operations).
        'department': {'nep_php': 642_612_015_000, 'house_php': department['gab_php'],
                       'senate_php': department['sv_php']},
        'operations': {'nep_php': 572_924_074_000, 'house_php': operations['gab_php'],
                       'senate_php': operations['sv_php']},
        'components': [
            {'name': row['name'], 'house_php': row['gab_php'], 'senate_php': row['sv_php'],
             'listed_house_php': row['listed_gab_php'], 'listed_php': row['listed_sv_php'],
             'pdf_page': row['pdf_page']}
            for row in components.values()
        ],
    }

    def annex_rollup(row):
        """Verified office/region subtotals for a Senate row, as printed."""
        out_rollup = {}
        for field, label in (('office_heading', 'office'), ('region_heading', 'region')):
            hid = row.get(field)
            h = heading_by_id.get(hid)
            if h is None or hid not in verified:
                continue
            out_rollup[label] = {
                'name': h['name'], 'path': h['path'], 'pdf_page': h['pdf_page'],
                'gab_php': h['gab_php'], 'sv_php': h['sv_php'],
                'inc_php': h['inc_php'], 'dec_php': h['dec_php'], 'net_php': h['net_php'],
            }
        return out_rollup or None

    annex_stats = Counter()
    for row in annex['rows']:
        evidence = {
            'id': row['id'], 'pdf_page': row['pdf_page'],
            'hb_page_cited': row['hb_page_cited'], 'office': row['office'],
            'region': region_key(row['region']) if row['region'] else None,
            'region_key': region_key(row['region']) if row['region'] else None,
            'program': row['program'], 'hb_title': row['hb_title'],
            'senate_title': row['senate_title'], 'gab_php': row['gab_php'],
            'inc_php': row['inc_php'], 'dec_php': row['dec_php'],
            'net_php': row['net_php'], 'sv_php': row['sv_php'],
            'is_fap': row['is_fap'], 'match': row['match'],
            'amount_agrees': row['amount_agrees'],
            'rollup': annex_rollup(row),
        }
        target = row['tree_id']
        if target:
            chain_id = f'hb:ic:{target}'
        if target and chain_id in chains:
            chains[chain_id]['senate'] = evidence
            annex_stats['attached'] += 1
        else:
            # FAP nodes and the 8 unmatched rows stay inspectable as their own chains.
            if target:
                evidence['tree_id'] = target
                evidence['tree_title'] = row.get('tree_title')
                evidence['bridge_note'] = ('A-4 row anchored to a foreign-assisted project '
                                           'node, not a project leaf; kept as its own record.')
                annex_stats['fap_node'] += 1
            else:
                evidence['bridge_note'] = ('Unmatched A-4 row — the printed-page join found '
                                           'no House leaf; retained for review.')
                annex_stats['unmatched'] += 1
            chains[row['id']] = {'id': row['id'], 'senate': evidence}

    # -- HGAB review bridge -------------------------------------------------------
    hgab = csv_rows(HGAB)
    flags = csv_rows(FLAGS)
    flag_catalog = {}
    flags_by_hgab = defaultdict(list)
    for row in flags:
        flag_catalog.setdefault(row['flag_code'], {'flag': row['flag'], 'family': row['family'],
                                                   'source': row['source']})
        flags_by_hgab[row['hgab_id']].append(
            [row['flag_code'], row['family'], pesos(row['value_php'])])

    hgab_by_key = defaultdict(list)
    for row in hgab:
        hgab_by_key[(int(row['bill_pdf_page']), int(row['amount_php']),
                     norm_title(row['title']))].append(row)

    bridge = {'unique': 0, 'ambiguous': 0, 'missing': 0}
    bridged_hgab = set()
    for chain in chains.values():
        leaf = chain.get('house')
        if not leaf:
            continue
        hits = hgab_by_key.get((leaf['pdf_page'], leaf['amount_php'], norm_title(leaf['title'])), [])
        if len(hits) == 1:
            row = hits[0]
            bridged_hgab.add(row['hgab_id'])
            chain['review'] = {
                'hgab_id': row['hgab_id'],
                'key_documents_found': int(row['key_documents_found']),
                'has_pow': row['has_pow'] == 'true',
                'has_bp202': row['has_bp202'] == 'true',
                'has_development_council': row['has_development_council'] == 'true',
                'has_geotagged_photos': row['has_geotagged_photos'] == 'true',
                'has_certificate_of_implementability': row['has_certificate_of_implementability'] == 'true',
                'red_flags': int(row['red_flags']),
                'red_flag_codes': [c for c in row['red_flag_codes'].split('; ') if c],
                'house_insertion': row['house_insertion'] == 'true',
                'senate_files': int(row['senate_files']),
                'senate_files_redacted': int(row['senate_files_redacted']),
                'dpwh_transparency_files': int(row['dpwh_transparency_files']),
                'legislative_districts': row['legislative_districts'],
                'office_scope': row['office_scope'],
                'dpwh_proposal_code': row['dpwh_proposal_code'] or None,
                'project_page': row['project_page'] or None,
                'reviewer_page': row['reviewer_page'] or None,
            }
            chain['flags'] = flags_by_hgab.get(row['hgab_id'], [])
            bridge['unique'] += 1
        elif len(hits) > 1:
            bridge['ambiguous'] += 1
        else:
            bridge['missing'] += 1
    bridge['hgab_rows_unbridged'] = len(hgab) - len(bridged_hgab)

    # -- Stamp actions and comparison evidence -------------------------------------
    ordered = []
    for chain in chains.values():
        if chain.get('house') and chain['house']['id'] in comparison_by_leaf:
            entries = comparison_by_leaf[chain['house']['id']]
            chain['comparison'] = dict(entries[0])
            if len(entries) > 1:
                chain['comparison']['note'] = 'Repeated comparison key; see group members.'
        # Repeated-key groups: annotate members after ordering (comparison ids differ).
        senate = chain.get('senate')
        actions = {
            'nep_house': nep_house_action(chain),
            'house_senate': (senate_action(senate) if senate else
                             ('No Senate record' if chain.get('house') else None)),
        }
        chain['actions'] = actions
        ordered.append(chain)
    ordered.sort(key=lambda c: c['id'])

    # Repeated-key groups: annotate members after ordering (comparison ids differ).
    multi_members = defaultdict(list)
    for row in comparison:
        raw_ids = row.get('house_third_source_id') or row.get('house_source_id') or ''
        if ',' in raw_ids:
            for leaf_id in [p.split(':')[-1] for p in raw_ids.split(',')]:
                multi_members[leaf_id].append(row['ID'])
    for chain in ordered:
        leaf = chain.get('house')
        if leaf and leaf['id'] in multi_members:
            chain['comparison'] = dict(chain.get('comparison') or {})
            chain['comparison']['repeated_key_group'] = multi_members[leaf['id']]

    # -- Validation ------------------------------------------------------------------
    def tally(field, filter_fn):
        return sum(c[field]['amount_php' if field != 'senate' else 'sv_php'] or 0
                   for c in ordered if filter_fn(c))

    house_rows = [c for c in ordered if c.get('house')]
    leaf_chains = [c for c in house_rows if c['house'].get('allocation_kind') != 'control']
    control_chains = [c for c in house_rows if c['house'].get('allocation_kind') == 'control']
    if len(leaf_chains) != len(leaves):
        raise ValueError(f'Leaf chains {len(leaf_chains)} != tree leaves {len(leaves)}')
    if sum(c['house']['amount_php'] for c in leaf_chains) != \
            sum(l['amount_php'] for l in leaves.values()):
        raise ValueError('House amounts diverge from the native tree')

    nep_seen = [c['nep']['id'] for c in ordered if c.get('nep')]
    if Counter(nep_seen) != Counter(nep_by_id.keys()):
        missing = set(nep_by_id) - set(nep_seen)
        extra = [i for i, n in Counter(nep_seen).items() if n > 1]
        raise ValueError(f'NEP coverage broken: missing {len(missing)}, duplicated {extra[:5]}')

    senate_rows = [c['senate'] for c in ordered if c.get('senate')]
    if len(senate_rows) != annex['summary']['a4_rows']:
        raise ValueError(f"A-4 coverage {len(senate_rows)} != {annex['summary']['a4_rows']}")
    sv_total = sum(r['sv_php'] or 0 for r in senate_rows)
    gab_total = sum(r['gab_php'] or 0 for r in senate_rows)
    matched_gab = sum(r['gab_php'] or 0 for r in senate_rows if r['match'] != 'unmatched')
    matched_sv = sum(r['sv_php'] or 0 for r in senate_rows if r['match'] != 'unmatched')
    if matched_sv != annex['summary']['sv_php_matched']:
        raise ValueError(f'A-4 Senate total {matched_sv} != source {annex["summary"]["sv_php_matched"]}')
    if matched_gab != annex['summary']['gab_php_matched']:
        raise ValueError(f'A-4 GAB total {matched_gab} != source {annex["summary"]["gab_php_matched"]}')
    if annex['summary']['match_stats']['unmatched'] != sum(1 for r in senate_rows if r['match'] == 'unmatched'):
        raise ValueError('A-4 unmatched count drifted; recheck the bridge')

    referenced = set()
    for row in comparison:
        if row['nep_source_id']:
            referenced.add(row['ID'])
        raw_ids = row.get('house_third_source_id') or row.get('house_source_id') or ''
        if raw_ids:
            referenced.add(row['ID'])
    # Every comparison row is carried either on a leaf chain or as a NEP-only chain.
    carried = {c.get('comparison', {}).get('id') for c in ordered if c.get('comparison')}
    carried |= {c['id'] for c in ordered if not c.get('house') and c.get('nep')}
    dropped = referenced - carried
    if dropped:
        raise ValueError(f'Comparison rows dropped: {sorted(dropped)[:5]}')

    senate_action_counts = Counter(c['actions']['house_senate'] for c in ordered
                                   if c['actions']['house_senate'])
    totals = {
        'nep': {'rows': len(nep_by_id), 'amount_php': sum(p['amount_php'] for p in nep_by_id.values())},
        'house': {'rows': len(leaf_chains), 'amount_php': sum(l['amount_php'] for l in leaves.values())},
        'controls': {'rows': len(control_chains),
                     'amount_php': sum(c['house']['amount_php'] for c in control_chains)},
        'senate': {'rows': len(senate_rows), 'amount_php': sv_total, 'gab_php': gab_total,
                   'matched_gab_php': matched_gab, 'matched_sv_php': matched_sv},
        'counts': {
            'senate_insertion': sum(1 for c in ordered if c.get('senate') and not c.get('house')),
            'cuts': senate_action_counts['Cut to zero'],
            'nep_only': sum(1 for c in ordered if c.get('nep') and not c.get('house')),
            'senate_only': sum(1 for c in ordered if c.get('senate') and not c.get('house')),
            'house_rows': len(leaf_chains),
            'house_projects_without_senate': sum(not c.get('senate') for c in leaf_chains),
            'house_controls_without_senate': sum(not c.get('senate') for c in control_chains),
        },
        'actions': {'nep_house': Counter(c['actions']['nep_house'] for c in ordered
                                         if c['actions']['nep_house']),
                    'house_senate': senate_action_counts},
        'flow_note': (f"{senate_action_counts['Cut to zero']:,} Annex A-4 rows cut to zero · "
                      f"A-4 covers {len(senate_rows):,} of {len(leaf_chains):,} House rows; "
                      'absence means the Senate left the House amount as-is.'),
    }
    review_totals = {
        'hgab_rows': len(hgab), 'bridged': bridge['unique'],
        'ambiguous': bridge['ambiguous'], 'missing': bridge['missing'],
        'unbridged_hgab_rows': bridge['hgab_rows_unbridged'],
        'flag_entries': len(flags),
        'chains_with_flags': sum(1 for c in ordered if c.get('flags')),
    }

    inputs = [NEP, COMPARISON, TREE, ANNEX, RAW_ANNEX, HGAB, FLAGS]
    return {
        'totals': totals,
        'budget_controls': budget_controls,
        'review_totals': review_totals,
        'flag_catalog': flag_catalog,
        'annex_note': annex['note'],
        'sources': {
            'nep': {'source_pdf': nep_source['source_pdf'], 'scope': nep_source['scope']},
            'house': {'source_pdf': 'HB_BUDGET_3rd_reading/3- HB 10858 FOR 3RD READING VOL I-C .pdf',
                      'scope': tree['scope']},
            'senate': {'label': annex['label'], 'inputs': annex['inputs']},
        },
        'chains': ordered,
        'inputs': {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in inputs},
    }


if __name__ == '__main__':
    bundle = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, ensure_ascii=False, separators=(',', ':')) + '\n',
                   encoding='utf-8')
    summary = {'chains': len(bundle['chains']), 'review': bundle['review_totals'],
               'actions': {k: dict(v) for k, v in bundle['totals']['actions'].items()}}
    print(json.dumps(summary, indent=2))
