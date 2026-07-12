// Mo AI v1 — MoOS built-in assistant (premium glass redesign + system control)
// Launched by /usr/bin/moai (qml-qt6 runtime — pure QML, no compilation).
//
// Backend: `ramalama serve` → llama.cpp llama-server, an OpenAI-compatible
// REST API. RamaLama's default serving port is 8080 (ramalama-serve docs:
// "The default serving port will be 8080 if available") and moai-start passes
// --port 8080 explicitly so it always matches the `api` constant below.
//
// SYSTEM CONTROL — the honest design:
//   Pure QML has NO Process API and its XMLHttpRequest cannot WRITE local files
//   (VERIFIED 2026-07-10, doc.qt.io/qt-6/qml-qtqml-xmlhttprequest.html: local
//   files can be READ with QML_XHR_ALLOW_FILE_READ but not written), so this
//   window cannot exec anything itself. Instead the Quick-Actions pills COPY an
//   exact `moai-do <action>` command to the clipboard (the same hidden-TextEdit
//   .copy() trick the Hardware Center uses) and show a bilingual toast telling
//   the user to run it in a terminal. The real, auditable work happens in the
//   whitelisted helper /usr/bin/moai-do (confirmation + pkexec). The model can
//   ALSO suggest the same `moai-do ...` commands in chat.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    // ── The brain endpoint is ALWAYS 127.0.0.1:8080. Whichever brain is active
    //    owns that port: the local RamaLama service (moai.service) OR the cloud
    //    gateway (moai-cloud.service, which holds the API key). moai-config
    //    switches which one runs, so this app stays simple and never needs to
    //    know the mode or read a config/argv.
    readonly property string api: "http://127.0.0.1:8080/v1/chat/completions"

    // The active streaming request, so the Stop button can abort it.
    property var activeXhr: null

    // ── In-app Settings (backed by the moai-control service on :8079) ───────
    readonly property string controlApi: "http://127.0.0.1:8079"
    property bool settingsOpen: false
    property bool settingsCloud: false
    property bool settingsSaving: false
    property string settingsError: ""

    function loadConfig() {
        settingsError = ""
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
                    fKey.text = ""
                    fKey.placeholderText = c.has_key
                        ? "•••• محفوظ | saved (اتركه فارغاً للإبقاء)"
                        : "sk-…  مفتاحك | your API key"
                } catch (e) {}
            } else {
                root.settingsError = "خدمة الإعدادات غير متاحة | settings service unavailable"
            }
        }
        xhr.send()
    }

    function saveConfig() {
        const body = {
            mode: settingsCloud ? "cloud" : "local",
            cloud_base: fBase.text.trim(),
            cloud_model: fModel.text.trim()
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
            if (xhr.status === 200)
                root.settingsOpen = false
            else
                root.settingsError = "تعذّر الحفظ | couldn't save"
        }
        xhr.send(JSON.stringify(body))
    }

    // System prompt (Mo AI v2 — an intelligent MoOS assistant).
    readonly property string systemPrompt:
        "You are Mo AI, the intelligent built-in assistant of MoOS — a premium " +
        "Arabic/English (RTL) Linux desktop by Moalfarras, based on Fedora Atomic " +
        "(bootc/OSTree, atomic updates) + KDE Plasma 6. Be genuinely helpful, " +
        "precise and proactive.\n\n" +
        "WHAT YOU CAN DO (put the EXACT command in a fenced code block — the app " +
        "shows a one-click Run button for moai-do actions):\n" +
        "• Fix & maintain: `moai-do update` (atomic system update), `moai-do " +
        "fix-audio`, `moai-do check-drivers`, `moai-do optimize` (clean + speed up), " +
        "`moai-do hw-report`.\n" +
        "• Install software: `moai-do install <flatpak-id>` (a Flathub app). Prefer " +
        "Flatpaks over layering rpm-ostree packages; for browsing, open the MoOS App " +
        "Center (Bazaar).\n" +
        "• Diagnose: explain the likely cause in plain language, then give a clear " +
        "step-by-step repair plan (services: `systemctl --user status <svc>`, logs: " +
        "`journalctl`).\n" +
        "• Program apps or MoOS itself: tell the user to use the “برمجة | Code” quick " +
        "action — it launches Claude Code or Codex in a terminal on their project.\n" +
        "• Ground advice in real hardware via the “افحص نظامي | Scan” action.\n\n" +
        "HOW TO BEHAVE: understand the goal → briefly diagnose → propose the SMALLEST " +
        "safe action → show the exact command → one line on what it does. Always " +
        "confirm before anything that updates, installs, removes, reboots or rolls " +
        "back. NEVER suggest destructive/unsafe commands, a raw root shell, or " +
        "bypassing confirmations. If offline or unsure, say so honestly.\n" +
        "STYLE: concise, friendly, in the user's language (العربية RTL أو English), " +
        "with short bullets and code blocks."

    // Rendered as Markdown. Points at the real "Start local brain" button below.
    readonly property string offlineHelp:
        "العقل المحلي غير مشغّل.\n" +
        "The local brain is off.\n\n" +
        "اضغط **«شغّل العقل المحلي»** بالأسفل — أو شغّل `moai-start` في الطرفية.\n" +
        "Tap **“Start local brain”** below — or run `moai-start` in a terminal.\n\n" +
        "ثم أعد المحاولة | then try again."

    // Shown while the brain is starting (first-run ~2.5 GB download), so the app
    // never says "offline" at the user who just started it.
    readonly property string startingHelp:
        "العقل المحلي يبدأ الآن… أول تشغيل يُحمّل النموذج (~2.5GB) وقد يأخذ دقائق.\n" +
        "The local brain is starting… first run downloads the model (~2.5 GB) and may take a few minutes.\n\n" +
        "سأصبح جاهزاً تلقائياً عند الانتهاء. | I'll be ready automatically once it finishes."

    // Cloud brain selected but the gateway/provider isn't answering.
    readonly property string cloudHelp:
        "لا أصل إلى العقل السحابي.\n" +
        "Can't reach the cloud brain.\n\n" +
        "افتح الإعدادات ⚙ وتحقّق من المفتاح والنموذج، أو بدّل للعقل المحلي.\n" +
        "Open settings ⚙ and check your key/model, or switch to the local brain."

    // Nova dark brand palette (MOOS_DESIGN)
    readonly property color brandBg: "#0B1220"
    readonly property color brandSurface: "#111A2E"
    readonly property color brandRaised: "#1A2740"
    readonly property color brandBlue: "#2E7BFF"
    readonly property color brandCyan: "#22D3EE"
    readonly property color brandViolet: "#8B5CF6"
    readonly property color brandText: "#E6EDF7"
    readonly property color brandSecondary: "#9FB0C9"
    readonly property color hairline: "#243350"

    // Quick actions — each pill LAUNCHES its `url` for real via the moos://
    // scheme handler (/usr/bin/moos-open), which runs the auditable moai-do
    // action in a visible terminal (confirmation + pkexec). No more clipboard.
    // icon: MoOS action symbols shipped at hicolor/scalable/actions, resolved
    // by NAME through the icon theme (contract §4 — no absolute paths).
    readonly property var quickActions: [
        { ar: "افحص نظامي",     en: "Scan",          url: "", action: "scan",        accent: "#22D3EE", icon: "moos-report" },
        { ar: "تحديث النظام",   en: "Update",        url: "moos://do/update",        accent: "#2E7BFF", icon: "moos-safe-update" },
        { ar: "تثبيت تطبيقات",  en: "Install apps",  url: "moos://app/setup",        accent: "#22D3EE", icon: "moos-install" },
        { ar: "إصلاح الصوت",    en: "Fix audio",     url: "moos://do/fix-audio",     accent: "#8B5CF6", icon: "moos-audio" },
        { ar: "فحص التعريفات",  en: "Check drivers", url: "moos://do/check-drivers", accent: "#22D3EE", icon: "moos-gpu" },
        { ar: "تحسين وتنظيف",   en: "Optimize",      url: "moos://do/optimize",      accent: "#2E7BFF", icon: "moos-optimize" },
        { ar: "تقرير الأجهزة",  en: "HW report",     url: "moos://do/hw-report",     accent: "#8B5CF6", icon: "moos-report" },
        { ar: "الخدمات الفاشلة", en: "Failed services", url: "moos://do/diagnose-services", accent: "#FFB45C", icon: "moos-system" },
        { ar: "مشاكل الإقلاع", en: "Boot problems", url: "moos://do/inspect-boot", accent: "#FF6B7A", icon: "moos-warning" },
        { ar: "افتح المحدّث", en: "Open updater", url: "moos://app/updater", accent: "#2E7BFF", icon: "moos-safe-update" },
        { ar: "افتح الاستعادة", en: "Open recovery", url: "moos://app/recovery", accent: "#8B5CF6", icon: "moos-system" },
        { ar: "برمجة (Claude/Codex)", en: "Code",    url: "moos://dev/code",         accent: "#22D3EE", icon: "moos-optimize" }
    ]

    // Clickable example prompts shown on a fresh conversation (empty history).
    readonly property var starters: [
        { emoji: "🚀", ar: "حدّث نظامي",    en: "Update my system", send: "حدّث نظام MoOS من فضلك" },
        { emoji: "🖥️", ar: "مواصفات جهازي", en: "My specs",         send: "ما مواصفات جهازي؟" },
        { emoji: "🔊", ar: "صلّح الصوت",     en: "Fix audio",        send: "الصوت لا يعمل عندي، ساعدني" },
        { emoji: "⚡", ar: "سرّع MoOS",      en: "Speed up MoOS",    send: "أعطني نصائح لتسريع وتحسين MoOS" }
    ]

    property bool serverUp: false
    property bool busy: false
    // True from when the user asks to start the local brain until the server is
    // up. The first run downloads ~2.5 GB, so without this the app would keep
    // saying "offline / start the brain" for minutes even though it IS starting.
    property bool brainStarting: false
    property var history: []   // [{role, content}] user/assistant only, last 12

    function startBrain() {
        Qt.openUrlExternally("moos://brain/start")
        brainStarting = true
        brainStartGuard.restart()   // clears if the server never comes up
    }

    // Safety net: if starting fails or the user cancels, stop claiming "starting"
    // after a generous window (first-run download can be slow).
    Timer { id: brainStartGuard; interval: 720000; onTriggered: root.brainStarting = false }

    // ── Nova Companion state (artwork/moai/README.md wiring contract) ───────
    // A 1400 ms success/error flash overrides the steady mapping:
    //   !serverUp → offline (local brain, not Internet), busy → thinking,
    //   focused + typed text → attentive, otherwise idle.
    property string companionFlash: ""
    readonly property string companionState:
        companionFlash !== "" ? companionFlash
        : !serverUp ? (brainStarting ? "thinking" : "offline")
        : busy ? "thinking"
        : (input.activeFocus && input.text.trim().length > 0) ? "attentive"
        : "idle"

    function flashCompanion(state) {
        companionFlash = state
        companionFlashTimer.restart()
    }

    Timer {
        id: companionFlashTimer
        interval: 1400
        onTriggered: root.companionFlash = ""
    }

    // Bilingual type (contract §5): Latin shapes in IBM Plex Sans, Arabic
    // falls back to IBM Plex Sans Arabic — both ship in the image (c4).
    // QML Text exposes font.family (singular), not a font.families list.
    // Qt/fontconfig automatically falls back to IBM Plex Sans Arabic for
    // Arabic glyphs that are not present in the primary Latin family.
    readonly property string uiFont: "IBM Plex Sans"

    title: "Mo AI"
    width: 460
    height: 720
    minimumWidth: 380
    minimumHeight: 520
    color: brandBg

    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    readonly property string greetingText:
        "مرحباً! أنا **Mo AI** — مساعدك في MoOS. أقدر أساعدك تتحكّم بالنظام: " +
        "التحديث، تثبيت التطبيقات، إصلاح الصوت والمزيد.\n\n" +
        "Hi! I'm **Mo AI** — your MoOS assistant. I can help you control the " +
        "system: updates, installing apps, fixing audio and more.\n\n" +
        "_جرّب الأزرار السريعة بالأسفل | try the quick actions below._"

    // Actions the model suggested in its last reply (parsed moai-do commands),
    // surfaced as one-click "Run" chips above the input.
    property var pendingRuns: []

    Component.onCompleted: chatModel.append({ role: "assistant", text: greetingText })

    ListModel { id: chatModel }

    // Poll the server so the header badge stays honest. /v1/models is a cheap
    // llama-server endpoint that exists whenever chat/completions does.
    Timer {
        interval: 4000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            const xhr = new XMLHttpRequest()
            xhr.open("GET", root.api.replace("/chat/completions", "/models"))
            xhr.onreadystatechange = function () {
                if (xhr.readyState === XMLHttpRequest.DONE) {
                    const up = (xhr.status === 200)
                    root.serverUp = up
                    if (up) root.brainStarting = false   // it's ready now
                }
            }
            xhr.send()
        }
    }

    function trimHistory() {
        if (history.length > 12)
            history = history.slice(-12)
    }

    function removeTypingBubble() {
        if (chatModel.count > 0
                && chatModel.get(chatModel.count - 1).role === "typing")
            chatModel.remove(chatModel.count - 1)
    }

    // Launch a quick action for real via the moos:// handler (moos-open), which
    // runs the auditable moai-do action in a visible terminal (confirm + pkexec).
    // Pure QML can't exec, but Qt.openUrlExternally reaches the scheme handler.
    // Detect safe moai-do actions the model mentioned so we can offer to run
    // them with one click (the actual run still goes through moai-do's own
    // confirmation + pkexec).
    function extractRuns(text) {
        const out = []
        const re = /moai-do\s+(update|fix-audio|check-drivers|optimize|hw-report)/g
        let m
        while ((m = re.exec(text)) !== null)
            if (out.indexOf(m[1]) === -1)
                out.push(m[1])
        return out
    }

    // Start a fresh conversation.
    function newChat() {
        chatModel.clear()
        history = []
        pendingRuns = []
        stopGenerating()
        chatModel.append({ role: "assistant", text: greetingText })
    }

    // Read-only system scan via moai-control; show it in chat and give the model
    // the context so follow-up "how do I improve this?" answers are grounded.
    function doScan() {
        const xhr = new XMLHttpRequest()
        xhr.open("GET", controlApi + "/scan")
        xhr.setRequestHeader("X-Moai-Control", "1")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            if (xhr.status !== 200) {
                chatModel.append({ role: "assistant",
                    text: "تعذّر فحص النظام | couldn't scan the system." })
                return
            }
            try {
                const s = JSON.parse(xhr.responseText)
                const disk = s.disk && s.disk.total_gb
                    ? (s.disk.free_gb + "/" + s.disk.total_gb + " GB free") : "?"
                const md = "**فحص النظام | System scan**\n\n"
                    + "- 🖥️ " + (s.os || "MoOS") + "\n"
                    + "- ⚙️ " + (s.cpu || "?") + "  (" + (s.cores || "?") + " cores)\n"
                    + "- 🧠 " + (s.mem_gb || "?") + " GB RAM\n"
                    + "- 💾 " + disk + "\n"
                    + "- 🎮 " + (s.gpu || "?") + "\n"
                    + "- 🐧 kernel " + (s.kernel || "?")
                chatModel.append({ role: "assistant", text: md })
                root.history.push({ role: "assistant", content: md })
                root.trimHistory()
                input.text = "بناءً على هذا الفحص، كيف أحسّن أداء وأمان نظامي؟ | Based on this scan, how do I improve my system's performance and security?"
                input.forceActiveFocus()
            } catch (e) {}
        }
        xhr.send()
    }

    function runAction(a) {
        if (a.action === "scan") {
            doScan()
            return
        }
        Qt.openUrlExternally(a.url)
        toast.show(a.ar + "  |  " + a.en)
        // No success state here: launching != the action succeeding — just an
        // honest attentive pulse (contract §7).
        attentivePulse.restart()
    }

    function sendPrompt(msg) {
        input.text = msg
        send()
    }

    function stopGenerating() {
        if (activeXhr) {
            try { activeXhr.abort() } catch (e) {}
            activeXhr = null
        }
        busy = false
    }

    function send() {
        const msg = input.text.trim()
        if (msg === "" || busy)
            return
        input.text = ""
        chatModel.append({ role: "user", text: msg })
        history.push({ role: "user", content: msg })
        trimHistory()
        // One growing bubble: starts as a "typing" pulse, becomes the assistant
        // reply and extends token-by-token as the stream arrives.
        chatModel.append({ role: "typing", text: "…" })
        const idx = chatModel.count - 1
        busy = true
        pendingRuns = []   // clear last reply's suggested actions

        let acc = ""          // accumulated reply text
        let sawData = false    // did we get any streamed delta?
        let processed = 0      // chars of responseText already parsed

        const xhr = new XMLHttpRequest()
        activeXhr = xhr
        xhr.open("POST", api)
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function () {
            // Parse newly-arrived SSE lines during LOADING (live) and DONE.
            if (xhr.readyState === XMLHttpRequest.LOADING
                    || xhr.readyState === XMLHttpRequest.DONE) {
                const full = xhr.responseText
                // Consume only COMPLETE lines: a `data:` line can split across
                // two ticks, so keep any trailing partial line buffered until
                // its newline arrives. At DONE, consume the remainder too.
                let end = full.lastIndexOf("\n") + 1     // 0 if no newline yet
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
                    } catch (e) { /* partial JSON line — completes next tick */ }
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
                root.flashCompanion("success")
                return
            }
            // No stream (older server or error) — try a whole-response parse.
            let reply = ""
            if (xhr.status === 200) {
                try {
                    reply = JSON.parse(xhr.responseText)
                                .choices[0].message.content.trim()
                } catch (e) { reply = "" }
            }
            if (reply !== "") {
                chatModel.set(idx, { role: "assistant", text: reply })
                root.history.push({ role: "assistant", content: reply })
                root.trimHistory()
                root.pendingRuns = root.extractRuns(reply)
                root.flashCompanion("success")
            } else {
                const help = !root.serverUp
                    ? (root.brainStarting ? root.startingHelp : root.offlineHelp)
                    : "لم أستطع توليد رد، حاول مجدداً. | I couldn't generate a reply — please try again."
                chatModel.set(idx, { role: "assistant", text: help })
                root.flashCompanion(root.serverUp ? "warning" : "error")
            }
        }
        xhr.send(JSON.stringify({
            model: "default",
            messages: [{ role: "system", content: systemPrompt }]
                          .concat(history),
            stream: true
        }))
    }

    pageStack.initialPage: Kirigami.Page {
        padding: 0
        background: Rectangle {
            color: root.brandBg
            Image {
                source: "file:///usr/share/wallpapers/NovaHorizonII/contents/images_dark/3840x2160.png"
                anchors.fill: parent
                fillMode: Image.PreserveAspectCrop
                opacity: 0.18
                smooth: true
            }
        }

        // Full RTL mirroring for Arabic sessions (contract §5): follows the
        // application layout direction and cascades to every child.
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ── Thin brand gradient bar (cyan → blue → violet) ──────────────
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 3
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: root.brandCyan }
                    GradientStop { position: 0.5; color: root.brandBlue }
                    GradientStop { position: 1.0; color: root.brandViolet }
                }
            }

            // ── Header (glass) ──────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 64
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#151F38" }
                    GradientStop { position: 1.0; color: "#0D1526" }
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    spacing: 11

                    // Nova Companion — the transparent Mo AI mascot replaces the
                    // old square-in-square tile (contract §3). All seven states
                    // stay PRELOADED as stacked Images; state changes cross-fade
                    // opacity only over 160 ms (contract §1 — never swap source).
                    Item {
                        id: companion
                        Layout.preferredWidth: 46
                        Layout.preferredHeight: 46

                        Repeater {
                            model: ["idle", "attentive", "thinking", "success",
                                    "warning", "error", "offline"]
                            Image {
                                required property string modelData
                                anchors.fill: parent
                                source: "file:///usr/share/moos/branding/moai/mascot/"
                                        + modelData + ".png"
                                sourceSize.width: 96
                                sourceSize.height: 96
                                fillMode: Image.PreserveAspectFit
                                smooth: true
                                opacity: root.companionState === modelData ? 1 : 0
                                Behavior on opacity {
                                    NumberAnimation { duration: 160 }
                                }
                            }
                        }

                        // Idle breathe: scale 1.0↔1.018 over 2800 ms; loop stops
                        // when the window is hidden (contract §2) and yields to
                        // the pulse so the two never fight over `scale`.
                        SequentialAnimation {
                            running: root.visible && root.companionState === "idle"
                                     && !attentivePulse.running
                            loops: Animation.Infinite
                            onStopped: companion.scale = 1.0
                            NumberAnimation {
                                target: companion; property: "scale"
                                from: 1.0; to: 1.018; duration: 1400
                                easing.type: Easing.InOutSine
                            }
                            NumberAnimation {
                                target: companion; property: "scale"
                                from: 1.018; to: 1.0; duration: 1400
                                easing.type: Easing.InOutSine
                            }
                        }

                        // Thinking wobble: scale 1.0↔1.025 + rotation −1.2↔1.2°
                        // over 1500 ms (contract §2).
                        ParallelAnimation {
                            running: root.visible && root.companionState === "thinking"
                            loops: Animation.Infinite
                            onStopped: { companion.scale = 1.0; companion.rotation = 0 }
                            SequentialAnimation {
                                NumberAnimation {
                                    target: companion; property: "scale"
                                    from: 1.0; to: 1.025; duration: 750
                                    easing.type: Easing.InOutSine
                                }
                                NumberAnimation {
                                    target: companion; property: "scale"
                                    from: 1.025; to: 1.0; duration: 750
                                    easing.type: Easing.InOutSine
                                }
                            }
                            SequentialAnimation {
                                NumberAnimation {
                                    target: companion; property: "rotation"
                                    from: -1.2; to: 1.2; duration: 750
                                    easing.type: Easing.InOutSine
                                }
                                NumberAnimation {
                                    target: companion; property: "rotation"
                                    from: 1.2; to: -1.2; duration: 750
                                    easing.type: Easing.InOutSine
                                }
                            }
                        }

                        // Honest attentive pulse for runAction (contract §7).
                        SequentialAnimation {
                            id: attentivePulse
                            NumberAnimation {
                                target: companion; property: "scale"
                                from: 1.0; to: 1.06; duration: 140
                                easing.type: Easing.OutQuad
                            }
                            NumberAnimation {
                                target: companion; property: "scale"
                                from: 1.06; to: 1.0; duration: 200
                                easing.type: Easing.InQuad
                            }
                        }
                    }

                    ColumnLayout {
                        spacing: 1
                        Text {
                            text: "Mo AI"
                            color: root.brandText
                            font.family: root.uiFont
                            font.pixelSize: 18
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: "مساعد MoOS | MoOS assistant"
                            color: root.brandSecondary
                            font.family: root.uiFont
                            font.pixelSize: 11
                        }
                    }

                    Item { Layout.fillWidth: true }

                    // New conversation
                    Rectangle {
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 24
                        radius: 8
                        color: newMouse.containsMouse ? "#1C2A47" : "transparent"
                        border.width: 1
                        border.color: newMouse.containsMouse ? "#3A4E76" : "#26334F"
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Text {
                            anchors.centerIn: parent
                            text: "＋"
                            color: root.brandSecondary
                            font.pixelSize: 16
                        }
                        MouseArea {
                            id: newMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.newChat()
                        }
                    }

                    // Settings ⚙ — opens the in-app Settings overlay (local/cloud).
                    Rectangle {
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 24
                        radius: 8
                        color: gearMouse.containsMouse ? "#1C2A47" : "transparent"
                        border.width: 1
                        border.color: gearMouse.containsMouse ? "#3A4E76" : "#26334F"
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Text {
                            anchors.centerIn: parent
                            text: "⚙"
                            color: root.brandSecondary
                            font.pixelSize: 14
                        }
                        MouseArea {
                            id: gearMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { root.loadConfig(); root.settingsOpen = true }
                        }
                    }

                    // Live status badge (pulses when the local brain is up).
                    Rectangle {
                        Layout.preferredHeight: 24
                        Layout.preferredWidth: badgeRow.implicitWidth + 20
                        radius: 12
                        color: "#141F38"
                        border.width: 1
                        border.color: root.serverUp ? Qt.rgba(0.13, 0.83, 0.93, 0.55)
                                                    : "#26334F"

                        RowLayout {
                            id: badgeRow
                            anchors.centerIn: parent
                            spacing: 6

                            Rectangle {
                                width: 7
                                height: 7
                                radius: 3.5
                                color: root.serverUp ? root.brandCyan
                                     : root.brainStarting ? root.brandBlue
                                     : root.brandSecondary
                                SequentialAnimation on opacity {
                                    running: root.serverUp || root.brainStarting
                                    loops: Animation.Infinite
                                    NumberAnimation { from: 1.0; to: 0.35; duration: 900 }
                                    NumberAnimation { from: 0.35; to: 1.0; duration: 900 }
                                }
                            }

                            Text {
                                text: root.serverUp ? "متصل | online"
                                     : root.brainStarting ? "يبدأ… | starting…"
                                     : "غير متصل | offline"
                                color: root.serverUp ? root.brandCyan
                                     : root.brainStarting ? root.brandBlue
                                     : root.brandSecondary
                                font.family: root.uiFont
                                font.pixelSize: 11
                            }
                        }
                    }
                }

                Rectangle {   // hairline under the header
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    color: root.hairline
                }
            }

            // ── Chat ────────────────────────────────────────────────────────
            ListView {
                id: listView
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 3
                topMargin: 10
                bottomMargin: 10
                model: chatModel
                onCountChanged: Qt.callLater(listView.positionViewAtEnd)

                QQC2.ScrollBar.vertical: QQC2.ScrollBar { }

                delegate: Item {
                    width: listView.width
                    height: bubble.height + 6

                    // 24 px Nova Companion avatar on assistant/typing bubbles;
                    // typing wears "thinking" (contract §3). Anchors flip under
                    // LayoutMirroring for RTL.
                    Image {
                        visible: model.role !== "user"
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        y: 4
                        width: 24
                        height: 24
                        sourceSize.width: 48
                        sourceSize.height: 48
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        source: "file:///usr/share/moos/branding/moai/mascot/"
                                + (model.role === "typing" ? "thinking" : "idle")
                                + ".png"
                    }

                    Rectangle {
                        id: bubble
                        readonly property bool mine: model.role === "user"
                        // anchors (not x:) so locale LayoutMirroring (RTL) flips
                        // the bubbles correctly.
                        anchors.right: mine ? parent.right : undefined
                        anchors.left: mine ? undefined : parent.left
                        anchors.rightMargin: 12
                        anchors.leftMargin: mine ? 12 : 40
                        y: 3
                        radius: 12
                        // user: brand blue tint; assistant: raised surface — both
                        // with a soft 1px border for the glass look.
                        color: mine ? "#242E7BFF" : root.brandRaised
                        border.width: 1
                        border.color: mine ? Qt.rgba(0.18, 0.48, 1.0, 0.38)
                                           : "#27344F"
                        width: msgText.width + 26
                        height: msgText.implicitHeight + 20

                        Text {
                            id: msgText
                            x: 13
                            y: 10
                            width: Math.min(implicitWidth,
                                            (listView.width * 0.82) - 26)
                            text: model.text
                            textFormat: model.role === "assistant"
                                        ? Text.MarkdownText : Text.PlainText
                            wrapMode: Text.Wrap
                            color: root.brandText
                            linkColor: root.brandCyan
                            font.family: root.uiFont
                            font.pixelSize: 14
                            onLinkActivated: function (link) {
                                Qt.openUrlExternally(link)
                            }

                            SequentialAnimation on opacity {
                                running: model.role === "typing"
                                loops: Animation.Infinite
                                // Value-source animations don't restore on stop;
                                // when typing→assistant flips, force full opacity
                                // so the streamed reply isn't left dimmed.
                                onRunningChanged: if (!running) msgText.opacity = 1
                                NumberAnimation { from: 1.0; to: 0.25; duration: 450 }
                                NumberAnimation { from: 0.25; to: 1.0; duration: 450 }
                            }
                        }
                    }
                }
            }

            // ── Starter prompts — only on a fresh conversation ──────────────
            Flow {
                Layout.fillWidth: true
                Layout.leftMargin: 12
                Layout.rightMargin: 12
                Layout.topMargin: 2
                Layout.bottomMargin: 2
                spacing: 8
                // chatModel.count notifies (unlike history.push); only the
                // greeting present → count 1 → fresh conversation.
                visible: chatModel.count <= 1

                Repeater {
                    model: root.starters
                    delegate: Rectangle {
                        id: chip
                        required property var modelData
                        radius: 14
                        height: 30
                        width: chipRow.implicitWidth + 22
                        color: chipMouse.containsMouse ? "#1C2A47" : "#131D33"
                        border.width: 1
                        border.color: chipMouse.containsMouse ? "#3A4E76" : "#26334F"
                        Behavior on color { ColorAnimation { duration: 120 } }

                        RowLayout {
                            id: chipRow
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: chip.modelData.emoji; font.pixelSize: 13 }
                            Text {
                                text: chip.modelData.ar + "  |  " + chip.modelData.en
                                color: root.brandText
                                font.family: root.uiFont
                                font.pixelSize: 12
                            }
                        }
                        MouseArea {
                            id: chipMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.sendPrompt(chip.modelData.send)
                        }
                    }
                }
            }

            // ── Quick actions (the system-control bar) ──────────────────────
            Rectangle {
                id: quickBar
                Layout.fillWidth: true
                Layout.preferredHeight: quickCol.implicitHeight + 20
                color: "#0D1526"

                Rectangle {   // top hairline
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: 1
                    color: root.hairline
                }

                ColumnLayout {
                    id: quickCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 10
                    spacing: 8

                    // ── Offline → a REAL "start the local brain" control. Opens
                    //    moos://brain/start (runs moai-start in a terminal: consent
                    //    + ~2.5 GB first-run download). While starting it shows a
                    //    distinct "downloading/warming up" state instead of the flat
                    //    "offline — run a command" dead-end.
                    Rectangle {
                        Layout.fillWidth: true
                        visible: !root.serverUp
                        radius: 12
                        Layout.preferredHeight: startCol.implicitHeight + 18
                        color: root.brainStarting ? "#152447" : "#161F38"
                        border.width: 1
                        border.color: root.brainStarting ? root.brandBlue : root.brandViolet

                        ColumnLayout {
                            id: startCol
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            spacing: 7

                            Text {
                                Layout.fillWidth: true
                                text: root.brainStarting
                                      ? "العقل المحلي يبدأ… أول مرة يُحمّل ~2.5GB وقد يأخذ دقائق.\nLocal brain starting… first run downloads ~2.5 GB, may take minutes."
                                      : "العقل المحلي غير مشغّل — شغّله محلياً بضغطة (يحتاج إنترنت أول مرة).\nThe local brain is off — start it locally in one click (needs Internet the first time)."
                                color: root.brandSecondary
                                font.family: root.uiFont
                                font.pixelSize: 11
                                wrapMode: Text.Wrap
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 36
                                visible: !root.brainStarting
                                radius: 10
                                color: startMouse.pressed ? "#2568D9"
                                     : startMouse.containsMouse ? Qt.lighter(root.brandBlue, 1.1)
                                     : root.brandBlue
                                Behavior on color { ColorAnimation { duration: 120 } }
                                Text {
                                    anchors.centerIn: parent
                                    text: "شغّل العقل المحلي  |  Start local brain"
                                    color: "white"
                                    font.family: root.uiFont
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                }
                                MouseArea {
                                    id: startMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.startBrain()
                                }
                            }
                        }
                    }

                    Text {
                        text: "أوامر سريعة | Quick actions"
                        color: root.brandSecondary
                        font.family: root.uiFont
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                    }

                    Flickable {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        contentWidth: actionsRow.implicitWidth
                        contentHeight: height
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        flickableDirection: Flickable.HorizontalFlick

                        Row {
                            id: actionsRow
                            spacing: 8

                            Repeater {
                                model: root.quickActions

                                delegate: Rectangle {
                                id: pill
                                required property var modelData
                                radius: 15
                                height: 32
                                width: pillRow.implicitWidth + 24
                                color: pillMouse.pressed ? "#101A30"
                                     : pillMouse.containsMouse ? "#1C2A47"
                                     : "#141F38"
                                border.width: 1
                                border.color: pillMouse.containsMouse ? "#3A4E76"
                                                                      : "#26334F"
                                Behavior on color { ColorAnimation { duration: 120 } }

                                RowLayout {
                                    id: pillRow
                                    anchors.centerIn: parent
                                    spacing: 7

                                    // Themed MoOS action symbol, tinted with the
                                    // pill accent (contract §4).
                                    Kirigami.Icon {
                                        source: pill.modelData.icon
                                        color: pill.modelData.accent
                                        Layout.preferredWidth: 16
                                        Layout.preferredHeight: 16
                                    }

                                    Text {
                                        text: pill.modelData.ar + "  |  " + pill.modelData.en
                                        color: root.brandText
                                        font.family: root.uiFont
                                        font.pixelSize: 12
                                    }
                                }

                                MouseArea {
                                    id: pillMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.runAction(pill.modelData)
                                }
                                }
                            }
                        }
                    }
                }
            }

            // ── Suggested actions from the last reply → one-click Run ───────
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: runsFlow.implicitHeight + 16
                visible: root.pendingRuns.length > 0
                color: "#0D1526"
                Rectangle {
                    anchors.left: parent.left; anchors.right: parent.right
                    anchors.top: parent.top; height: 1; color: root.hairline
                }
                Flow {
                    id: runsFlow
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 8
                    Repeater {
                        model: root.pendingRuns
                        delegate: Rectangle {
                            id: runChip
                            required property string modelData
                            radius: 15
                            height: 32
                            width: runRow.implicitWidth + 22
                            color: runMouse.pressed ? "#1F6F3A"
                                 : runMouse.containsMouse ? Qt.lighter("#1E7E45", 1.12)
                                 : "#1E7E45"
                            Behavior on color { ColorAnimation { duration: 120 } }
                            RowLayout {
                                id: runRow
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: "▶"; color: "white"; font.pixelSize: 11 }
                                Text {
                                    text: "نفّذ " + runChip.modelData + " | Run"
                                    color: "white"
                                    font.family: root.uiFont
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                }
                            }
                            MouseArea {
                                id: runMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    Qt.openUrlExternally("moos://do/" + runChip.modelData)
                                    toast.show("moai-do " + runChip.modelData)
                                }
                            }
                        }
                    }
                }
            }

            // ── Input row ───────────────────────────────────────────────────
            Rectangle {
                id: inputBar
                Layout.fillWidth: true
                Layout.preferredHeight: 66
                color: "#0D1526"

                Rectangle {   // top hairline
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: 1
                    color: root.hairline
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    QQC2.TextField {
                        id: input
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        placeholderText: "اسأل Mo AI... | Ask Mo AI..."
                        placeholderTextColor: root.brandSecondary
                        color: root.brandText
                        font.family: root.uiFont
                        font.pixelSize: 14
                        leftPadding: 13
                        rightPadding: 13
                        background: Rectangle {
                            color: root.brandRaised
                            radius: 10
                            border.width: 1
                            border.color: input.activeFocus ? root.brandBlue
                                                            : "#243350"
                        }
                        onAccepted: root.send()
                    }

                    QQC2.Button {
                        id: sendBtn
                        Layout.fillHeight: true
                        Layout.preferredWidth: 100
                        // While streaming, this becomes a Stop button (always
                        // enabled); otherwise it sends when there's text.
                        enabled: root.busy || input.text.trim().length > 0
                        background: Rectangle {
                            radius: 10
                            gradient: Gradient {
                                orientation: Gradient.Horizontal
                                GradientStop {
                                    position: 0.0
                                    color: root.busy ? "#B23A6B"
                                         : !sendBtn.enabled ? "#1E3A66"
                                         : sendBtn.pressed ? "#2568D9" : root.brandBlue
                                }
                                GradientStop {
                                    position: 1.0
                                    color: root.busy ? "#8B2E8B"
                                         : !sendBtn.enabled ? "#1E3A66"
                                         : sendBtn.pressed ? "#4A46C8"
                                         : Qt.rgba(0.35, 0.36, 0.9, 1.0)
                                }
                            }
                        }
                        contentItem: Text {
                            text: root.busy ? "إيقاف | Stop" : "إرسال | Send"
                            color: sendBtn.enabled ? "#FFFFFF" : root.brandSecondary
                            font.family: root.uiFont
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: root.busy ? root.stopGenerating() : root.send()
                    }
                }
            }
        }

        // ── Toast (floats above the quick-actions bar) ──────────────────────
        Rectangle {
            id: toast
            property string cmd: ""
            z: 100
            opacity: 0
            visible: opacity > 0
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: inputBar.height + quickBar.height + 12
            radius: 12
            width: Math.min(parent.width - 28, toastCol.implicitWidth + 28)
            height: toastCol.implicitHeight + 20
            color: "#16223C"
            border.width: 1
            border.color: Qt.rgba(0.13, 0.83, 0.93, 0.5)

            Behavior on opacity { NumberAnimation { duration: 220 } }

            Timer {
                id: toastTimer
                interval: 2800
                onTriggered: toast.opacity = 0
            }

            function show(c) {
                cmd = c
                opacity = 1
                toastTimer.restart()
            }

            ColumnLayout {
                id: toastCol
                anchors.centerIn: parent
                width: parent.width - 28
                spacing: 4

                Text {
                    Layout.fillWidth: true
                    text: "جارٍ التنفيذ في الطرفية ✓ | Running in a terminal ✓"
                    color: root.brandCyan
                    font.family: root.uiFont
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    wrapMode: Text.Wrap
                }
                Text {
                    Layout.fillWidth: true
                    text: toast.cmd
                    color: root.brandText
                    font.family: root.uiFont
                    font.pixelSize: 13
                    wrapMode: Text.WrapAnywhere
                }
            }
        }

        // ── In-app Settings overlay (modern glass card) ─────────────────────
        Rectangle {
            id: settingsOverlay
            anchors.fill: parent
            z: 300
            visible: root.settingsOpen
            color: "#D0060B16"

            // Backdrop click closes; the card's own MouseArea blocks pass-through.
            MouseArea { anchors.fill: parent; onClicked: root.settingsOpen = false }

            Rectangle {
                anchors.centerIn: parent
                width: Math.min(parent.width - 32, 400)
                height: Math.min(parent.height - 36, setCol.implicitHeight + 40)
                radius: 18
                color: root.brandSurface
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
                        Text {
                            text: "إعدادات Mo AI | Settings"
                            color: root.brandText
                            font.family: root.uiFont
                            font.pixelSize: 17
                            font.weight: Font.DemiBold
                        }
                        Item { Layout.fillWidth: true }
                        Rectangle {
                            Layout.preferredWidth: 28
                            Layout.preferredHeight: 28
                            radius: 8
                            color: closeMouse.containsMouse ? "#26334F" : "transparent"
                            Text { anchors.centerIn: parent; text: "✕"; color: root.brandSecondary; font.pixelSize: 14 }
                            MouseArea {
                                id: closeMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.settingsOpen = false
                            }
                        }
                    }

                    Text {
                        text: "العقل | Brain"
                        color: root.brandSecondary
                        font.family: root.uiFont
                        font.pixelSize: 12
                    }

                    // Segmented Local / Cloud toggle
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 44
                        radius: 12
                        color: "#0E1830"
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
                                color: !root.settingsCloud ? root.brandBlue : "transparent"
                                Behavior on color { ColorAnimation { duration: 120 } }
                                Text {
                                    anchors.centerIn: parent
                                    text: "محلي | Local"
                                    color: !root.settingsCloud ? "white" : root.brandSecondary
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
                                color: root.settingsCloud ? root.brandViolet : "transparent"
                                Behavior on color { ColorAnimation { duration: 120 } }
                                Text {
                                    anchors.centerIn: parent
                                    text: "سحابي | Cloud"
                                    color: root.settingsCloud ? "white" : root.brandSecondary
                                    font.family: root.uiFont
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.settingsCloud = true }
                            }
                        }
                    }

                    // Cloud provider fields
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: root.settingsCloud
                        spacing: 7

                        Text { text: "المزوّد | Provider (OpenAI-compatible base URL)"; color: root.brandSecondary; font.family: root.uiFont; font.pixelSize: 11 }
                        QQC2.TextField {
                            id: fBase
                            Layout.fillWidth: true
                            placeholderText: "https://openrouter.ai/api/v1"
                            placeholderTextColor: root.brandSecondary
                            color: root.brandText
                            font.family: root.uiFont
                            background: Rectangle { color: root.brandRaised; radius: 8; border.width: 1; border.color: fBase.activeFocus ? root.brandBlue : root.hairline }
                        }
                        Text { text: "النموذج | Model"; color: root.brandSecondary; font.family: root.uiFont; font.pixelSize: 11 }
                        QQC2.TextField {
                            id: fModel
                            Layout.fillWidth: true
                            placeholderText: "anthropic/claude-sonnet-5"
                            placeholderTextColor: root.brandSecondary
                            color: root.brandText
                            font.family: root.uiFont
                            background: Rectangle { color: root.brandRaised; radius: 8; border.width: 1; border.color: fModel.activeFocus ? root.brandBlue : root.hairline }
                        }
                        Text { text: "مفتاح API | API key (يُحفظ محلياً | stored locally)"; color: root.brandSecondary; font.family: root.uiFont; font.pixelSize: 11 }
                        QQC2.TextField {
                            id: fKey
                            Layout.fillWidth: true
                            echoMode: TextInput.Password
                            placeholderText: "sk-…"
                            placeholderTextColor: root.brandSecondary
                            color: root.brandText
                            font.family: root.uiFont
                            background: Rectangle { color: root.brandRaised; radius: 8; border.width: 1; border.color: fKey.activeFocus ? root.brandBlue : root.hairline }
                        }
                    }

                    // Local note
                    Text {
                        Layout.fillWidth: true
                        visible: !root.settingsCloud
                        text: "العقل المحلي خاص بالكامل (RamaLama) — لا إنترنت بعد التحميل الأول.\nThe local brain is fully private — no Internet after the first download."
                        color: root.brandSecondary
                        font.family: root.uiFont
                        font.pixelSize: 11
                        wrapMode: Text.Wrap
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: root.settingsError !== ""
                        text: root.settingsError
                        color: "#FF6B8B"
                        font.family: root.uiFont
                        font.pixelSize: 11
                        wrapMode: Text.Wrap
                    }

                    // Save
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 44
                        radius: 12
                        opacity: root.settingsSaving ? 0.6 : 1
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: root.brandBlue }
                            GradientStop { position: 1.0; color: root.brandViolet }
                        }
                        Text {
                            anchors.centerIn: parent
                            text: root.settingsSaving ? "جارٍ الحفظ… | Saving…" : "حفظ | Save"
                            color: "white"
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

        // ── Clipboard helper (pure-QML has no clipboard API) ────────────────
        // Kept in the scene and RENDERED (opacity 0, 1x1, behind everything) —
        // not visible:false — so TextEdit.copy() reliably reaches the system
        // clipboard, exactly like the Hardware Center's copy button.
        TextEdit {
            id: clip
            width: 1
            height: 1
            opacity: 0
            z: -1
        }
    }
}
