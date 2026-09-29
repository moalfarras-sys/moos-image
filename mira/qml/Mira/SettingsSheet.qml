import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Preferences in five short sections; every control acts on a real setting and shows its read-back.
Item {
    id: st
    property int section: 0
    readonly property var sections: [
        { icon: "face", label: mira.s.st_look },
        { icon: "mic", label: mira.s.st_voice },
        { icon: "echo", label: mira.s.st_echo },
        { icon: "cloud", label: mira.s.st_weather },
        { icon: "book", label: mira.s.st_memory },
        { icon: "globe", label: mira.companion.text ? mira.companion.text.section : "" } ]

    ColumnLayout {
        anchors.fill: parent
        spacing: 16

        // segmented section picker
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 44
            radius: 22
            color: Qt.rgba(1, 1, 1, 0.04)
            border.width: 1; border.color: Theme.hairline
            Row {
                id: seg
                anchors.fill: parent; anchors.margins: 4
                Repeater {
                    model: st.sections
                    delegate: AbstractButton {
                        required property var modelData
                        required property int index
                        width: seg.width / st.sections.length; height: seg.height
                        hoverEnabled: true
                        Accessible.name: modelData.label
                        onClicked: st.section = index
                        background: Rectangle {
                            radius: height / 2
                            color: st.section === index ? Qt.rgba(0.6, 0.48, 1, 0.24) : parent.hovered ? Qt.rgba(1, 1, 1, 0.05) : "transparent"
                            border.width: st.section === index ? 1 : 0
                            border.color: Qt.rgba(0.7, 0.6, 1, 0.45)
                            Behavior on color { ColorAnimation { duration: Theme.fast } }
                        }
                        contentItem: Row {
                            spacing: 6
                            Item { width: Math.max(0, (parent.width - ic.width - lb.implicitWidth - 6) / 2); height: 1 }
                            Icon { id: ic; name: modelData.icon; size: 15; color: st.section === index ? Theme.ink : Theme.ink3; anchors.verticalCenter: parent.verticalCenter }
                            T { id: lb; text: modelData.label; font.pixelSize: Theme.small; color: st.section === index ? Theme.ink : Theme.ink2; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter
                                visible: seg.width > 470 }
                        }
                    }
                }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: st.section

            // ── appearance ──────────────────────────────────────────
            Flickable {
                contentHeight: look.implicitHeight; clip: true; boundsBehavior: Flickable.StopAtBounds
                ColumnLayout {
                    id: look
                    width: parent.width
                    spacing: 16
                    SectionTitle { icon: "face"; text: mira.s.face; accent: Theme.rose }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        Repeater {
                            model: [{ style: "rose", label: mira.s.face_rose, tint: Theme.rose }, { style: "holo", label: mira.s.face_holo, tint: Theme.cyan }]
                            delegate: AbstractButton {
                                id: faceBtn
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredHeight: 190
                                hoverEnabled: true
                                Accessible.name: modelData.label
                                onClicked: mira.setFace(modelData.style)
                                readonly property bool chosen: mira.faceStyle === modelData.style
                                background: Glass {
                                    radius: 20
                                    lit: faceBtn.chosen
                                    edge: faceBtn.chosen ? Qt.rgba(faceBtn.modelData.tint.r, faceBtn.modelData.tint.g, faceBtn.modelData.tint.b, 0.7)
                                                         : faceBtn.hovered ? Theme.hairlineStrong : Theme.hairline
                                }
                                contentItem: Column {
                                    spacing: 10
                                    topPadding: 14
                                    Avatar { width: 120; height: 120; anchors.horizontalCenter: parent.horizontalCenter
                                             style: faceBtn.modelData.style; expression: faceBtn.hovered ? "happy" : "neutral"; tint: faceBtn.modelData.tint }
                                    Row {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        spacing: 6
                                        Icon { visible: faceBtn.chosen; name: "check"; size: 16; weight: 2.2; color: faceBtn.modelData.tint; anchors.verticalCenter: parent.verticalCenter }
                                        T { text: faceBtn.modelData.label; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                                    }
                                }
                            }
                        }
                    }
                    Glass {
                        Layout.fillWidth: true
                        Layout.preferredHeight: lookCol.implicitHeight + 32
                        radius: 18
                        ColumnLayout {
                            id: lookCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
                            spacing: 10
                            MiraSwitch { Layout.fillWidth: true; text: mira.s.motion; checked: mira.motion; onToggled: mira.setMotion(checked) }
                            T { Layout.fillWidth: true; text: mira.s.motion_sub; font.pixelSize: Theme.small; color: Theme.ink3 }
                            MiraSwitch { Layout.fillWidth: true; text: mira.s.screen_look; accent: Theme.amber
                                         checked: mira.screenLook; onToggled: mira.setScreenLook(checked) }
                            T { Layout.fillWidth: true; text: mira.s.screen_look_sub; font.pixelSize: Theme.small; color: Theme.ink3 }
                            RowLayout {
                                Layout.fillWidth: true
                                T { text: mira.s.lang_label; Layout.fillWidth: true }
                                PillButton { text: "العربية"; primary: mira.lang === "ar"; implicitHeight: 32; size: Theme.small; onClicked: mira.setLang("ar") }
                                PillButton { text: "English"; primary: mira.lang === "en"; implicitHeight: 32; size: Theme.small; onClicked: mira.setLang("en") }
                            }
                        }
                    }
                    Glass {
                        Layout.fillWidth: true
                        Layout.preferredHeight: aboutText.implicitHeight + 58
                        radius: 18
                        Column {
                            anchors.fill: parent; anchors.margins: 16
                            spacing: 8
                            SectionTitle { icon: "shield"; text: mira.s.about; accent: Theme.ok }
                            T { id: aboutText; width: parent.width; text: mira.s.about_body + "\n\n" + mira.s.shortcuts + ": " + mira.s.shortcuts_body; font.pixelSize: Theme.small; color: Theme.ink2 }
                        }
                    }
                }
            }

            // ── voice ───────────────────────────────────────────────
            Flickable {
                contentHeight: voice.implicitHeight; clip: true; boundsBehavior: Flickable.StopAtBounds
                ColumnLayout {
                    id: voice
                    width: parent.width
                    spacing: 14
                    Glass {
                        Layout.fillWidth: true; Layout.preferredHeight: 92; radius: 18
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 16; spacing: 6
                            MiraSwitch { Layout.fillWidth: true; text: mira.s.voice_on; checked: mira.echo.voice_enabled !== false
                                         enabled: mira.echo.online === true
                                         onToggled: { const want = checked; checked = Qt.binding(function() { return mira.echo.voice_enabled !== false }); mira.setVoiceEnabled(want) } }
                            T { Layout.fillWidth: true; text: mira.echo.wake_hint ? mira.echo.wake_hint : mira.s.voice_on_sub; font.pixelSize: Theme.small; color: Theme.ink3 }
                        }
                    }
                    SectionTitle { icon: "sparkle"; text: mira.s.brain_title; accent: Theme.violet }
                    Glass {
                        Layout.fillWidth: true; Layout.preferredHeight: brainCol.implicitHeight + 32; radius: 18
                        ColumnLayout {
                            id: brainCol
                            anchors.fill: parent; anchors.margins: 16; spacing: 8
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Rectangle { Layout.preferredWidth: 8; Layout.preferredHeight: 8; radius: 4
                                    color: mira.brainKey === "ok" || mira.brainKey === "set" ? Theme.ok : mira.brainKey === "failed" ? Theme.danger
                                         : mira.brainKey === "testing" ? Theme.amber : Theme.off }
                                T { Layout.fillWidth: true; font.pixelSize: Theme.small + 1; wrapMode: Text.NoWrap
                                    text: mira.brainKey === "ok" ? mira.s.brain_key_ok : mira.brainKey === "failed" ? mira.s.brain_key_failed
                                        : mira.brainKey === "testing" ? mira.s.brain_key_testing : mira.brainKey === "set" ? mira.s.brain_key_set : mira.s.brain_key_missing }
                            }
                            T { Layout.fillWidth: true; text: mira.s.brain_sub; font.pixelSize: Theme.small; color: Theme.ink3 }
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                MiraField { id: keyField; Layout.fillWidth: true; echoMode: TextInput.Password; placeholderText: mira.s.brain_key_placeholder
                                            onAccepted: { mira.saveGeminiKey(text); text = "" } }
                                PillButton { text: mira.s.brain_key_save; iconName: "check"; size: Theme.small; enabled: keyField.text.trim().length >= 20 && mira.brainKey !== "testing"
                                             onClicked: { mira.saveGeminiKey(keyField.text); keyField.text = "" } }
                            }
                        }
                    }
                    SectionTitle { icon: "wave"; text: mira.s.voice_name; accent: Theme.rose }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Repeater {
                            model: [{ n: "Aoede", d: mira.lang === "ar" ? "دافئ" : "Warm" }, { n: "Kore", d: mira.lang === "ar" ? "واضح" : "Clear" }, { n: "Leda", d: mira.lang === "ar" ? "هادئ" : "Calm" }]
                            delegate: PillButton { required property var modelData; Layout.fillWidth: true
                                text: modelData.n + " · " + modelData.d; primary: mira.voiceName === modelData.n; onClicked: mira.setVoiceName(modelData.n) }
                        }
                    }
                    Glass {
                        Layout.fillWidth: true; Layout.preferredHeight: wakeCol.implicitHeight + 32; radius: 18
                        ColumnLayout {
                            id: wakeCol
                            anchors.fill: parent; anchors.margins: 16; spacing: 8
                            MiraSwitch { Layout.fillWidth: true; text: mira.s.local_wake; checked: mira.wake.enabled; onToggled: mira.setLocalWake(checked) }
                            T { Layout.fillWidth: true; text: mira.s.local_wake_sub; font.pixelSize: Theme.small; color: Theme.ink3 }
                            ComboBox {
                                id: micCombo
                                Layout.fillWidth: true
                                visible: mira.wake.enabled
                                model: mira.wake.sources || []
                                currentIndex: Math.max(0, (mira.wake.sources || []).indexOf(mira.wake.source))
                                onActivated: mira.setMicSource(currentText)
                                font.family: Theme.font
                            }
                            T { Layout.fillWidth: true; visible: mira.wake.enabled && text !== ""; text: mira.wake.state || ""; font.pixelSize: Theme.small; color: Theme.cyan }
                        }
                    }
                    WakeCoach { Layout.fillWidth: true; Layout.preferredHeight: implicitHeight }
                }
            }

            // ── Echo ────────────────────────────────────────────────
            Flickable {
                contentHeight: echoCol.implicitHeight; clip: true; boundsBehavior: Flickable.StopAtBounds
                ColumnLayout {
                    id: echoCol
                    width: parent.width
                    spacing: 14
                    Glass {
                        Layout.fillWidth: true; Layout.preferredHeight: 70; radius: 18
                        RowLayout {
                            anchors.fill: parent; anchors.margins: 16; spacing: 12
                            Rectangle { width: 10; height: 10; radius: 5; color: mira.echo.online ? Theme.ok : Theme.danger }
                            Column { Layout.fillWidth: true
                                T { width: parent.width; text: mira.s.echo_state; font.weight: Font.DemiBold }
                                T { width: parent.width; text: mira.echo.state || ""; font.pixelSize: Theme.small; color: Theme.ink3; elide: Text.ElideRight; wrapMode: Text.NoWrap } }
                            Icon { name: "echo"; size: 26; color: mira.echo.online ? Theme.cyan : Theme.ink3 }
                        }
                    }
                    Glass {
                        Layout.fillWidth: true; Layout.preferredHeight: 70; radius: 18
                        RowLayout {
                            anchors.fill: parent; anchors.margins: 16; spacing: 12
                            Rectangle { width: 10; height: 10; radius: 5
                                color: mira.echo.standalone === "synced" ? Theme.ok : mira.echo.standalone === "unavailable" ? Theme.amber : Theme.off }
                            Column { Layout.fillWidth: true
                                T { width: parent.width; text: mira.s.standalone; font.weight: Font.DemiBold }
                                T { width: parent.width; font.pixelSize: Theme.small; color: Theme.ink3; elide: Text.ElideRight; wrapMode: Text.NoWrap
                                    text: mira.echo.standalone === "synced" ? mira.s.standalone_synced : mira.echo.standalone === "unavailable" ? mira.s.standalone_unavailable : mira.s.standalone_unknown } }
                            Icon { name: "shield"; size: 24; color: mira.echo.standalone === "synced" ? Theme.ok : Theme.ink3 }
                        }
                    }
                    Glass {
                        Layout.fillWidth: true; Layout.preferredHeight: sliders.implicitHeight + 32; radius: 18
                        ColumnLayout {
                            id: sliders
                            anchors.fill: parent; anchors.margins: 16; spacing: 10
                            RowLayout { Layout.fillWidth: true
                                T { text: mira.s.speaker_volume; Layout.fillWidth: true }
                                T { text: mira.echo.speaker_volume !== null && mira.echo.speaker_volume !== undefined ? mira.echo.speaker_volume + "%" : "—"; color: Theme.ink2; font.pixelSize: Theme.small } }
                            MiraSlider { Layout.fillWidth: true; from: 0; to: 100; stepSize: 1; accent: Theme.rose
                                enabled: mira.echo.online === true && mira.echo.speaker_volume !== null && mira.echo.speaker_volume !== undefined
                                value: mira.echo.speaker_volume || 0
                                onPressedChanged: if (!pressed) mira.setSpeakerVolume(value) }
                            RowLayout { Layout.fillWidth: true
                                T { text: mira.s.wake_threshold; Layout.fillWidth: true }
                                T { text: mira.echo.wake_threshold !== null && mira.echo.wake_threshold !== undefined ? mira.echo.wake_threshold + "%" : "—"; color: Theme.ink2; font.pixelSize: Theme.small } }
                            MiraSlider { Layout.fillWidth: true; from: 50; to: 99; stepSize: 1; accent: Theme.violet
                                enabled: mira.echo.online === true && mira.echo.wake_threshold !== null && mira.echo.wake_threshold !== undefined
                                value: mira.echo.wake_threshold || 70
                                onPressedChanged: if (!pressed) mira.setWakeThreshold(value) }
                            T { Layout.fillWidth: true; text: mira.s.wake_threshold_sub; font.pixelSize: Theme.small; color: Theme.ink3 }
                        }
                    }
                    Glass {
                        Layout.fillWidth: true; Layout.preferredHeight: echoCtl.implicitHeight + 32; radius: 18
                        ColumnLayout {
                            id: echoCtl
                            anchors.fill: parent; anchors.margins: 16; spacing: 12
                            MiraSwitch { Layout.fillWidth: true; text: mira.s.echo_mute; accent: Theme.danger
                                enabled: mira.echo.online === true && mira.echo.mute_available === true
                                checked: mira.echo.muted === true
                                onToggled: { const want = checked; checked = Qt.binding(function() { return mira.echo.muted === true }); mira.echoMute(want) } }
                            RowLayout { Layout.fillWidth: true; spacing: 8
                                PillButton { text: mira.s.echo_setup; iconName: "external"; enabled: mira.echo.online === true && mira.echo.setup === true; onClicked: mira.echoSetup() }
                                PillButton { text: mira.s.echo_pair; iconName: "bluetooth"; enabled: mira.echo.online === true && mira.echo.pair === true; onClicked: mira.echoPair() }
                            }
                            T { Layout.fillWidth: true; text: mira.echo.setup_url ? mira.echo.setup_url + " · " + mira.s.echo_setup_sub : mira.s.echo_setup_sub; font.pixelSize: Theme.small; color: Theme.ink3 }
                        }
                    }
                }
            }

            // ── weather ─────────────────────────────────────────────
            Flickable {
                contentHeight: wx.implicitHeight; clip: true; boundsBehavior: Flickable.StopAtBounds
                ColumnLayout {
                    id: wx
                    width: parent.width
                    spacing: 12
                    SectionTitle { icon: "cloud"; text: mira.s.city; accent: Theme.amber }
                    RowLayout {
                        Layout.fillWidth: true
                        MiraField { id: cityField; Layout.fillWidth: true; text: mira.city; placeholderText: mira.s.city_placeholder; onAccepted: mira.saveCity(text) }
                        PillButton { text: mira.s.save; primary: true; onClicked: mira.saveCity(cityField.text) }
                    }
                    T { Layout.fillWidth: true; color: mira.weather.ok ? Theme.ink2 : Theme.ink3; font.pixelSize: Theme.small
                        text: mira.weather.ok ? (mira.weather.city + " · " + mira.weather.temp + "° · " + mira.weather.condition + " · Open-Meteo · " + mira.weather.updated) : (mira.weather.error || "") }
                }
            }

            // ── memory ──────────────────────────────────────────────
            ColumnLayout {
                spacing: 10
                SectionTitle { icon: "book"; text: mira.s.profile; accent: Theme.violet }
                T { Layout.fillWidth: true; text: mira.s.profile_sub; font.pixelSize: Theme.small; color: Theme.ink3 }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 16
                    color: Qt.rgba(1, 1, 1, 0.04)
                    border.width: 1; border.color: profile.activeFocus ? Qt.rgba(0.35, 0.85, 1, 0.5) : Theme.hairline
                    ScrollView {
                        anchors.fill: parent; anchors.margins: 4
                        TextArea {
                            id: profile
                            text: mira.profileText
                            wrapMode: TextEdit.Wrap
                            color: Theme.ink
                            font.family: Theme.font; font.pixelSize: Theme.body
                            selectionColor: Qt.rgba(0.35, 0.8, 1, 0.35)
                            background: Item {}
                            property bool dirty: false
                            onTextChanged: dirty = (text !== mira.profileText)
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    T { Layout.fillWidth: true; font.pixelSize: Theme.small; color: profile.length > 4000 ? Theme.danger : profile.dirty ? Theme.amber : Theme.ink3
                        text: profile.length + " / 4000" + (profile.dirty ? " · " + mira.s.unsaved : (mira.profileStatus ? " · " + mira.profileStatus : "")) }
                    PillButton { text: mira.s.save; primary: true; enabled: profile.dirty && profile.length <= 4000; onClicked: { mira.saveProfile(profile.text); profile.dirty = false } }
                }
            }

            // ── phone ───────────────────────────────────────────────
            Flickable {
                contentHeight: phonePanel.implicitHeight; clip: true; boundsBehavior: Flickable.StopAtBounds
                CompanionPanel { id: phonePanel; width: parent.width }
            }
        }
    }
}
