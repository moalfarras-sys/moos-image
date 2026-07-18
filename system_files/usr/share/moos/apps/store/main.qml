// Mo Store — MoOS's own storefront, a standalone app. Pure-QML (launched by
// /usr/bin/moos-store via moos-qml-shell). The first-run onboarding is a
// SEPARATE app (apps/welcome) — this window is the store the user returns to.
//
// WHAT IT IS
//   A real store, not a static page. Every app, category and bundle is read at
//   runtime from /usr/share/moos/store/catalog.json — the SAME file /usr/bin/
//   moos-install obeys — so what the user can pick here is exactly what can be
//   installed, with no second list to drift.
//
// HOW INSTALL WORKS WITH NO TERMINAL AND NO C++ BRIDGE
//   Pure QML cannot spawn a process, so each pick fires
//   Qt.openUrlExternally("moos://store/install/<id>"). moos-open validates the id
//   against the catalog (a curated, safe set — hence no confirmation prompt) and
//   runs moos-install headless, streaming PROGRESS/DONE/FAIL/OPENED into
//   <cache>/moos-store/<id>.status. This window polls that file for a live bar.
//   The cache path is handed in as --cache= by the launcher (QML has no $HOME).
//
// Bilingual, Arabic-first, RTL-safe. Every structural colour comes from the
// active KDE palette so UI2 Graphite/Tidal recolours the whole store.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: win
    visible: true
    // Open at the design size, clamped to what the screen can actually hold so a
    // 1280×720 / 1366×768 laptop never gets an oversized window (see Welcome).
    width: Math.min(1080, Screen.desktopAvailableWidth * 0.92)
    height: Math.min(728, Screen.desktopAvailableHeight * 0.92)
    minimumWidth: Math.min(880, Screen.desktopAvailableWidth * 0.92)
    minimumHeight: Math.min(560, Screen.desktopAvailableHeight * 0.92)
    title: qsTr("Mo Store")
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

    // Accent used through the store. Turquoise (link) is the MoOS Tidal accent;
    // fall back to highlight if a scheme leaves it unset.
    readonly property color accent: win.cyan.a > 0 ? win.cyan : win.blue

    readonly property bool rtl: Qt.application.layoutDirection === Qt.RightToLeft

    // ── catalog data (filled at runtime) ──────────────────────────────────────
    property var cats: []            // [{id,en,ar,glyph}]
    property var apps: []            // [{id,cat,glyph,en,ar,desc_*,rating,reviews,source,popular,preselect,install}]
    property var bundles: []         // [{id,en,ar,glyph,desc_ar,apps:[ids]}]
    property bool loaded: false
    property string loadError: ""

    property string activeCat: "all"
    property string query: ""
    property var filtered: []

    // ── selection ("cart") ─────────────────────────────────────────────────────
    property var cart: ({})          // id -> true
    property int cartCount: 0

    // ── install run state ──────────────────────────────────────────────────────
    // installState[id] = { pct: 0..100, state: "queued"|"installing"|"done"|"opened"|"fail" }
    property var installState: ({})
    property bool installing: false
    property var queue: []
    property int queueIdx: 0

    // Where moos-open drops per-app status files (from the launcher's --cache=).
    readonly property string cacheDir: win.argValue("--cache=")

    function argValue(prefix) {
        var a = Qt.application.arguments
        for (var i = 0; i < a.length; i++)
            if (a[i].indexOf(prefix) === 0) return a[i].substring(prefix.length)
        return ""
    }

    // ── helpers ────────────────────────────────────────────────────────────────
    function catName(id) {
        if (id === "all") return win.rtl ? "الكل" : "All"
        for (var i = 0; i < win.cats.length; i++)
            if (win.cats[i].id === id) return win.rtl ? win.cats[i].ar : win.cats[i].en
        return id
    }

    function inCart(id) { return win.cart[id] === true }

    function toggleCart(id) {
        var c = Object.assign({}, win.cart)
        if (c[id]) delete c[id]; else c[id] = true
        win.cart = c
        win.cartCount = Object.keys(c).length
    }

    function addMany(ids) {
        var c = Object.assign({}, win.cart)
        for (var i = 0; i < ids.length; i++) c[ids[i]] = true
        win.cart = c
        win.cartCount = Object.keys(c).length
        win.flash((win.rtl ? "أُضيفت للمختار — " : "Added — ") + ids.length)
    }

    function clearCart() { win.cart = ({}); win.cartCount = 0 }

    function recompute() {
        var q = win.query.trim().toLowerCase()
        var out = []
        for (var i = 0; i < win.apps.length; i++) {
            var a = win.apps[i]
            if (win.activeCat !== "all" && a.cat !== win.activeCat) continue
            if (q !== "") {
                var hay = (a.en + " " + a.ar + " " + (a.desc_en || "") + " "
                           + (a.desc_ar || "") + " " + a.id).toLowerCase()
                if (hay.indexOf(q) < 0) continue
            }
            out.push(a)
        }
        win.filtered = out
    }

    function popularApps() {
        var out = []
        for (var i = 0; i < win.apps.length; i++)
            if (win.apps[i].popular) out.push(win.apps[i])
        return out
    }

    function preselectApps() {
        var out = []
        for (var i = 0; i < win.apps.length; i++)
            if (win.apps[i].preselect) out.push(win.apps[i])
        return out
    }

    function appById(id) {
        for (var i = 0; i < win.apps.length; i++)
            if (win.apps[i].id === id) return win.apps[i]
        return null
    }

    function flash(msg) { toastLabel.text = msg; toast.open(); toastTimer.restart() }

    onActiveCatChanged: recompute()
    onQueryChanged: recompute()

    // ── colour → #rrggbb (+ separate opacity). Qt's SVG-Tiny renderer supports
    //    hex and stroke-opacity, but NOT the CSS rgba() function — so use hex. ──
    function hex2(n) {
        var s = Math.round(Math.max(0, Math.min(1, n)) * 255).toString(16)
        return s.length < 2 ? "0" + s : s
    }
    function hexColor(c) { return "#" + hex2(c.r) + hex2(c.g) + hex2(c.b) }

    // ── line-glyph library (24×24, stroke-only, round joins) ───────────────────
    // A curated custom icon set so the store never falls back to generic symbols.
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
        "video":    "<rect x='3' y='6' width='13' height='12' rx='2.5'/><path d='M16 10.5l5-3v9l-5-3z'/>"
    })

    function glyphURL(name, c, w) {
        var inner = win.glyphs[name] || win.glyphs["spark"]
        var svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
                + "stroke='" + win.hexColor(c) + "' stroke-opacity='" + c.a.toFixed(3) + "' "
                + "stroke-width='" + w + "' stroke-linecap='round' stroke-linejoin='round'>"
                + inner + "</svg>"
        return "data:image/svg+xml;base64," + Qt.btoa(svg)
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
            // preselect the recommended set into the cart on first run.
            var c = {}
            for (var i = 0; i < win.apps.length; i++)
                if (win.apps[i].preselect) c[win.apps[i].id] = true
            win.cart = c
            win.cartCount = Object.keys(c).length
            win.loaded = true
            win.recompute()
        } catch (e) {
            win.loadError = "" + e
            win.loaded = false
        }
    }

    // ── install engine ─────────────────────────────────────────────────────────
    function setState(id, pct, state) {
        var s = Object.assign({}, win.installState)
        s[id] = { pct: pct, state: state }
        win.installState = s
    }

    function startInstall() {
        var ids = Object.keys(win.cart)
        if (ids.length === 0) return
        // Split: web apps just open a page; keep them last so the bars finish clean.
        win.queue = ids
        win.queueIdx = 0
        win.installing = true
        var s = {}
        for (var i = 0; i < ids.length; i++) s[ids[i]] = { pct: 0, state: "queued" }
        win.installState = s
        installSheet.open()
        win.installNext()
    }

    function installNext() {
        if (win.queueIdx >= win.queue.length) {
            win.installing = false
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
                // Status file absent/empty. Bounded: if nothing appears after
                // ~27s the moos:// dispatch itself failed — mark this app
                // failed and let the queue move on instead of spinning forever.
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

    // ═══════════════════════════════ BACKGROUND ═══════════════════════════════
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: win.canvas }
            GradientStop { position: 1.0; color: win.chrome }
        }
    }
    Rectangle {   // ambient turquoise glow, trailing-top
        width: 520; height: 520; radius: 260
        anchors.right: parent.right; anchors.top: parent.top
        anchors.rightMargin: -180; anchors.topMargin: -200
        color: win.accent; opacity: 0.10
    }
    Rectangle {   // ambient blue glow, leading-bottom
        width: 420; height: 420; radius: 210
        anchors.left: parent.left; anchors.bottom: parent.bottom
        anchors.leftMargin: -160; anchors.bottomMargin: -180
        color: win.blue; opacity: 0.07
    }

    // ═══════════════════════════════ ROOT ═════════════════════════════════════
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        LayoutMirroring.enabled: win.rtl
        LayoutMirroring.childrenInherit: true

        // ───────────────────────────── HEADER ─────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 78
            color: Qt.rgba(win.chrome.r, win.chrome.g, win.chrome.b, 0.55)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 26; anchors.rightMargin: 26
                spacing: 16

                Image {
                    source: "file:///usr/share/moos/moos-logo.png"
                    sourceSize.width: 40; sourceSize.height: 40
                    Layout.preferredWidth: 40; Layout.preferredHeight: 40
                }
                ColumnLayout {
                    spacing: 0
                    Text {
                        text: win.rtl ? "متجر MoOS" : "Mo Store"
                        color: win.txt; font.family: "IBM Plex Sans"
                        font.pixelSize: 20; font.bold: true
                    }
                    Text {
                        text: win.rtl ? "اختر تطبيقاتك — وثبّتها بنقرة، بلا طرفية"
                                      : "Pick your apps — one tap, no terminal"
                        color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 12
                    }
                }

                Item { Layout.fillWidth: true }

                // search field (also the command palette's twin)
                Rectangle {
                    Layout.preferredWidth: Math.min(340, win.width * 0.34)
                    Layout.preferredHeight: 42
                    radius: 21
                    color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.85)
                    border.width: searchField.activeFocus ? 1.5 : 1
                    border.color: searchField.activeFocus ? win.accent : win.outline
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14; anchors.rightMargin: 12
                        spacing: 8
                        Glyph { name: "compass"; tint: win.txt2; stroke: 1.6
                            Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
                        TextField {
                            id: searchField
                            Layout.fillWidth: true
                            background: null
                            color: win.txt
                            placeholderText: win.rtl ? "ابحث عن تطبيق…" : "Search apps…"
                            placeholderTextColor: win.txt2
                            font.family: "IBM Plex Sans"; font.pixelSize: 14
                            selectByMouse: true
                            onTextChanged: win.query = text
                            Keys.onEscapePressed: { text = "" }
                        }
                        Text {
                            // Real Plasma binding (Ctrl+K), not the macOS ⌘ glyph — no PC
                            // keyboard has a Command key, and this OS is not macOS.
                            visible: searchField.text === ""
                            text: "Ctrl K"
                            color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 11
                        }
                    }
                }

                // Browse the full Flathub catalog (search everything, update,
                // remove) via the Bazaar engine — installed on demand and kept out
                // of the app menu, so Mo Store stays the one visible store.
                Rectangle {
                    Layout.preferredHeight: 42
                    implicitWidth: browseRow.implicitWidth + 30
                    radius: 21
                    color: browseTap.pressed ? Qt.darker(win.surface, 1.1)
                         : browseHover.hovered ? Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.95)
                                               : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.75)
                    border.width: 1
                    border.color: browseHover.hovered ? win.accent : win.outline
                    Behavior on border.color { ColorAnimation { duration: 120 } }
                    HoverHandler { id: browseHover }
                    TapHandler { id: browseTap; onTapped: Qt.openUrlExternally("moos://store/browse-all") }
                    RowLayout {
                        id: browseRow
                        anchors.centerIn: parent; spacing: 8
                        Glyph { name: "compass"; tint: win.txt; stroke: 1.6
                            Layout.preferredWidth: 16; Layout.preferredHeight: 16 }
                        Text {
                            text: win.rtl ? "تصفّح الكل" : "Browse all"
                            color: win.txt; font.family: "IBM Plex Sans"
                            font.pixelSize: 13; font.bold: true
                        }
                    }
                }
            }

            Rectangle {   // hairline
                anchors.bottom: parent.bottom; width: parent.width; height: 1
                color: Qt.rgba(win.outline.r, win.outline.g, win.outline.b, 0.6)
            }
        }

        // ─────────────────────────── CATEGORY PILLS ───────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 60
            color: "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 24; anchors.rightMargin: 24
                spacing: 10

                Repeater {
                    model: {
                        var m = [{ id: "all", glyph: "spark" }]
                        for (var i = 0; i < win.cats.length; i++)
                            m.push({ id: win.cats[i].id, glyph: win.cats[i].glyph })
                        return m
                    }
                    delegate: Rectangle {
                        id: pill
                        required property var modelData
                        readonly property bool isOn: win.activeCat === pill.modelData.id
                        Layout.preferredHeight: 38
                        implicitWidth: pillRow.implicitWidth + 30
                        radius: 19
                        color: pill.isOn ? win.accent
                              : pillHover.hovered ? Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.9)
                              : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.55)
                        border.width: 1
                        border.color: pill.isOn ? win.accent : win.outline
                        Behavior on color { ColorAnimation { duration: 130 } }

                        HoverHandler { id: pillHover }
                        TapHandler { onTapped: win.activeCat = pill.modelData.id }

                        RowLayout {
                            id: pillRow
                            anchors.centerIn: parent
                            spacing: 8
                            Glyph {
                                name: pill.modelData.glyph
                                tint: pill.isOn ? win.onAccent : win.txt
                                stroke: 1.7
                                Layout.preferredWidth: 17; Layout.preferredHeight: 17
                            }
                            Text {
                                text: win.catName(pill.modelData.id)
                                color: pill.isOn ? win.onAccent : win.txt
                                font.family: "IBM Plex Sans"
                                font.pixelSize: 14
                                font.bold: pill.isOn
                            }
                        }
                    }
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: win.filtered.length + (win.rtl ? " تطبيق" : " apps")
                    color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 13
                }
            }
        }

        // ─────────────────────────────── BODY ─────────────────────────────────
        Flickable {
            id: flick
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: body.implicitHeight + 130
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            ColumnLayout {
                id: body
                x: 24
                width: flick.width - 48
                spacing: 22
                LayoutMirroring.enabled: win.rtl
                LayoutMirroring.childrenInherit: true

                Item { Layout.preferredHeight: 2 }

                // ── QUICK START (recommended essentials) ───────────────────────
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 132
                    visible: win.activeCat === "all" && win.query === "" && win.loaded
                    radius: 20
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16) }
                        GradientStop { position: 1.0; color: Qt.rgba(win.blue.r, win.blue.g, win.blue.b, 0.06) }
                    }
                    border.width: 1
                    border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.35)

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 18

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Text {
                                text: win.rtl ? "بداية سريعة" : "Quick start"
                                color: win.txt; font.family: "IBM Plex Sans"
                                font.pixelSize: 18; font.bold: true
                            }
                            Text {
                                text: win.rtl ? "الأساسيات الموصى بها لنظامك — مختارة مسبقاً وجاهزة للتثبيت."
                                              : "The essentials we recommend — pre-selected and ready."
                                color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 13
                                wrapMode: Text.WordWrap; Layout.fillWidth: true
                            }
                            RowLayout {
                                spacing: 8
                                Repeater {
                                    model: win.preselectApps()
                                    delegate: Rectangle {
                                        id: chip
                                        required property var modelData
                                        Layout.preferredHeight: 26
                                        implicitWidth: chipRow.implicitWidth + 18
                                        radius: 13
                                        color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.9)
                                        border.width: 1; border.color: win.outline
                                        RowLayout {
                                            id: chipRow
                                            anchors.centerIn: parent; spacing: 5
                                            Glyph { name: chip.modelData.glyph; tint: win.accent; stroke: 1.7
                                                Layout.preferredWidth: 13; Layout.preferredHeight: 13 }
                                            Text {
                                                text: win.rtl ? chip.modelData.ar : chip.modelData.en
                                                color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 12
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        PrimaryButton {
                            label: win.rtl ? "أضِف الموصى به" : "Add recommended"
                            glyphName: "spark"
                            action: function() {
                                var ids = []
                                var p = win.preselectApps()
                                for (var i = 0; i < p.length; i++) ids.push(p[i].id)
                                win.addMany(ids)
                            }
                        }
                    }
                }

                // ── BUNDLES ────────────────────────────────────────────────────
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    visible: win.activeCat === "all" && win.query === "" && win.bundles.length > 0

                    Text {
                        text: win.rtl ? "حزم جاهزة" : "Curated bundles"
                        color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 16; font.bold: true
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 14
                        Repeater {
                            model: win.bundles
                            delegate: Rectangle {
                                id: bundle
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredHeight: 128
                                radius: 18
                                color: bundleHover.hovered
                                     ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.95)
                                     : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.8)
                                border.width: 1.5
                                border.color: bundleHover.hovered ? win.accent : win.outline
                                scale: bundleHover.hovered ? 1.015 : 1.0
                                Behavior on color { ColorAnimation { duration: 140 } }
                                Behavior on border.color { ColorAnimation { duration: 140 } }
                                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutQuad } }

                                HoverHandler { id: bundleHover }

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 16
                                    spacing: 8
                                    RowLayout {
                                        spacing: 10
                                        Rectangle {
                                            Layout.preferredWidth: 38; Layout.preferredHeight: 38
                                            radius: 11
                                            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                                            Glyph {
                                                anchors.centerIn: parent
                                                width: 22; height: 22
                                                name: bundle.modelData.glyph; tint: win.accent; stroke: 1.8
                                            }
                                        }
                                        ColumnLayout {
                                            spacing: 0
                                            Text {
                                                text: win.rtl ? bundle.modelData.ar : bundle.modelData.en
                                                color: win.txt; font.family: "IBM Plex Sans"
                                                font.pixelSize: 15; font.bold: true
                                            }
                                            Text {
                                                text: bundle.modelData.apps.length + (win.rtl ? " تطبيقات" : " apps")
                                                color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 12
                                            }
                                        }
                                    }
                                    Text {
                                        text: bundle.modelData.desc_ar
                                        color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 12
                                        wrapMode: Text.WordWrap; Layout.fillWidth: true
                                        maximumLineCount: 2; elide: Text.ElideRight
                                        visible: win.rtl
                                    }
                                    Item { Layout.fillHeight: true }
                                    Rectangle {
                                        Layout.preferredHeight: 28
                                        implicitWidth: addAllRow.implicitWidth + 22
                                        radius: 14
                                        color: addAllTap.pressed ? Qt.darker(win.accent, 1.1)
                                             : Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.9)
                                        RowLayout {
                                            id: addAllRow
                                            anchors.centerIn: parent; spacing: 6
                                            Glyph { name: "spark"; tint: win.onAccent; stroke: 1.8
                                                Layout.preferredWidth: 13; Layout.preferredHeight: 13 }
                                            Text {
                                                text: win.rtl ? "أضِف الحزمة" : "Add bundle"
                                                color: win.onAccent; font.family: "IBM Plex Sans"
                                                font.pixelSize: 12; font.bold: true
                                            }
                                        }
                                        TapHandler { id: addAllTap; onTapped: win.addMany(bundle.modelData.apps) }
                                    }
                                }
                            }
                        }
                    }
                }

                // ── SECTION TITLE + "add the whole section" ────────────────────
                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    spacing: 10
                    Text {
                        text: win.query !== "" ? (win.rtl ? "نتائج البحث" : "Search results")
                                               : win.catName(win.activeCat)
                        color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 16; font.bold: true
                    }
                    Text {
                        text: "· " + win.filtered.length
                        color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 13
                        visible: win.loaded && win.filtered.length > 0
                    }
                    Item { Layout.fillWidth: true }
                    // One tap adds every app in THIS section to the cart — the
                    // group-per-section pick. addMany already skips anything already
                    // chosen, so it never double-adds. Hidden while searching (a
                    // search result set is not a section) or with one/zero apps.
                    Rectangle {
                        Layout.preferredHeight: 30
                        implicitWidth: addSecRow.implicitWidth + 24
                        radius: 15
                        visible: win.query === "" && win.filtered.length > 1
                        color: addSecTap.pressed ? Qt.darker(win.accent, 1.1)
                             : addSecHover.hovered ? win.accent
                             : Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                        border.width: 1
                        border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.5)
                        Behavior on color { ColorAnimation { duration: 120 } }
                        HoverHandler { id: addSecHover }
                        RowLayout {
                            id: addSecRow
                            anchors.centerIn: parent; spacing: 6
                            Glyph { name: "spark"
                                tint: (addSecHover.hovered || addSecTap.pressed) ? win.onAccent : win.accent
                                stroke: 1.8; Layout.preferredWidth: 13; Layout.preferredHeight: 13 }
                            Text {
                                text: win.rtl ? "أضِف كل القسم" : "Add all in section"
                                color: (addSecHover.hovered || addSecTap.pressed) ? win.onAccent : win.accent
                                font.family: "IBM Plex Sans"; font.pixelSize: 12; font.bold: true
                            }
                        }
                        TapHandler {
                            id: addSecTap
                            onTapped: {
                                var ids = []
                                for (var i = 0; i < win.filtered.length; i++)
                                    ids.push(win.filtered[i].id)
                                win.addMany(ids)
                            }
                        }
                    }
                }

                // ── APP GRID ───────────────────────────────────────────────────
                GridLayout {
                    Layout.fillWidth: true
                    columns: Math.max(1, Math.floor((flick.width - 48) / 290))
                    rowSpacing: 14; columnSpacing: 14

                    Repeater {
                        model: win.filtered
                        delegate: Rectangle {
                            id: card
                            required property var modelData
                            readonly property bool selected: win.inCart(card.modelData.id)
                            Layout.fillWidth: true
                            Layout.preferredHeight: 158
                            radius: 18
                            color: cardHover.hovered
                                 ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.96)
                                 : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.82)
                            border.width: card.selected ? 2 : 1.5
                            border.color: card.selected ? win.accent
                                        : cardHover.hovered ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.6)
                                        : win.outline
                            scale: cardHover.hovered ? 1.02 : 1.0
                            Behavior on color { ColorAnimation { duration: 140 } }
                            Behavior on border.color { ColorAnimation { duration: 140 } }
                            Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutQuad } }

                            HoverHandler { id: cardHover }

                            // popular ribbon
                            Rectangle {
                                visible: card.modelData.popular === true
                                anchors.top: parent.top; anchors.right: parent.right
                                anchors.topMargin: 12; anchors.rightMargin: 12
                                height: 20; width: popLabel.implicitWidth + 16; radius: 10
                                color: Qt.rgba(win.violet.r, win.violet.g, win.violet.b, 0.18)
                                Text {
                                    id: popLabel; anchors.centerIn: parent
                                    text: win.rtl ? "شائع" : "Popular"
                                    color: win.violet; font.family: "IBM Plex Sans"; font.pixelSize: 11; font.bold: true
                                }
                            }

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 8

                                RowLayout {
                                    spacing: 12
                                    Rectangle {
                                        Layout.preferredWidth: 46; Layout.preferredHeight: 46
                                        radius: 13
                                        color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                                        border.width: 1
                                        border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.3)
                                        Glyph {
                                            anchors.centerIn: parent; width: 26; height: 26
                                            name: card.modelData.glyph; tint: win.accent; stroke: 1.75
                                        }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 1
                                        Text {
                                            text: win.rtl ? card.modelData.ar : card.modelData.en
                                            color: win.txt; font.family: "IBM Plex Sans"
                                            font.pixelSize: 15; font.bold: true
                                            elide: Text.ElideRight; Layout.fillWidth: true
                                        }
                                        Text {
                                            text: win.rtl ? card.modelData.en : card.modelData.ar
                                            color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 12
                                            elide: Text.ElideRight; Layout.fillWidth: true
                                        }
                                        RowLayout {
                                            spacing: 5
                                            // No star-rating / review-count: Flathub exposes no such
                                            // figures, so any number shown here would be invented
                                            // (the owner's rule: nothing fake). Show only the honest
                                            // install-method badge below.
                                            // how it installs — so the method is never a mystery
                                            Rectangle {
                                                Layout.leftMargin: 3
                                                implicitWidth: srcLabel.implicitWidth + 12
                                                implicitHeight: 16; radius: 8
                                                color: Qt.rgba(win.txt2.r, win.txt2.g, win.txt2.b, 0.14)
                                                Text {
                                                    id: srcLabel
                                                    anchors.centerIn: parent
                                                    text: card.modelData.source === "flathub" ? "Flatpak"
                                                        : (card.modelData.install && card.modelData.install.kind === "web")
                                                          ? (win.rtl ? "ويب" : "Web")
                                                          : "MoOS"
                                                    color: win.txt2; font.family: "IBM Plex Sans"
                                                    font.pixelSize: 9; font.bold: true
                                                }
                                            }
                                        }
                                    }
                                }

                                Text {
                                    text: win.rtl ? card.modelData.desc_ar : card.modelData.desc_en
                                    color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 12
                                    wrapMode: Text.WordWrap; Layout.fillWidth: true
                                    maximumLineCount: 2; elide: Text.ElideRight
                                }

                                Item { Layout.fillHeight: true }

                                // select toggle
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 34
                                    radius: 10
                                    color: card.selected ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.9)
                                         : selTap.pressed ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 1.0)
                                         : Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.7)
                                    border.width: 1
                                    border.color: card.selected ? win.accent : win.outline
                                    Behavior on color { ColorAnimation { duration: 120 } }

                                    RowLayout {
                                        anchors.centerIn: parent; spacing: 7
                                        Text {
                                            text: card.selected ? "✓" : "+"
                                            color: card.selected ? win.onAccent : win.txt
                                            font.pixelSize: 14; font.bold: true
                                        }
                                        Text {
                                            text: card.selected ? (win.rtl ? "مُختار" : "Selected")
                                                : card.modelData.source === "moos" && card.modelData.install
                                                  && card.modelData.install.kind === "web"
                                                  ? (win.rtl ? "افتح الصفحة" : "Open page")
                                                  : (win.rtl ? "أضِف" : "Add")
                                            color: card.selected ? win.onAccent : win.txt
                                            font.family: "IBM Plex Sans"; font.pixelSize: 13
                                            font.bold: card.selected
                                        }
                                    }
                                    TapHandler { id: selTap; onTapped: win.toggleCart(card.modelData.id) }
                                }
                            }
                        }
                    }
                }

                // empty state
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 40
                    spacing: 8
                    visible: win.loaded && win.filtered.length === 0
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.rtl ? "لا توجد نتائج" : "No results"
                        color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 16; font.bold: true
                    }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.rtl ? "جرّب كلمة أخرى أو فئة مختلفة." : "Try another word or category."
                        color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 13
                    }
                }

                // load error / loading
                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 40
                    horizontalAlignment: Text.AlignHCenter
                    visible: !win.loaded
                    text: win.loadError !== ""
                          ? (win.rtl ? "تعذّر تحميل الكتالوج" : "Could not load the catalog")
                          : (win.rtl ? "جارٍ التحميل…" : "Loading…")
                    color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 14
                }

                Item { Layout.preferredHeight: 8 }
            }
        }
    }

    // ═══════════════════════════ FLOATING INSTALL BAR ═════════════════════════
    Rectangle {
        id: floatBar
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: win.cartCount > 0 && !installSheet.visible ? 22 : -90
        Behavior on anchors.bottomMargin { NumberAnimation { duration: 240; easing.type: Easing.OutBack } }
        height: 58
        width: Math.min(560, win.width - 48)
        radius: 29
        color: Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.98)
        border.width: 1
        border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.5)
        visible: anchors.bottomMargin > -90

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 20; anchors.rightMargin: 10
            spacing: 12
            LayoutMirroring.enabled: win.rtl
            LayoutMirroring.childrenInherit: true

            Rectangle {
                Layout.preferredWidth: 30; Layout.preferredHeight: 30; radius: 15
                color: win.accent
                Text { anchors.centerIn: parent; text: win.cartCount
                       color: win.onAccent; font.family: "IBM Plex Sans"; font.pixelSize: 14; font.bold: true }
            }
            Text {
                text: win.rtl ? "تطبيقات مختارة" : "selected"
                color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 14
            }
            Item { Layout.fillWidth: true }
            Text {
                text: win.rtl ? "مسح" : "Clear"
                color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 13
                TapHandler { onTapped: win.clearCart() }
            }
            PrimaryButton {
                label: win.rtl ? "ثبّت الآن" : "Install now"
                glyphName: "bolt"
                action: function() { win.startInstall() }
            }
        }
    }

    // ═══════════════════════════════ INSTALL SHEET ════════════════════════════
    Popup {
        id: installSheet
        anchors.centerIn: Overlay.overlay
        width: Math.min(560, win.width - 60)
        height: Math.min(560, win.height - 80)
        modal: true
        closePolicy: win.installing ? Popup.NoAutoClose : Popup.CloseOnEscape
        padding: 0

        background: Rectangle {
            radius: 22
            color: win.surface
            border.width: 1; border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.4)
        }
        enter: Transition {
            NumberAnimation { property: "scale"; from: 0.94; to: 1.0; duration: 180; easing.type: Easing.OutBack }
            NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 140 }
        }
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }

        readonly property bool allDone: {
            if (!win.installing && win.queueIdx >= win.queue.length && win.queue.length > 0) return true
            return false
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14
            LayoutMirroring.enabled: win.rtl
            LayoutMirroring.childrenInherit: true

            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    Layout.preferredWidth: 40; Layout.preferredHeight: 40; radius: 12
                    color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                    Glyph { anchors.centerIn: parent; width: 22; height: 22
                            name: installSheet.allDone ? "spark" : "bolt"; tint: win.accent; stroke: 1.8 }
                }
                ColumnLayout {
                    spacing: 0
                    Text {
                        text: installSheet.allDone ? (win.rtl ? "اكتمل التثبيت" : "All set")
                                                   : (win.rtl ? "جارٍ التثبيت" : "Installing")
                        color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 17; font.bold: true
                    }
                    Text {
                        text: win.rtl ? "يمكنك تثبيت المزيد لاحقاً من متجر MoOS أو عبر Mo AI."
                                      : "Install more later from Mo Store or via Mo AI."
                        color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 12
                        wrapMode: Text.WordWrap; Layout.fillWidth: true
                    }
                }
            }

            ListView {
                Layout.fillWidth: true; Layout.fillHeight: true
                clip: true; spacing: 10
                model: win.queue
                ScrollBar.vertical: ScrollBar {}
                delegate: Item {
                    id: irow
                    required property var modelData
                    width: ListView.view.width
                    height: 58
                    readonly property var st: win.installState[irow.modelData] || { pct: 0, state: "queued" }
                    readonly property var app: win.appById(irow.modelData)

                    RowLayout {
                        anchors.fill: parent
                        spacing: 12
                        LayoutMirroring.enabled: win.rtl
                        LayoutMirroring.childrenInherit: true

                        Rectangle {
                            Layout.preferredWidth: 40; Layout.preferredHeight: 40; radius: 11
                            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.12)
                            Glyph { anchors.centerIn: parent; width: 22; height: 22
                                    name: irow.app ? irow.app.glyph : "spark"
                                    tint: win.accent; stroke: 1.75 }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 5
                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: irow.app ? (win.rtl ? irow.app.ar : irow.app.en) : irow.modelData
                                    color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 14; font.bold: true
                                }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: irow.st.state === "done" ? (win.rtl ? "تم ✓" : "Done ✓")
                                        : irow.st.state === "opened" ? (win.rtl ? "فُتحت الصفحة" : "Opened")
                                        : irow.st.state === "fail" ? (win.rtl ? "فشل" : "Failed")
                                        : irow.st.state === "queued" ? (win.rtl ? "بالانتظار" : "Queued")
                                        : (Math.max(0, irow.st.pct) + "%")
                                    color: irow.st.state === "fail" ? win.violet
                                         : irow.st.state === "done" || irow.st.state === "opened" ? win.accent : win.txt2
                                    font.family: "IBM Plex Sans"; font.pixelSize: 12
                                }
                            }
                            // progress track
                            Rectangle {
                                Layout.fillWidth: true
                                height: 6; radius: 3
                                color: Qt.rgba(win.outline.r, win.outline.g, win.outline.b, 0.5)
                                Rectangle {
                                    height: parent.height; radius: 3
                                    width: parent.width * Math.max(0, Math.min(100, irow.st.pct)) / 100
                                    color: irow.st.state === "fail" ? win.violet : win.accent
                                    Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
                                }
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Rectangle {
                    Layout.preferredHeight: 42
                    implicitWidth: doneRow.implicitWidth + 40
                    radius: 12
                    opacity: win.installing ? 0.5 : 1.0
                    color: installSheet.allDone ? win.accent : win.raised
                    border.width: 1; border.color: installSheet.allDone ? win.accent : win.outline
                    RowLayout {
                        id: doneRow
                        anchors.centerIn: parent; spacing: 7
                        Text {
                            text: win.installing ? (win.rtl ? "جارٍ العمل…" : "Working…")
                                                 : (win.rtl ? "تم" : "Done")
                            color: installSheet.allDone ? win.onAccent : win.txt
                            font.family: "IBM Plex Sans"; font.pixelSize: 14; font.bold: true
                        }
                    }
                    TapHandler { enabled: !win.installing; onTapped: installSheet.close() }
                }
            }
        }
    }

    // ═══════════════════════════ COMMAND PALETTE (⌘K) ═════════════════════════
    Shortcut { sequences: ["Ctrl+K", "Ctrl+F"]; onActivated: palette.open() }

    Popup {
        id: palette
        anchors.centerIn: Overlay.overlay
        width: Math.min(600, win.width - 80)
        height: Math.min(460, win.height - 120)
        modal: true
        padding: 0
        onOpened: paletteField.forceActiveFocus()
        onClosed: paletteField.text = ""

        background: Rectangle {
            radius: 18; color: win.surface
            border.width: 1; border.color: win.accent
        }
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.45) }
        enter: Transition {
            NumberAnimation { property: "scale"; from: 0.96; to: 1.0; duration: 150; easing.type: Easing.OutQuad }
            NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 120 }
        }

        function matches() {
            var q = paletteField.text.trim().toLowerCase()
            var out = []
            for (var i = 0; i < win.apps.length; i++) {
                var a = win.apps[i]
                if (q === "") { out.push(a); if (out.length >= 40) break; continue }
                var hay = (a.en + " " + a.ar + " " + a.id).toLowerCase()
                if (hay.indexOf(q) >= 0) out.push(a)
            }
            return out
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12
            LayoutMirroring.enabled: win.rtl
            LayoutMirroring.childrenInherit: true

            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 44
                radius: 12; color: Qt.rgba(win.canvas.r, win.canvas.g, win.canvas.b, 0.6)
                border.width: 1; border.color: win.outline
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 12; spacing: 8
                    Glyph { name: "compass"; tint: win.accent; stroke: 1.7
                            Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
                    TextField {
                        id: paletteField
                        Layout.fillWidth: true
                        background: null; color: win.txt
                        placeholderText: win.rtl ? "اكتب اسم تطبيق ثم اضغط Enter لإضافته…"
                                                 : "Type an app, Enter to add…"
                        placeholderTextColor: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 15
                        selectByMouse: true
                        Keys.onReturnPressed: {
                            var m = palette.matches()
                            if (m.length > 0) { win.toggleCart(m[0].id); palette.close() }
                        }
                        Keys.onEscapePressed: palette.close()
                    }
                }
            }

            ListView {
                Layout.fillWidth: true; Layout.fillHeight: true
                clip: true; spacing: 4
                model: palette.matches()
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    id: prow
                    required property var modelData
                    width: ListView.view.width
                    height: 52
                    radius: 10
                    color: rowHover.hovered ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.12) : "transparent"
                    HoverHandler { id: rowHover }
                    TapHandler { onTapped: { win.toggleCart(prow.modelData.id); palette.close() } }
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 12; spacing: 12
                        LayoutMirroring.enabled: win.rtl
                        LayoutMirroring.childrenInherit: true
                        Rectangle {
                            Layout.preferredWidth: 34; Layout.preferredHeight: 34; radius: 9
                            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                            Glyph { anchors.centerIn: parent; width: 19; height: 19
                                    name: prow.modelData.glyph; tint: win.accent; stroke: 1.75 }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 0
                            Text {
                                text: win.rtl ? prow.modelData.ar : prow.modelData.en
                                color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 14; font.bold: true
                            }
                            Text {
                                text: win.rtl ? prow.modelData.desc_ar : prow.modelData.desc_en
                                color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 12
                                elide: Text.ElideRight; Layout.fillWidth: true
                            }
                        }
                        Text {
                            text: win.inCart(prow.modelData.id) ? "✓" : "+"
                            color: win.inCart(prow.modelData.id) ? win.accent : win.txt2
                            font.pixelSize: 16; font.bold: true
                        }
                    }
                }
            }
        }
    }

    // ═══════════════════════════════ PRIMARY BUTTON ═══════════════════════════
    component PrimaryButton: Rectangle {
        id: pb
        property string label: ""
        property string glyphName: ""
        property var action
        implicitWidth: pbRow.implicitWidth + 34
        implicitHeight: 42
        radius: 21
        color: pbTap.pressed ? Qt.darker(win.accent, 1.12)
             : pbHover.hovered ? Qt.lighter(win.accent, 1.08) : win.accent
        Behavior on color { ColorAnimation { duration: 120 } }
        HoverHandler { id: pbHover }
        TapHandler { id: pbTap; onTapped: if (pb.action) pb.action() }
        RowLayout {
            id: pbRow
            anchors.centerIn: parent; spacing: 8
            Glyph {
                visible: pb.glyphName !== ""
                name: pb.glyphName; tint: win.onAccent; stroke: 1.9
                Layout.preferredWidth: 16; Layout.preferredHeight: 16
            }
            Text {
                text: pb.label; color: win.onAccent
                font.family: "IBM Plex Sans"; font.pixelSize: 14; font.bold: true
            }
        }
    }

    // ═══════════════════════════════════ TOAST ════════════════════════════════
    Popup {
        id: toast
        y: win.height - 96
        x: (win.width - width) / 2
        width: toastLabel.implicitWidth + 36; height: 42
        padding: 0; modal: false; closePolicy: Popup.NoAutoClose
        background: Rectangle {
            radius: 21; color: win.raised
            border.width: 1; border.color: win.accent
        }
        Text { id: toastLabel; anchors.centerIn: parent; text: "MoOS"
               color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 13 }
        Timer { id: toastTimer; interval: 1800; onTriggered: toast.close() }
    }
}
