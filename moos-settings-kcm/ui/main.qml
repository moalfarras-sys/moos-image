// SPDX-License-Identifier: GPL-2.0-or-later
// One native System Settings module for the MoOS-specific system journeys.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import org.moos.ui as MoUI

KCM.ScrollViewKCM {
    id: root
    readonly property bool rtl: MoUI.Locale.rtl
    readonly property var state: kcm.status
    readonly property var deployment: state.deployment || ({})
    readonly property var update: state.update || ({})
    readonly property var remote: state.remote || ({})
    property string page: kcm.requestedPage
    readonly property color ink: Kirigami.Theme.textColor
    readonly property color secondaryInk: Qt.rgba(ink.r, ink.g, ink.b, 0.72)
    readonly property color accent: Kirigami.Theme.highlightColor
    readonly property color surface: Kirigami.Theme.alternateBackgroundColor

    function t(ar, en) { return rtl ? ar : en }
    function go(route) { Qt.openUrlExternally(route) }
    function display(value) { return value && value !== "—" ? value : t("غير معروف", "Unknown") }
    function aboutReport() {
        var lines = ["MoOS " + display(deployment.version)]
        function add(ar, en, value) { lines.push(t(ar, en) + ": " + display(value)) }
        add("الإصدارة", "Edition", deployment.edition)
        add("تاريخ البناء", "Built", deployment.builtAt ? new Date(deployment.builtAt * 1000).toLocaleDateString(Qt.locale()) : "")
        add("الصورة", "Image", deployment.digest)
        add("التوقيع", "Signature", deployment.signed ? t("موثّقة", "Verified") : t("غير معروف", "Unknown"))
        add("النواة", "Kernel", state.kernel)
        add("الجلسة", "Session", state.session)
        add("اسم الجهاز", "Device name", state.hostname)
        add("المعالج", "Processor", state.cpu)
        add("الرسوميات", "Graphics", state.gpu)
        add("الذاكرة", "Memory", (state.memory || {}).total)
        add("التخزين", "Storage", (state.storage || {}).total)
        add("البنية", "Architecture", state.arch)
        return lines.join("\n")
    }

    LayoutMirroring.enabled: rtl
    LayoutMirroring.childrenInherit: true
    Connections {
        target: kcm
        function onRequestedPageChanged() { root.page = kcm.requestedPage }
    }

    ColumnLayout {
        width: parent.width
        spacing: 16

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            Controls.Label {
                text: root.t("نظام واحد. إعدادات واحدة.", "One system. One place to set it up.")
                color: root.ink
                font.pixelSize: 22
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Controls.Label {
                text: root.t("إعدادات الشاشة والصوت والشبكة في الأقسام المجاورة؛ هنا حالة MoOS والتحديث والاستعادة والتحكم عن بُعد.",
                             "Display, sound and network use the sections alongside this one. Here are MoOS status, updates, recovery and remote access.")
                color: root.secondaryInk
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }

        Flow {
            Layout.fillWidth: true
            width: parent.width
            spacing: 8
            Repeater {
                model: [
                    { id: "overview", ar: "الحالة", en: "Status" },
                    { id: "update", ar: "التحديث", en: "Update" },
                    { id: "recovery", ar: "الاستعادة", en: "Recovery" },
                    { id: "remote", ar: "التحكم عن بُعد", en: "Remote" },
                    { id: "about", ar: "هذا الجهاز", en: "This device" },
                    { id: "whats-new", ar: "ما الجديد", en: "What's new" }
                ]
                delegate: Controls.Button {
                    required property var modelData
                    text: root.t(modelData.ar, modelData.en)
                    checkable: true
                    checked: root.page === modelData.id
                    Accessible.name: text
                    onClicked: root.page = modelData.id
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: statusRow.implicitHeight + 24
            radius: 14
            color: root.surface
            border.width: 1
            border.color: Qt.rgba(root.ink.r, root.ink.g, root.ink.b, 0.12)

            RowLayout {
                id: statusRow
                anchors.fill: parent
                anchors.margins: 12
                spacing: 12
                Controls.Label {
                    text: kcm.loading && Object.keys(root.state).length === 0
                          ? root.t("أقرأ حالة الجهاز…", "Reading device status…")
                          : Object.keys(root.state).length === 0
                            ? root.t("تعذّرت قراءة حالة الجهاز؛ حاول التحديث", "Device status unavailable; try refreshing")
                          : root.deployment.staged
                            ? root.t("تحديث جاهز لإعادة التشغيل", "Update ready for restart")
                            : root.update.state === "busy"
                              ? root.t("التحديث قيد العمل", "Update in progress")
                              : root.t("حالة MoOS", "MoOS status")
                    color: root.ink
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Controls.Button {
                    text: root.t("تحديث الحالة", "Refresh status")
                    enabled: !kcm.loading
                    Accessible.name: text
                    onClicked: kcm.refresh()
                }
            }
        }

        ColumnLayout {
            visible: root.page === "overview"
            Layout.fillWidth: true
            spacing: 12
            Controls.Label {
                text: root.t("جهازك الآن", "Your device now")
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }
            Controls.Label {
                text: root.t("الإصدار: ", "Version: ") + root.display(root.deployment.version)
                Layout.fillWidth: true
            }
            Controls.Label {
                text: root.deployment.signed
                      ? root.t("صورة نظام موقّعة", "Signed system image")
                      : root.t("التحقق من صورة النظام غير متاح", "Image verification unavailable")
                color: root.secondaryInk
                Layout.fillWidth: true
            }
            Controls.Label {
                text: root.deployment.staged
                      ? root.t("إصدار جاهز: ", "Ready version: ") + root.display(root.deployment.stagedVersion)
                      : root.t("لا يوجد تحديث مجهّز", "No staged update")
                Layout.fillWidth: true
            }
            Controls.Label {
                text: root.remote.active
                      ? root.t("التحكم عن بُعد يعمل", "Remote access is active")
                      : root.t("التحكم عن بُعد متوقف", "Remote access is off")
                Layout.fillWidth: true
            }
        }

        ColumnLayout {
            visible: root.page === "update"
            Layout.fillWidth: true
            spacing: 12
            Controls.Label {
                text: root.t("تحديث MoOS", "Update MoOS")
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }
            Controls.Label {
                text: root.deployment.staged
                      ? root.t("نسخة موقّعة جاهزة. أعد التشغيل عندما تنتهي من عملك.",
                               "A signed image is ready. Restart when your work is saved.")
                      : root.t("يفحص MoOS التوقيع والإصدار قبل تجهيز أي تحديث. تبقى النسخة السابقة للرجوع.",
                               "MoOS checks the signature and version before staging an update. The previous image stays available.")
                color: root.secondaryInk
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Controls.Button {
                text: root.deployment.staged ? root.t("عرض التحديث الجاهز", "View ready update")
                                             : root.t("فحص التحديثات", "Check for updates")
                Accessible.name: text
                onClicked: root.go("moos://app/updater")
            }
            Controls.Label {
                text: root.t("التطبيقات", "Applications")
                font.weight: Font.DemiBold
                Layout.topMargin: 12
                Layout.fillWidth: true
            }
            Controls.Label {
                text: root.t("حدّث التطبيقات المثبتة عبر Mo Store بعد تأكيد العملية.",
                             "Update installed applications through Mo Store after confirming the action.")
                color: root.secondaryInk
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Controls.Button {
                text: root.t("تحديث التطبيقات", "Update applications")
                Accessible.name: text
                onClicked: root.go("moos://do/update-apps")
            }
            Controls.Label {
                text: root.t("برامج الجهاز الثابتة", "Device firmware")
                font.weight: Font.DemiBold
                Layout.topMargin: 12
                Layout.fillWidth: true
            }
            Controls.Label {
                text: root.t("افحص التحديثات المدعومة لهذا الجهاز. سيطلب MoOS التأكيد قبل التثبيت.",
                             "Check updates supported by this device. MoOS asks before installing them.")
                color: root.secondaryInk
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Controls.Button {
                text: root.t("فحص برامج الجهاز", "Check device firmware")
                Accessible.name: text
                onClicked: root.go("moos://do/update-firmware")
            }
        }

        ColumnLayout {
            visible: root.page === "recovery"
            Layout.fillWidth: true
            spacing: 12
            Controls.Label {
                text: root.t("الاستعادة", "Recovery")
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }
            Controls.Label {
                text: root.t("نسخ محفوظة: ", "Saved images: ") + (root.deployment.rollback || 0)
                Layout.fillWidth: true
            }
            Controls.Label {
                text: root.t("راجع النسخة السابقة قبل اختيار الرجوع. ملفاتك الشخصية لا تتغير.",
                             "Review the previous image before choosing a rollback. Your personal files stay in place.")
                color: root.secondaryInk
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Controls.Button {
                text: root.t("عرض خيارات الاستعادة", "Review recovery options")
                Accessible.name: text
                onClicked: root.go("moos://app/recovery")
            }
        }

        ColumnLayout {
            visible: root.page === "remote"
            Layout.fillWidth: true
            spacing: 12
            Controls.Label {
                text: "Mo PC Remote"
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }
            Controls.Label {
                text: root.remote.failed
                      ? root.t("تحتاج الخدمة إلى انتباهك", "The service needs attention")
                      : root.remote.active
                        ? root.t("جاهز للاتصال الخاص من هاتفك", "Ready for a private connection from your phone")
                        : root.t("الاتصال متوقف حالياً", "Connection is currently off")
                color: root.secondaryInk
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Controls.Button {
                text: root.t("فتح التحكم عن بُعد", "Open Remote control")
                Accessible.name: text
                onClicked: root.go("moos://app/remote")
            }
        }

        ColumnLayout {
            visible: root.page === "about"
            Layout.fillWidth: true
            spacing: 8
            Controls.Label {
                text: root.t("حول هذا الجهاز", "About this device")
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }
            TextEdit { id: aboutClipboard; visible: false; Accessible.ignored: true }
            Controls.Button {
                text: root.t("نسخ التفاصيل", "Copy details")
                enabled: Object.keys(root.state).length > 0
                Accessible.name: text
                onClicked: {
                    aboutClipboard.text = root.aboutReport()
                    aboutClipboard.selectAll()
                    aboutClipboard.copy()
                    aboutClipboard.deselect()
                }
            }
            Repeater {
                model: [
                    { ar: "اسم الجهاز", en: "Device name", value: root.state.hostname },
                    { ar: "الإصدار", en: "Version", value: root.deployment.version },
                    { ar: "الإصدارة", en: "Edition", value: root.deployment.edition },
                    { ar: "تاريخ البناء", en: "Built", value: root.deployment.builtAt ? new Date(root.deployment.builtAt * 1000).toLocaleDateString(Qt.locale()) : "" },
                    { ar: "الصورة", en: "Image", value: root.deployment.digest },
                    { ar: "النواة", en: "Kernel", value: root.state.kernel },
                    { ar: "المعالج", en: "Processor", value: root.state.cpu },
                    { ar: "الرسوميات", en: "Graphics", value: root.state.gpu },
                    { ar: "الذاكرة", en: "Memory", value: (root.state.memory || {}).total },
                    { ar: "التخزين", en: "Storage", value: (root.state.storage || {}).total },
                    { ar: "البنية", en: "Architecture", value: root.state.arch }
                ]
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    Controls.Label { text: root.t(modelData.ar, modelData.en); Layout.preferredWidth: 132 }
                    Controls.Label {
                        text: root.display(modelData.value)
                        wrapMode: Text.WrapAnywhere
                        Layout.fillWidth: true
                    }
                }
            }
        }

        ColumnLayout {
            visible: root.page === "whats-new"
            Layout.fillWidth: true
            spacing: 12
            Controls.Label {
                text: root.t("ما الجديد في MoOS", "What's new in MoOS")
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }
            Repeater {
                model: (root.state.whatsNew || {}).entries || []
                delegate: ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 2
                    Controls.Label {
                        text: root.t((modelData.title || {}).ar || "", (modelData.title || {}).en || "")
                        font.weight: Font.DemiBold
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Controls.Label {
                        text: root.t((modelData.body || {}).ar || "", (modelData.body || {}).en || "")
                        color: root.secondaryInk
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Controls.Button {
                        visible: !!modelData.route
                        text: root.t("جرّبه", "Try it")
                        Accessible.name: text
                        onClicked: root.go(modelData.route)
                    }
                }
            }
        }
    }
}
