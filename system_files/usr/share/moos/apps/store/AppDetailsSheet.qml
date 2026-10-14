pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — an app's page, as a sheet: artwork, publisher, source, summary,
// description, facts, the advanced-source warning and Remove / Open / Review & install.
// It shows win.selectedApp; main.qml's openDetails() fills it.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Popup {
    id: details
    required property var win
    readonly property var design: win.design
    anchors.centerIn: Overlay.overlay
    width: Math.min(760, win.width - 70)
    height: Math.min(670, win.height - 56)
    modal: true
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle {
        radius: win.fs(26)
        color: win.surface
        border.width: 1
        border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.38)
    }
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.54) }
    enter: Transition {
        NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: win.motionEnabled ? design.motionPress : 0; easing.type: Easing.OutBack }
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: win.motionEnabled ? design.motionPress : 0 }
    }
    Flickable {
        id: detailFlick
        anchors.fill: parent
        anchors.margins: 22
        contentWidth: width
        contentHeight: detailBody.implicitHeight
        clip: true
        Keys.onPressed: (event) => MoUI.KeyboardViewport.pageScrollKeys(detailFlick, event)
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        ColumnLayout {
            id: detailBody
            width: parent.width
            spacing: 15
            RowLayout {
                Layout.fillWidth: true
                spacing: 15
                AppArtwork { win: details.win; app: win.selectedApp; size: 78 }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3
                    Text {
                        Layout.fillWidth: true
                        text: win.localName(win.selectedApp)
                        color: win.txt
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(24)
                        font.bold: true
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: win.selectedApp ? (win.selectedApp.developer || win.selectedApp.id) : ""
                        color: win.txt2
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(11)
                        elide: Text.ElideRight
                    }
                    RowLayout {
                        SourceBadge { win: details.win; app: win.selectedApp }
                        Rectangle {
                            visible: win.selectedApp !== null && !!win.selectedApp.license
                            implicitHeight: win.fs(22)
                            implicitWidth: licenseText.implicitWidth + 14
                            radius: height / 2
                            color: Qt.rgba(win.txt2.r, win.txt2.g, win.txt2.b, 0.12)
                            Text {
                                id: licenseText
                                anchors.centerIn: parent
                                text: win.selectedApp ? win.selectedApp.license : ""
                                color: win.txt2
                                font.family: win.uiFont
                                font.pixelSize: win.typePx(9)
                            }
                        }
                    }
                }
                ActionButton {
                    win: details.win
                    label: win.rtl ? "إغلاق" : "Close"
                    glyphName: "close"
                    triggered: function() { details.close() }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: win.selectedApp && win.selectedApp.screenshot ? 250 : 0
                visible: height > 0
                radius: design.radiusCard
                color: win.canvas
                clip: true
                Image {
                    anchors.fill: parent
                    source: win.selectedApp && win.selectedApp.screenshot ? win.selectedApp.screenshot : ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    smooth: true
                }
                Rectangle {
                    anchors.fill: parent
                    gradient: Gradient {
                        GradientStop { position: 0.6; color: "transparent" }
                        GradientStop { position: 1; color: Qt.rgba(win.canvas.r, win.canvas.g, win.canvas.b, 0.74) }
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                text: win.localSummary(win.selectedApp)
                textFormat: Text.PlainText
                color: win.txt
                font.family: win.uiFont
                font.pixelSize: win.typePx(15)
                font.bold: true
                wrapMode: Text.WordWrap
            }
            Text {
                Layout.fillWidth: true
                // Most catalogue entries have no long description, so localDescription
                // falls back to the summary — and the sheet showed the same sentence
                // twice. Only a description that ADDS something earns the row.
                visible: win.localDescription(win.selectedApp) !== win.localSummary(win.selectedApp)
                text: win.localDescription(win.selectedApp)
                textFormat: Text.PlainText
                color: win.txt2
                font.family: win.uiFont
                font.pixelSize: win.typePx(11)
                wrapMode: Text.WordWrap
                lineHeight: 1.35
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 3
                columnSpacing: 10
                Repeater {
                    model: [
                        {
                            label: win.rtl ? "المصدر" : "Source",
                            value: win.sourceLabel(win.selectedApp),
                            glyph: "orbit"
                        },
                        {
                            label: win.rtl ? "الفئة" : "Category",
                            value: win.categoryName(win.normalizedCategory(win.selectedApp || ({}))),
                            glyph: win.categoryGlyph(win.normalizedCategory(win.selectedApp || ({})))
                        },
                        {
                            label: win.rtl ? "الإصدار" : "Version",
                            value: win.selectedApp && win.selectedApp.version ? win.selectedApp.version : (win.rtl ? "يتبع المصدر" : "From source"),
                            glyph: "refresh"
                        }
                    ]
                    delegate: Rectangle {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: win.fs(78)
                        radius: design.radiusCard
                        color: Qt.rgba(win.canvas.r, win.canvas.g, win.canvas.b, 0.5)
                        border.width: 1
                        border.color: win.outline
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 9
                            Glyph { win: details.win; name: modelData.glyph; tint: win.accent; Layout.preferredWidth: win.fs(19); Layout.preferredHeight: win.fs(19) }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                // Explicit alignment on BOTH lines: Text defaults to its
                                // content's direction, so in RTL an Arabic label and a
                                // Latin value ("Flathub", "1.2.3") sat on opposite edges
                                // of the same chip.
                                Text {
                                    Layout.fillWidth: true
                                    horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                                    text: modelData.label
                                    color: win.txt2
                                    font.family: win.uiFont
                                    font.pixelSize: win.typePx(9)
                                }
                                Text {
                                    Layout.fillWidth: true
                                    horizontalAlignment: win.rtl ? Text.AlignRight : Text.AlignLeft
                                    text: modelData.value
                                    color: win.txt
                                    font.family: win.uiFont
                                    font.pixelSize: win.typePx(11)
                                    font.bold: true
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: win.fs(58)
                visible: win.selectedApp !== null && (win.selectedApp.requires_review === true
                                                      || (win.selectedApp.install
                                                          && win.selectedApp.install.requires_review === true)
                                                      || (win.selectedApp.install && win.selectedApp.install.kind === "npm"))
                radius: design.radiusCard
                color: Qt.rgba(win.violet.r, win.violet.g, win.violet.b, 0.1)
                border.width: 1
                border.color: Qt.rgba(win.violet.r, win.violet.g, win.violet.b, 0.34)
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10
                    Glyph { win: details.win; name: "shield"; tint: win.violet; Layout.preferredWidth: win.fs(20); Layout.preferredHeight: win.fs(20) }
                    Text {
                        Layout.fillWidth: true
                        text: win.rtl
                            ? "مصدر متقدم: راجع اسم الحزمة وطريقة التثبيت قبل المتابعة."
                            : "Advanced source: review the package and install method before continuing."
                        color: win.txt
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(10)
                        wrapMode: Text.WordWrap
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Text {
                    visible: win.systemManagedOnly(win.selectedApp)
                    text: win.rtl ? "مُدار مع النظام" : "System managed"
                    color: win.txt2
                    font.family: win.uiFont
                    font.pixelSize: win.typePx(10)
                    font.bold: true
                }
                Item { Layout.fillWidth: true }
                ActionButton {
                    win: details.win
                    visible: win.canRemove(win.selectedApp)
                    enabled: !win.jobIsActive()
                    label: win.rtl ? "إزالة" : "Remove"
                    glyphName: "trash"
                    destructive: true
                    triggered: function() { win.removeSelected(win.selectedApp) }
                }
                ActionButton {
                    win: details.win
                    enabled: !win.isInstalled(win.selectedApp)
                             || win.hasRunnableLifecycle(win.selectedApp)
                    label: win.isInstalled(win.selectedApp)
                        ? win.hasRunnableLifecycle(win.selectedApp)
                            ? (win.rtl ? "افتح التطبيق" : "Open app")
                            : (win.rtl ? "مثبّت وجاهز" : "Installed and ready")
                        : win.isWeb(win.selectedApp)
                            ? (win.rtl ? "افتح الموقع الرسمي" : "Open official website")
                            : (win.rtl ? "مراجعة وتثبيت" : "Review & install")
                    glyphName: win.isInstalled(win.selectedApp)
                        ? win.hasRunnableLifecycle(win.selectedApp) ? "external" : "check"
                        : "download"
                    primary: true
                    triggered: function() {
                        if (win.isInstalled(win.selectedApp)
                                && win.hasRunnableLifecycle(win.selectedApp))
                            win.runSelected(win.selectedApp)
                        else {
                            details.close()
                            win.installOne(win.selectedApp)
                        }
                    }
                }
            }
        }
    }
}
