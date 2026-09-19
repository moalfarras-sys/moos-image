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
import unittest

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "system_files/usr/share/plasma/shells/org.kde.plasma.desktop/contents"
IMAGE_PREFIX = "/usr/share/plasma/shells/org.kde.plasma.desktop/contents"

# Files MoOS ADDS rather than replaces. `rpm -qf` does not own them, so no upstream
# transaction can overwrite them and the survival gate has nothing to assert. They are
# named — not pattern-matched — because "it looked new to me" is how the lock screen
# went ungated for four revisions.
MOOS_ADDITIONS = {
    "lockscreen/MoOSClock.qml",
    "lockscreen/images/ring.png",
    "lockscreen/images/spark.png",
}


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
