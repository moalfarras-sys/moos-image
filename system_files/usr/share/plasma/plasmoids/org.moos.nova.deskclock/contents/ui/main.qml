// MoOS Nova Desk Clock — the large clock on the desktop.
//
// Separate from org.moos.nova.clock on purpose. That one is a PANEL applet: its
// compact representation is the dock's time, and its full representation is a
// calendar popup. On the desktop Plasma renders an applet's FULL representation,
// so putting the panel clock on the desktop would have produced a month grid,
// not a clock.
//
// MoOS is bilingual, so this shows the date twice — once in Arabic and once in
// the session locale (German on this hardware). Both lines come from QLocale, so
// neither is a hardcoded translation that goes stale.
//
// Colour comes from Kirigami.Theme, never PlasmaCore.Theme: PlasmaCore exposes
// Types only, and binding to a Theme that does not exist is how the panel clock
// spent its first revision drawing nothing at all.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    property date now: new Date()

    readonly property var arabicLocale: Qt.locale("ar")

    // Tick on the minute boundary. Nothing here shows seconds, so a 1 Hz timer
    // would be 59 wasted wakeups a minute for the life of the session.
    Timer {
        interval: 60000 - (root.now.getSeconds() * 1000 + root.now.getMilliseconds())
        running: true
        repeat: true
        onTriggered: {
            root.now = new Date()
            interval = 60000 - (root.now.getSeconds() * 1000 + root.now.getMilliseconds())
        }
    }

    fullRepresentation: Item {
        id: face

        implicitWidth: column.implicitWidth + Kirigami.Units.gridUnit * 2
        implicitHeight: column.implicitHeight + Kirigami.Units.gridUnit * 2

        Layout.minimumWidth: implicitWidth
        Layout.minimumHeight: implicitHeight

        // A desktop widget sits on the WALLPAPER, not on a themed surface, and a
        // wallpaper is whatever the user makes it. Kirigami.Theme.textColor alone
        // is therefore not enough: switch to the light theme and the clock turns
        // dark — on a dark wallpaper it simply vanishes, which is exactly what
        // happened the first time this was tried.
        //
        // The shadow is the fix. It is drawn in the INVERSE of the text colour, so
        // dark text carries a light halo and light text a dark one, and the clock
        // stays legible on any background either way.
        MultiEffect {
            anchors.fill: column
            source: column
            shadowEnabled: true
            shadowColor: Kirigami.Theme.textColor.hslLightness > 0.5
                         ? Qt.rgba(0, 0, 0, 0.55)
                         : Qt.rgba(1, 1, 1, 0.55)
            shadowBlur: 0.7
            shadowVerticalOffset: 0
            shadowHorizontalOffset: 0
            shadowOpacity: 0.9
        }

        ColumnLayout {
            id: column
            anchors.centerIn: parent
            spacing: Kirigami.Units.smallSpacing

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: Qt.formatTime(root.now, "HH:mm")
                color: Kirigami.Theme.textColor
                font.family: "IBM Plex Sans"
                font.pixelSize: Kirigami.Units.gridUnit * 5
                font.weight: Font.Light
                // Tabular figures: without them the whole clock shifts sideways
                // every time a 1 becomes a 2. Parentheses are load-bearing —
                // `font.features: { "tnum": 1 }` parses as a JS block and yields
                // undefined.
                font.features: ({ "tnum": 1 })
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root.arabicLocale.standaloneDayName(root.now.getDay(), Locale.LongFormat)
                      + "، " + Qt.formatDate(root.now, "d ")
                      + root.arabicLocale.standaloneMonthName(root.now.getMonth(), Locale.LongFormat)
                color: Kirigami.Theme.textColor
                opacity: 0.85
                font.family: "IBM Plex Sans Arabic"
                font.pixelSize: Kirigami.Units.gridUnit
                font.weight: Font.Medium
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: Qt.formatDate(root.now, Locale.LongFormat)
                color: Kirigami.Theme.textColor
                opacity: 0.55
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.85)
                font.weight: Font.Normal
            }
        }
    }
}
