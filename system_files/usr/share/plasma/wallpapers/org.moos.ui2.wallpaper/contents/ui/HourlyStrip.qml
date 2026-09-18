// The weather card's second face: the next few hours.
//
// The card answers "what is it like now". The question that follows it on a real
// desk is "and at four?" — and answering it meant opening an app. Six hours, from
// the SAME request the card already makes (one more parameter on the forecast
// call, no second service and no extra poll), each with its own glyph and
// temperature.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Item {
    id: strip

    // [{ hour: "16:00", temperature: 21, code: 3 }, …] — empty is a normal state:
    // a provider that omits the hourly block leaves this face saying so rather
    // than making the card fail.
    required property var hours
    required property string city
    property bool weatherReady: false
    // Which artwork a weather code wears — the card that owns this face passes the
    // same `weatherKind(code, daylight)` the front face uses, so one code cannot
    // mean two pictures on two faces of one card.
    required property var kindForCode

    readonly property bool rtl: MoUI.Locale.rtl
    readonly property var design: MoUI.Tokens
    readonly property string labelFamily: rtl ? "IBM Plex Sans Arabic" : "IBM Plex Sans"
    function local(arabic, english) { return MoUI.Locale.local(arabic, english) }
    // A temperature is an LTR island inside an Arabic label, the same rule the
    // front face follows.
    function degrees(value) { return "⁦" + value + "°⁩" }

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
                text: strip.local("الساعات القادمة", "NEXT HOURS")
                color: Kirigami.Theme.disabledTextColor
                font.family: strip.labelFamily
                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.55)
                font.weight: Font.DemiBold
                font.letterSpacing: strip.rtl ? 0 : 1.8
            }
            Item { Layout.fillWidth: true }
            Text {
                text: strip.city
                color: Kirigami.Theme.disabledTextColor
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.52)
                font.weight: Font.Medium
                elide: Text.ElideRight
                Layout.maximumWidth: Kirigami.Units.gridUnit * 6
            }
        }

        Item { Layout.preferredHeight: Kirigami.Units.gridUnit * 0.5 }

        Text {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !strip.weatherReady || strip.hours === undefined
                     || strip.hours === null || strip.hours.length === 0
            text: strip.weatherReady
                ? strip.local("لا توجد قراءة بالساعة الآن", "No hourly reading right now")
                : strip.local("…", "…")
            color: Kirigami.Theme.disabledTextColor
            font.family: strip.labelFamily
            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.62)
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Kirigami.Units.smallSpacing
            visible: strip.weatherReady && strip.hours !== undefined
                     && strip.hours !== null && strip.hours.length > 0

            Repeater {
                model: strip.hours
                delegate: Item {
                    id: slot
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 2

                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            // An hour is a technical token: it reads left to right in
                            // every session.
                            text: "⁦" + slot.modelData.hour + "⁩"
                            color: Kirigami.Theme.disabledTextColor
                            font.family: "IBM Plex Sans"
                            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.5)
                            font.weight: Font.Medium
                        }
                        Image {
                            Layout.alignment: Qt.AlignHCenter
                            Layout.preferredWidth: Math.round(Kirigami.Units.gridUnit * 1.5)
                            Layout.preferredHeight: Layout.preferredWidth
                            source: Qt.resolvedUrl("../images/weather/"
                                                   + strip.kindForCode(slot.modelData.code) + ".png")
                            sourceSize.width: Math.round(Kirigami.Units.gridUnit * 3)
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                            smooth: true
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: strip.degrees(slot.modelData.temperature)
                            color: Kirigami.Theme.textColor
                            font.family: "IBM Plex Sans"
                            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.8)
                            font.weight: Font.DemiBold
                        }
                    }
                }
            }
        }
    }
}
