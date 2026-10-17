#!/usr/bin/env python3
"""Catalogue availability agrees with the Store and never invents app testing."""
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'system_files/usr/bin/moos-compat-matrix'
CATALOG = ROOT / 'system_files/usr/share/moos/store/catalog.json'
ENGINES = ROOT / 'system_files/usr/share/moos/app-engines.json'


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


generator = load('compat_matrix_test', TOOL)
index = load('compat_index_test', TOOL.with_name('moos-store-index'))


class Availability(unittest.TestCase):
    def setUp(self):
        self.matrix = generator.generate_matrix(CATALOG, ENGINES)
        self.raw = json.loads(CATALOG.read_text())

    def cli(self, *args):
        return subprocess.run([sys.executable, str(TOOL), '--catalog', str(CATALOG),
                               '--engines', str(ENGINES), *args],
                              text=True, capture_output=True, timeout=30)

    def test_every_target_agrees_with_the_store_policy(self):
        for edition, profile in generator.PROFILES.items():
            offered = index.load_catalog(CATALOG, profile['arch'], set(profile['engines']))
            expected = {a['id'] for a in offered['apps']
                        if index.catalog_installable(a, profile['arch'])}
            actual = {a['id'] for a in self.matrix['apps']
                      if a['availability'][edition]['catalog_available']}
            self.assertEqual(actual, expected, edition)

    def test_availability_never_claims_measured_compatibility(self):
        self.assertIn('availability', self.matrix['scope']['en'].lower())
        for app in self.matrix['apps']:
            self.assertEqual(app['application_test'], 'not-assessed')
            for target in app['availability'].values():
                self.assertNotIn('compatible', target)
                self.assertNotIn('supported', target)

    def test_catalogue_versions_and_names(self):
        actual = {a['id']: a for a in self.matrix['apps']}
        for app in self.raw['apps']:
            self.assertEqual(actual[app['id']]['catalog_version'],
                             app.get('install', {}).get('version'))
            self.assertEqual(actual[app['id']]['name'], {k: unicodedata.normalize('NFKC', app[k]) for k in ('en', 'ar')})

    def test_foreign_limits_and_nvidia_only_graphics_are_explicit(self):
        apps = {a['id']: a for a in self.matrix['apps']}
        for app in self.raw['apps']:
            if app.get('engine') not in {'android', 'windows'}:
                continue
            row = apps[app['id']]['availability']
            self.assertFalse(row['moos-cloud']['catalog_available'])
            self.assertFalse(row['moos-arm']['catalog_available'])
            if app.get('engine') == 'android':
                self.assertEqual(row['moos-nvidia']['graphics'], 'software-on-nvidia-only')
                self.assertIn('software', row['moos-nvidia']['note']['en'])
                self.assertNotEqual(row['moos']['graphics'], 'software-on-nvidia-only')

    def test_missing_artifact_blocks_a_declared_architecture(self):
        raw = copy.deepcopy(self.raw)
        app = next(a for a in raw['apps'] if a.get('install', {}).get('kind') == 'appdrop')
        app['arch'] = ['x86_64', 'aarch64']
        app['install']['downloads'].pop('aarch64', None)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'catalog.json'
            path.write_text(json.dumps(raw))
            result = generator.generate_matrix(path, ENGINES)
        row = next(a for a in result['apps'] if a['id'] == app['id'])
        self.assertFalse(row['availability']['moos-arm']['catalog_available'])

    def test_rejected_entries_refuse_an_incomplete_report(self):
        raw = copy.deepcopy(self.raw)
        raw['apps'].append({'id': 'broken', 'source': 'unknown'})
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'catalog.json'
            path.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):
                generator.generate_matrix(path, ENGINES)

    def test_unknown_app_is_an_error(self):
        result = self.cli('--app', 'does-not-exist')
        self.assertEqual(result.returncode, 2)
        self.assertFalse(result.stdout)

    def test_filtered_summary_matches_the_selected_app(self):
        result = self.cli('--app', 'notepad-plus-plus')
        self.assertEqual(result.returncode, 0, result.stderr)
        matrix = json.loads(result.stdout)
        self.assertEqual(len(matrix['apps']), 1)
        self.assertEqual(matrix['summary']['total_apps'], 1)
        self.assertEqual(matrix['summary']['by_edition']['moos'], 1)
        self.assertEqual(matrix['summary']['by_edition']['moos-arm'], 0)

    def test_mac_explanation_comes_from_the_registry(self):
        expected = json.loads(ENGINES.read_text())['unsupported']
        self.assertEqual(self.matrix['unsupported'], [
            {'id': p['id'], 'name': p['name'], 'reason': p['reason']} for p in expected])

    def test_bilingual_report_labels_its_boundary(self):
        for language, expected in (('ar', 'إتاحة'), ('en', 'availability')):
            result = self.cli('--format', 'human', '--language', language,
                              '--app', 'notepad-plus-plus')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(expected, result.stdout.lower())

    def test_explicit_test_root_never_falls_back_to_the_installed_data(self):
        with tempfile.TemporaryDirectory() as td:
            result = subprocess.run([sys.executable, str(TOOL)],
                                    env=dict(os.environ, MOOS_TEST_ROOT=td),
                                    text=True, capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(result.stdout)


if __name__ == '__main__':
    unittest.main()
