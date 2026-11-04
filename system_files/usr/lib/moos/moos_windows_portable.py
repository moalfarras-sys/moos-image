"""Data ownership and lifetime coordination for the existing Windows Store owner.

Publisher hashes describe only pristine downloaded files. Added/changed files
belong to the user. Unknown legacy/recovery trees are never disposable. This is
not a Wine sandbox, nor a lifetime lease for programs launched outside MoOS.
"""
from __future__ import annotations

import contextlib
import bisect
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Callable

MAX_ENTRIES = 100_000
MAX_BYTES = 16 * 1024 ** 3
ID = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\Z")


class Error(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _identity(s: os.stat_result) -> tuple:
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink,
            s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _owned(s: os.stat_result, *, directory: bool = False) -> None:
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if (not kind(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o022
            or (not directory and s.st_nlink != 1)):
        raise Error("unsafe_path")


def no_mounts(root: Path) -> None:
    """Check mountinfo BEFORE traversal, including same-filesystem bind mounts."""
    root = Path(os.path.abspath(root))
    try:
        lines = Path("/proc/self/mountinfo").read_text().splitlines()
        for line in lines:
            fields = line.split()
            if len(fields) < 10 or "-" not in fields:
                raise ValueError("mountinfo")
            raw = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), fields[4])
            point = Path(raw)
            if point == root or root in point.parents:
                raise Error("unsafe_path")
    except (OSError, ValueError) as e:
        raise Error("unsafe_path") from e


def _directory(path: Path, *, create: bool = False) -> None:
    # Refuse an aliased ancestor before mkdir can create anything through it.
    for ancestor in (path, *path.parents):
        try:
            if stat.S_ISLNK(ancestor.lstat().st_mode):
                raise Error("unsafe_path")
        except FileNotFoundError:
            continue
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    _owned(path.lstat(), directory=True)


def _open_source(root: Path, name: str) -> int:
    """Do not follow a source component swapped for a link during the copy."""
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parts = name.split("/")
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        result = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            _owned(os.fstat(result))
        except BaseException:
            os.close(result)
            raise
        return result
    finally:
        os.close(fd)


def _lock_path(base: Path) -> Path:
    if not ID.fullmatch(base.name):
        raise Error("unsafe_path")
    # The lock survives ordinary removal, explicit data removal and reinstall.
    return base.parent / ".locks" / (base.name + ".lock")


def validate_lease(base: Path, fd: int, *, shared: bool = True) -> None:
    path = _lock_path(base)
    _directory(path.parent)
    _directory(path.parent.parent)
    if stat.S_IMODE(path.parent.stat().st_mode) != 0o700:
        raise Error("unsafe_path")
    s = os.fstat(fd)
    _owned(s)
    if s.st_size or stat.S_IMODE(s.st_mode) != 0o600 or _identity(path.lstat()) != _identity(s):
        raise Error("unsafe_path")
    if shared:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise Error("app_in_use") from e


@contextlib.contextmanager
def lease(base: Path, *, exclusive: bool):
    path = _lock_path(base)
    _directory(path.parent.parent, create=True)
    _directory(path.parent, create=True)
    no_mounts(path.parent)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        validate_lease(base, fd, shared=False)
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise Error("app_in_use") from e
        validate_lease(base, fd, shared=False)
        yield fd
    finally:
        os.close(fd)


def read_receipt(path: Path) -> dict:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        _owned(before)
        if before.st_size > 32 * 1024 * 1024:
            raise Error("ownership_unknown")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            value = json.load(stream)
        if not isinstance(value, dict) or _identity(os.fstat(fd)) != _identity(before):
            raise Error("ownership_unknown")
        return value
    except (ValueError, UnicodeError) as e:
        raise Error("ownership_unknown") from e
    finally:
        os.close(fd)


def _relative(name: str) -> bool:
    return (isinstance(name, str) and bool(name) and len(name) <= 4096
            and not any(c in name for c in "\\\0") and not name.startswith("/")
            and not re.search(r"[\x00-\x1f\x7f]", name)
            and all(p not in ("", ".", "..") and not p.endswith((" ", "."))
                    and ":" not in p for p in name.split("/")))


def validate_manifest(value: object) -> dict:
    if not isinstance(value, dict) or not value or len(value) > MAX_ENTRIES:
        raise Error("ownership_unknown")
    folded = {}
    for name, item in value.items():
        if not _relative(name) or not isinstance(item, dict):
            raise Error("ownership_unknown")
        mode = item.get("mode")
        if type(mode) is not int or mode < 0 or mode > 0o777 or mode & 0o022:
            raise Error("ownership_unknown")
        if set(item) == {"kind", "mode"} and item["kind"] == "directory":
            pass
        elif (set(item) == {"kind", "bytes", "sha256", "mode"} and item["kind"] == "file"
              and type(item["bytes"]) is int and 0 <= item["bytes"] <= MAX_BYTES
              and isinstance(item["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
            pass
        else:
            raise Error("ownership_unknown")
        key = name.casefold()
        if key in folded:
            raise Error("data_conflict")
        folded[key] = item
    for name in value:
        parts = name.split("/")
        for i in range(1, len(parts)):
            if folded.get("/".join(parts[:i]).casefold(), {}).get("kind") != "directory":
                raise Error("ownership_unknown")
    return value


def snapshot(root: Path, cancelled: Callable[[], bool] = lambda: False) -> dict:
    no_mounts(root)
    entries: dict = {}
    total = 0
    def walk(fd: int, prefix: str) -> None:
        nonlocal total
        before = os.fstat(fd)
        _owned(before, directory=True)
        for name in sorted(os.listdir(fd)):
            if cancelled():
                raise Error("cancelled")
            relative = prefix + name
            if not _relative(relative) or len(entries) >= MAX_ENTRIES:
                raise Error("unsafe_path")
            s = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(s.st_mode):
                _owned(s, directory=True)
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    if _identity(os.fstat(child)) != _identity(s):
                        raise Error("data_changed")
                    entries[relative] = {"kind": "directory", "mode": stat.S_IMODE(s.st_mode)}
                    walk(child, relative + "/")
                finally:
                    os.close(child)
            else:
                _owned(s)
                total += s.st_size
                if total > MAX_BYTES:
                    raise Error("unsafe_path")
                file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    if _identity(os.fstat(file_fd)) != _identity(s):
                        raise Error("data_changed")
                    digest = hashlib.sha256()
                    while block := os.read(file_fd, 1024 * 1024):
                        if cancelled():
                            raise Error("cancelled")
                        digest.update(block)
                    if _identity(os.fstat(file_fd)) != _identity(s):
                        raise Error("data_changed")
                    entries[relative] = {"kind": "file", "bytes": s.st_size,
                                         "sha256": digest.hexdigest(), "mode": stat.S_IMODE(s.st_mode)}
                finally:
                    os.close(file_fd)
            if _identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) != _identity(s):
                raise Error("data_changed")
        if _identity(os.fstat(fd)) != _identity(before):
            raise Error("data_changed")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        walk(fd, "")
    finally:
        os.close(fd)
    validate_manifest(entries) if entries else None
    return entries


def carry(root: Path, stage: Path, baseline: object, cancelled: Callable[[], bool]) -> tuple[dict, dict]:
    """Return pristine NEW publisher manifest and stable OLD tree snapshot."""
    old_publisher = validate_manifest(baseline)
    old = snapshot(root, cancelled)
    new = snapshot(stage, cancelled)
    # A changed publisher file is user data too. Never silently replace it.
    protected = {n: v for n, v in old.items() if old_publisher.get(n) != v}
    folded_new = {n.casefold(): (n, v) for n, v in new.items()}
    ordered_new = sorted(folded_new)
    for name, item in protected.items():
        key = name.casefold()
        found = folded_new.get(key)
        if found and not (item["kind"] == found[1]["kind"] == "directory" and name == found[0]):
            raise Error("data_conflict")
        for i in range(1, len(name.split("/"))):
            parent = "/".join(name.split("/")[:i])
            found = folded_new.get(parent.casefold())
            if found and (found[0] != parent or found[1]["kind"] != "directory"):
                raise Error("data_conflict")
        if item["kind"] == "file":
            at = bisect.bisect_left(ordered_new, key + "/")
            if at < len(ordered_new) and ordered_new[at].startswith(key + "/"):
                raise Error("data_conflict")
    for name, item in protected.items():
        if cancelled():
            raise Error("cancelled")
        target = stage / name
        if item["kind"] == "directory":
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Stage is private and cannot contain a pre-existing colliding path.
            with os.fdopen(_open_source(root, name), "rb") as source, target.open("xb") as dest:
                shutil.copyfileobj(source, dest, 1024 * 1024)
                os.fchmod(dest.fileno(), item["mode"])
    expected = dict(new)
    expected.update(protected)
    # Parent directories for carried data can have belonged to the old publisher.
    for name in tuple(expected):
        parts = name.split("/")
        for i in range(1, len(parts)):
            parent = "/".join(parts[:i])
            expected.setdefault(parent, old[parent])
    for name, item in sorted(expected.items(), key=lambda pair: -pair[0].count("/")):
        if name not in new and item["kind"] == "directory":
            os.chmod(stage / name, item["mode"], follow_symlinks=False)
    if snapshot(root, cancelled) != old or snapshot(stage, cancelled) != expected:
        raise Error("data_changed")
    return new, old


def observed_idle(*roots: Path) -> None:
    """Also refuse observed open fds; canonical launches additionally hold SH."""
    from moos_appdrop import _assert_app_trees_idle, DropError
    try:
        _assert_app_trees_idle(*roots)
    except DropError as e:
        raise Error(e.code) from e
    paths = tuple(str(p.resolve()) for p in roots if p.exists())
    for process in Path("/proc").iterdir():
        if not process.name.isdecimal() or process.name == str(os.getpid()):
            continue
        try:
            if process.stat().st_uid != os.getuid():
                continue
            for fd in (process / "fd").iterdir():
                try:
                    value = os.readlink(fd).removesuffix(" (deleted)")
                except FileNotFoundError:
                    continue
                if any(value == p or value.startswith(p + "/") for p in paths):
                    raise Error("app_in_use")
        except FileNotFoundError:
            continue
        except OSError:
            # Unknown external references are not a race-free idle guarantee.
            continue


def _run(app_id: str, runner: str) -> int:
    if not ID.fullmatch(app_id):
        raise Error("not_installed")
    base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "moos/windows-apps" / app_id
    if not base.is_dir() or base.is_symlink():
        raise Error("not_installed")
    with lease(base, exclusive=False) as fd:
        return subprocess.call(["/usr/bin/bash", runner, "--app-leased", app_id, str(fd)], pass_fds=(fd,))


def main() -> int:
    try:
        if len(sys.argv) != 4 or sys.argv[1] != "run":
            return 2
        return _run(sys.argv[2], sys.argv[3])
    except (Error, OSError) as e:
        busy = isinstance(e, Error) and e.code == "app_in_use"
        message = ("البرنامج قيد التحديث أو الإزالة؛ أعد المحاولة بعد اكتمال العملية. | This program is being updated or removed; try again when it finishes."
                   if busy else "هذا البرنامج غير مثبّت أو تعذّر التحقق من ملفاته. افتح متجر MoOS. | This program is not installed or its files could not be checked. Open Mo Store.")
        if isinstance(e, Error) and e.code == "not_installed":
            message = "هذا البرنامج غير مثبّت. ثبّته من متجر MoOS. | This program is not installed. Install it from Mo Store."
        print(message, file=sys.stderr)
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(["notify-send", "--app-name=MoOS", "--icon=moos-store",
                            "--hint=string:desktop-entry:org.moos.store", "MoOS", message],
                           timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 1 if busy else 2


if __name__ == "__main__":
    raise SystemExit(main())
