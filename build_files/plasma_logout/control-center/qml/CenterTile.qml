// SPDX-License-Identifier: GPL-2.0-or-later
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Item {
    id: tile
    property string label: ""
    property string symbol: ""
    property string detailText: ""
    property var measured: null
    property bool pending: false
    property bool compact: false
    property bool invertIndicator: false
    property bool detailsAvailable: false
    property bool toggleEnabled: true
    property bool detailsEnabled: true
    readonly property bool known: typeof measured === "boolean"
    readonly property bool highlighted: known && (invertIndicator ? !measured : measured)
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property alias settling: settle.running
    readonly property string statusText: pending ? MoUI.Locale.local("جارٍ التحقق", "Checking") : !known ? MoUI.Locale.local("غير متاح", "Unavailable") : detailText.length ? detailText : invertIndicator ? (measured ? MoUI.Locale.local("مكتوم", "Muted") : MoUI.Locale.local("غير مكتوم", "Unmuted")) : measured ? MoUI.Locale.local("مفعّل", "On") : MoUI.Locale.local("متوقف", "Off")
    signal clicked()
    signal detailsRequested()
    implicitHeight: compact ? Math.max(104, compactContent.implicitHeight + 4) : 84
    implicitWidth: 188

    // A measured state change, not a click, plays one finite settle. Reduced
    // motion stops it; it scales paint only and never moves a hit rectangle.
    property real orbScale: 1
    onHighlightedChanged: if (motionEnabled && visible) settle.restart()
    onMotionEnabledChanged: if (!motionEnabled) { settle.stop(); orbScale = 1; }
    SequentialAnimation {
        id: settle
        NumberAnimation { target: tile; property: "orbScale"; to: .86; duration: MoUI.Tokens.motionFast; easing.type: Easing.OutCubic }
        NumberAnimation { target: tile; property: "orbScale"; to: 1; duration: MoUI.Tokens.motionEmphasis; easing.type: Easing.OutBack; easing.overshoot: 2.2 }
    }

    // Liquid Glass control orb: solid native accent when active, a quiet
    // translucent well otherwise. Ink follows the selected native palette.
    component Orb: Rectangle {
        id: orb
        property int size: 40
        property bool active: false
        property bool focusRing: false
        property bool hovered: false
        property bool busy: false
        property bool motion: true
        property real pop: 1
        property string glyph: ""
        implicitWidth: size; implicitHeight: size; radius: size / 2
        scale: pop
        color: active ? Kirigami.Theme.highlightColor : Qt.alpha(Kirigami.Theme.textColor, hovered ? .12 : .07)
        border.width: focusRing ? 2 : 1
        border.color: focusRing ? Kirigami.Theme.highlightColor : Qt.alpha(active ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor, active ? .28 : .12)
        Behavior on color { ColorAnimation { duration: MoUI.Tokens.motionGeometry; easing.type: Easing.OutCubic } }
        // Specular sheen across the upper half: glass by light, not by blur.
        // Its pill (72% x 42%, 6% from the top) stays inside the circle;
        // a full-width pill painted grey corners outside the orb.
        Rectangle {
            objectName: "centerOrbSheen"
            anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: orb.size * .06 }
            width: orb.size * .72; height: orb.size * .42; radius: height / 2
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.alpha("white", orb.active ? .30 : .10) }
                GradientStop { position: 1; color: "transparent" }
            }
        }
        Kirigami.Icon {
            objectName: "centerTileGlyph"
            anchors.centerIn: parent; width: Math.round(orb.size * .55); height: width
            source: orb.glyph
            color: orb.active ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
            isMask: true
        }
        // Pending lasts only as long as the fixed executor transaction.
        SequentialAnimation on opacity {
            running: orb.busy && orb.motion
            loops: Animation.Infinite
            NumberAnimation { to: .55; duration: MoUI.Tokens.motionPage; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1; duration: MoUI.Tokens.motionPage; easing.type: Easing.InOutSine }
        }
        onBusyChanged: if (!busy) opacity = 1
        onMotionChanged: if (!motion) opacity = 1
    }

    Rectangle {
        objectName: "centerTileCard"
        anchors.fill: parent; radius: MoUI.Tokens.radiusCard
        visible: !tile.compact
        color: tile.highlighted ? Qt.alpha(Kirigami.Theme.highlightColor, .14) : Qt.alpha(Kirigami.Theme.textColor, mainButton.hovered ? .075 : .045)
        border.width: mainButton.activeFocus || detailButton.activeFocus ? 2 : 1
        border.color: mainButton.activeFocus || detailButton.activeFocus ? Kirigami.Theme.highlightColor : Qt.alpha(tile.highlighted ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor, tile.highlighted ? .32 : .10)
        Behavior on color { ColorAnimation { duration: MoUI.Tokens.motionGeometry; easing.type: Easing.OutCubic } }
        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
            height: parent.height * .5; radius: MoUI.Tokens.radiusCard - 1
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.alpha("white", .06) }
                GradientStop { position: 1; color: "transparent" }
            }
        }
    }
    RowLayout {
        anchors.fill: parent; spacing: 0
        PC3.AbstractButton {
            id: mainButton
            objectName: "centerTileToggle_" + tile.label
            Layout.fillWidth: true; Layout.fillHeight: true
            enabled: tile.known && tile.toggleEnabled
            leftPadding: tile.compact ? 0 : 10; rightPadding: tile.compact ? 0 : 8
            Accessible.name: tile.label
            Accessible.description: tile.statusText
            activeFocusOnTab: true
            background: null
            contentItem: Item {
                scale: mainButton.down && tile.motionEnabled ? .97 : 1
                Behavior on scale { NumberAnimation { duration: MoUI.Tokens.motionFast; easing.type: Easing.OutCubic } }
                RowLayout {
                    anchors.fill: parent; spacing: 10; visible: !tile.compact
                    Orb { size: 40; active: tile.highlighted; glyph: tile.symbol; hovered: mainButton.hovered; busy: tile.pending; motion: tile.motionEnabled; pop: tile.orbScale; Layout.alignment: Qt.AlignVCenter }
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: 2
                        PC3.Label { text: tile.label; Layout.fillWidth: true; font.weight: Font.DemiBold; textFormat: Text.PlainText; elide: Text.ElideRight }
                        PC3.Label { text: tile.statusText; Layout.fillWidth: true; font.pixelSize: MoUI.Tokens.typeCaption; opacity: .78; textFormat: Text.PlainText; elide: Text.ElideRight }
                    }
                }
                ColumnLayout {
                    id: compactContent
                    anchors.fill: parent; spacing: 4; visible: tile.compact
                    Orb { size: 44; active: tile.highlighted; glyph: tile.symbol; hovered: mainButton.hovered; focusRing: mainButton.activeFocus; busy: tile.pending; motion: tile.motionEnabled; pop: tile.orbScale; Layout.alignment: Qt.AlignHCenter }
                    PC3.Label { text: tile.label; Layout.fillWidth: true; font.pixelSize: MoUI.Tokens.typeSecondary; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
                    PC3.Label { text: tile.statusText; Layout.fillWidth: true; font.pixelSize: MoUI.Tokens.typeCaption; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; opacity: .78 }
                }
            }
            onClicked: tile.clicked()
            PC3.ToolTip { text: tile.compact ? tile.label + " · " + tile.statusText : "" }
        }
        PC3.ToolButton {
            id: detailButton
            objectName: "centerTileDetails_" + tile.label
            visible: tile.detailsAvailable
            enabled: tile.detailsEnabled
            Layout.preferredWidth: 44; Layout.fillHeight: true
            icon.name: MoUI.Locale.rtl ? "go-previous-symbolic" : "go-next-symbolic"
            text: tile.label + " · " + MoUI.Locale.local("التفاصيل", "Details")
            display: PC3.AbstractButton.IconOnly
            onClicked: tile.detailsRequested()
            PC3.ToolTip { text: parent.text }
            background: null
        }
    }
}
