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
from pathlib import Path
import re
import shutil
import stat

from finalize_image_state import owned_path


DERIVED = {'commit_num', 'file_contexts', 'file_contexts.homedirs', 'homedir_template',
           'modules_checksum', 'policy.kern', 'seusers', 'users_extra'}


def tree(root: Path, relative: str) -> dict[str, str]:
    base = owned_path(root, relative)
    result = {}
    for path in (base, *sorted(base.rglob('*'))):
        owned_path(root, str(path.relative_to(root)))
        info = path.lstat()
        if path.is_mount() or info.st_uid != root.stat().st_uid:
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
    stale = owned_path(root, 'var/lib/selinux')
    immutable = owned_path(root, 'etc/selinux/targeted')
    before = {}
    if stale.exists():
        config = owned_path(root, 'etc/selinux/semanage.conf').read_text()
        stores = re.findall(r'^\s*store-root\s*=\s*([^#\n]+)', config, re.M)
        modes = re.findall(r'^\s*module-store\s*=\s*([^#\n]+)', config, re.M)
        if [s.strip() for s in stores] != ['/etc/selinux'] or [m.strip() for m in modes] != ['direct']:
            raise RuntimeError('the /var policy store is not proven inactive')
        before = tree(root, 'etc/selinux/targeted')
        old = tree(root, 'var/lib/selinux')
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
    if stale.exists():
        shutil.rmtree(stale)
        if tree(root, 'etc/selinux/targeted') != before:
            raise RuntimeError('configured SELinux policy changed during inactive-store retirement')
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
