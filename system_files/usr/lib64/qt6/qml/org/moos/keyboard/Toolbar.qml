// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtQuick.VirtualKeyboard
import QtQuick.VirtualKeyboard.Settings
import org.kde.kirigami as Kirigami

Item {
    id: bar
    objectName: "moosKeyboardToolbar"
    required property real panelHeight
    required property var keyboardSettings
    required property color surface
    required property color ink
    required property color tint
    required property color accent
    required property color onAccent

    readonly property bool arabic: Qt.uiLanguage.toLowerCase().startsWith("ar")
    readonly property bool privateField: (InputContext.inputMethodHints &
        (Qt.ImhHiddenText | Qt.ImhSensitiveData)) !== 0
    readonly property bool restricted: privateField || (InputContext.inputMethodHints &
        (Qt.ImhDigitsOnly | Qt.ImhFormattedNumbersOnly | Qt.ImhDialableCharactersOnly |
         Qt.ImhDate | Qt.ImhTime | Qt.ImhEmailCharactersOnly | Qt.ImhUrlCharactersOnly |
         Qt.ImhLatinOnly | Qt.ImhUppercaseOnly | Qt.ImhLowercaseOnly)) !== 0
    readonly property bool digitsOnly: (InputContext.inputMethodHints &
        (Qt.ImhDigitsOnly | Qt.ImhFormattedNumbersOnly | Qt.ImhDialableCharactersOnly)) !== 0
    readonly property var groups: [
        ["😀","😄","😂","🥰","😊","😍","🤔","🥳","😎","😅","🥹","😴"],
        ["👍","👋","👏","🙏","🙌","🤝","💪","👌","✌️","🤍","❤️","💜"],
        ["✨","🎉","⭐","💡","✅","🔥","🌙","☀️","🌸","☕","🎁","🚀"]
    ]
    readonly property var defaultEmoji: ["😊","❤️","👍","✨","🙏"]
    readonly property var recent: Appearance.recentEmoji.split(" ").filter(e =>
        groups.some(group => group.includes(e)))
    readonly property var suggested: [...new Set(recent.concat(defaultEmoji))].slice(0, 5)
    property string page: ""
    property int groupIndex: 0
    property bool numberStrip: false
    readonly property bool showNumbers: numberStrip || digitsOnly
    readonly property bool canInsert: InputContext.inputItem !== null

    function label(ar, en) { return arabic ? ar : en }
    function closePanel() { sheet.close(); page = "" }
    function openPage(which) {
        if (page === which && sheet.opened) { closePanel(); return }
        page = which
        sheet.open()
    }
    function enterEmoji(symbol) {
        if (!canInsert || restricted || !groups.some(group => group.includes(symbol))) return
        // Finish composition before appending an emoji. Never read the client's text.
        if (InputContext.preeditText.length) InputContext.commit()
        InputContext.commit(symbol)
        if (Appearance.showSuggestions)
            Appearance.recentEmoji = [symbol].concat(recent.filter(e => e !== symbol)).slice(0, 5).join(" ")
    }
    function enterDigit(digit) {
        if (canInsert && /^[0-9]$/.test(digit))
            InputContext.inputEngine.virtualKeyClick(Qt.Key_0 + Number(digit), digit, Qt.NoModifier)
    }
    function localeLabel(code) {
        const locale = Qt.locale(code)
        return locale.nativeLanguageName + (locale.nativeTerritoryName ? " · " + locale.nativeTerritoryName : "")
    }
    readonly property var enabledLanguages: keyboardSettings.enabledLocales.length
        ? keyboardSettings.enabledLocales : VirtualKeyboardSettings.activeLocales
    function toggleLanguage(code) {
        const languages = enabledLanguages.slice()
        const index = languages.indexOf(code)
        if (index < 0) languages.push(code)
        else if (languages.length > 1) languages.splice(index, 1)
        else return
        keyboardSettings.enabledLocales = languages
        keyboardSettings.save()
    }
    onRestrictedChanged: if (restricted && page === "emoji") closePanel()
    Connections {
        target: InputContext
        function onInputItemChanged() { bar.closePanel(); bar.numberStrip = false }
    }
    Connections {
        target: bar.Window.window
        function onVisibleChanged() {
            if (!bar.Window.window.visible) { bar.closePanel(); bar.numberStrip = false }
        }
    }
    component Action: Controls.Button {
        id: action
        property bool selected: false
        property string glyph: ""
        property string spoken: text
        objectName: "keybar-" + spoken
        implicitWidth: 44
        implicitHeight: 44
        focusPolicy: Qt.NoFocus
        padding: 3
        Accessible.name: spoken
        contentItem: Item {
            Kirigami.Icon {
                anchors.centerIn: parent
                width: Math.min(23, parent.width)
                height: width
                visible: action.glyph !== ""
                source: action.glyph
                isMask: true
                color: action.selected || action.down ? bar.onAccent : bar.ink
            }
            Controls.Label {
                anchors.centerIn: parent
                visible: action.glyph === ""
                text: action.text
                font.weight: Font.Medium
                font.pixelSize: Math.min(21, Math.max(14, action.height * 0.49))
                color: action.selected || action.down ? bar.onAccent : bar.ink
            }
        }
        background: Rectangle {
            radius: Math.min(10, height / 3)
            topLeftRadius: bar.arabic ? 3 : radius
            topRightRadius: bar.arabic ? radius : 3
            color: action.selected || action.down ? bar.accent : bar.tint
        }
        opacity: enabled ? 1 : 0.55
    }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 5
        anchors.rightMargin: 5
        spacing: 4
        layoutDirection: bar.arabic ? Qt.RightToLeft : Qt.LeftToRight
        Action {
            glyph: "configure"
            spoken: bar.label("إعدادات لوحة المفاتيح", "Keyboard settings")
            selected: bar.page === "settings" || bar.page === "languages"
            Layout.fillHeight: true
            onClicked: bar.openPage("settings")
        }
        Action {
            glyph: "face-smile-symbolic"
            spoken: bar.label("رموز تعبيرية", "Emoji")
            visible: !bar.restricted
            selected: bar.page === "emoji"
            Layout.fillHeight: true
            onClicked: bar.openPage("emoji")
        }
        Action {
            text: "123"
            spoken: bar.label("صف الأرقام", "Number row")
            selected: bar.showNumbers
            visible: !bar.digitsOnly
            Layout.fillHeight: true
            onClicked: { bar.closePanel(); bar.numberStrip = !bar.numberStrip }
        }
        Flickable {
            id: strip
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: buttons.implicitWidth
            contentHeight: height
            boundsBehavior: Flickable.StopAtBounds
            flickableDirection: Flickable.HorizontalFlick
            Row {
                id: buttons
                height: parent.height
                spacing: 3
                Repeater {
                    model: bar.showNumbers ? ["1","2","3","4","5","6","7","8","9","0"]
                        : !bar.restricted && Appearance.showSuggestions ? bar.suggested : []
                    Action {
                        required property string modelData
                        text: modelData
                        width: Math.max(44, Math.min(72, (strip.width - 3 * (buttons.children.length - 2)) / Math.max(1, buttons.children.length - 1)))
                        height: buttons.height
                        onClicked: bar.showNumbers ? bar.enterDigit(modelData) : bar.enterEmoji(modelData)
                    }
                }
            }
        }
    }
    Controls.Popup {
        id: sheet
        objectName: "moosKeyboardSheet"
        parent: bar
        x: bar.arabic ? bar.width - width : 0
        y: bar.height + 2
        width: Math.min(480, bar.width)
        height: Math.min(bar.panelHeight - y - 2, bar.page === "languages" ? 330 : 220)
        padding: 8
        modal: false
        focus: false
        closePolicy: Controls.Popup.CloseOnEscape | Controls.Popup.CloseOnPressOutside
        onClosed: bar.page = ""
        background: Rectangle {
            color: bar.surface
            radius: 13
            border.color: bar.tint
            border.width: 1
        }
        contentItem: ColumnLayout {
            spacing: 4
            LayoutMirroring.enabled: bar.arabic
            LayoutMirroring.childrenInherit: true
            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 40
                Controls.Label {
                    Layout.fillWidth: true
                    text: bar.page === "emoji" ? bar.label("الرموز التعبيرية", "Emoji")
                        : bar.page === "languages" ? bar.label("لغات الكتابة", "Typing languages")
                        : bar.label("إعدادات لوحة المفاتيح", "Keyboard settings")
                    font.weight: Font.DemiBold
                    color: bar.ink
                }
                Action {
                    glyph: "window-close-symbolic"
                    spoken: bar.label("إغلاق", "Close")
                    onClicked: bar.closePanel()
                }
            }
            Loader {
                Layout.fillWidth: true
                Layout.fillHeight: true
                sourceComponent: bar.page === "emoji" ? emojiPage : bar.page === "languages" ? languagesPage : settingsPage
            }
        }
    }
    Component {
        id: emojiPage
        ColumnLayout {
            spacing: 3
            RowLayout {
                Repeater {
                    model: [bar.label("وجوه","Faces"), bar.label("مشاعر","Gestures"), bar.label("أشياء","Objects")]
                    Action {
                        required property int index
                        required property string modelData
                        text: modelData
                        Layout.fillWidth: true
                        selected: index === bar.groupIndex
                        onClicked: bar.groupIndex = index
                    }
                }
            }
            GridView {
                id: grid
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                cellWidth: width / Math.max(1, Math.floor(width / 48))
                cellHeight: 44
                model: bar.groups[bar.groupIndex]
                delegate: Action {
                    required property string modelData
                    text: modelData
                    width: grid.cellWidth - 3
                    height: grid.cellHeight - 3
                    onClicked: bar.enterEmoji(modelData)
                }
            }
        }
    }
    Component {
        id: settingsPage
        Controls.ScrollView {
            id: settingsScroll
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
                width: settingsScroll.availableWidth
                spacing: 2
                Repeater {
                    model: [bar.label("ارتفاع اللوحة","Keyboard height"), bar.label("عتامة الزجاج","Glass opacity")]
                    RowLayout {
                        id: setting
                        required property int index
                        required property string modelData
                        readonly property int value: index === 0 ? Appearance.heightPercent : Appearance.surfaceOpacity
                        readonly property int lower: index === 0 ? 28 : 72
                        readonly property int upper: index === 0 ? 48 : 100
                        function adjust(delta) {
                            const next = Math.max(lower, Math.min(upper, value + delta))
                            if (index === 0) Appearance.heightPercent = next
                            else Appearance.surfaceOpacity = next
                        }
                        Layout.fillWidth: true
                        Controls.Label { Layout.fillWidth: true; color: bar.ink; text: setting.modelData; wrapMode: Text.Wrap }
                        Action {
                            text: "−"
                            spoken: bar.label("تقليل ", "Decrease ") + setting.modelData
                            enabled: setting.value > setting.lower
                            onClicked: setting.adjust(-2)
                        }
                        Controls.Label { text: setting.value + "%"; color: bar.ink; horizontalAlignment: Text.AlignHCenter; Layout.minimumWidth: 45 }
                        Action {
                            text: "+"
                            spoken: bar.label("زيادة ", "Increase ") + setting.modelData
                            enabled: setting.value < setting.upper
                            onClicked: setting.adjust(2)
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Controls.Switch {
                        Layout.fillWidth: true
                        text: bar.label("اقتراح الرموز", "Suggest emoji")
                        focusPolicy: Qt.NoFocus
                        checked: Appearance.showSuggestions
                        onToggled: { Appearance.showSuggestions = checked; if (!checked) Appearance.recentEmoji = "" }
                    }
                    Controls.Button {
                        text: bar.label("لغات الكتابة", "Typing languages")
                        icon.name: "preferences-desktop-locale"
                        focusPolicy: Qt.NoFocus
                        onClicked: bar.page = "languages"
                    }
                }
            }
        }
    }
    Component {
        id: languagesPage
        ListView {
            objectName: "moosTypingLanguages"
            clip: true
            model: VirtualKeyboardSettings.availableLocales
            Controls.ScrollBar.vertical: Controls.ScrollBar {}
            delegate: Controls.CheckDelegate {
                required property string modelData
                objectName: "moos-locale-" + modelData
                width: ListView.view.width
                text: bar.localeLabel(modelData)
                checked: bar.enabledLanguages.includes(modelData)
                enabled: !checked || bar.enabledLanguages.length > 1
                focusPolicy: Qt.NoFocus
                onClicked: bar.toggleLanguage(modelData)
            }
        }
    }
}
