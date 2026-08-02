import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {dirname, resolve} from "node:path";
import {fileURLToPath} from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const remote = readFileSync(resolve(here, "../src/ui/RemoteScreen.tsx"), "utf8");
const app = readFileSync(resolve(here, "../src/App.tsx"), "utf8");
const icons = readFileSync(resolve(here, "../src/ui/icons.tsx"), "utf8");
const styles = readFileSync(resolve(here, "../src/styles.css"), "utf8");

assert.ok(icons.includes('aria-hidden="true" focusable="false"'),
  "decorative glyphs must not duplicate the adjacent accessible button/status text");

for (const name of ["IconFile", "IconFolder", "IconArrowUp", "IconRotate", "IconLock", "IconPlug"]) {
  assert.ok(icons.includes(`export const ${name}`), `Tidal Cut set misses ${name}`);
}
for (const cheap of ['>🔌<', '"📁"', '"📄"', '>⬆ Up<', '>↻ Sideways<', '>🔒 Upright<']) {
  assert.ok(!remote.includes(cheap) && !app.includes(cheap), `visible UI retains text glyph ${cheap}`);
}
for (const contract of ["<IconFolder />", "<IconFile />", "<IconArrowUp />", "<IconRotate />", "<IconLock />"]) {
  assert.ok(remote.includes(contract), `Remote surface does not use ${contract}`);
}
assert.ok(app.includes('<IconPlug className="error-glyph" />'));
assert.match(styles, /\.file-ic svg\s*\{[\s\S]*?width:\s*20px;[\s\S]*?height:\s*20px;/,
  "file glyphs need a deterministic small-size ladder");

console.log("PASS: Remote error, orientation and file surfaces use one scalable Tidal Cut icon set");
