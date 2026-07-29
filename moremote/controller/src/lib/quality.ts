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

  // 6. Anything else — including a browser that reports nothing at all, which is every desktop
  //    Safari and Firefox — keeps the old behaviour. Balanced is the safe opening move and the
  //    ladder takes it from there.
  return PRESET_BALANCED;
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
