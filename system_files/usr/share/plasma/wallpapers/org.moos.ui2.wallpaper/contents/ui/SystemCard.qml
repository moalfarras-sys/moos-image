// Device-health card: a live verdict plus animated CPU / RAM / Disk rings, drawn
// from ksystemstats runtime sensor IDs (not hardware-name labels). Each ring is
// present-gated on its sensor's Ready status, so a metric the machine does not
// expose simply shows "—" instead of a dead gauge (this is why the old GPU pill,
// which yields nothing on the open NVK driver, is replaced by the Disk ring).
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
    readonly property real diskValue: safeValue(diskSensor.value)
    readonly property bool cpuPresent: cpuSensor.status === Sensors.Sensor.Ready
    readonly property bool memoryPresent: memorySensor.status === Sensors.Sensor.Ready
    readonly property bool diskPresent: diskSensor.status === Sensors.Sensor.Ready
    // CPU and RAM are the minimum evidence for a system-health verdict.
    readonly property bool coreSensorsReady: cpuPresent && memoryPresent
    // Disk fullness is normal and must NOT drive the "pressure" verdict — only live
    // load (CPU/RAM) does.
    readonly property real peakValue: Math.max(cpuValue, memoryValue)
    readonly property color healthColor: !coreSensorsReady
        ? Kirigami.Theme.disabledTextColor
        : (peakValue >= 88
           ? Kirigami.Theme.negativeTextColor
           : (peakValue >= 65 ? Kirigami.Theme.neutralTextColor
                              : Kirigami.Theme.positiveTextColor))
    // "BUSY" (not "PRESSURED"): the fixed-width verdict column elides a 9-letter
    // word exactly at high load — the one moment the verdict matters most. A short
    // token fits like HEALTHY/ACTIVE without stealing width from the rings.
    readonly property string healthLabel: !coreSensorsReady
        ? "WAITING"
        : (peakValue >= 88 ? "BUSY"
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
        id: diskSensor
        sensorId: "disk/all/usedPercent"
        updateRateLimit: 1500
    }

    GlassCard {
        anchors.fill: parent
        motionEnabled: systemCard.motionEnabled
        entranceDelay: systemCard.entranceDelay

        RowLayout {
            anchors.fill: parent
            spacing: Math.round(Kirigami.Units.gridUnit * 0.5)

            // ── Verdict strip. FIXED width (fillWidth:false) — without this it eats
            //    the whole row and the rings collapse to a few pixels. ────────────
            ColumnLayout {
                Layout.fillWidth: false
                // HEALTHY is the widest normal verdict. 3.35 grid units clipped
                // it to "HEALT…" at the supported 4K/200% desktop scale.
                Layout.preferredWidth: Math.round(Kirigami.Units.gridUnit * 4.2)
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
                            NumberAnimation { to: 0.38; duration: 1500; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 1;    duration: 1500; easing.type: Easing.InOutSine }
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

            MetricRing {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: Math.round(Kirigami.Units.gridUnit * 2.4)
                label: "CPU"
                value: systemCard.cpuValue
                present: systemCard.cpuPresent
                motionEnabled: systemCard.motionEnabled
                accentColor: Kirigami.Theme.highlightColor
            }

            MetricRing {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: Math.round(Kirigami.Units.gridUnit * 2.4)
                label: "RAM"
                value: systemCard.memoryValue
                present: systemCard.memoryPresent
                motionEnabled: systemCard.motionEnabled
                accentColor: Kirigami.Theme.linkColor
            }

            MetricRing {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: Math.round(Kirigami.Units.gridUnit * 2.4)
                label: "DISK"
                value: systemCard.diskValue
                present: systemCard.diskPresent
                motionEnabled: systemCard.motionEnabled
                accentColor: Kirigami.Theme.positiveTextColor
            }
        }
    }
}
