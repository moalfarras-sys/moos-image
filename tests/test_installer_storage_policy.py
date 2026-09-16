#!/usr/bin/env python3
"""Gate: P1.3 — the offline installer's storage policy is hardware-safe.

WHY THIS EXISTS

moos-install-to-disk is the one privileged, destructive step in MoOS: it wipes a disk. Its
safety rests on a handshake with moos-list-disks — the helper that decides which disks the
user is even shown, and which of them count as removable. Nothing tested that helper, and it
asked lsblk for RM and HOTPLUG but never for TRAN.

That gap is not cosmetic. An internal eMMC — the only disk in a tablet or a cheap laptop —
reports HOTPLUG=1 on many boards, so it was classified "Removable drive". And
moos-install-to-disk deliberately FAILS CLOSED: when it cannot identify the live medium it
refuses a removable target, because that target might be the USB it booted from. Put those
together and the only installable disk in the machine is refused with live-node, on exactly
the hardware least able to boot something else. The eMMC boot and RPMB nodes (mmcblk0boot0,
mmcblk0boot1, mmcblk0rpmb) are separate type=disk devices too, and were listed as candidates.

The other half is that the installer's user-facing failure text is decided by grepping its
log for ENGLISH phrases ("no space left", "input/output error"). The live session may be
Arabic. Without a pinned locale the classifier matches nothing and a user who simply ran out
of room is told "something unexpected happened" instead of "the disk doesn't have enough
space" — a message that already exists and was simply never reached.

These fixtures drive the REAL enumerator with a fake lsblk, because the machine running the
gate has whatever disks it has, and a storage policy must be proven against hardware nobody
in CI owns.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENUMERATOR = ROOT / "system_files/usr/bin/moos-list-disks"
INSTALLER = ROOT / "system_files/usr/bin/moos-install-to-disk"

FAKE_LSBLK = r"""#!/usr/bin/bash
# Dispatch on the exact call shapes moos-list-disks uses.
case "$*" in
  *"-J"*)            cat "$MOOS_TEST_DISKS" ;;
  *"pkname"*)        printf '%s\n' "$MOOS_TEST_PKNAME" ;;
  *"-ndo type"*)     printf '%s\n' "disk" ;;
  *"FSTYPE"*)        node="${@: -1}"; cat "$MOOS_TEST_PARTS/$(basename "$node")" 2>/dev/null || true ;;
  *)                 exit 0 ;;
esac
"""

FAKE_FINDMNT = r"""#!/usr/bin/bash
printf '%s\n' "$MOOS_TEST_LIVE_SOURCE"
"""


def disk(name: str, *, size: int, tran: str, rm: bool, hotplug: bool,
         model: str | None = "Disk", ro: bool = False) -> dict:
    return {"name": name, "path": f"/dev/{name}", "type": "disk", "size": size,
            "model": model, "vendor": "ACME    ", "rm": rm, "ro": ro,
            "hotplug": hotplug, "tran": tran}


GIB = 1000 ** 3


class StoragePolicy(unittest.TestCase):
    def enumerate_disks(self, devices: list[dict], *, live_source: str = "/dev/sdc1",
                        pkname: str = "sdc", partitions: dict[str, str] | None = None) -> dict:
        root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="moos-disks-")))
        (root / "parts").mkdir()
        for node, text in (partitions or {}).items():
            (root / "parts" / node).write_text(text, encoding="utf-8")
        disks_file = root / "disks.json"
        disks_file.write_text(json.dumps({"blockdevices": devices}), encoding="utf-8")

        binaries = root / "bin"
        binaries.mkdir()
        for name, body in (("lsblk", FAKE_LSBLK), ("findmnt", FAKE_FINDMNT)):
            path = binaries / name
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)

        environment = os.environ | {
            "PATH": f"{binaries}:{os.environ.get('PATH', '')}",
            "MOOS_TEST_DISKS": str(disks_file),
            "MOOS_TEST_PARTS": str(root / "parts"),
            "MOOS_TEST_LIVE_SOURCE": live_source,
            "MOOS_TEST_PKNAME": pkname,
        }
        result = subprocess.run([sys.executable, str(ENUMERATOR)], env=environment,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def by_node(self, report: dict) -> dict[str, dict]:
        return {entry["node"]: entry for entry in report["disks"]}

    # ── the hardware matrix ──────────────────────────────────────────────────
    def test_sata_and_nvme_are_internal(self):
        report = self.enumerate_disks([
            disk("sda", size=500 * GIB, tran="sata", rm=False, hotplug=False),
            disk("nvme0n1", size=1000 * GIB, tran="nvme", rm=False, hotplug=False),
        ])
        found = self.by_node(report)
        for node in ("/dev/sda", "/dev/nvme0n1"):
            self.assertEqual(found[node]["kind"], "internal", node)
            self.assertFalse(found[node]["removable"], node)

    def test_a_usb_stick_is_removable(self):
        report = self.enumerate_disks([
            disk("sdc", size=32 * GIB, tran="usb", rm=True, hotplug=True),
        ], live_source="", pkname="")
        self.assertTrue(self.by_node(report)["/dev/sdc"]["removable"])

    def test_an_internal_emmc_is_not_called_removable(self):
        """The defect this gate was written for: HOTPLUG=1 on soldered storage.

        moos-install-to-disk refuses a REMOVABLE target when it cannot identify the live
        medium. Mislabel a tablet's only disk and the install is refused on the hardware
        least able to boot an alternative.
        """
        report = self.enumerate_disks([
            disk("mmcblk0", size=64 * GIB, tran="mmc", rm=False, hotplug=True),
        ], live_source="", pkname="")
        entry = self.by_node(report)["/dev/mmcblk0"]
        self.assertFalse(entry["removable"], "soldered eMMC is not removable media")
        self.assertEqual(entry["kind"], "internal")

    def test_an_sd_card_is_still_removable(self):
        report = self.enumerate_disks([
            disk("mmcblk1", size=64 * GIB, tran="mmc", rm=True, hotplug=True),
        ], live_source="", pkname="")
        self.assertTrue(self.by_node(report)["/dev/mmcblk1"]["removable"],
                        "an SD card really is removable; only soldered eMMC is not")

    def test_emmc_boot_and_rpmb_nodes_are_never_offered(self):
        report = self.enumerate_disks([
            disk("mmcblk0", size=64 * GIB, tran="mmc", rm=False, hotplug=True),
            disk("mmcblk0boot0", size=4 * 1000 * 1000, tran="mmc", rm=False, hotplug=True),
            disk("mmcblk0boot1", size=4 * 1000 * 1000, tran="mmc", rm=False, hotplug=True),
            disk("mmcblk0rpmb", size=4 * 1000 * 1000, tran="mmc", rm=False, hotplug=True),
        ], live_source="", pkname="")
        self.assertEqual(sorted(self.by_node(report)), ["/dev/mmcblk0"],
                         "eMMC boot/RPMB areas are not installation targets")

    def test_the_live_medium_is_marked_and_sorted_last(self):
        report = self.enumerate_disks([
            disk("sdc", size=32 * GIB, tran="usb", rm=True, hotplug=True),
            disk("sda", size=500 * GIB, tran="sata", rm=False, hotplug=False),
        ], live_source="/dev/sdc1", pkname="sdc")
        self.assertEqual(report["liveNode"], "/dev/sdc")
        self.assertTrue(self.by_node(report)["/dev/sdc"]["isLive"])
        self.assertEqual(report["disks"][-1]["node"], "/dev/sdc",
                         "the disk the user booted from must not be the obvious target")

    def test_pseudo_and_read_only_devices_are_excluded(self):
        report = self.enumerate_disks([
            disk("sda", size=500 * GIB, tran="sata", rm=False, hotplug=False),
            disk("zram0", size=8 * GIB, tran="", rm=False, hotplug=False, model=None),
            disk("loop0", size=2 * GIB, tran="", rm=False, hotplug=False, model=None),
            disk("sr0", size=1 * GIB, tran="sata", rm=True, hotplug=True),
            disk("sdz", size=500 * GIB, tran="sata", rm=False, hotplug=False, ro=True),
        ], live_source="", pkname="")
        self.assertEqual(sorted(self.by_node(report)), ["/dev/sda"])

    def test_a_disk_too_small_for_moos_is_flagged_not_hidden(self):
        report = self.enumerate_disks([
            disk("sdb", size=8 * GIB, tran="usb", rm=True, hotplug=True),
        ], live_source="", pkname="")
        self.assertTrue(self.by_node(report)["/dev/sdb"]["tooSmall"],
                        "a user must see why a disk cannot be chosen, not wonder where it went")

    def test_an_existing_windows_install_is_reported_before_it_is_erased(self):
        report = self.enumerate_disks(
            [disk("sda", size=500 * GIB, tran="sata", rm=False, hotplug=False)],
            live_source="", pkname="",
            partitions={"sda": "ntfs  Microsoft basic data  Windows  Basic\n"})
        entry = self.by_node(report)["/dev/sda"]
        self.assertTrue(entry["hasOS"])
        self.assertEqual(entry["osName"], "Windows")
        self.assertTrue(entry["hasData"])

    # ── the installer's own policy ───────────────────────────────────────────
    def test_every_destructive_command_names_only_the_chosen_target(self):
        source = INSTALLER.read_text(encoding="utf-8")
        code = "\n".join(line for line in source.splitlines()
                         if not line.lstrip().startswith("#"))
        def invokes(line: str, verb: str) -> bool:
            """A line that RUNS the tool, not one that mentions it.

            The installer matches bootc log output with case patterns like
            `*GPT*|*sgdisk*)` to decide which PHASE to emit. Those name the tool and
            touch nothing, so only a real command token counts.
            """
            for token in line.split():
                base = token.split("/")[-1]
                if base == verb or base.startswith(verb + "."):
                    return True
            return False

        targets = ("$NODE", "$ESP_PART", "$ROOT_PART", "$part", "$dev", "$esp", "$disk")
        for verb in ("wipefs", "sgdisk", "sfdisk", "mkfs", "blkdiscard", "parted"):
            for line in code.splitlines():
                if not invokes(line, verb):
                    continue
                self.assertTrue(
                    any(name in line for name in targets),
                    f"{verb} must act on the chosen target, not a literal device: {line.strip()}")

    def test_the_failure_classifier_can_still_read_its_own_log(self):
        """Actionable messages exist; a translated log is what stops them being reached."""
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("export LC_ALL=C", source,
                      "the no-space/disk-io classifier greps English phrases; pin the locale")
        for phrase, code in (("no space left on device", "no-space"),
                             ("Input/output error", "disk-io"),
                             ("no such image", "no-image")):
            self.assertIn(code, source)
            self.assertRegex(source, r"reason=\"" + code + r"\"")
            self.assertTrue(any(word in source.lower() for word in phrase.lower().split()[:2]),
                            f"nothing in the classifier matches {phrase!r}")

    def test_the_encryption_decision_is_written_down(self):
        """P1.3 asks for a decision. MoOS does not encrypt; that must be deliberate."""
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("ENCRYPTION:", source,
                      "an installer that does not encrypt must say so and say why")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(StoragePolicy))
    sys.exit(0 if result.wasSuccessful() else 1)
