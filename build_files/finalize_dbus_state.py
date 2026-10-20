#!/usr/bin/env python3
"""Retire the exact vendor D-Bus runtime alias from an unbooted image compose."""
import argparse
import os
from pathlib import Path
import stat

from finalize_image_state import owned_path


RULES = [['d', '/var/lib/dbus', '0755', '-', '-', '-'],
         ['L', '/var/lib/dbus/machine-id', '-', '-', '-', '-', '/etc/machine-id']]


def finalize(root: Path) -> None:
    root = root.resolve()
    if root == Path('/') and (not Path('/run/.containerenv').exists()
                             or Path('/run/ostree-booted').exists()):
        raise RuntimeError('D-Bus state retirement requires an unbooted build container')
    base = owned_path(root, 'var/lib/dbus')
    if not base.exists():
        return
    owner = root.stat()
    info = base.lstat()
    if (info.st_mode != stat.S_IFDIR | 0o755 or base.is_mount()
            or info.st_uid != owner.st_uid or info.st_gid != owner.st_gid):
        raise RuntimeError('unsafe D-Bus compose directory')
    entries = base.iterdir()
    first = next(entries, None)
    if first is None:
        return
    if first.name != 'machine-id' or next(entries, None) is not None:
        raise RuntimeError('unexpected D-Bus compose state')

    # Inspect this one final component without resolving its absolute target
    # into the build host (particularly in --root fixtures). Never walk it.
    link = base / 'machine-id'
    info = link.lstat()
    if (not stat.S_ISLNK(info.st_mode) or os.readlink(link) != '/etc/machine-id'
            or link.is_mount() or info.st_uid != owner.st_uid or info.st_gid != owner.st_gid):
        raise RuntimeError('unrecognized D-Bus machine-id alias')
    authority = owned_path(root, 'usr/lib/tmpfiles.d/dbus.conf')
    info = authority.lstat()
    if (not stat.S_ISREG(info.st_mode) or authority.is_mount() or info.st_size > 64 * 1024
            or info.st_uid != owner.st_uid or info.st_gid != owner.st_gid
            or stat.S_IMODE(info.st_mode) & 0o022):
        raise RuntimeError('unsafe D-Bus tmpfiles authority')
    rules = [line.split() for line in authority.read_text().splitlines()
             if line.strip() and not line.lstrip().startswith('#')]
    rules = [rule for rule in rules if len(rule) > 1
             and (rule[1] == '/var/lib/dbus' or rule[1].startswith('/var/lib/dbus/'))]
    if rules != RULES:
        raise RuntimeError('D-Bus tmpfiles authority drifted')
    target = owned_path(root, 'etc/machine-id')
    if target.exists():
        info = target.lstat()
        if (not stat.S_ISREG(info.st_mode) or target.is_mount() or info.st_size > 14
                or info.st_uid != owner.st_uid or info.st_gid != owner.st_gid
                or stat.S_IMODE(info.st_mode) & 0o022
                or target.read_bytes() not in (b'', b'uninitialized\n')):
            raise RuntimeError('D-Bus machine-id target is not a pristine image file')
    link.unlink()  # only the proven template alias; never the machine identity
    print('D-Bus runtime alias retired; image machine-id and vendor tmpfiles authority unchanged')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        finalize(args.root)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'D-Bus compose finalization refused: {exc}\n')
