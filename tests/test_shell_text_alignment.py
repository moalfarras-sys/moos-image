#!/usr/bin/env python3
"""Gate: a line of text in a fixed script sits on the column's edge, not on its own script's edge.

WHY THIS EXISTS

The MoOS Hub's clock column shows the date as a bilingual pair: an Arabic line (built from
`Qt.locale("ar")` names) over an English line (`Qt.locale("en")`). Neither Text set a
`horizontalAlignment`. Qt Quick then aligns each by the direction of ITS OWN TEXT, whatever the
layout around it does:

    Arabic session   the column is right-aligned; the English line hung on its LEFT edge
    English session  the column is left-aligned; the Arabic line hung on its RIGHT edge

On the owner's daily desktop that is a date floating three hundred pixels away from the clock it
belongs to. No gate could see it (every gate reads source or a first-party app window), and it
was found the first time the desktop itself was rendered off the station
(scripts/review/render-desktop.sh, 2026-09-17).

The rule, for MoOS's shell-side packages (scene wallpaper, greeter, lock screen, plasmoids): a
Text whose content is pinned to ONE script regardless of the session — it names `Qt.locale("…")`
or a property built from one — must say where it aligns. `Text.AlignLeft` is the leading edge:
the shell mirrors it to the right in an Arabic session. A Text that follows the session's own
locale needs nothing: its script and the layout already agree.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLASMA = ROOT / "system_files/usr/share/plasma"
TREES = [PLASMA / "wallpapers", PLASMA / "plasmoids", PLASMA / "shells/org.kde.plasma.desktop/contents/lockscreen"]
PINNED = re.compile(r'Qt\.locale\("[a-z_A-Z]+"\)')


def text_blocks(source: str):
    """Yield (line number, body) for every `Text { … }` item, nesting-aware."""
    for match in re.finditer(r"(?m)^[ \t]*(?:[A-Za-z0-9_.]+\.)?Text\s*\{", source):
        depth, index = 1, match.end()
        while depth and index < len(source):
            depth += {"{": 1, "}": -1}.get(source[index], 0)
            index += 1
        yield source.count("\n", 0, match.start()) + 1, source[match.end():index - 1]


def main() -> int:
    errors: list[str] = []
    checked = pinned_total = 0
    for tree in TREES:
        for path in sorted(tree.rglob("*.qml")):
            if "org.moos" not in path.as_posix() and "lockscreen" not in path.as_posix():
                continue
            source = path.read_text(encoding="utf-8")
            code = re.sub(r"(?m)//[^\n]*$", "", source)
            # Properties that hold one fixed locale ("readonly property var arabicLocale: Qt.locale("ar")").
            fixed = set(re.findall(r"property\s+var\s+(\w+)\s*:\s*Qt\.locale\(\"[a-z_A-Z]+\"\)", code))
            checked += 1
            for number, body in text_blocks(code):
                text_binding = re.search(r"(?s)\btext\s*:(.*?)(?:\n\s*[a-z][A-Za-z.]*\s*:|\Z)", body)
                if not text_binding:
                    continue
                expression = text_binding.group(1)
                if not (PINNED.search(expression) or any(re.search(rf"\b{name}\b", expression) for name in fixed)):
                    continue
                pinned_total += 1
                if "horizontalAlignment" not in body:
                    errors.append(f"{path.relative_to(ROOT).as_posix()}:{number}: this Text shows a fixed "
                                  "script and sets no horizontalAlignment, so it aligns by that script "
                                  "instead of by its column (Text.AlignLeft is the leading edge; the "
                                  "shell mirrors it in an Arabic session)")
    if checked < 10:
        print(f"GATE FAIL: only {checked} shell QML files were read; the packages moved")
        return 1
    if pinned_total == 0:
        print("GATE FAIL: no fixed-script Text was found at all — the Hub's bilingual date pair is "
              "gone or this gate can no longer see it; update the rule with the design")
        return 1
    if errors:
        print("GATE FAIL: tests/test_shell_text_alignment.py")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"shell text alignment gate passed ({checked} files, {pinned_total} fixed-script lines aligned explicitly)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
