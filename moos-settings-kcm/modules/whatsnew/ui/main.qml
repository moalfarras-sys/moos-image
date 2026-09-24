// SPDX-License-Identifier: GPL-2.0-or-later
// kcm_moos_whatsnew — what each MoOS update brought, newest first, grouped by the day
// it arrived. The list is /usr/share/moos/whats-new.json as moos_whats_new.py read and
// validated it (through the status document); "fresh" means newer than the system this
// machine ran before its last update. "Try it" appears only where MoOS has a route.
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
    readonly property var whatsNew: kcm.status.whatsNew || ({})
    readonly property real cardWidth: Kirigami.Units.gridUnit * 40
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)
    readonly property var ownPages: ["overview", "about", "update", "whats-new", "remote",
                                     "recovery", "assistant", "appearance", "themes", "wallpaper"]
    // A status document from before this page existed is an empty list, never an error.
    readonly property var entries: ready && whatsNew.entries ? whatsNew.entries : []
    readonly property int freshCount: ready ? (whatsNew.fresh || 0) : 0
    property string routeError: ""

    function t(ar, en) { return rtl ? ar : en }

    function routeAvailable(route) {
        var text = String(route || "")
        if (text.indexOf("moos://settings/") !== 0)
            return false
        var token = text.substring(16)
        return ownPages.indexOf(token) >= 0 || (ready && (kcm.status.destinations || {})[token] === true)
    }
    function open(route) {
        routeError = kcm.openRoute(route) ? "" : t("تعذّر فتح هذه الصفحة. حاول مرة أخرى.",
                                                    "Could not open that page. Try again.")
    }

    function dayLabel(epoch) {
        var date = new Date(epoch * 1000)
        return date.getDate() + " " + Qt.locale().monthName(date.getMonth(), Locale.LongFormat)
               + " " + date.getFullYear()
    }

    readonly property string freshText: {
        var count = freshCount
        if (!rtl)
            return count === 1 ? "1 new thing since your last update" : count + " new things since your last update"
        if (count === 1) return "تغيير واحد جديد منذ آخر تحديث"
        if (count === 2) return "تغييران جديدان منذ آخر تحديث"
        return count + (count <= 10 ? " تغييرات جديدة" : " تغييرًا جديدًا") + " منذ آخر تحديث"
    }

    // Entries that reached MoOS on the same day share one dated heading.
    readonly property var groups: {
        var result = []
        for (var i = 0; i < entries.length; ++i) {
            var entry = entries[i]
            var day = new Date(entry.merged * 1000)
            var key = day.getFullYear() + "-" + day.getMonth() + "-" + day.getDate()
            if (result.length === 0 || result[result.length - 1].key !== key)
                result.push({ key: key, epoch: entry.merged, fresh: false, entries: [] })
            var group = result[result.length - 1]
            group.entries.push(entry)
            if (entry.fresh)
                group.fresh = true
        }
        return result
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

        FormCard.FormCard {
            Layout.topMargin: Kirigami.Units.largeSpacing
            maximumWidth: root.cardWidth

            MoosInfoRow {
                glyph: "spark"
                text: root.t("ما الجديد في MoOS", "What's new in MoOS")
                description: root.freshCount > 0 ? root.freshText
                    : root.t("ما جاء به كل تحديث، والأحدث أولاً. كل جديد يصل مع التحديث التالي.",
                             "What each update brought, newest first. Anything new arrives with the next update.")
                trailing: [
                    MoosChip {
                        visible: root.freshCount > 0
                        glyph: "spark"
                        label: root.rtl ? "جديد: " + root.freshCount : root.freshCount + " new"
                        tone: "positive"
                    }
                ]
            }
        }

        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.gridUnit
            visible: root.ready && root.entries.length === 0
            icon.name: MoUI.SymbolCatalog.resolve("spark")
            text: root.t("لا توجد ملاحظات لهذا الإصدار", "Nothing is noted for this version")
            explanation: root.t("ستظهر هنا الأشياء التي يمكنك رؤيتها أو فعلها بعد كل تحديث.",
                                "What you can see or do after each update will appear here.")
        }

        Repeater {
            model: root.groups
            delegate: ColumnLayout {
                id: day
                required property var modelData
                Layout.fillWidth: true
                spacing: 0

                FormCard.FormHeader {
                    maximumWidth: root.cardWidth
                    title: root.dayLabel(day.modelData.epoch)
                           + (day.modelData.fresh ? root.t("  ·  جديد على هذا الجهاز", "  ·  New on this device") : "")
                }
                FormCard.FormCard {
                    maximumWidth: root.cardWidth

                    Repeater {
                        model: day.modelData.entries
                        delegate: NewsEntry {
                            required property var modelData
                            entry: modelData
                            tryable: !!modelData.route && root.routeAvailable(modelData.route)
                            onTryRequested: route => root.open(route)
                        }
                    }
                }
            }
        }
    }
}
