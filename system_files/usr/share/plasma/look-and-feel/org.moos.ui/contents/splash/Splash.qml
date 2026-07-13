/*
    MoOS UI splash screen (org.moos.ui)

    Stage contract VERIFIED against Breeze's Splash.qml
    (plasma-workspace/lookandfeel/org.kde.breeze/contents/splash/Splash.qml,
    checked 2026-07-10): ksplashqml increments the `stage` property; only
    stage 2 and stage 5 are handled — stage 2 fades the content in, stage 5
    fades the progress indicator out before the desktop appears (max stage 5).
    We must not change those two triggers or the session hands off with a
    frozen splash.

    Premium intro, kept deliberately GPU-LIGHT:
      • logo fade + scale entrance (OutCubic, ~500ms) via render-thread Animators
      • a soft brand glow that "breathes" — faked with concentric translucent
        discs (NO blur, NO shader, no Qt5Compat/GraphicalEffects dependency)
      • a neon cyan→blue light that sweeps the progress line, timed fast
    Everything is transforms + opacity only, so it renders instantly on weak
    GPUs. RTL-safe: the layout is centre-anchored (mirror-neutral) and the only
    horizontal motion is a symmetric light sweep, not directional text.

    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    id: root
    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.Complementary

    readonly property color deepest: Kirigami.Theme.backgroundColor
    readonly property color navy: Kirigami.Theme.alternateBackgroundColor
    readonly property color electric: Kirigami.Theme.highlightColor
    readonly property color cyan: Kirigami.Theme.hoverColor
    readonly property color secondaryText: Kirigami.Theme.disabledTextColor

    color: deepest

    property int stage

    onStageChanged: {
        if (stage == 2) {
            introAnimation.running = true;
        } else if (stage == 5) {
            outroAnimation.running = true;
        }
    }

    // Subtle vertical brand wash (plain linear gradient — no shader) so the
    // black field reads as deep navy, not flat.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.deepest }
            GradientStop { position: 1.0; color: root.navy }
        }
    }

    Item {
        id: content
        anchors.fill: parent
        opacity: 0

        // ── Ambient glow behind the logo ────────────────────────────────────
        // Concentric low-opacity discs approximate a radial glow WITHOUT any
        // blur/shader: alpha stacks toward the centre, so the middle is brighter
        // than the rim. A gentle scale+opacity breathe makes it feel alive.
        Item {
            id: glow
            anchors.centerIn: logo
            width: 360
            height: 360

            SequentialAnimation on scale {
                running: true
                loops: Animation.Infinite
                NumberAnimation { from: 0.95; to: 1.06; duration: 1700; easing.type: Easing.InOutSine }
                NumberAnimation { from: 1.06; to: 0.95; duration: 1700; easing.type: Easing.InOutSine }
            }
            SequentialAnimation on opacity {
                running: true
                loops: Animation.Infinite
                NumberAnimation { from: 0.75; to: 1.0; duration: 1700; easing.type: Easing.InOutSine }
                NumberAnimation { from: 1.0; to: 0.75; duration: 1700; easing.type: Easing.InOutSine }
            }

            Rectangle { anchors.centerIn: parent; width: 360; height: 360; radius: 180; color: root.electric; opacity: 0.030 }
            Rectangle { anchors.centerIn: parent; width: 290; height: 290; radius: 145; color: root.electric; opacity: 0.035 }
            Rectangle { anchors.centerIn: parent; width: 220; height: 220; radius: 110; color: root.electric; opacity: 0.040 }
            Rectangle { anchors.centerIn: parent; width: 160; height: 160; radius: 80;  color: root.cyan; opacity: 0.045 }
            Rectangle { anchors.centerIn: parent; width: 100; height: 100; radius: 50;  color: root.cyan; opacity: 0.055 }
        }

        Image {
            id: logo
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -Math.round(parent.height * 0.04)

            asynchronous: true
            source: "images/moos-logo.png"
            width: 220
            height: 220
            fillMode: Image.PreserveAspectFit
            sourceSize.width: 220
            sourceSize.height: 220

            // Pre-scaled; the intro ScaleAnimator settles it to 1.0.
            scale: 0.92
        }

        // ── Neon progress line ──────────────────────────────────────────────
        // A dim track with a bright cyan→blue light pill sweeping across it. The
        // pill's gradient fades to transparent at both ends so it reads as a
        // moving glow, not a hard bar.
        Rectangle {
            id: progressTrack
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: logo.bottom
            anchors.topMargin: 46

            width: 240
            height: 3
            radius: height / 2
            Kirigami.Theme.inherit: false
            Kirigami.Theme.colorSet: Kirigami.Theme.Button
            color: Kirigami.Theme.backgroundColor
            clip: true

            Rectangle {
                id: sweep
                width: 96
                height: parent.height
                radius: height / 2
                x: -width

                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: Qt.rgba(root.cyan.r, root.cyan.g, root.cyan.b, 0) }
                    GradientStop { position: 0.5; color: root.cyan }
                    GradientStop { position: 1.0; color: Qt.rgba(root.electric.r, root.electric.g, root.electric.b, 0) }
                }

                NumberAnimation on x {
                    from: -sweep.width
                    to: progressTrack.width
                    duration: 900
                    loops: Animation.Infinite
                    easing.type: Easing.InOutQuad
                    running: true
                }
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 32

            text: "MoOS"
            color: root.secondaryText
            font.family: "IBM Plex Sans"
            font.pixelSize: 14
            font.letterSpacing: 2
            textFormat: Text.PlainText
            Accessible.name: text
            Accessible.role: Accessible.StaticText
        }
    }

    // Entrance: fade the whole scene in while the logo settles up to full size.
    // Render-thread Animators (OpacityAnimator/ScaleAnimator) so weak GPUs stay
    // smooth. ~500ms OutCubic = quick, premium, never sluggish.
    ParallelAnimation {
        id: introAnimation
        running: false

        OpacityAnimator {
            target: content
            from: 0
            to: 1
            duration: 500
            easing.type: Easing.OutCubic
        }
        ScaleAnimator {
            target: logo
            from: 0.92
            to: 1.0
            duration: 520
            easing.type: Easing.OutCubic
        }
    }

    // Stage 5: fade the progress line out before the desktop takes over. No
    // `from` so it eases down from whatever its current opacity is (no snap).
    OpacityAnimator {
        id: outroAnimation
        running: false
        target: progressTrack
        to: 0
        duration: 300
        easing.type: Easing.OutCubic
    }
}
