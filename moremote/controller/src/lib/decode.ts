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

export class H264Stream {
  private dec: VideoDecoder | null = null;
  private codec = "";
  private started = false;

  constructor(
    private readonly onFrame: (f: VideoFrame) => void,
    private readonly onFail: (why: string) => void,
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
  }
}
