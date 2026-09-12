/**
 * Choosing the FIRST picture, from what the device already knows about itself.
 *
 * The stream used to open at Balanced on every device, always. The RTT ladder then corrected
 * it — but a ladder is a correction, not an opening move, and its timings are deliberately
 * slow in the direction of "more": four agreeing samples at 2s each, then a 20s cooldown per
 * step. So a phone on a fast link spent roughly half a minute looking at a picture worse than
 * it could have had from the first frame, and a phone on a metered 3G plan spent the first
 * seconds pushing bytes it could not afford before latency told the ladder to back off.
 *
 * Neither of those needed guessing. The platform hands us the answer: Network Information
 * tells us the class of link and whether the user asked for Data Saver, and deviceMemory /
 * hardwareConcurrency say whether this phone can decode a big picture at all. Reading them is
 * the difference between "it adapts eventually" and "it opens correct".
 *
 * WHAT THIS IS NOT: a bandwidth measurement. `downlink` is the browser's own rough estimate
 * and effectiveType is a bucket, so both are treated as evidence for a STARTING RUNG, never as
 * a licence to skip the ladder. The ladder still owns every step after the first, and it can
 * take the picture straight back down within ~4s if this opening guess was optimistic.
 */

export interface DeviceHints {
  /** navigator.connection.saveData — an explicit user request, not a hint. */
  saveData?: boolean;
  /** navigator.connection.effectiveType — "slow-2g" | "2g" | "3g" | "4g". */
  effectiveType?: string;
  /** navigator.connection.downlink, in Mbit/s (browser estimate, coarse). */
  downlink?: number;
  /** navigator.deviceMemory, in GB (Chrome caps this at 8). */
  deviceMemory?: number;
  /** navigator.hardwareConcurrency — logical cores. */
  hardwareConcurrency?: number;
  /** The widest picture this display can actually show, in physical pixels. */
  displayWidthPx?: number;
}

/** Indices into QUALITY_PRESETS: 0 Data saver, 1 Balanced, 2 Sharp, 3 Ultra. */
export const PRESET_DATA_SAVER = 0;
export const PRESET_BALANCED = 1;
export const PRESET_SHARP = 2;

/**
 * The rung to open on. Never returns Ultra: that is 2560px and ~13 Mbit/s, a decision the user
 * makes by hand (see AUTO_MAX_PRESET). Automatic behaviour tops out at Sharp.
 */
export function pickStartPreset(hints: DeviceHints = {}): number {
  const {
    saveData,
    effectiveType,
    downlink,
    deviceMemory,
    hardwareConcurrency,
    displayWidthPx,
  } = hints;

  // 1. Data Saver is a setting the user turned on, not a signal to weigh against others.
  //    Overriding it to send a sharper picture would be spending their data against their
  //    stated wish, which no amount of available bandwidth justifies.
  if (saveData === true) return PRESET_DATA_SAVER;

  // 2. A link the browser classes below 4g cannot hold Balanced's 1366px without the ladder
  //    immediately pulling it down, and that round trip is visible as a stutter on open.
  if (effectiveType === "slow-2g" || effectiveType === "2g" || effectiveType === "3g") {
    return PRESET_DATA_SAVER;
  }

  // 3. A weak device is a decode problem, not a network one, and no amount of bandwidth fixes
  //    it. Chrome reports deviceMemory in coarse steps and caps it at 8; <= 2GB together with
  //    few cores is the shape of a phone that will drop frames decoding 1080p H.264.
  const weakDevice =
    (typeof deviceMemory === "number" && deviceMemory <= 2) ||
    (typeof hardwareConcurrency === "number" && hardwareConcurrency <= 2);
  if (weakDevice) return PRESET_DATA_SAVER;

  // 4. A display that cannot show the pixels should not be sent them. Sharp is 1920 wide; a
  //    phone with less than ~1400 physical pixels across gains nothing from it but bytes and
  //    a longer decode.
  const narrowDisplay = typeof displayWidthPx === "number" && displayWidthPx > 0 &&
    displayWidthPx < 1400;

  // 5. Everything says fast: a 4g-class link with real headroom, a device that can decode, and
  //    a display wide enough to show it. Open at Sharp instead of climbing to it over ~28s.
  const capableDevice =
    (deviceMemory === undefined || deviceMemory >= 4) &&
    (hardwareConcurrency === undefined || hardwareConcurrency >= 4);
  const fastLink = effectiveType === "4g" && (downlink === undefined || downlink >= 5);
  if (fastLink && capableDevice && !narrowDisplay) return PRESET_SHARP;

  // 6. A browser that reports NO link class at all. Network Information is Chromium-only, so
  //    this is every desktop Firefox and every Safari — and it used to fall straight through to
  //    Balanced. On a phone that is right. On a computer it is a picture that is permanently
  //    soft, for two compounding reasons:
  //
  //      * Balanced is 1366px. The MoOS Cloud desktop being streamed is 1920 wide and the
  //        monitor showing it is usually wider still, so the viewer watches a 1366px source
  //        downscaled from 1920 and then upscaled again to fill the window. Detail is thrown
  //        away before the encoder ever sees it, and no bitrate puts it back.
  //
  //      * It does not correct itself. The ladder climbs only after four agreeing samples
  //        under 90ms at 2s each plus a 20s cooldown — and a Tailscale DERP relay jitters
  //        33..93ms on its own (the ladder's own comment says so). On the exact link this
  //        product is built for, `lat < 90` may never hold four times running, so the session
  //        can sit at 1366 for its whole life.
  //
  //    A wide display on a capable device is not a bandwidth guess: it is the SHAPE of a
  //    desktop or laptop, and those are on wifi or ethernet, not a metered cellular plan. The
  //    asymmetry settles it — being wrong here costs ~4s of a too-sharp picture, because
  //    dropping needs only two agreeing samples and a 6s cooldown; being wrong the old way
  //    cost ~30 seconds, or the entire session.
  //
  //    displayWidthPx is the physical width of the SCREEN (screen.width x devicePixelRatio),
  //    so a phone stays out of this: an iPhone reports ~1179 and lands on Balanced as before.
  const wideDisplay = typeof displayWidthPx === "number" && displayWidthPx >= 1400;
  if (effectiveType === undefined && capableDevice && wideDisplay) return PRESET_SHARP;

  // 7. Anything else keeps the old behaviour. Balanced is the safe opening move and the ladder
  //    takes it from there.
  return PRESET_BALANCED;
}

/**
 * The encode width to ask the helper for, given what we can measure RIGHT NOW.
 *
 * WHY A FAILED MEASUREMENT MUST NOT BECOME A REQUEST
 *
 * `shown` is 0 whenever the picture cannot be measured — no canvas, no layout, a hidden tab, a
 * frame between teardown and rebuild. The old rule was "0 means fall back to the preset ceiling",
 * which sounds harmless and is not: it makes a MEASUREMENT FAILURE indistinguishable from a
 * deliberate request for full size, and every distinct width costs the helper a complete GStreamer
 * teardown and rebuild (~200ms of no picture, then a fresh IDR).
 *
 * Measured on the MoOS Cloud server, one viewer, three minutes, from the agent's own log:
 *
 *     1100 -> 1920 -> 1690 -> 1920 -> 1616 -> 1194 -> 1788 -> 1920 -> 1440 -> 1920
 *     -> 1378 -> 1920 -> 1904 -> 1920 -> 1436 -> 1100 -> 1704 -> 1920 ...
 *
 * Every jump back to exactly 1920 is this branch firing, and every arrow is a rebuild the person
 * watching sees as the screen cutting out. The 12% dead band cannot damp it, because 1440 and 1920
 * are 33% apart — the guard is doing its job on a request that should never have been made.
 *
 * It also explains why the room never held H.264. Each rebuild emits a new SPS, so the client's
 * decoder is torn down and rebuilt on every one; a decode error anywhere in that churn votes the
 * whole room down to JPEG, which is what the log shows on EVERY session: h264 at connect, jpeg
 * 1-23 seconds later, without exception.
 *
 * So: when we cannot measure, do not change the request. Keep the last width we asked for, still
 * clamped to the current ceiling so a deliberate preset DROP is honoured immediately. Only a
 * viewer that has never once measured falls back to the ceiling, which is the original intent —
 * the first seconds must not be a deliberately small picture.
 */
export function encodeWidth(shown: number, ceiling: number, lastPushed: number): number {
  if (shown > 0) return Math.max(720, Math.min(ceiling, shown));
  return lastPushed > 0 ? Math.min(ceiling, lastPushed) : ceiling;
}

/** Read what this browser will tell us. Every field is optional by design. */
export function readDeviceHints(displayWidthPx?: number): DeviceHints {
  const nav = navigator as Navigator & {
    connection?: { saveData?: boolean; effectiveType?: string; downlink?: number };
    deviceMemory?: number;
  };
  const conn = nav.connection;
  return {
    saveData: conn?.saveData,
    effectiveType: conn?.effectiveType,
    downlink: conn?.downlink,
    deviceMemory: nav.deviceMemory,
    hardwareConcurrency: nav.hardwareConcurrency,
    displayWidthPx,
  };
}

/** A short human description of why the opening rung was chosen — shown in Settings ▸ About. */
export function describeHints(h: DeviceHints): string {
  const bits: string[] = [];
  if (h.saveData) bits.push("Data Saver on");
  if (h.effectiveType) bits.push(h.effectiveType);
  if (typeof h.downlink === "number") bits.push(`~${h.downlink} Mbit/s`);
  if (typeof h.deviceMemory === "number") bits.push(`${h.deviceMemory} GB`);
  if (typeof h.hardwareConcurrency === "number") bits.push(`${h.hardwareConcurrency} cores`);
  return bits.length ? bits.join(" · ") : "not reported by this browser";
}

/** What the host said it can encode, as `hello.encode` delivers it. */
export interface HostEncode { maxWidth: number; maxHeight: number; maxFps: number; }

function usable(host: HostEncode | null | undefined): HostEncode | null {
  return host && host.maxWidth > 0 && host.maxFps > 0 ? host : null;
}

/**
 * The highest preset the automatic ladder may climb to, given what the HOST said it can encode.
 *
 * pickStartPreset asks what the phone can decode and what the link can carry. Neither question
 * reaches the other end of the wire, and on a cloud desktop the other end is the constraint: a
 * 2-core Oracle A1 with a virtual display encodes H.264 in software, and MoOS's own probe
 * (`moos-visual-tier` -> `budget.remote_encode`) says so in as many words — "1280x720@30". The
 * stream ran at 1920x1080 anyway, because that value had no reader, and the cost was not
 * abstract: the portal helper sat at ~15% of one core of two, continuously, encoding pixels the
 * machine could not spare while the person was trying to use the desktop those cores belong to.
 *
 * This caps by FRAME RATE only, and the pixels are handled by hostEncodeCeiling below. The two
 * are deliberately separate. A preset is a bundle of {width, fps, JPEG quality}, so demoting a
 * whole rung to fit a width throws away the quality and the frame rate as well: the A1's 1280
 * ceiling would drop Sharp (1920px, q80) all the way to Data saver (1024px, q52) — a picture
 * WORSE than the host's own limit, for no reason. Clamping the requested width instead keeps
 * Sharp's quality at exactly the number of pixels the box said it can make.
 *
 * Frame rate cannot be clamped the same way because it belongs to the rung: Ultra is 60fps, and a
 * host that says 30 cannot serve it at any width.
 */
export function hostMaxPreset(
  presets: readonly { width: number; fps: number }[],
  host: HostEncode | null | undefined,
  fallback: number,
): number {
  const cap = usable(host);
  if (!cap) return fallback;
  let best = -1;
  for (let i = 0; i < presets.length; i++) if (presets[i].fps <= cap.maxFps) best = i;
  if (best < 0) best = 0;   // a ceiling below every preset still gets the smallest real one
  return Math.min(fallback, best);
}

/**
 * The widest picture to ask this host for, in encoder pixels.
 *
 * Applied to the AUTOMATIC choice only. A viewer who picks Sharp or Ultra by hand has made a
 * decision about their own link and their own eyes, and a preset button that silently refused to
 * change anything would be a dead control.
 */
export function hostEncodeCeiling(ceiling: number, host: HostEncode | null | undefined): number {
  const cap = usable(host);
  return cap ? Math.min(ceiling, cap.maxWidth) : ceiling;
}
