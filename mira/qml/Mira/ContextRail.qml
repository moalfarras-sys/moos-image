import QtQuick
import QtQuick.Layouts

// Left context: time and real weather, the house at a glance, and one-tap requests.
ColumnLayout {
    id: rail
    spacing: 12
    signal suggestion(string text)
    signal openSheet(string name)

    // ── time + weather ──────────────────────────────────────────────
    Glass {
        Layout.fillWidth: true
        Layout.preferredHeight: 132
        Item {
            anchors.fill: parent
            anchors.margins: 16
            Column {
                id: clockCol
                anchors.left: parent.left
                anchors.top: parent.top
                spacing: 2
                T {
                    id: clockText
                    anchors.left: parent.left
                    font.pixelSize: 40; font.weight: Font.Light; wrapMode: Text.NoWrap
                    font.features: { "tnum": 1 }
                    text: Qt.formatTime(now.value, "HH:mm")
                }
                T {
                    anchors.left: parent.left
                    font.pixelSize: Theme.small; color: Theme.ink2; wrapMode: Text.NoWrap
                    text: now.value.toLocaleDateString(Qt.locale(mira.lang === "ar" ? "ar_SA" : "en_GB"), "dddd d MMMM")
                }
            }
            Column {
                anchors.right: parent.right
                anchors.top: parent.top
                spacing: 4
                visible: mira.weather.ok === true
                Row {
                    anchors.right: parent.right
                    spacing: 6
                    Icon { name: rail.weatherIcon(mira.weather.code, mira.weather.is_day); size: 24; color: Theme.amber; anchors.verticalCenter: parent.verticalCenter }
                    T { text: (mira.weather.temp !== undefined ? mira.weather.temp : "—") + "°"; font.pixelSize: 26; font.weight: Font.Light; wrapMode: Text.NoWrap }
                }
                T { anchors.right: parent.right; text: mira.weather.condition || ""; font.pixelSize: Theme.small; color: Theme.ink2; wrapMode: Text.NoWrap }
                T { anchors.right: parent.right; text: mira.weather.city || ""; font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap }
            }
            T {
                anchors.right: parent.right; anchors.top: parent.top
                width: parent.width * 0.45
                visible: mira.weather.ok !== true
                text: mira.weather.error || mira.s.weather_unset
                font.pixelSize: Theme.small; color: Theme.ink3
                horizontalAlignment: Text.AlignRight
                TapHandler { onTapped: rail.openSheet("settings") }
            }
            Row {
                anchors.left: parent.left; anchors.bottom: parent.bottom
                spacing: 12
                visible: mira.weather.ok === true
                T { text: mira.s.humidity + " " + (mira.weather.humidity !== undefined && mira.weather.humidity !== null ? mira.weather.humidity + "%" : "—"); font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap }
                T { text: mira.s.wind + " " + (mira.weather.wind !== undefined && mira.weather.wind !== null ? mira.weather.wind + " km/h" : "—"); font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap }
            }
        }
    }

    // ── reminders and timers Mira will announce ─────────────────────
    Glass {
        Layout.fillWidth: true
        Layout.preferredHeight: remCol.implicitHeight + 24
        visible: (mira.reminders || []).length > 0
        ColumnLayout {
            id: remCol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
            spacing: 6
            Row {
                spacing: 8
                Icon { name: "clock"; size: 16; color: Theme.rose; anchors.verticalCenter: parent.verticalCenter }
                T { text: mira.s.rem_section; font.pixelSize: Theme.small; font.weight: Font.DemiBold; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
            }
            Repeater {
                model: mira.reminders || []
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 8
                    Rectangle { Layout.preferredWidth: 6; Layout.preferredHeight: 6; radius: 3; color: modelData.kind === "timer" ? Theme.amber : Theme.rose }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        T { text: modelData.text; font.pixelSize: Theme.small; Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight }
                        T { text: modelData.when; font.pixelSize: Theme.tiny; color: Theme.ink3; Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight }
                    }
                    IconButton { diameter: 26; iconName: "x"; tip: mira.s.rem_cancel; onClicked: mira.cancelReminder(modelData.id) }
                }
            }
        }
    }

    // ── home at a glance ────────────────────────────────────────────
    Glass {
        Layout.fillWidth: true
        Layout.preferredHeight: homeCol.implicitHeight + 32
        ColumnLayout {
            id: homeCol
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                SectionTitle { icon: "home"; text: mira.s.home; accent: Theme.cyan }
                Item { Layout.fillWidth: true }
                IconButton { diameter: 28; iconName: "chevron"; tip: mira.s.home; onClicked: rail.openSheet("home")
                             rotation: mira.lang === "ar" ? 180 : 0 }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Rectangle {
                    width: 44; height: 44; radius: 14
                    color: Qt.rgba(1, 0.77, 0.42, mira.home.lights_on > 0 ? 0.18 : 0.06)
                    Icon { anchors.centerIn: parent; name: "bulb"; size: 22; color: mira.home.lights_on > 0 ? Theme.amber : Theme.ink3 }
                }
                Column {
                    Layout.fillWidth: true
                    T { width: parent.width; text: mira.s.lights; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
                    T { width: parent.width; text: mira.home.lights_on + " / " + mira.home.lights_available + " " + mira.s.lights_on_of; font.pixelSize: Theme.small; color: Theme.ink2 }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                PillButton { Layout.fillWidth: true; text: mira.s.all_on; iconName: "sun"; size: Theme.small; implicitHeight: 34
                             enabled: mira.home.lights_available > 0 && !mira.home.busy; onClicked: mira.allLights(true) }
                PillButton { Layout.fillWidth: true; text: mira.s.all_off; iconName: "moon"; size: Theme.small; implicitHeight: 34
                             enabled: mira.home.lights_available > 0 && !mira.home.busy; onClicked: mira.allLights(false) }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline; visible: mira.home.tv !== null && mira.home.tv !== undefined }
            RowLayout {
                Layout.fillWidth: true
                visible: mira.home.tv !== null && mira.home.tv !== undefined
                spacing: 12
                Rectangle {
                    width: 44; height: 44; radius: 14
                    color: Qt.rgba(0.21, 0.85, 0.96, mira.home.tv && mira.home.tv.is_on ? 0.16 : 0.06)
                    Icon { anchors.centerIn: parent; name: "tv"; size: 22; color: mira.home.tv && mira.home.tv.is_on ? Theme.cyan : Theme.ink3 }
                }
                Column {
                    Layout.fillWidth: true
                    T { text: mira.home.tv ? mira.home.tv.name : ""; font.pixelSize: Theme.body; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width; wrapMode: Text.NoWrap }
                    T { width: parent.width; text: mira.home.tv ? (mira.s["state_" + mira.home.tv.state] || mira.home.tv.state) : ""; font.pixelSize: Theme.small; color: Theme.ink2 }
                }
                MiraSwitch {
                    enabled: !!mira.home.tv && !!(mira.home.tv.is_on ? mira.home.tv.off_capable : mira.home.tv.on_capable) && !mira.home.busy
                    checked: !!mira.home.tv && !!mira.home.tv.is_on
                    onToggled: { const want = checked; checked = Qt.binding(function() { return !!mira.home.tv && !!mira.home.tv.is_on });
                                 mira.homeAction(mira.home.tv.entity_id, want ? "turn_on" : "turn_off", -1, "") }
                }
            }
        }
    }

    // ── one-tap requests ────────────────────────────────────────────
    Glass {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 120
        Flickable {
            anchors.fill: parent
            anchors.margins: 16
            contentHeight: sgCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Column {
                id: sgCol
                width: parent.width
                spacing: 8
                SectionTitle { icon: "sparkle"; text: mira.s.quick; accent: Theme.violet }
                Item { width: 1; height: 2 }
                Repeater {
                    // With a linked home Mira leads with the house; without one, with this computer.
                    model: mira.home.linked ? [
                        { icon: "bulb", text: mira.s.sg_home_status },
                        { icon: "sun", text: mira.s.sg_weather },
                        { icon: "monitor", text: mira.s.sg_pc_status },
                        { icon: "clock", text: mira.s.sg_reminder }
                    ] : [
                        { icon: "download", text: mira.s.sg_update },
                        { icon: "monitor", text: mira.s.sg_pc_status },
                        { icon: "package", text: mira.s.sg_install },
                        { icon: "clock", text: mira.s.sg_reminder }
                    ]
                    delegate: Rectangle {
                        required property var modelData
                        width: sgCol.width; height: 42; radius: 13
                        color: sgHover.hovered ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.03)
                        border.width: 1; border.color: sgHover.hovered ? Theme.hairlineStrong : "transparent"
                        Behavior on color { ColorAnimation { duration: Theme.fast } }
                        Row {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left; anchors.leftMargin: 12
                            spacing: 10
                            Icon { name: modelData.icon; size: 17; color: Theme.ink2; anchors.verticalCenter: parent.verticalCenter }
                            T { text: modelData.text; font.pixelSize: Theme.small + 1; color: Theme.ink2; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
                        }
                        HoverHandler { id: sgHover; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: rail.suggestion(modelData.text) }
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData.text
                    }
                }
            }
        }
    }

    QtObject {
        id: now
        property date value: new Date()
    }
    Timer { interval: 1000 * (60 - new Date().getSeconds()); running: true; repeat: false
            onTriggered: { now.value = new Date(); interval = 60000; repeat = true; restart() } }

    function weatherIcon(code, isDay) {
        if (code === undefined || code === null || code < 0) return "cloud"
        if (code === 0 || code === 1) return isDay === 0 ? "moon" : "sun"
        if (code === 2 || code === 3) return "cloud"
        if (code === 45 || code === 48) return "fog"
        if (code >= 71 && code <= 77) return "snow"
        if (code >= 95) return "storm"
        return "rain"
    }
}
