#!/usr/bin/env python3
"""Exercise the actual staging path and cross-edition delivery declarations."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('community_stage',ROOT/'community/stage_client.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class Packaging(unittest.TestCase):
    def test_real_python_entrypoint_stages_without_shadowing_standard_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'community'
            result=subprocess.run([sys.executable,'-B',str(ROOT/'community/stage_client.py'),
                                   str(ROOT/'community'),str(target)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual({p.name for p in target.iterdir()},set(module.RUNTIME))

    def test_real_stage_contains_exact_client_bytes_without_server_or_private_files(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'community'
            module.stage(ROOT/'community',target)
            self.assertEqual({p.name for p in target.iterdir()},set(module.RUNTIME))
            for name in module.RUNTIME:
                self.assertEqual((target/name).read_bytes(),(ROOT/'community'/name).read_bytes())
                self.assertEqual((target/name).stat().st_mode&0o777,0o644)
            with self.assertRaises(ValueError):module.stage(ROOT/'community',target)

    def test_missing_native_source_fails_before_any_partial_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source';source.mkdir()
            for name in module.RUNTIME:
                if name!='main.qml':(source/name).write_text('fixture')
            target=Path(directory)/'out'
            with self.assertRaises(ValueError):module.stage(source,target)
            self.assertFalse(target.exists())

    def test_every_edition_stages_the_same_source_and_runs_actual_launcher_gate(self):
        for file in ('Containerfile','Containerfile.arm'):
            text=(ROOT/file).read_text()
            self.assertIn('FROM base AS community-build',text)
            self.assertIn('python3 -B /src/community/stage_client.py /src/community /out/community',text)
            self.assertIn('COPY --from=community-build /out/community/ /usr/lib/moos-community/community/',text)
        for file in ('build_files/build.sh','build_files/build-arm.sh'):
            self.assertIn('python3 /ctx/verify_community_client.py',(ROOT/file).read_text())
        launcher=(ROOT/'system_files/usr/bin/moos-community').read_text()
        self.assertIn('exec /usr/bin/python3 -s -m community.client',launcher)
        self.assertIn('QML_DISABLE_DISK_CACHE=1',launcher)
        self.assertIn('org.moos.community',(ROOT/'community/client.py').read_text())
        self.assertIn('Exec=/usr/bin/moos-community',(ROOT/'system_files/usr/share/applications/org.moos.community.desktop').read_text())
        gate=(ROOT/'build_files/verify_community_client.py').read_text()
        self.assertIn("'dbus-run-session'",gate);self.assertIn("'--capture'",gate)
        self.assertIn("'MOOS_COMMUNITY_UI_READY' not in output",gate)
        self.assertNotIn('except',gate)


if __name__=='__main__':unittest.main()
