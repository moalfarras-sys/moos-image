pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — All apps and Installed share this page: the category chips, "Add this
// section" and the virtualized app grid (one arrow-navigated keyboard stop).
// win.visibleApps is main.qml's filtered, sorted list.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
ColumnLayout {
    id: catalog
    required property var win
    readonly property var design: win.design
    anchors.fill: parent
    anchors.margins: 22
    visible: win.page === "apps" || win.page === "installed"
    spacing: design.space3

    RowLayout {
        Layout.fillWidth: true
        spacing: design.space2
        Flickable {
            id: chipFlick
            Layout.fillWidth: true
            Layout.preferredHeight: win.fs(40)
            contentWidth: categoryRow.implicitWidth
            contentHeight: height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            // In RTL the mirrored row puts the reading start — the active
            // "الكل" chip — at the RIGHT end of the content, and a fresh
            // Flickable shows the LEFT end. Snap to the reading start when
            // the row's width settles. A guarded reset, not a binding: a
            // binding on contentX would fight the user's own drag.
            function snapToReadingStart() {
                if (win.rtl && !chipFlick.moving && !chipFlick.dragging)
                    chipFlick.contentX = Math.max(0, chipFlick.contentWidth - chipFlick.width)
            }
            onContentWidthChanged: chipFlick.snapToReadingStart()
            Component.onCompleted: chipFlick.snapToReadingStart()
            RowLayout {
                id: categoryRow
                height: parent.height
                spacing: 7
                Repeater {
                    id: categoryRepeater
                    model: [{ id: "all", ar: "الكل", en: "All", glyph: "grid" }].concat(win.categoryDefs)
                    delegate: Rectangle {
                        id: categoryPill
                        required property var modelData
                        readonly property bool active: win.activeCategory === modelData.id
                        implicitWidth: pillRow.implicitWidth + 22
                        Layout.preferredHeight: win.fs(36)
                        radius: design.radiusControl
                        color: active ? win.accent
                                      : pillHover.hovered ? win.raised : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.7)
                        border.width: active ? 0 : 1
                        border.color: win.outline
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: win.rtl ? categoryPill.modelData.ar : categoryPill.modelData.en
                        FocusRing { win: catalog.win }
                        HoverHandler { id: pillHover }
                        TapHandler { onTapped: win.activeCategory = categoryPill.modelData.id }
                        Keys.onReturnPressed: win.activeCategory = categoryPill.modelData.id
                        Keys.onSpacePressed: win.activeCategory = categoryPill.modelData.id
                        RowLayout {
                            id: pillRow
                            anchors.centerIn: parent
                            spacing: 6
                            Glyph {
                                win: catalog.win
                                name: categoryPill.modelData.glyph
                                tint: categoryPill.active ? win.accentText : win.txt2
                                Layout.preferredWidth: win.fs(14)
                                Layout.preferredHeight: win.fs(14)
                            }
                            Text {
                                text: win.rtl ? categoryPill.modelData.ar : categoryPill.modelData.en
                                color: categoryPill.active ? win.accentText : win.txt
                                font.family: win.uiFont
                                font.pixelSize: win.typePx(11)
                                font.bold: categoryPill.active
                            }
                        }
                    }
                }
            }
        }
        Text {
            text: win.visibleApps.length + (win.rtl ? " تطبيق" : " apps")
            color: win.txt2
            font.family: win.uiFont
            font.pixelSize: win.typePx(11)
        }
        ActionButton {
            id: bulkAdd
            win: catalog.win
            visible: win.page === "apps" && win.visibleApps.length > 0
            // Demoted from the default Tab chain: document order made this
            // bulk action the pane's FIRST stop, so a keyboard user's first
            // Return queued a whole section. The virtual grid now hands focus
            // here explicitly after its arrow-navigated composite; Tab out
            // continues at the rail and Backtab returns to the grid.
            activeFocusOnTab: false
            Keys.onTabPressed: win.focusFirstNavItem(Qt.TabFocusReason)
            Keys.onBacktabPressed: appGrid.forceActiveFocus(Qt.BacktabFocusReason)
            label: win.rtl ? "أضف كل القسم" : "Add this section"
            glyphName: "download"
            triggered: function() {
                var ids = []
                for (var i = 0; i < win.visibleApps.length; ++i)
                    ids.push(win.visibleApps[i].id)
                win.addMany(ids)
            }
        }
    }

    GridView {
        id: appGrid
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        model: win.visibleApps
        readonly property int columnCount: width > 1020 ? 4 : width > 720 ? 3 : 2
        cellWidth: width / columnCount
        cellHeight: 192
        boundsBehavior: Flickable.StopAtBounds
        activeFocusOnTab: visible && count > 0
        keyNavigationEnabled: true
        Accessible.role: Accessible.List
        Accessible.name: win.rtl ? "شبكة التطبيقات" : "Application grid"
        Accessible.focusable: true
        Accessible.focused: activeFocus
        Accessible.description: currentItem
            ? win.localName(currentItem.modelData) + ", "
              + (currentIndex + 1) + " / " + count
            : ""
        Accessible.onPressAction: {
            if (currentIndex >= 0 && currentIndex < win.visibleApps.length)
                win.openDetails(win.visibleApps[currentIndex])
        }
        onActiveFocusChanged: {
            if (activeFocus && count > 0) {
                if (currentIndex < 0 || currentIndex >= count) currentIndex = 0
                positionViewAtIndex(currentIndex, GridView.Contain)
            }
        }
        onCountChanged: {
            if (count === 0) currentIndex = -1
            else if (currentIndex < 0 || currentIndex >= count)
                currentIndex = 0
        }
        Keys.onReturnPressed: {
            if (currentIndex >= 0 && currentIndex < win.visibleApps.length)
                win.openDetails(win.visibleApps[currentIndex])
        }
        Keys.onSpacePressed: {
            if (currentIndex >= 0 && currentIndex < win.visibleApps.length)
                win.openDetails(win.visibleApps[currentIndex])
        }
        Keys.onTabPressed: (event) => {
            if (bulkAdd.visible) {
                bulkAdd.forceActiveFocus(Qt.TabFocusReason)
            } else {
                win.focusFirstNavItem(Qt.TabFocusReason)
            }
            event.accepted = true
        }
        Keys.onBacktabPressed: {
            var last = categoryRepeater.itemAt(categoryRepeater.count - 1)
            if (last) last.forceActiveFocus(Qt.BacktabFocusReason)
        }
        Keys.onPressed: (event) => MoUI.KeyboardViewport.pageScrollKeys(appGrid, event)
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        delegate: Item {
            id: gridCell
            required property var modelData
            required property int index
            width: appGrid.cellWidth
            height: appGrid.cellHeight
            AppCard {
                win: catalog.win
                anchors.fill: parent
                anchors.margins: 6
                app: gridCell.modelData
                compositeFocus: true
                compositeCurrent: appGrid.activeFocus
                                  && gridCell.index === appGrid.currentIndex
            }
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: win.visibleApps.length === 0
        spacing: design.space2
        Item { Layout.fillHeight: true }
        Glyph {
            win: catalog.win
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: win.fs(42)
            Layout.preferredHeight: win.fs(42)
            name: win.page === "installed" ? "download" : "search"
            tint: win.txt2
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: win.page === "installed"
                ? (win.rtl ? "لا توجد تطبيقات مثبتة في هذا القسم" : "No installed apps in this view")
                : (win.rtl ? "لا توجد نتائج" : "No results")
            color: win.txt
            font.family: win.uiFont
            font.pixelSize: win.typePx(16)
            font.bold: true
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: win.rtl ? "جرّب كلمة بحث أو فئة مختلفة." : "Try another search or category."
            color: win.txt2
            font.family: win.uiFont
            font.pixelSize: win.typePx(11)
        }
        Item { Layout.fillHeight: true }
    }
}
