// SPDX-License-Identifier: GPL-2.0-or-later
// A state a person reads, not a control: a glyph, a sentence, its detail and an
// optional chip at the trailing edge.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard
import org.moos.ui as MoUI

FormCard.AbstractFormDelegate {
    id: info

    property string glyph: ""
    property string description: ""
    property color glyphColor: Kirigami.Theme.highlightColor
    property alias trailing: trailingSlot.data
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)

    focusPolicy: Qt.NoFocus
    hoverEnabled: false
    background: null
    Accessible.role: Accessible.StaticText
    Accessible.name: text
    Accessible.description: description

    contentItem: RowLayout {
        spacing: MoUI.Tokens.space3

        MoUI.SymbolIcon {
            Layout.alignment: Qt.AlignTop
            visible: info.glyph !== ""
            symbol: MoUI.SymbolCatalog.resolve(info.glyph)
            foreground: info.glyphColor
            implicitWidth: MoUI.Tokens.iconLarge
            implicitHeight: MoUI.Tokens.iconLarge
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: MoUI.Tokens.space1

            Controls.Label {
                Layout.fillWidth: true
                text: info.text
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.WordWrap
                Accessible.ignored: true
            }
            Controls.Label {
                Layout.fillWidth: true
                visible: info.description !== ""
                text: info.description
                color: info.secondaryInk
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.WordWrap
                Accessible.ignored: true
            }
        }
        RowLayout {
            id: trailingSlot
            Layout.alignment: Qt.AlignVCenter
            spacing: MoUI.Tokens.space2
        }
    }
}
