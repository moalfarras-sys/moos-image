// org.moos.ui2.greeter — the MoOS login scene (Liquid Glass).
//
// Plasma Login Manager owns the password card; this wallpaper owns only the calm
// scene behind it. The image, legibility veil and shared Tidal Horizon Portal
// paint synchronously so the password boundary is never delayed. The static
// portal frames the compiled authentication cluster; the protected brand stays
// a quiet top-left signature.
//
// The greeter compiles its own layout into a Qt resource
// (qrc:/qt/qml/org/kde/plasma/login/Main.qml), so this scene and
// org/kde/breeze/components are the two surfaces MoOS reaches: the clock, power
// buttons, battery and user avatar come from that module and are MoOS's own files,
// while the Main/Login layout, the session and keyboard-layout buttons and
// PlasmaExtras.PasswordField are stock. VERIFIED 2026-07-27 with `strings -el` on
// the binary — a plain `strings` finds no "breeze" in it at all, because Qt stores
// QStringLiteral as UTF-16, and reading that as "the module is unused" is wrong.
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
        // A wallpaper package directory. EVERY MoOS package ships both a
        // light master under images/ and a dark one under images_dark/; the
        // desktop scene plugin already picks by family name, and the greeter
        // must agree with it — the login wallpaper is contractually the SAME
        // image the lock shows, and an existing ScholarLight lock beside a
        // Graphite-dark login was exactly the mismatch this used to produce.
        if (path.indexOf("MoOSUI2") >= 0) {
            var base = path.replace(/\/+$/, "")
            var isLight = /Light$/.test(base)
                || /MoOSUI2Tide$/.test(base)
                || /MoOSUI2Daylight$/.test(base)
            return base + (isLight ? "/contents/images/3840x2160.jpg"
                                   : "/contents/images_dark/3840x2160.jpg")
        }
        return path + "/contents/images/3840x2160.jpg"
    }

    readonly property string sceneImage: root.resolveImage(root.configuration.Image)

    // ── The scene's palette, and why it is NOT Kirigami.Theme's ──────────────
    //
    // MEASURED 2026-07-27 on the installed machine. The greeter runs as the
    // `plasmalogin` system account, and that account's
    // /var/lib/plasmalogin/.config/kdeglobals carried the MoOSUI2 **Light**
    // palette — BackgroundNormal=216,235,231, ForegroundNormal=23,48,46 — while
    // this scene paints the **dark** Graphite wallpaper the login config pins.
    // Kirigami.Theme.textColor therefore drew the wordmark in near-black on a
    // near-black photograph: the brand was simply invisible. The three veil
    // layers below were tinting a dark image toward white at the same time.
    // Worse, that account's state lives in /var/lib/plasmalogin, which nothing in
    // the image provisions — it is unreproducible local state, so a fresh install
    // would have produced some third answer.
    //
    // A wallpaper is not a themed control. It is the one item on screen that
    // knows exactly what it is painting, and therefore the one item that must
    // never ask an ambient colour scheme it does not control. The design
    // contract's rule — colours come from Kirigami.Theme roles so all 16 themes
    // retint — is a rule about SESSION surfaces: no Global Theme reaches the
    // greeter at all (LookAndFeelManager runs inside the user's session, long
    // after this has drawn), so following a role here buys nothing and costs the
    // brand.
    //
    // So the veil and the signature use the MoOS UI2 tokens of the wallpaper this
    // scene actually resolved (artwork/MOOS_UI2_DESIGN.md), keyed off the same
    // test resolveImage() already uses to choose the frame. Graphite Dark by
    // default; the light branch follows every configured Light/Tide/Daylight
    // package, so it cannot strand dark ink on a light horizon.
    // Keep the palette variant derived from the same package path as the image.
    // Family light profiles must not inherit Graphite ink merely because they
    // are not named Tide.
    readonly property bool lightScene:
        /\/MoOSUI2[^/]*Light\//.test(root.sceneImage)
        || root.sceneImage.indexOf("/MoOSUI2Tide/") >= 0
        || root.sceneImage.indexOf("/MoOSUI2Daylight/") >= 0
    readonly property color canvas: root.lightScene ? "#D8EBE7" : "#14191C"
    readonly property color ink: root.lightScene ? "#17302E" : "#E8F1EF"
    readonly property color accent: root.lightScene ? "#006D67" : "#4ED7C8"

    // ── Base plate + wallpaper (both paint immediately) ─────────────────────
    Rectangle {
        anchors.fill: parent
        color: root.canvas
    }

    Image {
        anchors.fill: parent
        source: "file://" + root.sceneImage
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
        color: Qt.rgba(root.canvas.r, root.canvas.g, root.canvas.b, 0.12)
    }
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(root.canvas.r,
                                                         root.canvas.g,
                                                         root.canvas.b, 0.34) }
            GradientStop { position: 0.45; color: "transparent" }
            GradientStop { position: 1.0; color: Qt.rgba(root.canvas.r,
                                                         root.canvas.g,
                                                         root.canvas.b, 0.46) }
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
                color: root.ink
                font.family: "IBM Plex Sans Arabic"
                font.pixelSize: Math.max(22, Math.round(root.height * 0.03))
                font.weight: Font.DemiBold
                font.letterSpacing: 1
                // QtRendering, not NativeRendering. The flagship panel runs at
                // 225% — a FRACTIONAL devicePixelRatio — and Qt's native
                // rasteriser hints glyphs onto whole device pixels, which do not
                // line up with fractional logical ones. The wordmark's stems land
                // off-grid and the letterSpacing above rounds unevenly, so "MoOS"
                // reads slightly smeared beside the crisp emblem next to it. The
                // distance-field path scales cleanly at any ratio and is what
                // every other MoOS brand surface already uses.
                renderType: Text.QtRendering
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
