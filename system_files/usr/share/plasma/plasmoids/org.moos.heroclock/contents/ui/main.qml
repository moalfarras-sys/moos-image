// MoOS Hero Clock — the glass desktop clock.
//
// The owner asked for a first-party desktop widget that carries the brand:
// a large, light-weight time on a translucent glass card, the bilingual
// Arabic/English date, and the living MoOS mark with its comet-ring orbit in
// the corner — the same orbit the login, lock and logout scenes carry, so
// the desktop reads as one system.
//
// Rules inherited from org.moos.nova.clock and org.moos.brand (read their
// headers before editing):
// - Kirigami.Theme for colours, never PlasmaCore.Theme (does not exist).
// - The compact representation MUST set Layout.minimumWidth/preferredWidth or
//   the panel lays the next applet inside this one's pixels.
// - Motion is Animators/NumberAnimations only — no ShaderEffect, no
//   MultiEffect, no Lottie, no pkexec/sudo. This runs in plasmashell, forever.
// - The glow/ring/spark sprites are pre-baked by artwork/generate_login_scene.py
//   and MUST ship beside this file (the sprite gate checks).
// - Run the QML linter over this file before shipping a change.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    property date now: new Date()
    // The colon breathes at half-second phase; the seconds strip is live, so
    // the widget ticks at 1 Hz (the lock clock already does the same).
    property bool tick: true

    toolTipMainText: Qt.formatTime(now, Locale.LongFormat)
    toolTipSubText: Qt.formatDate(now, Locale.LongFormat)

    Timer {
        interval: 1000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: {
            const d = new Date();
            root.tick = d.getSeconds() % 2 === 0;
            root.now = d;
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

        // Glass: translucent fill via colour alpha (never item opacity — that
        // would dim the time and the emblem with it), hairline border, one
        // top highlight. The same glass language as the logout panel.
        Rectangle {
            id: card
            anchors.fill: parent
            radius: Kirigami.Units.gridUnit * 0.75
            color: Qt.alpha(Kirigami.Theme.backgroundColor, 0.58)
            border.width: 1
            border.color: Qt.alpha(Kirigami.Theme.textColor, 0.14)
        }
        Rectangle {
            anchors {
                top: card.top
                horizontalCenter: card.horizontalCenter
                topMargin: 1
            }
            width: card.width - Kirigami.Units.gridUnit * 1.5
            height: 1
            radius: 1
            color: Kirigami.Theme.textColor
            opacity: 0.12
        }

        // The living mark, lower right corner (mirrors for RTL via layout),
        // breathing behind its counter-rotating comet ring.
        Item {
            id: brandCorner
            width: Math.round(Math.min(hero.width, hero.height) * 0.36)
            height: width
            anchors {
                right: parent.right
                bottom: parent.bottom
                rightMargin: Kirigami.Units.largeSpacing * 2
                bottomMargin: Kirigami.Units.largeSpacing * 2
            }

            Image {
                anchors.centerIn: cornerEmblem
                width: cornerEmblem.width * 2.0
                height: width
                source: "../images/glow-cyan.png"
                opacity: 0.4
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    running: hero.visible
                    NumberAnimation { to: 0.65; duration: 3800; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.4; duration: 3800; easing.type: Easing.InOutSine }
                }
            }
            Image {
                id: cornerEmblem
                anchors.fill: parent
                source: "file:///usr/share/moos/moos-logo.png"
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                smooth: true
                sourceSize: Qt.size(width * 2, height * 2)
                SequentialAnimation on scale {
                    loops: Animation.Infinite
                    running: hero.visible
                    NumberAnimation { to: 1.04; duration: 3800; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 1.0; duration: 3800; easing.type: Easing.InOutSine }
                }
            }
            Image {
                anchors.centerIn: cornerEmblem
                width: cornerEmblem.width * 1.45
                height: width
                source: "../images/ring.png"
                mirror: true
                opacity: 0.6
                sourceSize: Qt.size(width * 2, height * 2)
                RotationAnimator on rotation {
                    from: 360; to: 0
                    duration: 24000
                    loops: Animation.Infinite
                    running: hero.visible
                }
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
                spacing: 0

                Text {
                    text: Qt.formatTime(root.now, "HH")
                    color: Kirigami.Theme.textColor
                    font.family: "IBM Plex Sans"
                    font.pixelSize: hero.timePx
                    font.weight: Font.Light
                    renderType: Text.NativeRendering
                }
                Text {
                    id: heroColon
                    text: ":"
                    color: Kirigami.Theme.highlightColor
                    font.family: "IBM Plex Sans"
                    font.pixelSize: hero.timePx
                    font.weight: Font.Light
                    renderType: Text.NativeRendering
                    opacity: root.tick ? 1.0 : 0.35
                    Behavior on opacity {
                        NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.InOutQuad }
                    }
                }
                Text {
                    text: Qt.formatTime(root.now, "mm")
                    color: Kirigami.Theme.textColor
                    font.family: "IBM Plex Sans"
                    font.pixelSize: hero.timePx
                    font.weight: Font.Light
                    renderType: Text.NativeRendering
                }
                Text {
                    text: Qt.formatTime(root.now, "ss")
                    color: Kirigami.Theme.highlightColor
                    leftPadding: Kirigami.Units.smallSpacing * 2
                    font.family: "IBM Plex Sans"
                    font.pixelSize: Math.round(hero.timePx * 0.40)
                    font.weight: Font.Normal
                    renderType: Text.NativeRendering
                    Layout.alignment: Qt.AlignBottom
                }
            }

            // The accent hairline with the gliding spark — the greeter's
            // glint, carried onto the desktop.
            Rectangle {
                id: heroHairline
                Layout.preferredWidth: Math.round(hero.width * 0.34)
                Layout.preferredHeight: 2
                radius: 1
                color: Kirigami.Theme.highlightColor
                opacity: 0.85

                Image {
                    id: heroSpark
                    source: "../images/spark.png"
                    width: 14
                    height: 14
                    y: Math.round((parent.height - height) / 2)
                    opacity: 0
                    SequentialAnimation {
                        running: hero.visible
                        loops: Animation.Infinite
                        PauseAnimation { duration: 5200 }
                        ParallelAnimation {
                            NumberAnimation { target: heroSpark; property: "x"
                                from: -heroSpark.width * 0.5
                                to: heroHairline.width - heroSpark.width * 0.5
                                duration: 1600; easing.type: Easing.InOutSine }
                            SequentialAnimation {
                                NumberAnimation { target: heroSpark; property: "opacity"
                                    to: 0.9; duration: 380; easing.type: Easing.OutCubic }
                                PauseAnimation { duration: 800 }
                                NumberAnimation { target: heroSpark; property: "opacity"
                                    to: 0; duration: 420; easing.type: Easing.InCubic }
                            }
                        }
                    }
                }
            }

            Text {
                text: Qt.formatDate(root.now, Qt.locale("ar"), Qt.locale("ar").dateFormat(Locale.LongFormat))
                color: Kirigami.Theme.textColor
                opacity: 0.9
                Layout.fillWidth: true
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignLeft
                font.family: "IBM Plex Sans Arabic"
                font.pixelSize: Math.round(hero.timePx * 0.30)
                renderType: Text.NativeRendering
            }
            Text {
                text: Qt.formatDate(root.now, Qt.locale("en"), "dddd, d MMMM yyyy")
                color: Kirigami.Theme.textColor
                opacity: 0.55
                Layout.fillWidth: true
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignLeft
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.round(hero.timePx * 0.24)
                renderType: Text.NativeRendering
            }
        }
    }
}
