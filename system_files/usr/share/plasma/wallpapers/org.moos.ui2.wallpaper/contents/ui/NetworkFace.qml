// The device card's second face: what is moving, and what is left.
//
// The rings on the first face answer "is the machine busy" as percentages. The
// questions that follow on a real desk are "is the network doing anything right
// now" and "how much room is actually left" — and a percentage answers neither.
// Two live rates and one figure in gigabytes, from the same ksystemstats source
// the rings already use.
//
// Every value is present-gated on its sensor's Ready status, exactly like the
// rings: a machine that does not expose one shows "—" rather than a confident
// zero.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.sensors as Sensors
import org.moos.ui as MoUI

Item {
    id: face

    readonly property bool rtl: MoUI.Locale.rtl
    readonly property var design: MoUI.Tokens
    readonly property string labelFamily: rtl ? "IBM Plex Sans Arabic" : "IBM Plex Sans"
    function local(arabic, english) { return MoUI.Locale.local(arabic, english) }

    // A rate or a size is a technical token: it reads left to right in every
    // session, like the temperatures and the dates on the other cards.
    function ltr(value) { return "⁦" + value + "⁩" }

    function rate(bytesPerSecond, ready) {
        if (!ready || bytesPerSecond === undefined || isNaN(bytesPerSecond)) { return "—" }
        const perSecond = Math.max(0, bytesPerSecond)
        if (perSecond < 1024) { return face.ltr(Math.round(perSecond) + " B/s") }
        if (perSecond < 1024 * 1024) { return face.ltr((perSecond / 1024).toFixed(0) + " KB/s") }
        return face.ltr((perSecond / (1024 * 1024)).toFixed(1) + " MB/s")
    }

    function gigabytes(bytes, ready) {
        if (!ready || bytes === undefined || isNaN(bytes)) { return "—" }
        return face.ltr((bytes / (1000 * 1000 * 1000)).toFixed(0) + " GB")
    }

    Sensors.Sensor {
        id: downloadSensor
        sensorId: "network/all/download"
        updateRateLimit: 3000
    }
    Sensors.Sensor {
        id: uploadSensor
        sensorId: "network/all/upload"
        updateRateLimit: 3000
    }
    Sensors.Sensor {
        id: freeSensor
        sensorId: "disk/all/free"
        updateRateLimit: 30000
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            Rectangle {
                Layout.preferredWidth: Math.max(5, Kirigami.Units.gridUnit * 0.34)
                Layout.preferredHeight: Layout.preferredWidth
                radius: width / 2
                color: Kirigami.Theme.highlightColor
            }
            Text {
                text: face.local("الشبكة والمساحة", "NETWORK & SPACE")
                color: Kirigami.Theme.disabledTextColor
                font.family: face.labelFamily
                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.55)
                font.weight: Font.DemiBold
                font.letterSpacing: face.rtl ? 0 : 1.8
            }
            Item { Layout.fillWidth: true }
        }

        Item { Layout.fillHeight: true }

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            columnSpacing: Kirigami.Units.largeSpacing
            rowSpacing: 2

            Repeater {
                model: [
                    {
                        label: face.local("تنزيل", "DOWN"),
                        value: face.rate(downloadSensor.value,
                                         downloadSensor.status === Sensors.Sensor.Ready)
                    },
                    {
                        label: face.local("رفع", "UP"),
                        value: face.rate(uploadSensor.value,
                                         uploadSensor.status === Sensors.Sensor.Ready)
                    },
                    {
                        label: face.local("متاح", "FREE"),
                        value: face.gigabytes(freeSensor.value,
                                              freeSensor.status === Sensors.Sensor.Ready)
                    }
                ]
                delegate: ColumnLayout {
                    id: figure
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 0

                    Text {
                        Layout.fillWidth: true
                        text: figure.modelData.label
                        color: Kirigami.Theme.disabledTextColor
                        font.family: face.labelFamily
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.5)
                        font.weight: Font.Medium
                        font.letterSpacing: face.rtl ? 0 : 1.2
                        horizontalAlignment: Text.AlignLeft
                    }
                    Text {
                        Layout.fillWidth: true
                        text: figure.modelData.value
                        color: Kirigami.Theme.textColor
                        font.family: "IBM Plex Sans"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 1.05)
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignLeft
                        elide: Text.ElideRight
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
