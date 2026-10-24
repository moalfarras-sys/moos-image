// SPDX-License-Identifier: GPL-2.0-or-later
// kcm_moos — MoOS and this device: what is installed, whether it is the image MoOS
// signed, and the machine it runs on. Every fact is a field of the status document
// moos-settings-status publishes; identity values (kernel, edition, architecture,
// session) arrive already normalised and are bound as labels, never raw.
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
    // Every group is read straight from the backend, which holds either a whole
    // accepted document or nothing: a binding never meets half of one.
    readonly property bool ready: kcm.statusValid
    readonly property var deployment: kcm.status.deployment || ({})
    readonly property var updateRecord: kcm.status.update || ({})
    readonly property var remote: kcm.status.remote || ({})
    readonly property var whatsNew: kcm.status.whatsNew || ({})
    readonly property var memory: kcm.status.memory || ({})
    readonly property var storage: kcm.status.storage || ({})
    readonly property var network: kcm.status.network || ({})
    readonly property var bluetooth: kcm.status.bluetooth || ({})
    readonly property var battery: kcm.status.battery || ({})
    readonly property real cardWidth: Kirigami.Units.gridUnit * 56
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)
    readonly property string unknownLabel: t("غير معروف", "Unknown")
    // The MoOS modules themselves: always there, whatever the status feed says.
    readonly property var ownPages: ["overview", "about", "update", "whats-new", "remote",
                                     "recovery", "assistant", "appearance", "themes", "wallpaper"]
    property string routeError: ""

    function t(ar, en) { return rtl ? ar : en }
    function label(pair) { return pair ? t(pair.ar || "", pair.en || "") : "" }
    // A field of the status document as text: "" for anything that is not a string.
    function text(value) { return typeof value === "string" ? value : "" }
    function isolated(value) { return "\u2068" + text(value) + "\u2069" }

    function routeAvailable(route) {
        var text = String(route)
        if (text.indexOf("moos://settings/") !== 0)
            return false
        var token = text.substring(16)
        return ownPages.indexOf(token) >= 0 || (ready && (kcm.status.destinations || {})[token] === true)
    }
    function open(route) {
        routeError = kcm.openRoute(route) ? "" : t("تعذّر فتح هذه الصفحة. حاول مرة أخرى.",
                                                    "Could not open that page. Try again.")
    }

    // Day and year in digits, the month in words, in the page's language.
    function builtLabel(epoch) {
        if (!(epoch > 0))
            return ""
        var date = new Date(epoch * 1000)
        return date.getDate() + " " + Qt.locale().monthName(date.getMonth(), Locale.LongFormat)
               + " " + date.getFullYear()
    }

    readonly property string versionText: ready && deployment.known ? "MoOS " + text(deployment.version) : ""
    readonly property string editionText: ready ? label(kcm.status.editionLabel) : ""
    readonly property string signatureText: !ready || !deployment.known
        ? t("حالة التوقيع غير معروفة", "Signature status unknown")
        : deployment.signed ? t("صورة نظام موقّعة", "Signed system image")
        : t("صورة نظام غير موثّقة", "Unverified system image")
    readonly property string signatureTone: !ready || !deployment.known ? "neutral"
        : deployment.signed ? "positive" : "warning"

    function updateSummary() {
        if (!ready)
            return { tone: "neutral", glyph: "safe-update", text: t("حالة التحديث غير معروفة", "Update status unknown") }
        if (updateRecord.known && updateRecord.state === "busy")
            return { tone: "neutral", glyph: "refresh", text: t("التحديث قيد التنفيذ", "Update in progress") }
        if (updateRecord.known && updateRecord.state === "replace-staged")
            return { tone: "warning", glyph: "safe-update", text: t("إصدار تصحيحي جاهز", "A corrective release is ready") }
        if (updateRecord.known && updateRecord.state === "blocked-downgrade")
            return { tone: "warning", glyph: "shield", text: t("تم منع إصدار أقدم", "An older release was blocked") }
        if (deployment.staged)
            return { tone: "positive", glyph: "safe-update", text: t("جاهز لإعادة التشغيل", "Ready to restart") }
        if (!updateRecord.known)
            return { tone: "neutral", glyph: "safe-update", text: t("لم يتم الفحص مؤخراً", "No recent check") }
        if (updateRecord.state === "current")
            return { tone: "positive", glyph: "check", text: t("MoOS محدّث", "MoOS is up to date") }
        if (updateRecord.state === "available")
            return { tone: "warning", glyph: "download", text: t("يتوفر تحديث موقّع", "Signed update available") }
        return { tone: "neutral", glyph: "safe-update", text: t("راجع التحديث", "Review the update") }
    }
    readonly property var updateState: updateSummary()

    readonly property string remoteText: !ready ? unknownLabel
        : !remote.available ? t("غير مثبت على هذا الجهاز", "Not installed on this device")
        : remote.failed ? t("توقفت الخدمة بخطأ", "Stopped with an error")
        : remote.active ? t("جاهز لاتصال من هاتفك", "Ready for your phone")
        : remote.enabled ? t("سيبدأ مع الجلسة", "Starts with your session")
        : t("متوقف", "Off")
    readonly property string rollbackText: !ready || !deployment.known ? unknownLabel
        : deployment.rollbackQueued ? t("الرجوع مجدول لإعادة التشغيل القادمة", "Rollback queued for the next restart")
        : deployment.rollback > 0 ? t("نسخة سابقة محفوظة", "A previous version is saved")
        : t("لا توجد نسخة سابقة بعد", "No previous version saved yet")

    readonly property string networkText: !ready || !network.known ? unknownLabel
        : network.connectivity === "portal" ? t("يلزم تسجيل الدخول", "Sign-in required")
        : !network.connected ? t("غير متصل", "Disconnected")
        : network.connectivity === "full" ? t("متصل بالإنترنت", "Online")
        : t("اتصال محدود", "Limited connection")
    readonly property string batteryText: !ready ? unknownLabel
        : !battery.available ? t("غير متاحة", "Unavailable")
        : Number(battery.percent).toLocaleString(Qt.locale(), "f", 0) + "%"
    readonly property string batteryDetail: !ready || !battery.available
        ? t("الأداء والسكون وتوفير الطاقة", "Performance, sleep and power saving")
        : battery.state === "charging" ? t("جارٍ الشحن", "Charging")
        : battery.state === "discharging" ? t("يعمل على البطارية", "On battery")
        : battery.state === "full" ? t("مكتملة الشحن", "Fully charged")
        : battery.state === "not charging" ? t("الشحن متوقف", "Not charging") : unknownLabel
    readonly property int freshCount: ready ? (whatsNew.fresh || 0) : 0
    readonly property string freshText: {
        var count = freshCount
        if (!rtl)
            return count === 1 ? "1 new thing since your last update" : count + " new things since your last update"
        if (count === 1) return "تغيير واحد جديد منذ آخر تحديث"
        if (count === 2) return "تغييران جديدان منذ آخر تحديث"
        return count + (count <= 10 ? " تغييرات جديدة" : " تغييرًا جديدًا") + " منذ آخر تحديث"
    }

    // What "Copy details" puts on the clipboard: the facts the page shows, in the page's
    // language, one per line, for a support conversation.
    function aboutReport() {
        var lines = [versionText || "MoOS"]
        function add(name, value) { if (value) lines.push(name + ": " + value) }
        add(t("الإصدارة", "Edition"), editionText)
        add(t("تاريخ البناء", "Built"), builtLabel(deployment.builtAt))
        add(t("صورة النظام", "System image"), ready ? text(deployment.digest) : "")
        add(t("التوقيع", "Signature"), signatureText)
        add(t("النواة", "Kernel"), ready ? text(kcm.status.kernelLabel) : "")
        add(t("الجلسة", "Session"), ready ? label(kcm.status.sessionLabel) : "")
        add(t("اسم الجهاز", "Device name"), ready ? text(kcm.status.hostname) : "")
        add(t("المعالج", "Processor"), ready ? text(kcm.status.cpu) : "")
        add(t("الرسوميات", "Graphics"), ready ? text(kcm.status.gpu) : "")
        add(t("الذاكرة", "Memory"), ready ? text(memory.total) : "")
        add(t("التخزين", "Storage"), ready ? text(storage.total) : "")
        add(t("المعمارية", "Architecture"), ready ? label(kcm.status.archLabel) : "")
        return lines.join("\n")
    }

    LayoutMirroring.enabled: rtl
    LayoutMirroring.childrenInherit: true
    Component.onCompleted: kcm.ensureFresh()
    onVisibleChanged: if (visible) kcm.ensureFresh()

    actions: [
        Kirigami.Action {
            text: root.t("تحديث الحالة", "Refresh")
            icon.name: "view-refresh"
            enabled: !kcm.loading
            onTriggered: kcm.refresh()
        }
    ]

    // A TextEdit is the clipboard a QML page has.
    TextEdit { id: clipboard; visible: false; Accessible.ignored: true }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        MoosStatusNotice {
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            backend: kcm
        }
        MoosRouteNotice {
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            message: root.routeError
        }

        MoosHero {
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            compact: true
            logoSource: kcm.logoSource
            title: root.t("مركز تحكم MoOS", "MoOS Control Center")
            subtitle: root.t("الصوت والاتصال ومساحة العمل", "Sound, connections and workspace")
            chips: [
                MoosChip {
                    glyph: root.signatureTone === "warning" ? "warning" : "shield"
                    label: root.signatureText
                    tone: root.signatureTone
                },
                MoosChip {
                    glyph: root.updateState.glyph
                    label: root.updateState.text
                    tone: root.updateState.tone
                }
            ]
            actions: [
                MoosChip {
                    glyph: "about"
                    label: root.versionText || root.unknownLabel
                    tone: "neutral"
                },
                Controls.Button {
                    Layout.fillWidth: true
                    text: root.t("ما الجديد", "What's new")
                    icon.name: MoUI.SymbolCatalog.resolve("spark")
                    Accessible.description: root.freshCount > 0 ? root.freshText
                        : root.t("ما الذي تغيّر في MoOS مع كل تحديث", "What changed in MoOS with each update")
                    onClicked: root.open("moos://settings/whats-new")
                }
            ]
        }

        GridLayout {
            id: liveControls
            objectName: "moosDeviceControls"
            Layout.fillWidth: true
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            columns: width >= Kirigami.Units.gridUnit * 40 ? 2 : 1
            columnSpacing: root.design.space3
            rowSpacing: root.design.space3
            MoosAudioCard {
                objectName: "moosControlAudio"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: root.cardWidth * 0.6
                backend: kcm
            }
            MoUI.Surface {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: root.cardWidth * 0.4
                implicitHeight: deviceRows.implicitHeight + root.design.space2 * 2
                ColumnLayout {
                    id: deviceRows
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: root.design.space2 }
                    spacing: 0
                    MoosDeviceTile {
                        objectName: "moosControlNetwork"
                        Layout.fillWidth: true
                        compact: true
                        glyph: "wifi"
                        text: root.t("الشبكة", "Network")
                        stateText: root.networkText
                        detail: root.ready && root.text(root.network.label)
                            ? root.text(root.network.label) : root.t("إدارة الاتصالات", "Manage connections")
                        active: root.ready && root.network.known === true && root.network.connectivity === "full"
                        enabled: root.routeAvailable("moos://settings/network")
                        onClicked: root.open("moos://settings/network")
                    }
                    MoosDeviceTile {
                        objectName: "moosControlBluetooth"
                        Layout.fillWidth: true
                        compact: true
                        glyph: "bluetooth"
                        text: root.t("بلوتوث", "Bluetooth")
                        stateText: !root.ready ? root.unknownLabel
                            : !root.bluetooth.available ? root.t("غير متاح", "Unavailable")
                            : root.bluetooth.powered ? root.t("مفعّل", "On") : root.t("متوقف", "Off")
                        detail: root.t("السماعات ولوحات المفاتيح والأجهزة", "Headphones, keyboards and devices")
                        active: root.ready && root.bluetooth.available === true && root.bluetooth.powered === true
                        enabled: root.routeAvailable("moos://settings/bluetooth")
                        onClicked: root.open("moos://settings/bluetooth")
                    }
                    MoosDeviceTile {
                        objectName: "moosControlBattery"
                        Layout.fillWidth: true
                        compact: true
                        glyph: "battery"
                        text: root.t("الطاقة", "Power")
                        stateText: root.batteryText
                        detail: root.batteryDetail
                        enabled: root.routeAvailable("moos://settings/energy")
                        onClicked: root.open("moos://settings/energy")
                    }
                }
            }
        }

        Kirigami.Heading {
            Layout.fillWidth: true
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: root.design.space3
            level: 2
            text: root.t("مساحتك، بطريقتك", "Make this space yours")
        }
        GridLayout {
            id: destinations
            objectName: "moosSettingsDestinations"
            Layout.fillWidth: true
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            columns: width >= Kirigami.Units.gridUnit * 32 ? 2 : 1
            columnSpacing: root.design.space3
            rowSpacing: root.design.space3

            MoosDestinationTile {
                objectName: "moosSettingsDisplay"
                Layout.fillWidth: true
                Layout.fillHeight: true
                glyph: "system"
                text: root.t("الشاشة والعرض", "Display & screens")
                description: root.t("الدقة، التحجيم وترتيب الشاشات", "Resolution, scale and screen arrangement")
                enabled: root.routeAvailable("moos://settings/display")
                onClicked: root.open("moos://settings/display")
            }
            MoosDestinationTile {
                Layout.fillWidth: true
                Layout.fillHeight: true
                glyph: "ui"
                text: root.t("المظهر والتخصيص", "Appearance & personality")
                description: root.t("ألوان MoOS، الخلفية والحركة", "MoOS colours, wallpaper and motion")
                enabled: root.routeAvailable("moos://settings/appearance")
                onClicked: root.open("moos://settings/appearance")
            }
            MoosDestinationTile {
                Layout.fillWidth: true
                Layout.fillHeight: true
                glyph: "keyboard"
                text: root.t("لوحة المفاتيح", "Keyboard")
                description: root.t("تخطيطات الكتابة وسلوك المفاتيح", "Typing layouts and key behaviour")
                enabled: root.routeAvailable("moos://settings/keyboard")
                onClicked: root.open("moos://settings/keyboard")
            }
            MoosDestinationTile {
                Layout.fillWidth: true
                Layout.fillHeight: true
                glyph: "shield"
                text: root.t("أذونات التطبيقات", "App permissions")
                description: root.t("الوصول إلى الكاميرا والميكروفون والأجهزة", "Camera, microphone and device access")
                enabled: root.routeAvailable("moos://settings/permissions")
                onClicked: root.open("moos://settings/permissions")
            }
            MoosDestinationTile {
                Layout.fillWidth: true
                Layout.fillHeight: true
                glyph: "user"
                text: root.t("إمكانية الوصول", "Accessibility")
                description: root.t("الرؤية، القراءة والتحكم بالإدخال", "Vision, reading and input assistance")
                enabled: root.routeAvailable("moos://settings/accessibility")
                onClicked: root.open("moos://settings/accessibility")
            }
            MoosDestinationTile {
                Layout.fillWidth: true
                Layout.fillHeight: true
                glyph: "notification"
                text: root.t("الإشعارات والتركيز", "Notifications & focus")
                description: root.t("التنبيهات، الأصوات وعدم الإزعاج", "Alerts, sounds and Do Not Disturb")
                enabled: root.routeAvailable("moos://settings/notifications")
                onClicked: root.open("moos://settings/notifications")
            }
            MoosDestinationTile {
                objectName: "moosSettingsWidgets"
                Layout.fillWidth: true
                Layout.fillHeight: true
                glyph: "grid"
                text: root.t("أدوات سطح المكتب", "Desktop widgets")
                description: root.t("أضف الأدوات، عاينها ورتّبها في مساحتك", "Add widgets, preview them and arrange your space")
                enabled: root.routeAvailable("moos://settings/desktop")
                onClicked: root.open("moos://settings/desktop")
            }
            MoosDestinationTile {
                Layout.fillWidth: true
                Layout.fillHeight: true
                glyph: "boxes"
                text: root.t("مساحات العمل", "Workspaces")
                description: root.t("أسطح المكتب الافتراضية والتنقل بينها", "Virtual desktops and navigation")
                enabled: root.routeAvailable("moos://settings/desktops")
                onClicked: root.open("moos://settings/desktops")
            }

        }

        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("نظرة سريعة", "At a glance")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosActionRow {
                glyph: "safe-update"
                text: root.t("التحديث", "Update")
                description: root.updateState.text
                enabled: root.routeAvailable("moos://settings/update")
                onClicked: root.open("moos://settings/update")
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "spark"
                text: root.t("ما الجديد", "What's new")
                description: root.freshCount > 0 ? root.freshText
                    : root.t("ما الذي جاء به كل تحديث، والأحدث أولاً", "What each update brought, newest first")
                enabled: root.routeAvailable("moos://settings/whats-new")
                onClicked: root.open("moos://settings/whats-new")
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "phone"
                text: "Mo PC Remote"
                description: root.remoteText
                enabled: root.routeAvailable("moos://settings/remote")
                onClicked: root.open("moos://settings/remote")
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "repair"
                text: root.t("الاستعادة", "Recovery")
                description: root.rollbackText
                enabled: root.routeAvailable("moos://settings/recovery")
                onClicked: root.open("moos://settings/recovery")
            }
        }

        Controls.Button {
            id: copyButton
            property bool copied: false
            Layout.alignment: Qt.AlignHCenter
            text: copied ? root.t("تم النسخ", "Copied") : root.t("نسخ التفاصيل", "Copy details")
            icon.name: MoUI.SymbolCatalog.resolve(copied ? "check" : "copy")
            enabled: root.ready
            Accessible.description: root.t("ينسخ إصدار MoOS ومواصفات الجهاز كنص لمحادثة دعم",
                                           "Copies the MoOS version and device facts as text for a support conversation")
            onClicked: {
                clipboard.text = root.aboutReport()
                clipboard.selectAll()
                clipboard.copy()
                clipboard.deselect()
                copied = true
                copiedReset.restart()
            }
            Timer { id: copiedReset; interval: 2200; onTriggered: copyButton.copied = false }
        }

        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("النظام", "System")
        }
        FormCard.FormCard {
            id: systemFacts
            maximumWidth: root.cardWidth

            MoosFactRow {
                label: root.t("الإصدار", "Version")
                value: root.ready && root.deployment.known ? "MoOS " + root.text(root.deployment.version) : ""
                technical: true
            }
            MoosFactRow {
                label: root.t("الإصدارة", "Edition")
                value: root.ready ? root.label(kcm.status.editionLabel) : ""
            }
            MoosFactRow {
                label: root.t("صورة النظام", "System image")
                value: root.ready ? root.text(root.deployment.digest) : ""
                technical: true
            }
            MoosFactRow {
                label: root.t("التوقيع", "Signature")
                value: root.ready && root.deployment.known ? root.signatureText : ""
                valueColor: root.deployment.signed ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.neutralTextColor
            }
            MoosFactRow {
                label: root.t("تاريخ البناء", "Built")
                value: root.ready ? root.builtLabel(root.deployment.builtAt) : ""
            }
            MoosFactRow {
                label: root.t("النواة", "Kernel")
                value: root.ready ? root.text(kcm.status.kernelLabel) : ""
                technical: true
            }
            MoosFactRow {
                label: root.t("الجلسة", "Session")
                value: root.ready ? root.label(kcm.status.sessionLabel) : ""
            }
        }

        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("هذا الجهاز", "This device")
        }
        FormCard.FormCard {
            id: deviceFacts
            maximumWidth: root.cardWidth

            MoosFactRow {
                label: root.t("اسم الجهاز", "Device name")
                value: root.ready ? root.text(kcm.status.hostname) : ""
                technical: true
            }
            MoosFactRow {
                label: root.t("المعالج", "Processor")
                value: root.ready ? root.text(kcm.status.cpu) : ""
                technical: true
            }
            MoosFactRow {
                label: root.t("الرسوميات", "Graphics")
                value: root.ready ? root.text(kcm.status.gpu) : ""
                technical: true
            }
            MoosFactRow {
                label: root.t("الذاكرة", "Memory")
                value: root.ready ? root.text(root.memory.total) : ""
                technical: true
            }
            MoosFactRow {
                label: root.t("التخزين", "Storage")
                value: root.ready && root.text(root.storage.total) && root.storage.total !== "—"
                    ? root.isolated(root.text(root.storage.free)) + root.t(" متاحة من ", " free of ")
                      + root.isolated(root.text(root.storage.total))
                    : ""
            }
            MoosFactRow {
                label: root.t("المعمارية", "Architecture")
                value: root.ready ? root.label(kcm.status.archLabel) : ""
            }
        }
    }
}
