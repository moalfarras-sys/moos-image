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

// Real deadlines and sockets whose close handshake never completes (a phone changing networks).
let clock = 10_000;
const deadlines = new Map<number, {at: number; callback: () => void}>();
const realDateNow = Date.now;
Date.now = () => clock;
Object.defineProperty(globalThis, "performance", {configurable: true, value: {now: () => clock}});
window.setTimeout = ((callback: () => void, delay: number) => {
  const id = nextTimer++;
  deadlines.set(id, {at: clock + delay, callback});
  return id;
}) as typeof window.setTimeout;
window.clearTimeout = (id: number) => { deadlines.delete(id); };
const advance = (ms: number) => {
  clock += ms;
  for (const [id, task] of [...deadlines]) {
    if (task.at <= clock) { deadlines.delete(id); task.callback(); }
  }
};
const open = (conn: RemoteConnection) => {
  conn.connect();
  const socket = latest;
  socket.readyState = TestSocket.OPEN;
  socket.onopen?.();
  socket.onmessage?.({data: JSON.stringify({type: "hello", screen: {w: 1920, h: 1080}})});
  return socket;
};

{
  const conn = new RemoteConnection("token", {});
  const socket = open(conn);
  const sent: any[] = [];
  socket.send = data => sent.push(JSON.parse(data));
  conn.text("س");
  advance(200);
  conn.text("ل");
  advance(50);
  assert.deepEqual(sent.filter(m => m.type === "text").map(m => m.value), ["سل"],
    "continuous Arabic input must flush at the actual 250 ms deadline");
  conn.disconnect();
  deadlines.clear();
}

{
  let opens = 0;
  let authFailures = 0;
  let frames = 0;
  const conn = new RemoteConnection("token", {
    onOpen: () => opens++, onAuthFail: () => authFailures++, onFrame: () => frames++,
  });
  const old = open(conn);
  open(conn);
  old.onopen?.();
  old.onmessage?.({data: JSON.stringify({type: "error", error: "unauthorized"})});
  old.onmessage?.({data: new ArrayBuffer(4)});
  assert.equal(opens, 2, "retired sockets cannot announce another successful open");
  assert.equal(authFailures, 0, "retired sockets cannot sign out the replacement session");
  assert.equal(frames, 0, "retired sockets cannot feed stale frames into the new decoder");
  conn.disconnect();
  deadlines.clear();
}

{
  const notices: boolean[] = [];
  const conn = new RemoteConnection("token", {onClose: reconnect => notices.push(reconnect)});
  const zombie = open(conn);
  zombie.close = () => { zombie.readyState = 2; }; // browser is stuck waiting for the dead peer
  advance(1);
  conn.probe();
  advance(2000);
  advance(500);
  assert.notEqual(latest, zombie, "resume recovery cannot depend on a dead peer completing close");
  assert.deepEqual(notices, [true], "a watchdog recovery reports the outage exactly once");
  zombie.onclose?.();
  assert.deepEqual(notices, [true], "a late zombie close cannot affect the new connection");
  conn.disconnect();
  deadlines.clear();
}

{
  const conn = new RemoteConnection("token", {});
  open(conn);
  conn.disconnect();
  conn.text("stale text");
  const socket = open(conn);
  const sent: any[] = [];
  socket.send = data => sent.push(JSON.parse(data));
  advance(300);
  assert.equal(sent.filter(m => m.type === "text").length, 0,
    "intentional disconnect must not preserve text for a later unrelated session");
  conn.disconnect();
  deadlines.clear();
}

{
  const conn = new RemoteConnection("token", {});
  conn.setWatching(false);
  conn.connect();
  const socket = latest;
  const sent: any[] = [];
  socket.send = data => sent.push(JSON.parse(data));
  socket.readyState = TestSocket.OPEN;
  socket.onopen?.();
  assert.equal(sent.find(m => m.type === "video")?.watching, false,
    "a hidden tab must preserve its visibility vote across reconnects");
  conn.text("سلام");
  advance(250);
  assert.equal(sent.filter(m => m.type === "text").length, 0,
    "queued text must wait for authentication and the current monitor geometry");
  socket.onmessage?.({data: JSON.stringify({type: "hello", monitor: 2, screen: {w: 800, h: 600}})});
  advance(80);
  assert.equal(sent.find(m => m.type === "text")?.display, 2,
    "reconnected text must use the authenticated session's display");
  conn.disconnect();
  deadlines.clear();
}

{
  const conn = new RemoteConnection("token", {});
  conn.connect();
  const stuck = latest;
  stuck.close = () => { stuck.readyState = 2; };
  advance(10000);
  advance(500);
  assert.notEqual(latest, stuck, "a CONNECTING socket without a handshake must have a deadline");
  conn.disconnect();
  deadlines.clear();
}

Date.now = realDateNow;
console.log("PASS: bounded typing latency, retired socket isolation and stalled-close recovery");
