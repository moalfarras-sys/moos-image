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

# Static security and UTM contract.
assert "secrets.token_urlsafe" in script
assert not re.search(r"passwd:\s*[\"']?[A-Za-z0-9]{6,}", script), \
    "a literal password must never appear in the generator"
assert "type: text" in script
assert "expire: true" in script
assert "ssh_pwauth: false" in script, \
    "the public bundle password must be console-only; SSH remains key-only"
assert '"ImageName": "seed.iso"' in script
assert '"ImageName": "moos-arm.qcow2"' in script
assert '"Architecture": "aarch64"' in script
assert '"ConfigurationVersion": 4' in script
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
        "#!/bin/sh\nexec /bin/cp -- \"$2\" \"$1\"\n",
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
    assert [drive["ImageName"] for drive in config["Drives"]] == [
        "moos-arm.qcow2", "seed.iso"
    ]
    skeleton_readme = (skeleton / "README-FIRST.txt").read_text(encoding="utf-8")
    assert "actions/workflows/build-arm.yml" in skeleton_readme

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
    readme_path = bundle / "README-FIRST.txt"
    readme = readme_path.read_text(encoding="utf-8")
    password_match = re.search(r"one-time password is:\s*\n\s+(\S+)", readme)
    assert password_match
    password = password_match.group(1)
    assert password not in complete.stdout and password not in complete.stderr, \
        "the generated credential must never enter CI logs"
    assert readme_path.stat().st_mode & 0o777 == 0o600

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
    assert password not in manifest_text

    zip_path = root / "MoOS-ARM.utm.zip"
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path) as archive:
        assert set(archive.namelist()) == {
            "MoOS-ARM.utm/config.plist",
            "MoOS-ARM.utm/README-FIRST.txt",
            "MoOS-ARM.utm/manifest.json",
            "MoOS-ARM.utm/Data/moos-arm.qcow2",
            "MoOS-ARM.utm/Data/seed.iso",
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

    # Two generated bundles never share a bootstrap credential.
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
    second_readme = (second_bundle / "README-FIRST.txt").read_text(encoding="utf-8")
    second_password = re.search(
        r"one-time password is:\s*\n\s+(\S+)", second_readme
    ).group(1)
    assert password != second_password

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
