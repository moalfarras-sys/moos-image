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
    property var source: ""
    property alias active: icon.active
    property color accentColor: Kirigami.Theme.highlightColor
    property color inkColor: Kirigami.Theme.highlightedTextColor
    property bool embeddedInAccent: false
    readonly property var sessionSymbols: ({
        "system-suspend": "moos-moon-symbolic",
        "system-suspend-hibernate": "moos-storage-symbolic",
        "system-reboot": "moos-refresh-symbolic",
        "system-reboot-update": "moos-safe-update-symbolic",
        "system-shutdown": "moos-power-symbolic",
        "system-shutdown-update": "moos-safe-update-symbolic",
        "system-log-out": "moos-external-symbolic",
        "system-lock-screen": "moos-lock-symbolic",
        "system-switch-user": "moos-user-symbolic",
        "system-users": "moos-user-symbolic",
        "user": "moos-user-symbolic"
    })
    function resolvedSource(value) {
        if (typeof value !== "string") { return value; }
        const name = value.replace(/-symbolic$/, "");
        return sessionSymbols[name] || value;
    }
    implicitWidth: MoUI.Tokens.targetControl
    implicitHeight: implicitWidth
    Accessible.ignored: true

    Rectangle {
        objectName: "moosSessionActionGlyphFill"
        anchors.fill: parent
        radius: width / 2
        color: glyph.accentColor
        visible: !glyph.embeddedInAccent
    }
    Kirigami.Icon {
        id: icon
        objectName: "moosSessionActionGlyphInk"
        source: glyph.resolvedSource(glyph.source)
        anchors.centerIn: parent
        width: Math.round(Math.min(parent.width, parent.height) * 0.66)
        height: width
        isMask: true
        color: glyph.inkColor
    }
}
