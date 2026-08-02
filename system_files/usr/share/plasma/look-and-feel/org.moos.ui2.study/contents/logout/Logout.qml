/*
    SPDX-FileCopyrightText: 2014 Aleix Pol Gonzalez <aleixpol@blue-systems.com>
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    The host contract (signals, ShutdownType, spdMethods, maysd, canLogout,
    softwareUpdatePending, remainingTime) is KDE Plasma 6.7's org.kde.breeze
    Logout.qml — untouched, so every action stays wired to the system. The
    visual design is an original MoOS UI2 ground-up rework: the Tidal Horizon
    portal, a centred live-clock + emblem header, and a compact command island
    whose actions use the same portal-key geometry as Login and Lock.
    Shut Down / Restart are gated behind a confirm tap (armOrFire); the signal
    each portal key emits stays byte-identical to the stock contract.
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects

import org.kde.coreaddons as KCoreAddons
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.sessions

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
    // Mirrored exactly on the lock (LockScreenUi/MainBlock/MoOSClock) and the
    // breeze ActionButton; documented here as the single source of truth so no
    // surface drifts. Change a token here → change it on the lock to match.
    //   accentA = Kirigami.Theme.highlightColor       · live theme accent
    //   accentB = accentA HSL hue +0.09               · two-tone signature
    //   ink     = Kirigami.Theme.textColor            · neutral glyph / text
    //   key     = gridUnit*5.8 × 4.8 · icon 0.42 of height · radius 0.28h
    //             idle fill ink 0.08 · lit fill ink 0.16 · crest cut + horizon
    //   pill    = radius height/2 (password field)
    //   scrim   = backgroundColor  0.52 / 0.30 / 0.60  (top / mid / foot)
    //   blur    = 54 wallpaper (lock's breeze WallpaperFader = 50)
    //   fonts   = IBM Plex Sans Arabic across both scripts and all numerals
    //   clock   = Font.Thin · letterSpacing -2 · accent colon · hairline accent
    //   motion  = Units.shortDuration (hover/press) · longDuration (fades) · OutCubic
    // ══════════════════════════════════════════════════════════════════════
    readonly property color accent: Kirigami.Theme.highlightColor
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
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

    property string nowTime: Qt.formatTime(new Date(), "HH:mm")
    Timer {
        interval: 15000; repeat: true; running: root.visible
        onTriggered: root.nowTime = Qt.formatTime(new Date(), "HH:mm")
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
    // key (it fills + shows a "press again" hint), the second FIRES the real
    // system signal. Everything else (Sleep, Log Out, Lock) fires immediately.
    // This only gates the click — the signal each key emits is byte-identical to
    // the stock contract, so the system path is untouched.
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

    // Orb captions follow the same single-language rule without isolation
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
            duration: 420; easing.type: Easing.OutCubic }
    }
    // Legibility scrim — the theme's own canvas, heavier at the top and foot so
    // the clock and the dock stay readable over any wallpaper. Calculated
    // transparency, never an opaque wash.
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

    // ── Tidal Horizon Portal ─────────────────────────────────────────────────
    // One shared curve now identifies every doorway. There are no drifting
    // curtains, breathing rings, or decorative loops: the portal performs one
    // short depth reveal, then becomes completely still.
    TidalHorizon {
        id: portal
        anchors.horizontalCenter: parent.horizontalCenter
        // The arc is a FRAME, never a line through the controls.  Its crest
        // stays behind the brand while its horizon lands below the Cancel key.
        // A wide 1.8:1 field also keeps both shoulders outside the five-action
        // dock on 16:9, 16:10 and ultrawide displays.
        y: parent.height * 0.10
        width: Math.min(parent.width * 0.96, parent.height * 1.80)
        height: Math.min(parent.height * 0.90, width * 0.56)
        accentA: root.accent
        accentB: root.accentB
        ink: Kirigami.Theme.textColor
        surface: Kirigami.Theme.alternateBackgroundColor
        compact: root.width < Kirigami.Units.gridUnit * 64
        reveal: root.motionEnabled ? 0 : 1
        intensity: 0.88

        Component.onCompleted: {
            if (root.motionEnabled) {
                portalReveal.start();
            }
        }
    }
    NumberAnimation {
        id: portalReveal
        target: portal
        property: "reveal"
        from: 0
        to: 1
        duration: 480
        easing.type: Easing.OutCubic
    }

    // The scene ABSORBS clicks; it does not cancel on one. This MouseArea used
    // to call cancelRequested(), and the sheet carried a "blocker" MouseArea to
    // shield its own background from it — declared `acceptedButtons:
    // Qt.NoButton`, which makes a MouseArea decline every button and let the
    // press fall straight through to this one. So a click on the giant clock, on
    // the heading, or in the gaps between the keys silently cancelled a pending
    // shutdown. Dismissing the doorway is now exactly two gestures, both
    // deliberate: the Cancel key and Escape.
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons }

    // ── The command sheet: a live-clock header over a column of action rows ──
    Item {
        id: sheet
        anchors.centerIn: parent
        // 50 grid units comfortably hold five 7-unit action cells while
        // avoiding the full-window "settings sheet" silhouette at HiDPI.
        width: Math.min(root.width - Kirigami.Units.gridUnit * 3, Kirigami.Units.gridUnit * 50)
        height: Math.min(root.height - Kirigami.Units.gridUnit * 3, column.implicitHeight)

        opacity: root.motionEnabled ? 0 : 1
        transform: Translate { id: sheetRise; y: Kirigami.Units.gridUnit * 2 }
        Component.onCompleted: {
            if (root.motionEnabled) {
                sheetEnter.start();
            } else {
                sheetRise.y = 0;
            }
        }
        ParallelAnimation {
            id: sheetEnter
            NumberAnimation { target: sheet; property: "opacity"; from: 0; to: 1
                duration: 420; easing.type: Easing.OutCubic }
            NumberAnimation { target: sheetRise; property: "y"; from: Kirigami.Units.gridUnit * 2; to: 0
                duration: 420; easing.type: Easing.OutCubic }
        }

        // The command island is deliberately compact: a still translucent plate
        // inside the large portal, with one Tidal Cut on its upper rim.
        Rectangle {
            anchors.fill: parent
            anchors.margins: -Kirigami.Units.gridUnit * 1.3
            radius: Math.min(Kirigami.Units.gridUnit * 1.6, height * 0.075)
            color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                           Kirigami.Theme.backgroundColor.g,
                           Kirigami.Theme.backgroundColor.b, 0.42)
            border.width: 1
            border.color: Qt.rgba(Kirigami.Theme.textColor.r,
                                  Kirigami.Theme.textColor.g,
                                  Kirigami.Theme.textColor.b, 0.16)

            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: -height / 2
                width: Kirigami.Units.gridUnit * 4.2
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
            width: parent.width
            spacing: Kirigami.Units.largeSpacing

            // ── Header: emblem, live clock, context — centred over the dock ──
            Item {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Kirigami.Units.gridUnit * 5.2
                Layout.preferredHeight: Kirigami.Units.gridUnit * 5.2
                // The emblem's halo, drawn from the live accent. It used to be a
                // shipped raster, images/glow-cyan.png — a fixed #22D3EE cyan
                // that the family generator can never retint, because it
                // recolours .svg and copies every other file byte-for-byte. So
                // all 16 themes wore the same cyan ring: on Arena's magenta the
                // halo measured hue ~270 against an accent of hue ~330. Built
                // from Kirigami.Theme.highlightColor it tracks every palette,
                // and the PNG no longer ships. Same RadialGradient idiom as the
                // portal-key bloom in MoOSUI2ActionButton, explicit radii for a clean
                // circle.
                RadialGradient {
                    anchors.centerIn: parent
                    width: parent.width * 2.1; height: width
                    horizontalRadius: width * 0.5
                    verticalRadius: height * 0.5
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.34) }
                        GradientStop { position: 0.34; color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.16) }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                }
                Image {
                    anchors.fill: parent
                    source: "../splash/images/moos-logo.png"
                    fillMode: Image.PreserveAspectFit; smooth: true; asynchronous: true
                }
            }
            // ── Editorial clock — the ONE MoOS clock face, unified with the lock's
            //    MoOSClock: oversized, ultra-thin, an accent colon, a hairline.
            //    Forced LTR so HH:mm never mirrors under RTL.
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                LayoutMirroring.enabled: false
                layoutDirection: Qt.LeftToRight
                spacing: 0
                QQC2.Label {
                    text: root.nowTime.split(":")[0]
                    color: Kirigami.Theme.textColor
                    font.family: "IBM Plex Sans Arabic"; font.weight: Font.ExtraLight
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize + 34
                    font.letterSpacing: -2
                }
                QQC2.Label {
                    text: ":"
                    color: root.accent
                    font.family: "IBM Plex Sans Arabic"; font.weight: Font.ExtraLight
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize + 34
                }
                QQC2.Label {
                    text: root.nowTime.split(":")[1]
                    color: Kirigami.Theme.textColor
                    font.family: "IBM Plex Sans Arabic"; font.weight: Font.ExtraLight
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize + 34
                    font.letterSpacing: -2
                }
            }
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Kirigami.Units.smallSpacing
                Layout.preferredWidth: Kirigami.Units.gridUnit * 4
                Layout.preferredHeight: 2; radius: 1
                color: root.accent
                opacity: 0.9
            }
            QQC2.Label {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Kirigami.Units.smallSpacing
                Layout.maximumWidth: Kirigami.Units.gridUnit * 36
                horizontalAlignment: Text.AlignHCenter
                text: root.headingText()
                // The question is the point of this screen, so it is drawn in the
                // foreground role, softened by opacity rather than swapped for a
                // weaker colour. It used to be disabledTextColor — semantically
                // "this control is switched off", and on the live 4K render it
                // measured 4.41:1 against the blurred wallpaper, a hair under
                // WCAG AA. This lands near 7.5:1 and still reads as a subtitle,
                // because the clock above it is 34pt.
                color: Kirigami.Theme.textColor
                opacity: 0.85
                elide: Text.ElideRight
                font.family: "IBM Plex Sans Arabic"
                font.pointSize: Kirigami.Theme.defaultFont.pointSize + 1
            }
            // The signed-in name. It was drawn in the accent and measured 3.58:1
            // against the blurred wallpaper on the live 4K render — under WCAG
            // AA's 4.5:1, and this is small text. The accent still marks the
            // clock's colon and the hairline right above, so the identity line
            // gives it up for the scheme's full-strength foreground role; every
            // one of the 16 palettes then carries this name at its own maximum
            // contrast, with no hex anywhere.
            QQC2.Label {
                Layout.alignment: Qt.AlignHCenter
                text: currentUser.fullName
                visible: text.length > 0
                color: Kirigami.Theme.textColor
                font.family: "IBM Plex Sans Arabic"; font.weight: Font.DemiBold
                font.pointSize: Kirigami.Theme.smallFont.pointSize
            }

            // ── Countdown (only when an action is pending) ──
            // fillWidth must be pinned OFF. QtQuick.Layouts propagates size
            // policy upwards: the progress track inside this row sets
            // fillWidth: true, which silently makes the row itself expanding and
            // overrides the 22-unit preferredWidth below — the countdown hairline
            // then ran the full width of the sheet with its seconds counter
            // stranded at the far end. Declaring it false keeps the bar the
            // compact object it was drawn as.
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                Layout.fillWidth: false
                Layout.preferredWidth: Kirigami.Units.gridUnit * 22
                visible: countdownTimer.running
                spacing: Kirigami.Units.smallSpacing
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 3; radius: 2
                    color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.22)
                    Rectangle {
                        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                        radius: parent.radius; color: root.accent
                        width: parent.width * Math.max(0, Math.min(1, root.remainingTime / 30))
                        // 0 when animations are off: this Behavior re-fires every second of the
                        // countdown, so an ungated 950ms here animated continuously through the
                        // whole 30s even with AnimationDurationFactor=0.
                        Behavior on width { NumberAnimation { duration: Kirigami.Units.longDuration > 1 ? 950 : 0; easing.type: Easing.Linear } }
                    }
                }
                QQC2.Label {
                    text: root.remainingTime
                    color: root.accent; font.family: "IBM Plex Sans Arabic"; font.weight: Font.Bold
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
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
                wrapMode: Text.WordWrap; font.family: "IBM Plex Sans Arabic"
                font.pointSize: Kirigami.Theme.smallFont.pointSize
            }
            QQC2.Label {
                Layout.alignment: Qt.AlignHCenter
                Layout.maximumWidth: Kirigami.Units.gridUnit * 34
                horizontalAlignment: Text.AlignHCenter
                visible: softwareUpdatePending
                text: root.bilingual("تحديثات النظام جاهزة للتثبيت", "System updates are ready to install")
                color: Kirigami.Theme.positiveTextColor
                wrapMode: Text.WordWrap; font.family: "IBM Plex Sans Arabic"
                font.weight: Font.DemiBold; font.pointSize: Kirigami.Theme.smallFont.pointSize
            }

            // ── The power dock: a responsive grid of portal keys ──
            // A single RowLayout could expose eight actions when an update and both
            // suspend methods were available: 8 × 7 grid units plus spacing exceeded
            // this 50-unit island and clipped at fractional scaling. Keep at most five
            // columns and form balanced 3+3 / 4+3 / 4+4 rows for six to eight actions.
            GridLayout {
                id: dock
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Kirigami.Units.smallSpacing
                rowSpacing: Kirigami.Units.largeSpacing
                columnSpacing: Kirigami.Units.largeSpacing
                readonly property int actionCount: root.visibleDockActions().length
                readonly property int widthLimit: Math.max(1, Math.floor(
                    (sheet.width + columnSpacing)
                    / (Kirigami.Units.gridUnit * 7 + columnSpacing)))
                columns: Math.max(1, Math.min(5, widthLimit,
                    actionCount <= 5 ? actionCount : Math.ceil(actionCount / 2)))

                MoOSUI2ActionButton {
                    id: suspendButton
                    iconName: "system-suspend-symbolic"
                    text: root.shortLabel("تعليق", "Sleep")
                    description: root.bilingual("إبقاء الجلسة", "Keep session")
                    visible: root.showAllOptions && spdMethods.SuspendState
                    onClicked: root.fireNow(() => root.suspendRequested(2))
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(suspendButton, horizontalStep, verticalStep)
                }
                MoOSUI2ActionButton {
                    id: hibernateButton
                    iconName: "system-suspend-hibernate-symbolic"
                    text: root.shortLabel("إسبات", "Hibernate")
                    description: root.bilingual("حفظ الجلسة", "Save session")
                    visible: root.showAllOptions && spdMethods.HibernateState
                    onClicked: root.fireNow(() => root.suspendRequested(4))
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(hibernateButton, horizontalStep, verticalStep)
                }
                MoOSUI2ActionButton {
                    id: rebootButton
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
                    iconName: "system-reboot-symbolic"
                    text: root.shortLabel("إعادة الآن", "Restart now")
                    description: armed ? root.bilingual("اضغط مجددًا لإعادة التشغيل", "Tap again to restart") : root.bilingual("بدون تحديث", "Without updating")
                    visible: maysd && softwareUpdatePending && (sdtype === ShutdownType.ShutdownTypeReboot || root.showAllOptions)
                    onClicked: root.armOrFire(rebootWithoutUpdatesButton, () => root.rebootRequested())
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(rebootWithoutUpdatesButton, horizontalStep, verticalStep)
                }
                MoOSUI2ActionButton {
                    id: shutdownButton
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
                    iconName: "system-log-out-symbolic"
                    text: root.shortLabel("تسجيل الخروج", "Log Out")
                    description: root.bilingual("إنهاء الجلسة", "End session")
                    visible: canLogout && (sdtype === ShutdownType.ShutdownTypeNone || root.showAllOptions)
                    onClicked: root.fireNow(() => root.logoutRequested())
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(logoutButton, horizontalStep, verticalStep)
                }
                MoOSUI2ActionButton {
                    id: lockButton
                    iconName: "system-lock-screen-symbolic"
                    text: root.shortLabel("قفل الشاشة", "Lock Screen")
                    description: root.bilingual("العودة لاحقًا", "Return later")
                    visible: root.showAllOptions
                    onClicked: root.fireNow(() => root.lockScreenRequested())
                    onNavigate: (horizontalStep, verticalStep) => root.moveFocus(lockButton, horizontalStep, verticalStep)
                }
            }

            // ── Cancel — subtle, centred below the dock ──
            // The comment said "subtle" from the first rewrite; the button was
            // drawn at full action weight, the same disc and the same DemiBold
            // caption as Shut Down, so the way OUT competed with the actions.
            // `subtle` is what makes it read one step down the hierarchy.
            MoOSUI2ActionButton {
                id: cancelButton
                iconName: "cancel-operation-symbolic"
                text: root.shortLabel("إلغاء", "Cancel")
                description: root.bilingual("العودة إلى سطح المكتب", "Back to desktop")
                subtle: true
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Kirigami.Units.largeSpacing
                onClicked: { root.disarm(); root.cancelRequested(); }
                onNavigate: (horizontalStep, verticalStep) => root.moveFocus(cancelButton, horizontalStep, verticalStep)
            }
        }
    }
}
