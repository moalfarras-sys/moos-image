/**
 * i18n — one tiny dictionary, one hook, no framework.
 *
 * The controller was built bilingual-by-hand: labels drifted between Arabic,
 * English and "both on one line". This module makes language a single switch:
 * every UI string lives here, t() resolves it, and the <html lang>/<dir>
 * attributes follow the choice so RTL mirrors correctly. Default language is
 * the browser's — Arabic speakers get Arabic without touching settings.
 */

export type Lang = "ar" | "en";

const LANG_KEY = "mo-remote-lang";

export function detectLang(): Lang {
  let saved: string | null = null;
  try { saved = localStorage.getItem(LANG_KEY); } catch { /* storage can be denied */ }
  if (saved === "ar" || saved === "en") return saved;
  return navigator.language?.toLowerCase().startsWith("ar") ? "ar" : "en";
}

export function setLang(lang: Lang): void {
  try { localStorage.setItem(LANG_KEY, lang); } catch { /* keep the current page usable */ }
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
}

/** Apply the stored language before first paint of any screen. */
export function initLang(): Lang {
  const lang = detectLang();
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  return lang;
}

const dict = {
  // ── Connection / status ──
  connecting: { ar: "جارٍ الاتصال…", en: "Connecting…" },
  reconnect: { ar: "إعادة الاتصال", en: "Reconnect" },
  pausedOnPc: { ar: "متوقف مؤقتاً من الكمبيوتر", en: "Paused on the PC" },
  notSharing: { ar: "MoOS لا يشارك الشاشة", en: "MoOS is not sharing the screen" },
  retry: { ar: "إعادة المحاولة", en: "Retry" },

  // ── Bottom chrome tabs ──
  controls: { ar: "التحكم", en: "Controls" },
  keyboard: { ar: "لوحة المفاتيح", en: "Keyboard" },
  clipboard: { ar: "الحافظة", en: "Clipboard" },
  files: { ar: "الملفات", en: "Files" },
  more: { ar: "المزيد", en: "More" },

  // ── Settings sheet ──
  settings: { ar: "الإعدادات", en: "Settings" },
  display: { ar: "الشاشة", en: "Display" },
  video: { ar: "الفيديو", en: "Video" },
  screen: { ar: "الشاشة", en: "Screen" },
  connection: { ar: "الاتصال", en: "Connection" },
  pointer: { ar: "المؤشر", en: "Pointer" },
  feel: { ar: "الإحساس", en: "Feel" },
  security: { ar: "الأمان", en: "Security" },
  about: { ar: "حول", en: "About" },
  quality: { ar: "الجودة", en: "Quality" },
  auto: { ar: "تلقائي", en: "Auto" },
  autoQuality: { ar: "جودة تلقائية — تتكيف مع شبكتك", en: "Auto quality — adapts to your network" },
  monitor: { ar: "الشاشة", en: "Monitor" },
  sideways: { ar: "جانبي", en: "Sideways" },
  upright: { ar: "مستقيم", en: "Upright" },
  rotationHelp: { ar: "ملاءمة تلقائية لحجم الشاشة، أو تدوير جانبي تختاره بنفسك. يبقى الاتجاه ثابتًا أثناء الكتابة.", en: "Fit adapts to your screen size. Choose Sideways to turn the picture. The orientation stays fixed while typing." },
  rotation: { ar: "التدوير", en: "Rotation" },
  zoom: { ar: "التكبير", en: "Zoom" },
  zoomIn: { ar: "تكبير", en: "Zoom in" },
  zoomOut: { ar: "تصغير", en: "Zoom out" },
  fullscreen: { ar: "ملء الشاشة", en: "Fullscreen" },
  fitPhone: { ar: "ملاءمة التلفون", en: "Fit phone" },
  mouseSpeed: { ar: "سرعة الفأرة", en: "Mouse speed" },
  scrollSpeed: { ar: "سرعة التمرير", en: "Scroll speed" },
  haptics: { ar: "الاهتزاز", en: "Haptics" },
  hapticsSub: { ar: "اهتزازة قصيرة عند اللمس والنقر.", en: "A short buzz on tap and click." },
  language: { ar: "اللغة", en: "Language" },
  signOut: { ar: "تسجيل خروج", en: "Sign out" },

  // ── Clipboard ──
  clipboardSync: { ar: "مزامنة الحافظة", en: "Clipboard sync" },
  pcClipboard: { ar: "حافظة الكمبيوتر", en: "PC clipboard" },
  get: { ar: "جلب", en: "Get" },
  sendPaste: { ar: "إرسال ولصق", en: "Send & Paste" },
  send: { ar: "إرسال", en: "Send" },
  typeHere: { ar: "اكتب هنا ← يصل للكمبيوتر", en: "Type here → reaches the PC" },

  // ── Keys ──
  esc: { ar: "Esc", en: "Esc" },
  tab: { ar: "Tab", en: "Tab" },
  win: { ar: "Win", en: "Win" },

  // ── Files ──
  emptyFolder: { ar: "المجلد فارغ", en: "Empty folder" },

  // ── Actions ──
  actions: { ar: "إجراءات", en: "Actions" },
  alerts: { ar: "تنبيهات", en: "Alerts" },
  done: { ar: "تم", en: "Done" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  reset: { ar: "تصفير", en: "Reset" },
  power: { ar: "الطاقة", en: "Power" },

  // ── About ──
  versionAndConnection: { ar: "الإصدار والاتصال", en: "Version and connection" },
  appVersion: { ar: "إصدار التطبيق", en: "App version" },
  thisDevice: { ar: "هذا الجهاز", en: "This device" },

  // ── Gestures coach marks ──
  gestureHelp: {
    ar: "إصبعان للتمرير · قرصة للتكبير · نقرة مزدوجة للتقريب",
    en: "Two fingers: scroll · pinch to zoom · double-tap to magnify",
  },

  // ── PWA install banner ──
  installBanner: {
    ar: "ثبّت التطبيق على جهازك للحصول على تجربة كاملة",
    en: "Install Mo Remote for the full experience",
  },
  install: { ar: "تثبيت", en: "Install" },

  // ── Auth / PIN screens ──
  pinSetup: { ar: "أنشئ رمز دخولك الخاص", en: "Set up your private access PIN" },
  pinConfirmTitle: { ar: "أكّد رمز الدخول", en: "Confirm your PIN" },
  pinChoose: { ar: "اختر رمزاً من 6 أرقام على الأقل.", en: "Choose a PIN of at least 6 digits." },
  pinConfirm: { ar: "أدخل نفس الرمز مرة أخرى للتأكيد.", en: "Enter the same PIN again to confirm." },
  pinMismatch: { ar: "الرمزان غير متطابقين. حاول مجدداً.", en: "PINs do not match. Try again." },
  pinSaveFailed: { ar: "تعذّر حفظ الرمز. حاول مجدداً.", en: "Could not save PIN. Please retry." },
  pinEnter: { ar: "أدخل رمز الدخول للاتصال.", en: "Enter your PIN to connect." },
  pinWrong: { ar: "الرمز خاطئ. حاول مجدداً.", en: "Wrong PIN. Try again." },
  locked: { ar: "مقفل. حاول بعد", en: "Locked. Try again in" },
  connectionDropped: { ar: "انقطع الاتصال. أعد الاتصال بالكمبيوتر وحاول مجدداً.", en: "Connection dropped. Reconnect to the PC and retry." },
  trustDevice: { ar: "الثقة بهذا الجهاز لمدة 30 يوماً", en: "Trust this device for 30 days" },
  trustDeviceHint: { ar: "إعادة اتصال بعد إعادة تشغيل الوكيل دون إدخال الرمز.", en: "Reconnect after an agent restart without entering the PIN." },
  privateRemote: { ar: "تحكم خاص عن بُعد", en: "Private remote control" },

  // ── Settings sheet ──
  settingsTitle: { ar: "الإعدادات", en: "Settings" },
  mouseKeys: { ar: "فأرة + مفاتيح", en: "Mouse + keys" },
  trackpad: { ar: "لوحة لمس", en: "Trackpad" },
  touch: { ar: "لمس", en: "Touch" },
  drag: { ar: "سحب", en: "Drag" },
  desktop: { ar: "سطح مكتب", en: "Desktop" },
  oneFingerDrag: { ar: "سحب بإصبع واحد", en: "One-finger drag" },
  oneFingerDragSub: { ar: "اسحب بإصبع واحد بدل التمرير.", en: "Drag with one finger instead of scrolling." },
  capturePointer: { ar: "احتجاز المؤشر", en: "Capture pointer" },
  capturePointerSub: { ar: "حركة خام للألعاب و3D. Esc يحرّره. ملء الشاشة يحتجز Esc وTab وCtrl+W.", en: "Raw movement for 3D and games. Esc releases it. Fullscreen also captures Esc, Tab and Ctrl+W." },
  naturalScroll: { ar: "تمرير طبيعي", en: "Natural scroll" },
  naturalScrollSub: { ar: "المحتوى يتبع إصبعك.", en: "Content follows your finger." },
  magnifyTyping: { ar: "تكبير أثناء الكتابة", en: "Magnify while typing" },
  magnifyTypingSub: { ar: "عند فتح لوحة المفاتيح، يرتفع سطح المكتب ويتكبير ليظهر سطر الكتابة بوضوح.", en: "When the keyboard opens, the desktop lifts clear of it and zooms to the cursor so you can read the line you are writing." },
  backgroundAlerts: { ar: "تنبيهات في الخلفية", en: "Background alerts" },
  backgroundAlertsSub: { ar: "تنبيهات عامة للاتصال ونقل الملفات فقط. إشعارات سطح المكتب وأسماء الملفات ومحتوى الحافظة لا تغادر الكمبيوتر.", en: "Generic connection and transfer alerts only. Desktop notifications, filenames and clipboard content never leave the PC." },

  // ── Mode hints (touch/trackpad/mouse) ──
  modeHintTouch: { ar: "نقرة · سحب بالتمرير · ضغط مطوّل = زر أيمن · ضغط ثم حركة = سحب", en: "Tap · swipe scrolls · hold = right-click · hold then move = drag" },
  modeHintDirect: { ar: "نقرة للنقر · إصبع واحد يسحب · إصبعان يتمريران", en: "Tap to click · one finger drags · two fingers scroll" },
  modeHintTrackpad: { ar: "مرّر لتحريك المؤشر، مثل لوحة لمس الحاسوب", en: "Slide to move the pointer, like a laptop trackpad" },
  modeHintDesktop: { ar: "فأرة ولوحة مفاتيح حقيقية — بدون أي تفسير", en: "A real mouse and keyboard — nothing is interpreted" },

  // ── Toolbar ──
  sound: { ar: "الصوت", en: "Sound" },
  type: { ar: "كتابة", en: "Type" },
} as const;

export type StringId = keyof typeof dict;

/**
 * t(id) — resolve a string for the current language, falling back to English
 * (never empty) when a translation is missing.
 */
export function t(lang: Lang, id: StringId): string {
  const entry = dict[id];
  return entry ? entry[lang] : id;
}

/** Convenience: a bound translator. */
export function makeT(lang: Lang): (id: StringId) => string {
  return (id: StringId) => t(lang, id);
}
