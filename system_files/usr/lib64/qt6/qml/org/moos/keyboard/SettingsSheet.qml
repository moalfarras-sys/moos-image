// SPDX-FileCopyrightText: 2026 Moalfarras — MoOS
// SPDX-License-Identifier: GPL-2.0-or-later

// The Touch Bar's own settings, in the keys' place like the emoji sheet: whether the
// keyboard learns the words this person writes, forgetting them, clearing recent emoji,
// and the way to Plasma's full keyboard settings. Every row is a 44-pixel-plus glass
// control; its opaque face and catch-all area keep touches off the keys underneath.
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Rectangle {
    id: sheet

    property QtObject theme: null
    property bool rightToLeft: false
    property string language: "en"
    property bool learning: true
    property int learnedCount: 0
    property int recentCount: 0
    property real rowHeight: 48

    signal learningToggled(bool on)
    signal forgetWords()
    signal clearRecent()
    signal allSettings()

    readonly property color ink: theme ? theme.glassInk : Kirigami.Theme.textColor
    readonly property color quietInk: theme ? theme.keySmallTextColor : Kirigami.Theme.textColor
    function say(ar, en) { return language === "ar" ? ar : en }

    color: theme ? theme.keyboardBackgroundColor : Kirigami.Theme.backgroundColor

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        onWheel: (wheel) => wheel.accepted = true
    }

    component SettingRow: Item {
        id: row
        property string label
        property string detail
        property bool toggle: false
        property bool checked: false
        property bool destructive: false
        property alias enabledRow: button.enabled
        signal activated()
        Layout.fillWidth: true
        // The row takes its text's real height (Arabic lines need their room), never
        // less than a touch row: a fixed height painted the detail line below the glass.
        Layout.preferredHeight: Math.max(sheet.rowHeight, texts.implicitHeight + Math.round(sheet.rowHeight * 0.4))
        TouchBarButton {
            id: button
            anchors.fill: parent
            theme: sheet.theme
            rightToLeft: sheet.rightToLeft
            accessibleName: row.label + (row.toggle ? (row.checked ? sheet.say("، مفعّل", ", on") : sheet.say("، متوقف", ", off")) : "")
            onActivated: row.activated()
        }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Math.round(sheet.rowHeight * 0.4)
            anchors.rightMargin: Math.round(sheet.rowHeight * 0.4)
            LayoutMirroring.enabled: sheet.rightToLeft
            LayoutMirroring.childrenInherit: true
            opacity: button.enabled ? 1 : 0.45
            ColumnLayout {
                id: texts
                objectName: "moosSettingTexts"
                Layout.fillWidth: true
                spacing: 0
                Text {
                    Layout.fillWidth: true
                    text: row.label
                    elide: Text.ElideRight
                    horizontalAlignment: Text.AlignLeft
                    color: sheet.ink
                    font.family: sheet.theme ? sheet.theme.fontFamily : ""
                    font.pixelSize: Math.round(sheet.rowHeight * 0.32)
                }
                Text {
                    Layout.fillWidth: true
                    visible: row.detail.length > 0
                    text: row.detail
                    elide: Text.ElideRight
                    horizontalAlignment: Text.AlignLeft
                    color: sheet.quietInk
                    font.family: sheet.theme ? sheet.theme.fontFamily : ""
                    font.pixelSize: Math.round(sheet.rowHeight * 0.24)
                }
            }
            // A switch drawn like the keys: accent track when on.
            Rectangle {
                visible: row.toggle
                Layout.preferredWidth: Math.round(sheet.rowHeight * 0.9)
                Layout.preferredHeight: Math.round(sheet.rowHeight * 0.5)
                radius: height / 2
                color: row.checked ? Kirigami.Theme.highlightColor
                                   : Qt.rgba(sheet.ink.r, sheet.ink.g, sheet.ink.b, 0.18)
                Behavior on color { ColorAnimation { duration: Kirigami.Units.shortDuration } }
                Rectangle {
                    width: parent.height - 6
                    height: width
                    radius: width / 2
                    y: 3
                    // The knob sits at the reading end when on.
                    x: (row.checked !== sheet.rightToLeft) ? parent.width - width - 3 : 3
                    color: row.checked ? Kirigami.Theme.highlightedTextColor : sheet.ink
                    Behavior on x { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Math.round(sheet.rowHeight * 0.2)
        spacing: Math.round(sheet.rowHeight * 0.12)

        GridLayout {
            Layout.fillWidth: true
            columns: sheet.width > sheet.rowHeight * 14 ? 2 : 1
            columnSpacing: Math.round(sheet.rowHeight * 0.15)
            rowSpacing: Math.round(sheet.rowHeight * 0.12)
            LayoutMirroring.enabled: sheet.rightToLeft
            LayoutMirroring.childrenInherit: true

            SettingRow {
                objectName: "moosKeyboardLearning"
                toggle: true
                checked: sheet.learning
                label: sheet.say("تعلّم الكلمات التي أكتبها", "Learn the words I write")
                detail: sheet.say("لاقتراحها لاحقًا. لا شيء من كلمات المرور أو العناوين.",
                                  "To suggest them later. Never from passwords or addresses.")
                onActivated: sheet.learningToggled(!sheet.learning)
            }
            SettingRow {
                objectName: "moosKeyboardForget"
                enabledRow: sheet.learnedCount > 0
                label: sheet.say("انسَ الكلمات المتعلَّمة", "Forget learned words")
                detail: sheet.learnedCount > 0
                    ? sheet.say(sheet.learnedCount + " كلمة محفوظة على هذا الجهاز فقط",
                                sheet.learnedCount + " words, kept on this computer only")
                    : sheet.say("لا كلمات محفوظة", "No words kept")
                onActivated: sheet.forgetWords()
            }
            SettingRow {
                objectName: "moosKeyboardClearRecent"
                enabledRow: sheet.recentCount > 0
                label: sheet.say("امسح الإيموجي الأخيرة", "Clear recent emoji")
                detail: sheet.recentCount > 0 ? sheet.say(sheet.recentCount + " إيموجي", sheet.recentCount + " emoji")
                                              : sheet.say("لا إيموجي أخيرة", "No recent emoji")
                onActivated: sheet.clearRecent()
            }
            SettingRow {
                objectName: "moosKeyboardAllSettings"
                label: sheet.say("كل إعدادات لوحة المفاتيح…", "All keyboard settings…")
                detail: sheet.say("اللغات والصوت والاهتزاز", "Languages, sound and vibration")
                onActivated: sheet.allSettings()
            }
        }
        Item { Layout.fillHeight: true }
    }
}
