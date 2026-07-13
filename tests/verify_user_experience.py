#!/usr/bin/env python3
"""Static gates for the active MoOS login/desktop experience."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


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
require("xdg-open" not in remote_desktop and "http://" not in remote_desktop,
        "Mo PC Remote launcher must never open an external browser")
native_remote = read("system_files/usr/bin/mo-pc-remote")
require("Gtk.Application" in native_remote,
        "Mo PC Remote control center must be a native GTK application")
require('UNIT = "mo-remote-personal.service"' in native_remote,
        "Mo PC Remote must manage the MoPC backend")

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
require("sudo waydroid init" not in moai_qml,
        "Mo AI must use the confirmed workflow, not copy sudo commands")
require('moos://do/setup-gaming' in moai_qml,
        "Mo AI's Compatibility panel must expose the focused gaming installer")
require('moos://do/setup-waydroid' in moai_qml,
        "Mo AI's Compatibility panel must expose the Android (Waydroid) setup")

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

# The versioned migration is what makes the redesign visible to existing users.
apply_theme = read("system_files/usr/bin/moos-apply-theme")
require("THEME_REV=9" in apply_theme, "Nova visual schema must be revision 9")

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
require("defuse_automatic_lookandfeel" in apply_theme,
        "moos-apply-theme must disarm Plasma's automatic look-and-feel switch")
require("current_lookandfeel" in apply_theme and "SELF-HEAL" in apply_theme,
        "moos-apply-theme must re-apply when the desktop is no longer wearing Nova")

xdg_kdeglobals = read("system_files/etc/xdg/kdeglobals")
require("AutomaticLookAndFeel=false" in xdg_kdeglobals,
        "MoOS ships one Look and Feel; Plasma's day/night switch can only swap Nova out")

ui_migrate = read("system_files/usr/bin/moos-ui-migrate")
require("MOOS_THEME_REV=7" in ui_migrate and "MOAI_UI_REV=3" in ui_migrate,
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

# Windows must wear the Nova decoration, not Breeze. Breeze here means Breeze's
# X / v / ^ title-bar glyphs on every window — the loudest remaining "this is
# stock KDE" tell after the dock.
kwinrc = read("system_files/etc/xdg/kwinrc")
require("library=org.kde.kwin.aurorae" in kwinrc,
        "KWin must load the Aurorae engine, not Breeze")
require("theme=__aurorae__svg__MoOSNova" in kwinrc,
        "KWin must use the MoOS Nova decoration; the __aurorae__svg__ prefix is "
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
lnf_defaults = read("system_files/usr/share/plasma/look-and-feel/org.moos.nova/contents/defaults")
require("[kwinrc][org.kde.kdecoration2]" in lnf_defaults
        and "theme=__aurorae__svg__MoOSNova" in lnf_defaults,
        "org.moos.nova's defaults must declare the window decoration, or Breeze's entry "
        "in ~/.config/kdedefaults/kwinrc permanently shadows /etc/xdg/kwinrc")
require("--group org.kde.kdecoration2 --key theme __aurorae__svg__MoOSNova" in apply_theme,
        "the theme migration must pin the Nova decoration into an existing user's own "
        "kwinrc; a system default cannot reach past kdedefaults")

# Same trap, third instance: [Sounds] is not in the entry set LookAndFeelManager applies,
# so a user carrying Theme=freedesktop from the defaults they were created under keeps it,
# and the MoOS sound theme ships without ever playing.
require("--group Sounds --key Theme moos-nova" in apply_theme,
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
require("--key gtk-sound-theme-name moos-nova" in apply_theme,
        "GTK's sound theme must be pinned too; gtkconfig syncs icons and cursors from "
        "kdeglobals but never [Sounds]")

aurorae = ROOT / "system_files/usr/share/aurorae/themes/MoOSNova"
for name in ("decoration.svg", "close.svg", "minimize.svg", "maximize.svg",
             "restore.svg", "MoOSNovarc"):
    require((aurorae / name).is_file(),
            f"the Nova decoration must ship {name}")

# The shadow is the theme's own job — Aurorae paints the decoration SVG across
# its Padding* region, and a decoration with no padding has no drop shadow, which
# lands windows flat on the wallpaper and looks WORSE than the Breeze it
# replaced. Guard the padding so a future edit cannot quietly delete the shadow.
themerc = read("system_files/usr/share/aurorae/themes/MoOSNova/MoOSNovarc")
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
widgets = ROOT / "system_files/usr/share/plasma/desktoptheme/Nova/widgets"
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
nova_theme = ROOT / "system_files/usr/share/plasma/desktoptheme/Nova"
for relative in kickoff_surfaces:
    path = nova_theme / relative
    require(path.is_file(), f"Nova Kickoff surface must exist: {relative}")
    if path.is_file():
        require("stroke" not in path.read_text(encoding="utf-8"),
                f"{relative} must remain fill-only for FrameSvg geometry")

# The dock has to actually leave the screen edge, or none of the rounded glass
# reads as floating.
layout = read("system_files/usr/share/plasma/layout-templates/"
              "org.kde.plasma.desktop.defaultPanel/contents/layout.js")
require("panel.floating = true" in layout, "the MoOS dock must float")
require('addWidget("org.kde.plasma.kickoff")' in layout,
        "MoOS must preserve the integrated Kickoff launcher")
require("org.moos.nova.launcher" not in layout,
        "MoOS must not ship a competing launcher in the panel")
require('addWidget("org.moos.nova.clock")' in layout,
        "new users must receive the compact Nova clock")
for package in ("org.moos.nova.clock",):
    root = ROOT / "system_files/usr/share/plasma/plasmoids" / package
    require((root / "metadata.json").is_file() and
            (root / "contents/ui/main.qml").is_file(),
            f"missing complete Plasma package: {package}")
require("try {" in layout,
        "the floating setter must be guarded -- a throw in the layout template "
        "leaves the session with NO panel")
require("NovaHorizonII/contents/images_dark/3840x2160.png" in apply_theme,
        "Existing users must migrate to Nova Horizon II")

lock_config = read("system_files/etc/xdg/kscreenlockerrc")
require("Image=/usr/share/wallpapers/NovaHorizonII" in lock_config,
        "Plasma lock screen must use Nova Horizon II")

sddm = read("system_files/etc/sddm.conf.d/moos.conf")
require(re.search(r"^Current=moos-nova$", sddm, re.MULTILINE) is not None,
        "SDDM must select the MoOS Nova theme")
sddm_preset = read("system_files/usr/share/sddm/themes/moos-nova/configs/moos-nova.conf")
require(sddm_preset.count('background = "nova-horizon-ii.png"') == 2,
        "SDDM idle and login screens must share Nova Horizon II")

wallpaper = ROOT / "system_files/usr/share/wallpapers/NovaHorizonII"
for relative in (
    "metadata.json", "contents/screenshot.png",
    "contents/images/3840x2160.png", "contents/images/3440x1440.png",
    "contents/images/2560x1600.png", "contents/images_dark/3840x2160.png",
    "contents/images_dark/3440x1440.png", "contents/images_dark/2560x1600.png",
):
    require((wallpaper / relative).is_file(), f"missing wallpaper asset: {relative}")

# These are the active selectors; comments and package metadata are deliberately
# outside this gate. The EFI shim directory name is also intentionally excluded.
active_selectors = {
    "SDDM": sddm,
    "lock screen": lock_config,
    "look and feel": read("system_files/usr/share/plasma/look-and-feel/org.moos.nova/contents/defaults"),
}
for surface, text in active_selectors.items():
    require(re.search(r"fedora|bgrt|spinner", text, re.IGNORECASE) is None,
            f"foreign branding selector is active in {surface}")

build = read("build_files/build.sh")
require("plymouth-set-default-theme moos-nova" in build,
        "image build must select MoOS Plymouth")
require("grep -qx 'Theme=moos-nova' /etc/plymouth/plymouthd.conf" in build,
        "image build must fail if the active Plymouth selector is not MoOS")
require("final initramfs contains the Fedora BGRT/spinner branding path" in build,
        "image build must reject Fedora BGRT/spinner paths in initramfs")

if errors:
    print("MoOS user-experience gate failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print("MoOS user-experience gate passed")
