pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — "Update apps automatically": the scheduled app updater's one switch, on the Updates
// page and in Settings. The backend persists the choice (moos-storectl auto-updates on|off); the
// switch shows what the file says, says "Saving…" until the file says what was asked, and needs
// the next MoOS update on a shell that cannot ask.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
RowLayout {
    id: autoRow
    required property var win
    readonly property var design: win.design
    readonly property bool on: autoRow.win.autoUpdatesPending ? autoRow.win.autoUpdatesWanted : autoRow.win.autoUpdates

    spacing: design.space4

    Rectangle {
        Layout.preferredWidth: autoRow.win.fs(40)
        Layout.preferredHeight: autoRow.win.fs(40)
        radius: autoRow.design.radiusControl
        color: autoRow.win.tint(autoRow.win.accent, autoRow.win.lightScheme ? 0.14 : 0.18)
        Glyph {
            win: autoRow.win
            anchors.centerIn: parent
            width: autoRow.win.fs(20)
            height: width
            name: "refresh"
            tint: autoRow.win.accent
        }
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 2
        Text {
            Layout.fillWidth: true
            text: autoRow.win.local("حدّث التطبيقات تلقائيًا", "Update apps automatically")
            color: autoRow.win.txt
            font.family: autoRow.win.uiFont
            font.pixelSize: autoRow.win.typePx(15)
            font.weight: Font.DemiBold
        }
        Text {
            Layout.fillWidth: true
            text: autoRow.win.autoUpdatesPending ? autoRow.win.local("يُحفظ…", "Saving…")
                : autoRow.on ? autoRow.win.local("مرة في اليوم في الخلفية، دون أن يقاطعك. يُحدَّث MoOS نفسه بجدوله الخاص.",
                                                 "Once a day in the background, without interrupting you. MoOS itself updates on its own schedule.")
                : autoRow.win.local("متوقف: تُحدَّث التطبيقات فقط عندما تضغط «حدّث».", "Off: apps update only when you press Update.")
            color: autoRow.win.txt2
            font.family: autoRow.win.uiFont
            font.pixelSize: autoRow.win.typePx(13)
            wrapMode: Text.WordWrap
        }
    }
    Rectangle {
        id: track
        Layout.preferredWidth: autoRow.win.fs(52)
        Layout.preferredHeight: autoRow.win.fs(30)
        radius: height / 2
        enabled: !autoRow.win.autoUpdatesPending
        opacity: enabled ? 1 : 0.6
        color: autoRow.on ? autoRow.win.accent : autoRow.win.tint(autoRow.win.txt, autoRow.win.lightScheme ? 0.18 : 0.22)
        activeFocusOnTab: true
        Accessible.role: Accessible.CheckBox
        Accessible.name: autoRow.win.local("حدّث التطبيقات تلقائيًا", "Update apps automatically")
        Accessible.checkable: true
        Accessible.checked: autoRow.on
        Accessible.onToggleAction: autoRow.win.setAutoUpdates(!autoRow.on)
        Accessible.onPressAction: autoRow.win.setAutoUpdates(!autoRow.on)
        Keys.onSpacePressed: autoRow.win.setAutoUpdates(!autoRow.on)
        Keys.onReturnPressed: autoRow.win.setAutoUpdates(!autoRow.on)
        FocusRing { win: autoRow.win }
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        TapHandler { enabled: track.enabled; onTapped: autoRow.win.setAutoUpdates(!autoRow.on) }
        Behavior on color { ColorAnimation { duration: autoRow.win.motionEnabled ? autoRow.design.motionFast : 0 } }
        Rectangle {
            width: track.height - 6
            height: width
            radius: width / 2
            y: 3
            x: autoRow.on !== autoRow.win.rtl ? track.width - width - 3 : 3
            color: autoRow.on ? autoRow.win.accentText : autoRow.win.canvas
            Behavior on x { NumberAnimation { duration: autoRow.win.motionEnabled ? autoRow.design.motionPress : 0; easing.type: Easing.OutCubic } }
        }
    }
}
