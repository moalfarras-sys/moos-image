#!/usr/bin/env python3
"""Gate the exact low-memory iPhone UTM net-installer release contract."""

from __future__ import annotations

import os
import pathlib
import plistlib
import subprocess
import sys
import tempfile
import zipfile


ROOT = pathlib.Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "artwork/generate_utm_installer.py"
WORKFLOW = ROOT / ".github/workflows/build-arm.yml"
BOOT = ROOT / "tests/boot_utm_net_installer.sh"
INSTALL = ROOT / "system_files/usr/libexec/moos-utm-net-install"


with tempfile.TemporaryDirectory(prefix="moos-utm-installer-gate-") as temporary:
    root = pathlib.Path(temporary)
    fake_bin = root / "bin"
    fake_bin.mkdir()

    qemu_img = fake_bin / "qemu-img"
    qemu_img.write_text(
        "#!/bin/sh\n"
        "[ \"$1\" = create ] || exit 2\n"
        ": > \"$4\"\n",
        encoding="utf-8",
    )
    qemu_img.chmod(0o755)

    cloud_localds = fake_bin / "cloud-localds"
    cloud_localds.write_text(
        "#!/bin/sh\n"
        "{ /bin/cat -- \"$2\"; /bin/echo ---META---; /bin/cat -- \"$3\"; } > \"$1\"\n",
        encoding="utf-8",
    )
    cloud_localds.chmod(0o755)

    installer = root / "recovery.qcow2"
    installer.write_bytes(b"QFI\xfb" + bytes(range(256)) * 64)
    bundle = root / "MoOS-UTM-Installer.utm"
    archive = root / "MoOS-UTM-Installer.utm.zip"
    env = os.environ.copy()
    env["PATH"] = str(fake_bin)
    generated = subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--installer-qcow2",
            str(installer),
            "--iphone",
            "--output",
            str(bundle),
            "--zip",
            str(archive),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert generated.returncode == 0, generated.stderr

    config = plistlib.loads((bundle / "config.plist").read_bytes())
    assert config["Backend"] == "QEMU"
    assert config["ConfigurationVersion"] == 4
    assert config["System"] == {
        "Architecture": "aarch64",
        "Target": "virt",
        "CPU": "default",
        "CPUFlagsAdd": [],
        "CPUFlagsRemove": [],
        "CPUCount": 2,
        "MemorySize": 1536,
        "JITCacheSize": 64,
        "ForceMulticore": False,
    }
    assert config["QEMU"]["UEFIBoot"] is True
    assert config["QEMU"]["Hypervisor"] is False
    assert config["Display"] == [{
        "Hardware": "virtio-ramfb",
        "DynamicResolution": False,
        "NativeResolution": False,
        "UpscalingFilter": "Linear",
        "DownscalingFilter": "Linear",
    }]
    assert config["Network"][0]["Mode"] == "Emulated"
    assert config["Network"][0]["Hardware"] == "virtio-net-pci"
    assert [drive["ImageName"] for drive in config["Drive"]] == [
        "installer.qcow2", "target.qcow2", "seed.iso"
    ]
    assert (bundle / "Data/installer.qcow2").read_bytes() == installer.read_bytes()
    assert (bundle / "Data/seed.iso").stat().st_size > 0
    assert (bundle / "Data/target.qcow2").is_file()

    readme = (bundle / "README-FIRST.txt").read_text(encoding="utf-8")
    assert "Emulated VLAN" in readme
    assert "OWNER-iPHONE-TEST-REQUIRED" in readme
    assert "Shared is fine" not in readme

    expected_members = {
        "MoOS-UTM-Installer.utm/config.plist",
        "MoOS-UTM-Installer.utm/README-FIRST.txt",
        "MoOS-UTM-Installer.utm/Data/installer.qcow2",
        "MoOS-UTM-Installer.utm/Data/moos-icon.png",
        "MoOS-UTM-Installer.utm/Data/target.qcow2",
        "MoOS-UTM-Installer.utm/Data/seed.iso",
    }
    with zipfile.ZipFile(archive) as zipped:
        assert set(zipped.namelist()) == expected_members
        assert zipped.testzip() is None

workflow = WORKFLOW.read_text(encoding="utf-8")
required_order = (
    "Boot the final QCOW2 through UEFI",
    "Build slim recovery installer disk for the proven candidate",
    "Package the iPhone UTM Net Installer",
    "Boot and visually prove the exact UTM Net Installer under TCG",
    "Upload proven UTM Net Installer",
    "Package the boot-proven ARM releases",
    "Boot, log in and visually prove the exact iPhone full bundle",
    "Upload ready-to-import UTM bundle",
)
positions = [workflow.index(name) for name in required_order]
assert positions == sorted(positions)
assert "MOOS_ARM_SKIP_VISUAL_GATE" not in workflow
assert "tests/boot_utm_net_installer.sh" in workflow
assert "tests/boot_arm_utm_bundle.sh" in workflow
assert ".digest = $digest | .product_sha = $product_sha" in workflow
assert "system_files/usr/share/moos/release/arm-latest.json" in workflow

boot = BOOT.read_text(encoding="utf-8")
for proof in (
    "config.plist",
    "MemorySize",
    "JITCacheSize",
    "virtio-ramfb",
    "tb-size=64",
    "MOOS_UTM_INSTALLER_MENU_READY",
    "screendump",
    "standard_deviation",
):
    assert proof in boot, f"net-installer boot proof lost {proof}"
assert "-device virtio-gpu-pci" in boot, \
    "stock-QEMU proof lost UTM virtio-ramfb's post-boot GPU equivalent"
assert "-device virtio-ramfb" not in boot, \
    "stock QEMU cannot launch UTM's patched virtio-ramfb model"

menu = (ROOT / "system_files/usr/libexec/moos-utm-installer-menu").read_text(
    encoding="utf-8"
)
assert "Emulated networking" in menu
assert "Shared networking" not in menu
assert "MOOS_UTM_INSTALLER_MENU_READY" in menu

install = INSTALL.read_text(encoding="utf-8")
for security_contract in (
    "cosign verify --key",
    "--enforce-container-sigpolicy",
    "--target-imgref",
    "ghcr.io/moalfarras-sys/moos-arm",
):
    assert security_contract in install

print("UTM iPhone net-installer gate passed")
