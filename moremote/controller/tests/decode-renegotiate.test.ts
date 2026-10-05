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
  static failConfigure = false;
  configured: { codec: string } | null = null;
  decoded: { type: string }[] = [];
  closed = false;
  decodeQueueSize = 0;
  constructor(public opts: { output: (frame: {close: () => void}) => void; error: (error: Error) => void }) { FakeDecoder.instances.push(this); }
  configure(c: { codec: string }) {
    if (FakeDecoder.failConfigure) throw new Error("unsupported codec");
    this.configured = c;
  }
  decode(chunk: { type: string }) { this.decoded.push(chunk); }
  close() { this.closed = true; }
}
class FakeChunk {
  type: string;
  constructor(init: { type: string }) { this.type = init.type; }
}
Object.defineProperty(globalThis, "VideoDecoder", { configurable: true, value: FakeDecoder });
Object.defineProperty(globalThis, "EncodedVideoChunk", { configurable: true, value: FakeChunk });

const { H264Stream, JpegStream } = await import("../src/lib/decode.ts");

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

FakeDecoder.instances.length = 0;
const headers = new H264Stream(() => {}, () => {});
headers.push(au(sps(0x31)));
headers.push(au(sps(0x31), delta));
assert.equal(FakeDecoder.instances.length, 0,
  "SPS metadata without an IDR is not a decodable keyframe");
headers.push(au(sps(0x31), idr));
assert.deepEqual(FakeDecoder.instances[0].decoded.map(chunk => chunk.type), ["key"],
  "an actual IDR must seed the reference history after ignored headers");

FakeDecoder.instances.length = 0;
FakeDecoder.failConfigure = true;
const configureFailures: string[] = [];
const unsupported = new H264Stream(() => {}, why => configureFailures.push(why));
unsupported.push(au(sps(0x31), idr));
assert.equal(FakeDecoder.instances[0].closed, true,
  "a configure failure must release the decoder it allocated");
assert.equal(configureFailures.length, 1, "one unsupported codec reports one failure");
FakeDecoder.instances[0].opts.error(new Error("late configure failure"));
assert.equal(configureFailures.length, 1, "a retired configure callback cannot spend another retry");
FakeDecoder.failConfigure = false;
console.log("PASS: headers cannot masquerade as IDRs and failed configure releases its decoder");

// One decode error is a resync, not a codec change. The first error rebuilds from the next
// keyframe (and asks for it); only a second one inside the window votes the room onto JPEG, which
// costs 12-19x the bytes per frame — on a weak link, the congestion that ended the session.
FakeDecoder.instances.length = 0;
const flaky: string[] = [];
let flakyKeyframes = 0;
const resync = new H264Stream(() => {}, why => flaky.push(why), () => flakyKeyframes++);
resync.push(au(sps(0x41), idr));
FakeDecoder.instances[0].opts.error(new Error("EncodingError: Decoder failure"));
assert.deepEqual(flaky, [], "a first decode error must not leave H.264");
assert.equal(flakyKeyframes, 1, "a first decode error must ask for the keyframe to resync from");
resync.push(au(delta));
assert.equal(FakeDecoder.instances.length, 1, "deltas after the error cannot reopen a decoder");
resync.push(au(sps(0x41), idr));
assert.equal(FakeDecoder.instances.length, 2, "the requested keyframe rebuilds the decoder");
FakeDecoder.instances[1].opts.error(new Error("EncodingError: Decoder failure"));
assert.equal(flaky.length, 1, "a repeat inside the window is a real failure and votes for JPEG");

FakeDecoder.instances.length = 0;
const refused: string[] = [];
const unsupportedLate = new H264Stream(() => {}, why => refused.push(why), () => {});
unsupportedLate.push(au(sps(0x41), idr));
FakeDecoder.instances[0].opts.error({ toString: () => "NotSupportedError: Decoder creation failed" } as Error);
assert.equal(refused.length, 1, "a codec the browser refuses is not retried as a resync");
console.log("PASS: a decode error resyncs on a keyframe first and only a repeat falls back to JPEG");

// Reproduce a decoder that consumes access units without output or an error.
// Pongs and a zero decodeQueueSize both look healthy in this failure mode.
let clock = 10000;
const originalPerformance = globalThis.performance;
Object.defineProperty(globalThis, "performance", {configurable: true, value: {now: () => clock}});
try {
  FakeDecoder.instances.length = 0;
  const failures: string[] = [];
  let requests = 0;
  const silent = new H264Stream(() => {}, why => failures.push(why), () => requests++);
  silent.push(au(sps(0x51), idr));
  const frozen = FakeDecoder.instances[0];
  clock += 2999;
  silent.push(au(delta));
  assert.equal(frozen.closed, false, "a brief decode delay must not restart the stream");
  clock++;
  silent.push(au(delta));
  assert.equal(frozen.closed, true, "silent output starvation must retire even an empty decoder queue");
  assert.equal(requests, 1);
  silent.push(au(delta));
  assert.equal(requests, 1, "recovery must not request an IDR for every arriving delta");
  clock += 1000;
  silent.push(au(delta));
  assert.equal(requests, 2, "a lost recovery IDR must be requested again without a reconnect");
  silent.push(au(sps(0x51), idr));
  const recovered = FakeDecoder.instances[1];
  clock += 2000;
  recovered.opts.output({close: () => {}});
  clock += 2000;
  silent.push(au(delta));
  assert.equal(recovered.closed, false, "actual decoded output refreshes the progress deadline");
  assert.deepEqual(failures, [], "silent recovery must keep the low-bandwidth H.264 codec");
  silent.reset();
} finally {
  Object.defineProperty(globalThis, "performance", {configurable: true, value: originalPerformance});
}
console.log("PASS: silent decoder stalls recover on an IDR with bounded retries and no JPEG vote");

// A slow image decode from before suspension must not paint over the recovered
// picture, or release the replacement generation's in-flight queue.
const jobs: {buf: ArrayBuffer; resolve: (frame: any) => void; reject: () => void}[] = [];
const shown: unknown[] = [];
const jpeg = new JpegStream(frame => shown.push(frame), buf => new Promise((resolve, reject) => {
  jobs.push({buf, resolve, reject: () => reject(new Error("bad image"))});
}));
const first = au([1]), obsolete = au([2]), current = au([3]), latest = au([4]);
jpeg.push(first); jpeg.push(obsolete);
jpeg.reset(); jpeg.push(current); jpeg.push(latest);
let staleClosed = false;
jobs[0].resolve({close: () => { staleClosed = true; }});
await Promise.resolve();
assert.equal(staleClosed, true, "a retired JPEG result must release its image bitmap");
assert.deepEqual(shown, [], "a retired JPEG must never overwrite the replacement picture");
assert.equal(jobs.length, 2, "a retired completion cannot unlock the new decode queue");
const newFrame = {close: () => {}};
jobs[1].resolve(newFrame);
await Promise.resolve();
assert.deepEqual(shown, [newFrame]);
assert.equal(jobs[2].buf, latest, "the replacement generation retains its latest waiting picture");
jpeg.push(obsolete);
jobs[2].reject();
await Promise.resolve();
assert.equal(jobs[3].buf, obsolete, "a rejected image decode cannot leave later frames frozen");
jpeg.reset();
jobs[3].resolve(null);
await Promise.resolve();
console.log("PASS: async JPEG results cannot cross hide/reconnect generations or wedge the frame queue");
