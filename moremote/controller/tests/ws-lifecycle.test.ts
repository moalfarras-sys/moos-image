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
