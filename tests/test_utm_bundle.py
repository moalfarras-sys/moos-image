#!/usr/bin/env python3
"""Gate the secure, boot-proven UTM release bundle contract."""

import hashlib
import json
import os
import pathlib
import plistlib
import re
import subprocess
import sys
import tempfile
import uuid
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "artwork/generate_utm_bundle.py"
WORKFLOW = ROOT / ".github/workflows/build-arm.yml"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


script = GENERATOR.read_text(encoding="utf-8")

# Static security and UTM contract. The artifact is public: a password created
# by the CI generator would be shared by every installation of that release.
assert "secrets.token_urlsafe" not in script
assert not re.search(r"passwd:\s*[\"']?[A-Za-z0-9]{6,}", script), \
    "a literal password must never appear in the generator"
assert "type: RANDOM" in script
assert "password: RANDOM" not in script
assert "expire: false" in script
assert "expire: true" not in script
assert "ssh_pwauth: false" in script, \
    "the public bundle password must be console-only; SSH remains key-only"
assert '"ImageName": "seed.iso"' in script
assert '"ImageName": "moos-arm.qcow2"' in script
assert '"Architecture": "aarch64"' in script
assert '"ConfigurationVersion": 4' in script
assert '"Backend": "QEMU"' in script
assert '"MemorySize": 4096' in script
assert '"UEFIBoot": True' in script
assert '"Mode": "Terminal"' in script
assert '"IconCustom": True' in script
assert "--expected-qcow2-sha256" in script
assert "--source-image-ref" in script
assert "manifest.json" in script
assert "actions/runs/" not in script and "actions?query" not in script

with tempfile.TemporaryDirectory(prefix="moos-utm-gate-") as tmp:
    root = pathlib.Path(tmp)
    fake_bin = root / "bin"
    fake_bin.mkdir()
    fake_cloud_localds = fake_bin / "cloud-localds"
    fake_cloud_localds.write_text(
        "#!/bin/sh\n"
        "{ /bin/cat -- \"$2\"; /bin/echo ---META---; /bin/cat -- \"$3\"; } > \"$1\"\n",
        encoding="utf-8",
    )
    fake_cloud_localds.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(fake_bin)

    # A skeleton remains honestly incomplete, but still includes a seed.
    skeleton = root / "skeleton.utm"
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(skeleton)],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert result.returncode == 2, result.stderr
    config = plistlib.loads((skeleton / "config.plist").read_bytes())
    assert set(config) == {
        "Backend", "ConfigurationVersion", "Information", "System", "QEMU",
        "Input", "Sharing", "Display", "Drive", "Network", "Serial", "Sound",
    }
    assert config["Backend"] == "QEMU"
    assert config["ConfigurationVersion"] == 4
    assert config["System"] == {
        "Architecture": "aarch64",
        "Target": "virt",
        "CPU": "default",
        "CPUFlagsAdd": [],
        "CPUFlagsRemove": [],
        "CPUCount": 4,
        "MemorySize": 4096,
        "JITCacheSize": 0,
        "ForceMulticore": False,
    }
    assert config["QEMU"]["UEFIBoot"] is True
    assert config["QEMU"]["RNGDevice"] is True
    assert config["QEMU"]["Hypervisor"] is True
    assert config["QEMU"]["AdditionalArguments"] == []
    assert set(config["QEMU"]) == {
        "DebugLog", "UEFIBoot", "RNGDevice", "BalloonDevice", "TPMDevice",
        "Hypervisor", "TSO", "RTCLocalTime", "PS2Controller",
        "AdditionalArguments",
    }
    assert config["Input"] == {
        "UsbBusSupport": "3.0",
        "UsbSharing": False,
        "MaximumUsbShare": 3,
    }
    assert config["Sharing"] == {
        "DirectoryShareMode": "None",
        "DirectoryShareReadOnly": True,
        "ClipboardSharing": False,
    }
    assert config["Information"]["IconCustom"] is True
    assert config["Information"]["Icon"] == "moos-icon.png"
    uuid.UUID(config["Information"]["UUID"])
    assert (skeleton / "Data/moos-icon.png").is_file()
    assert config["Display"] == [{
        "Hardware": "virtio-ramfb",
        "DynamicResolution": False,
        "NativeResolution": False,
        "UpscalingFilter": "Linear",
        "DownscalingFilter": "Linear",
    }]
    assert [drive["ImageName"] for drive in config["Drive"]] == [
        "moos-arm.qcow2", "seed.iso"
    ]
    for drive, image_type, read_only in zip(
        config["Drive"], ("Disk", "CD"), (False, True), strict=True
    ):
        assert drive["ImageType"] == image_type
        assert drive["Interface"] == "VirtIO"
        assert drive["InterfaceVersion"] == 1
        assert drive["ReadOnly"] is read_only
        uuid.UUID(drive["Identifier"])
    assert config["Serial"][0]["Mode"] == "Terminal"
    assert config["Serial"][0]["Target"] == "Auto"
    assert set(config["Serial"][0]["Terminal"]) == {
        "ForegroundColor", "BackgroundColor", "Font", "FontSize", "CursorBlink",
    }
    assert config["Network"][0]["Hardware"] == "virtio-net-pci"
    assert config["Network"][0]["PortForward"] == []
    assert set(config["Network"][0]) == {
        "Mode", "Hardware", "MacAddress", "IsolateFromHost", "PortForward",
    }
    assert re.fullmatch(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}", config["Network"][0]["MacAddress"])
    first_mac_octet = int(config["Network"][0]["MacAddress"].split(":")[0], 16)
    assert first_mac_octet & 0x02 and not first_mac_octet & 0x01
    assert config["Sound"] == [{"Hardware": "intel-hda"}]
    skeleton_readme = (skeleton / "README-FIRST.txt").read_text(encoding="utf-8")
    assert "actions/workflows/build-arm.yml" in skeleton_readme
    assert "VM-unique password" in skeleton_readme
    assert "one-time password is" not in skeleton_readme

    # The fake seed is the user-data payload. It must ask the guest to generate
    # a password, never contain one produced by the public release job.
    seed_payload = (skeleton / "Data/seed.iso").read_text(encoding="utf-8")
    assert "type: RANDOM" in seed_payload
    assert "password: RANDOM" not in seed_payload
    assert "expire: false" in seed_payload
    assert "expire: true" not in seed_payload
    assert "ssh_pwauth: false" in seed_payload
    assert f"instance-id: moos-arm-utm-{config['Information']['UUID'].lower()}" in seed_payload

    # A complete bundle is bound to the exact QCOW2 that passed boot proof.
    qcow = root / "release.qcow2"
    qcow.write_bytes(b"QFI\xfb" + bytes(range(256)) * 32)
    expected_sha = sha256(qcow)
    source_ref = "ghcr.io/moalfarras-sys/moos-arm@sha256:" + "a" * 64
    bundle = root / "MoOS-ARM.utm"
    complete = subprocess.run(
        [
            sys.executable, str(GENERATOR),
            "--qcow2", str(qcow),
            "--expected-qcow2-sha256", expected_sha,
            "--source-image-ref", source_ref,
            "--output", str(bundle),
        ],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert complete.returncode == 0, complete.stderr
    complete_config = plistlib.loads((bundle / "config.plist").read_bytes())
    readme_path = bundle / "README-FIRST.txt"
    readme = readme_path.read_text(encoding="utf-8")
    assert "VM-unique password" in readme
    assert "one-time password is" not in readme
    assert "password: RANDOM" not in readme

    copied_qcow = bundle / "Data/moos-arm.qcow2"
    assert sha256(copied_qcow) == expected_sha
    manifest_text = (bundle / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    assert manifest["source_image"] == source_ref
    assert manifest["disk"] == {
        "path": "Data/moos-arm.qcow2",
        "sha256": expected_sha,
        "bytes": qcow.stat().st_size,
    }
    assert manifest["seed"]["volume"] == "cidata"
    assert manifest["seed"]["credential"] == "generated-in-guest-console"
    assert manifest["seed"]["ssh_password_authentication"] is False
    assert manifest["seed"]["password_expired_at_greeter"] is False
    assert manifest["icon"]["path"] == "Data/moos-icon.png"
    assert manifest["icon"]["sha256"] == sha256(bundle / "Data/moos-icon.png")

    zip_path = root / "MoOS-ARM.utm.zip"
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path) as archive:
        assert set(archive.namelist()) == {
            "MoOS-ARM.utm/config.plist",
            "MoOS-ARM.utm/README-FIRST.txt",
            "MoOS-ARM.utm/manifest.json",
            "MoOS-ARM.utm/Data/moos-arm.qcow2",
            "MoOS-ARM.utm/Data/seed.iso",
            "MoOS-ARM.utm/Data/moos-icon.png",
        }
        archived_manifest = json.loads(
            archive.read("MoOS-ARM.utm/manifest.json").decode("utf-8")
        )
        assert archived_manifest["disk"]["sha256"] == expected_sha
        assert hashlib.sha256(
            archive.read("MoOS-ARM.utm/Data/moos-arm.qcow2")
        ).hexdigest() == expected_sha

    # Wrong proof digest must fail before a usable bundle is created.
    wrong_bundle = root / "wrong.utm"
    wrong = subprocess.run(
        [
            sys.executable, str(GENERATOR),
            "--qcow2", str(qcow),
            "--expected-qcow2-sha256", "0" * 64,
            "--source-image-ref", source_ref,
            "--output", str(wrong_bundle),
        ],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert wrong.returncode == 1
    assert not wrong_bundle.exists()

    # Two generated bundles have independent VM and device identities. Their
    # credentials are generated later, inside their respective guests.
    second_bundle = root / "Second.utm"
    second = subprocess.run(
        [
            sys.executable, str(GENERATOR),
            "--qcow2", str(qcow),
            "--expected-qcow2-sha256", expected_sha,
            "--source-image-ref", source_ref,
            "--output", str(second_bundle),
        ],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert second.returncode == 0, second.stderr
    second_config = plistlib.loads((second_bundle / "config.plist").read_bytes())
    assert complete_config["Information"]["UUID"] != second_config["Information"]["UUID"]
    assert complete_config["Network"][0]["MacAddress"] != second_config["Network"][0]["MacAddress"]

# The release workflow must package only after the exact disk passes boot.
workflow = WORKFLOW.read_text(encoding="utf-8")
assert workflow.index("Boot the final QCOW2 through UEFI") < workflow.index(
    "Package the boot-proven ARM releases"
)
assert "MOOS_ARM_PROVEN_SHA256" in workflow
assert "--expected-qcow2-sha256" in workflow
assert "MoOS-ARM.utm.zip" in workflow
assert "SHA256SUMS" in workflow
for required_path in (
    '      - "tests/boot_arm_qcow2.sh"',
    '      - "tests/verify_arm_runtime.sh"',
    '      - "tests/test_utm_bundle.py"',
    '      - "artwork/generate_utm_bundle.py"',
):
    assert workflow.count(required_path) == 2, \
        f"ARM push and PR filters must both include {required_path.strip()}"

print("UTM release bundle gate passed")
