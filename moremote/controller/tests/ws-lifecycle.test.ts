import assert from "node:assert/strict";
import {RemoteConnection} from "../src/lib/ws.ts";

let latest: TestSocket;
let nextTimer = 1;

class TestSocket {
  static readonly OPEN = 1;
  binaryType = "";
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((event: {data: string | ArrayBuffer}) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(_url: string) { latest = this; }
  send(_data: string) {}
  close() { this.readyState = 3; this.onclose?.(); }
}

Object.defineProperty(globalThis, "location", {
  configurable: true,
  value: {protocol: "https:", host: "remote.example"},
});
Object.defineProperty(globalThis, "window", {
  configurable: true,
  value: {
    setTimeout: (_callback: () => void, _delay: number) => nextTimer++,
    clearTimeout: (_id: number) => {},
    setInterval: (_callback: () => void, _delay: number) => nextTimer++,
    clearInterval: (_id: number) => {},
  },
});
Object.defineProperty(globalThis, "WebSocket", {configurable: true, value: TestSocket});

const closes: boolean[] = [];
const connection = new RemoteConnection("token", {onClose: recoverable => closes.push(recoverable)});

connection.connect();
latest.close();
assert.deepEqual(closes, [true], "an unexpected transport close must enter recovery");

connection.connect();
latest.onmessage?.({data: JSON.stringify({type: "stopped"})});
latest.close();
assert.deepEqual(closes, [true, false], "a server-requested stop must never masquerade as an outage");

connection.connect();
latest.onmessage?.({data: JSON.stringify({type: "idle"})});
latest.close();
assert.deepEqual(closes, [true, false, false], "an idle teardown must remain intentional");

console.log("PASS: socket closes distinguish recoverable outages from intentional teardown");

// ───────────────────────────────────────────────────────────────────────────────
// Contracts added 2026-08-03, each broken once against the pre-fix code:
//   1. A word typed across an outage survives the reconnect and delivers ONCE.
//   2. A zombie socket (iOS resume) is closed by probe() at machine speed.
//   3. A socket delivering FRAMES is alive even when its pongs are delayed —
//      the watchdog/probe must accept any inbound message as proof of life.
// ───────────────────────────────────────────────────────────────────────────────

const timers = new Map<number, () => void>();
Object.defineProperty(globalThis, "window", {
  configurable: true,
  value: {
    setTimeout: (callback: () => void, _delay: number) => { const id = nextTimer++; timers.set(id, callback); return id; },
    clearTimeout: (id: number) => { timers.delete(id); },
    setInterval: (_callback: () => void, _delay: number) => nextTimer++,
    clearInterval: (_id: number) => {},
    innerWidth: 390,
    innerHeight: 844,
    devicePixelRatio: 3,
    visualViewport: undefined,
  },
});
Object.defineProperty(globalThis, "screen", { configurable: true, value: { orientation: { type: "portrait-primary" } } });
const fireTimers = () => { const cbs = [...timers.values()]; timers.clear(); for (const cb of cbs) cb(); };

{ // 1 — the word survives the reconnect window
  const conn = new RemoteConnection("token", {});
  conn.connect();
  const s1 = latest;
  s1.readyState = TestSocket.OPEN;
  s1.onopen?.();
  conn.text("سلام");            // gathering for a flush that will find the socket dead
  s1.close();                    // the outage
  conn.keyTap("Enter");          // keys flush the buffer — into a dead socket
  timers.clear();                // drop the armed reconnect; this test reconnects by hand
  conn.connect();
  const s2 = latest;
  s2.readyState = TestSocket.OPEN;
  const delivered: string[] = [];
  s2.send = (d: string) => delivered.push(d);
  s2.onopen?.();
  s2.onmessage?.({data: JSON.stringify({type: "hello"})});
  fireTimers();                  // the hello-armed flush delivers the queued word
  const texts = delivered.map(x => JSON.parse(x)).filter(m => m.type === "text");
  assert.equal(texts.length, 1, "the word typed across the outage must deliver exactly once");
  assert.equal(texts[0].value, "سلام", "the queued word must arrive intact after hello");
  conn.disconnect();
  timers.clear();
}

{ // 2 — probe closes a silent zombie so onclose can reconnect NOW
  const conn = new RemoteConnection("token", {});
  conn.connect();
  const s = latest;
  s.readyState = TestSocket.OPEN;
  s.onopen?.();
  timers.clear();
  let closed = false;
  s.close = () => { closed = true; s.readyState = 3; s.onclose?.(); };
  conn.probe();
  fireTimers();                  // the probe deadline passes with total silence
  assert.equal(closed, true, "a silent socket after resume must be closed so reconnect can run");
  timers.clear();
}

{ // 3 — frames are proof of life; a probe must NOT kill a session that is streaming
  const conn = new RemoteConnection("token", {onFrame: () => {}});
  conn.connect();
  const s = latest;
  s.readyState = TestSocket.OPEN;
  s.onopen?.();
  timers.clear();
  let closed = false;
  s.close = () => { closed = true; s.readyState = 3; s.onclose?.(); };
  conn.probe();
  s.onmessage?.({data: new ArrayBuffer(4)});   // a frame arrives; no pong does
  fireTimers();
  assert.equal(closed, false, "a socket delivering frames must count as alive without a pong");
  conn.disconnect();
  timers.clear();
}

console.log("PASS: reconnect text survival, resume probe, and frame-liveness contracts hold");
