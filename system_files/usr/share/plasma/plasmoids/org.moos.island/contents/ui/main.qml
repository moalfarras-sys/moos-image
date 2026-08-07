// MoOS Context Island — the bar's answer to "what is this machine doing?"
//
// moos-bar.conf reserved a [smart] slot for this from the start and it was never
// built. This is it: the tray shows a mark only while something is happening,
// and the whole card is one click away.
//
// TWO THINGS WERE LEARNED THE HARD WAY BUILDING THIS, both measured live:
//
//  1. It cannot be a plain panel applet that collapses to zero width. Plasma
//     does not instantiate a representation for a zero-width applet, and the
//     width was computed from that representation's own content — so the
//     content that would give it width never existed and it stayed zero
//     forever. The compact representation's Component.onCompleted never fired
//     once. Plasma already ships the mechanism for "appear when you have
//     something to say": X-Plasma-NotificationArea + Plasmoid.status, which is
//     what org.kde.kdeconnect and org.kde.plasma.vault use on disk today.
//     ActiveStatus puts the item in the tray's visible row; PassiveStatus tucks
//     it behind the arrow. Reusing the shell's own mechanism also means the
//     island obeys the user's tray settings like every other item.
//
//  2. A tray cell is SQUARE. The first tray version drew a wide chip with title
//     and artist and rendered blank: the row overflowed the cell and was
//     clipped, leaving a gap in the tray with nothing in it. So the tray mark is
//     an icon — the shape a tray is for — and the title, artist and transport
//     live in the popup, where there is room for them.
//
// THE SIGNAL IS REAL. org.kde.plasma.private.mpris is the same Mpris2Model
// Plasma's own media applet uses; title, artist and transport come from the
// player over MPRIS2, event-driven, no polling and no timers. A player that is
// stopped, or that has published no title, is not a state worth a mark — there
// is deliberately no placeholder, because a mark that cannot be trusted is
// worse than an empty tray.
//
// Motion budget: opacity only, and only while something is actually playing.
// It sits behind the Kirigami seam the rest of MoOS uses (longDuration > 1), so
// "animations off" is honoured — and since THEME_REV 34 that duration is scaled
// by moos-visual-tier, so the island's motion tracks the machine's capability
// without knowing anything about the hardware.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.mpris as Mpris

PlasmoidItem {
    id: root

    readonly property bool rtl: Qt.locale().textDirection === Qt.RightToLeft
    readonly property int motionFast: Kirigami.Units.longDuration > 1
        ? Kirigami.Units.shortDuration : 0
    readonly property int motionMedium: Kirigami.Units.longDuration > 1
        ? Kirigami.Units.longDuration : 0

    function local(arabic, english) { return root.rtl ? arabic : english; }

    // ---- the source --------------------------------------------------------

    Mpris.Mpris2Model { id: players }

    readonly property var player: players.currentPlayer
    readonly property string track: root.player ? String(root.player.track || "") : ""
    readonly property string artist: root.player ? String(root.player.artist || "") : ""
    readonly property string artUrl: root.player ? String(root.player.artUrl || "") : ""
    readonly property bool playing: root.player !== null
        && root.player.playbackStatus === Mpris.PlaybackStatus.Playing
    readonly property bool paused: root.player !== null
        && root.player.playbackStatus === Mpris.PlaybackStatus.Paused

    readonly property bool active: root.track.length > 0
        && (root.playing || root.paused)

    // THE MECHANISM. Active = in the tray's visible row. Passive = behind the
    // arrow, costing nothing and bothering no one.
    Plasmoid.status: root.active
        ? PlasmaCore.Types.ActiveStatus
        : PlasmaCore.Types.PassiveStatus

    toolTipMainText: root.track
    toolTipSubText: root.artist

    // ---- the tray mark -----------------------------------------------------
    compactRepresentation: MouseArea {
        id: mark

        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        Accessible.name: root.track
        Accessible.description: root.artist
        Accessible.role: Accessible.Button

        // Left opens the card; middle skips, the way every media tray does.
        onClicked: mouse => {
            if (mouse.button === Qt.MiddleButton) {
                if (root.player) { root.player.Next(); }
            } else {
                root.expanded = !root.expanded;
            }
        }
        onWheel: wheel => {
            if (!root.player) { return; }
            if (wheel.angleDelta.y > 0) { root.player.Next(); }
            else { root.player.Previous(); }
        }

        Kirigami.Icon {
            id: glyph
            anchors.centerIn: parent
            width: Math.round(Math.min(mark.width, mark.height) * 0.82)
            height: width
            source: root.playing ? "media-playback-start-symbolic"
                                 : "media-playback-pause-symbolic"
            color: Kirigami.Theme.highlightColor
            scale: mark.containsMouse ? 1.12 : 1.0
            Behavior on scale {
                NumberAnimation { duration: root.motionFast; easing.type: Easing.OutBack }
            }

            // The one piece of life: it breathes only while something is
            // actually playing, and only when motion is on at all. The gate is
            // named in full here rather than through root.motionMedium — an
            // endless loop must show its own guard, to the reader and to
            // verify_user_experience, which refuses an alias it cannot follow.
            SequentialAnimation on opacity {
                running: root.playing && Kirigami.Units.longDuration > 1
                loops: Animation.Infinite
                alwaysRunToEnd: true
                NumberAnimation { from: 1.0; to: 0.5; duration: 1500; easing.type: Easing.InOutSine }
                NumberAnimation { from: 0.5; to: 1.0; duration: 1500; easing.type: Easing.InOutSine }
            }
        }
    }

    // ---- the card ----------------------------------------------------------
    fullRepresentation: Item {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 18
        Layout.preferredHeight: Kirigami.Units.gridUnit * 9
        Layout.minimumWidth: Kirigami.Units.gridUnit * 14
        Layout.minimumHeight: Kirigami.Units.gridUnit * 8

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.largeSpacing

            RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Layout.fillWidth: true

                Rectangle {
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 5
                    Layout.preferredHeight: Layout.preferredWidth
                    radius: Kirigami.Units.gridUnit * 0.7
                    color: Qt.alpha(Kirigami.Theme.highlightColor, 0.12)
                    clip: true

                    Image {
                        anchors.fill: parent
                        source: root.artUrl
                        visible: root.artUrl.length > 0 && status === Image.Ready
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize.width: 256
                    }
                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: parent.width * 0.5
                        height: width
                        source: "media-playback-start-symbolic"
                        color: Kirigami.Theme.highlightColor
                        visible: root.artUrl.length === 0
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaExtras.Heading {
                        text: root.track
                        level: 4
                        elide: Text.ElideRight
                        maximumLineCount: 2
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                    PlasmaComponents.Label {
                        text: root.artist
                        visible: text.length > 0
                        opacity: 0.7
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        Layout.fillWidth: true
                    }
                }
            }

            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: Kirigami.Units.largeSpacing

                PlasmaComponents.ToolButton {
                    icon.name: "media-skip-backward-symbolic"
                    display: PlasmaComponents.AbstractButton.IconOnly
                    Accessible.name: root.local("السابق", "Previous")
                    onClicked: if (root.player) { root.player.Previous(); }
                }
                PlasmaComponents.ToolButton {
                    icon.name: root.playing ? "media-playback-pause-symbolic"
                                            : "media-playback-start-symbolic"
                    display: PlasmaComponents.AbstractButton.IconOnly
                    Accessible.name: root.playing ? root.local("إيقاف مؤقت", "Pause")
                                                  : root.local("تشغيل", "Play")
                    onClicked: if (root.player) { root.player.PlayPause(); }
                }
                PlasmaComponents.ToolButton {
                    icon.name: "media-skip-forward-symbolic"
                    display: PlasmaComponents.AbstractButton.IconOnly
                    Accessible.name: root.local("التالي", "Next")
                    onClicked: if (root.player) { root.player.Next(); }
                }
            }
        }
    }
}
