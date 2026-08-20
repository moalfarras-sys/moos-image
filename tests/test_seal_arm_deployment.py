#!/usr/bin/env python3
"""Regression fixtures for the final ARM deployment seal."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "build_files/seal_arm_deployment.py"
DIGEST = "sha256:" + "a" * 64
IMAGE = "ghcr.io/moalfarras-sys/moos-arm@" + DIGEST


def fixture(origin_reference: str) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, Path, Path]:
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
        "options root=UUID=x rhgb quiet splash preempt=full split_lock_detect=off "
        "console=ttyAMA0,115200n8 console=tty0 console=ttyS0\n",
        encoding="utf-8",
    )
    return temporary, root, boot, origin, entry


def run(root: Path, boot: Path, image: str = IMAGE) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), "--root", str(root), "--boot", str(boot), "--expected-image", image],
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

    print("OK: the ARM disk seal pins the signed origin, removes foreign kargs, and rejects foreign/mutable refs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
