// Mo AI — the MoOS assistant, and the one place the system is managed from.
// Launched by /usr/bin/moai (qml-qt6 runtime — pure QML, no compilation).
//
// WHAT THIS IS
//   The Hardware Centre, the Compatibility Hub and the App Centre used to be
//   separate windows onto the same JSON that Mo AI already read, sitting next to
//   the one app that could actually explain what was wrong and repair it. They
//   are panels in here now, and /usr/bin/moos-hardware and /usr/bin/moos-compat
//   are shims that open `moai --device`.
//
// HOW IT REACHES THE SYSTEM — the honest design, do not widen it
//   Pure QML has NO Process API and its XMLHttpRequest cannot write local files,
//   so this window CANNOT execute anything. It has exactly two channels:
//
//     1. moai-control on 127.0.0.1:8079 — READ-ONLY state (/quick, /scan,
//        /search) plus its own brain config (/config). It changes nothing else.
//     2. Qt.openUrlExternally("moos://…") — the scheme handler /usr/bin/moos-open,
//        a strict whitelist, which runs the matching /usr/bin/moai-do action in a
//        VISIBLE terminal with a confirmation and a Polkit prompt.
//
//   The model can NAME an action from that fixed allowlist; the UI turns it into
//   a Run button; the user still confirms and still authenticates. The model
//   never executes anything, and neither does this file. Every moos:// URL below
//   must have a case in moos-open — tests/verify_user_experience.py cross-checks
//   the two, because three buttons once shipped pointing at routes that did not
//   exist and silently did nothing.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.Shapes
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    // ── Semantic design tokens — supplied by the active KDE scheme ───────
    // These bindings are deliberately owned by ApplicationWindow.palette. A
    // Global Theme changes KDE's palette at runtime; keeping Nova hex values
    // here made every card stay navy even on a light desktop.
    readonly property color surface0: root.palette.base             // canvas
    readonly property color surface1: root.palette.alternateBase    // cards
    readonly property color surface2: root.palette.button           // raised controls
    readonly property color surface3: root.palette.midlight         // hover / selected
    readonly property color chrome:   root.palette.window           // rail / headers
    readonly property color hairline: root.palette.mid
    readonly property color textHi:   root.palette.windowText
    readonly property color textLo:   root.palette.placeholderText
    readonly property color textMute: Qt.rgba(root.palette.placeholderText.r,
                                               root.palette.placeholderText.g,
                                               root.palette.placeholderText.b, 0.78)
    readonly property color novaCyan:   root.palette.link
    readonly property color novaBlue:   root.palette.highlight
    readonly property color novaViolet: root.palette.linkVisited
    readonly property color onAccent:   root.palette.highlightedText
    readonly property color okColor:   Kirigami.Theme.positiveTextColor
    readonly property color warnColor: Kirigami.Theme.neutralTextColor
    readonly property color badColor:  Kirigami.Theme.negativeTextColor
    readonly property string uiFont: "IBM Plex Sans"

    // ── Endpoints ───────────────────────────────────────────────────────────
    // 8080 is Mo AI's FRONT DOOR (moai-gateway) and nothing else. It is always
    // on, and it routes each REQUEST: to the local RamaLama brain on 8081 (which
    // it starts on demand) or to the configured cloud provider — whose API key it
    // alone ever sees. This app names the route it wants in the request's `model`
    // field and never learns the key, the provider, or the port behind the door.
    //
    // It used to be an either/or: the local brain and the cloud proxy both
    // listened on 8080, so only one could run, the choice was a global setting,
    // and changing it meant bouncing systemd units. That is why `route` below
    // exists at all.
    readonly property string api: "http://127.0.0.1:8080/v1/chat/completions"
    readonly property string controlApi: "http://127.0.0.1:8079"

    property var activeXhr: null
    property bool busy: false
    property bool brainStarting: false
    property var history: []            // [{role, content}] — last 12 turns
    property var pendingRuns: []        // moai-do actions the model just named
    property string panel: "chat"       // chat|device|apps|compat|remote|dev

    // ── Which brain answers THIS conversation ───────────────────────────────
    // `route` is exactly what goes in the POST's `model` field, and it is the
    // whole contract with moai-gateway:
    //     "local" | "local:<model>" | "cloud" | "cloud:<model-id>"
    // Empty means "the configured default" — which is what we send until
    // /models tells us what that default resolves to.
    property string route: ""
    property string defaultRoute: ""
    property var localModels: []        // moai-control /models — from `ramalama list`
    property var cloudModels: []        // …and from the PROVIDER's own /v1/models
    property string modelsError: ""
    property bool modelsLoading: false
    property bool pickerOpen: false

    readonly property bool routeIsCloud: root.route.indexOf("cloud") === 0
    readonly property bool routeIsLocal: root.route.indexOf("local") === 0
    // The part after the FIRST colon — a model id may contain colons of its own
    // ("local:qwen3:4b-instruct").
    readonly property string routeModel: {
        const i = root.route.indexOf(":")
        return i === -1 ? "" : root.route.substring(i + 1)
    }

    // ── Is the brain we are actually pointed at able to answer? ─────────────
    // Not "is something listening on 8080" — the gateway is ALWAYS listening, so
    // that question now answers yes on behalf of nobody. It depends on which
    // route the user picked, and only this app knows that.
    property var brains: ({})           // /quick: {gateway, local, cloud}
    property bool brainsKnown: false
    property bool defaultOnline: false  // /quick: can the DEFAULT brain answer
    readonly property bool serverUp:
          !root.brains.gateway ? false
        : root.routeIsLocal ? !!root.brains.local
        : root.routeIsCloud ? !!root.brains.cloud
        : root.defaultOnline

    // Live system state from moai-control.
    property var snap: ({})             // /scan
    property var plan: ({})             // snap.device_plan
    property bool scanning: false
    property string machineContext: ""

    title: "Mo AI"
    width: 940
    height: 700
    minimumWidth: 720
    minimumHeight: 540
    color: surface0
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    // ── Health, derived from the detector rather than asserted ──────────────
    //
    // planReady matters: moai-control refreshes the device plan on a background
    // thread and reports device_plan_pending until the first one lands. Without
    // this the panel would read "no problems" from an EMPTY action list and tell
    // the user their device was healthy before anything had looked at it.
    readonly property bool planReady: !snap.device_plan_pending && !!snap.device_plan
    readonly property var actions: (plan.actions || [])
    readonly property int problemCount: actions.length
    readonly property bool healthy: planReady && problemCount === 0
    readonly property bool hasImportant: {
        for (let i = 0; i < actions.length; i++)
            if (actions[i].severity === "important")
                return true
        return false
    }

    readonly property var remoteState: (snap.remote || {})
    readonly property var agentState: (snap.agents || {})
    readonly property var compatState: (snap.compatibility || {})
    readonly property var appState: (snap.apps || {})

    // ── The companion's mood ────────────────────────────────────────────────
    property string moodFlash: ""
    readonly property string mood:
          moodFlash !== "" ? moodFlash
        : !serverUp ? (brainStarting ? "thinking" : "offline")
        : busy ? "thinking"
        : (input.activeFocus && input.text.trim().length > 0) ? "attentive"
        : "idle"

    function flashMood(m) {
        moodFlash = m
        moodTimer.restart()
    }
    Timer { id: moodTimer; interval: 1400; onTriggered: root.moodFlash = "" }

    // ── The system prompt ───────────────────────────────────────────────────
    readonly property string systemPrompt:
        "You are Mo AI, the built-in assistant of MoOS — a premium Arabic/English " +
        "(RTL) Linux desktop by Moalfarras, with atomic updates (bootc/OSTree) " +
        "and a KDE Plasma 6 desktop. You are not a chat box beside the system; " +
        "you ARE its repair, update, cleanup and setup centre.\n\n" +
        "WHAT YOU CAN DO — put the EXACT command in a fenced code block and the app " +
        "turns it into a one-click Run button (it still asks the user to confirm and " +
        "still prompts for a password where one is needed):\n" +
        "• Repair & maintain: `moai-do update` (atomic system update), `moai-do " +
        "fix-audio`, `moai-do check-drivers`, `moai-do optimize` (clean + speed up), " +
        "`moai-do diagnose-services`, `moai-do inspect-boot`, `moai-do hw-report`.\n" +
        "• Drivers & firmware: `moai-do install-nvidia` (atomically switch to the MoOS " +
        "NVIDIA edition — applies on reboot, the previous system is kept for " +
        "rollback), `moai-do update-firmware` (device firmware via fwupd).\n" +
        "• Install ANY app: `moai-do install <flatpak-id>` — e.g. `moai-do install " +
        "org.blender.Blender`. It DOWNLOADS the app AND OPENS it when done, so a " +
        "request like “install a camera” ends with the camera on screen. Prefer " +
        "Flatpaks over layering rpm-ostree packages, and prefer apps built for KDE " +
        "Plasma / Wayland — an app made for another desktop can install fine and then " +
        "crash on launch. For a CAMERA use `org.gnome.Snapshot` (verified live here: it " +
        "reaches the webcam through the XDG camera portal). NEVER `io.github.cosmic_utils" +
        ".camera` — a COSMIC-desktop app that panics on KDE — and NOT `org.kde.kamoso`: " +
        "it is KDE's own, and it still segfaults in GStreamer a few seconds after it " +
        "opens. If you are not certain of an app id, tell the user to search it in " +
        "the Apps panel rather than guessing one.\n" +
        "• Run apps from OTHER systems, for real:\n" +
        "   – DOUBLE-CLICK IS ENOUGH. A downloaded .exe or .apk runs when the user opens " +
        "it in Files: MoOS hands it to the right layer, and if that layer is not installed " +
        "yet it offers the one-time setup right there. Say that FIRST — the setup commands " +
        "below are for someone who wants to prepare the machine in advance.\n" +
        "   – Windows programs: `moai-do setup-windows` installs Bottles (managed Wine) " +
        "and opens it, so any .exe runs. For games use `moai-do setup-gaming` (Steam + " +
        "Proton + Lutris); `moai-do install net.lutris.Lutris` manages both.\n" +
        "   – Android apps: `moai-do setup-waydroid` boots a real Android container " +
        "(idempotent — safe to re-run); afterwards Android apps appear in the launcher " +
        "like any other app, and an APK installs by double-clicking it (or " +
        "`waydroid app install <file>`).\n" +
        "• Coding agents, and ONE OF THEM NEEDS NO ACCOUNT: `moai-do install-opencode` " +
        "installs OpenCode wired to THIS MACHINE'S OWN brain — it codes with no cloud, no " +
        "login and no internet, and MoOS writes its provider config for the user. Recommend " +
        "it FIRST to anyone who has no AI subscription. The other two are cloud agents and " +
        "each needs its vendor account: `moai-do install-codex`, `moai-do install-claude` — they " +
        "install into ~/.local and run as the user, with no admin rights.\n" +
        "• Diagnose: explain the likely cause in plain language, then give the " +
        "SMALLEST safe repair.\n\n" +
        "WHICH BRAIN YOU ARE: the user picks it per conversation, from the chip next " +
        "to the message box — a LOCAL model that runs on this machine and never " +
        "leaves it, or a CLOUD model through their own API key. If they ask how to " +
        "change model or make you stronger/more private, point them at that chip; " +
        "the provider and the key live behind it, in Settings.\n\n" +
        "HOW TO BEHAVE: understand the goal → briefly diagnose → propose the smallest " +
        "safe action → show the exact command → one line on what it does. Always " +
        "confirm before anything that updates, installs, removes, reboots or rolls " +
        "back. NEVER suggest a destructive command, a raw root shell, or a way around " +
        "a confirmation. If you are offline or unsure, say so plainly.\n" +
        "STYLE: concise and friendly, in the user's language (العربية RTL or English), " +
        "short bullets, code blocks for commands."

    // Every bilingual message below is written as ONE PARAGRAPH PER LANGUAGE, and each
    // paragraph is stamped with its own directional mark (‏ = RLM, ‎ = LRM).
    //
    // Both halves of that are load-bearing, and the greeting — the first thing a new user
    // reads — proved it. These are Markdown, and in Markdown a single "\n" is a soft wrap,
    // not a paragraph break: the Arabic sentence and the English one merged into a single
    // bidi paragraph, whose base direction comes from its first strong character (Arabic).
    // So the English sentence was laid out right-to-left and its full stop jumped to the
    // front — the user's first impression of MoOS's assistant was ".the system, install any
    // app, clean things up, and run Mo PC Remote". A blank line makes each language its own
    // paragraph; the mark then pins that paragraph's direction instead of leaving it to
    // whatever character happens to come first (an English line that opens with "Mo AI"
    // would still resolve fine, but one that opens with a digit or "«" would not).
    readonly property string offlineHelp: (Qt.application.layoutDirection === Qt.RightToLeft)
        ? ("‏العقل المحلي غير مشغّل.\n\n" +
           "اضغط **«شغّل العقل المحلي»** بالأسفل — أو شغّل `moai-start` في الطرفية.\n\n" +
           "ثم أعد المحاولة.")
        : ("‎The local brain is off.\n\n" +
           "Tap **“Start local brain”** below — or run `moai-start` in a terminal.\n\n" +
           "Then try again.")

    readonly property string startingHelp: (Qt.application.layoutDirection === Qt.RightToLeft)
        ? ("‏العقل المحلي يبدأ الآن… أول تشغيل يُحمّل النموذج (~2.5GB) وقد يأخذ دقائق.\n\n" +
           "سأصبح جاهزاً تلقائياً عند الانتهاء.")
        : ("‎The local brain is starting… the first run downloads the model (~2.5 GB) and may take a few minutes.\n\n" +
           "I'll be ready automatically once it finishes.")

    // MoOS speaks the user's ONE language. The greeting used to stack Arabic and
    // English; now it shows only the session language (RTL ⇒ Arabic), the same
    // signal the whole app mirrors on. The model still replies in whatever
    // language the user writes in — that is per-message, not the static greeting.
    readonly property bool moaiRtl: Qt.application.layoutDirection === Qt.RightToLeft
    readonly property string greetingText: moaiRtl
        ? ("‏مرحباً! أنا **Mo AI** — مساعد MoOS.\n\n" +
           "أقدر أصلّح التعريفات، أحدّث النظام، أثبّت أي تطبيق، أنظّف الجهاز، وأشغّل Mo PC Remote.\n\n" +
           "_اسألني، أو استخدم الشريط الجانبي._")
        : ("‎Hi! I'm **Mo AI** — your MoOS assistant.\n\n" +
           "I can fix drivers, update the system, install any app, clean things up, and run Mo PC Remote.\n\n" +
           "_Ask me, or use the side rail._")

    readonly property var starters: [
        { ar: "حدّث نظامي",     en: "Update my system", send: "حدّث نظام MoOS من فضلك" },
        { ar: "افحص جهازي",     en: "Check my device",  send: "افحص جهازي وقل لي إذا في مشاكل تعريفات أو تحديثات" },
        { ar: "سرّع ونظّف",      en: "Speed up & clean", send: "نظّف النظام وسرّعه من فضلك" },
        { ar: "صلّح الصوت",      en: "Fix audio",        send: "الصوت لا يعمل عندي، ساعدني" }
    ]

    // ── The rail ────────────────────────────────────────────────────────────
    readonly property var navItems: [
        { id: "chat",   icon: "moos-ai",           ar: "المحادثة", en: "Chat" },
        { id: "device", icon: "moos-gpu",          ar: "الجهاز",   en: "Device" },
        { id: "apps",   icon: "moos-install",      ar: "التطبيقات", en: "Apps" },
        { id: "compat", icon: "moos-gaming",       ar: "التوافق",  en: "Compat" },
        { id: "remote", icon: "moos-phone",        ar: "التحكّم",   en: "Remote" },
        { id: "dev",    icon: "utilities-terminal", ar: "المطوّر",  en: "Dev" }
    ]

    // Compatibility targets. `key` matches moai-control's /scan compatibility
    // map, so "Ready" is read from the machine, never assumed.
    readonly property var compatCatalog: [
        { key: "steam",      title: "Steam + Proton", ar: "ألعاب Windows", en: "Windows games",
          url: "moos://do/setup-gaming", icon: "moos-gaming" },
        { key: "bottles",    title: "Bottles", ar: "تطبيقات Windows", en: "Windows apps",
          url: "moos://do/setup-windows", icon: "moos-system" },
        { key: "waydroid",   title: "Waydroid", ar: "تطبيقات Android", en: "Android apps",
          url: "moos://do/setup-waydroid", icon: "moos-android-apps" },
        { key: "kdeconnect", title: "KDE Connect", ar: "ربط الهاتف", en: "Phone integration",
          url: "moos://apps/install/org.kde.kdeconnect", icon: "moos-phone" }
    ]

    // Pin every paragraph's direction to its OWN language.
    //
    // The greeting above can be written correctly by hand; a model's reply cannot. Mo AI is
    // asked questions in Arabic and answers with English identifiers, paths and commands in
    // the middle of Arabic sentences — and Qt hands the whole Text one base direction, taken
    // from the first strong character it finds. One Arabic word at the top drags every
    // English line right-to-left and throws its punctuation to the front of the sentence.
    //
    // So stamp each paragraph with the mark its own first strong character calls for. What it
    // must NOT do is break the Markdown: a mark inserted before "#" or "-" or "```" stops
    // that line from being a heading, a bullet or a fence. Hence the skip-list — lines that
    // start with Markdown syntax are left exactly as they are (their content is nearly always
    // code or identifiers anyway, which are LTR by nature).
    function bidiFix(s) {
        if (!s)
            return s
        const arabic = /[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]/
        const latin = /[A-Za-z]/
        // Lines that OPEN with Markdown syntax are left alone — a mark in front of "#", "-",
        // "```" or "_" stops that line from being a heading, a bullet, a fence or an emphasis
        // run, and prints the syntax as literal text (seen on screen with the greeting's
        // italic line).
        const markdown = /^\s*(#{1,6}\s|[-*+]\s|\d+\.\s|>|```|\||[_*]|\s*$)/
        return s.split("\n").map(function (line) {
            if (markdown.test(line) || line.charAt(0) === "‎" || line.charAt(0) === "‏")
                return line
            const ar = line.search(arabic)
            const la = line.search(latin)
            if (ar < 0 && la < 0)
                return line
            const rtl = ar >= 0 && (la < 0 || ar < la)
            return (rtl ? "‏" : "‎") + line
        }).join("\n")
    }

    // The apps we recommend. Anything else is found by searching Flathub.
    readonly property var appCatalog: [
        { id: "io.github.kolunmi.Bazaar", title: "App Center (Bazaar)", ar: "تصفّح كل التطبيقات", en: "Browse everything" },
        { id: "org.mozilla.firefox",      title: "Firefox",     ar: "متصفح ويب",      en: "Web browser" },
        { id: "org.videolan.VLC",         title: "VLC",         ar: "مشغل وسائط",     en: "Media player" },
        { id: "org.libreoffice.LibreOffice", title: "LibreOffice", ar: "حزمة مكتبية", en: "Office suite" },
        { id: "org.gnome.Snapshot",       title: "Camera",      ar: "الكاميرا",       en: "Camera" },
        { id: "com.github.tchx84.Flatseal", title: "Flatseal",  ar: "صلاحيات التطبيقات", en: "App permissions" }
    ]

    ListModel { id: chatModel }
    ListModel { id: searchModel }
    property bool searching: false
    property string searchNote: ""

    // ── Startup ─────────────────────────────────────────────────────────────
    Component.onCompleted: {
        chatModel.append({ role: "assistant", text: greetingText })
        refreshScan()
        loadModels()
        // Open straight onto a panel. This is how the old centres survive as
        // commands: moos-hardware runs `moai --panel device`, moos-compat runs
        // `moai --panel compat`. `--device` is kept as an alias.
        const argv = Qt.application.arguments
        if (argv.indexOf("--device") !== -1) {
            root.panel = "device"
        } else {
            const i = argv.indexOf("--panel")
            if (i !== -1 && i + 1 < argv.length) {
                const p = argv[i + 1]
                if (["chat", "device", "apps", "compat", "remote", "dev"].indexOf(p) !== -1)
                    root.panel = p
            }
        }
    }

    // Cheap poll: brain + remote + agents. moai-control serves this without
    // touching the device plan, so it is safe at this interval.
    Timer {
        interval: 4000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            const xhr = new XMLHttpRequest()
            xhr.open("GET", root.controlApi + "/quick")
            xhr.setRequestHeader("X-Moai-Control", "1")
            xhr.onreadystatechange = function () {
                if (xhr.readyState !== XMLHttpRequest.DONE)
                    return
                if (xhr.status !== 200) {
                    root.brains = {}
                    root.defaultOnline = false
                    return
                }
                try {
                    const q = JSON.parse(xhr.responseText)
                    root.brains = q.brains || {}
                    root.brainsKnown = true
                    root.defaultOnline = !!q.online
                    if (root.serverUp)
                        root.brainStarting = false
                    // Merge the live bits into the snapshot so the Remote and
                    // Developer panels update without a full rescan.
                    const s = root.snap || {}
                    s.remote = q.remote || {}
                    s.agents = q.agents || {}
                    root.snap = s
                    root.snapChanged()
                } catch (e) {}
            }
            xhr.send()
        }
    }

    // The full scan is heavier (it carries the cached device plan), so it runs
    // on a slow beat and on demand.
    Timer {
        interval: 180000
        running: true
        repeat: true
        onTriggered: root.refreshScan()
    }

    function refreshScan() {
        root.scanning = true
        const xhr = new XMLHttpRequest()
        xhr.open("GET", controlApi + "/scan")
        xhr.setRequestHeader("X-Moai-Control", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            root.scanning = false
            if (xhr.status !== 200)
                return
            try {
                const s = JSON.parse(xhr.responseText)
                root.snap = s
                root.plan = s.device_plan || {}
                root.machineContext = root.buildContext(s)
            } catch (e) { /* keep the last good snapshot, not a half-parsed one */ }
        }
        xhr.send()
    }

    // What the model is told about this machine, on every request. Without it,
    // Mo AI is a chat box that has to be TOLD what hardware it is on; with it,
    // it opens already knowing this machine has an NVIDIA card on nouveau, and
    // can say so first. Facts and allowed action ids only — naming an action
    // does not grant the power to run it.
    function buildContext(s) {
        const p = s.device_plan || {}
        let c = "\n\nTHIS MACHINE (live, read-only — do not ask the user for it):\n"
        c += "• " + (s.os || "MoOS") + ", kernel " + (s.kernel || "?")
           + ", " + (s.mem_gb || "?") + " GB RAM, " + (s.cores || "?") + " cores\n"
        if (s.cpu) c += "• CPU: " + s.cpu + "\n"
        if (p.gpu) c += "• GPU: " + String(p.gpu).split("\n")[0] + "\n"
        if (p.driver_status) c += "• Graphics driver: " + p.driver_status + "\n"
        if (p.driver_gaps && p.driver_gaps.length)
            c += "• Devices with NO driver bound: " + p.driver_gaps.join("; ") + "\n"
        if (p.missing_firmware && p.missing_firmware.length)
            c += "• Firmware the kernel could not load: " + p.missing_firmware.join(", ") + "\n"
        if (p.firmware_updates && p.firmware_updates.length)
            c += "• Pending firmware updates: " + p.firmware_updates.join("; ") + "\n"
        const r = s.remote || {}
        c += "• Mo PC Remote: " + (r.active ? "running" : "stopped") + "\n"
        const a = s.agents || {}
        c += "• Coding agents installed: codex=" + (a.codex ? "yes" : "no")
           + ", claude=" + (a.claude ? "yes" : "no") + "\n"
        const acts = p.actions || []
        if (acts.length) {
            c += "• Repairs available right now (each maps to an allowed action):\n"
            for (let i = 0; i < acts.length; i++) {
                const act = acts[i]
                const cmd = act.url ? String(act.url).replace("moos://do/", "moai-do ") : ""
                c += "   - [" + act.severity + "] " + act.title
                   + (cmd ? "  ->  `" + cmd + "`" : "") + "\n"
            }
            c += "If something above is broken, say so first and offer the exact action.\n"
        } else {
            c += "• No hardware or driver problems detected.\n"
        }
        c += "Never invent hardware facts that are not in this list.\n"
        return c
    }

    // ── Actions ─────────────────────────────────────────────────────────────
    function launch(url, label) {
        Qt.openUrlExternally(url)
        toast.show(label || url)
        orbPulse.restart()
    }

    function startBrain() {
        Qt.openUrlExternally("moos://brain/start")
        brainStarting = true
        brainStartGuard.restart()
    }
    Timer { id: brainStartGuard; interval: 720000; onTriggered: root.brainStarting = false }

    function askAbout(title, detail) {
        root.panel = "chat"
        input.text = "اشرح لي هذه المشكلة وكيف أصلحها: " + title + " — " + detail
                   + "\nExplain this problem and how to fix it."
        input.forceActiveFocus()
    }

    // Search Flathub through moai-control (which falls back to the local
    // appstream index when offline). Searching is read-only; INSTALLING hands
    // the id to moos://apps/install/<id> -> moai-do install, which validates it
    // again and asks for confirmation. The two never share a code path.
    function searchApps(q) {
        const query = (q || "").trim()
        if (query === "") {
            searchModel.clear()
            root.searchNote = ""
            return
        }
        root.searching = true
        root.searchNote = ""
        const xhr = new XMLHttpRequest()
        xhr.open("GET", controlApi + "/search?q=" + encodeURIComponent(query))
        xhr.setRequestHeader("X-Moai-Control", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            root.searching = false
            searchModel.clear()
            if (xhr.status !== 200) {
                root.searchNote = "تعذّر البحث | search failed"
                return
            }
            try {
                const r = JSON.parse(xhr.responseText)
                const list = r.results || []
                for (let i = 0; i < list.length; i++)
                    searchModel.append(list[i])
                if (list.length === 0)
                    root.searchNote = "لا نتائج | no results"
                else if (r.source === "local")
                    root.searchNote = "بدون إنترنت — نتائج محلية | offline — local results"
            } catch (e) {
                root.searchNote = "تعذّر قراءة النتائج | couldn't read results"
            }
        }
        xhr.send()
    }

    // The moai-do actions the model named in its last reply, surfaced as Run
    // chips. Only ids from the fixed allowlist are matched — a command the model
    // invents does not become a button.
    //
    // This list must cover every action the systemPrompt above tells the model it may
    // name. It did not: the prompt promises "put the EXACT command in a fenced code
    // block and the app turns it into a one-click Run button", then offers
    // setup-gaming, setup-windows and install-opencode — three ids this regex did not
    // match. Each one is implemented in moai-do and routed in moos-open; only the
    // regex was missing, so the model would answer "run `moai-do setup-gaming`", the
    // code block would render, and no button would ever appear. The user is left
    // reading a command they were told they would not have to type — the same dead
    // promise as the eleven dead buttons in AGENTS.md, one layer up.
    // tests/verify_user_experience.py now compares this list against the prompt.
    function extractRuns(text) {
        const out = []
        const re = /moai-do\s+(update|fix-audio|check-drivers|optimize|hw-report|diagnose-services|inspect-boot|update-firmware|install-nvidia|setup-waydroid|setup-gaming|setup-windows|install-codex|install-claude|install-opencode)\b/g
        let m
        while ((m = re.exec(text)) !== null)
            if (out.indexOf(m[1]) === -1)
                out.push(m[1])
        return out
    }

    function newChat() {
        chatModel.clear()
        history = []
        pendingRuns = []
        stopGenerating()
        chatModel.append({ role: "assistant", text: greetingText })
    }

    function trimHistory() {
        if (history.length > 12)
            history = history.slice(-12)
    }

    function stopGenerating() {
        if (activeXhr) {
            try { activeXhr.abort() } catch (e) {}
            activeXhr = null
        }
        busy = false
    }

    function sendPrompt(msg) {
        root.panel = "chat"
        input.text = msg
        send()
    }

    function send() {
        const msg = input.text.trim()
        if (msg === "" || busy)
            return
        root.panel = "chat"
        input.text = ""
        chatModel.append({ role: "user", text: msg })
        history.push({ role: "user", content: msg })
        trimHistory()
        chatModel.append({ role: "typing", text: "…" })
        const idx = chatModel.count - 1
        busy = true
        pendingRuns = []

        let acc = ""
        let sawData = false
        let processed = 0

        const xhr = new XMLHttpRequest()
        activeXhr = xhr
        xhr.open("POST", api)
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            // Parse newly-arrived SSE lines during LOADING (live) and at DONE.
            if (xhr.readyState === XMLHttpRequest.LOADING
                    || xhr.readyState === XMLHttpRequest.DONE) {
                const full = xhr.responseText
                // Consume only COMPLETE lines: a `data:` line can split across
                // two ticks, so keep a trailing partial buffered until its
                // newline arrives. At DONE, consume the remainder too.
                let end = full.lastIndexOf("\n") + 1
                if (xhr.readyState === XMLHttpRequest.DONE)
                    end = full.length
                const fresh = end > processed ? full.substring(processed, end) : ""
                processed = end > processed ? end : processed
                const lines = fresh.split("\n")
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i].trim()
                    if (line.indexOf("data:") !== 0)
                        continue
                    const payload = line.substring(5).trim()
                    if (payload === "" || payload === "[DONE]")
                        continue
                    try {
                        const j = JSON.parse(payload)
                        const ch = j.choices && j.choices[0]
                        const delta = ch
                            ? (ch.delta ? ch.delta.content
                               : (ch.message ? ch.message.content : ""))
                            : ""
                        if (delta) {
                            acc += delta
                            sawData = true
                            chatModel.set(idx, { role: "assistant", text: acc })
                        }
                    } catch (e) { /* partial JSON — completes next tick */ }
                }
            }
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            root.busy = false
            root.activeXhr = null

            if (sawData && acc.trim() !== "") {
                chatModel.set(idx, { role: "assistant", text: acc })
                root.history.push({ role: "assistant", content: acc })
                root.trimHistory()
                root.pendingRuns = root.extractRuns(acc)
                root.flashMood("success")
                return
            }
            // No stream (older server or an error) — try a whole-response parse.
            let reply = ""
            if (xhr.status === 200) {
                try {
                    reply = JSON.parse(xhr.responseText).choices[0].message.content.trim()
                } catch (e) { reply = "" }
            }
            if (reply !== "") {
                chatModel.set(idx, { role: "assistant", text: reply })
                root.history.push({ role: "assistant", content: reply })
                root.trimHistory()
                root.pendingRuns = root.extractRuns(reply)
                root.flashMood("success")
            } else {
                const help = !root.serverUp
                    ? (root.brainStarting ? root.startingHelp : root.offlineHelp)
                    : "لم أستطع توليد رد، حاول مجدداً. | I couldn't generate a reply — please try again."
                chatModel.set(idx, { role: "assistant", text: help })
                root.flashMood(root.serverUp ? "warning" : "error")
            }
        }
        xhr.send(JSON.stringify({
            // THE ROUTE. moai-gateway reads this and sends the request to the
            // local brain or to the cloud provider accordingly; "default" (or an
            // empty route, before /models has answered) means "whatever
            // ~/.config/moai/config.json says", which is the old behaviour.
            model: root.route !== "" ? root.route : "default",
            messages: [{ role: "system", content: systemPrompt + root.machineContext }]
                          .concat(history),
            stream: true
        }))
    }

    // ── The brain picker ────────────────────────────────────────────────────
    // The real models this machine can reach: the local ones RamaLama has pulled,
    // and the ones the CONFIGURED PROVIDER says it serves — asked for by
    // moai-control, never guessed at here. There is no tier table in this app,
    // because there is no way to know what a private endpoint offers except to
    // ask it.
    function loadModels() {
        if (root.modelsLoading)
            return
        root.modelsLoading = true
        const xhr = new XMLHttpRequest()
        xhr.open("GET", controlApi + "/models")
        xhr.setRequestHeader("X-Moai-Control", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            root.modelsLoading = false
            if (xhr.status !== 200) {
                root.modelsError = "تعذّر جلب النماذج | couldn't reach the model list"
                return
            }
            try {
                const m = JSON.parse(xhr.responseText)
                root.localModels = m.local || []
                root.cloudModels = m.cloud || []
                root.modelsError = m.cloud_error || ""
                root.defaultRoute = m.default || ""
                // Start on the configured default; the user's pick then sticks
                // for the rest of the session.
                if (root.route === "" && root.defaultRoute !== "")
                    root.route = root.defaultRoute
            } catch (e) {
                root.modelsError = "تعذّر قراءة النماذج | couldn't read the model list"
            }
        }
        xhr.send()
    }

    function openPicker() {
        root.pickerOpen = true
        root.loadModels()
    }

    function pickRoute(id) {
        root.route = id
        root.pickerOpen = false
        root.flashMood("attentive")
    }

    // ═══════════════════════════════════════════════════════════════════════
    //  Reusable pieces
    // ═══════════════════════════════════════════════════════════════════════

    // The Nova orb. Drawn with QtQuick.Shapes: a conical-gradient annulus that
    // turns, a soft radial halo, and a core that breathes.
    //
    // No MultiEffect blur on purpose. This machine's GPU memory is mostly held
    // by the local model (llama-server sits at ~6 of 8 GB), and an offscreen
    // render target for a 44 px icon is not a trade worth making. A radial
    // gradient costs nothing and reads the same.
    component MoOrb: Item {
        id: orb
        property string mood: "idle"
        property real ringAngle: 0
        property real coreScale: 1.0
        property real haloScale: 1.0

        readonly property bool alive: mood !== "offline"
        readonly property color accent:
              mood === "success" ? root.okColor
            : mood === "warning" ? root.warnColor
            : mood === "error"   ? root.badColor
            : mood === "offline" ? root.textMute
            : root.novaBlue

        implicitWidth: 44
        implicitHeight: 44

        // Halo
        Shape {
            anchors.centerIn: parent
            width: orb.width * 1.75
            height: orb.height * 1.75
            scale: orb.haloScale
            opacity: orb.alive ? 0.5 : 0.16
            Behavior on opacity { NumberAnimation { duration: 260 } }
            ShapePath {
                strokeWidth: -1
                fillGradient: RadialGradient {
                    centerX: orb.width * 0.875; centerY: orb.height * 0.875
                    centerRadius: orb.width * 0.875
                    focalX: centerX; focalY: centerY
                    GradientStop { position: 0.55; color: Qt.rgba(orb.accent.r, orb.accent.g, orb.accent.b, 0.42) }
                    GradientStop { position: 1.00; color: Qt.rgba(orb.accent.r, orb.accent.g, orb.accent.b, 0.0) }
                }
                PathAngleArc {
                    centerX: orb.width * 0.875; centerY: orb.height * 0.875
                    radiusX: orb.width * 0.875; radiusY: orb.height * 0.875
                    startAngle: 0; sweepAngle: 360
                }
            }
        }

        // The turning ring — an annulus (odd-even fill) with a conical gradient.
        Shape {
            id: ring
            anchors.fill: parent
            scale: orb.coreScale
            opacity: orb.alive ? 1.0 : 0.42
            Behavior on opacity { NumberAnimation { duration: 260 } }
            ShapePath {
                fillRule: ShapePath.OddEvenFill
                strokeWidth: -1
                fillGradient: ConicalGradient {
                    centerX: orb.width / 2; centerY: orb.height / 2
                    angle: orb.ringAngle
                    GradientStop { position: 0.00; color: orb.alive ? root.novaCyan : root.hairline }
                    GradientStop { position: 0.34; color: orb.alive ? root.novaBlue : root.textMute }
                    GradientStop { position: 0.67; color: orb.alive ? root.novaViolet : root.surface3 }
                    GradientStop { position: 1.00; color: orb.alive ? root.novaCyan : root.hairline }
                }
                PathAngleArc {
                    moveToStart: true
                    centerX: orb.width / 2; centerY: orb.height / 2
                    radiusX: orb.width / 2; radiusY: orb.height / 2
                    startAngle: 0; sweepAngle: 360
                }
                PathAngleArc {
                    moveToStart: true
                    centerX: orb.width / 2; centerY: orb.height / 2
                    radiusX: orb.width * 0.335; radiusY: orb.height * 0.335
                    startAngle: 0; sweepAngle: 360
                }
            }
        }

        // The core, and the spark that says which mood we are in.
        Rectangle {
            anchors.centerIn: parent
            width: orb.width * 0.63
            height: width
            radius: width / 2
            scale: orb.coreScale
            gradient: Gradient {
                GradientStop { position: 0.0; color: root.surface2 }
                GradientStop { position: 1.0; color: root.surface0 }
            }

            Rectangle {
                anchors.centerIn: parent
                width: parent.width * (orb.mood === "thinking" ? 0.30 : 0.24)
                height: width
                radius: width / 2
                color: orb.accent
                opacity: orb.alive ? 1.0 : 0.55
                Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
                Behavior on color { ColorAnimation { duration: 240 } }
            }
        }

        // Idle: a slow breath.
        SequentialAnimation {
            running: root.visible && orb.mood === "idle" && !orbPulse.running
            loops: Animation.Infinite
            onStopped: { orb.coreScale = 1.0; orb.haloScale = 1.0 }
            ParallelAnimation {
                NumberAnimation { target: orb; property: "coreScale"; to: 1.03; duration: 1500; easing.type: Easing.InOutSine }
                NumberAnimation { target: orb; property: "haloScale"; to: 1.10; duration: 1500; easing.type: Easing.InOutSine }
            }
            ParallelAnimation {
                NumberAnimation { target: orb; property: "coreScale"; to: 1.0; duration: 1500; easing.type: Easing.InOutSine }
                NumberAnimation { target: orb; property: "haloScale"; to: 1.0; duration: 1500; easing.type: Easing.InOutSine }
            }
        }

        // Thinking: the ring turns and the halo throbs.
        NumberAnimation {
            running: root.visible && orb.mood === "thinking"
            target: orb; property: "ringAngle"
            from: 0; to: 360; duration: 2600
            loops: Animation.Infinite
            onStopped: orb.ringAngle = 0
        }
        SequentialAnimation {
            running: root.visible && orb.mood === "thinking"
            loops: Animation.Infinite
            onStopped: orb.haloScale = 1.0
            NumberAnimation { target: orb; property: "haloScale"; to: 1.16; duration: 620; easing.type: Easing.InOutSine }
            NumberAnimation { target: orb; property: "haloScale"; to: 0.98; duration: 620; easing.type: Easing.InOutSine }
        }

        // Attentive: leans in and holds.
        NumberAnimation {
            running: root.visible && orb.mood === "attentive"
            target: orb; property: "coreScale"
            to: 1.07; duration: 220; easing.type: Easing.OutBack
            onStopped: if (orb.mood !== "attentive") orb.coreScale = 1.0
        }

        // An honest pulse when the user launches something: launching is not
        // the same as succeeding, so this says "heard you", not "done".
        SequentialAnimation {
            id: orbPulse
            NumberAnimation { target: orb; property: "coreScale"; from: 1.0; to: 1.13; duration: 140; easing.type: Easing.OutQuad }
            NumberAnimation { target: orb; property: "coreScale"; to: 1.0; duration: 240; easing.type: Easing.InQuad }
        }
    }

    // A card.
    component Card: Rectangle {
        default property alias content: inner.data
        property alias pad: inner.anchors.margins
        radius: 14
        color: root.surface1
        border.width: 1
        border.color: root.hairline
        implicitHeight: inner.childrenRect.height + 2 * inner.anchors.margins
        Item {
            id: inner
            anchors.fill: parent
            anchors.margins: 14
        }
    }

    // The one button style in the app.
    component MoButton: Rectangle {
        id: btn
        property string label: ""
        property string icon: ""
        property bool primary: false
        property bool danger: false
        property bool enabled_: true
        signal clicked()

        readonly property color base:
              !enabled_ ? root.surface2
            : danger ? root.badColor
            : primary ? root.novaBlue
            : root.surface2

        implicitHeight: 34
        implicitWidth: row.implicitWidth + 26
        radius: 10
        color: !enabled_ ? base
             : ma.pressed ? Qt.darker(base, 1.12)
             : ma.containsMouse ? Qt.lighter(base, 1.16)
             : base
        border.width: 1
        border.color: primary || danger ? "transparent"
                    : ma.containsMouse ? root.novaBlue : root.hairline
        opacity: enabled_ ? 1.0 : 0.45
        Behavior on color { ColorAnimation { duration: 120 } }

        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: 7
            Kirigami.Icon {
                visible: btn.icon !== ""
                source: btn.icon
                color: btn.primary || btn.danger ? root.onAccent : root.textLo
                Layout.preferredWidth: 15
                Layout.preferredHeight: 15
            }
            Text {
                text: btn.label
                color: btn.primary || btn.danger ? root.onAccent : root.textHi
                font.family: root.uiFont
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }
        }
        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            enabled: btn.enabled_
            cursorShape: Qt.PointingHandCursor
            onClicked: btn.clicked()
        }
    }

    // A status pill: reads state from the machine, never asserts it.
    component StatusPill: Rectangle {
        property bool good: false
        property string goodText: ""
        property string badText: ""
        implicitHeight: 22
        implicitWidth: pillText.implicitWidth + 20
        radius: 11
        color: good
            ? Qt.rgba(root.okColor.r, root.okColor.g, root.okColor.b, 0.14)
            : Qt.rgba(root.textMute.r, root.textMute.g, root.textMute.b, 0.10)
        border.width: 1
        border.color: good
            ? Qt.rgba(root.okColor.r, root.okColor.g, root.okColor.b, 0.45)
            : root.hairline
        Text {
            id: pillText
            anchors.centerIn: parent
            text: parent.good ? parent.goodText : parent.badText
            color: parent.good ? root.okColor : root.textMute
            font.family: root.uiFont
            font.pixelSize: 11
            font.weight: Font.DemiBold
        }
    }

    component SectionTitle: Text {
        color: root.textHi
        font.family: root.uiFont
        font.pixelSize: 17
        font.weight: Font.DemiBold
    }

    component SectionNote: Text {
        color: root.textLo
        font.family: root.uiFont
        font.pixelSize: 12
        wrapMode: Text.Wrap
    }

    // ═══════════════════════════════════════════════════════════════════════
    //  The window
    // ═══════════════════════════════════════════════════════════════════════
    pageStack.initialPage: Kirigami.Page {
        id: page
        padding: 0

        // Painted, not photographed. The old build loaded a 3840×2160 wallpaper
        // PNG and scaled it into a 460 px window — a 4K decode and its memory on
        // every launch, for a texture nobody could see at 18% opacity. Two
        // gradients cost nothing and look better.
        background: Rectangle {
            gradient: Gradient {
                GradientStop { position: 0.0; color: root.chrome }
                GradientStop { position: 0.55; color: root.surface0 }
                GradientStop { position: 1.0; color: root.surface0 }
            }
            Shape {
                anchors.right: parent.right
                anchors.top: parent.top
                width: 520; height: 520
                opacity: 0.16
                ShapePath {
                    strokeWidth: -1
                    fillGradient: RadialGradient {
                        centerX: 380; centerY: 90; centerRadius: 340
                        focalX: centerX; focalY: centerY
                        GradientStop { position: 0.0; color: root.novaBlue }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                    PathAngleArc {
                        centerX: 380; centerY: 90; radiusX: 340; radiusY: 340
                        startAngle: 0; sweepAngle: 360
                    }
                }
            }
        }

        // Full RTL mirroring for Arabic sessions; cascades to every child.
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true

        RowLayout {
            anchors.fill: parent
            spacing: 0

            // ── The rail ────────────────────────────────────────────────────
            Rectangle {
                Layout.preferredWidth: 76
                Layout.fillHeight: true
                color: root.chrome

                Rectangle {
                    anchors.right: parent.right
                    width: 1; height: parent.height
                    color: root.hairline
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.topMargin: 14
                    anchors.bottomMargin: 12
                    spacing: 4

                    MoOrb {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 42
                        Layout.preferredHeight: 42
                        Layout.bottomMargin: 4
                        mood: root.mood
                    }

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.bottomMargin: 8
                        text: root.serverUp ? "متصل" : root.brainStarting ? "يبدأ…" : "غير متصل"
                        color: root.serverUp ? root.okColor
                             : root.brainStarting ? root.novaBlue : root.textMute
                        font.family: root.uiFont
                        font.pixelSize: 9
                        font.weight: Font.DemiBold
                    }

                    Repeater {
                        model: root.navItems
                        delegate: Item {
                            id: nav
                            required property var modelData
                            readonly property bool active: root.panel === modelData.id
                            Layout.fillWidth: true
                            Layout.preferredHeight: 54

                            Rectangle {   // active indicator
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                width: 3
                                height: nav.active ? 26 : 0
                                radius: 2
                                color: root.novaCyan
                                Behavior on height { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                            }

                            Rectangle {
                                anchors.centerIn: parent
                                width: 54; height: 46
                                radius: 12
                                color: nav.active
                                     ? Qt.rgba(root.novaBlue.r, root.novaBlue.g,
                                               root.novaBlue.b, 0.16)
                                     : navMa.containsMouse ? root.surface2 : "transparent"
                                Behavior on color { ColorAnimation { duration: 130 } }

                                ColumnLayout {
                                    anchors.centerIn: parent
                                    spacing: 3
                                    Kirigami.Icon {
                                        Layout.alignment: Qt.AlignHCenter
                                        Layout.preferredWidth: 20
                                        Layout.preferredHeight: 20
                                        source: nav.modelData.icon
                                        color: nav.active ? root.novaCyan : root.textMute
                                    }
                                    Text {
                                        Layout.alignment: Qt.AlignHCenter
                                        text: nav.modelData.ar
                                        color: nav.active ? root.textHi : root.textMute
                                        font.family: root.uiFont
                                        font.pixelSize: 9
                                        font.weight: nav.active ? Font.DemiBold : Font.Normal
                                    }
                                }
                            }

                            // A dot on Device when the detector found something.
                            Rectangle {
                                visible: nav.modelData.id === "device" && root.problemCount > 0
                                anchors.top: parent.top
                                anchors.topMargin: 6
                                anchors.horizontalCenter: parent.horizontalCenter
                                anchors.horizontalCenterOffset: 15
                                width: 8; height: 8; radius: 4
                                color: root.hasImportant ? root.badColor : root.warnColor
                                border.width: 2
                                border.color: root.chrome
                            }

                            MouseArea {
                                id: navMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.panel = nav.modelData.id
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    // Settings
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 46
                        Rectangle {
                            anchors.centerIn: parent
                            width: 54; height: 40
                            radius: 12
                            color: gearMa.containsMouse ? root.surface2 : "transparent"
                            Behavior on color { ColorAnimation { duration: 130 } }
                            Kirigami.Icon {
                                anchors.centerIn: parent
                                width: 19; height: 19
                                source: "configure"
                                color: root.textMute
                            }
                        }
                        MouseArea {
                            id: gearMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { root.loadConfig(); root.settingsOpen = true }
                        }
                    }
                }
            }

            // ── The panel ───────────────────────────────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                // Header
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 3
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: root.novaCyan }
                        GradientStop { position: 0.5; color: root.novaBlue }
                        GradientStop { position: 1.0; color: root.novaViolet }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 56
                    color: root.chrome

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 20
                        anchors.rightMargin: 16
                        spacing: 10

                        ColumnLayout {
                            spacing: 0
                            Text {
                                text: {
                                    switch (root.panel) {
                                    case "device": return "جهازي  |  My device"
                                    case "apps":   return "التطبيقات  |  Apps"
                                    case "compat": return "التوافق  |  Compatibility"
                                    case "remote": return "Mo PC Remote"
                                    case "dev":    return "المطوّر  |  Developer"
                                    default:       return "Mo AI"
                                    }
                                }
                                color: root.textHi
                                font.family: root.uiFont
                                font.pixelSize: 16
                                font.weight: Font.DemiBold
                            }
                            Text {
                                text: {
                                    switch (root.panel) {
                                    case "device": return !root.planReady ? "جارٍ الفحص… | scanning…"
                                        : root.healthy ? "لا مشاكل | no problems"
                                        : root.problemCount + " مشكلة | issue(s)"
                                    case "apps":   return "ابحث وثبّت أي تطبيق | search and install anything"
                                    case "compat": return "Windows · Android · الألعاب"
                                    case "remote": return "تحكّم بجهازك من هاتفك | control this PC from your phone"
                                    case "dev":    return "OpenCode · Claude Code · Codex"
                                    default:       return "مساعد MoOS | MoOS assistant"
                                    }
                                }
                                color: root.textLo
                                font.family: root.uiFont
                                font.pixelSize: 11
                            }
                        }

                        Item { Layout.fillWidth: true }

                        MoButton {
                            visible: root.panel === "chat"
                            label: "محادثة جديدة | New"
                            onClicked: root.newChat()
                        }
                        MoButton {
                            visible: root.panel === "device"
                            label: root.scanning ? "جارٍ… | Scanning" : "أعد الفحص | Rescan"
                            enabled_: !root.scanning
                            icon: "moos-report"
                            onClicked: root.refreshScan()
                        }
                    }

                    Rectangle {
                        anchors.left: parent.left; anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: 1
                        color: root.hairline
                    }
                }

                // ── Panels ──────────────────────────────────────────────────
                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: {
                        const i = ["chat", "device", "apps", "compat", "remote", "dev"].indexOf(root.panel)
                        return i < 0 ? 0 : i
                    }

                    // ══ CHAT ════════════════════════════════════════════════
                    ColumnLayout {
                        spacing: 0

                        ListView {
                            id: listView
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: 4
                            topMargin: 14
                            bottomMargin: 10
                            leftMargin: 16
                            rightMargin: 16
                            model: chatModel
                            onCountChanged: Qt.callLater(listView.positionViewAtEnd)
                            QQC2.ScrollBar.vertical: QQC2.ScrollBar { }

                            delegate: Item {
                                id: msg
                                required property int index
                                required property string role
                                required property string text
                                width: ListView.view.width - 32
                                height: bubble.height + 8

                                MoOrb {
                                    visible: msg.role !== "user"
                                    anchors.left: parent.left
                                    y: 4
                                    width: 26; height: 26
                                    mood: msg.role === "typing" ? "thinking" : "idle"
                                }

                                Rectangle {
                                    id: bubble
                                    readonly property bool mine: msg.role === "user"
                                    anchors.right: mine ? parent.right : undefined
                                    anchors.left: mine ? undefined : parent.left
                                    anchors.leftMargin: mine ? 0 : 36
                                    y: 3
                                    radius: 14
                                    color: mine
                                         ? Qt.rgba(root.novaBlue.r, root.novaBlue.g,
                                                   root.novaBlue.b, 0.16)
                                         : root.surface1
                                    border.width: 1
                                    border.color: mine
                                        ? Qt.rgba(root.novaBlue.r, root.novaBlue.g,
                                                  root.novaBlue.b, 0.38)
                                        : root.hairline
                                    width: body.width + 28
                                    height: body.implicitHeight + 22

                                    Text {
                                        id: body
                                        x: 14
                                        y: 11
                                        width: Math.min(implicitWidth, (msg.width * 0.80) - 28)
                                        // Per-paragraph direction: an Arabic answer that quotes an
                                        // English command must not drag the command's punctuation to
                                        // the wrong end of the line. See root.bidiFix.
                                        text: root.bidiFix(msg.text)
                                        textFormat: msg.role === "assistant"
                                                    ? Text.MarkdownText : Text.PlainText
                                        wrapMode: Text.Wrap
                                        color: root.textHi
                                        linkColor: root.novaCyan
                                        font.family: root.uiFont
                                        font.pixelSize: 14
                                        onLinkActivated: function (link) { Qt.openUrlExternally(link) }

                                        SequentialAnimation on opacity {
                                            running: msg.role === "typing"
                                            loops: Animation.Infinite
                                            // A value-source animation does not restore on stop; when
                                            // typing → assistant flips, force full opacity so the
                                            // streamed reply is not left dimmed.
                                            onRunningChanged: if (!running) body.opacity = 1
                                            NumberAnimation { from: 1.0; to: 0.30; duration: 460 }
                                            NumberAnimation { from: 0.30; to: 1.0; duration: 460 }
                                        }
                                    }
                                }
                            }
                        }

                        // The device banner — Mo AI opens already knowing.
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            Layout.bottomMargin: 8
                            visible: root.problemCount > 0 && chatModel.count <= 1
                            radius: 12
                            implicitHeight: bannerRow.implicitHeight + 22
                            color: Qt.rgba(root.warnColor.r, root.warnColor.g,
                                           root.warnColor.b, 0.09)
                            border.width: 1
                            border.color: Qt.rgba(root.warnColor.r, root.warnColor.g,
                                                  root.warnColor.b, 0.38)

                            RowLayout {
                                id: bannerRow
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                spacing: 12

                                Kirigami.Icon {
                                    source: "moos-warning"
                                    color: root.warnColor
                                    Layout.preferredWidth: 22
                                    Layout.preferredHeight: 22
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text {
                                        text: "وجدت " + root.problemCount + " مشكلة في جهازك  |  Found " + root.problemCount + " issue(s)"
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: (root.actions[0] || {}).title || ""
                                        color: root.textLo
                                        font.family: root.uiFont
                                        font.pixelSize: 11
                                        elide: Text.ElideRight
                                    }
                                }
                                MoButton {
                                    label: "افتح | Open"
                                    primary: true
                                    onClicked: root.panel = "device"
                                }
                            }
                        }

                        // Starters — only on a fresh conversation.
                        Flow {
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            Layout.bottomMargin: 6
                            spacing: 8
                            visible: chatModel.count <= 1
                            Repeater {
                                model: root.starters
                                delegate: MoButton {
                                    required property var modelData
                                    label: modelData.ar + "  ·  " + modelData.en
                                    onClicked: root.sendPrompt(modelData.send)
                                }
                            }
                        }

                        // The chosen brain cannot answer → a real control, not a
                        // dead end. WHICH control depends on the route: a cloud
                        // route needs a provider and a key, a local route needs
                        // the model server. Offering "Start local brain" to
                        // someone whose conversation is routed to the cloud would
                        // be a button that fixes nothing.
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            Layout.bottomMargin: 8
                            visible: root.brainsKnown && !root.serverUp
                            radius: 12
                            implicitHeight: startCol.implicitHeight + 22
                            color: root.brainStarting
                                 ? Qt.rgba(root.novaBlue.r, root.novaBlue.g,
                                           root.novaBlue.b, 0.10)
                                 : root.surface1
                            border.width: 1
                            border.color: root.brainStarting ? root.novaBlue : root.novaViolet

                            ColumnLayout {
                                id: startCol
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                spacing: 9

                                Text {
                                    Layout.fillWidth: true
                                    text: !root.brains.gateway
                                        ? "بوابة Mo AI متوقفة — شغّلها:  systemctl --user start moai-gateway\nMo AI's gateway is not running — start it:  systemctl --user start moai-gateway"
                                        : root.routeIsCloud
                                        ? "العقل السحابي غير مضبوط — أضف المزوّد والمفتاح.\nThe cloud brain is not set up — add the provider and your API key."
                                        : root.brainStarting
                                        ? "العقل المحلي يبدأ… أول مرة يُحمّل ~2.5GB وقد يأخذ دقائق.\nLocal brain starting… the first run downloads ~2.5 GB."
                                        : "العقل المحلي متوقف — سأشغّله تلقائياً عند أول رسالة، أو شغّله الآن لتراه.\nThe local brain is off — I'll start it on your first message, or start it now and watch it."
                                    color: root.textLo
                                    font.family: root.uiFont
                                    font.pixelSize: 11
                                    wrapMode: Text.Wrap
                                }
                                MoButton {
                                    Layout.fillWidth: true
                                    visible: !!root.brains.gateway && !root.routeIsCloud
                                             && !root.brainStarting
                                    label: "شغّل العقل المحلي  |  Start local brain"
                                    primary: true
                                    onClicked: root.startBrain()
                                }
                                MoButton {
                                    Layout.fillWidth: true
                                    visible: !!root.brains.gateway && root.routeIsCloud
                                    label: "اضبط العقل السحابي  |  Set up the cloud brain"
                                    icon: "configure"
                                    primary: true
                                    onClicked: { root.loadConfig(); root.settingsOpen = true }
                                }
                            }
                        }

                        // Run chips for the actions the model just named.
                        Flow {
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            Layout.bottomMargin: 8
                            spacing: 8
                            visible: root.pendingRuns.length > 0
                            Repeater {
                                model: root.pendingRuns
                                delegate: MoButton {
                                    required property string modelData
                                    label: "نفّذ  moai-do " + modelData
                                    icon: "moos-safe-update"
                                    primary: true
                                    onClicked: root.launch("moos://do/" + modelData, "moai-do " + modelData)
                                }
                            }
                        }

                        // Input
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 68
                            color: root.chrome
                            Rectangle {
                                anchors.left: parent.left; anchors.right: parent.right
                                anchors.top: parent.top
                                height: 1
                                color: root.hairline
                            }
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 10

                                // ── Which brain answers this conversation ──────
                                // The choice used to live in a settings sheet, be
                                // global, and require bouncing two systemd units.
                                // It is one tap from the message box now, and it
                                // is per conversation.
                                Rectangle {
                                    id: routeChip
                                    Layout.fillHeight: true
                                    Layout.preferredWidth: chipRow.implicitWidth + 20
                                    Layout.maximumWidth: 200
                                    radius: 11
                                    color: chipMa.containsMouse ? root.surface2 : root.surface1
                                    border.width: 1
                                    border.color: root.pickerOpen ? root.novaBlue : root.hairline
                                    Behavior on color { ColorAnimation { duration: 120 } }

                                    RowLayout {
                                        id: chipRow
                                        anchors.centerIn: parent
                                        spacing: 7

                                        // Green when the chosen brain can answer
                                        // right now — read from the machine, not
                                        // asserted.
                                        Rectangle {
                                            Layout.preferredWidth: 8
                                            Layout.preferredHeight: 8
                                            Layout.alignment: Qt.AlignVCenter
                                            radius: 4
                                            color: !root.serverUp ? root.textMute
                                                 : root.routeIsCloud ? root.novaViolet
                                                 : root.okColor
                                            Behavior on color { ColorAnimation { duration: 160 } }
                                        }

                                        ColumnLayout {
                                            spacing: 0
                                            Text {
                                                text: root.routeIsCloud ? "سحابي | Cloud"
                                                                        : "محلي | Local"
                                                color: root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: 11
                                                font.weight: Font.DemiBold
                                            }
                                            Text {
                                                Layout.maximumWidth: 118
                                                visible: root.routeModel !== ""
                                                text: root.routeModel
                                                color: root.textLo
                                                font.family: root.uiFont
                                                font.pixelSize: 9
                                                elide: Text.ElideRight
                                            }
                                        }

                                        Text {
                                            text: "▾"
                                            color: root.textMute
                                            font.family: root.uiFont
                                            font.pixelSize: 10
                                        }
                                    }

                                    MouseArea {
                                        id: chipMa
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.openPicker()
                                    }
                                }

                                QQC2.TextField {
                                    id: input
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    placeholderText: "اسأل Mo AI أي شيء… | Ask Mo AI anything…"
                                    placeholderTextColor: root.textMute
                                    color: root.textHi
                                    font.family: root.uiFont
                                    font.pixelSize: 14
                                    leftPadding: 14
                                    rightPadding: 14
                                    background: Rectangle {
                                        color: root.surface1
                                        radius: 11
                                        border.width: 1
                                        border.color: input.activeFocus ? root.novaBlue : root.hairline
                                        Behavior on border.color { ColorAnimation { duration: 130 } }
                                    }
                                    onAccepted: root.send()
                                }

                                Rectangle {
                                    Layout.fillHeight: true
                                    Layout.preferredWidth: 106
                                    radius: 11
                                    readonly property bool on_: root.busy || input.text.trim().length > 0
                                    opacity: on_ ? 1.0 : 0.45
                                    gradient: Gradient {
                                        orientation: Gradient.Horizontal
                                        GradientStop {
                                            position: 0.0
                                            color: root.busy ? root.badColor : root.novaBlue
                                        }
                                        GradientStop {
                                            position: 1.0
                                            color: root.busy ? root.warnColor : root.novaViolet
                                        }
                                    }
                                    Text {
                                        anchors.centerIn: parent
                                        text: root.busy ? "إيقاف | Stop" : "إرسال | Send"
                                        color: root.onAccent
                                        font.family: root.uiFont
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: parent.on_
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.busy ? root.stopGenerating() : root.send()
                                    }
                                }
                            }
                        }
                    }

                    // ══ DEVICE — the Hardware Centre and the drivers ════════
                    Flickable {
                        contentWidth: width
                        contentHeight: devCol.implicitHeight + 32
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        QQC2.ScrollBar.vertical: QQC2.ScrollBar { }

                        ColumnLayout {
                            id: devCol
                            width: parent.width - 32
                            x: 16
                            y: 16
                            spacing: 12

                            // Verdict.
                            Card {
                                Layout.fillWidth: true
                                RowLayout {
                                    width: parent.width
                                    spacing: 14

                                    Rectangle {
                                        Layout.preferredWidth: 44
                                        Layout.preferredHeight: 44
                                        radius: 22
                                        color: root.healthy
                                             ? Qt.rgba(root.okColor.r, root.okColor.g,
                                                       root.okColor.b, 0.14)
                                             : root.hasImportant
                                             ? Qt.rgba(root.badColor.r, root.badColor.g,
                                                       root.badColor.b, 0.14)
                                             : Qt.rgba(root.warnColor.r, root.warnColor.g,
                                                       root.warnColor.b, 0.14)
                                        Kirigami.Icon {
                                            anchors.centerIn: parent
                                            width: 24; height: 24
                                            source: root.healthy ? "moos-system" : "moos-warning"
                                            color: root.healthy ? root.okColor
                                                 : root.hasImportant ? root.badColor : root.warnColor
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 3
                                        Text {
                                            text: !root.planReady ? "جارٍ فحص جهازك…  |  Checking your device…"
                                                : root.healthy ? "جهازك سليم  |  Your device is healthy"
                                                : "وجدت " + root.problemCount + " مشكلة  |  " + root.problemCount + " issue(s) found"
                                            color: root.textHi
                                            font.family: root.uiFont
                                            font.pixelSize: 16
                                            font.weight: Font.DemiBold
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: !root.planReady
                                                ? "أقرأ التعريفات والبرامج الثابتة والأجهزة المتصلة…\nReading drivers, firmware and attached devices…"
                                                : root.healthy
                                                ? "لا توجد مشاكل في الأجهزة أو التعريفات.\nNo hardware or driver problems found."
                                                : "كل مشكلة بالأسفل معها الإصلاح الذي يناسبها.\nEach problem below comes with the repair that fixes it."
                                            color: root.textLo
                                            font.family: root.uiFont
                                            font.pixelSize: 11
                                            wrapMode: Text.Wrap
                                        }
                                    }
                                }
                            }

                            // Specs.
                            Card {
                                Layout.fillWidth: true
                                GridLayout {
                                    width: parent.width
                                    columns: 2
                                    columnSpacing: 18
                                    rowSpacing: 9

                                    Repeater {
                                        model: [
                                            { icon: "moos-identity", ar: "النظام", v: (root.snap.os || "MoOS") },
                                            { icon: "moos-cpu",      ar: "المعالج", v: (root.snap.cpu || "?") + " · " + (root.snap.cores || "?") + " cores" },
                                            { icon: "moos-memory",   ar: "الذاكرة", v: (root.snap.mem_gb || "?") + " GB RAM" },
                                            { icon: "moos-gpu",      ar: "الرسوميات", v: (root.snap.gpu || "?") },
                                            { icon: "moos-storage",  ar: "التخزين", v: (root.snap.disk && root.snap.disk.total_gb)
                                                 ? (root.snap.disk.free_gb + " / " + root.snap.disk.total_gb + " GB حرّ") : "?" },
                                            { icon: "moos-system",   ar: "النواة", v: (root.snap.kernel || "?") }
                                        ]
                                        delegate: RowLayout {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            spacing: 9
                                            Kirigami.Icon {
                                                source: modelData.icon
                                                color: root.novaCyan
                                                Layout.preferredWidth: 16
                                                Layout.preferredHeight: 16
                                            }
                                            Text {
                                                text: modelData.ar
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: 11
                                                Layout.preferredWidth: 54
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: modelData.v
                                                color: root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: 12
                                                elide: Text.ElideRight
                                            }
                                        }
                                    }
                                }
                            }

                            // The driver line, when the detector has one.
                            Card {
                                Layout.fillWidth: true
                                visible: !!root.plan.driver_status
                                RowLayout {
                                    width: parent.width
                                    spacing: 10
                                    Kirigami.Icon {
                                        source: "moos-gpu"
                                        color: root.novaViolet
                                        Layout.preferredWidth: 18
                                        Layout.preferredHeight: 18
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: root.plan.driver_status || ""
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: 12
                                        wrapMode: Text.Wrap
                                    }
                                }
                            }

                            // Every problem the detector actually found, each with its real repair.
                            Repeater {
                                model: root.actions
                                delegate: Card {
                                    id: issue
                                    required property var modelData
                                    Layout.fillWidth: true

                                    ColumnLayout {
                                        width: parent.width
                                        spacing: 8

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 9
                                            Rectangle {
                                                Layout.preferredWidth: 8
                                                Layout.preferredHeight: 8
                                                radius: 4
                                                color: issue.modelData.severity === "important"
                                                       ? root.badColor : root.warnColor
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: issue.modelData.title || ""
                                                color: root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: 13
                                                font.weight: Font.DemiBold
                                                elide: Text.ElideRight
                                            }
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: issue.modelData.detail || ""
                                            color: root.textLo
                                            font.family: root.uiFont
                                            font.pixelSize: 11
                                            wrapMode: Text.Wrap
                                        }
                                        RowLayout {
                                            spacing: 8
                                            MoButton {
                                                visible: String(issue.modelData.url || "").length > 0
                                                label: "أصلحها الآن  |  Fix it"
                                                primary: true
                                                icon: "moos-safe-update"
                                                onClicked: root.launch(issue.modelData.url, issue.modelData.title)
                                            }
                                            MoButton {
                                                label: "اسأل Mo AI  |  Ask"
                                                onClicked: root.askAbout(issue.modelData.title, issue.modelData.detail || "")
                                            }
                                        }
                                    }
                                }
                            }

                            // Maintenance — the whole of the old Hardware Centre's action list.
                            SectionTitle { text: "الصيانة  |  Maintenance"; Layout.topMargin: 6 }

                            Flow {
                                Layout.fillWidth: true
                                spacing: 8
                                Repeater {
                                    model: [
                                        { ar: "تحديث النظام", en: "Update", url: "moos://do/update", icon: "moos-safe-update" },
                                        { ar: "فحص التعريفات", en: "Drivers", url: "moos://do/check-drivers", icon: "moos-gpu" },
                                        { ar: "تحديث البرامج الثابتة", en: "Firmware", url: "moos://do/update-firmware", icon: "moos-system" },
                                        { ar: "تحسين وتنظيف", en: "Optimize", url: "moos://do/optimize", icon: "moos-optimize" },
                                        { ar: "إصلاح الصوت", en: "Fix audio", url: "moos://do/fix-audio", icon: "moos-audio" },
                                        { ar: "تقرير كامل", en: "Report", url: "moos://do/hw-report", icon: "moos-report" },
                                        { ar: "الخدمات الفاشلة", en: "Services", url: "moos://do/diagnose-services", icon: "moos-system" },
                                        { ar: "مشاكل الإقلاع", en: "Boot", url: "moos://do/inspect-boot", icon: "moos-warning" },
                                        { ar: "المحدّث", en: "Updater", url: "moos://app/updater", icon: "moos-safe-update" },
                                        { ar: "الاستعادة", en: "Recovery", url: "moos://app/recovery", icon: "moos-system" }
                                    ]
                                    delegate: MoButton {
                                        required property var modelData
                                        label: modelData.ar + "  ·  " + modelData.en
                                        icon: modelData.icon
                                        onClicked: root.launch(modelData.url, modelData.ar)
                                    }
                                }
                            }
                        }
                    }

                    // ══ APPS — the App Centre, with real Flathub search ═════
                    ColumnLayout {
                        spacing: 0

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 62
                            color: "transparent"
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 16
                                anchors.rightMargin: 16
                                anchors.topMargin: 14
                                spacing: 10

                                QQC2.TextField {
                                    id: searchField
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 40
                                    placeholderText: "ابحث في Flathub… (مثلاً blender) | Search Flathub…"
                                    placeholderTextColor: root.textMute
                                    color: root.textHi
                                    font.family: root.uiFont
                                    font.pixelSize: 13
                                    leftPadding: 14
                                    rightPadding: 14
                                    background: Rectangle {
                                        color: root.surface1
                                        radius: 11
                                        border.width: 1
                                        border.color: searchField.activeFocus ? root.novaBlue : root.hairline
                                    }
                                    onAccepted: root.searchApps(text)
                                }
                                MoButton {
                                    Layout.preferredHeight: 40
                                    label: root.searching ? "…" : "ابحث | Search"
                                    icon: "moos-install"
                                    primary: true
                                    enabled_: !root.searching
                                    onClicked: root.searchApps(searchField.text)
                                }
                            }
                        }

                        Flickable {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            contentWidth: width
                            contentHeight: appsCol.implicitHeight + 28
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            QQC2.ScrollBar.vertical: QQC2.ScrollBar { }

                            ColumnLayout {
                                id: appsCol
                                width: parent.width - 32
                                x: 16
                                y: 6
                                spacing: 10

                                Text {
                                    visible: root.searchNote !== ""
                                    text: root.searchNote
                                    color: root.textMute
                                    font.family: root.uiFont
                                    font.pixelSize: 12
                                }

                                // Search results.
                                Repeater {
                                    model: searchModel
                                    delegate: Card {
                                        id: hit
                                        required property string id
                                        required property string name
                                        required property string summary
                                        required property bool installed
                                        required property bool verified
                                        // The decision layer (moai-control): `recommended` is the
                                        // desktop-native answer to the NEED behind the query, and
                                        // `note` says why — or warns that an app is built for
                                        // another desktop and will crash here. Shipping the
                                        // ranking without showing it is the same as not shipping
                                        // it: the user still cannot tell the two apart.
                                        required property bool recommended
                                        required property string note
                                        Layout.fillWidth: true

                                        RowLayout {
                                            width: parent.width
                                            spacing: 12

                                            Rectangle {
                                                Layout.preferredWidth: 38
                                                Layout.preferredHeight: 38
                                                radius: 10
                                                color: root.surface2
                                                Kirigami.Icon {
                                                    anchors.centerIn: parent
                                                    width: 20; height: 20
                                                    source: "moos-install"
                                                    color: root.novaCyan
                                                }
                                            }

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 2
                                                RowLayout {
                                                    spacing: 6
                                                    Text {
                                                        text: hit.name
                                                        color: root.textHi
                                                        font.family: root.uiFont
                                                        font.pixelSize: 13
                                                        font.weight: Font.DemiBold
                                                    }
                                                    Text {
                                                        visible: hit.verified
                                                        text: "✓"
                                                        color: root.novaCyan
                                                        font.pixelSize: 12
                                                        font.weight: Font.Bold
                                                    }
                                                    // The MoOS pick, said out loud.
                                                    Rectangle {
                                                        visible: hit.recommended
                                                        Layout.preferredHeight: 17
                                                        Layout.preferredWidth: pickLabel.width + 12
                                                        radius: 5
                                                        color: Qt.rgba(root.novaCyan.r, root.novaCyan.g,
                                                                       root.novaCyan.b, 0.14)
                                                        border.width: 1
                                                        border.color: Qt.rgba(root.novaCyan.r, root.novaCyan.g,
                                                                              root.novaCyan.b, 0.45)
                                                        Text {
                                                            id: pickLabel
                                                            anchors.centerIn: parent
                                                            text: "اختيار MoOS  |  MoOS pick"
                                                            color: root.novaCyan
                                                            font.family: root.uiFont
                                                            font.pixelSize: 9
                                                            font.weight: Font.DemiBold
                                                        }
                                                    }
                                                }
                                                Text {
                                                    Layout.fillWidth: true
                                                    text: hit.summary
                                                    color: root.textLo
                                                    font.family: root.uiFont
                                                    font.pixelSize: 11
                                                    elide: Text.ElideRight
                                                }
                                                // Why this one — or why NOT that one. Cyan when it is
                                                // the pick, amber when the app targets another desktop
                                                // and will not survive here.
                                                Text {
                                                    visible: hit.note !== ""
                                                    Layout.fillWidth: true
                                                    text: (hit.recommended ? "✓ " : "⚠ ") + hit.note
                                                    color: hit.recommended ? root.novaCyan : root.warnColor
                                                    font.family: root.uiFont
                                                    font.pixelSize: 10
                                                    wrapMode: Text.WordWrap
                                                }
                                                Text {
                                                    text: hit.id
                                                    color: root.textMute
                                                    font.family: "JetBrains Mono"
                                                    font.pixelSize: 10
                                                }
                                            }

                                            MoButton {
                                                label: hit.installed ? "مثبّت ✓ | Installed" : "ثبّت | Install"
                                                primary: !hit.installed
                                                enabled_: !hit.installed
                                                onClicked: root.launch("moos://apps/install/" + hit.id, hit.name)
                                            }
                                        }
                                    }
                                }

                                SectionTitle {
                                    text: "موصى بها  |  Recommended"
                                    Layout.topMargin: 4
                                    visible: searchModel.count === 0
                                }

                                Repeater {
                                    model: searchModel.count === 0 ? root.appCatalog : []
                                    delegate: Card {
                                        id: rec
                                        required property var modelData
                                        readonly property bool installed: !!root.appState[modelData.id]
                                        Layout.fillWidth: true

                                        RowLayout {
                                            width: parent.width
                                            spacing: 12

                                            Rectangle {
                                                Layout.preferredWidth: 38
                                                Layout.preferredHeight: 38
                                                radius: 10
                                                color: root.surface2
                                                Kirigami.Icon {
                                                    anchors.centerIn: parent
                                                    width: 20; height: 20
                                                    source: "moos-install"
                                                    color: root.novaViolet
                                                }
                                            }
                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 2
                                                Text {
                                                    text: rec.modelData.title
                                                    color: root.textHi
                                                    font.family: root.uiFont
                                                    font.pixelSize: 13
                                                    font.weight: Font.DemiBold
                                                }
                                                Text {
                                                    Layout.fillWidth: true
                                                    text: rec.modelData.ar + "  |  " + rec.modelData.en
                                                    color: root.textLo
                                                    font.family: root.uiFont
                                                    font.pixelSize: 11
                                                }
                                            }
                                            MoButton {
                                                label: rec.installed ? "مثبّت ✓ | Installed" : "ثبّت | Install"
                                                primary: !rec.installed
                                                enabled_: !rec.installed
                                                onClicked: root.launch("moos://apps/install/" + rec.modelData.id,
                                                                       rec.modelData.title)
                                            }
                                        }
                                    }
                                }

                                SectionNote {
                                    Layout.fillWidth: true
                                    Layout.topMargin: 4
                                    visible: searchModel.count === 0
                                    text: "أو اطلب من Mo AI مباشرة: «ثبّت لي Blender».\nOr just ask Mo AI: “install Blender for me”."
                                }
                            }
                        }
                    }

                    // ══ COMPATIBILITY ══════════════════════════════════════
                    Flickable {
                        contentWidth: width
                        contentHeight: compatCol.implicitHeight + 32
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        QQC2.ScrollBar.vertical: QQC2.ScrollBar { }

                        ColumnLayout {
                            id: compatCol
                            width: parent.width - 32
                            x: 16
                            y: 16
                            spacing: 12

                            SectionNote {
                                Layout.fillWidth: true
                                text: "شغّل تطبيقات وألعاب Windows و Android على MoOS. الحالة مقروءة من جهازك، لا مفترضة.\n"
                                    + "Run Windows and Android apps and games on MoOS. Status is read from your machine, not assumed."
                            }

                            Repeater {
                                model: root.compatCatalog
                                delegate: Card {
                                    id: compat
                                    required property var modelData
                                    readonly property bool ready: !!root.compatState[modelData.key]
                                    Layout.fillWidth: true

                                    RowLayout {
                                        width: parent.width
                                        spacing: 12

                                        Rectangle {
                                            Layout.preferredWidth: 40
                                            Layout.preferredHeight: 40
                                            radius: 11
                                            color: compat.ready
                                                 ? Qt.rgba(root.okColor.r, root.okColor.g,
                                                           root.okColor.b, 0.13)
                                                 : root.surface2
                                            Kirigami.Icon {
                                                anchors.centerIn: parent
                                                width: 21; height: 21
                                                source: compat.modelData.icon
                                                color: compat.ready ? root.okColor : root.novaCyan
                                            }
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 3
                                            RowLayout {
                                                spacing: 8
                                                Text {
                                                    text: compat.modelData.title
                                                    color: root.textHi
                                                    font.family: root.uiFont
                                                    font.pixelSize: 14
                                                    font.weight: Font.DemiBold
                                                }
                                                StatusPill {
                                                    good: compat.ready
                                                    goodText: "جاهز | Ready"
                                                    badText: "غير مثبّت | Not set up"
                                                }
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: compat.modelData.ar + "  |  " + compat.modelData.en
                                                color: root.textLo
                                                font.family: root.uiFont
                                                font.pixelSize: 11
                                            }
                                        }
                                        MoButton {
                                            label: compat.ready ? "جاهز ✓" : "إعداد | Set up"
                                            primary: !compat.ready
                                            enabled_: !compat.ready
                                            onClicked: root.launch(compat.modelData.url, compat.modelData.title)
                                        }
                                    }
                                }
                            }

                            Card {
                                Layout.fillWidth: true
                                Layout.topMargin: 4
                                RowLayout {
                                    width: parent.width
                                    spacing: 12
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 3
                                        Text {
                                            text: "المحاكاة الافتراضية | Virtualisation (KVM)"
                                            color: root.textHi
                                            font.family: root.uiFont
                                            font.pixelSize: 13
                                            font.weight: Font.DemiBold
                                        }
                                        Text {
                                            text: "يحتاجه Waydroid والأجهزة الافتراضية.\nNeeded by Waydroid and virtual machines."
                                            color: root.textLo
                                            font.family: root.uiFont
                                            font.pixelSize: 11
                                        }
                                    }
                                    StatusPill {
                                        good: !!root.compatState.kvm
                                        goodText: "مفعّل | Enabled"
                                        badText: "غير متاح | Unavailable"
                                    }
                                }
                            }

                            MoButton {
                                Layout.topMargin: 4
                                label: "تثبيت ذكي حسب جهازي  |  Smart setup for my hardware"
                                icon: "moos-optimize"
                                onClicked: root.launch("moos://do/smart-setup", "Smart setup")
                            }
                        }
                    }

                    // ══ REMOTE ═════════════════════════════════════════════
                    Flickable {
                        contentWidth: width
                        contentHeight: remoteCol.implicitHeight + 32
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        QQC2.ScrollBar.vertical: QQC2.ScrollBar { }

                        ColumnLayout {
                            id: remoteCol
                            width: parent.width - 32
                            x: 16
                            y: 16
                            spacing: 12

                            Card {
                                Layout.fillWidth: true
                                RowLayout {
                                    width: parent.width
                                    spacing: 14

                                    Rectangle {
                                        Layout.preferredWidth: 46
                                        Layout.preferredHeight: 46
                                        radius: 23
                                        color: root.remoteState.active
                                               ? Qt.rgba(root.okColor.r, root.okColor.g,
                                                         root.okColor.b, 0.14)
                                               : root.surface2
                                        Kirigami.Icon {
                                            anchors.centerIn: parent
                                            width: 24; height: 24
                                            source: "moos-phone"
                                            color: root.remoteState.active ? root.okColor : root.textMute
                                        }
                                        // A live ring while it is actually serving.
                                        Rectangle {
                                            anchors.centerIn: parent
                                            width: parent.width; height: parent.height
                                            radius: width / 2
                                            color: "transparent"
                                            border.width: 2
                                            border.color: root.okColor
                                            visible: !!root.remoteState.active
                                            SequentialAnimation on opacity {
                                                running: !!root.remoteState.active
                                                loops: Animation.Infinite
                                                NumberAnimation { from: 0.7; to: 0.0; duration: 1200 }
                                                NumberAnimation { from: 0.0; to: 0.0; duration: 200 }
                                            }
                                            SequentialAnimation on scale {
                                                running: !!root.remoteState.active
                                                loops: Animation.Infinite
                                                NumberAnimation { from: 1.0; to: 1.45; duration: 1200 }
                                                NumberAnimation { from: 1.0; to: 1.0; duration: 200 }
                                            }
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        Text {
                                            text: root.remoteState.active
                                                  ? "يعمل الآن  |  Running"
                                                  : "متوقف  |  Stopped"
                                            color: root.remoteState.active ? root.okColor : root.textHi
                                            font.family: root.uiFont
                                            font.pixelSize: 16
                                            font.weight: Font.DemiBold
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: root.remoteState.active
                                                ? "افتح اللوحة لمسح رمز QR من هاتفك.\nOpen the panel to scan the QR code from your phone."
                                                : "شغّله ليتحكّم هاتفك بهذا الجهاز.\nStart it to control this PC from your phone."
                                            color: root.textLo
                                            font.family: root.uiFont
                                            font.pixelSize: 11
                                            wrapMode: Text.Wrap
                                        }
                                    }
                                }
                            }

                            // Start / Stop / Reconnect. These are user services — no
                            // password, no terminal. moos-open runs systemctl --user
                            // directly and Mo AI shows the result on the next poll.
                            Flow {
                                Layout.fillWidth: true
                                spacing: 8

                                MoButton {
                                    label: "تشغيل  |  Start"
                                    icon: "moos-phone"
                                    primary: true
                                    enabled_: !root.remoteState.active
                                    onClicked: root.launch("moos://remote/start", "Mo PC Remote — start")
                                }
                                MoButton {
                                    label: "إيقاف  |  Stop"
                                    danger: true
                                    enabled_: !!root.remoteState.active
                                    onClicked: root.launch("moos://remote/stop", "Mo PC Remote — stop")
                                }
                                MoButton {
                                    label: "إعادة الاتصال  |  Reconnect"
                                    icon: "moos-network"
                                    onClicked: root.launch("moos://remote/restart", "Mo PC Remote — reconnect")
                                }
                                MoButton {
                                    label: "افتح اللوحة  |  Open panel"
                                    onClicked: root.launch("moos://app/remote", "Mo PC Remote")
                                }
                            }

                            // The pieces it depends on — read from the machine.
                            Card {
                                Layout.fillWidth: true
                                ColumnLayout {
                                    width: parent.width
                                    spacing: 9
                                    Text {
                                        text: "المتطلّبات  |  Requirements"
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                    }
                                    Repeater {
                                        model: [
                                            { ar: "التقاط الشاشة (PipeWire)", en: "Screen capture", k: "pipewire" },
                                            { ar: "بوابة سطح المكتب (Portal)", en: "Desktop portal", k: "portal" }
                                        ]
                                        delegate: RowLayout {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            spacing: 10
                                            Text {
                                                Layout.fillWidth: true
                                                text: modelData.ar + "  |  " + modelData.en
                                                color: root.textLo
                                                font.family: root.uiFont
                                                font.pixelSize: 12
                                            }
                                            StatusPill {
                                                good: !!root.remoteState[modelData.k]
                                                goodText: "يعمل | OK"
                                                badText: "متوقف | Down"
                                            }
                                        }
                                    }
                                }
                            }

                            MoButton {
                                label: "الوصول من خارج المنزل  |  Reach it from outside"
                                icon: "moos-network"
                                onClicked: root.launch("moos://do/remote-anywhere", "Remote anywhere")
                            }
                        }
                    }

                    // ══ DEVELOPER — Codex and Claude ═══════════════════════
                    Flickable {
                        contentWidth: width
                        contentHeight: devsCol.implicitHeight + 32
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        QQC2.ScrollBar.vertical: QQC2.ScrollBar { }

                        ColumnLayout {
                            id: devsCol
                            width: parent.width - 32
                            x: 16
                            y: 16
                            spacing: 12

                            SectionNote {
                                Layout.fillWidth: true
                                text: "‏وكلاء برمجة يشتغلون داخل مشروعك كمستخدم عادي — يُثبَّتون في ~/.local، بلا صلاحيات مسؤول ولا مساس بالنظام.\n"
                                    + "‎Coding agents that run in your project as your user — installed into ~/.local, with no admin rights and no changes to the system."
                            }

                            Repeater {
                                // Two of these are somebody else's cloud, and one is not — which is
                                // the only distinction that matters on a machine that ships its own
                                // brain, so the card says it out loud. `local: true` earns the
                                // "works offline" badge and the cyan frame; the other two carry the
                                // account they need, because "why is it asking me to log in?" is the
                                // first thing a user hits otherwise.
                                model: [
                                    { key: "opencode", title: "OpenCode", local: true,
                                      ar: "وكيل يعمل على عقل MoOS المحلي", en: "Runs on the MoOS local brain",
                                      needs: "بلا حساب وبلا إنترنت  |  no account, no internet",
                                      pkg: "opencode-ai",
                                      install: "moos://do/install-opencode", run: "moos://dev/opencode" },
                                    { key: "claude", title: "Claude Code", local: false,
                                      ar: "وكيل Anthropic البرمجي", en: "Anthropic's coding agent",
                                      needs: "يحتاج حساب Anthropic  |  needs an Anthropic account",
                                      pkg: "@anthropic-ai/claude-code",
                                      install: "moos://do/install-claude", run: "moos://dev/claude" },
                                    { key: "codex", title: "Codex", local: false,
                                      ar: "وكيل OpenAI البرمجي", en: "OpenAI's coding agent",
                                      needs: "يحتاج حساب OpenAI  |  needs an OpenAI account",
                                      pkg: "@openai/codex",
                                      install: "moos://do/install-codex", run: "moos://dev/codex" }
                                ]
                                delegate: Card {
                                    id: ag
                                    required property var modelData
                                    readonly property bool have: !!root.agentState[modelData.key]
                                    readonly property bool onDevice: !!modelData.local
                                    Layout.fillWidth: true

                                    // The local agent is the one MoOS is actually proud of, so it
                                    // reads as first-party: a cyan hairline instead of the default.
                                    // Card IS a Rectangle, so this overrides its border binding —
                                    // there is no borderColor property to invent.
                                    border.color: ag.onDevice
                                                  ? Qt.rgba(root.novaCyan.r, root.novaCyan.g, root.novaCyan.b, 0.42)
                                                  : root.hairline

                                    RowLayout {
                                        width: parent.width
                                        spacing: 12

                                        Rectangle {
                                            Layout.preferredWidth: 40
                                            Layout.preferredHeight: 40
                                            radius: 11
                                            color: ag.have
                                                   ? Qt.rgba(root.okColor.r, root.okColor.g,
                                                             root.okColor.b, 0.13)
                                                   : (ag.onDevice
                                                      ? Qt.rgba(root.novaCyan.r, root.novaCyan.g, root.novaCyan.b, 0.12)
                                                      : root.surface2)
                                            Kirigami.Icon {
                                                anchors.centerIn: parent
                                                width: 21; height: 21
                                                source: ag.onDevice ? "moos-ai" : "utilities-terminal"
                                                color: ag.have ? root.okColor
                                                               : (ag.onDevice ? root.novaCyan : root.textMute)
                                            }
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 3
                                            RowLayout {
                                                spacing: 8
                                                Text {
                                                    text: ag.modelData.title
                                                    color: root.textHi
                                                    font.family: root.uiFont
                                                    font.pixelSize: 14
                                                    font.weight: Font.DemiBold
                                                }
                                                StatusPill {
                                                    good: ag.have
                                                    goodText: "مثبّت | Installed"
                                                    badText: "غير مثبّت | Not installed"
                                                }
                                                // The badge that is the whole point of shipping a
                                                // local brain: an agent that keeps working when the
                                                // network does not.
                                                Rectangle {
                                                    visible: ag.onDevice
                                                    Layout.preferredHeight: 18
                                                    Layout.preferredWidth: offlineText.width + 14
                                                    radius: 6
                                                    color: Qt.rgba(root.novaCyan.r, root.novaCyan.g,
                                                                   root.novaCyan.b, 0.14)
                                                    border.width: 1
                                                    border.color: Qt.rgba(root.novaCyan.r, root.novaCyan.g,
                                                                          root.novaCyan.b, 0.45)
                                                    Text {
                                                        id: offlineText
                                                        anchors.centerIn: parent
                                                        text: "يعمل بلا إنترنت  |  offline"
                                                        color: root.novaCyan
                                                        font.family: root.uiFont
                                                        font.pixelSize: 9
                                                        font.weight: Font.DemiBold
                                                    }
                                                }
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: ag.modelData.ar + "  |  " + ag.modelData.en
                                                color: root.textLo
                                                font.family: root.uiFont
                                                font.pixelSize: 11
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: ag.modelData.needs
                                                color: ag.onDevice ? root.novaCyan : root.textMute
                                                opacity: ag.onDevice ? 0.95 : 0.8
                                                font.family: root.uiFont
                                                font.pixelSize: 10
                                            }
                                            Text {
                                                text: ag.modelData.pkg
                                                color: root.textMute
                                                font.family: "JetBrains Mono"
                                                font.pixelSize: 10
                                            }
                                        }
                                        MoButton {
                                            label: ag.have ? "شغّل | Run" : "ثبّت | Install"
                                            primary: true
                                            icon: ag.have ? "utilities-terminal" : "moos-install"
                                            onClicked: root.launch(
                                                ag.have ? ag.modelData.run : ag.modelData.install,
                                                ag.modelData.title)
                                        }
                                    }
                                }
                            }

                            MoButton {
                                Layout.topMargin: 4
                                label: "افتح وكيلاً في مشروع  |  Open an agent in a project"
                                icon: "utilities-terminal"
                                // Enabled when ANY agent is installed — moai-code builds its picker
                                // from what is actually on the machine, so a third agent must not
                                // be forgotten here (the old condition named two by hand).
                                enabled_: !!root.agentState.claude || !!root.agentState.codex
                                          || !!root.agentState.opencode
                                onClicked: root.launch("moos://dev/code", "Code")
                            }
                        }
                    }
                }
            }
        }

        // ── Toast ───────────────────────────────────────────────────────────
        Rectangle {
            id: toast
            property string msg: ""
            z: 100
            opacity: 0
            visible: opacity > 0
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 90
            radius: 12
            width: Math.min(parent.width - 40, toastCol.implicitWidth + 30)
            height: toastCol.implicitHeight + 20
            color: root.surface2
            border.width: 1
            border.color: Qt.rgba(root.novaCyan.r, root.novaCyan.g,
                                  root.novaCyan.b, 0.5)
            Behavior on opacity { NumberAnimation { duration: 220 } }

            Timer { id: toastTimer; interval: 2800; onTriggered: toast.opacity = 0 }
            function show(m) {
                msg = m
                opacity = 1
                toastTimer.restart()
            }

            ColumnLayout {
                id: toastCol
                anchors.centerIn: parent
                spacing: 3
                Text {
                    text: "جارٍ التنفيذ ✓  |  Running ✓"
                    color: root.novaCyan
                    font.family: root.uiFont
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                }
                Text {
                    text: toast.msg
                    color: root.textHi
                    font.family: root.uiFont
                    font.pixelSize: 13
                }
            }
        }

        // ── The brain picker ────────────────────────────────────────────────
        // Every entry here is REAL: the local models come from `ramalama list`,
        // the cloud ones from the provider's own /v1/models. Nothing is invented,
        // and a provider that has no model list says so instead of being given a
        // made-up menu.
        Rectangle {
            anchors.fill: parent
            z: 250
            visible: root.pickerOpen
            color: Qt.rgba(root.palette.shadow.r, root.palette.shadow.g,
                           root.palette.shadow.b, 0.69)
            MouseArea { anchors.fill: parent; onClicked: root.pickerOpen = false }

            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 86
                width: Math.min(parent.width - 40, 430)
                height: Math.min(parent.height - 130, pickCol.implicitHeight + 32)
                radius: 16
                color: root.surface1
                border.width: 1
                border.color: root.hairline
                MouseArea { anchors.fill: parent }   // swallow clicks on the card

                ColumnLayout {
                    id: pickCol
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 9

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        SectionTitle {
                            Layout.fillWidth: true
                            text: "العقل والقوة  |  Brain & power"
                            font.pixelSize: 15
                        }
                        MoButton {
                            label: root.modelsLoading ? "…" : "تحديث | Refresh"
                            enabled_: !root.modelsLoading
                            onClicked: root.loadModels()
                        }
                    }

                    SectionNote {
                        Layout.fillWidth: true
                        text: "اختيارك يسري على هذه المحادثة فقط.  |  Applies to this conversation."
                        font.pixelSize: 10
                    }

                    Flickable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 90
                        contentWidth: width
                        contentHeight: choiceCol.implicitHeight
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        QQC2.ScrollBar.vertical: QQC2.ScrollBar { }

                        ColumnLayout {
                            id: choiceCol
                            width: parent.width
                            spacing: 3

                            // ── Local ──────────────────────────────────────
                            Text {
                                Layout.topMargin: 2
                                text: "محلي وخاص  |  Local & private"
                                color: root.textMute
                                font.family: root.uiFont
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                            }

                            Repeater {
                                model: root.localModels
                                delegate: Rectangle {
                                    id: locRow
                                    required property var modelData
                                    readonly property bool on_: root.route === locRow.modelData.id
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 40
                                    radius: 10
                                    color: locRow.on_
                                         ? Qt.rgba(root.okColor.r, root.okColor.g,
                                                   root.okColor.b, 0.14)
                                         : locMa.containsMouse ? root.surface2 : "transparent"
                                    border.width: 1
                                    border.color: locRow.on_ ? root.okColor : "transparent"
                                    Behavior on color { ColorAnimation { duration: 110 } }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 10
                                        anchors.rightMargin: 10
                                        spacing: 9

                                        Kirigami.Icon {
                                            source: "moos-system"
                                            color: root.okColor
                                            Layout.preferredWidth: 15
                                            Layout.preferredHeight: 15
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 0
                                            Text {
                                                Layout.fillWidth: true
                                                text: locRow.modelData.label
                                                color: root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: 12
                                                font.weight: locRow.on_ ? Font.DemiBold : Font.Normal
                                                elide: Text.ElideRight
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: !locRow.modelData.pulled
                                                        ? "يحتاج تحميلاً أول مرة | needs a first download"
                                                        : locRow.modelData.serving
                                                        ? "جاهز | ready"
                                                        : "محمَّل — يُعاد تشغيل العقل | downloaded — restarts the brain"
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: 9
                                                elide: Text.ElideRight
                                            }
                                        }
                                        Text {
                                            visible: locRow.on_
                                            text: "✓"
                                            color: root.okColor
                                            font.family: root.uiFont
                                            font.pixelSize: 13
                                            font.weight: Font.DemiBold
                                        }
                                    }
                                    MouseArea {
                                        id: locMa
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.pickRoute(locRow.modelData.id)
                                    }
                                }
                            }

                            // ── Cloud ──────────────────────────────────────
                            Text {
                                Layout.topMargin: 8
                                text: "سحابي  |  Cloud"
                                color: root.textMute
                                font.family: root.uiFont
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                            }

                            Repeater {
                                model: root.cloudModels
                                delegate: Rectangle {
                                    id: cldRow
                                    required property var modelData
                                    readonly property bool on_: root.route === cldRow.modelData.id
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 34
                                    radius: 10
                                    color: cldRow.on_
                                         ? Qt.rgba(root.novaViolet.r, root.novaViolet.g,
                                                   root.novaViolet.b, 0.18)
                                         : cldMa.containsMouse ? root.surface2 : "transparent"
                                    border.width: 1
                                    border.color: cldRow.on_ ? root.novaViolet : "transparent"
                                    Behavior on color { ColorAnimation { duration: 110 } }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 10
                                        anchors.rightMargin: 10
                                        spacing: 9

                                        Rectangle {
                                            Layout.preferredWidth: 7
                                            Layout.preferredHeight: 7
                                            Layout.alignment: Qt.AlignVCenter
                                            radius: 4
                                            color: root.novaViolet
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: cldRow.modelData.label
                                            color: root.textHi
                                            font.family: root.uiFont
                                            font.pixelSize: 12
                                            font.weight: cldRow.on_ ? Font.DemiBold : Font.Normal
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            visible: cldRow.on_
                                            text: "✓"
                                            color: root.novaViolet
                                            font.family: root.uiFont
                                            font.pixelSize: 13
                                            font.weight: Font.DemiBold
                                        }
                                    }
                                    MouseArea {
                                        id: cldMa
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.pickRoute(cldRow.modelData.id)
                                    }
                                }
                            }

                            // A provider with no /v1/models is not a failure — it
                            // just means the model is whatever the user typed into
                            // Settings, and that free-text field is still there.
                            Text {
                                Layout.fillWidth: true
                                Layout.topMargin: 4
                                visible: root.modelsError !== ""
                                text: root.modelsError
                                color: root.textMute
                                font.family: root.uiFont
                                font.pixelSize: 10
                                wrapMode: Text.Wrap
                            }
                        }
                    }

                    MoButton {
                        Layout.fillWidth: true
                        label: "المزوّد والمفتاح  |  Provider & API key"
                        icon: "configure"
                        onClicked: {
                            root.pickerOpen = false
                            root.loadConfig()
                            root.settingsOpen = true
                        }
                    }
                }
            }
        }

        // ── Settings ────────────────────────────────────────────────────────
        Rectangle {
            anchors.fill: parent
            z: 300
            visible: root.settingsOpen
            color: Qt.rgba(root.palette.shadow.r, root.palette.shadow.g,
                           root.palette.shadow.b, 0.82)
            MouseArea { anchors.fill: parent; onClicked: root.settingsOpen = false }

            Rectangle {
                anchors.centerIn: parent
                width: Math.min(parent.width - 40, 440)
                height: Math.min(parent.height - 40, setCol.implicitHeight + 40)
                radius: 18
                color: root.surface1
                border.width: 1
                border.color: root.hairline
                MouseArea { anchors.fill: parent }   // swallow clicks on the card

                ColumnLayout {
                    id: setCol
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 13

                    RowLayout {
                        Layout.fillWidth: true
                        SectionTitle { text: "إعدادات Mo AI  |  Settings" }
                        Item { Layout.fillWidth: true }
                        MoButton {
                            label: "✕"
                            onClicked: root.settingsOpen = false
                        }
                    }

                    Text {
                        text: "العقل | Brain"
                        color: root.textLo
                        font.family: root.uiFont
                        font.pixelSize: 12
                    }

                    // Local / Cloud
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 46
                        radius: 12
                        color: root.surface0
                        border.width: 1
                        border.color: root.hairline
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 4
                            spacing: 4
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                radius: 9
                                color: !root.settingsCloud ? root.novaBlue : "transparent"
                                Behavior on color { ColorAnimation { duration: 130 } }
                                Text {
                                    anchors.centerIn: parent
                                    text: "محلي | Local"
                                    color: !root.settingsCloud ? root.onAccent : root.textLo
                                    font.family: root.uiFont
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.settingsCloud = false }
                            }
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                radius: 9
                                color: root.settingsCloud ? root.novaViolet : "transparent"
                                Behavior on color { ColorAnimation { duration: 130 } }
                                Text {
                                    anchors.centerIn: parent
                                    text: "سحابي | Cloud"
                                    color: root.settingsCloud ? root.onAccent : root.textLo
                                    font.family: root.uiFont
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.settingsCloud = true }
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: root.settingsCloud
                        spacing: 7

                        Text { text: "الوكيل | Agent"; color: root.textLo; font.family: root.uiFont; font.pixelSize: 11 }

                        // The provider picker. Each preset fills in the base URL,
                        // the wire protocol and a CHEAP default model — a key is
                        // never part of a preset and never leaves the keyring.
                        Flow {
                            Layout.fillWidth: true
                            spacing: 6
                            Repeater {
                                model: root.providers
                                delegate: Rectangle {
                                    id: prov
                                    required property var modelData
                                    readonly property bool on_: root.settingsProvider === modelData.id
                                    height: 30
                                    width: provText.implicitWidth + 22
                                    radius: 9
                                    color: on_ ? root.novaBlue
                                         : provMa.containsMouse ? root.surface3 : root.surface2
                                    border.width: 1
                                    border.color: on_ ? "transparent" : root.hairline
                                    Behavior on color { ColorAnimation { duration: 120 } }
                                    Text {
                                        id: provText
                                        anchors.centerIn: parent
                                        text: prov.modelData.name
                                        color: prov.on_ ? root.onAccent : root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: 11
                                        font.weight: prov.on_ ? Font.DemiBold : Font.Normal
                                    }
                                    MouseArea {
                                        id: provMa
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.pickProvider(prov.modelData)
                                    }
                                }
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: text !== ""
                            text: {
                                for (let i = 0; i < root.providers.length; i++)
                                    if (root.providers[i].id === root.settingsProvider)
                                        return root.providers[i].hint || ""
                                return ""
                            }
                            color: root.textMute
                            font.family: root.uiFont
                            font.pixelSize: 10
                            wrapMode: Text.Wrap
                        }

                        Text {
                            text: "الرابط | Base URL"
                            color: root.textLo; font.family: root.uiFont; font.pixelSize: 11
                        }
                        QQC2.TextField {
                            id: fBase
                            Layout.fillWidth: true
                            placeholderText: "https://api.openai.com/v1"
                            placeholderTextColor: root.textMute
                            color: root.textHi
                            font.family: root.uiFont
                            font.pixelSize: 12
                            background: Rectangle { color: root.surface2; radius: 8; border.width: 1; border.color: fBase.activeFocus ? root.novaBlue : root.hairline }
                            onTextChanged: root.settingsProvider = root.matchProvider(text.trim(), root.settingsWire)
                        }

                        Text {
                            text: "النموذج | Model  " + (root.settingsWire === "anthropic" ? "(Anthropic)" : "(OpenAI-compatible)")
                            color: root.textLo; font.family: root.uiFont; font.pixelSize: 11
                        }
                        QQC2.TextField {
                            id: fModel
                            Layout.fillWidth: true
                            placeholderText: "gpt-5.4-mini"
                            placeholderTextColor: root.textMute
                            color: root.textHi
                            font.family: root.uiFont
                            font.pixelSize: 12
                            background: Rectangle { color: root.surface2; radius: 8; border.width: 1; border.color: fModel.activeFocus ? root.novaBlue : root.hairline }
                        }

                        Text {
                            text: "مفتاح API | API key — يُحفظ في خزنة النظام، لا في ملف"
                            color: root.textLo; font.family: root.uiFont; font.pixelSize: 11
                        }
                        QQC2.TextField {
                            id: fKey
                            Layout.fillWidth: true
                            echoMode: TextInput.Password
                            placeholderText: "sk-…"
                            placeholderTextColor: root.textMute
                            color: root.textHi
                            font.family: root.uiFont
                            font.pixelSize: 12
                            background: Rectangle { color: root.surface2; radius: 8; border.width: 1; border.color: fKey.activeFocus ? root.novaBlue : root.hairline }
                        }

                        // Test — sends a real request and reports what came back.
                        // "Saved ✓" proves nothing: the URL can be wrong, the key
                        // dead, the model missing, or the provider behind a CDN
                        // that refuses us. This is the only honest confirmation.
                        MoButton {
                            Layout.fillWidth: true
                            Layout.topMargin: 2
                            label: root.settingsTesting ? "جارٍ الاختبار… | Testing…"
                                                        : "اختبر الاتصال  |  Test connection"
                            icon: "moos-network"
                            enabled_: !root.settingsTesting
                            onClicked: root.testConfig()
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            visible: root.settingsTestMsg !== ""
                            radius: 9
                            implicitHeight: testText.implicitHeight + 18
                            color: root.settingsTestOk
                                ? Qt.rgba(root.okColor.r, root.okColor.g,
                                          root.okColor.b, 0.10)
                                : Qt.rgba(root.badColor.r, root.badColor.g,
                                          root.badColor.b, 0.10)
                            border.width: 1
                            border.color: root.settingsTestOk
                                ? Qt.rgba(root.okColor.r, root.okColor.g,
                                          root.okColor.b, 0.45)
                                : Qt.rgba(root.badColor.r, root.badColor.g,
                                          root.badColor.b, 0.45)
                            Text {
                                id: testText
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: 11
                                anchors.rightMargin: 11
                                text: root.settingsTestMsg
                                color: root.settingsTestOk ? root.okColor : root.badColor
                                font.family: root.uiFont
                                font.pixelSize: 11
                                wrapMode: Text.Wrap
                            }
                        }
                    }

                    SectionNote {
                        Layout.fillWidth: true
                        visible: !root.settingsCloud
                        text: "العقل المحلي خاص بالكامل (RamaLama) — لا إنترنت بعد التحميل الأول.\n"
                            + "The local brain is fully private — no Internet after the first download."
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: root.settingsError !== ""
                        text: root.settingsError
                        color: root.badColor
                        font.family: root.uiFont
                        font.pixelSize: 11
                        wrapMode: Text.Wrap
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 44
                        radius: 12
                        opacity: root.settingsSaving ? 0.6 : 1
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: root.novaBlue }
                            GradientStop { position: 1.0; color: root.novaViolet }
                        }
                        Text {
                            anchors.centerIn: parent
                            text: root.settingsSaving ? "جارٍ الحفظ… | Saving…" : "حفظ | Save"
                            color: root.onAccent
                            font.family: root.uiFont
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            enabled: !root.settingsSaving
                            onClicked: root.saveConfig()
                        }
                    }
                }
            }
        }
    }

    // ── Settings plumbing ───────────────────────────────────────────────────
    property bool settingsOpen: false
    property bool settingsCloud: false
    property bool settingsSaving: false
    property string settingsError: ""

    // The cloud provider. `wire` is the protocol the provider actually speaks;
    // moai-gateway translates it, so this app only ever speaks one dialect.
    property var providers: []
    property string settingsProvider: "custom"
    property string settingsWire: "openai"

    // The result of a REAL request to the provider — not "Saved ✓".
    property bool settingsTesting: false
    property bool settingsTestOk: false
    property string settingsTestMsg: ""

    function loadProviders() {
        const xhr = new XMLHttpRequest()
        xhr.open("GET", controlApi + "/providers")
        xhr.setRequestHeader("X-Moai-Control", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE || xhr.status !== 200)
                return
            try {
                root.providers = JSON.parse(xhr.responseText).providers || []
            } catch (e) {}
        }
        xhr.send()
    }

    /** Fill the form from a preset. The key is never part of a preset. */
    function pickProvider(p) {
        root.settingsProvider = p.id
        root.settingsWire = p.wire || "openai"
        if (p.base)
            fBase.text = p.base
        if (p.model)
            fModel.text = p.model
        root.settingsTestMsg = ""
    }

    /** Which preset (if any) the current form matches. */
    function matchProvider(base, wire) {
        for (let i = 0; i < providers.length; i++)
            if (providers[i].base && providers[i].base === base
                    && (providers[i].wire || "openai") === wire)
                return providers[i].id
        return "custom"
    }

    function loadConfig() {
        settingsError = ""
        settingsTestMsg = ""
        loadProviders()
        const xhr = new XMLHttpRequest()
        xhr.open("GET", controlApi + "/config")
        xhr.setRequestHeader("X-Moai-Control", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            if (xhr.status === 200) {
                try {
                    const c = JSON.parse(xhr.responseText)
                    root.settingsCloud = (c.mode === "cloud")
                    fBase.text = c.cloud_base || ""
                    fModel.text = c.cloud_model || ""
                    root.settingsWire = c.cloud_wire || "openai"
                    root.settingsProvider = root.matchProvider(fBase.text, root.settingsWire)
                    fKey.text = ""
                    fKey.placeholderText = c.has_key
                        ? "•••• محفوظ في خزنة النظام | saved (اتركه فارغاً للإبقاء)"
                        : "sk-…  مفتاحك | your API key"
                } catch (e) {}
            } else {
                root.settingsError = "خدمة الإعدادات غير متاحة | settings service unavailable"
            }
        }
        xhr.send()
    }

    /** Actually call the provider and say what came back. */
    function testConfig() {
        root.settingsTesting = true
        root.settingsTestMsg = ""
        const body = {
            cloud_base: fBase.text.trim(),
            cloud_model: fModel.text.trim(),
            cloud_wire: root.settingsWire
        }
        if (fKey.text.length > 0)
            body.cloud_key = fKey.text     // still being typed; not saved yet
        const xhr = new XMLHttpRequest()
        xhr.open("POST", controlApi + "/test")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.setRequestHeader("X-Moai-Control", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            root.settingsTesting = false
            try {
                const r = JSON.parse(xhr.responseText)
                root.settingsTestOk = !!r.ok
                if (r.ok) {
                    const u = r.usage || {}
                    root.settingsTestMsg = "✓ ردّ: “" + (r.reply || "") + "”\n"
                        + (r.model || "") + "  ·  " + (u["in"] || 0) + " in / "
                        + (u.out || 0) + " out tokens"
                } else {
                    root.settingsTestMsg = "✕ " + (r.error || "فشل | failed")
                }
            } catch (e) {
                root.settingsTestOk = false
                root.settingsTestMsg = "✕ تعذّر الاختبار | test failed"
            }
        }
        xhr.send(JSON.stringify(body))
    }

    function saveConfig() {
        const body = {
            mode: settingsCloud ? "cloud" : "local",
            cloud_base: fBase.text.trim(),
            cloud_model: fModel.text.trim(),
            cloud_wire: root.settingsWire
        }
        if (fKey.text.length > 0)
            body.cloud_key = fKey.text
        root.settingsError = ""
        root.settingsSaving = true
        const xhr = new XMLHttpRequest()
        xhr.open("POST", controlApi + "/config")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.setRequestHeader("X-Moai-Control", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            root.settingsSaving = false
            if (xhr.status === 200) {
                root.settingsOpen = false
                // The provider may have changed under the picker: re-ask for the
                // real model list, and re-resolve the default route.
                root.route = ""
                root.defaultRoute = ""
                root.loadModels()
            } else {
                root.settingsError = "تعذّر الحفظ | couldn't save"
            }
        }
        xhr.send(JSON.stringify(body))
    }
}
