/*
    SPDX-FileCopyrightText: 2014 Aleix Pol Gonzalez <aleixpol@blue-systems.com>
    SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity

    SPDX-License-Identifier: GPL-2.0-or-later
*/

// MoOS: Plasma's own lock-screen backdrop, carrying the MoOS session scene.
//
// The lock screen's LockScreenUi.qml instantiates exactly one of these, filling
// the screen underneath everything else it draws, and hands it the wallpaper,
// the clock, the auth stack and the footer to fade. That makes it the one place
// MoOS can paint the lock scene — the legibility veil and the MoOS signature —
// WITHOUT forking LockScreenUi.qml, the file that carries the authenticator
// wiring and that upstream rewrites every release. MoOS did fork it, to draw
// these two things, and had to re-derive it by hand for 6.8 beta 1 and again for
// beta 2. Now the lock screen runs upstream's own file, whatever Plasma ships.
//
// Everything upstream is kept verbatim: the blur, the colour-matrix shader, the
// two states, the transitions and every property the caller sets. The MoOS
// layer is the two items at the end, declared last so they sit above the
// blurred wallpaper and below the clock and the island (z-order follows the
// caller's declaration order, and this whole item is declared first there).
//   · The veil is the greeter's while the screen is idle — the wallpaper is the
//     picture — and deepens to the session scrim as the island comes up, driven
//     by the same `factor` upstream already animates for the blur. No animation
//     of its own, so nothing here can run while the machine sits locked.
//   · The signature is the one the login screen wears, at the same size and in
//     the same corner, so the three session surfaces sign themselves once, in
//     one place, instead of scattering the emblem over the clock and the face.

import QtQuick
import Qt5Compat.GraphicalEffects

import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Item {
    id: wallpaperFader
    property Item clock
    property Item mainStack
    property Item footer
    property alias source: wallpaperBlur.source
    property real factor: 0
    readonly property bool lightColorScheme: Math.max(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b) > 0.5

    property bool alwaysShowClock: false

    state: "on"

    Behavior on factor {
        NumberAnimation {
            target: wallpaperFader
            property: "factor"
            duration: Kirigami.Units.veryLongDuration * 2
            easing.type: Easing.InOutQuad
        }
    }
    FastBlur {
        id: wallpaperBlur
        anchors.fill: parent
        radius: 50 * wallpaperFader.factor
    }
    ShaderEffect {
        id: wallpaperShader
        anchors.fill: parent
        supportsAtlasTextures: true
        property var source: ShaderEffectSource {
            sourceItem: wallpaperBlur
            live: true
            hideSource: true
            textureMirroring: ShaderEffectSource.NoMirroring
        }

        readonly property real contrast: 0.8 * wallpaperFader.factor + (1 - wallpaperFader.factor)
        readonly property real saturation: 1.5 * wallpaperFader.factor + (1 - wallpaperFader.factor)
        readonly property real intensity: (wallpaperFader.lightColorScheme ? 1.6 : 0.7) * wallpaperFader.factor + (1 - wallpaperFader.factor)

        readonly property real transl: (1.0 - contrast) / 2.0;
        readonly property real rval: (1.0 - saturation) * 0.2126;
        readonly property real gval: (1.0 - saturation) * 0.7152;
        readonly property real bval: (1.0 - saturation) * 0.0722;

        property var colorMatrix: Qt.matrix4x4(
            contrast, 0,        0,        0.0,
            0,        contrast, 0,        0.0,
            0,        0,        contrast, 0.0,
            transl,   transl,   transl,   1.0).times(Qt.matrix4x4(
                rval + saturation, rval,     rval,     0.0,
                gval,     gval + saturation, gval,     0.0,
                bval,     bval,     bval + saturation, 0.0,
                0,        0,        0,        1.0)).times(Qt.matrix4x4(
                    intensity, 0,         0,         0,
                    0,         intensity, 0,         0,
                    0,         0,         intensity, 0,
                    0,         0,         0,         1
                ));

        fragmentShader: "qrc:/qt/qml/org/kde/breeze/components/shaders/WallpaperFader.frag.qsb"
    }

    // ── MoOS session scene ─────────────────────────────────────────────────
    readonly property var design: MoUI.Tokens

    Rectangle {
        id: sessionVeil
        anchors.fill: parent
        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: Qt.alpha(Kirigami.Theme.backgroundColor,
                                0.40 + (wallpaperFader.design.sessionScrimTopOpacity - 0.40)
                                       * wallpaperFader.factor)
            }
            GradientStop {
                position: 0.45
                color: Qt.alpha(Kirigami.Theme.backgroundColor,
                                0.08 + (wallpaperFader.design.sessionScrimMidOpacity - 0.08)
                                       * wallpaperFader.factor)
            }
            GradientStop {
                position: 1.0
                color: Qt.alpha(Kirigami.Theme.backgroundColor,
                                0.48 + (wallpaperFader.design.sessionScrimBottomOpacity - 0.48)
                                       * wallpaperFader.factor)
            }
        }
    }

    MoUI.SessionSignature {
        id: sessionSignature
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.leftMargin: Math.max(Kirigami.Units.gridUnit * 2,
                                     Math.round(wallpaperFader.width * 0.028))
        anchors.topMargin: Math.max(Kirigami.Units.gridUnit * 1.6,
                                    Math.round(wallpaperFader.height * 0.04))
        sceneHeight: wallpaperFader.height
        ink: Kirigami.Theme.textColor
        accent: Kirigami.Theme.highlightColor
    }

    states: [
        State {
            name: "on"
            PropertyChanges {
                mainStack.opacity: 1
                footer.opacity: 1
                wallpaperFader.factor: 1
                clock.shadow.opacity: 0
                clock.opacity: 1
            }
        },
        State {
            name: "off"
            PropertyChanges {
                mainStack.opacity: 0
                footer.opacity: 0
                wallpaperFader.factor: 0
                clock.shadow.opacity: wallpaperFader.alwaysShowClock ? 1 : 0
                clock.opacity: wallpaperFader.alwaysShowClock ? 1 : 0
            }
        }
    ]
    transitions: [
        Transition {
            from: "off"
            to: "on"
            //Note: can't use animators as they don't play well with parallelanimations
            NumberAnimation {
                targets: [wallpaperFader.mainStack, wallpaperFader.footer, wallpaperFader.clock]
                property: "opacity"
                duration: Kirigami.Units.veryLongDuration
                easing.type: Easing.InOutQuad
            }
        },
        Transition {
            from: "on"
            to: "off"
            NumberAnimation {
                targets: [wallpaperFader.mainStack, wallpaperFader.footer, wallpaperFader.clock]
                property: "opacity"
                duration: Kirigami.Units.veryLongDuration
                easing.type: Easing.InOutQuad
            }
        }
    ]
}
