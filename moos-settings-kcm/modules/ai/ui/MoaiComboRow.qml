// SPDX-License-Identifier: GPL-2.0-or-later
// A labelled drop-down in the native FormCard shape, stacked so a long model name fits.
// It always shows `shownIndex`, the index the PAGE says is chosen; picking another entry
// only asks (`picked`). If the page does not follow — a save that failed, a choice the
// service refused — the list returns to what the page shows instead of keeping the wish.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard
import org.moos.ui as MoUI

FormCard.AbstractFormDelegate {
    id: chooser

    property string label: ""
    property string description: ""
    property var options: []
    property int shownIndex: -1
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)

    signal picked(int index)

    focusPolicy: Qt.NoFocus
    hoverEnabled: false
    background: null
    Accessible.role: Accessible.Grouping
    Accessible.name: label

    contentItem: ColumnLayout {
        spacing: MoUI.Tokens.space2

        Controls.Label {
            Layout.fillWidth: true
            text: chooser.label
            color: Kirigami.Theme.textColor
            opacity: chooser.enabled ? 1 : MoUI.Tokens.disabledOpacity
            horizontalAlignment: Text.AlignLeft
            wrapMode: Text.WordWrap
            Accessible.ignored: true
        }
        Controls.ComboBox {
            id: box
            Layout.fillWidth: true
            model: chooser.options
            currentIndex: chooser.shownIndex
            enabled: chooser.enabled
            Accessible.name: chooser.label
            Accessible.description: chooser.description
            onActivated: index => {
                chooser.picked(index)
                box.currentIndex = Qt.binding(function () { return chooser.shownIndex })
            }
        }
        Controls.Label {
            Layout.fillWidth: true
            visible: chooser.description !== ""
            text: chooser.description
            color: chooser.secondaryInk
            horizontalAlignment: Text.AlignLeft
            wrapMode: Text.WordWrap
            Accessible.ignored: true
        }
    }
}
