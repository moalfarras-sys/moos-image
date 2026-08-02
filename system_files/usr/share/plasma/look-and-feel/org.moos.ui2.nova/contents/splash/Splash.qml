/*
    MoOS session splash — the calm branded threshold.

    ksplashqml increments `stage`; stage 2 reveals the content and stage 5
    hands off to the desktop. Motion is finite: one 460 ms entrance and short
    stage interpolation. There are no decorative loops, and no full-screen
    curve: the composition is the mineral depth field, the brand, and one
    progress line — the same quiet language as the session islands.

    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    id: root

    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.Complementary

    readonly property color deepest: Kirigami.Theme.backgroundColor
    readonly property color surface: Kirigami.Theme.alternateBackgroundColor
    readonly property color accentA: Kirigami.Theme.highlightColor
    readonly property color accentB: Kirigami.Theme.linkColor
    readonly property color ink: Kirigami.Theme.textColor
    readonly property color muted: Kirigami.Theme.disabledTextColor
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property bool rtl: Qt.locale().textDirection === Qt.RightToLeft
    readonly property real progress: Math.max(0.08, Math.min(1, stage / 5))
    readonly property int logoSize: Math.max(92, Math.min(146,
        Math.round(Math.min(width, height) * 0.14)))

    property int stage

    color: deepest

    function showStaticFrame() {
        revealAnimation.stop();
        content.opacity = 1;
        contentShift.y = 0;
    }

    onMotionEnabledChanged: {
        if (!motionEnabled) {
            showStaticFrame();
        }
    }

    onStageChanged: {
        if (stage === 2) {
            content.opacity = root.motionEnabled ? 0 : 1;
            if (root.motionEnabled) {
                revealAnimation.restart();
            } else {
                root.showStaticFrame();
            }
        } else if (stage >= 5) {
            revealAnimation.stop();
        }
    }

    // A mineral depth field. It is static and theme-native.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: root.deepest }
            GradientStop {
                position: 0.58
                color: Qt.tint(root.deepest,
                    Qt.rgba(root.accentB.r, root.accentB.g, root.accentB.b, 0.04))
            }
            GradientStop { position: 1; color: root.surface }
        }
    }

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.18
        width: Math.min(parent.width * 0.72, parent.height * 1.18)
        height: width
        radius: width / 2
        color: root.accentA
        opacity: 0.018
    }

    Item {
        id: content
        anchors.fill: parent
        opacity: root.motionEnabled ? 0 : 1
        transform: Translate {
            id: contentShift
            y: root.motionEnabled ? Kirigami.Units.gridUnit * 0.8 : 0
        }

        Item {
            id: brandStage
            width: root.logoSize
            height: width
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * 0.34 - height / 2

            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 1.42
                height: width
                radius: width / 2
                color: root.accentA
                opacity: 0.07
            }
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 1.15
                height: width
                radius: width / 2
                color: root.accentB
                opacity: 0.045
            }
            Image {
                anchors.fill: parent
                source: "images/moos-logo.png"
                sourceSize: Qt.size(512, 512)
                fillMode: Image.PreserveAspectFit
                asynchronous: false
                smooth: true
                mipmap: true
            }
        }

        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            y: brandStage.y + brandStage.height + Kirigami.Units.gridUnit * 1.25
            spacing: Kirigami.Units.smallSpacing

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "MoOS"
                textFormat: Text.PlainText
                color: root.ink
                font.family: "IBM Plex Sans Arabic"
                font.pixelSize: Math.max(20, Math.round(root.logoSize * 0.19))
                font.weight: Font.DemiBold
                font.letterSpacing: 1.8
                renderType: Text.QtRendering
                Accessible.name: text
                Accessible.role: Accessible.StaticText
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.rtl
                    ? "نجهّز مساحتك"
                    : "Preparing your space"
                textFormat: Text.PlainText
                color: root.ink
                opacity: 0.72
                font.family: "IBM Plex Sans Arabic"
                font.pixelSize: Math.max(12, Math.round(root.logoSize * 0.105))
                font.weight: Font.Normal
                renderType: Text.QtRendering
                Accessible.name: text
                Accessible.role: Accessible.StaticText
            }
        }

        Rectangle {
            id: progressTrack
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * 0.72 - height / 2
            width: Math.max(220, Math.min(360, parent.width * 0.24))
            height: 4
            radius: height / 2
            color: Qt.rgba(root.ink.r, root.ink.g, root.ink.b, 0.15)
            clip: true
            opacity: root.stage >= 5 ? 0 : 1

            Behavior on opacity {
                NumberAnimation {
                    duration: root.motionEnabled ? Kirigami.Units.shortDuration : 0
                    easing.type: Easing.OutCubic
                }
            }

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width * root.progress
                height: parent.height
                radius: height / 2
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: root.accentA }
                    GradientStop { position: 1; color: root.accentB }
                }
                Behavior on width {
                    NumberAnimation {
                        duration: root.motionEnabled ? 260 : 0
                        easing.type: Easing.OutCubic
                    }
                }
            }
        }
    }

    ParallelAnimation {
        id: revealAnimation
        running: false

        OpacityAnimator {
            target: content
            from: 0
            to: 1
            duration: 460
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: contentShift
            property: "y"
            from: Kirigami.Units.gridUnit * 0.8
            to: 0
            duration: 460
            easing.type: Easing.OutCubic
        }
    }
}
