"""Shared read-only hardware identity for MoOS Settings and Mo AI.

CPU names come from the kernel/util-linux; graphics classification belongs to
moos-visual-tier. No daemon, config writes, network access or privilege changes.
Unknown or malformed facts remain unknown instead of breaking the caller.
"""
from pathlib import Path
import json
import os
import re
import subprocess


def command(argv: list[str], timeout: float = 1.5) -> str:
    try:
        result = subprocess.run(argv, check=False, capture_output=True, text=True,
                                timeout=timeout, env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


# aarch64 exposes NO "model name" and NO "Hardware" line in /proc/cpuinfo -- only
# numeric "CPU implementer"/"CPU part" registers. The x86-only scan therefore fell
# through to the placeholder on every ARM machine, and the Device page told the
# owner of an Oracle A1 that their processor was a "MoOS device". lscpu decodes
# the same registers through util-linux's ARM table and answers "Neoverse-N1",
# which is what the hardware actually is.
ARM_IMPLEMENTERS = {
    "0x41": "ARM", "0x42": "Broadcom", "0x43": "Cavium", "0x44": "DEC",
    "0x4e": "NVIDIA", "0x50": "APM", "0x51": "Qualcomm", "0x53": "Samsung",
    "0x56": "Marvell", "0x61": "Apple", "0x69": "Intel", "0xc0": "Ampere",
}


def cpu_name() -> str:
    """The processor's real identity, or an honest blank -- never a fake name."""
    try:
        implementer = part = ""
        for line in Path("/proc/cpuinfo").read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if line.startswith(("model name", "Hardware")) and ":" in line:
                return re.sub(r"\s+", " ", line.split(":", 1)[1].strip())
            if line.startswith("CPU implementer") and ":" in line:
                implementer = line.split(":", 1)[1].strip().lower()
            elif line.startswith("CPU part") and ":" in line:
                part = line.split(":", 1)[1].strip()
    except OSError:
        implementer = part = ""

    # util-linux carries the implementer/part -> name table; prefer it.
    for line in command(["lscpu"], timeout=2.0).splitlines():
        if line.startswith("Model name:"):
            value = re.sub(r"\s+", " ", line.split(":", 1)[1].strip())
            if value and value != "-":
                return value

    # Last resort before giving up: name the vendor we decoded ourselves rather
    # than inventing a product name.
    vendor = ARM_IMPLEMENTERS.get(implementer, "")
    if vendor and part:
        return f"{vendor} {part}"
    if vendor:
        return vendor
    return ""


def gpu_name() -> str:
    """Graphics identity from moos-visual-tier, the one hardware prober.

    The Device page had no GPU field at all. Rather than grow a second probe
    that could disagree with the tier that actually drives compositor policy,
    this asks that tool and renders its answer.
    """
    raw = command(["moos-visual-tier", "--json"], timeout=4.0)
    if not raw:
        return ""
    try:
        payload = json.loads(raw)
        facts = payload.get("facts", {}) if isinstance(payload, dict) else {}
    except ValueError:
        return ""
    if not isinstance(facts, dict):
        return ""
    raw_drivers = facts.get("gpu_drivers")
    drivers = ([d for d in raw_drivers
                if isinstance(d, str) and d and d != "faux_driver"]
               if isinstance(raw_drivers, list) else [])
    gpu_class = facts.get("gpu_class")
    if not isinstance(gpu_class, str) or gpu_class not in {"software", "virtual", "integrated", "discrete"}:
        gpu_class = ""
    if drivers:
        label = ", ".join(drivers)
        return f"{label} ({gpu_class})" if gpu_class else label
    return gpu_class

