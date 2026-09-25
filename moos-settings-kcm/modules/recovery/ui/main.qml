// SPDX-License-Identifier: GPL-2.0-or-later
// kcm_moos_recovery — the saved system images and whether a return to one is queued,
// from the deployment list moos-settings-status read. A queued rollback is not a
// staged update, and the page never calls one the other. Choosing a version happens
// in the Recovery window, which confirms before anything changes.
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
    readonly property var deployment: kcm.status.deployment || ({})
    readonly property bool known: ready && deployment.known === true
    readonly property real cardWidth: Kirigami.Units.gridUnit * 40
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)
    property string routeError: ""

    function t(ar, en) { return rtl ? ar : en }
    function text(value) { return typeof value === "string" ? value : "" }
    function isolated(value) { return "\u2068" + text(value) + "\u2069" }
    function open(route) {
        routeError = kcm.openRoute(route) ? "" : t("تعذّر فتح نافذة الاستعادة. حاول مرة أخرى.",
                                                    "Could not open the Recovery window. Try again.")
    }

    function recoverySummary() {
        if (!known)
            return { tone: "neutral", glyph: "repair", title: t("حالة الاستعادة غير معروفة", "Recovery status unknown"),
                     detail: "" }
        if (deployment.rollbackQueued)
            return { tone: "warning", glyph: "warning",
                     title: t("الرجوع مجدول لإعادة التشغيل القادمة", "A rollback is queued for the next restart"),
                     detail: deployment.rollbackTarget
                         ? t("يبدأ MoOS الإصدار ", "MoOS starts version ") + isolated(deployment.rollbackTarget)
                           + t(" عند إعادة التشغيل. ملفاتك تبقى كما هي.", " at the next restart. Your files stay as they are.")
                         : t("يبدأ MoOS إصداراً سابقاً عند إعادة التشغيل. ملفاتك تبقى كما هي.",
                             "MoOS starts a previous version at the next restart. Your files stay as they are.") }
        if (deployment.rollback > 0)
            return { tone: "positive", glyph: "check", title: t("نسخة سابقة محفوظة", "A previous version is saved"),
                     detail: deployment.rollbackTarget
                         ? t("يمكنك الرجوع إلى الإصدار ", "You can return to version ") + isolated(deployment.rollbackTarget)
                           + t(" إذا لم يعجبك التحديث.", " if an update does not suit you.")
                         : t("يمكنك الرجوع إليها إذا لم يعجبك التحديث.", "You can return to it if an update does not suit you.") }
        return { tone: "neutral", glyph: "repair", title: t("لا توجد نسخة سابقة بعد", "No previous version saved yet"),
                 detail: t("بعد التحديث القادم يبقى الإصدار الذي تستخدمه الآن هنا للرجوع إليه.",
                           "After the next update, the version you run now is kept here to return to.") }
    }
    readonly property var summary: recoverySummary()

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
            title: root.t("الاستعادة", "Recovery")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosInfoRow {
                glyph: root.summary.glyph
                glyphColor: root.summary.tone === "warning" ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.highlightColor
                text: root.summary.title
                description: root.summary.detail
                trailing: [
                    MoosChip {
                        visible: root.known
                        glyph: root.deployment.rollbackQueued ? "warning" : "repair"
                        label: root.deployment.rollbackQueued ? root.t("مجدول", "Queued")
                             : root.t("نسخ محفوظة: ", "Saved: ") + (root.deployment.rollback || 0)
                        tone: root.summary.tone
                    }
                ]
            }
            FormCard.FormDelegateSeparator {}
            MoosFactRow {
                label: root.t("يعمل الآن", "Running now")
                value: root.known ? root.text(root.deployment.version) : ""
                technical: true
            }
            MoosFactRow {
                label: root.t("الإصدار السابق", "Previous version")
                value: root.known ? root.text(root.deployment.previousVersion) : ""
                technical: true
            }
            MoosFactRow {
                label: root.t("نسخ محفوظة", "Saved images")
                value: root.known ? String(root.deployment.rollback || 0) : ""
                technical: true
            }
            MoosFactRow {
                visible: root.known && root.deployment.rollbackQueued === true
                label: root.t("عند إعادة التشغيل", "At the next restart")
                value: root.known ? root.text(root.deployment.rollbackTarget) : ""
                technical: true
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "repair"
                text: root.t("عرض خيارات الاستعادة", "Review recovery options")
                description: root.t("راجع كل نسخة محفوظة قبل أن تختار الرجوع. يسألك MoOS قبل أي تغيير.",
                                    "See each saved version before you choose to return. MoOS asks before anything changes.")
                onClicked: root.open("moos://app/recovery")
            }
        }

        MoosNote {
            Layout.maximumWidth: root.cardWidth
            Layout.alignment: Qt.AlignHCenter
            text: root.t("يحتفظ MoOS بالإصدار السابق بعد كل تحديث. الرجوع يغيّر النظام فقط؛ ملفاتك وإعداداتك الشخصية تبقى كما هي.",
                         "MoOS keeps the previous version after every update. Returning changes the system only; your files and personal settings stay as they are.")
        }
    }
}
