// MoOS Context Island — one stable place for search and live activity.
//
// This is a direct panel zone immediately after the MoOS launcher, not a second
// media service and not a tray icon. Plasma's Mpris2Model remains the single
// source of truth and chooses the active player, including browsers that expose
// MPRIS through Media Session. The Island always occupies one medium, fixed
// slot: Search owns it at rest; Remote, privacy, Store, Mo AI jobs and media
// replace the contents without moving a single neighbouring task icon.
//
// Motion is contextual only: content cross-fades and settles inside fixed
// geometry, while the progress timer runs only when media is playing and
// somebody can see the position. No decorative timer or permanent compositor
// repaint loop is allowed here.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtCore
import Qt.labs.folderlistmodel
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PC3
import org.kde.plasma.extras as PlasmaExtras
import org.kde.milou as Milou
import org.kde.plasma.private.kicker as Kicker
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.mpris as Mpris
import org.moos.ui as MoUI
import "IslandTokens.js" as IslandTokens
// SearchView.qml and SearchAnswers.js live in THIS package. They used to be
// imported from the retired org.moos.search applet by a relative path across
// packages, which broke whenever one package was shadowed or updated without
// the other (THEME_REV 86).

PlasmoidItem {
    id: root

    readonly property var design: MoUI.Tokens
    readonly property bool rtl: MoUI.Locale.rtl
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property string uiFontFamily: Qt.application.font.family
    readonly property int searchSurfaceUnits: 24
    readonly property int searchBottomInset: root.design.targetComfortable
    readonly property int motionFast: design.duration(
        root.motionEnabled, design.motionFast)
    readonly property int motionGeometry: design.duration(
        root.motionEnabled, design.motionGeometry)

    function local(arabic, english) { return root.rtl ? arabic : english; }
    function fast() { return root.design.duration(root.motionEnabled, root.design.motionFast); }
    function bounded(value, low, high) {
        return Math.max(low, Math.min(high, value));
    }
    function twoDigits(value) {
        return value < 10 ? "0" + value : String(value);
    }
    function resolvedPlayerIcon() {
        if (!root.hasPlayer) { return "applications-multimedia-symbolic"; }
        if (root.desktopEntry.length > 0) {
            // MoOS's own apps publish `org.moos.<app>` as their desktop entry and
            // ship their icon under the MoOS icon theme as `moos-<app>`, so the
            // entry name on its own resolves to nothing and the capsule drew the
            // "unknown file" sheet beside a working player.
            if (root.desktopEntry.indexOf("org.moos.") === 0) {
                return "moos-" + root.desktopEntry.substring(9);
            }
            return root.desktopEntry;
        }

        // Browsers commonly publish Identity but omit DesktopEntry, while a
        // Flatpak artUrl can point into its private /tmp namespace. Resolve
        // only known identities to existing theme icons; never invent another
        // player registry or use the title as an executable/application id.
        const source = root.identity.toLowerCase();
        if (source.indexOf("chromium") >= 0) { return "chromium"; }
        if (source.indexOf("chrome") >= 0) { return "chrome"; }
        if (source.indexOf("firefox") >= 0) { return "firefox"; }
        if (source.indexOf("spotify") >= 0) { return "spotify"; }
        if (source.indexOf("vlc") >= 0) { return "vlc"; }
        if (source.indexOf("mpv") >= 0) { return "mpv"; }
        if (source.indexOf("moplayer") >= 0
                || source.indexOf("mo player") >= 0) {
            return "org.moos.moplayer";
        }
        const advertised = String(root.player.iconName || "");
        if (advertised.length > 0) { return advertised; }
        return "applications-multimedia-symbolic";
    }
    function resolvedArtworkSource() {
        const raw = root.artUrl;
        if (raw.indexOf("file:///tmp/.") !== 0) { return raw; }

        // Flatpak gives each app a private /tmp, but MPRIS publishes the URL as
        // if it were the host's /tmp. The same-user file is actually visible to
        // plasmashell below RuntimeLocation/.flatpak/<app-id>/tmp. Chromium's
        // Media Session uses .<reverse-dns-app-id>.<random-token> basenames, so
        // derive the namespace from that safe basename instead of maintaining
        // a second player/browser registry. Never carry a slash from MPRIS into
        // the translated path.
        const basename = raw.substring(raw.lastIndexOf("/") + 1);
        const match = basename.match(
            /^\.([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){1,})\.[A-Za-z0-9_-]+$/);
        if (!match) { return raw; }
        const runtimeUrl = String(StandardPaths.writableLocation(
            StandardPaths.RuntimeLocation));
        if (runtimeUrl.length < 1) { return raw; }
        const runtime = runtimeUrl.indexOf("file:") === 0
            ? runtimeUrl : "file://" + runtimeUrl;
        return runtime + "/.flatpak/" + match[1] + "/tmp/"
            + basename;
    }
    function formatTime(microseconds) {
        const total = Math.max(0, Math.floor(Number(microseconds || 0) / 1000000));
        const hours = Math.floor(total / 3600);
        const minutes = Math.floor((total % 3600) / 60);
        const seconds = total % 60;
        if (hours > 0) {
            return hours + ":" + root.twoDigits(minutes)
                + ":" + root.twoDigits(seconds);
        }
        return minutes + ":" + root.twoDigits(seconds);
    }
    function togglePlaying() {
        if (!root.player) { return; }
        if (root.playing && root.canPause) { root.player.Pause(); }
        else if (root.canPlay) { root.player.Play(); }
        else if (root.canControl) { root.player.PlayPause(); }
    }
    function seekTo(value) {
        if (root.player && root.canSeek) {
            root.player.position = Math.round(root.bounded(value, 0, root.length));
        }
    }
    function setVolume(value) {
        if (root.player && root.hasVolume) {
            root.player.volume = root.bounded(value, 0, 1.5);
        }
    }
    function toggleMuted() {
        if (!root.hasVolume) { return; }
        if (root.volume > 0.01) {
            root.lastAudibleVolume = root.volume;
            root.setVolume(0);
        } else {
            root.setVolume(Math.max(0.35, root.lastAudibleVolume));
        }
    }

    function runtimeFileUrl(path) {
        const runtime = String(StandardPaths.writableLocation(
            StandardPaths.RuntimeLocation));
        const base = runtime.indexOf("file:") === 0
            ? runtime : "file://" + runtime;
        return base + "/" + path;
    }
    function syncRemotePresence() {
        let mode = "idle";
        let sessions = 0;
        for (let index = 0; index < remotePresence.count; ++index) {
            const name = String(remotePresence.get(index, "fileName") || "");
            const match = name.match(/^presence-(active|paused)-([1-9][0-9]*)$/);
            if (!match) { continue; }
            const count = Number(match[2]);
            if (count > sessions || (count === sessions && match[1] === "paused")) {
                mode = match[1];
                sessions = count;
            }
        }
        root.remoteMode = mode;
        root.remoteSessions = sessions;
    }

    property string remoteMode: "idle"
    property int remoteSessions: 0
    readonly property bool remotePresent: root.remoteSessions > 0
        && (root.remoteMode === "active" || root.remoteMode === "paused")
    readonly property string remoteTitle: root.remoteMode === "paused"
        ? root.local("التحكم عن بُعد متوقف مؤقتًا", "Remote control paused")
        : root.local("التحكم عن بُعد نشط", "Remote control active")
    readonly property string remoteSource: root.remoteSessions === 1
        ? root.local("جهاز واحد متصل", "1 device connected")
        : root.local(root.remoteSessions + " أجهزة متصلة",
                     root.remoteSessions + " devices connected")

    FolderListModel {
        id: remotePresence
        folder: root.runtimeFileUrl("mo-remote")
        nameFilters: ["presence-active-*", "presence-paused-*"]
        showDirs: false
        sortField: FolderListModel.Name
        onCountChanged: root.syncRemotePresence()
        onDataChanged: root.syncRemotePresence()
        onStatusChanged: if (status === FolderListModel.Ready) {
            root.syncRemotePresence();
        }
    }

    // ── Privacy Presence (Camera, Microphone, Screen Share) ─────────────────────────
    FolderListModel {
        id: privacyPresence
        folder: root.runtimeFileUrl("moos-privacy")
        nameFilters: ["active-screen-*", "active-camera-*", "active-mic-*"]
        showDirs: false
        sortField: FolderListModel.Name
        onCountChanged: root.syncPrivacyPresence()
        onDataChanged: root.syncPrivacyPresence()
        onStatusChanged: if (status === FolderListModel.Ready) {
            root.syncPrivacyPresence();
        }
    }

    property bool privacyPresent: false
    property string privacyType: "screen"
    property string privacyApp: ""
    property string privacyNodeId: ""
    property string privacyTitle: ""
    property string privacySource: ""
    property string privacyIcon: "moos-cast-symbolic"

    // State arrives in the token NAME (see IslandTokens.js). W5 read the token's JSON body through
    // XMLHttpRequest, which plasmashell's Qt refuses, so the chip always said "Application" — and
    // named Mo PC Remote as the owner of EVERY screen share, including a browser meeting.
    function syncPrivacyPresence() {
        const names = [];
        for (let i = 0; i < privacyPresence.count; ++i) {
            names.push(String(privacyPresence.get(i, "fileName") || ""));
        }
        const stream = IslandTokens.choosePrivacyToken(names);
        root.privacyPresent = stream !== null;
        if (!stream) { return; }

        root.privacyType = stream.type;
        root.privacyNodeId = stream.nodeId;
        root.privacyApp = stream.app || root.local("تطبيق", "An app");
        const stopHint = root.local(root.privacyApp + " · انقر للإيقاف", root.privacyApp + " · Tap to stop");
        if (stream.type === "screen") {
            root.privacyIcon = "moos-cast-symbolic";
            root.privacyTitle = root.local("مشاركة الشاشة نشطة", "Screen sharing active");
        } else if (stream.type === "camera") {
            root.privacyIcon = "moos-camera-symbolic";
            root.privacyTitle = root.local("الكاميرا قيد الاستخدام", "Camera in use");
        } else {
            root.privacyIcon = "moos-microphone-symbolic";
            root.privacyTitle = root.local("الميكروفون قيد الاستخدام", "Microphone in use");
        }
        root.privacySource = stopHint;
    }

    // ── Store Job Presence (installs, removals, updates) ───────────────────────────
    // moos-storectl publishes `job-<action>-<state>-<progress>-<id>` in the runtime directory and
    // renames it as the job advances, so the model's own change signals ARE the progress feed: no
    // polling timer and no file read. `run`, `refresh-index` and `open-engine` are never published;
    // W5 showed each of them as "Installing …", and showed a removal as an install because it
    // compared the action with "uninstall" while the backend says "remove".
    FolderListModel {
        id: storeJobPresence
        folder: root.runtimeFileUrl("moos-store")
        nameFilters: ["job-*"]
        showDirs: false
        sortField: FolderListModel.Name
        onCountChanged: root.syncStoreJob()
        onDataChanged: root.syncStoreJob()
        onStatusChanged: if (status === FolderListModel.Ready) {
            root.syncStoreJob();
        }
    }

    property bool storeJobPresent: false
    property bool storeJobActive: false
    property string storeJobAction: "install"
    property real storeJobProgress: 0
    property string storeJobCurrentId: ""
    property string storeJobMessage: ""
    property string storeJobTitle: ""
    property string storeJobSource: ""
    property string storeJobIcon: "moos-install-symbolic"

    Timer {
        id: storeJobFinishTimer
        interval: 3500
        repeat: false
        onTriggered: {
            root.storeJobPresent = false;
        }
    }

    function storeJobVerb(action, name) {
        if (action === "update") {
            return name ? root.local("تحديث " + name, "Updating " + name)
                        : root.local("تحديث التطبيقات", "Updating apps");
        }
        if (action === "remove") {
            return name ? root.local("إزالة " + name, "Removing " + name)
                        : root.local("إزالة تطبيق", "Removing an app");
        }
        return name ? root.local("تثبيت " + name, "Installing " + name)
                    : root.local("تثبيت التطبيقات", "Installing apps");
    }

    function syncStoreJob() {
        const names = [];
        for (let i = 0; i < storeJobPresence.count; ++i) {
            names.push(String(storeJobPresence.get(i, "fileName") || ""));
        }
        const job = IslandTokens.chooseStoreToken(names);
        if (!job) {
            root.storeJobActive = false;
            if (!storeJobFinishTimer.running) { root.storeJobPresent = false; }
            return;
        }

        root.storeJobAction = job.action;
        root.storeJobCurrentId = job.id;
        root.storeJobIcon = job.action === "update" ? "moos-safe-update-symbolic" : "moos-install-symbolic";
        const verb = root.storeJobVerb(job.action, job.name);

        if (job.active) {
            root.storeJobActive = true;
            root.storeJobPresent = true;
            storeJobFinishTimer.stop();
            root.storeJobProgress = job.progress === null ? 0 : job.progress;
            root.storeJobTitle = verb;
            root.storeJobMessage = job.progress === null
                ? root.local("جارٍ العمل", "Working")
                : root.local("جارٍ التنزيل والتثبيت", "Downloading and installing");
            root.storeJobSource = job.progress === null
                ? root.storeJobMessage
                : (job.progress + "% · " + root.storeJobMessage);
            return;
        }
        // A finished token is shown only as the END of a job this session watched run: a token
        // left in the runtime directory must not announce "complete" again when the shell restarts.
        if (!root.storeJobActive) { return; }
        root.storeJobActive = false;
        if (job.state === "success") {
            root.storeJobProgress = 100;
            root.storeJobTitle = root.local("اكتمل: " + verb, verb + " — done");
            root.storeJobSource = root.local("تم بنجاح", "Completed");
        } else if (job.state === "cancelled") {
            root.storeJobTitle = root.local("أُلغي: " + verb, verb + " — cancelled");
            root.storeJobSource = root.local("لم يتغيّر شيء", "Nothing was changed");
        } else {
            root.storeJobTitle = root.local("تعذّر: " + verb, verb + " — failed");
            root.storeJobSource = root.local("افتح Mo Store لمعرفة السبب", "Open Mo Store to see why");
        }
        root.storeJobMessage = root.storeJobSource;
        storeJobFinishTimer.restart();
    }

    // ── Mo AI Job Presence (confirmed actions) ─────────────────────────────────────
    // moai-control publishes one token per confirmed job, `job-<id8hex>-<state>-<tool>`, in the
    // runtime directory and RENAMES it as the job runs, finishes or fails (done/failed tokens are
    // removed after 20 s, and one whose fileModified is older than that is ignored here: a producer
    // that stopped first leaves it behind). A rename changes no count, so this model — like the three above —
    // syncs on count, data and status (see IslandTokens.js). The name carries the tool id only — no arguments, no secrets — and the
    // chip opens Mo AI, where the person sees the steps. It ranks below Remote, privacy and the
    // Store: those are safety states or work the person started by hand.
    FolderListModel {
        id: moaiJobPresence
        folder: root.runtimeFileUrl("moai-jobs")
        nameFilters: ["job-*"]
        showDirs: false
        sortField: FolderListModel.Name
        onCountChanged: root.syncMoaiJob()
        onDataChanged: root.syncMoaiJob()
        onStatusChanged: if (status === FolderListModel.Ready) {
            root.syncMoaiJob();
        }
    }

    property bool moaiJobPresent: false
    property bool moaiJobActive: false
    // The ids this Island saw RUNNING at its last sync. Only one of them may be announced as done
    // or failed: the directory also holds tokens of jobs that ended earlier, and one of those must
    // never speak for the job that just ended (IslandTokens.chooseMoaiJobToken).
    property var moaiWatchedJobs: []
    property string moaiJobState: "running"
    property string moaiJobTitle: ""
    property string moaiJobCompact: ""
    property string moaiJobSource: ""
    readonly property string moaiJobIcon: "moos-ai-symbolic"

    Timer {
        id: moaiJobFinishTimer
        interval: 5000
        repeat: false
        onTriggered: {
            root.moaiJobPresent = false;
        }
    }

    function syncMoaiJob() {
        // Each token with the moment it entered its state (the producer stamps it). An ended
        // token older than the producer's 20 s linger is old news, even to a late sync.
        const entries = [];
        for (let i = 0; i < moaiJobPresence.count; ++i) {
            entries.push({ name: String(moaiJobPresence.get(i, "fileName") || ""),
                           modified: moaiJobPresence.get(i, "fileModified") });
        }
        const names = IslandTokens.recentMoaiJobNames(entries, Date.now());
        const job = IslandTokens.chooseMoaiJobToken(names, root.moaiWatchedJobs);
        root.moaiWatchedJobs = job ? job.runningIds : [];
        if (!job) {
            root.moaiJobActive = false;
            if (!moaiJobFinishTimer.running) { root.moaiJobPresent = false; }
            return;
        }
        const words = IslandTokens.moaiJobLabel(job.tool);
        const label = root.local(words[0], words[1]);
        root.moaiJobState = job.state;

        if (job.active) {
            root.moaiJobActive = true;
            root.moaiJobPresent = true;
            moaiJobFinishTimer.stop();
            root.moaiJobCompact = label;
            // Arabic leads with its own words and isolates the Latin name, so the
            // line keeps an RTL paragraph direction.
            root.moaiJobTitle = root.local(label + " · \u2068Mo AI\u2069", "Mo AI · " + label);
            root.moaiJobSource = job.running > 1
                ? root.local(job.running + " إجراءات قيد التنفيذ · افتح Mo AI",
                             job.running + " actions running · open Mo AI")
                : root.local("قيد التنفيذ · التفاصيل في Mo AI",
                             "Working · details in Mo AI");
            return;
        }
        // Like a Store job: a finished token is shown only as the END of a job this session
        // watched run, so a shell restart inside the producer's 20 s window stays quiet. The
        // library returns a finished job only from moaiWatchedJobs; this guard is the second
        // lock, so a re-reported directory can never announce the same end twice.
        if (!root.moaiJobActive) { return; }
        root.moaiJobActive = false;
        if (job.state === "done") {
            root.moaiJobCompact = root.local("اكتمل: " + label, label + " — done");
            root.moaiJobTitle = root.moaiJobCompact;
            root.moaiJobSource = root.local("تم بنجاح", "Completed");
        } else {
            root.moaiJobCompact = root.local("تعذّر: " + label, label + " — failed");
            root.moaiJobTitle = root.moaiJobCompact;
            root.moaiJobSource = root.local("افتح Mo AI لمعرفة السبب", "Open Mo AI to see why");
        }
        moaiJobFinishTimer.restart();
    }
    function openMoAI() {
        root.expanded = false;
        Qt.openUrlExternally("moos://app/moai");
    }

    // Mpris2Model deliberately owns active-player selection. Building another
    // registry here would disagree with Plasma and break browser Media Session.
    Mpris.Mpris2Model { id: players }

    readonly property var player: players.currentPlayer
    readonly property bool hasPlayer: root.player !== null
                                      && root.player !== undefined
    readonly property string track: root.hasPlayer
        ? String(root.player.track || "") : ""
    readonly property string artist: root.hasPlayer
        ? String(root.player.artist || "") : ""
    readonly property string album: root.hasPlayer
        ? String(root.player.album || "") : ""
    readonly property string artUrl: root.hasPlayer
        ? String(root.player.artUrl || "") : ""
    // Host-installed Chromium-family browsers publish the SAME dot-prefixed
    // /tmp basenames as their Flatpak builds, but for them the raw URL is the
    // readable one and the translated .flatpak path does not exist. QML cannot
    // stat a path, so the bridge is probe-driven: try the translation first
    // (the live-proven Flatpak path); when that image errors, fall back to the
    // raw MPRIS URL for this artwork. New artwork re-arms the bridge, so a
    // Flatpak player after a native one still gets the translated path.
    property bool artworkBridgeFailed: false
    onArtUrlChanged: root.artworkBridgeFailed = false
    readonly property string artworkSource: root.artworkBridgeFailed
        ? root.artUrl : root.resolvedArtworkSource()
    readonly property string identity: root.hasPlayer
        ? String(root.player.identity || "") : ""
    readonly property string desktopEntry: root.hasPlayer
        ? String(root.player.desktopEntry || "") : ""
    readonly property string playerIcon: root.resolvedPlayerIcon()
    readonly property string displayTrack: root.track.length > 0
        ? root.track : root.local("وسائط قيد التشغيل", "Media playback")
    readonly property string displaySource: root.identity.length > 0
        ? root.identity : (root.artist.length > 0 ? root.artist
            : (root.desktopEntry.length > 0 ? root.desktopEntry
                : root.local("الوسائط", "Media")))

    readonly property int playbackStatus: root.hasPlayer
        ? root.player.playbackStatus : Mpris.PlaybackStatus.Stopped
    readonly property bool playing:
        root.playbackStatus === Mpris.PlaybackStatus.Playing
    readonly property bool paused:
        root.playbackStatus === Mpris.PlaybackStatus.Paused
    readonly property bool canControl: root.hasPlayer && root.player.canControl
    readonly property bool canPlay: root.hasPlayer && root.player.canPlay
    readonly property bool canPause: root.hasPlayer && root.player.canPause
    readonly property bool canGoPrevious:
        root.hasPlayer && root.player.canGoPrevious
    readonly property bool canGoNext: root.hasPlayer && root.player.canGoNext
    readonly property bool canSeek: root.hasPlayer && root.player.canSeek
    readonly property real length: root.hasPlayer
        ? Math.max(0, Number(root.player.length || 0)) : 0
    readonly property real position: root.hasPlayer
        ? root.bounded(Number(root.player.position || 0), 0, root.length) : 0
    readonly property bool hasTimeline: root.length > 0
    readonly property real progress: root.hasTimeline
        ? root.bounded(root.position / root.length, 0, 1) : 0
    readonly property real volume: root.hasPlayer
        ? Number(root.player.volume) : -1
    readonly property bool hasVolume: root.hasPlayer
        && isFinite(root.volume) && root.volume >= 0
    property real lastAudibleVolume: 0.65
    property bool compactHovered: false
    property bool compactFocused: false
    readonly property bool compactInteractive: root.compactHovered || root.compactFocused
    property string query: ""
    property string queuedRun: ""
    property int queryRevision: 0

    onQueryChanged: {
        ++root.queryRevision;
        root.queuedRun = "";
    }

    Milou.ResultsModel {
        id: searchResults
        queryString: root.query
        limit: 30
        onQueryStringChangeRequested: (queryString, cursorPosition) => {
            root.query = queryString;
        }
        onQueryingChanged: root.runQueued()
    }

    Kicker.RecentUsageModel {
        id: searchRecentApps
        shownItems: Kicker.RecentUsageModel.OnlyApps
        ordering: 0
    }

    // Remote always owns the bar while it is connected. The popup can inspect
    // media too, without hiding the live sharing indicator or picking another
    // player outside Plasma's MPRIS authority.
    property string detailContext: "remote"
    readonly property bool multipleContexts: (root.remotePresent ? 1 : 0)
        + (root.privacyPresent ? 1 : 0)
        + (root.storeJobPresent ? 1 : 0)
        + (root.moaiJobPresent ? 1 : 0)
        + (root.mediaPresent ? 1 : 0) > 1
    readonly property bool showRemoteDetails: root.remotePresent
        && (root.detailContext === "remote" || (!root.mediaPresent && !root.privacyPresent && !root.storeJobPresent && !root.moaiJobPresent))
    readonly property bool showPrivacyDetails: root.privacyPresent
        && (root.detailContext === "privacy" || (!root.remotePresent && !root.storeJobPresent && !root.moaiJobPresent && !root.mediaPresent))
    readonly property bool showStoreDetails: root.storeJobPresent
        && (root.detailContext === "store" || (!root.remotePresent && !root.privacyPresent && !root.moaiJobPresent && !root.mediaPresent))
    readonly property bool showMoaiDetails: root.moaiJobPresent
        && (root.detailContext === "moai" || (!root.remotePresent && !root.privacyPresent && !root.storeJobPresent && !root.mediaPresent))
    readonly property bool showMediaDetails: root.mediaPresent
        && (root.detailContext === "media" || (!root.remotePresent && !root.privacyPresent && !root.storeJobPresent && !root.moaiJobPresent))
    function openDetails() {
        if (root.remotePresent) { root.detailContext = "remote"; }
        else if (root.privacyPresent) { root.detailContext = "privacy"; }
        else if (root.storeJobPresent) { root.detailContext = "store"; }
        else if (root.moaiJobPresent) { root.detailContext = "moai"; }
        else { root.detailContext = "media"; }
        root.expanded = true;
    }
    function openPrimary() {
        if (root.active) {
            root.openDetails();
        } else {
            // Search is the Island's idle face, so it opens HERE. Routing this
            // click through activateLauncherMenu made the applications page
            // appear even though the control says Search. The one MoOS Search
            // view lives in this package and runs Plasma's Milou models here.
            root.expanded = true;
        }
    }

    function openRecent(row) {
        if (row >= 0 && row < searchRecentApps.count
                && searchRecentApps.trigger(row, "", null)) {
            root.expanded = false;
        }
    }
    function runSearch(row) {
        if (!root.expanded || searchResults.querying || row < 0
                || row >= searchResults.rowCount()) return;
        if (searchResults.run(searchResults.index(row, 0))) root.expanded = false;
    }
    function runCurrent(row) {
        if (!root.expanded || root.query.trim().length === 0) return;
        if (searchResults.querying || searchResults.rowCount() < 1 || row < 0) {
            root.queuedRun = root.query;
            return;
        }
        root.queuedRun = "";
        root.runSearch(row);
    }
    function runQueued() {
        if (root.queuedRun.length < 1 || root.queuedRun !== root.query
                || searchResults.querying || searchResults.rowCount() < 1) return;
        const requestedQuery = root.queuedRun;
        const requestedRevision = root.queryRevision;
        Qt.callLater(() => {
            if (root.expanded && !root.active && root.query === requestedQuery
                    && root.queryRevision === requestedRevision
                    && root.queuedRun === requestedQuery && !searchResults.querying) {
                root.queuedRun = "";
                root.runSearch(0);
            }
        });
    }
    function askMoAI() {
        const question = root.query.trim();
        root.expanded = false;
        Qt.openUrlExternally(question.length > 0
            ? "moos://ai/ask/" + encodeURIComponent(question)
            : "moos://app/moai");
    }
    function openDestination(target) {
        root.expanded = false;
        Qt.openUrlExternally(target);
    }

    // Decode rasters for the DEVICE, not for logical pixels. A sourceSize is a
    // hard cap on the decoded image, so a fixed number silently under-samples
    // every HiDPI screen: on the reference 4K panel Qt reports
    // devicePixelRatio 3, where the 38 px avatar needs 114 real pixels and the
    // 104 px expanded cover needs 312 — the old fixed 96 and 256 are why album
    // art looked soft there while the text beside it stayed sharp. One owner
    // for the arithmetic so no surface can drift back to a magic number.
    readonly property real pixelRatio: Math.max(1, Screen.devicePixelRatio)
    function decodePx(logical) {
        return Math.ceil(Math.max(1, logical) * root.pixelRatio);
    }

    // Paused media remains useful. Stopped media gets a short release grace so
    // player hand-offs do not make the bar snap or flash at track boundaries.
    readonly property bool mediaPresent: root.hasPlayer
        && root.playbackStatus > Mpris.PlaybackStatus.Stopped
        && (root.track.length > 0 || root.identity.length > 0)
    readonly property bool active: root.remotePresent
                                   || root.privacyPresent
                                   || root.storeJobPresent
                                   || root.moaiJobPresent
                                   || root.mediaPresent
                                   || releaseGrace.running
    readonly property string contextTitle: !root.active
        ? root.local("ابحث في MoOS", "Search MoOS")
        : root.remotePresent
        ? root.remoteTitle
        : (root.privacyPresent
            ? root.privacyTitle
            : (root.storeJobPresent
                ? root.storeJobTitle
                : (root.moaiJobPresent
                    ? root.moaiJobTitle
                    : root.displayTrack)))
    // The bar is glanceable, not a transcript. Keep a concise label inside the
    // compact frame and reserve the complete sentence for the tooltip/popup.
    readonly property string compactTitle: !root.active
        ? root.local("بحث MoOS", "Search MoOS")
        : root.remotePresent
        ? root.local("تحكم متصل", "Remote connected")
        : (root.privacyPresent
            ? (root.privacyType === "screen"
                ? root.local("مشاركة الشاشة", "Screen sharing")
                : (root.privacyType === "camera"
                    ? root.local("الكاميرا نشطة", "Camera active")
                    : root.local("الميكروفون نشط", "Microphone active")))
            : (root.storeJobPresent ? root.storeJobTitle
                : (root.moaiJobPresent ? root.moaiJobCompact : root.displayTrack)))
    readonly property string contextSource: !root.active
        ? root.local("تطبيقات وملفات وإعدادات", "Apps, files and settings")
        : root.remotePresent
        ? root.remoteSource
        : (root.privacyPresent
            ? root.privacySource
            : (root.storeJobPresent
                ? root.storeJobSource
                : (root.moaiJobPresent
                    ? root.moaiJobSource
                    : root.displaySource)))
    readonly property string contextIcon: !root.active
        ? "moos-search-symbolic"
        : root.remotePresent
        ? "moos-pc-remote"
        : (root.privacyPresent
            ? root.privacyIcon
            : (root.storeJobPresent
                ? root.storeJobIcon
                : (root.moaiJobPresent
                    ? root.moaiJobIcon
                    : root.playerIcon)))

    onMediaPresentChanged: {
        if (root.mediaPresent) { releaseGrace.stop(); }
        else { releaseGrace.restart(); }
    }
    onActiveChanged: if (!root.active) { root.expanded = false; }
    onVolumeChanged: {
        if (root.volume > 0.01) { root.lastAudibleVolume = root.volume; }
    }
    onExpandedChanged: {
        if (root.expanded && root.player) { root.player.updatePosition(); }
        if (!root.expanded) {
            root.query = "";
            root.queuedRun = "";
        }
    }

    Timer {
        id: releaseGrace
        interval: 1600
        repeat: false
    }

    // Remote is a standing safety state. It used to announce as a 230 px
    // sentence and then collapse to a 72 px chip, shifting every task twice.
    // The fixed Context Island has room to keep the useful state and device
    // count visible for the full connection lifetime, so no timer or geometry
    // transition is needed.
    onRemotePresentChanged: if (root.remotePresent) {
        root.detailContext = "remote";
    }

    // Some players publish position only on request. Wake once per second only
    // while progress is both moving and visible (popup open or capsule hovered).
    Timer {
        id: positionSync
        interval: 1000
        repeat: true
        running: root.playing && root.hasTimeline
                 && root.visible && (root.expanded || root.compactHovered)
                 && (!root.remotePresent || (root.expanded && !root.showRemoteDetails))
        onTriggered: if (root.player) { root.player.updatePosition(); }
    }

    Plasmoid.status: PlasmaCore.Types.ActiveStatus
    Plasmoid.icon: root.contextIcon
    toolTipMainText: root.contextTitle
    toolTipSubText: root.contextSource
    toolTipTextFormat: Text.PlainText

    switchWidth: Kirigami.Units.gridUnit * 16
    switchHeight: Kirigami.Units.gridUnit * 11

    compactRepresentation: FocusScope {
        id: compact
        activeFocusOnTab: true
        onActiveFocusChanged: root.compactFocused = activeFocus
        Keys.onReturnPressed: root.openPrimary()
        Keys.onEnterPressed: root.openPrimary()
        Keys.onSpacePressed: event => {
            if (!event.isAutoRepeat) { root.openPrimary(); }
        }
        Keys.onEscapePressed: root.expanded = false
        Accessible.role: Accessible.Button
        Accessible.name: root.contextTitle
        Accessible.description: root.contextSource
        Accessible.onPressAction: root.openPrimary()

        // One invariant width is the central design decision: context changes
        // are allowed to move pixels INSIDE the Island, never its neighbours.
        // 9.5 grid units measure 171 px on the reference 4K/265% session. The
        // first fixed prototype used 14 and read as a second search bar instead
        // of an Island. Compact artwork and one 34 px action leave the title a
        // useful lane without giving activity permission to move the taskbar.
        readonly property real stableWidth: Math.round(Kirigami.Units.gridUnit * 9.5)
        implicitWidth: stableWidth
        implicitHeight: root.design.panelHeight
        Layout.preferredWidth: stableWidth
        Layout.minimumWidth: stableWidth
        Layout.maximumWidth: stableWidth
        Layout.fillHeight: true
        opacity: 1
        enabled: true
        visible: true
        clip: true

        HoverHandler {
            id: compactHover
            onHoveredChanged: root.compactHovered = hovered
        }

        Rectangle {
            id: compactShell
            anchors.fill: parent
            anchors.topMargin: root.design.space1
            anchors.bottomMargin: root.design.space1
            radius: Math.min(16, height / 2)
            // Follow the live glass-clarity control, using the same fill rule
            // as the other MoOS surfaces. Palette and depth still set the
            // balanced density; clear and solid remain visibly different.
            color: Qt.alpha(Kirigami.Theme.backgroundColor,
                            root.design.glassFill(Kirigami.Theme.backgroundColor,
                                                  root.design.glassLevelPanel,
                                                  root.design.glassRestingOpacity)
                            + (compactHover.hovered ? 0.05 : 0))
            border.width: compact.activeFocus ? 2 : root.design.borderHairline
            border.color: compact.activeFocus ? Kirigami.Theme.highlightColor
                : (compactHover.hovered
                    ? Qt.alpha(Kirigami.Theme.textColor, 0.22)
                    : root.design.glassEdge(Kirigami.Theme.backgroundColor,
                                            root.design.glassLevelPanel))
            antialiasing: true

            // The light along the top edge. One hairline, inset by the corner so
            // it lives on the straight part of the rim, painted only here.
            Rectangle {
                anchors.top: parent.top
                anchors.topMargin: 1
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.max(0, parent.width - parent.radius * 1.6)
                height: 1
                color: root.design.glassSpecular(Kirigami.Theme.backgroundColor,
                                                 root.design.glassLevelPanel)
                visible: parent.width > parent.radius * 2
            }

            Behavior on border.color {
                ColorAnimation { duration: root.motionFast }
            }
            Behavior on color {
                ColorAnimation { duration: root.motionFast }
            }

            // A restrained Tidal crest gives the eye a reason for the capsule
            // to widen. It grows with the same geometry clock as the shell and
            // then stays still; no ambient sweep or permanent repaint.
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: -height / 2
                width: compactHover.hovered ? parent.width * 0.30
                                            : parent.width * 0.12
                height: 2
                radius: 1
                color: Kirigami.Theme.highlightColor
                opacity: compactHover.hovered ? 0.78 : 0.34
                Behavior on width {
                    NumberAnimation {
                        duration: root.motionGeometry
                        easing.type: root.design.easeEmphasis
                    }
                }
                Behavior on opacity {
                    NumberAnimation { duration: root.motionFast }
                }
            }

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                cursorShape: Qt.PointingHandCursor
                // Same press-time capture as the launcher's compact button: if
                // the expanded dialog dismissed itself on this press, release
                // must not read the post-dismiss state and re-open it.
                property bool wasExpanded: false
                onPressed: wasExpanded = root.expanded
                onClicked: mouse => {
                    if (!root.active) {
                        root.openPrimary();
                    } else if (root.remotePresent) {
                        if (mouse.button === Qt.MiddleButton) {
                            Qt.openUrlExternally("moos://app/remote");
                        } else {
                            root.expanded = !wasExpanded;
                        }
                    } else if (mouse.button === Qt.MiddleButton) {
                        root.togglePlaying();
                    } else {
                        root.expanded = !wasExpanded;
                    }
                }
                onWheel: wheel => {
                    if (root.remotePresent || !root.player || !root.hasVolume) {
                        wheel.accepted = false;
                        return;
                    }
                    root.player.changeVolume(wheel.angleDelta.y > 0 ? 0.05 : -0.05,
                                             true);
                }
            }

            // A COLUMN, not two anchored siblings. The content row and the
            // timeline used to be anchored children of the same shell, and
            // anchors do not reserve anything from each other — so the
            // hairline drew straight across the source caption and no amount
            // of bottomMargin on the row fixed it, because the row's children
            // still sized themselves against the full shell. A column cannot
            // overlap: the lane takes its height first and the row gets what
            // is genuinely left.
            ColumnLayout {
                anchors.fill: parent
                // A pill's rim curves INWARD, so a flat margin lets the corner
                // eat whatever sits at the ends: the cover art was tangent to
                // the curve on one side and the caption was clipped by it on
                // the other.
                anchors.leftMargin: root.design.space2
                anchors.rightMargin: root.design.space2
                anchors.topMargin: 2
                anchors.bottomMargin: 2
                spacing: 1

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: root.design.space1
                layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

                Rectangle {
                    id: contextPlate
                    // DERIVED, never a literal. A hardcoded 38 was the same
                    // height the capsule had left over, so the artwork had no
                    // breathing room at all and any inset — including one I
                    // added here — pushed it and the caption straight through
                    // the pill's bottom curve. Sizing from the shell keeps a
                    // real margin at every panel height the bar can take.
                    readonly property int artSize:
                        Math.round(compactShell.height * 0.68)
                    Layout.preferredWidth: artSize
                    Layout.preferredHeight: artSize
                    // Without this the artwork stretched to the capsule's full
                    // height and sat off-centre against the type beside it.
                    Layout.alignment: Qt.AlignVCenter
                    radius: root.design.radiusControl
                    color: Qt.alpha(Kirigami.Theme.highlightColor, 0.16)
                    border.width: root.design.borderHairline
                    border.color: Qt.alpha(Kirigami.Theme.highlightColor,
                                           compactHover.hovered ? 0.46 : 0.24)
                    // The context change is SPRUNG, not timed.
                    //
                    // A NumberAnimation with an easing curve arrives at 1.0 on a
                    // schedule: the plate reaches its size because the clock ran
                    // out, and two changes in quick succession restart the curve
                    // from 0.90 with a visible jerk. MoOS already owns the
                    // physical answer — MoUI.SpringFeedback is what a MoOS Button,
                    // the brand plasmoid and Search all settle with — so the
                    // Island settles the same way instead of inventing a third
                    // motion language inside the bar.
                    //
                    // Retargetable is the property that matters here. Media can
                    // replace Remote which can replace Store within a second, and
                    // a spring that is already moving simply acquires the new
                    // target and keeps its velocity. It settles once, in one
                    // continuous move, rather than snapping back to restart.
                    //
                    // SCALE ONLY, which is SpringFeedback's own rule: the Island's
                    // width is fixed and its layout never moves, so nothing a
                    // neighbouring task icon can see is on a spring.
                    scale: contextSpring.value
                    opacity: 1

                    MoUI.SpringFeedback {
                        id: contextSpring
                        motionEnabled: root.motionEnabled
                        targetScale: 1
                    }

                    Connections {
                        target: root
                        function onContextIconChanged() {
                            if (root.motionEnabled && root.visible) {
                                // Compress, then let the spring carry it back.
                                // The dip is what reads as "this changed"; the
                                // physics is what makes it feel like an object
                                // rather than a fade.
                                contextSpring.value = 0.90;
                                contextSpring.retarget();
                                contextFade.restart();
                            }
                        }
                        function onMotionEnabledChanged() {
                            if (!root.motionEnabled) {
                                contextFade.stop();
                                contextSpring.value = 1;
                                contextPlate.opacity = 1;
                            }
                        }
                    }
                    // Opacity stays on a curve on purpose: a cross-fade is not a
                    // physical event, and springing it would overshoot past 1.
                    NumberAnimation {
                        id: contextFade
                        target: contextPlate; property: "opacity"
                        from: 0.48; to: 1
                        duration: root.motionFast
                        easing.type: Easing.OutCubic
                    }

                    // NOT Rectangle{radius}+clip: Qt clips a child to the
                    // item's BOUNDING BOX, never to its rounded corners, so an
                    // Image inside a rounded frame renders as a hard square
                    // that pokes out of every corner. It was invisible while
                    // the art was soft and became obvious the moment the
                    // decode was fixed. ShadowedImage rounds the texture
                    // itself with distance fields — the same primitive
                    // Kirigami's own cards use — so there is no mask layer and
                    // no MultiEffect in plasmashell's always-on budget.
                    // radiusControl, not a circle: the expanded cover is a
                    // rounded square, so the artwork no longer changes shape
                    // when the capsule opens.
                    Kirigami.ShadowedImage {
                        id: compactArt
                        anchors.fill: parent
                        radius: parent.radius
                        source: root.artworkSource
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize.width: root.decodePx(width)
                        visible: !root.remotePresent
                                 && !root.privacyPresent
                                 && !root.storeJobPresent
                                 && !root.moaiJobPresent
                                 && root.artworkSource.length > 0
                                 && status === Image.Ready
                        onStatusChanged: if (status === Image.Error
                                && root.artworkSource !== root.artUrl) {
                            root.artworkBridgeFailed = true;
                        }
                    }
                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: 18
                        height: 18
                        source: root.contextIcon
                        // A player publishes a desktop-entry NAME, which is not
                        // always an icon name: MoPlayer's entry is
                        // `org.moos.moplayer` and its icon is `moos-moplayer`,
                        // so the capsule drew the theme's "unknown file" sheet —
                        // a question mark on the bar next to a working player,
                        // measured on the station on 2026-09-18.
                        fallback: "applications-multimedia-symbolic"
                        color: root.privacyPresent
                            ? (root.privacyType === "camera"
                                ? Kirigami.Theme.positiveTextColor
                                : (root.privacyType === "screen" ? Kirigami.Theme.highlightColor : Kirigami.Theme.neutralTextColor))
                            : Kirigami.Theme.highlightColor
                        visible: !compactArt.visible
                    }

                    // Live state on the settled chip, never animated: a status dot (active or
                    // paused) and, for more than one device, the count. Both come from the same
                    // presence files as the sentence they replace.
                    Rectangle {
                        visible: root.remotePresent
                        width: 8
                        height: 8
                        radius: 4
                        anchors.top: parent.top
                        anchors.topMargin: -2
                        anchors.right: root.rtl ? undefined : parent.right
                        anchors.left: root.rtl ? parent.left : undefined
                        anchors.rightMargin: -2
                        anchors.leftMargin: -2
                        color: root.remoteMode === "paused"
                            ? Kirigami.Theme.neutralTextColor
                            : Kirigami.Theme.positiveTextColor
                        border.width: 2
                        border.color: Kirigami.Theme.backgroundColor
                    }

                    // Status dot for active privacy usage (Camera = green, Screen = cyan, Mic = amber)
                    Rectangle {
                        visible: !root.remotePresent && root.privacyPresent
                        width: 8
                        height: 8
                        radius: 4
                        anchors.top: parent.top
                        anchors.topMargin: -2
                        anchors.right: root.rtl ? undefined : parent.right
                        anchors.left: root.rtl ? parent.left : undefined
                        anchors.rightMargin: -2
                        anchors.leftMargin: -2
                        color: root.privacyType === "camera"
                            ? Kirigami.Theme.positiveTextColor
                            : (root.privacyType === "screen"
                                ? Kirigami.Theme.highlightColor
                                : Kirigami.Theme.neutralTextColor)
                        border.width: 2
                        border.color: Kirigami.Theme.backgroundColor
                    }
                    Rectangle {
                        visible: root.remotePresent && root.remoteSessions > 1
                        height: 16
                        width: Math.max(16, remoteCount.implicitWidth + 8)
                        radius: 8
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: -3
                        anchors.right: root.rtl ? undefined : parent.right
                        anchors.left: root.rtl ? parent.left : undefined
                        anchors.rightMargin: -4
                        anchors.leftMargin: -4
                        color: Kirigami.Theme.highlightColor
                        Text {
                            id: remoteCount
                            anchors.centerIn: parent
                            text: String(root.remoteSessions)
                            color: Kirigami.Theme.highlightedTextColor
                            font.pixelSize: 10
                            font.weight: Font.Bold
                        }
                    }
                }

                ColumnLayout {
                    id: compactText
                    visible: true
                    Layout.fillWidth: true
                    Layout.minimumWidth: 68
                    // Centre the two lines as a BLOCK. Filling the capsule's
                    // full height pushed the caption onto the pill's bottom
                    // curve, which clipped it — the source name was cut in
                    // half on the live panel.
                    Layout.alignment: Qt.AlignVCenter
                    Layout.fillHeight: false
                    // THE BAR'S REAL HEIGHT DECIDES HOW MANY LINES FIT, not the
                    // design token. `panelHeight` is what the capsule ASKS for
                    // (54); MoOS Bar gives its applets 40, and two pinned lines
                    // (17 + 15) plus the timeline lane need more than the 28 px
                    // that leaves — so on the owner's own desk the source line
                    // was drawn straight through the pill's bottom curve and
                    // sat outside the capsule, measured on the station on
                    // 2026-09-18 while a video was playing. The title is what
                    // the capsule is for; the source is a courtesy, so it is
                    // the one that goes when there is no room, and it is still
                    // in the tooltip and in the expanded view.
                    readonly property real laneRoom: timelineLane.visible ? 4 : 0
                    readonly property bool roomForSource: root.active
                        && compactShell.height - 4 - laneRoom >= 34
                    Layout.maximumHeight: Math.max(
                        17, compactShell.height - 4 - laneRoom)
                    Layout.leftMargin: root.design.space1
                    Layout.rightMargin: root.design.space1
                    spacing: 0
                    transform: Translate { id: trackShift }

                    // A track change used to be a hard text swap: one frame the
                    // old title, the next the new one, with no relationship
                    // between them. On a surface whose whole job is to show
                    // what is playing, that is the moment the user actually
                    // looks at — so it is the moment worth animating. The block
                    // rises a few pixels as the text is replaced, which reads
                    // as a deliberate update rather than a layout glitch. It is a
                    // one-shot triggered by real MPRIS data, never a loop, and
                    // it collapses to nothing when the user has motion off
                    // because motionFast is already gated on longDuration > 1.
                    opacity: 1
                    function stopTrackTurn() {
                        trackTurn.stop();
                        compactText.opacity = 1;
                        trackShift.y = 0;
                    }
                    onVisibleChanged: if (!visible) { stopTrackTurn(); }
                    Connections {
                        target: root
                        function onCompactTitleChanged() {
                            if (root.motionEnabled && compactText.visible
                                    && root.visible) {
                                trackTurn.restart();
                            } else {
                                compactText.stopTrackTurn();
                            }
                        }
                        function onMotionEnabledChanged() {
                            if (!root.motionEnabled) { compactText.stopTrackTurn(); }
                        }
                        function onVisibleChanged() {
                            if (!root.visible) { compactText.stopTrackTurn(); }
                        }
                    }
                    ParallelAnimation {
                        id: trackTurn
                        running: false
                        NumberAnimation {
                            target: compactText; property: "opacity"
                            from: 0.20; to: 1; duration: root.motionGeometry
                            easing.type: Easing.OutCubic
                        }
                        NumberAnimation {
                            target: trackShift; property: "y"
                            from: root.design.space1; to: 0
                            duration: root.motionGeometry
                            easing.type: root.design.easeEmphasis
                        }
                    }

                    // FIXED line boxes, not the font's own. An Arabic-capable UI
                    // font carries a tall ascent/descent, so two natural line
                    // boxes came to roughly 41 px inside a 46 px capsule that
                    // also has to hold the timeline lane — the caption was
                    // pushed onto the pill's curve and the progress hairline
                    // drew straight through it. Pinning both lines makes the
                    // block 32 px whatever script it renders, so the capsule
                    // holds title, source and timeline at its real height and
                    // stays correct if the bar is ever made shorter.
                    PC3.Label {
                        Layout.fillWidth: true
                        text: root.compactTitle
                        color: Kirigami.Theme.textColor
                        font.pixelSize: root.design.typeSecondary
                        font.weight: Font.DemiBold
                        lineHeightMode: Text.FixedHeight
                        lineHeight: 17
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: root.rtl ? Text.AlignRight
                                                      : Text.AlignLeft
                    }
                    PC3.Label {
                        Layout.fillWidth: true
                        visible: compactText.roomForSource
                        text: root.contextSource
                        color: Kirigami.Theme.disabledTextColor
                        font.pixelSize: root.design.typeCaption
                        lineHeightMode: Text.FixedHeight
                        lineHeight: 15
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: root.rtl ? Text.AlignRight
                                                      : Text.AlignLeft
                    }
                }

                // Play/pause is the one control that never hides: it is why the
                // capsule is reachable at all without opening anything.
                MediaControl {
                    slotSize: 34
                    revealed: root.mediaPresent && !root.remotePresent
                              && !root.privacyPresent && !root.storeJobPresent
                              && !root.moaiJobPresent
                    controlEnabled: root.playing
                        ? root.canPause : (root.canPlay || root.canControl)
                    iconName: root.playing ? "media-playback-pause-symbolic"
                                           : "media-playback-start-symbolic"
                    label: root.playing ? root.local("إيقاف مؤقت", "Pause")
                                        : root.local("تشغيل", "Play")
                    onActivated: root.togglePlaying()
                }

                // One-tap stop for privacy streams
                MediaControl {
                    slotSize: 34
                    revealed: !root.remotePresent && root.privacyPresent
                    controlEnabled: true
                    iconName: "moos-close-symbolic"
                    label: root.local("إيقاف", "Stop")
                    onActivated: Qt.openUrlExternally("moos://privacy/stop/" + root.privacyType + "/" + root.privacyNodeId)
                }

                // Quick open for Store jobs
                MediaControl {
                    slotSize: 34
                    revealed: !root.remotePresent && !root.privacyPresent && root.storeJobPresent
                    controlEnabled: true
                    iconName: "moos-store"
                    label: root.local("المتجر", "Store")
                    onActivated: Qt.openUrlExternally("moos://app/store")
                }

                // Quick open for a confirmed Mo AI job: the steps live in Mo AI.
                MediaControl {
                    slotSize: 34
                    revealed: !root.remotePresent && !root.privacyPresent
                              && !root.storeJobPresent && root.moaiJobPresent
                    controlEnabled: true
                    iconName: root.moaiJobIcon
                    label: root.local("فتح Mo AI", "Open Mo AI")
                    onActivated: root.openMoAI()
                }

                MediaControl {
                    slotSize: 34
                    revealed: root.remotePresent
                    controlEnabled: true
                    iconName: "configure-symbolic"
                    label: root.local("فتح إعدادات التحكم", "Open Remote controls")
                    onActivated: Qt.openUrlExternally("moos://app/remote")
                }
            }

            // The progress hairline had two defects, and both were visible.
            // It was anchored to the pill's BOTTOM EDGE, but that edge is a
            // curve, so a flat bar ran straight past it at each end and read
            // as a stray line under the capsule instead of part of it. And it
            // was anchored to parent.LEFT in every language, so in Arabic —
            // where the whole capsule is mirrored — it grew away from the
            // start of the track and appeared to drain as the media played.
            // Inset by the corner radius so it lives in the capsule's straight
            // middle, give it a track so the remaining time is legible too,
            // mirror the fill for RTL, and let it travel instead of jumping
            // between the one-second position samples.
            Item {
                id: timelineLane
                Layout.fillWidth: true
                Layout.preferredHeight: 3
                Layout.leftMargin: compactShell.radius * 0.35
                Layout.rightMargin: compactShell.radius * 0.35
                visible: (!root.remotePresent && !root.privacyPresent && !root.storeJobPresent
                          && !root.moaiJobPresent && root.hasTimeline)
                         || (!root.remotePresent && !root.privacyPresent && root.storeJobPresent && root.storeJobProgress > 0)

                Rectangle {
                    anchors.fill: parent
                    radius: height / 2
                    color: Qt.alpha(Kirigami.Theme.textColor, 0.14)
                }
                Rectangle {
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.left: root.rtl ? undefined : parent.left
                    anchors.right: root.rtl ? parent.right : undefined
                    width: parent.width * (root.storeJobPresent ? root.bounded(root.storeJobProgress / 100, 0, 1) : root.progress)
                    radius: height / 2
                    color: Kirigami.Theme.highlightColor
                    // A settle, not a crawl: position only arrives while the
                    // capsule is hovered or open, so this never runs at rest.
                    Behavior on width {
                        NumberAnimation {
                            duration: root.motionFast
                            easing.type: Easing.OutCubic
                        }
                    }
                }
            }
            }
        }
    }

    fullRepresentation: FocusScope {
        id: expanded
        Keys.onEscapePressed: root.expanded = false

        Layout.preferredWidth: root.active ? Kirigami.Units.gridUnit * 21
                                           : Kirigami.Units.gridUnit * 30
        Layout.preferredHeight: root.active
            ? Kirigami.Units.gridUnit
                * ((root.showRemoteDetails || root.showPrivacyDetails || root.showStoreDetails
                    || root.showMoaiDetails) ? 13 : 17)
                + (root.multipleContexts ? 48 : 0)
            // The Island popup grows upward from a bottom panel. The retired
            // standalone Search applet used 28 units, but that height crossed
            // behind the Horizon Bar at 4K/265% and clipped the Mo AI row.
            : Math.min(Kirigami.Units.gridUnit * root.searchSurfaceUnits,
                       Screen.height - Kirigami.Units.gridUnit * 7)
        Layout.minimumWidth: root.active ? Kirigami.Units.gridUnit * 18
                                         : Math.min(400, Screen.width - 24)
        Layout.minimumHeight: root.active
            ? Kirigami.Units.gridUnit
                * ((root.showRemoteDetails || root.showPrivacyDetails || root.showStoreDetails
                    || root.showMoaiDetails) ? 12 : 15)
                + (root.multipleContexts ? 48 : 0)
            : Kirigami.Units.gridUnit * 16
        Layout.maximumHeight: root.active
            ? Kirigami.Units.gridUnit * 22 + (root.multipleContexts ? 48 : 0)
            : Math.min(Kirigami.Units.gridUnit * root.searchSurfaceUnits,
                       Screen.height - Kirigami.Units.gridUnit * 7)
        opacity: root.motionEnabled ? 0 : 1
        scale: root.motionEnabled ? 0.96 : 1
        transformOrigin: Item.Top

        function revealPopup() {
            if (!root.motionEnabled || !root.expanded || !expanded.visible) {
                expandedEntrance.stop();
                expanded.opacity = 1;
                expanded.scale = 1;
            } else if (root.expanded) {
                expanded.opacity = 0;
                expanded.scale = 0.96;
                expandedEntrance.restart();
            }
        }
        Component.onCompleted: revealPopup()
        Connections {
            target: root
            function onExpandedChanged() {
                expanded.revealPopup();
            }
            function onMotionEnabledChanged() { expanded.revealPopup(); }
        }
        onVisibleChanged: revealPopup()
        ParallelAnimation {
            id: expandedEntrance
            NumberAnimation {
                target: expanded; property: "opacity"; from: 0; to: 1
                duration: root.motionGeometry; easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: expanded; property: "scale"; from: 0.96; to: 1
                duration: root.motionGeometry; easing.type: root.design.easeEmphasis
            }
        }

        SearchView {
            anchors.fill: parent
            visible: !root.active
            z: 20
            controller: root
            resultModel: searchResults
            recentModel: searchRecentApps
        }

        PC3.TabBar {
            id: contextTabs
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: root.design.space4
            visible: root.active && root.multipleContexts
            currentIndex: root.showRemoteDetails ? 0
                : (root.showPrivacyDetails ? 1
                    : (root.showStoreDetails ? 2 : (root.showMoaiDetails ? 3 : 4)))
            LayoutMirroring.enabled: root.rtl
            LayoutMirroring.childrenInherit: true
            PC3.TabButton {
                visible: root.remotePresent
                text: root.local("التحكم عن بُعد", "Remote")
                icon.name: "moos-pc-remote"
                onClicked: root.detailContext = "remote"
            }
            PC3.TabButton {
                visible: root.privacyPresent
                text: root.local("الخصوصية", "Privacy")
                icon.name: root.privacyIcon
                onClicked: root.detailContext = "privacy"
            }
            PC3.TabButton {
                visible: root.storeJobPresent
                text: root.local("المتجر", "Store")
                icon.name: root.storeJobIcon
                onClicked: root.detailContext = "store"
            }
            PC3.TabButton {
                visible: root.moaiJobPresent
                text: "Mo AI"
                icon.name: root.moaiJobIcon
                onClicked: root.detailContext = "moai"
            }
            PC3.TabButton {
                visible: root.mediaPresent
                text: root.local("الوسائط", "Media")
                icon.name: root.playerIcon
                onClicked: root.detailContext = "media"
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.design.space5
            anchors.topMargin: root.multipleContexts
                ? contextTabs.height + root.design.space5 * 2 : root.design.space5
            spacing: root.design.space4
            visible: root.showRemoteDetails
            layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

            RowLayout {
                Layout.fillWidth: true
                spacing: root.design.space4

                Rectangle {
                    Layout.preferredWidth: 76
                    Layout.preferredHeight: 76
                    radius: root.design.radiusCard
                    color: Qt.alpha(Kirigami.Theme.highlightColor, 0.16)

                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: 40
                        height: 40
                        source: "moos-pc-remote"
                        color: Kirigami.Theme.highlightColor
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: root.design.space1

                    PlasmaExtras.Heading {
                        Layout.fillWidth: true
                        text: root.remoteTitle
                        level: 3
                        maximumLineCount: 2
                        wrapMode: Text.Wrap
                        horizontalAlignment: root.rtl ? Text.AlignRight
                                                      : Text.AlignLeft
                    }
                    PC3.Label {
                        Layout.fillWidth: true
                        text: root.remoteSource
                        color: Kirigami.Theme.disabledTextColor
                        font.pixelSize: root.design.typeSecondary
                        horizontalAlignment: root.rtl ? Text.AlignRight
                                                      : Text.AlignLeft
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Qt.alpha(Kirigami.Theme.textColor, 0.12)
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: root.design.space3

                Rectangle {
                    Layout.preferredWidth: 10
                    Layout.preferredHeight: 10
                    radius: 5
                    color: root.remoteMode === "paused"
                        ? Kirigami.Theme.neutralTextColor
                        : Kirigami.Theme.positiveTextColor
                }
                PC3.Label {
                    Layout.fillWidth: true
                    text: root.remoteMode === "paused"
                        ? root.local("المشاركة متوقفة مؤقتًا، والجلسة ما زالت متصلة.",
                                     "Sharing is paused; the session remains connected.")
                        : root.local("تتم مشاركة الشاشة والتحكم مع جهاز موثوق الآن.",
                                     "Screen and controls are shared with a trusted device now.")
                    wrapMode: Text.Wrap
                    color: Kirigami.Theme.textColor
                    horizontalAlignment: root.rtl ? Text.AlignRight
                                                  : Text.AlignLeft
                }
            }

            Item { Layout.fillHeight: true }

            PC3.Button {
                Layout.fillWidth: true
                text: root.local("فتح مركز Mo PC Remote", "Open Mo PC Remote")
                icon.name: "configure-symbolic"
                onClicked: Qt.openUrlExternally("moos://app/remote")
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.design.space5
            anchors.topMargin: root.multipleContexts
                ? contextTabs.height + root.design.space5 * 2 : root.design.space5
            spacing: root.design.space4
            visible: root.showPrivacyDetails
            layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

            RowLayout {
                Layout.fillWidth: true
                spacing: root.design.space4

                Rectangle {
                    Layout.preferredWidth: 76
                    Layout.preferredHeight: 76
                    radius: root.design.radiusCard
                    color: Qt.alpha(root.privacyType === "camera"
                        ? Kirigami.Theme.positiveTextColor
                        : (root.privacyType === "screen" ? Kirigami.Theme.highlightColor : Kirigami.Theme.neutralTextColor), 0.16)

                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: 40
                        height: 40
                        source: root.privacyIcon
                        color: root.privacyType === "camera"
                            ? Kirigami.Theme.positiveTextColor
                            : (root.privacyType === "screen" ? Kirigami.Theme.highlightColor : Kirigami.Theme.neutralTextColor)
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: root.design.space1

                    PlasmaExtras.Heading {
                        Layout.fillWidth: true
                        text: root.privacyTitle
                        level: 3
                        maximumLineCount: 2
                        wrapMode: Text.Wrap
                        horizontalAlignment: root.rtl ? Text.AlignRight : Text.AlignLeft
                    }
                    PC3.Label {
                        Layout.fillWidth: true
                        text: root.privacyApp
                        color: Kirigami.Theme.disabledTextColor
                        font.pixelSize: root.design.typeSecondary
                        horizontalAlignment: root.rtl ? Text.AlignRight : Text.AlignLeft
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Qt.alpha(Kirigami.Theme.textColor, 0.12)
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: root.design.space3

                Rectangle {
                    Layout.preferredWidth: 10
                    Layout.preferredHeight: 10
                    radius: 5
                    color: root.privacyType === "camera"
                        ? Kirigami.Theme.positiveTextColor
                        : (root.privacyType === "screen" ? Kirigami.Theme.highlightColor : Kirigami.Theme.neutralTextColor)
                }
                PC3.Label {
                    Layout.fillWidth: true
                    text: root.privacyType === "screen"
                        ? root.local("تتم مشاركة الشاشة حالياً مع هذا التطبيق.",
                                     "Screen sharing is currently active with this app.")
                        : (root.privacyType === "camera"
                            ? root.local("الكاميرا قيد الاستخدام حالياً بواسطة هذا التطبيق.",
                                         "Camera is currently in use by this app.")
                            : root.local("الميكروفون قيد التسجيل حالياً بواسطة هذا التطبيق.",
                                         "Microphone is currently in use by this app."))
                    wrapMode: Text.Wrap
                    color: Kirigami.Theme.textColor
                    horizontalAlignment: root.rtl ? Text.AlignRight : Text.AlignLeft
                }
            }

            Item { Layout.fillHeight: true }

            PC3.Button {
                Layout.fillWidth: true
                text: root.local("إيقاف فوري بنقرة واحدة", "Stop with One Tap")
                icon.name: "media-playback-stop-symbolic"
                onClicked: {
                    Qt.openUrlExternally("moos://privacy/stop/" + root.privacyType + "/" + root.privacyNodeId);
                    root.expanded = false;
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.design.space5
            anchors.topMargin: root.multipleContexts
                ? contextTabs.height + root.design.space5 * 2 : root.design.space5
            spacing: root.design.space4
            visible: root.showStoreDetails
            layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

            RowLayout {
                Layout.fillWidth: true
                spacing: root.design.space4

                Rectangle {
                    Layout.preferredWidth: 76
                    Layout.preferredHeight: 76
                    radius: root.design.radiusCard
                    color: Qt.alpha(Kirigami.Theme.highlightColor, 0.16)

                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: 40
                        height: 40
                        source: root.storeJobIcon
                        color: Kirigami.Theme.highlightColor
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: root.design.space1

                    PlasmaExtras.Heading {
                        Layout.fillWidth: true
                        text: root.storeJobTitle
                        level: 3
                        maximumLineCount: 2
                        wrapMode: Text.Wrap
                        horizontalAlignment: root.rtl ? Text.AlignRight : Text.AlignLeft
                    }
                    PC3.Label {
                        Layout.fillWidth: true
                        text: root.storeJobSource
                        color: Kirigami.Theme.disabledTextColor
                        font.pixelSize: root.design.typeSecondary
                        horizontalAlignment: root.rtl ? Text.AlignRight : Text.AlignLeft
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Qt.alpha(Kirigami.Theme.textColor, 0.12)
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: root.design.space2
                visible: root.storeJobProgress > 0

                PC3.ProgressBar {
                    Layout.fillWidth: true
                    from: 0
                    to: 100
                    value: root.storeJobProgress
                }

                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label {
                        text: root.storeJobMessage
                        color: Kirigami.Theme.disabledTextColor
                        font.pixelSize: root.design.typeCaption
                        elide: Text.ElideRight
                    }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        text: Math.round(root.storeJobProgress) + "%"
                        color: Kirigami.Theme.highlightColor
                        font.pixelSize: root.design.typeCaption
                        font.weight: Font.Bold
                    }
                }
            }

            Item { Layout.fillHeight: true }

            PC3.Button {
                Layout.fillWidth: true
                text: root.local("فتح متجر Mo Store", "Open Mo Store")
                icon.name: "moos-store"
                onClicked: Qt.openUrlExternally("moos://app/store")
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.design.space5
            anchors.topMargin: root.multipleContexts
                ? contextTabs.height + root.design.space5 * 2 : root.design.space5
            spacing: root.design.space4
            visible: root.showMoaiDetails
            layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

            RowLayout {
                Layout.fillWidth: true
                spacing: root.design.space4

                Rectangle {
                    Layout.preferredWidth: 76
                    Layout.preferredHeight: 76
                    radius: root.design.radiusCard
                    color: Qt.alpha(root.moaiJobState === "failed"
                        ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.highlightColor, 0.16)

                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: 40
                        height: 40
                        source: root.moaiJobIcon
                        color: root.moaiJobState === "failed"
                            ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.highlightColor
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: root.design.space1

                    PlasmaExtras.Heading {
                        Layout.fillWidth: true
                        text: root.moaiJobTitle
                        level: 3
                        maximumLineCount: 2
                        wrapMode: Text.Wrap
                        horizontalAlignment: root.rtl ? Text.AlignRight : Text.AlignLeft
                    }
                    PC3.Label {
                        Layout.fillWidth: true
                        text: root.moaiJobSource
                        color: Qt.alpha(Kirigami.Theme.textColor, 0.72)
                        font.pixelSize: root.design.typeSecondary
                        wrapMode: Text.Wrap
                        horizontalAlignment: root.rtl ? Text.AlignRight : Text.AlignLeft
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Qt.alpha(Kirigami.Theme.textColor, 0.12)
            }

            PC3.Label {
                Layout.fillWidth: true
                text: root.local("وافقتَ على هذا الإجراء في Mo AI، وتظهر خطواته ونتيجته هناك.",
                                 "You confirmed this action in Mo AI; its steps and result are shown there.")
                wrapMode: Text.Wrap
                color: Kirigami.Theme.textColor
                horizontalAlignment: root.rtl ? Text.AlignRight : Text.AlignLeft
            }

            Item { Layout.fillHeight: true }

            PC3.Button {
                Layout.fillWidth: true
                text: root.local("فتح Mo AI", "Open Mo AI")
                icon.name: root.moaiJobIcon
                onClicked: root.openMoAI()
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.design.space5
            anchors.topMargin: root.multipleContexts
                ? contextTabs.height + root.design.space5 * 2 : root.design.space5
            spacing: root.design.space4
            visible: root.showMediaDetails
            layoutDirection: root.rtl ? Qt.RightToLeft : Qt.LeftToRight

            RowLayout {
                Layout.fillWidth: true
                spacing: root.design.space4

                Rectangle {
                    Layout.preferredWidth: 104
                    Layout.preferredHeight: 104
                    radius: root.design.radiusCard
                    color: Qt.alpha(Kirigami.Theme.highlightColor, 0.14)

                    // Same rounded-texture reason as the compact cover above.
                    Kirigami.ShadowedImage {
                        id: expandedArt
                        anchors.fill: parent
                        radius: parent.radius
                        source: root.artworkSource
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize.width: root.decodePx(width)
                        visible: root.artworkSource.length > 0
                                 && status === Image.Ready
                        onStatusChanged: if (status === Image.Error
                                && root.artworkSource !== root.artUrl) {
                            root.artworkBridgeFailed = true;
                        }
                    }
                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: 46
                        height: 46
                        source: root.playerIcon
                        color: Kirigami.Theme.highlightColor
                        visible: !expandedArt.visible
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: root.design.space1

                    Rectangle {
                        Layout.preferredWidth: Math.min(184,
                            sourceLabel.implicitWidth + root.design.space3)
                        Layout.preferredHeight: 24
                        radius: 12
                        color: Qt.alpha(Kirigami.Theme.highlightColor, 0.14)

                        PC3.Label {
                            id: sourceLabel
                            anchors.centerIn: parent
                            width: Math.min(168, implicitWidth)
                            text: root.displaySource
                            color: Kirigami.Theme.highlightColor
                            font.pixelSize: root.design.typeCaption
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }
                    }
                    PlasmaExtras.Heading {
                        Layout.fillWidth: true
                        text: root.displayTrack
                        level: 3
                        maximumLineCount: 2
                        wrapMode: Text.Wrap
                        elide: Text.ElideRight
                        horizontalAlignment: root.rtl ? Text.AlignRight
                                                      : Text.AlignLeft
                    }
                    PC3.Label {
                        Layout.fillWidth: true
                        text: [root.artist, root.album].filter(
                            value => value.length > 0).join(" · ")
                        visible: text.length > 0
                        color: Kirigami.Theme.disabledTextColor
                        maximumLineCount: 1
                        elide: Text.ElideRight
                        horizontalAlignment: root.rtl ? Text.AlignRight
                                                      : Text.AlignLeft
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                visible: root.hasTimeline
                spacing: root.design.space1

                PC3.Slider {
                    id: seekSlider
                    Layout.fillWidth: true
                    from: 0
                    to: Math.max(1, root.length)
                    value: root.position
                    enabled: root.canSeek
                    stepSize: 5000000
                    Accessible.name: root.local("موضع التشغيل", "Playback position")
                    Accessible.onIncreaseAction:
                        root.seekTo(root.position + seekSlider.stepSize)
                    Accessible.onDecreaseAction:
                        root.seekTo(root.position - seekSlider.stepSize)
                    onMoved: seekCommit.restart()
                    onPressedChanged: if (!pressed) { root.seekTo(value); }

                    Timer {
                        id: seekCommit
                        interval: 90
                        repeat: false
                        onTriggered: root.seekTo(seekSlider.value)
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label {
                        text: root.formatTime(seekSlider.value)
                        color: Kirigami.Theme.disabledTextColor
                        font.pixelSize: root.design.typeCaption
                        font.features: ({ "tnum": 1 })
                    }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        text: root.formatTime(root.length)
                        color: Kirigami.Theme.disabledTextColor
                        font.pixelSize: root.design.typeCaption
                        font.features: ({ "tnum": 1 })
                    }
                }
            }

            // The same control language as the capsule, one step up in size,
            // with the primary action finally reading as primary.
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: root.design.space4

                MediaControl {
                    slotSize: 40
                    controlEnabled: root.canGoPrevious
                    iconName: root.rtl ? "media-skip-forward-symbolic"
                                       : "media-skip-backward-symbolic"
                    label: root.local("السابق", "Previous")
                    onActivated: root.player.Previous()
                }
                MediaControl {
                    primary: true
                    controlEnabled: root.playing
                        ? root.canPause : (root.canPlay || root.canControl)
                    iconName: root.playing ? "media-playback-pause-symbolic"
                                           : "media-playback-start-symbolic"
                    label: root.playing ? root.local("إيقاف مؤقت", "Pause")
                                        : root.local("تشغيل", "Play")
                    onActivated: root.togglePlaying()
                }
                MediaControl {
                    slotSize: 40
                    controlEnabled: root.canGoNext
                    iconName: root.rtl ? "media-skip-backward-symbolic"
                                       : "media-skip-forward-symbolic"
                    label: root.local("التالي", "Next")
                    onActivated: root.player.Next()
                }
            }

            // Volume is SECONDARY. It used to run the popup's full width with
            // the same weight as the seek bar, so the surface read as two equal
            // timelines; inset and shortened, the seek bar keeps the hierarchy.
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: root.design.space5
                Layout.rightMargin: root.design.space5
                Layout.topMargin: root.design.space1
                visible: root.hasVolume
                spacing: root.design.space2

                MediaControl {
                    slotSize: 40
                    controlEnabled: root.hasVolume
                    iconName: root.volume <= 0.01
                        ? "audio-volume-muted-symbolic"
                        : "audio-volume-high-symbolic"
                    label: root.volume <= 0.01
                        ? root.local("إلغاء الكتم", "Unmute")
                        : root.local("كتم", "Mute")
                    onActivated: root.toggleMuted()
                }
                PC3.Slider {
                    id: volumeSlider
                    Layout.fillWidth: true
                    from: 0
                    to: 1
                    value: root.bounded(root.volume, 0, 1)
                    Accessible.name: root.local("مستوى الصوت", "Volume")
                    // Clamp to the slider's own 0..1 range: root.volume is the
                    // raw player value and setVolume's 1.5 headroom exists for
                    // mute-restore, so unclamped +0.05 steps could push a
                    // player to 150% while this slider reads 100%.
                    Accessible.onIncreaseAction:
                        root.setVolume(root.bounded(root.volume + 0.05, 0, 1))
                    Accessible.onDecreaseAction:
                        root.setVolume(root.bounded(root.volume - 0.05, 0, 1))
                    onMoved: volumeCommit.restart()
                    onPressedChanged: if (!pressed) { root.setVolume(value); }

                    Timer {
                        id: volumeCommit
                        interval: 60
                        repeat: false
                        onTriggered: root.setVolume(volumeSlider.value)
                    }
                }
                PC3.Label {
                    Layout.preferredWidth: 42
                    horizontalAlignment: Text.AlignRight
                    text: Math.round(root.bounded(volumeSlider.value, 0, 1) * 100)
                          + "%"
                    font.pixelSize: root.design.typeCaption
                    font.features: ({ "tnum": 1 })
                }
            }
        }
    }
}
