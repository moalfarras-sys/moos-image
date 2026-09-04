import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {dirname, resolve} from "node:path";
import {fileURLToPath} from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(here, "../src/ui/RemoteScreen.tsx"), "utf8");
const auth = readFileSync(resolve(here, "../src/ui/AuthScreens.tsx"), "utf8");
const styles = readFileSync(resolve(here, "../src/styles.css"), "utf8");

// Bottom sheets are true modal dialogs: focus enters them, Tab cannot escape,
// Escape closes, and the invoking toolbar control receives focus again.
for (const contract of [
  'role = "dialog"',
  'role={role}',
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

assert.match(
  styles,
  /@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{\s*\*,\s*\*::before,\s*\*::after\s*\{[\s\S]*?animation:\s*none\s*!important;[\s\S]*?transition:\s*none\s*!important;/,
  "Reduced Motion must stop every PWA animation and transition, including pseudo-elements",
);
assert.ok(!/animation-duration:\s*0?\.0*1m?s/i.test(styles),
  "Reduced Motion must be truly static, not a near-zero animation workaround");

console.log("PASS: Reduced Motion is a true static state across the complete PWA");

// The controller chrome owns a separate grid track. This is stronger than choosing a clever
// overlay position: the streamed stage and every toolbar hit target are disjoint by construction.
for (const contract of [
  'className="remote-stage"',
  'className="toolbar-primary" role="toolbar" aria-label="Remote controls"',
  'aria-label="Show remote controls"',
  // The label text is now i18n-resolved at runtime: assert the binding exists
  '>{tr("controls")}</span>',
  'role="status" aria-live="polite"',
]) assert.ok(source.includes(contract), `responsive remote chrome misses ${contract}`);
assert.match(styles, /\.remote\s*\{[\s\S]*?display:\s*grid;[\s\S]*?grid-template-areas:\s*"stage"\s*"controls";/,
  "phone layout must reserve separate stage and controls tracks");
assert.match(styles, /\.remote-stage\s*\{[\s\S]*?grid-area:\s*stage;/,
  "the streamed desktop must occupy only the protected stage");
assert.match(styles, /\.toolbar\s*\{[\s\S]*?grid-area:\s*controls;[\s\S]*?position:\s*relative;/,
  "toolbar must live in reserved chrome, never as a fixed/absolute picture overlay");
assert.match(styles, /height:\s*100dvh;/, "remote shell must follow Safari's dynamic viewport");
assert.match(styles, /\.topbar\s*\{[\s\S]*?min-width:\s*44px;[\s\S]*?min-height:\s*44px;/,
  "the compact connection disclosure must remain a safe touch target");

console.log("PASS: responsive chrome reserves the Horizon-safe stage and keeps 44px targets");

// Ctrl/Cmd+V on a computer transfers either text or image before asking the remote to paste.
// The phone sheet distinguishes clipboard-only from the consequential Send & Paste action.
for (const contract of [
  'item.type.startsWith("image/")',
  'await setClipboardImage(token, image)',
  'await setClipboard(token, text)',
  '<IconSend /> Send &amp; Paste',
  '<IconClipboard /> Set only',
  'role="status" aria-live="polite"><i />{clipboardBusy}',
  'nothing pasted',
]) assert.ok(source.includes(contract), `clipboard UX misses ${contract}`);
const desktopPaste = source.slice(source.indexOf('const onPaste = async (e: ClipboardEvent)'),
  source.indexOf('window.addEventListener("paste", onPaste)'));
assert.ok(desktopPaste.indexOf("await setClipboardImage") < desktopPaste.indexOf('combo(["Control", "V"])'),
  "desktop image paste must await the upload before sending the remote chord");

console.log("PASS: desktop image clipboard and phone Send & Paste are ordered and explicit");

assert.ok(!source.includes("window.confirm("),
  "sensitive power actions must not fall back to an unthemed browser confirm");
for (const contract of [
  'role="alertdialog"',
  'descriptionId="power-confirm-description"',
  'initialFocusSelector="#power-confirm-cancel"',
  'id="power-confirm-cancel"',
  'Unsaved work may be lost.',
  'onClick={() => void runPower(powerConfirm)}',
  'if (powerInFlightRef.current) return;',
  'powerInFlightRef.current = true;',
  'dismissible={!powerBusy}',
  'disabled={powerBusy}',
  '{powerBusy ? "Working…" : powerConfirm.label}',
]) {
  assert.ok(source.includes(contract), `power confirmation misses ${contract}`);
}
assert.match(source, /if \(needConfirm\) \{[\s\S]*?setPowerConfirm\(pending\);[\s\S]*?return;/,
  "a sensitive power action must stop at the confirmation state before reaching the API");

console.log("PASS: sensitive power actions use one themed, focus-safe confirmation path");
