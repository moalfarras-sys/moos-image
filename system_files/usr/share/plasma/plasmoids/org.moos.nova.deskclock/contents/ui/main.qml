// MoOS Nova Desk Clock — the clock on the desktop, the weather beside it, and the
// machine's pulse under both.
//
// ONE widget, not three, and that is deliberate. The rings began life as a separate
// plasmoid and it did not survive contact with Plasma: a desktop applet's position
// is stored in a resolution-keyed ItemGeometries string on the CONTAINMENT, not on
// the applet, and the x/y/w/h passed to addWidget() is transient — it is not
// persisted. So after the first shell restart the monitor was auto-placed at 0,0,
// on top of the folder icons, while the clock stayed where it was put. Two widgets
// that must sit together cannot be two widgets.
//
// Separate from org.moos.nova.clock, though. THAT one is a PANEL applet: its
// compact representation is the dock's time and its full representation is a
// calendar popup. On the desktop Plasma renders an applet's FULL representation, so
// putting the panel clock here would have produced a month grid, not a clock.
//
// MoOS is bilingual, so the date appears twice — once in Arabic, once in the
// session locale. Both come from QLocale; neither is a hardcoded translation that
// goes stale.
//
// Colour comes from Kirigami.Theme, never PlasmaCore.Theme: PlasmaCore exposes
// Types only, and binding to a Theme that does not exist is how the panel clock
// spent its first revision drawing nothing at all.
//
// IT COVERS NOTHING, AND IT CATCHES NOTHING. NoBackground means no card and no
// panel — just light on the wallpaper — and there is deliberately not a single
// MouseArea in this file. A desktop widget that accepts clicks eats the right-click
// that opens the desktop's own menu and the drag that starts a rubber-band
// selection, and the user cannot tell why their desktop went dead in that rectangle.
// Every animation below is decorative and passive.
//
// SENSOR IDS ARE NOT GUESSABLE. cpu/all/usage, memory/physical/usedPercent and
// gpu/gpu0/usage are real — verified against `kstatsviewer --list` on this
// hardware, which is the only list that counts. An earlier version of the desktop
// widgets invented ids that looked exactly as plausible as these, and the result
// was a widget that drew an empty box forever: a monitor showing nothing looks
// identical to a monitor reading zero. They also need plasma-ksystemstats.service
// RUNNING — it was not, and nothing started it. moos-apply-theme does.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.sensors as Sensors

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    property date now: new Date()

    readonly property var arabicLocale: Qt.locale("ar")

    // Ring thresholds. Deliberately not 50/75: a desktop sitting at 55% CPU is
    // working, not struggling, and a gauge that cries wolf at 55% is one you learn
    // to stop looking at.
    readonly property real warn: 65
    readonly property real crit: 88

    function tint(v) {
        if (v >= root.crit) { return "#F87171"; }   // red   — struggling
        if (v >= root.warn) { return "#FBBF24"; }   // amber — working
        return "#34D399";                           // green — fine
    }

    // Tick on the minute boundary. Nothing here shows seconds, so a 1 Hz timer
    // would be 59 wasted wakeups a minute for the life of the session.
    Timer {
        interval: 60000 - (root.now.getSeconds() * 1000 + root.now.getMilliseconds())
        running: true
        repeat: true
        onTriggered: {
            root.now = new Date()
            interval = 60000 - (root.now.getSeconds() * 1000 + root.now.getMilliseconds())
        }
    }

    // ── Weather ─────────────────────────────────────────────────────────────────
    // Where the user is, and what the sky is doing there — with nothing to configure,
    // no account, and no API key.
    //
    // Two public services, both free and key-less: ipwho.is turns this machine's public IP
    // into a coarse location (city-level, which is all a weather widget needs), and
    // Open-Meteo turns that into a forecast. Both verified live from this machine, and
    // verified with the User-Agent Qt actually sends — which is the whole story of why the
    // obvious provider is not the one used here:
    //
    //   ipapi.co answers `curl` perfectly and answers a BROWSER-shaped User-Agent with a
    //   Cloudflare interstitial ("<!DOCTYPE html><title>Just a moment…"). Qt's XMLHttpRequest
    //   sends a browser-shaped User-Agent. So the widget got HTML where it expected JSON,
    //   JSON.parse threw, the catch retried, and the weather row simply never appeared —
    //   with no error anywhere, because a plasmoid's console output is not shown. Testing
    //   the API with curl proves nothing about the API as the widget sees it.
    //
    // WHAT THIS COSTS THE USER, stated plainly because a desktop that phones home
    // quietly is a desktop you cannot trust: two HTTPS requests, the first of which
    // shows the IP to ipapi.co — which already sees it, because it is the request's own
    // source address — and nothing else. No identifiers, no account, no history. The
    // location is never written to disk; it lives in these properties for the session.
    // If either call fails, the row simply is not drawn: a widget that shows a broken
    // weather box is worse than a widget that shows a clock.
    //
    // Refresh: the sky every 15 minutes, the location every 6 hours (an IP does not
    // wander). A failure retries in 2 minutes rather than hammering a free service.
    property real lat: NaN
    property real lon: NaN
    property string city: ""
    property var sky: null          // { temp, feels, code, day, hi, lo } or null
    readonly property bool skyReady: sky !== null && !isNaN(lat)

    function locate() {
        const xhr = new XMLHttpRequest()
        xhr.open("GET", "https://ipwho.is/")
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            if (xhr.status !== 200) {
                retry.restart()
                return
            }
            try {
                const d = JSON.parse(xhr.responseText)
                if (typeof d.latitude !== "number" || typeof d.longitude !== "number")
                    throw new Error("no coordinates")
                root.lat = d.latitude
                root.lon = d.longitude
                root.city = d.city || ""
                root.forecast()
            } catch (e) {
                retry.restart()
            }
        }
        xhr.send()
    }

    function forecast() {
        if (isNaN(root.lat))
            return
        const url = "https://api.open-meteo.com/v1/forecast"
                  + "?latitude=" + root.lat + "&longitude=" + root.lon
                  + "&current=temperature_2m,apparent_temperature,weather_code,is_day"
                  + "&daily=temperature_2m_max,temperature_2m_min&forecast_days=1&timezone=auto"
        const xhr = new XMLHttpRequest()
        xhr.open("GET", url)
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            if (xhr.status !== 200) {
                retry.restart()
                return
            }
            try {
                const d = JSON.parse(xhr.responseText)
                const c = d.current
                root.sky = {
                    temp: Math.round(c.temperature_2m),
                    feels: Math.round(c.apparent_temperature),
                    code: c.weather_code,
                    day: c.is_day === 1,
                    hi: Math.round(d.daily.temperature_2m_max[0]),
                    lo: Math.round(d.daily.temperature_2m_min[0])
                }
            } catch (e) {
                retry.restart()
            }
        }
        xhr.send()
    }

    Component.onCompleted: locate()

    Timer { interval: 15 * 60000; running: true; repeat: true; onTriggered: root.forecast() }
    Timer { interval: 6 * 3600000; running: true; repeat: true; onTriggered: root.locate() }
    Timer { id: retry; interval: 2 * 60000; running: false; repeat: false
            onTriggered: isNaN(root.lat) ? root.locate() : root.forecast() }

    // WMO weather codes (Open-Meteo's `weather_code`), collapsed to the seven skies a
    // person actually distinguishes at a glance. The full table is 28 codes; drawing 28
    // icons would be precision nobody reads.
    function skyKind(code, day) {
        if (code === 0 || code === 1) return day ? "sun" : "moon"
        if (code === 2)               return day ? "partly" : "partlyNight"
        if (code === 3)               return "cloud"
        if (code === 45 || code === 48) return "fog"
        if (code >= 95)               return "storm"
        if ((code >= 71 && code <= 77) || code === 85 || code === 86) return "snow"
        if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82)) return "rain"
        return "cloud"
    }

    function skyNameAr(code) {
        if (code === 0) return "صحو"
        if (code === 1) return "صحو غالباً"
        if (code === 2) return "غائم جزئياً"
        if (code === 3) return "غائم"
        if (code === 45 || code === 48) return "ضباب"
        if (code >= 95) return "عاصفة رعدية"
        if ((code >= 71 && code <= 77) || code === 85 || code === 86) return "ثلج"
        if (code >= 80 && code <= 82) return "زخّات مطر"
        if (code >= 61 && code <= 67) return "مطر"
        if (code >= 51 && code <= 57) return "رذاذ"
        return "غائم"
    }

    fullRepresentation: Item {
        id: face

        implicitWidth: column.implicitWidth + Kirigami.Units.gridUnit * 2
        implicitHeight: column.implicitHeight + Kirigami.Units.gridUnit * 2

        Layout.minimumWidth: implicitWidth
        Layout.minimumHeight: implicitHeight

        // MoOS UI lens: a passive pane behind the existing clock/weather/system
        // composition. It contains no input handler, so the desktop keeps every
        // right-click and rubber-band gesture. The old widget had to draw a heavy
        // inverse halo around every glyph to survive arbitrary wallpapers; this
        // restrained glass surface gives the content one predictable contrast plane
        // while still letting the wallpaper colour breathe through it.
        GlassLens {
            anchors.fill: column
            anchors.margins: -Kirigami.Units.largeSpacing
        }

        // A desktop widget sits on the WALLPAPER, not on a themed surface, and a
        // wallpaper is whatever the user makes it. Kirigami.Theme.textColor alone is
        // not enough: switch to the light theme and the clock turns dark, and on a
        // dark wallpaper it simply vanishes — which is exactly what happened the
        // first time this was tried.
        //
        // The shadow is drawn in the INVERSE of the text colour, so dark text carries
        // a light halo and light text a dark one. Legible either way, on anything.
        MultiEffect {
            anchors.fill: column
            source: column
            shadowEnabled: true
            shadowColor: Kirigami.Theme.textColor.hslLightness > 0.5
                         ? Qt.rgba(0, 0, 0, 0.55)
                         : Qt.rgba(1, 1, 1, 0.55)
            shadowBlur: 0.7
            shadowVerticalOffset: 0
            shadowHorizontalOffset: 0
            shadowOpacity: 0.9
        }

        ColumnLayout {
            id: column
            anchors.centerIn: parent
            spacing: Kirigami.Units.smallSpacing

            // ── The time ─────────────────────────────────────────────────────────
            // Digit by digit, and only the digits that changed.
            //
            // The old clock re-rendered the whole "HH:mm" string and lifted the entire
            // block on every minute, so 14:09 → 14:10 threw four unchanged glyphs into
            // the air along with the two that moved. It read as a twitch. Each digit is
            // its own roller now: the outgoing glyph rises out of the frame while the
            // incoming one climbs in behind it, and a digit that did not change does not
            // move at all. At 14:59 → 15:00 three rollers turn together and it looks like
            // a mechanism; at 14:09 → 14:10 exactly one does.
            RowLayout {
                id: clockRow
                Layout.alignment: Qt.AlignHCenter
                spacing: 0

                readonly property int px: Kirigami.Units.gridUnit * 5
                readonly property string hhmm: Qt.formatTime(root.now, "HH:mm")

                Roller { glyph: clockRow.hhmm.charAt(0); px: clockRow.px }
                Roller { glyph: clockRow.hhmm.charAt(1); px: clockRow.px }

                // The colon does not roll — it breathes. A separator that jumps with the
                // digits is the tic the old animation had; one that fades on the minute is
                // the thing that tells you the clock is live and not a screenshot.
                Text {
                    id: colon
                    Layout.alignment: Qt.AlignVCenter
                    text: ":"
                    color: Kirigami.Theme.textColor
                    font.family: "IBM Plex Sans"
                    font.pixelSize: clockRow.px
                    font.weight: Font.Light
                    opacity: 0.85

                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        running: true
                        NumberAnimation { to: 0.35; duration: 2600; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.85; duration: 2600; easing.type: Easing.InOutSine }
                    }
                }

                Roller { glyph: clockRow.hhmm.charAt(3); px: clockRow.px }
                Roller { glyph: clockRow.hhmm.charAt(4); px: clockRow.px }
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root.arabicLocale.standaloneDayName(root.now.getDay(), Locale.LongFormat)
                      + "، " + Qt.formatDate(root.now, "d ")
                      + root.arabicLocale.standaloneMonthName(root.now.getMonth(), Locale.LongFormat)
                color: Kirigami.Theme.textColor
                opacity: 0.85
                font.family: "IBM Plex Sans Arabic"
                font.pixelSize: Kirigami.Units.gridUnit
                font.weight: Font.Medium
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: Qt.formatDate(root.now, Locale.LongFormat)
                color: Kirigami.Theme.textColor
                opacity: 0.55
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.85)
                font.weight: Font.Normal
            }

            // ── The sky ──────────────────────────────────────────────────────────
            // Drawn, not iconed: the glyph is live vector art (a sun whose rays turn, a
            // cloud that drifts, rain that actually falls), so it never depends on an icon
            // theme the user might change, and it never freezes into a sticker.
            //
            // The whole row fades in when the first forecast lands and is simply absent
            // until then — no spinner, no "—°", no placeholder that looks like a fault.
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.largeSpacing
                visible: root.skyReady
                opacity: root.skyReady ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } }

                SkyGlyph {
                    kind: root.skyReady ? root.skyKind(root.sky.code, root.sky.day) : "cloud"
                    size: Math.round(Kirigami.Units.gridUnit * 2.6)
                }

                Text {
                    text: root.skyReady ? root.sky.temp + "°" : ""
                    color: Kirigami.Theme.textColor
                    font.family: "IBM Plex Sans"
                    font.pixelSize: Math.round(Kirigami.Units.gridUnit * 1.9)
                    font.weight: Font.Light
                    font.features: ({ "tnum": 1 })
                }

                ColumnLayout {
                    spacing: 0

                    Text {
                        text: root.skyReady ? root.skyNameAr(root.sky.code) : ""
                        color: Kirigami.Theme.textColor
                        opacity: 0.9
                        font.family: "IBM Plex Sans Arabic"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.8)
                        font.weight: Font.Medium
                    }

                    Text {
                        text: root.skyReady
                              ? (root.city ? root.city + " · " : "")
                                + "↑" + root.sky.hi + "°  ↓" + root.sky.lo + "°"
                              : ""
                        color: Kirigami.Theme.textColor
                        opacity: 0.55
                        font.family: "IBM Plex Sans"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.65)
                        font.features: ({ "tnum": 1 })
                    }
                }
            }

            // ── The machine's pulse ──────────────────────────────────────────────
            // Three rings, no card, no legend, no title bar. Green while the machine
            // is fine, amber when it is working, red when it is struggling — so the
            // state reads from across the room without a digit being read.
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Kirigami.Units.largeSpacing
                spacing: Math.round(Kirigami.Units.gridUnit * 0.9)

                Gauge { label: "CPU"; sensorId: "cpu/all/usage" }
                Gauge { label: "RAM"; sensorId: "memory/physical/usedPercent" }
                // Removes itself on a machine with no GPU, rather than sitting there
                // at a permanent, meaningless 0%.
                Gauge { label: "GPU"; sensorId: "gpu/gpu0/usage"; hideWhenAbsent: true }
            }
        }
    }

    // ── Warm glass, shared by both MoOS UI variants ───────────────────────────
    // The light theme is warm pearl, not white; the dark theme is aubergine, not
    // blue-black. A very slow sheen is the only motion on the surface itself — the
    // semantic motion remains in the digit rollers and weather glyphs below.
    component GlassLens: Rectangle {
        id: lens

        radius: Math.round(Kirigami.Units.gridUnit * 1.5)
        color: Kirigami.Theme.backgroundColor.hslLightness > 0.55
               ? Qt.rgba(0.95, 0.92, 0.88, 0.70)
               : Qt.rgba(0.10, 0.075, 0.115, 0.72)
        border.width: 1
        border.color: Kirigami.Theme.backgroundColor.hslLightness > 0.55
                      ? Qt.rgba(0.49, 0.23, 0.93, 0.20)
                      : Qt.rgba(0.75, 0.52, 0.99, 0.24)
        clip: true

        Rectangle {
            id: sheen
            width: lens.width * 0.24
            height: lens.height * 1.5
            y: -lens.height * 0.25
            rotation: 16
            opacity: 0.28
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: Qt.rgba(0.95, 0.85, 1.0, 0.22) }
                GradientStop { position: 1.0; color: "transparent" }
            }

            SequentialAnimation on x {
                loops: Animation.Infinite
                running: lens.visible
                PropertyAction { value: -sheen.width * 1.5 }
                PauseAnimation { duration: 5200 }
                NumberAnimation {
                    to: lens.width + sheen.width
                    duration: 6200
                    easing.type: Easing.InOutSine
                }
                PauseAnimation { duration: 8400 }
            }
        }
    }

    // ── One digit of the clock, on a roller ─────────────────────────────────────
    // Two glyphs and a window. The width is measured from "0" with tabular figures on,
    // so every digit occupies the same column and the clock never shifts sideways when a
    // 1 becomes a 2 — the reason the old one needed tnum, kept for the same reason.
    component Roller: Item {
        id: roll

        required property string glyph
        property int px: 40

        // What is currently ON the roller. Bound-through would swap the glyph instantly
        // and there would be nothing left to animate out.
        property string shown: glyph

        implicitWidth: metrics.advanceWidth
        implicitHeight: metrics.height
        Layout.alignment: Qt.AlignVCenter
        clip: true

        TextMetrics {
            id: metrics
            font: incoming.font
            text: "0"
        }

        onGlyphChanged: {
            if (glyph === shown)
                return
            outgoing.text = shown
            incoming.text = glyph
            shown = glyph
            turn.restart()
        }

        Text {
            id: outgoing
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: roll.shown
            color: Kirigami.Theme.textColor
            font.family: "IBM Plex Sans"
            font.pixelSize: roll.px
            font.weight: Font.Light
            font.features: ({ "tnum": 1 })
            opacity: 0
        }

        Text {
            id: incoming
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: roll.shown
            color: Kirigami.Theme.textColor
            font.family: "IBM Plex Sans"
            font.pixelSize: roll.px
            font.weight: Font.Light
            font.features: ({ "tnum": 1 })
        }

        SequentialAnimation {
            id: turn

            // Put the two glyphs in their starting places without animating INTO them —
            // a transition from wherever they were left would show a flicker.
            PropertyAction { target: outgoing; property: "y";       value: 0 }
            PropertyAction { target: outgoing; property: "opacity"; value: 1 }
            PropertyAction { target: outgoing; property: "scale";   value: 1 }
            PropertyAction { target: incoming; property: "y";       value: roll.height * 0.9 }
            PropertyAction { target: incoming; property: "opacity"; value: 0 }
            PropertyAction { target: incoming; property: "scale";   value: 0.92 }

            // The two glyphs must not be legible AT THE SAME TIME. They were, on the first
            // cut — the roll was caught mid-flight in a screenshot and the frame held a
            // half-faded 3 sitting on top of a half-faded 4, which reads as a smear rather
            // than a mechanism. So the old digit is gone (opacity 0) before the new one has
            // faded in: it leaves fast, over the first third of the roll, and the new one
            // only begins to show once the frame is nearly clear.
            ParallelAnimation {
                NumberAnimation {
                    target: outgoing; property: "y"
                    to: -roll.height * 0.9; duration: 400; easing.type: Easing.InCubic
                }
                NumberAnimation {
                    target: outgoing; property: "opacity"
                    to: 0; duration: 170; easing.type: Easing.InQuad
                }
                NumberAnimation {
                    target: outgoing; property: "scale"
                    to: 0.92; duration: 400; easing.type: Easing.InCubic
                }

                // In from below, arriving with the smallest overshoot that still reads as
                // weight rather than as a bounce.
                NumberAnimation {
                    target: incoming; property: "y"
                    to: 0; duration: 560; easing.type: Easing.OutBack; easing.overshoot: 0.7
                }
                NumberAnimation {
                    target: incoming; property: "scale"
                    to: 1; duration: 560; easing.type: Easing.OutBack; easing.overshoot: 0.7
                }
                SequentialAnimation {
                    PauseAnimation { duration: 190 }
                    NumberAnimation {
                        target: incoming; property: "opacity"
                        to: 1; duration: 300; easing.type: Easing.OutCubic
                    }
                }
            }
        }
    }

    // ── The sky, drawn ──────────────────────────────────────────────────────────
    // Every glyph is vector + animation, and every animation is slow. A weather icon
    // that spins fast is a toy; one that turns once every twenty seconds is alive.
    // ── The sky, drawn ──────────────────────────────────────────────────────────
    // Every glyph is vector art plus an animation, and every animation is slow. A weather
    // icon that spins fast is a toy; one that turns once every twenty-four seconds is
    // alive. Drawing them (rather than pulling icon-theme PNGs) also means they cannot go
    // missing when the user changes their icon theme, and they scale to any size.
    component SkyGlyph: Item {
        id: glyph

        required property string kind
        property int size: 40

        implicitWidth: size
        implicitHeight: size
        Layout.preferredWidth: size
        Layout.preferredHeight: size

        readonly property color sunColor: "#FBBF24"
        readonly property color moonColor: "#E2E8F0"
        readonly property color cloudColor: Qt.rgba(Kirigami.Theme.textColor.r,
                                                    Kirigami.Theme.textColor.g,
                                                    Kirigami.Theme.textColor.b, 0.92)
        readonly property color rainColor: "#38BDF8"
        readonly property color snowColor: "#E0F2FE"
        readonly property color boltColor: "#FBBF24"

        readonly property bool clouded: kind === "partly" || kind === "partlyNight"
        readonly property bool hasSun: kind === "sun" || kind === "partly"
        readonly property bool hasMoon: kind === "moon" || kind === "partlyNight"
        readonly property bool hasCloud: kind === "cloud" || clouded
                                         || kind === "rain" || kind === "snow" || kind === "storm"

        // ── The sun: a disc that breathes, inside a crown of rays that turns ──────
        Item {
            id: sun
            width: glyph.size * (glyph.clouded ? 0.50 : 0.60)
            height: width
            visible: glyph.hasSun
            // Pushed up and left when a cloud is coming, so it peeks out from behind it
            // instead of being eclipsed by it.
            x: glyph.width / 2 - width / 2 - (glyph.clouded ? glyph.size * 0.15 : 0)
            y: glyph.height / 2 - height / 2 - (glyph.clouded ? glyph.size * 0.15 : 0)

            Rectangle {
                id: disc
                anchors.centerIn: parent
                width: parent.width * 0.60
                height: width
                radius: width / 2
                color: glyph.sunColor

                SequentialAnimation on scale {
                    loops: Animation.Infinite
                    running: sun.visible
                    NumberAnimation { to: 1.07; duration: 2200; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 1.00; duration: 2200; easing.type: Easing.InOutSine }
                }
            }

            Item {
                id: rays
                anchors.fill: parent

                // Each ray is a bar at 12 o'clock inside a full-size Item that is simply
                // rotated into place. Rotating the CONTAINER (whose origin is its centre,
                // i.e. the sun's centre) is what puts the bar on the rim — no trigonometry,
                // and it stays correct when the size changes.
                Repeater {
                    model: 8
                    delegate: Item {
                        required property int index
                        anchors.fill: parent
                        rotation: index * 45

                        Rectangle {
                            width: Math.max(1.5, sun.width * 0.055)
                            height: sun.width * 0.16
                            radius: width / 2
                            color: glyph.sunColor
                            opacity: 0.9
                            x: sun.width / 2 - width / 2
                            y: 0
                        }
                    }
                }

                RotationAnimation on rotation {
                    running: sun.visible
                    loops: Animation.Infinite
                    from: 0
                    to: 360
                    duration: 24000
                }
            }
        }

        // ── The moon: a crescent cut out of a disc ────────────────────────────────
        // One ShapePath, two circles, OddEvenFill: where the circles overlap, nothing is
        // painted. A second circle in "the background colour" would have been a lie —
        // there is no background here, only wallpaper.
        Shape {
            id: moon
            anchors.fill: parent
            visible: glyph.hasMoon
            preferredRendererType: Shape.CurveRenderer

            readonly property real cx: glyph.width / 2 - (glyph.clouded ? glyph.size * 0.15 : 0)
            readonly property real cy: glyph.height / 2 - (glyph.clouded ? glyph.size * 0.15 : 0)
            readonly property real r: glyph.size * (glyph.clouded ? 0.22 : 0.27)

            ShapePath {
                fillColor: glyph.moonColor
                strokeWidth: 0
                fillRule: ShapePath.OddEvenFill

                PathAngleArc {
                    centerX: moon.cx; centerY: moon.cy
                    radiusX: moon.r; radiusY: moon.r
                    startAngle: 0; sweepAngle: 360
                    moveToStart: true
                }
                PathAngleArc {
                    centerX: moon.cx + moon.r * 0.52; centerY: moon.cy - moon.r * 0.32
                    radiusX: moon.r * 0.92; radiusY: moon.r * 0.92
                    startAngle: 0; sweepAngle: 360
                    moveToStart: true
                }
            }

            SequentialAnimation on opacity {
                loops: Animation.Infinite
                running: moon.visible
                NumberAnimation { to: 0.80; duration: 3200; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.00; duration: 3200; easing.type: Easing.InOutSine }
            }
        }

        // ── The cloud: three lobes and a base, drifting ───────────────────────────
        // The drift is animated on a Translate, not on x: x is set by the layout above,
        // and animating a property something else is also driving is how you get a shape
        // that slowly walks off its own icon.
        Item {
            id: cloud
            width: glyph.size * 0.84
            height: glyph.size * 0.48
            visible: glyph.hasCloud
            x: glyph.width / 2 - width / 2 + (glyph.clouded ? glyph.size * 0.10 : 0)
            y: glyph.height / 2 - height / 2 + (glyph.clouded ? glyph.size * 0.12 : 0)

            transform: Translate { id: drift }

            Rectangle {
                x: 0; y: parent.height * 0.44
                width: parent.width; height: parent.height * 0.52
                radius: height / 2
                color: glyph.cloudColor
            }
            Rectangle {
                x: parent.width * 0.14; y: parent.height * 0.06
                width: parent.width * 0.44; height: width
                radius: width / 2
                color: glyph.cloudColor
            }
            Rectangle {
                x: parent.width * 0.50; y: parent.height * 0.22
                width: parent.width * 0.36; height: width
                radius: width / 2
                color: glyph.cloudColor
            }

            SequentialAnimation {
                running: cloud.visible
                loops: Animation.Infinite
                NumberAnimation { target: drift; property: "x"
                                  to: glyph.size * 0.05; duration: 4200; easing.type: Easing.InOutSine }
                NumberAnimation { target: drift; property: "x"
                                  to: -glyph.size * 0.05; duration: 4200; easing.type: Easing.InOutSine }
            }
        }

        // ── Rain ─────────────────────────────────────────────────────────────────
        // Three drops, each on its own phase (index × 380 ms). Falling in lockstep is the
        // difference between rain and a barcode.
        Repeater {
            model: glyph.kind === "rain" ? 3 : 0
            delegate: Rectangle {
                id: drop
                required property int index
                width: Math.max(1.5, glyph.size * 0.035)
                height: glyph.size * 0.17
                radius: width / 2
                color: glyph.rainColor
                x: glyph.size * (0.30 + index * 0.18)
                y: glyph.size * 0.62
                opacity: 0

                SequentialAnimation {
                    running: true
                    loops: Animation.Infinite
                    PauseAnimation { duration: drop.index * 380 }
                    ParallelAnimation {
                        NumberAnimation { target: drop; property: "y"
                                          from: glyph.size * 0.62; to: glyph.size * 0.95
                                          duration: 900; easing.type: Easing.InQuad }
                        SequentialAnimation {
                            NumberAnimation { target: drop; property: "opacity"; to: 0.95; duration: 200 }
                            NumberAnimation { target: drop; property: "opacity"; to: 0; duration: 700 }
                        }
                    }
                    PauseAnimation { duration: 1140 - drop.index * 380 }
                }
            }
        }

        // ── Snow ─────────────────────────────────────────────────────────────────
        // Same idea, half the speed, and it drifts sideways as it falls, because snow does.
        Repeater {
            model: glyph.kind === "snow" ? 3 : 0
            delegate: Rectangle {
                id: flake
                required property int index
                width: glyph.size * 0.09
                height: width
                radius: width / 2
                color: glyph.snowColor
                x: glyph.size * (0.30 + index * 0.18)
                y: glyph.size * 0.62
                opacity: 0

                transform: Translate { id: sway }

                SequentialAnimation {
                    running: true
                    loops: Animation.Infinite
                    PauseAnimation { duration: flake.index * 620 }
                    ParallelAnimation {
                        NumberAnimation { target: flake; property: "y"
                                          from: glyph.size * 0.62; to: glyph.size * 0.96
                                          duration: 1900; easing.type: Easing.InOutSine }
                        SequentialAnimation {
                            NumberAnimation { target: sway; property: "x"
                                              from: 0; to: glyph.size * 0.05
                                              duration: 950; easing.type: Easing.InOutSine }
                            NumberAnimation { target: sway; property: "x"
                                              to: -glyph.size * 0.03
                                              duration: 950; easing.type: Easing.InOutSine }
                        }
                        SequentialAnimation {
                            NumberAnimation { target: flake; property: "opacity"; to: 0.95; duration: 400 }
                            NumberAnimation { target: flake; property: "opacity"; to: 0; duration: 1500 }
                        }
                    }
                    PauseAnimation { duration: 1860 - flake.index * 620 }
                }
            }
        }

        // ── The bolt ─────────────────────────────────────────────────────────────
        // Dark for four seconds, then two strikes. Storms are rare, so this is the one
        // glyph allowed to be dramatic.
        Shape {
            id: bolt
            anchors.fill: parent
            visible: glyph.kind === "storm"
            preferredRendererType: Shape.CurveRenderer
            opacity: 0

            ShapePath {
                fillColor: glyph.boltColor
                strokeWidth: 0
                startX: glyph.size * 0.52; startY: glyph.size * 0.56
                PathLine { x: glyph.size * 0.40; y: glyph.size * 0.80 }
                PathLine { x: glyph.size * 0.50; y: glyph.size * 0.80 }
                PathLine { x: glyph.size * 0.42; y: glyph.size * 0.99 }
                PathLine { x: glyph.size * 0.66; y: glyph.size * 0.72 }
                PathLine { x: glyph.size * 0.53; y: glyph.size * 0.72 }
                PathLine { x: glyph.size * 0.61; y: glyph.size * 0.56 }
            }

            SequentialAnimation on opacity {
                loops: Animation.Infinite
                running: bolt.visible
                PauseAnimation { duration: 4000 }
                NumberAnimation { to: 1; duration: 60 }
                NumberAnimation { to: 0.15; duration: 90 }
                NumberAnimation { to: 1; duration: 50 }
                NumberAnimation { to: 0; duration: 320 }
            }
        }

        // ── Fog ──────────────────────────────────────────────────────────────────
        // No cloud: fog IS the sky. Three bars sliding past each other at different speeds.
        Repeater {
            model: glyph.kind === "fog" ? 3 : 0
            delegate: Rectangle {
                id: bar
                required property int index
                width: glyph.size * (0.70 - index * 0.08)
                height: Math.max(2, glyph.size * 0.075)
                radius: height / 2
                color: glyph.cloudColor
                opacity: 0.55
                x: glyph.size * 0.15
                y: glyph.size * (0.32 + index * 0.18)

                SequentialAnimation on x {
                    loops: Animation.Infinite
                    running: true
                    PauseAnimation { duration: bar.index * 500 }
                    NumberAnimation { to: glyph.size * 0.25; duration: 2600; easing.type: Easing.InOutSine }
                    NumberAnimation { to: glyph.size * 0.10; duration: 2600; easing.type: Easing.InOutSine }
                }
            }
        }
    }


    component Gauge: Item {
        id: gauge

        required property string label
        required property string sensorId
        property bool hideWhenAbsent: false

        readonly property real value: sensor.value !== undefined && !isNaN(sensor.value)
                                      ? Math.max(0, Math.min(100, sensor.value))
                                      : 0
        readonly property bool present: sensor.status === Sensors.Sensor.Ready

        visible: !hideWhenAbsent || present
        Layout.preferredWidth: visible ? ring.size : 0
        Layout.preferredHeight: visible ? ring.size + caption.implicitHeight + Kirigami.Units.smallSpacing : 0
        implicitWidth: Layout.preferredWidth
        implicitHeight: Layout.preferredHeight

        Sensors.Sensor {
            id: sensor
            sensorId: gauge.sensorId
            updateRateLimit: 1500
        }

        // The value the ARC draws, as opposed to the value the sensor reports. The two
        // are decoupled on purpose: sensors step, and a ring that steps looks broken.
        // This one sweeps.
        property real shown: 0
        onValueChanged: shown = value
        Behavior on shown {
            NumberAnimation { duration: 700; easing.type: Easing.OutCubic }
        }

        property color shownColor: root.tint(shown)
        Behavior on shownColor {
            ColorAnimation { duration: 500; easing.type: Easing.OutCubic }
        }

        Item {
            id: ring
            // Small on purpose. This is an at-a-glance instrument sitting under the
            // clock, not a dashboard: big enough to read the colour and the number,
            // small enough that you stop seeing it.
            readonly property int size: Math.round(Kirigami.Units.gridUnit * 2.5)
            readonly property real stroke: Math.max(3, size * 0.095)

            width: size
            height: size
            anchors.horizontalCenter: parent.horizontalCenter

            Shape {
                anchors.fill: parent
                preferredRendererType: Shape.CurveRenderer

                // The track. Faint, so the ring still reads as a gauge at 0%.
                ShapePath {
                    strokeWidth: ring.stroke
                    strokeColor: Qt.rgba(Kirigami.Theme.textColor.r,
                                         Kirigami.Theme.textColor.g,
                                         Kirigami.Theme.textColor.b, 0.16)
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    PathAngleArc {
                        centerX: ring.size / 2
                        centerY: ring.size / 2
                        radiusX: (ring.size - ring.stroke) / 2
                        radiusY: (ring.size - ring.stroke) / 2
                        startAngle: 135
                        sweepAngle: 270
                    }
                }

                // The value.
                ShapePath {
                    strokeWidth: ring.stroke
                    strokeColor: gauge.shownColor
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    PathAngleArc {
                        centerX: ring.size / 2
                        centerY: ring.size / 2
                        radiusX: (ring.size - ring.stroke) / 2
                        radiusY: (ring.size - ring.stroke) / 2
                        startAngle: 135
                        sweepAngle: 270 * (gauge.shown / 100)
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                text: Math.round(gauge.shown) + "%"
                color: Kirigami.Theme.textColor
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.round(ring.size * 0.28)
                font.weight: Font.DemiBold
                font.features: ({ "tnum": 1 })
            }
        }

        Text {
            id: caption
            anchors.top: ring.bottom
            anchors.topMargin: Kirigami.Units.smallSpacing
            anchors.horizontalCenter: parent.horizontalCenter
            text: gauge.label
            color: Kirigami.Theme.textColor
            opacity: 0.6
            font.family: "IBM Plex Sans"
            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.55)
            font.weight: Font.Medium
            font.letterSpacing: 1
        }
    }
}
