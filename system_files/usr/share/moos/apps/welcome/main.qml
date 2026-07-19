// MoOS Welcome — the first-run onboarding wizard (a real welcome, not a store).
// Pure-QML (launched by /usr/bin/moos-welcome via moos-qml-shell). The store is
// a SEPARATE standalone app (apps/store, /usr/bin/moos-store) — this wizard
// hands over to it on the last page.
//
// WHAT IT DOES, IN SIX STEPS
//   0 hero       أهلاً بك — the MoOS mark, breathing.
//   1 look       Graphite dark / Tidal light — the pick applies INSTANTLY via
//                moos://theme/{dark,light} (moos-open runs moos-theme detached),
//                and because the KDE platform theme broadcasts palette changes,
//                this very window recolours live as proof.
//   2 direction  What is this machine for? gaming / development / study /
//                office — multi-select. Each direction is a catalog BUNDLE, so
//                what a direction installs is exactly what the store shows.
//   3 apps       The optional essentials (camera, recorder, reader…) plus the
//                apps the chosen directions brought in — all toggleable.
//   4 install    Fires moos://store/install/<id> per app (the same headless
//                path the store uses) and polls <cache>/moos-store/<id>.status
//                for live progress bars. No terminal, ever.
//   5 done       Open Mo Store / open Mo AI / finish.
//
// Every app id, category and bundle comes at runtime from
// /usr/share/moos/store/catalog.json — the SAME file /usr/bin/moos-install
// obeys — so the wizard can never offer what the system cannot install.
//
// Bilingual, Arabic-first, RTL-safe. Every structural colour comes from the
// active KDE palette so UI2 Graphite/Tidal recolours the whole wizard.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: win
    visible: true
    // Open at the design size, but never larger than the screen can hold — a
    // 1280×720 or 1366×768 laptop (with the panel eating height) must not get a
    // window taller than the desktop. Clamp to 92% of the available area.
    width: Math.min(1080, Screen.desktopAvailableWidth * 0.92)
    height: Math.min(760, Screen.desktopAvailableHeight * 0.92)
    minimumWidth: Math.min(860, Screen.desktopAvailableWidth * 0.92)
    minimumHeight: Math.min(600, Screen.desktopAvailableHeight * 0.92)
    title: qsTr("Welcome to MoOS")
    color: win.canvas

    // ── semantic palette (KDE colour scheme owns every structural colour) ──────
    readonly property color canvas:   win.palette.base
    readonly property color surface:  win.palette.alternateBase
    readonly property color raised:   win.palette.button
    readonly property color chrome:   win.palette.window
    readonly property color outline:  win.palette.mid
    readonly property color blue:     win.palette.highlight
    readonly property color cyan:     win.palette.link
    readonly property color violet:   win.palette.linkVisited
    readonly property color txt:      win.palette.windowText
    readonly property color txt2:     win.palette.placeholderText
    readonly property color onAccent: win.palette.highlightedText

    // Accent used throughout. Turquoise (link) is the MoOS Tidal accent;
    // fall back to highlight if a scheme leaves it unset.
    readonly property color accent: win.cyan.a > 0 ? win.cyan : win.blue

    // ── language (chosen on the hero, applied system-wide) ─────────────────────
    // MoOS speaks ONE language, the user's — not both stacked in every window.
    // `lang` drives every string in this wizard and, via moos://lang/<code>,
    // the whole session (Plasma UI + formats + Flatpak) through /usr/bin/moos-lang.
    // Seeded from the locale the window opened under so a system already set to
    // Arabic starts Arabic. Everything reads `rtl`, which now follows the CHOICE.
    property string lang: Qt.application.layoutDirection === Qt.RightToLeft ? "ar" : "en"
    readonly property bool rtl: win.lang === "ar"

    function chooseLang(which) {
        if (win.lang === which) return
        win.lang = which
        // Apply to the whole session — headless, whitelisted route. A full Plasma
        // UI-language switch lands at the next login; the wizard itself flips live
        // because every string reads `win.rtl` above.
        Qt.openUrlExternally("moos://lang/" + which)
    }

    // ── wizard state ───────────────────────────────────────────────────────────
    property int step: 0
    readonly property int stepCount: 6
    readonly property bool navPages: win.step >= 1 && win.step <= 3

    function goNext() { if (win.step < win.stepCount - 1) win.step++ }
    function goBack() { if (win.step > 0) win.step-- }

    // ── catalog data (filled at runtime) ──────────────────────────────────────
    property var cats: []            // [{id,en,ar,glyph}]
    property var apps: []            // [{id,cat,glyph,en,ar,desc_*,source,popular,preselect,install}]
    property var bundles: []         // [{id,en,ar,glyph,desc_ar,apps:[ids]}]
    property bool loaded: false
    property string loadError: ""

    // ── the look (step 1) ──────────────────────────────────────────────────────
    // "dark" = Graphite, "light" = Tidal. Seeded from the palette the window
    // actually opened with — the wizard can be reopened from the menu on a
    // system already switched to Light, and a hardcoded "dark" would highlight
    // the wrong card AND make tapping the real half a dead click (chooseLook
    // early-returns on equality). Same lightness test the wallpaper scene uses.
    property string look: win.canvas.hslLightness > 0.55 ? "light" : "dark"

    function chooseLook(which) {
        if (win.look === which) return
        win.look = which
        // Instant, headless, reversible. moos-open whitelists every MoOS theme
        // route (dark, light, nova, amethyst, midnight, aurora) and runs
        // moos-theme detached; the palette change flows back into this window
        // live through the KDE platform theme.
        Qt.openUrlExternally("moos://theme/" + which)
    }

    // ── directions (step 2) — each id is a catalog bundle id ──────────────────
    readonly property var directionIds: ["game-starter", "dev-starter",
                                         "study-starter", "office-starter"]
    readonly property var directionMeta: ({
        "game-starter":   { glyph: "gamepad",   en: "Gaming",      ar: "ألعاب" },
        "dev-starter":    { glyph: "code",      en: "Development", ar: "تطوير" },
        "study-starter":  { glyph: "bulb",      en: "Study",       ar: "دراسة" },
        "office-starter": { glyph: "briefcase", en: "Office",      ar: "مكتب" }
    })
    property var directions: ({})    // bundle id -> true

    // ── app picks (step 3) ─────────────────────────────────────────────────────
    property var picks: ({})         // app id -> true
    property int pickCount: 0

    function countPicks(p) { return Object.keys(p).length }

    function bundleById(id) {
        for (var i = 0; i < win.bundles.length; i++)
            if (win.bundles[i].id === id) return win.bundles[i]
        return null
    }

    function appById(id) {
        for (var i = 0; i < win.apps.length; i++)
            if (win.apps[i].id === id) return win.apps[i]
        return null
    }

    function togglePick(id) {
        var p = Object.assign({}, win.picks)
        if (p[id]) delete p[id]; else p[id] = true
        win.picks = p
        win.pickCount = win.countPicks(p)
    }

    function toggleDirection(id) {
        var b = win.bundleById(id)
        if (!b) return
        var d = Object.assign({}, win.directions)
        var p = Object.assign({}, win.picks)
        if (d[id]) {
            delete d[id]
            // Drop this direction's apps — unless another selected direction
            // still wants them, or they are recommended essentials.
            for (var i = 0; i < b.apps.length; i++) {
                var aid = b.apps[i]
                var covered = false
                for (var k in d) {
                    var ob = win.bundleById(k)
                    if (ob && ob.apps.indexOf(aid) >= 0) { covered = true; break }
                }
                var a = win.appById(aid)
                if (!covered && !(a && a.preselect)) delete p[aid]
            }
        } else {
            d[id] = true
            for (var j = 0; j < b.apps.length; j++) p[b.apps[j]] = true
        }
        win.directions = d
        win.picks = p
        win.pickCount = win.countPicks(p)
    }

    // The optional-apps grid (step 3): every essential, plus whatever the
    // chosen directions pulled in, plus the popular picks — deduplicated,
    // essentials first so the camera/recorder gaps the base image leaves are
    // the first thing the user sees.
    function optionalApps() {
        var seen = {}
        var out = []
        function push(a) {
            if (!a || seen[a.id]) return
            seen[a.id] = true
            out.push(a)
        }
        var i
        for (i = 0; i < win.apps.length; i++)
            if (win.apps[i].cat === "ess") push(win.apps[i])
        for (var k in win.directions) {
            var b = win.bundleById(k)
            if (!b) continue
            for (i = 0; i < b.apps.length; i++) push(win.appById(b.apps[i]))
        }
        for (i = 0; i < win.apps.length; i++)
            if (win.apps[i].popular) push(win.apps[i])
        return out
    }

    // ── install engine (step 4) — the exact store contract ────────────────────
    // installState[id] = { pct: 0..100, state: "queued"|"installing"|"done"|"opened"|"fail" }
    property var installState: ({})
    property bool installing: false
    property bool installFinished: false
    property var queue: []
    property int queueIdx: 0

    // Where moos-open drops per-app status files (from the launcher's --cache=).
    readonly property string cacheDir: win.argValue("--cache=")

    // Live session (booted from the USB, not yet installed): the launcher passes
    // --live=1. Drives the "Install MoOS on this computer" call-to-action on the
    // hero so the Welcome hands off cleanly into the installer.
    readonly property bool live: win.argValue("--live=") === "1"
    property bool installerHandoff: false

    // Welcome is the live session's single front door. Opening the installer is a
    // hand-off, not a second wizard layered on top: start the unique installer
    // instance, show immediate feedback, then retire this window. On the installed
    // system Welcome starts again after the first password login, with --live=0,
    // so personalisation and app choices are applied to the real user account.
    function handoffToInstaller() {
        if (!win.live || win.installerHandoff) return
        win.installerHandoff = true
        Qt.openUrlExternally("moos://installer/open")
        installerHandoffTimer.restart()
    }

    Timer {
        id: installerHandoffTimer
        interval: 700
        repeat: false
        onTriggered: Qt.quit()
    }

    function argValue(prefix) {
        var a = Qt.application.arguments
        for (var i = 0; i < a.length; i++)
            if (a[i].indexOf(prefix) === 0) return a[i].substring(prefix.length)
        return ""
    }

    function setState(id, pct, state) {
        var s = Object.assign({}, win.installState)
        s[id] = { pct: pct, state: state }
        win.installState = s
    }

    function overallProgress() {
        if (win.queue.length === 0) return 0
        var sum = 0
        for (var i = 0; i < win.queue.length; i++) {
            var st = win.installState[win.queue[i]]
            sum += st ? st.pct : 0
        }
        return sum / (win.queue.length * 100)
    }

    function startInstall() {
        var ids = Object.keys(win.picks)
        win.step = 4
        if (ids.length === 0) { win.installFinished = true; return }
        win.queue = ids
        win.queueIdx = 0
        win.installing = true
        win.installFinished = false
        var s = {}
        for (var i = 0; i < ids.length; i++) s[ids[i]] = { pct: 0, state: "queued" }
        win.installState = s
        win.installNext()
    }

    function installNext() {
        if (win.queueIdx >= win.queue.length) {
            win.installing = false
            win.installFinished = true
            pollTimer.stop()
            return
        }
        var id = win.queue[win.queueIdx]
        win.setState(id, 3, "installing")
        Qt.openUrlExternally("moos://store/install/" + id)
        if (win.cacheDir === "") {
            // No status path (bare-runtime fallback): fire-and-forget, best effort.
            fallbackTimer.restart()
            return
        }
        pollTimer.targetId = id
        pollTimer.miss = 0
        pollTimer.polls = 0
        pollTimer.restart()
    }

    function readStatus(id) {
        try {
            var req = new XMLHttpRequest()
            req.open("GET", "file://" + win.cacheDir + "/" + id + ".status", false)
            req.send()
            var t = req.responseText
            if (!t) return { pct: -1, state: "installing" }
            var lines = t.split("\n")
            for (var i = lines.length - 1; i >= 0; i--) {
                var ln = lines[i].trim()
                if (ln === "") continue
                if (ln.indexOf("PROGRESS ") === 0)
                    return { pct: parseInt(ln.substring(9)) || 0, state: "installing" }
                if (ln === "DONE")   return { pct: 100, state: "done" }
                if (ln === "OPENED") return { pct: 100, state: "opened" }
                if (ln.indexOf("FAIL") === 0) return { pct: 0, state: "fail" }
            }
            return { pct: -1, state: "installing" }
        } catch (e) {
            return { pct: -1, state: "installing" }
        }
    }

    Timer {
        id: pollTimer
        interval: 450; repeat: true
        property string targetId: ""
        property int miss: 0
        property int polls: 0
        onTriggered: {
            pollTimer.polls++
            var s = win.readStatus(pollTimer.targetId)
            // Stale-file grace: moos-open truncates the status file before the
            // install starts, but the truncation itself is behind xdg-open
            // dispatch. A terminal line seen in the FIRST beats can be last
            // run's verdict for the same app — ignore it; a genuine terminal
            // state is still there on the next poll.
            var terminal = (s.state === "done" || s.state === "opened" || s.state === "fail")
            if (terminal && pollTimer.polls <= 3) {
                return
            }
            if (s.pct >= 0) {
                pollTimer.miss = 0
                var cur = win.installState[pollTimer.targetId]
                var pct = Math.max(s.pct, cur ? cur.pct : 0)   // never go backwards
                win.setState(pollTimer.targetId, pct, s.state)
            }
            if (terminal) {
                pollTimer.stop()
                win.queueIdx++
                win.installNext()
            } else if (s.pct < 0) {
                // Status file absent/empty. Bounded: if nothing has appeared
                // after ~27s the moos:// dispatch itself failed (handler not
                // registered, moos-install unresolvable) — mark this app failed
                // and move on, or the wizard would sit on this page forever
                // with no Skip and no Continue.
                pollTimer.miss++
                if (pollTimer.miss > 60) {
                    win.setState(pollTimer.targetId, 0, "fail")
                    pollTimer.stop()
                    win.queueIdx++
                    win.installNext()
                }
            }
        }
    }

    // Bare-runtime fallback with no status file: advance after a beat.
    Timer {
        id: fallbackTimer
        interval: 1400
        onTriggered: {
            win.setState(win.queue[win.queueIdx], 100, "opened")
            win.queueIdx++
            win.installNext()
        }
    }

    // ── colour → #rrggbb (+ separate opacity). Qt's SVG-Tiny renderer supports
    //    hex and stroke-opacity, but NOT the CSS rgba() function — so use hex. ──
    function hex2(n) {
        var s = Math.round(Math.max(0, Math.min(1, n)) * 255).toString(16)
        return s.length < 2 ? "0" + s : s
    }
    function hexColor(c) { return "#" + hex2(c.r) + hex2(c.g) + hex2(c.b) }

    // ── line-glyph library (24×24, stroke-only, round joins) ───────────────────
    // The same curated set Mo Store draws from, so a catalog glyph renders
    // identically in both apps.
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
        "check":    "<path d='M5 12.5l4.5 4.5L19 7'/>",
        "sun":      "<circle cx='12' cy='12' r='4.2'/><path d='M12 2.5v2.4M12 19.1v2.4M2.5 12h2.4M19.1 12h2.4M5 5l1.7 1.7M17.3 17.3L19 19M19 5l-1.7 1.7M6.7 17.3L5 19'/>",
        "moon":     "<path d='M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z'/>"
    })

    function glyphURL(name, c, w) {
        var inner = win.glyphs[name] || win.glyphs["spark"]
        var svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
                + "stroke='" + win.hexColor(c) + "' stroke-opacity='" + c.a.toFixed(3) + "' "
                + "stroke-width='" + w + "' stroke-linecap='round' stroke-linejoin='round'>"
                + inner + "</svg>"
        // Qt 6.11's non-deprecated overload accepts an array-like value;
        // QML does not provide the browser-only TextEncoder host API.
        return "data:image/svg+xml;base64," + Qt.btoa(Array.from(svg))
    }

    // ── reusable glyph image ───────────────────────────────────────────────────
    component Glyph: Image {
        property string name: "spark"
        property color tint: win.txt
        property real stroke: 1.7
        source: win.glyphURL(name, tint, stroke)
        sourceSize.width: Math.max(2, width)
        sourceSize.height: Math.max(2, height)
        smooth: true
        fillMode: Image.PreserveAspectFit
    }

    // ── catalog load ───────────────────────────────────────────────────────────
    Component.onCompleted: loadCatalog()

    function loadCatalog() {
        try {
            var req = new XMLHttpRequest()
            req.open("GET", "file:///usr/share/moos/store/catalog.json", false)
            req.send()
            var doc = JSON.parse(req.responseText)
            win.cats = doc.categories || []
            win.apps = doc.apps || []
            win.bundles = doc.bundles || []
            // The recommended essentials start selected — the user un-picks,
            // not hunts.
            var p = {}
            for (var i = 0; i < win.apps.length; i++)
                if (win.apps[i].preselect) p[win.apps[i].id] = true
            win.picks = p
            win.pickCount = win.countPicks(p)
            win.loaded = true
        } catch (e) {
            win.loadError = "" + e
            win.loaded = false
        }
    }

    // ═══════════════════════════════ BACKGROUND ═══════════════════════════════
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: win.canvas }
            GradientStop { position: 1.0; color: win.chrome }
        }
    }
    Rectangle {   // ambient turquoise glow, trailing-top
        width: 560; height: 560; radius: 280
        anchors.right: parent.right; anchors.top: parent.top
        anchors.rightMargin: -200; anchors.topMargin: -220
        color: win.accent; opacity: 0.10
    }
    Rectangle {   // ambient blue glow, leading-bottom
        width: 440; height: 440; radius: 220
        anchors.left: parent.left; anchors.bottom: parent.bottom
        anchors.leftMargin: -170; anchors.bottomMargin: -190
        color: win.blue; opacity: 0.07
    }

    // ═══════════════════════════════ ROOT ═════════════════════════════════════
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        LayoutMirroring.enabled: win.rtl
        LayoutMirroring.childrenInherit: true

        // ───────────────────────────── HEADER ─────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 74

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 28; anchors.rightMargin: 28
                spacing: 14

                Image {
                    source: "file:///usr/share/moos/moos-logo.png"
                    sourceSize.width: 34; sourceSize.height: 34
                    Layout.preferredWidth: 34; Layout.preferredHeight: 34
                    opacity: win.step === 0 ? 0 : 1
                    Behavior on opacity { NumberAnimation { duration: 200 } }
                }

                Item { Layout.fillWidth: true }

                // step dots
                Row {
                    spacing: 9
                    Repeater {
                        model: win.stepCount
                        delegate: Rectangle {
                            id: dot
                            required property int index
                            width: dot.index === win.step ? 26 : 8
                            height: 8
                            radius: 4
                            color: dot.index === win.step ? win.accent
                                 : dot.index < win.step
                                   ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.45)
                                   : Qt.rgba(win.outline.r, win.outline.g, win.outline.b, 0.8)
                            Behavior on width { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // skip — always an exit, never a trap
                Rectangle {
                    visible: win.step < 4
                    Layout.preferredHeight: 34
                    implicitWidth: skipRow.implicitWidth + 26
                    radius: 17
                    color: skipHover.hovered
                           ? Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.9)
                           : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.0)
                    border.width: 1
                    border.color: Qt.rgba(win.outline.r, win.outline.g, win.outline.b,
                                          skipHover.hovered ? 1.0 : 0.0)
                    Behavior on color { ColorAnimation { duration: 120 } }
                    HoverHandler { id: skipHover }
                    TapHandler { onTapped: win.step = 5 }
                    RowLayout {
                        id: skipRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: win.rtl ? "تخطّي" : "Skip"
                            color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 13
                        }
                    }
                }
            }
        }

        // ─────────────────────────────── PAGES ────────────────────────────────
        StackLayout {
            id: pages
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: win.step

            // ════════ 0 · HERO ════════
            Item {
                id: hero

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 0
                    width: Math.min(640, hero.width - 80)

                    Item {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 168
                        Layout.preferredHeight: 168

                        // breathing halo rings
                        Repeater {
                            model: 2
                            delegate: Rectangle {
                                id: ring
                                required property int index
                                anchors.centerIn: parent
                                width: 128 + ring.index * 34
                                height: width
                                radius: width / 2
                                color: "transparent"
                                border.width: 1
                                border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b,
                                                      0.34 - ring.index * 0.12)
                                SequentialAnimation on scale {
                                    running: hero.visible
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 1.06; duration: 2600 + ring.index * 500; easing.type: Easing.InOutSine }
                                    NumberAnimation { to: 1.0;  duration: 2600 + ring.index * 500; easing.type: Easing.InOutSine }
                                }
                            }
                        }
                        Rectangle {   // soft core glow behind the mark
                            anchors.centerIn: parent
                            width: 120; height: 120; radius: 60
                            color: win.accent
                            opacity: 0.14
                        }
                        Image {
                            anchors.centerIn: parent
                            source: "file:///usr/share/moos/moos-logo.png"
                            sourceSize.width: 104; sourceSize.height: 104
                            width: 104; height: 104
                        }
                    }

                    Item { Layout.preferredHeight: 26 }

                    // Language choice — the first decision, applied at once. Both
                    // names are shown on their own buttons (a language picker is
                    // the one place both languages belong); everything after this
                    // speaks only the one picked.
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 10
                        Repeater {
                            model: [ { id: "ar", label: "العربية" },
                                     { id: "en", label: "English" } ]
                            delegate: Rectangle {
                                id: langPill
                                required property var modelData
                                readonly property bool on: win.lang === langPill.modelData.id
                                Layout.preferredHeight: 40
                                implicitWidth: langLabel.implicitWidth + 44
                                radius: 20
                                color: langPill.on ? win.accent
                                     : langHover.hovered ? Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.9)
                                     : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.5)
                                border.width: 1
                                border.color: langPill.on ? win.accent : win.outline
                                Behavior on color { ColorAnimation { duration: 120 } }
                                HoverHandler { id: langHover }
                                TapHandler { onTapped: win.chooseLang(langPill.modelData.id) }
                                Text {
                                    id: langLabel
                                    anchors.centerIn: parent
                                    text: langPill.modelData.label
                                    color: langPill.on ? win.onAccent : win.txt
                                    font.family: "IBM Plex Sans"
                                    font.pixelSize: 16
                                    font.weight: langPill.on ? Font.DemiBold : Font.Normal
                                }
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 24 }

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.rtl ? "أهلاً بك في MoOS" : "Welcome to MoOS"
                        color: win.txt
                        font.family: "IBM Plex Sans"
                        font.pixelSize: 40
                        font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 18 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: win.rtl
                              ? "دقيقتان نجهّز فيهما نظامك: مظهرك، وجهة استخدامك، وتطبيقاتك — كلها بنقرات."
                              : "Two minutes to make this system yours: your look, your direction, your apps — all in taps."
                        color: win.txt2
                        font.family: "IBM Plex Sans"
                        font.pixelSize: 15
                        lineHeight: 1.35
                    }
                    Item { Layout.preferredHeight: 34 }

                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredHeight: 52
                        implicitWidth: beginRow.implicitWidth + 64
                        radius: 26
                        color: beginHover.hovered ? Qt.lighter(win.accent, 1.08) : win.accent
                        Behavior on color { ColorAnimation { duration: 120 } }
                        HoverHandler { id: beginHover }
                        TapHandler { onTapped: win.goNext() }
                        RowLayout {
                            id: beginRow
                            anchors.centerIn: parent
                            spacing: 10
                            Text {
                                text: win.rtl ? "لنبدأ" : "Let's begin"
                                color: win.onAccent
                                font.family: "IBM Plex Sans"
                                font.pixelSize: 17
                                font.weight: Font.DemiBold
                            }
                        }
                    }

                    // ── Live session hand-off ──────────────────────────────────
                    // On the live USB, the Welcome is the first thing the user sees,
                    // so this is exactly where "install MoOS for real" belongs. A
                    // secondary (outlined) action under "Let's begin" opens the
                    // installer UI via the moos://installer/open route (handled by
                    // moos-open). Hidden on an already installed system.
                    Item { visible: win.live; Layout.preferredHeight: 14 }
                    Rectangle {
                        visible: win.live
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredHeight: 50
                        implicitWidth: installRow.implicitWidth + 56
                        radius: 25
                        color: installHover.hovered ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.10)
                                                    : "transparent"
                        border.width: 1.5
                        border.color: installHover.hovered ? win.accent : win.outline
                        Behavior on border.color { ColorAnimation { duration: 120 } }
                        Behavior on color { ColorAnimation { duration: 120 } }
                        HoverHandler { id: installHover }
                        TapHandler {
                            enabled: !win.installerHandoff
                            onTapped: win.handoffToInstaller()
                        }
                        RowLayout {
                            id: installRow
                            anchors.centerIn: parent
                            spacing: 10
                            Text {
                                text: win.installerHandoff
                                      ? (win.rtl ? "نفتح المثبّت…" : "Opening installer…")
                                      : (win.rtl ? "ثبّت MoOS على هذا الكمبيوتر"
                                                 : "Install MoOS on this computer")
                                color: win.txt
                                font.family: "IBM Plex Sans"
                                font.pixelSize: 15
                                font.weight: Font.DemiBold
                            }
                        }
                    }
                    Text {
                        visible: win.live
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 8
                        horizontalAlignment: Text.AlignHCenter
                        text: win.rtl ? "أنت الآن على النسخة الحيّة — جرّب بحرّية، وثبّت متى شئت"
                                      : "You're on the live version — explore freely, install whenever you like"
                        color: win.txt2
                        font.family: "IBM Plex Sans"
                        font.pixelSize: 12
                    }
                }
            }

            // ════════ 1 · THE LOOK ════════
            Item {
                id: lookPage

                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(860, lookPage.width - 72)
                    spacing: 0

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.rtl ? "اختر مظهرك" : "Pick your look"
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 30; font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 8 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.rtl ? "يطبَّق فوراً — وهذه النافذة نفسها ستتلوّن أمامك"
                                      : "Applies instantly — this very window recolours as proof"
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 14
                    }
                    Item { Layout.preferredHeight: 30 }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 3
                        columnSpacing: 18
                        rowSpacing: 18

                        // one card per MoOS look — the whole family, pick any
                        Repeater {
                            model: [
                                { id: "dark",  glyph: "moon", en: "Graphite",    ar: "غرافيت داكن",
                                  canvasC: "#14191C", chromeC: "#1C2226", accentC: "#4ED7C8", txtC: "#E8F1EF" },
                                { id: "light", glyph: "sun",  en: "Tidal Light", ar: "تايدل فاتح",
                                  canvasC: "#D8EBE7", chromeC: "#C7E0DA", accentC: "#0E8577", txtC: "#17272B" },
                                { id: "nova",  glyph: "moon", en: "Nova",        ar: "نوفا",
                                  canvasC: "#0A1120", chromeC: "#111A2E", accentC: "#38BDF8", txtC: "#EAF2FF" },
                                { id: "amethyst", glyph: "moon", en: "Amethyst", ar: "أميثيست",
                                  canvasC: "#17121F", chromeC: "#201829", accentC: "#C084FC", txtC: "#F1E9F5" },
                                { id: "midnight", glyph: "moon", en: "Midnight", ar: "منتصف الليل",
                                  canvasC: "#000000", chromeC: "#0A0A0C", accentC: "#22D3EE", txtC: "#F5F7FA" },
                                { id: "aurora", glyph: "moon", en: "Aurora",     ar: "أورورا",
                                  canvasC: "#0E1524", chromeC: "#172236", accentC: "#2DD4BF", txtC: "#ECF2FB" }
                            ]
                            delegate: Rectangle {
                                id: lookCard
                                required property var modelData
                                readonly property bool selected: win.look === lookCard.modelData.id
                                Layout.fillWidth: true
                                Layout.preferredHeight: 172
                                radius: 20
                                color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b,
                                               lookHover.hovered || lookCard.selected ? 0.95 : 0.6)
                                border.width: lookCard.selected ? 2 : 1
                                border.color: lookCard.selected ? win.accent : win.outline
                                Behavior on color { ColorAnimation { duration: 130 } }
                                Behavior on border.color { ColorAnimation { duration: 130 } }
                                HoverHandler { id: lookHover }
                                TapHandler { onTapped: win.chooseLook(lookCard.modelData.id) }

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 18
                                    spacing: 12

                                    // miniature desktop preview, drawn live
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        radius: 14
                                        color: lookCard.modelData.canvasC
                                        clip: true

                                        Rectangle {   // preview glow
                                            width: parent.width * 0.7; height: width; radius: width / 2
                                            x: parent.width * 0.55; y: -width * 0.55
                                            color: lookCard.modelData.accentC
                                            opacity: 0.16
                                        }
                                        // mini glass bento (the desktop dashboard)
                                        Rectangle {
                                            x: 14; y: 14
                                            width: parent.width * 0.46; height: 42; radius: 9
                                            color: Qt.lighter(lookCard.modelData.canvasC, 1.35)
                                            opacity: 0.9
                                            Rectangle {
                                                x: 9; y: 9; width: 34; height: 10; radius: 5
                                                color: lookCard.modelData.accentC; opacity: 0.85
                                            }
                                            Rectangle {
                                                x: 9; y: 25; width: 52; height: 7; radius: 3.5
                                                color: lookCard.modelData.txtC; opacity: 0.35
                                            }
                                        }
                                        // mini dock capsule
                                        Rectangle {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            anchors.bottom: parent.bottom
                                            anchors.bottomMargin: 10
                                            width: parent.width * 0.5; height: 16; radius: 8
                                            color: Qt.lighter(lookCard.modelData.canvasC, 1.4)
                                            opacity: 0.95
                                            Row {
                                                anchors.centerIn: parent
                                                spacing: 6
                                                Repeater {
                                                    model: 5
                                                    delegate: Rectangle {
                                                        required property int index
                                                        width: 8; height: 8; radius: 2.5
                                                        color: lookCard.modelData.accentC
                                                        opacity: 0.75
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 10
                                        Glyph {
                                            name: lookCard.modelData.glyph
                                            tint: lookCard.selected ? win.accent : win.txt2
                                            Layout.preferredWidth: 20; Layout.preferredHeight: 20
                                        }
                                        ColumnLayout {
                                            spacing: 0
                                            Text {
                                                text: win.rtl ? lookCard.modelData.ar : lookCard.modelData.en
                                                color: win.txt
                                                font.family: "IBM Plex Sans"; font.pixelSize: 16; font.weight: Font.DemiBold
                                            }
                                            Text {
                                                text: win.rtl ? lookCard.modelData.en : lookCard.modelData.ar
                                                color: win.txt2
                                                font.family: "IBM Plex Sans"; font.pixelSize: 12
                                            }
                                        }
                                        Item { Layout.fillWidth: true }
                                        Rectangle {   // selected tick
                                            Layout.preferredWidth: 26; Layout.preferredHeight: 26
                                            radius: 13
                                            color: lookCard.selected ? win.accent : "transparent"
                                            border.width: lookCard.selected ? 0 : 1
                                            border.color: win.outline
                                            Behavior on color { ColorAnimation { duration: 130 } }
                                            Glyph {
                                                visible: lookCard.selected
                                                anchors.centerIn: parent
                                                name: "check"; tint: win.onAccent; stroke: 2.4
                                                width: 14; height: 14
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 14 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.rtl ? "وضع تلقائي (نهار/ليل)؟ من أي طرفية: moos-theme auto"
                                      : "Auto day/night? From any terminal: moos-theme auto"
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 12
                        opacity: 0.8
                    }
                }
            }

            // ════════ 2 · DIRECTION ════════
            Item {
                id: dirPage

                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(860, dirPage.width - 72)
                    spacing: 0

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.rtl ? "وجهة هذا الجهاز؟" : "What is this machine for?"
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 30; font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 8 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.rtl ? "اختر اتجاهاً أو أكثر — وسنجهّز عدّته كاملة"
                                      : "Pick one or more directions — we prepare the full kit"
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 14
                    }
                    Item { Layout.preferredHeight: 28 }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        rowSpacing: 18
                        columnSpacing: 18

                        Repeater {
                            model: win.directionIds
                            delegate: Rectangle {
                                id: dirCard
                                required property string modelData
                                readonly property var meta: win.directionMeta[dirCard.modelData]
                                readonly property var bundle: win.bundleById(dirCard.modelData)
                                readonly property bool selected: win.directions[dirCard.modelData] === true
                                Layout.fillWidth: true
                                Layout.preferredHeight: 116
                                radius: 20
                                color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b,
                                               dirHover.hovered || dirCard.selected ? 0.95 : 0.6)
                                border.width: dirCard.selected ? 2 : 1
                                border.color: dirCard.selected ? win.accent : win.outline
                                Behavior on color { ColorAnimation { duration: 130 } }
                                Behavior on border.color { ColorAnimation { duration: 130 } }
                                HoverHandler { id: dirHover }
                                TapHandler { onTapped: win.toggleDirection(dirCard.modelData) }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 18
                                    spacing: 16

                                    Rectangle {
                                        Layout.preferredWidth: 56; Layout.preferredHeight: 56
                                        radius: 16
                                        color: dirCard.selected
                                               ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.18)
                                               : Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.9)
                                        Behavior on color { ColorAnimation { duration: 130 } }
                                        Glyph {
                                            anchors.centerIn: parent
                                            name: dirCard.meta.glyph
                                            tint: dirCard.selected ? win.accent : win.txt
                                            stroke: 1.6
                                            width: 30; height: 30
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 3
                                        Text {
                                            text: win.rtl ? dirCard.meta.ar : dirCard.meta.en
                                            color: win.txt
                                            font.family: "IBM Plex Sans"; font.pixelSize: 18; font.weight: Font.DemiBold
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: dirCard.bundle
                                                  ? (win.rtl ? dirCard.bundle.desc_ar
                                                             : dirCard.bundle.en + " — "
                                                               + dirCard.bundle.apps.length
                                                               + " apps")
                                                  : ""
                                            color: win.txt2
                                            font.family: "IBM Plex Sans"; font.pixelSize: 13
                                            wrapMode: Text.WordWrap
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                        }
                                    }

                                    Rectangle {
                                        Layout.preferredWidth: 26; Layout.preferredHeight: 26
                                        radius: 13
                                        color: dirCard.selected ? win.accent : "transparent"
                                        border.width: dirCard.selected ? 0 : 1
                                        border.color: win.outline
                                        Behavior on color { ColorAnimation { duration: 130 } }
                                        Glyph {
                                            visible: dirCard.selected
                                            anchors.centerIn: parent
                                            name: "check"; tint: win.onAccent; stroke: 2.4
                                            width: 14; height: 14
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 14 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.rtl ? "ولا واحد؟ لا بأس — نظامك يبقى نظيفاً وتجد كل شيء في متجر Mo Store"
                                      : "None? Fine — the system stays clean, and Mo Store has everything"
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 12
                        opacity: 0.8
                    }
                }
            }

            // ════════ 3 · OPTIONAL APPS ════════
            Item {
                id: appsPage

                ColumnLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Math.max(36, (appsPage.width - 900) / 2)
                    anchors.rightMargin: Math.max(36, (appsPage.width - 900) / 2)
                    anchors.topMargin: 6
                    spacing: 0

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.rtl ? "تطبيقاتك الاختيارية" : "Your optional apps"
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 30; font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 8 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.rtl ? "الكاميرا والمسجّل والقارئ وأصحابهم — علِّم ما تريد، والباقي في المتجر"
                                      : "Camera, recorder, reader and friends — tick what you want; the rest lives in the store"
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 14
                    }
                    Item { Layout.preferredHeight: 20 }

                    Flickable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        contentWidth: width
                        contentHeight: appsGrid.implicitHeight + 20
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        GridLayout {
                            id: appsGrid
                            width: parent.width
                            columns: Math.max(2, Math.floor(width / 290))
                            rowSpacing: 12
                            columnSpacing: 12

                            Repeater {
                                model: win.loaded ? win.optionalApps() : []
                                delegate: Rectangle {
                                    id: appCard
                                    required property var modelData
                                    readonly property bool selected: win.picks[appCard.modelData.id] === true
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 74
                                    radius: 16
                                    color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b,
                                                   appHover.hovered || appCard.selected ? 0.95 : 0.55)
                                    border.width: 1
                                    border.color: appCard.selected ? win.accent : win.outline
                                    Behavior on color { ColorAnimation { duration: 120 } }
                                    Behavior on border.color { ColorAnimation { duration: 120 } }
                                    HoverHandler { id: appHover }
                                    TapHandler { onTapped: win.togglePick(appCard.modelData.id) }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 14; anchors.rightMargin: 14
                                        spacing: 12

                                        Rectangle {
                                            Layout.preferredWidth: 42; Layout.preferredHeight: 42
                                            radius: 12
                                            color: appCard.selected
                                                   ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                                                   : Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.9)
                                            Glyph {
                                                anchors.centerIn: parent
                                                name: appCard.modelData.glyph
                                                tint: appCard.selected ? win.accent : win.txt
                                                width: 22; height: 22
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 1
                                            Text {
                                                text: win.rtl ? appCard.modelData.ar : appCard.modelData.en
                                                color: win.txt
                                                font.family: "IBM Plex Sans"; font.pixelSize: 15; font.weight: Font.DemiBold
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }
                                            Text {
                                                text: win.rtl ? (appCard.modelData.desc_ar || "")
                                                              : (appCard.modelData.desc_en || "")
                                                color: win.txt2
                                                font.family: "IBM Plex Sans"; font.pixelSize: 12
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }
                                        }

                                        Rectangle {
                                            Layout.preferredWidth: 22; Layout.preferredHeight: 22
                                            radius: 11
                                            color: appCard.selected ? win.accent : "transparent"
                                            border.width: appCard.selected ? 0 : 1
                                            border.color: win.outline
                                            Behavior on color { ColorAnimation { duration: 120 } }
                                            Glyph {
                                                visible: appCard.selected
                                                anchors.centerIn: parent
                                                name: "check"; tint: win.onAccent; stroke: 2.6
                                                width: 12; height: 12
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // load error surface — never a blank page
                    Text {
                        visible: !win.loaded && win.loadError !== ""
                        Layout.alignment: Qt.AlignHCenter
                        text: (win.rtl ? "تعذّر قراءة الكتالوج: " : "Could not read the catalog: ") + win.loadError
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 13
                    }
                }
            }

            // ════════ 4 · INSTALL ════════
            Item {
                id: installPage

                ColumnLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Math.max(36, (installPage.width - 760) / 2)
                    anchors.rightMargin: Math.max(36, (installPage.width - 760) / 2)
                    anchors.topMargin: 6
                    spacing: 0

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.installFinished
                              ? (win.rtl ? "اكتمل التجهيز" : "Setup complete")
                              : (win.rtl ? "نجهّز نظامك…" : "Preparing your system…")
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 30; font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 8 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        visible: !win.installFinished
                        text: win.rtl ? "بلا طرفية. اترك النافذة مفتوحة حتى ينتهي الطابور"
                                      : "No terminal. Keep this window open until the queue finishes"
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 14
                    }
                    Item { Layout.preferredHeight: 22 }

                    // overall bar
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 10
                        radius: 5
                        color: Qt.rgba(win.outline.r, win.outline.g, win.outline.b, 0.5)
                        Rectangle {
                            width: parent.width * win.overallProgress()
                            height: parent.height
                            radius: 5
                            color: win.accent
                            Behavior on width { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
                        }
                    }
                    Item { Layout.preferredHeight: 18 }

                    Flickable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        contentWidth: width
                        contentHeight: installCol.implicitHeight + 16
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        ColumnLayout {
                            id: installCol
                            width: parent.width
                            spacing: 10

                            Repeater {
                                model: win.queue
                                delegate: Rectangle {
                                    id: instRow
                                    required property string modelData
                                    readonly property var app: win.appById(instRow.modelData)
                                    readonly property var st: win.installState[instRow.modelData]
                                                              || { pct: 0, state: "queued" }
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 64
                                    radius: 14
                                    color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.7)
                                    border.width: 1
                                    border.color: instRow.st.state === "fail"
                                                  ? win.violet
                                                  : Qt.rgba(win.outline.r, win.outline.g, win.outline.b, 0.8)

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 14; anchors.rightMargin: 16
                                        spacing: 12

                                        Rectangle {
                                            Layout.preferredWidth: 38; Layout.preferredHeight: 38
                                            radius: 11
                                            color: Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.9)
                                            Glyph {
                                                anchors.centerIn: parent
                                                name: instRow.app ? instRow.app.glyph : "spark"
                                                tint: instRow.st.state === "done" || instRow.st.state === "opened"
                                                      ? win.accent : win.txt
                                                width: 20; height: 20
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 5
                                            RowLayout {
                                                Layout.fillWidth: true
                                                Text {
                                                    text: instRow.app ? (win.rtl ? instRow.app.ar : instRow.app.en)
                                                                      : instRow.modelData
                                                    color: win.txt
                                                    font.family: "IBM Plex Sans"; font.pixelSize: 14; font.weight: Font.DemiBold
                                                }
                                                Item { Layout.fillWidth: true }
                                                Text {
                                                    text: instRow.st.state === "done"   ? (win.rtl ? "تم ✓" : "Done ✓")
                                                        : instRow.st.state === "opened" ? (win.rtl ? "فُتحت صفحته" : "Page opened")
                                                        : instRow.st.state === "fail"   ? (win.rtl ? "تعذّر" : "Failed")
                                                        : instRow.st.state === "queued" ? (win.rtl ? "بالانتظار" : "Queued")
                                                        : instRow.st.pct + "%"
                                                    color: instRow.st.state === "done" || instRow.st.state === "opened"
                                                           ? win.accent
                                                           : instRow.st.state === "fail" ? win.violet : win.txt2
                                                    font.family: "IBM Plex Sans"; font.pixelSize: 13
                                                }
                                            }
                                            Rectangle {
                                                Layout.fillWidth: true
                                                Layout.preferredHeight: 5
                                                radius: 2.5
                                                color: Qt.rgba(win.outline.r, win.outline.g, win.outline.b, 0.45)
                                                Rectangle {
                                                    width: parent.width * (instRow.st.pct / 100)
                                                    height: parent.height
                                                    radius: 2.5
                                                    color: instRow.st.state === "fail" ? win.violet : win.accent
                                                    Behavior on width { NumberAnimation { duration: 220 } }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // nothing was picked
                            Text {
                                visible: win.queue.length === 0
                                Layout.alignment: Qt.AlignHCenter
                                Layout.topMargin: 30
                                text: win.rtl ? "لم تختر تطبيقات — نظامك جاهز كما هو."
                                              : "No apps picked — your system is ready as it is."
                                color: win.txt2
                                font.family: "IBM Plex Sans"; font.pixelSize: 14
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 14 }
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        visible: win.installFinished
                        Layout.preferredHeight: 48
                        implicitWidth: contRow.implicitWidth + 56
                        radius: 24
                        color: contHover.hovered ? Qt.lighter(win.accent, 1.08) : win.accent
                        Behavior on color { ColorAnimation { duration: 120 } }
                        HoverHandler { id: contHover }
                        TapHandler { onTapped: win.goNext() }
                        RowLayout {
                            id: contRow
                            anchors.centerIn: parent
                            Text {
                                text: win.rtl ? "متابعة" : "Continue"
                                color: win.onAccent
                                font.family: "IBM Plex Sans"; font.pixelSize: 16; font.weight: Font.DemiBold
                            }
                        }
                    }
                    Item { Layout.preferredHeight: 10 }
                }
            }

            // ════════ 5 · DONE ════════
            Item {
                id: donePage

                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(620, donePage.width - 80)
                    spacing: 0

                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 96; Layout.preferredHeight: 96
                        radius: 48
                        color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                        border.width: 2
                        border.color: win.accent
                        scale: donePage.visible ? 1 : 0.6
                        Behavior on scale { NumberAnimation { duration: 320; easing.type: Easing.OutBack } }
                        Glyph {
                            anchors.centerIn: parent
                            name: "check"; tint: win.accent; stroke: 2.6
                            width: 44; height: 44
                        }
                    }

                    Item { Layout.preferredHeight: 26 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.rtl ? "نظامك جاهز" : "Your system is ready"
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 34; font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 10 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: win.rtl
                              ? "متجر Mo Store دائماً في متناولك، وMo AI مساعدك في كل شيء — أهلاً بك في بيتك الجديد."
                              : "Mo Store is always at hand, and Mo AI helps with everything — welcome home."
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 15
                        lineHeight: 1.35
                    }
                    Item { Layout.preferredHeight: 32 }

                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 14

                        Rectangle {
                            Layout.preferredHeight: 50
                            implicitWidth: storeRow.implicitWidth + 52
                            radius: 25
                            color: storeHover.hovered ? Qt.lighter(win.accent, 1.08) : win.accent
                            Behavior on color { ColorAnimation { duration: 120 } }
                            HoverHandler { id: storeHover }
                            TapHandler { onTapped: Qt.openUrlExternally("moos://app/store") }
                            RowLayout {
                                id: storeRow
                                anchors.centerIn: parent
                                spacing: 8
                                Text {
                                    text: win.rtl ? "افتح متجر Mo Store" : "Open Mo Store"
                                    color: win.onAccent
                                    font.family: "IBM Plex Sans"; font.pixelSize: 15; font.weight: Font.DemiBold
                                }
                            }
                        }

                        Rectangle {
                            Layout.preferredHeight: 50
                            implicitWidth: aiRow.implicitWidth + 52
                            radius: 25
                            color: aiHover.hovered
                                   ? Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.95)
                                   : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.6)
                            border.width: 1
                            border.color: win.outline
                            Behavior on color { ColorAnimation { duration: 120 } }
                            HoverHandler { id: aiHover }
                            TapHandler { onTapped: Qt.openUrlExternally("moos://app/moai") }
                            RowLayout {
                                id: aiRow
                                anchors.centerIn: parent
                                spacing: 8
                                Glyph { name: "spark"; tint: win.accent; width: 17; height: 17 }
                                Text {
                                    text: win.rtl ? "افتح Mo AI" : "Open Mo AI"
                                    color: win.txt
                                    font.family: "IBM Plex Sans"; font.pixelSize: 15; font.weight: Font.DemiBold
                                }
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 16 }
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredHeight: 38
                        implicitWidth: quitRow.implicitWidth + 34
                        radius: 19
                        color: "transparent"
                        border.width: 1
                        border.color: Qt.rgba(win.outline.r, win.outline.g, win.outline.b,
                                              quitHover.hovered ? 1.0 : 0.0)
                        HoverHandler { id: quitHover }
                        TapHandler { onTapped: Qt.quit() }
                        RowLayout {
                            id: quitRow
                            anchors.centerIn: parent
                            Text {
                                text: win.rtl ? "إنهاء" : "Finish"
                                color: win.txt2
                                font.family: "IBM Plex Sans"; font.pixelSize: 14
                            }
                        }
                    }
                }
            }
        }

        // ─────────────────────────────── FOOTER NAV ───────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: win.navPages ? 84 : 12
            Behavior on Layout.preferredHeight { NumberAnimation { duration: 180 } }

            RowLayout {
                visible: win.navPages
                anchors.fill: parent
                anchors.leftMargin: 34; anchors.rightMargin: 34
                anchors.bottomMargin: 22
                spacing: 12

                Rectangle {   // back
                    Layout.preferredHeight: 46
                    implicitWidth: backRow.implicitWidth + 44
                    radius: 23
                    color: backHover.hovered
                           ? Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.95)
                           : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.5)
                    border.width: 1
                    border.color: win.outline
                    Behavior on color { ColorAnimation { duration: 120 } }
                    HoverHandler { id: backHover }
                    TapHandler { onTapped: win.goBack() }
                    RowLayout {
                        id: backRow
                        anchors.centerIn: parent
                        Text {
                            text: win.rtl ? "السابق" : "Back"
                            color: win.txt
                            font.family: "IBM Plex Sans"; font.pixelSize: 15
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                Text {
                    visible: win.step === 3
                    text: win.pickCount + (win.rtl ? " مختار" : " selected")
                    color: win.txt2
                    font.family: "IBM Plex Sans"; font.pixelSize: 14
                }

                Rectangle {   // next / install
                    Layout.preferredHeight: 46
                    implicitWidth: nextRow.implicitWidth + 52
                    radius: 23
                    color: nextHover.hovered ? Qt.lighter(win.accent, 1.08) : win.accent
                    Behavior on color { ColorAnimation { duration: 120 } }
                    HoverHandler { id: nextHover }
                    TapHandler {
                        onTapped: {
                            if (win.step === 3) win.startInstall()
                            else win.goNext()
                        }
                    }
                    RowLayout {
                        id: nextRow
                        anchors.centerIn: parent
                        spacing: 8
                        Text {
                            text: win.step === 3
                                  ? (win.pickCount > 0
                                     ? (win.rtl ? "ثبّت الآن" : "Install now")
                                     : (win.rtl ? "متابعة بلا تثبيت" : "Continue without installing"))
                                  : (win.rtl ? "التالي" : "Next")
                            color: win.onAccent
                            font.family: "IBM Plex Sans"; font.pixelSize: 15; font.weight: Font.DemiBold
                        }
                    }
                }
            }
        }
    }
}
