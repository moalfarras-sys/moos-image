#!/usr/bin/env python3
"""Generate a ready-to-import MoOS-ARM.utm bundle for UTM on Apple silicon,
iPhone and iPad.

One authoritative generator replaces the three draft scripts this bundle
started as. The bundle it emits is HONEST about first boot: the ARM image
provisions its user through cloud-init NoCloud, exactly like the release
boot proof in tests/boot_arm_qcow2.sh — a UTM VM without a seed disk boots
to a login screen with no account on it. So the bundle always carries a
seed drive, and the seed is generated per bundle with a random one-time
password (or an SSH key), never a shared static one.

Usage:
  ./generate_utm_bundle.py [--qcow2 PATH] [--output DIR] [--ssh-key PATH]

Without --qcow2 the bundle is a skeleton: config.plist, README and an empty
Data/ the downloaded release qcow2 goes into. With --qcow2 the image is
copied in and the seed ISO is built when cloud-localds (or a mkisofs-family
tool) is available; otherwise the seed payloads are written to Data/ with
the exact command to finish them, and the script says so.
"""

from __future__ import annotations

import argparse
import pathlib
import plistlib
import secrets
import shutil
import subprocess
import sys
import zipfile

BUNDLE_NAME = "MoOS-ARM.utm"
SEED_VOLUME = "cidata"
README_NAME = "README-FIRST.txt"


def seed_user_data(ssh_key: str | None, password: str) -> str:
    # chpasswd with type:text hashes the random password inside the guest;
    # users[].passwd would need a pre-hashed value. expire:true forces a
    # change at first login, so the generated secret has a bounded life.
    lines = [
        "#cloud-config",
        "users:",
        "  - name: moos",
        "    gecos: MoOS",
        "    groups: [wheel]",
        "    shell: /bin/bash",
        "    lock_passwd: false",
    ]
    if ssh_key:
        lines += [
            "    ssh_authorized_keys:",
            f"      - {ssh_key}",
        ]
    lines += [
        "chpasswd:",
        "  expire: true",
        "  users:",
        "    - name: moos",
        f"      password: {password}",
        "      type: text",
        "ssh_pwauth: true",
    ]
    return "\n".join(lines) + "\n"


def build_config() -> dict:
    # UTM configuration schema v4 (iOS & macOS compatible).
    return {
        "ConfigurationVersion": 4,
        "Information": {
            "Name": "MoOS ARM",
            "Notes": "MoOS for aarch64 — MoOS UI. First boot creates the "
                     "'moos' user from the bundled cloud-init seed; the "
                     "one-time password is in README-FIRST.txt.",
            "IconCustom": False,
            "Icon": "linux",
        },
        "System": {
            "Architecture": "aarch64",
            "Target": "virt",
            "CPU": "default",
            "CPUCount": 4,
            "Memory": 3072,
            "JITCacheSize": 0,
            "ForceMulticore": False,
        },
        "Display": [
            {
                "Hardware": "virtio-gpu-pci",
                "Resolution": "1280x800",
                "UpscalingFilter": "Linear",
                "DownscalingFilter": "Linear",
            }
        ],
        "Drives": [
            {
                "ImageName": "moos-arm.qcow2",
                "Interface": "virtio",
                "ReadOnly": False,
            },
            {
                "ImageName": "seed.iso",
                "Interface": "virtio",
                "ReadOnly": True,
            },
        ],
        "Network": [
            {"Mode": "Emulated", "Hardware": "virtio-net-pci"}
        ],
        "Sound": [
            {"Hardware": "intel-hda"}
        ],
    }


def build_seed_iso(data_dir: pathlib.Path, user_data: str, meta_data: str) -> pathlib.Path | None:
    """Create the NoCloud seed ISO with cloud-localds or an mkisofs fallback."""
    seed = data_dir / "seed.iso"
    if shutil.which("cloud-localds"):
        tmp_user = data_dir / "user-data"
        tmp_meta = data_dir / "meta-data"
        tmp_user.write_text(user_data, encoding="utf-8")
        tmp_meta.write_text(meta_data, encoding="utf-8")
        try:
            subprocess.run(
                ["cloud-localds", str(seed), str(tmp_user), str(tmp_meta)],
                check=True, capture_output=True,
            )
            return seed
        except subprocess.CalledProcessError:
            pass
        finally:
            tmp_user.unlink(missing_ok=True)
            tmp_meta.unlink(missing_ok=True)
    for maker in ("genisoimage", "mkisofs", "xorriso"):
        if shutil.which(maker):
            tmp = data_dir / "cidata"
            tmp.mkdir(exist_ok=True)
            (tmp / "user-data").write_text(user_data, encoding="utf-8")
            (tmp / "meta-data").write_text(meta_data, encoding="utf-8")
            cmd = {
                "genisoimage": ["genisoimage", "-output", str(seed), "-volid", SEED_VOLUME, "-joliet", "-rock", str(tmp)],
                "mkisofs": ["mkisofs", "-output", str(seed), "-volid", SEED_VOLUME, "-joliet", "-rock", str(tmp)],
                "xorriso": ["xorriso", "-as", "mkisofs", "-output", str(seed), "-volid", SEED_VOLUME, "-joliet", "-rock", str(tmp)],
            }[maker]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                shutil.rmtree(tmp, ignore_errors=True)
                return seed
            except subprocess.CalledProcessError:
                continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--qcow2", type=pathlib.Path, default=None,
                        help="release qcow2 to copy into the bundle")
    parser.add_argument("--output", type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parent.parent / BUNDLE_NAME,
                        help="bundle directory (default: repo root)")
    parser.add_argument("--ssh-key", type=pathlib.Path, default=None,
                        help="public key to install instead of password-only login")
    args = parser.parse_args()

    if args.ssh_key is not None and not args.ssh_key.is_file():
        print(f"error: SSH public key not found: {args.ssh_key}", file=sys.stderr)
        return 1
    if args.qcow2 is not None and not args.qcow2.is_file():
        print(f"error: qcow2 not found: {args.qcow2}", file=sys.stderr)
        return 1

    bundle = args.output
    data_dir = bundle / "Data"
    data_dir.mkdir(parents=True, exist_ok=True)

    with open(bundle / "config.plist", "wb") as handle:
        plistlib.dump(build_config(), handle)

    ssh_key = args.ssh_key.read_text(encoding="utf-8").strip() if args.ssh_key else None
    # A per-bundle random password, shown once in README-FIRST.txt. It is
    # chpasswd-expired, so the first login forces a change. This is the
    # generated NoCloud seed the release contract requires — never a shared
    # static password shipped inside the image.
    one_time_password = secrets.token_urlsafe(12)
    user_data = seed_user_data(ssh_key, one_time_password)
    meta_data = "instance-id: moos-arm-utm-local\nlocal-hostname: moos-arm\n"

    seed = build_seed_iso(data_dir, user_data, meta_data)
    if seed is None:
        (data_dir / "user-data").write_text(user_data, encoding="utf-8")
        (data_dir / "meta-data").write_text(meta_data, encoding="utf-8")

    if args.qcow2 is not None:
        shutil.copy2(args.qcow2, data_dir / "moos-arm.qcow2")

    finish_lines = []
    if seed is None:
        finish_lines += [
            "The seed ISO could not be built here (no cloud-localds, genisoimage,",
            "mkisofs or xorriso found). Finish it with one command:",
            "",
            "    cloud-localds MoOS-ARM.utm/Data/seed.iso \\",
            "        MoOS-ARM.utm/Data/user-data MoOS-ARM.utm/Data/meta-data",
            "",
            "then delete the user-data/meta-data files. cloud-init requires the",
            "ISO volume label to be exactly 'cidata'.",
        ]
    if args.qcow2 is None:
        finish_lines += [
            "No qcow2 was supplied. Download the release artifact",
            "moos-arm-qcow2 from the newest successful 'Build MoOS ARM' run:",
            "    https://github.com/moalfarras-sys/moos-image/actions/workflows/build-arm.yml",
            "then:  zstd -d moos-arm-*.qcow2.zst",
            "and copy the uncompressed qcow2 to MoOS-ARM.utm/Data/moos-arm.qcow2",
        ]

    readme = "\n".join([
        "=" * 78,
        "MoOS ARM — UTM bundle (Apple silicon, iPhone, iPad)",
        "=" * 78,
        "",
        "Contents:",
        "  config.plist       UTM VM configuration (ARM64, UEFI is added by UTM)",
        "  Data/moos-arm.qcow2  the MoOS ARM disk" + ("" if args.qcow2 else "  (ADD ME — see below)"),
        "  Data/seed.iso      cloud-init NoCloud first-boot provisioning",
        "",
        f"First boot creates the user 'moos'. Its one-time password is:",
        "",
        f"    {one_time_password}",
        "",
        "You must change it at first login (cloud-init expires it).",
        "Keep this file private, or delete it after the first login.",
        "",
        "To use: open MoOS-ARM.utm (or the .utm.zip) in UTM / UTM SE.",
        "On iPhone/iPad UTM SE runs the same ARM64 system under emulation —",
        "performance is bounded by the device and the framework, not by MoOS.",
        "",
    ] + finish_lines + [""]) + "\n"
    (bundle / README_NAME).write_text(readme, encoding="utf-8")

    zip_path = bundle.with_suffix(".utm.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in bundle.rglob("*"):
            zf.write(path, path.relative_to(bundle.parent))

    print(f"Generated {bundle}")
    print(f"Packed {zip_path} ({zip_path.stat().st_size} bytes)")
    if seed is None or args.qcow2 is None:
        print("INCOMPLETE bundle — follow README-FIRST.txt before importing.", file=sys.stderr)
        return 2
    print(f"One-time password (also in {README_NAME}): {one_time_password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
