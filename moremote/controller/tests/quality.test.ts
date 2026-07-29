import assert from "node:assert/strict";
import {
  pickStartPreset, describeHints,
  PRESET_DATA_SAVER, PRESET_BALANCED, PRESET_SHARP,
} from "../src/lib/quality.ts";

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

// ── A browser that reports nothing keeps the old, safe behaviour ─────────────────────────
// Desktop Safari and Firefox expose no Network Information at all. Silence must not be read
// as either fast or slow, or the majority of desktops get a guess instead of a default.
assert.equal(pickStartPreset({}), PRESET_BALANCED,
  "no signals at all must fall back to Balanced, exactly as before this existed");
assert.equal(pickStartPreset(), PRESET_BALANCED, "no argument at all must be safe too");

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
