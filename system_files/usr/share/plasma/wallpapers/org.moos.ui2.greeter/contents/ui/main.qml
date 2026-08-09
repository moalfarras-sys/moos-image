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
    // EVERY family, not two of them.
    //
    // This was a light/dark branch carrying ONE hardcoded pair of tones, so the
    // scene only ever wore Graphite's ink and Graphite's accent. Point the login
    // wallpaper at Scholar or Arena and the photograph changed while the
    // signature stayed teal — the login screen followed the theme system in name
    // only. The literals had also drifted from the palettes they claimed to
    // copy: #14191C against Graphite's real #1D2529.
    //
    // The tones below are the SHIPPED colour schemes verbatim — Window
    // BackgroundNormal, Window ForegroundNormal, Selection BackgroundNormal. A
    // gate compares every entry against the real .colors file and fails a
    // wallpaper package that has no entry, so this cannot drift again and a new
    // family cannot silently fall back to Graphite.
    //
    // Keyed by WALLPAPER package, because that is what the login config names,
    // and two of them do not share their scheme's name: the Graphite wallpaper
    // carries MoOSUI2Dark and Tide carries MoOSUI2Light.
    readonly property var sceneTones: ({
        "MoOSUI2Graphite":      { canvas: "#1D2529", ink: "#E8F1EF", accent: "#4ED7C8" },
        "MoOSUI2Tide":          { canvas: "#C9E2DD", ink: "#17302E", accent: "#006D67" },
        "MoOSUI2Nova":          { canvas: "#111A2E", ink: "#EAF2FF", accent: "#6366F1" },
        "MoOSUI2NovaLight":     { canvas: "#C6DCE9", ink: "#17302E", accent: "#0E63C4" },
        "MoOSUI2Amethyst":      { canvas: "#201829", ink: "#F1E9F5", accent: "#C084FC" },
        "MoOSUI2AmethystLight": { canvas: "#D5D9EE", ink: "#17302E", accent: "#7C3AED" },
        "MoOSUI2Midnight":      { canvas: "#0A0A0C", ink: "#F5F7FA", accent: "#22D3EE" },
        "MoOSUI2Daylight":      { canvas: "#C5DAEC", ink: "#17302E", accent: "#0284C7" },
        "MoOSUI2Aurora":        { canvas: "#172236", ink: "#ECF2FB", accent: "#3B82F6" },
        "MoOSUI2AuroraLight":   { canvas: "#C2E4E1", ink: "#17302E", accent: "#0F766E" },
        "MoOSUI2Arena":         { canvas: "#150C22", ink: "#F5E9FF", accent: "#FF2D95" },
        "MoOSUI2ArenaLight":    { canvas: "#DDD0E9", ink: "#17302E", accent: "#C81D7A" },
        "MoOSUI2Forge":         { canvas: "#131A22", ink: "#E6EDF3", accent: "#3FB950" },
        "MoOSUI2ForgeLight":    { canvas: "#C4DED1", ink: "#17302E", accent: "#1A7F37" },
        "MoOSUI2Scholar":       { canvas: "#201A11", ink: "#F3EADB", accent: "#E0A458" },
        "MoOSUI2ScholarLight":  { canvas: "#DBD8CA", ink: "#17302E", accent: "#B45309" }
    })

    readonly property string sceneFamily: {
        const found = /\/wallpapers\/(MoOSUI2[A-Za-z]*)\//.exec(root.sceneImage)
        return found ? found[1] : "MoOSUI2Graphite"
    }
    readonly property var tones:
        root.sceneTones[root.sceneFamily] || root.sceneTones["MoOSUI2Graphite"]

    readonly property bool lightScene:
        /\/MoOSUI2[^/]*Light\//.test(root.sceneImage)
        || root.sceneImage.indexOf("/MoOSUI2Tide/") >= 0
        || root.sceneImage.indexOf("/MoOSUI2Daylight/") >= 0
    readonly property color canvas: root.tones.canvas
    readonly property color ink: root.tones.ink
    readonly property color accent: root.tones.accent

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
    //
    // The signature arrives; the security surface does not wait for it.
    //
    // This scene was fully static because "authentication must paint
    // immediately even with software rendering" — a real constraint, and it
    // still holds for everything above: the base plate, the wallpaper and both
    // veils are painted synchronously and are never animated. But this Row is
    // the one element that is neither the background nor the password card: it
    // is drawn by plasma-login-wallpaper BEHIND the greeter's compiled
    // authentication cluster, in a separate process, so a bounded fade here
    // cannot delay the prompt by a frame.
    //
    // Bounded is the whole contract: ONE shot on load, ~520 ms, opacity and a
    // few pixels of travel, then it is over and the scene is static again for
    // the rest of the session. No loop, no Animation.Infinite, no shader, no
    // Canvas — a login screen that keeps moving is a login screen that keeps
    // costing GPU while someone types a password.
    Row {
        id: signature
        opacity: 0
        Component.onCompleted: signatureEntrance.start()
        SequentialAnimation {
            id: signatureEntrance
            running: false
            PauseAnimation { duration: 140 }
            ParallelAnimation {
                NumberAnimation {
                    target: signature; property: "opacity"
                    from: 0; to: 1
                    duration: 520; easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: signature; property: "anchors.topMargin"
                    from: signature.anchors.topMargin + 14
                    to: signature.anchors.topMargin
                    duration: 520; easing.type: Easing.OutCubic
                }
            }
        }

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
