// SPDX-License-Identifier: GPL-2.0-or-later
// kcm_moos_remote — Mo PC Remote's switches, inside System Settings. The state is
// the user service and the Fast Remote journal as moos-settings-status measured
// them; every change is a fixed moos:// route (moos-open confirms turning it on).
// Pairing a phone, the PIN and the connection details live in the Mo PC Remote app.
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
    readonly property bool ready: kcm.statusValid
    readonly property var remote: kcm.status.remote || ({})
    readonly property bool installed: ready && remote.available === true
    readonly property real cardWidth: Kirigami.Units.gridUnit * 40
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)
    property string routeError: ""
    // Set when a switch asked for a change and cleared when the measured state
    // changes or the wait runs out; the switch itself never shows the wish.
    property bool waiting: false

    function t(ar, en) { return rtl ? ar : en }
    function open(route) {
        routeError = kcm.openRoute(route) ? "" : t("تعذّر فتح Mo PC Remote. حاول مرة أخرى.",
                                                    "Could not open Mo PC Remote. Try again.")
    }
    // A change of state: the switch waits for the measured result, never shows the wish.
    function request(route) {
        var opened = kcm.openRoute(route)
        routeError = opened ? "" : t("تعذّر تنفيذ الطلب. حاول مرة أخرى.", "Could not send that request. Try again.")
        waiting = opened
        if (opened)
            waitLimit.restart()
    }

    function remoteSummary() {
        if (!ready)
            return { tone: "neutral", title: t("حالة الاتصال غير معروفة", "Connection status unknown"), detail: "" }
        if (!remote.available)
            return { tone: "neutral", title: t("غير مثبت على هذا الجهاز", "Not installed on this device"),
                     detail: t("لا يحمل هذا الإصدار من MoOS تطبيق Mo PC Remote.", "This edition of MoOS does not carry Mo PC Remote.") }
        if (remote.failed)
            return { tone: "negative", title: t("توقفت الخدمة بخطأ", "The service stopped with an error"),
                     detail: t("أعد تشغيل الاتصال، أو افتح Mo PC Remote لترى السبب.",
                               "Restart the connection, or open Mo PC Remote to see why.") }
        if (remote.active)
            return { tone: "positive", title: t("جاهز لاتصال خاص من هاتفك", "Ready for a private connection from your phone"),
                     detail: t("يعمل الآن ويبدأ مع كل جلسة.", "Running now, and it starts with every session.") }
        if (remote.enabled)
            return { tone: "neutral", title: t("سيبدأ مع الجلسة", "Starts with your session"),
                     detail: t("مفعّل لكنه لا يعمل الآن.", "Turned on, but not running right now.") }
        return { tone: "neutral", title: t("التحكم عن بُعد متوقف", "Remote control is off"),
                 detail: t("لا يستطيع أي هاتف الاتصال بهذا الحاسوب.", "No phone can connect to this computer.") }
    }
    readonly property var summary: remoteSummary()

    Connections {
        target: kcm
        function onStatusChanged() { root.waiting = false }
    }
    Timer { id: waitLimit; interval: 12000; onTriggered: root.waiting = false }

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

        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: "Mo PC Remote"
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosInfoRow {
                glyph: "phone"
                text: root.summary.title
                description: root.summary.detail
                trailing: [
                    MoosChip {
                        visible: root.waiting
                        glyph: "refresh"
                        label: root.t("بانتظار النتيجة…", "Waiting…")
                        tone: "neutral"
                    },
                    MoosChip {
                        visible: root.installed && !root.waiting
                        glyph: root.remote.failed ? "warning" : root.remote.active ? "check" : "power"
                        label: root.remote.failed ? root.t("خطأ", "Error")
                             : root.remote.active ? root.t("يعمل", "On")
                             : root.t("متوقف", "Off")
                        tone: root.summary.tone
                    }
                ]
            }
            FormCard.FormDelegateSeparator {}
            MoosSwitchRow {
                glyph: "power"
                text: root.t("السماح بالتحكم من هاتفك", "Allow control from your phone")
                description: root.t("يبدأ مع كل جلسة. يسألك MoOS قبل تشغيله.",
                                    "It starts with every session. MoOS asks you before turning it on.")
                enabled: root.installed
                on: root.installed && root.remote.enabled === true
                onRequested: wanted => root.request(wanted ? "moos://remote/start" : "moos://remote/stop")
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "refresh"
                text: root.t("إعادة تشغيل الاتصال", "Restart the connection")
                description: root.t("مفيد عندما لا يصل الهاتف رغم أن الخدمة تعمل.",
                                    "Useful when the phone cannot reach this computer although the service is on.")
                enabled: root.installed && (root.remote.enabled === true || root.remote.failed === true)
                onClicked: root.request("moos://remote/restart")
            }
        }

        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("الهاتف", "Your phone")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosActionRow {
                glyph: "external"
                text: root.t("فتح Mo PC Remote", "Open Mo PC Remote")
                description: root.t("اقرن هاتفاً، واعرض الرمز وتفاصيل الاتصال.",
                                    "Pair a phone, and see the PIN and the connection details.")
                enabled: root.installed
                onClicked: root.open("moos://app/remote")
            }
        }
    }
}
