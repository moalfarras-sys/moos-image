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
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.workspace.calendar as PlasmaCalendar
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground

    property date now: new Date()
    readonly property bool rtl: MoUI.Locale.rtl
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property var design: MoUI.Tokens
    // MoOS shell chrome is bilingual. Following the host's unrelated regional
    // locale made an English desktop show German abbreviations ("Sa. 12 Sept.")
    // beside otherwise English controls. Keep this shell surface in the same
    // Arabic/English language as MoOS itself; the full calendar still exposes
    // regional date settings through its settings action.
    readonly property var displayLocale: rtl ? Qt.locale("ar") : Qt.locale("en_US")
    readonly property int motionFast: design.duration(
        root.motionEnabled, design.motionFast)
    readonly property int motionMedium: design.duration(
        root.motionEnabled, design.motionGeometry)
    readonly property real dayProgress: {
        const minutes = root.now.getHours() * 60 + root.now.getMinutes();
        return Math.max(0, Math.min(1, minutes / 1440));
    }
    readonly property string compactDate: {
        const pattern = root.rtl ? "ddd، d MMM" : "ddd · d MMM";
        const localized = root.latinNumerals(
            root.displayLocale.toString(root.now, pattern));
        return root.rtl ? localized : localized.toUpperCase();
    }

    // Same helper as the lock clock (MoOSClock.qml): day and month names stay
    // the locale's own, only the DIGITS fold to Latin — one number system on
    // every always-visible shell clock. Persian (U+06F0…) folds too.
    function latinNumerals(text) {
        let out = "";
        for (let i = 0; i < text.length; ++i) {
            const c = text.charCodeAt(i);
            if (c >= 0x0660 && c <= 0x0669) {
                out += String.fromCharCode(c - 0x0660 + 0x30);
            } else if (c >= 0x06F0 && c <= 0x06F9) {
                out += String.fromCharCode(c - 0x06F0 + 0x30);
            } else {
                out += text[i];
            }
        }
        return out;
    }

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

        // The outer Horizon Bar is the status area's one glass container. The
        // former clock-only capsule left tray icons visibly outside their own
        // group's surface. At rest this applet therefore adds no second box;
        // one accent rail and a compact two-line rhythm join tray and time.
        readonly property int contentWidth: statusRow.implicitWidth
            + Math.round(Kirigami.Units.largeSpacing * 1.5)

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
            anchors.topMargin: Kirigami.Units.smallSpacing
            anchors.bottomMargin: Kirigami.Units.smallSpacing
            radius: Math.round(height * 0.34)
            color: Qt.alpha(Kirigami.Theme.highlightColor,
                            compact.containsMouse ? 0.09
                            : root.expanded ? 0.055 : 0)
            border.width: root.design.borderHairline
            border.color: Qt.alpha(Kirigami.Theme.highlightColor,
                                   compact.containsMouse || root.expanded ? 0.22 : 0)
            scale: compact.containsMouse ? 1.01 : 1
            Behavior on color { ColorAnimation { duration: root.motionFast } }
            Behavior on border.color { ColorAnimation { duration: root.motionFast } }
            Behavior on scale {
                NumberAnimation {
                    duration: root.motionFast
                    easing.type: root.design.easeStandard
                }
            }
        }

        RowLayout {
            id: statusRow
            anchors.centerIn: parent
            spacing: Kirigami.Units.largeSpacing
            // Plasma mirrors the whole compact representation for RTL. Do not
            // mirror this row a second time.

            Rectangle {
                Layout.preferredWidth: Math.max(2, root.design.borderHairline * 2)
                Layout.preferredHeight: Math.round(Kirigami.Units.gridUnit * 1.38)
                Layout.alignment: Qt.AlignVCenter
                radius: width
                gradient: Gradient {
                    GradientStop { position: 0; color: Kirigami.Theme.highlightColor }
                    GradientStop {
                        position: 1
                        color: Qt.alpha(Kirigami.Theme.highlightColor, 0.24)
                    }
                }
                opacity: compact.containsMouse || root.expanded ? 1 : 0.78
                Behavior on opacity { NumberAnimation { duration: root.motionFast } }
            }

            ColumnLayout {
                id: clockColumn
                spacing: -Math.round(Kirigami.Units.smallSpacing * 0.45)

                Text {
                    id: timeLabel
                    Layout.alignment: Qt.AlignHCenter
                    text: Qt.formatTime(root.now, "HH:mm")
                    color: Kirigami.Theme.textColor
                    font.family: "IBM Plex Sans"
                    font.pixelSize: Math.max(13, Kirigami.Units.gridUnit * 0.82)
                    font.weight: Font.DemiBold
                    font.features: ({ "tnum": 1 })
                    transform: Translate { id: minuteShift }
                    onTextChanged: minuteTurn.restart()
                    SequentialAnimation {
                        id: minuteTurn
                        ParallelAnimation {
                            NumberAnimation {
                                target: minuteShift; property: "y"
                                from: -Math.round(Kirigami.Units.gridUnit * 0.30); to: 0
                                duration: root.motionMedium; easing.type: Easing.OutCubic
                            }
                            NumberAnimation {
                                target: timeLabel; property: "opacity"
                                from: 0.30; to: 1
                                duration: root.motionMedium; easing.type: Easing.OutCubic
                            }
                        }
                    }
                }

                Text {
                    id: dateLabel
                    Layout.alignment: Qt.AlignHCenter
                    text: root.compactDate
                    color: Kirigami.Theme.textColor
                    opacity: root.design.mutedOpacity
                    font.family: root.rtl ? "IBM Plex Sans Arabic" : "IBM Plex Sans"
                    font.pixelSize: Math.max(8, Kirigami.Units.gridUnit * 0.47)
                    font.weight: Font.Medium
                    font.letterSpacing: root.rtl ? 0 : 0.55
                }

                // A quiet day-progress line gives the status cluster one MoOS
                // signal without drawing another enclosing capsule. Keeping it
                // inside the column also keeps every anchor within its legal
                // parent/sibling scope when Plasma constructs the applet.
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(1, root.design.borderHairline)
                    Layout.topMargin: Math.round(Kirigami.Units.smallSpacing * 0.22)
                    radius: height
                    color: Qt.alpha(Kirigami.Theme.textColor, 0.09)

                    Rectangle {
                        width: parent.width * root.dayProgress
                        height: parent.height
                        radius: parent.radius
                        color: Kirigami.Theme.highlightColor
                        opacity: compact.containsMouse ? 0.92 : 0.58
                        Behavior on width {
                            NumberAnimation {
                                duration: root.motionMedium
                                easing.type: Easing.OutCubic
                            }
                        }
                        Behavior on opacity {
                            NumberAnimation { duration: root.motionFast }
                        }
                    }
                }
            }
        }
    }

    // Let PlasmoidItem choose the compact representation in the panel and this
    // full representation in a popup or standalone window. Forcing compact here
    // made plasmawindowed stretch the small panel chip across an entire window.
    fullRepresentation: Item {
        id: calendarPopup
        implicitWidth: Math.max(360, Kirigami.Units.gridUnit * 24)
        implicitHeight: Math.max(460, Kirigami.Units.gridUnit * 27)
        opacity: root.motionEnabled ? 0 : 1
        scale: root.motionEnabled ? 0.97 : 1
        transformOrigin: Item.Top

        // Plasma's MonthView resets its internal SwipeView index while its
        // width/height settles. In an RTL application, plasmawindowed exposed
        // an upstream ordering bug where those initial resizes advanced the
        // backend from September 2026 to October 2037 *after* an immediate
        // resetToToday(). Debounce the reset until geometry is stable. The
        // entrance animation covers the correction in a normal panel popup.
        Timer {
            id: calendarSettleTimer
            interval: Math.max(140, root.motionFast)
            repeat: false
            onTriggered: monthView.resetToToday()
        }
        onWidthChanged: calendarSettleTimer.restart()
        onHeightChanged: calendarSettleTimer.restart()

        function revealPopup() {
            if (!root.motionEnabled) {
                popupEntrance.stop();
                calendarPopup.opacity = 1;
                calendarPopup.scale = 1;
            } else if (root.expanded) {
                calendarPopup.opacity = 0;
                calendarPopup.scale = 0.97;
                popupEntrance.restart();
            }
        }
        Component.onCompleted: {
            // MonthView owns a separate displayed-date backend. Binding only
            // `today`/`currentDate` does not initialise that backend reliably
            // when plasmawindowed or the popup constructs it offscreen first;
            // live review exposed a September 2026 header over October 2037.
            // Match Plasma's digital-clock contract and explicitly reset it.
            monthView.resetToToday()
            calendarSettleTimer.restart()
            revealPopup()
        }
        Connections {
            target: root
            function onExpandedChanged() {
                monthView.resetToToday()
                calendarSettleTimer.restart()
                if (root.expanded) { calendarPopup.revealPopup(); }
            }
            function onMotionEnabledChanged() { calendarPopup.revealPopup(); }
        }
        ParallelAnimation {
            id: popupEntrance
            NumberAnimation {
                target: calendarPopup; property: "opacity"; from: 0; to: 1
                duration: root.motionMedium; easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: calendarPopup; property: "scale"; from: 0.97; to: 1
                duration: root.motionMedium; easing.type: root.design.easeEmphasis
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.largeSpacing

            MoUI.GlassSurface {
                id: dayHeader
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(
                    Kirigami.Units.gridUnit * 6,
                    headerContent.implicitHeight + Kirigami.Units.largeSpacing * 2)
                floating: true
                surfaceColor: Kirigami.Theme.backgroundColor
                accentColor: Kirigami.Theme.highlightColor
                selected: true
                rimOpacity: 0.34

                RowLayout {
                    id: headerContent
                    anchors {
                        fill: parent
                        margins: Kirigami.Units.largeSpacing
                    }
                    spacing: Kirigami.Units.largeSpacing
                    // Inherit the shell's logical direction; do not double-mirror.

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
                            Layout.fillWidth: true
                            text: root.latinNumerals(root.displayLocale.toString(
                                root.now, root.displayLocale.dateFormat(Locale.LongFormat)))
                            color: Kirigami.Theme.textColor
                            opacity: 0.88
                            font.family: root.rtl ? "IBM Plex Sans Arabic" : "IBM Plex Sans"
                            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.82)
                            elide: Text.ElideRight
                        }

                    }

                    ColumnLayout {
                        spacing: Kirigami.Units.smallSpacing

                        MoUI.IconButton {
                            symbol: "moos-calendar-symbolic"
                            accessibleLabel: root.rtl ? "العودة إلى اليوم" : qsTr("Return to today")
                            onClicked: monthView.resetToToday()

                            QQC2.ToolTip.visible: hovered
                            QQC2.ToolTip.text: accessibleLabel
                        }

                        MoUI.IconButton {
                            symbol: "moos-settings-symbolic"
                            accessibleLabel: root.rtl ? "إعدادات الوقت والتاريخ" : qsTr("Date and time settings")
                            onClicked: Qt.openUrlExternally("moos://settings/time")

                            QQC2.ToolTip.visible: hovered
                            QQC2.ToolTip.text: accessibleLabel
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: Math.max(
                            3, Math.round(Kirigami.Units.smallSpacing * 0.7))
                        Layout.fillHeight: true
                        Layout.maximumHeight: Math.round(Kirigami.Units.gridUnit * 4.1)
                        Layout.alignment: Qt.AlignVCenter
                        radius: width
                        color: Kirigami.Theme.highlightColor
                        opacity: 0.88
                    }
                }

                Rectangle {
                    anchors {
                        left: parent.left
                        right: parent.right
                        bottom: parent.bottom
                    }
                    height: Math.max(3, root.design.borderHairline * 3)
                    radius: height / 2
                    color: Qt.alpha(Kirigami.Theme.textColor, 0.10)

                    Rectangle {
                        width: parent.width * root.dayProgress
                        height: parent.height
                        radius: parent.radius
                        color: Kirigami.Theme.highlightColor
                    }
                }
            }

            MoUI.GlassSurface {
                Layout.fillWidth: true
                Layout.fillHeight: true
                floating: false
                surfaceColor: Kirigami.Theme.backgroundColor
                rimOpacity: root.design.glassBorderOpacity

                PlasmaCalendar.MonthView {
                    id: monthView
                    anchors {
                        fill: parent
                        margins: Kirigami.Units.largeSpacing
                    }
                    today: root.now
                    currentDate: root.now
                    showWeekNumbers: width >= Kirigami.Units.gridUnit * 22
                    borderWidth: root.design.borderHairline
                    borderOpacity: 0.20
                }
            }
        }
    }
}
