import QtQuick
import Qt5Compat.GraphicalEffects
import org.kde.kirigami as Kirigami

// Application expression of the shared MoOS Tidal Horizon geometry.
//
// Splash, login, lock, logout, Launcher and first-party apps all use the same
// soft ambient light aura.
// This component has no loop, timer, shader or input handler.
// SPDX-License-Identifier: GPL-2.0-or-later
Item {
    id: root

    property color surfaceColor: "#14191c"
    property color primaryColor: "#4ed7c8"
    property color secondaryColor: "#78afff"
    property color luminousColor: "#a8f1e8"
    property real strength: 1.0
    property bool compact: false
    property bool motionEnabled: Kirigami.Units.longDuration > 1
    property bool animateIn: false

    implicitWidth: 720
    implicitHeight: 240
    clip: false

    property real reveal: animateIn && motionEnabled ? 0.0 : 1.0

    Component.onCompleted: {
        if (root.animateIn && root.motionEnabled)
            entrance.start()
    }

    NumberAnimation {
        id: entrance
        target: root
        property: "reveal"
        from: 0.0
        to: 1.0
        duration: 320
        easing.type: Easing.OutCubic
    }

    opacity: Math.max(0, Math.min(1, reveal))

    // Premium Floating Glass Frame
    Rectangle {
        id: glassFrame
        anchors.fill: parent
        anchors.margins: root.height * 0.04
        
        // Ultra-smooth deep radius (Apple-like Squircle approximation)
        radius: Math.min(width, height) * 0.25
        
        // Deeply translucent glass body
        color: Qt.rgba(root.surfaceColor.r, root.surfaceColor.g, root.surfaceColor.b, 0.25 * root.strength)
        
        // Soft rim light mimicking glass reflection
        border.width: Math.max(1, root.height * 0.003)
        border.color: Qt.rgba(root.luminousColor.r, root.luminousColor.g, root.luminousColor.b, 0.18 * root.strength)
        
        layer.enabled: true
    }

    // Elegant cinematic drop shadow
    DropShadow {
        anchors.fill: glassFrame
        source: glassFrame
        radius: 80
        samples: 65
        color: Qt.rgba(0, 0, 0, 0.45 * root.strength)
        verticalOffset: 24
        transparentBorder: true
    }
}
