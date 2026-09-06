// MoOS Hero Clock — the glass desktop clock.
//
// The owner asked for a first-party desktop widget that carries the brand:
// a large, light-weight time on a translucent glass card, one active-locale
// date, and the protected MoOS mark seated in Tidal Cut geometry.
//
// Rules inherited from org.moos.nova.clock and org.moos.brand (read their
// headers before editing):
// - Kirigami.Theme for colours, never PlasmaCore.Theme (does not exist).
// - The compact representation MUST set Layout.minimumWidth/preferredWidth or
//   the panel lays the next applet inside this one's pixels.
// - Motion is finite and meaningful: the minute change only. No ShaderEffect,
//   MultiEffect, Lottie or always-running loop in plasmashell.
// - Run the QML linter over this file before shipping a change.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

PlasmoidItem {
    id: root
    // Follow the session reading direction (matches org.moos.brand). Under an
    // Arabic (RTL) session the date lines below hug the reading edge, not left.
    readonly property bool rtl: MoUI.Locale.rtl

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    property date now: new Date()
    readonly property var design: MoUI.Tokens
    readonly property var displayLocale: rtl ? Qt.locale("ar") : Qt.locale()
    readonly property int motionMedium: design.duration(
        Kirigami.Units.longDuration > 1, design.motionGeometry)

    function local(arabic, english) {
        return root.rtl ? arabic : english;
    }

    // MoOS keeps clock and calendar numerals Latin in every locale while the
    // surrounding Arabic copy and reading order remain genuinely RTL.
    function latinNumerals(value) {
        return String(value)
            .replace(/[٠۰]/g, "0").replace(/[١۱]/g, "1")
            .replace(/[٢۲]/g, "2").replace(/[٣۳]/g, "3")
            .replace(/[٤۴]/g, "4").replace(/[٥۵]/g, "5")
            .replace(/[٦۶]/g, "6").replace(/[٧۷]/g, "7")
            .replace(/[٨۸]/g, "8").replace(/[٩۹]/g, "9");
    }

    toolTipMainText: Qt.formatTime(now, Locale.LongFormat)
    toolTipSubText: latinNumerals(Qt.formatDate(now, Locale.LongFormat))

    Timer {
        interval: 60000 - (root.now.getSeconds() * 1000 + root.now.getMilliseconds())
        repeat: true
        running: true
        onTriggered: {
            const d = new Date();
            root.now = d;
            interval = 60000 - (d.getSeconds() * 1000 + d.getMilliseconds());
        }
    }

    // ── Panel fallback: a plain readable time, the nova clock's contract ────
    compactRepresentation: MouseArea {
        id: compact

        readonly property int contentWidth: Math.round(compactTime.implicitWidth
                                                       + Kirigami.Units.smallSpacing * 2)

        implicitWidth: contentWidth
        implicitHeight: Kirigami.Units.gridUnit * 2

        Layout.minimumWidth: contentWidth
        Layout.preferredWidth: contentWidth

        onClicked: root.expanded = !root.expanded

        Text {
            id: compactTime
            anchors.centerIn: parent
            text: Qt.formatTime(root.now, "HH:mm")
            color: Kirigami.Theme.textColor
            font.family: "IBM Plex Sans"
            font.pixelSize: Math.round(compact.height * 0.55)
            font.weight: Font.Medium
            renderType: Text.NativeRendering
        }
    }

    // ── The hero card ────────────────────────────────────────────────────────
    fullRepresentation: Item {
        id: hero

        implicitWidth: Kirigami.Units.gridUnit * 17
        implicitHeight: Kirigami.Units.gridUnit * 8

        Layout.minimumWidth: Kirigami.Units.gridUnit * 12
        Layout.minimumHeight: Kirigami.Units.gridUnit * 6

        // Every size below derives from BOTH axes: the widget is freely
        // resizable on the desktop (and plasmawindowed hands it a square),
        // and a font sized off height alone overflows a narrow card — the
        // first windowed run pushed the seconds strip clean out of the
        // glass. Verified live at square and wide aspect.
        readonly property int timePx: Math.round(Math.min(height * 0.34, width * 0.165))

        // The first generation ran five perpetual animations and a one-second
        // timer on an always-visible desktop surface. Tidal Horizon treats calm
        // as a premium feature: the card wakes once per minute and animates only
        // that meaningful change.
        Rectangle {
            id: card
            anchors.fill: parent
            radius: root.design.radiusCard
            // Same capsule class as the media island, so the same derived
            // density: the two sit side by side on the bar and must never
            // disagree about how solid MoOS glass is.
            color: Qt.alpha(Kirigami.Theme.backgroundColor,
                            root.design.glassDensity(Kirigami.Theme.backgroundColor))
            border.width: root.design.borderHairline
            border.color: Qt.alpha(Kirigami.Theme.textColor, 0.16)
        }

        Rectangle {
            anchors {
                left: card.left
                right: card.right
                top: card.top
            }
            height: Math.round(card.height * 0.44)
            radius: card.radius
            gradient: Gradient {
                GradientStop {
                    position: 0
                    color: Qt.alpha(Kirigami.Theme.highlightColor, 0.18)
                }
                GradientStop {
                    position: 1
                    color: "transparent"
                }
            }
        }

        Row {
            anchors {
                left: card.left
                top: card.top
                leftMargin: card.radius
                topMargin: 1
            }
            height: 2
            spacing: Kirigami.Units.smallSpacing

            Rectangle {
                width: Math.round(hero.width * 0.26)
                height: 2
                radius: 1
                color: Kirigami.Theme.highlightColor
                opacity: 0.92
            }
            Rectangle {
                width: Kirigami.Units.smallSpacing
                height: 2
                radius: 1
                color: Kirigami.Theme.highlightColor
                opacity: 0.34
            }
        }

        // The protected MoOS mark sits inside a palette-native Tidal Cut plate.
        // Its geometry is untouched; only its seating changed.
        Item {
            id: brandCorner
            width: Math.round(Math.min(hero.width, hero.height) * 0.32)
            height: width
            anchors {
                right: parent.right
                verticalCenter: parent.verticalCenter
                rightMargin: Kirigami.Units.largeSpacing * 2
            }

            Rectangle {
                anchors.fill: parent
                radius: Math.round(width * 0.30)
                // Rim scale (THEME_REV 32): the emblem plate is told by its
                // fill; the edge is a hint. At 0.44 it drew a hard outline
                // around the mark on a surface that has no other borders.
                color: Qt.alpha(Kirigami.Theme.highlightColor, 0.12)
                border.width: root.design.borderHairline
                border.color: Qt.alpha(Kirigami.Theme.highlightColor, 0.22)
            }

            Image {
                id: cornerEmblem
                anchors.centerIn: parent
                width: Math.round(parent.width * 0.78)
                height: width
                source: "file:///usr/share/moos/moos-logo.png"
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                smooth: true
                sourceSize: Qt.size(width * 2, height * 2)
            }

            Rectangle {
                anchors {
                    right: parent.right
                    bottom: parent.bottom
                    rightMargin: Math.round(parent.width * 0.18)
                }
                width: parent.width * 0.30
                height: 2
                radius: 1
                color: Kirigami.Theme.highlightColor
                opacity: 0.82
            }
        }

        ColumnLayout {
            anchors {
                left: parent.left
                right: brandCorner.left
                verticalCenter: parent.verticalCenter
                leftMargin: Kirigami.Units.largeSpacing * 3
                rightMargin: Kirigami.Units.largeSpacing
            }
            spacing: Math.round(Kirigami.Units.smallSpacing * 1.2)

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                Rectangle {
                    Layout.preferredWidth: 7
                    Layout.preferredHeight: 7
                    radius: width / 2
                    color: Kirigami.Theme.positiveTextColor
                }
                Text {
                    Layout.fillWidth: true
                    text: root.local("التوقيت المحلي", "LOCAL TIME")
                    color: Kirigami.Theme.disabledTextColor
                    font.family: root.rtl ? "IBM Plex Sans Arabic" : "IBM Plex Sans"
                    font.pixelSize: Math.max(10, Math.round(hero.timePx * 0.20))
                    font.weight: Font.DemiBold
                    font.letterSpacing: root.rtl ? 0 : 1.2
                }
            }

            Text {
                id: minuteLabel
                text: Qt.formatTime(root.now, "HH:mm")
                color: Kirigami.Theme.textColor
                font.family: "IBM Plex Sans"
                font.pixelSize: hero.timePx
                font.weight: Font.Light
                font.features: ({ "tnum": 1 })
                renderType: Text.NativeRendering
                transform: Translate { id: minuteShift }

                onTextChanged: minutePulse.restart()
                ParallelAnimation {
                    id: minutePulse
                    NumberAnimation {
                        target: minuteShift
                        property: "y"
                        from: -Math.round(Kirigami.Units.gridUnit * 0.32)
                        to: 0
                        duration: root.motionMedium
                        easing.type: Easing.OutCubic
                    }
                    NumberAnimation {
                        target: minuteLabel
                        property: "opacity"
                        from: 0.35
                        to: 1
                        duration: root.motionMedium
                        easing.type: Easing.OutCubic
                    }
                }
            }

            Row {
                id: heroHairline
                Layout.preferredWidth: Math.round(hero.width * 0.38)
                Layout.preferredHeight: 2
                spacing: Kirigami.Units.smallSpacing

                Rectangle {
                    width: Math.round(heroHairline.width * 0.72)
                    height: 2
                    radius: 1
                    color: Kirigami.Theme.highlightColor
                    opacity: 0.90
                }
                Rectangle {
                    width: Math.round(heroHairline.width * 0.12)
                    height: 2
                    radius: 1
                    color: Kirigami.Theme.highlightColor
                    opacity: 0.34
                }
            }

            Text {
                text: root.latinNumerals(root.displayLocale.toString(root.now,
                    root.rtl ? "dddd، d MMMM yyyy" : "dddd · d MMMM yyyy"))
                color: Kirigami.Theme.textColor
                opacity: 0.9
                Layout.fillWidth: true
                elide: Text.ElideRight
                horizontalAlignment: root.rtl ? Text.AlignRight : Text.AlignLeft
                font.family: root.rtl ? "IBM Plex Sans Arabic" : "IBM Plex Sans"
                font.pixelSize: Math.round(hero.timePx * 0.30)
                renderType: Text.NativeRendering
            }
            Text {
                text: root.local("MoOS · أفقك اليومي", "MoOS · YOUR DAILY HORIZON")
                color: Kirigami.Theme.textColor
                opacity: 0.55
                Layout.fillWidth: true
                elide: Text.ElideRight
                horizontalAlignment: root.rtl ? Text.AlignRight : Text.AlignLeft
                font.family: root.rtl ? "IBM Plex Sans Arabic" : "IBM Plex Sans"
                font.pixelSize: Math.round(hero.timePx * 0.24)
                font.weight: Font.DemiBold
                font.letterSpacing: root.rtl ? 0 : 0.9
                renderType: Text.NativeRendering
            }
        }
    }
}
