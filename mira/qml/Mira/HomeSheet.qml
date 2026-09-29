import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Every real Home Assistant device with only the controls its state says it supports.
// A control shows the device's read-back state; a request never flips the switch by itself.
Item {
    id: home
    property string expanded: ""
    readonly property var swatches: [
        { name: "pink", c: "#FF5AAF" }, { name: "purple", c: "#9150FF" }, { name: "blue", c: "#376EFF" },
        { name: "green", c: "#23D282" }, { name: "yellow", c: "#FFD241" }, { name: "orange", c: "#FF7D23" }, { name: "red", c: "#FF3746" } ]

    ColumnLayout {
        anchors.fill: parent
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Rectangle {
                Layout.preferredHeight: 34; radius: 17
                Layout.preferredWidth: sumRow.implicitWidth + 24
                color: Qt.rgba(1, 1, 1, 0.04); border.width: 1; border.color: Theme.hairline
                Row { id: sumRow; anchors.centerIn: parent; spacing: 6
                    Rectangle { width: 7; height: 7; radius: 3.5; color: Theme.ok; anchors.verticalCenter: parent.verticalCenter }
                    T { text: mira.home.available + " / " + mira.home.total + " " + mira.s.devices_available; font.pixelSize: Theme.small; color: Theme.ink2; wrapMode: Text.NoWrap } }
            }
            Item { Layout.fillWidth: true }
            PillButton { text: mira.s.all_on; iconName: "sun"; size: Theme.small; implicitHeight: 34; enabled: mira.home.lights_available > 0 && !mira.home.busy; onClicked: mira.allLights(true) }
            PillButton { text: mira.s.all_off; iconName: "moon"; size: Theme.small; implicitHeight: 34; enabled: mira.home.lights_available > 0 && !mira.home.busy; onClicked: mira.allLights(false) }
            IconButton { iconName: "refresh"; tip: mira.s.refresh; diameter: 34; onClicked: mira.refreshHome() }
            IconButton { iconName: "external"; tip: mira.s.open_ha; diameter: 34; onClicked: mira.openHomeAssistant() }
        }

        T {
            Layout.fillWidth: true
            visible: text !== ""
            text: mira.home.busy ? mira.s.checking : (mira.home.message || "")
            color: mira.home.busy ? Theme.amber : Theme.ink3
            font.pixelSize: Theme.small
        }

        // pairing, only when no link exists
        RowLayout {
            Layout.fillWidth: true
            visible: !mira.home.linked
            spacing: 8
            MiraField { id: token; Layout.fillWidth: true; echoMode: TextInput.Password; placeholderText: mira.s.ha_token }
            PillButton { text: mira.s.ha_save; primary: true; enabled: token.text.length > 40; onClicked: { mira.saveHomeToken(token.text); token.clear() } }
        }

        T {
            Layout.fillWidth: true
            visible: mira.deviceModel.count === 0
            text: mira.s.no_devices
            color: Theme.ink3
            horizontalAlignment: Text.AlignHCenter
            topPadding: 40
        }

        Flickable {
            id: grid
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentHeight: cards.implicitHeight + 8
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { width: 6 }
            readonly property int cols: width > 520 ? 2 : 1
            readonly property real cellWidth: Math.floor((width - (cols - 1) * 10) / cols)
            Flow {
                id: cards
                width: grid.width
                spacing: 10
                Repeater {
                    model: mira.deviceModel
                    delegate: Item {
                id: cell
                required property string entity_id
                required property string name
                required property string domain
                required property string state
                required property bool available
                required property bool is_on
                required property int brightness
                required property bool color_capable
                required property bool dimmable
                required property string rgb
                required property int volume
                required property bool volume_capable
                required property bool play_capable
                required property bool pause_capable
                required property bool on_capable
                required property bool off_capable
                required property bool group
                width: grid.cellWidth; height: card.height
                readonly property color accent: domain === "media_player" ? Theme.cyan : (rgb !== "" && is_on ? rgb : Theme.amber)

                Glass {
                    id: card
                    width: parent.width
                    height: cardBody.implicitHeight + 28
                    radius: 18
                    opacity: cell.available ? 1 : 0.5
                    tint: cell.is_on && cell.available ? Qt.rgba(cell.accent.r * 0.18 + 0.05, cell.accent.g * 0.18 + 0.05, cell.accent.b * 0.18 + 0.11, 0.8) : Theme.glass
                    lit: cell.is_on && cell.available

                    ColumnLayout {
                        id: cardBody
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
                        spacing: 10
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Rectangle {
                                width: 38; height: 38; radius: 12
                                color: Qt.rgba(cell.accent.r, cell.accent.g, cell.accent.b, cell.is_on ? 0.22 : 0.07)
                                Icon { anchors.centerIn: parent; size: 19
                                       name: cell.domain === "media_player" ? "tv" : cell.domain === "switch" ? "power" : "bulb"
                                       color: cell.is_on && cell.available ? cell.accent : Theme.ink3 }
                            }
                            Column {
                                Layout.fillWidth: true
                                T { width: parent.width; text: cell.name; font.pixelSize: Theme.body; font.weight: Font.DemiBold; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                                T { width: parent.width; text: (!cell.available ? mira.s.unavailable : (mira.s["state_" + cell.state] || cell.state)) + (cell.group ? " · " + (mira.lang === "ar" ? "مجموعة" : "group") : "")
                                    + (cell.brightness >= 0 && cell.is_on ? " · " + cell.brightness + "%" : "")
                                    font.pixelSize: Theme.small; color: Theme.ink3; wrapMode: Text.NoWrap }
                            }
                            MiraSwitch {
                                accent: cell.accent
                                enabled: cell.available && (cell.is_on ? cell.off_capable : cell.on_capable) && !mira.home.busy
                                checked: cell.is_on
                                Accessible.name: cell.name
                                onToggled: { const want = checked; checked = Qt.binding(function() { return cell.is_on }); mira.homeAction(cell.entity_id, want ? "turn_on" : "turn_off", -1, "") }
                            }
                        }
                        // brightness
                        RowLayout {
                            Layout.fillWidth: true
                            visible: cell.domain === "light" && cell.dimmable
                            spacing: 8
                            Icon { name: "sun"; size: 16; color: Theme.ink3 }
                            MiraSlider {
                                Layout.fillWidth: true
                                from: 1; to: 100; stepSize: 1
                                value: cell.brightness > 0 ? cell.brightness : 50
                                accent: cell.accent
                                enabled: cell.available && !mira.home.busy
                                onPressedChanged: if (!pressed) mira.homeAction(cell.entity_id, "brightness", value, "")
                            }
                        }
                        // colours
                        Row {
                            visible: cell.color_capable
                            spacing: 8
                            Repeater {
                                model: home.swatches
                                delegate: Rectangle {
                                    required property var modelData
                                    width: 24; height: 24; radius: 12
                                    color: modelData.c
                                    border.width: sw.hovered ? 2 : 1
                                    border.color: sw.hovered ? "white" : Qt.rgba(1, 1, 1, 0.25)
                                    opacity: cell.available && !mira.home.busy ? 1 : 0.35
                                    HoverHandler { id: sw; cursorShape: Qt.PointingHandCursor }
                                    TapHandler { enabled: cell.available && !mira.home.busy; onTapped: mira.homeAction(cell.entity_id, "color", -1, modelData.name) }
                                    Accessible.role: Accessible.Button
                                    Accessible.name: modelData.name
                                }
                            }
                        }
                        // media
                        RowLayout {
                            Layout.fillWidth: true
                            visible: cell.domain === "media_player"
                            spacing: 8
                            IconButton { iconName: "play"; tip: mira.s.play; diameter: 34; visible: cell.play_capable; enabled: cell.available; onClicked: mira.homeAction(cell.entity_id, "media_play", -1, "") }
                            IconButton { iconName: "pause"; tip: mira.s.pause; diameter: 34; visible: cell.pause_capable; enabled: cell.available; onClicked: mira.homeAction(cell.entity_id, "media_pause", -1, "") }
                            Icon { name: "volume"; size: 16; color: Theme.ink3; visible: cell.volume_capable }
                            MiraSlider {
                                Layout.fillWidth: true
                                visible: cell.volume_capable
                                from: 0; to: 100; stepSize: 1
                                value: cell.volume >= 0 ? cell.volume : 0
                                enabled: cell.available && cell.volume >= 0
                                onPressedChanged: if (!pressed) mira.homeAction(cell.entity_id, "volume", value, "")
                            }
                        }
                    }
                }
            }
                }
            }
        }
    }
}
