/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    Plasma 6.8's shell owns controlsowner.js and timer.js. Preserve that single
    control instance and its native host; the shared MoOS view only draws and
    forwards the existing signals. No authentication or power executor here.
*/
import QtQuick
import org.moos.ui as MoUI
import "timer.js" as AutoTriggerTimer

MoUI.SessionPower {
    sessionHost: parent
    cancelCountdown: () => AutoTriggerTimer.cancelAutoTrigger()
}
