// SPDX-License-Identifier: GPL-2.0-or-later
// A switch that shows the MEASURED state. Flipping it asks for the other state
// (the page opens a fixed route) and the switch returns to what is measured until
// the owner's record says the change happened. A switch that shows a wish as a
// fact is how a cancelled confirmation looks like success.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard
import org.moos.ui as MoUI

FormCard.AbstractFormDelegate {
    id: row

    property string glyph: ""
    property string description: ""
    property bool on: false
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)

    signal requested(bool wanted)

    Accessible.role: Accessible.CheckBox
    Accessible.checkable: true
    Accessible.checked: on
    Accessible.name: text
    Accessible.description: description
    Accessible.onPressAction: row.requested(!row.on)
    Accessible.onToggleAction: row.requested(!row.on)
    onClicked: requested(!on)

    contentItem: RowLayout {
        spacing: MoUI.Tokens.space3

        MoUI.SymbolIcon {
            visible: row.glyph !== ""
            symbol: MoUI.SymbolCatalog.resolve(row.glyph)
            foreground: Kirigami.Theme.textColor
            opacity: row.enabled ? 1 : MoUI.Tokens.disabledOpacity
            implicitWidth: Kirigami.Units.iconSizes.smallMedium
            implicitHeight: Kirigami.Units.iconSizes.smallMedium
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: MoUI.Tokens.space1

            Controls.Label {
                Layout.fillWidth: true
                text: row.text
                color: Kirigami.Theme.textColor
                opacity: row.enabled ? 1 : MoUI.Tokens.disabledOpacity
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.WordWrap
                Accessible.ignored: true
            }
            Controls.Label {
                Layout.fillWidth: true
                visible: row.description !== ""
                text: row.description
                color: row.secondaryInk
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.WordWrap
                Accessible.ignored: true
            }
        }
        Controls.Switch {
            id: toggle
            focusPolicy: Qt.NoFocus
            enabled: row.enabled
            checked: row.on
            Accessible.ignored: true
            onToggled: {
                row.requested(checked)
                checked = Qt.binding(function() { return row.on })
            }
        }
    }
}
