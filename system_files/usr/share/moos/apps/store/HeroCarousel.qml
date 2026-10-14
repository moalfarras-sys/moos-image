pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — the hero: the catalogue's featured apps, one at a time, each on a broad plate painted
// in the app's own colour (its branding for this scheme, else the catalogue's accent, else the
// theme's highlight) and moved until the ink on it reaches WCAG AA. The app's picture stands on a
// glass plinth on the trailing side, under a quiet horizon of arcs; the title, the line, who made
// it and its button sit on the leading side.
//
// It advances by itself every 8 s ONLY while Discover is the page, the window is active, the
// pointer is not over it and animations are on; ←/→ (and the arrows) move it at any time. The
// change is a crossfade with a short slide, on the shared motion rhythm, and exactly instant with
// animations off.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: hero
    objectName: "heroCarousel"
    required property var win
    readonly property var design: win.design
    property var items: win.featured
    property int currentIndex: 0
    property int shownIndex: 0
    readonly property int count: hero.items ? hero.items.length : 0
    readonly property var item: hero.count > 0 ? hero.items[Math.min(hero.shownIndex, hero.count - 1)] : null
    readonly property var app: hero.item ? hero.item.app : null
    readonly property color brand: hero.item && win.parseColour(hero.item.accent)
                                   ? win.parseColour(hero.item.accent)
                                   : hero.app ? win.appColour(hero.app) : win.accent
    readonly property color base: win.plateColour(hero.brand)
    readonly property color ink: win.inkOn(hero.base)
    readonly property bool inkIsLight: win.luminanceOf(hero.ink) > 0.5
    property color paint: hero.base
    readonly property bool wide: hero.width > hero.win.fs(900)

    Behavior on paint { ColorAnimation { duration: hero.win.motionEnabled ? hero.design.motionEmphasis : 0; easing.type: Easing.OutCubic } }

    implicitHeight: win.fs(304)
    activeFocusOnTab: true
    Accessible.role: Accessible.Grouping
    Accessible.name: win.local("تطبيقات مختارة: ", "Featured apps: ")
                     + (hero.count > 0 ? (hero.shownIndex + 1) + " / " + hero.count + ", " : "")
                     + hero.title
    Keys.onLeftPressed: hero.win.rtl ? hero.step(1) : hero.step(-1)
    Keys.onRightPressed: hero.win.rtl ? hero.step(-1) : hero.step(1)
    Keys.onReturnPressed: if (hero.app) hero.win.openDetails(hero.app)
    Keys.onEnterPressed: if (hero.app) hero.win.openDetails(hero.app)
    FocusRing { win: hero.win; controlRadius: hero.design.radiusPanel }

    readonly property string title: hero.item
        ? (hero.win.rtl ? (hero.item.title_ar || hero.win.localName(hero.app))
                        : (hero.item.title_en || hero.win.localName(hero.app)))
        : ""
    readonly property string tagline: hero.item
        ? (hero.win.rtl ? (hero.item.tagline_ar || hero.win.localSummary(hero.app))
                        : (hero.item.tagline_en || hero.win.localSummary(hero.app)))
        : ""

    function step(delta) {
        if (hero.count < 2) return
        hero.currentIndex = (hero.currentIndex + delta + hero.count) % hero.count
    }

    onCurrentIndexChanged: {
        if (!hero.win.motionEnabled) {
            swap.stop()
            hero.shownIndex = hero.currentIndex
            content.opacity = 1
            contentShift.x = 0
            return
        }
        swap.restart()
    }
    onCountChanged: if (hero.currentIndex >= hero.count) { hero.currentIndex = 0; hero.shownIndex = 0 }

    // Out with a short slide toward the start, in from the end: the direction follows reading.
    SequentialAnimation {
        id: swap
        ParallelAnimation {
            NumberAnimation { target: content; property: "opacity"; to: 0; duration: hero.win.motionEnabled ? hero.design.motionFast : 0; easing.type: Easing.InCubic }
            NumberAnimation { target: contentShift; property: "x"; to: hero.win.rtl ? 18 : -18; duration: hero.win.motionEnabled ? hero.design.motionFast : 0; easing.type: Easing.InCubic }
        }
        ScriptAction { script: { hero.shownIndex = hero.currentIndex; contentShift.x = hero.win.rtl ? -24 : 24 } }
        ParallelAnimation {
            NumberAnimation { target: content; property: "opacity"; to: 1; duration: hero.win.motionEnabled ? hero.design.motionEmphasis : 0; easing.type: Easing.OutCubic }
            NumberAnimation { target: contentShift; property: "x"; to: 0; duration: hero.win.motionEnabled ? hero.design.motionEmphasis : 0; easing.type: Easing.OutCubic }
        }
    }

    Timer {
        id: advance
        interval: 8000
        repeat: true
        running: hero.visible && hero.win.page === "discover" && hero.win.active && !heroHover.hovered
                 && hero.win.motionEnabled && hero.count > 1
        onTriggered: hero.step(1)
    }

    HoverHandler { id: heroHover }

    SoftShadow { win: hero.win; radius: hero.design.radiusPanel; strength: 1.6; lift: hero.design.space3 }

    // The plate.
    Rectangle {
        id: plate
        anchors.fill: parent
        radius: hero.design.radiusPanel
        clip: true
        gradient: Gradient {
            GradientStop { position: 0; color: hero.inkIsLight ? hero.paint : Qt.lighter(hero.paint, 1.08) }
            GradientStop { position: 1; color: hero.inkIsLight ? Qt.darker(hero.paint, 1.38) : hero.paint }
        }

        // The trailing half: light, an horizon of arcs, and the app on its plinth.
        Item {
            id: stage
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.right: parent.right
            width: parent.width * (hero.wide ? 0.46 : 0.42)

            Rectangle {
                width: plate.height * 1.5
                height: width
                radius: width / 2
                anchors.centerIn: parent
                anchors.horizontalCenterOffset: stage.width * 0.08
                anchors.verticalCenterOffset: plate.height * 0.18
                color: hero.win.tint(hero.ink, hero.inkIsLight ? 0.07 : 0.10)
            }
            Repeater {
                model: 3
                delegate: Rectangle {
                    required property int index
                    width: plate.height * (1.0 + index * 0.42)
                    height: width
                    radius: width / 2
                    anchors.centerIn: parent
                    anchors.horizontalCenterOffset: stage.width * 0.08
                    anchors.verticalCenterOffset: plate.height * 0.18
                    color: "transparent"
                    border.width: Math.max(1, hero.win.fs(1.5))
                    border.color: hero.win.tint(hero.ink, 0.16 - index * 0.04)
                }
            }
            Rectangle {
                width: plate.height * 0.34
                height: width
                radius: width / 2
                x: stage.width * 0.08
                y: plate.height * 0.12
                color: hero.win.tint(Qt.lighter(hero.paint, 1.6), 0.28)
            }

            // The plinth: a glass slab the app's picture stands on.
            Item {
                id: plinthHolder
                anchors.centerIn: parent
                anchors.horizontalCenterOffset: stage.width * 0.06
                width: plate.height * 0.66
                height: width
                opacity: content.opacity
                transform: Translate { x: contentShift.x * 0.6 }

                SoftShadow { win: hero.win; radius: plinth.radius; strength: 1.4; lift: hero.design.space4 }
                Rectangle {
                    id: plinth
                    anchors.fill: parent
                    radius: width / 2
                    gradient: Gradient {
                        GradientStop { position: 0; color: hero.win.tint(hero.inkOnDarkAlways, hero.inkIsLight ? 0.20 : 0.42) }
                        GradientStop { position: 1; color: hero.win.tint(hero.inkOnDarkAlways, hero.inkIsLight ? 0.06 : 0.18) }
                    }
                    border.width: 1
                    border.color: hero.win.tint(hero.inkOnDarkAlways, hero.inkIsLight ? 0.34 : 0.6)
                    AppIcon {
                        win: hero.win
                        anchors.centerIn: parent
                        app: hero.app
                        size: plinth.width * 0.56
                        lifted: true
                        rotation: hero.win.rtl ? 6 : -6
                    }
                }
            }
        }

        // The words and the button.
        Item {
            id: contentHolder
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: stage.left
            anchors.leftMargin: hero.wide ? hero.design.space6 + hero.design.space2 : hero.design.space5
            anchors.rightMargin: hero.design.space4

            ColumnLayout {
                id: content
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: -hero.design.space2
                spacing: hero.design.space3
                transform: Translate { id: contentShift }

                Rectangle {
                    Layout.preferredHeight: hero.win.fs(26)
                    Layout.preferredWidth: eyebrow.implicitWidth + hero.design.space3 * 2
                    radius: height / 2
                    color: hero.win.tint(hero.ink, 0.16)
                    RowLayout {
                        id: eyebrow
                        anchors.centerIn: parent
                        spacing: hero.design.space1 + 2
                        Glyph { win: hero.win; name: "star"; tint: hero.ink; Layout.preferredWidth: hero.win.fs(13); Layout.preferredHeight: hero.win.fs(13) }
                        Text {
                            text: hero.win.local("اختيار المحرّرين", "Editors' choice")
                            color: hero.ink
                            font.family: hero.win.uiFont
                            font.pixelSize: hero.win.typePx(12)
                            font.weight: Font.DemiBold
                        }
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: hero.title
                    color: hero.ink
                    font.family: hero.win.uiFont
                    font.pixelSize: hero.wide ? hero.win.typePx(44) : hero.win.typePx(32)
                    font.weight: Font.Bold
                    elide: Text.ElideRight
                    Accessible.role: Accessible.Heading
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    Layout.topMargin: -hero.design.space1
                    text: hero.tagline
                    color: hero.win.tint(hero.ink, 0.88)
                    font.family: hero.win.uiFont
                    font.pixelSize: hero.win.typePx(16)
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: hero.win.publisherLine(hero.app)
                    color: hero.win.tint(hero.ink, 0.74)
                    font.family: hero.win.uiFont
                    font.pixelSize: hero.win.typePx(13)
                    elide: Text.ElideRight
                }
                RowLayout {
                    Layout.topMargin: hero.design.space2
                    spacing: hero.design.space3
                    ProgressButton {
                        win: hero.win
                        app: hero.app
                        large: true
                        prominent: true
                        onColour: true
                        colourInk: hero.ink
                        colourBase: hero.paint
                    }
                    ActionButton {
                        win: hero.win
                        label: hero.win.local("التفاصيل", "Details")
                        pill: true
                        implicitHeight: hero.win.fs(44)
                        surfaceColor: hero.win.tint(hero.ink, 0.16)
                        textColor: hero.ink
                        outlineColor: hero.win.tint(hero.ink, 0.32)
                        accentColor: hero.ink
                        Accessible.name: hero.win.local("تفاصيل ", "Details of ") + hero.title
                        triggered: function() { if (hero.app) hero.win.openDetails(hero.app) }
                    }
                }
            }
        }

        // Which one of how many, and the arrows.
        RowLayout {
            anchors.bottom: parent.bottom
            anchors.right: parent.right
            anchors.bottomMargin: hero.design.space5
            anchors.rightMargin: hero.design.space5
            spacing: hero.design.space3
            visible: hero.count > 1
            Row {
                spacing: hero.design.space1 + 2
                Layout.alignment: Qt.AlignVCenter
                Repeater {
                    model: hero.count
                    delegate: Rectangle {
                        required property int index
                        width: index === hero.shownIndex ? hero.win.fs(22) : hero.win.fs(7)
                        height: hero.win.fs(7)
                        radius: height / 2
                        color: hero.win.tint(hero.ink, index === hero.shownIndex ? 0.95 : 0.38)
                        Behavior on width { NumberAnimation { duration: hero.win.motionEnabled ? hero.design.motionGeometry : 0; easing.type: Easing.OutCubic } }
                        TapHandler { onTapped: hero.currentIndex = parent.index }
                    }
                }
            }
            CircleButton {
                win: hero.win
                onGlass: true
                glassInk: hero.ink
                glyph: hero.win.rtl ? "arrow" : "arrow-back"
                accessibleName: hero.win.local("السابق", "Previous")
                onActivated: hero.step(-1)
            }
            CircleButton {
                win: hero.win
                onGlass: true
                glassInk: hero.ink
                glyph: hero.win.rtl ? "arrow-back" : "arrow"
                accessibleName: hero.win.local("التالي", "Next")
                onActivated: hero.step(1)
            }
        }
    }

    // The plinth's rim catches light the same way on every plate.
    readonly property color inkOnDarkAlways: win.inkOnDark

    // The plate's own rim, above its colour.
    Rectangle {
        anchors.fill: parent
        radius: hero.design.radiusPanel
        color: "transparent"
        border.width: 1
        border.color: hero.win.tint(hero.ink, 0.14)
    }
}
