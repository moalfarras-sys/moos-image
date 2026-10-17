"""Read Store-owned Android receipts consistently, without starting Android."""
import json
import hashlib
import os
from pathlib import Path
import re
import stat

PACKAGE = re.compile(r"(?=.{3,255}\Z)[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_~+-]{0,63}\Z")
PREFIX = "android-"


def record_id(package: str) -> str:
    """Keep even a maximum-length package within StoreBridge's 255-byte ID."""
    return PREFIX + (package if len(PREFIX + package) <= 255
                     else hashlib.sha256(package.encode()).hexdigest())


def package_for_id(data_home: Path, app_id: str) -> str | None:
    if not app_id.startswith(PREFIX):
        return None
    tail = app_id[len(PREFIX):]
    if PACKAGE.fullmatch(tail):
        record, invalid = read_record(data_home, tail)
        return tail if record and not invalid else None
    if SHA.fullmatch(tail):
        for path in (data_home / "moos/android").glob("*.json"):
            if record_id(path.stem) == app_id:
                record, invalid = read_record(data_home, path.stem)
                if record and not invalid:
                    return path.stem
    return None


def read_record(data_home: Path, package: str) -> tuple[dict | None, bool]:
    """(receipt, invalid): absent is distinct from damaged/linked state."""
    if not isinstance(package, str) or not PACKAGE.fullmatch(package):
        return None, True
    path = data_home / "moos/android" / (package + ".json")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_uid != os.getuid() or info.st_mode & 0o022 or info.st_size > 65536):
                return None, True
            value = json.loads(stream.read(65537).decode("utf-8"))
    except FileNotFoundError:
        return None, False
    except (OSError, ValueError):
        return None, True
    if (not isinstance(value, dict) or type(value.get("schema")) is not int
            or value["schema"] != 1 or value.get("id") != package
            or value.get("package") != package):
        return None, True
    digest, version = value.get("sha256"), value.get("version")
    if (not isinstance(digest, str) or not SHA.fullmatch(digest)
            or not isinstance(version, str) or (version and not VERSION.fullmatch(version))):
        return None, True
    source, catalog_id = value.get("source"), value.get("catalog_id")
    if not ((source == "file" and catalog_id == "")
            or (source == "catalog" and catalog_id == package)):
        return None, True
    return value, False


def unlisted(data_home: Path, claimed: set[str]) -> list[dict]:
    """A receipt alone is not installation: require the runtime's app directory."""
    result = []
    for path in sorted((data_home / "moos/android").glob("*.json")):
        package = path.stem
        if package in claimed:
            continue
        record, invalid = read_record(data_home, package)
        runtime = data_home / "waydroid/data/data" / package
        try:
            installed = stat.S_ISDIR(runtime.lstat().st_mode)
        except OSError:
            installed = False
        if record and not invalid and installed:
            result.append(record)
    return result
