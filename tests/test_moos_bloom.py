#!/usr/bin/env python3
"""Native Bloom finish: complete profiles, rendered actions and original art.

All executing theme fixtures have private paths and an unreachable desktop bus.
Qt rendering is optional only on the SDK-free repository worker.
"""
from __future__ import annotations

import configparser
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SHARE = ROOT / "system_files/usr/share"
GENERATOR = ROOT / "artwork/generate_moos_bloom.py"
PROFILES = json.loads((ROOT / "artwork/moos-design/theme-profiles.json").read_text())["profiles"]
BLOOM = [p for p in PROFILES if p["family"] == "bloom"]
WALLPAPER_MAP = ROOT/'system_files/usr/lib64/qt6/qml/org/moos/ui/WallpaperSources.js'
spec = importlib.util.spec_from_file_location("bloom_gate", GENERATOR)
bloom = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bloom)
try:
    from PySide6.QtCore import QCoreApplication, QRectF
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtQml import QJSEngine
    QT = True
except ImportError:
    QT = False


def parser(path):
    value = configparser.ConfigParser(interpolation=None)
    value.optionxform = str
    value.read(path)
    return value


def function(text, name):
    return re.search(r"(?ms)^"+re.escape(name)+r"\(\) \{.*?^\}$", text).group()


def contrast_pairs(svg):
    ratios = []
    for group in ET.fromstring(svg):
        if group.get("id", "").startswith("deactivated"):
            continue
        circle = next(e for e in group.iter() if e.tag.endswith("circle"))
        glyph = list(list(group)[1])[1]
        inks = {e.get("fill") for e in glyph.iter() if e.get("fill")}
        ratios.extend(bloom.contrast(ink, circle.get("fill")) for ink in inks)
    if not ratios or min(ratios) < 4.5:
        raise ValueError("unreadable Bloom action")
    return ratios


class BloomTests(unittest.TestCase):
    def test_live_diagnostics_execute_registered_profiles_and_refuse_unknown(self):
        for path, variable, end, fields in (
            (ROOT/'system_files/usr/bin/moos-selfcheck', 'lnf', '\n\nif [ -z "$want_deco" ]; then',
             ('want_deco', 'want_sch', 'want_ico', 'want_sty', 'want_wall', 'pair_dark', 'pair_light')),
            (ROOT/'tests/post-update-check.sh', 'theme_lnf', '\n\nif [ -n "$theme_family" ]; then',
             ('want_deco', 'want_scheme', 'want_icons', 'want_style', 'want_wallpaper', 'pair_dark', 'pair_light')),
        ):
            source = path.read_text().split('case "$'+variable+'" in', 1)[1].split(end, 1)[0]
            body = 'case "$'+variable+'" in'+source
            def read(theme, code=body):
                script = variable+'=$1\nbad() { :; }\n'+code+'\nprintf "%s\\n" '+ ' '.join('"${'+f+':-}"' for f in fields)
                p = subprocess.run(['bash', '-c', script, 'profile-check', theme], capture_output=True, text=True, check=True)
                return p.stdout.splitlines()
            for profile in PROFILES:
                with self.subTest(checker=path.name, theme=profile['id']):
                    dark = profile['id'].removesuffix('.light')
                    self.assertEqual(read(profile['id']), ['__aurorae__svg__'+profile['decoration'],
                        profile['scheme'], profile['icons'], profile['style'], profile['wallpaper'], dark, dark+'.light'])
            for invalid in ('org.moos.ui2.bloom.unknown', 'org.moos.ui2.unknown', 'org.kde.breeze.desktop', ''):
                self.assertEqual(read(invalid), ['']*len(fields))
            # Restore the actual omitted pair in a private control. Its two
            # healthy profiles must again be refused by the executed parser.
            old = body.replace('    org.moos.ui2.bloom|org.moos.ui2.bloom.light|\\\n', '', 1)
            self.assertNotEqual(old, body)
            self.assertEqual(read('org.moos.ui2.bloom.light', old), ['']*len(fields))

    def test_complete_native_pairs_preserve_existing_profiles_and_engine(self):
        old = {"org.moos.ui2"+suffix for suffix in ("", ".light")}
        old |= {"org.moos.ui2."+name+suffix for name in
                ("nova", "amethyst", "midnight", "aurora", "gaming", "dev", "study")
                for suffix in ("", ".light")}
        self.assertEqual({p["id"] for p in PROFILES}, old | {"org.moos.ui2.bloom", "org.moos.ui2.bloom.light"})
        engines = json.loads((ROOT / "artwork/moos-design/theme-profiles.json").read_text())["engines"]
        self.assertEqual(engines, {"qtWidgetStyle": "Breeze", "gtkTheme": "Breeze"})
        self.assertEqual({p["mode"] for p in BLOOM}, {"dark", "light"})
        for profile in BLOOM:
            with self.subTest(profile=profile["id"]):
                self.assertEqual(profile["icons"], profile["style"])
                self.assertEqual(profile["scheme"], profile["style"])
                defaults = parser(SHARE / "plasma/look-and-feel" / profile["id"] / "contents/defaults")
                self.assertEqual(defaults["kdeglobals][KDE"]["widgetStyle"], "Breeze")
                self.assertEqual(defaults["ksplashrc][KSplash"]["Engine"], "None")
                self.assertEqual(defaults["Wallpaper"]["Image"], profile["wallpaper"])
                self.assertEqual(defaults["kdeglobals][Icons"]["Theme"], profile["icons"])
                self.assertEqual(defaults["kwinrc][org.kde.kdecoration2"]["theme"], "__aurorae__svg__"+profile["decoration"])
                self.assertFalse(any(s.startswith("kwinrc][") and s != "kwinrc][org.kde.kdecoration2" for s in defaults))
                icons = SHARE / "icons" / profile["icons"]
                self.assertEqual((icons / "places/scalable/inode-directory.svg").read_bytes(),
                                 (icons / "places/scalable/folder.svg").read_bytes())
                self.assertTrue((icons / "moos/actions/scalable").is_dir())
                parent = SHARE / "icons" / ("MoOSUI2AmethystLight" if profile["mode"] == "light" else "MoOSUI2Amethyst")
                for category in ("actions", "apps"):
                    originals = {f.name: f.read_bytes() for f in (parent / "moos" / category / "scalable").glob("*.svg")}
                    derived = {f.name: f.read_bytes() for f in (icons / "moos" / category / "scalable").glob("*.svg")}
                    self.assertEqual(derived, originals, "Bloom must retain the gated parent glyph geometry and palette")
                metadata = json.loads((SHARE / "plasma/desktoptheme" / profile["style"] / "metadata.json").read_text())
                self.assertEqual(metadata["KPlugin"]["Id"], profile["style"])

    def test_native_window_targets_and_paired_ink(self):
        for profile in BLOOM:
            frame = SHARE / "aurorae/themes" / profile["decoration"]
            rc = parser(frame / (profile["decoration"]+"rc"))
            for key in ("TitleHeight", "ButtonHeight", "ButtonWidth"):
                self.assertEqual(rc["Layout"][key], "44")
            ids = {e.get("id") for e in ET.parse(frame / "decoration.svg").getroot().iter()}
            for prefix in ("decoration", "decoration-inactive", "decoration-opaque", "decoration-opaque-inactive"):
                self.assertTrue({prefix+'-'+p for p in bloom.glyphs.FRAME_POSITIONS}.issubset(ids))
            for prefix in ("decoration-maximized", "decoration-maximized-inactive", "decoration-maximized-opaque", "decoration-maximized-opaque-inactive"):
                self.assertIn(prefix+"-center", ids)
            for action in bloom.glyphs.BUTTONS:
                svg = (frame / (action+".svg")).read_text()
                with self.subTest(profile=profile["id"], action=action):
                    self.assertEqual({e.get("id") for e in ET.fromstring(svg) if e.get("id")},
                                     {s+"-center" for s in bloom.glyphs.BUTTON_STATES})
                    self.assertGreaterEqual(min(contrast_pairs(svg)), 4.5)
                    # Restored old same-colour ink must fail the identical predicate.
                    root = ET.fromstring(svg)
                    for group in root:
                        fill = next(e for e in group.iter() if e.tag.endswith("circle")).get("fill")
                        for e in list(list(group)[1])[1].iter():
                            if e.get("fill"):
                                e.set("fill", fill)
                    with self.assertRaises(ValueError):
                        contrast_pairs(ET.tostring(root, encoding="unicode"))

    @unittest.skipUnless(QT, "native Qt SVG module unavailable on SDK-free worker")
    def test_actual_qt_renders_every_window_action_and_state(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        count = 0
        for profile in BLOOM:
            frame = SHARE / "aurorae/themes" / profile["decoration"]
            decoration = QSvgRenderer(str(frame / "decoration.svg"))
            self.assertTrue(decoration.isValid())
            for action in bloom.glyphs.BUTTONS:
                renderer = QSvgRenderer(str(frame / (action+".svg")))
                self.assertTrue(renderer.isValid())
                for state in bloom.glyphs.BUTTON_STATES:
                    element = state+"-center"
                    self.assertTrue(renderer.elementExists(element))
                    self.assertEqual(renderer.boundsOnElement(element).width(), 44)
                    self.assertEqual(renderer.boundsOnElement(element).height(), 44)
                    for scale in (1, 1.5, 2.5):
                        size = round(44*scale)
                        image = QImage(size, size, QImage.Format_ARGB32)
                        image.fill(0)
                        painter = QPainter(image)
                        renderer.render(painter, element, QRectF(0, 0, size, size))
                        painter.end()
                        painted = sum(image.pixelColor(x, y).alpha() > 0 for y in range(size) for x in range(size))
                        self.assertGreater(painted, 30*scale*scale, (action, state, scale))
                        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
                        count += 1
        self.assertEqual(count, 480)
        del app

    @unittest.skipUnless(QT, "native Qt QML module unavailable on SDK-free worker")
    def test_real_shell_resolver_decodes_all_profiles_and_old_bloom_fails(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        source = (SHARE / "plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui/main.qml").read_text()
        resolver = re.search(r"(?ms)^    function resolveImage\(value\) \{.*?^    \}", source).group()
        engine = QJSEngine()
        shared = WALLPAPER_MAP.read_text().replace('.pragma library','')
        result = engine.evaluate(shared+'\nvar MoUI={WallpaperSources:{imageForPackage:imageForPackage}};var root={fallbackImage:"fallback"};'+resolver)
        self.assertFalse(result.isError(), result.toString())
        for profile in PROFILES:
            value = "/usr/share/wallpapers/"+profile["wallpaper"]
            resolved = engine.evaluate("resolveImage("+json.dumps(value)+")").toString()
            actual = ROOT / "system_files" / resolved.lstrip("/")
            self.assertTrue(actual.is_file(), (profile["id"], resolved))
            self.assertFalse(QImage(str(actual)).isNull(), resolved)
        # Restore the original resolver: both new native PNG packages become
        # nonexistent 4K JPEGs. The same real-image predicate must catch that.
        old = re.sub(r'(?m)^            var mapped = MoUI.WallpaperSources.imageForPackage\(base\)\n            if \(mapped !== ""\) \{ return mapped; \}\n', '', resolver)
        self.assertNotEqual(old, resolver)
        self.assertFalse(engine.evaluate(old).isError())
        for profile in BLOOM:
            resolved = engine.evaluate("resolveImage("+json.dumps("/usr/share/wallpapers/"+profile["wallpaper"])+")").toString()
            self.assertFalse((ROOT / "system_files" / resolved.lstrip("/")).is_file())
        del app

    @unittest.skipUnless(QT, "native Qt QML module unavailable on SDK-free worker")
    def test_actual_login_scene_resolves_the_same_originals_and_rejects_old_assumption(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        source = (SHARE / 'plasma/wallpapers/org.moos.ui2.greeter/contents/ui/main.qml').read_text()
        resolver = re.search(r'(?ms)^    function resolveImage\(value\) \{.*?^    \}', source).group()
        engine = QJSEngine()
        shared = WALLPAPER_MAP.read_text().replace('.pragma library','')
        self.assertFalse(engine.evaluate(shared+'\nvar MoUI={WallpaperSources:{imageForPackage:imageForPackage}};var root={fallbackImage:"fallback"};'+resolver).isError())
        for profile in PROFILES:
            value = '/usr/share/wallpapers/'+profile['wallpaper']
            actual = engine.evaluate('resolveImage('+json.dumps(value)+')').toString()
            self.assertFalse(QImage(str(ROOT/'system_files'/actual.lstrip('/'))).isNull(), actual)
        old = re.sub(r'(?m)^            var mapped = MoUI.WallpaperSources.imageForPackage\(base\)\n            if \(mapped !== ""\) \{ return mapped; \}\n', '', resolver)
        self.assertNotEqual(old, resolver)
        self.assertFalse(engine.evaluate(old).isError())
        for profile in BLOOM:
            actual = engine.evaluate('resolveImage('+json.dumps('/usr/share/wallpapers/'+profile['wallpaper'])+')').toString()
            self.assertFalse((ROOT/'system_files'/actual.lstrip('/')).is_file())
        del app

    def test_original_wallpaper_resolution_and_provenance(self):
        master = ROOT / "artwork/moos-ui2/wallpapers/moos-bloom-master.png"
        receipt = json.loads((master.parent / "bloom-generation.json").read_text())
        self.assertEqual(hashlib.sha256(master.read_bytes()).hexdigest(), receipt["sha256"])
        self.assertFalse(receipt["upscaled"])
        installed = SHARE / "wallpapers/MoOSUI2BloomLight/contents/images/1672x941.png"
        self.assertEqual(master.read_bytes(), installed.read_bytes())
        with Image.open(installed) as image:
            image.load()
            self.assertEqual(image.size, tuple(receipt["native_size"]))
        self.assertFalse((installed.parent / "3840x2160.jpg").exists())

    def test_native_wallpaper_selection_refuses_ambiguity(self):
        switch = (ROOT / "system_files/usr/bin/moos-theme").read_text()
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            share = private / "share"
            branch = share / "wallpapers/MoOSUI2BloomLight/contents/images"
            branch.mkdir(parents=True)
            (share / "konsole").mkdir()
            shutil.copy2(SHARE / "konsole/MoOSUI2AmethystLight.profile", share / "konsole")
            harness = ('set -euo pipefail\n'+function(switch, "load_profile").replace('/usr/share', str(share))+
                       '\nload_profile org.moos.ui2.bloom.light\nprintf "%s\\n" "$wallpaper"\n')
            env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
            env.update(HOME=str(private), XDG_CONFIG_HOME=str(private / "config"),
                       DBUS_SESSION_BUS_ADDRESS="unix:path="+str(private / "no-bus"),
                       MOOS_THEME_PROFILE_DB=str(SHARE / "moos/theme-profiles.tsv"))
            def run():
                return subprocess.run(["bash", "-c", harness], env=env, capture_output=True, text=True, timeout=10)
            self.assertTrue(run().stdout.strip().endswith("3840x2160.jpg"))  # old missing-package path remains a later refusal
            (branch / "preview.png").write_bytes(b"ignored")
            original = branch / "1672x941.png"
            original.write_bytes(b"fixture")
            self.assertEqual(run().stdout.strip(), str(original))
            (branch / "1920x1080.jpg").write_bytes(b"second")
            self.assertNotEqual(run().returncode, 0)
            self.assertIn("ambiguous", run().stderr)
            established = branch / "3840x2160.jpg"
            established.write_bytes(b"established")
            self.assertEqual(run().stdout.strip(), str(established))

    def test_finished_image_wallpaper_gate_keeps_legacy_and_native_refusals(self):
        path = ROOT / "build_files/verify_image_experience.py"
        tree = ast.parse(path.read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "theme_wallpaper_problem")
        namespace = dict(Path=Path, json=json, struct=struct)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        check = namespace["theme_wallpaper_problem"]
        for profile in PROFILES:
            self.assertEqual(check(profile["id"], profile["wallpaper"], SHARE), "", profile["id"])
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            shutil.copytree(SHARE / "wallpapers/MoOSUI2BloomLight", private / "wallpapers/MoOSUI2BloomLight")
            self.assertEqual(check("org.moos.ui2.bloom.light", "MoOSUI2BloomLight", private), "")
            self.assertTrue(check("org.moos.ui2.amethyst.light", "MoOSUI2BloomLight", private),
                            "a native Bloom PNG must never replace the legacy 4K requirement")
            self.assertTrue(check("org.moos.ui2.bloom", "MoOSUI2BloomLight", private))
            self.assertTrue(check("org.moos.ui2.bloom.light", "../MoOSBloom", private))
            image = private / "wallpapers/MoOSUI2BloomLight/contents/images/1672x941.png"
            original = image.read_bytes()
            image.write_bytes(original[:16]+struct.pack(">II", 1920, 1080)+original[24:])
            self.assertIn("dimensions", check("org.moos.ui2.bloom.light", "MoOSUI2BloomLight", private))
            image.unlink()
            self.assertTrue(check("org.moos.ui2.bloom.light", "MoOSUI2BloomLight", private))

    def test_curated_inputs_and_deterministic_generation(self):
        vendor = ROOT / "artwork/vendor/bloom"
        manifest = json.loads((vendor / "UPSTREAM.json").read_text())
        rows = {p["target"]: p for p in manifest["files"]}
        self.assertEqual({str(p.relative_to(ROOT)) for p in vendor.rglob("*.svg")} |
                         {str(p.relative_to(ROOT)) for p in vendor.rglob("*.rc")}, set(rows))
        for row in rows.values():
            self.assertEqual(hashlib.sha256((ROOT / row["target"]).read_bytes()).hexdigest(), row["sha256"])
            self.assertTrue(row["source_path"])
        for license_path in vendor.rglob("COPYING"):
            self.assertIn("GNU GENERAL PUBLIC LICENSE", license_path.read_text())
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            inputs = ["artwork/vendor/bloom", "artwork/generate_moos_aurorae.py", "artwork/moos-design/theme-profiles.json",
                      "artwork/moos-ui2/wallpapers/moos-bloom-master.png", "artwork/moos-ui2/wallpapers/bloom-generation.json"]
            for parent in ("MoOSUI2Amethyst", "MoOSUI2AmethystLight"):
                inputs += ["system_files/usr/share/"+rel for rel in
                           ("plasma/desktoptheme/"+parent, "icons/"+parent, "color-schemes/"+parent+".colors")]
            for suffix in ("", ".light"):
                inputs.append("system_files/usr/share/plasma/look-and-feel/org.moos.ui2.amethyst"+suffix)
            inputs.append("system_files/usr/share/wallpapers/MoOSPrismNight")
            for name in inputs:
                source, target = ROOT / name, private / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(source, target, symlinks=True)
                else:
                    shutil.copy2(source, target)
            env = dict(os.environ, MOOS_BLOOM_TEST_ROOT=str(private))
            subprocess.run(["python3", str(GENERATOR)], env=env, check=True, capture_output=True)
            generated = [p for p in (private / "system_files").rglob("*") if p.is_file() and
                         ("Bloom" in str(p) or "org.moos.ui2.bloom" in str(p))]
            self.assertGreater(len(generated), 150)
            for path in generated:
                self.assertEqual(path.read_bytes(), (ROOT / path.relative_to(private)).read_bytes(), str(path.relative_to(private)))
            # Corrupt pinned input must fail before creating the first output.
            broken = private / "artwork/vendor/bloom/colloid/light/decoration.svg"
            broken.write_text("<svg/>")
            wall = private / "system_files/usr/share/wallpapers/MoOSUI2BloomLight"
            shutil.rmtree(wall)
            refused = subprocess.run(["python3", str(GENERATOR)], env=env, capture_output=True, text=True)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("differs from its pinned source", refused.stderr)
            self.assertFalse(wall.exists())


if __name__ == "__main__":
    unittest.main()
