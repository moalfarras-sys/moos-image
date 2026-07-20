// org.moos.ui2.greeter — the fast, single-surface MoOS login scene.
//
// Plasma Login Manager owns the authentication card. This wallpaper owns only
// the scene behind it, so it deliberately stays quiet: one shared Graphite
// image, one legibility veil, and one compact corner signature with ambient
// orbital presence. The greeter must become interactive as quickly and
// predictably as possible — no animations are used here.
//
// No Repeater, ShaderEffect, Canvas, particles belongs here. Plymouth and the
// session splash provide motion; login must paint immediately.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root

    readonly property string fallbackImage:
        "/usr/share/wallpapers/MoOSUI2Graphite/contents/images_dark/3840x2160.jpg"

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

    // Calm contrast for the password card without a costly blur or shader.
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                       Kirigami.Theme.backgroundColor.g,
                       Kirigami.Theme.backgroundColor.b, 0.16)
    }

    // ── Static horizon line ─────────────────────────────────────────────────
    // A fine luminous thread at ~65% height — the one horizontal anchor
    // that says "this scene was composed, not defaulted".
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.height * 0.65
        width: root.width * 0.60
        height: 1
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.5; color: Qt.alpha(Kirigami.Theme.highlightColor, 0.40) }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    // ── Three depth-staggered accent dots ───────────────────────────────────
    // Static ambient light points — no motion, just presence and depth.
    Rectangle {
        x: 0.15 * root.width; y: 0.12 * root.height
        width: Math.max(4, root.height * 0.005); height: width; radius: width / 2
        color: Kirigami.Theme.highlightColor; opacity: 0.18
    }
    Rectangle {
        x: 0.78 * root.width; y: 0.18 * root.height
        width: Math.max(5, root.height * 0.007); height: width; radius: width / 2
        color: Kirigami.Theme.highlightColor; opacity: 0.14
    }
    Rectangle {
        x: 0.50 * root.width; y: 0.08 * root.height
        width: Math.max(3, root.height * 0.004); height: width; radius: width / 2
        color: Kirigami.Theme.hoverColor; opacity: 0.12
    }

    // ── MoOS signature with ambient orbital presence ────────────────────────
    Row {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.leftMargin: Math.max(Kirigami.Units.gridUnit * 2,
                                     Math.round(root.width * 0.035))
        anchors.topMargin: Math.max(Kirigami.Units.gridUnit * 2,
                                    Math.round(root.height * 0.045))
        spacing: Kirigami.Units.largeSpacing

        Item {
            width: Math.max(52, Math.round(root.height * 0.075))
            height: width

            // Static ambient glow — concentric translucent discs
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 2.2; height: width; radius: width / 2
                color: Kirigami.Theme.hoverColor; opacity: 0.08
            }
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 1.6; height: width; radius: width / 2
                color: Kirigami.Theme.highlightColor; opacity: 0.06
            }

            // Static orbital ring impression (Image element with fixed rotation)
            Image {
                anchors.centerIn: parent
                width: parent.width * 1.8; height: width
                source: "../images/ring.png"
                opacity: 0.22
                asynchronous: true
                sourceSize: Qt.size(width * 2, height * 2)
                rotation: 30
            }

            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.75
                height: width
                radius: width * 0.3
                color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                               Kirigami.Theme.backgroundColor.g,
                               Kirigami.Theme.backgroundColor.b, 0.72)
                border.width: 1
                border.color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                                      Kirigami.Theme.highlightColor.g,
                                      Kirigami.Theme.highlightColor.b, 0.55)

                Image {
                    anchors.fill: parent
                    anchors.margins: Math.round(parent.width * 0.16)
                    source: "file:///usr/share/pixmaps/moos-logo.png"
                    fillMode: Image.PreserveAspectFit
                    asynchronous: false
                    smooth: true
                }
            }
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "MoOS"
            color: Kirigami.Theme.textColor
            font.family: "IBM Plex Sans"
            font.pixelSize: Math.max(22, Math.round(root.height * 0.034))
            font.weight: Font.DemiBold
            font.letterSpacing: 1.5
            renderType: Text.NativeRendering
        }
    }
}
