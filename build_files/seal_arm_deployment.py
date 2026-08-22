#!/usr/bin/env python3
"""Seal a mounted MoOS disk deployment before it becomes a release artifact.

bootc-image-builder installs from its local container store, which leaves the
deployment origin on an unverified transport even when CI verified and signed
the source digest. It may also append an x86 serial console to the BLS entry.
This tool changes only those two narrowly defined pieces and fails on any
unexpected layout or reference.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import tempfile
from pathlib import Path


OFFICIAL_IMAGES = {
    "arm64": re.compile(
        r"^ghcr\.io/moalfarras-sys/moos-arm@sha256:[0-9a-f]{64}$"
    ),
    "x86_64": re.compile(
        r"^ghcr\.io/moalfarras-sys/(?:moos|moos-nvidia|moos-cloud)@sha256:[0-9a-f]{64}$"
    ),
}
ORIGIN_KEY = "container-image-reference="
UNVERIFIED_PREFIXES = (
    "ostree-unverified-registry:",
    "ostree-unverified-image:docker://",
)
SIGNED_PREFIX = "ostree-image-signed:docker://"
FOREIGN_KARGS = {"preempt=full", "split_lock_detect=off"}
OSTREE_KARG = re.compile(
    r"^ostree=/ostree/boot\.[01]/[^/\s]+/[0-9a-f]{64}/[0-9]+$"
)
CI_RUNTIME_KARG = "moos.ci-runtime-proof=1"
CI_RUNTIME_UNIT = "moos-ci-runtime-proof.service"
CI_RUNTIME_UNIT_TARGET = "/usr/lib/systemd/system/" + CI_RUNTIME_UNIT


def fail(message: str) -> None:
    raise SystemExit(f"MOOS DISK FATAL: {message}")


def atomic_write(path: Path, text: str) -> None:
    metadata = path.stat()
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.moos-", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as target:
            target.write(text)
            target.flush()
            os.fsync(target.fileno())
        os.chmod(temporary, stat.S_IMODE(metadata.st_mode))
        try:
            os.chown(temporary, metadata.st_uid, metadata.st_gid)
        except PermissionError:
            # Unit tests run unprivileged and already own both files. The release
            # workflow runs as root and preserves the deployed file's ownership.
            pass
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def seal_origin(root: Path, expected_image: str) -> Path:
    origins = sorted(root.glob("ostree/deploy/*/deploy/*.origin"))
    if len(origins) != 1:
        fail(f"expected exactly one deployed origin, found {len(origins)}")
    origin = origins[0]
    lines = origin.read_text(encoding="utf-8").splitlines()
    references = [line[len(ORIGIN_KEY):] for line in lines if line.startswith(ORIGIN_KEY)]
    if len(references) != 1:
        fail(f"{origin} has {len(references)} container image references")
    reference = references[0]
    signed = SIGNED_PREFIX + expected_image
    if reference == signed:
        return origin
    if not any(reference == prefix + expected_image for prefix in UNVERIFIED_PREFIXES):
        fail(f"refusing unexpected deployment origin: {reference}")
    rewritten = [
        ORIGIN_KEY + signed if line.startswith(ORIGIN_KEY) else line
        for line in lines
    ]
    atomic_write(origin, "\n".join(rewritten) + "\n")
    return origin


def seal_bls(
    boot: Path, target_arch: str, enable_ci_runtime_proof: bool = False
) -> list[Path]:
    entries = sorted(set(boot.glob("loader*/entries/*.conf")))
    if not entries:
        fail("no deployed BLS entries found")
    for entry in entries:
        lines = entry.read_text(encoding="utf-8").splitlines()
        option_indexes = [i for i, line in enumerate(lines) if line.startswith("options ")]
        if len(option_indexes) != 1:
            fail(f"{entry} has {len(option_indexes)} options lines")
        index = option_indexes[0]
        options = lines[index].split()[1:]
        ostree_options = [item for item in options if item.startswith("ostree=")]
        if len(ostree_options) != 1 or not OSTREE_KARG.fullmatch(ostree_options[0]):
            fail(f"{entry} does not select exactly one valid OSTree deployment")
        options = [item for item in options if not item.startswith("console=ttyS0")]
        if target_arch == "arm64":
            # These two latency flags are x86 policy and must not leak into an
            # ARM disk just because its shared image tree contains the source.
            options = [item for item in options if item not in FOREIGN_KARGS]
            required_options = (
                "console=ttyAMA0,115200n8",
                "console=tty0",
                "rhgb",
                "quiet",
                "splash",
            )
        else:
            # x86 desktop images keep their measured MoKernel policy. BIB may
            # inject a serial console for its own builder diagnostics; remove
            # that release-only leak while preserving the branded splash.
            required_options = ("rhgb", "quiet", "splash")
            if enable_ci_runtime_proof and CI_RUNTIME_KARG not in options:
                options.append(CI_RUNTIME_KARG)
        for required in required_options:
            if options.count(required) != 1:
                fail(f"{entry} must contain exactly one {required}")
        consoles = [item for item in options if item.startswith("console=")]
        if target_arch == "arm64" and consoles[-1] != "console=tty0":
            fail(f"{entry} does not keep the graphical console primary: {consoles}")
        if enable_ci_runtime_proof and options.count(CI_RUNTIME_KARG) != 1:
            fail(f"{entry} must contain exactly one {CI_RUNTIME_KARG}")
        lines[index] = "options " + " ".join(options)
        atomic_write(entry, "\n".join(lines) + "\n")
    return entries


def enable_ci_runtime_proof(origin: Path) -> Path:
    deployment = origin.with_suffix("")
    if not deployment.is_dir():
        fail(f"deployed root is missing beside {origin}")
    wants = deployment / "etc/systemd/system/multi-user.target.wants"
    wants.mkdir(parents=True, exist_ok=True)
    link = wants / CI_RUNTIME_UNIT
    if link.is_symlink():
        if os.readlink(link) != CI_RUNTIME_UNIT_TARGET:
            fail(f"refusing unexpected CI proof unit target: {os.readlink(link)}")
    elif link.exists():
        fail(f"refusing non-symlink CI proof unit enablement: {link}")
    else:
        os.symlink(CI_RUNTIME_UNIT_TARGET, link)
    return link


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--boot", required=True, type=Path)
    parser.add_argument("--expected-image", required=True)
    parser.add_argument("--target-arch", choices=sorted(OFFICIAL_IMAGES), default="arm64")
    parser.add_argument("--enable-ci-runtime-proof", action="store_true")
    args = parser.parse_args()
    if not OFFICIAL_IMAGES[args.target_arch].fullmatch(args.expected_image):
        fail(f"refusing non-official or non-digest image: {args.expected_image}")
    if not args.root.is_dir() or not args.boot.is_dir():
        fail("root and boot must be mounted directories")
    if args.enable_ci_runtime_proof and args.target_arch != "x86_64":
        fail("the CI runtime proof channel is x86-only")
    origin = seal_origin(args.root, args.expected_image)
    entries = seal_bls(args.boot, args.target_arch, args.enable_ci_runtime_proof)
    proof_link = enable_ci_runtime_proof(origin) if args.enable_ci_runtime_proof else None
    print(
        f"MOOS DISK SEALED ({args.target_arch}): {origin}; "
        f"{len(entries)} BLS entr{'y' if len(entries) == 1 else 'ies'}"
        + (f"; CI proof={proof_link}" if proof_link else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
