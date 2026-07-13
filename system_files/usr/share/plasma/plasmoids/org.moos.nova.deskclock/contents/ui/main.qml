// MoOS Nova Desk Clock — the clock on the desktop, and the machine's pulse under it.
//
// ONE widget, not two, and that is deliberate. The rings began life as a separate
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

    fullRepresentation: Item {
        id: face

        implicitWidth: column.implicitWidth + Kirigami.Units.gridUnit * 2
        implicitHeight: column.implicitHeight + Kirigami.Units.gridUnit * 2

        Layout.minimumWidth: implicitWidth
        Layout.minimumHeight: implicitHeight

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

            Text {
                id: timeText
                Layout.alignment: Qt.AlignHCenter
                text: Qt.formatTime(root.now, "HH:mm")
                color: Kirigami.Theme.textColor
                font.family: "IBM Plex Sans"
                font.pixelSize: Kirigami.Units.gridUnit * 5
                font.weight: Font.Light
                // Tabular figures: without them the whole clock shifts sideways every
                // time a 1 becomes a 2. The parentheses are load-bearing —
                // `font.features: { "tnum": 1 }` parses as a JS block, not an object
                // literal, and silently yields undefined.
                font.features: ({ "tnum": 1 })

                // The minute does not snap over, it lifts and settles. Short and small
                // on purpose: this fires once a minute for the life of the session, and
                // anything longer than a breath becomes a tic you cannot stop watching.
                transform: Translate { id: lift }
                onTextChanged: minuteTurn.restart()

                SequentialAnimation {
                    id: minuteTurn
                    ParallelAnimation {
                        NumberAnimation {
                            target: lift; property: "y"
                            from: 0; to: -Kirigami.Units.smallSpacing * 1.5
                            duration: 140; easing.type: Easing.OutCubic
                        }
                        NumberAnimation {
                            target: timeText; property: "opacity"
                            from: 1; to: 0.55; duration: 140; easing.type: Easing.OutCubic
                        }
                    }
                    ParallelAnimation {
                        NumberAnimation {
                            target: lift; property: "y"
                            to: 0; duration: 320; easing.type: Easing.OutBack
                        }
                        NumberAnimation {
                            target: timeText; property: "opacity"
                            to: 1; duration: 320; easing.type: Easing.OutCubic
                        }
                    }
                }
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
