// SPDX-License-Identifier: GPL-2.0-or-later
// Shown when a button's route could not be handed to MoOS's router. A button that
// silently does nothing is the defect this exists for.
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.InlineMessage {
    id: routeNotice

    property string message: ""

    Layout.fillWidth: true
    visible: message !== ""
    type: Kirigami.MessageType.Error
    text: message
}
