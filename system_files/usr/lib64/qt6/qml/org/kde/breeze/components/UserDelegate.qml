/*
    SPDX-FileCopyrightText: 2014 David Edmundson <davidedmundson@kde.org>
    SPDX-FileCopyrightText: 2014 Aleix Pol Gonzalez <aleixpol@blue-systems.com>
    SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity

    SPDX-License-Identifier: LGPL-2.0-or-later
*/

// MoOS: Plasma's own user avatar, wearing the MoOS ring.
//
// The last stock surface on the login and lock screens. Same story as
// ActionButton and Clock: the greeter's QML is compiled in, but the avatar it
// draws comes from this file on disk, so this is where MoOS reaches it.
//
// What changed, and nothing else did:
//   1. The ring around the face was Kirigami.Theme.textColor — a plain white
//      hoop, the one piece of the login screen still shouting Breeze once the
//      buttons and the clock became MoOS. It is the brand colour now, and it
//      LIGHTS when this user is the selected one: on a two-user machine the ring
//      is what tells you who you are about to log in as, so it should be the
//      thing that answers.
//   2. The disc behind the face was flat Theme.backgroundColor at 60%. It is the
//      MoOS glass tint now — the same brand-tinted surface the action buttons,
//      the dock and the lock card sit on.
//   3. IBM Plex Sans on the name, like every other MoOS surface.
//
// LEFT ALONE ON PURPOSE — the ShaderEffect below. MoOS's own packages ban
// always-on shaders (there is a gate), but this is Plasma's, it is what ROUNDS
// the avatar, and it costs nothing when nobody is logging in. Its shader lives at
// qrc:/qt/qml/org/kde/breeze/components/shaders/UserDelegate.frag.qsb — inside
// libcomponents.so, with no copy on disk. That URL still resolves after build.sh
// drops the module's `prefer` line (the plugin registers its resources when the
// .so loads, independently of where the QML is read from) — VERIFIED by
// rendering this delegate with `prefer` gone: the avatar stayed round. If it had
// not, the login and lock screens would have shipped square avatars.

import QtQuick
import QtQuick.Window

import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami

Item {
    id: wrapper

    // If we're using software rendering, draw outlines instead of shadows
    // See https://bugs.kde.org/show_bug.cgi?id=398317
    readonly property bool softwareRendering: GraphicsInfo.api === GraphicsInfo.Software
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1

    property bool isCurrent: true

    property string name
    property string userName
    property string avatarPath
    property string iconSource
    property bool needsPassword
    property var vtNumber
    property bool constrainText: true
    property alias nameFontSize: usernameDelegate.font.pointSize
    property real fontSize: Kirigami.Theme.defaultFont.pointSize + 2
    signal clicked()

    property real faceSize: Kirigami.Units.gridUnit * 7

    opacity: isCurrent ? 1.0 : 0.75

    Behavior on opacity {
        OpacityAnimator {
            duration: wrapper.motionEnabled ? Kirigami.Units.longDuration : 0
        }
    }

    // Draw a translucent background circle under the user picture — MoOS glass,
    // brand-tinted rather than a flat grey wash.
    Rectangle {
        anchors.centerIn: imageSource
        width: imageSource.width - 2 // Subtract to prevent fringing
        height: width
        radius: width / 2

        color: wrapper.softwareRendering
             ? Kirigami.Theme.backgroundColor
             : Kirigami.Theme.highlightColor
        opacity: wrapper.softwareRendering ? 0.6 : (wrapper.isCurrent ? 0.22 : 0.12)
        Behavior on opacity {
            NumberAnimation {
                duration: wrapper.motionEnabled ? Kirigami.Units.longDuration : 0
                easing.type: Easing.InOutQuad
            }
        }
    }

    Item {
        id: imageSource
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter

        Behavior on width {
            PropertyAnimation {
                from: wrapper.faceSize
                duration: wrapper.motionEnabled ? Kirigami.Units.longDuration : 0
            }
        }
        width: wrapper.isCurrent ? wrapper.faceSize : wrapper.faceSize - Kirigami.Units.gridUnit
        height: width

        //Image takes priority, taking a full path to a file, if that doesn't exist we show an icon
        Image {
            id: face
            source: wrapper.avatarPath
            sourceSize: Qt.size(wrapper.faceSize * Screen.devicePixelRatio, wrapper.faceSize * Screen.devicePixelRatio)
            fillMode: Image.PreserveAspectCrop
            anchors.fill: parent
        }

        Kirigami.Icon {
            id: faceIcon
            source: wrapper.iconSource
            visible: face.status === Image.Error || face.status === Image.Null
            anchors.fill: parent
            opacity: 0
        }

        // A generated profile should still look intentional. Plasma's generic
        // outline avatar made the first MoOS screen look like an unthemed
        // fallback whenever the account had no custom photo. Use the user's
        // first character instead; the accessible/user identity remains the
        // name immediately below and multi-user selection still stays clear.
        Text {
            anchors.centerIn: parent
            visible: faceIcon.visible
            text: wrapper.name.length > 0 ? wrapper.name.charAt(0).toUpperCase() : "M"
            color: Kirigami.Theme.textColor
            // Plex Arabic, never Inter: Inter has no Arabic coverage, so its Arabic
            // text silently falls back to Noto — a second Arabic face on the same
            // screen as the Plex date. Plex Arabic carries a full Latin set. And
            // font.families does not exist on Qt 6.11.1 here — see Logout.qml.
            font.family: "IBM Plex Sans Arabic"
            font.pixelSize: imageSource.width * 0.42
            font.weight: Font.Medium
            renderType: Text.NativeRendering
        }
    }

    ShaderEffect {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter

        width: imageSource.width
        height: imageSource.height

        supportsAtlasTextures: true

        readonly property Item source: ShaderEffectSource {
            sourceItem: imageSource
            // software rendering is just a fallback so we can accept not having a rounded avatar here
            hideSource: wrapper.GraphicsInfo.api !== GraphicsInfo.Software
            live: true // otherwise the user in focus will show a blurred avatar
        }

        // MoOS: the ring is the brand's, and it answers selection. Upstream drew
        // it in textColor — a white hoop that survived every other change.
        //
        // No Behavior here, deliberately: a Behavior on a `readonly` property is
        // rejected, and the way QML rejects it is to fail the WHOLE component
        // silently — `qml: Did not load any objects` with no error line and no
        // avatar. On the login screen that is not a cosmetic slip, it is a
        // greeter that cannot draw its user. Caught by rendering it (2026-07-17);
        // qmllint passed it. The property stays readonly because that is what the
        // ShaderEffect reads it as, and the selection colour simply snaps — which
        // is right anyway, since the size Behavior below already carries the move.
        readonly property color colorBorder: wrapper.isCurrent
            ? Kirigami.Theme.highlightColor
            : Kirigami.Theme.textColor

        fragmentShader: "qrc:/qt/qml/org/kde/breeze/components/shaders/UserDelegate.frag.qsb"
    }

    // The wallpaper service normally carries the full scene, but the login
    // manager must retain MoOS identity even while that service is starting or
    // when it falls back to a plain colour. Keep this badge small: it certifies
    // the surface without competing with the person being authenticated.
    Rectangle {
        anchors {
            right: imageSource.right
            bottom: imageSource.bottom
            rightMargin: -Kirigami.Units.smallSpacing
            bottomMargin: -Kirigami.Units.smallSpacing
        }
        width: Kirigami.Units.gridUnit * 2
        height: width
        radius: width / 2
        color: Kirigami.Theme.backgroundColor
        border.width: 1
        border.color: Kirigami.Theme.highlightColor
        visible: wrapper.isCurrent

        Image {
            anchors.fill: parent
            anchors.margins: Math.max(3, Math.round(parent.width * 0.16))
            source: "file:///usr/share/pixmaps/moos-logo.png"
            fillMode: Image.PreserveAspectFit
            smooth: true
            asynchronous: false
        }
    }

    PlasmaComponents3.Label {
        id: usernameDelegate

        anchors.top: imageSource.bottom
        anchors.topMargin: Kirigami.Units.gridUnit
        anchors.horizontalCenter: parent.horizontalCenter

        // Make it bigger than other fonts to match the scale of the avatar better
        font.family: "IBM Plex Sans Arabic"
        font.pointSize: wrapper.fontSize + 4

        width: wrapper.constrainText ? parent.width : undefined
        text: wrapper.name
        textFormat: Text.PlainText
        style: wrapper.softwareRendering ? Text.Outline : Text.Normal
        styleColor: wrapper.softwareRendering ? Kirigami.Theme.backgroundColor : "transparent" //no outline, doesn't matter
        wrapMode: Text.WordWrap
        maximumLineCount: wrapper.constrainText ? 3 : 1
        elide: Text.ElideRight
        horizontalAlignment: Text.AlignHCenter
        //make an indication that this has active focus, this only happens when reached with keyboard navigation
        font.underline: wrapper.activeFocus
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true

        onClicked: wrapper.clicked()
    }

    Keys.onSpacePressed: wrapper.clicked()
    Keys.onEnterPressed: wrapper.clicked()
    Keys.onReturnPressed: wrapper.clicked()

    Accessible.name: name
    Accessible.role: Accessible.Button
    Accessible.focusable: true
    Accessible.focused: activeFocus
    Accessible.onPressAction: wrapper.clicked()
}
