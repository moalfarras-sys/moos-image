// SPDX-License-Identifier: GPL-2.0-or-later
// The MoOS face of the MoOS group: the mark, the name, the version and the chips a
// person checks first, on one Liquid Glass sheet. Chips and actions are slots.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

MoUI.GlassSurface {
    id: hero

    property url logoSource
    property string title: "MoOS"
    property string subtitle: ""
    property alias chips: chipFlow.data
    property alias actions: actionColumn.data
    readonly property bool wide: width > Kirigami.Units.gridUnit * 30
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)

    Layout.fillWidth: true
    implicitHeight: heroGrid.implicitHeight + MoUI.Tokens.space5 * 2
    floating: true
    depth: MoUI.Tokens.glassLevelDialog
    surfaceColor: Kirigami.Theme.backgroundColor
    inkColor: Kirigami.Theme.textColor
    accentColor: Kirigami.Theme.highlightColor
    Accessible.role: Accessible.Grouping
    Accessible.name: subtitle ? title + " — " + subtitle : title

    GridLayout {
        id: heroGrid
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: MoUI.Tokens.space5
        columns: hero.wide ? 3 : 1
        columnSpacing: MoUI.Tokens.space5
        rowSpacing: MoUI.Tokens.space4

        Item {
            id: mark
            Layout.preferredWidth: Kirigami.Units.gridUnit * 5
            Layout.preferredHeight: Kirigami.Units.gridUnit * 5
            Layout.alignment: hero.wide ? Qt.AlignVCenter : Qt.AlignLeft
            Accessible.ignored: true

            Image {
                id: logo
                anchors.fill: parent
                source: hero.logoSource
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                smooth: true
                mipmap: true
                visible: status === Image.Ready
            }
            // Without the logo file the MoOS mark is drawn, never another project's.
            Rectangle {
                anchors.fill: parent
                visible: logo.status !== Image.Ready
                radius: MoUI.Tokens.radiusPanel
                color: Kirigami.Theme.highlightColor

                MoUI.SymbolIcon {
                    anchors.centerIn: parent
                    width: parent.width / 2
                    height: parent.height / 2
                    symbol: MoUI.SymbolCatalog.resolve("orbit")
                    foreground: Kirigami.Theme.highlightedTextColor
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: MoUI.Tokens.space2

            Kirigami.Heading {
                Layout.fillWidth: true
                text: hero.title
                level: 1
                font.weight: Font.Bold
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.WordWrap
            }
            Controls.Label {
                Layout.fillWidth: true
                visible: text !== ""
                text: hero.subtitle
                color: hero.secondaryInk
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.WordWrap
            }
            Flow {
                id: chipFlow
                Layout.fillWidth: true
                Layout.topMargin: MoUI.Tokens.space1
                spacing: MoUI.Tokens.space2
            }
        }

        ColumnLayout {
            id: actionColumn
            Layout.alignment: hero.wide ? Qt.AlignVCenter : Qt.AlignLeft
            spacing: MoUI.Tokens.space2
        }
    }
}
