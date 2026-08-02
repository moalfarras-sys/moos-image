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
pragma ComponentBehavior: Bound

import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root

    property int ambientPhase: 0

    // ── The motion policy, resolved once, for the whole scene ─────────────────
    //
    // Two config keys describe the same thing. `MotionMode` (0 still / 1 gentle /
    // 2 alive) is the real one: it is what `moos-theme motion` writes and what
    // the Theme Picker highlights. `AmbientMotion` is the original Boolean, still
    // written by moos-theme in the same transaction and still present in every
    // already-installed desktop's appletsrc. MotionMode wins when it holds a real
    // level; its -1 sentinel means "this desktop predates the key", and then the
    // old Boolean answers (see contents/config/main.xml for why the default is a
    // sentinel and not 1).
    //
    // `undefined` is handled as well as -1, because a running plasmashell can be
    // holding an OLDER copy of main.xml than this file — during an rpm-ostree
    // upgrade the QML is read fresh while the registered config keys are not — and
    // an unregistered key reads back undefined, not its default.
    readonly property int configuredMotionMode: {
        var raw = root.configuration.MotionMode
        var mode = (raw === undefined || raw === null) ? -1 : Number(raw)
        if (mode === 0 || mode === 1 || mode === 2) {
            return mode
        }
        return root.configuration.AmbientMotion === false ? 0 : 1
    }

    // Plasma signals "the user turned animations off" (System Settings → General
    // Behaviour, or any accessibility profile) by collapsing its animation
    // durations, and that must beat any level the user or moos-theme chose.
    //
    // This gate used to compare longDuration against ZERO, and was therefore
    // DEAD: Kirigami FLOORS that value at 1 and never returns 0, so the
    // expression could not be false and "disable animations" stopped nothing at
    // all on the largest surface on the screen. KDE's own three BusyIndicator.qml
    // (org/kde/breeze, org/kde/desktop, org/kde/plasma/components) all compare
    // against 1, and RejectPasswordPathAnimation.qml writes
    // `longDuration <= 1 ? 1 : 600`. Comparing against 1 is the only form that
    // ever fires.
    //
    // Spelled out in prose rather than quoting the broken expression on purpose:
    // tests/test_moos_motion_gate.py forbids the old form by searching the RAW
    // file text, comments included, so a comment that quotes the bug it fixes
    // fails the gate that exists to catch the bug.
    //
    // The name carries the config key deliberately. Every consumer of this value
    // — here, the bento, every card — reads `resolvedMotionMode` and therefore
    // says out loud which key it is obeying; the previous generic name is how a
    // gate invented locally and consulting nothing went unnoticed for so long.
    readonly property int resolvedMotionMode:
        Kirigami.Units.longDuration > 1 ? root.configuredMotionMode : 0

    // The scene layer's own on/off seam. It additionally waits for the art,
    // because the ambient washes crossfade OVER the wallpaper and have nothing to
    // sit on until it has decoded. The bento does not wait — it is an overlay,
    // and holding its entrance hostage to a 4K JPEG decode is what made the
    // dashboard appear a second late on cold boots.
    readonly property bool motionEnabled:
        root.resolvedMotionMode > 0 && art.status === Image.Ready

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

    // A disabled dashboard must not merely become invisible. DashboardBento owns minute/weather
    // timers and starts its first geolocation request on construction; keeping that object alive
    // made ShowDashboard=false continue polling and retaining the complete card tree in Cloud.
    // Loader.active is the lifecycle boundary: off (or too small to render) means no object, no
    // timers, no network request and no hidden rendering state.
    Component {
        id: bentoComponent
        DashboardBento {
            resolvedMotionMode: root.resolvedMotionMode
            themeLabel: root.themeLabel
        }
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

        readonly property bool dashboardRequested:
            root.configuration.ShowDashboard === undefined
            || root.configuration.ShowDashboard
        readonly property real bentoWidth:
            bentoLoader.item ? bentoLoader.item.implicitWidth : 0
        readonly property real bentoHeight:
            bentoLoader.item ? bentoLoader.item.implicitHeight : 0
        readonly property real fit: Math.min(
            1.0,
            bentoWidth > 0 ? roomWidth / bentoWidth : 1.0,
            bentoHeight > 0 ? roomHeight / bentoHeight : 1.0)

        width: bentoWidth * fit
        height: bentoHeight * fit
        // Below this the bento would scale so small it reads as clutter — a
        // phone-sized or heavily-squeezed desktop gets a clean wallpaper instead.
        //
        // Visibility follows Loader.active rather than repeating ShowDashboard.
        // Declaring visible twice is a QML load error, and a failed wallpaper also
        // rasterises nothing — the exact shape that once looked like a successful
        // CPU optimisation until the journal was checked.
        visible: bentoLoader.active && fit >= 0.62

        Loader {
            id: bentoLoader
            active: bentoFrame.dashboardRequested
                    && root.width >= 820 && root.height >= 520
            sourceComponent: bentoComponent
            width: item ? item.implicitWidth : 0
            height: item ? item.implicitHeight : 0
            transformOrigin: Item.TopLeft
            scale: bentoFrame.fit
        }
    }
}
