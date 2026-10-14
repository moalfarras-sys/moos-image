pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — Apps and Games. Apps: the twelve categories as chips, the four kinds (All · Linux ·
// Web · Windows · Android), an order (Recommended · Name · Recently updated, when the index can
// say), and every listed app in one virtualised grid. A collection opened from Discover shows its
// own apps and can be added whole ("Add this section"). Games is the same grid on the Games
// category, under a banner of the game stores and launchers.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: appsPage
    required property var win
    readonly property var design: win.design
    readonly property bool games: win.page === "games"
    readonly property var collection: !appsPage.games && win.activeCollection !== ""
                                      ? win.collectionById(win.activeCollection) : null
    readonly property real padding: appsPage.width > win.fs(1000) ? design.space6 : design.space5

    anchors.fill: parent
    visible: win.page === "apps" || win.page === "games"
    transform: pageEnter.shift
    PageEnter { id: pageEnter; win: appsPage.win; target: appsPage }

    // A changed view starts at its top: the Games banner is the grid's header, above row one.
    Connections {
        target: appsPage.win
        function onVisibleAppsChanged() { appGrid.positionViewAtBeginning() }
        function onPageChanged() { if (appsPage.visible) appGrid.positionViewAtBeginning() }
    }

    readonly property string heading: appsPage.games ? win.local("الألعاب", "Games")
        : appsPage.collection ? win.localName(appsPage.collection)
        : win.activeCategory !== "all" ? win.categoryName(win.activeCategory)
        : win.activeKind !== "all" ? win.localName(win.kindDef(win.activeKind))
        : win.local("كل التطبيقات", "All apps")
    readonly property string subheading: appsPage.collection
        ? (win.rtl ? (appsPage.collection.desc_ar || "") : (appsPage.collection.desc_en || ""))
        : ""

    // The banner of the Games page: the catalogue's "play" collection when it has one, else its
    // popular games, else the first games in recommended order.
    readonly property var launchers: {
        var play = appsPage.win.collectionById("play")
        var source = play ? play.apps : appsPage.win.browseOrder
        var out = []
        for (var i = 0; i < source.length && out.length < 4; ++i)
            if (source[i].cat === "fun") out.push(source[i])
        return out
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: appsPage.padding
        anchors.rightMargin: appsPage.padding
        anchors.topMargin: appsPage.design.space2
        spacing: appsPage.design.space3

        // ── heading ──
        // A heading only for a narrowed view (a collection, a category, a kind): unfiltered, the
        // header already says "Apps" and the kind chips carry the count.
        RowLayout {
            Layout.fillWidth: true
            visible: !appsPage.games && (appsPage.collection !== null || appsPage.win.activeCategory !== "all"
                                         || appsPage.win.activeKind !== "all")
            spacing: appsPage.design.space3
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: appsPage.heading
                    color: appsPage.win.txt
                    font.family: appsPage.win.uiFont
                    font.pixelSize: appsPage.win.typePx(24)
                    font.weight: Font.Bold
                    elide: Text.ElideRight
                    Accessible.role: Accessible.Heading
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: appsPage.subheading !== "" ? appsPage.subheading
                                                     : appsPage.win.appsCountText(appsPage.win.visibleApps.length)
                    color: appsPage.win.txt2
                    font.family: appsPage.win.uiFont
                    font.pixelSize: appsPage.win.typePx(13)
                    elide: Text.ElideRight
                }
            }
            ActionButton {
                id: bulkAdd
                win: appsPage.win
                visible: appsPage.collection !== null && appsPage.win.visibleApps.length > 0
                pill: true
                // Demoted from the default Tab chain: document order made this bulk action the
                // pane's FIRST stop, so a keyboard user's first Return queued a whole section. The
                // virtual grid hands focus here explicitly after its arrow-navigated composite; Tab
                // out continues at the rail and Backtab returns to the grid.
                activeFocusOnTab: false
                Keys.onTabPressed: appsPage.win.focusFirstNavItem(Qt.TabFocusReason)
                Keys.onBacktabPressed: appGrid.forceActiveFocus(Qt.BacktabFocusReason)
                label: appsPage.win.rtl ? "أضف كل القسم" : "Add this section"
                glyphName: "download"
                enabled: !appsPage.win.jobIsActive()
                triggered: function() {
                    var ids = []
                    for (var i = 0; i < appsPage.win.visibleApps.length; ++i)
                        ids.push(appsPage.win.visibleApps[i].id)
                    appsPage.win.addMany(ids)
                }
            }
        }

        // ── the categories ──
        Flickable {
            id: chipFlick
            Layout.fillWidth: true
            Layout.preferredHeight: appsPage.win.fs(40)
            visible: !appsPage.games && appsPage.collection === null
            contentWidth: categoryRow.implicitWidth
            contentHeight: height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            // In RTL the mirrored row puts the reading start — the "All" chip — at the RIGHT end
            // of the content, and a fresh Flickable shows the LEFT end. Snap to the reading start
            // when the row's width settles; a guarded reset, never a binding that fights a drag.
            function snapToReadingStart() {
                if (appsPage.win.rtl && !chipFlick.moving && !chipFlick.dragging)
                    chipFlick.contentX = Math.max(0, chipFlick.contentWidth - chipFlick.width)
            }
            onContentWidthChanged: chipFlick.snapToReadingStart()
            onWidthChanged: chipFlick.snapToReadingStart()
            Component.onCompleted: chipFlick.snapToReadingStart()
            EdgeFades { parent: chipFlick; anchors.fill: parent; win: appsPage.win; flick: chipFlick }
            RowLayout {
                id: categoryRow
                height: parent.height
                spacing: appsPage.design.space2
                Repeater {
                    id: categoryRepeater
                    model: [{ id: "all", ar: "الكل", en: "All", glyph: "grid" }].concat(appsPage.win.storeCategories)
                    delegate: KindChip {
                        id: categoryChip
                        required property var modelData
                        win: appsPage.win
                        label: appsPage.win.localName(categoryChip.modelData)
                        glyph: categoryChip.modelData.glyph
                        checked: appsPage.win.activeCategory === categoryChip.modelData.id
                        onActivated: appsPage.win.activeCategory = categoryChip.modelData.id
                    }
                }
            }
        }

        // ── the kinds, and the order ──
        // The kinds scroll sideways when the window is narrow; the order keeps its place at the end.
        RowLayout {
            Layout.fillWidth: true
            spacing: appsPage.design.space3
            Flickable {
                id: kindFlick
                Layout.fillWidth: true
                Layout.preferredHeight: kindRow.implicitHeight
                contentWidth: kindRow.implicitWidth
                contentHeight: height
                clip: true
                interactive: contentWidth > width
                boundsBehavior: Flickable.StopAtBounds
                function snapToReadingStart() {
                    if (appsPage.win.rtl && !kindFlick.moving && !kindFlick.dragging)
                        kindFlick.contentX = Math.max(0, kindFlick.contentWidth - kindFlick.width)
                }
                onContentWidthChanged: kindFlick.snapToReadingStart()
                onWidthChanged: kindFlick.snapToReadingStart()
                Component.onCompleted: kindFlick.snapToReadingStart()
                EdgeFades { parent: kindFlick; anchors.fill: parent; win: appsPage.win; flick: kindFlick }
                RowLayout {
                    id: kindRow
                    height: parent.height
                    spacing: appsPage.design.space2
                    Repeater {
                        model: [{ id: "all", ar: "الكل", en: "All", glyph: "" }].concat(appsPage.win.kindDefs)
                        delegate: KindChip {
                            id: kindChip
                            required property var modelData
                            win: appsPage.win
                            label: kindChip.modelData.id === "all" ? appsPage.win.local("كل الأنواع", "Every kind")
                                                                   : appsPage.win.localName(kindChip.modelData)
                            glyph: kindChip.modelData.glyph
                            count: appsPage.win.viewKindCounts[kindChip.modelData.id] || 0
                            checked: appsPage.win.activeKind === kindChip.modelData.id
                            visible: kindChip.modelData.id === "all" || kindChip.checked
                                     || (appsPage.win.viewKindCounts[kindChip.modelData.id] || 0) > 0
                            onActivated: appsPage.win.activeKind = kindChip.modelData.id
                        }
                    }
                }
            }
            Text {
                text: appsPage.win.local("الترتيب", "Order")
                color: appsPage.win.txt2
                font.family: appsPage.win.uiFont
                font.pixelSize: appsPage.win.typePx(12)
                visible: appsPage.width > appsPage.win.fs(860)
            }
            Repeater {
                model: [
                    { id: "recommended", ar: "المقترح", en: "Recommended" },
                    { id: "name", ar: "الاسم", en: "Name" },
                    { id: "updated", ar: "الأحدث", en: "Recently updated" }
                ]
                delegate: KindChip {
                    id: sortChip
                    required property var modelData
                    win: appsPage.win
                    label: appsPage.win.localName(sortChip.modelData)
                    checked: appsPage.win.sortMode === sortChip.modelData.id
                    visible: sortChip.modelData.id !== "updated" || appsPage.win.canSortByDate
                    onActivated: appsPage.win.sortMode = sortChip.modelData.id
                }
            }
        }

        GridView {
            id: appGrid
            objectName: "appGrid"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: -appsPage.design.space2
            Layout.rightMargin: -appsPage.design.space2
            clip: true
            model: appsPage.visible ? appsPage.win.visibleApps : []
            readonly property int columnCount: Math.max(2, Math.min(5, Math.floor(width / appsPage.win.fs(300))))
            cellWidth: width / columnCount
            cellHeight: appsPage.win.fs(208)
            boundsBehavior: Flickable.StopAtBounds
            reuseItems: true
            cacheBuffer: cellHeight * 2
            bottomMargin: appsPage.win.footClearance
            header: appsPage.games ? gamesBanner : null
            activeFocusOnTab: visible && count > 0
            keyNavigationEnabled: true
            Accessible.role: Accessible.List
            Accessible.name: appsPage.win.rtl ? "شبكة التطبيقات" : "Application grid"
            Accessible.focusable: true
            Accessible.focused: activeFocus
            Accessible.description: currentIndex >= 0 && currentIndex < appsPage.win.visibleApps.length
                ? appsPage.win.localName(appsPage.win.visibleApps[currentIndex]) + ", "
                  + (currentIndex + 1) + " / " + count
                : ""
            Accessible.onPressAction: {
                if (currentIndex >= 0 && currentIndex < appsPage.win.visibleApps.length)
                    appsPage.win.openDetails(appsPage.win.visibleApps[currentIndex])
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
                if (currentIndex >= 0 && currentIndex < appsPage.win.visibleApps.length)
                    appsPage.win.openDetails(appsPage.win.visibleApps[currentIndex])
            }
            Keys.onSpacePressed: {
                if (currentIndex >= 0 && currentIndex < appsPage.win.visibleApps.length)
                    appsPage.win.openDetails(appsPage.win.visibleApps[currentIndex])
            }
            Keys.onTabPressed: (event) => {
                if (bulkAdd.visible) {
                    bulkAdd.forceActiveFocus(Qt.TabFocusReason)
                } else {
                    appsPage.win.focusFirstNavItem(Qt.TabFocusReason)
                }
                event.accepted = true
            }
            Keys.onBacktabPressed: {
                var last = categoryRepeater.itemAt(categoryRepeater.count - 1)
                if (last && chipFlick.visible) last.forceActiveFocus(Qt.BacktabFocusReason)
                else appsPage.win.focusFirstNavItem(Qt.BacktabFocusReason)
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
                    win: appsPage.win
                    anchors.fill: parent
                    anchors.margins: appsPage.design.space2
                    app: gridCell.modelData
                    variant: "grid"
                    compositeFocus: true
                    compositeCurrent: appGrid.activeFocus
                                      && gridCell.index === appGrid.currentIndex
                }
            }
        }
    }

    // Nothing here: said, with a way out.
    ColumnLayout {
        anchors.centerIn: parent
        visible: appsPage.win.visibleApps.length === 0
        spacing: appsPage.design.space2
        Glyph {
            win: appsPage.win
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: appsPage.win.fs(44)
            Layout.preferredHeight: appsPage.win.fs(44)
            name: "search"
            tint: appsPage.win.txt2
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: appsPage.win.local("لا تطبيقات هنا", "No apps here")
            color: appsPage.win.txt
            font.family: appsPage.win.uiFont
            font.pixelSize: appsPage.win.typePx(20)
            font.weight: Font.Bold
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: appsPage.win.local("جرّب فئة أخرى أو نوعًا آخر من التطبيقات.", "Try another category or another kind of app.")
            color: appsPage.win.txt2
            font.family: appsPage.win.uiFont
            font.pixelSize: appsPage.win.typePx(13)
        }
        ActionButton {
            win: appsPage.win
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: appsPage.design.space2
            pill: true
            label: appsPage.win.local("أظهر الكل", "Show everything")
            triggered: function() {
                appsPage.win.activeKind = "all"
                appsPage.win.activeCategory = "all"
            }
        }
    }

    // The Games page's banner: what to play with, on a plate in the theme's own accent.
    Component {
        id: gamesBanner
        Item {
            id: banner
            readonly property color brand: Qt.darker(appsPage.win.accent, appsPage.win.lightScheme ? 1.0 : 1.35)
            readonly property color ink: appsPage.win.inkOn(banner.brand)
            readonly property color base: appsPage.win.readableBase(banner.brand, banner.ink)
            width: appGrid.width
            height: appsPage.win.fs(248)
            SoftShadow { win: appsPage.win; radius: appsPage.design.radiusPanel; strength: 1.4 }
            Rectangle {
                anchors.fill: parent
                anchors.leftMargin: appsPage.design.space2
                anchors.rightMargin: appsPage.design.space2
                anchors.bottomMargin: appsPage.design.space4
                radius: appsPage.design.radiusPanel
                clip: true
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: appsPage.win.rtl ? Qt.darker(banner.base, 1.3) : banner.base }
                    GradientStop { position: 1; color: appsPage.win.rtl ? banner.base : Qt.darker(banner.base, 1.3) }
                }
                Repeater {
                    model: 3
                    delegate: Rectangle {
                        required property int index
                        width: parent.height * (1.4 + index * 0.5)
                        height: width
                        radius: width / 2
                        x: appsPage.win.rtl ? -width * 0.35 : parent.width - width * 0.65
                        y: parent.height * 0.25
                        color: "transparent"
                        border.width: Math.max(1, appsPage.win.fs(1.5))
                        border.color: appsPage.win.tint(banner.ink, 0.14 - index * 0.035)
                    }
                }
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: appsPage.design.space5
                    spacing: appsPage.design.space5
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: banner.width * 0.4
                        spacing: appsPage.design.space2
                        Text {
                            Layout.fillWidth: true
                            text: appsPage.win.local("الألعاب", "Games")
                            color: appsPage.win.tint(banner.ink, 0.8)
                            font.family: appsPage.win.uiFont
                            font.pixelSize: appsPage.win.typePx(13)
                            font.weight: Font.DemiBold
                        }
                        Text {
                            Layout.fillWidth: true
                            text: appsPage.win.local("لعبتك التالية تنتظرك", "Your next game is waiting")
                            color: banner.ink
                            font.family: appsPage.win.uiFont
                            font.pixelSize: appsPage.win.typePx(32)
                            font.weight: Font.Bold
                            wrapMode: Text.WordWrap
                            Accessible.role: Accessible.Heading
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            text: appsPage.win.local("متاجر ألعاب وألعاب كلاسيكية ومجانية، ومع كل لعبة ما يعرفه MoOS عن عملها هنا.",
                                                     "Game stores, classics and free games, each with what MoOS knows about how it runs here.")
                            color: appsPage.win.tint(banner.ink, 0.86)
                            font.family: appsPage.win.uiFont
                            font.pixelSize: appsPage.win.typePx(14)
                            wrapMode: Text.WordWrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                        }
                        Text {
                            Layout.fillWidth: true
                            text: appsPage.win.appsCountText(appsPage.win.visibleApps.length)
                            color: appsPage.win.tint(banner.ink, 0.72)
                            font.family: appsPage.win.uiFont
                            font.pixelSize: appsPage.win.typePx(13)
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: banner.width * 0.5
                        spacing: appsPage.design.space3
                        visible: banner.width > appsPage.win.fs(760)
                        Repeater {
                            model: appsPage.launchers
                            delegate: Rectangle {
                                id: launcher
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredHeight: appsPage.win.fs(150)
                                radius: appsPage.design.radiusCard
                                color: appsPage.win.tint(banner.ink, launcherHover.hovered ? 0.20 : 0.12)
                                border.width: 1
                                border.color: appsPage.win.tint(banner.ink, 0.22)
                                activeFocusOnTab: true
                                Accessible.role: Accessible.Button
                                Accessible.name: appsPage.win.localName(launcher.modelData)
                                Accessible.onPressAction: appsPage.win.openDetails(launcher.modelData)
                                Keys.onReturnPressed: appsPage.win.openDetails(launcher.modelData)
                                FocusRing { win: appsPage.win }
                                HoverHandler { id: launcherHover; cursorShape: Qt.PointingHandCursor }
                                TapHandler { onTapped: appsPage.win.openDetails(launcher.modelData) }
                                ColumnLayout {
                                    anchors.centerIn: parent
                                    width: parent.width - appsPage.design.space4
                                    spacing: appsPage.design.space2
                                    AppIcon {
                                        win: appsPage.win
                                        Layout.alignment: Qt.AlignHCenter
                                        app: launcher.modelData
                                        size: appsPage.win.fs(60)
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: appsPage.win.localName(launcher.modelData)
                                        color: banner.ink
                                        font.family: appsPage.win.uiFont
                                        font.pixelSize: appsPage.win.typePx(13)
                                        font.weight: Font.DemiBold
                                        horizontalAlignment: Text.AlignHCenter
                                        elide: Text.ElideRight
                                    }
                                    ProgressButton {
                                        win: appsPage.win
                                        Layout.alignment: Qt.AlignHCenter
                                        app: launcher.modelData
                                        onColour: true
                                        colourInk: banner.ink
                                        colourBase: banner.base
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
