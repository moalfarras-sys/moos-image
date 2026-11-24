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
    readonly property bool desktopPosture: service.registered
        && tablet.properties.tabletMode === false
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

    readonly property Settings appearance: Settings {
        location: StandardPaths.writableLocation(StandardPaths.GenericConfigLocation) + "/moos-keyboardrc"
        category: "Appearance"
        property int heightPercent: 30
        property int surfaceOpacity: 94
    }
    readonly property int heightPercent: Math.max(25, Math.min(42, appearance.heightPercent))
    readonly property int surfaceOpacity: Math.max(72, Math.min(100, appearance.surfaceOpacity))
}
