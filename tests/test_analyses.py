"""Check the generated page against the scientific sources and download bundle."""
import csv
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest
from urllib.parse import unquote, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'data/analyses'


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.ids, self.references, self.inventory, self.figures = [], [], [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if 'id' in data:
            self.ids.append(data['id'])
        for name in ['href', 'src']:
            if data.get(name):
                self.references.append(data[name])
        if tag == 'tr' and 'data-files' in data:
            self.inventory.append(data)
        if tag == 'article' and 'data-category' in data:
            self.figures.append(data)


class AnalysesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads((PUBLIC / 'summary.json').read_text())
        cls.manifest = json.loads((PUBLIC / 'build-manifest.json').read_text())
        cls.html = (ROOT / 'analyses.html').read_text()
        cls.page = Page(cls.html)

    def test_headlines_match_the_archive_census(self):
        with (ROOT / 'analysis/database_in_numbers/tables/plot_datasets.csv').open() as stream:
            source = list(csv.DictReader(stream))
        self.assertEqual(len(source), self.summary['searches'])
        self.assertFalse(self.page.inventory)
        self.assertEqual(sum(int(float(row['structure_count'])) for row in source), self.summary['archived_structure_files'])
        self.assertEqual(sum(int(float(row['energy_model_count'])) for row in source), self.summary['model_archives'])

    def test_scientific_populations_and_approximate_reference_scope_are_explicit(self):
        self.assertEqual(self.summary['coordinate_verified_single_component_systems'], 189)
        self.assertEqual(self.summary['coordinate_verified_multicomponent_systems'], 44)
        self.assertEqual(self.summary['molecular_systems'], 234)
        self.assertIn('44,403 OMC25 training molecular records', self.html)
        self.assertIn('approximate histogram recoveries', self.html)
        self.assertEqual(len(self.page.figures), len(self.summary['figures']))

    def test_marked_sections_and_figure_resources_are_removed(self):
        self.assertEqual({figure['id'] for figure in self.summary['figures']}, {
            'chemical-content', 'density', 'molecular-map', 'multicomponent', 'software'})
        for ident in ['figure-map-diagnostics', 'figure-overview-wide', 'figure-overview-portrait',
                      'molecular-map', 'searches', 'data-methods', 'methods', 'inventory-table', 'download-search']:
            self.assertNotIn(ident, self.page.ids)
        for text in ['All molecular populations, quartiles, means and source-mass statistics',
                     'All available and shared-window density statistics, including multicomponent systems',
                     'Earlier exports', 'Sketch-map diagnostics', 'Database in numbers: wide overview',
                     'Database in numbers: portrait overview']:
            self.assertNotIn(text, self.html)
        self.assertIn('figure-molecular-map', self.page.ids)
        self.assertNotIn('map--optimization_runs.csv', self.html)
        self.assertNotIn('database--annual_counts.csv', self.html)
        self.assertNotIn('database--structure_count_ranking.csv', self.html)

    def test_page_has_unique_ids_and_resolving_local_links(self):
        self.assertEqual(len(self.page.ids), len(set(self.page.ids)))
        for ref in self.page.references:
            url = urlsplit(ref)
            if url.scheme or url.netloc:
                continue
            if url.path:
                path = ROOT / unquote(url.path)
                self.assertTrue(path.exists(), ref)
            elif url.fragment:
                self.assertIn(unquote(url.fragment), self.page.ids, ref)
        navigator = (ROOT / 'index.html').read_text()
        self.assertIn('id="dataset-analyses-link" href="analyses.html"', navigator)
        header = navigator.split('<nav class="cposs-toplinks"', 1)[1].split('</nav>', 1)[0]
        self.assertEqual(header.count('class="btn btn-sm btn-outline-light"'), 4)

    def test_retained_figure_tables_preserve_scientific_values(self):
        expected = {
            'analysis/cposs_omc25_comparison/tables/summary_statistics.csv',
            'analysis/cposs_omc25_comparison/density/tables/density_statistics.csv',
            'analysis/molecular_sketchmap/tables/dataset_embedding.csv',
            'analysis/cposs_omc25_comparison/tables/cposs_multicomponent_formula_units.csv',
            'analysis/database_in_numbers/workbook_crosscheck/proposed_panel_c_counts.csv',
        }
        self.assertEqual({item['source'] for item in self.summary['downloads']}, expected)
        self.assertEqual({item['path'] for item in self.summary['downloads']},
                         {figure['data'] for figure in self.summary['figures']})
        for item in self.summary['downloads']:
            raw = (ROOT / item['path']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256'])
            with (ROOT / item['source']).open(newline='') as source, (ROOT / item['path']).open(newline='') as public:
                a, b = list(csv.DictReader(source)), list(csv.DictReader(public))
            self.assertEqual(len(a), item['rows'])
            self.assertEqual(len(a), len(b))
            for original, exported in zip(a, b):
                for key, value in original.items():
                    if any(prefix in (value or '') for prefix in ['/Users/', '/tmp/', '/private/tmp/']):
                        self.assertIn('Local source location omitted', exported[key])
                    else:
                        self.assertEqual(value or '', exported[key], (item['id'], key))

    def test_bundle_has_figures_and_all_tables_without_private_sources(self):
        with zipfile.ZipFile(PUBLIC / 'cposs_figures_and_statistics.zip') as bundle:
            names = set(bundle.namelist())
            expected = {'data/analyses/summary.json', 'data/analyses/build-manifest.json', 'data/analyses/README.md'}
            for item in self.summary['downloads']:
                self.assertIn(item['path'], names)
                expected.add(item['path'])
            for figure in self.summary['figures']:
                for key in ['image', 'pdf', 'caption']:
                    if figure[key]:
                        self.assertIn(figure[key], names)
                        expected.add(figure[key])
            self.assertEqual(names, expected)
            self.assertFalse(any(name.lower().endswith(('.xlsx', '.xls')) or '/sources/' in name for name in names))
            self.assertTrue(all(not name.startswith('/') and '..' not in Path(name).parts for name in names))
        for source, checksum in self.manifest['source_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT / source).read_bytes()).hexdigest(), checksum, source)


if __name__ == '__main__':
    unittest.main()
