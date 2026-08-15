import assert from "node:assert/strict";
import {
  pickStartPreset, describeHints, encodeWidth,
  PRESET_DATA_SAVER, PRESET_BALANCED, PRESET_SHARP,
} from "../src/lib/quality.ts";

// ── A failed measurement must not become a request for full size ─────────────────────────
// Every distinct encode width costs the helper a full GStreamer teardown and rebuild, which the
// viewer sees as the screen cutting out. `shown === 0` means "cannot measure right now", and
// answering it with the ceiling made the request ping-pong. Measured on the live cloud server,
// one viewer, three minutes, from the agent's own log:
//
//   1100 -> 1920 -> 1690 -> 1920 -> 1616 -> 1194 -> 1788 -> 1920 -> 1440 -> 1920 -> 1378 -> 1920
//
// Every 1920 in that sequence is the unmeasurable branch, and the 12% dead band could not damp it
// because 1440 and 1920 are 33% apart.
assert.equal(encodeWidth(1440, 1920, 1440), 1440, "a good measurement is used as-is");
assert.equal(encodeWidth(0, 1920, 1440), 1440,
  "an unmeasurable moment must HOLD the last width, not jump to the ceiling");
assert.equal(encodeWidth(0, 1920, 0), 1920,
  "a viewer that has never measured still opens at the ceiling, not at a floor");

// A deliberate preset DROP must still take effect immediately, even while unmeasurable —
// otherwise a struggling link could not be relieved until the next successful layout.
assert.equal(encodeWidth(0, 1024, 1920), 1024,
  "the held width is still clamped to the current ceiling");

// The 720 floor survives: below it, text on a 1080p desktop is unreadable on any phone.
assert.equal(encodeWidth(320, 1920, 1440), 720, "the 720 floor still applies to a real measurement");
// ...but the floor is a floor, not a target: it must never raise a held width.
assert.equal(encodeWidth(2400, 1920, 1920), 1920, "a measurement above the ceiling is clamped");

// The opening rung, which the RTT ladder cannot supply because a ladder is a correction and
// not an opening move. Every case here is a real device shape, not an abstract branch.

// ── Data Saver is a decision, not a hint ──────────────────────────────────────────────────
// The user turned it on. Sending a sharper picture because bandwidth happens to be available
// spends their data against their stated wish, so it outranks every other signal.
assert.equal(
  pickStartPreset({ saveData: true, effectiveType: "4g", downlink: 50, deviceMemory: 8,
                    hardwareConcurrency: 8, displayWidthPx: 3000 }),
  PRESET_DATA_SAVER,
  "Data Saver must win over every fast-link signal");

// ── A slow link opens light, so the ladder is not immediately dragging it back down ───────
for (const effectiveType of ["slow-2g", "2g", "3g"]) {
  assert.equal(
    pickStartPreset({ effectiveType, deviceMemory: 8, hardwareConcurrency: 8, displayWidthPx: 3000 }),
    PRESET_DATA_SAVER,
    `${effectiveType} must open at Data saver`);
}

// ── A weak device is a DECODE problem; bandwidth does not fix it ──────────────────────────
assert.equal(
  pickStartPreset({ effectiveType: "4g", downlink: 50, deviceMemory: 2, hardwareConcurrency: 8,
                    displayWidthPx: 3000 }),
  PRESET_DATA_SAVER,
  "2GB of RAM must open light however fast the link is");
assert.equal(
  pickStartPreset({ effectiveType: "4g", downlink: 50, deviceMemory: 8, hardwareConcurrency: 2,
                    displayWidthPx: 3000 }),
  PRESET_DATA_SAVER,
  "a two-core phone must open light however fast the link is");

// ── The fast case, which is the whole point: correct on the first frame ───────────────────
// Without this the same phone spends ~28s climbing (4 agreeing samples at 2s, then a 20s
// cooldown) while looking at a picture worse than it could have had immediately.
assert.equal(
  pickStartPreset({ effectiveType: "4g", downlink: 20, deviceMemory: 8, hardwareConcurrency: 8,
                    displayWidthPx: 2400 }),
  PRESET_SHARP,
  "a capable device on a fast link must OPEN at Sharp, not climb to it");

// ── A narrow display gains nothing from Sharp's 1920 but bytes and decode time ────────────
assert.equal(
  pickStartPreset({ effectiveType: "4g", downlink: 50, deviceMemory: 8, hardwareConcurrency: 8,
                    displayWidthPx: 1170 }),
  PRESET_BALANCED,
  "a phone that cannot show 1920 physical pixels must not be sent them");

// ── 4g with a weak estimate is not evidence of headroom ──────────────────────────────────
assert.equal(
  pickStartPreset({ effectiveType: "4g", downlink: 2, deviceMemory: 8, hardwareConcurrency: 8,
                    displayWidthPx: 3000 }),
  PRESET_BALANCED,
  "4g at 2 Mbit/s must not open at Sharp — effectiveType is a bucket, not a measurement");

// ── A browser that reports NOTHING AT ALL keeps the old, safe behaviour ──────────────────
// Silence with no display measurement either must not be read as fast or slow. This is the
// floor case, and it stays exactly as it was.
assert.equal(pickStartPreset({}), PRESET_BALANCED,
  "no signals at all must fall back to Balanced, exactly as before this existed");
assert.equal(pickStartPreset(), PRESET_BALANCED, "no argument at all must be safe too");

// ── A COMPUTER whose browser hides the link must still open sharp ────────────────────────
// Network Information is Chromium-only, so desktop Firefox and every Safari report no
// effectiveType. They used to fall through to Balanced — 1366px of a 1920px cloud desktop,
// upscaled again to fill a big monitor — and the RTT ladder could not reliably rescue them:
// it climbs only on four consecutive samples under 90ms, and a Tailscale DERP relay jitters
// 33..93ms by itself. That is the "الصورة مو واضحة" case, and it could last the whole session.
//
// The screen width is the evidence. A 1400px+ physical display on a 4-core machine is a
// desktop or a laptop, which is on wifi or ethernet.
assert.equal(
  pickStartPreset({ hardwareConcurrency: 8, displayWidthPx: 2560 }),
  PRESET_SHARP,
  "desktop Firefox on a 1440p monitor must open at Sharp, not climb for 30s or never");
assert.equal(
  pickStartPreset({ hardwareConcurrency: 10, displayWidthPx: 3840 }),
  PRESET_SHARP,
  "desktop Safari on a 4K monitor must open at Sharp");

// ...but the same silence on a PHONE-shaped device must not. iOS Safari reports no
// effectiveType either, and an iPhone 15 Pro is 393 CSS px x 3 = 1179 physical.
assert.equal(
  pickStartPreset({ hardwareConcurrency: 6, displayWidthPx: 1179 }),
  PRESET_BALANCED,
  "a phone whose browser hides the link must NOT be promoted on screen width alone");

// A weak machine stays out of it whatever its monitor says: this is a decode limit.
assert.equal(
  pickStartPreset({ hardwareConcurrency: 2, displayWidthPx: 2560 }),
  PRESET_DATA_SAVER,
  "a two-core machine on a big monitor is still a decode problem");

// Data Saver still outranks the new branch, exactly as it outranks the fast-link one.
assert.equal(
  pickStartPreset({ saveData: true, hardwareConcurrency: 8, displayWidthPx: 2560 }),
  PRESET_DATA_SAVER,
  "Data Saver must win over the wide-display promotion too");

// A 4g device that reports no downlink and no memory is still allowed to open Sharp: absent
// fields are unknown, not bad, and effectiveType 4g is the browser's own verdict on the link.
assert.equal(
  pickStartPreset({ effectiveType: "4g", displayWidthPx: 2400 }), PRESET_SHARP,
  "4g with unknown-but-not-bad device fields may open at Sharp");

// ── Never Ultra automatically ─────────────────────────────────────────────────────────────
// Ultra is 2560px and roughly 13 Mbit/s. AUTO_MAX_PRESET exists because RTT is not bandwidth;
// this function must respect the same rule, so no input may produce it.
for (const hints of [
  { effectiveType: "4g", downlink: 1000, deviceMemory: 8, hardwareConcurrency: 16, displayWidthPx: 5120 },
  { effectiveType: "4g", downlink: 100, deviceMemory: 8, hardwareConcurrency: 8, displayWidthPx: 3840 },
]) {
  assert.ok(pickStartPreset(hints) <= PRESET_SHARP,
    "nothing may open at Ultra automatically — that rung is a deliberate user choice");
}

// ── The About line must say something in every case, including total silence ──────────────
assert.match(describeHints({}), /not reported/,
  "a browser that reports nothing must still produce a readable line, not an empty one");
assert.match(describeHints({ saveData: true, effectiveType: "4g", downlink: 12,
                             deviceMemory: 8, hardwareConcurrency: 8 }),
  /Data Saver on.*4g.*12.*8 GB.*8 cores/,
  "the About line must name every signal that was actually available");

console.log("PASS: opening-quality choice (device + link aware)");
