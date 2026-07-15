// org.moos.ui2.wallpaper — the MoOS desktop scene: wallpaper + the Tidal Glass
// dashboard, painted as ONE layer at the very bottom of the desktop stack.
//
// WHY A WALLPAPER PLUGIN AND NOT A DESKTOP WIDGET
//   A Plasma desktop widget always draws ABOVE the Folder View icon grid, and
//   three shipped fixes (x=80 → 260 → 360, icons right-aligned, live-ISO skip)
//   each only moved the collision with the "Install MoOS" icon. A wallpaper
//   renders BELOW icons, selection rubber-bands and every window — the bento
//   can never cover anything, on any screen, live or installed. So the widget
//   became this plugin, and the live ISO gets its dashboard back.
//
// IMAGE RESOLUTION
//   The `Image` config key (written by moos-theme / moos-apply-theme per UI2
//   half) may be a plain image file or a MoOS wallpaper *package* directory —
//   the same values org.kde.image historically received. When it is empty
//   (first boot, before any script ran), the scene follows the active palette:
//   Graphite masters on the dark half, Tide masters on the light half.
import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root

    readonly property bool lightSurface:
        Kirigami.Theme.backgroundColor.hslLightness > 0.55

    readonly property string fallbackImage: root.lightSurface
        ? "/usr/share/wallpapers/MoOSUI2Tide/contents/images/3840x2160.jpg"
        : "/usr/share/wallpapers/MoOSUI2Graphite/contents/images_dark/3840x2160.jpg"

    function resolveImage(value) {
        var v = String(value || "")
        if (v === "") {
            return root.fallbackImage
        }
        if (v.indexOf("file://") === 0) {
            v = v.substring(7)
        }
        // A concrete image file: use it as-is.
        if (/\.(jpg|jpeg|png|webp|avif)$/i.test(v)) {
            return v
        }
        // A MoOS wallpaper package dir: pick the master that matches the half
        // (Tide ships light masters under images/, Graphite dark ones under
        // images_dark/ — the same files the lock screen's org.kde.image uses).
        if (v.indexOf("MoOSUI2Tide") >= 0) {
            return v + "/contents/images/3840x2160.jpg"
        }
        if (v.indexOf("MoOSUI2Graphite") >= 0) {
            return v + "/contents/images_dark/3840x2160.jpg"
        }
        return v
    }

    // Delay ksplash until the scene is actually painted (org.kde.image does the
    // same) — but never forever: Image.onStatusChanged clears it on ANY outcome.
    Component.onCompleted: root.loading = true

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
        onStatusChanged: {
            if (status !== Image.Loading) {
                root.loading = false
            }
        }
    }

    // Solid palette canvas behind everything, so a missing/renamed master file
    // degrades to a branded flat colour, never to a black desktop.
    Rectangle {
        anchors.fill: parent
        z: -1
        color: Kirigami.Theme.backgroundColor
    }

    // Scale-to-fit frame. The bento has a FIXED design size (gridUnit*31 ×
    // gridUnit*12), and gridUnit tracks the user's font/DPI — so on a small
    // screen, a scaled desktop, or a large accessibility font, the fixed width
    // can exceed the space left after the margins and the bento would clip off
    // the right/bottom edge. This frame measures the room actually available and
    // scales the whole bento down (never up past 1.0) to fit, keeping its aspect
    // and every card readable. transformOrigin top-left so it shrinks toward the
    // corner it is anchored to, not toward its centre.
    Item {
        id: bentoFrame
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.topMargin: Math.max(36, Math.round(parent.height * 0.05))
        anchors.leftMargin: Math.max(44, Math.round(parent.width * 0.032))

        // The room the bento may occupy: everything from its top-left corner to
        // a comfortable inset from the opposite edges, capped so it never spans
        // more than ~68% of the screen width (it is a corner accent, not a bar).
        readonly property real roomWidth:
            Math.min(root.width * 0.68,
                     root.width - anchors.leftMargin - Math.max(44, Math.round(root.width * 0.032)))
        readonly property real roomHeight:
            root.height * 0.42 - anchors.topMargin

        readonly property real fit: Math.min(
            1.0,
            bento.implicitWidth  > 0 ? roomWidth  / bento.implicitWidth  : 1.0,
            bento.implicitHeight > 0 ? roomHeight / bento.implicitHeight : 1.0)

        width: bento.implicitWidth * fit
        height: bento.implicitHeight * fit
        // Below this the bento would scale so small it reads as clutter — a
        // phone-sized or heavily-squeezed desktop gets a clean wallpaper instead.
        visible: root.width >= 820 && root.height >= 520 && fit >= 0.62

        DashboardBento {
            id: bento
            width: implicitWidth
            height: implicitHeight
            transformOrigin: Item.TopLeft
            scale: bentoFrame.fit
        }
    }
}
