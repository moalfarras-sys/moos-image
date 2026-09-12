/**
 * Run tests/browser-input.test.mjs against the SHIPPED bundle in a real Chromium.
 *
 * The browser test is the only gate that exercises the production JavaScript end to end — the
 * node tests each import one module, which is exactly how an inverted wheel survived in the
 * callback that wires two correct modules together. It had no runner in the repository, so it
 * was run by hand and therefore not run. This is the runner.
 *
 *   node scripts/browser-test.mjs            # serve the built bundle, launch Chromium, run
 *   MO_REMOTE_EVIDENCE=/path node ...        # also write the screenshots the docs reference
 *
 * It serves moremote/agent/wwwroot (the committed bundle, so a stale build is caught by
 * bundle-freshness.test.ts rather than silently tested), starts Chromium with a CDP port, and
 * hands both to the test through the environment variables it already reads.
 */
import {createServer} from 'node:http';
import {spawn} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {existsSync, statSync} from 'node:fs';
import {extname, join, normalize, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.MO_REMOTE_PLAYWRIGHT || 'playwright');

const ROOT = join(here, '..', '..', 'agent', 'wwwroot');
const PORT = Number(process.env.MO_REMOTE_TEST_PORT || 5178);
const CDP_PORT = Number(process.env.MO_REMOTE_CDP_PORT || 9228);
const TYPES = {
  '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
  '.webmanifest': 'application/manifest+json',
};

const server = createServer(async (req, res) => {
  let path = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (path === '/') path = '/index.html';
  const file = join(ROOT, normalize(path).replace(/^(\.\.[/\\])+/, ''));
  if (!existsSync(file) || !statSync(file).isFile()) { res.writeHead(404); return res.end('not found'); }
  res.writeHead(200, {'content-type': TYPES[extname(file)] || 'application/octet-stream'});
  res.end(await readFile(file));
});
await new Promise(resolve => server.listen(PORT, '127.0.0.1', resolve));

// Launched rather than connected-to, so the test needs no browser running beforehand. The test
// itself reconnects over CDP, which is how it can open several isolated contexts of its own.
const browser = await chromium.launch({args: [`--remote-debugging-port=${CDP_PORT}`]});

let code = 0;
try {
  await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [join(here, '..', 'tests', 'browser-input.test.mjs')], {
      stdio: 'inherit',
      env: {
        ...process.env,
        MO_REMOTE_CDP: `http://127.0.0.1:${CDP_PORT}`,
        MO_REMOTE_TEST_URL: `http://127.0.0.1:${PORT}`,
      },
    });
    child.on('exit', status => status === 0 ? resolve() : reject(new Error(`browser test exited ${status}`)));
    child.on('error', reject);
  });
} catch (error) {
  console.error(String(error.message ?? error));
  code = 1;
} finally {
  await browser.close();
  server.close();
}
process.exit(code);
