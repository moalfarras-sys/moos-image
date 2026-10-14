pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — the page title, "Add app" and the search field. main.qml's shortcuts
// (Ctrl+K, Ctrl+F, Escape) reach the field through focusSearch(), clearSearch() and
// searchText.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: header
    required property var win
    readonly property var design: win.design
    readonly property string searchText: searchField.text

    function focusSearch() {
        searchField.forceActiveFocus()
    }

    function clearSearch() {
        searchField.clear()
    }

    Layout.fillWidth: true
    Layout.preferredHeight: win.fs(82)
    color: Qt.rgba(win.chrome.r, win.chrome.g, win.chrome.b, 0.55)
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 26
        anchors.rightMargin: 26
        spacing: design.space4
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            Text {
                text: {
                    for (var i = 0; i < win.navItems.length; ++i)
                        if (win.navItems[i].id === win.page)
                            return win.rtl ? win.navItems[i].ar : win.navItems[i].en
                    return "Mo Store"
                }
                color: win.txt
                font.family: win.uiFont
                font.pixelSize: win.typePx(22)
                font.bold: true
            }
            Text {
                text: win.page === "discover"
                    ? (win.rtl ? "تطبيقات آمنة، مرتبة لك، وكل المصادر في مكان واحد"
                               : "Trusted apps, smart discovery, every source in one place")
                    : win.visibleApps.length + (win.rtl ? " نتيجة" : " results")
                color: win.txt2
                font.family: win.uiFont
                font.pixelSize: win.typePx(11)
            }
        }

        MoUI.Button {
            label: win.local("إضافة تطبيق", "Add app")
            enabled: !win.jobIsActive()
            onClicked: win.openApplicationPicker()
            Accessible.description: win.local("اختر ملف تطبيق للمراجعة والتثبيت", "Choose an application file to review and install")
        }
        Rectangle {
            Layout.preferredWidth: Math.min(350, win.width * 0.28)
            Layout.preferredHeight: win.fs(46)
            radius: design.radiusCard
            color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.82)
            border.width: searchField.activeFocus ? 1.5 : 1
            border.color: searchField.activeFocus ? win.accent : win.outline
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 13
                anchors.rightMargin: 11
                spacing: design.space2
                Glyph {
                    win: header.win
                    name: "search"
                    tint: searchField.activeFocus ? win.accent : win.txt2
                    Layout.preferredWidth: win.fs(17)
                    Layout.preferredHeight: win.fs(17)
                }
                TextField {
                    id: searchField
                    Layout.fillWidth: true
                    background: null
                    color: win.txt
                    placeholderText: win.rtl ? "ابحث في كل التطبيقات…" : "Search every app…"
                    placeholderTextColor: win.txt2
                    font.family: win.uiFont
                    font.pixelSize: win.typePx(13)
                    selectByMouse: true
                    onTextChanged: {
                        win.query = text
                        if (text.trim() !== "" && win.page === "discover")
                            win.page = "apps"
                    }
                    Keys.onEscapePressed: clear()
                }
                Text {
                    visible: searchField.text === ""
                    text: "Ctrl K"
                    color: win.txt2
                    font.family: win.uiFont
                    font.pixelSize: win.typePx(9)
                }
            }
        }
    }
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: win.outline; opacity: 0.45 }
}
