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


def strip_noise(text: str) -> str:
    """Remove comments and string literals, so prose and messages cannot count as code."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"(?m)//[^\n]*$", "", text)
    text = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    text = re.sub(r"'(?:\\.|[^'\\\n])*'", "''", text)
    return text


def audit(path: Path) -> list[str]:
    code = strip_noise(path.read_text(encoding="utf-8"))
    first_id = re.search(r"(?m)^\s*id:\s*(\w+)", code)
    if not first_id:
        return [f"{path.relative_to(ROOT).as_posix()}: no root `id:` found — this gate cannot "
                "tell what the root is called; give the root an id"]
    root_id = first_id.group(1)
    declared = set(re.findall(
        r"(?m)^\s*(?:default\s+|required\s+|readonly\s+)*property\s+[\w.<>]+\s+(\w+)", code))
    declared |= {f"{name}Changed" for name in set(declared)}
    declared |= set(re.findall(r"(?m)^\s*function\s+(\w+)\s*\(", code))
    declared |= set(re.findall(r"(?m)^\s*signal\s+(\w+)", code))
    declared |= {f"{name}Changed" for name in INHERITED}

    problems: list[str] = []
    seen: dict[str, list[int]] = {}
    for number, line in enumerate(code.splitlines(), 1):
        for name in re.findall(rf"\b{re.escape(root_id)}\.(\w+)", line):
            if name not in declared and name not in INHERITED:
                seen.setdefault(name, []).append(number)
    rel = path.relative_to(ROOT).as_posix()
    for name, lines in sorted(seen.items()):
        shown = ", ".join(map(str, lines[:6])) + (" …" if len(lines) > 6 else "")
        problems.append(f"{rel}: `{root_id}.{name}` is read on line(s) {shown} but `{root_id}` "
                        f"never declares `{name}` — it evaluates to undefined at runtime and the "
                        "control silently paints Qt's default")
    return problems


def main() -> int:
    files = sorted(APPS.glob("*/main.qml"))
    if len(files) < 5:
        print(f"GATE FAIL: expected the five first-party apps under {APPS.relative_to(ROOT)}, "
              f"found {len(files)} — if they moved, move this gate with them.")
        return 1
    errors: list[str] = []
    for path in files:
        errors += audit(path)
    if errors:
        print("GATE FAIL: tests/test_qml_root_references.py")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"QML root-reference gate passed ({len(files)} first-party apps: every "
          "`<root>.<name>` is declared by the root or inherited from Window)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
