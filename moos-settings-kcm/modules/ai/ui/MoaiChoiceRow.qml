// SPDX-License-Identifier: GPL-2.0-or-later
// One choice of a set (a permission tier), in the native FormCard shape: a radio button,
// the choice's name, and its consequence in readable secondary ink. `chosen` is what the
// page will SAVE, never what the service already holds; the page says which is which.
// A risky choice turns its name the negative colour once it is picked.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard
import org.moos.ui as MoUI

FormCard.AbstractFormDelegate {
    id: choice

    property string description: ""
    property bool chosen: false
    property bool risky: false
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)

    signal choose()

    Accessible.role: Accessible.RadioButton
    Accessible.checkable: true
    Accessible.checked: chosen
    Accessible.name: text
    Accessible.description: description
    Accessible.onPressAction: choice.choose()
    onClicked: choose()

    contentItem: RowLayout {
        spacing: MoUI.Tokens.space3

        Controls.RadioButton {
            Layout.alignment: Qt.AlignTop
            checked: choice.chosen
            enabled: choice.enabled
            focusPolicy: Qt.NoFocus
            Accessible.ignored: true
            onToggled: {
                choice.choose()
                checked = Qt.binding(function () { return choice.chosen })
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: MoUI.Tokens.space1

            Controls.Label {
                Layout.fillWidth: true
                text: choice.text
                color: choice.risky && choice.chosen ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.textColor
                opacity: choice.enabled ? 1 : MoUI.Tokens.disabledOpacity
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.WordWrap
                Accessible.ignored: true
            }
            Controls.Label {
                Layout.fillWidth: true
                visible: choice.description !== ""
                text: choice.description
                color: choice.secondaryInk
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.WordWrap
                Accessible.ignored: true
            }
        }
    }
}
