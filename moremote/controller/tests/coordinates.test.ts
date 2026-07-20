import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {join} from "node:path";
import {normalizeContentPoint as n} from "../src/lib/coordinates.ts";
assert.deepEqual(n(200,400,{left:0,top:300,width:400,height:200}),{x:.5,y:.5}); // portrait letterbox
assert.deepEqual(n(400,200,{left:100,top:0,width:600,height:400}),{x:.5,y:.5}); // landscape
assert.deepEqual(n(-2,900,{left:10,top:10,width:100,height:100}),{x:0,y:1});
assert.throws(()=>n(NaN,0,{left:0,top:0,width:1,height:1}),RangeError);
assert.throws(()=>n(0,0,{left:0,top:0,width:0,height:1}),RangeError);
const lib = join(import.meta.dirname, "..", "src", "lib");
const gestures = readFileSync(join(lib, "gestures.ts"), "utf8");
const ws = readFileSync(join(lib, "ws.ts"), "utf8");
assert.match(gestures, /MOVE_THRESHOLD = 5/);
assert.match(gestures, /Continue below and deliver this first meaningful delta/);
// Text is coalesced before it is sent. The window has to be big enough that Arabic — which the
// agent types by borrowing the clipboard, one round trip per flush — batches into words rather
// than letters, and small enough to stay under the ~100ms where typing feels detached.
const coalesce = ws.match(/setTimeout\(\(\)=>this\.flushText\(\),(\d+)\)/);
assert.ok(coalesce, "ws.ts must coalesce text before sending");
assert.ok(Number(coalesce[1]) >= 30 && Number(coalesce[1]) <= 80,
  `text coalescing window should be 30-80ms, got ${coalesce[1]}ms`);
console.log("PASS: client letterbox/orientation/invalid-coordinate tests");
