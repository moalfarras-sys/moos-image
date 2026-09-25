// SPDX-License-Identifier: GPL-2.0-or-later
// kcm_moos_ai — Mo AI inside System Settings: its brain (cloud provider, model, the
// write-only key, free or paid, the free-model measurement), the phone channels, and
// what the phone agent may do on this computer. It replaces the settings sheet that
// lived inside the Mo AI window and the old terminal wizard; there is one place now.
//
// The page is a client of the same two loopback services the Mo AI app uses
// (MoaiService.qml): moai-agent-api, the one owner of the brain, the key, the channels
// and the permission tiers, and moai-control, which serves the model list and runs the
// free-model measurement. It reads when it opens and writes ONLY when the owner presses
// a Save (or picks a default model): opening the page never changes a stored value, the
// safe default included. Secrets are write-only — the service reports has_key and
// has_token, and this page never asks for, holds or shows a saved key or token. A
// section says "Saved" only after the service answered that it saved.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import org.kde.kirigamiaddons.formcard as FormCard
import org.moos.ui as MoUI

KCM.SimpleKCM {
    id: root

    readonly property bool rtl: MoUI.Locale.rtl
    readonly property var design: MoUI.Tokens
    readonly property real cardWidth: Kirigami.Units.gridUnit * 40
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)
    property string routeError: ""

    // ── What the services said. Nothing below is a default dressed as a fact. ──
    property var config: ({})                 // GET /api/config, accepted whole or not at all
    property string configState: "loading"    // loading | ready | offline | unreadable
    property var capabilities: ({})           // GET /api/capabilities (is the phone agent installed)
    property bool capabilitiesKnown: false
    property var modelsDoc: ({})              // GET /models (the provider's own list)
    property string modelsState: "loading"    // loading | ready | offline
    property var measureDoc: ({})             // GET /measure
    property var quickDoc: ({})               // GET /quick (can the default brain answer)
    property bool quickKnown: false
    property var channelsDoc: ({})            // GET /api/channels — only when the owner asks
    property string channelsState: "unchecked" // unchecked | checking | ready | failed
    property string channelsError: ""

    readonly property bool configReady: configState === "ready"
    readonly property var cloud: config.cloud || ({})
    readonly property var telegram: config.telegram || ({})
    readonly property var permissions: config.permissions || ({})
    readonly property var providers: Array.isArray(config.providers) ? config.providers : []
    readonly property var providerNames: providers.map(function (p) { return root.providerLabel(p.name) })
    readonly property string savedProvider: typeof cloud.provider === "string" ? cloud.provider : ""
    readonly property string savedModel: typeof cloud.model === "string" ? cloud.model : ""
    readonly property bool hasKey: cloud.has_key === true
    readonly property bool hasToken: telegram.has_token === true
    readonly property bool savedTelegram: telegram.enabled === true
    readonly property string savedAllow: Array.isArray(telegram.allow) ? telegram.allow.join(", ") : ""
    readonly property string savedTier: typeof permissions.tier === "string" ? permissions.tier : ""
    readonly property bool savedWeb: permissions.web === true
    readonly property string savedProject: typeof permissions.project === "string" ? permissions.project : ""
    // A primary brain exists once a cloud model was saved; the web switch writes a policy
    // keyed on it, and the service refuses web access without one.
    readonly property bool primaryExists: configReady && !!config.brain
                                          && (config.brain.mode === "cloud" || config.brain.mode === "hybrid")
    readonly property string savedLanguage: config.ui && (config.ui.language === "ar" || config.ui.language === "en")
                                            ? config.ui.language : ""
    readonly property bool agentInstalled: capabilitiesKnown && !!capabilities.agent
                                           && capabilities.agent.installed === true
    readonly property var cloudModels: Array.isArray(modelsDoc.cloud) ? modelsDoc.cloud : []
    readonly property string defaultModel: typeof modelsDoc["default"] === "string" ? modelsDoc["default"] : ""
    readonly property bool measuring: measureDoc.measuring === true
    property bool measureStarting: false

    // ── The drafts: what each Save will write. ──
    property string brainProvider: ""
    property bool telegramDraft: false
    property string tierDraft: ""
    property bool webDraft: false

    readonly property bool brainChanged: configReady && (brainProvider !== savedProvider
                                                         || modelField.text.trim() !== savedModel
                                                         || keyField.text.trim() !== "")
    readonly property bool telegramChanged: configReady && (telegramDraft !== savedTelegram
                                                            || tokenField.text.trim() !== ""
                                                            || root.allowList(allowField.text).join(", ") !== savedAllow)
    readonly property bool permissionsChanged: configReady
        && root.permissionsBody({ tier: savedTier, web: savedWeb, project: savedProject },
                                { tier: tierDraft, web: webDraft, project: projectField.text },
                                primaryExists).body !== null

    // ── What each section is doing, and what its last save came back with. ──
    property bool brainSaving: false
    property var brainNotice: ({})
    property bool defaultSaving: false
    property var defaultNotice: ({})
    property bool telegramSaving: false
    property var telegramNotice: ({})
    property bool permissionsSaving: false
    property var permissionsNotice: ({})

    function t(ar, en) { return rtl ? ar : en }
    // Several services answer in both languages at once: "عربي | English".
    function localPair(text) {
        var value = String(text || "")
        var pair = value.split(/\s+\|\s+/)
        return pair.length > 1 ? (rtl ? pair[0] : pair.slice(1).join(" | ")) : value
    }
    // "OpenRouter (مجاني فقط | free only)" → "OpenRouter (free only)" in English.
    function providerLabel(name) {
        var value = String(name || "")
        var match = /^(.*?)\s*\((.*)\s\|\s(.*)\)\s*$/.exec(value)
        return match ? match[1] + " (" + (rtl ? match[2] : match[3]) + ")" : value
    }
    function open(route) {
        routeError = kcm.openRoute(route) ? "" : t("تعذّر فتح هذه الصفحة. حاول مرة أخرى.",
                                                    "Could not open that. Try again.")
    }
    function providerEntry(catalogue, id) {
        for (var i = 0; i < catalogue.length; ++i) {
            if (catalogue[i] && catalogue[i].id === id)
                return catalogue[i]
        }
        return null
    }
    function indexOfId(list, id) {
        for (var i = 0; i < list.length; ++i) {
            if (list[i] && list[i].id === id)
                return i
        }
        return -1
    }
    function modelLabel(row) {
        if (!row)
            return ""
        // The automatic free route, named the way the Mo AI window's brain chip names it.
        if (row.id === "cloud:openrouter/free")
            return t("مجاني تلقائي", "Free · automatic")
        return row.label_ar ? t(row.label_ar, row.label_en || row.label || "") : String(row.label || row.id || "")
    }
    function groupLabel(group) {
        switch (group) {
        case "measured": return t("مقيسة على هذا الجهاز", "Measured on this machine")
        case "curated": return t("مختارة ومجرّبة", "Curated & tested")
        case "paid": return t("نماذج مدفوعة", "Paid models")
        case "free": return t("كل النماذج المجانية", "All free models")
        }
        return ""
    }
    function allowList(text) {
        return String(text || "").split(",").map(function (x) { return x.trim() })
                                 .filter(function (x) { return x.length > 0 })
    }

    // ── The bodies each Save sends: only what that section owns. ──
    // The brain: the provider, its catalogue address (the service refuses any other), the
    // model (blank means the provider's own default), and the key only when one was typed.
    function brainBody(provider, catalogue, model, key) {
        var entry = providerEntry(catalogue, provider)
        if (!entry)
            return { error: t("اختر مزوّداً من القائمة.", "Choose a provider from the list."), body: null }
        var cloudPart = { provider: entry.id, base: String(entry.base || ""),
                          model: String(model || "").trim() || String(entry.model || "") }
        var typed = String(key || "").trim()
        if (typed !== "")
            cloudPart.key = typed
        return { error: "", body: { mode: "cloud", cloud: cloudPart } }
    }
    // The default model, on the provider that is SAVED (the list below is that provider's).
    function defaultBody(provider, catalogue, id) {
        var entry = providerEntry(catalogue, provider)
        if (!entry)
            return { error: t("احفظ مزوّداً أولاً.", "Save a provider first."), body: null }
        var value = String(id || "")
        var bare = value.indexOf("cloud:") === 0 ? value.substring(6) : value
        return { error: "", body: { mode: "cloud", cloud: { provider: entry.id, base: String(entry.base || ""),
                                                             model: bare } } }
    }
    // Telegram: on/off and who may use it, always; the token only when one was typed. A
    // username is refused here: the service would drop it silently and fall back to pairing.
    function telegramBody(enabled, token, allowText) {
        var ids = allowList(allowText)
        for (var i = 0; i < ids.length; ++i) {
            if (!/^[0-9]+$/.test(ids[i]))
                return { error: t("اكتب معرّفات رقمية فقط، مفصولة بفواصل.",
                                  "Use numeric IDs only, separated by commas."), body: null }
        }
        var part = { enabled: enabled === true, allow: ids }
        var typed = String(token || "").trim()
        if (typed !== "")
            part.token = typed
        return { error: "", body: { telegram: part } }
    }
    // Permissions: only what changed. A tier is one of the four; "custom" or an unknown tier
    // is never written back. Saving a tier re-applies the web choice too, because each tier
    // carries its own web default and would otherwise change web access unasked.
    function permissionsBody(saved, draft, hasPrimary) {
        var change = {}
        var tierChanged = ["read", "project", "system", "full"].indexOf(draft.tier) >= 0
                          && draft.tier !== saved.tier
        if (tierChanged)
            change.tier = draft.tier
        if (hasPrimary && (tierChanged || draft.web !== saved.web))
            change.web = draft.web === true
        var project = String(draft.project || "").trim()
        if (project !== String(saved.project || ""))
            change.project = project
        return { body: Object.keys(change).length > 0 ? { permissions: change } : null }
    }
    function failureText(result) {
        if (result.timedOut)
            return t("لم يُجب Mo AI في الوقت المحدد، وقد يُطبَّق التغيير بعد قليل. اضغط «إعادة القراءة» لترى ما حُفظ.",
                     "Mo AI did not answer in time, and the change may still land. Press Refresh to see what is saved.")
        if (result.offline)
            return t("لم يُجب Mo AI، فلم يُحفظ شيء. حاول مرة أخرى.", "Mo AI did not answer, so nothing was saved. Try again.")
        if (result.error)
            return localPair(result.error)
        return t("تعذّر الحفظ (HTTP " + result.status + ").", "Could not save (HTTP " + result.status + ").")
    }

    // ── The words for each state. ──
    function brainChip() {
        if (!quickKnown)
            return { glyph: "ai", tone: "neutral", text: t("حالة العقل غير معروفة", "Brain status unknown") }
        if (quickDoc.online === true)
            return { glyph: "check", tone: "positive", text: t("العقل متصل", "Brain online") }
        return { glyph: "warning", tone: "warning", text: t("العقل غير متصل", "Brain offline") }
    }
    function tierChip(tier) {
        switch (tier) {
        case "read": return { glyph: "shield", tone: "positive", text: t("وكيل الهاتف معزول", "Phone agent sandboxed") }
        case "project": return { glyph: "shield", tone: "positive", text: t("وكيل الهاتف في مجلد المشروع", "Phone agent in the project folder") }
        case "system": return { glyph: "lock", tone: "neutral", text: t("وكيل الهاتف يسأل أولاً", "Phone agent asks first") }
        case "full": return { glyph: "danger", tone: "negative", text: t("وكيل الهاتف بلا تأكيد", "Phone agent needs no confirmation") }
        case "custom": return { glyph: "warning", tone: "warning", text: t("صلاحيات مخصّصة", "Custom permissions") }
        }
        return { glyph: "shield", tone: "neutral", text: t("الصلاحيات غير معروفة", "Permissions unknown") }
    }
    // The saved tier in the words the Mo AI window used for its host-control switch.
    function hostControlText(tier) {
        if (tier === "system" || tier === "full")
            return t("مُفعّل — يصل للكاميرا والترمنال وتحديث النظام من تليجرام",
                     "Enabled — Telegram can reach the camera, terminal and system actions")
        if (tier === "custom")
            return t("إعداد مخصّص على القرص — اختر مستوى أدناه ليُعرف حده الحقيقي",
                     "Custom on-disk configuration — pick a tier below to normalise it")
        if (tier === "read" || tier === "project")
            return t("معزول — يردّ فقط، لا يتحكّم بشيء", "Sandboxed — replies only; no device control")
        return t("غير معروف حتى يُجيب Mo AI.", "Unknown until Mo AI answers.")
    }
    // A key belongs to the service that issued it: the service refuses a switch between
    // services without the new one's key, and the form says so before anyone presses Save.
    readonly property bool keyForThisService: hasKey
        && String((providerEntry(providers, brainProvider) || {}).base || "") !== ""
        && String((providerEntry(providers, brainProvider) || {}).base || "")
           === String((providerEntry(providers, savedProvider) || {}).base || "")
    function keyText() {
        if (keyForThisService)
            return t("مفتاح محفوظ في الإعداد. لن يُعرض هنا أبداً.", "A key is saved. It is never displayed here.")
        if (hasKey)
            return t("المفتاح المحفوظ يخص مزوّداً آخر — أدخل مفتاح هذا المزوّد ليُحفظ.",
                     "The saved key belongs to another provider — enter this provider's key to save.")
        return t("لا مفتاح محفوظ — الوضع السحابي لن يعمل بدونه.", "No key saved — cloud mode requires one.")
    }
    function defaultDescription() {
        if (defaultSaving)
            return t("يُعيَّن الافتراضي…", "Making it the default…")
        if (modelsState === "loading")
            return t("جارٍ جلب النماذج…", "Fetching the model list…")
        if (modelsState === "offline")
            return t("تعذّر جلب النماذج", "Couldn't reach the model list")
        if (modelsDoc.cloud_error)
            return localPair(modelsDoc.cloud_error)
        var row = cloudModels[indexOfId(cloudModels, defaultModel)]
        if (!row)
            return t("الافتراضي المحفوظ ليس في هذه القائمة.", "The saved default is not in this list.")
        return [groupLabel(row.group), t(row.note_ar || "", row.note_en || "")]
            .filter(function (part) { return part !== "" }).join(" · ")
    }
    function measureText(m) {
        if (m.error)
            return localPair(m.error)
        if (m.measuring === true)
            return m.total > 0 ? t("جارٍ القياس — " + m.done + " من " + m.total, "Measuring — " + m.done + " of " + m.total)
                               : t("جارٍ تجهيز القائمة…", "Collecting candidates…")
        if ((m.measuredAt || 0) > 0)
            return t("الأسرع هنا: " + (m.bestLabel || "—") + " · "
                     + (m.ageDays < 1 ? "قيس اليوم" : "قياس عمره " + Math.round(m.ageDays) + " يوم"),
                     "Fastest here: " + (m.bestLabel || "—") + " · "
                     + (m.ageDays < 1 ? "measured today" : "measured " + Math.round(m.ageDays) + " days ago"))
        return t("لم يُقس شيء هنا بعد — الترتيب في القائمة من جهاز آخر.",
                 "Nothing measured here yet — the order in the list came from another machine.")
    }
    function telegramText(channel, state) {
        if (state === "checking")
            return t("جارٍ فحص الاتصال…", "Checking connection…")
        if (state === "ready" && channel) {
            if (channel.connected)
                return t("متصل فعلياً", "Connected") + (channel.account ? " · @" + channel.account : "")
            if (channel.configured)
                return t("مهيّأ لكن غير متصل", "Configured but offline")
            return t("غير مهيّأ", "Not configured")
        }
        if (!configReady)
            return ""
        if (!hasToken)
            return t("غير مهيّأ", "Not configured")
        return savedTelegram ? t("مفعّل؛ لم يُفحص الاتصال بعد", "Turned on; the connection is not checked yet")
                             : t("متوقف", "Turned off")
    }
    function whatsappText(channel, state) {
        if (state === "checking")
            return t("جارٍ فحص الاتصال…", "Checking connection…")
        if (state === "ready" && channel) {
            if (channel.connected)
                return t("متصل فعلياً", "Connected")
            if (channel.configured)
                return t("مهيّأ لكن غير متصل", "Configured but offline")
            return t("غير مربوط — سيفتح الربط رمز QR", "Not linked — pairing opens a QR code")
        }
        return t("لم يُفحص الاتصال بعد", "The connection is not checked yet")
    }

    // ── Reading. ──
    function applyDrafts(sections) {
        if (sections.indexOf("brain") >= 0) {
            brainProvider = savedProvider
            modelField.text = savedModel
            keyField.text = ""
        }
        if (sections.indexOf("telegram") >= 0) {
            telegramDraft = savedTelegram
            tokenField.text = ""
            allowField.text = savedAllow
        }
        if (sections.indexOf("permissions") >= 0) {
            tierDraft = savedTier
            webDraft = savedWeb
            projectField.text = savedProject
        }
    }
    function acceptConfig(doc) {
        return !!doc && typeof doc.cloud === "object" && doc.cloud !== null
            && typeof doc.telegram === "object" && doc.telegram !== null
            && typeof doc.permissions === "object" && doc.permissions !== null
            && Array.isArray(doc.providers)
    }
    function loadConfig(sections) {
        if (!configReady)
            configState = "loading"
        moai.request(true, "GET", "/api/config", null, 15000, function (r) {
            if (!r.ok || !root.acceptConfig(r.data)) {
                root.configState = r.offline ? "offline" : "unreadable"
                return
            }
            root.config = r.data
            root.configState = "ready"
            root.applyDrafts(sections)
        })
    }
    function loadCapabilities() {
        moai.request(true, "GET", "/api/capabilities", null, 10000, function (r) {
            root.capabilities = r.ok ? r.data : ({})
            root.capabilitiesKnown = r.ok
        })
    }
    function loadModels() {
        if (modelsState !== "ready")
            modelsState = "loading"
        moai.request(false, "GET", "/models", null, 30000, function (r) {
            if (!r.ok) {
                root.modelsState = "offline"
                return
            }
            root.modelsDoc = r.data
            root.modelsState = "ready"
        })
    }
    function loadMeasure() {
        moai.request(false, "GET", "/measure", null, 10000, function (r) {
            if (!r.ok)
                return                        // keep the last good measurement
            var finished = root.measuring && r.data.measuring !== true
            root.measureDoc = r.data
            if (finished)
                root.loadModels()             // the list carries a new order and new notes
        })
    }
    function loadQuick() {
        moai.request(false, "GET", "/quick", null, 10000, function (r) {
            root.quickDoc = r.ok ? r.data : ({})
            root.quickKnown = r.ok
        })
    }
    function loadAll(sections) {
        loadConfig(sections)
        loadCapabilities()
        loadModels()
        loadMeasure()
        loadQuick()
    }
    // Waking the phone agent to ask Telegram and WhatsApp is the owner's request, never a
    // side effect of opening the page.
    function checkChannels() {
        channelsState = "checking"
        channelsError = ""
        moai.request(true, "GET", "/api/channels", null, 90000, function (r) {
            if (!r.ok || typeof r.data.channels !== "object" || r.data.channels === null) {
                root.channelsState = "failed"
                root.channelsError = r.offline ? t("لم يُجب Mo AI.", "Mo AI did not answer.")
                                               : t("تعذّر فحص القنوات", "Could not probe channels")
                return
            }
            root.channelsDoc = r.data.channels
            root.channelsError = typeof r.data.error === "string" ? r.data.error : ""
            root.channelsState = "ready"
        })
    }

    // ── Writing: only from a button the owner pressed. ──
    function saveBrain() {
        if (!configReady)
            return                            // nothing is written over a record never read
        var request = brainBody(brainProvider, providers, modelField.text, keyField.text)
        if (request.error !== "") {
            brainNotice = { tone: "error", text: request.error }
            return
        }
        brainSaving = true
        brainNotice = ({})
        moai.request(true, "POST", "/api/config", request.body, 150000, function (r) {
            root.brainSaving = false
            if (!r.ok) {
                root.brainNotice = { tone: "error", text: root.failureText(r) }
                return
            }
            keyField.text = ""
            root.brainNotice = { tone: "positive", text: t("حُفظ العقل.", "The brain is saved.") }
            root.loadConfig(["brain"])
            root.loadModels()
            root.loadQuick()
        })
    }
    function saveDefaultModel(row) {
        if (!configReady)
            return                            // nothing is written over a record never read
        var request = defaultBody(savedProvider, providers, row ? row.id : "")
        if (request.error !== "") {
            defaultNotice = { tone: "error", text: request.error }
            return
        }
        defaultSaving = true
        defaultNotice = ({})
        moai.request(true, "POST", "/api/config", request.body, 150000, function (r) {
            root.defaultSaving = false
            if (!r.ok) {
                root.defaultNotice = { tone: "error", text: root.failureText(r) }
                return
            }
            root.defaultNotice = { tone: "positive", text: t("صار الافتراضي: ", "Default is now: ") + root.modelLabel(row) }
            root.loadConfig(root.brainChanged ? [] : ["brain"])
            root.loadModels()
        })
    }
    function measureFree() {
        measureStarting = true
        moai.request(false, "POST", "/measure", {}, 15000, function (r) {
            root.measureStarting = false
            if (r.ok) {
                root.measureDoc = r.data
                return
            }
            // The refusal carries its own reason — no key, or a provider with no free list.
            root.measureDoc = { measuring: false,
                                error: r.error || (r.offline ? t("لم يُجب Mo AI.", "Mo AI did not answer.")
                                    : t("أضف مفتاح المزوّد أولاً — القياس يرسل سؤالين حقيقيين.",
                                        "Add the provider key first — measuring sends two real questions.")) }
        })
    }
    function saveTelegram() {
        if (!configReady)
            return                            // nothing is written over a record never read
        var request = telegramBody(telegramDraft, tokenField.text, allowField.text)
        if (request.error !== "") {
            telegramNotice = { tone: "error", text: request.error }
            return
        }
        telegramSaving = true
        telegramNotice = ({})
        moai.request(true, "POST", "/api/config", request.body, 150000, function (r) {
            root.telegramSaving = false
            if (!r.ok) {
                root.telegramNotice = { tone: "error", text: root.failureText(r) }
                return
            }
            tokenField.text = ""
            root.telegramNotice = { tone: "positive", text: t("حُفظ تليجرام.", "Telegram is saved.") }
            root.loadConfig(["telegram"])
            if (root.channelsState === "ready")
                root.channelsState = "unchecked"
        })
    }
    function savePermissions() {
        if (!configReady)
            return                            // nothing is written over a record never read
        var request = permissionsBody({ tier: savedTier, web: savedWeb, project: savedProject },
                                      { tier: tierDraft, web: webDraft, project: projectField.text },
                                      primaryExists)
        if (request.body === null)
            return
        permissionsSaving = true
        permissionsNotice = ({})
        moai.request(true, "POST", "/api/config", request.body, 150000, function (r) {
            root.permissionsSaving = false
            if (!r.ok) {
                root.permissionsNotice = { tone: "error", text: root.failureText(r) }
                return
            }
            root.permissionsNotice = { tone: "positive", text: t("حُفظت الصلاحيات.", "Permissions are saved.") }
            root.loadConfig(["permissions"])
        })
    }

    MoaiService { id: moai }

    // While a measurement runs and the page is shown, ask how far it is.
    Timer {
        interval: 2500
        repeat: true
        running: root.measuring && root.visible
        onTriggered: root.loadMeasure()
    }

    LayoutMirroring.enabled: rtl
    LayoutMirroring.childrenInherit: true
    Component.onCompleted: loadAll(["brain", "telegram", "permissions"])
    onVisibleChanged: if (visible) {
        loadQuick()
        loadMeasure()
        loadCapabilities()
    }

    actions: [
        Kirigami.Action {
            text: root.t("إعادة القراءة", "Refresh")
            icon.name: "view-refresh"
            enabled: root.configState !== "loading"
            // Only sections with nothing typed are refilled; an edit in progress stays.
            onTriggered: root.loadAll([root.brainChanged ? "" : "brain", root.telegramChanged ? "" : "telegram",
                                       root.permissionsChanged ? "" : "permissions"])
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            visible: root.configState !== "ready"
            type: root.configState === "loading" ? Kirigami.MessageType.Information : Kirigami.MessageType.Warning
            text: root.configState === "loading"
                ? root.t("جارٍ قراءة إعدادات Mo AI…", "Reading Mo AI's settings…")
                : root.acceptConfig(root.config)
                ? root.t("توقفت خدمة إعدادات Mo AI عن الإجابة. المعروض هو آخر ما أجابت به، ولا يُحفظ شيء حتى تُجيب من جديد.",
                         "Mo AI's settings service stopped answering. What is shown is its last answer, and nothing can be saved until it answers again.")
                : root.configState === "offline"
                ? root.t("خدمة إعدادات Mo AI لا تُجيب، فلا تُعرض إعداداته ولا يُحفظ شيء.",
                         "Mo AI's settings service is not answering, so its settings are not shown and nothing can be saved.")
                : root.t("أجابت خدمة إعدادات Mo AI بما لا تفهمه هذه الصفحة، فلا تُعرض إعداداته ولا يُحفظ شيء.",
                         "Mo AI's settings service answered with something this page cannot read, so its settings are not shown and nothing can be saved.")
            actions: [
                Kirigami.Action {
                    text: root.t("أعد المحاولة", "Try again")
                    icon.name: "view-refresh"
                    visible: root.configState === "offline" || root.configState === "unreadable"
                    onTriggered: root.loadAll(["brain", "telegram", "permissions"])
                }
            ]
        }
        MoosRouteNotice {
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            message: root.routeError
        }

        MoosHero {
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            logoSource: "file:///usr/share/icons/hicolor/scalable/apps/moos-moai.svg"
            title: "Mo AI"
            subtitle: root.t("مساعد MoOS: عقله، وهاتفك، وما يُسمح له به على هذا الحاسوب.",
                             "Your MoOS assistant: its brain, your phone, and what it may do on this computer.")
            chips: [
                MoosChip {
                    glyph: root.brainChip().glyph
                    label: root.brainChip().text
                    tone: root.brainChip().tone
                },
                MoosChip {
                    visible: root.configReady
                    glyph: root.hasKey ? "lock" : "warning"
                    label: root.hasKey ? root.t("المفتاح محفوظ", "Key saved") : root.t("لا مفتاح محفوظ", "No key saved")
                    tone: root.hasKey ? "positive" : "warning"
                },
                MoosChip {
                    visible: root.configReady
                    glyph: root.tierChip(root.savedTier).glyph
                    label: root.tierChip(root.savedTier).text
                    tone: root.tierChip(root.savedTier).tone
                }
            ]
            actions: [
                Controls.Button {
                    Layout.fillWidth: true
                    text: root.t("افتح Mo AI", "Open Mo AI")
                    icon.name: MoUI.SymbolCatalog.resolve("external")
                    onClicked: root.open("moos://app/moai")
                }
            ]
        }

        // ══ The brain ═══════════════════════════════════════════════════════════
        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("العقل", "Brain")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth
            enabled: root.configReady && !root.brainSaving

            MoosInfoRow {
                glyph: "ai"
                text: root.t("عقل سحابي", "Cloud inference")
                description: root.t("المجاني افتراضي؛ المدفوع باختيارك. لا نماذج محلية.",
                                    "Free by default; paid by choice. No local models.")
            }
            FormCard.FormDelegateSeparator {}
            MoaiComboRow {
                label: root.t("المزوّد السحابي", "Cloud provider")
                options: root.providerNames
                shownIndex: root.indexOfId(root.providers, root.brainProvider)
                description: root.brainProvider === "opencode-zen"
                    ? root.t("خدمة OpenCode Zen مدفوعة حسب الاستخدام، بمفتاح من opencode.ai بعد إضافة وسيلة دفع. يعرض Mo AI فقط نماذج المحادثة التي تعمل ببروتوكوله، مثل DeepSeek وGLM وKimi وMiniMax. نماذجه المجانية المؤقتة قد تُستخدم بياناتك لتحسينها، فلا ترسل إليها بيانات شخصية.",
                             "OpenCode Zen bills per use, with a key from opencode.ai once billing is added. Mo AI lists only the chat models Zen serves on Mo AI's protocol (DeepSeek, GLM, Kimi, MiniMax and others). Its temporary free models may use your data to improve them — don't send them personal data.")
                    : (root.providerEntry(root.providers, root.brainProvider) || {}).free === false
                    ? root.t("مدفوع باختيارك: يحاسب المزوّد مفتاحك على كل استخدام.",
                             "Paid by your choice: the provider bills your key for every use.")
                    : ""
                onPicked: index => {
                    var entry = root.providers[index]
                    if (!entry)
                        return
                    root.brainProvider = entry.id
                    modelField.text = String(entry.model || "")
                }
            }
            MoosFactRow {
                label: root.t("العنوان", "Address")
                value: String((root.providerEntry(root.providers, root.brainProvider) || {}).base || "")
                technical: true
            }
            FormCard.FormTextFieldDelegate {
                id: modelField
                label: root.t("النموذج", "Model")
                placeholderText: String((root.providerEntry(root.providers, root.brainProvider) || {}).model
                                        || root.t("اسم النموذج", "Model ID"))
                Accessible.name: label
            }
            FormCard.FormPasswordFieldDelegate {
                id: keyField
                label: root.t("مفتاح API السحابي", "Cloud API key")
                placeholderText: root.keyForThisService
                    ? root.t("المفتاح محفوظ — اتركه فارغاً لإبقائه", "Key saved — leave blank to keep it")
                    : root.t("sk-…  (يُكتب ولا يُقرأ)", "sk-…  (write-only)")
                Accessible.name: label
            }
            MoosNote {
                text: root.keyText()
                bottomPadding: Kirigami.Units.smallSpacing
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "check"
                text: root.brainSaving ? root.t("جارٍ الحفظ…", "Saving…") : root.t("حفظ العقل", "Save the brain")
                description: root.t("يحفظ المزوّد والنموذج، والمفتاح إن كتبته. لا يُعرض المفتاح بعد حفظه.",
                                    "Saves the provider and the model, and the key if you typed one. A saved key is never shown.")
                enabled: root.brainChanged && !root.brainSaving
                onClicked: root.saveBrain()
            }
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            visible: !!root.brainNotice.text
            type: root.brainNotice.tone === "positive" ? Kirigami.MessageType.Positive : Kirigami.MessageType.Error
            text: root.brainNotice.text || ""
        }
        MoosNote {
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            text: root.t("نماذج سحابية فقط. المجاني افتراضي؛ المدفوع باختيارك. قد تنتهي الحصة المجانية.",
                         "Cloud models only. Free by default; paid models require your selection. Free quotas may run out.")
        }

        // ══ Cloud models: the default, and the free-model measurement ═══════════
        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("النماذج السحابية", "Cloud models")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoaiComboRow {
                label: root.t("النموذج الافتراضي", "Default model")
                enabled: root.configReady && root.modelsState === "ready" && root.cloudModels.length > 0
                         && !root.defaultSaving
                options: root.cloudModels.map(function (row) { return root.modelLabel(row) })
                shownIndex: root.indexOfId(root.cloudModels, root.defaultModel)
                description: root.defaultDescription()
                onPicked: index => root.saveDefaultModel(root.cloudModels[index])
            }
            FormCard.FormDelegateSeparator {
                visible: root.savedProvider !== "opencode-zen"
            }
            // Measuring asks the FREE list two questions, so a provider with no free list is
            // not offered a button that could only run for two minutes and fail.
            MoosInfoRow {
                visible: root.savedProvider !== "opencode-zen"
                glyph: "pulse"
                text: root.t("قِس النماذج المجانية على جهازك", "Measure the free models on your machine")
                description: root.measureStarting ? root.t("يبدأ القياس…", "Starting the measurement…")
                                                  : root.measureText(root.measureDoc)
            }
            MoosActionRow {
                visible: root.savedProvider !== "opencode-zen"
                glyph: "refresh"
                text: root.measuring || root.measureStarting ? root.t("جارٍ القياس…", "Measuring…")
                                     : root.t("قِس الآن (دقيقة أو دقيقتان)", "Measure now (a minute or two)")
                description: root.t("يسأل كل نموذج مجاني السؤالين نفسيهما عبر عقل Mo AI، ويرتّب القائمة بما أجاب فعلاً هنا.",
                                    "Asks every free model the same two questions through Mo AI's brain, and orders the list by what actually answered here.")
                enabled: root.configReady && !root.measuring && !root.measureStarting && root.modelsState !== "offline"
                onClicked: root.measureFree()
            }
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            visible: !!root.defaultNotice.text
            type: root.defaultNotice.tone === "positive" ? Kirigami.MessageType.Positive : Kirigami.MessageType.Error
            text: root.defaultNotice.text || ""
        }
        MoosNote {
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            text: root.t("القائمة حسب سياسة المزوّد المحفوظة. لا يتم تنزيل نماذج على الجهاز. تختار كل محادثة عقلها من شريحة العقل في Mo AI.",
                         "Models follow the saved provider policy. Nothing is downloaded to this device. Each conversation can still pick its own brain from the chip in Mo AI.")
        }

        // ══ Your phone ══════════════════════════════════════════════════════════
        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("قنوات الهاتف", "Phone channels")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosInfoRow {
                glyph: "chat"
                text: root.t("وكيل الهاتف", "Phone agent")
                description: root.t("المحرّك الموحّد لسطح المكتب وتليجرام وواتساب؛ نفس الجلسات والذاكرة والأدوات.",
                                    "The shared desktop, Telegram and WhatsApp runtime: one session store, memory and tool policy.")
                trailing: [
                    MoosChip {
                        glyph: !root.capabilitiesKnown ? "help" : root.agentInstalled && root.hasKey ? "check" : "warning"
                        label: !root.capabilitiesKnown ? root.t("غير معروف", "Unknown")
                             : !root.agentInstalled ? root.t("غير مثبّت", "Not installed")
                             : root.hasKey ? root.t("مثبّت ومهيّأ", "Installed and configured")
                             : root.t("يحتاج إعداداً", "Setup required")
                        tone: !root.capabilitiesKnown ? "neutral" : root.agentInstalled && root.hasKey ? "positive" : "warning"
                    }
                ]
            }
            MoosActionRow {
                visible: root.capabilitiesKnown && !root.agentInstalled
                glyph: "install"
                text: root.t("ثبّت وكيل الهاتف", "Install the phone agent")
                description: root.t("يسألك MoOS قبل التثبيت، ويستخدم العقل المحفوظ أعلاه.",
                                    "MoOS asks you first, and it uses the brain saved above.")
                onClicked: root.open("moos://do/install-openclaw")
            }
            FormCard.FormDelegateSeparator {}
            MoosInfoRow {
                glyph: "chat"
                text: "Telegram"
                description: root.t("بوت تليجرام — تكلّمه من جوالك وتكمل نفس المحادثة في Mo AI.",
                                    "Telegram bot — chat from your phone and continue the same conversation in Mo AI.")
                trailing: [
                    MoosChip {
                        visible: root.telegramText(root.channelsDoc.telegram, root.channelsState) !== ""
                        glyph: root.channelsState === "ready" && root.channelsDoc.telegram && root.channelsDoc.telegram.connected
                               ? "check" : "chat"
                        label: root.telegramText(root.channelsDoc.telegram, root.channelsState)
                        tone: root.channelsState === "ready" && root.channelsDoc.telegram && root.channelsDoc.telegram.connected
                              ? "positive" : "neutral"
                    }
                ]
            }
            MoaiSwitchRow {
                enabled: root.configReady && !root.telegramSaving
                glyph: "power"
                text: root.t("مفعّلة", "Enabled")
                description: root.t("يُحفظ مع زر الحفظ أدناه.", "Saved with the Save button below.")
                value: root.telegramDraft
                onToggledTo: wanted => root.telegramDraft = wanted
            }
            FormCard.FormPasswordFieldDelegate {
                id: tokenField
                enabled: root.configReady && !root.telegramSaving
                label: root.t("توكن بوت تليجرام", "Telegram bot token")
                placeholderText: root.hasToken
                    ? root.t("التوكن محفوظ — اتركه فارغاً لإبقائه", "Token saved — leave blank to keep it")
                    : root.t("123456:AA…  من @BotFather", "123456:AA…  from @BotFather")
                Accessible.name: label
            }
            FormCard.FormTextFieldDelegate {
                id: allowField
                enabled: root.configReady && !root.telegramSaving
                label: root.t("معرّفك الرقمي", "Your numeric ID")
                placeholderText: root.t("معرّفك الرقمي — مثال: 123456789", "Your numeric ID — e.g. 123456789")
                Accessible.name: label
            }
            MoosNote {
                text: root.t("المعرّف الرقمي لا اسم المستخدم: الأسماء تُغيَّر ويُعاد تخصيصها، والرقم ثابت. اتركه فارغاً فيعود الوضع إلى الاقتران حتى لا تُقفل خارج بوتك.",
                             "Use the numeric ID, not the username: names change and can be reassigned. Leave it blank to return to pairing mode.")
                bottomPadding: Kirigami.Units.smallSpacing
            }
            MoosActionRow {
                glyph: "check"
                text: root.telegramSaving ? root.t("جارٍ الحفظ…", "Saving…") : root.t("حفظ تليجرام", "Save Telegram")
                description: root.t("يحفظ التشغيل ومن يُسمح له، والتوكن إن كتبته. لا يُعرض التوكن بعد حفظه.",
                                    "Saves whether it is on and who may use it, and the token if you typed one. A saved token is never shown.")
                enabled: root.telegramChanged && !root.telegramSaving
                onClicked: root.saveTelegram()
            }
            FormCard.FormDelegateSeparator {}
            MoosInfoRow {
                glyph: "phone"
                text: "WhatsApp"
                description: root.t("اربط WhatsApp Web عبر OpenClaw؛ يستخدم نفس الوكيل والذاكرة والصلاحيات.",
                                    "Link WhatsApp Web through OpenClaw; it shares this agent, memory and permissions.")
                trailing: [
                    MoosChip {
                        glyph: root.channelsState === "ready" && root.channelsDoc.whatsapp && root.channelsDoc.whatsapp.connected
                               ? "check" : "phone"
                        label: root.whatsappText(root.channelsDoc.whatsapp, root.channelsState)
                        tone: root.channelsState === "ready" && root.channelsDoc.whatsapp && root.channelsDoc.whatsapp.connected
                              ? "positive" : "neutral"
                    }
                ]
            }
            MoosActionRow {
                glyph: "external"
                text: root.channelsState === "ready" && root.channelsDoc.whatsapp && root.channelsDoc.whatsapp.connected
                      ? root.t("إعادة الربط", "Relink") : root.t("ربط WhatsApp", "Link WhatsApp")
                description: root.t("يفتح نافذة تعرض رمز QR لتمسحه من هاتفك.", "Opens a window with a QR code to scan from your phone.")
                enabled: root.agentInstalled
                onClicked: root.open("moos://agent/whatsapp-login")
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "refresh"
                text: root.channelsState === "checking" ? root.t("جارٍ فحص الاتصال…", "Checking connection…")
                                                         : root.t("افحص الاتصال", "Check connection")
                description: root.channelsError !== "" ? root.localPair(root.channelsError)
                    : root.t("يوقظ وكيل الهاتف ليسأل تليجرام وواتساب عن حالتهما الفعلية.",
                             "Wakes the phone agent to ask Telegram and WhatsApp how they really are.")
                enabled: root.agentInstalled && root.channelsState !== "checking"
                onClicked: root.checkChannels()
            }
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            visible: !!root.telegramNotice.text
            type: root.telegramNotice.tone === "positive" ? Kirigami.MessageType.Positive : Kirigami.MessageType.Error
            text: root.telegramNotice.text || ""
        }

        // ══ Permissions ═════════════════════════════════════════════════════════
        // Four tiers, mapped onto the phone agent's OWN enforcement (moai-agent-api's TIERS):
        // read and project stay sandboxed; system and full reach the host, system asking in
        // the chat before every command and full asking nothing. The words are the ones the
        // Mo AI window used, unchanged. The selection is a draft until Save; opening the page
        // writes nothing, so the stored tier — the safe default included — stays what it is.
        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("الصلاحيات", "Permissions")
        }
        MoosNote {
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            text: root.t("كم يتحكّم الوكيل بجهازك فعلياً من تليجرام (كاميرا، برامج، ترمنال، تحديث، تطوير). ابدأ بـ«مع إذن».",
                         "Choose how much Telegram can control on this device. Start with “Ask first”.")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth
            enabled: root.configReady && !root.permissionsSaving

            MoosInfoRow {
                glyph: root.savedTier === "full" ? "danger" : "shield"
                glyphColor: root.savedTier === "full" ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.highlightColor
                text: root.t("تحكّم البوت بجهازك", "Bot device control")
                description: root.hostControlText(root.savedTier)
            }
            FormCard.FormDelegateSeparator {}
            MoaiChoiceRow {
                text: root.t("معطّل — بلا تحكّم", "Disabled — no control")
                description: root.t("يردّ ويحلّل داخل عزل فقط. لا كاميرا ولا برامج ولا ترمنال",
                                    "Replies inside a sandbox; no camera, apps or terminal")
                chosen: root.tierDraft === "read"
                onChoose: root.tierDraft = "read"
            }
            MoaiChoiceRow {
                text: root.t("تعديل المشروع", "Edit project")
                description: root.t("يقرأ ويعدّل ويختبر داخل مجلد المشروع المعزول، بلا وصول للنظام",
                                    "Reads, edits and tests inside the sandboxed project; no system access")
                chosen: root.tierDraft === "project"
                onChoose: root.tierDraft = "project"
            }
            MoaiChoiceRow {
                text: root.t("تحكّم بالنظام — بموافقة", "System control — ask first")
                description: root.t("يتحكّم بالجهاز الحقيقي، لكن يعرض كل أمر وتوافق عليه في تليجرام قبل تنفيذه",
                                    "Can control the device, but every command requires Telegram approval")
                chosen: root.tierDraft === "system"
                onChoose: root.tierDraft = "system"
            }
            MoaiChoiceRow {
                text: root.t("كامل — تحكّم بلا سؤال", "Full — no confirmation")
                description: root.t("ينفّذ أي شيء على جهازك فوراً بلا موافقة. الأقوى والأخطر — لك وحدك",
                                    "Runs immediately without approval. Most powerful and highest risk")
                risky: true
                chosen: root.tierDraft === "full"
                onChoose: root.tierDraft = "full"
            }
            MoosNote {
                visible: root.savedTier === "custom"
                text: root.t("الإعداد الحالي على القرص لا يطابق أي مستوى من الأربعة — اختر مستوى ليُوحَّد.",
                             "The on-disk configuration matches none of the four tiers — pick one to normalise it.")
                bottomPadding: Kirigami.Units.smallSpacing
            }
            FormCard.FormDelegateSeparator {}
            FormCard.FormTextFieldDelegate {
                id: projectField
                label: root.t("مجلد المشروع", "Project folder")
                placeholderText: root.t("مسار مطلق داخل مجلد المنزل (فارغ = بلا نطاق)",
                                        "An absolute path in your home folder (blank = unrestricted)")
                Accessible.name: label
            }
            MoosNote {
                text: root.t("يحصر عمل الوكيل في مجلد واحد. مسار مطلق داخل مجلد المنزل فقط — أي شيء آخر يُرفض.",
                             "Restricts the agent to one absolute path inside your home folder.")
                bottomPadding: Kirigami.Units.smallSpacing
            }
            FormCard.FormDelegateSeparator {}
            MoaiSwitchRow {
                enabled: root.primaryExists
                glyph: "globe"
                text: root.t("الإنترنت: بحث وقراءة صفحات", "Internet: search and read pages")
                description: root.primaryExists ? ""
                    : root.t("احفظ العقل أولاً؛ هذه الصلاحية تُكتب على العقل المحفوظ.",
                             "Save the brain first; this permission is written on the saved brain.")
                value: root.webDraft
                onToggledTo: wanted => root.webDraft = wanted
            }
            MoosNote {
                text: root.t("نموذج صغير ضعيف أمام حقن التعليمات، والبحث المحلي يتطلب تسجيل دخول Ollama — بدون حساب تفشل الأداة ويعلق العقل المحلي عليها. فعّله مع العقل السحابي فقط.",
                             "A small model is vulnerable to prompt injection, and local search needs an Ollama account sign-in — without one the tool always fails and the local brain can loop on it. Enable this with the cloud brain only.")
                bottomPadding: Kirigami.Units.smallSpacing
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "check"
                text: root.permissionsSaving ? root.t("جارٍ الحفظ…", "Saving…") : root.t("حفظ الصلاحيات", "Save permissions")
                description: root.t("يطبّق ما تغيّر فقط، ويعيد تشغيل وكيل الهاتف إن كان يعمل ليأخذ به فوراً.",
                                    "Applies only what changed, and restarts the phone agent if it is running so it takes effect at once.")
                enabled: root.permissionsChanged && !root.permissionsSaving
                onClicked: root.savePermissions()
            }
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            visible: !!root.permissionsNotice.text
            type: root.permissionsNotice.tone === "positive" ? Kirigami.MessageType.Positive : Kirigami.MessageType.Error
            text: root.permissionsNotice.text || ""
        }

        // ══ Reaching Mo AI ══════════════════════════════════════════════════════
        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("الوصول إلى Mo AI", "Reaching Mo AI")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosInfoRow {
                glyph: "keyboard"
                text: root.t("افتح Mo AI من أي مكان", "Open Mo AI from anywhere")
                description: root.t("الاختصار الافتراضي Meta+Space، ويمكنك تغييره.",
                                    "Meta+Space by default, and you can change it.")
                trailing: [
                    MoosKeyCap { keyName: "Meta" },
                    Controls.Label { text: "+"; Accessible.ignored: true },
                    MoosKeyCap { keyName: "Space" }
                ]
            }
            MoosActionRow {
                glyph: "settings"
                text: root.t("غيّر الاختصار", "Change the shortcut")
                description: root.t("في إعدادات الاختصارات، تحت Mo AI.", "In Shortcuts, under Mo AI.")
                onClicked: root.open("moos://settings/shortcuts")
            }
            FormCard.FormDelegateSeparator {}
            MoosInfoRow {
                glyph: "search"
                text: root.t("اسأل Mo AI من البحث", "Ask Mo AI from Search")
                description: root.t("اكتب سؤالك في البحث واختر «اسأل Mo AI»، أو اضغط Ctrl+Enter.",
                                    "Type your question in Search and choose “Ask Mo AI”, or press Ctrl+Enter.")
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "external"
                text: root.t("افتح Mo AI", "Open Mo AI")
                description: root.t("المحادثة، وفحص جهازك، والورشة.", "The chat, your device's check, and the Workbench.")
                onClicked: root.open("moos://app/moai")
            }
            FormCard.FormDelegateSeparator {}
            // Opens Mo AI on its device panel: the verdict on drivers, updates and security
            // from the daily check, each finding with the fixed repair that answers it.
            MoosActionRow {
                glyph: "report"
                text: root.t("افحص هذا الجهاز", "Check this device")
                description: root.t("حكم Mo AI على التعريفات والتحديثات والأمان، ومع كل ملاحظة الإصلاح الذي يناسبها.",
                                    "Mo AI's verdict on drivers, updates and security, each finding with the repair that fits it.")
                onClicked: root.open("moos://do/hw-report")
            }
        }

        // ══ What Mo AI follows ══════════════════════════════════════════════════
        // Mo AI has no look or language of its own any more: it follows MoOS's.
        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("يتبع نظامك", "Follows your system")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosActionRow {
                glyph: "ui"
                text: root.t("ثيمات MoOS", "MoOS Themes")
                description: root.t("يتبع Mo AI ثيم MoOS النشط وحجم الخط وتقليل الحركة.",
                                    "Mo AI follows the active MoOS theme, the font size and reduced motion.")
                onClicked: root.open("moos://settings/themes")
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "globe"
                text: root.t("اللغة والمنطقة", "Language and region")
                description: root.t("يعرض Mo AI لغة النظام، ويجيبك باللغة التي تكتب بها.",
                                    "Mo AI shows the system language, and answers in the language you write in.")
                onClicked: root.open("moos://settings/region")
            }
            // A language chosen for Mo AI alone, before it followed the system, is still in
            // its record. It is not used and not rewritten; the owner is told, once, here.
            MoosInfoRow {
                visible: root.savedLanguage !== ""
                glyph: "about"
                text: root.t("اختيار لغة قديم محفوظ", "An older language choice is saved")
                description: root.t("اخترتَ سابقاً " + (root.savedLanguage === "ar" ? "العربية" : "الإنجليزية")
                                    + " لـ Mo AI وحده. صار Mo AI يتبع لغة النظام ولم يعد يستخدم ذلك الاختيار؛ غيّر لغة النظام من «اللغة والمنطقة».",
                                    "You once chose " + (root.savedLanguage === "ar" ? "Arabic" : "English")
                                    + " for Mo AI alone. Mo AI now follows the system language and no longer uses that choice; change the system language in Language and region.")
            }
        }
    }
}
