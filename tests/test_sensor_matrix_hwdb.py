#!/usr/bin/env python3
"""Native compiled lookup for the actual sanitized udev V3 modalias."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'system_files/usr/lib/udev/hwdb.d/61-moos-v3-sensor.hwdb'
MATRIX = 'ACCEL_MOUNT_MATRIX=-1, 0, 0; 0, -1, 0; 0, 0, 1'


def key(vendor='MicroComputer_HK_TechLimited', product='V3', sensor='SMOCF05'):
    return f'sensor:modalias:acpi:{sensor}:{sensor}::dmi:bvnTest:svn{vendor}:pn{product}:pvrTest:'


class SensorMatrix(unittest.TestCase):
    def test_source_keeps_one_precise_alias_and_upstream_matrix(self):
        lines = [line for line in SOURCE.read_text().splitlines() if line and not line.startswith('#')]
        self.assertEqual(lines, [
            'sensor:modalias:acpi:SMOCF05:*:dmi:*:svnMicroComputer_HK_TechLimited:pnV3:*',
            ' ' + MATRIX])

    def test_native_compile_and_exact_lookup_negatives(self):
        tool = shutil.which('systemd-hwdb')
        if not tool:
            self.skipTest('native systemd-hwdb unavailable; final image lookup remains required')
        with tempfile.TemporaryDirectory(prefix='moos-sensor-hwdb-') as name:
            root = Path(name)
            folder = root / 'usr/lib/udev/hwdb.d'
            folder.mkdir(parents=True)
            shutil.copyfile(SOURCE, folder / SOURCE.name)
            subprocess.run([tool, '--strict', '--usr', '--root=' + name, 'update'],
                           check=True, capture_output=True, timeout=15)
            for query, expected in ((key(), MATRIX), (key(product='V3SE'), ''),
                                    (key(product='V30'), ''), (key(vendor='Other'), ''),
                                    (key(sensor='SMOCF00'), ''), (key(vendor='MicroComputer(HK)TechLimited'), '')):
                with self.subTest(query=query):
                    result = subprocess.run([tool, '--root=' + name, 'query', query],
                                            capture_output=True, text=True, timeout=10)
                    self.assertIn(result.returncode, (0, 1), result)
                    self.assertEqual(result.stdout.strip(), expected)

    def test_actual_final_compiler_refuses_missing_alias(self):
        bwrap = shutil.which('bwrap')
        vendor = Path('/usr/lib/udev/hwdb.d')
        if not bwrap or not shutil.which('systemd-hwdb') or not vendor.is_dir():
            self.skipTest('native namespace/hwdb sources unavailable; image compiler remains mandatory')
        with tempfile.TemporaryDirectory(prefix='moos-compiler-hwdb-') as name:
            udev = Path(name) / 'udev'
            sources = udev / 'hwdb.d'
            sources.mkdir(parents=True)
            for source in vendor.glob('*.hwdb'):
                if source.name != SOURCE.name:
                    shutil.copyfile(source, sources / source.name)
            command = [bwrap, '--unshare-user', '--uid', '0', '--gid', '0',
                       '--ro-bind', '/', '/', '--dev', '/dev', '--proc', '/proc',
                       '--unshare-all', '--die-with-parent', '--new-session',
                       '--tmpfs', '/tmp', '--tmpfs', '/run', '--tmpfs', '/etc/udev',
                       '--bind', str(udev), '/usr/lib/udev', '--', 'bash',
                       str(ROOT / 'build_files/compile_system_hwdb.sh')]
            old = subprocess.run(command, capture_output=True, text=True, timeout=30)
            if old.stderr.startswith('bwrap:'):
                self.skipTest('native private namespace unavailable: ' + old.stderr.splitlines()[0])
            self.assertEqual(old.returncode, 1, old)
            self.assertIn('native V3 sensor matrix lookup is missing or changed', old.stderr)
            shutil.copyfile(SOURCE, sources / SOURCE.name)
            fixed = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(fixed.returncode, 0, fixed)
            self.assertTrue((udev / 'hwdb.bin').is_file())
            self.assertIn('HWDB OK:', fixed.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
