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
import QtQuick.Window
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

    // Decode rasters for the DEVICE, not for logical pixels. A sourceSize is a
    // hard cap on the decoded image, so a fixed number silently under-samples
    // every HiDPI screen: on the reference 4K panel Qt reports
    // devicePixelRatio 3, where the 38 px avatar needs 114 real pixels and the
    // 104 px expanded cover needs 312 — the old fixed 96 and 256 are why album
    // art looked soft there while the text beside it stayed sharp. One owner
    // for the arithmetic so no surface can drift back to a magic number.
    readonly property real pixelRatio: Math.max(1, Screen.devicePixelRatio)
    function decodePx(logical) {
        return Math.ceil(Math.max(1, logical) * root.pixelRatio);
    }

    // A control that OPENS with the capsule instead of appearing inside it.
    //
    // These were plain `visible: hovered` buttons. visible flips at frame 0
    // while the capsule is still widening over motionGeometry, so all three
    // icons took their full layout width instantly, crushed the title beside
    // them, and then the text sprang back as the space caught up — the capsule
    // moved smoothly and its contents jumped. Giving the slot the SAME clock
    // and easing as the capsule's own implicitWidth makes the two read as one
    // movement: the capsule opens and the controls travel out of its edge.
    // Width carries the layout, opacity carries the ink slightly faster so the
    // icons are legible before they finish arriving, and visible follows the
    // width so a closed control costs no layout space at rest.
    // ONE control, designed — not a bare Plasma ToolButton dropped into glass.
    //
    // The transport used PC3.ToolButton with display:IconOnly, which inherits
    // the panel's own metrics: the icons came out around 28 px beside 14 px
    // type, sat on no surface at all, and each carried the widget style's
    // generic hover. Against a Liquid Glass capsule that reads as leftover
    // system parts, not as part of the product. This gives every control the
    // same geometry (a 30 px circular target with a 16 px glyph), the same
    // resting transparency, and the same glass fill on hover/press, so the
    // whole cluster keeps one rhythm and one language.
    //
    // The reveal is folded in here rather than wrapped around it: width and
    // ink travel on the capsule's own clock and easing, so the capsule and its
    // controls are a single movement, and a hidden control costs no layout
    // space at rest. Anchored to the edge the capsule grows from (RTL-aware)
    // so the glyph slides out of the rim instead of being squeezed.
    component MediaControl: Item {
        id: control
        property alias iconName: controlIcon.source
        property bool revealed: true
        property bool controlEnabled: true
        property string label: ""
        // The one action the surface exists for gets a filled plate and more
        // room; everything else stays a ghost. The expanded popup used to give
        // play/pause, previous and next the same bare glyph at the same
        // weight, so nothing said which one was the point.
        property bool primary: false
        property real slotSize: control.primary ? 52 : 30
        signal activated

        readonly property real glyphSize: Math.round(control.slotSize * 0.5)

        Layout.preferredWidth: control.revealed ? control.slotSize : 0
        Layout.preferredHeight: control.slotSize
        Layout.alignment: Qt.AlignVCenter
        clip: true
        opacity: control.revealed ? (control.controlEnabled ? 1 : 0.35) : 0
        visible: Layout.preferredWidth > 0.5
        enabled: control.controlEnabled

        Behavior on Layout.preferredWidth {
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

        Item {
            width: control.slotSize
            height: control.slotSize
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: root.rtl ? undefined : parent.right
            anchors.left: root.rtl ? parent.left : undefined

            Rectangle {
                id: controlPlate
                anchors.fill: parent
                radius: width / 2
                color: control.primary
                    ? Qt.alpha(Kirigami.Theme.highlightColor,
                               controlTap.pressed ? 1.0
                                   : (controlHover.hovered ? 0.92 : 0.82))
                    : Qt.alpha(Kirigami.Theme.textColor,
                               controlTap.pressed ? 0.18
                                   : (controlHover.hovered ? 0.10 : 0.0))
                Behavior on color {
                    ColorAnimation { duration: root.motionFast }
                }
            }

            Kirigami.Icon {
                id: controlIcon
                anchors.centerIn: parent
                width: control.glyphSize
                height: control.glyphSize
                color: control.primary ? Kirigami.Theme.highlightedTextColor
                                       : Kirigami.Theme.textColor
                scale: controlTap.pressed ? 0.86 : 1.0
                Behavior on scale {
                    NumberAnimation {
                        duration: root.motionFast
                        easing.type: Easing.OutQuad
                    }
                }
            }

            HoverHandler {
                id: controlHover
                cursorShape: Qt.PointingHandCursor
            }
            TapHandler {
                id: controlTap
                onTapped: control.activated()
            }

            Accessible.role: Accessible.Button
            Accessible.name: control.label
            Accessible.onPressAction: control.activated()
        }
    }

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

        // Arrive, do not blink into place. The capsule only ever faded, so
        // media starting felt like a redraw rather than something appearing on
        // the bar. A short settle from slightly under full size gives it a
        // physical entrance without a novelty bounce beside working app icons,
        // and it scales about the capsule's own centre so the neighbours never
        // move. Both ends of the scale are gated by motionEnabled, so with
        // animations off the capsule simply is there.
        transformOrigin: Item.Center
        scale: root.active ? 1.0 : (root.motionEnabled ? 0.88 : 1.0)
        Behavior on scale {
            NumberAnimation {
                duration: root.motionGeometry
                easing.type: root.design.easeEmphasis
            }
        }

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
            // Density from the family's own palette, not a literal: a
            // true-black OLED profile wants a denser slab than the reference
            // dark, and a light profile wants less body. See MoUI.Tokens.
            color: Qt.alpha(Kirigami.Theme.backgroundColor,
                            root.design.glassDensity(Kirigami.Theme.backgroundColor))
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

            // A COLUMN, not two anchored siblings. The content row and the
            // timeline used to be anchored children of the same shell, and
            // anchors do not reserve anything from each other — so the
            // hairline drew straight across the source caption and no amount
            // of bottomMargin on the row fixed it, because the row's children
            // still sized themselves against the full shell. A column cannot
            // overlap: the lane takes its height first and the row gets what
            // is genuinely left.
            ColumnLayout {
                anchors.fill: parent
                // A pill's rim curves INWARD, so a flat margin lets the corner
                // eat whatever sits at the ends: the cover art was tangent to
                // the curve on one side and the caption was clipped by it on
                // the other.
                anchors.leftMargin: root.design.space2
                anchors.rightMargin: root.design.space2
                anchors.topMargin: 2
                anchors.bottomMargin: 2
                spacing: 1

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: root.design.space1
                layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

                Rectangle {
                    // DERIVED, never a literal. A hardcoded 38 was the same
                    // height the capsule had left over, so the artwork had no
                    // breathing room at all and any inset — including one I
                    // added here — pushed it and the caption straight through
                    // the pill's bottom curve. Sizing from the shell keeps a
                    // real margin at every panel height the bar can take.
                    readonly property int artSize:
                        Math.round(compactShell.height * 0.7)
                    Layout.preferredWidth: artSize
                    Layout.preferredHeight: artSize
                    // Without this the artwork stretched to the capsule's full
                    // height and sat off-centre against the type beside it.
                    Layout.alignment: Qt.AlignVCenter
                    radius: root.design.radiusControl
                    color: Qt.alpha(Kirigami.Theme.highlightColor, 0.16)

                    // NOT Rectangle{radius}+clip: Qt clips a child to the
                    // item's BOUNDING BOX, never to its rounded corners, so an
                    // Image inside a rounded frame renders as a hard square
                    // that pokes out of every corner. It was invisible while
                    // the art was soft and became obvious the moment the
                    // decode was fixed. ShadowedImage rounds the texture
                    // itself with distance fields — the same primitive
                    // Kirigami's own cards use — so there is no mask layer and
                    // no MultiEffect in plasmashell's always-on budget.
                    // radiusControl, not a circle: the expanded cover is a
                    // rounded square, so the artwork no longer changes shape
                    // when the capsule opens.
                    Kirigami.ShadowedImage {
                        id: compactArt
                        anchors.fill: parent
                        radius: parent.radius
                        source: root.artworkSource
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize.width: root.decodePx(width)
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
                    id: compactText
                    Layout.fillWidth: true
                    Layout.minimumWidth: 92
                    // Centre the two lines as a BLOCK. Filling the capsule's
                    // full height pushed the caption onto the pill's bottom
                    // curve, which clipped it — the source name was cut in
                    // half on the live panel.
                    Layout.alignment: Qt.AlignVCenter
                    Layout.fillHeight: false
                    Layout.leftMargin: root.design.space1
                    Layout.rightMargin: root.design.space1
                    spacing: 0

                    // A track change used to be a hard text swap: one frame the
                    // old title, the next the new one, with no relationship
                    // between them. On a surface whose whole job is to show
                    // what is playing, that is the moment the user actually
                    // looks at — so it is the moment worth animating. The block
                    // dips and lifts as the text is replaced, which reads as
                    // the capsule turning over rather than glitching. It is a
                    // one-shot triggered by real MPRIS data, never a loop, and
                    // it collapses to nothing when the user has motion off
                    // because motionFast is already gated on longDuration > 1.
                    opacity: 1
                    Connections {
                        target: root
                        function onDisplayTrackChanged() { trackTurn.restart(); }
                    }
                    SequentialAnimation {
                        id: trackTurn
                        running: false
                        ParallelAnimation {
                            NumberAnimation {
                                target: compactText; property: "opacity"
                                to: 0.15; duration: Math.round(root.motionFast / 2)
                                easing.type: Easing.OutCubic
                            }
                            NumberAnimation {
                                target: compactText; property: "y"
                                to: compactText.y + 3
                                duration: Math.round(root.motionFast / 2)
                                easing.type: Easing.OutCubic
                            }
                        }
                        ParallelAnimation {
                            NumberAnimation {
                                target: compactText; property: "opacity"
                                to: 1; duration: root.motionFast
                                easing.type: Easing.OutCubic
                            }
                            NumberAnimation {
                                target: compactText; property: "y"
                                to: compactText.y
                                duration: root.motionFast
                                easing.type: root.design.easeEmphasis
                            }
                        }
                    }

                    // FIXED line boxes, not the font's own. An Arabic-capable UI
                    // font carries a tall ascent/descent, so two natural line
                    // boxes came to roughly 41 px inside a 46 px capsule that
                    // also has to hold the timeline lane — the caption was
                    // pushed onto the pill's curve and the progress hairline
                    // drew straight through it. Pinning both lines makes the
                    // block 32 px whatever script it renders, so the capsule
                    // holds title, source and timeline at its real height and
                    // stays correct if the bar is ever made shorter.
                    PC3.Label {
                        Layout.fillWidth: true
                        text: root.displayTrack
                        color: Kirigami.Theme.textColor
                        font.pixelSize: root.design.typeSecondary
                        font.weight: Font.DemiBold
                        lineHeightMode: Text.FixedHeight
                        lineHeight: 17
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: root.rtl ? Text.AlignRight
                                                      : Text.AlignLeft
                    }
                    PC3.Label {
                        Layout.fillWidth: true
                        text: root.displaySource
                        color: Kirigami.Theme.disabledTextColor
                        font.pixelSize: root.design.typeCaption
                        lineHeightMode: Text.FixedHeight
                        lineHeight: 15
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: root.rtl ? Text.AlignRight
                                                      : Text.AlignLeft
                    }
                }

                MediaControl {
                    revealed: compactHover.hovered && root.canGoPrevious
                    controlEnabled: root.canGoPrevious
                    iconName: root.rtl ? "media-skip-forward-symbolic"
                                       : "media-skip-backward-symbolic"
                    label: root.local("السابق", "Previous")
                    onActivated: root.player.Previous()
                }

                // Play/pause is the one control that never hides: it is why the
                // capsule is reachable at all without opening anything.
                MediaControl {
                    controlEnabled: root.playing
                        ? root.canPause : (root.canPlay || root.canControl)
                    iconName: root.playing ? "media-playback-pause-symbolic"
                                           : "media-playback-start-symbolic"
                    label: root.playing ? root.local("إيقاف مؤقت", "Pause")
                                        : root.local("تشغيل", "Play")
                    onActivated: root.togglePlaying()
                }

                MediaControl {
                    revealed: compactHover.hovered && root.canGoNext
                    controlEnabled: root.canGoNext
                    iconName: root.rtl ? "media-skip-backward-symbolic"
                                       : "media-skip-forward-symbolic"
                    label: root.local("التالي", "Next")
                    onActivated: root.player.Next()
                }

                MediaControl {
                    revealed: compactHover.hovered && root.hasVolume
                    controlEnabled: root.hasVolume
                    iconName: root.volume <= 0.01
                        ? "audio-volume-muted-symbolic"
                        : "audio-volume-high-symbolic"
                    label: root.volume <= 0.01
                        ? root.local("إلغاء الكتم", "Unmute")
                        : root.local("كتم", "Mute")
                    onActivated: root.toggleMuted()
                }
            }

            // The progress hairline had two defects, and both were visible.
            // It was anchored to the pill's BOTTOM EDGE, but that edge is a
            // curve, so a flat bar ran straight past it at each end and read
            // as a stray line under the capsule instead of part of it. And it
            // was anchored to parent.LEFT in every language, so in Arabic —
            // where the whole capsule is mirrored — it grew away from the
            // start of the track and appeared to drain as the media played.
            // Inset by the corner radius so it lives in the capsule's straight
            // middle, give it a track so the remaining time is legible too,
            // mirror the fill for RTL, and let it travel instead of jumping
            // between the one-second position samples.
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 3
                Layout.leftMargin: compactShell.radius * 0.35
                Layout.rightMargin: compactShell.radius * 0.35
                visible: root.hasTimeline

                Rectangle {
                    anchors.fill: parent
                    radius: height / 2
                    color: Qt.alpha(Kirigami.Theme.textColor, 0.14)
                }
                Rectangle {
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.left: root.rtl ? undefined : parent.left
                    anchors.right: root.rtl ? parent.right : undefined
                    width: parent.width * root.progress
                    radius: height / 2
                    color: Kirigami.Theme.highlightColor
                    // A settle, not a crawl: position only arrives while the
                    // capsule is hovered or open, so this never runs at rest.
                    Behavior on width {
                        NumberAnimation {
                            duration: root.motionFast
                            easing.type: Easing.OutCubic
                        }
                    }
                }
            }
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

                    // Same rounded-texture reason as the compact cover above.
                    Kirigami.ShadowedImage {
                        id: expandedArt
                        anchors.fill: parent
                        radius: parent.radius
                        source: root.artworkSource
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize.width: root.decodePx(width)
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

            // The same control language as the capsule, one step up in size,
            // with the primary action finally reading as primary.
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: root.design.space4

                MediaControl {
                    slotSize: 40
                    controlEnabled: root.canGoPrevious
                    iconName: root.rtl ? "media-skip-forward-symbolic"
                                       : "media-skip-backward-symbolic"
                    label: root.local("السابق", "Previous")
                    onActivated: root.player.Previous()
                }
                MediaControl {
                    primary: true
                    controlEnabled: root.playing
                        ? root.canPause : (root.canPlay || root.canControl)
                    iconName: root.playing ? "media-playback-pause-symbolic"
                                           : "media-playback-start-symbolic"
                    label: root.playing ? root.local("إيقاف مؤقت", "Pause")
                                        : root.local("تشغيل", "Play")
                    onActivated: root.togglePlaying()
                }
                MediaControl {
                    slotSize: 40
                    controlEnabled: root.canGoNext
                    iconName: root.rtl ? "media-skip-backward-symbolic"
                                       : "media-skip-forward-symbolic"
                    label: root.local("التالي", "Next")
                    onActivated: root.player.Next()
                }
            }

            // Volume is SECONDARY. It used to run the popup's full width with
            // the same weight as the seek bar, so the surface read as two equal
            // timelines; inset and shortened, the seek bar keeps the hierarchy.
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: root.design.space5
                Layout.rightMargin: root.design.space5
                Layout.topMargin: root.design.space1
                visible: root.hasVolume
                spacing: root.design.space2

                MediaControl {
                    slotSize: 28
                    controlEnabled: root.hasVolume
                    iconName: root.volume <= 0.01
                        ? "audio-volume-muted-symbolic"
                        : "audio-volume-high-symbolic"
                    label: root.volume <= 0.01
                        ? root.local("إلغاء الكتم", "Unmute")
                        : root.local("كتم", "Mute")
                    onActivated: root.toggleMuted()
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
