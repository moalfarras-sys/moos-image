#!/usr/bin/env python3
"""Generate MoOS-UTM-Installer.utm.zip — import once, net-install signed MoOS ARM.

The bundle ships:
  - installer.qcow2  small MoOS recovery environment (or full moos-arm recovery disk)
  - target.qcow2     empty persistent 32 GiB VirtIO disk
  - seed.iso         cloud-init that offers install / boot / recovery

On first boot the installer fetches ONLY the signed ghcr.io/moalfarras-sys/moos-arm
digest recorded in release/arm-latest.json (never GitHub source trees).
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import plistlib
import shutil
import subprocess
import sys
import uuid
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
ICON_SOURCE = ROOT / "system_files/usr/share/moos/moos-logo.png"
BUNDLE_NAME = "MoOS-UTM-Installer.utm"
TARGET_GIB = 32


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def random_mac() -> str:
    raw = bytearray(uuid.uuid4().bytes[:6])
    raw[0] = (raw[0] & 0xFC) | 0x02
    return ":".join(f"{b:02X}" for b in raw)


def build_config(*, iphone: bool) -> dict:
    return {
        "Backend": "QEMU",
        "ConfigurationVersion": 4,
        "Information": {
            "Name": "MoOS UTM Installer",
            "Notes": "Import once. First boot installs signed MoOS ARM to the target "
                     "disk over the network. Open Terminal for the serial console.",
            "IconCustom": True,
            "Icon": "moos-icon.png",
            "UUID": str(uuid.uuid4()).upper(),
        },
        "System": {
            "Architecture": "aarch64",
            "Target": "virt",
            "CPU": "default",
            "CPUFlagsAdd": [],
            "CPUFlagsRemove": [],
            "CPUCount": 2 if iphone else 4,
            "MemorySize": 3072 if iphone else 4096,
            "JITCacheSize": 0,
            "ForceMulticore": bool(iphone),
        },
        "QEMU": {
            "DebugLog": False,
            "UEFIBoot": True,
            "RNGDevice": True,
            "BalloonDevice": False,
            "TPMDevice": False,
            # iPhone / UTM SE has no Apple hypervisor — must use TCG/JIT.
            "Hypervisor": not iphone,
            "TSO": False,
            "RTCLocalTime": False,
            "PS2Controller": False,
            "AdditionalArguments": [],
        },
        "Input": {"UsbBusSupport": "3.0", "UsbSharing": False, "MaximumUsbShare": 3},
        "Sharing": {
            "DirectoryShareMode": "None",
            "DirectoryShareReadOnly": True,
            "ClipboardSharing": False,
        },
        "Display": [
            {
                "Hardware": "virtio-ramfb",
                "DynamicResolution": False,
                "NativeResolution": False,
                "UpscalingFilter": "Linear",
                "DownscalingFilter": "Linear",
            }
        ],
        "Drive": [
            {
                "ImageName": "installer.qcow2",
                "ImageType": "Disk",
                "Interface": "VirtIO",
                "InterfaceVersion": 1,
                "Identifier": str(uuid.uuid4()).upper(),
                "ReadOnly": False,
            },
            {
                "ImageName": "target.qcow2",
                "ImageType": "Disk",
                "Interface": "VirtIO",
                "InterfaceVersion": 1,
                "Identifier": str(uuid.uuid4()).upper(),
                "ReadOnly": False,
            },
            {
                "ImageName": "seed.iso",
                "ImageType": "CD",
                "Interface": "VirtIO",
                "InterfaceVersion": 1,
                "Identifier": str(uuid.uuid4()).upper(),
                "ReadOnly": True,
            },
        ],
        "Network": [
            {
                "Mode": "Shared",
                "Hardware": "virtio-net-pci",
                "MacAddress": random_mac(),
                "IsolateFromHost": False,
                "PortForward": [],
            }
        ],
        "Serial": [
            {
                "Mode": "Terminal",
                "Target": "Auto",
                "Terminal": {
                    "ForegroundColor": "#F4F7FF",
                    "BackgroundColor": "#07111F",
                    "Font": "Menlo",
                    "FontSize": 13,
                    "CursorBlink": False,
                },
            }
        ],
        "Sound": [{"Hardware": "intel-hda"}],
    }


def seed_user_data() -> str:
    return "\n".join(
        [
            "#cloud-config",
            "runcmd:",
            "  - [systemctl, enable, --now, NetworkManager]",
            "  - [systemctl, enable, --now, moos-utm-installer.service]",
            "final_message: MoOS UTM installer ready — choose Install from the menu",
        ]
    ) + "\n"


def build_seed_iso(data_dir: pathlib.Path, user_data: str, meta_data: str) -> pathlib.Path | None:
    seed = data_dir / "seed.iso"
    tmp_user = data_dir / "user-data"
    tmp_meta = data_dir / "meta-data"
    tmp_user.write_text(user_data, encoding="utf-8")
    tmp_meta.write_text(meta_data, encoding="utf-8")
    if shutil.which("cloud-localds"):
        try:
            subprocess.run(
                ["cloud-localds", str(seed), str(tmp_user), str(tmp_meta)],
                check=True,
                capture_output=True,
            )
            tmp_user.unlink(missing_ok=True)
            tmp_meta.unlink(missing_ok=True)
            seed.chmod(0o600)
            return seed
        except subprocess.CalledProcessError:
            pass
    return None


def create_sparse_qcow2(path: pathlib.Path, gib: int) -> None:
    if shutil.which("qemu-img"):
        subprocess.run(
            ["qemu-img", "create", "-f", "qcow2", str(path), f"{gib}G"],
            check=True,
        )
        return
    # Fallback: tiny placeholder — builder must replace with qemu-img create.
    path.write_bytes(b"")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / BUNDLE_NAME)
    parser.add_argument(
        "--installer-qcow2",
        type=pathlib.Path,
        required=True,
        help="MoOS ARM recovery/installer qcow2 (must contain moos-utm-net-install)",
    )
    parser.add_argument(
        "--zip",
        type=pathlib.Path,
        default=None,
        help="also write MoOS-UTM-Installer.utm.zip beside the bundle",
    )
    parser.add_argument(
        "--iphone",
        action="store_true",
        help="iPhone/UTM SE profile (Hypervisor=false, ForceMulticore=true)",
    )
    args = parser.parse_args()

    if not args.installer_qcow2.is_file():
        print(f"error: installer qcow2 missing: {args.installer_qcow2}", file=sys.stderr)
        return 1
    if not ICON_SOURCE.is_file():
        print(f"error: icon missing: {ICON_SOURCE}", file=sys.stderr)
        return 1

    bundle = args.output
    if bundle.exists() and any(bundle.iterdir()):
        print(f"error: bundle not empty: {bundle}", file=sys.stderr)
        return 1
    data = bundle / "Data"
    data.mkdir(parents=True)

    shutil.copy2(args.installer_qcow2, data / "installer.qcow2")
    target = data / "target.qcow2"
    create_sparse_qcow2(target, TARGET_GIB)

    with (bundle / "config.plist").open("wb") as handle:
        plistlib.dump(build_config(iphone=args.iphone), handle)
    shutil.copy2(ICON_SOURCE, data / "moos-icon.png")

    meta = f"instance-id: moos-utm-installer-{uuid.uuid4()}\nlocal-hostname: moos-installer\n"
    seed = build_seed_iso(data, seed_user_data(), meta)

    readme = bundle / "README-FIRST.txt"
    readme.write_text(
        "\n".join(
            [
                "MoOS UTM Installer — import this bundle ONCE in UTM.",
                "",
                "Disks:",
                "  installer.qcow2  recovery / net-install environment",
                "  target.qcow2     empty persistent MoOS disk (32 GiB sparse)",
                "",
                "First boot:",
                "  1. Connect network (Shared is fine on Mac/iPhone).",
                "  2. Open UTM Terminal — install logs appear on ttyAMA0.",
                "  3. Installer fetches the signed ghcr.io/moalfarras-sys/moos-arm digest",
                "     from release/arm-latest.json and verifies cosign.",
                "  4. Reboot; UEFI should prefer the target disk when MoOS is installed.",
                "",
                "Recovery:",
                "  Boot installer disk again for repair / reinstall (explicit wipe required).",
                "",
                "OWNER-iPHONE-TEST-REQUIRED",
                "  Physical iPhone retest is required before calling this bundle final.",
                "",
                f"installer_sha256={sha256_file(data / 'installer.qcow2')}",
                f"target_sha256={sha256_file(target)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    if args.zip:
        with zipfile.ZipFile(args.zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in bundle.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(bundle.parent))
        print(f"wrote {args.zip}")

    print(f"bundle ready: {bundle}")
    if seed is None:
        print("warning: seed.iso not built — run cloud-localds on Data/user-data + meta-data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
