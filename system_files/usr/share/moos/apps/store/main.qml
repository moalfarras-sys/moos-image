// Mo Store — the single, trusted application centre for MoOS.
//
// The signed catalogue remains the offline fallback and the source of MoOS
// recommendations.  /usr/bin/moos-store-index expands it at launch with every
// desktop application in the local Flatpak/AppStream indexes.  The index is
// local-first: browsing, search, installed state and icons keep working when
// Flathub's web API or the network is unavailable.
//
// State-changing work never travels through the public `moos:` URL scheme.
// MoosStore is a narrow C++ bridge exposed only to this read-only QML (and the
// Welcome).  It starts /usr/bin/moos-storectl with an argv list; the backend
// validates ids again, owns the real FlatpakTransaction and atomically publishes
// job.json.  A web page can open Mo Store, but it cannot install an app.
//
// This file is the window: all state, the data loading, the timers, the bridge
// calls and the palette live here. What it draws lives in the files beside it:
// StoreRail and StoreHeader, one file per page (DiscoverPage, CatalogPage,
// CategoriesPage, UpdatesPage, SourcesPage), the shelves and sheets, and the cards
// and controls they are built from. Each takes this window as
// `required property var win` and reaches it only as `win.<member>`
// (tests/test_qml_root_references.py holds that line); an id one of them needs from
// here is a root member instead (focusSearch(), openReview(), indexPolling, …).
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs as NativeDialogs
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

ApplicationWindow {
    id: win

    // Motion gate: the "loading catalogue" shimmer and the indeterminate job
    // spinner below AND their `running:` with this so "disable animations"
    // stops them. Kirigami floors longDuration at 1 when motion is off, so
    // `> 1` is the honest off-switch.
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    visible: true
    width: Math.min(1320, Screen.desktopAvailableWidth * 0.94)
    height: Math.min(820, Screen.desktopAvailableHeight * 0.94)
    minimumWidth: Math.min(900, Screen.desktopAvailableWidth * 0.94)
    minimumHeight: Math.min(620, Screen.desktopAvailableHeight * 0.94)
    title: qsTr("Mo Store")
    color: win.canvas

    // Semantic colours are owned by the active MoOS/KDE colour scheme.
    // TYPE SCALES WITH THE USER'S FONT SIZE, and until now it did not.
    //
    // 294 text items across the MoOS apps carried a hardcoded `font.pixelSize`, so the size
    // slider in System Settings > Fonts moved every application on the machine except this
    // operating system's own. That is an accessibility defect, not a style one: it is the
    // control someone with low vision reaches for first.
    //
    // The reference is POINT size, not pixels. MoOS ships `IBM Plex Sans,10` in
    // /etc/xdg/kdeglobals, and Qt reports pointSize 10 / pixelSize 13 on this 4K display —
    // pixels move with DPI and points do not, so dividing by the shipped 10pt gives exactly
    // 1.0 on every screen at the default and scales only when the USER changes the setting.
    //
    // fs() remains for geometry that grows with the user's font setting. Text goes
    // through typePx(), which snaps the old ad-hoc values to the reviewed
    // 11/13/14/15/20/24/32 role ramp and keeps 11 px as the functional minimum.
    readonly property real fontScale: Qt.application.font.pointSize > 0
                                      ? Qt.application.font.pointSize / 10 : 1
    function fs(px) { return Math.round(px * win.fontScale) }
    function typePx(px) { return design.typeSize(px, win.fontScale) }
    function local(ar, en) { return win.rtl ? ar : en }
    readonly property var design: MoUI.Tokens

    // The UI face is the SYSTEM face, not a string repeated in this file.
    //
    // This was `font.family: "IBM Plex Sans"` written out at every text item — 194 times across
    // Welcome, Mo Store and the Installer. Measured, the system font on MoOS already IS
    // IBM Plex Sans 13px (kdeglobals General font), and fontconfig maps sans-serif to it as well
    // (61-moos-brand.conf). So the literal added nothing to how MoOS looks and did exactly one
    // thing: it OVERRODE the user's own font choice, in the four apps MoOS ships, and nowhere
    // else. Someone who sets a larger or more legible face in System Settings watched every
    // application obey except this operating system's own.
    //
    // The proof that the literal is unnecessary is already in the tree: the theme picker sets no
    // font.family at all and renders in the brand face regardless, because the brand face is the
    // system face.
    readonly property string uiFont: Qt.application.font.family

    // ── semantic palette ───────────────────────────────────────────────────────
    //
    // READ FROM Kirigami.Theme, NOT FROM `palette`. Measured on one session, one scheme
    // (MoOSUI2Light, whose selection is #006D67):
    //
    //   an app using Kirigami.Theme  ->  surface #DFEFEA, accent #006D67   (MoOS teal)
    //   an app using palette.*       ->  surface #FFFFFF, accent #45A7D7   (stock Breeze blue)
    //
    // A bare `palette` in a QQuickWindow does not resolve the KDE colour scheme; it falls back
    // to Qt's built-in defaults, and QT_QPA_PLATFORMTHEME=kde does not change that (tested).
    // That is why MoOS's own windows wore a blue that appears nowhere in any MoOS palette,
    // inside a mint MoOS frame. Kirigami.Theme resolves it, so every surface now follows the
    // theme the user actually picked.
    //
    // The window paints on the VIEW set: rendered side by side the family gives four value
    // steps (Button #B8D8D2, Window #C9E2DD, View #D8EBE7, alternate #E1F0EC), and content
    // needs the airier end or the page collapses into one flat wash.
    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.View

    readonly property color canvas:   Kirigami.Theme.backgroundColor
    readonly property color surface:  Kirigami.Theme.alternateBackgroundColor
    readonly property color raised:   Kirigami.Theme.backgroundColor
    readonly property color chrome:   Kirigami.Theme.backgroundColor

    // Outline is the FOREGROUND at low alpha, NOT Kirigami.Theme.separatorColor — that
    // renders #FFFFFF in all five colour sets of this scheme, so binding to it deletes every
    // hairline on a light page. A tint of the text colour is dark on light and light on dark,
    // in every palette member, with no per-theme special case.
    readonly property color outline:  Qt.rgba(Kirigami.Theme.textColor.r,
                                              Kirigami.Theme.textColor.g,
                                              Kirigami.Theme.textColor.b, 0.14)
    readonly property color blue:     Kirigami.Theme.highlightColor
    readonly property color cyan:     Kirigami.Theme.linkColor
    readonly property color violet:   Kirigami.Theme.visitedLinkColor
    readonly property color dangerInk: Kirigami.Theme.negativeTextColor
    readonly property color txt:      Kirigami.Theme.textColor
    // Secondary text is text a person READS — a description, a label, a hint — so it is the
    // primary ink at 72%, exactly as MoOS Settings' mutedColor. It used to be
    // Kirigami.Theme.disabledTextColor, the DISABLED role: KColorScheme fades that 65% toward
    // the background and tints it, which measures 1.6:1 on the light schemes and 2.4:1 on the
    // dark ones. 72% measures 4.8-5.1:1 (light) and 8.4-9.9:1 (dark).
    // tests/test_secondary_text_contrast.py computes it for every shipped scheme.
    readonly property color txt2:     Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                              Kirigami.Theme.textColor.b, 0.72)
    readonly property color accentText: Kirigami.Theme.highlightedTextColor
    readonly property color accent:   Kirigami.Theme.highlightColor  // ONE accent for the OS: the theme's highlight,
                                      // the same teal the selection ring and the window
                                      // decoration already draw. `link` means links again.
    readonly property bool rtl: MoUI.Locale.rtl
    readonly property bool compactRail: win.width < 1080

    // Paths are passed by /usr/bin/moos-store.  Pure QML intentionally has no
    // environment or process access.
    readonly property string cacheDir: win.argValue("--cache=")
    readonly property string indexPath: win.argValue("--index=")
    readonly property string machinePath: win.argValue("--machine=")
    readonly property string jobPath: win.argValue("--job=")
    readonly property string readyPath: win.argValue("--ready=")
    readonly property string updatesPath: win.argValue("--updates=")

    // Catalogue and navigation state.
    property var curatedApps: []
    property var allApps: []
    property var visibleApps: []
    property var bundles: []
    property var indexSources: []
    property var indexStats: ({})
    property string indexToken: ""
    property bool indexReady: false
    property string loadError: ""
    property string page: "discover"
    property string activeCategory: "all"
    property string query: ""
    property var selectedApp: null

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

    readonly property var categoryDefs: [
        { id: "internet",      ar: "الإنترنت",         en: "Internet",       glyph: "globe" },
        { id: "communication", ar: "التواصل",          en: "Communication",  glyph: "chat" },
        { id: "office",        ar: "العمل والمكتب",     en: "Work & Office",  glyph: "briefcase" },
        { id: "development",   ar: "التطوير",           en: "Development",    glyph: "code" },
        { id: "graphics",      ar: "التصميم والصور",    en: "Graphics",       glyph: "camera" },
        { id: "audio-video",   ar: "الصوت والفيديو",    en: "Audio & Video",  glyph: "video" },
        { id: "games",         ar: "الألعاب",           en: "Games",          glyph: "gamepad" },
        { id: "education",     ar: "التعليم",           en: "Education",      glyph: "bulb" },
        { id: "science",       ar: "العلوم",            en: "Science",        glyph: "flask" },
        { id: "utilities",     ar: "الأدوات",           en: "Utilities",      glyph: "gear" },
        { id: "system",        ar: "النظام",            en: "System",         glyph: "monitor" },
        { id: "finance",       ar: "المال والأعمال",    en: "Finance",        glyph: "database" },
        { id: "ai",            ar: "الذكاء الاصطناعي",  en: "AI",             glyph: "brain" },
        { id: "other",         ar: "المزيد",            en: "More",           glyph: "grid" }
    ]

    readonly property var navItems: [
        { id: "discover",   ar: "استكشف",       en: "Discover",   glyph: "spark" },
        { id: "apps",       ar: "كل التطبيقات", en: "All apps",   glyph: "grid" },
        { id: "categories", ar: "الفئات",       en: "Categories", glyph: "boxes" },
        { id: "installed",  ar: "المثبتة",      en: "Installed",  glyph: "check" },
        { id: "updates",    ar: "التحديثات",    en: "Updates",    glyph: "refresh" },
        { id: "sources",    ar: "المصادر",      en: "Sources",    glyph: "orbit" }
    ]

    function argValue(prefix) {
        var args = Qt.application.arguments
        for (var i = 0; i < args.length; ++i)
            if (args[i].indexOf(prefix) === 0)
                return args[i].substring(prefix.length)
        return ""
    }

    function localName(obj) {
        if (!obj) return ""
        if (obj.name) return obj.name
        return win.rtl ? (obj.ar || obj.en || obj.id)
                       : (obj.en || obj.ar || obj.id)
    }

    function localSummary(obj) {
        if (!obj) return ""
        if (obj.summary) return obj.summary
        return win.rtl ? (obj.desc_ar || obj.desc_en || "")
                       : (obj.desc_en || obj.desc_ar || "")
    }

    function localDescription(obj) {
        if (!obj) return ""
        if (obj.description) return obj.description
        return win.localSummary(obj)
    }

    function categoryName(id) {
        if (id === "all") return win.rtl ? "كل التطبيقات" : "All apps"
        for (var i = 0; i < win.categoryDefs.length; ++i) {
            var item = win.categoryDefs[i]
            if (item.id === id) return win.rtl ? item.ar : item.en
        }
        return id
    }

    function categoryGlyph(id) {
        for (var i = 0; i < win.categoryDefs.length; ++i)
            if (win.categoryDefs[i].id === id) return win.categoryDefs[i].glyph
        return "grid"
    }

    function normalizedCategory(app) {
        if (app.category) return app.category
        if (app.cat === "dev") return "development"
        if (app.cat === "fun") return "games"
        if (app.cat === "work") return "office"
        if (app.cat === "ai") return "ai"
        if (app.cat === "ess") return "utilities"
        return "other"
    }

    // The badge on every card. It used to print the CHANNEL an app arrives
    // through -- "flathub" on all 3,343 of them, "npm" on the developer tools --
    // and the owner's rule covers that too: he named F-Droid alongside KWin and
    // Wayland as things he must never see. A channel is machinery.
    //
    // What the badge is FOR is not lost, because the thing a person actually
    // needs before installing is WHO MADE IT, and the card already prints that
    // on its own line: Valve Corporation, Mozilla, The Document Foundation. So
    // the default trusted channel goes unnamed and the badge says only that the
    // app is verified -- and an app arriving from anywhere ELSE still names its
    // origin, because an unusual source is exactly the thing worth reading.
    function sourceLabel(app) {
        if (!app) return ""
        if (app.source === "flathub" || app.source === "flatpak" || app.flatpak_ref) {
            if (app.origin && app.origin !== "" && app.origin !== "flathub")
                return app.origin
            return win.rtl ? "موثّق" : "Verified"
        }
        if (app.install && app.install.kind === "npm")
            return win.rtl ? "أداة مطوّر" : "Developer tool"
        if (app.install && app.install.kind === "web")
            return win.rtl ? "الموقع الرسمي" : "Official website"
        return app.source === "moos" ? "MoOS"
            : (app.source || (win.rtl ? "كتالوج MoOS" : "MoOS catalogue"))
    }

    function reviewDetail(app) {
        if (!app) return ""
        var detail = win.sourceLabel(app)
        if (app.install && app.install.kind === "npm") {
            if (app.install.pkg) detail += " · " + app.install.pkg
            if (app.install.risk)
                detail += " · " + (win.rtl ? "يشغّل سكربتات الحزمة" : "runs package scripts")
        } else if (app.install && app.install.kind === "appimage") {
            detail += " · " + (win.rtl ? "ملف موثّق" : "Verified file")
            if (app.install.version) detail += " " + app.install.version
            detail += " · SHA-256"
        } else if (app.install && app.install.risk) {
            detail += " · " + app.install.risk
        }
        return detail
    }

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
        return app && app.source === "moos" && app.install
            && app.install.kind === "android"
    }

    function hasRunnableLifecycle(app) {
        return win.hasFlatpakLifecycle(app) || win.hasAndroidLifecycle(app)
    }

    function hasInstalledScope(app, scope) {
        if (!app) return false
        if (win.installedScopeOverrides[app.id] !== undefined)
            return win.installedScopeOverrides[app.id].indexOf(scope) >= 0
        if (app.installed_scopes && app.installed_scopes.indexOf(scope) >= 0)
            return true
        return app.installed_scope === scope
    }

    // Curated npm tools and pinned AppImages install into ~/.local; Android
    // applications live behind MoOS's managed compatibility service. All are
    // removed by `moos-storectl remove <id>` (npm uninstall / delete the
    // AppImage / remove the package). They have no Flatpak lifecycle, so they
    // must be named here explicitly. A `web` entry only opened a vendor page;
    // nothing of ours is on disk and it is deliberately excluded.
    function hasCuratedLifecycle(app) {
        return app && app.source === "moos" && app.install
            && (app.install.kind === "npm" || app.install.kind === "appimage"
                || app.install.kind === "android")
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
            if (app && !win.isInstalled(app) && !next[ids[i]]) {
                next[ids[i]] = true
                ++added
                ++selected
            }
        }
        win.picks = next
        win.pickCount = Object.keys(next).length
        win.flash((win.rtl ? "أُضيف إلى قائمة التثبيت: " : "Added to install list: ") + added)
    }

    function clearPicks() {
        win.picks = ({})
        win.pickCount = 0
    }

    function appById(id) {
        for (var i = 0; i < win.allApps.length; ++i)
            if (win.allApps[i].id === id) return win.allApps[i]
        return null
    }

    function categoryCount(id) {
        var count = 0
        for (var i = 0; i < win.allApps.length; ++i)
            if (win.normalizedCategory(win.allApps[i]) === id) ++count
        return count
    }

    function installedCount() {
        var count = 0
        for (var i = 0; i < win.allApps.length; ++i)
            if (win.isInstalled(win.allApps[i])) ++count
        return count
    }

    function verifiedCount() {
        if (win.indexStats.verified !== undefined) return win.indexStats.verified
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
        var live = {}
        for (var i = 0; i < win.allApps.length; ++i)
            live[win.allApps[i].id] = win.allApps[i]
        var ranked = []
        for (var j = 0; j < win.curatedApps.length; ++j) {
            var entry = live[win.curatedApps[j].id] || win.curatedApps[j]
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

    // ── What MoOS can run ────────────────────────────────────────────────────
    //
    // Mo Store used to answer "does MoOS run Windows programs?" by putting the
    // Windows RUNTIME in its first row as if it were an app somebody chooses.
    // That names the engine, and a person who wants to run a program they
    // downloaded has no reason to learn what it is called. The promise still has
    // to be visible, so it is stated as a capability, in the registry's own
    // bilingual words, and tapping one opens the file picker for exactly the
    // files that capability accepts.
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
            // neither wine nor waydroid -- told the owner it runs Windows
            // programs and Android apps, and the picker it opened could only
            // ever fail. A missing or null list means "could not tell", and the
            // strip then shows everything exactly as it did before.
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
            // strip. It must never invent a capability it cannot name.
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

    // The header's "Add app" (StoreHeader.qml) opens the same picker.
    function openApplicationPicker() {
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
            win.bundles = keptBundles
            var normalized = []
            for (var i = 0; i < apps.length; ++i) {
                if (!win.curatedRunsHere(apps[i])) continue
                var source = Object.assign({}, apps[i])
                source.name = win.localName(source)
                source.summary = win.localSummary(source)
                source.description = source.summary
                source.category = win.normalizedCategory(source)
                source.curated = true
                source.installable = true
                source.installed = false
                normalized.push(source)
            }
            win.curatedApps = normalized
            win.allApps = normalized
            win.loadEngines()
            win.recompute()
        } catch (error) {
            win.loadError = "" + error
        }
    }

    function loadIndex() {
        try {
            var document = win.readJson(win.indexPath)
            if (!document || !document.apps || document.apps.length === 0) return false
            var token = JSON.stringify(document.generation || {})
            if (token === win.indexToken) return true
            win.indexToken = token
            win.allApps = document.apps
            win.bundles = document.bundles || win.bundles
            win.indexSources = document.sources || []
            win.indexStats = document.stats || ({})
            win.indexReady = true
            win.recompute()
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
                        || !win.matchesExpectedJob(document))
                    return false
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
                    win.flash(win.rtl ? "اكتملت العملية بنجاح" : "All done")
                } else if (document.state === "partial") {
                    win.flash(win.rtl ? "اكتمل بعض العناصر — راجع التفاصيل" : "Some items need attention")
                } else if (document.state !== "cancelled") {
                    win.flash(document.message || (win.rtl ? "تعذّر إكمال العملية" : "The operation did not complete"))
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
                    if (win.page === "updates")
                        Qt.callLater(function() { win.checkUpdates() })
                }
            }
            win.recompute()
            return true
        } catch (error) {
            return false
        }
    }

    function updateItems() {
        var items = win.updates.items || []
        var apps = []
        for (var i = 0; i < items.length; ++i)
            if (items[i].kind === "app") apps.push(items[i])
        return apps
    }

    function updateComponentCount() {
        var items = win.updates.items || []
        return Math.max(0, items.length - win.updateItems().length)
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

    function recompute() {
        var q = win.query.trim().toLowerCase()
        var out = []
        for (var i = 0; i < win.allApps.length; ++i) {
            var app = win.allApps[i]
            if (win.page === "installed" && !win.isInstalled(app)) continue
            if ((win.page === "apps" || win.page === "categories"
                    || win.page === "installed")
                    && win.activeCategory !== "all"
                    && win.normalizedCategory(app) !== win.activeCategory) continue
            if (q !== "") {
                var haystack = (win.localName(app) + " " + win.localSummary(app)
                    + " " + (app.id || "") + " " + (app.developer || "")
                    + " " + (app.categories || []).join(" ")).toLowerCase()
                if (haystack.indexOf(q) < 0) continue
            }
            out.push(app)
        }
        out.sort(function(a, b) {
            if (win.page === "installed") {
                var an = win.localName(a).toLowerCase()
                var bn = win.localName(b).toLowerCase()
                return an < bn ? -1 : (an > bn ? 1 : 0)
            }
            var ac = a.curated === true ? 1 : 0
            var bc = b.curated === true ? 1 : 0
            if (ac !== bc) return bc - ac
            var av = a.verified === true ? 1 : 0
            var bv = b.verified === true ? 1 : 0
            if (av !== bv) return bv - av
            var aname = win.localName(a).toLowerCase()
            var bname = win.localName(b).toLowerCase()
            return aname < bname ? -1 : (aname > bname ? 1 : 0)
        })
        win.visibleApps = out
    }

    function navigate(target) {
        win.page = target
        if (target !== "apps" && target !== "categories") win.activeCategory = "all"
        win.recompute()
    }

    function openCategory(category) {
        win.activeCategory = category
        win.page = "apps"
        win.recompute()
    }

    function openDetails(app) {
        win.selectedApp = app
        details.open()
    }

    function installOne(app) {
        win.clearPicks()
        win.setPicked(app.id, true)
        review.open()
    }

    // The selection shelf (SelectionShelf.qml) opens the review and steps aside while it is open.
    readonly property bool reviewOpened: review.opened
    function openReview() {
        review.open()
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
        // unsupported, and the question that decides it has not been asked. Saying
        // "confirm before installation" here would promise an install for a file
        // MoOS is about to refuse.
        win.flash(win.local("يفحص MoOS الملف ويسألك قبل أي إجراء.",
                            "MoOS is checking the file and will ask before doing anything."))
        // An install started from this window must be visible IN this window.
        // Every other MoosStore action restarts the poll for exactly this reason.
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

    DropOverlay { win: win; visible: appDropTarget.containsDrag }

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
        details.close()
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

    function openSourceEngine(action) {
        if (action === "refresh") {
            win.maybeRefreshCatalog(true)
            return
        }
        if (action === "permissions") {
            var flatseal = win.appById("com.github.tchx84.Flatseal")
            if (!flatseal) {
                win.flash(win.rtl ? "أداة الصلاحيات غير موجودة في الفهرس" : "The permissions tool is not in the index")
            } else if (win.isInstalled(flatseal)) {
                win.runSelected(flatseal)
            } else {
                win.installOne(flatseal)
            }
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

    onPageChanged: {
        recompute()
        // Ask only when the user is actually looking at the page, and only when
        // the answer is not already in hand — the check costs a process and can
        // touch the network.
        if (win.page === "updates" && win.updatesState === "unknown")
            Qt.callLater(function() { win.checkUpdates() })
    }
    onActiveCategoryChanged: recompute()
    onQueryChanged: recompute()

    // ── Opening one app's page from outside ─────────────────────────────────
    //
    // `moos-store --app=<id>`, an appstream:// link and Plasma's "Uninstall or Manage
    // Add-ons…" reach this window as one `--open-app=<id>` argument: in its own arguments at
    // launch, and through activateRequested() when the Store is already open (moos-qml-shell
    // forwards the second launch's argv). The launcher validated the id; it is validated again
    // here, where the window owns the boundary. A link only ever SHOWS an app: what happens
    // next is the person's choice on its page.
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

    // The search field lives in the header (StoreHeader.qml).
    function focusSearch() {
        storeHeader.focusSearch()
    }

    Shortcut {
        sequences: ["Ctrl+K", "Ctrl+F"]
        onActivated: win.focusSearch()
    }

    Shortcut {
        sequence: "Escape"
        onActivated: {
            if (details.opened) details.close()
            else if (review.opened) review.close()
            else if (storeHeader.searchText !== "") storeHeader.clearSearch()
        }
    }

    // Shared palette-aware symbolic vocabulary; application artwork remains
    // AppStream-provided, while every control glyph comes from the MoOS layer.
    // Glyph.qml draws them; the alias table stays here, beside the window's palette.
    readonly property var glyphAliases: ({
        "android": "android-apps", "brain": "ai", "doc": "document",
        "gamepad": "gaming", "gear": "settings", "mic": "microphone",
        "monitor": "system", "note": "music", "warn": "warning",
        "download": "install", "disk": "storage"
    })
    function glyphIcon(name) {
        return MoUI.SymbolCatalog.resolve(win.glyphAliases[name] || name || "spark")
    }

    // A focus ring nobody can see is no focus ring. Every focusable here is a bare
    // Rectangle inside a clipped Flickable, so Tab could park focus outside the viewport
    // and PageDown moved nothing. Enforced at the window, not per delegate — one wired by
    // hand is one somebody forgets:
    //   1. whatever HOLDS focus is scrolled into view, in both axes, in whichever
    //      Flickable ancestors clip it (the app grid, the chip row, the detail sheet);
    //   2. PageDown/PageUp move each content pane via pageScrollKeys(), reached by key
    //      bubbling from any focused item inside the pane.
    onActiveFocusItemChanged: MoUI.KeyboardViewport.revealFocus(win.activeFocusItem)

    // Tab out of the catalogue grid (CatalogPage.qml) lands on the rail's first entry.
    function focusFirstNavItem(reason) {
        rail.focusFirstNavItem(reason)
    }

    // Layered background: palette-driven, restrained, and alive without making
    // text compete with a wallpaper.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Qt.darker(win.canvas, 1.04) }
            GradientStop { position: 0.58; color: win.canvas }
            GradientStop { position: 1; color: win.chrome }
        }
    }
    Rectangle {
        width: 620
        height: 620
        radius: height / 2
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: -390
        anchors.rightMargin: -190
        color: win.accent
        opacity: 0.1
    }
    Rectangle {
        width: 480
        height: 480
        radius: height / 2
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.bottomMargin: -300
        anchors.leftMargin: -250
        color: win.blue
        opacity: 0.07
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
                Layout.fillWidth: true
                Layout.fillHeight: true

                // Discover page.
                DiscoverPage { win: win }

                // Virtualized catalogue / installed page.
                CatalogPage { win: win }

                // Category overview.
                CategoriesPage { win: win }

                // Updates.
                UpdatesPage { win: win }

                // Sources: engines are capabilities behind Mo Store, never extra
                // launchers competing in the application menu.
                SourcesPage { win: win }
            }
        }
    }

    // Selection shelf.  It never preselects software on launch.
    SelectionShelf { win: win }

    // Real transaction status shelf.  Null progress is shown as indeterminate,
    // never replaced with a made-up percentage.
    JobShelf { win: win }

    // App details.
    AppDetailsSheet { id: details; win: win }

    // One explicit review for a single app or a whole collection.
    ReviewSheet { id: review; win: win }

    StoreToast { id: toast; win: win }
}
