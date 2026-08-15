#!/usr/bin/env python3
"""Gate: every input path that can move the caret must flush pending text first.

WHY THIS EXISTS

The agent GATHERS text before typing it. That is deliberate and load-bearing: Arabic cannot be
typed by keysym on a Latin group, so it is typed by keymap group as one ordered batch, and
gathering turns a sentence into one switch-type-restore instead of one per letter.

A key or a click that arrives while a batch is still gathering therefore has to deliver the batch
FIRST, or it lands in the middle of the user's own sentence. KeyTap says so in its own comment —
"letting a key overtake a pending paste would reorder the edit" — and KeyTap, KeyDown, Click,
DoubleClick, ClickCurrent, MouseButton and MouseButtonCurrent all call FlushPendingText().

`KeyCode` did not. And `KeyCode` is exactly the path a COMPUTER browser uses: DesktopInput routes
any key whose character matches its US position by POSITION (decideKey -> "physical"), which
includes Space, Enter, Tab and every digit. Arabic letters do not match a US position, so they go
the other way, as `text`.

So one Arabic sentence typed from a desktop browser travelled two mechanisms at once, and the
physical half jumped the queue. The owner reported it in the mangled Arabic it produces — spaces
landing inside words, letters arriving after the space that should have followed them. From the
server there is nothing to see: every keystroke arrives, is accepted, and is injected.

`KeyUp` deliberately does NOT flush, and neither does the release edge of KeyCode: a release cannot
reorder an edit, because the press that owns it already flushed, and flushing on every release
would defeat the gathering entirely. That asymmetry is asserted too, so a later "fix" that flushes
unconditionally is caught here rather than in a bug report about Arabic being slow again.
"""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
INJECTOR = ROOT / "moremote/agent-linux/InputInjector.cs"


def body_of(code: str, signature: str) -> str | None:
    """The braced body of a method, by its signature line."""
    i = code.find(signature)
    if i < 0:
        return None
    j = code.find("{", i)
    if j < 0:
        return None
    depth, k = 0, j
    while k < len(code):
        if code[k] == "{":
            depth += 1
        elif code[k] == "}":
            depth -= 1
            if depth == 0:
                return code[j:k + 1]
        k += 1
    return None


def main() -> int:
    raw = INJECTOR.read_text(encoding="utf-8")
    # Strip comments so prose can never satisfy this gate.
    code = re.sub(r"//.*?$", "", raw, flags=re.M)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)

    errors: list[str] = []

    # 1. The paths that MUST flush.
    must_flush = [
        "public void KeyCode(string code, bool down)",
        "public void KeyTapCode(string code)",
        "public void KeyTap(string k)",
        "public void KeyDown(string k)",
    ]
    for sig in must_flush:
        b = body_of(code, sig)
        if b is None:
            errors.append(f"could not find {sig!r} — has it been renamed?")
        elif "FlushPendingText()" not in b:
            errors.append(
                f"{sig!r} does not call FlushPendingText(). A key that arrives while a text batch "
                f"is still gathering will overtake it, which scrambles Arabic typed from a desktop "
                f"browser (Space/Enter/digits go by position, Arabic goes as text).")

    # 2. KeyCode must flush only on the DOWN edge, or the gathering is defeated.
    b = body_of(code, "public void KeyCode(string code, bool down)")
    if b and "FlushPendingText()" in b:
        if not re.search(r"if\s*\(\s*down\s*\)\s*FlushPendingText\(\)", b):
            errors.append(
                "KeyCode flushes unconditionally. A release cannot reorder an edit — the press that "
                "owns it already flushed — and flushing on every key-up defeats the gathering that "
                "makes Arabic one batch instead of one round trip per letter.")

    # 3. KeyUp must NOT flush, for the same reason.
    b = body_of(code, "public void KeyUp(string k)")
    if b is None:
        errors.append("could not find KeyUp — has it been renamed?")
    elif "FlushPendingText()" in b:
        errors.append("KeyUp flushes; a release must not, or gathering is defeated on every letter.")

    if errors:
        print("GATE FAIL: a keystroke could overtake text that is still gathering.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: every press path flushes pending text first, releases do not, and KeyCode flushes "
          "only on the down edge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
