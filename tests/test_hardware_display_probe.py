#!/usr/bin/env python3
"""Exercise the real adapter in a private root; never write host policy/bus."""
import hashlib
from pathlib import Path
import shlex
import shutil
import subprocess
import unittest

from test_hardware_adapt_zram_availability import machine, SCRIPT

POLICY = Path('etc/systemd/user/plasma-powerdevil.service.d/50-moos-ddc.conf')
STAMP = Path('etc/moos/hardware-adapt.state')
OWNED = ('# Written by moos-hardware-adapt: no DDC/CI display answered on this\n'
         '# machine, and probing for one cost 6.5s of every login. Reversible —\n'
         '# delete this file (or attach a DDC-capable monitor and bump HW_REV).\n'
         '[Service]\nEnvironment=POWERDEVIL_NO_DDCUTIL=1\n')


def private_run(*, output='Invalid display\n', code=0, edid=b'first monitor',
                policy=None, linked=False, prepare_extra=None, script=SCRIPT):
    def prepare(tmp, env):
        connector = tmp / 'sys/class/drm/card1-DP-1'
        connector.mkdir()
        (connector / 'status').write_text('connected\n')
        if isinstance(edid, Path):
            (connector / 'edid').symlink_to(edid)
        elif edid is not None:
            (connector / 'edid').write_bytes(edid)
        if policy is not None:
            target = tmp / 'root' / POLICY
            target.parent.mkdir(parents=True)
            if linked:
                saved = tmp / 'personal.conf'
                saved.write_text(policy)
                target.symlink_to(saved)
            else:
                target.write_text(policy)
        command = tmp / 'bin/ddcutil'
        command.write_text('#!/bin/sh\nprintf "%s" ' + shlex.quote(output) + '\nexit ' + str(code) + '\n')
        command.chmod(0o755)
        if prepare_extra:
            prepare_extra(tmp, env)
    return machine(generator=False, default_config=False, mem_kb=3997540,
                   prepare=prepare, script=script)


class DisplayProbeTests(unittest.TestCase):
    def run_case(self, **kwargs):
        run = private_run(**kwargs)
        self.addCleanup(shutil.rmtree, run['tmp'])
        return run

    def test_kernel_zero_size_attribute_has_identity(self):
        # Like DRM EDID, this real Linux attribute has bytes despite st_size=0.
        path = Path('/proc/sys/kernel/ostype')
        if not path.exists():
            self.skipTest('Linux sysctl attribute unavailable')
        self.assertEqual(path.stat().st_size, 0)
        data = path.read_bytes()
        self.assertTrue(data)
        run = self.run_case(edid=path)
        self.assertEqual(run['result'].returncode, 0, run['result'].stderr)
        self.assertIn(hashlib.sha256(data).hexdigest(), (run['root'] / STAMP).read_text())

    def test_monitor_replacement_reprobes_same_connector(self):
        run = self.run_case()
        self.assertEqual(run['result'].returncode, 0, run['result'].stderr)
        old_stamp = (run['root'] / STAMP).read_bytes()
        # An unchanged monitor exits without executing the changed DDC probe.
        cmd = run['tmp'] / 'bin/ddcutil'
        cmd.write_text('#!/bin/sh\nprintf "Display 1\\n"\n')
        again = subprocess.run(['bash', str(SCRIPT)], env=run['env'], capture_output=True, timeout=10)
        self.assertEqual(again.returncode, 0)
        self.assertTrue((run['root'] / POLICY).exists())
        (run['tmp'] / 'sys/class/drm/card1-DP-1/edid').write_bytes(b'second monitor')
        changed = subprocess.run(['bash', str(SCRIPT)], env=run['env'], capture_output=True, timeout=10)
        self.assertEqual(changed.returncode, 0, changed.stderr)
        self.assertFalse((run['root'] / POLICY).exists())
        self.assertNotEqual(old_stamp, (run['root'] / STAMP).read_bytes())

    def test_failed_or_unrecognized_probe_preserves_policy_without_stamp(self):
        for code, output in ((124, ''), (137, ''), (1, ''), (1, 'Display 1\n'),
                             (0, ''), (0, 'unexpected output\n')):
            for policy in (None, OWNED):
                with self.subTest(code=code, output=output, existing=bool(policy)):
                    run = self.run_case(code=code, output=output, policy=policy)
                    self.assertEqual(run['result'].returncode, 1)
                    self.assertFalse((run['root'] / STAMP).exists())
                    path = run['root'] / POLICY
                    self.assertEqual(path.read_text() if path.exists() else None, policy)
                    self.assertNotIn('brightness control restored', run['result'].stdout)

    def test_successful_known_unsupported_and_empty_topology(self):
        for output in ('Invalid display\nInvalid display\n', 'No displays found\n', 'No displays found.\n'):
            run = self.run_case(output=output)
            self.assertEqual(run['result'].returncode, 0, run['result'].stderr)
            self.assertEqual((run['root'] / POLICY).read_text(), OWNED)
            self.assertTrue((run['root'] / STAMP).exists())
        def no_monitor(tmp, env):
            (tmp / 'sys/class/drm/card1-DP-1/status').write_text('disconnected\n')
        run = self.run_case(code=1, output='', prepare_extra=no_monitor)
        self.assertEqual(run['result'].returncode, 0)
        self.assertFalse((run['root'] / POLICY).exists())
        self.assertIn('display=none', (run['root'] / STAMP).read_text())

    def test_missing_or_empty_edid_is_distinct_from_read_failure(self):
        for edid in (None, b''):
            run = self.run_case(edid=edid)
            self.assertEqual(run['result'].returncode, 0)
            self.assertIn('card1-DP-1:no-edid', (run['root'] / STAMP).read_text())
        def unreadable(tmp, env):
            (tmp / 'sys/class/drm/card1-DP-1/edid').mkdir()
        run = self.run_case(edid=None, prepare_extra=unreadable)
        self.assertEqual(run['result'].returncode, 1)
        self.assertFalse((run['root'] / STAMP).exists())
        self.assertFalse((run['root'] / POLICY).exists())

    def test_edid_bound(self):
        run = self.run_case(edid=b'x' * 32769)
        self.assertEqual(run['result'].returncode, 1)
        self.assertFalse((run['root'] / STAMP).exists())

    def test_personal_and_linked_policy_survives_both_outcomes(self):
        for output in ('Display 1\n', 'Invalid display\n'):
            for linked in (False, True):
                personal = '[Service]\nEnvironment=PERSONAL=1\n'
                run = self.run_case(output=output, policy=personal, linked=linked)
                self.assertEqual((run['root'] / POLICY).read_text(), personal)
                self.assertEqual(run['result'].returncode, 1 if linked else 0)
                if linked:
                    self.assertTrue((run['root'] / POLICY).is_symlink())
                    self.assertFalse((run['root'] / STAMP).exists())

    def test_topology_change_during_probe_remains_retryable(self):
        def change(tmp, env):
            command = tmp / 'bin/ddcutil'
            status = tmp / 'sys/class/drm/card1-DP-1/status'
            command.write_text('#!/bin/sh\nprintf "disconnected\\n" > ' + shlex.quote(str(status)) +
                               '\nprintf "Invalid display\\n"\n')
        run = self.run_case(prepare_extra=change)
        self.assertEqual(run['result'].returncode, 1)
        self.assertFalse((run['root'] / STAMP).exists())
        self.assertFalse((run['root'] / POLICY).exists())

    def test_linked_parent_and_hardlinked_policy_are_preserved(self):
        for kind in ('parent', 'hardlink'):
            def unsafe(tmp, env):
                target = tmp / 'root' / POLICY
                if kind == 'hardlink':
                    import os
                    os.link(target, tmp / 'other-owner.conf')
                else:
                    original = target.parent
                    saved = tmp / 'saved-directory'
                    original.rename(saved)
                    original.symlink_to(saved, target_is_directory=True)
            run = self.run_case(policy=OWNED, output='Display 1\n', prepare_extra=unsafe)
            self.assertEqual(run['result'].returncode, 1)
            self.assertEqual((run['root'] / POLICY).read_text(), OWNED)
            self.assertFalse((run['root'] / STAMP).exists())

    def test_failure_keeps_previous_stamp_and_retry_can_complete(self):
        def previous(tmp, env):
            target = tmp / 'root' / STAMP
            target.parent.mkdir(parents=True)
            target.write_text('previous hardware revision\n')
        run = self.run_case(code=124, output='', prepare_extra=previous)
        self.assertEqual(run['result'].returncode, 1)
        self.assertEqual((run['root'] / STAMP).read_text(), 'previous hardware revision\n')
        (run['tmp'] / 'bin/ddcutil').write_text('#!/bin/sh\nprintf "Display 1\\n"\n')
        again = subprocess.run(['bash', str(SCRIPT)], env=run['env'], capture_output=True, timeout=10)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertNotEqual((run['root'] / STAMP).read_text(), 'previous hardware revision\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
