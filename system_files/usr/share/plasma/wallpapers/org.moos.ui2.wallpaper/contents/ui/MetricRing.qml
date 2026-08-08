// MetricRing — a premium animated circular gauge for one system metric, replacing
// the old 3px linear MetricPill. A faint full-circle track with a coloured progress
// arc that sweeps from the top (−90°), an odometer-style count-up number in the
// centre, and a label beneath. All motion is gated by `motionEnabled` (Plasma's
// "reduce animations"), and every colour comes from the active palette so it themes
// on Graphite/Tidal. Hardware-accelerated via QtQuick.Shapes (PathAngleArc).
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: ring

    required property string label
    required property real value        // 0..100
    required property bool present
    required property bool motionEnabled
    // MotionMode 2 ("alive"). The ring's accent is the halo below.
    required property bool accentMotion
    property color accentColor: Kirigami.Theme.highlightColor

    readonly property real clampedValue: Math.max(0, Math.min(100, value))
    property real displayedValue: present ? clampedValue : 0

    // The sensor refreshes every five seconds. Keep its interpolation far shorter
    // than that cadence: at the old 1.5 s sample / ~0.7 s animation pair, three
    // rings kept the 4K wallpaper repainting almost half of every second and held
    // plasmashell around 9% even after every endless animation had been removed.
    // shortDuration still follows Plasma's animation-speed slider and leaves the
    // card visually alive without turning telemetry into ambient animation.
    Behavior on displayedValue {
        enabled: ring.motionEnabled
        NumberAnimation {
            duration: Kirigami.Units.shortDuration
            easing.type: Easing.OutCubic
        }
    }

    // Reserve ~1 grid unit under the ring for the label; break the width→label→width
    // cycle by NOT reading the label's height back into the diameter.
    readonly property real diameter: Math.max(24, Math.min(width, height - Math.round(Kirigami.Units.gridUnit * 0.95)))
    readonly property real stroke: Math.max(3, ring.diameter * 0.11)

    // ── Why the arcs do not reach the item's edge ─────────────────────────────
    //
    // A Shape does NOT clip to its item. The halo below is drawn 1.8x as wide as
    // the arc it sits behind, so it needs 0.4 stroke-widths of room on each side
    // of that arc — and the first version gave it none: it stroked 2.5x the width
    // on an arc whose own radius already reached the item edge, putting 0.75
    // stroke-widths of halo OUTSIDE the item. Rendered with the real Qt runtime
    // (not the offscreen smoke, which never lays these out at a real size) the
    // three rings sit side by side in one row, and their three halos overlapped
    // into a single blob spanning the card.
    //
    // Pull the shared arc radius in by half the halo's width and the outermost
    // pixel the ring can paint is exactly the item's edge, halo included. This
    // geometry is CONSTANT across every motion level on purpose: only the halo's
    // colour appears and disappears, so switching still/gentle/alive never
    // resizes or relayouts the gauge.
    readonly property real glowStroke: ring.stroke * 1.8
    readonly property real arcRadius: ring.diameter / 2 - ring.glowStroke / 2

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Math.round(Kirigami.Units.smallSpacing * 0.5)

        Item {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: ring.diameter
            Layout.preferredHeight: ring.diameter

            Shape {
                anchors.fill: parent
                antialiasing: true
                preferredRendererType: Shape.CurveRenderer

                ShapePath {   // track
                    strokeWidth: ring.stroke
                    strokeColor: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                         Kirigami.Theme.textColor.b, 0.12)
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    PathAngleArc {
                        centerX: ring.diameter / 2; centerY: ring.diameter / 2
                        radiusX: ring.arcRadius
                        radiusY: ring.arcRadius
                        startAngle: -90; sweepAngle: 360
                    }
                }

                // The `alive` accent: a wider, softer halo behind the progress
                // arc. It is deliberately STATIC — three gauges each running
                // their own breathing loop would be three permanent repaint
                // sources for a decoration nobody stares at, and `alive` already
                // buys its life from the card sheen and the beacon ripple, both
                // of which rest between passes. A halo that simply appears costs
                // nothing per frame and is still plainly visible.
                ShapePath {   // progress glow — halo behind the arc
                    strokeWidth: ring.glowStroke
                    strokeColor: ring.present
                                 && ring.motionEnabled && ring.accentMotion
                               ? Qt.rgba(ring.accentColor.r, ring.accentColor.g,
                                         ring.accentColor.b, 0.18)
                               : "transparent"
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    PathAngleArc {
                        centerX: ring.diameter / 2; centerY: ring.diameter / 2
                        radiusX: ring.arcRadius
                        radiusY: ring.arcRadius
                        startAngle: -90
                        sweepAngle: 360 * ring.displayedValue / 100
                    }
                }

                ShapePath {   // progress
                    strokeWidth: ring.stroke
                    strokeColor: ring.present ? ring.accentColor
                               : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                         Kirigami.Theme.textColor.b, 0.2)
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    PathAngleArc {
                        centerX: ring.diameter / 2; centerY: ring.diameter / 2
                        radiusX: ring.arcRadius
                        radiusY: ring.arcRadius
                        startAngle: -90
                        sweepAngle: 360 * ring.displayedValue / 100
                    }
                }
            }

            // Tick marks at 25%, 50%, 75%, 100% on the track
            Repeater {
                model: [0.25, 0.50, 0.75, 1.00]
                Rectangle {
                    required property real modelData
                    readonly property real angle: -90 + 360 * modelData
                    readonly property real rad: angle * Math.PI / 180
                    readonly property real trackR: ring.arcRadius
                    x: ring.diameter / 2 + trackR * Math.cos(rad) - width / 2
                    y: ring.diameter / 2 + trackR * Math.sin(rad) - height / 2
                    width: Math.max(2, ring.stroke * 0.35)
                    height: width
                    radius: width / 2
                    color: Qt.rgba(Kirigami.Theme.textColor.r,
                                   Kirigami.Theme.textColor.g,
                                   Kirigami.Theme.textColor.b, 0.18)
                }
            }

            Text {   // centre readout
                anchors.centerIn: parent
                text: ring.present ? Math.round(ring.displayedValue) : "—"
                color: Kirigami.Theme.textColor
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.round(ring.diameter * 0.32)
                font.weight: Font.Light
                font.features: ({ "tnum": 1 })
            }
            Text {
                visible: ring.present
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.verticalCenter
                anchors.topMargin: Math.round(ring.diameter * 0.17)
                text: "%"
                color: Kirigami.Theme.disabledTextColor
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.round(ring.diameter * 0.14)
            }
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: ring.label
            color: Kirigami.Theme.disabledTextColor
            font.family: "IBM Plex Sans"
            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.46)
            font.weight: Font.DemiBold
            font.letterSpacing: 1.1
        }
    }
}
