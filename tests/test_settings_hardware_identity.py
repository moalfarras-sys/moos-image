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

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATUS = ROOT / "system_files/usr/libexec/moos-settings-status"
QML = ROOT / "system_files/usr/share/moos/apps/settings/main.qml"

status_src = STATUS.read_text(encoding="utf-8")
qml_src = QML.read_text(encoding="utf-8")

# Strip full-line comments so no assertion can be satisfied by prose describing
# the bug -- these files both discuss "MoOS device" in their comments.
status_code = "\n".join(
    l for l in status_src.splitlines() if not l.lstrip().startswith("#"))
qml_code = "\n".join(
    l for l in qml_src.splitlines() if not l.lstrip().startswith("//"))

assert '"MoOS device"' not in status_code, (
    "the backend invents a product name again; an unidentified CPU must return "
    "an empty string so the UI can say Unknown")
assert '"MoOS device"' not in qml_code, (
    "the Device page seeds a branded placeholder again")

tree = ast.parse(status_src)
functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
assert "cpu_name" in functions and "gpu_name" in functions, \
    f"missing hardware probes: {sorted({'cpu_name', 'gpu_name'} - functions)}"

# aarch64 support is the whole point: lscpu decodes what /proc/cpuinfo hides.
assert '"lscpu"' in status_code, (
    "cpu_name must consult lscpu; /proc/cpuinfo alone cannot name an ARM part")
assert "CPU implementer" in status_code and "ARM_IMPLEMENTERS" in status_code, (
    "cpu_name must still decode the implementer register as a last resort")

# One hardware authority: GPU facts come from moos-visual-tier, which already
# drives compositor policy. A second prober could disagree with it.
assert '"moos-visual-tier"' in status_code, (
    "gpu_name must ask moos-visual-tier rather than probing DRM a second time")
assert "lspci" not in status_code and "/sys/class/drm" not in status_code, (
    "a second GPU prober was added; use moos-visual-tier, the existing one")

assert '"gpu": gpu_name(),' in status_code, "the state document must carry gpu"
assert "win.status.gpu" in qml_code, "the Device page never renders the GPU"
assert re.search(r'local\("غير معروف",\s*"Unknown"\)', qml_code), \
    "an unidentified part must render as Unknown, not as a MoOS-branded name"

print("Settings hardware identity gate passed")
