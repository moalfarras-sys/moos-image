#!/usr/bin/env python3
"""Walk every page, sheet and shelf of the real Mo Store window offscreen and fail on any warning.

The window's pages after Discover load the first time they are shown, its sheets draw an app only
when one is handed to them, and an app's page draws a different card for every kind of app. A
binding that throws on one of those surfaces stays silent until a person opens it, so this walk
opens them all, in Arabic and in English, on the fixture data in tests/fixtures/mo-store (every
kind of app, installed and not, every compatibility reason, updates, permission documents, jobs and
three kinds of machine): Discover and its hero, Apps by kind, category and collection, Games, every
app's page, the screenshot viewer, the remove, permissions and review sheets, the job shelf in each
state, My apps, Updates (known, none, failed, unknown), Settings, Search, both deep links, keyboard
focus and the drop overlay. A fourth window has no index at all, only the signed catalogue, which
is what every Store paints first; it opens every catalogue entry's page. Any QML warning,
TypeError, ReferenceError, "Unable to assign" or binding loop fails.

The second test is the proof that the first one can fail: it walks a copy of the window in which
every view file carries a binding that throws only while that view is on screen, plus an "Unable to
assign" and a binding loop, and requires each of them in the log. A view the walk never shows, or a
log reader that stops seeing a class of warning, turns it red.

The review app id keeps the privileged bridge absent, so nothing is installed, removed, updated or
opened: the actions the walk presses answer with the window's own "needs the next MoOS update"
words. Nothing leaves the private HOME, and nothing is shown on a screen (offscreen platform).
"""
import concurrent.futures
import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "system_files/usr/share/moos/apps/store"
FIXTURES = ROOT / "tests/fixtures/mo-store"
RUNTIME = shutil.which("moos-qml-shell")

# The walker. It drives the window only through the members its own views use, one step at a
# time: `do` runs once, then the step waits (bounded) until `until` holds and `settle` ms have
# passed, so every page has drawn and every delegate has been made before the next step.
PROBE = r'''import QtQuick
import QtQuick.Controls

Item {
    id: harness
    property var app
    property var steps: []
    property int at: 0
    property bool acted: false
    property double since: 0

    function arg(name) {
        var hit = Qt.application.arguments.filter(a => a.indexOf("--" + name + "=") === 0)
        return hit.length ? hit[hit.length - 1].substring(name.length + 3) : ""
    }
    function readJson(path) {
        var request = new XMLHttpRequest()
        request.open("GET", "file://" + path, false)
        request.send()
        return JSON.parse(request.responseText)
    }
    function fixture(name) { return readJson(arg("fixtures") + "/" + name) }
    // Everything the window draws, the overlay with its sheets and the toast included.
    function root() {
        var item = app.contentItem
        while (item.parent) item = item.parent
        return item
    }
    function byName(name) {
        var found = search(root(), name)
        if (!found) throw new Error("no object named " + name)
        return found
    }
    // Whether a named part (a sheet, a shelf, the toast, the overlay) is on screen now.
    function shown(name) {
        var found = search(root(), name)
        return !!found && found.visible
    }
    // The toast's words, cleared before an action so the step reads only what that action said.
    // (A sheet or the toast enters the overlay the first time it opens.)
    function toastText() {
        var found = search(root(), "storeToast")
        return found && found.visible ? found.text : ""
    }
    function clearToast() {
        var found = search(root(), "storeToast")
        if (found) found.text = ""
    }
    function search(item, name) {
        if (!item) return null
        if (item.objectName === name) return item
        var kids = item.children || []
        for (var i = 0; i < kids.length; ++i) {
            var hit = search(kids[i], name)
            if (hit) return hit
        }
        return null
    }
    function scrollToEnd(name) {
        var flick = byName(name)
        flick.contentY = Math.max(0, flick.contentHeight - flick.height)
    }

    // A real RemoveSheet with a private recorder in place of its executor. No MoosStore
    // bridge is enabled: only the UI's default/explicit delete-data routing is exercised.
    property var recordedRemoveSheet
    property var recordedRemoveCalls: []
    function matchingItems(item, predicate) {
        var found = []
        for (var child of Array.from(item.children || [])) {
            if (predicate(child)) found.push(child)
            found = found.concat(matchingItems(child, predicate))
        }
        return found
    }
    function openRecordedWindowsRemoval() {
        var recorder = {}
        for (var key of Object.keys(app)) recorder[key] = app[key]
        recorder.bridgeHas = function(name) { return name === "removeAppData" }
        recorder.jobIsActive = function() { return false }
        recorder.removeSelected = function(item) { recordedRemoveCalls.push({ id: item.id, delete_data: false }) }
        recorder.removeSelectedWithData = function(item) { recordedRemoveCalls.push({ id: item.id, delete_data: true }) }
        var component = Qt.createComponent(arg("src").replace(/main\.qml$/, "RemoveSheet.qml"))
        if (component.status !== Component.Ready) throw new Error(component.errorString())
        recordedRemoveCalls = []
        recordedRemoveSheet = component.createObject(app.contentItem, {
            win: recorder, app: { id: "windows-removal-probe", name: "Removal probe", kind: "windows", installed: true }
        })
        if (!recordedRemoveSheet) throw new Error("the recorded RemoveSheet was not created")
        recordedRemoveSheet.open()
    }
    function removeChoiceCount() {
        return matchingItems(recordedRemoveSheet.contentItem,
                             item => item.modelData === true || item.modelData === false).length
    }
    function pressRecordedRemoval(withData) {
        var buttons = matchingItems(recordedRemoveSheet.contentItem,
            item => String(item).indexOf("ActionButton_") >= 0 && item.destructive === true)
        if (buttons.length !== 1) throw new Error("the RemoveSheet must have exactly one Remove button")
        recordedRemoveSheet.withData = withData
        buttons[0].triggered()
    }
    function closeRecordedRemoval() {
        recordedRemoveSheet.close()
        recordedRemoveSheet.destroy()
    }

    Component.onCompleted: {
        var component = Qt.createComponent(arg("src"))
        if (component.status !== Component.Ready) {
            console.error("STORE WALK FAILED: " + component.errorString()); Qt.exit(2); return
        }
        app = component.createObject(null, { width: Number(arg("w")), height: Number(arg("h")) })
        if (!app) { console.error("STORE WALK FAILED: the window was not created"); Qt.exit(2); return }
        steps = readJson(arg("walk"))
        tick.start()
    }
    Timer {
        id: tick
        interval: 30
        repeat: true
        onTriggered: {
            if (harness.at >= harness.steps.length) {
                stop()
                console.warn("STORE WALK DONE " + harness.steps.length)
                Qt.exit(0)
                return
            }
            var step = harness.steps[harness.at]
            var now = Date.now()
            try {
                if (!harness.acted) {
                    harness.acted = true
                    harness.since = now
                    if (step["do"]) (new Function("app", "harness", step["do"]))(harness.app, harness)
                    return
                }
                var reached = !step.until
                    || (new Function("app", "harness", "return (" + step.until + ")"))(harness.app, harness)
                if (reached && now - harness.since >= step.settle) {
                    console.warn("STORE WALK STEP " + harness.at + " " + step.label)
                    harness.at += 1
                    harness.acted = false
                } else if (!reached && now - harness.since > step.timeout) {
                    console.error("STORE WALK FAILED: " + step.label + " never reached: " + step.until)
                    Qt.exit(3)
                }
            } catch (error) {
                console.error("STORE WALK FAILED: " + step.label + ": " + error)
                Qt.exit(3)
            }
        }
    }
}
'''

# The windows the walk runs in: the owner's (Arabic, dark, 2.5x, a station with every engine
# ready), a fresh English install on a light scheme with nothing set up yet, a bare one with no
# updates, facts or settings files, an older machine document and a live job at launch, and the
# first frame of any Store: the signed catalogue alone, before (or without) an index.
VARIANTS = (
    {"name": "ar-station", "language": "ar", "scheme": "MoOSUI2Arena", "scale": "2.5", "size": (1280, 800),
     "machine": "machine-station.json", "updates": "updates-known.json", "facts": True,
     "settings": "settings.json", "job": None, "index": True},
    {"name": "en-fresh", "language": "en", "scheme": "MoOSUI2AuroraLight", "scale": "1", "size": (1536, 864),
     "machine": "machine-fresh.json", "updates": "updates-none.json", "facts": True,
     "settings": "settings-off.json", "job": None, "index": True},
    {"name": "en-bare", "language": "en", "scheme": "MoOSUI2Arena", "scale": "1", "size": (1280, 800),
     "machine": "machine-old.json", "updates": None, "facts": False, "settings": None,
     "job": "job-running.json", "index": True, "building": True},
    {"name": "ar-catalogue", "language": "ar", "scheme": "MoOSUI2AuroraLight", "scale": "1", "size": (1280, 800),
     "machine": "machine-station.json", "updates": None, "facts": False, "settings": None,
     "job": None, "index": False},
)
# The signed catalogue the window paints before the index (main.qml reads this exact path).
CATALOGUE = Path("/usr/share/moos/store/catalog.json")

# A log line that is a warning about QML: a file position, the qml console category (the walker's
# own markers aside) or one of the words Qt uses for a broken binding.
QML_POSITION = re.compile(r"\.qml:\d+")
BROKEN = re.compile(r"TypeError|ReferenceError|Unable to assign|Cannot assign|is not defined|"
                    r"Binding loop|is not a type|Cannot read property|Cannot call method|"
                    r"Unable to determine callable overload|Detected anchors on an item")


def problems(log: str) -> list[str]:
    found = []
    for line in log.splitlines():
        text = line.strip()
        if not text or "STORE WALK STEP" in text or "STORE WALK DONE" in text:
            continue
        if QML_POSITION.search(text) or BROKEN.search(text) or text.startswith("qml:") \
                or "STORE WALK FAILED" in text:
            found.append(text)
    return found


def family(app: dict) -> str:
    kind = app.get("kind") or ""
    return {"webapp": "web", "web": "web", "windows": "windows", "android": "android"}.get(kind, "linux")


def js(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def catalogue_walk() -> list[dict]:
    """The window with the signed catalogue only: every page, every entry's page, both sheets.
    The catalogue is the installed one, so the steps name no app: they take them by position."""
    try:
        entries = len(json.loads(CATALOGUE.read_text(encoding="utf-8")).get("apps", []))
    except (OSError, ValueError):
        entries = 0
    steps: list[dict] = []

    def step(label, do=None, until=None, settle=140, timeout=6000):
        steps.append({"label": label, "do": do, "until": until, "settle": settle, "timeout": timeout})

    step("the catalogue is read", until="app.allApps.length > 0 && !app.indexReady", timeout=15000)
    step("Discover from the catalogue", "app.navigate('discover')",
         "app.page === 'discover' && app.featured.length > 0 && app.collections.length > 0", settle=600)
    for card in range(1, 5):
        step(f"the hero's card {card + 1}",
             f"if (app.featured.length > {card}) harness.byName('heroCarousel').currentIndex = {card}",
             f"app.featured.length <= {card} || harness.byName('heroCarousel').currentIndex === {card}",
             settle=400)
    step("the foot of Discover", "harness.scrollToEnd('discoverFlick')", settle=400)
    step("Apps", "app.navigate('apps')", "app.page === 'apps' && app.visibleApps.length > 0", settle=400)
    for name in ("web", "windows", "android", "linux"):
        step(f"Apps: {name}", f"app.openKind('{name}')",
             f"app.activeKind === '{name}' && app.visibleApps.every(a => a.family === '{name}')", settle=250)
    step("Games", "app.navigate('games')", "app.page === 'games'", settle=300)
    for position in range(entries):
        step(f"the page of catalogue entry {position + 1}",
             f"if (app.allApps.length > {position}) app.openDetails(app.allApps[{position}])",
             f"app.allApps.length <= {position}"
             f" || (app.page === 'app' && app.selectedApp.id === app.allApps[{position}].id)", settle=160)
    step("the remove sheet", "app.openRemove(app.allApps[0])", "harness.shown('removeSheet')", settle=250)
    step("the remove sheet closes", "app.escapeAction()", "!harness.shown('removeSheet')")
    step("the permissions sheet", "app.openPermissions(app.allApps[0])", "harness.shown('permissionsSheet')",
         settle=250)
    step("the permissions sheet closes", "app.escapeAction()", "!harness.shown('permissionsSheet')")
    step("the review of one entry", "app.installOne(app.allApps[0])", "harness.shown('reviewSheet')", settle=250)
    step("the review closes", "app.escapeAction(); app.clearPicks()", "!harness.shown('reviewSheet')")
    step("a bundle", "if (app.bundles.length > 0) app.addMany(app.bundles[0].apps)",
         "app.bundles.length === 0 || app.pickCount > 0", settle=300)
    step("the review of the bundle", "if (app.pickCount > 0) app.openReview()",
         "app.pickCount === 0 || harness.shown('reviewSheet')", settle=300)
    step("the review closes", "app.escapeAction(); app.clearPicks()", "!harness.shown('reviewSheet')")
    step("My apps, empty", "app.navigate('library')", "app.page === 'library'", settle=300)
    step("Updates, never checked", "app.navigate('updates')",
         "app.page === 'updates' && app.updatesState === 'failed'", settle=300)
    step("Settings", "app.navigate('settings')", "app.page === 'settings'", settle=300)
    step("the foot of Settings", "harness.scrollToEnd('settingsFlick')", settle=250)
    step("search", "app.searchFor('a')", "app.page === 'search' && app.searchResults.length > 0", settle=300)
    step("a search with no result", "app.searchFor('zzqx')",
         "app.query === 'zzqx' && app.searchResults.length === 0", settle=300)
    step("Discover again", "app.navigate('discover')", "app.page === 'discover'", settle=300)
    return steps


def walk(variant: dict) -> list[dict]:
    """The steps for one window, with the counts it must show taken from the fixture itself."""
    if not variant["index"]:
        return catalogue_walk()
    index = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
    apps = index["apps"]
    by_id = {app["id"]: app for app in apps}
    listed = [app for app in apps if app.get("listed", True) is not False]
    installed = [app for app in apps if app.get("installed") is True]
    featured = [entry for entry in index["featured"]
                if entry["app"] in by_id and by_id[entry["app"]].get("listed", True) is not False
                and by_id[entry["app"]]["compat"]["verdict"] != "blocked"]
    collections = [row for row in index["collections"]
                   if sum(1 for member in row["apps"]
                          if member in by_id and by_id[member].get("listed", True) is not False) >= 3]
    games = [app for app in listed if app.get("cat") == "fun" and family(app) == "linux"]
    steps: list[dict] = []

    def step(label, do=None, until=None, settle=140, timeout=6000):
        steps.append({"label": label, "do": do, "until": until, "settle": settle, "timeout": timeout})

    def bridgeless(label, call, busy_words=None, words="app.needsUpdateText"):
        """An action the review window has no bridge for: it must say so in words and do nothing.
        While a job runs, an action that waits for it says that instead (`busy_words`), or holds
        silently with its control disabled (None: not pressed in that window)."""
        words = words if variant["job"] is None else busy_words
        if words is None:
            return
        step(label, f"harness.clearToast(); {call}",
             f"harness.toastText() === {words}")

    waiting = "app.local('انتظر اكتمال العملية الحالية', 'Wait for the current operation')"

    step("the index is read", until=f"app.indexReady && app.allApps.length === {len(apps)}", timeout=15000)
    step("Discover", "app.navigate('discover')",
         f"app.page === 'discover' && app.featured.length === {len(featured)}"
         f" && app.collections.length === {len(collections)}", settle=600)
    for card in range(1, len(featured)):
        step(f"the hero's card {card + 1}", f"harness.byName('heroCarousel').currentIndex = {card}",
             f"harness.byName('heroCarousel').currentIndex === {card}", settle=500)
    step("the foot of Discover", "harness.scrollToEnd('discoverFlick')", settle=400)
    # Keyboard focus on the rail, the way Tab out of the grid lands there: its ring must draw.
    step("keyboard focus", "app.requestActivate(); app.focusFirstNavItem(Qt.TabFocusReason)",
         "app.activeFocusItem !== null && app.activeFocusItem.activeFocus", settle=250)
    step("Apps", "app.navigate('apps')", f"app.page === 'apps' && app.visibleApps.length === {len(listed)}",
         settle=400)
    for name in ("web", "windows", "android", "linux"):
        count = sum(1 for app in listed if family(app) == name)
        step(f"Apps: {name}", f"app.openKind('{name}')",
             f"app.activeKind === '{name}' && app.visibleApps.length === {count}"
             f" && app.visibleApps.every(a => a.family === '{name}')", settle=300)
    step("Apps: a category", "app.openCategory('art')",
         "app.activeCategory === 'art' && app.visibleApps.every(a => a.cat === 'art')", settle=300)
    step("Apps by name", "app.sortMode = 'name'", "app.sortMode === 'name'", settle=250)
    step("Apps by recommendation", "app.sortMode = 'recommended'", "app.sortMode === 'recommended'")
    step("a collection", "app.openCollection('create')",
         "app.activeCollection === 'create' && app.visibleApps.length > 0", settle=300)
    step("the end of the grid", "harness.scrollToEnd('appGrid')", settle=250)
    step("Games", "app.navigate('games')",
         f"app.page === 'games' && app.visibleApps.length === {len(games)}", settle=400)
    step("back from Games", "app.goBack()", "app.page === 'discover'")

    for app in apps:
        ready = "'ready'" if app.get("details") else "'none'"
        step(f"the page of {app['id']}", f"app.openDetails(app.appById({js(app['id'])}))",
             f"app.page === 'app' && app.selectedApp.id === {js(app['id'])} && app.detailsState === {ready}",
             settle=220)
    step("the foot of an app's page", "harness.scrollToEnd('detailFlick')", settle=250)
    step("an app with screenshots", "app.openDetails(app.appById('org.example.Office'))",
         "app.selectedApp.id === 'org.example.Office' && app.detailsState === 'ready'"
         " && app.selectedDetails.screenshots.length === 3", settle=300)
    step("the screenshot viewer", "app.openScreenshots(app.selectedDetails.screenshots, 0)",
         "harness.shown('screenshotViewer')", settle=300)
    step("the last screenshot", "app.openScreenshots(app.selectedDetails.screenshots, 2)",
         "harness.shown('screenshotViewer')", settle=250)
    step("the viewer closes", "app.escapeAction()", "!harness.shown('screenshotViewer')")

    removable = ("org.example.Paint", "chat-web", "notes-win", "org.example.reader", "my-tool",
                 "cli-agent", "photo-tool", "org.example.Shared")
    for app_id in removable:
        step(f"the remove sheet for {app_id}", f"app.openRemove(app.appById({js(app_id)}))",
             "harness.shown('removeSheet')", settle=250)
        step("the remove sheet closes", "app.escapeAction()", "!harness.shown('removeSheet')")
    bridgeless("remove with data, without the bridge",
               "app.removeSelectedWithData(app.appById('org.example.Paint'))", waiting)

    for app_id in ("org.example.Paint", "chat-web", "notes-win", "org.example.reader", "org.example.Music"):
        step(f"the permissions of {app_id}",
             f"app.openPermissions(app.appById({js(app_id)})); app.permissionAppId = {js(app_id)};"
             " app.permissionRequestedAt = 0; app.readPermissions()",
             f"harness.shown('permissionsSheet') && app.permissionState === 'ready'"
             f" && app.permissionDoc.id === {js(app_id)}", settle=250)
        step("the permissions sheet closes", "app.escapeAction()", "!harness.shown('permissionsSheet')")
    step("permissions the shell cannot read yet", "app.openPermissions(app.appById('org.example.Browser'))",
         "harness.shown('permissionsSheet') && app.permissionState === 'unsupported'", settle=250)
    step("the permissions sheet closes", "app.escapeAction()", "!harness.shown('permissionsSheet')")
    step("permissions of an app not installed", "app.openPermissions(app.appById('org.example.Office'))",
         "harness.shown('permissionsSheet') && app.permissionState === 'facts'", settle=250)
    step("the permissions sheet closes", "app.escapeAction()", "!harness.shown('permissionsSheet')")
    bridgeless("a permission change, without the bridge",
               "app.setPermission(app.appById('org.example.Paint'), 'network', 'deny')")

    picks = ["org.example.Office", "chat-web", "tool-win", "photo-tool", "org.example.podcasts", "cli-two",
             "desktop-vendor"]
    # The selection shelf steps aside while a job runs: the job shelf has the foot of the window.
    shelf = "harness.shown('selectionShelf')" if variant["job"] is None else "!harness.shown('selectionShelf')"
    step("a selection", " ".join(f"app.setPicked({js(i)}, true);" for i in picks),
         f"app.pickCount === {len(picks)} && {shelf}", settle=400)
    step("the review of a selection", "app.openReview()", "harness.shown('reviewSheet')", settle=300)
    step("the review closes", "app.escapeAction(); app.clearPicks()",
         "!harness.shown('reviewSheet') && app.pickCount === 0")
    for app_id in ("vendor-site", "desktop-vendor", "org.example.Kart"):
        step(f"the review of {app_id}", f"app.installOne(app.appById({js(app_id)}))",
             "harness.shown('reviewSheet') && app.pickCount === 1", settle=250)
        step("the review closes", "app.escapeAction(); app.clearPicks()",
             "!harness.shown('reviewSheet') && app.pickCount === 0")

    if variant["job"] is None:
        for name in ("job-running.json", "job-indeterminate.json", "job-failed.json", "job-success.json"):
            step(f"the job shelf: {name}", f"app.job = harness.fixture({js(name)})",
                 "harness.shown('jobShelf')", settle=350)
        step("a job on the page of the app it installs",
             "app.job = harness.fixture('job-running.json'); app.openDetails(app.appById('org.example.Office'))",
             "app.selectedApp.id === 'org.example.Office' && app.appJobState(app.selectedApp) !== ''", settle=300)
        step("no job", "app.job = ({})", "!app.jobIsActive() && !app.jobIsTerminal()", settle=400)
    else:
        step("the job running at launch", "app.openDetails(app.appById('org.example.Office'))",
             "app.job.job_id === 'fixture-running' && app.jobIsActive() && harness.shown('jobShelf')"
             " && app.appJobState(app.selectedApp) !== ''", settle=300)
    step("a message", "app.flash('—')", "harness.shown('storeToast')")

    step("My apps", "app.navigate('library')",
         f"app.page === 'library' && app.installedApps.length === {len(installed)}", settle=400)
    for name in ("web", "windows", "android", "linux", "all"):
        count = len(installed) if name == "all" else sum(1 for app in installed if family(app) == name)
        step(f"My apps: {name}", f"app.libraryKind = '{name}'",
             f"app.libraryKind === '{name}' && app.libraryApps.length === {count}", settle=250)

    step("Updates", "app.navigate('updates')", "app.page === 'updates' && app.updatesState !== 'unknown'",
         settle=400)
    for name, state in (("updates-known.json", "known"), ("updates-none.json", "known"),
                        ("updates-failed.json", "failed")):
        step(f"Updates: {name}",
             f"app.updates = harness.fixture({js(name)}); app.updatesState = '{state}'",
             f"app.updatesState === '{state}'", settle=300)
    step("Updates: never checked", "app.updates = ({}); app.updatesState = 'unknown'",
         "app.updatesState === 'unknown'", settle=250)
    step("Updates: a check without the bridge", "app.checkUpdates()", "app.updatesState === 'failed'")
    step("Updates: back to known", "app.updates = harness.fixture('updates-known.json'); app.updatesState = 'known'",
         "app.updatesState === 'known' && app.updateItems().length === 2", settle=300)
    step("the foot of Updates", "harness.scrollToEnd('updatesFlick')", settle=250)
    bridgeless("an update, without the bridge", "app.updateOne(app.appById('org.example.Paint'))")
    bridgeless("update all, without the bridge", "app.updateAll()",
               words="app.local('تعذّر بدء التحديث', 'Could not start updates')")
    # The switch follows the settings file, never an older check's copy of it (updates.json
    # records what the backend read when that check started).
    stale = "updates-none.json" if variant["settings"] == "settings.json" else "updates-known.json"
    if variant["settings"]:
        step("the switch keeps the person's choice over a check's older copy",
             f"app.adoptAutoUpdates(harness.fixture({js(stale)}))",
             "app.autoUpdates === " + ("true" if variant["settings"] == "settings.json" else "false"),
             settle=200)
    step("the automatic switch, without the bridge",
         "harness.clearToast(); app.setAutoUpdates(!app.autoUpdates)",
         "harness.toastText() === app.needsUpdateText"
         " && !app.autoUpdatesPending")

    step("Settings", "app.navigate('settings')", "app.page === 'settings'", settle=400)
    step("the foot of Settings", "harness.scrollToEnd('settingsFlick')", settle=250)
    step("no pictures from the internet", "app.setRemotePictures(false)", "!app.remotePictures", settle=250)
    step("an app's page without internet pictures", "app.openDetails(app.appById('org.example.Paint'))",
         "app.page === 'app' && app.detailsState === 'ready'", settle=300)
    step("pictures from the internet again", "app.setRemotePictures(true)", "app.remotePictures")

    step("search in Arabic", "app.searchFor('الرسم')",
         "app.page === 'search' && app.searchResults.length > 0"
         " && app.searchResults[0].id === 'org.example.Paint'", settle=350)
    step("search with Arabic letter forms", "app.searchFor('أداة الصور')",
         "app.searchResults.length > 0 && app.searchResults[0].id === 'photo-tool'", settle=300)
    step("search in English", "app.searchFor('office')",
         "app.searchResults.length > 0 && app.searchResults[0].id === 'org.example.Office'", settle=300)
    step("a search with no result", "app.searchFor('zzqx')",
         "app.page === 'search' && app.query === 'zzqx' && app.searchResults.length === 0", settle=300)
    step("back from search", "app.goBack()", "app.page !== 'search'")

    step("a link to an app", "app.activateRequested(['moos-qml-shell', '--', '--open-app=chat-web'])",
         "app.page === 'app' && app.selectedApp.id === 'chat-web'", settle=250)
    step("a link to a page", "app.activateRequested(['moos-qml-shell', '--', '--open-page=library'])",
         "app.page === 'library'", settle=250)
    step("a file over the window", "harness.byName('dropOverlay').visible = true",
         "harness.shown('dropOverlay')", settle=250)
    step("the file leaves", "harness.byName('dropOverlay').visible = false", "!harness.shown('dropOverlay')")
    step("Discover again", "app.navigate('discover')", "app.page === 'discover'", settle=300)
    return steps


def palette(config: Path, scheme: str) -> None:
    """kdeglobals: the MoOS defaults with one scheme merged in, and the icon theme that matches it."""
    text = (ROOT / "system_files/etc/xdg/kdeglobals").read_text(encoding="utf-8") + "\n" + \
        (ROOT / f"system_files/usr/share/color-schemes/{scheme}.colors").read_text(encoding="utf-8")
    text = re.sub(r"(?m)^ColorScheme=.*$", f"ColorScheme={scheme}", text)
    text = re.sub(r"(?m)^Theme=MoOSUI2.*$", f"Theme={scheme}", text)
    (config / "kdeglobals").write_text(text, encoding="utf-8")


def copy_fixtures(target: Path) -> None:
    """The fixture data, with its own path and the present moment written in."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    shutil.copytree(FIXTURES, target)
    for path in target.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("@FIXTURES@", str(target)).replace("@NOW@", now), encoding="utf-8")


def run_walk(variant: dict, store: Path, work: Path, steps: list[dict] | None = None) -> subprocess.CompletedProcess:
    work.mkdir(parents=True)
    config = work / "config"
    config.mkdir()
    palette(config, variant["scheme"])
    runtime = work / "run"
    runtime.mkdir(mode=0o700)
    data = work / "store-cache"
    copy_fixtures(data)
    walk_file = work / "walk.json"
    walk_file.write_text(json.dumps(walk(variant) if steps is None else steps,
                                    ensure_ascii=False), encoding="utf-8")
    probe = work / "walk.qml"
    probe.write_text(PROBE, encoding="utf-8")
    width, height = variant["size"]
    # Without an index, the launcher's build has finished and left none: the catalogue stays. The
    # bare window's build never says it is done, so its rail keeps saying the catalogue is building.
    index = data / "index.json" if variant["index"] else work / "no-index.json"
    ready = work / "index.ready" if variant.get("building") else ""
    arguments = [f"--src={(store / 'main.qml').as_uri()}", f"--walk={walk_file}", f"--fixtures={data}",
                 f"--w={width}", f"--h={height}", f"--cache={data}", f"--index={index}",
                 f"--machine={data / variant['machine']}", f"--ready={ready}"]
    arguments.append(f"--updates={data / variant['updates']}" if variant["updates"] else "--updates=")
    arguments.append(f"--facts={data / 'facts.json'}" if variant["facts"] else "--facts=")
    arguments.append(f"--settings={data / variant['settings']}" if variant["settings"] else "--settings=")
    arguments.append(f"--job={data / variant['job']}" if variant["job"] else f"--job={work / 'no-job.json'}")
    locale = "ar_SA.UTF-8" if variant["language"] == "ar" else "en_US.UTF-8"
    env = {
        "PATH": "/usr/bin:/bin", "HOME": str(work), "XDG_CONFIG_HOME": str(config),
        "XDG_CONFIG_DIRS": str(config), "XDG_CACHE_HOME": str(work / "cache"),
        "XDG_DATA_HOME": str(work / "data"), "XDG_RUNTIME_DIR": str(runtime),
        "XDG_DATA_DIRS": f"{ROOT / 'system_files/usr/share'}:/usr/share",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(work / "no-bus"),
        "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software", "QT_QPA_PLATFORMTHEME": "kde",
        "XDG_CURRENT_DESKTOP": "KDE", "KDE_SESSION_VERSION": "6", "QT_QUICK_CONTROLS_STYLE": "Basic",
        "QML_DISABLE_DISK_CACHE": "1", "QML_XHR_ALLOW_FILE_READ": "1", "QT_FORCE_STDERR_LOGGING": "1",
        "QT_SCALE_FACTOR": variant["scale"], "QML_IMPORT_PATH": str(ROOT / "system_files/usr/lib64/qt6/qml"),
        "LANG": locale, "LC_ALL": locale, "LANGUAGE": variant["language"],
    }
    try:
        return subprocess.run([RUNTIME, "--app-id", "org.moos.store.review", "--icon", "moos-store",
                               "--qml", str(probe), "--", *arguments],
                              env=env, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired as expired:
        return subprocess.CompletedProcess(expired.cmd, -9, "", f"STORE WALK FAILED: timed out\n{expired.stderr or ''}")


def lifecycle_contract_walk() -> list[dict]:
    """Exercise the missing installed kinds and the real removal choice, not just their pages.

    The catalogue fixture's vendor app is deliberately uninstalled. Installed, legacy-kind and
    no-longer-listed copies must still Open/Remove through the existing backend authority.
    """
    steps = [{"label": "the lifecycle index is read", "until": "app.indexReady", "settle": 200, "timeout": 15000}]
    for label, extra in (("catalogue vendor", {"installed": True, "update_available": False}),
                         ("legacy vendor kind", {"installed": True, "kind": "", "update_available": False}),
                         ("retired vendor", {"installed": True, "kind": "vendor", "listed": False,
                                             "installable": False, "install": None, "update_available": False})):
        probe = "Object.assign({}, app.appById('desktop-vendor'), " + js(extra) + ")"
        steps.append({"label": label + " can open and remove", "until":
                      "(function(item) { return app.appKind(item) === 'vendor'"
                      " && app.hasRunnableLifecycle(item) && app.canRemove(item)"
                      " && app.primaryAction(item) === 'open' })((" + probe + "))",
                      "settle": 100, "timeout": 1500})
    steps.extend([
        {"label": "the Windows removal sheet opens", "do": "harness.openRecordedWindowsRemoval()",
         "until": "harness.recordedRemoveSheet.visible", "settle": 250, "timeout": 3000},
        {"label": "Windows has both choices and defaults to keep",
         "until": "harness.removeChoiceCount() === 2 && harness.recordedRemoveSheet.keepPossible"
                  " && harness.recordedRemoveSheet.withData === false", "settle": 100, "timeout": 1500},
        {"label": "default removal sends keep-data", "do": "harness.pressRecordedRemoval(false)",
         "until": "harness.recordedRemoveCalls.length === 1"
                  " && harness.recordedRemoveCalls[0].delete_data === false", "settle": 100, "timeout": 1500},
        {"label": "explicit data removal sends delete-data", "do": "harness.pressRecordedRemoval(true)",
         "until": "harness.recordedRemoveCalls.length === 2"
                  " && harness.recordedRemoveCalls[1].delete_data === true", "settle": 100, "timeout": 1500},
        {"label": "the recorded sheet closes", "do": "harness.closeRecordedRemoval()",
         "settle": 100, "timeout": 1500},
    ])
    return steps


@unittest.skipUnless(RUNTIME, "requires the native MoOS Qt runtime (moos-qml-shell)")
class StoreLifecycleContract(unittest.TestCase):
    def test_installed_vendor_actions_and_actual_windows_removal_choices(self):
        steps = lifecycle_contract_walk()
        with tempfile.TemporaryDirectory(prefix="mo-store-lifecycle-") as directory:
            for variant in VARIANTS[:2]:
                with self.subTest(window=variant["name"]):
                    result = run_walk(variant, STORE, Path(directory) / variant["name"], steps=steps)
                    self.assertEqual(result.returncode, 0, result.stderr[-6000:])
                    self.assertIn(f"STORE WALK DONE {len(steps)}", result.stderr)
                    self.assertEqual(problems(result.stderr), [], result.stderr[-6000:])


# One planted fault per view file: a binding that throws only while that view is on screen, so it
# reaches the log only if the walk shows the view. `visible` is every root's own property, except
# for the page-arrival helper, which is never drawn and acts while its page is `shown`.
PLANTED = "    readonly property int walkPlanted: {when} ? win.walkPlantedMissingMember.length : 0\n"
PLANTED_WHEN = {"PageEnter.qml": "shown"}
EXTRA = {
    # Two more classes of warning the reader must see, in views the walk shows.
    "SettingsPage.qml": "    property string walkPlantedText: visible ? undefined : \"\"\n",
    "SearchPage.qml": "    property int walkPlantedLoopA: walkPlantedLoopB + 1\n"
                      "    property int walkPlantedLoopB: walkPlantedLoopA + 1\n",
}


def planted_copy(target: Path) -> dict[str, int]:
    """A copy of the window with the faults planted; for each view, the line its fault is on."""
    shutil.copytree(STORE, target)
    lines = {}
    marker = "    required property var win\n"
    for path in sorted(target.glob("*.qml")):
        if path.name == "main.qml":
            continue
        text = path.read_text(encoding="utf-8")
        if text.count(marker) != 1:
            raise AssertionError(f"{path.name}: its root no longer declares `required property var win` once")
        lines[path.name] = text[:text.index(marker)].count("\n") + 2
        planted = PLANTED.format(when=PLANTED_WHEN.get(path.name, "visible"))
        path.write_text(text.replace(marker, marker + planted + EXTRA.get(path.name, "")), encoding="utf-8")
    return lines


@unittest.skipUnless(RUNTIME, "requires the native MoOS Qt runtime (moos-qml-shell)")
class StorePagesWalk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """All four walks at once: the three windows and the planted copy."""
        cls.scratch = tempfile.TemporaryDirectory(prefix="mo-store-walk-")
        work = Path(cls.scratch.name)
        cls.planted = planted_copy(work / "planted-store")
        jobs = [(variant["name"], variant, STORE) for variant in VARIANTS]
        jobs.append(("planted", VARIANTS[0], work / "planted-store"))
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = {name: pool.submit(run_walk, variant, store, work / name) for name, variant, store in jobs}
            cls.results = {name: future.result() for name, future in futures.items()}

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def test_every_page_sheet_and_shelf_loads_without_a_warning(self):
        for variant in VARIANTS:
            result = self.results[variant["name"]]
            with self.subTest(window=variant["name"]):
                found = problems(result.stderr)
                self.assertEqual(found, [], f"{variant['name']}: the window logged warnings:\n"
                                 + "\n".join(found[:40]))
                self.assertIn(f"STORE WALK DONE {len(walk(variant))}", result.stderr,
                              f"{variant['name']}: the walk did not finish:\n{result.stderr[-3000:]}")
                self.assertEqual(result.returncode, 0, result.stderr[-3000:])

    def test_the_walk_reaches_every_view_and_sees_each_kind_of_warning(self):
        self.assertGreaterEqual(len(self.planted), 40, "the window's view files were not found")
        result = self.results["planted"]
        found = problems(result.stderr)
        # Each view's own fault, on its own line: nothing else in the copy can produce it.
        missed = [name for name, line in self.planted.items()
                  if not any(f"/planted-store/{name}:{line}:" in text and "TypeError" in text for text in found)]
        self.assertEqual(missed, [], "views the walk never showed (or whose fault the reader missed):\n"
                         + result.stderr[-4000:])
        self.assertTrue(any("Unable to assign" in text and "/planted-store/SettingsPage.qml:" in text
                            for text in found), "the reader no longer sees an \"Unable to assign\" warning")
        self.assertTrue(any("Binding loop" in text and "walkPlantedLoop" in text for text in found),
                        "the reader no longer sees a binding loop")
        self.assertIn("STORE WALK DONE", result.stderr, "the planted walk did not finish")


if __name__ == "__main__":
    unittest.main()
