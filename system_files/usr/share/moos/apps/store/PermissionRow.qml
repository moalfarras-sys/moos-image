pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — one thing an app may do, in a person's words: its glyph, its name and one line about
// it, and on the trailing side either what is true (Allowed / Not allowed / Asks first), a switch,
// or — for a web app — Allow · Ask each time · Don't allow. A row that a broader permission
// already covers says so instead of offering a switch that could not change anything.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: row
    required property var win
    readonly property var design: win.design
    property string key: ""
    property bool allowed: false
    property bool ask: false
    property bool changeable: false
    // "info" (words only), "switch", or "choice" (allow / ask / deny).
    property string mode: "info"
    property bool busy: false
    signal chosen(string value)

    implicitHeight: Math.max(win.fs(56), rowLayout.implicitHeight + design.space3 * 2)

    readonly property string stateText: row.ask ? win.local("يسأل أولًا", "Asks first")
                                      : row.allowed ? win.local("مسموح", "Allowed")
                                      : win.local("غير مسموح", "Not allowed")

    RowLayout {
        id: rowLayout
        anchors.fill: parent
        anchors.topMargin: row.design.space2
        anchors.bottomMargin: row.design.space2
        spacing: row.design.space3

        Rectangle {
            Layout.preferredWidth: row.win.fs(36)
            Layout.preferredHeight: row.win.fs(36)
            radius: row.design.radiusControl
            color: row.win.tint(row.win.txt, row.win.lightScheme ? 0.06 : 0.08)
            Glyph {
                win: row.win
                anchors.centerIn: parent
                width: row.win.fs(18)
                height: width
                name: row.win.permissionGlyph(row.key)
                tint: row.win.txt
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: row.win.permissionTitle(row.key)
                color: row.win.txt
                font.family: row.win.uiFont
                font.pixelSize: row.win.typePx(14)
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            Text {
                Layout.fillWidth: true
                text: row.mode === "switch" && !row.changeable
                    ? row.win.local("تشمله صلاحية أوسع مسموح بها", "Covered by a broader permission that is allowed")
                    : row.win.permissionLine(row.key)
                color: row.win.txt2
                font.family: row.win.uiFont
                font.pixelSize: row.win.typePx(12)
                wrapMode: Text.WordWrap
            }
        }

        // What is true, in words.
        Rectangle {
            visible: row.mode === "info"
            Layout.preferredHeight: row.win.fs(26)
            Layout.preferredWidth: stateLabel.implicitWidth + row.design.space3 * 2
            radius: height / 2
            color: row.win.tint(row.allowed && !row.ask ? row.win.positiveInk : row.win.txt,
                                row.win.lightScheme ? 0.10 : 0.12)
            Text {
                id: stateLabel
                anchors.centerIn: parent
                text: row.stateText
                color: row.allowed && !row.ask ? row.win.positiveInk : row.win.txt2
                font.family: row.win.uiFont
                font.pixelSize: row.win.typePx(11)
                font.weight: Font.DemiBold
            }
        }

        // A switch.
        Rectangle {
            id: track
            visible: row.mode === "switch"
            enabled: row.changeable && !row.busy
            Layout.preferredWidth: row.win.fs(46)
            Layout.preferredHeight: row.win.fs(26)
            radius: height / 2
            opacity: enabled ? 1 : 0.45
            color: row.allowed ? row.win.accent : row.win.tint(row.win.txt, row.win.lightScheme ? 0.18 : 0.22)
            activeFocusOnTab: true
            Accessible.role: Accessible.CheckBox
            Accessible.name: row.win.permissionTitle(row.key)
            Accessible.checkable: true
            Accessible.checked: row.allowed
            Accessible.onToggleAction: row.chosen(row.allowed ? "deny" : "allow")
            Accessible.onPressAction: row.chosen(row.allowed ? "deny" : "allow")
            Keys.onSpacePressed: row.chosen(row.allowed ? "deny" : "allow")
            Keys.onReturnPressed: row.chosen(row.allowed ? "deny" : "allow")
            FocusRing { win: row.win }
            TapHandler { enabled: track.enabled; onTapped: row.chosen(row.allowed ? "deny" : "allow") }
            Behavior on color { ColorAnimation { duration: row.win.motionEnabled ? row.design.motionFast : 0 } }
            Rectangle {
                width: track.height - 6
                height: width
                radius: width / 2
                y: 3
                x: row.allowed !== row.win.rtl ? track.width - width - 3 : 3
                color: row.allowed ? row.win.accentText : row.win.canvas
                Behavior on x { NumberAnimation { duration: row.win.motionEnabled ? row.design.motionPress : 0; easing.type: Easing.OutCubic } }
            }
        }

        // Allow · Ask each time · Don't allow.
        Rectangle {
            visible: row.mode === "choice"
            Layout.preferredHeight: row.win.fs(32)
            Layout.preferredWidth: choiceRow.implicitWidth + 4
            radius: height / 2
            color: row.win.tint(row.win.txt, row.win.lightScheme ? 0.06 : 0.08)
            RowLayout {
                id: choiceRow
                anchors.centerIn: parent
                spacing: 2
                Repeater {
                    model: [
                        { value: "allow", ar: "سماح", en: "Allow" },
                        { value: "reset", ar: "اسأل كل مرة", en: "Ask each time" },
                        { value: "deny", ar: "منع", en: "Don't allow" }
                    ]
                    delegate: Rectangle {
                        id: segment
                        required property var modelData
                        readonly property bool on: segment.modelData.value === "reset" ? row.ask
                                                   : segment.modelData.value === "allow" ? (row.allowed && !row.ask)
                                                   : (!row.allowed && !row.ask)
                        Layout.preferredHeight: row.win.fs(28)
                        Layout.preferredWidth: segmentLabel.implicitWidth + row.design.space3 * 2
                        radius: height / 2
                        color: segment.on ? row.win.accent : "transparent"
                        enabled: !row.busy
                        activeFocusOnTab: true
                        Accessible.role: Accessible.RadioButton
                        Accessible.name: row.win.permissionTitle(row.key) + ": " + segmentLabel.text
                        Accessible.checked: segment.on
                        Accessible.onPressAction: row.chosen(segment.modelData.value)
                        Keys.onSpacePressed: row.chosen(segment.modelData.value)
                        Keys.onReturnPressed: row.chosen(segment.modelData.value)
                        FocusRing { win: row.win }
                        TapHandler { onTapped: if (!segment.on) row.chosen(segment.modelData.value) }
                        Text {
                            id: segmentLabel
                            anchors.centerIn: parent
                            text: row.win.rtl ? segment.modelData.ar : segment.modelData.en
                            color: segment.on ? row.win.accentText : row.win.txt
                            font.family: row.win.uiFont
                            font.pixelSize: row.win.typePx(12)
                            font.weight: segment.on ? Font.DemiBold : Font.Normal
                        }
                    }
                }
            }
        }
    }
}
