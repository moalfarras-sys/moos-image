/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later
*/
import QtQuick
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

// One coloured glyph for native login, lock and power controls. This item
// never handles input; the existing AbstractButton remains the sole owner.
Item {
    id: glyph
    objectName: "moosSessionActionGlyph"
    property alias source: icon.source
    property alias active: icon.active
    property color accentColor: Kirigami.Theme.highlightColor
    property color inkColor: Kirigami.Theme.highlightedTextColor
    property bool embeddedInAccent: false
    implicitWidth: MoUI.Tokens.targetControl
    implicitHeight: implicitWidth
    Accessible.ignored: true

    Rectangle {
        objectName: "moosSessionActionGlyphFill"
        anchors.fill: parent
        radius: Math.min(MoUI.Tokens.radiusControl, width * 0.30)
        color: glyph.accentColor
        visible: !glyph.embeddedInAccent
    }
    Kirigami.Icon {
        id: icon
        objectName: "moosSessionActionGlyphInk"
        anchors.centerIn: parent
        width: Math.round(Math.min(parent.width, parent.height) * 0.66)
        height: width
        isMask: true
        color: glyph.inkColor
    }
}
