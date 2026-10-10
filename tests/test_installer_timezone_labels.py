#!/usr/bin/env python3
"""Selectable zones must keep bilingual labels, valid data and image coverage."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('timezone_gate', ROOT/'build_files/verify_installer_timezones.py')
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
CATALOG = ROOT/'system_files/usr/share/moos/installer-timezones.json'
TAB = Path('/usr/share/zoneinfo/zone1970.tab')


class TimezoneLabels(unittest.TestCase):
    def test_current_selectable_zones_are_covered(self):
        self.assertGreater(gate.validate(CATALOG, TAB), 300)

    def test_missing_zone_language_and_city_are_rejected(self):
        for kind in ('missing-zone', 'missing-language', 'lost-arabic-city', 'invalid-id'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                data = json.loads(CATALOG.read_text())
                if kind == 'missing-zone': del data['zones']['Europe/Berlin']
                elif kind == 'missing-language': del data['zones']['Europe/Berlin']['ar']
                elif kind == 'lost-arabic-city': data['zones']['Europe/Berlin']['ar'] = 'Berlin'
                else: data['zones']['../escape'] = {'ar':'غير صالح', 'en':'invalid'}
                path = Path(directory)/'catalog.json'; path.write_text(json.dumps(data))
                with self.assertRaises(ValueError): gate.validate(path, TAB)

    def test_new_vendor_zone_requires_reviewed_data(self):
        with tempfile.TemporaryDirectory() as directory:
            tab = Path(directory)/'zone1970.tab'
            tab.write_text(TAB.read_text() + '\nZZ\t+0000+00000\tExample/New_City\n')
            with self.assertRaisesRegex(ValueError, 'without reviewed labels'):
                gate.validate(CATALOG, tab)

    def test_both_images_run_actual_native_search_gate(self):
        for filename in ('build.sh', 'build-arm.sh'):
            code = (ROOT/'build_files'/filename).read_text()
            self.assertIn('python3 /ctx/verify_installer_timezones.py --native', code)
            self.assertLess(code.index('verify_installer_timezones.py'), code.index('finalize_image_state.py'))


if __name__ == '__main__': unittest.main(verbosity=2)
