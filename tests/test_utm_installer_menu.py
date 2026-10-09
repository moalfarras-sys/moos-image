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
    def probe(self, action, *, installed=True, install_code=0, firmware="", firmware_code=0):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = SOURCE.read_text().split('\nmkdir -p "$(dirname "$LOG")" /run', 1)[0]
            # Replace host-facing functions, retaining real control flow and EFI parsing.
            source += r'''
pick_target_disk() { printf '/dev/private-test-disk\n'; }
target_has_moos() { [ "$MOOS_MENU_TEST_INSTALLED" = 1 ]; }
target_has_data() { [ "$MOOS_MENU_TEST_INSTALLED" = 1 ]; }
show_status() { printf 'status:%s\n' "$1" >> "$MOOS_MENU_TEST_CALLS"; }
run_install() { printf 'install:%s\n' "$1" >> "$MOOS_MENU_TEST_CALLS"; return "$MOOS_MENU_TEST_INSTALL_CODE"; }
whiptail() {
    printf 'dialog:%s\n' "$*" >> "$MOOS_MENU_TEST_CALLS"
    if [[ " $* " = *" --menu "* ]]; then
        if [ -e "$MOOS_MENU_TEST_MARKER" ]; then return 1; fi
        : > "$MOOS_MENU_TEST_MARKER"
        [ "$MOOS_MENU_TEST_ACTION" != cancel ] || return 1
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
                self.assertNotIn("install:", calls)
                self.assertNotIn("systemctl:", calls)

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
