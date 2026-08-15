#!/usr/bin/env python3
"""Gate: every printable ASCII character must be typeable, symbols included.

WHY THIS EXISTS

Latin text is injected as KEYSYMS, which KWin resolves against the active group at SHIFT LEVEL ONE
only — the same fact that forced AraKeymap to exist. So TryDirectStrokes covers a-z, 0-9 and space,
plus A-Z by pressing Shift explicitly, because uppercase is the one level-two case that is the same
on every Latin layout.

Every symbol is level two or higher, and its position is NOT layout-invariant: `@` is Shift+2 on US
and AltGr+Q on German. So any run containing a symbol returned false, and Deliver dropped the WHOLE
run with "Typing skipped N character(s) with no key on the available layouts". From the user's
side: paste a URL, a password or an email address into the remote and the symbols are missing, or
the line never arrives at all. That is what was reported — symbols not surviving a copy and paste.

UsKeymap fixes it the way AraKeymap already proved: select a KNOWN group and send POSITIONS, which
reach every level. This gate holds the two things that make that safe — total coverage of printable
ASCII, and agreement with the evdev codes InputInjector already uses for the same physical keys.
"""

from pathlib import Path
import re
import string
import sys


ROOT = Path(__file__).resolve().parents[1]
US = ROOT / "moremote/agent-linux/UsKeymap.cs"
INJECTOR = ROOT / "moremote/agent-linux/InputInjector.cs"


def main() -> int:
    us = US.read_text(encoding="utf-8")
    inj = INJECTOR.read_text(encoding="utf-8")
    errors: list[str] = []

    # ---- rebuild the table the way the C# does, from the same literals -------------------
    pairs = re.findall(r"\((\d+),\s*'((?:\\.|[^'])+)',\s*'((?:\\.|[^'])+)'\)", us)
    letters = re.findall(r"\((\d+),\s*'([a-z])'\)", us)

    def unesc(c: str) -> str:
        return {"\\\\": "\\", "\\'": "'"}.get(c, c)

    covered: dict[str, int] = {}
    for code, low, high in pairs:
        covered[unesc(low)] = int(code)
        covered[unesc(high)] = int(code)
    for code, ch in letters:
        covered[ch] = int(code)
        covered[ch.upper()] = int(code)
    for d, code in zip("1234567890", [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]):
        covered.setdefault(d, code)
    if "map[' '] = new Key(57, false)" in us:
        covered[" "] = 57

    # ---- 1. every printable ASCII character must be reachable ---------------------------
    missing = [c for c in string.printable[:95] if c not in covered]
    missing = [c for c in missing if c.isprintable()]
    if missing:
        errors.append(
            f"UsKeymap does not cover {len(missing)} printable ASCII character(s): {missing!r}. "
            f"A run containing one is dropped whole, which is how symbols vanished from a paste.")

    # ---- 2. the letter codes must agree with InputInjector.PhysicalCodes ----------------
    phys = dict(re.findall(r'\["Key([A-Z])"\]\s*=\s*(\d+)', inj))
    for letter, code in letters:
        want = phys.get(letter.upper())
        if want is not None and int(want) != int(code):
            errors.append(
                f"UsKeymap maps '{letter}' to evdev {code} but InputInjector.PhysicalCodes maps "
                f"Key{letter.upper()} to {want}. Two tables describing the same physical key must "
                f"not disagree.")

    # ---- 3. the fallback must actually be wired, and only as a FALLBACK ------------------
    if "UsKeymap.TryStrokes" not in inj:
        errors.append("InputInjector never calls UsKeymap.TryStrokes, so symbols are still dropped.")
    if 'events.Add(new { layout = "us" })' not in inj:
        errors.append("the US fallback does not select the `us` group; positions are only "
                      "deterministic once the group is known.")
    # It must come after the keysym attempt, or ordinary Latin text stops using the user's own
    # layout and pays a group switch per run for no reason.
    direct_at = inj.find("TryDirectStrokes(text, events)")
    us_at = inj.find("UsKeymap.TryStrokes(text, events)")
    if direct_at >= 0 and us_at >= 0 and us_at < direct_at:
        errors.append("UsKeymap is tried BEFORE the keysym path; it must be the fallback, or every "
                      "run of plain text pays a keyboard-group switch it does not need.")

    # ---- 4. shifted faces must actually press Shift --------------------------------------
    if not re.search(r"if \(k\.Shift\) events\.Add\(new \{ code = \(int\)Shift, down = true \}\)", us):
        errors.append("UsKeymap.TryStrokes does not press Shift for level-two characters, so every "
                      "symbol would type as its unshifted face (`2` instead of `@`).")

    if errors:
        print("GATE FAIL: symbols would not survive being typed into the remote.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: all {len(covered)} US positions cover printable ASCII, agree with PhysicalCodes, "
          f"press Shift for level two, and are used only as a fallback.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
