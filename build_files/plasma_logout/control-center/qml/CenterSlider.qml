// SPDX-License-Identifier: GPL-2.0-or-later
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI
ColumnLayout {
    id: card
    required property var backend
    property string field: "volume"
    property string label: ""
    property string symbol: ""
    property real minimum: 0
    readonly property var measured: backend.state[field]
    readonly property bool known: typeof measured === "number" && Number.isFinite(measured)
    spacing: 0
    RowLayout {
        Layout.fillWidth: true
        Kirigami.Icon { source: card.symbol; implicitWidth: 22; implicitHeight: 22 }
        PC3.Label { text: card.label; Layout.fillWidth: true }
        PC3.Label { text: card.known ? Math.round(card.measured) + "%" : "—"; font.features: ({tnum:1}) }
    }
    PC3.Slider {
        id: slider
        objectName: "centerSlider_" + card.field
        Layout.fillWidth: true
        Layout.minimumHeight: 44
        from: card.minimum; to: 100; stepSize: 1
        value: card.known ? card.measured : card.minimum
        enabled: card.known && card.backend.ready && !card.backend.busy
        Accessible.name: card.label
        // Reading a new snapshot never submits it. Pointer/touch commit only
        // on release; keyboard movement commits through the native moved signal.
        property bool interactionChanged: false
        onMoved: {
            interactionChanged = true;
            if (!pressed) { card.backend.request(card.field, Math.round(value)); interactionChanged = false; }
        }
        onPressedChanged: if (!pressed && interactionChanged) {
            card.backend.request(card.field, Math.round(value)); interactionChanged = false;
        }
    }
}
