/*
    Tidal Horizon Portal — the shared MoOS doorway motif.

    This component provides a soft ambient aura (glassmorphism glow) in the background.
    It contains no timer, loop, shader, hard-coded palette, logo, or input handler.
    Splash, login, lock and logout supply the same semantic colours.

    The signature is now an organic, soft dual-light ambient glow emitting from the bottom
    corners, replacing the old sharp cubic line. It acts as a cinematic backdrop.

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import Qt5Compat.GraphicalEffects

Item {
    id: portal

    property color accentA: "#4ED7C8"
    property color accentB: "#78AFFF"
    property color ink: "#E8F1EF"
    property color surface: "#1D2529"
    property real reveal: 1
    property real intensity: 1
    property bool compact: false

    opacity: Math.max(0, Math.min(1, reveal))

    // Premium Floating Glass Frame
    Rectangle {
        id: glassFrame
        anchors.fill: parent
        anchors.margins: portal.height * 0.04
        
        // Ultra-smooth deep radius (Apple-like Squircle approximation)
        radius: Math.min(width, height) * 0.25
        
        // Deeply translucent glass body
        color: Qt.rgba(portal.surface.r, portal.surface.g, portal.surface.b, 0.25 * portal.intensity)
        
        // Soft rim light mimicking glass reflection
        border.width: Math.max(1, portal.height * 0.003)
        border.color: Qt.rgba(portal.ink.r, portal.ink.g, portal.ink.b, 0.18 * portal.intensity)
        
        layer.enabled: true
    }

    // Elegant cinematic drop shadow
    DropShadow {
        anchors.fill: glassFrame
        source: glassFrame
        radius: 80
        samples: 65
        color: Qt.rgba(0, 0, 0, 0.45 * portal.intensity)
        verticalOffset: 24
        transparentBorder: true
    }
}
