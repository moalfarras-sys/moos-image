import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { BUILD } from "../src/types.ts";

// The controller is TypeScript, but the image does not ship TypeScript. It ships the vite
// output, and that output is COMMITTED, at moremote/agent/wwwroot — vite.config.ts writes
// there (`outDir: "../agent/wwwroot"`) and build.sh copies the directory into the image.
//
// So there are two copies of this UI in the repo and only one of them ever reaches a phone.
// Editing src/ and not running `npm run build` leaves the source correct, every test in this
// directory green, every Python gate green, and the shipped bundle unchanged — a silent
// no-op release. That is not hypothetical: the whole reason the rotation fix needed a
// hand-built agent under ~/.local to be testable at all was that shipping it depends on
// somebody remembering a command.
//
// This is the cheap half of the guard. It reads the BUILD marker the app displays in its
// About section and requires it to be present in the committed bundle, so bumping the marker
// without rebuilding fails here in milliseconds with no npm install and no network.
//
// The exhaustive half is in CI ("Controller bundle is built from the committed source"),
// which runs `npm ci && npm run build` and fails on any diff at all — including code changes
// made without touching the marker, which this test cannot see.

const WWWROOT = new URL("../../agent/wwwroot/", import.meta.url).pathname;

const assets = readdirSync(join(WWWROOT, "assets")).filter((f) => f.endsWith(".js"));
assert.ok(assets.length > 0,
  "moremote/agent/wwwroot/assets contains no JavaScript — the committed bundle is missing " +
  "entirely, and the image would ship an app that cannot start");

const bundled = assets.map((f) => readFileSync(join(WWWROOT, "assets", f), "utf8")).join("\n");

assert.ok(bundled.includes(BUILD),
  `the committed bundle does not contain BUILD ${JSON.stringify(BUILD)} from src/types.ts — ` +
  "moremote/agent/wwwroot is stale, so the image would ship the PREVIOUS controller while " +
  "the source, and every test that reads the source, describes the new one. " +
  "Run `npm run build` in moremote/controller and commit moremote/agent/wwwroot.");

// The service worker precaches the app shell, so a stale sw.js can pin a phone to an old
// bundle even after the bundle itself is updated. It must reference the assets that are
// actually present, or the first offline load serves files that no longer exist.
const sw = readFileSync(join(WWWROOT, "sw.js"), "utf8");
const precachedNames = [...sw.matchAll(/assets\/([A-Za-z0-9._-]+\.js)/g)].map((m) => m[1]);
assert.ok(precachedNames.length > 0,
  "sw.js precaches no assets/*.js — the service worker was generated against a different " +
  "build than the one committed");
for (const name of precachedNames) {
  assert.ok(assets.includes(name),
    `sw.js precaches assets/${name}, which is not in the committed bundle — the service ` +
    "worker and the bundle come from different builds, and an installed PWA would fetch a " +
    "file the image does not contain");
}

console.log(`PASS: committed bundle carries BUILD ${JSON.stringify(BUILD)} and a matching service worker`);
