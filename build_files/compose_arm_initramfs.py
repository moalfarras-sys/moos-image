#!/usr/bin/env python3
"""Compose ARM initramfs with a private build HOME and an empty root-home guard.

Only an empty, owned, unmounted real directory may be removed. Unknown bytes
remain intact and produce bounded metadata diagnostics, never file contents.
--root and --dracut are private-fixture seams; production uses the image root.
"""
import argparse
from collections import deque
import json
import os
from pathlib import Path
import re
import signal
import shutil
import stat
import subprocess
import tempfile

from finalize_image_state import owned_path


# Native c4b9b693 bootc input: systemd-tmpfiles creates these EMPTY vendor
# placeholders during package transactions. The authority lines, exact tree,
# ownership and file metadata must all match before the first unlink. In
# particular, provisioned authorized_keys is never an allowed retirement.
VENDOR_RULES = {
    'rpm-ostree-0-integration.conf': {
        'd /var/roothome 0700 root root -',
    },
    'konflux-buildinfo-contentsets.conf': {
        'd /var/roothome/buildinfo 0755 - - -',
        'd /var/roothome/buildinfo/content_manifests 0755 - - -',
        'f /var/roothome/buildinfo/content_manifests/content-sets.json 0644 - - -',
        'f /var/roothome/buildinfo/labels.json 0644 - - -',
    },
    'provision.conf': {
        'd- /var/roothome/.ssh :0700 root :root -',
        'f^ /var/roothome/.ssh/authorized_keys :0600 root :root - ssh.authorized_keys.root',
    },
}
VENDOR_DIRECTORIES = {'.ssh': 0o700, 'buildinfo': 0o755,
                      'buildinfo/content_manifests': 0o755}
VENDOR_FILES = {'buildinfo/labels.json', 'buildinfo/content_manifests/content-sets.json'}
VENDOR_AUTHORITY_MODES = {'rpm-ostree-0-integration.conf': 0o644,
                          'konflux-buildinfo-contentsets.conf': 0o664,
                          'provision.conf': 0o644}


def mountpoints():
    text = Path('/proc/self/mountinfo').read_text()
    return {re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), line.split()[4])
            for line in text.splitlines() if len(line.split()) > 4}


def describe(directory):
    """At most 64 names/type/size records, without following child symlinks."""
    pending = [(directory, 0)]
    count = 0
    mounts = mountpoints()
    while pending and count < 64:
        parent, depth = pending.pop()
        with os.scandir(parent) as entries:
            for entry in entries:
                if count >= 64:
                    break
                info = entry.stat(follow_symlinks=False)
                kind = ('directory' if stat.S_ISDIR(info.st_mode) else
                        'symlink' if stat.S_ISLNK(info.st_mode) else
                        'file' if stat.S_ISREG(info.st_mode) else 'special')
                print(json.dumps({'name': str(Path(entry.path).relative_to(directory)),
                                  'type': kind, 'size': info.st_size}), flush=True)
                count += 1
                if (kind == 'directory' and depth < 2
                        and entry.path not in mounts and not os.path.ismount(entry.path)):
                    pending.append((Path(entry.path), depth + 1))


def validate_root(root):
    if ((root / 'run/ostree-booted').exists()
            or root == Path('/') and not Path('/run/.containerenv').exists()):
        raise RuntimeError('initramfs composition requires an unbooted build container')


def build_path(root, relative):
    path = owned_path(root, relative)
    mounts = mountpoints()
    for current in (path, *path.parents):
        if current == root:
            break
        if current.exists():
            info = current.lstat()
            if (str(current) in mounts or os.path.ismount(current)
                    or info.st_uid != os.geteuid()):
                raise RuntimeError('refusing a mount or foreign-owned compose path')
    return path


def empty_owned_home(home):
    info = home.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or str(home) in mountpoints() or os.path.ismount(home)):
        raise RuntimeError('root-home path is a symlink, mount, foreign-owned or non-directory; preserved')
    if next(home.iterdir(), None) is not None:
        print('FATAL: root-home contains unknown bytes; preserved metadata follows:', flush=True)
        describe(home)
        raise RuntimeError('root-home is not empty; preserved')


def retire_empty_vendor_home(root, home):
    """Retire only the exact reproduced empty vendor tree, never unknown state."""
    build_path(root, str(home.relative_to(root)))
    if not any(home.iterdir()):
        return False

    def refuse(reason):
        print(f'FATAL: {reason}; root-home preserved; metadata follows:', flush=True)
        describe(home)
        raise RuntimeError('vendor root-home retirement refused')

    mounts = mountpoints()
    if any(Path(mount).is_relative_to(home) for mount in mounts):
        refuse('root-home contains a mount')
    owner = root.stat()
    info = home.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != owner.st_uid
            or info.st_gid != owner.st_gid or stat.S_IMODE(info.st_mode) != 0o700):
        refuse('root-home ownership, type or mode differs from its vendor rule')
    actual = {}
    for current, directories, files in os.walk(home, followlinks=False):
        for name in directories + files:
            path = Path(current) / name
            relative = str(path.relative_to(home))
            actual[relative] = path.lstat()
            if len(actual) > 5:
                refuse('root-home has additional entries')
    if set(actual) != VENDOR_FILES | set(VENDOR_DIRECTORIES):
        # The unchanged empty guard will diagnose all other unknown tree shapes.
        return False
    for relative, info in actual.items():
        if info.st_uid != owner.st_uid or info.st_gid != owner.st_gid:
            refuse('vendor root-home entry has unexpected ownership')
        if relative in VENDOR_FILES:
            if (not stat.S_ISREG(info.st_mode) or info.st_size != 0
                    or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o644):
                refuse('vendor root-home file is nonempty, linked, or has unexpected mode/type')
        elif not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != VENDOR_DIRECTORIES[relative]:
            refuse('vendor root-home directory has unexpected mode/type')
    for name, expected in VENDOR_RULES.items():
        # A local/runtime override is not permission to reinterpret vendor rules.
        for prefix in ('etc/tmpfiles.d', 'run/tmpfiles.d', 'usr/local/lib/tmpfiles.d'):
            try:
                override = owned_path(root, f'{prefix}/{name}')
            except RuntimeError:
                refuse('vendor tmpfiles override path is unsafe')
            if override.exists() or override.is_symlink():
                refuse('vendor tmpfiles authority is overridden')
        try:
            authority = build_path(root, f'usr/lib/tmpfiles.d/{name}')
            info = authority.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner.st_uid
                    or info.st_gid != owner.st_gid
                    or stat.S_IMODE(info.st_mode) != VENDOR_AUTHORITY_MODES[name]
                    or info.st_size > 32768):
                raise RuntimeError('vendor tmpfiles authority has unexpected metadata')
            lines = [' '.join(line.split()) for line in authority.read_text().splitlines()
                     if line.strip() and not line.lstrip().startswith('#')]
        except (OSError, RuntimeError) as error:
            refuse(f'vendor tmpfiles authority is unavailable: {error}')
        relevant = [line for line in lines if len(line.split()) > 1
                    and line.split()[1].startswith('/var/roothome')]
        if set(relevant) != expected or len(relevant) != len(expected):
            refuse('vendor tmpfiles authority lines differ from reviewed rules')
    # All paths and all authorities passed together. Remove no recursive tree,
    # and leave root-home itself for the ordinary empty-directory guard.
    for relative in sorted(VENDOR_FILES):
        (home / relative).unlink()
    for relative in sorted(VENDOR_DIRECTORIES, key=lambda value: value.count('/'), reverse=True):
        (home / relative).rmdir()
    print('Retired exact empty vendor root-home placeholders (5 entries; authorities verified)', flush=True)
    return True


def cleanup_scratch(root, scratch):
    """Only remove our private tree after refusing mounts and foreign owners."""
    path = owned_path(root, str(scratch.relative_to(root)))
    mounts = mountpoints()
    # Test the entire mount table before walking: even inspecting descendants
    # of a producer-created mount would cross the private scratch boundary.
    if any(Path(mount).is_relative_to(path) for mount in mounts):
        raise RuntimeError('private compose scratch contains a mount; preserved')
    if not path.is_dir() or path.stat().st_uid != os.geteuid():
        raise RuntimeError('private compose scratch is not an owned real directory; preserved')
    for current, directories, files in os.walk(path, followlinks=False):
        for name in directories + files:
            child = Path(current) / name
            if os.path.ismount(child) or child.lstat().st_uid != os.geteuid():
                raise RuntimeError('private compose scratch has a mount or foreign owner; preserved')
    shutil.rmtree(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel')
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--dracut', default='dracut')
    parser.add_argument('--timeout', type=float, default=900)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not re.fullmatch(r'[A-Za-z0-9._+~-]+', args.kernel):
        parser.error('invalid kernel release')
    if not 0 < args.timeout <= 900:
        parser.error('compose timeout must be positive and at most 900 seconds')
    validate_root(root)
    home = build_path(root, 'var/roothome')
    # Containerfile.arm deliberately supplies /tmp as a private tmpfs mount.
    # It is an allowed scratch parent, never a cleanup target; only our newly
    # generated directory beneath it is removed.
    scratch_parent = owned_path(root, 'tmp')
    if (not scratch_parent.is_dir() or scratch_parent.stat().st_uid != os.geteuid()):
        raise RuntimeError('compose scratch parent is not an owned real directory')
    if home.exists() or home.is_symlink():
        retire_empty_vendor_home(root, home)
        empty_owned_home(home)
    else:
        home.mkdir(mode=0o700)
    status = 1
    scratch = None
    try:
        scratch = Path(tempfile.mkdtemp(prefix='moos-dracut-', dir=scratch_parent))
        env = dict(os.environ)
        for key, name in (('HOME', 'home'), ('XDG_CONFIG_HOME', 'config'),
                          ('XDG_CACHE_HOME', 'cache'), ('XDG_DATA_HOME', 'data'),
                          ('XDG_STATE_HOME', 'state'), ('XDG_RUNTIME_DIR', 'runtime')):
            path = scratch / name
            path.mkdir(mode=0o700)
            env[key] = str(path)
        # Keep diagnostics private until the same last-20-lines contract is
        # printed; cleanup is restricted to our new, unmounted scratch tree.
        log = scratch / 'dracut.log'
        command = [args.dracut, '--no-hostonly', '--force', '--reproducible',
                   '--add', 'ostree plymouth',
                   str(root / f'usr/lib/modules/{args.kernel}/initramfs.img'), args.kernel]
        with log.open('wb') as stream:
            process = subprocess.Popen(command, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                status = process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                status = 124
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass  # The timed-out producer already exited; classification stays124.
                process.wait(timeout=5)
        with log.open(errors='replace') as stream:
            print(''.join(deque(stream, maxlen=20)), end='', flush=True)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'FATAL: compose or log inspection failed: {error}', flush=True)
        if status == 0:
            status = 1
    finally:
        # Both cleanup attempts run independently. A cleanup/diagnostic fault
        # must preserve the producer's original nonzero exit, never report green.
        if scratch is not None:
            try:
                cleanup_scratch(root, scratch)
            except (OSError, RuntimeError) as error:
                print(f'FATAL: {error}; private scratch preserved at {scratch}', flush=True)
                if status == 0:
                    status = 1
        try:
            empty_owned_home(home)
            home.rmdir()
        except (OSError, RuntimeError) as error:
            print(f'FATAL: {error}', flush=True)
            if status == 0:
                status = 1
    return status if status >= 0 else 128 - status


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as error:
        print(f'FATAL: {error}', flush=True)
        raise SystemExit(1)
