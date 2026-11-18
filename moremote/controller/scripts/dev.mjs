/**
 * Develop the controller against a real agent, without Vite.
 *
 *   npm run dev                         # build into dist/, rebuild on change, serve :5173
 *   MO_AGENT=https://host.ts.net npm run dev
 *   npm run preview                     # serve the committed ../agent/wwwroot as built
 *
 * /api and /ws are proxied to MO_AGENT (default http://localhost:8765) with Host AND Origin
 * rewritten: the agent's cross-origin check (rightly) 403s a WebSocket that claims to come
 * from localhost:5173, so a remote MO_AGENT stream never starts without the Origin rewrite.
 * Reload the page after a rebuild; there is no hot module replacement.
 */
import http from "node:http";
import https from "node:https";
import { watch } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import { dirname, extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "./build.mjs";
import { DEV_PORT, DEV_PROXY, OUT_DIR } from "../build.config.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const preview = process.argv.includes("--preview");
const SERVE = preview ? resolve(ROOT, OUT_DIR) : resolve(ROOT, "dist");
const AGENT = new URL(process.env.MO_AGENT || "http://localhost:8765");
const client = AGENT.protocol === "https:" ? https : http;
const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".webmanifest": "application/manifest+json",
  ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon", ".woff2": "font/woff2",
};

let building = Promise.resolve();
async function rebuild(reason) {
  building = building.then(async () => {
    try {
      const result = await build({ outDir: SERVE });
      console.log(`[dev] ${reason}: built ${result.js}`);
    } catch (error) {
      console.error(`[dev] build failed: ${error.message}`);
    }
  });
  return building;
}

const proxied = (path) => DEV_PROXY.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
const upstreamHeaders = (headers) => ({ ...headers, host: AGENT.host, origin: AGENT.origin });

async function serveFile(req, res) {
  await building;
  let path = decodeURIComponent(new URL(req.url, "http://dev").pathname);
  const file = join(SERVE, normalize(path).replace(/^([/\\]*\.\.)+/, ""));
  let target = file;
  try {
    if (!file.startsWith(SERVE + sep) || !(await stat(file)).isFile()) target = join(SERVE, "index.html");
  } catch {
    target = join(SERVE, "index.html");
  }
  res.writeHead(200, { "content-type": TYPES[extname(target)] || "application/octet-stream", "cache-control": "no-store" });
  res.end(await readFile(target));
}

const server = http.createServer((req, res) => {
  const path = new URL(req.url, "http://dev").pathname;
  if (!proxied(path)) {
    serveFile(req, res).catch((error) => { res.writeHead(500); res.end(String(error)); });
    return;
  }
  const upstream = client.request(new URL(req.url, AGENT), {
    method: req.method, headers: upstreamHeaders(req.headers),
  }, (answer) => {
    res.writeHead(answer.statusCode ?? 502, answer.headers);
    answer.pipe(res);
  });
  upstream.on("error", (error) => { res.writeHead(502); res.end(`agent unreachable: ${error.message}`); });
  req.pipe(upstream);
});

server.on("upgrade", (req, socket, head) => {
  if (!proxied(new URL(req.url, "http://dev").pathname)) { socket.destroy(); return; }
  const upstream = client.request(new URL(req.url, AGENT), { headers: upstreamHeaders(req.headers) });
  upstream.on("upgrade", (answer, agentSocket, agentHead) => {
    const lines = [`HTTP/1.1 ${answer.statusCode} ${answer.statusMessage}`];
    for (let i = 0; i < answer.rawHeaders.length; i += 2) lines.push(`${answer.rawHeaders[i]}: ${answer.rawHeaders[i + 1]}`);
    socket.write(`${lines.join("\r\n")}\r\n\r\n`);
    if (agentHead.length) socket.write(agentHead);
    if (head.length) agentSocket.write(head);
    agentSocket.pipe(socket).pipe(agentSocket);
    agentSocket.on("error", () => socket.destroy());
    socket.on("error", () => agentSocket.destroy());
  });
  upstream.on("response", (answer) => {
    socket.end(`HTTP/1.1 ${answer.statusCode} ${answer.statusMessage}\r\n\r\n`);
  });
  upstream.on("error", () => socket.destroy());
  upstream.end();
});

if (!preview) {
  await rebuild("start");
  let timer;
  for (const dir of ["src", "sw", "public"]) {
    watch(join(ROOT, dir), { recursive: true }, () => {
      clearTimeout(timer);
      timer = setTimeout(() => rebuild("change"), 120);
    });
  }
  watch(join(ROOT, "index.html"), () => rebuild("index.html"));
}
server.listen(DEV_PORT, "0.0.0.0", () => {
  console.log(`[dev] ${preview ? "preview of" : "serving"} ${SERVE} on http://localhost:${DEV_PORT}; /api and /ws -> ${AGENT.origin}`);
});
