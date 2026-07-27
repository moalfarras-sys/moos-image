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
    // MotionMode 2 ("alive"). This card owns two of the three accents that make
    // the level worth having: the beacon's ripple and the rings' halo.
    required property bool accentMotion
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
        accentMotion: systemCard.accentMotion
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

                        // The `alive` accent: a slow ripple out of the status dot.
                        //
                        // It is a CHILD with its own visibility gate rather than an
                        // opacity animation on the dot itself, for two reasons. The
                        // dot's colour is INFORMATION — it is the health verdict —
                        // and decoration must never dim information; a user glancing
                        // at a half-faded red dot cannot tell fading from failing.
                        // And a `SequentialAnimation on opacity` is a property value
                        // source: it owns the property and, when `running` goes
                        // false, stops writing without rewinding, so dropping from
                        // alive to gentle mid-fade used to leave the beacon
                        // permanently half-dim with nothing left to restore it. A
                        // frozen ripple that is not drawn costs and shows nothing.
                        Rectangle {
                            id: beaconRipple
                            anchors.centerIn: parent
                            width: parent.width
                            height: parent.height
                            radius: width / 2
                            color: "transparent"
                            border.width: 1
                            border.color: systemCard.healthColor
                            visible: systemCard.motionEnabled && systemCard.accentMotion
                            opacity: 0

                            SequentialAnimation {
                                running: systemCard.motionEnabled && systemCard.accentMotion
                                loops: Animation.Infinite
                                ParallelAnimation {
                                    NumberAnimation {
                                        target: beaconRipple
                                        property: "scale"
                                        from: 1
                                        to: 2.6
                                        duration: 1400
                                        easing.type: Easing.OutCubic
                                    }
                                    SequentialAnimation {
                                        NumberAnimation {
                                            target: beaconRipple
                                            property: "opacity"
                                            from: 0
                                            to: 0.55
                                            duration: 260
                                        }
                                        NumberAnimation {
                                            target: beaconRipple
                                            property: "opacity"
                                            to: 0
                                            duration: 1140
                                            easing.type: Easing.InQuad
                                        }
                                    }
                                }
                                // EVERY looping animation in this package rests,
                                // `alive` included: an infinite QML animation pins
                                // the render loop at the full frame rate and repaints
                                // the whole window for as long as it runs, about 11%
                                // of a CPU core whatever the item's size. 1.4 s of
                                // ripple in a 6 s cycle is a ~23% duty cycle and
                                // reads as a heartbeat rather than a strobe.
                                PauseAnimation { duration: 4600 }
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
                accentMotion: systemCard.accentMotion
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
                accentMotion: systemCard.accentMotion
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
                accentMotion: systemCard.accentMotion
                accentColor: Kirigami.Theme.positiveTextColor
            }
        }
    }
}
