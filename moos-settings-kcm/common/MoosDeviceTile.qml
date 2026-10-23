// SPDX-License-Identifier: GPL-2.0-or-later
// A measured device state and its native settings destination, in one target.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Controls.AbstractButton {
    id: tile
    property string glyph: "system"
    property string stateText: ""
    property string detail: ""
    property bool active: false
    property bool compact: false
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                 Kirigami.Theme.textColor.b, 0.72)
    padding: compact ? MoUI.Tokens.space3 : MoUI.Tokens.space4
    implicitWidth: 220
    implicitHeight: Math.max(compact ? 84 : 144, contentItem.implicitHeight + topPadding + bottomPadding)
    hoverEnabled: true
    activeFocusOnTab: true
    Accessible.name: text + ": " + stateText
    Accessible.description: detail
    background: MoUI.Surface {
        interactive: true
        hovered: tile.hovered
        pressed: tile.down
        selected: tile.visualFocus
        // A text-tinted 0.09 fill reduced secondary ink to 4.26:1 in a Light
        // family. State belongs to the accent rim/icon; keep the readable fill.
        fillOpacity: 0.035
        opacity: tile.compact && !tile.hovered && !tile.down && !tile.visualFocus ? 0 : 1
        border.color: Qt.alpha(tile.visualFocus || tile.active ? Kirigami.Theme.highlightColor
            : Kirigami.Theme.textColor, tile.visualFocus ? 0.9 : tile.active ? 0.32 : 0.09)
    }
    contentItem: GridLayout {
        columns: 3
        columnSpacing: MoUI.Tokens.space3
        rowSpacing: MoUI.Tokens.space1
        MoUI.SymbolIcon {
            Layout.row: 0
            Layout.column: 0
            Layout.rowSpan: tile.compact ? 3 : 1
            Layout.preferredWidth: MoUI.Tokens.iconLarge
            Layout.preferredHeight: width
            symbol: MoUI.SymbolCatalog.resolve(tile.glyph)
            foreground: tile.active ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
        }
        Controls.Label {
            Layout.row: 0
            Layout.column: 1
            Layout.fillWidth: true
            text: tile.text
            textFormat: Text.PlainText
            font.pixelSize: MoUI.Tokens.typeSecondary
            horizontalAlignment: Text.AlignLeft
            wrapMode: Text.WordWrap
        }
        MoUI.SymbolIcon {
            Layout.row: 0
            Layout.column: 2
            Layout.rowSpan: tile.compact ? 3 : 1
            Layout.preferredWidth: MoUI.Tokens.iconSmall
            Layout.preferredHeight: width
            symbol: MoUI.SymbolCatalog.resolve("arrow")
            foreground: tile.secondaryInk
            transform: Scale { origin.x: 8; xScale: MoUI.Locale.rtl ? -1 : 1 }
        }
        Controls.Label {
            Layout.row: 1
            Layout.column: tile.compact ? 1 : 0
            Layout.columnSpan: tile.compact ? 1 : 3
            Layout.fillWidth: true
            text: tile.stateText
            textFormat: Text.PlainText
            font.pixelSize: tile.compact ? MoUI.Tokens.typeBody : MoUI.Tokens.typeTitle
            font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignLeft
            wrapMode: Text.WordWrap
        }
        Controls.Label {
            Layout.row: 2
            Layout.column: tile.compact ? 1 : 0
            Layout.columnSpan: tile.compact ? 1 : 3
            Layout.fillWidth: true
            text: tile.detail
            textFormat: Text.PlainText
            color: tile.secondaryInk
            font.pixelSize: MoUI.Tokens.typeSecondary
            horizontalAlignment: Text.AlignLeft
            wrapMode: Text.WrapAnywhere
        }
    }
}
