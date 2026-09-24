// SPDX-License-Identifier: GPL-2.0-or-later
// A row that goes somewhere or starts something, in the native FormCard shape, with
// a MoOS glyph and secondary ink that stays readable (the stock description uses the
// DISABLED role, 1.6:1 on the light schemes).
import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard
import org.moos.ui as MoUI

FormCard.FormButtonDelegate {
    id: action

    property string glyph: "arrow"
    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)

    descriptionItem.color: action.secondaryInk
    Accessible.name: text
    Accessible.description: description

    leading: MoUI.SymbolIcon {
        symbol: MoUI.SymbolCatalog.resolve(action.glyph)
        foreground: Kirigami.Theme.textColor
        opacity: action.enabled ? 1 : MoUI.Tokens.disabledOpacity
        implicitWidth: Kirigami.Units.iconSizes.smallMedium
        implicitHeight: Kirigami.Units.iconSizes.smallMedium
    }
}
