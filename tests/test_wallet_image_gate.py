#!/usr/bin/env python3
"""The final wallet gate requires an executed marker AND the producer's exit."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT/'build_files/verify_wallet_preference.sh'

class Wiring(unittest.TestCase):
    def test_both_final_compositions_run_the_same_installed_proof(self):
        for container, builder in [('Containerfile','build.sh'),('Containerfile.arm','build-arm.sh')]:
            self.assertIn('COPY tests/test_wallet_preference.py /test_wallet_preference.py', (ROOT/container).read_text())
            source = (ROOT/'build_files'/builder).read_text()
            call = 'bash /ctx/verify_wallet_preference.sh'
            self.assertEqual(source.count(call), 1)
            self.assertGreater(source.index(call), source.rfind('bash /ctx/verify_settings_modules.sh'))

class ExecutedGate(unittest.TestCase):
    @unittest.skipUnless(shutil.which('bwrap'), 'private namespace unavailable on source runner')
    def test_empty_skipped_missing_and_failed_after_marker_cannot_pass(self):
        with tempfile.TemporaryDirectory(prefix='moos-wallet-gate-') as temp:
            folder=Path(temp)
            fake=folder/'python3'
            fake.write_text('''#!/usr/bin/bash
[ "$*" = '-B -s /ctx/test_wallet_preference.py --installed' ] || exit 44
case "$MOOS_GATE_TEST" in
 success) echo MOOS_IMAGE_WALLET_LIFECYCLE_PASS ;;
 empty) exit 0 ;;
 skipped) echo 'OK (skipped=12)' ;;
 failed) echo MOOS_IMAGE_WALLET_LIFECYCLE_PASS; exit 42 ;;
esac
''')
            fake.chmod(0o700)
            driver=folder/'driver';driver.write_text('fixture\n')
            args=['bwrap','--die-with-parent','--ro-bind','/usr','/usr','--ro-bind','/lib','/lib',
                  '--symlink','usr/bin','/bin','--dev','/dev','--tmpfs','/tmp','--dir','/ctx',
                  '--ro-bind',str(fake),str(Path('/usr/bin/python3').resolve()),'--ro-bind',str(GATE),'/gate']
            if Path('/lib64').exists():args+=['--ro-bind','/lib64','/lib64']
            probe=subprocess.run(args+['--','/usr/bin/true'],capture_output=True,text=True,timeout=10)
            if probe.returncode:
                if Path('/usr/lib/moos/edition').is_file():self.fail(probe.stderr)
                self.skipTest('source runner refuses private namespaces: '+probe.stderr[:120])
            for mode,expected in [('success',0),('empty',1),('skipped',1),('failed',42),('missing',1)]:
                with self.subTest(mode=mode):
                    binding=[] if mode=='missing' else ['--ro-bind',str(driver),'/ctx/test_wallet_preference.py']
                    result=subprocess.run(args+binding+['--','/usr/bin/bash','/gate'],env=os.environ|{'MOOS_GATE_TEST':mode},stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=10)
                    self.assertEqual(result.returncode,expected,result.stdout+result.stderr)

if __name__=='__main__':unittest.main(verbosity=2)
