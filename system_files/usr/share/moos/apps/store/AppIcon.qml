pragma ComponentBehavior: Bound

import QtQuick

// Mo Store — an app's picture. Its own icon when one loads (a local file always, an internet
// address only while the person allows app pictures from the internet); otherwise a designed
// monogram: a rounded tile in the app's own colour (its branding, the catalogue's accent, or a
// stable hue from its id), lit from the top like a real glass tile, carrying the first letter of
// its name. A small badge on the trailing corner can say where it comes from (web, Windows,
// Android). Never another system's logo.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: icon
    required property var win
    property var app: null
    property real size: win.fs(48)
    property bool showKind: false
    // A large monogram on a plate casts a soft shadow; a real icon keeps its own shading, since a
    // shadow under transparent artwork would show as a dark square.
    property bool lifted: false
    // The picture is decoded at the size it is shown, times the screen's scale.
    readonly property real decode: Math.ceil(icon.size * Math.max(1, Screen.devicePixelRatio))
    readonly property string source: win.iconSource(icon.app)
    readonly property bool hasPicture: picture.status === Image.Ready
    readonly property color base: win.appColour(icon.app)
    readonly property color ink: win.inkOnLarge(icon.base)
    readonly property string kind: win.appKind(icon.app)
    readonly property bool kindBadge: icon.showKind
        && (icon.kind === "webapp" || icon.kind === "web" || icon.kind === "windows" || icon.kind === "android")

    implicitWidth: icon.size
    implicitHeight: icon.size
    width: icon.size
    height: icon.size
    Accessible.ignored: true

    Image {
        id: picture
        anchors.fill: parent
        anchors.margins: icon.size * 0.04
        source: icon.source
        sourceSize.width: icon.decode
        sourceSize.height: icon.decode
        fillMode: Image.PreserveAspectFit
        asynchronous: true
        smooth: true
        mipmap: true
        visible: status === Image.Ready
    }

    // The monogram tile.
    Rectangle {
        id: tile
        anchors.fill: parent
        visible: !icon.hasPicture
        SoftShadow {
            win: icon.win
            visible: icon.lifted
            radius: tile.radius
            strength: 1.6
            lift: icon.size / 16
        }
        radius: icon.size * 0.26
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.lighter(icon.base, 1.22) }
            GradientStop { position: 0.55; color: icon.base }
            GradientStop { position: 1; color: Qt.darker(icon.base, 1.22) }
        }
        border.width: icon.lifted ? Math.max(2, icon.size / 48) : Math.max(1, icon.size / 64)
        border.color: icon.lifted ? Qt.rgba(1, 1, 1, 0.42) : Qt.rgba(0, 0, 0, icon.win.lightScheme ? 0.10 : 0.28)

        // The light on the tile: a soft sheen across its upper half and one bright hairline.
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: tile.border.width
            height: parent.height * 0.52
            radius: tile.radius - tile.border.width
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 0.22) }
                GradientStop { position: 1; color: Qt.rgba(1, 1, 1, 0) }
            }
        }
        Rectangle {
            anchors.top: parent.top
            anchors.topMargin: tile.border.width
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width - tile.radius * 1.6
            height: Math.max(1, icon.size / 72)
            color: Qt.rgba(1, 1, 1, 0.38)
        }

        Text {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -icon.size * 0.02
            text: icon.win.initialOf(icon.app)
            color: icon.ink
            font.family: icon.win.uiFont
            font.pixelSize: icon.win.typePx(Math.max(11, Math.round(icon.size * 0.46 / icon.win.fontScale)))
            font.weight: Font.DemiBold
        }
    }

    // Where the app comes from, when that is not obvious: a small disc on the trailing corner.
    Rectangle {
        visible: icon.kindBadge
        width: Math.round(icon.size * 0.38)
        height: width
        radius: width / 2
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.bottomMargin: -Math.round(icon.size * 0.06)
        anchors.rightMargin: -Math.round(icon.size * 0.06)
        color: icon.win.canvas
        border.width: 1
        border.color: icon.win.tint(icon.win.txt, 0.18)
        Glyph {
            win: icon.win
            anchors.centerIn: parent
            width: parent.width * 0.6
            height: width
            name: icon.win.kindGlyph(icon.kind)
            tint: icon.win.txt
        }
    }
}
