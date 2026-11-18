#!/usr/bin/env python3
"""Client-side window buttons follow the live MoOS frame.

Runs the real generator and the real moos-theme shell functions against a
private XDG_CONFIG_HOME; never the owner's GTK files, KWin config or bus.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "system_files/usr/bin/moos-theme"
CONTROLS = ROOT / "system_files/usr/share/moos/window-controls"
AURORAE = ROOT / "system_files/usr/share/aurorae/themes"
GENERATOR = ROOT / "artwork/generate_moos_window_controls.py"
IMPORT = "@import 'moos-window-controls.css';"
BASH = shutil.which("bash") or "/bin/bash"


def functions(source: str) -> str:
    start = source.index("window_controls_source() {")
    end = source.index("\napply_supplements() {")
    return source[start:end]


class Generated(unittest.TestCase):
    def test_generator_matches_committed_assets(self):
        result = subprocess.run([sys.executable, str(GENERATOR), "--check"],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_moos_frame_has_complete_parseable_controls(self):
        frames = sorted(p.name for p in AURORAE.iterdir() if re.fullmatch(r"MoOSUI2[A-Za-z0-9]*", p.name))
        self.assertGreaterEqual(len(frames), 18)
        self.assertEqual(sorted(p.name for p in CONTROLS.iterdir()), frames)
        for frame in frames:
            directory = CONTROLS / frame
            svgs = sorted(directory.glob("*.svg"))
            self.assertEqual(len(svgs), 4 * 8, frame)
            for svg in svgs:
                root = ET.parse(svg).getroot()
                self.assertEqual(root.get("width"), "24", svg)
                self.assertNotIn("href", svg.read_text(), svg)
            css = (directory / "window-controls.css").read_text()
            for url in re.findall(r'url\("([^"]+)"\)', css):
                self.assertTrue(url.startswith(f"moos-window-controls/{frame}/"), url)
                self.assertTrue((directory / url.rsplit("/", 1)[1]).is_file(), url)
            # GTK3 titlebuttons, GTK4/libadwaita windowcontrols and maximized restore.
            for selector in ("headerbar button.titlebutton.close:backdrop",
                             "windowcontrols > button.minimize:hover",
                             "window.maximized windowcontrols > button.maximize"):
                self.assertIn(selector, css, frame)

    def test_states_keep_the_frames_semantic_colours(self):
        bloom = (CONTROLS / "MoOSUI2Bloom/close-hover.svg").read_text()
        self.assertIn("#F36D75", bloom.upper())
        aurorae = (AURORAE / "MoOSUI2Bloom/close.svg").read_text()
        self.assertIn('id="hover-center"', aurorae)


class Installed(unittest.TestCase):
    def run_owner(self, *, frame: str | None, library="org.kde.kwin.aurorae.v2",
                  gtk3: str | None = "@import 'colors.css';\n.personal { color: red; }\n",
                  gtk4: str | None = "@import 'colors.css';@import 'moos-ui2.css';\n",
                  source_change=None, operation="apply", runs=1, inspect=None):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            config = base / "config"
            for gtk, text in (("gtk-3.0", gtk3), ("gtk-4.0", gtk4)):
                (config / gtk).mkdir(parents=True)
                if text is not None:
                    (config / gtk / "gtk.css").write_text(text)
            (base / "bin").mkdir()
            reader = base / "bin/kreadconfig6"
            reader.write_text("#!/bin/sh\ncase \"$*\" in\n"
                              f"  *--key\\ library*) printf '%s\\n' {library!r} ;;\n"
                              f"  *--key\\ theme*) printf '%s\\n' {('__aurorae__svg__' + frame) if frame else 'Breeze'!r} ;;\n"
                              "esac\n")
            reader.chmod(0o700)
            body = functions(THEME.read_text())
            if source_change:
                body = source_change(body)
            driver = base / "driver.sh"
            driver.write_text("set -u\n" + body + "\n"
                              + 'for _ in $(seq 1 "$RUNS"); do\n'
                              + '  if [ "$OPERATION" = apply ]; then apply_window_controls || exit 3;\n'
                              + '  else window_controls_complete || exit 4; fi\n'
                              + 'done\n')
            env = dict(os.environ, XDG_CONFIG_HOME=str(config), HOME=str(base),
                       MOOS_WINDOW_CONTROLS_DIR=str(CONTROLS), RUNS=str(runs), OPERATION=operation,
                       PATH=str(base / "bin") + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"))
            result = subprocess.run([BASH, str(driver)], env=env, capture_output=True,
                                    text=True, timeout=60)
            files = {str(p.relative_to(config)): p.read_bytes()
                     for p in sorted(config.rglob("*")) if p.is_file()}
            extra = inspect(config, env, driver) if inspect else None
            return result, files, extra

    def test_moos_frame_installs_both_gtk_generations_first_and_preserves_personal_css(self):
        result, files, _ = self.run_owner(frame="MoOSUI2Bloom")
        self.assertEqual(result.returncode, 0, result.stderr)
        for gtk in ("gtk-3.0", "gtk-4.0"):
            css = files[f"{gtk}/gtk.css"].decode()
            self.assertTrue(css.startswith(IMPORT + "\n"), css)
            self.assertEqual(css.count(IMPORT), 1)
            self.assertEqual(files[f"{gtk}/moos-window-controls.css"],
                             (CONTROLS / "MoOSUI2Bloom/window-controls.css").read_bytes())
            for svg in (CONTROLS / "MoOSUI2Bloom").glob("*.svg"):
                self.assertEqual(files[f"{gtk}/moos-window-controls/MoOSUI2Bloom/{svg.name}"],
                                 svg.read_bytes())
        self.assertIn(".personal { color: red; }", files["gtk-3.0/gtk.css"].decode())
        self.assertIn("@import 'moos-ui2.css';", files["gtk-4.0/gtk.css"].decode())

    def test_missing_gtk_css_is_created_and_repeated_runs_change_nothing(self):
        def second(config, env, driver):
            before = {p: p.read_bytes() for p in config.rglob("*") if p.is_file()}
            again = subprocess.run([BASH, str(driver)], env=env, capture_output=True, text=True, timeout=60)
            after = {p: p.read_bytes() for p in config.rglob("*") if p.is_file()}
            return again.returncode, before == after
        result, files, (code, unchanged) = self.run_owner(frame="MoOSUI2Aurora", gtk3=None, gtk4=None,
                                                          inspect=second)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(files["gtk-3.0/gtk.css"].decode(), IMPORT + "\n")
        self.assertEqual((code, unchanged), (0, True))

    def test_switching_frames_replaces_the_stylesheet_and_keeps_older_assets(self):
        def switch(config, env, driver):
            reader = Path(env["PATH"].split(os.pathsep)[0]) / "kreadconfig6"
            reader.write_text(reader.read_text().replace("MoOSUI2Bloom", "MoOSUI2AuroraLight"))
            again = subprocess.run([BASH, str(driver)], env=env, capture_output=True, text=True, timeout=60)
            return again.returncode, {str(p.relative_to(config)) for p in config.rglob("*") if p.is_file()}, \
                (config / "gtk-4.0/moos-window-controls.css").read_text()
        result, _, (code, names, css) = self.run_owner(frame="MoOSUI2Bloom", inspect=switch)
        self.assertEqual((result.returncode, code), (0, 0))
        self.assertIn("moos-window-controls/MoOSUI2AuroraLight/close-active.svg", css)
        self.assertNotIn("MoOSUI2Bloom/", css)
        self.assertIn("gtk-4.0/moos-window-controls/MoOSUI2Bloom/close-active.svg", names)

    def test_other_decorations_remove_only_the_moos_import_and_stylesheet(self):
        def to_breeze(config, env, driver):
            reader = Path(env["PATH"].split(os.pathsep)[0]) / "kreadconfig6"
            reader.write_text(reader.read_text().replace("org.kde.kwin.aurorae.v2", "org.kde.breeze"))
            again = subprocess.run([BASH, str(driver)], env=env, capture_output=True, text=True, timeout=60)
            check = subprocess.run([BASH, str(driver)], env=dict(env, OPERATION="check"),
                                   capture_output=True, text=True, timeout=60)
            return again.returncode, check.returncode, (config / "gtk-3.0/gtk.css").read_text(), \
                (config / "gtk-3.0/moos-window-controls.css").exists(), \
                (config / "gtk-3.0/moos-window-controls/MoOSUI2Bloom").is_dir()
        result, _, (code, check, css, stylesheet, assets) = self.run_owner(frame="MoOSUI2Bloom", inspect=to_breeze)
        self.assertEqual((result.returncode, code, check), (0, 0, 0))
        self.assertEqual(css, "@import 'colors.css';\n.personal { color: red; }\n")
        self.assertFalse(stylesheet)
        self.assertTrue(assets, "a restored older gtk.css must never import blank buttons")

    def test_unknown_or_traversing_frames_are_not_installed(self):
        for frame in ("MoOSUI2../../etc", "Breeze", "MoOSUI2Missing"):
            result, files, _ = self.run_owner(frame=frame)
            self.assertEqual(result.returncode, 0, (frame, result.stderr))
            self.assertNotIn(IMPORT, files["gtk-3.0/gtk.css"].decode(), frame)
            self.assertFalse(any("moos-window-controls/" in name for name in files), frame)

    def test_completeness_refuses_a_missing_import_or_changed_asset(self):
        def tamper(config, env, driver):
            check = lambda: subprocess.run([BASH, str(driver)], env=dict(env, OPERATION="check"),
                                           capture_output=True, text=True, timeout=60).returncode
            healthy = check()
            asset = config / "gtk-4.0/moos-window-controls/MoOSUI2Bloom/close-active.svg"
            asset.write_text("<svg/>")
            changed = check()
            subprocess.run([BASH, str(driver)], env=env, check=True, timeout=60)
            css = config / "gtk-3.0/gtk.css"
            css.write_text(css.read_text().replace(IMPORT + "\n", ""))
            unimported = check()
            return healthy, changed, unimported
        _, _, codes = self.run_owner(frame="MoOSUI2Bloom", inspect=tamper)
        self.assertEqual(codes, (0, 4, 4))

    def test_kde_gtk3_bridge_images_are_replaced_and_other_assets_kept(self):
        def seed_and_run(config, env, driver):
            assets = config / "gtk-3.0/assets"
            empty = "<svg viewBox='0 0 50 50'/>"
            for name in ("close-normal", "maximized-backdrop-hover", "minimize-active"):
                (assets / f"{name}.svg").write_text(empty)
            (assets / "arrow-down.png").write_bytes(b"gtkconfig-owned")
            again = subprocess.run([BASH, str(driver)], env=env, capture_output=True, text=True, timeout=60)
            return again.returncode, {p.name: p.read_bytes() for p in assets.iterdir()}
        result, _, (code, assets) = self.run_owner(frame="MoOSUI2Bloom", inspect=seed_and_run)
        self.assertEqual((result.returncode, code), (0, 0))
        source = CONTROLS / "MoOSUI2Bloom"
        mapping = {"normal": "active", "hover": "hover", "active": "pressed",
                   "backdrop-normal": "inactive", "backdrop-hover": "hover-inactive",
                   "backdrop-active": "pressed-inactive"}
        for button, image in (("close", "close"), ("minimize", "minimize"),
                              ("maximize", "maximize"), ("maximized", "restore")):
            for kde, state in mapping.items():
                self.assertEqual(assets[f"{button}-{kde}.svg"],
                                 (source / f"{image}-{state}.svg").read_bytes(), (button, kde))
        self.assertEqual(assets["arrow-down.png"], b"gtkconfig-owned")
        self.assertEqual(len([n for n in assets if n.endswith(".svg")]), 24)

    def test_other_frames_leave_gtkconfig_bridge_images_alone(self):
        def seed(config, env, driver):
            assets = config / "gtk-3.0/assets"; assets.mkdir(exist_ok=True)
            (assets / "close-normal.svg").write_text("breeze-rendered")
            reader = Path(env["PATH"].split(os.pathsep)[0]) / "kreadconfig6"
            reader.write_text(reader.read_text().replace("org.kde.kwin.aurorae.v2", "org.kde.breeze"))
            subprocess.run([BASH, str(driver)], env=env, check=True, timeout=60)
            return (assets / "close-normal.svg").read_text()
        _, _, image = self.run_owner(frame="MoOSUI2Bloom", gtk3=None, inspect=seed)
        # gtkconfig's own Breeze rendering is kept once the frame is not MoOS.
        self.assertEqual(image, "breeze-rendered")
        result, files, _ = self.run_owner(frame=None, library="org.kde.breeze")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(any(name.startswith("gtk-3.0/assets/") for name in files))

    def test_completeness_refuses_an_emptied_bridge_image(self):
        def empty_again(config, env, driver):
            (config / "gtk-3.0/assets/minimize-hover.svg").write_text("<svg/>")
            return subprocess.run([BASH, str(driver)], env=dict(env, OPERATION="check"),
                                  capture_output=True, text=True, timeout=60).returncode
        _, _, code = self.run_owner(frame="MoOSUI2Bloom", inspect=empty_again)
        self.assertEqual(code, 4)

    def test_old_owner_without_installation_is_refused_by_this_test(self):
        # Negative control: the previous owner wrote nothing for CSD buttons.
        result, files, _ = self.run_owner(
            frame="MoOSUI2Bloom",
            source_change=lambda s: s.replace("apply_window_controls() {\n",
                                              "apply_window_controls() {\n    return 0\n", 1))
        self.assertEqual(result.returncode, 0)
        self.assertNotIn(IMPORT, files["gtk-3.0/gtk.css"].decode())


class Wired(unittest.TestCase):
    def test_guard_supplements_checks_and_snapshots_own_the_files(self):
        source = THEME.read_text()
        guard = source[source.index("guard_theme_defaults() {"):]
        guard = guard[:guard.index("\n}\n")]
        self.assertIn("apply_window_controls || return 1", guard)
        self.assertIn('apply_window_controls "$deco" || supplement_failed=1', source)
        self.assertIn('window_controls_complete "$deco" || return 1', source)
        reconcile = source[source.index("\nreconcile() {"):]
        reconcile = reconcile[:reconcile.index("    lnf=\"$(current)\"")]
        self.assertIn("apply_window_controls ||", reconcile)
        watcher = (ROOT / "system_files/usr/lib/systemd/user/moos-theme-sync.path").read_text()
        self.assertIn("PathChanged=%h/.config/gtk-3.0/window_decorations.css", watcher)
        for name in ("gtk3-css", "gtk3-window-controls", "gtk4-window-controls"):
            self.assertEqual(source.count(f'_config_file "$snapshot" {name} '), 2, name)


if __name__ == "__main__":
    unittest.main()
