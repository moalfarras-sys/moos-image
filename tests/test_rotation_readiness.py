#!/usr/bin/env python3
"""Exercise the actual diagnostic chain with private sysfs and native wire shapes."""
import copy
import importlib.machinery
import importlib.util
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader(
    "rotation_plan", str(ROOT / "system_files/usr/bin/moos-device-plan"))
spec = importlib.util.spec_from_loader(loader.name, loader)
plan = importlib.util.module_from_spec(spec)
loader.exec_module(plan)


def sensor(has=True, orientation="normal"):
    return {"type": "a{sv}", "data": [{
        "HasAccelerometer": {"type": "b", "data": has},
        "AccelerometerOrientation": {"type": "s", "data": orientation}}]}


def display(enabled=True, rotation=1, scale=1.45):
    return {"outputs": [{"type": 7, "name": "eDP-1", "connected": True,
        "enabled": enabled, "scale": scale, "rotation": rotation,
        "currentModeId": "35", "modes": [{"id": "35", "size": {
            "width": 2560, "height": 1600}}]}]}


class RotationReadiness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.sysfs = Path(self.temp.name)
        self.clients = self.sysfs / "bus/i2c/devices"
        self.clients.mkdir(parents=True)

    def client(self, bound=False):
        client = self.clients / "i2c-SMOCF05:00"
        client.mkdir()
        if bound:
            driver = self.sysfs / "bus/i2c/drivers/st_lsm6dsx_i2c"
            driver.mkdir(parents=True)
            (client / "driver").symlink_to(driver, target_is_directory=True)
        return client

    def report(self, sensors=None, screens=None, sensor_status="ok", display_status="ok"):
        with patch.object(plan, "graphical_session_available", return_value=True), \
                patch.object(plan, "json_probe", side_effect=[
                (sensor() if sensors is None else sensors, sensor_status),
                (display() if screens is None else screens, display_status)]):
            return plan.rotation_report(self.sysfs)

    def test_old_empty_gap_is_not_a_successful_inventory(self):
        missing = self.sysfs / "absent"
        # Preserve the predecessor symptom alongside the explicit new confidence.
        self.assertEqual(plan.i2c_driver_gaps(missing), [])
        result = plan.motion_sensor_inventory(missing)
        self.assertFalse(result["known"])
        self.assertEqual(result["status"], "read-failed")

    def test_non_directory_bus_is_unknown(self):
        self.clients.rmdir()
        self.clients.write_text("not a device directory")
        self.assertFalse(plan.motion_sensor_inventory(self.sysfs)["known"])

    def test_empty_inventory_is_known(self):
        self.assertEqual(plan.motion_sensor_inventory(self.sysfs),
                         {"known": True, "status": "ok", "clients": []})

    def test_permission_refusal_does_not_become_empty_health(self):
        with patch.object(plan.os, "scandir", side_effect=PermissionError):
            self.assertFalse(plan.motion_sensor_inventory(self.sysfs)["known"])

    def test_driver_missing_wins_over_unavailable_service(self):
        self.client()
        result = self.report(sensor_status="unavailable")
        self.assertEqual(result["status"], "driver-missing")
        self.assertFalse(result["physical_rotation_tested"])

    def test_bound_driver_without_accelerometer_is_not_ready(self):
        self.client(bound=True)
        self.assertEqual(self.report(sensor(False))["status"], "accelerometer-missing")

    def test_readiness_reaches_existing_hardware_action_owner(self):
        with patch.object(plan, "run", return_value="01:00.0 VGA compatible controller: AMD\n\tKernel driver in use: amdgpu"), \
                patch.object(plan, "flatpak_installed", return_value=False), \
                patch.object(plan, "driver_gaps", return_value=[]), \
                patch.object(plan, "firmware_report", side_effect=lambda status: (
                    status.update(firmware_known=True, kernel_journal_known=True) or ([], []))):
            for state, health in (("driver-missing", "action-needed"),
                                  ("accelerometer-missing", "action-needed"),
                                  ("inspection-unavailable", "attention"),
                                  ("sensor-unavailable", "attention"),
                                  ("panel-disabled", "attention"),
                                  ("rotation-locked", "ready"),
                                  ("available-unverified", "ready"),
                                  ("not-applicable", "ready")):
                with self.subTest(state=state), patch.object(plan, "rotation_report",
                                                            return_value={"status": state}):
                    result = plan.detect(machine="x86_64")
                    self.assertEqual(result["health"], health)
                    self.assertEqual(result["rotation"]["status"], state)
                    actions = [a for a in result["actions"] if a["id"].startswith("rotation-")]
                    self.assertEqual(len(actions), int(health != "ready" or state == "rotation-locked"))
                    for action in actions:
                        self.assertIn(" | ", action["title"])
                        self.assertIn(" | ", action["detail"])
                        self.assertEqual(action["url"], "")

    def test_bound_driver_with_failed_proxy_is_unknown(self):
        self.client(bound=True)
        for status in ("timeout", "unavailable", "command-failed", "invalid-response"):
            with self.subTest(status=status):
                self.assertEqual(self.report(sensor_status=status)["status"], "sensor-unavailable")

    def test_sensor_presence_does_not_enable_disabled_panel(self):
        self.assertEqual(self.report(screens=display(False))["status"], "panel-disabled")

    def test_external_display_is_never_rotated_or_treated_as_panel(self):
        external = display()["outputs"][0]
        external.update(type=14, name="DP-11", scale=2.5)
        self.assertEqual(self.report(screens={"outputs": [external]})["status"], "not-applicable")

    def test_only_native_internal_panel_is_reported(self):
        screens = display()
        external = copy.deepcopy(screens["outputs"][0])
        external.update(type=14, name="DP-11", scale=2.5)
        screens["outputs"].append(external)
        result = self.report(screens=screens)
        self.assertEqual([p["name"] for p in result["display"]["panels"]], ["eDP-1"])
        self.assertEqual(screens["outputs"][1]["scale"], 2.5)

    def test_four_rotations_preserve_fractional_scale(self):
        for rotation in (1, 2, 4, 8, 16, 32, 64, 128):
            for scale in (1, 1.25, 1.45, 2.5):
                with self.subTest(rotation=rotation, scale=scale):
                    result = self.report(screens=display(rotation=rotation, scale=scale))
                    self.assertEqual(result["status"], "available-unverified")
                    panel = result["display"]["panels"][0]
                    width, height = (1600, 2560) if rotation in (2, 8, 32, 128) else (2560, 1600)
                    self.assertEqual(panel["derived_logical_size"], {
                        "width": round(width / scale, 3), "height": round(height / scale, 3)})
                    self.assertEqual(panel["derived_logical_bounds"], {
                        "width": math.ceil(width / scale), "height": math.ceil(height / scale)})
                    self.assertEqual(panel["scale"], scale)
                    self.assertEqual(panel["auto_rotation_policy"], "unavailable")
                    self.assertFalse(result["touch_mapping_tested"])

    def test_valid_idle_orientation_does_not_claim_a_physical_test(self):
        result = self.report(sensor(True, "undefined"))
        self.assertEqual(result["status"], "available-unverified")
        self.assertFalse(result["physical_rotation_tested"])

    def test_optional_native_policy_and_personal_lock(self):
        for value, expected in ((0, "never"), (1, "tablet"), (2, "always")):
            screens = display()
            screens["outputs"][0]["autoRotatePolicy"] = value
            result = self.report(screens=screens)
            self.assertEqual(result["display"]["panels"][0]["auto_rotation_policy"], expected)
            self.assertEqual(result["status"], "rotation-locked" if value == 0 else "available-unverified")
            self.assertEqual(screens["outputs"][0]["autoRotatePolicy"], value)
        for value in (True, "always", -1, 3, None):
            screens = display()
            screens["outputs"][0]["autoRotatePolicy"] = value
            self.assertFalse(plan.internal_panel_report(screens, "ok")["known"])

    def test_strict_sensor_types(self):
        invalid = [None, [], {}, {"type": "a{sv}", "data": []},
                   sensor(1), sensor("false"), sensor(True, "sideways")]
        wrong = sensor()
        wrong["data"][0]["HasAccelerometer"]["type"] = "s"
        invalid.append(wrong)
        for payload in invalid:
            with self.subTest(payload=payload):
                result = plan.sensor_proxy_report(payload, "ok")
                self.assertFalse(result["known"])
                self.assertEqual(result["status"], "invalid-response")

    def test_malformed_panel_never_claims_geometry(self):
        for key, value in (("scale", True), ("scale", 0), ("scale", float("nan")),
                           ("rotation", True), ("rotation", 3), ("modes", None),
                           ("enabled", "true"), ("currentModeId", "missing")):
            screens = display()
            screens["outputs"][0][key] = value
            with self.subTest(key=key, value=value):
                self.assertFalse(plan.internal_panel_report(screens, "ok")["known"])
        for size in (None, [], {"width": True, "height": 1600},
                     {"width": 2560, "height": -1}):
            screens = display()
            screens["outputs"][0]["modes"][0]["size"] = size
            self.assertFalse(plan.internal_panel_report(screens, "ok")["known"])

    def test_hotplug_new_snapshot_never_reuses_old_geometry(self):
        first = self.report()
        second = self.report(screens={"outputs": []})
        self.assertTrue(first["display"]["panels"])
        self.assertEqual(second["display"]["panels"], [])

    def test_absent_mode_identity_or_duplicate_ids_are_refused(self):
        screens = display()
        del screens["outputs"][0]["currentModeId"]
        del screens["outputs"][0]["modes"][0]["id"]
        self.assertFalse(plan.internal_panel_report(screens, "ok")["known"])
        screens = display()
        screens["outputs"][0]["modes"].append(copy.deepcopy(screens["outputs"][0]["modes"][0]))
        self.assertFalse(plan.internal_panel_report(screens, "ok")["known"])

    def test_headless_does_not_launch_qt(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(plan, "json_probe", return_value=(sensor(), "ok")) as probe:
            result = plan.rotation_report(self.sysfs)
        self.assertEqual(probe.call_count, 1)
        self.assertEqual(result["display"]["status"], "no-graphical-session")
        self.assertEqual(result["status"], "inspection-unavailable")

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "native Unix sockets unavailable")
    def test_wayland_socket_and_graphical_platform_are_required(self):
        endpoint = self.sysfs / "wayland-fixture"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(endpoint))
            env = {"XDG_SESSION_TYPE": "wayland", "XDG_RUNTIME_DIR": str(self.sysfs),
                   "WAYLAND_DISPLAY": endpoint.name}
            with patch.dict(os.environ, env, clear=True):
                self.assertTrue(plan.graphical_session_available())
            with patch.dict(os.environ, {**env, "QT_QPA_PLATFORM": "offscreen"}, clear=True):
                self.assertFalse(plan.graphical_session_available())
            with patch.dict(os.environ, {**env, "QT_QPA_PLATFORM": "xcb"}, clear=True):
                self.assertFalse(plan.graphical_session_available())
        endpoint.unlink()
        endpoint.write_text("a regular file is not a display")
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(plan.graphical_session_available())

    def test_probe_failure_and_invalid_json_are_explicit(self):
        cases = [subprocess.CompletedProcess([], 7, '{}', ''),
                 subprocess.CompletedProcess([], 0, 'bad', ''),
                 subprocess.CompletedProcess([], 0, ' ' * 262145, '')]
        for process in cases:
            with patch.object(plan.subprocess, "run", return_value=process):
                payload, status = plan.json_probe(["fixed-read-only-probe"])
                self.assertIsNone(payload)
                self.assertNotEqual(status, "ok")
        for error in (FileNotFoundError(), subprocess.TimeoutExpired([], 5)):
            with patch.object(plan.subprocess, "run", side_effect=error):
                self.assertIsNone(plan.json_probe(["fixed-read-only-probe"])[0])

    def test_daily_health_preserves_rotation_and_its_action(self):
        health_loader = importlib.machinery.SourceFileLoader(
            "rotation_health", str(ROOT / "system_files/usr/bin/moos-health"))
        health_spec = importlib.util.spec_from_loader(health_loader.name, health_loader)
        health = importlib.util.module_from_spec(health_spec)
        health_loader.exec_module(health)
        rotation = {"status": "driver-missing", "physical_rotation_tested": False}
        payload = {"rotation": rotation, "actions": [{"id": "rotation-driver-missing",
            "severity": "important", "title": "حساس الدوران | Rotation sensor",
            "detail": "تعريف مفقود | Driver missing", "url": ""}]}
        with patch.object(health, "tool", return_value=json.dumps(payload)):
            findings = []
            result = health.hardware_section(findings)
        self.assertEqual(result["rotation"], rotation)
        self.assertEqual(findings[0]["id"], "device-rotation-driver-missing")
        self.assertEqual(findings[0]["severity"], "warning")


if __name__ == "__main__":
    unittest.main()
