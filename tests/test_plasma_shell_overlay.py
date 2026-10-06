#!/usr/bin/env python3
"""Every file MoOS drops into KDE's own shell package must be gated in the image.

MoOS does not ship a Plasma shell package. It restyles `plasma-desktop`'s one by
dropping its versions on top of the package's own paths with `COPY system_files/ /`.
Measured on the station 2026-09-19, `rpm -V plasma-desktop` reports `S.5....T.` —
size, checksum and mtime all differing from what the package shipped — for six paths
under `/usr/share/plasma/shells/org.kde.plasma.desktop/contents/`.

That is supported, and it is fragile in one specific direction, which `build.sh`'s own
comment states: the base image owns those paths too, so any later transaction that
pulls plasma-desktop restores upstream's bytes at the same path. Every repo gate stays
green — they only read the source tree — while the shipped desktop silently reverts to
stock Plasma.

`build.sh` already asserts on the FINISHED filesystem that the overlay survived, with a
marker string per file so a reinstall at the same path cannot pass. The defect this gate
exists to prevent is the list falling behind the tree: it covered two of the six for as
long as the other four existed, and the four it missed included the LOCK SCREEN. Adding
a seventh overlay file and forgetting the gate is silent, and it stays silent until an
owner sees a Breeze lock screen on a MoOS machine.

So: the gate list is derived from the tree here, not maintained by hand there.
"""
from pathlib import Path
import re
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "system_files/usr/share/plasma/shells/org.kde.plasma.desktop/contents"
IMAGE_PREFIX = "/usr/share/plasma/shells/org.kde.plasma.desktop/contents"

# Files MoOS ADDS rather than replaces. `rpm -qf` does not own them, so no upstream
# transaction can overwrite them and the survival gate has nothing to assert. They are
# named — not pattern-matched — because "it looked new to me" is how the lock screen
# went ungated for four revisions. None today: the lock screen's own clock and its two
# images were retired on 2026-10-05 with the LockScreenUi.qml fork that used them.
MOOS_ADDITIONS: set[str] = set()

# The lock screen's two authentication-carrying files. MoOS replaced both until
# 2026-10-05 and had to re-derive them by hand for every Plasma release; the MoOS lock
# screen is now drawn by the breeze components those files instantiate, and these two
# paths belong to plasma-desktop alone. See tests/test_plasma_seams.py.
UPSTREAM_ONLY = ("lockscreen/LockScreenUi.qml", "lockscreen/MainBlock.qml")


def gate_entries(script: str) -> dict[str, str]:
    """The path:marker pairs that script's image gate actually checks."""
    text = (ROOT / "build_files" / script).read_text(encoding="utf-8")
    return {
        path: marker
        for path, marker in re.findall(
            r'"(' + re.escape(IMAGE_PREFIX) + r'/[^":]+):([^"]+)"', text)
    }


class PlasmaShellOverlay(unittest.TestCase):
    def setUp(self):
        self.tracked = sorted(
            str(path.relative_to(OVERLAY))
            for path in OVERLAY.rglob("*") if path.is_file())
        # x86 runs build.sh, aarch64 runs build-arm.sh, and both COPY the same
        # system_files/. A path guarded on one and not the other reverts on the
        # architecture nobody checked.
        self.scripts = {name: gate_entries(name)
                        for name in ("build.sh", "build-arm.sh")}

    def test_the_tree_carries_the_overlay_this_gate_is_about(self):
        """A rename that emptied the directory must fail here, not read as 'all clear'."""
        self.assertTrue(self.tracked, f"no overlay files under {OVERLAY}")
        for script, gated in sorted(self.scripts.items()):
            self.assertTrue(gated, f"{script} has no shell-overlay survival gate any more")

    def test_every_replaced_file_is_checked_in_the_finished_image(self):
        replaced = [name for name in self.tracked if name not in MOOS_ADDITIONS]
        for script, gated in sorted(self.scripts.items()):
            missing = [name for name in replaced
                       if f"{IMAGE_PREFIX}/{name}" not in gated]
            self.assertEqual(
                missing, [],
                f"these files overwrite plasma-desktop's own paths but {script} never "
                "checks they survived the build — a package transaction would restore "
                "stock Plasma at the same path with every repo gate still green:\n  "
                + "\n  ".join(missing))

    def test_the_authentication_files_are_left_to_upstream(self):
        for name in UPSTREAM_ONLY:
            self.assertNotIn(name, self.tracked,
                             f"{name} is back in the overlay: it carries the authenticator "
                             "wiring, and a MoOS copy of it is how a Plasma update becomes "
                             "the emergency locker")
            for script, gated in sorted(self.scripts.items()):
                self.assertNotIn(f"{IMAGE_PREFIX}/{name}", gated,
                                 f"{script} still demands a MoOS copy of {name}")

    def test_every_addition_is_really_an_addition(self):
        """The allowlist may not be used to excuse a file that IS in the tree's way."""
        stale = [name for name in MOOS_ADDITIONS if name not in self.tracked]
        self.assertEqual(stale, [],
                         "MOOS_ADDITIONS names files that are no longer in the tree; an "
                         "allowlist entry for a path nobody ships excuses nothing:\n  "
                         + "\n  ".join(stale))

    def test_every_marker_really_occurs_in_the_file_it_guards(self):
        """A marker that is not in the file passes the build and proves nothing.

        `build.sh` greps the finished image for this string. If the MoOS copy never
        contained it, the gate fails on a correct build; if upstream's copy also
        contains it, the gate passes on a reverted one. Both are checked here against
        the source, which is the only place that can see the MoOS copy at gate time.
        """
        for path, marker in sorted(
                {pair for gated in self.scripts.values() for pair in gated.items()}):
            name = path[len(IMAGE_PREFIX) + 1:]
            source = OVERLAY / name
            self.assertTrue(source.is_file(),
                            f"a build script guards {path}, which MoOS does not ship")
            self.assertIn(
                marker, source.read_text(encoding="utf-8", errors="replace"),
                f"a build script looks for '{marker}' in {name} to prove the file is "
                f"MoOS's, but the MoOS copy does not contain it")


class InstalledSessionIdentity(unittest.TestCase):
    """Execute selfcheck's real lock section against a private installed tree.

    A stock authentication file plus MoOS components is healthy since rev 101.
    Neither a missing component nor a restored authentication fork may pass.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.image = Path(self.tmp.name)
        self.lock = self.image / IMAGE_PREFIX.lstrip("/") / "lockscreen"
        self.lock.mkdir(parents=True)
        for name in ("LockScreenUi.qml", "MainBlock.qml"):
            (self.lock / name).write_text("import QtQuick\nItem {}\n")
        self.components = self.image / "usr/lib64/qt6/qml/org/kde/breeze/components"
        shutil.copytree(ROOT / "system_files/usr/lib64/qt6/qml/org/kde/breeze/components",
                        self.components)

    def report(self):
        text = (ROOT / "system_files/usr/bin/moos-selfcheck").read_text()
        section = text.split('head_ "القفل والإقلاع | Lock screen & boot"\n', 1)[1]
        section = section.split("if [ -d /usr/share/plymouth/themes/moos ]; then", 1)[0]
        section = section.replace("/usr/", str(self.image / "usr") + "/")
        result = subprocess.run(
            ["bash", "-c", 'set -uo pipefail\nok() { echo "OK $1"; }\n'
             'bad() { echo "BAD $1"; }\n' + section],
            capture_output=True, text=True, timeout=10,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                 "HOME": str(self.image), "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
                 "DISPLAY": "", "WAYLAND_DISPLAY": ""})
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_upstream_authentication_and_moos_components_pass(self):
        self.assertTrue(self.report().startswith("OK "))

    def test_each_missing_component_fails(self):
        for name in ("SessionManagementScreen", "WallpaperFader", "Clock",
                     "UserList", "UserDelegate", "ActionButton"):
            path = self.components / (name + ".qml")
            content = path.read_text()
            with self.subTest(component=name):
                path.unlink()
                self.assertTrue(self.report().startswith("BAD "))
            path.write_text(content)

    def test_upstream_component_with_only_a_moos_comment_fails(self):
        (self.components / "SessionManagementScreen.qml").write_text(
            "// MoOS imports org.moos.ui as MoUI\nimport QtQuick\nItem {}\n")
        self.assertTrue(self.report().startswith("BAD "))

    def test_missing_authentication_and_retired_fork_fail(self):
        for name in ("LockScreenUi.qml", "MainBlock.qml"):
            path = self.lock / name
            with self.subTest(file=name, state="missing"):
                path.unlink()
                self.assertTrue(self.report().startswith("BAD "))
            with self.subTest(file=name, state="fork"):
                path.write_text("import org.moos.ui\nItem {}\n")
                self.assertTrue(self.report().startswith("BAD "))
            path.write_text("import QtQuick\nItem {}\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
