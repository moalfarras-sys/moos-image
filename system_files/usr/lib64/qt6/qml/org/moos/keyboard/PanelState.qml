// SPDX-FileCopyrightText: 2026 Moalfarras
// SPDX-License-Identifier: GPL-2.0-or-later

pragma Singleton
import QtQuick
import QtCore
import org.kde.plasma.workspace.dbus as DBus
import "TouchBarLogic.js" as Logic

QtObject {
    id: state

    readonly property bool greeter: Logic.isGreeterHome(StandardPaths.writableLocation(StandardPaths.HomeLocation))

    // KWin owns the detachable cover, external pointers and the user's tablet
    // policy. Keep the keys usable until it publishes a typed desktop posture.
    readonly property bool postureKnown: service.registered && typeof tablet.properties.tabletMode === "boolean"
    readonly property bool desktopPosture: postureKnown && tablet.properties.tabletMode === false
    readonly property DBus.DBusServiceWatcher service: DBus.DBusServiceWatcher {
        busType: DBus.BusType.Session
        watchedService: "org.kde.KWin"
    }
    readonly property DBus.Properties tablet: DBus.Properties {
        busType: DBus.BusType.Session
        service: state.service.registered ? "org.kde.KWin" : ""
        path: "/org/kde/KWin"
        iface: "org.kde.KWin.TabletModeManager"
    }
    readonly property DBus.SignalWatcher postureEvents: DBus.SignalWatcher {
        busType: DBus.BusType.Session
        service: "org.kde.KWin"
        path: "/org/kde/KWin"
        iface: "org.kde.KWin.TabletModeManager"
        enabled: state.service.registered
        function dbustabletModeChanged() { state.tablet.updateAll() }
    }

    // Only the focused surface's capability is exposed here. Surrounding text
    // and candidate insertion belong to the focused input method.
    readonly property DBus.Properties inputPanel: DBus.Properties {
        busType: DBus.BusType.Session
        service: state.service.registered ? "org.kde.KWin" : ""
        path: "/VirtualKeyboard"
        iface: "org.kde.kwin.VirtualKeyboard"
    }
    readonly property DBus.SignalWatcher inputEvents: DBus.SignalWatcher {
        busType: DBus.BusType.Session
        service: "org.kde.KWin"
        path: "/VirtualKeyboard"
        iface: "org.kde.kwin.VirtualKeyboard"
        enabled: state.service.registered
        function dbusactiveClientSupportsTextInputChanged() { state.inputPanel.updateAll() }
        function dbusvisibleChanged() { state.inputPanel.updateAll() }
    }
    readonly property DBus.DBusServiceWatcher keyboardPolicy: DBus.DBusServiceWatcher {
        busType: DBus.BusType.Session
        watchedService: "org.moos.KeyboardPolicy"
    }
    readonly property DBus.Properties presence: DBus.Properties {
        busType: DBus.BusType.Session
        service: state.keyboardPolicy.registered ? "org.moos.KeyboardPolicy" : ""
        path: "/KeyboardPolicy"
        iface: "org.moos.KeyboardPolicy"
    }
    readonly property bool desktopTextFocus: service.registered && keyboardPolicy.registered
        && presence.properties.PhysicalKeyboard === true && !greeter
        && inputPanel.properties.activeClientSupportsTextInput === true
        && inputPanel.properties.visible === false

    readonly property Settings appearance: Settings {
        location: StandardPaths.writableLocation(StandardPaths.GenericConfigLocation) + "/moos-keyboardrc"
        category: "Appearance"
        property int heightPercent: 30
        property int surfaceOpacity: 94
    }
    readonly property int heightPercent: Math.max(25, Math.min(42, appearance.heightPercent))
    readonly property int surfaceOpacity: Math.max(72, Math.min(100, appearance.surfaceOpacity))
}
