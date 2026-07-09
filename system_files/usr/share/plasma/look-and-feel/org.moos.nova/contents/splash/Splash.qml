/*
    MoOS Nova splash screen (org.moos.nova)

    Stage contract modeled on Breeze's Splash.qml
    (plasma-workspace/lookandfeel/org.kde.breeze/contents/splash/Splash.qml):
    ksplashqml sets the incrementing `stage` property; stage 2 fades the
    content in, stage 5 fades the progress indicator out before the
    desktop appears.

    Deliberately lightweight: no blur, no shaders, no Kirigami dependency —
    scene-graph animators only, so it renders instantly on weak GPUs.

    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick

Rectangle {
    id: root
    color: "#050A14"

    property int stage

    onStageChanged: {
        if (stage == 2) {
            introAnimation.running = true;
        } else if (stage == 5) {
            outroAnimation.running = true;
        }
    }

    Item {
        id: content
        anchors.fill: parent
        opacity: 0

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

            // gentle settle-in: 0.96 -> 1.0
            scale: 0.96
        }

        // Indeterminate progress line
        Rectangle {
            id: progressTrack
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: logo.bottom
            anchors.topMargin: 48

            width: 240
            height: 3
            radius: height / 2
            color: "#2E7BFF"
            opacity: 0.35
            clip: true

            Rectangle {
                id: progressHighlight
                width: 72
                height: parent.height
                radius: height / 2
                color: "#22D3EE"
                x: -width

                NumberAnimation on x {
                    from: -progressHighlight.width
                    to: progressTrack.width
                    duration: 1200
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
            color: "#9FB0C9"
            font.family: "IBM Plex Sans"
            font.pixelSize: 14
            font.letterSpacing: 2
            textFormat: Text.PlainText
            Accessible.name: text
            Accessible.role: Accessible.StaticText
        }
    }

    ParallelAnimation {
        id: introAnimation
        running: false

        OpacityAnimator {
            target: content
            from: 0
            to: 1
            duration: 600
            easing.type: Easing.OutCubic
        }
        ScaleAnimator {
            target: logo
            from: 0.96
            to: 1.0
            duration: 600
            easing.type: Easing.OutCubic
        }
    }

    OpacityAnimator {
        id: outroAnimation
        running: false
        target: progressTrack
        from: 0.35
        to: 0
        duration: 300
        easing.type: Easing.OutCubic
    }
}
