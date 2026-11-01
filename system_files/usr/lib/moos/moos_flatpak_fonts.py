"""Host-font discovery for Flatpak, owned by font migration and Store lifecycle.

Preserves native grid scan metadata and named Meyar Arabic pairing, without
generic defaults, launch wrappers, permission changes or cache removal.
Fontconfig salts distinguish Flatpak's runtime /usr/share/fonts from the host
remap. Immutable font directories have zero mtimes, so the salt also follows
the booted signed OS and the installed runtime commit, including rollback.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys


FILE = "00-moos-host-font-cache.conf"
PREFIX = (b'<?xml version="1.0"?>\n'
          b'<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
          b'<!-- MoOS owned host-font discovery v1; preserve personal font rules. -->\n'
          b'<!-- delivery=')
MIDDLE = b' -->\n<fontconfig>\n  <remap-dir as-path="/usr/share/fonts" salt="moos-host-v1-'
SUFFIX = b'">/run/host/fonts</remap-dir>\n</fontconfig>\n'
SCAN_RULES = b'''  <match target="scan">
    <test name="family" compare="eq"><string>Meyar Mono</string></test>
    <edit name="spacing" mode="assign"><int>100</int></edit>
  </match>
  <match target="scan">
    <test name="family" compare="eq"><string>Meyar Mono Arabic</string></test>
    <edit name="spacing" mode="assign"><int>100</int></edit>
  </match>
'''
PAIRING_RULES = b'''  <alias binding="strong"><family>Meyar Sans</family><default><family>Meyar Arabic</family></default></alias>
  <alias binding="strong"><family>Meyar Mono</family><default><family>Meyar Mono Arabic</family></default></alias>
'''
POLICY_REVISION = 2
LOCK = b"MoOS host-font discovery lock v1\n"
HEX = re.compile(r"[0-9a-f]{64}\Z")
APP = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}\Z")
RUNTIME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+\Z")
MAX_FILE = 32768


def output(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise ValueError("Host-font discovery could not read " + args[0])
    if len(result.stdout) > 2 * 1024 * 1024:
        raise ValueError("Host-font discovery metadata exceeds its bound")
    return result.stdout.strip()


def signed_generation(document: dict) -> str:
    if not isinstance(document, dict):
        raise ValueError("Invalid deployment metadata document")
    deployments = document.get("deployments")
    if not isinstance(deployments, list):
        raise ValueError("Missing deployment metadata")
    booted = [d for d in deployments if isinstance(d, dict) and d.get("booted") is True]
    if len(booted) != 1:
        raise ValueError("Need exactly one booted deployment")
    checksum = booted[0].get("checksum", "")
    origin = booted[0].get("container-image-reference", "")
    if not isinstance(checksum, str) or not HEX.fullmatch(checksum):
        raise ValueError("Invalid booted deployment checksum")
    if not isinstance(origin, str) or not re.fullmatch(
            r"ostree-image-signed:docker://ghcr\.io/moalfarras-sys/moos(?:-nvidia|-cloud|-arm)?@sha256:[0-9a-f]{64}", origin):
        raise ValueError("Host-font discovery requires a signed MoOS deployment")
    return checksum


def fragment(deployment: str, runtime: str, commit: str) -> bytes:
    return runtime_fragment(deployment, [(runtime, commit)])


def runtime_fragment(deployment: str, runtimes: list[tuple[str, str]]) -> bytes:
    return _render_fragment(deployment, runtimes, POLICY_REVISION)


def _render_fragment(deployment: str, runtimes: list[tuple[str, str]], revision: int) -> bytes:
    if (not HEX.fullmatch(deployment) or not 1 <= len(runtimes) <= 32 or any(
            not RUNTIME.fullmatch(runtime) or not HEX.fullmatch(commit) for runtime, commit in runtimes)):
        raise ValueError("Invalid host-font delivery generation")
    delivery = [deployment, sorted(set(runtimes))]
    if revision == POLICY_REVISION:
        # A new scan policy cannot reuse the old dual-width cached metadata.
        # Include both revision and exact rule bytes, even for a same OS/runtime.
        delivery = [POLICY_REVISION, hashlib.sha256(SCAN_RULES + PAIRING_RULES).hexdigest(), *delivery]
    elif revision != 1:
        raise ValueError("Unknown font discovery policy revision")
    encoded = json.dumps(delivery, separators=(',', ':')).encode()
    generation = hashlib.sha256(encoded).hexdigest()
    suffix = SUFFIX if revision == 1 else SUFFIX.replace(b'</fontconfig>', SCAN_RULES + PAIRING_RULES + b'</fontconfig>')
    data = PREFIX + encoded.hex().encode() + MIDDLE + generation.encode() + suffix
    if len(data) > MAX_FILE:
        raise ValueError("Font delivery generation exceeds its bound")
    return data


def owned(data: bytes) -> bool:
    # Recompute the self-described generation, so a salt-only edit is refused.
    # Hex keeps runtime names containing '--' safe inside an XML comment.
    if len(data) > MAX_FILE or not data.startswith(PREFIX) or not data.endswith(b'</fontconfig>\n'):
        return False
    try:
        metadata, _body = data[len(PREFIX):].split(MIDDLE, 1)
        delivery = json.loads(bytes.fromhex(metadata.decode('ascii')))
        if len(delivery) == 2:
            # Exact be3 prototype only: it was never delivered. Admission is for
            # bounded old/fixed upgrade/recovery evidence, not arbitrary XML.
            revision = 1
            deployment, runtimes = delivery
        elif len(delivery) == 4 and delivery[:2] == [POLICY_REVISION, hashlib.sha256(SCAN_RULES + PAIRING_RULES).hexdigest()]:
            revision = POLICY_REVISION
            deployment, runtimes = delivery[2:]
        else:
            return False
        return data == _render_fragment(deployment, [tuple(row) for row in runtimes], revision)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return False


def mount_points() -> set[str]:
    # ismount() misses a same-filesystem bind mount. Decode mountinfo's escaped
    # names, never resolve links to decide that an unknown destination is safe.
    return {re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), line.split()[4])
            for line in Path("/proc/self/mountinfo").read_text().splitlines()}


def check_stat(info: os.stat_result, directory: bool) -> None:
    kind = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not kind or info.st_uid != os.getuid() or info.st_mode & 0o022 or (not directory and info.st_nlink != 1):
        raise ValueError("Preserve unknown, linked or writable font configuration")


def directory(parent: int, name: str, path: Path, mounts: set[str], create: bool = True) -> int:
    if str(path) in mounts:
        raise ValueError("Preserve mounted font configuration")
    try:
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    except FileNotFoundError:
        if not create:
            raise
        os.mkdir(name, mode=0o700, dir_fd=parent)
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        check_stat(os.fstat(fd), True)
    except BaseException:
        os.close(fd)
        raise
    return fd


def read_file(parent: int, name: str, path: Path, mounts: set[str]) -> tuple[bytes, os.stat_result] | None:
    if str(path) in mounts:
        raise ValueError("Preserve mounted font configuration")
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        check_stat(info, False)
        if info.st_size > MAX_FILE:
            raise ValueError("Preserve oversized font configuration")
        return handle.read(MAX_FILE + 1), info


def write_new(parent: int, name: str, data: bytes) -> None:
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def identity(info: os.stat_result) -> tuple:
    # Reading a previous revision can update atime; it is not an edit.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def install(home: Path, app_id: str, data: bytes | None, mounts: set[str] | None = None) -> bool:
    """Publish one bounded owned fragment; return False for an unchanged policy.

    The caller supplies an actually installed application ID. Tests use a
    private home and exact native runtime metadata; no real app config is used.
    """
    if not APP.fullmatch(app_id) or len(app_id) > 255 or (data is not None and not owned(data)):
        raise ValueError("Invalid application or font discovery fragment")
    if not home.is_absolute() or home.resolve() != home:
        raise ValueError("Preserve aliased home directory")
    mounts = mount_points() if mounts is None else mounts
    with contextlib.ExitStack() as stack:
        fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, fd)
        check_stat(os.fstat(fd), True)
        path = home
        for part in (".var", "app", app_id, "config", "fontconfig", "conf.d"):
            path /= part
            # refresh() verifies installation before this bounded path is made.
            # Preparing it at install time also covers the app's first launch.
            try:
                fd = directory(fd, part, path, mounts, create=data is not None)
            except FileNotFoundError:
                return False  # retirement never manufactures a missing path
            stack.callback(os.close, fd)
        previous = read_file(fd, FILE, path / FILE, mounts)
        if previous is None and data is None:
            return False
        if previous is not None and not owned(previous[0]):
            raise ValueError("Preserve edited host-font discovery fragment")
        lock_name = ".moos-host-font-cache.lock"
        previous_lock = read_file(fd, lock_name, path / lock_name, mounts)
        if previous_lock is None:
            write_new(fd, lock_name, LOCK)
        elif previous_lock[0] != LOCK:
            raise ValueError("Preserve unknown font discovery lock")
        lock = os.open(lock_name, os.O_RDWR | os.O_NOFOLLOW, dir_fd=fd)
        stack.callback(os.close, lock)
        check_stat(os.fstat(lock), False)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = read_file(fd, FILE, path / FILE, mounts)
        if previous is None and data is None:
            return False
        if previous is not None:
            if not owned(previous[0]):
                raise ValueError("Preserve edited host-font discovery fragment")
            if previous[0] == data:
                return False
            recovery_name = ".moos-host-font-cache-recovery"
            recovery = directory(fd, recovery_name, path / recovery_name, mounts)
            stack.callback(os.close, recovery)
            write_new(recovery, secrets.token_hex(16) + ".conf", previous[0])
            os.fsync(recovery)
            if data is None:
                current = read_file(fd, FILE, path / FILE, mounts)
                if current is None or current[0] != previous[0] or identity(current[1]) != identity(previous[1]):
                    raise ValueError("Font configuration changed during retirement")
                # The exact old bytes already have a unique durable recovery.
                # Unlink only this validated owned fragment, never any cache.
                os.unlink(FILE, dir_fd=fd)
                os.fsync(fd)
                return True
        temporary = ".moos-host-font-cache-" + secrets.token_hex(16)
        write_new(fd, temporary, data)
        try:
            current = read_file(fd, FILE, path / FILE, mounts)
            if previous is None:
                # link is an atomic no-clobber publication, unlike replace.
                if current is not None:
                    raise ValueError("Font configuration changed during publication")
                os.link(temporary, FILE, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
            else:
                if current is None or current[0] != previous[0] or identity(current[1]) != identity(previous[1]):
                    raise ValueError("Font configuration changed during publication")
                os.replace(temporary, FILE, src_dir_fd=fd, dst_dir_fd=fd)
            os.fsync(fd)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary, dir_fd=fd)
        return True


def refresh(app_ids: list[str] | None = None, *, home: Path | None = None, query=output,
            flatpak: str = "/usr/bin/flatpak", retire: bool = False) -> list[str]:
    """Refresh existing app homes after login or a completed Store transaction."""
    home = Path.home() if home is None else home
    applications: dict[str, set[str]] = {}
    installations = query([flatpak, "list", "--columns=installation"]).splitlines()
    if len(installations) > 4096 or any(scope not in ("user", "system") for scope in installations):
        raise ValueError("Host-font discovery has not qualified custom Flatpak installations")
    # One app home serves all installed branches, including a user and system
    # app with the same ID. Cover every exact runtime ref instead of guessing
    # the active branch from an ambiguous bare `flatpak info APP` request.
    rows = query([flatpak, "list", "--app", "--columns=application,runtime,installation"]).splitlines()
    if len(rows) > 2048:
        raise ValueError("Installed Flatpak inventory exceeds its bound")
    for row in rows:
        fields = row.split('\t')
        if len(fields) != 3:
            raise ValueError("Incomplete installed Flatpak application metadata")
        app_id, runtime, scope = fields
        if not APP.fullmatch(app_id) or len(app_id) > 255 or not RUNTIME.fullmatch(runtime) or scope not in ('user', 'system'):
            raise ValueError("Invalid installed Flatpak application inventory")
        applications.setdefault(app_id, set()).add(runtime)
    if app_ids is None:
        app_ids = list(applications)
    app_ids = list(dict.fromkeys(app_ids))
    if len(app_ids) > 512 or any(not APP.fullmatch(a) or len(a) > 255 for a in app_ids):
        raise ValueError("Invalid installed Flatpak application inventory")
    if not app_ids:
        return []
    if any(app_id not in applications for app_id in app_ids):
        raise ValueError("Host-font discovery requested an app that is not installed")
    if retire:
        # Explicit maintenance before an old, helper-unaware OS rollback.
        # Native font matching/choices and every cache stay untouched. This is
        # not an automatic guard for a GRUB rollback chosen without preparation.
        return [app_id for app_id in app_ids if install(home, app_id, None)]
    deployment = signed_generation(json.loads(query(["/usr/bin/rpm-ostree", "status", "--json"])))
    runtime_commits: dict[str, str] = {}
    # Resolve all inputs before publishing: an unavailable/ambiguous runtime
    # must preserve every earlier owned policy, rather than partially update.
    for runtime in sorted({r for app_id in app_ids for r in applications[app_id]}):
        # Flatpak1.18.4 run and unscoped info use the same native global runtime
        # search: user first, then system installations in native priority order.
        # Even a system app can therefore use the matching USER runtime.
        commit = query([flatpak, "info", "--show-commit", "runtime/" + runtime])
        if not HEX.fullmatch(commit):
            raise ValueError("Invalid installed Flatpak runtime commit")
        runtime_commits[runtime] = commit
    changed = []
    for app_id in app_ids:
        try:
            data = runtime_fragment(deployment, [(r, runtime_commits[r]) for r in applications[app_id]])
            if install(home, app_id, data):
                changed.append(app_id)
        except (OSError, ValueError) as error:
            raise ValueError(app_id + ": " + str(error)) from error
    return changed


if __name__ == "__main__":
    try:
        changed = refresh(flatpak=sys.argv[1] if len(sys.argv) == 2 else "/usr/bin/flatpak")
        print("MoOS host-font discovery refreshed: " + str(len(changed)))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit("MoOS host-font discovery refused: " + str(error))
