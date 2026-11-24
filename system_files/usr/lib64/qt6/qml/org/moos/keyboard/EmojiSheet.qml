// SPDX-FileCopyrightText: 2026 Moalfarras — MoOS
// SPDX-License-Identifier: GPL-2.0-or-later

// The emoji sheet: it takes the keys' place while open. Every emoji Plasma's picker knows,
// in Unicode order, scrolls sideways in the typing direction, the person's recent emoji
// first; category tabs jump and follow; delete repeats like the key; holding an emoji that
// comes in skin tones offers them. Its opaque face and catch-all area keep every touch off
// the keys underneath.
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

import "TouchBarLogic.js" as Logic
import "EmojiData.js" as Data

Rectangle {
    id: sheet

    property QtObject theme: null
    property bool rightToLeft: false
    property string language: "en"
    property var recent: []
    property string emojiFamily: "Noto Color Emoji"
    property string symbolFamily: "Noto Emoji"
    property real tabHeight: 44

    signal picked(string emoji)
    signal backspace()

    // Four rows of emoji above the tabs, never smaller than a 24-pixel cell.
    readonly property real cellSize: Math.max(24, Math.floor((height - tabHeight * 1.1) / 4))
    // The grid exists only while the sheet is shown: closed, it costs nothing. (Laid out
    // before the sheet had a height, a 1-pixel cell once made all 1913 emoji at startup.)
    readonly property GridView grid: gridLoader.item
    readonly property int section: grid ? Logic.sectionAt(grid.firstVisible, recent.length) : -1
    readonly property string sectionTitle: section < 0
        ? (language === "ar" ? "المستخدمة مؤخرًا" : "Recently used")
        : Data.categories[section][language === "ar" ? "ar" : "en"]

    color: theme ? Qt.alpha(theme.keyboardBackgroundColor, 1) : Kirigami.Theme.backgroundColor

    function jump(section) {
        tones.close()
        if (grid)
            grid.positionViewAtIndex(section < 0 ? 0 : recent.length + Data.categories[section].start,
                                     GridView.Beginning)
    }
    function reset() {
        tones.close()
        if (grid)
            grid.positionViewAtBeginning()
    }

    // Swallow every press that no emoji, tab or tone takes: the keys lie underneath.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        onWheel: (wheel) => wheel.accepted = true
    }

    Loader {
        id: gridLoader
        anchors {
            left: parent.left
            right: parent.right
            top: parent.top
            bottom: tabs.top
            bottomMargin: Math.round(sheet.tabHeight * 0.1)
        }
        active: sheet.visible && height >= 4 * 24
        sourceComponent: gridComponent
    }

    Component {
        id: gridComponent
        GridView {
            id: grid
            objectName: "moosEmojiGrid"
            clip: true
            flow: GridView.FlowTopToBottom
            layoutDirection: sheet.rightToLeft ? Qt.RightToLeft : Qt.LeftToRight
            boundsBehavior: Flickable.StopAtBounds
            cellHeight: sheet.cellSize
            cellWidth: Math.round(cellHeight * 1.12)
            cacheBuffer: cellWidth * 6
            model: sheet.recent.length + Data.emoji.length
            readonly property int firstVisible: {
                const edge = sheet.rightToLeft ? contentX + width - cellWidth / 2 : contentX + cellWidth / 2
                const found = indexAt(edge, contentY + cellHeight / 2)
                return found < 0 ? 0 : found
            }

            delegate: EmojiCell {
                required property int index
                width: grid.cellWidth
                height: sheet.cellSize
                theme: sheet.theme
                family: sheet.emojiFamily
                emoji: index < sheet.recent.length ? sheet.recent[index] : Data.emoji[index - sheet.recent.length]
                hasTones: index >= sheet.recent.length && Data.tones[index - sheet.recent.length] !== undefined
                accessibleName: Logic.nameOf(emoji, sheet.language)
                onPicked: (emoji) => sheet.picked(emoji)
                onHeld: (cell, emoji) => tones.open(cell, emoji)
            }
        }
    }

    RowLayout {
        id: tabs
        anchors {
            left: parent.left
            right: parent.right
            bottom: parent.bottom
        }
        height: sheet.tabHeight
        spacing: 0
        LayoutMirroring.enabled: sheet.rightToLeft
        LayoutMirroring.childrenInherit: true

        Repeater {
            model: Data.categories.length + 1
            TouchBarButton {
                required property int index
                objectName: "moosEmojiTab-" + (index === 0 ? "recent" : Data.categories[index - 1].key)
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.maximumWidth: sheet.tabHeight * 1.6
                theme: sheet.theme
                rightToLeft: sheet.rightToLeft
                filled: false
                selected: sheet.section === index - 1
                // VS15 asks for each symbol's text form: Qt 6.11 otherwise sends emoji
                // to the colour font whatever family is named. One ink, like the keys.
                glyph: (index === 0 ? "\u{1F558}" : Data.categories[index - 1].glyph) + "\ufe0e"
                glyphFamily: sheet.symbolFamily
                glyphSize: Math.round(height * 0.42)
                accessibleName: index === 0 ? (sheet.language === "ar" ? "المستخدمة مؤخرًا" : "Recently used")
                                            : Data.categories[index - 1][sheet.language === "ar" ? "ar" : "en"]
                onActivated: sheet.jump(index - 1)
            }
        }
        Item { Layout.fillWidth: true }
        TouchBarButton {
            Layout.preferredWidth: Math.round(sheet.tabHeight * 1.7)
            Layout.fillHeight: true
            theme: sheet.theme
            rightToLeft: sheet.rightToLeft
            objectName: "moosEmojiDelete"
            iconName: "edit-clear-symbolic"
            repeats: true
            accessibleName: sheet.language === "ar" ? "حذف" : "Delete"
            onActivated: sheet.backspace()
        }
    }

    // Skin tones: the held emoji and its five variants, above the cell it came from.
    MouseArea {
        anchors.fill: parent
        visible: tones.visible
        z: 9
        onPressed: tones.close()
    }
    Rectangle {
        id: tones
        visible: false
        z: 10
        property var choices: []
        width: toneRow.implicitWidth + Math.round(sheet.cellSize * 0.2)
        height: sheet.cellSize + Math.round(sheet.cellSize * 0.2)
        radius: sheet.theme ? sheet.theme.popupRadius : height / 4
        topLeftRadius: sheet.rightToLeft ? (sheet.theme ? sheet.theme.squareRadius : 2) : radius
        topRightRadius: sheet.rightToLeft ? radius : (sheet.theme ? sheet.theme.squareRadius : 2)
        color: sheet.theme ? sheet.theme.popupBackgroundColor : Kirigami.Theme.backgroundColor
        border.width: 1
        border.color: sheet.theme ? sheet.theme.popupBorderColor : Kirigami.Theme.disabledTextColor

        function open(cell, emoji) {
            const found = Logic.tonesOf(emoji)
            if (found.length === 0)
                return
            choices = found
            const at = cell.mapToItem(sheet, cell.width / 2, 0)
            x = Math.max(0, Math.min(sheet.width - width, at.x - width / 2))
            y = Math.max(0, at.y - height * 0.6)
            visible = true
        }
        function close() {
            visible = false
            choices = []
        }

        Row {
            id: toneRow
            anchors.centerIn: parent
            LayoutMirroring.enabled: sheet.rightToLeft
            Repeater {
                model: tones.choices
                EmojiCell {
                    required property string modelData
                    width: Math.round(sheet.cellSize * 1.04)
                    height: sheet.cellSize
                    theme: sheet.theme
                    family: sheet.emojiFamily
                    emoji: modelData
                    accessibleName: Logic.nameOf(modelData, sheet.language)
                    onPicked: (emoji) => { tones.close(); sheet.picked(emoji) }
                }
            }
        }
    }
}
