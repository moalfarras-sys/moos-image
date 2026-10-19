#!/usr/bin/env python3
"""Gate: MoOS Arrange keeps the properties that were measured on a live KWin, not assumed.

WHY THIS EXISTS

MoOS Arrange is a KWin script, and a KWin script is plain JavaScript evaluated inside KWin
with no type checking of any kind. A property that does not exist reads as `undefined`, and
`undefined` in the middle of an `&&` chain makes the whole chain falsy — silently. That is
not hypothetical: the first version of this script filtered candidate windows on
`window.onCurrentDesktop`, which **does not exist on KWin 6.7.5**. Every window was rejected,
the script cheerfully logged "nothing to arrange on this screen", and only running it on the
station and reading the live window object showed why. Virtual-desktop membership is the
`desktops` array, where an EMPTY array means "on all desktops" rather than "on none".

The same trap sits under the spelling of `moveable` and `resizeable`: KWin 6.7.5 answers to
those two, with the e, and reads `movable`/`resizable` as undefined. Both spellings appear in
`libkwin.so.6.7.5`, so grepping the binary cannot settle it and only the live object can.

So this gate pins the three things that were measured rather than guessed, plus the two that
make the feature real rather than shipped:

1.  it never reads `onCurrentDesktop`, and it does decide desktop membership from `desktops`;
2.  it uses the `moveable`/`resizeable` spellings KWin actually answers to;
3.  it arranges into `MaximizeArea`, so windows clear the MoOS Bar instead of sliding under it;
4.  kwinrc enables it — a script nothing enables is a file, not a feature;
5.  every menu entry it offers has a handler, because `AGENTS.md` forbids a dead action.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "system_files/usr/share/kwin/scripts/moos-arrange"
SCRIPT = PACKAGE / "contents/code/main.js"
METADATA = PACKAGE / "metadata.json"
KWINRC = ROOT / "system_files/etc/xdg/kwinrc"


def runtime_contract(source: str) -> subprocess.CompletedProcess[str]:
    """Execute actual callbacks with private window objects; never contact KWin."""
    harness = r'''
const vm = require("node:vm");
const assert = require("node:assert/strict");
function run(override, kind, throughMenu = false) {
    let writes = 0;
    const output = {};
    function window(extra = {}) {
        let geometry = {x: 10, y: 10, width: 500, height: 400};
        return Object.assign({normalWindow: true, minimized: false, skipTaskbar: false,
            skipSwitcher: false, fullScreen: false, desktops: [], output,
            moveable: true, resizeable: true,
            get frameGeometry() { return geometry; },
            set frameGeometry(value) { ++writes; geometry = value; }}, extra);
    }
    const leader = window();
    const other = window();
    const shortcuts = {};
    let menu;
    const context = {console: {info() {}}, KWin: {MaximizeArea: 1},
        workspace: {activeWindow: leader, currentDesktop: "current", stackingOrder: [other, leader],
            clientArea() { return {x: 0, y: 0, width: 1280, height: 720}; }},
        registerShortcut(name, text, keys, callback) { shortcuts[name] = callback; },
        registerUserActionsMenu(callback) { menu = callback; }};
    vm.runInNewContext(SOURCE, context);
    const item = throughMenu ? menu(leader).items[kind === "centre" ? 4 : 0] : null;
    Object.assign(leader, override);
    if (item) item.triggered();
    else shortcuts["MoOS Arrange: " + kind]();
    return writes;
}
for (const kind of ["centre", "halves", "thirds", "quarters", "main"]) {
    assert.ok(run({}, kind) > 0, kind + " must place eligible windows");
    for (const excluded of [{fullScreen: true}, {normalWindow: false}, {minimized: true},
             {skipTaskbar: true}, {skipSwitcher: true}, {moveable: false},
             {resizeable: false}, {desktops: ["elsewhere"]}]) {
        assert.equal(run(excluded, kind), 0, kind + " moved windows from excluded anchor " + JSON.stringify(excluded));
    }
}
assert.equal(run({fullScreen: true}, "centre", true), 0, "menu must revalidate its anchor");
assert.equal(run({resizeable: false}, "halves", true), 0, "stale menu must not rearrange other windows");
'''
    return subprocess.run([shutil.which("node") or "node", "-e",
                           "const SOURCE = " + json.dumps(source) + ";\n" + harness],
                          text=True, capture_output=True, timeout=15)


def code(text: str) -> str:
    """The script without comments, so a comment ABOUT a trap is not read as the trap."""
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

    for path in (SCRIPT, METADATA):
        if not path.is_file():
            print(f"GATE FAIL: {path.relative_to(ROOT)} is missing — KWin reads both of these "
                  "files by name")
            return 1

    body = code(SCRIPT.read_text(encoding="utf-8"))

    # 1. The property that does not exist, and the one that does.
    # The PROPERTY read, not the word: this file's own helper is called
    # isOnCurrentDesktop, and naming a concept is not using the broken API.
    if re.search(r"\.onCurrentDesktop\b", body):
        errors.append(
            "the script reads `onCurrentDesktop`. That property does not exist on KWin 6.7.5: "
            "it reads as undefined, which makes any `&&` chain containing it falsy, so NOTHING "
            "is ever arranged and the script says so instead of failing. Decide desktop "
            "membership from `window.desktops` (an empty array means all desktops).")
    if "window.desktops" not in body and ".desktops" not in body:
        errors.append("nothing reads `desktops`, so the script cannot tell which virtual "
                      "desktop a window is on.")

    # 2. The spellings KWin answers to.
    for wrong, right in (("movable", "moveable"), ("resizable", "resizeable")):
        if re.search(rf"\.{wrong}\b", body):
            errors.append(f"`window.{wrong}` reads as undefined on KWin 6.7.5 and would reject "
                          f"every window; the property is `{right}`, with the e.")
    for needed in ("moveable", "resizeable"):
        if needed not in body:
            errors.append(f"the candidate filter never checks `{needed}`, so the script would "
                          "try to move a window the window manager will not move.")

    # 3. Arrange inside the area a maximised window gets, not the whole output.
    if "KWin.MaximizeArea" not in body:
        errors.append("the script does not use `workspace.clientArea(KWin.MaximizeArea, …)`. "
                      "Any other area includes the space the MoOS Bar occupies, so every "
                      "arranged window would slide under the Bar.")

    # 4. A script nothing enables is a file, not a feature.
    plugin_id = json.loads(METADATA.read_text(encoding="utf-8")).get("KPlugin", {}).get("Id")
    if plugin_id != "moos-arrange":
        errors.append(f"metadata.json's KPlugin.Id is {plugin_id!r}; kwinrc and the directory "
                      "name both say moos-arrange.")
    enabled = config_value(KWINRC.read_text(encoding="utf-8"), "Plugins",
                           f"{plugin_id}Enabled")
    if enabled != "true":
        errors.append(f"etc/xdg/kwinrc [Plugins] {plugin_id}Enabled is {enabled!r}, not 'true'.")

    # 5. No dead action: every menu entry carries a handler.
    entries = re.findall(r"items\.push\(\{(.*?)\}\)", body, flags=re.S)
    if not entries:
        errors.append("no window-menu entries are built, so the feature has no surface a "
                      "person can find.")
    for entry in entries:
        if "triggered" not in entry:
            errors.append("a window-menu entry has no `triggered` handler — AGENTS.md forbids "
                          "an action that does nothing.")
    if "registerShortcut(" not in body:
        errors.append("no shortcut is registered, so the arrangements are reachable only "
                      "through the menu.")

    if not shutil.which("node"):
        errors.append("Node.js is required to execute the private Arrange callback controls.")
    else:
        source = SCRIPT.read_text(encoding="utf-8")
        actual = runtime_contract(source)
        if actual.returncode:
            errors.append("Arrange callback contract failed: " + actual.stderr[-2500:])
        # The actual old implementation must fail the same executable contract.
        old = source.replace("if (!isArrangeable(leader))", "if (!leader)")
        negative = runtime_contract(old)
        if old == source or negative.returncode == 0:
            errors.append("old unfiltered-anchor negative did not fail the callback contract")

    if errors:
        print("GATE FAIL: tests/test_moos_arrange.py")
        for error in errors:
            print(f" - {error}")
        return 1
    print("MoOS Arrange gate passed (live-measured KWin properties, Bar-aware area, enabled, "
          f"{len(entries)} menu entries all wired)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
