import pathlib
#!/usr/bin/env python3
"""Black-box hardware-plan tests with deterministic fake host commands."""
from pathlib import Path
import json
import importlib.machinery
import importlib.util
import os
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "system_files/usr/bin/moos-device-plan"


def clean_firmware_report(status=None):
    if status is not None:
        status.update(firmware_known=True, firmware_status="no-updates",
                      kernel_journal_known=True, kernel_journal_status="ok")
    return [], []


def executable(path: Path, shell_body: str, windows_body: str) -> None:
    if os.name == "nt":
        path = path.with_suffix(".cmd")
        path.write_text("@echo off\r\n" + windows_body, encoding="utf-8")
    else:
        path.write_text("#!/bin/sh\n" + shell_body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


if os.name == "nt":
    # Windows cannot directly execute the extensionless Linux helper or the
    # extensionless fake commands used by the black-box branch below. Import
    # the same production file and replace only its host probes; CI/Linux still
    # exercises the real process boundary.
    loader = importlib.machinery.SourceFileLoader("moos_device_plan", str(PLAN))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)

    lspci = """01:00.0 VGA compatible controller [0300]: NVIDIA Corporation TU104 [10de:1e81]
\tKernel driver in use: nouveau
04:00.0 Ethernet controller [0200]: Realtek [10ec:8125]
\tKernel driver in use: r8169"""

    def fake_run(*args, timeout=12):
        if args and args[0] == "lspci":
            return lspci
        if args and args[0] == "bootc":
            return '{"status":"ok"}'
        if args and args[0] == "mokutil":
            return "SecureBoot enabled"
        return ""

    module.run = fake_run
    module.flatpak_installed = lambda _app_id: False
    module.firmware_report = clean_firmware_report
    module.i2c_driver_gaps = lambda: []
    data = module.detect()
else:
    with tempfile.TemporaryDirectory() as tmp:
        bindir = Path(tmp)
        executable(bindir / "lspci", """cat <<'EOF'
01:00.0 VGA compatible controller [0300]: NVIDIA Corporation TU104 [10de:1e81]
\tKernel driver in use: nouveau
04:00.0 Ethernet controller [0200]: Realtek [10ec:8125]
\tKernel driver in use: r8169
EOF
""", """echo 01:00.0 VGA compatible controller [0300]: NVIDIA Corporation TU104 [10de:1e81]
echo   Kernel driver in use: nouveau
echo 04:00.0 Ethernet controller [0200]: Realtek [10ec:8125]
echo   Kernel driver in use: r8169
""")
        executable(bindir / "flatpak", "exit 1\n", "exit /b 1\r\n")
        executable(
            bindir / "bootc",
            "printf '%s\\n' '{\"status\":\"ok\"}'\n",
            "echo {\"status\":\"ok\"}\r\n",
        )
        executable(
            bindir / "mokutil",
            "echo 'SecureBoot enabled'\n",
            "echo SecureBoot enabled\r\n",
        )
        env = dict(os.environ)
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
        # This block simulates an x86 NVIDIA desktop, and moos-device-plan is architecture-aware
        # (the NVIDIA image is published for x86_64 only). Reading the HOST's CPU here made the
        # whole black-box section pass on a CI runner and fail on the maintainer's aarch64
        # machine. Say which machine is being simulated; the ARM branch is asserted separately
        # below, by importing the module and passing `machine` directly.
        env["MOOS_DEVICE_PLAN_MACHINE"] = "x86_64"
        data = json.loads(subprocess.check_output([str(PLAN)], text=True, env=env))

assert data["gpu_vendor"] == "nvidia"
assert data["driver"] == "nouveau", data["driver"]
assert data["health"] == "action-needed"
assert data["actions"][0]["url"] == "moos://do/install-nvidia"
assert "r8169" not in data["driver"]
assert data["driver_status"] == "NVIDIA detected; optimized image required", data["driver_status"]
# Mo AI renders the status line verbatim; an Arabic session must get Arabic.
assert any("\u0600" <= ch <= "\u06ff" for ch in data["driver_status_ar"]), data["driver_status_ar"]

# The NVIDIA image is published only for x86_64. Some ARM boards expose an
# NVIDIA PCI display device too; the hardware card must never offer an x86 image
# switch there even when the driver is absent.
loader = importlib.machinery.SourceFileLoader("moos_device_plan_arm", str(PLAN))
spec = importlib.util.spec_from_loader(loader.name, loader)
arm_module = importlib.util.module_from_spec(spec)
loader.exec_module(arm_module)
arm_module.run = lambda *args, **kwargs: (
    "01:00.0 VGA compatible controller: NVIDIA Corporation Device" if args[0] == "lspci"
    else '{"status":"ok"}' if args[0] in ("bootc", "rpm-ostree")
    else ""
)
arm_module.flatpak_installed = lambda _app_id: False
arm_module.firmware_report = clean_firmware_report
arm_module.i2c_driver_gaps = lambda: []
arm = arm_module.detect(machine="aarch64")
assert arm["architecture"] == "aarch64"
assert all(action.get("url") != "moos://do/install-nvidia" for action in arm["actions"])
assert "ARM" in arm["driver_status"], arm["driver_status"]

print("MoOS device-plan test passed")

# A healthy PCI GPU/network must not hide the V3's unbound ACPI/I2C sensor.
# Execute production detection against private sysfs; adapters, unrelated USB
# interfaces and another board's unknown client must not become false warnings.
with tempfile.TemporaryDirectory() as tmp:
    sysfs = Path(tmp)
    clients = sysfs / "bus/i2c/devices"
    clients.mkdir(parents=True)
    for name in ("i2c-0", "i2c-3", "i2c-PNP0C50:00", "i2c-UNKNOWN:00"):
        (clients / name).mkdir()
    loader = importlib.machinery.SourceFileLoader("moos_device_plan_i2c", str(PLAN))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    sensor_module = importlib.util.module_from_spec(spec)
    loader.exec_module(sensor_module)
    sensor_module.run = lambda *args, **kwargs: (
        "c4:00.0 VGA compatible controller: AMD Radeon\n\tKernel driver in use: amdgpu"
        if args[0] == "lspci" else "")
    sensor_module.firmware_report = clean_firmware_report
    sensor_module.flatpak_installed = lambda _app_id: False
    probe = sensor_module.i2c_driver_gaps
    sensor_module.i2c_driver_gaps = lambda: probe(sysfs)
    assert sensor_module.detect()["driver_gaps"] == []
    client = clients / "i2c-SMOCF05:00"
    client.mkdir()
    missing = sensor_module.detect()
    assert missing["health"] == "action-needed", missing
    assert len(missing["driver_gaps"]) == 1 and "SMOCF05" in missing["driver_gaps"][0]
    assert any(a["id"] == "driver-gap" for a in missing["actions"]), missing
    driver = sysfs / "bus/i2c/drivers/st_lsm6dsx_i2c"
    driver.mkdir(parents=True)
    (client / "driver").symlink_to(driver, target_is_directory=True)
    bound = sensor_module.detect()
    assert bound["driver_gaps"] == [] and bound["health"] == "ready", bound
    (client / "driver").unlink()
    (client / "driver").symlink_to(sysfs / "absent-driver", target_is_directory=True)
    assert "SMOCF05" in sensor_module.detect()["driver_gaps"][0]
print("device-plan I2C missing/bound/broken-link/unrelated-device controls passed")

# A PCI probe failure is unknown evidence, never a clean bill of health.
arm_module.run = lambda *args, **kwargs: ""
unknown = arm_module.detect(machine="aarch64")
assert unknown["health"] == "attention" and unknown["pci_known"] is False, unknown
assert any(a["id"] == "hardware-unavailable" for a in unknown["actions"])

# A rollback/staged NVIDIA deployment cannot identify the running base edition.
base = "ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos:latest"
nvidia = base.replace("/moos:", "/moos-nvidia:")
for deployed, other in ((base, nvidia), (nvidia, base)):
    payload = {"deployments": [
        {"staged": True, "container-image-reference": other},
        {"booted": True, "container-image-reference": deployed},
        {"booted": False, "container-image-reference": other}]}
    assert arm_module.booted_image_reference(json.dumps(payload)) == deployed
    bootc_payload = {"status": {"booted": {"image": {"image": {"image": deployed}}},
                               "staged": {"image": {"image": {"image": other}}}}}
    assert arm_module.booted_image_reference(json.dumps(bootc_payload)) == deployed
    # A readable but unusable bootc reply must still fall back to rpm-ostree.
    arm_module.run = lambda *args, **kwargs: (
        "01:00.0 VGA compatible controller: NVIDIA\n\tKernel driver in use: nvidia"
        if args[0] == "lspci" else '{"status":"ok"}' if args[0] == "bootc"
        else json.dumps(payload) if args[0] == "rpm-ostree" else "")
    detected = arm_module.detect(machine="x86_64")
    assert detected["nvidia_image"] is (deployed == nvidia), detected
for malformed in ("[]", "null", '{"deployments":null}', '{"status":[]}'):
    assert arm_module.booted_image_reference(malformed) == ""

from unittest.mock import patch
loader = importlib.machinery.SourceFileLoader("moos_device_plan_firmware", str(PLAN))
spec = importlib.util.spec_from_loader(loader.name, loader)
firmware_module = importlib.util.module_from_spec(spec)
loader.exec_module(firmware_module)
for payload in ([], None, {"Devices": None}, {"Devices": [None, [], "bad"]},
                {"Devices": [{"Name": "device", "Releases": "bad"}]},
                {"Devices": [{"Name": "device", "Releases": [None, 2]}]},
                {"Devices": [{"Name": 1, "Releases": [{"Version": "2"}]}]}):
    with patch.object(firmware_module.shutil, "which", return_value="fwupdmgr"), \
         patch.object(firmware_module.subprocess, "run", side_effect=[
             subprocess.CompletedProcess([], 0, json.dumps(payload)),
             subprocess.CompletedProcess([], 0, "")]):
        assert firmware_module.firmware_report() == ([], [])
with patch.object(firmware_module.shutil, "which", return_value="fwupdmgr"), \
     patch.object(firmware_module.subprocess, "run", side_effect=[
         subprocess.CompletedProcess([], 0, json.dumps({"Devices": [
             {"Name": "Controller", "Version": "1", "Releases": [{"Version": "2"}]}]})),
         subprocess.CompletedProcess([], 0, "Direct firmware load for test.bin failed")]):
    assert firmware_module.firmware_report() == (["Controller 1 → 2"], ["test.bin"])
print("device-plan unknown PCI, booted-only image and firmware JSON controls passed")


# Vendor words must not match class prose: "compatible" contains "ati".
# Run the actual detector and fake command processes, including mixed case.
if os.name != "nt":
    import shlex
    import sys

    def vendor_process_case(plan, label):
        with tempfile.TemporaryDirectory(prefix="moos-vendor-process-") as temporary:
            private = Path(temporary)
            for name, raw, code in (
                    ("lspci", "01:00.0 " + label + "\n\tKernel driver in use: fixture", 0),
                    ("fwupdmgr", '{"Devices":[]}', 0),
                    ("journalctl", "", 0),
                    ("flatpak", "", 1), ("bootc", "", 1),
                    ("rpm-ostree", "", 1), ("mokutil", "", 1)):
                executable(private / name,
                           "printf '%s\\n' " + shlex.quote(raw) + "\nexit " + str(code) + "\n", "")
            env = dict(os.environ, PATH=str(private), MOOS_DEVICE_PLAN_MACHINE="x86_64",
                       DBUS_SESSION_BUS_ADDRESS="unix:path="+str(private/"no-bus"))
            return json.loads(subprocess.check_output([sys.executable, str(plan)],
                                                       text=True, env=env, timeout=5))

    vendor_cases = (
        ("VGA compatible controller: Intel Corporation Graphics", "intel"),
        ("vGa CoMpAtIbLe controller: iNtEl Corporation Graphics", "intel"),
        ("3D controller: NVIDIA Corporation Graphics", "nvidia"),
        ("VGA compatible controller: nViDiA Corporation Graphics", "nvidia"),
        ("VGA compatible controller: Advanced Micro Devices, Inc. [AMD/ATI]", "amd"),
        ("vga COMPATIBLE controller: aMd Radeon Graphics", "amd"),
        ("VGA compatible controller: ATI Technologies Graphics", "amd"),
        ("Display controller: aTi Technologies Graphics", "amd"),
        ("VGA compatible controller: Unknown Vendor Graphics", "unknown"),
        ("vGa cOmPaTiBlE controller: QEMU Virtio Graphics", "unknown"),
        ("VGA compatible controller: Imagination Graphics", "unknown"),
    )
    for label, expected in vendor_cases:
        detected = vendor_process_case(PLAN, label)
        assert detected["gpu_vendor"] == expected, (label, expected, detected)
    print(f"device-plan vendor word-boundary process controls passed ({len(vendor_cases)})")


# Every device-plan title reaches the owner's screen through Mo AI's diagnostic
# card. Four of the six carried "عربي | English"; two shipped English-only and
# showed up untranslated inside an otherwise fully Arabic Mo AI on the live
# session. The convention is only a convention if something enforces it.
import re as _re
_plan = (pathlib.Path(__file__).resolve().parent.parent
         / "system_files/usr/bin/moos-device-plan").read_text(encoding="utf-8")
_titles = _re.findall(r'"title":\s*"([^"]+)"', _plan)
assert _titles, "no device-plan titles found"
_english_only = [t for t in _titles if not _re.search(r"[؀-ۿ]", t)]
assert not _english_only, (
    "these titles reach an Arabic screen untranslated; follow the "
    f"\"عربي | English\" convention the others use: {_english_only}")
print(f"device-plan bilingual title gate passed ({len(_titles)} titles)")

# Execute the real detector and fake external processes; no host fwupd/journal,
# session bus or firmware writes. The import seam isolates only sysfs I2C state.
if os.name != "nt":
    import sys
    import shlex

    def firmware_process_case(plan, fw_code=0, fw_raw='{"Devices":[]}',
                              journal_code=0, journal_raw="", pci_gap=False):
        with tempfile.TemporaryDirectory(prefix="moos-firmware-process-") as temporary:
            private = Path(temporary)
            def command(name, raw, code=0):
                executable(private / name,
                           "printf '%s\\n' " + shlex.quote(raw) + "\nexit " + str(code) + "\n", "")
            command("lspci", "01:00.0 VGA compatible controller: Intel GPU" +
                    ("" if pci_gap else "\n\tKernel driver in use: i915"))
            for name in ("bootc", "rpm-ostree", "mokutil"):
                command(name, "", 1)
            command("flatpak", "", 1)
            if fw_code is not None:
                command("fwupdmgr", fw_raw, fw_code)
            command("journalctl", journal_raw, journal_code)
            wrapper = """import importlib.machinery,importlib.util,json,sys
loader=importlib.machinery.SourceFileLoader('private_plan',sys.argv[1])
spec=importlib.util.spec_from_loader(loader.name,loader)
module=importlib.util.module_from_spec(spec);loader.exec_module(module)
module.i2c_driver_gaps=lambda: []
print(json.dumps(module.detect(machine='x86_64')))
"""
            env = dict(os.environ, PATH=str(private), DBUS_SESSION_BUS_ADDRESS="unix:path="+str(private/"no-bus"))
            return json.loads(subprocess.check_output([sys.executable, "-c", wrapper, str(plan)],
                                                       text=True, env=env, timeout=5))

    def confidence_contract(plan):
        count = 0
        for fw_code, raw in ((1, '{"Devices":[]}'), (0, "bad-json"), (0, ""),
                             (0, "[]"), (0, "{}"), (0, '{"Devices":null}'),
                             (0, '{"Devices":[null]}'), (2, "bad-json"),
                             (0, '{"Devices":[{"Name":"device","Releases":"bad"}]}'),
                             (None, "")):
            result = firmware_process_case(plan, fw_code, raw)
            assert result["health"] == "attention", result
            assert result["firmware_known"] is False and result["kernel_journal_known"] is True, result
            action = next(a for a in result["actions"] if a["id"] == "firmware-inspection-unavailable")
            assert any("\u0600" <= c <= "\u06ff" for c in action["detail"]) and "unconfirmed" in action["detail"]
            count += 1
        for fw_code, raw in ((0, '{"Devices":[]}'), (2, ""),
                             (2, '{"Devices":[]}'),
                             (2, '{"Error":{"Domain":"fwupd-error-quark","Code":9,"Message":"لا عمل مطلوب"}}')):
            result = firmware_process_case(plan, fw_code, raw)
            assert result["health"] == "ready" and result["firmware_known"] is True, result
            assert result["kernel_journal_known"] is True and not result["firmware_updates"], result
            count += 1
        updates = '{"Devices":[{"Name":"Controller","Version":"1","Releases":[{"Version":"2"}]}]}'
        result = firmware_process_case(plan, 0, updates)
        assert result["firmware_updates"] == ["Controller 1 → 2"] and result["health"] == "attention", result
        assert result["firmware_known"] is True and result["firmware_status"] == "updates", result
        count += 1
        result = firmware_process_case(plan, journal_raw="Direct firmware load for test.bin failed")
        assert result["missing_firmware"] == ["test.bin"] and result["health"] == "attention", result
        assert result["kernel_journal_known"] is True, result
        count += 1
        for gap in (False, True):
            result = firmware_process_case(plan, 1, "{}", journal_code=1,
                                           journal_raw="Direct firmware load for partial.bin failed", pci_gap=gap)
            assert result["health"] == ("action-needed" if gap else "attention"), result
            assert result["firmware_known"] is False and result["kernel_journal_known"] is False, result
            assert result["missing_firmware"] == ["partial.bin"], result
            assert any(a["id"] == "firmware-missing" for a in result["actions"]), result
            if gap:
                assert result["driver_gaps"] and any(a["id"] == "driver-gap" for a in result["actions"]), result
            count += 1
        # A real update observed before a malformed entry stays actionable,
        # while confidence remains unknown for the incomplete firmware query.
        partial_payload = json.loads(updates)
        partial_payload["Devices"].append({"Name": 1})
        partial_updates = json.dumps(partial_payload)
        result = firmware_process_case(plan, 0, partial_updates)
        assert result["firmware_updates"] and result["firmware_known"] is False, result
        assert result["health"] == "attention", result
        count += 1
        return count

    print(f"device-plan firmware confidence process controls passed ({confidence_contract(PLAN)})")

# Timeouts and missing executables are distinct from a successful empty report.
for failed_probe, failure, expected in (
        ("firmware", subprocess.TimeoutExpired("fwupdmgr", 25), "timeout"),
        ("firmware", FileNotFoundError("private missing binary"), "unavailable"),
        ("journal", subprocess.TimeoutExpired("journalctl", 20), "timeout"),
        ("journal", FileNotFoundError("private missing binary"), "unavailable")):
    diagnostics = {}
    ok_firmware = subprocess.CompletedProcess([], 0, '{"Devices":[]}')
    ok_journal = subprocess.CompletedProcess([], 0, "")
    calls = [failure, ok_journal] if failed_probe == "firmware" else [ok_firmware, failure]
    with patch.object(firmware_module.shutil, "which", return_value="fwupdmgr"), \
         patch.object(firmware_module.subprocess, "run", side_effect=calls):
        assert firmware_module.firmware_report(diagnostics) == ([], [])
    known = "firmware_known" if failed_probe == "firmware" else "kernel_journal_known"
    state = "firmware_status" if failed_probe == "firmware" else "kernel_journal_status"
    assert diagnostics[known] is False and diagnostics[state] == expected, diagnostics
print("device-plan firmware/journal timeout and unavailable controls passed (4)")
