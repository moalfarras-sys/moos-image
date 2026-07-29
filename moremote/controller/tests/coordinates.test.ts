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

// ---------------------------------------------------------------------------------------------
// The TURNED view: a desktop drawn a quarter turn round so a phone held upright is not 74% black.
//
// Every one of these is a bug that has a symptom rather than a stack trace. A hit-test that is
// transposed does not throw — it clicks somewhere else on the desktop, which reads as "the touch is
// inaccurate". So the properties are asserted directly: the corners land where they should, the
// projection is a true inverse of the normalisation, and a finger delta comes out on the axis the
// user meant.
import {normalizeRotatedPoint as r, projectPoint as p, rotateDelta as d} from "../src/lib/coordinates.ts";

// A 390x694 box at the top-left. Drawn anticlockwise, so the source's +x runs UP the screen and its
// +y runs RIGHT across it — tilt the phone clockwise and the desktop is upright.
const box = {left: 0, top: 0, width: 390, height: 694};
const near = (a: number, b: number, why: string) =>
  assert.ok(Math.abs(a - b) < 1e-9, `${why}: expected ${b}, got ${a}`);

// Centre stays the centre, whichever way round the picture is.
const mid = r(195, 347, box);
near(mid.x, 0.5, "rotated centre x");
near(mid.y, 0.5, "rotated centre y");

// The four corners, spelled out, because "it looked right" is how a transposition survives review.
const tl = r(0, 0, box);           // screen top-left      -> source top-RIGHT
near(tl.x, 1, "screen top-left is source x=1"); near(tl.y, 0, "screen top-left is source y=0");
const br = r(390, 694, box);       // screen bottom-right  -> source bottom-LEFT
near(br.x, 0, "screen bottom-right is source x=0"); near(br.y, 1, "screen bottom-right is source y=1");

// Clamping, not rejection: a tap in the letterbox lands on the nearest edge of the desktop rather
// than missing, exactly as the unrotated path already does.
const out = r(-50, 2000, box);
near(out.x, 0, "off-picture clamps x"); near(out.y, 0, "off-picture clamps y");
assert.throws(() => r(0, 0, {left: 0, top: 0, width: 0, height: 1}), RangeError);

// projectPoint must be the exact inverse in BOTH orientations, or the drawn cursor and the click
// drift apart — the cursor is the only feedback there is, so a mismatch is invisible until it is
// infuriating.
for (const rot of [false, true]) {
  for (const [nx, ny] of [[0, 0], [1, 0], [0, 1], [1, 1], [0.31, 0.77]]) {
    const s = p(nx, ny, box, rot);
    const back = rot ? r(s.x, s.y, box) : n(s.x, s.y, box);
    near(back.x, nx, `round trip x (rot=${rot})`);
    near(back.y, ny, `round trip y (rot=${rot})`);
  }
}

// A swipe toward the top of a turned phone is a swipe toward the RIGHT of the desktop. Get this
// backwards and two-finger scrolling moves the wrong axis, which is the single most confusing thing
// a remote desktop can do.
// Compared numerically, not structurally: negating a zero yields -0, which deepStrictEqual treats
// as a different value and arithmetic does not. The axes are the claim; the sign of nothing is not.
const delta = (dx: number, dy: number, rot: boolean, ex: number, ey: number, why: string) => {
  const got = d(dx, dy, rot);
  near(got.dx, ex, why + " dx"); near(got.dy, ey, why + " dy");
};
delta(3, -7, false, 3, -7, "unrotated deltas pass through untouched");
delta(0, -7, true, 7, 0, "screen-up is desktop-right when turned");
delta(5, 0, true, 0, 5, "screen-right is desktop-down when turned");

// Orientation is the USER'S to control — the owner asked for that twice and reported the picture
// "going landscape on the phone" on its own. Two things enforce that nothing rotates behind the
// user's back:
const remote = readFileSync(join(import.meta.dirname, "..", "src", "ui", "RemoteScreen.tsx"), "utf8");
const remoteCode = remote.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

// 1. Fullscreen must NOT force the phone's physical orientation. The lock("landscape") call — which
//    spun the phone sideways the moment the user tapped Fullscreen — must be gone from the code
//    (the comment explaining its removal may still name it, hence the comment-stripped check).
assert.ok(!/orientation[\s\S]{0,40}\.lock\?\.\("landscape"\)/.test(remoteCode),
  "fullscreen must not screen.orientation.lock('landscape') — the phone must never be force-rotated");

// 2. Auto (the default) must FOLLOW THE PHONE, not auto-rotate the picture: no fill heuristic. The
//    old `turned > upright` rotate-to-fill is what made a portrait phone show a sideways desktop.
assert.ok(!/turned > upright/.test(remoteCode),
  "Auto must not auto-rotate the picture to fill a portrait phone — that is the reported bug; "
  + "rotation is opt-in via the Sideways lock");
assert.match(remote, /🔒 Sideways|↻ Sideways|chooseOrient\("on"\)/,
  "the deliberate quarter-turn must still be available as an explicit user choice");

// ---------------------------------------------------------------------------------------------
// TYPING ON A PHONE. Three behaviours, each of which was a reported fault, and each of which fails
// silently rather than loudly — so each is pinned here rather than left to a visual check.

// 1. The canvas is never shrunk to fit above the keyboard. Squeezing a 16:9 desktop into the band
//    left over collapsed it to a 390x219 stamp, which is the "choked" report. The picture keeps its
//    size and MOVES instead, which is what the extra upward travel in clampPan is for.
// Tested against the CODE, not the prose. This file explains at length what the old line was and
// why it is gone, and quoting it is not the same as doing it — a comment-blind grep would fail on
// the explanation and force the next person to delete the reasoning to make the test pass.
const code = remote.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
assert.ok(!/canvas\.style\.height\s*=/.test(code),
  "the canvas must not be resized to dodge the keyboard — lift the picture instead");
assert.match(remote, /kbInsetRef\.current\s*=/,
  "something has to record how much of the screen the keyboard covers");
assert.match(remote, /Math\.max\(-\(maxY \+ lift\), view\.current\.panY\)/,
  "clampPan must grant exactly that much extra upward travel, or a fitted picture cannot move");

// 2. The rotation is frozen while the keyboard is open. The band above a soft keyboard is often
//    wider than it is tall, which the automatic rule reads as "landscape" — so tapping a text box
//    used to spin the whole desktop a quarter turn.
assert.match(remote, /if \(kbRotLatch\.current !== null\) return kbRotLatch\.current;/,
  "shouldRotate must honour the latch before it measures anything");
assert.match(remote, /kbRotLatch\.current = shouldRotate\(s\.w, s\.h\)/,
  "the latch has to be taken while the viewport still has the shape the user can see");

// 3. Pressing a key in the shortcut row must not close the phone's keyboard. `onMouseDown` cannot
//    prevent this on a touch screen — the compatibility mouse events fire after focus has already
//    moved — so the guard has to be on pointerdown.
assert.match(remote, /const keepFocus = \{ onPointerDown:/,
  "focus must be defended on pointerdown; onMouseDown is too late on touch");
assert.ok(!/onMouseDown=\{\(e\) => e\.preventDefault\(\)\}/.test(remote),
  "the old onMouseDown guards should be gone, not sitting alongside the working one");

// The orientation lock is a promise the user made to themselves, so it is answered before any
// measurement — a lock that is overridden by a heuristic is not a lock.
assert.match(remote, /if \(mode === "off"\) return false;[^\n]*\n\s*if \(mode === "on"\) return true;/,
  "an explicit lock must short-circuit shouldRotate entirely");

// A phone that keeps running yesterday's app after an update is indistinguishable from an update
// that never shipped. Both halves are needed: the worker must not wait, and the page must reload
// when a new one takes over.
const vite = readFileSync(join(import.meta.dirname, "..", "vite.config.ts"), "utf8");
const main = readFileSync(join(import.meta.dirname, "..", "src", "main.tsx"), "utf8");
assert.match(vite, /skipWaiting: true/, "a waiting service worker serves the old app for ever");
assert.match(vite, /clientsClaim: true/);
assert.match(main, /controllerchange/, "the page must reload when a new worker takes over");

console.log("PASS: client letterbox/orientation/turned-view/keyboard/update tests");
