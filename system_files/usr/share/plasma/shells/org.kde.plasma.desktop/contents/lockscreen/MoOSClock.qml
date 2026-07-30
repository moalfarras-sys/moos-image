/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    MoOS UI2 lock clock — editorial. A drop-in for org.kde.breeze components'
    Clock (same Item + `shadow` alias contract). Deliberately NOT a widget: a
    single oversized, ultra-light IBM Plex Sans Arabic time set in generous space, a hairline
    accent, and one quiet date. No capsule, no chrome. Premium by restraint,
    and fully theme-driven so it reads on any palette or wallpaper.
*/
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: clock

    property Item shadow
    implicitWidth: column.implicitWidth
    implicitHeight: column.implicitHeight

    // The motion gate for a surface that is up for HOURS.
    //
    // It is `> 1`, not `> 0`: Kirigami FLOORS longDuration at 1 when the user —
    // or the whole cloud edition, which sets AnimationDurationFactor=0 — has
    // asked for no motion. It is never 0, so `> 0` is always true and gates
    // nothing at all. KDE's own three BusyIndicator.qml files and
    // RejectPasswordPathAnimation.qml all test against 1 for exactly this
    // reason. Getting this wrong is invisible: the animation simply keeps
    // running and nobody is told.
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1

    // ── One date, in the session's own language ─────────────────────────────
    // This screen used to print the date TWICE: a hardcoded Qt.locale("ar")
    // line stacked over a hardcoded Qt.locale("en") line. On an Arabic session
    // that is the same day said twice; on an English one it is an Arabic date
    // the owner cannot read, above an English one. The date follows the SESSION
    // locale now — its language, its field order, its separators — and is said
    // once.
    readonly property var sessionLocale: Qt.locale()

    // …and the whole screen uses ONE numeral system. Qt renders ar_* dates with
    // Arabic-Indic digits (٢٧ يوليو ٢٠٢٦) while the hero time above is always
    // Latin HH:mm, so 20:01 and ٢٧ sat three centimetres apart in two different
    // number systems. Month and day NAMES stay the locale's — only the digits
    // are folded to Latin, so they match the clock they hang under. Persian
    // (U+06F0…U+06F9) folds too; fa_IR is the other locale Qt draws with
    // non-Latin digits.
    function latinNumerals(text) {
        let out = "";
        for (let i = 0; i < text.length; ++i) {
            const c = text.charCodeAt(i);
            if (c >= 0x0660 && c <= 0x0669) {
                out += String.fromCharCode(c - 0x0660 + 0x30);
            } else if (c >= 0x06F0 && c <= 0x06F9) {
                out += String.fromCharCode(c - 0x06F0 + 0x30);
            } else {
                out += text.charAt(i);
            }
        }
        return out;
    }

    ColumnLayout {
        id: column
        spacing: 0

        // ── The oversized, ultra-thin time. Always LTR (HH:mm) ──
        RowLayout {
            LayoutMirroring.enabled: false
            layoutDirection: Qt.LeftToRight
            spacing: 0

            // renderType on the three display Texts below is CurveRendering.
            // All three were NativeRendering, and all three were wrong.
            //
            // NativeRendering rasterises glyphs on the integer DEVICE pixel grid
            // with subpixel (RGB) antialiasing. This machine runs a 2.25
            // fractional scale, so the item origin lands BETWEEN device pixels
            // and a ~110pt glyph is filtered off-grid: every stem of the hero
            // clock carried a warm fringe down one edge and a cyan fringe down
            // the other, plainly visible in a 1:1 capture of
            // `kscreenlocker_greet --testing` (2026-07-27).
            //
            // QtRendering kills the fringe — but it is a distance field cached
            // at one small em size and scaled up, and at this size that is a
            // ~6x magnification: rendered and compared at 4x, the hairline
            // strokes came back soft and slightly wavy. Trading a colour fringe
            // for a blurred contour is not a fix on the one number the owner
            // looks at from across the room.
            //
            // CurveRendering (Qt 6.7+; this is 6.11) rasterises the real glyph
            // curves on the GPU, so it has neither a pixel grid to miss nor a
            // cached bitmap to stretch — sharp at any size and any scale. It
            // costs more per glyph, which is why it is here and not on the small
            // text below: five digits that change once a minute.
            //
            // NativeRendering still earns its place on SMALL text at integer
            // scales. Nothing on this clock is either.
            Text {
                id: hours
                text: Qt.formatTime(timeSource.now, "HH")
                color: Kirigami.Theme.textColor
                font.family: "IBM Plex Sans Arabic"
                font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize * 11)
                font.weight: Font.ExtraLight
                font.letterSpacing: -2
                renderType: Text.CurveRendering
            }
            Text {
                id: colon
                text: ":"
                color: Kirigami.Theme.highlightColor
                font.family: "IBM Plex Sans Arabic"
                font.pointSize: hours.font.pointSize
                font.weight: Font.ExtraLight
                renderType: Text.CurveRendering
                opacity: 0.9

                // The separator used to flicker on a four-second cycle keyed to
                // NOTHING — a seconds-modulo toggle that dropped it to 30% for
                // half of every cycle. A clock whose colon fades in and out at
                // an interval that matches no unit of time reads as a fault
                // light, not as a timepiece.
                //
                // It now pulses ONCE, on the only event this clock has: the
                // minute changing. Same gesture, same shape and same durations
                // as the desktop's ClockCard minutePulse, so the lock screen and
                // the desktop keep one heartbeat.
                SequentialAnimation {
                    id: minutePulse
                    running: false

                    NumberAnimation {
                        target: colon
                        property: "opacity"
                        from: 0.9
                        to: 0.32
                        duration: 170
                        easing.type: Easing.InQuad
                    }
                    NumberAnimation {
                        target: colon
                        property: "opacity"
                        to: 0.9
                        duration: 250
                        easing.type: Easing.OutCubic
                    }
                }
            }
            Text {
                id: minutes
                text: Qt.formatTime(timeSource.now, "mm")
                color: Kirigami.Theme.textColor
                font.family: "IBM Plex Sans Arabic"
                font.pointSize: hours.font.pointSize
                font.weight: Font.ExtraLight
                font.letterSpacing: -2
                renderType: Text.CurveRendering
            }
        }

        // ── A single hairline accent ──
        // It used to breathe forever: a 6.4-second opacity loop with no motion
        // gate. Two pixels of bar, but an infinite animation holds the render
        // loop at full frame rate and repaints the WHOLE window — and this
        // window also runs a DropShadow over the clock, so every one of those
        // frames re-blurred the hero type as well. It was part of the 11.8% of a
        // CPU core this screen measured on a LOCKED, IDLE machine; with this and
        // the brand's five loops gated, the same measurement reads 0.7%. The
        // hairline is a mark, not a heartbeat; it is static, and the minute
        // pulse above is the one deliberate motion on this clock.
        Rectangle {
            id: accentTick
            Layout.topMargin: Kirigami.Units.smallSpacing
            Layout.preferredWidth: Kirigami.Units.gridUnit * 4
            Layout.preferredHeight: 2
            radius: 1
            color: Kirigami.Theme.highlightColor
            opacity: 0.9
        }

        // ── The date: once, in the session's language, in Latin digits ──
        Text {
            Layout.topMargin: Kirigami.Units.largeSpacing
            text: clock.latinNumerals(clock.sessionLocale.toString(
                      timeSource.now, clock.sessionLocale.dateFormat(Locale.LongFormat)))
            color: Kirigami.Theme.textColor
            opacity: 0.85
            // Plex Arabic carries Latin as well as Arabic, so ONE family draws
            // this line whichever script the session speaks — the date never
            // changes weight or width when the locale does.
            font.family: "IBM Plex Sans Arabic"
            font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize * 1.4)
            font.weight: Font.Light
            renderType: Text.QtRendering
        }
    }

    QtObject {
        id: timeSource
        property date now: new Date()
    }

    Timer {
        // Still 1 Hz, deliberately. A timer armed for the next minute boundary
        // is the tempting optimisation and it is wrong here: timers do not fire
        // while the machine is suspended, so the first thing the owner would see
        // on waking the lid is the hero clock showing the time they closed it,
        // for up to a full minute. Ticking once a second costs a JS call and two
        // integer compares.
        //
        // What actually cost something was REDRAWING once a second for a clock
        // that only ever shows HH:mm: `now` fed four bindings and a DropShadow.
        // So the tick is cheap and `now` — and everything under it — only moves
        // when the displayed minute really changes.
        interval: 1000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: {
            const d = new Date();
            if (d.getMinutes() === timeSource.now.getMinutes()
                    && d.getHours() === timeSource.now.getHours()
                    && d.getDate() === timeSource.now.getDate()) {
                return;
            }
            timeSource.now = d;
            if (clock.motionEnabled) {
                minutePulse.restart();
            }
        }
    }
}
