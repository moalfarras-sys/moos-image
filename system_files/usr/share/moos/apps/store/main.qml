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
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

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
    readonly property color txt:      Kirigami.Theme.textColor
    readonly property color txt2:     Kirigami.Theme.disabledTextColor
    readonly property color onAccent: Kirigami.Theme.highlightedTextColor
    readonly property color accent:   Kirigami.Theme.highlightColor  // ONE accent for the OS: the theme's highlight,
                                      // the same teal the selection ring and the window
                                      // decoration already draw. `link` means links again.
    readonly property bool rtl: Qt.locale().textDirection === Qt.RightToLeft
    readonly property bool compactRail: win.width < 1080

    // Paths are passed by /usr/bin/moos-store.  Pure QML intentionally has no
    // environment or process access.
    readonly property string cacheDir: win.argValue("--cache=")
    readonly property string indexPath: win.argValue("--index=")
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

    function sourceLabel(app) {
        if (!app) return ""
        if (app.source === "flathub" || app.source === "flatpak" || app.flatpak_ref)
            return app.origin && app.origin !== "" ? app.origin : "Flathub"
        if (app.install && app.install.kind === "npm")
            return win.rtl ? "أداة مطوّر · npm" : "Developer tool · npm"
        if (app.install && app.install.kind === "web")
            return win.rtl ? "الموقع الرسمي" : "Official website"
        return app.source === "moos" ? "MoOS" : (app.source || "Flatpak")
    }

    function reviewDetail(app) {
        if (!app) return ""
        var detail = win.sourceLabel(app)
        if (app.install && app.install.kind === "npm") {
            if (app.install.pkg) detail += " · " + app.install.pkg
            if (app.install.risk)
                detail += " · " + (win.rtl ? "يشغّل سكربتات الحزمة" : "runs package scripts")
        } else if (app.install && app.install.kind === "appimage") {
            detail += " · AppImage"
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

    function hasInstalledScope(app, scope) {
        if (!app) return false
        if (win.installedScopeOverrides[app.id] !== undefined)
            return win.installedScopeOverrides[app.id].indexOf(scope) >= 0
        if (app.installed_scopes && app.installed_scopes.indexOf(scope) >= 0)
            return true
        return app.installed_scope === scope
    }

    // Curated npm tools and pinned AppImages install into ~/.local and are
    // removed by `moos-storectl remove <id>` (npm uninstall / delete the
    // AppImage). They have no Flatpak lifecycle, so canRemove used to return
    // false for them and the Remove button never appeared — a tool you could
    // install but never uninstall. A `web` entry only opened a vendor page, so
    // nothing of ours is on disk and it is deliberately excluded.
    function hasCuratedLifecycle(app) {
        return app && app.source === "moos" && app.install
            && (app.install.kind === "npm" || app.install.kind === "appimage")
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

    function curatedFeatured(limit) {
        var out = []
        for (var i = 0; i < win.allApps.length && out.length < limit; ++i) {
            var app = win.allApps[i]
            if (app.curated === true || app.popular === true) out.push(app)
        }
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
        toastLabel.text = message
        toast.open()
        toastTimer.restart()
    }

    function readJson(path) {
        if (!path || path === "") return null
        var request = new XMLHttpRequest()
        request.open("GET", "file://" + path + "?v=" + Date.now(), false)
        request.send()
        if (!request.responseText) return null
        return JSON.parse(request.responseText)
    }

    function loadCurated() {
        try {
            var request = new XMLHttpRequest()
            request.open("GET", "file:///usr/share/moos/store/catalog.json", false)
            request.send()
            var document = JSON.parse(request.responseText)
            win.bundles = document.bundles || []
            var apps = document.apps || []
            var normalized = []
            for (var i = 0; i < apps.length; ++i) {
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
                            && (item.message || "").indexOf("not installed") >= 0)) {
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
                       && (item.message || "") === "Already installed system-wide") {
                next[item.id] = true
                nextScopes[item.id] = ["system"]
            } else if (item.state === "skipped"
                       && (item.message || "") === "Already installed for this user") {
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
        if (!win.hasFlatpakLifecycle(app)) return
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

    Component.onCompleted: {
        win.loadCurated()
        win.loadIndex()
        win.adoptRecentUpdates()
        win.loadJob()
        if (win.jobIsActive()) jobPoll.start()
        Qt.callLater(function() { win.maybeRefreshCatalog(false) })
        indexPoll.start()
    }

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

    Shortcut {
        sequences: ["Ctrl+K", "Ctrl+F"]
        onActivated: searchField.forceActiveFocus()
    }

    Shortcut {
        sequence: "Escape"
        onActivated: {
            if (details.opened) details.close()
            else if (review.opened) review.close()
            else if (searchField.text !== "") searchField.clear()
        }
    }

    // Stroke-only glyphs keep navigation crisp while real application artwork
    // comes from AppStream.
    readonly property var glyphs: ({
        "compass":  "<circle cx='12' cy='12' r='9'/><path d='M15.5 8.5l-2.4 5.1-5.1 2.4 2.4-5.1z'/>",
        "gamepad":  "<rect x='2.5' y='7.5' width='19' height='10' rx='5'/><path d='M7 11v3M5.5 12.5h3'/><circle cx='15.5' cy='11.5' r='1.1'/><circle cx='18' cy='14' r='1.1'/>",
        "code":     "<path d='M9 8l-4.5 4L9 16M15 8l4.5 4L15 16'/>",
        "spark":    "<path d='M12 3l1.9 6.1L20 11l-6.1 1.9L12 19l-1.9-6.1L4 11l6.1-1.9z'/>",
        "globe":    "<circle cx='12' cy='12' r='9'/><path d='M3 12h18'/><path d='M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18'/>",
        "shield":   "<path d='M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z'/>",
        "camera":   "<rect x='3' y='7' width='18' height='13' rx='3'/><circle cx='12' cy='13.5' r='4'/><path d='M8.5 7l1.5-2.5h4L15.5 7'/>",
        "mic":      "<rect x='9' y='3' width='6' height='11' rx='3'/><path d='M5 11a7 7 0 0 0 14 0'/><path d='M12 18v3'/>",
        "doc":      "<path d='M6 3h8l4 4v14H6z'/><path d='M14 3v4h4'/><path d='M9 13h6M9 16.5h6'/>",
        "note":     "<circle cx='7' cy='18' r='2.4'/><circle cx='17' cy='15.5' r='2.4'/><path d='M9.4 18V6.5l10-2V15.5'/>",
        "mail":     "<rect x='3' y='5' width='18' height='14' rx='2.5'/><path d='M3.5 7l8.5 6 8.5-6'/>",
        "lock":     "<rect x='5' y='11' width='14' height='9' rx='2.5'/><path d='M8 11V8a4 4 0 0 1 8 0v3'/>",
        "flask":    "<path d='M9.5 3h5M10.5 3v5.5L6 17.5a2 2 0 0 0 1.8 3h8.4a2 2 0 0 0 1.8-3L13.5 8.5V3'/><path d='M8 15.5h8'/>",
        "joystick": "<circle cx='12' cy='6' r='3'/><path d='M12 9v6'/><path d='M6 21c1-4 3-6 6-6s5 2 6 6z'/>",
        "target":   "<circle cx='12' cy='12' r='9'/><circle cx='12' cy='12' r='5'/><circle cx='12' cy='12' r='1.4'/>",
        "gear":     "<circle cx='12' cy='12' r='3.2'/><path d='M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.2 5.2l2.1 2.1M16.7 16.7l2.1 2.1M18.8 5.2l-2.1 2.1M7.3 16.7l-2.1 2.1'/>",
        "chat":     "<path d='M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H9l-5 4z'/>",
        "car":      "<path d='M4 13l2.2-5.2h11.6L20 13'/><rect x='3' y='13' width='18' height='5' rx='2'/><circle cx='7.5' cy='18.5' r='1.4'/><circle cx='16.5' cy='18.5' r='1.4'/>",
        "bolt":     "<path d='M13 2.5L5 13.5h5l-1 8 8-11h-5z'/>",
        "container":"<rect x='3' y='8' width='18' height='11' rx='1.5'/><path d='M8 8v11M12 8v11M16 8v11'/><path d='M3 8l3-3h12l3 3'/>",
        "database": "<ellipse cx='12' cy='6' rx='7' ry='3'/><path d='M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6'/><path d='M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3'/>",
        "android":  "<path d='M6 12a6 6 0 0 1 12 0'/><rect x='6' y='12' width='12' height='7' rx='2'/><path d='M8 8.2L7 6M16 8.2L17 6M9.5 10h.01M14.5 10h.01'/>",
        "cube":     "<path d='M12 3l8 4.5v9L12 21l-8-4.5v-9z'/><path d='M12 3v18M4 7.5l8 4.5 8-4.5'/>",
        "orbit":    "<circle cx='12' cy='12' r='2.6'/><path d='M6.5 6.5a12 12 0 0 0-1.7 1.8C2.6 11.2 2.2 14 3.8 15.6c1.8 1.8 5.6 1 9.4-1.9s5.9-6.6 4.1-8.4c-1.2-1.2-3.5-1-6 .3'/>",
        "diamond":  "<path d='M12 3l6 6-6 12-6-12z'/><path d='M6 9h12'/>",
        "brain":    "<path d='M9.5 5.5A3 3 0 0 0 6.5 8.7 3 3 0 0 0 5.5 14c0 2 1.8 3.2 3.8 3.2M14.5 5.5a3 3 0 0 1 3 3.2 3 3 0 0 1 1 5.3c0 2-1.8 3.2-3.8 3.2M12 5v14'/>",
        "bulb":     "<path d='M9 17.5h6M10 20.5h4'/><path d='M12 3a6 6 0 0 0-4 10.4c.8.9.9 1.7.9 2.6h6.2c0-.9.1-1.7.9-2.6A6 6 0 0 0 12 3z'/>",
        "wave":     "<path d='M3 12h2.2M8 8v8M11.5 5v14M15 8.5v7M18.8 12H21'/>",
        "monitor":  "<rect x='3' y='4' width='18' height='12' rx='2'/><path d='M9 20h6M12 16v4'/>",
        "briefcase":"<rect x='3' y='8' width='18' height='12' rx='2.5'/><path d='M9 8V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2'/><path d='M3 13h18'/>",
        "gem":      "<path d='M12 3L5 9.5 12 21l7-11.5z'/><path d='M5 9.5h14M12 3l-2.6 6.5L12 21l2.6-11.5z'/>",
        "pen":      "<path d='M4 20l1.2-4.2L16.4 4.6a2 2 0 0 1 2.8 0l.2.2a2 2 0 0 1 0 2.8L8.2 18.8z'/><path d='M14.5 6.5l3 3'/>",
        "video":    "<rect x='3' y='6' width='13' height='12' rx='2.5'/><path d='M16 10.5l5-3v9l-5-3z'/>",
        "home":     "<path d='M3.5 11L12 3.5l8.5 7.5'/><path d='M5.5 9.5V21h13V9.5M9.5 21v-6h5v6'/>",
        "grid":     "<rect x='3' y='3' width='7' height='7' rx='2'/><rect x='14' y='3' width='7' height='7' rx='2'/><rect x='3' y='14' width='7' height='7' rx='2'/><rect x='14' y='14' width='7' height='7' rx='2'/>",
        "boxes":    "<path d='M4 7l4-2.5L12 7 8 9.5zM12 7l4-2.5L20 7l-4 2.5zM8 14.5l4-2.5 4 2.5-4 2.5z'/><path d='M4 7v5l4 2.5 4-2.5V7M12 7v5l4 2.5 4-2.5V7M8 14.5v4.5l4 2.5 4-2.5v-4.5'/>",
        "check":    "<path d='M4.5 12.5l5 5L20 6.5'/>",
        "refresh":  "<path d='M20 8a8.5 8.5 0 0 0-14.5-2L3 8.5'/><path d='M3 4v4.5h4.5M4 16a8.5 8.5 0 0 0 14.5 2L21 15.5'/><path d='M21 20v-4.5h-4.5'/>",
        "search":   "<circle cx='10.5' cy='10.5' r='6.5'/><path d='M15.5 15.5L21 21'/>",
        "download": "<path d='M12 3v12M7 10l5 5 5-5'/><path d='M4 20h16'/>",
        "trash":    "<path d='M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6'/>",
        "external": "<path d='M13 4h7v7M20 4l-9 9'/><path d='M18 14v6H4V6h6'/>",
        "star":     "<path d='M12 3l2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z'/>"
    })

    function hex2(number) {
        var value = Math.round(Math.max(0, Math.min(1, number)) * 255).toString(16)
        return value.length < 2 ? "0" + value : value
    }

    function hexColor(colour) {
        return "#" + win.hex2(colour.r) + win.hex2(colour.g) + win.hex2(colour.b)
    }

    function glyphURL(name, colour, stroke) {
        var inner = win.glyphs[name] || win.glyphs.spark
        var svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
            + "stroke='" + win.hexColor(colour) + "' stroke-opacity='" + colour.a.toFixed(3) + "' "
            + "stroke-width='" + stroke + "' stroke-linecap='round' stroke-linejoin='round'>"
            + inner + "</svg>"
        return "data:image/svg+xml;base64," + Qt.btoa(Array.from(svg))
    }

    component Glyph: Image {
        property string name: "spark"
        property color tint: win.txt
        property real stroke: 1.7
        source: win.glyphURL(name, tint, stroke)
        sourceSize.width: Math.max(2, width)
        sourceSize.height: Math.max(2, height)
        fillMode: Image.PreserveAspectFit
        smooth: true
    }

    component ActionButton: Rectangle {
        id: action
        property string label: ""
        property string glyphName: ""
        property bool primary: false
        property bool destructive: false
        property var triggered
        implicitWidth: actionRow.implicitWidth + 28
        implicitHeight: 40
        radius: 13
        opacity: enabled ? 1 : 0.45
        color: primary ? (actionTap.pressed ? Qt.darker(win.accent, 1.12)
                                             : actionHover.hovered ? Qt.lighter(win.accent, 1.07) : win.accent)
                       : actionHover.hovered ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 1)
                                             : Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.74)
        border.width: primary ? 0 : 1
        border.color: destructive ? win.violet : (actionHover.hovered ? win.accent : win.outline)
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: label
        HoverHandler { id: actionHover; enabled: action.enabled }
        TapHandler {
            id: actionTap
            enabled: action.enabled
            onTapped: if (action.triggered) action.triggered()
        }
        Keys.onReturnPressed: if (action.enabled && action.triggered) action.triggered()
        Keys.onSpacePressed: if (action.enabled && action.triggered) action.triggered()
        Behavior on color { ColorAnimation { duration: 120 } }
        RowLayout {
            id: actionRow
            anchors.centerIn: parent
            spacing: 7
            Glyph {
                visible: action.glyphName !== ""
                name: action.glyphName
                tint: action.primary ? win.onAccent
                                     : action.destructive ? win.violet : win.txt
                Layout.preferredWidth: 16
                Layout.preferredHeight: 16
            }
            Text {
                text: action.label
                color: action.primary ? win.onAccent
                                      : action.destructive ? win.violet : win.txt
                font.family: win.uiFont
                font.pixelSize: 13
                font.bold: true
            }
        }
    }

    component AppArtwork: Rectangle {
        id: artwork
        property var app: null
        property int size: 52
        implicitWidth: size
        implicitHeight: size
        radius: Math.round(size * 0.28)
        color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.12)
        border.width: 1
        border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.22)
        Image {
            id: realIcon
            anchors.centerIn: parent
            width: artwork.size * 0.72
            height: width
            source: artwork.app && artwork.app.icon ? artwork.app.icon : ""
            sourceSize.width: Math.max(64, width)
            sourceSize.height: Math.max(64, height)
            fillMode: Image.PreserveAspectFit
            smooth: true
            asynchronous: true
            visible: status === Image.Ready
        }
        Glyph {
            anchors.centerIn: parent
            width: artwork.size * 0.52
            height: width
            name: artwork.app && artwork.app.glyph
                  ? artwork.app.glyph : win.categoryGlyph(win.normalizedCategory(artwork.app || ({})))
            tint: win.accent
            stroke: 1.65
            visible: !realIcon.visible
        }
    }

    component SourceBadge: Rectangle {
        id: badge
        property var app: null
        implicitHeight: 22
        implicitWidth: badgeRow.implicitWidth + 15
        radius: 11
        color: Qt.rgba(win.txt2.r, win.txt2.g, win.txt2.b, 0.12)
        RowLayout {
            id: badgeRow
            anchors.centerIn: parent
            spacing: 4
            Glyph {
                name: badge.app && badge.app.verified === true ? "check"
                                                              : badge.app && badge.app.flatpak_ref ? "shield" : "external"
                tint: badge.app && badge.app.verified === true ? win.accent : win.txt2
                Layout.preferredWidth: 11
                Layout.preferredHeight: 11
            }
            Text {
                text: win.sourceLabel(badge.app)
                color: badge.app && badge.app.verified === true ? win.accent : win.txt2
                font.family: win.uiFont
                font.pixelSize: 10
                font.bold: true
            }
        }
    }

    component AppCard: Rectangle {
        id: card
        required property var app
        property bool selected: win.isPicked(app.id)
        property bool installed: win.isInstalled(app)
        radius: 20
        color: cardHover.hovered
             ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.98)
             : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.82)
        border.width: selected ? 2 : 1
        border.color: card.selected ? win.accent
                     : cardHover.hovered ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.56)
                                         : win.outline
        scale: cardHover.hovered ? 1.012 : 1
        activeFocusOnTab: true
        Accessible.role: Accessible.ListItem
        Accessible.name: win.localName(app) + ", " + win.sourceLabel(app)
        HoverHandler { id: cardHover }
        TapHandler { onTapped: win.openDetails(card.app) }
        Keys.onReturnPressed: win.openDetails(card.app)
        Keys.onSpacePressed: win.openDetails(card.app)
        Behavior on color { ColorAnimation { duration: 130 } }
        Behavior on border.color { ColorAnimation { duration: 130 } }
        Behavior on scale { NumberAnimation { duration: 130; easing.type: Easing.OutQuad } }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 9
            RowLayout {
                Layout.fillWidth: true
                spacing: 11
                AppArtwork { app: card.app; size: 48 }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        Layout.fillWidth: true
                        text: win.localName(card.app)
                        color: win.txt
                        font.family: win.uiFont
                        font.pixelSize: 15
                        font.bold: true
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: card.app.developer || card.app.id
                        color: win.txt2
                        font.family: win.uiFont
                        font.pixelSize: 10
                        elide: Text.ElideRight
                    }
                }
                Rectangle {
                    visible: card.installed
                    Layout.preferredWidth: 24
                    Layout.preferredHeight: 24
                    radius: 12
                    color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.15)
                    Glyph { anchors.centerIn: parent; width: 13; height: 13; name: "check"; tint: win.accent }
                }
            }
            Text {
                Layout.fillWidth: true
                text: win.localSummary(card.app)
                color: win.txt2
                font.family: win.uiFont
                font.pixelSize: 11
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                spacing: 7
                SourceBadge { app: card.app }
                Item { Layout.fillWidth: true }
                ActionButton {
                    enabled: !card.installed || win.hasFlatpakLifecycle(card.app)
                    label: card.installed
                        ? win.hasFlatpakLifecycle(card.app)
                            ? (win.rtl ? "افتح" : "Open")
                            : (win.rtl ? "جاهز" : "Ready")
                        : card.selected ? (win.rtl ? "مُضاف" : "Added")
                        : win.isWeb(card.app) ? (win.rtl ? "الموقع" : "Website")
                        : (win.rtl ? "تثبيت" : "Install")
                    glyphName: card.installed
                        ? win.hasFlatpakLifecycle(card.app) ? "external" : "check"
                        : card.selected ? "check" : "download"
                    primary: card.selected
                    triggered: function() {
                        if (card.installed && win.hasFlatpakLifecycle(card.app))
                            win.runSelected(card.app)
                        else if (card.selected) win.setPicked(card.app.id, false)
                        else win.installOne(card.app)
                    }
                }
            }
        }
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
        radius: 310
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
        radius: 240
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
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: win.compactRail ? 82 : 222
            color: Qt.rgba(win.chrome.r, win.chrome.g, win.chrome.b, 0.82)
            border.width: 0
            Behavior on Layout.preferredWidth { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 62
                    spacing: 11
                    Rectangle {
                        Layout.preferredWidth: 46
                        Layout.preferredHeight: 46
                        radius: 15
                        color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.12)
                        border.width: 1
                        border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.26)
                        Image {
                            anchors.centerIn: parent
                            width: 36
                            height: 36
                            source: "file:///usr/share/moos/moos-logo.png"
                            sourceSize.width: 48
                            sourceSize.height: 48
                        }
                    }
                    ColumnLayout {
                        visible: !win.compactRail
                        Layout.fillWidth: true
                        spacing: -1
                        Text {
                            text: "MO STORE"
                            color: win.txt
                            font.family: win.uiFont
                            font.pixelSize: 16
                            font.bold: true
                            font.letterSpacing: 1.5
                        }
                        Text {
                            text: win.rtl ? "مركز تطبيقات MoOS" : "MoOS app centre"
                            color: win.txt2
                            font.family: win.uiFont
                            font.pixelSize: 10
                        }
                    }
                }

                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: win.outline; opacity: 0.55 }
                Item { Layout.preferredHeight: 2 }

                Repeater {
                    model: win.navItems
                    delegate: Rectangle {
                        id: nav
                        required property var modelData
                        readonly property bool active: win.page === nav.modelData.id
                        Layout.fillWidth: true
                        Layout.preferredHeight: 46
                        radius: 14
                        color: active ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                                      : navHover.hovered ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.72)
                                                         : "transparent"
                        border.width: active ? 1 : 0
                        border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.34)
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: win.rtl ? nav.modelData.ar : nav.modelData.en
                        HoverHandler { id: navHover }
                        TapHandler { onTapped: win.navigate(nav.modelData.id) }
                        Keys.onReturnPressed: win.navigate(nav.modelData.id)
                        Behavior on color { ColorAnimation { duration: 120 } }
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: win.compactRail ? 15 : 14
                            anchors.rightMargin: 12
                            spacing: 12
                            Glyph {
                                name: nav.modelData.glyph
                                tint: nav.active ? win.accent : win.txt2
                                Layout.preferredWidth: 19
                                Layout.preferredHeight: 19
                            }
                            Text {
                                visible: !win.compactRail
                                Layout.fillWidth: true
                                text: win.rtl ? nav.modelData.ar : nav.modelData.en
                                color: nav.active ? win.txt : win.txt2
                                font.family: win.uiFont
                                font.pixelSize: 13
                                font.bold: nav.active
                            }
                            Rectangle {
                                visible: !win.compactRail && nav.modelData.id === "installed" && win.installedCount() > 0
                                implicitWidth: installedBadge.implicitWidth + 12
                                implicitHeight: 22
                                radius: 11
                                color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                                Text {
                                    id: installedBadge
                                    anchors.centerIn: parent
                                    text: win.installedCount()
                                    color: win.accent
                                    font.family: win.uiFont
                                    font.pixelSize: 10
                                    font.bold: true
                                }
                            }
                            // Only once the count is genuinely known — an
                            // un-checked page must not imply "nothing pending".
                            Rectangle {
                                visible: !win.compactRail && nav.modelData.id === "updates"
                                    && win.updatesState === "known" && win.updateItems().length > 0
                                implicitWidth: updatesBadge.implicitWidth + 12
                                implicitHeight: 22
                                radius: 11
                                color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                                Text {
                                    id: updatesBadge
                                    anchors.centerIn: parent
                                    text: win.updateItems().length
                                    color: win.accent
                                    font.family: win.uiFont
                                    font.pixelSize: 10
                                    font.bold: true
                                }
                            }
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: win.compactRail ? 50 : 72
                    radius: 16
                    color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.7)
                    border.width: 1
                    border.color: win.outline
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 9
                        Rectangle {
                            Layout.preferredWidth: 28
                            Layout.preferredHeight: 28
                            radius: 14
                            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                            // The rail's working light. It belongs to the line beside
                            // it — "Building catalogue…" — so it pulses while the index
                            // is actually being built and goes solid the moment it is
                            // ready.
                            //
                            // It used to pulse forever, with no `running:` guard at all.
                            // One 8 px dot animating without end keeps the QML render
                            // loop at full frame rate, and repainting a 4K window for it
                            // measured ~11% of a CPU core on an idle desktop — paid by
                            // every session that merely had the Store window restored
                            // behind other windows. Every other infinite animation MoOS
                            // ships was already guarded; this was the one that was not.
                            Rectangle {
                                id: railWorkingDot
                                anchors.centerIn: parent
                                width: 8
                                height: 8
                                radius: 4
                                color: win.hasFlatpakCatalog() ? win.accent : win.violet
                                property real pulse: 1
                                opacity: railWorkingPulse.running ? railWorkingDot.pulse : 1
                                SequentialAnimation {
                                    id: railWorkingPulse
                                    running: !win.indexReady && win.motionEnabled
                                    loops: Animation.Infinite
                                    NumberAnimation {
                                        target: railWorkingDot; property: "pulse"
                                        from: 0.35; to: 1; duration: 850
                                    }
                                    NumberAnimation {
                                        target: railWorkingDot; property: "pulse"
                                        from: 1; to: 0.35; duration: 850
                                    }
                                }
                            }
                        }
                        ColumnLayout {
                            visible: !win.compactRail
                            Layout.fillWidth: true
                            spacing: 0
                            Text {
                                text: !win.indexReady
                                    ? (win.rtl ? "يُجهّز الفهرس…" : "Building catalogue…")
                                    : win.hasFlatpakCatalog()
                                        ? (win.rtl ? "الفهرس الكامل جاهز" : "Full catalogue ready")
                                        : (win.rtl ? "الفهرس المحدود · يحتاج اتصالًا" : "Limited catalogue · connection needed")
                                color: win.txt
                                font.family: win.uiFont
                                font.pixelSize: 11
                                font.bold: true
                            }
                            Text {
                                text: win.allApps.length + (win.rtl ? " تطبيق" : " apps")
                                color: win.txt2
                                font.family: win.uiFont
                                font.pixelSize: 10
                            }
                        }
                    }
                }
            }
            Rectangle {
                anchors.right: win.rtl ? undefined : parent.right
                anchors.left: win.rtl ? parent.left : undefined
                width: 1
                height: parent.height
                color: win.outline
                opacity: 0.62
            }
        }

        // Main surface.
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 82
                color: Qt.rgba(win.chrome.r, win.chrome.g, win.chrome.b, 0.55)
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 26
                    anchors.rightMargin: 26
                    spacing: 16
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Text {
                            text: {
                                for (var i = 0; i < win.navItems.length; ++i)
                                    if (win.navItems[i].id === win.page)
                                        return win.rtl ? win.navItems[i].ar : win.navItems[i].en
                                return "Mo Store"
                            }
                            color: win.txt
                            font.family: win.uiFont
                            font.pixelSize: 22
                            font.bold: true
                        }
                        Text {
                            text: win.page === "discover"
                                ? (win.rtl ? "تطبيقات آمنة، مرتبة لك، وكل المصادر في مكان واحد"
                                           : "Trusted apps, smart discovery, every source in one place")
                                : win.visibleApps.length + (win.rtl ? " نتيجة" : " results")
                            color: win.txt2
                            font.family: win.uiFont
                            font.pixelSize: 11
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: Math.min(430, win.width * 0.38)
                        Layout.preferredHeight: 46
                        radius: 15
                        color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.82)
                        border.width: searchField.activeFocus ? 1.5 : 1
                        border.color: searchField.activeFocus ? win.accent : win.outline
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 13
                            anchors.rightMargin: 11
                            spacing: 8
                            Glyph {
                                name: "search"
                                tint: searchField.activeFocus ? win.accent : win.txt2
                                Layout.preferredWidth: 17
                                Layout.preferredHeight: 17
                            }
                            TextField {
                                id: searchField
                                Layout.fillWidth: true
                                background: null
                                color: win.txt
                                placeholderText: win.rtl ? "ابحث في كل التطبيقات…" : "Search every app…"
                                placeholderTextColor: win.txt2
                                font.family: win.uiFont
                                font.pixelSize: 13
                                selectByMouse: true
                                onTextChanged: {
                                    win.query = text
                                    if (text.trim() !== "" && win.page === "discover")
                                        win.page = "apps"
                                }
                                Keys.onEscapePressed: clear()
                            }
                            Text {
                                visible: searchField.text === ""
                                text: "Ctrl K"
                                color: win.txt2
                                font.family: win.uiFont
                                font.pixelSize: 9
                            }
                        }
                    }
                }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: win.outline; opacity: 0.45 }
            }

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                // Discover page.
                Flickable {
                    id: discoverFlick
                    anchors.fill: parent
                    visible: win.page === "discover"
                    contentWidth: width
                    contentHeight: discoverBody.implicitHeight + 48
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    ColumnLayout {
                        id: discoverBody
                        x: 24
                        width: discoverFlick.width - 48
                        spacing: 22

                        Item { Layout.preferredHeight: 2 }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 224
                            radius: 28
                            gradient: Gradient {
                                orientation: Gradient.Horizontal
                                GradientStop { position: 0; color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.22) }
                                GradientStop { position: 0.58; color: Qt.rgba(win.blue.r, win.blue.g, win.blue.b, 0.1) }
                                GradientStop { position: 1; color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.9) }
                            }
                            border.width: 1
                            border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.38)
                            clip: true
                            Rectangle {
                                width: 300
                                height: 300
                                radius: 150
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.rightMargin: -70
                                color: win.accent
                                opacity: 0.08
                            }
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 28
                                spacing: 24
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    Text {
                                        text: win.rtl ? "MO STORE · جيل جديد" : "MO STORE · REIMAGINED"
                                        color: win.accent
                                        font.family: win.uiFont
                                        font.pixelSize: 10
                                        font.bold: true
                                        font.letterSpacing: 1.5
                                    }
                                    Text {
                                        text: win.rtl ? "كل تطبيقاتك. متجر واحد." : "Every app. One beautiful home."
                                        color: win.txt
                                        font.family: win.uiFont
                                        font.pixelSize: Math.min(34, win.width * 0.029)
                                        font.bold: true
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        Layout.maximumWidth: 660
                                        text: win.rtl
                                            ? "ابحث في فهرس Flatpak الكامل، ثبّت بأمان، وافتح التطبيقات والتحديثات ومصادر النظام من تجربة واحدة."
                                            : "Search the complete local Flatpak catalogue, install safely, and manage apps, updates and system engines from one experience."
                                        color: win.txt2
                                        font.family: win.uiFont
                                        font.pixelSize: 13
                                        wrapMode: Text.WordWrap
                                    }
                                    RowLayout {
                                        spacing: 9
                                        ActionButton {
                                            label: win.rtl ? "استكشف كل التطبيقات" : "Explore all apps"
                                            glyphName: "grid"
                                            primary: true
                                            triggered: function() { win.navigate("apps") }
                                        }
                                        ActionButton {
                                            label: win.rtl ? "جهّز حزمة ذكية" : "Build a smart set"
                                            glyphName: "spark"
                                            triggered: function() {
                                                if (win.bundles.length > 0)
                                                    win.addMany(win.bundles[0].apps || [])
                                            }
                                        }
                                    }
                                }
                                ColumnLayout {
                                    Layout.preferredWidth: 250
                                    Layout.fillHeight: true
                                    spacing: 10
                                    Repeater {
                                        model: [
                                            { value: win.allApps.length, label: win.rtl ? "تطبيق متاح" : "apps available", glyph: "grid" },
                                            { value: win.verifiedCount(), label: win.rtl ? "ناشر موثّق" : "verified publishers", glyph: "shield" },
                                            { value: win.installedCount(), label: win.rtl ? "مثبّت لديك" : "installed", glyph: "check" }
                                        ]
                                        delegate: Rectangle {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            radius: 15
                                            color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.72)
                                            border.width: 1
                                            border.color: win.outline
                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.margins: 12
                                                spacing: 10
                                                Glyph {
                                                    name: modelData.glyph
                                                    tint: win.accent
                                                    Layout.preferredWidth: 19
                                                    Layout.preferredHeight: 19
                                                }
                                                ColumnLayout {
                                                    spacing: -2
                                                    Text {
                                                        text: modelData.value
                                                        color: win.txt
                                                        font.family: win.uiFont
                                                        font.pixelSize: 18
                                                        font.bold: true
                                                    }
                                                    Text {
                                                        text: modelData.label
                                                        color: win.txt2
                                                        font.family: win.uiFont
                                                        font.pixelSize: 9
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: win.rtl ? "اختيارات MoOS" : "MoOS picks"
                                color: win.txt
                                font.family: win.uiFont
                                font.pixelSize: 17
                                font.bold: true
                            }
                            Text {
                                text: win.rtl ? "· تطبيقات موثوقة للبدء" : "· trusted ways to get started"
                                color: win.txt2
                                font.family: win.uiFont
                                font.pixelSize: 11
                            }
                            Item { Layout.fillWidth: true }
                            ActionButton {
                                label: win.rtl ? "عرض الكل" : "See all"
                                glyphName: "external"
                                triggered: function() { win.navigate("apps") }
                            }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: win.width > 1220 ? 4 : 3
                            columnSpacing: 12
                            rowSpacing: 12
                            Repeater {
                                model: win.curatedFeatured(win.width > 1220 ? 8 : 6)
                                delegate: AppCard {
                                    required property var modelData
                                    app: modelData
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 178
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.topMargin: 2
                            Text {
                                text: win.rtl ? "فئات لكل استخدام" : "Made for every kind of day"
                                color: win.txt
                                font.family: win.uiFont
                                font.pixelSize: 17
                                font.bold: true
                            }
                            Item { Layout.fillWidth: true }
                            Text {
                                text: win.rtl ? "من العمل إلى اللعب، ومن التصميم إلى الذكاء الاصطناعي" : "Work, play, create, learn and build"
                                color: win.txt2
                                font.family: win.uiFont
                                font.pixelSize: 11
                            }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: win.width > 1180 ? 4 : 3
                            columnSpacing: 12
                            rowSpacing: 12
                            Repeater {
                                model: win.categoryDefs.slice(0, 8)
                                delegate: Rectangle {
                                    id: homeCategory
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 82
                                    radius: 18
                                    color: homeCategoryHover.hovered
                                        ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.94)
                                        : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.72)
                                    border.width: 1
                                    border.color: homeCategoryHover.hovered ? win.accent : win.outline
                                    activeFocusOnTab: true
                                    Accessible.role: Accessible.Button
                                    Accessible.name: win.rtl ? modelData.ar : modelData.en
                                    HoverHandler { id: homeCategoryHover }
                                    TapHandler { onTapped: win.openCategory(homeCategory.modelData.id) }
                                    Keys.onReturnPressed: win.openCategory(homeCategory.modelData.id)
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 12
                                        Rectangle {
                                            Layout.preferredWidth: 44
                                            Layout.preferredHeight: 44
                                            radius: 14
                                            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.13)
                                            Glyph { anchors.centerIn: parent; width: 22; height: 22; name: homeCategory.modelData.glyph; tint: win.accent }
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 0
                                            Text {
                                                text: win.rtl ? homeCategory.modelData.ar : homeCategory.modelData.en
                                                color: win.txt
                                                font.family: win.uiFont
                                                font.pixelSize: 13
                                                font.bold: true
                                            }
                                            Text {
                                                text: win.categoryCount(homeCategory.modelData.id) + (win.rtl ? " تطبيق" : " apps")
                                                color: win.txt2
                                                font.family: win.uiFont
                                                font.pixelSize: 10
                                            }
                                        }
                                        Glyph { name: "external"; tint: win.txt2; Layout.preferredWidth: 14; Layout.preferredHeight: 14 }
                                    }
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.topMargin: 2
                            Text {
                                text: win.rtl ? "حزم ذكية" : "Smart collections"
                                color: win.txt
                                font.family: win.uiFont
                                font.pixelSize: 17
                                font.bold: true
                            }
                            Text {
                                text: win.rtl ? "· ثبّت مجموعة كاملة بمراجعة واحدة" : "· one review, a complete setup"
                                color: win.txt2
                                font.family: win.uiFont
                                font.pixelSize: 11
                            }
                            Item { Layout.fillWidth: true }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: win.width > 1180 ? 3 : 2
                            columnSpacing: 12
                            rowSpacing: 12
                            Repeater {
                                model: win.bundles
                                delegate: Rectangle {
                                    id: bundleCard
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 132
                                    radius: 20
                                    color: bundleHover.hovered
                                        ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.96)
                                        : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.76)
                                    border.width: 1
                                    border.color: bundleHover.hovered ? win.accent : win.outline
                                    HoverHandler { id: bundleHover }
                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 7
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Glyph {
                                                name: bundleCard.modelData.glyph || "boxes"
                                                tint: win.accent
                                                Layout.preferredWidth: 21
                                                Layout.preferredHeight: 21
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: win.rtl ? bundleCard.modelData.ar : bundleCard.modelData.en
                                                color: win.txt
                                                font.family: win.uiFont
                                                font.pixelSize: 14
                                                font.bold: true
                                            }
                                            Text {
                                                text: (bundleCard.modelData.apps || []).length
                                                color: win.accent
                                                font.family: win.uiFont
                                                font.pixelSize: 12
                                                font.bold: true
                                            }
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: win.rtl ? bundleCard.modelData.desc_ar : bundleCard.modelData.desc_en
                                            color: win.txt2
                                            font.family: win.uiFont
                                            font.pixelSize: 10
                                            wrapMode: Text.WordWrap
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                        }
                                        Item { Layout.fillHeight: true }
                                        ActionButton {
                                            label: win.rtl ? "أضف الحزمة" : "Add collection"
                                            glyphName: "download"
                                            triggered: function() { win.addMany(bundleCard.modelData.apps || []) }
                                        }
                                    }
                                }
                            }
                        }
                        Item { Layout.preferredHeight: 12 }
                    }
                }

                // Virtualized catalogue / installed page.
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 22
                    visible: win.page === "apps" || win.page === "installed"
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Flickable {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            contentWidth: categoryRow.implicitWidth
                            contentHeight: height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            RowLayout {
                                id: categoryRow
                                height: parent.height
                                spacing: 7
                                Repeater {
                                    model: [{ id: "all", ar: "الكل", en: "All", glyph: "grid" }].concat(win.categoryDefs)
                                    delegate: Rectangle {
                                        id: categoryPill
                                        required property var modelData
                                        readonly property bool active: win.activeCategory === modelData.id
                                        implicitWidth: pillRow.implicitWidth + 22
                                        Layout.preferredHeight: 36
                                        radius: 12
                                        color: active ? win.accent
                                                      : pillHover.hovered ? win.raised : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.7)
                                        border.width: active ? 0 : 1
                                        border.color: win.outline
                                        HoverHandler { id: pillHover }
                                        TapHandler { onTapped: win.activeCategory = categoryPill.modelData.id }
                                        RowLayout {
                                            id: pillRow
                                            anchors.centerIn: parent
                                            spacing: 6
                                            Glyph {
                                                name: categoryPill.modelData.glyph
                                                tint: categoryPill.active ? win.onAccent : win.txt2
                                                Layout.preferredWidth: 14
                                                Layout.preferredHeight: 14
                                            }
                                            Text {
                                                text: win.rtl ? categoryPill.modelData.ar : categoryPill.modelData.en
                                                color: categoryPill.active ? win.onAccent : win.txt
                                                font.family: win.uiFont
                                                font.pixelSize: 11
                                                font.bold: categoryPill.active
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        Text {
                            text: win.visibleApps.length + (win.rtl ? " تطبيق" : " apps")
                            color: win.txt2
                            font.family: win.uiFont
                            font.pixelSize: 11
                        }
                        ActionButton {
                            visible: win.page === "apps" && win.visibleApps.length > 0
                            label: win.rtl ? "أضف كل القسم" : "Add this section"
                            glyphName: "download"
                            triggered: function() {
                                var ids = []
                                for (var i = 0; i < win.visibleApps.length; ++i)
                                    ids.push(win.visibleApps[i].id)
                                win.addMany(ids)
                            }
                        }
                    }

                    GridView {
                        id: appGrid
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: win.visibleApps
                        readonly property int columnCount: width > 1020 ? 4 : width > 720 ? 3 : 2
                        cellWidth: width / columnCount
                        cellHeight: 192
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        delegate: Item {
                            required property var modelData
                            width: appGrid.cellWidth
                            height: appGrid.cellHeight
                            AppCard {
                                anchors.fill: parent
                                anchors.margins: 6
                                app: modelData
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: win.visibleApps.length === 0
                        spacing: 8
                        Item { Layout.fillHeight: true }
                        Glyph {
                            Layout.alignment: Qt.AlignHCenter
                            Layout.preferredWidth: 42
                            Layout.preferredHeight: 42
                            name: win.page === "installed" ? "download" : "search"
                            tint: win.txt2
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: win.page === "installed"
                                ? (win.rtl ? "لا توجد تطبيقات مثبتة في هذا القسم" : "No installed apps in this view")
                                : (win.rtl ? "لا توجد نتائج" : "No results")
                            color: win.txt
                            font.family: win.uiFont
                            font.pixelSize: 16
                            font.bold: true
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: win.rtl ? "جرّب كلمة بحث أو فئة مختلفة." : "Try another search or category."
                            color: win.txt2
                            font.family: win.uiFont
                            font.pixelSize: 11
                        }
                        Item { Layout.fillHeight: true }
                    }
                }

                // Category overview.
                Flickable {
                    anchors.fill: parent
                    visible: win.page === "categories"
                    contentWidth: width
                    contentHeight: categoryBody.implicitHeight + 44
                    clip: true
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    ColumnLayout {
                        id: categoryBody
                        x: 24
                        width: parent.width - 48
                        spacing: 18
                        Item { Layout.preferredHeight: 4 }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 122
                            radius: 24
                            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.12)
                            border.width: 1
                            border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.3)
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 24
                                spacing: 17
                                Rectangle {
                                    Layout.preferredWidth: 66
                                    Layout.preferredHeight: 66
                                    radius: 21
                                    color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                                    Glyph { anchors.centerIn: parent; width: 32; height: 32; name: "boxes"; tint: win.accent }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 3
                                    Text {
                                        text: win.rtl ? "اختر حسب ما تريد إنجازه" : "Start with what you want to do"
                                        color: win.txt
                                        font.family: win.uiFont
                                        font.pixelSize: 22
                                        font.bold: true
                                    }
                                    Text {
                                        text: win.rtl ? "فئات عملية بدل قوائم تقنية طويلة." : "Human categories instead of package-manager jargon."
                                        color: win.txt2
                                        font.family: win.uiFont
                                        font.pixelSize: 12
                                    }
                                }
                            }
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: win.width > 1160 ? 4 : 3
                            columnSpacing: 13
                            rowSpacing: 13
                            Repeater {
                                model: win.categoryDefs
                                delegate: Rectangle {
                                    id: categoryTile
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 132
                                    radius: 21
                                    color: categoryHover.hovered
                                        ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.97)
                                        : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.78)
                                    border.width: 1
                                    border.color: categoryHover.hovered ? win.accent : win.outline
                                    activeFocusOnTab: true
                                    Accessible.role: Accessible.Button
                                    Accessible.name: win.rtl ? modelData.ar : modelData.en
                                    HoverHandler { id: categoryHover }
                                    TapHandler { onTapped: win.openCategory(categoryTile.modelData.id) }
                                    Keys.onReturnPressed: win.openCategory(categoryTile.modelData.id)
                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 16
                                        spacing: 8
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Rectangle {
                                                Layout.preferredWidth: 46
                                                Layout.preferredHeight: 46
                                                radius: 15
                                                color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.13)
                                                Glyph { anchors.centerIn: parent; width: 24; height: 24; name: categoryTile.modelData.glyph; tint: win.accent }
                                            }
                                            Item { Layout.fillWidth: true }
                                            Text {
                                                text: win.categoryCount(categoryTile.modelData.id)
                                                color: win.accent
                                                font.family: win.uiFont
                                                font.pixelSize: 15
                                                font.bold: true
                                            }
                                        }
                                        Text {
                                            text: win.rtl ? categoryTile.modelData.ar : categoryTile.modelData.en
                                            color: win.txt
                                            font.family: win.uiFont
                                            font.pixelSize: 14
                                            font.bold: true
                                        }
                                        Text {
                                            text: win.rtl ? "استكشف التطبيقات" : "Explore apps"
                                            color: win.txt2
                                            font.family: win.uiFont
                                            font.pixelSize: 10
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Updates.
                Flickable {
                    anchors.fill: parent
                    visible: win.page === "updates"
                    contentWidth: width
                    contentHeight: updateBody.implicitHeight + 50
                    clip: true
                    ColumnLayout {
                        id: updateBody
                        x: 26
                        width: parent.width - 52
                        spacing: 16
                        Item { Layout.preferredHeight: 4 }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 210
                            radius: 27
                            gradient: Gradient {
                                orientation: Gradient.Horizontal
                                GradientStop { position: 0; color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.2) }
                                GradientStop { position: 1; color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.88) }
                            }
                            border.width: 1
                            border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.36)
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 28
                                spacing: 24
                                Rectangle {
                                    Layout.preferredWidth: 92
                                    Layout.preferredHeight: 92
                                    radius: 30
                                    color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                                    Glyph { anchors.centerIn: parent; width: 46; height: 46; name: "refresh"; tint: win.accent }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 7
                                    Text {
                                        // Say what is true, and say "not checked yet" when
                                        // that is what is true. Never show 0 before looking.
                                        text: {
                                            if (win.updatesChecking)
                                                return win.rtl ? "نفحص التحديثات…" : "Checking for updates…"
                                            if (win.updatesState === "failed")
                                                return win.rtl ? "تعذّر فحص التحديثات" : "Could not check for updates"
                                            if (win.updatesState === "unknown")
                                                return win.rtl ? "تطبيقاتك، وتحديثاتها." : "Your apps, and their updates."
                                            var n = win.updateItems().length
                                            if (n === 0 && win.updateComponentCount() > 0)
                                                return win.rtl
                                                    ? "توجد تحديثات لمكوّنات مشتركة."
                                                    : "Shared components have updates."
                                            if (n === 0)
                                                return win.rtl ? "كل تطبيقاتك محدّثة." : "Everything is up to date."
                                            return win.rtl
                                                ? (n === 1 ? "تطبيق واحد ينتظر التحديث." : n + " تطبيقات تنتظر التحديث.")
                                                : (n === 1 ? "1 app has an update." : n + " apps have updates.")
                                        }
                                        color: win.txt
                                        font.family: win.uiFont
                                        font.pixelSize: 24
                                        font.bold: true
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: {
                                            if (win.updatesState === "failed")
                                                return win.rtl
                                                    ? "تحقّق من اتصالك ثم أعد الفحص. تحديث صورة MoOS والبرامج الثابتة تبقى في مسارات النظام الموقّعة."
                                                    : "Check your connection and try again. MoOS image and firmware updates stay on their signed system paths."
                                            var extra = win.updateComponentCount()
                                            if (win.updatesState === "known" && extra > 0)
                                                return win.rtl
                                                    ? "بالإضافة إلى " + extra + " مكوّن مشترك يُحدَّث معها. تحديث صورة MoOS والبرامج الثابتة تبقى في مسارات النظام الموقّعة."
                                                    : "Plus " + extra + " shared component(s) that update with them. MoOS image and firmware updates stay on their signed system paths."
                                            return win.rtl
                                                ? "حدّث تطبيقات Flatpak هنا. تحديث صورة MoOS والبرامج الثابتة يبقيان في مسارات النظام الموقّعة."
                                                : "Update Flatpak apps here. MoOS image and firmware updates stay on their signed system paths."
                                        }
                                        color: win.txt2
                                        font.family: win.uiFont
                                        font.pixelSize: 12
                                        wrapMode: Text.WordWrap
                                    }
                                    RowLayout {
                                        spacing: 8
                                        ActionButton {
                                            label: win.updateItems().length === 0
                                                   && win.updateComponentCount() > 0
                                                ? (win.rtl ? "تحديث المكوّنات الآن" : "Update components now")
                                                : (win.rtl ? "تحديث التطبيقات الآن" : "Update apps now")
                                            glyphName: "refresh"
                                            primary: true
                                            // Nothing pending is a reason not to offer the
                                            // button, once we actually know that.
                                            enabled: !win.jobIsActive() && !win.updatesChecking
                                                && !(win.updatesState === "known" && win.updates.count === 0)
                                            triggered: function() { win.updateAll() }
                                        }
                                        ActionButton {
                                            label: win.rtl ? "إعادة الفحص" : "Check again"
                                            glyphName: "search"
                                            enabled: !win.updatesChecking
                                            triggered: function() {
                                                win.updatesState = "unknown"
                                                win.updatesCheckedAt = ""
                                                win.checkUpdates()
                                            }
                                        }
                                        ActionButton {
                                            label: win.rtl ? "تحديث MoOS" : "Update MoOS"
                                            glyphName: "shield"
                                            triggered: function() { win.openSystemUpdater() }
                                        }
                                    }
                                }
                            }
                        }
                        // The list the page was missing: what actually has an
                        // update, named, with the version currently installed.
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 9
                            visible: win.updatesState === "known" && win.updateItems().length > 0
                            Text {
                                text: win.rtl ? "بانتظار التحديث" : "Waiting to update"
                                color: win.txt2
                                font.family: win.uiFont
                                font.pixelSize: 12
                                font.bold: true
                            }
                            Repeater {
                                model: win.updatesState === "known" ? win.updateItems() : []
                                delegate: Rectangle {
                                    id: pendingRow
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 62
                                    radius: 16
                                    color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.72)
                                    border.width: 1
                                    border.color: win.outline
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 16
                                        anchors.rightMargin: 16
                                        spacing: 13
                                        Rectangle {
                                            Layout.preferredWidth: 36
                                            Layout.preferredHeight: 36
                                            radius: 11
                                            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                                            Glyph {
                                                anchors.centerIn: parent
                                                width: 19; height: 19
                                                name: "download"; tint: win.accent
                                            }
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 1
                                            Text {
                                                Layout.fillWidth: true
                                                text: pendingRow.modelData.name || pendingRow.modelData.id
                                                color: win.txt
                                                font.family: win.uiFont
                                                font.pixelSize: 14
                                                font.bold: true
                                                elide: Text.ElideRight
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: pendingRow.modelData.id
                                                    + (pendingRow.modelData.version
                                                        ? " · " + pendingRow.modelData.version : "")
                                                color: win.txt2
                                                font.family: win.uiFont
                                                font.pixelSize: 11
                                                elide: Text.ElideRight
                                            }
                                        }
                                        Text {
                                            text: pendingRow.modelData.origin || ""
                                            color: win.txt2
                                            font.family: win.uiFont
                                            font.pixelSize: 11
                                        }
                                    }
                                }
                            }
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: 3
                            columnSpacing: 13
                            Repeater {
                                model: [
                                    { glyph: "grid", ar: "تطبيقات Flatpak", en: "Flatpak apps", ar2: "تحديث آمن بصلاحيات المستخدم", en2: "Safe per-user transactions", action: "update" },
                                    { glyph: "shield", ar: "صورة MoOS", en: "MoOS image", ar2: "تحديث موقّع يُطبق بعد إعادة التشغيل", en2: "Signed, applied after reboot", action: "system-update" },
                                    { glyph: "gear", ar: "البرامج الثابتة", en: "Device firmware", ar2: "تحديثات العتاد من المصدر الموثوق", en2: "Trusted hardware updates", action: "firmware" }
                                ]
                                delegate: Rectangle {
                                    id: updateCard
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 156
                                    radius: 21
                                    color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.78)
                                    border.width: 1
                                    border.color: win.outline
                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 16
                                        spacing: 8
                                        Glyph {
                                            name: updateCard.modelData.glyph
                                            tint: win.accent
                                            Layout.preferredWidth: 27
                                            Layout.preferredHeight: 27
                                        }
                                        Text {
                                            text: win.rtl ? updateCard.modelData.ar : updateCard.modelData.en
                                            color: win.txt
                                            font.family: win.uiFont
                                            font.pixelSize: 14
                                            font.bold: true
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: win.rtl ? updateCard.modelData.ar2 : updateCard.modelData.en2
                                            color: win.txt2
                                            font.family: win.uiFont
                                            font.pixelSize: 10
                                            wrapMode: Text.WordWrap
                                        }
                                        Item { Layout.fillHeight: true }
                                        ActionButton {
                                            label: updateCard.modelData.action === "update"
                                                ? win.updateItems().length === 0
                                                    && win.updateComponentCount() > 0
                                                    ? (win.rtl ? "حدّث المكوّنات الآن" : "Update components now")
                                                    : (win.rtl ? "حدّث تطبيقات Flatpak الآن" : "Update Flatpaks now")
                                                : updateCard.modelData.action === "system-update"
                                                    ? (win.rtl ? "افتح محدّث MoOS" : "Open MoOS Updater")
                                                    : (win.rtl ? "افتح تحديثات البرامج الثابتة" : "Open firmware updates")
                                            glyphName: updateCard.modelData.action === "update"
                                                ? "refresh" : "external"
                                            enabled: updateCard.modelData.action !== "update"
                                                || (!win.jobIsActive()
                                                    && !win.updatesChecking
                                                    && !(win.updatesState === "known"
                                                         && win.updates.count === 0))
                                            triggered: function() {
                                                if (updateCard.modelData.action === "update") win.updateAll()
                                                else if (updateCard.modelData.action === "system-update")
                                                    win.openSystemUpdater()
                                                else win.openSourceEngine(updateCard.modelData.action)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Sources: engines are capabilities behind Mo Store, never extra
                // launchers competing in the application menu.
                Flickable {
                    anchors.fill: parent
                    visible: win.page === "sources"
                    contentWidth: width
                    contentHeight: sourceBody.implicitHeight + 50
                    clip: true
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    ColumnLayout {
                        id: sourceBody
                        x: 26
                        width: parent.width - 52
                        spacing: 17
                        Item { Layout.preferredHeight: 4 }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 142
                            radius: 25
                            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.11)
                            border.width: 1
                            border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.3)
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 24
                                spacing: 17
                                Rectangle {
                                    Layout.preferredWidth: 70
                                    Layout.preferredHeight: 70
                                    radius: 23
                                    color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                                    Glyph { anchors.centerIn: parent; width: 34; height: 34; name: "orbit"; tint: win.accent }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Text {
                                        text: win.rtl ? "مصادر متعددة، تجربة واحدة." : "Many sources. One coherent store."
                                        color: win.txt
                                        font.family: win.uiFont
                                        font.pixelSize: 23
                                        font.bold: true
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: win.rtl
                                            ? "Mo Store يوحّد البيانات والإدارة، ويُبقي المحركات المتخصصة متاحة عند الحاجة من دون تكرار المتاجر في القائمة."
                                            : "Mo Store unifies discovery and management while keeping specialist engines available without duplicate storefronts."
                                        color: win.txt2
                                        font.family: win.uiFont
                                        font.pixelSize: 11
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: win.width > 1120 ? 2 : 1
                            columnSpacing: 13
                            rowSpacing: 13
                            Repeater {
                                model: [
                                    {
                                        id: "flathub", glyph: "shield",
                                        ar: "Flathub · المصدر الأساسي", en: "Flathub · Primary source",
                                        ar2: win.hasFlatpakCatalog()
                                            ? "آلاف التطبيقات المعزولة، فهرس محلي، وأيقونات وبيانات AppStream حقيقية."
                                            : "الكتالوج الأساسي فقط متاح الآن؛ اتصل بالإنترنت لتحديث فهرس التطبيقات الكامل.",
                                        en2: win.hasFlatpakCatalog()
                                            ? "Thousands of sandboxed apps with a local AppStream catalogue and real metadata."
                                            : "Only the essential catalogue is available; connect to refresh the full app index.",
                                        stateAr: win.hasFlatpakCatalog() ? "مدمج" : "يحتاج تحديثًا",
                                        stateEn: win.hasFlatpakCatalog() ? "Integrated" : "Refresh needed",
                                        action: win.hasFlatpakCatalog() ? "" : "refresh"
                                    },
                                    {
                                        id: "bazaar", glyph: "grid",
                                        ar: "Bazaar · محرك Flatpak اختياري", en: "Bazaar · Optional Flatpak engine",
                                        ar2: "واجهة متقدمة للكتالوج والحسابات والمفضلة. تبقى مخفية من قائمة النظام كي يظل Mo Store المتجر الوحيد.",
                                        en2: "An advanced catalogue, account and favourites engine, kept out of the menu so Mo Store stays the one storefront.",
                                        stateAr: "اختياري", stateEn: "Optional", action: "bazaar"
                                    },
                                    {
                                        id: "discover", glyph: "monitor",
                                        ar: "Discover · محرك النظام", en: "Discover · System engine",
                                        ar2: "للتحديثات، البرامج الثابتة وإضافات Plasma. لا يفتح تثبيت حزم نظام عشوائية.",
                                        en2: "For updates, firmware and Plasma add-ons — never arbitrary host packages.",
                                        stateAr: "متاح", stateEn: "Available", action: "discover"
                                    },
                                    {
                                        id: "appimage", glyph: "external",
                                        ar: "AppImage · مصادر خارجية", en: "AppImage · External sources",
                                        ar2: "يُسمح فقط بروابط الناشر الرسمية والوصفات المراجعة. لا تثبيت صامت لملفات غير موقّعة.",
                                        en2: "Only reviewed recipes and official publisher links — never silent unverified executables.",
                                        stateAr: "مقيّد بأمان", stateEn: "Safety restricted", action: ""
                                    },
                                    {
                                        id: "permissions", glyph: "lock",
                                        ar: "Flatseal · إدارة الصلاحيات", en: "Flatseal · Permissions",
                                        ar2: "راجع وصول التطبيقات للملفات والكاميرا والميكروفون والشبكة.",
                                        en2: "Review app access to files, camera, microphone and the network.",
                                        stateAr: "أداة موصى بها", stateEn: "Recommended tool", action: "permissions"
                                    },
                                    {
                                        id: "developer", glyph: "code",
                                        ar: "أدوات المطور", en: "Developer tools",
                                        ar2: "أدوات npm المراجعة تظهر بوضوح كمصدر متقدم؛ لا taps ولا أوامر shell حرة.",
                                        en2: "Reviewed npm tools are clearly marked as advanced; their package scripts run only after explicit approval.",
                                        stateAr: "مراجعة مطلوبة", stateEn: "Review required", action: ""
                                    }
                                ]
                                delegate: Rectangle {
                                    id: sourceCard
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 168
                                    radius: 22
                                    color: sourceHover.hovered
                                        ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.96)
                                        : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.77)
                                    border.width: 1
                                    border.color: sourceHover.hovered ? win.accent : win.outline
                                    HoverHandler { id: sourceHover }
                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 16
                                        spacing: 8
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Rectangle {
                                                Layout.preferredWidth: 46
                                                Layout.preferredHeight: 46
                                                radius: 15
                                                color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.13)
                                                Glyph { anchors.centerIn: parent; width: 24; height: 24; name: sourceCard.modelData.glyph; tint: win.accent }
                                            }
                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 1
                                                Text {
                                                    text: win.rtl ? sourceCard.modelData.ar : sourceCard.modelData.en
                                                    color: win.txt
                                                    font.family: win.uiFont
                                                    font.pixelSize: 14
                                                    font.bold: true
                                                }
                                                Text {
                                                    text: win.rtl ? sourceCard.modelData.stateAr : sourceCard.modelData.stateEn
                                                    color: win.accent
                                                    font.family: win.uiFont
                                                    font.pixelSize: 10
                                                    font.bold: true
                                                }
                                            }
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: win.rtl ? sourceCard.modelData.ar2 : sourceCard.modelData.en2
                                            color: win.txt2
                                            font.family: win.uiFont
                                            font.pixelSize: 10
                                            wrapMode: Text.WordWrap
                                            maximumLineCount: 3
                                            elide: Text.ElideRight
                                        }
                                        Item { Layout.fillHeight: true }
                                        ActionButton {
                                            visible: sourceCard.modelData.action !== ""
                                            enabled: !win.jobIsActive()
                                            label: sourceCard.modelData.action === "permissions"
                                                ? win.isInstalled(win.appById("com.github.tchx84.Flatseal"))
                                                    ? (win.rtl ? "افتح الأداة" : "Open tool")
                                                    : (win.rtl ? "ثبّت الأداة" : "Install tool")
                                                : sourceCard.modelData.action === "refresh"
                                                    ? (win.rtl ? "حدّث الفهرس" : "Refresh catalogue")
                                                : sourceCard.modelData.action === "bazaar"
                                                    && !win.isInstalled(win.appById("io.github.kolunmi.Bazaar"))
                                                    ? (win.rtl ? "ثبّت المحرك وافتحه" : "Install & open engine")
                                                : (win.rtl ? "فتح المحرك" : "Open engine")
                                            glyphName: sourceCard.modelData.action === "permissions"
                                                && !win.isInstalled(win.appById("com.github.tchx84.Flatseal"))
                                                || sourceCard.modelData.action === "bazaar"
                                                    && !win.isInstalled(win.appById("io.github.kolunmi.Bazaar"))
                                                ? "download" : "external"
                                            triggered: function() {
                                                win.openSourceEngine(sourceCard.modelData.action)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Selection shelf.  It never preselects software on launch.
    Rectangle {
        id: selectionShelf
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: win.pickCount > 0
                              && !review.opened
                              && !win.jobIsActive()
                              && !win.jobIsTerminal() ? 20 : -84
        width: Math.min(610, win.width - 56)
        height: 58
        radius: 20
        visible: anchors.bottomMargin > -84
        color: Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.98)
        border.width: 1
        border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.48)
        Behavior on anchors.bottomMargin { NumberAnimation { duration: 220; easing.type: Easing.OutBack } }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 13
            anchors.rightMargin: 9
            spacing: 10
            Rectangle {
                Layout.preferredWidth: 34
                Layout.preferredHeight: 34
                radius: 12
                color: win.accent
                Text {
                    anchors.centerIn: parent
                    text: win.pickCount
                    color: win.onAccent
                    font.family: win.uiFont
                    font.pixelSize: 13
                    font.bold: true
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: -1
                Text {
                    text: win.rtl ? "قائمة التثبيت جاهزة" : "Install list ready"
                    color: win.txt
                    font.family: win.uiFont
                    font.pixelSize: 12
                    font.bold: true
                }
                Text {
                    text: win.rtl ? "راجع المصدر قبل البدء" : "Review sources before starting"
                    color: win.txt2
                    font.family: win.uiFont
                    font.pixelSize: 9
                }
            }
            ActionButton {
                label: win.rtl ? "مسح" : "Clear"
                glyphName: "trash"
                triggered: function() { win.clearPicks() }
            }
            ActionButton {
                label: win.rtl ? "مراجعة وتثبيت" : "Review & install"
                glyphName: "download"
                primary: true
                triggered: function() { review.open() }
            }
        }
    }

    // Real transaction status shelf.  Null progress is shown as indeterminate,
    // never replaced with a made-up percentage.
    Rectangle {
        id: jobShelf
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: win.jobIsActive() || win.jobIsTerminal() ? 20 : -100
        width: Math.min(690, win.width - 56)
        height: 76
        radius: 22
        visible: anchors.bottomMargin > -100
        color: Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.98)
        border.width: 1
        border.color: win.job.state === "failed" ? win.violet
                      : Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.48)
        Behavior on anchors.bottomMargin { NumberAnimation { duration: 220; easing.type: Easing.OutBack } }
        RowLayout {
            anchors.fill: parent
            anchors.margins: 13
            spacing: 12
            Rectangle {
                Layout.preferredWidth: 44
                Layout.preferredHeight: 44
                radius: 15
                color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                Glyph {
                    anchors.centerIn: parent
                    width: 23
                    height: 23
                    name: win.jobIsTerminal() ? (win.job.state === "success" ? "check" : "shield") : "download"
                    tint: win.job.state === "failed" ? win.violet : win.accent
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: win.waitingForJob
                            ? (win.rtl ? "يبدأ العمل…" : "Starting…")
                            : win.job.message || (win.rtl ? "جارٍ تنفيذ العملية" : "Working")
                        color: win.txt
                        font.family: win.uiFont
                        font.pixelSize: 12
                        font.bold: true
                        elide: Text.ElideRight
                    }
                    Text {
                        visible: win.job.progress !== null && win.job.progress !== undefined
                        text: Math.round(win.job.progress || 0) + "%"
                        color: win.accent
                        font.family: win.uiFont
                        font.pixelSize: 11
                        font.bold: true
                    }
                }
                Rectangle {
                    id: jobProgressTrack
                    Layout.fillWidth: true
                    Layout.preferredHeight: 6
                    radius: 3
                    color: Qt.rgba(win.outline.r, win.outline.g, win.outline.b, 0.5)
                    clip: true
                    Rectangle {
                        visible: win.job.progress !== null && win.job.progress !== undefined
                        height: parent.height
                        radius: 3
                        width: parent.width * Math.max(0, Math.min(100, win.job.progress || 0)) / 100
                        color: win.accent
                        Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
                    }
                    Rectangle {
                        id: jobProgressIndeterminate
                        visible: win.job.progress === null || win.job.progress === undefined
                        width: jobProgressTrack.width * 0.28
                        height: jobProgressTrack.height
                        radius: 3
                        color: win.accent
                        SequentialAnimation on x {
                            running: jobProgressIndeterminate.visible && win.motionEnabled
                            loops: Animation.Infinite
                            NumberAnimation {
                                from: -jobProgressIndeterminate.width
                                to: jobProgressTrack.width
                                duration: 1200
                                easing.type: Easing.InOutQuad
                            }
                        }
                    }
                }
            }
            ActionButton {
                visible: win.jobIsActive()
                enabled: !win.waitingForJob
                label: win.rtl ? "إلغاء" : "Cancel"
                glyphName: "trash"
                destructive: true
                triggered: function() {
                    if (typeof MoosStore !== "undefined") MoosStore.cancelJob()
                }
            }
            ActionButton {
                visible: win.jobIsTerminal()
                label: win.rtl ? "إخفاء" : "Dismiss"
                glyphName: "check"
                triggered: function() { win.job = ({}) }
            }
        }
    }

    // App details.
    Popup {
        id: details
        anchors.centerIn: Overlay.overlay
        width: Math.min(760, win.width - 70)
        height: Math.min(670, win.height - 56)
        modal: true
        padding: 0
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            radius: 26
            color: win.surface
            border.width: 1
            border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.38)
        }
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.54) }
        enter: Transition {
            NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: 170; easing.type: Easing.OutBack }
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 130 }
        }
        Flickable {
            anchors.fill: parent
            anchors.margins: 22
            contentWidth: width
            contentHeight: detailBody.implicitHeight
            clip: true
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            ColumnLayout {
                id: detailBody
                width: parent.width
                spacing: 15
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 15
                    AppArtwork { app: win.selectedApp; size: 78 }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3
                        Text {
                            Layout.fillWidth: true
                            text: win.localName(win.selectedApp)
                            color: win.txt
                            font.family: win.uiFont
                            font.pixelSize: 24
                            font.bold: true
                            elide: Text.ElideRight
                        }
                        Text {
                            Layout.fillWidth: true
                            text: win.selectedApp ? (win.selectedApp.developer || win.selectedApp.id) : ""
                            color: win.txt2
                            font.family: win.uiFont
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }
                        RowLayout {
                            SourceBadge { app: win.selectedApp }
                            Rectangle {
                                visible: win.selectedApp !== null && !!win.selectedApp.license
                                implicitHeight: 22
                                implicitWidth: licenseText.implicitWidth + 14
                                radius: 11
                                color: Qt.rgba(win.txt2.r, win.txt2.g, win.txt2.b, 0.12)
                                Text {
                                    id: licenseText
                                    anchors.centerIn: parent
                                    text: win.selectedApp ? win.selectedApp.license : ""
                                    color: win.txt2
                                    font.family: win.uiFont
                                    font.pixelSize: 9
                                }
                            }
                        }
                    }
                    ActionButton {
                        label: win.rtl ? "إغلاق" : "Close"
                        glyphName: "external"
                        triggered: function() { details.close() }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: win.selectedApp && win.selectedApp.screenshot ? 250 : 0
                    visible: height > 0
                    radius: 18
                    color: win.canvas
                    clip: true
                    Image {
                        anchors.fill: parent
                        source: win.selectedApp && win.selectedApp.screenshot ? win.selectedApp.screenshot : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        smooth: true
                    }
                    Rectangle {
                        anchors.fill: parent
                        gradient: Gradient {
                            GradientStop { position: 0.6; color: "transparent" }
                            GradientStop { position: 1; color: Qt.rgba(win.canvas.r, win.canvas.g, win.canvas.b, 0.74) }
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: win.localSummary(win.selectedApp)
                    color: win.txt
                    font.family: win.uiFont
                    font.pixelSize: 15
                    font.bold: true
                    wrapMode: Text.WordWrap
                }
                Text {
                    Layout.fillWidth: true
                    text: win.localDescription(win.selectedApp)
                    color: win.txt2
                    font.family: win.uiFont
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                    maximumLineCount: 8
                    elide: Text.ElideRight
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 3
                    columnSpacing: 10
                    Repeater {
                        model: [
                            {
                                label: win.rtl ? "المصدر" : "Source",
                                value: win.sourceLabel(win.selectedApp),
                                glyph: "orbit"
                            },
                            {
                                label: win.rtl ? "الفئة" : "Category",
                                value: win.categoryName(win.normalizedCategory(win.selectedApp || ({}))),
                                glyph: win.categoryGlyph(win.normalizedCategory(win.selectedApp || ({})))
                            },
                            {
                                label: win.rtl ? "الإصدار" : "Version",
                                value: win.selectedApp && win.selectedApp.version ? win.selectedApp.version : (win.rtl ? "يتبع المصدر" : "From source"),
                                glyph: "refresh"
                            }
                        ]
                        delegate: Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 78
                            radius: 15
                            color: Qt.rgba(win.canvas.r, win.canvas.g, win.canvas.b, 0.5)
                            border.width: 1
                            border.color: win.outline
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 9
                                Glyph { name: modelData.glyph; tint: win.accent; Layout.preferredWidth: 19; Layout.preferredHeight: 19 }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0
                                    Text { text: modelData.label; color: win.txt2; font.family: win.uiFont; font.pixelSize: 9 }
                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.value
                                        color: win.txt
                                        font.family: win.uiFont
                                        font.pixelSize: 11
                                        font.bold: true
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 58
                    visible: win.selectedApp !== null && (win.selectedApp.requires_review === true
                                                          || (win.selectedApp.install
                                                              && win.selectedApp.install.requires_review === true)
                                                          || (win.selectedApp.install && win.selectedApp.install.kind === "npm"))
                    radius: 16
                    color: Qt.rgba(win.violet.r, win.violet.g, win.violet.b, 0.1)
                    border.width: 1
                    border.color: Qt.rgba(win.violet.r, win.violet.g, win.violet.b, 0.34)
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 10
                        Glyph { name: "shield"; tint: win.violet; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                        Text {
                            Layout.fillWidth: true
                            text: win.rtl
                                ? "مصدر متقدم: راجع اسم الحزمة وطريقة التثبيت قبل المتابعة."
                                : "Advanced source: review the package and install method before continuing."
                            color: win.txt
                            font.family: win.uiFont
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        visible: win.systemManagedOnly(win.selectedApp)
                        text: win.rtl ? "مُدار مع النظام" : "System managed"
                        color: win.txt2
                        font.family: win.uiFont
                        font.pixelSize: 10
                        font.bold: true
                    }
                    Item { Layout.fillWidth: true }
                    ActionButton {
                        visible: win.canRemove(win.selectedApp)
                        enabled: !win.jobIsActive()
                        label: win.rtl ? "إزالة" : "Remove"
                        glyphName: "trash"
                        destructive: true
                        triggered: function() { win.removeSelected(win.selectedApp) }
                    }
                    ActionButton {
                        enabled: !win.isInstalled(win.selectedApp)
                                 || win.hasFlatpakLifecycle(win.selectedApp)
                        label: win.isInstalled(win.selectedApp)
                            ? win.hasFlatpakLifecycle(win.selectedApp)
                                ? (win.rtl ? "افتح التطبيق" : "Open app")
                                : (win.rtl ? "مثبّت وجاهز" : "Installed and ready")
                            : win.isWeb(win.selectedApp)
                                ? (win.rtl ? "افتح الموقع الرسمي" : "Open official website")
                                : (win.rtl ? "مراجعة وتثبيت" : "Review & install")
                        glyphName: win.isInstalled(win.selectedApp)
                            ? win.hasFlatpakLifecycle(win.selectedApp) ? "external" : "check"
                            : "download"
                        primary: true
                        triggered: function() {
                            if (win.isInstalled(win.selectedApp)
                                    && win.hasFlatpakLifecycle(win.selectedApp))
                                win.runSelected(win.selectedApp)
                            else {
                                details.close()
                                win.installOne(win.selectedApp)
                            }
                        }
                    }
                }
            }
        }
    }

    // One explicit review for a single app or a whole collection.
    Popup {
        id: review
        anchors.centerIn: Overlay.overlay
        width: Math.min(600, win.width - 70)
        height: Math.min(610, win.height - 70)
        modal: true
        padding: 0
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            radius: 24
            color: win.surface
            border.width: 1
            border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.4)
        }
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.54) }
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 13
            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    Layout.preferredWidth: 48
                    Layout.preferredHeight: 48
                    radius: 16
                    color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                    Glyph { anchors.centerIn: parent; width: 25; height: 25; name: "shield"; tint: win.accent }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1
                    Text {
                        text: win.onlyWebPicks()
                            ? win.pickCount === 1
                                ? (win.rtl ? "راجع الموقع الخارجي" : "Review external website")
                                : (win.rtl ? "راجع المواقع الخارجية" : "Review external websites")
                            : win.pickedWebCount() > 0
                                ? (win.rtl ? "راجع قبل المتابعة" : "Review before continuing")
                                : (win.rtl ? "راجع قبل التثبيت" : "Review before installing")
                        color: win.txt
                        font.family: win.uiFont
                        font.pixelSize: 18
                        font.bold: true
                    }
                    Text {
                        text: win.onlyWebPicks()
                            ? (win.rtl
                                ? "سيفتح Mo Store صفحة الناشر الرسمية عبر HTTPS؛ وأنت تُكمل أي تنزيل من هناك."
                                : "Mo Store opens the publisher's official HTTPS page; you complete any download there.")
                            : win.pickedWebCount() > 0
                                ? (win.rtl
                                    ? "تُثبت تطبيقات Flatpak للمستخدم فقط، وتفتح العناصر الخارجية صفحات ناشريها الرسمية."
                                    : "Flatpaks install for your user only; external items open their publishers' official pages.")
                                : (win.rtl
                                    ? "سيُثبت Flatpak بصلاحيات المستخدم فقط. المصادر المتقدمة موضحة أدناه."
                                    : "Flatpaks install for your user only. Advanced sources are clearly marked below.")
                        color: win.txt2
                        font.family: win.uiFont
                        font.pixelSize: 10
                    }
                }
            }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: win.outline; opacity: 0.6 }
            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 8
                model: Object.keys(win.picks)
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: Rectangle {
                    id: reviewItem
                    required property var modelData
                    readonly property var app: win.appById(modelData)
                    width: ListView.view.width
                    height: 68
                    radius: 15
                    color: Qt.rgba(win.canvas.r, win.canvas.g, win.canvas.b, 0.5)
                    border.width: 1
                    border.color: win.outline
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 10
                        AppArtwork { app: reviewItem.app; size: 44 }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            Text {
                                Layout.fillWidth: true
                                text: win.localName(reviewItem.app)
                                color: win.txt
                                font.family: win.uiFont
                                font.pixelSize: 12
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                text: win.reviewDetail(reviewItem.app)
                                color: reviewItem.app
                                       && (reviewItem.app.requires_review
                                           || (reviewItem.app.install
                                               && reviewItem.app.install.requires_review))
                                       ? win.violet : win.txt2
                                font.family: win.uiFont
                                font.pixelSize: 9
                                elide: Text.ElideRight
                            }
                        }
                        ActionButton {
                            label: win.rtl ? "إزالة" : "Remove"
                            glyphName: "trash"
                            triggered: function() { win.setPicked(reviewItem.modelData, false) }
                        }
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 58
                radius: 15
                color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.1)
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 9
                    Glyph { name: "lock"; tint: win.accent; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                    Text {
                        Layout.fillWidth: true
                        text: win.rtl
                            ? "لا صلاحية مسؤول، والمواقع الخارجية لا تثبّت تلقائياً؛ أدوات npm المعلّمة قد تشغّل سكربتات الحزمة بعد موافقتك."
                            : "No administrator access, and external websites never install automatically. Marked npm tools may run package scripts after your approval."
                        color: win.txt
                        font.family: win.uiFont
                        font.pixelSize: 10
                        wrapMode: Text.WordWrap
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                ActionButton {
                    label: win.rtl ? "رجوع" : "Back"
                    glyphName: "external"
                    triggered: function() { review.close() }
                }
                Item { Layout.fillWidth: true }
                ActionButton {
                    label: win.onlyWebPicks()
                        ? win.pickCount === 1
                            ? (win.rtl ? "افتح الموقع الرسمي" : "Open official website")
                            : (win.rtl ? "افتح المواقع الرسمية" : "Open official websites")
                        : win.pickedWebCount() > 0
                            ? (win.rtl ? "تابع مع " : "Continue with ") + win.pickCount
                            : (win.rtl ? "ثبّت " : "Install ") + win.pickCount
                    glyphName: win.onlyWebPicks() ? "external" : "download"
                    primary: true
                    enabled: win.pickCount > 0 && !win.jobIsActive()
                    triggered: function() { win.beginInstall() }
                }
            }
        }
    }

    Popup {
        id: toast
        x: (win.width - width) / 2
        y: win.height - 112
        width: Math.min(toastLabel.implicitWidth + 38, win.width - 60)
        height: 44
        padding: 0
        modal: false
        closePolicy: Popup.NoAutoClose
        background: Rectangle {
            radius: 16
            color: win.raised
            border.width: 1
            border.color: win.accent
        }
        Text {
            id: toastLabel
            anchors.centerIn: parent
            width: parent.width - 22
            horizontalAlignment: Text.AlignHCenter
            text: "Mo Store"
            color: win.txt
            font.family: win.uiFont
            font.pixelSize: 11
            elide: Text.ElideRight
        }
        Timer { id: toastTimer; interval: 2500; onTriggered: toast.close() }
    }
}
