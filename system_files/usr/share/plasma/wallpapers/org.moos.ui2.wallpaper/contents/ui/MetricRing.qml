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
    property color accentColor: Kirigami.Theme.highlightColor

    readonly property real clampedValue: Math.max(0, Math.min(100, value))
    property real displayedValue: present ? clampedValue : 0

    Behavior on displayedValue {
        enabled: ring.motionEnabled
        NumberAnimation { duration: 700; easing.type: Easing.OutCubic }
    }

    // Reserve ~1 grid unit under the ring for the label; break the width→label→width
    // cycle by NOT reading the label's height back into the diameter.
    readonly property real diameter: Math.max(24, Math.min(width, height - Math.round(Kirigami.Units.gridUnit * 0.95)))
    readonly property real stroke: Math.max(3, ring.diameter * 0.11)

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
                        radiusX: ring.diameter / 2 - ring.stroke / 2
                        radiusY: ring.diameter / 2 - ring.stroke / 2
                        startAngle: -90; sweepAngle: 360
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
                        radiusX: ring.diameter / 2 - ring.stroke / 2
                        radiusY: ring.diameter / 2 - ring.stroke / 2
                        startAngle: -90
                        sweepAngle: 360 * ring.displayedValue / 100
                    }
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
