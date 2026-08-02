import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { strict as assert } from "node:assert";

const source = readFileSync(resolve(import.meta.dirname, "../src/ui/RemoteScreen.tsx"), "utf8");
const broken = source.slice(source.indexOf("const onBroken = () =>"), source.indexOf("a.addEventListener(\"playing\""));

assert.ok(
  broken.includes("if (audioRetryRef.current !== null) return"),
  "a burst of stalled/error/ended events must coalesce into one audio retry",
);
assert.ok(
  broken.includes("audioRetryRef.current = null") &&
    broken.indexOf("await audioStreamUrl(token)") < broken.indexOf("audioRetryRef.current = null") &&
    broken.indexOf("audioRetryRef.current = null") < broken.indexOf("a.src = `${url}&t=${Date.now()}`"),
  "the retry slot must remain occupied through ticket fetch and reopen for the new source",
);
assert.ok(
  broken.includes("generation !== audioGenerationRef.current") && broken.includes("!a.src"),
  "an async retry must not resurrect sound after Stop or unmount",
);
assert.ok(
  source.includes("if (audioRetryRef.current !== null) window.clearTimeout(audioRetryRef.current)"),
  "unmount must cancel the single pending audio retry even when the timer id is zero",
);

console.log("audio retry lifecycle tests passed");
