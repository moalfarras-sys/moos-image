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
        // Qualify the property explicitly. Plasma's expandedChanged signal also
        // carries an `expanded` argument; resolving the bare name through that
        // injected argument is deprecated in Qt 6 and warns on every login.
        if (root.expanded) {
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

        // A wordmark, not another anonymous dock icon. The width remains tied
        // to panel height, so the control has the same physical proportions at
        // 100% and 200% scale.
        readonly property int contentWidth: Math.round(height * 2.45)

        implicitWidth: contentWidth
        implicitHeight: Kirigami.Units.gridUnit * 2

        Layout.minimumWidth: contentWidth
        Layout.preferredWidth: contentWidth
        Layout.maximumWidth: contentWidth

        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        Accessible.name: "MoOS"

        onClicked: mouse => {
            spinFlourish.restart();
            if (mouse.button === Qt.MiddleButton) {
                root.run("gdbus call --session -d org.kde.plasmashell -o /PlasmaShell -m org.kde.PlasmaShell.activateLauncherMenu");
            } else {
                root.expanded = !root.expanded;
            }
        }

        // The whole control is one calm piece of mineral glass. The earlier
        // version rendered a large spinning logo in an empty slot, which made
        // the bar read as a row of unrelated icons.
        Rectangle {
            anchors.centerIn: parent
            width: Math.round(compact.contentWidth * 0.94)
            height: Math.round(compact.height * 0.78)
            radius: height / 2
            color: Qt.alpha(compact.containsMouse
                                ? Kirigami.Theme.highlightColor
                                : Kirigami.Theme.textColor,
                            compact.pressed ? 0.23 : (compact.containsMouse ? 0.14 : 0.065))
            border.width: 1
            border.color: Qt.alpha(compact.containsMouse
                                       ? Kirigami.Theme.highlightColor
                                       : Kirigami.Theme.textColor,
                                   compact.containsMouse ? 0.48 : 0.13)
            scale: compact.pressed ? 0.97 : 1.0
            Behavior on color { ColorAnimation { duration: 150 } }
            Behavior on border.color { ColorAnimation { duration: 150 } }
            Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        }

        RowLayout {
            anchors.centerIn: parent
            width: Math.round(compact.contentWidth * 0.78)
            height: Math.round(compact.height * 0.68)
            spacing: Math.max(4, Math.round(Kirigami.Units.smallSpacing * 0.75))
            layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

            Item {
                Layout.preferredWidth: parent.height
                Layout.preferredHeight: parent.height

                Image {
                    anchors.centerIn: emblem
                    width: emblem.width * 1.65
                    height: width
                    source: "../images/glow-cyan.png"
                    opacity: compact.containsMouse ? 0.75 : 0.30
                    Behavior on opacity { NumberAnimation { duration: 180 } }
                }
                Image {
                    id: emblem
                    anchors.centerIn: parent
                    width: Math.round(parent.height * 0.82)
                    height: width
                    source: "file:///usr/share/moos/moos-logo.png"
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    smooth: true
                    sourceSize: Qt.size(width * 2, height * 2)

                    SequentialAnimation on scale {
                        loops: Animation.Infinite
                        running: compact.visible && !spinFlourish.running
                        NumberAnimation { to: 1.035; duration: 4200; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 1.0; duration: 4200; easing.type: Easing.InOutSine }
                    }
                    RotationAnimation {
                        id: spinFlourish
                        target: emblem
                        property: "rotation"
                        from: 0
                        to: 360
                        duration: 620
                        easing.type: Easing.OutBack
                        onStopped: emblem.rotation = 0
                    }
                }
                Image {
                    anchors.centerIn: emblem
                    width: emblem.width * 1.22
                    height: width
                    source: "../images/ring.png"
                    opacity: compact.containsMouse ? 0.84 : 0.42
                    sourceSize: Qt.size(width * 2, height * 2)
                    RotationAnimator on rotation {
                        from: 0; to: 360
                        duration: compact.containsMouse ? 9000 : 18000
                        loops: Animation.Infinite
                        running: compact.visible
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: -1
                Text {
                    text: "MoOS"
                    color: Kirigami.Theme.textColor
                    font.family: "IBM Plex Sans"
                    font.pixelSize: Math.max(12, Math.round(compact.height * 0.26))
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.5
                }
                Text {
                    text: compact.containsMouse
                        ? (root.rtl ? "مركز التحكم" : "CONTROL")
                        : (root.rtl ? "جاهز" : "READY")
                    color: compact.containsMouse
                        ? Kirigami.Theme.highlightColor
                        : Kirigami.Theme.positiveTextColor
                    font.family: "IBM Plex Sans"
                    font.pixelSize: Math.max(7, Math.round(compact.height * 0.13))
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.2
                    opacity: 0.84
                    Behavior on color { ColorAnimation { duration: 160 } }
                }
            }

            Rectangle {
                Layout.preferredWidth: Math.max(5, Math.round(compact.height * 0.11))
                Layout.preferredHeight: width
                radius: width / 2
                color: Kirigami.Theme.positiveTextColor
                opacity: compact.containsMouse ? 1.0 : 0.72
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    running: compact.visible && !compact.containsMouse
                    NumberAnimation { to: 0.36; duration: 1800; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.72; duration: 1800; easing.type: Easing.InOutSine }
                }
            }
        }
    }

    // ── The MoOS glance ───────────────────────────────────────────────────────
    fullRepresentation: Item {
        implicitWidth: Kirigami.Units.gridUnit * 22
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
                    Image {
                        anchors.centerIn: glanceEmblem
                        width: glanceEmblem.width * 1.42
                        height: width
                        source: "../images/ring.png"
                        mirror: true
                        opacity: 0.7
                        sourceSize: Qt.size(width * 2, height * 2)
                        RotationAnimator on rotation {
                            from: 360; to: 0
                            duration: 22000
                            loops: Animation.Infinite
                            running: root.expanded
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
                Layout.preferredHeight: Kirigami.Units.gridUnit * 3.35
                radius: Kirigami.Units.cornerRadius * 1.45
                color: Qt.alpha(Kirigami.Theme.highlightColor,
                                searchInput.activeFocus ? 0.22 : (launchMouse.containsMouse ? 0.17 : 0.11))
                border.width: 1
                border.color: Qt.alpha(Kirigami.Theme.highlightColor,
                                       searchInput.activeFocus ? 0.85 : (launchMouse.containsMouse ? 0.62 : 0.34))
                scale: launchMouse.pressed ? 0.985 : 1.0
                Behavior on color { ColorAnimation { duration: 140 } }
                Behavior on border.color { ColorAnimation { duration: 140 } }
                Behavior on scale { NumberAnimation { duration: 100; easing.type: Easing.OutCubic } }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Kirigami.Units.largeSpacing * 1.2
                    anchors.rightMargin: Kirigami.Units.largeSpacing * 1.2
                    spacing: Kirigami.Units.mediumSpacing
                    layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

                    Rectangle {
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 2.1
                        Layout.preferredHeight: width
                        radius: width / 2
                        color: Qt.alpha(Kirigami.Theme.highlightColor, searchInput.activeFocus ? 0.35 : 0.20)
                        Behavior on color { ColorAnimation { duration: 140 } }

                        Kirigami.Icon {
                            anchors.centerIn: parent
                            width: Kirigami.Units.iconSizes.medium
                            height: width
                            source: searchInput.text.trim().length > 0 ? (root.rtl ? "arrow-left-symbolic" : "arrow-right-symbolic") : "system-search-symbolic"
                            color: Kirigami.Theme.highlightColor
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        TextInput {
                            id: searchInput
                            Layout.fillWidth: true
                            font.family: "IBM Plex Sans"
                            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.72)
                            font.weight: Font.DemiBold
                            color: Kirigami.Theme.textColor
                            selectByMouse: true
                            clip: true

                            Text {
                                text: root.rtl ? "ابحث أو اكتب لـ Mo AI..." : "Search or type for Mo AI..."
                                color: Kirigami.Theme.textColor
                                opacity: 0.45
                                visible: searchInput.text.length === 0
                                font: searchInput.font
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.right: parent.right
                            }

                            onAccepted: {
                                const query = text.trim();
                                if (query.startsWith("ai ") || query.startsWith("ذكاء ") || query === "ai" || query === "ذكاء") {
                                    root.run("moai");
                                } else if (query.startsWith("store ") || query.startsWith("متجر ") || query === "store" || query === "متجر") {
                                    root.run("moos-store");
                                } else if (query.length > 0) {
                                    const escaped = query.replace(/'/g, "'\\''");
                                    root.run("gdbus call --session -d org.kde.krunner -o /App -m org.kde.krunner.displaySingleRunner '" + escaped + "' || gdbus call --session -d org.kde.plasmashell -o /PlasmaShell -m org.kde.PlasmaShell.activateLauncherMenu");
                                } else {
                                    root.run("gdbus call --session -d org.kde.plasmashell -o /PlasmaShell -m org.kde.PlasmaShell.activateLauncherMenu");
                                }
                                searchInput.text = "";
                            }
                        }

                        Text {
                            text: {
                                const q = searchInput.text.trim();
                                if (q.startsWith("ai ") || q.startsWith("ذكاء ")) return root.rtl ? "↵ تشغيل Mo AI" : "↵ Open Mo AI";
                                if (q.startsWith("store ") || q.startsWith("متجر ")) return root.rtl ? "↵ فتح متجر MoOS" : "↵ Open Mo Store";
                                if (q.length > 0) return root.rtl ? "↵ بحث في التطبيقات والنظام" : "↵ Search apps & system";
                                return root.rtl ? "التطبيقات والملفات والإعدادات" : "Apps, files and settings";
                            }
                            color: searchInput.text.trim().length > 0 ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
                            opacity: searchInput.text.trim().length > 0 ? 0.9 : 0.55
                            font.family: "IBM Plex Sans"
                            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.54)
                            font.weight: searchInput.text.trim().length > 0 ? Font.Medium : Font.Normal
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                        Layout.preferredHeight: width
                        radius: width / 2
                        color: Qt.alpha(Kirigami.Theme.textColor, 0.1)
                        visible: searchInput.text.length > 0

                        Kirigami.Icon {
                            anchors.centerIn: parent
                            width: Kirigami.Units.iconSizes.small
                            height: width
                            source: "edit-clear-symbolic"
                            color: Kirigami.Theme.textColor
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: searchInput.text = ""
                        }
                    }

                    Kirigami.Icon {
                        visible: searchInput.text.length === 0
                        Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                        Layout.preferredHeight: width
                        source: root.rtl ? "arrow-left-symbolic" : "arrow-right-symbolic"
                        color: Kirigami.Theme.textColor
                        opacity: launchMouse.containsMouse ? 0.9 : 0.45
                    }
                }

                MouseArea {
                    id: launchMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.IBeamCursor
                    onClicked: searchInput.forceActiveFocus()
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

                StatusChip {
                    icon: "security-high-symbolic"
                    label: root.rtl ? "النظام محمي" : "System protected"
                    accent: Kirigami.Theme.positiveTextColor
                }
                StatusChip {
                    icon: "chronometer-symbolic"
                    label: root.uptimeLine.length > 0
                        ? (root.rtl ? "تشغيل " : "Up ") + root.uptimeLine
                        : (root.rtl ? "جلسة نشطة" : "Session active")
                    accent: Kirigami.Theme.highlightColor
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
                columns: 2
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

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 2.45
                radius: Kirigami.Units.cornerRadius
                color: Qt.alpha(Kirigami.Theme.textColor,
                                sessionMouse.containsMouse ? 0.11 : 0.055)
                Behavior on color { ColorAnimation { duration: 120 } }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Kirigami.Units.largeSpacing
                    anchors.rightMargin: Kirigami.Units.largeSpacing
                    layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight
                    Kirigami.Icon {
                        Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                        Layout.preferredHeight: width
                        source: "system-shutdown-symbolic"
                        color: Kirigami.Theme.negativeTextColor
                    }
                    Text {
                        Layout.fillWidth: true
                        text: root.rtl ? "القفل والطاقة والجلسة" : "Lock, power & session"
                        color: Kirigami.Theme.textColor
                        font.family: "IBM Plex Sans"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.62)
                        font.weight: Font.Medium
                    }
                    Kirigami.Icon {
                        Layout.preferredWidth: Kirigami.Units.iconSizes.small
                        Layout.preferredHeight: width
                        source: root.rtl ? "arrow-left-symbolic" : "arrow-right-symbolic"
                        color: Kirigami.Theme.textColor
                        opacity: 0.45
                    }
                }
                MouseArea {
                    id: sessionMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.run("ksmserver-logout-greeter")
                }
            }
        }
    }

    component StatusChip: Rectangle {
        id: chip
        property alias icon: chipIcon.source
        property string label: ""
        property color accent: Kirigami.Theme.highlightColor

        Layout.fillWidth: true
        Layout.preferredHeight: Kirigami.Units.gridUnit * 1.7
        radius: height / 2
        color: Qt.alpha(accent, 0.085)
        border.width: 1
        border.color: Qt.alpha(accent, 0.22)
        RowLayout {
            anchors.centerIn: parent
            spacing: Kirigami.Units.smallSpacing
            Kirigami.Icon {
                id: chipIcon
                Layout.preferredWidth: Kirigami.Units.iconSizes.small
                Layout.preferredHeight: width
                color: chip.accent
            }
            Text {
                text: chip.label
                color: chip.accent
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.max(9, Math.round(Kirigami.Units.gridUnit * 0.51))
                font.weight: Font.Medium
            }
        }
    }

    // A quiet, premium action tile: compact horizontal composition, hover lift,
    // and a restrained accent rail instead of a generic icon grid.
    component GlanceAction: Rectangle {
        id: tile

        property alias icon: tileIcon.source
        property string label: ""
        signal activated()

        Layout.fillWidth: true
        Layout.preferredHeight: Kirigami.Units.gridUnit * 2.85
        radius: Kirigami.Units.cornerRadius
        // Translucent fill via the colour's alpha, NOT item opacity — opacity
        // multiplies into children and would dim the icon and caption with it.
        color: Qt.alpha(Kirigami.Theme.textColor,
                        tileMouse.pressed ? 0.16 : (tileMouse.containsMouse ? 0.12 : 0.06))
        scale: tileMouse.pressed ? 0.97 : (tileMouse.containsMouse ? 1.02 : 1.0)
        Behavior on color { ColorAnimation { duration: 120 } }
        Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

        Rectangle {
            width: 2
            height: parent.height * 0.42
            radius: 1
            anchors.left: root.rtl ? undefined : parent.left
            anchors.right: root.rtl ? parent.right : undefined
            anchors.verticalCenter: parent.verticalCenter
            color: Kirigami.Theme.highlightColor
            opacity: tileMouse.containsMouse ? 0.9 : 0.28
            Behavior on opacity { NumberAnimation { duration: 120 } }
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Kirigami.Units.largeSpacing
            anchors.rightMargin: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing
            layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

            Kirigami.Icon {
                id: tileIcon
                Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                color: Kirigami.Theme.textColor
            }
            Text {
                Layout.fillWidth: true
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
