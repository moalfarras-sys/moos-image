// Real browser integration with an isolated, intercepted transport. No live input.
// MO_REMOTE_PLAYWRIGHT points to an optional external Playwright installation.
import assert from 'node:assert/strict';
import {readFile, mkdir} from 'node:fs/promises';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.MO_REMOTE_PLAYWRIGHT || 'playwright');
const browser = await chromium.connectOverCDP(process.env.MO_REMOTE_CDP || 'http://127.0.0.1:9228');
const origin = process.env.MO_REMOTE_TEST_URL || 'http://127.0.0.1:5178';
const evidence = process.env.MO_REMOTE_EVIDENCE;
const frame = await readFile(new URL('../../../docs/evidence/mo-pc-remote-control-center-ar-1080p.png', import.meta.url));
const contexts = [];
const errors = [];
async function viewer(options, mode, language = 'en', cursorEmbedded = false) {
  const context = await browser.newContext({...options, serviceWorkers: 'block'});
  contexts.push(context);
  await context.addInitScript(({mode, language}) => {
    localStorage.setItem('mo_remote_token', 'isolated-browser-test');
    localStorage.setItem('moremote.mode', JSON.stringify(mode));
    localStorage.setItem('moremote.seenGestureHint', '1');
    localStorage.setItem('mo-remote-lang', language);
    localStorage.setItem('moremote.orient', '"upright"');
  }, {mode, language});
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    const body = path === '/api/status'
      ? {name:'Mo PC Remote', version:'test', firstRun:false, locked:false, lockoutSeconds:0, hostPowerAllowed:true}
      : path === '/api/devices' ? {devices:[]} : {ok:true, kind:'empty'};
    return route.fulfill({json:body});
  });
  const packets = [];
  const sockets = [];
  let autoHello = true;
  const hello = ws => {
    ws.send(JSON.stringify({type:'hello', screen:{w:1920,h:1080}, paused:false,
      cursorEmbedded, input:{ready:true}, clipboard:{ready:true}, monitors:[]}));
    ws.send(frame);
  };
  await page.routeWebSocket('**/ws', ws => {
    sockets.push(ws);
    ws.onMessage(message => {
      const msg = JSON.parse(String(message));
      packets.push(msg);
      if (msg.type === 'auth') {
        if (autoHello) hello(ws);
      } else if (msg.type === 'ping') ws.send(JSON.stringify({type:'pong',t:msg.t}));
      else if (msg.type === 'keyframe') ws.send(frame);
    });
  });
  await page.goto(origin);
  await page.locator('.toolbar-primary').waitFor();
  await page.locator('.topbar.mini[aria-expanded="false"]').waitFor();
  await page.waitForTimeout(100);
  return {page, packets, sockets, hello, holdHello: () => { autoHello = false; }};
}
function input(packets) {
  return packets.filter(p => ['text','key','combo','down','up','click','move','moveRelative','downCurrent','upCurrent','clickCurrent','dblclickCurrent'].includes(p.type));
}
async function capture(page, name) {
  if (!evidence) return;
  await mkdir(evidence, {recursive:true});
  await page.screenshot({path:`${evidence}/${name}.png`});
}
try {
  const phone = await viewer({viewport:{width:390,height:844}, deviceScaleFactor:3,
    isMobile:true, hasTouch:true}, 'touch', 'ar');
  const {page, packets} = phone;
  await capture(page, 'phone-ar');
  await page.getByRole('button', {name:'كتابة', exact:true}).click();
  const field = page.locator('.kbinput');
  assert.ok(await field.evaluate(el=>document.activeElement===el),'typing tap must focus synchronously');
  await field.fill('ab😀');
  await page.waitForTimeout(300);
  packets.length = 0;
  await field.press('Backspace');
  await page.waitForTimeout(100);
  assert.equal(input(packets).filter(p => p.type === 'key' && p.key === 'Backspace').length, 1,
    'deleting one emoji must send one Backspace');
  packets.length = 0;
  await page.getByRole('button', {name:'Backspace', exact:true}).click();
  await field.fill('س');
  await page.waitForTimeout(300);
  assert.deepEqual(input(packets).map(p => p.type === 'text' ? ['text',p.value] : [p.type,p.key]),
    [['key','Backspace'], ['text','س']], 'toolbar Backspace resets the phone typing baseline');

  await field.fill('');
  await page.waitForTimeout(100);
  packets.length = 0;
  await field.evaluate(el => {
    el.dispatchEvent(new CompositionEvent('compositionstart', {bubbles:true,data:''}));
    el.value = 'سلام';
    el.dispatchEvent(new InputEvent('input', {bubbles:true,inputType:'insertCompositionText',data:'سلام',isComposing:true}));
    el.dispatchEvent(new KeyboardEvent('keydown', {bubbles:true,cancelable:true,key:'Enter',code:'Enter',isComposing:true}));
  });
  await page.waitForTimeout(300);
  assert.equal(input(packets).length, 0, 'IME confirmation must not submit Enter or incomplete text');
  await field.evaluate(el => el.dispatchEvent(new CompositionEvent('compositionend', {bubbles:true,data:'سلام'})));
  await page.waitForTimeout(300);
  assert.deepEqual(input(packets).map(p => [p.type,p.value]), [['text','سلام']], 'composition commits exactly once');
  // A network break while an IME word is marked preserves it as a local draft.
  await field.fill('');
  await page.waitForTimeout(100);
  packets.length = 0;
  await field.evaluate(el => {
    el.dispatchEvent(new CompositionEvent('compositionstart', {bubbles:true}));
    el.value = 'مسودة';
    el.dispatchEvent(new InputEvent('input', {bubbles:true,isComposing:true,data:'مسودة'}));
  });
  phone.holdHello();
  const socketCount = phone.sockets.length;
  phone.sockets.at(-1).close({code:1011,reason:'isolated network interruption'});
  await page.waitForTimeout(100);
  await field.fill('مسودة جديدة');
  assert.equal(input(packets).length,0,'offline edits stay local until authenticated hello');
  for (let n=0; n<40 && phone.sockets.length<=socketCount; n++) await page.waitForTimeout(100);
  assert.ok(phone.sockets.length>socketCount,'recoverable close reconnects automatically');
  phone.hello(phone.sockets.at(-1));
  await page.waitForTimeout(350);
  assert.deepEqual(input(packets).map(p=>[p.type,p.value]), [['text','مسودة جديدة']],
    'recovery commits the complete interrupted IME draft exactly once');
  await page.getByRole('button', {name:'تم', exact:true}).click();
  await page.locator('.toolbar.fade-toolbar').waitFor({state:'attached',timeout:10_000});

  for (const [width,height] of [[844,390],[390,844],[844,390],[390,844]]) {
    await page.setViewportSize({width,height});
    await page.waitForTimeout(100);
    const boxes = await page.evaluate(() => {
      const a = document.querySelector('.remote-stage').getBoundingClientRect();
      const b = document.querySelector('.toolbar').getBoundingClientRect();
      const canvas = document.querySelector('canvas');
      const data = canvas.getContext('2d').getImageData(canvas.width/2,canvas.height/2,1,1).data;
      return {overlap:Math.max(0,Math.min(a.right,b.right)-Math.max(a.left,b.left))*
        Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)), pixel:[...data]};
    });
    assert.equal(boxes.overlap,0,'phone rotation must keep controller chrome outside the desktop');
    assert.ok(boxes.pixel.some((n,i) => i < 3 && n > 13),'rotation must retain the decoded desktop frame');
  }
  await page.setViewportSize({width:844,height:390});
  await capture(page, 'phone-landscape-ar');

  const desktop = await viewer({viewport:{width:1366,height:900}},'desktop');
  const dp = desktop.page;
  await dp.getByRole('button', {name:'Settings',exact:true}).click();
  await dp.getByRole('dialog').waitFor();
  desktop.packets.length=0;
  await dp.keyboard.press('Tab');
  await dp.keyboard.press('ArrowDown');
  await dp.keyboard.press('Escape');
  await dp.waitForTimeout(100);
  assert.deepEqual(input(desktop.packets),[],'modal navigation must never reach the remote PC');
  await dp.locator('canvas').click({position:{x:500,y:350}});
  desktop.packets.length=0;
  await dp.keyboard.press('ArrowLeft');
  await dp.waitForTimeout(100);
  assert.equal(input(desktop.packets).filter(p=>p.type==='key').length,2,
    'physical keyboard must resume after the modal closes');
  await capture(dp, 'desktop-en');
  const trackpad = await viewer({viewport:{width:390,height:844},deviceScaleFactor:3,
    isMobile:true,hasTouch:true,colorScheme:'dark'}, 'trackpad', 'ar', true);
  await trackpad.page.waitForFunction(() => document.querySelector('.remote-cursor').hidden);
  const cdp = await trackpad.page.context().newCDPSession(trackpad.page);
  const touch = (type,points) => cdp.send('Input.dispatchTouchEvent',{type,touchPoints:points});
  trackpad.packets.length = 0;
  await touch('touchStart',[{x:160,y:400}]);
  await touch('touchMove',[{x:190,y:400}]);
  await touch('touchMove',[{x:220,y:400}]);
  await touch('touchEnd',[]);
  await trackpad.page.waitForTimeout(80);
  assert.ok(trackpad.packets.some(p=>p.type==='moveRelative' && p.dx>0),'trackpad uses real relative motion');
  assert.ok(!trackpad.packets.some(p=>p.type==='move' || p.type==='click'),'trackpad never warps the cursor');
  trackpad.packets.length = 0;
  await touch('touchStart',[{x:160,y:400}]);
  await touch('touchEnd',[]);
  await trackpad.page.waitForTimeout(80);
  assert.equal(trackpad.packets.filter(p=>p.type==='clickCurrent').length,1,'tap clicks the actual host cursor');
  await capture(trackpad.page,'phone-dark-ar');
  await trackpad.page.getByRole('button',{name:'الإعدادات',exact:true}).click();
  await trackpad.page.locator('.sheet').evaluate(async el => {
    await Promise.all(el.getAnimations().map(animation=>animation.finished));
  });
  const headingClear = await trackpad.page.locator('.sheet').evaluate(sheet => {
    const close = sheet.querySelector('.sheet-close').getBoundingClientRect();
    const range = document.createRange(); range.selectNodeContents(sheet.querySelector('h3'));
    const title = range.getBoundingClientRect();
    return close.width >= 44 && close.height >= 44 &&
      (close.right <= title.left || title.right <= close.left || close.bottom <= title.top);
  });
  assert.ok(headingClear, 'Arabic sheet title and 44px close target must not overlap');
  await capture(trackpad.page,'settings-dark-ar');
  await trackpad.page.locator('.sheet-close').click();
  await trackpad.page.getByRole('button',{name:'الشاشة',exact:true}).click();
  await capture(trackpad.page,'display-dark-ar');
  await trackpad.page.locator('.sheet-close').click();

  // Both clipboard directions stay local to this isolated test. Prove that a failed
  // PC clipboard write never sends Ctrl+V with whatever used to be on that PC.
  const cp = trackpad.page;
  await cp.evaluate(() => {
    window.phoneClipboard = 'MoOS العربية 😀';
    Object.defineProperty(navigator, 'clipboard', {configurable:true,value:{
      readText: async () => window.phoneClipboard,
      writeText: async text => { window.phoneClipboard = text; },
    }});
  });
  let pcText = 'من الكمبيوتر 😀';
  let rejectWrite = false;
  await cp.route('**/api/clipboard', async route => {
    if (route.request().method() === 'GET') return route.fulfill({json:{kind:'text',text:pcText}});
    if (rejectWrite) return route.fulfill({status:503,json:{error:'isolated failure'}});
    pcText = route.request().postDataJSON().text;
    return route.fulfill({json:{ok:true}});
  });
  await cp.getByRole('button',{name:'الحافظة',exact:true}).click();
  await cp.locator('textarea[readonly]').filter({visible:true}).waitFor();
  await cp.waitForFunction(() => document.querySelector('textarea[readonly]')?.value === 'من الكمبيوتر 😀');
  await cp.getByRole('button',{name:'نسخ',exact:true}).click();
  assert.equal(await cp.evaluate(() => window.phoneClipboard),pcText,'PC text copies to phone');
  await cp.evaluate(() => { window.phoneClipboard = 'MoOS العربية 😀'; });
  await cp.getByRole('button',{name:'لصق من حافظة الهاتف',exact:true}).click();
  const draft = cp.locator('textarea:not([readonly])');
  assert.equal(await draft.inputValue(),'MoOS العربية 😀','phone clipboard becomes an editable draft');
  trackpad.packets.length = 0;
  await cp.getByRole('button',{name:'إرسال ولصق',exact:true}).click();
  await cp.waitForTimeout(150);
  assert.equal(pcText,'MoOS العربية 😀');
  assert.equal(input(trackpad.packets).filter(p=>p.type==='combo').length,1);
  rejectWrite = true;
  trackpad.packets.length = 0;
  await cp.getByRole('button',{name:'إرسال ولصق',exact:true}).click();
  await cp.waitForTimeout(150);
  assert.deepEqual(input(trackpad.packets),[],'failed clipboard upload must never paste stale PC data');
  await cp.locator('.toast').waitFor({state:'hidden'});
  await capture(cp,'clipboard-dark-ar');

  // Emulate the visual viewport keyboard contract (Chromium headless has no OS
  // keyboard). Verify geometry for suggestion/emoji-panel heights and iOS panning.
  for (const [height,offsetTop] of [[480,0],[370,20],[844,0]]) {
    await cp.evaluate(({height,offsetTop}) => {
      Object.defineProperties(window.visualViewport, {
        height:{configurable:true,value:height}, offsetTop:{configurable:true,value:offsetTop},
      });
      window.visualViewport.dispatchEvent(new Event('resize'));
    },{height,offsetTop});
    const box = await cp.locator('.sheet').boundingBox();
    assert.ok(box.y >= offsetTop && box.y + box.height <= height + offsetTop + 1,
      'clipboard sheet must fit above the phone keyboard');
  }
  await cp.evaluate(() => { navigator.clipboard.readText = async () => { throw new Error('denied'); }; });
  await cp.getByRole('button',{name:'لصق من حافظة الهاتف',exact:true}).click();
  assert.equal(await draft.evaluate(el=>document.activeElement===el),true,'denied clipboard read focuses manual paste');
  assert.equal(await draft.inputValue(),'MoOS العربية 😀','denied read preserves the draft');
  await cp.locator('.sheet-close').click();
  await cp.getByRole('button',{name:'كتابة',exact:true}).click();
  assert.ok(await cp.locator('.kbinput').evaluate(el=>document.activeElement===el));
  for (const [height,offsetTop] of [[480,0],[370,20],[844,0]]) {
    await cp.evaluate(({height,offsetTop}) => {
      Object.defineProperties(window.visualViewport, {
        height:{configurable:true,value:height}, offsetTop:{configurable:true,value:offsetTop},
      });
      window.visualViewport.dispatchEvent(new Event('resize'));
    },{height,offsetTop});
    const box = await cp.locator('.kbbar').boundingBox();
    assert.ok(box.y >= offsetTop && box.y + box.height <= height + offsetTop + 1,
      'typing and shortcuts must remain above the phone keyboard');
  }
  await cp.locator('.toast').waitFor({state:'hidden'});
  await capture(cp,'keyboard-dark-ar');

  const light = await viewer({viewport:{width:360,height:800},deviceScaleFactor:2,
    isMobile:true,hasTouch:true,colorScheme:'light',reducedMotion:'reduce'},'touch','ar');
  await capture(light.page,'phone-light-ar');
  await light.page.getByRole('button',{name:'الإعدادات',exact:true}).click();
  await capture(light.page,'settings-light-ar');
  assert.equal(await light.page.locator('.sheet').evaluate(el=>getComputedStyle(el).animationName),'none');
  assert.deepEqual(errors, [], 'browser must have no uncaught application errors');
  console.log('PASS: real Chromium phone Unicode/IME/shortcuts, rotation geometry, frame continuity and desktop modal input isolation');
} finally {
  for (const context of contexts) await context.close();
  await browser.close();
}
