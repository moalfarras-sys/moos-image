#!/usr/bin/env python3
"""Final native gates require an executed marker AND the producer's exit."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROOFS = [
    ('verify_wallet_preference.sh', 'test_wallet_preference.py', 'MOOS_IMAGE_WALLET_LIFECYCLE_PASS'),
    ('verify_flatpak_transaction.sh', 'test_flatpak_transaction_signals.py', 'MOOS_IMAGE_FLATPAK_TRANSACTION_PASS'),
]

class Wiring(unittest.TestCase):
    def test_both_final_compositions_run_the_same_installed_proof(self):
        for container, builder in [('Containerfile','build.sh'),('Containerfile.arm','build-arm.sh')]:
            for gate, driver, marker in PROOFS:
                with self.subTest(container=container, gate=gate):
                    self.assertIn(f'COPY tests/{driver} /{driver}', (ROOT/container).read_text())
                    source = (ROOT/'build_files'/builder).read_text()
                    call = 'bash /ctx/'+gate
                    self.assertEqual(source.count(call), 1)
                    self.assertGreater(source.index(call), source.rfind('bash /ctx/verify_settings_modules.sh'))

class ExecutedGate(unittest.TestCase):
    @unittest.skipUnless(shutil.which('bwrap'), 'private namespace unavailable on source runner')
    def test_empty_skipped_missing_and_failed_after_marker_cannot_pass(self):
        for gate, driver, marker in PROOFS:
            with self.subTest(gate=gate):
                self.check_gate(gate, driver, marker)

    def check_gate(self, gate, driver_name, marker):
        with tempfile.TemporaryDirectory(prefix='moos-wallet-gate-') as temp:
            folder=Path(temp)
            fake=folder/'python3'
            fake.write_text('''#!/usr/bin/bash
[ "$*" = '-B -s /ctx/DRIVER --installed' ] || exit 44
case "$MOOS_GATE_TEST" in
 success) echo MARKER ;;
 empty) exit 0 ;;
 skipped) echo 'OK (skipped=12)' ;;
 failed) echo MARKER; exit 42 ;;
esac
'''.replace('DRIVER', driver_name).replace('MARKER', marker))
            fake.chmod(0o700)
            driver=folder/'driver';driver.write_text('fixture\n')
            args=['bwrap','--die-with-parent','--ro-bind','/usr','/usr','--ro-bind','/lib','/lib',
                  '--symlink','usr/bin','/bin','--dev','/dev','--tmpfs','/tmp','--dir','/ctx',
                  '--ro-bind',str(fake),str(Path('/usr/bin/python3').resolve()),'--ro-bind',str(ROOT/'build_files'/gate),'/gate']
            if Path('/lib64').exists():args+=['--ro-bind','/lib64','/lib64']
            probe=subprocess.run(args+['--','/usr/bin/true'],capture_output=True,text=True,timeout=10)
            if probe.returncode:
                if Path('/usr/lib/moos/edition').is_file():self.fail(probe.stderr)
                self.skipTest('source runner refuses private namespaces: '+probe.stderr[:120])
            for mode,expected in [('success',0),('empty',1),('skipped',1),('failed',42),('missing',1)]:
                with self.subTest(mode=mode):
                    binding=[] if mode=='missing' else ['--ro-bind',str(driver),'/ctx/'+driver_name]
                    result=subprocess.run(args+binding+['--','/usr/bin/bash','/gate'],env=os.environ|{'MOOS_GATE_TEST':mode},stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=10)
                    self.assertEqual(result.returncode,expected,result.stdout+result.stderr)

if __name__=='__main__':unittest.main(verbosity=2)
