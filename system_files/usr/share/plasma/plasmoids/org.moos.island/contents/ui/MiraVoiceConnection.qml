import QtQuick
import org.kde.plasma.workspace.dbus as DBus

Item {
    id: link
    visible: false

    readonly property string service: "org.moos.Mira"
    readonly property string objectPath: "/Mira"
    readonly property var livePhases: ["activating", "listening", "thinking", "executing", "speaking"]
    readonly property bool active: livePhases.includes(phase)

    property string phase: "idle"
    property string result: ""
    property string pending: ""
    property bool stopping: false
    property int stateRevision: 0

    function stringValue(value) {
        // KDE wraps a D-Bus string as DBus.STRING. The wrapped value,
        // not the wrapper's truthiness, carries the phase or outcome.
        if (typeof value === "string") return value;
        return typeof value?.value === "string" ? value.value : "";
    }

    function receive(rawValue) {
        const value = stringValue(rawValue);
        ++stateRevision;
        phase = livePhases.includes(value) || ["idle", "off", "error"].includes(value)
            ? value : "idle";
        if (!active) stopping = false;
        if (active) result = "";
    }

    function refresh() {
        if (!watcher.registered) return;
        const revision = ++stateRevision;
        // Resolve a unique name before reading. A status read must never
        // reactivate a service that quit after the watcher reported it.
        DBus.SessionBus.asyncCall({
            service: "org.freedesktop.DBus", path: "/org/freedesktop/DBus",
            iface: "org.freedesktop.DBus", member: "GetNameOwner",
            signature: "s", arguments: [link.service]
        }, owner => {
            const name = link.stringValue(owner.value);
            if (revision !== link.stateRevision || !watcher.registered || !name.startsWith(":")) return;
            DBus.SessionBus.asyncCall({
                service: name, path: link.objectPath, iface: link.service, member: "IslandVoiceState"
            }, reply => {
                if (revision === link.stateRevision && watcher.registered) link.receive(reply.value);
            }, _error => {});
        }, _error => {});
    }

    function request() {
        if (pending || stopping) return;
        const stop = active;
        pending = stop ? "stop" : "start";
        result = "";
        DBus.SessionBus.asyncCall({
            service: link.service, path: link.objectPath, iface: link.service,
            member: stop ? "IslandStop" : "IslandTalk"
        }, reply => {
            link.pending = "";
            const outcome = link.stringValue(reply.value);
            if (outcome === "ok") {
                link.stopping = stop && link.active;
            } else {
                link.result = ["setup", "off", "busy", "refused", "idle"].includes(outcome)
                    ? outcome : "failed";
            }
            link.refresh();
        }, _error => {
            link.pending = "";
            link.result = "unavailable";
        });
    }

    DBus.DBusServiceWatcher {
        id: watcher
        busType: DBus.BusType.Session
        watchedService: link.service
        onRegisteredChanged: {
            if (registered) {
                link.refresh();
            } else {
                link.receive("idle");
                if (link.pending) link.result = "unavailable";
            }
        }
    }
    DBus.SignalWatcher {
        busType: DBus.BusType.Session
        service: link.service
        path: link.objectPath
        iface: link.service
        function dbusIslandVoiceChanged(phase) { link.receive(phase); }
    }
    Component.onCompleted: refresh()
}
