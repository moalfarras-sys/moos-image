// SPDX-License-Identifier: GPL-2.0-or-later
// A front door to an installed settings owner. This control never mirrors a
// device setting or invents state: the destination KCM remains authoritative.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Controls.AbstractButton {
    id: tile
    property string glyph: "settings"
    property string description: ""
    hoverEnabled: true
    activeFocusOnTab: true
    padding: MoUI.Tokens.space4
    implicitHeight: Math.max(96, contentItem.implicitHeight + topPadding + bottomPadding)
    implicitWidth: Kirigami.Units.gridUnit * 18
    Accessible.name: text
    Accessible.description: description

    background: MoUI.Surface {
        interactive: true
        hovered: tile.hovered
        pressed: tile.down
        selected: tile.visualFocus
        // A quiet sheet at rest; focus is a complete, high-contrast perimeter.
        fillOpacity: tile.down ? 0.13 : tile.hovered ? 0.08 : 0.035
        border.color: Qt.alpha(tile.visualFocus ? Kirigami.Theme.highlightColor
            : Kirigami.Theme.textColor, tile.visualFocus ? 0.9 : 0.09)
        Behavior on color {
            ColorAnimation { duration: Kirigami.Units.longDuration > 1 ? MoUI.Tokens.motionFast : 0 }
        }
    }
    contentItem: RowLayout {
        spacing: MoUI.Tokens.space3
        Rectangle {
            Layout.preferredWidth: MoUI.Tokens.targetControl
            Layout.preferredHeight: MoUI.Tokens.targetControl
            radius: MoUI.Tokens.radiusControl
            color: Qt.alpha(Kirigami.Theme.highlightColor, 0.13)
            MoUI.SymbolIcon {
                anchors.centerIn: parent
                width: MoUI.Tokens.iconLarge
                height: width
                symbol: MoUI.SymbolCatalog.resolve(tile.glyph)
                foreground: Kirigami.Theme.highlightColor
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: MoUI.Tokens.space1
            Controls.Label {
                Layout.fillWidth: true
                text: tile.text
                textFormat: Text.PlainText
                font.pixelSize: MoUI.Tokens.typeBody
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.WordWrap
            }
            Controls.Label {
                Layout.fillWidth: true
                text: tile.description
                textFormat: Text.PlainText
                color: Qt.alpha(Kirigami.Theme.textColor, 0.72)
                font.pixelSize: MoUI.Tokens.typeSecondary
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.WordWrap
            }
        }
        MoUI.SymbolIcon {
            Layout.preferredWidth: MoUI.Tokens.iconSmall
            Layout.preferredHeight: MoUI.Tokens.iconSmall
            symbol: MoUI.SymbolCatalog.resolve("arrow")
            foreground: Qt.alpha(Kirigami.Theme.textColor, 0.6)
            transform: Scale { origin.x: 8; xScale: MoUI.Locale.rtl ? -1 : 1 }
        }
    }
}
