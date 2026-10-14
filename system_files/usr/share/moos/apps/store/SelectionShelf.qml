pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — the install list, floating at the bottom of the window while apps are
// picked and nothing is running.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: selectionShelf
    required property var win
    readonly property var design: win.design
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: win.pickCount > 0
                          && !win.reviewOpened
                          && !win.jobIsActive()
                          && !win.jobIsTerminal() ? 20 : -84
    width: Math.min(610, win.width - 56)
    height: 58
    radius: design.radiusCard
    visible: anchors.bottomMargin > -84
    color: Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.98)
    border.width: 1
    border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.48)
    Behavior on anchors.bottomMargin { NumberAnimation { duration: win.motionEnabled ? design.motionGeometry : 0; easing.type: Easing.OutBack } }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 13
        anchors.rightMargin: 9
        spacing: 10
        Rectangle {
            Layout.preferredWidth: win.fs(34)
            Layout.preferredHeight: win.fs(34)
            radius: design.radiusControl
            color: win.accent
            Text {
                anchors.centerIn: parent
                text: win.pickCount
                color: win.accentText
                font.family: win.uiFont
                font.pixelSize: win.typePx(13)
                font.bold: true
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: -1
            Text {
                text: win.rtl ? "قائمة التثبيت جاهزة" : "Install list ready"
                color: win.txt
                font.family: win.uiFont
                font.pixelSize: win.typePx(12)
                font.bold: true
            }
            Text {
                text: win.rtl ? "راجع المصدر قبل البدء" : "Review sources before starting"
                color: win.txt2
                font.family: win.uiFont
                font.pixelSize: win.typePx(9)
            }
        }
        ActionButton {
            win: selectionShelf.win
            label: win.rtl ? "مسح" : "Clear"
            glyphName: "trash"
            triggered: function() { win.clearPicks() }
        }
        ActionButton {
            win: selectionShelf.win
            label: win.rtl ? "مراجعة وتثبيت" : "Review & install"
            glyphName: "download"
            primary: true
            triggered: function() { win.openReview() }
        }
    }
}
