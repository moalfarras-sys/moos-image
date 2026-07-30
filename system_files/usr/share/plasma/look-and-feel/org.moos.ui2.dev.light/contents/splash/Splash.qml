/*
    MoOS UI — Liquid Glass session splash

    The ksplashqml host increments `stage`; stage 2 reveals the branded frame
    and stage 5 hands off to the desktop. Keep those triggers intact.

    Motion budget: one finite reveal and one progress sweep. The logo, orbital
    geometry and atmosphere are otherwise static, which keeps session startup
    calm and leaves CPU/GPU time to KWin and plasmashell. Plasma animations-off
    bypasses both motions and lands directly on the complete resting frame.

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
    readonly property color electric: Kirigami.Theme.highlightColor
    readonly property color cyan: Kirigami.Theme.hoverColor
    readonly property color violet: Kirigami.Theme.linkColor
    readonly property color secondaryText: Kirigami.Theme.disabledTextColor
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property int heroSize: Math.max(220, Math.min(320,
        Math.round(Math.min(width, height) * 0.34)))

    property int stage

    color: deepest

    function showStaticFrame() {
        revealAnimation.stop();
        progressMotion.stop();
        content.opacity = 1;
        hero.scale = 1;
        progressSweep.x = (progressTrack.width - progressSweep.width) / 2;
    }

    onMotionEnabledChanged: {
        if (!motionEnabled) {
            showStaticFrame();
        }
    }

    onStageChanged: {
        if (stage === 2) {
            progressTrack.opacity = 1;
            if (root.motionEnabled) {
                revealAnimation.restart();
            } else {
                root.showStaticFrame();
            }
        } else if (stage === 5) {
            revealAnimation.stop();
            progressMotion.stop();
            progressTrack.opacity = 0;
        }
    }

    // Static vertical wash: every family member receives its own scheme roles.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.deepest }
            GradientStop { position: 0.58; color: Qt.tint(root.deepest,
                Qt.rgba(root.electric.r, root.electric.g, root.electric.b, 0.035)) }
            GradientStop { position: 1.0; color: root.surface }
        }
    }

    // A quiet asymmetric light field gives depth without driving the render loop.
    Rectangle {
        width: Math.min(root.width, root.height) * 0.92
        height: width
        radius: width / 2
        anchors.centerIn: parent
        anchors.horizontalCenterOffset: -width * 0.16
        color: root.electric
        opacity: 0.018
    }
    Rectangle {
        width: Math.min(root.width, root.height) * 0.64
        height: width
        radius: width / 2
        anchors.centerIn: parent
        anchors.horizontalCenterOffset: width * 0.34
        anchors.verticalCenterOffset: -height * 0.18
        color: root.violet
        opacity: 0.014
    }

    Item {
        id: content
        anchors.fill: parent
        opacity: root.motionEnabled ? 0 : 1

        Item {
            id: hero
            width: root.heroSize
            height: root.heroSize
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -28
            scale: root.motionEnabled ? 0.965 : 1

            // Layered, theme-driven orbital geometry. Nothing here moves.
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.96
                height: width
                radius: width / 2
                color: "transparent"
                border.width: 1
                border.color: Qt.rgba(root.electric.r, root.electric.g,
                    root.electric.b, 0.16)
                rotation: -10
            }
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.78
                height: width
                radius: width / 2
                color: Qt.rgba(root.electric.r, root.electric.g,
                    root.electric.b, 0.025)
                border.width: 1
                border.color: Qt.rgba(root.violet.r, root.violet.g,
                    root.violet.b, 0.24)
                rotation: 14
            }

            Image {
                anchors.centerIn: parent
                width: parent.width
                height: parent.height
                asynchronous: true
                source: "images/ring.png"
                sourceSize: Qt.size(width * 2, height * 2)
                fillMode: Image.PreserveAspectFit
                opacity: 0.34
                smooth: true
                mipmap: true
            }

            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.61
                height: width
                radius: 24
                color: Qt.rgba(root.surface.r, root.surface.g, root.surface.b, 0.32)
                border.width: 1
                border.color: Qt.rgba(root.electric.r, root.electric.g,
                    root.electric.b, 0.20)
            }

            // Protected MoOS identity asset: seating and palette may change;
            // the mark itself is never redrawn or transformed.
            Image {
                id: logo
                anchors.centerIn: parent
                width: parent.width * 0.66
                height: width
                asynchronous: true
                source: "images/moos-logo.png"
                sourceSize: Qt.size(512, 512)
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
            }
        }

        Text {
            id: brandText
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: hero.bottom
            anchors.topMargin: 16
            text: "MoOS"
            textFormat: Text.PlainText
            color: Kirigami.Theme.textColor
            font.family: Qt.application.font.family
            font.pixelSize: 20
            font.weight: Font.DemiBold
            font.letterSpacing: 1.4
            Accessible.name: text
            Accessible.role: Accessible.StaticText
        }

        Rectangle {
            id: progressTrack
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: brandText.bottom
            anchors.topMargin: 20
            width: 240
            height: 4
            radius: 2
            color: Qt.rgba(root.secondaryText.r, root.secondaryText.g,
                root.secondaryText.b, 0.18)
            clip: true

            Rectangle {
                id: progressSweep
                width: 84
                height: parent.height
                radius: parent.radius
                x: (progressTrack.width - width) / 2
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop {
                        position: 0.0
                        color: Qt.rgba(root.cyan.r, root.cyan.g, root.cyan.b, 0)
                    }
                    GradientStop { position: 0.42; color: root.electric }
                    GradientStop { position: 0.66; color: root.violet }
                    GradientStop {
                        position: 1.0
                        color: Qt.rgba(root.violet.r, root.violet.g, root.violet.b, 0)
                    }
                }
            }
        }
    }

    // The only entrance: a restrained 420ms opacity/scale settle.
    ParallelAnimation {
        id: revealAnimation
        running: false

        OpacityAnimator {
            target: content
            from: 0
            to: 1
            duration: 420
            easing.type: Easing.OutCubic
        }
        ScaleAnimator {
            target: hero
            from: 0.965
            to: 1
            duration: 420
            easing.type: Easing.OutCubic
        }
    }

    // The only continuous motion, and only while the host is actually loading.
    NumberAnimation {
        id: progressMotion
        target: progressSweep
        property: "x"
        from: -progressSweep.width
        to: progressTrack.width
        duration: 1100
        loops: Animation.Infinite
        easing.type: Easing.InOutCubic
        running: root.motionEnabled && root.visible
            && root.stage >= 2 && root.stage < 5
    }
}
