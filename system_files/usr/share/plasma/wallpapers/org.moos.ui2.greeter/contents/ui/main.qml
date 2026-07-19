// org.moos.ui2.greeter — the fast, single-surface MoOS login scene.
//
// Plasma Login Manager owns the authentication card. This wallpaper owns only
// the scene behind it, so it deliberately stays quiet: one shared Graphite
// image, one legibility veil, and one compact corner signature. The previous
// 491-line scene ran dozens of infinite animations and placed a large emblem
// in the same top-centre area as Plasma's clock. On software rendering that
// caused a long black hand-off and a visible clock/logo/date collision.
//
// No Repeater, ShaderEffect, Canvas, particles, or Animation belongs here.
// Plymouth and the session splash provide motion; login must become interactive
// as quickly and predictably as possible.
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

    // A small signature in a reserved corner. It never competes with the
    // centred user/password card or the bottom session actions.
    Row {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.leftMargin: Math.max(Kirigami.Units.gridUnit * 2,
                                     Math.round(root.width * 0.035))
        anchors.topMargin: Math.max(Kirigami.Units.gridUnit * 2,
                                    Math.round(root.height * 0.045))
        spacing: Kirigami.Units.largeSpacing

        Rectangle {
            width: Math.max(44, Math.round(root.height * 0.065))
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
