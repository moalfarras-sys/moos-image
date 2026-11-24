#!/usr/bin/env python3
"""Prove MoOS Arrange's automatic split on a private native virtual KWin.

Owner steering, 2026-11-23: opening two programs should split the screen, and four
should take a quarter each. This opens real Wayland client windows one at a time in
a private `kwin_wayland --virtual` (1280x720, no panel) with the actual script
loaded, and reads every window's frame geometry after each one arrives. It also
reads the KWin 6.8 API the script relies on (internalId, minSize, windowList,
windowAdded/windowRemoved, minimizedChanged), so a property that reads as undefined
fails here instead of silently disabling the feature. A copy with the mode forced
off is the negative: its windows must stay where KWin put them.

All writable state and sockets stay under a unique /tmp directory, retained as
evidence. The private bus has no service activation directories. Software
compositor evidence only: virtual 48px layer-shell panel; no physical display or input acceptance.

    python3 scripts/review/arrange-auto-native.py
"""
import json
import os
import pathlib
import sys
import subprocess
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "system_files/usr/share/kwin/scripts/moos-arrange/contents/code/main.js"
QDBUS = "/usr/lib64/qt6/bin/qdbus"

r = pathlib.Path(tempfile.mkdtemp(prefix="moos-arrange-auto-"))
print(r, flush=True)
for d in ("home", "runtime", "config", "cache", "data"):
    (r / d).mkdir(mode=0o700)
# The signed host also installs an enabled-by-default copy. Only the named
# source variant may respond to these private compositor events.
(r / "config/kwinrc").write_text("[Plugins]\nmoos-arrangeEnabled=false\n")
(r / "bus.conf").write_text(
    "<busconfig><type>session</type><listen>unix:path=" + str(r / "bus") + "</listen><auth>EXTERNAL</auth>"
    '<policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/>'
    "</policy></busconfig>")
env = {k: v for k, v in os.environ.items()
       if not k.startswith(("WAYLAND", "DBUS", "XDG_", "QT_", "DISPLAY"))}
env.update(HOME=str(r / "home"), XDG_RUNTIME_DIR=str(r / "runtime"), XDG_CONFIG_HOME=str(r / "config"),
           XDG_CACHE_HOME=str(r / "cache"), XDG_DATA_HOME=str(r / "data"),
           DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(r / "bus"), WAYLAND_DISPLAY="wayland-arrange-auto",
           QT_QPA_PLATFORM="wayland", LIBGL_ALWAYS_SOFTWARE="1", KWIN_WAYLAND_NO_PERMISSION_CHECKS="1",
           XDG_CONFIG_DIRS=str(r / "config"), KWIN_COMPOSE="Q", QT_QUICK_BACKEND="software",
           LANG="C.UTF-8", QT_FORCE_STDERR_LOGGING="1", QT_LOGGING_TO_CONSOLE="1")
# Without QT_FORCE_STDERR_LOGGING a script's console.info goes to the journal, not kwin.log.
procs = []


def qdbus(*args):
    return subprocess.run([QDBUS, *args], env=env, text=True, capture_output=True, timeout=5)


def load(name, source):
    path = r / (name + ".js")
    path.write_text(source)
    out = qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.loadScript", str(path), name)
    if out.returncode:
        raise RuntimeError(out.stderr)
    out = qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.start")
    if out.returncode:
        raise RuntimeError(out.stderr)
    time.sleep(0.6)


def open_window(title, minimum_height=0):
    client = r / (title + ".py")
    client.write_text(
        "from PySide6.QtWidgets import QApplication, QWidget\n"
        "a = QApplication([])\n"
        f"w = QWidget(); w.setWindowTitle({title!r})\n"
        f"w.setMinimumHeight({minimum_height}); w.resize(420, 300); w.show()\n"
        "a.exec()\n")
    proc = subprocess.Popen(["python3", str(client)], env=env,
                            stdout=(r / (title + ".log")).open("w"), stderr=subprocess.STDOUT)
    procs.append(proc)
    time.sleep(1.6)
    return proc


READ = ('const all = workspace.windowList().filter(w => /^MOOS_AUTO_/.test(w.caption)).map(w => ({'
        'title: w.caption, g: w.frameGeometry, client: w.clientGeometry, minimum: w.minSize, id: typeof w.internalId, min: w.minSize ? "size" : typeof w.minSize,'
        'minimizedChanged: !!w.minimizedChanged}));'
        'console.info("ARRANGE_AUTO_{tag} " + JSON.stringify({windows: all, '
        'added: !!(workspace.windowAdded && workspace.windowAdded.connect), '
        'removed: !!(workspace.windowRemoved && workspace.windowRemoved.connect)}));')


def run(variant):
    stamp = time.monotonic()
    source = SCRIPT.read_text().replace("registerShortcut(", "recordShortcut(").replace(
        "registerUserActionsMenu(", "recordMenu(")
    if variant == "off":
        forced = source.replace('let autoArrange = setting("AutoArrange", true);', "let autoArrange = false;")
        if forced == source:
            raise RuntimeError("cannot construct the forced-off negative")
        source = forced
    load("arrange_" + variant, "function recordShortcut() {}\nfunction recordMenu() {}\n" + source)
    opened = []
    for index in range(1, 5):
        minimum_height = 346 if variant == "limits" and index == 4 else 0
        opened.append(open_window(f"MOOS_AUTO_{variant}_{index}", minimum_height))
        load(f"read_{variant}_{index}", READ.replace("{tag}", f"{variant.upper()}_{index}"))
    if variant == "panel":
        for remaining in (3, 2):
            closed = opened.pop()
            closed.terminate()
            closed.wait(timeout=5)
            time.sleep(.5)
            load(f"close_{remaining}", READ.replace("{tag}", f"CLOSE_{remaining}"))
    load(f"unload_{variant}", 'console.info("unload");')
    qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.unloadScript", "arrange_" + variant)
    for proc in opened:
        proc.terminate()
        proc.wait(timeout=5)
    time.sleep(1.0)
    return round(time.monotonic() - stamp, 1)


try:
    bus = subprocess.Popen(["dbus-daemon", "--nofork", "--config-file=" + str(r / "bus.conf")], env=env,
                           stdout=(r / "bus.log").open("w"), stderr=subprocess.STDOUT)
    procs.append(bus)
    time.sleep(0.3)
    kwin = subprocess.Popen(["kwin_wayland", "--virtual", "--width", "1280", "--height", "720",
                             "--socket", env["WAYLAND_DISPLAY"], "--no-lockscreen", "--no-global-shortcuts",
                             "--no-kactivities"], env=env, stdout=(r / "kwin.log").open("w"),
                            stderr=subprocess.STDOUT)
    procs.append(kwin)
    for _ in range(80):
        if (r / "runtime" / env["WAYLAND_DISPLAY"]).is_socket():
            break
        if kwin.poll() is not None:
            raise RuntimeError("KWin exited " + str(kwin.returncode))
        time.sleep(0.1)
    else:
        raise RuntimeError("no private Wayland socket")
    time.sleep(0.6)
    installed = qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.isScriptLoaded", "moos-arrange")
    assert installed.returncode == 0 and installed.stdout.strip() == "false", (installed.stdout, installed.stderr)
    timing = {"on": run("on"), "off": run("off"), "limits": run("limits")}
    # Exercise the work-area exclusion through the real layer-shell protocol.
    panel_qml = r / "panel.qml"
    panel_qml.write_text("""import QtQuick
import org.kde.layershell as LS
Window {
    width: 1280; height: 48; visible: true
    LS.Window.anchors: LS.Window.AnchorTop | LS.Window.AnchorLeft | LS.Window.AnchorRight
    LS.Window.layer: LS.Window.LayerTop
    LS.Window.exclusionZone: 48
    LS.Window.scope: "moos-arrange-private-panel"
}""")
    client = r / "panel.py"
    client.write_text("""import sys
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine
app = QGuiApplication([])
engine = QQmlApplicationEngine()
engine.load(QUrl.fromLocalFile(sys.argv[1]))
assert engine.rootObjects()
app.exec()
""")
    panel = subprocess.Popen([sys.executable, str(client), str(panel_qml)],
                             env=env | {"QT_WAYLAND_SHELL_INTEGRATION": "layer-shell"},
                             stdout=(r / "panel.log").open("w"), stderr=subprocess.STDOUT)
    procs.append(panel)
    timing["panel"] = run("panel")
    found = {}
    for line in (r / "kwin.log").read_text(errors="replace").splitlines():
        if "ARRANGE_AUTO_" in line:
            tag, payload = line.split("ARRANGE_AUTO_", 1)[1].split(" ", 1)
            found[tag] = json.loads(payload)

    def geoms(tag):
        return [w["g"] for w in sorted(found[tag]["windows"], key=lambda w: w["title"])]

    two, four = geoms("ON_2"), geoms("ON_4")
    api = found["ON_1"]
    assert api["added"] and api["removed"], api
    assert all(w["id"] != "undefined" and w["minimizedChanged"] for w in api["windows"]), api
    assert all(abs(g["width"] - 628) <= 2 for g in two) and len({g["x"] for g in two}) == 2, two
    assert all(abs(g["width"] - 628) <= 2 and abs(g["height"] - 348) <= 2 for g in four), four
    assert len({(g["x"], g["y"]) for g in four}) == 4, four
    panel_four = geoms("PANEL_4")
    assert sorted((g["x"],g["y"],g["width"],g["height"]) for g in panel_four) == [
        (8,56,628,324),(8,388,628,324),(644,56,628,324),(644,388,628,324)], panel_four
    closed_two = geoms("CLOSE_2")
    assert sorted((g["x"],g["y"],g["width"],g["height"]) for g in closed_two) == [
        (8,56,628,656),(644,56,628,656)], closed_two
    before_four = geoms("LIMITS_3")
    after_four = geoms("LIMITS_4")
    limited = next(w for w in found["LIMITS_4"]["windows"] if w["title"].endswith("_4"))
    border_height = limited["g"]["height"] - limited["client"]["height"]
    assert limited["minimum"]["height"] <= 348 < limited["minimum"]["height"] + border_height, limited
    assert limited["client"]["height"] >= limited["minimum"]["height"], limited
    assert before_four == after_four[:3], ("a client cannot fit underneath its title bar", before_four, after_four)
    off_four = geoms("OFF_4")
    assert not any(abs(g["width"] - 628) <= 2 and abs(g["height"] - 348) <= 2 for g in off_four), off_four
    receipt = {"result": "PASS", "two": two, "four": four, "offFour": off_four, "constrainedFourth": limited, "panelFour": panel_four, "afterClosingTwo": closed_two, "seconds": timing,
               "api": {"internalId": api["windows"][0]["id"], "minSize": api["windows"][0]["min"]},
               "scope": "private virtual KWin, native Wayland clients; virtual 48px layer-shell panel; no physical display or input"}
    (r / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)
finally:
    for proc in reversed(procs):
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    print("EVIDENCE " + str(r), flush=True)
