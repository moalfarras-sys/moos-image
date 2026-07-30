#!/usr/bin/env python3
"""Fail the image build when the MoOS Store chain is unsafe or inconsistent.

The catalog is executable input: ids reach command arguments, `bin` reaches a
filename, npm packages run package scripts, and web recipes open browser pages.
This gate therefore validates the catalog defensively before checking the
relationships between the two QML surfaces, their launchers, the private
StoreBridge and moos-storectl.

New catalog glyphs deliberately do not require duplicate edits to two hardcoded
QML libraries. Both surfaces have a safe `spark` fallback; this gate checks that
fallback relationship instead of requiring every catalog glyph to be present.

Full-line comments are stripped before any source search, so a gate can never be
satisfied by the prose that documents it.
"""

import json
import os
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

CATALOG = "/usr/share/moos/store/catalog.json"
STORE_QML = "/usr/share/moos/apps/store/main.qml"
WELCOME_QML = "/usr/share/moos/apps/welcome/main.qml"
SYMBOL_CATALOG = "/usr/share/moos/apps/ui/SymbolCatalog.js"
MOOS_STORECTL = "/usr/bin/moos-storectl"
MOOS_STORE_INDEX = "/usr/bin/moos-store-index"
MOOS_OPEN = "/usr/bin/moos-open"
MOOS_STORE = "/usr/bin/moos-store"
MOOS_WELCOME = "/usr/bin/moos-welcome"
MOOS_SELFCHECK = "/usr/bin/moos-selfcheck"

errors = []
IMAGE_ROOT = Path(os.environ.get("MOOS_TEST_ROOT", "/"))


def require(ok, message):
    if not ok:
        errors.append(message)


def text(path):
    # In the image build the root is `/`. Developers can run the identical gate
    # against system_files on Windows/Linux with MOOS_TEST_ROOT=<repo>/system_files.
    return (IMAGE_ROOT / str(path).lstrip("/")).read_text(encoding="utf-8")


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


def walk_strings(value, where="$"):
    """Reject control characters anywhere, including future schema fields."""
    if isinstance(value, str):
        bad = next(
            (ch for ch in value if unicodedata.category(ch) == "Cc"),
            None,
        )
        if bad is not None:
            require(
                False,
                f"{where} contains forbidden control character U+{ord(bad):04X}",
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk_strings(child, f"{where}[{index}]")
    elif isinstance(value, dict):
        for key, child in value.items():
            require(
                key not in {"rating", "reviews"},
                f"{where} contains manual {key!r}; the catalog has no verified "
                "ratings/review source",
            )
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
    require(
        not any(ch.isspace() for ch in value),
        f"{label} contains whitespace",
    )
    try:
        parts = urlsplit(value)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        require(False, f"{label} is not a valid URL: {exc}")
        return None
    require(parts.scheme == "https", f"{label} must use HTTPS")
    require(bool(host), f"{label} has no hostname")
    require(
        parts.username is None and parts.password is None,
        f"{label} must not contain URL credentials",
    )
    require(port is None, f"{label} must not contain an explicit port")
    require(parts.netloc == host, f"{label} hostname must use canonical lowercase form")
    return parts


def require_review_metadata(inst, label, risk):
    require(
        inst.get("risk") == risk,
        f"{label}.risk must be {risk!r}",
    )
    require(
        inst.get("requires_review") is True,
        f"{label}.requires_review must be true",
    )


def validate_basename(value, label):
    name = clean_text(value, label, BIN_RE)
    if name:
        require(name not in {".", ".."}, f"{label} must be a basename, not a path")
        require("/" not in name and "\\" not in name,
                f"{label} must be a basename, not a path")
    return name


# ── the catalog itself must parse and have the three sections ─────────────────
try:
    catalog = json.loads(text(CATALOG))
except Exception as e:  # noqa: BLE001 - any failure here is fatal for the store
    print(f"GATE FAIL: the store catalog does not parse: {e}")
    raise SystemExit(1)

require(isinstance(catalog, dict), "the catalog root must be a JSON object")
if not isinstance(catalog, dict):
    catalog = {}
walk_strings(catalog)


def section(name):
    value = catalog.get(name)
    require(isinstance(value, list), f"catalog.{name} must be an array")
    return value if isinstance(value, list) else []


cats = section("categories")
apps = section("apps")
bundles = section("bundles")
require(len(cats) > 0, "the catalog has no categories")
require(len(apps) > 0, "the catalog has no apps")

# ── categories are well-formed ────────────────────────────────────────────────
cat_ids = set()
for index, category in enumerate(cats):
    label = f"category[{index}]"
    require(isinstance(category, dict), f"{label} must be an object")
    if not isinstance(category, dict):
        continue
    cid = required_text(category, "id", label, SLUG_RE)
    add_unique(cid, cat_ids, "category")
    required_text(category, "en", label)
    required_text(category, "ar", label)
    required_text(category, "glyph", label, GLYPH_RE)

# ── apps are well-formed and installable ──────────────────────────────────────
app_ids = set()
used_kinds = set()
for index, app in enumerate(apps):
    label = f"app[{index}]"
    require(isinstance(app, dict), f"{label} must be an object")
    if not isinstance(app, dict):
        continue

    source = required_text(app, "source", label)
    aid_pattern = FLATPAK_ID_RE if source == "flathub" else SLUG_RE
    aid = required_text(app, "id", label, aid_pattern)
    add_unique(aid, app_ids, "app")
    category = required_text(app, "cat", label, SLUG_RE)
    require(
        category in cat_ids,
        f"app {aid or '?'} references undefined category {category!r}",
    )
    required_text(app, "glyph", label, GLYPH_RE)
    required_text(app, "en", label)
    required_text(app, "ar", label)
    required_text(app, "desc_en", label)
    required_text(app, "desc_ar", label)
    for boolean_field in ("popular", "preselect"):
        if boolean_field in app:
            require(
                isinstance(app[boolean_field], bool),
                f"{label}.{boolean_field} must be boolean",
            )

    require(
        source in {"flathub", "moos"},
        f"app {aid or '?'} has unknown source {source!r}",
    )
    if app.get("preselect") is True:
        require(
            source == "flathub",
            f"preselected app {aid or '?'} must be a sandboxed Flatpak; "
            "advanced recipes always require an explicit user choice",
        )
    if source == "flathub":
        require(
            "install" not in app,
            f"Flathub app {aid or '?'} must not carry a second install recipe",
        )
        continue
    if source != "moos":
        continue

    inst = app.get("install")
    require(isinstance(inst, dict), f"MoOS app {aid or '?'} needs install object")
    if not isinstance(inst, dict):
        continue
    kind = required_text(inst, "kind", f"{label}.install")
    require(
        kind in {"npm", "appimage", "web"},
        f"app {aid or '?'} has unknown install kind {kind!r}",
    )
    if kind:
        used_kinds.add(kind)

    if kind == "npm":
        pkg = required_text(inst, "pkg", f"{label}.install")
        binary = validate_basename(inst.get("bin"), f"{label}.install.bin")
        expected = NPM_RECIPE_ALLOWLIST.get(aid)
        require(
            expected is not None,
            f"npm app {aid or '?'} is not in the exact recipe allowlist",
        )
        if expected is not None:
            require(
                (pkg, binary) == expected,
                f"npm app {aid} must use exact recipe pkg={expected[0]!r}, "
                f"bin={expected[1]!r}",
            )
        require_review_metadata(inst, f"{label}.install", "runs-package-scripts")
        for forbidden in ("url", "version", "sha256", "external"):
            require(
                forbidden not in inst,
                f"npm recipe {aid or '?'} must not contain install.{forbidden}",
            )

    elif kind == "web":
        parts = checked_https_url(inst.get("url"), f"{label}.install.url")
        require(
            inst.get("external") is True,
            f"web recipe {aid or '?'} must declare install.external=true",
        )
        require_review_metadata(inst, f"{label}.install", "external-download")
        for forbidden in ("pkg", "bin", "version", "sha256"):
            require(
                forbidden not in inst,
                f"web recipe {aid or '?'} must not contain install.{forbidden}",
            )
        if parts is not None and parts.hostname:
            allowed_paths = WEB_PAGE_ALLOWLIST.get(parts.hostname)
            require(
                allowed_paths is not None,
                f"web recipe {aid or '?'} uses non-allowlisted domain "
                f"{parts.hostname!r}",
            )
            decoded_path = unquote(parts.path)
            if allowed_paths is not None:
                require(
                    decoded_path in allowed_paths,
                    f"web recipe {aid or '?'} uses non-allowlisted page path "
                    f"{decoded_path!r}",
                )
            require(
                not parts.query and not parts.fragment,
                f"web recipe {aid or '?'} must open a canonical page without "
                "query/fragment",
            )
            require(
                not decoded_path.lower().endswith(DIRECT_DOWNLOAD_SUFFIXES),
                f"web recipe {aid or '?'} points directly to an executable/archive",
            )

    elif kind == "appimage":
        # Metadata alone is not enough: the relationship section below also
        # requires moos-storectl to verify the declared digest before execution.
        checked_https_url(inst.get("url"), f"{label}.install.url")
        validate_basename(inst.get("bin"), f"{label}.install.bin")
        required_text(inst, "version", f"{label}.install", VERSION_RE)
        required_text(inst, "sha256", f"{label}.install", SHA256_RE)
        require_review_metadata(inst, f"{label}.install", "downloaded-executable")
        require(
            inst.get("external") is True,
            f"AppImage recipe {aid or '?'} must declare install.external=true",
        )
        for forbidden in ("pkg",):
            require(
                forbidden not in inst,
                f"AppImage recipe {aid or '?'} must not contain install.{forbidden}",
            )

# ── bundles only reference apps that exist ────────────────────────────────────
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
    required_text(bundle, "glyph", label, GLYPH_RE)
    required_text(bundle, "desc_en", label)
    required_text(bundle, "desc_ar", label)
    refs = bundle.get("apps")
    require(
        isinstance(refs, list) and bool(refs),
        f"{label}.apps must be a non-empty array",
    )
    if not isinstance(refs, list):
        continue
    seen_refs = set()
    for ref_index, ref in enumerate(refs):
        ref_label = f"{label}.apps[{ref_index}]"
        canonical = clean_text(ref, ref_label)
        require(
            bool(SLUG_RE.fullmatch(canonical) or FLATPAK_ID_RE.fullmatch(canonical))
            if canonical else False,
            f"{ref_label} is not a canonical app id",
        )
        require(
            canonical not in seen_refs,
            f"bundle {bid or '?'} repeats app {canonical!r}",
        )
        if canonical:
            seen_refs.add(canonical)
        require(
            canonical in app_ids,
            f"bundle {bid or '?'} references undefined app {canonical!r}",
        )

# ── RELATIONSHIP: both QML surfaces safely tolerate new catalog glyphs ─────────
store_qml = text(STORE_QML)
welcome_qml = text(WELCOME_QML)
symbol_catalog = code(text(SYMBOL_CATALOG), "//")
require(
    '"moos-spark-symbolic"' in symbol_catalog
    and "symbolNames[candidate]" in symbol_catalog,
    "the generated symbolic catalog lost its owned spark fallback",
)
for qml_src, label in ((store_qml, "Mo Store"), (welcome_qml, "Welcome")):
    qml_code = code(qml_src, "//")
    require(
        'import "../ui/SymbolCatalog.js" as MoOSSymbols' in qml_code
        and "MoOSSymbols.resolve(" in qml_code,
        f"the {label} QML lost the safe spark fallback for new catalog glyphs",
    )

# Welcome intentionally shows a small direction subset, while the catalog may
# grow many more bundles. Validate only the ids Welcome actually references.
welcome_code = code(welcome_qml, "//")
direction_match = re.search(
    r"property\s+var\s+directionIds\s*:\s*\[(.*?)\]",
    welcome_code,
    re.DOTALL,
)
require(
    direction_match is not None,
    "could not parse Welcome.directionIds (catalog bundle relationship lost)",
)
if direction_match is not None:
    direction_ids = re.findall(r'"([^"]+)"', direction_match.group(1))
    require(
        len(direction_ids) == len(set(direction_ids)),
        "Welcome.directionIds contains duplicate bundle ids",
    )
    for direction_id in direction_ids:
        require(
            direction_id in bundle_ids,
            f"Welcome references undefined catalog bundle {direction_id!r}",
        )

# ── RELATIONSHIP: the trusted backend performs every catalog recipe safely ────
storectl_code = code(text(MOOS_STORECTL), "#")
require(
    CATALOG in storectl_code,
    "moos-storectl does not read the signed store catalog path",
)
SOURCE_HANDLER = {"flathub": ("FlatpakAdapter", "install_many")}
KIND_HANDLER = {
    "npm": ("_install_npm", 'install.get("pkg")', '"--prefix"'),
    "appimage": (
        "_install_pinned_appimage",
        'install.get("sha256")',
        "hasher.hexdigest()",
    ),
    "web": ("_install_web", "urlsplit", "XDG_OPEN"),
}
if any(isinstance(app, dict) and app.get("source") == "flathub" for app in apps):
    for handler_token in SOURCE_HANDLER["flathub"]:
        require(
            handler_token in storectl_code,
            "the catalog has Flathub apps but moos-storectl lacks its "
            f"{handler_token!r} transaction path",
        )
for kind in used_kinds:
    for handler_token in KIND_HANDLER.get(kind, ()):
        require(
            handler_token in storectl_code,
            f"the catalog uses install kind {kind!r} but moos-storectl lacks "
            f"required handler token {handler_token!r}",
        )
if used_kinds:
    require(
        re.search(r'metadata\.get\(\s*"requires_review"', storectl_code)
        and re.search(r'metadata\.get\(\s*"risk"', storectl_code),
        "moos-storectl does not consume install.requires_review/risk metadata",
    )
require(
    '"job.json"' in storectl_code and "_atomic_bytes" in storectl_code,
    "moos-storectl must publish one atomic job.json for both QML surfaces",
)

# ── RELATIONSHIP: installs cross only the private StoreBridge process boundary ─
bridge_code = code(build_text("moos-qml-shell.cpp"), "//")
for token in (
    "class StoreBridge",
    "Q_INVOKABLE bool installApps",
    'QStringLiteral("/usr/bin/moos-storectl")',
    '"org.moos.store"',
    '"org.moos.welcome"',
    'QStringLiteral("MoosStore")',
):
    require(
        token in bridge_code,
        f"moos-qml-shell lost required StoreBridge token {token!r}",
    )
require(
    "QProcess::startDetached" in bridge_code
    and 'QStringList args{QStringLiteral("install")}' in bridge_code,
    "StoreBridge must start fixed moos-storectl argv, never construct a shell command",
)

# The public moos: URL scheme remains useful for theme/installer handoff, but it
# must not be an install authority: any web page can invoke a registered scheme.
open_code = code(text(MOOS_OPEN), "#")
require(
    "store/install" not in open_code,
    "moos-open still exposes public store/install — a web page could trigger installs",
)
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
    require(
        "MoosStore.installApps" in qml_code,
        f"the {label} QML does not install through the private StoreBridge",
    )
    require(
        "moos://store/install/" not in qml_code,
        f"the {label} QML still installs through the public moos: URL scheme",
    )
    require(CATALOG in qml_code,
            f"the {label} QML does not read the store catalog it displays")
    require("--cache=" in qml_code,
            f"the {label} QML does not read the shared --cache= path")
    require(
        "job.json" in qml_code or "--job=" in qml_code,
        f"the {label} QML does not poll moos-storectl's job document",
    )

# ── RELATIONSHIP: launchers hand both QML surfaces one cache/job namespace ─────
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
    require(
        launches_qml,
        f"{label} does not launch {qml_ref} — launcher and app have drifted apart",
    )
    require("--cache=" in launcher,
            f"{label} does not pass --cache= to the QML — progress polling has no path")
    require(
        'CACHEDIR="${XDG_CACHE_HOME:-$HOME/.cache}/moos-store"' in launcher,
        f"{label} must use the backend's ~/.cache/moos-store job namespace",
    )
    require("QML_XHR_ALLOW_FILE_READ" in launcher,
            f"{label} does not enable local-file XHR — the QML cannot read the catalog")
    require(
        "/usr/bin/moos-qml-shell" in launcher and f"--app-id {app_id}" in launcher,
        f"{label} must run under the app id that enables its private StoreBridge",
    )

store_launcher = code(text(MOOS_STORE), "#")
require(
    MOOS_STORE_INDEX in store_launcher and CATALOG in store_launcher,
    "moos-store does not refresh its AppStream index from the curated catalog",
)
require(
    '--index="$INDEX"' in store_launcher and '--job="$JOB"' in store_launcher,
    "moos-store does not pass the index/job paths its QML reads",
)
index_code = code(text(MOOS_STORE_INDEX), "#")
require(
    CATALOG in index_code,
    "moos-store-index does not merge the signed curated catalog",
)

# ── RELATIONSHIP: the on-device self-check actually checks the store ───────────
# moos-selfcheck is what a user runs after `bootc upgrade` to confirm everything
# arrived and works. If the store ships but the health check never looks at it, a
# broken install path reads as a clean bill of health.
selfcheck = code(text(MOOS_SELFCHECK), "#")
require(CATALOG in selfcheck,
        "moos-selfcheck does not check the store catalogue — a missing store would pass silently")
require("moos-storectl" in selfcheck,
        "moos-selfcheck does not verify the trusted store backend")
require("store/install" not in selfcheck,
        "moos-selfcheck still blesses the retired public install route")
require("x-scheme-handler/moos" in selfcheck,
        "moos-selfcheck does not verify the moos:// handler Welcome still uses for handoff")
require("moos-store" in selfcheck,
        "moos-selfcheck does not check the Mo Store launcher — a missing storefront would pass silently")

# ── report ────────────────────────────────────────────────────────────────────
if errors:
    print("GATE FAIL: the MoOS Store chain is inconsistent:")
    for e in errors:
        print(f"  - {e}")
    raise SystemExit(1)

print(
    f"MoOS Store catalog OK: {len(apps)} apps, {len(cats)} categories, "
    f"{len(bundles)} bundles — safe recipes and chain consistent."
)
