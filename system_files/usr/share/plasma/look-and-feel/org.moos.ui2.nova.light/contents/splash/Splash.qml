/*
    MoOS UI2 splash screen (org.moos.ui2) — v2

    Stage contract VERIFIED against Breeze's Splash.qml
    (plasma-workspace/lookandfeel/org.kde.breeze/contents/splash/Splash.qml,
    checked 2026-07-10): ksplashqml increments the `stage` property; only
    stage 2 and stage 5 are handled — stage 2 fades the content in, stage 5
    fades the progress indicator out before the desktop appears (max stage 5).
    We must not change those two triggers or the session hands off with a
    frozen splash.

    Premium intro — "Orbital Reveal":
      • The ring appears first as a point and expands outward (scale 0→1)
      • The logo materialises FROM INSIDE the ring — the ring births the mark
      • 3 energy particles shoot outward from the centre during the reveal
      • A multi-lane progress bar with 3 sweeps in cyan/violet/electric
      • The MoOS wordmark types in letter by letter

    GPU-LIGHT: transforms + opacity only via render-thread Animators, NO blur,
    NO shader, no Qt5Compat/GraphicalEffects. RTL-safe: centre-anchored.

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
    readonly property color violet: Qt.rgba(0.545, 0.361, 0.965, 1.0) // #8B5CF6
    readonly property color secondaryText: Kirigami.Theme.disabledTextColor

    color: deepest

    property int stage

    onStageChanged: {
        if (stage == 2) {
            introAnimation.running = true;
            ringReveal.running = true;
            shineSweep.running = true;
            bloomFlash.running = true;
            particleBurst.running = true;
            typewriterTimer.running = true;
        } else if (stage == 5) {
            outroAnimation.running = true;
        }
    }

    // Subtle vertical brand wash
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

        // Arrival bloom: soft disc that expands and fades
        Rectangle {
            id: bloomFlash
            anchors.centerIn: logo
            width: 150
            height: 150
            radius: 75
            color: root.cyan
            opacity: 0
            scale: 0.4
            property alias running: bloomAnim.running
            ParallelAnimation {
                id: bloomAnim
                running: false
                NumberAnimation { target: bloomFlash; property: "scale"
                    from: 0.4; to: 2.8; duration: 1100; easing.type: Easing.OutCubic }
                SequentialAnimation {
                    NumberAnimation { target: bloomFlash; property: "opacity"
                        from: 0; to: 0.55; duration: 200; easing.type: Easing.OutCubic }
                    NumberAnimation { target: bloomFlash; property: "opacity"
                        to: 0; duration: 900; easing.type: Easing.InCubic }
                }
            }
        }

        // ── Orbital ring — starts as a point, expands to full size ──────────
        // This is the "3D reveal": the ring births the logo from inside it.
        Image {
            id: orbitalRing
            anchors.centerIn: logo
            width: 330
            height: 330
            asynchronous: true
            source: "images/ring.png"
            sourceSize.width: 660
            sourceSize.height: 660
            opacity: 0
            scale: 0.0

            RotationAnimator on rotation {
                from: 0; to: 360
                duration: 8000
                loops: Animation.Infinite
                running: true
            }

            // Ring reveal: scale from 0 to 1 with bounce
            ParallelAnimation {
                id: ringReveal
                running: false
                NumberAnimation {
                    target: orbitalRing; property: "scale"
                    from: 0.0; to: 1.0
                    duration: 900; easing.type: Easing.OutBack; easing.overshoot: 1.2
                }
                NumberAnimation {
                    target: orbitalRing; property: "opacity"
                    from: 0; to: 0.85
                    duration: 600; easing.type: Easing.OutCubic
                }
            }
        }

        // ── Counter-rotating inner ring (3D depth) ──────────────────────────
        Image {
            anchors.centerIn: logo
            width: 260
            height: 260
            asynchronous: true
            source: "images/ring.png"
            sourceSize.width: 520
            sourceSize.height: 520
            opacity: orbitalRing.opacity * 0.45
            scale: orbitalRing.scale * 0.85
            RotationAnimator on rotation {
                from: 360; to: 0
                duration: 14000
                loops: Animation.Infinite
                running: true
            }
        }

        // ── The logo ────────────────────────────────────────────────────────
        Image {
            id: logo
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -Math.round(parent.height * 0.04)

            asynchronous: true
            source: "images/moos-logo.png"
            width: 236
            height: 236
            fillMode: Image.PreserveAspectFit
            sourceSize.width: 512
            sourceSize.height: 512
            smooth: true
            mipmap: true
            scale: 0.0

            // Logo breathing after arrival
            SequentialAnimation on scale {
                id: logoBreathe
                running: false
                loops: Animation.Infinite
                NumberAnimation { from: 1.0; to: 1.025; duration: 2400; easing.type: Easing.InOutSine }
                NumberAnimation { from: 1.025; to: 1.0; duration: 2400; easing.type: Easing.InOutSine }
            }

            // Studio light-sweep across the mark
            Item {
                anchors.fill: parent
                clip: true
                Rectangle {
                    id: shine
                    width: parent.width * 0.42
                    height: parent.height * 1.8
                    rotation: 18
                    y: -parent.height * 0.4
                    x: -width * 1.4
                    opacity: 0.0
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: Qt.rgba(root.cyan.r, root.cyan.g, root.cyan.b, 0) }
                        GradientStop { position: 0.5; color: Qt.rgba(root.cyan.r, root.cyan.g, root.cyan.b, 0.6) }
                        GradientStop { position: 1.0; color: Qt.rgba(root.cyan.r, root.cyan.g, root.cyan.b, 0) }
                    }
                    SequentialAnimation {
                        id: shineSweep
                        running: false
                        PauseAnimation { duration: 620 }
                        ParallelAnimation {
                            NumberAnimation { target: shine; property: "x"
                                from: -shine.width * 1.4; to: logo.width + shine.width * 0.4
                                duration: 900; easing.type: Easing.InOutSine }
                            SequentialAnimation {
                                NumberAnimation { target: shine; property: "opacity"; to: 0.9; duration: 300 }
                                NumberAnimation { target: shine; property: "opacity"; to: 0.0; duration: 420 }
                            }
                        }
                    }
                }
            }
        }

        // ── Energy particles that shoot outward during reveal ────────────────
        // 3 particles radiating from centre in different directions
        Image {
            id: p1
            source: "images/particle.png"
            width: 16; height: 16
            x: root.width / 2 - 8
            y: root.height * 0.46 - 8
            opacity: 0
            property alias running: p1Anim.running
        }
        Image {
            id: p2
            source: "images/particle.png"
            width: 12; height: 12
            x: root.width / 2 - 6
            y: root.height * 0.46 - 6
            opacity: 0
        }
        Image {
            id: p3
            source: "images/particle.png"
            width: 10; height: 10
            x: root.width / 2 - 5
            y: root.height * 0.46 - 5
            opacity: 0
        }

        ParallelAnimation {
            id: particleBurst
            running: false

            // Particle 1: shoots upper-right
            SequentialAnimation {
                PauseAnimation { duration: 400 }
                ParallelAnimation {
                    id: p1Anim
                    NumberAnimation { target: p1; property: "x"; to: root.width * 0.62; duration: 1200; easing.type: Easing.OutCubic }
                    NumberAnimation { target: p1; property: "y"; to: root.height * 0.28; duration: 1200; easing.type: Easing.OutCubic }
                    SequentialAnimation {
                        NumberAnimation { target: p1; property: "opacity"; to: 0.9; duration: 200 }
                        NumberAnimation { target: p1; property: "opacity"; to: 0; duration: 1000; easing.type: Easing.InCubic }
                    }
                }
            }

            // Particle 2: shoots lower-left
            SequentialAnimation {
                PauseAnimation { duration: 500 }
                ParallelAnimation {
                    NumberAnimation { target: p2; property: "x"; to: root.width * 0.35; duration: 1100; easing.type: Easing.OutCubic }
                    NumberAnimation { target: p2; property: "y"; to: root.height * 0.62; duration: 1100; easing.type: Easing.OutCubic }
                    SequentialAnimation {
                        NumberAnimation { target: p2; property: "opacity"; to: 0.8; duration: 180 }
                        NumberAnimation { target: p2; property: "opacity"; to: 0; duration: 920; easing.type: Easing.InCubic }
                    }
                }
            }

            // Particle 3: shoots upper-left
            SequentialAnimation {
                PauseAnimation { duration: 600 }
                ParallelAnimation {
                    NumberAnimation { target: p3; property: "x"; to: root.width * 0.38; duration: 1000; easing.type: Easing.OutCubic }
                    NumberAnimation { target: p3; property: "y"; to: root.height * 0.30; duration: 1000; easing.type: Easing.OutCubic }
                    SequentialAnimation {
                        NumberAnimation { target: p3; property: "opacity"; to: 0.7; duration: 160 }
                        NumberAnimation { target: p3; property: "opacity"; to: 0; duration: 840; easing.type: Easing.InCubic }
                    }
                }
            }
        }

        // ── Multi-lane neon progress bar ─────────────────────────────────────
        // Three sweeps in cyan/violet/electric racing across the track
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

            // Sweep 1: cyan (fastest)
            Rectangle {
                id: sweep1
                width: 80
                height: parent.height
                radius: height / 2
                x: -width
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: Qt.rgba(root.cyan.r, root.cyan.g, root.cyan.b, 0) }
                    GradientStop { position: 0.5; color: root.cyan }
                    GradientStop { position: 1.0; color: Qt.rgba(root.cyan.r, root.cyan.g, root.cyan.b, 0) }
                }
                NumberAnimation on x {
                    from: -sweep1.width
                    to: progressTrack.width
                    duration: 800
                    loops: Animation.Infinite
                    easing.type: Easing.InOutQuad
                    running: true
                }
            }

            // Sweep 2: violet (medium speed, delayed)
            Rectangle {
                id: sweep2
                width: 64
                height: parent.height
                radius: height / 2
                x: -width
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: Qt.rgba(root.violet.r, root.violet.g, root.violet.b, 0) }
                    GradientStop { position: 0.5; color: root.violet }
                    GradientStop { position: 1.0; color: Qt.rgba(root.violet.r, root.violet.g, root.violet.b, 0) }
                }
                SequentialAnimation on x {
                    PauseAnimation { duration: 300 }
                    NumberAnimation {
                        from: -sweep2.width
                        to: progressTrack.width
                        duration: 1100
                        loops: Animation.Infinite
                        easing.type: Easing.InOutQuad
                    }
                }
            }

            // Sweep 3: electric blue (slowest, most delayed)
            Rectangle {
                id: sweep3
                width: 48
                height: parent.height
                radius: height / 2
                x: -width
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: Qt.rgba(root.electric.r, root.electric.g, root.electric.b, 0) }
                    GradientStop { position: 0.5; color: root.electric }
                    GradientStop { position: 1.0; color: Qt.rgba(root.electric.r, root.electric.g, root.electric.b, 0) }
                }
                SequentialAnimation on x {
                    PauseAnimation { duration: 550 }
                    NumberAnimation {
                        from: -sweep3.width
                        to: progressTrack.width
                        duration: 1400
                        loops: Animation.Infinite
                        easing.type: Easing.InOutQuad
                    }
                }
            }
        }

        // ── Typewriter MoOS wordmark ─────────────────────────────────────────
        Text {
            id: brandText
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 32

            property string fullText: "MoOS"
            property int charCount: 0

            text: fullText.substring(0, charCount)
            color: root.secondaryText
            font.family: "IBM Plex Sans"
            font.pixelSize: 14
            font.letterSpacing: 2
            textFormat: Text.PlainText
            Accessible.name: fullText
            Accessible.role: Accessible.StaticText

            Timer {
                id: typewriterTimer
                interval: 140
                repeat: true
                running: false
                onTriggered: {
                    if (brandText.charCount < brandText.fullText.length) {
                        brandText.charCount++;
                    } else {
                        stop();
                    }
                }
            }
        }
    }

    // Entrance: fade the whole scene in while the logo zooms from 0 to full.
    // OutBack gives the confident settle. Ring expands first (via ringReveal),
    // then the logo pops out of it.
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
            from: 0.0
            to: 1.0
            duration: 850
            easing.type: Easing.OutBack
        }
        // After the logo lands, start the breathing
        SequentialAnimation {
            PauseAnimation { duration: 900 }
            ScriptAction { script: logoBreathe.running = true }
        }
    }

    // Stage 5: fade the progress line out before the desktop takes over.
    OpacityAnimator {
        id: outroAnimation
        running: false
        target: progressTrack
        to: 0
        duration: 300
        easing.type: Easing.OutCubic
    }
}
