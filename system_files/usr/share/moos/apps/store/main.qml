// Mo Store — MoOS's one place to find, install, open, update, remove and permission apps: Linux
// apps, web apps, Windows programs and Android apps, with what this computer can run said honestly
// before anything happens.
//
// The signed catalogue (/usr/share/moos/store/catalog.json) paints the first frame and carries
// MoOS's own recommendations. /usr/bin/moos-store-index expands it at launch into index.json:
// every app this machine can be offered, with its kind, its Store category, a folded search key, a
// compatibility verdict and a pointer to its details document (docs/MO_STORE.md). The window reads
// the index ONCE per generation, derives its maps, counts and orders from it in place, and never
// re-sorts it on a job tick: a finished job changes only the installed flags of its own items.
//
// State-changing work never travels through the public `moos:` URL scheme. MoosStore is a narrow
// C++ bridge exposed only to this read-only QML (and the Welcome). It starts /usr/bin/moos-storectl
// with an argv list; the backend validates ids again, owns the real transactions and atomically
// publishes job.json. A web page can open Mo Store or an app's page, but it cannot install an app.
// Bridge methods newer than the installed shell are called only through a `typeof` guard, and a
// missing one says that it needs the next MoOS update instead of failing silently.
//
// This file is the window: all state, the data loading, the timers, the bridge calls and the
// palette live here. What it draws lives in the files beside it: StoreRail and StoreHeader, one
// file per page (DiscoverPage, AppsPage, LibraryPage, UpdatesPage, SettingsPage, SearchPage and
// AppPage), the sheets and shelves, and the cards and controls they are built from. Each takes
// this window as `required property var win` and reaches it only as `win.<member>`
// (tests/test_qml_root_references.py holds that line); an id one of them needs from here is a root
// member instead (focusSearch(), openReview(), openRemove(), indexPolling, …).
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs as NativeDialogs
import QtCore
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

ApplicationWindow {
    id: win

    // Motion gate: the hero's auto-advance, the catalogue working light and the indeterminate job
    // bar AND their `running:` with this, and every duration collapses to 0 with it, so "disable
    // animations" stops all of them. Kirigami floors longDuration at 1 when motion is off, so
    // `> 1` is the honest off-switch.
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    visible: true
    width: Math.min(1440, Screen.desktopAvailableWidth * 0.94)
    height: Math.min(900, Screen.desktopAvailableHeight * 0.94)
    minimumWidth: Math.min(960, Screen.desktopAvailableWidth * 0.94)
    minimumHeight: Math.min(620, Screen.desktopAvailableHeight * 0.94)
    title: qsTr("Mo Store")
    color: win.canvas

    // TYPE SCALES WITH THE USER'S FONT SIZE.
    //
    // 294 text items across the MoOS apps once carried a hardcoded `font.pixelSize`, so the size
    // slider in System Settings > Fonts moved every application on the machine except this
    // operating system's own. The reference is POINT size, not pixels: MoOS ships
    // `IBM Plex Sans,10` in /etc/xdg/kdeglobals, so dividing by the shipped 10pt gives exactly 1.0
    // on every screen at the default and scales only when the USER changes the setting.
    //
    // fs() is for geometry that grows with the user's font setting. Text goes through typePx(),
    // which snaps to the reviewed 11/13/14/15/20/24/32/48 role ramp.
    readonly property real fontScale: Qt.application.font.pointSize > 0
                                      ? Qt.application.font.pointSize / 10 : 1
    function fs(px) { return Math.round(px * win.fontScale) }
    function typePx(px) { return design.typeSize(px, win.fontScale) }
    function local(ar, en) { return win.rtl ? ar : en }
    readonly property var design: MoUI.Tokens

    // The UI face is the SYSTEM face: on MoOS that already is IBM Plex Sans (Arabic), and naming it
    // here would only override a face the person chose for themselves.
    readonly property string uiFont: Qt.application.font.family

    // ── semantic palette ───────────────────────────────────────────────────────
    //
    // READ FROM Kirigami.Theme, NOT FROM `palette`: a bare `palette` in a QQuickWindow does not
    // resolve the KDE colour scheme and falls back to Qt's stock blue. The window paints on the
    // VIEW set; content needs its airier end or the page collapses into one flat wash.
    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.View

    readonly property color canvas:   Kirigami.Theme.backgroundColor
    readonly property color surface:  Kirigami.Theme.alternateBackgroundColor
    readonly property color raised:   Kirigami.Theme.backgroundColor
    readonly property color chrome:   Kirigami.Theme.backgroundColor

    // Outline is the FOREGROUND at low alpha, NOT Kirigami.Theme.separatorColor — that renders
    // #FFFFFF in all five colour sets of these schemes, so binding to it deletes every hairline on a
    // light page. A tint of the text colour is dark on light and light on dark, in every family.
    readonly property color outline:  Qt.rgba(Kirigami.Theme.textColor.r,
                                              Kirigami.Theme.textColor.g,
                                              Kirigami.Theme.textColor.b, 0.14)
    readonly property color blue:     Kirigami.Theme.highlightColor
    readonly property color cyan:     Kirigami.Theme.linkColor
    readonly property color violet:   Kirigami.Theme.visitedLinkColor
    readonly property color dangerInk: Kirigami.Theme.negativeTextColor
    readonly property color positiveInk: Kirigami.Theme.positiveTextColor
    readonly property color warningInk: Kirigami.Theme.neutralTextColor
    readonly property color txt:      Kirigami.Theme.textColor
    // Secondary text is text a person READS — a description, a label, a hint — so it is the
    // primary ink at 72%, exactly as MoOS Settings' mutedColor. The DISABLED role measures 1.6:1 on
    // the light schemes; 72% measures 4.8-5.1:1 (light) and 8.4-9.9:1 (dark).
    // tests/test_secondary_text_contrast.py computes it for every shipped scheme.
    readonly property color txt2:     Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                              Kirigami.Theme.textColor.b, 0.72)
    readonly property color accentText: Kirigami.Theme.highlightedTextColor
    readonly property color accent:   Kirigami.Theme.highlightColor  // ONE accent for the OS: the theme's highlight.
    readonly property bool lightScheme: design.isLight(Kirigami.Theme.backgroundColor)
    readonly property bool rtl: MoUI.Locale.rtl
    readonly property bool compactRail: win.width < 1100
    // Room every page leaves at its foot while a shelf floats there (a selection, a job), so its
    // last row can always scroll clear of the shelf.
    readonly property real footClearance: win.pickCount > 0 || win.jobIsActive() || win.jobIsTerminal()
                                          ? win.fs(112) : 0

    // A colour at an alpha, so a view never spells out four channels to fade one role.
    function tint(color, alpha) { return Qt.rgba(color.r, color.g, color.b, alpha) }

    // The Store's card material, from the scheme: on a light scheme a frosted, paler pane of the
    // canvas; on a dark one the alternate background lifted a breath toward the ink. Opaque, so a
    // soft shadow can sit under it and the material holds with compositing and blur off.
    readonly property color cardColor: win.lightScheme
        ? Qt.tint(win.canvas, Qt.rgba(1, 1, 1, 0.55))
        : Qt.tint(win.surface, win.tint(win.txt, 0.035))
    readonly property color cardBorder: win.tint(win.txt, win.lightScheme ? 0.11 : 0.12)
    // The rail and the header's search: a little denser than the canvas they float on.
    readonly property color glassColor: win.lightScheme
        ? Qt.tint(win.canvas, Qt.rgba(1, 1, 1, 0.38))
        : Qt.tint(win.canvas, win.tint(win.surface, 0.82))

    // The ink for a surface painted in an APP's colour (a hero, a monogram, an app page's band).
    // The scheme cannot supply it: the surface is the app's, not the theme's. So the ink is near
    // white or near black, whichever reads better, and readableBase() moves the surface until that
    // ink reaches WCAG AA 4.5:1 — measured, never assumed.
    readonly property color inkOnDark: Qt.rgba(1, 1, 1, 1)
    readonly property color inkOnLight: Qt.rgba(0.055, 0.067, 0.086, 1)
    function luminanceOf(c) {
        function channel(v) { return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
        return 0.2126 * channel(c.r) + 0.7152 * channel(c.g) + 0.0722 * channel(c.b)
    }
    function contrastOf(a, b) {
        var la = win.luminanceOf(a)
        var lb = win.luminanceOf(b)
        return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
    }
    function inkOn(c) {
        return win.contrastOf(c, win.inkOnDark) >= win.contrastOf(c, win.inkOnLight)
            ? win.inkOnDark : win.inkOnLight
    }
    function readableBase(c, ink) {
        var base = c
        var darken = win.luminanceOf(ink) > 0.5
        for (var i = 0; i < 16 && win.contrastOf(base, ink) < 4.6; ++i)
            base = darken ? Qt.darker(base, 1.1) : Qt.lighter(base, 1.06)
        return base
    }

    // The plate an app's colour paints (the hero, an app page's band): light ink when the colour can
    // carry it after a modest deepening — an editorial plate — and otherwise, on a light scheme, a
    // pastel of the colour (a third of the canvas mixed in) under dark ink, so a pale brand colour
    // never shouts across a light page.
    function plateColour(c) {
        var deep = c
        for (var i = 0; i < 5 && win.contrastOf(deep, win.inkOnDark) < 4.6; ++i)
            deep = Qt.darker(deep, 1.1)
        if (win.contrastOf(deep, win.inkOnDark) >= 4.6) return deep
        var pale = win.lightScheme ? Qt.tint(c, win.tint(win.canvas, 0.34)) : c
        return win.readableBase(pale, win.inkOnLight)
    }

    // The ink for LARGE type on an app's colour (a monogram's letter): light whenever it reaches
    // the 3:1 WCAG asks of large text, as brand tiles do.
    function inkOnLarge(c) {
        return win.contrastOf(c, win.inkOnDark) >= 3 ? win.inkOnDark : win.inkOnLight
    }

    // Paths are passed by /usr/bin/moos-store.  Pure QML intentionally has no
    // environment or process access.
    readonly property string cacheDir: win.argValue("--cache=")
    readonly property string indexPath: win.argValue("--index=")
    readonly property string machinePath: win.argValue("--machine=")
    readonly property string jobPath: win.argValue("--job=")
    readonly property string readyPath: win.argValue("--ready=")
    readonly property string updatesPath: win.argValue("--updates=")
    readonly property string factsPath: win.argValue("--facts=")
    readonly property string settingsPath: win.argValue("--settings=")

    // Catalogue and navigation state.
    property var curatedApps: []
    property var curatedMap: ({})
    property var allApps: []
    property var appMap: ({})
    property var browseOrder: []
    property var visibleApps: []
    property var bundles: []
    property var collections: []
    property var featured: []
    property var storeCategories: []
    property var kindCounts: ({})
    property var viewKindCounts: ({})
    property var catCounts: ({})
    property var indexSources: []
    property var indexStats: ({})
    property string indexGeneratedAt: ""
    property string indexToken: ""
    property bool indexReady: false
    property string loadError: ""
    property string page: "discover"
    property var history: []
    property string activeCategory: "all"
    property string activeKind: "all"
    property string activeCollection: ""
    property string sortMode: "recommended"
    property bool canSortByDate: false
    property string libraryKind: "all"
    property var installedApps: []
    property var libraryApps: []
    property string query: ""
    property var searchResults: []
    property var selectedApp: null
    property var selectedDetails: null
    property string detailsState: "none"
    property var detailsCache: ({})

    // Selection and real transaction state.
    property var picks: ({})
    property int pickCount: 0
    property var job: ({})
    property bool waitingForJob: false
    property string previousJobId: ""
    property int jobWaitTicks: 0
    property string expectedAction: ""
    property var expectedIds: []
    property double requestEpoch: 0
    property var installedOverrides: ({})
    property var installedScopeOverrides: ({})
    property bool catalogRefreshRequested: false

    // Pending updates. `updatesState` is deliberately three-valued: "unknown"
    // is not the same as "none", and a page that shows 0 before it has looked
    // is lying. Nothing here is derived from the index — only from the backend's
    // own read-only answer.
    property var updates: ({})
    property string updatesState: "unknown"
    property bool updatesChecking: false
    property string updatesCheckedAt: ""

    // The owner's automatic-update choice, as the backend persisted it (absent means on).
    property bool autoUpdates: true
    property bool autoUpdatesPending: false
    property bool autoUpdatesWanted: true

    // What this computer is (machine.json), the cached catalogue facts (sizes, permission words,
    // end of life) and the installed app's permission document for the page that is open.
    property var machine: ({})
    property var facts: ({})
    property string factsState: "none"
    property var permissionDoc: null
    property string permissionState: "none"
    property string permissionAppId: ""
    property double permissionRequestedAt: 0

    // ── what the window shows ───────────────────────────────────────────────────
    readonly property var navItems: [
        { id: "discover", ar: "اكتشف",     en: "Discover", glyph: "compass" },
        { id: "apps",     ar: "التطبيقات", en: "Apps",     glyph: "grid" },
        { id: "games",    ar: "الألعاب",   en: "Games",    glyph: "gaming" },
        { id: "library",  ar: "تطبيقاتي",  en: "My apps",  glyph: "boxes" },
        { id: "updates",  ar: "التحديثات", en: "Updates",  glyph: "safe-update" },
        { id: "settings", ar: "الإعدادات", en: "Settings", glyph: "settings" }
    ]

    // The Store's twelve categories (catalogue `categories[]`). The index names them; these are the
    // words used before it arrives and for any id it does not name. Android and Windows wear MoOS's
    // own glyphs, never another system's mark.
    readonly property var storeCategoryDefs: [
        { id: "ess",   ar: "الأساسيات",        en: "Essentials",           glyph: "compass" },
        { id: "comm",  ar: "التواصل",          en: "Communication",        glyph: "chat" },
        { id: "work",  ar: "المكتب والدراسة",   en: "Office & study",       glyph: "briefcase" },
        { id: "art",   ar: "التصميم والصور",    en: "Graphics & photo",     glyph: "pen" },
        { id: "media", ar: "شاهد واستمع",       en: "Watch & listen",       glyph: "play" },
        { id: "fun",   ar: "الألعاب",          en: "Games",                glyph: "gaming" },
        { id: "dev",   ar: "البرمجة",          en: "Development",          glyph: "code" },
        { id: "ai",    ar: "الذكاء الاصطناعي",  en: "AI",                   glyph: "ai" },
        { id: "edu",   ar: "التعليم",          en: "Education",            glyph: "bulb" },
        { id: "util",  ar: "الأدوات والأمان",   en: "Utilities & security", glyph: "shield" },
        { id: "droid", ar: "تطبيقات أندرويد",   en: "Android apps",         glyph: "phone" },
        { id: "win",   ar: "برامج ويندوز",      en: "Windows programs",     glyph: "system" }
    ]

    // Where an app comes from, in the four words a person uses (docs/MO_STORE.md "Kinds of app").
    readonly property var kindDefs: [
        { id: "linux",   ar: "تطبيقات لينكس",  en: "Linux apps",       glyph: "cube",
          ar2: "معزولة، من الكتالوج المفتوح",          en2: "Sandboxed, from the open catalogue" },
        { id: "web",     ar: "تطبيقات الويب",  en: "Web apps",         glyph: "globe",
          ar2: "كل تطبيق في نافذته الخاصة",           en2: "Each in a window of its own" },
        { id: "windows", ar: "برامج ويندوز",   en: "Windows programs", glyph: "system",
          ar2: "من الناشر، ومطابقة لبصمة راجعناها",      en2: "From the publisher, checked by fingerprint" },
        { id: "android", ar: "تطبيقات أندرويد", en: "Android apps",     glyph: "phone",
          ar2: "تعمل بجانب برامجك الأخرى",             en2: "Running beside your other programs" }
    ]

    // The index's old 14-value `category`, for an index written before `cat` existed.
    readonly property var legacyCategory: ({
        "internet": "ess", "communication": "comm", "office": "work", "development": "dev",
        "graphics": "art", "audio-video": "media", "games": "fun", "education": "edu",
        "science": "edu", "utilities": "util", "system": "util", "finance": "work",
        "ai": "ai", "other": "util"
    })

    function argValue(prefix) {
        var args = Qt.application.arguments
        for (var i = 0; i < args.length; ++i)
            if (args[i].indexOf(prefix) === 0)
                return args[i].substring(prefix.length)
        return ""
    }

    // ── words ───────────────────────────────────────────────────────────────────
    function localName(obj) {
        if (!obj) return ""
        if (win.rtl) return obj.ar || obj.name || obj.name_en || obj.en || obj.id || ""
        return obj.en || obj.name_en || obj.name || obj.ar || obj.id || ""
    }

    function localSummary(obj) {
        if (!obj) return ""
        if (win.rtl) return obj.desc_ar || obj.summary || obj.desc_en || ""
        return obj.desc_en || obj.summary || obj.desc_ar || ""
    }

    function localDescription(obj) {
        if (!obj) return ""
        // A curated entry's description IS its summary in the index's language; the window's
        // language decides which of the catalogue's two it shows.
        if (obj.desc_en || obj.desc_ar) return win.localSummary(obj)
        if (obj.description) return obj.description
        return win.localSummary(obj)
    }

    // A left-to-right island for a version, a size or an address inside right-to-left text.
    function ltr(text) { return "⁦" + text + "⁩" }

    function countText(n) {
        return String(Math.round(n || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, ",")
    }

    // Arabic counts by the language's own rules: one and two have their own words, 3–10 the
    // plural, 11–99 the singular accusative, and a hundred and up the singular again.
    function arabicCount(n, one, two, few, many, other) {
        if (n === 1) return one
        if (n === 2) return two
        var tail = n % 100
        if (tail >= 3 && tail <= 10) return win.countText(n) + " " + few
        if (tail >= 11 && tail <= 99) return win.countText(n) + " " + many
        return win.countText(n) + " " + other
    }

    function appsCountText(n) {
        if (!win.rtl) return n === 1 ? "1 app" : win.countText(n) + " apps"
        if (n === 0) return "لا تطبيقات"
        return win.arabicCount(n, "تطبيق واحد", "تطبيقان", "تطبيقات", "تطبيقًا", "تطبيق")
    }

    function componentsCountText(n) {
        if (!win.rtl) return n === 1 ? "1 shared component" : win.countText(n) + " shared components"
        return win.arabicCount(n, "مكوّن مشترك واحد", "مكوّنان مشتركان", "مكوّنات مشتركة", "مكوّنًا مشتركًا", "مكوّن مشترك")
    }

    function updatesCountText(n) {
        if (!win.rtl) return n === 1 ? "1 update" : win.countText(n) + " updates"
        return win.arabicCount(n, "تحديث واحد", "تحديثان", "تحديثات", "تحديثًا", "تحديث")
    }

    readonly property var monthsAr: ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو",
                                     "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
    readonly property var monthsEn: ["January", "February", "March", "April", "May", "June", "July",
                                     "August", "September", "October", "November", "December"]
    function dateText(value) {
        var m = /^(\d{4})-(\d{2})-(\d{2})/.exec("" + (value || ""))
        if (!m) return ""
        var month = parseInt(m[2], 10) - 1
        if (month < 0 || month > 11) return ""
        var day = parseInt(m[3], 10)
        return win.rtl ? day + " " + win.monthsAr[month] + " " + m[1]
                       : day + " " + win.monthsEn[month] + " " + m[1]
    }

    function agoText(value) {
        var at = Date.parse(value || "")
        if (!isFinite(at)) return ""
        var seconds = Math.max(0, (Date.now() - at) / 1000)
        if (seconds < 60) return win.local("الآن", "just now")
        var minutes = Math.floor(seconds / 60)
        if (minutes < 60)
            return win.rtl ? "منذ " + win.arabicCount(minutes, "دقيقة", "دقيقتين", "دقائق", "دقيقة", "دقيقة")
                           : minutes + (minutes === 1 ? " minute ago" : " minutes ago")
        var hours = Math.floor(minutes / 60)
        if (hours < 24)
            return win.rtl ? "منذ " + win.arabicCount(hours, "ساعة", "ساعتين", "ساعات", "ساعة", "ساعة")
                           : hours + (hours === 1 ? " hour ago" : " hours ago")
        var days = Math.floor(hours / 24)
        return win.rtl ? "منذ " + win.arabicCount(days, "يوم", "يومين", "أيام", "يومًا", "يوم")
                       : days + (days === 1 ? " day ago" : " days ago")
    }

    function sizeText(bytes) {
        var n = Number(bytes || 0)
        if (!(n > 0)) return ""
        var units = win.rtl ? ["بايت", "كيلوبايت", "ميغابايت", "غيغابايت"] : ["B", "KB", "MB", "GB"]
        var step = 0
        while (n >= 1000 && step < units.length - 1) { n /= 1000; ++step }
        var shown = n >= 10 || step === 0 ? Math.round(n) : Math.round(n * 10) / 10
        return shown + " " + units[step]
    }

    // ── kinds, categories and names ─────────────────────────────────────────────
    function appKind(app) {
        if (!app) return ""
        var kind = app.kind ? "" + app.kind : (app.install && app.install.kind ? "" + app.install.kind : "")
        if (kind === "windows-portable") return "windows"
        if (kind === "vendor-rpm") return "vendor"
        if (kind === "appimage") return "appdrop"
        if (kind !== "") return kind
        return app.source === "local" ? "dropped" : "flatpak"
    }

    // The four places an app comes from, as the person sees them.
    function kindFamily(kind) {
        if (kind === "webapp" || kind === "web") return "web"
        if (kind === "windows") return "windows"
        if (kind === "android") return "android"
        return "linux"
    }

    function kindDef(id) {
        for (var i = 0; i < win.kindDefs.length; ++i)
            if (win.kindDefs[i].id === id) return win.kindDefs[i]
        return null
    }

    function kindLabel(kind) {
        switch (kind) {
        case "webapp":  return win.local("تطبيق ويب", "Web app")
        case "web":     return win.local("موقع الناشر", "Publisher's website")
        case "windows": return win.local("برنامج ويندوز", "Windows program")
        case "android": return win.local("تطبيق أندرويد", "Android app")
        case "appdrop":
        case "vendor":  return win.local("من موقع الناشر", "From the publisher's website")
        case "npm":     return win.local("أداة مطوّر", "Developer tool")
        case "dropped": return win.local("أُضيف من ملف", "Added from a file")
        default:        return win.local("تطبيق لينكس", "Linux app")
        }
    }

    function kindGlyph(kind) {
        switch (kind) {
        case "webapp":
        case "web":     return "globe"
        case "windows": return "system"
        case "android": return "phone"
        case "appdrop":
        case "vendor":  return "download"
        case "npm":     return "terminal"
        case "dropped": return "folder"
        default:        return "cube"
        }
    }

    function catDef(id) {
        for (var i = 0; i < win.storeCategories.length; ++i)
            if (win.storeCategories[i].id === id) return win.storeCategories[i]
        for (var j = 0; j < win.storeCategoryDefs.length; ++j)
            if (win.storeCategoryDefs[j].id === id) return win.storeCategoryDefs[j]
        return null
    }

    function storeCat(app) {
        var family = win.kindFamily(win.appKind(app))
        if (family === "android") return "droid"
        if (family === "windows") return "win"
        for (var j = 0; j < win.storeCategoryDefs.length; ++j)
            if (win.storeCategoryDefs[j].id === app.cat) return app.cat
        return win.legacyCategory[app.category] || "util"
    }

    function categoryName(id) {
        if (id === "all") return win.local("الكل", "All")
        var def = win.catDef(id)
        return def ? win.localName(def) : id
    }

    function categoryGlyph(id) {
        var def = win.catDef(id)
        return def ? def.glyph : "grid"
    }

    // The search key, folded exactly as moos-store-index folds `search`: lowercase; Arabic marks,
    // the tatweel and the invisible direction marks removed; the alef forms, ى/ئ, ؤ and ة
    // unified; Arabic and Persian digits made ASCII; separators made one space.
    function foldSearch(value) {
        var text = ("" + (value || "")).toLowerCase()
        text = text.replace(/[ؐ-ًؚ-ٰٟۖ-ۭـ​-‏‪-‮⁦-⁩؜﻿]/g, "")
        text = text.replace(/[أإآٱ]/g, "ا").replace(/[ىئ]/g, "ي").replace(/ؤ/g, "و").replace(/ة/g, "ه")
        text = text.replace(/[٠-٩]/g, function(c) { return String(c.charCodeAt(0) - 0x0660) })
        text = text.replace(/[۰-۹]/g, function(c) { return String(c.charCodeAt(0) - 0x06F0) })
        return text.replace(/[\s_.\-+/()|·]+/g, " ").trim()
    }

    function idTail(id) {
        var text = "" + (id || "")
        var dot = text.lastIndexOf(".")
        return dot > 0 ? text.substring(dot + 1) : text
    }

    // One index entry, made whole for the window: its kind and family, its Store category, an
    // English name and a search key even when an older index did not write them, and the
    // catalogue's own picture and colour for a curated app the index carried without them.
    function normalizeApp(app) {
        app.kind = win.appKind(app)
        app.family = win.kindFamily(app.kind)
        app.cat = win.storeCat(app)
        if (!app.name_en) app.name_en = app.en || app.name || app.id
        if (app.listed === undefined) app.listed = true
        var curated = win.curatedMap[app.id]
        if (curated && curated !== app) {
            if (!app.icon_url && curated.icon_url) app.icon_url = curated.icon_url
            if (!app.accent && curated.accent) app.accent = curated.accent
            if (!app.developer && curated.developer) app.developer = curated.developer
            if (!app.keywords_en && curated.keywords_en) app.keywords_en = curated.keywords_en
            if (!app.keywords_ar && curated.keywords_ar) app.keywords_ar = curated.keywords_ar
            if (app.popular === undefined && curated.popular !== undefined) app.popular = curated.popular
        }
        if (typeof app.search !== "string") {
            app.search = win.foldSearch([app.name, app.name_en, app.en, app.ar, app.developer,
                                         win.idTail(app.id)].concat(app.keywords_en || [])
                                        .concat(app.keywords_ar || []).join(" "))
        }
        return app
    }

    // ── colour of an app ────────────────────────────────────────────────────────
    function parseColour(value) {
        return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value)
            ? Qt.lighter(value, 1) : null
    }

    function hashOf(text) {
        var h = 2166136261
        var s = "" + (text || "")
        for (var i = 0; i < s.length; ++i) {
            h ^= s.charCodeAt(i)
            h = (h * 16777619) >>> 0
        }
        return h
    }

    // A stable colour from the id, for an app that names none: every hue is possible, at the
    // saturation and lightness the scheme's own accent sits at, so a wall of monograms reads as
    // one family rather than confetti.
    function idColour(id) {
        var hue = (win.hashOf(id) % 360) / 360
        return Qt.hsla(hue, 0.52, win.lightScheme ? 0.40 : 0.46, 1)
    }

    // The app's own colour for the active scheme: its branding, then the catalogue's accent, then
    // a stable hue from its id.
    function appColour(app) {
        if (!app) return win.accent
        var branding = app.branding
        var colour = branding ? win.parseColour(win.lightScheme ? branding.light : branding.dark) : null
        if (!colour && branding) colour = win.parseColour(win.lightScheme ? branding.dark : branding.light)
        if (!colour) colour = win.parseColour(app.accent || (app.install && app.install.accent))
        return colour || win.idColour(app.id)
    }

    // One letter (or a number) for a monogram: the first of the app's English name, which is
    // the name its own mark uses.
    function initialOf(app) {
        var name = "" + ((app && (app.name_en || app.en || app.name)) || (app && app.id) || "?")
        // QML's engine has no \p{L}: skip spaces and punctuation, keep the first letter or digit.
        var match = /[^\s\-_.:;,'"()\[\]{}+&|!?@#$%^*=<>\/\\~`«»“”]/.exec(name)
        return match ? match[0].toUpperCase() : "?"
    }

    // ── compatibility, in this window's own words ───────────────────────────────
    //
    // `not_verified` is about WHO published an app, not whether it runs here, so it is said in the
    // safety words and never turns "Works on this PC" into "Works with limits".
    //
    // Three reasons are facts about an app rather than limits of this computer: a web app needs the
    // internet, a publisher may be unverified, a download may come from its publisher. They are
    // said on the app's page as notes, and never paint a warning on its card.
    readonly property var informationalReasons: ["not_verified", "needs_internet", "vendor_download"]

    function compatOf(app) {
        var c = app && app.compat ? app.compat : null
        if (!c) return { known: false, verdict: "ok", reasons: [], notes: [] }
        var limits = []
        var notes = []
        var reasons = c.reasons || []
        for (var i = 0; i < reasons.length; ++i) {
            if (win.informationalReasons.indexOf(reasons[i]) >= 0) {
                if (reasons[i] !== "not_verified") notes.push(reasons[i])
            } else {
                limits.push(reasons[i])
            }
        }
        var verdict = c.verdict === "blocked" ? "blocked" : limits.length > 0 ? "warn" : "ok"
        return { known: true, verdict: verdict, reasons: limits, notes: notes }
    }

    function compatTitle(verdict) {
        if (verdict === "blocked") return win.local("غير متاح هنا", "Not available here")
        if (verdict === "warn") return win.local("يعمل مع بعض القيود", "Works with limits")
        return win.local("يعمل على هذا الجهاز", "Works on this PC")
    }

    readonly property var compatPhrases: ({
        "arch":                      ["لم يُصنع لهذا النوع من الحواسيب", "Not made for this kind of computer"],
        "engine_missing":            ["يحتاج جزءًا لا يتضمنه هذا الإصدار من MoOS", "Needs a part this edition of MoOS does not include"],
        "android_setup":             ["تحتاج تطبيقات أندرويد إلى إعداد لمرة واحدة أولًا", "Android apps need a one-time setup first"],
        "android_software_graphics": ["تعمل تطبيقات أندرويد هنا دون تسريع رسومي، فقد تبطؤ الألعاب", "Android apps draw without graphics acceleration here, so games may be slow"],
        "low_disk":                  ["قد لا تكفي المساحة الفارغة", "There may not be enough free space"],
        "low_memory":                ["قد يبطؤ مع ذاكرة هذا الجهاز", "May be slow with this computer's memory"],
        "small_screen":              ["مصمم لشاشة أكبر", "Designed for a larger screen"],
        "needs_internet":            ["يحتاج اتصالًا بالإنترنت", "Needs an internet connection"],
        "x11_only_scaled":           ["قد يبدو غير حاد على هذه الشاشة عالية الدقة", "May look soft on this high-resolution screen"],
        "eol":                       ["توقف مطوّره عن تحديثه", "Its developer no longer updates it"],
        "broad_permissions":         ["يطلب وصولًا واسعًا إلى ملفاتك أو أجهزتك", "Asks for wide access to your files or devices"],
        "vendor_download":           ["يُنزَّل من الناشر ويعمل خارج العزل", "Downloaded from the publisher; runs outside the sandbox"],
        "not_verified":              ["ناشره غير موثّق", "Its publisher is not verified"]
    })

    function compatReasonText(key) {
        var phrase = win.compatPhrases[key]
        return phrase ? (win.rtl ? phrase[0] : phrase[1]) : ""
    }

    // ── safety and permissions ──────────────────────────────────────────────────
    readonly property var permissionPhrases: ({
        "network":       ["الإنترنت", "Internet", "يتصل بالإنترنت", "Connects to the internet", "network"],
        "files-home":    ["مجلد المنزل", "Home folder", "يقرأ ملفات مجلد المنزل ويكتبها", "Reads and writes the files in your home folder", "home"],
        "files-all":     ["كل الملفات", "All files", "يصل إلى كل ملفاتك وإلى ملفات النظام", "Reaches all your files and the system's", "folder"],
        "downloads":     ["التنزيلات", "Downloads", "يصل إلى مجلد التنزيلات", "Reaches your Downloads folder", "download"],
        "devices":       ["الأجهزة", "Devices", "يستخدم الكاميرات وUSB والأجهزة الأخرى", "Uses cameras, USB and other devices", "usb"],
        "sound":         ["الصوت والميكروفون", "Sound and microphone", "يشغّل الصوت ويستطيع استخدام الميكروفون", "Plays sound and can use the microphone", "audio"],
        "bluetooth":     ["البلوتوث", "Bluetooth", "يتحدث إلى أجهزة البلوتوث", "Talks to Bluetooth devices", "bluetooth"],
        "background":    ["العمل في الخلفية", "Background", "يواصل العمل بعد إغلاق نافذته", "Keeps working after its window closes", "moon"],
        "host-commands": ["أوامر خارج العزل", "Commands outside", "يستطيع تشغيل أوامر خارج عزله", "Can run commands outside its sandbox", "terminal"],
        "notifications": ["الإشعارات", "Notifications", "يعرض إشعارات على سطح المكتب", "Shows notifications on your desktop", "notification"],
        "microphone":    ["الميكروفون", "Microphone", "يسمع عبر الميكروفون", "Listens through the microphone", "microphone"],
        "camera":        ["الكاميرا", "Camera", "يرى عبر الكاميرا", "Sees through the camera", "camera"],
        "location":      ["الموقع", "Location", "يعرف موقعك التقريبي", "Knows your approximate location", "pin"],
        "clipboard":     ["الحافظة", "Clipboard", "يقرأ ما تنسخه ويكتب فيه", "Reads and writes what you copy", "copy"],
        "screen":        ["الشاشة", "Screen", "يشارك شاشتك عندما تسمح", "Shares your screen when you allow it", "cast"]
    })

    function permissionTitle(key) {
        var p = win.permissionPhrases[key]
        return p ? (win.rtl ? p[0] : p[1]) : key
    }

    function permissionLine(key) {
        var p = win.permissionPhrases[key]
        return p ? (win.rtl ? p[2] : p[3]) : ""
    }

    function permissionGlyph(key) {
        var p = win.permissionPhrases[key]
        return p ? p[4] : "lock"
    }

    // What an app may do, as words a person reads: the installed app's own document when it is
    // open, the catalogue facts before it is installed. Each row: {key, allowed, changeable, ask}.
    function permissionRowsFor(app) {
        if (!app) return []
        var doc = win.permissionDoc
        if (doc && doc.id === app.id && doc.rows && doc.rows.length) {
            var rows = []
            for (var i = 0; i < doc.rows.length; ++i)
                rows.push({ key: doc.rows[i].key, allowed: doc.rows[i].state === "allow",
                            changeable: doc.rows[i].changeable === true, ask: doc.rows[i].ask === true })
            return rows
        }
        var kind = win.appKind(app)
        if (kind === "webapp") {
            var asked = (app.install && app.install.permissions) || []
            var webRows = []
            for (var w = 0; w < asked.length; ++w)
                webRows.push({ key: asked[w], allowed: false, changeable: false, ask: true })
            return webRows
        }
        var fact = win.facts[app.id]
        if (kind === "flatpak" && fact && fact.permissions) {
            var factRows = []
            for (var f = 0; f < fact.permissions.length; ++f)
                factRows.push({ key: fact.permissions[f], allowed: false, changeable: false, ask: false, requested: true })
            return factRows
        }
        return []
    }

    // One word for how far an app reaches: "sandboxed", "more" (a sandboxed app that asks for wide
    // access) or "full" (it runs as the person and sees every file), said plainly.
    function safetyLevel(app) {
        var kind = win.appKind(app)
        if (kind === "appdrop" || kind === "windows" || kind === "npm" || kind === "vendor"
                || kind === "dropped") return "full"
        if (kind === "web") return "page"
        if (kind === "webapp" || kind === "android") return "sandboxed"
        var rows = win.permissionRowsFor(app)
        for (var i = 0; i < rows.length; ++i)
            if (rows[i].allowed && ["files-all", "files-home", "devices", "host-commands"].indexOf(rows[i].key) >= 0)
                return "more"
        return "sandboxed"
    }

    function safetyTitle(app) {
        var level = win.safetyLevel(app)
        if (level === "full") return win.local("وصول كامل", "Full access")
        if (level === "more") return win.local("يطلب صلاحيات أوسع", "Asks for more")
        if (level === "page") return win.local("يفتح صفحة الناشر", "Opens the publisher's page")
        if (win.appKind(app) === "webapp") return win.local("معزول في نافذته الخاصة", "Sandboxed in its own window")
        if (win.appKind(app) === "android") return win.local("معزول في مساحة أندرويد", "Sandboxed in the Android space")
        return win.local("معزول", "Sandboxed")
    }

    function safetyLine(app) {
        var level = win.safetyLevel(app)
        if (level === "full")
            return win.local("يعمل باسمك ويستطيع رؤية كل ملفاتك، فثبّته فقط إن كنت تثق بناشره.",
                             "It runs as you and can see all your files, so install it only if you trust its publisher.")
        if (level === "more")
            return win.local("يعمل في عزله، لكنه يطلب الوصول إلى أشياء خارجه.",
                             "It runs in its own sandbox, but asks to reach things outside it.")
        if (level === "page")
            return win.local("لا يُثبَّت شيء: يفتح متجر Mo صفحة الناشر الرسمية فقط.",
                             "Nothing is installed: Mo Store only opens the publisher's official page.")
        if (win.appKind(app) === "webapp")
            return win.local("يعمل في نافذة منفصلة عن متصفحك، ويسألك قبل الكاميرا والميكروفون.",
                             "It runs in a window apart from your browser and asks before the camera or microphone.")
        if (win.appKind(app) === "android")
            return win.local("يدير أندرويد أذوناته داخل مساحته الخاصة.",
                             "Android manages its permissions inside its own space.")
        return win.local("يعمل في عزله الخاص ولا يرى إلا ما سُمح له به.",
                         "It runs in its own sandbox and sees only what it is allowed to.")
    }

    // The page's words for a permissions document's note.
    function permissionNoteText(key) {
        if (key === "full_access")
            return win.local("هذا التطبيق يعمل باسمك دون عزل، فلا توجد مفاتيح لتغييرها: يستطيع رؤية كل ملفاتك.",
                             "This app runs as you without a sandbox, so there are no switches to change: it can see all your files.")
        if (key === "android_managed")
            return win.local("أذونات تطبيقات أندرويد تُدار من إعدادات أندرويد داخل مساحته.",
                             "An Android app's permissions are managed in Android's own settings, inside its space.")
        if (key === "not_installed")
            return win.local("ثبّت التطبيق أولًا لتغيير أذوناته.", "Install the app first to change its permissions.")
        return ""
    }

    // Free when the licence names one, proprietary when it says so, unknown otherwise.
    function licenceKind(app) {
        var text = "" + ((app && app.license) || (win.selectedDetails && win.selectedDetails.license) || "")
        if (text === "") return "unknown"
        if (/proprietary|licenseref/i.test(text)) return "proprietary"
        return "free"
    }

    function contentRatingText(rating) {
        if (rating === "all") return win.local("للجميع", "Everyone")
        if (rating === "teen") return win.local("للمراهقين فما فوق", "Teens and up")
        if (rating === "mature") return win.local("للبالغين", "Adults only")
        return win.local("غير مصنّف", "Not rated")
    }

    // Who made an app, in the line under its name.
    function publisherLine(app) {
        if (!app) return ""
        var kind = win.appKind(app)
        if (kind === "dropped") return win.kindLabel(kind)
        var who = app.developer ? "" + app.developer : ""
        if (kind === "flatpak") return who !== "" ? who : win.kindLabel(kind)
        return who !== "" ? who + " · " + win.kindLabel(kind) : win.kindLabel(kind)
    }

    // The badge on every card. It used to print the CHANNEL an app arrives
    // through -- "flathub" on all 3,343 of them, "npm" on the developer tools --
    // and the owner's rule covers that too: he named F-Droid alongside KWin and
    // Wayland as things he must never see. A channel is machinery.
    //
    // What the badge is FOR is not lost, because the thing a person actually
    // needs before installing is WHO MADE IT, and the card already prints that
    // on its own line. So the default trusted channel goes unnamed and the badge
    // says that the app is verified ONLY when it is -- and an app arriving from
    // anywhere ELSE names where it comes from, because an unusual source is
    // exactly the thing worth reading.
    function sourceLabel(app) {
        if (!app) return ""
        var kind = win.appKind(app)
        if (kind === "flatpak") {
            if (app.origin && app.origin !== "" && app.origin !== "flathub" && app.origin !== "flatpak")
                return app.origin
            return app.verified === true ? (win.rtl ? "موثّق" : "Verified") : win.kindLabel(kind)
        }
        if (app.install && app.install.kind === "npm")
            return win.rtl ? "أداة مطوّر" : "Developer tool"
        if (app.install && app.install.kind === "web")
            return win.rtl ? "موقع الناشر" : "Publisher's website"
        return win.kindLabel(kind)
    }

    function reviewDetail(app) {
        if (!app) return ""
        var kind = win.appKind(app)
        var detail = win.sourceLabel(app)
        if (app.install && app.install.kind === "npm") {
            if (app.install.pkg) detail += " · " + app.install.pkg
            if (app.install.risk)
                detail += " · " + (win.rtl ? "يشغّل سكربتات الحزمة" : "runs package scripts")
        } else if (kind === "appdrop" || kind === "windows") {
            detail += " · " + (win.rtl ? "ملف موثّق" : "Verified file")
            if (app.install && app.install.version) detail += " " + app.install.version
            detail += " · SHA-256 · " + (win.rtl ? "خارج العزل" : "outside the sandbox")
        } else if (kind === "vendor") {
            // The newest build from the publisher's own repository, accepted only when the key MoOS
            // trusts for that publisher signed it.
            detail += " · " + (win.rtl ? "موقّع بمفتاح ناشره" : "signed with its publisher's key")
                    + " · " + (win.rtl ? "خارج العزل" : "outside the sandbox")
        } else if (kind === "webapp") {
            detail += " · " + (win.rtl ? "في نافذته الخاصة" : "in a window of its own")
        } else if (kind === "android") {
            detail += " · " + (win.rtl ? "ملف موثّق" : "Verified file")
        }
        return detail
    }

    // ── state of one app ────────────────────────────────────────────────────────
    function isInstalled(app) {
        if (!app) return false
        if (win.installedOverrides[app.id] !== undefined)
            return win.installedOverrides[app.id] === true
        return app.installed === true
    }

    function isWeb(app) {
        return app && app.install && app.install.kind === "web"
    }

    function pickedWebCount() {
        var ids = Object.keys(win.picks)
        var count = 0
        for (var i = 0; i < ids.length; ++i)
            if (win.isWeb(win.appById(ids[i]))) ++count
        return count
    }

    function onlyWebPicks() {
        return win.pickCount > 0 && win.pickedWebCount() === win.pickCount
    }

    function hasFlatpakLifecycle(app) {
        return app && (app.source === "flatpak"
                       || app.source === "flathub"
                       || (app.flatpak_ref && app.flatpak_ref !== ""))
    }

    function hasAndroidLifecycle(app) {
        return app && app.install && app.install.kind === "android"
            || app && app.kind === "android"
    }

    // What moos-storectl can open by id (`run`): Flatpaks, Android apps, web apps, App Drop apps
    // (catalogue and dropped) and Windows programs. npm tools run from a terminal, and a
    // publisher's page has nothing to open.
    function hasRunnableLifecycle(app) {
        if (!app) return false
        if (win.hasFlatpakLifecycle(app) || win.hasAndroidLifecycle(app)) return true
        var kind = win.appKind(app)
        return kind === "webapp" || kind === "appdrop" || kind === "windows" || kind === "dropped"
    }

    function hasInstalledScope(app, scope) {
        if (!app) return false
        if (win.installedScopeOverrides[app.id] !== undefined)
            return win.installedScopeOverrides[app.id].indexOf(scope) >= 0
        if (app.installed_scopes && app.installed_scopes.indexOf(scope) >= 0)
            return true
        return app.installed_scope === scope
    }

    // Everything moos-storectl installs into the person's home that is not a Flatpak — npm tools,
    // App Drop and Windows programs, web apps, Android apps and a file the person dropped — is
    // removed by `moos-storectl remove <id>`. A `web` entry only opened a publisher's page:
    // nothing of ours is on disk, and it is deliberately excluded.
    function hasCuratedLifecycle(app) {
        var kind = win.appKind(app)
        return app && (kind === "npm" || kind === "appdrop" || kind === "android"
                       || kind === "webapp" || kind === "windows" || kind === "dropped")
    }

    function canRemove(app) {
        if (!win.isInstalled(app))
            return false
        // Curated tools are always user-scoped, so their Remove is always valid.
        if (win.hasCuratedLifecycle(app))
            return true
        if (!win.hasFlatpakLifecycle(app))
            return false
        // A live transaction result outranks stale/legacy catalogue metadata.
        // In particular ["system"] is conclusive: do not fall through to the
        // no-scope fallback and expose a Remove action the backend must refuse.
        if (win.installedScopeOverrides[app.id] !== undefined)
            return win.installedScopeOverrides[app.id].indexOf("user") >= 0
        if (app.installed_scopes)
            return app.installed_scopes.indexOf("user") >= 0
        return app.installed_scope !== "system"
    }

    function systemManagedOnly(app) {
        return win.isInstalled(app)
            && win.hasFlatpakLifecycle(app)
            && win.hasInstalledScope(app, "system")
            && !win.hasInstalledScope(app, "user")
    }

    // Permissions the Store can change: a Flatpak's and a web app's, once installed.
    function canChangePermissions(app) {
        var kind = win.appKind(app)
        return win.isInstalled(app) && (kind === "flatpak" || kind === "webapp")
    }

    // ── the selection (one review installs a whole set) ─────────────────────────
    function isPicked(id) {
        return win.picks[id] === true
    }

    function setPicked(id, on) {
        if (on && !win.isPicked(id) && win.pickCount >= 64) {
            win.flash(win.rtl ? "الحد الأقصى 64 تطبيقًا لكل عملية" : "Up to 64 apps per operation")
            return
        }
        var next = Object.assign({}, win.picks)
        if (on) next[id] = true
        else delete next[id]
        win.picks = next
        win.pickCount = Object.keys(next).length
    }

    function togglePicked(id) {
        win.setPicked(id, !win.isPicked(id))
    }

    function addMany(ids) {
        var next = Object.assign({}, win.picks)
        var added = 0
        var selected = Object.keys(next).length
        for (var i = 0; i < ids.length && selected < 64; ++i) {
            var app = win.appById(ids[i])
            if (app && !win.isInstalled(app) && !next[ids[i]]
                    && win.compatOf(app).verdict !== "blocked") {
                next[ids[i]] = true
                ++added
                ++selected
            }
        }
        win.picks = next
        win.pickCount = Object.keys(next).length
        win.flash(added > 0
            ? (win.rtl ? "أُضيف إلى قائمة التثبيت: " : "Added to the install list: ") + added
            : win.local("كل تطبيقات هذه المجموعة مثبّتة أو مضافة", "Every app in this set is already installed or added"))
    }

    function clearPicks() {
        win.picks = ({})
        win.pickCount = 0
    }

    function appById(id) {
        return win.appMap[id] || null
    }

    function appsByIds(ids) {
        var out = []
        for (var i = 0; i < (ids || []).length; ++i) {
            var app = win.appById(ids[i])
            if (app) out.push(app)
        }
        return out
    }

    function categoryCount(id) {
        return win.catCounts[id] || 0
    }

    function installedCount() {
        return win.installedApps.length
    }

    function verifiedCount() {
        if (win.indexStats.verified_apps !== undefined) return win.indexStats.verified_apps
        var count = 0
        for (var i = 0; i < win.allApps.length; ++i)
            if (win.allApps[i].verified === true) ++count
        return count
    }

    function hasFlatpakCatalog() {
        if (!win.indexReady || !(win.indexStats.appstream_components > 0))
            return false
        for (var i = 0; i < win.indexSources.length; ++i)
            if (win.indexSources[i].kind === "flatpak-appstream"
                    && !win.indexSources[i].error)
                return true
        return false
    }

    function maybeRefreshCatalog(force) {
        if (win.hasFlatpakCatalog()) return
        if (!force && win.catalogRefreshRequested) return
        if (!win.indexReady || win.jobIsActive() || win.waitingForJob) return
        if (typeof MoosStore === "undefined") return
        win.catalogRefreshRequested = true
        win.expectJob("refresh-index", ["flathub"])
        if (!MoosStore.refreshIndex()) {
            win.waitingForJob = false
            win.flash(win.rtl
                ? "تعذّر بدء تحديث فهرس التطبيقات"
                : "Could not start catalogue refresh")
            return
        }
        jobPoll.restart()
    }

    // MoOS picks are editorial: the catalogue's popular apps first, then the rest
    // of the curated catalogue, both in catalog.json's own order. Taking the first
    // curated apps of the store-wide alphabetical list made the row "Alpaca,
    // Android Studio, Anki, Antigravity…" and ignored the popular flag entirely
    // (captured on the daily driver, plan M1.4). Live index entries are preferred
    // so installed state and icons stay current.
    function curatedFeatured(limit) {
        var live = win.appMap
        var ranked = []
        for (var j = 0; j < win.curatedApps.length; ++j) {
            var entry = live[win.curatedApps[j].id] || win.curatedApps[j]
            if (entry.listed === false) continue
            var popular = entry.popular === true || win.curatedApps[j].popular === true
            ranked.push({ app: entry, rank: popular ? 0 : 1, order: j })
        }
        ranked.sort(function(a, b) { return a.rank - b.rank || a.order - b.order })
        var out = []
        for (var k = 0; k < ranked.length && out.length < limit; ++k)
            out.push(ranked[k].app)
        return out
    }

    function jobItem(id) {
        var items = win.job.items || []
        for (var i = 0; i < items.length; ++i)
            if (items[i].id === id) return items[i]
        return null
    }

    function jobIsActive() {
        return win.waitingForJob
            || win.job.state === "starting"
            || win.job.state === "running"
    }

    function jobIsTerminal() {
        return win.job.state === "success"
            || win.job.state === "partial"
            || win.job.state === "failed"
            || win.job.state === "cancelled"
            || win.job.state === "busy"
    }

    // Where one app stands in the running job, for the button on its card and its page:
    // "" (not in it), "waiting", "running" (with a real percentage or none) or "starting".
    function appJobState(app) {
        if (!app) return ""
        if (win.waitingForJob && win.expectedIds.indexOf(app.id) >= 0) return "starting"
        if (!(win.job.state === "starting" || win.job.state === "running")) return ""
        var item = win.jobItem(app.id)
        if (!item) return ""
        if (item.state === "queued") return "waiting"
        if (item.state === "running" || item.state === "starting") return "running"
        return ""
    }

    function appJobProgress(app) {
        var item = app ? win.jobItem(app.id) : null
        if (item && item.progress !== null && item.progress !== undefined) return item.progress
        if (win.job.current_id === (app && app.id) && win.job.progress !== null
                && win.job.progress !== undefined) return win.job.progress
        return -1
    }

    function flash(message) {
        toast.show(message)
    }

    function readJson(path) {
        if (!path || path === "") return null
        var request = new XMLHttpRequest()
        request.open("GET", "file://" + path + "?v=" + Date.now(), false)
        request.send()
        if (!request.responseText) return null
        return JSON.parse(request.responseText)
    }

    // The same read, off the first frame: big documents (facts, an app's details) are parsed when
    // they arrive, and `done` receives the parsed document or null.
    function readJsonLater(path, done) {
        if (!path || path === "") { done(null); return }
        var request = new XMLHttpRequest()
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE) return
            var parsed = null
            try { parsed = request.responseText ? JSON.parse(request.responseText) : null }
            catch (error) { parsed = null }
            done(parsed)
        }
        request.open("GET", "file://" + path + "?v=" + Date.now())
        request.send()
    }

    // ── What MoOS can run ────────────────────────────────────────────────────
    //
    // A person who wants to run a program they downloaded has no reason to learn
    // what the engine behind it is called. The promise is stated as a capability,
    // in the registry's own bilingual words, and choosing one opens the file picker
    // for exactly the files that capability accepts.
    //
    // The registry is the single source (system_files/usr/share/moos/app-engines.json).
    // Nothing here can name a runtime, because nothing here invents a string.
    property var engineCapabilities: []
    // Engine ids the index probed as usable here; null until the index is read,
    // and null again if it could not tell. Never [] for "none" -- see loadEngines.
    property var indexEngines: null
    // This machine's Flatpak arch, or "" when unknown. Same rule as indexEngines:
    // unknown filters nothing.
    property string machineArch: ""

    // Written by the launcher before the first frame (moos-store --print-machine).
    function loadMachine() {
        try {
            if (!win.machinePath) return
            var document = win.readJson(win.machinePath)
            if (!document) return
            win.machine = document
            win.machineArch = "" + (document.arch || "")
            win.indexEngines = (document.engines === null
                                || document.engines === undefined)
                               ? null : document.engines
        } catch (error) {
            win.machineArch = ""
            win.indexEngines = null
        }
    }

    // Can this machine install the curated entry at all? Mirrors
    // moos-store-index: an entry naming architectures exists on those and
    // nowhere else, and one naming an engine needs a runtime for it. Anything
    // unknown filters nothing -- an empty store is the worse failure.
    function curatedRunsHere(entry) {
        if (!entry) return false
        var arches = entry.arch
        if (win.machineArch && arches && arches.length
                && arches.indexOf(win.machineArch) < 0) return false
        var engine = entry.engine
                     || ((entry.install && entry.install.kind === "android")
                         ? "android" : "")
        if (engine && win.indexEngines !== null && win.indexEngines !== undefined
                && win.indexEngines.indexOf("" + engine) < 0) return false
        return true
    }

    function loadEngines() {
        try {
            var document = win.readJson("/usr/share/moos/app-engines.json")
            if (!document || !document.engines) return
            // The registry DESCRIBES every engine MoOS knows; it does not say
            // which ones THIS machine has a runtime for. The index probes that
            // (app-engines.json's own `probe` field) and writes the answer as
            // `engines`. Without this filter an ARM desktop -- which ships
            // neither runtime -- told the owner it runs Windows programs and
            // Android apps, and the picker it opened could only ever fail. A
            // missing or null list means "could not tell", and the list then
            // shows everything exactly as it did before.
            var ready = win.indexEngines
            var list = []
            for (var i = 0; i < document.engines.length; ++i) {
                var engine = document.engines[i]
                if (!engine || !engine.name) continue
                if (ready !== null && ready !== undefined
                        && ready.indexOf("" + engine.id) < 0) continue
                var claims = engine.claims || {}
                list.push({
                    "id": "" + engine.id,
                    "label": "" + (win.rtl ? engine.name.ar : engine.name.en),
                    "extensions": claims.extensions || []
                })
            }
            win.engineCapabilities = list
        } catch (error) {
            // A store that cannot read the registry simply does not show the
            // list. It must never invent a capability it cannot name.
            win.engineCapabilities = []
        }
    }

    function openPickerFor(capability) {
        var patterns = []
        for (var i = 0; i < capability.extensions.length; ++i)
            patterns.push("*." + capability.extensions[i])
        applicationFile.nameFilters = patterns.length > 0
            ? [capability.label + " (" + patterns.join(" ") + ")"]
            : []
        applicationFile.open()
    }

    // The header's and Settings' "Add an app from a file" open the same picker.
    function openApplicationPicker() {
        applicationFile.nameFilters = []
        applicationFile.open()
    }

    function loadCurated() {
        try {
            var request = new XMLHttpRequest()
            request.open("GET", "file:///usr/share/moos/store/catalog.json", false)
            request.send()
            var document = JSON.parse(request.responseText)
            var apps = document.apps || []
            // Same rule the index applies: a bundle may only name apps this
            // machine is actually offered, and a bundle left with fewer than two
            // members is no longer the set that was curated -- on ARM "Gaming
            // Starter" lost five of its six.
            var offered = {}
            for (var a = 0; a < apps.length; ++a)
                if (win.curatedRunsHere(apps[a])) offered["" + apps[a].id] = true
            var keptBundles = []
            var rawBundles = document.bundles || []
            for (var b = 0; b < rawBundles.length; ++b) {
                var bundle = Object.assign({}, rawBundles[b])
                var members = bundle.apps || []
                var kept = []
                for (var m = 0; m < members.length; ++m)
                    if (offered["" + members[m]]) kept.push(members[m])
                bundle.apps = kept
                if (kept.length >= 2) keptBundles.push(bundle)
            }
            var normalized = []
            var map = {}
            for (var i = 0; i < apps.length; ++i) {
                if (!win.curatedRunsHere(apps[i])) continue
                var source = Object.assign({}, apps[i])
                source.summary = win.localSummary(source)
                source.description = source.summary
                source.curated = true
                source.installable = true
                source.installed = false
                normalized.push(source)
                map[source.id] = source
            }
            win.curatedMap = map
            win.curatedApps = normalized
            win.loadEngines()
            win.adoptCatalogue(normalized, {
                bundles: keptBundles,
                categories: document.categories || [],
                collections: document.collections || [],
                featured: document.featured || []
            })
        } catch (error) {
            win.loadError = "" + error
        }
    }

    // Everything the pages read, derived ONCE from one generation of apps: a map by id, the
    // counts by kind and category, the recommended browsing order, the collections and the hero.
    function adoptCatalogue(apps, document) {
        var map = {}
        var kinds = { "linux": 0, "web": 0, "windows": 0, "android": 0 }
        var cats = {}
        var listed = []
        var dated = false
        for (var i = 0; i < apps.length; ++i) {
            var app = win.normalizeApp(apps[i])
            map[app.id] = app
            if (app.released) dated = true
            if (app.listed === false) continue
            kinds[app.family] = (kinds[app.family] || 0) + 1
            cats[app.cat] = (cats[app.cat] || 0) + 1
            listed.push(app)
        }
        listed.sort(function(a, b) {
            return win.recommendScore(a) - win.recommendScore(b)
                || win.localName(a).toLowerCase().localeCompare(win.localName(b).toLowerCase())
        })
        for (var r = 0; r < listed.length; ++r) listed[r]._rank = r
        win.appMap = map
        win.allApps = apps
        win.kindCounts = kinds
        win.catCounts = cats
        win.browseOrder = listed
        win.canSortByDate = dated
        if (!dated && win.sortMode === "updated") win.sortMode = "recommended"
        win.bundles = (document.bundles && document.bundles.length) ? document.bundles : win.bundles
        win.storeCategories = win.resolveCategories(document.categories || [])
        win.collections = win.resolveCollections(document.collections || [])
        win.featured = win.resolveFeatured(document.featured || [])
        win.recompute()
        win.recomputeLibrary()
        if (win.query !== "") win.runSearch()
        if (win.selectedApp) win.selectedApp = win.appById(win.selectedApp.id) || win.selectedApp
    }

    // Curated first (popular, then in the catalogue's order), then verified apps that follow the
    // publishers' quality guide (they name brand colours), then verified, then the rest.
    function recommendScore(app) {
        if (app.curated === true) {
            var order = win.curatedApps.indexOf(win.curatedMap[app.id])
            return (app.popular === true ? 0 : 1000) + Math.max(0, order)
        }
        if (app.verified === true && app.branding) return 10000
        if (app.verified === true) return 20000
        return 30000
    }

    function resolveCategories(named) {
        var out = []
        for (var i = 0; i < win.storeCategoryDefs.length; ++i) {
            var def = win.storeCategoryDefs[i]
            var entry = { id: def.id, ar: def.ar, en: def.en, glyph: def.glyph }
            for (var j = 0; j < named.length; ++j) {
                if (named[j].id !== def.id) continue
                if (named[j].ar) entry.ar = named[j].ar
                if (named[j].en) entry.en = named[j].en
                if (named[j].glyph && def.id !== "droid" && def.id !== "win") entry.glyph = named[j].glyph
            }
            out.push(entry)
        }
        return out
    }

    // The catalogue's editorial rows. An index written before collections existed still gets a
    // Discover worth opening: MoOS's picks, then a row for each category the catalogue fills.
    function resolveCollections(named) {
        var out = []
        for (var i = 0; i < named.length; ++i) {
            var members = []
            var ids = named[i].apps || []
            for (var k = 0; k < ids.length; ++k) {
                var member = win.appById(ids[k])
                if (member && member.listed !== false) members.push(member)
            }
            if (members.length < 3) continue
            out.push({ id: "" + named[i].id, ar: named[i].ar || named[i].en || "", en: named[i].en || named[i].ar || "",
                       desc_ar: named[i].desc_ar || "", desc_en: named[i].desc_en || "",
                       glyph: named[i].glyph || "spark", apps: members })
        }
        if (out.length > 0) return out
        var picks = win.curatedFeatured(16)
        if (picks.length >= 3)
            out.push({ id: "moos-picks", ar: "اختيارات MoOS", en: "MoOS picks",
                       desc_ar: "تطبيقات موثوقة للبدء", desc_en: "Trusted ways to get started",
                       glyph: "star", apps: picks })
        for (var c = 0; c < win.storeCategoryDefs.length; ++c) {
            var def = win.storeCategoryDefs[c]
            var row = []
            for (var a = 0; a < win.browseOrder.length && row.length < 16; ++a)
                if (win.browseOrder[a].cat === def.id) row.push(win.browseOrder[a])
            if (row.length >= 4)
                out.push({ id: "cat-" + def.id, ar: def.ar, en: def.en, desc_ar: "", desc_en: "",
                           glyph: def.glyph, apps: row, category: def.id })
            if (out.length >= 7) break
        }
        return out
    }

    function collectionById(id) {
        for (var i = 0; i < win.collections.length; ++i)
            if (win.collections[i].id === id) return win.collections[i]
        return null
    }

    // The hero: the catalogue's featured cards, or MoOS's popular picks when it names none.
    function resolveFeatured(named) {
        var out = []
        for (var i = 0; i < named.length && out.length < 8; ++i) {
            var app = win.appById(named[i].app)
            if (!app || app.listed === false || win.compatOf(app).verdict === "blocked") continue
            out.push({ app: app, title_ar: named[i].title_ar || "", title_en: named[i].title_en || "",
                       tagline_ar: named[i].tagline_ar || "", tagline_en: named[i].tagline_en || "",
                       accent: named[i].accent || "" })
        }
        if (out.length > 0) return out
        var picks = win.curatedFeatured(5)
        for (var p = 0; p < picks.length; ++p)
            out.push({ app: picks[p], title_ar: "", title_en: "", tagline_ar: "", tagline_en: "", accent: "" })
        return out
    }

    function loadIndex() {
        try {
            var document = win.readJson(win.indexPath)
            if (!document || !document.apps || document.apps.length === 0) return false
            var token = JSON.stringify(document.generation || {})
            if (token === win.indexToken) return true
            win.indexToken = token
            win.indexSources = document.sources || []
            win.indexStats = document.stats || ({})
            win.indexGeneratedAt = (document.generation && document.generation.generated_at) || ""
            win.adoptCatalogue(document.apps, document)
            win.indexReady = true
            win.loadFacts()
            Qt.callLater(function() { win.maybeRefreshCatalog(false) })
            return true
        } catch (error) {
            return false
        }
    }

    function indexBuildReady() {
        if (!win.readyPath || win.readyPath === "") return true
        try {
            var request = new XMLHttpRequest()
            request.open("GET", "file://" + win.readyPath + "?v=" + Date.now(), false)
            request.send()
            return (request.responseText || "").trim() !== ""
        } catch (error) {
            return false
        }
    }

    // Sizes, permission words and end of life of the catalogue's Linux apps, written by
    // `moos-storectl facts` before the index. Read off the first frame.
    function loadFacts() {
        if (!win.factsPath) return
        win.readJsonLater(win.factsPath, function(document) {
            win.facts = document && document.apps ? document.apps : ({})
            win.factsState = document && document.state === "success" ? "ready"
                           : document ? "failed" : "missing"
        })
    }

    function factOf(app) {
        return app ? (win.facts[app.id] || null) : null
    }

    // An app's details document: screenshots, releases, links, languages, licence. Read when its
    // page opens; `details` is relative to the cache directory (the current generation).
    function loadDetails(app) {
        win.selectedDetails = null
        if (!app || !app.details) { win.detailsState = "none"; return }
        var path = "" + app.details
        if (!/^details\/[A-Za-z0-9._-]+\.json$/.test(path) || path.indexOf("..") >= 0 || !win.cacheDir) {
            win.detailsState = "none"
            return
        }
        var cached = win.detailsCache[app.id]
        if (cached) { win.selectedDetails = cached; win.detailsState = "ready"; return }
        win.detailsState = "loading"
        var id = app.id
        win.readJsonLater(win.cacheDir + "/" + path, function(document) {
            if (!win.selectedApp || win.selectedApp.id !== id) return
            if (document && document.id === id) {
                var next = Object.assign({}, win.detailsCache)
                next[id] = document
                win.detailsCache = next
                win.selectedDetails = document
                win.detailsState = "ready"
            } else {
                win.detailsState = "missing"
            }
        })
    }

    // What an installed app may do, from the backend (`moos-storectl permissions <id>`, which writes
    // permissions/<id>.json). An app that is not installed is described from the catalogue facts.
    function loadPermissions(app) {
        permissionPoll.stop()
        win.permissionDoc = null
        if (!app) { win.permissionState = "none"; return }
        var kind = win.appKind(app)
        if (kind === "web") { win.permissionState = "none"; return }
        if (!win.isInstalled(app)) { win.permissionState = "facts"; return }
        if (typeof MoosStore === "undefined" || typeof MoosStore.appPermissions !== "function") {
            win.permissionState = "unsupported"
            return
        }
        win.permissionAppId = app.id
        win.permissionRequestedAt = Date.now()
        if (!MoosStore.appPermissions(app.id)) { win.permissionState = "failed"; return }
        win.permissionState = "loading"
        permissionPoll.restart()
    }

    function readPermissions() {
        if (!win.cacheDir || win.permissionAppId === "") return false
        try {
            var document = win.readJson(win.cacheDir + "/permissions/" + win.permissionAppId + ".json")
            if (!document || document.id !== win.permissionAppId) return false
            var at = Date.parse(document.generated_at || "")
            if (!isFinite(at) || at + 2000 < win.permissionRequestedAt) return false
            win.permissionDoc = document
            win.permissionState = "ready"
            return true
        } catch (error) {
            return false
        }
    }

    // The person's Store choices (~/.config/moos/store.json): absent or unreadable means
    // automatic updates are on, the backend's own default.
    function loadStoreSettings() {
        try {
            var document = win.settingsPath ? win.readJson(win.settingsPath) : null
            win.autoUpdates = !(document && document.auto_updates === false)
        } catch (error) {
            win.autoUpdates = true
        }
    }

    function loadJob() {
        try {
            var document = win.readJson(win.jobPath)
            if (!document || !document.job_id) return false
            var active = document.state === "starting" || document.state === "running"
            var updated = Date.parse(document.updated_at || "")
            if (active && (!isFinite(updated) || Date.now() - updated > 120000)) {
                document.state = "failed"
                document.progress = null
                document.current_id = null
                document.message = win.rtl
                    ? "توقفت العملية السابقة قبل أن تكتمل"
                    : "The previous operation stopped before it completed"
                // Drop the stale step's key, or jobText would render that step's
                // cheerful progress line over this timeout notice.
                document.message_key = ""
                active = false
            }
            var terminal = document.state === "success"
                || document.state === "partial"
                || document.state === "failed"
                || document.state === "cancelled"
                || document.state === "busy"
            // A finished job from a previous Store session is history, not a new
            // notification. The freshly generated index already reflects it.
            if (!win.waitingForJob && !win.job.job_id && terminal) return false
            if (win.waitingForJob) {
                if (document.job_id === win.previousJobId
                        || !win.matchesExpectedJob(document)) {
                    if (!active) return false
                    // A fresh, live job that is not ours holds the backend: our request was
                    // refused, and a refusal is never written over another request's live job,
                    // so no document of ours will come. Say "busy" now instead of timing out,
                    // and show what IS running.
                    win.waitingForJob = false
                    win.flash(win.jobText({ "message_key": "busy" },
                                          win.local("متجر Mo مشغول بعملية أخرى", "Mo Store is busy")))
                    win.job = document
                    return true
                }
                win.waitingForJob = false
            }
            win.job = document
            if (win.jobIsTerminal()) {
                jobPoll.stop()
                win.applyJobInstalledState(document)
                if (document.action === "refresh-index"
                        && document.state === "success")
                    win.loadIndex()
                if (document.state === "success") {
                    win.clearPicks()
                    win.flash(win.jobText(document, win.rtl ? "اكتملت العملية بنجاح" : "All done"))
                } else if (document.state === "partial") {
                    win.flash(win.rtl ? "اكتمل بعض العناصر — راجع التفاصيل" : "Some items need attention")
                } else if (document.state !== "cancelled") {
                    win.flash(win.jobText(document, win.rtl ? "تعذّر إكمال العملية" : "The operation did not complete"))
                }
                if (document.action !== "refresh-index")
                    Qt.callLater(function() { win.maybeRefreshCatalog(false) })
                // Anything that installs, removes or updates invalidates the
                // pending-update answer. Drop it rather than show a stale list.
                if (document.action === "update"
                        || document.action === "install"
                        || document.action === "remove") {
                    win.updatesState = "unknown"
                    win.updates = ({})
                    win.updatesCheckedAt = ""
                    if (win.page === "updates" || win.page === "library")
                        Qt.callLater(function() { win.checkUpdates() })
                }
                win.afterJob(document)
            }
            return true
        } catch (error) {
            return false
        }
    }

    // What a finished job changes in the window: only the installed flags of its own items (the
    // library and the open page follow them), and a permissions document it rewrote.
    function afterJob(document) {
        if (document.action === "install" || document.action === "remove")
            win.recomputeLibrary()
        if (document.action === "set-permission" && win.selectedApp
                && win.permissionAppId === win.selectedApp.id) {
            var started = Date.parse(document.started_at || "")
            win.permissionRequestedAt = isFinite(started) ? started : Date.now()
            if (!win.readPermissions()) win.loadPermissions(win.selectedApp)
        }
        if (document.action === "remove" && win.selectedApp
                && !win.isInstalled(win.selectedApp)) {
            win.loadPermissions(win.selectedApp)
        }
        if (document.action === "install" && win.selectedApp && win.isInstalled(win.selectedApp))
            win.loadPermissions(win.selectedApp)
    }

    // Pending updates the person can act on: apps, and catalogue pins newer than what is
    // installed (`kind: "pin"`). Runtimes and other shared parts ride along and are counted apart.
    function updateItems() {
        var items = win.updates.items || []
        var apps = []
        for (var i = 0; i < items.length; ++i)
            if (items[i].kind === "app" || items[i].kind === "pin") apps.push(items[i])
        return apps
    }

    function updateComponentCount() {
        var items = win.updates.items || []
        return Math.max(0, items.length - win.updateItems().length)
    }

    function updateFor(app) {
        if (!app || win.updatesState !== "known") return null
        var items = win.updateItems()
        for (var i = 0; i < items.length; ++i)
            if (items[i].id === app.id) return items[i]
        return null
    }

    function hasUpdate(app) {
        if (!app || !win.isInstalled(app)) return false
        return win.updateFor(app) !== null || app.update_available === true
    }

    function loadUpdates() {
        if (!win.updatesPath || win.updatesPath === "") return false
        try {
            var document = win.readJson(win.updatesPath)
            if (!document || document.action !== "check-updates") return false
            if (document.checked_at === win.updatesCheckedAt) return false
            win.updatesCheckedAt = document.checked_at || ""
            win.updates = document
            win.updatesState = document.state === "success" ? "known" : "failed"
            win.updatesChecking = false
            if (document.auto_updates === true || document.auto_updates === false)
                win.autoUpdates = document.auto_updates
            return true
        } catch (error) {
            return false
        }
    }

    function adoptRecentUpdates() {
        // Reopening the Store should not forget what it learned a minute ago —
        // but it must not present an hours-old answer as current either. Older
        // than six hours stays "unknown", so the page checks again instead of
        // quietly showing a number that may have moved.
        if (!win.updatesPath || win.updatesPath === "") return false
        try {
            var document = win.readJson(win.updatesPath)
            if (!document || document.action !== "check-updates") return false
            if (document.state !== "success") return false
            var checked = Date.parse(document.checked_at || "")
            if (!isFinite(checked) || Date.now() - checked > 21600000) return false
            win.updatesCheckedAt = document.checked_at || ""
            win.updates = document
            win.updatesState = "known"
            if (document.auto_updates === true || document.auto_updates === false)
                win.autoUpdates = document.auto_updates
            return true
        } catch (error) {
            return false
        }
    }

    function checkUpdates() {
        if (win.updatesChecking) return
        if (typeof MoosStore === "undefined" || !MoosStore.checkUpdates()) {
            win.updatesState = "failed"
            return
        }
        win.updatesChecking = true
        updatePoll.restart()
    }

    function matchesExpectedJob(document) {
        if (document.action !== win.expectedAction) return false
        var started = Date.parse(document.started_at || "")
        if (!isFinite(started) || started + 1000 < win.requestEpoch) return false
        if (win.expectedIds.length === 0) return true
        var items = document.items || []
        if (items.length !== win.expectedIds.length) return false
        for (var i = 0; i < win.expectedIds.length; ++i) {
            var found = false
            for (var j = 0; j < items.length; ++j)
                if (items[j].id === win.expectedIds[i]) { found = true; break }
            if (!found) return false
        }
        return true
    }

    function expectJob(action, ids) {
        win.previousJobId = win.job.job_id || ""
        win.expectedAction = action
        win.expectedIds = ids.slice(0)
        win.requestEpoch = Date.now()
        win.waitingForJob = true
        win.jobWaitTicks = 0
    }

    // The backend reports progress in one language and the UI speaks the
    // owner's. moos-storectl therefore emits a stable `message_key` beside its
    // human `message`; the key is the contract, the prose is the fallback for a
    // job document written before keys existed. Failures deliberately carry no
    // key, so their real diagnostic text reaches the user verbatim.
    readonly property var jobPhrases: ({
        "refreshing_index":         ["يُعاد بناء فهرس التطبيقات الموحّد", "Rebuilding the unified app index"],
        "index_refreshed":          ["تم تحديث الفهرس", "Index refreshed"],
        "downloading_file":         ["يجري تنزيل ملف موثّق", "Downloading a verified file"],
        "downloading_android":      ["يجري تنزيل تطبيق أندرويد موثّق", "Downloading verified app"],
        "preparing_windows":        ["تجري تهيئة برنامج ويندوز", "Preparing the Windows program"],
        "windows_legacy_program":   ["هذا برنامج ويندوز قديم بإصدار 32-بت؛ يثبّت متجر Mo برامج ويندوز 64-بت فقط", "This is an older 32-bit Windows program; Mo Store installs 64-bit Windows programs only"],
        "unsupported_arch":         ["هذا التطبيق غير متوفّر لهذا النوع من الأجهزة", "This app is not available for this kind of computer"],
        "publisher_page_opened":    ["فُتحت صفحة الناشر", "Opened the publisher's page"],
        "app_up_to_date":           ["هذا التطبيق محدَّث", "This app is up to date"],
        "update_by_file":           ["ثُبّت هذا التطبيق من ملف؛ ثبّت ملفًا أحدث منه لتحديثه", "This app was installed from a file; install a newer file of it to update it"],
        "removed_with_data":        ["أُزيل مع بياناته", "Removed with its data"],
        "removed_data_untracked":   ["تمت الإزالة. بقيت الإعدادات التي حفظها التطبيق في مجلد المنزل كما هي", "Removed. Settings the app saved elsewhere in your home folder were kept"],
        "permission_changed":       ["تم تغيير الإذن", "Permission changed"],
        "permissions_reset":        ["أُعيدت الأذونات إلى وضعها الأصلي", "Permissions reset"],
        "invalid_id":               ["معرّف التطبيق غير صالح", "This app ID is not valid"],
        "invalid_permission":       ["لا يمكن تغيير هذا الإذن هنا", "This permission cannot be changed here"],
        "unsupported_kind":         ["لا يستطيع متجر Mo تنفيذ هذا لهذا التطبيق", "Mo Store cannot do this for this app"],
        "busy":                     ["متجر Mo مشغول بعملية أخرى — حاول بعد قليل", "Mo Store is busy with another operation — try again shortly"],
        "inspecting_file":          ["تجري قراءة الملف", "Reading the file"],
        "extracting_file":          ["يجري فكّ التطبيق", "Unpacking the application"],
        "integrating_app":          ["تجري إضافته إلى قائمة التطبيقات", "Adding it to the launcher"],
        "already_installed_user":   ["مثبّت مسبقًا لهذا المستخدم", "Already installed for this user"],
        "already_installed_system": ["مثبّت مسبقًا على مستوى النظام", "Already installed system-wide"],
        "not_installed":            ["التطبيق غير مثبّت", "App is not installed"],
        "nothing_to_remove":        ["لا شيء لإزالته — هذا التطبيق يُنزَّل من موقعه الرسمي خارج متجر Mo", "Nothing to remove — this app is downloaded from its official website, outside Mo Store"],
        "installed":                ["تم التثبيت", "Installed"],
        "removed":                  ["تمت الإزالة", "Removed"],
        "updated":                  ["تم التحديث", "Updated"],
        "up_to_date":               ["كل التطبيقات محدَّثة", "Apps are up to date"],
        "opening":                  ["جارٍ الفتح", "Opening"],
        "opened":                   ["تم الفتح", "Opened"],
        "preparing_gpu":            ["تهيئة موارد الرسوميات", "Preparing GPU headroom"],
        "completed":                ["اكتمل", "Completed"],
        "cancelled":                ["أُلغيت العملية", "Cancelled"],
        "cancelled_before_start":   ["أُلغيت قبل أن تبدأ", "Cancelled before starting"],
        "all_ready":                ["كل التطبيقات المطلوبة جاهزة", "All requested apps are ready"],
        "app_removed":              ["تمت إزالة التطبيق", "App removed"],
        "app_opened":               ["تم فتح التطبيق", "App opened"],
        "apps_updated":             ["تم تحديث التطبيقات", "Apps updated"]
    })

    function jobText(source, fallback) {
        var phrase = source && source.message_key
            ? win.jobPhrases[source.message_key] : undefined
        if (phrase)
            return win.rtl ? phrase[0] : phrase[1]
        return (source && source.message) || fallback
    }

    // True when `item` reports `key`, accepting the pre-key prose so a job
    // document left in the cache by an older Mo Store still resolves.
    function jobItemIs(item, key, legacyProse) {
        if (!item) return false
        if (item.message_key) return item.message_key === key
        return (item.message || "") === legacyProse
    }

    function applyJobInstalledState(document) {
        if (!document || !document.action) return
        if (document.action !== "install" && document.action !== "remove") return
        var next = Object.assign({}, win.installedOverrides)
        var nextScopes = Object.assign({}, win.installedScopeOverrides)
        var items = document.items || []
        for (var i = 0; i < items.length; ++i) {
            var item = items[i]
            if (document.action === "remove") {
                if (item.state === "done"
                        || (item.state === "skipped"
                            && win.jobItemIs(item, "not_installed",
                                             "App is not installed"))) {
                    var removedApp = win.appById(item.id)
                    next[item.id] = win.hasInstalledScope(removedApp, "system")
                    nextScopes[item.id] = win.hasInstalledScope(removedApp, "system")
                        ? ["system"] : []
                }
            } else if (item.state === "done") {
                next[item.id] = true
                var installedApp = win.appById(item.id)
                nextScopes[item.id] = win.hasInstalledScope(installedApp, "system")
                    ? ["user", "system"] : ["user"]
            } else if (item.state === "skipped"
                       && win.jobItemIs(item, "already_installed_system",
                                        "Already installed system-wide")) {
                next[item.id] = true
                nextScopes[item.id] = ["system"]
            } else if (item.state === "skipped"
                       && win.jobItemIs(item, "already_installed_user",
                                        "Already installed for this user")) {
                next[item.id] = true
                var skippedApp = win.appById(item.id)
                nextScopes[item.id] = win.hasInstalledScope(skippedApp, "system")
                    ? ["user", "system"] : ["user"]
            }
        }
        win.installedOverrides = next
        win.installedScopeOverrides = nextScopes
    }

    // ── the Apps and Games pages ────────────────────────────────────────────────
    //
    // Filters a list that is already in recommended order: a category or a collection, then one
    // of the four kinds, then the order the person asked for. Runs when a filter changes or a new
    // index generation arrives, never on a job tick.
    function recompute() {
        var out = []
        var counts = { "all": 0, "linux": 0, "web": 0, "windows": 0, "android": 0 }
        var games = win.page === "games"
        var collection = !games && win.activeCollection !== "" ? win.collectionById(win.activeCollection) : null
        var source = collection ? collection.apps : win.browseOrder
        for (var i = 0; i < source.length; ++i) {
            var app = source[i]
            if (games && app.cat !== "fun") continue
            if (!games && !collection && win.activeCategory !== "all" && app.cat !== win.activeCategory) continue
            ++counts.all
            counts[app.family] = (counts[app.family] || 0) + 1
            if (win.activeKind !== "all" && app.family !== win.activeKind) continue
            out.push(app)
        }
        win.viewKindCounts = counts
        if (win.sortMode === "name") {
            out.sort(function(a, b) {
                return win.localName(a).toLowerCase().localeCompare(win.localName(b).toLowerCase())
            })
        } else if (win.sortMode === "updated" && win.canSortByDate) {
            out.sort(function(a, b) { return ("" + (b.released || "")).localeCompare("" + (a.released || "")) })
        }
        win.visibleApps = out
    }

    function kindCountIn(family) {
        if (family === "all") return win.browseOrder.length
        return win.kindCounts[family] || 0
    }

    // ── My apps ─────────────────────────────────────────────────────────────────
    function recomputeLibrary() {
        var out = []
        for (var i = 0; i < win.allApps.length; ++i)
            if (win.isInstalled(win.allApps[i])) out.push(win.allApps[i])
        out.sort(function(a, b) {
            return win.localName(a).toLowerCase().localeCompare(win.localName(b).toLowerCase())
        })
        win.installedApps = out
        win.filterLibrary()
    }

    function filterLibrary() {
        if (win.libraryKind === "all") { win.libraryApps = win.installedApps; return }
        var out = []
        for (var i = 0; i < win.installedApps.length; ++i)
            if (win.installedApps[i].family === win.libraryKind) out.push(win.installedApps[i])
        win.libraryApps = out
    }

    function libraryCount(family) {
        if (family === "all") return win.installedApps.length
        var count = 0
        for (var i = 0; i < win.installedApps.length; ++i)
            if (win.installedApps[i].family === family) ++count
        return count
    }

    // ── search ──────────────────────────────────────────────────────────────────
    //
    // The query is folded exactly as the index folded `search`, then ranked: an exact name, a name
    // that starts with it, a word of the name that starts with it, the keywords (and the
    // developer), and last the summary. Every word typed must match.
    function wordsStart(text, tokens) {
        var padded = " " + text
        for (var i = 0; i < tokens.length; ++i)
            if (padded.indexOf(" " + tokens[i]) < 0) return false
        return true
    }

    function allIn(text, tokens) {
        for (var i = 0; i < tokens.length; ++i)
            if (text.indexOf(tokens[i]) < 0) return false
        return true
    }

    function runSearch() {
        var q = win.foldSearch(win.query)
        if (q === "") { win.searchResults = []; return }
        var tokens = q.split(" ")
        var scored = []
        for (var i = 0; i < win.allApps.length; ++i) {
            var app = win.allApps[i]
            if (app.listed === false && !win.isInstalled(app)) continue
            if (app._fn === undefined) {
                app._fn = win.foldSearch(win.localName(app))
                app._fe = win.foldSearch(app.name_en || "")
            }
            var tier = -1
            if (app._fn === q || app._fe === q) tier = 0
            else if (app._fn.indexOf(q) === 0 || app._fe.indexOf(q) === 0) tier = 1
            else if (win.wordsStart(app._fn + " " + app._fe, tokens)) tier = 2
            else if (win.allIn(app.search || "", tokens)) tier = 3
            else {
                if (app._fs === undefined) app._fs = win.foldSearch(win.localSummary(app))
                if (win.allIn(app._fs, tokens)) tier = 4
            }
            if (tier >= 0) scored.push({ app: app, tier: tier, rank: app._rank === undefined ? 1e9 : app._rank })
        }
        scored.sort(function(a, b) { return a.tier - b.tier || a.rank - b.rank })
        var out = []
        for (var k = 0; k < scored.length && k < 400; ++k) out.push(scored[k].app)
        win.searchResults = out
    }

    // The header's field types here. A first character takes the window to the search page; the
    // results follow ~120 ms after the last key, so typing never waits on 3,000 apps.
    function setQuery(text) {
        win.query = text
        if (text.trim() !== "" && win.page !== "search") {
            win.pushHistory()
            win.page = "search"
        }
        searchDebounce.restart()
    }

    function searchFor(text) {
        storeHeader.setSearchText(text)
    }

    // ── navigation ──────────────────────────────────────────────────────────────
    //
    // The rail's pages start fresh. An app's page, a collection, a category or a search remembers
    // where it was opened from, and Back (Escape, Backspace, Alt+Left, or the header's arrow)
    // returns there with its filters as they were.
    function navigate(target) {
        win.history = []
        win.activeCategory = "all"
        win.activeKind = "all"
        win.activeCollection = ""
        if (win.query !== "") storeHeader.clearSearch()
        win.page = target
        win.recompute()
    }

    function pushHistory() {
        var entry = { page: win.page, appId: win.page === "app" && win.selectedApp ? win.selectedApp.id : "",
                      category: win.activeCategory, kind: win.activeKind, collection: win.activeCollection }
        win.history = win.history.concat([entry])
    }

    readonly property bool canGoBack: win.history.length > 0

    function goBack() {
        var stack = win.history.slice(0)
        var last = stack.pop()
        win.history = stack
        if (!last) {
            if (win.page !== "discover") win.navigate("discover")
            return
        }
        if (last.page !== "search" && win.query !== "") storeHeader.clearSearch()
        win.activeCategory = last.category
        win.activeKind = last.kind
        win.activeCollection = last.collection
        if (last.page === "app") {
            var app = win.appById(last.appId)
            if (app) { win.showApp(app); return }
        }
        win.page = last.page
        win.recompute()
    }

    function openCategory(category) {
        if (category === "fun") { win.navigate("games"); return }
        win.pushHistory()
        win.activeKind = "all"
        win.activeCollection = ""
        win.activeCategory = category
        win.page = "apps"
        win.recompute()
    }

    function openKind(family) {
        win.pushHistory()
        win.activeCategory = "all"
        win.activeCollection = ""
        win.activeKind = family
        win.page = "apps"
        win.recompute()
    }

    function openCollection(id) {
        var collection = win.collectionById(id)
        if (!collection) return
        if (collection.category) { win.openCategory(collection.category); return }
        win.pushHistory()
        win.activeCategory = "all"
        win.activeKind = "all"
        win.activeCollection = id
        win.page = "apps"
        win.recompute()
    }

    // An app's page replaces the window's content (it is no longer a popup): the rail stays, the
    // header carries Back, and the page reads the app's details document when it opens.
    function openDetails(app) {
        if (!app) return
        win.pushHistory()
        win.showApp(app)
    }

    function showApp(app) {
        win.selectedApp = app
        win.page = "app"
        win.loadDetails(app)
        win.loadPermissions(app)
    }

    // ── what the buttons do ─────────────────────────────────────────────────────
    function installOne(app) {
        win.clearPicks()
        win.setPicked(app.id, true)
        review.open()
    }

    // The selection shelf (SelectionShelf.qml) opens the review and steps aside while it is on
    // screen, from the first frame of its entrance.
    readonly property bool reviewOpened: review.visible
    function openReview() {
        review.open()
    }

    // The one button an app shows first, by what is true of it now.
    function primaryAction(app) {
        if (!app) return "none"
        if (win.appJobState(app) !== "") return "progress"
        if (win.isInstalled(app)) {
            if (win.hasUpdate(app)) return "update"
            return win.hasRunnableLifecycle(app) ? "open" : "installed"
        }
        if (win.compatOf(app).verdict === "blocked" || app.installable === false) return "blocked"
        if (win.isPicked(app.id)) return "added"
        return win.isWeb(app) ? "website" : "get"
    }

    function primaryLabel(action) {
        switch (action) {
        case "open":      return win.local("فتح", "Open")
        case "update":    return win.local("تحديث", "Update")
        case "installed": return win.local("مثبّت", "Installed")
        case "blocked":   return win.local("غير متاح", "Unavailable")
        case "website":   return win.local("زيارة", "Visit")
        case "added":     return win.local("مُضاف", "Added")
        case "progress":  return win.local("جارٍ…", "Working…")
        default:          return win.local("تثبيت", "Get")
        }
    }

    function performPrimary(app) {
        var action = win.primaryAction(app)
        if (action === "open") win.runSelected(app)
        else if (action === "update") win.updateOne(app)
        else if (action === "added") win.setPicked(app.id, false)
        else if (action === "get" || action === "website") win.installOne(app)
    }

    readonly property string needsUpdateText: win.local("يحتاج هذا تحديث MoOS القادم", "This needs the next MoOS update")

    // Whether the installed shell's bridge offers a method this window would call (a newer
    // window can run on an older shell until the next MoOS update).
    // The shell clears the bridge to null while the window closes, and views still bind to this.
    function bridgeHas(name) {
        return typeof MoosStore !== "undefined" && MoosStore !== null && typeof MoosStore[name] === "function"
    }

    // Returns whether MoOS took the file. The caller needs the answer: telling the
    // drag source a drop was accepted when nothing happened leaves the person
    // watching a window that did not react and gives them nothing to retry.
    function reviewDroppedFile(url) {
        if (win.jobIsActive()) {
            win.flash(win.local("انتظر اكتمال العملية الحالية", "Wait for the current operation"))
            return false
        }
        if (typeof MoosStore === "undefined" || typeof MoosStore.installFile !== "function"
                || !MoosStore.installFile(url)) {
            win.flash(win.local("تعذّر فتح الملف. اختر ملف تطبيق محليًا.",
                                "Could not open the file. Choose a local application file."))
            return false
        }
        // What is true at this instant, and nothing more: the file has been handed
        // to MoOS to look at. It has not been inspected yet, it may turn out to be
        // unsupported, and the question that decides it has not been asked.
        win.flash(win.local("يفحص MoOS الملف ويسألك قبل أي إجراء.",
                            "MoOS is checking the file and will ask before doing anything."))
        // An install started from this window must be visible IN this window.
        jobPoll.restart()
        return true
    }

    NativeDialogs.FileDialog {
        id: applicationFile
        title: win.local("إضافة تطبيق إلى MoOS", "Add an app to MoOS")
        fileMode: NativeDialogs.FileDialog.OpenFile
        onAccepted: win.reviewDroppedFile(selectedFile)
    }

    DropArea {
        id: appDropTarget
        anchors.fill: parent
        onEntered: function(drag) { drag.accepted = drag.hasUrls && drag.urls.length === 1 }
        onDropped: function(drop) {
            if (!drop.hasUrls || drop.urls.length !== 1) return
            if (win.reviewDroppedFile(drop.urls[0]))
                drop.acceptProposedAction()
        }
    }

    function beginInstall() {
        var ids = Object.keys(win.picks)
        if (ids.length === 0 || win.jobIsActive()) return
        if (typeof MoosStore === "undefined") {
            win.flash(win.rtl ? "قناة التثبيت الموثوقة غير متاحة" : "The trusted install channel is unavailable")
            return
        }
        win.expectJob("install", ids)
        if (!MoosStore.installApps(ids)) {
            win.waitingForJob = false
            win.flash(win.rtl ? "تعذّر بدء عملية التثبيت" : "Could not start the install")
            return
        }
        review.close()
        jobPoll.restart()
    }

    function runSelected(app) {
        if (!win.hasRunnableLifecycle(app)) return
        if (win.jobIsActive()) {
            win.flash(win.rtl ? "انتظر اكتمال العملية الحالية" : "Wait for the current operation")
            return
        }
        win.expectJob("run", [app.id])
        if (typeof MoosStore === "undefined" || !MoosStore.runApp(app.id)) {
            win.waitingForJob = false
            win.flash(win.rtl ? "تعذّر فتح التطبيق" : "Could not open the app")
            return
        }
        jobPoll.restart()
    }

    function removeSelected(app) {
        if (win.jobIsActive()) {
            win.flash(win.rtl ? "انتظر اكتمال العملية الحالية" : "Wait for the current operation")
            return
        }
        if (!win.canRemove(app)) {
            win.flash(win.rtl
                ? "هذا التطبيق مُدار مع النظام ولا يُزال من متجر المستخدم"
                : "This app is system-managed and cannot be removed from the user store")
            return
        }
        win.expectJob("remove", [app.id])
        if (typeof MoosStore === "undefined" || !MoosStore.removeApp(app.id)) {
            win.waitingForJob = false
            win.flash(win.rtl ? "تعذّر بدء الإزالة" : "Could not start removal")
            return
        }
        removeSheet.close()
        jobPoll.restart()
    }

    // Removal together with the app's own data (moos-storectl remove --delete-data <id>).
    function removeSelectedWithData(app) {
        if (win.jobIsActive()) {
            win.flash(win.rtl ? "انتظر اكتمال العملية الحالية" : "Wait for the current operation")
            return
        }
        if (!win.canRemove(app)) {
            win.flash(win.rtl
                ? "هذا التطبيق مُدار مع النظام ولا يُزال من متجر المستخدم"
                : "This app is system-managed and cannot be removed from the user store")
            return
        }
        if (typeof MoosStore === "undefined" || typeof MoosStore.removeAppData !== "function") {
            win.flash(win.needsUpdateText)
            return
        }
        win.expectJob("remove", [app.id])
        if (!MoosStore.removeAppData(app.id)) {
            win.waitingForJob = false
            win.flash(win.rtl ? "تعذّر بدء الإزالة" : "Could not start removal")
            return
        }
        removeSheet.close()
        jobPoll.restart()
    }

    function updateAll() {
        if (win.jobIsActive()) return
        win.expectJob("update", [])
        if (typeof MoosStore === "undefined" || !MoosStore.updateApps()) {
            win.waitingForJob = false
            win.flash(win.rtl ? "تعذّر بدء التحديث" : "Could not start updates")
            return
        }
        jobPoll.restart()
    }

    // One app, of any kind (moos-storectl update <id>).
    function updateOne(app) {
        if (!app || win.jobIsActive()) return
        if (typeof MoosStore === "undefined" || typeof MoosStore.updateApp !== "function") {
            win.flash(win.needsUpdateText)
            return
        }
        win.expectJob("update", [app.id])
        if (!MoosStore.updateApp(app.id)) {
            win.waitingForJob = false
            win.flash(win.rtl ? "تعذّر بدء التحديث" : "Could not start the update")
            return
        }
        jobPoll.restart()
    }

    // One permission of an installed app: allow, deny, or reset to what the app asked for.
    function setPermission(app, key, value) {
        if (!app || win.jobIsActive()) return
        if (typeof MoosStore === "undefined" || typeof MoosStore.setPermission !== "function") {
            win.flash(win.needsUpdateText)
            return
        }
        win.permissionAppId = app.id
        win.expectJob("set-permission", [app.id])
        if (!MoosStore.setPermission(app.id, key, value)) {
            win.waitingForJob = false
            win.flash(win.local("تعذّر تغيير الإذن", "Could not change the permission"))
            return
        }
        jobPoll.restart()
    }

    // The scheduled app updater's switch. It is a setting, not a job: the backend writes it at
    // once, the window reads the file back until it says what was asked, and then asks for the
    // pending-update document, which carries the same answer.
    function setAutoUpdates(on) {
        if (win.autoUpdatesPending || on === win.autoUpdates) return
        if (typeof MoosStore === "undefined" || typeof MoosStore.setAutoUpdates !== "function") {
            win.flash(win.needsUpdateText)
            return
        }
        win.autoUpdatesWanted = on
        if (!MoosStore.setAutoUpdates(on)) {
            win.flash(win.local("تعذّر تغيير التحديث التلقائي", "Could not change automatic updates"))
            return
        }
        win.autoUpdatesPending = true
        settingsPoll.restart()
    }

    function openSourceEngine(action) {
        if (action === "refresh") {
            win.maybeRefreshCatalog(true)
            return
        }
        if (win.jobIsActive()) {
            win.flash(win.rtl ? "انتظر اكتمال العملية الحالية" : "Wait for the current operation")
            return
        }
        win.expectJob("open-engine", [action])
        if (typeof MoosStore === "undefined" || !MoosStore.openEngine(action)) {
            win.waitingForJob = false
            win.flash(win.rtl ? "تعذّر فتح المحرك" : "Could not open the engine")
            return
        }
        jobPoll.restart()
    }

    // The job shelf's Cancel (JobShelf.qml): every bridge call stays in this file.
    function cancelJob() {
        if (typeof MoosStore !== "undefined") MoosStore.cancelJob()
    }

    function openSystemUpdater() {
        if (typeof MoosStore === "undefined" || !MoosStore.openSystemUpdater())
            win.flash(win.rtl ? "تعذّر فتح محدّث MoOS" : "Could not open MoOS Updater")
    }

    // Places outside the Store it may send a person to: fixed MoOS routes that navigate or ask
    // before they act (firmware lives in MoOS Settings → Update; the one-time Windows and Android
    // setups are moai-do's, with its confirmation). Nothing here installs.
    readonly property var systemRoutes: ({
        "firmware": "moos://settings/update",
        "setup-windows": "moos://do/setup-windows",
        "setup-android": "moos://do/setup-waydroid"
    })

    function openSystemRoute(name) {
        var url = win.systemRoutes[name]
        if (!url || !Qt.openUrlExternally(url))
            win.flash(win.local("تعذّر فتح هذه الصفحة", "Could not open that page"))
    }

    // A publisher's link (website, help, donate, report a problem): https only.
    function isSafeLink(url) {
        return typeof url === "string" && /^https:\/\/[^\s/?#]+[^\s]*$/i.test(url)
    }

    function openLink(url) {
        if (!win.isSafeLink(url) || !Qt.openUrlExternally(url))
            win.flash(win.local("تعذّر فتح الرابط", "Could not open the link"))
    }

    // A picture the window may load: a local file always, an internet address only while the
    // person allows app pictures from the internet (Settings).
    function pictureSource(url) {
        var text = "" + (url || "")
        if (text.indexOf("file:///") === 0) return text
        if (text.indexOf("https://") === 0 && win.remotePictures) return text
        return ""
    }

    function iconSource(app) {
        if (!app) return ""
        return win.pictureSource(app.icon) || win.pictureSource(app.icon_url)
    }

    // ── sheets ──────────────────────────────────────────────────────────────────
    function openRemove(app) {
        if (!app) return
        removeSheet.app = app
        removeSheet.open()
    }

    function openPermissions(app) {
        if (!app) return
        if (!win.permissionDoc || win.permissionDoc.id !== app.id) win.loadPermissions(app)
        permissionsSheet.app = app
        permissionsSheet.open()
    }

    function openScreenshots(shots, index) {
        if (!shots || shots.length === 0) return
        screenshotViewer.shots = shots
        screenshotViewer.index = Math.max(0, Math.min(shots.length - 1, index))
        screenshotViewer.open()
    }

    // Escape closes the sheet on screen first. A sheet still arriving (`opened` turns true only
    // when its entrance ends) counts as on screen: Escape pressed at once must not go Back.
    function escapeAction() {
        if (screenshotViewer.visible) screenshotViewer.close()
        else if (removeSheet.visible) removeSheet.close()
        else if (permissionsSheet.visible) permissionsSheet.close()
        else if (review.visible) review.close()
        else if (win.page === "search" || win.canGoBack) win.goBack()
    }

    // ── the person's own window preference ──────────────────────────────────────
    Settings {
        id: windowPrefs
        location: StandardPaths.writableLocation(StandardPaths.GenericConfigLocation) + "/moos/store-window.conf"
        category: "window"
        property bool remotePictures: true
    }
    readonly property bool remotePictures: windowPrefs.remotePictures
    function setRemotePictures(on) {
        windowPrefs.remotePictures = on
    }

    onPageChanged: {
        if (win.page === "apps" || win.page === "games") win.recompute()
        // Ask only when the person is actually looking at the page, and only when
        // the answer is not already in hand — the check costs a process and can
        // touch the network.
        if ((win.page === "updates" || win.page === "library") && win.updatesState === "unknown")
            Qt.callLater(function() { win.checkUpdates() })
    }
    onActiveCategoryChanged: recompute()
    onActiveKindChanged: recompute()
    onActiveCollectionChanged: recompute()
    onSortModeChanged: recompute()
    onLibraryKindChanged: filterLibrary()
    onInstalledOverridesChanged: recomputeLibrary()

    // ── Opening one app's page from outside ─────────────────────────────────
    //
    // `moos-store --app=<id>`, an appstream:// link and Plasma's "Uninstall or Manage
    // Add-ons…" reach this window as one `--open-app=<id>` argument: in its own arguments at
    // launch, and through activateRequested() when the Store is already open (moos-qml-shell
    // forwards the second launch's argv). The launcher validated the id; it is validated again
    // here, where the window owns the boundary. A link only ever SHOWS an app: what happens
    // next is the person's choice on its page. The launcher's jump list names a page the same
    // way (`--open-page=updates`), from a fixed list.
    property string pendingOpenApp: ""

    function requestedAppId(argv) {
        var id = ""
        for (var i = 0; i < argv.length; ++i) {
            var arg = "" + argv[i]
            if (arg.indexOf("--open-app=") !== 0) continue
            var candidate = arg.substring("--open-app=".length)
            if (/^[A-Za-z0-9][A-Za-z0-9._-]{1,254}$/.test(candidate) && candidate.indexOf("..") < 0)
                id = candidate
        }
        return id
    }

    function requestedPage(argv) {
        var target = ""
        for (var i = 0; i < argv.length; ++i) {
            var arg = "" + argv[i]
            if (arg.indexOf("--open-page=") !== 0) continue
            var candidate = arg.substring("--open-page=".length)
            if (["discover", "apps", "games", "library", "updates", "settings"].indexOf(candidate) >= 0)
                target = candidate
        }
        return target
    }

    // The page opens once the index can answer: at once when the loaded index (or, with no index
    // at all, the catalogue) knows the id. While the launch-time poll still waits for a rebuilt
    // index, an id the old one does not know waits with it rather than being called missing.
    function openRequestedApp() {
        if (win.pendingOpenApp === "") return
        var app = win.indexReady ? win.appById(win.pendingOpenApp) : null
        if (!app && win.indexPolling) return
        var id = win.pendingOpenApp
        win.pendingOpenApp = ""
        if (!app) app = win.appById(id)
        if (app) win.openDetails(app)
        else win.flash(win.local("لم يُعثر على هذا التطبيق في Mo Store", "This app was not found in Mo Store"))
    }

    function activateRequested(arguments) {
        var target = win.requestedPage(arguments)
        if (target !== "") win.navigate(target)
        var id = win.requestedAppId(arguments)
        if (id === "") return
        win.pendingOpenApp = id
        win.openRequestedApp()
    }

    onIndexReadyChanged: win.openRequestedApp()
    onIndexPollingChanged: win.openRequestedApp()

    Component.onCompleted: {
        win.loadMachine()
        win.loadCurated()
        win.loadStoreSettings()
        win.loadIndex()
        win.adoptRecentUpdates()
        win.loadJob()
        if (win.jobIsActive()) jobPoll.start()
        Qt.callLater(function() { win.maybeRefreshCatalog(false) })
        indexPoll.start()
        win.activateRequested(Qt.application.arguments)
    }

    // Whether the launch-time poll is still waiting for the rebuilt index. The rail's status
    // card (StoreRail.qml) says "Building catalogue…" and pulses only while it is.
    readonly property bool indexPolling: indexPoll.running

    Timer {
        id: indexPoll
        interval: 850
        repeat: true
        property int ticks: 0
        onTriggered: {
            ++ticks
            if (win.indexBuildReady()) {
                win.loadIndex()
                stop()
            }
            if (ticks > 36) stop()
        }
        onRunningChanged: if (running) ticks = 0
    }

    // The check is a separate detached process, so poll for its document the
    // same way the job is polled. Bounded: a check that never lands leaves the
    // page saying so rather than spinning forever.
    Timer {
        id: updatePoll
        interval: 500
        repeat: true
        property int ticks: 0
        onTriggered: {
            ++ticks
            if (win.loadUpdates()) { stop(); return }
            if (ticks > 60) {
                stop()
                win.updatesChecking = false
                if (win.updatesState === "unknown") win.updatesState = "failed"
            }
        }
        onRunningChanged: if (running) ticks = 0
    }

    Timer {
        id: jobPoll
        interval: 420
        repeat: true
        onTriggered: {
            ++win.jobWaitTicks
            win.loadJob()
            if (win.waitingForJob && win.jobWaitTicks > 40) {
                win.waitingForJob = false
                stop()
                win.flash(win.rtl ? "لم تبدأ العملية — حاول مجددًا" : "The operation did not start — try again")
            }
        }
    }

    // `moos-storectl permissions <id>` runs detached and writes its document; bounded like the rest.
    Timer {
        id: permissionPoll
        interval: 250
        repeat: true
        property int ticks: 0
        onTriggered: {
            ++ticks
            if (win.readPermissions()) { stop(); return }
            if (ticks > 40) { stop(); win.permissionState = "failed" }
        }
        onRunningChanged: if (running) ticks = 0
    }

    // The automatic-update switch, read back from the file the backend writes.
    Timer {
        id: settingsPoll
        interval: 200
        repeat: true
        property int ticks: 0
        onTriggered: {
            ++ticks
            var document = null
            try { document = win.settingsPath ? win.readJson(win.settingsPath) : null } catch (error) { document = null }
            var stored = !(document && document.auto_updates === false)
            if (document && stored === win.autoUpdatesWanted) {
                stop()
                win.autoUpdates = stored
                win.autoUpdatesPending = false
                win.checkUpdates()
                return
            }
            if (ticks > 25) {
                stop()
                win.autoUpdatesPending = false
                win.flash(win.local("لم يُحفظ اختيار التحديث التلقائي", "The automatic-update choice was not saved"))
            }
        }
        onRunningChanged: if (running) ticks = 0
    }

    Timer {
        id: searchDebounce
        interval: 120
        onTriggered: win.runSearch()
    }

    // The search field lives in the header (StoreHeader.qml).
    function focusSearch() {
        storeHeader.focusSearch()
    }

    Shortcut {
        sequences: ["Ctrl+K", "Ctrl+F", "/"]
        onActivated: win.focusSearch()
    }

    Shortcut {
        sequence: "Escape"
        onActivated: win.escapeAction()
    }

    Shortcut {
        sequence: "Alt+Left"
        onActivated: win.goBack()
    }

    Shortcut {
        sequence: "Backspace"
        enabled: win.canGoBack && !(win.activeFocusItem && win.activeFocusItem.cursorPosition !== undefined)
        onActivated: win.goBack()
    }

    // Shared palette-aware symbolic vocabulary; application artwork remains
    // AppStream-provided, while every control glyph comes from the MoOS layer.
    // Glyph.qml draws them; the alias table stays here, beside the window's palette.
    readonly property var glyphAliases: ({
        "android": "android-apps", "brain": "ai", "doc": "document",
        "gamepad": "gaming", "gear": "settings", "mic": "microphone",
        "monitor": "system", "note": "music", "warn": "warning",
        "download": "install", "disk": "storage",
        "media": "play", "archive": "boxes"
    })
    function glyphIcon(name) {
        return MoUI.SymbolCatalog.resolve(win.glyphAliases[name] || name || "spark")
    }

    // A focus ring nobody can see is no focus ring. Enforced at the window, not per delegate:
    //   1. whatever HOLDS focus is scrolled into view, in both axes, in whichever
    //      Flickable ancestors clip it (the grids, the rows, the app page);
    //   2. PageDown/PageUp move each content pane via pageScrollKeys(), reached by key
    //      bubbling from any focused item inside the pane.
    onActiveFocusItemChanged: MoUI.KeyboardViewport.revealFocus(win.activeFocusItem)

    // Tab out of the app grid (AppsPage.qml) lands on the rail's first entry.
    function focusFirstNavItem(reason) {
        rail.focusFirstNavItem(reason)
    }

    // Layered background: the scheme's canvas, one broad, still light from the leading top
    // corner and a quiet horizon low on the window. Nothing here moves.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: win.canvas }
            GradientStop { position: 1; color: Qt.darker(win.canvas, win.lightScheme ? 1.03 : 1.12) }
        }
    }
    Rectangle {
        width: win.fs(760)
        height: win.fs(760)
        radius: width / 2
        x: win.rtl ? win.width - width * 0.62 : -width * 0.38
        y: -height * 0.62
        color: win.tint(win.accent, win.lightScheme ? 0.10 : 0.08)
    }
    Rectangle {
        width: win.fs(620)
        height: win.fs(620)
        radius: width / 2
        x: win.rtl ? -width * 0.35 : win.width - width * 0.65
        y: win.height - height * 0.4
        color: win.tint(win.cyan, win.lightScheme ? 0.07 : 0.05)
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        LayoutMirroring.enabled: win.rtl
        LayoutMirroring.childrenInherit: true

        // Navigation rail.
        StoreRail { id: rail; win: win }

        // Main surface.
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            StoreHeader { id: storeHeader; win: win }

            Item {
                id: pageHost
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                DiscoverPage { win: win }

                // Apps and Games: one filtered, virtualised grid.
                AppsPage { win: win }

                // An app's page.
                AppPage { win: win }

                // The pages behind the rail load the first time they are shown and then stay,
                // keeping their scroll position.
                Loader {
                    anchors.fill: parent
                    active: win.page === "library" || status === Loader.Ready
                    sourceComponent: Component { LibraryPage { win: win } }
                }
                Loader {
                    anchors.fill: parent
                    active: win.page === "updates" || status === Loader.Ready
                    sourceComponent: Component { UpdatesPage { win: win } }
                }
                Loader {
                    anchors.fill: parent
                    active: win.page === "settings" || status === Loader.Ready
                    sourceComponent: Component { SettingsPage { win: win } }
                }
                Loader {
                    anchors.fill: parent
                    active: win.page === "search" || status === Loader.Ready
                    sourceComponent: Component { SearchPage { win: win } }
                }
            }
        }
    }

    // Selection shelf.  It never preselects software on launch.
    SelectionShelf { win: win }

    // Real transaction status shelf.  Null progress is shown as indeterminate,
    // never replaced with a made-up percentage.
    JobShelf { win: win }

    // One explicit review for a single app or a whole collection.
    ReviewSheet { id: review; win: win }

    // Remove (keep data, or remove it too) and an installed app's permissions.
    RemoveSheet { id: removeSheet; win: win }
    PermissionsSheet { id: permissionsSheet; win: win }

    // A screenshot, whole, over the window.
    ScreenshotViewer { id: screenshotViewer; win: win }

    StoreToast { id: toast; win: win }

    DropOverlay { win: win; visible: appDropTarget.containsDrag }
}
