// org.moos.ui2.greeter — the MoOS login scene (Liquid Glass).
//
// Plasma Login Manager owns the password card; this wallpaper owns only the calm
// scene behind it. The image (MoOSUI2Graphite, the premium sculpted-glass horizon)
// and a legibility veil paint synchronously so the password boundary is never
// delayed, and the brand is a quiet top-left signature. Content leads.
//
// Gate contract (build_files/verify_image_experience.py): NO "Repeater",
// "Animation", "ShaderEffect" or "Canvas" tokens, and the brand MUST stay anchored
// to the top-left corner so it can never overlap the centred password surface.
// This scene is fully static — the calmest possible way to honour that.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root

    readonly property string fallbackImage:
        "/usr/share/wallpapers/MoOSUI2Graphite/contents/images_dark/3840x2160.jpg"

    readonly property color accent: Kirigami.Theme.highlightColor

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
        // A wallpaper package directory: prefer a dark 4K frame, else a light one.
        if (path.indexOf("MoOSUI2Tide") >= 0) {
            return path + "/contents/images/3840x2160.jpg"
        }
        if (path.indexOf("MoOSUI2") >= 0) {
            return path + "/contents/images_dark/3840x2160.jpg"
        }
        return path + "/contents/images/3840x2160.jpg"
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

    // ── Legibility veil + vignette ──────────────────────────────────────────
    // A gentle overall tint and a soft top/bottom vignette keep the password card
    // readable and frame the centred surface. Cheap, static gradients.
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
                                                         Kirigami.Theme.backgroundColor.b, 0.34) }
            GradientStop { position: 0.45; color: "transparent" }
            GradientStop { position: 1.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                                                         Kirigami.Theme.backgroundColor.g,
                                                         Kirigami.Theme.backgroundColor.b, 0.46) }
        }
    }

    // ── MoOS signature — quiet, top-left (gate: brand stays in its corner) ──
    Row {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.leftMargin: Math.max(Kirigami.Units.gridUnit * 2,
                                     Math.round(root.width * 0.028))
        anchors.topMargin: Math.max(Kirigami.Units.gridUnit * 1.6,
                                    Math.round(root.height * 0.04))
        spacing: Kirigami.Units.largeSpacing

        Image {
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(34, Math.round(root.height * 0.038))
            height: width
            source: "file:///usr/share/pixmaps/moos-logo.png"
            fillMode: Image.PreserveAspectFit
            asynchronous: false
            smooth: true
            mipmap: true
        }

        Column {
            anchors.verticalCenter: parent.verticalCenter
            spacing: Math.round(root.height * 0.006)

            Text {
                text: "MoOS"
                color: Kirigami.Theme.textColor
                font.family: "Inter"
                font.pixelSize: Math.max(22, Math.round(root.height * 0.03))
                font.weight: Font.DemiBold
                font.letterSpacing: 1
                renderType: Text.NativeRendering
            }
            Rectangle {
                width: Math.max(26, Math.round(root.height * 0.04))
                height: 2
                radius: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: root.accent }
                    GradientStop { position: 1.0; color: Qt.alpha(root.accent, 0.0) }
                }
            }
        }
    }
}
