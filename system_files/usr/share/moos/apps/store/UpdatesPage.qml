pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — Updates: what is true now (not checked yet / checking / could not check / up to date
// / N waiting), Update all and Check now, when it was last checked, every app waiting with its
// version from → to and its own Update, the "Update apps automatically" switch, and two calm
// cards for what the Store does not update itself: MoOS (its signed updater) and device firmware
// (MoOS Settings → Update, where each device is shown before anything is flashed).
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: updatesPage
    required property var win
    readonly property var design: win.design
    readonly property real padding: updatesPage.width > win.fs(1000) ? design.space6 : design.space5
    readonly property int waiting: win.updatesState === "known" ? win.updateItems().length : 0

    anchors.fill: parent
    visible: win.page === "updates"
    transform: pageEnter.shift
    PageEnter { id: pageEnter; win: updatesPage.win; target: updatesPage }

    Flickable {
        id: updatesFlick
        objectName: "updatesFlick"
        anchors.fill: parent
        contentWidth: width
        contentHeight: updateBody.implicitHeight + updatesPage.design.space6 * 2
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Keys.onPressed: (event) => MoUI.KeyboardViewport.pageScrollKeys(updatesFlick, event)
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: updateBody
            x: updatesPage.padding
            y: updatesPage.design.space2
            width: updatesFlick.width - updatesPage.padding * 2
            spacing: updatesPage.design.space5

            // ── where things stand ──
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: statusRow.implicitHeight + updatesPage.design.space6 * 2
                radius: updatesPage.design.radiusPanel
                color: updatesPage.win.cardColor
                border.width: 1
                border.color: updatesPage.win.cardBorder
                SoftShadow { win: updatesPage.win; radius: updatesPage.design.radiusPanel; strength: 1.2 }
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 1
                    radius: parent.radius - 1
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: updatesPage.win.tint(updatesPage.win.accent, updatesPage.win.rtl ? 0 : 0.14) }
                        GradientStop { position: 1; color: updatesPage.win.tint(updatesPage.win.accent, updatesPage.win.rtl ? 0.14 : 0) }
                    }
                }
                RowLayout {
                    id: statusRow
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: updatesPage.design.space6
                    anchors.rightMargin: updatesPage.design.space6
                    spacing: updatesPage.design.space5
                    Rectangle {
                        Layout.preferredWidth: updatesPage.win.fs(88)
                        Layout.preferredHeight: updatesPage.win.fs(88)
                        radius: width / 2
                        color: updatesPage.win.tint(updatesPage.win.updatesState === "failed" ? updatesPage.win.warningInk
                                                    : updatesPage.waiting > 0 ? updatesPage.win.accent : updatesPage.win.positiveInk,
                                                    updatesPage.win.lightScheme ? 0.16 : 0.20)
                        Glyph {
                            win: updatesPage.win
                            anchors.centerIn: parent
                            width: updatesPage.win.fs(44)
                            height: width
                            name: updatesPage.win.updatesState === "failed" ? "warning"
                                : updatesPage.waiting > 0 || updatesPage.win.updatesChecking ? "safe-update" : "check"
                            tint: updatesPage.win.updatesState === "failed" ? updatesPage.win.warningInk
                                : updatesPage.waiting > 0 ? updatesPage.win.accent : updatesPage.win.positiveInk
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: updatesPage.design.space2
                        Text {
                            Layout.fillWidth: true
                            // Say what is true, and say "not checked yet" when that is what is true.
                            // Never show 0 before looking.
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
                                return win.rtl ? win.updatesCountText(n) + " بانتظارك"
                                               : (n === 1 ? "1 update is ready" : n + " updates are ready")
                            }
                            color: updatesPage.win.txt
                            font.family: updatesPage.win.uiFont
                            font.pixelSize: updatesPage.win.typePx(28)
                            font.weight: Font.Bold
                            wrapMode: Text.WordWrap
                            Accessible.role: Accessible.Heading
                        }
                        Text {
                            Layout.fillWidth: true
                            text: {
                                if (updatesPage.win.updatesState === "failed")
                                    return updatesPage.win.local("تحقّق من اتصالك ثم أعد الفحص.", "Check your connection and try again.")
                                var when = updatesPage.win.agoText(updatesPage.win.updatesCheckedAt)
                                var line = when !== "" ? updatesPage.win.local("آخر فحص ", "Last checked ") + when : ""
                                var extra = updatesPage.win.updateComponentCount()
                                if (updatesPage.win.updatesState === "known" && extra > 0)
                                    line += (line !== "" ? "  ·  " : "")
                                          + updatesPage.win.local("ومعها ", "plus ") + updatesPage.win.componentsCountText(extra)
                                return line !== "" ? line : updatesPage.win.local("يفحص المتجر عندما تفتح هذه الصفحة.", "The Store checks when you open this page.")
                            }
                            color: updatesPage.win.txt2
                            font.family: updatesPage.win.uiFont
                            font.pixelSize: updatesPage.win.typePx(14)
                            wrapMode: Text.WordWrap
                        }
                        RowLayout {
                            Layout.topMargin: updatesPage.design.space2
                            spacing: updatesPage.design.space3
                            ActionButton {
                                win: updatesPage.win
                                pill: true
                                primary: true
                                label: win.updateItems().length === 0 && win.updateComponentCount() > 0
                                    ? (win.rtl ? "حدّث المكوّنات الآن" : "Update components now")
                                    : updatesPage.waiting > 0 ? updatesPage.win.local("حدّث الكل", "Update all") + " (" + updatesPage.waiting + ")"
                                    : updatesPage.win.local("حدّث الكل", "Update all")
                                glyphName: "refresh"
                                // Nothing pending is a reason not to offer the button, once we know it.
                                enabled: !win.jobIsActive() && !win.updatesChecking
                                    && !(win.updatesState === "known" && win.updates.count === 0)
                                triggered: function() { updatesPage.win.updateAll() }
                            }
                            ActionButton {
                                win: updatesPage.win
                                pill: true
                                label: updatesPage.win.local("افحص الآن", "Check now")
                                glyphName: "search"
                                enabled: !updatesPage.win.updatesChecking
                                triggered: function() {
                                    updatesPage.win.updatesState = "unknown"
                                    updatesPage.win.updatesCheckedAt = ""
                                    updatesPage.win.checkUpdates()
                                }
                            }
                        }
                    }
                }
            }

            // ── automatic updates ──
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: autoRow.implicitHeight + updatesPage.design.space4 * 2
                radius: updatesPage.design.radiusCard + 2
                color: updatesPage.win.cardColor
                border.width: 1
                border.color: updatesPage.win.cardBorder
                AutoUpdateRow {
                    id: autoRow
                    win: updatesPage.win
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: updatesPage.design.space5
                    anchors.rightMargin: updatesPage.design.space5
                }
            }

            // ── what is waiting ──
            // The list the page was missing: what actually has an update, named, with the version
            // it has and the version it gets, and its own Update.
            ColumnLayout {
                Layout.fillWidth: true
                spacing: updatesPage.design.space2
                visible: win.updatesState === "known" && win.updateItems().length > 0
                Text {
                    text: win.rtl ? "بانتظار التحديث" : "Waiting to update"
                    color: updatesPage.win.txt
                    font.family: updatesPage.win.uiFont
                    font.pixelSize: updatesPage.win.typePx(20)
                    font.weight: Font.Bold
                    Accessible.role: Accessible.Heading
                }
                Repeater {
                    model: win.updatesState === "known" ? win.updateItems() : []
                    delegate: Rectangle {
                        id: pendingRow
                        required property var modelData
                        readonly property var app: updatesPage.win.appById(pendingRow.modelData.id)
                        readonly property string from: pendingRow.modelData.kind === "pin"
                            ? (pendingRow.modelData.installed_version || "") : (pendingRow.modelData.version || "")
                        readonly property string to: pendingRow.modelData.kind === "pin"
                            ? (pendingRow.modelData.version || "")
                            : (pendingRow.app && pendingRow.app.version && pendingRow.app.version !== pendingRow.from
                               ? pendingRow.app.version : "")
                        Layout.fillWidth: true
                        Layout.preferredHeight: updatesPage.win.fs(72)
                        radius: updatesPage.design.radiusCard
                        color: updatesPage.win.cardColor
                        border.width: 1
                        border.color: rowHover.hovered ? updatesPage.win.tint(updatesPage.win.accent, 0.45) : updatesPage.win.cardBorder
                        HoverHandler { id: rowHover }
                        TapHandler { enabled: pendingRow.app !== null; onTapped: updatesPage.win.openDetails(pendingRow.app) }
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: updatesPage.design.space4
                            anchors.rightMargin: updatesPage.design.space4
                            spacing: updatesPage.design.space4
                            AppIcon {
                                win: updatesPage.win
                                app: pendingRow.app || ({ id: pendingRow.modelData.id, name: pendingRow.modelData.name })
                                size: updatesPage.win.fs(44)
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    text: pendingRow.app ? updatesPage.win.localName(pendingRow.app)
                                                         : (pendingRow.modelData.name || pendingRow.modelData.id)
                                    color: updatesPage.win.txt
                                    font.family: updatesPage.win.uiFont
                                    font.pixelSize: updatesPage.win.typePx(15)
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    text: {
                                        var parts = []
                                        if (pendingRow.from !== "" && pendingRow.to !== "")
                                            parts.push(updatesPage.win.ltr(pendingRow.from + "  →  " + pendingRow.to))
                                        else if (pendingRow.to !== "")
                                            parts.push(updatesPage.win.local("إلى ", "to ") + updatesPage.win.ltr(pendingRow.to))
                                        else if (pendingRow.from !== "")
                                            parts.push(updatesPage.win.local("المثبّت ", "installed ") + updatesPage.win.ltr(pendingRow.from))
                                        parts.push(pendingRow.app ? updatesPage.win.kindLabel(updatesPage.win.appKind(pendingRow.app))
                                                                  : updatesPage.win.kindLabel(pendingRow.modelData.kind === "pin" ? "appdrop" : "flatpak"))
                                        return parts.join("  ·  ")
                                    }
                                    color: updatesPage.win.txt2
                                    font.family: updatesPage.win.uiFont
                                    font.pixelSize: updatesPage.win.typePx(12)
                                    elide: Text.ElideRight
                                }
                            }
                            ActionButton {
                                win: updatesPage.win
                                pill: true
                                compact: true
                                label: updatesPage.win.local("تحديث", "Update")
                                glyphName: "refresh"
                                enabled: !updatesPage.win.jobIsActive()
                                Accessible.name: updatesPage.win.local("حدّث ", "Update ")
                                                 + (pendingRow.modelData.name || pendingRow.modelData.id)
                                triggered: function() {
                                    updatesPage.win.updateOne(pendingRow.app || { id: pendingRow.modelData.id })
                                }
                            }
                        }
                    }
                }
            }

            // ── what the Store does not update itself ──
            GridLayout {
                Layout.fillWidth: true
                columns: updateBody.width > updatesPage.win.fs(760) ? 2 : 1
                columnSpacing: updatesPage.design.space4
                rowSpacing: updatesPage.design.space4
                Repeater {
                    model: [
                        { id: "system", glyph: "shield", ar: "نظام MoOS نفسه", en: "MoOS itself",
                          ar2: "تحديثات النظام موقّعة وتُطبَّق عند إعادة التشغيل، ويبقى الإصدار السابق جاهزًا للعودة إليه.",
                          en2: "System updates are signed and applied on restart, and the previous version stays ready to return to." },
                        { id: "firmware", glyph: "cpu", ar: "البرامج الثابتة للأجهزة", en: "Device firmware",
                          ar2: "تظهر في إعدادات MoOS ← التحديث، حيث ترى كل جهاز وإصداره قبل أن يُثبَّت أي شيء.",
                          en2: "Listed in MoOS Settings → Update, where you see each device and version before anything is installed." }
                    ]
                    delegate: Rectangle {
                        id: systemCard
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: systemColumn.implicitHeight + updatesPage.design.space5 * 2
                        radius: updatesPage.design.radiusCard + 2
                        color: updatesPage.win.cardColor
                        border.width: 1
                        border.color: updatesPage.win.cardBorder
                        ColumnLayout {
                            id: systemColumn
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: updatesPage.design.space5
                            spacing: updatesPage.design.space2
                            RowLayout {
                                spacing: updatesPage.design.space3
                                Rectangle {
                                    Layout.preferredWidth: updatesPage.win.fs(40)
                                    Layout.preferredHeight: updatesPage.win.fs(40)
                                    radius: updatesPage.design.radiusControl
                                    color: updatesPage.win.tint(updatesPage.win.txt, updatesPage.win.lightScheme ? 0.06 : 0.08)
                                    Glyph {
                                        win: updatesPage.win
                                        anchors.centerIn: parent
                                        width: updatesPage.win.fs(20)
                                        height: width
                                        name: systemCard.modelData.glyph
                                        tint: updatesPage.win.txt
                                    }
                                }
                                Text {
                                    text: updatesPage.win.localName(systemCard.modelData)
                                    color: updatesPage.win.txt
                                    font.family: updatesPage.win.uiFont
                                    font.pixelSize: updatesPage.win.typePx(15)
                                    font.weight: Font.DemiBold
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: updatesPage.win.rtl ? systemCard.modelData.ar2 : systemCard.modelData.en2
                                color: updatesPage.win.txt2
                                font.family: updatesPage.win.uiFont
                                font.pixelSize: updatesPage.win.typePx(13)
                                wrapMode: Text.WordWrap
                            }
                            ActionButton {
                                win: updatesPage.win
                                Layout.topMargin: updatesPage.design.space2
                                pill: true
                                compact: true
                                label: systemCard.modelData.id === "system"
                                    ? (updatesPage.win.rtl ? "افتح محدّث MoOS" : "Open MoOS Updater")
                                    : (updatesPage.win.rtl ? "افتح تحديثات البرامج الثابتة" : "Open firmware updates")
                                glyphName: "external"
                                triggered: function() {
                                    if (systemCard.modelData.id === "system") updatesPage.win.openSystemUpdater()
                                    else updatesPage.win.openSystemRoute("firmware")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
