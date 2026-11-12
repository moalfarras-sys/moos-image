#!/usr/bin/env python3
"""Exercise the real KWin effect on a private bus/display, never the owner bus."""
import argparse
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "system_files/usr/share/kwin/effects/moos-quiet-lift"
TRACE = r'''
"use strict";
const nativeAnimate = animate, nativeCancel = cancel, nativeRedirect = redirect;
animate = function(o) { const ids = nativeAnimate(o); console.info('MOOS_NATIVE_ANIMATE ' +
    JSON.stringify({duration:o.duration,ids:ids})); return ids; };
cancel = function(ids) { console.info('MOOS_NATIVE_CANCEL '+JSON.stringify(ids)); return nativeCancel(ids); };
redirect = function(ids, direction) {const ok = nativeRedirect(ids,direction);
    console.info('MOOS_NATIVE_REDIRECT '+ok); return ok;};
effect.animationEnded.connect(function(w) {console.info('MOOS_NATIVE_END');});
effects.windowAdded.connect(function(w) {console.info('MOOS_NATIVE_WINDOW '+JSON.stringify({
    visible:w.visible,managed:w.managed,normal:w.normalWindow,dialog:w.dialog,
    fullScreen:w.fullScreen,fullEffect:effects.hasActiveFullScreenEffect,
    time:animationTime(220)}));});
'''
CLIENT = '''from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QTimer
import sys
app=QApplication([])
w=QWidget(); w.resize(640,480); w.setWindowTitle("MoOS native motion qualification")
w.show(); QTimer.singleShot(int(sys.argv[1]),w.close)
QTimer.singleShot(int(sys.argv[1])+500,app.quit)
app.exec()
print("MOOS_NATIVE_CLIENT_EXECUTED")
'''


def private_environment(folder):
    # Set these on dbus-run-session itself. Setting only KWin's environment
    # leaves D-Bus-activated processes able to read or write the owner's state.
    env = {key: value for key, value in os.environ.items() if key in ("PATH", "LANG")}
    env.update({"HOME":str(folder/"home"), "XDG_CONFIG_HOME":str(folder/"config"),
                "XDG_CONFIG_DIRS":str(folder/"config"), "XDG_DATA_HOME":str(folder/"data"),
                "XDG_DATA_DIRS":"/usr/share", "XDG_CACHE_HOME":str(folder/"cache"),
                "XDG_RUNTIME_DIR":str(folder/"runtime"), "QT_QPA_PLATFORM":"offscreen",
                "KWIN_COMPOSE":"O2", "QT_FORCE_STDERR_LOGGING":"1",
                "QT_LOGGING_RULES":"kwin_scripting.debug=true"})
    return env


def verified_bus_environment(folder):
    env = private_environment(folder)
    for key, value in env.items():
        if os.environ.get(key) != value:
            raise RuntimeError(f"private session environment unavailable: {key}")
    if any(key in os.environ for key in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY")):
        raise RuntimeError("owner display environment reached private review")
    address = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    if not address:
        raise RuntimeError("private session bus unavailable")
    env["DBUS_SESSION_BUS_ADDRESS"] = address
    result = subprocess.run(["dbus-send", "--session", "--print-reply",
        "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus",
        "org.freedesktop.DBus.GetConnectionUnixProcessID", "string:org.freedesktop.DBus"],
        env=env, capture_output=True, text=True, timeout=5)
    match = re.search(r"uint32\s+(\d+)", result.stdout)
    if result.returncode or not match:
        raise RuntimeError("private session bus PID unavailable")
    pid = int(match.group(1))
    daemon = dict(item.split(b"=", 1) for item in Path(f"/proc/{pid}/environ")
                  .read_bytes().split(b"\0") if b"=" in item)
    for key, value in private_environment(folder).items():
        if daemon.get(key.encode()) != value.encode():
            raise RuntimeError(f"session bus inherited non-private state: {key}")
    if any(key in daemon for key in (b"DISPLAY", b"WAYLAND_DISPLAY", b"XAUTHORITY")):
        raise RuntimeError("session bus inherited owner display")
    return env, pid


def inside(folder, mode):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # Refuse even a direct --inside invocation before starting the compositor.
    env, bus_pid = verified_bus_environment(folder)
    private = folder / "data/kwin/effects"
    private.mkdir(parents=True)
    plugin = "scale" if mode == "old" else "moos-quiet-lift"
    package = Path("/usr/share/kwin/effects/scale") if mode == "old" else PACKAGE
    destination = private / plugin
    shutil.copytree(package, destination)
    code = destination / "contents/code/main.js"
    code.write_text(TRACE + ("throw new Error('required broken effect control');\n" if mode == "broken" else "")
                    + code.read_text())
    factor = 0 if mode == "reduced" else 1
    (folder / "config/kdeglobals").write_text(f"[KDE]\nAnimationDurationFactor={factor}\n")
    (folder / "config/kwinrc").write_text("[Plugins]\nscaleEnabled=" +
        ("true" if mode == "old" else "false") + "\nfadeEnabled=false\nglideEnabled=false\n"
        "moos-quiet-liftEnabled=" + ("false" if mode == "old" else "true") + "\n")
    client = folder / "client.py"
    client.write_text(CLIENT)
    log = folder / "kwin.log"
    with log.open("w") as output:
        compositor = subprocess.Popen(["kwin_wayland", "--virtual", "--width", "1024",
            "--height", "768", "--socket", "wayland-review", "--no-lockscreen",
            "--no-global-shortcuts", "--no-kactivities"], env=env, stdout=output, stderr=subprocess.STDOUT)
        try:
            socket = folder / "runtime/wayland-review"
            until = time.monotonic()+15
            while not socket.exists() and compositor.poll() is None and time.monotonic()<until:
                time.sleep(0.1)
            if not socket.exists():
                raise RuntimeError("private KWin display unavailable")
            time.sleep(0.5)
            loaded = subprocess.run(["qdbus-qt6", "org.kde.KWin", "/Effects",
                "org.freedesktop.DBus.Properties.Get", "org.kde.kwin.Effects", "loadedEffects"], env=env, capture_output=True,text=True,timeout=8)
            if loaded.returncode:
                raise RuntimeError("private KWin effect readback unavailable")
            (folder / "loaded-effects.txt").write_text(loaded.stdout + loaded.stderr)
            if mode == "broken":
                if plugin in loaded.stdout.splitlines():
                    raise RuntimeError("broken effect was loaded")
            else:
                if plugin not in loaded.stdout.splitlines():
                    raise RuntimeError("required effect not loaded")
                clientenv = dict(env, QT_QPA_PLATFORM="wayland", WAYLAND_DISPLAY="wayland-review")
                for lifetime in (650, 65):
                    result = subprocess.run([sys.executable,str(client),str(lifetime)],env=clientenv,
                        capture_output=True,text=True,timeout=8)
                    (folder / f"client-{lifetime}.log").write_text(result.stdout+result.stderr)
                    if result.returncode or "MOOS_NATIVE_CLIENT_EXECUTED" not in result.stdout:
                        raise RuntimeError("native window journey did not execute")
                time.sleep(0.3)
            running = compositor.poll() is None
        finally:
            if compositor.poll() is None:
                compositor.terminate()
            try:
                compositor.wait(timeout=8)
            except subprocess.TimeoutExpired:
                compositor.kill(); compositor.wait(timeout=5)
    text = log.read_text()
    events = [line[line.index("MOOS_NATIVE_"):] for line in text.splitlines() if "MOOS_NATIVE_" in line]
    if not running:
        raise RuntimeError("private KWin exited during the window journey")
    if mode == "fixed" and (not any("REDIRECT true" in e for e in events)
                             or sum("_END" in e for e in events)<6):
        raise RuntimeError("native reversal/settlement not observed")
    if mode == "reduced" and any("ANIMATE" in e for e in events):
        raise RuntimeError("reduced motion started an animation")
    if mode == "old" and not any("CANCEL" in e for e in events):
        raise RuntimeError("stock interrupted-animation control not observed")
    if mode != "broken" and ("ReferenceError" in text or "TypeError" in text):
        raise RuntimeError("native effect runtime error")
    receipt = {"mode":mode,"events":events,"private_compositor_alive":running,
               "private_bus_pid":bus_pid,"bus_environment_verified":True,
               "owner_session_used":False,"physical_input":False}
    (folder/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inside",action="store_true")
    parser.add_argument("--mode",choices=("old","fixed","reduced","broken"),required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.inside:
        inside(args.output,args.mode)
    else:
        args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
        args.output = args.output.resolve()
        for name in ("home", "config", "data", "cache", "runtime"):
            (args.output / name).mkdir(mode=0o700)
        raise SystemExit(subprocess.run(["dbus-run-session","--",sys.executable,__file__,
            "--inside","--mode",args.mode,"--output",str(args.output)],
            env=private_environment(args.output),timeout=45).returncode)
