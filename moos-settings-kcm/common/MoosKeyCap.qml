// SPDX-License-Identifier: GPL-2.0-or-later
// One key of a shortcut, drawn as a key. Latin key names in every language: that
// is what is printed on the keyboard in front of the reader.
import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Rectangle {
    id: keyCap

    property string keyName: ""

    implicitWidth: Math.max(Kirigami.Units.gridUnit * 1.75, keyText.implicitWidth + MoUI.Tokens.space3 * 2)
    implicitHeight: Kirigami.Units.gridUnit * 1.5
    radius: MoUI.Tokens.radiusSmall
    color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.07)
    border.width: 1
    border.color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.22)
    Accessible.ignored: true

    Controls.Label {
        id: keyText
        anchors.centerIn: parent
        text: keyCap.keyName
        textFormat: Text.PlainText
        font.weight: Font.DemiBold
    }
}
