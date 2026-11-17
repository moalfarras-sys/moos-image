// SPDX-License-Identifier: GPL-2.0-or-later
// Reuse the fixed MoOS executor. No QML command, model text or device name reaches a shell.
import QtQuick
import org.kde.plasma.plasma5support as P5Support
import org.moos.ui as MoUI
import org.kde.bluezqt as BluezQt
import org.kde.plasma.networkmanagement as PlasmaNM
import org.kde.kitemmodels as KItemModels
import org.kde.plasma.private.volume as Audio
import org.kde.plasma.private.brightnesscontrolplugin as Brightness
import org.kde.plasma.workspace.dbus as DBus
import org.kde.notificationmanager as NotificationManager

Item {
    id: backend
    visible: false
    property bool opened: false
    property bool testing: false
    property var testCommands: []
    property bool busy: false
    property bool ready: false
    property var state: ({})
    property var batteryPercent: null
    property var pluggedIn: null
    readonly property string wifiConnectionName: nativeWatchers.item ? nativeWatchers.item.wifiConnectionName : ""
    readonly property string bluetoothConnectionName: nativeWatchers.item ? nativeWatchers.item.bluetoothConnectionName : ""
    property string errorText: ""
    property string pendingField: ""
    property var pendingValue: null
    property string currentCommand: ""
    property bool refreshQueued: false
    property int activeInteractions: 0
    readonly property string prefix: "timeout --kill-after=2s 18 /usr/bin/moos-control "
    readonly property string statusCommand: prefix + "status"
    onOpenedChanged: {
        if (opened) refresh();
        else { refreshDelay.stop(); refreshQueued = false; }
    }
    onBusyChanged: if (!busy && opened && refreshQueued && activeInteractions === 0) refreshDelay.restart()
    // Sliders hold this lease until their release has submitted its fixed action.
    // A native device event must not write a fresh value through an active drag.
    function beginInteraction() { activeInteractions += 1; refreshDelay.stop(); }
    function endInteraction() {
        activeInteractions = Math.max(0, activeInteractions - 1);
        if (!activeInteractions && opened && refreshQueued && !busy) refreshDelay.restart();
    }
    function scheduleRefresh() {
        if (!opened) return;
        refreshQueued = true;
        if (!busy && activeInteractions === 0) refreshDelay.restart();
    }
    function refresh() { readStatus(false); }
    function readStatus(preserveError) {
        if (busy || activeInteractions > 0) { if (opened) refreshQueued = true; return; }
        if (!preserveError) errorText = "";
        busy = true;
        execute(statusCommand);
    }
    Timer {
        id: refreshDelay
        interval: 180
        repeat: false
        onTriggered: {
            if (!backend.opened || backend.busy || backend.activeInteractions > 0) return;
            backend.refreshQueued = false;
            backend.readStatus(true);
        }
    }
    function execute(command) {
        currentCommand = command;
        if (testing) testCommands = testCommands.concat([command]);
        else executor.connectSource(command);
    }
    function commandFor(field, value) {
        if (["wifi", "bluetooth", "night_light", "dnd"].indexOf(field) >= 0 && typeof value === "boolean")
            return ({wifi: "wifi", bluetooth: "bluetooth", night_light: "night-light", dnd: "dnd"})[field] + (value ? " on" : " off");
        if (field === "muted" && typeof value === "boolean") return value ? "mute" : "unmute";
        if (field === "mic_muted" && typeof value === "boolean") return value ? "mic mute" : "mic unmute";
        if ((field === "volume" || field === "brightness") && Number.isInteger(value) && value >= (field === "brightness" ? 5 : 0) && value <= 100)
            return field + " " + value;
        if (field === "power_profile" && ["power-saver", "balanced", "performance"].indexOf(value) >= 0)
            return "power-profile " + value;
        return "";
    }
    function request(field, value) {
        if (busy || !ready || state[field] === null || state[field] === undefined) return false;
        const command = commandFor(field, value);
        if (!command.length) return false;
        errorText = "";
        pendingField = field;
        pendingValue = value;
        busy = true;
        execute(prefix + command);
        return true;
    }
    function decode(text) {
        const data = JSON.parse(text);
        if (!data || Array.isArray(data) || typeof data !== "object") throw new Error("shape");
        for (const key of ["wifi", "bluetooth", "muted", "night_light", "dnd", "mic_muted"])
            if (data[key] !== null && typeof data[key] !== "boolean") throw new Error("boolean");
        for (const key of ["volume", "brightness"])
            if (data[key] !== null && (typeof data[key] !== "number" || !Number.isFinite(data[key]) || data[key] < 0 || data[key] > 100)) throw new Error("range");
        if (data.power_profile !== null && ["power-saver", "balanced", "performance"].indexOf(data.power_profile) < 0) throw new Error("profile");
        return data;
    }
    function finish(source, data) {
        executor.disconnectSource(source);
        if (source !== currentCommand) return;
        if (data["exit code"] !== 0 || data["exit status"] !== 0) {
            errorText = MoUI.Locale.local("تعذّر تنفيذ التغيير. لم نؤكد نجاحه.", "The change could not be confirmed.");
            if (source === statusCommand) { ready = false; busy = false; pendingField = ""; }
            else { pendingField = ""; execute(statusCommand); }
            return;
        }
        if (source !== statusCommand) { execute(statusCommand); return; }
        try {
            const snapshot = decode(data.stdout);
            if (pendingField.length && snapshot[pendingField] !== pendingValue)
                errorText = MoUI.Locale.local("الجهاز لم يؤكد القيمة المطلوبة. جرّب مجددًا.", "The device did not confirm the requested value. Try again.");
            if (activeInteractions > 0) refreshQueued = opened;
            else state = snapshot;
            ready = true;
        } catch (error) {
            ready = false;
            errorText = MoUI.Locale.local("حالة الأجهزة غير متاحة الآن.", "Device status is unavailable right now.");
        }
        pendingField = "";
        busy = false;
    }
    // These native owners only announce invalidation. The fixed executor above
    // remains the sole snapshot/action authority, including PipeWire's defaults.
    // Unload observers when closed; no periodic timer or extra daemon is used.
    Loader {
        id: nativeWatchers
        objectName: "centerNativeWatchers"
        active: backend.opened && !backend.testing
        sourceComponent: Item {
            id: observers
            property string wifiConnectionName: ""
            readonly property string bluetoothConnectionName: BluezQt.Manager.operational && BluezQt.Manager.connectedDevices.length > 0 ? String(BluezQt.Manager.connectedDevices[0].name).slice(0, 128) : ""
            function updateWirelessName() {
                const value = activeWireless.count > 0 ? activeWireless.data(activeWireless.index(0, 0), PlasmaNM.NetworkModel.NameRole) : "";
                wifiConnectionName = typeof value === "string" ? value.slice(0, 128) : "";
            }
            PlasmaNM.NetworkModel { id: nativeNetworks }
            KItemModels.KSortFilterProxyModel {
                id: activeWireless
                sourceModel: nativeNetworks
                filterRoleName: "ConnectionState"
                filterRowCallback: (row, parent) => {
                    const index = nativeNetworks.index(row, 0, parent);
                    return nativeNetworks.data(index, PlasmaNM.NetworkModel.ConnectionStateRole) === PlasmaNM.Enums.Activated
                        && nativeNetworks.data(index, PlasmaNM.NetworkModel.TypeRole) === PlasmaNM.Enums.Wireless;
                }
                onCountChanged: observers.updateWirelessName()
            }
            Connections { target: activeWireless; function onDataChanged() { observers.updateWirelessName(); } }
            Component.onCompleted: updateWirelessName()
            PlasmaNM.EnabledConnections {
                onWirelessEnabled: backend.scheduleRefresh()
                onWirelessHwEnabled: backend.scheduleRefresh()
                onNetworkingEnabled: backend.scheduleRefresh()
            }
            PlasmaNM.AvailableDevices { onWirelessDeviceAvailableChanged: backend.scheduleRefresh() }
            PlasmaNM.NetworkStatus {
                onActiveConnectionsChanged: backend.scheduleRefresh()
                onConnectivityChanged: backend.scheduleRefresh()
            }
            Connections {
                target: BluezQt.Manager
                function onOperationalChanged() { backend.scheduleRefresh(); }
                function onBluetoothOperationalChanged() { backend.scheduleRefresh(); }
                function onBluetoothBlockedChanged() { backend.scheduleRefresh(); }
                function onUsableAdapterChanged() { backend.scheduleRefresh(); }
                function onAdaptersChanged() { backend.scheduleRefresh(); }
            }
            Connections { target: BluezQt.Manager.usableAdapter; function onPoweredChanged() { backend.scheduleRefresh(); } }
            Connections {
                target: NotificationManager.Server
                function onValidChanged() { backend.scheduleRefresh(); }
                function onInhibitedChanged() { backend.scheduleRefresh(); }
            }
            Audio.SinkModel { id: sinks }
            Audio.SourceModel { id: sources }
            Connections {
                target: sinks
                function onDataChanged() { backend.scheduleRefresh(); }
                function onModelReset() { backend.scheduleRefresh(); }
                function onRowsInserted() { backend.scheduleRefresh(); }
                function onRowsRemoved() { backend.scheduleRefresh(); }
            }
            Connections {
                target: sources
                function onDataChanged() { backend.scheduleRefresh(); }
                function onModelReset() { backend.scheduleRefresh(); }
                function onRowsInserted() { backend.scheduleRefresh(); }
                function onRowsRemoved() { backend.scheduleRefresh(); }
            }
            Connections { target: Audio.Context; function onStateChanged() { backend.scheduleRefresh(); } }
            Brightness.ScreenBrightnessControl {
                id: screenBrightness
                onIsBrightnessAvailableChanged: backend.scheduleRefresh()
            }
            Connections {
                target: screenBrightness.displays
                function onDataChanged() { backend.scheduleRefresh(); }
                function onModelReset() { backend.scheduleRefresh(); }
                function onRowsInserted() { backend.scheduleRefresh(); }
                function onRowsMoved() { backend.scheduleRefresh(); }
                function onRowsRemoved() { backend.scheduleRefresh(); }
            }
            DBus.Properties {
                busType: DBus.BusType.Session
                service: "org.kde.KWin.NightLight"
                path: "/org/kde/KWin/NightLight"
                iface: "org.kde.KWin.NightLight"
                onPropertiesChanged: (interfaceName, changed, invalidated) => {
                    // Temperature animation is not a request to rerun device probes.
                    if (["available", "enabled", "running", "inhibited"].some(key => changed[key] !== undefined || invalidated.indexOf(key) >= 0)) backend.scheduleRefresh();
                }
                onRefreshed: backend.scheduleRefresh()
            }
            DBus.DBusServiceWatcher {
                busType: DBus.BusType.Session
                watchedService: "org.kde.KWin.NightLight"
                onRegisteredChanged: backend.scheduleRefresh()
            }
        }
    }
    P5Support.DataSource {
        engine: "powermanagement"
        connectedSources: backend.testing ? [] : ["Battery", "AC Adapter"]
        onNewData: (source, data) => {
            if (source === "Battery") backend.batteryPercent = typeof data.Percent === "number" && data.Percent >= 0 && data.Percent <= 100 ? data.Percent : null;
            if (source === "AC Adapter") backend.pluggedIn = typeof data["Plugged in"] === "boolean" ? data["Plugged in"] : null;
        }
    }
    P5Support.DataSource {
        id: executor
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName, data) => backend.finish(sourceName, data)
    }
}
