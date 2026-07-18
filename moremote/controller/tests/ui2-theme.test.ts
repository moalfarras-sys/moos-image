import assert from "node:assert/strict";
import {existsSync, readFileSync, readdirSync} from "node:fs";
import {dirname, resolve} from "node:path";
import {fileURLToPath} from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const controller = resolve(here, "..");
const repo = resolve(controller, "../..");
const source = readFileSync(resolve(controller, "src/styles.css"), "utf8").toLowerCase();

const dark = [
  "#14191c", "#1d2529", "#232d32", "#2c383e", "#4ed7c8", "#78afff", "#a8f1e8",
  "#69d9a5", "#f4c56a", "#ff7d88", "#e8f1ef", "#9cafac", "#415158",
];
const light = [
  "#d8ebe7", "#c9e2dd", "#e1f0ec", "#b8d8d2", "#006d67", "#1d6278", "#0b6965",
  "#086b4b", "#7b520f", "#a52f3f", "#17302e", "#466360", "#527f79",
];
const legacy = [
  "#0b0f19", "#5b8cff", "#7c5cff", "#ef4444", "#ffffff", "#fff",
  "#087e77", "#246b83", "#0a9d92", "#147a58", "#986515", "#b23b4a",
  "#58736f", "#8ebab3",
];

assert.match(source, /@media\s*\(prefers-color-scheme:\s*light\)/);
for (const token of [...dark, ...light]) assert.ok(source.includes(token), `source misses ${token}`);
for (const token of legacy) assert.ok(!source.includes(token), `source retains legacy ${token}`);

const assets = resolve(repo, "moremote/agent/wwwroot/assets");
const cssFiles = readdirSync(assets).filter((name) => name.endsWith(".css"));
assert.equal(cssFiles.length, 1, "the shipping bundle must contain one current CSS asset");
const bundle = readFileSync(resolve(assets, cssFiles[0]), "utf8").toLowerCase();
for (const token of [...dark, ...light]) assert.ok(bundle.includes(token), `bundle misses ${token}`);
for (const token of legacy) assert.ok(!bundle.includes(token), `bundle retains legacy ${token}`);

const html = readFileSync(resolve(repo, "moremote/agent/wwwroot/index.html"), "utf8");
const linkedCss = html.match(/href="\/(assets\/[^\"]+\.css)"/)?.[1];
assert.ok(linkedCss && existsSync(resolve(repo, "moremote/agent/wwwroot", linkedCss)),
  "shipping index does not reference the generated CSS asset");
assert.match(html, /content="#14191c" media="\(prefers-color-scheme: dark\)"/);
assert.match(html, /content="#d8ebe7" media="\(prefers-color-scheme: light\)"/);

// The palette + CSS now live in ONE shared module (/usr/lib/moos/moos_ui2.py);
// the native GTK panel imports them instead of carrying its own copy.
const sharedPalette = readFileSync(resolve(repo, "system_files/usr/lib/moos/moos_ui2.py"), "utf8").toLowerCase();
for (const token of [...dark, ...light]) assert.ok(sharedPalette.includes(token), `shared palette misses ${token}`);
for (const token of legacy) assert.ok(!sharedPalette.includes(token), `shared palette retains legacy ${token}`);
assert.match(sharedPalette, /def gtk_prefers_dark\(\)/);

const nativePanel = readFileSync(resolve(repo, "system_files/usr/bin/mo-pc-remote"), "utf8").toLowerCase();
assert.match(nativePanel, /from moos_ui2 import[^\n]*\bui2_dark\b/,
  "native panel must import the shared dark palette");
assert.match(nativePanel, /from moos_ui2 import[^\n]*\bui2_light\b/,
  "native panel must import the shared light palette");
assert.match(nativePanel, /from moos_ui2 import[^\n]*\bgtk_prefers_dark\b/,
  "native panel must import the shared dark-preference probe");
assert.match(nativePanel, /add_css_class\("ui2-card"\)/);

console.log("PASS: Mo PC Remote UI2 source, shipping bundle, and native GTK palette");
