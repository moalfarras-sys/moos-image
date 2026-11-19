#!/usr/bin/env python3
"""Gate: the ARM edition asks by name for what x86 inherits, and the image gate proves it.

WHY THIS EXISTS

build_files/verify_desktop_parity.py checks capabilities on the finished image of both
architectures: Arabic RTL detection, pw-dump for the privacy chip, Breeze GTK and gtkconfig for
the look moos-theme selects, the Sonnet spell-check plugin, the ALSA route into PipeWire, and
every applet and pinned status item the MoOS Bar template names, and the kdialog App Drop asks
with. On the A1 (44.20260923.568) all eight capabilities were missing, while the published x86
image (44.20260923.920) had every one.

This test is the source half: both build scripts run the gate, build-arm.sh installs a package
for every capability (x86 gets them from kinoite-main), and the gate is proven to refuse a root
that lacks each one.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build_files"))
import verify_desktop_parity as parity  # noqa: E402

TEMPLATE = ROOT / "system_files" / parity.LAYOUT

# The ARM package that supplies each capability's first path.
ARM_PACKAGE = {
    "usr/bin/lspci": "pciutils",
    "usr/bin/lsusb": "usbutils",
    "usr/bin/node": "nodejs22",
    "usr/bin/npm": "nodejs22-npm",
    "usr/lib64/libatomic.so.1": "libatomic",
    "usr/share/qt6/translations/qtbase_ar.qm": "qt6-qttranslations",
    "usr/bin/pw-dump": "pipewire-utils",
    "usr/share/themes/Breeze/gtk-3.0/gtk.css": "breeze-gtk-gtk3",
    "usr/share/themes/Breeze/gtk-4.0/gtk.css": "breeze-gtk-gtk4",
    "usr/lib64/qt6/plugins/kf6/kded/gtkconfig.so": "kde-gtk-config",
    "usr/lib64/qt6/plugins/kf6/sonnet/sonnet_hunspell.so": "kf6-sonnet-hunspell",
    "usr/share/alsa/alsa.conf.d/99-pipewire-default.conf": "pipewire-alsa",
    "usr/bin/kdialog": "kdialog",
}


def code(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def full_root(tmp: Path, skip: set[str] = frozenset(), extra_applet_missing: str = "") -> Path:
    for _loss, alternatives in parity.CAPABILITIES:
        if alternatives[0] in skip:
            continue
        path = tmp / alternatives[0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
        if alternatives[0] in parity.EXECUTABLE_CAPABILITIES:
            path.chmod(0o755)
    layout = tmp / parity.LAYOUT
    layout.parent.mkdir(parents=True, exist_ok=True)
    layout.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    placed, pinned, loaded = parity.bar_applets(layout.read_text(encoding="utf-8"))
    for plugin in placed + pinned + loaded:
        if plugin == extra_applet_missing:
            continue
        so = tmp / f"usr/lib64/qt6/plugins/plasma/applets/{plugin}.so"
        so.parent.mkdir(parents=True, exist_ok=True)
        so.write_text("x", encoding="utf-8")
    return tmp


class BothBuildsRunIt(unittest.TestCase):
    def test_both_build_scripts_run_the_gate(self):
        for script in ("build.sh", "build-arm.sh"):
            text = code((ROOT / "build_files" / script).read_text(encoding="utf-8"))
            self.assertIn("python3 /ctx/verify_desktop_parity.py --root /", text, script)

    def test_arm_installs_a_package_for_every_capability(self):
        text = code((ROOT / "build_files/build-arm.sh").read_text(encoding="utf-8"))
        firsts = [alternatives[0] for _loss, alternatives in parity.CAPABILITIES]
        self.assertEqual(sorted(firsts), sorted(ARM_PACKAGE), "a capability has no ARM package")
        for path, package in ARM_PACKAGE.items():
            self.assertRegex(text, rf"(?<![\w-]){package}(?![\w-])",
                             f"build-arm.sh never installs {package}, so ARM lacks /{path}")

    def test_both_architectures_qualify_the_store_npm_runtime(self):
        for script in ("build.sh", "build-arm.sh"):
            text = code((ROOT / "build_files" / script).read_text(encoding="utf-8"))
            self.assertIn("python3 /ctx/verify_desktop_parity.py --root / --npm-runtime", text)
            for package in ("nodejs22", "nodejs22-npm"):
                self.assertRegex(text, rf"(?<![\w-]){package}(?![\w-])")

    def test_store_keeps_its_fixed_system_provider(self):
        import ast
        source = ast.parse((ROOT / "system_files/usr/bin/moos-storectl").read_text())
        providers = [ast.literal_eval(node.value) for node in source.body
                     if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == "NPM"
                             for target in node.targets)]
        self.assertEqual(providers, [parity.NPM])


class TheGateReadsTheRealBar(unittest.TestCase):
    def test_the_parser_finds_the_bar_the_template_draws(self):
        placed, pinned, loaded = parity.bar_applets(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(placed[0], "org.moos.brand")
        self.assertIn("org.kde.plasma.systemtray", placed)
        self.assertIn("org.moos.nova.clock", placed)
        self.assertIn("org.kde.plasma.networkmanagement", pinned)
        self.assertIn("org.kde.plasma.volume", pinned)
        self.assertEqual(len(placed), 6)
        self.assertEqual(len(pinned), 4)
        self.assertTrue(set(pinned) <= set(loaded))
        self.assertIn("org.kde.plasma.keyboardindicator", loaded)


class TheGateRefuses(unittest.TestCase):
    def test_a_complete_root_passes(self):
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(parity.problems(full_root(Path(raw))), [])

    def test_each_missing_capability_is_named(self):
        for _loss, alternatives in parity.CAPABILITIES:
            with self.subTest(path=alternatives[0]), tempfile.TemporaryDirectory() as raw:
                found = parity.problems(full_root(Path(raw), skip={alternatives[0]}))
                self.assertEqual(len(found), 1, found)
                self.assertIn(alternatives[0], found[0])

    def test_runtime_and_hardware_providers_must_be_executable_files(self):
        for name in parity.EXECUTABLE_CAPABILITIES:
            with self.subTest(path=name), tempfile.TemporaryDirectory() as raw:
                root = full_root(Path(raw))
                path = root / name
                path.chmod(0o644)
                found = parity.problems(root)
                self.assertEqual(len(found), 1, found)
                self.assertIn(name, found[0])
                path.unlink()
                path.mkdir()
                found = parity.problems(root)
                self.assertEqual(len(found), 1, found)
                self.assertIn(name, found[0])

    def test_old_arm_provider_closure_is_refused(self):
        with tempfile.TemporaryDirectory() as raw:
            found = parity.problems(full_root(Path(raw), skip={"usr/bin/node", "usr/bin/npm"}))
            self.assertEqual(len(found), 2, found)
            self.assertTrue(any("/usr/bin/node" in problem for problem in found))
            self.assertTrue(any("/usr/bin/npm" in problem for problem in found))

    def test_native_runtime_cannot_execute_providers_from_an_alternate_root(self):
        with tempfile.TemporaryDirectory() as raw:
            full_root(Path(raw))
            with self.assertRaises(SystemExit) as refused, \
                    mock.patch.object(parity, "npm_runtime") as runtime:
                parity.main(["--root", raw, "--npm-runtime"])
            self.assertEqual(refused.exception.code, 2)
            runtime.assert_not_called()

    def test_a_bar_applet_the_edition_lacks_is_named(self):
        with tempfile.TemporaryDirectory() as raw:
            found = parity.problems(full_root(Path(raw), extra_applet_missing="org.kde.plasma.volume"))
            self.assertEqual(found, ["the MoOS Bar pins status item org.kde.plasma.volume, "
                                     "which this edition does not ship"])

    def test_unpinned_native_tray_providers_are_required(self):
        for plugin in ("org.kde.plasma.keyboardindicator", "org.kde.kdeconnect", "org.kde.plasma.vault"):
            with self.subTest(plugin=plugin), tempfile.TemporaryDirectory() as raw:
                found = parity.problems(full_root(Path(raw), extra_applet_missing=plugin))
                self.assertEqual(found, [f"the MoOS Bar loads tray applet {plugin}, which this edition does not ship"])

    def test_an_unreadable_load_list_refuses_even_with_visible_pins(self):
        with tempfile.TemporaryDirectory() as raw:
            root = full_root(Path(raw))
            layout = root / parity.LAYOUT
            layout.write_text(layout.read_text().replace('writeConfig("extraItems",', 'writeConfig("missing",'))
            self.assertEqual(parity.problems(root), ["the MoOS Bar template has no readable tray extraItems load list"])

    def test_the_command_fails_on_an_empty_root(self):
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(parity.main(["--root", raw]), 1)


class TheImageNpmRuntimeRefuses(unittest.TestCase):
    def test_missing_or_nonexecutable_provider_refuses_before_any_process(self):
        with tempfile.TemporaryDirectory() as raw:
            provider = Path(raw) / "node"
            for missing in ("NODE", "NPM"):
                for exists in (False, True):
                    if exists:
                        provider.write_text("unusable")
                        provider.chmod(0o644)
                    elif provider.exists():
                        provider.unlink()
                    providers = {"NODE": sys.executable, "NPM": sys.executable,
                                 missing: str(provider)}
                    with self.subTest(provider=missing, exists=exists), \
                            mock.patch.multiple(parity, **providers), \
                            mock.patch.object(parity.subprocess, "run") as process:
                        with self.assertRaisesRegex(RuntimeError, "missing or unusable"):
                            parity.npm_runtime()
                        process.assert_not_called()

    def test_native_command_failures_and_timeout_remain_failures(self):
        failures = (parity.subprocess.CompletedProcess([], 42, "", ""),
                    parity.subprocess.TimeoutExpired("node", 30),
                    FileNotFoundError("missing native loader"))
        for result in failures:
            with self.subTest(result=type(result).__name__), \
                    mock.patch.object(parity, "NODE", sys.executable), \
                    mock.patch.object(parity, "NPM", sys.executable), \
                    mock.patch.object(parity.subprocess, "run") as process:
                if isinstance(result, Exception):
                    process.side_effect = result
                else:
                    process.return_value = result
                with self.assertRaisesRegex(RuntimeError, "Node execution"):
                    parity.npm_runtime()

    def test_offline_lifecycle_uses_private_state_and_preserves_other_prefix_data(self):
        calls = []

        def process(argv, **options):
            calls.append((argv, options))
            prefix = Path(options["cwd"]) / "prefix"
            binary = prefix / "bin/moos-store-runtime-proof"
            if "--eval" in argv:
                output = "MOOS_NODE_OK"
            elif "install" in argv:
                binary.parent.mkdir()
                binary.write_text("fixture")
                binary.chmod(0o755)
                output = ""
            elif "uninstall" in argv:
                binary.unlink()
                output = ""
            else:
                output = "MOOS_NODE_NPM_OK\n"
            return parity.subprocess.CompletedProcess(argv, 0, output, "")

        with mock.patch.object(parity, "NODE", sys.executable), \
                mock.patch.object(parity, "NPM", sys.executable), \
                mock.patch.object(parity.subprocess, "run", side_effect=process), \
                mock.patch.dict(parity.os.environ, {"NODE_OPTIONS": "invalid injected options",
                                                     "npm_config_registry": "https://invalid.example"}):
            parity.npm_runtime()
        self.assertEqual(len(calls), 4)
        for argv, options in calls:
            self.assertEqual(options["env"]["PATH"], "/usr/bin:/bin")
            self.assertNotIn("NODE_OPTIONS", options["env"])
            self.assertNotIn("npm_config_registry", options["env"])
            self.assertEqual(options["timeout"], 30)
            if "install" in argv or "uninstall" in argv:
                for flag in ("--offline", "--ignore-scripts", "--global", "--prefix", "--no-audit"):
                    self.assertIn(flag, argv)

    def test_success_exit_without_node_or_installed_executable_marker_is_refused(self):
        with mock.patch.object(parity, "NODE", sys.executable), \
                mock.patch.object(parity, "NPM", sys.executable), \
                mock.patch.object(parity.subprocess, "run", return_value=
                                  parity.subprocess.CompletedProcess([], 0, "", "")):
            with self.assertRaisesRegex(RuntimeError, "unexpected output"):
                parity.npm_runtime()
        with mock.patch.object(parity, "NODE", sys.executable), \
                mock.patch.object(parity, "NPM", sys.executable), \
                mock.patch.object(parity.subprocess, "run", side_effect=[
                    parity.subprocess.CompletedProcess([], 0, "MOOS_NODE_OK", ""),
                    parity.subprocess.CompletedProcess([], 0, "", "")]):
            with self.assertRaisesRegex(RuntimeError, "did not publish its executable"):
                parity.npm_runtime()


if __name__ == "__main__":
    unittest.main(verbosity=2)
