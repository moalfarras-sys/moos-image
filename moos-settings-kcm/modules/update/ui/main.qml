// SPDX-License-Identifier: GPL-2.0-or-later
// kcm_moos_update — one place for every update this machine takes, each row read
// from its owner's record, never inferred here:
//   System            the booted/staged deployment and /run/moos/update-state.json
//   Applications      ~/.local/state/moos/app-updates.json from moos-flatpak-update
//   Device firmware   no record yet; the row starts the confirmed firmware check
// Every action is an existing fixed route; the router and moai-do confirm and escalate.
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
    readonly property var apps: kcm.status.apps || ({})
    readonly property var failures: ready && apps.failures ? apps.failures : []
    readonly property real cardWidth: Kirigami.Units.gridUnit * 40
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)
    readonly property string unknownLabel: t("غير معروف", "Unknown")
    property string routeError: ""

    function t(ar, en) { return rtl ? ar : en }
    function isolated(value) { return "\u2068" + (typeof value === "string" ? value : "") + "\u2069" }
    function open(route) {
        routeError = kcm.openRoute(route) ? "" : t("تعذّر بدء هذا الإجراء. حاول مرة أخرى.",
                                                    "Could not start that action. Try again.")
    }
    function whenLabel(epoch) {
        if (!(epoch > 0))
            return ""
        var date = new Date(epoch * 1000)
        return date.toLocaleString(Qt.locale(), Locale.ShortFormat)
    }

    // ── System ──────────────────────────────────────────────────────────────
    function systemSummary() {
        if (!ready)
            return { tone: "neutral", glyph: "safe-update", title: t("حالة التحديث غير معروفة", "Update status unknown"),
                     detail: "" }
        var installed = t("المثبت الآن: ", "Installed now: ") + isolated(deployment.version)
        if (updateRecord.known && updateRecord.state === "busy")
            return { tone: "neutral", glyph: "refresh", title: t("يتم تجهيز تحديث", "An update is being prepared"),
                     detail: installed }
        if (updateRecord.known && updateRecord.state === "replace-staged")
            return { tone: "warning", glyph: "safe-update",
                     title: t("إصدار تصحيحي يحلّ محل التحديث المجهّز", "A corrective release replaces the staged update"),
                     detail: t("المجهّز: ", "Staged: ") + isolated(deployment.stagedVersion)
                             + t("  ·  التصحيحي: ", "  ·  Corrective: ") + isolated(updateRecord.latestVersion) }
        if (updateRecord.known && updateRecord.state === "blocked-downgrade")
            return { tone: "warning", glyph: "shield", title: t("تم منع إصدار أقدم", "An older release was blocked"),
                     detail: t("لا يرجع MoOS إلى إصدار أقدم من الذي يعمل. ", "MoOS never moves back to an older release by itself. ")
                             + installed }
        if (deployment.staged)
            return { tone: "positive", glyph: "safe-update", title: t("تحديث موقّع جاهز", "A signed update is ready"),
                     detail: t("يبدأ الإصدار ", "Version ") + isolated(deployment.stagedVersion)
                             + t(" عند إعادة التشغيل القادمة. احفظ عملك أولاً.", " starts at the next restart. Save your work first.") }
        if (!updateRecord.known)
            return { tone: "neutral", glyph: "safe-update", title: t("لم يتم الفحص مؤخراً", "No recent check"),
                     detail: installed }
        if (updateRecord.state === "current")
            return { tone: "positive", glyph: "check", title: t("MoOS محدّث", "MoOS is up to date"), detail: installed }
        if (updateRecord.state === "available")
            return { tone: "warning", glyph: "download", title: t("يتوفر تحديث موقّع", "A signed update is available"),
                     detail: t("الإصدار الجديد: ", "New version: ") + isolated(updateRecord.latestVersion) + "  ·  " + installed }
        return { tone: "neutral", glyph: "safe-update", title: t("راجع التحديث", "Review the update"), detail: installed }
    }
    readonly property var system: systemSummary()

    // ── Applications ────────────────────────────────────────────────────────
    function appsSummary() {
        if (!ready)
            return { tone: "neutral", title: unknownLabel, detail: "" }
        if (!apps.known)
            return { tone: "neutral", title: t("لا يوجد تحديث تلقائي مسجّل بعد", "No automatic update recorded yet"),
                     detail: t("يحدّث MoOS تطبيقاتك تلقائياً في الخلفية ويسجّل النتيجة هنا.",
                               "MoOS updates your applications in the background and records the result here.") }
        var when = whenLabel(apps.updated)
        if (apps.state === "running")
            return { tone: "neutral", title: t("يتم تحديث التطبيقات الآن", "Applications are updating now"),
                     detail: t("بدأ في ", "Started ") + when }
        if (apps.state === "interrupted")
            return { tone: "warning", title: t("توقف آخر تحديث قبل أن يكتمل", "The last update stopped before it finished"),
                     detail: t("بدأ في ", "Started ") + when + t(". سيُعاد في الموعد القادم، أو حدّث الآن.",
                                                                   ". It runs again at its next time, or update now.") }
        if (apps.state === "failed")
            return { tone: "warning",
                     title: failures.length > 0
                         ? t("تعذّر تحديث بعض التطبيقات", "Some applications could not be updated")
                         : t("تعذّر تحديث التطبيقات", "Applications could not be updated"),
                     detail: t("آخر محاولة: ", "Last attempt: ") + when }
        return { tone: "positive", title: t("التطبيقات محدّثة", "Applications are up to date"),
                 detail: t("آخر تحديث: ", "Last update: ") + when }
    }
    readonly property var appState: appsSummary()

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
            title: root.t("النظام", "System")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosInfoRow {
                glyph: root.system.glyph
                text: root.system.title
                description: root.system.detail
                trailing: [
                    MoosChip {
                        visible: root.ready && root.deployment.known === true
                        glyph: root.deployment.signed ? "shield" : "warning"
                        label: root.deployment.signed ? root.t("موقّع", "Signed") : root.t("غير موثّق", "Unverified")
                        tone: root.deployment.signed ? "positive" : "warning"
                    }
                ]
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "safe-update"
                text: root.ready && root.deployment.staged ? root.t("عرض التحديث الجاهز", "View the ready update")
                                                           : root.t("فحص التحديثات", "Check for updates")
                description: root.t("يتحقق MoOS من التوقيع والإصدار قبل تجهيز أي تحديث، وتبقى النسخة السابقة للرجوع إليها.",
                                    "MoOS checks the signature and the version before it stages anything, and keeps the previous version to return to.")
                onClicked: root.open("moos://app/updater")
            }
        }

        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("التطبيقات", "Applications")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosInfoRow {
                glyph: "boxes"
                text: root.appState.title
                description: root.appState.detail
                trailing: [
                    MoosChip {
                        visible: root.ready && root.apps.known === true
                        glyph: root.appState.tone === "positive" ? "check"
                             : root.appState.tone === "warning" ? "warning" : "refresh"
                        label: root.apps.state === "ok" ? root.t("تم", "Done")
                             : root.apps.state === "running" ? root.t("قيد العمل", "Running")
                             : root.apps.state === "interrupted" ? root.t("لم يكتمل", "Unfinished")
                             : root.t("تعذّر", "Failed")
                        tone: root.appState.tone
                    }
                ]
            }
            Repeater {
                model: root.failures
                delegate: MoosInfoRow {
                    required property var modelData
                    glyph: "warning"
                    glyphColor: Kirigami.Theme.neutralTextColor
                    text: "\u2068" + modelData.app + "\u2069"
                    description: modelData.reason
                }
            }
            FormCard.FormDelegateSeparator {}
            MoosActionRow {
                glyph: "download"
                text: root.t("تحديث التطبيقات الآن", "Update applications now")
                description: root.t("يحدّث Mo Store كل التطبيقات المثبتة بعد أن تؤكد.",
                                    "Mo Store updates every installed application after you confirm.")
                onClicked: root.open("moos://do/update-apps")
            }
        }

        FormCard.FormHeader {
            maximumWidth: root.cardWidth
            title: root.t("برامج الجهاز الثابتة", "Device firmware")
        }
        FormCard.FormCard {
            maximumWidth: root.cardWidth

            MoosActionRow {
                glyph: "cpu"
                text: root.t("فحص برامج الجهاز", "Check device firmware")
                description: root.t("يبحث عن التحديثات التي تنشرها الشركة المصنّعة لهذا الجهاز، ويسألك MoOS قبل تثبيت أي منها.",
                                    "Looks for the updates this device's maker publishes. MoOS asks before installing any of them.")
                onClicked: root.open("moos://do/update-firmware")
            }
        }
    }
}
