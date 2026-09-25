// SPDX-License-Identifier: GPL-2.0-or-later
// One measured fact inside a FormCard. A value that is missing is said in words
// ("Unknown"), never left blank and never guessed.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard
import org.moos.ui as MoUI

FormCard.AbstractFormDelegate {
    id: fact

    property string label: ""
    property string value: ""
    // A name the hardware or the registry gave (host, processor, digest, size) reads
    // left-to-right inside an Arabic sentence; anything else follows the language.
    property bool technical: false
    property color valueColor: Kirigami.Theme.textColor
    readonly property string unknownText: MoUI.Locale.local("غير معروف", "Unknown")
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)

    focusPolicy: Qt.NoFocus
    hoverEnabled: false
    background: null
    Accessible.role: Accessible.StaticText
    Accessible.name: label + ": " + (value || unknownText)

    contentItem: RowLayout {
        spacing: MoUI.Tokens.space4

        Controls.Label {
            Layout.preferredWidth: Kirigami.Units.gridUnit * 8
            text: fact.label
            color: fact.secondaryInk
            horizontalAlignment: Text.AlignLeft
            elide: Text.ElideRight
            Accessible.ignored: true
        }
        Controls.Label {
            Layout.fillWidth: true
            text: fact.value ? (fact.technical ? "\u2068" + fact.value + "\u2069" : fact.value)
                             : fact.unknownText
            textFormat: Text.PlainText
            color: fact.value ? fact.valueColor : fact.secondaryInk
            font.weight: Font.Medium
            horizontalAlignment: Text.AlignLeft
            wrapMode: Text.Wrap
            Accessible.ignored: true
        }
    }
}
