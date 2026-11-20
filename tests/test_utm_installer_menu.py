#!/usr/bin/env python3
"""Run menu/EFI selection with private shell functions, never firmware or reboot."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "system_files/usr/libexec/moos-utm-installer-menu"


class InstallerMenu(unittest.TestCase):
    def probe(self, action, *, installed=True, install_code=0, firmware="", firmware_code=0,
              target="/dev/private-test-disk", readable=True):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = SOURCE.read_text().split('\nmkdir -p "$(dirname "$LOG")" /run', 1)[0]
            # Replace host-facing functions, retaining real control flow and EFI parsing.
            source += r'''
pick_target_disk() { printf '%s\n' "$MOOS_MENU_TEST_TARGET"; }
lsblk() {
    [ "$MOOS_MENU_TEST_READABLE" = 1 ] || return 7
    printf 'disk\n'
    if [ "$MOOS_MENU_TEST_INSTALLED" = 1 ]; then printf 'part btrfs\n'; fi
}
show_status() { printf 'status:%s\n' "$1" >> "$MOOS_MENU_TEST_CALLS"; }
run_install() { printf 'install:%s\n' "$1" >> "$MOOS_MENU_TEST_CALLS"; return "$MOOS_MENU_TEST_INSTALL_CODE"; }
whiptail() {
    printf 'dialog:%s\n' "$*" >> "$MOOS_MENU_TEST_CALLS"
    if [[ " $* " = *" --menu "* ]]; then
        while [ "$1" != --menu ]; do shift; done
        shift 5
        while [ "$#" -ge 2 ]; do
            printf 'row:%s|%s\n' "$1" "$2" >> "$MOOS_MENU_TEST_CALLS"
            shift 2
        done
        if [ "$#" -ne 0 ]; then printf 'invalid menu argument count\n' >> "$MOOS_MENU_TEST_CALLS"; fi
        if [ -e "$MOOS_MENU_TEST_MARKER" ]; then return 1; fi
        : > "$MOOS_MENU_TEST_MARKER"
        [ "$MOOS_MENU_TEST_ACTION" != cancel ] || return 1
        [ "$MOOS_MENU_TEST_ACTION" != error ] || return 255
        printf '%s\n' "$MOOS_MENU_TEST_ACTION" >&2
    fi
}
efibootmgr() {
    if [ "$#" = 0 ]; then printf '%s\n' "$MOOS_MENU_TEST_FIRMWARE"; return 0; fi
    printf 'efi:%s\n' "$*" >> "$MOOS_MENU_TEST_CALLS"
    return "$MOOS_MENU_TEST_FIRMWARE_CODE"
}
systemctl() { printf 'systemctl:%s\n' "$*" >> "$MOOS_MENU_TEST_CALLS"; }
main_menu
'''
            script = base / "probe.sh"
            script.write_text(source)
            env = {**os.environ, "MOOS_MENU_TEST_INSTALLED": str(int(installed)),
                   "MOOS_MENU_TEST_TARGET": target, "MOOS_MENU_TEST_READABLE": str(int(readable)),
                   "MOOS_MENU_TEST_ACTION": action,
                   "MOOS_MENU_TEST_INSTALL_CODE": str(install_code),
                   "MOOS_MENU_TEST_FIRMWARE": firmware,
                   "MOOS_MENU_TEST_FIRMWARE_CODE": str(firmware_code),
                   "MOOS_MENU_TEST_CALLS": str(base / "calls"),
                   "MOOS_MENU_TEST_MARKER": str(base / "shown")}
            result = subprocess.run(["bash", str(script)], env=env, text=True,
                                    capture_output=True, timeout=5)
            calls = (base / "calls").read_text() if (base / "calls").exists() else ""
            return result, calls

    def test_cancel_never_installs_or_reboots(self):
        for installed in (False, True):
            with self.subTest(installed=installed):
                result, calls = self.probe("cancel", installed=installed)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Recovery menu closed.", calls)
                menu, = [line for line in calls.splitlines() if line.startswith("dialog:") and " --menu " in line]
                self.assertIn("--clear", menu.removeprefix("dialog:").split())
                self.assertNotIn("install:", calls)
                self.assertNotIn("systemctl:", calls)

    def test_dialog_error_is_reported_without_installing(self):
        result, calls = self.probe("error")
        self.assertEqual(result.returncode, 255, result.stderr)
        self.assertIn("Recovery menu failed.", calls)
        self.assertNotIn("Recovery menu closed.", calls)
        self.assertNotIn("install:", calls)
        self.assertNotIn("systemctl:", calls)

    def test_recovery_menu_passes_real_tag_item_pairs(self):
        for installed, rows in (
            (False, ["2|Install latest signed MoOS", "5|Shell / serial debug"]),
            (True, ["1|إقلاع MoOS من UEFI | Boot MoOS firmware entry",
                    "2|Install latest signed MoOS",
                    "4|إعادة التثبيت: مسح القرص | Reinstall (erase target)"]),
        ):
            with self.subTest(installed=installed):
                result, calls = self.probe("cancel", installed=installed)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("invalid menu argument count", calls)
                self.assertEqual([line[4:] for line in calls.splitlines() if line.startswith("row:")], rows)

    def test_unavailable_target_cannot_offer_install(self):
        for target, readable in (("", True), ("/dev/private-test-disk", False)):
            with self.subTest(target=target):
                result, calls = self.probe("2", target=target, readable=readable)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Target layout could not be read", calls)
                self.assertNotIn("row:", calls)
                self.assertNotIn("install:", calls)
                self.assertNotIn("systemctl:", calls)

    def test_headless_entry_reports_manual_command_without_running_installer(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            installer = base / "installer"
            marker = base / "invoked"
            installer.write_text('#!/bin/sh\nprintf "called\\n" > "$MOOS_MENU_MARKER"\nexit 42\n')
            installer.chmod(0o755)
            source = SOURCE.read_text()
            for original, private in (("/usr/libexec/moos-utm-net-install", installer),
                                      ("/dev/tty1", base / "absent-tty1"),
                                      ("/dev/console", base / "console"),
                                      ("/var/log/moos-utm-installer-menu.log", base / "log"),
                                      ("/run", base / "run")):
                source = source.replace(original, str(private))
            result = subprocess.run(["bash", "-c", source], env={**os.environ, "MOOS_MENU_MARKER": str(marker)},
                                    capture_output=True, text=True, timeout=5)
            self.assertFalse(marker.exists(), "a missing menu started the installer")
            self.assertEqual(result.returncode, 1, result.stderr)
            status = (base / "run/moos-utm-installer-status").read_text()
            self.assertIn(f"sudo {installer}", status)

    def test_failed_install_never_reports_completion_or_reboots(self):
        result, calls = self.probe("2", install_code=9)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("install:install", calls)
        self.assertIn("Installation did not complete", calls)
        self.assertNotIn("Installation complete.", calls)
        self.assertNotIn("systemctl:", calls)

    def test_successful_install_can_reboot(self):
        result, calls = self.probe("2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Installation complete.", calls)
        self.assertIn("systemctl:reboot", calls)

    def test_unique_moos_entry_keeps_hex_b_and_ignores_first_other_entry(self):
        result, calls = self.probe("1", firmware="Boot0001* UTM Recovery\nBoot000B* MoOS\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("efi:-n 000B", calls)
        self.assertNotIn("efi:-n 0001", calls)
        self.assertIn("systemctl:reboot", calls)

    def test_missing_or_ambiguous_moos_entry_never_changes_firmware_or_reboots(self):
        for firmware in ("Boot0001* UTM Recovery", "Boot000A* MoOS\nBoot000B* MoOS backup"):
            with self.subTest(firmware=firmware):
                result, calls = self.probe("1", firmware=firmware)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("efi:", calls)
                self.assertNotIn("systemctl:", calls)

    def test_firmware_write_failure_never_reboots(self):
        result, calls = self.probe("1", firmware="Boot000B* MoOS", firmware_code=7)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("efi:-n 000B", calls)
        self.assertNotIn("systemctl:", calls)


if __name__ == '__main__':
    unittest.main(verbosity=2)
