// SPDX-License-Identifier: GPL-2.0-or-later
// kcm_moos_appearance — MoOS Themes, the first page of Appearance & Style. It replaces the
// separate MoOS Themes window: the sixteen MoOS looks with their own previews, apply and
// undo, the desktop canvas image, glass clarity and wallpaper motion, and the native pages
// for fine control.
//
// Every change is one fixed verb of the shared backend (kcm.runFixed), which runs
// /usr/bin/moos-theme — the one owner of a MoOS look. moos-theme carries each change as a
// transaction: it snapshots the desktop, applies, verifies every supplement it owns (GTK,
// Konsole, the lock screen, the desktop scene), and restores the snapshot when anything
// does not read back. This page adds the second half: it calls a change done only after
// moos-theme exited 0 AND a fresh read of the desktop says what was asked for.
//
// The page's own watchdog never stops a change. What it cannot promise is the process's
// lifetime: a verb's process belongs to the module, so a change is stopped mid-way when
// the page itself goes away (another page or module opened, the window closed) and when
// the backend's own ceiling for a verb runs out. moos-theme cannot roll back from that. So
// while a change runs the page opens nothing else, and — unless the backend says its
// changes outlive the page (changesOutlivePage) — asks the person to keep it open.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import org.kde.kirigamiaddons.formcard as FormCard
import org.moos.ui as MoUI
import "ThemeLogic.js" as Logic

KCM.SimpleKCM {
    id: root

    readonly property bool rtl: MoUI.Locale.rtl
    readonly property var design: MoUI.Tokens
    readonly property real cardWidth: Kirigami.Units.gridUnit * 44
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)
    // The installed MoOS looks, read once from their packages (the backend lists them;
    // a settings page cannot read local files itself).
    readonly property var looks: kcm.moosThemes()

    // What the desktop wears, as moos-theme last REPORTED it. Nothing here is ever set
    // from a click: a card is marked only after a read says so.
    property string lookKind: "reading"        // reading | moos | unset | foreign | unknown
    property string currentLook: ""
    property string currentMotion: ""
    property bool motionReadable: true
    property string currentClarity: ""
    readonly property var currentEntry: entryFor(currentLook)

    // One change at a time, as moos-theme itself allows.
    property string operation: ""              // apply | undo | canvas | canvas-reset | motion | clarity
    property string expected: ""               // the look, motion or clarity the change must produce
    property string phase: ""                  // changing | verifying
    property bool late: false
    property QtObject mutation: null
    property QtObject readback: null
    readonly property bool busy: operation !== ""
    readonly property int watchdogMs: 30000
    // True only once the backend runs a change outside this page's lifetime and says so;
    // until then leaving the page stops the change, and the page says that while it runs.
    readonly property bool changesOutlivePage: kcm.changesOutlivePage === true
    readonly property string stayNote: changesOutlivePage ? ""
        : t(" أبقِ هذه الصفحة مفتوحة حتى ينتهي.", " Keep this page open until it finishes.")

    property string notice: ""
    property int noticeType: Kirigami.MessageType.Information
    property string noticeDetail: ""
    property string routeError: ""

    function t(ar, en) { return rtl ? ar : en }

    function entryFor(id) {
        for (var i = 0; i < looks.length; ++i) {
            if (looks[i].id === id)
                return looks[i]
        }
        return null
    }
    function lookName(id) {
        var entry = entryFor(id)
        if (!entry)
            return t("مظهر MoOS", "a MoOS look")
        return rtl ? (entry.nameAr || entry.name) : entry.name
    }
    function motionName(value) {
        return value === "still" ? t("ساكن", "Still")
             : value === "gentle" ? t("هادئ", "Gentle")
             : value === "alive" ? t("حيّ", "Alive") : ""
    }
    function clarityName(value) {
        return value === "clear" ? t("شفاف", "Clear")
             : value === "balanced" ? t("متوازن", "Balanced")
             : value === "solid" ? t("صلب", "Solid") : ""
    }
    // Opening another page replaces this one, and that stops a change still running.
    function open(route) {
        if (busy)
            return
        routeError = kcm.openRoute(route) ? "" : t("تعذّر فتح هذه الصفحة. حاول مرة أخرى.",
                                                    "Could not open that page. Try again.")
    }
    // A native page is offered unless the device status measured that it is not installed.
    function nativeAvailable(token) {
        return !kcm.statusValid || (kcm.status.destinations || {})[token] !== false
    }

    // ── Reading the desktop ──────────────────────────────────────────────────────────
    function whenDone(job, handler) {
        if (!job)
            return false
        if (job.running)
            job.finished.connect(function() { handler(job) })
        else
            Qt.callLater(handler, job)
        return true
    }
    function showLook(job) {
        var state = Logic.lookState(job.output, job.ok)
        lookKind = state.kind
        currentLook = state.id
    }
    function showMotion(job) {
        currentMotion = Logic.reportedChoice(job.output, job.ok, Logic.MOTIONS)
        motionReadable = currentMotion !== ""
    }
    function showClarity(job) {
        currentClarity = Logic.reportedChoice(job.output, job.ok, Logic.CLARITIES)
    }
    // Read-only queries, never while a change runs: a change reads its own result back.
    function measure() {
        if (busy)
            return
        if (!whenDone(kcm.runFixed("theme-status"), function(job) { if (!root.busy) root.showLook(job) }))
            lookKind = "unknown"
        whenDone(kcm.runFixed("theme-motion-status"), function(job) { if (!root.busy) root.showMotion(job) })
        whenDone(kcm.runFixed("theme-clarity-status"), function(job) { if (!root.busy) root.showClarity(job) })
    }

    // ── Changing it ──────────────────────────────────────────────────────────────────
    function applyLook(id) {
        if (busy || !Logic.isLook(id) || !entryFor(id))
            return
        begin("apply", kcm.runFixed("theme-apply-lnf", id), id)
    }
    function undo() {
        if (busy)
            return
        begin("undo", kcm.runFixed("theme-undo"), "")
    }
    function chooseCanvas(fileUrl) {
        if (busy)
            return
        var token = Logic.wallpaperToken(fileUrl)
        if (token === "") {
            report(Kirigami.MessageType.Error,
                   t("اختر صورة محفوظة على هذا الحاسوب.", "Choose an image saved on this computer."), "")
            return
        }
        begin("canvas", kcm.runFixed("theme-wallpaper-token", token), currentLook)
    }
    function resetCanvas() {
        if (busy)
            return
        begin("canvas-reset", kcm.runFixed("theme-wallpaper-reset"), currentLook)
    }
    function setMotion(value) {
        if (busy || Logic.MOTIONS.indexOf(value) < 0 || value === currentMotion)
            return
        begin("motion", kcm.runFixed("theme-motion", value), value)
    }
    function setClarity(value) {
        if (busy || Logic.CLARITIES.indexOf(value) < 0 || value === currentClarity)
            return
        begin("clarity", kcm.runFixed("theme-clarity", value), value)
    }

    function begin(kind, job, expectedValue) {
        if (!job) {
            report(Kirigami.MessageType.Error, t("رفض MoOS هذا الطلب.", "MoOS refused that request."), "")
            return
        }
        operation = kind
        expected = expectedValue
        phase = "changing"
        late = false
        mutation = job
        report(Kirigami.MessageType.Information, progressText() + stayNote, "")
        watchdog.restart()
        whenDone(job, root.mutationEnded)
    }
    // moos-theme has exited. A failure is reported; a success is only provisional until
    // the desktop is read back.
    function mutationEnded(job) {
        if (job !== mutation)
            return
        mutation = null
        watchdog.stop()
        if (!job.ok) {
            finish(Kirigami.MessageType.Error, failureText(Logic.failureKind(job.exitCode, job.errorOutput)),
                   Logic.detail(job.errorOutput, job.output))
            return
        }
        phase = "verifying"
        watchdog.restart()
        var probe = operation === "motion" ? kcm.runFixed("theme-motion-status")
                  : operation === "clarity" ? kcm.runFixed("theme-clarity-status")
                  : kcm.runFixed("theme-status")
        readback = probe
        if (!whenDone(probe, root.readbackEnded)) {
            readback = null
            finish(Kirigami.MessageType.Error, t("تم التغيير لكن تعذّر التحقق منه.",
                                                 "The change ran, but it could not be checked."), "")
        }
    }
    function readbackEnded(job) {
        if (job !== readback)
            return
        readback = null
        watchdog.stop()
        if (!job.ok) {
            finish(Kirigami.MessageType.Error, t("تم التغيير لكن تعذّر التحقق منه.",
                                                 "The change ran, but it could not be checked."),
                   Logic.detail(job.errorOutput, job.output))
            return
        }
        var differs = false
        if (operation === "motion") {
            showMotion(job)
            differs = currentMotion !== expected
        } else if (operation === "clarity") {
            showClarity(job)
            differs = currentClarity !== expected
        } else if (operation === "undo") {
            // Undo restores the exact earlier state, which may be a look from outside MoOS.
            showLook(job)
            differs = lookKind === "unknown"
        } else {
            showLook(job)
            differs = lookKind !== "moos" || currentLook !== expected
        }
        if (differs) {
            finish(Kirigami.MessageType.Error, t("انتهى التغيير لكن سطح المكتب لا يُظهر ما طلبته.",
                                                 "The change finished, but the desktop does not show what you asked for."), "")
            return
        }
        finish(Kirigami.MessageType.Positive, (late ? t("اكتمل بعد انتظار أطول: ", "Finished after a longer wait: ") : "")
                                              + successText(), "")
    }
    function finish(type, text, detail) {
        operation = ""
        expected = ""
        phase = ""
        late = false
        report(type, text, detail)
        // A new look brings its own scene and material, and a failed change may have been
        // rolled back: read everything once more rather than trust what was shown.
        measure()
    }
    function report(type, text, detail) {
        noticeType = type
        notice = text
        noticeDetail = detail
    }

    function progressText() {
        switch (operation) {
        case "apply": return t("جارٍ تطبيق ", "Applying ") + lookName(expected) + "…"
        case "undo": return t("جارٍ العودة إلى المظهر السابق…", "Going back to the previous look…")
        case "canvas": return t("جارٍ وضع الصورة على مساحة العمل…", "Placing your image on the desktop canvas…")
        case "canvas-reset": return t("جارٍ استعادة خلفية المظهر…", "Bringing back the look's own wallpaper…")
        case "motion": return t("جارٍ ضبط حركة الخلفية…", "Setting wallpaper motion…")
        case "clarity": return t("جارٍ ضبط وضوح الزجاج…", "Setting glass clarity…")
        }
        return ""
    }
    function successText() {
        switch (operation) {
        case "apply": return t("تم تطبيق ", "Applied ") + lookName(expected) + t(" وتم التحقق منه", " and verified")
        case "undo": return t("عاد المظهر السابق وتم التحقق منه", "The previous look is back and verified")
        case "canvas": return t("تم تحديث مساحة العمل والتحقق منها", "Desktop canvas updated and verified")
        case "canvas-reset": return t("عادت خلفية المظهر وتم التحقق منها", "The look's own wallpaper is back and verified")
        case "motion": return t("حركة الخلفية الآن: ", "Wallpaper motion is now ") + motionName(expected)
        case "clarity": return t("وضوح الزجاج الآن: ", "Glass clarity is now ") + clarityName(expected)
        }
        return ""
    }
    function failureText(kind) {
        switch (kind) {
        case "rollback-failed":
            return t("لم يكتمل التغيير، ولم يكتمل إرجاع المظهر السابق. طبّق مظهراً من جديد.",
                     "The change did not complete, and the previous look could not be fully restored. Apply a look again.")
        case "rolled-back":
            return t("لم يكتمل التغيير، فأعاد MoOS المظهر السابق كما كان تماماً.",
                     "The change did not complete, so MoOS put the previous look back exactly as it was.")
        case "busy":
            return t("تغيير آخر في المظهر ما زال يعمل. حاول بعد لحظات.",
                     "Another appearance change is still running. Try again in a moment.")
        case "no-undo":
            return t("لا يوجد مظهر سابق للعودة إليه بعد.", "There is no earlier look to go back to yet.")
        case "not-moos":
            return t("اختر مظهر MoOS أولاً، ثم غيّر صورة مساحة العمل.",
                     "Choose a MoOS look first, then change its desktop canvas.")
        case "missing":
            return t("هذا المظهر غير مثبت على هذا النظام.", "That look is not installed on this system.")
        case "no-tool":
            return t("تعذّر تشغيل أداة المظاهر في MoOS.", "MoOS could not start its theme tool.")
        case "stopped":
            // Stopped from outside, moos-theme could not put the earlier look back.
            return t("استغرق التغيير وقتاً طويلاً جداً فتوقف قبل أن يكتمل. طبّق مظهراً من جديد.",
                     "The change took far too long and was stopped before it finished. Apply a look again.")
        }
        switch (operation) {
        case "apply": return t("تعذّر تطبيق المظهر.", "The look could not be applied.")
        case "undo": return t("لم يكتمل التراجع.", "Undo did not complete.")
        case "canvas": return t("تعذّر وضع الصورة على مساحة العمل.", "The image could not be placed on the desktop canvas.")
        case "canvas-reset": return t("تعذّرت استعادة خلفية المظهر.", "The look's own wallpaper could not be brought back.")
        case "motion": return t("تعذّر تغيير حركة الخلفية.", "Wallpaper motion could not be changed.")
        case "clarity": return t("تعذّر تغيير وضوح الزجاج.", "Glass clarity could not be changed.")
        }
        return t("تعذّر إكمال التغيير.", "The change could not be completed.")
    }

    readonly property string heroSubtitle: {
        if (lookKind === "moos")
            return t("المظهر الحالي: ", "Current look: ") + lookName(currentLook)
        if (lookKind === "reading")
            return t("جارٍ قراءة المظهر الحالي…", "Reading the current look…")
        if (lookKind === "unset")
            return t("لم يُختر مظهر بعد — المظهر الافتراضي هو MoOS UI.", "No look chosen yet — MoOS UI is the default.")
        if (lookKind === "foreign")
            return t("سطح المكتب يستخدم مظهراً من خارج MoOS.", "The desktop is wearing a look from outside MoOS.")
        return t("تعذّرت قراءة المظهر الحالي.", "The current look could not be read.")
    }
    readonly property string heroSummary: currentEntry ? (rtl ? currentEntry.summaryAr : currentEntry.summaryEn)
                                                       : t("اختر مظهراً، ثم صورة مساحة العمل ووضوح الزجاج وحركة الخلفية.",
                                                           "Pick a look, then its desktop canvas, glass clarity and wallpaper motion.")

    // This watchdog never stops moos-theme: an interrupted transaction could leave half of
    // two looks. The page says it is taking longer, keeps every other change and page
    // locked, and still reads the result when it arrives. (The backend's own ceiling for a
    // verb is separate; when it stops one, the job ends as "stopped" and the page says so.)
    // A read-back is only a query, so a late one is let go.
    Timer {
        id: watchdog
        interval: root.watchdogMs
        onTriggered: {
            if (root.phase === "changing") {
                root.late = true
                root.report(Kirigami.MessageType.Information,
                            root.t("ما زال التغيير يعمل ويستغرق وقتاً أطول من المعتاد.",
                                   "The change is still running and taking longer than usual.")
                            + root.stayNote, "")
            } else if (root.phase === "verifying") {
                root.readback = null
                root.finish(Kirigami.MessageType.Error,
                            root.t("انتهت مهلة التحقق.", "Checking the result timed out."), "")
            }
        }
    }

    FileDialog {
        id: canvasDialog
        title: root.t("اختر صورة لمساحة العمل", "Choose a desktop canvas image")
        fileMode: FileDialog.OpenFile
        nameFilters: [root.t("الصور (*.png *.jpg *.jpeg *.webp *.avif)", "Images (*.png *.jpg *.jpeg *.webp *.avif)")]
        onAccepted: root.chooseCanvas(selectedFile)
    }

    // A TextEdit is the clipboard a QML page has.
    TextEdit { id: clipboard; visible: false; Accessible.ignored: true }

    LayoutMirroring.enabled: rtl
    LayoutMirroring.childrenInherit: true
    Component.onCompleted: root.measure()
    onVisibleChanged: if (visible) root.measure()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        MoosRouteNotice {
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            message: root.routeError
        }

        // ── The hero: the look the desktop wears, as moos-theme reported it ─────────────
        MoUI.GlassSurface {
            id: hero
            readonly property bool wide: width > Kirigami.Units.gridUnit * 30

            Layout.fillWidth: true
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            implicitHeight: heroGrid.implicitHeight + MoUI.Tokens.space5 * 2
            floating: true
            depth: MoUI.Tokens.glassLevelDialog
            surfaceColor: Kirigami.Theme.backgroundColor
            inkColor: Kirigami.Theme.textColor
            accentColor: Kirigami.Theme.highlightColor
            Accessible.role: Accessible.Grouping
            Accessible.name: root.t("ثيمات MoOS", "MoOS Themes") + " — " + root.heroSubtitle

            // The active palette's accent, washed in from the trailing edge.
            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                opacity: 0.9
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: root.rtl ? 1.0 : 0.0; color: "transparent" }
                    GradientStop { position: root.rtl ? 0.0 : 1.0; color: Qt.alpha(Kirigami.Theme.highlightColor, 0.12) }
                }
            }

            GridLayout {
                id: heroGrid
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: MoUI.Tokens.space5
                columns: hero.wide ? 3 : 1
                columnSpacing: MoUI.Tokens.space5
                rowSpacing: MoUI.Tokens.space4

                Item {
                    Layout.preferredWidth: hero.wide ? Kirigami.Units.gridUnit * 12 : Math.min(heroGrid.width, Kirigami.Units.gridUnit * 18)
                    Layout.preferredHeight: Math.round(Layout.preferredWidth * 9 / 16)
                    Layout.alignment: Qt.AlignVCenter

                    // The current look as a screen in a bezel. A plain Image on purpose:
                    // measured offscreen on Qt's software scene graph (the one the ARM
                    // edition runs), a ShadowedImage here stayed blank while the same
                    // element drew inside the look grid.
                    Rectangle {
                        anchors.fill: parent
                        radius: MoUI.Tokens.radiusControl
                        color: Qt.alpha(Kirigami.Theme.textColor, 0.10)
                        border.width: MoUI.Tokens.borderHairline
                        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.22)
                    }
                    Image {
                        id: heroPreview
                        anchors.fill: parent
                        anchors.margins: MoUI.Tokens.space1 + MoUI.Tokens.borderHairline
                        source: root.currentEntry ? root.currentEntry.preview : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        mipmap: true
                        clip: true
                        sourceSize: Qt.size(Math.max(64, Math.round(width * Screen.devicePixelRatio)),
                                            Math.max(36, Math.round(height * Screen.devicePixelRatio)))
                        Accessible.ignored: true
                    }
                    MoUI.SymbolIcon {
                        anchors.centerIn: parent
                        visible: heroPreview.status !== Image.Ready
                        symbol: MoUI.SymbolCatalog.resolve("ui")
                        foreground: root.secondaryInk
                        implicitWidth: MoUI.Tokens.iconHero
                        implicitHeight: MoUI.Tokens.iconHero
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                    spacing: MoUI.Tokens.space2

                    Kirigami.Heading {
                        Layout.fillWidth: true
                        text: root.t("ثيمات MoOS", "MoOS Themes")
                        level: 1
                        font.weight: Font.Bold
                        horizontalAlignment: Text.AlignLeft
                        wrapMode: Text.WordWrap
                    }
                    Controls.Label {
                        Layout.fillWidth: true
                        text: root.heroSubtitle
                        textFormat: Text.PlainText
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignLeft
                        wrapMode: Text.WordWrap
                    }
                    Controls.Label {
                        Layout.fillWidth: true
                        visible: text !== ""
                        text: root.heroSummary
                        textFormat: Text.PlainText
                        color: root.secondaryInk
                        horizontalAlignment: Text.AlignLeft
                        wrapMode: Text.WordWrap
                    }
                    Flow {
                        Layout.fillWidth: true
                        Layout.topMargin: MoUI.Tokens.space1
                        spacing: MoUI.Tokens.space2

                        MoosChip {
                            visible: root.busy
                            glyph: "refresh"
                            label: root.late ? root.t("ما زال يعمل…", "Still finishing…")
                                 : root.phase === "verifying" ? root.t("جارٍ التحقق…", "Checking…")
                                 : root.t("جارٍ التطبيق…", "Applying…")
                            tone: "neutral"
                        }
                        MoosChip {
                            visible: root.currentEntry !== null
                            glyph: root.currentEntry && root.currentEntry.light ? "sun" : "moon"
                            label: root.currentEntry && root.currentEntry.light ? root.t("فاتح", "Light") : root.t("داكن", "Dark")
                            tone: "neutral"
                        }
                        MoosChip {
                            visible: root.currentClarity !== ""
                            glyph: "diamond"
                            label: root.t("الزجاج: ", "Glass: ") + root.clarityName(root.currentClarity)
                            tone: "neutral"
                        }
                        MoosChip {
                            visible: root.currentMotion !== ""
                            glyph: "wave"
                            label: root.t("الحركة: ", "Motion: ") + root.motionName(root.currentMotion)
                            tone: "neutral"
                        }
                    }
                }

                ColumnLayout {
                    Layout.alignment: hero.wide ? Qt.AlignVCenter : Qt.AlignLeft
                    spacing: MoUI.Tokens.space2

                    Controls.Button {
                        Layout.fillWidth: true
                        text: root.t("تراجع", "Undo")
                        icon.name: MoUI.SymbolCatalog.resolve(root.rtl ? "arrow" : "arrow-back")
                        enabled: !root.busy
                        Accessible.description: root.t("يعيد المظهر الذي كان قبل آخر تغيير، كما كان تماماً",
                                                       "Puts back the look from before the last change, exactly as it was")
                        onClicked: root.undo()
                    }
                }
            }
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            visible: root.notice !== ""
            text: root.notice
            type: root.noticeType
            actions: [
                Kirigami.Action {
                    text: root.t("نسخ التفاصيل", "Copy details")
                    icon.name: MoUI.SymbolCatalog.resolve("copy")
                    visible: root.noticeDetail !== ""
                    onTriggered: {
                        clipboard.text = root.noticeDetail
                        clipboard.selectAll()
                        clipboard.copy()
                        clipboard.deselect()
                    }
                },
                Kirigami.Action {
                    text: root.t("إغلاق", "Dismiss")
                    icon.name: MoUI.SymbolCatalog.resolve("close")
                    visible: !root.busy
                    onTriggered: root.report(Kirigami.MessageType.Information, "", "")
                }
            ]
        }

        // ── The looks ──────────────────────────────────────────────────────────────────
        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("المظاهر", "Looks")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosInfoRow {
                visible: root.looks.length === 0
                glyph: "warning"
                glyphColor: Kirigami.Theme.neutralTextColor
                text: root.t("لم يُعثر على مظاهر MoOS على هذا النظام", "No MoOS looks were found on this system")
                description: root.t("المظاهر جزء من صورة النظام؛ تحديث MoOS يعيدها.",
                                    "The looks are part of the system image; a MoOS update brings them back.")
            }

            Item {
                id: lookArea
                visible: root.looks.length > 0
                Layout.fillWidth: true
                implicitHeight: lookGrid.implicitHeight + MoUI.Tokens.space4 * 2

                // Arrow keys walk the grid, mirrored in Arabic; Tab walks it too.
                function step(from, delta) {
                    var target = from + delta
                    if (target < 0 || target >= lookRepeater.count)
                        return
                    var next = lookRepeater.itemAt(target)
                    if (next)
                        next.forceActiveFocus(Qt.TabFocusReason)
                }

                GridLayout {
                    id: lookGrid
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: MoUI.Tokens.space4
                    columns: Logic.columns(width, Kirigami.Units.gridUnit * 9)
                    columnSpacing: MoUI.Tokens.space3
                    rowSpacing: MoUI.Tokens.space3
                    uniformCellWidths: true

                    Repeater {
                        id: lookRepeater
                        model: root.looks

                        delegate: ThemeCard {
                            id: lookCard
                            required property var modelData
                            required property int index

                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            look: lookCard.modelData
                            active: root.lookKind === "moos" && root.currentLook === lookCard.modelData.id
                            pending: root.operation === "apply" && root.expected === lookCard.modelData.id
                            enabled: !root.busy
                            onClicked: root.applyLook(lookCard.modelData.id)
                            Keys.onPressed: event => {
                                var delta = 0
                                if (event.key === Qt.Key_Left)
                                    delta = root.rtl ? 1 : -1
                                else if (event.key === Qt.Key_Right)
                                    delta = root.rtl ? -1 : 1
                                else if (event.key === Qt.Key_Up)
                                    delta = -lookGrid.columns
                                else if (event.key === Qt.Key_Down)
                                    delta = lookGrid.columns
                                else
                                    return
                                event.accepted = true
                                lookArea.step(lookCard.index, delta)
                            }
                        }
                    }
                }
            }
        }

        // ── The desktop canvas ─────────────────────────────────────────────────────────
        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("مساحة العمل", "Desktop canvas")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosActionRow {
                glyph: "image"
                text: root.t("ضع صورتك", "Use your own image")
                description: root.t("اختر صورة من هذا الحاسوب؛ يبقى المظهر وألوانه كما هي.",
                                    "Pick an image from this computer; the look and its colours stay as they are.")
                enabled: !root.busy && root.lookKind === "moos"
                onClicked: canvasDialog.open()
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "refresh"
                text: root.t("خلفية المظهر الأصلية", "The look's own wallpaper")
                description: root.t("يعيد الخلفية التي صُمّمت مع المظهر الحالي.",
                                    "Brings back the wallpaper designed with the current look.")
                enabled: !root.busy && root.lookKind === "moos"
                onClicked: root.resetCanvas()
            }
        }

        // ── Glass and motion ───────────────────────────────────────────────────────────
        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("الزجاج والحركة", "Glass and motion")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            ChoiceRow {
                glyph: "diamond"
                text: root.t("وضوح الزجاج", "Glass clarity")
                description: root.design.blurActive
                    ? root.t("من شفاف إلى صلب — لكل واجهات MoOS.", "Clear to solid — across every MoOS surface.")
                    : root.t("صلب تلقائياً لأن الشفافية مخفّضة على هذا الجهاز.",
                             "Solid automatically while transparency is reduced on this device.")
                options: [
                    { value: "clear", label: root.t("شفاف", "Clear") },
                    { value: "balanced", label: root.t("متوازن", "Balanced") },
                    { value: "solid", label: root.t("صلب", "Solid") }
                ]
                current: root.currentClarity
                requestedValue: root.operation === "clarity" ? root.expected : ""
                enabled: !root.busy
                onPicked: value => root.setClarity(value)
            }
            FormCard.FormDelegateSeparator {}
            ChoiceRow {
                glyph: "wave"
                text: root.t("حركة الخلفية", "Wallpaper motion")
                description: root.motionReadable
                    ? root.t("اختر مستوى الهدوء والحيوية لخلفية MoOS الحية.",
                             "How calm or lively the MoOS live wallpaper is.")
                    : root.t("تعذّرت قراءة حركة الخلفية؛ تعمل مع خلفية MoOS الحية فقط.",
                             "Wallpaper motion could not be read; it works with the MoOS live wallpaper only.")
                options: [
                    { value: "still", label: root.t("ساكن", "Still") },
                    { value: "gentle", label: root.t("هادئ", "Gentle") },
                    { value: "alive", label: root.t("حيّ", "Alive") }
                ]
                current: root.currentMotion
                requestedValue: root.operation === "motion" ? root.expected : ""
                enabled: !root.busy
                onPicked: value => root.setMotion(value)
            }
        }

        // ── Fine control, on the system's own pages ────────────────────────────────────
        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("ضبط دقيق", "Fine control")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosActionRow {
                glyph: "ui"
                text: root.t("السمة العامة", "Global theme")
                description: root.t("كل السمات المثبتة، ومنها سمات MoOS.", "Every installed theme, MoOS's included.")
                enabled: !root.busy && root.nativeAvailable("global-theme")
                onClicked: root.open("moos://settings/global-theme")
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "gem"
                text: root.t("الألوان", "Colors")
                description: root.t("مخطط الألوان ولون التمييز.", "The colour scheme and the accent colour.")
                enabled: !root.busy && root.nativeAvailable("colors")
                onClicked: root.open("moos://settings/colors")
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "grid"
                text: root.t("الأيقونات", "Icons")
                description: root.t("سمة الأيقونات وأحجامها.", "The icon theme and icon sizes.")
                enabled: !root.busy && root.nativeAvailable("icons")
                onClicked: root.open("moos://settings/icons")
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "mouse"
                text: root.t("المؤشر", "Cursors")
                description: root.t("شكل المؤشر وحجمه.", "The pointer's shape and size.")
                enabled: !root.busy && root.nativeAvailable("cursors")
                onClicked: root.open("moos://settings/cursors")
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "system"
                text: root.t("إطار النوافذ", "Window decorations")
                description: root.t("شريط عنوان النوافذ وأزراره.", "Window title bars and their buttons.")
                enabled: !root.busy && root.nativeAvailable("window-decoration")
                onClicked: root.open("moos://settings/window-decoration")
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "document"
                text: root.t("الخطوط", "Fonts")
                description: root.t("خطوط الواجهة والنصوص وأحجامها.", "Interface and text fonts, and their sizes.")
                enabled: !root.busy && root.nativeAvailable("fonts")
                onClicked: root.open("moos://settings/fonts")
            }
        }
    }
}
