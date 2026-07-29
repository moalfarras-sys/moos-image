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
import QtQuick.Effects
import org.kde.kirigami as Kirigami

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
    readonly property color onAccent:   Kirigami.Theme.highlightedTextColor

    // Same focus ring as Mo Store, Welcome and the Installer. One focus treatment across MoOS.
    component FocusRing: Rectangle {
        anchors.fill: parent
        anchors.margins: -3
        radius: (parent && parent.radius !== undefined ? parent.radius : 0) + 3
        color: "transparent"
        border.width: 2
        border.color: root.novaBlue
        visible: parent ? parent.activeFocus : false
        z: 99
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
    // fs() deliberately preserves today's proportions rather than snapping sizes onto a tidy
    // scale. Collapsing the 18 distinct sizes to a modular scale is a visual redesign that has
    // to be reviewed screen by screen; making them respond to the user is a correctness fix
    // that can be proven neutral. This is the second one. The first is still worth doing.
    readonly property real fontScale: Qt.application.font.pointSize > 0
                                      ? Qt.application.font.pointSize / 10 : 1
    function fs(px) { return Math.round(px * root.fontScale) }

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

    // ── The glass backdrop — the roadmap's last Nova Glass item ─────────────
    // The window used to be one flat colour; the flagship app now sits on a
    // living scene: a deepening gradient, two aurora bands drifting slower
    // than the eye tracks, the brand's breathing light, and the mark itself
    // as a watermark with its comet ring. Everything is palette-driven so all
    // six family themes (and Tidal light) keep their own identity, and every
    // sprite is a pre-baked PNG from artwork/generate_login_scene.py at the
    // canonical /usr/share/moos/brand/ — a missing sprite degrades to the
    // plain gradient, never to a broken window. Declared as a sibling of the
    // pageStack at z:-1, so it draws behind every page. Animators only, the
    // same budget as every MoOS always-on surface.
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

        Rectangle {
            id: ambientCyan
            width: parent.width * 1.6
            height: parent.height * 0.5
            y: parent.height * 0.02
            rotation: -14
            opacity: 0.05
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: root.novaCyan }
                GradientStop { position: 1.0; color: "transparent" }
            }
            XAnimator on x {
                from: -ambientCyan.width * 0.35
                to: root.width - ambientCyan.width * 0.65
                duration: 140000
                loops: Animation.Infinite
                easing.type: Easing.InOutSine
                running: root.visible && root.motionEnabled
            }
        }
        Rectangle {
            id: ambientViolet
            width: parent.width * 1.5
            height: parent.height * 0.45
            y: parent.height * 0.5
            rotation: 10
            opacity: 0.04
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: root.novaViolet }
                GradientStop { position: 1.0; color: "transparent" }
            }
            XAnimator on x {
                from: root.width - ambientViolet.width * 0.6
                to: -ambientViolet.width * 0.4
                duration: 170000
                loops: Animation.Infinite
                easing.type: Easing.InOutSine
                running: root.visible && root.motionEnabled
            }
        }

        Image {
            id: ambientGlowCyan
            source: "file:///usr/share/moos/brand/glow-cyan.png"
            width: Math.round(Math.min(parent.width, parent.height) * 0.9)
            height: width
            x: -width * 0.35
            y: parent.height - height * 0.55
            asynchronous: true
            opacity: 0.14
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                running: root.visible && root.motionEnabled
                NumberAnimation { to: 0.26; duration: 5200; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.14; duration: 5200; easing.type: Easing.InOutSine }
            }
        }
        Image {
            id: ambientGlowViolet
            source: "file:///usr/share/moos/brand/glow-violet.png"
            width: Math.round(Math.min(parent.width, parent.height) * 0.75)
            height: width
            x: parent.width - width * 0.55
            y: -height * 0.35
            asynchronous: true
            opacity: 0.18
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                running: root.visible && root.motionEnabled
                NumberAnimation { to: 0.08; duration: 5200; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.18; duration: 5200; easing.type: Easing.InOutSine }
            }
        }

        // The watermark: the mark at whisper opacity, its comet ring turning
        // once a minute — presence, not decoration competing with content.
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
            SequentialAnimation on scale {
                loops: Animation.Infinite
                running: root.visible && root.motionEnabled
                NumberAnimation { to: 1.02; duration: 6000; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: 6000; easing.type: Easing.InOutSine }
            }
        }
        Image {
            anchors.centerIn: ambientMark
            source: "file:///usr/share/moos/brand/ring.png"
            width: ambientMark.width * 1.35
            height: width
            asynchronous: true
            opacity: 0.10
            RotationAnimator on rotation {
                from: 0; to: 360
                duration: 60000
                loops: Animation.Infinite
                running: root.visible && root.motionEnabled
            }
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
        { ar: "حدّث نظامي",     en: "Update my system", icon: "moos-safe-update", hint: "آمن وموقّع | signed & safe", send: "حدّث نظام MoOS من فضلك" },
        { ar: "افحص جهازي",     en: "Check my device",  icon: "moos-cpu",         hint: "تعريفات وصحّة | drivers & health", send: "افحص جهازي وقل لي إذا في مشاكل تعريفات أو تحديثات" },
        { ar: "سرّع ونظّف",      en: "Speed up & clean", icon: "moos-optimize",    hint: "مساحة وذاكرة | space & memory", send: "نظّف النظام وسرّعه من فضلك" },
        { ar: "صلّح الصوت",      en: "Fix audio",        icon: "moos-audio",       hint: "صوت لا يعمل | no sound", send: "الصوت لا يعمل عندي، ساعدني" }
    ]

    // ── The rail ────────────────────────────────────────────────────────────
    readonly property var navItems: [
        { id: "chat",   icon: "moos-ai",           ar: "المحادثة", en: "Chat" },
        { id: "device", icon: "moos-gpu",          ar: "الجهاز",   en: "Device" },
        { id: "apps",   icon: "moos-install",      ar: "التطبيقات", en: "Apps" },
        { id: "compat", icon: "moos-gaming",       ar: "التوافق",  en: "Compat" },
        { id: "remote", icon: "moos-phone",        ar: "التحكّم",   en: "Remote" },
        { id: "dev",    icon: "utilities-terminal", ar: "المطوّر",  en: "Dev" },
        { id: "agent",  icon: "moos-identity",     ar: "الوكيل",   en: "Agent" }
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
                if (["chat", "device", "apps", "compat", "remote", "dev", "agent"].indexOf(p) !== -1)
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
                       : "لم أستطع توليد رد، حاول مجدداً. | I couldn't generate a reply — please try again.")
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
                root.pullError = res.error || "تعذّر بدء التنزيل | could not start the download"
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
                root.cfgError = res.error || "تعذّر الحذف | could not delete the model"
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
        { id: "diagnose-services", label: "الخدمات الفاشلة | Failed services", read: true },
        { id: "check-drivers",     label: "الكرت والتعريف | GPU & drivers",    read: true },
        { id: "inspect-boot",      label: "حالة الإقلاع | Boot status",         read: true },
        { id: "net-doctor",        label: "تشخيص الشبكة | Network doctor",       read: true },
        { id: "gpu-report",        label: "ذاكرة كرت الشاشة | GPU memory",       read: true },
        { id: "fix-audio",         label: "إصلاح الصوت | Fix audio",            read: false },
        { id: "optimize",          label: "تنظيف وتحرير مساحة | Clean & free space", read: false },
        { id: "rollback",          label: "الرجوع لنسخة سابقة | Roll back",      read: false },
        { id: "update",            label: "تحديث MoOS | Update MoOS",           read: false }
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
                    root.pullError = s.error || "فشل التنزيل | the download failed"
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
            running: root.visible && orb.mood === "idle" && !orbPulse.running && root.motionEnabled
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
            running: root.visible && orb.mood === "thinking" && root.motionEnabled
            target: orb; property: "ringAngle"
            from: 0; to: 360; duration: 2600
            loops: Animation.Infinite
            onStopped: orb.ringAngle = 0
        }
        SequentialAnimation {
            running: root.visible && orb.mood === "thinking" && root.motionEnabled
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
            onRunningChanged: if (!running) orb.coreScale = 1.0
        }
        onPulse: orbPulse.restart()
    }

    // A card.
    component Card: Rectangle {
        default property alias content: inner.data
        property alias pad: inner.anchors.margins
        radius: root.fs(14)
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

        // Every button in Mo AI is this component, so one edit makes all 33 of them reachable —
        // and this is the only MoOS app whose buttons carry a `label`, which means it is the only
        // one that can announce a real name to a screen reader instead of an anonymous "button".
        activeFocusOnTab: btn.enabled_
        Accessible.role: Accessible.Button
        Accessible.name: btn.label
        Keys.onReturnPressed: if (btn.enabled_) btn.clicked()
        Keys.onSpacePressed:  if (btn.enabled_) btn.clicked()
        FocusRing { }

        readonly property color base:
              !enabled_ ? root.surface2
            : danger ? root.badColor
            : primary ? root.novaBlue
            : root.surface2

        implicitHeight: root.fs(34)
        implicitWidth: row.implicitWidth + 26
        radius: root.fs(11)
        color: !enabled_ ? base
             : ma.pressed ? Qt.darker(base, 1.12)
             : ma.containsMouse ? Qt.lighter(base, 1.16)
             : base
        border.width: 1
        border.color: primary || danger ? "transparent"
                    : ma.containsMouse ? root.novaBlue : root.hairline
        opacity: enabled_ ? 1.0 : 0.45
        scale: !enabled_ ? 1.0 : (ma.pressed ? 0.97 : (ma.containsMouse ? 1.03 : 1.0))
        Behavior on color { ColorAnimation { duration: 120 } }
        Behavior on scale { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }

        // glass top sheen — a hairline of light for premium depth
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.topMargin: 1
            anchors.leftMargin: 6
            anchors.rightMargin: 6
            height: 1
            radius: height / 2
            color: Qt.rgba(1, 1, 1, btn.primary || btn.danger ? 0.20 : 0.07)
        }

        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: 7
            Kirigami.Icon {
                visible: btn.icon !== ""
                source: btn.icon
                color: btn.primary || btn.danger ? root.onAccent : root.textLo
                Layout.preferredWidth: root.fs(15)
                Layout.preferredHeight: root.fs(15)
            }
            Text {
                text: btn.label
                color: btn.primary || btn.danger ? root.onAccent : root.textHi
                font.family: root.uiFont
                font.pixelSize: root.fs(12)
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
            font.pixelSize: root.fs(11)
            font.weight: Font.DemiBold
        }
    }

    component SectionTitle: Text {
        color: root.textHi
        font.family: root.uiFont
        font.pixelSize: root.fs(17)
        font.weight: Font.DemiBold
    }

    component SectionNote: Text {
        color: root.textLo
        font.family: root.uiFont
        font.pixelSize: root.fs(12)
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
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true

        RowLayout {
            anchors.fill: parent
            spacing: 0

            // ── The rail ────────────────────────────────────────────────────
            Rectangle {
                Layout.preferredWidth: root.fs(76)
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
                        id: heroOrb
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: root.fs(42)
                        Layout.preferredHeight: root.fs(42)
                        Layout.bottomMargin: 4
                        mood: root.mood
                    }

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.bottomMargin: 8
                        // Bilingual by session direction, like the rest of the app —
                        // it was Arabic-only, breaking the convention on English sessions.
                        text: (Qt.application.layoutDirection === Qt.RightToLeft)
                              ? (root.serverUp ? "متصل" : root.brainStarting ? "يبدأ…" : "غير متصل")
                              : (root.serverUp ? "Online" : root.brainStarting ? "Starting…" : "Offline")
                        color: root.serverUp ? root.okColor
                             : root.brainStarting ? root.novaBlue : root.textMute
                        font.family: root.uiFont
                        font.pixelSize: root.fs(9)
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
                                Behavior on height { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                            }

                            Rectangle {
                                anchors.centerIn: parent
                                width: 54; height: 46
                                radius: root.fs(12)
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
                                        Layout.preferredWidth: root.fs(20)
                                        Layout.preferredHeight: root.fs(20)
                                        source: nav.modelData.icon
                                        color: nav.active ? root.novaCyan : root.textMute
                                    }
                                    Text {
                                        Layout.alignment: Qt.AlignHCenter
                                        text: Qt.application.layoutDirection === Qt.RightToLeft
                                            ? nav.modelData.ar : nav.modelData.en
                                        color: nav.active ? root.textHi : root.textMute
                                        font.family: root.uiFont
                                        font.pixelSize: root.fs(9)
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
                        Layout.preferredHeight: root.fs(46)
                        Rectangle {
                            anchors.centerIn: parent
                            width: 54; height: 40
                            radius: root.fs(12)
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
                            onClicked: { root.settingsOpen = true }
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
                                    case "device": return "جهازي  |  My device"
                                    case "apps":   return "التطبيقات  |  Apps"
                                    case "compat": return "التوافق  |  Compatibility"
                                    case "remote": return "Mo PC Remote"
                                    case "dev":    return "المطوّر  |  Developer"
                                    case "agent":  return "الوكيل  |  Agent"
                                    default:       return "Mo AI"
                                    }
                                }
                                color: root.textHi
                                font.family: root.uiFont
                                font.pixelSize: root.fs(16)
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
                                    case "agent":  return "OpenClaw · Telegram · الجلسات"
                                    default:       return "مساعد MoOS | MoOS assistant"
                                    }
                                }
                                color: root.textLo
                                font.family: root.uiFont
                                font.pixelSize: root.fs(11)
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

                        ListView {
                            id: listView
                            anchors.fill: parent
                            visible: chatModel.count > 1
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
                                    radius: root.fs(14)
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
                                        font.pixelSize: root.fs(14)
                                        onLinkActivated: function (link) { Qt.openUrlExternally(link) }

                                        SequentialAnimation on opacity {
                                            running: msg.role === "typing" && root.motionEnabled
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

                        // ══ Empty-state hero — premium welcome (aurora art + brand + suggestion cards) ══
                        // Shown before the first exchange (chatModel holds only the seeded
                        // greeting). A generated mesh-gradient aurora fills the void; the
                        // brand orb sits over a soft accent glow; four glass cards (crafted
                        // icon + prompt + hint) seed the conversation via sendPrompt. The
                        // ListView and its greeting bubble take over on the first reply.
                        Item {
                            anchors.fill: parent
                            visible: chatModel.count <= 1

                            Image {
                                anchors.fill: parent
                                source: root.isLight ? "hero-bg-light.png" : "hero-bg.png"
                                fillMode: Image.PreserveAspectCrop
                                opacity: root.isLight ? 0.75 : 0.92
                                asynchronous: true
                            }

                            // Same doodle weave as the conversation, over the aurora and
                            // below the brand content — so the pattern is already visible
                            // the moment the app opens, not only once a chat begins.
                            ChatDoodle {
                                anchors.fill: parent
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
                                    text: Qt.application.layoutDirection === Qt.RightToLeft ? "أهلاً، أنا Mo AI" : "Hi, I'm Mo AI"
                                    color: root.textHi
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(32)
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: Qt.application.layoutDirection === Qt.RightToLeft
                                        ? "مساعد MoOS — اختر بداية، أو اكتب طلبك."
                                        : "Your MoOS assistant — pick a starting point, or just type."
                                    color: root.textLo
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(14)
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
                                            radius: root.fs(16)
                                            color: Qt.rgba(root.surface1.r, root.surface1.g, root.surface1.b, cardMA.containsMouse ? 0.94 : 0.66)
                                            border.width: 1
                                            border.color: cardMA.containsMouse
                                                ? Qt.rgba(root.novaCyan.r, root.novaCyan.g, root.novaCyan.b, 0.55)
                                                : root.hairline
                                            scale: cardMA.containsMouse ? 1.02 : 1.0
                                            Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                                            Behavior on border.color { ColorAnimation { duration: 140 } }
                                            Behavior on color { ColorAnimation { duration: 140 } }

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.margins: 13
                                                spacing: 12
                                                layoutDirection: Qt.application.layoutDirection

                                                Rectangle {
                                                    Layout.preferredWidth: root.fs(42); Layout.preferredHeight: root.fs(42)
                                                    radius: root.fs(12)
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
                                                        text: Qt.application.layoutDirection === Qt.RightToLeft ? modelData.ar : modelData.en
                                                        color: root.textHi
                                                        font.family: root.uiFont
                                                        font.pixelSize: root.fs(14)
                                                        font.weight: Font.DemiBold
                                                        elide: Text.ElideRight
                                                    }
                                                    Text {
                                                        Layout.fillWidth: true
                                                        text: modelData.hint
                                                        color: root.textMute
                                                        font.family: root.uiFont
                                                        font.pixelSize: root.fs(11)
                                                        elide: Text.ElideRight
                                                    }
                                                }
                                            }
                                            MouseArea {
                                                id: cardMA
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: root.sendPrompt(modelData.send)
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
                            radius: root.fs(12)
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
                                    Layout.preferredWidth: root.fs(22)
                                    Layout.preferredHeight: root.fs(22)
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text {
                                        text: "وجدت " + root.problemCount + " مشكلة في جهازك  |  Found " + root.problemCount + " issue(s)"
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.fs(13)
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: (root.actions[0] || {}).title || ""
                                        color: root.textLo
                                        font.family: root.uiFont
                                        font.pixelSize: root.fs(11)
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
                            visible: false   // superseded by the hero's premium suggestion cards
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
                            radius: root.fs(12)
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
                                    font.pixelSize: root.fs(11)
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
                                    radius: root.fs(11)
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
                                            Layout.preferredWidth: root.fs(8)
                                            Layout.preferredHeight: root.fs(8)
                                            Layout.alignment: Qt.AlignVCenter
                                            radius: height / 2
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
                                                font.pixelSize: root.fs(11)
                                                font.weight: Font.DemiBold
                                            }
                                            Text {
                                                Layout.maximumWidth: 118
                                                visible: root.routeModel !== ""
                                                text: root.routeModel
                                                color: root.textLo
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(9)
                                                elide: Text.ElideRight
                                            }
                                        }

                                        Text {
                                            text: "▾"
                                            color: root.textMute
                                            font.family: root.uiFont
                                            font.pixelSize: root.fs(10)
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
                                    font.pixelSize: root.fs(14)
                                    leftPadding: 14
                                    rightPadding: 14
                                    background: Rectangle {
                                        color: root.surface1
                                        radius: root.fs(11)
                                        border.width: 1
                                        border.color: input.activeFocus ? root.novaBlue : root.hairline
                                        Behavior on border.color { ColorAnimation { duration: 130 } }
                                    }
                                    onAccepted: root.send()
                                }

                                Rectangle {
                                    Layout.fillHeight: true
                                    Layout.preferredWidth: root.fs(106)
                                    radius: root.fs(11)
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
                                        font.pixelSize: root.fs(13)
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
                                            font.pixelSize: root.fs(16)
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
                                            font.pixelSize: root.fs(11)
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
                                            { icon: "moos-system",   ar: "نواة MoOS", v: (root.snap.kernel || "?") }
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
                                                text: modelData.ar
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(11)
                                                Layout.preferredWidth: root.fs(54)
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: modelData.v
                                                color: root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(12)
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
                                        Layout.preferredWidth: root.fs(18)
                                        Layout.preferredHeight: root.fs(18)
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: root.plan.driver_status || ""
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.fs(12)
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
                                                font.pixelSize: root.fs(13)
                                                font.weight: Font.DemiBold
                                                elide: Text.ElideRight
                                            }
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: issue.modelData.detail || ""
                                            color: root.textLo
                                            font.family: root.uiFont
                                            font.pixelSize: root.fs(11)
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
                                    placeholderText: "ابحث في Flathub… (مثلاً blender) | Search Flathub…"
                                    placeholderTextColor: root.textMute
                                    color: root.textHi
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(13)
                                    leftPadding: 14
                                    rightPadding: 14
                                    background: Rectangle {
                                        color: root.surface1
                                        radius: root.fs(11)
                                        border.width: 1
                                        border.color: searchField.activeFocus ? root.novaBlue : root.hairline
                                    }
                                    onAccepted: root.searchApps(text)
                                }
                                MoButton {
                                    Layout.preferredHeight: root.fs(40)
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
                                    font.pixelSize: root.fs(12)
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
                                                Layout.preferredWidth: root.fs(38)
                                                Layout.preferredHeight: root.fs(38)
                                                radius: root.fs(10)
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
                                                        font.pixelSize: root.fs(13)
                                                        font.weight: Font.DemiBold
                                                    }
                                                    Text {
                                                        visible: hit.verified
                                                        text: "✓"
                                                        color: root.novaCyan
                                                        font.pixelSize: root.fs(12)
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
                                                            text: "اختيار MoOS  |  MoOS pick"
                                                            color: root.novaCyan
                                                            font.family: root.uiFont
                                                            font.pixelSize: root.fs(9)
                                                            font.weight: Font.DemiBold
                                                        }
                                                    }
                                                }
                                                Text {
                                                    Layout.fillWidth: true
                                                    text: hit.summary
                                                    color: root.textLo
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.fs(11)
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
                                                    font.pixelSize: root.fs(10)
                                                    wrapMode: Text.WordWrap
                                                }
                                                Text {
                                                    text: hit.id
                                                    color: root.textMute
                                                    font.family: "JetBrains Mono"
                                                    font.pixelSize: root.fs(10)
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
                                                Layout.preferredWidth: root.fs(38)
                                                Layout.preferredHeight: root.fs(38)
                                                radius: root.fs(10)
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
                                                    font.pixelSize: root.fs(13)
                                                    font.weight: Font.DemiBold
                                                }
                                                Text {
                                                    Layout.fillWidth: true
                                                    text: rec.modelData.ar + "  |  " + rec.modelData.en
                                                    color: root.textLo
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.fs(11)
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
                                            Layout.preferredWidth: root.fs(40)
                                            Layout.preferredHeight: root.fs(40)
                                            radius: root.fs(11)
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
                                                    font.pixelSize: root.fs(14)
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
                                                font.pixelSize: root.fs(11)
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
                                            font.pixelSize: root.fs(13)
                                            font.weight: Font.DemiBold
                                        }
                                        Text {
                                            text: "يحتاجه Waydroid والأجهزة الافتراضية.\nNeeded by Waydroid and virtual machines."
                                            color: root.textLo
                                            font.family: root.uiFont
                                            font.pixelSize: root.fs(11)
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
                                                running: !!root.remoteState.active && root.motionEnabled
                                                loops: Animation.Infinite
                                                NumberAnimation { from: 0.7; to: 0.0; duration: 1200 }
                                                NumberAnimation { from: 0.0; to: 0.0; duration: 200 }
                                            }
                                            SequentialAnimation on scale {
                                                running: !!root.remoteState.active && root.motionEnabled
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
                                            font.pixelSize: root.fs(16)
                                            font.weight: Font.DemiBold
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: root.remoteState.active
                                                ? "افتح اللوحة لمسح رمز QR من هاتفك.\nOpen the panel to scan the QR code from your phone."
                                                : "شغّله ليتحكّم هاتفك بهذا الجهاز.\nStart it to control this PC from your phone."
                                            color: root.textLo
                                            font.family: root.uiFont
                                            font.pixelSize: root.fs(11)
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
                                        font.pixelSize: root.fs(13)
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
                                                font.pixelSize: root.fs(12)
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
                                            Layout.preferredWidth: root.fs(40)
                                            Layout.preferredHeight: root.fs(40)
                                            radius: root.fs(11)
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
                                                    font.pixelSize: root.fs(14)
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
                                                        text: "يعمل بلا إنترنت  |  offline"
                                                        color: root.novaCyan
                                                        font.family: root.uiFont
                                                        font.pixelSize: root.fs(9)
                                                        font.weight: Font.DemiBold
                                                    }
                                                }
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: ag.modelData.ar + "  |  " + ag.modelData.en
                                                color: root.textLo
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(11)
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: ag.modelData.needs
                                                color: ag.onDevice ? root.novaCyan : root.textMute
                                                opacity: ag.onDevice ? 0.95 : 0.8
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(10)
                                            }
                                            Text {
                                                text: ag.modelData.pkg
                                                color: root.textMute
                                                font.family: "JetBrains Mono"
                                                font.pixelSize: root.fs(10)
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
                            spacing: 8
                            SectionTitle { text: "الوكيل  |  Agent" }
                            Item { Layout.fillWidth: true }
                            StatusPill {
                                good: root.agentReady
                                goodText: root.agentBusy
                                    ? "يفكّر… | Thinking"
                                    : "جاهز عند الطلب | Ready on demand"
                                badText: !root.agentStatusLoaded
                                    ? "جارٍ الفحص… | Checking"
                                    : !root.agentInstalled
                                        ? "غير مثبّت | Not installed"
                                        : !root.agentMachineConfigured
                                            ? "يحتاج إعداد | Setup needed"
                                            : "غير متصل | Offline"
                            }
                            MoButton {
                                label: "تحديث | Refresh"
                                icon: "moos-report"
                                onClicked: root.agentLoadStatus()
                            }
                        }

                        SectionNote {
                            Layout.fillWidth: true
                            text: "نفس المحادثات التي تراها في تليجرام — تقرأها هنا وتكمل من الشاشة."
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
                                spacing: 12
                                Kirigami.Icon {
                                    source: root.agentInstalled ? "moos-system" : "moos-install"
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
                                            ? "أكمل تجهيز الوكيل | Finish agent setup"
                                            : "ثبّت وكيل الهاتف | Install phone agent"
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.fs(14)
                                        font.weight: Font.DemiBold
                                    }
                                    SectionNote {
                                        Layout.fillWidth: true
                                        text: root.agentSetupNote
                                        font.pixelSize: root.fs(11)
                                    }
                                }
                                MoButton {
                                    primary: true
                                    icon: root.agentInstalled ? "moos-repair" : "moos-install"
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
                            font.pixelSize: root.fs(11)
                            wrapMode: Text.Wrap
                        }

                        RowLayout {
                            visible: root.agentMachineConfigured
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 10

                            // ── sessions ──
                            Card {
                                Layout.preferredWidth: root.fs(190)
                                Layout.fillHeight: true
                                ColumnLayout {
                                    anchors.fill: parent
                                    spacing: 4
                                    Text {
                                        text: "المحادثات | Sessions"
                                        color: root.textMute
                                        font.family: root.uiFont
                                        font.pixelSize: root.fs(10)
                                        font.weight: Font.DemiBold
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
                                                        anchors.right: parent.right
                                                        anchors.margins: 8
                                                        text: modelData.label
                                                        elide: Text.ElideRight
                                                        color: root.agentCurrent === modelData.id ? root.novaBlue : root.textMute
                                                        font.family: root.uiFont
                                                        font.pixelSize: root.fs(11)
                                                    }
                                                    MouseArea {
                                                        anchors.fill: parent
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: root.agentOpen(modelData.id, modelData.key)
                                                    }
                                                }
                                            }
                                            Text {
                                                visible: root.agentSessions.length === 0
                                                Layout.fillWidth: true
                                                Layout.topMargin: 10
                                                text: "لا محادثات بعد"
                                                horizontalAlignment: Text.AlignHCenter
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(10)
                                            }
                                        }
                                    }
                                }
                            }

                            // ── thread ──
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: 8

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
                                                    radius: root.fs(10)
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
                                                        font.pixelSize: root.fs(12)
                                                    }
                                                }
                                            }
                                            Text {
                                                visible: root.agentThread.length === 0
                                                Layout.fillWidth: true
                                                Layout.topMargin: 30
                                                text: "اختر محادثة، أو اكتب رسالة لتبدأ واحدة جديدة"
                                                horizontalAlignment: Text.AlignHCenter
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(11)
                                            }
                                        }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    QQC2.TextField {
                                        id: agentInput
                                        Layout.fillWidth: true
                                        placeholderText: "اكتب رسالة…  |  Message"
                                        enabled: root.agentReady && !root.agentBusy
                                        font.family: root.uiFont
                                        font.pixelSize: root.fs(12)
                                        onAccepted: if (root.agentReady) {
                                            root.agentSend(text)
                                            text = ""
                                        }
                                    }
                                    MoButton {
                                        label: root.agentBusy ? "…" : "إرسال | Send"
                                        enabled_: root.agentReady && !root.agentBusy
                                        onClicked: { root.agentSend(agentInput.text); agentInput.text = "" }
                                    }
                                }
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
            radius: root.fs(12)
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
                    // Neutral "working" — not a ✓ success claim. The action may
                    // fail-closed (no confirm dialog) or be a no-op; the orb only
                    // knows it dispatched the request, not that it completed.
                    text: "جارٍ التنفيذ…  |  Working…"
                    color: root.novaCyan
                    font.family: root.uiFont
                    font.pixelSize: root.fs(11)
                    font.weight: Font.DemiBold
                }
                Text {
                    text: toast.msg
                    color: root.textHi
                    font.family: root.uiFont
                    font.pixelSize: root.fs(13)
                }
            }
        }

        // ── The brain picker ────────────────────────────────────────────────
        // Every entry here is REAL: local models come from the selected engine's
        // inventory, cloud ones from the provider's own /v1/models. Nothing is
        // invented, and a provider with no model list says so instead of being
        // given a made-up menu.
        Rectangle {
            anchors.fill: parent
            z: 250
            visible: root.pickerOpen
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                           Kirigami.Theme.textColor.b, 0.69)
            MouseArea { anchors.fill: parent; onClicked: root.pickerOpen = false }

            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 86
                width: Math.min(parent.width - 40, 430)
                height: Math.min(parent.height - 130, pickCol.implicitHeight + 32)
                radius: root.fs(16)
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
                            font.pixelSize: root.fs(15)
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
                        font.pixelSize: root.fs(10)
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
                                font.pixelSize: root.fs(10)
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
                                    radius: root.fs(10)
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
                                                font.pixelSize: root.fs(12)
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
                                                      ? ("يُنزَّل الآن — " + root.pullPercent
                                                         + "% | downloading — keep this open")
                                                      : (locRow.modelData.note ? locRow.modelData.note + "  ·  " : "")
                                                      + (!locRow.modelData.pulled
                                                        ? ((locRow.modelData.size_gb > 0
                                                            ? "~" + locRow.modelData.size_gb + " GB — " : "")
                                                           + "تحميل بضغطة | one-tap download")
                                                        : locRow.modelData.serving
                                                        ? "جاهز | ready"
                                                        : "محمَّل — يُعاد تشغيل العقل | downloaded — restarts the brain")
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(9)
                                                elide: Text.ElideRight
                                            }
                                        }
                                        Text {
                                            visible: locRow.on_
                                            text: "✓"
                                            color: root.okColor
                                            font.family: root.uiFont
                                            font.pixelSize: root.fs(13)
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
                                            Behavior on width { NumberAnimation { duration: 260 } }
                                        }
                                    }
                                    MouseArea {
                                        id: locMa
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        // Not pickRoute: an un-pulled brain must be
                                        // fetched before it can answer anything.
                                        onClicked: root.pickOrPull(locRow.modelData)
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
                                font.pixelSize: root.fs(9)
                                wrapMode: Text.WordWrap
                            }

                            // ── Cloud ──────────────────────────────────────
                            Text {
                                Layout.topMargin: 8
                                text: "سحابي  |  Cloud"
                                color: root.textMute
                                font.family: root.uiFont
                                font.pixelSize: root.fs(10)
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
                                    radius: root.fs(10)
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
                                            font.pixelSize: root.fs(12)
                                            font.weight: cldRow.on_ ? Font.DemiBold : Font.Normal
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            visible: cldRow.on_
                                            text: "✓"
                                            color: root.novaViolet
                                            font.family: root.uiFont
                                            font.pixelSize: root.fs(13)
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
                                font.pixelSize: root.fs(10)
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
            anchors.fill: parent
            z: 300
            visible: root.settingsOpen
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                           Kirigami.Theme.textColor.b, 0.82)
            MouseArea { anchors.fill: parent; onClicked: root.settingsOpen = false }

            Rectangle {
                anchors.centerIn: parent
                width: Math.min(parent.width - 48, 560)
                height: Math.min(parent.height - 48, 640)
                radius: root.fs(18)
                color: root.surface1
                border.color: root.hairline
                border.width: 1
                MouseArea { anchors.fill: parent }   // ابتلع النقر حتى لا يُغلق

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 12

                    // ── header ──
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        ColumnLayout {
                            spacing: 0
                            Text {
                                text: "الإعدادات  |  Settings"
                                color: root.textHi
                                font.family: root.uiFont
                                font.pixelSize: root.fs(17)
                                font.weight: Font.DemiBold
                            }
                            Text {
                                text: "تسري على المحادثة هنا وعلى بوت تليجرام معاً"
                                color: root.textMute
                                font.family: root.uiFont
                                font.pixelSize: root.fs(10)
                            }
                        }
                        Item { Layout.fillWidth: true }
                        StatusPill {
                            good: root.cfgError === ""
                            goodText: root.cfgSaving ? "يحفظ… | Saving" : "متصل | Linked"
                            badText: "لوحة التحكم متوقفة"
                        }
                        MoButton {
                            label: "إغلاق | Close"
                            onClicked: root.settingsOpen = false
                        }
                    }

                    // ── section tabs ──
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        Repeater {
                            model: [
                                { id: "brain",   ar: "العقل",     en: "Brain" },
                                { id: "channel", ar: "القناة",    en: "Channel" },
                                { id: "voice",   ar: "الصوت",     en: "Voice" },
                                { id: "power",   ar: "الطاقة",    en: "Power" },
                                { id: "perms",   ar: "الصلاحيات", en: "Access" },
                                { id: "models",  ar: "النماذج",   en: "Models" },
                                { id: "health",  ar: "الصحة",     en: "Health" }
                            ]
                            delegate: Rectangle {
                                required property var modelData
                                readonly property bool on_: root.cfgTab === modelData.id
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.fs(32)
                                radius: root.fs(9)
                                color: on_ ? Qt.rgba(root.novaBlue.r, root.novaBlue.g, root.novaBlue.b, 0.18)
                                           : "transparent"
                                border.width: 1
                                border.color: on_ ? root.novaBlue : root.hairline
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.ar
                                    color: on_ ? root.novaBlue : root.textMute
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(12)
                                    font.weight: on_ ? Font.DemiBold : Font.Normal
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.cfgTab = modelData.id
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
                        font.pixelSize: root.fs(11)
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
                            spacing: 12

                            // ══ BRAIN ══════════════════════════════════════
                            ColumnLayout {
                                visible: root.cfgTab === "brain"
                                Layout.fillWidth: true
                                spacing: 8

                                SectionNote {
                                    Layout.fillWidth: true
                                    text: "المحلي مجاني وخاص. السحابي أذكى للمهام الصعبة."
                                }

                                Repeater {
                                    model: [
                                        { id: "local", ar: "محلي وخاص", d: "كل رسالة تعالج على هذا الجهاز" },
                                        { id: "cloud", ar: "سحابي", d: "كل رسالة تذهب إلى المزوّد الذي اخترته" }
                                    ]
                                    delegate: Rectangle {
                                        required property var modelData
                                        readonly property bool on_: root.cfgMode === modelData.id
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: root.fs(50)
                                        radius: root.fs(11)
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
                                                text: modelData.ar
                                                color: on_ ? root.novaBlue : root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(12)
                                                font.weight: Font.DemiBold
                                            }
                                            Text {
                                                text: modelData.d
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(10)
                                            }
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: root.cfgMode = modelData.id
                                        }
                                    }
                                }

                                SectionTitle { text: "المزوّد السحابي" ; Layout.topMargin: 6 }

                                QQC2.ComboBox {
                                    id: provBox
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
                                    Layout.fillWidth: true
                                    placeholderText: "https://…/v1"
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(11)
                                }
                                QQC2.TextField {
                                    id: modelField
                                    Layout.fillWidth: true
                                    placeholderText: "اسم النموذج | model id"
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(11)
                                }
                                QQC2.TextField {
                                    id: keyField
                                    Layout.fillWidth: true
                                    echoMode: TextInput.Password
                                    placeholderText: root.cfgHasKey
                                        ? "المفتاح محفوظ — اتركه فارغاً لإبقائه"
                                        : "sk-…  (يُكتب ولا يُقرأ)"
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(11)
                                }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: root.cfgHasKey
                                        ? "مفتاح محفوظ في الإعداد. لن يُعرض هنا أبداً."
                                        : "لا مفتاح محفوظ — الوضع السحابي لن يعمل بدونه."
                                }
                            }

                            // ══ CHANNEL ════════════════════════════════════
                            ColumnLayout {
                                visible: root.cfgTab === "channel"
                                Layout.fillWidth: true
                                spacing: 8

                                SectionNote {
                                    Layout.fillWidth: true
                                    text: "بوت تليجرام — تكلّمه من جوالك وترى المحادثة في لوحة «الوكيل»."
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: "مفعّلة"
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.fs(12)
                                    }
                                    Item { Layout.fillWidth: true }
                                    QQC2.Switch { id: tgSwitch }
                                }
                                QQC2.TextField {
                                    id: tokenField
                                    Layout.fillWidth: true
                                    echoMode: TextInput.Password
                                    placeholderText: root.cfgHasToken
                                        ? "التوكن محفوظ — اتركه فارغاً لإبقائه"
                                        : "123456:AA…  من @BotFather"
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(11)
                                }
                                QQC2.TextField {
                                    id: allowField
                                    Layout.fillWidth: true
                                    placeholderText: "معرّفك الرقمي — مثال: 123456789"
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(11)
                                }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: "المعرّف الرقمي لا اسم المستخدم: الأسماء تُغيَّر ويُعاد تخصيصها، والرقم ثابت. اتركه فارغاً فيعود الوضع إلى الاقتران حتى لا تُقفل خارج بوتك."
                                }
                            }

                            // ══ VOICE ══════════════════════════════════════
                            ColumnLayout {
                                visible: root.cfgTab === "voice"
                                Layout.fillWidth: true
                                spacing: 8

                                SectionNote {
                                    Layout.fillWidth: true
                                    text: "تكتب فيرد نصاً، وترسل رسالة صوتية فيرد صوتاً."
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: "الرد بصوت"
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.fs(12)
                                    }
                                    Item { Layout.fillWidth: true }
                                    QQC2.Switch { id: ttsSwitch }
                                }
                                QQC2.ComboBox {
                                    id: ttsAutoBox
                                    Layout.fillWidth: true
                                    model: ["حين أرسل صوتاً فقط", "دائماً", "أبداً"]
                                    font.family: root.uiFont
                                }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: "الفصحى ممتازة · الشامي مقبول · المغاربية غير مفهومة. صوت واحد: ar_JO-kareem."
                                }
                            }

                            // ══ POWER ══════════════════════════════════════
                            ColumnLayout {
                                visible: root.cfgTab === "power"
                                Layout.fillWidth: true
                                spacing: 8

                                SectionNote {
                                    Layout.fillWidth: true
                                    text: "متى ينزل النموذج من كرت الشاشة ويترك الجهاز يتنفّس."
                                }
                                QQC2.ComboBox {
                                    id: keepBox
                                    Layout.fillWidth: true
                                    model: ["٥ دقائق — أقل ضغط", "١٥ دقيقة — موصى به", "ساعة", "لا ينام أبداً"]
                                    font.family: root.uiFont
                                }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: "«لا ينام أبداً» يحجز ٤ جيجا باستمرار. مع متصفح مكبّر قد يستنزف الذاكرة ويُسقط سطح المكتب."
                                }

                            }

                            // ══ ACCESS ═════════════════════════════════════
                            // Three tiers, mapped onto OpenClaw's OWN enforcement. The
                            // decisive knob is sandbox.mode (all=boxed, off=host):
                            //   read → معطّل: sandbox=all, exec denied — no reach to the machine
                            //   ask  → مع إذن: sandbox=off (HOST) + approvals forwarded to the
                            //          origin chat, so a Telegram request is approved from
                            //          Telegram before the command runs on the real computer
                            //   full → كامل: sandbox=off (HOST), elevatedDefault=full, nothing
                            //          withheld — runs on the machine immediately, no prompt
                            // Only the allowlisted owner can drive any of it. Each switch
                            // writes the key the engine already obeys — no invented layer.
                            ColumnLayout {
                                visible: root.cfgTab === "perms"
                                Layout.fillWidth: true
                                spacing: 8

                                SectionNote {
                                    Layout.fillWidth: true
                                    text: "كم يتحكّم الوكيل بجهازك فعلياً من تليجرام (كاميرا، برامج، ترمنال، تحديث، تطوير). ابدأ بـ«مع إذن»."
                                }

                                // ── Quick toggle: host control ON / OFF ────────────
                                // One tap flips between full host control (sandbox off)
                                // and fully sandboxed (read). It writes the tier through
                                // moai-agent-api, which restarts OpenClaw so Telegram picks
                                // it up at once. The three tiers below stay for the middle
                                // "with approval" choice.
                                Rectangle {
                                    id: hostToggle
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: root.fs(60)
                                    radius: root.fs(12)
                                    readonly property bool hostOn: root.cfgTier !== "read"
                                    color: hostOn ? Qt.rgba(root.okColor.r, root.okColor.g, root.okColor.b, 0.12)
                                                  : Qt.rgba(root.textMute.r, root.textMute.g, root.textMute.b, 0.07)
                                    border.width: 1
                                    border.color: hostOn ? root.okColor : root.hairline
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 14
                                        anchors.rightMargin: 14
                                        spacing: 12
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 1
                                            Text {
                                                text: "تحكّم البوت بجهازك"
                                                color: root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(13)
                                                font.weight: Font.DemiBold
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: hostToggle.hostOn
                                                    ? "مُفعّل — يصل للكاميرا والترمنال وتحديث النظام من تليجرام"
                                                    : "معزول — يردّ فقط، لا يتحكّم بشيء"
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(10)
                                                wrapMode: Text.Wrap
                                            }
                                        }
                                        QQC2.Switch {
                                            checked: root.cfgTier !== "read"
                                            enabled: !root.cfgSaving
                                            onToggled: {
                                                root.cfgTier = checked ? "full" : "read"
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
                                    model: [
                                        { id: "read", ar: "معطّل — بلا تحكّم",
                                          d: "يردّ ويحلّل داخل عزل فقط. لا كاميرا ولا برامج ولا ترمنال" },
                                        { id: "ask",  ar: "مع إذن — تحكّم بموافقة",
                                          d: "يتحكّم بالجهاز الحقيقي، لكن يعرض كل أمر وتوافق عليه في تليجرام قبل تنفيذه" },
                                        { id: "full", ar: "كامل — تحكّم بلا سؤال",
                                          d: "ينفّذ أي شيء على جهازك فوراً بلا موافقة. الأقوى والأخطر — لك وحدك" }
                                    ]
                                    delegate: Rectangle {
                                        required property var modelData
                                        readonly property bool on_: root.cfgTier === modelData.id
                                        readonly property bool risky: modelData.id === "full"
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: root.fs(54)
                                        radius: root.fs(11)
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
                                                text: modelData.ar
                                                color: on_ ? (risky ? root.badColor : root.novaBlue) : root.textHi
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(12)
                                                font.weight: Font.DemiBold
                                            }
                                            Text {
                                                text: modelData.d
                                                color: root.textMute
                                                font.family: root.uiFont
                                                font.pixelSize: root.fs(10)
                                                wrapMode: Text.Wrap
                                            }
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: root.cfgTier = modelData.id
                                        }
                                    }
                                }

                                SectionTitle { text: "مجلد المشروع" ; Layout.topMargin: 6 }
                                QQC2.TextField {
                                    id: projectField
                                    Layout.fillWidth: true
                                    text: root.cfgProject
                                    placeholderText: "/var/home/moos/… (فارغ = بلا نطاق)"
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(11)
                                }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: "يحصر عمل الوكيل في مجلد واحد. مسار مطلق داخل مجلد المنزل فقط — أي شيء آخر يُرفض."
                                }

                                SectionTitle { text: "الإنترنت" ; Layout.topMargin: 6 }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: "بحث وقراءة صفحات"
                                        color: root.textHi
                                        font.family: root.uiFont
                                        font.pixelSize: root.fs(12)
                                    }
                                    Item { Layout.fillWidth: true }
                                    QQC2.Switch { id: webSwitch }
                                }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: "نموذج 4B ضعيف أمام حقن التعليمات — صفحة خبيثة تقدر تعطيه أوامر باعتبارها محتوى. فعّله مع العقل السحابي فقط."
                                }
                            }

                            // ══ MODELS ═════════════════════════════════════
                            ColumnLayout {
                                visible: root.cfgTab === "models"
                                Layout.fillWidth: true
                                spacing: 8

                                RowLayout {
                                    Layout.fillWidth: true
                                    SectionTitle { text: "النماذج المحلية" }
                                    Item { Layout.fillWidth: true }
                                    MoButton {
                                        label: "تحديث | Refresh"
                                        onClicked: root.loadModels()
                                    }
                                }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: "تُحمَّل من الجهاز — بلا إنترنت وبلا اشتراك. التنزيل بضغطة واحدة."
                                }

                                Repeater {
                                    model: root.localModels
                                    delegate: Rectangle {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: root.fs(52)
                                        radius: root.fs(11)
                                        color: "transparent"
                                        border.width: 1
                                        border.color: root.hairline
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 10
                                            spacing: 8
                                            ColumnLayout {
                                                spacing: 1
                                                Text {
                                                    text: modelData.label || modelData.id
                                                    color: root.textHi
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.fs(12)
                                                    font.weight: Font.DemiBold
                                                }
                                                Text {
                                                    text: modelData.pulled
                                                        ? ("محمّل" + (modelData.size ? " · " + modelData.size : ""))
                                                        : "غير محمّل — اضغط للتنزيل"
                                                    color: root.textMute
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.fs(10)
                                                }
                                            }
                                            Item { Layout.fillWidth: true }
                                            MoButton {
                                                label: modelData.pulled ? "استخدم | Use" : "نزّل | Get"
                                                onClicked: root.pickOrPull(modelData)
                                            }
                                            MoButton {
                                                visible: !!modelData.pulled
                                                label: "حذف"
                                                danger: true
                                                onClicked: root.deleteModel(modelData.id)
                                            }
                                        }
                                    }
                                }

                                Text {
                                    visible: root.pullModel !== ""
                                    Layout.fillWidth: true
                                    text: "جارٍ تنزيل " + root.pullModel + " — " + root.pullPercent + "٪"
                                    color: root.novaBlue
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(11)
                                }
                                Text {
                                    visible: root.pullError !== ""
                                    Layout.fillWidth: true
                                    text: root.pullError
                                    color: root.badColor
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(11)
                                    wrapMode: Text.Wrap
                                }
                            }

                            // ══ HEALTH ═════════════════════════════════════
                            // Repairs are moos://do/<id> — a NAMED action that moai-do
                            // confirms and runs behind Polkit. Never a composed command:
                            // that is the safety contract the build gate enforces.
                            ColumnLayout {
                                visible: root.cfgTab === "health"
                                Layout.fillWidth: true
                                spacing: 8

                                RowLayout {
                                    Layout.fillWidth: true
                                    SectionTitle { text: "صحة النظام" }
                                    Item { Layout.fillWidth: true }
                                    MoButton {
                                        label: root.diagLoading ? "يفحص…" : "افحص الآن"
                                        enabled_: !root.diagLoading
                                        icon: "moos-report"
                                        onClicked: root.diagnoseSystem()
                                    }
                                }
                                SectionNote {
                                    Layout.fillWidth: true
                                    text: "فحص للقراءة فقط من moos-selfcheck. كل إصلاح فعل مسمّى يسألك قبل تنفيذه."
                                }

                                Text {
                                    visible: !root.diagLoading && (root.diagResult.summary !== undefined)
                                    Layout.fillWidth: true
                                    text: root.diagResult.summary || ""
                                    color: root.textHi
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(12)
                                    wrapMode: Text.Wrap
                                }

                                Repeater {
                                    // defaultRepairs is the documented fallback ("always shown,
                                    // and the fallback before a diagnose run has returned") — but
                                    // nothing ever rendered it, so it was dead code and the safe
                                    // repair menu simply did not exist until a diagnose returned
                                    // fixes. Use it whenever the backend has none, which is also
                                    // what makes the read-only diagnostics reachable.
                                    model: (root.diagResult.fixes && root.diagResult.fixes.length)
                                           ? root.diagResult.fixes : root.defaultRepairs
                                    delegate: Rectangle {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: root.fs(52)
                                        radius: root.fs(11)
                                        color: "transparent"
                                        border.width: 1
                                        border.color: root.hairline
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 10
                                            spacing: 8
                                            ColumnLayout {
                                                spacing: 1
                                                Text {
                                                    // Two shapes reach this delegate: the backend's
                                                    // fixes carry `title`, defaultRepairs carries
                                                    // `label`. Accept both, or the fallback list
                                                    // renders bare ids at the user.
                                                    text: modelData.title || modelData.label || modelData.id
                                                    color: root.textHi
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.fs(12)
                                                    font.weight: Font.DemiBold
                                                }
                                                Text {
                                                    text: modelData.note || ""
                                                    visible: !!modelData.note
                                                    color: root.textMute
                                                    font.family: root.uiFont
                                                    font.pixelSize: root.fs(10)
                                                    wrapMode: Text.Wrap
                                                }
                                            }
                                            Item { Layout.fillWidth: true }
                                            MoButton {
                                                // A read-only entry (diagnose-services, net-doctor,
                                                // gpu-report…) shows information; calling its button
                                                // "Fix" promises a repair it does not perform.
                                                label: modelData.read ? "افحص | Check" : "أصلح | Fix"
                                                onClicked: Qt.openUrlExternally("moos://do/" + modelData.id)
                                            }
                                        }
                                    }
                                }

                                Text {
                                    visible: !root.diagLoading
                                             && (root.diagResult.fixes === undefined
                                                 || root.diagResult.fixes.length === 0)
                                             && root.diagResult.summary !== undefined
                                    Layout.fillWidth: true
                                    text: "لا مشاكل تحتاج إصلاحاً."
                                    color: root.okColor
                                    font.family: root.uiFont
                                    font.pixelSize: root.fs(11)
                                }
                            }
                        }
                    }

                    // ── save ──
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.fs(44)
                        radius: root.fs(12)
                        opacity: root.cfgSaving ? 0.6 : 1
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: root.novaBlue }
                            GradientStop { position: 1.0; color: root.novaViolet }
                        }
                        Text {
                            anchors.centerIn: parent
                            text: root.cfgSaving ? "جارٍ الحفظ… | Saving…" : "حفظ | Save"
                            color: root.onAccent
                            font.family: root.uiFont
                            font.pixelSize: root.fs(14)
                            font.weight: Font.DemiBold
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            enabled: !root.cfgSaving
                            onClicked: root.cfgSave({
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
    property string cfgTab: "brain"
    property string cfgMode: "local"
    property string cfgProvider: "synterolink"
    property var    cfgProviders: []
    property var    cfgProviderNames: []
    property bool   cfgHasKey: false
    property bool   cfgHasToken: false
    property bool   cfgSaving: false
    property string cfgError: ""
    property string cfgTier: "ask"
    property string cfgProject: ""

    function cfgLoad(done) {
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/config")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status !== 200) {
                root.cfgError = "لوحة التحكم لا تستجيب — شغّل moai-agent-api.service"
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
                root.cfgError = "رد غير مفهوم من لوحة التحكم"
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
                root.cfgError = "تعذّر الحفظ (HTTP " + xhr.status + ")"
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
            ? "ثبّت وأكمل | Install"
            : "جهّز العقل | Set up"
    readonly property string agentSetupNote:
        !agentInstalled
            ? "إعداد واحد مؤكّد يثبّت OpenClaw والعقل والصوت محلياً، ثم يبقى التشغيل عند الطلب."
            : !agentOpenClawConfigured
                ? "إعداد OpenClaw غير مكتمل؛ أعد تشغيل المثبّت الآمن ليصلحه دون مسح اختياراتك."
                : "العقل أو الصوت المحلي غير مجهّز. الإجراء التالي ينشئهما ويتحقق منهما فعلياً."

    function agentLoadStatus() {
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/status")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status !== 200) {
                root.agentStatusLoaded = false
                root.agentStatusError = "لوحة الوكيل لا تستجيب — moai-agent-api.service"
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
                    root.agentLoadSessions()
            } catch (e) {
                root.agentStatusLoaded = false
                root.agentStatusError = "رد حالة الوكيل غير مفهوم | Bad status response"
            }
        }
        xhr.send()
    }

    function agentLoadSessions() {
        const xhr = new XMLHttpRequest()
        xhr.open("GET", root.agentApi + "/api/sessions")
        xhr.setRequestHeader("X-Moai-Agent", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try { root.agentSessions = JSON.parse(xhr.responseText); root.agentError = "" }
                catch (e) { root.agentError = "رد غير مفهوم | Bad response" }
            } else {
                root.agentError = "لوحة الوكيل لا تستجيب — moai-agent-api.service"
            }
        }
        xhr.send()
    }

    function agentOpen(id, key) {
        root.agentCurrent = id
        root.agentCurrentKey = String(key).split(":").pop()
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
            let reply = "لا رد | No reply"
            if (xhr.status === 200) {
                try { const r = JSON.parse(xhr.responseText); reply = r.reply || r.error || reply }
                catch (e) { reply = "رد غير مفهوم" }
            } else {
                reply = "تعذّر الاتصال بالوكيل"
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
