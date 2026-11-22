/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later
*/
import QtQuick
import QtQuick.Controls.impl as ControlsImpl
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
        "input-keyboard-virtual-on": "moos-session-hide-keyboard-symbolic",
        "input-keyboard-virtual-off": "moos-session-show-keyboard-symbolic",
        "input-keyboard": "moos-session-input-language-symbolic",
        "system-suspend": "moos-session-sleep-symbolic",
        "system-suspend-hibernate": "moos-session-hibernate-symbolic",
        "system-reboot": "moos-session-restart-symbolic",
        "system-reboot-update": "moos-session-update-restart-symbolic",
        "system-shutdown": "moos-session-poweroff-symbolic",
        "system-shutdown-update": "moos-session-update-poweroff-symbolic",
        "system-log-out": "moos-session-logout-symbolic",
        "system-lock-screen": "moos-session-lock-symbolic",
        "system-switch-user": "moos-session-switch-user-symbolic",
        "system-users": "moos-session-switch-user-symbolic",
        "user": "moos-user-symbolic"
    })
    function resolvedSource(value) {
        if (typeof value !== "string") { return value; }
        const name = value.replace(/-symbolic$/, "");
        return sessionSymbols[name] || value;
    }
    readonly property var symbol: resolvedSource(source)
    readonly property bool mirrorExit: symbol === "moos-session-logout-symbolic"
        && Qt.application.layoutDirection === Qt.RightToLeft
    readonly property bool rasterSymbol: GraphicsInfo.api === GraphicsInfo.Software
        && typeof symbol === "string" && symbol.startsWith("moos-")
    implicitWidth: MoUI.Tokens.targetControl
    implicitHeight: implicitWidth
    Accessible.ignored: true

    Rectangle {
        objectName: "moosSessionActionGlyphFill"
        anchors.fill: parent
        // The shorter top corner is the cut from the MoOS key silhouette.
        radius: Math.round(width * 0.32)
        topRightRadius: Qt.application.layoutDirection === Qt.RightToLeft ? radius : width * 0.12
        topLeftRadius: Qt.application.layoutDirection === Qt.RightToLeft ? width * 0.12 : radius
        color: glyph.accentColor
        visible: !glyph.embeddedInAccent
    }
    Kirigami.Icon {
        id: icon
        objectName: "moosSessionActionGlyphInk"
        visible: !glyph.rasterSymbol
        source: glyph.rasterSymbol ? "" : glyph.symbol
        anchors.centerIn: parent
        width: Math.round(Math.min(parent.width, parent.height) * 0.74)
        height: width
        transform: Scale { origin.x: icon.width / 2; xScale: glyph.mirrorExit ? -1 : 1 }
        isMask: true
        color: glyph.inkColor
    }
    // Kirigami's GPU mask does not recolour the stroke on the raster backend.
    // The same native icon-theme asset is tinted by Qt Controls on that path.
    Loader {
        anchors.fill: icon
        active: glyph.rasterSymbol
        sourceComponent: ControlsImpl.IconImage {
            objectName: "moosSessionRasterInk"
            name: glyph.symbol
            mirror: glyph.mirrorExit
            color: icon.color
            fillMode: Image.PreserveAspectFit
        }
    }
}
