// The clock card's second page: this week, with today marked.
//
// The card answers "what time is it" at a glance. The question that follows it on
// a real desk is "what is the date — and what day is the 20th", and answering that
// meant opening a calendar. Seven cells, the week the owner is standing in, today
// filled with the family accent. Nothing is fetched and nothing ticks: it is drawn
// from the same `now` the clock already has.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Item {
    id: strip

    required property date now
    readonly property bool rtl: MoUI.Locale.rtl
    readonly property var design: MoUI.Tokens
    readonly property string labelFamily: rtl ? "IBM Plex Sans Arabic" : "IBM Plex Sans"
    function local(arabic, english) { return MoUI.Locale.local(arabic, english) }

    // The week the locale itself starts on — Saturday in Arabic, Monday in
    // English — so the row reads the way the person's own calendar does rather
    // than the way a hardcoded index would.
    readonly property int dayOfYear: {
        const first = new Date(strip.now.getFullYear(), 0, 1)
        return Math.floor((strip.now - first) / 86400000) + 1
    }
    readonly property int firstDay: Qt.locale().firstDayOfWeek
    readonly property date weekStart: {
        const start = new Date(strip.now)
        start.setHours(0, 0, 0, 0)
        const offset = (start.getDay() - strip.firstDay + 7) % 7
        start.setDate(start.getDate() - offset)
        return start
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
                text: strip.local("هذا الأسبوع", "THIS WEEK")
                color: Kirigami.Theme.disabledTextColor
                font.family: strip.labelFamily
                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.55)
                font.weight: Font.DemiBold
                font.letterSpacing: strip.rtl ? 0 : 1.8
            }
            Item { Layout.fillWidth: true }
            Text {
                // The month the week belongs to, so a week that straddles two
                // months still says which one today is in.
                text: Qt.formatDate(strip.now, Qt.locale(strip.rtl ? "ar" : "en"), "MMMM yyyy")
                color: Kirigami.Theme.disabledTextColor
                font.family: strip.labelFamily
                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.52)
                font.weight: Font.Medium
            }
        }

        Item { Layout.preferredHeight: Kirigami.Units.gridUnit * 0.7 }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Kirigami.Units.smallSpacing

            Repeater {
                model: 7
                delegate: Item {
                    id: cell
                    required property int index
                    readonly property date day: {
                        const value = new Date(strip.weekStart)
                        value.setDate(value.getDate() + cell.index)
                        return value
                    }
                    readonly property bool today:
                        cell.day.getDate() === strip.now.getDate()
                        && cell.day.getMonth() === strip.now.getMonth()
                        && cell.day.getFullYear() === strip.now.getFullYear()
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    Rectangle {
                        anchors.centerIn: parent
                        width: Math.min(parent.width, Math.round(Kirigami.Units.gridUnit * 2.1))
                        height: Math.min(parent.height, Math.round(Kirigami.Units.gridUnit * 2.6))
                        radius: strip.design.radiusControl
                        color: cell.today ? Kirigami.Theme.highlightColor : "transparent"
                        opacity: cell.today ? 0.92 : 1
                        border.width: cell.today ? 0 : 1
                        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.12)

                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 0

                            Text {
                                // Arabic day names are long ("الأربعاء" is eight
                                // glyphs) and a fixed size clipped the widest of
                                // them inside the cell — seen on the station on
                                // 2026-09-18, where "الجمعة" lost its first letter
                                // in the today cell. Fit the name to the cell and
                                // let the size fall, never the letters.
                                Layout.alignment: Qt.AlignHCenter
                                Layout.preferredWidth: Math.max(
                                    1, Math.round(Kirigami.Units.gridUnit * 1.9))
                                horizontalAlignment: Text.AlignHCenter
                                fontSizeMode: Text.HorizontalFit
                                minimumPixelSize: Math.round(Kirigami.Units.gridUnit * 0.34)
                                text: Qt.locale(strip.rtl ? "ar" : "en").standaloneDayName(
                                          cell.day.getDay(), Locale.ShortFormat)
                                color: cell.today ? Kirigami.Theme.highlightedTextColor
                                                  : Kirigami.Theme.disabledTextColor
                                font.family: strip.labelFamily
                                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.5)
                                font.weight: Font.Medium
                            }
                            Text {
                                Layout.alignment: Qt.AlignHCenter
                                // A date is an LTR technical token inside an Arabic
                                // card, the same rule the temperature follows.
                                text: "⁦" + cell.day.getDate() + "⁩"
                                color: cell.today ? Kirigami.Theme.highlightedTextColor
                                                  : Kirigami.Theme.textColor
                                font.family: "IBM Plex Sans"
                                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.95)
                                font.weight: cell.today ? Font.DemiBold : Font.Normal
                            }
                        }
                    }
                }
            }
        }

        Item { Layout.preferredHeight: Kirigami.Units.smallSpacing }

        // The same badge the clock face carries, so turning the card feels like
        // turning ONE object over rather than swapping in a different card.
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.round(Kirigami.Units.gridUnit * 1.45)
            radius: height / 2
            color: Qt.rgba(Kirigami.Theme.alternateBackgroundColor.r,
                           Kirigami.Theme.alternateBackgroundColor.g,
                           Kirigami.Theme.alternateBackgroundColor.b, 0.62)
            border.width: 1
            border.color: Qt.alpha(Kirigami.Theme.highlightColor, 0.22)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Kirigami.Units.largeSpacing
                anchors.rightMargin: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.smallSpacing

                Rectangle {
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 1.1
                    Layout.preferredHeight: 2
                    radius: 1
                    color: Kirigami.Theme.highlightColor
                }
                Text {
                    text: "MoOS"
                    color: Kirigami.Theme.textColor
                    font.family: "IBM Plex Sans"
                    font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.53)
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.4
                }
                Item { Layout.fillWidth: true }
                Text {
                    // The day of the year, because a week view is the one place a
                    // person asks "how far into the year are we".
                    text: strip.local("اليوم " + strip.dayOfYear + " من السنة",
                                      "DAY " + strip.dayOfYear + " OF THE YEAR")
                    color: Kirigami.Theme.disabledTextColor
                    font.family: strip.labelFamily
                    font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.49)
                    font.weight: Font.Medium
                    font.letterSpacing: strip.rtl ? 0 : 1.1
                }
            }
        }
    }
}
