#!/usr/bin/env python3
"""Gate: a wallpaper the owner picks outside moos-theme survives login and drift checks.

WHY THIS EXISTS

On 2026-09-17 the owner reported that a wallpaper chosen in Plasma's own "Desktop and
Wallpaper" dialog changed the desktop and then came back as the theme wallpaper after a
reboot. The choice never passed through moos-theme, so the central state still said
"profile"; the login reconcile and the 30-minute drift check re-applied the theme canvas.

The reconciler now adopts the live choice before deciding: a desktop moved to Plasma's
plain image plugin is carried back onto the MoOS scene WITH the owner's image (so MoOS Hub
stays), and a non-family image is recorded as custom. Verified live on the station; this
gate drives the real shell functions against a scripted plasmashell.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "system_files/usr/bin/moos-theme"
BASH = "/usr/bin/bash" if Path("/usr/bin/bash").exists() else "bash"
TOKEN = "%2Fvar%2Fhome%2Fowner%2FPictures%2Fsea.png"

# One scripted plasmashell: each evaluateScript is recognised by a marker it prints.
FAKE_GDBUS = r"""#!/usr/bin/bash
script="$*"
printf '%s\n' "$script" >>"$MOOS_TEST_LOG"
case "$script" in
  *moos-image-plugin*)
    if [ "$MOOS_TEST_PLUGIN" = image ]; then
      printf "(true, 'moos-image-plugin:%s')\n" "$MOOS_TEST_TOKEN"
    else
      printf "(true, 'moos-image-plugin:none')\n"
    fi ;;
  *"var IMAGE = decodeURIComponent"*)
    printf 'applied\n' >>"$MOOS_TEST_APPLIED"
    printf "(true, 'scene-ready')\n" ;;
  *moos-wallpaper-state*)
    printf "(true, 'moos-wallpaper-state:%s:%s')\n" "$MOOS_TEST_MODE" "$MOOS_TEST_TOKEN" ;;
  *) printf "(true, '')\n" ;;
esac
"""


def function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    end = source.index("\n}\n", start) + 3
    return source[start:end]


class OwnerWallpaperChoice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = OWNER.read_text(encoding="utf-8")
        cls.functions = "\n".join(function(cls.source, name) for name in (
            "current", "theme_state_root", "theme_state_field", "encode_profile_wallpaper",
            "capture_wallpaper_identity", "write_theme_state", "apply_desktop_scene_token",
            "adopt_live_wallpaper_choice", "load_wallpaper_expectation"))

    def run_case(self, *, plugin: str, mode: str, prior_state: str = "profile"):
        root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="moos-owner-wall-")))
        bindir = root / "bin"
        bindir.mkdir()
        for name, body in (("gdbus", FAKE_GDBUS), ("kreadconfig6", "#!/usr/bin/bash\necho org.moos.ui2.aurora\n")):
            path = bindir / name
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)
        state_dir = root / "state/moos/theme"
        state_dir.mkdir(parents=True)
        (state_dir / "theme-state.json").write_text(
            '{\n  "schema": 2,\n  "status": "committed",\n  "active": "org.moos.ui2.aurora",\n'
            '  "previous": "org.moos.ui2.aurora",\n'
            f'  "wallpaperMode": "{prior_state}",\n'
            '  "wallpaperEncoded": "%2Fusr%2Fshare%2Fwallpapers%2FMoOSUI2Aurora",\n'
            '  "updated": "2026-09-17T00:00:00Z"\n}\n', encoding="utf-8")
        probe = root / "probe"
        probe.write_text(
            self.functions
            + '\nwallpaper_package=/usr/share/wallpapers/MoOSUI2Aurora\n'
            + 'load_wallpaper_expectation state\n'
            + 'printf "%s %s\\n" "$desktop_wallpaper_mode" "$desktop_wallpaper_token"\n',
            encoding="utf-8")
        env = os.environ | {
            "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            "XDG_STATE_HOME": str(root / "state"),
            "MOOS_TEST_LOG": str(root / "calls.log"),
            "MOOS_TEST_APPLIED": str(root / "applied.log"),
            "MOOS_TEST_PLUGIN": plugin,
            "MOOS_TEST_MODE": mode,
            "MOOS_TEST_TOKEN": TOKEN,
        }
        result = subprocess.run([BASH, str(probe)], env=env, capture_output=True,
                                text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        state = (state_dir / "theme-state.json").read_text(encoding="utf-8")
        applied = (root / "applied.log").exists()
        return result.stdout.strip(), state, applied

    def test_a_plain_image_plugin_choice_is_carried_onto_the_scene_and_kept(self):
        expectation, state, applied = self.run_case(plugin="image", mode="custom")
        self.assertTrue(applied, "the owner's image must be moved onto the MoOS scene")
        self.assertIn('"wallpaperMode": "custom"', state)
        self.assertIn(f'"wallpaperEncoded": "{TOKEN}"', state)
        self.assertEqual(expectation, f"custom {TOKEN}",
                         "reconciliation must now expect the owner's image, not the theme's")

    def test_a_scene_image_chosen_on_its_own_page_is_kept(self):
        expectation, state, applied = self.run_case(plugin="scene", mode="custom")
        self.assertFalse(applied, "an image already on the scene needs no re-point")
        self.assertIn('"wallpaperMode": "custom"', state)
        self.assertEqual(expectation, f"custom {TOKEN}")

    def test_the_family_canvas_stays_a_profile_wallpaper(self):
        expectation, state, _ = self.run_case(plugin="scene", mode="profile")
        self.assertIn('"wallpaperMode": "profile"', state)
        self.assertTrue(expectation.startswith("profile "), expectation)

    def test_profile_means_this_family_not_any_moos_canvas(self):
        capture = function(self.source, "capture_wallpaper_identity")
        self.assertIn('var FAMILY = "\'"$family"\'";', capture)
        self.assertIn('bare == FAMILY || bare == FAMILY + "Light"', capture)
        self.assertNotIn("/\\/", capture, "QJSEngine rejects an escaped-slash RegExp")
        manual = function(self.source, "apply_wallpaper_transaction")
        self.assertNotIn("adopt_live_wallpaper_choice", manual,
                         "picking a theme still resets to that theme's canvas")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(OwnerWallpaperChoice))
    raise SystemExit(0 if result.wasSuccessful() else 1)
