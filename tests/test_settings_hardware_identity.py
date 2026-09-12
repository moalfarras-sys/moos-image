#!/usr/bin/env python3
"""The Device page must name real hardware, or admit it cannot.

Measured on the live Oracle A1: the page said the processor was a "MoOS device".
aarch64 exposes no "model name" and no "Hardware" line in /proc/cpuinfo -- only
numeric CPU implementer/part registers -- so the x86-only scan fell through to a
branded placeholder on every ARM machine. lscpu decodes the same registers and
answers "Neoverse-N1". There was also no GPU field at all.

A placeholder that looks like a product name is worse than an empty field: it
tells the owner something false about their own machine.
"""

import ast
import pathlib
import re
import sys
import json
import runpy
import subprocess
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATUS = ROOT / "system_files/usr/libexec/moos-settings-status"
QML = ROOT / "system_files/usr/share/moos/apps/settings/main.qml"

HARDWARE = ROOT / "system_files/usr/lib/moos/moos_hardware.py"
status_src = STATUS.read_text(encoding="utf-8")
hardware_src = HARDWARE.read_text(encoding="utf-8")
qml_src = QML.read_text(encoding="utf-8")

# Strip full-line comments so no assertion can be satisfied by prose describing
# the bug -- these files both discuss "MoOS device" in their comments.
status_code = "\n".join(
    l for l in status_src.splitlines() if not l.lstrip().startswith("#"))
qml_code = "\n".join(
    l for l in qml_src.splitlines() if not l.lstrip().startswith("//"))

hardware_code = "\n".join(l for l in hardware_src.splitlines() if not l.lstrip().startswith("#"))

assert '"MoOS device"' not in status_code + hardware_code, (
    "the backend invents a product name again; an unidentified CPU must return "
    "an empty string so the UI can say Unknown")
assert '"MoOS device"' not in qml_code, (
    "the Device page seeds a branded placeholder again")

tree = ast.parse(hardware_src)
functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
assert "cpu_name" in functions and "gpu_name" in functions, \
    f"missing hardware probes: {sorted({'cpu_name', 'gpu_name'} - functions)}"

# aarch64 support is the whole point: lscpu decodes what /proc/cpuinfo hides.
assert '"lscpu"' in hardware_code, (
    "cpu_name must consult lscpu; /proc/cpuinfo alone cannot name an ARM part")
assert "CPU implementer" in hardware_code and "ARM_IMPLEMENTERS" in hardware_code, (
    "cpu_name must still decode the implementer register as a last resort")

# One hardware authority: GPU facts come from moos-visual-tier, which already
# drives compositor policy. A second prober could disagree with it.
assert '"moos-visual-tier"' in hardware_code, (
    "gpu_name must ask moos-visual-tier rather than probing DRM a second time")
assert "lspci" not in status_code + hardware_code and "/sys/class/drm" not in hardware_code, (
    "a second GPU prober was added; use moos-visual-tier, the existing one")

assert '"gpu": gpu_name(),' in status_code, "the state document must carry gpu"
assert "win.status.gpu" in qml_code, "the Device page never renders the GPU"
assert re.search(r'local\("غير معروف",\s*"Unknown"\)', qml_code), \
    "an unidentified part must render as Unknown, not as a MoOS-branded name"

class HardwareIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = runpy.run_path(str(STATUS))
        cls.control = runpy.run_path(str(ROOT / "system_files/usr/bin/moai-control"))
        cls.hardware = cls.settings["hardware"]

    def test_x86_name_needs_no_subprocess(self):
        with patch.object(pathlib.Path, "read_text", return_value="model name : Example   CPU\n"), patch.object(self.hardware, "command") as command:
            self.assertEqual(self.hardware.cpu_name(), "Example CPU")
            command.assert_not_called()

    def test_arm_name_and_vendor_fallback(self):
        registers = "CPU implementer : 0x41\nCPU part : 0xd0c\n"
        with patch.object(pathlib.Path, "read_text", return_value=registers), patch.object(self.hardware, "command", return_value="Model name: Neoverse-N1") as command:
            self.assertEqual(self.hardware.cpu_name(), "Neoverse-N1")
            command.assert_called_once_with(["lscpu"], timeout=2.0)
        with patch.object(pathlib.Path, "read_text", return_value=registers), patch.object(self.hardware, "command", return_value=""):
            self.assertEqual(self.hardware.cpu_name(), "ARM 0xd0c")

    def test_unknown_cpu_stays_unknown(self):
        with patch.object(pathlib.Path, "read_text", side_effect=OSError), patch.object(self.hardware, "command", return_value=""):
            self.assertEqual(self.hardware.cpu_name(), "")

    def test_gpu_uses_existing_authority_and_tolerates_bad_data(self):
        for facts, expected in (({"gpu_drivers": ["nvidia"], "gpu_class": "discrete"}, "nvidia (discrete)"), ({"gpu_drivers": ["faux_driver"], "gpu_class": "software"}, "software"), ({"gpu_drivers": [None, 3, "virtio_gpu"], "gpu_class": "virtual"}, "virtio_gpu (virtual)")):
            with self.subTest(facts=facts), patch.object(self.hardware, "command", return_value=json.dumps({"facts": facts})) as command:
                self.assertEqual(self.hardware.gpu_name(), expected)
                command.assert_called_once_with(["moos-visual-tier", "--json"], timeout=4.0)
        for raw in ("", "invalid", "null", "[]", '{"facts": null}', '{"facts": []}', '{"facts":{"gpu_drivers":"nvidia","gpu_class":[]}}'):
            with self.subTest(raw=raw), patch.object(self.hardware, "command", return_value=raw):
                self.assertEqual(self.hardware.gpu_name(), "")

    def test_probe_failures_are_bounded_and_do_not_raise(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("lscpu", 2), UnicodeError()):
            with self.subTest(error=error), patch.object(subprocess, "run", side_effect=error):
                self.assertEqual(self.hardware.command(["lscpu"], timeout=2), "")
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "misleading output")):
            self.assertEqual(self.hardware.command(["lscpu"]), "")

    def test_real_settings_and_scan_agree_on_arm_without_host_actions(self):
        settings_scope = self.settings["full_state"].__globals__
        control_scope = self.control["scan"].__globals__
        self.assertIs(self.control["hardware"], self.hardware)
        settings_stubs = {name: (lambda: {}) for name in ("storage_state", "deployment_state", "destinations_state", "dynamic_state")}
        settings_stubs["command"] = lambda *a, **k: ""
        control_stubs = {name: (lambda: {}) for name in ("disk_usage", "installed_apps", "remote_state", "agent_state", "cached_plan")}
        os_release = {"PRETTY_NAME=": "MoOS", "VERSION=": "44.20260912.0"}
        control_stubs.update(_first_line=lambda path, prefix: os_release.get(prefix, "") if path == "/etc/os-release" else "",
                             command_exists=lambda *a: False)
        def probe(argv, **kwargs):
            if argv == ["lscpu"]:
                return "Model name: Neoverse-N1"
            if argv == ["moos-visual-tier", "--json"]:
                return json.dumps({"facts": {"gpu_class": "software", "gpu_drivers": []}})
            raise AssertionError(argv)
        with patch.dict(settings_scope, settings_stubs), patch.dict(control_scope, control_stubs), patch.object(pathlib.Path, "read_text", return_value="CPU implementer : 0x41\nCPU part : 0xd0c"), patch.object(self.hardware, "command", side_effect=probe), patch.object(subprocess, "run", side_effect=AssertionError("unexpected host command")):
            settings = self.settings["full_state"]()
            scan = self.control["scan"]()
        self.assertEqual(settings["schema"], 1)
        for field, expected in (("cpu", "Neoverse-N1"), ("gpu", "software")):
            self.assertEqual(settings[field], expected)
            self.assertEqual(scan[field], expected)
        # Mo AI's context names the OS and its release from these two fields; with the
        # version missing, a model asked for it invented a base distribution's instead.
        self.assertEqual((scan["os"], scan["version"]), ("MoOS", "44.20260912.0"))
        self.assertNotIn(".fc", scan["kernel"])


if __name__ == "__main__":
    unittest.main()
