/**
 * Turning "the field used to say X, now it says Y" into keystrokes.
 *
 * WHY THIS IS A MODULE AND NOT A BRANCH INSIDE onInput
 *
 * The phone types through a hidden field: the browser owns the text, and the controller works out
 * what changed and sends that. Two callers need that answer — the ordinary `input` event, and the
 * end of an IME composition — and until now only ONE of them had it. `onCompositionEnd` carried
 * its own three-line approximation:
 *
 *     const committed = after.startsWith(before) ? after.slice(before.length) : e.data;
 *     if (committed) conn.text(committed);
 *
 * which is correct only when a composition purely APPENDS. It has two failure modes and an iPhone
 * Arabic keyboard hits both several times a sentence:
 *
 *   * A composition that REPLACES what it was composing (every autocorrect, every suggestion tap)
 *     takes the `e.data` branch and sends the whole composed string WITHOUT deleting the letters
 *     it replaced. The field says "السلام"; the desktop ends up with "سلاالسلام". Worse, the
 *     baseline is then set to the field's value, so every later keystroke is diffed against a
 *     string that no longer describes the desktop and the divergence compounds for the rest of
 *     the session.
 *
 *   * A composition that SHRINKS — backspacing through a marked Arabic word — has `after` shorter
 *     than `before`, so `startsWith` is false and `e.data` is empty. `committed` is falsy and
 *     NOTHING is sent. The word is gone from the phone and still on the desktop.
 *
 * The `input` path already knew how to do this properly, including a bidi guard that took real
 * effort to get right. Extracting it means the composition path inherits all of it instead of
 * re-deriving a worse version, and it means the logic can be tested without a phone in hand —
 * which is what tests/typing.test.ts now does.
 */

/** One keystroke instruction. `n` is a repeat count for key taps. */
export type Op =
  | { t: "text"; v: string }
  | { t: "key"; k: string; n: number };

/**
 * The characters whose presence makes caret-relative movement unsafe.
 *
 * Arrow keys move the caret VISUALLY, not logically: Qt's default LogicalMoveStyle reverses the
 * mapping inside an RTL run, so ArrowLeft walks FORWARD through Arabic. Stepping back over a
 * shared suffix with it would delete that suffix instead of the differing middle and drop the
 * replacement at the end — re-scrambling the very text the replace path exists to repair.
 */
const BIDI = /[֐-ࣿיִ-﷿ﹰ-﻿]/;

/**
 * What to send so the remote field goes from `before` to `after`.
 *
 * Pure, total, and order-significant: the caller must emit the ops in sequence.
 */
export function diffToOps(before: string, after: string): Op[] {
  if (before === after) return [];

  // Pure append — the overwhelmingly common case, and the cheapest.
  if (after.length > before.length && after.startsWith(before)) {
    return [{ t: "text", v: after.slice(before.length) }];
  }

  // Pure delete from the end.
  if (after.length < before.length && before.startsWith(after)) {
    return [{ t: "key", k: "Backspace", n: before.length - after.length }];
  }

  // Replaced (autocorrect / IME rewrite). Deleting the WHOLE line and retyping it turned one
  // autocorrect into a Backspace storm — up to 300 taps — that visibly stalled the session.
  // Autocorrect rewrites one word: keep the common prefix AND suffix, delete only the differing
  // middle, retype it.
  let p = 0;
  const max = Math.min(before.length, after.length);
  while (p < max && before[p] === after[p]) p++;
  let sf = 0;
  while (sf < max - p && before[before.length - 1 - sf] === after[after.length - 1 - sf]) sf++;

  // Only sf === 0 needs no walk at all, so when the rewrite carries a shared suffix in
  // bidirectional text, rewrite the whole tail instead: more keystrokes, but every one of them is
  // direction-independent. See BIDI above for why the walk cannot be trusted there.
  const walk = sf > 0 && !BIDI.test(before + after);
  const removed = walk ? before.length - p - sf : before.length - p;
  const middle = walk ? after.slice(p, after.length - sf) : after.slice(p);

  const ops: Op[] = [];
  // The remote caret sits at the end of what we sent; step over the shared suffix, delete the
  // middle, type the replacement, then walk back.
  if (walk && sf > 0) ops.push({ t: "key", k: "ArrowLeft", n: sf });
  if (removed > 0) ops.push({ t: "key", k: "Backspace", n: removed });
  if (middle) ops.push({ t: "text", v: middle });
  if (walk && sf > 0) ops.push({ t: "key", k: "ArrowRight", n: sf });
  return ops;
}
