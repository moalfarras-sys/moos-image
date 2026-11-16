#!/usr/bin/env python3
"""Exercise the real packaged ELF/signature and bounded package admission."""
import importlib.util
import lzma
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'build_files/smocf05'
sys.path.insert(0, str(HERE))
import admit
import module

PACKAGE = HERE / admit.MANIFEST['rpm_name']


class PackageAdmission(unittest.TestCase):
    def test_actual_rpm_payload_and_production_signature(self):
        result = admit.package_check(PACKAGE)
        self.assertIn('acpi*:SMOCF05:*', result['alias'])
        self.assertEqual(result['vermagic'], module.VERMAGIC)

    def test_changed_and_linked_rpm_refused_before_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'changed.rpm'
            data = bytearray(PACKAGE.read_bytes())
            data[-20] ^= 1
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'RPM bytes drift'):
                admit.package_check(path)
            link = Path(temporary) / 'linked.rpm'
            link.symlink_to(PACKAGE)
            with self.assertRaisesRegex(ValueError, 'linked'):
                admit.package_check(link)

    def test_actual_module_content_tamper_refused_by_crypto(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with tempfile.TemporaryFile() as stream:
                subprocess.run(['rpm2cpio', str(PACKAGE)], stdout=stream, check=True)
                stream.seek(0)
                subprocess.run(['cpio', '-idm', '--quiet', '--no-absolute-filenames',
                                '--no-preserve-owner'], stdin=stream, cwd=root, check=True)
            data = bytearray(module.unpack(root / module.RELATIVE))
            module.verify_signature(bytes(data), HERE / 'module.pem')
            data[128] ^= 1
            with self.assertRaises(subprocess.CalledProcessError):
                module.verify_signature(bytes(data), HERE / 'module.pem')

    def test_compression_bomb_and_trailing_stream_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'module.xz'
            for data in (lzma.compress(b'\0' * (module.LIMIT + 1)),
                         lzma.compress(b'ELF') + b'trailing'):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    module.unpack(path)

    def test_host_compose_has_no_authorization(self):
        with self.assertRaisesRegex(ValueError, 'restricted to an explicit compose container'):
            admit.compose(PACKAGE)


if __name__ == '__main__':
    unittest.main()
