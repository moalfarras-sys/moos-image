#!/usr/bin/env python3
"""Boot rebuild must reject drift/tampering before any package transaction."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('plymouth_rpms', ROOT / 'build_files/plymouth_rpms.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PackageBoundaries(unittest.TestCase):
    def attempt(self, *, base=None, digest=None, filename='core.rpm', owned=None, manifest_change=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'core.rpm').write_bytes(b'private fixture')
            manifest = dict(schema=1, arch='x86_64', base=module.BASE,
                            fixed=module.FIXED, source_sha256=module.SOURCE,
                            packages=[dict(name='plymouth-core-libs', file=filename,
                                           arch='x86_64', sha256=digest or module.sha(root/'core.rpm'))])
            if manifest_change: manifest.update(manifest_change)
            (root / 'manifest.json').write_text(json.dumps(manifest))
            def command(argv):
                if argv[1] == '--eval': return 'x86_64'
                if argv[1] == '-qa': return owned or 'plymouth-core-libs'
                if argv[1] == '-q': return base or module.BASE
                self.fail('unexpected external command')
            with patch.object(module, 'command', side_effect=command), \
                 patch.object(module, 'metadata', return_value=['plymouth-core-libs', module.FIXED, 'x86_64']), \
                 patch.object(module.subprocess, 'run') as mutation:
                with self.assertRaises(AssertionError): module.install(root)
                mutation.assert_not_called()

    def test_later_upstream_is_never_downgraded(self):
        self.attempt(base='26.0-1.fc45')
    def test_tampered_payload_is_not_installed(self):
        self.attempt(digest='0'*64)
    def test_package_path_cannot_escape_manifest(self):
        self.attempt(filename='../core.rpm')
    def test_missing_owned_package_blocks_whole_transaction(self):
        self.attempt(owned='plymouth-core-libs\nplymouth-plugin-script')
    def test_unreviewed_source_is_not_accepted(self):
        self.attempt(manifest_change={'source_sha256': '0'*64})
    def test_other_architecture_is_not_accepted(self):
        self.attempt(manifest_change={'arch': 'aarch64'})

if __name__ == '__main__': unittest.main(verbosity=2)
