"""Consolidated NIA dataset: one Senate workbook row, complementary locations."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'analysis-nia' / 'data'

spec = importlib.util.spec_from_file_location(
    'nia_consolidated', ROOT / 'analysis-nia/build_nia_consolidated.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ConsolidatedDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = builder.build()
        cls.projects = cls.dataset['projects']
        cls.by_id = {p['id']: p for p in cls.projects}

    def test_one_row_per_senate_workbook_line(self):
        self.assertEqual(len(self.projects), 937)
        self.assertEqual(len(self.by_id), 937)
        self.assertEqual(self.dataset['unit'], 'senate_workbook_row')

    def test_money_reconciles_once_on_projects(self):
        nep = [p for p in self.projects if (p.get('nep_amount') or 0) > 0]
        house = [p for p in self.projects if (p.get('hgab_amount') or 0) > 0]
        self.assertEqual(len(nep), 791)
        self.assertEqual(sum(p['nep_amount'] for p in nep), 17_598_181_000)
        self.assertEqual(len(house), 828)
        self.assertEqual(sum(p['hgab_amount'] for p in house), 17_999_305_000)

    def test_coordinate_workbook_matches_and_review_rows_are_disjoint(self):
        source = self.dataset['meta']['coordinate_workbook']
        attached = {
            entry['row']: entry for project in self.projects
            if (entry := project['locations']['coordinate_workbook'])
        }
        review = {entry['row']: entry['reason'] for entry in source['review_rows']}
        self.assertEqual(len(attached), source['matched_rows'])
        self.assertEqual(len(attached), 799)
        self.assertTrue(attached.keys().isdisjoint(review))
        # Row 785 is a submission-only row (reallocation recipient, not a
        # Senate workbook project) — it stays held here and joins the web
        # export's reallocation chain instead.
        self.assertEqual(review, {
            65: 'geography_differs', 67: 'geography_differs', 69: 'geography_differs',
            71: 'geography_differs', 73: 'geography_differs',
            785: 'no_printed_project_title',
            1803: 'repeated_project_key',
        })
        # Inserted rows (no printed title) attach through the revised title
        # and submission amount; documented reassignments keep a geography note.
        for row in (1616, 1618, 1671):
            entry = attached[row]
            self.assertEqual(entry['match_method'], 'revised_title_and_submission_amount')
            note = entry['geography_review']
            self.assertEqual(note['october_region'], 'Region 13')
            self.assertIn('Region 2', note['coordinate_row_region'])
        self.assertEqual(attached[279]['row'], 279)
        self.assertTrue(attached[279]['map_url'].startswith('https://'))
        self.assertTrue(any(
            'outside_philippines_screening_bounds' in point['issues']
            for point in attached[384]['coordinates']['points']
        ))

    def test_coordinate_workbook_retains_each_exact_pair(self):
        entries = [project['locations']['coordinate_workbook'] for project in self.projects]
        for entry in filter(None, entries):
            for point in entry['coordinates']['points']:
                if point['latitude'] is not None and point['longitude'] is not None:
                    self.assertIn(point['coordinate_pair_text'], entry['coordinate_text'])

        entry = next(entry for entry in filter(None, entries) if any(
            '…' in point['source_fragment'] and point.get('coordinate_pair_text')
            for point in entry['coordinates']['points']
        ))
        points = [point for point in entry['coordinates']['points']
                  if '…' in point['source_fragment'] and point.get('coordinate_pair_text')]
        self.assertGreater(len({point['coordinate_pair_text'] for point in points}), 1)
        self.assertTrue(all('…' not in point['coordinate_pair_text'] for point in points))

    def test_basiao_endpoint_dashes_preserve_degrees_and_all_eight_sites(self):
        from coordinate_parse import endpoint_observations

        entry = next(project['locations']['coordinate_workbook'] for project in self.projects
                     if (project['locations']['coordinate_workbook'] or {}).get('row') == 1347)
        points = entry['coordinates']['points']
        self.assertEqual(len(points), 8)
        self.assertEqual([point['role'] for point in points], ['start', 'end'] * 4)
        self.assertTrue(all(11.26 < point['latitude'] < 11.28 for point in points))
        self.assertEqual(points[2]['section_label'], 'Lateral A')
        self.assertAlmostEqual(points[2]['latitude'], 11.2721527778)
        self.assertAlmostEqual(points[2]['longitude'], 125.1688194444)
        self.assertTrue(points[2]['coordinate_pair_text'].startswith('11° 16'))
        self.assertEqual(endpoint_observations('Start: -11.2, 125.1')[0]['latitude'], -11.2)
        self.assertEqual(endpoint_observations('Start -11.2, 125.1')[0]['latitude'], -11.2)

    def test_lubang_numbered_sites_keep_latitude_degrees(self):
        entry = next(project['locations']['coordinate_workbook'] for project in self.projects
                     if (project['locations']['coordinate_workbook'] or {}).get('row') == 2002)
        points = entry['coordinates']['points']
        self.assertEqual(len(points), 5)
        self.assertTrue(all(13.8 < point['latitude'] < 13.9 for point in points))
        self.assertAlmostEqual(points[-1]['latitude'], 13.83875)
        self.assertAlmostEqual(points[-1]['longitude'], 120.1368111111)
        self.assertTrue(points[-1]['coordinate_pair_text'].startswith('13°50'))

    def test_matching_splits_are_flagged_not_duplicated(self):
        splits = [p for p in self.projects if p['matching']['split']]
        self.assertEqual(len(splits), 77)
        self.assertEqual(self.dataset['meta']['counts']['matching_split'], 77)
        for p in splits:
            self.assertIn('matching_split', p['flags'])
            self.assertEqual(len(p['comparison_ids']), 2)
            self.assertIn(p['matching']['split_reason'],
                          ('reworded_printing', 'repeated_title'))

    def test_location_coverage_partitions_projects(self):
        counts = self.dataset['meta']['counts']
        coverage = counts['coverage']
        self.assertEqual(sum(coverage.values()), 937)
        self.assertEqual(counts['with_title_gps'],
                         coverage.get('title_gps', 0) + coverage.get('title_gps+psgc', 0))
        self.assertEqual(counts['with_psgc_centroid'],
                         coverage.get('psgc', 0) + coverage.get('title_gps+psgc', 0))
        self.assertGreaterEqual(counts['with_title_gps'], 400)
        self.assertGreaterEqual(counts['with_psgc_centroid'], 700)

    def test_title_gps_points_do_not_inflate_project_count(self):
        maniana = next(p for p in self.projects if 'Maniana' in (p.get('submission_label') or ''))
        self.assertEqual(maniana['locations']['title_gps']['point_count'], 6)
        self.assertIn('multi_site_title_gps', maniana['flags'])
        # One project id, one House amount — six sites share it.
        self.assertEqual(maniana['hgab_amount'], 60_000_000)

    def test_chainage_php_per_m_is_allocation_proxy(self):
        # PRIS-SDC PH2: ₱2,450,000 over Sta 0+000 → 0+200 (200 m).
        row = self.by_id['sen:r73']
        chainage = row['locations']['chainage']
        self.assertEqual(chainage['length_m'], 200)
        self.assertEqual(chainage['php_per_m'], 12_250.0)
        self.assertEqual(chainage['php_per_m_basis'], 'hgab')
        self.assertEqual(chainage['nep_php_per_m'], 12_250.0)
        self.assertEqual(chainage['hgab_php_per_m'], 12_250.0)
        counts = self.dataset['meta']['counts']
        self.assertGreaterEqual(counts['with_chainage_length'], 400)
        self.assertEqual(counts['with_php_per_m'], counts['with_chainage_length'])
        # Point-only stations have no length → no rate.
        point_only = next(
            p for p in self.projects
            if (p['locations'].get('chainage') or {}).get('spans')
            and (p['locations']['chainage'].get('length_m') in (None, 0))
            and all(s.get('point') for s in p['locations']['chainage']['spans']))
        self.assertIsNone(point_only['locations']['chainage'].get('php_per_m'))

    def test_written_outputs_match_builder(self):
        if not builder.OUT_JSON.is_file():
            self.skipTest('nia_consolidated.json not written yet')
        written = json.loads(builder.OUT_JSON.read_text())
        self.assertEqual(written['meta']['counts'], self.dataset['meta']['counts'])
        self.assertEqual(len(written['projects']), 937)


if __name__ == '__main__':
    unittest.main()
