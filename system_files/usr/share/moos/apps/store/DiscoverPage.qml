pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — Discover: the hero with what MoOS can run, MoOS picks, the first
// categories and the smart collections.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Flickable {
    id: discoverFlick
    required property var win
    readonly property var design: win.design
    anchors.fill: parent
    visible: win.page === "discover"
    contentWidth: width
    contentHeight: discoverBody.implicitHeight + 48
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    Keys.onPressed: (event) => MoUI.KeyboardViewport.pageScrollKeys(discoverFlick, event)
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    ColumnLayout {
        id: discoverBody
        x: 24
        width: discoverFlick.width - 48
        spacing: 22

        Item { Layout.preferredHeight: win.fs(2) }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: win.fs(224)
            radius: win.fs(28)
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.22) }
                GradientStop { position: 0.58; color: Qt.rgba(win.blue.r, win.blue.g, win.blue.b, 0.1) }
                GradientStop { position: 1; color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.9) }
            }
            border.width: 1
            border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.38)
            clip: true
            RowLayout {
                z: 1
                anchors.fill: parent
                anchors.margins: 28
                spacing: design.space5
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: design.space2
                    Text {
                        text: win.rtl ? "MO STORE · جيل جديد" : "MO STORE · REIMAGINED"
                        color: win.accent
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(10)
                        font.bold: true
                        font.letterSpacing: 1.5
                    }
                    Text {
                        text: win.rtl ? "كل تطبيقاتك. متجر واحد." : "Every app. One beautiful home."
                        color: win.txt
                        font.family: win.uiFont
                        font.pixelSize: Math.min(win.typePx(32),
                                                 Math.max(win.typePx(24),
                                                          win.width * 0.029))
                        font.bold: true
                    }
                    Text {
                        Layout.fillWidth: true
                        Layout.maximumWidth: 660
                        text: win.rtl
                            ? "اكتشف تطبيقاتك هنا، أو أضف ملفًا نزّلته. مكان واحد للتثبيت والتحديث، مع توضيح التوافق قبل المتابعة."
                            : "Discover apps here, or add a file you downloaded. One place to install and update, with compatibility explained before you continue."
                        color: win.txt2
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(13)
                        wrapMode: Text.WordWrap
                    }
                    Flow {
                        Layout.fillWidth: true
                        Layout.maximumWidth: 660
                        spacing: 8
                        visible: win.engineCapabilities.length > 0
                        Repeater {
                            model: win.engineCapabilities
                            delegate: Rectangle {
                                required property var modelData
                                // 40 px is the contract's minimum interactive
                                // target; this is a real button, not a label.
                                implicitHeight: Math.max(40, win.fs(40))
                                implicitWidth: capabilityLabel.implicitWidth + 28
                                radius: design.radiusControl
                                color: capabilityTouch.containsMouse
                                    ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.18)
                                    : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.82)
                                border.width: 1
                                border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.35)
                                Text {
                                    id: capabilityLabel
                                    anchors.centerIn: parent
                                    text: parent.modelData.label
                                    color: win.txt
                                    font.family: win.uiFont
                                    font.pixelSize: win.typePx(13)
                                }
                                MouseArea {
                                    id: capabilityTouch
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: win.openPickerFor(parent.modelData)
                                }
                                Accessible.role: Accessible.Button
                                Accessible.name: modelData.label
                                Accessible.description: win.local(
                                    "اختر ملفًا من هذا النوع لإضافته",
                                    "Choose a file of this kind to add")
                                Accessible.onPressAction: win.openPickerFor(modelData)
                            }
                        }
                    }
                    RowLayout {
                        spacing: 9
                        ActionButton {
                            win: discoverFlick.win
                            label: win.rtl ? "استكشف كل التطبيقات" : "Explore all apps"
                            glyphName: "grid"
                            primary: true
                            triggered: function() { win.navigate("apps") }
                        }
                        ActionButton {
                            win: discoverFlick.win
                            label: win.rtl ? "جهّز حزمة ذكية" : "Build a smart set"
                            glyphName: "spark"
                            triggered: function() {
                                if (win.bundles.length > 0)
                                    win.addMany(win.bundles[0].apps || [])
                            }
                        }
                    }
                }
                ColumnLayout {
                    Layout.preferredWidth: win.fs(250)
                    Layout.fillHeight: true
                    spacing: 10
                    Repeater {
                        model: [
                            { value: win.allApps.length, label: win.rtl ? "تطبيق متاح" : "apps available", glyph: "grid" },
                            { value: win.verifiedCount(), label: win.rtl ? "ناشر موثّق" : "verified publishers", glyph: "shield" },
                            { value: win.installedCount(), label: win.rtl ? "مثبّت لديك" : "installed", glyph: "check" }
                        ]
                        delegate: Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: design.radiusCard
                            color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.72)
                            border.width: 1
                            border.color: win.outline
                            // The three stat cards share the hero's height, and an
                            // Arabic-capable UI font's natural line boxes are taller
                            // than its glyphs: measured at 4K/225%, each caption sat
                            // on its card's border. Fixed line heights keep value and
                            // caption inside the card, the minimum height grows the
                            // hero instead of clipping, and a filling column stops
                            // each card centring its text at a different offset.
                            Layout.minimumHeight: statRow.implicitHeight + 16
                            RowLayout {
                                id: statRow
                                anchors.fill: parent
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                anchors.topMargin: 8
                                anchors.bottomMargin: 8
                                spacing: 12
                                Glyph {
                                    win: discoverFlick.win
                                    name: modelData.glyph
                                    tint: win.accent
                                    Layout.preferredWidth: win.fs(19)
                                    Layout.preferredHeight: win.fs(19)
                                    Layout.alignment: Qt.AlignVCenter
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.alignment: Qt.AlignVCenter
                                    spacing: 0
                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.value
                                        color: win.txt
                                        font.family: win.uiFont
                                        font.pixelSize: win.typePx(18)
                                        font.bold: true
                                        lineHeightMode: Text.FixedHeight
                                        lineHeight: Math.ceil(win.typePx(18) * 1.15)
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.label
                                        color: win.txt2
                                        font.family: win.uiFont
                                        font.pixelSize: win.typePx(9)
                                        lineHeightMode: Text.FixedHeight
                                        lineHeight: Math.ceil(win.typePx(9) * 1.35)
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: win.rtl ? "اختيارات MoOS" : "MoOS picks"
                color: win.txt
                font.family: win.uiFont
                font.pixelSize: win.typePx(17)
                font.bold: true
            }
            Text {
                text: win.rtl ? "· تطبيقات موثوقة للبدء" : "· trusted ways to get started"
                color: win.txt2
                font.family: win.uiFont
                font.pixelSize: win.typePx(11)
            }
            Item { Layout.fillWidth: true }
            ActionButton {
                win: discoverFlick.win
                label: win.rtl ? "عرض الكل" : "See all"
                glyphName: "external"
                triggered: function() { win.navigate("apps") }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: win.width > 1220 ? 4 : 3
            columnSpacing: 12
            rowSpacing: 12
            Repeater {
                model: win.curatedFeatured(win.width > 1220 ? 8 : 6)
                delegate: AppCard {
                    required property var modelData
                    win: discoverFlick.win
                    app: modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: win.fs(178)
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 2
            Text {
                text: win.rtl ? "فئات لكل استخدام" : "Made for every kind of day"
                color: win.txt
                font.family: win.uiFont
                font.pixelSize: win.typePx(17)
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Text {
                text: win.rtl ? "من العمل إلى اللعب، ومن التصميم إلى الذكاء الاصطناعي" : "Work, play, create, learn and build"
                color: win.txt2
                font.family: win.uiFont
                font.pixelSize: win.typePx(11)
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: win.width > 1180 ? 4 : 3
            columnSpacing: 12
            rowSpacing: 12
            Repeater {
                model: win.categoryDefs.slice(0, 8)
                delegate: Rectangle {
                    id: homeCategory
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: win.fs(82)
                    radius: design.radiusCard
                    color: homeCategoryHover.hovered
                        ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.94)
                        : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.72)
                    border.width: 1
                    border.color: homeCategoryHover.hovered ? win.accent : win.outline
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: win.rtl ? homeCategory.modelData.ar : homeCategory.modelData.en
                    FocusRing { win: discoverFlick.win }
                    HoverHandler { id: homeCategoryHover }
                    TapHandler { onTapped: win.openCategory(homeCategory.modelData.id) }
                    Keys.onReturnPressed: win.openCategory(homeCategory.modelData.id)
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: design.space3
                        Rectangle {
                            Layout.preferredWidth: win.fs(44)
                            Layout.preferredHeight: win.fs(44)
                            radius: design.radiusControl
                            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.13)
                            Glyph { win: discoverFlick.win; anchors.centerIn: parent; width: 22; height: 22; name: homeCategory.modelData.glyph; tint: win.accent }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Text {
                                text: win.rtl ? homeCategory.modelData.ar : homeCategory.modelData.en
                                color: win.txt
                                font.family: win.uiFont
                                font.pixelSize: win.typePx(13)
                                font.bold: true
                            }
                            Text {
                                text: win.categoryCount(homeCategory.modelData.id) + (win.rtl ? " تطبيق" : " apps")
                                color: win.txt2
                                font.family: win.uiFont
                                font.pixelSize: win.typePx(10)
                            }
                        }
                        Glyph { win: discoverFlick.win; name: "external"; tint: win.txt2; Layout.preferredWidth: win.fs(14); Layout.preferredHeight: win.fs(14) }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 2
            Text {
                text: win.rtl ? "حزم ذكية" : "Smart collections"
                color: win.txt
                font.family: win.uiFont
                font.pixelSize: win.typePx(17)
                font.bold: true
            }
            Text {
                text: win.rtl ? "· ثبّت مجموعة كاملة بمراجعة واحدة" : "· one review, a complete setup"
                color: win.txt2
                font.family: win.uiFont
                font.pixelSize: win.typePx(11)
            }
            Item { Layout.fillWidth: true }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: win.width > 1180 ? 3 : 2
            columnSpacing: 12
            rowSpacing: 12
            Repeater {
                model: win.bundles
                delegate: Rectangle {
                    id: bundleCard
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: win.fs(132)
                    radius: design.radiusCard
                    color: bundleHover.hovered
                        ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.96)
                        : Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.76)
                    border.width: 1
                    border.color: bundleHover.hovered ? win.accent : win.outline
                    HoverHandler { id: bundleHover }
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 7
                        RowLayout {
                            Layout.fillWidth: true
                            Glyph {
                                win: discoverFlick.win
                                name: bundleCard.modelData.glyph || "boxes"
                                tint: win.accent
                                Layout.preferredWidth: win.fs(21)
                                Layout.preferredHeight: win.fs(21)
                            }
                            Text {
                                Layout.fillWidth: true
                                text: win.rtl ? bundleCard.modelData.ar : bundleCard.modelData.en
                                color: win.txt
                                font.family: win.uiFont
                                font.pixelSize: win.typePx(14)
                                font.bold: true
                            }
                            Text {
                                text: (bundleCard.modelData.apps || []).length
                                color: win.accent
                                font.family: win.uiFont
                                font.pixelSize: win.typePx(12)
                                font.bold: true
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: win.rtl ? bundleCard.modelData.desc_ar : bundleCard.modelData.desc_en
                            color: win.txt2
                            font.family: win.uiFont
                            font.pixelSize: win.typePx(10)
                            wrapMode: Text.WordWrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                        }
                        Item { Layout.fillHeight: true }
                        ActionButton {
                            win: discoverFlick.win
                            label: win.rtl ? "أضف الحزمة" : "Add collection"
                            glyphName: "download"
                            triggered: function() { win.addMany(bundleCard.modelData.apps || []) }
                        }
                    }
                }
            }
        }
        Item { Layout.preferredHeight: win.fs(12) }
    }
}
