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
            BREEZE_COMPONENTS / "WallpaperFader.qml",
            BREEZE_COMPONENTS / "SessionManagementScreen.qml",
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
        self.assertIn("import org.moos.ui as MoUI", splash)
        self.assertEqual(splash.count("duration: root.design.motionPortal"), 3)
        self.assertIn("target: brandStage", splash)
        self.assertIn("brandStage.scale = 1", splash)
        self.assertIn(
            "duration: root.design.duration(root.motionEnabled,\n"
            "                                                       root.design.motionEmphasis)",
            splash,
        )
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
        self.assertIn("import org.moos.ui as MoUI", logout)
        self.assertIn("radius: root.design.radiusDialog", logout)
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
        island = qml_code(
            (BREEZE_COMPONENTS / "SessionManagementScreen.qml").read_text(encoding="utf-8")
        )
        backdrop = qml_code(
            (BREEZE_COMPONENTS / "WallpaperFader.qml").read_text(encoding="utf-8")
        )

        for forbidden in ("Timer {", "Animation.Infinite", "ShaderEffect"):
            self.assertNotIn(forbidden, login)
        self.assertIn("import org.moos.ui as MoUI", action)
        self.assertIn("radius: design.radiusPanel", action)
        self.assertNotIn("radius: width / 2", action)
        self.assertIn("font.family: design.interfaceFamily", action)
        self.assertIn("readonly property real compactScale", action)
        self.assertIn("sceneHeight - 320", action)
        self.assertIn("largeSpacing * 4 * compactScale", action)
        self.assertIn("6.6 * Math.max(0.82, root.compactScale)", action)
        self.assertIn("trackSeconds: false", clock)
        self.assertIn("Locale.LongFormat", clock)
        self.assertIn("sessionLocale.dateFormat(Locale.LongFormat)", clock)
        self.assertNotIn("Animation.Infinite", clock)
        self.assertIn("LayoutMirroring.enabled: false", clock)
        self.assertIn("layoutDirection: Qt.LeftToRight", clock)
        self.assertIn("readonly property real responsiveScale", clock)
        # A clock that does not fit above the face is hidden by both greeters; it scales
        # to the band the island leaves it, and the date steps aside before the time has to.
        self.assertIn("roomForDate ? (sceneHeight - 385) / 300", clock)
        self.assertIn(": (sceneHeight - 346) / 200", clock)
        self.assertIn("readonly property bool roomForDate: sceneHeight >= 560", clock)
        # Sized from the window both components are actually in, never the screen alone.
        for sized in (clock, action):
            self.assertIn(
                "readonly property real sceneHeight: "
                "Window.height > 0 ? Window.height : Screen.height", sized)
            self.assertNotIn("Screen.height - 320", sized)

        # ONE island for both doors: the lock screen's MainBlock and the login greeter's
        # Login are each a SessionManagementScreen, so what is drawn here is drawn on both.
        for surface in (island, backdrop):
            self.assertNotIn("Animation.Infinite", surface)
            self.assertNotIn("Timer {", surface)
        self.assertIn("MoUI.GlassSurface {", island)
        self.assertIn("id: island", island)
        self.assertIn("radius: root.design.radiusDialog", island)
        self.assertIn("fillOpacity: root.design.sessionGlassOpacity", island)
        # It hugs the cluster it frames instead of being sized from outside…
        self.assertIn("userListView.y + faceInset - root.islandPadTop", island)
        self.assertIn("prompts.y + promptBlock.y + promptBlock.height", island)
        # …and keeps upstream's two anchor lines, which both greeters place their clock by.
        self.assertIn("bottom: parent.verticalCenter", island)
        self.assertIn("anchors.top: parent.verticalCenter", island)
        # The face of the stock password row: one field, one key, the family's radius.
        self.assertIn("implicitHeight: root.design.targetControl", island)
        self.assertEqual(island.count("radius: root.design.radiusControl + 2"), 2)
        # The island signs itself (the login scene is another process and may be absent).
        self.assertIn('source: "file:///usr/share/pixmaps/moos-logo.png"', island)

        # The lock backdrop carries the session veil and the shared signature, and keeps
        # upstream's fade machinery whole.
        self.assertIn("MoUI.SessionSignature {", backdrop)
        self.assertIn("anchors.left: parent.left", backdrop)
        self.assertIn("anchors.top: parent.top", backdrop)
        self.assertIn("wallpaperFader.design.sessionScrimTopOpacity", backdrop)
        for upstream in ("FastBlur {", "id: wallpaperShader", 'name: "on"', 'name: "off"',
                         "clock.shadow.opacity", "mainStack.opacity: 1"):
            self.assertIn(upstream, backdrop)
        # The login scene signs with the same component, in the same corner.
        self.assertIn("MoUI.SessionSignature {", login)

    def test_the_lock_screen_draws_no_second_clock_or_card(self) -> None:
        """The fork this design replaced kept its own clock, card and images in the shell
        package. Any of them returning means two clocks, or a card behind the island."""
        for retired in ("MoOSClock.qml", "LockScreenUi.qml", "MainBlock.qml", "images"):
            self.assertFalse((LOCK_ROOT / retired).exists(),
                             f"{retired} is back in the lock screen overlay")
        self.assertEqual(sorted(p.name for p in LOCK_ROOT.iterdir()), ["MediaControls.qml"])

    def test_one_signature_component_signs_every_session_surface(self) -> None:
        signature = (
            ROOT / "system_files/usr/lib64/qt6/qml/org/moos/ui/SessionSignature.qml"
        ).read_text(encoding="utf-8")
        self.assertIn('source: "file:///usr/share/pixmaps/moos-logo.png"', signature)
        self.assertIn('text: "MoOS"', signature)
        # It reads nothing ambient: the caller supplies the ink.
        self.assertNotIn("Kirigami", signature)
        self.assertNotIn("Tokens", qml_code(signature))
        self.assertNotIn("Animation", qml_code(signature))
        users = {
            "lock": BREEZE_COMPONENTS / "WallpaperFader.qml",
            "login": LOGIN_ROOT / "main.qml",
            "power": LNF_ROOT / "org.moos.ui2/contents/logout/Logout.qml",
        }
        for name, path in users.items():
            text = qml_code(path.read_text(encoding="utf-8"))
            self.assertEqual(text.count("MoUI.SessionSignature {"), 1, name)
            self.assertNotIn('text: "MoOS"', text, f"{name} draws a second wordmark of its own")

    def test_power_screen_borrows_the_session_clock_and_face(self) -> None:
        logout = qml_code(
            (LNF_ROOT / "org.moos.ui2/contents/logout/Logout.qml").read_text(encoding="utf-8")
        )
        self.assertIn("import org.kde.breeze.components as SessionComponents", logout)
        self.assertEqual(logout.count("SessionComponents.Clock {"), 1)
        self.assertEqual(logout.count("SessionComponents.UserDelegate {"), 1)
        # No private clock: one numeral system, one face, one date format.
        for retired in ("nowTime", "nowDate", "toLocaleDateString", "Qt.formatTime"):
            self.assertNotIn(retired, logout)
        # The clock yields whole when the island leaves it no band.
        self.assertIn("visible: root.clockFits", logout)


if __name__ == "__main__":
    unittest.main()
