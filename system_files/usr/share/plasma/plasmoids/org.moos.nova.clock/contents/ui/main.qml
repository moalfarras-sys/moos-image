// MoOS Nova Clock — panel time/date with a calendar popup.
//
// Two bugs lived in this file, and both were invisible to a syntax check.
//
// 1. Plasma 6 has no PlasmaCore.Theme. org.kde.plasma.core exposes Types;
//    colours come from Kirigami.Theme. The first version bound
//    `color: PlasmaCore.Theme.textColor` — undefined at runtime. The QML linter
//    catches it:  Member "Theme" not found on type "undefined" [missing-property]
//
// 2. A panel applet must declare Layout.minimumWidth/preferredWidth on its
//    compact representation. implicitWidth alone is NOT enough: Plasma lays the
//    panel out with those attached properties, and without them it allocated
//    this applet far less width than it paints. The next applet along was then
//    positioned inside the clock's own pixels — the system tray drew its icons
//    on top of the digits. Nothing errored; the panel just looked corrupted.
//    Upstream's org.kde.plasma.digitalclock sets all three. So do we.
//
// Run the QML linter over this file before shipping a change to it.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.workspace.calendar as PlasmaCalendar
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: compactRepresentation

    property date now: new Date()
    readonly property bool rtl: Qt.locale().textDirection === Qt.RightToLeft
    readonly property var displayLocale: rtl ? Qt.locale("ar") : Qt.locale()

    toolTipMainText: Qt.formatTime(now, displayLocale, Locale.LongFormat)
    toolTipSubText: Qt.formatDate(now, displayLocale, Locale.LongFormat)

    // Tick on the minute boundary, not at 1 Hz: nothing here displays seconds,
    // so a per-second timer was 59 needless wakeups a minute in a process that
    // never exits.
    Timer {
        interval: 60000 - (root.now.getSeconds() * 1000 + root.now.getMilliseconds())
        running: true
        repeat: true
        onTriggered: {
            root.now = new Date()
            interval = 60000 - (root.now.getSeconds() * 1000 + root.now.getMilliseconds())
        }
    }

    compactRepresentation: MouseArea {
        id: compact

        // The one number the panel layout actually reads. Everything else about
        // this applet's width is derived from it — see the header comment.
        readonly property int contentWidth: clockRow.implicitWidth + Kirigami.Units.largeSpacing * 2

        implicitWidth: contentWidth
        implicitHeight: Kirigami.Units.gridUnit * 2

        Layout.minimumWidth: contentWidth
        Layout.preferredWidth: contentWidth
        Layout.maximumWidth: contentWidth

        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.expanded = !root.expanded

        Accessible.name: root.toolTipMainText + ", " + root.toolTipSubText

        Rectangle {
            anchors.fill: parent
            radius: Kirigami.Units.cornerRadius
            color: Kirigami.Theme.textColor
            opacity: compact.containsMouse ? 0.10 : (root.expanded ? 0.07 : 0.0)
            Behavior on opacity { NumberAnimation { duration: 120 } }
        }

        // A turquoise hairline sweeps in under the time on hover — the same
        // accent the lock clock and the hero clock carry, sized from the row
        // so it works at any panel scale.
        Rectangle {
            anchors {
                bottom: parent.bottom
                bottomMargin: 3
                horizontalCenter: parent.horizontalCenter
            }
            width: compact.containsMouse ? clockRow.width : 0
            height: 2
            radius: 1
            color: Kirigami.Theme.highlightColor
            opacity: compact.containsMouse ? 0.9 : 0
            Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            Behavior on opacity { NumberAnimation { duration: 150 } }
        }

        RowLayout {
            id: clockRow
            anchors.centerIn: parent
            spacing: Math.round(Kirigami.Units.smallSpacing * 1.5)
            layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

            Text {
                text: Qt.formatTime(root.now, "HH:mm")
                color: Kirigami.Theme.textColor
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.max(12, Kirigami.Units.gridUnit * 0.78)
                font.weight: Font.DemiBold
                // The parentheses are load-bearing: `font.features: { "tnum": 1 }`
                // parses as a JS block, not an object literal, and silently yields
                // undefined. Tabular figures keep the clock from twitching as the
                // digits change width.
                font.features: ({ "tnum": 1 })
            }

            Rectangle {
                Layout.preferredWidth: 1
                Layout.preferredHeight: Math.round(Kirigami.Units.gridUnit * 0.8)
                Layout.alignment: Qt.AlignVCenter
                color: Kirigami.Theme.textColor
                opacity: 0.18
            }

            Text {
                text: Qt.formatDate(root.now, root.displayLocale, "ddd d MMM")
                color: Kirigami.Theme.textColor
                opacity: 0.66
                font.family: root.rtl ? "IBM Plex Sans Arabic" : "IBM Plex Sans"
                font.pixelSize: Math.max(9, Kirigami.Units.gridUnit * 0.58)
                font.weight: Font.Medium
            }
        }
    }

    // A finished popup, in the MoOS clock identity (matches the lock screen): a
    // large light-weight time, a bilingual Arabic/English date and one restrained
    // turquoise tick, above the month calendar — not a bare MonthView.
    fullRepresentation: Item {
        implicitWidth: Kirigami.Units.gridUnit * 22
        implicitHeight: Kirigami.Units.gridUnit * 24

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.largeSpacing

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Text {
                        text: Qt.formatTime(root.now, "HH:mm")
                        color: Kirigami.Theme.textColor
                        font.family: "IBM Plex Sans"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 2.6)
                        font.weight: Font.Light
                        font.features: ({ "tnum": 1 })
                    }
                    Text {
                        text: Qt.formatDate(root.now, Qt.locale("ar"), Qt.locale("ar").dateFormat(Locale.LongFormat))
                        color: Kirigami.Theme.textColor
                        opacity: 0.9
                        font.family: "IBM Plex Sans Arabic"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.95)
                    }
                    Text {
                        text: Qt.formatDate(root.now, Qt.locale("en"), "dddd, d MMMM yyyy")
                        color: Kirigami.Theme.textColor
                        opacity: 0.6
                        font.family: "IBM Plex Sans"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.72)
                    }
                }

                Rectangle {   // the one luminous accent, echoing the lock screen
                    Layout.alignment: Qt.AlignVCenter
                    Layout.preferredWidth: Math.max(3, Math.round(Kirigami.Units.smallSpacing * 0.7))
                    Layout.preferredHeight: Math.round(Kirigami.Units.gridUnit * 2.2)
                    radius: width
                    color: Kirigami.Theme.highlightColor
                    opacity: 0.9
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Kirigami.Theme.textColor
                opacity: 0.12
            }

            PlasmaCalendar.MonthView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                today: root.now
            }
        }
    }
}
