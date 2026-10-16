pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — Discover: the four app platforms, the hero, the catalogue's collections as rows, ready-made sets that set up a PC in one
// step, the twelve categories, and a quiet line about the catalogue itself.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: discover
    required property var win
    readonly property var design: win.design
    readonly property real padding: discover.width > win.fs(1000) ? design.space6 : design.space5

    anchors.fill: parent
    visible: win.page === "discover"
    transform: pageEnter.shift
    PageEnter { id: pageEnter; win: discover.win; target: discover }

    // A kind's tint is one of the scheme's own roles, so the four read as one family.
    function kindTone(id) {
        if (id === "web") return discover.win.cyan
        if (id === "windows") return discover.win.violet
        if (id === "android") return discover.win.positiveInk
        return discover.win.accent
    }

    Flickable {
        id: discoverFlick
        objectName: "discoverFlick"
        anchors.fill: parent
        contentWidth: width
        contentHeight: discoverBody.implicitHeight + discover.design.space6 * 2 + discover.win.footClearance
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Keys.onPressed: (event) => MoUI.KeyboardViewport.pageScrollKeys(discoverFlick, event)
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: discoverBody
            x: discover.padding
            y: discover.design.space2
            width: discoverFlick.width - discover.padding * 2
            spacing: discover.design.space6

            // ── Where apps come from ──
            ColumnLayout {
                Layout.fillWidth: true
                spacing: discover.design.space4
                SectionHeader {
                    win: discover.win
                    Layout.fillWidth: true
                    title: discover.win.local("اختر نوع التطبيقات", "Browse by platform")
                    subtitle: discover.win.local("حزم لينكس، وبرامج ويندوز، وتطبيقات أندرويد، ومواقع الويب — مع توضيح التوافق",
                                                 "Linux packages, Windows programs, Android apps and web apps — with compatibility shown")
                    glyph: "orbit"
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: discoverBody.width > discover.win.fs(900) ? 4 : 2
                    columnSpacing: discover.design.space4
                    rowSpacing: discover.design.space4
                    Repeater {
                        model: discover.win.kindDefs
                        delegate: Rectangle {
                            id: source
                            objectName: "platform-" + source.modelData.id
                            required property var modelData
                            readonly property color tone: discover.kindTone(source.modelData.id)
                            readonly property int count: discover.win.kindCountIn(source.modelData.id)
                            Layout.fillWidth: true
                            Layout.preferredHeight: discover.win.fs(148)
                            radius: discover.design.radiusCard + 2
                            color: discover.win.cardColor
                            border.width: 1
                            border.color: sourceHover.hovered ? discover.win.tint(source.tone, 0.6) : discover.win.cardBorder
                            scale: sourceFeedback.value
                            activeFocusOnTab: true
                            Accessible.role: Accessible.Button
                            Accessible.name: discover.win.localName(source.modelData) + ", "
                                             + discover.win.appsCountText(source.count)
                            Accessible.description: discover.win.rtl ? source.modelData.ar2 : source.modelData.en2
                            Accessible.onPressAction: discover.win.openKind(source.modelData.id)
                            Keys.onReturnPressed: discover.win.openKind(source.modelData.id)
                            Keys.onSpacePressed: discover.win.openKind(source.modelData.id)
                            FocusRing { win: discover.win }
                            HoverHandler { id: sourceHover; cursorShape: Qt.PointingHandCursor }
                            TapHandler { onTapped: discover.win.openKind(source.modelData.id) }
                            MoUI.SpringFeedback {
                                id: sourceFeedback
                                active: source.visible
                                motionEnabled: discover.win.motionEnabled
                                targetScale: sourceHover.hovered ? discover.design.hoverScale : 1
                            }
                            SoftShadow { win: discover.win; radius: source.radius; strength: sourceHover.hovered ? 1.8 : 1 }
                            // A wash of the kind's tone from the leading corner.
                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: 1
                                radius: source.radius - 1
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0; color: discover.win.tint(source.tone, discover.win.rtl ? 0 : (discover.win.lightScheme ? 0.10 : 0.14)) }
                                    GradientStop { position: 1; color: discover.win.tint(source.tone, discover.win.rtl ? (discover.win.lightScheme ? 0.10 : 0.14) : 0) }
                                }
                            }
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: discover.design.space4
                                spacing: discover.design.space1
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: discover.design.space3
                                    Rectangle {
                                        Layout.preferredWidth: discover.win.fs(44)
                                        Layout.preferredHeight: discover.win.fs(44)
                                        radius: width / 2
                                        color: discover.win.tint(source.tone, discover.win.lightScheme ? 0.18 : 0.22)
                                        Glyph {
                                            win: discover.win
                                            anchors.centerIn: parent
                                            width: discover.win.fs(22)
                                            height: width
                                            name: source.modelData.glyph
                                            tint: discover.win.lightScheme ? Qt.darker(source.tone, 1.1) : source.tone
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    Text {
                                        text: discover.win.countText(source.count)
                                        color: discover.win.txt
                                        font.family: discover.win.uiFont
                                        font.pixelSize: discover.win.typePx(20)
                                        font.weight: Font.Bold
                                    }
                                }
                                Item { Layout.fillHeight: true }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    text: discover.win.localName(source.modelData)
                                    color: discover.win.txt
                                    font.family: discover.win.uiFont
                                    font.pixelSize: discover.win.typePx(15)
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    text: discover.win.rtl ? source.modelData.ar2 : source.modelData.en2
                                    color: discover.win.txt2
                                    font.family: discover.win.uiFont
                                    font.pixelSize: discover.win.typePx(12)
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }
            }

            HeroCarousel {
                win: discover.win
                Layout.fillWidth: true
                visible: discover.win.featured.length > 0
            }

            // ── The catalogue's collections ──
            Repeater {
                model: discover.win.collections
                delegate: CollectionRow {
                    required property var modelData
                    win: discover.win
                    collection: modelData
                    bleed: discover.padding
                    Layout.fillWidth: true
                }
            }

            // ── Ready-made sets ──
            ColumnLayout {
                Layout.fillWidth: true
                spacing: discover.design.space4
                visible: discover.win.bundles.length > 0
                SectionHeader {
                    win: discover.win
                    Layout.fillWidth: true
                    title: discover.win.local("جهّز هذا الجهاز بخطوة واحدة", "Set up this PC in one step")
                    subtitle: discover.win.local("مجموعات جاهزة تراجعها مرة واحدة ثم تُثبَّت معًا",
                                                 "Ready-made sets: review once, install together")
                    glyph: "boxes"
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: discoverBody.width > discover.win.fs(1100) ? 3 : 2
                    columnSpacing: discover.design.space4
                    rowSpacing: discover.design.space4
                    Repeater {
                        model: discover.win.bundles
                        delegate: Rectangle {
                            id: bundleCard
                            required property var modelData
                            readonly property var members: discover.win.appsByIds(bundleCard.modelData.apps || [])
                            readonly property color tone: discover.win.idColour("bundle-" + bundleCard.modelData.id)
                            Layout.fillWidth: true
                            Layout.preferredHeight: discover.win.fs(176)
                            radius: discover.design.radiusCard + 2
                            color: discover.win.cardColor
                            border.width: 1
                            border.color: bundleHover.hovered ? discover.win.tint(discover.win.accent, 0.5) : discover.win.cardBorder
                            HoverHandler { id: bundleHover }
                            SoftShadow { win: discover.win; radius: bundleCard.radius }
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: discover.design.space4
                                spacing: discover.design.space2
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: discover.design.space3
                                    Rectangle {
                                        Layout.preferredWidth: discover.win.fs(40)
                                        Layout.preferredHeight: discover.win.fs(40)
                                        radius: discover.design.radiusControl
                                        gradient: Gradient {
                                            GradientStop { position: 0; color: Qt.lighter(bundleCard.tone, 1.25) }
                                            GradientStop { position: 1; color: bundleCard.tone }
                                        }
                                        Glyph {
                                            win: discover.win
                                            anchors.centerIn: parent
                                            width: discover.win.fs(20)
                                            height: width
                                            name: bundleCard.modelData.glyph || "boxes"
                                            tint: discover.win.inkOn(bundleCard.tone)
                                        }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 0
                                        Text {
                                            horizontalAlignment: Text.AlignLeft
                                            Layout.fillWidth: true
                                            text: discover.win.localName(bundleCard.modelData)
                                            color: discover.win.txt
                                            font.family: discover.win.uiFont
                                            font.pixelSize: discover.win.typePx(15)
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: discover.win.appsCountText(bundleCard.members.length)
                                            color: discover.win.txt2
                                            font.family: discover.win.uiFont
                                            font.pixelSize: discover.win.typePx(12)
                                        }
                                    }
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    text: discover.win.rtl ? (bundleCard.modelData.desc_ar || "") : (bundleCard.modelData.desc_en || "")
                                    color: discover.win.txt2
                                    font.family: discover.win.uiFont
                                    font.pixelSize: discover.win.typePx(13)
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                }
                                Item { Layout.fillHeight: true }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: discover.design.space3
                                    // The set's members, overlapping like a hand of cards.
                                    Item {
                                        Layout.preferredHeight: discover.win.fs(32)
                                        Layout.preferredWidth: discover.win.fs(32) + Math.max(0, Math.min(5, bundleCard.members.length) - 1) * discover.win.fs(22)
                                        Repeater {
                                            model: bundleCard.members.slice(0, 5)
                                            delegate: Rectangle {
                                                id: memberFrame
                                                required property var modelData
                                                required property int index
                                                width: discover.win.fs(32)
                                                height: width
                                                radius: discover.win.fs(10)
                                                x: discover.win.rtl ? (parent ? parent.width : 0) - width - memberFrame.index * discover.win.fs(22)
                                                                    : memberFrame.index * discover.win.fs(22)
                                                z: 10 - memberFrame.index
                                                color: discover.win.cardColor
                                                AppIcon {
                                                    win: discover.win
                                                    anchors.centerIn: parent
                                                    app: memberFrame.modelData
                                                    size: discover.win.fs(28)
                                                }
                                            }
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    ActionButton {
                                        win: discover.win
                                        pill: true
                                        compact: true
                                        label: discover.win.local("أضف المجموعة", "Add the set")
                                        glyphName: "download"
                                        enabled: !discover.win.jobIsActive()
                                        Accessible.name: discover.win.local("أضف المجموعة: ", "Add the set: ")
                                                         + discover.win.localName(bundleCard.modelData)
                                        triggered: function() { discover.win.addMany(bundleCard.modelData.apps || []) }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ── Categories ──
            ColumnLayout {
                Layout.fillWidth: true
                spacing: discover.design.space4
                SectionHeader {
                    win: discover.win
                    Layout.fillWidth: true
                    title: discover.win.local("تصفّح حسب الفئة", "Browse by category")
                    subtitle: discover.win.local("من العمل إلى اللعب، ومن الصور إلى البرمجة",
                                                 "From work to play, from photos to code")
                    glyph: "grid"
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: discoverBody.width > discover.win.fs(1100) ? 6
                           : discoverBody.width > discover.win.fs(760) ? 4 : 3
                    columnSpacing: discover.design.space3
                    rowSpacing: discover.design.space3
                    Repeater {
                        model: discover.win.storeCategories
                        delegate: Rectangle {
                            id: categoryTile
                            required property var modelData
                            readonly property color tone: discover.win.idColour("category-" + categoryTile.modelData.id)
                            Layout.fillWidth: true
                            Layout.preferredHeight: discover.win.fs(112)
                            radius: discover.design.radiusCard
                            color: discover.win.cardColor
                            border.width: 1
                            border.color: categoryHover.hovered ? discover.win.tint(categoryTile.tone, 0.7) : discover.win.cardBorder
                            scale: categoryFeedback.value
                            activeFocusOnTab: true
                            Accessible.role: Accessible.Button
                            Accessible.name: discover.win.localName(categoryTile.modelData) + ", "
                                             + discover.win.appsCountText(discover.win.categoryCount(categoryTile.modelData.id))
                            Accessible.onPressAction: discover.win.openCategory(categoryTile.modelData.id)
                            Keys.onReturnPressed: discover.win.openCategory(categoryTile.modelData.id)
                            Keys.onSpacePressed: discover.win.openCategory(categoryTile.modelData.id)
                            FocusRing { win: discover.win }
                            HoverHandler { id: categoryHover; cursorShape: Qt.PointingHandCursor }
                            TapHandler { onTapped: discover.win.openCategory(categoryTile.modelData.id) }
                            MoUI.SpringFeedback {
                                id: categoryFeedback
                                active: categoryTile.visible
                                motionEnabled: discover.win.motionEnabled
                                targetScale: categoryHover.hovered ? discover.design.hoverScale : 1
                            }
                            SoftShadow { win: discover.win; radius: categoryTile.radius; strength: categoryHover.hovered ? 1.6 : 0.8 }
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: discover.design.space3 + 2
                                spacing: discover.design.space1
                                Rectangle {
                                    Layout.preferredWidth: discover.win.fs(40)
                                    Layout.preferredHeight: discover.win.fs(40)
                                    radius: discover.design.radiusControl
                                    gradient: Gradient {
                                        GradientStop { position: 0; color: Qt.lighter(categoryTile.tone, 1.25) }
                                        GradientStop { position: 1; color: categoryTile.tone }
                                    }
                                    Glyph {
                                        win: discover.win
                                        anchors.centerIn: parent
                                        width: discover.win.fs(20)
                                        height: width
                                        name: categoryTile.modelData.glyph
                                        tint: discover.win.inkOn(categoryTile.tone)
                                    }
                                }
                                Item { Layout.fillHeight: true }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    text: discover.win.localName(categoryTile.modelData)
                                    color: discover.win.txt
                                    font.family: discover.win.uiFont
                                    font.pixelSize: discover.win.typePx(14)
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    text: discover.win.appsCountText(discover.win.categoryCount(categoryTile.modelData.id))
                                    color: discover.win.txt2
                                    font.family: discover.win.uiFont
                                    font.pixelSize: discover.win.typePx(12)
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }
            }

            // ── The catalogue itself, quietly ──
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: discover.design.space2
                spacing: discover.design.space2
                Item { Layout.fillWidth: true }
                Glyph {
                    win: discover.win
                    name: discover.win.indexReady ? "check" : "refresh"
                    tint: discover.win.txt2
                    Layout.preferredWidth: discover.win.fs(14)
                    Layout.preferredHeight: discover.win.fs(14)
                }
                Text {
                    text: {
                        var parts = []
                        parts.push(discover.win.indexReady
                            ? discover.win.local("الكتالوج جاهز", "Catalogue ready")
                            : discover.win.indexPolling ? discover.win.local("يُجهَّز الكتالوج…", "Preparing the catalogue…")
                            : discover.win.local("الكتالوج الأساسي", "Essential catalogue"))
                        parts.push(discover.win.appsCountText(discover.win.browseOrder.length))
                        var when = discover.win.agoText(discover.win.indexGeneratedAt)
                        if (when !== "") parts.push(discover.win.local("حُدِّث ", "updated ") + when)
                        return parts.join("  ·  ")
                    }
                    color: discover.win.txt2
                    font.family: discover.win.uiFont
                    font.pixelSize: discover.win.typePx(12)
                }
                Item { Layout.fillWidth: true }
            }
        }
    }
}
