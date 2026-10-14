pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — the navigation rail: a glass pane floating beside the content with the Store's mark,
// its six places (Discover · Apps · Games · My apps with its count · Updates with what is pending ·
// Settings) and a quiet line about the catalogue. It mirrors in Arabic and folds to its glyphs on a
// narrow window.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: rail
    required property var win
    readonly property var design: win.design
    readonly property bool compact: win.compactRail

    // Tab out of the app grid lands here (AppsPage.qml → win.focusFirstNavItem).
    function focusFirstNavItem(reason) {
        var first = navRepeater.itemAt(0)
        if (first) first.forceActiveFocus(reason)
    }

    Layout.fillHeight: true
    Layout.preferredWidth: rail.compact ? win.fs(88) : win.fs(240)
    Behavior on Layout.preferredWidth { NumberAnimation { duration: rail.win.motionEnabled ? rail.design.motionGeometry : 0; easing.type: Easing.OutCubic } }

    Rectangle {
        id: pane
        anchors.fill: parent
        anchors.topMargin: rail.design.space3
        anchors.bottomMargin: rail.design.space3
        anchors.leftMargin: rail.design.space3
        radius: rail.design.radiusPanel
        color: rail.win.glassColor
        border.width: 1
        border.color: rail.win.design.glassEdge(rail.win.canvas, rail.win.design.glassLevelPanel)
        SoftShadow { win: rail.win; radius: pane.radius; strength: 0.8 }
        Rectangle {
            anchors.top: parent.top
            anchors.topMargin: 1
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width - pane.radius * 1.6
            height: 1
            color: rail.win.design.glassSpecular(rail.win.canvas, rail.win.design.glassLevelPanel)
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: rail.design.space3
            spacing: rail.design.space1

            // The mark.
            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: rail.win.fs(64)
                Layout.leftMargin: rail.compact ? 0 : rail.design.space2
                spacing: rail.design.space3
                Item {
                    Layout.preferredWidth: rail.win.fs(40)
                    Layout.preferredHeight: rail.win.fs(40)
                    Layout.alignment: rail.compact ? Qt.AlignHCenter : Qt.AlignVCenter
                    Layout.fillWidth: rail.compact
                    Image {
                        anchors.centerIn: parent
                        width: rail.win.fs(36)
                        height: width
                        source: "file:///usr/share/moos/moos-logo.png"
                        sourceSize.width: Math.ceil(width * Math.max(1, Screen.devicePixelRatio))
                        sourceSize.height: Math.ceil(height * Math.max(1, Screen.devicePixelRatio))
                        smooth: true
                        mipmap: true
                    }
                }
                ColumnLayout {
                    visible: !rail.compact
                    Layout.fillWidth: true
                    spacing: 0
                    Text {
                        text: rail.win.local("متجر MoOS", "Mo Store")
                        color: rail.win.txt
                        font.family: rail.win.uiFont
                        font.pixelSize: rail.win.typePx(17)
                        font.weight: Font.Bold
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: rail.win.local("كل تطبيقاتك، في مكان واحد", "Every app, in one place")
                        color: rail.win.txt2
                        font.family: rail.win.uiFont
                        font.pixelSize: rail.win.typePx(11)
                        elide: Text.ElideRight
                    }
                }
            }

            Item { Layout.preferredHeight: rail.design.space2 }

            Repeater {
                id: navRepeater
                model: rail.win.navItems
                delegate: Rectangle {
                    id: nav
                    required property var modelData
                    required property int index
                    readonly property bool active: rail.win.page === nav.modelData.id
                    readonly property int badge: nav.modelData.id === "library" ? rail.win.installedCount()
                        : nav.modelData.id === "updates" && rail.win.updatesState === "known"
                          ? rail.win.updateItems().length : 0
                    Layout.fillWidth: true
                    Layout.preferredHeight: rail.win.fs(44)
                    radius: rail.design.radiusControl
                    color: nav.active ? rail.win.tint(rail.win.accent, rail.win.lightScheme ? 0.16 : 0.18)
                         : navHover.hovered ? rail.win.tint(rail.win.txt, rail.win.lightScheme ? 0.06 : 0.07)
                         : "transparent"
                    activeFocusOnTab: true
                    Accessible.role: Accessible.PageTab
                    Accessible.name: rail.win.localName(nav.modelData)
                                     + (nav.badge > 0 ? ", " + nav.badge : "")
                    Accessible.checkable: true
                    Accessible.checked: nav.active
                    Accessible.onPressAction: rail.win.navigate(nav.modelData.id)
                    FocusRing { win: rail.win }
                    HoverHandler { id: navHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: rail.win.navigate(nav.modelData.id) }
                    Keys.onReturnPressed: rail.win.navigate(nav.modelData.id)
                    Keys.onSpacePressed: rail.win.navigate(nav.modelData.id)
                    Keys.onDownPressed: { var below = navRepeater.itemAt(nav.index + 1); if (below) below.forceActiveFocus(Qt.TabFocusReason) }
                    Keys.onUpPressed: { var above = navRepeater.itemAt(nav.index - 1); if (above) above.forceActiveFocus(Qt.BacktabFocusReason) }
                    Behavior on color { ColorAnimation { duration: rail.win.motionEnabled ? rail.design.motionFast : 0 } }

                    // The lit edge of the page that is open.
                    Rectangle {
                        visible: nav.active
                        width: rail.win.fs(3)
                        height: parent.height * 0.46
                        radius: width / 2
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: rail.win.fs(3)
                        color: rail.win.accent
                    }
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: rail.compact ? 0 : rail.design.space4
                        anchors.rightMargin: rail.compact ? 0 : rail.design.space3
                        spacing: rail.design.space3
                        Item {
                            Layout.fillWidth: rail.compact
                            Layout.preferredWidth: rail.win.fs(22)
                            Layout.preferredHeight: rail.win.fs(22)
                            Glyph {
                                win: rail.win
                                anchors.centerIn: parent
                                width: rail.win.fs(20)
                                height: width
                                name: nav.modelData.glyph
                                tint: nav.active ? rail.win.accent : rail.win.txt2
                            }
                            // A compact rail still says that something is pending.
                            Rectangle {
                                visible: rail.compact && nav.modelData.id === "updates" && nav.badge > 0
                                width: rail.win.fs(9)
                                height: width
                                radius: width / 2
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.rightMargin: parent.width / 2 - rail.win.fs(14)
                                color: rail.win.accent
                            }
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            visible: !rail.compact
                            Layout.fillWidth: true
                            text: rail.win.localName(nav.modelData)
                            color: nav.active ? rail.win.txt : rail.win.txt2
                            font.family: rail.win.uiFont
                            font.pixelSize: rail.win.typePx(14)
                            font.weight: nav.active ? Font.DemiBold : Font.Medium
                            elide: Text.ElideRight
                        }
                        Rectangle {
                            visible: !rail.compact && nav.badge > 0
                            Layout.preferredHeight: rail.win.fs(22)
                            Layout.preferredWidth: Math.max(rail.win.fs(22), badgeLabel.implicitWidth + rail.design.space2 * 2)
                            radius: height / 2
                            color: nav.modelData.id === "updates" ? rail.win.accent
                                 : rail.win.tint(rail.win.txt, rail.win.lightScheme ? 0.08 : 0.10)
                            Text {
                                id: badgeLabel
                                anchors.centerIn: parent
                                text: rail.win.countText(nav.badge)
                                color: nav.modelData.id === "updates" ? rail.win.accentText : rail.win.txt2
                                font.family: rail.win.uiFont
                                font.pixelSize: rail.win.typePx(11)
                                font.weight: Font.DemiBold
                            }
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }

            // The catalogue, quietly: a working light while it is being built, then its size.
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: rail.compact ? 0 : rail.design.space3
                Layout.bottomMargin: rail.design.space2
                spacing: rail.design.space2
                Item {
                    Layout.preferredWidth: rail.win.fs(12)
                    Layout.preferredHeight: rail.win.fs(12)
                    Layout.fillWidth: rail.compact
                    // The rail's working light. It belongs to the line beside it — "Preparing
                    // the catalogue…" — so it pulses while the index is actually being built and
                    // goes solid the moment it is ready.
                    //
                    // It once pulsed forever, with no `running:` guard: one 8 px dot animating
                    // without end kept the render loop at full frame rate, ~11% of a CPU core on an
                    // idle desktop. It runs only while the launch-time poll is still waiting.
                    Rectangle {
                        id: railWorkingDot
                        anchors.centerIn: parent
                        width: rail.win.fs(8)
                        height: width
                        radius: height / 2
                        color: rail.win.indexReady ? rail.win.positiveInk : rail.win.accent
                        property real pulse: 1
                        opacity: railWorkingPulse.running ? railWorkingDot.pulse : 1
                        SequentialAnimation {
                            id: railWorkingPulse
                            // win.indexPolling (main.qml's index poll) bounds the pulse: the poll gives
                            // up after 36 ticks, and the light then stops with it.
                            running: !rail.win.indexReady && rail.win.indexPolling && rail.win.motionEnabled
                            loops: Animation.Infinite
                            NumberAnimation {
                                target: railWorkingDot; property: "pulse"
                                from: 0.35; to: 1; duration: rail.win.motionEnabled ? rail.design.motionPortal * 2 : 0
                            }
                            NumberAnimation {
                                target: railWorkingDot; property: "pulse"
                                from: 1; to: 0.35; duration: rail.win.motionEnabled ? rail.design.motionPortal * 2 : 0
                            }
                        }
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    visible: !rail.compact
                    Layout.fillWidth: true
                    text: !rail.win.indexReady
                        ? (rail.win.indexPolling ? rail.win.local("يُجهَّز الكتالوج…", "Preparing the catalogue…")
                                                 : rail.win.local("الكتالوج الأساسي", "Essential catalogue"))
                        : rail.win.appsCountText(rail.win.browseOrder.length)
                    color: rail.win.txt2
                    font.family: rail.win.uiFont
                    font.pixelSize: rail.win.typePx(11)
                    elide: Text.ElideRight
                }
            }
        }
    }
}
