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

        // The art's slow bob. It drifted down and straight back up with no gap at
        // all — a 100% duty cycle, running on the DEFAULT desktop, and an infinite
        // QML animation repaints the whole window for as long as it runs (about
        // 11% of a CPU core whatever the item's size). Every looping animation in
        // this package now rests; here the rest reads as a hover at each end of
        // the drift, which is what a floating object actually does, and it halves
        // the cost of the calm default level.
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
            PauseAnimation { duration: 2600 }
            NumberAnimation {
                target: floatShift
                property: "y"
                to: -2.5
                duration: 3100
                easing.type: Easing.InOutSine
            }
            PauseAnimation { duration: 2600 }
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

            // Fog is the only condition whose ribbons never stopped drifting —
            // the two sweeps ran back to back, so the loop was at a 100% duty
            // cycle and the whole wallpaper repainted for as long as the forecast
            // said fog. Fog settles; a pause at each end of the drift is truer to
            // it than a permanent slide, and it is what keeps this level calm.
            SequentialAnimation on x {
                running: scene.motionEnabled && scene.kind === "fog"
                loops: Animation.Infinite
                PauseAnimation { duration: fogRibbon.index * 420 }
                NumberAnimation {
                    to: scene.width * 0.29
                    duration: 2600
                    easing.type: Easing.InOutSine
                }
                PauseAnimation { duration: 2400 }
                NumberAnimation {
                    to: scene.width * 0.18
                    duration: 2600
                    easing.type: Easing.InOutSine
                }
                PauseAnimation { duration: 2400 }
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
