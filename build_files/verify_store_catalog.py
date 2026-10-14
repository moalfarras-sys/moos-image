#!/usr/bin/env python3
"""Fail the image build when the Mo Store catalogue or the chain that executes it is unsafe.

The catalogue (/usr/share/moos/store/catalog.json, schema v2 in docs/MO_STORE.md) is executable
input: ids reach command arguments, web addresses decide which sites stay inside an app window,
download URLs and their SHA-256 pins decide which bytes MoOS runs, Android signers decide which
updates a container accepts, and executables inside archives become launchers. This gate
therefore validates the catalogue defensively — every kind against an exact allowlist, every
pin against a strict format — before it checks the relationships between the two QML surfaces,
their launchers, the private StoreBridge, moos-storectl, the indexer, the web-app policy and
the vendor-package helper.

Rules that matter more than they look:

* Downloads come from the publisher, pinned. MoOS mirrors nothing: each download names the
  publisher's own HTTPS URL, matched against an exact host + path rule that also binds the
  pinned version and architecture, plus its exact size and SHA-256.
* A vendor RPM is accepted only from an allowlisted repository, for an allowlisted package,
  signed by a key this image already trusts. The gate computes that key's fingerprint itself
  and proves build.sh (and build-arm.sh for an aarch64 entry) imports it.
* A web app's hosts are its own sites. The window has no address bar, so a host that is a
  public suffix — or a `*.` wildcard whose base is one, or that spans one — would keep strangers'
  pages inside it under the app's trusted name: `*.notion.site` is every Notion user's published
  page. The Public Suffix List decides; it is vendored beside this gate (publicsuffix/) so the
  answer is the same on every machine that runs it.
* Glyphs must be SymbolCatalog names. Both QML surfaces fall back to `spark` for anything else,
  so an unknown glyph is not a crash, it is a silently wrong picture; the gate's glyph pattern
  is a subset of the indexer's SLUG_RE, and the indexer's own sanitiser runs on the catalogue
  here, so the two can never disagree about what a valid entry is.
* MoOS's voice never names machinery (an engine, a packaging format, a store channel) or
  another operating system, in descriptions, taglines or search words.

Full-line comments are stripped before any source search, so a gate can never be satisfied by
the prose that documents it. Run locally with MOOS_TEST_ROOT=system_files; tests that plant bad
entries import this module and call check_catalog() on a modified copy.
"""

from __future__ import annotations

import base64
import copy
import functools
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

CATALOG = "/usr/share/moos/store/catalog.json"
STORE_QML = "/usr/share/moos/apps/store/main.qml"
WELCOME_QML = "/usr/share/moos/apps/welcome/main.qml"
SYMBOL_CATALOG = "/usr/lib64/qt6/qml/org/moos/ui/SymbolCatalog.js"
MOOS_STORECTL = "/usr/bin/moos-storectl"
MOOS_STORE_INDEX = "/usr/bin/moos-store-index"
MOOS_OPEN = "/usr/bin/moos-open"
MOOS_STORE = "/usr/bin/moos-store"
MOOS_WELCOME = "/usr/bin/moos-welcome"
MOOS_SELFCHECK = "/usr/bin/moos-selfcheck"
WEBAPP_POLICY = "/usr/lib/moos/moos_webapp_policy.py"
VENDOR_RPM_HELPER = "/usr/lib/moos/moos_vendor_rpm.py"

IMAGE_ROOT = Path(os.environ.get("MOOS_TEST_ROOT", "/"))
BUILD_DIR = Path(__file__).resolve().parent
# publicsuffix.org's list, as fetched (publicsuffix/README.md: source, version, licence). Read
# from beside this file, never from the machine: a gate must answer the same everywhere.
PUBLIC_SUFFIX_LIST = BUILD_DIR / "publicsuffix" / "public_suffix_list.dat"

SLUG_RE = re.compile(r"(?=.{1,64}\Z)[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
_DOMAIN_LABEL = r"[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?"
_APP_LABEL = r"[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?"
FLATPAK_ID_RE = re.compile(
    rf"(?=.{{3,255}}\Z){_DOMAIN_LABEL}\.{_DOMAIN_LABEL}"
    rf"(?:\.{_APP_LABEL})+\Z"
)
# A SymbolCatalog name. Hyphens are legal there ("android-apps") and in the indexer's SLUG_RE
# (^[a-z0-9][a-z0-9-]{0,63}$); underscores are legal in neither, so the gate refuses them too.
GLYPH_RE = re.compile(r"(?=.{1,64}\Z)[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
BIN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
VERSION_RE = re.compile(r"[0-9][A-Za-z0-9._+-]{0,63}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
FINGERPRINT_RE = re.compile(r"[0-9A-F]{40}\Z")
ACCENT_RE = re.compile(r"#[0-9a-f]{6}\Z")
WM_CLASS_RE = re.compile(r"[A-Za-z0-9._ -]{1,80}\Z")
# A path inside an extracted download: plain segments only, no "..", no absolute path.
REL_PATH_RE = re.compile(r"(?=.{1,255}\Z)[A-Za-z0-9_@+][A-Za-z0-9._@+ -]*"
                         r"(?:/[A-Za-z0-9_@+][A-Za-z0-9._@+ -]*)*\Z")
# An Android application id. Two labels is legal and common (app.organicmaps),
# so this is deliberately looser than FLATPAK_ID_RE, which requires three.
ANDROID_PACKAGE_RE = re.compile(
    r"(?=.{3,255}\Z)[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+\Z")
ARABIC_LETTER_RE = re.compile(r"[ؠ-يٮ-ۓۺ-ۿ]")

ARCHES = ("aarch64", "x86_64")
MAX_DOWNLOAD = 4 * 1024 ** 3
# docs/MO_STORE.md: the twelve Store categories every surface and the web-app menu map share.
CATEGORY_IDS = {"ess", "comm", "work", "art", "media", "fun", "dev", "ai", "edu", "util",
                "droid", "win"}
TOP_LEVEL_KEYS = {"_comment", "categories", "collections", "featured", "bundles", "apps"}
APP_KEYS = {"id", "source", "cat", "glyph", "en", "ar", "desc_en", "desc_ar", "developer",
            "keywords_en", "keywords_ar", "accent", "icon_url", "arch", "engine", "popular",
            "preselect", "install"}
FREEDESKTOP_MAIN_CATEGORIES = {"AudioVideo", "Audio", "Video", "Development", "Education",
                               "Game", "Graphics", "Network", "Office", "Science", "Settings",
                               "System", "Utility"}

# Each kind's recipe: the risk label it must carry and exactly which keys it may hold. An
# unknown key is refused rather than ignored: a typo ("permission") would otherwise ship as a
# recipe that silently drops what its author meant.
KINDS = {
    "npm": {"risk": "runs-package-scripts", "required": {"kind", "pkg", "bin", "risk",
                                                         "requires_review"}, "optional": set()},
    "web": {"risk": "external-download", "required": {"kind", "url", "external", "risk",
                                                      "requires_review"}, "optional": set()},
    "webapp": {"risk": "web-app", "required": {"kind", "url", "hosts", "identity",
                                               "permissions", "accent", "risk",
                                               "requires_review"}, "optional": set()},
    "appdrop": {"risk": "downloaded-executable",
                "required": {"kind", "artifact", "version", "downloads", "risk",
                             "requires_review", "external"},
                "optional": {"desktop_id", "wm_class", "exec", "icon", "categories"}},
    "windows-portable": {"risk": "downloaded-executable",
                         "required": {"kind", "version", "downloads", "exe", "risk",
                                      "requires_review", "external"},
                         "optional": {"wm_class"}},
    "android": {"risk": "external-download",
                "required": {"kind", "url", "sha256", "size", "package", "signer", "risk",
                             "requires_review", "external"},
                "optional": {"version"}},
    "vendor-rpm": {"risk": "downloaded-executable",
                   "required": {"kind", "repo", "package", "key_fingerprint", "install_root",
                                "exec", "desktop", "wm_class", "risk", "requires_review",
                                "external"},
                   "optional": {"icon"}},
}
RETIRED_KINDS = {
    "appimage": "the bare-file appimage kind is retired: an AppImage is an appdrop recipe "
                "(artifact appimage) so it gets a launcher and a record",
}

# Web recipes open a human-facing page; they never name a package or executable. Exact hosts
# and exact page paths keep a compromised catalogue entry from turning `xdg-open` into a
# generic URL launcher. Empty on purpose: every program the catalogue used to send to a
# publisher page is now installable (or was removed), and an entry that only opens a page must
# say so in its description AND earn its page here.
WEB_PAGE_ALLOWLIST: dict[str, frozenset[str]] = {}
DIRECT_DOWNLOAD_SUFFIXES = (
    ".appimage", ".deb", ".rpm", ".exe", ".msi", ".dmg", ".pkg",
    ".tar", ".tar.gz", ".tgz", ".zip", ".apk",
)

# Npm is intentionally an exact recipe allowlist, not a package-name pattern.
# A catalog edit cannot substitute a similarly named package or swap the binary.
NPM_RECIPE_ALLOWLIST = {
    "claude-code": ("@anthropic-ai/claude-code", "claude"),
    "codex": ("@openai/codex", "codex"),
    "gemini-cli": ("@google/gemini-cli", "gemini"),
}

# Downloads are taken from the publisher, never mirrored by MoOS: each is the publisher's own
# HTTPS URL, pinned by exact size and SHA-256 and verified before anything runs. (Windows
# programs used to be "listed, never redistributed" as links to publisher pages; they are now
# downloaded the same way, from the same publishers, and still never mirrored.) Each rule is
# EXACT: one host and one path pattern per app, with the pinned version ({v}) and per-arch
# tokens ({a}, {b}) substituted, so a re-pin that changes the version but not the URL — or that
# swaps two architectures' URLs — fails here. Only what the catalogue uses is listed.
DOWNLOAD_RULES = {
    "photocraft": ("github.com",
                   r"/storytold/photocraft/releases/download/v{v}/photocraft-{v}-linux-{b}\.AppImage",
                   {"x86_64": ("", "x86_64"), "aarch64": ("", "aarch64")}),
    "lmstudio": ("installers.lmstudio.ai",
                 r"/linux/{a}/{v}/LM-Studio-{v}-{a}\.AppImage",
                 {"x86_64": ("x64", ""), "aarch64": ("arm64", "")}),
    "cursor": ("downloads.cursor.com",
               r"/production/[0-9a-f]{{40}}/linux/{a}/Cursor-{v}-{b}\.AppImage",
               {"x86_64": ("x64", "x86_64"), "aarch64": ("arm64", "aarch64")}),
    "antigravity": ("storage.googleapis.com",
                    r"/antigravity-public/antigravity-hub/{v}-[0-9]+/linux-{a}/Antigravity\.tar\.gz",
                    {"x86_64": ("x64", ""), "aarch64": ("arm", "")}),
    "antigravity-ide": ("edgedl.me.gvt1.com",
                        r"/edgedl/release2/j0qc3/antigravity/stable/{v}-[0-9]+/linux-{a}/"
                        r"Antigravity%20IDE\.tar\.gz",
                        {"x86_64": ("x64", ""), "aarch64": ("arm", "")}),
    "notepad-plus-plus": ("github.com",
                          r"/notepad-plus-plus/notepad-plus-plus/releases/download/v{v}/"
                          r"npp\.{v}\.portable\.x64\.zip",
                          {"x86_64": ("", "")}),
    "notepad3": ("github.com",
                 r"/rizonesoft/Notepad3/releases/download/RELEASE_{v}/Notepad3_{v}_x64_Portable\.zip",
                 {"x86_64": ("", "")}),
    "putty": ("the.earth.li", r"/~sgtatham/putty/{v}/w64/putty\.exe", {"x86_64": ("", "")}),
    "sumatrapdf": ("www.sumatrapdfreader.org", r"/dl/rel/{v}/SumatraPDF-{v}-64\.zip",
                   {"x86_64": ("", "")}),
    "winmerge": ("github.com",
                 r"/WinMerge/winmerge/releases/download/v{v}/winmerge-{v}-x64-exe\.zip",
                 {"x86_64": ("", "")}),
    "heidisql": ("github.com",
                 r"/HeidiSQL/HeidiSQL/releases/download/v{v}/HeidiSQL_{v}_64_Portable\.zip",
                 {"x86_64": ("", "")}),
}
# Android APKs come from the main F-Droid repository only, never a mirror: mirrors lag and drop
# old files, while f-droid.org keeps serving every file its signed index names.
ANDROID_HOST = "f-droid.org"

# Install-independent icons, used by the index before an app is installed and fetched only when
# the person allows app pictures from the internet. Publisher hosts only; a web app never has
# one (its own icon is captured from the site once it is installed).
ICON_HOSTS = {"f-droid.org", "raw.githubusercontent.com"}
ICON_RULES = {
    # app id -> (host, path pattern; {v} is the recipe's pinned version, so the icon follows
    # the exact tag that was reviewed)
    "photocraft": ("raw.githubusercontent.com",
                   r"/storytold/photocraft/v{v}/[A-Za-z0-9._@/-]+\.(?:png|svg)"),
}

# A vendor RPM is read from the publisher's own signed repository, never layered onto the
# image: its newest build, digest and size come from the repository metadata, `rpmkeys
# --checksig` must prove the trusted key signed it, and only `install_root` is unpacked into
# the person's home. Exact allowlist: repository -> (package, key fingerprint, key file).
# The key file must be one the image already trusts: build.sh imports it (build.sh, after the
# release-file scrub: `rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-openai-chatgpt`, line 97 on
# 2026-10-14) and so does build-arm.sh (line 207) for the aarch64 build.
VENDOR_RPM_ALLOWLIST = {
    "https://persistent.oaistatic.com/codex-app-prod/linux/rpm/$basearch": (
        "chatgpt", "3BFA0E4AE8B8CC16A2D9BA684A3B4A566C4660E4",
        "/etc/pki/rpm-gpg/RPM-GPG-KEY-openai-chatgpt"),
}
VENDOR_INSTALL_ROOT_RE = re.compile(r"/(?:usr/lib|opt)/[a-z0-9][a-z0-9._-]{0,63}\Z")
VENDOR_DESKTOP_RE = re.compile(r"/usr/share/applications/[A-Za-z0-9][A-Za-z0-9._-]{0,120}"
                               r"\.desktop\Z")

# Words MoOS's own voice never uses (descriptions, taglines, collection lines, search words):
# the machinery an app runs on, the store channel it came from, or another operating system.
# The platform an app comes FROM ("Windows programs", "Android apps") is fine; an app's own
# product name (Bottles, Lutris, F-Droid) is fine in `en`/`ar`.
MACHINERY_WORDS = (
    "wine", "bottles", "waydroid", "proton", "lutris", "qemu", "bubblewrap",
    "flatpak", "flatpaks", "appimage", "appimages", "wayland", "xwayland", "kwin", "plasma",
    "kde", "gnome", "chromium", "qtwebengine", "flathub", "f-droid", "fdroid",
    "فلاتباك", "فلات باك", "فلاتهب", "ويلاند", "بلازما", "كيدي", "جنوم", "إف-درويد",
    "اف-درويد", "واين", "وايدرويد",
)
FOREIGN_OS_WORDS = (
    "fedora", "red hat", "redhat", "rhel", "kinoite", "silverblue", "ubuntu", "debian",
    "فيدورا", "ريد هات", "أوبونتو", "اوبونتو", "ديبيان",
)
DESKTOP_WORDS = ("kde", "gnome", "plasma", "كيدي", "جنوم", "بلازما")


def _word_pattern(words):
    alternatives = "|".join(re.escape(word).replace(r"\ ", r"[\s-]*") for word in words)
    return re.compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])", re.IGNORECASE)


MACHINERY_RE = _word_pattern(MACHINERY_WORDS + FOREIGN_OS_WORDS)
FOREIGN_OS_RE = _word_pattern(FOREIGN_OS_WORDS)
DEVELOPER_RE = _word_pattern(FOREIGN_OS_WORDS + DESKTOP_WORDS)


class Report:
    def __init__(self):
        self.errors: list[str] = []

    def require(self, ok, message):
        if not ok:
            self.errors.append(message)


def read_root(root: Path, path: str) -> str:
    # In the image build the root is `/`. Developers run the identical gate against the tree
    # with MOOS_TEST_ROOT=<repo>/system_files.
    return (root / str(path).lstrip("/")).read_text(encoding="utf-8")


def code(raw, marker):
    """Drop whole-line comments (lines whose first non-space chars are `marker`).

    Trailing comments are left alone — the code token a gate looks for is still on
    the line — but a token sitting ALONE on a comment line cannot satisfy a gate.
    """
    return "\n".join(
        line for line in raw.splitlines() if not line.lstrip().startswith(marker)
    )


def has_control(value):
    """Reject C0/C1 controls while allowing Arabic shaping marks such as ZWNJ."""
    return any(unicodedata.category(ch) == "Cc" for ch in value)


def load_source_module(name: str, path: Path):
    """Import one of the image's Python files without writing bytecode beside it."""
    sys.dont_write_bytecode = True
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


def symbol_names(symbol_catalog_source: str) -> set[str]:
    body = re.search(r"var\s+symbolNames\s*=\s*\(\{(.*?)\}\)", symbol_catalog_source, re.DOTALL)
    if body is None:
        return set()
    return set(re.findall(r'"([a-z0-9-]+)"\s*:\s*true', body.group(1)))


def relative_luminance(colour: str) -> float:
    channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_with_white(colour: str) -> float:
    return 1.05 / (relative_luminance(colour) + 0.05)


def pgp_v4_fingerprint(armored: str) -> str:
    """The v4 fingerprint of the first public-key packet of an ASCII-armored key (RFC 4880)."""
    lines = [line.strip() for line in armored.strip().splitlines()]
    start = lines.index("-----BEGIN PGP PUBLIC KEY BLOCK-----")
    end = lines.index("-----END PGP PUBLIC KEY BLOCK-----")
    body = lines[start + 1:end]
    if "" in body:  # armor headers end at the first blank line
        body = body[body.index("") + 1:]
    raw = base64.b64decode("".join(line for line in body if not line.startswith("=")))
    head = raw[0]
    if not head & 0x80:
        raise ValueError("not an OpenPGP packet")
    if head & 0x40:
        tag, first = head & 0x3F, raw[1]
        if first < 192:
            length, offset = first, 2
        elif first < 224:
            length, offset = ((first - 192) << 8) + raw[2] + 192, 3
        elif first == 255:
            length, offset = int.from_bytes(raw[2:6], "big"), 6
        else:
            raise ValueError("partial-length key packet")
    else:
        tag, length_type = (head >> 2) & 0x0F, head & 0x03
        if length_type == 3:
            raise ValueError("indeterminate-length key packet")
        size = (1, 2, 4)[length_type]
        length, offset = int.from_bytes(raw[1:1 + size], "big"), 1 + size
    if tag != 6:
        raise ValueError(f"first packet is tag {tag}, not a public key")
    packet = raw[offset:offset + length]
    if not packet or packet[0] != 4:
        raise ValueError(f"key packet version {packet[:1].hex()} is not v4")
    digest = hashlib.sha1(b"\x99" + len(packet).to_bytes(2, "big") + packet,
                          usedforsecurity=False)
    return digest.hexdigest().upper()


class PublicSuffixes:
    """The Public Suffix List's rules, matched by the algorithm https://publicsuffix.org/list/
    specifies: the longest matching rule prevails, an exception rule beats it and gives up its
    leftmost label, and with no match the last label alone is the suffix (the rule "*")."""

    def __init__(self, text: str) -> None:
        self.rules: set[str] = set()
        self.exceptions: set[str] = set()
        for line in text.splitlines():
            words = line.split()   # a rule is read up to its first whitespace
            if not words or words[0].startswith("//"):
                continue
            rule = words[0]
            labels = [self.ascii_label(label) for label in rule.lstrip("!").split(".")]
            # Every rule today is a name or a leftmost "*."; any other shape is a list this code
            # would misread, so it is refused rather than half understood.
            if "" in labels or "*" in labels[1:]:
                raise ValueError(f"unexpected rule shape {rule!r}")
            (self.exceptions if rule.startswith("!") else self.rules).add(".".join(labels))
        if len(self.rules) < 5000 or not {"com", "co.uk", "github.io"} <= self.rules:
            raise ValueError(f"only {len(self.rules)} rules, or not ones every copy has: the "
                             "list is truncated or not the Public Suffix List")

    @staticmethod
    def ascii_label(label: str) -> str:
        """Hosts in the catalogue are ASCII, so an internationalised rule is compared as the
        A-label its domain is registered under (xn--…)."""
        label = label.lower()
        return label if label.isascii() else "xn--" + label.encode("punycode").decode("ascii")

    def public_suffix(self, name: str) -> str:
        labels = name.lower().rstrip(".").split(".")
        for start in range(len(labels)):
            if ".".join(labels[start:]) in self.exceptions:
                return ".".join(labels[start + 1:])
        for start in range(len(labels)):
            candidate = ".".join(labels[start:])
            wildcard = ".".join(["*", *labels[start + 1:]])
            if candidate in self.rules or (start + 1 < len(labels) and wildcard in self.rules):
                return candidate
        return labels[-1]

    def is_public_suffix(self, name: str) -> bool:
        return self.public_suffix(name) == name.lower().rstrip(".")

    def rules_under(self, name: str) -> list[str]:
        """Rules strictly inside `name`: below each, sites belong to different owners again."""
        tail = "." + name.lower().rstrip(".")
        return sorted(rule for rule in self.rules if rule.endswith(tail))


@functools.lru_cache(maxsize=4)
def load_public_suffixes(path: Path) -> PublicSuffixes:
    return PublicSuffixes(Path(path).read_text(encoding="utf-8"))


def public_suffix_problem(pattern: str, suffixes: PublicSuffixes) -> str | None:
    """Why a web app host pattern would keep other people's sites inside the app's window."""
    wildcard = pattern.startswith("*.")
    base = pattern[2:] if wildcard else pattern
    if suffixes.is_public_suffix(base):
        if wildcard:
            return (f"{pattern!r} covers every site under the public suffix {base!r}; each of "
                    "them is someone else's")
        return f"{pattern!r} is a public suffix, the name other people's sites live under"
    under = suffixes.rules_under(base) if wildcard else []
    if under:
        return (f"{pattern!r} spans sites of different owners: the Public Suffix List's rule "
                f"{under[0]!r} lies inside it")
    return None


# ── the catalogue ─────────────────────────────────────────────────────────────────────────────
def check_catalog(catalog, root: Path = IMAGE_ROOT, build_dir: Path = BUILD_DIR,
                  catalog_path: Path | None = None) -> tuple[Report, dict]:
    """Validate the catalogue itself. Returns the report and facts the chain check needs."""
    report = Report()
    require = report.require
    facts = {"used_kinds": set(), "risks": set(), "bundle_ids": set(), "app_ids": set(),
             "has_flathub": False, "kinds": {}}

    def walk_strings(value, where="$"):
        """Reject control characters anywhere, including future schema fields."""
        if isinstance(value, str):
            bad = next((ch for ch in value if unicodedata.category(ch) == "Cc"), None)
            if bad is not None:
                require(False, f"{where} contains forbidden control character U+{ord(bad):04X}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk_strings(child, f"{where}[{index}]")
        elif isinstance(value, dict):
            for key, child in value.items():
                require(key not in {"rating", "reviews"},
                        f"{where} contains manual {key!r}; the catalog has no verified "
                        "ratings/review source")
                walk_strings(key, f"{where}.<key>")
                walk_strings(child, f"{where}.{key}")

    def clean_text(value, label, pattern=None):
        ok = isinstance(value, str) and bool(value) and value == value.strip()
        require(ok, f"{label} must be a non-empty canonical string")
        if not ok:
            return ""
        require(not has_control(value), f"{label} contains a control character")
        if pattern is not None:
            require(bool(pattern.fullmatch(value)), f"{label} is not canonical: {value!r}")
        return value

    def required_text(obj, field, label, pattern=None):
        return clean_text(obj.get(field), f"{label}.{field}", pattern)

    def add_unique(value, seen, label):
        if not value:
            return
        require(value not in seen, f"duplicate {label} id: {value!r}")
        seen.add(value)

    def checked_https_url(raw, label):
        value = clean_text(raw, label)
        if not value:
            return None
        require("\\" not in value, f"{label} contains a backslash/path ambiguity")
        require(not any(ch.isspace() for ch in value), f"{label} contains whitespace")
        try:
            parts = urlsplit(value)
            host = parts.hostname
            port = parts.port
        except ValueError as exc:
            require(False, f"{label} is not a valid URL: {exc}")
            return None
        require(parts.scheme == "https", f"{label} must use HTTPS")
        require(bool(host), f"{label} has no hostname")
        require(parts.username is None and parts.password is None,
                f"{label} must not contain URL credentials")
        require(port is None, f"{label} must not contain an explicit port")
        require(parts.netloc == host, f"{label} hostname must use canonical lowercase form")
        require(not parts.query and not parts.fragment,
                f"{label} must not carry a query or fragment")
        return parts

    def require_review_metadata(inst, label, risk):
        require(inst.get("risk") == risk, f"{label}.risk must be {risk!r}")
        require(inst.get("requires_review") is True, f"{label}.requires_review must be true")

    def validate_basename(value, label):
        name = clean_text(value, label, BIN_RE)
        if name:
            require(name not in {".", ".."}, f"{label} must be a basename, not a path")
            require("/" not in name and "\\" not in name, f"{label} must be a basename, not a path")
        return name

    def relative_path(value, label):
        path = clean_text(value, label)
        if path:
            require(bool(REL_PATH_RE.fullmatch(path)) and ".." not in path.split("/")
                    and "." not in path.split("/"),
                    f"{label} must be a relative path inside the download, without '..' "
                    f"or a leading '/': {path!r}")
        return path

    def text_rules(value, label, *, arabic, limit, sentence=False, words=MACHINERY_RE):
        """Bilingual copy: the right script, bounded, one sentence, never machinery."""
        if not isinstance(value, str) or not value:
            return
        has_arabic = bool(ARABIC_LETTER_RE.search(value))
        if arabic:
            require(has_arabic, f"{label} must be written in Arabic: {value!r}")
        else:
            require(not has_arabic, f"{label} must not contain Arabic letters: {value!r}")
        require(len(value) <= limit, f"{label} is {len(value)} characters; the limit is {limit}")
        if sentence:
            require(value.endswith("."), f"{label} must end with a full stop: {value!r}")
            require(re.search(r"[.!?؟](?=\s)", value[:-1]) is None,
                    f"{label} must be one sentence: {value!r}")
        if words is not None:
            hit = words.search(value)
            require(hit is None, f"{label} names machinery or another system "
                                 f"({hit.group(0) if hit else ''!r}); MoOS never says it")

    def accent_rule(value, label, minimum):
        accent = clean_text(value, label, ACCENT_RE)
        if accent:
            ratio = contrast_with_white(accent)
            require(ratio >= minimum,
                    f"{label} {accent} reaches only {ratio:.2f}:1 against white text; "
                    f"it needs {minimum}:1")
        return accent

    if not isinstance(catalog, dict):
        require(False, "the catalog root must be a JSON object")
        return report, facts
    walk_strings(catalog)
    for key in catalog:
        require(key in TOP_LEVEL_KEYS, f"catalog has unknown top-level key {key!r}")
    if "_comment" in catalog:
        require(isinstance(catalog["_comment"], str), "catalog._comment must be text")

    def section(name):
        value = catalog.get(name)
        require(isinstance(value, list), f"catalog.{name} must be an array")
        return value if isinstance(value, list) else []

    cats = section("categories")
    apps = section("apps")
    bundles = section("bundles")
    collections = section("collections")
    featured = section("featured")
    require(len(cats) > 0, "the catalog has no categories")
    require(len(apps) > 0, "the catalog has no apps")

    try:
        symbols = symbol_names(code(read_root(root, SYMBOL_CATALOG), "//"))
    except OSError as error:
        symbols = set()
        require(False, f"cannot read the SymbolCatalog: {error}")
    require(bool(symbols), "could not read any glyph names from the SymbolCatalog")

    def glyph_rule(obj, label):
        glyph = required_text(obj, "glyph", label, GLYPH_RE)
        if glyph and symbols:
            require(glyph in symbols,
                    f"{label}.glyph {glyph!r} is not a SymbolCatalog name; the Store would "
                    "silently draw the spark fallback instead")
        return glyph

    # ── categories: exactly the contract's twelve ──────────────────────────────────────────
    cat_ids = set()
    for index, category in enumerate(cats):
        label = f"category[{index}]"
        require(isinstance(category, dict), f"{label} must be an object")
        if not isinstance(category, dict):
            continue
        cid = required_text(category, "id", label, SLUG_RE)
        add_unique(cid, cat_ids, "category")
        text_rules(required_text(category, "en", label), f"{label}.en", arabic=False, limit=40)
        text_rules(required_text(category, "ar", label), f"{label}.ar", arabic=True, limit=40)
        glyph_rule(category, label)
    require(cat_ids == CATEGORY_IDS,
            f"the categories must be exactly docs/MO_STORE.md's {sorted(CATEGORY_IDS)}; "
            f"missing {sorted(CATEGORY_IDS - cat_ids)}, unknown {sorted(cat_ids - CATEGORY_IDS)}")

    # ── apps ────────────────────────────────────────────────────────────────────────────────
    app_ids = set()
    names_en: dict[str, str] = {}
    names_ar: dict[str, str] = {}
    by_id: dict[str, dict] = {}
    policy = None
    suffixes = None
    for index, app in enumerate(apps):
        label = f"app[{index}]"
        require(isinstance(app, dict), f"{label} must be an object")
        if not isinstance(app, dict):
            continue
        for key in app:
            require(key in APP_KEYS, f"{label} has unknown key {key!r}")

        source = required_text(app, "source", label)
        inst = app.get("install")
        kind_hint = inst.get("kind") if isinstance(inst, dict) else None
        # A MoOS-curated entry is a slug — EXCEPT an Android one, whose identity is
        # its package id, dots and all. The android block below then requires
        # install.package to equal it, so the catalogue and the container cannot
        # drift apart into naming two different things.
        if source == "flathub":
            aid_pattern = FLATPAK_ID_RE
        elif kind_hint == "android":
            aid_pattern = ANDROID_PACKAGE_RE
        else:
            aid_pattern = SLUG_RE
        aid = required_text(app, "id", label, aid_pattern)
        add_unique(aid, app_ids, "app")
        if aid:
            by_id[aid] = app
        label = f"app {aid or index}"
        category = required_text(app, "cat", label, SLUG_RE)
        require(category in cat_ids, f"{label} references undefined category {category!r}")
        glyph_rule(app, label)

        en = required_text(app, "en", label)
        ar = required_text(app, "ar", label)
        text_rules(en, f"{label}.en", arabic=False, limit=48, words=FOREIGN_OS_RE)
        text_rules(ar, f"{label}.ar", arabic=True, limit=48, words=FOREIGN_OS_RE)
        for value, seen, which in ((en, names_en, "en"), (ar, names_ar, "ar")):
            if value:
                folded = value.casefold()
                require(folded not in seen,
                        f"{label}.{which} {value!r} is also the name of {seen.get(folded)}; "
                        "two cards with one name are one confused person")
                seen.setdefault(folded, aid)
        text_rules(required_text(app, "desc_en", label), f"{label}.desc_en", arabic=False,
                   limit=140, sentence=True)
        text_rules(required_text(app, "desc_ar", label), f"{label}.desc_ar", arabic=True,
                   limit=140, sentence=True)
        developer = required_text(app, "developer", label)
        require(len(developer) <= 80, f"{label}.developer is longer than 80 characters")
        hit = DEVELOPER_RE.search(developer)
        require(hit is None, f"{label}.developer names another system or desktop "
                             f"({hit.group(0) if hit else ''!r}); name the app's own makers")
        for field, arabic in (("keywords_en", False), ("keywords_ar", True)):
            if field not in app:
                continue
            words = app[field]
            ok = isinstance(words, list) and 1 <= len(words) <= 12
            require(ok, f"{label}.{field} must be a list of 1 to 12 search words")
            if not ok:
                continue
            seen_words = set()
            for position, word in enumerate(words):
                where = f"{label}.{field}[{position}]"
                word = clean_text(word, where)
                if not word:
                    continue
                text_rules(word, where, arabic=arabic, limit=32)
                require(word.casefold() not in seen_words, f"{where} repeats {word!r}")
                seen_words.add(word.casefold())
        for boolean_field in ("popular", "preselect"):
            if boolean_field in app:
                require(isinstance(app[boolean_field], bool),
                        f"{label}.{boolean_field} must be boolean")
        arch = app.get("arch")
        if arch is not None:
            require(isinstance(arch, list) and bool(arch)
                    and all(item in ARCHES for item in arch) and len(set(arch)) == len(arch),
                    f"{label}.arch must be a non-empty list drawn from {list(ARCHES)}")
        engine = app.get("engine")
        if engine is not None:
            require(engine in {"windows", "android"},
                    f"{label}.engine must be 'windows' or 'android', not {engine!r}")
        if "accent" in app:
            accent_rule(app["accent"], f"{label}.accent", 3.0)

        require(source in {"flathub", "moos"}, f"{label} has unknown source {source!r}")
        if app.get("preselect") is True:
            require(source == "flathub",
                    f"preselected app {aid or '?'} must be a sandboxed Flatpak; "
                    "advanced recipes always require an explicit user choice")
            # Welcome preselects from the raw catalogue on every machine, so a preselected
            # app that exists on one architecture is a dead tick on the other.
            require(arch is None,
                    f"preselected app {aid or '?'} must run on every architecture")
        if source == "flathub":
            facts["has_flathub"] = True
            require("install" not in app,
                    f"Flathub app {aid or '?'} must not carry a second install recipe")
            require(engine is None, f"Flathub app {aid or '?'} must not declare an engine")
            require("icon_url" not in app,
                    f"Flathub app {aid or '?'} must not carry icon_url; AppStream has its icon")
            continue
        if source != "moos":
            continue

        require("accent" in app,
                f"MoOS app {aid or '?'} needs an accent: it has no AppStream branding colour")
        require(isinstance(inst, dict), f"MoOS app {aid or '?'} needs install object")
        if not isinstance(inst, dict):
            continue
        kind = required_text(inst, "kind", f"{label}.install")
        if kind in RETIRED_KINDS:
            require(False, f"{label} uses retired install kind {kind!r}: {RETIRED_KINDS[kind]}")
            continue
        require(kind in KINDS, f"{label} has unknown install kind {kind!r}")
        if kind not in KINDS:
            continue
        facts["used_kinds"].add(kind)
        facts["kinds"][aid] = kind
        spec = KINDS[kind]
        present = set(inst)
        missing = spec["required"] - present
        unknown = present - spec["required"] - spec["optional"]
        require(not missing, f"{label}.install ({kind}) is missing {sorted(missing)}")
        require(not unknown, f"{label}.install ({kind}) has unknown keys {sorted(unknown)}")
        require_review_metadata(inst, f"{label}.install", spec["risk"])
        facts["risks"].add(spec["risk"])
        if "external" in inst:
            require(inst.get("external") is True,
                    f"{label}.install.external must be true")

        # Platform consistency: what a card says it is, is what it installs.
        if kind == "windows-portable":
            require(engine == "windows" and category == "win" and arch == ["x86_64"],
                    f"{label}: a Windows program needs engine 'windows', cat 'win' and "
                    "arch ['x86_64'] (64-bit programs only)")
        else:
            require(category != "win" and engine != "windows",
                    f"{label}: only a windows-portable recipe belongs to Windows programs")
        if kind == "android":
            require(engine == "android" and category == "droid",
                    f"{label}: an Android app needs engine 'android' and cat 'droid'")
        else:
            require(category != "droid" and engine != "android",
                    f"{label}: only an android recipe belongs to Android apps")
        if kind in {"appdrop", "vendor-rpm"}:
            require(arch is not None,
                    f"{label}: a {kind} recipe must say which architectures it exists for")

        icon_url = app.get("icon_url")
        if icon_url is not None:
            parts = checked_https_url(icon_url, f"{label}.icon_url")
            require(kind != "webapp",
                    f"{label}: a web app takes its icon from its own site once installed; "
                    "it must not carry icon_url")
            if parts is not None and parts.hostname:
                require(parts.hostname in ICON_HOSTS,
                        f"{label}.icon_url host {parts.hostname!r} is not an allowlisted "
                        "publisher host")
                if kind == "android" and aid:
                    require(parts.hostname == ANDROID_HOST and re.fullmatch(
                        rf"/repo/{re.escape(aid)}/[A-Za-z-]+/icon_[A-Za-z0-9_=-]+\.png",
                        parts.path) is not None,
                        f"{label}.icon_url must be the signed index's own icon for {aid}")
                elif kind != "android":
                    rule = ICON_RULES.get(aid)
                    version = inst.get("version") if isinstance(inst.get("version"), str) else ""
                    require(rule is not None and parts.hostname == rule[0] and version and
                            re.fullmatch(rule[1].format(v=re.escape(version)), parts.path),
                            f"{label}.icon_url is not the publisher icon allowed for {aid} at "
                            "its pinned version")

        if kind == "npm":
            pkg = required_text(inst, "pkg", f"{label}.install")
            binary = validate_basename(inst.get("bin"), f"{label}.install.bin")
            expected = NPM_RECIPE_ALLOWLIST.get(aid)
            require(expected is not None,
                    f"npm app {aid or '?'} is not in the exact recipe allowlist")
            if expected is not None:
                require((pkg, binary) == expected,
                        f"npm app {aid} must use exact recipe pkg={expected[0]!r}, "
                        f"bin={expected[1]!r}")

        elif kind == "web":
            parts = checked_https_url(inst.get("url"), f"{label}.install.url")
            require(re.search(r"publisher's page", str(app.get("desc_en", "")), re.I) is not None
                    and "صفحة الناشر" in str(app.get("desc_ar", "")),
                    f"web recipe {aid or '?'} only opens a publisher page, so its descriptions "
                    "must say so (\"publisher's page\" / \"صفحة الناشر\")")
            if parts is not None and parts.hostname:
                allowed_paths = WEB_PAGE_ALLOWLIST.get(parts.hostname)
                require(allowed_paths is not None,
                        f"web recipe {aid or '?'} uses non-allowlisted domain {parts.hostname!r}")
                decoded_path = unquote(parts.path)
                if allowed_paths is not None:
                    require(decoded_path in allowed_paths,
                            f"web recipe {aid or '?'} uses non-allowlisted page path "
                            f"{decoded_path!r}")
                require(not decoded_path.lower().endswith(DIRECT_DOWNLOAD_SUFFIXES),
                        f"web recipe {aid or '?'} points directly to an executable/archive")

        elif kind == "webapp":
            checked_https_url(inst.get("url"), f"{label}.install.url")
            require(inst.get("accent") == app.get("accent"),
                    f"{label}: install.accent must equal the app's accent, so the launcher "
                    "tile and the Store card agree")
            if policy is None:
                try:
                    policy = load_source_module("moos_webapp_policy_for_gate",
                                                root / WEBAPP_POLICY.lstrip("/"))
                except (OSError, ImportError, SyntaxError) as error:
                    policy = False
                    require(False, f"cannot load the web-app policy {WEBAPP_POLICY}: {error}")
            if policy:
                try:
                    policy.parse_entry(app)
                except policy.WebAppError as error:
                    require(False, f"{label} is refused by moos_webapp_policy: {error}")
            # The policy keeps every address on these hosts inside a window with no address bar
            # and answers their permission requests with the person's decisions for this app.
            if suffixes is None:
                try:
                    suffixes = load_public_suffixes(PUBLIC_SUFFIX_LIST)
                except (OSError, UnicodeError, ValueError) as error:
                    suffixes = False
                    require(False, f"cannot read the Public Suffix List {PUBLIC_SUFFIX_LIST}: "
                                   f"{error}; no web app host can be checked without it")
            hosts = inst.get("hosts")
            if suffixes and isinstance(hosts, list):
                for host in hosts:
                    problem = public_suffix_problem(host.lower(), suffixes) \
                        if isinstance(host, str) else None
                    require(problem is None, f"{label}.install.hosts {problem}: the app window "
                                             "would keep their pages inside it, with no address "
                                             "bar and this app's permissions")

        elif kind in {"appdrop", "windows-portable"}:
            version = required_text(inst, "version", f"{label}.install", VERSION_RE)
            downloads = inst.get("downloads")
            ok = isinstance(downloads, dict) and bool(downloads)
            require(ok, f"{label}.install.downloads must be a non-empty object")
            if ok:
                keys = sorted(downloads)
                require(all(key in ARCHES for key in keys),
                        f"{label}.install.downloads keys must be from {list(ARCHES)}")
                if kind == "appdrop":
                    require(arch == keys, f"{label}.arch must equal the sorted download "
                                          f"architectures {keys}")
                else:
                    require(keys == ["x86_64"],
                            f"{label}: a Windows program is pinned for x86_64 only")
                rule = DOWNLOAD_RULES.get(aid)
                require(rule is not None,
                        f"{label} has no exact download rule; add its publisher host and path")
                digests = []
                for arch_key, item in downloads.items():
                    where = f"{label}.install.downloads.{arch_key}"
                    if not isinstance(item, dict):
                        require(False, f"{where} must be an object")
                        continue
                    require(set(item) == {"url", "sha256", "size"},
                            f"{where} must hold exactly url, sha256 and size")
                    parts = checked_https_url(item.get("url"), f"{where}.url")
                    digest = required_text(item, "sha256", where, SHA256_RE)
                    digests.append(digest)
                    size = item.get("size")
                    require(type(size) is int and 0 < size <= MAX_DOWNLOAD,
                            f"{where}.size must be an integer byte count in (0, 4 GiB]")
                    if parts is None or rule is None or not version:
                        continue
                    tokens = rule[2].get(arch_key)
                    require(tokens is not None, f"{where}: no download rule for {arch_key}")
                    if tokens is None:
                        continue
                    pattern = rule[1].format(v=re.escape(version), a=re.escape(tokens[0]),
                                             b=re.escape(tokens[1]))
                    require(parts.hostname == rule[0] and re.fullmatch(pattern, parts.path),
                            f"{where}.url is not the publisher's {arch_key} download for "
                            f"version {version}: {item.get('url')!r}")
                require(len(set(digests)) == len(digests),
                        f"{label}: two architectures pin the same SHA-256 — a copied entry")
            if kind == "appdrop":
                artifact = inst.get("artifact")
                require(artifact in {"appimage", "archive"},
                        f"{label}.install.artifact must be 'appimage' or 'archive'")
                if artifact == "archive":
                    require("exec" in inst,
                            f"{label}: an archive must name its program (install.exec)")
                else:
                    require("exec" not in inst and "icon" not in inst,
                            f"{label}: an AppImage starts through its own AppRun; exec and "
                            "icon belong to archives")
                if "exec" in inst:
                    relative_path(inst["exec"], f"{label}.install.exec")
                if "icon" in inst:
                    icon = relative_path(inst["icon"], f"{label}.install.icon")
                    require(icon.lower().endswith((".png", ".svg")),
                            f"{label}.install.icon must be a .png or .svg file")
                if "desktop_id" in inst:
                    desktop_id = clean_text(inst["desktop_id"], f"{label}.install.desktop_id",
                                            FLATPAK_ID_RE)
                    require(not desktop_id.startswith("org.moos."),
                            f"{label}.install.desktop_id must never shadow a MoOS launcher")
                if "categories" in inst:
                    menu = inst["categories"]
                    require(isinstance(menu, list) and bool(menu) and len(set(menu)) == len(menu)
                            and all(item in FREEDESKTOP_MAIN_CATEGORIES for item in menu),
                            f"{label}.install.categories must be freedesktop main categories")
            else:
                exe = relative_path(inst.get("exe"), f"{label}.install.exe")
                require(exe.lower().endswith(".exe"), f"{label}.install.exe must be a .exe file")
                item = downloads.get("x86_64") if isinstance(downloads, dict) else None
                url = item.get("url") if isinstance(item, dict) else None
                if isinstance(url, str):
                    path = urlsplit(url).path
                    if path.lower().endswith(".exe"):
                        require(exe == unquote(path.rsplit("/", 1)[-1]),
                                f"{label}: a single-file download's exe is its own file name")
                    else:
                        require(path.lower().endswith(".zip"),
                                f"{label}: a Windows program arrives as one .exe or a .zip")
            if "wm_class" in inst:
                clean_text(inst["wm_class"], f"{label}.install.wm_class", WM_CLASS_RE)

        elif kind == "android":
            # Held to the same standard as every download: https from the main repository only,
            # an exact SHA-256 and size verified before anything reaches the container, the
            # signer Android will hold every later update to, and a package id the container
            # will actually accept. An entry that is not pinned is refused here rather than
            # downloaded and discovered later.
            parts = checked_https_url(inst.get("url"), f"{label}.install.url")
            required_text(inst, "sha256", f"{label}.install", SHA256_RE)
            signer = required_text(inst, "signer", f"{label}.install", SHA256_RE)
            package = required_text(inst, "package", f"{label}.install", ANDROID_PACKAGE_RE)
            require(package == aid,
                    f"Android recipe {aid or '?'} must use its package id as the app id, "
                    f"so the catalogue and the container name the same thing")
            size = inst.get("size")
            require(type(size) is int and 0 < size <= MAX_DOWNLOAD,
                    f"{label}.install.size must be an integer byte count in (0, 4 GiB]")
            if "version" in inst:
                required_text(inst, "version", f"{label}.install", VERSION_RE)
            if parts is not None and package:
                match = re.fullmatch(rf"/repo/{re.escape(package)}_([0-9]+)(?:_([0-9a-f]{{7}}))?"
                                     r"\.apk", parts.path)
                require(parts.hostname == ANDROID_HOST and match is not None,
                        f"{label}.install.url must be {package}'s own file in "
                        f"https://{ANDROID_HOST}/repo/")
                # A developer-signed build is published as <package>_<code>_<signer prefix>.apk;
                # pinning that file with another signer is a copy-paste error that Android
                # turns into a refused update one day.
                if match is not None and match.group(2) and signer:
                    require(signer.startswith(match.group(2)),
                            f"{label}: the file is signed by {match.group(2)}…, but the recipe "
                            f"records signer {signer[:7]}…")

        elif kind == "vendor-rpm":
            repo = required_text(inst, "repo", f"{label}.install")
            allowed = VENDOR_RPM_ALLOWLIST.get(repo)
            require(allowed is not None,
                    f"{label}.install.repo {repo!r} is not an allowlisted vendor repository")
            package = required_text(inst, "package", f"{label}.install", BIN_RE)
            fingerprint = required_text(inst, "key_fingerprint", f"{label}.install",
                                        FINGERPRINT_RE)
            if allowed is not None:
                require(package == allowed[0],
                        f"{label}: repository {repo} is allowlisted for package {allowed[0]!r} "
                        f"only")
                require(fingerprint == allowed[1],
                        f"{label}: repository {repo} is signed by {allowed[1]}, not "
                        f"{fingerprint}")
                try:
                    actual = pgp_v4_fingerprint(read_root(root, allowed[2]))
                except (OSError, ValueError, IndexError) as error:
                    actual = None
                    require(False, f"{label}: cannot read the trusted key {allowed[2]}: {error}")
                if actual is not None:
                    require(actual == allowed[1],
                            f"{label}: {allowed[2]} has fingerprint {actual}, not {allowed[1]}")
                import_line = f"rpm --import {allowed[2]}"
                scripts = ["build.sh"] + (["build-arm.sh"] if "aarch64" in (arch or []) else [])
                for script in scripts:
                    try:
                        source = code((build_dir / script).read_text(encoding="utf-8"), "#")
                    except OSError as error:
                        require(False, f"{label}: cannot read {script}: {error}")
                        continue
                    require(re.search(rf"^\s*{re.escape(import_line)}\s*$", source,
                                      re.MULTILINE) is not None,
                            f"{label}: {script} does not trust {allowed[2]} "
                            f"(`{import_line}`); the helper could never verify this package")
            install_root = required_text(inst, "install_root", f"{label}.install",
                                         VENDOR_INSTALL_ROOT_RE)
            require(not install_root.endswith("/"), f"{label}.install.install_root is not "
                                                    "canonical")
            relative_path(inst.get("exec"), f"{label}.install.exec")
            required_text(inst, "desktop", f"{label}.install", VENDOR_DESKTOP_RE)
            if "icon" in inst:
                icon = relative_path(inst["icon"], f"{label}.install.icon")
                require(icon.lower().endswith((".png", ".svg")),
                        f"{label}.install.icon must be a .png or .svg file")
            clean_text(inst.get("wm_class"), f"{label}.install.wm_class", WM_CLASS_RE)

    facts["app_ids"] = app_ids

    # ── the index and the gate must agree on what a valid entry is ─────────────────────────
    if catalog_path is not None:
        try:
            indexer = load_source_module("moos_store_index_for_gate",
                                         root / MOOS_STORE_INDEX.lstrip("/"))
            for arch_name in ARCHES:
                loaded = indexer.load_catalog(catalog_path, arch_name)
                # The indexer skips a bad entry (and logs why) instead of failing the whole index,
                # so a refusal is only visible here: an entry it skips is an app that silently
                # disappears from the Store.
                for skipped in (loaded.get("skipped") or []) if isinstance(loaded, dict) else []:
                    require(False, f"moos-store-index refuses the catalogue {skipped.get('section')} "
                                   f"entry {skipped.get('id')} on {arch_name}: {skipped.get('reason')}")
        except (OSError, ImportError, SyntaxError, AttributeError) as error:
            require(False, f"cannot load moos-store-index to cross-check the catalogue: {error}")
        except Exception as error:  # noqa: BLE001 - CatalogError and anything it raises
            require(False, f"moos-store-index refuses the catalogue (the whole Store index "
                           f"would fail to build): {error}")

    # ── collections: the Discover rows ─────────────────────────────────────────────────────
    collection_ids = set()
    for index, row in enumerate(collections):
        label = f"collection[{index}]"
        require(isinstance(row, dict), f"{label} must be an object")
        if not isinstance(row, dict):
            continue
        for key in row:
            require(key in {"id", "en", "ar", "glyph", "desc_en", "desc_ar", "apps"},
                    f"{label} has unknown key {key!r}")
        cid = required_text(row, "id", label, SLUG_RE)
        add_unique(cid, collection_ids, "collection")
        label = f"collection {cid or index}"
        text_rules(required_text(row, "en", label), f"{label}.en", arabic=False, limit=48)
        text_rules(required_text(row, "ar", label), f"{label}.ar", arabic=True, limit=48)
        glyph_rule(row, label)
        require(("desc_en" in row) == ("desc_ar" in row),
                f"{label} must describe itself in both languages or in neither")
        for field, arabic in (("desc_en", False), ("desc_ar", True)):
            if field in row:
                text_rules(required_text(row, field, label), f"{label}.{field}", arabic=arabic,
                           limit=140, sentence=True)
        members = row.get("apps")
        ok = isinstance(members, list) and 4 <= len(members) <= 24
        require(ok, f"{label}.apps must list 4 to 24 apps")
        if ok:
            require(len(set(map(str, members))) == len(members), f"{label} repeats an app")
            for member in members:
                require(isinstance(member, str) and member in app_ids,
                        f"{label} references undefined app {member!r}")

    # ── featured: the Discover hero cards ──────────────────────────────────────────────────
    require(3 <= len(featured) <= 8, "catalog.featured must hold 3 to 8 hero cards")
    seen_featured = set()
    everywhere = 0
    for index, card in enumerate(featured):
        label = f"featured[{index}]"
        require(isinstance(card, dict), f"{label} must be an object")
        if not isinstance(card, dict):
            continue
        for key in card:
            require(key in {"app", "title_en", "title_ar", "tagline_en", "tagline_ar", "accent"},
                    f"{label} has unknown key {key!r}")
        target = required_text(card, "app", label)
        require(target in app_ids, f"{label} features undefined app {target!r}")
        require(target not in seen_featured, f"{label} features {target!r} twice")
        seen_featured.add(target)
        text_rules(required_text(card, "title_en", label), f"{label}.title_en", arabic=False,
                   limit=40)
        text_rules(required_text(card, "title_ar", label), f"{label}.title_ar", arabic=True,
                   limit=40)
        text_rules(required_text(card, "tagline_en", label), f"{label}.tagline_en",
                   arabic=False, limit=100, sentence=True)
        text_rules(required_text(card, "tagline_ar", label), f"{label}.tagline_ar",
                   arabic=True, limit=100, sentence=True)
        if "accent" in card:
            accent_rule(card["accent"], f"{label}.accent", 4.5)
        app = by_id.get(target, {})
        arch = app.get("arch")
        if (arch is None or "aarch64" in arch) and not app.get("engine"):
            everywhere += 1
    require(everywhere >= 3,
            "at least three hero cards must feature apps that run on every edition (aarch64, "
            "no engine), or an ARM Discover page has no hero")

    # ── bundles only reference apps that exist, and only Flatpaks ──────────────────────────
    bundle_ids = set()
    for index, bundle in enumerate(bundles):
        label = f"bundle[{index}]"
        require(isinstance(bundle, dict), f"{label} must be an object")
        if not isinstance(bundle, dict):
            continue
        bid = required_text(bundle, "id", label, SLUG_RE)
        add_unique(bid, bundle_ids, "bundle")
        required_text(bundle, "en", label)
        required_text(bundle, "ar", label)
        glyph_rule(bundle, label)
        text_rules(required_text(bundle, "desc_en", label), f"{label}.desc_en", arabic=False,
                   limit=140, sentence=True)
        text_rules(required_text(bundle, "desc_ar", label), f"{label}.desc_ar", arabic=True,
                   limit=140, sentence=True)
        refs = bundle.get("apps")
        require(isinstance(refs, list) and bool(refs), f"{label}.apps must be a non-empty array")
        if not isinstance(refs, list):
            continue
        seen_refs = set()
        for ref_index, ref in enumerate(refs):
            ref_label = f"{label}.apps[{ref_index}]"
            canonical = clean_text(ref, ref_label)
            require(
                bool(SLUG_RE.fullmatch(canonical) or FLATPAK_ID_RE.fullmatch(canonical)
                     or ANDROID_PACKAGE_RE.fullmatch(canonical)) if canonical else False,
                f"{ref_label} is not a canonical app id",
            )
            require(canonical not in seen_refs, f"bundle {bid or '?'} repeats app {canonical!r}")
            if canonical:
                seen_refs.add(canonical)
            require(canonical in app_ids,
                    f"bundle {bid or '?'} references undefined app {canonical!r}")
            # One click installs a whole bundle, so it may only hold sandboxed apps: a recipe
            # that needs its own review (a download, a package script, a vendor package) is
            # never installed as a side effect of choosing a direction.
            member = by_id.get(canonical)
            if member is not None:
                require(member.get("source") == "flathub",
                        f"bundle {bid or '?'} holds {canonical!r}, which needs its own review; "
                        "bundles hold sandboxed apps only")
    facts["bundle_ids"] = bundle_ids
    return report, facts


# ── the chain that executes the catalogue ─────────────────────────────────────────────────────
SOURCE_HANDLER = {"flathub": ("FlatpakAdapter", "install_many")}
KIND_HANDLER = {
    "npm": ("_install_npm", 'install.get("pkg")', '"--prefix"'),
    "web": ("_install_web", "urlsplit", "XDG_OPEN"),
    # The backend's install paths for the v2 kinds (docs/MO_STORE.md "Kinds of app").
    "webapp": ("_install_webapp", "parse_entry("),
    "appdrop": ("_install_appdrop", "pinned_artifact(", "appdrop.plan_for("),
    "windows-portable": ("_install_windows_portable", "pe_architecture(", "_wine_argv("),
    # The publisher's own signed package: storectl never reimplements the module's checks.
    "vendor-rpm": ("_install_vendor_app", "vendor.parse_entry(install)",
                   "vendor.install(app_id, entry", "VENDOR_FAILURE_KEYS.get(code)"),
}


def check_chain(facts: dict, root: Path = IMAGE_ROOT, build_dir: Path = BUILD_DIR) -> Report:
    report = Report()
    require = report.require

    def text(path):
        return read_root(root, path)

    def store_text():
        """Mo Store's QML as one text: main.qml first, then the view files beside it by name.

        The Store window is main.qml; its rail, pages, sheets and cards are component files in the
        same folder. A promise this gate requires of the Store (or forbids it) holds for all of them.
        """
        main = root / STORE_QML.lstrip("/")
        folder = main.parent
        files = sorted((p for p in folder.rglob("*") if p.is_file() and p.suffix in (".qml", ".js")),
                       key=lambda p: (p != main, p.relative_to(folder).as_posix()))
        return "\n".join(p.read_text(encoding="utf-8") for p in files)

    # ── both QML surfaces safely tolerate catalog glyphs ──────────────────────────────────
    store_qml = store_text()
    welcome_qml = text(WELCOME_QML)
    symbol_catalog = code(text(SYMBOL_CATALOG), "//")
    require('"moos-spark-symbolic"' in symbol_catalog
            and "symbolNames[candidate]" in symbol_catalog,
            "the generated symbolic catalog lost its owned spark fallback")
    for qml_src, label in ((store_qml, "Mo Store"), (welcome_qml, "Welcome")):
        qml_code = code(qml_src, "//")
        require("import org.moos.ui as MoUI" in qml_code
                and "MoUI.SymbolCatalog.resolve(" in qml_code,
                f"the {label} QML lost the safe spark fallback for new catalog glyphs")

    # Welcome intentionally shows a small direction subset, while the catalog may
    # grow many more bundles. Validate only the ids Welcome actually references.
    welcome_code = code(welcome_qml, "//")
    direction_match = re.search(r"property\s+var\s+directionIds\s*:\s*\[(.*?)\]",
                                welcome_code, re.DOTALL)
    require(direction_match is not None,
            "could not parse Welcome.directionIds (catalog bundle relationship lost)")
    if direction_match is not None:
        direction_ids = re.findall(r'"([^"]+)"', direction_match.group(1))
        require(len(direction_ids) == len(set(direction_ids)),
                "Welcome.directionIds contains duplicate bundle ids")
        for direction_id in direction_ids:
            require(direction_id in facts["bundle_ids"],
                    f"Welcome references undefined catalog bundle {direction_id!r}")

    # ── the trusted backend performs every catalog recipe safely ───────────────────────────
    storectl_code = code(text(MOOS_STORECTL), "#")
    require(CATALOG in storectl_code, "moos-storectl does not read the signed store catalog path")
    if facts["has_flathub"]:
        for handler_token in SOURCE_HANDLER["flathub"]:
            require(handler_token in storectl_code,
                    "the catalog has Flathub apps but moos-storectl lacks its "
                    f"{handler_token!r} transaction path")
    for kind in sorted(facts["used_kinds"]):
        for handler_token in KIND_HANDLER.get(kind, ()):
            require(handler_token in storectl_code,
                    f"the catalog uses install kind {kind!r} but moos-storectl lacks "
                    f"required handler token {handler_token!r}")
    for risk in sorted(facts["risks"]):
        require(f'"{risk}"' in storectl_code,
                f"the catalog labels recipes {risk!r} but moos-storectl never names that "
                "review risk, so it would refuse them")
    if facts["used_kinds"]:
        require(re.search(r'metadata\.get\(\s*"requires_review"', storectl_code)
                and re.search(r'metadata\.get\(\s*"risk"', storectl_code),
                "moos-storectl does not consume install.requires_review/risk metadata")
    require('"job.json"' in storectl_code and "_atomic_bytes" in storectl_code,
            "moos-storectl must publish one atomic job.json for both QML surfaces")
    if "vendor-rpm" in facts["used_kinds"]:
        try:
            helper = code(text(VENDOR_RPM_HELPER), "#")
        except OSError:
            helper = ""
        require("--checksig" in helper,
                f"the catalog has vendor-rpm recipes but {VENDOR_RPM_HELPER} is missing or "
                "never runs `rpmkeys --checksig`")

    # ── installs cross only the private StoreBridge process boundary ───────────────────────
    bridge_code = code((build_dir / "moos-qml-shell.cpp").read_text(encoding="utf-8"), "//")
    for token in ("class StoreBridge", "Q_INVOKABLE bool installApps",
                  'QStringLiteral("/usr/bin/moos-storectl")', '"org.moos.store"',
                  '"org.moos.welcome"', 'QStringLiteral("MoosStore")'):
        require(token in bridge_code, f"moos-qml-shell lost required StoreBridge token {token!r}")
    require("QProcess::startDetached" in bridge_code
            and 'QStringList args{QStringLiteral("install")}' in bridge_code,
            "StoreBridge must start fixed moos-storectl argv, never construct a shell command")

    # The public moos: URL scheme remains useful for theme/installer handoff, but it
    # must not be an install authority: any web page can invoke a registered scheme.
    open_code = code(text(MOOS_OPEN), "#")
    require("store/install" not in open_code,
            "moos-open still exposes public store/install — a web page could trigger installs")
    # The Welcome's look picker and handover buttons are moos:// URLs too — a route
    # that disappears on one side turns a first-run button into a dead click.
    require("theme/dark" in open_code and "theme/light" in open_code,
            "moos-open lost the theme/dark|light routes the Welcome's look picker fires")
    require("app/store" in open_code,
            "moos-open lost the app/store route — the Welcome cannot hand over to Mo Store")
    require("installer/open" in open_code,
            "moos-open lost installer/open — live Welcome cannot hand off to the installer")

    for qml_src, label in ((store_qml, "Mo Store"), (welcome_qml, "Welcome")):
        qml_code = code(qml_src, "//")
        require("MoosStore.installApps" in qml_code,
                f"the {label} QML does not install through the private StoreBridge")
        require("moos://store/install/" not in qml_code,
                f"the {label} QML still installs through the public moos: URL scheme")
        require(CATALOG in qml_code, f"the {label} QML does not read the store catalog it displays")
        require("--cache=" in qml_code, f"the {label} QML does not read the shared --cache= path")
        require("job.json" in qml_code or "--job=" in qml_code,
                f"the {label} QML does not poll moos-storectl's job document")

    # ── launchers hand both QML surfaces one cache/job namespace ───────────────────────────
    for launcher_path, qml_ref, app_id, label in (
        (MOOS_STORE, STORE_QML, "org.moos.store", "moos-store"),
        (MOOS_WELCOME, WELCOME_QML, "org.moos.welcome", "moos-welcome"),
    ):
        launcher = code(text(launcher_path), "#")
        launches_qml = qml_ref in launcher
        if label == "moos-store":
            launches_qml = launches_qml or (
                'STORE_DIR="/usr/share/moos/apps/store"' in launcher
                and 'QML="${STORE_DIR}/main.qml"' in launcher
            )
        require(launches_qml,
                f"{label} does not launch {qml_ref} — launcher and app have drifted apart")
        require("--cache=" in launcher,
                f"{label} does not pass --cache= to the QML — progress polling has no path")
        require('CACHEDIR="${XDG_CACHE_HOME:-$HOME/.cache}/moos-store"' in launcher,
                f"{label} must use the backend's ~/.cache/moos-store job namespace")
        require("QML_XHR_ALLOW_FILE_READ" in launcher,
                f"{label} does not enable local-file XHR — the QML cannot read the catalog")
        require("/usr/bin/moos-qml-shell" in launcher and f"--app-id {app_id}" in launcher,
                f"{label} must run under the app id that enables its private StoreBridge")

    store_launcher = code(text(MOOS_STORE), "#")
    require(MOOS_STORE_INDEX in store_launcher and CATALOG in store_launcher,
            "moos-store does not refresh its AppStream index from the curated catalog")
    require('--index="$INDEX"' in store_launcher and '--job="$JOB"' in store_launcher,
            "moos-store does not pass the index/job paths its QML reads")
    index_code = code(text(MOOS_STORE_INDEX), "#")
    require(CATALOG in index_code, "moos-store-index does not merge the signed curated catalog")

    # ── the on-device self-check actually checks the store ─────────────────────────────────
    # moos-selfcheck is what a user runs after `bootc upgrade` to confirm everything
    # arrived and works. If the store ships but the health check never looks at it, a
    # broken install path reads as a clean bill of health.
    selfcheck = code(text(MOOS_SELFCHECK), "#")
    require(CATALOG in selfcheck,
            "moos-selfcheck does not check the store catalogue — a missing store would pass silently")
    require("moos-storectl" in selfcheck, "moos-selfcheck does not verify the trusted store backend")
    require("store/install" not in selfcheck,
            "moos-selfcheck still blesses the retired public install route")
    require("x-scheme-handler/moos" in selfcheck,
            "moos-selfcheck does not verify the moos:// handler Welcome still uses for handoff")
    require("moos-store" in selfcheck,
            "moos-selfcheck does not check the Mo Store launcher — a missing storefront would "
            "pass silently")
    return report


def main() -> int:
    catalog_path = IMAGE_ROOT / CATALOG.lstrip("/")
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 - any failure here is fatal for the store
        print(f"GATE FAIL: the store catalog does not parse: {e}")
        return 1
    catalog_report, facts = check_catalog(copy.deepcopy(catalog), IMAGE_ROOT, BUILD_DIR,
                                          catalog_path)
    errors = list(catalog_report.errors)
    try:
        errors += check_chain(facts, IMAGE_ROOT, BUILD_DIR).errors
    except OSError as error:
        errors.append(f"a file the Store chain needs is missing: {error}")
    if errors:
        print("GATE FAIL: the MoOS Store chain is inconsistent:")
        for e in errors:
            print(f"  - {e}")
        return 1
    apps = catalog.get("apps", [])
    kinds: dict[str, int] = {}
    for app in apps:
        kind = (app.get("install") or {}).get("kind") or app.get("source")
        kinds[kind] = kinds.get(kind, 0) + 1
    print(f"MoOS Store catalog OK: {len(apps)} apps "
          f"({', '.join(f'{k} {n}' for k, n in sorted(kinds.items()))}), "
          f"{len(catalog.get('categories', []))} categories, "
          f"{len(catalog.get('collections', []))} collections, "
          f"{len(catalog.get('featured', []))} featured, "
          f"{len(catalog.get('bundles', []))} bundles — safe recipes and chain consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
