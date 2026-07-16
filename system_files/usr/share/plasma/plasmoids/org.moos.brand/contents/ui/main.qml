// MoOS Brand — the living emblem in the panel.
//
// The panel's launcher button (Kickoff) is compiled into plasma-desktop and
// cannot animate its icon, so the ANIMATED brand the owner asked for is this
// first-party applet: the emblem breathes at idle, glows on hover, and gives a
// quick spin flourish when pressed. Its popup is the MoOS glance — version,
// uptime, and the six actions that define the system (store, AI, updates,
// theme, settings, recovery), so the mark is a doorway, not a decoration.
//
// Rules inherited from org.moos.nova.clock (read its header before editing):
// - Kirigami.Theme for colours, never PlasmaCore.Theme (does not exist).
// - The compact representation MUST set Layout.minimumWidth/preferredWidth or
//   the panel lays the next applet inside this one's pixels.
// - Run the QML linter over this file before shipping a change.
//
// Motion is Animators/NumberAnimations on transform properties only — no
// shaders, no Lottie, the same budget as every MoOS always-on surface. The
// glow is a pre-baked sprite from artwork/generate_login_scene.py.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: compactRepresentation

    readonly property bool rtl: Qt.locale().textDirection === Qt.RightToLeft

    toolTipMainText: "MoOS"
    toolTipSubText: root.prettyName

    property string prettyName: "MoOS"
    property string versionLine: ""
    property string uptimeLine: ""

    // QML's XMLHttpRequest cannot read file:// in Qt 6 unless the embedding
    // process sets QML_XHR_ALLOW_FILE_READ — plasmashell does not (verified in
    // plasmawindowed 2026-07-16: the header stayed version-less, silently). The
    // executable engine below is the same reader the glance actions already
    // use, so os-release and uptime come from two one-shot `cat`s instead.
    P5Support.DataSource {
        id: reader
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName, data) => {
            const out = (data["stdout"] || "");
            if (sourceName.indexOf("os-release") >= 0) {
                const pretty = out.match(/^PRETTY_NAME="?([^"\n]+)"?$/m);
                const version = out.match(/^VERSION="?([^"\n]+)"?$/m);
                if (pretty) {
                    root.prettyName = pretty[1];
                }
                if (version) {
                    root.versionLine = version[1];
                }
            } else if (sourceName.indexOf("uptime") >= 0) {
                const seconds = parseFloat(out.split(" ")[0]);
                if (isFinite(seconds)) {
                    const days = Math.floor(seconds / 86400);
                    const hours = Math.floor((seconds % 86400) / 3600);
                    const minutes = Math.floor((seconds % 3600) / 60);
                    root.uptimeLine = days > 0 ? days + "d " + hours + "h"
                                    : (hours > 0 ? hours + "h " + minutes + "m" : minutes + "m");
                }
            }
            disconnectSource(sourceName);
        }
    }

    function refreshOsRelease() {
        reader.connectSource("cat /etc/os-release");
    }

    function refreshUptime() {
        reader.connectSource("cat /proc/uptime");
    }

    Component.onCompleted: refreshOsRelease()
    onExpandedChanged: {
        if (expanded) {
            refreshUptime();
        }
    }

    // One launcher for the glance actions. The executable engine runs the
    // command detached from the popup's lifetime; every command here is a
    // user-session MoOS binary (no pkexec, no root).
    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName) => {
            disconnectSource(sourceName);
        }
    }

    function run(command) {
        runner.connectSource(command);
        root.expanded = false;
    }

    compactRepresentation: MouseArea {
        id: compact

        // Wider than tall on purpose — the brand gets a little more presence
        // than a stock icon, without pushing the panel around: the width is
        // still derived from the panel height, so it scales with the dock.
        readonly property int contentWidth: Math.round(height * 1.2)

        implicitWidth: contentWidth
        implicitHeight: Kirigami.Units.gridUnit * 2

        Layout.minimumWidth: contentWidth
        Layout.preferredWidth: contentWidth
        Layout.maximumWidth: contentWidth

        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        Accessible.name: "MoOS"

        onClicked: {
            spinFlourish.restart();
            root.expanded = !root.expanded;
        }

        // Hover halo — the pre-baked cyan glow, brightening under the pointer.
        Image {
            anchors.centerIn: emblem
            width: emblem.width * 2.1
            height: width
            source: "../images/glow-cyan.png"
            opacity: compact.containsMouse ? 0.9 : 0.35
            Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
            SequentialAnimation on scale {
                loops: Animation.Infinite
                running: compact.visible
                NumberAnimation { to: 1.08; duration: 4000; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: 4000; easing.type: Easing.InOutSine }
            }
        }

        Image {
            id: emblem
            anchors.centerIn: parent
            // Fuller-bleed than a themed icon: the transparent vector mark can
            // use nearly the whole panel height and still breathe.
            width: Math.round(Math.min(parent.height, parent.width) * 0.92)
            height: width
            source: "file:///usr/share/moos/moos-logo.png"
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            smooth: true
            sourceSize: Qt.size(width * 2, height * 2)

            // The idle breath — slow enough to feel alive, never busy.
            SequentialAnimation on scale {
                loops: Animation.Infinite
                running: compact.visible && !spinFlourish.running
                NumberAnimation { to: 1.05; duration: 4000; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: 4000; easing.type: Easing.InOutSine }
            }

            // The press flourish: one quick full turn, settling with a spring.
            RotationAnimation {
                id: spinFlourish
                target: emblem
                property: "rotation"
                from: 0
                to: 360
                duration: 650
                easing.type: Easing.OutBack
                onStopped: emblem.rotation = 0
            }
        }
    }

    // ── The MoOS glance ───────────────────────────────────────────────────────
    fullRepresentation: Item {
        implicitWidth: Kirigami.Units.gridUnit * 19
        implicitHeight: mainColumn.implicitHeight + Kirigami.Units.largeSpacing * 4

        ColumnLayout {
            id: mainColumn
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing * 2
            spacing: Kirigami.Units.largeSpacing

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

                Item {
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 3.2
                    Layout.preferredHeight: Kirigami.Units.gridUnit * 3.2

                    Image {
                        anchors.centerIn: glanceEmblem
                        width: glanceEmblem.width * 1.9
                        height: width
                        source: "../images/glow-violet.png"
                        opacity: 0.55
                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            running: root.expanded
                            NumberAnimation { to: 0.8; duration: 3200; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 0.55; duration: 3200; easing.type: Easing.InOutSine }
                        }
                    }
                    Image {
                        id: glanceEmblem
                        anchors.fill: parent
                        source: "file:///usr/share/moos/moos-logo.png"
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        sourceSize: Qt.size(width * 2, height * 2)
                        SequentialAnimation on scale {
                            loops: Animation.Infinite
                            running: root.expanded
                            NumberAnimation { to: 1.04; duration: 3200; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 1.0; duration: 3200; easing.type: Easing.InOutSine }
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Text {
                        text: "MoOS"
                        color: Kirigami.Theme.textColor
                        font.family: "IBM Plex Sans"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 1.15)
                        font.weight: Font.DemiBold
                        font.letterSpacing: 2
                    }
                    Text {
                        text: root.versionLine
                        visible: text.length > 0
                        color: Kirigami.Theme.textColor
                        opacity: 0.62
                        font.family: "IBM Plex Sans"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.62)
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Text {
                        text: root.uptimeLine.length > 0
                            ? "قيد التشغيل منذ | Up for " + root.uptimeLine
                            : ""
                        visible: text.length > 0
                        color: Kirigami.Theme.textColor
                        opacity: 0.45
                        font.family: "IBM Plex Sans"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.58)
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Kirigami.Theme.textColor
                opacity: 0.12
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 3
                rowSpacing: Kirigami.Units.smallSpacing
                columnSpacing: Kirigami.Units.smallSpacing
                layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

                GlanceAction {
                    icon: "moos-store"
                    label: "المتجر | Store"
                    onActivated: root.run("moos-store")
                }
                GlanceAction {
                    icon: "moos-moai"
                    label: "Mo AI"
                    onActivated: root.run("moai")
                }
                GlanceAction {
                    icon: "update-none-symbolic"
                    label: "التحديثات | Updates"
                    onActivated: root.run("moos-update")
                }
                GlanceAction {
                    icon: "contrast-symbolic"
                    label: "الثيم | Theme"
                    onActivated: root.run("moos-theme toggle")
                }
                GlanceAction {
                    icon: "configure-symbolic"
                    label: "الإعدادات | Settings"
                    onActivated: root.run("systemsettings")
                }
                GlanceAction {
                    icon: "edit-undo-symbolic"
                    label: "الاستعادة | Recovery"
                    onActivated: root.run("moos-rollback")
                }
            }
        }
    }

    // A quiet, premium action tile: icon over a caption, hover lift, press dip.
    component GlanceAction: Rectangle {
        id: tile

        property alias icon: tileIcon.source
        property string label: ""
        signal activated()

        Layout.fillWidth: true
        Layout.preferredHeight: Kirigami.Units.gridUnit * 4.2
        radius: Kirigami.Units.cornerRadius
        // Translucent fill via the colour's alpha, NOT item opacity — opacity
        // multiplies into children and would dim the icon and caption with it.
        color: Qt.alpha(Kirigami.Theme.textColor,
                        tileMouse.pressed ? 0.16 : (tileMouse.containsMouse ? 0.12 : 0.06))
        scale: tileMouse.pressed ? 0.97 : (tileMouse.containsMouse ? 1.02 : 1.0)
        Behavior on color { ColorAnimation { duration: 120 } }
        Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

        ColumnLayout {
            anchors.centerIn: parent
            spacing: Math.round(Kirigami.Units.smallSpacing * 0.8)

            Kirigami.Icon {
                id: tileIcon
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                color: Kirigami.Theme.textColor
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: tile.label
                color: Kirigami.Theme.textColor
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.max(10, Math.round(Kirigami.Units.gridUnit * 0.55))
                font.weight: Font.Medium
            }
        }

        MouseArea {
            id: tileMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: tile.activated()
        }
    }
}
