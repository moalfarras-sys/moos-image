pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — Categories: a banner and one tile per category; a tile opens the
// catalogue filtered to it.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Flickable {
    id: categoriesFlick
    required property var win
    readonly property var design: win.design
    anchors.fill: parent
    visible: win.page === "categories"
    contentWidth: width
    contentHeight: categoryBody.implicitHeight + 44
    clip: true
    Keys.onPressed: (event) => MoUI.KeyboardViewport.pageScrollKeys(categoriesFlick, event)
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    ColumnLayout {
        id: categoryBody
        x: 24
        width: parent.width - 48
        spacing: 18
        Item { Layout.preferredHeight: win.fs(4) }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: win.fs(122)
            radius: design.radiusPanel
            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.12)
            border.width: 1
            border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.3)
            RowLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 17
                Rectangle {
                    Layout.preferredWidth: win.fs(66)
                    Layout.preferredHeight: win.fs(66)
                    radius: win.fs(21)
                    color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                    Glyph { win: categoriesFlick.win; anchors.centerIn: parent; width: 32; height: 32; name: "boxes"; tint: win.accent }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3
                    Text {
                        text: win.rtl ? "اختر حسب ما تريد إنجازه" : "Start with what you want to do"
                        color: win.txt
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(22)
                        font.bold: true
                    }
                    Text {
                        text: win.rtl ? "فئات عملية بدل قوائم تقنية طويلة." : "Human categories instead of package-manager jargon."
                        color: win.txt2
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(12)
                    }
                }
            }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: win.width > 1160 ? 4 : 3
            columnSpacing: 13
            rowSpacing: 13
            Repeater {
                model: win.categoryDefs
                delegate: Rectangle {
                    id: categoryTile
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: win.fs(132)
                    radius: win.fs(21)
                    color: categoryHover.hovered
                        ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.97)
                        : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.78)
                    border.width: 1
                    border.color: categoryHover.hovered ? win.accent : win.outline
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: win.rtl ? categoryTile.modelData.ar : categoryTile.modelData.en
                    FocusRing { win: categoriesFlick.win }
                    HoverHandler { id: categoryHover }
                    TapHandler { onTapped: win.openCategory(categoryTile.modelData.id) }
                    Keys.onReturnPressed: win.openCategory(categoryTile.modelData.id)
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: design.space2
                        RowLayout {
                            Layout.fillWidth: true
                            Rectangle {
                                Layout.preferredWidth: win.fs(46)
                                Layout.preferredHeight: win.fs(46)
                                radius: design.radiusCard
                                color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.13)
                                Glyph { win: categoriesFlick.win; anchors.centerIn: parent; width: 24; height: 24; name: categoryTile.modelData.glyph; tint: win.accent }
                            }
                            Item { Layout.fillWidth: true }
                            Text {
                                text: win.categoryCount(categoryTile.modelData.id)
                                color: win.accent
                                font.family: win.uiFont
                                font.pixelSize: win.typePx(15)
                                font.bold: true
                            }
                        }
                        Text {
                            text: win.rtl ? categoryTile.modelData.ar : categoryTile.modelData.en
                            color: win.txt
                            font.family: win.uiFont
                            font.pixelSize: win.typePx(14)
                            font.bold: true
                        }
                        Text {
                            text: win.rtl ? "استكشف التطبيقات" : "Explore apps"
                            color: win.txt2
                            font.family: win.uiFont
                            font.pixelSize: win.typePx(10)
                        }
                    }
                }
            }
        }
    }
}
