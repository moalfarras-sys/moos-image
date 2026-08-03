// Turning what arrives on the wire into something the canvas can draw.
//
// Two codecs, and the difference is not a detail. JPEG is a series of whole pictures: every frame
// stands alone, arrives complete, and decodes with no memory of the last one. H.264 is a stream:
// most frames are a diff against the frame before, so they only mean anything in order, and only
// after a keyframe has established what they are a diff FROM.
//
// Everything below follows from that. Measured on real hardware at 1080p, it buys 79 Mbit/s down
// to 4.3 — the difference between a stream that works on mobile data and one that does not.

// A VideoFrame is drawable by drawImage() exactly like an ImageBitmap, which is why the whole
// render path below is unchanged: only the thing in the box is new.
export type Drawable = ImageBitmap | HTMLImageElement | VideoFrame;

export function drawableSize(d: Drawable): { w: number; h: number } {
  if (d instanceof HTMLImageElement) return { w: d.naturalWidth, h: d.naturalHeight };
  if ("displayWidth" in d) return { w: d.displayWidth, h: d.displayHeight };
  return { w: d.width, h: d.height };
}

export function closeDrawable(d: Drawable | null) {
  if (d && "close" in d) (d as ImageBitmap | VideoFrame).close();
}

/**
 * Can this browser decode the H.264 stream at all?
 *
 * WebCodecs is gated on a secure context — not as a formality, but absolutely: over plain http the
 * API is simply not on `window`. So a phone opening the old LAN address (http://192.168.x.x:8765)
 * answers false here and correctly stays on JPEG, while the same phone on the Tailscale HTTPS name
 * answers true. The address is not a detail of the transport; it decides what the video can be.
 */
export function canDecodeH264(): boolean {
  return typeof window !== "undefined" && "VideoDecoder" in window && window.isSecureContext;
}

// ---------------------------------------------------------------- JPEG

export async function decodeJpeg(buf: ArrayBuffer): Promise<Drawable | null> {
  const blob = new Blob([buf], { type: "image/jpeg" });
  if ("createImageBitmap" in window) {
    try {
      return await createImageBitmap(blob);
    } catch {
      /* fall through */
    }
  }
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(null); };
    img.src = url;
  });
}

// ---------------------------------------------------------------- H.264 (Annex-B)

/** Walk the start codes and hand back each NAL's type and where its payload begins. */
function* nals(b: Uint8Array): Generator<{ type: number; at: number }> {
  for (let i = 0; i + 3 < b.length; i++) {
    if (b[i] !== 0 || b[i + 1] !== 0) continue;
    let at = -1;
    if (b[i + 2] === 1) at = i + 3;
    else if (b[i + 2] === 0 && b[i + 3] === 1) at = i + 4;
    if (at < 0 || at >= b.length) continue;
    yield { type: b[at] & 0x1f, at };
    i = at;
  }
}

/**
 * A decoder holding no reference frame cannot use a P-frame — it is a diff against a picture that
 * does not exist. So the first thing fed in has to be a keyframe, and everything before it is
 * dropped on the floor rather than decoded into garbage. NAL 5 is an IDR slice; NAL 7 is the SPS,
 * which the encoder is told to repeat before every keyframe precisely so a late joiner can start.
 */
function isKeyframe(b: Uint8Array): boolean {
  for (const n of nals(b)) {
    if (n.type === 5 || n.type === 7) return true;
    if (n.type === 1) return false;   // a non-IDR coded slice: this is a delta, stop looking
  }
  return false;
}

/**
 * The codec string, read out of the stream instead of assumed.
 *
 * VideoDecoder.configure() wants "avc1.PPCCLL" — profile, constraint flags, level — and it wants
 * the RIGHT one: hardcoding Baseline and then being handed a High-profile stream is a decode error
 * on a phone, at a distance, with nothing to see. The encoders here disagree about this by design
 * (nvh264enc and x264enc default to High, openh264enc to Constrained Baseline) and the helper
 * picks between them at runtime by what will actually start. So it is read from the SPS, which is
 * in the stream, which is the only thing that cannot be wrong.
 */
function codecFromSps(b: Uint8Array): string | null {
  for (const n of nals(b)) {
    if (n.type !== 7) continue;
    if (n.at + 3 >= b.length) return null;
    const hex = (v: number) => v.toString(16).padStart(2, "0");
    return `avc1.${hex(b[n.at + 1])}${hex(b[n.at + 2])}${hex(b[n.at + 3])}`;
  }
  return null;
}

/**
 * The complete SPS payload, byte for byte — not just the three bytes the codec string uses.
 *
 * The codec string is profile+level and NOTHING else: a pipeline rebuilt at a new width emits an
 * SPS with different picture dimensions but the identical "avc1.PPCCLL", so comparing codec
 * strings says "same stream" about a stream the decoder cannot continue. The full SPS bytes are
 * the encoder's own declaration of everything that matters; if any of it changed, the safe read
 * of the situation is "new stream".
 */
function spsOf(b: Uint8Array): Uint8Array | null {
  let start = -1;
  for (let i = 0; i + 3 < b.length; i++) {
    if (b[i] !== 0 || b[i + 1] !== 0) continue;
    let at = -1;
    if (b[i + 2] === 1) at = i + 3;
    else if (b[i + 2] === 0 && b[i + 3] === 1) at = i + 4;
    if (at < 0 || at >= b.length) continue;
    if (start >= 0) return b.subarray(start, i);   // the SPS ran up to this next start code
    if ((b[at] & 0x1f) === 7) start = at;
    i = at;
  }
  return start >= 0 ? b.subarray(start) : null;
}

function bytesEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

/**
 * How many access units may be in flight inside the decoder before we stop feeding it.
 *
 * WHY A LIMIT EXISTS AT ALL, AND WHAT ITS ABSENCE LOOKED LIKE
 *
 * VideoDecoder.decode() does not block and does not refuse: it queues. So when the phone cannot
 * decode as fast as the server encodes — a cheap device, a hot device that has thermally throttled,
 * a background tab that the browser has deprioritised, or simply 1080p60 on a phone built for 30 —
 * the queue does not overflow and nothing reports an error. It just grows, and every frame in it is
 * a frame the user will see LATE. The picture drifts steadily further behind the input until a click
 * appears to do nothing for two seconds and then everything happens at once.
 *
 * That failure is invisible from the server: its own backlog is empty, it sent everything promptly,
 * every measurement it has says the session is healthy. Only the client can see it, so only the
 * client can fix it.
 *
 * 8 is ~0.27s at 30fps: past any decode hiccup worth riding out, short of what a person reads as lag.
 */
const MAX_DECODE_QUEUE = 8;

export class H264Stream {
  private dec: VideoDecoder | null = null;
  private codec = "";
  private started = false;
  /** True while we are skipping deltas and waiting for an IDR to resynchronise from. */
  private resyncing = false;
  /** The SPS this decoder was built for. A keyframe carrying a DIFFERENT one is a renegotiated
   *  stream (the width ladder rebuilt the pipeline), not a decodable continuation. */
  private lastSps: Uint8Array | null = null;

  constructor(
    private readonly onFrame: (f: VideoFrame) => void,
    private readonly onFail: (why: string) => void,
    /** Ask the server for an IDR now. Rate-limited by the caller AND by the agent. */
    private readonly onNeedKeyframe: () => void = () => {},
  ) {}

  push(buf: ArrayBuffer) {
    const b = new Uint8Array(buf);
    const key = isKeyframe(b);

    if (!this.started) {
      if (!key) return;                       // still waiting for something to start FROM
      const codec = codecFromSps(b);
      if (!codec) return;                     // a keyframe with no SPS is not a place to start
      if (!this.open(codec)) return;
      this.started = true;
      this.lastSps = spsOf(b);
    } else if (key) {
      // A mid-session keyframe whose SPS changed is the encoder renegotiating — the width
      // ladder rebuilt the pipeline at a new resolution. The codec STRING usually survives
      // that (same profile, same level), so the old path fed the new stream to the old
      // decoder, and on phones that cannot follow an in-band dimension change the decode
      // error tore the whole room down to JPEG. Every renegotiation starts with exactly the
      // keyframe a fresh decoder needs, so reopen on it: a clean handover, zero frames lost,
      // no fallback.
      const sps = spsOf(b);
      if (sps && this.lastSps && !bytesEqual(sps, this.lastSps)) {
        const codec = codecFromSps(b);
        if (!codec) return;
        this.reset();
        if (!this.open(codec)) return;
        this.started = true;
      }
      if (sps) this.lastSps = sps;
    }

    // Falling behind: throw away the past rather than display it late.
    //
    // Dropping a P-frame corrupts every frame after it until the next IDR, so this cannot simply
    // skip one and carry on. It drops EVERYTHING until a keyframe arrives — a clean restart of the
    // stream rather than a hole in the middle of it — and asks for that keyframe rather than waiting
    // up to a full GOP for the scheduled one. Exactly the same trade the agent makes when ITS queue
    // overruns (see StreamSession's backlog drop); this is the client-side half of it.
    if (!this.resyncing && (this.dec?.decodeQueueSize ?? 0) > MAX_DECODE_QUEUE) {
      this.resyncing = true;
      this.onNeedKeyframe();
    }
    if (this.resyncing) {
      if (!key) return;                       // still catching up; this frame is already history
      this.resyncing = false;
    }

    try {
      this.dec!.decode(new EncodedVideoChunk({
        type: key ? "key" : "delta",
        // Monotonic and in microseconds. The decoder only needs the ORDER — there are no B-frames
        // in this stream (bframes=0 / zerolatency), so presentation order is coding order.
        timestamp: Math.round(performance.now() * 1000),
        data: b,
      }));
    } catch (e) {
      this.reset();
      this.onFail(String(e));
    }
  }

  private open(codec: string): boolean {
    if (this.dec && this.codec === codec) return true;
    this.reset();
    try {
      const dec = new VideoDecoder({
        output: (f) => this.onFrame(f),
        // A decoder that errors is not a decoder that recovers: it is closed, and the next
        // keyframe has to build a new one. Telling the caller lets it fall back to JPEG rather
        // than sit in front of a frozen picture wondering.
        error: (e) => { this.reset(); this.onFail(String(e)); },
      });
      dec.configure({ codec, optimizeForLatency: true });
      this.dec = dec;
      this.codec = codec;
      return true;
    } catch (e) {
      this.onFail(String(e));
      return false;
    }
  }

  /** Forget everything and wait for the next keyframe. */
  reset() {
    try { this.dec?.close(); } catch { /* already closed */ }
    this.dec = null;
    this.codec = "";
    this.started = false;
    this.resyncing = false;
    this.lastSps = null;
  }
}
