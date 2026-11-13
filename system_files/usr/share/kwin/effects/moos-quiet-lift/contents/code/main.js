/*
 * MoOS Quiet Lift, using KWin's native animation owner.
 * Window eligibility derives from KDE's Scale effect, retaining its exclusions.
 * SPDX-FileCopyrightText: 2018, 2021 Vlad Zahorodnii <vlad.zahorodnii@kde.org>
 * SPDX-FileCopyrightText: 2026 MoOS contributors
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
"use strict";

// Bridge to artwork/moos-design/tokens.json, checked with the shared QML roles.
// KWin's JavaScript effect engine cannot import a QML singleton.
const motionGeometry = 220;
const motionPress = 160;
const excludedClasses = {
    "ksmserver ksmserver": [],
    "ksmserver-logout-greeter ksmserver-logout-greeter": [],
    "ksplashqml ksplashqml": [],
    "spectacle org.kde.spectacle": ["region-editor"]
};

class QuietLift {
    constructor() {
        this.running = new Set();
        effects.windowAdded.connect(this.open.bind(this));
        effects.windowClosed.connect(this.close.bind(this));
        effects.windowDataChanged.connect(this.grabChanged.bind(this));
        effects.windowDeleted.connect(window => this.running.delete(window));
        effect.animationEnded.connect(this.ended.bind(this));
        effect.configChanged.connect(() => {
            if (animationTime(motionGeometry) <= 1) {
                for (const window of this.running) {
                    this.stop(window);
                }
            }
        });
    }

    eligible(window) {
        if (effects.hasActiveFullScreenEffect || !window.visible || !window.managed
                || window.popupWindow || window.lockScreen || window.outline
                || window.fullScreen || animationTime(motionGeometry) <= 1) {
            return false;
        }
        const excluded = excludedClasses[window.windowClass];
        if (excluded && (!excluded.length || excluded.includes(window.tag))) {
            return false;
        }
        if (window.windowClass === "plasmashell plasmashell"
                || window.windowClass === "plasmashell org.kde.plasmashell") {
            return window.hasDecoration;
        }
        return window.normalWindow || window.dialog;
    }

    roles(window, value) {
        window.setData(Effect.WindowForceBackgroundContrastRole, value);
        window.setData(Effect.WindowForceBlurRole, value);
    }

    stop(window) {
        const state = window.moosQuietLift;
        delete window.moosQuietLift;
        this.running.delete(window);
        if (state) {
            cancel(state.ids);
            this.roles(window, null);
        }
    }

    ended(window) {
        const state = window.moosQuietLift;
        if (!state) {
            return;
        }
        // Native KWin emits once per attribute, with id 0, not the animation id.
        // Keep glass roles until all three equal-duration attributes finish.
        if (--state.remaining === 0) {
            delete window.moosQuietLift;
            this.running.delete(window);
            this.roles(window, null);
        }
    }

    start(window, opening) {
        this.stop(window);
        const lift = Math.min(18, Math.max(0, window.geometry.height * 0.025));
        const scale = opening ? 0.96 : 0.985;
        const animations = opening ? [
            {type: Effect.Scale, from: scale, to: 1},
            {type: Effect.Translation, from: {value1: 0, value2: lift}, to: {value1: 0, value2: 0}},
            {type: Effect.Opacity, from: 0, to: 1}
        ] : [
            {type: Effect.Scale, from: 1, to: scale},
            {type: Effect.Translation, from: {value1: 0, value2: 0}, to: {value1: 0, value2: lift / 2}},
            {type: Effect.Opacity, from: 1, to: 0}
        ];
        this.roles(window, true);
        window.moosQuietLift = {
            opening,
            remaining: animations.length,
            ids: animate({window, animations, keepAlive: true,
                duration: animationTime(opening ? motionGeometry : motionPress),
                curve: opening ? QEasingCurve.OutCubic : QEasingCurve.InCubic})
        };
        this.running.add(window);
    }

    open(window) {
        if (this.eligible(window) && !effect.isGrabbed(window, Effect.WindowAddedGrabRole)) {
            this.start(window, true);
        }
    }

    close(window) {
        if (!this.eligible(window) || window.skipsCloseAnimation
                || effect.isGrabbed(window, Effect.WindowClosedGrabRole)) {
            this.stop(window);
            return;
        }
        const state = window.moosQuietLift;
        // Closing during arrival reverses the actual current native timeline;
        // cancelling and starting at scale 1 would visibly jump on fast apps.
        if (state && state.opening && redirect(state.ids, Effect.Backward)) {
            state.opening = false;
            return;
        }
        this.start(window, false);
    }

    grabChanged(window, role) {
        if ((role === Effect.WindowAddedGrabRole || role === Effect.WindowClosedGrabRole)
                && effect.isGrabbed(window, role)) {
            this.stop(window);
        }
    }
}

new QuietLift();
