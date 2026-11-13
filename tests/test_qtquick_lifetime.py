#!/usr/bin/env python3
"""Refuse unreviewed Qt packages and false-green native teardown evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "build_files/qtquick"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rpm = load("qtquick_rpms", SOURCE / "rpms.py")
native = load("qtquick_native", SOURCE / "native-proof.py")


class NativeEvidence(unittest.TestCase):
    def result(self, code=0, marker=True, library="/private/libQt6Quick.so.6.11.2"):
        text = "MOOS_QT_LIBRARY " + library + "\n"
        if marker:
            text += "MOOS_QT_TEARDOWN_NATIVE_EXECUTED true\n"
        return subprocess.CompletedProcess([], code, "", text)

    def test_real_completion_requires_loaded_library_and_executed_marker(self):
        self.assertTrue(native.validate(self.result(), Path("/private/libQt6Quick.so.6.11.2"),
                                        "pass")["destruction_executed"])
        for result in (self.result(marker=False), self.result(code=7),
                       self.result(library="/usr/lib64/libQt6Quick.so.6.11.2")):
            with self.subTest(result=result), self.assertRaises(ValueError):
                native.validate(result, Path("/private/libQt6Quick.so.6.11.2"), "pass")

    def test_old_control_requires_actual_sigsegv_without_success(self):
        path = Path("/private/libQt6Quick.so.6.11.2")
        self.assertEqual(native.validate(self.result(-11, False), path, "crash")["exit"], -11)
        for code, marker in ((0, False), (0, True), (-6, False), (-11, True), (139, False)):
            with self.subTest(code=code, marker=marker), self.assertRaises(ValueError):
                native.validate(self.result(code, marker), path, "crash")

    def test_duplicate_library_or_success_marker_is_not_accepted(self):
        for extra in ("MOOS_QT_LIBRARY /private/libQt6Quick.so.6.11.2\n",
                      "MOOS_QT_TEARDOWN_NATIVE_EXECUTED true\n"):
            result = self.result()
            result.stderr += extra
            with self.assertRaises(ValueError):
                native.validate(result, Path("/private/libQt6Quick.so.6.11.2"), "pass")


class PackageAdmission(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.data = rpm.review("6.11.2-3.fc44")
        self.manifest = {**self.data, "arch": "x86_64", "packages": [],
                         "quick_sha256": "a" * 64,
                         "native_proof": {"exit": 0, "destruction_executed": True}}
        for name in sorted(rpm.PACKAGES):
            path = self.folder / (name + ".rpm")
            path.write_text(name)
            self.manifest["packages"].append({"name": name, "file": path.name,
                                               "sha256": rpm.sha(path)})
        for file, key in (("teardown-probe", "probe_sha256"), ("teardown.qml", "qml_sha256")):
            path = self.folder / file
            path.write_text(file)
            self.manifest[key] = rpm.sha(path)

    def validate(self, document=None, metadata=None):
        (self.folder / "manifest.json").write_text(json.dumps(document or self.manifest))
        def info(path):
            return [path.stem, self.data["fixed"], "x86_64",
                    "qt6-qtdeclarative-" + self.data["fixed"] + ".src.rpm"]
        with patch.object(rpm, "architecture", return_value="x86_64"), \
             patch.object(rpm, "owned_packages", return_value={rpm.NAME: []}), \
             patch.object(rpm, "metadata", side_effect=metadata or info), \
             patch.object(rpm, "package_payload", return_value="a" * 64):
            return rpm.validate_manifest(self.folder)

    def test_selects_only_already_installed_runtime(self):
        _, _, selected = self.validate()
        self.assertEqual(set(selected), {rpm.NAME})

    def test_source_architecture_payload_and_execution_drift_refuse(self):
        changes = {"base": "6.12.0-1.fc44", "arch": "aarch64", "source_sha256": "b" * 64,
                   "quick_sha256": "c" * 64,
                   "native_proof": {"exit": 0, "destruction_executed": False}}
        for key, value in changes.items():
            document = copy.deepcopy(self.manifest)
            document[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(document)

    def test_incomplete_duplicate_unknown_and_traversing_rpms_refuse(self):
        for mode in ("missing", "duplicate", "unknown", "traversal"):
            document = copy.deepcopy(self.manifest)
            if mode == "missing":
                document["packages"].pop()
            elif mode == "duplicate":
                document["packages"].append(document["packages"][0])
            elif mode == "unknown":
                document["packages"][0]["name"] = "kernel"
            else:
                document["packages"][0]["file"] = "../outside.rpm"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.validate(document)

    def test_linked_and_changed_rpm_bytes_refuse(self):
        item = self.manifest["packages"][0]
        path = self.folder / item["file"]
        path.write_text("changed")
        with self.assertRaises(ValueError):
            self.validate()
        destination = self.folder / "other"
        path.rename(destination)
        path.symlink_to(destination)
        with self.assertRaises(ValueError):
            self.validate()

    def test_wrong_rpm_native_metadata_refuses(self):
        with self.assertRaises(ValueError):
            self.validate(metadata=lambda path: [path.stem, self.data["fixed"], "aarch64", "bad.src.rpm"])

    def test_unknown_installed_base_is_not_downgraded(self):
        # -2 remains a reviewed transaction input, never the new SDK/source.
        for value in ("6.11.2-2.fc44", "6.11.2-4.fc44", "6.12.0-1.fc44", "", self.data["fixed"]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                rpm.review(value)

    def test_exact_old_and_current_vendor_inputs_upgrade_without_mixed_packages(self):
        def row(name, version, arch="x86_64", source=None):
            return f"{name} {version} {arch} {source or 'qt6-qtdeclarative-' + version + '.src.rpm'}"
        for version in ("6.11.2-2.fc44", "6.11.2-3.fc44"):
            rows = "\n".join(row(name, version) for name in (rpm.NAME, rpm.NAME + "-devel"))
            with self.subTest(version=version), patch.object(rpm, "command", return_value=rows):
                owned = rpm.owned_packages(self.data, "x86_64")
                self.assertEqual({value[1] for value in owned.values()}, {version})
        base = row(rpm.NAME, "6.11.2-3.fc44")
        refused = (
            row(rpm.NAME, "6.11.2-4.fc44"),
            row(rpm.NAME, "6.12.0-1.fc44"),
            row(rpm.NAME, "6.11.2-2.1.moos1.fc44"),
            row(rpm.NAME, self.data["fixed"]),
            row(rpm.NAME, "6.11.2-3.fc44", "i686"),
            row(rpm.NAME, "6.11.2-3.fc44", source="unknown.src.rpm"),
            base + "\n" + row(rpm.NAME + "-devel", "6.11.2-2.fc44"),
            base + "\n" + row(rpm.NAME, "6.11.2-3.fc44", "i686"),
            base + "\n" + base,
            row(rpm.NAME + "-devel", "6.11.2-3.fc44"),
        )
        for rows in refused:
            with self.subTest(rows=rows), patch.object(rpm, "command", return_value=rows):
                with self.assertRaises(ValueError):
                    rpm.owned_packages(self.data, "x86_64")

    def test_prepared_source_keeps_both_independent_teardown_repairs(self):
        def digest(path):
            return self.data["fixed_itemview_sha256" if path == rpm.ITEMVIEW else "fixed_pixmap_sha256"]
        with patch.object(rpm, "sha", side_effect=digest):
            rpm.prepared()
        for missing in (rpm.ITEMVIEW, rpm.PIXMAP):
            with self.subTest(missing=missing), patch.object(
                    rpm, "sha", side_effect=lambda path: "0" * 64 if path == missing else digest(path)):
                with self.assertRaises(ValueError):
                    rpm.prepared()

    def test_native_probe_requires_exact_development_headers(self):
        def available(argv):
            if argv[:2] == ["rpm", "--eval"]:
                return "x86_64"
            return "6.11.2" if argv[0] == "pkg-config" else "6.11.2-3.fc44 x86_64"
        with patch.object(rpm, "command", side_effect=available):
            rpm.sdk("6.11.2-3.fc44")
        for missing in ("qt6-qtdeclarative-devel", "Qt6Quick"):
            def refusal(argv):
                if missing in argv:
                    raise subprocess.CalledProcessError(1, argv)
                return available(argv)
            with self.subTest(missing=missing), patch.object(rpm, "command", side_effect=refusal):
                with self.assertRaises(subprocess.CalledProcessError):
                    rpm.sdk("6.11.2-3.fc44")
        with patch.object(rpm, "command", return_value="6.12.0-1.fc44"):
            with self.assertRaises(ValueError):
                rpm.sdk("6.11.2-3.fc44")
        for runtime in ("6.11.2-2.fc44 x86_64", "6.11.2-3.fc44 i686",
                        "6.11.2-3.fc44 x86_64\n6.11.2-3.fc44 i686"):
            with self.subTest(runtime=runtime), patch.object(
                    rpm, "command", side_effect=lambda argv: runtime if argv[-1] == rpm.NAME else available(argv)):
                with self.assertRaises(ValueError):
                    rpm.sdk("6.11.2-3.fc44")
        for filename in ("Containerfile", "Containerfile.arm"):
            stage = (ROOT / filename).read_text().split("FROM base AS qtquick-build\n", 1)[1].split("\nFROM ", 1)[0]
            self.assertIn("qt6-qtdeclarative-devel", stage.split("RUN bash", 1)[0])

    def test_build_requires_native_old_and_packaged_fixed_proofs(self):
        script = (SOURCE / "build.sh").read_text()
        self.assertIn("rpmkeys --checksig --verbose", script)
        self.assertIn("--expect crash", script)
        self.assertIn("rpmbuild -bb", script)
        for name in ("Containerfile", "Containerfile.arm"):
            text = (ROOT / name).read_text()
            self.assertIn("FROM base AS qtquick-build", text)
            self.assertIn("from=qtquick-build,source=/out/qtquick,target=/qtquick-rpms", text)
        for name in ("build.sh", "build-arm.sh"):
            self.assertIn("python3 /ctx/qtquick/rpms.py verify", (ROOT / "build_files" / name).read_text())


if __name__ == "__main__":
    unittest.main()
