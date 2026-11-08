"""User-owned password-wallet preference; native KDE providers keep the secrets.

Never read a wallet item, change PAM, or create another Secret Service. The
default is off. Explicit Settings choices survive the old one-time UI repair.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import subprocess
import tempfile
import time


class WalletError(RuntimeError):
    pass


BUS_NAMES = {"org.kde.kwalletd", "org.kde.kwalletd5", "org.kde.kwalletd6",
             "org.kde.ksecretd", "org.freedesktop.secrets",
             "org.freedesktop.impl.portal.desktop.kwallet"}
PROVIDERS = {"/usr/bin/kwalletd5", "/usr/bin/kwalletd6", "/usr/bin/ksecretd"}
KEYS = (("Wallet", "Enabled"), ("KSecretD", "Enabled"),
        ("org.freedesktop.secrets", "apiEnabled"))


def command(argv, timeout=5):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise WalletError("Password wallet control is unavailable.") from error
    if result.returncode:
        raise WalletError("The password wallet did not accept the change.")
    return result.stdout.strip()


def bus(method, signature="", *arguments):
    activation = method == "StartServiceByName"
    argv = ["busctl", "--user", "--timeout=10s" if activation else "--timeout=3s", "--json=short", "call",
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", method]
    if signature:
        argv += [signature, *map(str, arguments)]
    try:
        reply = json.loads(command(argv, timeout=12 if activation else 5))["data"]
        if not isinstance(reply, list) or len(reply) != 1:
            raise ValueError("invalid bus reply")
        return reply[0]
    except (ValueError, KeyError, TypeError) as error:
        raise WalletError("The desktop session could not be verified.") from error


def names():
    value = bus("ListNames")
    if not isinstance(value, list) or not all(isinstance(n, str) for n in value):
        raise WalletError("The desktop session could not be verified.")
    return set(value) & BUS_NAMES


def read(group, key, default="false", path="kwalletrc"):
    return command(["kreadconfig6", "--file", str(path), "--group", group,
                    "--key", key, "--default", default])


def snapshot(target):
    """Read preference bytes only after checking the opened file itself."""
    try:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as handle:
        metadata = os.fstat(handle.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1 or metadata.st_size > 256*1024):
            raise WalletError("The existing wallet configuration was left unchanged.")
        data = handle.read(256*1024 + 1)
        if len(data) > 256*1024:
            raise WalletError("The existing wallet configuration was left unchanged.")
        return data


def state():
    empty = {"known": False, "available": False, "enabled": False,
             "active": False, "ready": False, "choice": ""}
    try:
        flags = [read(*key) for key in KEYS]
        choice = read("MoOS", "WalletChoice", "")
        if any(f not in ("true", "false") for f in flags) or choice not in ("", "on", "off"):
            raise WalletError("Invalid password wallet preference.")
        active = names()
        available = Path("/usr/bin/kwalletd6").is_file() and Path("/usr/bin/ksecretd").is_file()
        pinned = owned_processes()
        for fd in pinned.values():
            os.close(fd)
        ready = "org.freedesktop.secrets" in active and "org.kde.kwalletd6" in active
        consistent = len(set(flags)) == 1 and (not choice or (choice == "on") == (flags[0] == "true"))
        return {"known": consistent, "available": available,
                "enabled": all(f == "true" for f in flags), "active": bool(active),
                "ready": ready, "choice": choice}
    except (WalletError, OSError):
        return empty


def owned_processes():
    """Pin only same-user, native wallet providers before sending any signal."""
    processes = {}
    try:
        for name in sorted(names()):
            owner = bus("GetNameOwner", "s", name)
            pid = bus("GetConnectionUnixProcessID", "s", owner)
            uid = bus("GetConnectionUnixUser", "s", owner)
            if type(pid) is not int or pid <= 1 or type(uid) is not int or uid != os.getuid():
                raise WalletError("A password service has an unexpected owner.")
            if pid in processes:
                continue
            fd = os.pidfd_open(pid)
            processes[pid] = fd
            executable = os.readlink(f"/proc/{pid}/exe")
            if (executable not in PROVIDERS or os.stat(f"/proc/{pid}").st_uid != os.getuid()
                    or bus("GetConnectionUnixProcessID", "s", owner) != pid):
                raise WalletError("Another password service is in use; it was left unchanged.")
        return processes
    except (OSError, WalletError):
        for fd in processes.values():
            os.close(fd)
        raise WalletError("The running password service could not be safely identified.")


def stop(processes):
    for fd in processes.values():
        try:
            signal.pidfd_send_signal(fd, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for _ in range(50):
        exited = len(select.select(list(processes.values()), [], [], 0)[0]) == len(processes)
        if exited and not names():
            return
        time.sleep(.1)
    raise WalletError("The password wallet is still running. Try switching it off again.")


def save_and_lock(processes):
    """Let KDE persist unlocked collections before terminating its providers.

    Only collection paths/locked flags are read, never items or credentials.
    Address the verified unique bus owner, so no activation or replacement
    provider can receive the calls. A failed save refuses termination.
    """
    active = names()
    for name in ("org.freedesktop.secrets", "org.kde.kwalletd6", "org.kde.kwalletd5"):
        if name not in active:
            continue
        owner = bus("GetNameOwner", "s", name)
        if bus("GetConnectionUnixProcessID", "s", owner) not in processes:
            raise WalletError("The password service changed; try again.")
        base = ["busctl", "--user", "--auto-start=no", "--timeout=5s", "--json=short"]
        if name != "org.freedesktop.secrets":
            command(base + ["call", owner, "/modules/kwalletd6" if name.endswith("6") else "/modules/kwalletd5",
                            "org.kde.KWallet", "closeAllWallets"])
            continue
        try:
            reply = json.loads(command(base + ["get-property", owner, "/org/freedesktop/secrets",
                                               "org.freedesktop.Secret.Service", "Collections"]))
            collections = reply["data"]
            if (reply["type"] != "ao" or not isinstance(collections, list) or len(collections) > 256
                    or any(not isinstance(p, str) or not re.fullmatch(r"/[A-Za-z0-9_/]+", p) for p in collections)):
                raise ValueError("invalid collections")
            unlocked = []
            for path in collections:
                locked = json.loads(command(base + ["get-property", owner, path,
                                        "org.freedesktop.Secret.Collection", "Locked"]))
                if locked.get("type") != "b" or type(locked.get("data")) is not bool:
                    raise ValueError("invalid lock state")
                if locked["data"] is False:
                    unlocked.append(path)
            if unlocked:
                result = json.loads(command(base + ["call", owner, "/org/freedesktop/secrets",
                    "org.freedesktop.Secret.Service", "Lock", "ao", str(len(unlocked)), *unlocked]))
                if result.get("type") != "aoo" or result.get("data") != [unlocked, "/"]:
                    raise ValueError("collections not saved and locked")
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise WalletError("The wallet could not be safely locked; it was left running.") from error


def change(wanted):
    if wanted not in ("on", "off"):
        raise WalletError("Choose on or off.")
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home()/".config")
    if not config.is_absolute():
        raise WalletError("The user configuration directory is unavailable.")
    try:
        config.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = config.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o022):
            raise WalletError("The user configuration directory has an unexpected owner.")
    except OSError as error:
        raise WalletError("The user configuration directory is unavailable.") from error
    target = config/"kwalletrc"
    try:
        original = snapshot(target)
    except OSError as error:
        raise WalletError("The existing wallet configuration was left unchanged.") from error
    flags = [read(*key) for key in KEYS]
    if any(value not in ("true", "false") for value in flags):
        raise WalletError("The existing wallet preference could not be read.")
    if wanted == "on" and not state()["available"]:
        raise WalletError("The native password wallet is not available on this system.")
    try:
        lock = os.open(config/".moos-wallet.lock", os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK, 0o600)
    except OSError as error:
        raise WalletError("The password wallet preference is busy or unavailable.") from error
    processes = {}
    temporary = None
    try:
        info = os.fstat(lock)
        if info.st_uid != os.getuid() or info.st_nlink != 1 or not stat.S_ISREG(info.st_mode):
            raise WalletError("The password wallet preference is busy or unavailable.")
        os.fchmod(lock, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise WalletError("Another wallet change is still running.") from error
        processes = owned_processes()  # refuse unrelated owners before writing
        fd, path = tempfile.mkstemp(prefix=".moos-wallet-", dir=config)
        temporary = Path(path)
        with os.fdopen(fd, "wb") as handle:
            handle.write(original or b"")
        value = "true" if wanted == "on" else "false"
        for group, key in KEYS:
            command(["kwriteconfig6", "--file", path, "--group", group, "--key", key, "--type", "bool", value])
        command(["kwriteconfig6", "--file", path, "--group", "Wallet", "--key", "First Use", "--type", "bool", "false"])
        command(["kwriteconfig6", "--file", path, "--group", "MoOS", "--key", "WalletChoice", wanted])
        if (any(read(*key, path=path) != value for key in KEYS)
                or read("MoOS", "WalletChoice", "", path=path) != wanted
                or read("Wallet", "First Use", path=path) != "false"):
            raise WalletError("The password wallet preference could not be saved.")
        current = snapshot(target)
        if current != original:
            raise WalletError("The wallet preference changed elsewhere; try again.")
        if wanted == "off":
            save_and_lock(processes)
        published = temporary.read_bytes()
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        if snapshot(target) != original:
            raise WalletError("The wallet preference changed elsewhere; try again.")
        os.replace(temporary, target)
        temporary = None
        if wanted == "off":
            stop(processes)
        else:
            try:
                for service in ("org.kde.kwalletd6", "org.freedesktop.impl.portal.desktop.kwallet"):
                    bus("StartServiceByName", "su", service, "0")
                for _ in range(50):
                    measured = state()
                    if (measured["known"] and measured["enabled"]
                            and measured["ready"] and measured["choice"] == "on"):
                        return measured
                    time.sleep(.1)
                else:
                    raise WalletError("The password wallet did not become ready.")
            except WalletError:
                # Restore only the bytes we just published, retaining concurrent
                # user edits. Never remove or inspect the encrypted wallet files.
                if snapshot(target) == published:
                    if original is None:
                        target.unlink()
                    else:
                        fd, path = tempfile.mkstemp(prefix=".moos-wallet-restore-", dir=config)
                        with os.fdopen(fd, "wb") as handle:
                            handle.write(original)
                        os.replace(path, target)
                newcomers = owned_processes()
                try:
                    for pid, fd in newcomers.items():
                        if pid not in processes:
                            try:
                                signal.pidfd_send_signal(fd, signal.SIGTERM)
                            except ProcessLookupError:
                                pass
                finally:
                    for fd in newcomers.values():
                        os.close(fd)
                raise
        measured = state()
        if (not measured["known"] or measured["enabled"] != (wanted == "on")
                or (wanted == "off" and measured["active"])):
            raise WalletError("The saved wallet preference could not be confirmed.")
        return measured
    except OSError as error:
        raise WalletError("The wallet preference could not be safely saved.") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        for fd in processes.values():
            os.close(fd)
        os.close(lock)
