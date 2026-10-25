// Generated native control view; canonical design: org.moos.ui2/contents/logout/Logout.qml.
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
// Under a name as well: QtQuick.Shapes has gradients of the same names, and they are not Items.
import Qt5Compat.GraphicalEffects as Effects

import org.kde.breeze.components as SessionComponents
import org.kde.coreaddons as KCoreAddons
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.sessions
import org.moos.ui as MoUI

Item {
    id: root

    anchors.fill: parent
    required property Item sessionHost
    required property var cancelCountdown
    readonly property Item hostRoot: sessionHost
    readonly property string activeLook: MoUI.SessionAppearance.configuredLook()
    readonly property url sceneWallpaper: root.wallpaperSource
    objectName: "moosSessionPower"
    onHostRootChanged: {
        disarm();
        Qt.callLater(root.focusInitialAction);
    }
    focus: true
    readonly property url wallpaperSource: MoUI.SessionAppearance.configuredWallpaper()

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

    onLogoutRequested: root.sessionHost.logoutRequested()
    onHaltRequested: root.sessionHost.haltRequested()
    onHaltUpdateRequested: root.sessionHost.haltUpdateRequested()
    onRebootRequested: root.sessionHost.rebootRequested()
    onRebootUpdateRequested: root.sessionHost.rebootUpdateRequested()
    onCancelRequested: root.sessionHost.cancelRequested()
    onLockScreenRequested: root.sessionHost.lockScreenRequested()
    onCancelSoftwareUpdateRequested: root.sessionHost.cancelSoftwareUpdateRequested()
    onSuspendRequested: method => root.sessionHost.suspendRequested(method)
    onRebootRequested2: option => root.sessionHost.rebootRequested2(option)


    readonly property bool showAllOptions: sdtype === ShutdownType.ShutdownTypeDefault
    readonly property real remainingTime: sessionHost.remainingTime

    // ═══════════════════ MoOS Session Design Tokens ═══════════════════════
    // ONE canonical set for every session surface (lock, power, login scene).
    // The lock and login screens draw theirs in the breeze components
    // (SessionManagementScreen, WallpaperFader, ActionButton); the clock and
    // the face are not mirrored at all — this screen instantiates the same
    // two components. Change a token here → change it there to match.
    //   accentA = Kirigami.Theme.highlightColor       · live theme accent
    //   accentB = accentA HSL hue +0.09               · two-tone signature
    //   ink     = Kirigami.Theme.textColor            · neutral glyph / text
    //   island  = selected Window roles at0.94 · quiet rim · readable ink
    //             accent crest gradient · radius radiusDialog · depth halo
    //             (the same plate SessionManagementScreen draws for lock/login)
    //   tile    = gridUnit*8.6 × 5.3 · circular paired icon · calm native target
    //             idle fill ink0.025 · lit fill ink0.07 · focus-only accents
    //   ring    = countdown: Shape arc, stroke 3, accentA on accentA 0.18
    //   scrim   = backgroundColor  0.52 / 0.30 / 0.60  (top / mid / foot)
    //   blur    = shared sessionWallpaperBlur, also used by WallpaperFader
    //   fonts   = IBM Plex Sans Arabic across both scripts and all numerals
    //   clock   = org.kde.breeze.components Clock — the one session clock
    //   face    = org.kde.breeze.components UserDelegate — the one session face
    //   motion  = Units.shortDuration (hover/press) · longDuration (fades) · OutCubic
    // ══════════════════════════════════════════════════════════════════════
    readonly property color accent: Kirigami.Theme.highlightColor
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property var design: MoUI.Tokens
    // The session family's one size (Tokens.sessionScale): the island, its
    // tiles and its type grow and shrink with the clock and the face.
    readonly property real sessionScale: design.sessionScale(root.width, root.height)

    function settleScene() {
        backdropFade.stop();
        sheetEnter.stop();
        orbitRun.stop();
        wallpaper.opacity = 1;
        sheet.opacity = 1;
        sheet.scale = 1;
        sheetRise.y = 0;
        orbitGlow = 0;
    }
    onMotionEnabledChanged: if (!motionEnabled) { settleScene(); }
    onVisibleChanged: if (!visible) { settleScene(); }

    // The orbit: the light that runs round the lock and login island's rim runs
    // round this one too, twice, when the island arrives, and then docks in the
    // crest. A counted number of turns, never a loop.
    property real orbitAngle: 0
    property real orbitGlow: 0
    SequentialAnimation {
        id: orbitRun
        PauseAnimation { duration: root.design.motionPortal }
        NumberAnimation {
            target: root; property: "orbitGlow"; to: 1
            duration: root.design.duration(root.motionEnabled, root.design.motionGeometry)
        }
        NumberAnimation {
            target: root; property: "orbitAngle"
            from: 0; to: 360
            loops: 2
            duration: root.design.duration(root.motionEnabled, root.design.motionPortal) * 8
            easing.type: Easing.InOutSine
        }
        NumberAnimation {
            target: root; property: "orbitGlow"; to: 0
            duration: root.design.duration(root.motionEnabled, root.design.motionPortal)
        }
    }
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

    function stopCountdown() { root.cancelCountdown(); }

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
        default: return bilingual("خيارات الجلسة", "Session options");
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

    Component.onCompleted: {
        Qt.callLater(root.focusInitialAction);
        console.info("MOOS_SESSION_POWER_READY", Qt.resolvedUrl("SessionPower.qml"), activeLook, sceneWallpaper);
    }

    // ── Scene: the active theme's OWN wallpaper, blurred ─────────────────────
    // Every look-and-feel package ships its theme's wallpaper as
    // previews/fullscreenpreview.jpg; a package-relative path resolves to the
    // right one for each of the 18 themes, so the doorway is NEVER a flat colour
    // — it is the same background the desktop wears, softened by a real blur.
    // The QML stays byte-identical across packages; only the image differs.
    Image {
        id: wallpaper
        objectName: "moosSessionWallpaper"
        anchors.fill: parent
        source: root.wallpaperSource
        fillMode: Image.PreserveAspectCrop
        cache: true
        asynchronous: true
        opacity: 0
        layer.enabled: true
        // The lock and power scene use one blur radius; retain more of the
        // selected image's colour and contours while the card protects text.
        layer.effect: FastBlur { radius: root.design.sessionWallpaperBlur }
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
                Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, root.design.sessionScrimTopOpacity) }
            GradientStop { position: 0.45; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, root.design.sessionScrimMidOpacity) }
            GradientStop { position: 1.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, root.design.sessionScrimBottomOpacity) }
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
    readonly property real clockGap: Kirigami.Units.gridUnit * 1.5
    readonly property bool clockFits: clockBand.implicitHeight + clockGap + sheet.height
                                      + stageMargin * 2 <= root.height
    readonly property real groupHeight: sheet.height
                                        + (clockFits ? clockBand.implicitHeight + clockGap : 0)
    readonly property real groupTop: Math.round((root.height - groupHeight) / 2)

    Item {
        id: clockBand
        implicitWidth: sessionClock.implicitWidth * 0.72
        implicitHeight: sessionClock.implicitHeight * 0.72
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.groupTop
        visible: root.clockFits
        opacity: wallpaper.opacity
        SessionComponents.Clock {
            id: sessionClock
            anchors.centerIn: parent
            heroWhenIdle: false
            scale: 0.72
        }
    }

    // ── The Glass Island ─────────────────────────────────────────────────────
    // One substantial layered-material card carries the whole doorway: header
    // (emblem · clock · date), the question, the signed-in identity, the
    // countdown ring, the action dock and the way out. Material is painted
    // from scheme roles only — fill, sheen, border, rim — so all 16 palettes
    // wear it natively, and there is no offscreen effect layer behind it.
    Item {
        id: sheet
        // The wallpaper keeps the shared session veil; the working sheet
        // follows the selected desktop's light/dark material and ink roles.
        Kirigami.Theme.inherit: false
        Kirigami.Theme.colorSet: Kirigami.Theme.Window
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.groupTop + (root.clockFits ? clockBand.implicitHeight + root.clockGap : 0)
        width: Math.min(root.width - Kirigami.Units.gridUnit * 3,
                        Math.max(Kirigami.Units.gridUnit * 26 * root.sessionScale,
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
                if (GraphicsInfo.api !== GraphicsInfo.Software) {
                    orbitRun.start();
                }
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

        // The same material owner as login/lock. Three hard halo rectangles
        // produced visible nested rings over light wallpapers.
        MoUI.GlassSurface {
            id: island
            objectName: "moosSessionCard"
            anchors.fill: parent
            animateArrival: false // The complete sheet owns its finite entrance.
            radius: root.design.radiusDialog
            depth: root.design.glassLevelDialog
            surfaceColor: Kirigami.Theme.backgroundColor
            inkColor: Kirigami.Theme.textColor
            accentColor: root.accent
            fillOpacity: 0.94
            border.width: root.design.borderHairline
            border.color: Qt.rgba(Kirigami.Theme.textColor.r,
                                  Kirigami.Theme.textColor.g,
                                  Kirigami.Theme.textColor.b, 0.10)

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

            // The orbit's light, cut to the island's own rim; not drawn once docked.
            Item {
                id: rimMask
                anchors.fill: parent
                visible: false
                layer.enabled: root.orbitGlow > 0
                Rectangle {
                    anchors.fill: parent
                    radius: island.radius
                    color: "transparent"
                    border.width: 2
                    border.color: "black"
                    antialiasing: true
                }
            }
            Effects.ConicalGradient {
                id: rimPaint
                anchors.fill: parent
                visible: false
                angle: root.orbitAngle
                gradient: Gradient {
                    GradientStop { position: 0.00; color: Qt.alpha(root.accent, 0.0) }
                    GradientStop { position: 0.70; color: Qt.alpha(root.accent, 0.0) }
                    GradientStop { position: 0.90; color: Qt.alpha(root.accentB, 0.85) }
                    GradientStop { position: 0.985; color: root.accent }
                    GradientStop { position: 1.00; color: Qt.alpha(root.accent, 0.0) }
                }
            }
            Effects.OpacityMask {
                anchors.fill: parent
                source: rimPaint
                maskSource: rimMask
                visible: root.orbitGlow > 0
                opacity: root.orbitGlow
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
                faceSize: Kirigami.Units.gridUnit * 2.8 * root.sessionScale
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
                font.pointSize: Math.max(10, Math.round((Kirigami.Theme.defaultFont.pointSize + 7)
                                                        * root.sessionScale))
            }

            // ── Countdown ring (only while an action is pending) ──
            // The naked hairline is retired: remaining time is now a still arc
            // that empties clockwise around the seconds numeral. One Shape,
            // stroke-only, painted from accentA over its own 0.18 track — no
            // effect layer, and the per-second sweep is a gated Behavior.
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                visible: root.sessionHost.countingDown
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

            QQC2.Label {
                objectName: "moosPowerBootIntent"
                Layout.alignment: Qt.AlignHCenter
                Layout.maximumWidth: sheet.width - root.design.space6
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                textFormat: Text.PlainText
                visible: rebootToFirmwareSetup || rebootToBootLoaderMenu || rebootToBootLoaderEntry !== ""
                text: rebootToFirmwareSetup
                    ? root.bilingual("ستفتح إعدادات الجهاز بعد إعادة التشغيل", "Restart will open firmware settings")
                    : rebootToBootLoaderMenu
                    ? root.bilingual("ستفتح قائمة الإقلاع بعد إعادة التشغيل", "Restart will open the boot menu")
                    : root.bilingual("سيبدأ الإقلاع من: ", "Restart will use: ") + rebootToBootLoaderEntry
                color: Kirigami.Theme.neutralTextColor
            }

            // ── The power dock: a responsive grid of large tiles ──
            // The usual five actions share one calm row on a wide desktop.
            // Update variants still use balanced rows; narrow outputs lower
            // the cap before either the card or its caption can overflow.
            GridLayout {
                id: dock
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Kirigami.Units.smallSpacing
                rowSpacing: Kirigami.Units.largeSpacing
                columnSpacing: Kirigami.Units.largeSpacing
                readonly property int actionCount: root.visibleDockActions().length
                readonly property int widthLimit: Math.max(1, Math.floor(
                    ((root.width - Kirigami.Units.gridUnit * 7) + columnSpacing)
                    / (Kirigami.Units.gridUnit * 8.6 * root.sessionScale + columnSpacing)))
                columns: Math.max(1, Math.min(5, widthLimit,
                    actionCount <= 5 ? actionCount : Math.ceil(actionCount / 2)))

                SessionPowerButton {
                    id: suspendButton
                    revealOrder: 0
                    iconName: "system-suspend-symbolic"
                    text: root.shortLabel("السكون", "Sleep")
                    description: root.bilingual("إبقاء الجلسة", "Keep session")
                    visible: root.showAllOptions && spdMethods.SuspendState
                    onClicked: root.fireNow(() => root.suspendRequested(2))
                    onInteracted: root.stopCountdown()
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(suspendButton, horizontalStep, verticalStep)
                }
                SessionPowerButton {
                    id: hibernateButton
                    revealOrder: 1
                    iconName: "system-suspend-hibernate-symbolic"
                    text: root.shortLabel("إسبات", "Hibernate")
                    description: root.bilingual("حفظ الجلسة", "Save session")
                    visible: root.showAllOptions && spdMethods.HibernateState
                    onClicked: root.fireNow(() => root.suspendRequested(4))
                    onInteracted: root.stopCountdown()
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(hibernateButton, horizontalStep, verticalStep)
                }
                SessionPowerButton {
                    id: rebootButton
                    revealOrder: 2
                    iconName: softwareUpdatePending ? "system-reboot-update-symbolic" : "system-reboot-symbolic"
                    text: softwareUpdatePending ? root.shortLabel("تحديث وإعادة التشغيل", "Update & Restart") : root.shortLabel("إعادة التشغيل", "Restart")
                    description: armed ? root.bilingual("اضغط مجددًا لإعادة التشغيل", "Tap again to restart")
                        : (softwareUpdatePending ? root.bilingual("تثبيت التحديثات أولًا", "Install updates first") : root.bilingual("بدء جلسة جديدة", "Start fresh"))
                    emphasized: sdtype === ShutdownType.ShutdownTypeReboot
                    visible: maysd && (sdtype === ShutdownType.ShutdownTypeReboot || root.showAllOptions)
                    onClicked: root.armOrFire(rebootButton, () => { if (softwareUpdatePending) { root.rebootUpdateRequested(); } else { root.rebootRequested(); } })
                    onInteracted: root.stopCountdown()
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(rebootButton, horizontalStep, verticalStep)
                }
                SessionPowerButton {
                    id: rebootWithoutUpdatesButton
                    revealOrder: 3
                    iconName: "system-reboot-symbolic"
                    text: root.shortLabel("إعادة الآن", "Restart now")
                    description: armed ? root.bilingual("اضغط مجددًا لإعادة التشغيل", "Tap again to restart") : root.bilingual("بدون تحديث", "Without updating")
                    visible: maysd && softwareUpdatePending && (sdtype === ShutdownType.ShutdownTypeReboot || root.showAllOptions)
                    onClicked: root.armOrFire(rebootWithoutUpdatesButton, () => root.rebootRequested())
                    onInteracted: root.stopCountdown()
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(rebootWithoutUpdatesButton, horizontalStep, verticalStep)
                }
                SessionPowerButton {
                    id: shutdownButton
                    revealOrder: 4
                    iconName: softwareUpdatePending ? "system-shutdown-update-symbolic" : "system-shutdown-symbolic"
                    text: softwareUpdatePending ? root.shortLabel("تحديث وإيقاف التشغيل", "Update & Shut Down") : root.shortLabel("إيقاف التشغيل", "Shut Down")
                    description: armed ? root.bilingual("اضغط مجددًا للإيقاف", "Tap again to power off")
                        : (softwareUpdatePending ? root.bilingual("تثبيت التحديثات أولًا", "Install updates first") : root.bilingual("إيقاف الجهاز بأمان", "Power off safely"))
                    emphasized: sdtype === ShutdownType.ShutdownTypeHalt
                    destructive: true
                    visible: maysd && (sdtype === ShutdownType.ShutdownTypeHalt || root.showAllOptions)
                    onClicked: root.armOrFire(shutdownButton, () => { if (softwareUpdatePending) { root.haltUpdateRequested(); } else { root.haltRequested(); } })
                    onInteracted: root.stopCountdown()
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(shutdownButton, horizontalStep, verticalStep)
                }
                SessionPowerButton {
                    id: shutdownWithoutUpdatesButton
                    revealOrder: 5
                    iconName: "system-shutdown-symbolic"
                    text: root.shortLabel("إيقاف الآن", "Shut down now")
                    description: armed ? root.bilingual("اضغط مجددًا للإيقاف", "Tap again to power off") : root.bilingual("بدون تحديث", "Without updating")
                    destructive: true
                    visible: maysd && softwareUpdatePending && (sdtype === ShutdownType.ShutdownTypeHalt || root.showAllOptions)
                    onClicked: root.armOrFire(shutdownWithoutUpdatesButton, () => root.haltRequested())
                    onInteracted: root.stopCountdown()
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(shutdownWithoutUpdatesButton, horizontalStep, verticalStep)
                }
                SessionPowerButton {
                    id: logoutButton
                    revealOrder: 6
                    iconName: "system-log-out-symbolic"
                    text: root.shortLabel("تسجيل الخروج", "Log Out")
                    description: root.bilingual("إنهاء الجلسة", "End session")
                    visible: canLogout && (sdtype === ShutdownType.ShutdownTypeNone || root.showAllOptions)
                    onClicked: root.fireNow(() => root.logoutRequested())
                    onInteracted: root.stopCountdown()
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(logoutButton, horizontalStep, verticalStep)
                }
                SessionPowerButton {
                    id: lockButton
                    revealOrder: 7
                    iconName: "system-lock-screen-symbolic"
                    text: root.shortLabel("قفل الشاشة", "Lock Screen")
                    description: root.bilingual("العودة لاحقًا", "Return later")
                    visible: root.showAllOptions
                    onClicked: root.fireNow(() => root.lockScreenRequested())
                    onInteracted: root.stopCountdown()
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(lockButton, horizontalStep, verticalStep)
                }
            }

            // ── The hint line — one stable place for state guidance ──
            // Descriptions no longer pop in under individual tiles (which made
            // the dock jump); the island explains the armed confirm tap here,
            // in a reserved line that never reflows the layout.
            QQC2.Label {
                id: confirmationHint
                objectName: "moosSessionConfirmationHint"
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredHeight: confirmationMetrics.height
                Layout.maximumWidth: column.width
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                textFormat: Text.PlainText
                text: root.armedButton ? root.armedButton.description : ""
                color: Kirigami.Theme.textColor
                opacity: root.armedButton ? 1.0 : 0
                font.family: root.design.interfaceFamily; font.weight: Font.DemiBold
                font.pointSize: Kirigami.Theme.smallFont.pointSize + 1
                FontMetrics { id: confirmationMetrics; font: confirmationHint.font }
            }

            // ── The way out — a full-width quiet pill under its hairline ──
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                               Kirigami.Theme.textColor.b, 0.10)
            }
            SessionPowerButton {
                id: cancelButton
                revealOrder: 8
                iconName: "cancel-operation-symbolic"
                text: root.shortLabel("العودة إلى سطح المكتب", "Back to desktop")
                description: root.bilingual("العودة إلى سطح المكتب", "Back to desktop")
                subtle: true
                Layout.alignment: Qt.AlignHCenter
                Layout.bottomMargin: Kirigami.Units.smallSpacing
                onClicked: { root.disarm(); root.cancelRequested(); }
                onInteracted: root.stopCountdown()
                onNavigate: (horizontalStep, verticalStep) => root.moveFocus(cancelButton, horizontalStep, verticalStep)
            }
        }
    }
}
