#!/usr/bin/env python3
"""Gate: no MoOS app QML names the base distribution, checked before the image build.

build_files/verify_identity.py enforces this inside the built image, where a failure costs a
full CI build. On 2026-09-12 Mo AI's new identity rule named the distribution it forbade: every
local repo gate passed, and the x86 and ARM builds of that commit failed at the identity step.
This runs the same rule on the source tree, stripping comments exactly as that gate does.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "system_files/usr/share/moos/apps"
# The image gate's own rule, verbatim; if it changes, this mirror must be revisited.
IMAGE_RULE = ('rglob("*.qml")', 'flags=re.DOTALL)', '(?m)//.*$', '"fedora" not in source.lower()')


def offenders():
    found = []
    for qml in sorted(APPS.rglob("*.qml")):
        source = re.sub(r"/\*.*?\*/", "", qml.read_text(encoding="utf-8"), flags=re.DOTALL)
        source = re.sub(r"(?m)//.*$", "", source)
        if "fedora" in source.lower():
            found.append(str(qml.relative_to(ROOT)))
    return found


def main():
    gate = (ROOT / "build_files/verify_identity.py").read_text(encoding="utf-8")
    missing = [fragment for fragment in IMAGE_RULE if fragment not in gate]
    if missing:
        print(f"GATE FAIL: verify_identity.py no longer contains {missing}; update this mirror")
        return 1
    bad = offenders()
    if bad:
        print("GATE FAIL: MoOS app QML names the base distribution "
              "(build_files/verify_identity.py fails the image build):")
        for path in bad:
            print("  -", path)
        return 1
    print(f"App QML identity gate passed ({len(list(APPS.rglob('*.qml')))} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
