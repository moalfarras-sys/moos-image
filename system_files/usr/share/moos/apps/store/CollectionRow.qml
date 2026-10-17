pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — one Discover row: a collection's title and line, "See all", and its apps as cards in
// a row that scrolls sideways — by its arrows, a horizontal wheel or Shift+wheel, a drag, or the
// keyboard (←/→ between cards, Enter opens one). The row runs in the reading direction and bleeds
// to the page's edges, so the next card shows that there is more. It is virtualised.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
ColumnLayout {
    id: row
    required property var win
    readonly property var design: win.design
    required property var collection
    // The page's side padding: the row reaches past it to the page's edges.
    property real bleed: design.space6
    // A row made on the spot (more from a developer, similar apps) has no page to see in full.
    property bool canSeeAll: true
    readonly property real cardWidth: win.fs(212)
    readonly property real cardHeight: win.fs(256)

    spacing: design.space3

    SectionHeader {
        win: row.win
        Layout.fillWidth: true
        title: row.win.localName(row.collection)
        subtitle: row.win.rtl ? (row.collection.desc_ar || "") : (row.collection.desc_en || "")
        glyph: row.collection.glyph || "spark"
        showAll: row.canSeeAll
        showArrows: list.contentWidth > list.width - row.bleed * 2 + 1
        canPrevious: row.win.rtl ? !list.atXEnd : !list.atXBeginning
        canNext: row.win.rtl ? !list.atXBeginning : !list.atXEnd
        onSeeAll: row.win.openCollection(row.collection.id)
        onPrevious: row.page(-1)
        onNext: row.page(1)
    }

    function page(direction) {
        var stride = row.cardWidth + list.spacing
        var shown = Math.max(1, Math.floor((list.width - row.bleed * 2) / stride))
        var first = list.indexAt(row.win.rtl ? list.contentX + list.width - row.bleed - 2 : list.contentX + row.bleed + 2,
                                 row.cardHeight / 2)
        if (first < 0) first = 0
        var target = Math.max(0, Math.min(list.count - 1, first + direction * shown))
        list.positionViewAtIndex(target, ListView.Beginning)
    }

    ListView {
        id: list
        objectName: "collection-" + row.collection.id
        Layout.fillWidth: true
        Layout.leftMargin: -row.bleed
        Layout.rightMargin: -row.bleed
        Layout.preferredHeight: row.cardHeight + row.design.space6
        leftMargin: row.bleed
        rightMargin: row.bleed
        orientation: ListView.Horizontal
        spacing: row.design.space4
        clip: true
        model: row.collection.apps
        boundsBehavior: Flickable.StopAtBounds
        highlightFollowsCurrentItem: false
        keyNavigationEnabled: true
        cacheBuffer: row.cardWidth * 2
        reuseItems: true
        activeFocusOnTab: count > 0
        Accessible.role: Accessible.List
        Accessible.name: row.win.localName(row.collection)
        Keys.onReturnPressed: if (currentIndex >= 0) row.win.openDetails(row.collection.apps[currentIndex])
        Keys.onEnterPressed: if (currentIndex >= 0) row.win.openDetails(row.collection.apps[currentIndex])
        onActiveFocusChanged: if (activeFocus && count > 0 && currentIndex < 0) currentIndex = 0
        onCurrentIndexChanged: if (activeFocus) positionViewAtIndex(currentIndex, ListView.Contain)
        WheelHandler {
            // Let ListView handle ordinary horizontal wheels and let vertical
            // gestures reach the enclosing page. A general WheelHandler blocks
            // that propagation even if onWheel rejects the event; a nonblocking
            // manual handler would scroll horizontal gestures twice.
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            acceptedModifiers: Qt.ShiftModifier
            onWheel: (event) => {
                var sideways = event.angleDelta.x !== 0 || event.pixelDelta.x !== 0
                var delta = sideways ? (event.pixelDelta.x || event.angleDelta.x)
                                     : (event.pixelDelta.y || event.angleDelta.y)
                var low = list.originX - list.leftMargin
                var high = list.originX + list.contentWidth + list.rightMargin - list.width
                list.contentX = Math.max(low, Math.min(Math.max(low, high), list.contentX - delta))
                event.accepted = true
            }
        }
        delegate: Item {
            id: cell
            required property var modelData
            required property int index
            width: row.cardWidth
            height: row.cardHeight + row.design.space6
            AppCard {
                win: row.win
                app: cell.modelData
                variant: "tile"
                width: row.cardWidth
                height: row.cardHeight
                y: row.design.space2
                compositeFocus: true
                compositeCurrent: list.activeFocus && cell.index === list.currentIndex
            }
        }
    }
}
