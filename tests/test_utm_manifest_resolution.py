#!/usr/bin/env python3
"""An old recovery image resolves the promoted registry target once and fails closed."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "system_files/usr/libexec/moos-utm-net-install"


class ManifestResolution(unittest.TestCase):
    def resolve(self, remote, exit_code=0):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            binary = base / "bin"
            binary.mkdir()
            local = base / "local.json"
            local.write_text(json.dumps({"digest": "sha256:" + "a" * 64, "version": "44.20261001.1"}))
            network = base / "remote.json"
            network.write_text(json.dumps({"Digest": remote.get("digest"),
                                          "Labels": {"org.opencontainers.image.version": remote.get("version", "unknown")}}))
            skopeo = binary / "skopeo"
            skopeo.write_text('#!/bin/sh\nprintf "%s\\n" "$*" > "$MOOS_NET_TEST_ARGS"\n'
                            'cat "$MOOS_NET_TEST_BODY"\nexit "$MOOS_NET_TEST_EXIT"\n')
            skopeo.chmod(0o755)
            text = SOURCE.read_text()
            function = text[text.index("resolve_digest() {"):text.index("verify_and_install() {")]
            helper = base / "probe.sh"
            helper.write_text("set -euo pipefail\nrequire_cmd() { command -v \"$1\" >/dev/null; }\n"
                              "status() { printf '%s\\n' \"$1\" >&2; }\n"
                              "log() { printf '%s\\n' \"$*\" >&2; }\n"
                              'MANIFEST_LOCAL="$MOOS_NET_TEST_LOCAL"\n'
                              'REGISTRY="ghcr.io/moalfarras-sys/moos-arm"\n' + function + "\nresolve_digest\n")
            env = {**os.environ, "PATH": str(binary) + ":/usr/bin:/bin",
                   "MOOS_NET_TEST_LOCAL": str(local), "MOOS_NET_TEST_BODY": str(network),
                   "MOOS_NET_TEST_EXIT": str(exit_code), "MOOS_NET_TEST_ARGS": str(base / "args")}
            result = subprocess.run(["bash", str(helper)], env=env, text=True,
                                    capture_output=True, timeout=10)
            arguments = (base / "args").read_text() if (base / "args").exists() else ""
            return result, arguments

    def test_live_release_wins_over_an_old_bundled_target(self):
        result, arguments = self.resolve({"digest": "sha256:" + "b" * 64, "version": "44.20261008.2"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("sha256:" + "b" * 64 + "|44.20261008.2", result.stdout)
        self.assertIn("--command-timeout 30s", arguments)
        self.assertIn("--override-arch arm64", arguments)
        self.assertIn("docker://ghcr.io/moalfarras-sys/moos-arm:latest", arguments)

    def test_network_failure_has_an_explicit_bundled_fallback(self):
        result, _ = self.resolve({}, exit_code=7)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("sha256:" + "a" * 64, result.stdout)
        self.assertIn("bundled signed release", result.stderr)

    def test_invalid_live_metadata_never_silently_installs_the_old_target(self):
        result, _ = self.resolve({"digest": "not-a-digest"})
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("sha256:" + "a" * 64, result.stdout)


class TargetPolicy(unittest.TestCase):
    def probe(self, action, inventory="", code=0, target="", boot_disk="/dev/vda"):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            binary = base / "bin"
            binary.mkdir()
            lsblk = binary / "lsblk"
            lsblk.write_text('#!/bin/sh\n'
                             'if [ "$*" = "-dnpro PKNAME -- /dev/vda2" ]; then\n'
                             '    printf "%s\\n" "$MOOS_TEST_BOOT_DISK"\n'
                             'else\n    printf "%s\\n" "$MOOS_TARGET_TEST_LAYOUT"\nfi\n'
                             'exit "$MOOS_TARGET_TEST_CODE"\n')
            lsblk.chmod(0o755)
            findmnt = binary / "findmnt"
            findmnt.write_text('#!/bin/sh\n[ "$*" = "--noheadings --nofsroot --output SOURCE --mountpoint /boot" ] || exit 1\necho /dev/vda2\n')
            findmnt.chmod(0o755)
            source = SOURCE.read_text()
            functions = source[source.index("pick_target_disk() {"):source.index("resolve_digest() {")]
            helper = base / "probe.sh"
            helper.write_text('set -euo pipefail\nTARGET_DEV="$MOOS_TARGET_TEST_EXPLICIT"\n'
                              'log() { printf "%s\\n" "$*" >&2; }\n' + functions + '\n' + action + '\n')
            env = {**os.environ, "PATH": str(binary) + ":/usr/bin:/bin",
                   "MOOS_TARGET_TEST_LAYOUT": inventory, "MOOS_TARGET_TEST_CODE": str(code),
                   "MOOS_TARGET_TEST_EXPLICIT": target, "MOOS_TEST_BOOT_DISK": boot_disk}
            return subprocess.run(["bash", str(helper)], env=env, capture_output=True, text=True, timeout=5)

    def test_only_two_disk_bundle_can_auto_select_its_second_disk(self):
        installer = dict(name="/dev/vda", type="disk", ro=False, fstype=None, label=None)
        target = dict(installer, name="/dev/vdb")
        seed = dict(installer, name="/dev/vdc", ro=True, fstype="iso9660", label="cidata")
        swap = dict(installer, name="/dev/zram0", fstype="swap")
        def select(disks, boot="/dev/vda"):
            return self.probe("pick_target_disk", json.dumps({"blockdevices": disks}), boot_disk=boot)
        for disks in ([installer, target], [seed, target, swap, installer]):
            result = select(disks)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "/dev/vdb")
        for disks in ([installer], [installer, target, dict(seed, ro=False)],
                      [installer, target, dict(seed, label="other")],
                      [installer, target, dict(seed, fstype=None)],
                      [installer, target, seed, dict(swap, name="/dev/sdc")],
                      [installer, target, seed, dict(swap, fstype=None)],
                      [installer, dict(target, ro=True)]):
            with self.subTest(disks=disks):
                self.assertEqual(select(disks).stdout.strip(), "")
        for boot in ("/dev/vdb", ""):
            self.assertEqual(select([installer, target, seed], boot).stdout.strip(), "")

    def test_invalid_explicit_target_never_falls_back_to_second_disk(self):
        result = self.probe("pick_target_disk", "/dev/vda disk\n/dev/vdb disk", target="/dev/moos-private-nonexistent")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_any_filesystem_or_partition_requires_erase_consent(self):
        for inventory in ("disk ext4", "disk xfs", "disk btrfs", "disk\npart"):
            with self.subTest(inventory=inventory):
                result = self.probe("target_has_data /dev/private-test", inventory)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_empty_and_unreadable_layout_are_distinct(self):
        self.assertEqual(self.probe("target_has_data /dev/private-test", "disk").returncode, 1)
        self.assertEqual(self.probe("target_has_data /dev/private-test", code=7).returncode, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
