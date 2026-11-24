// SPDX-FileCopyrightText: 2026 Moalfarras
// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import org.kde.plasma.workspace.dbus as DBus

QtObject {
    id: focus
    required property bool followTextFocus
    required property bool desktopPosture
    property bool handledFocus: false
    onFollowTextFocusChanged: handledFocus = false
    onDesktopPostureChanged: {
        handledFocus = false
        if (followTextFocus && keyboard) keyboard.updateAll()
    }
    readonly property string iface: "org.kde.kwin.VirtualKeyboard"
    readonly property DBus.Properties keyboard: DBus.Properties {
        busType: DBus.BusType.Session
        service: focus.followTextFocus ? "org.kde.KWin" : ""
        path: "/VirtualKeyboard"
        iface: focus.iface
        onRefreshed: focus.followFocus()
    }
    readonly property DBus.SignalWatcher events: DBus.SignalWatcher {
        busType: DBus.BusType.Session
        service: "org.kde.KWin"
        path: "/VirtualKeyboard"
        iface: focus.iface
        enabled: focus.followTextFocus
        function dbusactiveChanged() { focus.keyboard.updateAll() }
        function dbusactiveClientSupportsTextInputChanged() { focus.keyboard.updateAll() }
        function dbusmodeChanged() { focus.keyboard.updateAll() }
        function dbusavailableChanged() { focus.keyboard.updateAll() }
    }

    // Some Wayland clients enable text input on pointer focus without asking
    // KWin to show the panel. Honor the native AnyInput preference once per
    // focus or posture change. A subsequent Hide stays in effect for the rest of that focus.
    // Plasma wraps a native D-Bus INT32 (the mode) while leaving booleans
    // plain. Never coerce a missing property or a single-property reply tuple.
    function followFocus() {
        const state = keyboard.properties
        const mode = state.mode
        const anyInput = mode === 2 || (!!mode && mode.value === 2)
        if (!followTextFocus || !anyInput || state.available !== true || state.active !== true
                || state.activeClientSupportsTextInput !== true) {
            handledFocus = false
            return
        }
        if (handledFocus || typeof state.visible !== "boolean") return
        handledFocus = true
        if (state.visible) return
        DBus.SessionBus.asyncCall({
            service: "org.kde.KWin", path: "/VirtualKeyboard",
            iface: focus.iface, member: "forceActivate"
        }, () => {}, error => console.warn("MoOS Touch Bar: KWin refused to show the panel", error.message))
    }
}
