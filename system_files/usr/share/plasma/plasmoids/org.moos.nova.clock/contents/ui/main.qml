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

        // The clock is a CHIP, not loose text. The dock now carries the launcher
        // as a chip at one end; giving the clock the same quiet glass at the
        // other end is what makes the dock read as one designed object instead
        // of a bar with things dropped on it. Faint at rest on purpose — this
        // sits over live wallpaper all day and must never shout.
        Rectangle {
            id: chip
            anchors.fill: parent
            anchors.topMargin: Kirigami.Units.smallSpacing
            anchors.bottomMargin: Kirigami.Units.smallSpacing
            radius: height / 2

            // The glass is an ALPHA on the colour, never `opacity`. Item opacity
            // multiplies onto children, so a 0.05 chip took the lit hairline
            // below down to 0.05 x 0.25 and it never appeared on screen at all.
            readonly property real glass: compact.containsMouse ? 0.13
                                        : (root.expanded ? 0.10 : 0.05)
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                           Kirigami.Theme.textColor.b, glass)
            Behavior on color { ColorAnimation { duration: 140 } }

            // One hairline along the top edge, lit like the dock's own rim, so
            // the chip is made of the same material as the panel under it.
            Rectangle {
                anchors { left: parent.left; right: parent.right; top: parent.top }
                anchors.leftMargin: parent.radius * 0.6
                anchors.rightMargin: parent.radius * 0.6
                height: 1
                color: Kirigami.Theme.highlightColor
                opacity: compact.containsMouse ? 0.60 : 0.30
                Behavior on opacity { NumberAnimation { duration: 140 } }
            }
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
                id: timeLabel
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

                // The minute turns over with a short rise, so the one moment
                // this applet has anything to say is the one moment it moves.
                // It rides a Translate rather than y/anchors: the layout must not
                // see the applet change height mid-animation, or the whole dock
                // relayouts sixty times an hour.
                transform: Translate { id: minuteShift }
                onTextChanged: minuteTurn.restart()
                SequentialAnimation {
                    id: minuteTurn
                    ParallelAnimation {
                        NumberAnimation {
                            target: minuteShift; property: "y"
                            from: -Math.round(Kirigami.Units.gridUnit * 0.35); to: 0
                            duration: 340; easing.type: Easing.OutCubic
                        }
                        NumberAnimation {
                            target: timeLabel; property: "opacity"
                            from: 0.25; to: 1.0
                            duration: 300; easing.type: Easing.OutCubic
                        }
                    }
                }
            }

            // The divider carries the accent instead of grey text: it is the one
            // pixel of MoOS turquoise at this end of the dock, answering the lit
            // rim above it and the launcher chip opposite.
            Rectangle {
                Layout.preferredWidth: 2
                Layout.preferredHeight: Math.round(Kirigami.Units.gridUnit * 0.72)
                Layout.alignment: Qt.AlignVCenter
                radius: width / 2
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Kirigami.Theme.highlightColor }
                    GradientStop { position: 1.0; color: Kirigami.Theme.textColor }
                }
                opacity: compact.containsMouse ? 0.75 : 0.45
                Behavior on opacity { NumberAnimation { duration: 140 } }
            }

            Text {
                // `Qt.formatDate(date, locale, "ddd d MMM")` does NOT accept a
                // format STRING in its three-argument form — that overload wants
                // a Locale.FormatType, so the pattern was discarded and the dock
                // silently rendered the full long date ("الاثنين، ٢٧ يوليو ٢٠٢٦"),
                // stretching the clock across the end of the panel. Locale.toString
                // is the call that honours a pattern, and it still uses the
                // locale's own day and month names. Same call the lock clock makes.
                text: root.displayLocale.toString(root.now, "ddd d MMM")
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
