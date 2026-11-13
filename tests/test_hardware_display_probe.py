#!/usr/bin/env python3
"""Exercise the real adapter in a private root; never write host policy/bus."""
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time
import unittest

from test_hardware_adapt_zram_availability import machine, SCRIPT

POLICY = Path('etc/systemd/user/plasma-powerdevil.service.d/50-moos-ddc.conf')
STAMP = Path('etc/moos/hardware-adapt.state')
OWNED = ('# Written by moos-hardware-adapt: no DDC/CI display answered on this\n'
         '# machine, and probing for one cost 6.5s of every login. Reversible —\n'
         '# delete this file (or attach a DDC-capable monitor and bump HW_REV).\n'
         '[Service]\nEnvironment=POWERDEVIL_NO_DDCUTIL=1\n')


def private_run(*, output='Invalid display\n', error='', code=0, edid=b'first monitor',
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
        command.write_text('#!/bin/sh\nprintf "%s" ' + shlex.quote(output) +
                           '\nprintf "%s" ' + shlex.quote(error) + ' >&2\nexit ' + str(code) + '\n')
        command.chmod(0o755)
        if prepare_extra:
            prepare_extra(tmp, env)
    return machine(generator=False, default_config=False, mem_kb=3997540,
                   prepare=prepare, script=script)


def bind_driver(tmp, driver, *, card='card1'):
    """Native DRM topology: virtgpu binds below its PCI/MMIO DRM parent."""
    sysfs = tmp / 'sys'
    device = sysfs / 'class/drm' / card / 'device'
    device.mkdir(parents=True)
    if driver == 'virtio_gpu':
        transport = sysfs / 'bus/pci/drivers/virtio-pci'
        transport.mkdir(parents=True, exist_ok=True)
        (device / 'driver').symlink_to(transport)
        device = device / 'virtio0'
        device.mkdir()
        owner = sysfs / 'bus/virtio/drivers/virtio_gpu'
    else:
        owner = sysfs / 'bus/pci/drivers' / driver
    owner.mkdir(parents=True, exist_ok=True)
    (device / 'driver').symlink_to(owner)


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

    def test_exit_zero_with_diagnostics_is_not_no_ddc_evidence(self):
        for output in ('Invalid display\n', 'Display 1\n', 'No displays found\n'):
            for policy in (None, OWNED):
                run = self.run_case(output=output, policy=policy,
                                    error='Device /dev/i2c-5 is not readable and writable.\n')
                self.assertEqual(run['result'].returncode, 1)
                self.assertFalse((run['root'] / STAMP).exists())
                path = run['root'] / POLICY
                self.assertEqual(path.read_text() if path.exists() else None, policy)
                self.assertIn('probe diagnostics', run['result'].stdout)

    def test_virtual_drm_owners_do_not_require_a_physical_ddc_bus(self):
        for driver in ('virtio_gpu', 'qxl', 'bochs-drm'):
            for policy in (None, OWNED):
                def virtual(tmp, env):
                    bind_driver(tmp, driver)
                    command = tmp / 'bin/ddcutil'
                    command.write_text('#!/bin/sh\n: > ' + shlex.quote(str(tmp / 'ddc-called')) + '\nexit 1\n')
                run = self.run_case(prepare_extra=virtual, policy=policy)
                self.assertEqual(run['result'].returncode, 0, run['result'].stderr)
                self.assertIn('ddc=virtual', (run['root'] / STAMP).read_text())
                self.assertFalse((run['tmp'] / 'ddc-called').exists())
                path = run['root'] / POLICY
                self.assertEqual(path.read_text() if path.exists() else None, policy)

    def test_physical_unknown_or_mixed_owners_keep_missing_bus_refusal(self):
        for driver in (None, 'amdgpu', 'i915', 'virtio-pci', 'unreviewed'):
            def physical(tmp, env):
                if driver is not None:
                    bind_driver(tmp, driver)
            run = self.run_case(prepare_extra=physical, code=1, output='',
                                error='No /dev/i2c devices exist.\n')
            self.assertEqual(run['result'].returncode, 1)
            self.assertFalse((run['root'] / STAMP).exists())
        def mixed(tmp, env):
            bind_driver(tmp, 'virtio_gpu')
            connector = tmp / 'sys/class/drm/card2-DP-1'
            connector.mkdir()
            (connector / 'status').write_text('connected\n')
            bind_driver(tmp, 'amdgpu', card='card2')
        run = self.run_case(prepare_extra=mixed, code=1, output='')
        self.assertEqual(run['result'].returncode, 1)
        self.assertFalse((run['root'] / STAMP).exists())

    def test_virtual_owner_change_reprobes_same_edid(self):
        run = self.run_case(prepare_extra=lambda tmp, env: bind_driver(tmp, 'qxl'))
        self.assertEqual(run['result'].returncode, 0)
        link = run['tmp'] / 'sys/class/drm/card1/device/driver'
        link.unlink()
        physical = run['tmp'] / 'sys/bus/pci/drivers/amdgpu'
        physical.mkdir()
        link.symlink_to(physical)
        again = subprocess.run(['bash', str(SCRIPT)], env=run['env'], capture_output=True, timeout=10)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn('ddc=probe', (run['root'] / STAMP).read_text())
        self.assertEqual((run['root'] / POLICY).read_text(), OWNED)

    def test_writeback_is_not_a_physical_monitor(self):
        def writeback(tmp, env):
            connector = tmp / 'sys/class/drm/card1-DP-1'
            connector.rename(connector.with_name('card1-Writeback-1'))
            (connector.with_name('card1-Writeback-1') / 'status').write_text('unknown\n')
        run = self.run_case(prepare_extra=writeback, code=1, output='')
        self.assertEqual(run['result'].returncode, 0)
        self.assertIn('ddc=none', (run['root'] / STAMP).read_text())
        self.assertFalse((run['root'] / POLICY).exists())

    def test_native_ddc_no_i2c_is_not_a_successful_empty_scan(self):
        bwrap, ddcutil = shutil.which('bwrap'), shutil.which('ddcutil')
        if not bwrap or not ddcutil:
            self.skipTest('native ddcutil/bwrap unavailable; process controls still required')
        result = subprocess.run(
            [bwrap, '--ro-bind', '/', '/', '--dev', '/dev', '--proc', '/proc',
             '--unshare-all', '--die-with-parent', '--new-session', '--tmpfs', '/tmp',
             '--setenv', 'HOME', '/tmp', '--setenv', 'XDG_CACHE_HOME', '/tmp/cache',
             '--setenv', 'XDG_CONFIG_HOME', '/tmp/config', '--setenv', 'LC_ALL', 'C',
             '--', '/usr/bin/timeout', '--kill-after=2s', '10', ddcutil, 'detect', '--brief'],
            capture_output=True, text=True, timeout=15)
        if 'bwrap:' in result.stderr:
            self.skipTest('native private namespace unavailable: ' + result.stderr.splitlines()[0])
        self.assertEqual(result.returncode, 1, result)
        self.assertIn('No /dev/i2c devices exist.', result.stderr)
        run = self.run_case(output=result.stdout, error=result.stderr, code=result.returncode)
        self.assertEqual(run['result'].returncode, 1)
        self.assertFalse((run['root'] / STAMP).exists())

        # One harmless fake device lets native detect reach verify_i2c_access.
        # That function's missing-device diagnostics do not change detect's exit
        # status: retaining stderr is necessary, not merely a stub convention.
        command = result.args
        marker = command.index('--proc')
        command[marker:marker] = ['--dev-bind', '/dev/null', '/dev/i2c-0']
        diagnostic = subprocess.run(command, capture_output=True, text=True, timeout=15)
        if diagnostic.returncode == 0 and diagnostic.stderr.strip():
            run = self.run_case(output=diagnostic.stdout, error=diagnostic.stderr,
                                code=diagnostic.returncode)
            self.assertEqual(run['result'].returncode, 1)
            self.assertFalse((run['root'] / STAMP).exists())
            self.assertIn('probe diagnostics', run['result'].stdout)
        else:
            # Some CI hosts expose no physical I2C topology to diagnose. The
            # deterministic exit0+stderr controls above remain mandatory.
            self.assertIn(diagnostic.returncode, (0, 1), diagnostic)

    def test_probe_output_is_bounded_before_publication(self):
        for stream in ('stdout', 'stderr'):
            def large(tmp, env):
                cmd = tmp / 'bin/ddcutil'
                redirect = ' >&2' if stream == 'stderr' else ''
                cmd.write_text('#!/bin/sh\npython3 -c "print(\'x\' * 150000)"' + redirect + '\n')
            run = self.run_case(prepare_extra=large, policy=OWNED)
            self.assertEqual(run['result'].returncode, 1)
            self.assertFalse((run['root'] / STAMP).exists())
            self.assertEqual((run['root'] / POLICY).read_text(), OWNED)
            self.assertIn('probe oversized', run['result'].stdout)

    def test_output_refusal_retires_descendant_after_leader_exit(self):
        def descendant(tmp, env):
            code = ("import os, time\n"
                    "pid = os.fork()\n"
                    "if pid == 0:\n"
                    "    time.sleep(0.2)\n"
                    "    os.write(1, b'x' * 150000)\n"
                    "    time.sleep(60)\n"
                    "else:\n"
                    f"    open({str(tmp / 'descendant-pid')!r}, 'w').write(str(pid))\n"
                    "    os._exit(0)\n")
            (tmp / 'bin/ddcutil').write_text('#!/bin/sh\nexec python3 -c ' + shlex.quote(code) + '\n')
        run = self.run_case(prepare_extra=descendant)
        pid = int((run['tmp'] / 'descendant-pid').read_text())
        def alive():
            try:
                raw = Path(f'/proc/{pid}/stat').read_text()
                return raw[raw.rindex(')') + 2:].split()[0] not in ('Z', 'X', 'x')
            except FileNotFoundError:
                return False
        try:
            deadline = time.monotonic() + 2
            while alive() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertFalse(alive(), 'refused probe left its child running')
            self.assertEqual(run['result'].returncode, 1)
            self.assertIn('probe oversized', run['result'].stdout)
            self.assertFalse((run['root'] / STAMP).exists())
        finally:
            if alive():
                os.kill(pid, 9)

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
