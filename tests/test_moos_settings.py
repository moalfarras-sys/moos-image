#!/usr/bin/env python3
"""Focused product and safety gate for MoOS Command Center."""

from __future__ import annotations

import json
import runpy
import shutil
import time
from unittest.mock import patch
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
            'argValue("--section=", arguments)',
            "function activateRequested(arguments)",
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


    def test_network_distinguishes_portal_limited_offline_and_unknown(self):
        scope = runpy.run_path(str(STATUS))
        probe = scope["network_state"]
        for raw, connected, full, known in (
            ("connected:full", True, True, True),
            ("connected:portal", True, False, True),
            ("connected (site only):limited", True, False, True),
            ("disconnected:none", False, False, True),
            ("", False, False, False),
        ):
            with self.subTest(raw=raw), patch.dict(probe.__globals__, command=lambda args: raw if args[-1] == "general" else ""):
                state = probe()
                self.assertEqual((state["connected"], state["full"], state["known"]), (connected, full, known))

    def test_signature_requires_official_origin_and_known_deployment(self):
        probe = runpy.run_path(str(STATUS))["deployment_state"]
        for ref, signed in (
            ("ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-arm:latest", True),
            ("ostree-image-signed:docker://example.org/moos:latest", False),
            ("ostree-unverified-registry:ghcr.io/moalfarras-sys/moos-arm:latest", False),
        ):
            raw = json.dumps({"deployments": [{"booted": True, "container-image-reference": ref}, {"staged": True}]})
            with self.subTest(ref=ref), patch.dict(probe.__globals__, command=lambda *a, **kw: raw):
                state = probe()
                self.assertTrue(state["known"])
                self.assertEqual(state["signed"], signed)
                self.assertEqual(state["rollback"], 0, "staged image is never a rollback")
        for raw in ("", "null", '{"deployments":null}', '{"deployments":[null]}'):
            with patch.dict(probe.__globals__, command=lambda *a, **kw: raw):
                self.assertFalse(probe()["known"])

    def test_destination_probe_matches_router_and_checks_modules(self):
        scope = runpy.run_path(str(STATUS))
        routes = {key: tuple(argv.split()) for key, argv in re.findall(
            r"^    settings/([a-z-]+)\)\s+gui ([^;]+?)\s*;;", ROUTER.read_text(), re.M)}
        self.assertEqual(scope["DESTINATIONS"], routes)
        probe = scope["destinations_state"]
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "plasma/kcms/systemsettings_qwidgets/kcm_clock.so"
            module.parent.mkdir(parents=True)
            module.touch()
            with patch.dict(probe.__globals__, command=lambda *a: tmp), patch.object(shutil, "which", return_value="/usr/bin/systemsettings"):
                state = probe()
                self.assertTrue(state["time"])
                self.assertFalse(state["region"])
                self.assertTrue(state["full"])
            with patch.object(shutil, "which", return_value=None):
                self.assertFalse(any(probe().values()))

    def test_publish_stamps_completed_snapshot(self):
        publish = runpy.run_path(str(STATUS))["publish"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            publish(path, {"generatedAt": 1})
            self.assertLess(abs(json.loads(path.read_text())["generatedAt"] - time.time()), 2)

    def test_ui_status_navigation_and_launch_behaviour(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node required to execute the QML JavaScript functions")
        qml = APP.read_text()
        def function(name):
            start = qml.index("    function " + name + "(")
            brace = qml.index("{", start)
            depth = 1
            end = brace + 1
            while depth:
                if qml[end] == "{": depth += 1
                if qml[end] == "}": depth -= 1
                end += 1
            return qml[start:end]
        scope = runpy.run_path(str(STATUS))
        state = scope["full_state"]()
        state["generatedAt"] = int(time.time())
        state["destinations"] = {"audio": True}
        script = """
const assert = require('node:assert/strict');
let statusLoaded=false, statusError='', statusSerial=0, status={}, launchError='';
let rtl=false, searchQuery='sound', activeSection='home';
let searchField={text:'sound'}, contentFlick={contentY:500};
let calls=[]; const Qt={openUrlExternally: url => {calls.push(url); return false}};
""" + "\n".join(function(n) for n in ("local", "routeAvailable", "routeReason", "openRoute", "selectSection", "acceptStatus", "statusFailure"))
        commands = qml.split("readonly property var commands: ")[1].split("\n\n    readonly property var activeSectionData")[0].strip()
        visible = qml.split("readonly property var visibleCommands: ")[1].split("\n\n    readonly property string statusUrl")[0].strip()
        script += "\nconst commands = " + commands + ";\nfunction visibleCommands() " + visible
        script += "\nassert.ok(visibleCommands().some(item => item.route === 'moos://settings/audio')); searchQuery='audio'; assert.equal(visibleCommands().length, 1);\n"
        script += "\nlet valid = " + json.dumps(state) + ";\n"
        script += """
assert.equal(acceptStatus(valid), true);
assert.equal(statusLoaded, true);
for (const bad of [null, {}, {...valid, generatedAt:1}, {...valid, schema:2}, {...valid, audio:{}}, {...valid, network:null}])
    assert.equal(acceptStatus(bad), false);
assert.equal(routeAvailable('moos://settings/audio'), true);
assert.equal(routeAvailable('moos://settings/missing'), false);
openRoute('https://example.org'); openRoute('moos://settings/missing');
assert.deepEqual(calls, []);
openRoute('moos://settings/audio');
assert.equal(calls.length, 1); assert.notEqual(launchError, '');
selectSection('devices');
assert.equal(searchQuery, ''); assert.equal(contentFlick.contentY, 0);
statusFailure(); assert.equal(statusLoaded, false); assert.notEqual(statusError, '');
assert.equal(routeAvailable('moos://settings/audio'), false);
assert.equal(acceptStatus(valid), true); assert.equal(statusError, '');
"""
        result = subprocess.run([node, "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rtl_is_mirrored_once_and_search_stays_synchronised(self):
        qml = APP.read_text()
        self.assertIn("onSearchQueryChanged:", qml)
        self.assertIn("searchField.text = searchQuery", qml)
        self.assertNotIn("horizontalAlignment: win.rtl ? Text.AlignRight", qml)
        search = qml.split('id: searchField')[1].split('FocusRing {')[0]
        self.assertIn('anchors.left: parent.left', search)
        self.assertNotIn('anchors.right:', search)
        self.assertIn('settings/region', qml)


if __name__ == "__main__":
    unittest.main()
