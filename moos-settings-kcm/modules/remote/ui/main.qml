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
    // A requested change, until the MEASURED state shows it. moos-open asks before
    // turning Remote on and the owner may answer late, so a wait is not cleared by
    // whichever measurement happens to arrive first. It ends when the field the request
    // targets reads the value asked for (a restart has none: when a measurement taken
    // after it arrives), or after two minutes (the question was declined, or the
    // change did not happen). The switch shows the measurement throughout, never the wish.
    property string waitField: ""
    property bool waitValue: false
    property real waitSince: 0
    readonly property bool waiting: waitSince > 0
    readonly property int waitLimitMs: 120000

    function t(ar, en) { return rtl ? ar : en }
    function open(route) {
        routeError = kcm.openRoute(route) ? "" : t("تعذّر فتح Mo PC Remote. حاول مرة أخرى.",
                                                    "Could not open Mo PC Remote. Try again.")
    }
    function request(route, field, value) {
        var opened = kcm.openRoute(route)
        routeError = opened ? "" : t("تعذّر تنفيذ الطلب. حاول مرة أخرى.", "Could not send that request. Try again.")
        if (!opened) {
            endWait()
            return
        }
        waitField = field
        waitValue = value === true
        waitSince = Date.now() / 1000
        waitLimit.restart()
    }
    function endWait() {
        waitSince = 0
        waitField = ""
        waitLimit.stop()
    }
    function settled() {
        if (!waiting || !ready)
            return false
        if (waitField === "")
            return kcm.statusGeneratedAt >= waitSince + 2
        return remote[waitField] === waitValue
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
        function onStatusChanged() {
            if (root.settled())
                root.endWait()
        }
    }
    Timer { id: waitLimit; interval: root.waitLimitMs; onTriggered: root.endWait() }
    // While a request waits and the page is shown, measure again every 3 s (the helper
    // takes about 0.2 s). The backend also watches the unit's enable link, so a change
    // that lands while the page is hidden is read as soon as it happens.
    Timer {
        interval: 3000
        repeat: true
        running: root.waiting && root.visible
        onTriggered: kcm.refresh()
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
                onRequested: wanted => root.request(wanted ? "moos://remote/start" : "moos://remote/stop",
                                                    "enabled", wanted)
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "refresh"
                text: root.t("إعادة تشغيل الاتصال", "Restart the connection")
                description: root.t("مفيد عندما لا يصل الهاتف رغم أن الخدمة تعمل.",
                                    "Useful when the phone cannot reach this computer although the service is on.")
                enabled: root.installed && (root.remote.enabled === true || root.remote.failed === true)
                onClicked: root.request("moos://remote/restart", "", false)
            }
        }

        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("الوضع السريع", "Fast Remote")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosSwitchRow {
                glyph: "bolt"
                text: root.t("تسريع الاتصال", "Speed up the connection")
                description: root.t("يوقف حركة الخلفية والضبابية والحركات مؤقتاً ليبقى البث سريعاً. يعود كل شيء عند إيقافه.",
                                    "Pauses the live wallpaper, blur and animations so the stream stays quick. Everything returns when you turn it off.")
                enabled: root.installed
                on: root.installed && root.remote.fast === true
                onRequested: wanted => root.request(wanted ? "moos://remote/fast-on" : "moos://remote/fast-off",
                                                    "fast", wanted)
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
