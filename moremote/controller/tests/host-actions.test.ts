import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { actionGroups, hostKindFrom, COMBO_MODIFIERS, type KeyAction } from "../src/lib/hostActions.ts";
import { t } from "../src/lib/i18n.ts";

// A quick-action tile is a button, and a button whose keys the agent cannot press is a dead
// button. So this reads the AGENTS' OWN key tables and proves every tile is pressable on the host
// it is offered for — not merely that the table looks plausible.
const here = dirname(fileURLToPath(import.meta.url));
const linux = readFileSync(resolve(here, "../../agent-linux/InputInjector.cs"), "utf8");
const windows = readFileSync(resolve(here, "../../agent/Core/InputInjector.cs"), "utf8");

function table(source: string, name: string): Set<string> {
  const start = source.indexOf(name);
  assert.ok(start >= 0, `agent table ${name} not found`);
  const body = source.slice(start, source.indexOf("};", start));
  return new Set([...body.matchAll(/\["([^"]+)"\]\s*=/g)].map((m) => m[1].toLowerCase()));
}

const linuxModifiers = table(linux, "Dictionary<string, ushort> Modifiers");
const linuxKeys = table(linux, "Dictionary<string, ushort> Keys");
const linuxPhysical = table(linux, "PhysicalCodes");
const windowsKeys = table(windows, "var m = new Dictionary<string, ushort>");
const windowsPhysical = table(windows, "Dictionary<string, Scan> PhysicalScan");

const printable = (k: string) => k.length === 1 && k > " " && k <= "~";

function linuxCanPress(a: KeyAction): string | null {
  if (a.kind === "code") return linuxPhysical.has(a.code.toLowerCase()) ? null : `no physical ${a.code}`;
  if (a.kind === "tap") return linuxKeys.has(a.key.toLowerCase()) ? null : `no key ${a.key}`;
  for (const k of a.keys) {
    if (linuxModifiers.has(k.toLowerCase())) continue;
    if (printable(k) || linuxKeys.has(k.toLowerCase())) continue;
    return `combo key ${k} is neither a modifier, a printable character nor a named key`;
  }
  return a.keys.some((k) => !linuxModifiers.has(k.toLowerCase())) ? null : "a combo of modifiers only";
}

function windowsCanPress(a: KeyAction): string | null {
  if (a.kind === "code") return windowsPhysical.has(a.code.toLowerCase()) ? null : `no physical ${a.code}`;
  const keys = a.kind === "tap" ? [a.key] : a.keys;
  for (const k of keys) {
    // KeyMap adds A-Z, 0-9 and F1-F12 in a loop after the literal entries.
    if (/^[a-z0-9]$/i.test(k) || /^F([1-9]|1[0-2])$/.test(k) || windowsKeys.has(k.toLowerCase())) continue;
    return `Windows KeyMap cannot press ${k}`;
  }
  return null;
}

for (const kind of ["moos", "windows"] as const) {
  const ids = new Set<string>();
  for (const group of actionGroups(kind)) {
    assert.notEqual(t("en", group.title as never), group.title, `group ${group.title} has no translation`);
    assert.notEqual(t("ar", group.title as never), group.title, `group ${group.title} has no Arabic`);
    for (const action of group.actions) {
      assert.ok(!ids.has(action.id), `${kind}: duplicate action ${action.id}`);
      ids.add(action.id);
      assert.notEqual(t("en", action.label as never), action.label, `${action.label} has no translation`);
      assert.notEqual(t("ar", action.label as never), action.label, `${action.label} has no Arabic`);
      if (action.send.kind === "combo")
        assert.ok(action.send.keys.some((k) => (COMBO_MODIFIERS as readonly string[]).includes(k)),
          `${kind}/${action.id}: a combo without a modifier belongs to tap()`);
      const why = kind === "moos" ? linuxCanPress(action.send) : windowsCanPress(action.send);
      assert.equal(why, null, `${kind}/${action.id} would be a dead tile: ${why}`);
    }
  }
  assert.ok(ids.size >= 18, `${kind}: the quick actions shrank to ${ids.size}`);
}

assert.equal(hostKindFrom("Win32 SendInput"), "windows");
assert.equal(hostKindFrom("KWin EIS"), "moos");
assert.equal(hostKindFrom(undefined), "moos");
assert.equal(hostKindFrom(""), "moos");

// The MoOS shortcuts the tiles name, as read back from a MoOS session on 2026-10-06. A change
// here is a deliberate decision about which desktop command a tile presses.
const moos = Object.fromEntries(actionGroups("moos").flatMap((g) => g.actions).map((a) => [a.id, a.send]));
assert.deepEqual(moos.mira, { kind: "combo", keys: ["Meta", "Space"] }, "Mira is Meta+Space (org.moos.moai)");
assert.deepEqual(moos.search, { kind: "combo", keys: ["Alt", "Space"] }, "KRunner is Alt+Space");
assert.deepEqual(moos.overview, { kind: "combo", keys: ["Meta", "w"] }, "KWin Overview is Meta+W");
assert.deepEqual(moos.launcher, { kind: "tap", key: "Meta" }, "the launcher opens on a lone Meta");
assert.deepEqual(moos.shot, { kind: "code", code: "PrintScreen" }, "Spectacle listens on Print");

console.log("PASS: every MoOS and Windows quick action is a key the agent can actually press");
