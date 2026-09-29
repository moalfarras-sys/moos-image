/* Mira Companion — Mira on the owner's phone.
 *
 * Everything this page shows comes from Mira's computer over one event stream (/api/events):
 * her phase, live caption, conversation with verified action cards, and the Home devices'
 * read-back state. A request from here only ever means "sent": success appears when Mira's own
 * report arrives, never on the page's say-so. No external resources; all text goes in through
 * textContent. */
'use strict';

(() => {
  const ACTIVE = ['listening', 'thinking', 'speaking', 'executing'];
  const SVG = 'http://www.w3.org/2000/svg';
  // Mira's own line icons (qml/Mira/icons.js), 24×24, stroke only.
  const ICONS = {
    mic: 'M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z M5.5 11a6.5 6.5 0 0 0 13 0 M12 17.5V21 M8.5 21h7',
    stop: 'M8 7h8a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z',
    send: 'M12 19V5 M6 11l6-6 6 6',
    home: 'M3.5 11L12 4l8.5 7 M5.5 9.5V20h13V9.5 M10 20v-5.5h4V20',
    chat: 'M5 4.5h14a2 2 0 0 1 2 2V15a2 2 0 0 1-2 2h-7l-5 4v-4H5a2 2 0 0 1-2-2V6.5a2 2 0 0 1 2-2z',
    bulb: 'M9.5 18h5 M10.5 21h3 M12 3a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.3 1.1 2.1v.1h5v-.1c0-.8.4-1.5 1.1-2.1A6 6 0 0 0 12 3z',
    tv: 'M3.5 7.5h17v11h-17z M8 3.5l4 4 4-4',
    power: 'M12 3.5v8 M6.6 6.6a7.5 7.5 0 1 0 10.8 0',
    sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M12 2.5v2 M12 19.5v2 M2.5 12h2 M19.5 12h2 M5.3 5.3l1.4 1.4 M17.3 17.3l1.4 1.4 M5.3 18.7l1.4-1.4 M17.3 6.7l1.4-1.4',
    moon: 'M19.5 14.5A8 8 0 1 1 9.5 4.5a6.5 6.5 0 0 0 10 10z',
    cloud: 'M7 18.5h10a4 4 0 0 0 .4-8A6 6 0 0 0 5.8 10a4.3 4.3 0 0 0 1.2 8.5z',
    check: 'M5 12.5l4.5 4.5L19 7.5',
    clock: 'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z M12 7.5V12l3 2',
    alert: 'M12 9v4 M12 16.5v.3 M10.3 4.2L2.8 17.3a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0z',
    refresh: 'M19.5 11.5a7.5 7.5 0 1 0-2.2 5.3 M19.5 4.5v7h-7',
    play: 'M8 5.5v13l10.5-6.5z',
    pause: 'M8.5 5.5v13 M15.5 5.5v13',
    volume: 'M4 9.5h3.5L12 5.5v13l-4.5-4H4z M15.5 9a4 4 0 0 1 0 6 M18.3 6.5a8 8 0 0 1 0 11',
    sparkle: 'M12 3.5l1.7 5 5 1.8-5 1.7-1.7 5-1.8-5-5-1.7 5-1.8z M18.5 16l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z',
    x: 'M6.5 6.5l11 11 M17.5 6.5l-11 11',
    shield: 'M12 3.5l7.5 3v5.5c0 4.5-3.1 7.5-7.5 9-4.4-1.5-7.5-4.5-7.5-9V6.5z M9 12l2 2 4-4',
    lock: 'M7.5 10.5V8a4.5 4.5 0 0 1 9 0v2.5 M5.5 10.5h13v10h-13z M12 14.5v2.5',
  };
  const TEXT = {
    ar: {
      title: 'ميرا', tab_mira: 'ميرا', tab_home: 'البيت',
      talk: 'تحدّث', stop: 'إيقاف', send: 'إرسال', placeholder: 'اكتب لميرا…',
      face_label: 'وجه ميرا · المس لتتحدث',
      phase_idle: 'جاهزة', phase_listening: 'أسمعك…', phase_thinking: 'أفكّر…', phase_speaking: 'ميرا تتحدث',
      phase_executing: 'أنفّذ وأتحقق…', phase_error: 'حدث خطأ', phase_offline: 'الصوت متوقف',
      you: 'أنت', mira: 'ميرا', action: 'تم التحقق', pending: 'لم يتأكد', failed: 'تعذّر', noted: 'سجل',
      empty_chat_title: 'ابدأ معي', empty_chat_body: 'تكلّم أو اكتب. كل أمر أنفّذه يظهر هنا مع نتيجته الحقيقية.',
      svc_echo: 'Echo', svc_home: 'البيت',
      conn_connecting: 'أتصل بكمبيوتر ميرا…', conn_lost: 'انقطع الاتصال بكمبيوتر ميرا',
      conn_retry_in: 'إعادة المحاولة خلال {s} ث', conn_offline: 'الهاتف غير متصل بالشبكة', retry: 'أعد الآن',
      not_sent: 'لم يُرسل · تحقّق من الاتصال', slow_down: 'طلبات كثيرة · انتظر قليلاً ثم أعد',
      too_long: 'الرسالة طويلة جداً (الحد 2000 حرف)',
      err_unknown_device: 'هذا الجهاز لم يعد في البيت', err_unavailable: 'الجهاز غير متاح الآن',
      err_unsupported: 'هذا الجهاز لا يدعم هذا التحكم', err_generic: 'تعذّر إرسال الطلب',
      devices_available: 'أجهزة متاحة', lights: 'الأضواء', lights_on_of: 'مضاءة',
      all_on: 'تشغيل الكل', all_off: 'إطفاء الكل', refresh: 'تحديث',
      checking: 'أتحقق من النتيجة على الجهاز…',
      no_devices: 'لا تظهر أجهزة بعد. تأكد أن Home Assistant يعمل وأن الربط محفوظ على الكمبيوتر.',
      state_on: 'يعمل', state_off: 'مطفأ', state_playing: 'يعرض', state_paused: 'متوقف مؤقتاً', state_idle: 'خامل',
      unavailable: 'غير متاح', group: 'مجموعة',
      brightness: 'السطوع', color: 'اللون', volume: 'الصوت', play: 'تشغيل', pause: 'إيقاف مؤقت',
      pair_title: 'اربط هاتفك بميرا', pair_body: 'هذا الهاتف غير مقترن بعد.',
      pair_rotated_title: 'تغيّر رمز الإقران', pair_rotated_body: 'غُيّر رمز الإقران على الكمبيوتر، ففُصل هذا الهاتف.',
      pair_invalid_title: 'رابط الإقران لم يعد صالحاً', pair_invalid_body: 'ربما غُيّر الرمز على الكمبيوتر.',
      pair_steps: ['على الكمبيوتر افتح ميرا ← الإعدادات ← الهاتف.', 'اضغط «إظهار رمز الإقران».',
                   'امسح الرمز بكاميرا الـ iPhone وافتح الرابط في Safari.'],
      pair_note: 'تعمل ميرا على هاتفك عبر شبكة Tailscale الخاصة بك فقط.',
      pair_retry: 'أعد المحاولة',
      act_waiting: 'بانتظار موافقتك:', act_approve: 'موافقة', act_reject: 'إلغاء',
      act_password: 'سيطلب النظام كلمة المرور على الكمبيوتر', act_running: 'يعمل الآن…',
      act_expired: 'انتهت مهلة الموافقة؛ لم يُنفَّذ شيء', act_cancelled: 'ألغيت', act_change: 'تغيير في النظام',
      colors: { pink: 'وردي', purple: 'بنفسجي', blue: 'أزرق', green: 'أخضر', yellow: 'أصفر', orange: 'برتقالي', red: 'أحمر' },
    },
    en: {
      title: 'Mira', tab_mira: 'Mira', tab_home: 'Home',
      talk: 'Talk', stop: 'Stop', send: 'Send', placeholder: 'Message Mira…',
      face_label: 'Mira’s face · tap to talk',
      phase_idle: 'Ready', phase_listening: 'Listening…', phase_thinking: 'Thinking…', phase_speaking: 'Mira is speaking',
      phase_executing: 'Working on it…', phase_error: 'Something went wrong', phase_offline: 'Voice is off',
      you: 'You', mira: 'Mira', action: 'Verified', pending: 'Unverified', failed: 'Failed', noted: 'Noted',
      empty_chat_title: 'Start with me', empty_chat_body: 'Talk or type. Every action I take shows up here with its real result.',
      svc_echo: 'Echo', svc_home: 'Home',
      conn_connecting: 'Connecting to Mira’s computer…', conn_lost: 'Lost the connection to Mira’s computer',
      conn_retry_in: 'retrying in {s} s', conn_offline: 'This phone is offline', retry: 'Retry',
      not_sent: 'Not sent · check the connection', slow_down: 'Too many requests · wait a moment and try again',
      too_long: 'That message is too long (2000 characters max)',
      err_unknown_device: 'That device is no longer in your home', err_unavailable: 'That device is unavailable right now',
      err_unsupported: 'That device does not support this control', err_generic: 'The request could not be sent',
      devices_available: 'devices available', lights: 'Lights', lights_on_of: 'on',
      all_on: 'All on', all_off: 'All off', refresh: 'Refresh',
      checking: 'Checking the result on the device…',
      no_devices: 'No devices yet. Make sure Home Assistant is running and linked on the computer.',
      state_on: 'On', state_off: 'Off', state_playing: 'Playing', state_paused: 'Paused', state_idle: 'Idle',
      unavailable: 'Unavailable', group: 'group',
      brightness: 'Brightness', color: 'Color', volume: 'Volume', play: 'Play', pause: 'Pause',
      pair_title: 'Pair your phone with Mira', pair_body: 'This phone is not paired yet.',
      pair_rotated_title: 'The pairing code changed', pair_rotated_body: 'The code was changed on the computer, so this phone was signed out.',
      pair_invalid_title: 'This pairing link is no longer valid', pair_invalid_body: 'The code may have been changed on the computer.',
      pair_steps: ['On the computer, open Mira → Settings → Phone.', 'Press “Show pairing code”.',
                   'Scan it with the iPhone camera and open the link in Safari.'],
      pair_note: 'Mira works on your phone only over your own Tailscale network.',
      pair_retry: 'Try again',
      act_waiting: 'Waiting for your approval:', act_approve: 'Approve', act_reject: 'Cancel',
      act_password: 'The computer will ask for your password', act_running: 'Running…',
      act_expired: 'Approval timed out; nothing ran', act_cancelled: 'Cancelled', act_change: 'System change',
      colors: { pink: 'Pink', purple: 'Purple', blue: 'Blue', green: 'Green', yellow: 'Yellow', orange: 'Orange', red: 'Red' },
    },
  };
  // The desktop's words win for these keys, so the phone says exactly what Mira's window says.
  const SHARED = new Set(['talk', 'stop', 'send', 'you', 'mira', 'action', 'pending', 'failed', 'empty_chat_title',
    'empty_chat_body', 'phase_idle', 'phase_listening', 'phase_thinking', 'phase_speaking', 'phase_executing',
    'phase_error', 'phase_offline', 'all_on', 'all_off', 'refresh', 'checking', 'no_devices', 'state_on', 'state_off',
    'state_playing', 'state_paused', 'state_idle', 'unavailable', 'brightness', 'color', 'volume', 'play', 'pause',
    'devices_available', 'lights', 'lights_on_of', 'svc_echo', 'svc_home', 'act_waiting', 'act_approve', 'act_reject',
    'act_running', 'act_expired', 'act_cancelled', 'act_change']);
  const PHASE_COLORS = {       // Theme.phaseColor / phaseColor2
    idle: ['#FF6FB5', '#9B7BFF'], listening: ['#3DF2C4', '#35D8F4'], thinking: ['#9B7BFF', '#5B8CFF'],
    speaking: ['#FF6FB5', '#9B7BFF'], executing: ['#FFC46B', '#FF6FB5'], error: ['#FF5C7A', '#7A1E3A'],
    offline: ['#6B7390', '#2A3050'],
  };

  const $ = (id) => document.getElementById(id);
  const el = {
    app: $('app'), avatar: $('avatar'), title: $('title'), services: $('services'), tabs: $('tabs'),
    tabMira: $('tab-mira'), tabHome: $('tab-home'), viewMira: $('view-mira'), viewHome: $('view-home'),
    banner: $('banner'), bannerText: $('banner-text'), bannerRetry: $('banner-retry'), toasts: $('toasts'),
    core: $('core'), ring: $('ring'), faceA: $('face-a'), faceB: $('face-b'), phaseLabel: $('phase-label'),
    caption: $('caption'), chat: $('chat'), chatEmpty: $('chat-empty'), chatEmptyTitle: $('chat-empty-title'),
    chatEmptyBody: $('chat-empty-body'), devicesCount: $('devices-count'), chipWeather: $('chip-weather'),
    allOn: $('all-on'), allOff: $('all-off'), refresh: $('refresh'), homeMessage: $('home-message'),
    homeEmpty: $('home-empty'), devices: $('devices'), dock: $('dock'), talk: $('talk'), talkIcon: $('talk-icon'),
    talkLabel: $('talk-label'), field: $('field'), send: $('send'), pairing: $('pairing'), pairTitle: $('pair-title'),
    pairBody: $('pair-body'), pairSteps: $('pair-steps'), pairNote: $('pair-note'), pairRetry: $('pair-retry'),
    actions: $('actions'),
  };
  const motionQuery = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  const reducedMotion = () => !!(motionQuery && motionQuery.matches);

  const store = {
    get(key) { try { return window.localStorage.getItem(key); } catch (_) { return null; } },
    set(key, value) { try { window.localStorage.setItem(key, value); } catch (_) { /* private mode */ } },
  };

  const state = {
    lang: store.get('mira.lang') || ((navigator.language || '').toLowerCase().startsWith('ar') ? 'ar' : 'en'),
    s: {}, phase: 'idle', level: 0, status: '', caption: '', captionRole: '', mood: 'neutral', face: 'rose',
    services: {}, weather: {}, home: {}, echo: {}, busy: false, devices: [], palette: [], faceFormat: 'png',
    conn: 'connecting', paired: false, view: 'mira', sending: false, pending: new Map(), byeReason: '',
  };
  if (state.lang !== 'ar' && state.lang !== 'en') state.lang = 'ar';

  // ── helpers ────────────────────────────────────────────────────────────────────
  function t(key) {
    if (SHARED.has(key) && typeof state.s[key] === 'string' && state.s[key]) return state.s[key];
    const table = TEXT[state.lang] || TEXT.ar;
    return key in table ? table[key] : (TEXT.en[key] !== undefined ? TEXT.en[key] : key);
  }
  function fmt(text, vars) { return String(text).replace(/\{(\w+)\}/g, (_, k) => (k in vars ? vars[k] : '')); }
  function icon(name, filled) {
    const svg = document.createElementNS(SVG, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    svg.setAttribute('class', 'icon' + (filled ? ' filled' : ''));
    const path = document.createElementNS(SVG, 'path');
    path.setAttribute('d', ICONS[name] || ICONS.sparkle);
    svg.appendChild(path);
    return svg;
  }
  function node(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function setIcon(host, name, filled) {
    const current = host.firstElementChild;
    if (current && current.dataset.icon === name && current.classList.contains('filled') === !!filled) return;
    const svg = icon(name, filled);
    svg.dataset.icon = name;
    host.replaceChildren(svg);
  }
  const live = () => state.conn === 'live';
  const active = () => ACTIVE.includes(state.phase);

  // ── requests ───────────────────────────────────────────────────────────────────
  async function post(path, body) {
    if (!live()) { toast('error', t('not_sent')); return false; }
    let response;
    try {
      response = await fetch(path, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (_) {
      toast('error', t('not_sent'));
      return false;
    }
    if (response.status === 202) return true;
    if (response.status === 401) { showPairing('unpaired'); return false; }
    if (response.status === 429) { toast('pending', t('slow_down')); return false; }
    let code = '';
    try { code = (await response.json()).error || ''; } catch (_) { /* not JSON */ }
    const message = TEXT[state.lang]['err_' + code];
    toast('error', message || t('err_generic'));
    return false;
  }

  // ── connection: one event stream, rebuilt with backoff ─────────────────────────
  const conn = { source: null, attempt: 0, timer: 0, tick: 0, retryAt: 0 };

  function connect() {
    clearTimeout(conn.timer);
    clearInterval(conn.tick);
    if (conn.source) conn.source.close();
    setConn('connecting');
    const source = new EventSource('/api/events');
    conn.source = source;
    const on = (name, fn) => source.addEventListener(name, (event) => {
      if (conn.source !== source) return;
      let data;
      try { data = JSON.parse(event.data); } catch (_) { return; }
      fn(data);
    });
    on('snapshot', (data) => { conn.attempt = 0; onSnapshot(data); });
    on('state', onState);
    on('level', (data) => { state.level = Number(data.level) || 0; ring.kick(); });
    on('chat', (row) => chat.add(row, true));
    on('chat_update', (row) => chat.update(row));
    on('chat_reset', (data) => chat.reset(data.rows || []));
    on('devices', (data) => { state.devices = Array.isArray(data.devices) ? data.devices : []; renderHome(); settlePending(); });
    on('toast', (data) => toast(data.kind, data.text));
    on('bye', (data) => { state.byeReason = data.reason || ''; });
    source.onerror = () => {
      if (conn.source !== source) return;
      source.close();
      conn.source = null;
      probe();
    };
  }

  async function probe() {
    // An event stream cannot say why it failed; one plain request can.
    try {
      const response = await fetch('/api/state', { credentials: 'same-origin', cache: 'no-store' });
      if (response.status === 401) {
        showPairing(state.byeReason === 'rotated' ? 'rotated' : 'unpaired');
        return;
      }
    } catch (_) { /* unreachable: retry below */ }
    retryLater();
  }

  function retryLater() {
    conn.attempt += 1;
    const steps = [1, 2, 3, 5, 8, 13, 20, 30];
    const base = steps[Math.min(conn.attempt - 1, steps.length - 1)];
    const wait = base * (0.85 + Math.random() * 0.3);
    conn.retryAt = Date.now() + wait * 1000;
    setConn('lost');
    conn.timer = setTimeout(connect, wait * 1000);
    conn.tick = setInterval(renderBanner, 1000);
  }

  function setConn(value) {
    state.conn = value;
    el.app.dataset.conn = value;
    renderBanner();
    renderCaption();
    renderServices();
    renderDock();
    renderHome();
  }

  function renderBanner() {
    // Before the first answer the caption says "connecting"; the banner is for a lost connection.
    const show = state.conn === 'lost' || (state.paired && state.conn === 'connecting');
    el.banner.hidden = !show;
    if (!show) { clearInterval(conn.tick); return; }
    let text;
    if (navigator.onLine === false) text = t('conn_offline');
    else if (state.conn === 'lost') {
      const seconds = Math.max(0, Math.ceil((conn.retryAt - Date.now()) / 1000));
      text = t('conn_lost') + ' · ' + fmt(t('conn_retry_in'), { s: seconds });
    } else text = t('conn_connecting');
    el.bannerText.textContent = text;
    el.bannerRetry.textContent = t('retry');
    el.bannerRetry.hidden = state.conn !== 'lost';
  }

  function showPairing(kind) {
    clearTimeout(conn.timer);
    clearInterval(conn.tick);
    if (conn.source) { conn.source.close(); conn.source = null; }
    state.paired = false;
    state.conn = 'unpaired';
    el.app.dataset.conn = 'unpaired';
    el.banner.hidden = true;
    const titles = { rotated: 'pair_rotated_title', invalid: 'pair_invalid_title' };
    const bodies = { rotated: 'pair_rotated_body', invalid: 'pair_invalid_body' };
    el.pairTitle.textContent = t(titles[kind] || 'pair_title');
    el.pairBody.textContent = t(bodies[kind] || 'pair_body');
    el.pairSteps.replaceChildren(...t('pair_steps').map((step) => node('li', '', step)));
    el.pairNote.textContent = t('pair_note');
    el.pairRetry.textContent = t('pair_retry');
    el.pairing.hidden = false;
    ring.stop();
  }

  // ── state from Mira ────────────────────────────────────────────────────────────
  function onSnapshot(snap) {
    state.paired = true;
    state.actions = [];
    state.byeReason = '';
    el.pairing.hidden = true;
    state.devices = Array.isArray(snap.devices) ? snap.devices : [];
    state.palette = Array.isArray(snap.palette) ? snap.palette : [];
    state.faceFormat = snap.faceFormat === 'webp' ? 'webp' : 'png';
    applyState(snap);
    chat.reset(Array.isArray(snap.chat) ? snap.chat : []);
    setConn('live');
    renderAll();
    settlePending(true);
    face.preload();
  }

  function onState(patch) {
    applyState(patch);
    if ('lang' in patch || 's' in patch) { renderAll(); return; }
    if ('phase' in patch || 'mood' in patch || 'faceStyle' in patch) { renderPhase(); updateFace(); }
    if ('faceStyle' in patch) face.preload();
    if ('status' in patch || 'caption' in patch || 'captionRole' in patch) renderCaption();
    if ('services' in patch || 'echo' in patch) { renderServices(); renderDock(); }
    if ('home' in patch || 'weather' in patch) { renderHome(); if ('home' in patch) settlePending(); }
    if ('actions' in patch) renderActions();
  }

  function applyState(data) {
    const fields = { phase: 'phase', status: 'status', caption: 'caption', captionRole: 'captionRole', mood: 'mood',
      faceStyle: 'face', lang: 'lang', services: 'services', weather: 'weather', home: 'home', echo: 'echo', busy: 'busy' };
    for (const [key, target] of Object.entries(fields)) if (key in data && data[key] !== null) state[target] = data[key];
    if (data.s && typeof data.s === 'object') state.s = data.s;
    if (typeof data.level === 'number') state.level = data.level;
    if (Array.isArray(data.actions)) state.actions = data.actions;
    if (state.lang !== 'ar' && state.lang !== 'en') state.lang = 'ar';
    if (!PHASE_COLORS[state.phase]) state.phase = 'idle';
    store.set('mira.lang', state.lang);
  }

  // ── rendering ──────────────────────────────────────────────────────────────────
  function renderAll() {
    const root = document.documentElement;
    root.lang = state.lang;
    root.dir = state.lang === 'ar' ? 'rtl' : 'ltr';
    document.title = state.lang === 'ar' ? 'ميرا · Mira' : 'Mira · ميرا';
    el.title.textContent = t('title');
    el.tabMira.replaceChildren(icon('chat'), node('span', '', t('tab_mira')));
    el.tabHome.replaceChildren(icon('home'), node('span', '', t('tab_home')));
    el.core.setAttribute('aria-label', t('face_label'));
    el.field.placeholder = t('placeholder');
    el.field.setAttribute('aria-label', t('placeholder'));
    el.send.setAttribute('aria-label', t('send'));
    setIcon(el.send, 'send');
    setIcon(el.refresh, 'refresh');
    el.refresh.setAttribute('aria-label', t('refresh'));
    el.allOn.replaceChildren(icon('sun'), node('span', '', t('all_on')));
    el.allOff.replaceChildren(icon('moon'), node('span', '', t('all_off')));
    el.chatEmptyTitle.textContent = t('empty_chat_title');
    el.chatEmptyBody.textContent = t('empty_chat_body');
    chat.relabel();
    renderPhase();
    renderCaption();
    renderServices();
    renderDock();
    renderHome(true);
    renderBanner();
    renderActions();
    updateFace();
    fitViewport();
  }

  // System changes waiting for the owner, and what came of them: the desktop's own cards.
  function renderActions() {
    const list = (state.actions || []).filter((a) => a && typeof a.aid === 'string');
    el.actions.hidden = list.length === 0;
    el.actions.replaceChildren();
    for (const a of list.slice(0, 3)) {
      const card = node('div', 'act');
      card.dataset.stage = String(a.stage || '');
      const glyph = a.stage === 'ask' ? (a.category === 'privileged_confirm' ? 'lock' : 'shield')
        : a.stage === 'ok' ? 'check' : a.stage === 'running' ? 'clock' : 'alert';
      const head = node('div', 'act-head');
      head.append(icon(glyph), node('strong', 'act-title', String(a.title || '')));
      card.append(head);
      const line = a.stage === 'ask' ? String(a.detail || '') : String(a.summary || '');
      if (line) card.append(node('p', 'act-line', line));
      if (a.stage === 'ask') {
        if (a.category === 'privileged_confirm') card.append(node('p', 'act-note', t('act_password')));
        const row = node('div', 'act-buttons');
        const no = node('button', 'pill', ''); no.type = 'button';
        no.replaceChildren(icon('x'), node('span', '', t('act_reject')));
        const yes = node('button', 'pill primary', ''); yes.type = 'button';
        yes.replaceChildren(icon('check'), node('span', '', t('act_approve')));
        no.addEventListener('click', () => answerAction(a.aid, 'reject', card));
        yes.addEventListener('click', () => answerAction(a.aid, 'approve', card));
        row.append(no, yes);
        card.append(row);
      }
      el.actions.append(card);
    }
  }

  function answerAction(aid, answer, card) {
    card.querySelectorAll('button').forEach((b) => { b.disabled = true; });
    post('/api/action', { aid, answer }).then((ok) => {
      if (!ok) card.querySelectorAll('button').forEach((b) => { b.disabled = false; });
    });
  }

  function renderPhase() {
    el.app.dataset.phase = state.phase;
    el.app.dataset.face = state.face === 'holo' ? 'holo' : 'rose';
    el.phaseLabel.textContent = t('phase_' + state.phase) || t('phase_idle');
    ring.setPhase(state.phase, state.face);
    renderDock();
  }

  function renderCaption() {
    const text = !state.paired ? (state.conn === 'unpaired' ? '' : t('conn_connecting')) : (state.caption || state.status || '');
    el.caption.textContent = text;
    el.caption.dataset.role = state.caption ? (state.captionRole || '') : '';
  }

  function renderServices() {
    const services = state.services || {};
    const items = [['echo', t('svc_echo')], ['home', t('svc_home')]];
    el.services.replaceChildren(...items.map(([key, label]) => {
      const item = node('span', 'svc');
      item.dataset.state = live() ? (services[key] || 'connecting') : 'unknown';
      item.append(node('i'), node('span', '', label));
      return item;
    }));
  }

  function renderDock() {
    const isActive = active();
    el.talk.classList.toggle('active', isActive);
    const echo = state.echo || {};
    el.talk.classList.toggle('dim', !isActive && (echo.online !== true || echo.voice_enabled === false));
    el.talkLabel.textContent = isActive ? t('stop') : t('talk');
    el.talk.setAttribute('aria-label', isActive ? t('stop') : t('talk'));
    setIcon(el.talkIcon, isActive ? 'stop' : 'mic', isActive);
    el.talk.disabled = !live();
    const ready = el.field.value.trim() !== '';
    el.send.classList.toggle('ready', ready && live());
    el.send.classList.toggle('busy', state.sending);
    el.send.disabled = !live() || state.sending;
  }

  // ── conversation ───────────────────────────────────────────────────────────────
  const chat = {
    maxSeq: 0,
    stick: true,          // the reader is at the newest message; keep them there as things resize
    reset(rows) {
      for (const item of [...el.chat.querySelectorAll('.msg')]) item.remove();
      this.maxSeq = 0;
      for (const row of rows) this.add(row, false);
      this.empty();
      this.scroll(true);
    },
    add(row, animate) {
      const seq = Number(row.seq) || 0;
      if (seq && seq <= this.maxSeq) { this.update(row); return; }
      const nearBottom = this.stick || this.nearBottom();
      const item = this.render(row);
      if (!animate) item.style.animation = 'none';
      el.chat.appendChild(item);
      this.maxSeq = Math.max(this.maxSeq, seq);
      const all = el.chat.querySelectorAll('.msg');
      for (let i = 0; i < all.length - 150; i += 1) all[i].remove();
      this.empty();
      if (nearBottom || row.role === 'user') this.scroll(!animate);
    },
    update(row) {
      const old = el.chat.querySelector(`.msg[data-seq="${Number(row.seq) || 0}"]`);
      if (!old) return;
      const fresh = this.render(row);
      fresh.style.animation = 'none';
      old.replaceWith(fresh);
    },
    render(row) {
      const role = String(row.role || 'mira');
      const card = role === 'action' || role === 'error';
      const item = node('div', 'msg ' + (card ? 'card' : role === 'user' ? 'user' : 'mira'));
      item.dataset.seq = String(Number(row.seq) || 0);
      item.dataset.role = role;
      item.dataset.time = String(row.time || '');
      if (card) {
        let status = role === 'error' ? 'error' : String(row.status || '');
        if (!['ok', 'pending', 'partial', 'error'].includes(status)) status = 'unknown';
        item.dataset.status = status;
        const body = node('div', 'card-body');
        const badge = node('span', 'card-badge');
        badge.appendChild(icon(status === 'ok' ? 'check' : status === 'pending' || status === 'partial' ? 'clock'
          : status === 'unknown' ? 'sparkle' : 'alert'));
        badge.setAttribute('role', 'img');
        badge.setAttribute('aria-label', status === 'ok' ? t('action') : status === 'error' ? t('failed')
          : status === 'unknown' ? t('noted') : t('pending'));
        const text = node('p', 'card-text', String(row.text || ''));
        text.dir = 'auto';
        body.append(badge, text, node('span', 'card-time', String(row.time || '')));
        item.appendChild(body);
      } else {
        const bubble = node('div', 'bubble');
        const text = node('p', 'text', String(row.text || ''));
        text.dir = 'auto';
        const meta = node('span', 'meta', (role === 'user' ? t('you') : t('mira')) + ' · ' + String(row.time || ''));
        bubble.append(text, meta);
        item.appendChild(bubble);
      }
      return item;
    },
    relabel() {
      for (const meta of el.chat.querySelectorAll('.msg .meta')) {
        const item = meta.closest('.msg');
        meta.textContent = (item.dataset.role === 'user' ? t('you') : t('mira')) + ' · ' + item.dataset.time;
      }
    },
    empty() { el.chatEmpty.hidden = !!el.chat.querySelector('.msg'); },
    nearBottom() { return el.chat.scrollHeight - el.chat.scrollTop - el.chat.clientHeight < 90; },
    scroll(instant) {
      this.stick = true;
      requestAnimationFrame(() => {
        el.chat.scrollTo({ top: el.chat.scrollHeight, behavior: instant || reducedMotion() ? 'auto' : 'smooth' });
      });
    },
  };
  el.chat.addEventListener('scroll', () => { chat.stick = chat.nearBottom(); }, { passive: true });
  if (window.ResizeObserver) {
    // The stage grows while captions stream in; the conversation keeps its newest line in view.
    new ResizeObserver(() => { if (chat.stick) el.chat.scrollTop = el.chat.scrollHeight; }).observe(el.chat);
  }

  // ── home ───────────────────────────────────────────────────────────────────────
  const cards = new Map();

  function renderHome(relabel) {
    const home = state.home || {};
    el.devicesCount.textContent = `${home.available || 0} / ${home.total || 0} ${t('devices_available')}`;
    const weather = state.weather || {};
    if (weather.ok) {
      el.chipWeather.hidden = false;
      el.chipWeather.replaceChildren(icon('cloud'), node('span', '', [weather.city, `${weather.temp}°`, weather.condition]
        .filter((part) => part !== undefined && part !== null && part !== '').join(' · ')));
    } else el.chipWeather.hidden = true;
    const lightsBlocked = !live() || !(home.lights_available > 0) || home.busy === true;
    el.allOn.disabled = lightsBlocked;
    el.allOff.disabled = lightsBlocked;
    el.refresh.disabled = !live();
    el.homeMessage.textContent = home.busy ? t('checking') : (home.message || '');
    el.homeMessage.classList.toggle('busy', home.busy === true);
    el.homeEmpty.textContent = t('no_devices');
    el.homeEmpty.hidden = state.devices.length > 0;
    const seen = new Set();
    let previous = null;
    for (const device of state.devices) {
      const id = String(device.entity_id || '');
      if (!id) continue;
      seen.add(id);
      let card = cards.get(id);
      if (!card || relabel) {
        const fresh = buildCard(id);
        if (card) card.root.replaceWith(fresh.root);
        card = fresh;
        cards.set(id, card);
      }
      updateCard(card, device);
      const anchor = previous ? previous.nextSibling : el.devices.firstChild;
      if (anchor !== card.root) el.devices.insertBefore(card.root, anchor);
      previous = card.root;
    }
    for (const [id, card] of cards) if (!seen.has(id)) { card.root.remove(); cards.delete(id); }
  }

  function deviceById(id) { return state.devices.find((d) => d.entity_id === id); }

  function act(id, action, extra) {
    const device = deviceById(id);
    if (!device || !device.available || (state.home || {}).busy) return;
    state.pending.set(id, Date.now());
    const card = cards.get(id);
    if (card) card.root.classList.add('pending');
    post('/api/home/action', Object.assign({ entity_id: id, action }, extra || {})).then((ok) => {
      if (!ok) { state.pending.delete(id); if (card) card.root.classList.remove('pending'); }
    });
  }

  function settlePending(all) {
    const home = state.home || {};
    const now = Date.now();
    for (const [id, since] of state.pending) {
      if (all || (!home.busy && now - since > 400) || now - since > 20000) {
        state.pending.delete(id);
        const card = cards.get(id);
        if (card) card.root.classList.remove('pending');
      }
    }
  }

  function buildCard(id) {
    const root = node('article', 'device');
    const head = node('div', 'device-head');
    const iconBox = node('div', 'device-icon');
    const titles = node('div', 'device-titles');
    const name = node('div', 'device-name');
    const status = node('div', 'device-state');
    titles.append(name, status);
    const toggle = node('button', 'switch');
    toggle.type = 'button';
    toggle.setAttribute('role', 'switch');
    toggle.addEventListener('click', () => {
      const d = deviceById(id);
      if (d) act(id, d.is_on ? 'turn_off' : 'turn_on');
    });
    head.append(iconBox, titles, toggle);

    const brightRow = node('div', 'control-row');
    const bright = rangeInput(1, 100, t('brightness'));
    const brightValue = node('span', 'value');
    brightRow.append(icon('sun'), bright, brightValue);
    bright.addEventListener('input', () => { brightValue.textContent = bright.value + '%'; paintRange(bright); });
    bright.addEventListener('change', () => act(id, 'brightness', { value: Number(bright.value) }));

    const swatches = node('div', 'swatches');
    const swatchButtons = state.palette.map((entry) => {
      const button = node('button', 'swatch');
      button.type = 'button';
      button.style.setProperty('--sw', entry.color);
      button.setAttribute('aria-label', (TEXT[state.lang].colors || {})[entry.name] || entry.name);
      button.appendChild(node('i'));
      button.addEventListener('click', () => act(id, 'color', { color: entry.name }));
      swatches.appendChild(button);
      return { button, entry };
    });

    const media = node('div', 'media');
    const play = node('button', 'round');
    play.type = 'button';
    play.setAttribute('aria-label', t('play'));
    play.appendChild(icon('play'));
    play.addEventListener('click', () => act(id, 'media_play'));
    const pause = node('button', 'round');
    pause.type = 'button';
    pause.setAttribute('aria-label', t('pause'));
    pause.appendChild(icon('pause'));
    pause.addEventListener('click', () => act(id, 'media_pause'));
    const volIcon = icon('volume');
    const volume = rangeInput(0, 100, t('volume'));
    const volumeValue = node('span', 'value');
    volume.addEventListener('input', () => { volumeValue.textContent = volume.value + '%'; paintRange(volume); });
    volume.addEventListener('change', () => act(id, 'volume', { value: Number(volume.value) }));
    media.append(play, pause, volIcon, volume, volumeValue);

    root.append(head, brightRow, swatches, media);
    return { root, iconBox, name, status, toggle, brightRow, bright, brightValue, swatches, swatchButtons, media, play,
      pause, volIcon, volume, volumeValue };
  }

  function rangeInput(min, max, label) {
    const input = node('input', 'range');
    input.type = 'range';
    input.min = String(min);
    input.max = String(max);
    input.step = '1';
    input.setAttribute('aria-label', label);
    const hold = () => { input.dataset.dragging = '1'; };
    const release = () => { delete input.dataset.dragging; };
    input.addEventListener('pointerdown', hold);
    input.addEventListener('touchstart', hold, { passive: true });
    input.addEventListener('pointerup', release);
    input.addEventListener('touchend', release);
    input.addEventListener('blur', release);
    return input;
  }

  function paintRange(input) {
    const min = Number(input.min), max = Number(input.max);
    const fill = ((Number(input.value) - min) / Math.max(1, max - min)) * 100;
    input.style.setProperty('--fill', fill.toFixed(1) + '%');
  }

  function setRange(input, value) {
    if (input.dataset.dragging || document.activeElement === input) return;
    input.value = String(value);
    paintRange(input);
  }

  function rgbOf(hex) {
    const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(String(hex || ''));
    return m ? [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)] : null;
  }

  function updateCard(card, d) {
    const busy = (state.home || {}).busy === true;
    const usable = live() && d.available && !busy;
    const accent = d.domain === 'media_player' ? '#35D8F4' : (d.rgb && d.is_on ? d.rgb : '#FFC46B');
    card.root.style.setProperty('--accent', accent);
    card.root.classList.toggle('on', !!(d.is_on && d.available));
    card.root.classList.toggle('unavailable', !d.available);
    setIcon(card.iconBox, d.domain === 'media_player' ? 'tv' : d.domain === 'switch' ? 'power' : 'bulb');
    card.name.textContent = d.name || d.entity_id;
    let line = d.available ? (t('state_' + d.state) !== 'state_' + d.state ? t('state_' + d.state) : String(d.state))
      : t('unavailable');
    if (d.group) line += ' · ' + t('group');
    if (d.brightness >= 0 && d.is_on) line += ' · ' + d.brightness + '%';
    card.status.textContent = line;
    card.toggle.setAttribute('aria-checked', d.is_on ? 'true' : 'false');
    card.toggle.setAttribute('aria-label', d.name || d.entity_id);
    card.toggle.disabled = !usable || !(d.is_on ? d.off_capable : d.on_capable);

    const dimmable = d.domain === 'light' && !!d.dimmable;
    card.brightRow.hidden = !dimmable;
    if (dimmable) {
      setRange(card.bright, d.brightness > 0 ? d.brightness : 50);
      if (!card.bright.dataset.dragging) card.brightValue.textContent = (d.brightness > 0 && d.is_on ? d.brightness : Number(card.bright.value)) + '%';
      card.bright.disabled = !usable;
    }
    card.swatches.hidden = !d.color_capable;
    if (d.color_capable) {
      const rgb = rgbOf(d.rgb);
      for (const { button, entry } of card.swatchButtons) {
        const want = rgbOf(entry.color);
        const current = !!(rgb && want && d.is_on && Math.max(...rgb.map((v, i) => Math.abs(v - want[i]))) <= 35);
        button.setAttribute('aria-current', current ? 'true' : 'false');
        button.disabled = !usable;
      }
    }
    const isMedia = d.domain === 'media_player';
    card.media.hidden = !isMedia;
    if (isMedia) {
      card.play.hidden = !d.play_capable;
      card.pause.hidden = !d.pause_capable;
      card.play.disabled = card.pause.disabled = !usable;
      const hasVolume = !!d.volume_capable;
      card.volume.hidden = !hasVolume;
      card.volIcon.style.display = hasVolume ? '' : 'none';
      card.volumeValue.hidden = !hasVolume;
      if (hasVolume) {
        setRange(card.volume, d.volume >= 0 ? d.volume : 0);
        if (!card.volume.dataset.dragging) card.volumeValue.textContent = (d.volume >= 0 ? d.volume : 0) + '%';
        card.volume.disabled = !usable || !(d.volume >= 0);
      }
    }
    card.root.classList.toggle('pending', state.pending.has(d.entity_id));
  }

  // ── Mira's face ────────────────────────────────────────────────────────────────
  const face = {
    front: el.faceA, back: el.faceB, target: '', token: 0, blinking: false, mouth: 0, lastSwap: 0,
    url(expression, style) {
      const hiDpi = (window.devicePixelRatio || 1) >= 1.5;
      return `/face/${style || state.face}/${expression}.${state.faceFormat}${hiDpi ? '?s=512' : ''}`;
    },
    show(expression, quick) {
      if (!state.paired) return;
      const url = this.url(expression);
      if (url === this.target) return;
      this.target = url;
      const token = ++this.token;
      const next = this.back, prev = this.front;
      let done = false;
      const reveal = () => {
        if (done || token !== this.token) return;
        done = true;
        next.classList.toggle('quick', !!quick);
        prev.classList.toggle('quick', !!quick);
        next.classList.add('on');
        prev.classList.remove('on');
        this.front = next;
        this.back = prev;
      };
      next.onload = reveal;
      if (next.getAttribute('src') !== url) next.setAttribute('src', url);
      if (next.complete && next.naturalWidth > 0) reveal();
      const avatar = this.url('neutral');
      if (el.avatar.getAttribute('src') !== avatar) el.avatar.setAttribute('src', avatar);
    },
    preload() {
      const moods = new Set(['neutral', 'happy', 'attentive', 'thinking', 'curious', 'sad', 'sleepy', 'blink',
        'speaking_open', 'speaking_round', state.mood || 'neutral']);
      setTimeout(() => { for (const expression of moods) { const image = new Image(); image.src = this.url(expression); } }, 600);
    },
  };

  function baseExpression() {
    switch (state.phase) {
      case 'listening': return 'attentive';
      case 'thinking': return 'thinking';
      case 'executing': return 'curious';
      case 'error': return 'sad';
      case 'offline': return 'sleepy';
      default: return state.mood || 'neutral';
    }
  }

  function updateFace() {
    let expression = baseExpression();
    let quick = false;
    if (state.phase === 'speaking' && !reducedMotion()) {
      if (face.mouth > 0.34) expression = 'speaking_open';
      else if (face.mouth > 0.1) expression = 'speaking_round';
      quick = true;
    }
    if (face.blinking) { expression = 'blink'; quick = true; }
    face.show(expression, quick);
  }

  let blinkTimer = 0;
  function scheduleBlink() {
    clearTimeout(blinkTimer);
    blinkTimer = setTimeout(() => {
      if (!document.hidden && state.paired && !reducedMotion() && state.phase !== 'speaking' && state.phase !== 'offline') {
        blink(Math.random() < 0.18);
      } else scheduleBlink();
    }, 2600 + Math.random() * 3800);
  }
  function blink(twice) {
    face.blinking = true;
    updateFace();
    setTimeout(() => {
      face.blinking = false;
      updateFace();
      if (twice) setTimeout(() => blink(false), 170);
      else scheduleBlink();
    }, 140);
  }

  // ── the ring of light (a 2D-canvas reading of shaders/aura.frag) ───────────────
  const TAU = Math.PI * 2;
  const hexRgb = (hex) => rgbOf(hex) || [255, 255, 255];
  const rgba = (c, a) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${Math.max(0, Math.min(1, a)).toFixed(3)})`;
  const mixc = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
  const grey = (c, k) => { const g = (c[0] + c[1] + c[2]) / 3; return mixc(c, [g, g, g], k); };
  const hash = (a, b) => { const x = Math.sin(a * 127.1 + b * 311.7) * 43758.5453; return x - Math.floor(x); };

  const ring = {
    ctx: el.ring.getContext('2d'), size: 0, dpr: 1, t: Math.random() * 100, lv: 0,
    cA: hexRgb(PHASE_COLORS.idle[0]), cB: hexRgb(PHASE_COLORS.idle[1]), tA: null, tB: null,
    w: { think: 0, exec: 0, err: 0, off: 0 }, tw: { think: 0, exec: 0, err: 0, off: 0 },
    motes: Array.from({ length: 18 }, (_, i) => ({ h1: hash(i, 3.7), h2: hash(i, 9.1) })),
    raf: 0, last: 0, lastActivity: performance.now(), lastMouth: 0,
    setPhase(phase, style) {
      const pair = phase === 'idle' && style === 'holo' ? ['#35D8F4', '#9B7BFF'] : (PHASE_COLORS[phase] || PHASE_COLORS.idle);
      this.tA = hexRgb(pair[0]);
      this.tB = hexRgb(pair[1]);
      this.tw = { think: phase === 'thinking' ? 1 : 0, exec: phase === 'executing' ? 1 : 0,
        err: phase === 'error' ? 1 : 0, off: phase === 'offline' ? 1 : 0 };
      this.kick();
    },
    resize() {
      const css = el.ring.clientWidth;
      if (!css) return false;
      const dpr = Math.min(window.devicePixelRatio || 1, 3);
      const px = Math.round(css * dpr);
      if (el.ring.width !== px) { el.ring.width = px; el.ring.height = px; }
      this.size = css;
      this.dpr = dpr;
      return true;
    },
    fps() {
      if (document.hidden || !state.paired) return 0;
      if (reducedMotion()) return 0;
      if (ACTIVE.includes(state.phase) || state.phase === 'error') return 60;
      const idle = performance.now() - this.lastActivity;
      if (idle < 45000) return 30;
      if (idle < 120000) return 12;
      return 0;
    },
    kick() {
      this.lastActivity = performance.now();
      if (!this.raf) {
        this.last = performance.now();
        this.raf = requestAnimationFrame((now) => this.frame(now));
      }
    },
    stop() { if (this.raf) cancelAnimationFrame(this.raf); this.raf = 0; },
    frame(now) {
      this.raf = 0;
      const fps = this.fps();
      if (fps === 0) {            // still: settle on the target state and draw once
        this.step(10);
        this.draw();
        return;
      }
      if (now - this.last >= 1000 / fps - 3) {
        this.step(Math.min(0.1, (now - this.last) / 1000));
        this.last = now;
        this.draw();
        if (state.phase === 'speaking' && now - this.lastMouth > 85) { this.lastMouth = now; updateFace(); }
        if (ACTIVE.includes(state.phase)) el.talk.style.setProperty('--level', this.lv.toFixed(3));
      }
      this.raf = requestAnimationFrame((next) => this.frame(next));
    },
    step(dt) {
      this.t += Math.min(dt, 0.1);
      const k = 1 - Math.exp(-dt / 0.18);
      if (this.tA) for (let i = 0; i < 3; i += 1) { this.cA[i] += (this.tA[i] - this.cA[i]) * k; this.cB[i] += (this.tB[i] - this.cB[i]) * k; }
      for (const key of Object.keys(this.w)) this.w[key] += (this.tw[key] - this.w[key]) * k;
      const voiced = state.phase === 'listening' || state.phase === 'speaking';
      const target = voiced ? Math.max(0, Math.min(1, state.level)) : 0;
      const rate = 1 - Math.exp(-dt / (target > this.lv ? 0.05 : 0.22));
      this.lv += (target - this.lv) * rate;
      const mouthTarget = state.phase === 'speaking' ? target : 0;
      face.mouth += (mouthTarget - face.mouth) * (1 - Math.exp(-dt / (mouthTarget > face.mouth ? 0.04 : 0.11)));
    },
    draw() {
      if (!this.resize()) return;
      const ctx = this.ctx, S = this.size, c = S / 2, t = this.t, lv = this.lv, w = this.w;
      const k = S / 300;
      const calm = 1 - w.off;
      const R = S / 3 + 1.5 * k;                       // just outside the face (portal = S / 1.5)
      let I = 1 - w.err * (0.28 - 0.28 * Math.sin(t * 3.2));
      I *= 1 - 0.65 * w.off;
      const A = grey(this.cA, w.off * 0.8), B = grey(this.cB, w.off * 0.8), mid = mixc(A, B, 0.5);
      ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      ctx.clearRect(0, 0, S, S);
      ctx.globalCompositeOperation = 'lighter';

      // outer glow: brighter and wider with the voice
      const outer = R * (1.34 + lv * 0.22);
      const glow = ctx.createRadialGradient(c, c, R * 0.9, c, c, outer);
      glow.addColorStop(0, rgba(mid, (0.26 + lv * 0.5) * I));
      glow.addColorStop(0.35, rgba(mid, (0.10 + lv * 0.22) * I));
      glow.addColorStop(1, rgba(mid, 0));
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(c, c, outer, 0, TAU);
      ctx.arc(c, c, R * 0.9, 0, TAU, true);
      ctx.fill();

      // the ring, breathing with slow noise; the voice makes it ripple
      const amp = (0.018 + lv * 0.085) * S * 0.5 * calm;
      const path = new Path2D();
      const N = 128;
      for (let i = 0; i <= N; i += 1) {
        const a = (i / N) * TAU;
        const n = 0.22 * Math.sin(3 * a + t * 0.9) + 0.16 * Math.sin(5 * a - t * 1.3 + 1.7) + 0.12 * Math.sin(2 * a + t * 0.5 + 0.6);
        const r = R + n * amp;
        const x = c + r * Math.cos(a), y = c + r * Math.sin(a);
        if (i === 0) path.moveTo(x, y); else path.lineTo(x, y);
      }
      let stroke;
      if (ctx.createConicGradient) {
        stroke = ctx.createConicGradient(t * 0.45, c, c);
        stroke.addColorStop(0, rgba(A, 1));
        stroke.addColorStop(0.5, rgba(B, 1));
        stroke.addColorStop(1, rgba(A, 1));
      } else {
        stroke = ctx.createLinearGradient(0, 0, S, S);
        stroke.addColorStop(0, rgba(A, 1));
        stroke.addColorStop(1, rgba(B, 1));
      }
      ctx.strokeStyle = stroke;
      for (const [width, alpha] of [[12, 0.1], [6, 0.22], [2.4, 0.92]]) {
        ctx.globalAlpha = Math.min(1, alpha * I * (1 + lv * 0.4));
        ctx.lineWidth = width * k * (1 + lv * 0.35);
        ctx.stroke(path);
      }
      ctx.globalAlpha = 1;

      // thinking: two comets chase around the ring
      if (w.think > 0.01) {
        const bright = mixc(A, [255, 255, 255], 0.45);
        for (const head of [t * 2.3, t * 2.3 + Math.PI]) {
          for (let j = 0; j < 14; j += 1) {
            const a0 = head - 0.9 + (j / 14) * 0.9;
            ctx.strokeStyle = rgba(bright, (j / 14) ** 2 * w.think * I);
            ctx.lineWidth = (1.2 + (j / 14) * 2.8) * k;
            ctx.beginPath();
            ctx.arc(c, c, R, a0, a0 + 0.9 / 14 + 0.01);
            ctx.stroke();
          }
        }
      }
      // executing: a segmented orbit just outside
      if (w.exec > 0.01) {
        const r = R + 0.055 * S;
        const segment = (TAU * r) / 36;
        ctx.setLineDash([segment * 0.3, segment * 0.7]);
        ctx.lineDashOffset = -t * 0.9 * segment;
        ctx.strokeStyle = rgba(mixc(A, B, 0.3), 0.9 * w.exec * I);
        ctx.lineWidth = 2.2 * k;
        ctx.beginPath();
        ctx.arc(c, c, r, 0, TAU);
        ctx.stroke();
        ctx.setLineDash([]);
      }
      // motes: sparks orbiting just outside; faster while thinking, brighter with the voice
      for (let i = 0; i < this.motes.length; i += 1) {
        const { h1, h2 } = this.motes[i];
        const a = h1 * TAU + t * (0.05 + 0.1 * h2) * (1 + 3 * w.think) * (h2 > 0.5 ? 1 : -1);
        const r = R + (0.035 + 0.085 * h2) * S + 0.008 * S * Math.sin(t * 0.7 + i);
        const twinkle = 0.55 + 0.45 * Math.sin(t * (1.3 + h1 * 2) + i * 1.7);
        ctx.fillStyle = rgba(mixc(A, B, h2), twinkle * (0.5 + 0.6 * lv + 0.4 * w.think) * calm * I);
        ctx.beginPath();
        ctx.arc(c + r * Math.cos(a), c + r * Math.sin(a), (0.9 + 0.9 * h1) * k, 0, TAU);
        ctx.fill();
      }
      ctx.globalCompositeOperation = 'source-over';
    },
  };

  // ── toasts ─────────────────────────────────────────────────────────────────────
  function toast(kind, text) {
    if (!text) return;
    kind = ['ok', 'pending', 'error', 'info'].includes(kind) ? kind : 'info';
    const item = node('div', 'toast');
    item.dataset.kind = kind;
    item.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    item.append(icon(kind === 'ok' ? 'check' : kind === 'error' ? 'alert' : kind === 'pending' ? 'clock' : 'sparkle'),
      node('span', '', String(text)));
    el.toasts.appendChild(item);
    while (el.toasts.children.length > 3) el.toasts.firstElementChild.remove();
    setTimeout(() => {
      item.classList.add('leaving');
      setTimeout(() => item.remove(), 260);
    }, kind === 'error' ? 5200 : 3600);
  }

  // ── layout: the visual viewport (iOS keyboard) and the face's size ─────────────
  function fitViewport() {
    const vv = window.visualViewport;
    const height = vv ? vv.height : window.innerHeight;
    const width = vv ? vv.width : window.innerWidth;
    const root = document.documentElement.style;
    root.setProperty('--app-h', Math.round(height) + 'px');
    root.setProperty('--app-top', Math.round(vv ? vv.offsetTop : 0) + 'px');
    const keyboard = !!vv && window.innerHeight - vv.height > 140 && document.activeElement === el.field;
    el.app.classList.toggle('keyboard', keyboard);
    const portal = keyboard ? 44 : Math.round(Math.max(96, Math.min(width * 0.4, (height - 330) * 0.42, 190)));
    root.setProperty('--portal', portal + 'px');
    ring.kick();
  }

  // ── interactions ───────────────────────────────────────────────────────────────
  function setView(view) {
    state.view = view === 'home' ? 'home' : 'mira';
    el.app.dataset.view = state.view;
    const home = state.view === 'home';
    el.viewMira.hidden = home;
    el.viewHome.hidden = !home;
    el.tabMira.setAttribute('aria-selected', String(!home));
    el.tabHome.setAttribute('aria-selected', String(home));
    el.tabMira.tabIndex = home ? -1 : 0;
    el.tabHome.tabIndex = home ? 0 : -1;
    if (!home) { ring.kick(); chat.scroll(true); }
  }

  function talkOrStop() {
    ring.kick();
    post(active() ? '/api/stop' : '/api/talk');
  }

  el.tabMira.addEventListener('click', () => setView('mira'));
  el.tabHome.addEventListener('click', () => setView('home'));
  el.tabs.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    const next = state.view === 'mira' ? 'home' : 'mira';
    setView(next);
    (next === 'home' ? el.tabHome : el.tabMira).focus();
  });
  el.core.addEventListener('click', talkOrStop);
  el.core.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); talkOrStop(); }
  });
  el.talk.addEventListener('click', talkOrStop);
  el.allOn.addEventListener('click', () => post('/api/lights', { on: true }));
  el.allOff.addEventListener('click', () => post('/api/lights', { on: false }));
  el.refresh.addEventListener('click', () => post('/api/home/refresh'));
  el.bannerRetry.addEventListener('click', () => { conn.attempt = 0; connect(); });
  el.pairRetry.addEventListener('click', () => { conn.attempt = 0; connect(); });

  const typing = () => el.app.classList.toggle('typing', document.activeElement === el.field || el.field.value !== '');
  el.field.addEventListener('input', () => { typing(); renderDock(); });
  el.field.addEventListener('focus', () => { typing(); setTimeout(fitViewport, 50); });
  el.field.addEventListener('blur', () => { typing(); setTimeout(fitViewport, 50); });
  el.dock.addEventListener('submit', async (event) => {
    event.preventDefault();
    const text = el.field.value.trim();
    if (!text || state.sending) return;
    if (text.length > 2000) { toast('error', t('too_long')); return; }
    state.sending = true;
    renderDock();
    const ok = await post('/api/send', { text });
    state.sending = false;
    if (ok) { el.field.value = ''; typing(); if (state.view !== 'mira') setView('mira'); }
    renderDock();
  });

  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', fitViewport);
    window.visualViewport.addEventListener('scroll', fitViewport);
  }
  window.addEventListener('resize', fitViewport);
  window.addEventListener('online', () => { if (state.paired && !live()) { conn.attempt = 0; connect(); } else renderBanner(); });
  window.addEventListener('offline', renderBanner);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { ring.stop(); return; }
    ring.kick();
    if (state.paired && !live() && !conn.source) { conn.attempt = 0; connect(); }
  });
  document.addEventListener('pointerdown', () => ring.kick(), { passive: true });
  if (motionQuery && motionQuery.addEventListener) motionQuery.addEventListener('change', () => { ring.kick(); updateFace(); });

  // ── start ──────────────────────────────────────────────────────────────────────
  const params = new URLSearchParams(window.location.search);
  renderAll();
  setView('mira');
  scheduleBlink();
  if (params.get('pair') === 'invalid') {
    window.history.replaceState(null, '', '/');
    showPairing('invalid');
  } else {
    connect();
  }
})();
