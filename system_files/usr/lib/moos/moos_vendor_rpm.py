"""MoOS vendor RPM — run a publisher's own signed Linux package from the person's home.

Some publishers ship their Linux program ONLY as a signed package in their own repository; the
official ChatGPT desktop app is one. On MoOS the signed image is read-only and must keep following
its origin, so layering such a package is not how an application arrives. This module does what a
careful person would do by hand, with no administrator rights and without running ANYTHING from the
package (no scriptlet, no program):

  1. resolve   read the publisher's repository metadata over https and pick the newest build of
               exactly one package name for this machine's architecture;
  2. fetch     download it to disk with the size and SHA-256 the metadata promised;
  3. verify    prove with `rpmkeys` that it carries a valid signature by the ONE publisher key the
               catalogue names, and that this key is already in the image's trusted keyring;
  4. extract   unpack only the app's own folder (its `install_root`) into the home, refusing
               absolute or `..` names, devices, links that leave the folder and control characters,
               stripping setuid/setgid, within byte and entry budgets;
  5. integrate write a launcher of MoOS's own (never the package's) and a record.

Places (docs/MO_STORE.md, kind `vendor`; every path is recomputed from the app id, nothing a record
says is trusted as a path):

  ~/Applications/<id>/                                       the contents of install_root
  ~/Applications/<id>/.moos-vendor                           ownership marker, contains "<id>"
  ~/Applications/<id>/.moos-icon.png | .moos-icon.svg        the catalogue icon, when outside install_root
  ~/Applications/.<id>.vendor-staging | .vendor-previous     only while an install or update runs
  ~/.local/share/moos/vendor/<id>.json                       record (schema 1)
  ~/.local/share/applications/org.moos.vendor.<id>.desktop   launcher (X-MoOS-Vendor=<id>)
  ~/.cache/moos-store/downloads/vendor-<id>-*/               private work folder, always removed

A folder or launcher MoOS did not write — an App Drop app of the same name, a folder the person
made, a hand-written chatgpt.desktop — is never read, adopted or overwritten: MoOS's launcher has
its own file name, and remove() deletes only what carries MoOS's marker. The program's own data
(its settings and sign-in) is not MoOS's to delete.

CATALOGUE ENTRY (`install` of kind "vendor-rpm"), checked by parse_entry():

  repo             an exact https base with "$basearch", listed in TRUSTED_REPOSITORIES
  package          the package name
  key_fingerprint  the 40 hex digits TRUSTED_REPOSITORIES pins for that repo; the key must already
                   be in the image's RPM keyring
  install_root     absolute payload folder under /usr or /opt that IS the app, e.g. /usr/lib/chatgpt
  exec             program path relative to install_root, e.g. ChatGPT
  desktop          payload path of the publisher's .desktop file; only Name, Comment, Icon and
                   Categories are read from it (Icon only for information), each sanitised
  wm_class         StartupWMClass for MoOS's launcher
  icon?            payload path of a PNG or SVG icon
  schemes?         up to 4 URL schemes the launcher hands to the app (x-scheme-handler). The
                   catalogue names them, never the package; http, https, file, moos … are refused.

API for moos-storectl. Every failure is VendorError(code, detail): `code` is one of ERROR_CODES and
is stable (the Store owns the bilingual words for it), `detail` is for a log only.

  parse_entry(entry) -> Entry
  machine_arch() -> "x86_64" | "aarch64";  check_arch(arch) -> arch
  resolve(entry, arch, *, opener=None) -> dict
      {name, arch, epoch, version, release, evr, url, sha256, size, installed_size,
       archive_size, repo}
  fetch(info, directory, *, progress=None, cancelled=None, opener=None) -> Path
      progress(done_bytes, total_bytes); cancelled() -> bool is asked once per 1 MiB block
  key_installed(fingerprint, *, run=subprocess.run) -> bool
  verify_signature(rpm_path, fingerprint, *, run=subprocess.run) -> dict
      {fingerprint, algorithm, payload_digest}
  read_header(rpm_path, *, run=...) -> dict;  check_header(rpm_path, info, *, run=...) -> dict
  extract(rpm_path, install_root, target_dir, *, extras=(), work_dir=None, cancelled=None,
          progress=None, convert=None, seed=None) -> Extracted
      progress(percent); extras are payload paths captured in memory (≤ MAX_EXTRA_BYTES each);
      seed {name: bytes} is written into the new target BEFORE unpacking (the ownership marker)
  extract_cpio(cpio_path, install_root, target_dir, *, extras=(), compressed_size=0,
               cancelled=None, progress=None, seed=None) -> Extracted
  sandbox_report(tree, exec_rel, *, proc_sys=Path("/proc/sys")) -> dict
      {mode: namespace|setuid|off|unavailable|not-chromium, helper, setuid_files, chromium,
       switches, userns}
  desktop_fields(data, fallback_name) -> {name, comment, categories, icon_name}
  write_launcher(app_id, *, exec_path, name, comment="", icon="", categories="Utility;",
                 wm_class="", schemes=()) -> Path
  install(app_id, entry, *, arch=None, info=None, display_name="", progress=None,
          cancelled=None, opener=None, run=subprocess.run, convert=None,
          refresh_menu=True, proc_sys=Path("/proc/sys")) -> dict (the record)
      progress(stage, percent | None) with stage in STAGES; atomic: a failed update keeps the
      version that worked
  installed(app_id) -> dict | None
  intact(app_id) -> bool                        the record, MoOS's launcher and the marked folder
  update_available(app_id, newest) -> bool      newest: a resolve() result or "[E:]V-R"
  remove(app_id, *, refresh_menu=True) -> bool
  rpmvercmp(a, b) -> -1 | 0 | 1;  evr_compare(a, b) -> -1 | 0 | 1

INTEGRATION NOTES (moos-storectl, install.kind "vendor-rpm"):

  * install and update are one call, `install(app_id, recipe["install"], progress=…, cancelled=…)`,
    run inside the Store's job and under its global lock (two installs of one id must not overlap).
    Stage keys and error codes are stable; the job maps them to its own bilingual message keys.
  * check-updates: `info = resolve(entry, machine_arch())`, then `update_available(app_id, info)`;
    pass that `info` back to install() to resolve once (install() re-checks it against the entry).
  * remove: `remove(app_id)`. The program's own settings and sign-in are the person's: deleting
    them (`--delete-data`) is the Store's decision, not this module's.
  * index: `installed(app_id)["evr"]` is the installed version; `["desktop"]` the launcher's file.
  * the catalogue verifier should accept a vendor-rpm entry only when parse_entry() does, so the
    repository allowlist and its key pin live in exactly one place (TRUSTED_REPOSITORIES).
  * The ChatGPT entry, measured against the real package chatgpt-26.1007.71326-1 (x86_64 and
    aarch64 builds are both published):
        {"kind": "vendor-rpm",
         "repo": "https://persistent.oaistatic.com/codex-app-prod/linux/rpm/$basearch",
         "package": "chatgpt", "key_fingerprint": "3BFA0E4AE8B8CC16A2D9BA684A3B4A566C4660E4",
         "install_root": "/usr/lib/chatgpt", "exec": "ChatGPT",
         "icon": "/usr/share/pixmaps/chatgpt.png",
         "desktop": "/usr/share/applications/chatgpt.desktop", "wm_class": "ChatGPT",
         "schemes": ["codex"], "risk": "downloaded-executable", "requires_review": true,
         "external": true}
    Its own .desktop asks to handle codex: links — and http, https and office documents, which
    MoOS does not grant (only the catalogue's `schemes` reach the launcher). That build ships no
    chrome-sandbox: its Chromium runtime uses the user-namespace sandbox (sandbox_report()).

The whole chain is pure Python from the standard library plus three fixed tools from the image,
always called with an argument list and a clean environment, never through a shell: `rpmkeys`
(signature), `rpm -q`/`rpm -qp` (keyring and signed header, read-only) and `rpm2cpio` (payload).
tests/test_moos_vendor_rpm.py.
"""

from __future__ import annotations

import bz2
import contextlib
import dataclasses
import functools
import gzip
import hashlib
import http.client
import io
import json
import lzma
import os
from pathlib import Path
import platform
import posixpath
import re
import shutil
import ssl
import stat
import struct
import subprocess
import tempfile
import time
from typing import Any, Callable, Iterable, Mapping
import urllib.error
import urllib.parse
import urllib.request
import xml.parsers.expat

RPMKEYS = "/usr/bin/rpmkeys"
RPM = "/usr/bin/rpm"
RPM2CPIO = "/usr/bin/rpm2cpio"

SUPPORTED_ARCHES = ("x86_64", "aarch64")

# The exact repositories a catalogue entry may name, each bound to the ONE publisher key that may
# sign its packages (so no entry can pair a repository with another key the image happens to
# trust). A new vendor is reviewed here, and its key is imported into the image by build.sh.
TRUSTED_REPOSITORIES = {
    # The official ChatGPT desktop app ("Codex Linux Repository" key, imported by build.sh).
    "https://persistent.oaistatic.com/codex-app-prod/linux/rpm/$basearch": "3BFA0E4AE8B8CC16A2D9BA684A3B4A566C4660E4",
}

USER_AGENT = "MoOS-Store/1"
NETWORK_TIMEOUT = 30                      # seconds for a connect or one read
METADATA_DEADLINE = 120                   # seconds for one metadata document, start to end
MAX_REDIRECTS = 5
MAX_REPOMD_BYTES = 1024 ** 2
MAX_PRIMARY_BYTES = 64 * 1024 ** 2        # compressed
MAX_PRIMARY_OPEN_BYTES = 256 * 1024 ** 2  # decompressed
MAX_PACKAGE_BYTES = 4 * 1024 ** 3
MAX_TREE_BYTES = 16 * 1024 ** 3
MAX_TREE_FILES = 250_000                  # archive entries, inside and outside install_root
MAX_RATIO = 200                           # extracted / compressed: a bomb, not an app
RATIO_FLOOR = 64 * 1024 ** 2              # the ratio is judged only past this many bytes
MAX_EXTRA_BYTES = 8 * 1024 ** 2
MAX_NAME_BYTES = 4096
MAX_LINK_BYTES = 4095
TRAILER_SLACK = 1024 ** 2                 # zero padding a payload may carry after its trailer
CONVERT_TIMEOUT = 1800
TOOL_TIMEOUT = 600
SPACE_MARGIN = 256 * 1024 ** 2
BLOCK = 1024 * 1024
MARKER = ".moos-vendor"
ICON_STEM = ".moos-icon"

# Stage keys install() reports, in order. The Store owns the words.
STAGES = ("resolving", "downloading", "verifying", "extracting", "integrating")

ERROR_CODES = frozenset({
    "bad_entry",                 # the catalogue entry is malformed
    "bad_id",                    # the app id is not a slug
    "unsupported_arch",          # no build for this processor
    "network_error",             # connection, TLS or HTTP status failure
    "insecure_redirect",         # a redirect hop was not https
    "too_many_redirects",
    "metadata_too_large",        # repository metadata over its cap
    "metadata_invalid",          # malformed or unsafe XML, a weak or missing checksum, bad fields
    "metadata_digest_mismatch",  # the package list does not match the repository index
    "metadata_unsupported",      # compressed with something this Python cannot read
    "package_not_found",         # no package of that name for this architecture
    "foreign_host",              # the metadata points the download at another host
    "download_too_large",        # the body is larger than the metadata promised
    "download_incomplete",       # the body ended early
    "digest_mismatch",           # SHA-256 of the download differs from the metadata
    "no_space",
    "cancelled",
    "tool_missing",              # rpmkeys, rpm or rpm2cpio is absent
    "key_not_installed",         # the publisher key is not in the image's keyring
    "signature_untrusted_key",   # rpmkeys: NOKEY / NOTTRUSTED
    "signature_invalid",         # rpmkeys: BAD / NOT OK / any check that did not pass
    "signature_missing",         # no publisher signature at all
    "signature_wrong_key",       # signed, but not provably by the catalogue's key
    "signature_weak",            # signed by that key with a weak algorithm only
    "payload_unverified",        # no payload digest was checked against the signed header
    "header_mismatch",           # the signed header names another package or version
    "extract_failed",            # rpm2cpio failed, timed out or produced nothing
    "archive_invalid",           # malformed payload: magic, truncation, trailer, junk after it
    "unsupported_archive",       # the payload format for files over 4 GiB, or not cpio at all
    "unsafe_archive",            # absolute or '..' names, devices, escaping links, control chars
    "archive_bomb",              # byte, entry or ratio budget exceeded
    "install_root_missing",      # nothing under install_root in the payload
    "nothing_to_launch",         # exec is missing, not a program, or outside the app folder
    "sandbox_unavailable",       # a Chromium program that could not start its sandbox here
    "name_taken",                # a launcher or folder MoOS did not write is in the way
    "unsafe_path",               # the home path cannot be written into a launcher safely
})

MAIN_CATEGORIES = {"AudioVideo", "Audio", "Video", "Development", "Education", "Game", "Graphics",
                   "Network", "Office", "Science", "Settings", "System", "Utility"}
RESERVED_SCHEMES = frozenset({
    "http", "https", "file", "ftp", "ftps", "sftp", "ssh", "smb", "nfs", "data", "javascript",
    "about", "blob", "mailto", "tel", "sms", "moos", "appstream", "trash", "desktop", "applications",
    "settings", "kcm", "help", "man", "info",
})

_RPM_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}")
_FINGERPRINT = re.compile(r"[0-9A-Fa-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_APP_ID = re.compile(r"[a-z0-9][a-z0-9-]{1,62}")
_EPOCH = re.compile(r"[0-9]{1,10}")
_EVR_PART = re.compile(r"[A-Za-z0-9._+~^]{1,128}")
_WM_CLASS = re.compile(r"[A-Za-z0-9._ -]{1,80}")
_SCHEME = re.compile(r"[a-z][a-z0-9+.-]{1,31}")
_CATEGORIES = re.compile(r"(?:[A-Za-z]+;)+")
_CONTROL = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029]")
_BIDI = re.compile("[\u200e\u200f\u202a-\u202e\u2066-\u2069]")
_EXEC_UNSAFE = re.compile(r'["`$\\]')


class VendorError(Exception):
    """Refused or failed. `code` is a stable key the Store owns the words for; `detail` is for a log."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


# ── places ───────────────────────────────────────────────────────────────────
def home() -> Path:
    return Path(os.environ.get("HOME") or Path.home())


def data_home() -> Path:
    configured = os.environ.get("XDG_DATA_HOME")
    return Path(configured) if configured and Path(configured).is_absolute() else home() / ".local/share"


def cache_home() -> Path:
    configured = os.environ.get("XDG_CACHE_HOME")
    return Path(configured) if configured and Path(configured).is_absolute() else home() / ".cache"


def applications_dir() -> Path:
    return home() / "Applications"


def vendor_root() -> Path:
    """Where the records live (the apps themselves live in ~/Applications)."""
    return data_home() / "moos/vendor"


def downloads_dir() -> Path:
    # On disk, never in the RAM-backed /tmp: a package and its payload are gigabytes.
    return cache_home() / "moos-store/downloads"


def desktop_dir() -> Path:
    return data_home() / "applications"


def check_id(app_id: str) -> str:
    if not isinstance(app_id, str) or not _APP_ID.fullmatch(app_id):
        raise VendorError("bad_id", repr(app_id)[:80])
    return app_id


def app_dir(app_id: str) -> Path:
    return applications_dir() / check_id(app_id)


def staging_dir(app_id: str) -> Path:
    return applications_dir() / f".{check_id(app_id)}.vendor-staging"


def previous_dir(app_id: str) -> Path:
    return applications_dir() / f".{check_id(app_id)}.vendor-previous"


def record_path(app_id: str) -> Path:
    return vendor_root() / f"{check_id(app_id)}.json"


def launcher_name(app_id: str) -> str:
    return f"org.moos.vendor.{check_id(app_id)}.desktop"


def launcher_path(app_id: str) -> Path:
    return desktop_dir() / launcher_name(app_id)


# ── the catalogue entry ──────────────────────────────────────────────────────
@dataclasses.dataclass(frozen=True)
class Entry:
    repo: str
    package: str
    key_fingerprint: str
    install_root: str
    exec: str
    desktop: str
    wm_class: str
    icon: str = ""
    schemes: tuple[str, ...] = ()

    def repo_url(self, arch: str) -> str:
        return self.repo.replace("$basearch", check_arch(arch)).rstrip("/")


def machine_arch() -> str:
    machine = platform.machine().lower()
    arch = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}.get(machine)
    if arch is None:
        raise VendorError("unsupported_arch", machine)
    return arch


def check_arch(arch: str) -> str:
    if arch not in SUPPORTED_ARCHES:
        raise VendorError("unsupported_arch", repr(arch)[:40])
    return arch


def _payload_path(value: Any, field: str, code: str = "bad_entry") -> str:
    """An absolute, already-normal path inside the package: no `..`, no `//`, no trailing slash."""
    if (not isinstance(value, str) or not value.startswith("/") or value.startswith("//")
            or len(value) > 1024 or _CONTROL.search(value) or "\\" in value
            or value == "/" or posixpath.normpath(value) != value):
        raise VendorError(code, f"{field} must be a normal absolute path: {value!r}"[:200])
    return value


def _relative_path(value: Any, field: str) -> str:
    if (not isinstance(value, str) or not value or value.startswith("/") or len(value) > 255
            or _CONTROL.search(value) or "\\" in value or ".." in value.split("/")
            or value == "." or posixpath.normpath(value) != value):
        raise VendorError("bad_entry", f"{field} must be a normal relative path: {value!r}"[:200])
    return value


def _check_https_url(url: str, code: str, *, fragment: bool = False) -> urllib.parse.SplitResult:
    if not isinstance(url, str) or len(url) > 2048 or _CONTROL.search(url) or " " in url or "\\" in url:
        raise VendorError(code, repr(url)[:200])
    try:
        parts = urllib.parse.urlsplit(url)
        parts.port  # noqa: B018 - a malformed port raises here
    except ValueError as error:
        raise VendorError(code, str(error)) from None
    if (parts.scheme != "https" or not parts.hostname or parts.username is not None
            or parts.password is not None or (parts.fragment and not fragment)):
        raise VendorError(code, url[:200])
    return parts


def parse_entry(entry: Mapping[str, Any]) -> Entry:
    """The catalogue's word for one vendor package, checked field by field (an Entry too: anyone can
    construct one, so it is checked again rather than trusted)."""
    if isinstance(entry, Entry):
        entry = {**dataclasses.asdict(entry), "schemes": list(entry.schemes)}
    if not isinstance(entry, Mapping):
        raise VendorError("bad_entry", "the entry is not an object")
    repo = entry.get("repo")
    if not isinstance(repo, str) or repo.count("$basearch") != 1 or "$" in repo.replace("$basearch", ""):
        raise VendorError("bad_entry", "repo must contain $basearch exactly once")
    parts = _check_https_url(repo.replace("$basearch", "x86_64"), "bad_entry")
    if parts.query or ".." in parts.path.split("/"):
        raise VendorError("bad_entry", "repo must be a plain https folder")
    package = entry.get("package")
    if not isinstance(package, str) or not _RPM_NAME.fullmatch(package):
        raise VendorError("bad_entry", "package")
    fingerprint = entry.get("key_fingerprint")
    if not isinstance(fingerprint, str) or not _FINGERPRINT.fullmatch(fingerprint):
        raise VendorError("bad_entry", "key_fingerprint must be 40 hexadecimal digits")
    pinned = TRUSTED_REPOSITORIES.get(repo)
    if pinned is None:
        raise VendorError("bad_entry", f"repo is not a reviewed vendor repository: {repo}"[:200])
    if pinned.lower() != fingerprint.lower():
        raise VendorError("bad_entry", "key_fingerprint is not the key pinned for this repository")
    install_root = _payload_path(entry.get("install_root"), "install_root")
    levels = install_root.split("/")[1:]
    # The app's OWN folder: /usr/<lib|share|…>/<app> or /opt/<app>, never a shared system folder.
    if not ((levels[0] == "usr" and len(levels) >= 3) or (levels[0] == "opt" and len(levels) >= 2)):
        raise VendorError("bad_entry", "install_root must be the app's own folder under /usr or /opt")
    exec_rel = _relative_path(entry.get("exec"), "exec")
    desktop = _payload_path(entry.get("desktop"), "desktop")
    if not desktop.endswith(".desktop"):
        raise VendorError("bad_entry", "desktop must name a .desktop file")
    icon = entry.get("icon") or ""
    if icon:
        icon = _payload_path(icon, "icon")
        if not icon.endswith((".png", ".svg")):
            raise VendorError("bad_entry", "icon must be a PNG or SVG file")
    wm_class = entry.get("wm_class")
    if not isinstance(wm_class, str) or not _WM_CLASS.fullmatch(wm_class):
        raise VendorError("bad_entry", "wm_class")
    schemes = entry.get("schemes") or []
    if not isinstance(schemes, (list, tuple)) or len(schemes) > 4:
        raise VendorError("bad_entry", "schemes")
    for scheme in schemes:
        if not isinstance(scheme, str) or not _SCHEME.fullmatch(scheme) or scheme in RESERVED_SCHEMES:
            raise VendorError("bad_entry", f"scheme {scheme!r}"[:80])
    return Entry(repo=repo, package=package, key_fingerprint=fingerprint.lower(),
                 install_root=install_root, exec=exec_rel, desktop=desktop, wm_class=wm_class,
                 icon=icon, schemes=tuple(dict.fromkeys(schemes)))


# ── version order, exactly as rpm compares ───────────────────────────────────
def _digit(char: str) -> bool:
    return "0" <= char <= "9"


def _alpha(char: str) -> bool:
    return "a" <= char <= "z" or "A" <= char <= "Z"


def rpmvercmp(a: str, b: str) -> int:
    """rpm's rpmvercmp(), segment for segment: ASCII letters and digits only, `~` sorts before
    everything (even the end of the string), `^` after the end of the string but before any other
    segment, leading zeros do not count, a number beats letters. The odd cases are odd in rpm too."""
    if a == b:
        return 0
    i = j = 0
    len_a, len_b = len(a), len(b)
    while i < len_a or j < len_b:
        while i < len_a and not (_digit(a[i]) or _alpha(a[i])) and a[i] not in "~^":
            i += 1
        while j < len_b and not (_digit(b[j]) or _alpha(b[j])) and b[j] not in "~^":
            j += 1
        char_a = a[i] if i < len_a else ""
        char_b = b[j] if j < len_b else ""
        if char_a == "~" or char_b == "~":
            if char_a != "~":
                return 1
            if char_b != "~":
                return -1
            i += 1
            j += 1
            continue
        if char_a == "^" or char_b == "^":
            if not char_a:
                return -1
            if not char_b:
                return 1
            if char_a != "^":
                return 1
            if char_b != "^":
                return -1
            i += 1
            j += 1
            continue
        if not (char_a and char_b):
            break
        start_a, start_b = i, j
        if _digit(char_a):
            while i < len_a and _digit(a[i]):
                i += 1
            while j < len_b and _digit(b[j]):
                j += 1
            numeric = True
        else:
            while i < len_a and _alpha(a[i]):
                i += 1
            while j < len_b and _alpha(b[j]):
                j += 1
            numeric = False
        segment_a, segment_b = a[start_a:i], b[start_b:j]
        if not segment_b:
            return 1 if numeric else -1
        if numeric:
            segment_a, segment_b = segment_a.lstrip("0"), segment_b.lstrip("0")
            if len(segment_a) != len(segment_b):
                return 1 if len(segment_a) > len(segment_b) else -1
        if segment_a != segment_b:
            return 1 if segment_a > segment_b else -1
    if i >= len_a and j >= len_b:
        return 0
    return -1 if i >= len_a else 1


def _evr(value: Any) -> tuple[int, str, str]:
    if isinstance(value, Mapping):
        epoch, version, release = value.get("epoch", 0), value.get("version"), value.get("release", "")
    elif isinstance(value, (tuple, list)) and len(value) == 3:
        epoch, version, release = value
    elif isinstance(value, str):
        text = value.strip()
        epoch, colon, rest = text.partition(":")
        if not colon:
            epoch, rest = "0", text
        version, dash, release = rest.rpartition("-")
        if not dash:
            version, release = rest, ""
    else:
        raise VendorError("bad_entry", "not a version")
    epoch_text = str(epoch if epoch not in (None, "") else 0)
    if not _EPOCH.fullmatch(epoch_text) or not isinstance(version, str) or not _EVR_PART.fullmatch(version) \
            or not isinstance(release, str) or (release and not _EVR_PART.fullmatch(release)):
        raise VendorError("bad_entry", f"not a version: {value!r}"[:120])
    return int(epoch_text), version, release


def evr_compare(a: Any, b: Any) -> int:
    """Package order: epoch as a number, then version, then release, each with rpmvercmp()."""
    (epoch_a, version_a, release_a), (epoch_b, version_b, release_b) = _evr(a), _evr(b)
    if epoch_a != epoch_b:
        return 1 if epoch_a > epoch_b else -1
    return rpmvercmp(version_a, version_b) or rpmvercmp(release_a, release_b)


def evr_text(epoch: int, version: str, release: str) -> str:
    return f"{epoch}:{version}-{release}" if epoch else f"{version}-{release}"


# ── https only, with a cap on everything ─────────────────────────────────────
class _HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
    """Every redirect hop must stay on https; the response that asked for another one is closed.

    The hop is judged twice: from the raw Location header (before urllib's own scheme filter, which
    would report an `ftp:` or `file:` hop as a generic HTTP error) and again as the request urllib
    is about to send."""

    max_redirections = MAX_REDIRECTS

    @staticmethod
    def _judge(fp: Any, newurl: str) -> None:
        try:
            _check_https_url(newurl, "insecure_redirect", fragment=True)
        except VendorError:
            with contextlib.suppress(Exception):
                fp.close()
            raise

    def http_error_302(self, req, fp, code, msg, headers):  # noqa: N802 - urllib's name
        location = headers.get("location") or headers.get("uri")
        if location:
            self._judge(fp, urllib.parse.urljoin(req.full_url, location.strip()))
        return super().http_error_302(req, fp, code, msg, headers)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802 - urllib's name
        self._judge(fp, newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def https_opener() -> urllib.request.OpenerDirector:
    """An opener that can only speak https: no http, ftp or file handler is installed at all."""
    opener = urllib.request.OpenerDirector()
    for handler in (urllib.request.ProxyHandler(),
                    urllib.request.HTTPSHandler(context=ssl.create_default_context()),
                    urllib.request.HTTPDefaultErrorHandler(), _HttpsOnlyRedirect(),
                    urllib.request.HTTPErrorProcessor(), urllib.request.UnknownHandler()):
        opener.add_handler(handler)
    return opener


def _open(url: str, opener: Any):
    _check_https_url(url, "network_error")
    request = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
    try:
        response = (opener or https_opener()).open(request, timeout=NETWORK_TIMEOUT)
    except VendorError:
        raise
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        if 300 <= status < 400:
            raise VendorError("too_many_redirects", f"HTTP {status} {url}"[:200]) from None
        raise VendorError("network_error", f"HTTP {status} {url}"[:200]) from None
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as error:
        raise VendorError("network_error", f"{url}: {error}"[:300]) from None
    if response is None:
        raise VendorError("network_error", url[:200])
    final = response.geturl() if hasattr(response, "geturl") else url
    status = getattr(response, "status", 200)
    try:
        _check_https_url(final, "insecure_redirect", fragment=True)
        if status != 200:
            raise VendorError("network_error", f"HTTP {status} {url}"[:200])
    except VendorError:
        response.close()
        raise
    return response


def _read_capped(response: Any, cap: int, too_large: str, *, sink: Callable[[bytes], Any] | None = None,
                 hasher: Any = None, cancelled: Callable[[], bool] | None = None,
                 progress: Callable[[int], None] | None = None, deadline: float | None = None) -> int:
    headers = getattr(response, "headers", None)
    length = headers.get("Content-Length") if headers is not None else None
    if length and length.strip().isdigit() and int(length) > cap:
        raise VendorError(too_large, f"{length} bytes announced, {cap} allowed")
    total = 0
    while True:
        if cancelled is not None and cancelled():
            raise VendorError("cancelled")
        if deadline is not None and time.monotonic() > deadline:
            raise VendorError("network_error", "the transfer took too long")
        try:
            block = response.read(BLOCK)
        except (OSError, http.client.HTTPException, ValueError) as error:
            raise VendorError("network_error", str(error)[:300]) from None
        if not block:
            return total
        total += len(block)
        if total > cap:
            raise VendorError(too_large, f"more than {cap} bytes")
        if sink is not None:
            sink(block)
        if hasher is not None:
            hasher.update(block)
        if progress is not None:
            progress(total)


def _document(url: str, cap: int, opener: Any) -> bytes:
    chunks: list[bytes] = []
    response = _open(url, opener)
    with contextlib.closing(response):
        _read_capped(response, cap, "metadata_too_large", sink=chunks.append,
                     deadline=time.monotonic() + METADATA_DEADLINE)
    return b"".join(chunks)


def _same_host_url(base: str, href: str, xml_base: str | None) -> str:
    """Where the metadata points, resolved — and refused unless it is https on the repository's host."""
    if not isinstance(href, str) or not href or len(href) > 2048 or _CONTROL.search(href) or "\\" in href:
        raise VendorError("metadata_invalid", f"location {href!r}"[:200])
    root = base + "/"
    if xml_base:
        _check_https_url(xml_base, "foreign_host")
        root = xml_base if xml_base.endswith("/") else xml_base + "/"
    url = urllib.parse.urljoin(root, href)
    expected = urllib.parse.urlsplit(base)
    try:
        parts = urllib.parse.urlsplit(url)
        same = (parts.scheme == "https" and parts.hostname is not None
                and parts.hostname.lower() == (expected.hostname or "").lower()
                and parts.port == expected.port and parts.username is None and parts.password is None)
    except ValueError:
        same = False
    if not same:
        raise VendorError("foreign_host", url[:200])
    if parts.query or parts.fragment:
        raise VendorError("metadata_invalid", url[:200])
    return url


# ── repository metadata ──────────────────────────────────────────────────────
_NS_REPO = "http://linux.duke.edu/metadata/repo"
_NS_COMMON = "http://linux.duke.edu/metadata/common"
_XML_BASE = "http://www.w3.org/XML/1998/namespace base"
_DIGESTS = {"sha256": 64, "sha512": 128}
_MAX_TEXT = 4096


def _split(name: str) -> tuple[str, str]:
    uri, _, local = name.rpartition(" ")
    return uri, local


def _parser(start: Callable, end: Callable, text: Callable):
    """expat with every way to declare or fetch an entity refused: no DOCTYPE, no ENTITY, ever."""
    parser = xml.parsers.expat.ParserCreate(namespace_separator=" ")
    parser.buffer_text = True
    parser.SetParamEntityParsing(xml.parsers.expat.XML_PARAM_ENTITY_PARSING_NEVER)

    def refuse(*_args: Any) -> None:
        raise VendorError("metadata_invalid", "document type and entity declarations are refused")

    parser.StartDoctypeDeclHandler = refuse
    parser.EntityDeclHandler = refuse
    parser.UnparsedEntityDeclHandler = refuse
    parser.ExternalEntityRefHandler = refuse
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = text
    return parser


class _Fields:
    """Collects the text of selected children of one element, bounded."""

    def __init__(self) -> None:
        self.field: str | None = None
        self.parts: list[str] = []
        self.size = 0

    def begin(self, field: str) -> None:
        self.field, self.parts, self.size = field, [], 0

    def text(self, data: str) -> None:
        if self.field is not None:
            self.size += len(data)
            if self.size > _MAX_TEXT:
                raise VendorError("metadata_invalid", f"<{self.field}> is too long")
            self.parts.append(data)

    def finish(self) -> str:
        value = "".join(self.parts).strip()
        self.field = None
        return value


def _feed(parser: Any, data: bytes, final: bool) -> None:
    try:
        parser.Parse(data, final)
    except xml.parsers.expat.ExpatError as error:
        raise VendorError("metadata_invalid", str(error)) from None


def _digest_spec(kind: str, value: str, what: str) -> tuple[str, str]:
    kind = (kind or "").lower()
    value = (value or "").lower()
    if kind not in _DIGESTS:
        raise VendorError("metadata_invalid", f"{what} has a weak or unknown checksum: {kind!r}"[:120])
    if not re.fullmatch(f"[0-9a-f]{{{_DIGESTS[kind]}}}", value):
        raise VendorError("metadata_invalid", f"{what} checksum is malformed")
    return kind, value


def _parse_repomd(data: bytes) -> dict[str, Any]:
    stack: list[tuple[str, str]] = []
    collected: list[dict[str, Any]] = []
    fields = _Fields()
    current: dict[str, Any] | None = None

    def start(name: str, attrs: dict[str, str]) -> None:
        nonlocal current
        uri, local = _split(name)
        depth = len(stack)
        stack.append((uri, local))
        if depth == 0 and (uri, local) != (_NS_REPO, "repomd"):
            raise VendorError("metadata_invalid", "not a repository index")
        if depth == 1 and (uri, local) == (_NS_REPO, "data"):
            current = {"type": attrs.get("type", "")}
            collected.append(current)
        elif depth == 2 and current is not None and uri == _NS_REPO:
            if local in ("checksum", "open-checksum"):
                current[f"{local}-type"] = attrs.get("type", "")
                fields.begin(local)
            elif local in ("size", "open-size"):
                fields.begin(local)
            elif local == "location":
                current["href"] = attrs.get("href", "")
                current["xml_base"] = attrs.get(_XML_BASE)

    def end(_name: str) -> None:
        nonlocal current
        depth = len(stack) - 1
        _uri, local = stack.pop()
        if depth == 2 and current is not None and fields.field == local:
            current[local] = fields.finish()
        elif depth == 1:
            current = None

    parser = _parser(start, end, fields.text)
    _feed(parser, data, True)
    primary = [entry for entry in collected if entry.get("type") == "primary"]
    if len(primary) != 1:
        raise VendorError("metadata_invalid", "the index must name exactly one package list")
    entry = primary[0]
    result: dict[str, Any] = {"href": entry.get("href", ""), "xml_base": entry.get("xml_base")}
    result["checksum"] = _digest_spec(entry.get("checksum-type", ""), entry.get("checksum", ""), "the package list")
    if entry.get("open-checksum"):
        result["open_checksum"] = _digest_spec(entry.get("open-checksum-type", ""), entry["open-checksum"],
                                               "the package list")
    for key in ("size", "open-size"):
        value = entry.get(key)
        if value:
            if not value.isdigit():
                raise VendorError("metadata_invalid", f"{key} is not a number")
            result[key.replace("-", "_")] = int(value)
    return result


def _decompressor(blob: bytes) -> io.BufferedIOBase:
    """What the bytes ARE decides how they are read, not what the file is called."""
    if blob[:2] == b"\x1f\x8b":
        return gzip.GzipFile(fileobj=io.BytesIO(blob))
    if blob[:6] == b"\xfd7zXZ\x00":
        return lzma.LZMAFile(io.BytesIO(blob))
    if blob[:3] == b"BZh":
        return bz2.BZ2File(io.BytesIO(blob))
    if blob[:4] == b"\x28\xb5\x2f\xfd":
        try:
            from compression import zstd  # type: ignore[import-not-found]  # Python 3.14+
        except ImportError:
            raise VendorError("metadata_unsupported", "zstd needs Python 3.14") from None
        return zstd.ZstdFile(io.BytesIO(blob))
    if blob.lstrip()[:1] == b"<":
        return io.BytesIO(blob)  # type: ignore[return-value]
    raise VendorError("metadata_invalid", "the package list is in an unknown format")


class _Primary:
    """Streams primary.xml and keeps only the packages named `name` for `arch`."""

    def __init__(self, name: str, arch: str) -> None:
        self.name, self.arch = name, arch
        self.stack: list[tuple[str, str]] = []
        self.fields = _Fields()
        self.package: dict[str, Any] | None = None
        self.matches: list[dict[str, Any]] = []

    def start(self, name: str, attrs: dict[str, str]) -> None:
        uri, local = _split(name)
        depth = len(self.stack)
        self.stack.append((uri, local))
        if depth == 0 and (uri, local) != (_NS_COMMON, "metadata"):
            raise VendorError("metadata_invalid", "not a package list")
        if depth == 1 and (uri, local) == (_NS_COMMON, "package"):
            self.package = {"type": attrs.get("type", "")}
        elif depth == 2 and self.package is not None and uri == _NS_COMMON:
            package = self.package
            if local in ("name", "arch", "checksum"):
                if local == "checksum":
                    package["checksum_type"] = attrs.get("type", "")
                self.fields.begin(local)
            elif local == "version":
                package.update(epoch=attrs.get("epoch", "0"), version=attrs.get("ver"), release=attrs.get("rel"))
            elif local == "size":
                package.update(size=attrs.get("package"), installed_size=attrs.get("installed"),
                               archive_size=attrs.get("archive"))
            elif local == "location":
                package.update(href=attrs.get("href"), xml_base=attrs.get(_XML_BASE))

    def end(self, _name: str) -> None:
        depth = len(self.stack) - 1
        _uri, local = self.stack.pop()
        if depth == 2 and self.package is not None and self.fields.field == local:
            self.package[local] = self.fields.finish()
        elif depth == 1 and self.package is not None:
            package, self.package = self.package, None
            if package.get("type") == "rpm" and package.get("name") == self.name \
                    and package.get("arch") == self.arch:
                self.matches.append(package)


def _number(value: Any, what: str, *, required: bool) -> int:
    if value in (None, "") and not required:
        return 0
    if not isinstance(value, str) or not value.isdigit() or len(value) > 15:
        raise VendorError("metadata_invalid", f"{what} is not a number")
    return int(value)


def _candidate(package: dict[str, Any], base: str) -> dict[str, Any]:
    epoch, version, release = _evr((package.get("epoch") or "0", package.get("version"), package.get("release")))
    if not release:
        raise VendorError("metadata_invalid", "a package has no release")
    if package.get("checksum_type") != "sha256" or not _SHA256.fullmatch(package.get("checksum", "")):
        raise VendorError("metadata_invalid", "a package is not pinned to SHA-256")
    size = _number(package.get("size"), "package size", required=True)
    if size == 0:
        raise VendorError("metadata_invalid", "a package has no size")
    if size > MAX_PACKAGE_BYTES:
        raise VendorError("download_too_large", f"{size} bytes")
    url = _same_host_url(base, package.get("href") or "", package.get("xml_base"))
    return {"name": package["name"], "arch": package["arch"], "epoch": epoch, "version": version,
            "release": release, "evr": evr_text(epoch, version, release), "url": url,
            "sha256": package["checksum"], "size": size,
            "installed_size": _number(package.get("installed_size"), "installed size", required=False),
            "archive_size": _number(package.get("archive_size"), "archive size", required=False),
            "repo": base}


def resolve(entry: Mapping[str, Any] | Entry, arch: str, *, opener: Any = None) -> dict[str, Any]:
    """The newest build of exactly `package` for `arch`, from the publisher's own metadata."""
    spec = parse_entry(entry)
    base = spec.repo_url(arch)
    index = _parse_repomd(_document(base + "/repodata/repomd.xml", MAX_REPOMD_BYTES, opener))
    list_url = _same_host_url(base, index["href"], index.get("xml_base"))
    cap = min(MAX_PRIMARY_BYTES, index.get("size") or MAX_PRIMARY_BYTES)
    blob = _document(list_url, cap, opener)
    if "size" in index and len(blob) != index["size"]:
        raise VendorError("metadata_digest_mismatch", "the package list has the wrong size")
    kind, digest = index["checksum"]
    if hashlib.new(kind, blob).hexdigest() != digest:
        raise VendorError("metadata_digest_mismatch", "the package list does not match the index")
    collector = _Primary(spec.package, arch)
    parser = _parser(collector.start, collector.end, collector.fields.text)
    open_kind, open_digest = index.get("open_checksum", ("sha256", ""))
    open_hash = hashlib.new(open_kind)
    open_cap = min(MAX_PRIMARY_OPEN_BYTES, index.get("open_size") or MAX_PRIMARY_OPEN_BYTES)
    total = 0
    try:
        with _decompressor(blob) as stream:
            while True:
                chunk = stream.read(BLOCK)
                if not chunk:
                    break
                total += len(chunk)
                if total > open_cap:
                    raise VendorError("metadata_too_large", "the package list expands too far")
                open_hash.update(chunk)
                _feed(parser, chunk, False)
    except VendorError:
        raise
    except Exception as error:  # gzip/lzma/bz2/zstd each name their corruption differently
        raise VendorError("metadata_invalid", f"the package list cannot be read: {error}"[:200]) from None
    _feed(parser, b"", True)
    if open_digest and open_hash.hexdigest() != open_digest:
        raise VendorError("metadata_digest_mismatch", "the package list does not match the index")
    if not collector.matches:
        raise VendorError("package_not_found", f"{spec.package} for {arch}")
    candidates = [_candidate(package, base) for package in collector.matches]
    return max(candidates, key=functools.cmp_to_key(evr_compare))


# ── download ─────────────────────────────────────────────────────────────────
def _download_fields(info: Mapping[str, Any]) -> tuple[str, str, int]:
    url, digest, size = info.get("url"), info.get("sha256"), info.get("size")
    _check_https_url(url, "bad_entry")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise VendorError("bad_entry", "sha256")
    if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_PACKAGE_BYTES:
        raise VendorError("bad_entry", "size")
    return url, digest, size


def _package_file_name(info: Mapping[str, Any]) -> str:
    name = f"{info.get('name')}-{info.get('version')}-{info.get('release')}.{info.get('arch')}.rpm"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+~^-]{0,250}", name):
        return "package.rpm"
    return name


def _existing(path: Path) -> Path:
    probe = Path(path)
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return probe


def _require_space(needs: Mapping[Path, int]) -> None:
    devices: dict[int, list[int]] = {}
    for path, need in needs.items():
        probe = _existing(path)
        info = os.statvfs(probe)
        slot = devices.setdefault(os.stat(probe).st_dev, [info.f_bavail * info.f_frsize, 0])
        slot[1] += max(int(need), 0)
    for free, need in devices.values():
        if need + SPACE_MARGIN > free:
            raise VendorError("no_space", f"{need} bytes needed, {free} free")


def _unlink_quietly(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)


def fetch(info: Mapping[str, Any], directory: str | os.PathLike[str], *,
          progress: Callable[[int, int], None] | None = None,
          cancelled: Callable[[], bool] | None = None, opener: Any = None) -> Path:
    """Download the resolved package into `directory`: exactly `size` bytes with that SHA-256."""
    url, digest, size = _download_fields(info)
    folder = Path(directory)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if folder.is_symlink() or not folder.is_dir():
        raise VendorError("unsafe_path", str(folder))
    _require_space({folder: size})
    final = folder / _package_file_name(info)
    partial = folder / f".{final.name}.part"
    _unlink_quietly(partial)
    hasher = hashlib.sha256()
    descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as sink:
            response = _open(url, opener)
            with contextlib.closing(response):
                total = _read_capped(response, size, "download_too_large", sink=sink.write, hasher=hasher,
                                     cancelled=cancelled,
                                     progress=(lambda done: progress(done, size)) if progress else None)
            sink.flush()
            os.fsync(sink.fileno())
        if total < size:
            raise VendorError("download_incomplete", f"{total} of {size} bytes")
        if hasher.hexdigest() != digest:
            raise VendorError("digest_mismatch", f"{hasher.hexdigest()} != {digest}")
        os.replace(partial, final)
        return final
    except BaseException:
        _unlink_quietly(partial)
        raise


# ── the publisher's signature, by the image's own tools ──────────────────────
def _tool_env() -> dict[str, str]:
    # A clean C environment: stable output to parse, and no ~/.rpmmacros to redefine the keyring.
    return {"LC_ALL": "C", "LANG": "C", "PATH": "/usr/bin:/bin", "HOME": "/nonexistent"}


def _tool(run: Callable[..., Any], argv: list[str], *, timeout: int, failure: str) -> tuple[int, str, str]:
    try:
        done = run(argv, stdin=subprocess.DEVNULL, capture_output=True, env=_tool_env(),
                   timeout=timeout, check=False)
    except FileNotFoundError as error:
        raise VendorError("tool_missing", argv[0]) from error
    except subprocess.TimeoutExpired as error:
        raise VendorError(failure, f"{posixpath.basename(argv[0])} timed out") from error

    def text(value: Any) -> str:
        return value.decode("utf-8", "replace") if isinstance(value, bytes) else (value or "")

    return done.returncode, text(done.stdout), text(done.stderr)


def _fingerprint(value: str) -> str:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
        raise VendorError("bad_entry", "key_fingerprint must be 40 hexadecimal digits")
    return value.lower()


def key_installed(fingerprint: str, *, run: Callable[..., Any] = subprocess.run) -> bool:
    """Is the publisher key in the image's keyring? Read-only `rpm -q gpg-pubkey`.

    rpm 6 names each key by its full fingerprint; older rpm by the last 8 hex digits."""
    expected = _fingerprint(fingerprint)
    _status, output, _errors = _tool(
        run, [RPM, "-q", "gpg-pubkey", "--qf", "%{name}-%{version}-%{release} %{packager}\\n"],
        timeout=60, failure="key_not_installed")
    for line in output.splitlines():
        match = re.match(r"gpg-pubkey-([0-9A-Fa-f]+)-([0-9A-Fa-f]+)(?:\s|$)", line.strip())
        if match:
            version = match.group(1).lower()
            if version == expected or (len(version) == 8 and version == expected[-8:]):
                return True
    return False


_SIGNATURE = re.compile(
    r"(?:(?:Header|Package|Legacy)\s+)?(?:OpenPGP\s+)?(?:V(?P<version>\d)\s+)?"
    r"(?P<pubkey>[A-Za-z0-9]+)/(?P<hash>[A-Za-z0-9-]+)\s+signature,\s+key\s+"
    r"(?:fingerprint:\s+(?P<fingerprint>[0-9A-Fa-f]+)|ID\s+(?P<keyid>[0-9A-Fa-f]+))", re.IGNORECASE)
_PAYLOAD_DIGEST = re.compile(r"Payload\s+(?P<hash>SHA256|SHA384|SHA512|SHA3-256|SHA3-512)(?:\s+ALT)?\s+digest",
                             re.IGNORECASE)
STRONG_HASHES = frozenset({"SHA256", "SHA384", "SHA512", "SHA3-256", "SHA3-512"})
STRONG_PUBKEYS = frozenset({"RSA", "ECDSA", "EDDSA", "ED25519", "ED448"})


def parse_checksig(returncode: int, output: str, fingerprint: str, path: str | os.PathLike[str] | None = None
                   ) -> dict[str, str]:
    """Judge `rpmkeys --checksig --verbose` output. Every check must say OK; one signature line must
    name the catalogue key — by its full fingerprint (rpm 6) or its 16-digit key id — with
    RSA/SHA-256 or stronger; and a payload digest must have been checked against the signed header.
    An 8-digit key id cannot prove which key signed, so it does not count."""
    expected = _fingerprint(fingerprint)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    # rpmkeys names the file first ("<path>:"); every other line is "<check>: <verdict>".
    if lines and ((path is not None and lines[0] == f"{os.fspath(path)}:")
                  or (lines[0].endswith(":") and ": " not in lines[0])):
        lines = lines[1:]
    untrusted: list[str] = []
    failed: list[str] = []
    signatures: list[re.Match[str]] = []
    payload = ""
    for line in lines:
        label, separator, verdict = line.rpartition(": ")
        verdict = verdict.strip()
        if not separator:
            failed.append(line)
        elif verdict.startswith(("NOKEY", "NOTTRUSTED")):
            untrusted.append(line)
        elif verdict != "OK":
            failed.append(line)
        elif (signature := _SIGNATURE.fullmatch(label)) is not None:
            signatures.append(signature)
        elif (digest := _PAYLOAD_DIGEST.fullmatch(label)) is not None:
            payload = payload or digest.group("hash").upper()
    if untrusted:
        raise VendorError("signature_untrusted_key", untrusted[0][:200])
    if failed or returncode != 0:
        raise VendorError("signature_invalid", (failed or [f"rpmkeys exited {returncode}"])[0][:200])
    if not signatures:
        raise VendorError("signature_missing", "the package carries no signature")
    ours = [match for match in signatures
            if (match.group("fingerprint") or "").lower() == expected
            or (len(match.group("keyid") or "") == 16 and match.group("keyid").lower() == expected[-16:])]
    if not ours:
        raise VendorError("signature_wrong_key", signatures[0].group(0)[:200])
    strong = [match for match in ours if match.group("pubkey").upper() in STRONG_PUBKEYS
              and match.group("hash").upper() in STRONG_HASHES]
    if not strong:
        raise VendorError("signature_weak", ours[0].group(0)[:200])
    if not payload:
        raise VendorError("payload_unverified", "no payload digest was checked")
    best = strong[0]
    return {"fingerprint": expected, "algorithm": f"{best.group('pubkey').upper()}/{best.group('hash').upper()}",
            "payload_digest": payload}


def verify_signature(rpm_path: str | os.PathLike[str], fingerprint: str, *,
                     run: Callable[..., Any] = subprocess.run) -> dict[str, str]:
    """The package is signed by the catalogue's key, which the image already trusts — or refused."""
    expected = _fingerprint(fingerprint)
    if not key_installed(expected, run=run):
        raise VendorError("key_not_installed", expected)
    path = os.fspath(rpm_path)
    status, output, errors = _tool(run, [RPMKEYS, "--checksig", "--verbose", "--", path],
                                   timeout=TOOL_TIMEOUT, failure="signature_invalid")
    if status != 0 and not output.strip():
        raise VendorError("signature_invalid", errors.strip()[-200:] or f"rpmkeys exited {status}")
    return parse_checksig(status, output, expected, path)


_HEADER_FORMAT = "%{NAME}\\n%{EPOCHNUM}\\n%{VERSION}\\n%{RELEASE}\\n%{ARCH}\\n%{PAYLOADFORMAT}\\n"


def read_header(rpm_path: str | os.PathLike[str], *, run: Callable[..., Any] = subprocess.run) -> dict[str, str]:
    status, output, errors = _tool(run, [RPM, "-qp", "--qf", _HEADER_FORMAT, "--", os.fspath(rpm_path)],
                                   timeout=TOOL_TIMEOUT, failure="header_mismatch")
    lines = output.split("\n")
    if status != 0 or len(lines) < 6:
        raise VendorError("header_mismatch", (errors.strip() or "the header cannot be read")[-200:])
    name, epoch, version, release, arch, payload = lines[:6]
    return {"name": name, "epoch": epoch, "version": version, "release": release, "arch": arch,
            "payload_format": payload}


def check_header(rpm_path: str | os.PathLike[str], info: Mapping[str, Any], *,
                 run: Callable[..., Any] = subprocess.run) -> dict[str, str]:
    """The SIGNED header must name what the metadata promised: same package, version and arch."""
    header = read_header(rpm_path, run=run)
    expected = (info.get("name"), str(info.get("epoch", 0)), info.get("version"), info.get("release"),
                info.get("arch"))
    actual = (header["name"], header["epoch"], header["version"], header["release"], header["arch"])
    if actual != expected:
        raise VendorError("header_mismatch", f"{actual} != {expected}"[:200])
    if header["payload_format"] != "cpio":
        raise VendorError("unsupported_archive", f"payload format {header['payload_format']!r}"[:80])
    return header


# ── the payload ──────────────────────────────────────────────────────────────
@dataclasses.dataclass
class Extracted:
    files: int = 0
    directories: int = 0
    links: int = 0
    bytes: int = 0
    skipped: int = 0                                   # entries outside install_root, not written
    stripped: list[str] = dataclasses.field(default_factory=list)   # setuid/setgid removed (tree paths)
    extras: dict[str, bytes] = dataclasses.field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {"files": self.files, "directories": self.directories, "links": self.links,
                "bytes": self.bytes, "skipped": self.skipped, "stripped": list(self.stripped),
                "extras": sorted(self.extras)}


class _Budget:
    def __init__(self, compressed: int, total: int, cancelled: Callable[[], bool] | None,
                 progress: Callable[[int], None] | None):
        self.compressed = max(int(compressed or 0), 0)
        self.total = max(int(total), 1)
        self.cancelled = cancelled or (lambda: False)
        self.progress = progress
        self.entries = 0
        self.bytes = 0
        self._last = 0.0

    def entry(self) -> None:
        self.entries += 1
        if self.entries > MAX_TREE_FILES:
            raise VendorError("archive_bomb", f"more than {MAX_TREE_FILES} entries")

    def account(self, size: int) -> None:
        """Called BEFORE anything is written, so a bomb never reaches the disk."""
        self.bytes += size
        if self.bytes > MAX_TREE_BYTES:
            raise VendorError("archive_bomb", f"{self.bytes} bytes")
        if self.compressed and self.bytes > RATIO_FLOOR and self.bytes > self.compressed * MAX_RATIO:
            raise VendorError("archive_bomb", f"expands {self.bytes // self.compressed}x")

    def tick(self, position: int) -> None:
        now = time.monotonic()
        if now - self._last < 0.25:
            return
        self._last = now
        if self.cancelled():
            raise VendorError("cancelled")
        if self.progress is not None:
            self.progress(min(99, position * 100 // self.total))


def _refuse_control(name: str) -> None:
    if _CONTROL.search(name) or "\\" in name:
        raise VendorError("unsafe_archive", f"control character in a name: {name!r}"[:200])


def _member_path(name: str) -> str:
    """`./usr/lib/app/x` -> `/usr/lib/app/x`. Absolute names and `..` are refused, never repaired."""
    _refuse_control(name)
    if name.startswith("/"):
        raise VendorError("unsafe_archive", f"absolute name: {name!r}"[:200])
    rest = name[2:] if name.startswith("./") else name
    parts = rest.split("/")
    if ".." in parts:
        raise VendorError("unsafe_archive", f"name leaves the archive: {name!r}"[:200])
    return "/" + "/".join(part for part in parts if part and part != ".")


def _inside(path: str, root: str) -> str | None:
    """Path relative to `root` ("" for root itself), or None when it is outside."""
    if path == root:
        return ""
    if path.startswith(root + "/"):
        return path[len(root) + 1:]
    return None


def _read_exact(stream: Any, count: int) -> bytes:
    data = stream.read(count)
    if len(data) != count:
        raise VendorError("archive_invalid", "the payload ends early")
    return data


_HEX8 = re.compile(rb"[0-9A-Fa-f]{8}")


def _header_fields(header: bytes) -> list[int]:
    fields = []
    for index in range(13):
        chunk = header[6 + 8 * index: 14 + 8 * index]
        if not _HEX8.fullmatch(chunk):
            raise VendorError("archive_invalid", "a header field is not hexadecimal")
        fields.append(int(chunk, 16))
    return fields


class _Reader:
    """A newc ("070701"/"070702") reader that writes only under `root`, never through a link."""

    def __init__(self, stream: Any, total: int, root: str, target: Path, wanted: set[str],
                 result: Extracted, budget: _Budget):
        self.stream, self.total, self.root, self.target = stream, total, root, target
        self.wanted, self.result, self.budget = wanted, result, budget
        self.hard_written: dict[int, Path | None] = {}
        self.hard_bytes: dict[int, bytes | None] = {}
        self.pending: dict[int, list[tuple[str, str | None, int]]] = {}
        self.extra_links: dict[str, str] = {}
        self.root_seen = False

    # -- stream helpers --------------------------------------------------
    def _align(self) -> None:
        pad = (-self.stream.tell()) % 4
        if pad:
            _read_exact(self.stream, pad)

    def _skip(self, size: int) -> None:
        position = self.stream.tell() + size
        if position > self.total:
            raise VendorError("archive_invalid", "the payload ends early")
        self.stream.seek(position)
        self.budget.tick(position)

    def _copy(self, size: int, sink: Any, capture: bytearray | None) -> None:
        if sink is None and capture is None:
            self._skip(size)
            return
        remaining = size
        while remaining:
            block = _read_exact(self.stream, min(BLOCK, remaining))
            remaining -= len(block)
            if sink is not None:
                sink.write(block)
            if capture is not None:
                capture.extend(block)
            self.budget.tick(self.stream.tell())

    # -- the tree --------------------------------------------------------
    def _parent(self, rel: str) -> Path:
        """Create the folders above `rel`; a component that is a link or a file is refused."""
        current = self.target
        for part in rel.split("/")[:-1]:
            current = current / part
            try:
                info = os.lstat(current)
            except FileNotFoundError:
                os.mkdir(current, 0o755)
                continue
            if not stat.S_ISDIR(info.st_mode):
                raise VendorError("unsafe_archive", f"{rel!r} passes through a link or a file"[:200])
        return current

    def _directory(self, rel: str) -> None:
        path = self._parent(rel) / rel.split("/")[-1]
        try:
            os.mkdir(path, 0o755)
        except FileExistsError:
            if not stat.S_ISDIR(os.lstat(path).st_mode):
                raise VendorError("unsafe_archive", f"{rel!r} is both a folder and something else"[:200])
            return
        self.result.directories += 1

    def _create(self, rel: str) -> tuple[Path, Any]:
        path = self._parent(rel) / rel.split("/")[-1]
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        except FileExistsError:
            raise VendorError("unsafe_archive", f"{rel!r} appears twice"[:200]) from None
        return path, os.fdopen(descriptor, "wb")

    def _seal(self, sink: Any, rel: str, mode: int) -> None:
        # Keep the executable bit and nothing else: never setuid or setgid, never group/world write.
        os.fchmod(sink.fileno(), 0o755 if mode & 0o111 else 0o644)
        sink.close()
        if mode & (stat.S_ISUID | stat.S_ISGID):
            self.result.stripped.append(rel)
        self.result.files += 1

    def _link(self, source: Path, rel: str) -> None:
        path = self._parent(rel) / rel.split("/")[-1]
        if os.path.lexists(path):
            raise VendorError("unsafe_archive", f"{rel!r} appears twice"[:200])
        os.link(source, path, follow_symlinks=False)
        self.result.files += 1

    # -- entries ---------------------------------------------------------
    def run(self) -> None:
        while True:
            header = _read_exact(self.stream, 110)
            magic = header[:6]
            if magic in (b"07070X", b"07070x"):
                raise VendorError("unsupported_archive", "the payload uses the format for files over 4 GiB")
            if magic not in (b"070701", b"070702"):
                raise VendorError("archive_invalid", "not a newc payload")
            ino, mode, _uid, _gid, nlink, _mtime, size, _dmaj, _dmin, _rmaj, _rmin, namesize, _check = \
                _header_fields(header)
            if not 2 <= namesize <= MAX_NAME_BYTES + 1:
                raise VendorError("archive_invalid", "a name is empty or too long")
            raw = _read_exact(self.stream, namesize)
            self._align()
            if raw[-1:] != b"\0" or b"\0" in raw[:-1]:
                raise VendorError("archive_invalid", "a name is not terminated")
            if raw[:-1] == b"TRAILER!!!":
                self._trailer(size)
                break
            try:
                name = raw[:-1].decode("utf-8")
            except UnicodeDecodeError:
                raise VendorError("unsafe_archive", f"a name is not UTF-8: {raw[:80]!r}") from None
            self.budget.entry()
            self._entry(name, ino, mode, nlink, size)
            self._align()
        self._finish()

    def _entry(self, name: str, ino: int, mode: int, nlink: int, size: int) -> None:
        path = _member_path(name)
        kind = stat.S_IFMT(mode)
        if kind not in (stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK):
            raise VendorError("unsafe_archive", f"device, pipe or socket: {name!r}"[:200])
        rel = _inside(path, self.root)
        if kind == stat.S_IFDIR:
            if size:
                raise VendorError("archive_invalid", f"a folder with data: {name!r}"[:200])
            if rel == "":
                self.root_seen = True
            elif rel is not None:
                self._directory(rel)
            else:
                self.result.skipped += 1
            return
        if kind == stat.S_IFLNK:
            self._symlink(name, path, rel, size)
            return
        if rel == "":
            raise VendorError("unsafe_archive", "the app folder itself is a file")
        if size > MAX_TREE_BYTES:
            raise VendorError("archive_bomb", f"{size} bytes in one file")
        if nlink > 1:
            self._hardlink(path, rel, ino, mode, size)
            return
        capture = bytearray() if path in self.wanted and size <= MAX_EXTRA_BYTES else None
        if rel is None:
            self._copy(size, None, capture)
            self.result.skipped += 1
        else:
            self.budget.account(size)
            _path, sink = self._create(rel)
            try:
                self._copy(size, sink, capture)
            finally:
                if not sink.closed:
                    self._seal(sink, rel, mode)
            self.result.bytes += size
        if capture is not None:
            self.result.extras[path] = bytes(capture)

    def _symlink(self, name: str, path: str, rel: str | None, size: int) -> None:
        if not 0 < size <= MAX_LINK_BYTES:
            raise VendorError("archive_invalid", f"a link of {size} bytes: {name!r}"[:200])
        raw = _read_exact(self.stream, size)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise VendorError("unsafe_archive", f"a link target is not UTF-8: {name!r}"[:200]) from None
        _refuse_control(text)
        joined = text if text.startswith("/") else posixpath.join(posixpath.dirname(path), text)
        resolved = posixpath.normpath(joined)
        if path in self.wanted:
            self.extra_links[path] = resolved
        if rel is None:
            self.result.skipped += 1
            return
        if rel == "":
            raise VendorError("unsafe_archive", "the app folder itself is a link")
        if resolved.startswith("//") or _inside(resolved, self.root) is None:
            raise VendorError("unsafe_archive", f"link leaves the app folder: {name!r} -> {text!r}"[:200])
        self.budget.account(0)
        destination = self._parent(rel) / rel.split("/")[-1]
        if os.path.lexists(destination):
            raise VendorError("unsafe_archive", f"{rel!r} appears twice"[:200])
        # Rewritten relative, so an absolute link inside the package still points inside the tree.
        os.symlink(posixpath.relpath(resolved, posixpath.dirname(path)), destination)
        self.result.links += 1

    def _hardlink(self, path: str, rel: str | None, ino: int, mode: int, size: int) -> None:
        """newc stores a hard-linked file's data once, normally with its LAST name."""
        if size == 0:
            if ino in self.hard_written:
                self._join(ino, path, rel)
            else:
                self.pending.setdefault(ino, []).append((path, rel, mode))
            return
        if ino in self.hard_written:
            raise VendorError("unsafe_archive", "a hard link carries its data twice")
        members = self.pending.pop(ino, []) + [(path, rel, mode)]
        holder = next((member for member in members if member[1] is not None), None)
        wants_bytes = any(member[0] in self.wanted for member in members) and size <= MAX_EXTRA_BYTES
        capture = bytearray() if wants_bytes else None
        written: Path | None = None
        if holder is None:
            self._copy(size, None, capture)
        else:
            self.budget.account(size)
            written, sink = self._create(holder[1])
            try:
                self._copy(size, sink, capture)
            finally:
                if not sink.closed:
                    self._seal(sink, holder[1], holder[2])
            self.result.bytes += size
        self.hard_written[ino] = written
        self.hard_bytes[ino] = bytes(capture) if capture is not None else None
        for member in members:
            if member is not holder:
                self._join(ino, member[0], member[1])
            elif member[0] in self.wanted and capture is not None:
                self.result.extras[member[0]] = bytes(capture)

    def _join(self, ino: int, path: str, rel: str | None) -> None:
        if path in self.wanted and self.hard_bytes.get(ino) is not None:
            self.result.extras[path] = self.hard_bytes[ino]  # type: ignore[assignment]
        if rel is None:
            self.result.skipped += 1
            return
        source = self.hard_written.get(ino)
        if source is None:
            raise VendorError("unsafe_archive", f"a hard link without its data: {path!r}"[:200])
        self.budget.account(0)
        self._link(source, rel)

    def _trailer(self, size: int) -> None:
        if size:
            raise VendorError("archive_invalid", "the trailer carries data")
        self._align()
        rest = self.total - self.stream.tell()
        if rest > TRAILER_SLACK:
            raise VendorError("archive_invalid", f"{rest} bytes after the trailer")
        if self.stream.read(rest).strip(b"\0"):
            raise VendorError("archive_invalid", "data after the trailer")

    def _finish(self) -> None:
        # Hard-link groups whose every name had no data: an empty file, linked under each name.
        for ino, members in list(self.pending.items()):
            holder = next((member for member in members if member[1] is not None), None)
            if holder is not None:
                self.budget.account(0)
                written, sink = self._create(holder[1])
                self._seal(sink, holder[1], holder[2])
                self.hard_written[ino] = written
            else:
                self.hard_written[ino] = None
            self.hard_bytes[ino] = b""
            for member in members:
                if member is not holder:
                    self._join(ino, member[0], member[1])
                elif member[0] in self.wanted:
                    self.result.extras[member[0]] = b""
        self.pending.clear()
        # A wanted file that is a link into the app folder is read from the tree just written.
        for extra, resolved in self.extra_links.items():
            rel = _inside(resolved, self.root)
            if not rel or extra in self.result.extras:
                continue
            candidate = self.target / rel
            try:
                info = os.lstat(candidate)
            except FileNotFoundError:
                continue
            if stat.S_ISREG(info.st_mode) and info.st_size <= MAX_EXTRA_BYTES:
                self.result.extras[extra] = candidate.read_bytes()
        if not self.root_seen and not (self.result.files or self.result.directories or self.result.links):
            raise VendorError("install_root_missing", self.root)


def extract_cpio(cpio_path: str | os.PathLike[str], install_root: str, target_dir: str | os.PathLike[str], *,
                 extras: Iterable[str] = (), compressed_size: int = 0,
                 cancelled: Callable[[], bool] | None = None,
                 progress: Callable[[int], None] | None = None,
                 seed: Mapping[str, bytes] | None = None) -> Extracted:
    """Unpack the part of a newc payload under `install_root` into the new folder `target_dir`.

    `seed` files are written into the new folder BEFORE anything is unpacked (MoOS's ownership
    marker), so the folder is never unmarked, and a payload that ships the same name is refused."""
    root = _payload_path(install_root, "install_root")
    wanted = {_payload_path(extra, "extra") for extra in extras if extra}
    target = Path(target_dir)
    try:
        target.mkdir(mode=0o755)
    except FileExistsError:
        raise VendorError("name_taken", str(target)) from None
    result = Extracted()
    try:
        for name, data in (seed or {}).items():
            if not name or "/" in name or name in (".", "..") or _CONTROL.search(name):
                raise VendorError("bad_entry", f"seed {name!r}"[:80])
            _write_new(target / name, data)
        with open(cpio_path, "rb") as stream:
            total = os.fstat(stream.fileno()).st_size
            budget = _Budget(compressed_size, total, cancelled, progress)
            _Reader(stream, total, root, target, wanted, result, budget).run()
        return result
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise


def _rpm2cpio(rpm_path: Path, cpio_path: Path, cancelled: Callable[[], bool], limit: int) -> None:
    """rpm2cpio into a private file, to the end, checked — never a pipe a reader can close early
    (a producer killed by SIGPIPE after a padded trailer looks like success to its consumer)."""
    if not os.access(RPM2CPIO, os.X_OK):
        raise VendorError("tool_missing", RPM2CPIO)
    output = os.open(cpio_path, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW | os.O_CLOEXEC)
    with tempfile.TemporaryFile(dir=cpio_path.parent) as errors:
        try:
            child = subprocess.Popen([RPM2CPIO, os.fspath(rpm_path)], stdin=subprocess.DEVNULL, stdout=output,
                                     stderr=errors, env=_tool_env(), close_fds=True)
        except OSError as error:
            raise VendorError("tool_missing", f"{RPM2CPIO}: {error}") from error
        finally:
            os.close(output)
        deadline = time.monotonic() + CONVERT_TIMEOUT
        status: int | None = None
        try:
            while status is None:
                try:
                    status = child.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    if cancelled():
                        raise VendorError("cancelled") from None
                    if time.monotonic() > deadline:
                        raise VendorError("extract_failed", "rpm2cpio timed out") from None
                    if cpio_path.stat().st_size > limit:
                        raise VendorError("archive_bomb", "the payload expands past its budget") from None
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
        if status != 0:
            errors.seek(0)
            tail = errors.read()[-400:].decode("utf-8", "replace").strip()
            raise VendorError("extract_failed", f"rpm2cpio exited {status}: {tail}"[:500])
    size = cpio_path.stat().st_size
    if size == 0:
        raise VendorError("extract_failed", "rpm2cpio produced nothing")
    if size > limit:
        raise VendorError("archive_bomb", "the payload expands past its budget")


def extract(rpm_path: str | os.PathLike[str], install_root: str, target_dir: str | os.PathLike[str], *,
            extras: Iterable[str] = (), work_dir: str | os.PathLike[str] | None = None,
            cancelled: Callable[[], bool] | None = None, progress: Callable[[int], None] | None = None,
            convert: Callable[[Path, Path, Callable[[], bool], int], None] | None = None,
            seed: Mapping[str, bytes] | None = None) -> Extracted:
    """rpm2cpio (no scriptlet runs) into a private file, then the payload reader above."""
    package = Path(rpm_path)
    target = Path(target_dir)
    work = Path(work_dir) if work_dir is not None else target.parent
    compressed = package.stat().st_size
    limit = min(MAX_TREE_BYTES, max(compressed, 1) * MAX_RATIO) + TRAILER_SLACK
    stop = cancelled or (lambda: False)
    descriptor, name = tempfile.mkstemp(prefix=".payload-", suffix=".cpio", dir=work)
    os.close(descriptor)
    payload = Path(name)
    try:
        (convert or _rpm2cpio)(package, payload, stop, limit)
        if stop():
            raise VendorError("cancelled")
        return extract_cpio(payload, install_root, target, extras=extras, compressed_size=compressed,
                            cancelled=stop, progress=progress, seed=seed)
    finally:
        _unlink_quietly(payload)


# ── does the program start its own sandbox? (read, never run) ────────────────
SANDBOX_SWITCHES = ("--no-sandbox", "--disable-namespace-sandbox", "--disable-setuid-sandbox")
# Chromium's zygote prefers the user-namespace sandbox whenever the kernel lets an unprivileged
# user create one; only otherwise does it look for a root-owned setuid `chrome-sandbox` beside the
# program, and with neither it stops with "No usable sandbox!". These strings are that logic.
_CHROMIUM_MARKERS = (b"No usable sandbox", b"disable-namespace-sandbox")
_APPEND_SWITCH = re.compile(
    rb"appendSwitch\(\s*[\"'`](?:--)?(no-sandbox|disable-namespace-sandbox|disable-setuid-sandbox)[\"'`]")
MAX_BUNDLE_SCAN = 1024 ** 3


def userns_available(proc_sys: Path = Path("/proc/sys")) -> bool:
    """May an unprivileged user create a user namespace on this kernel? Plain file reads."""
    def read(rel: str) -> str | None:
        try:
            return (proc_sys / rel).read_text(encoding="ascii").strip()
        except (OSError, UnicodeDecodeError):
            return None

    maximum = read("user/max_user_namespaces")
    if maximum is None or not maximum.isdigit() or int(maximum) == 0:
        return False
    if read("kernel/unprivileged_userns_clone") not in (None, "1"):
        return False
    return read("kernel/apparmor_restrict_unprivileged_userns") in (None, "0")


def _contains_all(path: Path, needles: Iterable[bytes]) -> bool:
    wanted = set(needles)
    overlap = max(len(needle) for needle in wanted) - 1
    tail = b""
    with open(path, "rb") as handle:
        while wanted:
            block = handle.read(8 * BLOCK)
            if not block:
                break
            window = tail + block
            wanted = {needle for needle in wanted if needle not in window}
            tail = window[-overlap:]
    return not wanted


def _is_elf(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            return handle.read(4) == b"\x7fELF"
    except OSError:
        return False


def _program(tree: Path, exec_rel: str) -> Path:
    """The program a launcher will run: a regular executable ELF or script inside the tree."""
    root = Path(tree).resolve()
    try:
        program = (Path(tree) / exec_rel).resolve(strict=True)
        info = os.stat(program)
    except (OSError, RuntimeError):
        raise VendorError("nothing_to_launch", exec_rel) from None
    if not program.is_relative_to(root) or not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o111:
        raise VendorError("nothing_to_launch", exec_rel)
    with open(program, "rb") as handle:
        head = handle.read(4)
    if head != b"\x7fELF" and head[:2] != b"#!":
        raise VendorError("nothing_to_launch", f"{exec_rel} is not a program")
    return program


def _bundle_switches(tree: Path) -> set[str]:
    """Switches an Electron app's own code appends to itself (resources/app.asar, JS files only)."""
    found: set[str] = set()
    archive = tree / "resources" / "app.asar"
    try:
        if archive.is_symlink() or not archive.is_file():
            return found
        with open(archive, "rb") as handle:
            head = handle.read(16)
            if len(head) < 16:
                return found
            size_field, header_size, _payload, json_size = struct.unpack("<4I", head)
            if size_field != 4 or json_size > header_size or json_size > 64 * 1024 ** 2:
                return found
            header = json.loads(handle.read(json_size))
            base = 8 + header_size
            scanned = 0
            pending = [header]
            while pending:
                node = pending.pop()
                for name, child in (node.get("files") or {}).items():
                    if not isinstance(child, dict):
                        continue
                    if "files" in child:
                        pending.append(child)
                        continue
                    if child.get("unpacked") or not str(name).endswith((".js", ".cjs", ".mjs")):
                        continue
                    size = child.get("size")
                    offset = child.get("offset")
                    if not isinstance(size, int) or not str(offset).isdigit() or size > 64 * 1024 ** 2:
                        continue
                    scanned += size
                    if scanned > MAX_BUNDLE_SCAN:
                        return found
                    handle.seek(base + int(offset))
                    for match in _APPEND_SWITCH.finditer(handle.read(size)):
                        found.add("--" + match.group(1).decode("ascii"))
    except (OSError, ValueError, struct.error, AttributeError, TypeError):
        return found
    return found


def sandbox_report(tree: str | os.PathLike[str], exec_rel: str, *, proc_sys: Path = Path("/proc/sys"),
                   scan_bundle: bool = True) -> dict[str, Any]:
    """How the extracted program will isolate its renderers, read from its files and /proc/sys only.

    mode: "namespace" (the user-namespace sandbox), "setuid" (a root-owned setuid helper — never
    after extract(), which strips the bit), "off" (the app turns its own sandbox off), "unavailable"
    (a Chromium program with no sandbox it could start here) or "not-chromium"."""
    tree = Path(tree)
    setuid: list[str] = []
    helper = "absent"
    for directory, folders, files in os.walk(tree):
        for name in files + folders:
            path = Path(directory) / name
            info = os.lstat(path)
            if stat.S_ISREG(info.st_mode):
                if info.st_mode & (stat.S_ISUID | stat.S_ISGID):
                    setuid.append(str(path.relative_to(tree)))
                if name == "chrome-sandbox":
                    helper = "setuid" if info.st_mode & stat.S_ISUID and info.st_uid == 0 else "inert"
    program = _program(tree, exec_rel)
    binaries = [program] if _is_elf(program) else sorted(
        (path for path in program.parent.iterdir() if path.is_file() and not path.is_symlink() and _is_elf(path)),
        key=lambda path: -path.stat().st_size)[:3]
    chromium = any(_contains_all(binary, _CHROMIUM_MARKERS) for binary in binaries)
    switches: set[str] = set()
    for directory, folders, files in os.walk(tree):
        # The app's own launchers: scripts in its folder and one level down, not every tool it bundles.
        if Path(directory) != tree:
            folders[:] = []
        for name in files:
            path = Path(directory) / name
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode) or info.st_size > 64 * 1024:
                continue
            data = path.read_bytes()
            if data[:2] == b"#!":
                switches.update(switch for switch in SANDBOX_SWITCHES if switch.encode() in data)
    if scan_bundle:
        switches |= _bundle_switches(tree)
    userns = userns_available(proc_sys)
    if "--no-sandbox" in switches:
        mode = "off"
    elif not chromium:
        mode = "not-chromium"
    elif userns and "--disable-namespace-sandbox" not in switches:
        mode = "namespace"
    elif helper == "setuid" and "--disable-setuid-sandbox" not in switches:
        mode = "setuid"
    else:
        mode = "unavailable"
    return {"mode": mode, "helper": helper, "setuid_files": setuid, "chromium": chromium,
            "switches": sorted(switches), "userns": userns}


# ── the launcher MoOS writes ─────────────────────────────────────────────────
def _clean_text(value: str, limit: int) -> str:
    """One line a person reads: no control characters, no bidi overrides, bounded."""
    value = _BIDI.sub("", _CONTROL.sub(" ", value or ""))
    return " ".join(value.split())[:limit].strip()


def _display_text(value: str, limit: int) -> str:
    """A desktop-file string value, unescaped once (\\s \\n \\t \\r \\\\), then cleaned."""
    escapes = {"s": " ", "n": " ", "t": " ", "r": " ", "\\": "\\"}
    value = re.sub(r"\\(.)", lambda match: escapes.get(match.group(1), match.group(1)), value or "")
    return _clean_text(value, limit)


def desktop_fields(data: bytes | None, fallback_name: str) -> dict[str, str]:
    """Name, Comment, Categories (and Icon, for information) from a package's .desktop file.
    Exec, MimeType, actions and every other key are the package's instructions and are not read."""
    fields: dict[str, str] = {}
    section = ""
    text = (data or b"")[:64 * 1024].decode("utf-8", "replace")
    for line in text.splitlines()[:400]:
        line = line.strip()
        if line.startswith("["):
            section = line
        elif section == "[Desktop Entry]" and "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            if key.strip() in ("Name", "Comment", "Categories", "Icon"):
                fields.setdefault(key.strip(), value.strip())
    categories: list[str] = []
    for category in fields.get("Categories", "").split(";"):
        if category.strip() in MAIN_CATEGORIES and category.strip() not in categories:
            categories.append(category.strip())
    return {"name": _display_text(fields.get("Name", ""), 80) or _display_text(fallback_name, 80) or "App",
            "comment": _display_text(fields.get("Comment", ""), 160),
            "categories": ";".join(categories or ["Utility"]) + ";",
            "icon_name": _display_text(fields.get("Icon", ""), 80)}


def _desktop_path(path: str) -> str:
    if _CONTROL.search(path) or "\\" in path:
        raise VendorError("unsafe_path", path[:200])
    return path


def _exec_argument(path: str) -> str:
    """One quoted Exec argument. A home path with a quote, backtick, dollar or backslash would need
    two layers of escaping that launchers disagree about: refused rather than guessed."""
    if _CONTROL.search(path) or _EXEC_UNSAFE.search(path):
        raise VendorError("unsafe_path", path[:200])
    return '"' + path.replace("%", "%%") + '"'


def launcher_text(app_id: str, *, exec_path: str, name: str, comment: str = "", icon: str = "",
                  categories: str = "Utility;", wm_class: str = "", schemes: Iterable[str] = ()) -> str:
    app_id = check_id(app_id)
    name = _clean_text(name, 80)
    comment = _clean_text(comment, 160)
    if not name:
        raise VendorError("bad_entry", "a launcher needs a name")
    if not _CATEGORIES.fullmatch(categories or ""):
        raise VendorError("bad_entry", "categories")
    if wm_class and not _WM_CLASS.fullmatch(wm_class):
        raise VendorError("bad_entry", "wm_class")
    schemes = list(schemes)
    for scheme in schemes:
        if not _SCHEME.fullmatch(scheme) or scheme in RESERVED_SCHEMES:
            raise VendorError("bad_entry", f"scheme {scheme!r}"[:80])
    lines = ["[Desktop Entry]", "Type=Application", f"Name={name.replace(chr(92), chr(92) * 2)}"]
    if comment:
        lines.append(f"Comment={comment.replace(chr(92), chr(92) * 2)}")
    lines += [f"Exec={_exec_argument(exec_path)} %U", f"TryExec={_desktop_path(exec_path)}",
              f"Icon={_desktop_path(icon) if icon else 'application-x-executable'}",
              "Terminal=false", f"Categories={categories}"]
    if schemes:
        lines.append("MimeType=" + "".join(f"x-scheme-handler/{scheme};" for scheme in schemes))
    if wm_class:
        lines.append(f"StartupWMClass={wm_class}")
    lines += [f"X-MoOS-Vendor={app_id}", ""]
    return "\n".join(lines)


def _read_small(path: Path, limit: int) -> bytes | None:
    """A regular file's first `limit` bytes, never through a link."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return None
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            return None
        return handle.read(limit)


def _marked_launcher(path: Path, app_id: str) -> bool:
    data = _read_small(path, 64 * 1024)
    if data is None:
        return False
    return f"X-MoOS-Vendor={app_id}" in (line.strip() for line in data.decode("utf-8", "replace").splitlines())


def _marked_tree(path: Path, app_id: str) -> bool:
    try:
        if not stat.S_ISDIR(os.lstat(path).st_mode):
            return False
    except FileNotFoundError:
        return False
    data = _read_small(path / MARKER, 256)
    return data is not None and data.decode("utf-8", "replace").strip() == app_id


def _present(path: Path) -> bool:
    return os.path.lexists(path)


def _claim_launcher(app_id: str) -> Path:
    path = launcher_path(app_id)
    if _present(path) and not _marked_launcher(path, app_id):
        raise VendorError("name_taken", str(path))
    return path


def _write_atomic(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.new")
    _unlink_quietly(temporary)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            os.fchmod(handle.fileno(), mode)
        os.replace(temporary, path)
    except BaseException:
        _unlink_quietly(temporary)
        raise


def write_launcher(app_id: str, *, exec_path: str, name: str, comment: str = "", icon: str = "",
                   categories: str = "Utility;", wm_class: str = "", schemes: Iterable[str] = ()) -> Path:
    """org.moos.vendor.<id>.desktop — written by MoOS; a file there that MoOS did not write is refused."""
    path = _claim_launcher(app_id)
    text = launcher_text(app_id, exec_path=exec_path, name=name, comment=comment, icon=icon,
                         categories=categories, wm_class=wm_class, schemes=schemes)
    _write_atomic(path, text.encode("utf-8"), 0o644)
    return path


def _refresh_menu() -> None:
    for argv in (["update-desktop-database", str(desktop_dir())], ["kbuildsycoca6", "--noincremental"]):
        if shutil.which(argv[0]):
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=60, check=False)


# ── records ──────────────────────────────────────────────────────────────────
def installed(app_id: str) -> dict[str, Any] | None:
    data = _read_small(record_path(app_id), 64 * 1024)
    if data is None:
        return None
    try:
        record = json.loads(data.decode("utf-8"))
        if not isinstance(record, dict) or record.get("schema") != 1 or record.get("id") != app_id:
            return None
        _evr(record)
    except (ValueError, UnicodeDecodeError, VendorError):
        return None
    return record


def intact(app_id: str) -> bool:
    """Is everything install() wrote still in place: the record, MoOS's own launcher and the
    marked app folder? What opens the app, and what may skip a reinstall, asks this."""
    return (installed(app_id) is not None and _marked_launcher(launcher_path(app_id), app_id)
            and _marked_tree(app_dir(app_id), app_id))


def update_available(app_id: str, newest: Any) -> bool:
    """True only when `newest` sorts after what is installed (a lower build is never an update)."""
    record = installed(app_id)
    if record is None:
        return False
    return evr_compare(newest, record) > 0


def _remove_tree(path: Path, app_id: str) -> bool:
    if _marked_tree(path, app_id):
        shutil.rmtree(path)   # fd-based on Linux: never follows a link inside
        return True
    return False


def remove(app_id: str, *, refresh_menu: bool = True) -> bool:
    """Remove exactly what install() wrote for `app_id`: files carrying MoOS's marker, nothing else."""
    app_id = check_id(app_id)
    removed = False
    launcher = launcher_path(app_id)
    if _marked_launcher(launcher, app_id):
        launcher.unlink()
        removed = True
    for directory in (app_dir(app_id), staging_dir(app_id), previous_dir(app_id)):
        removed = _remove_tree(directory, app_id) or removed
    record = record_path(app_id)
    if _read_small(record, 1) is not None:
        record.unlink()
        removed = True
    if removed and refresh_menu:
        _refresh_menu()
    return removed


# ── install / update ─────────────────────────────────────────────────────────
def _checked_info(info: Mapping[str, Any], spec: Entry, arch: str) -> dict[str, Any]:
    """A resolve() result handed back by the Store: re-checked against the catalogue entry."""
    url, digest, size = _download_fields(info)
    epoch, version, release = _evr(info)
    base = spec.repo_url(arch)
    if info.get("name") != spec.package or info.get("arch") != arch or not release:
        raise VendorError("bad_entry", "the resolved package does not belong to this entry")
    if _same_host_url(base, url, None) != url:
        raise VendorError("foreign_host", url[:200])
    checked = {"name": spec.package, "arch": arch, "epoch": epoch, "version": version, "release": release,
               "evr": evr_text(epoch, version, release), "url": url, "sha256": digest, "size": size, "repo": base}
    for key in ("installed_size", "archive_size"):
        value = info.get(key, 0)
        checked[key] = value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
    return checked


def _icon_ok(data: bytes, path: str) -> bool:
    if path.endswith(".png"):
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    head = data[:4096].lstrip()
    return path.endswith(".svg") and (head.startswith(b"<svg") or head.startswith(b"<?xml")) and b"<svg" in data[:65536]


def _write_new(path: Path, data: bytes) -> None:
    """A file MoOS adds to a freshly unpacked app folder. A package that already ships one of these
    names is trying to pass its own file off as MoOS's: refused, never overwritten."""
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o644)
    except FileExistsError:
        raise VendorError("unsafe_archive", f"the package ships {path.name}") from None
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        os.fchmod(handle.fileno(), 0o644)


def _place_icon(staging: Path, spec: Entry, extracted: Extracted) -> str:
    """The icon's path relative to the app folder, or "" for the generic one."""
    if not spec.icon:
        return ""
    rel = _inside(spec.icon, spec.install_root)
    if rel:
        data = _read_small(staging / rel, MAX_EXTRA_BYTES + 1)
        return rel if data and len(data) <= MAX_EXTRA_BYTES and _icon_ok(data, spec.icon) else ""
    data = extracted.extras.get(spec.icon)
    if not data or not _icon_ok(data, spec.icon):
        return ""
    name = ICON_STEM + posixpath.splitext(spec.icon)[1]
    _write_new(staging / name, data)
    return name


def install(app_id: str, entry: Mapping[str, Any] | Entry, *, arch: str | None = None,
            info: Mapping[str, Any] | None = None, display_name: str = "",
            progress: Callable[[str, int | None], None] | None = None,
            cancelled: Callable[[], bool] | None = None, opener: Any = None,
            run: Callable[..., Any] = subprocess.run,
            convert: Callable[[Path, Path, Callable[[], bool], int], None] | None = None,
            refresh_menu: bool = True, proc_sys: Path = Path("/proc/sys")) -> dict[str, Any]:
    """Install or update one vendor app. Atomic: until the new version is complete and integrated,
    the version that worked stays in place, and a failure brings it back."""
    app_id = check_id(app_id)
    spec = parse_entry(entry)
    arch = check_arch(arch or machine_arch())
    report = progress or (lambda _stage, _percent: None)
    stop = cancelled or (lambda: False)
    final = app_dir(app_id)
    staging = staging_dir(app_id)
    previous = previous_dir(app_id)

    # Never adopt or overwrite what MoOS did not write, and say so before downloading anything.
    launcher = _claim_launcher(app_id)
    if _present(final) and not _marked_tree(final, app_id):
        raise VendorError("name_taken", str(final))
    for leftover in (staging, previous):
        if _present(leftover) and not _remove_tree(leftover, app_id):
            raise VendorError("name_taken", str(leftover))

    report("resolving", None)
    resolved = _checked_info(info, spec, arch) if info is not None else resolve(spec, arch, opener=opener)
    if resolved["installed_size"] > MAX_TREE_BYTES:
        raise VendorError("archive_bomb", f"{resolved['installed_size']} bytes installed")
    if stop():
        raise VendorError("cancelled")
    downloads = downloads_dir()
    downloads.mkdir(mode=0o700, parents=True, exist_ok=True)
    applications_dir().mkdir(mode=0o755, parents=True, exist_ok=True)
    vendor_root().mkdir(parents=True, exist_ok=True)
    unpacked = resolved["installed_size"] or resolved["size"] * 4
    _require_space({downloads: resolved["size"] + (resolved["archive_size"] or unpacked),
                    applications_dir(): unpacked})
    work = Path(tempfile.mkdtemp(prefix=f"vendor-{app_id}-", dir=downloads))
    swapped = False
    launcher_written = False
    old_launcher = _read_small(launcher, 64 * 1024)
    try:
        report("downloading", 0)
        package = fetch(resolved, work, cancelled=stop, opener=opener,
                        progress=lambda done, total: report("downloading", min(99, done * 100 // total)))
        report("verifying", None)
        signature = verify_signature(package, spec.key_fingerprint, run=run)
        check_header(package, resolved, run=run)
        if stop():
            raise VendorError("cancelled")
        # Indeterminate while rpm2cpio writes the payload (it reports nothing); the reader that
        # follows reports real percentages.
        report("extracting", None)
        extras = [path for path in (spec.desktop, spec.icon) if path and _inside(path, spec.install_root) is None]
        extracted = extract(package, spec.install_root, staging, extras=extras, work_dir=work,
                            cancelled=stop, progress=lambda percent: report("extracting", percent),
                            convert=convert, seed={MARKER: f"{app_id}\n".encode()})
        _unlink_quietly(package)
        report("integrating", None)
        sandbox = sandbox_report(staging, spec.exec, proc_sys=proc_sys)
        if sandbox["mode"] == "unavailable":
            raise VendorError("sandbox_unavailable", json.dumps(sandbox)[:200])
        desktop_rel = _inside(spec.desktop, spec.install_root)
        desktop_data = (_read_small(staging / desktop_rel, 64 * 1024) if desktop_rel
                        else extracted.extras.get(spec.desktop))
        fields = desktop_fields(desktop_data, display_name or spec.package)
        icon_rel = _place_icon(staging, spec, extracted)
        if stop():
            raise VendorError("cancelled")
        if _present(final):
            final.rename(previous)
        staging.rename(final)
        swapped = True
        exec_path = str(final / spec.exec)
        write_launcher(app_id, exec_path=exec_path, name=fields["name"], comment=fields["comment"],
                       icon=str(final / icon_rel) if icon_rel else "", categories=fields["categories"],
                       wm_class=spec.wm_class, schemes=spec.schemes)
        launcher_written = True
        record = {"schema": 1, "id": app_id, "kind": "vendor-rpm", "package": resolved["name"],
                  "arch": resolved["arch"], "epoch": resolved["epoch"], "version": resolved["version"],
                  "release": resolved["release"], "evr": resolved["evr"], "sha256": resolved["sha256"],
                  "size": resolved["size"], "repo": resolved["repo"], "url": resolved["url"],
                  "fingerprint": signature["fingerprint"], "signature": signature["algorithm"],
                  "desktop": launcher_name(app_id), "directory": str(final), "exec": spec.exec,
                  "install_root": spec.install_root,
                  "name": fields["name"], "icon": icon_rel, "tree_bytes": extracted.bytes,
                  "tree_files": extracted.files, "stripped": extracted.stripped, "sandbox": sandbox["mode"],
                  "installed_at": int(time.time())}
        _write_atomic(record_path(app_id), (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode(),
                      0o644)
    except BaseException:
        if swapped:
            _remove_tree(final, app_id)
        _remove_tree(staging, app_id)
        if _present(previous) and not _present(final):
            previous.rename(final)                     # the version that worked comes back
        if launcher_written:
            if old_launcher is not None:
                _write_atomic(launcher, old_launcher, 0o644)
            else:
                _unlink_quietly(launcher)
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)
    _remove_tree(previous, app_id)
    if refresh_menu:
        _refresh_menu()
    report("integrating", 100)
    return record
