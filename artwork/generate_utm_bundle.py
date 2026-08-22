#!/usr/bin/env python3
"""Generate a ready-to-import MoOS-ARM.utm bundle for UTM on Apple silicon,
iPhone and iPad.

One authoritative generator replaces the three draft scripts this bundle
started as. The bundle it emits is HONEST about first boot: the ARM image
provisions its user through cloud-init NoCloud, exactly like the release
boot proof in tests/boot_arm_qcow2.sh — a UTM VM without a seed disk boots
to a login screen with no account on it. So the bundle always carries a
seed drive. That public seed contains no password: cloud-init generates a
different local-console bootstrap password inside every VM first boot.

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
import shutil
import subprocess
import sys
import uuid
import zipfile

BUNDLE_NAME = "MoOS-ARM.utm"
SEED_VOLUME = "cidata"
README_NAME = "README-FIRST.txt"
ICON_NAME = "moos-icon.png"
ICON_SOURCE = (
    pathlib.Path(__file__).resolve().parent.parent
    / "system_files/usr/share/moos/moos-logo.png"
)
OFFICIAL_IMAGE_RE = re.compile(
    r"^ghcr\.io/moalfarras-sys/moos-arm@sha256:[0-9a-f]{64}$"
)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seed_user_data(ssh_key: str | None) -> str:
    # The public release bundle must not contain a credential shared by every
    # downloader. Do not use cloud-init's chpasswd type=RANDOM here. Its
    # implementation writes the result directly to /dev/console, which MoOS
    # intentionally keeps on tty0 so graphical boot remains visible; UTM's
    # built-in Terminal is ttyAMA0 and would never show that credential.
    # Instead a final-stage helper generates the password inside this VM,
    # feeds it to chpasswd over stdin, and writes it once to the ARM serial
    # console. The public seed contains generator code, never a credential.
    # SSH password authentication remains disabled and KRDP is off by default.
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
        "write_files:",
        "  - path: /run/moos-utm-firstboot-password.py",
        "    owner: root:root",
        "    permissions: '0700'",
        "    content: |",
        "      #!/usr/bin/python3",
        "      import secrets",
        "      import string",
        "      import subprocess",
        "      chars = [secrets.choice(string.ascii_uppercase),",
        "               secrets.choice(string.ascii_lowercase),",
        "               secrets.choice(string.digits)]",
        "      alphabet = string.ascii_letters + string.digits",
        "      chars.extend(secrets.choice(alphabet) for _ in range(17))",
        "      secrets.SystemRandom().shuffle(chars)",
        "      password = ''.join(chars)",
        "      subprocess.run(['chpasswd'], input=f'moos:{password}\\n',",
        "                     text=True, check=True)",
        "      message = ('\\nMOOS_ARM_FIRST_BOOT_PASSWORD_BEGIN\\n'",
        "                 f'user=moos\\npassword={password}\\n'",
        "                 'MOOS_ARM_FIRST_BOOT_PASSWORD_END\\n')",
        "      with open('/dev/ttyAMA0', 'w', encoding='utf-8') as serial:",
        "          serial.write(message)",
        "          serial.flush()",
        "      password = ''",
        "runcmd:",
        "  - [/usr/bin/python3, /run/moos-utm-firstboot-password.py]",
        "  - [rm, -f, /run/moos-utm-firstboot-password.py]",
        "ssh_pwauth: false",
        "disable_root: true",
        "final_message: MOOS_ARM_FIRST_BOOT_READY — use the VM-unique moos password printed between the markers in UTM Terminal",
    ]
    return "\n".join(lines) + "\n"


def random_mac_address() -> str:
    raw = bytearray(uuid.uuid4().bytes[:6])
    raw[0] = (raw[0] & 0xFC) | 0x02
    return ":".join(f"{byte:02X}" for byte in raw)


def build_config() -> dict:
    # UTM's current QEMU configuration schema is v4. All non-optional Codable
    # fields are present so UTM decodes this directly instead of guessing that
    # it is a legacy bundle. The built-in serial terminal is load-bearing: it
    # is where cloud-init reveals the credential generated inside this VM.
    return {
        "Backend": "QEMU",
        "ConfigurationVersion": 4,
        "Information": {
            "Name": "MoOS ARM",
            "Notes": "MoOS for aarch64 — MoOS UI. On first boot open the "
                     "built-in Terminal view: this VM generates and prints its "
                     "own local-console password for the 'moos' user.",
            "IconCustom": True,
            "Icon": ICON_NAME,
            "UUID": str(uuid.uuid4()).upper(),
        },
        "System": {
            "Architecture": "aarch64",
            "Target": "virt",
            "CPU": "default",
            "CPUFlagsAdd": [],
            "CPUFlagsRemove": [],
            "CPUCount": 4,
            # 4 GiB is the smallest profile the release boot proof has actually
            # exercised. Do not advertise the former unproven 3 GiB guess.
            "MemorySize": 4096,
            "JITCacheSize": 0,
            "ForceMulticore": False,
        },
        "QEMU": {
            "DebugLog": False,
            "UEFIBoot": True,
            "RNGDevice": True,
            "BalloonDevice": False,
            "TPMDevice": False,
            "Hypervisor": True,
            "TSO": False,
            "RTCLocalTime": False,
            "PS2Controller": False,
            "AdditionalArguments": [],
        },
        "Input": {
            "UsbBusSupport": "3.0",
            "UsbSharing": False,
            "MaximumUsbShare": 3,
        },
        "Sharing": {
            "DirectoryShareMode": "None",
            "DirectoryShareReadOnly": True,
            "ClipboardSharing": False,
        },
        "Display": [
            {
                # UTM's own aarch64/virt default combines an early RAM
                # framebuffer (visible UEFI) with the virtio GPU used by MoOS.
                "Hardware": "virtio-ramfb",
                "DynamicResolution": False,
                "NativeResolution": False,
                "UpscalingFilter": "Linear",
                "DownscalingFilter": "Linear",
            }
        ],
        "Drive": [
            {
                "ImageName": "moos-arm.qcow2",
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
                "Mode": "Emulated",
                "Hardware": "virtio-net-pci",
                "MacAddress": random_mac_address(),
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
                        help="optional public key to install alongside console login")
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

    if not ICON_SOURCE.is_file():
        print(f"error: MoOS UTM icon is missing: {ICON_SOURCE}", file=sys.stderr)
        return 1
    config = build_config()
    with open(bundle / "config.plist", "wb") as handle:
        plistlib.dump(config, handle)
    shutil.copy2(ICON_SOURCE, data_dir / ICON_NAME)

    ssh_key = args.ssh_key.read_text(encoding="utf-8").strip() if args.ssh_key else None
    # No password is generated on the build host or stored in the public zip.
    # cloud-init generates it independently inside every first boot.
    user_data = seed_user_data(ssh_key)
    instance_id = config["Information"]["UUID"].lower()
    meta_data = f"instance-id: moos-arm-utm-{instance_id}\nlocal-hostname: moos-arm\n"

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
        "  Data/moos-icon.png native MoOS identity in the UTM library",
        "",
        "First boot creates the user 'moos' and generates its password INSIDE",
        "your VM. The public download contains no shared or pre-generated password.",
        "",
        "Before pressing Start, open UTM's built-in Terminal view and keep it",
        "visible. During first boot cloud-init prints:",
        "",
        "    Set the following 'random' passwords",
        "    moos:<your VM-unique password>",
        "",
        "Use that password on the graphical MoOS login screen. SSH password",
        "login is disabled and Mo PC Remote is off until you explicitly enable it.",
        "After login, change the bootstrap password in Settings, then stop the VM",
        "and detach the read-only seed.iso drive. The password is not forcibly",
        "expired at the greeter because Plasma Login Manager 6.7 cannot complete",
        "that three-step PAM conversation; expiring it would lock out first login.",
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
                "credential": "generated-in-guest-ttyAMA0",
                "ssh_password_authentication": False,
                "password_expired_at_greeter": False,
            },
            "icon": {
                "path": f"Data/{ICON_NAME}",
                "sha256": sha256_file(data_dir / ICON_NAME),
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
    print("First-boot credential will be generated only inside the guest and shown on ttyAMA0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
