pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — Updates: what is pending (not checked yet / none / failed / known), the
// apps waiting, and the three update paths (apps here; the MoOS image and firmware on
// their signed system paths).
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Flickable {
    id: updatesFlick
    required property var win
    readonly property var design: win.design
    anchors.fill: parent
    visible: win.page === "updates"
    contentWidth: width
    contentHeight: updateBody.implicitHeight + 50
    clip: true
    Keys.onPressed: (event) => MoUI.KeyboardViewport.pageScrollKeys(updatesFlick, event)
    ColumnLayout {
        id: updateBody
        x: 26
        width: parent.width - 52
        spacing: design.space4
        Item { Layout.preferredHeight: win.fs(4) }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: win.fs(210)
            radius: win.fs(27)
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.2) }
                GradientStop { position: 1; color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.88) }
            }
            border.width: 1
            border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.36)
            RowLayout {
                anchors.fill: parent
                anchors.margins: 28
                spacing: design.space5
                Rectangle {
                    Layout.preferredWidth: win.fs(92)
                    Layout.preferredHeight: win.fs(92)
                    radius: win.fs(30)
                    color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                    Glyph { win: updatesFlick.win; anchors.centerIn: parent; width: 46; height: 46; name: "refresh"; tint: win.accent }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 7
                    Text {
                        // Say what is true, and say "not checked yet" when
                        // that is what is true. Never show 0 before looking.
                        text: {
                            if (win.updatesChecking)
                                return win.rtl ? "نفحص التحديثات…" : "Checking for updates…"
                            if (win.updatesState === "failed")
                                return win.rtl ? "تعذّر فحص التحديثات" : "Could not check for updates"
                            if (win.updatesState === "unknown")
                                return win.rtl ? "تطبيقاتك، وتحديثاتها." : "Your apps, and their updates."
                            var n = win.updateItems().length
                            if (n === 0 && win.updateComponentCount() > 0)
                                return win.rtl
                                    ? "توجد تحديثات لمكوّنات مشتركة."
                                    : "Shared components have updates."
                            if (n === 0)
                                return win.rtl ? "كل تطبيقاتك محدّثة." : "Everything is up to date."
                            return win.rtl
                                ? (n === 1 ? "تطبيق واحد ينتظر التحديث." : n + " تطبيقات تنتظر التحديث.")
                                : (n === 1 ? "1 app has an update." : n + " apps have updates.")
                        }
                        color: win.txt
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(24)
                        font.bold: true
                    }
                    Text {
                        Layout.fillWidth: true
                        text: {
                            if (win.updatesState === "failed")
                                return win.rtl
                                    ? "تحقّق من اتصالك ثم أعد الفحص. تحديث صورة MoOS والبرامج الثابتة تبقى في مسارات النظام الموقّعة."
                                    : "Check your connection and try again. MoOS image and firmware updates stay on their signed system paths."
                            var extra = win.updateComponentCount()
                            if (win.updatesState === "known" && extra > 0)
                                return win.rtl
                                    ? "بالإضافة إلى " + extra + " مكوّن مشترك يُحدَّث معها. تحديث صورة MoOS والبرامج الثابتة تبقى في مسارات النظام الموقّعة."
                                    : "Plus " + extra + " shared component(s) that update with them. MoOS image and firmware updates stay on their signed system paths."
                            return win.rtl
                                ? "حدّث تطبيقاتك هنا. تحديث صورة MoOS والبرامج الثابتة يبقيان في مسارات النظام الموقّعة."
                                : "Update your apps here. MoOS image and firmware updates stay on their signed system paths."
                        }
                        color: win.txt2
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(12)
                        wrapMode: Text.WordWrap
                    }
                    RowLayout {
                        spacing: design.space2
                        ActionButton {
                            win: updatesFlick.win
                            label: win.updateItems().length === 0
                                   && win.updateComponentCount() > 0
                                ? (win.rtl ? "تحديث المكوّنات الآن" : "Update components now")
                                : (win.rtl ? "تحديث التطبيقات الآن" : "Update apps now")
                            glyphName: "refresh"
                            primary: true
                            // Nothing pending is a reason not to offer the
                            // button, once we actually know that.
                            enabled: !win.jobIsActive() && !win.updatesChecking
                                && !(win.updatesState === "known" && win.updates.count === 0)
                            triggered: function() { win.updateAll() }
                        }
                        ActionButton {
                            win: updatesFlick.win
                            label: win.rtl ? "إعادة الفحص" : "Check again"
                            glyphName: "search"
                            enabled: !win.updatesChecking
                            triggered: function() {
                                win.updatesState = "unknown"
                                win.updatesCheckedAt = ""
                                win.checkUpdates()
                            }
                        }
                        ActionButton {
                            win: updatesFlick.win
                            label: win.rtl ? "تحديث MoOS" : "Update MoOS"
                            glyphName: "shield"
                            triggered: function() { win.openSystemUpdater() }
                        }
                    }
                }
            }
        }
        // The list the page was missing: what actually has an
        // update, named, with the version currently installed.
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 9
            visible: win.updatesState === "known" && win.updateItems().length > 0
            Text {
                text: win.rtl ? "بانتظار التحديث" : "Waiting to update"
                color: win.txt2
                font.family: win.uiFont
                font.pixelSize: win.typePx(12)
                font.bold: true
            }
            Repeater {
                model: win.updatesState === "known" ? win.updateItems() : []
                delegate: Rectangle {
                    id: pendingRow
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: win.fs(62)
                    radius: design.radiusCard
                    color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.72)
                    border.width: 1
                    border.color: win.outline
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 16
                        anchors.rightMargin: 16
                        spacing: 13
                        Rectangle {
                            Layout.preferredWidth: win.fs(36)
                            Layout.preferredHeight: win.fs(36)
                            radius: design.radiusControl
                            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                            Glyph {
                                win: updatesFlick.win
                                anchors.centerIn: parent
                                width: 19; height: 19
                                name: "download"; tint: win.accent
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            Text {
                                Layout.fillWidth: true
                                text: pendingRow.modelData.name || pendingRow.modelData.id
                                color: win.txt
                                font.family: win.uiFont
                                font.pixelSize: win.typePx(14)
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                text: pendingRow.modelData.id
                                    + (pendingRow.modelData.version
                                        ? " · " + pendingRow.modelData.version : "")
                                color: win.txt2
                                font.family: win.uiFont
                                font.pixelSize: win.typePx(11)
                                elide: Text.ElideRight
                            }
                        }
                        Text {
                            text: pendingRow.modelData.origin || ""
                            color: win.txt2
                            font.family: win.uiFont
                            font.pixelSize: win.typePx(11)
                        }
                    }
                }
            }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: 3
            columnSpacing: 13
            Repeater {
                model: [
                    { glyph: "grid", ar: "تحديثات التطبيقات", en: "App updates", ar2: "تحديث آمن بصلاحيات المستخدم", en2: "Safe per-user transactions", action: "update" },
                    { glyph: "shield", ar: "صورة MoOS", en: "MoOS image", ar2: "تحديث موقّع يُطبق بعد إعادة التشغيل", en2: "Signed, applied after reboot", action: "system-update" },
                    { glyph: "gear", ar: "البرامج الثابتة", en: "Device firmware", ar2: "تحديثات العتاد من المصدر الموثوق", en2: "Trusted hardware updates", action: "firmware" }
                ]
                delegate: Rectangle {
                    id: updateCard
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: win.fs(156)
                    radius: win.fs(21)
                    color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.78)
                    border.width: 1
                    border.color: win.outline
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: design.space2
                        Glyph {
                            win: updatesFlick.win
                            name: updateCard.modelData.glyph
                            tint: win.accent
                            Layout.preferredWidth: win.fs(27)
                            Layout.preferredHeight: win.fs(27)
                        }
                        Text {
                            text: win.rtl ? updateCard.modelData.ar : updateCard.modelData.en
                            color: win.txt
                            font.family: win.uiFont
                            font.pixelSize: win.typePx(14)
                            font.bold: true
                        }
                        Text {
                            Layout.fillWidth: true
                            text: win.rtl ? updateCard.modelData.ar2 : updateCard.modelData.en2
                            color: win.txt2
                            font.family: win.uiFont
                            font.pixelSize: win.typePx(10)
                            wrapMode: Text.WordWrap
                        }
                        Item { Layout.fillHeight: true }
                        ActionButton {
                            win: updatesFlick.win
                            label: updateCard.modelData.action === "update"
                                ? win.updateItems().length === 0
                                    && win.updateComponentCount() > 0
                                    ? (win.rtl ? "حدّث المكوّنات الآن" : "Update components now")
                                    : (win.rtl ? "حدّث التطبيقات الآن" : "Update apps now")
                                : updateCard.modelData.action === "system-update"
                                    ? (win.rtl ? "افتح محدّث MoOS" : "Open MoOS Updater")
                                    : (win.rtl ? "افتح تحديثات البرامج الثابتة" : "Open firmware updates")
                            glyphName: updateCard.modelData.action === "update"
                                ? "refresh" : "external"
                            enabled: updateCard.modelData.action !== "update"
                                || (!win.jobIsActive()
                                    && !win.updatesChecking
                                    && !(win.updatesState === "known"
                                         && win.updates.count === 0))
                            triggered: function() {
                                if (updateCard.modelData.action === "update") win.updateAll()
                                else if (updateCard.modelData.action === "system-update")
                                    win.openSystemUpdater()
                                else win.openSourceEngine(updateCard.modelData.action)
                            }
                        }
                    }
                }
            }
        }
    }
}
