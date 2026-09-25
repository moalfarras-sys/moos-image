// MoOS Island presence tokens: state carried in FILE NAMES, parsed without reading a file.
//
// plasmashell may not read a local file through XMLHttpRequest (Qt 6 refuses it unless
// QML_XHR_ALLOW_FILE_READ=1, which the shell does not and should not export). A FolderListModel
// reports file names, so every producer writes its state INTO the name:
//
//   mo-remote/presence-<active|paused>-<sessions>                 Mo PC Remote (since rev 52)
//   moos-store/job-<action>-<state>-<progress|x>-<id>             moos-storectl
//   moos-privacy/active-<screen|camera|mic>-<node>[-<app>]        moos-privacy-monitor
//   moai-jobs/job-<id8hex>-<running|done|failed>-<tool>           moai-control (rev 86)
//
// A producer RENAMES a token as its state changes. A same-count rename changes no count: Qt 6.11's
// FolderListModel reports it as dataChanged plus a Loading -> Ready status cycle (measured
// 2026-09-24), so every Island model syncs on count, data AND status.
//
// <id> and <app> are percent-encoded with "-" written as %2D, so "-" only ever separates fields.
// Pure functions, no Qt: tests/test_island_tokens.py runs this file in node.
.pragma library

var STORE_ACTIONS = ["install", "remove", "update"];
var STORE_STATES = ["starting", "running", "success", "failed", "cancelled"];
var PRIVACY_TYPES = ["screen", "camera", "mic"];
var MOAI_JOB_STATES = ["running", "done", "failed"];
// How long an ENDED Mo AI job is news. moai-control stamps a token's mtime when it enters its
// state and removes done/failed tokens after the same 20 s (JOB_TOKEN_LINGER); a producer that
// stops first leaves them behind. Running tokens have no age limit.
var MOAI_JOB_LINGER_MS = 20000;

// What a confirmed Mo AI job is DOING, in the person's words. The token carries the tool id only
// (never arguments or secrets); ids come from moai_tool_schemas.py and
// tests/test_island_tokens.py fails when a confirmed tool has no words here.
var MOAI_JOB_LABELS = {
    install_app: ["تثبيت تطبيق", "Installing an app"],
    uninstall_app: ["إزالة تطبيق", "Removing an app"],
    update_apps: ["تحديث التطبيقات", "Updating apps"],
    system_update: ["تحديث MoOS", "Updating MoOS"],
    update_firmware: ["تحديث البرامج الثابتة", "Updating firmware"],
    system_rollback: ["استعادة النظام السابق", "Restoring the previous system"],
    fix_audio: ["إصلاح الصوت", "Repairing sound"],
    optimize_system: ["تحسين النظام", "Optimizing the system"],
    install_nvidia: ["تثبيت تعريف الرسوميات", "Installing the graphics driver"],
    setup_gaming: ["تجهيز الألعاب", "Setting up gaming"],
    setup_windows: ["تجهيز تطبيقات ويندوز", "Setting up Windows apps"],
    setup_waydroid: ["تجهيز تطبيقات أندرويد", "Setting up Android apps"],
    remote_anywhere: ["تجهيز الوصول عن بُعد", "Setting up remote access"]
};

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

// -> null, or { id, state, tool, active, finished }
// `id` is eight lowercase hex digits and `tool` is [a-z_]{1,40}: nothing a person typed, and
// nothing a hostile name can smuggle into another field.
function parseMoaiJobToken(fileName) {
    var match = /^job-([0-9a-f]{8})-([a-z]+)-([a-z_]{1,40})$/.exec(String(fileName || ""));
    if (!match || MOAI_JOB_STATES.indexOf(match[2]) === -1) { return null; }
    return {
        id: match[1],
        state: match[2],
        tool: match[3],
        active: match[2] === "running",
        finished: match[2] !== "running"
    };
}

// The job the Island shows, plus how many are still running and which ones.
//
// `watchedIds` is the `runningIds` of the caller's PREVIOUS call: the jobs the Island saw running
// a moment ago. A running job always outranks a finished one (ties resolve by id, so every render
// of the same directory agrees). A FINISHED token is shown only when its job is one of those
// watched ids: the directory also holds tokens of jobs that ended earlier (they linger for 20 s,
// and a producer that dies leaves them for good), and choosing among ALL finished tokens once
// said "Repairing sound — failed" about a retry that had just succeeded. Among watched jobs that
// ended together, a failure outranks a success: it is the one that needs the person.
//
// -> null, or { id, state, tool, active, finished, running, runningIds }
// null means nothing is running and no watched job ended, so the caller watches nothing next.
function chooseMoaiJobToken(fileNames, watchedIds) {
    var watched = Array.isArray(watchedIds) ? watchedIds : [];
    var best = null;
    var runningIds = [];
    var rank = { done: 1, failed: 2, running: 3 };
    for (var index = 0; index < fileNames.length; ++index) {
        var job = parseMoaiJobToken(fileNames[index]);
        if (!job) { continue; }
        if (job.active) {
            if (runningIds.indexOf(job.id) === -1) { runningIds.push(job.id); }
        } else if (watched.indexOf(job.id) === -1) {
            continue;                   // it ended before this Island watched it run
        }
        if (!best || rank[job.state] > rank[best.state]
                || (rank[job.state] === rank[best.state] && job.id > best.id)) {
            best = job;
        }
    }
    if (best) {
        runningIds.sort();
        best.running = runningIds.length;
        best.runningIds = runningIds;
    }
    return best;
}

// The names chooseMoaiJobToken may consider, from the model's { name, modified } rows.
//
// `modified` is FolderListModel's fileModified (a Date, or milliseconds): the moment the token
// entered its state. A done or failed token older than MOAI_JOB_LINGER_MS is dropped — it is not
// news any more, whatever a late sync says — and so is one whose age cannot be read. A running
// token is always kept: a long job is still running however long ago it started.
function recentMoaiJobNames(entries, nowMs) {
    var names = [];
    var list = Array.isArray(entries) ? entries : [];
    for (var index = 0; index < list.length; ++index) {
        var entry = list[index] || {};
        var name = String(entry.name || "");
        var job = parseMoaiJobToken(name);
        if (!job) { continue; }
        if (job.finished) {
            var modified = entry.modified instanceof Date ? entry.modified.getTime()
                                                          : Number(entry.modified);
            if (!isFinite(modified) || modified <= 0
                    || Number(nowMs) - modified > MOAI_JOB_LINGER_MS) {
                continue;
            }
        }
        names.push(name);
    }
    return names;
}

// [arabic, english] for a tool id; a tool without words gets a generic, honest label.
function moaiJobLabel(tool) {
    var label = Object.prototype.hasOwnProperty.call(MOAI_JOB_LABELS, tool)
        ? MOAI_JOB_LABELS[tool] : null;
    return label ? label.slice() : ["إجراء من Mo AI", "A Mo AI action"];
}
