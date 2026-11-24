// SPDX-FileCopyrightText: 2026 Moalfarras — MoOS
// SPDX-License-Identifier: GPL-2.0-or-later

// One control of the MoOS Touch Bar and emoji sheet: a glass key with the MoOS corner
// (three round, the top-trailing one square, following the typing direction), drawing an
// emoji, a word or a symbolic icon. A tap activates it; a held repeating control (cursor,
// delete) repeats like a key; a held emoji asks for its skin tones.
import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: control

    property QtObject theme: null
    property string glyph: ""
    property string glyphFamily: ""
    property real glyphSize: Math.round(height * 0.5)
    property string iconName: ""
    property bool filled: true
    property bool accent: false
    property bool selected: false
    property bool rightToLeft: false
    property bool repeats: false
    property string accessibleName: glyph
    readonly property bool pressed: tap.pressed

    signal activated()
    signal held()

    implicitWidth: height
    opacity: enabled ? 1 : 0.38

    readonly property color ink: accent || selected ? Kirigami.Theme.highlightedTextColor
                                                    : (theme ? theme.glassInk : Kirigami.Theme.textColor)

    Rectangle {
        id: face
        anchors.fill: parent
        anchors.margins: Math.max(2, Math.round(control.height * 0.07))
        visible: control.filled || control.accent || control.selected || tap.pressed
        readonly property real round: control.theme ? control.theme.buttonRadius : height / 3
        readonly property real square: control.theme ? control.theme.squareRadius : 2
        radius: round
        topLeftRadius: control.rightToLeft ? square : round
        topRightRadius: control.rightToLeft ? round : square
        color: {
            if (control.accent || control.selected)
                return Kirigami.Theme.highlightColor
            if (!control.theme)
                return Kirigami.Theme.backgroundColor
            if (tap.pressed)
                return control.theme.normalKeyPressedBackgroundColor
            return control.filled ? control.theme.highlightedKeyBackgroundColor : "transparent"
        }
        border.width: 1
        border.color: control.theme ? Qt.rgba(control.theme.glassInk.r, control.theme.glassInk.g,
                                              control.theme.glassInk.b, control.theme.darkGround ? 0.10 : 0.12)
                                    : "transparent"
        scale: tap.pressed ? 0.92 : 1
        Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: Kirigami.Units.shortDuration } }

        // Glass, lit along its top edge.
        Rectangle {
            anchors.top: parent.top
            anchors.topMargin: 1
            x: control.rightToLeft ? face.square + 1 : face.round * 0.7
            width: Math.max(0, parent.width - face.round * 0.7 - face.square - 1)
            height: 1
            color: Qt.rgba(1, 1, 1, control.accent || control.selected ? 0.32
                                                     : (control.theme && control.theme.darkGround ? 0.10 : 0.8))
        }
    }

    Text {
        anchors.centerIn: parent
        visible: control.glyph.length > 0 && control.iconName.length === 0
        width: Math.max(0, control.width - face.anchors.margins * 4)
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: control.glyph
        color: control.ink
        font.family: control.glyphFamily.length > 0 ? control.glyphFamily
                                                     : (control.theme ? control.theme.fontFamily : "")
        font.pixelSize: Math.max(1, control.glyphSize)
        scale: tap.pressed ? 0.92 : 1
        Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }
    }

    Kirigami.Icon {
        anchors.centerIn: parent
        visible: control.iconName.length > 0
        width: Math.round(control.height * 0.46)
        height: width
        source: control.iconName
        isMask: true
        color: control.ink
    }

    TapHandler {
        id: tap
        gesturePolicy: TapHandler.ReleaseWithinBounds
        longPressThreshold: 0.45
        onTapped: if (!control.repeats) control.activated()
        onLongPressed: if (!control.repeats) control.held()
        onPressedChanged: {
            if (!control.repeats)
                return
            if (pressed) {
                control.activated()
                repeater.interval = 420
                repeater.start()
            } else {
                repeater.stop()
            }
        }
        onCanceled: repeater.stop()
    }

    Timer {
        id: repeater
        repeat: true
        onTriggered: {
            interval = 60
            if (tap.pressed && control.enabled) control.activated()
            else stop()
        }
    }

    Accessible.role: Accessible.Button
    Accessible.name: control.accessibleName
    Accessible.onPressAction: control.activated()
}
