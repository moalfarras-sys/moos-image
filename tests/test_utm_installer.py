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
INSTALL = ROOT / "system_files/usr/libexec/moos-utm-net-install"
WORKFLOW = ROOT / ".github/workflows/build-arm.yml"


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
    # The bundle below is generated with --iphone, so the expected System block
    # is the low-memory profile. Kept as a name rather than a literal so the
    # assertion reads the same way the generator branches.
    IPHONE_PROFILE = True
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
    # RECOVERED FROM archive/arm-utm-20260827 AND BROUGHT UP TO DATE.
    #
    # The archive froze this contract on 2026-08-26 at CPUCount 2 / MemorySize
    # 1536 / JITCacheSize 64 / ForceMulticore False, and knew only ONE profile.
    # The shipped generator has moved on and now has two, which was verified by
    # RUNNING build_config() rather than reading it:
    #
    #     iphone=True   CPUCount 2  MemorySize 3072  ForceMulticore True   Hypervisor False
    #     iphone=False  CPUCount 4  MemorySize 4096  ForceMulticore False  Hypervisor True
    #
    # Hypervisor is the load-bearing difference: iOS does not grant the JIT
    # entitlement UTM needs for hardware virtualisation, so an iPhone bundle must
    # ask for TCG. Asserting the August values would have failed a correct
    # generator, which is why this recovery updates the expectation instead of
    # restoring the branch.
    expected_system = {
        "Architecture": "aarch64",
        "Target": "virt",
        "CPU": "default",
        "CPUFlagsAdd": [],
        "CPUFlagsRemove": [],
        "CPUCount": 2 if IPHONE_PROFILE else 4,
        "MemorySize": 3072 if IPHONE_PROFILE else 4096,
        "JITCacheSize": 0,
        "ForceMulticore": bool(IPHONE_PROFILE),
    }
    assert config["System"] == expected_system, (
        f"UTM System block drifted: {config['System']} != {expected_system}")
    assert config["QEMU"]["UEFIBoot"] is True
    assert config["QEMU"]["Hypervisor"] is (not IPHONE_PROFILE), (
        "an iPhone bundle must request TCG: iOS grants no JIT entitlement for "
        "hardware virtualisation")
    assert config["Display"] == [{
        "Hardware": "virtio-ramfb",
        "DynamicResolution": False,
        "NativeResolution": False,
        "UpscalingFilter": "Linear",
        "DownscalingFilter": "Linear",
    }]
    # Also moved on since the archive. The bundle used to ask for an Emulated
    # VLAN; the shipped generator asks for UTM's "Shared" NAT and its README now
    # says so in as many words ("Shared is fine on Mac/iPhone"). A net installer
    # has to reach the internet, so Shared is the correct mode and the archived
    # expectation was the stale one — verified by running build_config().
    assert config["Network"][0]["Mode"] == "Shared"
    assert config["Network"][0]["Hardware"] == "virtio-net-pci"
    assert [drive["ImageName"] for drive in config["Drive"]] == [
        "installer.qcow2", "target.qcow2", "seed.iso"
    ]
    assert (bundle / "Data/installer.qcow2").read_bytes() == installer.read_bytes()
    assert (bundle / "Data/seed.iso").stat().st_size > 0
    assert (bundle / "Data/target.qcow2").is_file()

    readme = (bundle / "README-FIRST.txt").read_text(encoding="utf-8")
    assert "Shared is fine" in readme, (
        "the README must tell the owner which network mode to pick, and it must "
        "match the mode the config actually requests")
    assert "OWNER-iPHONE-TEST-REQUIRED" in readme
    assert "Emulated VLAN" not in readme, (
        "the retired Emulated-VLAN instruction must not come back beside a "
        "config that asks for Shared")

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

# THE WORKFLOW-ORDER BLOCK FROM THE ARCHIVE IS DELIBERATELY NOT RECOVERED.
#
# It asserted an eight-step release order from archive/arm-utm-20260827. Four of
# those step names no longer exist: two were renamed, and two — "Boot and
# visually prove the exact UTM Net Installer under TCG" and "Boot, log in and
# visually prove the exact iPhone full bundle" — are genuinely absent, along
# with the word "proven" in the upload step.
#
# That looks like main having become looser, and it is worth being precise about
# why this test does not re-impose it: PROJECT_STATE.md records that this
# archive branch "packages the recovery disk before the candidate is proven and
# carried a visual-gate bypass", and that "the unsafe publication order and
# bypass remain rejected". Restoring its ordering here would re-litigate a
# decided design through a test file, which is not what a recovered gate is for.
#
# The gap itself is NOT dropped on the floor: MOOS_ROADMAP.md already tracks
# "Package that exact QCOW2 as MoOS-ARM.utm.zip ... Perform a visible
# UTM-equivalent login" as an open release blocker. That is where the missing
# visual proof belongs, as a release gate someone closes with evidence — not as
# a string comparison against a workflow.
#
# What IS recovered above is the part that was unguarded and current: the bundle
# layout, config.plist contract, drive set, README and zip membership, all
# checked against the generator as it ships today.


# The net installer is what actually writes MoOS onto the target disk, and it
# shipped with no executable coverage at all. These are release-safety
# properties, not style: a regression that pinned a floating tag, or ran cosign
# after bootc, would install an unverified image while still looking correct.
#
# Full-line comments are stripped before matching so an assertion can never be
# satisfied by prose. Inline "#" is NOT stripped, because this script uses
# ${digest#sha256:} parameter expansion that a naive strip would mangle.
install_src = INSTALL.read_text(encoding="utf-8")
install_code = "\n".join(
    line for line in install_src.splitlines() if not line.lstrip().startswith("#")
)

assert 'ref="${REGISTRY}@${digest}"' in install_code, (
    "the image reference must be pinned by digest with '@'. A ':' tag form is "
    "mutable and would let the installer fetch something other than the "
    "signature-verified content")
assert '"${REGISTRY}:' not in install_code, (
    "no tag-form reference may appear: a floating tag defeats digest pinning")

assert r'[[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]' in install_code, (
    "the manifest digest must be validated against an anchored sha256 pattern "
    "before it is ever interpolated into an image reference")

verify_at = install_code.find("cosign verify")
install_at = install_code.find("bootc install")
assert verify_at != -1 and install_at != -1, "installer lost cosign or bootc"
assert verify_at < install_at, (
    "cosign verify must run BEFORE bootc install; verifying afterwards would "
    "install unverified content and only then complain")

verify_tail = install_code[verify_at:install_at]
assert "exit 1" in verify_tail, (
    "a failed signature must abort the installation, not fall through to "
    "bootc install")

assert "--enforce-container-sigpolicy" in install_code, (
    "bootc must enforce the container signature policy on the installed "
    "target, so the installed system keeps requiring signed updates")


# A gate nothing runs is not a gate. The ARM workflow already triggers on the
# installer generator, so before this file existed it rebuilt on installer
# changes while running no installer coverage at all. Keep both halves wired.
workflow = WORKFLOW.read_text(encoding="utf-8")
for required_path in (
    '      - "artwork/generate_utm_installer.py"',
    '      - "tests/test_utm_installer.py"',
):
    assert workflow.count(required_path) == 2, \
        f"ARM push and PR filters must both include {required_path.strip()}"
assert "python3 tests/test_utm_installer.py" in workflow, \
    "this gate must actually execute in the ARM workflow"

print("UTM net-installer gate passed")
