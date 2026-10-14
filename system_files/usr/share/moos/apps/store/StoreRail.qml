pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — the navigation rail: the brand, the six pages (with the installed and
// update counts) and the catalogue status card.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: rail
    required property var win
    readonly property var design: win.design

    // Tab out of the catalogue grid lands here (CatalogPage.qml → win.focusFirstNavItem).
    function focusFirstNavItem(reason) {
        var first = navRepeater.itemAt(0)
        if (first) first.forceActiveFocus(reason)
    }

    Layout.fillHeight: true
    Layout.preferredWidth: win.compactRail ? 82 : 222
    color: Qt.rgba(win.chrome.r, win.chrome.g, win.chrome.b, 0.82)
    border.width: 0
    Behavior on Layout.preferredWidth { NumberAnimation { duration: win.motionEnabled ? design.motionPress : 0; easing.type: Easing.OutCubic } }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: design.space2

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: win.fs(62)
            spacing: 11
            Rectangle {
                Layout.preferredWidth: win.fs(46)
                Layout.preferredHeight: win.fs(46)
                radius: design.radiusCard
                color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.12)
                border.width: 1
                border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.26)
                Image {
                    anchors.centerIn: parent
                    width: 36
                    height: 36
                    source: "file:///usr/share/moos/moos-logo.png"
                    sourceSize.width: 48
                    sourceSize.height: 48
                }
            }
            ColumnLayout {
                visible: !win.compactRail
                Layout.fillWidth: true
                spacing: -1
                Text {
                    text: "MO STORE"
                    color: win.txt
                    font.family: win.uiFont
                    font.pixelSize: win.typePx(16)
                    font.bold: true
                    font.letterSpacing: 1.5
                }
                Text {
                    text: win.rtl ? "مركز تطبيقات MoOS" : "MoOS app centre"
                    color: win.txt2
                    font.family: win.uiFont
                    font.pixelSize: win.typePx(10)
                }
            }
        }

        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: win.fs(1); color: win.outline; opacity: 0.55 }
        Item { Layout.preferredHeight: win.fs(2) }

        Repeater {
            id: navRepeater
            model: win.navItems
            delegate: Rectangle {
                id: nav
                required property var modelData
                readonly property bool active: win.page === nav.modelData.id
                Layout.fillWidth: true
                Layout.preferredHeight: win.fs(46)
                radius: design.radiusControl
                color: active ? Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                              : navHover.hovered ? Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.72)
                                                 : "transparent"
                border.width: active ? 1 : 0
                border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.34)
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: win.rtl ? nav.modelData.ar : nav.modelData.en
                FocusRing { win: rail.win }
                HoverHandler { id: navHover }
                TapHandler { onTapped: win.navigate(nav.modelData.id) }
                Keys.onReturnPressed: win.navigate(nav.modelData.id)
                Behavior on color { ColorAnimation { duration: win.motionEnabled ? design.motionFast : 0 } }
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: win.compactRail ? 15 : 14
                    anchors.rightMargin: 12
                    spacing: design.space3
                    Glyph {
                        win: rail.win
                        name: nav.modelData.glyph
                        tint: nav.active ? win.accent : win.txt2
                        Layout.preferredWidth: win.fs(19)
                        Layout.preferredHeight: win.fs(19)
                    }
                    Text {
                        visible: !win.compactRail
                        Layout.fillWidth: true
                        text: win.rtl ? nav.modelData.ar : nav.modelData.en
                        color: nav.active ? win.txt : win.txt2
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(13)
                        font.bold: nav.active
                    }
                    Rectangle {
                        visible: !win.compactRail && nav.modelData.id === "installed" && win.installedCount() > 0
                        implicitWidth: installedBadge.implicitWidth + 12
                        implicitHeight: win.fs(22)
                        radius: height / 2
                        color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                        Text {
                            id: installedBadge
                            anchors.centerIn: parent
                            text: win.installedCount()
                            color: win.accent
                            font.family: win.uiFont
                            font.pixelSize: win.typePx(10)
                            font.bold: true
                        }
                    }
                    // Only once the count is genuinely known — an
                    // un-checked page must not imply "nothing pending".
                    Rectangle {
                        visible: !win.compactRail && nav.modelData.id === "updates"
                            && win.updatesState === "known" && win.updateItems().length > 0
                        implicitWidth: updatesBadge.implicitWidth + 12
                        implicitHeight: win.fs(22)
                        radius: height / 2
                        color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                        Text {
                            id: updatesBadge
                            anchors.centerIn: parent
                            text: win.updateItems().length
                            color: win.accent
                            font.family: win.uiFont
                            font.pixelSize: win.typePx(10)
                            font.bold: true
                        }
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: win.compactRail ? 50 : 72
            radius: design.radiusCard
            color: Qt.rgba(win.surface.r, win.surface.g, win.surface.b, 0.7)
            border.width: 1
            border.color: win.outline
            RowLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 9
                Rectangle {
                    Layout.preferredWidth: win.fs(28)
                    Layout.preferredHeight: win.fs(28)
                    radius: height / 2
                    color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
                    // The rail's working light. It belongs to the line beside
                    // it — "Building catalogue…" — so it pulses while the index
                    // is actually being built and goes solid the moment it is
                    // ready.
                    //
                    // It used to pulse forever, with no `running:` guard at all.
                    // One 8 px dot animating without end keeps the QML render
                    // loop at full frame rate, and repainting a 4K window for it
                    // measured ~11% of a CPU core on an idle desktop — paid by
                    // every session that merely had the Store window restored
                    // behind other windows. Every other infinite animation MoOS
                    // ships was already guarded; this was the one that was not.
                    Rectangle {
                        id: railWorkingDot
                        anchors.centerIn: parent
                        width: 8
                        height: 8
                        radius: height / 2
                        color: win.hasFlatpakCatalog() ? win.accent : win.violet
                        property real pulse: 1
                        opacity: railWorkingPulse.running ? railWorkingDot.pulse : 1
                        SequentialAnimation {
                            id: railWorkingPulse
                            // win.indexPolling (main.qml's index poll) bounds the pulse:
                            // the poll gives up after 36 ticks, and without this term
                            // a catalogue that never lands left the dot
                            // pulsing at frame rate forever — measured ~12%
                            // of a core, flat, for the life of the window.
                            running: !win.indexReady && win.indexPolling && win.motionEnabled
                            loops: Animation.Infinite
                            NumberAnimation {
                                target: railWorkingDot; property: "pulse"
                                from: 0.35; to: 1; duration: win.motionEnabled ? 850 : 0
                            }
                            NumberAnimation {
                                target: railWorkingDot; property: "pulse"
                                from: 1; to: 0.35; duration: win.motionEnabled ? 850 : 0
                            }
                        }
                    }
                }
                ColumnLayout {
                    visible: !win.compactRail
                    Layout.fillWidth: true
                    spacing: 0
                    Text {
                        text: !win.indexReady
                            ? (win.indexPolling
                                ? (win.rtl ? "يُجهّز الفهرس…" : "Building catalogue…")
                                : (win.rtl ? "تعذّر تجهيز الفهرس" : "Catalogue build failed"))
                            : win.hasFlatpakCatalog()
                                ? (win.rtl ? "الفهرس الكامل جاهز" : "Full catalogue ready")
                                : (win.rtl ? "الفهرس المحدود · يحتاج اتصالًا" : "Limited catalogue · connection needed")
                        color: win.txt
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(11)
                        font.bold: true
                    }
                    Text {
                        text: win.allApps.length + (win.rtl ? " تطبيق" : " apps")
                        color: win.txt2
                        font.family: win.uiFont
                        font.pixelSize: win.typePx(10)
                    }
                }
            }
        }
    }
    Rectangle {
        anchors.right: win.rtl ? undefined : parent.right
        anchors.left: win.rtl ? parent.left : undefined
        width: 1
        height: parent.height
        color: win.outline
        opacity: 0.62
    }
}
