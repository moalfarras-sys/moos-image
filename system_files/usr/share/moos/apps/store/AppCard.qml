pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — one app as a card, in three shapes: "grid" (the Apps and Games grid), "tile" (a
// Discover row) and "row" (search results). Its picture, its name and maker, a line about it, where
// it comes from, whether it works here when it does not simply work, and its one button. The whole
// card opens the app's page; hovering lifts it.
//
// A virtual GridView is one keyboard composite: making each instantiated delegate a Tab stop
// strands keyboard users on only the visible cache window. Discover cards keep their normal
// independent stops; the app grid opts into arrow-key navigation (compositeFocus) and marks its
// current card (compositeCurrent).
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: card
    required property var win
    readonly property var design: win.design
    required property var app
    property string variant: "grid"
    property bool compositeFocus: false
    property bool compositeCurrent: false
    property bool selected: win.isPicked(app.id)
    property bool installed: win.isInstalled(app)
    readonly property bool hovered: cardHover.hovered
    readonly property var compat: win.compatOf(card.app)

    radius: card.variant === "row" ? design.radiusCard : design.radiusCard + 2
    color: win.cardColor
    border.width: card.selected ? 2 : 1
    border.color: card.selected ? win.accent
                 : cardHover.hovered ? win.tint(win.accent, 0.5)
                                     : win.outline
    scale: feedback.value
    activeFocusOnTab: !card.compositeFocus
    Accessible.role: Accessible.Button
    Accessible.name: win.localName(app) + ", " + win.sourceLabel(app)
    Accessible.description: win.localSummary(app)
    Accessible.onPressAction: win.openDetails(card.app)
    FocusRing { win: card.win; visible: card.activeFocus || card.compositeCurrent }
    HoverHandler { id: cardHover; cursorShape: Qt.PointingHandCursor }
    TapHandler { onTapped: card.win.openDetails(card.app) }
    Keys.onReturnPressed: win.openDetails(card.app)
    Keys.onSpacePressed: win.openDetails(card.app)
    Behavior on border.color { ColorAnimation { duration: card.win.motionEnabled ? card.design.motionPress : 0 } }

    MoUI.SpringFeedback {
        id: feedback
        active: card.visible
        motionEnabled: card.win.motionEnabled
        targetScale: cardHover.hovered && card.variant !== "row" ? card.design.hoverScale : 1
    }
    SoftShadow {
        win: card.win
        radius: card.radius
        strength: cardHover.hovered ? 1.8 : 1
        visible: card.variant !== "row"
    }

    // The glass edge: one bright hairline along the top.
    Rectangle {
        anchors.top: parent.top
        anchors.topMargin: 1
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width - card.radius * 2
        height: 1
        color: card.win.design.glassSpecular(card.win.cardColor, card.win.design.glassLevelScene)
        opacity: card.win.lightScheme ? 1 : 0.5
    }

    // ── grid ──
    ColumnLayout {
        visible: card.variant === "grid"
        anchors.fill: parent
        anchors.margins: card.design.space4
        spacing: card.design.space2
        RowLayout {
            Layout.fillWidth: true
            spacing: card.design.space3
            AppIcon { win: card.win; app: card.app; size: card.win.fs(56); showKind: true }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: card.win.localName(card.app)
                    color: card.win.txt
                    font.family: card.win.uiFont
                    font.pixelSize: card.win.typePx(15)
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: card.win.publisherLine(card.app)
                    color: card.win.txt2
                    font.family: card.win.uiFont
                    font.pixelSize: card.win.typePx(12)
                    elide: Text.ElideRight
                }
            }
        }
        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.fillWidth: true
            text: card.win.localSummary(card.app)
            color: card.win.txt2
            font.family: card.win.uiFont
            font.pixelSize: card.win.typePx(13)
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
        Item { Layout.fillHeight: true }
        // The foot: where it comes from, a limit on this PC when there is one (its words are on
        // the app's page), and the one button. The badge gives way before the button does.
        RowLayout {
            Layout.fillWidth: true
            spacing: card.design.space2
            SourceBadge { win: card.win; app: card.app; maxWidth: card.width * 0.46 }
            Glyph {
                win: card.win
                visible: card.compat.known && card.compat.verdict !== "ok"
                name: card.compat.verdict === "blocked" ? "danger" : "warning"
                tint: card.compat.verdict === "blocked" ? card.win.dangerInk : card.win.warningInk
                Layout.preferredWidth: card.win.fs(16)
                Layout.preferredHeight: card.win.fs(16)
            }
            Item { Layout.fillWidth: true }
            ProgressButton {
                win: card.win
                app: card.app
                tabStop: !card.compositeFocus
                visible: card.variant === "grid"
            }
        }
    }

    // ── tile ──
    ColumnLayout {
        visible: card.variant === "tile"
        anchors.fill: parent
        anchors.margins: card.design.space4
        spacing: card.design.space1
        AppIcon {
            win: card.win
            app: card.app
            size: card.win.fs(64)
            showKind: true
            Layout.bottomMargin: card.design.space2
        }
        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.fillWidth: true
            text: card.win.localName(card.app)
            color: card.win.txt
            font.family: card.win.uiFont
            font.pixelSize: card.win.typePx(15)
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.fillWidth: true
            text: card.win.publisherLine(card.app)
            color: card.win.txt2
            font.family: card.win.uiFont
            font.pixelSize: card.win.typePx(12)
            elide: Text.ElideRight
        }
        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.fillWidth: true
            Layout.topMargin: card.design.space1
            text: card.win.localSummary(card.app)
            color: card.win.txt2
            font.family: card.win.uiFont
            font.pixelSize: card.win.typePx(13)
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
        Item { Layout.fillHeight: true }
        RowLayout {
            Layout.fillWidth: true
            spacing: card.design.space2
            ProgressButton {
                win: card.win
                app: card.app
                tabStop: !card.compositeFocus
                visible: card.variant === "tile"
            }
            Item { Layout.fillWidth: true }
            Glyph {
                win: card.win
                visible: card.compat.known && card.compat.verdict !== "ok"
                name: card.compat.verdict === "blocked" ? "danger" : "warning"
                tint: card.compat.verdict === "blocked" ? card.win.dangerInk : card.win.warningInk
                Layout.preferredWidth: card.win.fs(16)
                Layout.preferredHeight: card.win.fs(16)
            }
        }
    }

    // ── row ──
    RowLayout {
        visible: card.variant === "row"
        anchors.fill: parent
        anchors.leftMargin: card.design.space4
        anchors.rightMargin: card.design.space4
        spacing: card.design.space4
        AppIcon { win: card.win; app: card.app; size: card.win.fs(52); showKind: true }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            RowLayout {
                Layout.fillWidth: true
                spacing: card.design.space2
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: false
                    Layout.maximumWidth: card.width * 0.42
                    text: card.win.localName(card.app)
                    color: card.win.txt
                    font.family: card.win.uiFont
                    font.pixelSize: card.win.typePx(15)
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                SourceBadge { win: card.win; app: card.app; maxWidth: card.width * 0.3 }
                Item { Layout.fillWidth: true }
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: card.win.localSummary(card.app) || card.win.publisherLine(card.app)
                color: card.win.txt2
                font.family: card.win.uiFont
                font.pixelSize: card.win.typePx(13)
                elide: Text.ElideRight
            }
        }
        CompatBadge {
            win: card.win
            app: card.app
            compact: true
            visible: card.compat.known && card.compat.verdict !== "ok"
        }
        ProgressButton {
            win: card.win
            app: card.app
            tabStop: !card.compositeFocus
            visible: card.variant === "row"
        }
    }
}
