pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — the install list, floating at the foot of the window while apps are picked and
// nothing is running: how many, their pictures, Clear, and Review & install. It steps aside while
// the review is open and while a job runs or has just ended (the job shelf has the floor then).
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: selectionShelf
    objectName: "selectionShelf"
    required property var win
    readonly property var design: win.design
    readonly property var picked: {
        var ids = Object.keys(selectionShelf.win.picks)
        var out = []
        for (var i = 0; i < ids.length && out.length < 4; ++i) {
            var app = selectionShelf.win.appById(ids[i])
            if (app) out.push(app)
        }
        return out
    }

    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: win.pickCount > 0
                          && !win.reviewOpened
                          && !win.jobIsActive()
                          && !win.jobIsTerminal() ? win.fs(20) : -win.fs(100)
    width: Math.min(win.fs(640), win.width - win.fs(64))
    height: win.fs(68)
    visible: anchors.bottomMargin > -win.fs(100)
    z: 49
    Behavior on anchors.bottomMargin { NumberAnimation { duration: selectionShelf.win.motionEnabled ? selectionShelf.design.motionGeometry : 0; easing.type: Easing.OutCubic } }

    SoftShadow { win: selectionShelf.win; radius: shelf.radius; strength: 2.2; lift: selectionShelf.design.space3 }
    Rectangle {
        id: shelf
        anchors.fill: parent
        radius: height / 2
        color: selectionShelf.win.cardColor
        border.width: 1
        border.color: selectionShelf.win.tint(selectionShelf.win.accent, 0.5)
        LayoutMirroring.enabled: selectionShelf.win.rtl
        LayoutMirroring.childrenInherit: true

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: selectionShelf.design.space3
            anchors.rightMargin: selectionShelf.design.space3
            spacing: selectionShelf.design.space3
            Rectangle {
                Layout.preferredWidth: selectionShelf.win.fs(44)
                Layout.preferredHeight: selectionShelf.win.fs(44)
                radius: width / 2
                color: selectionShelf.win.accent
                Text {
                    anchors.centerIn: parent
                    text: selectionShelf.win.pickCount
                    color: selectionShelf.win.accentText
                    font.family: selectionShelf.win.uiFont
                    font.pixelSize: selectionShelf.win.typePx(15)
                    font.weight: Font.Bold
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: selectionShelf.win.local("قائمة التثبيت جاهزة", "Install list ready")
                    color: selectionShelf.win.txt
                    font.family: selectionShelf.win.uiFont
                    font.pixelSize: selectionShelf.win.typePx(14)
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: selectionShelf.win.local("راجع مصدر كل تطبيق قبل البدء", "Review where each comes from before starting")
                    color: selectionShelf.win.txt2
                    font.family: selectionShelf.win.uiFont
                    font.pixelSize: selectionShelf.win.typePx(12)
                    elide: Text.ElideRight
                }
            }
            Row {
                spacing: -selectionShelf.win.fs(8)
                visible: selectionShelf.width > selectionShelf.win.fs(560)
                Repeater {
                    model: selectionShelf.picked
                    delegate: Rectangle {
                        id: pickedIcon
                        required property var modelData
                        width: selectionShelf.win.fs(34)
                        height: width
                        radius: selectionShelf.win.fs(11)
                        color: selectionShelf.win.cardColor
                        AppIcon { win: selectionShelf.win; anchors.centerIn: parent; app: pickedIcon.modelData; size: selectionShelf.win.fs(30) }
                    }
                }
            }
            ActionButton {
                win: selectionShelf.win
                pill: true
                compact: true
                label: selectionShelf.win.local("مسح", "Clear")
                triggered: function() { selectionShelf.win.clearPicks() }
            }
            ActionButton {
                win: selectionShelf.win
                pill: true
                compact: true
                primary: true
                label: selectionShelf.win.local("راجع وثبّت", "Review & install")
                glyphName: "download"
                triggered: function() { selectionShelf.win.openReview() }
            }
        }
    }
}
