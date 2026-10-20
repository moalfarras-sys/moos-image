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
