import assert from "node:assert/strict";
import { diffToOps, type Op } from "../src/lib/typing.ts";

/** Replay ops against `before` the way the remote field would, so a diff can be checked end to end. */
function apply(before: string, ops: Op[]): string {
  // The remote caret sits at the end of what we sent. ArrowLeft/Right move it; Backspace deletes
  // to its left; text inserts at it. That is exactly what the desktop does with these keystrokes.
  let s = before, caret = before.length;
  for (const op of ops) {
    if (op.t === "text") { s = s.slice(0, caret) + op.v + s.slice(caret); caret += op.v.length; }
    else if (op.k === "Backspace") {
      const n = Math.min(op.n, caret);
      s = s.slice(0, caret - n) + s.slice(caret); caret -= n;
    }
    else if (op.k === "ArrowLeft") caret = Math.max(0, caret - op.n);
    else if (op.k === "ArrowRight") caret = Math.min(s.length, caret + op.n);
  }
  return s;
}

/** The property that matters: whatever the ops are, replaying them must reach `after`. */
function roundTrip(before: string, after: string, what: string) {
  const got = apply(before, diffToOps(before, after));
  assert.equal(got, after,
    `${what}: replaying the ops on ${JSON.stringify(before)} gave ${JSON.stringify(got)}, ` +
    `expected ${JSON.stringify(after)}`);
}

// ── The ordinary cases ────────────────────────────────────────────────────────────────────
assert.deepEqual(diffToOps("abc", "abc"), [], "no change must send nothing");
assert.deepEqual(diffToOps("ab", "abc"), [{ t: "text", v: "c" }], "append sends only the tail");
assert.deepEqual(diffToOps("abc", "ab"), [{ t: "key", k: "Backspace", n: 1 }], "delete sends Backspace");
roundTrip("", "hello", "typing from empty");
roundTrip("hello", "", "clearing the field");

// ── THE TWO COMPOSITION BUGS THIS MODULE EXISTS TO FIX ────────────────────────────────────
// onCompositionEnd used to do `after.startsWith(before) ? after.slice(before.length) : e.data`,
// which is correct only for a composition that purely APPENDS.

// 1. A suggestion REWRITES the stem. The old code sent the whole composed word and deleted
//    nothing, so the desktop kept the replaced letters and the baseline silently diverged.
roundTrip("سلا", "السلام", "an IME suggestion that rewrites what it was composing");
assert.ok(diffToOps("سلا", "السلام").some(o => o.t === "key" && o.k === "Backspace"),
  "a rewrite must delete what it replaced — the old code deleted nothing and duplicated the stem");

// 2. Backspacing through a marked word made e.data empty, so NOTHING was sent and the word
//    stayed on the desktop after it was gone from the phone.
roundTrip("السلام", "الس", "backspacing through a composing word");
assert.ok(diffToOps("السلام", "الس").length > 0,
  "a shrinking composition must send deletions — the old code sent nothing at all");
roundTrip("مرحبا", "", "erasing a composed word entirely");

// ── Autocorrect in the middle, which is why the prefix/suffix walk exists ──────────────────
roundTrip("teh cat sat", "the cat sat", "autocorrect rewriting one word mid-line");
{
  // The guarantee is that it does not DELETE AND RETYPE the line — deleting the whole thing turned
  // one autocorrect into a Backspace storm (up to 300 taps) that visibly stalled the session. The
  // arrow walk that avoids it costs 2*suffix arrows, which is cheap and non-destructive, so what
  // is measured here is the destructive work: how much is erased and how much is retyped.
  const ops = diffToOps("teh cat sat", "the cat sat");
  const erased = ops.filter(o => o.t === "key" && o.k === "Backspace")
                    .reduce((n, o) => n + (o as { n: number }).n, 0);
  const retyped = ops.filter(o => o.t === "text")
                     .reduce((n, o) => n + (o as { v: string }).v.length, 0);
  assert.ok(erased <= 3, `a one-word autocorrect must erase only the differing middle (erased ${erased})`);
  assert.ok(retyped <= 3, `a one-word autocorrect must retype only the differing middle (retyped ${retyped})`);
}

// ── The bidi guard: arrows move VISUALLY, so they must not be used inside RTL text ─────────
// Qt's LogicalMoveStyle reverses arrow direction inside an RTL run, so a walk over a shared
// suffix would delete the wrong thing. In bidi text the whole tail is rewritten instead.
{
  const ops = diffToOps("كتاب جميل", "كتب جميل");
  assert.ok(!ops.some(o => o.t === "key" && (o.k === "ArrowLeft" || o.k === "ArrowRight")),
    "no arrow keys may be used when the text is bidirectional — they move visually, not logically");
  roundTrip("كتاب جميل", "كتب جميل", "an Arabic rewrite with a shared suffix");
}
// Latin text with a shared suffix MAY use the walk, and must still round-trip.
roundTrip("hello world", "help world", "a Latin rewrite with a shared suffix");

// ── Characters that are more than one code unit must not corrupt the diff ─────────────────
roundTrip("aَ", "a", "deleting an Arabic diacritic");
roundTrip("hi 😀", "hi", "deleting an emoji (a surrogate pair)");
roundTrip("hi", "hi 😀", "typing an emoji");

// ── Symbols and mixed scripts, which is what the owner actually types ─────────────────────
roundTrip("", "user@example.com", "an email address");
roundTrip("", "https://x.com/a?b=1&c=2", "a URL with symbols");
roundTrip("مرحبا", "مرحبا @الجميع", "Arabic followed by a symbol and more Arabic");
roundTrip("test", "test!", "a trailing symbol");

console.log("PASS: the field diff round-trips for append, delete, rewrite, bidi, emoji and symbols");
