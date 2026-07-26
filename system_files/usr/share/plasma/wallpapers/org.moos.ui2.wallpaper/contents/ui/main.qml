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

    property int ambientPhase: 0
    // Three conditions, and the third is the one that used to be missing: a user
    // who turns Plasma's animations OFF (System Settings → General Behaviour, or
    // any accessibility profile) still got a permanently breathing 4K desktop,
    // because this gate only knew about the plugin's own AmbientMotion key. Plasma
    // signals "no animation" by collapsing every duration to 0, exactly as the
    // bento already honours it — so the scene layer honours it too, and the whole
    // wallpaper falls completely still instead of animating against the setting.
    readonly property bool motionEnabled:
        root.configuration.AmbientMotion
        && Kirigami.Units.longDuration > 0
        && art.status === Image.Ready

    readonly property bool lightSurface:
        Kirigami.Theme.backgroundColor.hslLightness > 0.55

    readonly property string fallbackImage: root.lightSurface
        ? "/usr/share/wallpapers/MoOSUI2Tide/contents/images/3840x2160.jpg"
        : "/usr/share/wallpapers/MoOSUI2Graphite/contents/images_dark/3840x2160.jpg"

    // The bento's theme badge. Derive the active MoOS look from the wallpaper
    // package name so the badge names the theme the user actually picked
    // (Midnight, Nova, …) instead of only ever "GRAPHITE"/"TIDAL". Empty until a
    // package is set (first boot) — the badge then falls back to the half.
    readonly property string themeLabel: {
        var v = String(root.configuration.Image || "")
        var m = v.match(/MoOSUI2([A-Za-z]+?)(Light)?\/?$/)
        if (!m) {
            return ""
        }
        var names = {
            "Tide": "TIDAL", "Graphite": "GRAPHITE", "Midnight": "MIDNIGHT",
            "Nova": "NOVA", "Amethyst": "AMETHYST", "Aurora": "AURORA",
            "Daylight": "DAYLIGHT", "Arena": "ARENA", "Forge": "FORGE",
            "Scholar": "SCHOLAR"
        }
        var base = names[m[1]] || m[1].toUpperCase()
        return base + (m[2] ? " LIGHT" : " GLASS")
    }

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
        // A MoOS wallpaper package dir: EVERY MoOS package ships both a light
        // master under images/ and a dark one under images_dark/ (the same files
        // the lock screen's org.kde.image uses). Light-family packages — names
        // ending in "Light", plus Tide and Daylight — take the light master;
        // every other MoOS theme is dark and takes images_dark. This must cover
        // the whole family: earlier only Tide/Graphite were handled, so Midnight,
        // Nova, Amethyst, Aurora, Arena, Forge, Scholar and every *Light package
        // fell through to the bare dir path and QML Image could not open it — the
        // desktop showed only the flat fallback colour with no wallpaper.
        if (v.indexOf("MoOSUI2") >= 0) {
            var base = v.replace(/\/+$/, "")
            var isLight = /Light$/.test(base)
                || /MoOSUI2Tide$/.test(base)
                || /MoOSUI2Daylight$/.test(base)
            return base + (isLight ? "/contents/images/3840x2160.jpg"
                                   : "/contents/images_dark/3840x2160.jpg")
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

    // "Living glass" without turning a 4K desktop into a permanent animation.
    // Two very low-alpha mineral washes exchange emphasis only once per
    // 90 seconds. The transition lasts 1.8 s, so the scene is completely idle
    // 98% of the time and remains safe on fractional-scale / battery systems.
    Timer {
        interval: 90000
        repeat: true
        running: root.motionEnabled
        onTriggered: root.ambientPhase = (root.ambientPhase + 1) % 2
    }

    Rectangle {
        anchors.fill: parent
        z: 0.1
        opacity: root.motionEnabled
            ? (root.ambientPhase === 0 ? 0.055 : 0.13)
            : 0
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop {
                position: 0.72
                color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                               Kirigami.Theme.highlightColor.g,
                               Kirigami.Theme.highlightColor.b, 0.16)
            }
            GradientStop { position: 1.0; color: "transparent" }
        }
        Behavior on opacity {
            enabled: root.motionEnabled
            NumberAnimation { duration: 1800; easing.type: Easing.InOutCubic }
        }
    }

    Rectangle {
        anchors.fill: parent
        z: 0.1
        opacity: root.motionEnabled
            ? (root.ambientPhase === 0 ? 0.11 : 0.04)
            : 0
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop {
                position: 0.0
                color: Qt.rgba(Kirigami.Theme.linkColor.r,
                               Kirigami.Theme.linkColor.g,
                               Kirigami.Theme.linkColor.b, 0.10)
            }
            GradientStop { position: 0.42; color: "transparent" }
            GradientStop { position: 1.0; color: "transparent" }
        }
        Behavior on opacity {
            enabled: root.motionEnabled
            NumberAnimation { duration: 1800; easing.type: Easing.InOutCubic }
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
        z: 1
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
        //
        // ShowDashboard is MERGED into this existing condition, not added as a
        // second `visible:`. Declaring the property twice is not an override in
        // QML, it is the error "Property value set multiple times" — and the whole
        // wallpaper then fails to load, leaving a blank desktop. That failure also
        // rasterises nothing, so it reads on a CPU graph exactly like a successful
        // optimisation: measured 0% with the setting BOTH on and off before the
        // journal was checked. `undefined` means the key is not registered, and
        // must mean "show".
        visible: (root.configuration.ShowDashboard === undefined
                  || root.configuration.ShowDashboard)
                 && root.width >= 820 && root.height >= 520 && fit >= 0.62

        DashboardBento {
            id: bento
            width: implicitWidth
            height: implicitHeight
            transformOrigin: Item.TopLeft
            scale: bentoFrame.fit
            themeLabel: root.themeLabel
        }
    }
}
