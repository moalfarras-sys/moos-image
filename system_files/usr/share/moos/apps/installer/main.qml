// MoOS Setup — the live-USB installer, in the language of the Welcome wizard.
// Pure-QML (launched by /usr/bin/moos-installer via moos-qml-shell). This is the
// FRONT of one unified MoOS journey: Setup writes MoOS to a disk here on the USB;
// the existing Welcome wizard (apps/welcome) then personalises look/direction/apps
// on the installed system's FIRST boot. Setup deliberately does NOT re-ask those.
//
// EIGHT STEPS
//   0 welcome   language pick (applies to the live session + the install default).
//   1 sell      one honest screen: what MoOS actually is. No hype.
//   2 disk      a card per eligible internal disk (name/model/size/data). The USB
//               you booted from is shown as a PROTECTED, non-selectable row.
//   3 method    "Erase & install" — the single, honest MoOS install path.
//   4 account   username + required password; auto sign-in is an explicit choice.
//   5 confirm   the point of no return — a press-and-HOLD control, never a click.
//   6 progress  one long job, human PHASES, honest stepped progress. No logs.
//   7 success   remove USB → restart → first boot continues into Welcome.
//
// BACKEND CONTRACT (pure QML can't touch disks — the launcher/helper do):
//   --disks=<path>       JSON the launcher wrote: { liveNode, disks:[…] } (see loadDisks)
//   --cache=<dir>        where the privileged helper streams the install status file
//   moos://installer/probe       re-run disk detection (rewrites the --disks file)
//   moos://installer/begin      pkexec → /usr/bin/moos-install-to-disk (the target
//                               disk + account come from recipe.json, NOT the URL)
//                               which appends PHASE/PROGRESS/DONE/FAIL to
//                               <cache>/moos-installer/install.status (the store idiom)
//   moos://installer/reboot | poweroff
//
// Bilingual, Arabic-first, RTL-safe. Structural colour comes from the KDE palette
// so the live session's Graphite/Tidal recolours the installer too.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: win
    visible: true
    width: Math.min(1080, Screen.desktopAvailableWidth * 0.92)
    height: Math.min(760, Screen.desktopAvailableHeight * 0.92)
    minimumWidth: Math.min(860, Screen.desktopAvailableWidth * 0.92)
    minimumHeight: Math.min(600, Screen.desktopAvailableHeight * 0.92)
    title: qsTr("Install MoOS")
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
    readonly property color accent: win.cyan.a > 0 ? win.cyan : win.blue

    // Destructive intent is NOT the same as an install failure (violet). Erasing a
    // disk deserves its own unmistakable warm-red, distinct from cyan "safe".
    readonly property color danger:     "#F0616D"
    readonly property color dangerSoft: Qt.rgba(0.941, 0.380, 0.427, 0.14)
    readonly property color amber:      "#F5B24A"

    // ── language (chosen on the hero, applied to the whole live session) ───────
    property string lang: Qt.application.layoutDirection === Qt.RightToLeft ? "ar" : "en"
    readonly property bool rtl: win.lang === "ar"
    function tr(ar, en) { return win.rtl ? ar : en }

    function chooseLang(which) {
        if (win.lang === which) return
        win.lang = which
        Qt.openUrlExternally("moos://lang/" + which)
    }

    // ── wizard state ───────────────────────────────────────────────────────────
    property int step: 0
    // NAMED, not numbered. These indices are the StackLayout's child order, the progress
    // dots' model, and every jump in this file — a page inserted in the middle used to mean
    // hunting bare 5/6/7s through 1900 lines and hoping. That is the trap this project keeps
    // paying for: a constant goes stale and nothing says so. Insert a page HERE and in the
    // StackLayout, and the rest follows. stepCount is gated against the real child count.
    readonly property int stepWelcome:  0
    readonly property int stepSell:     1
    readonly property int stepDisk:     2
    readonly property int stepMethod:   3
    readonly property int stepAccount:  4
    readonly property int stepZone:     5
    readonly property int stepConfirm:  6
    readonly property int stepProgress: 7
    readonly property int stepSuccess:  8
    readonly property int stepCount: 9
    // Footer Back/Next lives on the reversible choice pages (disk, method, account, zone).
    // Confirm has its own inline back + hold-commit; progress/success are committed.
    readonly property bool navPages: win.step === win.stepDisk || win.step === win.stepMethod
                                     || win.step === win.stepAccount || win.step === win.stepZone

    // ── account (step 4). Applied on the target's FIRST boot by moos-firstboot
    // from the recipe the secure bridge writes — bootc install itself makes no
    // user. A password is always required; automatic sign-in is independent and
    // never grants passwordless administration. Keyboard/locale/timezone are derived
    // from the chosen language (Apple-style zero-click) and applied too. ─────────
    property string acctUser: "moos"
    property string acctFull: ""
    property bool   acctAutologin: false
    property string acctPass: ""
    property string acctPass2: ""
    // The CONSOLE keymap (/etc/vconsole.conf). It describes the same physical keyboard the
    // graphical layout describes, so DERIVE it from xkbForLang's primary entry — naming the
    // layout twice is what broke it. When the default became de,ara (the owner's hardware is
    // German) this line was left behind returning a literal "us", so every install since has
    // typed German on the desktop and US in the text console: 'y' and 'z' swapped exactly
    // where you land when the desktop does not start, and exactly where a wrong character in
    // a password is least affordable. vconsole takes ONE keymap and moos-firstboot rejects a
    // comma, so the primary layout is all there is to send. xkb layout codes and console
    // keymap names coincide for what MoOS ships (de, us, both in `localectl list-keymaps`);
    // a layout whose console keymap has a different name would need a mapping here.
    function keymapForLang() { return win.xkbForLang().split(",")[0] }
    function xkbForLang()    { return win.lang === "ar" ? "de,ara" : "de" }
    function localeForLang() { return win.lang === "ar" ? "ar_SA.UTF-8" : "en_US.UTF-8" }
    // A GUESS, and only the zone step's starting selection — never the answer on its own.
    // Language is not location: this project's own owner is an Arabic speaker in Germany, so
    // BOTH branches were wrong for him — Arabic handed him Asia/Riyadh (+2h off) and English
    // handed him UTC (a placeholder nobody lives in). The clock was two hours wrong on the
    // panel and nothing in the install ever asked. Hence stepZone: derive a guess, then let
    // the human correct it, because only the human knows where they are.
    function tzForLang()     { return win.lang === "ar" ? "Asia/Riyadh" : "Europe/Berlin" }

    // ── timezone (step 5) ──────────────────────────────────────────────────────
    // Read straight from tzdata's own zone1970.tab — the list the system already ships, so
    // the picker cannot drift from what /usr/share/zoneinfo actually has (a hand-kept list
    // would). The launcher exports QML_XHR_ALLOW_FILE_READ=1 for exactly this kind of local
    // read, which is how the disk JSON arrives too. Best-effort: if the file cannot be read
    // the step falls back to the guess and still installs — a missing list must never be a
    // dead end.
    property var    zones: []
    property string tz: ""
    property string zoneFilter: ""
    readonly property string zoneTabPath: "/usr/share/zoneinfo/zone1970.tab"

    function loadZones() {
        var out = []
        try {
            var req = new XMLHttpRequest()
            req.open("GET", "file://" + win.zoneTabPath, false)
            req.send()
            var lines = req.responseText.split("\n")
            for (var i = 0; i < lines.length; i++) {
                var l = lines[i]
                if (l === "" || l.charAt(0) === "#") continue
                // codes \t coordinates \t TZ \t comments
                var f = l.split("\t")
                if (f.length < 3) continue
                var name = f[2].trim()
                if (name !== "") out.push(name)
            }
        } catch (e) { out = [] }
        out.sort()
        win.zones = out
        if (win.tz === "") win.tz = win.tzForLang()
    }

    // Matches on the whole zone name, so "berlin", "europe" and "Europe/Ber" all find it.
    function zonesFiltered() {
        var q = win.zoneFilter.trim().toLowerCase()
        if (win.zones.length === 0) return win.tz === "" ? [] : [win.tz]
        if (q === "") return win.zones
        var out = []
        for (var i = 0; i < win.zones.length; i++)
            if (win.zones[i].toLowerCase().indexOf(q) !== -1) out.push(win.zones[i])
        return out
    }
    function zoneLabel(z) { return z.replace(/_/g, " ").replace("/", " › ") }
    readonly property bool acctUserValid: /^[a-z_][a-z0-9_-]{0,31}$/.test(win.acctUser)
    readonly property bool acctValid: win.acctUserValid
        && win.acctPass.length >= 8 && win.acctPass === win.acctPass2

    function goNext() { if (win.step < win.stepCount - 1) win.step++ }
    function goBack() { if (win.step > 0) win.step-- }

    // ── disks (filled by the launcher's JSON; re-read on rescan) ───────────────
    // disk = { node, name, model, sizeBytes, sizeH, removable, isLive, tooSmall,
    //          hasOS, osName, hasData }
    property var disks: []
    property string liveNode: ""
    property bool probing: true
    property string probeError: ""
    property string targetNode: ""
    property string method: "erase"     // the single MoOS install method (Erase & install)

    readonly property string disksPath: win.argValue("--disks=")
    readonly property string cacheDir:  win.argValue("--cache=")

    function argValue(prefix) {
        var a = Qt.application.arguments
        for (var i = 0; i < a.length; i++)
            if (a[i].indexOf(prefix) === 0) return a[i].substring(prefix.length)
        return ""
    }

    function targetDisk() {
        for (var i = 0; i < win.disks.length; i++)
            if (win.disks[i].node === win.targetNode) return win.disks[i]
        return null
    }
    function eligibleDisks() {
        var out = []
        for (var i = 0; i < win.disks.length; i++)
            if (!win.disks[i].isLive) out.push(win.disks[i])
        return out
    }
    function liveDisk() {
        for (var i = 0; i < win.disks.length; i++)
            if (win.disks[i].isLive) return win.disks[i]
        return null
    }

    function loadDisks() {
        win.probeError = ""
        try {
            if (win.disksPath === "") { win.probing = false; win.probeError = "no-path"; return }
            var req = new XMLHttpRequest()
            req.open("GET", "file://" + win.disksPath, false)
            req.send()
            var doc = JSON.parse(req.responseText)
            win.liveNode = doc.liveNode || ""
            win.disks = doc.disks || []
            win.probing = false
            // A disk that vanished between probes must not stay selected.
            if (win.targetNode !== "" && !win.targetDisk()) win.targetNode = ""
        } catch (e) {
            win.probing = false
            win.probeError = "" + e
        }
    }

    // Rescan: ask the helper to rewrite the JSON, then re-read after a beat.
    function rescanDisks() {
        rescanTimer.prevCount = win.eligibleDisks().length
        win.probing = true
        Qt.openUrlExternally("moos://installer/probe")
        rescanTimer.tries = 0
        rescanTimer.restart()
    }
    Timer {
        id: rescanTimer
        interval: 600; repeat: true
        property int tries: 0
        property int prevCount: -1
        onTriggered: {
            rescanTimer.tries++
            win.loadDisks()   // refreshes win.disks and (always) clears win.probing
            // loadDisks always clears `probing`, so the retry must be driven off the
            // disk COUNT changing — keep polling (spinner up) until the helper's
            // rewrite lands or the ~3.6s budget runs out.
            if (win.eligibleDisks().length !== rescanTimer.prevCount || rescanTimer.tries >= 6) {
                rescanTimer.stop()
            } else {
                win.probing = true
            }
        }
    }

    // ── install engine (step 5) — the store status-file idiom, one long job ────
    property int instPct: 0
    property string instState: "idle"   // idle | running | done | fail
    property string instPhase: ""        // partition|format|copy|bootloader|finalize
    property string failReason: ""

    function phaseLabel(code) {
        switch (code) {
        case "partition": return win.tr("نجهّز القرص", "Preparing the disk")
        case "format":    return win.tr("نهيّئ النظام", "Formatting")
        case "copy":      return win.tr("ننسخ MoOS", "Copying MoOS")
        case "bootloader":return win.tr("نجعله قابلاً للإقلاع", "Making it bootable")
        case "finalize":  return win.tr("نُنهي اللمسات الأخيرة", "Final touches")
        default:          return win.tr("نُجهّز…", "Working…")
        }
    }
    function failText(code) {
        switch (code) {
        case "disk-io":  return win.tr("تعذّر الكتابة على القرص — قد يكون تالفاً أو غير متصل جيداً.",
                                       "Couldn't write to the disk — it may be faulty or loosely connected.")
        case "no-space": return win.tr("مساحة القرص غير كافية.", "The disk doesn't have enough space.")
        case "verify":   return win.tr("تحقّقنا من النسخ فوجدنا اختلافاً — أوقفنا حفاظاً على سلامتك.",
                                       "We verified the copy and found a mismatch — we stopped to keep you safe.")
        case "live-node":return win.tr("رفضنا الكتابة على قرص الإقلاع نفسه — اختر قرصاً آخر.",
                                       "We refused to write to the boot drive itself — pick another disk.")
        case "no-network":return win.tr("تعذّر الوصول للإنترنت لجلب MoOS. اتصل بشبكة (أيقونة الشبكة في الشريط) ثم أعد المحاولة.",
                                       "Couldn't reach the internet to fetch MoOS. Connect to a network (the network icon in the panel), then retry.")
        case "no-image": return win.tr("صورة MoOS غير متوفّرة محلّياً ولا شبكة لجلبها.",
                                       "The MoOS image isn't available locally and there's no network to fetch it.")
        case "password-required":
            return win.tr("أنشئ كلمة سر من 8 محارف على الأقل قبل بدء التثبيت.",
                          "Create a password with at least 8 characters before installing.")
        case "hash-failed":
            return win.tr("تعذّر تأمين كلمة السر. لم نبدأ التثبيت حفاظاً على حسابك.",
                          "Couldn't secure the password. Installation did not start, to protect your account.")
        case "seed-failed":
            return win.tr("نُسخ النظام، لكن تعذّر حفظ الحساب بأمان. أوقفنا العملية كي لا نترك نظاماً غير قابل للدخول.",
                          "The system was copied, but the account could not be saved safely. We stopped instead of leaving an unusable install.")
        case "stalled":  return win.tr("توقّف التثبيت عن الاستجابة.", "The installation stopped responding.")
        default:         return win.tr("حدث خطأ غير متوقّع أثناء التثبيت.", "Something unexpected happened during installation.")
        }
    }

    function startInstall() {
        if (win.targetNode === "" || win.targetNode === win.liveNode) return
        // Hand the answers to the privileged helper via the SECURE bridge (writes a
        // 0600 file), synchronously — the password must NEVER hit a moos:// URL.
        var recipe = {
            node:      win.targetNode,       // the helper takes the target from HERE, not the URL
            username:  win.acctUser,
            fullname:  win.acctFull,
            password:  win.acctPass,
            autologin: win.acctAutologin ? 1 : 0,
            keymap:    win.keymapForLang(),
            xkblayout: win.xkbForLang(),
            locale:    win.localeForLang(),
            timezone:  win.tz !== "" ? win.tz : win.tzForLang()
        }
        // The bridge write is synchronous, so the recipe is on disk before we fire
        // the begin route. If the bridge is unavailable we do NOT start — the helper
        // would have no target (no node in the URL, by design).
        if (typeof MoosInstaller === "undefined" || !MoosInstaller.writeRecipe(JSON.stringify(recipe))) {
            win.step = win.stepProgress
            win.instState = "fail"
            win.failReason = "generic"
            return
        }
        win.step = win.stepProgress
        win.instState = "running"
        win.instPct = 0
        win.instPhase = "partition"
        win.failReason = ""
        Qt.openUrlExternally("moos://installer/begin")
        instPoll.miss = 0
        instPoll.polls = 0
        instPoll.restart()
    }

    function readInstall() {
        try {
            var req = new XMLHttpRequest()
            // cacheDir IS ~/.cache/moos-installer (the launcher passes its private dir).
            // Appending another "/moos-installer" here polled a path that never exists,
            // so a SUCCEEDING install reported "FAIL stalled" — found the first time the
            // wizard was driven end-to-end in QEMU (2026-07-16). The status file must be
            // the exact path moos-open hands the pkexec'd helper.
            req.open("GET", "file://" + win.cacheDir + "/install.status", false)
            req.send()
            var t = req.responseText
            if (!t) return { pct: -1, phase: "", state: "running", reason: "" }
            var lines = t.split("\n")
            var pct = -1, phase = "", state = "running", reason = ""
            for (var i = 0; i < lines.length; i++) {
                var ln = lines[i].trim()
                if (ln === "") continue
                if (ln.indexOf("PHASE ") === 0) phase = ln.substring(6).trim()
                else if (ln.indexOf("PROGRESS ") === 0) pct = parseInt(ln.substring(9)) || 0
                else if (ln === "DONE") { state = "done"; pct = 100 }
                else if (ln.indexOf("FAIL") === 0) { state = "fail"; reason = ln.substring(4).trim() }
            }
            return { pct: pct, phase: phase, state: state, reason: reason }
        } catch (e) {
            return { pct: -1, phase: "", state: "running", reason: "" }
        }
    }

    Timer {
        id: instPoll
        interval: 450; repeat: true
        property int miss: 0
        property int polls: 0
        onTriggered: {
            instPoll.polls++
            var s = win.readInstall()
            var terminal = (s.state === "done" || s.state === "fail")
            // Stale-file grace: ignore a terminal verdict in the first beats (it can
            // be a previous run's line before the helper truncates).
            if (terminal && instPoll.polls <= 3) return
            if (s.phase !== "") win.instPhase = s.phase
            if (s.pct >= 0) {
                instPoll.miss = 0
                win.instPct = Math.max(win.instPct, s.pct)   // never go backwards
            } else {
                instPoll.miss++
                // ~90s of total silence with no terminal line → the dispatch failed.
                // Must comfortably exceed the helper's online ensure_network worst
                // case (45x1s + two systemctl restarts) so a legitimately slow
                // network-up is never mistaken for a stall. The helper also emits a
                // heartbeat during that wait, so this threshold is the backstop.
                if (instPoll.miss > 200 && !terminal) {
                    win.instState = "fail"
                    win.failReason = "stalled"
                    instPoll.stop()
                    return
                }
            }
            if (terminal) {
                instPoll.stop()
                if (s.state === "done") {
                    win.instPct = 100
                    win.instState = "done"
                    doneBeat.restart()
                } else {
                    win.instState = "fail"
                    win.failReason = s.reason || "generic"
                }
            }
        }
    }
    Timer { id: doneBeat; interval: 500; onTriggered: win.step = win.stepSuccess }

    // ── colour → #rrggbb helpers (Qt SVG-Tiny: hex + stroke-opacity, no rgba()) ─
    function hex2(n) {
        var s = Math.round(Math.max(0, Math.min(1, n)) * 255).toString(16)
        return s.length < 2 ? "0" + s : s
    }
    function hexColor(c) { return "#" + hex2(c.r) + hex2(c.g) + hex2(c.b) }

    // ── line-glyph library (24×24, stroke-only) — Welcome's set + installer icons ─
    readonly property var glyphs: ({
        "spark":    "<path d='M12 3l1.9 6.1L20 11l-6.1 1.9L12 19l-1.9-6.1L4 11l6.1-1.9z'/>",
        "shield":   "<path d='M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z'/>",
        "gear":     "<circle cx='12' cy='12' r='3.2'/><path d='M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.2 5.2l2.1 2.1M16.7 16.7l2.1 2.1M18.8 5.2l-2.1 2.1M7.3 16.7l-2.1 2.1'/>",
        "bolt":     "<path d='M13 2.5L5 13.5h5l-1 8 8-11h-5z'/>",
        "check":    "<path d='M5 12.5l4.5 4.5L19 7'/>",
        "database": "<ellipse cx='12' cy='6' rx='7' ry='3'/><path d='M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6'/><path d='M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3'/>",
        "container":"<rect x='3' y='8' width='18' height='11' rx='1.5'/><path d='M8 8v11M12 8v11M16 8v11'/><path d='M3 8l3-3h12l3 3'/>",
        "lock":     "<rect x='5' y='11' width='14' height='9' rx='2.5'/><path d='M8 11V8a4 4 0 0 1 8 0v3'/>",
        "sun":      "<circle cx='12' cy='12' r='4.2'/><path d='M12 2.5v2.4M12 19.1v2.4M2.5 12h2.4M19.1 12h2.4M5 5l1.7 1.7M17.3 17.3L19 19M19 5l-1.7 1.7M6.7 17.3L5 19'/>",
        "warn":     "<path d='M12 3.5l9 15.5H3z'/><path d='M12 10v4.2M12 17.4v.01'/>",
        "power":    "<path d='M12 3v8'/><path d='M7.2 6.6a8 8 0 1 0 9.6 0'/>",
        "refresh":  "<path d='M20 5v4h-4'/><path d='M20 9A8 8 0 1 0 20.5 13.5'/>",
        "disk":     "<circle cx='12' cy='12' r='9'/><circle cx='12' cy='12' r='2.4'/><path d='M12 3v4M12 17v4M3 12h4M17 12h4'/>",
        "arrow":    "<path d='M5 12h13M13 6l6 6-6 6'/>"
    })
    function glyphURL(name, c, w) {
        var inner = win.glyphs[name] || win.glyphs["spark"]
        var svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
                + "stroke='" + win.hexColor(c) + "' stroke-opacity='" + c.a.toFixed(3) + "' "
                + "stroke-width='" + w + "' stroke-linecap='round' stroke-linejoin='round'>"
                + inner + "</svg>"
        return "data:image/svg+xml;base64," + Qt.btoa(svg)
    }
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

    Component.onCompleted: { loadDisks(); loadZones() }

    // ═══════════════════════════════ BACKGROUND ═══════════════════════════════
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: win.canvas }
            GradientStop { position: 1.0; color: win.chrome }
        }
    }
    Rectangle {
        width: 560; height: 560; radius: 280
        anchors.right: parent.right; anchors.top: parent.top
        anchors.rightMargin: -200; anchors.topMargin: -220
        color: win.accent; opacity: 0.10
    }
    Rectangle {
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
                    opacity: win.step === win.stepWelcome ? 0 : 1
                    Behavior on opacity { NumberAnimation { duration: 200 } }
                }

                Item { Layout.fillWidth: true }

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

                // Balancer for the logo, so the dots stay centred. No Skip: you
                // cannot skip installing into a usable OS.
                Item { Layout.preferredWidth: 34; Layout.preferredHeight: 34 }
            }
        }

        // ─────────────────────────────── PAGES ────────────────────────────────
        StackLayout {
            id: pages
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: win.step

            // ════════ 0 · WELCOME / LANGUAGE ════════
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
                        Rectangle {
                            anchors.centerIn: parent
                            width: 120; height: 120; radius: 60
                            color: win.accent; opacity: 0.14
                        }
                        Image {
                            anchors.centerIn: parent
                            source: "file:///usr/share/moos/moos-logo.png"
                            sourceSize.width: 104; sourceSize.height: 104
                            width: 104; height: 104
                        }
                    }

                    Item { Layout.preferredHeight: 26 }

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
                        text: win.tr("أهلاً بك في MoOS", "Welcome to MoOS")
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 40; font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 18 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: win.tr("لنثبّت MoOS على جهازك. خطوات قليلة وواضحة — وأنت تقرّر كل شيء.",
                                     "Let's install MoOS on your computer. A few clear steps — you decide everything.")
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 15; lineHeight: 1.35
                    }
                    Item { Layout.preferredHeight: 10 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.tr("اختر لغتك — يتبعها النظام كله", "Pick your language — the whole system follows")
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 12; opacity: 0.8
                    }
                    Item { Layout.preferredHeight: 30 }

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
                                text: win.tr("لنبدأ التثبيت", "Let's begin")
                                color: win.onAccent
                                font.family: "IBM Plex Sans"; font.pixelSize: 17; font.weight: Font.DemiBold
                            }
                        }
                    }
                }
            }

            // ════════ 1 · WHAT MoOS IS (the honest sell) ════════
            Item {
                id: sellPage
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(880, sellPage.width - 72)
                    spacing: 0

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.tr("نظام واحد، متكامل", "One system, complete")
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 30; font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 8 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.tr("هذا ما ستحصل عليه — بصدق، دون مبالغة.", "Here's what you get — honestly, no hype.")
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 14
                    }
                    Item { Layout.preferredHeight: 30 }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 18
                        Repeater {
                            model: [
                                { glyph: "spark",  ar: "جاهز من أول إقلاع", ar2: "متجر Mo Store، ومساعد Mo AI، ومظهر أنيق — دون إعداد يدوي.",
                                  en: "Ready on first boot", en2: "Mo Store, the Mo AI assistant, and a refined look — no manual setup." },
                                { glyph: "shield", ar: "يحدّث نفسه بأمان", ar2: "تحديثات ذرّية كاملة، وإن ساء تحديث تعود للسابق بنقرة.",
                                  en: "Updates safely", en2: "Full atomic updates; if one goes wrong you roll back in a click." },
                                { glyph: "gear",   ar: "لك أنت", ar2: "عربي أو إنجليزي، فاتح أو داكن، ووجهة الجهاز تختارها بعد الإقلاع.",
                                  en: "Made yours", en2: "Arabic or English, light or dark, and you choose the machine's purpose after boot." }
                            ]
                            delegate: Rectangle {
                                id: sellCard
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredHeight: 214
                                radius: 20
                                color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.7)
                                border.width: 1
                                border.color: win.outline
                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 20
                                    spacing: 12
                                    Rectangle {
                                        Layout.preferredWidth: 56; Layout.preferredHeight: 56
                                        radius: 16
                                        color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                                        Glyph {
                                            anchors.centerIn: parent
                                            name: sellCard.modelData.glyph; tint: win.accent; stroke: 1.6
                                            width: 30; height: 30
                                        }
                                    }
                                    Text {
                                        text: win.tr(sellCard.modelData.ar, sellCard.modelData.en)
                                        color: win.txt
                                        font.family: "IBM Plex Sans"; font.pixelSize: 17; font.weight: Font.DemiBold
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: win.tr(sellCard.modelData.ar2, sellCard.modelData.en2)
                                        color: win.txt2
                                        font.family: "IBM Plex Sans"; font.pixelSize: 13; lineHeight: 1.3
                                        wrapMode: Text.WordWrap
                                    }
                                    Item { Layout.fillHeight: true }
                                }
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 30 }
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredHeight: 50
                        implicitWidth: sellNextRow.implicitWidth + 60
                        radius: 25
                        color: sellNextHover.hovered ? Qt.lighter(win.accent, 1.08) : win.accent
                        Behavior on color { ColorAnimation { duration: 120 } }
                        HoverHandler { id: sellNextHover }
                        TapHandler { onTapped: win.goNext() }
                        RowLayout {
                            id: sellNextRow
                            anchors.centerIn: parent
                            spacing: 8
                            Text {
                                text: win.tr("التالي", "Next")
                                color: win.onAccent
                                font.family: "IBM Plex Sans"; font.pixelSize: 16; font.weight: Font.DemiBold
                            }
                        }
                    }
                    Item { Layout.preferredHeight: 8 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.tr("رجوع", "Back")
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 13
                        TapHandler { onTapped: win.goBack() }
                    }
                }
            }

            // ════════ 2 · DISK SELECTION ════════
            Item {
                id: diskPage
                ColumnLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Math.max(40, (diskPage.width - 820) / 2)
                    anchors.rightMargin: Math.max(40, (diskPage.width - 820) / 2)
                    anchors.topMargin: 4
                    spacing: 0

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.tr("أين نثبّت MoOS؟", "Where should MoOS go?")
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 30; font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 8 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.eligibleDisks().length === 1
                              ? win.tr("قرص واحد فقط — إليك تفاصيله. لن يُمحى شيء الآن.",
                                       "Only one disk — here are its details. Nothing is erased yet.")
                              : win.tr("اختر القرص. لن يُمحى شيء الآن — ستؤكّد لاحقاً.",
                                       "Pick a disk. Nothing is erased yet — you'll confirm later.")
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 14
                    }
                    Item { Layout.preferredHeight: 20 }

                    // probing spinner
                    ColumnLayout {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 40
                        visible: win.probing
                        spacing: 14
                        BusyIndicator { Layout.alignment: Qt.AlignHCenter; running: win.probing }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: win.tr("نبحث عن الأقراص…", "Finding your disks…")
                            color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 14
                        }
                    }

                    // empty state
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 24
                        visible: !win.probing && win.eligibleDisks().length === 0
                        spacing: 16
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 120
                            radius: 20
                            color: win.dangerSoft
                            border.width: 1; border.color: win.danger
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 16
                                Glyph { name: "warn"; tint: win.danger; width: 30; height: 30 }
                                Text {
                                    Layout.fillWidth: true
                                    text: win.tr("لم نعثر على قرص داخلي قابل للكتابة. تأكّد من توصيل القرص ثم أعد الفحص.",
                                                 "No writable internal disk found. Check that a drive is connected, then rescan.")
                                    color: win.txt
                                    font.family: "IBM Plex Sans"; font.pixelSize: 14; wrapMode: Text.WordWrap
                                }
                            }
                        }
                        Rectangle {
                            Layout.alignment: Qt.AlignHCenter
                            Layout.preferredHeight: 44
                            implicitWidth: rescanRow.implicitWidth + 44
                            radius: 22
                            color: rescanHover.hovered ? Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.95)
                                                       : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.6)
                            border.width: 1; border.color: win.outline
                            HoverHandler { id: rescanHover }
                            TapHandler { onTapped: win.rescanDisks() }
                            RowLayout {
                                id: rescanRow
                                anchors.centerIn: parent
                                spacing: 8
                                Glyph { name: "refresh"; tint: win.txt; width: 17; height: 17 }
                                Text {
                                    text: win.tr("أعد الفحص", "Rescan")
                                    color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 14
                                }
                            }
                        }
                    }

                    // disk list
                    Flickable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: !win.probing && win.eligibleDisks().length > 0
                        contentWidth: width
                        contentHeight: diskCol.implicitHeight + 16
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        ColumnLayout {
                            id: diskCol
                            width: parent.width
                            spacing: 12

                            Repeater {
                                model: win.eligibleDisks()
                                delegate: Rectangle {
                                    id: diskCard
                                    required property var modelData
                                    readonly property bool selected: win.targetNode === diskCard.modelData.node
                                    readonly property bool disabled: diskCard.modelData.tooSmall === true
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 96
                                    radius: 20
                                    opacity: diskCard.disabled ? 0.5 : 1
                                    color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b,
                                                   diskHover.hovered || diskCard.selected ? 0.95 : 0.6)
                                    border.width: diskCard.selected ? 2 : 1
                                    border.color: diskCard.selected ? win.accent : win.outline
                                    Behavior on color { ColorAnimation { duration: 130 } }
                                    Behavior on border.color { ColorAnimation { duration: 130 } }
                                    HoverHandler { id: diskHover; enabled: !diskCard.disabled }
                                    TapHandler {
                                        enabled: !diskCard.disabled
                                        onTapped: win.targetNode = diskCard.modelData.node
                                    }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 18; anchors.rightMargin: 18
                                        spacing: 16

                                        Rectangle {
                                            Layout.preferredWidth: 56; Layout.preferredHeight: 56
                                            radius: 16
                                            color: diskCard.selected
                                                   ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.18)
                                                   : Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.9)
                                            Glyph {
                                                anchors.centerIn: parent
                                                name: "database"
                                                tint: diskCard.selected ? win.accent : win.txt
                                                stroke: 1.6; width: 28; height: 28
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 4
                                            Text {
                                                Layout.fillWidth: true
                                                // Localize the disk KIND (the drive about to be wiped
                                                // must read in the UI language); the model name is a
                                                // proper noun and stays as-is.
                                                text: win.tr(
                                                          diskCard.modelData.kind === "internal" ? "قرص داخلي"
                                                          : diskCard.modelData.kind === "removable" ? "قرص قابل للإزالة"
                                                          : diskCard.modelData.kind === "live" ? "قرص الإقلاع (USB)"
                                                          : diskCard.modelData.name,
                                                          diskCard.modelData.name)
                                                      + (diskCard.modelData.model ? " · " + diskCard.modelData.model : "")
                                                color: win.txt
                                                font.family: "IBM Plex Sans"; font.pixelSize: 16; font.weight: Font.DemiBold
                                                elide: Text.ElideRight
                                            }
                                            RowLayout {
                                                spacing: 8
                                                Text {
                                                    text: diskCard.modelData.sizeH
                                                    color: win.txt2
                                                    font.family: "IBM Plex Sans"; font.pixelSize: 13
                                                }
                                                // data badge
                                                Rectangle {
                                                    readonly property bool hasOS: diskCard.modelData.hasOS === true
                                                    readonly property bool hasData: diskCard.modelData.hasData === true
                                                    Layout.preferredHeight: 20
                                                    implicitWidth: badgeText.implicitWidth + 18
                                                    radius: 10
                                                    color: hasOS ? Qt.rgba(win.violet.r, win.violet.g, win.violet.b, 0.16)
                                                         : hasData ? Qt.rgba(win.amber.r, win.amber.g, win.amber.b, 0.16)
                                                         : Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                                                    Text {
                                                        id: badgeText
                                                        anchors.centerIn: parent
                                                        text: parent.hasOS
                                                              ? win.tr("يحتوي نظام: " + (diskCard.modelData.osName || "غير معروف"),
                                                                       "Has " + (diskCard.modelData.osName || "an OS"))
                                                              : parent.hasData ? win.tr("يحتوي بيانات", "Has data")
                                                              : win.tr("فارغ", "Empty")
                                                        color: parent.hasOS ? win.violet : parent.hasData ? win.amber : win.accent
                                                        font.family: "IBM Plex Sans"; font.pixelSize: 11; font.weight: Font.DemiBold
                                                    }
                                                }
                                                Text {
                                                    visible: diskCard.disabled
                                                    text: win.tr("صغير جداً للتثبيت", "Too small to install")
                                                    color: win.danger
                                                    font.family: "IBM Plex Sans"; font.pixelSize: 12
                                                }
                                            }
                                        }

                                        // radio-style select
                                        Rectangle {
                                            Layout.preferredWidth: 26; Layout.preferredHeight: 26
                                            radius: 13
                                            color: "transparent"
                                            border.width: 2
                                            border.color: diskCard.selected ? win.accent : win.outline
                                            Rectangle {
                                                anchors.centerIn: parent
                                                width: 13; height: 13; radius: 7
                                                color: win.accent
                                                visible: diskCard.selected
                                            }
                                        }
                                    }
                                }
                            }

                            // warning strip for a selected disk with data/OS
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: warnStripCol.implicitHeight + 24
                                visible: {
                                    var d = win.targetDisk()
                                    return d && (d.hasOS === true || d.hasData === true)
                                }
                                radius: 16
                                color: win.dangerSoft
                                border.width: 1; border.color: win.danger
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 12
                                    Glyph { name: "warn"; tint: win.danger; width: 22; height: 22; Layout.alignment: Qt.AlignTop }
                                    ColumnLayout {
                                        id: warnStripCol
                                        Layout.fillWidth: true
                                        spacing: 2
                                        Text {
                                            Layout.fillWidth: true
                                            text: win.tr("هذا القرص يحتوي على بيانات. متابعة التثبيت ستمحوها كلها.",
                                                         "This disk has data on it. Continuing will erase all of it.")
                                            color: win.txt
                                            font.family: "IBM Plex Sans"; font.pixelSize: 13; wrapMode: Text.WordWrap
                                        }
                                    }
                                }
                            }

                            // protected boot-USB row
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 64
                                visible: win.liveDisk() !== null
                                radius: 18
                                color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.35)
                                border.width: 1
                                border.color: Qt.rgba(win.outline.r, win.outline.g, win.outline.b, 0.6)
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 18; anchors.rightMargin: 18
                                    spacing: 14
                                    Rectangle {
                                        Layout.preferredWidth: 40; Layout.preferredHeight: 40
                                        radius: 12
                                        color: Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.7)
                                        Glyph { anchors.centerIn: parent; name: "lock"; tint: win.txt2; width: 20; height: 20 }
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: win.tr("قرص الإقلاع (USB) — محميّ، لن يُمَسّ",
                                                     "Boot drive (USB) — protected, never touched")
                                        color: win.txt2
                                        font.family: "IBM Plex Sans"; font.pixelSize: 13
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ════════ 3 · METHOD ════════
            Item {
                id: methodPage
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(760, methodPage.width - 72)
                    spacing: 0

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.tr("كيف نثبّت؟", "How should we install?")
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 30; font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 8 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.tr("اختر الطريقة. سنشرح كل خيار بوضوح.", "Choose a method. We'll explain each one plainly.")
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 14
                    }
                    Item { Layout.preferredHeight: 26 }

                    Repeater {
                        model: [
                            { id: "erase", glyph: "bolt",
                              ar: "امسح وثبّت", en: "Erase & install",
                              arDesc: "يمحو كل شيء على القرص المختار ويجعل MoOS النظام الوحيد. الأنظف والأبسط.",
                              enDesc: "Wipes everything on the selected disk and makes MoOS the only system. The cleanest, simplest path." }
                        ]
                        delegate: Rectangle {
                            id: methodCard
                            required property var modelData
                            readonly property bool selected: win.method === methodCard.modelData.id
                            Layout.fillWidth: true
                            Layout.preferredHeight: 118
                            Layout.bottomMargin: 16
                            radius: 20
                            color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b,
                                           methodHover.hovered || methodCard.selected ? 0.95 : 0.6)
                            border.width: methodCard.selected ? 2 : 1
                            border.color: methodCard.selected ? win.accent : win.outline
                            Behavior on color { ColorAnimation { duration: 130 } }
                            Behavior on border.color { ColorAnimation { duration: 130 } }
                            HoverHandler { id: methodHover }
                            TapHandler { onTapped: win.method = methodCard.modelData.id }

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 18
                                spacing: 16
                                Rectangle {
                                    Layout.preferredWidth: 56; Layout.preferredHeight: 56
                                    Layout.alignment: Qt.AlignTop
                                    radius: 16
                                    color: methodCard.selected
                                           ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.18)
                                           : Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.9)
                                    Glyph {
                                        anchors.centerIn: parent
                                        name: methodCard.modelData.glyph
                                        tint: methodCard.selected ? win.accent : win.txt
                                        stroke: 1.6; width: 28; height: 28
                                    }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Text {
                                        text: win.tr(methodCard.modelData.ar, methodCard.modelData.en)
                                        color: win.txt
                                        font.family: "IBM Plex Sans"; font.pixelSize: 18; font.weight: Font.DemiBold
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: win.tr(methodCard.modelData.arDesc, methodCard.modelData.enDesc)
                                        color: win.txt2
                                        font.family: "IBM Plex Sans"; font.pixelSize: 13; lineHeight: 1.3
                                        wrapMode: Text.WordWrap
                                    }
                                }
                                Rectangle {
                                    Layout.preferredWidth: 26; Layout.preferredHeight: 26
                                    Layout.alignment: Qt.AlignVCenter
                                    radius: 13
                                    color: methodCard.selected ? win.accent : "transparent"
                                    border.width: methodCard.selected ? 0 : 1
                                    border.color: win.outline
                                    Glyph {
                                        visible: methodCard.selected
                                        anchors.centerIn: parent
                                        name: "check"; tint: win.onAccent; stroke: 2.4; width: 14; height: 14
                                    }
                                }
                            }
                        }
                    }

                    // plain "what happens" strip
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        spacing: 8
                        Repeater {
                            model: [
                                { g: "check",  ar: "يُمحى كامل القرص المختار.", en: "The selected disk is fully erased." },
                                { g: "bolt",   ar: "يُنسخ MoOS ويُهيّأ للإقلاع.", en: "MoOS is copied and made bootable." },
                                { g: "warn",   ar: "بياناتك القديمة لا يمكن استرجاعها بعدها.", en: "Your old data can't be recovered afterward." }
                            ]
                            delegate: RowLayout {
                                id: whatRow
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 10
                                Glyph { name: whatRow.modelData.g
                                        tint: whatRow.modelData.g === "warn" ? win.danger : win.txt2
                                        width: 16; height: 16 }
                                Text {
                                    Layout.fillWidth: true
                                    text: win.tr(whatRow.modelData.ar, whatRow.modelData.en)
                                    color: win.txt2
                                    font.family: "IBM Plex Sans"; font.pixelSize: 13
                                }
                            }
                        }
                    }
                }
            }

            // ════════ 4 · ACCOUNT ════════
            Item {
                id: acctPage
                Flickable {
                    anchors.fill: parent
                    contentWidth: width
                    contentHeight: acctCol.implicitHeight + 28
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    ColumnLayout {
                        id: acctCol
                        width: Math.min(560, acctPage.width - 80)
                        x: Math.max(40, (acctPage.width - width) / 2)
                        spacing: 0

                        Item { Layout.preferredHeight: 6 }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: win.tr("احفظ حسابك", "Your account")
                            color: win.txt
                            font.family: "IBM Plex Sans"; font.pixelSize: 30; font.weight: Font.Bold
                        }
                        Item { Layout.preferredHeight: 8 }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: win.tr("أنشئ حسابك الآمن. كلمة السر تحمي القفل وإجراءات الإدارة، ويمكنك اختيار الدخول التلقائي.",
                                         "Create your secure account. The password protects lock and admin actions; auto sign-in stays optional.")
                            color: win.txt2
                            font.family: "IBM Plex Sans"; font.pixelSize: 14; lineHeight: 1.3
                        }
                        Item { Layout.preferredHeight: 22 }

                        // username
                        Text {
                            text: win.tr("اسم المستخدم", "Username")
                            color: win.txt2
                            font.family: "IBM Plex Sans"; font.pixelSize: 13
                        }
                        Item { Layout.preferredHeight: 6 }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 48
                            radius: 12
                            color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.7)
                            border.width: 1
                            border.color: !win.acctUserValid && win.acctUser !== "" ? win.danger
                                        : userInput.activeFocus ? win.accent : win.outline
                            TextInput {
                                id: userInput
                                anchors.fill: parent
                                anchors.leftMargin: 14; anchors.rightMargin: 14
                                verticalAlignment: TextInput.AlignVCenter
                                horizontalAlignment: win.rtl ? TextInput.AlignRight : TextInput.AlignLeft
                                color: win.txt
                                font.family: "IBM Plex Sans"; font.pixelSize: 15
                                clip: true; selectByMouse: true
                                text: "moos"
                                maximumLength: 32
                                onTextChanged: win.acctUser = text.toLowerCase()
                            }
                            Text {
                                visible: userInput.text === ""
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: win.rtl ? undefined : parent.left
                                anchors.right: win.rtl ? parent.right : undefined
                                anchors.leftMargin: 14; anchors.rightMargin: 14
                                text: "moos"
                                color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 15
                            }
                        }
                        Text {
                            visible: !win.acctUserValid && win.acctUser !== ""
                            text: win.tr("أحرف إنجليزية صغيرة وأرقام و - _ فقط، تبدأ بحرف.",
                                         "Lowercase letters, digits, - and _; must start with a letter.")
                            color: win.danger
                            font.family: "IBM Plex Sans"; font.pixelSize: 11
                            Layout.topMargin: 4
                        }
                        Item { Layout.preferredHeight: 16 }

                        // full name (optional)
                        Text {
                            text: win.tr("الاسم الكامل (اختياري)", "Full name (optional)")
                            color: win.txt2
                            font.family: "IBM Plex Sans"; font.pixelSize: 13
                        }
                        Item { Layout.preferredHeight: 6 }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 48
                            radius: 12
                            color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.7)
                            border.width: 1
                            border.color: fullInput.activeFocus ? win.accent : win.outline
                            TextInput {
                                id: fullInput
                                anchors.fill: parent
                                anchors.leftMargin: 14; anchors.rightMargin: 14
                                verticalAlignment: TextInput.AlignVCenter
                                horizontalAlignment: win.rtl ? TextInput.AlignRight : TextInput.AlignLeft
                                color: win.txt
                                font.family: "IBM Plex Sans"; font.pixelSize: 15
                                clip: true; selectByMouse: true
                                maximumLength: 64
                                onTextChanged: win.acctFull = text
                            }
                        }
                        Item { Layout.preferredHeight: 22 }

                        // Sign-in behaviour. Both choices keep the required
                        // password for lock-screen and privileged actions.
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 14
                            Repeater {
                                model: [
                                    { autoLogin: false, glyph: "lock", ar: "الدخول بكلمة السر", en: "Password at sign-in",
                                      arD: "الخيار الآمن الموصى به", enD: "Recommended — asks at startup" },
                                    { autoLogin: true, glyph: "bolt", ar: "دخول تلقائي", en: "Auto sign-in",
                                      arD: "يفتح سطح المكتب مباشرة — تبقى كلمة السر للإدارة والقفل",
                                      enD: "Opens the desktop directly — password still protects admin and lock" }
                                ]
                                delegate: Rectangle {
                                    id: pwCard
                                    required property var modelData
                                    readonly property bool selected: win.acctAutologin === pwCard.modelData.autoLogin
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 92
                                    radius: 16
                                    color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b,
                                                   pwHover.hovered || pwCard.selected ? 0.95 : 0.6)
                                    border.width: pwCard.selected ? 2 : 1
                                    border.color: pwCard.selected ? win.accent : win.outline
                                    Behavior on border.color { ColorAnimation { duration: 120 } }
                                    HoverHandler { id: pwHover }
                                    TapHandler { onTapped: win.acctAutologin = pwCard.modelData.autoLogin }
                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 4
                                        RowLayout {
                                            spacing: 8
                                            Glyph { name: pwCard.modelData.glyph
                                                    tint: pwCard.selected ? win.accent : win.txt2
                                                    width: 18; height: 18 }
                                            Text {
                                                text: win.tr(pwCard.modelData.ar, pwCard.modelData.en)
                                                color: win.txt
                                                font.family: "IBM Plex Sans"; font.pixelSize: 15; font.weight: Font.DemiBold
                                            }
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: win.tr(pwCard.modelData.arD, pwCard.modelData.enD)
                                            color: win.txt2
                                            font.family: "IBM Plex Sans"; font.pixelSize: 12; wrapMode: Text.WordWrap
                                        }
                                        Item { Layout.fillHeight: true }
                                    }
                                }
                            }
                        }

                        // Password fields are always required. Auto sign-in only
                        // controls the greeter; it never weakens sudo or Polkit.
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Item { Layout.preferredHeight: 16 }
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 48
                                radius: 12
                                color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.7)
                                border.width: 1
                                border.color: passInput.activeFocus ? win.accent : win.outline
                                TextInput {
                                    id: passInput
                                    anchors.fill: parent
                                    anchors.leftMargin: 14; anchors.rightMargin: 14
                                    verticalAlignment: TextInput.AlignVCenter
                                    color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 15
                                    echoMode: TextInput.Password; clip: true; selectByMouse: true
                                    onTextChanged: win.acctPass = text
                                }
                                Text {
                                    visible: passInput.text === ""
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: win.rtl ? undefined : parent.left
                                    anchors.right: win.rtl ? parent.right : undefined
                                    anchors.leftMargin: 14; anchors.rightMargin: 14
                                    text: win.tr("كلمة السر", "Password")
                                    color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 15
                                }
                            }
                            Item { Layout.preferredHeight: 10 }
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 48
                                radius: 12
                                color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.7)
                                border.width: 1
                                border.color: win.acctPass2 !== "" && win.acctPass !== win.acctPass2 ? win.danger
                                            : pass2Input.activeFocus ? win.accent : win.outline
                                TextInput {
                                    id: pass2Input
                                    anchors.fill: parent
                                    anchors.leftMargin: 14; anchors.rightMargin: 14
                                    verticalAlignment: TextInput.AlignVCenter
                                    color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 15
                                    echoMode: TextInput.Password; clip: true; selectByMouse: true
                                    onTextChanged: win.acctPass2 = text
                                }
                                Text {
                                    visible: pass2Input.text === ""
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: win.rtl ? undefined : parent.left
                                    anchors.right: win.rtl ? parent.right : undefined
                                    anchors.leftMargin: 14; anchors.rightMargin: 14
                                    text: win.tr("أعد كلمة السر", "Repeat password")
                                    color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 15
                                }
                            }
                            Text {
                                visible: win.acctPass !== "" && win.acctPass.length < 8
                                text: win.tr("استخدم 8 محارف على الأقل.", "Use at least 8 characters.")
                                color: win.danger
                                font.family: "IBM Plex Sans"; font.pixelSize: 11
                                Layout.topMargin: 4
                            }
                            Text {
                                visible: win.acctPass2 !== "" && win.acctPass !== win.acctPass2
                                text: win.tr("كلمتا السر غير متطابقتين", "The passwords don't match")
                                color: win.danger
                                font.family: "IBM Plex Sans"; font.pixelSize: 11
                                Layout.topMargin: 4
                            }
                        }

                        Item { Layout.preferredHeight: 14 }
                        Text {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: win.tr("تُنشأ حسابك عند أول إقلاع. تقدر تغيّر كل شيء لاحقاً من الإعدادات.",
                                         "Your account is created on first boot. You can change everything later in Settings.")
                            color: win.txt2
                            font.family: "IBM Plex Sans"; font.pixelSize: 12; opacity: 0.85
                        }
                        Item { Layout.preferredHeight: 8 }
                    }
                }
            }

            // ════════ 5 · TIME ZONE ════════
            // The clock is the most-looked-at thing on the desktop, and it was the one thing
            // the install never asked about — it guessed from the LANGUAGE. Language is not
            // location (an Arabic speaker in Germany got Riyadh; an English one got UTC), so
            // the guess is only where this list starts. The zones come from tzdata's own
            // zone1970.tab, so the picker cannot drift from what /usr/share/zoneinfo has.
            Item {
                id: zonePage
                ColumnLayout {
                    id: zoneCol
                    width: Math.min(560, zonePage.width - 80)
                    x: Math.max(40, (zonePage.width - width) / 2)
                    height: zonePage.height
                    spacing: 0

                    Item { Layout.preferredHeight: 6 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.tr("منطقتك الزمنية", "Your time zone")
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 30; font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 8 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: win.tr("عشان الساعة تضبط من أول لحظة. اخترنا لك بداية — صحّحها لو مكانك غير.",
                                     "So the clock is right from the first minute. We picked a starting point — change it if you are somewhere else.")
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 14; lineHeight: 1.3
                    }
                    Item { Layout.preferredHeight: 18 }

                    // search
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 48
                        radius: 12
                        color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.7)
                        border.width: 1
                        border.color: zoneSearch.activeFocus ? win.accent : win.outline
                        TextInput {
                            id: zoneSearch
                            anchors.fill: parent
                            anchors.leftMargin: 14; anchors.rightMargin: 14
                            verticalAlignment: TextInput.AlignVCenter
                            horizontalAlignment: win.rtl ? TextInput.AlignRight : TextInput.AlignLeft
                            color: win.txt
                            font.family: "IBM Plex Sans"; font.pixelSize: 15
                            clip: true; selectByMouse: true
                            onTextChanged: win.zoneFilter = text
                        }
                        Text {
                            visible: zoneSearch.text === ""
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: win.rtl ? undefined : parent.left
                            anchors.right: win.rtl ? parent.right : undefined
                            anchors.leftMargin: 14; anchors.rightMargin: 14
                            text: win.tr("ابحث… مثلاً برلين أو Berlin", "Search… e.g. Berlin")
                            color: win.txt2; font.family: "IBM Plex Sans"; font.pixelSize: 15
                        }
                    }
                    Item { Layout.preferredHeight: 12 }

                    // the list
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.bottomMargin: 18
                        radius: 12
                        color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.45)
                        border.width: 1; border.color: win.outline
                        clip: true

                        ListView {
                            id: zoneList
                            anchors.fill: parent
                            anchors.margins: 6
                            clip: true
                            model: win.zonesFiltered()
                            currentIndex: -1
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                            // Scroll the pick into view, or the promise above is a lie: sorted
                            // alphabetically this list parks on "Africa › Abidjan", so the page
                            // said "we picked a starting point" while the screen showed nothing
                            // picked — the pre-selection existed only in the recipe.
                            //
                            // The height guard is the whole trick. Component.onCompleted runs
                            // BEFORE the layout has given this view a size: measured, height was
                            // -12 (anchors.fill of a parent still at 0, minus the 6px margins),
                            // and positionViewAtIndex on a negative height silently lands
                            // somewhere near the end of the list. The index was right all along
                            // (Europe/Berlin = 245 of 312) — the viewport was not. So reveal only
                            // once there is a real viewport, and only ONCE, or a later relayout
                            // would yank the list back while the user is reading it.
                            property bool revealed: false
                            function revealPick() {
                                if (revealed || height <= 0 || !model || win.tz === "") return
                                var i = model.indexOf(win.tz)
                                if (i < 0) return
                                positionViewAtIndex(i, ListView.Center)
                                revealed = true
                            }
                            onHeightChanged: revealPick()
                            onModelChanged: revealPick()
                            Component.onCompleted: revealPick()
                            delegate: Rectangle {
                                required property string modelData
                                width: zoneList.width - 12
                                height: 40
                                radius: 9
                                readonly property bool picked: modelData === win.tz
                                color: picked ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.18)
                                     : zoneHover.hovered ? Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.9)
                                     : "transparent"
                                border.width: picked ? 1 : 0
                                border.color: win.accent
                                HoverHandler { id: zoneHover }
                                TapHandler { onTapped: win.tz = modelData }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: win.rtl ? undefined : parent.left
                                    anchors.right: win.rtl ? parent.right : undefined
                                    anchors.leftMargin: 12; anchors.rightMargin: 12
                                    width: parent.width - 24
                                    elide: Text.ElideRight
                                    text: win.zoneLabel(parent.modelData)
                                    color: parent.picked ? win.txt : win.txt2
                                    font.family: "IBM Plex Sans"; font.pixelSize: 14
                                    font.weight: parent.picked ? Font.DemiBold : Font.Normal
                                }
                            }
                        }
                        // The list never reads empty-and-silent: a failed read or a filter that
                        // matches nothing says so, instead of looking like a broken app.
                        Text {
                            anchors.centerIn: parent
                            width: parent.width - 40
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            visible: zoneList.count === 0
                            text: win.zones.length === 0
                                  ? win.tr("تعذّرت قراءة قائمة المناطق — سنكمل بـ " + win.tz,
                                           "Could not read the zone list — we will use " + win.tz)
                                  : win.tr("ما في منطقة بهذا الاسم", "No zone matches that")
                            color: win.txt2
                            font.family: "IBM Plex Sans"; font.pixelSize: 14
                        }
                    }
                }
            }

            // ════════ 6 · CONFIRM (point of no return) ════════
            Item {
                id: confirmPage
                readonly property var d: win.targetDisk()

                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(560, confirmPage.width - 80)
                    spacing: 0

                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 72; Layout.preferredHeight: 72
                        radius: 36
                        color: win.dangerSoft
                        border.width: 2; border.color: win.danger
                        Glyph { anchors.centerIn: parent; name: "warn"; tint: win.danger; stroke: 2.0; width: 34; height: 34 }
                    }
                    Item { Layout.preferredHeight: 20 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.tr("نقطة اللاعودة", "The point of no return")
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 28; font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 10 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: win.tr("تأكّد من التفاصيل. بعد هذه الخطوة يبدأ المسح ولا يمكن التراجع.",
                                     "Check the details. After this, erasing begins and can't be undone.")
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 14; lineHeight: 1.3
                    }
                    Item { Layout.preferredHeight: 22 }

                    // summary card
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: summaryCol.implicitHeight + 32
                        radius: 18
                        color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.7)
                        border.width: 1; border.color: win.outline
                        ColumnLayout {
                            id: summaryCol
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 10
                            Repeater {
                                model: [
                                    { ar: "القرص", en: "Disk",   v: confirmPage.d ? confirmPage.d.name : "—", danger: false },
                                    { ar: "الموديل", en: "Model", v: confirmPage.d ? (confirmPage.d.model || "—") : "—", danger: false },
                                    { ar: "الحجم", en: "Size",   v: confirmPage.d ? confirmPage.d.sizeH : "—", danger: false },
                                    { ar: "الإجراء", en: "Action", v: win.tr("سيُمحى بالكامل", "Will be fully erased"), danger: true },
                                    { ar: "النتيجة", en: "Result", v: win.tr("MoOS النظام الوحيد", "MoOS as the only system"), danger: false }
                                ]
                                delegate: RowLayout {
                                    id: sumRow
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: 12
                                    Text {
                                        Layout.preferredWidth: 88
                                        text: win.tr(sumRow.modelData.ar, sumRow.modelData.en)
                                        color: win.txt2
                                        font.family: "IBM Plex Sans"; font.pixelSize: 13
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: sumRow.modelData.v
                                        color: sumRow.modelData.danger ? win.danger : win.txt
                                        font.family: "IBM Plex Sans"; font.pixelSize: 14
                                        font.weight: sumRow.modelData.danger ? Font.DemiBold : Font.Normal
                                        horizontalAlignment: win.rtl ? Text.AlignLeft : Text.AlignRight
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }

                    // re-validation banner (target changed / vanished)
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.topMargin: 14
                        Layout.preferredHeight: 52
                        visible: confirmPage.d === null || win.targetNode === win.liveNode
                        radius: 14
                        color: win.dangerSoft
                        border.width: 1; border.color: win.danger
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 10
                            Glyph { name: "warn"; tint: win.danger; width: 20; height: 20 }
                            Text {
                                Layout.fillWidth: true
                                text: win.tr("تغيّر القرص المختار. عد واختر من جديد.",
                                             "The selected disk changed. Go back and choose again.")
                                color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 13; wrapMode: Text.WordWrap
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 22 }

                    // hold-to-erase control
                    Rectangle {
                        id: holdBtn
                        readonly property bool armed: confirmPage.d !== null && win.targetNode !== win.liveNode
                        property real hold: 0
                        Layout.fillWidth: true
                        Layout.preferredHeight: 56
                        radius: 28
                        opacity: holdBtn.armed ? 1 : 0.5
                        color: Qt.rgba(win.danger.r, win.danger.g, win.danger.b, 0.16)
                        border.width: 1.5; border.color: win.danger

                        // fill that grows while held
                        Rectangle {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: parent.width * holdBtn.hold
                            radius: 28
                            color: win.danger
                            Behavior on width { NumberAnimation { duration: 60 } }
                        }
                        Text {
                            anchors.centerIn: parent
                            text: holdBtn.hold > 0.02
                                  ? win.tr("استمر بالضغط…", "Keep holding…")
                                  : win.tr("اضغط مطوّلاً للمسح والتثبيت", "Press and hold to erase & install")
                            color: holdBtn.hold > 0.5 ? win.onAccent : win.danger
                            font.family: "IBM Plex Sans"; font.pixelSize: 15; font.weight: Font.DemiBold
                        }
                        Timer {
                            id: holdTimer
                            interval: 16; repeat: true
                            onTriggered: {
                                holdBtn.hold += 16 / 1600
                                if (holdBtn.hold >= 1) {
                                    holdBtn.hold = 1
                                    holdTimer.stop()
                                    win.startInstall()
                                }
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            enabled: holdBtn.armed
                            // Always start from zero: a completed hold leaves hold==1
                            // (startInstall never resets it), and revisiting Confirm
                            // must not let one tap re-fire the irreversible wipe.
                            onPressed: { holdBtn.hold = 0; holdTimer.start() }
                            onReleased: { holdTimer.stop(); if (holdBtn.hold < 1) holdBtn.hold = 0 }
                            onCanceled: { holdTimer.stop(); if (holdBtn.hold < 1) holdBtn.hold = 0 }
                        }
                    }
                    Item { Layout.preferredHeight: 14 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.tr("تراجع، لم أتأكد بعد", "Go back, I'm not sure yet")
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 14
                        TapHandler { onTapped: win.goBack() }
                    }
                }
            }

            // ════════ 6 · PROGRESS ════════
            Item {
                id: progressPage
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(620, progressPage.width - 80)
                    spacing: 0

                    // breathing mark keeps the slow copy feeling alive
                    Item {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 120; Layout.preferredHeight: 120
                        visible: win.instState !== "fail"
                        Repeater {
                            model: 2
                            delegate: Rectangle {
                                id: pring
                                required property int index
                                anchors.centerIn: parent
                                width: 88 + pring.index * 26
                                height: width; radius: width / 2
                                color: "transparent"; border.width: 1
                                border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.30 - pring.index * 0.1)
                                SequentialAnimation on scale {
                                    running: progressPage.visible && win.instState === "running"
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 1.07; duration: 2200 + pring.index * 400; easing.type: Easing.InOutSine }
                                    NumberAnimation { to: 1.0;  duration: 2200 + pring.index * 400; easing.type: Easing.InOutSine }
                                }
                            }
                        }
                        Image {
                            anchors.centerIn: parent
                            source: "file:///usr/share/moos/moos-logo.png"
                            sourceSize.width: 64; sourceSize.height: 64
                            width: 64; height: 64
                        }
                    }
                    // fail icon
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 96; Layout.preferredHeight: 96
                        visible: win.instState === "fail"
                        radius: 48
                        color: win.dangerSoft
                        border.width: 2; border.color: win.danger
                        Glyph { anchors.centerIn: parent; name: "warn"; tint: win.danger; stroke: 2.4; width: 44; height: 44 }
                    }

                    Item { Layout.preferredHeight: 24 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.instState === "fail"
                              ? win.tr("تعثّر التثبيت", "Installation stopped")
                              : win.tr("نثبّت MoOS…", "Installing MoOS…")
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 30; font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 10 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        visible: win.instState !== "fail"
                        text: win.tr("قد يستغرق بضع دقائق. لا تفصل الطاقة ولا تنزع USB بعد.",
                                     "This can take a few minutes. Don't cut power or remove the USB yet.")
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 14; lineHeight: 1.3
                    }
                    Item { Layout.preferredHeight: 24 }

                    // overall bar (running) — turns danger on fail
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 10
                        radius: 5
                        color: Qt.rgba(win.outline.r, win.outline.g, win.outline.b, 0.5)
                        Rectangle {
                            width: parent.width * (win.instPct / 100)
                            height: parent.height; radius: 5
                            color: win.instState === "fail" ? win.danger : win.accent
                            Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
                        }
                    }
                    Item { Layout.preferredHeight: 12 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        visible: win.instState !== "fail"
                        // Western "45%" on both paths: instPct is a Number (always
                        // Western digits), so the old Arabic "٪" produced mixed script
                        // ("45٪"). One sign that matches the digits, no bidi surprises.
                        text: win.phaseLabel(win.instPhase) + " — " + win.instPct + "%"
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 15; font.weight: Font.DemiBold
                    }

                    // reassurance (running)
                    Item { Layout.preferredHeight: 18; visible: win.instState !== "fail" }
                    Rectangle {
                        Layout.fillWidth: true
                        visible: win.instState !== "fail"
                        Layout.preferredHeight: 56
                        radius: 14
                        color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.6)
                        border.width: 1; border.color: win.outline
                        Text {
                            anchors.fill: parent
                            anchors.margins: 14
                            verticalAlignment: Text.AlignVCenter
                            wrapMode: Text.WordWrap
                            text: win.tr("نكتب كل شيء بعناية. ستُعلمك هذه الشاشة فور الانتهاء.",
                                         "We're writing everything carefully. This screen will tell you the moment it's done.")
                            color: win.txt2
                            font.family: "IBM Plex Sans"; font.pixelSize: 13
                        }
                    }

                    // failure block
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: win.instState === "fail"
                        spacing: 14
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: failCol.implicitHeight + 28
                            radius: 16
                            color: win.dangerSoft
                            border.width: 1; border.color: win.danger
                            ColumnLayout {
                                id: failCol
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 8
                                Text {
                                    Layout.fillWidth: true
                                    text: win.failText(win.failReason)
                                    color: win.txt
                                    font.family: "IBM Plex Sans"; font.pixelSize: 14; wrapMode: Text.WordWrap
                                }
                                Text {
                                    text: win.tr("عرض التفاصيل: ", "Details: ") + "FAIL " + win.failReason
                                    color: win.txt2
                                    font.family: "IBM Plex Sans"; font.pixelSize: 11; opacity: 0.7
                                }
                            }
                        }
                        RowLayout {
                            Layout.alignment: Qt.AlignHCenter
                            spacing: 12
                            Rectangle {
                                Layout.preferredHeight: 46
                                implicitWidth: retryRow.implicitWidth + 48
                                radius: 23
                                color: retryHover.hovered ? Qt.lighter(win.accent, 1.08) : win.accent
                                HoverHandler { id: retryHover }
                                TapHandler { onTapped: win.startInstall() }
                                RowLayout {
                                    id: retryRow
                                    anchors.centerIn: parent
                                    spacing: 8
                                    Glyph { name: "refresh"; tint: win.onAccent; width: 16; height: 16 }
                                    Text {
                                        text: win.tr("أعد المحاولة", "Retry")
                                        color: win.onAccent
                                        font.family: "IBM Plex Sans"; font.pixelSize: 15; font.weight: Font.DemiBold
                                    }
                                }
                            }
                            Rectangle {
                                Layout.preferredHeight: 46
                                implicitWidth: otherRow.implicitWidth + 44
                                radius: 23
                                color: otherHover.hovered ? Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.95)
                                                          : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.6)
                                border.width: 1; border.color: win.outline
                                HoverHandler { id: otherHover }
                                TapHandler { onTapped: { win.instState = "idle"; win.step = win.stepDisk } }
                                RowLayout {
                                    id: otherRow
                                    anchors.centerIn: parent
                                    Text {
                                        text: win.tr("اختر قرصاً آخر", "Choose another disk")
                                        color: win.txt
                                        font.family: "IBM Plex Sans"; font.pixelSize: 15
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ════════ 7 · SUCCESS ════════
            Item {
                id: successPage
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(620, successPage.width - 80)
                    spacing: 0

                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 96; Layout.preferredHeight: 96
                        radius: 48
                        color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                        border.width: 2; border.color: win.accent
                        scale: successPage.visible ? 1 : 0.6
                        Behavior on scale { NumberAnimation { duration: 320; easing.type: Easing.OutBack } }
                        Glyph { anchors.centerIn: parent; name: "check"; tint: win.accent; stroke: 2.6; width: 44; height: 44 }
                    }

                    Item { Layout.preferredHeight: 24 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: win.tr("تم تثبيت MoOS", "MoOS is installed")
                        color: win.txt
                        font.family: "IBM Plex Sans"; font.pixelSize: 34; font.weight: Font.Bold
                    }
                    Item { Layout.preferredHeight: 10 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: win.tr("انزع USB ثم أعد التشغيل. عند الإقلاع سيرحّب بك MoOS ويساعدك في اختيار مظهرك ووجهتك وتطبيقاتك.",
                                     "Remove the USB and restart. On first boot, MoOS will welcome you and help you pick your look, direction, and apps.")
                        color: win.txt2
                        font.family: "IBM Plex Sans"; font.pixelSize: 15; lineHeight: 1.35
                    }
                    Item { Layout.preferredHeight: 28 }

                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 14
                        Rectangle {
                            Layout.preferredHeight: 50
                            implicitWidth: rebootRow.implicitWidth + 52
                            radius: 25
                            color: rebootHover.hovered ? Qt.lighter(win.accent, 1.08) : win.accent
                            HoverHandler { id: rebootHover }
                            TapHandler { onTapped: Qt.openUrlExternally("moos://installer/reboot") }
                            RowLayout {
                                id: rebootRow
                                anchors.centerIn: parent
                                spacing: 8
                                Glyph { name: "power"; tint: win.onAccent; width: 17; height: 17 }
                                Text {
                                    text: win.tr("أعد التشغيل الآن", "Restart now")
                                    color: win.onAccent
                                    font.family: "IBM Plex Sans"; font.pixelSize: 15; font.weight: Font.DemiBold
                                }
                            }
                        }
                        Rectangle {
                            Layout.preferredHeight: 50
                            implicitWidth: poweroffRow.implicitWidth + 48
                            radius: 25
                            color: poweroffHover.hovered ? Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.95)
                                                         : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.6)
                            border.width: 1; border.color: win.outline
                            HoverHandler { id: poweroffHover }
                            TapHandler { onTapped: Qt.openUrlExternally("moos://installer/poweroff") }
                            RowLayout {
                                id: poweroffRow
                                anchors.centerIn: parent
                                Text {
                                    text: win.tr("إيقاف التشغيل", "Power off")
                                    color: win.txt
                                    font.family: "IBM Plex Sans"; font.pixelSize: 15; font.weight: Font.DemiBold
                                }
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 18 }
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredHeight: 34
                        implicitWidth: usbRow.implicitWidth + 30
                        radius: 17
                        color: Qt.rgba(win.amber.r, win.amber.g, win.amber.b, 0.14)
                        border.width: 1; border.color: Qt.rgba(win.amber.r, win.amber.g, win.amber.b, 0.5)
                        RowLayout {
                            id: usbRow
                            anchors.centerIn: parent
                            spacing: 7
                            Glyph { name: "warn"; tint: win.amber; width: 14; height: 14 }
                            Text {
                                text: win.tr("تذكّر: انزع USB أولاً", "Remember: remove the USB first")
                                color: win.amber
                                font.family: "IBM Plex Sans"; font.pixelSize: 13; font.weight: Font.DemiBold
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 24 }

                    // MoOS's own signature — designed by Moalfarras, with a QR to
                    // the site. No Fedora, no upstream mark: this is MoOS.
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 16
                        Rectangle {
                            Layout.preferredWidth: 96; Layout.preferredHeight: 96
                            radius: 14
                            color: "#FFFFFF"
                            Image {
                                anchors.centerIn: parent
                                width: 82; height: 82
                                source: "file:///usr/share/moos/apps/installer/qr-moalfarras.png"
                                sourceSize.width: 164; sourceSize.height: 164
                                smooth: true
                                fillMode: Image.PreserveAspectFit
                            }
                        }
                        ColumnLayout {
                            spacing: 4
                            Text {
                                text: win.tr("صُمّم بواسطة Moalfarras", "Designed by Moalfarras")
                                color: win.txt
                                font.family: "IBM Plex Sans"; font.pixelSize: 16; font.weight: Font.DemiBold
                            }
                            Rectangle {
                                Layout.preferredHeight: 30
                                implicitWidth: siteRow.implicitWidth + 24
                                radius: 15
                                color: siteHover.hovered ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                                                         : Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.08)
                                HoverHandler { id: siteHover }
                                TapHandler { onTapped: Qt.openUrlExternally("https://www.moalfarras.space") }
                                RowLayout {
                                    id: siteRow
                                    anchors.centerIn: parent
                                    spacing: 6
                                    Glyph { name: "arrow"; tint: win.accent; width: 14; height: 14 }
                                    Text {
                                        text: "www.moalfarras.space"
                                        color: win.accent
                                        font.family: "IBM Plex Sans"; font.pixelSize: 14; font.weight: Font.DemiBold
                                    }
                                }
                            }
                            Text {
                                text: win.tr("امسح الرمز لزيارة الموقع", "Scan the code to visit")
                                color: win.txt2
                                font.family: "IBM Plex Sans"; font.pixelSize: 12
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
                    color: backHover.hovered ? Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.95)
                                             : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.5)
                    border.width: 1; border.color: win.outline
                    HoverHandler { id: backHover }
                    TapHandler { onTapped: win.goBack() }
                    RowLayout {
                        id: backRow
                        anchors.centerIn: parent
                        Text {
                            text: win.tr("السابق", "Back")
                            color: win.txt; font.family: "IBM Plex Sans"; font.pixelSize: 15
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                Rectangle {   // next
                    readonly property bool ready: (win.step === win.stepDisk && win.targetNode !== "")
                                                  || win.step === win.stepMethod
                                                  || (win.step === win.stepAccount && win.acctValid)
                                                  || (win.step === win.stepZone && win.tz !== "")
                    Layout.preferredHeight: 46
                    implicitWidth: nextRow.implicitWidth + 52
                    radius: 23
                    opacity: ready ? 1 : 0.45
                    color: nextHover.hovered ? Qt.lighter(win.accent, 1.08) : win.accent
                    HoverHandler { id: nextHover; enabled: parent.ready }
                    TapHandler {
                        enabled: parent.ready
                        onTapped: win.goNext()
                    }
                    RowLayout {
                        id: nextRow
                        anchors.centerIn: parent
                        spacing: 8
                        Text {
                            text: win.tr("التالي", "Next")
                            color: win.onAccent
                            font.family: "IBM Plex Sans"; font.pixelSize: 15; font.weight: Font.DemiBold
                        }
                    }
                }
            }
        }
    }
}
