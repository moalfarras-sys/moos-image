// SPDX-License-Identifier: GPL-2.0-or-later
// Reuse the fixed MoOS executor. No QML command, model text or device name reaches a shell.
import QtQuick
import org.kde.plasma.plasma5support as P5Support
import org.moos.ui as MoUI

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
    property string errorText: ""
    property string pendingField: ""
    property var pendingValue: null
    property string currentCommand: ""
    readonly property string prefix: "timeout --kill-after=2s 18 /usr/bin/moos-control "
    readonly property string statusCommand: prefix + "status"
    onOpenedChanged: if (opened) refresh()
    function refresh() {
        if (busy) return;
        errorText = "";
        busy = true;
        execute(statusCommand);
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
            state = snapshot;
            ready = true;
        } catch (error) {
            ready = false;
            errorText = MoUI.Locale.local("حالة الأجهزة غير متاحة الآن.", "Device status is unavailable right now.");
        }
        pendingField = "";
        busy = false;
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
