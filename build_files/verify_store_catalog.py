#!/usr/bin/env python3
"""Fail the image build when the MoOS Store chain is internally inconsistent.

The store is one fact expressed across a chain of files, and the whole point of
the design is that they cannot drift:

    catalog.json ── every app, category and bundle the user can see
        │
        ├─▶ TWO QML surfaces draw it: the Mo Store app (apps/store) and the
        │   Welcome onboarding wizard (apps/welcome). Each draws every app with
        │   a glyph named in the catalog, from a glyph library defined in the
        │   QML itself.
        │
        ├─▶ moos-install installs each app by its catalog `source`/`install.kind`
        │
        └─▶ moos-open's `store/install/<id>` route runs moos-install for a
            catalog id, and BOTH QML surfaces fire exactly that moos:// URL,
            with their launchers handing the QML the cache path it polls for
            progress.

This gate checks the RELATIONSHIPS between those files, not constants inside one:
add an app with a glyph a QML can't draw, or an install kind moos-install can't
perform, or rename the URL route on one side only, and the build stops here — long
before a user taps Install and watches nothing happen.

Full-line comments are stripped before any search, so a gate can never be
satisfied by the prose that documents it (the same discipline as config()/code()
in the other verifiers).
"""

import json
import os
import re
from pathlib import Path

CATALOG = "/usr/share/moos/store/catalog.json"
STORE_QML = "/usr/share/moos/apps/store/main.qml"
WELCOME_QML = "/usr/share/moos/apps/welcome/main.qml"
MOOS_INSTALL = "/usr/bin/moos-install"
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


# ── the catalog itself must parse and have the three sections ─────────────────
try:
    catalog = json.loads(text(CATALOG))
except Exception as e:  # noqa: BLE001 - any failure here is fatal for the store
    print(f"GATE FAIL: the store catalog does not parse: {e}")
    raise SystemExit(1)

cats = catalog.get("categories", [])
apps = catalog.get("apps", [])
bundles = catalog.get("bundles", [])
require(len(cats) > 0, "the catalog has no categories")
require(len(apps) > 0, "the catalog has no apps")

cat_ids = {c.get("id") for c in cats}
app_ids = {a.get("id") for a in apps}

# ── categories are well-formed ────────────────────────────────────────────────
for c in cats:
    for field in ("id", "en", "ar", "glyph"):
        require(bool(c.get(field)), f"category {c.get('id', '?')} is missing '{field}'")

# ── apps are well-formed and installable ──────────────────────────────────────
KINDS_REQUIRE = {"npm": ("pkg",), "appimage": ("url", "bin"), "web": ("url",)}
for a in apps:
    aid = a.get("id", "?")
    for field in ("id", "source", "cat", "glyph", "en", "ar"):
        require(bool(a.get(field)), f"app {aid} is missing '{field}'")
    require(a.get("cat") in cat_ids,
            f"app {aid} is in category '{a.get('cat')}', which is not defined")
    source = a.get("source")
    require(source in ("flathub", "moos"),
            f"app {aid} has unknown source '{source}' (moos-install cannot install it)")
    if source == "moos":
        inst = a.get("install") or {}
        kind = inst.get("kind")
        require(kind in KINDS_REQUIRE,
                f"app {aid} is a moos app with unknown install kind '{kind}'")
        for field in KINDS_REQUIRE.get(kind, ()):  # required sub-fields per kind
            require(bool(inst.get(field)),
                    f"app {aid} ({kind}) is missing install.{field}")

# ── bundles only reference apps that exist ────────────────────────────────────
for b in bundles:
    for field in ("id", "en", "ar", "glyph", "apps"):
        require(bool(b.get(field)), f"bundle {b.get('id', '?')} is missing '{field}'")
    for ref in b.get("apps", []):
        require(ref in app_ids,
                f"bundle {b.get('id', '?')} lists app '{ref}', which is not in the catalog")

# ── RELATIONSHIP: every glyph the catalog names must exist in BOTH QML libraries ─
# Each surface draws each glyph from `readonly property var glyphs: ({...})`. If
# the catalog names one a QML has no path for, the card silently falls back to
# the 'spark' glyph — a store where three different apps wear the same icon.
# Parse each QML's glyph keys and demand the catalog's glyphs are a subset.
def qml_glyph_library(path, label):
    src = text(path)
    try:
        block = src.split("property var glyphs:", 1)[1].split("})", 1)[0]
        # Each entry is  "<key>": "<svg…>"  with any amount of alignment spacing;
        # the svg values use single quotes internally, so no "…" appears inside
        # a value.
        found = set(re.findall(r'"([A-Za-z0-9_]+)"\s*:\s*"', block))
    except Exception:  # noqa: BLE001
        found = set()
    require(len(found) >= 10,
            f"could not parse the glyph library out of the {label} QML (did its shape change?)")
    return src, found


store_qml, store_glyphs = qml_glyph_library(STORE_QML, "Mo Store")
welcome_qml, welcome_glyphs = qml_glyph_library(WELCOME_QML, "Welcome")

used_glyphs = {c.get("glyph") for c in cats} | {b.get("glyph") for b in bundles} \
    | {a.get("glyph") for a in apps}
for g in sorted(used_glyphs):
    require(g in store_glyphs,
            f"glyph '{g}' is used in the catalog but the Mo Store QML cannot draw it "
            f"(add its path to the glyphs library, or the card shows a fallback icon)")
    require(g in welcome_glyphs,
            f"glyph '{g}' is used in the catalog but the Welcome QML cannot draw it "
            f"(add its path to the glyphs library, or the card shows a fallback icon)")

# ── RELATIONSHIP: moos-install can perform every source/kind the catalog uses ──
install_code = code(text(MOOS_INSTALL), "#")
require(CATALOG in install_code, "moos-install does not read the store catalog path")
SOURCE_HANDLER = {"flathub": "flatpak install"}
KIND_HANDLER = {"npm": "npm install", "appimage": "curl", "web": "xdg-open"}
if any(a.get("source") == "flathub" for a in apps):
    require(SOURCE_HANDLER["flathub"] in install_code,
            "the catalog has flathub apps but moos-install has no flatpak install path")
used_kinds = {(a.get("install") or {}).get("kind")
              for a in apps if a.get("source") == "moos"}
for kind in used_kinds:
    if kind in KIND_HANDLER:
        require(KIND_HANDLER[kind] in install_code,
                f"the catalog uses install kind '{kind}' but moos-install has no handler for it")

# moos-install's stdout contract is what the Welcome parses — keep the tokens.
for token in ("PROGRESS", "DONE", "FAIL", "OPENED"):
    require(token in install_code,
            f"moos-install no longer emits '{token}' — the Welcome's progress bar reads it")

# ── RELATIONSHIP: the moos:// install route both surfaces fire actually exists ─
open_code = code(text(MOOS_OPEN), "#")
require("store/install" in open_code,
        "moos-open has no 'store/install' route — the install taps would do nothing")
require("moos-install" in open_code,
        "moos-open's store route does not run moos-install")
require(CATALOG in open_code,
        "moos-open's store route does not validate ids against the store catalog")
# The Welcome's look picker and handover buttons are moos:// URLs too — a route
# that disappears on one side turns a first-run button into a dead click.
require("theme/dark" in open_code and "theme/light" in open_code,
        "moos-open lost the theme/dark|light routes the Welcome's look picker fires")
require("app/store" in open_code,
        "moos-open lost the app/store route — the Welcome cannot hand over to Mo Store")

for qml_path, qml_src, label in ((STORE_QML, store_qml, "Mo Store"),
                                 (WELCOME_QML, welcome_qml, "Welcome")):
    qml_code = code(qml_src, "//")
    require("moos://store/install/" in qml_code,
            f"the {label} QML no longer fires moos://store/install/ — installs are wired to nothing")
    require(CATALOG in qml_code,
            f"the {label} QML does not read the store catalog it displays")
    require("--cache=" in qml_code,
            f"the {label} QML does not read the --cache= path its launcher passes")

# ── RELATIONSHIP: each launcher hands its QML what it needs (cache + file XHR) ─
for launcher_path, qml_ref, label in ((MOOS_STORE, STORE_QML, "moos-store"),
                                      (MOOS_WELCOME, WELCOME_QML, "moos-welcome")):
    launcher = code(text(launcher_path), "#")
    require(qml_ref in launcher,
            f"{label} does not launch {qml_ref} — launcher and app have drifted apart")
    require("--cache=" in launcher,
            f"{label} does not pass --cache= to the QML — progress polling has no path")
    require("QML_XHR_ALLOW_FILE_READ" in launcher,
            f"{label} does not enable local-file XHR — the QML cannot read the catalog")

# ── RELATIONSHIP: the on-device self-check actually checks the store ───────────
# moos-selfcheck is what a user runs after `bootc upgrade` to confirm everything
# arrived and works. If the store ships but the health check never looks at it, a
# broken install path reads as a clean bill of health. Tie them together: the
# self-check must interrogate the catalogue AND the moos:// route the store fires.
selfcheck = code(text(MOOS_SELFCHECK), "#")
require(CATALOG in selfcheck,
        "moos-selfcheck does not check the store catalogue — a missing store would pass silently")
require("store/install" in selfcheck,
        "moos-selfcheck does not verify the store/install route the store depends on")
require("x-scheme-handler/moos" in selfcheck,
        "moos-selfcheck does not verify the moos:// handler — dead install links would pass")
require("moos-store" in selfcheck,
        "moos-selfcheck does not check the Mo Store launcher — a missing storefront would pass silently")

# ── report ────────────────────────────────────────────────────────────────────
if errors:
    print("GATE FAIL: the MoOS Store chain is inconsistent:")
    for e in errors:
        print(f"  - {e}")
    raise SystemExit(1)

print(f"MoOS Store catalog OK: {len(apps)} apps, {len(cats)} categories, "
      f"{len(bundles)} bundles, {len(store_glyphs)} store glyphs / "
      f"{len(welcome_glyphs)} welcome glyphs — chain consistent.")
