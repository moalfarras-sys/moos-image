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
  ./generate_utm_bundle.py [--output DIR]
  ./generate_utm_bundle.py --qcow2 PATH --expected-qcow2-sha256 SHA256 \
      --source-image-ref IMAGE@sha256:DIGEST [--output DIR] [--ssh-key PATH]

Without --qcow2 the bundle is a skeleton: config.plist, README and an empty
Data/ the downloaded release qcow2 goes into. With --qcow2 the image is
copied in and the seed ISO is built when cloud-localds (or a mkisofs-family
tool) is available; otherwise the seed payloads are written to Data/ with
the exact command to finish them, and the script says so.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import plistlib
import re
import secrets
import shutil
import subprocess
import sys
import zipfile

BUNDLE_NAME = "MoOS-ARM.utm"
SEED_VOLUME = "cidata"
README_NAME = "README-FIRST.txt"
OFFICIAL_IMAGE_RE = re.compile(
    r"^ghcr\.io/moalfarras-sys/moos-arm@sha256:[0-9a-f]{64}$"
)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        # The generated password is for the local UTM console only. SSH stays
        # key-only so a public release bundle never exposes a password login.
        "ssh_pwauth: false",
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
            seed.chmod(0o600)
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
                seed.chmod(0o600)
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
    parser.add_argument("--expected-qcow2-sha256", default=None,
                        help="required SHA-256 of --qcow2; binds the bundle to boot proof")
    parser.add_argument("--source-image-ref", default=None,
                        help="required signed ghcr.io/.../moos-arm@sha256:... source")
    args = parser.parse_args()

    if args.ssh_key is not None and not args.ssh_key.is_file():
        print(f"error: SSH public key not found: {args.ssh_key}", file=sys.stderr)
        return 1
    if args.qcow2 is not None and not args.qcow2.is_file():
        print(f"error: qcow2 not found: {args.qcow2}", file=sys.stderr)
        return 1
    if args.qcow2 is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", args.expected_qcow2_sha256 or ""):
            print("error: --qcow2 requires --expected-qcow2-sha256 (64 lowercase hex)",
                  file=sys.stderr)
            return 1
        if not OFFICIAL_IMAGE_RE.fullmatch(args.source_image_ref or ""):
            print("error: --qcow2 requires the exact official --source-image-ref",
                  file=sys.stderr)
            return 1
        source_sha = sha256_file(args.qcow2)
        if source_sha != args.expected_qcow2_sha256:
            print(
                f"error: qcow2 SHA-256 is {source_sha}, expected "
                f"{args.expected_qcow2_sha256}",
                file=sys.stderr,
            )
            return 1
    elif args.expected_qcow2_sha256 is not None or args.source_image_ref is not None:
        print("error: digest/source arguments require --qcow2", file=sys.stderr)
        return 1

    bundle = args.output
    if bundle.exists() and any(bundle.iterdir()):
        print(f"error: output bundle is not empty: {bundle}", file=sys.stderr)
        return 1
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
        (data_dir / "user-data").chmod(0o600)
        (data_dir / "meta-data").chmod(0o600)

    if args.qcow2 is not None:
        bundled_qcow = data_dir / "moos-arm.qcow2"
        shutil.copy2(args.qcow2, bundled_qcow)
        copied_sha = sha256_file(bundled_qcow)
        if copied_sha != args.expected_qcow2_sha256:
            print(
                f"error: copied qcow2 SHA-256 is {copied_sha}, expected "
                f"{args.expected_qcow2_sha256}",
                file=sys.stderr,
            )
            return 1

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
    readme_path = bundle / README_NAME
    readme_path.write_text(readme, encoding="utf-8")
    readme_path.chmod(0o600)

    if args.qcow2 is not None and seed is not None:
        config_path = bundle / "config.plist"
        manifest = {
            "schema": 1,
            "product": "MoOS ARM",
            "architecture": "aarch64",
            "source_image": args.source_image_ref,
            "disk": {
                "path": "Data/moos-arm.qcow2",
                "sha256": args.expected_qcow2_sha256,
                "bytes": (data_dir / "moos-arm.qcow2").stat().st_size,
            },
            "seed": {
                "path": "Data/seed.iso",
                "sha256": sha256_file(seed),
                "volume": SEED_VOLUME,
            },
            "config": {
                "path": "config.plist",
                "sha256": sha256_file(config_path),
            },
        }
        (bundle / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    zip_path = bundle.with_suffix(".utm.zip")
    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=1,
        allowZip64=True,
    ) as zf:
        for path in bundle.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(bundle.parent))

    print(f"Generated {bundle}")
    print(f"Packed {zip_path} ({zip_path.stat().st_size} bytes)")
    if seed is None or args.qcow2 is None:
        print("INCOMPLETE bundle — follow README-FIRST.txt before importing.", file=sys.stderr)
        return 2
    print(f"First-boot console credential is stored only in {README_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
