pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — one app as a card: artwork, name, publisher, summary, source badge and
// its one action. Discover lays cards out in a grid; the catalogue's virtual
// GridView makes the whole grid one keyboard stop (compositeFocus) and marks its
// current card (compositeCurrent).
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: card
    required property var win
    readonly property var design: win.design
    required property var app
    // A virtual GridView is one keyboard composite: making each instantiated delegate a
    // Tab stop strands keyboard users on only the visible cache window. Discover cards keep
    // their normal independent stops; the catalogue grid opts into arrow-key navigation.
    property bool compositeFocus: false
    property bool compositeCurrent: false
    property bool selected: win.isPicked(app.id)
    property bool installed: win.isInstalled(app)
    radius: design.radiusCard
    color: cardHover.hovered
         ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.98)
         : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.82)
    border.width: selected ? 2 : 1
    border.color: card.selected ? win.accent
                 : cardHover.hovered ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.56)
                                     : win.outline
    scale: cardHover.hovered ? 1.012 : 1
    activeFocusOnTab: !card.compositeFocus
    Accessible.role: Accessible.ListItem
    FocusRing { win: card.win; visible: card.activeFocus || card.compositeCurrent }
    Accessible.name: win.localName(app) + ", " + win.sourceLabel(app)
    HoverHandler { id: cardHover }
    TapHandler { onTapped: win.openDetails(card.app) }
    Keys.onReturnPressed: win.openDetails(card.app)
    Keys.onSpacePressed: win.openDetails(card.app)
    Behavior on color { ColorAnimation { duration: win.motionEnabled ? design.motionPress : 0 } }
    Behavior on border.color { ColorAnimation { duration: win.motionEnabled ? design.motionPress : 0 } }
    Behavior on scale { NumberAnimation { duration: win.motionEnabled ? design.motionPress : 0; easing.type: Easing.OutQuad } }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 9
        RowLayout {
            Layout.fillWidth: true
            spacing: 11
            AppArtwork { win: card.win; app: card.app; size: 48 }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    Layout.fillWidth: true
                    text: win.localName(card.app)
                    color: win.txt
                    font.family: win.uiFont
                    font.pixelSize: win.typePx(15)
                    font.bold: true
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: card.app.developer || card.app.id
                    color: win.txt2
                    font.family: win.uiFont
                    font.pixelSize: win.typePx(10)
                    elide: Text.ElideRight
                }
            }
            Rectangle {
                visible: card.installed
                Layout.preferredWidth: win.fs(24)
                Layout.preferredHeight: win.fs(24)
                radius: height / 2
                color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.15)
                Glyph { win: card.win; anchors.centerIn: parent; width: 13; height: 13; name: "check"; tint: win.accent }
            }
        }
        Text {
            Layout.fillWidth: true
            text: win.localSummary(card.app)
            color: win.txt2
            font.family: win.uiFont
            font.pixelSize: win.typePx(11)
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
        Item { Layout.fillHeight: true }
        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            SourceBadge { win: card.win; app: card.app }
            Item { Layout.fillWidth: true }
            ActionButton {
                win: card.win
                activeFocusOnTab: !card.compositeFocus
                enabled: !card.installed || win.hasRunnableLifecycle(card.app)
                label: card.installed
                    ? win.hasRunnableLifecycle(card.app)
                        ? (win.rtl ? "افتح" : "Open")
                        : (win.rtl ? "جاهز" : "Ready")
                    : card.selected ? (win.rtl ? "مُضاف" : "Added")
                    : win.isWeb(card.app) ? (win.rtl ? "الموقع" : "Website")
                    : (win.rtl ? "تثبيت" : "Install")
                glyphName: card.installed
                    ? win.hasRunnableLifecycle(card.app) ? "external" : "check"
                    : card.selected ? "check" : "download"
                primary: card.selected
                triggered: function() {
                    if (card.installed && win.hasRunnableLifecycle(card.app))
                        win.runSelected(card.app)
                    else if (card.selected) win.setPicked(card.app.id, false)
                    else win.installOne(card.app)
                }
            }
        }
    }
}
