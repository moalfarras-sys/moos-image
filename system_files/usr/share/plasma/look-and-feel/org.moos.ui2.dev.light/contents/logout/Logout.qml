/*
    SPDX-FileCopyrightText: 2014 Aleix Pol Gonzalez <aleixpol@blue-systems.com>
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    The host contract (signals, ShutdownType, spdMethods, maysd, canLogout,
    softwareUpdatePending, remainingTime) is KDE Plasma 6.7's org.kde.breeze
    Logout.qml — untouched, so every action stays wired to the system.

    The design is the MoOS session family's, and it is the same scene the lock
    and login screens draw: the theme's wallpaper under the session veil, the
    MoOS signature in the leading corner, the session clock top-centre, and ONE
    glass island in the middle that carries who is signed in, the question, the
    countdown ring and a dock of large action tiles. The clock and the face are
    not look-alikes of the lock screen's — they are the same two components
    (org.kde.breeze.components Clock and UserDelegate, both MoOS's files), so
    the three doors cannot drift apart. Shut Down / Restart are gated behind a
    confirm tap (armOrFire); the signal each tile emits stays byte-identical to
    the stock contract.
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Shapes
import Qt5Compat.GraphicalEffects

import org.kde.breeze.components as SessionComponents
import org.kde.coreaddons as KCoreAddons
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.sessions
import org.moos.ui as MoUI

Item {
    id: root

    width: screenGeometry.width
    height: screenGeometry.height
    focus: true

    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.Complementary

    LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    signal logoutRequested()
    signal haltRequested()
    signal haltUpdateRequested()
    signal suspendRequested(int spdMethod)
    signal rebootRequested()
    signal rebootRequested2(int opt)
    signal rebootUpdateRequested()
    signal cancelRequested()
    signal lockScreenRequested()
    signal cancelSoftwareUpdateRequested()

    readonly property bool showAllOptions: sdtype === ShutdownType.ShutdownTypeDefault
    property int remainingTime: 30

    // ═══════════════════ MoOS Session Design Tokens ═══════════════════════
    // ONE canonical set for every session surface (lock, power, login scene).
    // The lock and login screens draw theirs in the breeze components
    // (SessionManagementScreen, WallpaperFader, ActionButton); the clock and
    // the face are not mirrored at all — this screen instantiates the same
    // two components. Change a token here → change it there to match.
    //   accentA = Kirigami.Theme.highlightColor       · live theme accent
    //   accentB = accentA HSL hue +0.09               · two-tone signature
    //   ink     = Kirigami.Theme.textColor            · neutral glyph / text
    //   island  = bg 0.58 fill · sheen ink 0.06→0 · border ink 0.16
    //             accent crest gradient · radius radiusDialog · depth halo
    //             (the same plate SessionManagementScreen draws for lock/login)
    //   tile    = gridUnit*8.6 × 6.2 · icon 0.30 of height · radius gu*1.4
    //             idle fill ink 0.09 · lit fill ink 0.16 · crest cut + horizon
    //   ring    = countdown: Shape arc, stroke 3, accentA on accentA 0.18
    //   scrim   = backgroundColor  0.52 / 0.30 / 0.60  (top / mid / foot)
    //   blur    = 54 wallpaper (lock's breeze WallpaperFader = 50)
    //   fonts   = IBM Plex Sans Arabic across both scripts and all numerals
    //   clock   = org.kde.breeze.components Clock — the one session clock
    //   face    = org.kde.breeze.components UserDelegate — the one session face
    //   motion  = Units.shortDuration (hover/press) · longDuration (fades) · OutCubic
    // ══════════════════════════════════════════════════════════════════════
    readonly property color accent: Kirigami.Theme.highlightColor
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property var design: MoUI.Tokens
    // accentB — the two-tone partner (accentA hue-rotated +0.09 in HSL), same
    // derivation as the portal rim. The horizon rides accentA/accentB so its
    // hue is 100% theme-derived — no hardcoded base colour anywhere.
    //
    // The shared TidalHorizon component consumes both roles directly.
    readonly property color accentB: {
        const c = Kirigami.Theme.highlightColor;
        if (c.hslSaturation < 0.08 || c.hslHue < 0) { return Qt.lighter(c, 1.28); }
        let nh = c.hslHue + 0.09; if (nh > 1) { nh -= 1; }
        return Qt.hsla(nh, Math.min(1, c.hslSaturation), Math.min(0.72, c.hslLightness * 1.08), 1);
    }

    function stopCountdown() { countdownTimer.stop(); }

    function currentAction() {
        switch (sdtype) {
        case ShutdownType.ShutdownTypeReboot:
            if (softwareUpdatePending) { rebootUpdateRequested(); } else { rebootRequested(); }
            break;
        case ShutdownType.ShutdownTypeHalt:
            if (softwareUpdatePending) { haltUpdateRequested(); } else { haltRequested(); }
            break;
        default:
            logoutRequested();
        }
    }

    function visibleDockActions() {
        const candidates = [suspendButton, hibernateButton, rebootButton,
            rebootWithoutUpdatesButton, shutdownButton, shutdownWithoutUpdatesButton,
            logoutButton, lockButton];
        const result = [];
        for (let i = 0; i < candidates.length; ++i) {
            if (candidates[i].visible && candidates[i].enabled) { result.push(candidates[i]); }
        }
        return result;
    }

    function visibleActions() {
        const result = visibleDockActions();
        if (cancelButton.visible && cancelButton.enabled) { result.push(cancelButton); }
        return result;
    }

    function moveFocus(button, horizontalStep, verticalStep) {
        const actions = visibleDockActions();
        if (actions.length === 0) { return; }
        if (button === cancelButton) {
            const edge = verticalStep < 0 || horizontalStep < 0
                ? actions.length - 1 : 0;
            actions[edge].forceActiveFocus(Qt.TabFocusReason);
            return;
        }
        const idx = Math.max(0, actions.indexOf(button));
        if (verticalStep !== 0) {
            const next = idx + verticalStep * dock.columns;
            if (next < 0 || next >= actions.length) {
                cancelButton.forceActiveFocus(Qt.TabFocusReason);
            } else {
                actions[next].forceActiveFocus(Qt.TabFocusReason);
            }
            return;
        }
        let logicalStep = horizontalStep;
        if (Qt.application.layoutDirection === Qt.RightToLeft) { logicalStep *= -1; }
        const next = (idx + logicalStep + actions.length) % actions.length;
        actions[next].forceActiveFocus(Qt.TabFocusReason);
    }

    function focusInitialAction() {
        if (sdtype === ShutdownType.ShutdownTypeReboot && rebootButton.visible) {
            rebootButton.forceActiveFocus(Qt.OtherFocusReason);
        } else if (sdtype === ShutdownType.ShutdownTypeHalt && shutdownButton.visible) {
            shutdownButton.forceActiveFocus(Qt.OtherFocusReason);
        } else if (sdtype === ShutdownType.ShutdownTypeNone && logoutButton.visible) {
            logoutButton.forceActiveFocus(Qt.OtherFocusReason);
        } else {
            cancelButton.forceActiveFocus(Qt.OtherFocusReason);
        }
    }

    // ── Confirm-on-sensitive ────────────────────────────────────────────────
    // Shut Down / Restart are gated behind a second tap: the first tap ARMS the
    // tile (it fills + the island's hint line explains), the second FIRES the
    // real system signal. Everything else (Sleep, Log Out, Lock) fires
    // immediately. This only gates the click — the signal each tile emits is
    // byte-identical to the stock contract, so the system path is untouched.
    property var armedButton: null
    Timer { id: armTimer; interval: 4000; onTriggered: root.disarm() }
    function disarm() {
        if (root.armedButton) { root.armedButton.armed = false; root.armedButton = null; }
        armTimer.stop();
    }
    function armOrFire(btn, fire) {
        root.stopCountdown();
        if (root.armedButton === btn) { root.disarm(); fire(); return; }
        root.disarm();
        btn.armed = true;
        root.armedButton = btn;
        armTimer.restart();
    }
    // Any immediate action or a cancel clears a pending arm first.
    function fireNow(fire) { root.disarm(); root.stopCountdown(); fire(); }

    function headingText() {
        switch (sdtype) {
        case ShutdownType.ShutdownTypeReboot: return bilingual("إعادة تشغيل MoOS", "Restart MoOS");
        case ShutdownType.ShutdownTypeHalt: return bilingual("إيقاف MoOS", "Shut down MoOS");
        case ShutdownType.ShutdownTypeNone: return bilingual("تسجيل الخروج", "Log out");
        default: return bilingual("ماذا تريد أن تفعل؟", "What would you like to do?");
        }
    }

    // Session surfaces speak the session language. Keep the shared helper name
    // because headings, warnings and Accessible descriptions all use it, but
    // return one isolated phrase instead of drawing Arabic and English together.
    // The isolation marks still protect punctuation and counts in RTL.
    function bilingual(arabic, english) {
        if (Qt.application.layoutDirection === Qt.RightToLeft) {
            return "\u2067" + arabic + "\u2069";
        }
        return "\u2066" + english + "\u2069";
    }

    // Tile captions follow the same single-language rule without isolation
    // characters so compact label measurement remains predictable.
    function shortLabel(arabic, english) {
        return Qt.application.layoutDirection === Qt.RightToLeft ? arabic : english;
    }

    KCoreAddons.KUser { id: currentUser }
    SessionsModel { id: otherSessionsModel; includeUnusedSessions: false; includeOwnSession: false }
    QQC2.Action { shortcut: "Escape"; onTriggered: root.cancelRequested() }

    Timer {
        id: countdownTimer
        interval: 1000; repeat: true; running: !root.showAllOptions
        onTriggered: {
            root.remainingTime -= 1;
            if (root.remainingTime <= 0) { stop(); root.currentAction(); }
        }
    }

    Component.onCompleted: Qt.callLater(root.focusInitialAction)

    // ── Scene: the active theme's OWN wallpaper, blurred ─────────────────────
    // Every look-and-feel package ships its theme's wallpaper as
    // previews/fullscreenpreview.jpg; a package-relative path resolves to the
    // right one for each of the 16 themes, so the doorway is NEVER a flat colour
    // — it is the same background the desktop wears, softened by a real blur.
    // The QML stays byte-identical across packages; only the image differs.
    Image {
        id: wallpaper
        anchors.fill: parent
        source: Qt.resolvedUrl("../previews/fullscreenpreview.jpg")
        fillMode: Image.PreserveAspectCrop
        cache: true
        asynchronous: true
        opacity: 0
        layer.enabled: true
        // MoOS token: the same wallpaper blur the lock uses (breeze WallpaperFader
        // is 50) — so the frosted background reads identically on both screens.
        layer.effect: FastBlur { radius: 54 }
        Component.onCompleted: {
            if (root.motionEnabled) {
                backdropFade.start();
            } else {
                wallpaper.opacity = 1;
            }
        }
        OpacityAnimator { id: backdropFade; target: wallpaper; from: 0; to: 1.0
            duration: root.design.motionPortal; easing.type: root.design.easeStandard }
    }
    // Legibility scrim — the theme's own canvas, heavier at the top and foot so
    // the island stays readable over any wallpaper. Calculated transparency,
    // never an opaque wash.
    Rectangle {
        anchors.fill: parent
        opacity: wallpaper.opacity
        // MoOS token — the ONE session scrim (0.52 / 0.30 / 0.60), shared by the
        // lock and the login scene so every surface veils the wallpaper equally.
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.52) }
            GradientStop { position: 0.45; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.30) }
            GradientStop { position: 1.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.60) }
        }
    }

    // The scene ABSORBS clicks; it does not cancel on one. Dismissing the
    // doorway is exactly two gestures, both deliberate: the Cancel key and
    // Escape — a stray click on the wallpaper or in a gap must never silently
    // cancel (or worse, race) a pending shutdown.
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons }

    // ── The session frame: signature and clock ───────────────────────────────
    // The same two marks, in the same two places, as the lock and login
    // screens. The signature keeps its leading corner; the clock shares the
    // vertical axis with the island and stands above it.
    MoUI.SessionSignature {
        id: signature
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.leftMargin: Math.max(Kirigami.Units.gridUnit * 2,
                                     Math.round(root.width * 0.028))
        anchors.topMargin: Math.max(Kirigami.Units.gridUnit * 1.6,
                                    Math.round(root.height * 0.04))
        sceneHeight: root.height
        ink: Kirigami.Theme.textColor
        accent: root.accent
        opacity: wallpaper.opacity
        // In a 640x480 mode the island reaches the corner; the island wins.
        visible: sheet.y > y + height + Kirigami.Units.smallSpacing
                 || x + width + Kirigami.Units.largeSpacing < sheet.x
                 || x > sheet.x + sheet.width + Kirigami.Units.largeSpacing
    }

    // The clock and the island are centred as ONE group. A dock of two tile
    // rows on a short screen leaves no band for the clock; it steps aside
    // whole rather than squeeze against the island, exactly as both greeters
    // hide a clock that does not fit.
    readonly property real stageMargin: Kirigami.Units.gridUnit * 2
    readonly property real clockGap: Kirigami.Units.gridUnit * 2.5
    readonly property bool clockFits: sessionClock.implicitHeight + clockGap + sheet.height
                                      + stageMargin * 2 <= root.height
    readonly property real groupHeight: sheet.height
                                        + (clockFits ? sessionClock.implicitHeight + clockGap : 0)
    readonly property real groupTop: Math.round((root.height - groupHeight) / 2)

    SessionComponents.Clock {
        id: sessionClock
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.groupTop
        visible: root.clockFits
        opacity: wallpaper.opacity
    }

    // ── The Glass Island ─────────────────────────────────────────────────────
    // One substantial layered-material card carries the whole doorway: header
    // (emblem · clock · date), the question, the signed-in identity, the
    // countdown ring, the action dock and the way out. Material is painted
    // from scheme roles only — fill, sheen, border, rim — so all 16 palettes
    // wear it natively, and there is no offscreen effect layer behind it.
    Item {
        id: sheet
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.groupTop + (root.clockFits ? sessionClock.implicitHeight + root.clockGap : 0)
        width: Math.min(root.width - Kirigami.Units.gridUnit * 3,
                        Math.max(Kirigami.Units.gridUnit * 26,
                                 column.implicitWidth + Kirigami.Units.gridUnit * 4))
        height: Math.min(root.height - Kirigami.Units.gridUnit * 3,
                         column.implicitHeight + Kirigami.Units.gridUnit * 3.6)

        opacity: root.motionEnabled ? 0 : 1
        scale: root.motionEnabled ? 0.965 : 1
        transformOrigin: Item.Center
        transform: Translate { id: sheetRise; y: Kirigami.Units.gridUnit * 2 }
        Component.onCompleted: {
            if (root.motionEnabled) {
                sheetEnter.start();
            } else {
                sheetRise.y = 0;
                sheet.scale = 1;
            }
        }
        ParallelAnimation {
            id: sheetEnter
            NumberAnimation { target: sheet; property: "opacity"; from: 0; to: 1
                duration: root.design.motionPortal; easing.type: root.design.easeStandard }
            NumberAnimation { target: sheetRise; property: "y"; from: Kirigami.Units.gridUnit * 2; to: 0
                duration: root.design.motionPortal; easing.type: root.design.easeStandard }
            NumberAnimation { target: sheet; property: "scale"; from: 0.965; to: 1
                duration: root.design.motionPortal; easing.type: root.design.easeEmphasis }
        }

        // Depth halo — a still, cheap stand-in for a drop shadow: two nested
        // translucent plates grow past the card so it visibly floats off the
        // scene. No offscreen layer, no effect, nothing animates.
        Rectangle {
            anchors.fill: island
            anchors.margins: -Kirigami.Units.gridUnit * 1.1
            radius: island.radius + Kirigami.Units.gridUnit * 1.1
            color: Qt.rgba(0, 0, 0, 0.04)
        }
        Rectangle {
            anchors.fill: island
            anchors.margins: -Kirigami.Units.gridUnit * 0.7
            radius: island.radius + Kirigami.Units.gridUnit * 0.7
            color: Qt.rgba(0, 0, 0, 0.06)
        }
        Rectangle {
            anchors.fill: island
            anchors.margins: -Kirigami.Units.gridUnit * 0.35
            radius: island.radius + Kirigami.Units.gridUnit * 0.35
            color: Qt.rgba(0, 0, 0, 0.08)
        }

        Rectangle {
            id: island
            anchors.fill: parent
            radius: root.design.radiusDialog
            color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                           Kirigami.Theme.backgroundColor.g,
                           Kirigami.Theme.backgroundColor.b, 0.58)
            border.width: root.design.borderHairline
            border.color: Qt.rgba(Kirigami.Theme.textColor.r,
                                  Kirigami.Theme.textColor.g,
                                  Kirigami.Theme.textColor.b, 0.16)

            // Sheen — the glass catch-light across the island's upper field.
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

            // The crest — the two-tone mark every MoOS session island carries
            // on its top edge, the same width as the one on the lock and login.
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: -height / 2
                width: Kirigami.Units.gridUnit * 4
                height: 3
                radius: height / 2
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: root.accent }
                    GradientStop { position: 1; color: root.accentB }
                }
            }
        }

        ColumnLayout {
            id: column
            anchors.centerIn: parent
            width: sheet.width - Kirigami.Units.gridUnit * 4
            spacing: Kirigami.Units.largeSpacing

            // ── Who is signed in — the session face, the one the lock shows ──
            SessionComponents.UserDelegate {
                id: identity
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Kirigami.Units.smallSpacing
                Layout.preferredWidth: Math.min(column.width, Kirigami.Units.gridUnit * 16)
                Layout.preferredHeight: faceInset + faceSize + nameLine.height
                                        + Kirigami.Units.gridUnit * 0.9
                faceSize: Kirigami.Units.gridUnit * 4
                // The delegate draws the name four points above `fontSize`,
                // which here lands on the secondary size: the question below
                // is this island's headline, not the name.
                fontSize: Kirigami.Theme.defaultFont.pointSize - 2
                name: currentUser.fullName.length > 0 ? currentUser.fullName
                                                      : currentUser.loginName
                userName: currentUser.loginName
                avatarPath: currentUser.faceIconUrl
                iconSource: "user-identity"
                constrainText: false
                isCurrent: true
                // A portrait, not a control: this screen's keys are the tiles,
                // and it is never a focus stop (nothing gives it focus).
                Accessible.ignored: true

                FontMetrics {
                    id: nameLine
                    font.family: root.design.interfaceFamily
                    font.pointSize: identity.fontSize + 4
                }
            }

            // ── The question — display weight ──
            QQC2.Label {
                Layout.alignment: Qt.AlignHCenter
                Layout.maximumWidth: Kirigami.Units.gridUnit * 36
                horizontalAlignment: Text.AlignHCenter
                text: root.headingText()
                // The question is the point of this screen: foreground role at
                // display size.
                color: Kirigami.Theme.textColor
                elide: Text.ElideRight
                font.family: root.design.interfaceFamily
                font.weight: Font.DemiBold
                font.pointSize: Kirigami.Theme.defaultFont.pointSize + 7
            }

            // ── Countdown ring (only while an action is pending) ──
            // The naked hairline is retired: remaining time is now a still arc
            // that empties clockwise around the seconds numeral. One Shape,
            // stroke-only, painted from accentA over its own 0.18 track — no
            // effect layer, and the per-second sweep is a gated Behavior.
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                visible: countdownTimer.running
                spacing: Kirigami.Units.largeSpacing

                Item {
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 3.2
                    Layout.preferredHeight: Kirigami.Units.gridUnit * 3.2

                    Shape {
                        anchors.fill: parent
                        preferredRendererType: Shape.CurveRenderer
                        ShapePath {
                            strokeWidth: 3
                            strokeColor: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.18)
                            fillColor: "transparent"
                            capStyle: ShapePath.RoundCap
                            PathAngleArc {
                                centerX: Kirigami.Units.gridUnit * 1.6
                                centerY: Kirigami.Units.gridUnit * 1.6
                                radiusX: Kirigami.Units.gridUnit * 1.45
                                radiusY: Kirigami.Units.gridUnit * 1.45
                                startAngle: -90
                                sweepAngle: 360
                            }
                        }
                        ShapePath {
                            strokeWidth: 3
                            strokeColor: root.accent
                            fillColor: "transparent"
                            capStyle: ShapePath.RoundCap
                            PathAngleArc {
                                id: countdownArc
                                centerX: Kirigami.Units.gridUnit * 1.6
                                centerY: Kirigami.Units.gridUnit * 1.6
                                radiusX: Kirigami.Units.gridUnit * 1.45
                                radiusY: Kirigami.Units.gridUnit * 1.45
                                startAngle: -90
                                sweepAngle: 360 * Math.max(0, Math.min(1, root.remainingTime / 30))
                                // 0 when animations are off: this Behavior re-fires every
                                // second of the countdown, so an ungated sweep here would
                                // animate continuously through the whole 30s even with
                                // AnimationDurationFactor=0.
                                Behavior on sweepAngle { NumberAnimation {
                                    duration: root.motionEnabled
                                              ? root.design.motionPortal * 2 : 0
                                    easing.type: Easing.Linear } }
                            }
                        }
                    }
                    QQC2.Label {
                        anchors.centerIn: parent
                        text: root.remainingTime
                        color: Kirigami.Theme.textColor
                        font.family: root.design.interfaceFamily; font.weight: Font.DemiBold
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize + 3
                    }
                }
                QQC2.Label {
                    Layout.maximumWidth: Kirigami.Units.gridUnit * 18
                    text: root.bilingual("سيُنفَّذ الإجراء تلقائيًا", "The action will run automatically")
                    wrapMode: Text.WordWrap
                    color: Kirigami.Theme.textColor
                    opacity: root.design.mutedOpacity
                    font.family: root.design.interfaceFamily
                    font.pointSize: Kirigami.Theme.smallFont.pointSize + 1
                }
            }

            QQC2.Label {
                Layout.alignment: Qt.AlignHCenter
                Layout.maximumWidth: Kirigami.Units.gridUnit * 34
                horizontalAlignment: Text.AlignHCenter
                visible: otherSessionsModel.count > 0 && (sdtype !== ShutdownType.ShutdownTypeNone || root.showAllOptions)
                text: otherSessionsModel.count === 1
                    ? root.bilingual("يوجد مستخدم آخر مسجّل الدخول وقد يفقد عمله", "Another user is signed in and may lose work")
                    : root.bilingual("يوجد %1 مستخدمين آخرين مسجّلي الدخول".arg(otherSessionsModel.count), "%1 other users are signed in".arg(otherSessionsModel.count))
                color: Kirigami.Theme.neutralTextColor
                wrapMode: Text.WordWrap; font.family: root.design.interfaceFamily
                font.pointSize: Kirigami.Theme.smallFont.pointSize
            }
            QQC2.Label {
                Layout.alignment: Qt.AlignHCenter
                Layout.maximumWidth: Kirigami.Units.gridUnit * 34
                horizontalAlignment: Text.AlignHCenter
                visible: softwareUpdatePending
                text: root.bilingual("تحديثات النظام جاهزة للتثبيت", "System updates are ready to install")
                color: Kirigami.Theme.positiveTextColor
                wrapMode: Text.WordWrap; font.family: root.design.interfaceFamily
                font.weight: Font.DemiBold; font.pointSize: Kirigami.Theme.smallFont.pointSize
            }

            // ── The power dock: a responsive grid of large tiles ──
            // At most four tile columns; six to eight actions form balanced
            // 3+3 / 4+3 / 4+4 rows, and a narrow island lowers the cap further.
            GridLayout {
                id: dock
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Kirigami.Units.smallSpacing
                rowSpacing: Kirigami.Units.largeSpacing
                columnSpacing: Kirigami.Units.largeSpacing
                readonly property int actionCount: root.visibleDockActions().length
                readonly property int widthLimit: Math.max(1, Math.floor(
                    ((root.width - Kirigami.Units.gridUnit * 7) + columnSpacing)
                    / (Kirigami.Units.gridUnit * 8.6 + columnSpacing)))
                columns: Math.max(1, Math.min(4, widthLimit,
                    actionCount <= 4 ? actionCount : Math.ceil(actionCount / 2)))

                MoOSUI2ActionButton {
                    id: suspendButton
                    revealOrder: 0
                    iconName: "system-suspend-symbolic"
                    text: root.shortLabel("تعليق", "Sleep")
                    description: root.bilingual("إبقاء الجلسة", "Keep session")
                    visible: root.showAllOptions && spdMethods.SuspendState
                    onClicked: root.fireNow(() => root.suspendRequested(2))
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(suspendButton, horizontalStep, verticalStep)
                }
                MoOSUI2ActionButton {
                    id: hibernateButton
                    revealOrder: 1
                    iconName: "system-suspend-hibernate-symbolic"
                    text: root.shortLabel("إسبات", "Hibernate")
                    description: root.bilingual("حفظ الجلسة", "Save session")
                    visible: root.showAllOptions && spdMethods.HibernateState
                    onClicked: root.fireNow(() => root.suspendRequested(4))
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(hibernateButton, horizontalStep, verticalStep)
                }
                MoOSUI2ActionButton {
                    id: rebootButton
                    revealOrder: 2
                    iconName: softwareUpdatePending ? "system-reboot-update-symbolic" : "system-reboot-symbolic"
                    text: softwareUpdatePending ? root.shortLabel("تحديث وإعادة", "Update & Restart") : root.shortLabel("إعادة التشغيل", "Restart")
                    description: armed ? root.bilingual("اضغط مجددًا لإعادة التشغيل", "Tap again to restart")
                        : (softwareUpdatePending ? root.bilingual("تثبيت التحديثات أولًا", "Install updates first") : root.bilingual("بدء جلسة جديدة", "Start fresh"))
                    emphasized: sdtype === ShutdownType.ShutdownTypeReboot
                    visible: maysd && (sdtype === ShutdownType.ShutdownTypeReboot || root.showAllOptions)
                    onClicked: root.armOrFire(rebootButton, () => { if (softwareUpdatePending) { root.rebootUpdateRequested(); } else { root.rebootRequested(); } })
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(rebootButton, horizontalStep, verticalStep)
                }
                MoOSUI2ActionButton {
                    id: rebootWithoutUpdatesButton
                    revealOrder: 3
                    iconName: "system-reboot-symbolic"
                    text: root.shortLabel("إعادة الآن", "Restart now")
                    description: armed ? root.bilingual("اضغط مجددًا لإعادة التشغيل", "Tap again to restart") : root.bilingual("بدون تحديث", "Without updating")
                    visible: maysd && softwareUpdatePending && (sdtype === ShutdownType.ShutdownTypeReboot || root.showAllOptions)
                    onClicked: root.armOrFire(rebootWithoutUpdatesButton, () => root.rebootRequested())
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(rebootWithoutUpdatesButton, horizontalStep, verticalStep)
                }
                MoOSUI2ActionButton {
                    id: shutdownButton
                    revealOrder: 4
                    iconName: softwareUpdatePending ? "system-shutdown-update-symbolic" : "system-shutdown-symbolic"
                    text: softwareUpdatePending ? root.shortLabel("تحديث وإيقاف", "Update & Shut Down") : root.shortLabel("إيقاف التشغيل", "Shut Down")
                    description: armed ? root.bilingual("اضغط مجددًا للإيقاف", "Tap again to power off")
                        : (softwareUpdatePending ? root.bilingual("تثبيت التحديثات أولًا", "Install updates first") : root.bilingual("إيقاف الجهاز بأمان", "Power off safely"))
                    emphasized: sdtype === ShutdownType.ShutdownTypeHalt
                    destructive: true
                    visible: maysd && (sdtype === ShutdownType.ShutdownTypeHalt || root.showAllOptions)
                    onClicked: root.armOrFire(shutdownButton, () => { if (softwareUpdatePending) { root.haltUpdateRequested(); } else { root.haltRequested(); } })
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(shutdownButton, horizontalStep, verticalStep)
                }
                MoOSUI2ActionButton {
                    id: shutdownWithoutUpdatesButton
                    revealOrder: 5
                    iconName: "system-shutdown-symbolic"
                    text: root.shortLabel("إيقاف الآن", "Shut down now")
                    description: armed ? root.bilingual("اضغط مجددًا للإيقاف", "Tap again to power off") : root.bilingual("بدون تحديث", "Without updating")
                    destructive: true
                    visible: maysd && softwareUpdatePending && (sdtype === ShutdownType.ShutdownTypeHalt || root.showAllOptions)
                    onClicked: root.armOrFire(shutdownWithoutUpdatesButton, () => root.haltRequested())
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(shutdownWithoutUpdatesButton, horizontalStep, verticalStep)
                }
                MoOSUI2ActionButton {
                    id: logoutButton
                    revealOrder: 6
                    iconName: "system-log-out-symbolic"
                    text: root.shortLabel("تسجيل الخروج", "Log Out")
                    description: root.bilingual("إنهاء الجلسة", "End session")
                    visible: canLogout && (sdtype === ShutdownType.ShutdownTypeNone || root.showAllOptions)
                    onClicked: root.fireNow(() => root.logoutRequested())
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(logoutButton, horizontalStep, verticalStep)
                }
                MoOSUI2ActionButton {
                    id: lockButton
                    revealOrder: 7
                    iconName: "system-lock-screen-symbolic"
                    text: root.shortLabel("قفل الشاشة", "Lock Screen")
                    description: root.bilingual("العودة لاحقًا", "Return later")
                    visible: root.showAllOptions
                    onClicked: root.fireNow(() => root.lockScreenRequested())
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(lockButton, horizontalStep, verticalStep)
                }
            }

            // ── The hint line — one stable place for state guidance ──
            // Descriptions no longer pop in under individual tiles (which made
            // the dock jump); the island explains the armed confirm tap here,
            // in a reserved line that never reflows the layout.
            QQC2.Label {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredHeight: Kirigami.Units.gridUnit * 1.2
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                text: root.armedButton ? root.armedButton.description : ""
                color: root.armedButton ? root.armedButton.accentA : Kirigami.Theme.textColor
                opacity: root.armedButton ? 1.0 : 0
                font.family: root.design.interfaceFamily; font.weight: Font.DemiBold
                font.pointSize: Kirigami.Theme.smallFont.pointSize + 1
            }

            // ── The way out — a full-width quiet pill under its hairline ──
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                               Kirigami.Theme.textColor.b, 0.10)
            }
            MoOSUI2ActionButton {
                id: cancelButton
                revealOrder: 8
                iconName: "cancel-operation-symbolic"
                text: root.shortLabel("إلغاء — العودة إلى سطح المكتب", "Cancel — back to desktop")
                description: root.bilingual("العودة إلى سطح المكتب", "Back to desktop")
                subtle: true
                Layout.alignment: Qt.AlignHCenter
                Layout.bottomMargin: Kirigami.Units.smallSpacing
                onClicked: { root.disarm(); root.cancelRequested(); }
                onNavigate: (horizontalStep, verticalStep) => root.moveFocus(cancelButton, horizontalStep, verticalStep)
            }
        }
    }
}
