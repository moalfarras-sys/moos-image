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

    DashboardBento {
        id: bento
        // Top-leading, generous margins. Folder View icons are right-aligned
        // (moos-apply-theme writes alignment=1), so the visual balance is:
        // bento top-left, icons top-right — and even a full desktop of icons
        // merely draws over wallpaper, never a widget.
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.topMargin: Math.max(40, Math.round(parent.height * 0.05))
        anchors.leftMargin: Math.max(48, Math.round(parent.width * 0.032))
        width: implicitWidth
        height: implicitHeight
        // A phone-sized or squeezed screen gets a clean wallpaper, not a
        // cramped bento.
        visible: parent.width >= 900 && parent.height >= 560
    }
}
