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
// Touch slop, asserted as a RANGE rather than pinned to a literal.
//
// This used to read `assert.match(gestures, /MOVE_THRESHOLD = 5/)` with no stated reason, and 5 CSS px
// is not a slop — a thumb travels that far before it has finished landing. Crossing it committed the
// gesture to "scroll", and onUp had no case for "scroll", so no click was sent at all. The test was
// holding the bug in place.
//
// What matters is not the number but that it sits in the band every touch platform converged on for
// the same tap-versus-swipe decision (iOS ~10pt, Android's scaled touch slop ~8dp), and that the
// gesture can still be RESCUED as a tap at the end if it crossed the line but was plainly a tap.
const slop = gestures.match(/MOVE_THRESHOLD = (\d+)/);
assert.ok(slop, "gestures.ts must define a touch slop");
assert.ok(Number(slop[1]) >= 8 && Number(slop[1]) <= 20,
  `touch slop must be a real slop, not a rounding error: got ${slop[1]}px`);
assert.match(gestures, /case "scroll":/,
  "onUp must be able to rescue a short, small gesture as a tap — otherwise a wobbled tap sends nothing");
assert.match(gestures, /TAP_RESCUE_MS/);
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
