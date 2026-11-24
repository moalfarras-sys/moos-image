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
    property string owner: ""
    property int ownerRevision: 0
    property int stateRevision: 0

    function stringValue(value) {
        // KDE wraps strings from both method replies and signals in DBus.STRING.
        if (typeof value === "string") return value;
        return typeof value?.value === "string" ? value.value : "";
    }

    function receive(rawValue) {
        const value = stringValue(rawValue);
        if (!livePhases.includes(value) && !["idle", "off", "error"].includes(value)) return;
        ++stateRevision;
        phase = value;
        if (!active) {
            stopping = false;
            if (result === "stopUnconfirmed") result = "";
        } else if (result !== "stopUnconfirmed") {
            result = "";
        }
    }

    function resolveOwner(accept, reject) {
        const generation = ownerRevision;
        DBus.SessionBus.asyncCall({
            service: "org.freedesktop.DBus", path: "/org/freedesktop/DBus",
            iface: "org.freedesktop.DBus", member: "GetNameOwner",
            signature: "(s)", arguments: [link.service]
        }, reply => {
            if (generation !== link.ownerRevision) return;
            const name = link.stringValue(reply.value);
            if (name.startsWith(":")) {
                link.owner = name;
                accept(name);
            } else {
                reject();
            }
        }, _error => { if (generation === link.ownerRevision) reject(); });
    }

    function refresh() {
        if (!watcher.registered) return;
        const revision = ++stateRevision;
        // An observation must never activate a service which has quit.
        resolveOwner(name => {
            if (revision !== link.stateRevision) return;
            DBus.SessionBus.asyncCall({
                service: name, path: link.objectPath, iface: link.service, member: "IslandVoiceState"
            }, state => {
                if (revision === link.stateRevision && name === link.owner) link.receive(state.value);
            }, _error => {});
        }, () => {});
    }

    function request() {
        if (pending || stopping) return;
        const stop = active;
        const generation = ownerRevision;
        pending = stop ? "stop" : "start";
        result = "";

        const failed = () => {
            if (generation !== link.ownerRevision) return;
            link.pending = "";
            link.result = stop ? "stopUnconfirmed" : "unavailable";
            link.refresh();
        };
        const send = name => {
            if (stop && !link.active) {
                link.pending = "";
                return;
            }
            DBus.SessionBus.asyncCall({
                service: name, path: link.objectPath, iface: link.service,
                member: stop ? "IslandStop" : "IslandTalk"
            }, reply => {
                if (generation !== link.ownerRevision) return;
                link.pending = "";
                const outcome = link.stringValue(reply.value);
                if (outcome === "ok") {
                    link.stopping = stop && link.active;
                } else if (stop && outcome !== "idle") {
                    link.result = "stopUnconfirmed";
                } else {
                    link.result = ["setup", "off", "busy", "refused", "idle"].includes(outcome)
                        ? outcome : "failed";
                }
                link.refresh();
            }, failed);
        };
        // A phase signal can reach the panel before the passive lookup finishes.
        // Deliver an immediate stop to that running owner, without activating Mira.
        if (stop && !owner) resolveOwner(send, failed);
        else send(owner || service);
    }

    Timer {
        // The command returning does not mean the audio route has finished.
        // Preserve the measured phase and offer another stop if there is no receipt.
        interval: 5000
        running: link.stopping
        onTriggered: {
            link.stopping = false;
            link.result = "stopUnconfirmed";
            link.refresh();
        }
    }

    DBus.DBusServiceWatcher {
        id: watcher
        busType: DBus.BusType.Session
        watchedService: link.service
        onRegisteredChanged: {
            if (registered) {
                link.refresh();
            } else {
                ++link.ownerRevision;
                const interrupted = link.active || link.pending.length > 0;
                link.owner = "";
                link.pending = "";
                link.receive("idle");
                link.result = interrupted ? "unavailable" : "";
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
    Component.onCompleted: if (stateRevision === 0) refresh()
}
