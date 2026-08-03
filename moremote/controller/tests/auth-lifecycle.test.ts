import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {dirname, resolve} from "node:path";
import {fileURLToPath} from "node:url";
import {fetchWithTimeout, getStatus} from "../src/lib/api.ts";

const here = dirname(fileURLToPath(import.meta.url));
const app = readFileSync(resolve(here, "../src/App.tsx"), "utf8");
const auth = readFileSync(resolve(here, "../src/ui/AuthScreens.tsx"), "utf8");

const originalFetch = globalThis.fetch;
try {
  globalThis.fetch = async () => new Response('{"error":"down"}', {
    status: 503,
    headers: {"content-type": "application/json"},
  });
  await assert.rejects(getStatus(), /status failed: 503/,
    "a non-success status response must not be mistaken for a usable ServerStatus");
} finally {
  globalThis.fetch = originalFetch;
}

try {
  globalThis.fetch = async (_input, init) => new Promise<Response>((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => {
      reject(init.signal?.reason ?? new DOMException("aborted", "AbortError"));
    }, {once: true});
  });
  await assert.rejects(fetchWithTimeout("/api/status", {}, 5), /timed out/,
    "a black-holed control request must abort instead of pinning the UI forever");
} finally {
  globalThis.fetch = originalFetch;
}

for (const contract of [
  'tokenStore.set(grant.token);',
  'await validateSession(tok)',
  'await resumeTrustedDevice(remembered.id, remembered.token)',
  'deviceStore.clear();',
  'setView({ name: "loading" });',
  'Access was approved, but the PC connection dropped.',
  'const retry = () => {',
  'void decide();',
  'role="status" aria-live="polite"',
  'role="alert"',
]) {
  assert.ok(app.includes(contract), `app transition misses ${contract}`);
}

assert.equal((auth.match(/finally \{/g) ?? []).length, 2,
  "setup and login must both release busy state through finally");
assert.equal((auth.match(/Connection dropped\. Reconnect to the PC and retry\./g) ?? []).length, 2,
  "setup and login need an explicit recoverable network error");
assert.equal((auth.match(/onDone: \(grant: AuthResult\) => Promise<void>/g) ?? []).length, 2,
  "both auth screens must await the handoff instead of leaking its rejection");
assert.ok((auth.match(/aria-busy=\{busy\}/g) ?? []).length === 2,
  "setup and login must expose their in-flight state to assistive clients");
assert.ok(auth.includes('if (!handedOff) setBusy(false);'),
  "the auth screen must release busy on failure without updating after a successful unmount");
for (const contract of [
  "Trust this device for 30 days",
  "Reconnect after an agent restart without entering the PIN.",
  "trustDevice, defaultDeviceName()",
]) {
  assert.ok(auth.includes(contract), `trusted-device consent misses ${contract}`);
}

console.log("PASS: auth handoff, retry, HTTP status, and busy-state recovery are bounded");

// ───────────────────────────────────────────────────────────────────────────────
// Token EXPIRY is not a sign-out (added 2026-08-03, broken once against the old
// routing). The agent's 60-minute sliding TTL ends mid-session; the old path sent
// that through exitToLogin, whose logout() revokes the trusted-device credential
// too — destroying, on every expiry, the credential that exists to survive expiry,
// and putting the owner back at the PIN pad each hour. Expiry must re-decide
// through the device credential and must never revoke anything.
// ───────────────────────────────────────────────────────────────────────────────
const remote = readFileSync(resolve(here, "../src/ui/RemoteScreen.tsx"), "utf8");
assert.ok(remote.includes("onAuthFail: () => onAuthExpired()"),
  "an unauthorized socket must route through the expiry path");
assert.ok(!remote.includes("onAuthFail: () => onExit()"),
  "an unauthorized socket must not be treated as a deliberate sign-out");
const expiredBody = app.slice(app.indexOf("const authExpired"), app.indexOf("};", app.indexOf("const authExpired")));
assert.ok(expiredBody.includes("tokenStore.clear()") && expiredBody.includes("decide()"),
  "expiry drops the dead access token and re-decides through the device credential");
assert.ok(!expiredBody.includes("logout("),
  "expiry must never revoke the trusted-device credential");
assert.ok(app.includes("onAuthExpired={authExpired}"),
  "the remote screen must be handed the expiry route");

console.log("PASS: token expiry resumes through the trusted device instead of revoking it");
