#!/usr/bin/env python3
"""Focused product and safety gate for MoOS Command Center."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "system_files/usr/share/moos/apps/settings/main.qml"
LAUNCHER = ROOT / "system_files/usr/bin/moos-settings"
STATUS = ROOT / "system_files/usr/libexec/moos-settings-status"
DESKTOP = ROOT / "system_files/usr/share/applications/org.moos.settings.desktop"
ROUTER = ROOT / "system_files/usr/bin/moos-open"
ICONS = ROOT / "system_files/usr/share/icons/hicolor"
ICON_SIZES = (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512)


class MoOSSettingsTests(unittest.TestCase):
    def test_complete_launch_chain_and_owned_icon_ship(self) -> None:
        for path in (APP, LAUNCHER, STATUS, DESKTOP):
            self.assertTrue(path.is_file(), path)
        for path in (LAUNCHER, STATUS):
            self.assertTrue(path.stat().st_mode & stat.S_IXUSR, path)

        launcher = LAUNCHER.read_text(encoding="utf-8")
        desktop = DESKTOP.read_text(encoding="utf-8")
        self.assertIn("--app-id org.moos.settings", launcher)
        self.assertIn("--icon moos-control-center", launcher)
        self.assertIn('QML_XHR_ALLOW_FILE_READ=1', launcher)
        self.assertIn('"$@"', launcher)
        self.assertIn("Exec=moos-settings", desktop)
        self.assertIn("Icon=moos-control-center", desktop)
        self.assertIn("StartupWMClass=org.moos.settings", desktop)
        self.assertIn("Exec=moos-settings --section=appearance", desktop)
        self.assertIn("Exec=moos-settings --section=connectivity", desktop)
        self.assertIn("Exec=moos-settings --section=recovery", desktop)

        # SVG master is gone, check for PNG raster ladder.
        for size in ICON_SIZES:
            raster = ICONS / f"{size}x{size}/apps/moos-control-center.png"
            with self.subTest(size=size):
                self.assertTrue(raster.is_file(), raster)
                self.assertGreater(raster.stat().st_size, 256, raster)

    def test_qml_is_one_localised_accessible_motion_safe_product(self) -> None:
        qml = APP.read_text(encoding="utf-8")
        for contract in (
            "import org.moos.ui as MoUI",
            "Kirigami.Theme.highlightColor",
            "LayoutMirroring.enabled: rtl",
            "readonly property bool motionEnabled: Kirigami.Units.longDuration > 1",
            "implicitHeight: win.fs(48)",
            "implicitHeight: win.fs(88)",
            "Accessible.role: Accessible.Button",
            "MoUI.FocusRing",
            "MoUI.Button",
            'property string searchQuery: ""',
            "visibleCommands",
            "status.deployment.signed",
            "status.network.connected",
            "status.bluetooth.powered",
            'argValue("--section=")',
        ):
            self.assertIn(contract, qml)
        self.assertGreaterEqual(qml.count("Accessible.role: Accessible.Button"), 3)
        self.assertGreaterEqual(qml.count("MoUI.SymbolCatalog.resolve("), 12)
        # The Tidal arc is retired (owner verdict 2026-08-02): the hero field
        # must stay a calm themed surface with no full-screen curve.
        self.assertNotIn("TidalHorizon", qml)
        self.assertNotIn("font.family:", qml)
        self.assertNotIn("Animation.Infinite", qml)
        self.assertNotIn("Qt.openUrlExternally(command", qml)
        self.assertRegex(
            qml.replace("\n", " "),
            r'function openRoute\(route\).*?indexOf\("moos://settings/"\)',
        )

    def test_every_command_is_a_fixed_live_router_destination(self) -> None:
        qml = APP.read_text(encoding="utf-8")
        router = ROUTER.read_text(encoding="utf-8")
        routes = sorted(set(re.findall(r'"moos://(settings/[a-z0-9-]+)"', qml)))
        self.assertGreaterEqual(len(routes), 30)

        declared: set[str] = set()
        for match in re.finditer(r"^\s{4}([a-z0-9/*|-]+)\)", router, re.MULTILINE):
            declared.update(part for part in match.group(1).split("|") if part != "*")
        self.assertTrue(set(routes) <= declared, sorted(set(routes) - declared))
        self.assertNotIn("settings/*", declared)

        settings_start = router.index("settings/themes)")
        settings_end = router.index("\n\n    # ── Theme:", settings_start)
        command_center_routes = router[settings_start:settings_end]
        self.assertNotIn("eval ", command_center_routes)
        self.assertNotIn("sh -c", command_center_routes)
        self.assertNotIn("$tgt", command_center_routes)

        for route, executable, target in (
            ("settings/themes", "moos-theme-picker", ""),
            ("settings/wallpaper", "moos-theme-picker", ""),
            ("settings/display", "systemsettings", "kcm_kscreen"),
            ("settings/network", "systemsettings", "kcm_networkmanagement"),
            ("settings/audio", "systemsettings", "kcm_pulseaudio"),
            ("settings/permissions", "systemsettings", "kcm_app-permissions"),
            ("settings/update", "moos-update", ""),
            ("settings/recovery", "moos-rollback", ""),
            ("settings/firmware-security", "kinfocenter", "kcm_firmware_security"),
        ):
            line = next(
                row for row in command_center_routes.splitlines()
                if row.strip().startswith(route + ")")
            )
            self.assertIn("gui " + executable, line)
            if target:
                self.assertIn(target, line)

    def test_status_boundary_publishes_atomically_without_process_authority(self) -> None:
        source = STATUS.read_text(encoding="utf-8")
        self.assertIn('return base / "status.json"', source)
        self.assertIn("os.replace(temporary, path)", source)
        self.assertIn("os.chmod(temporary, 0o600)", source)
        self.assertIn("subprocess.run(", source)
        self.assertIn("capture_output=True", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system", source)
        self.assertNotIn('add_argument("--output"', source)

        with tempfile.TemporaryDirectory() as runtime:
            env = {**os.environ, "XDG_RUNTIME_DIR": runtime}
            result = subprocess.run(
                [str(STATUS)],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = Path(runtime) / "moos-settings/status.json"
            state = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(state["schema"], 1)
            self.assertEqual(state["product"], "MoOS")
            self.assertIn("deployment", state)
            self.assertIn("network", state)
            self.assertIn("memory", state)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
