#!/usr/bin/env python3
"""Advice is not a fault, and Mo AI must not dress it as one.

On a healthy Oracle A1 whose device plan held exactly two INFO entries -- an
Android-emulator KVM note and "16 GiB is recommended for development" -- Mo AI
showed a warning triangle and announced "وجدت 2 مشكلة في جهازك" (found 2
problems). The owner reasonably read that as the system being broken.

The plan carries two severities, "important" and "info", and the QML already
knew the difference (it had a hasImportant property) while the banner counted
every entry as a problem. A banner that cries fault over advice teaches the
owner to ignore the banner that matters.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
QML = ROOT / "system_files/usr/share/moos/apps/moai/main.qml"
ICONS = ROOT / "system_files/usr/share/icons/hicolor/scalable/actions"

src = QML.read_text(encoding="utf-8")
code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("//"))

# problemCount must count only real faults, never every action.
assert not re.search(r"property int problemCount:\s*actions\.length", code), (
    "problemCount counts every plan entry again, so INFO advice is announced as "
    "a problem under a warning icon")
assert 'severity === "important"' in code, \
    "problemCount must select on severity"
assert "property int adviceCount" in code, \
    "advice must be counted separately from faults"

# The banner's icon and tint must follow the distinction, not be hardcoded.
icon_branch = re.search(
    r'root\.problemCount > 0\s*\n?\s*\?\s*"(moos-[a-z-]+-symbolic)"'
    r'\s*:\s*"(moos-[a-z-]+-symbolic)"', code)
assert icon_branch, "the banner icon no longer branches on severity"
assert icon_branch.group(1) != icon_branch.group(2), (
    "both branches show the same glyph, so advice still renders as a warning: "
    f"{icon_branch.group(1)}")

# The tint must be derived, and derived FROM severity -- not merely named.
tone = re.search(r'property color bannerTone:\s*root\.problemCount > 0', code)
assert tone, "the banner tint must be derived from problemCount"
assert code.count("bannerTone") >= 3, \
    "bannerTone is declared but not actually used for fill and border"

# Every icon the banner names must actually ship, or it renders as nothing.
for icon in set(re.findall(r'"(moos-[a-z-]+-symbolic)"', code)):
    assert (ICONS / f"{icon}.svg").is_file(), (
        f"{icon} is referenced but not shipped; a missing icon renders blank")

# Arabic number agreement for both wordings.
assert "function adviceCountText(" in code and "function issueCountText(" in code, \
    "both counts need real Arabic number agreement"
assert "اقتراحان" in src and "مشكلتان" in src, \
    "the dual form is what these counts hit most often"

print("Mo AI severity banner gate passed")
