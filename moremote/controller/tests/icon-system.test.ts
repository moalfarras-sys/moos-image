import assert from "node:assert/strict";
import {readFileSync, readdirSync} from "node:fs";
import {dirname, resolve} from "node:path";
import {fileURLToPath} from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
// Since v56 the remote surface spans RemoteScreen, the kit and the dock/keyboard/sheet components.
const remoteDir = resolve(here, "../src/ui/remote");
const remote = [
  readFileSync(resolve(here, "../src/ui/RemoteScreen.tsx"), "utf8"),
  readFileSync(resolve(here, "../src/ui/kit.tsx"), "utf8"),
  readFileSync(resolve(here, "../src/ui/Touchpad.tsx"), "utf8"),
  ...readdirSync(remoteDir).filter((f) => f.endsWith(".tsx")).sort()
    .map((f) => readFileSync(resolve(remoteDir, f), "utf8")),
].join("\n");
const app = readFileSync(resolve(here, "../src/App.tsx"), "utf8");
const icons = readFileSync(resolve(here, "../src/ui/icons.tsx"), "utf8");
const styles = readFileSync(resolve(here, "../src/styles.css"), "utf8");

assert.ok(icons.includes('aria-hidden="true" focusable="false"'),
  "decorative glyphs must not duplicate the adjacent accessible button/status text");

for (const name of ["IconFile", "IconFolder", "IconArrowUp", "IconRotate", "IconLock", "IconPlug", "IconClose", "IconPause", "IconBackspace", "IconEnter", "IconDesktop", "IconConnection",
  "IconTouch", "IconMoos", "IconTransfer", "IconLauncher", "IconSparkle", "IconSearch", "IconTerminal", "IconOverview", "IconCamera", "IconKeyboardHide"]) {
  assert.ok(icons.includes(`export const ${name}`), `Tidal Cut set misses ${name}`);
}
for (const cheap of ['>🔌<', '"📁"', '"📄"', '>⬆ Up<', '>↻ Sideways<', '>🔒 Upright<', '>×</button>', '>⏸ ', '>⌫</button>', '>↵</button>']) {
  assert.ok(!remote.includes(cheap) && !app.includes(cheap), `visible UI retains text glyph ${cheap}`);
}
for (const contract of ["<IconFolder />", "<IconFile />", "<IconArrowUp />", "<IconRotate />", "<IconLock />", "<IconClose />", "<IconPause />", "<IconConnection />", "<IconDesktop />", "<IconBackspace />", "<IconEnter />",
  "<IconTouch />", "<IconTrackpad />", "<IconMouse />", "<IconMoos />", "<IconTransfer />", "<IconKeyboardHide />"]) {
  assert.ok(remote.includes(contract), `Remote surface does not use ${contract}`);
}
assert.ok(app.includes('<IconPlug className="error-glyph" />'));
assert.match(styles, /\.file-ic svg\s*\{[\s\S]*?width:\s*20px;[\s\S]*?height:\s*20px;/,
  "file glyphs need a deterministic small-size ladder");
assert.ok(!styles.includes('content: "✦ ";'), "credits must not depend on a font-specific dingbat");

console.log("PASS: Remote error, orientation and file surfaces use one scalable Tidal Cut icon set");
