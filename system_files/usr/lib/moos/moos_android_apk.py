"""MoOS Android APK — what the APK Android keeps says about an installed Android app.

Mo Store installs a catalogue Android app by handing its pinned APK to the Android container,
which keeps it at /data/app/~~<random>/<package>-<random>/base.apk (Android 11 and later;
/data/app/<package>-<suffix>/base.apk before). The container's /data is
$XDG_DATA_HOME/waydroid/data. That file, not a record MoOS wrote, is what Android runs, and it
says which build is installed:

  package       the manifest's package attribute
  version code  android:versionCode (with android:versionCodeMajor): the number Android compares.
                It refuses an APK whose version code is lower than the one it keeps.
  version name  android:versionName when it is plain text, for people to read
  signer        the SHA-256 of the first signer's certificate in the APK Signing Block (v3, else
                v2). Android refuses an update signed by another key. The catalogue records the
                same digest as `signer`.
  sha256        the file's own digest, read only when its size is the pin's

moos-storectl (check-updates, Update all, `update <package>`) and moos-store-index (the app page)
ask pin_is_update() whether the catalogue's pin is an update for an installed app, so that
updates.json and index.json give one answer:

  * an APK that IS the pin, byte for byte, is up to date;
  * otherwise, when both version codes are known, the pin is an update only when Android would
    take it as one: a higher version code than the APK Android keeps, and no other signer when
    both signers are known. A build newer than the catalogue's (the app's own library updated it,
    or the person installed one) is never offered the older pin;
  * when what Android keeps cannot be read or compared, only the Store's own record can say which
    bytes the Store installed, and the pin is an update when the record names other bytes. An app
    with no record of the Store's (the earlier Mo Store wrote none; another installer put it
    there) is then left alone.

An APK the person installed from a file (moos-storectl install-file writes its record with an
empty catalog_id) is theirs: both programs call it adopted and never ask this rule.

The pin names its version code in its file name. The main repository publishes every APK as
<package>_<versionCode>[_<signer prefix>].apk, and build_files/verify_store_catalog.py holds every
Android pin to that name (pin_version_code()).

Nothing here starts the container or runs a program. Files are read through no link, a manifest
up to MANIFEST_LIMIT bytes and a signing block up to SIGNING_BLOCK_LIMIT bytes.

API:
  kept_apk_dirs(waydroid_data, package) -> list[Path] | None
      the folders Android keeps `package` in; None when Android's app folder cannot be read
  kept(waydroid_data, package, pin_size=None, *, unsized_limit=..., remembered=None)
      -> ApkFacts | None: the one APK Android keeps for `package`, or None when there is not
      exactly one readable APK of that package (two while Android replaces the app)
  read_apk(path, pin_size=None, *, unsized_limit=..., remembered=None) -> ApkFacts | None
      `remembered` {path: ApkFacts}: facts read earlier are reused while the file's identity
      (device, inode, size, times) is unchanged; ApkFacts.to_json()/from_json() keep them
  manifest_facts(data) -> (package, version_code, version_name) of a compiled manifest
  pin_version_code(url, package) -> int | None
  pin_is_update(*, pin_sha256, pin_code, pin_signer, kept, recorded_sha256) -> bool
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
from pathlib import Path
import re
import stat
import struct
from typing import Any, Mapping
import urllib.parse
import zipfile
import zlib

MANIFEST = "AndroidManifest.xml"
# A compiled manifest is tens of kilobytes (VLC's is 119 KiB); a larger one is not read.
MANIFEST_LIMIT = 4 * 1024 * 1024
# The signing block holds certificates and signatures, a few KiB padded to 4 KiB.
SIGNING_BLOCK_LIMIT = 16 * 1024 * 1024
# What is hashed of an APK whose pin names no size, as moos-storectl caps such a download.
UNSIZED_LIMIT = 2 * 1024 ** 3
BLOCK = 1024 * 1024

ANDROID_NAMESPACE = "http://schemas.android.com/apk/res/android"
# android:versionCode, android:versionName and android:versionCodeMajor (android.R.attr).
VERSION_CODE, VERSION_NAME, VERSION_CODE_MAJOR = 0x0101021B, 0x0101021C, 0x01010576
# Chunk types of Android's binary XML (ResourceTypes.h) and the value types read here.
XML, STRING_POOL, RESOURCE_MAP, START_ELEMENT = 0x0003, 0x0001, 0x0180, 0x0102
TYPE_STRING, TYPE_FIRST_INT, TYPE_LAST_INT = 0x03, 0x10, 0x1F
UTF8_FLAG = 0x100
NO_INDEX = 0xFFFFFFFF
# The APK Signing Block, just before the zip's central directory, and its signature schemes.
SIGNING_BLOCK_MAGIC = b"APK Sig Block 42"
SIGNATURE_V3, SIGNATURE_V2 = 0xF05368C0, 0x7109871A

_SHA256_RE = re.compile(r"[0-9a-f]{64}")


@dataclasses.dataclass(frozen=True)
class ApkFacts:
    identity: tuple[int, int, int, int, int]  # device, inode, size, mtime_ns, ctime_ns
    package: str | None
    version_code: int | None
    version_name: str | None
    signer: str | None
    sha256: str | None

    def to_json(self) -> dict[str, Any]:
        return dataclasses.asdict(self) | {"identity": list(self.identity)}

    @classmethod
    def from_json(cls, value: object) -> "ApkFacts | None":
        """Facts kept by to_json(), or None for anything else."""
        if not isinstance(value, dict) or set(value) != {f.name for f in dataclasses.fields(cls)}:
            return None
        identity = value["identity"]
        if not (isinstance(identity, list) and len(identity) == 5
                and all(type(part) is int for part in identity)):
            return None
        texts = ("package", "version_name", "signer", "sha256")
        if not all(value[name] is None or isinstance(value[name], str) for name in texts):
            return None
        code = value["version_code"]
        if not (code is None or (type(code) is int and code >= 0)):
            return None
        if any(value[name] is not None and not _SHA256_RE.fullmatch(value[name])
               for name in ("signer", "sha256")):
            return None
        return cls(tuple(identity), value["package"], code, value["version_name"],
                   value["signer"], value["sha256"])


# ── where Android keeps an app ─────────────────────────────────────────────────────────────────
def kept_apk_dirs(waydroid_data: Path, package: str) -> list[Path] | None:
    """The folders Android keeps `package` in under its /data (`waydroid_data`).

    /data/app/~~<random>/<package>-<random>/ (Android 11 and later) or /data/app/<package>-<n>/,
    never through a link. None when /data/app cannot be listed: Android's system account owns it,
    so another login account cannot read it.
    """
    prefix = f"{package}-"
    found: list[Path] = []
    try:
        with os.scandir(Path(waydroid_data) / "app") as entries:
            for entry in entries:
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if entry.name.startswith(prefix):
                    found.append(Path(entry.path))
                    continue
                with os.scandir(entry.path) as inner:
                    found += [Path(item.path) for item in inner if item.name.startswith(prefix)
                              and item.is_dir(follow_symlinks=False)]
    except OSError:
        return None
    return found


def kept(waydroid_data: Path, package: str, pin_size: int | None = None, *,
         unsized_limit: int = UNSIZED_LIMIT,
         remembered: Mapping[str, ApkFacts] | None = None) -> ApkFacts | None:
    """The one APK Android keeps for `package`, read; None when there is not exactly one APK of
    that package to read (two while Android replaces the app, a link, an unreadable folder)."""
    folders = kept_apk_dirs(waydroid_data, package)
    if folders is None or len(folders) != 1:
        return None
    facts = read_apk(folders[0] / "base.apk", pin_size, unsized_limit=unsized_limit,
                     remembered=remembered)
    if facts is None or (facts.package is not None and facts.package != package):
        return None
    return facts


# ── one APK ────────────────────────────────────────────────────────────────────────────────────
def read_apk(path: Path, pin_size: int | None = None, *, unsized_limit: int = UNSIZED_LIMIT,
             remembered: Mapping[str, ApkFacts] | None = None) -> ApkFacts | None:
    """What one APK says about itself; None when it is not a regular file that can be read.

    The file is opened through no link. Its digest is read only when its size is `pin_size` (or,
    with no size pinned, when it is at most `unsized_limit` bytes): another size is other bytes.
    A manifest or signing block that cannot be read leaves those facts None.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                             | getattr(os, "O_CLOEXEC", 0))
    except OSError:
        return None
    try:
        with os.fdopen(descriptor, "rb") as handle:
            status = os.fstat(handle.fileno())
            if not stat.S_ISREG(status.st_mode):
                return None
            identity = (status.st_dev, status.st_ino, status.st_size, status.st_mtime_ns,
                        status.st_ctime_ns)
            size = status.st_size
            digest_wanted = size == pin_size if pin_size is not None else size <= unsized_limit
            earlier = remembered.get(str(path)) if remembered is not None else None
            if earlier is not None and earlier.identity == identity \
                    and (earlier.sha256 is not None or not digest_wanted):
                return earlier
            package, version_code, version_name = _manifest(handle)
            signer = _signer(handle, size)
            digest = None
            if digest_wanted:
                handle.seek(0)
                hasher = hashlib.sha256()
                for block in iter(lambda: handle.read(BLOCK), b""):
                    hasher.update(block)
                digest = hasher.hexdigest()
    except OSError:
        return None
    return ApkFacts(identity, package, version_code, version_name, signer, digest)


def _manifest(handle: Any) -> tuple[str | None, int | None, str | None]:
    nothing = (None, None, None)
    try:
        handle.seek(0)
        with zipfile.ZipFile(handle) as archive:
            info = archive.getinfo(MANIFEST)
            if info.file_size > MANIFEST_LIMIT:
                return nothing
            with archive.open(info) as member:
                data = member.read(MANIFEST_LIMIT + 1)
    except (zipfile.BadZipFile, KeyError, ValueError, NotImplementedError, RuntimeError,
            EOFError, zlib.error, struct.error):
        return nothing
    return manifest_facts(data) if len(data) <= MANIFEST_LIMIT else nothing


class _Strings:
    """A binary XML string pool, decoded one string at a time."""

    def __init__(self, data: bytes, offset: int, header: int, size: int):
        count, _styles, flags, start = struct.unpack_from("<IIII", data, offset + 8)
        if header < 28 or header + 4 * count > size:
            raise ValueError("string pool")
        self.data, self.utf8 = data, bool(flags & UTF8_FLAG)
        self.offsets = struct.unpack_from(f"<{count}I", data, offset + header)
        self.base, self.end = offset + start, offset + size

    def get(self, index: int) -> str | None:
        if index >= len(self.offsets):
            return None
        at = self.base + self.offsets[index]
        if self.utf8:
            for _ in range(2):                  # the length in UTF-16 units, then in bytes
                length = self._unit(at, 1)
                at += 1
                if length & 0x80:
                    length = ((length & 0x7F) << 8) | self._unit(at, 1)
                    at += 1
            width, encoding = 1, "utf-8"
        else:
            length = self._unit(at, 2)
            at += 2
            if length & 0x8000:
                length = ((length & 0x7FFF) << 16) | self._unit(at, 2)
                at += 2
            width, encoding = 2, "utf-16-le"
        if at + width * length > self.end:
            raise ValueError("a string runs out of its pool")
        return self.data[at:at + width * length].decode(encoding)

    def _unit(self, at: int, width: int) -> int:
        if at + width > self.end:
            raise ValueError("a string runs out of its pool")
        return int.from_bytes(self.data[at:at + width], "little")


def manifest_facts(data: bytes) -> tuple[str | None, int | None, str | None]:
    """(package, version code, version name) of a compiled AndroidManifest.xml.

    Read as Android's own package reader reads them, from the <manifest> element's attributes:
    each version attribute by its android.R.attr id (or, without one, its name in the android
    namespace), a version code only when it is an integer. A None for what it does not say.
    """
    nothing = (None, None, None)
    try:
        kind, header, total = struct.unpack_from("<HHI", data, 0)
        if kind != XML or header < 8 or not header <= total <= len(data):
            return nothing
        strings: _Strings | None = None
        ids: tuple[int, ...] = ()
        offset = header
        while offset + 8 <= total:
            kind, header, size = struct.unpack_from("<HHI", data, offset)
            if header < 8 or size < header or offset + size > total:
                return nothing
            if kind == STRING_POOL and strings is None:
                strings = _Strings(data, offset, header, size)
            elif kind == RESOURCE_MAP:
                ids = struct.unpack_from(f"<{(size - header) // 4}I", data, offset + header)
            elif kind == START_ELEMENT:
                if strings is None:
                    return nothing
                return _manifest_element(data, offset, header, size, strings, ids)
            offset += size
    except (struct.error, ValueError, IndexError, UnicodeDecodeError):
        pass
    return nothing


def _manifest_element(data: bytes, offset: int, header: int, size: int, strings: _Strings,
                      ids: tuple[int, ...]) -> tuple[str | None, int | None, str | None]:
    _namespace, name, start, width, count = struct.unpack_from("<IIHHH", data, offset + header)
    first = offset + header + start
    if strings.get(name) != "manifest" or width < 20 or first + count * width > offset + size:
        return None, None, None
    words = {VERSION_CODE: "versionCode", VERSION_CODE_MAJOR: "versionCodeMajor",
             VERSION_NAME: "versionName"}
    found: dict[int | str, tuple[int, int, int]] = {}
    for index in range(count):
        namespace, name, raw, _size, _zero, value_type, value = struct.unpack_from(
            "<IIIHBBI", data, first + index * width)
        resource = ids[name] if name < len(ids) else None
        label = strings.get(name)
        if resource in words:
            found.setdefault(resource, (raw, value_type, value))
        elif resource is None and namespace != NO_INDEX \
                and strings.get(namespace) == ANDROID_NAMESPACE:
            for attribute, word in words.items():
                if label == word:
                    found.setdefault(attribute, (raw, value_type, value))
        elif namespace == NO_INDEX and label == "package":
            found.setdefault("package", (raw, value_type, value))

    def integer(attribute: int) -> int | None:
        _raw, value_type, value = found.get(attribute, (NO_INDEX, 0, 0))
        return value if TYPE_FIRST_INT <= value_type <= TYPE_LAST_INT else None

    def text(attribute: int | str) -> str | None:
        raw, value_type, value = found.get(attribute, (NO_INDEX, 0, 0))
        if raw != NO_INDEX:
            return strings.get(raw)
        return strings.get(value) if value_type == TYPE_STRING else None

    code, major = integer(VERSION_CODE), integer(VERSION_CODE_MAJOR)
    version_code = None if code is None else ((major or 0) << 32) | code
    return text("package"), version_code, text(VERSION_NAME)


def _prefixed(buffer: bytes) -> tuple[bytes, bytes]:
    """A length-prefixed field of the signing block, and what follows it."""
    if len(buffer) < 4:
        raise ValueError("truncated")
    length = struct.unpack_from("<I", buffer)[0]
    if 4 + length > len(buffer):
        raise ValueError("truncated")
    return buffer[4:4 + length], buffer[4 + length:]


def _signer(handle: Any, size: int) -> str | None:
    """SHA-256 of the first signer's certificate in the APK Signing Block (v3, else v2)."""
    try:
        tail = min(size, 22 + 0xFFFF)          # the end record and the longest zip comment
        handle.seek(size - tail)
        end = handle.read(tail)
        at = end.rfind(b"PK\x05\x06")
        if at < 0 or len(end) - at < 22:
            return None
        directory = struct.unpack_from("<I", end, at + 16)[0]
        if not 32 <= directory <= size:
            return None
        handle.seek(directory - 24)
        footer = handle.read(24)
        if len(footer) != 24 or footer[8:] != SIGNING_BLOCK_MAGIC:
            return None
        length = struct.unpack_from("<Q", footer)[0]
        if not 24 <= length <= min(directory - 8, SIGNING_BLOCK_LIMIT):
            return None
        handle.seek(directory - 8 - length)
        block = handle.read(length + 8)
        if len(block) != length + 8 or struct.unpack_from("<Q", block)[0] != length:
            return None
        schemes: dict[int, bytes] = {}
        at, stop = 8, len(block) - 24
        while at + 12 <= stop:
            pair, scheme = struct.unpack_from("<QI", block, at)
            if pair < 4 or at + 8 + pair > stop:
                return None
            schemes.setdefault(scheme, block[at + 12:at + 8 + pair])
            at += 8 + pair
        value = schemes.get(SIGNATURE_V3) or schemes.get(SIGNATURE_V2)
        if value is None:
            return None
        signers, _ = _prefixed(value)
        signer, _ = _prefixed(signers)
        signed, _ = _prefixed(signer)
        _digests, rest = _prefixed(signed)
        certificates, _ = _prefixed(rest)
        certificate, _ = _prefixed(certificates)
    except (OSError, struct.error, ValueError):
        return None
    return hashlib.sha256(certificate).hexdigest() if certificate else None


# ── the rule ───────────────────────────────────────────────────────────────────────────────────
def pin_version_code(url: object, package: str) -> int | None:
    """The version code the catalogue's pinned file name carries:
    <package>_<versionCode>[_<signer prefix>].apk, as the main repository names every APK."""
    if not isinstance(url, str) or not isinstance(package, str):
        return None
    name = urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]
    match = re.fullmatch(rf"{re.escape(package)}_([0-9]{{1,19}})(?:_[0-9a-f]{{7}})?\.apk", name)
    return int(match.group(1)) if match else None


def pin_is_update(*, pin_sha256: str, pin_code: int | None, pin_signer: object,
                  kept: ApkFacts | None, recorded_sha256: object) -> bool:
    """Whether installing the catalogue's pin updates the app Android keeps.

    `kept` is the APK Android keeps (kept()), None when it cannot be read; `recorded_sha256` the
    digest the Store's own record names, None when there is no such record.
    """
    pin_sha256 = pin_sha256.lower()
    if kept is not None:
        if kept.sha256 == pin_sha256:
            return False
        if kept.version_code is not None and pin_code is not None:
            signer = pin_signer.lower() if isinstance(pin_signer, str) else None
            if signer and kept.signer and kept.signer != signer:
                return False                    # Android takes an update only from the same key
            return kept.version_code < pin_code
    return isinstance(recorded_sha256, str) and recorded_sha256.lower() != pin_sha256
