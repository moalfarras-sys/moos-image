/*
    SPDX-FileCopyrightText: 2016 David Edmundson <davidedmundson@kde.org>
    SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity

    SPDX-License-Identifier: LGPL-2.0-or-later
*/

// MoOS: Plasma's own session screen, wearing the MoOS Auth Island.
//
// PLASMA 6.8 SEAM. Upstream 6.7.90 added `authenticationTypeItem` and the row
// that shows it; both are taken verbatim (three-way merge of upstream
// 6.7.5 -> 6.7.90 onto MoOS's 6.7 file). build_files/plasma_seams.py installs
// this copy only over a 6.8 plasma-workspace.
//
// This ONE file is the layout of both doors into the machine. The login
// greeter's compiled Login.qml and the lock screen's MainBlock.qml are each a
// `SessionManagementScreen { … }`: the user list, the notification line, the
// prompt column and the action row all live here, and each caller only drops
// its password row into the default slot. So the island is drawn here, once,
// and the login screen and the lock screen cannot drift apart again — which is
// exactly what they had done. MoOS used to fork the lock screen's own
// LockScreenUi.qml and MainBlock.qml to draw a card behind them, hand-sized
// from outside (it was a third taller than its content, and the brand mark sat
// on its rim), while the login screen, out of reach, drew no card at all.
//
// It is also why MoOS no longer forks either of those two lock-screen files.
// They carry the authenticator wiring and upstream rewrites them every release
// (three reviewed variants existed for 6.7, 6.8 beta 1 and beta 2). This file
// carries no authentication at all — it never sees a password, an authenticator
// or a signal other than "a user was picked" — so the island can be as
// ambitious as it likes and can never be the reason someone is locked out.
//
// THE CONTRACT WITH UPSTREAM — every caller is compiled or upstream code:
//   · the public API is upstream's, name for name: notificationMessage,
//     actionItems, actionItemsVisible, userListModel, userListCurrentIndex,
//     userListCurrentItem, showUserList, userList, fontSize, the default
//     slot, userSelected() and playHighlightAnimation();
//   · the two anchor lines are upstream's: the user list's BOTTOM sits on the
//     vertical centre and the prompts start below it. Both greeters place their
//     clock from `userList.y`, and the virtual keyboard moves the stack by the
//     login button's position;
//   · the action row's wrapping rule is upstream's, verbatim.
// What MoOS owns is everything painted: the glass island that hugs the cluster,
// the notice pill, and the face of the stock password field and its key.

import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Templates as T
import QtQuick.Window

import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

FocusScope {
    id: root

    /*
     * Any message to be displayed to the user, visible above the text fields
     */
    property alias notificationMessage: notificationsLabel.text

    /*
     * A list of Items (typically ActionButtons) to be shown in a Row beneath the prompts
     */
    property alias actionItems: actionItemsLayout.children

    /*
     * Whether to show or hide the list of action items as a whole.
     */
    property alias actionItemsVisible: actionItemsLayout.visible

    /*
     * A model with a list of users to show in the view.
     * There are different implementations in sddm greeter (UserModel) and
     * KScreenLocker (SessionsModel), so some roles will be missing.
     *
     * type: {
     *  name: string,
     *  realName: string,
     *  homeDir: string,
     *  icon: string,
     *  iconName?: string,
     *  needsPassword?: bool,
     *  displayNumber?: string,
     *  vtNumber?: int,
     *  session?: string
     *  isTty?: bool,
     * }
     */
    property alias userListModel: userListView.model

    /*
     * Self explanatory
     */
    property alias userListCurrentIndex: userListView.currentIndex
    property alias userListCurrentItem: userListView.currentItem
    property bool showUserList: true

    property alias userList: userListView

    property real fontSize: Kirigami.Theme.defaultFont.pointSize + 2

    /*
     * The item used to indicate the type of authentication required, e.g. a password or fingerprint icon.
     */
    property Item authenticationTypeItem: null

    default property alias _children: innerLayout.children

    signal userSelected()

    function playHighlightAnimation() {
        bounceAnimation.start();
    }

    // ── MoOS session tokens ────────────────────────────────────────────────
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property var design: MoUI.Tokens
    readonly property color accentA: Kirigami.Theme.highlightColor
    // The second hue of the two-tone signature, derived from the live accent so
    // every family gets its own pair. Decorative only: it has no paired ink in
    // a KDE colour scheme, so it never sits under a glyph.
    readonly property color accentB: {
        const c = Kirigami.Theme.highlightColor;
        if (c.hslSaturation < 0.08 || c.hslHue < 0) {
            return Qt.lighter(c, 1.28);
        }
        let nh = c.hslHue + 0.09;
        if (nh > 1) { nh -= 1; }
        return Qt.hsla(nh, Math.min(1, c.hslSaturation), Math.min(0.72, c.hslLightness * 1.08), 1);
    }

    // The island hugs the cluster it frames: the prompt column is upstream's
    // sixteen grid units, and the plate adds one even margin around it. On a
    // screen too short to spare that margin above the face (a 640x480 firmware
    // mode leaves the clock about a hundred pixels) the top margin gives way
    // first, so the plate can never climb into the clock.
    readonly property real islandPad: Math.round(Kirigami.Units.gridUnit * 1.5)
    readonly property real islandPadTop: Math.round(Math.max(
        Kirigami.Units.smallSpacing * 2,
        Math.min(islandPad, userListView.y * 0.16)))
    // One account: the island is the prompt column plus its margin. Several:
    // it widens to hold them. When they all fit they stand in one row (MoOS's
    // UserList) and the island is as wide as the row. Otherwise the list is
    // upstream's carousel, and the island holds the selected face and one
    // neighbour each way — two where there is room — so nobody's face straddles
    // the plate's edge. `userReach` is how many neighbours that is; MoOS's
    // UserDelegate reads it and steps aside beyond it.
    readonly property bool everyoneShown: userListView.showsEveryone === true
    readonly property int userSlots: {
        if (userListView.count < 2 || !userListView.visible) {
            return 1;
        }
        if (everyoneShown) {
            return userListView.count;
        }
        const fits = Math.floor((root.width - Kirigami.Units.gridUnit - islandPad * 2)
                                / userListView.userItemWidth);
        const wanted = userListView.count > 3 ? 5 : 3;
        return Math.max(1, Math.min(wanted, fits % 2 === 0 ? fits - 1 : fits));
    }
    readonly property int userReach: everyoneShown ? userListView.count
                                                   : (userSlots - 1) / 2
    readonly property real islandWidth: Math.min(
        root.width - Kirigami.Units.gridUnit,
        Math.max(Kirigami.Units.gridUnit * 16,
                 userListView.userItemWidth * userSlots) + islandPad * 2)
    // Where there are neighbours, a neighbour's name may run to a second line,
    // and it stands over the password row's own columns. Upstream makes room
    // by lifting the whole user list three grid units, which takes the room
    // out of the clock's band; the prompts step DOWN instead, and by the two
    // lines MoOS's delegate allows, so the clock never has to know.
    readonly property real neighbourRoom: userListView.constrainText
        ? Kirigami.Units.gridUnit * 2 : 0

    // Both greeters fade this screen by fading the StackView that holds it, so
    // the holder's opacity IS the doorway opening. The island rides it — a few
    // pixels of rise, in lockstep with upstream's own animation — instead of
    // running a clock of its own: nothing here can be out of step with the
    // fade, loop, or move at all when the owner has animations off.
    readonly property real stage: (motionEnabled && parent) ? parent.opacity : 1
    readonly property bool staged: stage > 0.02
    onStagedChanged: {
        if (staged) {
            island.arrivalPlayed = false;
            island.playArrival();
        }
    }
    transform: Translate {
        y: (1 - root.stage) * Kirigami.Units.gridUnit * 0.8
    }

    // A refusal wears the negative role; a hint (Caps Lock, a PAM prompt) must
    // not — a red pill for "Caps Lock is on" would cry wolf at the one place
    // where red has to mean something. This screen is only ever handed a
    // string, so it recognises a refusal by the same catalogue entries the two
    // callers build theirs from, in whatever language the session speaks.
    readonly property bool noticeIsAlert: {
        const text = notificationsLabel.text;
        if (text === "") {
            return false;
        }
        const refusals = [
            i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:status", "Unlocking failed"),
            i18nd("plasma_login", "Login Failed"),
        ];
        for (let i = 0; i < refusals.length; ++i) {
            if (refusals[i] !== "" && text.indexOf(refusals[i]) >= 0) {
                return true;
            }
        }
        return false;
    }

    // ── The MoOS face of the stock password row (visual only) ──────────────
    // The login greeter's field and key are instantiated by compiled QML and
    // the lock screen's by upstream's MainBlock; neither can be edited, and
    // both arrive here as children of the prompt slot. Plasma's TextField says
    // in its own source that it "can't guarantee that background will always be
    // present or have the margins property" — replacing the background is a
    // supported thing to do — so each stock control is handed a MoOS background
    // (and the key its glyph), the Complementary colour set the island wears,
    // and an accessible name or role where it had none. Nothing else is
    // written: not its text, echo mode, focus, a handler or a signal. What is
    // read is what a background needs to draw itself — focus, hover, press, the
    // icon's name and the placeholder. A control this does not recognise keeps
    // its stock face, which is the safe failure; a throw here is left loud on
    // purpose, because the build's greeter probe fails on it.
    property var adoptedControls: []

    function adoptControl(control) {
        if (root.adoptedControls.indexOf(control) >= 0) {
            return;
        }
        if (control instanceof T.TextField) {
            root.adoptedControls.push(control);
            control.Kirigami.Theme.inherit = false;
            control.Kirigami.Theme.colorSet = Kirigami.Theme.Complementary;
            control.background = fieldFace.createObject(control, { control: control });
            // Both greeters run outside a normal application window, where an
            // assistive client cannot be assumed to fall back to the
            // placeholder. A field nobody named says what it asks for.
            if (control.Accessible.name === "") {
                control.Accessible.name = Qt.binding(() => control.placeholderText);
            }
        } else if (control instanceof T.Button && !(control instanceof T.ToolButton)) {
            root.adoptedControls.push(control);
            control.Kirigami.Theme.inherit = false;
            control.Kirigami.Theme.colorSet = Kirigami.Theme.Complementary;
            control.background = keyFace.createObject(control, { control: control });
            control.contentItem = keyGlyph.createObject(control, { control: control });
            // The key now shows a drawn arrow instead of text or a themed icon,
            // so its role is stated rather than inferred.
            control.Accessible.role = Accessible.Button;
        }
    }

    function adoptPromptControls() {
        // The slot's own children and one level into a row — the password row
        // is `RowLayout { field; key }`. Deliberately no deeper: the media
        // controls live further down and keep the face they were given.
        const slot = innerLayout.children;
        for (let i = 0; i < slot.length; ++i) {
            if (slot[i] instanceof RowLayout) {
                const row = slot[i].children;
                for (let j = 0; j < row.length; ++j) {
                    root.adoptControl(row[j]);
                }
            } else {
                root.adoptControl(slot[i]);
            }
        }
    }

    Component.onCompleted: adoptPromptControls()

    Component {
        id: fieldFace

        Rectangle {
            id: field
            required property T.TextField control
            // Plasma's TextField takes its padding from these when they exist.
            readonly property QtObject margins: QtObject {
                readonly property real left: Math.round(Kirigami.Units.gridUnit * 0.9)
                readonly property real right: left
                readonly property real top: Math.round(Kirigami.Units.smallSpacing * 2.5)
                readonly property real bottom: top
            }

            implicitWidth: Kirigami.Units.gridUnit * 8 + margins.left + margins.right
            implicitHeight: root.design.targetControl
            radius: root.design.radiusControl + 2
            color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                           Kirigami.Theme.backgroundColor.g,
                           Kirigami.Theme.backgroundColor.b,
                           field.control.activeFocus ? root.design.mutedOpacity
                                                     : root.design.disabledOpacity)
            border.width: field.control.activeFocus ? root.design.focusWidth
                                                    : root.design.borderHairline
            border.color: field.control.activeFocus
                ? Qt.rgba(root.accentA.r, root.accentA.g, root.accentA.b, 0.95)
                : Qt.rgba(Kirigami.Theme.textColor.r,
                          Kirigami.Theme.textColor.g,
                          Kirigami.Theme.textColor.b,
                          field.control.hovered ? 0.34 : 0.20)
            Behavior on border.color { ColorAnimation {
                duration: root.design.duration(root.motionEnabled, root.design.motionGeometry)
            } }

            // The focus halo: one soft ring outside the field, lit only while
            // the field has the keyboard.
            Rectangle {
                z: -1
                anchors.fill: parent
                anchors.margins: -Kirigami.Units.smallSpacing
                radius: parent.radius + Kirigami.Units.smallSpacing
                color: "transparent"
                border.width: Kirigami.Units.smallSpacing
                border.color: Qt.rgba(root.accentA.r, root.accentA.g, root.accentA.b,
                                      field.control.activeFocus ? 0.16 : 0.0)
                Behavior on border.color { ColorAnimation {
                    duration: root.design.duration(root.motionEnabled, root.design.motionGeometry)
                } }
            }
        }
    }

    Component {
        id: keyFace

        // The Portal key. Its fill stays on accentA — the scheme's Selection
        // background — because highlightedTextColor is contrast-gated against
        // that exact role in every MoOS palette; accentB lives in the rim only.
        Rectangle {
            id: key
            required property T.AbstractButton control

            implicitWidth: root.design.targetControl
            implicitHeight: root.design.targetControl
            radius: root.design.radiusControl + 2
            color: root.accentA
            opacity: key.control.enabled ? 1 : root.design.disabledOpacity
            scale: key.control.down ? root.design.pressScale : 1.0
            border.width: key.control.visualFocus ? root.design.focusWidth
                                                  : root.design.borderHairline
            border.color: Qt.rgba(root.accentB.r, root.accentB.g, root.accentB.b,
                                  (key.control.visualFocus || key.control.hovered) ? 0.95 : 0.50)
            Behavior on scale { NumberAnimation {
                duration: root.design.duration(root.motionEnabled, root.design.motionFast)
                easing.type: root.design.easeStandard
            } }

            // Hover and press read as light on the key, never as a second hue.
            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                color: Kirigami.Theme.highlightedTextColor
                opacity: key.control.down ? 0.16 : (key.control.hovered ? 0.08 : 0)
            }
        }
    }

    Component {
        id: keyGlyph

        Item {
            id: glyph
            required property T.AbstractButton control
            readonly property bool labelled: glyph.control.text !== ""

            implicitWidth: glyph.labelled
                ? keyLabel.implicitWidth + Kirigami.Units.gridUnit * 2
                : root.design.iconControl
            implicitHeight: root.design.iconControl

            // Both greeters ask for "go-next" (or "go-previous" under RTL), and
            // the icon theme answers with a hairline chevron that all but
            // vanishes on the accent. The key draws its own arrow — the same
            // weight as the type beside it — and falls back to the icon theme
            // for any name it does not know.
            readonly property bool forward: glyph.control.icon.name === "go-next"
            readonly property bool backward: glyph.control.icon.name === "go-previous"

            Shape {
                anchors.centerIn: parent
                visible: !glyph.labelled && (glyph.forward || glyph.backward)
                width: root.design.iconControl
                height: root.design.iconControl
                preferredRendererType: Shape.CurveRenderer
                transform: Scale {
                    origin.x: root.design.iconControl / 2
                    xScale: glyph.backward ? -1 : 1
                }
                ShapePath {
                    strokeWidth: 2
                    strokeColor: Kirigami.Theme.highlightedTextColor
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.RoundJoin
                    startX: 3; startY: 10
                    PathLine { x: 17; y: 10 }
                    PathMove { x: 11; y: 4 }
                    PathLine { x: 17; y: 10 }
                    PathLine { x: 11; y: 16 }
                }
            }
            Kirigami.Icon {
                anchors.centerIn: parent
                visible: !glyph.labelled && !glyph.forward && !glyph.backward
                width: root.design.iconControl
                height: root.design.iconControl
                source: glyph.control.icon.name
                isMask: true
                color: Kirigami.Theme.highlightedTextColor
            }
            PlasmaComponents3.Label {
                id: keyLabel
                anchors.centerIn: parent
                visible: glyph.labelled
                text: glyph.control.Kirigami.MnemonicData.richTextLabel
                textFormat: Text.StyledText
                color: Kirigami.Theme.highlightedTextColor
                font.family: root.design.interfaceFamily
                font.weight: Font.DemiBold
            }
        }
    }

    // ── The Auth Island ────────────────────────────────────────────────────
    // One mineral-glass plate behind the whole cluster — face, name, notice and
    // prompts — sized FROM that cluster, so it is exactly as tall as what it
    // frames on a single-user lock screen and on a login screen showing a
    // username field, a fingerprint hint and media controls alike. Declared
    // first: z-order is declaration order, and the plate sits behind.
    MoUI.GlassSurface {
        id: island

        // MoOS's UserDelegate says how far below the list's top its face
        // starts; a delegate that does not say so starts at the top.
        readonly property real faceInset: (userListView.currentItem
            && userListView.currentItem.faceInset !== undefined)
            ? userListView.currentItem.faceInset : 0
        readonly property real topEdge: userListView.visible
            ? userListView.y + faceInset - root.islandPadTop
            : prompts.y - root.islandPad
        readonly property real bottomEdge: prompts.y + promptBlock.y + promptBlock.height
                                           + root.islandPad

        x: Math.round((root.width - width) / 2)
        y: Math.round(topEdge)
        width: root.islandWidth
        height: Math.round(bottomEdge - topEdge)
        radius: root.design.radiusDialog
        depth: root.design.glassLevelDialog
        surfaceColor: Kirigami.Theme.backgroundColor
        fillOpacity: root.design.sessionGlassOpacity
        inkColor: Kirigami.Theme.textColor
        accentColor: root.accentA
        border.color: Qt.rgba(Kirigami.Theme.textColor.r,
                              Kirigami.Theme.textColor.g,
                              Kirigami.Theme.textColor.b, 0.16)

        // Sheen — the catch-light across the plate's upper field.
        Rectangle {
            anchors { top: parent.top; left: parent.left; right: parent.right }
            anchors.margins: 1
            height: parent.height * 0.42
            radius: parent.radius - 1
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(Kirigami.Theme.textColor.r,
                    Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.06) }
                GradientStop { position: 1.0; color: Qt.rgba(Kirigami.Theme.textColor.r,
                    Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.0) }
            }
        }
        // The crest: the two-tone mark every MoOS session surface carries on
        // its top edge.
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: -height / 2
            width: Kirigami.Units.gridUnit * 4
            height: 3
            radius: height / 2
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: root.accentA }
                GradientStop { position: 1; color: root.accentB }
            }
        }
    }
    // The maker's mark, on the island's lower edge — the counterpart of the
    // crest on its upper one. The session signature lives in the corner of the
    // scene, but on the login screen that scene is painted by ANOTHER process
    // (plasma-login-wallpaper), and when it is late or absent the greeter stands
    // on a flat colour. The island is drawn by the greeter itself, so this is
    // the one mark that is on screen whenever a password can be typed. It used
    // to be an emblem pinned to the corner of the user's face.
    Rectangle {
        id: makersMark
        anchors.horizontalCenter: island.horizontalCenter
        anchors.verticalCenter: island.bottom
        width: makersRow.implicitWidth + Kirigami.Units.gridUnit
        height: Math.round(Kirigami.Units.gridUnit * 1.2)
        radius: height / 2
        color: Kirigami.Theme.backgroundColor
        border.width: root.design.borderHairline
        border.color: Qt.rgba(Kirigami.Theme.textColor.r,
                              Kirigami.Theme.textColor.g,
                              Kirigami.Theme.textColor.b, 0.16)

        Row {
            id: makersRow
            anchors.centerIn: parent
            spacing: Math.round(Kirigami.Units.smallSpacing * 1.25)
            // The wordmark reads left to right in every language.
            LayoutMirroring.enabled: false

            Image {
                anchors.verticalCenter: parent.verticalCenter
                width: Math.round(makersMark.height * 0.62)
                height: width
                // The canonical mark the identity firewall pins.
                source: "file:///usr/share/pixmaps/moos-logo.png"
                sourceSize: Qt.size(width * Screen.devicePixelRatio,
                                    height * Screen.devicePixelRatio)
                fillMode: Image.PreserveAspectFit
                asynchronous: false
                smooth: true
                mipmap: true
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "MoOS"
                color: Kirigami.Theme.textColor
                opacity: root.design.mutedOpacity
                font.family: root.design.interfaceFamily
                font.pixelSize: Math.round(makersMark.height * 0.52)
                font.weight: Font.DemiBold
                font.letterSpacing: 1
                renderType: Text.QtRendering
            }
        }
    }

    // Depth halo — three still plates behind the island stand in for a drop
    // shadow, so it floats off the scene with no offscreen effect.
    Repeater {
        model: [
            { grow: 1.1, ink: 0.04 },
            { grow: 0.7, ink: 0.06 },
            { grow: 0.35, ink: 0.08 },
        ]
        Rectangle {
            required property var modelData
            z: -1
            anchors.fill: island
            anchors.margins: -Kirigami.Units.gridUnit * modelData.grow
            radius: island.radius + Kirigami.Units.gridUnit * modelData.grow
            color: Qt.rgba(0, 0, 0, modelData.ink)
        }
    }

    // FIXME: move this component into a layout, rather than abusing
    // anchors and implicitly relying on other components' built-in
    // whitespace to avoid items being overlapped.
    UserList {
        id: userListView
        visible: root.showUserList && y > 0
        anchors {
            bottom: parent.verticalCenter
            left: parent.left
            right: parent.right
        }
        fontSize: root.fontSize
        // bubble up the signal
        onUserSelected: root.userSelected()
    }

    // The prompts, then the action buttons. Upstream stretched the prompt
    // block to ten grid units to push the actions down; the island hugs the
    // prompts instead, and one fixed gap keeps the actions clear of its edge.
    ColumnLayout {
        id: prompts
        anchors.top: parent.verticalCenter
        anchors.topMargin: Kirigami.Units.largeSpacing + root.neighbourRoom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        spacing: Kirigami.Units.smallSpacing

        // Plasma 6.8: the authentication-type indicator, upstream's, verbatim.
        RowLayout {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 16
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            Layout.fillHeight: false
            Layout.topMargin: Kirigami.Units.largeSpacing
            spacing: 0
            visible: root.authenticationTypeItem !== null
            children: [root.authenticationTypeItem]
        }

        // The notice line. The slot always keeps one line's height, which is
        // what stops the cluster jumping when a message arrives; the pill
        // inside it is only there while there is something to say.
        Item {
            id: noticeSlot
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 16
            implicitHeight: Math.max(noticePill.implicitHeight,
                                     noticeMetrics.height + Kirigami.Units.largeSpacing)
                            + Kirigami.Units.smallSpacing * 2

            FontMetrics {
                id: noticeMetrics
                font: notificationsLabel.font
            }

            Rectangle {
                id: noticePill
                anchors.centerIn: parent

                // The pill takes its size from the label and the label caps its
                // OWN width: a wrapping Text whose width comes from its parent
                // while the parent's implicit width comes from the Text is the
                // classic binding loop.
                implicitWidth: notificationsLabel.width + Kirigami.Units.gridUnit * 1.6
                implicitHeight: notificationsLabel.implicitHeight + Kirigami.Units.largeSpacing
                width: implicitWidth
                height: implicitHeight
                // A pill for one line, a rounded card when PAM says something
                // long enough to wrap. The message is never elided: here the
                // text IS the reason the machine refused.
                radius: Math.min(height / 2, Kirigami.Units.gridUnit * 1.2)
                visible: opacity > 0
                opacity: notificationsLabel.text !== "" ? 1 : 0
                transform: Translate {
                    y: (1 - noticePill.opacity) * Kirigami.Units.gridUnit * 0.4
                }

                color: root.noticeIsAlert
                    ? Qt.rgba(Kirigami.Theme.negativeTextColor.r,
                              Kirigami.Theme.negativeTextColor.g,
                              Kirigami.Theme.negativeTextColor.b, 0.16)
                    : Qt.rgba(Kirigami.Theme.textColor.r,
                              Kirigami.Theme.textColor.g,
                              Kirigami.Theme.textColor.b,
                              root.design.surfaceRestingOpacity)
                border.width: root.design.borderHairline
                border.color: root.noticeIsAlert
                    ? Qt.rgba(Kirigami.Theme.negativeTextColor.r,
                              Kirigami.Theme.negativeTextColor.g,
                              Kirigami.Theme.negativeTextColor.b, 0.65)
                    : Qt.rgba(Kirigami.Theme.textColor.r,
                              Kirigami.Theme.textColor.g,
                              Kirigami.Theme.textColor.b, 0.20)

                Behavior on opacity { NumberAnimation {
                    duration: root.design.duration(root.motionEnabled, root.design.motionGeometry)
                    easing.type: root.design.easeStandard
                } }

                PlasmaComponents3.Label {
                    id: notificationsLabel
                    anchors.centerIn: parent
                    width: Math.min(implicitWidth, Kirigami.Units.gridUnit * 14)
                    font.family: root.design.interfaceFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    font.weight: Font.Medium
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    color: root.noticeIsAlert ? Kirigami.Theme.negativeTextColor
                                              : Kirigami.Theme.textColor
                }

                SequentialAnimation {
                    id: bounceAnimation
                    loops: 1
                    PropertyAnimation {
                        target: noticePill
                        properties: "scale"
                        from: 1.0
                        to: 1.06
                        duration: root.design.duration(root.motionEnabled,
                                                       root.design.motionGeometry)
                        easing.type: Easing.OutQuad
                    }
                    PropertyAnimation {
                        target: noticePill
                        properties: "scale"
                        from: 1.06
                        to: 1.0
                        duration: root.design.duration(root.motionEnabled,
                                                       root.design.motionGeometry)
                        easing.type: Easing.InQuad
                    }
                }
            }
        }

        ColumnLayout {
            id: promptBlock
            Layout.maximumWidth: Kirigami.Units.gridUnit * 16
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            ColumnLayout {
                id: innerLayout
                Layout.alignment: Qt.AlignHCenter
                Layout.fillWidth: true
                // A username field over a password row needs a visible seam.
                spacing: Kirigami.Units.smallSpacing * 2
                onChildrenChanged: Qt.callLater(root.adoptPromptControls)
            }
        }

        // Clear of the island's lower edge. It gives way on a short screen,
        // but never below the plate's own margin.
        Item {
            Layout.fillWidth: true
            Layout.minimumHeight: root.islandPad + Kirigami.Units.gridUnit * 0.8
            Layout.preferredHeight: root.islandPad + Kirigami.Units.gridUnit * 1.8
            Layout.maximumHeight: Layout.preferredHeight
            Layout.fillHeight: true
        }

        Item {
            Layout.alignment: Qt.AlignHCenter
            implicitHeight: actionItemsLayout.implicitHeight
            implicitWidth: actionItemsLayout.implicitWidth
            GridLayout {
                id: actionItemsLayout
                anchors.centerIn: parent

                readonly property int spacing: Kirigami.Units.largeSpacing
                rowSpacing: spacing
                columnSpacing: spacing

                readonly property int buttonCount: visibleChildren.length
                readonly property int singleRowWidth: (children[0].implicitWidth * buttonCount) + (spacing * (buttonCount - 1))
                columns: singleRowWidth < root.width ? buttonCount : Math.ceil(buttonCount / 2)
            }
        }
        Item {
            Layout.fillHeight: true
        }
    }
}
