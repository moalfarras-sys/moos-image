// SPDX-License-Identifier: GPL-2.0-or-later
// One fact a person checks at a glance: signed, up to date, rollback ready.
// The label is full-strength ink; only the tint and the glyph carry the tone.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

MoUI.Surface {
    id: chip

    property string glyph: "check"
    property string label: ""
    // positive | warning | negative | neutral
    property string tone: "neutral"
    readonly property color toneColor: tone === "positive" ? Kirigami.Theme.positiveTextColor
        : tone === "warning" ? Kirigami.Theme.neutralTextColor
        : tone === "negative" ? Kirigami.Theme.negativeTextColor
        : Kirigami.Theme.highlightColor

    implicitHeight: Math.max(Kirigami.Units.gridUnit * 1.5, chipRow.implicitHeight + MoUI.Tokens.space1 * 2)
    implicitWidth: chipRow.implicitWidth + MoUI.Tokens.space3 * 2
    radius: height / 2
    surfaceColor: Qt.alpha(toneColor, 0.14)
    inkColor: Kirigami.Theme.textColor
    accentColor: toneColor
    border.color: Qt.alpha(toneColor, 0.42)
    Accessible.role: Accessible.StaticText
    Accessible.name: label

    RowLayout {
        id: chipRow
        anchors.centerIn: parent
        spacing: MoUI.Tokens.space1 + 2

        MoUI.SymbolIcon {
            symbol: MoUI.SymbolCatalog.resolve(chip.glyph)
            foreground: chip.toneColor
            implicitWidth: MoUI.Tokens.iconSmall
            implicitHeight: MoUI.Tokens.iconSmall
        }
        Controls.Label {
            text: chip.label
            textFormat: Text.PlainText
            color: Kirigami.Theme.textColor
            font.weight: Font.DemiBold
            Accessible.ignored: true
        }
    }
}
