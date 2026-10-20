#!/usr/bin/env python3
"""Retire proven inactive package state in the composed, unbooted Plasma base only.

The Atomic base configures its real SELinux module store under /etc. A distro-
sync can also seed a vendor-only /var store, which must not enter an immutable
image. Never discard a module absent from, or different in, the configured
store. Preserve the entire configured store and its actual boot policy bytes.
The finished-image state and identity gates remain unchanged.
"""
from __future__ import annotations

import argparse
import grp
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat

from finalize_image_state import owned_path


DERIVED = {'commit_num', 'file_contexts', 'file_contexts.homedirs', 'homedir_template',
           'modules_checksum', 'policy.kern', 'seusers', 'users_extra'}


def mount_points(text: str | None = None) -> set[Path]:
    """Read kernel mount identities; Path.is_mount misses same-filesystem binds."""
    if text is None:
        try:
            text = Path('/proc/self/mountinfo').read_text()
        except OSError as error:
            raise RuntimeError('cannot establish compose mount ownership') from error
    found = set()
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 10 or '-' not in fields[6:]:
            raise RuntimeError('invalid compose mount table')
        encoded = fields[4]
        if re.search(r'\\(?!040|011|012|134)', encoded):
            raise RuntimeError('invalid escaped mount path')
        decoded = re.sub(r'\\(040|011|012|134)',
                         lambda match: chr(int(match.group(1), 8)), encoded)
        path = Path(decoded)
        if not path.is_absolute():
            raise RuntimeError('nonabsolute compose mount path')
        found.add(path)
    if not found:
        raise RuntimeError('empty compose mount table')
    return found


def refuse_mounted_ancestors(root: Path, path: Path, mounts: set[Path]) -> None:
    for candidate in (path, *path.parents):
        if candidate == root:
            break  # the container/test root itself is naturally mounted
        if not candidate.is_relative_to(root):
            raise RuntimeError('compose path escaped root')
        if candidate in mounts or candidate.is_mount():
            raise RuntimeError(f'unsafe compose mount: {candidate.relative_to(root)}')


def tree(root: Path, relative: str, mounts: set[Path] | None = None) -> dict[str, str]:
    base = owned_path(root, relative)
    mounts = mount_points() if mounts is None else mounts
    refuse_mounted_ancestors(root, base, mounts)
    # Refuse mounted descendants before rglob enumerates another policy tree.
    if any(mount.is_relative_to(base) for mount in mounts):
        raise RuntimeError("unsafe mounted policy subtree")
    result = {}
    for path in (base, *sorted(base.rglob('*'))):
        owned_path(root, str(path.relative_to(root)))
        info = path.lstat()
        if path in mounts or path.is_mount() or info.st_uid != root.stat().st_uid:
            raise RuntimeError(f'unsafe owner or mount: {path.relative_to(root)}')
        if stat.S_ISREG(info.st_mode):
            if info.st_size > 32 * 1024**2:
                raise RuntimeError(f'unbounded policy file: {path.relative_to(root)}')
            result[str(path.relative_to(base))] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif not stat.S_ISDIR(info.st_mode):
            raise RuntimeError(f'unsafe policy entry: {path.relative_to(root)}')
    return result


def finalize(root: Path) -> None:
    root = root.resolve()
    if root == Path('/') and (not Path('/run/.containerenv').exists()
                             or Path('/run/ostree-booted').exists()):
        raise RuntimeError('canary finalization requires an unbooted build container')
    mounts = mount_points()
    # Newer Atomic bases declare this exact compatibility alias through
    # generated tmpfiles authority. Never follow or retire an arbitrary link.
    stale = owned_path(root, 'var/lib') / 'selinux'
    alias = stale.is_symlink()
    if alias:
        info = stale.lstat()
        authority = owned_path(root, 'usr/lib/tmpfiles.d/rpm-ostree-0-integration.conf')
        for parent in (root / 'var', stale.parent):
            if (parent.is_mount() or parent.stat().st_uid != root.stat().st_uid
                    or parent.stat().st_gid != root.stat().st_gid):
                raise RuntimeError('unsafe SELinux alias parent owner or mount')
        refuse_mounted_ancestors(root, stale, mounts)
        refuse_mounted_ancestors(root, authority, mounts)
        expected = ['L', '/var/lib/selinux', '-', '-', '-', '-', '../../etc/selinux']
        if (os.readlink(stale) != '../../etc/selinux' or stale.is_mount()
                or info.st_uid != root.stat().st_uid or info.st_gid != root.stat().st_gid
                or not stale.is_dir() or not authority.is_file() or authority.is_mount()
                or authority.stat().st_uid != root.stat().st_uid
                or authority.stat().st_gid != root.stat().st_gid
                or expected not in [line.split() for line in authority.read_text().splitlines()]):
            raise RuntimeError('unreviewed SELinux compatibility alias or missing authority')
    else:
        stale = owned_path(root, 'var/lib/selinux')
    immutable = owned_path(root, 'etc/selinux/targeted')
    before = {}
    if stale.exists() or alias:
        config = owned_path(root, 'etc/selinux/semanage.conf').read_text()
        stores = re.findall(r'^\s*store-root\s*=\s*([^#\n]+)', config, re.M)
        modes = re.findall(r'^\s*module-store\s*=\s*([^#\n]+)', config, re.M)
        if [s.strip() for s in stores] != ['/etc/selinux'] or [m.strip() for m in modes] != ['direct']:
            raise RuntimeError('the /var policy store is not proven inactive')
        before = tree(root, 'etc/selinux/targeted', mounts)
        if not alias:
            old = tree(root, 'var/lib/selinux', mounts)
            if set(p.name for p in stale.iterdir()) != {'targeted'}:
                raise RuntimeError('unexpected policy store beside targeted')
            active = stale / 'targeted/active'
            if set(p.name for p in (stale / 'targeted').iterdir()) != {
                    'active', 'semanage.read.LOCK', 'semanage.trans.LOCK'}:
                raise RuntimeError('unexpected transaction state in inactive policy store')
            if set(p.name for p in active.iterdir()) != DERIVED | {'modules'}:
                raise RuntimeError('unexpected inactive derived policy entry')
            for lock in ('semanage.read.LOCK', 'semanage.trans.LOCK'):
                if (stale / 'targeted' / lock).stat().st_size:
                    raise RuntimeError('nonempty inactive policy lock')
            inputs = {p: digest for p, digest in old.items() if p.startswith('targeted/active/modules/')}
            if not inputs:
                raise RuntimeError('inactive store has no verified module inputs')
            for path, digest in inputs.items():
                corresponding = path.removeprefix('targeted/')
                if before.get(corresponding) != digest:
                    raise RuntimeError(f'inactive module is absent or different in the real store: {path}')
        # Exactly the configured store's compiled bytes must be what boot loads.
        policies = list((immutable / 'policy').glob('policy.*'))
        if len(policies) != 1 or policies[0].read_bytes() != (immutable / 'active/policy.kern').read_bytes():
            raise RuntimeError('the actual boot policy does not match the configured module store')

    # Check all cleanup candidates before the first deletion. Runtime ownership
    # of the empty HPLIP directory is retained through its exact tmpfiles recipe.
    hp = owned_path(root, 'var/lib/hp')
    hp_rule = owned_path(root, 'usr/lib/tmpfiles.d/moos-plasma-next-state.conf')
    if hp.exists():
        info = hp.stat()
        if (not hp.is_dir() or hp.is_mount() or any(hp.iterdir())
                or stat.S_IMODE(info.st_mode) != 0o755
                or info.st_uid != root.stat().st_uid or info.st_gid != root.stat().st_gid):
            raise RuntimeError('HPLIP compose directory is not an empty owned 0755 directory')
        if hp_rule.exists():
            raise RuntimeError('refuse to replace existing canary tmpfiles authority')
    run_hp = owned_path(root, 'run/hplip')
    if run_hp.exists():
        info = run_hp.stat()
        policy = owned_path(root, 'usr/lib/tmpfiles.d/hplip.conf').read_text()
        if (not run_hp.is_dir() or run_hp.is_mount() or any(run_hp.iterdir())
                or info.st_uid != root.stat().st_uid or info.st_gid != grp.getgrnam('lp').gr_gid
                or stat.S_IMODE(info.st_mode) != 0o775
                or not re.search(r'^d\s+/run/hplip\s+0775\s+root\s+lp\s+-\s*$', policy, re.M)):
            raise RuntimeError('HPLIP runtime directory has no matching vendor authority')
    if stale.exists() or alias:
        if alias:
            stale.unlink()
        else:
            shutil.rmtree(stale)
        if tree(root, 'etc/selinux/targeted', mounts) != before:
            raise RuntimeError('configured SELinux policy changed during inactive-store retirement')
        if alias:
            print('Canary base: retired exact tmpfiles-owned SELinux compatibility alias; configured store and boot policy unchanged')
        else:
            print(f'Canary base: retired inactive vendor store; {len(inputs)} module inputs match the configured store; boot policy unchanged')
    if hp.exists():
        hp_rule.parent.mkdir(parents=True, exist_ok=True)
        hp_rule.write_text('# Empty compose directory, preserving native package ownership.\nd /var/lib/hp 0755 root root -\n')
        hp.rmdir()
    if run_hp.exists():
        run_hp.rmdir()
    print('Canary base package state canonicalized; the final MoOS gates remain mandatory')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--root', type=Path, default=Path('/'))
    args = parser.parse_args()
    try:
        finalize(args.root)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        parser.exit(1, f'Canary base finalization refused: {exc}\n')
