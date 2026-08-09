// MoOS Media Island — one adaptive MPRIS surface in the Horizon Bar.
//
// This is a direct panel zone immediately after the MoOS launcher, not a second
// media service and not a tray icon. Plasma's Mpris2Model remains the single
// source of truth and chooses the active player, including browsers that expose
// MPRIS through Media Session. The applet is one pixel and transparent at idle,
// expands when a real player appears, and offers the same player in a compact
// bar surface and a detailed popup.
//
// Motion is contextual only: geometry follows media/hover state and the progress
// timer runs only while media is playing and somebody can see the position. No
// decorative timer or permanent compositor repaint loop is allowed here.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtCore
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PC3
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.mpris as Mpris
import org.moos.ui as MoUI

PlasmoidItem {
    id: root

    readonly property var design: MoUI.Tokens
    readonly property bool rtl: Qt.locale().textDirection === Qt.RightToLeft
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property int motionFast: design.duration(
        root.motionEnabled, design.motionFast)
    readonly property int motionGeometry: design.duration(
        root.motionEnabled, design.motionGeometry)

    function local(arabic, english) { return root.rtl ? arabic : english; }
    function bounded(value, low, high) {
        return Math.max(low, Math.min(high, value));
    }
    function twoDigits(value) {
        return value < 10 ? "0" + value : String(value);
    }
    function resolvedPlayerIcon() {
        if (!root.hasPlayer) { return "applications-multimedia-symbolic"; }
        if (root.desktopEntry.length > 0) { return root.desktopEntry; }

        // Browsers commonly publish Identity but omit DesktopEntry, while a
        // Flatpak artUrl can point into its private /tmp namespace. Resolve
        // only known identities to existing theme icons; never invent another
        // player registry or use the title as an executable/application id.
        const source = root.identity.toLowerCase();
        if (source.indexOf("chromium") >= 0) { return "chromium"; }
        if (source.indexOf("chrome") >= 0) { return "chrome"; }
        if (source.indexOf("firefox") >= 0) { return "firefox"; }
        if (source.indexOf("spotify") >= 0) { return "spotify"; }
        if (source.indexOf("vlc") >= 0) { return "vlc"; }
        if (source.indexOf("mpv") >= 0) { return "mpv"; }
        if (source.indexOf("moplayer") >= 0
                || source.indexOf("mo player") >= 0) {
            return "org.moos.moplayer";
        }
        const advertised = String(root.player.iconName || "");
        if (advertised.length > 0) { return advertised; }
        return "applications-multimedia-symbolic";
    }
    function resolvedArtworkSource() {
        const raw = root.artUrl;
        if (raw.indexOf("file:///tmp/.") !== 0) { return raw; }

        // Flatpak gives each app a private /tmp, but MPRIS publishes the URL as
        // if it were the host's /tmp. The same-user file is actually visible to
        // plasmashell below RuntimeLocation/.flatpak/<app-id>/tmp. Chromium's
        // Media Session uses .<reverse-dns-app-id>.<random-token> basenames, so
        // derive the namespace from that safe basename instead of maintaining
        // a second player/browser registry. Never carry a slash from MPRIS into
        // the translated path.
        const basename = raw.substring(raw.lastIndexOf("/") + 1);
        const match = basename.match(
            /^\.([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){1,})\.[A-Za-z0-9_-]+$/);
        if (!match) { return raw; }
        const runtimeUrl = String(StandardPaths.writableLocation(
            StandardPaths.RuntimeLocation));
        if (runtimeUrl.length < 1) { return raw; }
        const runtime = runtimeUrl.indexOf("file:") === 0
            ? runtimeUrl : "file://" + runtimeUrl;
        return runtime + "/.flatpak/" + match[1] + "/tmp/"
            + basename;
    }
    function formatTime(microseconds) {
        const total = Math.max(0, Math.floor(Number(microseconds || 0) / 1000000));
        const hours = Math.floor(total / 3600);
        const minutes = Math.floor((total % 3600) / 60);
        const seconds = total % 60;
        if (hours > 0) {
            return hours + ":" + root.twoDigits(minutes)
                + ":" + root.twoDigits(seconds);
        }
        return minutes + ":" + root.twoDigits(seconds);
    }
    function togglePlaying() {
        if (!root.player) { return; }
        if (root.playing && root.canPause) { root.player.Pause(); }
        else if (root.canPlay) { root.player.Play(); }
        else if (root.canControl) { root.player.PlayPause(); }
    }
    function seekTo(value) {
        if (root.player && root.canSeek) {
            root.player.position = Math.round(root.bounded(value, 0, root.length));
        }
    }
    function setVolume(value) {
        if (root.player && root.hasVolume) {
            root.player.volume = root.bounded(value, 0, 1.5);
        }
    }
    function toggleMuted() {
        if (!root.hasVolume) { return; }
        if (root.volume > 0.01) {
            root.lastAudibleVolume = root.volume;
            root.setVolume(0);
        } else {
            root.setVolume(Math.max(0.35, root.lastAudibleVolume));
        }
    }

    // Mpris2Model deliberately owns active-player selection. Building another
    // registry here would disagree with Plasma and break browser Media Session.
    Mpris.Mpris2Model { id: players }

    readonly property var player: players.currentPlayer
    readonly property bool hasPlayer: root.player !== null
                                      && root.player !== undefined
    readonly property string track: root.hasPlayer
        ? String(root.player.track || "") : ""
    readonly property string artist: root.hasPlayer
        ? String(root.player.artist || "") : ""
    readonly property string album: root.hasPlayer
        ? String(root.player.album || "") : ""
    readonly property string artUrl: root.hasPlayer
        ? String(root.player.artUrl || "") : ""
    // Host-installed Chromium-family browsers publish the SAME dot-prefixed
    // /tmp basenames as their Flatpak builds, but for them the raw URL is the
    // readable one and the translated .flatpak path does not exist. QML cannot
    // stat a path, so the bridge is probe-driven: try the translation first
    // (the live-proven Flatpak path); when that image errors, fall back to the
    // raw MPRIS URL for this artwork. New artwork re-arms the bridge, so a
    // Flatpak player after a native one still gets the translated path.
    property bool artworkBridgeFailed: false
    onArtUrlChanged: root.artworkBridgeFailed = false
    readonly property string artworkSource: root.artworkBridgeFailed
        ? root.artUrl : root.resolvedArtworkSource()
    readonly property string identity: root.hasPlayer
        ? String(root.player.identity || "") : ""
    readonly property string desktopEntry: root.hasPlayer
        ? String(root.player.desktopEntry || "") : ""
    readonly property string playerIcon: root.resolvedPlayerIcon()
    readonly property string displayTrack: root.track.length > 0
        ? root.track : root.local("وسائط قيد التشغيل", "Media playback")
    readonly property string displaySource: root.identity.length > 0
        ? root.identity : (root.artist.length > 0 ? root.artist
            : (root.desktopEntry.length > 0 ? root.desktopEntry
                : root.local("الوسائط", "Media")))

    readonly property int playbackStatus: root.hasPlayer
        ? root.player.playbackStatus : Mpris.PlaybackStatus.Stopped
    readonly property bool playing:
        root.playbackStatus === Mpris.PlaybackStatus.Playing
    readonly property bool paused:
        root.playbackStatus === Mpris.PlaybackStatus.Paused
    readonly property bool canControl: root.hasPlayer && root.player.canControl
    readonly property bool canPlay: root.hasPlayer && root.player.canPlay
    readonly property bool canPause: root.hasPlayer && root.player.canPause
    readonly property bool canGoPrevious:
        root.hasPlayer && root.player.canGoPrevious
    readonly property bool canGoNext: root.hasPlayer && root.player.canGoNext
    readonly property bool canSeek: root.hasPlayer && root.player.canSeek
    readonly property real length: root.hasPlayer
        ? Math.max(0, Number(root.player.length || 0)) : 0
    readonly property real position: root.hasPlayer
        ? root.bounded(Number(root.player.position || 0), 0, root.length) : 0
    readonly property bool hasTimeline: root.length > 0
    readonly property real progress: root.hasTimeline
        ? root.bounded(root.position / root.length, 0, 1) : 0
    readonly property real volume: root.hasPlayer
        ? Number(root.player.volume) : -1
    readonly property bool hasVolume: root.hasPlayer
        && isFinite(root.volume) && root.volume >= 0
    property real lastAudibleVolume: 0.65
    property bool compactHovered: false

    // Paused media remains useful. Stopped media gets a short release grace so
    // player hand-offs do not make the bar snap or flash at track boundaries.
    readonly property bool mediaPresent: root.hasPlayer
        && root.playbackStatus > Mpris.PlaybackStatus.Stopped
        && (root.track.length > 0 || root.identity.length > 0)
    readonly property bool active: root.mediaPresent || releaseGrace.running

    onMediaPresentChanged: {
        if (root.mediaPresent) { releaseGrace.stop(); }
        else { releaseGrace.restart(); }
    }
    onVolumeChanged: {
        if (root.volume > 0.01) { root.lastAudibleVolume = root.volume; }
    }
    onExpandedChanged: {
        if (root.expanded && root.player) { root.player.updatePosition(); }
    }

    Timer {
        id: releaseGrace
        interval: 1600
        repeat: false
    }

    // Some players publish position only on request. Wake once per second only
    // while progress is both moving and visible (popup open or capsule hovered).
    Timer {
        id: positionSync
        interval: 1000
        repeat: true
        running: root.playing && root.hasTimeline
                 && (root.expanded || root.compactHovered)
        onTriggered: if (root.player) { root.player.updatePosition(); }
    }

    Plasmoid.status: root.active
        ? PlasmaCore.Types.ActiveStatus
        : PlasmaCore.Types.PassiveStatus
    Plasmoid.icon: root.playerIcon
    toolTipMainText: root.active ? root.displayTrack
                                 : root.local("لا توجد وسائط", "No active media")
    toolTipSubText: root.active ? root.displaySource : ""
    toolTipTextFormat: Text.PlainText

    switchWidth: Kirigami.Units.gridUnit * 16
    switchHeight: Kirigami.Units.gridUnit * 11

    compactRepresentation: Item {
        id: compact

        readonly property real baseWidth: 218 + root.bounded(
            root.displayTrack.length * 1.65, 24, 88)
        implicitWidth: root.active
            ? Math.round(baseWidth + (compactHover.hovered ? 68 : 0)) : 1
        implicitHeight: root.design.panelHeight
        Layout.preferredWidth: implicitWidth
        Layout.minimumWidth: root.active ? 242 : 1
        Layout.maximumWidth: 374
        Layout.fillHeight: true
        opacity: root.active ? 1 : 0
        enabled: root.active
        visible: opacity > 0
        clip: true

        Behavior on implicitWidth {
            NumberAnimation {
                duration: root.motionGeometry
                easing.type: root.design.easeEmphasis
            }
        }
        Behavior on opacity {
            NumberAnimation {
                duration: root.motionFast
                easing.type: Easing.OutCubic
            }
        }

        HoverHandler {
            id: compactHover
            onHoveredChanged: root.compactHovered = hovered
        }

        Rectangle {
            id: compactShell
            anchors.fill: parent
            anchors.topMargin: root.design.space1
            anchors.bottomMargin: root.design.space1
            radius: height / 2
            color: Qt.alpha(Kirigami.Theme.backgroundColor,
                            root.design.isLight(Kirigami.Theme.backgroundColor)
                                ? 0.84 : 0.72)
            border.width: root.design.borderHairline
            border.color: Qt.alpha(Kirigami.Theme.textColor,
                                   compactHover.hovered ? 0.22 : 0.13)
            antialiasing: true

            Behavior on border.color {
                ColorAnimation { duration: root.motionFast }
            }

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                cursorShape: Qt.PointingHandCursor
                // Same press-time capture as the launcher's compact button: if
                // the expanded dialog dismissed itself on this press, release
                // must not read the post-dismiss state and re-open it.
                property bool wasExpanded: false
                onPressed: wasExpanded = root.expanded
                onClicked: mouse => {
                    if (mouse.button === Qt.MiddleButton) {
                        root.togglePlaying();
                    } else {
                        root.expanded = !wasExpanded;
                    }
                }
                onWheel: wheel => {
                    if (!root.player || !root.hasVolume) { return; }
                    root.player.changeVolume(wheel.angleDelta.y > 0 ? 0.05 : -0.05,
                                             true);
                }
                Accessible.role: Accessible.Button
                Accessible.name: root.displayTrack
                Accessible.description: root.displaySource
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: root.design.space1
                anchors.rightMargin: root.design.space2
                spacing: root.design.space2
                layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

                Rectangle {
                    Layout.preferredWidth: 38
                    Layout.preferredHeight: 38
                    radius: 19
                    color: Qt.alpha(Kirigami.Theme.highlightColor, 0.16)
                    clip: true

                    Image {
                        id: compactArt
                        anchors.fill: parent
                        source: root.artworkSource
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                        sourceSize.width: 96
                        visible: root.artworkSource.length > 0
                                 && status === Image.Ready
                        onStatusChanged: if (status === Image.Error
                                && root.artworkSource !== root.artUrl) {
                            root.artworkBridgeFailed = true;
                        }
                    }
                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: 22
                        height: 22
                        source: root.playerIcon
                        color: Kirigami.Theme.highlightColor
                        visible: !compactArt.visible
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 92
                    spacing: 0

                    PC3.Label {
                        Layout.fillWidth: true
                        text: root.displayTrack
                        color: Kirigami.Theme.textColor
                        font.pixelSize: root.design.typeSecondary
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        horizontalAlignment: root.rtl ? Text.AlignRight
                                                      : Text.AlignLeft
                    }
                    PC3.Label {
                        Layout.fillWidth: true
                        text: root.displaySource
                        color: Kirigami.Theme.disabledTextColor
                        font.pixelSize: root.design.typeCaption
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        horizontalAlignment: root.rtl ? Text.AlignRight
                                                      : Text.AlignLeft
                    }
                }

                PC3.ToolButton {
                    visible: compactHover.hovered && root.canGoPrevious
                    enabled: root.canGoPrevious
                    icon.name: root.rtl ? "media-skip-forward-symbolic"
                                        : "media-skip-backward-symbolic"
                    display: PC3.AbstractButton.IconOnly
                    Accessible.name: root.local("السابق", "Previous")
                    onClicked: root.player.Previous()
                }

                PC3.ToolButton {
                    enabled: root.playing ? root.canPause
                                          : (root.canPlay || root.canControl)
                    icon.name: root.playing ? "media-playback-pause-symbolic"
                                            : "media-playback-start-symbolic"
                    display: PC3.AbstractButton.IconOnly
                    Accessible.name: root.playing
                        ? root.local("إيقاف مؤقت", "Pause")
                        : root.local("تشغيل", "Play")
                    onClicked: root.togglePlaying()
                }

                PC3.ToolButton {
                    visible: compactHover.hovered && root.canGoNext
                    enabled: root.canGoNext
                    icon.name: root.rtl ? "media-skip-backward-symbolic"
                                        : "media-skip-forward-symbolic"
                    display: PC3.AbstractButton.IconOnly
                    Accessible.name: root.local("التالي", "Next")
                    onClicked: root.player.Next()
                }

                PC3.ToolButton {
                    visible: compactHover.hovered && root.hasVolume
                    enabled: root.hasVolume
                    icon.name: root.volume <= 0.01
                        ? "audio-volume-muted-symbolic"
                        : "audio-volume-high-symbolic"
                    display: PC3.AbstractButton.IconOnly
                    Accessible.name: root.volume <= 0.01
                        ? root.local("إلغاء الكتم", "Unmute")
                        : root.local("كتم", "Mute")
                    onClicked: root.toggleMuted()
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                width: parent.width * root.progress
                height: 2
                radius: 1
                visible: root.hasTimeline
                color: Kirigami.Theme.highlightColor
                opacity: 0.9
            }
        }
    }

    fullRepresentation: Item {
        id: expanded

        Layout.preferredWidth: Kirigami.Units.gridUnit * 21
        Layout.preferredHeight: Kirigami.Units.gridUnit * 17
        Layout.minimumWidth: Kirigami.Units.gridUnit * 18
        Layout.minimumHeight: Kirigami.Units.gridUnit * 15

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.design.space5
            spacing: root.design.space4
            layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

            RowLayout {
                Layout.fillWidth: true
                spacing: root.design.space4

                Rectangle {
                    Layout.preferredWidth: 104
                    Layout.preferredHeight: 104
                    radius: root.design.radiusCard
                    color: Qt.alpha(Kirigami.Theme.highlightColor, 0.14)
                    clip: true

                    Image {
                        id: expandedArt
                        anchors.fill: parent
                        source: root.artworkSource
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                        sourceSize.width: 256
                        visible: root.artworkSource.length > 0
                                 && status === Image.Ready
                        onStatusChanged: if (status === Image.Error
                                && root.artworkSource !== root.artUrl) {
                            root.artworkBridgeFailed = true;
                        }
                    }
                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: 46
                        height: 46
                        source: root.playerIcon
                        color: Kirigami.Theme.highlightColor
                        visible: !expandedArt.visible
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: root.design.space1

                    Rectangle {
                        Layout.preferredWidth: Math.min(184,
                            sourceLabel.implicitWidth + root.design.space3)
                        Layout.preferredHeight: 24
                        radius: 12
                        color: Qt.alpha(Kirigami.Theme.highlightColor, 0.14)

                        PC3.Label {
                            id: sourceLabel
                            anchors.centerIn: parent
                            width: Math.min(168, implicitWidth)
                            text: root.displaySource
                            color: Kirigami.Theme.highlightColor
                            font.pixelSize: root.design.typeCaption
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }
                    }
                    PlasmaExtras.Heading {
                        Layout.fillWidth: true
                        text: root.displayTrack
                        level: 3
                        maximumLineCount: 2
                        wrapMode: Text.Wrap
                        elide: Text.ElideRight
                        horizontalAlignment: root.rtl ? Text.AlignRight
                                                      : Text.AlignLeft
                    }
                    PC3.Label {
                        Layout.fillWidth: true
                        text: [root.artist, root.album].filter(
                            value => value.length > 0).join(" · ")
                        visible: text.length > 0
                        color: Kirigami.Theme.disabledTextColor
                        maximumLineCount: 1
                        elide: Text.ElideRight
                        horizontalAlignment: root.rtl ? Text.AlignRight
                                                      : Text.AlignLeft
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                visible: root.hasTimeline
                spacing: root.design.space1

                PC3.Slider {
                    id: seekSlider
                    Layout.fillWidth: true
                    from: 0
                    to: Math.max(1, root.length)
                    value: root.position
                    enabled: root.canSeek
                    stepSize: 5000000
                    Accessible.name: root.local("موضع التشغيل", "Playback position")
                    Accessible.onIncreaseAction:
                        root.seekTo(root.position + seekSlider.stepSize)
                    Accessible.onDecreaseAction:
                        root.seekTo(root.position - seekSlider.stepSize)
                    onMoved: seekCommit.restart()
                    onPressedChanged: if (!pressed) { root.seekTo(value); }

                    Timer {
                        id: seekCommit
                        interval: 90
                        repeat: false
                        onTriggered: root.seekTo(seekSlider.value)
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label {
                        text: root.formatTime(seekSlider.value)
                        color: Kirigami.Theme.disabledTextColor
                        font.pixelSize: root.design.typeCaption
                        font.features: ({ "tnum": 1 })
                    }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        text: root.formatTime(root.length)
                        color: Kirigami.Theme.disabledTextColor
                        font.pixelSize: root.design.typeCaption
                        font.features: ({ "tnum": 1 })
                    }
                }
            }

            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: root.design.space3

                PC3.ToolButton {
                    enabled: root.canGoPrevious
                    icon.name: root.rtl ? "media-skip-forward-symbolic"
                                        : "media-skip-backward-symbolic"
                    display: PC3.AbstractButton.IconOnly
                    Accessible.name: root.local("السابق", "Previous")
                    onClicked: root.player.Previous()
                }
                PC3.ToolButton {
                    Layout.preferredWidth: 52
                    Layout.preferredHeight: 52
                    enabled: root.playing ? root.canPause
                                          : (root.canPlay || root.canControl)
                    icon.name: root.playing ? "media-playback-pause-symbolic"
                                            : "media-playback-start-symbolic"
                    display: PC3.AbstractButton.IconOnly
                    Accessible.name: root.playing
                        ? root.local("إيقاف مؤقت", "Pause")
                        : root.local("تشغيل", "Play")
                    onClicked: root.togglePlaying()
                }
                PC3.ToolButton {
                    enabled: root.canGoNext
                    icon.name: root.rtl ? "media-skip-backward-symbolic"
                                        : "media-skip-forward-symbolic"
                    display: PC3.AbstractButton.IconOnly
                    Accessible.name: root.local("التالي", "Next")
                    onClicked: root.player.Next()
                }
            }

            RowLayout {
                Layout.fillWidth: true
                visible: root.hasVolume
                spacing: root.design.space2

                PC3.ToolButton {
                    icon.name: root.volume <= 0.01
                        ? "audio-volume-muted-symbolic"
                        : "audio-volume-high-symbolic"
                    display: PC3.AbstractButton.IconOnly
                    Accessible.name: root.volume <= 0.01
                        ? root.local("إلغاء الكتم", "Unmute")
                        : root.local("كتم", "Mute")
                    onClicked: root.toggleMuted()
                }
                PC3.Slider {
                    id: volumeSlider
                    Layout.fillWidth: true
                    from: 0
                    to: 1
                    value: root.bounded(root.volume, 0, 1)
                    Accessible.name: root.local("مستوى الصوت", "Volume")
                    // Clamp to the slider's own 0..1 range: root.volume is the
                    // raw player value and setVolume's 1.5 headroom exists for
                    // mute-restore, so unclamped +0.05 steps could push a
                    // player to 150% while this slider reads 100%.
                    Accessible.onIncreaseAction:
                        root.setVolume(root.bounded(root.volume + 0.05, 0, 1))
                    Accessible.onDecreaseAction:
                        root.setVolume(root.bounded(root.volume - 0.05, 0, 1))
                    onMoved: volumeCommit.restart()
                    onPressedChanged: if (!pressed) { root.setVolume(value); }

                    Timer {
                        id: volumeCommit
                        interval: 60
                        repeat: false
                        onTriggered: root.setVolume(volumeSlider.value)
                    }
                }
                PC3.Label {
                    Layout.preferredWidth: 42
                    horizontalAlignment: Text.AlignRight
                    text: Math.round(root.bounded(volumeSlider.value, 0, 1) * 100)
                          + "%"
                    font.pixelSize: root.design.typeCaption
                    font.features: ({ "tnum": 1 })
                }
            }
        }
    }
}
