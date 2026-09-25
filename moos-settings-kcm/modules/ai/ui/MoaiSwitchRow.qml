// SPDX-License-Identifier: GPL-2.0-or-later
// A switch inside a form that has a Save button. It shows `value`, the value Save will
// WRITE, and asks the page for the other one; nothing is written by flipping it. (The
// shared MoosSwitchRow is the other kind: it shows a measured state and acts at once.)
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard
import org.moos.ui as MoUI

FormCard.AbstractFormDelegate {
    id: toggleRow

    property string glyph: ""
    property string description: ""
    property bool value: false
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)

    signal toggledTo(bool wanted)

    Accessible.role: Accessible.CheckBox
    Accessible.checkable: true
    Accessible.checked: value
    Accessible.name: text
    Accessible.description: description
    Accessible.onPressAction: toggleRow.toggledTo(!toggleRow.value)
    Accessible.onToggleAction: toggleRow.toggledTo(!toggleRow.value)
    onClicked: toggledTo(!value)

    contentItem: RowLayout {
        spacing: MoUI.Tokens.space3

        MoUI.SymbolIcon {
            visible: toggleRow.glyph !== ""
            symbol: MoUI.SymbolCatalog.resolve(toggleRow.glyph)
            foreground: Kirigami.Theme.textColor
            opacity: toggleRow.enabled ? 1 : MoUI.Tokens.disabledOpacity
            implicitWidth: Kirigami.Units.iconSizes.smallMedium
            implicitHeight: Kirigami.Units.iconSizes.smallMedium
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: MoUI.Tokens.space1

            Controls.Label {
                Layout.fillWidth: true
                text: toggleRow.text
                color: Kirigami.Theme.textColor
                opacity: toggleRow.enabled ? 1 : MoUI.Tokens.disabledOpacity
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.WordWrap
                Accessible.ignored: true
            }
            Controls.Label {
                Layout.fillWidth: true
                visible: toggleRow.description !== ""
                text: toggleRow.description
                color: toggleRow.secondaryInk
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.WordWrap
                Accessible.ignored: true
            }
        }
        Controls.Switch {
            focusPolicy: Qt.NoFocus
            enabled: toggleRow.enabled
            checked: toggleRow.value
            Accessible.ignored: true
            onToggled: {
                toggleRow.toggledTo(checked)
                checked = Qt.binding(function () { return toggleRow.value })
            }
        }
    }
}
