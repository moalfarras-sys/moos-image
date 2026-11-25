// SPDX-FileCopyrightText: 2026 Moalfarras — MoOS
// SPDX-License-Identifier: GPL-2.0-or-later

// The MoOS Touch Bar: a strip of glass over the on-screen keyboard's keys that changes with
// what the person is doing, the way a Touch Bar does.
//
//   [ 😊 ]  [ suggestions … | matching emoji ]  [ ◀ ▶ ] [ ⚙ ]
//
// • While a word is being written it suggests how to finish it — from the words this
//   person has written on this keyboard (Plasma switches Qt Virtual Keyboard's own
//   prediction off; an input method that still offers candidates, such as Pinyin, shows
//   its own list here instead) — and emoji whose Arabic, English or German keywords fit.
//   A suggestion replaces the word and adds a space; holding one forgets it.
// • Otherwise it is an emoji scrubber: emoji for the word just written, else recent ones.
// • 😊 opens the emoji sheet over the keys; ⌨ brings the keys back.
// • ◀ ▶ move the text cursor (held, they repeat); ⚙ opens the bar's own settings in the
//   keys' place — learning on/off, forget learned words, clear recent emoji — and from
//   there Plasma's keyboard page in System Settings.
// • In a password or other sensitive field it suggests nothing and records nothing, and
//   offers no settings; on the login screen (the plasmalogin account) it offers only the
//   cursor keys.
//
// It only drives the input method's public API: InputContext.commit() — an emoji, or a
// word with a replacement range — the candidate list's selectItem(), and the engine's
// virtualKeyClick() for the cursor and delete keys. The keyboard style places it (see
// style.qml, "MoOS:").
import QtQuick
import QtQuick.Layouts
import QtCore
import org.kde.kirigami as Kirigami

import "TouchBarLogic.js" as Logic

Item {
    id: root

    // Supplied by the keyboard style.
    property QtObject inputContext: null
    property QtObject theme: null
    property real barHeight: 48
    property real bandHeight: barHeight + 8
    property real sideInset: 0
    property bool rightToLeft: false
    property string emojiFamily: "Noto Color Emoji"
    property bool desktopBar: false
    property bool keysShown: false
    readonly property bool toolsOpen: sheetOpen || settingsOpen
    signal toggleKeys()
    signal resetKeys()
    signal feedback()

    property bool systemTools: false
    readonly property bool showSystemTools: systemTools && !toolsOpen && !sensitive && !greeter
    property bool sheetOpen: false
    property bool settingsOpen: false
    property int activeCandidate: -1
    readonly property var recent: Logic.parseRecent(store.recentEmoji)
    // The person's own words (word → times written); revision re-runs the bindings.
    property var vocabulary: ({})
    property int vocabularyRevision: 0

    readonly property QtObject engine: inputContext ? inputContext.inputEngine : null
    readonly property QtObject candidates: engine ? engine.wordCandidateListModel : null
    readonly property int hints: inputContext ? inputContext.inputMethodHints : 0
    readonly property bool sensitive: (hints & (Qt.ImhHiddenText | Qt.ImhSensitiveData)) !== 0
    readonly property bool greeter: Logic.isGreeterHome(StandardPaths.writableLocation(StandardPaths.HomeLocation))
    readonly property bool emojiAllowed: !greeter && !sensitive && (hints & (Qt.ImhDigitsOnly | Qt.ImhFormattedNumbersOnly
                                          | Qt.ImhDialableCharactersOnly | Qt.ImhEmailCharactersOnly
                                          | Qt.ImhUrlCharactersOnly)) === 0
    readonly property bool candidateMode: !sensitive && candidates !== null && candidates.count > 0
    readonly property string word: inputContext && !sensitive
        ? Logic.currentWord(inputContext.preeditText, inputContext.surroundingText, inputContext.cursorPosition) : ""
    readonly property string partial: inputContext && emojiAllowed && inputContext.preeditText.length === 0
        ? Logic.partialWord(inputContext.surroundingText, inputContext.cursorPosition) : ""
    readonly property var suggestions: vocabularyRevision >= 0 && !candidateMode && partial.length > 0
        ? Logic.suggestWords(vocabulary, partial, 3) : []
    readonly property bool composing: candidateMode || suggestions.length > 0
    readonly property var wordEmoji: emojiAllowed && word.length > 1 ? Logic.emojiFor(word, composing ? 4 : 10) : []
    readonly property string language: Qt.locale().name.indexOf("ar") === 0 ? "ar" : "en"

    function commitEmoji(emoji) {
        if (!inputContext || !emojiAllowed)
            return
        root.feedback()
        // The word before it is finished: learn it, as a typed space would.
        learnWord(Logic.partialWord(inputContext.surroundingText, inputContext.cursorPosition))
        // One commit of the whole sequence. A key event carrying this text would reach
        // plasma-keyboard 6.8.3's InputListenerItem, which commits a key's text once per
        // keysym: "❤️" (U+2764 U+FE0F) arrived twice, a family emoji five times.
        if (inputContext.preeditText.length > 0)
            inputContext.commit()
        inputContext.commit(emoji)
        store.recentEmoji = JSON.stringify(Logic.pushRecent(root.recent, emoji))
    }
    function sendKey(key) {
        if (!engine)
            return
        root.feedback()
        engine.virtualKeyClick(key, "", Qt.NoModifier)
    }
    function chooseCandidate(index) {
        if (candidateMode) {
            if (index < 0 || index >= candidates.count)
                return
            root.feedback()
            candidates.selectItem(index)
            return
        }
        const chosen = suggestions[index]
        const typed = partial
        if (!chosen || typed.length === 0 || !inputContext)
            return
        root.feedback()
        // Replace the letters before the cursor with the whole word and a space.
        inputContext.commit(chosen + " ", -typed.length, typed.length)
        learnWord(chosen)
    }
    function learnWord(word) {
        if (!emojiAllowed || !store.learnWords || !Logic.learn(vocabulary, word))
            return
        vocabularyRevision += 1
        saveWords.restart()
    }
    function forgetCandidate(index) {
        if (candidateMode || !suggestions[index])
            return
        root.feedback()
        Logic.forget(vocabulary, suggestions[index])
        vocabularyRevision += 1
        saveWords.restart()
    }
    function setLearning(on) {
        root.feedback()
        store.learnWords = on
    }
    function forgetAllWords() {
        root.feedback()
        vocabulary = ({})
        vocabularyRevision += 1
        saveWords.stop()
        store.learnedWords = "{}"
    }
    function clearRecentEmoji() {
        root.feedback()
        store.recentEmoji = "[]"
    }
    function openSettings() {
        if (greeter || sensitive)
            return
        root.feedback()
        root.sheetOpen = false
        root.settingsOpen = false
        const panel = root.Window.window
        if (panel && typeof panel.showSettings === "function")
            panel.showSettings()
    }

    onSheetOpenChanged: if (sheetOpen) { settingsOpen = false; sheet.recent = root.recent; sheet.reset() }
    onSettingsOpenChanged: if (settingsOpen) sheetOpen = false
    Component.onCompleted: vocabulary = Logic.parseWords(store.learnedWords)
    onEmojiAllowedChanged: if (!emojiAllowed) sheetOpen = false
    onHintsChanged: { sheetOpen = false; settingsOpen = false; systemTools = false }
    onDesktopBarChanged: { sheetOpen = false; settingsOpen = false; resetKeys() }

    Connections {
        target: root.candidates
        function onActiveItemChanged(index) { root.activeCandidate = index }
        function onCountChanged() { if (root.candidates.count === 0) root.activeCandidate = -1 }
    }
    // A word is finished when the person types a space, Return, punctuation or an emoji.
    Connections {
        target: root.engine
        function onVirtualKeyClicked(key, text, modifiers, isAutoRepeat) {
            if (!isAutoRepeat && root.emojiAllowed && root.inputContext
                    && Logic.endsWord(key, text, Qt.Key_Space, Qt.Key_Return))
                root.learnWord(Logic.partialWord(root.inputContext.surroundingText, root.inputContext.cursorPosition))
        }
    }
    Connections {
        target: root.Window.window
        function onVisibleChanged() {
            if (!root.Window.window.visible) {
                root.sheetOpen = false
                root.settingsOpen = false
                root.systemTools = false
                root.resetKeys()
            }
        }
    }

    // Recent emoji and the person's own words stay in their own config
    // (~/.config/moos-keyboardrc): never from a password, sensitive, e-mail or web field.
    Settings {
        id: store
        location: StandardPaths.writableLocation(StandardPaths.GenericConfigLocation) + "/moos-keyboardrc"
        category: "TouchBar"
        property string recentEmoji: "[]"
        property string learnedWords: "{}"
        property bool learnWords: true
    }
    Timer {
        id: saveWords
        interval: 1500
        onTriggered: store.learnedWords = JSON.stringify(root.vocabulary)
    }

    Item {
        id: bar
        anchors {
            left: parent.left
            right: parent.right
            leftMargin: root.sideInset
            rightMargin: root.sideInset
        }
        y: Math.round((root.bandHeight - root.barHeight) / 2)
        height: root.barHeight
        LayoutMirroring.enabled: root.rightToLeft
        LayoutMirroring.childrenInherit: true

        RowLayout {
            anchors.fill: parent
            spacing: Math.round(root.barHeight * 0.1)

            TouchBarButton {
                id: emojiSwitch
                objectName: "moosTouchBarEmojiSwitch"
                Layout.preferredWidth: Math.round(root.barHeight * 1.35)
                Layout.fillHeight: true
                theme: root.theme
                rightToLeft: root.rightToLeft
                enabled: root.emojiAllowed
                selected: root.sheetOpen
                glyph: "😊"
                glyphFamily: root.emojiFamily
                glyphSize: Math.round(height * 0.5)
                iconName: root.sheetOpen ? "input-keyboard-virtual-symbolic" : ""
                accessibleName: root.sheetOpen ? (root.language === "ar" ? "لوحة المفاتيح" : "Keyboard")
                                               : (root.language === "ar" ? "الرموز التعبيرية" : "Emoji")
                onActivated: { root.feedback(); root.sheetOpen = !root.sheetOpen }
            }

            Item {
                id: middle
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                // Writing a word: the input method's suggestions, then emoji for it.
                RowLayout {
                    anchors.fill: parent
                    spacing: 0
                    enabled: root.composing && !root.toolsOpen && !root.showSystemTools
                    opacity: enabled ? 1 : 0
                    visible: opacity > 0
                    Behavior on opacity { NumberAnimation { duration: Kirigami.Units.shortDuration } }

                    ListView {
                        id: words
                        objectName: "moosTouchBarWords"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        orientation: ListView.Horizontal
                        boundsBehavior: Flickable.StopAtBounds
                        interactive: contentWidth > width
                        model: root.candidateMode ? root.candidates : root.suggestions
                        delegate: Item {
                            id: chip
                            required property int index
                            required property var model
                            readonly property string display: root.candidateMode ? String(model.display)
                                                                                  : String(model.modelData)
                            // Pinyin and the like mark the candidate Space commits; for the
                            // person's own words the first, most written one leads.
                            readonly property bool active: root.candidateMode ? index === root.activeCandidate
                                                                              : index === 0
                            readonly property bool quoted: root.candidateMode && index === 0 && root.activeCandidate > 0
                            height: ListView.view.height
                            width: Math.max(Math.round(root.barHeight * 1.8),
                                            Math.min(label.implicitWidth + Math.round(root.barHeight * 0.8),
                                                     Math.round(words.width * 0.6)))

                            TouchBarButton {
                                anchors.fill: parent
                                theme: root.theme
                                rightToLeft: root.rightToLeft
                                filled: false
                                selected: chip.active
                                accessibleName: chip.display
                                onActivated: root.chooseCandidate(chip.index)
                                onHeld: root.forgetCandidate(chip.index)
                            }
                            Text {
                                id: label
                                anchors.centerIn: parent
                                width: Math.min(implicitWidth, parent.width - Math.round(root.barHeight * 0.5))
                                elide: Text.ElideRight
                                text: chip.quoted ? "«" + chip.display + "»" : chip.display
                                color: chip.active ? Kirigami.Theme.highlightedTextColor
                                                   : (root.theme ? root.theme.glassInk : Kirigami.Theme.textColor)
                                font.family: root.theme ? root.theme.fontFamily : ""
                                font.weight: chip.active ? Font.DemiBold : Font.Normal
                                font.pixelSize: Math.round(root.barHeight * 0.4)
                            }
                            Rectangle {
                                visible: chip.index < words.count - 1 && !chip.active
                                         && !(words.itemAtIndex(chip.index + 1) && words.itemAtIndex(chip.index + 1).active)
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.right: parent.right
                                width: 1
                                height: Math.round(parent.height * 0.42)
                                color: root.theme ? root.theme.selectionListSeparatorColor : Kirigami.Theme.disabledTextColor
                            }
                        }
                    }
                    Rectangle {
                        visible: emojiForWord.count > 0
                        Layout.preferredWidth: 1
                        Layout.preferredHeight: Math.round(root.barHeight * 0.5)
                        Layout.leftMargin: Math.round(root.barHeight * 0.12)
                        Layout.rightMargin: Math.round(root.barHeight * 0.12)
                        color: root.theme ? root.theme.selectionListSeparatorColor : Kirigami.Theme.disabledTextColor
                    }
                    Row {
                        Layout.fillHeight: true
                        Repeater {
                            id: emojiForWord
                            model: root.composing ? root.wordEmoji : []
                            EmojiCell {
                                required property string modelData
                                width: Math.round(root.barHeight * 1.1)
                                height: root.barHeight
                                theme: root.theme
                                family: root.emojiFamily
                                emoji: modelData
                                accessibleName: Logic.nameOf(modelData, root.language)
                                onPicked: (emoji) => root.commitEmoji(emoji)
                            }
                        }
                    }
                }

                Loader {
                    anchors.fill: parent
                    active: root.showSystemTools
                    enabled: active
                    sourceComponent: SystemStrip {
                        rtl: root.rightToLeft
                        language: root.language
                        compact: true
                        inInputPanel: true
                        opacity: 0
                        Component.onCompleted: appear.start()
                        NumberAnimation on opacity {
                            id: appear
                            running: false
                            from: 0; to: 1
                            duration: Kirigami.Units.shortDuration
                            easing.type: Easing.OutCubic
                        }
                    }
                }

                // Between words: an emoji scrubber.
                ListView {
                    id: scrubber
                    objectName: "moosTouchBarScrubber"
                    anchors.fill: parent
                    orientation: ListView.Horizontal
                    boundsBehavior: Flickable.StopAtBounds
                    enabled: !root.composing && !root.toolsOpen && !root.showSystemTools && root.emojiAllowed
                    opacity: enabled ? 1 : 0
                    visible: opacity > 0
                    Behavior on opacity { NumberAnimation { duration: Kirigami.Units.shortDuration } }
                    model: root.wordEmoji.length > 0 ? root.wordEmoji : Logic.recentOrPopular(root.recent, 24)
                    delegate: EmojiCell {
                        required property string modelData
                        width: Math.round(root.barHeight * 1.1)
                        height: ListView.view.height
                        theme: root.theme
                        family: root.emojiFamily
                        emoji: modelData
                        accessibleName: Logic.nameOf(modelData, root.language)
                        onPicked: (emoji) => root.commitEmoji(emoji)
                    }
                }

                // The emoji sheet is open: the bar names where it is.
                Text {
                    anchors.centerIn: parent
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    opacity: root.sheetOpen || root.settingsOpen ? 1 : 0
                    visible: opacity > 0
                    Behavior on opacity { NumberAnimation { duration: Kirigami.Units.shortDuration } }
                    text: root.settingsOpen ? (root.language === "ar" ? "إعدادات الشريط" : "Touch Bar settings")
                                            : sheet.sectionTitle
                    color: root.theme ? root.theme.keySmallTextColor : Kirigami.Theme.textColor
                    font.family: root.theme ? root.theme.fontFamily : ""
                    font.pixelSize: Math.round(root.barHeight * 0.36)
                }

                // A password or other sensitive field.
                RowLayout {
                    anchors.centerIn: parent
                    visible: root.sensitive
                    spacing: Math.round(root.barHeight * 0.15)
                    Kirigami.Icon {
                        Layout.preferredWidth: Math.round(root.barHeight * 0.4)
                        Layout.preferredHeight: Layout.preferredWidth
                        source: "object-locked-symbolic"
                        isMask: true
                        color: root.theme ? root.theme.keySmallTextColor : Kirigami.Theme.textColor
                    }
                    Text {
                        text: root.language === "ar" ? "إدخال محمي — لا اقتراحات ولا سجل"
                                                     : "Protected input — no suggestions, nothing recorded"
                        color: root.theme ? root.theme.keySmallTextColor : Kirigami.Theme.textColor
                        font.family: root.theme ? root.theme.fontFamily : ""
                        font.pixelSize: Math.round(root.barHeight * 0.32)
                    }
                }
            }

            // The cursor keys keep their screen direction in either language.
            Row {
                visible: !root.showSystemTools || bar.width >= 420
                Layout.fillHeight: true
                LayoutMirroring.enabled: false
                LayoutMirroring.childrenInherit: true
                spacing: Math.round(root.barHeight * 0.06)
                Repeater {
                    model: !root.desktopBar && !root.toolsOpen && !root.showSystemTools
                           && !root.sensitive && !root.greeter && bar.width >= 18 * root.barHeight
                           ? [Qt.Key_Home, Qt.Key_End] : []
                    TouchBarButton {
                        required property int modelData
                        width: Math.round(root.barHeight * 1.15)
                        height: parent.height
                        theme: root.theme
                        rightToLeft: root.rightToLeft
                        readonly property bool start: modelData === Qt.Key_Home
                        objectName: start ? "moosTouchBarHome" : "moosTouchBarEnd"
                        iconName: start !== root.rightToLeft ? "go-first-symbolic" : "go-last-symbolic"
                        accessibleName: start ? (root.language === "ar" ? "أول السطر" : "Start of line")
                                              : (root.language === "ar" ? "آخر السطر" : "End of line")
                        onActivated: root.sendKey(modelData)
                    }
                }
                TouchBarButton {
                    objectName: "moosTouchBarLeft"
                    width: Math.round(root.barHeight * 1.15)
                    height: parent.height
                    theme: root.theme
                    rightToLeft: root.rightToLeft
                    iconName: "arrow-left-symbolic"
                    repeats: true
                    accessibleName: root.language === "ar" ? "تحريك المؤشر يسارًا" : "Move cursor left"
                    onActivated: root.sendKey(Qt.Key_Left)
                }
                TouchBarButton {
                    objectName: "moosTouchBarRight"
                    width: Math.round(root.barHeight * 1.15)
                    height: parent.height
                    theme: root.theme
                    rightToLeft: root.rightToLeft
                    iconName: "arrow-right-symbolic"
                    repeats: true
                    accessibleName: root.language === "ar" ? "تحريك المؤشر يمينًا" : "Move cursor right"
                    onActivated: root.sendKey(Qt.Key_Right)
                }
            }
            TouchBarButton {
                objectName: "moosTouchBarSystem"
                visible: !root.greeter && !root.sensitive
                Layout.preferredWidth: root.barHeight
                Layout.fillHeight: true
                theme: root.theme
                rightToLeft: root.rightToLeft
                iconName: "moos-system-symbolic"
                selected: root.showSystemTools
                accessibleName: root.language === "ar" ? "أدوات النظام" : "System tools"
                onActivated: {
                    root.feedback()
                    const open = !root.showSystemTools
                    root.sheetOpen = false
                    root.settingsOpen = false
                    root.systemTools = open
                }
            }
            TouchBarButton {
                objectName: "moosTouchBarKeys"
                visible: root.desktopBar
                Layout.preferredWidth: root.barHeight
                Layout.fillHeight: true
                theme: root.theme
                rightToLeft: root.rightToLeft
                selected: root.keysShown
                iconName: root.keysShown ? "moos-session-hide-keyboard-symbolic" : "moos-session-show-keyboard-symbolic"
                accessibleName: root.keysShown
                    ? (root.language === "ar" ? "إخفاء صفوف المفاتيح" : "Hide key rows")
                    : (root.language === "ar" ? "إظهار صفوف المفاتيح" : "Show key rows")
                onActivated: {
                    root.feedback()
                    root.sheetOpen = false
                    root.settingsOpen = false
                    root.toggleKeys()
                }
            }
            TouchBarButton {
                objectName: "moosTouchBarSettings"
                // Nothing opens over a password field, a lock screen or the login screen.
                visible: !root.greeter && !root.sensitive
                Layout.preferredWidth: Math.round(root.barHeight * 1.15)
                Layout.fillHeight: true
                theme: root.theme
                rightToLeft: root.rightToLeft
                selected: root.settingsOpen
                iconName: "settings-configure"
                accessibleName: root.language === "ar" ? "إعدادات لوحة المفاتيح" : "Keyboard settings"
                onActivated: { root.feedback(); root.settingsOpen = !root.settingsOpen }
            }
        }
    }

    // A hairline between the bar and the keys.
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.bandHeight - 1
        width: parent.width - root.sideInset * 2 - Math.round(root.barHeight * 0.6)
        height: 1
        visible: !root.sheetOpen && !root.settingsOpen
        color: root.theme ? root.theme.selectionListSeparatorColor : Kirigami.Theme.disabledTextColor
    }

    EmojiSheet {
        id: sheet
        objectName: "moosEmojiSheet"
        anchors {
            left: parent.left
            right: parent.right
            bottom: parent.bottom
            leftMargin: root.sideInset
            rightMargin: root.sideInset
        }
        height: Math.max(0, parent.height - root.bandHeight)
        theme: root.theme
        rightToLeft: root.rightToLeft
        language: root.language
        emojiFamily: root.emojiFamily
        tabHeight: Math.max(44, Math.round(height * 0.2))
        opacity: root.sheetOpen ? 1 : 0
        visible: opacity > 0
        enabled: root.sheetOpen
        transform: Translate {
            y: root.sheetOpen ? 0 : Math.round(root.barHeight * 0.3)
            Behavior on y { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
        }
        Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
        onPicked: (emoji) => root.commitEmoji(emoji)
        onBackspace: root.sendKey(Qt.Key_Backspace)
    }

    SettingsSheet {
        objectName: "moosKeyboardSettingsSheet"
        anchors {
            left: parent.left
            right: parent.right
            bottom: parent.bottom
            leftMargin: root.sideInset
            rightMargin: root.sideInset
        }
        height: Math.max(0, parent.height - root.bandHeight)
        theme: root.theme
        rightToLeft: root.rightToLeft
        language: root.language
        rowHeight: Math.max(48, Math.round(root.barHeight * 1.1))
        learning: store.learnWords
        learnedCount: root.vocabularyRevision >= 0 ? Object.keys(root.vocabulary).length : 0
        recentCount: root.recent.length
        opacity: root.settingsOpen ? 1 : 0
        visible: opacity > 0
        enabled: root.settingsOpen
        Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
        onLearningToggled: (on) => root.setLearning(on)
        onForgetWords: root.forgetAllWords()
        onClearRecent: root.clearRecentEmoji()
        onAllSettings: root.openSettings()
    }
}
