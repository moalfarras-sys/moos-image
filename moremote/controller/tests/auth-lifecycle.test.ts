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
  'tokenStore.set(token);',
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
assert.equal((auth.match(/onDone: \(token: string\) => Promise<void>/g) ?? []).length, 2,
  "both auth screens must await the handoff instead of leaking its rejection");
assert.ok((auth.match(/aria-busy=\{busy\}/g) ?? []).length === 2,
  "setup and login must expose their in-flight state to assistive clients");
assert.ok(auth.includes('if (!handedOff) setBusy(false);'),
  "the auth screen must release busy on failure without updating after a successful unmount");

console.log("PASS: auth handoff, retry, HTTP status, and busy-state recovery are bounded");
