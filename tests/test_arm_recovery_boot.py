#!/usr/bin/env python3
"""Controls for archive-bound recovery admission; never boot or access a guest."""
import importlib.util
import json
from pathlib import Path
import plistlib
import socket
import stat
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("recovery_boot", ROOT / "tests/arm_recovery_boot.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
spec = importlib.util.spec_from_file_location("recovery_packager", ROOT / "artwork/generate_utm_installer.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)
MENU = "MoOS UTM\nInstall latest signed MoOS\nShell / serial debug\n<Ok> <Cancel>"


def fixture(root, *, change=None, duplicate=False, link=False):
    installer, target = root / "installer", root / "target"
    installer.write_bytes(b"private installer fixture")
    target.write_bytes(b"private empty target fixture")
    entries = {
        "config.plist": plistlib.dumps(packager.build_config(iphone=True)),
        "README-FIRST.txt": ("installer_sha256=" + gate.sha(installer) + "\n" +
                             "target_sha256=" + gate.sha(target) + "\n").encode(),
        "Data/installer.qcow2": installer.read_bytes(),
        "Data/target.qcow2": target.read_bytes(),
        "Data/seed.iso": packager.seed_user_data().encode(),
        "Data/moos-icon.png": b"private icon",
    }
    if change:
        change(entries)
    archive = root / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        for name, data in entries.items():
            if link and name == "Data/seed.iso":
                info = zipfile.ZipInfo(gate.PREFIX + name)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                zipped.writestr(info, b"/private/escape")
            else:
                zipped.writestr(gate.PREFIX + name, data)
        if duplicate:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                zipped.writestr(gate.PREFIX + "Data/seed.iso", entries["Data/seed.iso"])
    return archive


class RecoveryArchive(unittest.TestCase):
    def test_installer_capacity_matches_the_packaged_ten_gib_image(self):
        gib = 1024**3
        with tempfile.TemporaryDirectory() as directory:
            disk = Path(directory) / "installer.qcow2"
            disk.write_bytes(b"QFI\xfb" + (3).to_bytes(4, "big") + bytes(96))
            for size in (10 * gib, 10 * gib + 512):
                metadata = json.dumps({"format": "qcow2", "virtual-size": size}).encode()
                with patch.object(gate, "run", return_value=subprocess.CompletedProcess([], 0, metadata)):
                    if size == 10 * gib:
                        with self.assertRaisesRegex(RuntimeError, "disk format or size"):
                            gate.qcow_input(disk, 8 * gib)
                        self.assertEqual(gate.qcow_input(disk, gate.RECOVERY_DISK_LIMITS["installer"])["virtual-size"], size)
                    else:
                        with self.assertRaisesRegex(RuntimeError, "disk format or size"):
                            gate.qcow_input(disk, gate.RECOVERY_DISK_LIMITS["installer"])

    def test_all_three_packaged_devices_and_seed_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = fixture(root)
            before = gate.sha(archive)
            data = gate.unpack(archive, root / "out")
            self.assertEqual((data / "seed.iso").read_bytes(), packager.seed_user_data().encode())
            self.assertEqual(gate.sha(archive), before)

    def test_unexpected_duplicate_missing_and_linked_entries_are_refused(self):
        cases = [dict(change=lambda e: e.update({"../../escape": b"bad"})),
                 dict(change=lambda e: e.pop("Data/seed.iso")),
                 dict(duplicate=True), dict(link=True)]
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(RuntimeError):
                    gate.unpack(fixture(root, **case), root / "out")
                self.assertFalse((root / "escape").exists())

    def test_wrong_disk_digest_and_drive_order_are_refused(self):
        def reorder(entries):
            config = plistlib.loads(entries["config.plist"])
            config["Drive"].reverse()
            entries["config.plist"] = plistlib.dumps(config)
        for mutate in (reorder, lambda e: e.update({"Data/target.qcow2": b"changed"})):
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(RuntimeError):
                    gate.unpack(fixture(root, change=mutate), root / "out")


class NativeObservation(unittest.TestCase):
    def test_original_os_name_starting_and_cloud_init_messages_are_not_a_menu(self):
        for text in ("Welcome to MoOS Installer", "MoOS Installer Starting...",
                     "MoOS UTM installer ready — choose Install from the menu", ""):
            self.assertFalse(gate.menu_text(text))
        self.assertTrue(gate.menu_text(MENU))

    def test_real_failure_patterns_refuse_before_screen_or_input(self):
        for text in ("\x1b[0;1;31mFailed to start moos-arm-block-coldplug.service\x1b[0m",
                     "Dependency failed for /boot/efi.", "Reached target emergency.target"):
            self.assertTrue(gate.fatal_serial(text))
            with tempfile.TemporaryDirectory() as directory:
                serial = Path(directory) / "serial.log"
                serial.write_text("MoOS Installer\n" + text)
                with patch.object(gate, "screenshot") as capture:
                    process = type("Process", (), {"poll": lambda self: None})()
                    with self.assertRaisesRegex(RuntimeError, "failed/emergency"):
                        gate.wait_screen(None, process, serial, Path(directory), "menu",
                                         lambda s: True, 1)
                    capture.assert_not_called()

    def test_no_menu_times_out_and_dead_qemu_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            serial = root / "serial.log"
            serial.write_text("Welcome to MoOS Installer")
            process = type("Process", (), {"poll": lambda self: None})()
            with patch.object(gate, "screenshot", return_value=(b"pixels", "MoOS Installer", [])), \
                    patch.object(gate.time, "sleep"), \
                    patch.object(gate.time, "monotonic", side_effect=[0, 0, 2]):
                with self.assertRaisesRegex(RuntimeError, "deadline"):
                    gate.wait_screen(None, process, serial, root, "menu",
                                     lambda s: gate.menu_text(s[1]), 1)
            process = type("Process", (), {"poll": lambda self: 0})()
            with self.assertRaisesRegex(RuntimeError, "QEMU exited"):
                gate.wait_screen(None, process, serial, root, "menu", lambda s: True, 1)

    def test_qmp_is_private_and_rejects_enter_before_sending(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "qmp.sock")
            listener = socket.socket(socket.AF_UNIX)
            listener.bind(path)
            listener.listen()
            received = []
            def server():
                client, _ = listener.accept()
                with client, client.makefile("rb") as reader:
                    client.sendall(b'{"QMP":{}}\n')
                    for _ in range(2):
                        received.append(json.loads(reader.readline()))
                        client.sendall(b'{"return":{}}\n')
            worker = threading.Thread(target=server)
            worker.start()
            qmp = gate.QMP(path)
            qmp.key("tab")
            with self.assertRaisesRegex(RuntimeError, "unsafe"):
                qmp.key("ret")
            qmp.sock.close()
            worker.join(timeout=3)
            listener.close()
            self.assertFalse(worker.is_alive())
            self.assertEqual([r["execute"] for r in received], ["qmp_capabilities", "send-key"])
            self.assertEqual(received[1]["arguments"]["keys"][0]["data"], "tab")


class ReleaseAdmission(unittest.TestCase):
    def test_recovery_boot_is_mandatory_before_upload_and_auto_promotion(self):
        workflow = (ROOT / ".github/workflows/build-arm.yml").read_text()
        start = workflow.index("      - name: Boot and accept the packaged three-drive recovery installer\n")
        stop = workflow.index("      - name: Upload ARM recovery acceptance evidence\n", start)
        block = workflow[start:stop]
        self.assertNotIn("continue-on-error", block)
        self.assertNotIn("if:", block)
        self.assertIn('tests/boot_utm_net_installer.sh "$archive"', block)
        self.assertIn('--expected-sha256 "$before" --revision "$GITHUB_SHA" --run-id "$GITHUB_RUN_ID"', block)
        self.assertLess(start, workflow.index("      - name: Upload UTM Net Installer\n"))
        self.assertIn("needs: [build, disk]", workflow)
        self.assertIn("needs.disk.result == 'success'", workflow)

    def test_proven_archive_is_not_randomly_regenerated_after_acceptance(self):
        workflow = (ROOT / ".github/workflows/build-arm.yml").read_text()
        final = workflow.split("      - name: Package the boot-proven ARM releases\n", 1)[1]
        self.assertNotIn("python3 artwork/generate_utm_installer.py", final)
        self.assertIn('"$MOOS_ARM_RECOVERY_PROVEN_SHA256"', final)
        self.assertIn('cp "$recovery_archive" "$work/MoOS-UTM-Installer.utm.zip"', final)
        for path in ("tests/boot_utm_net_installer.sh", "tests/arm_recovery_boot.py",
                     "tests/test_arm_recovery_boot.py"):
            self.assertEqual(workflow.count('      - "' + path + '"'), 2)
        for runner in ("Justfile", "tests/repo-gates.sh", ".github/workflows/build-arm.yml"):
            self.assertIn("python3 tests/test_arm_recovery_boot.py", (ROOT / runner).read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
