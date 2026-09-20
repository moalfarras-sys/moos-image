#!/usr/bin/env python3
"""The design reference must obey the design system it documents.

WHY THIS FILE EXISTS

`artwork/moos-ui2/DesignStudio.qml` is the executable reference a designer opens
to see what MoOS UI *is*, and `scripts/review/design-studio.py` is the only
supported way to render it. Neither was gated, and every defect below shipped
into the reference while looking perfectly convincing in a screenshot:

* the studio assigned `fillOpacity` on every glass surface itself. That bypasses
  `GlassSurface.qml`'s own `Tokens.glassFill()` binding — and `glassFill()` is the
  ONLY consumer of `Tokens.blurActive`. The one window whose job is to show the
  Liquid Glass material was the one window that never took the material's code
  path, so the branch that rewrote blur handling could not be seen in it at all;
* layout direction came from a `--language` command-line flag instead of
  `org.moos.ui`'s `Locale` singleton, which the visual contract names as the
  source of direction. A flag cannot be wrong in a screenshot, so nothing caught
  that a real Arabic session would disagree with it;
* the "opaque preview surfaces" switch was a stock `QQC2.Switch`, 20.125 px tall
  with a 36×18 indicator, in a window whose own footer claims its components come
  from the MoOS source — against a contract that states 40×40 logical px as the
  minimum interactive target (artwork/MOOS_UI2_DESIGN.md);
* the runner replaced `XDG_CONFIG_DIRS` with a fixture holding no `kwinrc`, so
  `Tokens.readBlurPreference()` found no policy in any layer and took its
  `return false` fallback. Every capture ever taken with it showed the opaque
  no-blur material, and nobody could render the frosted one on purpose.

None of that is visible to a grep, because in each case the QML was valid and the
picture was pretty. So this gate does what the clarity and motion gates do: it
RUNS the reference in a real QML engine, walks the object tree it actually built,
and reads the values the surfaces actually hold.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "artwork/moos-ui2/DesignStudio.qml"
RUNNER = ROOT / "scripts/review/design-studio.py"
UI = ROOT / "system_files/usr/lib64/qt6/qml"
RUNTIME = next((name for name in ("moos-qml-shell", "qml-qt6", "qml6", "qml")
                if shutil.which(name)), None)

# The contract's minimum interactive target, in logical pixels.
MINIMUM_TARGET = 40


def load_runner():
    """Import the review runner by path; its name is not an identifier."""
    spec = importlib.util.spec_from_file_location("moos_design_studio_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner()


# The probe instantiates the reference and reports what the engine built, rather
# than what the source says it should have built.
PROBE = """
import QtQuick
import Qt.labs.settings
import org.moos.ui as MoUI

Item {
    property var sink: Settings {
        fileName: "%(out)s"
        category: "Probe"
        property bool ran: false
        property bool rtl: false
        property bool mirroring: false
        property string locale: ""
        property bool blurActive: false
        property string fills: ""
        property string targets: ""
    }
    Component.onCompleted: {
        const factory = Qt.createComponent("%(studio)s")
        if (factory.status === Component.Error) {
            console.log("PROBE_ERROR " + factory.errorString())
            Qt.exit(3)
        }
        const window = factory.createObject(null, {})
        if (!window) { console.log("PROBE_ERROR createObject returned null"); Qt.exit(4) }
        const fills = [], targets = []
        function walk(item, insideScrollBar) {
            if (!item || !item.children) return
            for (let i = 0; i < item.children.length; ++i) {
                const child = item.children[i]
                const kind = child.toString().split("(")[0]
                // A scroll bar is a scroll affordance, not a tap target, and its
                // internal drag area is 21 px wide by design. It is the one thing
                // excluded here, and it is excluded BY NAME.
                const scrollBar = insideScrollBar || kind.indexOf("ScrollBar") >= 0
                // A MoUI GlassSurface: it owns a depth, a surface colour and the
                // fill those two produce.
                if (child.depth !== undefined && child.fillOpacity !== undefined
                        && child.surfaceColor !== undefined)
                    fills.push(child.depth + ":" + child.fillOpacity.toFixed(3))
                // Anything a person can press is an interactive target. Labels
                // contain spaces, so records are separated with "|", not " ".
                if (typeof child.clicked === "function" && child.visible
                        && child.width > 0 && child.height > 0 && !scrollBar)
                    targets.push((child.text || child.label || kind)
                                 + "=" + Math.round(child.width) + "x" + Math.round(child.height))
                walk(child, scrollBar)
            }
        }
        // One settle pass, so the reported sizes are laid-out sizes.
        const settle = Qt.createQmlObject(
            'import QtQuick; Timer { interval: 400; running: true }', window, 'settle')
        settle.triggered.connect(function () {
            walk(window.contentItem, false)
            sink.rtl = window.rtl
            sink.mirroring = window.LayoutMirroring.enabled
            sink.locale = MoUI.Locale.language
            sink.blurActive = MoUI.Tokens.blurActive
            sink.fills = fills.join(" ")
            sink.targets = targets.join("|")
            sink.ran = true
            Qt.callLater(function () { Qt.exit(0) })
        })
    }
}
"""


def inspect(blur: str, language: str, flag: str | None = None,
            scheme: str = "MoOSUI2AuroraLight") -> dict:
    """Build the runner's own fixture, run the reference in it, report what it built.

    The fixture is built with the RUNNER's functions on purpose: if the harness
    ever loses its explicit blur policy again, this gate stops building one too
    and the density tests below go red.
    """
    with tempfile.TemporaryDirectory(prefix="moos-design-studio-gate-") as raw:
        work = Path(raw)
        config = work / "config"
        config.mkdir()
        runner.write_palette(config, scheme)
        runner.write_blur_policy(config, blur)
        runtime_dir = work / "run"
        runtime_dir.mkdir(mode=0o700)
        out = work / "probe.ini"
        probe = work / "probe.qml"
        probe.write_text(
            PROBE % {"out": out, "studio": STUDIO.resolve().as_uri()}, encoding="utf-8")
        environment = {
            "HOME": str(work), "XDG_CONFIG_HOME": str(config),
            "XDG_CONFIG_DIRS": str(config), "XDG_DATA_HOME": str(work / "data"),
            "XDG_CACHE_HOME": str(work / "cache"), "XDG_RUNTIME_DIR": str(runtime_dir),
            # No session bus: a private one activates the desktop portals, which
            # outlive it. See the runner's docstring.
            "DBUS_SESSION_BUS_ADDRESS": f"unix:path={work}/absent-session-bus",
            "QML_IMPORT_PATH": str(UI), "QML2_IMPORT_PATH": str(UI),
            "QML_DISABLE_DISK_CACHE": "1", "QT_QPA_PLATFORM": "offscreen",
            "QT_QUICK_BACKEND": "software", "QT_QPA_PLATFORMTHEME": "kde",
            "QT_QUICK_CONTROLS_STYLE": "org.kde.desktop",
            "XDG_CURRENT_DESKTOP": "KDE", "KDE_SESSION_VERSION": "6",
            "LANG": "ar_EG.UTF-8" if language == "ar" else "en_US.UTF-8",
            "PATH": "/usr/bin:/bin",
        }
        command = ([RUNTIME, "--app-id", "org.moos.designstudio.gate", "--qml", str(probe)]
                   if RUNTIME == "moos-qml-shell" else [RUNTIME, str(probe)])
        # The reference reads its own `--language` from the process arguments. The
        # gate can therefore hand it a flag that CONTRADICTS the locale and check
        # which of the two the direction follows.
        command += ["--", f"--language={flag if flag else language}"]
        result = subprocess.run(command, env=environment, capture_output=True, timeout=180)
        if result.returncode != 0 or not out.exists():
            raise AssertionError(
                "the design reference did not run:\n"
                + result.stderr.decode(errors="replace") + result.stdout.decode(errors="replace"))
        values = {}
        for line in out.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                # QSettings quotes any value that contains a space.
                values[key.strip()] = value.strip().strip('"')
        if values.get("ran") != "true":
            raise AssertionError("the probe never completed its walk of the reference")
        return values


def png(width: int, height: int, colour_of) -> bytes:
    """A minimal 8-bit RGB PNG, so a capture check can be handed a known picture."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(colour_of(x, y))
    def chunk(kind: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw)))
            + chunk(b"IEND", b""))


class TheReviewRunner(unittest.TestCase):
    """The half of the contract that needs no Qt: the harness's own promises."""

    def test_the_runner_is_executable_like_its_siblings(self) -> None:
        self.assertTrue(os.access(RUNNER, os.X_OK),
                        f"{RUNNER.relative_to(ROOT)} is not executable; "
                        "every other tool in scripts/review/ is")

    def test_the_explicit_blur_policy_argument_survives(self) -> None:
        """A reviewer must be able to render BOTH materials on purpose.

        Without this argument the fixture states no policy, `readBlurPreference()`
        falls back to `false`, and every capture is the opaque material whatever
        the caption claims.
        """
        help_text = subprocess.run([sys.executable, str(RUNNER), "--help"],
                                   capture_output=True, text=True, timeout=60).stdout
        self.assertIn("--blur", help_text, "the harness lost its blur-policy argument")
        for policy in ("on", "off", "unset"):
            self.assertIn(policy, help_text, f"--blur can no longer be {policy}")

    def test_the_blur_policy_is_written_where_tokens_reads_it(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            config = Path(raw)
            runner.write_blur_policy(config, "on")
            self.assertEqual((config / "kwinrc").read_text(encoding="utf-8"),
                             "[Plugins]\nblurEnabled=true\n")
            runner.write_blur_policy(config, "off")
            self.assertEqual((config / "kwinrc").read_text(encoding="utf-8"),
                             "[Plugins]\nblurEnabled=false\n")
            (config / "kwinrc").unlink()
            runner.write_blur_policy(config, "unset")
            self.assertFalse((config / "kwinrc").exists(),
                             "`unset` must leave the fixture with no policy at all")

    def test_the_fixture_palette_carries_the_schemes_own_colours(self) -> None:
        """Naming `ColorScheme=` is not applying it.

        Measured on this station: a fixture kdeglobals that only names the scheme
        renders Breeze's #eff0f1; one with the scheme's `[Colors:*]` groups merged
        in renders AuroraLight's (194,228,225). The merge is the mechanism.
        """
        with tempfile.TemporaryDirectory() as raw:
            config = Path(raw)
            runner.write_palette(config, "MoOSUI2AuroraLight")
            text = (config / "kdeglobals").read_text(encoding="utf-8")
            self.assertIn("[Colors:Window]", text)
            self.assertIn("BackgroundNormal=194,228,225", text)
            self.assertIn("ColorScheme=MoOSUI2AuroraLight", text)

    def test_a_blank_or_half_drawn_capture_is_rejected(self) -> None:
        """Exit status, an error regex and an mtime all pass for an empty PNG."""
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            flat = work / "flat.png"
            flat.write_bytes(png(240, 240, lambda x, y: (194, 228, 225)))
            self.assertTrue(runner.complaints(runner.survey(flat)),
                            "a single flat colour passed the capture check")

            half = work / "half.png"
            half.write_bytes(png(240, 240, lambda x, y: (
                ((x * 7) % 256, (y * 11) % 256, (x * y) % 256) if y < 120
                else (194, 228, 225))))
            self.assertTrue(runner.complaints(runner.survey(half)),
                            "a half-drawn capture passed the capture check")

            drawn = work / "drawn.png"
            drawn.write_bytes(png(240, 240, lambda x, y: (
                (x * 3) % 256, (y * 5) % 256, (x + y) % 256)))
            self.assertEqual(runner.complaints(runner.survey(drawn)), [],
                             "a picture with real content was rejected")

    def test_a_capture_must_land_inside_the_repository(self) -> None:
        """`--capture` used to build arbitrary directory trees anywhere on disk."""
        result = subprocess.run(
            [sys.executable, str(RUNNER), "--capture", "/tmp/moos-design-studio-escape.png"],
            capture_output=True, text=True, timeout=60)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside", result.stderr)
        self.assertFalse(Path("/tmp/moos-design-studio-escape.png").exists())


@unittest.skipIf(RUNTIME is None, "no QML runtime on this machine (CI)")
class TheDesignReference(unittest.TestCase):
    """The half that has to run: what the engine actually builds."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.frosted = inspect(blur="on", language="ar")
        cls.opaque = inspect(blur="off", language="ar")

    @staticmethod
    def levels(report: dict) -> dict[int, float]:
        """depth -> fill, for every glass surface the reference built."""
        found: dict[int, float] = {}
        for entry in report["fills"].split():
            depth, _, fill = entry.partition(":")
            found[int(depth)] = float(fill)
        return found

    @staticmethod
    def sizes(report: dict) -> list[tuple[str, int, int]]:
        controls = []
        for entry in report["targets"].split("|"):
            if not entry.strip():
                continue
            name, _, box = entry.strip().rpartition("=")
            width, _, height = box.partition("x")
            controls.append((name or "control", int(width), int(height)))
        return controls

    def test_the_reference_reads_the_fixture_blur_policy(self) -> None:
        self.assertEqual(self.frosted["blurActive"], "true")
        self.assertEqual(self.opaque["blurActive"], "false")

    def test_density_comes_from_tokens_glassfill(self) -> None:
        """The defect this gate was written for.

        A studio that assigns its own `fillOpacity` cannot produce both of these
        answers, because `Tokens.glassFill()` is the only thing that knows about
        `blurActive`: with blur and the default Clear preference it returns the
        resting density at EVERY depth. Without blur, the effective clarity is
        pinned to the near-solid endpoint at every depth; the rim and specular
        retain the hierarchy without spending readability on transparency.
        """
        frosted = self.levels(self.frosted)
        opaque = self.levels(self.opaque)
        self.assertEqual(sorted(frosted), [0, 1, 2, 3],
                         "the reference must show all four Aurora Glass depths")
        self.assertEqual(sorted(opaque), [0, 1, 2, 3])
        for depth, fill in frosted.items():
            self.assertAlmostEqual(
                fill, 0.22, places=3,
                msg=f"with blur on, depth {depth} paints {fill}; glassFill() returns "
                    "the resting density — this surface is not going through it")
        for depth, fill in opaque.items():
            self.assertAlmostEqual(
                fill, 0.97, places=3,
                msg=f"without blur depth {depth} paints {fill}, not the shared "
                    "near-solid reduced-transparency endpoint")
            self.assertGreater(fill, frosted[depth] + 0.7)

    def test_layout_direction_comes_from_the_shipped_locale_singleton(self) -> None:
        """A flag is not a locale.

        `org.moos.ui`'s Locale reads `Qt.locale().textDirection`, and the visual
        contract makes it the source of direction. So the reference must mirror
        with an Arabic session even when its own `--language` flag says otherwise,
        and must not mirror with an English one that claims Arabic.
        """
        arabic = inspect(blur="on", language="ar", flag="en")
        self.assertEqual(arabic["locale"], "ar")
        self.assertEqual(arabic["rtl"], "true",
                         "an Arabic session must mirror even when --language says en")
        self.assertEqual(arabic["mirroring"], "true",
                         "LayoutMirroring must follow the locale, not the flag")

        english = inspect(blur="on", language="en", flag="ar")
        self.assertEqual(english["locale"], "en")
        self.assertEqual(english["rtl"], "false",
                         "an English session must not mirror because a flag says ar")
        self.assertEqual(english["mirroring"], "false")

    def test_every_interactive_target_meets_the_forty_pixel_minimum(self) -> None:
        """artwork/MOOS_UI2_DESIGN.md: minimum interactive target 40×40 logical px.

        A stock QQC2.Switch measures 20.125 px tall with a 36×18 indicator — half
        the contract — in a window that tells designers this is how MoOS is built.
        """
        controls = self.sizes(self.frosted)
        self.assertGreaterEqual(len(controls), 4,
                                "the reference stopped building interactive samples")
        for name, width, height in controls:
            with self.subTest(control=name):
                self.assertGreaterEqual(
                    height, MINIMUM_TARGET,
                    f"{name} is {width}×{height}; the contract's minimum is "
                    f"{MINIMUM_TARGET}×{MINIMUM_TARGET}")
                self.assertGreaterEqual(width, MINIMUM_TARGET,
                                        f"{name} is {width}×{height}")

    def test_the_reference_shows_every_shipped_arabic_string(self) -> None:
        """Arabic is first-class: the Arabic run must not fall back to English."""
        arabic = inspect(blur="on", language="ar")
        self.assertIn("مساحات", arabic["targets"],
                      "the Arabic session rendered English button labels")


class TheReferenceSource(unittest.TestCase):
    """Cheap companions, kept beside the measurements that explain them."""

    @staticmethod
    def code() -> str:
        """The studio with its comments removed.

        The comments have to be able to NAME the forms this gate forbids, the way
        tests/test_moos_motion_gate.py strips them for the same reason.
        """
        text = STUDIO.read_text(encoding="utf-8")
        return "\n".join(line.split("//")[0] for line in text.splitlines())

    def test_the_studio_never_assigns_its_own_fill(self) -> None:
        self.assertNotIn(
            "fillOpacity:", self.code(),
            "assigning fillOpacity bypasses GlassSurface's Tokens.glassFill() "
            "binding, which is the only consumer of Tokens.blurActive")

    def test_the_studio_does_not_derive_direction_from_a_flag(self) -> None:
        code = self.code()
        self.assertIn("MoUI.Locale.rtl", code,
                      "layout direction must come from the shipped Locale singleton")
        self.assertNotIn('argument("language", "en") === "ar"', code,
                         "layout direction was derived from a command-line flag")

    def test_the_studio_uses_the_shipped_motion_gate(self) -> None:
        code = self.code()
        self.assertIn("Kirigami.Units.longDuration > 1", code,
                      "reduced motion must be READ from the owner's setting, not simulated")
        self.assertNotIn("longDuration > 0", code)

    def test_the_studio_uses_the_shipped_muted_alpha(self) -> None:
        code = self.code()
        self.assertIn("design.mutedOpacity", code,
                      "secondary ink must use Tokens.mutedOpacity, not an invented alpha")
        self.assertNotIn("0.76", code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
