import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {dirname, resolve} from "node:path";
import {fileURLToPath} from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(here, "../src/ui/RemoteScreen.tsx"), "utf8");
const auth = readFileSync(resolve(here, "../src/ui/AuthScreens.tsx"), "utf8");

// Bottom sheets are true modal dialogs: focus enters them, Tab cannot escape,
// Escape closes, and the invoking toolbar control receives focus again.
for (const contract of [
  'role="dialog"',
  'aria-modal="true"',
  'tabIndex={-1}',
  'event.key === "Escape"',
  'event.key !== "Tab"',
  'previous?.focus()',
  'className="sheet-close"',
  '[contenteditable="true"]',
]) {
  assert.ok(source.includes(contract), `remote sheet misses ${contract}`);
}
assert.equal((source.match(/<SheetPanel label=/g) ?? []).length, 4,
  "Display, Settings, Files and Clipboard must all use the modal sheet contract");
assert.ok(!source.includes('<div className="sheet">'),
  "a raw visual-only sheet bypasses focus containment and Escape handling");

assert.match(source, /<button\s+type="button"\s+className=\{[\s\S]*?topbar[\s\S]*?aria-expanded=\{!compactBar\}/,
  "connection details must be a keyboard-operable disclosure button");
assert.match(source, /className="toast"\s+role="status"\s+aria-live="polite"/,
  "transient remote errors and confirmations must be announced politely");

console.log("PASS: remote modal focus, status disclosure, and live announcements");

for (const contract of [
  'role="status"',
  'aria-label={`${count} PIN digits entered`}',
  'window.addEventListener("keydown", onKeyDown)',
  'event.key === "Backspace" || event.key === "Delete"',
  'event.key === "Enter" && canSubmit',
  'className="keypad" aria-disabled={disabled}',
  'disabled={busy || locked > 0}',
]) {
  assert.ok(auth.includes(contract), `PIN screen misses ${contract}`);
}
assert.ok((auth.match(/disabled=\{disabled\}/g) ?? []).length >= 3,
  "lockout/busy state must disable every digit and correction control, not only Confirm");

console.log("PASS: PIN is keyboard-operable and atomically disabled during lockout/request");
