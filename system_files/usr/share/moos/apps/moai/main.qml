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
import QtQuick.Dialogs
import QtQuick.Shapes
import QtQuick.Effects
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Kirigami.ApplicationWindow {
    id: root

    // ── Motion gate ──────────────────────────────────────────────────────
    // Every endless animation below (the idle-orb breathing, the thinking
    // halo, the typing dots, the ambient particles, the remote-active rings)
    // ANDs its `running:` with this. Kirigami.Units.longDuration is what the
    // "animation speed" slider actually moves and KDE FLOORS it at 1 when
    // animations are disabled — so `> 1` is false exactly when the user, or
    // `moos-theme motion still`, has turned motion off, and every loop stops
    // instead of rasterising forever on an idle assistant window.
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1

    // ── Semantic design tokens — supplied by the active MoOS colour scheme ───────
    //
    // These read Kirigami.Theme, NOT ApplicationWindow.palette, and the difference is not
    // academic. Measured on one session, one scheme (MoOSUI2Light, selection #006D67), two
    // MoOS apps sampled at the same moment:
    //
    //   an app on Kirigami.Theme  ->  surface #DFEFEA, accent #006D67   (MoOS teal)
    //   an app on palette.*       ->  surface #FFFFFF, accent #45A7D7   (stock Breeze blue)
    //
    // A bare `palette` on a QQuickWindow does not resolve the KDE colour scheme; it falls back
    // to Qt's built-in defaults, and QT_QPA_PLATFORMTHEME=kde does not change that. The comment
    // that used to sit here said the bindings were "deliberately owned by
    // ApplicationWindow.palette" so a Global Theme change would follow at runtime — the intent
    // was exactly right and the mechanism never delivered it.
    //
    // The identifiers stay (novaBlue, novaCyan, novaViolet are load-bearing names); only what
    // they resolve to changes.
    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.View

    readonly property color surface0: Kirigami.Theme.backgroundColor            // canvas
    readonly property color surface1: Kirigami.Theme.alternateBackgroundColor   // cards
    readonly property color surface2: Kirigami.Theme.backgroundColor            // raised controls
    readonly property color surface3: Kirigami.Theme.hoverColor                 // hover / selected
    readonly property color chrome:   Kirigami.Theme.backgroundColor            // rail / headers
    // A tint of the foreground, never Kirigami.Theme.separatorColor: that renders #FFFFFF in
    // every colour set of this scheme, so binding to it deletes every hairline on a light page.
    readonly property color hairline: Qt.rgba(Kirigami.Theme.textColor.r,
                                              Kirigami.Theme.textColor.g,
                                              Kirigami.Theme.textColor.b, 0.14)
    readonly property color textHi:   Kirigami.Theme.textColor
    readonly property color textLo:   Kirigami.Theme.disabledTextColor
    readonly property color textMute: Qt.rgba(Kirigami.Theme.disabledTextColor.r,
                                               Kirigami.Theme.disabledTextColor.g,
                                               Kirigami.Theme.disabledTextColor.b, 0.78)
    readonly property color novaCyan:   Kirigami.Theme.linkColor
    readonly property color novaBlue:   Kirigami.Theme.highlightColor
    // Is the active canvas dark? Drives the chat doodle backdrop's opacity so the
    // low-contrast pattern reads on both a graphite and a porcelain surface.
    readonly property bool isDark: (0.299 * Kirigami.Theme.backgroundColor.r
                                    + 0.587 * Kirigami.Theme.backgroundColor.g
                                    + 0.114 * Kirigami.Theme.backgroundColor.b) < 0.5
    readonly property color novaViolet: Kirigami.Theme.visitedLinkColor
    readonly property color accentText:   Kirigami.Theme.highlightedTextColor

    // Same focus ring as Mo Store, Welcome and the Installer. One focus treatment across MoOS.
    component FocusRing: MoUI.FocusRing {
        accentColor: root.novaBlue
    }
    // Mo AI is theme-adaptive (its palette comes from the active KDE scheme), so
    // the hero's baked aurora must follow suit: light themes (Tidal/Daylight) get
    // the pale variant, dark themes the deep one.
    readonly property bool isLight: Kirigami.Theme.backgroundColor.hslLightness > 0.5
    readonly property color okColor:   Kirigami.Theme.positiveTextColor
    readonly property color warnColor: Kirigami.Theme.neutralTextColor
    readonly property color badColor:  Kirigami.Theme.negativeTextColor
    // The system face, not a literal: MoOS already sets IBM Plex Sans as the system font,
    // so this renders identically today and stops overriding the user's choice tomorrow.
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
    function fs(px) { return Math.round(px * root.fontScale) }
    function typePx(px) { return design.typeSize(px, root.fontScale) }
    readonly property var design: MoUI.Tokens

    readonly property string uiFont: Qt.application.font.family

    // ── Endpoints ───────────────────────────────────────────────────────────
    // 8080 is Mo AI's FRONT DOOR (moai-gateway) and nothing else. It is always
    // on, and it routes each REQUEST to the selected allowlisted local engine
    // (Ollama or RamaLama, started on demand) or to the configured cloud
    // provider — whose API key it alone ever sees. This app names the route it
    // wants in the request's `model` field and never learns the key, provider,
    // unit, or port behind the door.
    //
    // It used to be an either/or: the local brain and the cloud proxy both
    // listened on 8080, so only one could run, the choice was a global setting,
    // and changing it meant bouncing systemd units. That is why `route` below
    // exists at all.
    //
    // The port is no longer a constant, because the machine is no longer assumed
    // to have one human on it. On a shared MoOS Cloud server every account gets
    // its own front door (see 60-moai-ports), and `moai` forwards the ports this
    // session actually resolved to.
    //
    // Before this, both developers' apps opened 127.0.0.1:8080 — so the SECOND
    // one reached the FIRST one's gateway, and with it the cloud key that the
    // gateway is meant to be the only thing that ever sees.
    //
    // The fallbacks below are the historical single-user values, so a desktop
    // that passes no arguments at all behaves exactly as it always has.
    function argPort(flag, fallback) {
        const argv = Qt.application.arguments
        const i = argv.indexOf(flag)
        if (i !== -1 && i + 1 < argv.length) {
            const n = parseInt(argv[i + 1], 10)
            if (!isNaN(n) && n > 0 && n < 65536)
                return n
        }
        return fallback
    }
    function argWindowDimension(axis, fallback) {
        const argv = Qt.application.arguments
        const i = argv.indexOf("--window-size")
        if (i === -1 || i + 1 >= argv.length)
            return fallback
        const match = /^(\d{3,4})x(\d{3,4})$/.exec(String(argv[i + 1]))
        if (!match)
            return fallback
        const value = parseInt(match[axis + 1], 10)
        const minimum = axis === 0 ? 720 : 540
        return value >= minimum && value <= 7680 ? value : fallback
    }
    function argLayoutDirection() {
        const argv = Qt.application.arguments
        const i = argv.indexOf("--layout-direction")
        if (i === -1 || i + 1 >= argv.length)
            return ""
        const value = String(argv[i + 1]).toLowerCase()
        return value === "rtl" || value === "ltr" ? value : ""
    }
    readonly property string layoutDirectionOverride: root.argLayoutDirection()
    readonly property bool moaiRtl: layoutDirectionOverride === "rtl"
        || (layoutDirectionOverride === ""
            && Qt.application.layoutDirection === Qt.RightToLeft)
    readonly property int gatewayPort: root.argPort("--gateway-port", 8080)
    readonly property int controlPort: root.argPort("--control-port", 8079)
    readonly property int agentPort:   root.argPort("--agent-port",   8077)

    readonly property string api: "http://127.0.0.1:" + root.gatewayPort + "/v1/chat/completions"
    readonly property string controlApi: "http://127.0.0.1:" + root.controlPort

    property var activeXhr: null
    property bool busy: false
    property bool brainStarting: false
    property var history: []            // [{role, content}] — last 12 turns
    property var pendingRuns: []        // moai-do actions the model just named
    property var pendingAttachments: [] // private imported image/text/file payloads
    property string lastSubmissionDisplay: ""
    property var lastSubmissionContent: null
    property bool retryPending: false
    property bool voiceRecording: false
    property string chatSessionId: "moai-desktop-" + Date.now().toString(36)
                                   + "-" + Math.floor(Math.random() * 0x1000000).toString(36)
    property string chatOpenClawSessionKey: ""
    property bool chatSessionStart: false
    property bool chatSidebarOpen: false
    property string agentDecision: ""
    property string panel: "chat"       // chat|device|apps|compat|remote|dev|agent

    // ── Which brain answers THIS conversation ───────────────────────────────
    // `route` is exactly what goes in the POST's `model` field, and it is the
    // whole contract with moai-gateway:
    //     "local" | "local:<model>" | "cloud" | "cloud:<model-id>"
    // Empty means "the configured default" — which is what we send until
    // /models tells us what that default resolves to.
    property string route: ""
    property string defaultRoute: ""
    property var localModels: []        // moai-control /models — selected engine's real inventory
    property var cloudModels: []        // …and from the PROVIDER's own /v1/models
    property string modelsError: ""
    property bool modelsLoading: false
    property bool pickerOpen: false

    // The download the picker offers. `pullModel` is the starter being fetched
    // right now (""=none), so its own row can draw the bar instead of the whole
    // list pretending to download.
    property string pullModel: ""
    property int pullPercent: 0
    property string pullError: ""

    readonly property bool routeIsCloud: root.route.indexOf("cloud") === 0
    readonly property bool routeIsLocal: root.route.indexOf("local") === 0
    readonly property bool routeIsHybrid: root.route.indexOf("hybrid") === 0
    property string hybridDecision: ""
    // The part after the FIRST colon — a model id may contain colons of its own
    // ("local:qwen3:4b").
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
        : root.routeIsHybrid ? (!!root.brains.local || !!root.brains.cloud)
        : root.defaultOnline

    // Live system state from moai-control.
    property var snap: ({})             // /scan
    property var plan: ({})             // snap.device_plan
    property bool scanning: false
    property string machineContext: ""

    title: "Mo AI"
    width: root.argWindowDimension(0, 940)
    height: root.argWindowDimension(1, 700)
    minimumWidth: 720
    minimumHeight: 540
    color: surface0
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    // ── The glass backdrop ──────────────────────────────────────────────────
    // The flagship app sits on a quiet depth scene: a deepening gradient, the
    // shared Tidal Horizon cut and the unchanged MoOS mark as a watermark. The
    // horizon is painted from the live Kirigami palette: Arena, Amethyst, Study
    // and every light partner receive their own accent pair without decoding
    // decorative rasters per launch. The identity mark and ring remain brand
    // artwork and degrade to the painted gradient if unavailable.
    // Declared as a sibling of the pageStack at z:-1, so it draws behind every
    // page. It is intentionally static: six perpetual decorative loops measured
    // 12.95% of a CPU core while idle and conveyed no state. Identity remains;
    // motion is reserved for direct interaction and honest live status.
    Item {
        id: ambient
        anchors.fill: parent
        z: -1

        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.lighter(root.surface0, 1.05) }
                GradientStop { position: 0.55; color: root.surface0 }
                GradientStop { position: 1.0; color: Qt.darker(root.surface0, 1.25) }
            }
        }

        // The watermark stays static at whisper opacity: presence without
        // decoration competing with content or background battery cost.
        Image {
            id: ambientMark
            source: "file:///usr/share/moos/moos-logo.png"
            width: Math.round(Math.min(parent.width, parent.height) * 0.5)
            height: width
            x: parent.width - width * 0.62
            y: parent.height - height * 0.60
            asynchronous: true
            fillMode: Image.PreserveAspectFit
            opacity: 0.05
        }
        Image {
            anchors.centerIn: ambientMark
            source: "file:///usr/share/moos/brand/ring.png"
            width: ambientMark.width * 1.35
            height: width
            asynchronous: true
            opacity: 0.10
        }
    }

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
        "• Rescue & diagnose: `moai-do rollback` (go back to the previous version if an " +
        "update broke something — atomic and reversible, applies on reboot), `moai-do " +
        "net-doctor` (network/DNS/Tailscale check — read-only), `moai-do gpu-report` (GPU " +
        "memory and what is holding it — read-only; useful when the remote is slow or an " +
        "app fails to open).\n" +
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
        "• Phone agent: `moai-do install-openclaw` installs and fully configures the " +
        "Telegram agent, local brain and Arabic voice. `moai-do setup-brain` repairs or " +
        "prepares only the local model and speech engines. Both are fixed, confirmed actions.\n" +
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
    readonly property string offlineHelp: root.moaiRtl
        ? ("‏العقل المحلي غير مشغّل.\n\n" +
           "اضغط **«شغّل العقل المحلي»** بالأسفل — أو شغّل `moai-start` في الطرفية.\n\n" +
           "ثم أعد المحاولة.")
        : ("‎The local brain is off.\n\n" +
           "Tap **“Start local brain”** below — or run `moai-start` in a terminal.\n\n" +
           "Then try again.")

    readonly property string startingHelp: root.moaiRtl
        ? ("‏العقل المحلي يبدأ الآن… أول تشغيل يُحمّل النموذج (~2.5GB) وقد يأخذ دقائق.\n\n" +
           "سأصبح جاهزاً تلقائياً عند الانتهاء.")
        : ("‎The local brain is starting… the first run downloads the model (~2.5 GB) and may take a few minutes.\n\n" +
           "I'll be ready automatically once it finishes.")

    // MoOS speaks the user's ONE language. The greeting used to stack Arabic and
    // English; now it shows only the session language (RTL ⇒ Arabic), the same
    // signal the whole app mirrors on. The model still replies in whatever
    // language the user writes in — that is per-message, not the static greeting.
    // Preserve the compact 720 px layout, but use the room available on a
    // desktop/4K window for a readable workspace sidebar instead of scaling a
    // phone-sized icon rail across every form factor.
    readonly property bool workspaceSidebarExpanded: width >= 1120
    function local(ar, en) { return root.moaiRtl ? ar : en }
    function localLegacy(value) {
        var text = String(value || "")
        var pair = text.split(/\s+\|\s+/)
        return pair.length > 1 ? (root.moaiRtl ? pair[0] : pair.slice(1).join(" | "))
                               : text
    }
    readonly property string greetingText: moaiRtl
        ? ("‏مرحباً! أنا **Mo AI** — مساعد MoOS.\n\n" +
           "أقدر أصلّح التعريفات، أحدّث النظام، أثبّت أي تطبيق، أنظّف الجهاز، وأشغّل Mo PC Remote.\n\n" +
           "_اسألني، أو استخدم الشريط الجانبي._")
        : ("‎Hi! I'm **Mo AI** — your MoOS assistant.\n\n" +
           "I can fix drivers, update the system, install any app, clean things up, and run Mo PC Remote.\n\n" +
           "_Ask me, or use the side rail._")

    readonly property var starters: [
        { ar: "حدّث نظامي",     en: "Update my system", icon: "moos-safe-update-symbolic", hint: root.local("آمن وموقّع", "signed & safe"), send: "حدّث نظام MoOS من فضلك" },
        { ar: "افحص جهازي",     en: "Check my device",  icon: "moos-cpu-symbolic",         hint: root.local("تعريفات وصحّة", "drivers & health"), send: "افحص جهازي وقل لي إذا في مشاكل تعريفات أو تحديثات" },
        { ar: "سرّع ونظّف",      en: "Speed up & clean", icon: "moos-optimize-symbolic",    hint: root.local("مساحة وذاكرة", "space & memory"), send: "نظّف النظام وسرّعه من فضلك" },
        { ar: "صلّح الصوت",      en: "Fix audio",        icon: "moos-audio-symbolic",       hint: root.local("صوت لا يعمل", "no sound"), send: "الصوت لا يعمل عندي، ساعدني" }
    ]

    // ── The rail ────────────────────────────────────────────────────────────
    readonly property var navItems: [
        { id: "chat",   icon: "moos-ai-symbolic",           ar: "المحادثة", en: "Chat" },
        { id: "device", icon: "moos-gpu-symbolic",          ar: "الجهاز",   en: "Device" },
        { id: "apps",   icon: "moos-install-symbolic",      ar: "التطبيقات", en: "Apps" },
        { id: "compat", icon: "moos-gaming-symbolic",       ar: "التوافق",  en: "Compat" },
        { id: "remote", icon: "moos-phone-symbolic",        ar: "التحكّم",   en: "Remote" },
        { id: "dev",    icon: "moos-code-symbolic", ar: "المطوّر",  en: "Dev" },
        { id: "agent",  icon: "moos-identity-symbolic",     ar: "الوكيل",   en: "Agent" }
    ]

    // Compatibility targets. `key` matches moai-control's /scan compatibility
    // map, so "Ready" is read from the machine, never assumed.
    readonly property var compatCatalog: [
        { key: "steam",      title: "Steam + Proton", ar: "ألعاب Windows", en: "Windows games",
          url: "moos://do/setup-gaming", icon: "moos-gaming-symbolic" },
        { key: "bottles",    title: "Bottles", ar: "تطبيقات Windows", en: "Windows apps",
          url: "moos://do/setup-windows", icon: "moos-system-symbolic" },
        { key: "waydroid",   title: "Waydroid", ar: "تطبيقات Android", en: "Android apps",
          url: "moos://do/setup-waydroid", icon: "moos-android-apps-symbolic" },
        { key: "kdeconnect", title: "KDE Connect", ar: "ربط الهاتف", en: "Phone integration",
          url: "moos://apps/install/org.kde.kdeconnect", icon: "moos-phone-symbolic" }
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
                if (["chat", "device", "apps", "compat", "remote", "dev", "agent"].indexOf(p) !== -1)
                    root.panel = p
            }
        }
        const workspaceIndex = argv.indexOf("--workspace")
        if (workspaceIndex !== -1 && workspaceIndex + 1 < argv.length) {
            const workspace = argv[workspaceIndex + 1]
            if (["conversations", "projects", "tasks", "terminal"].indexOf(workspace) !== -1) {
                root.panel = "agent"
                root.agentWorkspaceTab = workspace
            }
        }
        const projectIndex = argv.indexOf("--project")
        if (projectIndex !== -1 && projectIndex + 1 < argv.length) {
            const projectId = argv[projectIndex + 1]
            if (/^[0-9a-f]{20}$/.test(projectId)) {
                root.panel = "agent"
                root.agentWorkspaceTab = "projects"
                Qt.callLater(function () { root.agentOpenProject(projectId) })
            }
        }
        const routeIndex = argv.indexOf("--route")
        if (routeIndex !== -1 && routeIndex + 1 < argv.length) {
            const requestedRoute = argv[routeIndex + 1]
            if (requestedRoute === "hybrid"
                    || requestedRoute.indexOf("local") === 0
                    || requestedRoute.indexOf("cloud") === 0)
                root.route = requestedRoute
        }
        const sessionIdIndex = argv.indexOf("--session-id")
        const sessionKeyIndex = argv.indexOf("--session-key")
        if (sessionIdIndex !== -1 && sessionIdIndex + 1 < argv.length
                && sessionKeyIndex !== -1 && sessionKeyIndex + 1 < argv.length) {
            const startupSessionId = String(argv[sessionIdIndex + 1])
            const startupSessionKey = String(argv[sessionKeyIndex + 1])
            if (/^[0-9a-fA-F-]{36}$/.test(startupSessionId)
                    && /^[A-Za-z0-9_.:-]{1,180}$/.test(startupSessionKey)) {
                root.panel = "chat"
                Qt.callLater(function () {
                    root.agentOpenPrimary(startupSessionId, startupSessionKey,
                                          root.local("محادثة موحّدة", "Unified conversation"))
                })
            }
        }
        if (argv.indexOf("--open-history") !== -1) {
            root.panel = "chat"
            root.chatSidebarOpen = true
            Qt.callLater(function () { root.agentLoadStatus() })
        }
        root.chatSessionStart = argv.indexOf("--session-start") !== -1
        const settingsIndex = argv.indexOf("--settings")
        if (settingsIndex !== -1 && settingsIndex + 1 < argv.length) {
            const settingsSection = String(argv[settingsIndex + 1])
            if (["models", "providers", "openclaw", "telegram", "whatsapp",
                 "voice", "permissions", "memory", "projects", "terminal",
                 "privacy", "appearance"].indexOf(settingsSection) !== -1) {
                root.cfgTab = settingsSection
                root.settingsOpen = true
            }
        }
        const promptIndex = argv.indexOf("--prompt")
        if (promptIndex !== -1 && promptIndex + 1 < argv.length) {
            const startupPrompt = String(argv[promptIndex + 1]).trim()
            if (startupPrompt !== "" && startupPrompt.length <= 8000) {
                root.panel = "chat"
                Qt.callLater(function () { root.sendPrompt(startupPrompt) })
            }
        }
    }

    FileDialog {
        id: attachmentDialog
        title: root.local("أرفق صورة أو ملفاً", "Attach an image or file")
        fileMode: FileDialog.OpenFile
        onAccepted: root.importAttachment(selectedFile.toString())
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
        if (typeof heroOrb !== "undefined") heroOrb.pulse()
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
                root.searchNote = root.local("تعذّر البحث", "Search failed")
                return
            }
            try {
                const r = JSON.parse(xhr.responseText)
                const list = r.results || []
                for (let i = 0; i < list.length; i++)
                    searchModel.append(list[i])
                if (list.length === 0)
                    root.searchNote = root.local("لا نتائج", "No results")
                else if (r.source === "local")
                    root.searchNote = root.local("بدون إنترنت — نتائج محلية",
                                                 "Offline — local results")
            } catch (e) {
                root.searchNote = root.local("تعذّر قراءة النتائج",
                                             "Couldn't read results")
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
        const re = /moai-do\s+(update|fix-audio|check-drivers|optimize|hw-report|diagnose-services|inspect-boot|update-firmware|install-nvidia|setup-waydroid|setup-gaming|setup-windows|install-codex|install-claude|install-opencode|install-openclaw|setup-brain|rollback|net-doctor|gpu-report)\b/g
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
        chatSessionId = "moai-desktop-" + Date.now().toString(36)
                        + "-" + Math.floor(Math.random() * 0x1000000).toString(36)
        chatOpenClawSessionKey = ""
        agentDecision = ""
        lastSubmissionDisplay = ""
        lastSubmissionContent = null
        retryPending = false
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

    function regenerateLast() {
        if (root.busy || root.lastSubmissionContent === null
                || root.lastSubmissionDisplay === "") return
        while (root.history.length > 0) {
            const removed = root.history.pop()
            if (removed.role === "user") break
        }
        while (chatModel.count > 0) {
            const role = chatModel.get(chatModel.count - 1).role
            chatModel.remove(chatModel.count - 1)
            if (role === "user") break
        }
        root.retryPending = true
        root.send()
    }

    function sendPrompt(msg) {
        root.panel = "chat"
        input.text = msg
        send()
    }

    function send() {
        const replay = root.retryPending
        const msg = replay ? root.lastSubmissionDisplay : input.text.trim()
        if (msg === "" || busy)
            return
        root.panel = "chat"
        const attachments = replay ? [] : root.pendingAttachments.slice(0)
        const replayParts = replay && Array.isArray(root.lastSubmissionContent)
            ? root.lastSubmissionContent : []
        const hasImage = replay
            ? replayParts.some(function (part) { return part.type === "image_url" })
            : attachments.some(function (item) { return item.content_type === "image" })
        let selectedRoute = root.route !== "" ? root.route : "default"
        if (hasImage) {
            const vision = root.localModels.filter(function (model) {
                return (model.input || []).indexOf("image") >= 0
            })
            if (root.routeIsLocal || root.routeIsHybrid) {
                if (vision.length === 0) {
                    root.agentError = root.local(
                        "الصورة محفوظة ولم تُرسل: لا يوجد نموذج محلي يعلن دعم الصور.",
                        "Image kept unsent: no local model advertises image input.")
                    return
                }
                selectedRoute = vision[0].id
            } else {
                const selectedCloud = root.cloudModels.filter(function (model) {
                    return model.id === selectedRoute
                           && (model.input || []).indexOf("image") >= 0
                })
                if (selectedCloud.length === 0) {
                    root.agentError = root.local(
                        "الصورة محفوظة ولم تُرسل: النموذج السحابي لا يعلن دعم الصور.",
                        "Image kept unsent: the cloud model does not advertise image input.")
                    return
                }
            }
        }
        root.agentError = ""
        if (!replay) input.text = ""
        const attachmentNames = attachments.map(function (item) { return item.name }).join(", ")
        const displayText = replay ? msg : msg
            + (attachmentNames === "" ? "" : "\n📎 " + attachmentNames)
        chatModel.append({ role: "user", text: displayText })
        let userContent = replay ? root.lastSubmissionContent : msg
        if (!replay && attachments.length > 0) {
            const parts = [{ type: "text", text: msg }]
            for (let attachmentIndex = 0; attachmentIndex < attachments.length; ++attachmentIndex) {
                const attachment = attachments[attachmentIndex]
                if (attachment.content_type === "image") {
                    parts.push({ type: "image_url", image_url: { url: attachment.content } })
                } else if (attachment.content_type === "text") {
                    parts.push({ type: "text", text: "\n\n--- " + attachment.name
                        + " ---\n" + attachment.content })
                } else {
                    parts.push({ type: "text", text: "\n\nAttached file: " + attachment.name
                        + " (" + attachment.mime + ", " + attachment.size + " bytes)" })
                }
            }
            userContent = parts
        }
        root.retryPending = false
        root.lastSubmissionDisplay = displayText
        root.lastSubmissionContent = userContent
        history.push({ role: "user", content: userContent })
        root.pendingAttachments = []
        trimHistory()
        chatModel.append({ role: "typing", text: "…" })
        const idx = chatModel.count - 1
        busy = true
        pendingRuns = []

        let acc = ""
        let sawData = false
        // How much the model spent thinking on its second channel. Only used to
        // explain an empty answer — see the reasoning_content note below.
        let reasonedChars = 0
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
                        // A REASONING model answers on a second channel.
                        //
                        // qwen3 and its family return their deliberation in
                        // `reasoning_content` and the actual answer in `content`.
                        // This app only ever read `content`, so on a CPU-only box
                        // the result was a spinner that sat still for a minute and
                        // then a blank bubble — measured here: qwen3:8b spent 70
                        // tokens (57 of them reasoning) to answer "OK", and at
                        // ~4 tok/s a 220-token budget ran out mid-thought and
                        // produced NOTHING visible.
                        //
                        // Counting it is what turns that silence into a diagnosis
                        // below. It is deliberately not appended to the answer:
                        // deliberation is not the reply, and splicing it in would
                        // put the model's scratch work in the user's chat.
                        if (ch && ch.delta && ch.delta.reasoning_content)
                            reasonedChars += ch.delta.reasoning_content.length
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
            if (root.routeIsHybrid) {
                const chosen = xhr.getResponseHeader("X-MoAI-Route") || ""
                const reason = xhr.getResponseHeader("X-MoAI-Route-Reason") || ""
                root.hybridDecision = chosen === ""
                    ? "" : chosen + (reason === "" ? "" : " · " + reason)
            }
            const agentPath = xhr.getResponseHeader("X-MoAI-Agent") || ""
            root.agentDecision = agentPath === "openclaw"
                ? root.local("وكيل موحّد", "Unified agent")
                : agentPath === "direct-fallback"
                    ? root.local("رد مباشر احتياطي", "Direct fallback") : ""

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
                // "I couldn't generate a reply" is true but useless when the real
                // story is that the model DID answer — on a channel this app does
                // not show — and ran out of budget before reaching the answer.
                // Say which it was, because the two have different fixes.
                const help = !root.serverUp
                    ? (root.brainStarting ? root.startingHelp : root.offlineHelp)
                    : (reasonedChars > 0
                       ? "هذا نموذج تفكير: استهلك ميزانيته في التفكير قبل أن يكتب الجواب. "
                         + "اختر نموذجاً مباشراً (qwen2.5:7b-instruct) — أسرع على هذا الخادم بلا كرت شاشة.\n"
                         + "This is a reasoning model: it spent its budget thinking and never "
                         + "reached the answer. Pick a direct model (qwen2.5:7b-instruct) — on this "
                         + "GPU-less server it is measurably faster."
                       : root.local("لم أستطع توليد رد، حاول مجدداً.",
                                    "I couldn't generate a reply — please try again."))
                chatModel.set(idx, { role: "assistant", text: help })
                root.flashMood(root.serverUp ? "warning" : "error")
            }
        }
        const request = {
            // THE ROUTE. moai-gateway reads this and sends the request to the
            // local brain or to the cloud provider accordingly; "default" (or an
            // empty route, before /models has answered) means "whatever
            // ~/.config/moai/config.json says", which is the old behaviour.
            model: selectedRoute,
            messages: [{ role: "system", content: systemPrompt + root.machineContext }]
                          .concat(history),
            stream: true
        }
        request.moai = {
            privacy: "standard",
            agent: true,
            session: root.chatSessionId
        }
        if (root.chatOpenClawSessionKey !== "")
            request.moai.session_key = root.chatOpenClawSessionKey
        xhr.send(JSON.stringify(request))
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
                root.modelsError = root.local("تعذّر جلب النماذج",
                                              "Couldn't reach the model list")
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
                root.modelsError = root.local("تعذّر قراءة النماذج",
                                              "Couldn't read the model list")
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

    // ── Tapping a starter that is not on this machine yet ────────────────────
    //
    // The row has always said "one-tap download". Until now the tap only set the
    // route, and the first chat came back with a terminal-only pull instruction.
    // The tap now asks the selected engine through the control API, shows its real
    // progress, and picks the brain when it lands. The picker STAYS OPEN while it
    // downloads: closing it over a running download is how you get a user who
    // thinks nothing happened and taps a second brain.
    function pickOrPull(entry) {
        if (entry.pulled) {
            root.pickRoute(entry.id)
            return
        }
        if (root.pullModel !== "")     // one at a time; the backend serialises too
            return
        const bare = entry.id.indexOf("local:") === 0 ? entry.id.substring(6) : entry.id
        root.pullError = ""
        root.pullPercent = 0
        root.pullModel = bare
        const xhr = new XMLHttpRequest()
        xhr.open("POST", controlApi + "/pull")
        xhr.setRequestHeader("X-Moai-Control", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            let res = {}
            try { res = JSON.parse(xhr.responseText) } catch (e) { res = {} }
            if (xhr.status !== 200 || res.state === "error") {
                root.pullError = res.error || root.local("تعذّر بدء التنزيل",
                                                        "Could not start the download")
                root.pullModel = ""
                return
            }
            pullPoll.pickWhenDone = entry.id
            pullPoll.start()
        }
        xhr.send(JSON.stringify({ model: bare }))
    }

    // Remove a locally-pulled brain from Settings. The backend refuses anything
    // that is not actually installed, and refuses the active brain, so this only
    // ever frees disk for a model the user is done with. `deleteBusy` holds the
    // id being removed so its row can show a spinner and disable its button.
    property string deleteBusy: ""
    function deleteModel(id) {
        const bare = id.indexOf("local:") === 0 ? id.substring(6) : id
        if (root.deleteBusy !== "")
            return
        root.deleteBusy = bare
        root.cfgError = ""
        const xhr = new XMLHttpRequest()
        xhr.open("POST", controlApi + "/delete")
        xhr.setRequestHeader("X-Moai-Control", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            let res = {}
            try { res = JSON.parse(xhr.responseText) } catch (e) { res = {} }
            root.deleteBusy = ""
            if (xhr.status !== 200 || !res.ok) {
                root.cfgError = res.error || root.local("تعذّر الحذف",
                                                       "Could not delete the model")
                return
            }
            root.loadModels()          // the row must disappear now
        }
        xhr.send(JSON.stringify({ model: bare }))
    }

    // ── Diagnose & fix the system, safely ────────────────────────────────────
    // Ask the control API to reason about system health (it runs moos-selfcheck)
    // and hand back the broken checks plus a curated menu of SAFE moai-do repairs.
    // The diagnosis is read-only; each repair the UI offers is a moos://do/<id>
    // that still goes through moai-do's confirm + Polkit — never a free command.
    property var diagResult: ({})
    property bool diagLoading: false
    // The safe repair menu — always shown, and the fallback before a diagnose run
    // has returned. Mirrors moai-control's /diagnose fixes; each id is a REAL
    // moai-do action (moos://do/<id> → confirm + Polkit). read=true only shows
    // information. Nothing here is a placeholder.
    readonly property var defaultRepairs: [
        { id: "diagnose-services", label: root.local("الخدمات الفاشلة", "Failed services"), read: true },
        { id: "check-drivers",     label: root.local("الكرت والتعريف", "GPU & drivers"), read: true },
        { id: "inspect-boot",      label: root.local("حالة الإقلاع", "Boot status"), read: true },
        { id: "net-doctor",        label: root.local("تشخيص الشبكة", "Network doctor"), read: true },
        { id: "gpu-report",        label: root.local("ذاكرة كرت الشاشة", "GPU memory"), read: true },
        { id: "fix-audio",         label: root.local("إصلاح الصوت", "Fix audio"), read: false },
        { id: "optimize",          label: root.local("تنظيف وتحرير مساحة", "Clean & free space"), read: false },
        { id: "rollback",          label: root.local("الرجوع لنسخة سابقة", "Roll back"), read: false },
        { id: "update",            label: root.local("تحديث MoOS", "Update MoOS"), read: false }
    ]
    function diagnoseSystem() {
        root.diagLoading = true
        const xhr = new XMLHttpRequest()
        xhr.open("GET", controlApi + "/diagnose")
        xhr.setRequestHeader("X-Moai-Control", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            root.diagLoading = false
            let res = {}
            try { res = JSON.parse(xhr.responseText) } catch (e) { res = {} }
            root.diagResult = res
        }
        xhr.send()
    }

    Timer {
        id: pullPoll
        property string pickWhenDone: ""
        interval: 1200
        repeat: true
        onTriggered: {
            const xhr = new XMLHttpRequest()
            xhr.open("GET", controlApi + "/pull")
            xhr.setRequestHeader("X-Moai-Control", "1")
            xhr.onreadystatechange = function () {
                if (xhr.readyState !== XMLHttpRequest.DONE || xhr.status !== 200)
                    return
                let s = {}
                try { s = JSON.parse(xhr.responseText) } catch (e) { return }
                root.pullPercent = s.percent || 0
                if (s.state === "running")
                    return
                pullPoll.stop()
                root.pullModel = ""
                if (s.state === "error") {
                    root.pullError = s.error || root.local("فشل التنزيل",
                                                          "The download failed")
                    return
                }
                // Landed. Re-ask what this machine has (the row must stop saying
                // "download") and switch to the brain the user actually asked for.
                root.loadModels()
                root.pickRoute(pullPoll.pickWhenDone)
            }
            xhr.send()
        }
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

        // Ask the orb to play its "heard you" pulse. Living inside the
        // component means it is always in scope, unlike a root function that
        // tries to reach a nested id (which is why `orbPulse.restart()` used
        // to throw "orbPulse is not defined").
        signal pulse()

        readonly property bool alive: mood !== "offline"
        readonly property color accent:
              mood === "success" ? root.okColor
            : mood === "warning" ? root.warnColor
            : mood === "error"   ? root.badColor
            : mood === "offline" ? root.textMute
            : root.novaBlue

        implicitWidth: root.fs(44)
        implicitHeight: root.fs(44)

        // Halo
        Shape {
            anchors.centerIn: parent
            width: orb.width * 1.75
            height: orb.height * 1.75
            scale: orb.haloScale
            opacity: orb.alive ? 0.5 : 0.16
            Behavior on opacity { NumberAnimation { duration: root.motionEnabled ? design.motionGeometry : 0 } }
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
            Behavior on opacity { NumberAnimation { duration: root.motionEnabled ? design.motionGeometry : 0 } }
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
                Behavior on width { NumberAnimation { duration: root.motionEnabled ? design.motionGeometry : 0; easing.type: Easing.OutCubic } }
                Behavior on color { ColorAnimation { duration: root.motionEnabled ? design.motionGeometry : 0 } }
            }
        }

        // Idle: a slow breath.
        SequentialAnimation {
            running: root.visible && orb.mood === "idle" && !orbPulse.running && root.motionEnabled
            loops: Animation.Infinite
            onStopped: { orb.coreScale = 1.0; orb.haloScale = 1.0 }
            ParallelAnimation {
                NumberAnimation { target: orb; property: "coreScale"; to: 1.03; duration: root.motionEnabled ? 1500 : 0; easing.type: Easing.InOutSine }
                NumberAnimation { target: orb; property: "haloScale"; to: 1.10; duration: root.motionEnabled ? 1500 : 0; easing.type: Easing.InOutSine }
            }
            ParallelAnimation {
                NumberAnimation { target: orb; property: "coreScale"; to: 1.0; duration: root.motionEnabled ? 1500 : 0; easing.type: Easing.InOutSine }
                NumberAnimation { target: orb; property: "haloScale"; to: 1.0; duration: root.motionEnabled ? 1500 : 0; easing.type: Easing.InOutSine }
            }
        }

        // Thinking: the ring turns and the halo throbs.
        NumberAnimation {
            running: root.visible && orb.mood === "thinking" && root.motionEnabled
            target: orb; property: "ringAngle"
            from: 0; to: 360; duration: root.motionEnabled ? 2600 : 0
            loops: Animation.Infinite
            onStopped: orb.ringAngle = 0
        }
        SequentialAnimation {
            running: root.visible && orb.mood === "thinking" && root.motionEnabled
            loops: Animation.Infinite
            onStopped: orb.haloScale = 1.0
            NumberAnimation { target: orb; property: "haloScale"; to: 1.16; duration: root.motionEnabled ? 620 : 0; easing.type: Easing.InOutSine }
            NumberAnimation { target: orb; property: "haloScale"; to: 0.98; duration: root.motionEnabled ? 620 : 0; easing.type: Easing.InOutSine }
        }

        // Attentive: leans in and holds.
        NumberAnimation {
            running: root.visible && orb.mood === "attentive"
            target: orb; property: "coreScale"
            to: 1.07; duration: root.motionEnabled ? design.motionGeometry : 0; easing.type: Easing.OutBack
            onStopped: if (orb.mood !== "attentive") orb.coreScale = 1.0
        }

        // An honest pulse when the user launches something: launching is not
        // the same as succeeding, so this says "heard you", not "done".
        SequentialAnimation {
            id: orbPulse
            NumberAnimation { target: orb; property: "coreScale"; from: 1.0; to: 1.13; duration: root.motionEnabled ? design.motionPress : 0; easing.type: Easing.OutQuad }
            NumberAnimation { target: orb; property: "coreScale"; to: 1.0; duration: root.motionEnabled ? design.motionGeometry : 0; easing.type: Easing.InQuad }
            onRunningChanged: if (!running) orb.coreScale = 1.0
        }
        onPulse: orbPulse.restart()
    }

    // A card.
    component Card: Rectangle {
        default property alias content: inner.data
        property alias pad: inner.anchors.margins
        radius: design.radiusCard
        color: root.surface1
        border.width: 1
        border.color: root.hairline
        implicitHeight: inner.childrenRect.height + 2 * inner.anchors.margins
        Item {
            id: inner
            anchors.fill: parent
            anchors.margins: design.space4
        }
    }

    // The one button style in the app.
    component MoButton: MoUI.Button {
        id: btn
        property bool danger: false
        property bool enabled_: true
        destructive: btn.danger
        enabled: btn.enabled_
        compact: true
        cornerRadius: design.radiusControl
        iconPixelSize: root.typePx(14)
        fontPixelSize: root.typePx(13)
        motionEnabled: root.motionEnabled
        surfaceColor: root.surface2
        accentColor: root.novaBlue
        dangerColor: root.badColor
        textColor: root.textHi
        mutedTextColor: root.textLo
        accentForegroundColor: root.accentText
        outlineColor: root.hairline
    }

    // Keyboard/screen-reader seam for every hand-drawn clickable surface that
    // is not already a MoButton. MouseArea alone is invisible to Tab and AT;
    // keeping this in one component also guarantees the same 2 px focus ring
    // and Enter/Space behaviour across rails, cards, pickers and settings.
    component ActionArea: MouseArea {
        id: actionArea
        required property string actionName
        property bool checkable: false
        property bool checked: false
        property int actionRole: checkable ? Accessible.RadioButton : Accessible.Button
        property real focusRadius: root.fs(10)
        signal triggered()

        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        activeFocusOnTab: enabled && visible
        Accessible.role: actionRole
        Accessible.name: actionName
        Accessible.checked: checked
        Keys.onReturnPressed: triggered()
        Keys.onEnterPressed: triggered()
        Keys.onSpacePressed: triggered()
        onClicked: triggered()

        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            radius: actionArea.focusRadius + 3
            color: "transparent"
            border.width: 2
            border.color: root.novaBlue
            visible: actionArea.activeFocus
            z: 99
        }
    }

    // A status pill: reads state from the machine, never asserts it.
    component StatusPill: Rectangle {
        property bool good: false
        property string goodText: ""
        property string badText: ""
        implicitHeight: root.fs(22)
        implicitWidth: pillText.implicitWidth + 20
        radius: height / 2
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
            font.pixelSize: root.typePx(11)
            font.weight: Font.DemiBold
        }
    }

    component SectionTitle: Text {
        color: root.textHi
        font.family: root.uiFont
        font.pixelSize: root.typePx(17)
        font.weight: Font.DemiBold
    }

    component SectionNote: Text {
        color: root.textLo
        font.family: root.uiFont
        font.pixelSize: root.typePx(12)
        wrapMode: Text.Wrap
    }

    // ── ChatDoodle ───────────────────────────────────────────────────────────
    // The reusable chat backdrop: a WhatsApp-style tech line-art tile (AI, code,
    // terminal, files, security, automation, Telegram, chips, cloud, MoOS) tinted
    // to the live theme's text colour, with the exact Mo AI mark woven in and left
    // UNRECOLOURED. Purely decorative — no input, no layout. Instantiated BOTH over
    // the welcome aurora (below the hero content) AND behind the message list, so
    // the pattern reads across the whole conversation surface, dark and light.
    component ChatDoodle: Item {
        id: doodleRoot
        clip: true
        // Clearly visible as texture, never enough to compete with message text.
        property real lineOpacity: root.isDark ? 0.13 : 0.12
        property real markOpacity: root.isDark ? 0.11 : 0.10

        Image {
            id: doodleTile
            anchors.fill: parent
            source: Qt.resolvedUrl("chat-doodles.svg")
            fillMode: Image.Tile
            horizontalAlignment: Image.AlignLeft
            verticalAlignment: Image.AlignTop
            sourceSize: Qt.size(220, 220)
            smooth: true
            asynchronous: true
            opacity: doodleRoot.lineOpacity
            // Static, blur-free colorization — recolours the white strokes to the
            // theme text colour without allocating per-frame GPU buffers.
            layer.enabled: true
            layer.effect: MultiEffect {
                colorization: 1.0
                colorizationColor: root.textHi
            }
        }
        Repeater {
            id: mark
            readonly property int step: 264
            readonly property int cols: Math.max(1, Math.ceil(doodleTile.width / step))
            readonly property int rows: Math.max(1, Math.ceil(doodleTile.height / step))
            model: cols * rows
            delegate: Kirigami.Icon {
                source: "moos-moai"
                width: 34
                height: 34
                smooth: true
                opacity: doodleRoot.markOpacity
                x: (index % mark.cols) * mark.step + mark.step / 2 - width / 2 + 60
                y: Math.floor(index / mark.cols) * mark.step + mark.step / 2 - height / 2 + 30
            }
        }
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
        LayoutMirroring.enabled: root.moaiRtl
        LayoutMirroring.childrenInherit: true

        RowLayout {
            anchors.fill: parent
            spacing: 0

            // ── The rail ────────────────────────────────────────────────────
            Rectangle {
                Layout.preferredWidth: root.workspaceSidebarExpanded
                    ? root.fs(188) : root.fs(76)
                Layout.fillHeight: true
                color: root.chrome
                Behavior on Layout.preferredWidth {
                    NumberAnimation {
                        duration: root.motionEnabled ? design.motionGeometry : 0
                        easing.type: Easing.OutCubic
                    }
                }

                Rectangle {
                    anchors.right: parent.right
                    width: 1; height: parent.height
                    color: root.hairline
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.topMargin: 14
                    anchors.bottomMargin: 12
                    spacing: design.space1

                    MoOrb {
                        id: heroOrb
                        Layout.alignment: root.workspaceSidebarExpanded
                            ? Qt.AlignLeft : Qt.AlignHCenter
                        Layout.leftMargin: root.workspaceSidebarExpanded ? root.fs(18) : 0
                        Layout.preferredWidth: root.fs(42)
                        Layout.preferredHeight: root.fs(42)
                        Layout.bottomMargin: 4
                        mood: root.mood
                    }

                    Text {
                        Layout.alignment: root.workspaceSidebarExpanded
                            ? Qt.AlignLeft : Qt.AlignHCenter
                        Layout.leftMargin: root.workspaceSidebarExpanded ? root.fs(18) : 0
                        Layout.bottomMargin: 8
                        // Bilingual by session direction, like the rest of the app —
                        // it was Arabic-only, breaking the convention on English sessions.
                        text: root.moaiRtl
                              ? (root.serverUp ? "متصل" : root.brainStarting ? "يبدأ…" : "غير متصل")
                              : (root.serverUp ? "Online" : root.brainStarting ? "Starting…" : "Offline")
                        color: root.serverUp ? root.okColor
                             : root.brainStarting ? root.novaBlue : root.textMute
                        font.family: root.uiFont
                        font.pixelSize: root.typePx(9)
                        font.weight: Font.DemiBold
                    }

                    Repeater {
                        model: root.navItems
                        delegate: Item {
                            id: nav
                            required property var modelData
                            readonly property bool active: root.panel === modelData.id
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.fs(54)

                            Rectangle {   // active indicator
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                width: 3
                                height: nav.active ? 26 : 0
                                radius: root.fs(2)
                                color: root.novaCyan
                                Behavior on height { NumberAnimation { duration: root.motionEnabled ? design.motionPress : 0; easing.type: Easing.OutCubic } }
                            }

                            Rectangle {
                                anchors.centerIn: parent
                                width: root.workspaceSidebarExpanded
                                    ? parent.width - root.fs(20) : root.fs(54)
                                height: root.fs(46)
                                radius: design.radiusControl
                                color: nav.active
                                     ? Qt.rgba(root.novaBlue.r, root.novaBlue.g,
                                               root.novaBlue.b, 0.16)
                                     : navMa.containsMouse ? root.surface2 : "transparent"
                                Behavior on color { ColorAnimation { duration: root.motionEnabled ? design.motionPress : 0 } }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: root.workspaceSidebarExpanded
                                        ? root.fs(14) : 0
                                    anchors.rightMargin: root.workspaceSidebarExpanded
                                        ? root.fs(12) : 0
                                    spacing: root.workspaceSidebarExpanded ? design.space3 : 0
                                    Kirigami.Icon {
                                        Layout.alignment: root.workspaceSidebarExpanded
                                            ? Qt.AlignVCenter : Qt.AlignHCenter | Qt.AlignTop
                                        Layout.preferredWidth: root.fs(20)
                                        Layout.preferredHeight: root.fs(20)
                                        source: nav.modelData.icon
                                        color: nav.active ? root.novaCyan : root.textMute
                                    }
                                    Text {
                                        Layout.fillWidth: root.workspaceSidebarExpanded
                                        Layout.alignment: root.workspaceSidebarExpanded
                                            ? Qt.AlignVCenter : Qt.AlignHCenter | Qt.AlignBottom
                                        text: root.moaiRtl
                                            ? nav.modelData.ar : nav.modelData.en
                                        color: nav.active ? root.textHi : root.textMute
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(root.workspaceSidebarExpanded ? 12 : 9)
                                        font.weight: nav.active ? Font.DemiBold : Font.Normal
                                        horizontalAlignment: root.workspaceSidebarExpanded
                                            ? Text.AlignLeft : Text.AlignHCenter
                                        elide: Text.ElideRight
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

                            ActionArea {
                                id: navMa
                                anchors.fill: parent
                                actionName: root.moaiRtl
                                    ? nav.modelData.ar : nav.modelData.en
                                checkable: true
                                checked: nav.active
                                focusRadius: root.fs(12)
                                onTriggered: root.panel = nav.modelData.id
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    // Settings
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.fs(46)
                        Rectangle {
                            anchors.centerIn: parent
                            width: root.workspaceSidebarExpanded
                                ? parent.width - root.fs(20) : root.fs(54)
                            height: root.fs(40)
                            radius: design.radiusControl
                            color: gearMa.containsMouse ? root.surface2 : "transparent"
                            Behavior on color { ColorAnimation { duration: root.motionEnabled ? design.motionPress : 0 } }
                            Kirigami.Icon {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: root.workspaceSidebarExpanded
                                    ? root.fs(14) : (parent.width - width) / 2
                                width: 19; height: 19
                                source: "moos-settings-symbolic"
                                color: root.textMute
                            }
                            Text {
                                visible: root.workspaceSidebarExpanded
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: root.fs(48)
                                anchors.right: parent.right
                                anchors.rightMargin: root.fs(12)
                                text: root.local("الإعدادات", "Settings")
                                color: root.textMute
                                font.family: root.uiFont
                                font.pixelSize: root.typePx(12)
                                elide: Text.ElideRight
                            }
                        }
                        ActionArea {
                            id: gearMa
                            anchors.fill: parent
                            actionName: root.moaiRtl
                                ? "الإعدادات" : "Settings"
                            focusRadius: root.fs(12)
                            onTriggered: root.settingsOpen = true
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
                    Layout.preferredHeight: root.fs(3)
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: root.novaCyan }
                        GradientStop { position: 0.5; color: root.novaBlue }
                        GradientStop { position: 1.0; color: root.novaViolet }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.fs(56)
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
                                    case "device": return root.local("جهازي", "My device")
                                    case "apps":   return root.local("التطبيقات", "Apps")
                                    case "compat": return root.local("التوافق", "Compatibility")
                                    case "remote": return "Mo PC Remote"
                                    case "dev":    return root.local("المطوّر", "Developer")
                                    case "agent":  return root.local("الوكيل", "Agent")
                                    default:       return "Mo AI"
                                    }
                                }
                                color: root.textHi
                                font.family: root.uiFont
                                font.pixelSize: root.typePx(16)
                                font.weight: Font.DemiBold
                            }
                            Text {
                                text: {
                                    switch (root.panel) {
                                    case "device": return !root.planReady
                                        ? root.local("جارٍ الفحص…", "Scanning…")
                                        : root.healthy
                                        ? root.local("لا مشاكل", "No problems")
                                        : root.local(root.problemCount + " مشكلة",
                                                     root.problemCount + " issue(s)")
                                    case "apps":   return root.local("ابحث وثبّت أي تطبيق",
                                                                     "Search and install anything")
                                    case "compat": return root.local(
                                        "Windows · Android · الألعاب",
                                        "Windows · Android · Games")
                                    case "remote": return root.local("تحكّم بجهازك من هاتفك",
                                                                     "Control this PC from your phone")
                                    case "dev":    return "OpenCode · Claude Code · Codex"
                                    case "agent":  return root.local(
                                        "OpenClaw · Telegram · الجلسات",
                                        "OpenClaw · Telegram · Sessions")
                                    default:       return root.local("مساعد MoOS", "MoOS assistant")
                                    }
                                }
                                color: root.textLo
                                font.family: root.uiFont
                                font.pixelSize: root.typePx(11)
                            }
                        }

                        Item { Layout.fillWidth: true }

                        MoButton {
                            visible: root.panel === "chat"
                            label: root.local("المحادثات", "Conversations")
                            iconName: "moos-ai-symbolic"
                            primary: root.chatSidebarOpen
                            onClicked: {
                                root.chatSidebarOpen = !root.chatSidebarOpen
                                if (root.chatSidebarOpen) root.agentLoadStatus()
                            }
                        }
                        MoButton {
                            visible: root.panel === "chat"
                            label: root.local("محادثة جديدة", "New chat")
                            onClicked: root.newChat()
                        }
                        MoButton {
                            visible: root.panel === "device"
                            label: root.scanning ? root.local("جارٍ…", "Scanning…")
                                                 : root.local("أعد الفحص", "Rescan")
                            enabled_: !root.scanning
                            iconName: "moos-report-symbolic"
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
                        const i = ["chat", "device", "apps", "compat", "remote", "dev", "agent"].indexOf(root.panel)
                        return i < 0 ? 0 : i
                    }

                    // ══ CHAT ════════════════════════════════════════════════
                    ColumnLayout {
                        spacing: 0

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                        // The doodle backdrop, behind the message list (shows once the
                        // conversation begins; the welcome hero carries its own copy).
                        ChatDoodle {
                            anchors.fill: parent
                            z: -1
                        }

                        Rectangle {
                            id: chatHistorySidebar
                            z: 40
                            visible: root.chatSidebarOpen
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            width: Math.min(root.fs(280), parent.width * 0.42)
                            color: root.chrome
                            border.width: 1
                            border.color: root.hairline
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: design.space2
                                spacing: design.space1
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        Layout.fillWidth: true
                                        text: root.local("سجل المحادثات", "Conversation history")
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(12)
                                        font.weight: Font.DemiBold
                                    }
                                    MoButton {
                                        label: "×"
                                        onClicked: root.chatSidebarOpen = false
                                    }
                                }
                                QQC2.TextField {
                                    Layout.fillWidth: true
                                    placeholderText: root.local("بحث…", "Search…")
                                    text: root.agentSearch
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(10)
                                    onTextChanged: {
                                        root.agentSearch = text
                                        primarySearchDelay.restart()
                                    }
                                    Timer {
                                        id: primarySearchDelay
                                        interval: 180
                                        repeat: false
                                        onTriggered: root.agentLoadSessions()
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    QQC2.CheckBox {
                                        text: root.local("المؤرشفة", "Archived")
                                        checked: root.agentShowArchived
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(9)
                                        onToggled: {
                                            root.agentShowArchived = checked
                                            root.agentLoadSessions()
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    MoButton {
                                        label: root.local("جديدة", "New")
                                        onClicked: root.newChat()
                                    }
                                }
                                ListView {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    model: root.agentSessions
                                    clip: true
                                    spacing: 2
                                    QQC2.ScrollBar.vertical: QQC2.ScrollBar { }
                                    delegate: Rectangle {
                                        required property var modelData
                                        width: ListView.view.width
                                        height: root.fs(48)
                                        radius: root.fs(7)
                                        color: root.chatOpenClawSessionKey === modelData.key
                                               ? Qt.rgba(root.novaBlue.r, root.novaBlue.g,
                                                         root.novaBlue.b, 0.16)
                                               : "transparent"
                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 8
                                            anchors.rightMargin: 8
                                            spacing: 1
                                            RowLayout {
                                                Layout.fillWidth: true
                                                Text {
                                                    Layout.fillWidth: true
                                                    text: modelData.label
                                                    color: root.textHi
                                                    elide: Text.ElideRight
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.typePx(10)
                                                    font.weight: Font.DemiBold
                                                }
                                                Text {
                                                    text: modelData.pinned ? "●" : ""
                                                    color: root.novaCyan
                                                    font.pixelSize: root.typePx(8)
                                                }
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: root.local("جلسة OpenClaw موحّدة",
                                                                 "Unified OpenClaw session")
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(8)
                                            }
                                        }
                                        ActionArea {
                                            anchors.fill: parent
                                            actionName: modelData.label
                                            focusRadius: root.fs(7)
                                            onTriggered: root.agentOpenPrimary(
                                                modelData.id, modelData.key, modelData.label)
                                        }
                                    }
                                }
                                Text {
                                    visible: root.agentSessions.length === 0
                                    Layout.fillWidth: true
                                    text: root.agentStatusLoaded
                                        ? root.local("لا توجد محادثات", "No conversations")
                                        : root.local("جارٍ تحميل السجل…", "Loading history…")
                                    horizontalAlignment: Text.AlignHCenter
                                    color: root.textMute
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(9)
                                }
                            }
                        }

                        DropArea {
                            id: chatDropArea
                            anchors.fill: parent
                            z: 20
                            onDropped: function (drop) {
                                const urls = drop.urls || []
                                for (let i = 0; i < Math.min(urls.length, 8); ++i)
                                    root.importAttachment(String(urls[i]))
                                drop.accept()
                            }
                            Rectangle {
                                anchors.fill: parent
                                visible: chatDropArea.containsDrag
                                color: Qt.rgba(root.novaBlue.r, root.novaBlue.g,
                                               root.novaBlue.b, 0.12)
                                border.width: 2
                                border.color: root.novaBlue
                                radius: design.radiusCard
                                Text {
                                    anchors.centerIn: parent
                                    text: root.local("أفلت الصور أو الملفات هنا",
                                                     "Drop images or files here")
                                    color: root.textHi
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(15)
                                    font.weight: Font.DemiBold
                                }
                            }
                        }

                        ListView {
                            id: listView
                            anchors.fill: parent
                            visible: chatModel.count > 1
                            clip: true
                            spacing: design.space1
                            topMargin: 14
                            bottomMargin: 10
                            leftMargin: 16
                            rightMargin: 16
                            model: chatModel
                            onCountChanged: Qt.callLater(listView.positionViewAtEnd)
                            QQC2.ScrollBar.vertical: QQC2.ScrollBar { }
                            Timer {
                                id: sessionStartDelay
                                interval: 180
                                repeat: false
                                onTriggered: listView.positionViewAtBeginning()
                            }

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
                                    readonly property bool toolish:
                                        msg.role.indexOf("tool-") === 0
                                    readonly property color toolColor:
                                        msg.role === "tool-error" ? root.badColor
                                        : msg.role === "tool-success" ? root.okColor
                                        : root.novaViolet
                                    anchors.right: mine ? parent.right : undefined
                                    anchors.left: mine ? undefined : parent.left
                                    anchors.leftMargin: mine ? 0 : 36
                                    y: 3
                                    radius: design.radiusControl
                                    color: toolish
                                         ? Qt.rgba(toolColor.r, toolColor.g,
                                                   toolColor.b, 0.12)
                                         : mine
                                         ? Qt.rgba(root.novaBlue.r, root.novaBlue.g,
                                                   root.novaBlue.b, 0.16)
                                         : root.surface1
                                    border.width: 1
                                    border.color: toolish
                                        ? Qt.rgba(toolColor.r, toolColor.g,
                                                  toolColor.b, 0.45)
                                        : mine
                                        ? Qt.rgba(root.novaBlue.r, root.novaBlue.g,
                                                  root.novaBlue.b, 0.38)
                                        : root.hairline
                                    width: body.width + 28
                                    height: body.implicitHeight + 22
                                            + ((msg.role === "assistant" || bubble.toolish)
                                               ? root.fs(26) : 0)

                                    TextEdit {
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
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(14)
                                        readOnly: true
                                        selectByMouse: true
                                        persistentSelection: true
                                        activeFocusOnPress: true
                                        onLinkActivated: function (link) { Qt.openUrlExternally(link) }

                                        SequentialAnimation on opacity {
                                            running: msg.role === "typing" && root.motionEnabled
                                            loops: Animation.Infinite
                                            // A value-source animation does not restore on stop; when
                                            // typing → assistant flips, force full opacity so the
                                            // streamed reply is not left dimmed.
                                            onRunningChanged: if (!running) body.opacity = 1
                                            NumberAnimation { from: 1.0; to: 0.30; duration: root.motionEnabled ? 460 : 0 }
                                            NumberAnimation { from: 0.30; to: 1.0; duration: root.motionEnabled ? 460 : 0 }
                                        }
                                    }

                                    Item {
                                        visible: msg.role === "assistant" || bubble.toolish
                                        anchors.right: parent.right
                                        anchors.bottom: parent.bottom
                                        anchors.margins: root.fs(4)
                                        width: root.fs(28)
                                        height: root.fs(24)
                                        Kirigami.Icon {
                                            anchors.centerIn: parent
                                            width: root.fs(14)
                                            height: root.fs(14)
                                            source: "edit-copy"
                                            color: copyMessageArea.containsMouse
                                                ? root.novaCyan : root.textMute
                                        }
                                        ActionArea {
                                            id: copyMessageArea
                                            anchors.fill: parent
                                            actionName: root.local("نسخ الرد", "Copy response")
                                            focusRadius: root.fs(6)
                                            onTriggered: {
                                                body.selectAll()
                                                body.copy()
                                                body.deselect()
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // ══ Empty-state hero — Tidal Horizon + brand + suggestion cards ══
                        // Shown before the first exchange (chatModel holds only the seeded
                        // greeting). The same concave horizon used by the shell seats the
                        // unchanged Mo AI orb; four glass cards seed the conversation via
                        // sendPrompt. The ListView takes over on the first reply.
                        Item {
                            anchors.fill: parent
                            visible: chatModel.count <= 1

                            // Doodles remain a quiet texture, no longer the dominant identity.
                            ChatDoodle {
                                anchors.fill: parent
                                opacity: root.isLight ? 0.10 : 0.14
                            }

                            Column {
                                anchors.centerIn: parent
                                spacing: 22
                                width: Math.min(parent.width - 80, 620)

                                // brand orb over a layered glow
                                Item {
                                    width: 130; height: 130
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    Rectangle {
                                        anchors.centerIn: parent; width: 130; height: 130; radius: 65
                                        color: Qt.rgba(root.novaCyan.r, root.novaCyan.g, root.novaCyan.b, 0.06)
                                        border.width: 1
                                        border.color: Qt.rgba(root.novaCyan.r, root.novaCyan.g, root.novaCyan.b, 0.20)
                                    }
                                    Rectangle {
                                        anchors.centerIn: parent; width: 102; height: 102; radius: 51
                                        color: Qt.rgba(root.novaCyan.r, root.novaCyan.g, root.novaCyan.b, 0.10)
                                    }
                                    MoOrb { anchors.centerIn: parent; width: 82; height: 82; mood: "idle" }
                                }

                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: root.moaiRtl ? "أهلاً، أنا Mo AI" : "Hi, I'm Mo AI"
                                    color: root.textHi
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(32)
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: root.moaiRtl
                                        ? "مساعد MoOS — اختر بداية، أو اكتب طلبك."
                                        : "Your MoOS assistant — pick a starting point, or just type."
                                    color: root.textLo
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(14)
                                }

                                // four premium glass suggestion cards (2×2)
                                Grid {
                                    id: heroCards
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    columns: parent.width > 520 ? 2 : 1
                                    columnSpacing: 12
                                    rowSpacing: 12
                                    Repeater {
                                        model: root.starters
                                        delegate: Rectangle {
                                            required property var modelData
                                            width: heroCards.columns === 2 ? (heroCards.parent.width - 12) / 2 : heroCards.parent.width
                                            height: 74
                                            radius: design.radiusCard
                                            color: Qt.rgba(root.surface1.r, root.surface1.g, root.surface1.b, cardMA.containsMouse ? 0.94 : 0.66)
                                            border.width: 1
                                            border.color: cardMA.containsMouse
                                                ? Qt.rgba(root.novaCyan.r, root.novaCyan.g, root.novaCyan.b, 0.55)
                                                : root.hairline
                                            scale: cardMA.containsMouse ? 1.02 : 1.0
                                            Behavior on scale { NumberAnimation { duration: root.motionEnabled ? design.motionPress : 0; easing.type: Easing.OutCubic } }
                                            Behavior on border.color { ColorAnimation { duration: root.motionEnabled ? design.motionPress : 0 } }
                                            Behavior on color { ColorAnimation { duration: root.motionEnabled ? design.motionPress : 0 } }

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.margins: 13
                                                spacing: design.space3
                                                layoutDirection: root.moaiRtl
                                                    ? Qt.RightToLeft : Qt.LeftToRight

                                                Rectangle {
                                                    Layout.preferredWidth: root.fs(42); Layout.preferredHeight: root.fs(42)
                                                    radius: design.radiusControl
                                                    color: Qt.rgba(root.novaCyan.r, root.novaCyan.g, root.novaCyan.b, 0.13)
                                                    Kirigami.Icon {
                                                        anchors.centerIn: parent
                                                        width: 22; height: 22
                                                        source: modelData.icon
                                                        color: root.novaCyan
                                                    }
                                                }
                                                ColumnLayout {
                                                    Layout.fillWidth: true
                                                    spacing: 1
                                                    Text {
                                                        Layout.fillWidth: true
                                                        text: root.moaiRtl ? modelData.ar : modelData.en
                                                        color: root.textHi
                                                        font.family: root.uiFont
                                                        font.pixelSize: root.typePx(14)
                                                        font.weight: Font.DemiBold
                                                        elide: Text.ElideRight
                                                    }
                                                    Text {
                                                        Layout.fillWidth: true
                                                        text: modelData.hint
                                                        color: root.textMute
                                                        font.family: root.uiFont
                                                        font.pixelSize: root.typePx(11)
                                                        elide: Text.ElideRight
                                                    }
                                                }
                                            }
                                            ActionArea {
                                                id: cardMA
                                                anchors.fill: parent
                                                actionName: root.moaiRtl
                                                    ? modelData.ar : modelData.en
                                                focusRadius: root.fs(16)
                                                onTriggered: root.sendPrompt(modelData.send)
                                            }
                                        }
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
                            radius: design.radiusControl
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
                                spacing: design.space3

                                Kirigami.Icon {
                                    source: "moos-warning-symbolic"
                                    color: root.warnColor
                                    Layout.preferredWidth: root.fs(22)
                                    Layout.preferredHeight: root.fs(22)
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text {
                                        text: root.local(
                                            "وجدت " + root.problemCount + " مشكلة في جهازك",
                                            "Found " + root.problemCount + " issue(s)")
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(13)
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: (root.actions[0] || {}).title || ""
                                        color: root.textLo
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(11)
                                        elide: Text.ElideRight
                                    }
                                }
                                MoButton {
                                    label: root.local("افتح", "Open")
                                    primary: true
                                    onClicked: root.panel = "device"
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
                            radius: design.radiusControl
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
                                        ? root.local(
                                            "بوابة Mo AI متوقفة — شغّلها:  systemctl --user start moai-gateway",
                                            "Mo AI's gateway is not running — start it:  systemctl --user start moai-gateway")
                                        : root.routeIsCloud
                                        ? root.local(
                                            "العقل السحابي غير مضبوط — أضف المزوّد والمفتاح.",
                                            "The cloud brain is not set up — add the provider and your API key.")
                                        : root.brainStarting
                                        ? root.local(
                                            "العقل المحلي يبدأ… أول مرة يُحمّل ~2.5GB وقد يأخذ دقائق.",
                                            "Local brain starting… the first run downloads ~2.5 GB.")
                                        : root.local(
                                            "العقل المحلي متوقف — سأشغّله تلقائياً عند أول رسالة، أو شغّله الآن لتراه.",
                                            "The local brain is off — I'll start it on your first message, or start it now and watch it.")
                                    color: root.textLo
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(11)
                                    wrapMode: Text.Wrap
                                }
                                MoButton {
                                    Layout.fillWidth: true
                                    visible: !!root.brains.gateway && !root.routeIsCloud
                                             && !root.brainStarting
                                    label: root.local("شغّل العقل المحلي", "Start local brain")
                                    primary: true
                                    onClicked: root.startBrain()
                                }
                                MoButton {
                                    Layout.fillWidth: true
                                    visible: !!root.brains.gateway && root.routeIsCloud
                                    label: root.local("اضبط العقل السحابي",
                                                      "Set up the cloud brain")
                                    iconName: "moos-settings-symbolic"
                                    primary: true
                                    onClicked: { root.settingsOpen = true }
                                }
                            }
                        }

                        // Run chips for the actions the model just named.
                        Flow {
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            Layout.bottomMargin: 8
                            spacing: design.space2
                            visible: root.pendingRuns.length > 0
                            Repeater {
                                model: root.pendingRuns
                                delegate: MoButton {
                                    required property string modelData
                                    label: "نفّذ  moai-do " + modelData
                                    iconName: "moos-safe-update-symbolic"
                                    primary: true
                                    onClicked: root.launch("moos://do/" + modelData, "moai-do " + modelData)
                                }
                            }
                        }

                        Flow {
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            Layout.bottomMargin: root.lastSubmissionContent !== null
                                && !root.busy ? 8 : 0
                            visible: root.lastSubmissionContent !== null && !root.busy
                            MoButton {
                                label: root.local("إعادة توليد آخر رد", "Regenerate last reply")
                                iconName: "view-refresh"
                                onClicked: root.regenerateLast()
                            }
                        }

                        Flow {
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            Layout.bottomMargin: root.pendingAttachments.length ? 8 : 0
                            spacing: design.space1
                            visible: root.pendingAttachments.length > 0
                            Repeater {
                                model: root.pendingAttachments
                                delegate: Rectangle {
                                    required property var modelData
                                    width: attachmentChipRow.implicitWidth + 18
                                    height: root.fs(32)
                                    radius: design.radiusControl
                                    color: root.surface1
                                    border.width: 1
                                    border.color: root.hairline
                                    RowLayout {
                                        id: attachmentChipRow
                                        anchors.centerIn: parent
                                        spacing: design.space1
                                        Kirigami.Icon {
                                            source: modelData.content_type === "image"
                                                ? "image-x-generic" : "text-x-generic"
                                            color: root.novaCyan
                                            Layout.preferredWidth: root.fs(15)
                                            Layout.preferredHeight: root.fs(15)
                                        }
                                        Text {
                                            text: modelData.name
                                            color: root.textHi
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(10)
                                            elide: Text.ElideMiddle
                                            Layout.maximumWidth: root.fs(180)
                                        }
                                        Text {
                                            text: "×"
                                            color: root.textMute
                                            font.pixelSize: root.typePx(13)
                                        }
                                    }
                                    ActionArea {
                                        anchors.fill: parent
                                        actionName: root.local("إزالة المرفق", "Remove attachment")
                                        focusRadius: root.fs(8)
                                        onTriggered: root.removePendingAttachment(modelData.id)
                                    }
                                }
                            }
                        }

                        // Input
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.fs(68)
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

                                MoButton {
                                    label: root.local("إرفاق", "Attach")
                                    iconName: "mail-attachment"
                                    onClicked: attachmentDialog.open()
                                }
                                MoButton {
                                    label: root.voiceRecording
                                        ? root.local("إيقاف التسجيل", "Stop recording")
                                        : root.local("صوت", "Voice")
                                    iconName: root.voiceRecording
                                        ? "media-playback-stop" : "audio-input-microphone"
                                    primary: root.voiceRecording
                                    onClicked: root.toggleVoiceRecording()
                                }

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
                                    radius: design.radiusControl
                                    color: chipMa.containsMouse ? root.surface2 : root.surface1
                                    border.width: 1
                                    border.color: root.pickerOpen ? root.novaBlue : root.hairline
                                    Behavior on color { ColorAnimation { duration: root.motionEnabled ? design.motionFast : 0 } }

                                    RowLayout {
                                        id: chipRow
                                        anchors.centerIn: parent
                                        spacing: 7

                                        // Green when the chosen brain can answer
                                        // right now — read from the machine, not
                                        // asserted.
                                        Rectangle {
                                            Layout.preferredWidth: root.fs(8)
                                            Layout.preferredHeight: root.fs(8)
                                            Layout.alignment: Qt.AlignVCenter
                                            radius: height / 2
                                            color: !root.serverUp ? root.textMute
                                                 : root.routeIsCloud ? root.novaViolet
                                                 : root.routeIsHybrid ? root.novaCyan
                                                 : root.okColor
                                            Behavior on color { ColorAnimation { duration: root.motionEnabled ? design.motionPress : 0 } }
                                        }

                                        ColumnLayout {
                                            spacing: 0
                                            Text {
                                                text: root.routeIsCloud
                                                    ? root.local("سحابي", "Cloud")
                                                    : root.routeIsHybrid
                                                        ? root.local("هجين", "Hybrid")
                                                        : root.local("محلي", "Local")
                                                color: root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(11)
                                                font.weight: Font.DemiBold
                                            }
                                            Text {
                                                Layout.maximumWidth: 118
                                                visible: root.routeModel !== ""
                                                         || root.agentDecision !== ""
                                                         || (root.routeIsHybrid
                                                             && root.hybridDecision !== "")
                                                text: {
                                                    const routeText = root.routeIsHybrid
                                                        && root.hybridDecision !== ""
                                                        ? root.hybridDecision : root.routeModel
                                                    if (routeText !== "" && root.agentDecision !== "")
                                                        return routeText + " · " + root.agentDecision
                                                    return routeText !== "" ? routeText : root.agentDecision
                                                }
                                                color: root.textLo
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(9)
                                                elide: Text.ElideRight
                                            }
                                        }

                                        Text {
                                            text: "▾"
                                            color: root.textMute
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(10)
                                        }
                                    }

                                    ActionArea {
                                        id: chipMa
                                        anchors.fill: parent
                                        actionName: root.moaiRtl
                                            ? "اختيار مسار العقل" : "Choose brain route"
                                        focusRadius: root.fs(11)
                                        onTriggered: root.openPicker()
                                    }
                                }

                                QQC2.TextField {
                                    id: input
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    placeholderText: root.local("اسأل Mo AI أي شيء…",
                                                                "Ask Mo AI anything…")
                                    placeholderTextColor: root.textMute
                                    color: root.textHi
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(14)
                                    leftPadding: 14
                                    rightPadding: 14
                                    background: Rectangle {
                                        color: root.surface1
                                        radius: design.radiusControl
                                        border.width: 1
                                        border.color: input.activeFocus ? root.novaBlue : root.hairline
                                        Behavior on border.color { ColorAnimation { duration: root.motionEnabled ? design.motionPress : 0 } }
                                    }
                                    onAccepted: root.send()
                                }

                                Rectangle {
                                    Layout.fillHeight: true
                                    Layout.preferredWidth: root.fs(106)
                                    radius: design.radiusControl
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
                                        text: root.busy ? root.local("إيقاف", "Stop")
                                                        : root.local("إرسال", "Send")
                                        color: root.accentText
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(13)
                                        font.weight: Font.DemiBold
                                    }
                                    ActionArea {
                                        anchors.fill: parent
                                        enabled: parent.on_
                                        actionName: root.busy
                                            ? (root.moaiRtl ? "إيقاف التوليد" : "Stop generating")
                                            : (root.moaiRtl ? "إرسال الرسالة" : "Send message")
                                        focusRadius: root.fs(11)
                                        onTriggered: root.busy ? root.stopGenerating() : root.send()
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
                            spacing: design.space3

                            // Verdict.
                            Card {
                                Layout.fillWidth: true
                                RowLayout {
                                    width: parent.width
                                    spacing: 14

                                    Rectangle {
                                        Layout.preferredWidth: root.fs(44)
                                        Layout.preferredHeight: root.fs(44)
                                        radius: height / 2
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
                                            source: root.healthy ? "moos-system-symbolic" : "moos-warning-symbolic"
                                            color: root.healthy ? root.okColor
                                                 : root.hasImportant ? root.badColor : root.warnColor
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 3
                                        Text {
                                            text: !root.planReady
                                                ? root.local("جارٍ فحص جهازك…",
                                                             "Checking your device…")
                                                : root.healthy
                                                ? root.local("جهازك سليم",
                                                             "Your device is healthy")
                                                : root.local(
                                                    "وجدت " + root.problemCount + " مشكلة",
                                                    root.problemCount + " issue(s) found")
                                            color: root.textHi
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(16)
                                            font.weight: Font.DemiBold
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: !root.planReady
                                                ? root.local(
                                                    "أقرأ التعريفات والبرامج الثابتة والأجهزة المتصلة…",
                                                    "Reading drivers, firmware and attached devices…")
                                                : root.healthy
                                                ? root.local(
                                                    "لا توجد مشاكل في الأجهزة أو التعريفات.",
                                                    "No hardware or driver problems found.")
                                                : root.local(
                                                    "كل مشكلة بالأسفل معها الإصلاح الذي يناسبها.",
                                                    "Each problem below comes with the repair that fixes it.")
                                            color: root.textLo
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(11)
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
                                            { icon: "moos-identity-symbolic", ar: "النظام", en: "System", v: (root.snap.os || "MoOS") },
                                            { icon: "moos-cpu-symbolic",      ar: "المعالج", en: "Processor", v: (root.snap.cpu || "?") + " · " + (root.snap.cores || "?") + " cores" },
                                            { icon: "moos-memory-symbolic",   ar: "الذاكرة", en: "Memory", v: (root.snap.mem_gb || "?") + " GB RAM" },
                                            { icon: "moos-gpu-symbolic",      ar: "الرسوميات", en: "Graphics", v: (root.snap.gpu || "?") },
                                            { icon: "moos-storage-symbolic",  ar: "التخزين", en: "Storage", v: (root.snap.disk && root.snap.disk.total_gb)
                                                 ? root.local(root.snap.disk.free_gb + " / " + root.snap.disk.total_gb + " GB حرّ",
                                                              root.snap.disk.free_gb + " / " + root.snap.disk.total_gb + " GB free") : "?" },
                                            { icon: "moos-system-symbolic",   ar: "نواة MoOS", en: "MoOS kernel", v: (root.snap.kernel || "?") }
                                        ]
                                        delegate: RowLayout {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            spacing: 9
                                            Kirigami.Icon {
                                                source: modelData.icon
                                                color: root.novaCyan
                                                Layout.preferredWidth: root.fs(16)
                                                Layout.preferredHeight: root.fs(16)
                                            }
                                            Text {
                                                text: root.local(modelData.ar, modelData.en)
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(11)
                                                Layout.preferredWidth: root.fs(54)
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: modelData.v
                                                color: root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(12)
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
                                        source: "moos-gpu-symbolic"
                                        color: root.novaViolet
                                        Layout.preferredWidth: root.fs(18)
                                        Layout.preferredHeight: root.fs(18)
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: root.plan.driver_status || ""
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(12)
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
                                        spacing: design.space2

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 9
                                            Rectangle {
                                                Layout.preferredWidth: root.fs(8)
                                                Layout.preferredHeight: root.fs(8)
                                                radius: height / 2
                                                color: issue.modelData.severity === "important"
                                                       ? root.badColor : root.warnColor
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: issue.modelData.title || ""
                                                color: root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(13)
                                                font.weight: Font.DemiBold
                                                elide: Text.ElideRight
                                            }
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: issue.modelData.detail || ""
                                            color: root.textLo
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(11)
                                            wrapMode: Text.Wrap
                                        }
                                        RowLayout {
                                            spacing: design.space2
                                            MoButton {
                                                visible: String(issue.modelData.url || "").length > 0
                                                label: root.local("أصلحها الآن", "Fix it")
                                                primary: true
                                                iconName: "moos-safe-update-symbolic"
                                                onClicked: root.launch(issue.modelData.url, issue.modelData.title)
                                            }
                                            MoButton {
                                                label: root.local("اسأل Mo AI", "Ask")
                                                onClicked: root.askAbout(issue.modelData.title, issue.modelData.detail || "")
                                            }
                                        }
                                    }
                                }
                            }

                            // Maintenance — the whole of the old Hardware Centre's action list.
                            SectionTitle {
                                text: root.local("الصيانة", "Maintenance")
                                Layout.topMargin: 6
                            }

                            Flow {
                                Layout.fillWidth: true
                                spacing: design.space2
                                Repeater {
                                    model: [
                                        { ar: "تحديث النظام", en: "Update", url: "moos://do/update", icon: "moos-safe-update-symbolic" },
                                        { ar: "فحص التعريفات", en: "Drivers", url: "moos://do/check-drivers", icon: "moos-gpu-symbolic" },
                                        { ar: "تحديث البرامج الثابتة", en: "Firmware", url: "moos://do/update-firmware", icon: "moos-system-symbolic" },
                                        { ar: "تحسين وتنظيف", en: "Optimize", url: "moos://do/optimize", icon: "moos-optimize-symbolic" },
                                        { ar: "إصلاح الصوت", en: "Fix audio", url: "moos://do/fix-audio", icon: "moos-audio-symbolic" },
                                        { ar: "تقرير كامل", en: "Report", url: "moos://do/hw-report", icon: "moos-report-symbolic" },
                                        { ar: "الخدمات الفاشلة", en: "Services", url: "moos://do/diagnose-services", icon: "moos-system-symbolic" },
                                        { ar: "مشاكل الإقلاع", en: "Boot", url: "moos://do/inspect-boot", icon: "moos-warning-symbolic" },
                                        { ar: "المحدّث", en: "Updater", url: "moos://app/updater", icon: "moos-safe-update-symbolic" },
                                        { ar: "الاستعادة", en: "Recovery", url: "moos://app/recovery", icon: "moos-system-symbolic" }
                                    ]
                                    delegate: MoButton {
                                        required property var modelData
                                        label: root.local(modelData.ar, modelData.en)
                                        iconName: modelData.icon
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
                            Layout.preferredHeight: root.fs(62)
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
                                    Layout.preferredHeight: root.fs(40)
                                    placeholderText: root.local(
                                        "ابحث في Flathub… (مثلاً blender)",
                                        "Search Flathub…")
                                    placeholderTextColor: root.textMute
                                    color: root.textHi
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(13)
                                    leftPadding: 14
                                    rightPadding: 14
                                    background: Rectangle {
                                        color: root.surface1
                                        radius: design.radiusControl
                                        border.width: 1
                                        border.color: searchField.activeFocus ? root.novaBlue : root.hairline
                                    }
                                    onAccepted: root.searchApps(text)
                                }
                                MoButton {
                                    Layout.preferredHeight: root.fs(40)
                                    label: root.searching ? "…" : root.local("ابحث", "Search")
                                    iconName: "moos-install-symbolic"
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
                                    font.pixelSize: root.typePx(12)
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
                                            spacing: design.space3

                                            Rectangle {
                                                Layout.preferredWidth: root.fs(38)
                                                Layout.preferredHeight: root.fs(38)
                                                radius: design.radiusSmall
                                                color: root.surface2
                                                Kirigami.Icon {
                                                    anchors.centerIn: parent
                                                    width: 20; height: 20
                                                    source: "moos-install-symbolic"
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
                                                        font.pixelSize: root.typePx(13)
                                                        font.weight: Font.DemiBold
                                                    }
                                                    Text {
                                                        visible: hit.verified
                                                        text: "✓"
                                                        color: root.novaCyan
                                                        font.pixelSize: root.typePx(12)
                                                        font.weight: Font.Bold
                                                    }
                                                    // The MoOS pick, said out loud.
                                                    Rectangle {
                                                        visible: hit.recommended
                                                        Layout.preferredHeight: root.fs(17)
                                                        Layout.preferredWidth: pickLabel.width + 12
                                                        radius: root.fs(5)
                                                        color: Qt.rgba(root.novaCyan.r, root.novaCyan.g,
                                                                       root.novaCyan.b, 0.14)
                                                        border.width: 1
                                                        border.color: Qt.rgba(root.novaCyan.r, root.novaCyan.g,
                                                                              root.novaCyan.b, 0.45)
                                                        Text {
                                                            id: pickLabel
                                                            anchors.centerIn: parent
                                                            text: root.local("اختيار MoOS", "MoOS pick")
                                                            color: root.novaCyan
                                                            font.family: root.uiFont
                                                            font.pixelSize: root.typePx(9)
                                                            font.weight: Font.DemiBold
                                                        }
                                                    }
                                                }
                                                Text {
                                                    Layout.fillWidth: true
                                                    text: hit.summary
                                                    color: root.textLo
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.typePx(11)
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
                                                    font.pixelSize: root.typePx(10)
                                                    wrapMode: Text.WordWrap
                                                }
                                                Text {
                                                    text: hit.id
                                                    color: root.textMute
                                                    font.family: "JetBrains Mono"
                                                    font.pixelSize: root.typePx(10)
                                                }
                                            }

                                            MoButton {
                                                label: hit.installed
                                                    ? root.local("مثبّت ✓", "Installed")
                                                    : root.local("ثبّت", "Install")
                                                primary: !hit.installed
                                                enabled_: !hit.installed
                                                onClicked: root.launch("moos://apps/install/" + hit.id, hit.name)
                                            }
                                        }
                                    }
                                }

                                SectionTitle {
                                    text: root.local("موصى بها", "Recommended")
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
                                            spacing: design.space3

                                            Rectangle {
                                                Layout.preferredWidth: root.fs(38)
                                                Layout.preferredHeight: root.fs(38)
                                                radius: design.radiusSmall
                                                color: root.surface2
                                                Kirigami.Icon {
                                                    anchors.centerIn: parent
                                                    width: 20; height: 20
                                                    source: "moos-install-symbolic"
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
                                                    font.pixelSize: root.typePx(13)
                                                    font.weight: Font.DemiBold
                                                }
                                                Text {
                                                    Layout.fillWidth: true
                                                    text: root.local(rec.modelData.ar,
                                                                     rec.modelData.en)
                                                    color: root.textLo
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.typePx(11)
                                                }
                                            }
                                            MoButton {
                                                label: rec.installed
                                                    ? root.local("مثبّت ✓", "Installed")
                                                    : root.local("ثبّت", "Install")
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
                                    text: root.local(
                                        "أو اطلب من Mo AI مباشرة: «ثبّت لي Blender».",
                                        "Or just ask Mo AI: “install Blender for me”.")
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
                            spacing: design.space3

                            SectionNote {
                                Layout.fillWidth: true
                                text: root.local(
                                    "شغّل تطبيقات وألعاب Windows و Android على MoOS. الحالة مقروءة من جهازك، لا مفترضة.",
                                    "Run Windows and Android apps and games on MoOS. Status is read from your machine, not assumed.")
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
                                        spacing: design.space3

                                        Rectangle {
                                            Layout.preferredWidth: root.fs(40)
                                            Layout.preferredHeight: root.fs(40)
                                            radius: design.radiusControl
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
                                                spacing: design.space2
                                                Text {
                                                    text: compat.modelData.title
                                                    color: root.textHi
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.typePx(14)
                                                    font.weight: Font.DemiBold
                                                }
                                                StatusPill {
                                                    good: compat.ready
                                                    goodText: root.local("جاهز", "Ready")
                                                    badText: root.local("غير مثبّت", "Not set up")
                                                }
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: root.local(compat.modelData.ar,
                                                                 compat.modelData.en)
                                                color: root.textLo
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(11)
                                            }
                                        }
                                        MoButton {
                                            label: compat.ready ? root.local("جاهز ✓", "Ready")
                                                                : root.local("إعداد", "Set up")
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
                                    spacing: design.space3
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 3
                                        Text {
                                            text: root.local("المحاكاة الافتراضية (KVM)",
                                                             "Virtualisation (KVM)")
                                            color: root.textHi
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(13)
                                            font.weight: Font.DemiBold
                                        }
                                        Text {
                                            text: root.local(
                                                "يحتاجه Waydroid والأجهزة الافتراضية.",
                                                "Needed by Waydroid and virtual machines.")
                                            color: root.textLo
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(11)
                                        }
                                    }
                                    StatusPill {
                                        good: !!root.compatState.kvm
                                        goodText: root.local("مفعّل", "Enabled")
                                        badText: root.local("غير متاح", "Unavailable")
                                    }
                                }
                            }

                            MoButton {
                                Layout.topMargin: 4
                                label: root.local("تثبيت ذكي حسب جهازي",
                                                  "Smart setup for my hardware")
                                iconName: "moos-optimize-symbolic"
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
                            spacing: design.space3

                            Card {
                                Layout.fillWidth: true
                                RowLayout {
                                    width: parent.width
                                    spacing: 14

                                    Rectangle {
                                        Layout.preferredWidth: root.fs(46)
                                        Layout.preferredHeight: root.fs(46)
                                        radius: height / 2
                                        color: root.remoteState.active
                                               ? Qt.rgba(root.okColor.r, root.okColor.g,
                                                         root.okColor.b, 0.14)
                                               : root.surface2
                                        Kirigami.Icon {
                                            anchors.centerIn: parent
                                            width: 24; height: 24
                                            source: "moos-phone-symbolic"
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
                                            // root.visible joins the gate: every sibling loop has a
                                            // visibility term, and without it an active remote session
                                            // kept this ring animating with the panel hidden.
                                            SequentialAnimation on opacity {
                                                running: !!root.remoteState.active && root.visible && root.motionEnabled
                                                loops: Animation.Infinite
                                                NumberAnimation { from: 0.7; to: 0.0; duration: root.motionEnabled ? 1200 : 0 }
                                                NumberAnimation { from: 0.0; to: 0.0; duration: root.motionEnabled ? design.motionGeometry : 0 }
                                            }
                                            SequentialAnimation on scale {
                                                running: !!root.remoteState.active && root.visible && root.motionEnabled
                                                loops: Animation.Infinite
                                                NumberAnimation { from: 1.0; to: 1.45; duration: root.motionEnabled ? 1200 : 0 }
                                                NumberAnimation { from: 1.0; to: 1.0; duration: root.motionEnabled ? design.motionGeometry : 0 }
                                            }
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: design.space1
                                        Text {
                                            text: root.remoteState.active
                                                  ? root.local("يعمل الآن", "Running")
                                                  : root.local("متوقف", "Stopped")
                                            color: root.remoteState.active ? root.okColor : root.textHi
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(16)
                                            font.weight: Font.DemiBold
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: root.remoteState.active
                                                ? root.local(
                                                    "افتح اللوحة لمسح رمز QR من هاتفك.",
                                                    "Open the panel to scan the QR code from your phone.")
                                                : root.local(
                                                    "شغّله ليتحكّم هاتفك بهذا الجهاز.",
                                                    "Start it to control this PC from your phone.")
                                            color: root.textLo
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(11)
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
                                spacing: design.space2

                                MoButton {
                                    label: root.local("تشغيل", "Start")
                                    iconName: "moos-phone-symbolic"
                                    primary: true
                                    enabled_: !root.remoteState.active
                                    onClicked: root.launch("moos://remote/start", "Mo PC Remote — start")
                                }
                                MoButton {
                                    label: root.local("إيقاف", "Stop")
                                    danger: true
                                    enabled_: !!root.remoteState.active
                                    onClicked: root.launch("moos://remote/stop", "Mo PC Remote — stop")
                                }
                                MoButton {
                                    label: root.local("إعادة الاتصال", "Reconnect")
                                    iconName: "moos-network-symbolic"
                                    onClicked: root.launch("moos://remote/restart", "Mo PC Remote — reconnect")
                                }
                                MoButton {
                                    label: root.local("افتح اللوحة", "Open panel")
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
                                        text: root.local("المتطلّبات", "Requirements")
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(13)
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
                                                text: root.local(modelData.ar, modelData.en)
                                                color: root.textLo
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(12)
                                            }
                                            StatusPill {
                                                good: !!root.remoteState[modelData.k]
                                                goodText: root.local("يعمل", "OK")
                                                badText: root.local("متوقف", "Down")
                                            }
                                        }
                                    }
                                }
                            }

                            MoButton {
                                label: root.local("الوصول من خارج المنزل",
                                                  "Reach it from outside")
                                iconName: "moos-network-symbolic"
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
                            spacing: design.space3

                            SectionNote {
                                Layout.fillWidth: true
                                text: root.local(
                                    "‏وكلاء برمجة يشتغلون داخل مشروعك كمستخدم عادي — يُثبَّتون في ~/.local، بلا صلاحيات مسؤول ولا مساس بالنظام.",
                                    "‎Coding agents that run in your project as your user — installed into ~/.local, with no admin rights and no changes to the system.")
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
                                      needsAr: "بلا حساب وبلا إنترنت", needsEn: "No account or internet",
                                      pkg: "opencode-ai",
                                      install: "moos://do/install-opencode", run: "moos://dev/opencode" },
                                    { key: "claude", title: "Claude Code", local: false,
                                      ar: "وكيل Anthropic البرمجي", en: "Anthropic's coding agent",
                                      needsAr: "يحتاج حساب Anthropic", needsEn: "Needs an Anthropic account",
                                      pkg: "@anthropic-ai/claude-code",
                                      install: "moos://do/install-claude", run: "moos://dev/claude" },
                                    { key: "codex", title: "Codex", local: false,
                                      ar: "وكيل OpenAI البرمجي", en: "OpenAI's coding agent",
                                      needsAr: "يحتاج حساب OpenAI", needsEn: "Needs an OpenAI account",
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
                                        spacing: design.space3

                                        Rectangle {
                                            Layout.preferredWidth: root.fs(40)
                                            Layout.preferredHeight: root.fs(40)
                                            radius: design.radiusControl
                                            color: ag.have
                                                   ? Qt.rgba(root.okColor.r, root.okColor.g,
                                                             root.okColor.b, 0.13)
                                                   : (ag.onDevice
                                                      ? Qt.rgba(root.novaCyan.r, root.novaCyan.g, root.novaCyan.b, 0.12)
                                                      : root.surface2)
                                            Kirigami.Icon {
                                                anchors.centerIn: parent
                                                width: 21; height: 21
                                                source: ag.onDevice ? "moos-ai-symbolic" : "moos-code-symbolic"
                                                color: ag.have ? root.okColor
                                                               : (ag.onDevice ? root.novaCyan : root.textMute)
                                            }
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 3
                                            RowLayout {
                                                spacing: design.space2
                                                Text {
                                                    text: ag.modelData.title
                                                    color: root.textHi
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.typePx(14)
                                                    font.weight: Font.DemiBold
                                                }
                                                StatusPill {
                                                    good: ag.have
                                                    goodText: root.local("مثبّت", "Installed")
                                                    badText: root.local("غير مثبّت", "Not installed")
                                                }
                                                // The badge that is the whole point of shipping a
                                                // local brain: an agent that keeps working when the
                                                // network does not.
                                                Rectangle {
                                                    visible: ag.onDevice
                                                    Layout.preferredHeight: root.fs(18)
                                                    Layout.preferredWidth: offlineText.width + 14
                                                    radius: root.fs(6)
                                                    color: Qt.rgba(root.novaCyan.r, root.novaCyan.g,
                                                                   root.novaCyan.b, 0.14)
                                                    border.width: 1
                                                    border.color: Qt.rgba(root.novaCyan.r, root.novaCyan.g,
                                                                          root.novaCyan.b, 0.45)
                                                    Text {
                                                        id: offlineText
                                                        anchors.centerIn: parent
                                                        text: root.local("يعمل بلا إنترنت", "Offline")
                                                        color: root.novaCyan
                                                        font.family: root.uiFont
                                                        font.pixelSize: root.typePx(9)
                                                        font.weight: Font.DemiBold
                                                    }
                                                }
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: root.local(ag.modelData.ar,
                                                                 ag.modelData.en)
                                                color: root.textLo
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(11)
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: root.local(ag.modelData.needsAr,
                                                                 ag.modelData.needsEn)
                                                color: ag.onDevice ? root.novaCyan : root.textMute
                                                opacity: ag.onDevice ? 0.95 : 0.8
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(10)
                                            }
                                            Text {
                                                text: ag.modelData.pkg
                                                color: root.textMute
                                                font.family: "JetBrains Mono"
                                                font.pixelSize: root.typePx(10)
                                            }
                                        }
                                        MoButton {
                                            label: ag.have ? root.local("شغّل", "Run")
                                                           : root.local("ثبّت", "Install")
                                            primary: true
                                            iconName: ag.have ? "moos-code-symbolic" : "moos-install-symbolic"
                                            onClicked: root.launch(
                                                ag.have ? ag.modelData.run : ag.modelData.install,
                                                ag.modelData.title)
                                        }
                                    }
                                }
                            }

                            MoButton {
                                Layout.topMargin: 4
                                label: root.local("افتح وكيلاً في مشروع",
                                                  "Open an agent in a project")
                                iconName: "moos-code-symbolic"
                                // Enabled when ANY agent is installed — moai-code builds its picker
                                // from what is actually on the machine, so a third agent must not
                                // be forgotten here (the old condition named two by hand).
                                enabled_: !!root.agentState.claude || !!root.agentState.codex
                                          || !!root.agentState.opencode
                                onClicked: root.launch("moos://dev/code", "Code")
                            }
                        }
                    }
                    // ══ AGENT — the OpenClaw agent, same brain, same sessions ══
                    // Loads on first open, not at startup: polling the console
                    // before the user asks would wake services for nothing.
                    // Reads and writes through moai-agent-api on 8077. Pure QML
                    // cannot touch ~/.openclaw directly, so the console is the seam.
                    ColumnLayout {
                        spacing: 10

                        property bool loadedOnce: false
                        onVisibleChanged: if (visible && !loadedOnce) {
                            loadedOnce = true
                            root.agentLoadStatus()
                        }
                        Timer {
                            interval: 5000
                            repeat: true
                            running: root.panel === "agent"
                            onTriggered: root.agentLoadStatus()
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: design.space2
                            SectionTitle { text: root.local("الوكيل", "Agent") }
                            Item { Layout.fillWidth: true }
                            StatusPill {
                                good: root.agentReady
                                goodText: root.agentBusy
                                    ? root.local("يفكّر…", "Thinking")
                                    : root.local("جاهز عند الطلب", "Ready on demand")
                                badText: !root.agentStatusLoaded
                                    ? root.local("جارٍ الفحص…", "Checking")
                                    : !root.agentInstalled
                                        ? root.local("غير مثبّت", "Not installed")
                                        : !root.agentMachineConfigured
                                            ? root.local("يحتاج إعداد", "Setup needed")
                                            : root.local("غير متصل", "Offline")
                            }
                            MoButton {
                                label: root.local("تحديث", "Refresh")
                                iconName: "moos-report-symbolic"
                                onClicked: root.agentLoadStatus()
                            }
                        }

                        SectionNote {
                            Layout.fillWidth: true
                            text: root.local(
                                "نفس المحادثات التي تراها في تليجرام — تقرأها هنا وتكمل من الشاشة.",
                                "The same Telegram conversations — read and continue them here.")
                        }

                        Card {
                            visible: root.agentStatusLoaded && !root.agentMachineConfigured
                            Layout.fillWidth: true
                            Layout.preferredHeight: agentSetupRow.implicitHeight + 28
                            border.color: Qt.rgba(root.novaBlue.r, root.novaBlue.g,
                                                  root.novaBlue.b, 0.55)
                            RowLayout {
                                id: agentSetupRow
                                anchors.fill: parent
                                spacing: design.space3
                                Kirigami.Icon {
                                    source: root.agentInstalled ? "moos-system-symbolic" : "moos-install-symbolic"
                                    color: root.novaBlue
                                    Layout.preferredWidth: root.fs(28)
                                    Layout.preferredHeight: root.fs(28)
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 3
                                    Text {
                                        Layout.fillWidth: true
                                        text: root.agentInstalled
                                            ? root.local("أكمل تجهيز الوكيل",
                                                         "Finish agent setup")
                                            : root.local("ثبّت وكيل الهاتف",
                                                         "Install phone agent")
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(14)
                                        font.weight: Font.DemiBold
                                    }
                                    SectionNote {
                                        Layout.fillWidth: true
                                        text: root.agentSetupNote
                                        font.pixelSize: root.typePx(11)
                                    }
                                }
                                MoButton {
                                    primary: true
                                    iconName: root.agentInstalled ? "moos-repair-symbolic" : "moos-install-symbolic"
                                    label: root.agentSetupLabel
                                    onClicked: root.launch(root.agentSetupAction,
                                                           root.agentInstalled
                                                               ? "Agent setup"
                                                               : "OpenClaw")
                                }
                            }
                        }

                        Text {
                            visible: root.agentAnyError !== ""
                            Layout.fillWidth: true
                            text: root.agentAnyError
                                + "   —   systemctl --user start moai-agent-api.service"
                            color: root.badColor
                            font.family: root.uiFont
                            font.pixelSize: root.typePx(11)
                            wrapMode: Text.Wrap
                        }

                        RowLayout {
                            visible: root.agentMachineConfigured
                            Layout.fillWidth: true
                            spacing: design.space1
                            Repeater {
                                model: [
                                    { id: "conversations", ar: "المحادثات", en: "Conversations" },
                                    { id: "projects", ar: "المشاريع", en: "Projects" },
                                    { id: "tasks", ar: "المهام", en: "Tasks" },
                                    { id: "terminal", ar: "الطرفية", en: "Terminal" }
                                ]
                                delegate: MoButton {
                                    required property var modelData
                                    label: root.local(modelData.ar, modelData.en)
                                    primary: root.agentWorkspaceTab === modelData.id
                                    onClicked: {
                                        root.agentWorkspaceTab = modelData.id
                                        if (modelData.id === "projects") root.agentLoadProjects()
                                        if (modelData.id === "tasks") root.agentLoadTasks()
                                        if (modelData.id === "terminal") root.agentLoadTerminals()
                                    }
                                }
                            }
                            Item { Layout.fillWidth: true }
                        }

                        RowLayout {
                            visible: root.agentMachineConfigured
                                     && root.agentWorkspaceTab === "conversations"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 10

                            // ── sessions ──
                            Card {
                                Layout.preferredWidth: root.fs(190)
                                Layout.fillHeight: true
                                ColumnLayout {
                                    anchors.fill: parent
                                    spacing: design.space1
                                    Text {
                                        text: root.local("المحادثات", "Sessions")
                                        color: root.textMute
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(10)
                                        font.weight: Font.DemiBold
                                    }
                                    QQC2.TextField {
                                        id: agentSearchField
                                        Layout.fillWidth: true
                                        placeholderText: root.local("بحث…", "Search…")
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(11)
                                        Accessible.name: placeholderText
                                        onTextChanged: {
                                            root.agentSearch = text
                                            agentSearchDelay.restart()
                                        }
                                        Timer {
                                            id: agentSearchDelay
                                            interval: 180
                                            repeat: false
                                            onTriggered: root.agentLoadSessions()
                                        }
                                    }
                                    QQC2.CheckBox {
                                        Layout.fillWidth: true
                                        text: root.local("المؤرشفة", "Archived")
                                        checked: root.agentShowArchived
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(10)
                                        onToggled: {
                                            root.agentShowArchived = checked
                                            root.agentLoadSessions()
                                        }
                                    }
                                    Flickable {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        contentWidth: width
                                        contentHeight: sessCol.implicitHeight
                                        clip: true
                                        boundsBehavior: Flickable.StopAtBounds
                                        QQC2.ScrollBar.vertical: QQC2.ScrollBar { }
                                        ColumnLayout {
                                            id: sessCol
                                            width: parent.width
                                            spacing: 2
                                            Repeater {
                                                model: root.agentSessions
                                                delegate: Rectangle {
                                                    required property var modelData
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: root.fs(34)
                                                    radius: root.fs(7)
                                                    color: root.agentCurrent === modelData.id
                                                           ? Qt.rgba(root.novaBlue.r, root.novaBlue.g, root.novaBlue.b, 0.16)
                                                           : "transparent"
                                                    Text {
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        anchors.left: parent.left
                                                        anchors.right: pinSessionButton.left
                                                        anchors.margins: 8
                                                        text: modelData.label
                                                        elide: Text.ElideRight
                                                        color: root.agentCurrent === modelData.id ? root.novaBlue : root.textMute
                                                        font.family: root.uiFont
                                                        font.pixelSize: root.typePx(11)
                                                    }
                                                    Item {
                                                        id: pinSessionButton
                                                        z: 3
                                                        anchors.right: parent.right
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        width: root.fs(30)
                                                        height: root.fs(30)
                                                        Kirigami.Icon {
                                                            anchors.centerIn: parent
                                                            source: "pin"
                                                            color: modelData.pinned
                                                                ? root.novaBlue : root.textMute
                                                            width: root.fs(16)
                                                            height: root.fs(16)
                                                        }
                                                        ActionArea {
                                                            anchors.fill: parent
                                                            actionName: root.local(
                                                                modelData.pinned ? "إلغاء التثبيت" : "تثبيت",
                                                                modelData.pinned ? "Unpin" : "Pin")
                                                            focusRadius: root.fs(7)
                                                            onTriggered: root.agentUpdateSession(
                                                                modelData.id, { pinned: !modelData.pinned })
                                                        }
                                                    }
                                                    ActionArea {
                                                        anchors.fill: parent
                                                        actionName: modelData.label
                                                        checkable: true
                                                        checked: root.agentCurrent === modelData.id
                                                        focusRadius: root.fs(7)
                                                        onTriggered: root.agentOpen(modelData.id, modelData.key)
                                                    }
                                                }
                                            }
                                            Text {
                                                visible: root.agentSessions.length === 0
                                                Layout.fillWidth: true
                                                Layout.topMargin: 10
                                                text: root.local("لا محادثات بعد",
                                                                 "No sessions yet")
                                                horizontalAlignment: Text.AlignHCenter
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(10)
                                            }
                                        }
                                    }
                                }
                            }

                            // ── thread ──
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: design.space2

                                RowLayout {
                                    visible: root.agentCurrent !== ""
                                    Layout.fillWidth: true
                                    spacing: design.space1
                                    QQC2.TextField {
                                        id: agentTitleField
                                        Layout.fillWidth: true
                                        text: root.agentCurrentLabel
                                        placeholderText: root.local("اسم المحادثة", "Conversation name")
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(11)
                                        onAccepted: root.agentUpdateSession(
                                            root.agentCurrent, { title: text })
                                    }
                                    MoButton {
                                        label: root.local("إعادة تسمية", "Rename")
                                        enabled_: agentTitleField.text.trim() !== ""
                                        onClicked: root.agentUpdateSession(
                                            root.agentCurrent, { title: agentTitleField.text })
                                    }
                                    MoButton {
                                        label: root.local("أرشفة", "Archive")
                                        onClicked: root.agentUpdateSession(
                                            root.agentCurrent, { archived: true })
                                    }
                                }

                                Card {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    Flickable {
                                        id: threadFlick
                                        anchors.fill: parent
                                        anchors.margins: 10
                                        contentWidth: width
                                        contentHeight: msgCol.implicitHeight
                                        clip: true
                                        boundsBehavior: Flickable.StopAtBounds
                                        QQC2.ScrollBar.vertical: QQC2.ScrollBar { }
                                        onContentHeightChanged: contentY = Math.max(0, contentHeight - height)
                                        ColumnLayout {
                                            id: msgCol
                                            width: parent.width
                                            spacing: 6
                                            Repeater {
                                                model: root.agentThread
                                                delegate: Rectangle {
                                                    required property var modelData
                                                    readonly property bool mine: modelData.role === "user"
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: agentBubble.implicitHeight + 16
                                                    radius: design.radiusSmall
                                                    color: mine
                                                        ? Qt.rgba(root.novaBlue.r, root.novaBlue.g, root.novaBlue.b, 0.14)
                                                        : Qt.rgba(root.hairline.r, root.hairline.g, root.hairline.b, 0.18)
                                                    Text {
                                                        id: agentBubble
                                                        anchors.left: parent.left
                                                        anchors.right: parent.right
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        anchors.margins: 10
                                                        text: modelData.text
                                                        wrapMode: Text.Wrap
                                                        color: root.textHi
                                                        font.family: root.uiFont
                                                        font.pixelSize: root.typePx(12)
                                                    }
                                                }
                                            }
                                            Text {
                                                visible: root.agentThread.length === 0
                                                Layout.fillWidth: true
                                                Layout.topMargin: 30
                                                text: root.local(
                                                    "اختر محادثة، أو اكتب رسالة لتبدأ واحدة جديدة",
                                                    "Choose a session, or write a message to start one")
                                                horizontalAlignment: Text.AlignHCenter
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(11)
                                            }
                                        }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: design.space2
                                    QQC2.TextField {
                                        id: agentInput
                                        Layout.fillWidth: true
                                        placeholderText: root.local("اكتب رسالة…", "Message")
                                        enabled: root.agentReady && !root.agentBusy
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(12)
                                        onAccepted: if (root.agentReady) {
                                            root.agentSend(text)
                                            text = ""
                                        }
                                    }
                                    MoButton {
                                        label: root.agentBusy ? "…"
                                                                  : root.local("إرسال", "Send")
                                        enabled_: root.agentReady && !root.agentBusy
                                        onClicked: { root.agentSend(agentInput.text); agentInput.text = "" }
                                    }
                                }
                            }
                        }

                        ColumnLayout {
                            visible: root.agentMachineConfigured
                                     && root.agentWorkspaceTab === "projects"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: design.space2
                            RowLayout {
                                Layout.fillWidth: true
                                QQC2.TextField {
                                    id: projectPathField
                                    Layout.fillWidth: true
                                    placeholderText: root.local(
                                        "مسار مشروع داخل مجلد المنزل…",
                                        "Project path inside your home…")
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(11)
                                    onAccepted: root.agentAddProject(text)
                                }
                                MoButton {
                                    label: root.local("إضافة مشروع", "Add project")
                                    enabled_: projectPathField.text.trim() !== ""
                                    onClicked: root.agentAddProject(projectPathField.text)
                                }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: design.space2
                                ListView {
                                    Layout.preferredWidth: root.fs(250)
                                    Layout.fillHeight: true
                                    model: root.agentProjects
                                    spacing: design.space1
                                    clip: true
                                    QQC2.ScrollBar.vertical: QQC2.ScrollBar { }
                                    delegate: Card {
                                        required property var modelData
                                        width: ListView.view.width
                                        height: root.fs(86)
                                        ColumnLayout {
                                            anchors.fill: parent
                                            spacing: 2
                                            RowLayout {
                                                Layout.fillWidth: true
                                                Kirigami.Icon {
                                                    source: "folder"
                                                    color: root.novaBlue
                                                    Layout.preferredWidth: root.fs(20)
                                                    Layout.preferredHeight: root.fs(20)
                                                }
                                                Text {
                                                    Layout.fillWidth: true
                                                    text: modelData.name
                                                    color: root.textHi
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.typePx(11)
                                                    font.weight: Font.DemiBold
                                                }
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: modelData.path
                                                elide: Text.ElideMiddle
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(9)
                                            }
                                            RowLayout {
                                                Layout.fillWidth: true
                                                Item { Layout.fillWidth: true }
                                                MoButton {
                                                    label: root.local("فتح", "Open")
                                                    onClicked: root.agentOpenProject(modelData.id)
                                                }
                                                MoButton {
                                                    label: root.local("مهمة", "Task")
                                                    onClicked: {
                                                        root.agentTaskProject = modelData.id
                                                        root.agentWorkspaceTab = "tasks"
                                                        root.agentLoadTasks()
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                                Card {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    ColumnLayout {
                                        anchors.fill: parent
                                        spacing: design.space1
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Text {
                                                Layout.fillWidth: true
                                                text: root.agentProjectCurrent
                                                      ? root.local("مساحة عمل المشروع", "Project workbench")
                                                      : root.local("اختر مشروعاً لعرض ملفاته وتغييرات Git",
                                                                   "Select a project to inspect files and Git changes")
                                                color: root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(11)
                                                font.weight: Font.DemiBold
                                            }
                                            MoButton {
                                                visible: root.agentProjectCurrent !== ""
                                                label: root.local("الحالة", "Status")
                                                onClicked: root.agentLoadProjectGitStatus()
                                            }
                                            MoButton {
                                                visible: root.agentProjectCurrent !== ""
                                                label: root.local("الفروقات", "Diff")
                                                onClicked: root.agentLoadProjectDiff("")
                                            }
                                        }
                                        Text {
                                            visible: root.agentProjectCurrent !== ""
                                            Layout.fillWidth: true
                                            text: (root.agentProjectPath || ".")
                                            color: root.textMute
                                            font.family: "JetBrains Mono"
                                            font.pixelSize: root.typePx(9)
                                            elide: Text.ElideMiddle
                                        }
                                        RowLayout {
                                            visible: root.agentProjectCurrent !== ""
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            spacing: design.space1
                                            ListView {
                                                Layout.preferredWidth: root.fs(220)
                                                Layout.fillHeight: true
                                                model: root.agentProjectEntries
                                                clip: true
                                                spacing: 1
                                                QQC2.ScrollBar.vertical: QQC2.ScrollBar { }
                                                header: MoButton {
                                                    visible: root.agentProjectPath !== ""
                                                    width: ListView.view.width
                                                    label: root.local("↩ المجلد الأعلى", "↩ Parent folder")
                                                    onClicked: root.agentLoadProjectFiles(root.agentProjectParent)
                                                }
                                                delegate: Rectangle {
                                                    required property var modelData
                                                    width: ListView.view.width
                                                    height: root.fs(30)
                                                    radius: root.fs(6)
                                                    color: "transparent"
                                                    RowLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: 4
                                                        Kirigami.Icon {
                                                            source: modelData.type === "directory" ? "folder" : "text-x-generic"
                                                            color: modelData.type === "directory" ? root.novaBlue : root.textMute
                                                            Layout.preferredWidth: root.fs(15)
                                                            Layout.preferredHeight: root.fs(15)
                                                        }
                                                        Text {
                                                            Layout.fillWidth: true
                                                            text: modelData.name
                                                            elide: Text.ElideMiddle
                                                            color: root.textHi
                                                            font.family: root.uiFont
                                                            font.pixelSize: root.typePx(9)
                                                        }
                                                    }
                                                    ActionArea {
                                                        anchors.fill: parent
                                                        actionName: modelData.name
                                                        focusRadius: root.fs(6)
                                                        onTriggered: modelData.type === "directory"
                                                            ? root.agentLoadProjectFiles(modelData.path)
                                                            : root.agentLoadProjectFile(modelData.path)
                                                    }
                                                }
                                            }
                                            Rectangle {
                                                Layout.fillWidth: true
                                                Layout.fillHeight: true
                                                radius: root.fs(7)
                                                color: Qt.rgba(0.02, 0.025, 0.03, 0.96)
                                                Flickable {
                                                    anchors.fill: parent
                                                    anchors.margins: design.space1
                                                    contentWidth: width
                                                    contentHeight: projectPreview.implicitHeight
                                                    clip: true
                                                    QQC2.ScrollBar.vertical: QQC2.ScrollBar { }
                                                    TextEdit {
                                                        id: projectPreview
                                                        width: parent.width
                                                        readOnly: true
                                                        selectByMouse: true
                                                        text: root.agentProjectPreview
                                                        color: "#d7eee7"
                                                        selectionColor: root.novaBlue
                                                        selectedTextColor: root.accentText
                                                        font.family: "JetBrains Mono"
                                                        font.pixelSize: root.typePx(9)
                                                        wrapMode: TextEdit.WrapAnywhere
                                                        Accessible.name: root.local(
                                                            "معاينة الملف أو تغييرات Git",
                                                            "File or Git change preview")
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        ColumnLayout {
                            visible: root.agentMachineConfigured
                                     && root.agentWorkspaceTab === "tasks"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: design.space2
                            RowLayout {
                                Layout.fillWidth: true
                                QQC2.TextField {
                                    id: taskTitleField
                                    Layout.fillWidth: true
                                    placeholderText: root.local("صف المهمة…", "Describe a task…")
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(11)
                                    onAccepted: root.agentCreateTask(text)
                                }
                                MoButton {
                                    label: root.local("إنشاء", "Create")
                                    primary: true
                                    enabled_: taskTitleField.text.trim() !== ""
                                    onClicked: root.agentCreateTask(taskTitleField.text)
                                }
                            }
                            ListView {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                model: root.agentTasks
                                spacing: design.space1
                                clip: true
                                QQC2.ScrollBar.vertical: QQC2.ScrollBar { }
                                delegate: Card {
                                    required property var modelData
                                    width: ListView.view.width
                                    height: taskColumn.implicitHeight + root.fs(24)
                                    ColumnLayout {
                                        id: taskColumn
                                        anchors.fill: parent
                                        spacing: design.space1
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Text {
                                                Layout.fillWidth: true
                                                text: modelData.title
                                                color: root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(13)
                                                font.weight: Font.DemiBold
                                            }
                                            StatusPill {
                                                good: modelData.status === "completed"
                                                goodText: root.local("مكتملة", "Completed")
                                                badText: modelData.status
                                            }
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: root.local(
                                                (modelData.steps || []).length + " خطوات · "
                                                    + (modelData.tools || []).length + " أدوات",
                                                (modelData.steps || []).length + " steps · "
                                                    + (modelData.tools || []).length + " tools")
                                            color: root.textMute
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(10)
                                        }
                                        Text {
                                            visible: (modelData.description || "") !== ""
                                            Layout.fillWidth: true
                                            text: modelData.description || ""
                                            color: root.textMute
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(10)
                                            wrapMode: Text.Wrap
                                        }
                                        Repeater {
                                            model: modelData.steps || []
                                            delegate: Text {
                                                required property var modelData
                                                Layout.fillWidth: true
                                                text: (modelData.status === "completed" ? "✓ "
                                                       : modelData.status === "failed" ? "! " : "• ")
                                                      + modelData.title
                                                color: modelData.status === "failed"
                                                       ? root.badColor : root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(10)
                                                wrapMode: Text.Wrap
                                            }
                                        }
                                        Text {
                                            visible: (modelData.tools || []).length > 0
                                            Layout.fillWidth: true
                                            text: root.local("الأدوات: ", "Tools: ")
                                                  + (modelData.tools || []).map(function (tool) {
                                                      return tool.name
                                                  }).join(" · ")
                                            color: root.novaCyan
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(9)
                                            wrapMode: Text.WrapAnywhere
                                        }
                                        Text {
                                            visible: (modelData.error || "") !== ""
                                            Layout.fillWidth: true
                                            text: modelData.error || ""
                                            color: root.badColor
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(10)
                                            wrapMode: Text.Wrap
                                        }
                                        Text {
                                            visible: (modelData.result || "") !== ""
                                            Layout.fillWidth: true
                                            text: modelData.result || ""
                                            color: root.textHi
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(10)
                                            wrapMode: Text.Wrap
                                        }
                                        Repeater {
                                            model: root.agentTaskApprovals(modelData.id)
                                            delegate: Rectangle {
                                                required property var modelData
                                                Layout.fillWidth: true
                                                height: approvalColumn.implicitHeight + root.fs(20)
                                                radius: root.fs(9)
                                                color: Qt.rgba(root.warnColor.r, root.warnColor.g,
                                                               root.warnColor.b, 0.10)
                                                border.color: Qt.rgba(root.warnColor.r, root.warnColor.g,
                                                                      root.warnColor.b, 0.42)
                                                ColumnLayout {
                                                    id: approvalColumn
                                                    anchors.fill: parent
                                                    anchors.margins: root.fs(10)
                                                    spacing: design.space1
                                                    Text {
                                                        Layout.fillWidth: true
                                                        text: root.local("بانتظار موافقتك", "Waiting for your approval")
                                                        color: root.warnColor
                                                        font.family: root.uiFont
                                                        font.pixelSize: root.typePx(11)
                                                        font.weight: Font.DemiBold
                                                    }
                                                    TextEdit {
                                                        Layout.fillWidth: true
                                                        readOnly: true
                                                        selectByMouse: true
                                                        text: modelData.command
                                                        color: root.textHi
                                                        font.family: "JetBrains Mono"
                                                        font.pixelSize: root.typePx(9)
                                                        wrapMode: TextEdit.WrapAnywhere
                                                    }
                                                    Text {
                                                        visible: modelData.cwd !== ""
                                                        Layout.fillWidth: true
                                                        text: modelData.cwd
                                                        color: root.textMute
                                                        font.family: "JetBrains Mono"
                                                        font.pixelSize: root.typePx(8)
                                                        elide: Text.ElideMiddle
                                                    }
                                                    RowLayout {
                                                        Layout.fillWidth: true
                                                        Item { Layout.fillWidth: true }
                                                        MoButton {
                                                            visible: modelData.allowed.indexOf("allow-always") >= 0
                                                            label: root.local("السماح دائماً", "Always allow")
                                                            onClicked: root.agentResolveApproval(
                                                                modelData.id, "allow-always")
                                                        }
                                                        MoButton {
                                                            visible: modelData.allowed.indexOf("allow-once") >= 0
                                                            label: root.local("السماح مرة", "Allow once")
                                                            primary: true
                                                            onClicked: root.agentResolveApproval(
                                                                modelData.id, "allow-once")
                                                        }
                                                        MoButton {
                                                            visible: modelData.allowed.indexOf("deny") >= 0
                                                            label: root.local("رفض", "Deny")
                                                            onClicked: root.agentResolveApproval(
                                                                modelData.id, "deny")
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                        RowLayout {
                                            Layout.fillWidth: true
                                            visible: modelData.status !== "completed"
                                                     && modelData.status !== "cancelled"
                                            Item { Layout.fillWidth: true }
                                            MoButton {
                                                label: modelData.status === "running"
                                                    ? root.local("إيقاف مؤقت", "Pause")
                                                    : modelData.status === "paused"
                                                        ? root.local("استكمال", "Resume")
                                                    : modelData.status === "failed"
                                                        ? root.local("إعادة المحاولة", "Retry")
                                                        : root.local("بدء", "Start")
                                                onClicked: root.agentTaskAction(
                                                    modelData.id,
                                                    modelData.status === "running" ? "pause"
                                                        : modelData.status === "paused" ? "resume" : "start")
                                            }
                                            MoButton {
                                                label: root.local("إلغاء", "Cancel")
                                                onClicked: root.agentTaskAction(modelData.id, "cancel")
                                            }
                                        }
                                    }
                                }
                            }
                            Timer {
                                interval: 1500
                                repeat: true
                                running: root.panel === "agent"
                                         && root.agentWorkspaceTab === "tasks"
                                         && root.agentTasks.some(function (task) {
                                             return task.status === "running"
                                         })
                                onTriggered: root.agentLoadTasks()
                            }
                        }

                        ColumnLayout {
                            visible: root.agentMachineConfigured
                                     && root.agentWorkspaceTab === "terminal"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: design.space2
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: design.space1
                                Repeater {
                                    model: root.agentTerminals
                                    delegate: MoButton {
                                        required property var modelData
                                        label: modelData.title
                                        primary: root.agentTerminalCurrent === modelData.id
                                        onClicked: root.agentSelectTerminal(modelData.id)
                                    }
                                }
                                MoButton {
                                    label: root.local("+ طرفية", "+ Terminal")
                                    onClicked: root.agentStartTerminal()
                                }
                                Item { Layout.fillWidth: true }
                                MoButton {
                                    visible: root.agentTerminalCurrent !== ""
                                    label: root.local("إيقاف", "Stop")
                                    onClicked: root.agentStopTerminal()
                                }
                            }
                            Card {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                color: Qt.rgba(0.02, 0.025, 0.03, 0.96)
                                Flickable {
                                    id: terminalFlick
                                    anchors.fill: parent
                                    anchors.margins: design.space2
                                    contentWidth: width
                                    contentHeight: terminalOutput.implicitHeight
                                    clip: true
                                    boundsBehavior: Flickable.StopAtBounds
                                    QQC2.ScrollBar.vertical: QQC2.ScrollBar { }
                                    onContentHeightChanged: contentY = Math.max(0, contentHeight - height)
                                    TextEdit {
                                        id: terminalOutput
                                        width: terminalFlick.width
                                        text: root.agentTerminalOutput
                                        readOnly: true
                                        selectByMouse: true
                                        wrapMode: TextEdit.WrapAnywhere
                                        color: "#d7eee7"
                                        selectionColor: root.novaBlue
                                        selectedTextColor: root.accentText
                                        font.family: "JetBrains Mono"
                                        font.pixelSize: root.typePx(11)
                                        Accessible.name: root.local("مخرجات الطرفية", "Terminal output")
                                    }
                                }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                QQC2.TextField {
                                    id: terminalInput
                                    Layout.fillWidth: true
                                    enabled: root.agentTerminalCurrent !== ""
                                    placeholderText: root.local("اكتب أمراً كمستخدمك…", "Run as your user…")
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: root.typePx(11)
                                    onAccepted: {
                                        root.agentWriteTerminal(text + "\n")
                                        text = ""
                                    }
                                }
                                MoButton {
                                    label: root.local("تشغيل", "Run")
                                    enabled_: root.agentTerminalCurrent !== ""
                                              && terminalInput.text !== ""
                                    onClicked: {
                                        root.agentWriteTerminal(terminalInput.text + "\n")
                                        terminalInput.text = ""
                                    }
                                }
                            }
                            Timer {
                                interval: 180
                                repeat: true
                                running: root.panel === "agent"
                                         && root.agentWorkspaceTab === "terminal"
                                         && root.agentTerminalCurrent !== ""
                                onTriggered: root.agentPollTerminal()
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
            radius: design.radiusControl
            width: Math.min(parent.width - 40, toastCol.implicitWidth + 30)
            height: toastCol.implicitHeight + 20
            color: root.surface2
            border.width: 1
            border.color: Qt.rgba(root.novaCyan.r, root.novaCyan.g,
                                  root.novaCyan.b, 0.5)
            Behavior on opacity { NumberAnimation { duration: root.motionEnabled ? design.motionGeometry : 0 } }

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
                    // Neutral "working" — not a ✓ success claim. The action may
                    // fail-closed (no confirm dialog) or be a no-op; the orb only
                    // knows it dispatched the request, not that it completed.
                    text: root.local("جارٍ التنفيذ…", "Working…")
                    color: root.novaCyan
                    font.family: root.uiFont
                    font.pixelSize: root.typePx(11)
                    font.weight: Font.DemiBold
                }
                Text {
                    text: toast.msg
                    color: root.textHi
                    font.family: root.uiFont
                    font.pixelSize: root.typePx(13)
                }
            }
        }

        // ── The brain picker ────────────────────────────────────────────────
        // Every entry here is REAL: local models come from the selected engine's
        // inventory, cloud ones from the provider's own /v1/models. Nothing is
        // invented, and a provider with no model list says so instead of being
        // given a made-up menu.
        Rectangle {
            id: brainPickerDialog
            anchors.fill: parent
            z: 250
            visible: root.pickerOpen
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                           Kirigami.Theme.textColor.b, 0.69)
            focus: visible
            Accessible.role: Accessible.Dialog
            Accessible.name: root.moaiRtl ? "اختيار عقل Mo AI" : "Choose the Mo AI brain"
            Keys.onEscapePressed: root.pickerOpen = false
            onVisibleChanged: if (visible) forceActiveFocus()
            MouseArea { anchors.fill: parent; onClicked: root.pickerOpen = false }

            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 86
                width: Math.min(parent.width - 40, 430)
                height: Math.min(parent.height - 130, pickCol.implicitHeight + 32)
                radius: design.radiusCard
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
                        spacing: design.space2
                        SectionTitle {
                            Layout.fillWidth: true
                            text: root.local("العقل والقوة", "Brain & power")
                            font.pixelSize: root.typePx(15)
                        }
                        MoButton {
                            label: root.modelsLoading ? "…"
                                                      : root.local("تحديث", "Refresh")
                            iconName: "moos-refresh-symbolic"
                            enabled_: !root.modelsLoading
                            onClicked: root.loadModels()
                        }
                        MoButton {
                            label: root.local("إغلاق", "Close")
                            iconName: "moos-close-symbolic"
                            onClicked: root.pickerOpen = false
                        }
                    }

                    SectionNote {
                        Layout.fillWidth: true
                        text: root.local("اختيارك يسري على هذه المحادثة فقط.",
                                         "Applies to this conversation only.")
                        font.pixelSize: root.typePx(10)
                    }

                    Rectangle {
                        id: hybridRow
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.fs(52)
                        radius: design.radiusSmall
                        color: root.routeIsHybrid
                            ? Qt.rgba(root.novaCyan.r, root.novaCyan.g,
                                      root.novaCyan.b, 0.16)
                            : hybridMa.containsMouse ? root.surface2 : "transparent"
                        border.width: 1
                        border.color: root.routeIsHybrid ? root.novaCyan : root.hairline
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: design.space2
                            Kirigami.Icon {
                                source: "moos-ai-symbolic"
                                color: root.novaCyan
                                Layout.preferredWidth: root.fs(20)
                                Layout.preferredHeight: root.fs(20)
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1
                                Text {
                                    text: root.local("هجين ذكي", "Smart Hybrid")
                                    color: root.textHi
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(12)
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "خاص وسريع محلياً؛ السحابة للمهام الصعبة فقط",
                                        "Private and fast locally; cloud only for harder work")
                                    color: root.textMute
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(9)
                                    elide: Text.ElideRight
                                }
                            }
                            Text {
                                visible: root.routeIsHybrid
                                text: "✓"
                                color: root.novaCyan
                                font.pixelSize: root.typePx(13)
                            }
                        }
                        ActionArea {
                            id: hybridMa
                            anchors.fill: parent
                            actionName: root.local("اختيار العقل الهجين", "Choose Hybrid brain")
                            checkable: true
                            checked: root.routeIsHybrid
                            focusRadius: root.fs(9)
                            onTriggered: root.pickRoute("hybrid")
                        }
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
                                text: root.local("محلي وخاص", "Local & private")
                                color: root.textMute
                                font.family: root.uiFont
                                font.pixelSize: root.typePx(10)
                                font.weight: Font.DemiBold
                            }

                            Repeater {
                                model: root.localModels
                                delegate: Rectangle {
                                    id: locRow
                                    required property var modelData
                                    readonly property bool on_: root.route === locRow.modelData.id
                                    readonly property bool downloading:
                                        root.pullModel !== ""
                                        && (locRow.modelData.id === "local:" + root.pullModel
                                            || locRow.modelData.id === root.pullModel)
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: root.fs(40)
                                    radius: design.radiusSmall
                                    color: locRow.on_
                                         ? Qt.rgba(root.okColor.r, root.okColor.g,
                                                   root.okColor.b, 0.14)
                                         : locMa.containsMouse ? root.surface2 : "transparent"
                                    border.width: 1
                                    border.color: locRow.on_ ? root.okColor : "transparent"
                                    Behavior on color { ColorAnimation { duration: root.motionEnabled ? design.motionFast : 0 } }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 10
                                        anchors.rightMargin: 10
                                        spacing: 9

                                        Kirigami.Icon {
                                            source: "moos-system-symbolic"
                                            color: root.okColor
                                            Layout.preferredWidth: root.fs(15)
                                            Layout.preferredHeight: root.fs(15)
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 0
                                            Text {
                                                Layout.fillWidth: true
                                                text: locRow.modelData.label
                                                color: root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(12)
                                                font.weight: locRow.on_ ? Font.DemiBold : Font.Normal
                                                elide: Text.ElideRight
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                // The curated starters carry a bilingual note and an
                                                // honest download size from moai-control — the user
                                                // knows what each brain is good at, and what the tap
                                                // costs, BEFORE anything happens.
                                                text: locRow.downloading
                                                      ? root.local(
                                                            "يُنزَّل الآن — " + root.pullPercent + "٪",
                                                            "Downloading — " + root.pullPercent + "%; keep this open")
                                                      : (locRow.modelData.note
                                                         ? root.localLegacy(locRow.modelData.note) + "  ·  "
                                                         : "")
                                                      + (!locRow.modelData.pulled
                                                        ? ((locRow.modelData.size_gb > 0
                                                            ? "~" + locRow.modelData.size_gb + " GB — " : "")
                                                           + root.local("تحميل بضغطة",
                                                                        "One-tap download"))
                                                        : locRow.modelData.serving
                                                        ? root.local("جاهز", "Ready")
                                                        : root.local(
                                                            "محمَّل — يُعاد تشغيل العقل",
                                                            "Downloaded — restarts the brain"))
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(9)
                                                elide: Text.ElideRight
                                            }
                                        }
                                        Text {
                                            visible: locRow.on_
                                            text: "✓"
                                            color: root.okColor
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(13)
                                            font.weight: Font.DemiBold
                                        }
                                    }
                                    // The download bar, drawn along the bottom edge of
                                    // this row and ONLY while this brain is the one
                                    // downloading. A bar on every row would claim the
                                    // whole list is arriving.
                                    Rectangle {
                                        visible: locRow.downloading
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.bottom: parent.bottom
                                        anchors.margins: 1
                                        height: 3
                                        radius: height / 2
                                        color: Qt.rgba(root.okColor.r, root.okColor.g,
                                                       root.okColor.b, 0.18)
                                        Rectangle {
                                            anchors.left: parent.left
                                            anchors.top: parent.top
                                            anchors.bottom: parent.bottom
                                            width: parent.width * (root.pullPercent / 100.0)
                                            radius: root.fs(2)
                                            color: root.okColor
                                            Behavior on width { NumberAnimation { duration: root.motionEnabled ? design.motionGeometry : 0 } }
                                        }
                                    }
                                    ActionArea {
                                        id: locMa
                                        anchors.fill: parent
                                        actionName: locRow.modelData.label
                                        checkable: true
                                        checked: locRow.on_
                                        focusRadius: root.fs(9)
                                        // Not pickRoute: an un-pulled brain must be
                                        // fetched before it can answer anything.
                                        onTriggered: root.pickOrPull(locRow.modelData)
                                    }
                                }
                            }

                            // The download's own failure, said once, under the list —
                            // no disk, no network, a tag the registry moved. Silence
                            // here is what made the old refusal unexplainable.
                            Text {
                                visible: root.pullError !== ""
                                Layout.fillWidth: true
                                text: root.pullError
                                color: root.badColor
                                font.family: root.uiFont
                                font.pixelSize: root.typePx(9)
                                wrapMode: Text.WordWrap
                            }

                            // ── Cloud ──────────────────────────────────────
                            Text {
                                Layout.topMargin: 8
                                text: root.local("سحابي", "Cloud")
                                color: root.textMute
                                font.family: root.uiFont
                                font.pixelSize: root.typePx(10)
                                font.weight: Font.DemiBold
                            }

                            Repeater {
                                model: root.cloudModels
                                delegate: Rectangle {
                                    id: cldRow
                                    required property var modelData
                                    readonly property bool on_: root.route === cldRow.modelData.id
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: root.fs(34)
                                    radius: design.radiusSmall
                                    color: cldRow.on_
                                         ? Qt.rgba(root.novaViolet.r, root.novaViolet.g,
                                                   root.novaViolet.b, 0.18)
                                         : cldMa.containsMouse ? root.surface2 : "transparent"
                                    border.width: 1
                                    border.color: cldRow.on_ ? root.novaViolet : "transparent"
                                    Behavior on color { ColorAnimation { duration: root.motionEnabled ? design.motionFast : 0 } }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 10
                                        anchors.rightMargin: 10
                                        spacing: 9

                                        Rectangle {
                                            Layout.preferredWidth: root.fs(7)
                                            Layout.preferredHeight: root.fs(7)
                                            Layout.alignment: Qt.AlignVCenter
                                            radius: height / 2
                                            color: root.novaViolet
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: cldRow.modelData.label
                                            color: root.textHi
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(12)
                                            font.weight: cldRow.on_ ? Font.DemiBold : Font.Normal
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            visible: cldRow.on_
                                            text: "✓"
                                            color: root.novaViolet
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(13)
                                            font.weight: Font.DemiBold
                                        }
                                    }
                                    ActionArea {
                                        id: cldMa
                                        anchors.fill: parent
                                        actionName: cldRow.modelData.label
                                        checkable: true
                                        checked: cldRow.on_
                                        focusRadius: root.fs(9)
                                        onTriggered: root.pickRoute(cldRow.modelData.id)
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
                                font.pixelSize: root.typePx(10)
                                wrapMode: Text.Wrap
                            }
                        }
                    }

                    MoButton {
                        Layout.fillWidth: true
                        label: root.local("المزوّد والمفتاح", "Provider & API key")
                        iconName: "moos-settings-symbolic"
                        onClicked: {
                            root.pickerOpen = false
                            root.settingsOpen = true
                        }
                    }
                }
            }
        }

        // ── Settings ────────────────────────────────────────────────────────
        // Redesigned: one sectioned sheet backed by moai-agent-api (127.0.0.1:8077),
        // which owns the SAME openclaw.json that drives the Telegram bot. Mo AI and
        // OpenClaw therefore cannot disagree about the brain, the key or the channel —
        // there is exactly one place each of those lives.
        //
        // Secrets are WRITE-ONLY here, as in moai-control: the API reports has_key /
        // has_token and never returns the value, so this sheet cannot leak what it saved.
        Rectangle {
            id: settingsDialog
            anchors.fill: parent
            z: 300
            visible: root.settingsOpen
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                           Kirigami.Theme.textColor.b, 0.82)
            focus: visible
            Accessible.role: Accessible.Dialog
            Accessible.name: root.moaiRtl ? "إعدادات Mo AI" : "Mo AI settings"
            Keys.onEscapePressed: root.settingsOpen = false
            onVisibleChanged: if (visible) forceActiveFocus()
            MouseArea { anchors.fill: parent; onClicked: root.settingsOpen = false }

            Rectangle {
                anchors.centerIn: parent
                width: Math.min(parent.width - 48, 760)
                height: Math.min(parent.height - 48, 640)
                radius: design.radiusCard
                color: root.surface1
                border.color: root.hairline
                border.width: 1
                MouseArea { anchors.fill: parent }   // ابتلع النقر حتى لا يُغلق

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: design.space3

                    // ── header ──
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        ColumnLayout {
                            spacing: 0
                            Text {
                                text: root.local("الإعدادات", "Settings")
                                color: root.textHi
                                font.family: root.uiFont
                                font.pixelSize: root.typePx(17)
                                font.weight: Font.DemiBold
                            }
                            Text {
                                text: root.local(
                                    "إعداد واحد لسطح المكتب وOpenClaw وتليجرام وواتساب",
                                    "One configuration for desktop, OpenClaw, Telegram and WhatsApp")
                                color: root.textMute
                                font.family: root.uiFont
                                font.pixelSize: root.typePx(10)
                            }
                        }
                        Item { Layout.fillWidth: true }
                        StatusPill {
                            good: root.cfgError === ""
                            goodText: root.cfgSaving ? root.local("يحفظ…", "Saving")
                                                     : root.local("متصل", "Linked")
                            badText: root.local("لوحة التحكم متوقفة",
                                                "Control service is offline")
                        }
                        MoButton {
                            label: root.local("إغلاق", "Close")
                            iconName: "moos-close-symbolic"
                            onClicked: root.settingsOpen = false
                        }
                    }

                    // ── section tabs ──
                    GridLayout {
                        Layout.fillWidth: true
                        columns: width < root.fs(560) ? 3 : 4
                        rowSpacing: design.space1
                        columnSpacing: design.space1
                        Repeater {
                            model: [
                                { id: "models",      ar: "النماذج",   en: "Models" },
                                { id: "providers",   ar: "المزوّدون", en: "Providers" },
                                { id: "openclaw",    ar: "OpenClaw",  en: "OpenClaw" },
                                { id: "telegram",    ar: "تليجرام",   en: "Telegram" },
                                { id: "whatsapp",    ar: "واتساب",    en: "WhatsApp" },
                                { id: "voice",       ar: "الصوت",     en: "Voice" },
                                { id: "permissions", ar: "الصلاحيات", en: "Permissions" },
                                { id: "memory",      ar: "الذاكرة",   en: "Memory" },
                                { id: "projects",    ar: "المشاريع",  en: "Projects" },
                                { id: "terminal",    ar: "الطرفية",   en: "Terminal" },
                                { id: "privacy",     ar: "الخصوصية",  en: "Privacy" },
                                { id: "appearance",  ar: "المظهر",    en: "Appearance" }
                            ]
                            delegate: Rectangle {
                                required property var modelData
                                readonly property bool on_: root.cfgTab === modelData.id
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.fs(32)
                                radius: design.radiusSmall
                                color: on_ ? Qt.rgba(root.novaBlue.r, root.novaBlue.g, root.novaBlue.b, 0.18)
                                           : "transparent"
                                border.width: 1
                                border.color: on_ ? root.novaBlue : root.hairline
                                Text {
                                    anchors.centerIn: parent
                                    text: root.local(modelData.ar, modelData.en)
                                    color: on_ ? root.novaBlue : root.textMute
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(12)
                                    font.weight: on_ ? Font.DemiBold : Font.Normal
                                }
                                ActionArea {
                                    anchors.fill: parent
                                    actionName: root.moaiRtl ? modelData.ar : modelData.en
                                    checkable: true
                                    checked: parent.on_
                                    focusRadius: root.fs(9)
                                    onTriggered: root.cfgTab = modelData.id
                                }
                            }
                        }
                    }

                    Text {
                        visible: root.cfgError !== ""
                        Layout.fillWidth: true
                        text: root.cfgError
                        color: root.badColor
                        font.family: root.uiFont
                        font.pixelSize: root.typePx(11)
                        wrapMode: Text.Wrap
                    }

                    // ── body ──
                    Flickable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        contentWidth: width
                        contentHeight: cfgBody.implicitHeight
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        QQC2.ScrollBar.vertical: QQC2.ScrollBar { }

                        ColumnLayout {
                            id: cfgBody
                            width: parent.width
                            spacing: design.space3

                            // ══ BRAIN ══════════════════════════════════════
                            ColumnLayout {
                                visible: root.cfgTab === "privacy" || root.cfgTab === "providers"
                                Layout.fillWidth: true
                                spacing: design.space2

                                SectionNote {
                                    visible: root.cfgTab === "privacy"
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "اختر محلياً أو سحابياً أو دع الوضع الهجين يحمي الخاص ويصعّد الصعب.",
                                        "Choose local or cloud, or let Hybrid keep private work local and escalate difficult tasks.")
                                }

                                Repeater {
                                    visible: root.cfgTab === "privacy"
                                    model: [
                                        { id: "local", ar: "محلي وخاص", en: "Local & private",
                                          dAr: "كل رسالة تعالج على هذا الجهاز",
                                          dEn: "Every message is processed on this device" },
                                        { id: "cloud", ar: "سحابي", en: "Cloud",
                                          dAr: "كل رسالة تذهب إلى المزوّد الذي اخترته",
                                          dEn: "Every message goes to your chosen provider" },
                                        { id: "hybrid", ar: "هجين ذكي", en: "Smart hybrid",
                                          dAr: "يحافظ على الخاص محلياً ويستخدم السحابة للمهام الصعبة فقط",
                                          dEn: "Keeps private work local and uses cloud only for difficult tasks" }
                                    ]
                                    delegate: Rectangle {
                                        required property var modelData
                                        readonly property bool on_: root.cfgMode === modelData.id
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: root.fs(50)
                                        radius: design.radiusControl
                                        color: on_ ? Qt.rgba(root.novaBlue.r, root.novaBlue.g, root.novaBlue.b, 0.13)
                                                   : "transparent"
                                        border.width: 1
                                        border.color: on_ ? root.novaBlue : root.hairline
                                        ColumnLayout {
                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.verticalCenter: parent.verticalCenter
                                            anchors.margins: 12
                                            spacing: 1
                                            Text {
                                                text: root.local(modelData.ar, modelData.en)
                                                color: on_ ? root.novaBlue : root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(12)
                                                font.weight: Font.DemiBold
                                            }
                                            Text {
                                                text: root.local(modelData.dAr, modelData.dEn)
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(10)
                                            }
                                        }
                                        ActionArea {
                                            anchors.fill: parent
                                            actionName: root.local(modelData.ar, modelData.en)
                                            checkable: true
                                            checked: parent.on_
                                            focusRadius: root.fs(11)
                                            onTriggered: root.cfgMode = modelData.id
                                        }
                                    }
                                }

                                SectionTitle {
                                    visible: root.cfgTab === "providers"
                                    text: root.local("المزوّد السحابي", "Cloud provider")
                                    Layout.topMargin: 6
                                }

                                QQC2.ComboBox {
                                    id: provBox
                                    visible: root.cfgTab === "providers"
                                    Layout.fillWidth: true
                                    model: root.cfgProviderNames
                                    font.family: root.uiFont
                                    onActivated: {
                                        const p = root.cfgProviders[currentIndex]
                                        if (p && p.base) { baseField.text = p.base; modelField.text = p.model }
                                        root.cfgProvider = p ? p.id : ""
                                    }
                                }
                                QQC2.TextField {
                                    id: baseField
                                    visible: root.cfgTab === "providers"
                                    Layout.fillWidth: true
                                    placeholderText: "https://…/v1"
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(11)
                                }
                                QQC2.TextField {
                                    id: modelField
                                    visible: root.cfgTab === "providers"
                                    Layout.fillWidth: true
                                    placeholderText: root.local("اسم النموذج", "Model ID")
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(11)
                                }
                                SectionNote {
                                    id: cloudKeyLabel
                                    visible: root.cfgTab === "providers"
                                    Layout.fillWidth: true
                                    text: root.local("مفتاح API السحابي", "Cloud API key")
                                    Accessible.name: text
                                }
                                QQC2.TextField {
                                    id: keyField
                                    visible: root.cfgTab === "providers"
                                    Layout.fillWidth: true
                                    echoMode: TextInput.Password
                                    Accessible.name: root.local("مفتاح API السحابي",
                                                                "Cloud API key")
                                    Accessible.labelledBy: cloudKeyLabel
                                    placeholderText: root.cfgHasKey
                                        ? root.local(
                                            "المفتاح محفوظ — اتركه فارغاً لإبقائه",
                                            "Key saved — leave blank to keep it")
                                        : root.local("sk-…  (يُكتب ولا يُقرأ)",
                                                     "sk-…  (write-only)")
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(11)
                                }
                                SectionNote {
                                    visible: root.cfgTab === "providers"
                                    Layout.fillWidth: true
                                    text: root.cfgHasKey
                                        ? root.local(
                                            "مفتاح محفوظ في الإعداد. لن يُعرض هنا أبداً.",
                                            "A key is saved. It is never displayed here.")
                                        : root.local(
                                            "لا مفتاح محفوظ — الوضع السحابي لن يعمل بدونه.",
                                            "No key saved — cloud mode requires one.")
                                }
                            }

                            // ══ CHANNEL ════════════════════════════════════
                            ColumnLayout {
                                visible: root.cfgTab === "telegram" || root.cfgTab === "whatsapp"
                                Layout.fillWidth: true
                                spacing: design.space2

                                SectionNote {
                                    visible: root.cfgTab === "telegram"
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "بوت تليجرام — تكلّمه من جوالك وترى المحادثة في لوحة «الوكيل».",
                                        "Telegram bot — chat from your phone and see it in the Agent panel.")
                                }
                                SectionNote {
                                    visible: root.cfgTab === "telegram"
                                    Layout.fillWidth: true
                                    text: root.cfgChannelsBusy
                                        ? root.local("جارٍ فحص الاتصال…", "Checking connection…")
                                        : root.cfgChannels.telegram.connected
                                            ? root.local(
                                                "متصل فعلياً" + (root.cfgChannels.telegram.account ? " · @" + root.cfgChannels.telegram.account : ""),
                                                "Connected" + (root.cfgChannels.telegram.account ? " · @" + root.cfgChannels.telegram.account : ""))
                                            : root.cfgChannels.telegram.configured
                                                ? root.local("مهيّأ لكن غير متصل", "Configured but offline")
                                                : root.local("غير مهيّأ", "Not configured")
                                }
                                RowLayout {
                                    visible: root.cfgTab === "telegram"
                                    Layout.fillWidth: true
                                    Text {
                                        id: telegramEnabledLabel
                                        text: root.local("مفعّلة", "Enabled")
                                        Accessible.name: text
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(12)
                                    }
                                    Item { Layout.fillWidth: true }
                                    QQC2.Switch {
                                        id: tgSwitch
                                        implicitWidth: root.fs(48)
                                        Accessible.labelledBy: telegramEnabledLabel
                                    }
                                }
                                SectionNote {
                                    id: telegramTokenLabel
                                    visible: root.cfgTab === "telegram"
                                    Layout.fillWidth: true
                                    text: root.local("توكن بوت تليجرام", "Telegram bot token")
                                    Accessible.name: text
                                }
                                QQC2.TextField {
                                    id: tokenField
                                    visible: root.cfgTab === "telegram"
                                    Layout.fillWidth: true
                                    echoMode: TextInput.Password
                                    Accessible.name: root.local("توكن بوت تليجرام",
                                                                "Telegram bot token")
                                    Accessible.labelledBy: telegramTokenLabel
                                    placeholderText: root.cfgHasToken
                                        ? root.local(
                                            "التوكن محفوظ — اتركه فارغاً لإبقائه",
                                            "Token saved — leave blank to keep it")
                                        : root.local("123456:AA…  من @BotFather",
                                                     "123456:AA…  from @BotFather")
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(11)
                                }
                                QQC2.TextField {
                                    id: allowField
                                    visible: root.cfgTab === "telegram"
                                    Layout.fillWidth: true
                                    placeholderText: root.local(
                                        "معرّفك الرقمي — مثال: 123456789",
                                        "Your numeric ID — e.g. 123456789")
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(11)
                                }
                                SectionNote {
                                    visible: root.cfgTab === "telegram"
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "المعرّف الرقمي لا اسم المستخدم: الأسماء تُغيَّر ويُعاد تخصيصها، والرقم ثابت. اتركه فارغاً فيعود الوضع إلى الاقتران حتى لا تُقفل خارج بوتك.",
                                        "Use the numeric ID, not the username: names change and can be reassigned. Leave it blank to return to pairing mode.")
                                }
                                Rectangle {
                                    visible: root.cfgTab === "whatsapp"
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: root.fs(1)
                                    color: root.hairline
                                }
                                RowLayout {
                                    visible: root.cfgTab === "whatsapp"
                                    Layout.fillWidth: true
                                    spacing: design.space2
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Text {
                                            text: "WhatsApp"
                                            color: root.textHi
                                            font.family: root.uiFont
                                            font.pixelSize: root.typePx(13)
                                            font.weight: Font.DemiBold
                                        }
                                        SectionNote {
                                            Layout.fillWidth: true
                                            text: root.local(
                                                "اربط WhatsApp Web عبر OpenClaw؛ يستخدم نفس الوكيل والذاكرة والصلاحيات.",
                                                "Link WhatsApp Web through OpenClaw; it shares this agent, memory and permissions.")
                                        }
                                        SectionNote {
                                            Layout.fillWidth: true
                                            text: root.cfgChannelsBusy
                                                ? root.local("جارٍ فحص الاتصال…", "Checking connection…")
                                                : root.cfgChannels.whatsapp.connected
                                                    ? root.local("متصل فعلياً", "Connected")
                                                    : root.cfgChannels.whatsapp.configured
                                                        ? root.local("مهيّأ لكن غير متصل", "Configured but offline")
                                                        : root.local("غير مربوط — سيفتح الربط رمز QR", "Not linked — pairing opens a QR code")
                                        }
                                    }
                                    MoButton {
                                        label: root.cfgChannels.whatsapp.connected
                                            ? root.local("إعادة الربط", "Relink")
                                            : root.local("ربط WhatsApp", "Link WhatsApp")
                                        iconName: "network-connect"
                                        onClicked: root.launch(
                                            "moos://agent/whatsapp-login", "WhatsApp")
                                    }
                                }
                                SectionNote {
                                    visible: (root.cfgTab === "telegram" || root.cfgTab === "whatsapp")
                                             && root.cfgChannelsError !== ""
                                    Layout.fillWidth: true
                                    text: root.cfgChannelsError
                                }
                            }

                            // ══ VOICE ══════════════════════════════════════
                            ColumnLayout {
                                visible: root.cfgTab === "voice"
                                Layout.fillWidth: true
                                spacing: design.space2

                                SectionNote {
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "تكتب فيرد نصاً، وترسل رسالة صوتية فيرد صوتاً.",
                                        "Type for a text reply; send voice for a voice reply.")
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        id: voiceRepliesLabel
                                        text: root.local("الرد بصوت", "Voice replies")
                                        Accessible.name: text
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(12)
                                    }
                                    Item { Layout.fillWidth: true }
                                    QQC2.Switch {
                                        id: ttsSwitch
                                        implicitWidth: root.fs(48)
                                        Accessible.labelledBy: voiceRepliesLabel
                                    }
                                }
                                QQC2.ComboBox {
                                    id: ttsAutoBox
                                    Layout.fillWidth: true
                                    model: root.moaiRtl
                                        ? ["حين أرسل صوتاً فقط", "دائماً", "أبداً"]
                                        : ["Only after voice messages", "Always", "Never"]
                                    font.family: root.uiFont
                                }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "الفصحى ممتازة · الشامي مقبول · المغاربية غير مفهومة. صوت واحد: ar_JO-kareem.",
                                        "Arabic voice support uses ar_JO-kareem; Modern Standard Arabic works best.")
                                }
                            }

                            // ══ POWER ══════════════════════════════════════
                            ColumnLayout {
                                visible: root.cfgTab === "memory"
                                Layout.fillWidth: true
                                spacing: design.space2

                                SectionNote {
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "متى ينزل النموذج من كرت الشاشة ويترك الجهاز يتنفّس.",
                                        "Choose when the model releases GPU memory.")
                                }
                                QQC2.ComboBox {
                                    id: keepBox
                                    Layout.fillWidth: true
                                    model: root.moaiRtl
                                        ? ["٥ دقائق — أقل ضغط", "١٥ دقيقة — موصى به", "ساعة", "لا ينام أبداً"]
                                        : ["5 minutes — lighter", "15 minutes — recommended", "1 hour", "Never sleep"]
                                    font.family: root.uiFont
                                }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "«لا ينام أبداً» يحجز ٤ جيجا باستمرار. مع متصفح مكبّر قد يستنزف الذاكرة ويُسقط سطح المكتب.",
                                        "“Never sleep” keeps about 4 GB reserved and can exhaust memory beside a heavy browser.")
                                }

                            }

                            // ══ ACCESS ═════════════════════════════════════
                            // Four tiers, mapped onto OpenClaw's OWN enforcement. The
                            // decisive knob is sandbox.mode (all=boxed, off=host):
                            //   read → معطّل: sandbox=all, exec denied — no reach to the machine
                            //   project → sandbox=all, workspace rw; never reaches the host
                            //   system → sandbox=off (HOST) + approvals forwarded to the
                            //          origin chat, so a Telegram request is approved from
                            //          Telegram before the command runs on the real computer
                            //   full → كامل: sandbox=off (HOST), elevatedDefault=full, nothing
                            //          withheld — runs on the machine immediately, no prompt
                            // Only the allowlisted owner can drive any of it. Each switch
                            // writes the key the engine already obeys — no invented layer.
                            ColumnLayout {
                                visible: root.cfgTab === "permissions" || root.cfgTab === "projects"
                                Layout.fillWidth: true
                                spacing: design.space2

                                SectionNote {
                                    visible: root.cfgTab === "permissions"
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "كم يتحكّم الوكيل بجهازك فعلياً من تليجرام (كاميرا، برامج، ترمنال، تحديث، تطوير). ابدأ بـ«مع إذن».",
                                        "Choose how much Telegram can control on this device. Start with “Ask first”.")
                                }

                                // ── Quick toggle: host control ON / OFF ────────────
                                // One tap flips between full host control (sandbox off)
                                // and fully sandboxed (read). It writes the tier through
                                // moai-agent-api, which restarts OpenClaw so Telegram picks
                                // it up at once. The three tiers below stay for the middle
                                // "with approval" choice.
                                Rectangle {
                                    id: hostToggle
                                    visible: root.cfgTab === "permissions"
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: root.fs(60)
                                    radius: design.radiusControl
                                    readonly property bool hostOn:
                                        root.cfgTier === "system" || root.cfgTier === "full"
                                    color: hostOn ? Qt.rgba(root.okColor.r, root.okColor.g, root.okColor.b, 0.12)
                                                  : Qt.rgba(root.textMute.r, root.textMute.g, root.textMute.b, 0.07)
                                    border.width: 1
                                    border.color: hostOn ? root.okColor : root.hairline
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 14
                                        anchors.rightMargin: 14
                                        spacing: design.space3
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 1
                                            Text {
                                                id: botDeviceControlLabel
                                                text: root.local("تحكّم البوت بجهازك",
                                                                 "Bot device control")
                                                Accessible.name: text
                                                color: root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(13)
                                                font.weight: Font.DemiBold
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: hostToggle.hostOn
                                                    ? root.local(
                                                        "مُفعّل — يصل للكاميرا والترمنال وتحديث النظام من تليجرام",
                                                        "Enabled — Telegram can reach the camera, terminal and system actions")
                                                    : root.local(
                                                        "معزول — يردّ فقط، لا يتحكّم بشيء",
                                                        "Sandboxed — replies only; no device control")
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(10)
                                                wrapMode: Text.Wrap
                                            }
                                        }
                                        QQC2.Switch {
                                            checked: hostToggle.hostOn
                                            enabled: !root.cfgSaving
                                            implicitWidth: root.fs(48)
                                            Accessible.labelledBy: botDeviceControlLabel
                                            onToggled: {
                                                root.cfgTier = checked ? "system" : "read"
                                                root.cfgSave({
                                                    mode: root.cfgMode, provider: root.cfgProvider,
                                                    base: baseField.text, model: modelField.text, key: keyField.text,
                                                    tgOn: tgSwitch.checked, token: tokenField.text, allow: allowField.text,
                                                    ttsOn: ttsSwitch.checked, ttsAuto: ttsAutoBox.currentIndex,
                                                    keep: keepBox.currentIndex, web: webSwitch.checked,
                                                    tier: root.cfgTier, project: projectField.text
                                                }, function () { keyField.text = ""; tokenField.text = "" })
                                            }
                                        }
                                    }
                                }

                                Repeater {
                                    visible: root.cfgTab === "permissions"
                                    model: [
                                        { id: "read", ar: "معطّل — بلا تحكّم",
                                          en: "Disabled — no control",
                                          dAr: "يردّ ويحلّل داخل عزل فقط. لا كاميرا ولا برامج ولا ترمنال",
                                          dEn: "Replies inside a sandbox; no camera, apps or terminal" },
                                        { id: "project", ar: "تعديل المشروع",
                                          en: "Edit project",
                                          dAr: "يقرأ ويعدّل ويختبر داخل مجلد المشروع المعزول، بلا وصول للنظام",
                                          dEn: "Reads, edits and tests inside the sandboxed project; no system access" },
                                        { id: "system",  ar: "تحكّم بالنظام — بموافقة",
                                          en: "System control — ask first",
                                          dAr: "يتحكّم بالجهاز الحقيقي، لكن يعرض كل أمر وتوافق عليه في تليجرام قبل تنفيذه",
                                          dEn: "Can control the device, but every command requires Telegram approval" },
                                        { id: "full", ar: "كامل — تحكّم بلا سؤال",
                                          en: "Full — no confirmation",
                                          dAr: "ينفّذ أي شيء على جهازك فوراً بلا موافقة. الأقوى والأخطر — لك وحدك",
                                          dEn: "Runs immediately without approval. Most powerful and highest risk" }
                                    ]
                                    delegate: Rectangle {
                                        required property var modelData
                                        readonly property bool on_: root.cfgTier === modelData.id
                                        readonly property bool risky: modelData.id === "full"
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: root.fs(54)
                                        radius: design.radiusControl
                                        color: on_ ? (risky
                                                ? Qt.rgba(root.badColor.r, root.badColor.g, root.badColor.b, 0.13)
                                                : Qt.rgba(root.novaBlue.r, root.novaBlue.g, root.novaBlue.b, 0.13))
                                            : "transparent"
                                        border.width: 1
                                        border.color: on_ ? (risky ? root.badColor : root.novaBlue) : root.hairline
                                        ColumnLayout {
                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.verticalCenter: parent.verticalCenter
                                            anchors.margins: 12
                                            spacing: 1
                                            Text {
                                                text: root.local(modelData.ar, modelData.en)
                                                color: on_ ? (risky ? root.badColor : root.novaBlue) : root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(12)
                                                font.weight: Font.DemiBold
                                            }
                                            Text {
                                                text: root.local(modelData.dAr, modelData.dEn)
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(10)
                                                wrapMode: Text.Wrap
                                            }
                                        }
                                        ActionArea {
                                            anchors.fill: parent
                                            actionName: root.local(modelData.ar, modelData.en)
                                            checkable: true
                                            checked: parent.on_
                                            focusRadius: root.fs(11)
                                            onTriggered: root.cfgTier = modelData.id
                                        }
                                    }
                                }

                                SectionTitle {
                                    visible: root.cfgTab === "projects"
                                    text: root.local("مجلد المشروع", "Project folder")
                                    Layout.topMargin: 6
                                }
                                QQC2.TextField {
                                    id: projectField
                                    visible: root.cfgTab === "projects"
                                    Layout.fillWidth: true
                                    text: root.cfgProject
                                    placeholderText: root.local(
                                        "/var/home/moos/… (فارغ = بلا نطاق)",
                                        "/var/home/moos/… (blank = unrestricted)")
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(11)
                                }
                                SectionNote {
                                    visible: root.cfgTab === "projects"
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "يحصر عمل الوكيل في مجلد واحد. مسار مطلق داخل مجلد المنزل فقط — أي شيء آخر يُرفض.",
                                        "Restricts the agent to one absolute path inside your home folder.")
                                }

                                SectionTitle {
                                    visible: root.cfgTab === "permissions"
                                    text: root.local("الإنترنت", "Internet")
                                    Layout.topMargin: 6
                                }
                                RowLayout {
                                    visible: root.cfgTab === "permissions"
                                    Layout.fillWidth: true
                                    Text {
                                        id: webAccessLabel
                                        text: root.local("بحث وقراءة صفحات",
                                                         "Search and read pages")
                                        Accessible.name: text
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.typePx(12)
                                    }
                                    Item { Layout.fillWidth: true }
                                    QQC2.Switch {
                                        id: webSwitch
                                        implicitWidth: root.fs(48)
                                        Accessible.labelledBy: webAccessLabel
                                    }
                                }
                                SectionNote {
                                    visible: root.cfgTab === "permissions"
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "نموذج 4B ضعيف أمام حقن التعليمات — صفحة خبيثة تقدر تعطيه أوامر باعتبارها محتوى. فعّله مع العقل السحابي فقط.",
                                        "A 4B model is vulnerable to prompt injection from malicious pages. Enable this with the cloud brain only.")
                                }
                            }

                            // ══ OPENCLAW ══════════════════════════════════
                            ColumnLayout {
                                visible: root.cfgTab === "openclaw"
                                Layout.fillWidth: true
                                spacing: design.space2

                                SectionTitle { text: "OpenClaw" }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "المحرّك الموحّد لسطح المكتب وتليجرام وواتساب؛ نفس الجلسات والذاكرة والأدوات.",
                                        "The shared desktop, Telegram and WhatsApp runtime: one session store, memory and tool policy.")
                                }
                                StatusPill {
                                    good: root.agentOpenClawConfigured
                                    goodText: root.local("مثبّت ومهيّأ", "Installed and configured")
                                    badText: root.local("يحتاج إعداداً", "Setup required")
                                }
                                MoButton {
                                    Layout.fillWidth: true
                                    label: root.agentMachineConfigured
                                        ? root.local("افتح مساحة الوكيل", "Open Agent workspace")
                                        : root.agentSetupLabel
                                    primary: true
                                    onClicked: {
                                        if (!root.agentMachineConfigured) {
                                            Qt.openUrlExternally(root.agentSetupAction)
                                            return
                                        }
                                        root.settingsOpen = false
                                        root.panel = "agent"
                                        root.agentWorkspaceTab = "conversations"
                                        root.agentLoadStatus()
                                    }
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: root.fs(1)
                                    color: root.hairline
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    SectionTitle { text: root.local("صحة النظام", "System health") }
                                    Item { Layout.fillWidth: true }
                                    MoButton {
                                        label: root.diagLoading
                                            ? root.local("يفحص…", "Checking…")
                                            : root.local("افحص الآن", "Check now")
                                        enabled_: !root.diagLoading
                                        iconName: "moos-report-symbolic"
                                        onClicked: root.diagnoseSystem()
                                    }
                                }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "أدوات MoOS الأصلية للقراءة والإصلاح؛ كل إصلاح فعل ثابت يطلب التأكيد.",
                                        "Native read-only MoOS diagnostics and fixed repair actions; every repair asks first.")
                                }
                                Text {
                                    visible: !root.diagLoading
                                             && root.diagResult.summary !== undefined
                                    Layout.fillWidth: true
                                    text: root.diagResult.summary || ""
                                    color: root.textHi
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(11)
                                    wrapMode: Text.Wrap
                                }
                                Repeater {
                                    model: (root.diagResult.fixes && root.diagResult.fixes.length)
                                           ? root.diagResult.fixes : root.defaultRepairs
                                    delegate: Rectangle {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: root.fs(48)
                                        radius: design.radiusControl
                                        color: "transparent"
                                        border.width: 1
                                        border.color: root.hairline
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: root.fs(9)
                                            Text {
                                                Layout.fillWidth: true
                                                text: modelData.title || modelData.label || modelData.id
                                                color: root.textHi
                                                elide: Text.ElideRight
                                                font.family: root.uiFont
                                                font.pixelSize: root.typePx(11)
                                            }
                                            MoButton {
                                                label: modelData.read
                                                    ? root.local("افحص", "Check")
                                                    : root.local("أصلح", "Fix")
                                                onClicked: Qt.openUrlExternally("moos://do/" + modelData.id)
                                            }
                                        }
                                    }
                                }
                            }

                            // ══ TERMINAL ══════════════════════════════════
                            ColumnLayout {
                                visible: root.cfgTab === "terminal"
                                Layout.fillWidth: true
                                spacing: design.space2

                                SectionTitle { text: root.local("الطرفية المدمجة", "Integrated terminal") }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "PTY حقيقي بتبويبات ومخرجات حية وإيقاف للعمليات. يبدأ داخل المشروع المختار ولا يقبل أمراً مركّباً من الواجهة.",
                                        "A real tabbed PTY with live output and process stop. It starts in the selected project and the UI cannot supply an executable.")
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: root.local(
                                        root.agentTerminals.length + " جلسة طرفية حالية",
                                        root.agentTerminals.length + " current terminal session(s)")
                                    color: root.textHi
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(12)
                                }
                                MoButton {
                                    Layout.fillWidth: true
                                    label: root.local("افتح الطرفية", "Open terminal")
                                    primary: true
                                    onClicked: {
                                        root.settingsOpen = false
                                        root.panel = "agent"
                                        root.agentWorkspaceTab = "terminal"
                                        root.agentLoadTerminals()
                                    }
                                }
                            }

                            // ══ APPEARANCE ════════════════════════════════
                            ColumnLayout {
                                visible: root.cfgTab === "appearance"
                                Layout.fillWidth: true
                                spacing: design.space2

                                SectionTitle { text: root.local("مظهر Mo AI", "Mo AI appearance") }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "Mo AI يتبع لوحة MoOS النشطة، اتجاه اللغة، حجم الخط وتقليل الحركة تلقائياً. غيّرها من منتقي MoOS الموحد.",
                                        "Mo AI follows the active MoOS palette, language direction, font scale and reduced-motion setting. Change them in the shared MoOS picker.")
                                }
                                MoButton {
                                    Layout.fillWidth: true
                                    label: root.local("افتح المظهر والثيمات", "Open appearance and themes")
                                    // moos-ui-symbolic is the family's themes glyph; a
                                    // "moos-themes-symbolic" never existed and drew blank.
                                    iconName: "moos-ui-symbolic"
                                    primary: true
                                    onClicked: root.launch("moos://settings/themes", "MoOS themes")
                                }
                            }

                            // ══ MODELS ═════════════════════════════════════
                            ColumnLayout {
                                visible: root.cfgTab === "models"
                                Layout.fillWidth: true
                                spacing: design.space2

                                RowLayout {
                                    Layout.fillWidth: true
                                    SectionTitle {
                                        text: root.local("النماذج المحلية", "Local models")
                                    }
                                    Item { Layout.fillWidth: true }
                                    MoButton {
                                        label: root.local("تحديث", "Refresh")
                                        onClicked: root.loadModels()
                                    }
                                }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "تُحمَّل من الجهاز — بلا إنترنت وبلا اشتراك. التنزيل بضغطة واحدة.",
                                        "Runs on this device without internet or a subscription. Download in one tap.")
                                }

                                Repeater {
                                    model: root.localModels
                                    delegate: Rectangle {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: root.fs(52)
                                        radius: design.radiusControl
                                        color: "transparent"
                                        border.width: 1
                                        border.color: root.hairline
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 10
                                            spacing: design.space2
                                            ColumnLayout {
                                                spacing: 1
                                                Text {
                                                    text: modelData.label || modelData.id
                                                    color: root.textHi
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.typePx(12)
                                                    font.weight: Font.DemiBold
                                                }
                                                Text {
                                                    text: modelData.pulled
                                                        ? (root.local("محمّل", "Downloaded")
                                                           + (modelData.size ? " · " + modelData.size : ""))
                                                        : root.local(
                                                            "غير محمّل — اضغط للتنزيل",
                                                            "Not downloaded — tap to get")
                                                    color: root.textMute
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.typePx(10)
                                                }
                                            }
                                            Item { Layout.fillWidth: true }
                                            MoButton {
                                                label: modelData.pulled
                                                    ? root.local("استخدم", "Use")
                                                    : root.local("نزّل", "Get")
                                                onClicked: root.pickOrPull(modelData)
                                            }
                                            MoButton {
                                                visible: !!modelData.pulled
                                                label: root.local("حذف", "Delete")
                                                danger: true
                                                onClicked: root.deleteModel(modelData.id)
                                            }
                                        }
                                    }
                                }

                                Text {
                                    visible: root.pullModel !== ""
                                    Layout.fillWidth: true
                                    text: root.local(
                                        "جارٍ تنزيل " + root.pullModel + " — " + root.pullPercent + "٪",
                                        "Downloading " + root.pullModel + " — " + root.pullPercent + "%")
                                    color: root.novaBlue
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(11)
                                }
                                Text {
                                    visible: root.pullError !== ""
                                    Layout.fillWidth: true
                                    text: root.pullError
                                    color: root.badColor
                                    font.family: root.uiFont
                                    font.pixelSize: root.typePx(11)
                                    wrapMode: Text.Wrap
                                }
                            }

                        }
                    }

                    // ── save ──
                    Rectangle {
                        visible: ["privacy", "providers", "telegram", "voice",
                                  "memory", "permissions", "projects"].indexOf(root.cfgTab) !== -1
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.fs(44)
                        radius: design.radiusControl
                        opacity: root.cfgSaving ? 0.6 : 1
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: root.novaBlue }
                            GradientStop { position: 1.0; color: root.novaViolet }
                        }
                        Text {
                            anchors.centerIn: parent
                            text: root.cfgSaving ? root.local("جارٍ الحفظ…", "Saving…")
                                                 : root.local("حفظ", "Save")
                            color: root.accentText
                            font.family: root.uiFont
                            font.pixelSize: root.typePx(14)
                            font.weight: Font.DemiBold
                        }
                        ActionArea {
                            anchors.fill: parent
                            enabled: !root.cfgSaving
                            actionName: root.moaiRtl ? "حفظ الإعدادات" : "Save settings"
                            focusRadius: root.fs(12)
                            onTriggered: root.cfgSave({
                                mode: root.cfgMode,
                                provider: root.cfgProvider,
                                base: baseField.text,
                                model: modelField.text,
                                key: keyField.text,
                                tgOn: tgSwitch.checked,
                                token: tokenField.text,
                                allow: allowField.text,
                                ttsOn: ttsSwitch.checked,
                                ttsAuto: ttsAutoBox.currentIndex,
                                keep: keepBox.currentIndex,
                                web: webSwitch.checked,
                                tier: root.cfgTier,
                                project: projectField.text
                            }, function () {
                                keyField.text = ""
                                tokenField.text = ""
                            })
                        }
                    }
                }

                // يملأ الحقول عند كل فتح — لا عند الإقلاع
                Connections {
                    target: root
                    function onSettingsOpenChanged() {
                        if (!root.settingsOpen) return
                        root.cfgLoad(function (c) {
                            provBox.currentIndex = Math.max(0, root.cfgProviders.findIndex(
                                function (p) { return p.id === c.cloud.provider }))
                            baseField.text  = c.cloud.base
                            modelField.text = c.cloud.model
                            tgSwitch.checked = c.telegram.enabled
                            allowField.text  = (c.telegram.allow || []).join(", ")
                            ttsSwitch.checked = c.voice.tts_enabled
                            ttsAutoBox.currentIndex = ["inbound", "always", "off"].indexOf(c.voice.tts_auto)
                            keepBox.currentIndex = ["5m", "15m", "60m", "-1"].indexOf(c.power.keep_alive)
                            webSwitch.checked = c.permissions.web
                        })
                    }
                }
            }
        }
    }

    // ── Settings plumbing (moai-agent-api) ──────────────────────────────────
    // One backend for BOTH surfaces: this sheet and the Telegram bot read and
    // write the same ~/.openclaw/openclaw.json through moai-agent-api. There is
    // no second copy of "which brain" or "which key" to drift out of sync.
    property string cfgTab: "privacy"
    property string cfgMode: "local"
    property string cfgProvider: "synterolink"
    property var    cfgProviders: []
    property var    cfgProviderNames: []
    property bool   cfgHasKey: false
    property bool   cfgHasToken: false
    property var    cfgChannels: ({
        telegram: { configured: false, running: false, connected: false,
                    account: "", mode: "", error: "" },
        whatsapp: { configured: false, running: false, connected: false,
                    account: "", mode: "", error: "" }
    })
    property bool   cfgChannelsBusy: false
    property string cfgChannelsError: ""
    property bool   cfgSaving: false
    property string cfgError: ""
    property string cfgTier: "ask"
    property string cfgProject: ""
    onCfgTabChanged: {
        if (cfgTab === "openclaw") root.agentLoadStatus()
        else if (cfgTab === "models") root.loadModels()
        else if (cfgTab === "terminal") root.agentLoadTerminals()
        else if (cfgTab === "telegram" || cfgTab === "whatsapp") root.cfgLoadChannels()
    }

    function cfgLoadChannels() {
        root.cfgChannelsBusy = true
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/channels")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            root.cfgChannelsBusy = false
            if (xhr.status !== 200) {
                root.cfgChannelsError = root.local(
                    "تعذّر فحص القنوات", "Could not probe channels")
                return
            }
            try {
                const result = JSON.parse(xhr.responseText)
                root.cfgChannels = result.channels
                root.cfgChannelsError = result.error || ""
            } catch (e) {
                root.cfgChannelsError = root.local(
                    "رد حالة القنوات غير مفهوم", "Bad channel status response")
            }
        }
        xhr.send()
    }

    function cfgLoad(done) {
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/config")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status !== 200) {
                root.cfgError = root.local(
                    "لوحة التحكم لا تستجيب — شغّل moai-agent-api.service",
                    "Control service is unavailable — start moai-agent-api.service")
                return
            }
            try {
                const c = JSON.parse(xhr.responseText)
                root.cfgError = ""
                root.cfgMode = c.brain.mode
                root.cfgProvider = c.cloud.provider
                root.cfgProviders = c.providers
                root.cfgProviderNames = c.providers.map(function (p) { return p.name })
                root.cfgHasKey = c.cloud.has_key
                root.cfgHasToken = c.telegram.has_token
                root.cfgTier = (c.permissions && c.permissions.tier) || "ask"
                root.cfgProject = (c.permissions && c.permissions.project) || ""
                if (done) done(c)
            } catch (e) {
                root.cfgError = root.local("رد غير مفهوم من لوحة التحكم",
                                           "Unrecognised control response")
            }
        }
        xhr.send()
    }

    function cfgSave(v, done) {
        root.cfgSaving = true
        root.cfgError = ""
        const AUTO = ["inbound", "always", "off"]
        const KEEP = ["5m", "15m", "60m", "-1"]
        const body = {
            mode: v.mode,
            cloud: { provider: v.provider, base: v.base, model: v.model, key: v.key },
            telegram: {
                enabled: v.tgOn,
                token: v.token,
                allow: v.allow.split(",").map(function (x) { return x.trim() })
                                        .filter(function (x) { return x.length > 0 })
            },
            voice: { tts_enabled: v.ttsOn, tts_auto: AUTO[v.ttsAuto] || "inbound" },
            power: { keep_alive: KEEP[v.keep] || "15m" },
            permissions: { web: v.web, tier: v.tier, project: v.project }
        }
        const xhr = new XMLHttpRequest()
        xhr.open("POST", root.agentApi + "/api/config")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            root.cfgSaving = false
            if (xhr.status === 200) {
                let r = {}
                try { r = JSON.parse(xhr.responseText) } catch (e) { }
                if (r.error) { root.cfgError = r.error; return }
                if (done) done()
                root.cfgLoad()
            } else {
                root.cfgError = root.local("تعذّر الحفظ (HTTP " + xhr.status + ")",
                                           "Could not save (HTTP " + xhr.status + ")")
            }
        }
        xhr.send(JSON.stringify(body))
    }

    // ── Agent plumbing ──────────────────────────────────────────────────────
    // moai-agent-api is the ONLY bridge: pure QML has no Process API and cannot
    // read ~/.openclaw itself. Same pattern as controlApi above — and the same
    // per-user port, because this one holds the most personal things Mo AI has
    // (each human's sessions and their Telegram bot token) and must never be
    // answered by another account's service.
    readonly property string agentApi: "http://127.0.0.1:" + root.agentPort
    property var  agentSessions: []
    property var  agentThread: []
    property string agentCurrent: ""
    property string agentCurrentKey: "console"
    property string agentCurrentLabel: ""
    property string agentSearch: ""
    property bool agentShowArchived: false
    property string agentWorkspaceTab: "conversations"
    onAgentWorkspaceTabChanged: {
        root.agentLoadCurrentWorkspace()
    }
    property var agentProjects: []
    property string agentProjectCurrent: ""
    property string agentProjectPath: ""
    property string agentProjectParent: ""
    property var agentProjectEntries: []
    property string agentProjectPreview: ""
    property var agentTasks: []
    property var agentApprovals: []
    property string agentTaskProject: ""
    property var agentTerminals: []
    property string agentTerminalCurrent: ""
    property string agentTerminalOutput: ""
    property int agentTerminalOffset: 0
    property bool agentBusy: false
    property string agentError: ""
    property string agentStatusError: ""
    property bool agentStatusLoaded: false
    property bool agentInstalled: false
    property bool agentOpenClawConfigured: false
    property bool agentBrainConfigured: false
    property bool agentSpeechConfigured: false
    readonly property bool agentMachineConfigured:
        agentInstalled && agentOpenClawConfigured
        && agentBrainConfigured && agentSpeechConfigured
    readonly property string agentAnyError:
        agentStatusError !== "" ? agentStatusError : agentError
    readonly property bool agentReady:
        agentStatusLoaded && agentMachineConfigured && agentAnyError === ""
    readonly property string agentSetupAction:
        !agentInstalled || !agentOpenClawConfigured
            ? "moos://do/install-openclaw"
            : "moos://do/setup-brain"
    readonly property string agentSetupLabel:
        !agentInstalled || !agentOpenClawConfigured
            ? root.local("ثبّت وأكمل", "Install")
            : root.local("جهّز العقل", "Set up")
    readonly property string agentSetupNote:
        !agentInstalled
            ? root.local(
                "إعداد واحد مؤكّد يثبّت OpenClaw والعقل والصوت محلياً، ثم يبقى التشغيل عند الطلب.",
                "One confirmed setup installs OpenClaw, the local brain and speech; it then runs on demand.")
            : !agentOpenClawConfigured
                ? root.local(
                    "إعداد OpenClaw غير مكتمل؛ أعد تشغيل المثبّت الآمن ليصلحه دون مسح اختياراتك.",
                    "OpenClaw setup is incomplete; rerun the safe installer without losing your choices.")
                : root.local(
                    "العقل أو الصوت المحلي غير مجهّز. الإجراء التالي ينشئهما ويتحقق منهما فعلياً.",
                    "The local brain or speech is not configured. The next action creates and verifies both.")

    function agentLoadCurrentWorkspace() {
        if (root.agentWorkspaceTab === "projects") root.agentLoadProjects()
        else if (root.agentWorkspaceTab === "tasks") root.agentLoadTasks()
        else if (root.agentWorkspaceTab === "terminal") root.agentLoadTerminals()
        else root.agentLoadSessions()
    }

    function agentLoadStatus() {
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/status")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status !== 200) {
                root.agentStatusLoaded = false
                root.agentStatusError = root.local(
                    "لوحة الوكيل لا تستجيب — moai-agent-api.service",
                    "Agent service is unavailable — moai-agent-api.service")
                return
            }
            try {
                const s = JSON.parse(xhr.responseText)
                root.agentInstalled = !!s.openclaw_installed
                root.agentOpenClawConfigured = !!s.openclaw_configured
                root.agentBrainConfigured = !!s.brain_configured
                root.agentSpeechConfigured = !!s.speech_configured
                root.agentStatusLoaded = true
                root.agentStatusError = ""
                if (root.agentMachineConfigured)
                    root.agentLoadCurrentWorkspace()
            } catch (e) {
                root.agentStatusLoaded = false
                root.agentStatusError = root.local("رد حالة الوكيل غير مفهوم",
                                                   "Bad status response")
            }
        }
        xhr.send()
    }

    function agentLoadSessions() {
        const xhr = new XMLHttpRequest()
        let query = "?q=" + encodeURIComponent(root.agentSearch)
        if (root.agentShowArchived) query += "&archived=1"
        xhr.open("GET", root.agentApi + "/api/sessions" + query)
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try { root.agentSessions = JSON.parse(xhr.responseText); root.agentError = "" }
                catch (e) {
                    root.agentError = root.local("رد غير مفهوم", "Bad response")
                }
            } else {
                root.agentError = root.local(
                    "لوحة الوكيل لا تستجيب — moai-agent-api.service",
                    "Agent service is unavailable — moai-agent-api.service")
            }
        }
        xhr.send()
    }

    function agentOpen(id, key) {
        root.agentCurrent = id
        root.agentCurrentKey = String(key).split(":").pop()
        for (let i = 0; i < root.agentSessions.length; ++i) {
            if (root.agentSessions[i].id === id) {
                root.agentCurrentLabel = root.agentSessions[i].label
                break
            }
        }
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/session?id=" + encodeURIComponent(id))
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try { root.agentThread = JSON.parse(xhr.responseText) } catch (e) { root.agentThread = [] }
            }
        }
        xhr.send()
    }

    function agentOpenPrimary(id, key, label) {
        if (!/^[0-9a-fA-F-]{36}$/.test(String(id))
                || !/^[A-Za-z0-9_.:-]{1,180}$/.test(String(key))) {
            root.agentError = root.local("معرّف المحادثة غير صالح",
                                         "Invalid conversation identifier")
            return
        }
        root.stopGenerating()
        root.panel = "chat"
        root.agentCurrent = String(id)
        root.agentCurrentKey = String(key).split(":").pop()
        root.agentCurrentLabel = String(label || "")
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/session?id=" + encodeURIComponent(id))
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status !== 200) {
                root.agentError = root.local("تعذّر فتح المحادثة",
                                             "Could not open conversation")
                return
            }
            try {
                const messages = JSON.parse(xhr.responseText)
                chatModel.clear()
                root.history = []
                root.lastSubmissionDisplay = ""
                root.lastSubmissionContent = null
                root.retryPending = false
                const start = Math.max(0, messages.length - 200)
                for (let i = start; i < messages.length; ++i) {
                    const role = messages[i].role === "user" ? "user"
                               : messages[i].role === "tool"
                                   ? "tool-" + String(messages[i].status || "success")
                                   : "assistant"
                    const messageText = String(messages[i].text || "").trim()
                    if (messageText === "") continue
                    chatModel.append({ role: role, text: messageText })
                    if (role.indexOf("tool-") !== 0)
                        root.history.push({ role: role, content: messageText })
                }
                root.trimHistory()
                if (chatModel.count === 0)
                    chatModel.append({ role: "assistant", text: root.greetingText })
                root.chatOpenClawSessionKey = String(key)
                root.chatSessionId = "moai-desktop-" + String(id)
                root.chatSidebarOpen = false
                root.agentError = ""
                if (root.chatSessionStart)
                    sessionStartDelay.restart()
            } catch (e) {
                root.agentError = root.local("رد المحادثة غير مفهوم",
                                             "Bad conversation response")
            }
        }
        xhr.send()
    }

    function agentUpdateSession(id, fields) {
        if (!id) return
        const payload = { id: id }
        if (fields.title !== undefined) payload.title = fields.title
        if (fields.pinned !== undefined) payload.pinned = fields.pinned
        if (fields.archived !== undefined) payload.archived = fields.archived
        if (fields.project !== undefined) payload.project = fields.project
        const xhr = new XMLHttpRequest()
        xhr.open("POST", root.agentApi + "/api/session/update")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                root.agentError = ""
                if (payload.title !== undefined)
                    root.agentCurrentLabel = String(payload.title).trim()
                if (payload.archived === true && !root.agentShowArchived) {
                    root.agentCurrent = ""
                    root.agentCurrentLabel = ""
                    root.agentThread = []
                }
                root.agentLoadSessions()
            } else {
                try { root.agentError = JSON.parse(xhr.responseText).error }
                catch (e) { root.agentError = root.local("تعذّر حفظ المحادثة",
                                                         "Could not save conversation") }
            }
        }
        xhr.send(JSON.stringify(payload))
    }

    function agentLoadProjects() {
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/projects")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try { root.agentProjects = JSON.parse(xhr.responseText); root.agentError = "" }
                catch (e) { root.agentError = root.local("رد مشاريع غير مفهوم", "Bad projects response") }
            } else root.agentError = root.local("تعذّر تحميل المشاريع", "Could not load projects")
        }
        xhr.send()
    }

    function agentAddProject(path) {
        if (!String(path).trim()) return
        const xhr = new XMLHttpRequest()
        xhr.open("POST", root.agentApi + "/api/project/upsert")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                projectPathField.text = ""
                root.agentError = ""
                root.agentLoadProjects()
            } else {
                try { root.agentError = JSON.parse(xhr.responseText).error }
                catch (e) { root.agentError = root.local("تعذّرت إضافة المشروع", "Could not add project") }
            }
        }
        xhr.send(JSON.stringify({ path: String(path).trim() }))
    }

    function agentOpenProject(id) {
        root.agentProjectCurrent = id
        root.agentTaskProject = id
        root.agentProjectPreview = ""
        root.agentLoadProjectFiles("")
        root.agentLoadProjectGitStatus()
    }

    function agentLoadProjectFiles(path) {
        if (!root.agentProjectCurrent) return
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/project/files?project="
                 + encodeURIComponent(root.agentProjectCurrent)
                 + "&path=" + encodeURIComponent(path || ""))
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try {
                    const result = JSON.parse(xhr.responseText)
                    root.agentProjectEntries = result.entries || []
                    root.agentProjectPath = result.path || ""
                    root.agentProjectParent = result.parent || ""
                    root.agentError = ""
                } catch (e) { root.agentError = root.local("رد ملفات غير مفهوم", "Bad file response") }
            } else {
                try { root.agentError = JSON.parse(xhr.responseText).error }
                catch (e) { root.agentError = root.local("تعذّر عرض ملفات المشروع",
                                                         "Could not list project files") }
            }
        }
        xhr.send()
    }

    function agentLoadProjectFile(path) {
        if (!root.agentProjectCurrent) return
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/project/file?project="
                 + encodeURIComponent(root.agentProjectCurrent)
                 + "&path=" + encodeURIComponent(path))
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try {
                    const result = JSON.parse(xhr.responseText)
                    root.agentProjectPreview = result.content || ""
                    root.agentError = ""
                } catch (e) { root.agentError = root.local("رد ملف غير مفهوم", "Bad file response") }
            } else {
                try { root.agentError = JSON.parse(xhr.responseText).error }
                catch (e) { root.agentError = root.local("تعذّرت معاينة الملف",
                                                         "Could not preview file") }
            }
        }
        xhr.send()
    }

    function agentLoadProjectGitStatus() {
        if (!root.agentProjectCurrent) return
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/project/git-status?project="
                 + encodeURIComponent(root.agentProjectCurrent))
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try {
                    const result = JSON.parse(xhr.responseText)
                    root.agentProjectPreview = result.status
                        || root.local("شجرة العمل نظيفة.", "Working tree is clean.")
                    root.agentError = ""
                } catch (e) { root.agentError = root.local("رد Git غير مفهوم", "Bad Git response") }
            } else {
                try { root.agentError = JSON.parse(xhr.responseText).error }
                catch (e) { root.agentError = root.local("تعذّر قراءة حالة Git",
                                                         "Could not read Git status") }
            }
        }
        xhr.send()
    }

    function agentLoadProjectDiff(path) {
        if (!root.agentProjectCurrent) return
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/project/git-diff?project="
                 + encodeURIComponent(root.agentProjectCurrent)
                 + "&path=" + encodeURIComponent(path || ""))
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try {
                    const result = JSON.parse(xhr.responseText)
                    let output = ""
                    if (result.staged) output += root.local("التغييرات المجهزة:\n",
                                                           "Staged changes:\n") + result.staged
                    if (result.unstaged) output += (output ? "\n" : "")
                                                 + root.local("التغييرات غير المجهزة:\n",
                                                              "Unstaged changes:\n")
                                                 + result.unstaged
                    root.agentProjectPreview = output
                        || root.local("لا توجد فروقات.", "No changes.")
                    root.agentError = ""
                } catch (e) { root.agentError = root.local("رد فرق غير مفهوم", "Bad diff response") }
            } else {
                try { root.agentError = JSON.parse(xhr.responseText).error }
                catch (e) { root.agentError = root.local("تعذّر عرض فروقات Git",
                                                         "Could not show Git diff") }
            }
        }
        xhr.send()
    }

    function agentLoadTasks() {
        const xhr = new XMLHttpRequest()
        let query = root.agentTaskProject
            ? "?project=" + encodeURIComponent(root.agentTaskProject) : ""
        xhr.open("GET", root.agentApi + "/api/tasks" + query)
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try { root.agentTasks = JSON.parse(xhr.responseText); root.agentError = "" }
                catch (e) { root.agentError = root.local("رد مهام غير مفهوم", "Bad tasks response") }
            } else root.agentError = root.local("تعذّر تحميل المهام", "Could not load tasks")
        }
        xhr.send()
        root.agentLoadApprovals()
    }

    function agentLoadApprovals() {
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/approvals")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try { root.agentApprovals = JSON.parse(xhr.responseText) }
                catch (e) { root.agentApprovals = [] }
            } else root.agentApprovals = []
        }
        xhr.send()
    }

    function agentTaskApprovals(taskId) {
        return root.agentApprovals.filter(function (approval) {
            return approval.task === taskId
        })
    }

    function agentResolveApproval(id, decision) {
        const xhr = new XMLHttpRequest()
        xhr.open("POST", root.agentApi + "/api/approval/resolve")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                root.agentError = ""
                root.agentLoadTasks()
            } else {
                try { root.agentError = JSON.parse(xhr.responseText).error }
                catch (e) { root.agentError = root.local(
                    "تعذّر حسم الموافقة", "Could not resolve approval") }
                root.agentLoadApprovals()
            }
        }
        xhr.send(JSON.stringify({ id: id, decision: decision }))
    }

    function agentCreateTask(title) {
        title = String(title).trim()
        if (!title) return
        const xhr = new XMLHttpRequest()
        xhr.open("POST", root.agentApi + "/api/task/create")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                taskTitleField.text = ""
                root.agentError = ""
                root.agentLoadTasks()
            } else {
                try { root.agentError = JSON.parse(xhr.responseText).error }
                catch (e) { root.agentError = root.local("تعذّر إنشاء المهمة", "Could not create task") }
            }
        }
        xhr.send(JSON.stringify({ title: title, project: root.agentTaskProject, steps: [] }))
    }

    function agentUpdateTask(id, status) {
        const xhr = new XMLHttpRequest()
        xhr.open("POST", root.agentApi + "/api/task/update")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) root.agentLoadTasks()
            else {
                try { root.agentError = JSON.parse(xhr.responseText).error }
                catch (e) { root.agentError = root.local("تعذّر تحديث المهمة", "Could not update task") }
            }
        }
        xhr.send(JSON.stringify({ id: id, status: status }))
    }

    function agentTaskAction(id, action) {
        const xhr = new XMLHttpRequest()
        xhr.open("POST", root.agentApi + "/api/task/action")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                root.agentError = ""
                root.agentLoadTasks()
            } else {
                try { root.agentError = JSON.parse(xhr.responseText).error }
                catch (e) { root.agentError = root.local("تعذّر التحكم بالمهمة",
                                                         "Could not control task") }
            }
        }
        xhr.send(JSON.stringify({ id: id, action: action }))
    }

    function agentLoadTerminals() {
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/terminals")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try {
                    root.agentTerminals = JSON.parse(xhr.responseText)
                    if (!root.agentTerminalCurrent && root.agentTerminals.length)
                        root.agentSelectTerminal(root.agentTerminals[0].id)
                } catch (e) {
                    root.agentError = root.local("رد طرفية غير مفهوم", "Bad terminal response")
                }
            }
        }
        xhr.send()
    }

    function agentSelectTerminal(id) {
        root.agentTerminalCurrent = id
        root.agentTerminalOutput = ""
        root.agentTerminalOffset = 0
        root.agentPollTerminal()
    }

    function agentStartTerminal() {
        const xhr = new XMLHttpRequest()
        xhr.open("POST", root.agentApi + "/api/terminal/start")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try {
                    const created = JSON.parse(xhr.responseText)
                    root.agentLoadTerminals()
                    root.agentSelectTerminal(created.id)
                } catch (e) { root.agentError = root.local("تعذّر فتح الطرفية", "Could not open terminal") }
            } else {
                try { root.agentError = JSON.parse(xhr.responseText).error }
                catch (e) { root.agentError = root.local("تعذّر فتح الطرفية", "Could not open terminal") }
            }
        }
        xhr.send(JSON.stringify({ project: root.agentTaskProject }))
    }

    function agentPollTerminal() {
        if (!root.agentTerminalCurrent) return
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/terminal/output?id="
                 + encodeURIComponent(root.agentTerminalCurrent)
                 + "&offset=" + root.agentTerminalOffset)
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE || xhr.status !== 200) return
            try {
                const data = JSON.parse(xhr.responseText)
                if (data.truncated) root.agentTerminalOutput = ""
                root.agentTerminalOutput += data.output || ""
                root.agentTerminalOffset = data.offset || root.agentTerminalOffset
                if (!data.running) root.agentLoadTerminals()
            } catch (e) { }
        }
        xhr.send()
    }

    function agentWriteTerminal(input) {
        if (!root.agentTerminalCurrent || !input) return
        const xhr = new XMLHttpRequest()
        xhr.open("POST", root.agentApi + "/api/terminal/write")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState === XMLHttpRequest.DONE && xhr.status !== 200)
                root.agentError = root.local("تعذّرت كتابة الأمر", "Could not write command")
        }
        xhr.send(JSON.stringify({ id: root.agentTerminalCurrent, input: input }))
    }

    function agentStopTerminal() {
        if (!root.agentTerminalCurrent) return
        const xhr = new XMLHttpRequest()
        xhr.open("POST", root.agentApi + "/api/terminal/stop")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            root.agentPollTerminal()
            root.agentLoadTerminals()
        }
        xhr.send(JSON.stringify({ id: root.agentTerminalCurrent }))
    }

    function importAttachment(path) {
        if (!path) return
        const xhr = new XMLHttpRequest()
        xhr.open("POST", root.agentApi + "/api/attachment/import")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try {
                    const attachment = JSON.parse(xhr.responseText)
                    root.pendingAttachments = root.pendingAttachments.concat([attachment])
                    root.agentError = ""
                } catch (e) {
                    root.agentError = root.local("رد مرفق غير مفهوم", "Bad attachment response")
                }
            } else {
                try { root.agentError = JSON.parse(xhr.responseText).error }
                catch (e) { root.agentError = root.local("تعذّر إرفاق الملف", "Could not attach file") }
                toast.show(root.agentError)
            }
        }
        xhr.send(JSON.stringify({ path: path }))
    }

    function removePendingAttachment(id) {
        root.pendingAttachments = root.pendingAttachments.filter(function (item) {
            return item.id !== id
        })
    }

    function toggleVoiceRecording() {
        const stopping = root.voiceRecording
        const xhr = new XMLHttpRequest()
        xhr.open("POST", root.agentApi
                 + (stopping ? "/api/voice/stop" : "/api/voice/start"))
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try {
                    const result = JSON.parse(xhr.responseText)
                    root.voiceRecording = !!result.recording
                    if (result.text) input.text = result.text
                    if (result.text) input.forceActiveFocus()
                } catch (e) {
                    root.voiceRecording = false
                    toast.show(root.local("رد الصوت غير مفهوم", "Bad voice response"))
                }
            } else {
                root.voiceRecording = false
                try { toast.show(JSON.parse(xhr.responseText).error) }
                catch (e) { toast.show(root.local("تعذّر تشغيل الصوت", "Voice failed")) }
            }
        }
        xhr.send("{}")
    }

    function agentSend(text) {
        if (!text || root.agentBusy || !root.agentReady) return
        root.agentBusy = true
        root.agentError = ""
        // Echo locally so the message appears instantly; the reply lands on return.
        root.agentThread = root.agentThread.concat([{ role: "user", text: text }])
        const xhr = new XMLHttpRequest()
        xhr.open("POST", root.agentApi + "/api/send")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            root.agentBusy = false
            let reply = root.local("لا رد", "No reply")
            if (xhr.status === 200) {
                try { const r = JSON.parse(xhr.responseText); reply = r.reply || r.error || reply }
                catch (e) { reply = root.local("رد غير مفهوم", "Bad response") }
            } else {
                reply = root.local("تعذّر الاتصال بالوكيل",
                                   "Could not connect to the agent")
                root.agentError = reply
            }
            root.agentThread = root.agentThread.concat([{ role: "assistant", text: reply }])
            root.agentLoadSessions()
        }
        xhr.send(JSON.stringify({ key: root.agentCurrentKey, text: text }))
    }

    // ── Settings plumbing ───────────────────────────────────────────────────
    property bool settingsOpen: false
}
