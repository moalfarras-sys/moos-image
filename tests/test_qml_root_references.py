#!/usr/bin/env python3
"""Gate: a first-party QML app may not read a property of its root object that the root never
declares.

WHY THIS EXISTS

`root.novaOrange` is not an error QML reports when a file loads. It evaluates to `undefined`; a
colour binding logs "Unable to assign [undefined] to QColor" and keeps the type's default, and
`Qt.rgba(root.novaOrange.r, …)` throws a TypeError inside the binding. The window opens, the image
build's launch test passes (the app did not exit), every source gate passes (the text they grep
for is there), and the user gets a control painted in Qt's defaults.

Wave W4 (PR #110) shipped exactly that in the one card that must be right: Mo AI's confirmation
card for a PRIVILEGED action. Its warning frame, icon and "needs your administrator password" line
were bound to `root.novaOrange`, a name that has never existed in that file — six lines, ten
references — so on the dark theme the banner was a white slab with black text. It was found by
rendering the source in a real Qt runtime and reading its log, which no gate does.

This is the static half of that review: cheap, and sufficient for this defect class. For each
app it collects what the root declares (properties, functions, signals, the implied
`<property>Changed` signals) and what a Window/ApplicationWindow already has, and fails on any
other `<rootId>.<name>`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "system_files/usr/share/moos/apps"
# MoOS's settings pages: System Settings modules and the shared rows they are built from.
KCM = ROOT / "moos-settings-kcm"

# Members every QQuickWindow / QQC2 ApplicationWindow root already has. Keep this list to what the
# apps really use: a name added here is a name this gate can no longer catch as a typo.
INHERITED = {
    "width", "height", "x", "y", "visible", "visibility", "title", "color", "opacity", "flags",
    "contentItem", "activeFocusItem", "active", "screen", "palette", "font", "locale",
    "minimumWidth", "minimumHeight", "maximumWidth", "maximumHeight",
    "close", "show", "hide", "raise", "lower", "requestActivate", "alert",
    "showNormal", "showMaximized", "showMinimized", "showFullScreen",
    "header", "footer", "menuBar", "background", "overlay", "data",
}
# A settings page's root is a KCM page and its shared rows are controls: these are the two
# members of theirs the files read (a control's `text`, an Item's `enabled`).
INHERITED_CONTROL = {"text", "enabled"}
# These QQC2 states belong to AbstractButton, not to every settings page or Item.
# Keep the allowance type-scoped so a misspelt state on another root still fails.
ABSTRACT_BUTTON_STATES = {"down", "hovered", "visualFocus"}


def strip_noise(text: str) -> str:
    """Remove comments and string literals, so prose and messages cannot count as code."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"(?m)//[^\n]*$", "", text)
    text = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    text = re.sub(r"'(?:\\.|[^'\\\n])*'", "''", text)
    return text


def declarations(code: str, inherited: set[str]) -> set[str]:
    """What a file's objects declare (properties, functions, signals), plus the change signals."""
    declared = set(re.findall(
        r"(?m)^\s*(?:default\s+|required\s+|readonly\s+)*property\s+[\w.<>]+\s+(\w+)", code))
    declared |= {f"{name}Changed" for name in set(declared)}
    declared |= set(re.findall(r"(?m)^\s*function\s+(\w+)\s*\(", code))
    declared |= set(re.findall(r"(?m)^\s*signal\s+(\w+)", code))
    declared |= {f"{name}Changed" for name in inherited}
    return declared


def audit(path: Path, inherited: set[str] = INHERITED) -> list[str]:
    code = strip_noise(path.read_text(encoding="utf-8"))
    return audit_source(code, path.relative_to(ROOT).as_posix(), inherited)


def audit_source(code: str, label: str, inherited: set[str]) -> list[str]:
    root_type = re.search(r"(?m)^\s*([\w.]+)\s*\{", code)
    if root_type and root_type.group(1).split(".")[-1] == "AbstractButton":
        inherited = inherited | ABSTRACT_BUTTON_STATES
    first_id = re.search(r"(?m)^\s*id:\s*(\w+)", code)
    if not first_id:
        return [f"{label}: no root `id:` found — this gate cannot "
                "tell what the root is called; give the root an id"]
    root_id = first_id.group(1)
    declared = declarations(code, inherited)

    problems: list[str] = []
    seen: dict[str, list[int]] = {}
    for number, line in enumerate(code.splitlines(), 1):
        for name in re.findall(rf"\b{re.escape(root_id)}\.(\w+)", line):
            if name not in declared and name not in inherited:
                seen.setdefault(name, []).append(number)
    rel = label
    for name, lines in sorted(seen.items()):
        shown = ", ".join(map(str, lines[:6])) + (" …" if len(lines) > 6 else "")
        problems.append(f"{rel}: `{root_id}.{name}` is read on line(s) {shown} but `{root_id}` "
                        f"never declares `{name}` — it evaluates to undefined at runtime and the "
                        "control silently paints Qt's default")
    return problems


# ── Mo Store's views are files beside its window ──────────────────────────────
#
# apps/store/main.qml is the window and keeps all of the Store's state; the rail, the pages, the
# sheets and the cards are component files next to it, and each declares
# `required property var win` — the window. A component file cannot see main.qml's ids, yet QML
# resolves many of them anyway: an instance falls back to the scope of the file that created it,
# so a view that says `review.open()` or a bare `design.radiusCard` WORKS by accident of where it
# was instantiated, and nothing reports it. (Measured on Qt 6.11: a component read main.qml's ids
# and root properties that way, and `Child { win: win }` written inside a component file bound
# `win` to itself and came out undefined, without a warning.) So a view reaches the window only as
# `win.<member>`, every member it reads must be one main.qml's root declares, and nothing hands
# `win` on as `win: win` outside main.qml.
STORE = APPS / "store"


def ids(code: str) -> set[str]:
    """Every `id:` in a file, including one written inline (`ReviewSheet { id: review; … }`)."""
    return set(re.findall(r"(?<![\w.])id\s*:\s*(\w+)", code))


def audit_store_components(window: Path = STORE / "main.qml") -> list[str]:
    window_code = strip_noise(window.read_text(encoding="utf-8"))
    members = declarations(window_code, INHERITED) | INHERITED
    window_names = (ids(window_code)
                    | set(re.findall(r"(?m)^\s*(?:default\s+|required\s+|readonly\s+)*property"
                                     r"\s+[\w.<>]+\s+(\w+)", window_code))
                    | set(re.findall(r"(?m)^\s*function\s+(\w+)\s*\(", window_code)))
    problems: list[str] = []
    for path in sorted(STORE.rglob("*.qml")):
        if path == window:
            continue
        rel = path.relative_to(ROOT).as_posix()
        code = strip_noise(path.read_text(encoding="utf-8"))
        lines = code.splitlines()
        if not re.search(r"(?m)^\s*required\s+property\s+var\s+win\b", code):
            problems.append(f"{rel}: declares no `required property var win` — a Store view takes "
                            "the window from whoever creates it, never from QML's scope")
        if re.search(r"\bwin\s*:\s*win\s*[;}\n]", code):
            problems.append(f"{rel}: binds `win: win` — inside a component file that binds the "
                            "property to itself (undefined, without a warning); hand on "
                            "`<rootId>.win`")
        unknown: dict[str, list[int]] = {}
        for number, line in enumerate(lines, 1):
            for name in re.findall(r"\bwin\.(\w+)", line):
                if name not in members:
                    unknown.setdefault(name, []).append(number)
        for name, at in sorted(unknown.items()):
            problems.append(f"{rel}: `win.{name}` is read on line(s) {', '.join(map(str, at[:6]))} "
                            f"but main.qml's root never declares `{name}` — it evaluates to "
                            "undefined at runtime and the view silently paints Qt's default")
        local = (ids(code)
                 | declarations(code, set())
                 | set(re.findall(r"\b(?:var|let|const)\s+(\w+)", code))
                 | {name.strip() for params in re.findall(r"function\s*\w*\s*\(([^)]*)\)", code)
                    for name in params.split(",") if name.strip()}
                 | set(re.findall(r"\((\w+)\)\s*=>", code)))
        for name in sorted(window_names - local - {"win"}):
            bare = re.compile(rf"(?<![\w.]){re.escape(name)}\b(?!\s*:)")
            at = [number for number, line in enumerate(lines, 1) if bare.search(line)]
            if at:
                problems.append(f"{rel}: names main.qml's `{name}` on line(s) "
                                f"{', '.join(map(str, at[:6]))} without `win.` — that resolves only "
                                f"through its creator's scope; read `win.{name}` or declare it here")
    return problems


def main() -> int:
    # A native control's inherited states are valid, but typos and those same
    # names on an Item must still be refused. No broad global whitelist.
    for root_type, state, should_fail in (
        ("Controls.AbstractButton", "hovered", False),
        ("Controls.AbstractButton", "down", False),
        ("Controls.AbstractButton", "visualFocus", False),
        ("Controls.AbstractButton", "visualFocuss", True),
        ("Item", "hovered", True),
        ("Item", "down", True),
        ("Item", "visualFocus", True),
    ):
        code = f"{root_type} {{\n id: subject\n property bool probe: subject.{state}\n}}"
        if bool(audit_source(code, "inheritance-control", INHERITED)) != should_fail:
            print(f"GATE FAIL: root inheritance control {root_type}.{state}")
            return 1
    files = sorted(APPS.glob("*/main.qml"))
    settings = sorted(KCM.rglob("*.qml"))
    if len(files) < 4 or len(list(KCM.glob("modules/*/ui/main.qml"))) < 5:
        print(f"GATE FAIL: expected the four first-party apps under {APPS.relative_to(ROOT)} and "
              f"the MoOS settings modules under {KCM.relative_to(ROOT)}, found {len(files)} apps "
              f"and {len(settings)} settings files — if they moved, move this gate with them.")
        return 1
    errors: list[str] = []
    for path in files:
        errors += audit(path)
    for path in settings:
        errors += audit(path, INHERITED | INHERITED_CONTROL)
    errors += audit_store_components()
    views = [path for path in sorted(STORE.rglob("*.qml")) if path != STORE / "main.qml"]
    files += settings
    if errors:
        print("GATE FAIL: tests/test_qml_root_references.py")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"QML root-reference gate passed ({len(files)} first-party QML files: every "
          "`<root>.<name>` is declared by the root or inherited from its type; "
          f"{len(views)} Mo Store view files reach the window only through a declared `win.`)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
