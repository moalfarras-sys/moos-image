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
5.  every menu entry it offers has a handler, because `AGENTS.md` forbids a dead action;
6.  the automatic arrangement (owner steering 2026-11-23: two programs split the screen,
    four take a quarter each) runs from real add/remove/minimise signals: halves, main and
    two, quarters, a fifth window floating, a lone survivor taking the area, portrait rows,
    a window that cannot shrink refusing the layout, dialogs ignored, and the Meta+Alt+A
    toggle with its on-screen notice. The previous script, which had none of it, must fail.
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
            get clientGeometry() { return geometry; },
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


def auto_contract(source: str) -> subprocess.CompletedProcess[str]:
    """Drive the automatic arrangement through private signals; never contact KWin."""
    harness = r"""
const vm = require("node:vm");
const assert = require("node:assert/strict");
function signal() { const slots = []; return {connect(f) { slots.push(f); }, emit(...a) { for (const f of slots) f(...a); }}; }
function desk(area) {
    const output = {geometry: {...area}}; const stack = []; const added = signal(); const removed = signal();
    const shortcuts = {}; const osd = []; let menu; let serial = 0;
    const context = {console: {info() {}}, KWin: {MaximizeArea: 1},
        callDBus(...a) { osd.push(a.join(" ")); },
        registerShortcut(n, t, k, f) { shortcuts[n] = f; }, registerUserActionsMenu(f) { menu = f; },
        workspace: {currentDesktop: "current", currentActivity: "here", stackingOrder: stack, activeWindow: null,
            windowAdded: added, windowRemoved: removed, windowList() { return stack.slice(); },
            screens: [output], screensChanged: signal(),
            clientArea(option, w) { return w.output.geometry; }}};
    vm.runInNewContext(SOURCE, context);
    function open(extra = {}) {
        let g = {x: 300 + 40 * serial, y: 200, width: 400, height: 300};
        const w = Object.assign({internalId: "w" + (++serial), normalWindow: true, minimized: false,
            skipTaskbar: false, skipSwitcher: false, fullScreen: false, desktops: [], output,
            moveable: true, resizeable: true, writes: 0, minimizedChanged: signal(),
            get clientGeometry() { return {width: g.width - (this.borderWidth || 0), height: g.height - (this.borderHeight || 0)}; },
            get frameGeometry() { return g; }, set frameGeometry(v) { ++w.writes; g = v; }}, extra);
        stack.push(w); context.workspace.activeWindow = w; added.emit(w); return w;
    }
    function close(w) { stack.splice(stack.indexOf(w), 1); removed.emit(w); }
    function resize(bounds, display = output) {
        Object.assign(display.geometry, bounds);
        context.workspace.screensChanged.emit();
    }
    return {open, close, resize, shortcuts, osd, menu: () => menu, ctx: context};
}
const wide = {x: 0, y: 0, width: 1280, height: 720};
const d = desk(wide);
const a = d.open();
assert.equal(a.writes, 0, "a lone window keeps its size");
const b = d.open();
assert.ok(a.writes > 0 && b.writes > 0, "two programs must split the screen");
assert.equal(a.frameGeometry.width, b.frameGeometry.width, "halves are equal");
assert.notEqual(a.frameGeometry.x, b.frameGeometry.x, "halves sit side by side");
assert.ok(Math.abs(a.frameGeometry.width - 628) <= 1, "half of the Bar-aware area: " + a.frameGeometry.width);
const c = d.open();
assert.equal(new Set([a, b, c].map(w => w.frameGeometry.x + ":" + w.frameGeometry.y)).size, 3, "three distinct cells");
const e = d.open();
const quarters = [a, b, c, e].map(w => w.frameGeometry);
assert.ok(quarters.every(g => Math.abs(g.width - 628) <= 1 && Math.abs(g.height - 348) <= 1), "four programs take quarters: " + JSON.stringify(quarters));
assert.equal(new Set(quarters.map(g => g.x + ":" + g.y)).size, 4, "four distinct quarters");
const f = d.open();
assert.equal(f.writes, 0, "a fifth window floats");
d.close(f); d.close(e); d.close(c); d.close(b);
assert.equal(JSON.stringify(a.frameGeometry), JSON.stringify({x: 8, y: 8, width: 1264, height: 704}), "the last arranged window takes the area");
const dialog = desk(wide); dialog.open(); const sheet = dialog.open({normalWindow: false});
assert.equal(sheet.writes, 0, "dialogs are never arranged");
const tall = desk({x: 0, y: 0, width: 720, height: 1280});
const t1 = tall.open(); const t2 = tall.open();
assert.equal(t1.frameGeometry.x, t2.frameGeometry.x, "portrait stacks the two windows");
assert.notEqual(t1.frameGeometry.y, t2.frameGeometry.y, "portrait rows differ");
const rotate = desk(wide);
const pair = [rotate.open(), rotate.open()];
const startingSides = pair.map(w => w.frameGeometry.x);
const second = {geometry: {x: 1280, y: 0, width: 1600, height: 900}};
rotate.ctx.workspace.screens.push(second);
rotate.ctx.workspace.screensChanged.emit();
const otherPair = [rotate.open({output: second}), rotate.open({output: second})];
const otherWrites = otherPair.map(w => w.writes);
const portrait = {x: 0, y: 0, width: 720, height: 1280};
rotate.resize(portrait);
assert.deepEqual(pair.map(w => [w.frameGeometry.y, w.frameGeometry.width, w.frameGeometry.height]).sort((a,b) => a[0]-b[0]),
    [[8,704,628], [644,704,628]], "existing windows stack after rotation without another window opening");
assert.deepEqual(otherPair.map(w => w.writes), otherWrites, "changing one output leaves the other pair alone");
const rotatedWrites = pair.map(w => w.writes);
rotate.resize(portrait);
assert.deepEqual(pair.map(w => w.writes), rotatedWrites, "unchanged logical bounds do not overwrite personal sizing");
rotate.resize(wide);
assert.deepEqual(pair.map(w => w.frameGeometry.x), startingSides, "rotating back retains each window's side");
const constrained = desk(wide);
const fixedPair = [constrained.open(), constrained.open({minSize: {width: 610, height: 150}})];
const fixedWrites = fixedPair.map(w => w.writes);
constrained.resize({x: 0, y: 0, width: 1024, height: 576});
assert.deepEqual(fixedPair.map(w => w.writes), fixedWrites, "a scale change must respect both windows' client limits");
const wideApp = desk(wide); const w1 = wideApp.open(); const w2 = wideApp.open({minSize: {width: 900, height: 200}});
assert.equal(w1.writes + w2.writes, 0, "a program that cannot shrink to its half refuses the layout");
const capped = desk(wide); const cap1 = capped.open();
const cap2 = capped.open({maxSize: {width: 380, height: 800}});
assert.equal(cap1.writes + cap2.writes, 0, "refuse a split a size-capped window cannot fill");
// A quarter has 348 logical pixels for the frame, including the decoration.
const decorated = desk(wide);
const group = [decorated.open(), decorated.open(), decorated.open()];
const placements = group.map(w => w.writes);
const limited = decorated.open({borderHeight: 28, minSize: {width: 150, height: 346}});
assert.deepEqual(group.map(w => w.writes), placements, "preflight every client before the first move");
assert.equal(limited.writes, 0, "346 client pixels and a 28px title bar do not fit in 348");
decorated.shortcuts["MoOS Arrange: quarters"]();
assert.deepEqual(group.map(w => w.writes), placements, "the keyboard shortcut must use the same limits");
assert.equal(limited.writes, 0);
const manual = desk(wide);
manual.shortcuts["MoOS Arrange: auto"]();
const normal = manual.open();
const large = manual.open({minSize: {width: 1000, height: 250}});
manual.menu()(normal).items[0].triggered();
assert.equal(normal.writes + large.writes, 0, "a later window must veto the whole menu action");
manual.shortcuts["MoOS Arrange: centre"]();
assert.equal(large.writes, 0, "centring must keep the client's minimum");
const last = desk(wide);
const bounded = last.open({borderWidth: 8, borderHeight: 28, maxSize: {width: 620, height: 676}});
const peer = last.open();
assert.equal(bounded.frameGeometry.width, 628, "a 620px client with 8px of borders fills a half");
assert.equal(bounded.frameGeometry.height, 704, "the title bar does not count against the client maximum");
const halfWrites = bounded.writes;
last.close(peer);
assert.equal(bounded.writes, halfWrites, "do not expand a capped survivor beyond its maximum");
const odd = desk({x: 17, y: 54, width: 1281, height: 721});
const fourOdd = [odd.open(), odd.open(), odd.open(), odd.open()].map(w => w.frameGeometry);
assert.equal(Math.max(...fourOdd.map(g => g.x+g.width)), 17+1281-8, "exact trailing margin");
assert.equal(Math.max(...fourOdd.map(g => g.y+g.height)), 54+721-8, "exact bottom margin");
const separate = desk(wide); const visible = separate.open();
separate.open({activities: ["other"]});
assert.equal(visible.writes, 0, "a different activity cannot trigger a split here");
const unrelated = separate.open({normalWindow:false});
separate.close(unrelated);
assert.equal(visible.writes,0,"closing a dialog should not retile the current windows");
const real = separate.open();
const prior = real.writes;
separate.close(separate.open({normalWindow:false}));
assert.equal(real.writes, prior, "closing a transient should preserve manual placement");
const off = desk(wide); off.shortcuts["MoOS Arrange: auto"]();
assert.ok(off.osd.some(s => s.includes("Auto arrange: off")), "toggling shows the notice");
const o1 = off.open(); const o2 = off.open();
off.resize(portrait);
assert.equal(o1.writes + o2.writes, 0, "turned off, nothing moves");
const item = off.menu()(o1).items.find(i => i.checkable);
assert.ok(item && typeof item.triggered === "function" && item.checked === false, "the menu shows the checkable state");
"""
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
        automatic = auto_contract(source)
        if automatic.returncode:
            errors.append("automatic arrangement contract failed: " + automatic.stderr[-2500:])
        # A script that never arranges by itself (the mode forced off, as before
        # 2026-11-23) must fail the same contract, or the contract proves nothing.
        disabled = source.replace('let autoArrange = setting("AutoArrange", true);',
                                  'let autoArrange = false;')
        if disabled == source or auto_contract(disabled).returncode == 0:
            errors.append("a script with the automatic arrangement switched off passed its contract")

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
