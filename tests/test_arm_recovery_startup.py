#!/usr/bin/env python3
"""Keep recovery's native startup graph separate from cloud-final's own work."""
import configparser
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MENU = ROOT / "system_files/usr/lib/systemd/system/moos-utm-installer.service"
COLDPLUG = ROOT / "system_files/usr/lib/systemd/system/moos-arm-block-coldplug.service"


class RecoveryStartup(unittest.TestCase):
    @unittest.skipUnless(shutil.which("systemd-analyze"), "native systemd analyzer unavailable")
    def test_native_solver_starts_menu_without_waiting_for_cloud_final(self):
        # These inherited edges were read from the actual 966 guest. Target
        # default ordering matters: multi-user.target implicitly waits for its
        # wanted menu, while cloud-final explicitly waits for multi-user.
        units = {
            "basic.target": "[Unit]\nDefaultDependencies=no\n",
            "sysinit.target": "[Unit]\nDefaultDependencies=no\n",
            "shutdown.target": "[Unit]\nDefaultDependencies=no\n",
            "plymouth-quit.service": "[Unit]\nDefaultDependencies=no\n[Service]\nExecStart=/usr/bin/true\n",
            "NetworkManager.service": "[Unit]\nDefaultDependencies=no\n[Service]\nExecStart=/usr/bin/true\n",
            # The native datasource generator requests cloud-init.target from
            # multi-user.target.wants when the packaged seed is present.
            "multi-user.target": "[Unit]\nRequires=basic.target\nAfter=basic.target\nWants=cloud-init.target\n",
            "cloud-init.target": "[Unit]\nAfter=multi-user.target\nWants=cloud-final.service\n",
            "cloud-final.service": "[Unit]\nDefaultDependencies=no\nAfter=multi-user.target\n[Service]\nExecStart=/usr/bin/true\n",
        }
        current = MENU.read_text()
        admitted = configparser.ConfigParser(interpolation=None)
        admitted.read_string(current)
        self.assertEqual(admitted["Install"]["WantedBy"], "multi-user.target")
        self.assertEqual(admitted["Unit"]["RequiresMountsFor"], "/boot")
        self.assertIn("plymouth-quit.service", admitted["Unit"]["After"].split())
        self.assertNotIn("cloud-final.service", admitted["Unit"]["After"].split())
        late = current.replace("After=" + admitted["Unit"]["After"],
                               "After=NetworkManager.service cloud-final.service")
        for name, source, cycle in (
            ("966-discarded-job", late, True),
            ("1005-late-menu", late.replace("WantedBy=multi-user.target",
                                            "WantedBy=cloud-init.target"), False),
            ("local-menu", current, False),
        ):
            with self.subTest(source=name), tempfile.TemporaryDirectory(prefix="moos-recovery-graph-") as temporary:
                private = Path(temporary)
                config = configparser.ConfigParser(interpolation=None)
                config.read_string(source)
                target = config["Install"]["WantedBy"]
                self.assertIn(target, ("multi-user.target", "cloud-init.target"))
                for unit, text in units.items():
                    # Materialize the enablement edge in the offline graph.
                    if unit == target:
                        text += "Wants=moos-utm-installer.service\n"
                    (private / unit).write_text(text)
                # Only the executable is replaced: verify never starts it, and
                # this keeps availability independent of the installed image.
                (private / MENU.name).write_text(source.replace(
                    "ExecStart=/usr/libexec/moos-utm-installer-menu", "ExecStart=/usr/bin/true"))
                env = dict(os.environ, SYSTEMD_UNIT_PATH=temporary,
                           DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(private / "no-bus"))
                result = subprocess.run(
                    ["systemd-analyze", "--user", "verify", "--man=no", "--generators=no",
                     str(private / "multi-user.target")], env=env, capture_output=True, text=True, timeout=15)
                diagnostic = result.stdout + result.stderr
                self.assertEqual(result.returncode, 0, diagnostic)
                # The old solver also exits zero after deleting a real job.
                self.assertEqual("Found ordering cycle" in diagnostic, cycle, diagnostic)
                self.assertEqual("deleted to break ordering cycle" in diagnostic, cycle, diagnostic)

    @unittest.skipUnless(shutil.which("systemd-analyze"), "native systemd analyzer unavailable")
    def test_only_the_owner_of_recovery_tty1_can_start(self):
        dropin = ROOT / "build_files/arm-recovery-getty-tty1.conf"
        marker = "/etc/moos-utm-install-complete"
        self.assertIn("ConditionPathExists=" + marker, dropin.read_text().splitlines())
        self.assertIn("ConditionPathExists=!" + marker, MENU.read_text().splitlines())
        with tempfile.TemporaryDirectory(prefix="moos-recovery-tty-") as temporary:
            private = Path(temporary)
            complete = private / "complete"
            unit = "[Unit]\nDefaultDependencies=no\n[Service]\nExecStart=/usr/bin/true\n"
            (private / "getty@.service").write_text(unit)
            (private / "autovt@.service").symlink_to("getty@.service")
            (private / "serial-getty@.service").write_text(unit)
            (private / MENU.name).write_text(MENU.read_text().replace(marker, str(complete)))
            env = dict(os.environ, SYSTEMD_UNIT_PATH=temporary,
                       DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(private / "no-bus"))

            def conditions(name, status):
                result = subprocess.run(["systemd-analyze", "--user", "--generators=no",
                                         "condition", "--unit=" + name], env=env,
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, status, (name, result.stderr))
                if status:
                    self.assertIn(str(complete), result.stderr)

            # The previous recovery image admitted both the menu and the login.
            conditions(MENU.name, 0)
            conditions("getty@tty1.service", 0)
            override = private / "getty@tty1.service.d/50-moos-recovery-menu.conf"
            override.parent.mkdir()
            override.write_text(dropin.read_text().replace(marker, str(complete)))
            for installed in (False, True):
                if installed:
                    complete.touch()
                conditions(MENU.name, int(installed))
                for name in ("getty@tty1.service", "autovt@tty1.service"):
                    conditions(name, int(not installed))
                for name in ("getty@tty2.service", "serial-getty@ttyAMA0.service"):
                    conditions(name, 0)

    def test_coldplug_waits_for_the_required_native_daemon(self):
        config = configparser.ConfigParser(interpolation=None, strict=False)
        # ConfigParser keeps only the last repeated After=. Read every actual
        # directive, as systemd does, instead of losing one inherited edge.
        text = COLDPLUG.read_text()
        after = {value for line in text.splitlines() if line.startswith("After=")
                 for value in line.removeprefix("After=").split()}
        config.read_string(text)
        self.assertIn("systemd-udevd.service", config["Unit"]["Requires"].split())
        self.assertTrue({"systemd-udevd.service", "systemd-udev-trigger.service"} <= after)
        self.assertEqual(config["Unit"]["DefaultDependencies"], "no")
        self.assertEqual(config["Service"]["TimeoutStartSec"], "120")
        self.assertEqual(config["Service"]["ExecStart"], "/usr/libexec/moos-arm-block-coldplug")

    def test_packaged_seed_does_not_wait_for_its_own_final_stage(self):
        path = ROOT / "artwork/generate_utm_installer.py"
        spec = importlib.util.spec_from_file_location("moos_recovery_bundle", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        seed = module.seed_user_data()
        self.assertIn("[systemctl, enable, --now, NetworkManager]", seed)
        self.assertNotIn("moos-utm-installer.service", seed)
        build = (ROOT / "build_files/build-arm-recovery.sh").read_text()
        self.assertIn("systemctl enable moos-utm-installer.service", build)


if __name__ == "__main__":
    unittest.main()
