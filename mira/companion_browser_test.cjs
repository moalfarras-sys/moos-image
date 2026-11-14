// Optional real-browser qualification against test_companion's private loopback
// server. Fixture cookie arrives on stdin, never argv, logs or durable storage.
'use strict';
const assert = require('node:assert/strict');
const readline = require('node:readline');
const { chromium } = require('playwright');
const lines = readline.createInterface({ input: process.stdin });
const pending = [];
const queued = [];
lines.on('line', line => {
  const data = JSON.parse(line);
  if (pending.length) pending.shift()(data); else queued.push(data);
});
const next = () => queued.length ? Promise.resolve(queued.shift()) : new Promise(resolve => pending.push(resolve));
async function step(name) {
  process.stdout.write('STEP ' + name + '\n');
  assert.equal((await next()).ack, name);
}

(async () => {
  const input = await next();
  const browser = await chromium.launch({ headless: true,
    ...(process.env.MIRA_BROWSER_EXECUTABLE ? { executablePath: process.env.MIRA_BROWSER_EXECUTABLE } : {}) });
  try {
    const context = await browser.newContext({ viewport: { width: 380, height: 780 },
      isMobile: true, hasTouch: true, locale: 'ar', reducedMotion: 'reduce' });
    await context.addCookies([{ name: 'mira_session', value: input.cookie, url: input.origin,
      httpOnly: true, sameSite: 'Strict' }]);
    await context.addInitScript(() => {
      window.privateReviewSnapshots = 0;
      const NativeEventSource = window.EventSource;
      window.EventSource = class extends NativeEventSource {
        constructor(...args) {
          super(...args);
          this.addEventListener('snapshot', () => { window.privateReviewSnapshots += 1; });
        }
      };
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.name));
    await page.goto(input.origin);
    await page.waitForSelector('#app[data-conn="live"]');
    await page.waitForFunction(() => !document.getElementById('talk').disabled);
    assert.match(await page.locator('#voice-hint').innerText(), /ميكروفون الكمبيوتر/);
    assert.match(await page.locator('#voice-hint').innerText(), /الهاتف لا/);
    assert.equal(await page.locator('#talk').evaluate(el => el.classList.contains('dim')), false);
    assert.equal(await page.locator('html').getAttribute('dir'), 'rtl');

    async function bounds(label) {
      const geometry = await page.evaluate(() => {
        const ids = ['dock', 'talk', 'field', 'send', 'voice-hint', 'chat'];
        return ids.map(id => {
          const r = document.getElementById(id).getBoundingClientRect();
          return { id, x: r.x, y: r.y, right: r.right, bottom: r.bottom, w: r.width, h: r.height,
            vw: innerWidth, vh: innerHeight };
        });
      });
      for (const r of geometry) assert.ok(r.x >= -1 && r.y >= -1 && r.right <= r.vw + 1 &&
        r.bottom <= r.vh + 1 && r.w > 0 && r.h > 0, label + ': clipped ' + r.id);
      assert.ok(geometry.find(r => r.id === 'chat').h >= 64, label + ': no usable conversation room');
    }
    await bounds('portrait');
    const talkRequest = page.waitForRequest(r => r.url().endsWith('/api/talk') && r.method() === 'POST');
    await page.locator('#talk').click();
    await talkRequest;
    await step('active');
    await page.waitForFunction(() => document.getElementById('talk-label').textContent === 'إيقاف');
    const stopRequest = page.waitForRequest(r => r.url().endsWith('/api/stop') && r.method() === 'POST');
    await page.locator('#talk').click();
    await stopRequest;
    await step('busy');
    await page.waitForFunction(() => document.getElementById('talk').disabled);
    assert.match(await page.locator('#voice-hint').innerText(), /مشغول/);
    await step('setup');
    await page.waitForFunction(() => document.getElementById('voice-hint').textContent.includes('أكمل إعداد'));
    assert.equal(await page.locator('#talk').isDisabled(), true);
    await step('retry');
    await page.waitForFunction(() => !document.getElementById('talk').disabled);
    assert.match(await page.locator('#voice-hint').innerText(), /اختبار نصي/);
    assert.match(await page.locator('#voice-hint').innerText(), /لم يتأكد/);
    const retryRequest = page.waitForRequest(r => r.url().endsWith('/api/talk') && r.method() === 'POST');
    await page.locator('#talk').click();
    await retryRequest;
    await step('echo');
    await page.waitForFunction(() => !document.getElementById('talk').disabled);
    assert.match(await page.locator('#voice-hint').innerText(), /ميكروفون Echo/);
    await page.setViewportSize({ width: 780, height: 380 });
    await page.waitForTimeout(100);
    await bounds('landscape');
    const manifest = await page.request.get(input.origin + '/manifest.webmanifest');
    assert.equal((await manifest.json()).orientation, 'any');
    // A real EventSource disconnect/reconnect retains the browser session and
    // restores fresh measured state. The private server alone closes streams.
    const previousSnapshots = await page.evaluate(() => window.privateReviewSnapshots);
    await step('disconnect');
    await page.waitForFunction(previous => window.privateReviewSnapshots > previous, previousSnapshots);
    await page.waitForSelector('#app[data-conn="live"]');
    await page.waitForFunction(() => !document.getElementById('talk').disabled);
    await step('english');
    await page.waitForFunction(() => document.documentElement.lang === 'en');
    assert.match(await page.locator('#voice-hint').innerText(), /computer microphone/);
    await bounds('landscape-ltr');
    // Guard the scope: no browser capture API or audio route was requested.
    assert.equal(await page.evaluate(() => document.getElementById('talk').getAttribute('aria-describedby')), 'voice-hint');
    assert.deepEqual(errors, []);
    console.log('MIRA_COMPANION_BROWSER_PASS portrait landscape RTL LTR desktop-Echo busy setup SSE-reconnect');
    await context.close();
  } finally {
    await browser.close();
    lines.close();
  }
})().catch(error => {
  // No request URL, headers, cookies or page text can enter a failed receipt.
  console.error('MIRA_COMPANION_BROWSER_FAIL ' + error.name + ': ' +
    (error.code === 'ERR_ASSERTION' ? String(error.message).split('\n')[0] : 'browser journey failed'));
  process.exitCode = 1;
  lines.close();
});
