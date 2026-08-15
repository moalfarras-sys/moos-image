#!/usr/bin/env python3
"""Gate: the controller's toolbar edge must be decided by ONE query, in CSS and in JS.

WHY THIS EXISTS

The bottom edge of the window is not the controller's to use. The remote MoOS desktop keeps its
Horizon Bar bottom-centred — `moos-bar.conf` ships `location=bottom` / `alignment=center`, and the
live cloud accounts read back `location=4` — so a controller bar parked there covers the dock the
user is reaching for. On a pointer machine it is worse than cosmetic: the bottom strip is also the
hover-summon gesture, so reaching for the remote's dock made our own bar rise under the pointer and
take the click.

Two files have to agree about this. styles.css POSITIONS the bar; RemoteScreen decides which edge
SUMMONS it. If they disagree the gesture opens a door on the opposite wall — the bar is at the top
and the strip that reveals it is at the bottom, or the reverse. Nothing errors; it just feels
broken. So both read one exported constant, and this gate asserts the stylesheet really does carry
it verbatim.

AND WHY THE QUERY IS `any-*`

It used to be `(hover: hover) and (pointer: fine)`. Those test the PRIMARY pointer, and on a Windows
touchscreen laptop the primary pointer is the touchscreen even with a mouse and trackpad attached.
So `pointer: fine` is FALSE on a very ordinary computer, the rule never applied, and the bar sat at
the bottom on top of the dock — the reported symptom. RemoteScreen already documents the same trap
for gesture mode ("A touchscreen laptop therefore starts in touch mode"), and a browser that
declines to answer pointer queries at all — headless Firefox does — fell into the same hole and got
a phone layout in a 1280x860 window.

`any-hover`/`any-pointer` ask whether a fine hovering pointer is AVAILABLE. The viewport clause
covers the browser that answers nothing: at least 900px wide in landscape is not a phone. A phone in
landscape is under 900px and is caught by the short-landscape rail rule, which is declared later and
deliberately still wins.
"""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "moremote/controller/src/styles.css"
TYPES = ROOT / "moremote/controller/src/types.ts"
SCREEN = ROOT / "moremote/controller/src/ui/RemoteScreen.tsx"


def main() -> int:
    errors: list[str] = []
    css = CSS.read_text(encoding="utf-8")
    types = TYPES.read_text(encoding="utf-8")
    screen = SCREEN.read_text(encoding="utf-8")

    m = re.search(r'export const POINTER_BAR_QUERY\s*=\s*\n?\s*"([^"]+)"', types)
    if not m:
        print("GATE FAIL:\n  - types.ts does not export POINTER_BAR_QUERY as a string literal.")
        return 1
    query = m.group(1)

    # 1. The primary-pointer form must be gone from BOTH files: it is the actual defect.
    stale = "(hover: hover) and (pointer: fine)"
    if stale in css:
        errors.append(
            f"styles.css still uses {stale!r}. That tests the PRIMARY pointer, which is the "
            f"touchscreen on a Windows touchscreen laptop, so the toolbar stays at the bottom "
            f"covering the remote's dock.")
    if stale in screen:
        errors.append(f"RemoteScreen.tsx still hard-codes {stale!r} instead of POINTER_BAR_QUERY.")

    # 2. The query must ask about AVAILABLE pointers, not the primary one.
    if "any-hover" not in query or "any-pointer" not in query:
        errors.append(
            "POINTER_BAR_QUERY does not use any-hover/any-pointer, so a touchscreen laptop with a "
            "mouse is still classed as a phone.")

    # 3. The stylesheet must carry the constant VERBATIM, or the two halves have drifted.
    occurrences = css.count(f"@media {query} {{")
    if occurrences < 2:
        errors.append(
            f"styles.css contains {occurrences} `@media <POINTER_BAR_QUERY>` block(s); expected at "
            f"least 2 (the toolbar itself and the .show-tab handle that must move with it). CSS and "
            f"JS must agree on the edge or the summon gesture opens the opposite wall.")

    # 4. JS must read the constant rather than a copy of the string.
    if "matchMedia(POINTER_BAR_QUERY)" not in screen:
        errors.append("RemoteScreen.tsx does not call matchMedia(POINTER_BAR_QUERY).")

    # 5. The short-landscape rail must still be declared AFTER the pointer block, because both can
    #    match on a small landscape screen and source order is what makes the rail win.
    pointer_at = css.find(f"@media {query} {{")
    rail_at = css.find("@media (orientation: landscape) and (max-height: 520px)")
    if pointer_at >= 0 and rail_at >= 0 and rail_at < pointer_at:
        errors.append(
            "the short-landscape rail is declared BEFORE the pointer block; media queries add no "
            "specificity, so the pointer block would now win and a phone in landscape would lose "
            "its vertical rail.")

    if errors:
        print("GATE FAIL: the toolbar could sit on the remote desktop's dock.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: one POINTER_BAR_QUERY drives both the CSS placement and the JS summon edge, it asks "
          "about available pointers, and the short-landscape rail still wins.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
