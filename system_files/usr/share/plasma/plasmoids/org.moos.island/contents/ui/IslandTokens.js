// MoOS Island presence tokens: state carried in FILE NAMES, parsed without reading a file.
//
// plasmashell may not read a local file through XMLHttpRequest (Qt 6 refuses it unless
// QML_XHR_ALLOW_FILE_READ=1, which the shell does not and should not export). A FolderListModel
// reports file names, so every producer writes its state INTO the name:
//
//   mo-remote/presence-<active|paused>-<sessions>                 Mo PC Remote (since rev 52)
//   moos-store/job-<action>-<state>-<progress|x>-<id>             moos-storectl
//   moos-privacy/active-<screen|camera|mic>-<node>[-<app>]        moos-privacy-monitor
//
// <id> and <app> are percent-encoded with "-" written as %2D, so "-" only ever separates fields.
// Pure functions, no Qt: tests/test_island_tokens.py runs this file in node.
.pragma library

var STORE_ACTIONS = ["install", "remove", "update"];
var STORE_STATES = ["starting", "running", "success", "failed", "cancelled"];
var PRIVACY_TYPES = ["screen", "camera", "mic"];

function decodeField(text) {
    try { return decodeURIComponent(String(text || "")); }
    catch (error) { return ""; }
}

// A person's name for an app id. The job document carries ids only, and "Org.mozilla.firefox"
// (what W5 showed) is not a name.
function displayName(id) {
    var value = String(id || "").trim();
    if (!value) { return ""; }
    var parts = value.split(".").filter(function (part) { return part.length > 0; });
    var generic = ["desktop", "app", "client", "application", "gui", "linux"];
    var name = parts.length ? parts[parts.length - 1] : value;
    if (parts.length > 2 && generic.indexOf(name.toLowerCase()) !== -1) {
        name = parts[parts.length - 2];
    }
    name = name.replace(/[_-]+/g, " ").trim();
    if (!name) { return ""; }
    // Keep a publisher's own capitals (LibreOffice, GIMP); only lift an all-lowercase word.
    if (name === name.toLowerCase()) {
        name = name.split(" ").map(function (word) {
            return word.charAt(0).toUpperCase() + word.slice(1);
        }).join(" ");
    }
    return name;
}

// -> null, or { action, state, progress (0-100 | null), id, name, active, finished }
function parseStoreToken(fileName) {
    var match = /^job-([a-z]+)-([a-z]+)-(x|[0-9]{1,3})-(.*)$/.exec(String(fileName || ""));
    if (!match) { return null; }
    if (STORE_ACTIONS.indexOf(match[1]) === -1 || STORE_STATES.indexOf(match[2]) === -1) {
        return null;
    }
    var progress = match[3] === "x" ? null : Math.max(0, Math.min(100, Number(match[3])));
    var id = decodeField(match[4]);
    return {
        action: match[1],
        state: match[2],
        progress: progress,
        id: id,
        name: displayName(id),
        active: match[2] === "starting" || match[2] === "running",
        finished: match[2] === "success" || match[2] === "failed" || match[2] === "cancelled"
    };
}

// Several tokens can coexist for an instant (the producer creates the new name before it removes
// the old one). An active job outranks a finished one; among equals the later state wins.
function chooseStoreToken(fileNames) {
    var best = null;
    var rank = { starting: 1, running: 2, cancelled: 3, failed: 4, success: 5 };
    for (var index = 0; index < fileNames.length; ++index) {
        var job = parseStoreToken(fileNames[index]);
        if (!job) { continue; }
        if (!best
                || (job.active && !best.active)
                || (job.active === best.active && rank[job.state] > rank[best.state])
                || (job.active === best.active && job.state === best.state
                    && (job.progress || 0) > (best.progress || 0))) {
            best = job;
        }
    }
    return best;
}

// -> null, or { type, nodeId, app }   (app is "" when the producer could not name it)
function parsePrivacyToken(fileName) {
    var match = /^active-([a-z]+)-([0-9A-Za-z]+)(?:-(.*))?$/.exec(String(fileName || ""));
    if (!match || PRIVACY_TYPES.indexOf(match[1]) === -1) { return null; }
    return { type: match[1], nodeId: match[2], app: decodeField(match[3] || "") };
}

// Screen sharing outranks the camera, which outranks the microphone: the most exposing first.
function choosePrivacyToken(fileNames) {
    var order = { screen: 3, camera: 2, mic: 1 };
    var best = null;
    for (var index = 0; index < fileNames.length; ++index) {
        var stream = parsePrivacyToken(fileNames[index]);
        if (stream && (!best || order[stream.type] > order[best.type])) { best = stream; }
    }
    return best;
}
