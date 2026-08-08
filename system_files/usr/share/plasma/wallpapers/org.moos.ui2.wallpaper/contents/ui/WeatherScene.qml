// Local 3D weather artwork with lightweight condition motion layered in QML.
pragma ComponentBehavior: Bound

import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: scene

    required property string kind
    required property bool motionEnabled
    required property bool accentMotion

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

        // sourceSize is ONE QSize property, not two. Writing `sourceSize.height:
        // sourceSize.width` makes a component of it depend on a component of itself,
        // so Qt reports "Binding loop detected for property sourceSize.height" and
        // resolves it the only way it can: by DROPPING the binding. The art then
        // decodes at a stale height instead of the intended 2x supersample, and
        // plasmashell logs the loop on every load and every condition change.
        //
        // That noise is not free. This project's stated test for a UI2 regression is
        // "no QML error appeared in the journal" — a permanent loop message poisons
        // the one signal we use to detect the next bug.
        //
        // Derive the pixel size once and assign the whole QSize in a single binding.
        Image {
            id: art
            anchors.fill: parent
            readonly property int artPx: Math.max(256, Math.round(art.width * 2))
            source: Qt.resolvedUrl("../images/weather/" + scene.kind + ".png")
            sourceSize: Qt.size(art.artPx, art.artPx)
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
            asynchronous: true
        }

        // A finite pulse fired by a sparse timer, not an always-running animation.
        // On this 4K/HDR desktop the old endless bob held plasmashell at 10.25%
        // even in Gentle and 11.3% in Alive; Still immediately fell to 0.87%.
        // PauseAnimation inside an infinite group did not make the render driver
        // idle enough. This pulse occupies 1.8 s of a 60 s Gentle cadence (3%)
        // and 1.8 s of a 45 s Alive cadence (4%); the timer costs no frame.
        Timer {
            id: floatCadence
            interval: scene.accentMotion ? 45000 : 60000
            repeat: true
            triggeredOnStart: true
            running: scene.motionEnabled && scene.visible
            onTriggered: floatPulse.restart()
            onRunningChanged: {
                if (!running) {
                    floatPulse.stop()
                    floatShift.y = 0
                }
            }
        }

        SequentialAnimation {
            id: floatPulse
            PropertyAction {
                target: floatShift
                property: "y"
                value: 0
            }
            NumberAnimation {
                target: floatShift
                property: "y"
                to: 2.5
                duration: 500
                easing.type: Easing.InOutSine
            }
            NumberAnimation {
                target: floatShift
                property: "y"
                to: -2.5
                duration: 800
                easing.type: Easing.InOutSine
            }
            NumberAnimation {
                target: floatShift
                property: "y"
                to: 0
                duration: 500
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

            Timer {
                id: rainCadence
                interval: 20000
                repeat: true
                triggeredOnStart: true
                running: scene.motionEnabled && scene.visible
                    && scene.accentMotion && scene.kind === "rain"
                onTriggered: rainBurst.restart()
                onRunningChanged: {
                    if (!running) {
                        rainBurst.stop()
                        rainDrop.y = scene.height * 0.58
                        rainDrop.opacity = 0
                    }
                }
            }

            SequentialAnimation {
                id: rainBurst
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

            Timer {
                id: snowCadence
                interval: 24000
                repeat: true
                triggeredOnStart: true
                running: scene.motionEnabled && scene.visible
                    && scene.accentMotion && scene.kind === "snow"
                onTriggered: snowBurst.restart()
                onRunningChanged: {
                    if (!running) {
                        snowBurst.stop()
                        snowFlake.y = scene.height * 0.56
                        snowFlake.opacity = 0
                        snowSway.x = 0
                    }
                }
            }

            SequentialAnimation {
                id: snowBurst
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
            transform: Translate { id: fogShift }

            Timer {
                id: fogCadence
                interval: 30000
                repeat: true
                triggeredOnStart: true
                running: scene.motionEnabled && scene.visible
                    && scene.accentMotion && scene.kind === "fog"
                onTriggered: fogBurst.restart()
                onRunningChanged: {
                    if (!running) {
                        fogBurst.stop()
                        fogShift.x = 0
                    }
                }
            }

            SequentialAnimation {
                id: fogBurst
                PauseAnimation { duration: fogRibbon.index * 420 }
                NumberAnimation {
                    target: fogShift
                    property: "x"
                    to: scene.width * 0.06
                    duration: 1200
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: fogShift
                    property: "x"
                    to: -scene.width * 0.05
                    duration: 1200
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: fogShift
                    property: "x"
                    to: 0
                    duration: 1200
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

        Timer {
            id: stormCadence
            interval: 30000
            repeat: true
            triggeredOnStart: true
            running: scene.motionEnabled && scene.visible
                && scene.accentMotion && stormFlash.visible
            onTriggered: stormBurst.restart()
            onRunningChanged: {
                if (!running) {
                    stormBurst.stop()
                    stormFlash.opacity = 0
                }
            }
        }

        SequentialAnimation {
            id: stormBurst
            NumberAnimation {
                target: stormFlash; property: "opacity"; to: 0.16; duration: 70
            }
            NumberAnimation {
                target: stormFlash; property: "opacity"; to: 0.02; duration: 100
            }
            NumberAnimation {
                target: stormFlash; property: "opacity"; to: 0.12; duration: 60
            }
            NumberAnimation {
                target: stormFlash; property: "opacity"; to: 0; duration: 360
            }
        }
    }
}
