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

  // ── Connection status pill ──
  connectedStatus: { ar: "متصل", en: "Connected" },
  reconnectingStatus: { ar: "إعادة الاتصال…", en: "Reconnecting…" },
  pausedOnPcStatus: { ar: "متوقف مؤقتاً على الكمبيوتر", en: "Paused on PC" },
  endedOnPc: { ar: "انتهت الجلسة على الكمبيوتر", en: "Ended on PC" },
  idleTimeout: { ar: "انتهت المهلة بسبب الخمول", en: "Idle timeout" },
  noVideo: { ar: "لا فيديو", en: "No video" },
  noInput: { ar: "لا إدخال", en: "No input" },
  noClipboard: { ar: "لا حافظة", en: "No clipboard" },
  connHealthyShow: { ar: "الاتصال سليم. إظهار تفاصيل الاتصال", en: "Connection healthy. Show connection details" },
  connHealthyHide: { ar: "الاتصال سليم. إخفاء تفاصيل الاتصال", en: "Connection healthy. Hide connection details" },
  connDetailsShown: { ar: "تُعرض تفاصيل الاتصال", en: "Connection details are shown" },

  // ── Reconnect overlay ──
  openingDesktop: { ar: "جارٍ فتح سطح مكتب MoOS", en: "Opening your MoOS desktop" },
  restoringConnection: { ar: "جارٍ استعادة الاتصال", en: "Restoring the connection" },
  preparingPicture: { ar: "جارٍ تجهيز صورة واضحة وسريعة الاستجابة…", en: "Preparing a clear, responsive picture…" },
  controlsAreSafe: { ar: "أدواتك بأمان. ستتابع الصورة تلقائياً.", en: "Your controls are safe. The picture will continue automatically." },

  // ── Toasts / runtime feedback ──
  notifPermDenied: { ar: "لم يُمنح إذن الإشعارات", en: "Notification permission was not granted" },
  trustedDevicesLoadFailed: { ar: "تعذّر تحميل الأجهزة الموثوقة", en: "Could not load trusted devices" },
  deviceRemoved: { ar: "تمت إزالة", en: "removed" },
  deviceRemoveFailed: { ar: "تعذّر إزالة هذا الجهاز", en: "Could not remove that device" },
  videoFellBackJpeg: { ar: "عاد الفيديو إلى JPEG", en: "Video fell back to JPEG" },
  inputPrefix: { ar: "الإدخال:", en: "Input:" },
  imagePastedPc: { ar: "تم لصق الصورة على الكمبيوتر", en: "Image pasted on PC" },
  textPastedPc: { ar: "تم لصق النص على الكمبيوتر", en: "Text pasted on PC" },
  imageSendFailedNothingPasted: { ar: "تعذّر إرسال الصورة — لم يُلصق شيء", en: "Couldn't send the image — nothing pasted" },
  textSendFailedNothingPasted: { ar: "تعذّر إرسال النص — لم يُلصق شيء", en: "Couldn't send the text — nothing pasted" },
  folderOpenFailed: { ar: "تعذّر فتح هذا المجلد", en: "Can't open that folder" },
  qualityPrefix: { ar: "الجودة:", en: "Quality:" },
  fitToScreen: { ar: "ملاءمة الشاشة", en: "Fit to screen" },
  originalSize100: { ar: "الحجم الأصلي (100%)", en: "Original size (100%)" },
  gotPcImage: { ar: "تم جلب صورة الكمبيوتر", en: "Got PC image" },
  gotPcText: { ar: "تم جلب نص الكمبيوتر", en: "Got PC text" },
  pcClipboardEmpty: { ar: "حافظة الكمبيوتر فارغة", en: "PC clipboard is empty" },
  pcClipboardReadFailed: { ar: "تعذّرت قراءة حافظة الكمبيوتر", en: "Failed to read PC clipboard" },
  pcClipboardUpdated: { ar: "تم تحديث حافظة الكمبيوتر", en: "PC clipboard updated" },
  pcClipboardSetFailed: { ar: "تعذّر تحديث حافظة الكمبيوتر", en: "Failed to set PC clipboard" },
  copiedOnPhone: { ar: "تم النسخ على الهاتف", en: "Copied on phone" },
  longPressToCopy: { ar: "اضغط مطوّلاً على النص لنسخه", en: "Long-press the text to copy" },
  imageTooLarge: { ar: "الصورة كبيرة جداً (الحد الأقصى ~24 م.ب)", en: "Image too large (max ~24MB)" },
  pcClipboardImageUpdated: { ar: "تم تحديث صورة حافظة الكمبيوتر", en: "PC clipboard image updated" },
  imageSendFailed: { ar: "تعذّر إرسال الصورة", en: "Image wasn't sent — nothing pasted" },
  pcImageSetFailed: { ar: "تعذّر تحديث صورة الكمبيوتر", en: "Failed to set PC image" },
  downloadAuthFailed: { ar: "فشل تفويض التنزيل", en: "Download authorization failed" },
  downloadingPrefix: { ar: "جارٍ تنزيل", en: "Downloading" },
  uploadedToPcPrefix: { ar: "تم رفع", en: "Uploaded" },
  uploadedToPcSuffix: { ar: "إلى الكمبيوتر", en: "to PC" },
  uploadPaused: { ar: "تم إيقاف الرفع مؤقتاً — اختر نفس الملف للمتابعة", en: "Upload paused — select the same file to resume" },
  modePrefix: { ar: "الوضع:", en: "Mouse:" },
  taskManagerSafe: { ar: "مدير المهام (Ctrl+Alt+Del آمن)", en: "Task Manager (safe Ctrl+Alt+Del)" },
  soundAuthFailed: { ar: "فشل تفويض الصوت", en: "Sound authorization failed" },
  soundUnavailable: { ar: "الصوت غير متاح حالياً", en: "Sound is unavailable right now" },
  soundNoEndpoint: { ar: "لا يوجد منفذ صوت — نفّذ: moos-cloud-desktop doctor", en: "No sound endpoint — run: moos-cloud-desktop doctor" },
  addToHomeScreenFullscreen: { ar: "أضِف التطبيق للشاشة الرئيسية لملء الشاشة", en: "Add to Home Screen for fullscreen" },
  safariShareAddHome: { ar: "Safari ◂ مشاركة ◂ إضافة إلى الشاشة الرئيسية", en: "Safari ▸ Share ▸ Add to Home Screen" },
  refreshingEllipsis: { ar: "جارٍ التحديث…", en: "Refreshing…" },
  screenNumberPrefix: { ar: "شاشة", en: "Screen" },
  mainScreen: { ar: "الرئيسية", en: "Main" },
  remoteMoosDesktopAria: { ar: "سطح مكتب MoOS عن بُعد", en: "Remote MoOS desktop" },
  remoteControlsAria: { ar: "أدوات التحكم عن بُعد", en: "Remote controls" },
  zoomCenterAria: { ar: "تكبير على المركز، أو العودة للملاءمة", en: "Zoom in on the centre, or back to fit" },
  idleReconnectBody: {
    ar: "أعد الاتصال متى شئت. لن تُكتب أي حروف حتى تعود سطح المكتب.",
    en: "Reconnect when you are ready. Nothing will be typed until the desktop returns.",
  },
  stoppedSignoutBody: {
    ar: "ابدأ جلسة جديدة أو سجّل الخروج من هذا الجهاز.",
    en: "Start a fresh session or sign out from this device.",
  },

  // ── Default device names (shown later in Security ▸ trusted devices) ──
  androidPhone: { ar: "هاتف أندرويد", en: "Android phone" },
  windowsDevice: { ar: "جهاز ويندوز", en: "Windows device" },
  linuxDevice: { ar: "جهاز لينكس", en: "Linux device" },
  myDevice: { ar: "جهازي", en: "My device" },
  backspaceAria: { ar: "حذف", en: "Backspace" },
  cannotReachPc: {
    ar: "تعذّر الوصول إلى الكمبيوتر. هل الوكيل يعمل و Tailscale متصل؟",
    en: "Cannot reach the PC. Is the agent running and Tailscale connected?",
  },
  longPressPasteHint: {
    ar: "…أو اضغط مطوّلاً هنا ← الصق، ثم أرسل والصق على الكمبيوتر",
    en: "…or long-press here → Paste, then send & paste on the PC",
  },
  approvedButDropped: {
    ar: "تم قبول الدخول، لكن اتصال الكمبيوتر انقطع. أعد الاتصال وحاول مجدداً.",
    en: "Access was approved, but the PC connection dropped. Reconnect and retry.",
  },

  // ── Orientation toast ──
  orientAutoToast: { ar: "يتبع هاتفك — مستقيم", en: "Follows your phone — upright" },
  orientOnToast: { ar: "مُدار جانبياً — يملأ الشاشة", en: "Turned sideways — fills the screen" },
  orientOffToast: { ar: "مُثبّت مستقيماً", en: "Locked upright" },

  // ── Quality presets ──
  qualityDataSaver: { ar: "توفير البيانات", en: "Data saver" },
  qualityBalanced: { ar: "متوازن", en: "Balanced" },
  qualitySharp: { ar: "حاد", en: "Sharp" },
  qualityUltra: { ar: "فائق", en: "Ultra" },

  // ── Actions grid ──
  ctrlAltDel: { ar: "Ctrl+Alt+Del", en: "Ctrl+Alt+Del" },
  copy: { ar: "نسخ", en: "Copy" },
  paste: { ar: "لصق", en: "Paste" },
  refresh: { ar: "تحديث", en: "Refresh" },
  disconnect: { ar: "قطع الاتصال", en: "Disconnect" },
  showRemoteControls: { ar: "إظهار أدوات التحكم", en: "Show remote controls" },

  // ── Power section ──
  powerSummaryAllowed: { ar: "قفل، سكون، إعادة تشغيل، إيقاف تشغيل", en: "Lock, sleep, restart, shut down" },
  powerSummaryManaged: { ar: "تُدار من مسؤول السحابة", en: "Managed by the Cloud administrator" },
  powerCloudManagedBody: {
    ar: "هذه جلسة سحابية مشتركة بلا كلمة مرور. استخدم طرفية الخادم لإعادة تشغيلها أو إنهائها بأمان.",
    en: "This is a shared, passwordless Cloud session. Use the server console to restart or end it safely.",
  },
  lock: { ar: "قفل", en: "Lock" },
  sleep: { ar: "سكون", en: "Sleep" },
  signOutPower: { ar: "تسجيل الخروج", en: "Sign out" },
  restart: { ar: "إعادة التشغيل", en: "Restart" },
  shutDown: { ar: "إيقاف التشغيل", en: "Shut down" },

  // ── Security / trusted devices ──
  loadingTrustedDevices: { ar: "جارٍ تحميل الأجهزة الموثوقة…", en: "Loading trusted devices…" },
  noRememberedDevices: { ar: "لا توجد أجهزة محفوظة.", en: "No remembered devices." },
  thisDeviceSuffix: { ar: " · هذا الجهاز", en: " · This device" },
  lastUsedPrefix: { ar: "آخر استخدام", en: "Last used" },
  removeDevice: { ar: "إزالة", en: "Remove" },
  removingDevice: { ar: "جارٍ الإزالة…", en: "Removing…" },
  removeTrustedDeviceAria: { ar: "إزالة الجهاز الموثوق", en: "Remove trusted device" },

  // ── Files sheet ──
  filesTitle: { ar: "الملفات", en: "Files" },
  up: { ar: "أعلى", en: "Up" },
  uploadHere: { ar: "رفع هنا", en: "Upload here" },
  loadingEllipsis: { ar: "جارٍ التحميل…", en: "Loading…" },
  truncatedFolderNotice: {
    ar: "تُعرض أول 500 عنصر. افتح مجلداً أصغر للمتابعة.",
    en: "Showing the first 500 items. Open a smaller folder to continue.",
  },

  // ── Clipboard sheet ──
  pcToPhone: { ar: "من الكمبيوتر إلى الهاتف", en: "From PC to phone" },
  phoneToPcText: { ar: "من الهاتف إلى الكمبيوتر · نص", en: "From phone to PC · text" },
  phoneToPcImage: { ar: "من الهاتف إلى الكمبيوتر · صورة", en: "From phone to PC · image" },
  readPhoneClipboard: { ar: "لصق من حافظة الهاتف", en: "Paste from phone clipboard" },
  pastePhoneManually: { ar: "اضغط مطوّلاً داخل حقل النص واختر لصق.", en: "Long-press the text field and choose Paste." },
  pastePc: { ar: "لصق بالكمبيوتر", en: "Paste on PC" },
  fitScreen: { ar: "ملاءمة الشاشة", en: "Fit screen" },
  selectAll: { ar: "تحديد الكل", en: "Select all" },
  undo: { ar: "تراجع", en: "Undo" },
  pressGetToFetch: { ar: "اضغط جلب لإحضار حافظة الكمبيوتر", en: "Press Get to fetch the PC clipboard" },
  typeOrPasteText: { ar: "اكتب أو الصق نصاً…", en: "Type or paste text…" },
  getPcClipboard: { ar: "جلب حافظة الكمبيوتر", en: "Get PC Clipboard" },
  setOnly: { ar: "تعيين فقط", en: "Set only" },
  setImageOnly: { ar: "تعيين الصورة فقط", en: "Set image only" },
  photoAndPaste: { ar: "صورة ولصق", en: "Photo & Paste" },
  longPressImageSaveCopy: {
    ar: "اضغط مطوّلاً على الصورة للحفظ / النسخ على آيفون.",
    en: "Long-press the image to Save / Copy on your iPhone.",
  },
  sendingImage: { ar: "جارٍ إرسال الصورة…", en: "Sending image…" },
  sendingText: { ar: "جارٍ إرسال النص…", en: "Sending text…" },
  sendingPastingText: { ar: "جارٍ الإرسال واللصق…", en: "Sending and pasting text…" },
  sendingPastingImage: { ar: "جارٍ إرسال الصورة ولصقها…", en: "Sending and pasting image…" },
  settingPcClipboard: { ar: "جارٍ تعيين حافظة الكمبيوتر…", en: "Setting PC clipboard…" },
  settingPcImage: { ar: "جارٍ تعيين صورة الكمبيوتر…", en: "Setting PC image…" },
  closePrefix: { ar: "إغلاق", en: "Close" },

  // ── Power confirmation dialog ──
  confirmPrefix: { ar: "تأكيد", en: "Confirm" },
  thisPcQuestion: { ar: "هذا الكمبيوتر؟", en: "this PC?" },
  shutdownConfirmBody: {
    ar: "ستنتهي الجلسة عن بُعد وسيُطفأ هذا الكمبيوتر. قد يُفقد أي عمل غير محفوظ.",
    en: "The remote session will end and this computer will power off. Unsaved work may be lost.",
  },
  restartConfirmBody: {
    ar: "ستنتهي الجلسة عن بُعد أثناء إعادة تشغيل هذا الكمبيوتر. قد يُفقد أي عمل غير محفوظ.",
    en: "The remote session will end while this computer restarts. Unsaved work may be lost.",
  },
  sessionEndConfirmBody: {
    ar: "ستنتهي جلسة سطح المكتب الحالية. قد يُفقد أي عمل غير محفوظ.",
    en: "The current desktop session will end. Unsaved work may be lost.",
  },
  workingEllipsis: { ar: "جارٍ التنفيذ…", en: "Working…" },
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
