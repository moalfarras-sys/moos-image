// org.moos.ui2.greeter — the MoOS login scene.
//
// WHY A WALLPAPER PLUGIN
//   plasma-login-manager's greeter QML is compiled INTO the binary
//   (qrc:/qt/qml/org/kde/plasma/login/Main.qml) — the auth card cannot be
//   re-skinned from the filesystem. The one surface the image DOES own is the
//   wallpaper process (plasma-login-wallpaper loads any Plasma/Wallpaper
//   KPackage named by WallpaperPluginId, config from
//   [Greeter][Wallpaper][<id>][General] — verified against
//   plasma-login-manager v6.7.2 wallpaperintegration.cpp). So the whole MoOS
//   login identity — the animated emblem, the wordmark, the ambient light —
//   lives here, drawn behind the stock auth card. The greeter blurs this
//   scene while its UI is visible (WallpaperFader), which reads as depth:
//   sharp brand at idle, soft glow behind the password field.
//
// MOTION BUDGET
//   Same philosophy as the boot splash: Animators only (render thread), no
//   ShaderEffect, no Canvas, no Lottie runtime, no network. All light is
//   pre-baked alpha sprites from artwork/generate_login_scene.py; the scene
//   only moves and fades them.
//
// IMAGE RESOLUTION
//   `Image` accepts what org.kde.image accepted (a file or a MoOS wallpaper
//   package dir) — the login==lock gate in verify_image_experience.py reads
//   the package name straight out of the drop-in, so the config value keeps
//   naming the Graphite package (/usr/share/wallpapers/MoOSUI2Graphite/ — and
//   mind the punctuation here: build.sh greps QML too for wallpaper paths,
//   and a sentence period right after a path reads as part of the path).
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root

    // UI2 Graphite tokens (artwork/moos-ui2/palette.json). The greeter has no
    // user session to follow, so the scene is pinned to the dark half — the
    // same reasoning that pins the drop-in's wallpaper to Graphite.
    readonly property color canvasColor: "#14191C"
    readonly property color textColor: "#E8F1EF"
    readonly property color primaryColor: "#4ED7C8"
    readonly property color cyanAccent: "#22D3EE"
    readonly property color violetAccent: "#8B5CF6"

    readonly property string fallbackImage:
        "/usr/share/wallpapers/MoOSUI2Graphite/contents/images_dark/3840x2160.jpg"

    function resolveImage(value) {
        var v = String(value || "")
        if (v === "") {
            return root.fallbackImage
        }
        if (v.indexOf("file://") === 0) {
            v = v.substring(7)
        }
        if (/\.(jpg|jpeg|png|webp|avif)$/i.test(v)) {
            return v
        }
        if (v.indexOf("MoOSUI2Tide") >= 0) {
            return v + "/contents/images/3840x2160.jpg"
        }
        if (v.indexOf("MoOSUI2") >= 0) {
            return v + "/contents/images_dark/3840x2160.jpg"
        }
        return v
    }

    // Solid graphite behind everything: a missing master degrades to a branded
    // flat colour, never to a black login screen.
    Rectangle {
        anchors.fill: parent
        color: root.canvasColor
    }

    Image {
        id: art
        anchors.fill: parent
        source: "file://" + root.resolveImage(root.configuration.Image)
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        smooth: true
        sourceSize: Qt.size(root.width * Screen.devicePixelRatio,
                            root.height * Screen.devicePixelRatio)
    }

    // ── Living Aurora: four curtains of emerald, teal, cyan and violet light,
    //    tall vertical light-sheets drifting horizontally over a faint scatter of
    //    stars. Rotated Rectangle gradients + Animators only (render thread) — no
    //    shaders, same motion budget as the splash. Slow drift: this screen can
    //    stay up for minutes, so the light is felt more than watched, and the
    //    greeter blurs the whole scene the moment the password field is summoned.
    Repeater {
        model: 18
        delegate: Rectangle {
            id: star
            required property int index
            readonly property var xs: [0.05, 0.14, 0.23, 0.31, 0.40, 0.48, 0.57, 0.66, 0.74, 0.83, 0.91, 0.09, 0.19, 0.37, 0.53, 0.71, 0.88, 0.62]
            readonly property var ys: [0.06, 0.20, 0.04, 0.30, 0.11, 0.40, 0.16, 0.47, 0.09, 0.34, 0.22, 0.15, 0.44, 0.27, 0.38, 0.12, 0.50, 0.24]
            width: Math.max(2, Math.round(root.height * (0.0016 + 0.0012 * (star.index % 3))))
            height: width
            radius: width / 2
            color: root.textColor
            x: star.xs[star.index] * root.width
            y: star.ys[star.index] * root.height
            opacity: 0.12
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                running: root.visible
                NumberAnimation { to: 0.5; duration: 2400 + star.index * 150; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.12; duration: 2400 + star.index * 150; easing.type: Easing.InOutSine }
            }
        }
    }
    Repeater {
        model: 4
        delegate: Rectangle {
            id: curtain
            required property int index
            readonly property color tone: ["#10B981", "#2DD4BF", "#22D3EE", "#8B5CF6"][curtain.index]
            readonly property real baseOp: [0.14, 0.16, 0.11, 0.13][curtain.index]
            width: root.width * [0.42, 0.48, 0.38, 0.46][curtain.index]
            height: root.height * [0.66, 0.72, 0.60, 0.68][curtain.index]
            y: root.height * [0.00, -0.05, 0.08, -0.02][curtain.index]
            rotation: [-16, 12, -10, 18][curtain.index]
            transformOrigin: Item.Center
            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.42; color: curtain.tone }
                GradientStop { position: 1.0; color: "transparent" }
            }
            opacity: curtain.baseOp
            XAnimator on x {
                from: [-0.14, 0.50, 0.16, 0.42][curtain.index] * root.width
                to: [0.46, -0.06, 0.58, 0.04][curtain.index] * root.width
                duration: [64000, 82000, 72000, 92000][curtain.index]
                loops: Animation.Infinite
                easing.type: Easing.InOutSine
                running: root.visible
            }
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                running: root.visible
                NumberAnimation { to: curtain.baseOp * 1.5; duration: 6000 + curtain.index * 900; easing.type: Easing.InOutSine }
                NumberAnimation { to: curtain.baseOp * 0.6; duration: 6000 + curtain.index * 900; easing.type: Easing.InOutSine }
            }
        }
    }

    // An occasional shooting star streaks across the upper sky — the one
    // deliberate glint over the calm drift of the curtains.
    Rectangle {
        id: shootingStar
        width: Math.max(40, root.width * 0.045)
        height: 2
        radius: 1
        rotation: 20
        opacity: 0
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 1.0; color: "#EAFDF8" }
        }
        SequentialAnimation {
            loops: Animation.Infinite
            running: root.visible
            PauseAnimation { duration: 8000 }
            ParallelAnimation {
                NumberAnimation { target: shootingStar; property: "x"; from: root.width * 0.14; to: root.width * 0.60; duration: 1200; easing.type: Easing.InCubic }
                NumberAnimation { target: shootingStar; property: "y"; from: root.height * 0.12; to: root.height * 0.40; duration: 1200; easing.type: Easing.InCubic }
                SequentialAnimation {
                    NumberAnimation { target: shootingStar; property: "opacity"; to: 0.9; duration: 260; easing.type: Easing.OutCubic }
                    NumberAnimation { target: shootingStar; property: "opacity"; to: 0; duration: 900; easing.type: Easing.InCubic }
                }
            }
            PauseAnimation { duration: 6000 }
        }
    }

    // ── Legibility scrim: graphite falloff at the top and bottom edges ────────
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(root.canvasColor.r, root.canvasColor.g, root.canvasColor.b, 0.55) }
            GradientStop { position: 0.35; color: "transparent" }
            GradientStop { position: 1.0; color: Qt.rgba(root.canvasColor.r, root.canvasColor.g, root.canvasColor.b, 0.55) }
        }
    }

    // ── Drifting light motes: six sparks rising through the whole scene at
    //    whisper opacity and different speeds. They start together below the
    //    frame and separate within the first climb; the wrap happens fully
    //    off-screen so the loop never shows a pop.
    Repeater {
        model: 6
        delegate: Image {
            id: mote
            required property int index
            source: "../images/spark.png"
            width: Math.max(6, Math.round(root.height * (0.007 + 0.004 * (mote.index % 3))))
            height: width
            x: Math.round([0.16, 0.84, 0.31, 0.68, 0.07, 0.93][mote.index] * root.width)
            opacity: [0.22, 0.15, 0.26, 0.18, 0.13, 0.20][mote.index]
            YAnimator on y {
                from: root.height * 1.06
                to: -mote.height - root.height * 0.06
                duration: 38000 + mote.index * 9000
                loops: Animation.Infinite
                running: root.visible
            }
        }
    }

    // ── The MoOS brand: breathing glow, the emblem, two orbiting sparks, the
    //    wordmark — staged entrance, then a calm idle. Scaled from screen height
    //    so a 768p panel keeps the brand clear of the greeter's user avatar.
    Item {
        id: brand
        anchors.horizontalCenter: parent.horizontalCenter
        y: Math.round(root.height * 0.055)
        width: emblemSize
        height: brandColumn.height
        // Screen-relative, not gridUnit: the greeter often runs unscaled, and a
        // gridUnit cap left the hero emblem 117px tall on a 4K panel (verified
        // via kscreenlocker_greet --testing 2026-07-16). ~13.5% of the screen
        // height reads as the hero at 768p (104px) and 4K (292px) alike.
        readonly property real emblemSize: Math.round(Math.min(root.height * 0.135,
                                                               root.width * 0.12))

        transform: Translate { id: brandRise; y: -Kirigami.Units.gridUnit * 1.4 }
        opacity: 0

        Column {
            id: brandColumn
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Math.round(brand.emblemSize * 0.16)

            Item {
                id: emblemStage
                width: brand.emblemSize
                height: brand.emblemSize
                anchors.horizontalCenter: parent.horizontalCenter

                // Breathing halo — cyan wide, violet narrower in counter-phase.
                Image {
                    id: glowCyan
                    anchors.centerIn: emblem
                    width: brand.emblemSize * 2.5
                    height: width
                    source: "../images/glow-cyan.png"
                    opacity: 0.55
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        running: root.visible
                        NumberAnimation { to: 0.85; duration: 3600; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.55; duration: 3600; easing.type: Easing.InOutSine }
                    }
                }
                Image {
                    id: glowViolet
                    anchors.centerIn: emblem
                    width: brand.emblemSize * 1.9
                    height: width
                    source: "../images/glow-violet.png"
                    opacity: 0.6
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        running: root.visible
                        NumberAnimation { to: 0.35; duration: 3600; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.6; duration: 3600; easing.type: Easing.InOutSine }
                    }
                }

                // Two comet rings, counter-orbiting at different radii and
                // periods — the emblem's swirl given an orbit of its own.
                // ringB is mirrored so its tail trails its direction too.
                Image {
                    id: ringA
                    anchors.centerIn: emblem
                    width: brand.emblemSize * 1.62
                    height: width
                    source: "../images/ring.png"
                    opacity: 0.85
                    sourceSize: Qt.size(width * Screen.devicePixelRatio,
                                        height * Screen.devicePixelRatio)
                    RotationAnimator on rotation {
                        from: 0; to: 360
                        duration: 21000
                        loops: Animation.Infinite
                        running: root.visible
                    }
                }
                Image {
                    id: ringB
                    anchors.centerIn: emblem
                    width: brand.emblemSize * 1.36
                    height: width
                    source: "../images/ring.png"
                    mirror: true
                    opacity: 0.45
                    sourceSize: Qt.size(width * Screen.devicePixelRatio,
                                        height * Screen.devicePixelRatio)
                    RotationAnimator on rotation {
                        from: 360; to: 0
                        duration: 34000
                        loops: Animation.Infinite
                        running: root.visible
                    }
                }

                Image {
                    id: emblem
                    anchors.centerIn: parent
                    width: brand.emblemSize
                    height: brand.emblemSize
                    source: "file:///usr/share/pixmaps/moos-logo.png"
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    smooth: true
                    sourceSize: Qt.size(width * Screen.devicePixelRatio,
                                        height * Screen.devicePixelRatio)

                    // The idle breath: barely-there scale, six seconds a cycle.
                    SequentialAnimation on scale {
                        loops: Animation.Infinite
                        running: root.visible
                        NumberAnimation { to: 1.03; duration: 3000; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 1.0; duration: 3000; easing.type: Easing.InOutSine }
                    }
                }

                // Two sparks orbiting the emblem — opposite directions, different
                // radii and periods, so the motion never reads as a loading spinner.
                Item {
                    id: orbitA
                    anchors.fill: emblemStage
                    RotationAnimator on rotation {
                        from: 0; to: 360
                        duration: 18000
                        loops: Animation.Infinite
                        running: root.visible
                    }
                    Image {
                        source: "../images/spark.png"
                        width: brand.emblemSize * 0.16
                        height: width
                        x: (emblemStage.width - width) / 2
                        y: -brand.emblemSize * 0.14
                    }
                }
                Item {
                    id: orbitB
                    anchors.fill: emblemStage
                    RotationAnimator on rotation {
                        from: 360; to: 0
                        duration: 30000
                        loops: Animation.Infinite
                        running: root.visible
                    }
                    Image {
                        source: "../images/spark.png"
                        width: brand.emblemSize * 0.10
                        height: width
                        opacity: 0.7
                        x: (emblemStage.width - width) / 2
                        y: emblemStage.height - brand.emblemSize * 0.02
                    }
                }
            }

            Text {
                id: wordmark
                anchors.horizontalCenter: parent.horizontalCenter
                text: "MoOS"
                color: root.textColor
                font.family: "IBM Plex Sans"
                // Pixel-sized against the emblem so the whole brand scales as one
                // piece on any panel (pointSize follows the greeter's font DPI,
                // which does not track the screen).
                font.pixelSize: Math.max(18, Math.round(brand.emblemSize * 0.24))
                font.weight: Font.DemiBold
                font.letterSpacing: Math.max(2, Math.round(brand.emblemSize * 0.028))
                renderType: Text.NativeRendering
                opacity: 0
            }

            Rectangle {
                id: hairline
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.round(wordmark.implicitWidth * 0.5)
                height: 2
                radius: 1
                color: root.primaryColor
                opacity: 0

                // Every few seconds a spark glides along the hairline — the
                // one deliberate glint in an otherwise calm idle.
                Image {
                    id: hairlineSpark
                    source: "../images/spark.png"
                    width: Math.max(10, Math.round(brand.emblemSize * 0.10))
                    height: width
                    y: Math.round((parent.height - height) / 2)
                    opacity: 0
                    SequentialAnimation {
                        running: root.visible
                        loops: Animation.Infinite
                        PauseAnimation { duration: 4600 }
                        ParallelAnimation {
                            NumberAnimation { target: hairlineSpark; property: "x"
                                from: -hairlineSpark.width * 0.5
                                to: hairline.width - hairlineSpark.width * 0.5
                                duration: 1700; easing.type: Easing.InOutSine }
                            SequentialAnimation {
                                NumberAnimation { target: hairlineSpark; property: "opacity"
                                    to: 0.9; duration: 400; easing.type: Easing.OutCubic }
                                PauseAnimation { duration: 850 }
                                NumberAnimation { target: hairlineSpark; property: "opacity"
                                    to: 0; duration: 450; easing.type: Easing.InCubic }
                            }
                        }
                    }
                }
            }

            Text {
                id: caption
                anchors.horizontalCenter: parent.horizontalCenter
                text: "أهلًا بعودتك | Welcome back"
                color: root.textColor
                opacity: 0
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.max(13, Math.round(brand.emblemSize * 0.125))
                renderType: Text.NativeRendering
            }
        }

        // Staged entrance: emblem settles first, then the wordmark, hairline and
        // caption follow — the confident sequence of a finished OS.
        ParallelAnimation {
            id: brandEntrance
            running: false
            NumberAnimation { target: brand; property: "opacity"; from: 0; to: 1
                duration: 1100; easing.type: Easing.OutCubic }
            // The emblem arrives from slightly above scale and settles — the
            // cinematic beat that makes the entrance read as intentional.
            NumberAnimation { target: brand; property: "scale"; from: 1.12; to: 1.0
                duration: 1300; easing.type: Easing.OutCubic }
            NumberAnimation { target: brandRise; property: "y"
                from: -Kirigami.Units.gridUnit * 1.4; to: 0
                duration: 1100; easing.type: Easing.OutCubic }
            SequentialAnimation {
                PauseAnimation { duration: 420 }
                NumberAnimation { target: wordmark; property: "opacity"; to: 0.95
                    duration: 700; easing.type: Easing.OutCubic }
            }
            SequentialAnimation {
                PauseAnimation { duration: 620 }
                NumberAnimation { target: hairline; property: "opacity"; to: 0.9
                    duration: 600; easing.type: Easing.OutCubic }
            }
            SequentialAnimation {
                PauseAnimation { duration: 800 }
                NumberAnimation { target: caption; property: "opacity"; to: 0.62
                    duration: 700; easing.type: Easing.OutCubic }
            }
        }
        Component.onCompleted: brandEntrance.start()

        // The idle float — the whole brand drifts ±5px, slower than the breath,
        // so the two rhythms never sync into a visible loop.
        SequentialAnimation {
            loops: Animation.Infinite
            running: root.visible
            PauseAnimation { duration: 1400 }
            NumberAnimation { target: brand; property: "y"
                to: Math.round(root.height * 0.055) + 5
                duration: 4200; easing.type: Easing.InOutSine }
            NumberAnimation { target: brand; property: "y"
                to: Math.round(root.height * 0.055) - 3
                duration: 4200; easing.type: Easing.InOutSine }
            NumberAnimation { target: brand; property: "y"
                to: Math.round(root.height * 0.055)
                duration: 3200; easing.type: Easing.InOutSine }
        }
    }
}
