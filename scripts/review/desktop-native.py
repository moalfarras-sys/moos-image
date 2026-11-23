#!/usr/bin/env python3
"""Look at the REAL MoOS desktop shell, drawn from this tree, on a private KWin.

    python3 scripts/review/desktop-native.py OUT_DIR [--look org.moos.ui2.bloom] [--lang ar|en]
        [--logical 1766x1104] [--scale 1.45] [--wait 20] [--hub on|off]
        [--call activateLauncherMenu] [--script extra.js] [--gpu]

plasmashell and kactivitymanagerd run inside bubblewrap. Inside it, this tree's MoOS QML modules
are bound over the installed ones, and the Plasma packages come first in XDG_DATA_DIRS: a merged
copy of /usr/share/plasma with system_files laid over it, as the image composes them. A private
`kwin_wayland --virtual` stacks the shell. A private session bus WITHOUT service directories carries
the shell's names and KWin's ScreenShot2 capture, so nothing can be activated on it. The system bus
is absent: battery, network and Bluetooth applets show their unavailable state. WAYLAND_DISPLAY,
DISPLAY, the session bus and every HOME/XDG path are replaced, and the owner's runtime directory is
hidden from the shell.

The scene wallpaper and the Hub are set through PlasmaShell.evaluateScript, as
scripts/review/render-desktop.sh does on X11. `--call activateLauncherMenu` opens Mova after the
desktop frame. Each capture is the whole virtual output at native resolution. result.json records
the frames and the shell's complaints about MoOS's own packages.

Source-harness evidence only. It runs a fresh account with no moos-apply-theme migration, software
rendering and a virtual output. Fonts and natively compiled components (the Control Center plugin,
KCMs) come from the INSTALLED image, not this tree. It is never installed, signed or physical
acceptance, and it is no proof of input, motion or performance.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = ROOT / "system_files"
QML = Path("/usr/lib64/qt6/qml")
KAMD = "/usr/libexec/kactivitymanagerd"


def no_core() -> None:
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def profile(look: str) -> dict:
    data = json.loads((FILES / "usr/share/moos/theme-profiles.json").read_text(encoding="utf-8"))
    for entry in data["profiles"]:
        if entry.get("id") == look:
            return entry
    raise SystemExit(f"unknown look {look!r}; see system_files/usr/share/moos/theme-profiles.json")


def seam_overrides(share: Path) -> str:
    """Install the reviewed seam set for the host's Plasma into the merged share, as the build does.

    system_files may hold a copy for another Plasma; build_files/plasma_seams.py replaces it with
    the one set whose range holds the image's Plasma, so the harness uses that same selection.
    """
    spec = importlib.util.spec_from_file_location("plasma_seams", ROOT / "build_files/plasma_seams.py")
    seams = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seams)
    version = seams.package_version("plasma-workspace")
    chosen = seams.select_set(seams.load_registry(), version)
    for dest, rel in chosen["sources"].items():
        if dest.startswith("/usr/share/plasma/"):
            target = share / "plasma" / dest[len("/usr/share/plasma/"):]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "build_files/plasma-seams" / rel, target)
    return f"{chosen['id']} for Plasma {version}"


def module_overlays() -> list[str]:
    """Bind each source MoOS QML module directory over its installed counterpart."""
    binds: list[str] = []
    source_root = FILES / "usr/lib64/qt6/qml/org/moos"
    for src in sorted(p for p in source_root.iterdir() if p.is_dir()):
        dest = QML / "org/moos" / src.name
        if dest.is_dir():
            binds += ["--ro-bind", str(src), str(dest)]
    return binds


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out")
    ap.add_argument("--look", default="org.moos.ui2.bloom")
    ap.add_argument("--lang", choices=("ar", "en"), default="ar")
    ap.add_argument("--logical", default="1766x1104")
    ap.add_argument("--scale", type=float, default=1.45)
    ap.add_argument("--wait", type=float, default=20.0, help="seconds for the shell to settle")
    ap.add_argument("--hub", choices=("on", "off"), default="on")
    ap.add_argument("--call", default="", help="a PlasmaShell method to call after the desktop frame")
    ap.add_argument("--script", default="", help="an extra evaluateScript file run after the scene")
    ap.add_argument("--gpu", action="store_true")
    args = ap.parse_args()
    if args.call and not args.call.replace("_", "").isalnum():
        ap.error("--call takes a bare PlasmaShell method name")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    lw, lh = (int(v) for v in args.logical.split("x"))
    look = profile(args.look)

    base = Path(tempfile.mkdtemp(prefix="moos-desktop-review."))
    run = base / "run"
    for d in ("home", "config", "cache", "data", "xdg", "run", "share"):
        (base / d).mkdir(mode=0o700)
    cfg = base / "config"
    # The image lays MoOS's files inside stock packages (the shell's defaults, the panel template).
    # A merged copy keeps the stock package metadata that KPackage needs to find each one.
    shutil.copytree("/usr/share/plasma", base / "share/plasma", symlinks=True)
    shutil.copytree(FILES / "usr/share/plasma", base / "share/plasma", symlinks=True, dirs_exist_ok=True)
    seam_set = seam_overrides(base / "share")

    scheme = look["scheme"]
    colors = FILES / f"usr/share/color-schemes/{scheme}.colors"
    if not colors.is_file():
        colors = Path(f"/usr/share/color-schemes/{scheme}.colors")
    (cfg / "kdeglobals").write_text(
        colors.read_text(encoding="utf-8")
        + f"\n[General]\nColorScheme={scheme}\n"
        f"[KDE]\nLookAndFeelPackage={args.look}\n[Icons]\nTheme={look['icons']}\n", encoding="utf-8")
    (cfg / "plasmarc").write_text(f"[Theme]\nname={look['style']}\n", encoding="utf-8")
    pw, ph = round(lw * args.scale), round(lh * args.scale)
    (cfg / "kwinoutputconfig.json").write_text(json.dumps([
        {"name": "outputs", "data": [{"connectorName": "Virtual-0", "scale": args.scale,
                                      "mode": {"basic": {"width": pw, "height": ph, "refreshRate": 60000},
                                               "flags": 1},
                                      "transform": "Normal", "overscan": 0, "rgbRange": "Automatic",
                                      "vrrPolicy": "Never"}]},
        {"name": "setups", "data": [{"lidClosed": False, "outputs": [
            {"enabled": True, "outputIndex": 0, "position": {"x": 0, "y": 0}, "priority": 1,
             "replicationSource": ""}]}]}]), encoding="utf-8")
    (cfg / "kwinrc").write_text("[Plugins]\nblurEnabled=true\n", encoding="utf-8")
    bus_conf = base / "bus.conf"
    bus_conf.write_text(
        '<busconfig><type>session</type><listen>unix:path=' + str(run / "bus") +
        '</listen><auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/>'
        '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
    lang = {"ar": "ar_SA.UTF-8", "en": "en_US.UTF-8"}[args.lang]
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("WAYLAND", "DBUS", "XDG_", "QT_", "QML", "KDE", "DISPLAY", "XAUTHORITY",
                                "LANG", "LC_"))}
    env.update(HOME=str(base / "home"), XDG_RUNTIME_DIR=str(run), XDG_CONFIG_HOME=str(cfg),
               XDG_CACHE_HOME=str(base / "cache"), XDG_DATA_HOME=str(base / "data"),
               XDG_CONFIG_DIRS=f"{base / 'xdg'}:{FILES / 'etc/xdg'}:/etc/xdg",
               XDG_DATA_DIRS=f"{base / 'share'}:{FILES / 'usr/share'}:/usr/share",
               DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(run / "bus"),
               DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(base / "absent-system-bus"),
               KWIN_WAYLAND_NO_PERMISSION_CHECKS="1", QT_FORCE_STDERR_LOGGING="1",
               LANG=lang, LC_ALL=lang, LANGUAGE=args.lang)
    if not args.gpu:
        env.update(LIBGL_ALWAYS_SOFTWARE="1", GALLIUM_DRIVER="llvmpipe", LP_NUM_THREADS="4")
    procs: list[subprocess.Popen] = []
    result: dict = {"look": args.look, "lang": args.lang, "logical": [lw, lh], "scale": args.scale,
                    "gpu": args.gpu, "seams": seam_set, "frames": [], "markers": {}}
    sock = "wayland-desktop-review"
    try:
        procs.append(subprocess.Popen(["dbus-daemon", "--nofork", "--config-file=" + str(bus_conf)],
                                      env=env, stdout=(base / "bus.log").open("w"), stderr=subprocess.STDOUT))
        for _ in range(50):
            if (run / "bus").is_socket():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("private bus did not start")
        kwin = subprocess.Popen(["kwin_wayland", "--virtual", "--width", str(lw), "--height", str(lh),
                                 "--scale", str(args.scale), "--socket", sock, "--no-lockscreen",
                                 "--no-global-shortcuts", "--no-kactivities"],
                                env=env, stdout=(base / "kwin.log").open("w"), stderr=subprocess.STDOUT,
                                preexec_fn=no_core)
        procs.append(kwin)
        for _ in range(100):
            if (run / sock).is_socket():
                break
            if kwin.poll() is not None:
                raise RuntimeError(f"KWin exited {kwin.returncode}")
            time.sleep(0.1)
        else:
            raise RuntimeError("no private Wayland socket")
        time.sleep(0.6)

        import dbus  # noqa: E402
        from PySide6.QtGui import QImage  # noqa: E402
        session = dbus.bus.BusConnection("unix:path=" + str(run / "bus"))

        def has_owner(name: str) -> bool:
            proxy = session.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus")
            return bool(dbus.Interface(proxy, "org.freedesktop.DBus").NameHasOwner(name))

        def wait_for(name: str, seconds: float) -> float | None:
            started = time.monotonic()
            while time.monotonic() - started < seconds:
                if has_owner(name):
                    return round(time.monotonic() - started, 3)
                time.sleep(0.25)
            return None

        cenv = dict(env, WAYLAND_DISPLAY=sock, QT_QPA_PLATFORM="wayland", XDG_SESSION_TYPE="wayland",
                    XDG_CURRENT_DESKTOP="KDE", KDE_FULL_SESSION="true", KDE_SESSION_VERSION="6",
                    QML_DISABLE_DISK_CACHE="1",
                    QT_LOGGING_RULES="*.debug=false;qml.info=true;qml.warning=true")
        wrap = ["bwrap", "--die-with-parent", "--unshare-net", "--ro-bind", "/", "/", "--dev-bind", "/dev", "/dev",
                "--tmpfs", "/run/user", "--bind", str(base), str(base)] + module_overlays()
        procs.append(subprocess.Popen(wrap + [KAMD], env=cenv, stdout=(base / "kamd.log").open("w"),
                                      stderr=subprocess.STDOUT, preexec_fn=no_core))
        result["markers"]["activity-manager"] = wait_for("org.kde.ActivityManager", 20)
        started = time.monotonic()
        shell = subprocess.Popen(wrap + ["plasmashell", "--no-respawn"], env=cenv,
                                 stdout=(base / "plasmashell.log").open("w"), stderr=subprocess.STDOUT,
                                 preexec_fn=no_core)
        procs.append(shell)
        result["markers"]["plasmashell-bus"] = wait_for("org.kde.plasmashell", 60)
        if result["markers"]["plasmashell-bus"] is None:
            raise RuntimeError("plasmashell never claimed its bus name")

        def shell_call(method: str, *params):
            proxy = session.get_object("org.kde.plasmashell", "/PlasmaShell")
            return dbus.Interface(proxy, "org.kde.PlasmaShell").get_dbus_method(method)(*params)

        wallpaper = FILES / "usr/share/wallpapers" / look["wallpaper"]
        if not wallpaper.is_dir():
            wallpaper = Path("/usr/share/wallpapers") / look["wallpaper"]
        scene = (
            "var ds = desktops();\n"
            "for (var i = 0; i < ds.length; i++) {\n"
            "  ds[i].wallpaperPlugin = 'org.moos.ui2.wallpaper';\n"
            "  ds[i].currentConfigGroup = ['Wallpaper', 'org.moos.ui2.wallpaper', 'General'];\n"
            f"  ds[i].writeConfig('Image', {json.dumps(str(wallpaper))});\n"
            f"  ds[i].writeConfig('ShowDashboard', {'true' if args.hub == 'on' else 'false'});\n"
            "  ds[i].reloadConfig();\n"
            "}\n"
            "print('moos-scene:' + ds.length + ' panels:' + panels().length);\n")
        scripts = [scene] + ([Path(args.script).read_text(encoding="utf-8")] if args.script else [])
        logs = []
        for text in scripts:
            try:
                logs.append(str(shell_call("evaluateScript", text)))
            except dbus.DBusException as exc:
                logs.append("evaluateScript failed: " + exc.get_dbus_message())
        result["script"] = logs

        def capture(path: Path) -> None:
            shot = dbus.Interface(session.get_object("org.kde.KWin", "/org/kde/KWin/ScreenShot2"),
                                  "org.kde.KWin.ScreenShot2")
            rd, wr = os.pipe()
            try:
                meta = shot.CaptureActiveScreen({"native-resolution": True, "include-cursor": False},
                                                dbus.types.UnixFd(wr))
            finally:
                os.close(wr)
            data = bytearray()
            with os.fdopen(rd, "rb") as fh:
                while chunk := fh.read(1 << 20):
                    data += chunk
            w, h, stride, fmt = (int(meta[k]) for k in ("width", "height", "stride", "format"))
            QImage(bytes(data), w, h, stride, QImage.Format(fmt)).copy().save(str(path))

        time.sleep(max(0.0, args.wait - (time.monotonic() - started)))
        capture(out / "desktop.png")
        result["frames"].append({"t": round(time.monotonic() - started, 2), "file": "desktop.png"})
        if args.call:
            try:
                shell_call(args.call)
            except dbus.DBusException as exc:
                result["call_error"] = exc.get_dbus_message()
            time.sleep(4)
            capture(out / f"{args.call}.png")
            result["frames"].append({"t": round(time.monotonic() - started, 2), "file": f"{args.call}.png"})
        result["alive"] = {"kwin": kwin.poll() is None, "plasmashell": shell.poll() is None}
        complaints: dict[str, int] = {}
        for line in (base / "plasmashell.log").read_text(errors="replace").splitlines():
            if any(key in line for key in ("org.moos", "/moos/", "MoOS")) and \
                    any(key in line for key in ("rror", "arning", "TypeError", "ReferenceError", "not ")):
                line = line.replace(str(base / "share") + "/", "usr/share/").replace(str(FILES) + "/", "")
                complaints[line[:300]] = complaints.get(line[:300], 0) + 1
        result["moos_complaints"] = sorted(complaints.items(), key=lambda kv: -kv[1])[:40]
        result["result"] = "CAPTURED"
    except Exception as exc:  # the evidence of a failed run is the log, kept below
        result["result"] = f"FAILED: {exc}"
    finally:
        for proc in reversed(procs):
            if proc.poll() is None:
                proc.terminate()
        for proc in reversed(procs):
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        for name in ("plasmashell.log", "kwin.log", "kamd.log"):
            if (base / name).is_file():
                shutil.copy2(base / name, out / name)
        (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8")
        shutil.rmtree(base, ignore_errors=True)
    print(json.dumps({k: result[k] for k in ("result", "markers", "frames")}, ensure_ascii=False))
    return 0 if result["result"] == "CAPTURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
