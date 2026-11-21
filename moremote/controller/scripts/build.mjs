/**
 * Build the Mawj controller into agent/wwwroot (or another owned output directory).
 *
 *   node scripts/build.mjs            # the shipped bundle, ../agent/wwwroot
 *   node scripts/build.mjs --out dist # the dev server's private copy (gitignored)
 *
 * Why this is not Vite any more: see build.config.mjs. The pipeline is the one Vite 8 ran,
 * written out: rolldown (with oxc JSX and minifier) bundles src/main.tsx, lightningcss
 * minifies the one stylesheet, index.html receives the hashed tags, public/ is copied, the
 * web app manifest is written, and sw/sw.js is bundled with the Workbox runtime and the
 * generated precache list into a single classic sw.js.
 *
 * Every step is deterministic (sorted inputs, content hashes, no timestamps): CI rebuilds the
 * committed bundle and fails on any byte of difference.
 */
import { createHash } from "node:crypto";
import { cp, mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { rolldown } from "rolldown";
import { transform as transformCss } from "lightningcss";
import {
  CSS_TARGETS, JS_TARGET, MANIFEST, OUT_DIR, PRECACHE_EXTENSIONS,
} from "../build.config.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SHIPPED_OUT = resolve(ROOT, OUT_DIR);
const DEV_OUT = resolve(ROOT, "dist");

// The agent's pre-login policy serves exactly this shape of asset name before a device has
// signed in (agent/Core/PreLoginRequestPolicy.cs). A name it refuses would be a blank page
// on the login screen, so the build refuses it first.
const ASSET_NAME = /^assets\/[A-Za-z0-9][A-Za-z0-9_-]*\.(?:js|css)$/;
const DEV_ENTRY = '<script type="module" src="/src/main.tsx"></script>';
const PRODUCTION = { "process.env.NODE_ENV": JSON.stringify("production") };
// The minified output options Vite 8 passed to rolldown for an app build.
const OUTPUT = {
  minify: true,
  generatedCode: { preset: "es2015" },
  topLevelVar: true,
  comments: { annotation: false, jsdoc: false, legal: false },
};

const cssTargets = Object.fromEntries(Object.entries(CSS_TARGETS).map(([browser, version]) => {
  const [major, minor = 0] = Array.isArray(version) ? version : [version];
  return [browser, (major << 16) | (minor << 8)];
}));

const shortHash = (bytes) => createHash("sha256").update(bytes).digest("base64url").slice(0, 8);
const md5 = (bytes) => createHash("md5").update(bytes).digest("hex");
const posix = (path) => path.split(sep).join("/");

async function filesUnder(dir) {
  const found = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) found.push(...await filesUnder(path));
    else if (entry.isFile()) found.push(path);
    else throw new Error(`build: ${path} is neither a file nor a directory`);
  }
  return found.sort();
}

async function bundleApp() {
  const stylesheets = [];
  const bundle = await rolldown({
    input: join(ROOT, "src", "main.tsx"),
    platform: "browser",
    transform: { target: JS_TARGET, jsx: { runtime: "automatic" }, define: PRODUCTION },
    plugins: [{
      // The stylesheet is emitted by lightningcss below; the import only orders it.
      name: "mo-remote-stylesheet",
      load(id) {
        if (!id.endsWith(".css")) return null;
        stylesheets.push(id);
        return { code: "", moduleType: "js", moduleSideEffects: false };
      },
    }],
  });
  try {
    const { output } = await bundle.generate({
      format: "es",
      entryFileNames: "assets/index-[hash].js",
      chunkFileNames: "assets/[name]-[hash].js",
      ...OUTPUT,
    });
    if (output.length !== 1 || output[0].type !== "chunk") {
      throw new Error(`build: expected one JavaScript chunk, rolldown produced ${output.map((o) => o.fileName).join(", ")}`);
    }
    if (stylesheets.length !== 1) {
      throw new Error(`build: expected one imported stylesheet, found ${stylesheets.length}`);
    }
    return { js: output[0], stylesheet: stylesheets[0] };
  } finally {
    await bundle.close();
  }
}

async function buildStylesheet(path) {
  const source = await readFile(path, "utf8");
  // No asset pipeline exists for CSS: a url() or @import would ship a reference to a file the
  // agent does not serve. Refuse it rather than emit a silently broken stylesheet.
  if (/@import\b|url\(/i.test(source.replace(/\/\*[\s\S]*?\*\//g, ""))) {
    throw new Error(`build: ${relative(ROOT, path)} uses url() or @import, which this build does not resolve`);
  }
  const { code, warnings } = transformCss({
    filename: relative(ROOT, path), code: Buffer.from(source), minify: true, targets: cssTargets,
  });
  if (warnings.length) {
    throw new Error(`build: lightningcss warned about ${relative(ROOT, path)}: ${warnings.map((w) => w.message).join("; ")}`);
  }
  return Buffer.concat([code, Buffer.from("\n")]);
}

async function bundleServiceWorker(entries) {
  const bundle = await rolldown({
    input: join(ROOT, "sw", "sw.js"),
    platform: "browser",
    transform: { target: JS_TARGET, define: PRODUCTION },
    plugins: [{
      name: "mo-remote-precache-manifest",
      resolveId(id) { return id === "virtual:precache-manifest" ? "\0precache-manifest" : null; },
      load(id) {
        return id === "\0precache-manifest" ? `export default ${JSON.stringify(entries)};` : null;
      },
    }],
  });
  try {
    const { output } = await bundle.generate({ format: "iife", ...OUTPUT });
    if (output.length !== 1 || output[0].type !== "chunk") {
      throw new Error("build: the service worker must bundle into exactly one classic script");
    }
    return output[0].code;
  } finally {
    await bundle.close();
  }
}

export async function build({ outDir = SHIPPED_OUT } = {}) {
  outDir = resolve(outDir);
  // The output directory is emptied first, so only the two owned destinations are accepted.
  if (outDir !== SHIPPED_OUT && outDir !== DEV_OUT) {
    throw new Error(`build: refusing to empty ${outDir}; use ${OUT_DIR} or dist`);
  }
  const html = await readFile(join(ROOT, "index.html"), "utf8");
  if (html.split(DEV_ENTRY).length !== 2 || !html.includes("</head>")) {
    throw new Error(`build: index.html must contain exactly one ${DEV_ENTRY} and a </head>`);
  }

  const { js, stylesheet } = await bundleApp();
  const css = await buildStylesheet(stylesheet);
  const cssName = `assets/index-${shortHash(css)}.css`;
  for (const name of [js.fileName, cssName]) {
    if (!ASSET_NAME.test(name)) throw new Error(`build: ${name} is not a name the agent serves before login`);
  }

  await rm(outDir, { recursive: true, force: true });
  await mkdir(join(outDir, "assets"), { recursive: true });
  const publicDir = join(ROOT, "public");
  if (existsSync(publicDir)) await cp(publicDir, outDir, { recursive: true });
  await writeFile(join(outDir, js.fileName), js.code);
  await writeFile(join(outDir, cssName), css);
  await writeFile(join(outDir, "index.html"), html
    .replace(/\n[ \t]*<script type="module" src="\/src\/main\.tsx"><\/script>/, "")
    .replace("</head>",
      `  <script type="module" crossorigin src="/${js.fileName}"></script>\n` +
      `    <link rel="stylesheet" crossorigin href="/${cssName}">\n` +
      `    <link rel="manifest" href="/manifest.webmanifest">\n  </head>`));
  await writeFile(join(outDir, "manifest.webmanifest"), `${JSON.stringify(MANIFEST)}\n`);

  // The app shell: every built file of a cached type, plus the manifest. Hashed assets are
  // revisioned by their name; everything else by its MD5, as Workbox's generator did.
  const entries = [];
  for (const path of await filesUnder(outDir)) {
    const url = posix(relative(outDir, path));
    if (url === "sw.js") continue;
    if (url !== "manifest.webmanifest" && !PRECACHE_EXTENSIONS.some((ext) => url.endsWith(ext))) continue;
    entries.push({ url, revision: url.startsWith("assets/") ? null : md5(await readFile(path)) });
  }
  for (const path of await filesUnder(join(outDir, "assets"))) {
    const url = posix(relative(outDir, path));
    if (!ASSET_NAME.test(url)) throw new Error(`build: ${url} is not a name the agent serves before login`);
  }
  await writeFile(join(outDir, "sw.js"), await bundleServiceWorker(entries));
  return { outDir, js: js.fileName, css: cssName, precached: entries.length };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const at = process.argv.indexOf("--out");
  const outDir = at > 0 ? resolve(ROOT, process.argv[at + 1] ?? "") : SHIPPED_OUT;
  const started = performance.now();
  const result = await build({ outDir });
  console.log(`built ${relative(ROOT, result.outDir) || "."}: ${result.js}, ${result.css}, ` +
    `sw.js precaching ${result.precached} files (${Math.round(performance.now() - started)} ms)`);
}
