// Verified Plasma system-monitor sensor IDs. These are runtime IDs from
// ksystemstats, not labels inferred from the hardware names.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.sensors as Sensors

Item {
    id: systemCard

    required property bool motionEnabled
    property int entranceDelay: 0

    readonly property real cpuValue: safeValue(cpuSensor.value)
    readonly property real memoryValue: safeValue(memorySensor.value)
    readonly property real gpuValue: safeValue(gpuSensor.value)
    readonly property bool cpuPresent: cpuSensor.status === Sensors.Sensor.Ready
    readonly property bool memoryPresent: memorySensor.status === Sensors.Sensor.Ready
    readonly property bool gpuPresent: gpuSensor.status === Sensors.Sensor.Ready
    // CPU and RAM are the minimum evidence for a system-health verdict. GPU is
    // optional because the generic edition may expose no GPU usage sensor.
    readonly property bool coreSensorsReady: cpuPresent && memoryPresent
    readonly property real peakValue: Math.max(cpuValue, memoryValue,
                                               gpuPresent ? gpuValue : 0)
    readonly property color healthColor: !coreSensorsReady
        ? Kirigami.Theme.disabledTextColor
        : (peakValue >= 88
           ? Kirigami.Theme.negativeTextColor
           : (peakValue >= 65 ? Kirigami.Theme.neutralTextColor
                              : Kirigami.Theme.positiveTextColor))
    readonly property string healthLabel: !coreSensorsReady
        ? "WAITING"
        : (peakValue >= 88 ? "PRESSURED"
                           : (peakValue >= 65 ? "ACTIVE" : "HEALTHY"))

    function safeValue(rawValue) {
        if (rawValue === undefined || isNaN(rawValue)) {
            return 0
        }
        return Math.max(0, Math.min(100, rawValue))
    }

    Sensors.Sensor {
        id: cpuSensor
        sensorId: "cpu/all/usage"
        updateRateLimit: 1500
    }

    Sensors.Sensor {
        id: memorySensor
        sensorId: "memory/physical/usedPercent"
        updateRateLimit: 1500
    }

    Sensors.Sensor {
        id: gpuSensor
        sensorId: "gpu/gpu0/usage"
        updateRateLimit: 1500
    }

    GlassCard {
        anchors.fill: parent
        motionEnabled: systemCard.motionEnabled
        entranceDelay: systemCard.entranceDelay

        RowLayout {
            anchors.fill: parent
            spacing: Math.round(Kirigami.Units.gridUnit * 0.65)

            ColumnLayout {
                Layout.preferredWidth: Math.round(Kirigami.Units.gridUnit * 3.35)
                Layout.fillHeight: true
                spacing: 0

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing

                    Rectangle {
                        id: beacon
                        Layout.preferredWidth: Math.max(6, Kirigami.Units.gridUnit * 0.42)
                        Layout.preferredHeight: Layout.preferredWidth
                        radius: width / 2
                        color: systemCard.healthColor

                        SequentialAnimation on opacity {
                            running: systemCard.motionEnabled && beacon.visible
                            loops: Animation.Infinite
                            NumberAnimation {
                                to: 0.38
                                duration: 1500
                                easing.type: Easing.InOutSine
                            }
                            NumberAnimation {
                                to: 1
                                duration: 1500
                                easing.type: Easing.InOutSine
                            }
                        }
                    }
                    Text {
                        text: "SYSTEM"
                        color: Kirigami.Theme.disabledTextColor
                        font.family: "IBM Plex Sans"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.5)
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1.4
                    }
                }

                Item { Layout.fillHeight: true }

                Text {
                    // "PRESSURED" (9 chars) at this size is wider than the fixed
                    // status column, so it used to overlap into the CPU pill.
                    // Fill the column and elide instead of overrunning it.
                    Layout.fillWidth: true
                    text: systemCard.healthLabel
                    color: systemCard.healthColor
                    font.family: "IBM Plex Sans"
                    font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.66)
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.1
                    elide: Text.ElideRight
                }
            }

            MetricPill {
                Layout.fillWidth: true
                Layout.fillHeight: true
                label: "CPU"
                value: systemCard.cpuValue
                present: systemCard.cpuPresent
                motionEnabled: systemCard.motionEnabled
                accentColor: Kirigami.Theme.highlightColor
            }

            MetricPill {
                Layout.fillWidth: true
                Layout.fillHeight: true
                label: "RAM"
                value: systemCard.memoryValue
                present: systemCard.memoryPresent
                motionEnabled: systemCard.motionEnabled
                accentColor: Kirigami.Theme.linkColor
            }

            MetricPill {
                Layout.fillWidth: true
                Layout.fillHeight: true
                label: "GPU"
                value: systemCard.gpuValue
                present: systemCard.gpuPresent
                motionEnabled: systemCard.motionEnabled
                accentColor: Kirigami.Theme.positiveTextColor
            }
        }
    }
}
