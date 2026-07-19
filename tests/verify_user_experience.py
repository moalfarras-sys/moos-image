#!/usr/bin/env python3
"""Static gates for the active MoOS login/desktop experience."""

from pathlib import Path
import ast
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


# ── Gate the code, not the comment explaining the code ────────────────────────
#
# Every file in this repo documents the bug it exists to prevent, which means the
# thing a gate searches for is usually ALSO sitting in a comment two lines above the
# fix. A gate written as `"Kawkab Mono" in fontconfig_text` therefore passes even
# after Kawkab Mono has been deleted from the rules — the comment still names it.
#
# That is not hypothetical. Both of these were written that way first, and both
# stayed green when the thing they guard was removed. AGENTS.md: "Prove a new gate
# bites by breaking the thing it guards and watching it go red." These two did not,
# until the comments were stripped.
def code(text: str, style: str = "hash") -> str:
    """Strip comments so a gate cannot be satisfied by prose."""
    if style == "xml":
        return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    marker = "//" if style == "slash" else "#"
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith(marker)
    )


# One product, one launcher. Ignore development templates and documentation.
launchers = []
for path in (ROOT / "system_files/usr/share/applications").glob("*.desktop"):
    text = path.read_text(encoding="utf-8")
    if re.search(r"^Name=Mo (?:PC )?Remote(?: Personal)?$", text, re.MULTILINE):
        launchers.append(path.name)
require(launchers == ["org.moos.remote.desktop"],
        f"Mo Remote must have exactly one launcher; found {launchers}")

# The server must only join a real Plasma workspace. default.target caused
# root, SDDM, and the desktop user to race for port 8765 on real hardware.
unit = read("system_files/usr/lib/systemd/user/mo-remote-personal.service")
require("ConditionUser=!@system" in unit, "Mo Remote must reject system users")
require("WantedBy=plasma-workspace.target" in unit,
        "Mo Remote must start with the Plasma workspace")
require("WantedBy=default.target" not in unit,
        "Mo Remote must not be globally attached to default.target")
require("WAYLAND_DISPLAY=wayland-0" not in unit,
        "Mo Remote must not guess the Wayland socket name")
require('find "%t" -maxdepth 1 -type s -name "wayland-*"' in unit,
        "Mo Remote must discover the active Wayland socket")

remote_desktop = read("system_files/usr/share/applications/org.moos.remote.desktop")
require("Exec=/usr/bin/mo-pc-remote" in remote_desktop,
        "Mo PC Remote must launch its native control center")
require("Icon=moos-pc-remote" in remote_desktop,
        "Mo PC Remote must use its first-party MoOS icon, not the retired vendored name")
require("xdg-open" not in remote_desktop and "http://" not in remote_desktop,
        "Mo PC Remote launcher must never open an external browser")
native_remote = read("system_files/usr/bin/mo-pc-remote")
require("Gtk.Application" in native_remote,
        "Mo PC Remote control center must be a native GTK application")
require('UNIT = "mo-remote-personal.service"' in native_remote,
        "Mo PC Remote must manage the MoPC backend")

# ── Remote control must be a whole, regression-proof chain ────────────────────
#
# Mo PC Remote is how the owner drives this machine from a phone, so every link
# must be gated: the UI button, the router case, and the backend action. Any one
# of them going quiet makes "I can't reach my computer" with no error anywhere.
# Each assertion reads the CODE, never the prose — the comment above names
# "mo-remote-personal.service" on purpose, so a gate that matched the string
# would pass green while the route that opens it had been deleted.
moai_remote_qml = code(read("system_files/usr/share/moos/apps/moai/main.qml"), "slash")
router_remote = code(read("system_files/usr/bin/moos-open"))
do_remote = code(read("system_files/usr/bin/moai-do"))
for route in ("remote/start", "remote/stop", "remote/restart", "app/remote",
              "do/remote-anywhere"):
    require('moos://%s"' % route in moai_remote_qml,
            "Mo AI must offer the %s action (it is how the owner reaches this "
            "machine remotely)" % route)
require('remote/start)' in router_remote and 'remote/stop)' in router_remote \
        and 'remote/restart)' in router_remote,
        "moos-open must route remote/start|stop|restart to the MoPC backend")
require('remote-anywhere)' in router_remote,
        "moos-open must route do/remote-anywhere to moai-do")
# The start route is privileged by CONFIRM, not by root: it enables a persistent
# service, so a drive-by moos://remote/start must not open remote access silently.
require('remote/start)   confirm' in router_remote,
        "moos-open must confirm before enabling Mo PC Remote (persistent access "
        "must never be opened by a drive-by moos:// link)")
# The user-service helper must use enable/disable --now, so the panel and the
# router never disagree about whether it returns after a reboot. NOT plain
# start/stop, which would leave it off next boot.
require('REMOTE_UNIT="mo-remote-personal.service"' in router_remote,
        "moos-open must target mo-remote-personal.service for remote control")
# remote_ctl forwards its args to `systemctl --user "$@" UNIT`, and the callers
# pass `enable --now` / `disable --now` (see the remote/start|stop|restart arms
# below). Assert the forwarding mechanism AND that both persistent verbs are used
# by the callers — not a literal expanded string, which the helper does not write.
require('systemctl --user "$@"' in router_remote or 'systemctl --user "$@"' in router_remote,
        "moos-open's remote_ctl must forward its args to systemctl --user, so the "
        "callers' enable/disable --now actually reach the unit")
require('remote_ctl enable --now' in router_remote,
        "the remote/start arm must enable --now (persist across reboot), matching "
        "the Mo PC Remote panel")
require('remote_ctl disable --now' in router_remote,
        "the remote/stop arm must disable --now (stop AND persist off)")
require("do_remote_anywhere()" in do_remote and 'remote-anywhere) do_remote_anywhere' in do_remote,
        "moai-do must DEFINE and DISPATCH do_remote_anywhere — the Tailscale "
        "serve path that makes Mo PC Remote reachable from mobile data")
require("tailscale serve" in do_remote,
        "do_remote_anywhere must run `tailscale serve` to give the machine a "
        "real HTTPS name on the tailnet (LAN IP over http dies on mobile data)")
require("tailscale set --operator" in do_remote,
        "do_remote_anywhere must grant the user Tailscale operator so later "
        "serve changes need no root")

# First-party dock icons are SVG masters plus raster fallbacks. Plasma can request
# any of these sizes depending on scale factor; a single 512 px PNG makes a 16 px
# task icon look soft and, historically, Remote had only that one file.
moai_desktop = read("system_files/usr/share/applications/org.moos.moai.desktop")
require("Icon=moos-moai" in moai_desktop,
        "Mo AI must use the MoOS intelligent-core icon")
for icon in ("moos-moai", "moos-pc-remote"):
    master = ROOT / f"system_files/usr/share/icons/hicolor/scalable/apps/{icon}.svg"
    require(master.is_file(), f"{icon} must ship a scalable SVG master")
    if master.is_file():
        svg = code(master.read_text(encoding="utf-8"), "xml")
        if icon == "moos-moai":
            # 2026-07-16: the owner replaced Mo AI's vector icon with commissioned
            # raster artwork. The scalable entry is now a wrapper that must embed
            # the EXACT 1024px master (artwork/icons/mo-ai-1024.png) — anything
            # else (a text logo, a recompressed or low-res bitmap) is a downgrade.
            import base64 as _b64
            master_png = ROOT / "artwork/icons/mo-ai-1024.png"
            require(master_png.is_file(), "the Mo AI 1024px icon master is missing from artwork/icons")
            if master_png.is_file():
                require(_b64.b64encode(master_png.read_bytes()).decode() in svg,
                        "moos-moai.svg must embed the exact mo-ai-1024.png master, byte for byte")
        else:
            require("<text" not in svg and "<image" not in svg,
                    f"{icon} must remain original vector geometry with no text or embedded bitmap")
    for size in (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512):
        png = ROOT / f"system_files/usr/share/icons/hicolor/{size}x{size}/apps/{icon}.png"
        require(png.is_file(), f"{icon} is missing its {size}px dock fallback")

# The store's two icon names (moos-store for the store itself, mo-store for the
# hidden Discover entry) are the SAME artwork — if they ever drift, one surface
# quietly keeps an old brand. And every rendered size must carry real alpha:
# the source art arrived with a baked-in checkerboard, and a regression to an
# opaque background would put a white square on the dock.
for size in (16, 22, 24, 32, 48, 64, 128, 256, 512):
    a = ROOT / f"system_files/usr/share/icons/hicolor/{size}x{size}/apps/moos-store.png"
    b = ROOT / f"system_files/usr/share/icons/hicolor/{size}x{size}/apps/mo-store.png"
    require(a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes(),
            f"moos-store and mo-store must stay byte-identical at {size}px")
for name, sizes in (("moos-moai", (16, 512)), ("moos-store", (16, 512))):
    for size in sizes:
        png = ROOT / f"system_files/usr/share/icons/hicolor/{size}x{size}/apps/{name}.png"
        if png.is_file():
            data = png.read_bytes()
            require(data[25:26] == b"\x06",
                    f"{name} {size}px must be RGBA — a flattened background is a regression")
require((ROOT / "moremote/Logo.png").read_bytes()
        == (ROOT / "system_files/usr/share/icons/hicolor/512x512/apps/moos-pc-remote.png").read_bytes(),
        "the vendored Mo PC Remote icon and the OS icon must stay byte-identical")

device_plan = read("system_files/usr/bin/moos-device-plan")
require('"missing_recommended_apps"' in device_plan and '"actions"' in device_plan,
        "hardware detection must produce an actionable installation plan")
setup = read("system_files/usr/bin/moos-setup")
require('MODE="${1:---interactive}"' in setup and "missing_recommended_apps" in setup,
        "first-run setup must support a hardware-aware smart mode")
router = read("system_files/usr/bin/moos-open")
for route in ("do/smart-setup", "do/setup-gaming", "do/install-nvidia", "do/setup-waydroid"):
    require(route in router, f"missing safe MoOS action route: {route}")

# The Hardware Centre and the Compatibility Hub are panels inside Mo AI now, so
# their guarantees are asserted against Mo AI's QML. They still hold.
moai_qml = read("system_files/usr/share/moos/apps/moai/main.qml")

# First-party QML cards must follow the active KDE colour scheme. Mo AI and the
# Welcome app used to carry Nova's navy canvas/card/text hex values inside their
# own QML, so applying a complete light Global Theme still opened two dark-blue
# applications. Gate the token BINDINGS (not merely the word "palette"), and
# strip comments so the explanation above cannot make this pass.
moai_palette_code = code(moai_qml, "slash")
welcome_qml = read("system_files/usr/share/moos/apps/welcome/main.qml")
welcome_palette_code = code(welcome_qml, "slash")
store_qml = read("system_files/usr/share/moos/apps/store/main.qml")
store_palette_code = code(store_qml, "slash")

# Mo Store must make the whole section installable in one tap (the group-per-
# category pick) and must SHOW how each app installs, so the method is never a
# mystery — the owner's two asks. Both drive real, existing plumbing (addMany
# feeds the cart; the real install streams from moos-install).
require('"أضِف كل القسم"' in store_qml and "win.addMany(ids)" in store_qml,
        "Mo Store must offer a per-section 'Add all' that carts the whole category")
require('card.modelData.source === "flathub" ? "Flatpak"' in store_qml,
        "Mo Store cards must show each app's install method (Flatpak / Web / MoOS)")

# Launch feedback must be CALM but present. An earlier revision shipped the "prominent"
# form (bouncing icon AND a launching-state task-manager button) as a SYSTEM default, so
# it hit every app: opening the terminal or any pinned app flashed a bounce and a second
# task button, which the owner read as "it opens a new window every click". Keep the busy
# cursor (immediate, universally understood) and forbid the bounce and the extra task
# button, so the click is acknowledged without the surface flashing.
klaunch = read("system_files/etc/xdg/klaunchrc")
require("BusyCursor=true" in klaunch
        and "Bouncing=false" in klaunch
        and "TaskbarButton=false" in klaunch,
        "MoOS launch feedback must be calm: busy cursor on, bounce + extra task button off "
        "(the prominent form read as opening a new window on every click)")

# Installing a browser makes it the default — the owner's ask: click a link, YOUR
# browser opens, the one you just chose. moos-install sets the web + http/https
# handlers to the just-installed browser (in the user's own config, no root), and
# knows the common browsers.
moos_install = read("system_files/usr/bin/moos-install")
require("xdg-settings set default-web-browser" in moos_install
        and "x-scheme-handler/https" in moos_install,
        "installing a browser must set it as the default web + http/https handler")
require("com.google.Chrome" in moos_install and "org.mozilla.firefox" in moos_install,
        "the browser-default step must recognise the common browsers (Chrome/Firefox/Brave/…)")

for token, role in {
    "surface0": "root.palette.base",
    "surface1": "root.palette.alternateBase",
    "surface2": "root.palette.button",
    "chrome": "root.palette.window",
    "hairline": "root.palette.mid",
    "textHi": "root.palette.windowText",
    "textLo": "root.palette.placeholderText",
    "novaBlue": "root.palette.highlight",
    "novaCyan": "root.palette.link",
    "novaViolet": "root.palette.linkVisited",
    "onAccent": "root.palette.highlightedText",
}.items():
    require(re.search(
        rf"readonly\s+property\s+color\s+{token}\s*:\s*{re.escape(role)}\b",
        moai_palette_code,
    ) is not None,
            f"Mo AI's {token} token must follow {role}, not a hard-coded Nova colour")

# The same semantic tokens hold on BOTH catalog surfaces: Mo Store (the
# standalone storefront, apps/store) and the Welcome onboarding wizard
# (apps/welcome). A hard-coded canvas in either one reopens the "two dark-blue
# applications on a light theme" bug.
for surface_label, palette_code in (("Mo Store", store_palette_code),
                                    ("MoOS Welcome", welcome_palette_code)):
    for token, role in {
        "canvas": "win.palette.base",
        "surface": "win.palette.alternateBase",
        "raised": "win.palette.button",
        "chrome": "win.palette.window",
        "outline": "win.palette.mid",
        "txt": "win.palette.windowText",
        "txt2": "win.palette.placeholderText",
        "blue": "win.palette.highlight",
        "cyan": "win.palette.link",
        "violet": "win.palette.linkVisited",
        "onAccent": "win.palette.highlightedText",
    }.items():
        require(re.search(
            rf"readonly\s+property\s+color\s+{token}\s*:\s*{re.escape(role)}\b",
            palette_code,
        ) is not None,
                f"{surface_label}'s {token} token must follow {role}, not Nova's fixed palette")

legacy_nova_surfaces = {
    "#0b1220", "#111a2e", "#16233a", "#1a2740", "#263a5c", "#263852",
    "#f4f8ff", "#e6edf7", "#9fb0c9", "#7f94b5", "#0c1424", "#070c16",
    "#0a1120", "#0c1526", "#16233c", "#0e1830",
}
# The MoOS Welcome's "Pick your look" grid PREVIEWS every theme in the family, so it
# legitimately names each theme's own canvas/accent hexes (Nova's navy among them) as
# swatch VALUES — not as the app's own chrome. Strip those swatch property lines
# (canvasC/chromeC/accentC/txtC) before the structural-Nova scan, so a *preview* of Nova
# is not misread as Nova *chrome*. The rest of Welcome is still held to the palette tokens.
welcome_scan = re.sub(r"(?m)^\s*(canvasC|chromeC|accentC|txtC)\s*:.*$", "",
                      welcome_palette_code)
for app, qml_code in (("Mo AI", moai_palette_code),
                      ("MoOS Welcome", welcome_scan),
                      ("Mo Store", store_palette_code)):
    retained = sorted(colour for colour in legacy_nova_surfaces
                      if colour in qml_code.lower())
    require(not retained,
            f"{app} must not retain Nova's structural navy/text colours: {retained}")

require("component Card: Rectangle" in moai_palette_code
        and "color: root.surface1" in moai_palette_code,
        "Mo AI's shared Card must consume the palette-backed card token")
# The store's app cards carry no per-card accent (the old `cardItem.modelData.c`);
# each card fills with the palette surface token and borders on the palette accent
# (when selected) or the palette outline (otherwise). The relationship is
# unchanged — cards follow the KDE scheme, never a fixed Nova colour — so gate the
# bindings, still card-specific (`card.selected` exists only on the store's app
# card), so a hard-coded card colour still goes red.
require("Qt.rgba(win.surface.r" in store_palette_code
        and "border.color: card.selected ? win.accent" in store_palette_code
        and ": win.outline" in store_palette_code,
        "Mo Store cards must consume the palette-backed surface and outline tokens")
# The Welcome's pick cards (look/direction/app) follow the same contract with
# their own delegate ids — the `.selected ? win.accent` shape is the pin.
require("Qt.rgba(win.surface.r" in welcome_palette_code
        and ".selected ? win.accent : win.outline" in welcome_palette_code,
        "MoOS Welcome cards must consume the palette-backed surface and outline tokens")
for surface_label, palette_code in (("Mo Store", store_palette_code),
                                    ("MoOS Welcome", welcome_palette_code)):
    require("NovaHorizonII" not in palette_code,
            f"{surface_label} must not paint Nova's dark wallpaper over a light KDE palette")

require("sudo waydroid init" not in moai_qml,
        "Mo AI must use the confirmed workflow, not copy sudo commands")
require('moos://do/setup-gaming' in moai_qml,
        "Mo AI's Compatibility panel must expose the focused gaming installer")
require('moos://do/setup-waydroid' in moai_qml,
        "Mo AI's Compatibility panel must expose the Android (Waydroid) setup")
require('moos://do/setup-windows' in moai_qml,
        "Mo AI's Compatibility panel must expose the Windows (Bottles) setup as a real flow, "
        "not a bare Flatpak install that leaves the user staring at an unopened Bottles")

# ── launch() must not reach an out-of-scope anim id (orbPulse) ─────────────────
#
# Mo AI's launch(url, label) used to call orbPulse.restart() to play the "heard
# you" pulse. orbPulse is the id of a SequentialAnimation declared INSIDE the
# MoOrb component, so a root-scope function cannot see it — QML threw
# "ReferenceError: orbPulse is not defined" every time a link opened, confirmed
# live in the journal. The pulse must be driven by a signal ON the component
# (MoOrb.signal pulse()), and launch() must call it on the hero orb instance by
# id (heroOrb.pulse()), never by the bare nested id. Strip comments: the fix's
# own comment names "orbPulse", so a gate that matched the word would pass green
# while the call came back.
moai_qml_code = code(moai_qml, "slash")
require("signal pulse()" in moai_qml_code,
        "MoOrb must expose a signal pulse() so the launch feedback can be triggered from "
        "scope — a root function cannot reach a nested id like orbPulse")
require("id: heroOrb" in moai_qml_code,
        "the visible Mo AI orb must carry id heroOrb, so launch() can pulse it by id")
# The nested component may legitimately call orbPulse.restart() (it is in scope
# there). Only the ROOT launch() function must not — that is the line that threw
# "orbPulse is not defined". Gate the function body, not the whole file.
_launch = re.search(r"function\s+launch\([^)]*\)\s*\{(.*?)\n    \}", moai_qml_code, re.S)
require(_launch is not None, "Mo AI must define launch(url, label)")
if _launch:
    require("orbPulse.restart()" not in _launch.group(1),
            "launch() must not call orbPulse.restart() — orbPulse is a nested component id "
            "and is out of scope from root, which threw 'orbPulse is not defined' on every open")
require('heroOrb.pulse()' in moai_qml_code,
        "launch() must pulse the hero orb by id (heroOrb.pulse()), the in-scope way to fire "
        "the launch feedback")

# Saving Mo AI's mode must always answer the HTTP request. A prior bind-race fix
# accidentally indented self._send() under the "gateway already active" branch,
# so the first save that had to start the gateway succeeded server-side but left
# the UI waiting forever.
_moai_control_for_save = code(read("system_files/usr/bin/moai-control"), "hash")
_gateway_start = re.search(
    r"if not user_unit_active\(GATEWAY_UNIT\):\s+"
    r"sysctl\(\"enable\", \"--now\", GATEWAY_UNIT\)\s+"
    r"else:\s+sysctl\(\"enable\", GATEWAY_UNIT\)\s+"
    r"self\._send\(200, \{\"ok\": True, \"mode\": mode\}\)",
    _moai_control_for_save,
)
require(_gateway_start is not None,
        "Mo AI config save must answer after either starting or reusing the gateway; "
        "self._send() cannot be conditional on the gateway already being active")

# Whitespace-sensitive Python can satisfy the sequence above while placing the
# whole sequence in H's class body. That imports as far as the class definition,
# then crashes immediately because neither `self` nor `mode` exists there. Check
# the syntax tree: the gateway activation and response must belong to do_POST.
_control_tree = ast.parse(read("system_files/usr/bin/moai-control"))
_control_imports = {
    alias.name
    for node in _control_tree.body
    if isinstance(node, ast.Import)
    for alias in node.names
}
require(
    "sys" in _control_imports,
    "moai-control's port-busy recovery writes to sys.stderr, so sys must be imported",
)
_handler = next((n for n in _control_tree.body
                 if isinstance(n, ast.ClassDef) and n.name == "H"), None)
_post = next((n for n in (_handler.body if _handler else [])
              if isinstance(n, ast.FunctionDef) and n.name == "do_POST"), None)
require(_post is not None, "moai-control must define H.do_POST")
if _handler:
    require(not any(isinstance(n, (ast.If, ast.Expr)) for n in _handler.body),
            "moai-control H class body must contain only definitions/assignments; request code "
            "at class scope crashes the service during startup")
if _post:
    _post_calls = [n for n in ast.walk(_post) if isinstance(n, ast.Call)]
    require(any(isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "self" and n.func.attr == "_send"
                and n.lineno > 1235 for n in _post_calls),
            "Mo AI config save response must execute inside H.do_POST")

# ── The camera the user actually gets must run on THIS desktop ────────────────
#
# "Install a camera" resolved, on Flathub's top hit, to io.github.cosmic_utils.camera:
# a COSMIC-desktop app that installs cleanly and then PANICS on KDE Plasma — it hunts
# com.system76.Cosmic* D-Bus watchers that do not exist here and dies in its wgpu video
# renderer. The webcam and libcamera were fine; the app was wrong for the desktop.
#
# Gate the RECOMMENDED-apps list, not the whole file: the prompt is allowed to NAME the
# bad id as one to avoid (that is the opposite of recommending it), but the one-click
# app catalogue must offer Kamoso and must never offer the COSMIC camera.
appcatalog_match = re.search(r"property var appCatalog:\s*\[(.*?)\]", moai_qml, re.DOTALL)
require(appcatalog_match is not None, "Mo AI must expose an appCatalog of recommended apps")
appcatalog = appcatalog_match.group(1) if appcatalog_match else ""
require("org.gnome.Snapshot" in appcatalog,
        "Mo AI's recommended apps must offer a camera that actually runs here — Snapshot "
        "reaches the webcam through the XDG camera portal, verified live on this machine")
require("cosmic_utils.camera" not in appcatalog,
        "Mo AI must not OFFER io.github.cosmic_utils.camera as a recommended app — it is a "
        "COSMIC-desktop app and panics on KDE Plasma")
# And not Kamoso either, which is the harder lesson. It IS KDE-native, it WAS in this
# catalogue, and this gate used to demand it — because "KDE-native" was mistaken for
# "works". It opens and then segfaults inside GStreamer's camerabin after 15-45 seconds
# (reproduced twice on 2026-07-13, with 6.5 GB free on the GPU, while gst-launch grabbed a
# clean frame from the same webcam). A recommendation the OS makes is a promise; gate on
# the promise, not on the toolkit.
require("org.kde.kamoso" not in appcatalog,
        "Mo AI must not offer Kamoso: KDE-native or not, it segfaults in GStreamer seconds "
        "after launch on this hardware — 'it opened once' is not verification")

# The old centres must keep opening — as commands, into their panel in Mo AI.
for shim, panel in (("moos-hardware", "device"), ("moos-compat", "compat")):
    text = read(f"system_files/usr/bin/{shim}")
    require(f"moai --panel {panel}" in text,
            f"{shim} must open Mo AI on the {panel} panel")

# ── Every moos:// URL a QML app opens must have a route in moos-open ─────────
#
# THIS is the gate that was missing. Mo AI once shipped with Start/Stop/Reconnect
# buttons for Mo PC Remote, an Install button on every app, and Install/Run for
# Codex and Claude — eleven buttons in total, opening moos:// URLs that moos-open
# had no case for. Every one of them popped "unknown MoOS action" and did
# nothing, and every gate stayed green, because no gate compared the two files.
# A button that opens a route that does not exist is not a cosmetic bug; it is a
# feature that does not exist.
def routes_declared(router_text: str) -> set[str]:
    """The case labels in moos-open's dispatch, e.g. {'do/update', 'remote/start'}.

    The bare `*)` default arm is EXCLUDED. It is the "unknown MoOS action" error
    path, not a route — counting it would make `startswith("")` true for every
    URL on earth and quietly turn this whole gate into a no-op. (It did, on the
    first version of this function.)
    """
    declared: set[str] = set()
    for match in re.finditer(r"^\s{4}([a-z0-9/*|-]+)\)", router_text, re.MULTILINE):
        for label in match.group(1).split("|"):
            label = label.strip()
            if label != "*":
                declared.add(label)
    return declared


def route_is_covered(url_path: str, declared: set[str]) -> bool:
    if url_path in declared:
        return True
    # A wildcard case such as `apps/install/*` covers everything under its prefix.
    return any(
        pattern.endswith("*") and pattern != "*"
        and url_path.startswith(pattern[:-1])
        for pattern in declared
    )


declared_routes = routes_declared(router)
require("*" not in declared_routes, "the default arm must not count as a route")
require("apps/install/*" in declared_routes,
        "moos-open must accept an app id to install (apps/install/*)")

# ── One language, chosen by the user, applied to the whole session ───────────
# MoOS shows ONE language (the user's), not both stacked in every window. The
# Welcome's language pick fires moos://lang/<code>; moos-open routes it to
# /usr/bin/moos-lang, which writes only the user's own plasma-localerc + flatpak
# language (no root). All three pieces must ship together or the pick is a dead
# tap, so gate the chain the same way the theme/install chains are gated.
require("lang/ar" in declared_routes and "lang/en" in declared_routes,
        "moos-open must route the Welcome's language pick (lang/ar, lang/en) — "
        "without it the language buttons do nothing")
require((ROOT / "system_files/usr/bin/moos-lang").is_file(),
        "the language writer /usr/bin/moos-lang is missing — moos-open's lang route "
        "would call a command that does not exist")
moos_lang = code(read("system_files/usr/bin/moos-lang"))
require("plasma-localerc" in moos_lang and "LANGUAGE" in moos_lang,
        "moos-lang must set the Plasma UI language via plasma-localerc — that one "
        "write is what carries the choice to the desktop, the MoOS apps and the session")
require("flatpak config" in moos_lang and "languages" in moos_lang,
        "moos-lang must set the Flatpak language too, or Flathub apps stay in the "
        "install-time language after a switch")
welcome_lang = code(read("system_files/usr/share/moos/apps/welcome/main.qml"), "slash")
require("moos://lang/" in welcome_lang and "chooseLang" in welcome_lang,
        "the Welcome must offer the language pick that drives the whole session")
# The counterpart: opening an installed app. Without this route Mo AI can install a
# program and then have no way to launch it — the exact gap that made "install a
# camera" end at a fresh icon nobody had asked for instead of a live camera.
require("apps/run/*" in declared_routes,
        "moos-open must accept an app id to OPEN (apps/run/*), or an installed app "
        "cannot be launched from Mo AI")

# ── Double-click a .exe or an .apk and it runs ───────────────────────────────
# The last mile of "run any program from any system". Three pieces have to line up, and if
# any one of them drops out the double-click dies SILENTLY — the file manager just opens the
# binary in a text editor, which is precisely what MoOS did before this shipped:
#   1. the runner exists and knows both worlds,
#   2. a desktop entry claims the types (including the two a real .exe actually resolves to
#      on this image — x-msdownload and vnd.microsoft.portable-executable; Bottles' own entry
#      claims neither by that name),
#   3. the system default points at the runner — and apply-theme pins it in the user's own
#      mimeapps.list, which outranks /etc/xdg.
runner = code(read("system_files/usr/bin/moos-run-foreign"))
require("com.usebottles.bottles" in runner and "waydroid" in runner,
        "moos-run-foreign must route Windows files to Bottles and Android files to Waydroid")
require("setup-windows" in runner and "setup-waydroid" in runner,
        "moos-run-foreign must offer the one-time runtime setup when the runtime is missing — "
        "a first .exe on a fresh MoOS lands before Bottles exists, and failing silently there "
        "is the whole bug this closes")
runner_desktop = read("system_files/usr/share/applications/org.moos.runforeign.desktop")
system_mimeapps = read("system_files/etc/xdg/mimeapps.list")
for mime in ("application/x-msdownload",
             "application/vnd.microsoft.portable-executable",
             "application/vnd.android.package-archive"):
    require(mime in runner_desktop,
            f"org.moos.runforeign.desktop must claim {mime}")
    require(f"{mime}=org.moos.runforeign.desktop" in system_mimeapps,
            f"/etc/xdg/mimeapps.list must make the MoOS runner the default for {mime}")
require("org.moos.runforeign.desktop" in code(read("system_files/usr/bin/moos-apply-theme")),
        "moos-apply-theme must pin the MoOS runner in the user's mimeapps.list — the user's "
        "file outranks /etc/xdg, so shipping the default is only half the fix")

# ── Mo AI answers the NEED, not the keyword ──────────────────────────────────
# Flathub ranks by popularity, and for "camera" that puts a COSMIC-desktop app on top: it
# installs, then panics on Plasma. The user's camera "did not work" while the webcam, the
# install and libcamera were all fine. So the search ranks the desktop-native answer first
# and labels apps built for another desktop — and BOTH halves are gated, because a ranking
# the UI never renders is a ranking the user never receives.
control = code(read("system_files/usr/bin/moai-control"))
require("KNOWN_GOOD" in control and "org.gnome.Snapshot" in control,
        "moai-control must carry the need→known-good-app table (camera → org.gnome.Snapshot is "
        "its archetype); without it Flathub's raw top hit reaches the user")
require("def desktop_mismatch" in control and "cosmic" in control,
        "moai-control must label desktop-mismatched apps — a COSMIC/GNOME-only Flatpak "
        "installs cleanly on MoOS and then crashes, and the user is told AFTER the download")
# Local brains are MANAGED from Settings, not only downloaded from the chat picker.
# The backend must expose a /delete that is the safe mirror of /pull: it removes a
# model RamaLama actually lists as installed (never something user-typed), and
# never the active brain (that would break a running conversation).
require("def delete_model" in control,
        "moai-control needs delete_model() — the safe mirror of start_pull()")
require("/delete" in control,
        "moai-control must route /delete to remove a local model from Settings")
require("not an installed local model" in control,
        "moai-control /delete must refuse anything not actually installed (safe by the live set, "
        "the same allowlist discipline as /pull — never a user-typed shell argument)")
require("the active brain" in control,
        "moai-control /delete must refuse deleting the model the brain is currently serving")
moai_qml = read("system_files/usr/share/moos/apps/moai/main.qml")
# …and Settings must actually offer download / use / delete on each local model —
# a backend endpoint the UI never calls is a feature the user never gets.
require("function deleteModel" in moai_qml and "root.deleteModel(" in moai_qml,
        "Mo AI Settings must let the user delete a local model")
require('controlApi + "/delete"' in moai_qml,
        "Mo AI's deleteModel must POST to moai-control's /delete")
require("النماذج المحلية" in moai_qml and "root.pickOrPull(" in moai_qml,
        "Mo AI Settings must show the Local models section with a one-tap download")
# Mo AI reasons about the system and offers SAFE repairs: a READ-ONLY /diagnose
# that runs moos-selfcheck, and a Settings panel that shows health + one-tap fixes,
# each fix a moai-do action behind confirmation — never a composed command.
require("def diagnose_system" in control and "/diagnose" in control,
        "moai-control must expose /diagnose — read-only system health from moos-selfcheck")
require("moos-selfcheck" in control,
        "diagnose must reason from moos-selfcheck, not invent its own health verdict")
require("function diagnoseSystem" in moai_qml and 'controlApi + "/diagnose"' in moai_qml,
        "Mo AI must call /diagnose from its System-health panel")
require("صحة النظام" in moai_qml
        and 'Qt.openUrlExternally("moos://do/" + modelData.id)' in moai_qml,
        "Mo AI's Diagnose panel must offer repairs as moos://do/<id> (moai-do confirm + Polkit), "
        "never a free-form command — the whole safety contract")
require("recommended" in moai_qml and "hit.note" in moai_qml,
        "Mo AI must render the pick and the warning (recommended / note) on each search hit — "
        "ranking them in the backend and not showing them changes nothing for the user")

# ── A first-party app must not be killed by the first-party brain ────────────
# MoOS ships a local LLM and a video player, and on an 8 GB card they cannot both have the
# memory. With the brain loaded (~6 GB held) MoPlayer could not create an EGL context —
# `eglMakeCurrent failed`, then libepoxy asserts and the process ABORTS. The user's own OS
# killed its own player on launch, with no message, because its own assistant was holding
# the graphics card. Core dumps on the maintainer's machine, 2026-07-13.
#
# moos-gpu-headroom unloads ONLY the brain (which reloads itself on the next message) and
# only when the card is nearly full. If either half of this drops out, the crash comes back
# and it looks exactly like a broken app.
headroom = code(read("system_files/usr/bin/moos-gpu-headroom"))
require("moai.service" in headroom and "nvidia-smi" in headroom,
        "moos-gpu-headroom must free the local brain — and nothing else — when the GPU is "
        "too full for an app to make a context")
require("moos-gpu-headroom" in code(read("system_files/usr/bin/moplayer")),
        "MoPlayer's launcher must ask for GPU headroom before starting: with the brain loaded "
        "it aborts on eglMakeCurrent, which reads to the user as a broken app")

# ── The image's copy of MoPlayer's launcher must BE MoPlayer's launcher ───────
# The launcher is the app's file (moplayer/packaging/moos/moplayer). The image only carries
# a copy of it at system_files/usr/bin/moplayer, and for two hours those two files silently
# disagreed: the GPU-headroom guard above existed ONLY in the image's copy. One `install -D`
# from the app's packaging — exactly what `just sync-moplayer` prints — and the guard is gone,
# with nothing to notice. `sync-moplayer` now performs that install itself; this is what
# catches it if the two ever drift again.
require(read("system_files/usr/bin/moplayer") == read("moplayer/packaging/moos/moplayer"),
        "system_files/usr/bin/moplayer must be byte-identical to moplayer/packaging/moos/moplayer "
        "— the launcher belongs to the app, and a divergent copy is one `install -D` away from "
        "dropping the GPU guard (run `just sync-moplayer`)")

# ── The vendored app must be the app that was committed ───────────────────────
# The vendored tree is built from `git ls-files`, so an UNTRACKED file in MoPlayer's working
# tree is copied by nobody: the image compiles source with an import pointing at a file that
# is not there, and the build fails twenty minutes in, inside a container. `sync-moplayer`
# refuses a dirty tree for that reason. Here we check the result: every Dart file the vendored
# source imports from its own lib/ has to exist in the vendored tree.
vendor_lib = ROOT / "moplayer" / "lib"
missing_imports: list[str] = []
for dart in vendor_lib.rglob("*.dart"):
    for target in re.findall(r"""import\s+['"]((?:\.{1,2}/)[^'"]+\.dart)['"]""",
                             dart.read_text(encoding="utf-8")):
        if not (dart.parent / target).resolve().exists():
            missing_imports.append(f"{dart.relative_to(ROOT)} -> {target}")
require(not missing_imports,
        "the vendored MoPlayer source imports files that were not vendored — its working tree "
        "had uncommitted files when it was synced, and the image build will fail on a missing "
        f"URI: {missing_imports[:3]}")

# ── One MoPlayer, not one per click ──────────────────────────────────────────
# Flutter's runner template sets G_APPLICATION_NON_UNIQUE, and with it every click in Kickoff
# starts a WHOLE NEW PROCESS. Found on the maintainer's machine on 2026-07-14: three MoPlayers
# running at once, each rendering video (~28% of a core apiece) on an 8 GB card that the local LLM
# already holds ~6 GB of — and kwin_wayland SIGSEGV'd on a swapchain allocation minutes later. He
# had clicked the icon again *because* the desktop felt slow.
#
# It is also wrong on the subscription's terms: max_connections = 1, so copy two fights copy one
# for the only stream the account is allowed and knocks it off the air.
#
# Comments stripped, because the fix's own comment says the words "G_APPLICATION_NON_UNIQUE".
runner = code(read("moplayer/linux/runner/my_application.cc"), "slash")
require("G_APPLICATION_NON_UNIQUE" not in runner,
        "MoPlayer must be a UNIQUE GApplication — NON_UNIQUE is what let three copies run at once, "
        "each holding VRAM on a card that has none to spare")
require("gtk_window_present" in runner and "gtk_application_get_windows" in runner,
        "a second launch must RAISE the window that already exists — a unique app whose activate() "
        "still builds a new window just moves the duplication inside one process")

# ── fcitx5 must not ship ─────────────────────────────────────────────────────
# It is a CJK input-method framework MoOS has no use for (Arabic and German are xkb layouts,
# which KWin handles natively), it arrives only as a dependency of a JAPANESE IME, and it has
# a launcher entry — so it is one click away. The moment it starts it rewrites the user's
# ~/.config/kxkbrc to `LayoutList=us` and their Arabic and German layouts are gone, silently.
# That happened on this machine: the maintainer could not type Arabic for two hours.
require("dnf5 -y remove fcitx5-mozc fcitx5" in code(read("build_files/build.sh")),
        "build.sh must remove fcitx5 — one launch of it wipes the user's keyboard layouts and "
        "nothing in the system notices")
selfcheck = code(read("system_files/usr/bin/moos-selfcheck"))
require("KeyboardLayouts.getLayoutsList" in selfcheck,
        "moos-selfcheck must read the layouts KWin ACTUALLY loaded, not localectl's system "
        "default — the system default stayed a perfect 'de,ara' while the session typed US, "
        "and the check reported green throughout")

# ── The console types the same keyboard the desktop types ────────────────────
# The installer derives keymap/layout/locale/timezone from the chosen language, and writes
# BOTH an X11 layout (/etc/X11/xorg.conf.d/00-keyboard.conf) and a console keymap
# (/etc/vconsole.conf). They describe ONE piece of hardware. When the default became de,ara
# because the owner's keyboard is German, `xkbForLang` was updated and `keymapForLang` was
# left behind returning a literal "us" — so every install since wrote a German desktop and a
# US text console. That console is exactly where you land when the desktop will not start,
# and a 'y' that types 'z' is least affordable exactly there.
#
# So this gate asserts the RELATIONSHIP — the console keymap is derived from the layout — and
# not a literal "de", which is the constant-goes-stale trap that produced the bug in the
# first place. Comments are stripped (style="slash") because the prose right above names both
# "us" and "de", and a gate that matches its own comment passes forever.
installer_qml = code(read("system_files/usr/share/moos/apps/installer/main.qml"), style="slash")
keymap_fn = re.search(r"function\s+keymapForLang\s*\(\s*\)\s*\{([^}]*)\}", installer_qml)
require(keymap_fn,
        "the installer must define keymapForLang() — /etc/vconsole.conf's console keymap comes "
        "from it, and without it the console falls back to us on German hardware")
require("xkbForLang" in keymap_fn.group(1),
        "keymapForLang() must derive the console keymap from xkbForLang() — naming the keyboard "
        "twice is what let the console keep typing 'us' after the layout became 'de,ara'")

# ── The boot theme is a SCRIPT theme; gate what the plugin LOADS, not just draws ─
# The splash was once dead for weeks with every gate green: they asserted the theme
# was installed, selected, and its PNGs decoded — all true while the screen was a
# grey text fallback, because the plugin ABORTED loading an asset nothing checked.
# The theme is now a native Script theme (moos.script moves logo/ring/head/glow),
# but the same failure mode exists: a script whose ScriptFile — or any sprite it
# loads — is missing falls straight back to the text splash. So gate the script and
# its sprites in the repo tree, in the config, in the script's own load calls, and
# in build.sh's fail-closed check.
theme_dir = ROOT / "system_files/usr/share/plymouth/themes/moos"
build_sh = code(read("build_files/build.sh"))
require("plymouth-plugin-script" in build_sh,
        "build.sh must install plymouth-plugin-script — the moos boot theme is a Script theme")
require("plymouth-set-default-theme moos" in build_sh,
        "build.sh must select the moos boot theme")
require("for _f in moos.script logo.png ring.png head.png glow.png" in build_sh,
        "build.sh must PROVE the script + its four sprites landed — a missing ScriptFile or "
        "sprite silently drops the boot to the text splash, with every other gate green")
for _asset in ("moos.script", "logo.png", "ring.png", "head.png", "glow.png"):
    require((theme_dir / _asset).is_file(),
            f"the moos Script theme must ship {_asset} — the splash aborts to text without it")
_moos_cfg = (theme_dir / "moos.plymouth").read_text(encoding="utf-8")
require("ModuleName=script" in _moos_cfg,
        "moos.plymouth must select the script module")
require("ScriptFile=/usr/share/plymouth/themes/moos/moos.script" in _moos_cfg,
        "moos.plymouth must point ScriptFile at moos.script")
_moos_script = (theme_dir / "moos.script").read_text(encoding="utf-8")
for _spr in ('Image("logo.png")', 'Image("ring.png")', 'Image("head.png")', 'Image("glow.png")'):
    require(_spr in _moos_script,
            f"moos.script must load {_spr} — a typo'd or missing load aborts the whole theme")
require("Plymouth.SetRefreshFunction" in _moos_script,
        "moos.script must drive the reveal + loading orbit from a refresh function")

# ── plymouth.use-simpledrm must stay opt-out-able ───────────────────────────
# The karg was proven in a VM, promoted to every machine, and on the owner's NVIDIA box it
# did the opposite of its promise: nvidia is force_drivers'd into the initramfs and owns the
# display two seconds before plymouth-start runs, so Plymouth drew on a simpledrm device
# that no longer existed and the boot was black — no emblem, no splash, nothing saying MoOS.
# Every gate stayed green throughout, because they all check that the THEME is configured,
# which it was. The theme was never broken; the surface it draws on was.
#
# bootc kargs.d can only ADD a karg, so the nvidia edition opts out by build.sh deleting the
# file that carries it. That only works while the karg lives ALONE in its own file: fold it
# back into the shared one and the rm removes nothing, the karg returns for everyone, and
# the NVIDIA splash dies again with a green build. So gate the separation itself.
kargs_dir = ROOT / "system_files/usr/lib/bootc/kargs.d"
shared_kargs = code(read("system_files/usr/lib/bootc/kargs.d/10-moos-boot-splash.toml"))
require("plymouth.use-simpledrm" not in shared_kargs,
        "plymouth.use-simpledrm must NOT be in the shared kargs file — the nvidia edition "
        "opts out by deleting its file, and bootc kargs.d cannot subtract a karg. In the "
        "shared file it reaches NVIDIA and blacks out the boot splash")
optout = kargs_dir / "20-moos-simpledrm.toml"
if not optout.is_file():
    # Guarded, not chained: require() collects and keeps going, so reading a missing file
    # below would raise FileNotFoundError and the run would die on a traceback instead of
    # printing which gate failed and why. A gate that crashes teaches nothing.
    require(False,
            "20-moos-simpledrm.toml must exist — it is the only file build.sh can delete to "
            "keep plymouth.use-simpledrm off the NVIDIA edition, and bootc kargs.d cannot "
            "subtract a karg any other way")
else:
    require("plymouth.use-simpledrm" in code(optout.read_text(encoding="utf-8")),
            "20-moos-simpledrm.toml must actually carry plymouth.use-simpledrm, or the generic "
            "edition loses the karg that took its boot from 8 min to 90 s")
require("rm -f /usr/lib/bootc/kargs.d/20-moos-simpledrm.toml" in code(read("build_files/build.sh")),
        "build.sh must delete 20-moos-simpledrm.toml for the nvidia edition — without it the "
        "karg ships to NVIDIA and there is no boot splash at all")

# ── An I/O scheduler is a property of a DISK, not of a partition ─────────────
# A udev KERNEL glob does not stop at the whole disk: the trailing * in `nvme[0-9]*n[0-9]*`
# also matches `nvme0n1p1`. Only a disk has queue/, so the NVMe rule tried to set a scheduler
# on every partition and logged "Could not chase sysfs attribute .../nvme0n1p1/queue/scheduler"
# 28 times per boot — while setting the disk itself correctly, which is why nobody noticed.
# The SATA rules were quiet only by luck: their ATTR{queue/rotational} is a MATCH that a
# partition also fails, so they failed silently rather than loudly.
#
# Gate the discriminator, not the log line: every scheduler assignment must be constrained to
# DEVTYPE=disk. Checking for absence of the error message would need a boot to observe.
sched_rules = read("system_files/usr/lib/udev/rules.d/60-moos-ioschedulers.rules")
sched_lines = [l for l in code(sched_rules).splitlines() if "queue/scheduler" in l]
require(sched_lines, "60-moos-ioschedulers.rules must actually set queue/scheduler")
for line in sched_lines:
    require('ENV{DEVTYPE}=="disk"' in line,
            "every queue/scheduler rule must be constrained to ENV{DEVTYPE}==\"disk\" — a KERNEL "
            "glob swallows partitions too, and a partition has no scheduler to set: "
            f"{line.strip()[:80]}")

# ── The wizard's page count must be the wizard's real pages ──────────────────
# stepCount drives the progress dots and bounds goNext(); the StackLayout's children ARE the
# pages. They are two hand-kept numbers describing one thing, so they drift: get it wrong and
# the dots count pages that do not exist, or Next stops one short of the end and the install
# can never be reached. Nothing else in the app would say a word. So assert the RELATIONSHIP
# by counting the StackLayout's real children — this is the check that makes inserting a page
# safe, which is how the time-zone step was added.
def stacklayout_children(text: str) -> int:
    start = text.index("StackLayout {")
    depth, kids = 0, 0
    for line in text[start:].splitlines():
        if depth == 1 and re.match(r"^\s*[A-Za-z_][\w.]*\s*\{", line):
            kids += 1
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            break
    return kids

declared = re.search(r"readonly property int stepCount:\s*(\d+)", installer_qml)
require(declared, "the installer must declare stepCount — the progress dots read it")
actual = stacklayout_children(installer_qml)
require(int(declared.group(1)) == actual,
        f"stepCount says {declared.group(1)} but the StackLayout has {actual} pages — the dots "
        "and the wizard disagree, and Next stops on the wrong page")

# Named indices, not bare numbers. A page inserted in the middle used to mean renumbering
# every 5/6/7 scattered through ~1900 lines by hand; one missed and the installer jumps to the
# wrong page at the point of no return. The names make the pages movable.
stray = re.search(r"win\.step\s*(?:===?|=)\s*\d", installer_qml)
require(not stray,
        "no bare step numbers: use the named stepWelcome/…/stepSuccess indices, or the next "
        f"inserted page silently sends the wizard to the wrong screen (found: {stray.group(0) if stray else ''})")

# ── The install must apply the timezone the HUMAN picked ─────────────────────
# tzForLang() is a guess derived from the UI language, and language is not location: this
# project's owner is an Arabic speaker in Germany, so the Arabic branch handed him Riyadh (2h
# wrong) and the English branch handed him UTC (a placeholder nobody lives in). The desktop
# clock — the most-looked-at thing on the screen — was simply wrong, and the install never
# asked. The zone step exists so the human corrects the guess; if the recipe silently sends
# the guess anyway, the step is decoration.
recipe = re.search(r"timezone:\s*(.+)", installer_qml)
require(recipe, "the install recipe must carry a timezone — moos-firstboot writes /etc/localtime from it")
# \b, not `in`. `"win.tz" in "win.tzForLang()"` is True — the substring test was satisfied by
# the exact line it exists to reject, and passed green while the recipe shipped the guess.
# Caught only by breaking it on purpose. The boundary stops at `win.tz` and refuses the prefix.
require(re.search(r"win\.tz\b", recipe.group(1)),
        "the recipe's timezone must be the zone the user chose (win.tz), not tzForLang() alone — "
        "otherwise the picker changes nothing and the clock stays wrong")

# ── The third agent is the one that needs nobody's cloud ─────────────────────
# Codex and Claude Code are both somebody else's subscription. OpenCode is provider-agnostic,
# so on a machine that ships its own brain it can be pointed at THAT — a coding agent that
# works with no account, no login and no internet. Verified end-to-end on the hardware:
# `moai-do install-opencode` installed it, wrote the provider config, and with the brain
# STOPPED, `opencode run` woke it through moai-gateway and got an answer back.
#
# The install is gated as a whole because the npm package alone is not the feature: an agent
# that lands with no provider configured opens, asks for a model the user does not have, and
# is indistinguishable from broken. If the config write is dropped, the button still "works"
# and the user still cannot code.
control_code = code(read("system_files/usr/bin/moai-control"))
require('"opencode": command_exists("opencode")' in control_code,
        "moai-control must report whether OpenCode is installed, or Mo AI's Developer panel "
        "cannot tell Install from Run")
do_code = code(read("system_files/usr/bin/moai-do"))
require("do_install_opencode" in do_code and "opencode-ai" in do_code,
        "moai-do must be able to install OpenCode — the only coding agent on MoOS that needs "
        "no account")
require("opencode.json" in do_code and "127.0.0.1:8080/v1" in do_code,
        "moai-do install-opencode must WRITE the provider config pointing at moai-gateway — "
        "an agent installed with no provider is indistinguishable from a broken one")
require("agentState.opencode" in moai_qml,
        "Mo AI's Developer panel must know about OpenCode — an agent the system can install "
        "and the UI cannot show is an agent nobody finds")
code_runner = code(read("system_files/usr/bin/moai-code"))
require("claude|codex|opencode" in code_runner,
        "moai-code must accept opencode as an agent, or moos://dev/opencode opens nothing")

# ── An Arabic assistant that speaks English must not mangle it ───────────────
# Qt gives a whole Text ONE base direction, taken from its first strong character, and in
# Markdown a single "\n" is a soft wrap rather than a paragraph break. So Mo AI's greeting —
# Arabic first line, English second — became one right-to-left paragraph, and the English
# sentence was rendered with its full stop thrown to the front: the first thing a new MoOS
# user read was ".the system, install any app, clean things up, and run Mo PC Remote".
# Fixed by giving each language its own paragraph with its own directional mark, and by
# stamping every model reply per paragraph (bidiFix) — the model mixes the two languages in
# one answer constantly, and that text cannot be hand-written.
# ── The desk dashboard: weather, a clock that turns, and nothing in the way ──
#
# This gated org.moos.ui2.dashboard the desktop WIDGET, which no longer ships: as a
# Plasma applet it always drew ON TOP of the Folder View icons, and three shipped
# fixes (x=80→260→360, icons right-aligned, live-ISO skip) each only moved the
# collision with the "Install MoOS" icon. The bento now renders INSIDE the
# wallpaper (org.moos.ui2.wallpaper: image + DashboardBento as one layer BELOW the
# icons), so it can never cover anything — and the live ISO gets it back.
#
# The protections themselves do not change, because the bugs they remember do not
# care which layer the bento paints on.
SCENE = "system_files/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper"
dashboard = read(f"{SCENE}/contents/ui/DashboardBento.qml")
# style="slash": QML comments, and this gate MUST see past them. The checks below name the thing
# they forbid (ipapi.co, MouseArea) in the very comment that explains why — strip the prose or the
# gate passes on a broken file, which is the comment trap AGENTS.md warns about.
dashboard_code = code(dashboard, "slash")
require("ipwho.is" in dashboard_code and "api.open-meteo.com" in dashboard_code,
        "the desk dashboard must read the weather from ipwho.is + Open-Meteo — both key-less, "
        "and both verified against the User-Agent Qt actually sends")
require("ipapi.co" not in dashboard_code,
        "ipapi.co must not be the dashboard's geocoder: it answers curl but serves a Cloudflare "
        "interstitial to Qt's browser-shaped User-Agent, so the widget got HTML instead of "
        "JSON and the weather silently never appeared")
dashboard_ui = "".join(
    code(read(f"{SCENE}/contents/ui/{f}"), "slash")
    for f in ("main.qml", "DashboardBento.qml", "ClockCard.qml", "WeatherCard.qml",
              "SystemCard.qml", "GlassCard.qml"))
require("MouseArea" not in dashboard_ui,
        "the desk dashboard must not contain a MouseArea: it lives in the wallpaper, and "
        "anything that accepts clicks eats the desktop's own right-click menu and rubber-band "
        "selection inside its rectangle, with no way for the user to tell why")
# The wallpaper wrapper is the layer contract itself: the scene must BE a
# wallpaper (below icons), embed the bento, and expose the Image config key the
# theme scripts write per half. Break any of these and the widget-over-icons
# collision family returns.
scene_main = code(read(f"{SCENE}/contents/ui/main.qml"), "slash")
require("WallpaperItem" in scene_main,
        "the scene's root must be a WallpaperItem — anything else does not render below the icons")
require("DashboardBento" in scene_main,
        "the scene wallpaper no longer embeds the dashboard bento")
require('"Plasma/Wallpaper"' in read(f"{SCENE}/metadata.json"),
        "org.moos.ui2.wallpaper must be a Plasma/Wallpaper package")
require('name="Image"' in read(f"{SCENE}/contents/config/main.xml"),
        "the scene wallpaper lost its Image config entry — moos-theme cannot set the half")
require("import org.kde.plasma.plasmoid" not in code(dashboard, "slash"),
        "DashboardBento must stay plain QtQuick/Kirigami — the build's smoke harness "
        "loads it directly, which the Plasmoid API would break")
require(not (ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.ui2.dashboard").exists(),
        "the retired dashboard APPLET package is back — as a desktop widget it draws over "
        "the icons; the bento belongs inside org.moos.ui2.wallpaper")
shell_defaults = read("system_files/usr/share/plasma/shells/org.kde.plasma.desktop/contents/defaults")
require("Wallpaper=org.moos.ui2.wallpaper" in code(shell_defaults, "hash"),
        "the desktop shell defaults must select org.moos.ui2.wallpaper, or a fresh "
        "desktop boots without the MoOS scene")



# ── Self-referential grouped-property bindings, and why this gate is STATIC ───
#
# `sourceSize.height: sourceSize.width` reads as two properties. It is one: sourceSize is a
# single QSize, so that line makes a component of it depend on a component of itself. Qt calls
# it "Binding loop detected for property sourceSize.height" and resolves it the only way it
# can — by DROPPING the binding. The property then holds a stale value forever, silently.
#
# UI2's dashboard shipped exactly that line, and the weather art has been decoding at the wrong
# size ever since, with plasmashell logging the loop on every load and every condition change.
#
# The build ALREADY runs the dashboard under plasmawindowed and ALREADY greps its log for
# "binding loop" (build_files/build.sh). It did not catch this, and it never could: under
# QT_QPA_PLATFORM=offscreen the card is never laid out to a real width, so the binding is
# evaluated once, never re-enters, and Qt has no loop to detect. Reproduced deliberately — the
# broken file exits 124 with a clean log and the build calls it a pass. A runtime gate that
# cannot give the thing a geometry cannot see a geometry-driven loop.
#
# So this one is static, and it is the gate that actually bites. Any binding whose left side is
# `<group>.<a>` and whose right side reads `<group>.<b>` on the same object is a loop by
# construction — for sourceSize, font, anchors, or anything else Qt groups.
#
# The `(?<![\w.])` is load-bearing: `sourceSize.width: other.sourceSize.width` is a perfectly
# ordinary binding to a DIFFERENT object, and must not be flagged.
#
# WHICH groups: only QML VALUE TYPES. `sourceSize` is a single QSize, so writing .height
# notifies the whole property and the .width binding re-enters — a loop. `Layout` and `anchors`
# look identical in source but are an attached object and a grouped object: their components
# are independent properties that do not notify each other, and binding one to another is
# ordinary QML (`Layout.preferredHeight: Layout.preferredWidth` just means "square").
#
# That distinction is not a guess. The running session logged loops for exactly two properties,
# `sourceSize.height` and `icon.height` — both value types — while WeatherCard.qml:41 and
# SystemCard.qml:79 bound Layout.preferredHeight to Layout.preferredWidth in the same dashboard,
# on the same frames, and Qt never once complained. A gate that flagged those would be crying
# wolf on correct code, and the next agent would rightly delete it.
VALUE_TYPE_GROUPS = ("sourceSize", "font", "icon", "palette")
SELF_REFERENTIAL_GROUP = re.compile(
    rf"^\s*({'|'.join(VALUE_TYPE_GROUPS)})\.([A-Za-z_]\w*)\s*:\s*(?P<rhs>.*)$"
)

# Scope: the QML MoOS actually writes. The SDDM theme vendors a copy of Qt's own
# VirtualKeyboard styles, which contain this pattern upstream — that is not our code, it is
# not ours to fix, and SDDM is not even installed on Kinoite 44. Gating it would only teach
# the next agent to switch the gate off.
moos_qml_roots = (
    "system_files/usr/share/moos/apps",
    "system_files/usr/share/plasma/plasmoids",
    "system_files/usr/share/plasma/look-and-feel",
)
shipped_qml = sorted(
    qml
    for relative in moos_qml_roots
    for qml in (ROOT / relative).rglob("*.qml")
)
require(shipped_qml != [],
        "no MoOS QML was found to scan — this gate would pass vacuously over an empty list")
for qml_file in shipped_qml:
    for number, line in enumerate(
        code(qml_file.read_text(encoding="utf-8"), "slash").splitlines(), start=1
    ):
        # `anchors.left: parent.left; anchors.right: parent.right` is TWO bindings sharing a
        # line, and neither is a loop. Judge each binding on its own or the gate cries wolf on
        # the most ordinary line in QML.
        for statement in line.split(";"):
            match = SELF_REFERENTIAL_GROUP.match(statement)
            if match is None:
                continue
            group = match.group(1)
            rhs = match.group("rhs")
            if re.search(rf"(?<![\w.]){re.escape(group)}\.\w+", rhs) is None:
                continue
            require(False,
                    f"{qml_file.relative_to(ROOT)}:{number} binds a component of `{group}` to "
                    f"another component of the same `{group}` ({statement.strip()}). That is "
                    f"one grouped property depending on itself: Qt detects a binding loop and "
                    f"DROPS the binding, so the value is silently stale. Compute it once and "
                    f"assign the whole group (e.g. `sourceSize: Qt.size(px, px)`)")

require("function bidiFix" in moai_qml and "root.bidiFix(msg.text)" in moai_qml,
        "Mo AI must pin each paragraph's text direction to its own language (bidiFix, applied "
        "to every chat bubble) — one Arabic word otherwise drags every English line RTL and "
        "throws its punctuation to the wrong end")
require("‎" in moai_qml and "‏" in moai_qml,
        "Mo AI's bilingual messages must carry explicit LRM/RLM marks — without them the "
        "paragraph's direction is decided by whichever character happens to come first")

# ── The brain must say WHY it did not start ──────────────────────────────────
# It had exactly one failure message — "the first start downloads the model (~2.5 GB) and
# keeps going in the background" — and it printed that when the disk was full, when there
# was no network to download from, and when llama-server aborted because the GPU had no
# memory left (which happened on this machine). The user waits for a download that is not
# running. The gateway now refuses a start that cannot work (disk, network) and, when the
# unit is DOWN, reads the service's own log and names the cause.
# ── Nothing expensive between the user and their desktop ─────────────────────
# Fedora Atomic's appstream refresh is WantedBy=multi-user.target and sat in this machine's
# critical chain at +3.525 s — a third of MoOS's userspace boot — rebuilding an app-store
# index nobody had asked for yet. And flatpak-system-update, the single most expensive unit
# on a MoOS boot (1min 3.885s of CPU), fired two minutes into the session at normal priority,
# competing with the desktop for CPU and disk exactly when the user starts working.
build_sh = code(read("build_files/build.sh"))
require("systemctl disable fedora-atomic-desktop-appstream-cache-refresh.service" in build_sh
        and "systemctl enable moos-appstream-refresh.timer" in build_sh,
        "build.sh must move the appstream refresh out of the boot path and onto MoOS's timer "
        "— it costs 3.5 s of every boot for a catalogue nothing has opened yet")
flatpak_idle = read("system_files/usr/lib/systemd/system/flatpak-system-update.service.d/moos-idle.conf")
require("CPUSchedulingPolicy=idle" in flatpak_idle and "IOSchedulingClass=idle" in flatpak_idle,
        "flatpak-system-update must run at idle CPU and I/O priority — at normal priority it "
        "is what 'the system feels slow right after login' is actually made of")

# ── The live session must reach the network on its own ───────────────────────
# On a slow first boot (a cold WHPX guest, software rendering, a machine thrashing through
# its first userspace) dbus-broker — the system message bus, Type=notify-reload with NO
# TimeoutStartSec of its own — did not signal READY inside the 90s default and was killed
# with result 'timeout'. EVERY unit that needs the bus then failed in the same instant with
# "Dependency failed": NetworkManager, NetworkManager-wait-online, tuned, tuned-ppd. The
# live session came up with NO network, so the Welcome wizard could not install anything,
# until NM was started by hand — sixteen minutes late. Seen on the v21 ISO, 2026-07-15
# (vm-test/v21-26-root.png, vm-test/v21-24-nmlog.png).
#
# Two drop-ins, same philosophy as plasma's moos-stop-timeout.conf: a generous timeout
# costs nothing on fast hardware. Comments are stripped with code() so neither gate can be
# satisfied by the prose that names the very directive it checks for.
#
#   1. dbus-broker gets a far larger start window — the ROOT fix, since a bus that does not
#      time out never starts the cascade.
dbus_timeout = code(read(
    "system_files/usr/lib/systemd/system/dbus-broker.service.d/moos-start-timeout.conf"))
dbus_start = re.search(r"TimeoutStartSec\s*=\s*(\d+)\s*(min|s|sec)?", dbus_timeout)
require(dbus_start is not None,
        "dbus-broker must get a TimeoutStartSec drop-in — its stock unit sets none, so it "
        "inherits the 90s default the slow first boot blew past, killing the system bus and "
        "every unit that needs it (NetworkManager, tuned, ...)")
if dbus_start:
    dbus_seconds = int(dbus_start.group(1)) * (60 if dbus_start.group(2) == "min" else 1)
    require(dbus_seconds >= 120,
            f"dbus-broker's TimeoutStartSec must be generously above the 90s default (got "
            f"{dbus_seconds}s), or a slow WHPX first boot trips it again and the network "
            f"cascade returns")

#   2. NetworkManager keeps retrying its OWN failures. Stock NM already sets Restart=on-failure
#      (which does NOT fire on the 'dependency' failure that struck here — systemd restarts a
#      service whose own process failed, never one cancelled by a failed dependency); the
#      load-bearing addition is StartLimitIntervalSec=0, so a run of quick restarts on a rocky
#      boot cannot trip the default 5-in-10s burst and latch NM off for good.
nm_restart = code(read(
    "system_files/usr/lib/systemd/system/NetworkManager.service.d/moos-restart.conf"))
require("Restart=on-failure" in nm_restart,
        "NetworkManager's drop-in must declare Restart=on-failure (explicit even though stock "
        "sets it), or the intent to self-heal a failed NM goes undocumented")
require(re.search(r"RestartSec\s*=\s*\d", nm_restart) is not None,
        "NetworkManager's drop-in must set a RestartSec so its retries are paced")
require("StartLimitIntervalSec=0" in nm_restart,
        "NetworkManager's drop-in must disable the start rate limiter (StartLimitIntervalSec=0) "
        "— without it a handful of quick own-failure restarts on a bad boot trip the default "
        "5-in-10s burst and latch NM off for good, re-creating 'no network until I intervene'")

gateway = code(read("system_files/usr/bin/moai-gateway"))
require("def preflight_local" in gateway and "disk_free" in gateway and "have_network" in gateway,
        "moai-gateway must pre-flight a local start (disk space, network) instead of failing "
        "deep inside RamaLama and blaming a download that never began")
require("def local_failure_reason" in gateway and "FAILURE_SIGNS" in gateway,
        "moai-gateway must read the unit's own log when the brain is down and name the cause "
        "(GPU memory, disk, network) — one generic 'still downloading' message for every "
        "failure is how a dead brain looks like a slow one")

for qml_path in sorted((ROOT / "system_files/usr/share/moos/apps").glob("*/main.qml")):
    qml_text = qml_path.read_text(encoding="utf-8")
    for url in sorted(set(re.findall(r'moos://([a-z0-9/._-]+)', qml_text))):
        # A URL the app builds at runtime ("moos://do/" + action) shows up here as
        # the bare prefix "do/". It is not a route; the values substituted into it
        # are checked below, against the allowlist the app actually draws from.
        if url.endswith("/"):
            continue
        require(route_is_covered(url, declared_routes),
                f"{qml_path.parent.name} opens moos://{url}, "
                f"which moos-open has no case for — that button does nothing")

# The Run chips are built from the actions Mo AI parses out of a model reply, so
# their URLs never appear as literals. Check the allowlist that feeds them.
runs = re.search(r"const re = /moai-do\\s\+\(([a-z|-]+)\)", moai_qml)
require(runs is not None, "Mo AI must match suggested actions against a fixed allowlist")
if runs:
    for action in runs.group(1).split("|"):
        require(route_is_covered(f"do/{action}", declared_routes),
                f"Mo AI can offer to run `moai-do {action}`, "
                f"but moos-open has no do/{action} route")

# ── The cloud brain ─────────────────────────────────────────────────────────
gateway = read("system_files/usr/bin/moai-gateway")
control_py = read("system_files/usr/bin/moai-control")

# Python's urllib announces itself as "Python-urllib/3.x", and Cloudflare — which
# fronts a large share of AI providers — answers that with 403 "error code: 1010"
# before the request reaches the API at all. The gateway shipped with the default
# UA, so the cloud brain was fully configurable and completely dead: it could not
# reach ANY Cloudflare-fronted provider. Both processes that call out must identify
# themselves.
for name, text in (("moai-gateway", gateway), ("moai-control", control_py)):
    require('add_header("User-Agent"' in text,
            f"{name} must send a User-Agent — the urllib default is 403'd by Cloudflare")
    require("MoOS-MoAI/" in text,
            f"{name} must identify itself as MoOS-MoAI")

# Claude's native API is not OpenAI's. If we offer it, we must actually translate.
require('"/messages"' in gateway and "anthropic-version" in gateway
        and "x-api-key" in gateway,
        "the Anthropic wire must hit /v1/messages with x-api-key + anthropic-version")
require("content_block_delta" in gateway,
        "the Anthropic wire must translate content_block_delta into OpenAI deltas")
require("max_tokens" in gateway,
        "Anthropic requires max_tokens; the gateway must supply one")

# Presets describe providers. A preset must never carry a credential.
require('"key"' not in control_py.split("PROVIDERS = [")[1].split("]")[0],
        "a provider preset must never contain an API key")
require("secret-tool" in gateway,
        "the gateway must read the key from Secret Service, not from config.json")

# …and the other half of the same contract: every do/* route that moos-open hands
# to moai-do must be an action moai-do actually implements. (Not every do/* route
# goes there — do/smart-setup and do/setup-gaming are dispatched to moos-setup by
# moos-open itself — so assert against the arm that really calls moai-do, rather
# than assuming.)
moai_do = read("system_files/usr/bin/moai-do")
moai_do_arm = re.search(
    r"^\s{4}((?:do/[a-z-]+\|)*do/[a-z-]+)\)\s*\n\s*term moai-do",
    router, re.MULTILINE)
require(moai_do_arm is not None,
        "moos-open must dispatch its moai-do actions from a single case arm")
if moai_do_arm:
    for label in moai_do_arm.group(1).split("|"):
        action = label.split("/", 1)[1]
        require(f"{action})" in moai_do,
                f"moos-open routes {label} to moai-do, which does not implement it")

# Install must also RUN. "Install a camera" is only finished when the camera is on
# screen, so do_install opens the app it just installed. Gate the CALL, not just the
# def: launch_app necessarily appears once in its own `launch_app()` definition, so a
# lone match would stay green even if the call inside do_install were deleted — the
# same dead-feature-behind-a-green-gate shape this file exists to catch.
moai_do_code = code(moai_do)
require("launch_app()" in moai_do_code and moai_do_code.count("launch_app") >= 2,
        "moai-do must DEFINE and CALL launch_app — a successful install must open the "
        "app it installed, or Mo AI can download a program and never run it")

# Screen capture. The original implementation spawned `spectacle` once per frame (~630ms,
# i.e. ~1 fps) and shelled out to `kscreen-doctor` to guess the desktop geometry — the two
# things that made remote control feel broken. Capture is now a PipeWire stream from the
# portal, which also *tells* us the geometry, so both of those probes are gone. Guard the
# new invariants rather than the old workarounds.
capture = read("moremote/agent-linux/ScreenCapture.cs")
require("kscreen-doctor" not in capture,
        "Screen geometry must come from the portal, not an external kscreen probe")
require("PortalBridge" in capture,
        "Capture must be backed by the PipeWire portal stream")
require("public ScreenCapture(PortalBridge portal)" in capture,
        "Capture must not do blocking work in its constructor")
require("CaptureFallback" in capture,
        "spectacle must remain a fallback, never the primary capture path")

# The portal helper is what actually produces frames and injects input.
portal = read("moremote/agent-linux/mo-remote-portal.py")
require("pipewiresrc" in portal, "Remote capture must run on PipeWire")
require("NotifyPointerMotionAbsolute" in portal,
        "The pointer must be positioned absolutely, so a tap lands where it was tapped")
require("CURSOR_HIDDEN" in portal,
        "The stream must be able to hide the cursor — drawing it re-encodes a full frame per move")

# Arabic from a phone is two separate contracts. KWin/XKB expects the legacy 0x05xx Arabic
# keysyms, while phone keyboards commit words through composition events. Losing either half
# makes the D-Bus call look successful while letters vanish or arrive duplicated.
text_keysym = read("moremote/agent-linux/TextKeysym.cs")
input_injector = read("moremote/agent-linux/InputInjector.cs")
remote_screen = read("moremote/controller/src/ui/RemoteScreen.tsx")
require("0x05c1" in text_keysym and "0x05e0" in text_keysym
        and "TextKeysym.ForCodepoint" in input_injector,
        "Mo PC Remote must map core Arabic Unicode to XKB's legacy Arabic keysyms")
require("onCompositionStart" in remote_screen and "onCompositionEnd" in remote_screen
        and "composingRef.current" in remote_screen,
        "the phone keyboard must send committed Arabic/IME text once, not stream composition edits")

# build.sh installs into the image by name; a stale filename here fails the image build.
build = read("build_files/build.sh")
require("mo-remote-portal.py" in build, "build.sh must ship the PipeWire portal helper")
require("mo-remote-input-portal.py" not in build,
        "build.sh still references the removed input-only helper")
require("pipewire-gstreamer" in build,
        "build.sh must guarantee the capture pipeline's GStreamer/PipeWire packages")

# JPEG has no temporal compression: every frame is a whole picture, so merely LOOKING at a desktop
# costs as much as scrubbing through it. Measured on real hardware at 1080p — 79 Mbit/s against
# H.264's 4.3. Nobody notices that on a home LAN and nobody survives it on mobile data, which is
# the entire reason this feature exists.
#
# The hardware encoders cannot be relied on. NVENC opens a session against the GPU and refuses when
# VRAM is gone — measured here, with a local LLM holding 6 of 8 GB, nvh264enc failed to open at
# 7748/8192 MiB and worked again at 7625. So a software encoder is not a nicety, it is the floor
# under H.264 itself, and the helper must be able to walk DOWN to it rather than die on the way.
portal = read("moremote/agent-linux/mo-remote-portal.py")
require("gstreamer1-plugin-openh264" in build,
        "the image must ship a software H.264 encoder: NVENC is not guaranteed to open (VRAM), and "
        "without a fallback the stream drops to JPEG — 79 Mbit/s, unusable on mobile data")
require("h264parse" in portal and "byte-stream" in portal,
        "the H.264 stream must be Annex-B with repeated SPS/PPS, or a phone that joins mid-stream "
        "(the only way anyone joins a live stream) has nothing to start decoding from")
require("_h264_blacklist" in portal,
        "an encoder that exists can still refuse to start; the helper must fall to the next one "
        "instead of leaving the user with no desktop")

session = read("moremote/agent/Web/StreamSession.cs")
require("_encoded" in session and "TryDequeue" in session,
        "H.264 access units must be queued and drained in order — the JPEG path keeps only the "
        "newest frame, and a hole in an H.264 stream corrupts every frame until the next IDR")

# An idle remote must cost NOTHING. This is the bug that made the machine feel broken.
#
# The helper used to build its pipeline at import and hold it PLAYING forever. A live PipeWire
# ScreenCast stream is not passive: it makes the COMPOSITOR copy out every damaged frame. Measured
# on the maintainer's machine on 2026-07-14 with **zero clients connected** — kwin_wayland at 55%
# of a core, the helper at 32%, permanently, from the moment he logged in. He reported it as "the
# reboot hangs". It also kept the GPU warm on an 8 GB card that a local LLM already holds ~6 GB of,
# which is the same VRAM ceiling kwin SIGSEGVs against.
#
# So: no viewer, no pipeline. Gated on the code with comments stripped, because every claim below
# is also written in prose right next to the thing it guards.
portal_code = code(portal)
require('"streaming": False' in portal_code,
        "the portal helper must come up IDLE — a pipeline built at import streams to nobody and "
        "makes the compositor copy every frame for a viewer who is not there")
require(not re.search(r"^rebuild\(\)\s*$", portal_code, re.M),
        "the helper must not build a pipeline at module level: nobody has connected yet")
require('if not state["streaming"]:' in portal_code,
        "rebuild() must refuse to build with no viewer, or a stray quality/scale push resurrects "
        "the encoder on an idle machine")

bridge_code = code(read("moremote/agent-linux/PortalBridge.cs"), "slash")
require("public void SetStreaming(bool on)" in bridge_code,
        "PortalBridge must be able to tell the helper whether anyone is watching")
require("_streaming" in bridge_code and "Stalled =>" in bridge_code
        and "_ready && _streaming" in bridge_code,
        "an IDLE helper is not a STALLED helper — judging it stalled sends every first frame down "
        "the spectacle fallback, which costs ~700ms a frame")

capture_code = code(capture, "slash")
require("_portal.SetStreaming(!_sessionH264.IsEmpty)" in capture_code,
        "the encoder must run exactly while somebody is watching — no more, and no less")
require("public void SessionArrived(Guid id)" in capture_code,
        "a viewer must be registered when it ARRIVES, not on its first codec vote: a JPEG-only "
        "client never sends one, and it would stream to a viewer nobody counted")

session_code = code(session, "slash")
require("SessionArrived" in session_code and "SessionGone" in session_code,
        "StreamSession owns the viewer's lifetime; both ends of it must reach the capture")
require(session_code.index("ValidateAndTouch") < session_code.index("SessionArrived"),
        "the screen encoder must start AFTER authentication — an unauthenticated socket must not "
        "be able to make this machine start capturing its own screen")

# Remote control that only works inside the house is not remote control.
#
# Mo PC Remote was always reachable from anywhere — Tailscale is a mesh, and NetworkGuard has
# always allowed the tailnet's 100.64.0.0/10. What defeated it was the ADDRESS the panel handed
# the user: it took the default route's source IP, printed http://192.168.x.x:8765, and that
# address stops existing the moment the phone is on mobile data. The panel must offer the
# MagicDNS HTTPS name, which works anywhere on the tailnet AND is a secure context — without
# which the browser will not give Mo PC Remote WebCodecs, the clipboard, or a real PWA install.
panel = read("system_files/usr/bin/mo-pc-remote")
require("tailscale" in panel and "serve" in panel,
        "the Mo PC Remote panel must offer the Tailscale address; a LAN IP over http dies the "
        "moment the phone leaves the house")
require("qrencode" in panel and "qrencode" in build,
        "the panel must render its address as a QR code, and the image must ship qrencode — an "
        "address a user has to retype is an address they get wrong")
require("remote-anywhere" in read("system_files/usr/bin/moai-do"),
        "enabling access from anywhere touches Tailscale's operator bit, which is privileged, "
        "so it must be a moai-do action and not something the panel does behind the user's back")
require('"up","--operator"' in panel and 'BackendState' in panel,
        "the panel's one-click setup must log Tailscale in when a fresh installation is in "
        "NeedsLogin; calling serve alone can never produce a working remote address")
require("subprocess.Popen" in panel and "threading.Thread" in panel,
        "Tailscale login waits for the owner to authenticate; it must run outside GTK's main "
        "thread so the login URL and QR can appear without freezing the panel")
require('re.search(r"https://' in panel and "mo-remote-login-" in panel,
        "the panel must surface Tailscale's authentication URL and QR instead of sending the "
        "owner to a terminal after its setup button fails")

# The phone UI that ships is the COMMITTED build output. MoRemoteLinux.csproj copies
# ../agent/wwwroot/** into the image; nothing in the image build ever runs vite. So editing
# controller/src and not rebuilding ships the OLD interface, silently, with a perfectly green
# build — the same shape as every other bug found tonight, where the source was right and the
# thing that reached the user was stale.
#
# These are canaries: strings that exist in the current source and must therefore exist in the
# bundle. If they do not, wwwroot was not rebuilt.
#     cd moremote/controller && npm ci && npm run build   # then commit agent/wwwroot
bundle = "".join(p.read_text(errors="replace")
                 for p in (ROOT / "moremote/agent/wwwroot/assets").glob("*.js"))
manifest = read("moremote/agent/wwwroot/manifest.webmanifest")
require("No video" in bundle,
        "the shipped phone UI is stale: controller/src has strings the built bundle does not. "
        "Rebuild moremote/controller and commit moremote/agent/wwwroot")
require('"orientation":"landscape"' in manifest.replace(" ", ""),
        "the shipped web app manifest is stale, or no longer asks for landscape — a desktop "
        "fitted into a portrait phone is a stamp between two black bars")

control = read("system_files/usr/bin/moai-control")
gateway = read("system_files/usr/bin/moai-gateway")
require('"cloud_key":' not in control,
        "Mo AI must not persist cloud_key in JSON")
require('c.get("cloud_key")' not in gateway,
        "Mo AI gateway must not read plaintext cloud_key from JSON")
require("secret-tool" in control and "secret-tool" in gateway,
        "Mo AI cloud credentials must use Secret Service")
require('had_legacy_key = "cloud_key" in data' in control and
        "elif had_legacy_key:" in control,
        "Mo AI must remove even an empty legacy cloud_key field")

# ── The curated local starters, and that the picker can explain them ─────────
# A fresh install used to show exactly ONE local model, so the picker answered
# the question "which brains can I have?" with silence (owner, 2026-07-17).
# moai-control must ship at least two curated one-tap-download starters — each
# with a bilingual note and an honest size — and the picker must actually
# render those two fields, or the catalog exists and the user still sees bare
# model tags. Both sides checked, because either alone regresses silently.
_rec = re.search(r"RECOMMENDED_LOCAL\s*=\s*\[(.*?)\]", code(control), re.S)
require(_rec is not None, "moai-control lost its RECOMMENDED_LOCAL starter catalog")
require(len(re.findall(r'"id":', _rec.group(1))) >= 2,
        "the local starter catalog must offer at least two models to download")
require(_rec.group(1).count('"note":') == len(re.findall(r'"id":', _rec.group(1)))
        and _rec.group(1).count('"size_gb":') == len(re.findall(r'"id":', _rec.group(1))),
        "every curated starter needs a bilingual note AND a size_gb — the picker "
        "promises the cost of the tap before anything downloads")
_moai_qml = code(read("system_files/usr/share/moos/apps/moai/main.qml"), style="slash")
require("modelData.note" in _moai_qml and "modelData.size_gb" in _moai_qml,
        "Mo AI's picker must render the starters' note and size_gb — a catalog "
        "the UI never shows is not a catalog")

# ── "one-tap download" must BE one tap ───────────────────────────────────────
#
# The picker labelled every un-pulled starter "تحميل بضغطة | one-tap download"
# from the day the catalog shipped, and the tap only set the route: the first
# chat then came back from moai-gateway with "Pull it first: ramalama pull <x>".
# A terminal instruction, on the desktop whose entire promise is that there is no
# terminal — the label was true about the intent and false about the machine.
# Gate the whole chain, because any one link failing restores the dead end:
#   1. the label's endpoint exists in moai-control and is allowlisted;
#   2. the tap routes through pickOrPull, not pickRoute;
#   3. the pull carries the ollama:// transport.
# (3) is not style. MEASURED 2026-07-17: a bare `ramalama pull qwen3:8b` resolves
# to hf://Qwen/Qwen3-8B-GGUF, which short_model() renders "Qwen/Qwen3-8B-GGUF" —
# matching no id in the catalog — so the gateway reports a fully downloaded brain
# as missing, forever, with no way out from the UI.
require('self.path.startswith("/pull")' in code(control)
        and "def start_pull" in code(control),
        "moai-control must serve /pull — Mo AI's picker promises a one-tap "
        "download and needs a machine behind the label")
_start_pull = re.search(r"def start_pull\(.*?\n(?=\n\S|\Z)", code(control), re.S)
require(_start_pull is not None
        and "RECOMMENDED_LOCAL" in _start_pull.group(0)
        and "unknown model" in _start_pull.group(0),
        "start_pull must accept ONLY ids from RECOMMENDED_LOCAL — an arbitrary "
        "model string from the UI is an arbitrary registry fetch")
require(re.search(r'"ramalama",\s*"pull",\s*"ollama://"\s*\+', code(control)) is not None,
        "the starter pull must prefix ollama:// — a bare tag resolves to a "
        "HuggingFace name that short_model() can never match back to the "
        "catalog, so the brain downloads and still reports as missing")
require("pickOrPull" in _moai_qml,
        "the picker's tap must go through pickOrPull — pickRoute alone only sets "
        "a route to a brain this machine does not have")
require(re.search(r"onClicked:\s*root\.pickRoute\(locRow", _moai_qml) is None,
        "the local starter row must not tap straight to pickRoute — that is the "
        "dead end that sent users to a terminal")

# ── One door, two brains, chosen per request ────────────────────────────────
#
# Mo AI's local brain and its cloud proxy both used to listen on 8080. Only one of
# them could run, so the choice of brain was a GLOBAL setting, and changing it meant
# `systemctl disable --now` one unit and `enable --now` the other. There was no way
# to ask a stronger model one question without rebuilding the whole plumbing first.
#
# Now moai-gateway owns 8080 alone, is always on, and routes each REQUEST by its
# `model` field; moai.service serves the local brain on 8081 and is started on
# demand. Everything below guards a specific way that could silently come apart —
# and every one of them is checked against the CODE, never the comment that
# explains it.
gateway_code = code(gateway)
control_code = code(control)
local_unit = read("system_files/usr/lib/systemd/user/moai.service")
gateway_unit = read("system_files/usr/lib/systemd/user/moai-gateway.service")
build_code = code(read("build_files/build.sh"))

# ── MoOS must introduce itself as MoOS ────────────────────────────────────────
#
# os-release VERSION is inherited from the base, and the base is Kinoite — so an image that had
# renamed NAME, PRETTY_NAME, the GRUB title and the boot splash still said
# `44.20260714.0 (Kinoite)`. That field is what the ANACONDA INSTALLER prints, which means the
# first screen of a fresh MoOS install named a different distribution. Found while auditing the
# ISO the owner asked to install on a second machine.
#
# ID_LIKE="fedora" is deliberately NOT policed here: it is a machine-readable compatibility hint
# that dnf, Flatpak and third-party installers read, not branding. Removing it breaks tools.
#
# Gated on the SUBSTITUTION ITSELF, not on the string "(Nova)": that string is already in build.sh
# twice (PRETTY_NAME, /etc/system-release), so a gate that merely looks for it passes with the
# rewrite deleted — which is exactly what the first version of this gate did.
require(r'VERSION="\1"' in build_code,
        "the image must STRIP the base's codename from os-release VERSION — that string is what "
        "the Anaconda installer prints, and the first sentence of a fresh MoOS install must not "
        "introduce a second name (neither the base's, nor one of ours)")
require('PRETTY_NAME="MoOS"' in build_code,
        "the OS introduces itself as MoOS, and as nothing else")

# The two ports must not collide. This is the whole architecture in two lines.
require("Environment=MOAI_PORT=8081" in local_unit,
        "the local brain must serve on 8081 — 8080 is moai-gateway's, and two "
        "processes on one port is the either/or this replaced")
require('MOAI_GATEWAY_PORT", "8080"' in gateway_code
        and 'MOAI_LOCAL_PORT", "8081"' in gateway_code,
        "moai-gateway must default to 8080 (the front door) and reach the local "
        "brain on 8081")

# The front door must be on for EVERY user. It used to be moai-cloud.service,
# enabled only while the user's default was cloud — a door that was locked unless
# you had already chosen to walk through it.
require("systemctl --global enable moai-gateway.service" in build_code,
        "moai-gateway is the only thing Mo AI talks to; the image must enable it "
        "for every user, not leave it opt-in")
require("systemctl --global enable moai.service" not in build_code,
        "the local brain is ON DEMAND — enabling it for every user loads 2.5 GB of "
        "weights into VRAM at every login, on a machine where it already holds 6 of 8 GB")
require(not (ROOT / "system_files/usr/lib/systemd/user/moai-cloud.service").exists(),
        "moai-cloud.service was the opt-in cloud proxy; moai-gateway.service replaces it")
require("moai-cloud" not in code(read("system_files/usr/bin/moai-config")),
        "moai-config must not still enable/disable the retired moai-cloud.service")

# ── The local brain must not hold VRAM while idle ─────────────────────────────
#
# moai.service loads ~6 GB into an 8 GB GPU and never releases it while up. That left the
# compositor almost nothing: a maximised browser on top of a loaded brain exhausted VRAM,
# the NVIDIA driver logged `NVRM: VM: invalid mmap context`, and kwin_wayland SIGSEGV'd —
# the whole desktop froze. So the brain is unloaded when idle and reloaded on demand.
idle_watch = code(read("system_files/usr/bin/moai-idle"))
require("systemctl --user stop" in idle_watch and 'UNIT="moai.service"' in idle_watch,
        "moai-idle must STOP moai.service when idle — a watchdog that only measures idleness "
        "frees no VRAM, which is the entire point")
require("moai-activity" in idle_watch and "moai-activity" in gateway_code,
        "moai-idle must key off the same activity stamp moai-gateway writes, or 'idle' is a "
        "guess — and the gateway must actually write it")
require("def mark_activity" in gateway_code and "\n        mark_activity()" in gateway_code,
        "moai-gateway must DEFINE and CALL mark_activity() on the local-chat path, or the "
        "watchdog cannot tell a loaded-but-unused brain from one in active use")
require("ActiveEnterTimestamp" in idle_watch,
        "moai-idle must treat the unit's own start as activity (ActiveEnterTimestamp): "
        "the stamp records the last CHAT, so a brain started seconds ago still wears a "
        "stale stamp — this checker killed a 2-second-old brain live on 2026-07-17, "
        "which read to the owner as 'the assistant does not work'")
require((ROOT / "system_files/usr/lib/systemd/user/moai-idle.timer").is_file()
        and (ROOT / "system_files/usr/lib/systemd/user/moai-idle.service").is_file(),
        "the idle-unload timer and its oneshot service must ship")
require("systemctl --global enable moai-idle.timer" in build_code,
        "the idle-unload timer must be enabled for every user; leaving it opt-in means the "
        "brain keeps holding VRAM until someone stops it by hand, and the freeze returns")
# The gateway must still be able to bring the brain BACK, or unloading it is a one-way trip.
require('systemctl("start")' in gateway_code and "def ensure_local" in gateway_code,
        "moai-gateway.ensure_local must start the local brain on demand — moai-idle stopping "
        "it is only safe because the next request reloads it")

# THE ROUTING CONTRACT. The app names the brain in the `model` field, and a request
# that names none must still work exactly as it did — an older client, or a chat
# opened before /models answered, sends "default" and must get the configured brain.
require('low.startswith("local:")' in gateway_code
        and 'low.startswith("cloud:")' in gateway_code,
        "moai-gateway must route on the request's model field: local:<m> / cloud:<m>")
require('brain = "cloud" if cfg.get("mode") == "cloud" else "local"' in gateway_code,
        "a request that names no brain must fall back to the configured default in "
        "config.json, or every existing client breaks. (Gate the line in resolve(), not "
        "the bare expression — it also appears in /healthz, so the loose form passed with "
        "the routing decision itself replaced by False.)")

# llama.cpp IGNORES the model field — verified: it answers a request for a model
# that does not exist with whatever weights it has loaded. So a picker offering
# several local models that merely forwards the name would be a lie: every one of
# them would be answered by the same model. Switching local model means restarting
# the unit against it, and only for a model that is already downloaded — a chat
# message must never be able to start a multi-gigabyte download.
require('systemctl("restart")' in gateway_code,
        "moai-gateway must RESTART the local unit to change model: llama.cpp ignores "
        "the model field, so passing the name through would serve the wrong weights "
        "under the right name")
require("for name in pulled_models():" in gateway_code
        and "if not target:" in gateway_code
        and "not downloaded" in gateway_code,
        "moai-gateway must only switch to a local model it found in `ramalama list`, and "
        "refuse the rest — a chat message must never kick off a multi-GB download")

# The shadowed-config trap, in the one place it can still bite. ~/.config/moos/moai.env
# is moai.service's EnvironmentFile, and systemd applies it AFTER the unit's own
# Environment= — so it WINS. Every machine that ever ran `moai-start` has one that says
# MOAI_PORT=8080, the port the gateway now owns. Shipping a corrected unit file changes
# nothing on those machines: the local brain would come up on top of the front door.
# Two things therefore have to repair the file that actually decides.
#
# Gate the USE, not the definition. Both of the next two were written first as
# `"env_port()" in gateway_code` and `"ensure_front_door()" in control_code` — and
# both stayed GREEN when the repair was disabled, because the function's own `def`
# line contains its name. A gate that matches the thing it is looking for inside the
# declaration of that thing cannot fail. Assert on the line that DECIDES.
require("def ensure_front_door():" in control_code
        and "\n    ensure_front_door()" in control_code
        and 'MOAI_PORT=%d" % LOCAL_PORT' in control_code
        # …and it must actually WRITE the repaired file. Asserting only on the
        # constants passed when the write itself was gutted — leaving an empty
        # moai.env behind — which is the same green-gate-over-a-dead-feature shape
        # this whole file exists to catch.
        and r'"\n".join(out)' in control_code
        and "os.replace(tmp, ENV_FILE)" in control_code,
        "moai-control must define AND CALL ensure_front_door(), and it must actually "
        "rewrite a stale MOAI_PORT in ~/.config/moos/moai.env — a corrected unit file "
        "is shadowed by that EnvironmentFile and loses the port")
require("env_port() != LOCAL_PORT" in gateway_code,
        "moai-gateway must reconcile the port before starting the local brain: a stale "
        "moai.env put RamaLama on 8080 while the gateway polled 8081, and the chat "
        "timed out with the model loaded and idle")
require('MOAI_PORT=8080' not in code(read("system_files/usr/bin/moai-start")),
        "moai-start must not write MOAI_PORT=8080 back into moai.env — that is the "
        "file that outranks the unit, and 8080 belongs to the gateway")

# The model list must be ASKED FOR, never invented. The user's provider is a private
# endpoint; there is no way to know what it serves except to call it. A hardcoded
# "small/medium/large" tier table would be a menu of models that may not exist on
# their account, and picking one would 404 in their face.
#
# Again: assert on the CALL, not the `def`. "local_models()" is a substring of
# "def local_models():", so gating the bare name passes even when the function has
# been renamed out of existence and models() calls something that is gone.
require('base + "/models"' in control_code
        and "cloud, cloud_error = cloud_models(cfg)" in control_code,
        "moai-control /models must ASK the configured provider for its real model list "
        "— a hardcoded tier table would be a menu of models the user's account may not "
        "have, and picking one would 404 in their face")
require('"ramalama", "list"' in control_code
        and "def local_models():" in control_code
        and "local = local_models()" in control_code,
        "moai-control /models must report the local models from `ramalama list` — and the "
        "function must exist AND be called; gating either alone leaves the other free to "
        "be renamed out from under it")
require("cloud_error" in control_code,
        "a provider with no /models must say so, so the UI can fall back to the "
        "free-text model field instead of showing an invented list")

# …and the app must actually USE the route, or all of the above is decoration.
require("model: root.route" in moai_qml,
        "Mo AI must send the chosen route as the request's model field")
require("function pickRoute(" in moai_qml and "root.pickRoute(" in moai_qml
        and "function loadModels()" in moai_qml and "root.loadModels()" in moai_qml,
        "Mo AI must offer the brain/model picker and populate it from moai-control")

# moai-start writes the EnvironmentFile that outranks the unit. If it defaults the
# port to 8080 again, every `moai-start` puts the local brain back on top of the
# front door — which is the bug this whole change is undoing. (Gating for the
# literal "MOAI_PORT=8080" is not enough: the file writes MOAI_PORT=$PORT, so the
# 8080 never appears as a string.)
moai_start_code = code(read("system_files/usr/bin/moai-start"))
require('PORT="${MOAI_PORT:-8081}"' in moai_start_code,
        "moai-start must default the local brain to 8081; 8080 is moai-gateway's")

# The versioned migration is what makes the redesign visible to existing users.
apply_theme = read("system_files/usr/bin/moos-apply-theme")
apply_theme_code = code(apply_theme)
require("THEME_REV=20" in apply_theme_code, "MoOS UI2 visual schema must be revision 20")
# Rev 12 carries a rewritten desk widget (weather + rolling digits), and a plasmoid does not
# reach an existing user by being newer. OSTree pins every mtime under /usr to the epoch and
# Qt's qmlcache is keyed on mtime, so plasmashell happily keeps executing the COMPILED OLD
# widget after the upgrade — the file changed, the cache did not notice, and the user sees
# last month's clock. apply-theme purges the QML caches on every THEME_REV.
require("qmlcache" in apply_theme_code,
        "moos-apply-theme must purge the QML disk cache on a THEME_REV bump — OSTree's frozen "
        "mtimes mean a rebuilt plasmoid is invisible to qmlcache, and the old widget keeps "
        "running")

# Nova must survive Plasma, not just reach it.
#
# Plasma's automatic day/night switch resolves Default{Light,Dark}LookAndFeel BY NAME
# when it fires. If the named package is not installed it does NOT fall back to the
# configured LookAndFeelPackage — it falls back to Breeze and PERSISTS that into the
# user's kdeglobals, which then outranks /etc/xdg for good. Removing Fedora's
# look-and-feel packages did exactly this to an existing user: the image was right, the
# system default was right, and the desktop still came up Breeze Dark.
#
# Two things have to hold, so both are gated. The switch must be off for new users, and
# an apply-once marker must never outrank what the desktop is ACTUALLY wearing — a
# script that trusts its own marker on a desktop that has silently reverted is the thing
# that keeps it reverted.
require("pin_lookandfeel_switch_targets()" in apply_theme_code,
        "moos-apply-theme must point Plasma's day/night switch at MoOS themes, "
        "never leave it aimed at a package that is not installed")
require("current_lookandfeel()" in apply_theme_code and "SELF-HEAL" in apply_theme_code,
        "moos-apply-theme must re-apply when the desktop is no longer wearing MoOS")
require(all(token in apply_theme_code for token in (
            "current_scheme()", "current_style()", "current_icons()",
            "current_scene_state()", "theme_complete()")),
        "the apply-once marker must be backed by runtime readback of the full theme and "
        "the exact per-containment desktop-SCENE state, not only LNF + decoration")
require("scene-each" in apply_theme_code
        and "desktops=[1-9][0-9]*;state=" in apply_theme_code,
        "the desktop scene must be validated once per containment; a global count of one "
        "breaks every multi-monitor or multi-Activity desktop")
require("timeout 4s gdbus call" in apply_theme_code,
        "runtime scene readback must time out instead of hanging login on an "
        "unresponsive plasmashell")
require("desktop_wallpapers_complete()" in apply_theme_code
        and "matching == desktops" in apply_theme_code
        and "grep -m1 '^Image='" not in apply_theme_code,
        "theme completion must verify the wallpaper on every desktop containment; "
        "the first Image= line is not authoritative on multiple monitors/Activities")
# The scene replaces the desktop-widget era: the repair points every containment
# at org.moos.ui2.wallpaper, hands it the half's package, and clears the retired
# applets that would otherwise still draw over the icons. addWidget placement is
# FORBIDDEN — any coordinate is a collision with some icon layout somewhere.
require("apply_desktop_scene" in apply_theme_code
        and 'd.wallpaperPlugin = "org.moos.ui2.wallpaper"' in apply_theme_code
        and 'writeConfig("Image", IMAGE)' in apply_theme_code
        and 'ws[j].remove()' in apply_theme_code,
        "theme repair must point every desktop containment at the MoOS scene wallpaper "
        "and remove the retired dashboard applets")
require("d.addWidget(" not in apply_theme_code,
        "moos-apply-theme must not place desktop widgets — the bento lives inside the "
        "wallpaper precisely because every widget coordinate collides with icons somewhere")
require("flock -n 9" in apply_theme_code,
        "two overlapping autostart instances must not race while replacing the same widget")
require('theme_complete "$lnf_after" "$deco_after" "$want_wallpaper_package"'
        in apply_theme_code
        and 'rm -f "$marker"' in apply_theme_code,
        "a partial theme apply must leave its marker absent so the next login retries")

xdg_kdeglobals = code(read("system_files/etc/xdg/kdeglobals"))
require("AutomaticLookAndFeel=false" in xdg_kdeglobals,
        "the day/night switch ships off; changing the look at sunset is a choice, not a default")
require("DefaultDarkLookAndFeel=org.moos.ui2" in xdg_kdeglobals
        and "DefaultLightLookAndFeel=org.moos.ui2.light" in xdg_kdeglobals
        and "LookAndFeelPackage=org.moos.ui2" in xdg_kdeglobals,
        "both day/night targets must name MoOS themes — Plasma resolves them BY NAME, "
        "and a name it cannot resolve sends the desktop to Breeze, permanently")

# ── MoOS ships ONE look, in two halves, and both halves must be whole ────────
#
# It used to ship THREE looks — Nova, then UI, then UI2 — all installed at once. System Settings
# offered the user six MoOS themes, Konsole offered six MoOS profiles, and the wallpaper picker
# held five Nova wallpapers and one called "F44". The owner's rule: one name, one of everything.
# The old two generations are gone; these gates guard the one that is left, and the one below
# makes sure they cannot come back.
#
# A half-installed light theme is worse than none: Plasma applies what it finds and silently
# substitutes Breeze for what it does not, so the user gets a desktop that is MoOS in some places
# and Breeze in others and cannot tell why. Each of these is a piece the light half cannot do
# without.
light_lnf = code(
    read("system_files/usr/share/plasma/look-and-feel/org.moos.ui2.light/contents/defaults")
)
require("ColorScheme=MoOSUI2Light" in light_lnf and "name=MoOSUI2Light" in light_lnf,
        "the light Global Theme must select the light colour scheme and Plasma style")
require("theme=__aurorae__svg__MoOSUI2Light" in light_lnf,
        "the light Global Theme must select the light window decoration — Aurorae has no "
        "ColorScheme stylesheet, so a light desktop with the dark decoration writes "
        "near-white title text onto a near-white title bar")
require("Theme=MoOSUI2Light" in light_lnf,
        "the light Global Theme must select the light icon theme — the dark symbolics are drawn "
        "for a dark panel and vanish on porcelain")

for asset in (
    "system_files/usr/share/aurorae/themes/MoOSUI2Light/decoration.svg",
    "system_files/usr/share/color-schemes/MoOSUI2Light.colors",
    "system_files/usr/share/konsole/MoOSUI2Light.colorscheme",
    "system_files/usr/share/konsole/MoOSUI2Light.profile",
    "system_files/usr/share/plasma/desktoptheme/MoOSUI2Light/colors",
):
    require((ROOT / asset).is_file(), f"the light half of the MoOS theme is missing {asset}")

light_style = code(read("system_files/usr/share/plasma/desktoptheme/MoOSUI2Light/plasmarc"))
require("enabled=false" in light_style,
        "the light theme must keep adaptive transparency off; it otherwise turns the dock into an "
        "opaque white slab while the dark half remains designed glass")

# ── One engine, one family ───────────────────────────────────────────────────
#
# MoOS ships a FAMILY of looks on the single UI2 engine — every family is a matched
# light+dark PAIR: Graphite/Tidal, Nova/Nova Light, Amethyst/Amethyst Light,
# Midnight/Daylight, Aurora/Aurora Light. The light siblings' ids are the dark id +
# ".light". The rule is still not self-enforcing: an OLD generation (org.moos.nova,
# org.moos.ui) or a foreign look left on disk does not error, it quietly offers the user a
# second, wrong picker entry. So the family must be EXACTLY these — every one MoOS-branded,
# nothing foreign, no reintroduced old generation. (verify_identity.py enforces the same set
# with name/id checks; this gate holds the on-disk package + Konsole-profile count.)
FAMILY_LNF = ["org.moos.ui2", "org.moos.ui2.amethyst", "org.moos.ui2.amethyst.light",
              "org.moos.ui2.aurora", "org.moos.ui2.aurora.light", "org.moos.ui2.dev",
              "org.moos.ui2.dev.light", "org.moos.ui2.gaming", "org.moos.ui2.gaming.light",
              "org.moos.ui2.light", "org.moos.ui2.midnight", "org.moos.ui2.midnight.light",
              "org.moos.ui2.nova", "org.moos.ui2.nova.light", "org.moos.ui2.study",
              "org.moos.ui2.study.light"]
lnf_dirs = sorted(p.name for p in (ROOT / "system_files/usr/share/plasma/look-and-feel").iterdir())
require(lnf_dirs == FAMILY_LNF,
        f"the MoOS Global Theme family must be exactly {FAMILY_LNF}; found {lnf_dirs}")

FAMILY_PROFILES = ["MoOSUI2.profile", "MoOSUI2Amethyst.profile", "MoOSUI2AmethystLight.profile",
                   "MoOSUI2Arena.profile", "MoOSUI2ArenaLight.profile", "MoOSUI2Aurora.profile",
                   "MoOSUI2AuroraLight.profile", "MoOSUI2Daylight.profile", "MoOSUI2Forge.profile",
                   "MoOSUI2ForgeLight.profile", "MoOSUI2Light.profile", "MoOSUI2Midnight.profile",
                   "MoOSUI2Nova.profile", "MoOSUI2NovaLight.profile", "MoOSUI2Scholar.profile",
                   "MoOSUI2ScholarLight.profile"]
konsole_profiles = sorted(
    p.name for p in (ROOT / "system_files/usr/share/konsole").glob("*.profile"))
require(konsole_profiles == FAMILY_PROFILES,
        f"the MoOS Konsole profile family must be exactly {FAMILY_PROFILES}; found {konsole_profiles}")

wallpapers = sorted(p.name for p in (ROOT / "system_files/usr/share/wallpapers").iterdir())
require(all(w.startswith("MoOS") for w in wallpapers),
        f"MoOS ships MoOS's wallpapers; found {wallpapers}")

# No name but MoOS. Checked across everything the image installs, with comments stripped, because
# the history of this rule is written in the comments that explain it.
shipped_names = ""
for path in (ROOT / "system_files").rglob("*"):
    if path.is_file() and path.suffix in (".desktop", ".json", ".theme", ".plymouth", ".profile",
                                          ".colorscheme", ".colors", "") and path.stat().st_size < 200_000:
        try:
            shipped_names += code(path.read_text(encoding="utf-8"), "hash")
        except (UnicodeDecodeError, OSError):
            continue
for banned in ("NovaShadow", "NovaIce", "Nova Seed", "moos-nova"):
    require(banned not in shipped_names,   # shipped_names = system_files only, comments stripped
            f"'{banned}' must not ship: the OS is called MoOS, and a picker that offers the user "
            f"a second name is a picker that makes them wonder what they installed")

# The light half is GENERATED from the dark one. If someone hand-edits it, the two silently
# diverge — so the generator has to stay in the repo and stay wired to both halves.
generator = code(read("artwork/generate_moos_ui2.py"))
require("MoOSUI2Light" in generator and "MoOSUI2" in generator,
        "the MoOS light/dark pair must be generated, not hand-maintained")
for package in ("org.moos.ui2", "org.moos.ui2.light"):
    previews = ROOT / f"system_files/usr/share/plasma/look-and-feel/{package}/contents/previews"
    for name in ("preview.png", "lockscreen.png", "splash.png", "fullscreenpreview.jpg"):
        require((previews / name).is_file(), f"{package} is missing its user-facing {name}")

light_deco = code(read("system_files/usr/share/aurorae/themes/MoOSUI2Light/MoOSUI2Lightrc"))
require("ActiveTextColor=23,48,46,255" in light_deco,
        "the light decoration must have DARK title text; Aurorae takes its title colour "
        "from its own rc, not from the colour scheme, so the dark rc paints near-white "
        "text onto a near-white title bar")

# The user must be able to switch, and switching must carry the three things a Global
# Theme does not: Konsole (its scheme is not a KDE scheme and follows nothing), GTK's
# prefer-dark (Plasma's gtkconfig never sets it), and the wallpaper (measured: applying
# the light Global Theme left the navy wallpaper in place).
theme_switch = code(read("system_files/usr/bin/moos-theme"))
require("plasma-apply-lookandfeel -a" in theme_switch,
        "moos-theme must apply the Global Theme")
require("--key DefaultProfile" in theme_switch,
        "moos-theme must switch Konsole's profile — a light desktop with a black terminal "
        "is not a light desktop")
require("gtk-application-prefer-dark-theme" in theme_switch
        and "color-scheme" in theme_switch,
        "moos-theme must tell GTK which side of the day it is on, or Firefox stays dark "
        "on a light desktop")
# The wallpaper is the MoOS SCENE plugin (image + dashboard bento below the
# icons). plasma-apply-wallpaperimage is FORBIDDEN: it flips containments back
# onto org.kde.image and the bento silently vanishes. The switch must drive the
# scene plugin directly, per containment.
require("apply_desktop_scene" in theme_switch
        and 'd.wallpaperPlugin = "org.moos.ui2.wallpaper"' in theme_switch
        and 'writeConfig("Image", IMAGE)' in theme_switch,
        "moos-theme must set the desktop SCENE (org.moos.ui2.wallpaper) per containment; "
        "applying the Global Theme does not carry it")
require("plasma-apply-wallpaperimage" not in theme_switch,
        "moos-theme must not call plasma-apply-wallpaperimage — it forces org.kde.image "
        "back onto the containments and the dashboard bento disappears")
# The LNF defaults must not carry a [Wallpaper] section for the same reason:
# LookAndFeelManager applies it by forcing org.kde.image onto every containment.
for half in ("org.moos.ui2", "org.moos.ui2.light"):
    lnf_defaults = code(
        read(f"system_files/usr/share/plasma/look-and-feel/{half}/contents/defaults"))
    require("[Wallpaper]" not in lnf_defaults,
            f"{half}/contents/defaults carries a [Wallpaper] section — every theme apply "
            f"would force org.kde.image back and erase the scene (the dashboard)")

# moos-apply-theme repairs the look the user is ON, not the one MoOS prefers. Dragging a
# user who chose Light back to Dark on every login is not protection, it is the bug.
require("target_lnf()" in apply_theme_code and "theme_intact()" in apply_theme_code,
        "the self-heal must accept EITHER MoOS look and repair to the one the user chose")

ui_migrate = read("system_files/usr/bin/moos-ui-migrate")
require("MOOS_THEME_REV=8" in ui_migrate and "MOAI_UI_REV=3" in ui_migrate,
        "UI cache and Mo AI migrations must be explicitly revisioned")
require('rm -rf "$HOME/.cache"' not in ui_migrate,
        "UI migration must never erase the whole user cache")

# GStreamer keys its registry on plugin mtimes, and OSTree pins every mtime under /usr to the
# epoch — so the registry never invalidates itself across a bootc upgrade, including one that
# changes the DRIVER. A moos -> moos-nvidia switch leaves the user with a registry that cached
# "nvcodec provides zero elements", and the hardware H.264 encoder Mo PC Remote needs does not
# exist as far as GStreamer is concerned. Measured on real hardware: dropping it made
# nvh264enc / nvh265enc / nvautogpuh264enc appear at once, at 4.3 Mbit/s against JPEG's 79.
#
# It must be keyed on the booted deployment, not on the revision constants — those are bumped
# by hand, and nobody bumps one because an image changed — and it must run BEFORE the
# apply-once marker gate, which by construction cannot notice a different image.
require("gstreamer-1.0" in ui_migrate and "gst-registry-" in ui_migrate,
        "the GStreamer registry must be dropped after an image change, or a moos-nvidia "
        "upgrade keeps caching the answer that the NVENC encoder does not exist")
require(ui_migrate.index("gst-registry-") < ui_migrate.index('[ -e "$marker" ] && exit 0'),
        "the GStreamer registry drop must run BEFORE the once-per-revision marker gate; "
        "an apply-once marker cannot notice that the machine booted a different image")
require("secret-tool" not in ui_migrate,
        "UI migration must never inspect or mutate Mo AI credentials")

# Windows must wear the MoOS decoration, not Breeze. Breeze here means Breeze's
# X / v / ^ title-bar glyphs on every window — the loudest remaining "this is
# stock KDE" tell after the dock.
# ── Log in to an empty desktop, not to the one that crashed ──────────────────
# Plasma's default is `restorePreviousLogout`, and on this hardware that default IS the bug the
# maintainer reported as "the reboot hangs". He rebooted into a fresh image on 2026-07-14 and
# Plasma faithfully restored what had been open: MoPlayer rendering video, Mo AI's QML shell, and
# the remote's screen capture — together, on a card a local LLM already holds ~6 GB of. Ninety
# seconds after login kwin_wayland could not allocate a swapchain and SIGSEGV'd; the desktop froze
# and rebuilt itself.
#
# Restoring an IPTV player is also a live action, not a cosmetic one: the subscription allows
# max_connections = 1, so a session restore can knock the user's own stream off a TV in another
# room. This is a default (in /etc/xdg), not a decree — System Settings still wins.
ksmserverrc = code(read("system_files/etc/xdg/ksmserverrc"))
require("loginMode=emptySession" in ksmserverrc,
        "MoOS must log in to an empty session: restoring the previous one reopened MoPlayer, Mo AI "
        "and the screen capture at once, and kwin SIGSEGV'd on the VRAM they asked for")

kwinrc = read("system_files/etc/xdg/kwinrc")
require("library=org.kde.kwin.aurorae" in kwinrc,
        "KWin must load the Aurorae engine, not Breeze")
require("theme=__aurorae__svg__MoOSUI2" in kwinrc,
        "KWin must use the MoOS UI2 decoration; the __aurorae__svg__ prefix is "
        "what routes the theme to the Aurorae SVG engine")

# …and the two checks above are NOT enough on their own. They were green for the
# entire life of this project while every window wore Breeze.
#
# XDG_CONFIG_DIRS is "~/.config/kdedefaults:/etc/xdg:…", and LookAndFeelManager writes
# the applied theme's defaults into kdedefaults/ — which therefore SHADOWS the
# /etc/xdg/kwinrc gated above. A user created under Breeze gets
# kdedefaults/kwinrc = org.kde.breeze, and Nova's defaults never declared a decoration,
# so applying Nova never overwrote it. The system default could not win, and the gate
# on it could not see that.
#
# Gate the file that actually decides: the Look-and-Feel defaults (correct for new
# users) and the explicit user-config write in the migration (correct for existing
# ones, since ~/.config outranks kdedefaults outright).
lnf_defaults = read("system_files/usr/share/plasma/look-and-feel/org.moos.ui2/contents/defaults")
require("[kwinrc][org.kde.kdecoration2]" in lnf_defaults
        and "theme=__aurorae__svg__MoOSUI2" in lnf_defaults,
        "org.moos.ui2's defaults must declare the window decoration, or Breeze's entry "
        "in ~/.config/kdedefaults/kwinrc permanently shadows /etc/xdg/kwinrc")
require('--group org.kde.kdecoration2 --key theme "$want_deco"' in apply_theme,
        "the theme migration must pin the MoOS decoration into an existing user's own "
        "kwinrc; a system default cannot reach past kdedefaults")

# Same trap, third instance: [Sounds] is not in the entry set LookAndFeelManager applies,
# so a user carrying Theme=freedesktop from the defaults they were created under keeps it,
# and the MoOS sound theme ships without ever playing.
require("--group Sounds --key Theme moos" in apply_theme,
        "the theme migration must pin the Nova sound theme into an existing user's own "
        "kdeglobals; Plasma never writes [Sounds] when applying a Global Theme")

# GTK apps are the last non-Qt surface, and the one place where MoOS was generating the
# right answer and throwing it away. Plasma's gtkconfig module regenerates
# ~/.config/gtk-3.0/colors.css from the active KDE scheme — those colours ARE Nova's — but
# it never sets gtk-theme-name. Empty means GTK uses built-in Adwaita, which does not read
# a single one of the borders_breeze / content_view_bg_breeze variables that file defines.
# Only the Breeze GTK stylesheet does (965 references). Naming it is what connects the two.
require("--key gtk-theme-name Breeze" in apply_theme,
        "GTK apps must name the Breeze stylesheet, or the Nova palette Plasma generates "
        "into colors.css is read by nothing")
require("--key gtk-sound-theme-name moos" in apply_theme,
        "GTK's sound theme must be pinned too; gtkconfig syncs icons and cursors from "
        "kdeglobals but never [Sounds]")

aurorae = ROOT / "system_files/usr/share/aurorae/themes/MoOSUI2"
for name in ("decoration.svg", "close.svg", "minimize.svg", "maximize.svg",
             "restore.svg", "MoOSUI2rc"):
    require((aurorae / name).is_file(),
            f"the MoOS decoration must ship {name}")

# The shadow is the theme's own job — Aurorae paints the decoration SVG across
# its Padding* region, and a decoration with no padding has no drop shadow, which
# lands windows flat on the wallpaper and looks WORSE than the Breeze it
# replaced. Guard the padding so a future edit cannot quietly delete the shadow.
themerc = read("system_files/usr/share/aurorae/themes/MoOSUI2/MoOSUI2rc")
for pad in ("PaddingLeft", "PaddingRight", "PaddingTop", "PaddingBottom"):
    match = re.search(rf"^{pad}=(\d+)$", themerc, re.MULTILINE)
    require(match is not None and int(match.group(1)) > 0,
            f"{pad} must be > 0 or the window decoration ships with no shadow")

# Same fill-only invariant as the Plasma Style: a stroke inflates the FrameSvg
# element bbox and the stretch factor magnifies the overflow.
for svg in sorted(aurorae.glob("*.svg")):
    require("stroke" not in svg.read_text(encoding="utf-8"),
            f"{svg.name} must be fill-only (stroke inflates the FrameSvg bbox)")

# Nova must own the panel and the task buttons. Without these two FrameSvgs the
# Plasma Style falls back down the chain to breeze-dark for the dock background
# and the task indicator, and the desktop reads as stock KDE with a repaint --
# which is the exact complaint the Nova redesign exists to answer.
widgets = ROOT / "system_files/usr/share/plasma/desktoptheme/MoOSUI2/widgets"
for svg in ("panel-background.svg", "tasks.svg"):
    require((widgets / svg).is_file(),
            f"Nova Plasma Style must ship its own {svg}, not inherit Breeze's")

# 9-patch pieces must be fill-only. A stroke inflates the element's bounding box
# by half the stroke width, and FrameSvg multiplies that overflow by the stretch
# factor -- on a 4K dock a 0.5px overhang became a 50px transparent band punched
# through the panel. Verified on hardware; keep the art strokeless.
for svg in ("panel-background.svg", "tasks.svg"):
    path = widgets / svg
    if path.is_file():
        require("stroke" not in path.read_text(encoding="utf-8"),
                f"{svg} must be fill-only; a stroke inflates the FrameSvg "
                f"element bbox and tears a gap in the stretched edge")

# Kickoff remains KDE's integrated plugin, but every presentation surface it
# asks Plasma Style for must be owned by Nova rather than falling back to Breeze.
kickoff_surfaces = {
    "dialogs/background.svg",
    "widgets/lineedit.svg",
    "widgets/plasmoidheading.svg",
    "widgets/viewitem.svg",
    "widgets/listitem.svg",
    "widgets/line.svg",
    "widgets/button.svg",
}
nova_theme = ROOT / "system_files/usr/share/plasma/desktoptheme/MoOSUI2"
for relative in kickoff_surfaces:
    path = nova_theme / relative
    require(path.is_file(), f"the MoOS Kickoff surface must exist: {relative}")
    if path.is_file():
        require("stroke" not in path.read_text(encoding="utf-8"),
                f"{relative} must remain fill-only for FrameSvg geometry")

# The dock has to actually leave the screen edge, or none of the rounded glass
# reads as floating.
layout = read("system_files/usr/share/plasma/layout-templates/"
              "org.kde.plasma.desktop.defaultPanel/contents/layout.js")
require("panel.floating = true" in layout, "the MoOS dock must float")

# ── Frosted glass: the premium surface finish MoOS competes on ────────────────
#
# A floating dock that turns into an opaque slab under every maximised window is not a
# glass dock. Nova pins Plasma::Theme::adaptiveTransparencyEnabled() OFF so the dock keeps
# its translucent blur at all times, like the macOS dock / Win11 acrylic taskbar. The
# blur plugin (Effect-blur) must stay shipped-on for the frost to exist at all.
nova_plasmarc = code(read("system_files/usr/share/plasma/desktoptheme/MoOSUI2/plasmarc"))
require("[AdaptiveTransparency]" in nova_plasmarc and "enabled=false" in nova_plasmarc,
        "the Nova dock must stay frosted glass (AdaptiveTransparency enabled=false); adaptive "
        "opacity turns the floating dock into an opaque slab the moment a window is maximised")
kwin_glass = code(read("system_files/etc/xdg/kwinrc"))
require("blurEnabled=true" in kwin_glass,
        "KWin's blur must ship ON — it is what frosts the dock, the terminal and every "
        "translucent surface; without it 'glass' is just flat transparency")

# The Arabic terminal is SOLID by choice (the maintainer tried the glass and rejected it):
# a fully opaque slab, no blur, in both schemes — but beautified. Both colour schemes must
# stay opaque, and both profiles must carry the premium chrome, or the terminal regresses to
# either a see-through window or a bare default.
for scheme in ("MoOSUI2Dark", "MoOSUI2Light"):
    konsole_scheme = code(read(f"system_files/usr/share/konsole/{scheme}.colorscheme"))
    require("Opacity=1" in konsole_scheme and "Blur=false" in konsole_scheme,
            f"{scheme} Konsole scheme must be SOLID (Opacity=1, Blur=false) — the maintainer "
            f"asked for a solid terminal, not the frosted-glass one that was tried and rejected")
for prof in ("MoOSUI2.profile", "MoOSUI2Light.profile"):
    profile_text = code(read(f"system_files/usr/share/konsole/{prof}"))
    require("TerminalMargin=14" in profile_text
            and "ScrollBarPosition=2" in profile_text
            and "UseCustomCursorColor=true" in profile_text
            and "AutoCopySelectedText=true" in profile_text,
            f"{prof} must keep the beautified terminal: inner padding, a hidden scrollbar, a "
            f"coloured cursor and copy-on-select — not the bare FALLBACK defaults")
    # And the keys must sit in the groups Konsole actually reads. Konsole's group names are
    # "Cursor Options" and "Interaction Options"; under [Cursor]/[Interaction] the file still
    # parses, this gate's key strings are still present, and the keys are silently DEAD — a
    # live terminal was verified rendering a white cursor with CustomCursorColor set.
    require("[Cursor Options]" in profile_text and "[Interaction Options]" in profile_text,
            f"{prof} must put the cursor keys under [Cursor Options] and the selection keys "
            f"under [Interaction Options] — Konsole ignores [Cursor]/[Interaction] entirely")
konsolerc_chrome = code(read("system_files/etc/xdg/konsolerc"))
require("ShowMenuBarByDefault=false" in konsolerc_chrome
        and "TabBarVisibility=ShowTabBarWhenNeeded" in konsolerc_chrome,
        "konsolerc must ship the clean chrome (no menu bar, tab strip only when needed) — that "
        "is the 'smaller UI' the maintainer asked for; a single-tab window should be pure terminal")
# The toolbars are the other half of that "smaller UI", and konsolerc cannot reach them: they
# live in the Qt State blob in ~/.local/state/konsolestaterc, outside the XDG config cascade.
# apply-theme is the only place that can hide them, so gate it there.
require("konsolestaterc" in apply_theme_code and "sessionToolbar" in apply_theme_code,
        "moos-apply-theme must hide Konsole's toolbars by patching the State blob in "
        "konsolestaterc — no config file can do it, so if this drops out the terminal silently "
        "grows its toolbar back")
require('addWidget("org.kde.plasma.kickoff")' in layout,
        "MoOS must preserve the integrated Kickoff launcher")
require("org.moos.nova.launcher" not in layout,
        "MoOS must not ship a competing launcher in the panel")
require('addWidget("org.moos.nova.clock")' in layout,
        "new users must receive the compact Nova clock")
# The living brand: org.moos.brand is the ONE MoOS mark in the bar (animated
# emblem + glance popup), and Kickoff hands the logo role to it. Both sides of
# that trade are gated together — brand present AND Kickoff on a search glyph
# glyph — because shipping only half re-creates the double-logo bar one way,
# or a logo-less bar the other.
require('addWidget("org.moos.brand")' in layout,
        "new users must receive the animated MoOS brand applet in the panel")
require('writeConfig("icon", "system-search-symbolic")' in layout,
        "Kickoff must wear the search glyph — the MoOS wordmark owns identity "
        "while the adjacent launcher communicates its real purpose")
for package in ("org.moos.nova.clock", "org.moos.brand", "org.moos.heroclock"):
    root = ROOT / "system_files/usr/share/plasma/plasmoids" / package
    require((root / "metadata.json").is_file() and
            (root / "contents/ui/main.qml").is_file(),
            f"missing complete Plasma package: {package}")
brand_qml = code(read(
    "system_files/usr/share/plasma/plasmoids/org.moos.brand/contents/ui/main.qml"
), style="slash")
require("if (root.expanded)" in brand_qml and "if (expanded)" not in brand_qml,
        "the brand applet must qualify root.expanded; the bare signal argument "
        "uses deprecated parameter injection and warns on every Plasma login")
require("height * 2.45" in brand_qml and 'text: "MoOS"' in brand_qml
        and '"READY"' in brand_qml,
        "the panel brand must remain the MoOS wordmark control, not regress to "
        "an anonymous circular dock icon")
# The brand applet must never grow a shader/Lottie dependency (it lives in
# plasmashell, forever), and its actions must stay user-session binaries —
# a pkexec here would put a password prompt behind a panel click. code():
# the header comment documents exactly these bans, so grep the code, not the prose.
for always_on in ("org.moos.brand", "org.moos.heroclock"):
    applet_qml = code(read(f"system_files/usr/share/plasma/plasmoids/{always_on}/contents/ui/main.qml"),
                      style="slash")
    for banned in ("ShaderEffect", "MultiEffect", "Lottie", "pkexec", "sudo "):
        require(banned not in applet_qml,
                f"{always_on} must not use {banned.strip()!r}")
logout_qml = read(
    "system_files/usr/share/plasma/look-and-feel/org.moos.ui2/contents/logout/Logout.qml"
)
require("gridUnit * 55 ? 2 : 3" in logout_qml,
        "the desktop logout surface must keep its balanced 3x2 command deck "
        "with a two-column narrow-screen fallback")
require("try {" in layout,
        "the floating setter must be guarded -- a throw in the layout template "
        "leaves the session with NO panel")
require("want_wallpaper_package=/usr/share/wallpapers/MoOSUI2Graphite" in apply_theme
        and "contents/images_dark/3840x2160.jpg" in apply_theme,
        "Existing users must migrate to the MoOS UI2 Graphite dark wallpaper")

lock_config = read("system_files/etc/xdg/kscreenlockerrc")
require("Image=/usr/share/wallpapers/MoOSUI2Graphite" in lock_config,
        "Plasma lock screen must use MoOS UI2 Graphite")

# ── The login screen, and why it is gated against the lock screen ─────────────
#
# The greeter is the first surface of the running system the user sees, and it is the only
# themed surface a Global Theme can never reach: LookAndFeelManager runs inside the user's
# session, long after plasma-login-manager has drawn. So the greeter is pinned by hand in the
# image — and a hand-pinned value is precisely what a theme rollout leaves behind.
#
# It was left behind. UI2 moved the lock screen to MoOSUI2Graphite and did not move the
# greeter, so a fully-UI2 machine booted to a Nova login screen and a Graphite desktop one
# second later. The in-image gate could not see it: it asserted the literal string
# "NovaHorizon", which is to say it was holding the bug in place.
#
# The fix is to gate the RELATIONSHIP, not a name. Whatever wallpaper the lock screen uses,
# the login screen must use the same one. That cannot be satisfied by a stale constant, and
# the next theme family inherits the guarantee for free.
#
# code() is not optional here: the drop-in's own comments explain this bug and therefore
# contain the very wallpaper name being asserted. Gate the config, not the prose.
login_drop_ins = sorted(
    (ROOT / "system_files/usr/lib/plasmalogin/plasmalogin.conf.d").glob("*.conf")
)
require(login_drop_ins != [],
        "the login screen ships no MoOS drop-in — the greeter would show Plasma's default")
login_config = code(
    "\n".join(p.read_text(encoding="utf-8") for p in login_drop_ins)
)
# The plugin id is a RELATIONSHIP too, not a constant. This line used to pin
# "org.kde.image", and went stale the day the login scene became MoOS's own
# plugin. Whatever the drop-in names must still resolve in this tree.
# Whatever the drop-in names must be loadable: org.kde.* ships with Plasma; an
# org.moos.* id must be a wallpaper package in THIS tree, main.qml and all —
# otherwise plasma-login-wallpaper resolves nothing and the first screen after
# boot is black.
login_plugin = re.search(r"^WallpaperPluginId=(\S+)", login_config, re.MULTILINE)
require(login_plugin is not None,
        "the login screen must select a wallpaper plugin, or the greeter draws Plasma's default")
if login_plugin is not None and not login_plugin.group(1).startswith("org.kde."):
    login_scene = ROOT / "system_files/usr/share/plasma/wallpapers" / login_plugin.group(1)
    require((login_scene / "contents/ui/main.qml").is_file(),
            f"the login screen names wallpaper plugin {login_plugin.group(1)} but the tree "
            "ships no such package — the first screen after boot would be black")
    require((login_scene / "contents/config/main.xml").is_file()
            and 'name="Image"' in (login_scene / "contents/config/main.xml").read_text(encoding="utf-8"),
            f"login wallpaper plugin {login_plugin.group(1)} declares no Image config key — "
            "the drop-in's wallpaper value would be silently ignored")
    require(f"[Greeter][Wallpaper][{login_plugin.group(1)}][General]" in login_config,
            "the login drop-in's wallpaper group does not match the plugin it names — "
            "the greeter would load the scene with an empty config")
    login_scene_qml = code(
        (login_scene / "contents/ui/main.qml").read_text(encoding="utf-8"),
        style="slash",
    )
    for expensive in ("Repeater", "Animation", "ShaderEffect", "Canvas"):
        require(expensive not in login_scene_qml,
                f"the login wallpaper uses {expensive}; authentication must paint "
                "immediately even with software rendering")
    require("anchors.left: parent.left" in login_scene_qml
            and "anchors.top: parent.top" in login_scene_qml,
            "the MoOS login signature is not pinned to its safe corner — a "
            "centred brand can overlap Plasma's password/user surface again")

# Login is one security surface, not an idle clock page followed by a second
# authentication layout. The clock remains on the lock screen; a cold boot
# presents the password prompt directly.
require(re.search(r"^ShowClock=false$", login_config, re.MULTILINE) is not None,
        "Plasma Login Manager must open directly on the password surface; its "
        "idle clock page reintroduces a second layout and can overlap branding")

lock_wallpaper = re.search(r"^Image=.*/wallpapers/([A-Za-z0-9_.-]+)",
                           code(lock_config), re.MULTILINE)
require(lock_wallpaper is not None,
        "the lock screen names no wallpaper package, so the login screen cannot be matched to it")
if lock_wallpaper is not None:
    package = lock_wallpaper.group(1)
    require(f"/wallpapers/{package}" in login_config,
            f"the login screen must use the lock screen's wallpaper ({package}); the first "
            f"screen after boot is otherwise off-brand while every gate stays green")
    require((ROOT / "system_files/usr/share/wallpapers" / package).is_dir(),
            f"the login and lock screens name a wallpaper package the image does not ship: "
            f"{package}")

# SDDM is DEAD on this base: Kinoite 44 boots plasmalogin, so the moos SDDM
# theme and its config were files nobody read — and the gates that asserted their
# contents were green on a login screen that never rendered them. The tree is
# deleted; this now fails if it comes back. The real login screen is verified
# above, against the lock screen's wallpaper.
for dead_sddm in ("system_files/usr/share/sddm", "system_files/etc/sddm.conf.d"):
    require(not (ROOT / dead_sddm).exists(),
            f"dead SDDM login stack is back in the tree: {dead_sddm} — "
            "plasmalogin is the display manager; nothing reads SDDM files")

# The dock is a floating CAPSULE — centered, hugging its content — not an
# edge-to-edge bar. The installed flagship machine runs that geometry (the
# shipped proof ui2-dark-real-desktop.jpg), but the layout template only set
# `floating`, so every new user and the live ISO booted to the old full-width
# bar while every gate stayed green. Seen live in QEMU, 2026-07-14.
#
# Two surfaces hand out this geometry — the template (users with no panel yet)
# and moos-apply-theme's migration (users who already have one). Gate the
# RELATIONSHIP: both must state all three decisions, or a fresh user and an
# upgraded user boot into two different docks.
dock_surfaces = {
    "dock template": code(read(
        "system_files/usr/share/plasma/layout-templates/"
        "org.kde.plasma.desktop.defaultPanel/contents/layout.js")),
    "dock migration (moos-apply-theme)": code(read("system_files/usr/bin/moos-apply-theme")),
}
for dock_surface, dock_code in dock_surfaces.items():
    for needle, decision in (
        ('lengthMode = "fit"', "hug the content (capsule, not bar)"),
        ('alignment = "center"', "sit centered"),
        (".floating = true", "float off the screen edge"),
    ):
        require(needle in dock_code,
                f"{dock_surface} no longer makes the dock {decision} — "
                f"missing {needle!r}; fresh and upgraded users would get different docks")

# libadwaita apps ignore gtk-theme-name, so without these css files Bazaar —
# MoOS's OWN app store — renders stock Adwaita blue on a turquoise desktop.
# The colours are not this gate's constants: they must EQUAL the UI2 palette
# master (palette.json), so a palette change drags the css with it or fails.
adw_palette = json.loads(read("artwork/moos-ui2/palette.json"))
for adw_variant, adw_css_rel in (("dark", "system_files/usr/share/moos/gtk/moos-ui2-dark.css"),
                                 ("light", "system_files/usr/share/moos/gtk/moos-ui2-light.css")):
    adw_css = read(adw_css_rel)
    require("managed by moos-theme" in adw_css,
            f"{adw_css_rel} lost its moos-theme marker — the switcher would refuse "
            "to update it and stale colours would stick forever")
    for token, adw_key in (("primary", "accent_bg_color"),
                           ("surface", "window_bg_color"),
                           ("canvas", "view_bg_color"),
                           ("text", "window_fg_color")):
        expected_hex = adw_palette[adw_variant][token]
        require(f"@define-color {adw_key} {expected_hex};" in adw_css,
                f"{adw_css_rel}: {adw_key} does not match palette.json's "
                f"{adw_variant}.{token} ({expected_hex}) — libadwaita apps would "
                "drift from the desktop palette")
adw_switcher = code(read("system_files/usr/bin/moos-theme"))
for adw_needle in ("moos-ui2-dark.css", "moos-ui2-light.css",
                   # gtk.css belongs to Plasma's gtkconfig (it writes the
                   # colors.css import at login, before moos-theme runs) —
                   # MoOS only APPENDS this one import line. Verified live
                   # 2026-07-14: a replace-the-file approach never installed.
                   "@import 'moos-ui2.css';"):
    require(adw_needle in adw_switcher,
            f"moos-theme no longer wires libadwaita css ({adw_needle} missing) — "
            "Flathub apps would fall back to stock Adwaita")
require("xdg-config/gtk-4.0:ro" in read("system_files/usr/share/moos/gtk/overrides/global"),
        "the Flatpak global override no longer grants gtk-4.0 read access — "
        "sandboxed apps cannot see the UI2 css at all")
require("/usr/share/moos/gtk/overrides/global" in
        read("system_files/usr/lib/tmpfiles.d/moos-gtk-overrides.conf"),
        "tmpfiles no longer seeds the Flatpak global override — a fresh machine "
        "never gets the gtk-4.0 read hole")

# Each UI2 half must ship the pointer that reads against ITS canvas — a white
# cursor on Tidal Light's mint was a low-contrast pointer, documented as UI2
# coverage gap 4. No cursor name is this gate's constant: it reads what the
# LNF defaults declare, requires the two halves to DIFFER, and requires the
# switcher and the image build to agree with the defaults.
ui2_cursors = {}
for cursor_variant in ("org.moos.ui2", "org.moos.ui2.light"):
    cursor_match = re.search(
        r"^cursorTheme=(\S+)$",
        read(f"system_files/usr/share/plasma/look-and-feel/{cursor_variant}/contents/defaults"),
        re.MULTILINE)
    require(cursor_match is not None, f"{cursor_variant} defaults name no cursor theme")
    ui2_cursors[cursor_variant] = cursor_match.group(1)
require(ui2_cursors["org.moos.ui2"] != ui2_cursors["org.moos.ui2.light"],
        "both UI2 halves name the same cursor — one canvas gets a low-contrast pointer")
cursor_switcher = code(read("system_files/usr/bin/moos-theme"))
cursor_build = code(read("build_files/build.sh"))
for cursor_name in ui2_cursors.values():
    require(f"cursor={cursor_name}" in cursor_switcher,
            f"moos-theme never selects {cursor_name} — the LNF defaults and the "
            "switcher would fight over the pointer")
    require(f"/usr/share/icons/{cursor_name}" in cursor_build,
            f"build.sh never creates {cursor_name} — the defaults would name a "
            "cursor that does not exist and Plasma would fall back")

ui_wallpaper = ROOT / "system_files/usr/share/wallpapers/MoOSUI2Graphite"
for relative in (
    "metadata.json", "contents/screenshot.png",
    "contents/images/3840x2160.jpg", "contents/images/3440x1440.jpg",
    "contents/images/2560x1600.jpg", "contents/images_dark/3840x2160.jpg",
    "contents/images_dark/3440x1440.jpg", "contents/images_dark/2560x1600.jpg",
):
    require((ui_wallpaper / relative).is_file(), f"missing MoOS wallpaper asset: {relative}")

# The requested visual break from Nova is measurable: the operative pair may not
# retain Nova's cyan/blue focus tokens, and the light canvas may not fall back to
# glaring 255,255,255. Comments are stripped so prose cannot satisfy the gate.
for scheme in ("MoOSUI2Dark", "MoOSUI2Light"):
    palette = code(read(f"system_files/usr/share/color-schemes/{scheme}.colors"))
    require("34,211,238" not in palette and "46,123,255" not in palette,
            f"{scheme} must use the orchid/apricot MoOS UI accents, not Nova cyan/blue")
require("BackgroundNormal=255,255,255" not in
        code(read("system_files/usr/share/color-schemes/MoOSUI2Light.colors")),
        "MoOS UI Light must use warm pearl surfaces, never a pure-white canvas")

# These are the active selectors; comments and package metadata are deliberately
# outside this gate. The EFI shim directory name is also intentionally excluded.
active_selectors = {
    "lock screen": lock_config,
    "look and feel": read("system_files/usr/share/plasma/look-and-feel/org.moos.ui2/contents/defaults"),
}
for surface, text in active_selectors.items():
    require(re.search(r"fedora|bgrt|spinner", text, re.IGNORECASE) is None,
            f"foreign branding selector is active in {surface}")

build = read("build_files/build.sh")
require("plymouth-set-default-theme moos" in build,
        "image build must select MoOS Plymouth")
require("grep -qx 'Theme=moos' /etc/plymouth/plymouthd.conf" in build,
        "image build must fail if the active Plymouth selector is not MoOS")
require("final initramfs contains the Fedora BGRT/spinner branding path" in build,
        "image build must reject Fedora BGRT/spinner paths in initramfs")
require('omit_dracutmodules+=" nfs "' in build and build.count('--omit "nfs"') >= 2,
        "the generic --no-hostonly initramfs must omit dracut's NFS-root module: otherwise "
        "its pre-udev hook starts rpcbind/rpc.statd on every local OSTree boot and logs hard "
        "state-directory errors before switch-root")

# ── The kde-settings profile must name the theme the image actually defaults to ─
#
# /usr/share/kde-settings/kde-profile/default/xdg is the layer AGENTS.md blames for the Breeze
# fallback: Plasma resolved a Global Theme BY NAME out of this cascade, the name no longer
# existed, and it silently persisted Breeze. /etc/xdg outranks it, so a stale value here loses
# every time — right up until the once it doesn't, and then it fails permanently and invisibly.
#
# It named org.moos.nova through both the MoOS UI and MoOS UI2 rollouts, i.e. a family the theme
# switcher cannot even reach. Gate the relationship, not the name: whatever /etc/xdg/kdeglobals
# declares as the default Global Theme, build.sh must repoint this profile at the SAME package.
default_lnf = re.search(r"^LookAndFeelPackage=(\S+)",
                        code(read("system_files/etc/xdg/kdeglobals")), re.MULTILINE)
require(default_lnf is not None,
        "/etc/xdg/kdeglobals declares no default Global Theme")
if default_lnf is not None:
    require(f"LookAndFeelPackage={default_lnf.group(1)}|' \"${{_kde_profile}}/kdeglobals\"" in build,
            f"build.sh must repoint the kde-settings profile at the image's default Global "
            f"Theme ({default_lnf.group(1)}); leaving it on an older family is the exact stale "
            f"name that made Plasma fall back to Breeze and write it down")
    require(f"/usr/share/wallpapers/{lock_wallpaper.group(1)}|' \\" in build
            or f"/usr/share/wallpapers/{lock_wallpaper.group(1)}" in build,
            f"build.sh must repoint the kde-settings profile's lock screen at the wallpaper the "
            f"image actually uses ({lock_wallpaper.group(1)})")

# ── The boot splash must be the same colour as the desktop it boots into ──────
#
# Plymouth is the first surface of MoOS the user ever sees, and it is system-wide: it cannot
# follow a per-user Global Theme, so it has to be pinned in the image by hand — which is exactly
# how it got left behind. It stayed Nova's deep navy (#050A14) with a blue progress bar through
# the entire UI2 rollout, so every boot opened on navy and landed on graphite a second later.
#
# Do not gate a hard-coded hex here: that is what pinned the login screen to NovaHorizon for a
# whole theme family. Read the UI2 palette that the rest of the image is generated from and
# require the splash to agree with it. The splash then cannot drift from the desktop again, and
# a future palette change updates this gate for free.
# The Script theme sets its background from the script (Window.SetBackground*Color),
# not from a .plymouth key. The owner's brief calls for a deep near-black NAVY field
# (not the graphite desktop canvas), so gate the exact navy values so a future edit
# cannot wash the boot out to grey or drift it off the intended navy.
moos_script_src = read("system_files/usr/share/plymouth/themes/moos/moos.script")
require("Window.SetBackgroundTopColor(0.027, 0.043, 0.086)" in moos_script_src,
        "the boot splash's deep-navy top background drifted from #070B16")
require("Window.SetBackgroundBottomColor(0.016, 0.024, 0.039)" in moos_script_src,
        "the boot splash's navy bottom background drifted from #04060A")

# The splash is LOGO-HERO: the crisp mark is centred and the cyan-violet energy
# head ORBITS a ring as the loading indicator. Gate that the script actually
# centres the logo and drives the head around the ring at ring_radius, so a future
# edit cannot bury the mark or freeze the loader.
require("logo_sprite.SetX(cx" in moos_script_src and "logo_sprite.SetY(cy" in moos_script_src,
        "the boot mark must be centred as the hero")
require("head_sprite.SetX(hx" in moos_script_src and "ring_radius" in moos_script_src,
        "the boot loading head must orbit the ring (ring_radius) as the loading indicator")
# Scale to screen height, so it is crisp at 1080p and 4K without stretching.
require("Window.GetHeight(0)" in moos_script_src,
        "the boot splash must size itself from the screen height (crisp at 1080p and 4K)")

# The flicker-free kargs are cosmetic-only and proven on this base; require the
# load-bearing ones so a future edit cannot silently drop the splash or the
# fast-path that took the installed boot from 8 min to 90 s.
#
# Read the WHOLE kargs.d, not one file. plymouth.use-simpledrm moved into its own
# 20-moos-simpledrm.toml so build.sh can withhold it from the NVIDIA edition (where it
# blacked the splash out entirely — see the section above). This gate asked only
# 10-moos-boot-splash.toml, so the move made it fail while the karg still shipped: it was
# pinning a FILE, and what matters is that the generic edition still gets the karg.
boot_kargs = "".join(
    p.read_text(encoding="utf-8")
    for p in sorted((ROOT / "system_files/usr/lib/bootc/kargs.d").glob("*.toml"))
)
for karg in ("rhgb", "quiet", "plymouth.use-simpledrm", "vt.global_cursor_default=0"):
    require(f'"{karg}"' in boot_kargs,
            f"the boot karg {karg!r} is gone — the graphical splash or its "
            "flicker-free handoff would regress")

# The identity firewall must stay wired and stay documented. This is the one gate
# that catches a base-image update or a confused agent re-introducing another OS's
# branding on the finished bytes; an edit that removed its invocation, or the
# IDENTITY CONTRACT that tells an agent not to touch it, is itself a regression.
require((ROOT / "build_files/verify_no_foreign_identity.py").is_file(),
        "the identity firewall script is gone — nothing sweeps the built image "
        "for foreign branding the named-surface gates do not know about")
require("verify_no_foreign_identity.py" in read("build_files/build.sh"),
        "build.sh no longer runs the identity firewall — a foreign logo or name "
        "could reach a user-visible surface with every gate still green")
require("THE IDENTITY CONTRACT" in read("AGENTS.md"),
        "AGENTS.md lost the IDENTITY CONTRACT — the first thing that tells an "
        "agent not to let MoOS boot as another OS")

# ── The lock screen is MoOS's own, and it can still authenticate ──────────────
#
# The lock screen was the last surface still drawn by Plasma's shell default
# (Breeze clock, field and typography). kscreenlocker draws it from the SHELL
# package, NOT the look-and-feel (verified live 2026-07-14: a [Greeter] Theme
# pointing at a look-and-feel silently fell back to this shell default), so MoOS
# overrides the shell's LockScreenUi.qml directly. This is a SECURITY surface:
# the file is a fork that keeps the base's auth path, and the base shell provides
# MainBlock/PasswordSync beside it — this gate makes sure the override stays MoOS
# AND keeps the auth wiring, so it can neither look un-MoOS nor lock a user out.
shell_lock = "system_files/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen"
for lock_file in ("LockScreenUi.qml", "MoOSClock.qml"):
    require((ROOT / shell_lock / lock_file).is_file(),
            f"the shell lockscreen override is missing {lock_file} — the lock "
            "screen would be Plasma's default, not MoOS's")
lock_ui = read(f"{shell_lock}/LockScreenUi.qml")
# The auth path must stay the proven one: it still talks to the authenticator
# and still hands the password to MainBlock.
require("authenticator" in lock_ui,
        "the lock screen override no longer talks to the authenticator — unlock would break")
require("MainBlock" in lock_ui and "onPasswordResult" in lock_ui,
        "the lock screen override lost the MainBlock password path — the password would go nowhere")
# It must be MoOS, not the stock shell UI: the MoOS clock has to be there.
require("MoOSClock" in lock_ui,
        "the lock screen override dropped the MoOS clock — it would read as the Breeze default")
require("MoOSClock" in read(f"{shell_lock}/MoOSClock.qml") or "MoOS" in read(f"{shell_lock}/MoOSClock.qml"),
        "MoOSClock.qml is not the MoOS clock")
# Qt.formatTime has no (date, locale, format-string) overload. With a locale
# slipped in, the "HH"/"mm" formats were IGNORED and the greeter drew the full
# long time — "20:03:56 UTC+00:00" — at display size, twice, clear across the
# lock screen (seen live in the 179 ISO walkthrough). formatDate is fine with
# a locale; formatTime is the one that must stay two-argument.
require(re.search(r"formatTime\s*\([^)]*Qt\.locale", read(f"{shell_lock}/MoOSClock.qml")) is None,
        "MoOSClock.qml calls Qt.formatTime with a locale argument — Qt ignores "
        "the format string and the greeter draws the long UTC time at 7.4x")
# No stale [Greeter] Theme pointing at a look-and-feel (which silently falls back).
require(re.search(r"^Theme=", read("system_files/etc/xdg/kscreenlockerrc"), re.MULTILINE) is None,
        "kscreenlockerrc sets a [Greeter] Theme again — the greeter loads the "
        "SHELL lockscreen, so a look-and-feel Theme there just misleads and "
        "falls back; the override is what draws MoOS")
# The brand and the clock live on different rulers (the brand in gridUnits, the
# clock derived from the userlist geometry), and on a 4K panel the halfway
# formula parked the clock INSIDE the emblem+wordmark (seen live 2026-07-16 via
# kscreenlocker_greet --testing). The floor below the brand is what keeps them
# apart; a rewrite that loses it re-ships the collision on every tall screen.
require(re.search(r"y:\s*Math\.max\(\s*brand\.y\s*\+\s*brand\.height", lock_ui) is not None,
        "the lock screen clock lost its floor below the brand — on a 4K panel "
        "the time draws through the MoOS emblem and wordmark again")
# The auth cluster INSIDE the card (avatar, password field, unlock button) was
# the last stock-Breeze surface — the deferred "auth card". MoOS now overrides
# the shell's lockscreen MainBlock.qml too. It is THE unlock path: this gate
# holds the auth wiring byte-for-byte present so a future restyle can never
# quietly break login. The visual dressing is free to change; these wires are not.
mainblock = read(f"{shell_lock}/MainBlock.qml")
require("SessionManagementScreen" in mainblock,
        "MainBlock.qml is no longer a SessionManagementScreen — it would lose the "
        "user avatar/list and the whole auth screen contract")
for wire, why in (
        (r"signal\s+passwordResult\s*\(\s*string\s+password\s*\)",
         "the passwordResult(string) signal LockScreenUi connects to authenticator.respond"),
        (r"function\s+startLogin\s*\(", "the startLogin() entry point"),
        (r"passwordResult\s*\(\s*password\s*\)", "the passwordResult(password) emit inside startLogin"),
        (r"alias\s+mainPasswordBox\s*:\s*passwordBox", "the mainPasswordBox alias LockScreenUi drives"),
        (r"target:\s*PasswordSync", "the PasswordSync binding that carries the typed secret"),
        (r"onClicked:\s*sessionManager\.startLogin\(\)", "the unlock button wired to startLogin"),
        (r"PlasmaExtras\.PasswordField", "the real password field (secret entry, not a plain TextField)"),
):
    require(re.search(wire, mainblock) is not None,
            f"MoOS MainBlock.qml lost {why} — the lock/login could stop accepting "
            "the password. Restyle the auth card, never rewire it.")
# And it must actually be MoOS, not a copy of the stock file: the auth-safety
# contract banner is the tell that this is the deliberate MoOS fork.
require("AUTH SAFETY CONTRACT" in mainblock,
        "MoOS MainBlock.qml lost its AUTH SAFETY CONTRACT banner — either it "
        "reverted to stock Breeze or someone rewrote it without the guardrails")
# ── The animated brand's light is pre-baked sprites, and they must travel with
#    every QML file that names them. A QML that references images/glow-cyan.png
#    with no sprite beside it fails SILENTLY (Image logs a warning nobody reads
#    and draws nothing) — the brand would quietly lose its glow.
for qml_dir in (Path("system_files/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen"),
                Path("system_files/usr/share/plasma/wallpapers/org.moos.ui2.greeter/contents/ui"),
                *sorted(Path("system_files/usr/share/plasma/look-and-feel").glob("org.moos.ui2*/contents/logout"))):
    for qml in sorted((ROOT / qml_dir).glob("*.qml")):
        body = qml.read_text(encoding="utf-8")
        for sprite in re.findall(r'"(?:\.\./)?images/([a-z-]+\.png)"', body):
            # the greeter plugin's ui/main.qml references ../images/, siblings images/
            base = qml_dir.parent / "images" if "../images/" in body else qml_dir / "images"
            require((ROOT / base / sprite).is_file(),
                    f"{qml.relative_to(ROOT)} references {sprite} but the sprite is not "
                    f"at {base}/ — the animated brand would silently lose its light "
                    "(regenerate with artwork/generate_login_scene.py)")
# ── The same rule for APPS: Mo AI's glass backdrop reads the canonical shared
#    sprites at /usr/share/moos/brand/. An absolute path fails even more
#    silently than a package-relative one (nothing in the app's own tree looks
#    wrong), so every such reference must resolve inside system_files.
for qml in sorted((ROOT / "system_files/usr/share/moos/apps").rglob("*.qml")):
    body = qml.read_text(encoding="utf-8")
    for sprite in re.findall(r'file:///usr/share/moos/brand/([a-z-]+\.png)', body):
        require((ROOT / "system_files/usr/share/moos/brand" / sprite).is_file(),
                f"{qml.relative_to(ROOT)} references /usr/share/moos/brand/{sprite} "
                "but the image does not ship it — the glass backdrop would silently "
                "lose its light (regenerate with artwork/generate_login_scene.py)")
# ── Logout action icons must be the -symbolic glyphs. The buttons recolour their
#    icon with isMask, and the MoOSUI2 theme's full-colour action icons (a filled
#    disc with white detail) mask into a featureless blob — every logout button
#    shipped as a solid circle until 2026-07-16. Symbolic variants are drawn for
#    exactly this. Kirigami falls back to the blob silently, so pin the names.
logout_qml = read("system_files/usr/share/plasma/look-and-feel/org.moos.ui2/contents/logout/Logout.qml")
for icon_name in re.findall(r'iconName:\s*(?:[^"\n]*\?\s*)?"([^"]+)"(?:\s*:\s*"([^"]+)")?', logout_qml):
    for name in filter(None, icon_name):
        require(name.endswith("-symbolic"),
                f"logout button icon {name!r} is not a -symbolic glyph — isMask "
                "turns the theme's full-colour icon into a solid blob")
require('function bilingual(arabic, english)' in logout_qml
        and '"\\u2067" + arabic + "\\u2069"' in logout_qml
        and '"\\u2066" + english + "\\u2069"' in logout_qml,
        "the logout screen must isolate its Arabic and English phrases; without "
        "Unicode bidi isolation RTL moves punctuation and reverses the language order")
require('bilingual("ماذا تريد أن تفعل؟", "What would you like to do?")' in logout_qml,
        "the logout heading bypasses the shared bilingual formatter")

# plasma-login-manager's wallpaper is a separate process. If it is late or
# unavailable, the compiled greeter falls back to a flat colour; the shared user
# delegate must still identify the surface as MoOS and must not regress to the
# cheap generic outline avatar for accounts without a custom photo.
user_delegate = read("system_files/usr/lib64/qt6/qml/org/kde/breeze/components/UserDelegate.qml")
require('source: "file:///usr/share/pixmaps/moos-logo.png"' in user_delegate,
        "the login user delegate lost its MoOS fallback badge")
require("wrapper.name.charAt(0).toUpperCase()" in user_delegate
        and "visible: faceIcon.visible" in user_delegate,
        "accounts without a custom photo must use an intentional initial avatar, "
        "not Plasma's generic outline")

# Every selectable palette is one MoOS UI engine, not another login/session
# design hiding under a different colour name. KDE needs a look-and-feel package
# per palette, but the doorway QML must remain byte-identical across all of them.
lnf_packages = sorted(
    path for path in (ROOT / "system_files/usr/share/plasma/look-and-feel").glob("org.moos.ui2*")
    if path.is_dir()
)
require(len(lnf_packages) >= 2,
        "MoOS must ship at least the matched dark/light UI2 pair")
for doorway in (
    "contents/splash/Splash.qml",
    "contents/logout/Logout.qml",
    "contents/logout/MoOSUI2ActionButton.qml",
):
    variants = {
        (package / doorway).read_bytes()
        for package in lnf_packages
        if (package / doorway).is_file()
    }
    require(
        len(variants) == 1
        and all((package / doorway).is_file() for package in lnf_packages),
        f"{doorway} must be one shared MoOS design across every UI2 palette; "
        "a drifting package creates overlapping/inconsistent session screens",
    )
family_generator = code(read("artwork/generate_moos_themes.py"), "hash")
family_lnf = family_generator.split("def build_lnf(", 1)[1].split("\ndef ", 1)[0]
require('src.suffix == ".svg"' in family_lnf
        and 'src.suffix in (".qml", ".svg")' not in family_lnf
        and "shutil.copy2(src, out)" in family_lnf,
        "the family generator must copy session-screen QML byte-for-byte and "
        "recolour only artwork; otherwise one rebuild forks 16 login/logout designs")

# The installed-disk release gate must make decisions on an ANSI-free serial
# log. systemd colours individual words, so grepping the raw stream previously
# reported failure after the disk had visibly reached Basic System and login.
disk_workflow = read(".github/workflows/build-disk.yml")
require(
    "serial.plain.log" in disk_workflow
    and "ansi = re.compile" in disk_workflow
    and disk_workflow.count("/tmp/serial.plain.log") >= 3,
    "the qcow2 boot gate must strip ANSI once and use the normalised serial log "
    "for both failure and success decisions",
)
require(
    "sddm-greeter" not in code(disk_workflow),
    "the installed-disk gate must not wait for retired SDDM; MoOS uses plasma-login-manager",
)

# ── Arabic in the terminal ────────────────────────────────────────────────────
#
# MoOS brands itself Arabic/English and shipped a terminal an Arabic user could not
# read. A terminal draws one glyph per fixed-width cell; every Arabic font in Fedora
# is proportional, so Konsole tore the cursive joins apart and rendered الطرفية as
# ا ل ط ر ف ي ة — the word shattered into loose letters. JetBrains Mono has no
# Arabic glyphs at all, so fontconfig fell through to a generic Arabic font and the
# result was mush.
#
# Kawkab Mono is drawn to connect ACROSS a fixed advance. It is the only reason
# Arabic in the terminal is legible, and nothing else in this build would notice if
# it went missing — the terminal would simply go back to being unreadable, in a
# language most of the people reviewing this cannot read.
build_code = code(build)
require("/usr/share/fonts/kawkab-mono" in build_code,
        "the image must install Kawkab Mono; without it Arabic in the terminal is unreadable")
require("sha256sum -c -" in build_code,
        "the Kawkab Mono download must be digest-pinned, not fetched blind")

fontconf = code(read("system_files/etc/fonts/conf.d/61-moos-brand.conf"), "xml")
require("<family>Kawkab Mono</family>" in fontconf,
        "fontconfig must actually place Kawkab Mono in the fallback chain")
require(re.search(r"<family>JetBrains Mono</family>\s*<accept>", fontconf) is not None,
        "Konsole asks for JetBrains Mono BY NAME and never resolves the generic monospace "
        "alias, so the Arabic fallback must hang off the NAMED family — a rule written only "
        "on `monospace` never reaches the terminal at all")

# ── A window must know which app it is ────────────────────────────────────────
#
# The stock QML runtime names every window it hosts org.qt-project.qml-qt6, so Plasma
# could not match Mo AI's window to org.moos.moai.desktop and drew the generic green
# Qt diamond in the taskbar instead of the Mo AI orb. Nothing errors when this breaks;
# the app just wears somebody else's icon.
require("-o /usr/bin/moos-qml-shell" in build_code,
        "the image must build the QML host that sets the app_id")
for launcher, app_id in (
    ("system_files/usr/bin/moai", "org.moos.moai"),
    ("system_files/usr/bin/moos-welcome", "org.moos.welcome"),
    ("system_files/usr/bin/moos-store", "org.moos.store"),
):
    text = code(read(launcher))
    require("/usr/bin/moos-qml-shell" in text and f"--app-id {app_id}" in text,
            f"{launcher} must EXEC moos-qml-shell with --app-id {app_id}, or its window "
            f"carries the QML runtime's app_id and the taskbar shows the generic Qt icon")

# ── …and clicking it twice must not give you two of it ────────────────────────
#
# The host had no single-instance guard, and EVERY pure-QML MoOS app runs under it — so this one
# omission opened a second Mo AI, a second Store, a second everything. Measured on the maintainer's
# machine: `moai` three times, three processes, three QML engines, three GPU surfaces, on a card
# the local brain already holds ~6 GB of. Same bug MoPlayer had (NON_UNIQUE), different road.
#
# KDBusService(Unique) rather than a lock file, and the difference is the RAISE: on Wayland a
# process may not pull its own window forward without an XDG activation token, and only the shell
# that launched it can mint one. KDBusService carries the token across; KWindowSystem spends it.
# A lock file would suppress the duplicate and leave the user clicking an icon that does nothing.
shell_src = code(read("build_files/moos-qml-shell.cpp"), "slash")
require("KDBusService service(" in shell_src and "KDBusService::Unique" in shell_src,
        "moos-qml-shell must be single-instance — without it every MoOS QML app opens again on "
        "every click, each with its own QML engine and its own GPU surface")
# …and the guard must not cost the app its ability to START. Strict Unique refuses to run at all
# when there is no session bus, which is exactly the case in the image's own QML smoke-test: every
# MoOS QML app came back exit=1 instead of staying up, and the build went red. A missing bus may
# cost the guard; it may never cost the app.
require("KDBusService::NoExitOnFailure" in shell_src,
        "a missing session bus must disable the single-instance guard, not the application — "
        "without NoExitOnFailure the shell exits rather than opening the app")
require("KDBusService::activateRequested" in shell_src
        and "KWindowSystem::activateWindow" in shell_src,
        "a second launch must RAISE the running window: uniqueness alone turns the second click "
        "into nothing happening, which reads as an app that failed to start")
require("-lKF6DBusAddons" in build_code and "libKF6DBusAddons" in build_code,
        "build.sh must LINK the guard and then verify the link — a silently unlinked binary still "
        "runs, still shows the app, and still opens twice")

# ── A desktop that can show you a picture ─────────────────────────────────────
#
# MoOS shipped no image viewer AT ALL and no default for image/*, so photos opened in
# whatever browser the user installed. A browser's desktop file claims image/png and
# nothing in MoOS contested it.
require(re.search(r"^\s*gwenview \\$", build_code, re.MULTILINE) is not None
        and re.search(r"^\s*haruna \\$", build_code, re.MULTILINE) is not None,
        "the image must actually INSTALL an image viewer and a video player")
mimeapps = code(read("system_files/etc/xdg/mimeapps.list"))
require("image/jpeg=org.kde.gwenview.desktop" in mimeapps
        and "video/mp4=org.kde.haruna.desktop" in mimeapps,
        "MoOS must claim image/* and video/* or a browser will")
# Shipping the default is only half of it: ~/.config/mimeapps.list outranks /etc/xdg,
# and Plasma writes that file the first time anyone picks "Open With" — which every
# existing user already did, in Chrome, because there was nothing else to pick.
require("pin_default_apps()" in apply_theme_code,
        "the image/video defaults must also be pinned into the user's own mimeapps.list; "
        "/etc/xdg alone never reaches a user who already opened a photo in a browser")

# ── The desktop is not empty ──────────────────────────────────────────────────
for asset in (
    "system_files/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/metadata.json",
    "system_files/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui/main.qml",
    "system_files/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui/DashboardBento.qml",
    "system_files/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/config/main.xml",
):
    require((ROOT / asset).is_file(), f"the MoOS scene wallpaper package is missing {asset}")
require("apply_desktop_scene" in apply_theme_code,
        "an installed desktop must receive the MoOS scene through the per-containment repair")
# The dashboard used to be SKIPPED on the live ISO because, as a widget, it landed
# on the "Install MoOS" icon. Inside the wallpaper it renders BELOW the icons, so
# the live session gets the dashboard back — and any live-skip gate would now be
# hiding the scene from the first screen a user ever sees.
require("rd.live.image" not in apply_theme_code,
        "moos-apply-theme must not skip the desktop scene on the live ISO — the bento lives "
        "below the icons now, and the live desktop is where it makes the first impression")
build_script_code = code(read("build_files/build.sh"))
# The bento is deliberately plain QtQuick/Kirigami so the build can genuinely
# LOAD it (a WallpaperItem root only exists inside plasmashell). The smoke hosts
# DashboardBento in a window via moos-qml-shell under a real session bus and
# rejects the live QML diagnostics; the wallpaper wrapper is checked structurally.
require("moos-scene-smoke.qml" in build_script_code
        and "DashboardBento.qml" in build_script_code,
        "the image build must load the scene bento through a real QML host; "
        "a package that only exists on disk is not a package that loads")
normalized_build_script = " ".join(build_script_code.replace("\\", " ").split())
require("dbus-run-session -- /usr/bin/moos-qml-shell --app-id org.moos.scene-smoke" in
        normalized_build_script,
        "the headless scene smoke needs a session bus; without one even KDE's stock "
        "digital clock exits silently and the gate tests the container, not the package")
require('"KPackageStructure": "Plasma/Wallpaper"' in build_script_code,
        "the image build must verify the scene package type — a Plasma/Applet here means "
        "the bento went back to drawing over the icons")
for qml_runtime_failure in ("typeerror", "unable to assign", "binding loop"):
    require(qml_runtime_failure in build_script_code,
            "the scene smoke must reject live QML %s diagnostics; a QML host can "
            "stay alive while one card is blank" % qml_runtime_failure)

# The clock and the rings are ONE applet, and they have to stay one. A desktop
# applet's position lives in a resolution-keyed ItemGeometries string on the
# CONTAINMENT, not on the applet, and the geometry passed to addWidget() is
# transient — so two applets that must sit together drift apart the first time the
# shell restarts, and the second one lands on top of the folder icons.
require("org.moos.nova.sysmon" not in apply_theme_code
        and not (ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.nova.sysmon").exists(),
        "the system rings must live INSIDE the desk clock, not as a second applet — "
        "Plasma does not persist a scripted applet's position, so they will not stay together")

# Every sensor id in a shipped widget must be one that exists. These three were
# INVENTED the first time, and they looked exactly as plausible as the real ones:
# the widget drew an empty box and reported nothing, forever. A monitor showing
# nothing is indistinguishable from a monitor reading zero, which is why nothing
# else in this build would ever have caught it.
#
# Ground truth is `kstatsviewer --list` on real hardware. If a sensor id changes
# upstream, this gate is a stale list too — but a stale list that someone has to
# look at beats a widget that fails silently.
KNOWN_SENSORS = {
    "cpu/all/usage",
    "memory/physical/usedPercent",
    "disk/all/usedPercent",
    "gpu/gpu0/usage",
}
for sensor in re.findall(r'sensorId:\s*"([^"]+)"', dashboard_ui):
    require(sensor in KNOWN_SENSORS,
            f"the desk clock reads sensor '{sensor}', which is not in the verified list "
            f"{sorted(KNOWN_SENSORS)}. Check it against `kstatsviewer --list` — an invented "
            f"sensor id draws an empty ring and never says why")
require(len(re.findall(r'sensorId:\s*"', dashboard_ui)) >= 3,
        "the desk widget must show CPU, memory and Disk")

# Sensors are useless if nothing serves them. ksystemstats was NOT running on this
# image and nothing started it, so every monitor widget drew an empty grey box.
require("systemctl --user start plasma-ksystemstats.service" in apply_theme_code,
        "the sensor daemon must be started explicitly — it does not come up on demand, "
        "and without it every system monitor silently draws nothing")

# ── The tray shows two things, not sixteen ────────────────────────────────────
require('writeConfig("shownItems"' in apply_theme_code
        and "org.kde.plasma.keyboardlayout" in apply_theme_code
        and "org.kde.plasma.volume" in apply_theme_code,
        "the tray must show exactly the keyboard layout and the volume; everything else "
        "belongs behind the collapse arrow")
# …and writing that config is not enough. Plasma 6.7's writeConfig+reloadConfig sets the
# FILE but never rebuilds the running systray's shown/hidden model — verified on 6.7.2, where
# the file said "2 shown" while the tray drew 8 across reboots, and the gate above stayed
# green the whole time. The shell has to be restarted for the collapse to reach the user, and
# it must be guarded by a per-revision marker so it fires once on a THEME_REV bump, not on
# every login. Assert on the CODE (comments stripped), both halves, so neither can rot alone.
require(("restart plasma-plasmashell.service" in apply_theme_code
         or "kquitapp6 plasmashell" in apply_theme_code)
        and "moos-tray-collapsed.v" in apply_theme_code,
        "moos-apply-theme must RESTART plasmashell (guarded once per THEME_REV) after writing "
        "the tray config — in Plasma 6.7 reloadConfig writes the file but the running shell "
        "keeps drawing the full tray, so the collapse is invisible without a restart")
require("xdg-desktop-portal-kde" in apply_theme_code,
        "StatusNotifierItems are matched on their OWN Id, not a plasmoid id — the portal's "
        "remote-control icon and the Xwayland bridge are not plasmoids and survive a "
        "hiddenItems list that only names plasmoids")

# The panel clock must declare its width to the panel layout. implicitWidth alone is
# NOT enough: Plasma lays the panel out from the Layout attached properties, and
# without them it allocated the clock less width than it painted — so the system tray
# was positioned INSIDE the clock's pixels and drew its icons on top of the digits.
# Nothing errored. The panel just looked corrupted.
panel_clock = code(
    read("system_files/usr/share/plasma/plasmoids/org.moos.nova.clock/contents/ui/main.qml"),
    "slash",
)
require("Layout.minimumWidth:" in panel_clock and "Layout.preferredWidth:" in panel_clock,
        "the panel clock must declare Layout.minimumWidth/preferredWidth on its compact "
        "representation. implicitWidth alone is not enough — Plasma lays the panel out from "
        "the Layout attached properties, and without them the system tray is positioned "
        "INSIDE the clock's pixels and draws its icons on top of the digits")

for label, qml_path in (
    ("org.moos.nova.clock",
     "system_files/usr/share/plasma/plasmoids/org.moos.nova.clock/contents/ui/main.qml"),
    ("org.moos.ui2.wallpaper (DashboardBento)",
     "system_files/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui/DashboardBento.qml"),
):
    qml = code(read(qml_path), "slash")
    require("PlasmaCore.Theme" not in qml,
            f"{label}: Plasma 6 has no PlasmaCore.Theme — org.kde.plasma.core exposes Types "
            f"only. Binding a colour to it is undefined at runtime and the surface silently "
            f"draws nothing at all. Use Kirigami.Theme.")

# ── Everything MoOS launches gets a GPU it can actually use ───────────────────
#
# The brain holds ~6 GB of an 8 GB card, and a graphical app started into what is left does
# not fall back to software — it ABORTS on eglMakeCurrent. /usr/bin/moplayer calls
# moos-gpu-headroom, so MoPlayer survives; nothing else did. Mo AI's whole promise is
# "install a camera" ending with the camera ON SCREEN, and it was handing every Flatpak it
# installed to a full graphics card. Both launch paths — the installer's and the
# moos://apps/run route — must ask for headroom first, so gate both.
for launcher in ("moai-do", "moos-open"):
    require("moos-gpu-headroom" in code(read(f"system_files/usr/bin/{launcher}")),
            f"{launcher} must call moos-gpu-headroom before opening an app — with the local "
            f"brain loaded there is not enough VRAM left to make an EGL context, and the app "
            f"aborts instead of degrading")

# ── MoOS's own apps are in MoOS's own dock ────────────────────────────────────
#
# layout.js pins them, and layout.js only runs for a user who has no panel yet — so on the
# maintainer's own machine, months and many green gates later, the dock held moai, browser,
# dolphin, systemsettings, konsole: no MoPlayer, no Mo PC Remote. Gating the template was
# gating the file that does not decide (PROJECT_STATE.md, the shadowed-config trap). The
# thing that decides for an EXISTING user is the reconcile in moos-apply-theme, so gate that.
require('writeConfig("launchers"' in apply_theme_code
        and "org.kde.plasma.icontasks" in apply_theme_code
        and "applications:org.moos.moplayer.desktop" in apply_theme_code
        and "applications:org.moos.remote.desktop" in apply_theme_code,
        "moos-apply-theme must put MoOS's own apps back into an EXISTING user's dock — the "
        "layout template only ever runs for a user who has no panel, so every upgraded user "
        "keeps a dock with no MoPlayer and no Mo PC Remote in it")
# The dock belongs to the user. The reconcile may ADD a missing MoOS app; it may not rewrite
# the dock to the shipped list, or it would silently unpin whatever the user pinned and
# re-pin whatever they deliberately removed — every single upgrade. That property lives in
# one expression, so gate the expression.
require("isMoOS(u) || cur.indexOf(u) >= 0" in apply_theme_code,
        "the dock reconcile must add ONLY MoOS's own apps and otherwise keep the user's "
        "launchers as found — a non-MoOS default the user unpinned must stay unpinned")

# ── The disk does not fill itself ─────────────────────────────────────────────
#
# Three leaks, all measured on the maintainer's machine on 2026-07-13, all with no ceiling:
# 125 GB of dangling podman layers from building this very image, 4.2 GB of core dumps from
# one night of GPU crashes, and a journal growing toward systemd's 10 %-of-disk default
# (~47 GB here). Cleaning them by hand worked and then came straight back — podman was at
# 14 GB reclaimable a day later. A fix the user has to remember is not a fix.
# code(): a systemd drop-in comments with `#`, so an UNSET cap sitting in the prose that
# explains it would satisfy a naive gate — caught exactly that way while writing this one.
journald_cap = code(read("system_files/usr/lib/systemd/journald.conf.d/10-moos-cap.conf"))
require("[Journal]" in journald_cap and "SystemMaxUse=" in journald_cap,
        "the journal must have a ceiling — systemd's default is 10 % of the filesystem, "
        "which is ~47 GB of logs on this machine that nobody will ever read")

coredump_cap = code(read("system_files/usr/lib/systemd/coredump.conf.d/10-moos-cap.conf"))
require("[Coredump]" in coredump_cap and "MaxUse=" in coredump_cap,
        "core dumps must have a ceiling — this machine's GPU sits permanently near the edge, "
        "so crashes recur, and one night of them wrote 4.2 GB of dumps")

reclaim = code(read("system_files/usr/bin/moos-reclaim-disk"))
require("podman image prune" in reclaim,
        "moos-reclaim-disk must prune the dangling layers that every image build leaves behind")
# THE DANGEROUS FLAG. `podman system prune` deletes STOPPED CONTAINERS, and `-a` then deletes
# the images they used. The moplayer-dev distrobox is stopped almost always, and it is the only
# compiler this OSTree machine has — so one "thorough" flag in a weekly automated job silently
# destroys the user's ability to build their own app. Dangling images are unreferenced by
# definition; nothing a container uses can be reached by `image prune`. That is the whole
# safety argument, and this gate is what keeps it true.
require("system prune" not in reclaim
        and " -a" not in reclaim
        and "--all" not in reclaim,
        "moos-reclaim-disk must NEVER use `podman system prune` or -a/--all: system prune "
        "removes stopped containers, and the moplayer-dev distrobox — the only compiler on "
        "this OSTree system — is stopped almost all the time")
require("moos-reclaim-disk.timer" in code(read("build_files/build.sh")),
        "the disk-reclaim timer must be enabled in the image — a maintenance script nobody "
        "starts is the manual cleanup it was written to replace")

# build.yml already invokes this gate directly. Keep the focused visual suite behind
# that existing CI entry instead of adding another workflow step (workflow pushes require
# a separate token scope and have historically been rejected after all local work passed).
ui2_gate = subprocess.run(
    [sys.executable, "-B", str(ROOT / "tests/test_moos_ui2.py")],
    cwd=ROOT,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    check=False,
)
require(ui2_gate.returncode == 0,
        "the focused MoOS UI2 package/art/motion gate failed:\n" + ui2_gate.stdout.strip())


# ── A switch must land on a SIGNED origin ─────────────────────────────────────
#
# `bootc upgrade` keeps the origin it was given; `bootc switch` REPLACES it. Without
# --enforce-container-sigpolicy, switch writes `ostree-unverified-registry:` — and an
# installed MoOS boots `ostree-image-signed:docker://` (the kickstart deploys it that
# way; the install-time end of this contract is gated in verify_image_experience.py).
#
# So `moai-do install-nvidia` — the one action that moves a user between editions —
# silently downgraded a signature-enforcing machine to one that verifies nothing, and
# because the origin persists, EVERY later upgrade stayed unverified for the life of
# the install. It shipped, it ran on the maintainer's machine (journal, 2026-07-16
# 08:05: "Staging image for deployment: ostree-unverified-registry:…/moos-nvidia"),
# and every gate was green: the kickstart it asserts on was still correct, because
# nothing checked the switch the RUNNING system performs.
#
# Comments are stripped first: the fix documents the flag directly above the call, so
# a gate reading raw text would pass on the prose after the flag itself was deleted.
_SWITCH = re.compile(r"bootc\s+switch\b([^\n;|&]*)")
for _tool in sorted((ROOT / "system_files/usr/bin").iterdir()):
    if not _tool.is_file():
        continue
    try:
        _text = _tool.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    for _args in _SWITCH.findall(code(_text)):
        require("--enforce-container-sigpolicy" in _args,
                f"system_files/usr/bin/{_tool.name} runs `bootc switch` without "
                "--enforce-container-sigpolicy. switch REPLACES the origin, so this stages "
                "ostree-unverified-registry: and the machine — and every later upgrade — "
                "stops verifying signatures for the life of the install. "
                f"Offending arguments: `bootc switch{_args.rstrip()}`")


# ── Every action Mo AI PROMISES gets a Run button ─────────────────────────────
#
# Mo AI's systemPrompt tells the model: "put the EXACT command in a fenced code block
# and the app turns it into a one-click Run button". extractRuns()'s regex is what
# actually makes that button, and the two lists were never compared — so the prompt
# offered `moai-do setup-gaming`, `setup-windows` and `install-opencode`, the model
# named them exactly as instructed, and no button appeared. All three were implemented
# in moai-do and routed in moos-open; only the regex was short. The existing route
# gates could not see it: they check moos:// URLs against moos-open's cases, and a
# promise that never becomes a URL has no route to check.
#
# So: every id the prompt hands the model must be matchable by the regex, and every id
# the regex matches must be a real, routed action (the button opens moos://do/<id>).
# `install` is excluded — it takes a Flathub id and goes through moos://apps/install/<id>.
_moai_qml = read("system_files/usr/share/moos/apps/moai/main.qml")
_prompt_start = _moai_qml.index("property string systemPrompt")
_prompt_text = _moai_qml[_prompt_start:_moai_qml.index("function ", _prompt_start)]
_prompt_actions = set(re.findall(r"moai-do ([a-z][a-z0-9-]+)", _prompt_text)) - {"install"}

_re_match = re.search(r"const re = /moai-do\\s\+\((.*?)\)\\b/g", _moai_qml)
require(_re_match is not None,
        "Mo AI's extractRuns() Run-button regex could not be found — if it was renamed or "
        "restructured, update this gate so it keeps comparing the prompt to the buttons")
if _re_match:
    _button_actions = set(_re_match.group(1).split("|"))
    _moai_do_text = read("system_files/usr/bin/moai-do")
    _router_text = read("system_files/usr/bin/moos-open")

    for _act in sorted(_prompt_actions - _button_actions):
        require(False,
                f"Mo AI's system prompt offers `moai-do {_act}` but extractRuns()'s regex does "
                f"not match it, so the model names it exactly as told and NO Run button appears. "
                f"Add '{_act}' to the regex or stop promising it in the prompt.")

    for _act in sorted(_button_actions):
        require(re.search(rf"^\s+{re.escape(_act)}\)\s", _moai_do_text, re.M) is not None,
                f"extractRuns() offers a Run button for `moai-do {_act}`, but moai-do implements "
                f"no such action — the button would run nothing")
        require(route_is_covered(f"do/{_act}", routes_declared(_router_text)),
                f"extractRuns() offers a Run button for `moai-do {_act}`, but moos-open has no "
                f"case for moos://do/{_act} — the button falls through to \"unknown MoOS action\"")

theme_safety_gate = subprocess.run(
    [sys.executable, "-B", str(ROOT / "tests/test_moos_theme_safety.py")],
    cwd=ROOT,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    check=False,
)
require(theme_safety_gate.returncode == 0,
        "the MoOS rollback/automatic-theme safety gate failed:\n"
        + theme_safety_gate.stdout.strip())

# ── The installer's status pipeline: three parties, ONE path ─────────────────
# moos-open (the writer), the moos-installer launcher (which hands the QML its
# --cache dir) and the QML poller must agree on the status file, or the wizard
# calls a SUCCEEDING install "stalled" — which is exactly what shipped: the
# launcher's --cache already IS ~/.cache/moos-installer, and the QML appended
# another "/moos-installer", polling a path no one writes. Found the first time
# the wizard was driven end-to-end (QEMU, 2026-07-16). Gate the relationship.
inst_launcher = code(read("system_files/usr/bin/moos-installer"), "hash")
inst_qml = code(read("system_files/usr/share/moos/apps/installer/main.qml"), "slash")
inst_open = code(read("system_files/usr/bin/moos-open"), "hash")
require('CACHEDIR="${CACHE}/moos-installer"' in inst_launcher
        and '--cache="$CACHEDIR"' in inst_launcher,
        "moos-installer must pass its private ~/.cache/moos-installer dir as --cache")
require('win.cacheDir + "/install.status"' in inst_qml,
        "the installer QML must poll <cacheDir>/install.status — cacheDir already "
        "IS the private moos-installer dir")
require('cacheDir + "/moos-installer/' not in inst_qml,
        "the installer QML must not re-append /moos-installer to cacheDir — that "
        "polls a path nobody writes and reports a succeeding install as stalled")
require('${_idir}/install.status' in inst_open
        and '/moos-installer"' in inst_open,
        "moos-open must hand the helper the same ~/.cache/moos-installer/install.status")

# ── The keyboard the session actually compiles ───────────────────────────────
# KWin (Wayland) takes its keymap from systemd-localed (locale1), NOT from the
# shipped kxkbrc: on the live ISO the panel said "DE" while typing was
# English (US), because nothing shipped localed's two sources. Proven in QEMU
# (2026-07-16): populating localed flipped the live session to German
# instantly. So the image must ship BOTH files, and they must agree with
# kxkbrc — gate the relationship, not a constant.
kxkbrc = code(read("system_files/etc/xdg/kxkbrc"), "hash")
layout_list = next((ln.split("=", 1)[1].strip() for ln in kxkbrc.splitlines()
                    if ln.strip().startswith("LayoutList=")), "")
require(layout_list != "", "kxkbrc must declare a LayoutList")
xorg_kbd = code(read("system_files/etc/X11/xorg.conf.d/00-keyboard.conf"), "hash")
require(f'Option "XkbLayout" "{layout_list}"' in xorg_kbd,
        f"00-keyboard.conf must ship XkbLayout \"{layout_list}\" — the same list "
        "kxkbrc declares, because KWin compiles what locale1 answers")
vconsole = code(read("system_files/etc/vconsole.conf"), "hash")
first_layout = layout_list.split(",")[0]
require(f"KEYMAP={first_layout}" in vconsole,
        f"vconsole.conf must ship KEYMAP={first_layout} (the primary kxkbrc layout, "
        "same derivation the installer uses)")

# ── ONE visible store, whatever scope Bazaar lands in ────────────────────────
# Bazaar (Mo Store's full-catalog engine) can be installed per-user (by
# moos-store-browse) or system-wide (by moos-setup's checklist). The launcher
# hide that only edited the per-user flatpak export shipped a machine showing
# TWO stores the day Bazaar arrived system-scope. The fix is one shared helper
# that writes a NoDisplay override into the user's own applications dir — the
# single location that outranks BOTH flatpak export scopes. Gate the
# relationship: every installer of Bazaar must route through that helper, and
# the helper must target the winning directory.
one_store = code(read("system_files/usr/bin/moos-one-store"), "hash")
require("/.local/share}/applications" in one_store,
        "moos-one-store must write its override under ~/.local/share/applications "
        "(the only dir that outranks both flatpak export scopes)")
require("NoDisplay=true" in one_store,
        "moos-one-store must set NoDisplay=true on the Bazaar override")
require("flatpak/exports" not in one_store,
        "moos-one-store must not edit flatpak export files — a Bazaar update regenerates them")
for installer_of_bazaar in ("moos-store-browse", "moos-setup"):
    text = code(read(f"system_files/usr/bin/{installer_of_bazaar}"), "hash")
    require("moos-one-store" in text,
            f"{installer_of_bazaar} can install Bazaar, so it must call moos-one-store "
            "to keep Mo Store the single visible storefront")

# ── Re-sizing zram must never storm the swap unit ─────────────────────────────
# On a fresh install's FIRST boot, moos-hardware-adapt re-tiers zram for the
# machine's RAM and re-applies it. A bare `systemctl restart
# systemd-zram-setup@zram0` right after boot stops the just-started
# dev-zram0.swap and re-starts it inside systemd's start-rate window: the swap
# unit trips start-limit-hit, every later setup retry dies with EBUSY writing
# comp_algorithm (the device is already sized), and the install's first boot
# ends with TWO failed units and swap OFF. Reproduced end-to-end in QEMU
# (2026-07-17, ISO 44.20260717.190) and invisible to every existing gate — the
# machine still boots, it is just silently degraded and selfcheck-red.
#
# The contract, on the comment-stripped script:
#   1. no bare `systemctl restart` of the zram stack, ever;
#   2. a config-equality skip, so an ordinary boot never touches a working swap;
#   3. the one legitimate apply uses stop → daemon-reload → reset-failed →
#      ONE start of dev-zram0.swap, in that order (reset-failed clears the
#      start-limit counters; the single start pulls setup in via Requires=).
_hw = code(read("system_files/usr/libexec/moos-hardware-adapt"), "hash")
require(re.search(r"systemctl\s+restart\s+\S*systemd-zram-setup", _hw) is None,
        "moos-hardware-adapt must not `systemctl restart systemd-zram-setup@…` — "
        "that storms dev-zram0.swap into start-limit-hit on a fresh install's first "
        "boot and leaves the machine with failed units and no swap")
require('= "$zwant"' in _hw or "= \"$(cat" in _hw or '"$zwant" ]' in _hw,
        "moos-hardware-adapt must compare the zram config it would write with what "
        "is already on disk and skip the apply when identical — an ordinary boot "
        "must never stop a working swap")
_i_stop = _hw.find("systemctl stop dev-zram0.swap")
_i_reload = _hw.find("systemctl daemon-reload")
_i_reset = _hw.find("systemctl reset-failed dev-zram0.swap")
_i_start = _hw.find("systemctl start dev-zram0.swap")
require(-1 < _i_stop < _i_reload < _i_reset < _i_start,
        "moos-hardware-adapt's zram apply must be exactly: stop dev-zram0.swap → "
        "daemon-reload → reset-failed dev-zram0.swap → start dev-zram0.swap. "
        "reset-failed must come after the stop (it clears the start-limit counters "
        "the stop/start cycle charged) and before the single start request")

# ── A transient zram-setup failure must not look permanent on a fresh install ──
# Round-190 (QEMU) finding: one transient boot-time failure of
# systemd-zram-setup@zram0 left the device sized (disksize set, mkswap done), so
# every retry then died EBUSY writing comp_algorithm and the first boot ended
# with no swap. The fix is a template drop-in whose ExecStartPre resets the zram
# device before each (re)start — guarded so it SKIPS an active swap and no-ops on
# a healthy first boot. Hold both halves: the reset, and the /proc/swaps guard
# that keeps it from ever touching live swap.
_zram_drop = "system_files/usr/lib/systemd/system/systemd-zram-setup@.service.d/10-moos-reset-on-retry.conf"
require((ROOT / _zram_drop).is_file(),
        "the zram reset-on-retry drop-in is missing — one transient zram-setup "
        "failure on a fresh install's first boot would leave the device wedged "
        "(EBUSY on every retry) and the install would boot with no swap")
_zd = read(_zram_drop)
require(re.search(r"ExecStartPre=.*/sys/block/%i/reset", _zd) is not None,
        "the zram drop-in must reset /sys/block/%i/reset in ExecStartPre so a "
        "retry-after-transient-failure starts from a clean, re-configurable device")
require("/proc/swaps" in _zd,
        "the zram drop-in must guard on /proc/swaps — it must never reset a zram "
        "device that is currently an ACTIVE swap")
require(re.search(r"ExecStartPre=-", _zd) is not None,
        "the zram drop-in's ExecStartPre must be prefixed '-' (failure-tolerant) "
        "so a guard miss can never block the device from being set up")

# ── The live session must not lock itself mid-install ────────────────────────
# The live ISO's KDE session kept the stock 5-minute autolock, so the screen
# LOCKED over a running install (QEMU walkthrough of 44.20260717.190: "Copying
# MoOS — 86%" behind a lock screen). liveuser has no password, so that lock
# protects nothing and reads as a hang on a machine the user does not trust yet.
# The fix is moos-live-polish; its safety story is the kernel-cmdline condition,
# so the gate holds BOTH halves: it must fire on live boots only, before the
# session that reads its config exists, and it must write the live USER's
# config, never a system-wide path an installed machine would inherit.
# Only EFFECTIVE lines count — a commented-out Condition= would pass a raw
# substring check while systemd ignores it (this gate was broken-once to prove
# exactly that, and the naive version stayed green).
_lp_unit = "\n".join(
    line for line in
    read("system_files/usr/lib/systemd/system/moos-live-polish.service").splitlines()
    if not line.lstrip().startswith(("#", ";")))
require("ConditionKernelCommandLine=rd.live.image" in _lp_unit,
        "moos-live-polish.service must be gated on ConditionKernelCommandLine="
        "rd.live.image — without it an INSTALLED MoOS loses its lock screen")
require("Before=display-manager.service" in _lp_unit,
        "moos-live-polish.service must run Before=display-manager.service — the "
        "live session reads kscreenlockerrc once, at session start")
require("After=livesys.service" in _lp_unit,
        "moos-live-polish.service must order After=livesys.service — livesys "
        "creates the live user whose home it writes into")
_lp = code(read("system_files/usr/libexec/moos-live-polish"), "hash")
require("Autolock=false" in _lp and "LockOnResume=false" in _lp,
        "moos-live-polish must write Autolock=false and LockOnResume=false into "
        "the live user's kscreenlockerrc")
require("/etc/xdg" not in _lp,
        "moos-live-polish must never write /etc/xdg — that would disable the lock "
        "screen on installed systems too")
require("getent passwd" in _lp,
        "moos-live-polish must resolve the live user via getent and no-op when "
        "absent — the unit alone cannot prove livesys ran")
require(re.search(r"systemctl enable moos-live-polish\.service", read("build_files/build.sh")),
        "build.sh must enable moos-live-polish.service or the fix ships dormant")

# ─────────────────────────────────────────────────────────────────────────────
# Gates for the 2026-07-18 audit fixes. Each guards a RELATIONSHIP a shipped
# regression would break, comment-stripped so prose cannot satisfy it.
# ─────────────────────────────────────────────────────────────────────────────

# #1 Passwordless-root shortcuts must not ship at all — not as an active rule
#    and not as a helper that can create one later.
require(not (ROOT / "system_files/usr/share/polkit-1/rules.d/50-moos-devmode.rules").exists(),
        "the dev-mode passwordless-root polkit rule must not ship in the image")
require(not (ROOT / "system_files/usr/bin/moos-devmode-enable").exists(),
        "the image must not ship a helper that creates broad passwordless admin rules")

# #10/#20 The desktop dashboard clock: 24-hour digits with NO AM/PM meridiem, and
#         its second date line pinned to English (the ar+en pair every clock uses).
_clock = code(read("system_files/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui/ClockCard.qml"), "slash")
require('"AP"' not in _clock,
        "the dashboard clock must not pair an AM/PM meridiem with 24-hour digits")
require('Qt.locale("en")' in _clock,
        "the dashboard clock's secondary date line must be pinned to English")
require(re.search(r"RowLayout\s*\{[^}]*LayoutMirroring\.enabled:\s*false"
                  r"[^}]*LayoutMirroring\.childrenInherit:\s*true"
                  r"[^}]*layoutDirection:\s*Qt\.LeftToRight",
                  _clock, re.DOTALL) is not None,
        "the dashboard HH:mm row must reject inherited RTL mirroring")

# #9 The UI font is requested BY NAME everywhere, so the Arabic fallback must hang
#    off the NAMED family (a sans-serif prefer never reaches a by-name request).
_font = code(read("system_files/etc/fonts/conf.d/61-moos-brand.conf"), "xml")
require(re.search(r"<family>IBM Plex Sans</family>\s*<accept>", _font) is not None,
        "IBM Plex Sans must carry a by-name <accept> fallback to IBM Plex Sans Arabic")

# #3/#7 moos-open: disruptive drive-by-triggerable routes must route through a
#       confirmation before acting.
_open = code(read("system_files/usr/bin/moos-open"), "hash")
def _arm(text: str, label: str) -> str:
    m = re.search(re.escape(label) + r"(.*?);;", text, re.DOTALL)
    return m.group(1) if m else ""
for _label in ("remote/start)", "installer/reboot)", "installer/poweroff)",
               "session/logout)", "session/power)"):
    require("confirm" in _arm(_open, _label),
            f"moos-open {_label} must confirm before acting (drive-by moos:// safety)")

# #18 do_setup_waydroid must free VRAM before starting the Android (EGL) UI.
_moaido = code(read("system_files/usr/bin/moai-do"), "hash")
_ws = _moaido.find("waydroid session start")
require(_ws > 0 and "moos-gpu-headroom" in _moaido[max(0, _ws - 400):_ws],
        "do_setup_waydroid must call moos-gpu-headroom before 'waydroid session start'")

# #16 moos-firstboot must not stamp completion when the account was not created.
_fb = code(read("system_files/usr/libexec/moos-firstboot"), "hash")
require('id "$USERNAME"' in _fb and "NOT stamping" in _fb,
        "moos-firstboot must not stamp a userless install; it must retry next boot")
require("account recipe has no password hash" in _fb,
        "moos-firstboot must reject a missing password hash instead of creating an insecure account")
require("NOPASSWD" not in _fb and "49-moos-passwordless.rules" not in _fb,
        "moos-firstboot must never create passwordless sudo/polkit access")
require("sddm" not in _fb.lower(),
        "moos-firstboot must not recreate a retired SDDM login stack")
require("autologin" not in _fb.lower() and "plasmalogin.conf.d" not in _fb,
        "installed MoOS must always show the password greeter; moos-firstboot "
        "must not create an automatic-sign-in configuration")
_fb_unit = code(read("system_files/usr/lib/systemd/system/moos-firstboot.service"), "hash")
require("sddm" not in _fb_unit.lower(),
        "moos-firstboot.service still orders against retired SDDM")

# #25 moos-hardware-adapt must APPLY the sysctl it writes (daemon-reload does not).
_hw = code(read("system_files/usr/libexec/moos-hardware-adapt"), "hash")
require(re.search(r"90-moos-hardware\.conf.*?sysctl --system", _hw, re.DOTALL) is not None,
        "moos-hardware-adapt must run `sysctl --system` after writing 90-moos-hardware.conf")

# #8 Fast Remote must restore the CAPTURED layout on off, not a hard-coded country.
_fr = code(read("system_files/usr/bin/moos-fast-remote"), "hash")
require("set_layout de" not in _fr,
        "Fast Remote off must not restore a hard-coded 'de' layout")
require("prevlayout" in _fr and "set_layout_idx" in _fr,
        "Fast Remote must save the active layout on and restore it on off")

# #19 Every Windows/foreign type runforeign claims must have a default handler.
_mime = read("system_files/etc/xdg/mimeapps.list")
for _t in ("application/x-ms-shortcut", "application/x-wine-extension-msp"):
    require(f"{_t}=org.moos.runforeign.desktop" in _mime,
            f"{_t} must default to org.moos.runforeign.desktop")

# #5/#11/#22 The install helper: single-instance lock, network-wait heartbeat, and
#            a hard fail (not a silent passwordless downgrade) when hashing fails.
_i2d = code(read("system_files/usr/bin/moos-install-to-disk"), "hash")
require("flock -n 9" in _i2d,
        "moos-install-to-disk must hold an flock so a re-fired begin cannot double-wipe")
require('fail "hash-failed"' in _i2d,
        "a chosen password that cannot be hashed must fail, not become passwordless")
require('fail "password-required"' in _i2d and '${#R_PASS}' in _i2d,
        "moos-install-to-disk must reject a missing/short password in the privileged backend")
require('fail "seed-failed"' in _i2d,
        "the installer must not report success when the target account recipe could not be saved")
require("/usr/lib/systemd/systemd-update-done --root=" in _i2d
        and '.updated' in _i2d,
        "the installer must mark the deployed /etc caches current; otherwise "
        "ldconfig performs a long cold rebuild before the first password greeter")
_iqml = read("system_files/usr/share/moos/apps/installer/main.qml")
require("acctPass.length >= 8" in _iqml,
        "the account page must require a password")
require("acctAutologin" not in _iqml and "autologin:" not in _iqml.lower(),
        "the installer must not expose or write an automatic-sign-in choice")
require("AUTOLOGIN=" not in _i2d,
        "the privileged installer backend must not seed an automatic-sign-in value")
_login_dropins = "\n".join(
    p.read_text(encoding="utf-8")
    for p in (ROOT / "system_files/usr/lib/plasmalogin/plasmalogin.conf.d").glob("*.conf")
)
require(re.search(r"^\s*\[Autologin\]\s*$", _login_dropins, re.MULTILINE) is None,
        "the shipped plasma-login-manager configuration must not enable automatic sign-in")
for _installer_failure in ("password-required", "hash-failed", "seed-failed"):
    require(f'case "{_installer_failure}"' in _iqml,
            f"the installer has no actionable UI message for {_installer_failure}")
_m = re.search(r"instPoll\.miss\s*>\s*(\d+)", _iqml)
require(_m is not None and int(_m.group(1)) >= 150,
        "installer stall threshold must exceed the online ensure_network worst case")

# The published qcow2 is a downloadable disk, so it must never contain a
# repository-known credential. CI substitutes a random value in a private temp file.
_bib = read("bib/config.toml")
require("__MOOS_CI_RANDOM_PASSWORD__" in _bib and "moostest2026" not in _bib,
        "bib/config.toml must contain only the CI-random password placeholder")
require("openssl rand -hex" in disk_workflow
        and "/tmp/moos-bib-config.toml:/config.toml:ro" in disk_workflow,
        "build-disk.yml must inject a fresh private password before publishing qcow2")

# Welcome is the one live-session landing surface, hands off to the unique
# installer without leaving two wizard windows stacked, and returns once on the
# first password-authenticated login of the installed account. Its app choices
# must drive the same catalogued install/status contract as Mo Store.
_welcome = read("system_files/usr/share/moos/apps/welcome/main.qml")
_welcome_launch = code(read("system_files/usr/bin/moos-welcome"), "hash")
_firstrun = code(read("system_files/usr/bin/moos-firstrun"), "hash")
_firstrun_desktop = read("system_files/etc/xdg/autostart/org.moos.firstrun.desktop")
require("--live=\"$LIVE\"" in _welcome_launch and "rd.live.image" in _welcome_launch,
        "moos-welcome must tell the QML whether it runs from the live image")
require("moos://installer/open" in _welcome and "handoffToInstaller" in _welcome
        and "onTriggered: Qt.quit()" in _welcome,
        "the live Welcome must hand off to the installer and close instead of "
        "leaving two onboarding windows layered")
require("Object.keys(win.picks)" in _welcome
        and "moos://store/install/" in _welcome
        and 'ln === "DONE"' in _welcome and 'ln.indexOf("FAIL")' in _welcome,
        "Welcome selections must execute the real Mo Store install route and "
        "surface both success and failure")
require("Exec=/usr/bin/moos-firstrun" in _firstrun_desktop
        and "moos-firstrun-done" in _firstrun and "moos-welcome && exit 0" in _firstrun,
        "the installed account must receive the MoOS Welcome exactly once on first login")

# Confirmation dialogs must render one locale, not a mixed RTL/LTR sentence.
# The latter visibly moves the question mark and swaps the clauses in kdialog.
_open_router = code(read("system_files/usr/bin/moos-open"), "hash")
require("localized_message" in _open_router
        and 'message="$(localized_message "${1:-}")"' in _open_router,
        "moos-open confirmations must choose one localized message before opening the dialog")
require('--warningyesno "$message"' in _open_router
        and '--warningyesno "$1"' not in _open_router,
        "kdialog must receive the locale-selected confirmation, never the raw RTL/LTR pair")

# Fedora's legacy mcelog unit exits failed on AMD and explicitly asks for
# rasdaemon. Ship one cross-vendor RAS owner and lock the build contract in.
_build = code(read("build_files/build.sh"), "hash")
require("dnf5 -y install rasdaemon" in _build
        and "systemctl enable rasdaemon.service" in _build,
        "the image must install and enable Fedora's cross-vendor rasdaemon")
require("systemctl mask mcelog.service" in _build,
        "the AMD-incompatible mcelog unit must be masked to avoid a failed boot unit")

# A slow DRM driver can outlive udevadm settle. Starting the login KWin before
# /dev/dri/card* exists leaves the manager active but the greeter permanently
# black, so the manager owns one bounded, card-number-agnostic preflight.
_drm_wait = code(read("system_files/usr/libexec/moos-wait-drm"), "hash")
_login_drm_dropin = code(
    read("system_files/usr/lib/systemd/system/plasmalogin.service.d/10-moos-wait-drm.conf"),
    "hash",
)
require('"$drm_dir"/card*' in _drm_wait and 'i=$((i + 1))' in _drm_wait,
        "the login DRM preflight must wait for any card number with a bounded loop")
require("MOOS_DRM_WAIT_STEPS" in _drm_wait and "exit 1" in _drm_wait,
        "the login DRM preflight needs a testable hard timeout, not an infinite boot wait")
require("ExecStartPre=/usr/libexec/moos-wait-drm" in _login_drm_dropin,
        "plasmalogin.service must run the DRM preflight before starting KWin")
require("chmod 0755 /usr/libexec/moos-wait-drm" in _build,
        "build.sh must make the login DRM preflight executable")

# bootc/OSTree owns these root paths as symlinks into persistent /var. Generic
# home.conf/provision.conf directory rules otherwise emit three errors on every
# boot. Scrub only those exact top-level rules and fail loudly if upstream moves
# them; never mask either whole vendor file and lose unrelated provisioning.
require(
    'home_tmpfiles="/usr/lib/tmpfiles.d/home.conf"' in _build
    and 'provision_tmpfiles="/usr/lib/tmpfiles.d/provision.conf"' in _build,
    "the build must target the two vendor tmpfiles files that conflict with OSTree",
)
require(
    "_tmpfiles" in _build
    and "/(home|srv)" in _build
    and "/root" in _build
    and "conflicting /home or /srv tmpfiles rule survived" in _build
    and "conflicting /root tmpfiles rule survived" in _build,
    "the build must remove and verify all three conflicting top-level rules",
)

# Retired SDDM/org.moos.nova generators used to recreate a second login/theme
# stack even after runtime files were removed.
_legacy_art = code(read("artwork/generate_nova_visuals.py"), "hash")
require("generate_sddm" not in _legacy_art and "--sddm" not in _legacy_art,
        "the legacy artwork generator can still recreate the retired SDDM stack")
require("org.moos.nova" not in _legacy_art and "--previews" not in _legacy_art,
        "the legacy artwork generator can still recreate the retired Nova look-and-feel")

# #2/#6 The ISO build must embed the image into the live containers-storage for
#       OFFLINE install AND verify it (fail-loud), not assume Titanoboa did it.
_isoyml = read(".github/workflows/build-iso.yml")
require("containers-storage:[overlay@" in _isoyml and "image exists" in _isoyml,
        "build-iso.yml must embed the MoOS image into the live ISO's containers-storage and verify it")
require(
    'offline_ref="$(sudo tr -d' in _isoyml
    and '${rootfs}/usr/lib/moos/install-imageref' in _isoyml
    and ']${offline_ref}"' in _isoyml
    and 'image exists "${offline_ref}"' in _isoyml,
    "digest-pinned ISO builds must alias the source to the exact tagged ref the offline installer requests",
)

# Qt 6.11 deprecates Qt.btoa(string) in favour of an array-like overload, but
# QML's JavaScript host is not a browser and does not expose TextEncoder. These
# glyph helpers only build ASCII SVG, so Array.from(svg) is both documented and
# sufficient; a browser-only encoder would make every generated icon disappear.
for _glyph_qml in (
    "system_files/usr/share/moos/apps/installer/main.qml",
    "system_files/usr/share/moos/apps/store/main.qml",
    "system_files/usr/share/moos/apps/welcome/main.qml",
):
    _glyph_text = code(read(_glyph_qml), "slash")
    require("TextEncoder" not in _glyph_text,
            f"{_glyph_qml} must not use browser-only TextEncoder in QML")
    require("Qt.btoa(Array.from(svg))" in _glyph_text,
            f"{_glyph_qml} must use Qt 6.11's array-like btoa overload for SVG glyphs")

# #14 CI must verify the signature against the SAME public key the OS enforces.
# (The theme-safety and UI2 gates already run transitively via this file's own
# subprocess invocations above, so they are wired — no separate build.yml entry.)
_byml = read(".github/workflows/build.yml")
require("cosign verify --key cosign.pub" in _byml,
        "build.yml must verify the signature against the OS-enforced public key")

if errors:
    print("MoOS user-experience gate failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print("MoOS user-experience gate passed")
