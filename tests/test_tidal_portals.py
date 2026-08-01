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
    def test_all_four_doorways_ship_the_exact_reviewed_geometry(self) -> None:
        family = ui2_packages()
        self.assertEqual(len(family), 16)
        copies = [
            LOCK_ROOT / "TidalHorizon.qml",
            LOGIN_ROOT / "TidalHorizon.qml",
        ]
        for package in family:
            copies.extend(
                (
                    package / "contents/splash/TidalHorizon.qml",
                    package / "contents/logout/TidalHorizon.qml",
                )
            )
        assert_portal_sync(copies)

    def test_byte_identity_gate_rejects_a_mutated_copy(self) -> None:
        """Prove the sync gate bites instead of passing every input."""
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "TidalHorizon.qml"
            altered.write_bytes(PORTAL_MASTER.read_bytes() + b"\n// drift\n")
            with self.assertRaisesRegex(AssertionError, "geometry drifted"):
                assert_portal_sync([altered])

    def test_portal_is_pure_theme_fed_scalable_geometry(self) -> None:
        portal = PORTAL_MASTER.read_text(encoding="utf-8")
        for role in (
            "property color accentA",
            "property color accentB",
            "property color ink",
            "property color surface",
            "property real reveal",
            "property real intensity",
            "property bool compact",
        ):
            self.assertIn(role, portal)
        for signature in (
            "DropShadow {",
            "radius: Math.min(width, height) * 0.25",
            "samples: 65",
            "color: Qt.rgba(0, 0, 0, 0.45 * portal.intensity)",
            "transparentBorder: true",
        ):
            self.assertIn(signature, portal)
        for forbidden in (
            "Timer {",
            "Animation.Infinite",
            "MouseArea {",
            "ShaderEffect",
            "layer.effect",
        ):
            self.assertNotIn(forbidden, portal)

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
        self.assertIn("portal.reveal = 1", splash)
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
        self.assertIn("parent.width * 0.96", logout)
        self.assertIn("parent.height * 1.80", logout)
        self.assertIn("Kirigami.Units.gridUnit * 50", logout)
        self.assertIn("Kirigami.Units.gridUnit * 1.6", logout)
        self.assertIn("property real keyWidth", action)
        self.assertIn("property real keyHeight", action)
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

        self.assertIn("TidalHorizon {", login)
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

        self.assertIn("TidalHorizon {", lock)
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
