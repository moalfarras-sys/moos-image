// Local 3D weather artwork with lightweight condition motion layered in QML.
pragma ComponentBehavior: Bound

import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: scene

    required property string kind
    required property bool motionEnabled

    clip: true

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height) * 0.9
        height: width
        radius: width / 2
        color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                       Kirigami.Theme.highlightColor.g,
                       Kirigami.Theme.highlightColor.b,
                       Kirigami.Theme.backgroundColor.hslLightness > 0.55
                       ? 0.09 : 0.12)
        border.width: 1
        border.color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                              Kirigami.Theme.highlightColor.g,
                              Kirigami.Theme.highlightColor.b, 0.13)
    }

    Item {
        id: floatingArt
        anchors.centerIn: parent
        width: Math.min(scene.width, scene.height) * 0.98
        height: width
        transform: Translate { id: floatShift }

        Image {
            anchors.fill: parent
            source: Qt.resolvedUrl("../images/weather/" + scene.kind + ".png")
            sourceSize.width: Math.max(256, Math.round(width * 2))
            sourceSize.height: sourceSize.width
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
            asynchronous: true
        }

        SequentialAnimation {
            running: scene.motionEnabled && scene.visible
            loops: Animation.Infinite
            NumberAnimation {
                target: floatShift
                property: "y"
                from: -2.5
                to: 2.5
                duration: 3100
                easing.type: Easing.InOutSine
            }
            NumberAnimation {
                target: floatShift
                property: "y"
                to: -2.5
                duration: 3100
                easing.type: Easing.InOutSine
            }
        }
    }

    // Rain keeps a small phase difference between drops so the motion reads as
    // weather rather than a synchronized loading indicator.
    Repeater {
        model: scene.kind === "rain" ? 5 : 0
        delegate: Rectangle {
            id: rainDrop
            required property int index

            width: Math.max(2, scene.width * 0.014)
            height: scene.height * 0.1
            radius: width / 2
            x: scene.width * (0.29 + index * 0.11)
            y: scene.height * 0.58
            color: Kirigami.Theme.highlightColor
            opacity: 0
            rotation: 8

            SequentialAnimation {
                running: scene.motionEnabled && scene.kind === "rain"
                loops: Animation.Infinite
                PauseAnimation { duration: rainDrop.index * 180 }
                ParallelAnimation {
                    NumberAnimation {
                        target: rainDrop
                        property: "y"
                        from: scene.height * 0.58
                        to: scene.height * 0.86
                        duration: 760
                        easing.type: Easing.InQuad
                    }
                    SequentialAnimation {
                        NumberAnimation {
                            target: rainDrop
                            property: "opacity"
                            to: 0.7
                            duration: 170
                        }
                        NumberAnimation {
                            target: rainDrop
                            property: "opacity"
                            to: 0
                            duration: 590
                        }
                    }
                }
                PauseAnimation { duration: 900 - rainDrop.index * 180 }
            }
        }
    }

    Repeater {
        model: scene.kind === "snow" ? 6 : 0
        delegate: Rectangle {
            id: snowFlake
            required property int index

            width: Math.max(3, scene.width * (0.018 + (index % 2) * 0.008))
            height: width
            radius: width / 2
            x: scene.width * (0.25 + index * 0.095)
            y: scene.height * 0.56
            color: Kirigami.Theme.highlightedTextColor
            opacity: 0
            transform: Translate { id: snowSway }

            SequentialAnimation {
                running: scene.motionEnabled && scene.kind === "snow"
                loops: Animation.Infinite
                PauseAnimation { duration: snowFlake.index * 260 }
                ParallelAnimation {
                    NumberAnimation {
                        target: snowFlake
                        property: "y"
                        from: scene.height * 0.56
                        to: scene.height * 0.87
                        duration: 1600
                        easing.type: Easing.InOutSine
                    }
                    SequentialAnimation {
                        NumberAnimation {
                            target: snowSway
                            property: "x"
                            from: 0
                            to: scene.width * 0.025
                            duration: 800
                            easing.type: Easing.InOutSine
                        }
                        NumberAnimation {
                            target: snowSway
                            property: "x"
                            to: -scene.width * 0.02
                            duration: 800
                            easing.type: Easing.InOutSine
                        }
                    }
                    SequentialAnimation {
                        NumberAnimation {
                            target: snowFlake
                            property: "opacity"
                            to: 0.82
                            duration: 360
                        }
                        NumberAnimation {
                            target: snowFlake
                            property: "opacity"
                            to: 0
                            duration: 1240
                        }
                    }
                }
                PauseAnimation { duration: 1560 - snowFlake.index * 260 }
            }
        }
    }

    Repeater {
        model: scene.kind === "fog" ? 3 : 0
        delegate: Rectangle {
            id: fogRibbon
            required property int index

            width: scene.width * (0.54 - index * 0.05)
            height: Math.max(2, scene.height * 0.018)
            radius: height / 2
            x: scene.width * 0.23
            y: scene.height * (0.58 + index * 0.08)
            color: Kirigami.Theme.disabledTextColor
            opacity: 0.38

            SequentialAnimation on x {
                running: scene.motionEnabled && scene.kind === "fog"
                loops: Animation.Infinite
                PauseAnimation { duration: fogRibbon.index * 420 }
                NumberAnimation {
                    to: scene.width * 0.29
                    duration: 2600
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    to: scene.width * 0.18
                    duration: 2600
                    easing.type: Easing.InOutSine
                }
            }
        }
    }

    Rectangle {
        id: stormFlash
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height) * 0.72
        height: width
        radius: width / 2
        visible: scene.kind === "storm"
        color: Kirigami.Theme.neutralTextColor
        opacity: 0

        SequentialAnimation on opacity {
            running: scene.motionEnabled && stormFlash.visible
            loops: Animation.Infinite
            PauseAnimation { duration: 3900 }
            NumberAnimation { to: 0.16; duration: 70 }
            NumberAnimation { to: 0.02; duration: 100 }
            NumberAnimation { to: 0.12; duration: 60 }
            NumberAnimation { to: 0; duration: 360 }
        }
    }
}
