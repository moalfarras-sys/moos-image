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

    toolTipMainText: Qt.formatTime(now, Locale.LongFormat)
    toolTipSubText: Qt.formatDate(now, Locale.LongFormat)

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
                text: Qt.formatDate(root.now, "ddd d MMM")
                color: Kirigami.Theme.textColor
                opacity: 0.66
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.max(9, Kirigami.Units.gridUnit * 0.58)
                font.weight: Font.Medium
            }
        }
    }

    fullRepresentation: Item {
        implicitWidth: Kirigami.Units.gridUnit * 22
        implicitHeight: Kirigami.Units.gridUnit * 20

        PlasmaCalendar.MonthView {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing
            today: root.now
        }
    }
}
