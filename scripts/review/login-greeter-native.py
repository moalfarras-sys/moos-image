#!/usr/bin/env python3
"""Look at the REAL Plasma Login greeter, drawn from this tree, on a private KWin.

    python3 scripts/review/login-greeter-native.py OUT_DIR [--look org.moos.ui2.bloom]
        [--lang ar|en] [--logical 1766x1104] [--scale 1.45] [--stock] [--frames 0.4,0.8,1.6,3]
        [--type "secret"] [--gpu]

plasma-login-greeter --test and plasma-login-wallpaper run inside bubblewrap with
this tree's session files bind-mounted over the installed ones (an import path
alone does not replace an installed module), stacked by a private
`kwin_wayland --virtual` exactly as the login KWin stacks them. A private
session bus WITHOUT service directories carries KWin's ScreenShot2 capture; the
system bus is absent. Nothing reaches the owner's display, bus or accounts:
WAYLAND_DISPLAY/DISPLAY are replaced and every HOME/XDG path is private.

It reports when each process printed its readiness marker and captures the
whole output at the requested times (seconds after the greeter started), so a
slow or empty first frame is measured rather than guessed. `--stock` omits the
MoOS overlays (installed bytes only). Source-harness evidence: virtual output,
test-mode greeter, no PAM; never a cold-boot or authentication proof.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QDBUS = "/usr/lib64/qt6/bin/qdbus"
SEAM = ROOT / "build_files/plasma-seams/6.8"
FILES = ROOT / "system_files"
QML = Path("/usr/lib64/qt6/qml")
OVERLAY_DIRS = ("org/moos/ui", "org/kde/breeze/components")
WALLPAPER_PLUGIN = Path("/usr/share/plasma/wallpapers/org.moos.ui2.greeter")

LOOKS = {
    # look -> (colour scheme, icon theme, wallpaper package, plasma style)
    "org.moos.ui2.bloom": ("MoOSUI2Bloom", "MoOSUI2Bloom", "MoOSUI2Bloom", "MoOSUI2Bloom"),
    "org.moos.ui2.bloom.light": ("MoOSUI2BloomLight", "MoOSUI2BloomLight", "MoOSUI2BloomLight", "MoOSUI2BloomLight"),
    "org.moos.ui2": ("MoOSUI2Dark", "MoOSUI2", "MoOSUI2Graphite", "MoOSUI2"),
    "org.moos.ui2.light": ("MoOSUI2Light", "MoOSUI2Light", "MoOSUI2Tide", "MoOSUI2Light"),
    "org.moos.ui2.aurora": ("MoOSUI2Aurora", "MoOSUI2Aurora", "MoOSUI2Aurora", "MoOSUI2Aurora"),
    "org.moos.ui2.aurora.light": ("MoOSUI2AuroraLight", "MoOSUI2AuroraLight", "MoOSUI2AuroraLight", "MoOSUI2AuroraLight"),
    "org.moos.ui2.gaming": ("MoOSUI2Arena", "MoOSUI2Arena", "MoOSUI2Arena", "MoOSUI2Arena"),
    "org.moos.ui2.study.light": ("MoOSUI2ScholarLight", "MoOSUI2ScholarLight", "MoOSUI2ScholarLight", "MoOSUI2ScholarLight"),
}


def no_core() -> None:
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def overlays() -> list[str]:
    """Bind every source session file over its installed counterpart."""
    binds: list[str] = []
    for rel in OVERLAY_DIRS:
        for src in sorted((FILES / "usr/lib64/qt6/qml" / rel).iterdir()):
            if src.suffix not in (".qml", ".js") or not src.is_file():
                continue
            dest = QML / rel / src.name
            seam = SEAM / dest.relative_to("/")
            chosen = seam if seam.is_file() else src
            if dest.exists():
                binds += ["--ro-bind", str(chosen), str(dest)]
    source_plugin = FILES / "usr/share/plasma/wallpapers/org.moos.ui2.greeter"
    binds += ["--ro-bind", str(source_plugin), str(WALLPAPER_PLUGIN)]
    return binds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--look", default="org.moos.ui2.bloom")
    ap.add_argument("--lang", default="ar")
    ap.add_argument("--logical", default="1766x1104")
    ap.add_argument("--scale", type=float, default=1.45)
    ap.add_argument("--stock", action="store_true")
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--frames", default="0.5,1.0,2.0,4.0")
    ap.add_argument("--type", default="")
    ap.add_argument("--wake", action="store_true", help="move the pointer before capturing")
    ap.add_argument("--real", action="store_true",
                    help="run the real greeter UI (no --test) against an absent daemon socket")
    ap.add_argument("--cache", action="store_true",
                    help="keep a private QML disk cache and start twice (warm second start)")
    ap.add_argument("--surface", choices=("login", "lock"), default="login",
                    help="lock: kscreenlocker_greet --testing (the same shared island)")
    ap.add_argument("--poll", type=float, default=0.0,
                    help="sample the screen every N seconds until the last frame time")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    lw, lh = (int(v) for v in args.logical.split("x"))
    scheme, icons, wallpaper, style = LOOKS[args.look]

    base = Path(tempfile.mkdtemp(prefix="moos-login-review."))
    run = base / "run"
    for d in ("home", "config", "cache", "data", "xdg", "run"):
        (base / d).mkdir(mode=0o700)
    cfg = base / "config"
    colors = Path(f"/usr/share/color-schemes/{scheme}.colors")
    if not colors.is_file():
        colors = FILES / f"usr/share/color-schemes/{scheme}.colors"
    (cfg / "kdeglobals").write_text(
        colors.read_text(encoding="utf-8")
        + f"\n[General]\nColorScheme={scheme}\nfont=Meyar Sans,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1\n"
        f"[KDE]\nLookAndFeelPackage={args.look}\n[Icons]\nTheme={icons}\n", encoding="utf-8")
    (cfg / "plasmarc").write_text(f"[Theme]\nname={style}\n", encoding="utf-8")
    (cfg / "plasmalogin.conf").write_text(
        "[Greeter]\nWallpaperPluginId=org.moos.ui2.greeter\nShowClock=true\n\n"
        f"[Greeter][Wallpaper][org.moos.ui2.greeter][General]\nImage=/usr/share/wallpapers/{wallpaper}/\n",
        encoding="utf-8")
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
    (cfg / "kscreenlockerrc").write_text(
        "[Greeter]\nWallpaperPlugin=org.kde.image\n\n[Greeter][Wallpaper][org.kde.image][General]\n"
        f"Image=/usr/share/wallpapers/{wallpaper}/\n", encoding="utf-8")
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
               XDG_CONFIG_DIRS=str(base / "xdg") + ":/etc/xdg", XDG_DATA_DIRS="/usr/share",
               DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(run / "bus"),
               DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(base / "absent-system-bus"),
               KWIN_WAYLAND_NO_PERMISSION_CHECKS="1", QT_FORCE_STDERR_LOGGING="1",
               LANG=lang, LC_ALL=lang, LANGUAGE=args.lang)
    if not args.gpu:
        env.update(LIBGL_ALWAYS_SOFTWARE="1", GALLIUM_DRIVER="llvmpipe", LP_NUM_THREADS="4")
    procs: list[subprocess.Popen] = []
    result: dict = {"look": args.look, "lang": args.lang, "logical": [lw, lh], "scale": args.scale,
                    "stock": args.stock, "gpu": args.gpu, "markers": {}, "frames": []}
    sock = "wayland-login-review"
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
        cenv = dict(env, WAYLAND_DISPLAY=sock, QT_QPA_PLATFORM="wayland",
                    QT_LOGGING_RULES="*.debug=false;qml.info=true;qml.warning=true",
                    SDDM_SOCKET=str(base / "absent-daemon-socket"))
        if not args.cache:
            cenv["QML_DISABLE_DISK_CACHE"] = "1"
        wrap = ["bwrap", "--die-with-parent", "--unshare-net", "--ro-bind", "/", "/", "--dev-bind", "/dev", "/dev",
                "--bind", str(base), str(base), "--tmpfs", "/run/user"]
        # plasma-login reads /etc/plasmalogin.conf, not XDG_CONFIG_HOME; a
        # private copy selects the requested scene without touching the host.
        wrap += ["--ro-bind", str(cfg / "plasmalogin.conf"), "/etc/plasmalogin.conf"]
        if not args.stock:
            wrap += overlays()
        greeter_cmd = ["/usr/libexec/plasma-login-greeter"] + ([] if args.real else ["--test"])
        if args.surface == "lock":
            greeter_cmd = ["/usr/libexec/kscreenlocker_greet", "--testing"]
        if args.surface == "lock":
            started = time.monotonic()
            (base / "wallpaper.log").write_text("")
            wall = subprocess.Popen(["/usr/bin/true"])
        elif not args.cache:
            started = time.monotonic()
            wall = subprocess.Popen(wrap + ["/usr/bin/plasma-login-wallpaper"], env=cenv,
                                    stdout=(base / "wallpaper.log").open("w"), stderr=subprocess.STDOUT,
                                    preexec_fn=no_core)
            procs.append(wall)
        else:
            # A first, discarded start fills the private disk cache.
            for binary in (["/usr/bin/plasma-login-wallpaper"], greeter_cmd):
                warm = subprocess.Popen(wrap + binary, env=cenv, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, preexec_fn=no_core)
                time.sleep(4)
                warm.terminate()
                warm.wait(timeout=5)
            started = time.monotonic()
            wall = subprocess.Popen(wrap + ["/usr/bin/plasma-login-wallpaper"], env=cenv,
                                    stdout=(base / "wallpaper.log").open("w"), stderr=subprocess.STDOUT,
                                    preexec_fn=no_core)
            procs.append(wall)
        greeter = subprocess.Popen(wrap + greeter_cmd, env=cenv,
                                   stdout=(base / "greeter.log").open("w"), stderr=subprocess.STDOUT,
                                   preexec_fn=no_core)
        procs.append(greeter)
        session = None
        import dbus  # noqa: E402
        from PySide6.QtGui import QImage  # noqa: E402
        session = dbus.bus.BusConnection("unix:path=" + str(run / "bus"))

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

        def markers() -> None:
            for name in ("wallpaper", "greeter"):
                text = (base / f"{name}.log").read_text(errors="replace")
                for key in ("MOOS_AUTH_SURFACE_READY", "MOOS_LOGIN_APPEARANCE_READY", "MOOS_LOGIN_SCENE_READY"):
                    tag = f"{name}:{key}"
                    if key in text and tag not in result["markers"]:
                        result["markers"][tag] = round(time.monotonic() - started, 3)

        def qdbus(*a: str) -> None:
            subprocess.run([QDBUS, *a], env=env, capture_output=True, timeout=10)

        times = [float(t) for t in args.frames.split(",") if t]
        if args.poll:
            from PySide6.QtGui import QImage as _Q  # noqa: F401
            samples = []
            tick = args.poll
            limit = min(times) if times else 2.0
            while time.monotonic() - started <= limit:
                while time.monotonic() - started < tick:
                    markers()
                    time.sleep(0.01)
                path = base / "sample.png"
                at = round(time.monotonic() - started, 3)
                capture(path)
                img = QImage(str(path)).scaled(64, 40)
                lum = [0.0, 0]
                for y in range(img.height()):
                    for x in range(img.width()):
                        c = img.pixelColor(x, y)
                        lum[0] += (0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()) / 255
                        lum[1] += 1
                samples.append({"t": at, "mean_luma": round(lum[0] / lum[1], 4)})
                tick = time.monotonic() - started + args.poll
            result["samples"] = samples
            result["first_non_black"] = next((s["t"] for s in samples if s["mean_luma"] > 0.02), None)
        for t in times:
            while time.monotonic() - started < t:
                markers()
                time.sleep(0.02)
            name = f"t{t:.2f}.png"
            capture(out / name)
            result["frames"].append({"t": t, "file": name})
        if args.wake or args.type:
            # Input reaches ONLY the private KWin, through its own EIS endpoint
            # (the same libei client Mawj uses), never a host uinput device.
            sys.path.insert(0, str(ROOT / "moremote/agent-linux"))
            import gi  # noqa: E402
            gi.require_version("Gio", "2.0")
            from gi.repository import Gio, GLib  # noqa: E402
            from mo_remote_eis import EisInput  # noqa: E402
            private = Gio.DBusConnection.new_for_address_sync(
                "unix:path=" + str(run / "bus"),
                Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                None, None)
            eis = EisInput(private, Gio, GLib)
            try:
                for x in (0.46, 0.5, 0.54):
                    eis.absolute(x, 0.62)
                    time.sleep(0.05)
                time.sleep(1.4)
                capture(out / "woken.png")
                result["frames"].append({"t": "woken", "file": "woken.png"})
                if args.type:
                    codes = {c: k for c, k in zip("qwertyuiopasdfghjklzxcvbnm",
                             (16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 30, 31, 32, 33, 34, 35, 36, 37,
                              38, 44, 45, 46, 47, 48, 49, 50))}
                    for ch in args.type:
                        eis.send("NotifyKeyboardKeycode", (codes[ch], 1), None)
                        eis.send("NotifyKeyboardKeycode", (codes[ch], 0), None)
                        time.sleep(0.06)
                    time.sleep(0.8)
                    capture(out / "typed.png")
                    result["frames"].append({"t": "typed", "file": "typed.png"})
                    if args.surface == "lock":
                        # The lock greeter's testing mode owns a real PAM
                        # authenticator for this account: never submit there.
                        raise StopIteration
                    eis.send("NotifyKeyboardKeycode", (28, 1), None)
                    eis.send("NotifyKeyboardKeycode", (28, 0), None)
                    time.sleep(0.45)
                    capture(out / "submitted.png")
                    time.sleep(1.0)
                    capture(out / "refused.png")
                    result["frames"] += [{"t": "submitted", "file": "submitted.png"},
                                         {"t": "refused", "file": "refused.png"}]
            except StopIteration:
                pass
            finally:
                eis.close()
        markers()
        for name in ("wallpaper", "greeter"):
            log = (base / f"{name}.log").read_text(errors="replace")
            (out / f"{name}.log").write_text(log)
        (out / "kwin.log").write_text((base / "kwin.log").read_text(errors="replace"))
        result["alive"] = {"wallpaper": wall.poll() is None, "greeter": greeter.poll() is None}
        result["result"] = "CAPTURED"
    except Exception as exc:  # evidence, not a verdict
        result["result"] = "ERROR"
        result["error"] = repr(exc)
    finally:
        for p in reversed(procs):
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
        shutil.rmtree(base, ignore_errors=True)
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["result"] == "CAPTURED" else 1


if __name__ == "__main__":
    sys.exit(main())
