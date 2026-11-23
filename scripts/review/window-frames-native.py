#!/usr/bin/env python3
"""Measure MoOS Aurorae window frames in a private native virtual KWin.

WHY THIS EXISTS

The decoration is a KWin plugin (aurorae.v2) reading a theme rc, and no source
gate ever rendered one. The owner's Oracle desktop (1280x720 at 75%, Arabic,
Bloom Light) showed a caption 68 logical px off the window centre, and the
plugin's own arithmetic says a 140 px TitleBorderLeft/Right leaves no caption at
all in a dialog narrower than about 450 px. Those are pixel facts, so this tool
measures pixels: it starts a private `kwin_wayland --virtual` (own HOME, XDG
directories, Wayland socket and a session bus with no service activation),
installs the requested Aurorae themes into the private XDG_DATA_HOME, opens real
Qt windows with Arabic and English captions at several widths, places and
maximizes them through KWin scripting, captures each frame with the native
ScreenShot2 interface and reports:

  * whether caption ink exists outside the button group,
  * the caption ink centre relative to the window centre (logical px),
  * whether the caption fits its window or is elided,
  * caption and button vertical bounds inside the title bar,
  * the button group's side (RTL mirroring) in restored and maximized states.

Composition is OpenGL (llvmpipe). The 6.8 virtual backend refuses QPainter
(KWIN_COMPOSE=Q) and that private KWin crashed on its first screenshot, so Q is
not offered; the compositor also runs with RLIMIT_CORE=0.

Nothing here touches the owner's compositor, bus, portal, Remote or config.
Every writable path lives under one new private directory that is retained as
evidence. This is software-compositor evidence for decoration geometry; it does
not qualify physical input, touch, a GPU or a signed image.

  window-frames-native.py [--theme-root DIR] [--theme NAME ...] [--scale S]
                          [--lang ar|en] [--out DIR] [--check]
"""
from __future__ import annotations

import argparse
import configparser
import json
import hashlib
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

INSTALLED = pathlib.Path("/usr/share/aurorae/themes")
QDBUS = "/usr/lib64/qt6/bin/qdbus"

# (key, logical width, logical height, Arabic caption, English caption)
WINDOWS = (
    ("narrow", 380, 220, "إعدادات العرض", "Display Settings"),
    ("dialog", 480, 260, "فتح ملف — المستندات", "Open File — Documents"),
    ("medium", 720, 300, "تقرير الصيانة - moos-image - Visual Studio Code",
     "Maintenance report - moos-image - Visual Studio Code"),
    ("wide", 1040, 300, "مرحباً - moos-image - Visual Studio Code",
     "Welcome - moos-image - Visual Studio Code"),
    ("maximized", 900, 500, "نافذة مكبرة — مدير الملفات", "Maximized window — Files"),
)
PLACES = {"narrow": (40, 60), "dialog": (470, 60), "medium": (40, 380), "wide": (40, 720)}

CLIENT = r'''
import json, sys
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
spec = json.loads(sys.argv[1])
app = QApplication(sys.argv[:1])
keep = []
widths = {}
title = QFont("Meyar Sans", 10)
if len(sys.argv) > 3 and sys.argv[3]:
    # A desktop picture under the restored windows, so shadows and hairlines
    # are reviewed against real artwork instead of the compositor's black.
    size = app.primaryScreen().size()
    backdrop = QLabel()
    backdrop.setWindowTitle("MOOS_BACKDROP")
    backdrop.setWindowFlag(Qt.FramelessWindowHint)
    backdrop.setPixmap(QPixmap(sys.argv[3]).scaled(size, Qt.KeepAspectRatioByExpanding,
                                                   Qt.SmoothTransformation))
    backdrop.resize(size)
    backdrop.show()
    keep.append(backdrop)
for key, w, h, caption in spec:
    win = QWidget()
    win.setWindowTitle(caption)
    win.setAutoFillBackground(True)
    win.resize(w, h)
    lay = QVBoxLayout(win)
    lay.addWidget(QLabel(key))
    win.show()
    keep.append(win)
    widths[caption] = QFontMetricsF(title).horizontalAdvance(caption)
print("MOOS_FRAMES_CLIENT " + json.dumps(widths, ensure_ascii=False), flush=True)
QTimer.singleShot(int(sys.argv[2]) * 1000, app.quit)
app.exec()
'''


def kwin_decoration(path: pathlib.Path) -> dict[str, str]:
    """The decoration keys a kwinrc ships, with KWin's own defaults if absent."""
    cfg = configparser.ConfigParser(interpolation=None, strict=False)
    cfg.optionxform = str
    cfg.read(path, encoding="utf-8")
    group = cfg["org.kde.kdecoration2"] if cfg.has_section("org.kde.kdecoration2") else {}
    return {"ButtonsOnLeft": group.get("ButtonsOnLeft", "MS"),
            "ButtonsOnRight": group.get("ButtonsOnRight", "HIAX"),
            "BorderSize": group.get("BorderSize", "Normal"),
            "BorderSizeAuto": group.get("BorderSizeAuto", "true")}


def kwin_buttons(path: pathlib.Path) -> tuple[str, str]:
    """The ButtonsOnLeft/Right a kwinrc ships (KWin's own HIAX default if absent)."""
    shipped = kwin_decoration(path)
    return shipped["ButtonsOnLeft"], shipped["ButtonsOnRight"]


def no_core() -> None:
    """A private compositor that fails must not store a core in the host collector."""
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def theme_layout(root: pathlib.Path, name: str) -> dict:
    cfg = configparser.ConfigParser(interpolation=None, strict=False)
    cfg.optionxform = str
    cfg.read(root / name / f"{name}rc", encoding="utf-8")
    lay = cfg["Layout"] if cfg.has_section("Layout") else {}

    def num(key: str, default: float) -> float:
        try:
            return float(lay.get(key, default))
        except ValueError:
            return float(default)

    return {k: num(k, d) for k, d in (
        ("TitleEdgeLeft", 5), ("TitleEdgeRight", 5), ("TitleEdgeTop", 5), ("TitleEdgeBottom", 5),
        ("TitleEdgeLeftMaximized", 0), ("TitleEdgeRightMaximized", 0),
        ("TitleEdgeTopMaximized", 0), ("TitleEdgeBottomMaximized", 0),
        ("TitleBorderLeft", 5), ("TitleBorderRight", 5), ("TitleHeight", 20),
        ("ButtonWidth", 20), ("ButtonHeight", 20), ("ButtonSpacing", 5),
        ("ButtonMarginTop", 0), ("ButtonMarginTopMaximized", 0), ("ExplicitButtonSpacer", 10))}


def run_one(args, theme: str, root: pathlib.Path) -> dict:
    from PySide6.QtGui import QImage, QColor  # noqa: F401 (local import keeps --help light)
    import dbus

    r = root / theme
    for d in ("home", "config", "cache", "data/aurorae/themes", "xdg"):
        (r / d).mkdir(parents=True, mode=0o700, exist_ok=True)
    # Unix socket paths are limited to 107 bytes, so the bus and Wayland
    # sockets live in a short private runtime directory removed afterwards.
    run = pathlib.Path(tempfile.mkdtemp(prefix="mf-", dir="/tmp"))
    shutil.copytree(args.theme_root / theme, r / "data/aurorae/themes" / theme)
    lay = theme_layout(args.theme_root, theme)
    (r / "config/kwinrc").write_text(
        "[org.kde.kdecoration2]\nlibrary=org.kde.kwin.aurorae.v2\n"
        f"theme=__aurorae__svg__{theme}\nButtonsOnLeft={args.left}\nButtonsOnRight={args.right}\n"
        f"BorderSize={args.border_size}\nBorderSizeAuto={args.border_size_auto}\n"
        "[Plugins]\nscaleEnabled=false\nmagiclampEnabled=false\nslideEnabled=false\n"
        "blurEnabled=false\nslidingpopupsEnabled=false\nfadingpopupsEnabled=false\n",
        encoding="utf-8")
    (r / "config/kdeglobals").write_text(
        "[General]\nfont=Meyar Sans,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1\n"
        "[WM]\nactiveFont=Meyar Sans,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1\n"
        "[KDE]\nAnimationDurationFactor=0\n", encoding="utf-8")
    # kwin_wayland --virtual takes LOGICAL --width/--height and makes an output of
    # width*scale pixels (measured: 1200 at 0.75 gave a 900 px, 1200-logical desk).
    pix_w, pix_h = round(args.logical[0] * args.scale), round(args.logical[1] * args.scale)
    # KWin chooses its own scale for an unknown output and ignores --scale
    # (measured: --scale 0.75 produced a 1.0 desktop), so the requested scale is
    # stored the way the native display settings store it.
    (r / "config/kwinoutputconfig.json").write_text(json.dumps([
        {"name": "outputs", "data": [{"connectorName": "Virtual-0", "scale": args.scale,
                                      "mode": {"basic": {"width": pix_w, "height": pix_h, "refreshRate": 60000},
                                               "flags": 1},
                                      "transform": "Normal", "overscan": 0, "rgbRange": "Automatic",
                                      "vrrPolicy": "Never"}]},
        {"name": "setups", "data": [{"lidClosed": False, "outputs": [
            {"enabled": True, "outputIndex": 0, "position": {"x": 0, "y": 0}, "priority": 1,
             "replicationSource": ""}]}]}], indent=1), encoding="utf-8")
    bus_conf = r / "bus.conf"
    bus_conf.write_text(
        '<busconfig><type>session</type><listen>unix:path=' + str(run / "bus") +
        '</listen><auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/>'
        '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
    lang = "ar_SA.UTF-8" if args.lang == "ar" else "C.UTF-8"
    sock = "wayland-frames"
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("WAYLAND", "DBUS", "XDG_", "QT_", "KDE", "DISPLAY", "XAUTHORITY"))}
    env.update(HOME=str(r / "home"), XDG_RUNTIME_DIR=str(run),
               XDG_CONFIG_HOME=str(r / "config"), XDG_CACHE_HOME=str(r / "cache"),
               XDG_DATA_HOME=str(r / "data"), XDG_CONFIG_DIRS=str(r / "xdg"),
               XDG_DATA_DIRS="/usr/local/share:/usr/share",
               DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(run / "bus"),
               LIBGL_ALWAYS_SOFTWARE="1", GALLIUM_DRIVER="llvmpipe", LP_NUM_THREADS="2",
               KWIN_COMPOSE=args.compose, KWIN_WAYLAND_NO_PERMISSION_CHECKS="1",
               QT_FORCE_STDERR_LOGGING="1", QT_LOGGING_TO_CONSOLE="1",
               LANG=lang, LC_ALL=lang, LANGUAGE=args.lang)
    procs = []
    result = {"theme": theme, "scale": args.scale, "lang": args.lang, "compose": args.compose,
              "buttons": {"left": args.left, "right": args.right},
              "border": {"size": args.border_size, "auto": args.border_size_auto}, "layout": lay, "windows": {},
              "source_files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted((r / "data/aurorae/themes" / theme).iterdir()) if p.is_file()}}
    try:
        bus = subprocess.Popen(["dbus-daemon", "--nofork", "--config-file=" + str(bus_conf)],
                               env=env, stdout=(r / "bus.log").open("w"), stderr=subprocess.STDOUT)
        procs.append(bus)
        for _ in range(50):
            if (run / "bus").is_socket():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("private bus did not start")
        kwin = subprocess.Popen(
            ["kwin_wayland", "--virtual", "--width", str(args.logical[0]), "--height", str(args.logical[1]),
             "--scale", str(args.scale), "--socket", sock, "--no-lockscreen",
             "--no-global-shortcuts", "--no-kactivities"],
            env=env, stdout=(r / "kwin.log").open("w"), stderr=subprocess.STDOUT, preexec_fn=no_core)
        procs.append(kwin)
        for _ in range(100):
            if (run / sock).is_socket():
                break
            if kwin.poll() is not None:
                raise RuntimeError(f"KWin exited {kwin.returncode}")
            time.sleep(0.1)
        else:
            raise RuntimeError("no private Wayland socket")
        spec = [(k, w, h, ar if args.lang == "ar" else en) for k, w, h, ar, en in WINDOWS]
        cenv = dict(env, WAYLAND_DISPLAY=sock, QT_QPA_PLATFORM="wayland", PYTHONDONTWRITEBYTECODE="1")
        (r / "client.py").write_text(CLIENT, encoding="utf-8")
        client = subprocess.Popen([sys.executable, "-s", "-B", str(r / "client.py"),
                                   json.dumps(spec, ensure_ascii=False), "90",
                                   str(args.backdrop or "")],
                                  env=cenv, stdout=(r / "client.log").open("w"), stderr=subprocess.STDOUT)
        procs.append(client)
        widths = None
        for _ in range(150):
            text = (r / "client.log").read_text(encoding="utf-8", errors="replace")
            if "MOOS_FRAMES_CLIENT " in text:
                widths = json.loads(text.split("MOOS_FRAMES_CLIENT ", 1)[1].splitlines()[0])
                break
            if client.poll() is not None:
                raise RuntimeError("client exited: " + text[-2000:])
            time.sleep(0.1)
        else:
            raise RuntimeError("client never reported its windows")
        time.sleep(2.0)

        def qdbus(*a: str) -> subprocess.CompletedProcess:
            return subprocess.run([QDBUS, *a], env=env, text=True, capture_output=True, timeout=10)

        def script(name: str, source: str) -> None:
            p = r / f"{name}.js"
            p.write_text(source, encoding="utf-8")
            out = qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.loadScript", str(p), name)
            if out.returncode:
                raise RuntimeError(out.stderr)
            out = qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.start")
            if out.returncode:
                raise RuntimeError(out.stderr)
            time.sleep(0.8)

        # Gtk/Qt can publish allocations before their first Wayland buffer is
        # managed by KWin. A fixed sleep can then measure no windows at all.
        # Wait for the actual native publication, never infer it from the PID.
        expected = {caption for _key, _w, _h, caption in spec}
        for attempt in range(20):
            marker = f"MOOS_FRAMES_READY_{attempt} "
            script(f"ready-{attempt}", "console.warn(" + json.dumps(marker) +
                   "+JSON.stringify(workspace.windowList().map(w=>w.caption)));")
            lines = [ln for ln in (r / "kwin.log").read_text(errors="replace").splitlines() if marker in ln]
            if lines and expected.issubset(set(json.loads(lines[-1].split(marker, 1)[1]))):
                break
        else:
            raise RuntimeError("native window publication did not become ready")

        session = dbus.bus.BusConnection("unix:path=" + str(run / "bus"))
        shot = dbus.Interface(session.get_object("org.kde.KWin", "/org/kde/KWin/ScreenShot2"),
                              "org.kde.KWin.ScreenShot2")

        def capture(method: str, *head) -> QImage:
            rd, wr = os.pipe()
            try:
                meta = getattr(shot, method)(*head, {"include-decoration": True, "include-shadow": False,
                                                      "native-resolution": True, "include-cursor": False},
                                             dbus.types.UnixFd(wr))
            finally:
                os.close(wr)
            data = bytearray()
            with os.fdopen(rd, "rb") as fh:
                while chunk := fh.read(1 << 20):
                    data += chunk
            w, h, stride, fmt = int(meta["width"]), int(meta["height"]), int(meta["stride"]), int(meta["format"])
            return QImage(bytes(data), w, h, stride, QImage.Format(fmt)).copy()

        places = {c: PLACES.get(k) for k, _w, _h, c in spec}
        maxed = [c for k, _w, _h, c in spec if k == "maximized"]
        # Restored windows first, over the backdrop, with the future maximized
        # window out of the way: desk.png shows shadows and hairlines in place.
        script("place", "const places=" + json.dumps(places, ensure_ascii=False) + ";const maxed=" +
               json.dumps(maxed, ensure_ascii=False) + ";for (const w of workspace.windowList()){"
               "if(w.caption==='MOOS_BACKDROP'){w.keepBelow=true;w.noBorder=true;"
               "w.frameGeometry={x:0,y:0,width:" + str(args.logical[0]) + ",height:" +
               str(args.logical[1]) + "};continue;}"
               "if(!w.normalWindow) continue; if(maxed.includes(w.caption)){w.minimized=true;continue;}"
               "const p=places[w.caption]; if(p){const g=w.frameGeometry;"
               "w.frameGeometry={x:p[0],y:p[1],width:g.width,height:g.height};}}")
        time.sleep(1.5)
        capture("CaptureActiveScreen").save(str(r / "desk.png"))
        script("maximize", "const maxed=" + json.dumps(maxed, ensure_ascii=False) + ";"
               "for (const w of workspace.windowList()){"
               "if(w.normalWindow && maxed.includes(w.caption)){w.minimized=false;w.setMaximize(true,true);"
               "workspace.activeWindow=w;}}")
        time.sleep(1.5)
        script("read", "const out=[];for (const w of workspace.windowList()){if(!w.normalWindow) continue;"
               "const f=w.frameGeometry,c=w.clientGeometry;out.push({caption:w.caption,id:String(w.internalId),"
               "frame:{x:f.x,y:f.y,width:f.width,height:f.height},client:{x:c.x,y:c.y,width:c.width,height:c.height}});}"
               "console.warn('MOOS_FRAMES_GEOMETRY '+JSON.stringify(out));")
        log = (r / "kwin.log").read_text(encoding="utf-8", errors="replace")
        line = [ln for ln in log.splitlines() if "MOOS_FRAMES_GEOMETRY " in ln]
        if not line:
            raise RuntimeError("KWin script reported no geometry; log tail: " + log[-1500:])
        geometry = {g["caption"]: g for g in json.loads(line[-1].split("MOOS_FRAMES_GEOMETRY ", 1)[1])}

        capture("CaptureActiveScreen").save(str(r / "screen.png"))
        for key, _w, _h, caption in spec:
            g = geometry.get(caption)
            if not g:
                result["windows"][key] = {"error": "window missing"}
                continue
            img = capture("CaptureWindow", g["id"])
            img.save(str(r / f"{key}.png"))
            result["windows"][key] = analyse(img, g, lay, key == "maximized", widths.get(caption, 0.0))
            expected_bar = lay["TitleHeight"] + lay["TitleEdgeTopMaximized" if key == "maximized" else "TitleEdgeTop"] + lay["TitleEdgeBottomMaximized" if key == "maximized" else "TitleEdgeBottom"]
            result["windows"][key]["declared_bar_matches"] = abs(result["windows"][key]["title_bar_logical"] - expected_bar) < 1.5
            result["windows"][key]["geometry"] = g
        result["result"] = "MEASURED"
    except Exception as exc:  # retained as evidence; the caller decides the verdict
        result["result"] = "ERROR"
        result["error"] = str(exc)
    finally:
        for p in reversed(procs):
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
        shutil.rmtree(run, ignore_errors=True)
    (r / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def analyse(img, g: dict, lay: dict, maximized: bool, text_width: float) -> dict:
    frame, client = g["frame"], g["client"]
    s = img.width() / frame["width"]
    bar = round((client["y"] - frame["y"]) * s)
    width = img.width()
    edge = lay["TitleEdgeLeftMaximized" if maximized else "TitleEdgeLeft"]
    top = lay["TitleEdgeTopMaximized" if maximized else "TitleEdgeTop"]
    margin = lay["ButtonMarginTopMaximized" if maximized else "ButtonMarginTop"]
    buttons = 3
    group = buttons * lay["ButtonWidth"] + (buttons - 1) * lay["ButtonSpacing"]

    def rgb(x: int, y: int) -> tuple[int, int, int]:
        c = img.pixelColor(x, y)
        return c.red(), c.green(), c.blue()

    # Each row has its own background: a frame's top highlight or a vertical
    # gradient is a full-width row of one colour, not caption ink. (At 150 % the
    # dark frame's bright top edge otherwise read as a caption spanning the bar.)
    ink = []
    for y in range(bar):
        counts: dict[tuple[int, int, int], int] = {}
        row = [rgb(x, y) for x in range(width)]
        for c in row[::2]:
            counts[c] = counts.get(c, 0) + 1
        bg = max(counts, key=counts.get)
        ink.append([sum(abs(a - b) for a, b in zip(c, bg)) > 90 for c in row])
    guard = round(6 * s)
    columns = [x for x in range(guard, width - guard) if any(ink[y][x] for y in range(guard // 2, bar))]
    left_group = (round(edge * s), round((edge + group) * s))
    right_group = (width - round((edge + group) * s), width - round(edge * s))

    def inside(x: int, span: tuple[int, int]) -> bool:
        return span[0] - 3 <= x <= span[1] + 3

    left_ink = [x for x in columns if inside(x, left_group)]
    right_ink = [x for x in columns if inside(x, right_group)]
    side = "left" if len(left_ink) > len(right_ink) else ("right" if right_ink else "none")
    group_span = left_group if side == "left" else right_group
    caption_cols = [x for x in columns if not inside(x, group_span)]
    out = {"logical_frame": [frame["width"], frame["height"]], "title_bar_logical": round(bar / s, 2),
           "button_side": side, "caption_present": bool(caption_cols)}
    if caption_cols:
        rows = [y for y in range(bar) if any(ink[y][x] for x in caption_cols)]
        lo, hi = min(caption_cols), max(caption_cols)
        out.update(caption_ink_logical=[round(lo / s, 1), round(hi / s, 1)],
                   caption_ink_width=round((hi - lo + 1) / s, 1),
                   caption_centre_offset=round(((lo + hi) / 2) / s - frame["width"] / 2, 1),
                   caption_rows_logical=[round(min(rows) / s, 1), round(max(rows) / s, 1)],
                   caption_text_advance=round(text_width, 1),
                   caption_complete=(hi - lo + 1) / s >= 0.9 * text_width if text_width else None)
    group_cols = [x for x in columns if inside(x, group_span)]
    if group_cols:
        rows = [y for y in range(bar) if any(ink[y][x] for x in group_cols)]
        out.update(button_rows_logical=[round(min(rows) / s, 1), round(max(rows) / s, 1)],
                   button_centre_offset=round(((min(rows) + max(rows)) / 2) / s - (bar / s) / 2, 1),
                   button_expected_top=top + margin)
    return out


def frame_failures(results: list[dict]) -> list[tuple[str, str, dict]]:
    """Windows whose caption is missing, elided or >2 logical px off centre, or whose
    actions are not on the locale's start side (right for Arabic, left for English)."""
    bad = []
    for r in results:
        start = "right" if r["lang"] == "ar" else "left"
        for key, w in r.get("windows", {}).items():
            offset = w.get("caption_centre_offset")
            rows = w.get("caption_rows_logical", [])
            room = len(rows) == 2 and rows[0] >= 2 and rows[1] <= w.get("title_bar_logical", 0) - 2
            if (not w.get("caption_present") or not w.get("caption_complete")
                    or not w.get("declared_bar_matches")
                    or not room
                    or offset is None or abs(offset) > 2 or w.get("button_side") != start):
                bad.append((r["theme"], key, w))
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theme-root", type=pathlib.Path, default=INSTALLED)
    ap.add_argument("--theme", action="append")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--lang", choices=("ar", "en"), default="ar")
    ap.add_argument("--compose", choices=("O2",), default="O2")
    ap.add_argument("--kwinrc", type=pathlib.Path,
                    help="read ButtonsOnLeft/Right from this kwinrc (default: the repository's "
                         "shipped file for --theme-root inside it, else /etc/xdg/kwinrc)")
    ap.add_argument("--left", help="override ButtonsOnLeft")
    ap.add_argument("--right", help="override ButtonsOnRight")
    ap.add_argument("--border-size", help="override the shipped KWin BorderSize (None, Normal, ...)")
    ap.add_argument("--backdrop", type=pathlib.Path,
                    help="a picture shown under the restored windows (desk.png review frame)")
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 unless every caption is present, complete and within 2 logical px "
                         "of its window centre, and the actions sit on the locale's start side")
    args = ap.parse_args()
    # Qt ignores relative HOME/XDG paths and then silently loads installed
    # decoration bytes. Resolve before creating any private session inputs.
    args.theme_root = args.theme_root.resolve()
    if args.backdrop is not None:
        args.backdrop = args.backdrop.resolve()
    if args.out is not None:
        args.out = args.out.resolve()
    args.logical = (1600, 1040)
    repo = pathlib.Path(__file__).resolve().parents[2]
    if args.kwinrc is None:
        inside = args.theme_root.resolve().is_relative_to(repo)
        args.kwinrc = repo / "system_files/etc/xdg/kwinrc" if inside else pathlib.Path("/etc/xdg/kwinrc")
    shipped = kwin_decoration(args.kwinrc)
    args.left = shipped["ButtonsOnLeft"] if args.left is None else args.left
    args.right = shipped["ButtonsOnRight"] if args.right is None else args.right
    args.border_size = shipped["BorderSize"] if args.border_size is None else args.border_size
    args.border_size_auto = "false" if args.border_size != shipped["BorderSize"] else shipped["BorderSizeAuto"]
    themes = args.theme or sorted(p.name for p in args.theme_root.iterdir() if (p / "decoration.svg").exists())
    base = args.out or pathlib.Path(tempfile.mkdtemp(prefix="moos-window-frames-"))
    base.mkdir(parents=True, exist_ok=True)
    print(base, flush=True)
    results = [run_one(args, t, base) for t in themes]
    (base / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for res in results:
        print(json.dumps({"theme": res["theme"], "result": res["result"], "error": res.get("error"),
                          "windows": {k: {kk: v.get(kk) for kk in ("button_side", "caption_present",
                                                                    "caption_centre_offset", "caption_complete",
                                                                    "title_bar_logical")}
                                      for k, v in res.get("windows", {}).items()}}, ensure_ascii=False))
    if not all(r["result"] == "MEASURED" for r in results):
        return 1
    if args.check:
        bad = frame_failures(results)
        for theme, key, w in bad:
            print("FRAME_CHECK_FAILED", theme, key, json.dumps(w, ensure_ascii=False))
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
