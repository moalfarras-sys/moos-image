#!/usr/bin/env python3
"""Regression fixtures for the shared ARM/x86 release deployment seal."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "build_files/seal_arm_deployment.py"
DIGEST = "sha256:" + "a" * 64
IMAGE = "ghcr.io/moalfarras-sys/moos-arm@" + DIGEST


def fixture(
    origin_reference: str,
    *,
    options: str = (
        "root=UUID=x ostree=/ostree/boot.1/default/"
        + "c" * 64
        + "/0 rhgb quiet splash preempt=full split_lock_detect=off "
        "console=ttyAMA0,115200n8 console=tty0 console=ttyS0"
    ),
) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, Path, Path]:
    temporary = tempfile.TemporaryDirectory(prefix="moos-arm-seal-")
    base = Path(temporary.name)
    root = base / "root"
    boot = base / "boot"
    origin = root / "ostree/deploy/default/deploy" / ("b" * 64 + ".0.origin")
    entry = boot / "loader.1/entries/ostree-1.conf"
    origin.parent.mkdir(parents=True)
    entry.parent.mkdir(parents=True)
    origin.write_text(
        "[origin]\ncontainer-image-reference=" + origin_reference + "\n",
        encoding="utf-8",
    )
    entry.write_text(
        "title MoOS\n"
        f"options {options}\n",
        encoding="utf-8",
    )
    return temporary, root, boot, origin, entry


def run(
    root: Path,
    boot: Path,
    image: str = IMAGE,
    arch: str = "arm64",
    ci_runtime_proof: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
            str(SCRIPT),
            "--root", str(root),
            "--boot", str(boot),
            "--expected-image", image,
            "--target-arch", arch,
        ]
    if ci_runtime_proof:
        command.append("--enable-ci-runtime-proof")
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
    )


def main() -> int:
    temporary, root, boot, origin, entry = fixture("ostree-unverified-registry:" + IMAGE)
    with temporary:
        result = run(root, boot)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "container-image-reference=ostree-image-signed:docker://" + IMAGE in origin.read_text()
        options = entry.read_text(encoding="utf-8")
        assert "console=ttyS0" not in options
        assert "preempt=full" not in options
        assert "split_lock_detect=off" not in options
        assert options.rstrip().endswith("console=tty0")
        # A second pass is exactly idempotent.
        assert run(root, boot).returncode == 0

    temporary, root, boot, _, _ = fixture(
        "ostree-unverified-registry:example.invalid/foreign@" + DIGEST
    )
    with temporary:
        assert run(root, boot).returncode != 0

    temporary, root, boot, _, _ = fixture("ostree-unverified-registry:" + IMAGE)
    with temporary:
        assert run(root, boot, "ghcr.io/moalfarras-sys/moos-arm:latest").returncode != 0

    x86_image = "ghcr.io/moalfarras-sys/moos@" + DIGEST
    temporary, root, boot, origin, entry = fixture(
        "ostree-unverified-registry:" + x86_image,
        options=(
            "root=UUID=x ostree=/ostree/boot.0/default/"
            + "d" * 64
            + "/0 rhgb quiet splash preempt=full split_lock_detect=off console=ttyS0"
        ),
    )
    with temporary:
        origin.with_suffix("").mkdir()
        result = run(root, boot, x86_image, "x86_64")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "container-image-reference=ostree-image-signed:docker://" + x86_image in origin.read_text()
        options = entry.read_text(encoding="utf-8")
        assert "console=ttyS0" not in options
        assert "preempt=full" in options
        assert "split_lock_detect=off" in options
        assert run(root, boot, x86_image, "x86_64").returncode == 0

    temporary, root, boot, origin, entry = fixture(
        "ostree-unverified-registry:" + x86_image,
        options=(
            "root=UUID=x ostree=/ostree/boot.0/default/"
            + "9" * 64
            + "/0 rhgb quiet splash console=ttyS0"
        ),
    )
    with temporary:
        deployment = origin.with_suffix("")
        deployment.mkdir()
        result = run(root, boot, x86_image, "x86_64", True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert entry.read_text().count("moos.ci-runtime-proof=1") == 1
        proof_link = (
            deployment / "etc/systemd/system/multi-user.target.wants/"
            "moos-ci-runtime-proof.service"
        )
        assert proof_link.is_symlink()
        assert proof_link.readlink() == Path(
            "/usr/lib/systemd/system/moos-ci-runtime-proof.service"
        )
        assert run(root, boot, x86_image, "x86_64", True).returncode == 0

    temporary, root, boot, origin, _ = fixture(
        "ostree-unverified-registry:" + IMAGE
    )
    with temporary:
        origin.with_suffix("").mkdir()
        assert run(root, boot, IMAGE, "arm64", True).returncode != 0

    cloud_image = "ghcr.io/moalfarras-sys/moos-cloud@" + DIGEST
    temporary, root, boot, origin, entry = fixture(
        "ostree-unverified-registry:" + cloud_image,
        options=(
            "root=UUID=x ostree=/ostree/boot.0/default/"
            + "e" * 64
            + "/0 video=Virtual-1:1920x1080@60 console=tty0 "
            "console=ttyS0 console=ttyS0,9600n8"
        ),
    )
    with temporary:
        deployment = origin.with_suffix("")
        deployment.mkdir()
        result = run(root, boot, cloud_image, "x86_64", True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "container-image-reference=ostree-image-signed:docker://" + cloud_image in origin.read_text()
        options = entry.read_text(encoding="utf-8")
        assert "rhgb" not in options and " quiet " not in options and "splash" not in options
        assert options.count("console=ttyS0,115200n8") == 1
        assert options.count("moos.ci-runtime-proof=1") == 1
        assert options.rstrip().endswith("console=tty0")
        assert (
            deployment / "etc/systemd/system/multi-user.target.wants/"
            "moos-ci-runtime-proof.service"
        ).is_symlink()

    temporary, root, boot, _, _ = fixture(
        "ostree-unverified-registry:" + cloud_image,
        options=(
            "root=UUID=x ostree=/ostree/boot.0/default/"
            + "8" * 64
            + "/0 console=ttyS0,115200n8 console=tty0"
        ),
    )
    with temporary:
        assert run(root, boot, cloud_image, "x86_64").returncode != 0

    temporary, root, boot, _, _ = fixture(
        "ostree-unverified-registry:ghcr.io/moalfarras-sys/moos-arm@" + DIGEST,
        options=(
            "root=UUID=x ostree=/ostree/boot.0/default/"
            + "f" * 64
            + "/0 rhgb quiet splash"
        ),
    )
    with temporary:
        assert run(root, boot, x86_image, "x86_64").returncode != 0

    temporary, root, boot, _, _ = fixture(
        "ostree-unverified-registry:" + x86_image,
        options="root=UUID=x rhgb quiet splash",
    )
    with temporary:
        assert run(root, boot, x86_image, "x86_64").returncode != 0

    print("OK: the shared disk seal pins signed ARM/x86 origins, removes builder kargs, and rejects foreign/mutable refs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
