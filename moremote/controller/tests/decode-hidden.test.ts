import assert from "node:assert/strict";

// ──────────────────────────────────────────────────────────────────────────────
// A hidden page decodes nothing, and the phone going into a pocket is not a
// reason to leave H.264.
//
// A phone takes the hardware decoder away from a page it has put in the
// background. Frames keep arriving for a moment — a periodic keyframe among
// them — and the old code reopened a decoder on that keyframe while still
// hidden, collected two errors and voted the room down to JPEG. On the Oracle
// machine 40 of 51 give-ups were followed by the phone's session ending within
// 30 seconds, and three give-ups pin a tab to JPEG for good.
//
// This drives the real H264Stream with a decoder stand-in through: hide, frames
// and an error that arrive while hidden, return, and the error a strict decoder
// raises afterwards — and checks that a give-up reason now says what the page
// was doing, because the agent's log is the only place that evidence survives.
// ──────────────────────────────────────────────────────────────────────────────

class FakeDecoder {
  static instances: FakeDecoder[] = [];
  configured: { codec: string } | null = null;
  decoded: { type: string }[] = [];
  closed = false;
  decodeQueueSize = 0;
  constructor(public opts: { output: (frame: { close: () => void }) => void; error: (error: Error) => void }) {
    FakeDecoder.instances.push(this);
  }
  configure(c: { codec: string }) { this.configured = c; }
  decode(chunk: { type: string }) { this.decoded.push(chunk); }
  close() { this.closed = true; }
  // What the platform does: deliver a frame, or fail.
  emitFrame() { this.opts.output({ close() {} }); }
  fail(message = "EncodingError: Decoder failure") { this.opts.error(new Error(message)); }
}
class FakeChunk {
  type: string;
  constructor(init: { type: string }) { this.type = init.type; }
}
Object.defineProperty(globalThis, "VideoDecoder", { configurable: true, value: FakeDecoder });
Object.defineProperty(globalThis, "EncodedVideoChunk", { configurable: true, value: FakeChunk });
let hidden = false;
Object.defineProperty(globalThis, "document", { configurable: true, value: { get hidden() { return hidden; } } });

const { H264Stream } = await import("../src/lib/decode.ts");

const sps = [0, 0, 0, 1, 0x67, 0x42, 0xc0, 0x20, 0x8c];
const idr = [0, 0, 0, 1, 0x65, 0x88, 0x84];
const delta = [0, 0, 0, 1, 0x41, 0x9a, 0x22];
const au = (...parts: number[][]) => new Uint8Array(parts.flat()).buffer as ArrayBuffer;
const keyframe = () => au(sps, idr);

const failures: string[] = [];
let keyframeRequests = 0;
let frames = 0;
const stream = new H264Stream(() => { frames++; }, (why: string) => failures.push(why), () => keyframeRequests++);

// A healthy stream.
stream.push(keyframe());
stream.push(au(delta));
const first = FakeDecoder.instances[0];
first.emitFrame(); first.emitFrame();
assert.equal(frames, 2);

// The phone puts the page away.
hidden = true;
stream.suspend();
assert.equal(first.closed, true, "a hidden page must give its decoder back at once");

// Frames, including a periodic keyframe, keep arriving until the agent hears nobody is watching.
stream.push(au(delta));
stream.push(keyframe());
stream.push(au(delta));
assert.equal(FakeDecoder.instances.length, 1,
  "a keyframe that arrives while hidden must not open a decoder: the phone would refuse it, and " +
  "that refusal is what voted the room down to JPEG");

// The retired decoder reports the failure the platform gave it, late.
first.fail();
first.fail();
assert.deepEqual(failures, [], "errors from a decoder retired by suspend() are not evidence about the stream");
assert.equal(keyframeRequests, 0, "nor a reason to ask the agent for anything");

// The phone comes back.
hidden = false;
stream.resume();
stream.push(au(delta));
assert.equal(FakeDecoder.instances.length, 1, "a delta cannot start a decoder: it waits for a keyframe");
stream.push(keyframe());
assert.equal(FakeDecoder.instances.length, 2, "the first keyframe after return opens a fresh decoder");
const second = FakeDecoder.instances[1];
assert.equal(second.decoded[0].type, "key");

// A strict decoder may still refuse once right after return: that is absorbed by a resync ...
second.emitFrame();
second.fail();
assert.deepEqual(failures, [], "one error is a resync, not a give-up");
assert.equal(keyframeRequests, 1, "and the resync asks for a keyframe");

// ... and a second one inside the window is a real give-up, which now says what the page was doing.
stream.push(keyframe());
const third = FakeDecoder.instances[2];
third.emitFrame(); third.emitFrame(); third.emitFrame();
third.fail();
assert.equal(failures.length, 1, "a repeat inside the window still falls back to JPEG");
const why = failures[0];
assert.ok(why.startsWith("Error: EncodingError: Decoder failure"), "the browser's own words come first: " + why);
assert.match(why, /\[hidden=0 shown=\d+ms open=\d+ms decoded=3\]$/,
  "the reason carries whether the page was hidden, how long since it was shown, the decoder's age " +
  "and what it produced: " + why);
assert.ok(why.length <= 200, "setH264 truncates at 200: the context must fit behind a typical error");

// A page that starts hidden (a restored tab) is suspended before anything arrives.
FakeDecoder.instances.length = 0;
hidden = true;
const late = new H264Stream(() => {}, (w: string) => failures.push(w));
late.suspend();
late.push(keyframe());
assert.equal(FakeDecoder.instances.length, 0, "a page that was never seen decodes nothing");
hidden = false;
late.resume();
late.push(keyframe());
assert.equal(FakeDecoder.instances.length, 1);

console.log("PASS: a hidden page decodes nothing, a pocket is not a give-up, and a give-up says what the page was doing");
