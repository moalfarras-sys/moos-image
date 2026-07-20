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
// Text coalescing is adaptive: keysym-typable text flushes within one 60 Hz frame, while text the
// agent must type by borrowing the clipboard batches into words (one borrow per letter is both
// slower and clobbers the clipboard repeatedly).
const fastMs = ws.match(/FAST_FLUSH_MS = (\d+)/);
const clipMs = ws.match(/CLIPBOARD_FLUSH_MS = (\d+)/);
assert.ok(fastMs && clipMs, "ws.ts must define both coalescing windows");
assert.ok(Number(fastMs[1]) <= 16, `keysym flush must stay within one 60Hz frame, got ${fastMs[1]}ms`);
assert.ok(Number(clipMs[1]) > Number(fastMs[1]) && Number(clipMs[1]) <= 80,
  `clipboard flush should batch but stay imperceptible, got ${clipMs[1]}ms`);
// The client's fast-path test must match the agent's, or text routes down the wrong path.
assert.match(ws, /FAST_TEXT = \/\^\[a-zA-Z0-9 \]\*\$\//);
console.log("PASS: client letterbox/orientation/invalid-coordinate tests");
