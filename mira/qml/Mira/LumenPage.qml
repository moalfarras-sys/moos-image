import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window

// Lumen — every light in the house and the computer, as one page. The stage shows each light in its
// own colour; what the owner picks there (or with a room/group chip) is what every control below
// acts on: power, colour, white, brightness, effects, scenes, Screen Sync. Nothing here claims a
// change before the engine reads it back (a PC header says "accepted by the controller").
PageFrame {
    id: lp
    icon: "bulb"
    title: mira.s.lu_title
    subtitle: mira.s.lu_sub
    accent: Theme.violet
    busy: !st.ready && st.error === ""

    readonly property var page: mira.lumenPage
    readonly property var st: page ? page.state : ({})
    // the long lists are their own properties (pages/lumen.py): they change only when a light does
    readonly property var lights: (page ? page.lights : []).filter(function(l) { return !l.group })
    readonly property var rooms: page ? page.rooms : []
    readonly property var groups: page ? page.groups : []
    readonly property var scenes: page ? page.scenes : []
    readonly property var sync: page ? page.sync : ({})
    readonly property bool wide: contentWidth >= 860
    property real clock: 0                // the window's shared clock (Main.qml), for living lights
    property var picked: []               // light ids; empty = every light
    property string chip: "all"           // which chip made the pick
    readonly property var targets: picked.length ? picked : lights.map(function(l) { return l.id })
    readonly property var focusLight: {
        const ids = targets
        for (let i = 0; i < lights.length; i++)
            if (ids.indexOf(lights[i].id) >= 0 && lights[i].on) return lights[i]
        for (let j = 0; j < lights.length; j++)
            if (ids.indexOf(lights[j].id) >= 0) return lights[j]
        return null
    }
    readonly property var pcLights: lights.filter(function(l) { return l.source === "pc" })
    readonly property var effectChoices: {
        const seen = {}, out = []
        lights.forEach(function(l) {
            if (targets.indexOf(l.id) < 0 || l.source === "pc") return
            ;(l.effect_names || []).forEach(function(e) { if (!seen[e.id]) { seen[e.id] = 1; out.push(e) } })
        })
        return out
    }
    // the room's colour: the lit lights, mixed by how bright each one is
    readonly property color ambient: {
        let r = 0, g = 0, b = 0, w = 0
        lights.forEach(function(l) {
            if (!l.on) return
            const c = Qt.color(l.hex), k = Math.max(0.15, l.level / 100)
            r += c.r * k; g += c.g * k; b += c.b * k; w += k
        })
        return w > 0 ? Qt.rgba(r / w, g / w, b / w, 1) : Qt.rgba(0.35, 0.38, 0.6, 1)
    }
    readonly property real litShare: {
        const online = lights.filter(function(l) { return l.online }).length
        return online ? lights.filter(function(l) { return l.on }).length / online : 0
    }

    component Chip: AbstractButton {
        id: c
        property bool active: false
        property string glyph: ""
        hoverEnabled: true
        implicitHeight: 34
        implicitWidth: chipRow.implicitWidth + 26
        background: Rectangle {
            radius: 17
            color: c.active ? Qt.rgba(0.61, 0.48, 1, 0.24) : c.hovered ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.04)
            border.width: 1
            border.color: c.active ? Qt.rgba(0.75, 0.65, 1, 0.65) : c.visualFocus ? Theme.cyan : Theme.hairline
            Behavior on color { ColorAnimation { duration: Theme.fast } }
        }
        contentItem: Item {
            Row {
                id: chipRow; anchors.centerIn: parent; spacing: 6
                Icon { visible: c.glyph !== ""; name: c.glyph || "sparkle"; size: 15; color: c.active ? Theme.ink : Theme.ink2; anchors.verticalCenter: parent.verticalCenter }
                T { text: c.text; font.pixelSize: Theme.small; wrapMode: Text.NoWrap; color: c.active ? Theme.ink : Theme.ink2; anchors.verticalCenter: parent.verticalCenter }
            }
        }
    }

    function pick(ids, chipName) { picked = ids; chip = chipName }
    function toggle(id) {
        const next = picked.slice()
        const at = next.indexOf(id)
        if (at >= 0) next.splice(at, 1); else next.push(id)
        picked = next
        chip = next.length ? "" : "all"
    }
    function nameOf(id) {
        for (let i = 0; i < lights.length; i++) if (lights[i].id === id) return lights[i].name
        return id
    }

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
            visible: !!lp.st.sample
            anchors.verticalCenter: parent.verticalCenter
            text: mira.s.lu_sample; tone: "warn"; icon: "alert"
        },
        StatusPill {
            visible: lp.st.ready
            anchors.verticalCenter: parent.verticalCenter
            text: (lp.st.counts ? lp.st.counts.on : 0) + " " + mira.s.lu_lights_on + " · "
                  + (lp.st.counts ? lp.st.counts.online : 0) + "/" + (lp.st.counts ? lp.st.counts.lights : 0)
            tone: lp.st.counts && lp.st.counts.online < lp.st.counts.lights ? "warn" : "ok"; icon: "bulb"
        },
        IconButton {
            anchors.verticalCenter: parent.verticalCenter
            iconName: "refresh"; tip: mira.s.pcp_refresh || ""
            onClicked: if (lp.page) lp.page.refresh()
        }
    ]

    // ── the engine is not answering ──
    Glass {
        Layout.fillWidth: true
        visible: lp.st.error !== undefined && lp.st.error !== "" && !lp.st.ready
        Layout.preferredHeight: offRow.implicitHeight + 28
        radius: 18
        tint: Qt.rgba(0.30, 0.07, 0.14, 0.55)
        edge: Qt.rgba(1, 0.36, 0.48, 0.45)
        RowLayout {
            id: offRow
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 16 }
            spacing: 12
            Icon { name: "alert"; size: 22; color: Theme.danger }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 2
                T { text: mira.s.lu_unreachable; font.weight: Font.DemiBold; Layout.fillWidth: true }
                T { text: mira.s.lu_unreachable_hint; font.pixelSize: Theme.small; color: Theme.ink3; Layout.fillWidth: true }
            }
        }
    }

    // ── the stage: every light in its own colour ──
    Glass {
        id: stage
        Layout.fillWidth: true
        Layout.preferredHeight: Math.max(210, rooms.implicitHeight + 64)
        radius: 26
        tint: Qt.rgba(0.03 + lp.ambient.r * 0.10 * lp.litShare, 0.035 + lp.ambient.g * 0.08 * lp.litShare,
                      0.09 + lp.ambient.b * 0.12 * lp.litShare, 0.92)
        clip: true
        // the room's own glow, rising from the floor of the stage
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: parent.height * 0.9
            radius: stage.radius
            opacity: 0.25 + 0.55 * lp.litShare
            gradient: Gradient {
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 1.0; color: Qt.rgba(lp.ambient.r, lp.ambient.g, lp.ambient.b, 0.38) }
            }
            Behavior on opacity { NumberAnimation { duration: Theme.emphasized } }
        }
        // the live scene, top corner
        Row {
            anchors { top: parent.top; left: parent.left; margins: 14 }
            spacing: 8
            visible: !!lp.st.scene || !!lp.sync.running
            Rectangle {
                height: 26; radius: 13; width: sceneWord.implicitWidth + 30
                color: Qt.rgba(1, 1, 1, 0.08); border.width: 1; border.color: Theme.hairlineStrong
                Row {
                    anchors.centerIn: parent; spacing: 6
                    Icon { name: lp.sync.running ? "monitor" : "sparkle"; size: 14; color: Theme.ink; anchors.verticalCenter: parent.verticalCenter }
                    T { id: sceneWord; text: lp.sync.running ? mira.s.lu_sync_running : (lp.st.scene ? lp.st.scene.name : "")
                        font.pixelSize: Theme.small; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
                }
            }
        }
        Flow {
            id: rooms
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18; topMargin: 44 }
            spacing: 22
            Repeater {
                model: lp.rooms
                delegate: Column {
                    required property var modelData
                    spacing: 4
                    T {
                        text: modelData.name === "PC" ? mira.s.lu_pc : modelData.name
                        font.pixelSize: Theme.tiny + 1; font.weight: Font.DemiBold; color: Theme.ink3
                        font.letterSpacing: 0.6; wrapMode: Text.NoWrap
                        TapHandler { onTapped: lp.pick(modelData.lights, "room:" + modelData.name) }
                    }
                    Row {
                        spacing: 2
                        Repeater {
                            model: lp.lights.filter(function(l) { return modelData.lights.indexOf(l.id) >= 0 })
                            delegate: LightOrb {
                                required property var modelData
                                name: modelData.name
                                tone: modelData.hex
                                lit: modelData.on
                                online: modelData.online
                                level: modelData.level
                                pc: modelData.source === "pc"
                                living: !!modelData.living || (lp.sync.running && (lp.sync.lights || []).indexOf(modelData.id) >= 0)
                                clock: lp.clock
                                size: lp.wide ? 52 : 44
                                picked: lp.picked.indexOf(modelData.id) >= 0
                                onClicked: lp.toggle(modelData.id)
                                onPowerRequested: if (lp.page) lp.page.setPower([modelData.id], !modelData.on)
                            }
                        }
                    }
                }
            }
        }
        T {
            anchors.centerIn: parent
            visible: lp.st.ready && lp.lights.length === 0
            text: lp.st.home && lp.st.home.linked === false ? mira.s.lu_home_unlinked : mira.s.no_devices
            color: Theme.ink3
        }
    }

    // ── what the controls act on ──
    Flow {
        Layout.fillWidth: true
        spacing: 8
        Chip { text: mira.s.lu_all; glyph: "grid"; active: lp.picked.length === 0; onClicked: lp.pick([], "all") }
        Repeater {
            model: lp.rooms.filter(function(r) { return r.name !== "PC" })
            delegate: Chip {
                required property var modelData
                text: modelData.name; glyph: "home"
                active: lp.chip === "room:" + modelData.name
                onClicked: lp.pick(modelData.lights, "room:" + modelData.name)
            }
        }
        Repeater {
            // a Hue room is also a Home Assistant room by the same name: one chip is enough
            model: lp.groups.filter(function(g) {
                return !lp.rooms.some(function(r) { return r.name === g.name })
            })
            delegate: Chip {
                required property var modelData
                text: modelData.name; glyph: "layers"
                active: lp.chip === "group:" + modelData.id
                onClicked: lp.pick(modelData.lights, "group:" + modelData.id)
            }
        }
        Chip {
            visible: lp.pcLights.length > 0
            text: mira.s.lu_pc; glyph: "fan"
            active: lp.chip === "pc"
            onClicked: lp.pick(lp.pcLights.map(function(l) { return l.id }), "pc")
        }
    }

    // ── power and the last result ──
    RowLayout {
        Layout.fillWidth: true
        spacing: 10
        T {
            Layout.fillWidth: true
            text: lp.picked.length === 0 ? mira.s.lu_select_hint
                : lp.picked.length === 1 ? lp.nameOf(lp.picked[0]) : lp.picked.length + " " + mira.s.lu_selected_n
            color: lp.picked.length ? Theme.ink : Theme.ink3
            font.pixelSize: Theme.body
            elide: Text.ElideRight; wrapMode: Text.NoWrap
        }
        StatusPill {
            visible: !!lp.st.note && !!lp.st.note.text && lp.st.busy === ""
            text: (lp.st.note && lp.st.note.text) || ""
            tone: lp.st.note ? (lp.st.note.status === "ok" ? "ok" : lp.st.note.status === "error" ? "error" : "warn") : "info"
            icon: lp.st.note && lp.st.note.status === "ok" ? "check" : "alert"
            Layout.maximumWidth: 360
        }
        PillButton { text: mira.s.lu_on; iconName: "sun"; enabled: lp.st.busy === ""; onClicked: lp.page.setPower(lp.picked, true) }
        PillButton { text: mira.s.lu_off; iconName: "moon"; enabled: lp.st.busy === ""; onClicked: lp.page.setPower(lp.picked, false) }
    }

    // ── colour + scenes ──
    GridLayout {
        Layout.fillWidth: true
        columns: lp.wide ? 2 : 1
        columnSpacing: 16; rowSpacing: 16

        Card {
            icon: "drop"; title: mira.s.lu_color; accent: Theme.rose
            Layout.alignment: Qt.AlignTop
            Layout.fillWidth: !lp.wide
            Layout.preferredWidth: lp.wide ? 380 : -1
            RowLayout {
                Layout.fillWidth: true
                spacing: 14
                ColorWheel {
                    Layout.preferredWidth: 176; Layout.preferredHeight: 176
                    current: lp.focusLight && lp.focusLight.on ? lp.focusLight.hex : "#9B7BFF"
                    onPicked: function(hex) { lp.page.setColor(lp.picked, hex) }
                }
                Grid {
                    Layout.alignment: Qt.AlignVCenter
                    columns: 2; spacing: 9
                    Repeater {
                        model: ["#FF1E2D", "#FF7314", "#FFDC28", "#1EDC5A", "#28D7F5", "#285AFF", "#9B64FF", "#FF50AA"]
                        delegate: Rectangle {
                            required property string modelData
                            width: 30; height: 30; radius: 15
                            color: modelData
                            border.width: sw.hovered ? 2 : 1
                            border.color: sw.hovered ? "white" : Qt.rgba(1, 1, 1, 0.25)
                            HoverHandler { id: sw; cursorShape: Qt.PointingHandCursor }
                            TapHandler { onTapped: lp.page.setColor(lp.picked, modelData) }
                            Accessible.role: Accessible.Button
                            Accessible.name: modelData
                        }
                    }
                }
            }
            // white, warm → cool
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                T { text: mira.s.lu_warm; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
                Slider {
                    id: kelvin
                    Layout.fillWidth: true
                    from: 2000; to: 6500; stepSize: 100; value: 3200
                    implicitHeight: 30
                    background: Rectangle {
                        x: kelvin.leftPadding; y: kelvin.topPadding + kelvin.availableHeight / 2 - height / 2
                        width: kelvin.availableWidth; height: 10; radius: 5
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: kelvin.mirrored ? 1 : 0; color: "#FF8A2A" }
                            GradientStop { position: 0.5; color: "#FFE2B8" }
                            GradientStop { position: kelvin.mirrored ? 0 : 1; color: "#CFE3FF" }
                        }
                    }
                    handle: Rectangle {
                        x: kelvin.leftPadding + kelvin.visualPosition * (kelvin.availableWidth - width)
                        y: kelvin.topPadding + kelvin.availableHeight / 2 - height / 2
                        width: 20; height: 20; radius: 10; color: "white"
                        border.width: 2; border.color: Qt.rgba(0, 0, 0, 0.25)
                    }
                    onPressedChanged: if (!pressed) lp.page.setWhite(lp.picked, value)
                    Accessible.name: mira.s.lu_white
                }
                T { text: mira.s.lu_cool; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
            }
            // brightness
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Icon { name: "sun"; size: 18; color: Theme.amber }
                MiraSlider {
                    id: level
                    Layout.fillWidth: true
                    from: 1; to: 100; stepSize: 1
                    value: lp.focusLight && lp.focusLight.on ? lp.focusLight.level : 70
                    accent: Theme.amber
                    onPressedChanged: if (!pressed) lp.page.setBrightness(lp.picked, value)
                    Accessible.name: mira.s.lu_brightness
                }
                T { text: Math.round(level.value) + "%"; font.pixelSize: Theme.small; color: Theme.ink2; Layout.preferredWidth: 40; wrapMode: Text.NoWrap }
            }
            // a lamp's own effects (Hue: candle, fire, prism …)
            Flow {
                Layout.fillWidth: true
                visible: lp.effectChoices.length > 0
                spacing: 6
                Repeater {
                    model: [{ id: "none", name: mira.s.lu_effect_none }].concat(lp.effectChoices)
                    delegate: PillButton {
                        required property var modelData
                        text: modelData.name
                        size: Theme.small
                        implicitHeight: 30
                        onClicked: lp.page.setEffect(lp.picked, modelData.id)
                    }
                }
            }
        }

        Card {
            id: scenesCard
            icon: "layers"; title: mira.s.lu_scenes; subtitle: mira.s.lu_scenes_sub; accent: Theme.violet
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            trailing: [
                PillButton {
                    visible: !!lp.st.scene
                    text: mira.s.lu_stop_living; size: Theme.small; implicitHeight: 30
                    onClicked: lp.page.stopLiving()
                }
            ]
            GridLayout {
                Layout.fillWidth: true
                columns: Math.max(2, Math.floor((scenesCard.width - 32) / 150))
                columnSpacing: 10; rowSpacing: 10
                Repeater {
                    model: lp.scenes
                    delegate: AbstractButton {
                        id: sc
                        required property var modelData
                        readonly property bool active: !!lp.st.scene && lp.st.scene.id === modelData.id
                        Layout.fillWidth: true
                        implicitHeight: 78
                        hoverEnabled: true
                        focusPolicy: Qt.StrongFocus
                        Accessible.name: modelData.name + " · " + modelData.mood
                        onClicked: lp.page.applyScene(modelData.id, lp.picked)
                        background: Rectangle {
                            radius: 16
                            clip: true
                            border.width: sc.active ? 2 : 1
                            border.color: sc.active ? "white" : sc.visualFocus ? Theme.cyan : Qt.rgba(1, 1, 1, sc.hovered ? 0.35 : 0.14)
                            gradient: Gradient {
                                orientation: Gradient.Horizontal
                                GradientStop { position: 0.0; color: sc.stops[0] }
                                GradientStop { position: 0.34; color: sc.stops[1] }
                                GradientStop { position: 0.67; color: sc.stops[2] }
                                GradientStop { position: 1.0; color: sc.stops[3] }
                            }
                            // legibility veil over the palette
                            Rectangle {
                                anchors.fill: parent; radius: parent.radius
                                gradient: Gradient {
                                    GradientStop { position: 0.0; color: Qt.rgba(0.02, 0.02, 0.08, sc.hovered ? 0.05 : 0.15) }
                                    GradientStop { position: 1.0; color: Qt.rgba(0.02, 0.02, 0.08, 0.72) }
                                }
                            }
                        }
                        readonly property var stops: {
                            const p = modelData.palette || []
                            if (p.length === 0) {
                                const k = modelData.kelvin || 4000
                                const warm = k < 3000 ? "#FF9A3C" : k < 4500 ? "#FFD9A8" : "#DDEBFF"
                                return [warm, warm, Qt.lighter(warm, 1.1), "#FFFFFF"]
                            }
                            return [p[0], p[1 % p.length], p[2 % p.length], p[3 % p.length]]
                        }
                        contentItem: Item {
                            Column {
                                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 12 }
                                spacing: 1
                                Row {
                                    spacing: 6
                                    T { text: sc.modelData.name; font.pixelSize: Theme.body; font.weight: Font.DemiBold; color: "white"; wrapMode: Text.NoWrap }
                                    Rectangle {
                                        visible: sc.modelData.living
                                        anchors.verticalCenter: parent.verticalCenter
                                        height: 16; width: livingWord.implicitWidth + 10; radius: 8
                                        color: Qt.rgba(1, 1, 1, 0.22)
                                        T { id: livingWord; anchors.centerIn: parent; text: mira.s.lu_living; font.pixelSize: 9; color: "white"; wrapMode: Text.NoWrap }
                                    }
                                }
                                T { width: parent.width; text: sc.modelData.mood; font.pixelSize: Theme.tiny; color: Qt.rgba(1, 1, 1, 0.78)
                                    maximumLineCount: 1; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                            }
                        }
                        scale: down ? 0.97 : (hovered ? 1.02 : 1)
                        Behavior on scale { NumberAnimation { duration: Theme.fast; easing.type: Easing.OutBack } }
                    }
                }
            }
        }
    }

    // ── Screen Sync + the PC ──
    GridLayout {
        Layout.fillWidth: true
        columns: lp.wide ? 2 : 1
        columnSpacing: 16; rowSpacing: 16

        Card {
            icon: "monitor"; title: mira.s.lu_sync; subtitle: mira.s.lu_sync_sub; accent: Theme.cyan
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            lit: !!lp.sync.running
            // a little screen, lit by the colours the lights are taking from it
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 150
                // the wall behind the screen, lit the way the room is: two soft layers, wider than the screen
                Repeater {
                    model: [{ grow: 70, alpha: 0.16 }, { grow: 34, alpha: 0.26 }]
                    delegate: Rectangle {
                        required property var modelData
                        anchors.centerIn: screenBox
                        width: screenBox.width + modelData.grow; height: screenBox.height + modelData.grow * 0.75
                        radius: height / 2.6
                        color: Qt.color(lp.sync.ambient || "#8E5BFF")
                        opacity: lp.sync.running ? modelData.alpha : 0
                        Behavior on color { ColorAnimation { duration: 300 } }
                        Behavior on opacity { NumberAnimation { duration: Theme.emphasized } }
                    }
                }
                Rectangle {
                    id: screenBox
                    anchors.centerIn: parent
                    height: parent.height - 34; width: height * 16 / 9
                    radius: 10
                    color: "#05060C"
                    border.width: 2; border.color: Qt.rgba(1, 1, 1, 0.18)
                    Rectangle {
                        anchors.fill: parent; anchors.margins: 6; radius: 6
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: lp.sync.running ? lp.edgeColor(0) : "#151933" }
                            GradientStop { position: 0.5; color: lp.sync.running ? Qt.color(lp.sync.ambient || "#151933") : "#1A1F3D" }
                            GradientStop { position: 1; color: lp.sync.running ? lp.edgeColor(1) : "#151933" }
                        }
                        Behavior on opacity { NumberAnimation { duration: 200 } }
                        Icon { anchors.centerIn: parent; visible: !lp.sync.running; name: "monitor"; size: 30; color: Theme.ink3 }
                    }
                    Rectangle { width: 40; height: 4; radius: 2; color: Qt.rgba(1, 1, 1, 0.2)
                                anchors { top: parent.bottom; topMargin: 6; horizontalCenter: parent.horizontalCenter } }
                }
                // the lights around the screen, each in the colour it is being sent
                Row {
                    anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom }
                    spacing: 10
                    Repeater {
                        model: lp.sync.running ? (lp.sync.lights || []) : []
                        delegate: Rectangle {
                            required property string modelData
                            width: 14; height: 14; radius: 7
                            color: (lp.sync.preview || {})[modelData] || "#333"
                            border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.5)
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }
                    }
                }
            }
            // mode
            Row {
                Layout.alignment: Qt.AlignHCenter
                spacing: 6
                Repeater {
                    model: [{ id: "video", label: mira.s.lu_mode_video, glyph: "film" },
                            { id: "game", label: mira.s.lu_mode_game, glyph: "gamepad" },
                            { id: "ambient", label: mira.s.lu_mode_ambient, glyph: "leaf" }]
                    delegate: PillButton {
                        required property var modelData
                        text: modelData.label; iconName: modelData.glyph; size: Theme.small; implicitHeight: 32
                        primary: lp.syncMode === modelData.id
                        onClicked: { lp.syncMode = modelData.id; if (lp.sync.running) lp.page.startSync(modelData.id, lp.picked) }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                T {
                    Layout.fillWidth: true
                    font.pixelSize: Theme.small
                    color: lp.sync.state === "denied" || lp.sync.error ? Theme.danger : Theme.ink3
                    text: !lp.sync.running ? "" :
                          lp.sync.state === "asking" ? mira.s.lu_sync_asking :
                          lp.sync.state === "denied" ? mira.s.lu_sync_denied :
                          lp.sync.error ? lp.sync.error :
                          mira.s.lu_sync_running + " · " + Math.round(lp.sync.fps || 0) + " " + mira.s.lu_fps + " · "
                          + (lp.sync.stream === "hue" ? mira.s.lu_stream_hue : lp.sync.stream === "ha" ? mira.s.lu_stream_ha : mira.s.lu_pc)
                }
                PillButton {
                    text: mira.s.lu_sync_screen
                    enabled: lp.st.busy !== "sync"
                    onClicked: lp.page.chooseScreen(lp.syncMode, lp.picked)
                }
                PillButton {
                    primary: !lp.sync.running
                    danger: !!lp.sync.running
                    iconName: lp.sync.running ? "stop" : "play"
                    text: lp.sync.running ? mira.s.lu_sync_stop : mira.s.lu_sync_start
                    enabled: lp.st.busy !== "sync"
                    onClicked: lp.sync.running ? lp.page.stopSync() : lp.page.startSync(lp.syncMode, lp.picked)
                }
            }
            // a faster, smoother stream once Lumen holds its own Hue pairing
            Rectangle {
                Layout.fillWidth: true
                visible: !(lp.st.hue && lp.st.hue.streaming) && lp.lights.some(function(l) { return l.integration === "hue" || (l.detail || "").indexOf("Hue") >= 0 })
                implicitHeight: pairRow.implicitHeight + 20
                radius: 14
                color: Qt.rgba(0.21, 0.85, 0.96, 0.07)
                border.width: 1; border.color: Qt.rgba(0.21, 0.85, 0.96, 0.25)
                RowLayout {
                    id: pairRow
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                    spacing: 10
                    Icon { name: "link"; size: 18; color: Theme.cyan }
                    T {
                        Layout.fillWidth: true
                        font.pixelSize: Theme.small
                        text: lp.st.hue && lp.st.hue.pairing && lp.st.hue.pairing.state === "waiting" ? mira.s.lu_hue_waiting
                            : lp.st.hue && lp.st.hue.pairing && lp.st.hue.pairing.state === "failed" ? mira.s.lu_hue_failed
                            : mira.s.lu_hue_pair_sub
                    }
                    PillButton {
                        text: mira.s.lu_hue_pair; size: Theme.small; implicitHeight: 30
                        enabled: !(lp.st.hue && lp.st.hue.pairing && lp.st.hue.pairing.state === "waiting")
                        onClicked: lp.page.pairHue()
                    }
                }
            }
        }

        Card {
            icon: "fan"; title: mira.s.lu_pc_title
            subtitle: lp.st.pc && lp.st.pc.present ? (lp.st.pc.maker + " · " + lp.st.pc.product + " · " + lp.st.pc.firmware) : mira.s.lu_pc_none
            accent: Theme.violet
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            Repeater {
                model: lp.pcLights
                delegate: RowLayout {
                    id: hdr
                    required property var modelData
                    property bool editing: false
                    Layout.fillWidth: true
                    spacing: 10
                    // the header as a ring of its own colour
                    Rectangle {
                        width: 40; height: 40; radius: 20
                        color: "transparent"
                        border.width: 4
                        border.color: modelData.on ? modelData.hex : Qt.rgba(1, 1, 1, 0.12)
                        Icon { anchors.centerIn: parent; name: "fan"; size: 18; color: modelData.on ? modelData.hex : Theme.ink3 }
                        TapHandler { onTapped: lp.toggle(modelData.id) }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        visible: !hdr.editing
                        T { text: modelData.name; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                        T { text: modelData.detail; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                    }
                    MiraField {
                        id: nameField
                        visible: hdr.editing
                        Layout.fillWidth: true
                        text: modelData.name
                        onAccepted: { lp.page.rename(modelData.id, text); hdr.editing = false }
                    }
                    IconButton { iconName: hdr.editing ? "check" : "pencil"; tip: mira.s.lu_rename; diameter: 32
                                 onClicked: { if (hdr.editing) lp.page.rename(modelData.id, nameField.text); hdr.editing = !hdr.editing } }
                    IconButton { iconName: "bolt"; tip: mira.s.lu_identify_tip; diameter: 32; onClicked: lp.page.identify(modelData.id) }
                    MiraSwitch {
                        checked: !!modelData.on
                        accent: Qt.color(modelData.hex)
                        onToggled: { const want = checked; checked = Qt.binding(function() { return !!modelData.on }); lp.page.setPower([modelData.id], want) }
                    }
                }
            }
            Flow {
                Layout.fillWidth: true
                visible: lp.pcLights.length > 0
                spacing: 6
                Repeater {
                    model: lp.st.fx || []
                    delegate: PillButton {
                        required property string modelData
                        text: mira.s["lu_fx_" + modelData] || modelData
                        size: Theme.small; implicitHeight: 30
                        onClicked: {
                            const ids = lp.picked.filter(function(id) { return id.indexOf("pc:") === 0 })
                            lp.page.setEffect(ids.length ? ids : lp.pcLights.map(function(l) { return l.id }), modelData === "static" ? "none" : modelData)
                        }
                    }
                }
            }
            T {
                Layout.fillWidth: true
                visible: lp.pcLights.length > 0
                text: mira.s.lu_pc_note
                font.pixelSize: Theme.tiny + 1; color: Theme.ink3
            }
        }
    }

    property string syncMode: sync.mode || "video"
    function edgeColor(side) {
        const ids = sync.lights || []
        const prev = sync.preview || {}
        const keys = ids.filter(function(id) { return id.indexOf("pc:") !== 0 && prev[id] })
        if (keys.length === 0) return Qt.color(sync.ambient || "#151933")
        return Qt.color(prev[side === 0 ? keys[0] : keys[keys.length - 1]])
    }
}
