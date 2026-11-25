"""Smoke tests for supporting_docs attachment in the NIA web export."""
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
POW = os.path.join(ROOT, 'analysis-nia', 'data', 'program_of_works',
                   'pow_review_availability.json')
BUNDLE = os.path.join(ROOT, 'web', 'public', 'data', 'nia.json')


class TestSupportingDocs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(POW) as f:
            cls.pow = json.load(f)
        with open(BUNDLE) as f:
            cls.chains = json.load(f)['chains']
        cls.supported = {r['senate_id'] for r in cls.pow['coverage'] if r.get('supported')}
        cls.by_wb = {}
        for chain in cls.chains:
            for w in chain.get('workbook', []):
                cls.by_wb[w['id']] = chain

    def test_supported_count_attached(self):
        with_docs = [c for c in self.chains if c.get('supporting_docs')]
        self.assertEqual(len(with_docs), len(self.supported))

    def test_every_supported_row_attached_exactly_once(self):
        seen = {}
        for chain in self.chains:
            docs = chain.get('supporting_docs')
            if not docs:
                continue
            for w in chain.get('workbook', []):
                if w['id'] in self.supported:
                    self.assertNotIn(w['id'], seen, w['id'])
                    seen[w['id']] = chain['id']
        # sen:r480 is supported but has no workbook row anywhere in the
        # bundle; it resolves through the agency-only chain's Excel row.
        self.assertEqual(set(seen) | {'sen:r480'}, self.supported)
        cabtris = next(c for c in self.chains if c['id'] == 'nia_agency_oct10:r149')
        self.assertTrue(cabtris.get('supporting_docs'))

    def test_doc_shape_and_totals(self):
        for chain in self.chains:
            docs = chain.get('supporting_docs')
            if not docs:
                continue
            self.assertEqual(docs['source'], 'POW FOR REVIEW')
            # Older retained snapshots may still contain the private root;
            # public output is sanitized by the Vite build. New exports omit it.
            self.assertTrue(docs['drive_url'].startswith('https://drive.google.com/'))
            self.assertEqual(
                docs['doc_count'], docs['pdf_count'] + docs['image_count'])
            self.assertTrue(docs['packages'])
            self.assertEqual(
                sum(p['doc_count'] for p in docs['packages']), docs['doc_count'])
            self.assertEqual(
                sum(p['pdf_count'] for p in docs['packages']), docs['pdf_count'])
            for p in docs['packages']:
                self.assertTrue(p['path'])
                self.assertGreaterEqual(p['doc_count'], 1)

    def test_package_paths_exist_locally(self):
        root = self.pow['source']
        if not os.path.isdir(root):
            self.skipTest('Local source mirror is not available in this checkout')
        checked = 0
        for chain in self.chains:
            docs = chain.get('supporting_docs')
            if not docs:
                continue
            for p in docs['packages']:
                path = os.path.join(root, p['path'])
                self.assertTrue(os.path.isdir(path), p['path'])
                checked += 1
        self.assertGreater(checked, 0)

    def test_anchors(self):
        aupagan = self.by_wb.get('sen:r1456')
        self.assertIsNotNone(aupagan)
        docs = aupagan['supporting_docs']
        self.assertEqual(docs['doc_count'], 2)
        self.assertEqual(docs['pdf_count'], 1)
        self.assertEqual(docs['image_count'], 1)
        self.assertEqual(docs['packages'][0]['name'], 'REPAIRPIS-LARPIS(AUPAGAN)-300M')

        cabtris = next((c for c in self.chains if c['id'] == 'nia_agency_oct10:r149'), None)
        self.assertIsNotNone(cabtris)
        self.assertEqual(cabtris['supporting_docs']['packages'][0]['name'],
                         'SERVICEROADSNIS-CABTRIS-5M')

    def test_supporting_docs_csv_export(self):
        export = os.path.join(ROOT, 'web', 'public', 'data', 'export', 'nia',
                              'supporting-docs.csv')
        self.assertTrue(os.path.exists(export))
        with open(export, encoding='utf-8') as f:
            lines = f.read().splitlines()
        header = lines[0].split(',')
        self.assertEqual(header[0], 'chain_id')
        self.assertEqual(header[3], 'package_path')
        self.assertEqual(len(lines) - 1,
                         sum(len(c['supporting_docs']['packages'])
                             for c in self.chains if c.get('supporting_docs')))


if __name__ == '__main__':
    unittest.main()
