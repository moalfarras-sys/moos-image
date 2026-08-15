import assert from "node:assert/strict";

// ───────────────────────────────────────────────────────────────────────────────
// Mid-stream renegotiation must REOPEN the decoder, not feed it a new stream.
//
// The width ladder rebuilds the encode pipeline at a new resolution; the new SPS
// usually carries the IDENTICAL codec string (same profile, same level), so the
// old path fed the renegotiated stream into the old decoder instance. On phones
// that cannot follow an in-band dimension change the decode error tore the whole
// room down to full-picture JPEG — measured at 79 Mbit/s against H.264's 4.3 —
// and that congestion is what the disconnect loop grew out of. Broken once
// against the pre-fix code: the old decoder swallowed the new stream and no
// second decoder was ever built.
// ───────────────────────────────────────────────────────────────────────────────

class FakeDecoder {
  static instances: FakeDecoder[] = [];
  configured: { codec: string } | null = null;
  decoded: { type: string }[] = [];
  closed = false;
  decodeQueueSize = 0;
  constructor(public opts: { output: (frame: {close: () => void}) => void; error: (error: Error) => void }) { FakeDecoder.instances.push(this); }
  configure(c: { codec: string }) { this.configured = c; }
  decode(chunk: { type: string }) { this.decoded.push(chunk); }
  close() { this.closed = true; }
}
class FakeChunk {
  type: string;
  constructor(init: { type: string }) { this.type = init.type; }
}
Object.defineProperty(globalThis, "VideoDecoder", { configurable: true, value: FakeDecoder });
Object.defineProperty(globalThis, "EncodedVideoChunk", { configurable: true, value: FakeChunk });

const { H264Stream } = await import("../src/lib/decode.ts");

// Annex-B building blocks. The SPS payloads differ only PAST the three bytes the
// codec string is read from — exactly the shape of a resolution-only change.
const sps = (tail: number) => [0, 0, 0, 1, 0x67, 0x64, 0x00, 0x28, tail];
const idr = [0, 0, 0, 1, 0x65, 0x88, 0x84];
const delta = [0, 0, 0, 1, 0x41, 0x9a, 0x22];
const au = (...parts: number[][]) => new Uint8Array(parts.flat()).buffer as ArrayBuffer;

const failures: string[] = [];
const stream = new H264Stream(() => {}, (why: string) => failures.push(why));

stream.push(au(sps(0x11), idr));               // the session starts at width A
stream.push(au(delta));
assert.equal(FakeDecoder.instances.length, 1, "one decoder serves the first stream");
assert.equal(FakeDecoder.instances[0].decoded.length, 2, "keyframe and delta reach decoder #1");

stream.push(au(sps(0x22), idr));               // the ladder renegotiated: same codec string, new SPS
assert.equal(FakeDecoder.instances.length, 2, "a changed SPS must build a fresh decoder");
assert.equal(FakeDecoder.instances[0].closed, true, "the outgrown decoder must be closed");
assert.equal(FakeDecoder.instances[1].decoded.length, 1, "the renegotiation keyframe seeds decoder #2");
assert.equal(FakeDecoder.instances[1].decoded[0].type, "key", "the seed frame must be the keyframe itself");
assert.equal(FakeDecoder.instances[1].configured?.codec, "avc1.640028", "the codec string is read from the new SPS");

stream.push(au(sps(0x22), idr));               // the SAME SPS repeated is a plain GOP boundary
assert.equal(FakeDecoder.instances.length, 2, "an unchanged SPS must not rebuild anything");
assert.deepEqual(failures, [], "a clean renegotiation must never reach the JPEG fallback");

console.log("PASS: a renegotiated stream reopens the decoder instead of failing to JPEG");

// A decoder backlog is state INSIDE VideoDecoder. Asking for an IDR while keeping that decoder
// alive puts the IDR behind the stale pictures and still makes the viewer watch the past catch up.
// Recovery must close it immediately, drop deltas, and seed a fresh generation from one IDR.
FakeDecoder.instances.length = 0;
const recovered: {close: () => void}[] = [];
let keyframeRequests = 0;
const lagging = new H264Stream((frame) => recovered.push(frame as unknown as {close: () => void}),
  (why: string) => failures.push(why), () => keyframeRequests++);

lagging.push(au(sps(0x31), idr));
const stale = FakeDecoder.instances[0];
stale.decodeQueueSize = 9;
lagging.push(au(delta));
assert.equal(stale.closed, true, "a backlogged decoder must be closed, not left to catch up");
assert.equal(keyframeRequests, 1, "dropping a delta backlog must request one recovery IDR");
lagging.push(au(delta));
assert.equal(FakeDecoder.instances.length, 1, "deltas before the IDR must not reopen a decoder");
lagging.push(au(sps(0x31), idr));
assert.equal(FakeDecoder.instances.length, 2, "the recovery IDR must seed a fresh decoder");
assert.deepEqual(FakeDecoder.instances[1].decoded.map((c) => c.type), ["key"],
  "only the recovery IDR may enter the fresh decoder");

// WebCodecs may deliver callbacks already queued by close(). They belong to the retired generation:
// an old error cannot reset decoder #2, and an old output must be closed rather than painted.
let orphanClosed = false;
stale.opts.output({close: () => { orphanClosed = true; }});
stale.opts.error(new Error("late stale decoder error"));
assert.equal(orphanClosed, true, "a frame emitted by a retired decoder must be released");
assert.equal(FakeDecoder.instances[1].closed, false, "a retired decoder error must not close the replacement");

console.log("PASS: decode backlog recovery discards stale generations and restarts on one IDR");
