#!/usr/bin/env python3
"""Recovery must ship and verify the same reviewed Plymouth fix as full ARM.

The old recovery build passed with stock packages and archive names alone.
Source wiring checks retain that refusal. Private roots exercise the unchanged
production verifier: an archive can list the right names and still carry stale
library, script or artwork bytes. No test mounts an image or installs an RPM.
"""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "build_files/verify_plymouth_initramfs.py"
RECOVERY = ROOT / "build_files/build-arm-recovery.sh"
CONTAINER = ROOT / "Containerfile.arm-recovery"
spec = importlib.util.spec_from_file_location(
    "recovery_plymouth_authority", ROOT / "build_files/plymouth_rpms.py")
AUTHORITY = importlib.util.module_from_spec(spec)
spec.loader.exec_module(AUTHORITY)


def stage_commands(text, name):
    marker = "FROM base AS " + name + "\n"
    if marker not in text:
        raise AssertionError("missing native Plymouth producer stage")
    body = text.split(marker, 1)[1].split("\nFROM ", 1)[0]
    return [line for line in body.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


class RecoveryPlymouthWiring(unittest.TestCase):
    def test_native_ci_builds_and_rereads_recovery_before_the_desktop(self):
        workflow = (ROOT / '.github/workflows/build-arm.yml').read_text()
        start = workflow.index('      - name: Build and verify the native recovery image\n')
        end = workflow.index('      - name: Build the image\n', start)
        block = '\n'.join(line for line in workflow[start:end].splitlines()
                          if not line.lstrip().startswith('#'))
        self.assertNotRegex(block, r'(?m)^\s+(?:if|continue-on-error):')
        self.assertIn('podman build --pull=always -f Containerfile.arm-recovery', block)
        self.assertIn("[ \"$(podman inspect --format '{{.Architecture}}' \"$img\")\" = arm64 ]", block)
        self.assertIn('podman run --rm --network=none --read-only', block)
        self.assertIn('python3 /tmp/verify-plymouth.py "$archive"', block)
        self.assertIn('for archive in "${archives[@]}"', block)
        self.assertIn('set -euo pipefail', block)

    def test_recovery_reuses_the_exact_native_arm_producer(self):
        self.assertEqual(
            stage_commands(CONTAINER.read_text(), "plymouth-build"),
            stage_commands((ROOT / "Containerfile.arm").read_text(), "plymouth-build"))

    def test_the_runtime_mount_comes_from_that_producer(self):
        runs = re.findall(r"^RUN(?:[^\n]*\\\n)*[^\n]*", CONTAINER.read_text(), re.M)
        target = [run for run in runs if "bash /usr/libexec/moos-build-arm-recovery.sh" in run]
        self.assertEqual(len(target), 1)
        self.assertIn("--mount=type=bind,from=plymouth-build,source=/out,target=/plymouth-rpms", target[0])

    def test_recovery_installs_then_composes_then_checks_exact_archive_bytes(self):
        code = "\n".join(line for line in RECOVERY.read_text().splitlines()
                         if not line.lstrip().startswith("#"))
        install = "python3 /ctx/plymouth_rpms.py install /plymouth-rpms"
        compose = 'python3 /ctx/compose_arm_initramfs.py "${kver}"'
        verify = 'python3 /ctx/verify_plymouth_initramfs.py "/usr/lib/modules/${kver}/initramfs.img"'
        for command in (install, compose, verify):
            self.assertEqual(code.count(command), 1)
        self.assertLess(code.index('dnf5 -y install'), code.index(install))
        self.assertLess(code.index(install), code.index("plymouth-set-default-theme moos"))
        self.assertLess(code.index(install), code.index(compose))
        self.assertLess(code.index(compose), code.index(verify))
        self.assertLess(code.index(verify), code.index('echo "=== (6) gates ==="'))


class ExactArchiveBytes(unittest.TestCase):
    def verify(self, *, changed=None, missing=None, root_library=None,
               package_version=None, receipt=True):
        real_path = Path
        with tempfile.TemporaryDirectory(prefix="moos-recovery-plymouth-") as temporary:
            root = real_path(temporary)
            library = "usr/lib64/libply-splash-core.so.5.0.0"
            payload = b"reviewed native Plymouth library fixture"
            installed = {library: payload if root_library is None else root_library}
            script = (ROOT / "system_files/usr/share/plymouth/themes/moos/moos.script").read_bytes()
            names = set(re.findall(rb'Image\("([^"\n]+)"\)', script))
            self.assertTrue(names, "the production script must declare its real assets")
            prefix = "usr/share/plymouth/themes/moos/"
            for name in names | {b"moos.script", b"moos.plymouth", b"logo.png"}:
                self.assertEqual(real_path(name.decode()).name, name.decode())
                installed[prefix + name.decode()] = script if name == b"moos.script" else b"asset:" + name
            for name, body in installed.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
            record = {"schema": 1, "fixed": AUTHORITY.FIXED,
                      "library_sha256": hashlib.sha256(payload).hexdigest(),
                      "packages": ["plymouth-core-libs", "plymouth-plugin-script"]}
            if receipt:
                target = root / "usr/share/moos/plymouth-frame-lifetime.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(record))
            archive = dict(installed)
            if changed:
                archive.update(changed)
            if missing:
                archive.pop(missing)
            self.last_listing = "\n".join(sorted(archive))

            def mapped_path(value):
                return root / str(value).lstrip("/") if str(value).startswith("/") else real_path(value)

            def rpm(argv, **kwargs):
                self.assertEqual(argv[:4], ["rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}"])
                self.assertIn(argv[4], record["packages"])
                return package_version or AUTHORITY.FIXED

            def extract(argv, **kwargs):
                self.assertEqual(argv[:2], ["lsinitrd", "-f"])
                self.assertEqual(argv[3], "/private/fixture-initramfs.img")
                self.assertTrue(kwargs.get("check"))
                return subprocess.CompletedProcess(argv, 0, archive.get(argv[2], b""), b"")

            with patch("pathlib.Path", side_effect=mapped_path), \
                 patch("subprocess.check_output", side_effect=rpm), \
                 patch("subprocess.run", side_effect=extract), \
                 patch.object(sys, "argv", [str(VERIFY), "/private/fixture-initramfs.img"]), \
                 redirect_stdout(io.StringIO()) as output:
                runpy.run_path(str(VERIFY), run_name="recovery_archive_fixture")
            self.assertIn("package, root, boot library and theme bytes agree", output.getvalue())

    def test_exact_fixed_root_and_archive_pass(self):
        self.verify()

    def test_same_archive_names_cannot_hide_a_stale_library(self):
        library = "usr/lib64/libply-splash-core.so.5.0.0"
        with self.assertRaisesRegex(AssertionError, "fixed Plymouth library"):
            self.verify(changed={library: b"stock or stale library"})
        self.assertIn(library, self.last_listing)

    def test_same_archive_names_cannot_hide_old_script_or_artwork(self):
        prefix = "usr/share/plymouth/themes/moos/"
        for name in ("moos.script", "moos.plymouth", "intro1.png"):
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, "boot asset"):
                self.verify(changed={prefix + name: b"stale bytes with the same filename"})
            self.assertIn(prefix + name, self.last_listing)

    def test_missing_archive_asset_is_refused(self):
        with self.assertRaisesRegex(AssertionError, "boot asset"):
            self.verify(missing="usr/share/plymouth/themes/moos/intro1.png")

    def test_fixed_receipt_cannot_admit_stock_root_or_package(self):
        with self.assertRaises(AssertionError):
            self.verify(root_library=b"unreviewed library")
        with self.assertRaisesRegex(AssertionError, "unfixed Plymouth package"):
            self.verify(package_version=AUTHORITY.BASE)

    def test_missing_fixed_receipt_is_refused(self):
        with self.assertRaises(FileNotFoundError):
            self.verify(receipt=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
