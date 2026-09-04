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
  const saved = localStorage.getItem(LANG_KEY);
  if (saved === "ar" || saved === "en") return saved;
  return navigator.language?.toLowerCase().startsWith("ar") ? "ar" : "en";
}

export function setLang(lang: Lang): void {
  localStorage.setItem(LANG_KEY, lang);
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
  rotation: { ar: "التدوير", en: "Rotation" },
  zoom: { ar: "التكبير", en: "Zoom" },
  fullscreen: { ar: "ملء الشاشة", en: "Fullscreen" },
  fitPhone: { ar: "ملاءمة التلفون", en: "Fit phone" },
  mouseSpeed: { ar: "سرعة الفأرة", en: "Mouse speed" },
  scrollSpeed: { ar: "سرعة التمرير", en: "Scroll speed" },
  haptics: { ar: "الاهتزاز", en: "Haptics" },
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
