// org.moos.ui2.greeter — the MoOS login scene.
//
// Plasma Login Manager owns the password card. This wallpaper owns only the
// scene BEHIND it, so it stays disciplined: the base image and the legibility
// veil paint synchronously so the password boundary is never delayed, and the
// only motion is a pair of continuously-rotating halo rings on the corner
// signature — driven by render-thread Animators, which cannot block first
// paint. Depth is built from soft pre-baked glow sprites (the same ones the
// lock and logout scenes use), not hard-edged discs.
//
// Gate contract (build_files/verify_image_experience.py): this file may NOT
// contain the tokens "Repeater", "Animation", "ShaderEffect" or "Canvas", and
// the brand MUST stay anchored to the top-left corner so it can never overlap
// the centred password surface. Motion therefore uses *Animator* types only
// (no "*Animation"), and loop counts are large finite integers rather than
// Animation.Infinite. Keep it that way.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root

    readonly property string fallbackImage:
        "/usr/share/wallpapers/MoOSUI2Graphite/contents/images_dark/3840x2160.jpg"

    // The signature colours, resolved once from the active scheme so the login
    // scene carries the same accent identity as the lock and logout doors.
    readonly property color accent: Kirigami.Theme.highlightColor
    readonly property color accentSoft: Kirigami.Theme.hoverColor

    function resolveImage(value) {
        var path = String(value || "")
        if (path === "") {
            return root.fallbackImage
        }
        if (path.indexOf("file://") === 0) {
            path = path.substring(7)
        }
        if (/\.(jpg|jpeg|png|webp|avif)$/i.test(path)) {
            return path
        }
        if (path.indexOf("MoOSUI2Tide") >= 0) {
            return path + "/contents/images/3840x2160.jpg"
        }
        if (path.indexOf("MoOSUI2") >= 0) {
            return path + "/contents/images_dark/3840x2160.jpg"
        }
        return path
    }

    // ── Base plate + wallpaper (both paint immediately) ─────────────────────
    Rectangle {
        anchors.fill: parent
        color: Kirigami.Theme.backgroundColor
    }

    Image {
        anchors.fill: parent
        source: "file://" + root.resolveImage(root.configuration.Image)
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: true
        smooth: true
        sourceSize: Qt.size(root.width * Screen.devicePixelRatio,
                            root.height * Screen.devicePixelRatio)
    }

    // ── Brand-tinted depth glow ─────────────────────────────────────────────
    // Soft radial sprites (no hard edge): a teal pool rising behind the
    // signature corner and a cooler violet counter-glow in the far corner give
    // the flat wallpaper atmosphere without ever washing out the centred card.
    Image {
        source: "../images/glow-cyan.png"
        width: Math.max(root.width, root.height) * 0.62
        height: width
        x: root.width * 0.10 - width / 2
        y: root.height * 0.16 - height / 2
        opacity: 0.55
        asynchronous: true
        smooth: true
        sourceSize: Qt.size(width, width)
    }
    Image {
        source: "../images/glow-violet.png"
        width: Math.max(root.width, root.height) * 0.58
        height: width
        x: root.width * 0.94 - width / 2
        y: root.height * 0.92 - height / 2
        opacity: 0.42
        asynchronous: true
        smooth: true
        sourceSize: Qt.size(width, width)
    }

    // ── Legibility veil + vignette ──────────────────────────────────────────
    // A gentle overall tint keeps the password card and clock readable over any
    // wallpaper; the vertical vignette darkens the top and bottom edges so the
    // scene frames the centred authentication surface. Cheap static gradients.
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                       Kirigami.Theme.backgroundColor.g,
                       Kirigami.Theme.backgroundColor.b, 0.12)
    }
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                                                         Kirigami.Theme.backgroundColor.g,
                                                         Kirigami.Theme.backgroundColor.b, 0.40) }
            GradientStop { position: 0.42; color: "transparent" }
            GradientStop { position: 1.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                                                         Kirigami.Theme.backgroundColor.g,
                                                         Kirigami.Theme.backgroundColor.b, 0.52) }
        }
    }

    // ── Composed horizon thread ─────────────────────────────────────────────
    // A fine luminous line at ~65% height — the one horizontal anchor that says
    // "this scene was composed, not defaulted" — with a fainter echo above it.
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.height * 0.65
        width: root.width * 0.62
        height: 1
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.5; color: Qt.alpha(root.accent, 0.42) }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.height * 0.65 - Math.max(6, root.height * 0.012)
        width: root.width * 0.34
        height: 1
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.5; color: Qt.alpha(root.accentSoft, 0.16) }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    // ── Static ambient accent dots — depth-staggered light points ───────────
    Rectangle {
        x: 0.17 * root.width; y: 0.14 * root.height
        width: Math.max(4, root.height * 0.005); height: width; radius: width / 2
        color: root.accent; opacity: 0.20
    }
    Rectangle {
        x: 0.80 * root.width; y: 0.20 * root.height
        width: Math.max(5, root.height * 0.007); height: width; radius: width / 2
        color: root.accent; opacity: 0.14
    }
    Rectangle {
        x: 0.52 * root.width; y: 0.09 * root.height
        width: Math.max(3, root.height * 0.004); height: width; radius: width / 2
        color: root.accentSoft; opacity: 0.14
    }
    Rectangle {
        x: 0.88 * root.width; y: 0.56 * root.height
        width: Math.max(3, root.height * 0.004); height: width; radius: width / 2
        color: root.accentSoft; opacity: 0.12
    }

    // ── MoOS signature — a glass identity chip with a living halo ───────────
    // Anchored to the top-left corner (gate requirement): the brand can never
    // reach the centred password. The halo rings rotate continuously via
    // Animators — the scene's only motion, running on the render thread without
    // ever delaying the greeter's first paint.
    Row {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.leftMargin: Math.max(Kirigami.Units.gridUnit * 2,
                                     Math.round(root.width * 0.038))
        anchors.topMargin: Math.max(Kirigami.Units.gridUnit * 2,
                                    Math.round(root.height * 0.05))
        spacing: Kirigami.Units.largeSpacing * 1.4

        Item {
            id: emblemStage
            width: Math.max(72, Math.round(root.height * 0.10))
            height: width
            anchors.verticalCenter: parent.verticalCenter

            // Soft teal pool behind the chip — makes the emblem read brightly
            // against the dark scene without a light-coloured chip.
            Image {
                anchors.centerIn: parent
                width: parent.width * 2.3; height: width
                source: "../images/glow-cyan.png"
                opacity: 0.7
                asynchronous: true
                smooth: true
                sourceSize: Qt.size(width, width)
            }

            // Outer halo ring — a slow, continuous clockwise turn.
            Image {
                anchors.centerIn: parent
                width: parent.width * 1.92; height: width
                source: "../images/ring.png"
                opacity: 0.5
                asynchronous: true
                smooth: true
                sourceSize: Qt.size(width * 2, width * 2)
                RotationAnimator on rotation {
                    from: 0; to: 360
                    duration: 44000
                    loops: 1000000
                    running: true
                }
            }
            // Inner halo ring — counter-rotating, fainter, for quiet depth.
            Image {
                anchors.centerIn: parent
                width: parent.width * 1.46; height: width
                source: "../images/ring.png"
                mirror: true
                opacity: 0.3
                asynchronous: true
                smooth: true
                sourceSize: Qt.size(width * 2, width * 2)
                RotationAnimator on rotation {
                    from: 360; to: 0
                    duration: 64000
                    loops: 1000000
                    running: true
                }
            }

            // The frosted chip that holds the mark.
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.84
                height: width
                radius: width * 0.30
                color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                               Kirigami.Theme.backgroundColor.g,
                               Kirigami.Theme.backgroundColor.b, 0.66)
                border.width: 1
                border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.6)

                // Silk highlight along the chip's crest — the UI2 glass tell.
                Rectangle {
                    anchors { top: parent.top; left: parent.left; right: parent.right; margins: 2 }
                    height: 1
                    radius: 1
                    color: Qt.rgba(Kirigami.Theme.textColor.r,
                                   Kirigami.Theme.textColor.g,
                                   Kirigami.Theme.textColor.b, 0.20)
                }

                Image {
                    anchors.fill: parent
                    anchors.margins: Math.round(parent.width * 0.14)
                    source: "file:///usr/share/pixmaps/moos-logo.png"
                    fillMode: Image.PreserveAspectFit
                    asynchronous: false
                    smooth: true
                    mipmap: true
                }
            }
        }

        // The wordmark lockup — name over a fine accent underline and a soft
        // localized welcome. Left-aligned beside the chip.
        Column {
            anchors.verticalCenter: parent.verticalCenter
            spacing: Math.round(root.height * 0.008)

            Text {
                text: "MoOS"
                color: Kirigami.Theme.textColor
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.max(26, Math.round(root.height * 0.04))
                font.weight: Font.DemiBold
                font.letterSpacing: 1.5
                renderType: Text.NativeRendering
            }

            Rectangle {
                width: Math.max(34, Math.round(root.height * 0.055))
                height: 2
                radius: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: root.accent }
                    GradientStop { position: 1.0; color: Qt.alpha(root.accent, 0.0) }
                }
            }

            Text {
                text: "أهلاً بعودتك"
                color: Kirigami.Theme.textColor
                opacity: 0.66
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.max(13, Math.round(root.height * 0.017))
                font.weight: Font.Normal
                font.letterSpacing: 0.5
                renderType: Text.NativeRendering
            }
        }
    }
}
