/*
    SPDX-FileCopyrightText: 2016 David Edmundson <davidedmundson@kde.org>
    SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity

    SPDX-License-Identifier: LGPL-2.0-or-later
*/

// MoOS: Plasma's own session screen, wearing the MoOS Auth Island.
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
// Under a name: QtQuick.Shapes has gradients of the same names, and they are not Items.
import Qt5Compat.GraphicalEffects as Effects
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

    default property alias _children: innerLayout.children

    signal userSelected()

    function playHighlightAnimation() {
        bounceAnimation.start();
    }

    // ── MoOS session tokens ────────────────────────────────────────────────
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property bool softwareRendering: GraphicsInfo.api === GraphicsInfo.Software
    readonly property var design: MoUI.Tokens
    // ONE number sizes the whole session family from the window it is in
    // (Tokens.sessionScale): the clock, the faces, this island and the keys grow
    // and shrink together. `unit` is the grid unit at that size.
    readonly property real sessionScale: userListView.sessionScale !== undefined
        ? userListView.sessionScale : design.sessionScale(Window.width, Window.height)
    readonly property real unit: Kirigami.Units.gridUnit * sessionScale
    readonly property color accentA: Kirigami.Theme.highlightColor
    // The second hue of the two-tone signature, derived from the live accent so
    // every family gets its own pair. Decorative only: it has no paired ink in
    // a KDE colour scheme, so it never sits under a glyph.
    readonly property color accentB: root.design.sessionRim(root.accentA, Kirigami.Theme.linkColor)

    // The island hugs the cluster it frames: the prompt column is upstream's
    // sixteen grid units, and the plate adds one even margin around it. On a
    // screen too short to spare that margin above the face (a 640x480 firmware
    // mode leaves the clock about a hundred pixels) the top margin gives way
    // first, so the plate can never climb into the clock.
    readonly property real islandPad: Math.round(unit * 1.5)
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
        const fits = Math.floor((root.width - root.unit - islandPad * 2)
                                / userListView.userItemWidth);
        const wanted = userListView.count > 3 ? 5 : 3;
        return Math.max(1, Math.min(wanted, fits % 2 === 0 ? fits - 1 : fits));
    }
    readonly property int userReach: everyoneShown ? userListView.count
                                                   : (userSlots - 1) / 2
    readonly property real islandWidth: Math.min(
        root.width - root.unit,
        Math.max(root.unit * 16,
                 userListView.userItemWidth * userSlots) + islandPad * 2)
    // Where there are neighbours, a neighbour's name may run to a second line,
    // and it stands over the password row's own columns. Upstream makes room
    // by lifting the whole user list three grid units, which takes the room
    // out of the clock's band; the prompts step DOWN instead, and by the two
    // lines MoOS's delegate allows, so the clock never has to know.
    readonly property real neighbourRoom: userListView.constrainText
        ? root.unit * 2 : 0

    // ── Arrival ─────────────────────────────────────────────────────────────
    // The parent controls visibility. Only decorative surfaces follow this
    // short entrance; the password field and actions keep their final positions.
    readonly property real stage: parent ? parent.opacity : 1
    // The login greeter learns the selected account's look a moment after it
    // starts. Until MoUI.SessionAppearance says it has settled (or its bounded
    // wait ends) the island and its prompts are transparent — never invisible,
    // so the password field keeps the keyboard — and then appear at once in the
    // right colours, instead of arriving in the greeter account's seed palette
    // and repainting a third of a second later. The lock screen is never a
    // greeter, so this is always settled there.
    readonly property bool appearanceSettled: MoUI.SessionAppearance.greeterSettled !== false
    readonly property real settledOpacity: appearanceSettled ? 1 : 0
    readonly property bool staged: stage > 0.02 && appearanceSettled
    property real arrival: motionEnabled ? 0 : 1
    onMotionEnabledChanged: if (!motionEnabled) {
        arrivalRun.stop();
        orbitRun.stop();
        orbitGlow = 0;
        arrival = 1;
    }
    // ── The greeting ────────────────────────────────────────────────────────
    // Read from the clock when the island arrives; nothing polls it.
    property int greetingHour: new Date().getHours()
    readonly property bool anonymousPrompt: userListView.currentItem !== null
        && userListView.currentItem.anonymous === true
    readonly property string greeting: {
        if (root.anonymousPrompt) {
            return MoUI.Locale.local("سجّل الدخول إلى MoOS", "Sign in to MoOS");
        }
        const hour = root.greetingHour;
        if (hour >= 5 && hour < 12) {
            return MoUI.Locale.local("صباح الخير", "Good morning");
        }
        if (hour >= 12 && hour < 17) {
            return MoUI.Locale.local("طاب يومك", "Good afternoon");
        }
        return MoUI.Locale.local("مساء الخير", "Good evening");
    }

    onStagedChanged: {
        if (staged) {
            root.greetingHour = new Date().getHours();
            if (motionEnabled) {
                arrivalRun.restart();
            } else {
                arrival = 1;
            }
            island.arrivalPlayed = false;
            island.playArrival();
            playArrivalRim();
        } else {
            arrivalRun.stop();
            orbitRun.stop();
            orbitGlow = 0;
            arrival = motionEnabled ? 0 : 1;
        }
    }
    NumberAnimation {
        id: arrivalRun
        target: root; property: "arrival"
        from: 0; to: 1
        duration: root.design.duration(root.motionEnabled, root.design.motionGeometry)
    }
    // The slice [from, to] of the arrival, as 0..1.
    function slice(from, to) {
        return Math.max(0, Math.min(1, (root.arrival - from) / (to - from)));
    }
    function settle(t) {    // ease-out cubic
        const u = 1 - t;
        return 1 - u * u * u;
    }
    function spring(t) {    // ease-out back: one small overshoot
        const c = 1.45, u = t - 1;
        return 1 + (c + 1) * u * u * u + c * u * u;
    }

    // A single accent sweep marks arrival. Editing a password never restarts it.
    property real orbitAngle: 0
    property real orbitGlow: 0
    function playArrivalRim() {
        if (!root.motionEnabled || root.softwareRendering) {
            return;
        }
        orbitRun.restart();
    }
    SequentialAnimation {
        id: orbitRun
        NumberAnimation {
            target: root; property: "orbitGlow"; to: 1
            duration: root.design.duration(root.motionEnabled, root.design.motionGeometry)
        }
        NumberAnimation {
            target: root; property: "orbitAngle"
            from: 0; to: 360
            duration: root.design.duration(root.motionEnabled, root.design.motionGeometry)
            easing.type: Easing.InOutSine
        }
        NumberAnimation {
            target: root; property: "orbitGlow"; to: 0
            duration: root.design.duration(root.motionEnabled, root.design.motionFast)
        }
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
    // (and the key its glyph), the selected Window colour set the island wears,
    // and an accessible name or role where it had none. Nothing else is
    // written: not its text, echo mode, focus, a handler or a signal. What is
    // read is what a background needs to draw itself — focus, hover, press, the
    // icon's name and the placeholder. A control this does not recognise keeps
    // its stock face, which is the safe failure; a throw here is left loud on
    // purpose, because the build's greeter probe fails on it.
    property var adoptedControls: []

    function adoptControl(control, partner) {
        if (root.adoptedControls.indexOf(control) >= 0) {
            return;
        }
        if (control instanceof T.TextField) {
            root.adoptedControls.push(control);
            control.Kirigami.Theme.inherit = false;
            control.Kirigami.Theme.colorSet = Kirigami.Theme.Window;
            // In the password row the partner is the key beside the field: the
            // field's face becomes ONE capsule that holds both.
            control.background = fieldFace.createObject(control, {
                control: control,
                key: (partner && partner !== control && partner instanceof T.AbstractButton) ? partner : null
            });
            control.font.pointSize = Qt.binding(() => Math.max(8, Math.round(
                (Kirigami.Theme.defaultFont.pointSize + 2) * root.sessionScale)));
            // Both greeters run outside a normal application window, where an
            // assistive client cannot be assumed to fall back to the
            // placeholder. A field nobody named says what it asks for.
            if (control.Accessible.name === "") {
                control.Accessible.name = Qt.binding(() => control.placeholderText);
            }
        } else if (control instanceof T.Button && !(control instanceof T.ToolButton)) {
            root.adoptedControls.push(control);
            control.Kirigami.Theme.inherit = false;
            control.Kirigami.Theme.colorSet = Kirigami.Theme.Window;
            const face = keyFace.createObject(control, { control: control, partner: partner || null });
            control.background = face;
            control.contentItem = keyGlyph.createObject(control, { control: control, face: face });
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
                // The key takes the field beside it as its partner: it lights
                // when that field has something in it.
                const row = slot[i].children;
                let field = null;
                let key = null;
                for (let j = 0; j < row.length; ++j) {
                    if (row[j] instanceof T.TextField) {
                        field = row[j];
                    } else if (row[j] instanceof T.Button && !(row[j] instanceof T.ToolButton)) {
                        key = row[j];
                    }
                }
                for (let j = 0; j < row.length; ++j) {
                    root.adoptControl(row[j], row[j] === field ? key : field);
                }
            } else {
                root.adoptControl(slot[i]);
            }
        }
    }

    Component.onCompleted: {
        MoUI.SessionAppearance.followOwnSession();
        adoptPromptControls();
        console.info("MOOS_AUTH_SURFACE_READY", Qt.resolvedUrl("SessionManagementScreen.qml"));
    }

    Component {
        id: fieldFace

        // The password capsule. The field's own face stays exactly the field's
        // size (the control lays its text out against it); the plate it draws
        // reaches across the row's gap and holds the key, so field and key read
        // as ONE control — the way the key sits inside the field on every
        // current desktop sign-in. The key is still upstream's own button beside
        // the field, declared after it, so it paints over the plate and keeps
        // its own focus, hit area and accessible role. A field with no key (the
        // user-name prompt) is a capsule on its own.
        Item {
            id: field
            required property T.TextField control
            property T.AbstractButton key: null
            // Plasma's TextField takes its padding from these when they exist.
            readonly property QtObject margins: QtObject {
                readonly property real left: Math.round(root.unit * 0.9)
                readonly property real right: left
                readonly property real top: Math.round(Kirigami.Units.smallSpacing * 2.5 * root.sessionScale)
                readonly property real bottom: top
            }
            readonly property bool joined: field.key !== null && field.key.visible
                && field.key.parent === field.control.parent
            // The key's span in the field's coordinates: both are children of
            // the same row, so their x positions share one origin, mirrored or not.
            readonly property real reachStart: field.joined ? Math.min(0, field.key.x - field.control.x) : 0
            readonly property real reachEnd: field.joined
                ? Math.max(field.control.width, field.key.x + field.key.width - field.control.x)
                : field.control.width
            readonly property bool lit: field.control.activeFocus
                || (field.joined && field.key.activeFocus)

            implicitWidth: root.unit * 8 + margins.left + margins.right
            implicitHeight: Math.round(root.design.targetControl * root.sessionScale)

            Rectangle {
                id: capsule
                x: field.reachStart
                width: field.reachEnd - field.reachStart
                height: parent.height
                radius: Math.round((root.design.radiusControl + 2) * root.sessionScale)
                // The Tidal Cut at control size: the top-trailing corner — the
                // one over the key — is short, like the key's own and like the
                // cut on the island above it.
                readonly property real shortCorner: Math.max(2, Math.round(radius * 0.32))
                topLeftRadius: capsule.LayoutMirroring.enabled ? shortCorner : radius
                topRightRadius: capsule.LayoutMirroring.enabled ? radius : shortCorner
                color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                               Kirigami.Theme.backgroundColor.g,
                               Kirigami.Theme.backgroundColor.b,
                               field.lit ? root.design.mutedOpacity : root.design.disabledOpacity)
                border.width: field.lit ? root.design.focusWidth : root.design.borderHairline
                border.color: field.lit
                    ? Qt.rgba(root.accentA.r, root.accentA.g, root.accentA.b, 0.95)
                    : Qt.rgba(Kirigami.Theme.textColor.r,
                              Kirigami.Theme.textColor.g,
                              Kirigami.Theme.textColor.b,
                              field.control.hovered ? 0.34 : 0.20)
                Behavior on border.color { ColorAnimation {
                    duration: root.design.duration(root.motionEnabled, root.design.motionGeometry)
                } }

                // The catch-light along the capsule's upper edge: glass, not a slot.
                Rectangle {
                    anchors { left: parent.left; right: parent.right; top: parent.top }
                    anchors.margins: parent.border.width
                    height: parent.height * 0.5
                    radius: parent.radius - parent.border.width
                    topLeftRadius: capsule.topLeftRadius - parent.border.width
                    topRightRadius: capsule.topRightRadius - parent.border.width
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.rgba(Kirigami.Theme.textColor.r,
                            Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.07) }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                }

                // The focus halo: one soft ring outside the capsule, lit only
                // while the field or its key has the keyboard.
                Rectangle {
                    z: -1
                    anchors.fill: parent
                    anchors.margins: -Kirigami.Units.smallSpacing
                    radius: parent.radius + Kirigami.Units.smallSpacing
                    topLeftRadius: capsule.topLeftRadius + Kirigami.Units.smallSpacing
                    topRightRadius: capsule.topRightRadius + Kirigami.Units.smallSpacing
                    color: "transparent"
                    border.width: Kirigami.Units.smallSpacing
                    border.color: Qt.rgba(root.accentA.r, root.accentA.g, root.accentA.b,
                                          field.lit ? 0.18 : 0.0)
                    Behavior on border.color { ColorAnimation {
                        duration: root.design.duration(root.motionEnabled, root.design.motionGeometry)
                    } }
                }
            }
        }
    }

    Component {
        id: keyFace

        // The Portal key. It is ARMED when the field beside it holds something
        // (or when there is no field: a password-less account's "Log In"): then
        // it fills with accentA — the scheme's Selection background, the one
        // role highlightedTextColor is contrast-gated against in every MoOS
        // palette. Unarmed it is glass with the accent on its edge, so an empty
        // field does not shout a button nobody can use yet. accentB lives in the
        // rim only.
        // Inside the capsule the key is an inset portal: the full 44 px stays
        // its hit area, the drawn key stands a few pixels in from the capsule's
        // rim, concentric with it. Beside a field it sits in the field's plate;
        // alone (a password-less "Log In") it is its own rounded key.
        Item {
            id: key
            required property T.AbstractButton control
            property T.TextField partner: null
            readonly property bool armed: !key.partner || !key.partner.visible
                                          || key.partner.length > 0
            readonly property bool nested: key.partner !== null && key.partner.visible
            readonly property real inset: key.nested
                ? Math.max(3, Math.round(4 * root.sessionScale)) : 0

            implicitWidth: Math.round(root.design.targetControl * root.sessionScale)
            implicitHeight: Math.round(root.design.targetControl * root.sessionScale)

            Rectangle {
                id: keyPlate
                anchors.fill: parent
                anchors.margins: key.inset
                // Concentric with the capsule: the family radius less the inset.
                radius: Math.round((root.design.radiusControl + 2) * root.sessionScale) - key.inset
                readonly property real shortCorner: Math.max(2, Math.round(radius * 0.32))
                topLeftRadius: keyPlate.LayoutMirroring.enabled ? shortCorner : radius
                topRightRadius: keyPlate.LayoutMirroring.enabled ? radius : shortCorner
                color: key.armed ? root.accentA
                                 : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                           Kirigami.Theme.textColor.b, root.design.surfaceRestingOpacity)
                opacity: key.control.enabled ? 1 : root.design.disabledOpacity
                scale: key.control.down ? root.design.pressScale : 1.0
                border.width: key.control.visualFocus ? root.design.focusWidth
                                                      : (key.nested ? 0 : root.design.borderHairline)
                border.color: Qt.rgba(root.accentB.r, root.accentB.g, root.accentB.b,
                                      (key.control.visualFocus || key.control.hovered) ? 0.95 : 0.50)
                Behavior on scale { NumberAnimation {
                    duration: root.design.duration(root.motionEnabled, root.design.motionFast)
                    easing.type: root.design.easeStandard
                } }
                Behavior on color { ColorAnimation {
                    duration: root.design.duration(root.motionEnabled, root.design.motionGeometry)
                } }

                // Hover and press read as light on the key, never as a second hue.
                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    color: key.armed ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                    opacity: key.control.down ? 0.16 : (key.control.hovered ? 0.08 : 0)
                }
            }
        }
    }

    Component {
        id: keyGlyph

        Item {
            id: glyph
            required property T.AbstractButton control
            // The key's face: the glyph wears the ink that is paired with its fill.
            property Item face: null
            readonly property bool armed: !glyph.face || glyph.face.armed
            readonly property color ink: glyph.armed ? Kirigami.Theme.highlightedTextColor
                                                     : Kirigami.Theme.textColor
            readonly property bool labelled: glyph.control.text !== ""

            implicitWidth: glyph.labelled
                ? keyLabel.implicitWidth + root.unit * 2
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
                opacity: glyph.armed ? 1 : root.design.mutedOpacity
                transform: [
                    Scale {
                        origin.x: root.design.iconControl / 2
                        origin.y: root.design.iconControl / 2
                        xScale: (glyph.backward ? -1 : 1) * root.sessionScale
                        yScale: root.sessionScale
                    },
                    // Armed, the arrow leans a step towards where it goes.
                    Translate {
                        x: glyph.armed ? (glyph.backward ? -1 : 1) * root.unit * 0.08 : 0
                        Behavior on x { NumberAnimation {
                            duration: root.design.duration(root.motionEnabled, root.design.motionGeometry)
                            easing.type: root.design.easeSpring
                        } }
                    }
                ]
                ShapePath {
                    strokeWidth: 2
                    strokeColor: glyph.ink
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
                width: Math.round(root.design.iconControl * root.sessionScale)
                height: width
                source: glyph.control.icon.name
                isMask: true
                color: glyph.ink
            }
            PlasmaComponents3.Label {
                id: keyLabel
                anchors.centerIn: parent
                visible: glyph.labelled
                text: glyph.control.Kirigami.MnemonicData.richTextLabel
                textFormat: Text.StyledText
                color: glyph.ink
                font.family: root.design.interfaceFamily
                font.weight: Font.DemiBold
                font.pointSize: Math.max(8, Math.round(
                    (Kirigami.Theme.defaultFont.pointSize + 1) * root.sessionScale))
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
        objectName: "moosAuthenticationCard"
        Kirigami.Theme.inherit: false
        Kirigami.Theme.colorSet: Kirigami.Theme.Window

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
        y: Math.round(topEdge + (1 - root.settle(root.slice(0, 0.7))) * root.unit * 1.4)
        width: root.islandWidth
        height: Math.round(bottomEdge - topEdge)
        scale: 0.94 + 0.06 * root.spring(root.slice(0, 0.8))
        opacity: root.settledOpacity
        radius: Math.round(root.design.radiusDialog * Math.max(0.8, root.sessionScale))
        // The Tidal Cut (MoUI.TidalShape): the island is the same silhouette as
        // every MoOS window action, at the size of the sheet — three corners
        // round, the top-trailing one cut at 45°, lit along the top and the cut.
        cut: radius
        sheen: 0.07
        depth: root.design.glassLevelDialog
        surfaceColor: Kirigami.Theme.backgroundColor
        // Glass, not a slab: behind the island both greeters have already
        // blurred and dimmed the scene (WallpaperFader), so a 0.80 sheet lets
        // that light through while text keeps its contrast. The software
        // renderer has no blur behind it and keeps the near-opaque 0.94 sheet.
        fillOpacity: root.softwareRendering ? 0.94 : 0.80
        inkColor: Kirigami.Theme.textColor
        accentColor: root.accentA
        border.color: Qt.rgba(Kirigami.Theme.textColor.r,
                              Kirigami.Theme.textColor.g,
                              Kirigami.Theme.textColor.b, 0.16)

        // The crest: the two-tone mark every MoOS session surface carries on
        // its top edge.
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: -height / 2
            width: root.unit * 4
            height: Math.max(3, Math.round(3 * root.sessionScale))
            radius: height / 2
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: root.accentA }
                GradientStop { position: 1; color: root.accentB }
            }
        }

        // The orbit's light: a conical sweep of the accent's two tones with a
        // bright head and a long tail, cut to the plate's own rim. Two stock
        // effects over two textures the size of the island; it repaints only
        // while it turns, and is not drawn at all once it has docked.
        Item {
            id: rimMask
            anchors.fill: parent
            visible: false
            layer.enabled: root.orbitGlow > 0
            MoUI.TidalShape {
                anchors.fill: parent
                radius: island.radius
                cut: island.cut
                strokeColor: "black"
                strokeWidth: Math.max(2, Math.round(2 * root.sessionScale))
            }
        }
        Effects.ConicalGradient {
            id: rimPaint
            anchors.fill: parent
            visible: false
            angle: root.orbitAngle
            gradient: Gradient {
                GradientStop { position: 0.00; color: Qt.alpha(root.accentA, 0.0) }
                GradientStop { position: 0.70; color: Qt.alpha(root.accentA, 0.0) }
                GradientStop { position: 0.90; color: Qt.alpha(root.accentB, 0.85) }
                GradientStop { position: 0.985; color: root.accentA }
                GradientStop { position: 1.00; color: Qt.alpha(root.accentA, 0.0) }
            }
        }
        Effects.OpacityMask {
            anchors.fill: parent
            source: rimPaint
            maskSource: rimMask
            visible: root.orbitGlow > 0 && !root.softwareRendering
            opacity: root.orbitGlow
        }

        // A refusal: the rim answers once in the negative role, with the notice.
        MoUI.TidalShape {
            id: refusalRim
            anchors.fill: parent
            radius: island.radius
            cut: island.cut
            strokeWidth: Math.max(2, Math.round(2 * root.sessionScale))
            strokeColor: Kirigami.Theme.negativeTextColor
            opacity: 0
            visible: opacity > 0
            SequentialAnimation {
                id: refusalFlash
                NumberAnimation {
                    target: refusalRim; property: "opacity"; from: 0; to: 0.9
                    duration: root.design.duration(root.motionEnabled, root.design.motionFast)
                }
                NumberAnimation {
                    target: refusalRim; property: "opacity"; to: 0
                    duration: root.design.duration(root.motionEnabled, root.design.motionPortal)
                    easing.type: root.design.easeStandard
                }
            }
        }
    }
    onNoticeIsAlertChanged: if (noticeIsAlert && motionEnabled) { refusalFlash.restart(); }

    // Light behind the plate: one still pool of the accent, so the island reads
    // as lit from within the scene rather than laid on it.
    Effects.RadialGradient {
        z: -2
        anchors.centerIn: island
        width: island.width * 2.6
        height: island.height * 2.0
        horizontalRadius: width / 2
        verticalRadius: height / 2
        visible: !root.softwareRendering
        opacity: root.settle(root.slice(0, 1)) * root.settledOpacity
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.alpha(root.accentA, 0.20) }
            GradientStop { position: 0.45; color: Qt.alpha(root.accentB, 0.07) }
            GradientStop { position: 0.72; color: "transparent" }
            GradientStop { position: 1.0; color: "transparent" }
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
        width: makersRow.implicitWidth + root.unit
        height: Math.round(root.unit * 1.2)
        radius: height / 2
        opacity: root.slice(0.5, 1) * root.settledOpacity
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

    // GlassSurface owns depth. Extra expanded rectangles painted three hard
    // rings around the login/lock card, unlike the shared power surface.

    // FIXME: move this component into a layout, rather than abusing
    // anchors and implicitly relying on other components' built-in
    // whitespace to avoid items being overlapped.
    UserList {
        id: userListView
        // Observe the native selection; authentication and selected account
        // remain entirely owned by the caller. Ordinary lock clients do not
        // activate the separate login account's appearance reader.
        onSelectedUserChanged: MoUI.SessionAppearance.followUser(selectedUser)
        Component.onCompleted: MoUI.SessionAppearance.followUser(selectedUser)
        Kirigami.Theme.inherit: false
        Kirigami.Theme.colorSet: Kirigami.Theme.Window
        visible: root.showUserList && y > 0
        anchors {
            bottom: parent.verticalCenter
            left: parent.left
            right: parent.right
        }
        fontSize: root.fontSize
        // bubble up the signal
        onUserSelected: root.userSelected()
        transform: Translate {
            y: (1 - root.settle(root.slice(0.08, 0.8))) * root.unit * 1.2
        }
    }

    // The prompts, then the action buttons. Upstream stretched the prompt
    // block to ten grid units to push the actions down; the island hugs the
    // prompts instead, and one fixed gap keeps the actions clear of its edge.
    ColumnLayout {
        id: prompts
        objectName: "moosSessionPrompts"
        Kirigami.Theme.inherit: false
        Kirigami.Theme.colorSet: Kirigami.Theme.Window
        anchors.top: parent.verticalCenter
        anchors.topMargin: Kirigami.Units.largeSpacing + root.neighbourRoom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        spacing: Kirigami.Units.smallSpacing
        // Interactive targets are never staged: they are opaque the moment the
        // selected appearance is known (see appearanceSettled).
        opacity: root.settledOpacity

        // The notice line. The slot always keeps one line's height, which is
        // what stops the cluster jumping when a message arrives; the pill
        // inside it is only there while there is something to say.
        Item {
            id: noticeSlot
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            Layout.maximumWidth: root.unit * 16
            implicitHeight: Math.max(noticePill.implicitHeight, greetingLabel.implicitHeight,
                                     noticeMetrics.height + Kirigami.Units.largeSpacing)
                            + Kirigami.Units.smallSpacing * 2

            FontMetrics {
                id: noticeMetrics
                font: noticeText.font
            }

            // The greeting: the line is empty until somebody arrives, so the
            // island says hello in the session's language — by the time of day
            // read when it arrives, never on a timer. A notice (Caps Lock, PAM,
            // a refusal) takes the same line and the greeting steps aside.
            PlasmaComponents3.Label {
                id: greetingLabel
                objectName: "moosSessionGreeting"
                anchors.centerIn: parent
                width: Math.min(implicitWidth, root.unit * 15)
                text: root.greeting
                textFormat: Text.PlainText
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                font.family: root.design.interfaceFamily
                font.pointSize: Math.max(8, Math.round((Kirigami.Theme.defaultFont.pointSize + 1)
                                                       * root.sessionScale))
                font.weight: Font.Medium
                color: Kirigami.Theme.textColor
                opacity: root.design.mutedOpacity
                visible: notificationsLabel.text.length === 0 && text.length > 0
                Accessible.ignored: true
            }

            Rectangle {
                id: noticePill
                anchors.centerIn: parent

                // The pill takes its size from the label and the label caps its
                // OWN width: a wrapping Text whose width comes from its parent
                // while the parent's implicit width comes from the Text is the
                // classic binding loop.
                implicitWidth: noticeText.width + root.unit * 1.6
                implicitHeight: noticeText.implicitHeight + Kirigami.Units.largeSpacing
                width: implicitWidth
                height: implicitHeight
                // A pill for one line, a rounded card when PAM says something
                // long enough to wrap. The message is never elided: here the
                // text IS the reason the machine refused.
                radius: Math.min(height / 2, root.unit * 1.2)
                visible: opacity > 0
                opacity: notificationsLabel.text !== "" ? 1 : 0
                transform: Translate {
                    y: (1 - noticePill.opacity) * root.unit * 0.4
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

                // Upstream's notice text, verbatim: the public alias writes
                // here and the refusal check reads it. It is not drawn.
                PlasmaComponents3.Label {
                    id: notificationsLabel
                    visible: false
                    font: noticeText.font
                    textFormat: Text.PlainText
                }
                // What the island SAYS: the same notice in the session's own
                // Arabic (MoUI.SessionText — exact known plasma_login/PAM
                // strings only; anything else is shown as it came).
                PlasmaComponents3.Label {
                    id: noticeText
                    objectName: "moosSessionNotice"
                    text: MoUI.SessionText.present(notificationsLabel.text, MoUI.SessionText.isArabic(Qt.locale().name))
                    anchors.centerIn: parent
                    width: Math.min(implicitWidth, root.unit * 14)
                    font.family: root.design.interfaceFamily
                    font.pointSize: Math.max(8, Math.round(Kirigami.Theme.defaultFont.pointSize
                                                           * root.sessionScale))
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
            Layout.maximumWidth: root.unit * 16
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
            Layout.minimumHeight: root.islandPad + root.unit * 0.8
            Layout.preferredHeight: root.islandPad + root.unit * 1.8
            Layout.maximumHeight: Layout.preferredHeight
            Layout.fillHeight: true
        }

        Item {
            id: actionDockSlot
            Layout.alignment: Qt.AlignHCenter
            // The session dock: one glass sheet in the island's silhouette holds
            // every session action, the way the MoOS bar holds the desktop's,
            // instead of a loose row of separate tiles. The actions and their
            // wrapping rule stay upstream's; only what is painted behind them
            // is MoOS's.
            readonly property real dockPad: Math.round(Kirigami.Units.smallSpacing * 1.5 * root.sessionScale)
            readonly property bool docked: actionItemsLayout.visible
                && actionItemsLayout.visibleChildren.length > 0
            implicitHeight: actionItemsLayout.implicitHeight + (docked ? dockPad * 2 : 0)
            implicitWidth: actionItemsLayout.implicitWidth + (docked ? dockPad * 2 : 0)
            MoUI.TidalShape {
                id: actionDock
                objectName: "moosSessionActionDock"
                anchors.fill: parent
                visible: actionDockSlot.docked
                Kirigami.Theme.inherit: false
                Kirigami.Theme.colorSet: Kirigami.Theme.Window
                radius: Math.round(root.design.radiusPanel * Math.max(0.8, root.sessionScale))
                cut: radius
                fillColor: Qt.alpha(Kirigami.Theme.backgroundColor, 0.58)
                sheen: 0.06
                strokeColor: Qt.alpha(Kirigami.Theme.textColor, 0.14)
                strokeWidth: root.design.borderHairline
                specularColor: root.design.glassSpecular(Kirigami.Theme.backgroundColor,
                                                         root.design.glassLevelPanel)
            }
            GridLayout {
                id: actionItemsLayout
                // MoOS ActionButtons read this: inside the dock they are
                // transparent at rest.
                property bool moosDock: true
                // The actions stand on the scene, outside the island. The
                // Window set is the selected look's own pair — light ink in
                // every dark family, dark ink in every light one. Complementary
                // is dark in ALL eighteen MoOS schemes, which left white
                // captions on the light families' bright scenes.
                Kirigami.Theme.inherit: false
                Kirigami.Theme.colorSet: Kirigami.Theme.Window
                anchors.centerIn: parent

                // Docked keys sit as close as the MoOS bar's.
                readonly property int spacing: moosDock ? Kirigami.Units.smallSpacing : Kirigami.Units.largeSpacing
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
