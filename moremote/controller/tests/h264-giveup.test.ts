import assert from "node:assert/strict";

// A tab-scoped sessionStorage double, installed before the module under test is imported.
const store = new Map<string, string>();
(globalThis as any).sessionStorage = {
  getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
  setItem: (k: string, v: string) => void store.set(k, v),
  removeItem: (k: string) => void store.delete(k),
  clear: () => store.clear(),
};

const { h264Failures, noteH264Failure, h264GivenUp, H264_MAX_FAILURES } =
  await import("../src/lib/h264state.ts");

// ── A fresh tab always gets to try ────────────────────────────────────────────────────────
assert.equal(h264Failures(), 0, "a fresh tab has no history");
assert.equal(h264GivenUp(), false, "a fresh tab must be allowed to offer H.264");

// ── Failures accumulate, and the budget is exactly the backoff it gates (15s, 30s, 60s) ──
assert.equal(noteH264Failure(), 1);
assert.equal(h264GivenUp(), false, "one failure is not a verdict");
assert.equal(noteH264Failure(), 2);
assert.equal(h264GivenUp(), false, "two failures is still not a verdict");
assert.equal(noteH264Failure(), 3);
assert.equal(h264GivenUp(), true,
  "after three failures — 15s + 30s + 60s of chances — the tab must stop offering H.264");

// ── THE HOLE THIS EXISTS TO CLOSE ─────────────────────────────────────────────────────────
// The retry path was bounded to three; the CONNECT path was not bounded at all. ws.ts asked
// canDecodeH264(), which only answers "is WebCodecs available in principle" and knows nothing
// about the failures that just happened — so every reconnect handed the room a clean slate.
// Measured on the cloud server, the three-strikes rule working and then being undone by a socket:
//
//     09:00:00 jpeg -> 09:01:00 h264   60s (retry n=2) -> stops, budget spent   <- correct
//     13:39:30 session END
//     13:39:31 session START -> h264 IMMEDIATELY                                <- the hole
//
// Every codec change is a full pipeline rebuild the user sees as the screen cutting out, and
// sessions there reconnect every one to two minutes. So the verdict must survive a reconnect.
assert.equal(h264GivenUp(), true,
  "the verdict must survive a reconnect — it is read from storage, not from component state");

// A verdict must never be silently undone by more failures either.
noteH264Failure();
assert.equal(h264GivenUp(), true, "further failures keep the verdict");
assert.ok(h264Failures() > H264_MAX_FAILURES);

// ── A NEW TAB starts clean, which is why this is sessionStorage and not localStorage ─────
// A browser that fails once must not be condemned for ever.
store.clear();
const fresh = await import("../src/lib/h264state.ts?new-tab");
assert.equal(fresh.h264Failures(), 0, "a new tab starts clean");
assert.equal(fresh.h264GivenUp(), false, "a new tab may try H.264 again");

// ── Storage being unavailable must not break the app (private mode) ──────────────────────
const good = (globalThis as any).sessionStorage;
(globalThis as any).sessionStorage = {
  getItem() { throw new Error("denied"); },
  setItem() { throw new Error("denied"); },
};
assert.equal(fresh.h264Failures(), 0, "a fresh private tab starts with no history");
assert.equal(fresh.h264GivenUp(), false, "a fresh private tab may try H.264");
assert.equal(fresh.noteH264Failure(), 1);
assert.equal(fresh.noteH264Failure(), 2);
assert.equal(fresh.noteH264Failure(), 3);
assert.equal(fresh.h264GivenUp(), true,
  "private-mode reconnects must respect the same three-failure budget");
(globalThis as any).sessionStorage = good;
assert.equal(fresh.h264GivenUp(), true,
  "storage becoming available cannot erase failures already recorded by the tab");

console.log("PASS: the H.264 give-up verdict is one fact, survives reconnects, and resets per tab");
