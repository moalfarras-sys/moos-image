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
  constructor(public opts: { output: unknown; error: unknown }) { FakeDecoder.instances.push(this); }
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
