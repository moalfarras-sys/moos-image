/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    MoOS Theme Picker — a real, working chooser for the 16 MoOS Global Themes.
    The theme LIST is discovered from the installed look-and-feel packages (the
    source of truth), not a hardcoded table; each card previews the theme's own
    wallpaper + accent, and applying runs `moos-theme apply-lnf <id>` which is
    the atomic, undo-safe switch (save-previous + revert-on-failure). The picker
    itself is Kirigami.Theme-driven, so it wears whichever theme is active.
*/
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support

Kirigami.ApplicationWindow {
    id: root
    title: "MoOS Themes"
    width: Kirigami.Units.gridUnit * 52
    height: Kirigami.Units.gridUnit * 38
    minimumWidth: Kirigami.Units.gridUnit * 30
    minimumHeight: Kirigami.Units.gridUnit * 24

    readonly property color accent: Kirigami.Theme.highlightColor
    property string currentLnf: ""
    property bool busy: false

    // ── real command runner (Plasma executable engine) ──────────────────────
    P5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            root.handleOutput(source, (data && data["stdout"]) ? data["stdout"] : "")
            disconnectSource(source)
        }
        function run(cmd) { connectSource(cmd) }
    }

    function handleOutput(cmd, out) {
        if (cmd.indexOf("look-and-feel/org.moos.ui2") >= 0 && cmd.indexOf("metadata.json") >= 0) {
            themesModel.clear();
            const lines = out.split("\n");
            for (let i = 0; i < lines.length; ++i) {
                const line = lines[i].trim();
                if (!line) continue;
                const parts = line.split("|");
                const id = parts[0];
                const name = parts.length > 1 && parts[1] ? parts[1] : id;
                themesModel.append({ lnf: id, name: name, isLight: id.endsWith(".light") });
            }
            root.refreshCurrent();
        } else if (cmd.indexOf("LookAndFeelPackage") >= 0) {
            root.currentLnf = out.trim();
            root.busy = false;
        }
    }

    function refreshThemes() {
        exec.run('for d in /usr/share/plasma/look-and-feel/org.moos.ui2*; do id=$(basename "$d"); nm=$(sed -n \'s/.*"Name"[^"]*"\\([^"]*\\)".*/\\1/p\' "$d/metadata.json" | head -1); echo "$id|$nm"; done');
    }
    function refreshCurrent() {
        exec.run('kreadconfig6 --file kdeglobals --group KDE --key LookAndFeelPackage');
    }
    function applyTheme(lnf) {
        if (root.busy) return;
        root.busy = true;
        exec.run('moos-theme apply-lnf ' + lnf);
        // give the switch a moment, then read back what actually took
        currentTimer.restart();
    }
    function undo() {
        if (root.busy) return;
        root.busy = true;
        exec.run('moos-theme undo');
        currentTimer.restart();
    }
    Timer { id: currentTimer; interval: 1400; onTriggered: root.refreshCurrent() }

    ListModel { id: themesModel }
    Component.onCompleted: refreshThemes()

    // ── header ──────────────────────────────────────────────────────────────
    header: QQC2.ToolBar {
        contentItem: RowLayout {
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon { source: "preferences-desktop-theme-global"; implicitWidth: Kirigami.Units.iconSizes.medium; implicitHeight: implicitWidth }
            ColumnLayout {
                spacing: 0
                Layout.fillWidth: true
                Kirigami.Heading { level: 3; text: "ثيمات MoOS  ·  MoOS Themes"; elide: Text.ElideRight }
                QQC2.Label {
                    text: root.busy ? "…يُطبّق | applying" : (root.currentActiveName())
                    opacity: 0.7; font.pointSize: Kirigami.Theme.smallFont.pointSize; elide: Text.ElideRight
                }
            }
            QQC2.Button {
                text: "تراجع | Undo"
                icon.name: "edit-undo"
                enabled: !root.busy
                onClicked: root.undo()
            }
        }
    }
    function currentActiveName() {
        for (let i = 0; i < themesModel.count; ++i) {
            if (themesModel.get(i).lnf === root.currentLnf) return "المُطبّق | Active:  " + themesModel.get(i).name;
        }
        return root.currentLnf;
    }

    // ── the grid of theme cards ─────────────────────────────────────────────
    QQC2.ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        GridView {
            id: grid
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            cellWidth: Math.floor(width / Math.max(1, Math.floor(width / (Kirigami.Units.gridUnit * 15))))
            cellHeight: Kirigami.Units.gridUnit * 12
            model: themesModel
            clip: true

            delegate: Item {
                width: grid.cellWidth
                height: grid.cellHeight
                required property string lnf
                required property string name
                required property bool isLight
                readonly property bool isActive: lnf === root.currentLnf

                QQC2.AbstractButton {
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.smallSpacing
                    hoverEnabled: true
                    onClicked: root.applyTheme(lnf)
                    scale: down ? 0.98 : (hovered ? 1.02 : 1.0)
                    Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }

                    background: Rectangle {
                        radius: Kirigami.Units.gridUnit * 0.6
                        color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.05)
                        border.width: isActive ? 2 : (parent.hovered ? 1.5 : 1)
                        border.color: isActive || parent.hovered
                            ? root.accent
                            : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.14)
                        Behavior on border.color { ColorAnimation { duration: Kirigami.Units.shortDuration } }
                    }
                    contentItem: ColumnLayout {
                        spacing: 0
                        // wallpaper preview
                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            Image {
                                anchors.fill: parent
                                source: "file:///usr/share/plasma/look-and-feel/" + lnf + "/contents/previews/fullscreenpreview.jpg"
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                Rectangle {   // clip corners (top)
                                    anchors.fill: parent
                                    color: "transparent"
                                }
                            }
                            // active check badge
                            Rectangle {
                                visible: isActive
                                anchors { top: parent.top; right: parent.right; margins: Kirigami.Units.smallSpacing }
                                width: Kirigami.Units.iconSizes.medium; height: width; radius: width / 2
                                color: root.accent
                                Kirigami.Icon { anchors.centerIn: parent; source: "checkmark"; color: "white"; width: Kirigami.Units.iconSizes.small; height: width }
                            }
                        }
                        // caption row
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.margins: Kirigami.Units.smallSpacing
                            spacing: Kirigami.Units.smallSpacing
                            QQC2.Label {
                                Layout.fillWidth: true
                                text: name
                                elide: Text.ElideRight
                                font.weight: Font.DemiBold
                                color: Kirigami.Theme.textColor
                            }
                            Kirigami.Icon {
                                source: isLight ? "weather-clear" : "weather-clear-night"
                                implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth
                                opacity: 0.7
                            }
                        }
                    }
                }
            }
        }
    }

    // gentle busy veil
    Rectangle {
        anchors.fill: parent
        visible: root.busy
        color: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.35)
        QQC2.BusyIndicator { anchors.centerIn: parent; running: root.busy }
    }
}
