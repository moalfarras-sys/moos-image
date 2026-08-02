#!/usr/bin/env python3
"""Regression gates for the MoOS Tidal Horizon system doorways.

These tests guard the product relationship, not a screenshot approximation:
Splash, Login, Lock and Logout must share one pure geometry component; their
hosts may choose lifecycle-specific scale and finite motion, but may not fork
the visual signature or restore ambient animation.
"""

from __future__ import annotations

from pathlib import Path
import re
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SHARE = ROOT / "system_files/usr/share"
PORTAL_MASTER = ROOT / "artwork/tidal-portal/TidalHorizon.qml"
LNF_ROOT = SHARE / "plasma/look-and-feel"
LOCK_ROOT = (
    SHARE
    / "plasma/shells/org.kde.plasma.desktop/contents/lockscreen"
)
LOGIN_ROOT = SHARE / "plasma/wallpapers/org.moos.ui2.greeter/contents/ui"
BREEZE_COMPONENTS = (
    ROOT / "system_files/usr/lib64/qt6/qml/org/kde/breeze/components"
)


def ui2_packages() -> list[Path]:
    return sorted(path for path in LNF_ROOT.glob("org.moos.ui2*") if path.is_dir())


def qml_code(text: str) -> str:
    """Discard comments without corrupting file:/// strings."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def assert_portal_sync(paths: list[Path]) -> None:
    """Raise when any shipped portal drifts from the reviewed canonical bytes."""
    expected = PORTAL_MASTER.read_bytes()
    for path in paths:
        if not path.is_file():
            raise AssertionError(f"missing Tidal Horizon copy: {path}")
        if path.read_bytes() != expected:
            raise AssertionError(f"Tidal Horizon geometry drifted: {path}")


class TidalPortalContractTests(unittest.TestCase):
    def test_the_retired_arc_never_returns(self) -> None:
        """Owner verdict (2026-08-02): the full-screen Tidal curve is retired.
        No session surface, package, or first-party app may ship or draw it."""
        shipped = sorted((ROOT / "system_files").rglob("TidalHorizon.qml"))
        self.assertEqual(shipped, [], f"retired arc component shipped: {shipped}")
        self.assertFalse(PORTAL_MASTER.exists(),
                         "the retired arc master must not return")
        for surface in (
            LOCK_ROOT / "LockScreenUi.qml",
            LOGIN_ROOT / "main.qml",
            LNF_ROOT / "org.moos.ui2/contents/logout/Logout.qml",
            LNF_ROOT / "org.moos.ui2/contents/splash/Splash.qml",
        ):
            text = re.sub(r"//[^\n]*", "", surface.read_text(encoding="utf-8"))
            self.assertNotIn("TidalHorizon", text,
                             f"{surface} still references the retired arc")

    def test_splash_has_one_finite_reveal_and_stage_progress(self) -> None:
        splash = (
            LNF_ROOT
            / "org.moos.ui2/contents/splash/Splash.qml"
        ).read_text(encoding="utf-8")
        self.assertEqual(splash.count("id: revealAnimation"), 1)
        self.assertNotIn("Animation.Infinite", splash)
        self.assertNotIn("progressMotion", splash)
        self.assertIn("duration: 460", splash)
        self.assertIn("duration: root.motionEnabled ? 260 : 0", splash)
        self.assertIn("contentShift.y = 0", splash)

    def test_logout_is_a_framed_compact_command_island(self) -> None:
        logout = (
            LNF_ROOT
            / "org.moos.ui2/contents/logout/Logout.qml"
        ).read_text(encoding="utf-8")
        action = (
            LNF_ROOT
            / "org.moos.ui2/contents/logout/MoOSUI2ActionButton.qml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Animation.Infinite", logout + action)
        # The Glass Island: adaptive width between a 26-unit floor and the
        # content's own implicit width, a 2-unit radius, and the layered
        # material (fill, sheen, rim) with a soft three-step depth halo.
        self.assertIn("Kirigami.Units.gridUnit * 26", logout)
        self.assertIn("column.implicitWidth + Kirigami.Units.gridUnit * 4", logout)
        self.assertIn("id: island", logout)
        self.assertIn("radius: Kirigami.Units.gridUnit * 2", logout)
        self.assertIn("Qt.rgba(0, 0, 0, 0.04)", logout)
        # The countdown is a still Shape ring driven by remainingTime — the
        # naked hairline track must not return.
        self.assertIn("PathAngleArc", logout)
        self.assertIn(
            "sweepAngle: 360 * Math.max(0, Math.min(1, root.remainingTime / 30))",
            logout,
        )
        # Second-generation tiles: caption INSIDE the key surface, sized as a
        # real tile, with the crest/horizon cuts intact on dock tiles.
        self.assertIn("property real keyWidth", action)
        self.assertIn("property real keyHeight", action)
        self.assertIn("control.subtle ? 3.1 : 6.2", action)
        self.assertIn("control.subtle ? 10.4 : 8.6", action)
        self.assertIn("width: parent.width * 0.30", action)
        self.assertIn("width: parent.width * 0.42", action)
        self.assertNotIn("radius: width / 2", action)

    def test_login_and_lock_share_static_session_language(self) -> None:
        login = qml_code((LOGIN_ROOT / "main.qml").read_text(encoding="utf-8"))
        action = (BREEZE_COMPONENTS / "ActionButton.qml").read_text(
            encoding="utf-8"
        )
        clock = (BREEZE_COMPONENTS / "Clock.qml").read_text(encoding="utf-8")
        lock = (LOCK_ROOT / "LockScreenUi.qml").read_text(encoding="utf-8")
        lock_clock = (LOCK_ROOT / "MoOSClock.qml").read_text(encoding="utf-8")
        main_block = (LOCK_ROOT / "MainBlock.qml").read_text(encoding="utf-8")

        for forbidden in ("Timer {", "Animation.Infinite", "ShaderEffect"):
            self.assertNotIn(forbidden, login)
        self.assertIn("radius: height * 0.30", action)
        self.assertNotIn("radius: width / 2", action)
        self.assertIn("IBM Plex Sans Arabic", action)
        self.assertIn("trackSeconds: false", clock)
        self.assertIn("Locale.LongFormat", clock)
        self.assertIn("sessionLocale.dateFormat(Locale.LongFormat)", clock)
        self.assertNotIn("Animation.Infinite", clock)
        self.assertIn("LayoutMirroring.enabled: false", clock)
        self.assertIn("layoutDirection: Qt.LeftToRight", clock)

        self.assertNotIn("Animation.Infinite", lock)
        self.assertIn(
            "anchors.left: lockScreenUi.rtl ? undefined : parent.left", lock
        )
        self.assertIn(
            "anchors.right: lockScreenUi.rtl ? parent.right : undefined", lock
        )
        self.assertIn("IBM Plex Sans Arabic", lock_clock)
        self.assertIn(
            "Layout.preferredWidth: loginButton.Layout.preferredHeight * 1.28",
            main_block,
        )
        self.assertIn("radius: height * 0.30", main_block)
        self.assertIn("width: parent.width * 0.30", main_block)
        self.assertIn("width: parent.width * 0.42", main_block)


if __name__ == "__main__":
    unittest.main()
