"""Smoke tests for the [POW FOR REVIEW] availability artifact."""
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.dirname(HERE)
POW = os.path.join(ANALYSIS, 'data', 'program_of_works')


class TestPowReviewAvailability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(POW, 'pow_review_availability.json')) as f:
            cls.ds = json.load(f)

    def test_schema_and_counts(self):
        self.assertEqual(self.ds['schema_version'], 1)
        self.assertTrue(self.ds['source_drive_url'].startswith('https://drive.google.com/'))
        self.assertIn('POW FOR REVIEW', self.ds['source_subfolder'])
        s = self.ds['summary']
        self.assertGreater(s['packages'], 0)
        self.assertGreater(s['total_docs'], 0)
        self.assertEqual(s['total_docs'], s['total_pdfs'] + s['total_images'])
        self.assertEqual(len(self.ds['packages']), s['packages'])
        self.assertEqual(len(self.ds['coverage']), s['senate_projects'])
        self.assertEqual(
            s['senate_projects_with_docs'] + s['senate_projects_unsupported'],
            s['senate_projects'])

    def test_doc_counts_sum_parts(self):
        for p in self.ds['projects']:
            self.assertEqual(p['doc_count'], p['pdf_count'] + p['image_count'], p['senate_id'])
            self.assertGreaterEqual(p['doc_count'], 1)

    def test_supported_rows_carry_packages(self):
        for r in self.ds['coverage']:
            if r['supported']:
                self.assertEqual(r['support'], 'supported')
                self.assertGreaterEqual(r['package_count'], 1)
                self.assertTrue(r['packages'])
            else:
                self.assertEqual(r['package_count'], 0)
                self.assertEqual(r['doc_count'], 0)

    def test_region_rows_cover_packages(self):
        total = sum(r['packages'] for r in self.ds['by_region'])
        self.assertEqual(total, self.ds['summary']['packages'])
        for r in self.ds['by_region']:
            if r.get('senate_projects'):
                self.assertEqual(
                    r['projects_with_docs'] + r['unsupported'], r['senate_projects'],
                    r['region_folder'])

    def test_only_strong_matches_attributed(self):
        by_pid = {p['id']: p for p in self.ds['packages']}
        for r in self.ds['coverage']:
            for pk in r.get('packages', []):
                pkg = by_pid.get(pk['package_id'])
                if pkg:
                    self.assertEqual(pkg['match_strength'], 'strong',
                                     pk['package_id'])

    def test_support_scale_bars(self):
        scale = self.ds['summary']['support_scale']
        self.assertEqual([r['id'] for r in scale], ['pow', 'photos', 'none'])
        self.assertEqual(scale[0]['count'], self.ds['summary']['senate_projects_with_pow'])
        self.assertEqual(scale[1]['count'], self.ds['summary']['senate_projects_with_photos'])
        self.assertEqual(scale[2]['count'], self.ds['summary']['senate_projects_unsupported'])
        self.assertEqual(
            sum(1 for r in self.ds['coverage'] if r.get('has_pow')),
            scale[0]['count'])
        self.assertEqual(
            sum(1 for r in self.ds['coverage'] if r.get('has_photos')),
            scale[1]['count'])

    def test_no_conflicting_amounts_per_row(self):
        """A supported row must not carry strong packages with mutually
        inconsistent parsed amounts (conflict resolution should have
        demoted them)."""
        by_pid = {p['id']: p for p in self.ds['packages']}
        for r in self.ds['coverage']:
            amts = {by_pid.get(pk['package_id'], {}).get('amount_php')
                    for pk in r.get('packages', [])}
            amts.discard(None)
            self.assertLessEqual(len(amts), 1, r['senate_id'])

    def test_calibration_anchors(self):
        """Known package → Senate row identities from the earlier PBC drop
        analysis must still hold in the [FOR REVIEW] drop."""
        want = {
            'AUPAGAN': ('sen:r1456', 300000000),   # LARPIS Aupagan repair PIS
            'BANTOG': ('sen:r1874', 10000000),     # PENRIS Bantog SPIP
            'CONSUELO': ('sen:r740', None),        # Consuelo CIS service road
            'LABANGAN': ('sen:r414', 200000000),   # Labangan RIS repair NIS
        }
        for key, (sid, amt) in want.items():
            hits = [p for p in self.ds['packages']
                    if key in ((p.get('system_guess') or '') + ' ' + p['name']).upper()
                    and p['match_strength'] == 'strong'
                    and (amt is None or p.get('amount_php') == amt)]
            self.assertTrue(hits, f'anchor {key} missing')
            self.assertEqual(hits[0]['best_match']['senate_id'], sid, key)

    def test_amount_veto_blocks_false_pdf_confirm(self):
        """Cabiao (500M) must not PDF-confirm onto PDRIS r549 (200M), and
        Pantingan (200M) must not confirm onto a 20M SPIP row."""
        for p in self.ds['packages']:
            name = p['name'].upper()
            if 'CABIAO' in name:
                bm = p.get('best_match') or {}
                self.assertNotEqual(bm.get('senate_id'), 'sen:r549', 'Cabiao')
                self.assertNotEqual(bm.get('pdf_confirmed'), True, 'Cabiao')
            if 'PANTINGAN' in name:
                bm = p.get('best_match') or {}
                self.assertNotEqual(bm.get('senate_id'), 'sen:r1795', 'Pantingan')
                self.assertNotEqual(bm.get('pdf_confirmed'), True, 'Pantingan')

    def test_allocation_group_folders_are_not_packages(self):
        """"120M - SPIP" / "50M - SPIP" style group folders expand to their
        children instead of forming one big package."""
        names = {p['name'] for p in self.ds['packages']}
        self.assertNotIn('120M - SPIP', names)
        self.assertNotIn('50M - SPIP', names)
        self.assertIn('EGPIPSOLAR-ASINGAN SPIP-5M', names)


if __name__ == '__main__':
    unittest.main()
