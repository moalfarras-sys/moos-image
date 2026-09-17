#!/usr/bin/env python3
"""Gate: the window switcher is a MoOS surface, and keeps the three properties it was built for.

WHY THIS EXISTS

Alt+Tab is one of the few surfaces a person sees dozens of times a day, and until W7 it was the
stock `thumbnail_grid`. Measured on the station on 2026-09-17 (44.20260917.858, KWin 6.7.5,
3840x2160 at 265%, Arabic session), three things were wrong with it on a MoOS desk, and each one
is a rule below:

1.  READING DIRECTION.  The stock layouts decide theirs from `Application.layoutDirection`.
    MoOS ships bilingual QML strings instead of Qt translation catalogues, so no translator is
    installed and that property is LeftToRight on EVERY MoOS session, Arabic ones included - the
    warning written at the top of `org/moos/ui/Locale.qml`. The switcher therefore ran
    left-to-right inside a right-to-left desk. `MoUI.Locale.rtl` is the one authority, and it was
    confirmed to return true inside KWin's own QML engine by rendering it into the live switcher.
    A future edit that reaches for `Application.layoutDirection` because it is what upstream uses
    re-introduces exactly this bug, silently, in the language half the users read.

2.  MOTION.  Nothing may animate unconditionally. Plasma's reduced-motion setting arrives as
    `Kirigami.Units.longDuration <= 1`, the same signal `org/moos/ui/SpringFeedback.qml` reads;
    with animations off the strip must jump, not merely hurry. Every duration therefore goes
    through `Tokens.duration(motionEnabled, ...)` and the spring is bound to the same flag.

3.  NO LOST CAPABILITY AND NO DEAD BUTTON.  The stock layout could close a window from the
    switcher. Dropping that to make a prettier surface would be a regression, so MoOS keeps it -
    and `AGENTS.md` forbids shipping a button that does nothing, so the handler must really call
    the model's `close`. That method was confirmed to exist on KWin 6.7.5 by reading `typeof
    tabBox.model.close` off the LIVE model and rendering the answer into the switcher: "function".

It also holds the wiring: a switcher nothing selects is decoration, so kwinrc must name this
package for both the main and the same-application switcher.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "system_files/usr/share/kwin/tabbox/org.moos.ui2.switcher"
QML = PACKAGE / "contents/ui/main.qml"
METADATA = PACKAGE / "metadata.json"
KWINRC = ROOT / "system_files/etc/xdg/kwinrc"
PACKAGE_ID = "org.moos.ui2.switcher"


def code(text: str) -> str:
    """The QML with comments removed, so prose about a trap is not read as the trap."""
    without_block = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(line for line in without_block.splitlines()
                     if not line.lstrip().startswith("//"))


def config_value(text: str, group: str, key: str) -> str | None:
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1]
        elif current == group and stripped.startswith(f"{key}="):
            return stripped.split("=", 1)[1].strip()
    return None


def main() -> int:
    errors: list[str] = []

    for path in (QML, METADATA):
        if not path.is_file():
            print(f"GATE FAIL: {path.relative_to(ROOT)} is missing - the MoOS switcher is a "
                  "KPackage, and KWin reads both of these files by name")
            return 1

    body = code(QML.read_text(encoding="utf-8"))

    # 1. Reading direction.
    if "Application.layoutDirection" in body:
        errors.append(
            "the switcher reads `Application.layoutDirection`. On MoOS that property is "
            "LeftToRight in every session including Arabic ones, because MoOS ships bilingual "
            "QML strings rather than Qt catalogues (see org/moos/ui/Locale.qml). Take the "
            "direction from `MoUI.Locale.rtl` instead.")
    if "MoUI.Locale.rtl" not in body:
        errors.append("the switcher never reads `MoUI.Locale.rtl`, so nothing mirrors it for an "
                      "Arabic reader. `LayoutMirroring.enabled` must follow the locale.")
    if "LayoutMirroring.enabled" not in body:
        errors.append("nothing sets `LayoutMirroring.enabled`, so the strip cannot mirror.")

    # 2. Motion.
    if "Kirigami.Units.longDuration > 1" not in body:
        errors.append("the switcher does not derive `motionEnabled` from "
                      "`Kirigami.Units.longDuration > 1`, which is how Plasma's reduced-motion "
                      "setting reaches QML.")
    for match in re.finditer(r"^\s*(\w*[Dd]uration)\s*:\s*(.+)$", body, flags=re.M):
        key, value = match.group(1), match.group(2).strip()
        if "Tokens.duration(" not in value and value not in {"0"}:
            errors.append(f"`{key}: {value}` is not guarded - every duration must go through "
                          "`MoUI.Tokens.duration(tabBox.motionEnabled, ...)` so that reduced "
                          "motion stops it rather than shortening it.")
    for match in re.finditer(r"SpringFeedback\s*\{(.*?)\n(\s*)\}", body, flags=re.S):
        if "active:" not in match.group(1) or "motionEnabled" not in match.group(1):
            errors.append("a SpringFeedback is not bound to `motionEnabled`; with animations off "
                          "it would still spring.")

    # 3. No lost capability, no dead button.
    if "tabBox.model.close(" not in body:
        errors.append("nothing calls `tabBox.model.close(index)`. The stock layout could close a "
                      "window from the switcher; MoOS must not drop that capability silently.")
    for match in re.finditer(r"IconButton\s*\{(.*?)\n(\s{24})\}", body, flags=re.S):
        if "onClicked:" not in match.group(1):
            errors.append("an IconButton in the switcher has no `onClicked` - AGENTS.md forbids "
                          "a button that does nothing.")

    # Secondary ink follows the W6 contrast repair, never the disabled role.
    if "disabledTextColor" in body:
        errors.append("the switcher paints text with `disabledTextColor`; that role measures "
                      "1.6:1 as secondary text on the light schemes (see "
                      "tests/test_secondary_text_contrast.py).")

    # The wiring: KWin has to be told to use it, for both switchers.
    kwinrc = KWINRC.read_text(encoding="utf-8")
    for group in ("TabBox", "TabBoxAlternative"):
        selected = config_value(kwinrc, group, "LayoutName")
        if selected != PACKAGE_ID:
            errors.append(f"etc/xdg/kwinrc [{group}] LayoutName is {selected!r}, not "
                          f"{PACKAGE_ID!r}; the package would ship and never be shown.")

    # The package identifies itself as MoOS's, and as the kind of package KWin looks for.
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    if metadata.get("KPackageStructure") != "KWin/WindowSwitcher":
        errors.append("metadata.json does not declare KPackageStructure KWin/WindowSwitcher, so "
                      "KWin will not list it as a switcher at all.")
    if metadata.get("KPlugin", {}).get("Id") != PACKAGE_ID:
        errors.append(f"metadata.json's KPlugin.Id must be {PACKAGE_ID!r} - it is what kwinrc "
                      "names and what the directory is called.")

    if errors:
        print("GATE FAIL: tests/test_moos_switcher.py")
        for error in errors:
            print(f" - {error}")
        return 1
    print("MoOS switcher gate passed (locale-driven direction, guarded motion, live close, "
          "selected for both switchers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
