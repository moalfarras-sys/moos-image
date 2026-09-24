#!/usr/bin/env python3
"""MoOS's seams in Plasma: install the reviewed set, refuse drift, and load the real lock screen.

WHY THIS EXISTS (plan row P6.7)

MoOS restyles Plasma by REPLACING ten files inside two Plasma packages (the shell package's lock
screen, widget explorer, edit mode, defaults and panel template; three breeze components the login,
lock and logout screens draw). Each replacement is a fork of the upstream file at one Plasma
version. Nothing in the build knew which version: the survival gate proves MoOS's bytes are still
there, which is exactly what goes wrong when upstream moves on.

Measured 2026-09-24 against Plasma 6.8 beta 1 (6.7.90): upstream rewrote LockScreenUi.qml and
MainBlock.qml and removed `VirtualKeyboardLoader` from org.kde.breeze.components. MoOS's 6.7 copy
instantiates that type, so on 6.8 kscreenlocker would print "Failed to load lockscreen QML,
falling back to built-in locker" — every MoOS machine would get the emergency locker the day the
base image moved to 6.8, while every gate stayed green. The mutable `kinoite-main:44` tag moves
by itself; nobody would have had to touch this repository for it to happen.

So this tool, run by build.sh and build-arm.sh after the last package transaction:

  1. reads the image's Plasma version and selects the ONE reviewed seam set for it (none → fail);
  2. installs that set's variant files over the shell/component paths;
  3. refuses any seam whose upstream bytes (rpm's own file digest) differ from what the set was
     reviewed against — an upstream bug fix to the lock screen must reach MoOS's copy, not be
     silently shadowed by it;
  4. refuses a Plasma file modified in the image that is neither a registered seam nor a
     registered edit — the registry is checked against rpm, not against memory;
  5. starts kscreenlocker's real greeter in testing mode, offscreen, with no session bus and a
     throwaway HOME, and fails on any QML load failure.

`probe-lockscreen` also runs on a workstation: it is isolated from the live session by
construction (no bus address that exists, private HOME/XDG dirs, offscreen platform).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "plasma-seams" / "seams.json"
SHELL_ID = "org.kde.plasma.desktop"
GREETER = "/usr/libexec/kscreenlocker_greet"

# Plasma files the build EDITS in place (sed), rather than replaces. They follow whatever upstream
# ships, so they are not seams; they are named so rpm -V can account for every modified file.
REGISTERED_EDITS = {
    "/usr/lib64/qt6/qml/org/kde/breeze/components/qmldir":
        "build.sh drops `prefer` so the breeze components resolve from disk (MoOS's ActionButton/Clock)",
    "/usr/share/wayland-sessions/plasma.desktop":
        "the identity scrub renames the session",
    **{f"/usr/share/plasma/look-and-feel/{name}/metadata.json":
       "hide_breeze_global_themes.py hides Breeze's Global Theme wrappers from the picker"
       for name in ("org.kde.breeze.desktop", "org.kde.breezedark.desktop",
                    "org.kde.breezetwilight.desktop")},
}
PLASMA_PACKAGES = ("plasma-desktop", "plasma-workspace", "kscreenlocker", "kwin",
                   "libplasma", "plasma-login-manager")

# What kscreenlocker and the QML engine print when the lock screen did NOT load.
LOAD_FAILURES = (
    re.compile(r"Failed to load lockscreen QML"),
    re.compile(r"Error loading QML file"),
    re.compile(r"\bis not a type\b"),
    re.compile(r"\bmodule \"[^\"]+\" is not installed"),
    re.compile(r"\bType \S+ unavailable\b"),
    re.compile(r"\bis not installed\b"),
)
# Script errors count only when they come from a file MoOS owns: upstream is not MoOS's to judge
# under an offscreen platform with no bus, but MoOS's own code must run clean there.
SCRIPT_ERROR = re.compile(r"\b(TypeError|ReferenceError|Unable to assign)\b")
MOOS_OWNED = re.compile(r"/lockscreen/|/org/kde/breeze/components/|/org/moos/")
LOCKED = re.compile(r"^Locked at \d+")


class SeamError(Exception):
    pass


def version_key(text: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", text.split("-")[0])
    if not parts:
        raise SeamError(f"not a version: {text!r}")
    return tuple(int(p) for p in parts)


def load_registry(path: Path = REGISTRY) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != 1:
        raise SeamError(f"{path}: unknown schema {data.get('schema')!r}")
    return data


def select_set(registry: dict, plasma_version: str) -> dict:
    """The one set whose [from, before) range holds this Plasma version."""
    key = version_key(plasma_version)
    matches = [s for s in registry["sets"]
               if version_key(s["plasma"]["from"]) <= key < version_key(s["plasma"]["before"])]
    if len(matches) != 1:
        known = ", ".join(f"{s['id']} [{s['plasma']['from']}, {s['plasma']['before']})"
                          for s in registry["sets"])
        raise SeamError(
            f"no reviewed MoOS seam set for Plasma {plasma_version} (sets: {known}). MoOS replaces "
            "files inside Plasma's own packages; a Plasma it was never reviewed against can load "
            "a broken lock screen. Derive and review a set: build_files/plasma-seams/README.md")
    return matches[0]


def rpm(*args: str, root: str = "/") -> str:
    cmd = ["rpm", *args] if root == "/" else ["rpm", "--root", root, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SeamError(f"{' '.join(cmd)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


def rpm_verify(package: str, root: str = "/") -> str:
    """`rpm -V` output. Its exit status is 1 whenever anything differs, which is expected here."""
    cmd = ["rpm", "-V", "--nodeps", "--noscripts", package]
    if root != "/":
        cmd[1:1] = ["--root", root]
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def package_version(package: str, root: str = "/") -> str:
    return rpm("-q", "--qf", "%{VERSION}", package, root=root).strip()


def upstream_digests(package: str, root: str = "/") -> dict[str, str]:
    algo = rpm("-q", "--qf", "%{FILEDIGESTALGO}", package, root=root).strip()
    if algo != "8":  # RPM_HASH_SHA256
        raise SeamError(f"{package} records file digests with algorithm {algo}, not SHA-256")
    out = rpm("-q", "--qf", "[%{FILENAMES}\t%{FILEDIGESTS}\n]", package, root=root)
    return dict(line.split("\t", 1) for line in out.splitlines() if "\t" in line)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rooted(root: str, path: str) -> Path:
    return Path(root) / path.lstrip("/")


def apply_and_verify(registry: dict, root: str = "/", seams_dir: Path = HERE / "plasma-seams",
                     dry_run: bool = False) -> list[str]:
    """Install the selected set and refuse drift. Returns the report lines."""
    vpkg = registry["version_package"]
    plasma = package_version(vpkg, root)
    chosen = select_set(registry, plasma)
    report = [f"Plasma {plasma} ({vpkg}) -> MoOS seam set {chosen['id']}"]

    errors: list[str] = []
    digests: dict[str, dict[str, str]] = {}
    for seam in registry["seams"]:
        path, package = seam["path"], seam["package"]
        if package not in digests:
            digests[package] = upstream_digests(package, root)
        upstream = digests[package].get(path)
        reviewed = chosen["reviewed"].get(path, [])
        if upstream is None:
            errors.append(f"{package} no longer ships {path}: MoOS's copy would sit where nothing "
                          "loads it. Find where upstream moved it and re-review the seam.")
        elif upstream not in reviewed:
            errors.append(
                f"{path}: {package} {package_version(package, root)} ships upstream bytes "
                f"{upstream[:16]}…, and set {chosen['id']} was reviewed against "
                f"{', '.join(d[:16] + '…' for d in reviewed) or 'nothing'}. Upstream changed a file "
                "MoOS replaces; re-derive MoOS's copy (three-way merge, README.md) and record "
                "the new digest only after the lock-screen probe passes.")

        source = chosen["sources"].get(path)
        target = rooted(root, path)
        if source:
            src = seams_dir / source
            if not src.is_file():
                errors.append(f"set {chosen['id']} names {source}, which is not in {seams_dir}")
                continue
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_symlink():
                    target.unlink()
                shutil.copyfile(src, target)
                os.chmod(target, 0o644)
            report.append(f"  installed {chosen['id']} variant: {path}")
        elif not target.is_file():
            errors.append(f"{path}: MoOS's copy is missing from the image")

    # Every modified Plasma file must be accounted for, from rpm's point of view.
    seam_paths = {s["path"] for s in registry["seams"]}
    for package in PLASMA_PACKAGES:
        try:
            rpm("-q", package, root=root)
        except SeamError:
            continue  # not installed in this edition
        for line in rpm_verify(package, root).splitlines():
            flags, _, rest = line.partition(" ")
            fields = rest.split()
            if len(flags) < 3 or flags[2] != "5" or not fields:
                continue
            path = fields[-1]
            if " c " in f" {rest} " or path.startswith("/etc/"):
                continue  # configuration files are the owner's and MoOS's to change
            if path not in seam_paths and path not in REGISTERED_EDITS:
                errors.append(f"{path} ({package}) is modified in the image but is neither a "
                              "registered seam nor a registered edit — register it in seams.json "
                              "so the next Plasma is reviewed for it")

    if errors:
        raise SeamError("\n".join(errors))
    report.append(f"  {len(registry['seams'])} seams match their reviewed upstream bytes")
    return report


def classify_greeter_output(lines: list[str]) -> list[str]:
    """The lines that mean the lock screen did not load, or MoOS's own code errored."""
    bad = []
    for line in lines:
        if any(p.search(line) for p in LOAD_FAILURES):
            bad.append(line)
        elif SCRIPT_ERROR.search(line) and MOOS_OWNED.search(line):
            bad.append(line)
    return bad


def probe_lockscreen(shell_dir: str | None = None, timeout: float = 60.0,
                     settle: float = 4.0, greeter: str = GREETER) -> tuple[bool, list[str]]:
    """Start the real greeter in testing mode, isolated, and read what the QML engine says.

    shell_dir: a shell package directory to test instead of the installed one (it is copied into
    a private XDG_DATA_HOME under another id, so the system package is never touched).
    """
    if not os.access(greeter, os.X_OK):
        return False, [f"{greeter} is missing: kscreenlocker is not installed"]
    work = Path(tempfile.mkdtemp(prefix="moos-lockprobe-"))
    try:
        dirs = {name: work / name for name in ("home", "config", "cache", "data", "runtime")}
        for d in dirs.values():
            d.mkdir()
        dirs["runtime"].chmod(0o700)
        shell = SHELL_ID
        if shell_dir:
            shell = "org.moos.lockprobe"
            dest = dirs["data"] / "plasma" / "shells" / shell
            shutil.copytree(shell_dir, dest, symlinks=True)
            meta = dest / "metadata.json"
            data = json.loads(meta.read_text(encoding="utf-8"))
            data["KPlugin"]["Id"] = shell
            meta.write_text(json.dumps(data), encoding="utf-8")
        env = {
            "PATH": "/usr/bin:/usr/sbin",
            "HOME": str(dirs["home"]),
            "XDG_CONFIG_HOME": str(dirs["config"]),
            "XDG_CACHE_HOME": str(dirs["cache"]),
            "XDG_DATA_HOME": str(dirs["data"]),
            "XDG_RUNTIME_DIR": str(dirs["runtime"]),
            "XDG_DATA_DIRS": "/usr/share",
            # An address that does not exist: the probe can never reach a live session bus.
            "DBUS_SESSION_BUS_ADDRESS": f"unix:path={dirs['runtime']}/no-bus",
            "QT_QPA_PLATFORM": "offscreen",
            # Deterministic in a build container with no GPU; the QML still loads in full.
            "QT_QUICK_BACKEND": "software",
            "QT_FORCE_STDERR_LOGGING": "1",
            "QT_LOGGING_RULES": "*.debug=false;qml.warning=true;js.warning=true",
            "QML_DISABLE_DISK_CACHE": "1",
            "LANG": "C.UTF-8",
        }
        proc = subprocess.Popen([greeter, "--testing", "--shell", shell], env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
        # Raw reads, split here: a buffered readline() after select() strands every line but the
        # first of a chunk in Python's buffer, where select() can no longer see it.
        fd = proc.stdout.fileno()
        os.set_blocking(fd, False)
        pending = b""
        lines: list[str] = []
        locked_at = None

        def drain() -> None:
            nonlocal pending, locked_at
            while True:
                try:
                    chunk = os.read(fd, 65536)
                except BlockingIOError:
                    return
                if not chunk:
                    return
                pending += chunk
                *complete, pending = pending.split(b"\n")
                for raw in complete:
                    line = raw.decode("utf-8", "replace")
                    lines.append(line)
                    if locked_at is None and LOCKED.search(line):
                        locked_at = time.monotonic()

        sel = selectors.DefaultSelector()
        sel.register(fd, selectors.EVENT_READ)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if locked_at is not None and time.monotonic() > locked_at + settle:
                break
            if proc.poll() is not None:
                break
            if sel.select(timeout=0.2):
                drain()
        exited = proc.poll()
        if exited is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        drain()
        if pending:
            lines.append(pending.decode("utf-8", "replace"))
        sel.close()
        proc.stdout.close()

        problems = classify_greeter_output(lines)
        if exited is not None:
            problems.append(f"the greeter exited by itself with status {exited} before it was stopped")
        if locked_at is None:
            problems.append(f"the greeter never reported 'Locked at' within {timeout:.0f} s")
        return (not problems), (problems or lines)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="install the reviewed set, refuse drift, probe the lock screen")
    b.add_argument("--root", default="/")
    b.add_argument("--timeout", type=float, default=60.0)
    v = sub.add_parser("verify", help="refuse drift without installing anything")
    v.add_argument("--root", default="/")
    s = sub.add_parser("select", help="print the set for a Plasma version")
    s.add_argument("version")
    p = sub.add_parser("probe-lockscreen", help="load the lock screen in an isolated greeter")
    p.add_argument("--shell-dir")
    p.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args(argv)

    try:
        registry = load_registry()
        if args.cmd == "select":
            print(select_set(registry, args.version)["id"])
            return 0
        if args.cmd in ("build", "verify"):
            for line in apply_and_verify(registry, args.root, dry_run=(args.cmd == "verify")):
                print(f"MoOS seams: {line}")
            if args.cmd == "verify":
                return 0
        ok, lines = probe_lockscreen(getattr(args, "shell_dir", None),
                                     timeout=getattr(args, "timeout", 60.0))
        if not ok:
            print("GATE FAIL: the lock screen does not load on this Plasma:", file=sys.stderr)
            for line in lines:
                print(f"  {line}", file=sys.stderr)
            print("           An owner would meet kscreenlocker's emergency locker instead of "
                  "MoOS's lock screen. See build_files/plasma-seams/README.md.", file=sys.stderr)
            return 1
        print("MoOS seams: the lock screen loads in kscreenlocker's real greeter")
        return 0
    except SeamError as exc:
        print(f"GATE FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
