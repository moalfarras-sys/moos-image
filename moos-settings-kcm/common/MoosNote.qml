// SPDX-License-Identifier: GPL-2.0-or-later
// A sentence of explanation under a section, in readable secondary ink.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Controls.Label {
    id: note

    readonly property color secondaryInk: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.72)

    Layout.fillWidth: true
    leftPadding: Kirigami.Units.largeSpacing
    rightPadding: Kirigami.Units.largeSpacing
    topPadding: Kirigami.Units.smallSpacing
    color: note.secondaryInk
    horizontalAlignment: Text.AlignLeft
    wrapMode: Text.WordWrap
}
