pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Mo Store — the header over every page: Back (when there is somewhere to go back to), the page's
// name, the search field (Ctrl+K, Ctrl+F or /) and "Add an app from a file". Typing takes the
// window to the search page; Escape clears the field, then goes back. main.qml's shortcuts reach
// the field through focusSearch(), clearSearch(), setSearchText() and searchText.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: header
    required property var win
    readonly property var design: win.design
    readonly property string searchText: searchField.text
    readonly property bool topLevel: win.page !== "app" && win.page !== "search"

    function focusSearch() {
        searchField.forceActiveFocus()
        searchField.selectAll()
    }

    function clearSearch() {
        searchField.clear()
    }

    function setSearchText(text) {
        searchField.text = text
        searchField.forceActiveFocus()
        searchField.cursorPosition = searchField.text.length
    }

    readonly property string backTarget: {
        var stack = header.win.history
        if (stack.length === 0) return ""
        var last = stack[stack.length - 1]
        if (last.page === "app") {
            var app = header.win.appById(last.appId)
            return app ? header.win.localName(app) : ""
        }
        if (last.page === "search") return header.win.local("البحث", "Search")
        for (var i = 0; i < header.win.navItems.length; ++i)
            if (header.win.navItems[i].id === last.page) return header.win.localName(header.win.navItems[i])
        return ""
    }

    readonly property string pageTitle: {
        for (var i = 0; i < header.win.navItems.length; ++i)
            if (header.win.navItems[i].id === header.win.page) return header.win.localName(header.win.navItems[i])
        if (header.win.page === "search") return header.win.local("البحث", "Search")
        return ""
    }

    Layout.fillWidth: true
    Layout.preferredHeight: win.fs(76)

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: header.width > header.win.fs(1000) ? header.design.space6 : header.design.space5
        anchors.rightMargin: header.width > header.win.fs(1000) ? header.design.space6 : header.design.space5
        anchors.topMargin: header.design.space2
        spacing: header.design.space3

        CircleButton {
            win: header.win
            visible: header.win.canGoBack
            glyph: header.win.rtl ? "arrow" : "arrow-back"
            accessibleName: header.backTarget !== "" ? header.win.local("رجوع إلى ", "Back to ") + header.backTarget
                                                     : header.win.local("رجوع", "Back")
            onActivated: header.win.goBack()
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: header.win.fs(120)
            spacing: 0
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                visible: header.topLevel || header.win.page === "search"
                text: header.pageTitle
                color: header.win.txt
                font.family: header.win.uiFont
                font.pixelSize: header.win.typePx(24)
                font.weight: Font.Bold
                elide: Text.ElideRight
                Accessible.role: Accessible.Heading
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                visible: !header.topLevel && header.win.page === "app" && header.backTarget !== ""
                text: header.backTarget
                color: header.win.txt2
                font.family: header.win.uiFont
                font.pixelSize: header.win.typePx(15)
                font.weight: Font.Medium
                elide: Text.ElideRight
            }
        }

        // The search field: one glass pill with its keyboard hint.
        Rectangle {
            id: searchBox
            Layout.preferredWidth: Math.min(header.win.fs(460), header.width * 0.42)
            Layout.preferredHeight: header.win.fs(44)
            radius: height / 2
            color: header.win.glassColor
            border.width: searchField.activeFocus ? 2 : 1
            border.color: searchField.activeFocus ? header.win.accent : header.win.cardBorder
            Behavior on border.color { ColorAnimation { duration: header.win.motionEnabled ? header.design.motionFast : 0 } }
            SoftShadow { win: header.win; radius: searchBox.radius; strength: searchField.activeFocus ? 1.2 : 0.6 }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: header.design.space4
                anchors.rightMargin: header.design.space2
                spacing: header.design.space2
                Glyph {
                    win: header.win
                    name: "search"
                    tint: searchField.activeFocus ? header.win.accent : header.win.txt2
                    Layout.preferredWidth: header.win.fs(18)
                    Layout.preferredHeight: header.win.fs(18)
                }
                TextField {
                    id: searchField
                    Layout.fillWidth: true
                    background: null
                    color: header.win.txt
                    placeholderText: header.win.local("ابحث في التطبيقات والألعاب وتطبيقات الويب…", "Search apps, games and web apps…")
                    placeholderTextColor: header.win.txt2
                    font.family: header.win.uiFont
                    font.pixelSize: header.win.typePx(14)
                    selectByMouse: true
                    Accessible.name: header.win.local("ابحث في متجر MoOS", "Search Mo Store")
                    onTextChanged: header.win.setQuery(text)
                    Keys.onEscapePressed: {
                        if (searchField.text !== "") searchField.clear()
                        else header.win.escapeAction()
                    }
                }
                Rectangle {
                    visible: searchField.text === ""
                    Layout.preferredHeight: header.win.fs(24)
                    Layout.preferredWidth: keyLabel.implicitWidth + header.design.space2 * 2
                    radius: header.design.radiusSmall
                    color: header.win.tint(header.win.txt, header.win.lightScheme ? 0.06 : 0.08)
                    border.width: 1
                    border.color: header.win.cardBorder
                    Text {
                        id: keyLabel
                        anchors.centerIn: parent
                        text: header.win.ltr("Ctrl K")
                        color: header.win.txt2
                        font.family: header.win.uiFont
                        font.pixelSize: header.win.typePx(11)
                    }
                }
                CircleButton {
                    win: header.win
                    visible: searchField.text !== ""
                    size: header.win.fs(30)
                    glyph: "close"
                    accessibleName: header.win.local("امسح البحث", "Clear the search")
                    onActivated: { searchField.clear(); searchField.forceActiveFocus() }
                }
            }
        }

        CircleButton {
            win: header.win
            size: header.win.fs(44)
            glyph: "upload"
            enabled: !header.win.jobIsActive()
            accessibleName: header.win.local("أضف تطبيقًا من ملف", "Add an app from a file")
            onActivated: header.win.openApplicationPicker()
            ToolTip.visible: hovered
            ToolTip.text: accessibleName
            ToolTip.delay: 600
            property bool hovered: false
            HoverHandler { onHoveredChanged: parent.hovered = hovered }
        }
    }
}
