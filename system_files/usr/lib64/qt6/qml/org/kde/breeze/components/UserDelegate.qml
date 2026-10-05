/*
    SPDX-FileCopyrightText: 2014 David Edmundson <davidedmundson@kde.org>
    SPDX-FileCopyrightText: 2014 Aleix Pol Gonzalez <aleixpol@blue-systems.com>
    SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity

    SPDX-License-Identifier: LGPL-2.0-or-later
*/

// MoOS: Plasma's own user avatar, wearing the MoOS ring.
//
// The login greeter's QML is compiled in, and the lock screen's is upstream's
// own, but the avatar both draw comes from this file on disk — so this is where
// MoOS reaches the face on every session surface (the power screen uses it too).
//
// What MoOS owns here, and nothing else changed:
//   1. The ring around the face is the brand colour and LIGHTS for the selected
//      user: on a two-user machine the ring is what tells you who you are about
//      to log in as. Upstream drew a plain white hoop.
//   2. The face sits in light. A still three-step bloom in the accent stands
//      behind the selected user, drawn HERE so the login screen has it too. The
//      lock screen used to paint it from outside, at a hand-measured offset that
//      was a grid unit low and that the login screen could not have at all.
//   3. An account with no photo shows its initial on a two-tone jewel disc. The
//      login greeter hands every such account a stock grey silhouette (a file
//      compiled into its binary) while the lock screen handed over nothing, so
//      the same person was a silhouette at login and a letter one screen later.
//      Both are the letter now. The "type a user name" entry, which is nobody
//      yet, gets a person glyph instead of the first letter of an instruction.
//   4. IBM Plex Sans Arabic on the name, like every other MoOS surface, and a
//      long single name wraps inside the island instead of running past it.
//
// The MoOS emblem that used to be pinned to the corner of the face is gone on
// purpose. It was there so the login screen still said MoOS if its wallpaper
// process had not painted yet; every session surface now carries the corner
// signature, and a logo sitting on the owner's own face was the first thing the
// owner asked to have cleaned up.
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
import org.moos.ui as MoUI

Item {
    id: wrapper

    // If we're using software rendering, draw outlines instead of shadows
    // See https://bugs.kde.org/show_bug.cgi?id=398317
    readonly property bool softwareRendering: GraphicsInfo.api === GraphicsInfo.Software
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property var design: MoUI.Tokens
    // The accent's second tone — decorative only, it never sits under a glyph.
    readonly property color accentB: {
        const c = Kirigami.Theme.highlightColor;
        if (c.hslSaturation < 0.08 || c.hslHue < 0) {
            return Qt.lighter(c, 1.28);
        }
        let nh = c.hslHue + 0.09;
        if (nh > 1) { nh -= 1; }
        return Qt.hsla(nh, Math.min(1, c.hslSaturation), Math.min(0.72, c.hslLightness * 1.08), 1);
    }

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

    // The face block is upstream's seven grid units; the face gives the top
    // six-tenths of one back as air, which is what lets the session island
    // start below the clock's date instead of crowding it.
    readonly property real faceInset: Math.round(Kirigami.Units.gridUnit * 0.6)
    property real faceSize: Kirigami.Units.gridUnit * 7 - faceInset

    // In a list of accounts the session island holds the selected face and a
    // few neighbours each way (it says how many); a face further off would
    // straddle the island's edge, so it waits out of sight until the selection
    // moves towards it. Outside such a list — the lock and power screens —
    // nothing is ever out of reach.
    readonly property int reach: (ListView.view && ListView.view.parent
                                  && ListView.view.parent.userReach !== undefined)
        ? ListView.view.parent.userReach : -1
    readonly property bool inReach: {
        if (reach < 0 || !ListView.view) {
            return true;
        }
        const own = wrapper["index"];
        return own === undefined || Math.abs(own - ListView.view.currentIndex) <= reach;
    }

    opacity: !inReach ? 0 : (isCurrent ? 1.0 : design.mutedOpacity)
    enabled: inReach

    Behavior on opacity {
        OpacityAnimator {
            duration: design.duration(wrapper.motionEnabled,
                                      design.motionGeometry)
        }
    }

    // The account has no picture of its own: nothing was supplied, it failed to
    // load, or it is the silhouette plasma-login-manager compiles into its
    // binary for every account without one.
    readonly property bool placeholderFace: face.status === Image.Error
        || face.status === Image.Null
        || String(wrapper.avatarPath).indexOf("/org/kde/plasma/login/") >= 0
    // The "type a user name" entry has no account behind it yet.
    readonly property bool anonymous: wrapper.userName === ""

    // The bloom: three still discs of the accent behind the selected face.
    // Plain rectangles — no effect layer, nothing animated.
    Repeater {
        // Sized as a share of the face, so the small portrait on the power
        // screen wears the same bloom in proportion.
        model: [
            { grow: 0.54, glow: 0.035 },
            { grow: 0.33, glow: 0.06 },
            { grow: 0.14, glow: 0.10 },
        ]
        Rectangle {
            required property var modelData
            anchors.centerIn: imageSource
            width: Math.round(imageSource.width * (1 + modelData.grow))
            height: width
            radius: width / 2
            color: Kirigami.Theme.highlightColor
            opacity: modelData.glow
            visible: wrapper.isCurrent && !wrapper.softwareRendering
        }
    }

    // The disc under the picture — MoOS glass in the accent's two tones, so an
    // initial sits on a jewel rather than on a flat grey wash.
    Rectangle {
        anchors.centerIn: imageSource
        width: imageSource.width - 2 // Subtract to prevent fringing
        height: width
        radius: width / 2

        color: Kirigami.Theme.backgroundColor
        opacity: wrapper.softwareRendering ? design.mutedOpacity : 1
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            visible: !wrapper.softwareRendering
            opacity: wrapper.isCurrent ? 1 : design.disabledOpacity
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.alpha(wrapper.accentB, 0.46) }
                GradientStop { position: 1.0; color: Qt.alpha(Kirigami.Theme.highlightColor, 0.18) }
            }
        }
    }

    Item {
        id: imageSource
        anchors.top: parent.top
        anchors.topMargin: wrapper.faceInset
        anchors.horizontalCenter: parent.horizontalCenter

        Behavior on width {
            PropertyAnimation {
                from: wrapper.faceSize
                duration: design.duration(wrapper.motionEnabled,
                                          design.motionGeometry)
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
            visible: !wrapper.placeholderFace
        }

        Kirigami.Icon {
            id: faceIcon
            source: wrapper.iconSource
            visible: wrapper.placeholderFace
            anchors.fill: parent
            opacity: 0
        }

        // An account without a photo is its initial; the username prompt, which
        // is nobody yet, is a person glyph. The name itself stays immediately
        // below and remains the accessible identity.
        Text {
            anchors.centerIn: parent
            visible: wrapper.placeholderFace && !wrapper.anonymous
            text: wrapper.name.length > 0 ? wrapper.name.charAt(0).toUpperCase() : "M"
            color: Kirigami.Theme.textColor
            // Plex Arabic, never Inter: Inter has no Arabic coverage, so its Arabic
            // text silently falls back to Noto — a second Arabic face on the same
            // screen as the Plex date. Plex Arabic carries a full Latin set. And
            // font.families does not exist on Qt 6.11.1 here — see Logout.qml.
            font.family: design.interfaceFamily
            font.pixelSize: imageSource.width * 0.40
            font.weight: Font.Medium
            renderType: Text.QtRendering
        }
        Kirigami.Icon {
            anchors.centerIn: parent
            visible: wrapper.placeholderFace && wrapper.anonymous
            width: Math.round(imageSource.width * 0.46)
            height: width
            source: "user-symbolic"
            isMask: true
            color: Kirigami.Theme.textColor
        }
    }

    ShaderEffect {
        anchors.top: parent.top
        anchors.topMargin: wrapper.faceInset
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

    PlasmaComponents3.Label {
        id: usernameDelegate

        anchors.top: imageSource.bottom
        anchors.topMargin: Math.round(Kirigami.Units.gridUnit * 0.45)
        anchors.horizontalCenter: parent.horizontalCenter

        // Make it bigger than other fonts to match the scale of the avatar better
        font.family: design.interfaceFamily
        font.pointSize: wrapper.fontSize + 4

        // A lone user is not boxed in by neighbours, but the name still has to
        // stay inside the island that frames it (sixteen grid units of prompts).
        width: wrapper.constrainText
            ? parent.width
            : Math.min(implicitWidth, Kirigami.Units.gridUnit * 16)
        text: wrapper.name
        textFormat: Text.PlainText
        style: wrapper.softwareRendering ? Text.Outline : Text.Normal
        styleColor: wrapper.softwareRendering ? Kirigami.Theme.backgroundColor : "transparent" //no outline, doesn't matter
        wrapMode: Text.WordWrap
        // Two lines either way. Upstream allows three beside neighbours; the
        // session island keeps room under the faces for exactly one more.
        maximumLineCount: 2
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
