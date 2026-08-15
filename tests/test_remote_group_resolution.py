#!/usr/bin/env python3
"""Gate: a named keyboard group must resolve to THAT group, not to the user's own.

WHY THIS EXISTS

Both keymap tables in this project — AraKeymap and UsKeymap — work by POSITION, and a position is
only deterministic once the group is known. That is their whole premise: KWin resolves an injected
keysym against the active group at shift level one only, so anything above level one (every Arabic
diacritic, every ASCII symbol) has to be sent as a position on a group we have selected.

`select_group()` resolved names like this:

    idx = layout_state["ara"] if name == "ara" else layout_state["home"]

Every name that was not "ara" silently became the user's OWN layout. That was harmless while "ara"
and "home" were the only names anyone asked for, and it stopped being harmless the moment UsKeymap
started asking for "us" to type symbols: the request resolved to `home`, the batch typed US
positions on the GERMAN group, and the user got German faces. Measured live on this machine with
the exact positions UsKeymap emits for `@ / - ;` while group 0 (de) was active:

    expected  @ / - ;
    got       " - ß ö

and on the real `us` group the same positions produced `@/-;` correctly.

Nothing failed. No warning, no dropped run, no log line — the text simply arrived wrong, which is
the worst shape a bug can have, and it is why this is gated rather than left to review.

THE SECOND HALF: THE WARNING MUST NAME THE GROUP THAT IS MISSING

`warned` was a single bool guarding a hard-coded Arabic message, so a machine without a `us` group
told its owner to install an ARABIC keyboard. It is a set of names now, and the message is built
from the name, so one missing layout no longer mutes the report for another.
"""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"


def main() -> int:
    raw = HELPER.read_text(encoding="utf-8")
    # Strip # comments AND docstrings. This file explains its own history in prose, and the first
    # version of this gate matched the OLD expression quoted inside _group_index's docstring — a
    # gate that fires on its own explanation is worse than no gate.
    code = re.sub(r'"""(?:.|\n)*?"""', "", raw)
    code = "\n".join(l for l in code.splitlines() if not l.lstrip().startswith("#"))
    errors: list[str] = []

    # 1. The aliasing ASSIGNMENT must be gone — matched as an assignment, not as a mention.
    if re.search(r'idx\s*=\s*layout_state\["ara"\]\s+if\s+name\s*==\s*"ara"\s+else\s+layout_state\["home"\]', code):
        errors.append(
            'select_group still resolves every non-"ara" name to layout_state["home"]. A request '
            'for "us" then types US positions on the user\'s own layout and produces its faces '
            '(measured: @ / - ; arrived as \" - ß ö on a German group).')

    # 2. There must be a real resolver that looks the name up in the live ring.
    fn = re.search(r"def _group_index\(name\):(.*?)(?=\ndef )", code, re.S)
    if not fn:
        errors.append("no _group_index(name) resolver — a named group cannot be looked up at all.")
    else:
        body = fn.group(1)
        if 'layout_state["codes"]' not in body:
            errors.append("_group_index does not consult layout_state['codes'], so it cannot "
                          "resolve any group the machine actually has beyond the two cached ones.")
        if "startswith(name)" not in body:
            errors.append("_group_index does not match the requested name against the ring; a "
                          "layout code like 'us' or 'ara(qwerty)' must be found by prefix.")
        for cached in ('"home"', '"ara"'):
            if cached not in body:
                errors.append(f"_group_index no longer honours the cached {cached} index, which is "
                              f"resolved once at startup and must keep working.")

    # 3. select_group must USE it.
    sg = re.search(r"def select_group\(name, send\):(.*?)(?=\ndef )", code, re.S)
    if not sg:
        errors.append("could not find select_group(name, send).")
    elif "_group_index(name)" not in sg.group(1):
        errors.append("select_group does not call _group_index(name).")

    # 4. The warning must be per-name and must not hard-code Arabic.
    if re.search(r'layout_state\["warned"\]\s*=\s*True', code):
        errors.append('layout_state["warned"] is still a bool being set to True, so the first '
                      "missing layout mutes the warning for every other one.")
    if sg and "no Arabic keyboard layout is configured" in sg.group(1):
        errors.append("select_group still hard-codes the Arabic message for every failure — a "
                      "machine missing a 'us' group would be told to install an Arabic keyboard.")

    # 5. And the state must be initialised as a set, or `not in` / `.add` would throw.
    if not re.search(r'"warned":\s*set\(\)', code):
        errors.append('layout_state["warned"] is not initialised as a set(), so the per-name '
                      "guard would raise instead of warning.")

    if errors:
        print("GATE FAIL: a keyboard group request could silently land on the wrong layout.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: named groups resolve against the live layout ring, cached home/ara still work, and "
          "a missing layout is reported by name.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
