import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window

// Home: every device in the house, room by room, by the owner's own names, with what each one can
// really do. A name, a room or a voice name set here is set IN Home Assistant (every app and Mira
// use it from then on); a control shows only what the device supports and says "done" only after
// the device reads back.
PageFrame {
    id: hp
    icon: "home"
    title: mira.s.hm_title
    subtitle: mira.s.hm_sub
    accent: Theme.cyan
    busy: !st.ready

    readonly property var page: mira.homePage
    readonly property var st: page ? page.state : ({})
    readonly property bool wide: contentWidth >= 820
    property string editing: ""            // the entity being renamed

    readonly property bool onScreen: Window.visibility !== Window.Hidden && Window.visibility !== Window.Minimized
    property bool wasHidden: false
    onOnScreenChanged: {
        if (!page) return
        if (!onScreen) { wasHidden = true; page.hidden() }
        else if (wasHidden) { wasHidden = false; page.resume() }
    }
    Component.onDestruction: if (page) page.hidden()

    actions: [
        StatusPill {
            visible: !!hp.st.sample
            anchors.verticalCenter: parent.verticalCenter
            text: mira.s.hm_sample; tone: "warn"; icon: "alert"
        },
        StatusPill {
            visible: hp.st.linked === true && !!hp.st.counts
            anchors.verticalCenter: parent.verticalCenter
            text: hp.st.counts ? (hp.st.counts.online + "/" + hp.st.counts.devices + " " + mira.s.hm_online + " · "
                                  + hp.st.counts.rooms + " " + mira.s.hm_rooms) : ""
            tone: "ok"; icon: "home"
        },
        IconButton {
            anchors.verticalCenter: parent.verticalCenter
            iconName: "bulb"; tip: mira.s.hm_lights_page
            onClicked: hp.page.openLumen()
        },
        IconButton {
            anchors.verticalCenter: parent.verticalCenter
            iconName: "external"; tip: mira.s.hm_open_ha
            onClicked: hp.page.openHomeAssistant()
        },
        IconButton {
            anchors.verticalCenter: parent.verticalCenter
            iconName: "refresh"; tip: mira.s.refresh || ""
            onClicked: hp.page.refresh()
        }
    ]

    // ── not linked yet: make this computer the hub, finish its first run, or link one that exists ──
    readonly property var hubState: st.hub || ({})
    property bool haveOwn: false
    Card {
        visible: hp.st.linked === false && !hp.haveOwn && (hp.hubState.stage === "none" || hp.hubState.stage === undefined)
        icon: "home"; title: mira.s.hm_hub_title; subtitle: mira.s.hm_hub_sub; accent: Theme.cyan
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            PillButton { text: mira.s.hm_hub_setup; iconName: "download"; primary: true
                         enabled: (hp.st.busy || "") === ""; onClicked: hp.page.setupHub() }
            PillButton { text: mira.s.hm_hub_have; onClicked: hp.haveOwn = true }
            Item { Layout.fillWidth: true }
        }
    }
    Card {
        visible: hp.st.linked === false && (hp.hubState.stage === "installed" || hp.hubState.stage === "starting")
        icon: "home"; title: mira.s.hm_hub_title; accent: Theme.cyan
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Rectangle {
                width: 18; height: 18; radius: 9; color: "transparent"
                border.width: 2; border.color: Theme.cyan
                Rectangle { width: 6; height: 6; radius: 3; color: Theme.cyan; anchors.centerIn: parent }
                SequentialAnimation on opacity {
                    running: mira.motion && parent.visible; loops: Animation.Infinite
                    NumberAnimation { to: 0.3; duration: 700 } NumberAnimation { to: 1; duration: 700 }
                }
            }
            T { Layout.fillWidth: true; text: mira.s.hm_hub_starting; color: Theme.ink2 }
        }
    }
    Card {
        visible: hp.st.linked === false && hp.hubState.stage === "onboarding"
        icon: "user"; title: mira.s.hm_hub_account; subtitle: mira.s.hm_hub_account_sub; accent: Theme.cyan
        GridLayout {
            Layout.fillWidth: true
            columns: hp.wide ? 3 : 1
            columnSpacing: 8; rowSpacing: 8
            MiraField { id: ownerName; Layout.fillWidth: true; placeholderText: mira.s.hm_hub_name; Accessible.name: mira.s.hm_hub_name }
            MiraField { id: ownerUser; Layout.fillWidth: true; placeholderText: mira.s.hm_hub_user; Accessible.name: mira.s.hm_hub_user
                        validator: RegularExpressionValidator { regularExpression: /[a-z0-9._-]{0,40}/ } }
            MiraField { id: ownerPass; Layout.fillWidth: true; echoMode: TextInput.Password; placeholderText: mira.s.hm_hub_pass; Accessible.name: mira.s.hm_hub_pass }
        }
        PillButton {
            text: mira.s.hm_hub_create; primary: true; iconName: "check"
            enabled: ownerName.text.trim().length > 0 && ownerUser.text.length > 1 && ownerPass.text.length >= 8 && (hp.st.busy || "") === ""
            onClicked: { hp.page.onboard(ownerName.text, ownerUser.text, ownerPass.text); ownerPass.clear() }
        }
    }
    Card {
        visible: hp.st.linked === false && (hp.haveOwn || hp.hubState.stage === "token")
        icon: "link"; title: mira.s.hm_link_title; subtitle: mira.s.hm_link_sub; accent: Theme.cyan
        T {
            Layout.fillWidth: true
            text: hp.st.probe && hp.st.probe.reachable ? mira.s.hm_link_found : mira.s.hm_link_none
            color: Theme.ink2; font.pixelSize: Theme.small
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            MiraField { id: urlField; Layout.preferredWidth: 240; placeholderText: "http://127.0.0.1:8123"; Accessible.name: mira.s.hm_url }
            MiraField { id: tokenField; Layout.fillWidth: true; echoMode: TextInput.Password; placeholderText: mira.s.hm_token; Accessible.name: mira.s.hm_token }
            PillButton { text: mira.s.hm_connect; primary: true; enabled: tokenField.text.length > 40
                         onClicked: { hp.page.link(tokenField.text, urlField.text); tokenField.clear() } }
        }
        PillButton { text: mira.s.hm_open_ha; iconName: "external"; onClicked: hp.page.openHomeAssistant() }
    }

    // ── found on the network ──
    Glass {
        Layout.fillWidth: true
        visible: (hp.st.discovered || []).length > 0
        Layout.preferredHeight: discRow.implicitHeight + 24
        radius: 18
        tint: Qt.rgba(0.21, 0.85, 0.96, 0.08)
        edge: Qt.rgba(0.21, 0.85, 0.96, 0.35)
        RowLayout {
            id: discRow
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 14 }
            spacing: 10
            Icon { name: "sparkle"; size: 20; color: Theme.cyan }
            T {
                Layout.fillWidth: true
                text: mira.s.hm_discovered + ": " + (hp.st.discovered || []).map(function(d) { return d.title }).join("، ")
                font.pixelSize: Theme.small
            }
            PillButton { text: mira.s.hm_add; size: Theme.small; implicitHeight: 30; onClicked: hp.page.openHomeAssistant() }
        }
    }

    StatusPill {
        visible: !!hp.st.note && !!hp.st.note.text && (hp.st.busy || "") === ""
        text: (hp.st.note && hp.st.note.text) || ""
        tone: hp.st.note ? (hp.st.note.status === "ok" ? "ok" : hp.st.note.status === "error" ? "error" : "warn") : "info"
        icon: hp.st.note && hp.st.note.status === "ok" ? "check" : "alert"
    }

    // ── room by room ──
    Repeater {
        model: hp.page ? hp.page.rooms : []
        delegate: ColumnLayout {
            id: roomBox
            required property var modelData
            Layout.fillWidth: true
            spacing: 10
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Rectangle {
                    width: 34; height: 34; radius: 11
                    color: Qt.rgba(0.21, 0.85, 0.96, 0.12)
                    Icon { anchors.centerIn: parent; name: "door"; size: 18; color: Theme.cyan }
                }
                T { text: roomBox.modelData.name || mira.s.hm_no_room; font.pixelSize: Theme.title; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                T { text: roomBox.modelData.on + " " + mira.s.hm_on + " · " + roomBox.modelData.devices.length + " " + mira.s.hm_devices
                    color: Theme.ink3; font.pixelSize: Theme.small; wrapMode: Text.NoWrap }
                Item { Layout.fillWidth: true }
            }
            GridLayout {
                Layout.fillWidth: true
                columns: hp.wide ? 2 : 1
                columnSpacing: 12; rowSpacing: 12
                Repeater {
                    model: roomBox.modelData.devices
                    delegate: DeviceCard {}
                }
            }
        }
    }

    component DeviceCard: Glass {
        id: card
        required property var modelData
        readonly property bool edit: hp.editing === modelData.entity_id
        readonly property color accent: modelData.kind === "tv" ? Theme.cyan : modelData.kind === "light" ? Theme.amber
                                      : modelData.kind === "scene" ? Theme.violet : modelData.kind === "sensor" ? Theme.mint : Theme.rose
        Layout.fillWidth: true
        Layout.preferredWidth: 1
        Layout.alignment: Qt.AlignTop
        Layout.preferredHeight: body.implicitHeight + 28
        radius: 18
        opacity: modelData.available ? 1 : 0.55
        lit: modelData.on
        tint: modelData.on ? Qt.rgba(accent.r * 0.14 + 0.05, accent.g * 0.14 + 0.06, accent.b * 0.14 + 0.12, 0.82) : Theme.glass

        ColumnLayout {
            id: body
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Rectangle {
                    width: 40; height: 40; radius: 13
                    color: Qt.rgba(card.accent.r, card.accent.g, card.accent.b, card.modelData.on ? 0.24 : 0.09)
                    Icon { anchors.centerIn: parent; name: card.modelData.icon; size: 20
                           color: card.modelData.on ? card.accent : Theme.ink3 }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1
                    visible: !card.edit
                    T { text: card.modelData.name; font.pixelSize: Theme.body; font.weight: Font.DemiBold
                        Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                    T {
                        Layout.fillWidth: true
                        text: (!card.modelData.available ? mira.s.hm_unavailable
                               : card.modelData.kind === "sensor" ? card.modelData.value + " " + card.modelData.unit
                               : card.modelData.on ? mira.s.hm_on + (card.modelData.level >= 0 ? " · " + card.modelData.level + "%" : "")
                               : (card.modelData.power ? mira.s.hm_off : ""))
                              + (card.modelData.detail ? " · " + card.modelData.detail : "")
                        font.pixelSize: Theme.small; color: Theme.ink3; elide: Text.ElideRight; wrapMode: Text.NoWrap
                    }
                }
                MiraField {
                    id: nameField
                    visible: card.edit
                    Layout.fillWidth: true
                    text: card.modelData.name
                    Accessible.name: mira.s.hm_rename
                    onAccepted: saveBtn.clicked()
                }
                IconButton {
                    visible: !card.edit
                    iconName: "pencil"; tip: mira.s.hm_rename; diameter: 32
                    onClicked: { hp.editing = card.modelData.entity_id; nameField.forceActiveFocus(); nameField.selectAll() }
                }
                MiraSwitch {
                    visible: card.modelData.power && !card.edit
                    enabled: card.modelData.available && (hp.st.busy || "") === ""
                    checked: card.modelData.on
                    accent: card.accent
                    Accessible.name: card.modelData.name
                    onToggled: { const want = checked; checked = Qt.binding(function() { return card.modelData.on }); hp.page.setPower(card.modelData.entity_id, want) }
                }
            }
            // what it can do, in words
            T {
                Layout.fillWidth: true
                visible: card.modelData.summary !== "" && !card.edit
                text: card.modelData.summary
                font.pixelSize: Theme.tiny + 1; color: Theme.ink2
                maximumLineCount: 2; elide: Text.ElideRight
            }
            // its other names, as chips
            Flow {
                Layout.fillWidth: true
                visible: card.modelData.aliases.length > 0 && !card.edit
                spacing: 5
                Repeater {
                    model: card.modelData.aliases
                    delegate: Rectangle {
                        required property string modelData
                        height: 22; radius: 11; width: aliasText.implicitWidth + 16
                        color: Qt.rgba(1, 1, 1, 0.06); border.width: 1; border.color: Theme.hairline
                        T { id: aliasText; anchors.centerIn: parent; text: "«" + modelData + "»"; font.pixelSize: Theme.tiny; color: Theme.ink2; wrapMode: Text.NoWrap }
                    }
                }
            }
            // quick controls the device really has
            RowLayout {
                Layout.fillWidth: true
                visible: !card.edit && card.modelData.available && (card.modelData.volume_step || card.modelData.activate || card.modelData.kind === "light")
                spacing: 6
                // a TV that has no volume level (only steps) gets steps, never a slider it would ignore
                Rectangle {
                    visible: card.modelData.volume_step
                    implicitHeight: 32; implicitWidth: volRow.implicitWidth + 8; radius: 16
                    color: Qt.rgba(1, 1, 1, 0.045); border.width: 1; border.color: Theme.hairline
                    Row {
                        id: volRow; anchors.centerIn: parent; spacing: 2
                        AbstractButton {
                            width: 30; height: 28; hoverEnabled: true
                            Accessible.name: mira.s.hm_vol_down
                            background: Rectangle { radius: 14; color: parent.hovered ? Qt.rgba(1, 1, 1, 0.09) : "transparent" }
                            contentItem: T { text: "−"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 18 }
                            onClicked: hp.page.press(card.modelData.entity_id, "volume_down")
                        }
                        Icon { name: "volume"; size: 16; color: Theme.ink2; anchors.verticalCenter: parent.verticalCenter }
                        AbstractButton {
                            width: 30; height: 28; hoverEnabled: true
                            Accessible.name: mira.s.hm_vol_up
                            background: Rectangle { radius: 14; color: parent.hovered ? Qt.rgba(1, 1, 1, 0.09) : "transparent" }
                            contentItem: T { text: "+"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 18 }
                            onClicked: hp.page.press(card.modelData.entity_id, "volume_up")
                        }
                    }
                }
                IconButton { visible: card.modelData.kind === "tv"; iconName: "home"; tip: mira.s.hm_tv_home; diameter: 32
                             onClicked: hp.page.press(card.modelData.entity_id, "home") }
                PillButton { visible: card.modelData.activate; text: mira.s.hm_activate; iconName: "play"; size: Theme.small; implicitHeight: 30
                             onClicked: hp.page.press(card.modelData.entity_id, "activate") }
                PillButton { visible: card.modelData.kind === "light"; text: mira.s.hm_lights_page; iconName: "drop"; size: Theme.small; implicitHeight: 30
                             onClicked: hp.page.openLumen() }
                Item { Layout.fillWidth: true }
            }
            // renaming: the name above, the room and the voice names here
            ColumnLayout {
                Layout.fillWidth: true
                visible: card.edit
                spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    T { text: mira.s.hm_room; font.pixelSize: Theme.small; color: Theme.ink2; wrapMode: Text.NoWrap }
                    ComboBox {
                        id: roomBoxPick
                        Layout.fillWidth: true
                        editable: true
                        model: (hp.page ? hp.page.areas : []).map(function(a) { return a.name })
                        Component.onCompleted: { const i = find(card.modelData.room); currentIndex = i; if (i < 0) editText = card.modelData.room }
                        font.family: Theme.font
                    }
                }
                MiraField { id: aliasField; Layout.fillWidth: true; placeholderText: mira.s.hm_aliases_hint
                            text: card.modelData.aliases.join("، "); Accessible.name: mira.s.hm_aliases }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }
                    PillButton { text: mira.s.hm_cancel; size: Theme.small; implicitHeight: 32; onClicked: hp.editing = "" }
                    PillButton {
                        id: saveBtn
                        text: mira.s.hm_save; primary: true; size: Theme.small; implicitHeight: 32
                        onClicked: {
                            const id = card.modelData.entity_id
                            if (nameField.text.trim() !== card.modelData.name) hp.page.rename(id, nameField.text.trim())
                            const room = roomBoxPick.editText.trim()
                            if (room !== card.modelData.room) hp.page.moveTo(id, room)
                            if (aliasField.text.trim() !== card.modelData.aliases.join("، ")) hp.page.setAliases(id, aliasField.text)
                            hp.editing = ""
                        }
                    }
                }
            }
        }
    }
}
