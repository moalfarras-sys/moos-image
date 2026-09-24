#!/usr/bin/env python3
"""Hide Breeze's three Global Theme wrappers from the picker, on every edition.

The Global Theme picker should read all-MoOS. Breeze's three looks (Breeze, Breeze Dark, Breeze
Twilight) are KDE's, not another distribution's, so they are NOT deleted: Breeze stays the
fallback ENGINE every MoOS look reaches for (FallbackTheme=breeze-dark). But a foreign NAME in the
chooser, beside MoOS's looks, is the "not fully MoOS" the owner asked to remove. So the wrappers
get Hidden=true while the Breeze plasma style and colour engine stay intact and selectable as the
fallback. Nothing is removed from disk.

This lived inline in build.sh, so the x86 editions hid Breeze and the ARM edition did not.
Measured on the A1 (moos-arm 44.20260923.568) on 2026-09-24: all three wrappers had no Hidden
key, and the picker offered Breeze beside the MoOS looks. The Plasma seam gate found the
asymmetry: rpm -V reported these three files modified on x86 only. One script, called by both
build scripts, keeps the editions from drifting apart again.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

WRAPPERS = ("org.kde.breeze.desktop", "org.kde.breezedark.desktop", "org.kde.breezetwilight.desktop")
LOOK_AND_FEEL = "usr/share/plasma/look-and-feel"


def metadata_paths(root: Path) -> list[Path]:
    return [root / LOOK_AND_FEEL / name / "metadata.json" for name in WRAPPERS]


def hide(root: Path) -> list[Path]:
    """Mark every present wrapper hidden. Idempotent; a missing wrapper is not an error."""
    hidden = []
    for path in metadata_paths(root):
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("KPlugin", {})["Hidden"] = True
        data["Hidden"] = True  # some KCM paths read the top-level flag
        path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
        hidden.append(path)
    return hidden


def verify(root: Path) -> list[str]:
    problems = []
    for path in metadata_paths(root):
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("KPlugin", {}).get("Hidden") is not True or data.get("Hidden") is not True:
            problems.append(f"{path} is still offered in the Global Theme picker")
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("/")
    for path in hide(root):
        print(f"MoOS: hid {path.parent.name} from the Global Theme picker")
    problems = verify(root)
    for problem in problems:
        print(f"GATE FAIL: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
