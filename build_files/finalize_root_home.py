#!/usr/bin/env python3
"""Retire only verified empty vendor root-home scaffolds in an unbooted compose."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import stat

from finalize_image_state import owned_path


KONFLUX = 'usr/lib/tmpfiles.d/konflux-buildinfo-contentsets.conf'
PROVISION = 'usr/lib/tmpfiles.d/provision.conf'
# Published bootc base5356bdd4 carries this unpackaged generated file as
# root:root0664. Accept that one root-group-writable input only at its exact
# reviewed bytes, retaining its native metadata and all other owner/mode guards.
REVIEWED_KONFLUX_SHA256 = '43d9c01a06c1a1abe4e03ff0cea0a0e5366d4358b4695f4dbe09f23757d9d24c'
RULES = {
    KONFLUX: [
        'd /var/roothome/buildinfo 0755 - - -',
        'd /var/roothome/buildinfo/content_manifests 0755 - - -',
        'f /var/roothome/buildinfo/content_manifests/content-sets.json 0644 - - -',
        'f /var/roothome/buildinfo/labels.json 0644 - - -',
    ],
    PROVISION: [
        'd- /var/roothome/.ssh :0700 root :root -',
        'f^ /var/roothome/.ssh/authorized_keys :0600 root :root - ssh.authorized_keys.root',
    ],
}
SCAFFOLDS = {
    '.ssh': (stat.S_IFDIR | 0o700, PROVISION),
    'buildinfo': (stat.S_IFDIR | 0o755, KONFLUX),
    'buildinfo/content_manifests': (stat.S_IFDIR | 0o755, KONFLUX),
    'buildinfo/content_manifests/content-sets.json': (stat.S_IFREG | 0o644, KONFLUX),
    'buildinfo/labels.json': (stat.S_IFREG | 0o644, KONFLUX),
}


def finalize(root: Path) -> None:
    root = root.resolve()
    if root == Path('/') and (not Path('/run/.containerenv').exists()
                             or Path('/run/ostree-booted').exists()):
        raise RuntimeError('root-home retirement requires an unbooted build container')
    owner = root.stat()
    alias = root / 'root'
    if (not alias.is_symlink() or os.readlink(alias) != 'var/roothome'
            or alias.lstat().st_uid != owner.st_uid or alias.lstat().st_gid != owner.st_gid):
        raise RuntimeError('root home does not use the reviewed bootc alias')
    base = owned_path(root, 'var/roothome')
    if not base.exists():
        return

    # Walk only known directories after checking each mount/type/owner. A key,
    # populated JSON, unknown entry or link refuses before the first deletion.
    pending = [base]
    seen = []
    authorities = set()
    while pending:
        path = pending.pop()
        owned_path(root, str(path.relative_to(root)))
        info = path.lstat()
        relative = str(path.relative_to(base))
        if relative == '.':
            expected = stat.S_IFDIR | 0o700
        elif relative in SCAFFOLDS:
            expected, authority = SCAFFOLDS[relative]
            authorities.add(authority)
        else:
            raise RuntimeError(f'unexpected root-home compose state: {relative}')
        if (path.is_mount() or info.st_mode != expected or info.st_uid != owner.st_uid
                or info.st_gid != owner.st_gid
                or (stat.S_ISREG(info.st_mode) and info.st_size != 0)):
            raise RuntimeError(f'root-home scaffold is not empty owned vendor state: {relative}')
        seen.append(path)
        if stat.S_ISDIR(info.st_mode):
            for child in path.iterdir():
                if str(child.relative_to(base)) not in SCAFFOLDS:
                    raise RuntimeError(f'unexpected root-home compose state: {child.relative_to(base)}')
                pending.append(child)

    for relative in authorities:
        path = owned_path(root, relative)
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or path.is_mount() or info.st_size > 64 * 1024
                or info.st_uid != owner.st_uid or info.st_gid != owner.st_gid
                or stat.S_IMODE(info.st_mode) & 0o002):
            raise RuntimeError(f'unsafe root-home tmpfiles authority: {relative}')
        data = path.read_bytes()
        if stat.S_IMODE(info.st_mode) & 0o020 and (
                relative != KONFLUX or stat.S_IMODE(info.st_mode) != 0o664
                or hashlib.sha256(data).hexdigest() != REVIEWED_KONFLUX_SHA256):
            raise RuntimeError(f'unreviewed root-group-writable authority: {relative}')
        rules = [line.split() for line in data.decode().splitlines()
                 if line.strip() and not line.lstrip().startswith('#')]
        rules = [rule for rule in rules if len(rule) > 1
                 and (rule[1] == '/var/roothome' or rule[1].startswith('/var/roothome/'))]
        if rules != [line.split() for line in RULES[relative]]:
            raise RuntimeError(f'root-home tmpfiles authority drifted: {relative}')

    for path in sorted(seen, key=lambda p: len(p.parts), reverse=True):
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()
    print(f'Root-home compose scaffolds retired: {len(seen)} empty entries; vendor runtime authorities unchanged')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        finalize(args.root)
    except (OSError, RuntimeError) as exc:
        parser.exit(1, f'Root-home compose finalization refused: {exc}\n')
