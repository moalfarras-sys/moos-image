#!/usr/bin/env python3
"""Static gates for the active MoOS login/desktop experience."""

from pathlib import Path
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
        require("<text" not in svg and "<image" not in svg,
                f"{icon} must remain original vector geometry with no text or embedded bitmap")
    for size in (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512):
        png = ROOT / f"system_files/usr/share/icons/hicolor/{size}x{size}/apps/{icon}.png"
        require(png.is_file(), f"{icon} is missing its {size}px dock fallback")
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
        welcome_palette_code,
    ) is not None,
            f"MoOS Welcome's {token} token must follow {role}, not Nova's fixed palette")

legacy_nova_surfaces = {
    "#0b1220", "#111a2e", "#16233a", "#1a2740", "#263a5c", "#263852",
    "#f4f8ff", "#e6edf7", "#9fb0c9", "#7f94b5", "#0c1424", "#070c16",
    "#0a1120", "#0c1526", "#16233c", "#0e1830",
}
for app, qml_code in (("Mo AI", moai_palette_code),
                      ("MoOS Welcome", welcome_palette_code)):
    retained = sorted(colour for colour in legacy_nova_surfaces
                      if colour in qml_code.lower())
    require(not retained,
            f"{app} must not retain Nova's structural navy/text colours: {retained}")

require("component Card: Rectangle" in moai_palette_code
        and "color: root.surface1" in moai_palette_code,
        "Mo AI's shared Card must consume the palette-backed card token")
require("Qt.rgba(win.surface.r" in welcome_palette_code
        and "cardHover.hovered ? cardItem.modelData.c : win.outline" in welcome_palette_code,
        "MoOS Welcome cards must consume the palette-backed surface and outline tokens")
require("NovaHorizonII" not in welcome_palette_code,
        "MoOS Welcome must not paint Nova's dark wallpaper over a light KDE palette")

require("sudo waydroid init" not in moai_qml,
        "Mo AI must use the confirmed workflow, not copy sudo commands")
require('moos://do/setup-gaming' in moai_qml,
        "Mo AI's Compatibility panel must expose the focused gaming installer")
require('moos://do/setup-waydroid' in moai_qml,
        "Mo AI's Compatibility panel must expose the Android (Waydroid) setup")
require('moos://do/setup-windows' in moai_qml,
        "Mo AI's Compatibility panel must expose the Windows (Bottles) setup as a real flow, "
        "not a bare Flatpak install that leaves the user staring at an unopened Bottles")

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
moai_qml = read("system_files/usr/share/moos/apps/moai/main.qml")
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
# ── The desk widget: weather, a clock that turns, and nothing in the way ─────
deskclock = read("system_files/usr/share/plasma/plasmoids/"
                 "org.moos.nova.deskclock/contents/ui/main.qml")
# style="slash": QML comments, and this gate MUST see past them. Both of the checks below
# name the thing they forbid (ipapi.co, MouseArea) in the very comment that explains why it
# is forbidden — strip the prose or the gate fails against the correct file, which is the
# comment trap AGENTS.md warns about, arriving from the other direction.
deskclock_code = code(deskclock, "slash")
require("ipwho.is" in deskclock_code and "api.open-meteo.com" in deskclock_code,
        "the desk widget must read the weather from ipwho.is + Open-Meteo — both key-less, "
        "and both verified against the User-Agent Qt actually sends")
require("ipapi.co" not in deskclock_code,
        "ipapi.co must not be the widget's geocoder: it answers curl but serves a Cloudflare "
        "interstitial to Qt's browser-shaped User-Agent, so the widget got HTML instead of "
        "JSON and the weather silently never appeared")
require("component Roller" in deskclock_code and "component SkyGlyph" in deskclock_code,
        "the desk widget must keep the per-digit clock roller and the drawn, animated sky "
        "glyphs — the old clock threw all four digits in the air every minute, and an icon "
        "pulled from the icon theme disappears when the user changes it")
require("component GlassLens" in deskclock_code and "SequentialAnimation on x" in deskclock_code,
        "the MoOS UI desk widget must keep its passive glass lens and slow moving sheen")
require('text: "MoOS  /  LIVE"' in deskclock_code
        and "Kirigami.Units.gridUnit * 27" in deskclock_code
        and "SequentialAnimation on scale" in deskclock_code,
        "the MoOS UI desk widget must remain the wide live dashboard, not regress to Nova's "
        "old narrow clock with a glass rectangle placed behind it")
require("MouseArea" not in deskclock_code,
        "the desk widget must not contain a MouseArea: it sits on the wallpaper, and anything "
        "that accepts clicks eats the desktop's own right-click menu and rubber-band selection "
        "inside its rectangle, with no way for the user to tell why")


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
require("THEME_REV=16" in apply_theme_code, "MoOS UI2 visual schema must be revision 16")
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
            "current_widget_state()", "theme_complete()")),
        "the apply-once marker must be backed by runtime readback of the full theme and "
        "the exact per-containment desktop-widget state, not only LNF + decoration")
require("ui1-each" in apply_theme_code and "ui2-each" in apply_theme_code
        and "desktops=[1-9][0-9]*;state=" in apply_theme_code
        and "expected_widgets='ui1=0;ui2=1'" not in apply_theme_code,
        "desktop widgets must be validated once per containment; a global count of one "
        "breaks every multi-monitor or multi-Activity desktop")
require("timeout 4s gdbus call" in apply_theme_code,
        "runtime widget readback must time out instead of hanging login on an "
        "unresponsive plasmashell")
require("desktop_wallpapers_complete()" in apply_theme_code
        and "matching == desktops" in apply_theme_code
        and "grep -m1 '^Image='" not in apply_theme_code,
        "theme completion must verify the wallpaper on every desktop containment; "
        "the first Image= line is not authoritative on multiple monitors/Activities")
require("widget-deduplicated" in apply_theme_code
        and "for (var n = 1; n < targets.length; n++)" in apply_theme_code
        and "d.addWidget(TARGET, 80, 70, TARGET_WIDTH, TARGET_HEIGHT)" in apply_theme_code,
        "theme repair must deduplicate and instantiate the selected dashboard family "
        "per containment, whether UI2 or the explicit UI1 rollback is active")
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

# ── MoOS ships TWO looks, and both must be whole ──────────────────────────────
#
# A half-installed light theme is worse than none: Plasma applies what it finds and
# silently substitutes Breeze for what it does not, so the user gets a desktop that
# is MoOS in some places and Breeze in others and cannot tell why. Each of these is
# a piece the light theme cannot do without.
#
# The light theme carries no SVGs of its own ON PURPOSE — NovaLight's plasmarc sets
# FallbackTheme=Nova and borrows the dark theme's artwork, which is what stops the
# two from drifting apart. So this gate checks for the fallback, not for SVGs.
light_lnf = code(
    read("system_files/usr/share/plasma/look-and-feel/org.moos.ui.light/contents/defaults")
)
require("ColorScheme=MoOSUILight" in light_lnf and "name=MoOSUILight" in light_lnf,
        "the light Global Theme must select the light colour scheme and Plasma style")
require("theme=__aurorae__svg__MoOSUILight" in light_lnf,
        "the light Global Theme must select the light window decoration — Aurorae has no "
        "ColorScheme stylesheet, so a light desktop with the dark decoration writes "
        "near-white title text onto a near-white title bar")
require("Theme=NovaLight" in light_lnf,
        "the light Global Theme must select the light icon theme — Nova's symbolics are "
        "drawn light for a dark panel and vanish on porcelain")
require("Image=MoOSUIAtmosphere" in light_lnf,
        "the light Global Theme must select the warm pearl MoOS UI wallpaper")

light_style = code(read("system_files/usr/share/plasma/desktoptheme/MoOSUILight/plasmarc"))
require("FallbackTheme=MoOSUI" in light_style,
        "MoOSUILight must fall back to MoOSUI for its SVGs; duplicating the artwork is how "
        "the two styles drift apart")
require("enabled=false" in light_style,
        "MoOS UI Light must keep adaptive transparency off; it otherwise turns the dock "
        "into an opaque white slab while Dark remains designed glass")
require((ROOT / "system_files/usr/share/plasma/desktoptheme/MoOSUILight/colors").is_file(),
        "MoOSUILight must ship its own colour palette")
light_panel = ROOT / "system_files/usr/share/plasma/desktoptheme/MoOSUILight/widgets/panel-background.svg"
require(light_panel.is_file(),
        "MoOS UI Light must ship a warm-tinted panel using the dark dock's exact geometry")
if light_panel.is_file():
    light_panel_code = code(light_panel.read_text(encoding="utf-8"), "xml")
    require("#8B7082" in light_panel_code and "#705969" in light_panel_code,
            "MoOS UI Light dock must be warm mauve glass, not bright white")
for asset in (
    "system_files/usr/share/aurorae/themes/MoOSUILight/decoration.svg",
    "system_files/usr/share/aurorae/themes/MoOSUILight/MoOSUILightrc",
    "system_files/usr/share/color-schemes/MoOSUILight.colors",
    "system_files/usr/share/konsole/MoOSUILight.colorscheme",
    "system_files/usr/share/konsole/MoOSUILight.profile",
):
    require((ROOT / asset).is_file(), f"the light theme is missing {asset}")

# The light decoration is GENERATED from the dark one. If someone hand-edits it, the
# two silently diverge — so the generator has to stay in the repo and stay wired to
# both themes.
generator = code(read("artwork/generate_moos_ui.py"))
require("MoOSUILight" in generator and "DARK_MAP" in generator and "LIGHT_MAP" in generator,
        "the MoOS UI pair must be generated from the proven Nova contracts, not hand-maintained")
for package in ("org.moos.ui", "org.moos.ui.light"):
    previews = ROOT / f"system_files/usr/share/plasma/look-and-feel/{package}/contents/previews"
    for name in ("preview.png", "lockscreen.png", "splash.png", "fullscreenpreview.jpg"):
        require((previews / name).is_file(), f"{package} is missing its user-facing {name}")
require((ROOT / "system_files/usr/share/plasma/look-and-feel/org.moos.ui/contents/previews/preview.png").read_bytes()
        != (ROOT / "system_files/usr/share/plasma/look-and-feel/org.moos.nova/contents/previews/preview.png").read_bytes(),
        "MoOS UI must not advertise itself with Nova's old blue preview in System Settings")

light_deco = code(read("system_files/usr/share/aurorae/themes/MoOSUILight/MoOSUILightrc"))
require("ActiveTextColor=41,33,46,255" in light_deco,
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
require("plasma-apply-wallpaperimage" in theme_switch,
        "moos-theme must set the wallpaper; applying the Global Theme does not carry it")

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

# Windows must wear the Nova decoration, not Breeze. Breeze here means Breeze's
# X / v / ^ title-bar glyphs on every window — the loudest remaining "this is
# stock KDE" tell after the dock.
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

aurorae = ROOT / "system_files/usr/share/aurorae/themes/MoOSUI"
for name in ("decoration.svg", "close.svg", "minimize.svg", "maximize.svg",
             "restore.svg", "MoOSUIrc"):
    require((aurorae / name).is_file(),
            f"the Nova decoration must ship {name}")

# The shadow is the theme's own job — Aurorae paints the decoration SVG across
# its Padding* region, and a decoration with no padding has no drop shadow, which
# lands windows flat on the wallpaper and looks WORSE than the Breeze it
# replaced. Guard the padding so a future edit cannot quietly delete the shadow.
themerc = read("system_files/usr/share/aurorae/themes/MoOSUI/MoOSUIrc")
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
widgets = ROOT / "system_files/usr/share/plasma/desktoptheme/MoOSUI/widgets"
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
nova_theme = ROOT / "system_files/usr/share/plasma/desktoptheme/MoOSUI"
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

# ── Frosted glass: the premium surface finish MoOS competes on ────────────────
#
# A floating dock that turns into an opaque slab under every maximised window is not a
# glass dock. Nova pins Plasma::Theme::adaptiveTransparencyEnabled() OFF so the dock keeps
# its translucent blur at all times, like the macOS dock / Win11 acrylic taskbar. The
# blur plugin (Effect-blur) must stay shipped-on for the frost to exist at all.
nova_plasmarc = code(read("system_files/usr/share/plasma/desktoptheme/MoOSUI/plasmarc"))
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
for scheme in ("NovaDark", "NovaLight", "MoOSUIDark", "MoOSUILight",
               "MoOSUI2Dark", "MoOSUI2Light"):
    konsole_scheme = code(read(f"system_files/usr/share/konsole/{scheme}.colorscheme"))
    require("Opacity=1" in konsole_scheme and "Blur=false" in konsole_scheme,
            f"{scheme} Konsole scheme must be SOLID (Opacity=1, Blur=false) — the maintainer "
            f"asked for a solid terminal, not the frosted-glass one that was tried and rejected")
for prof in ("MoOS.profile", "MoOSLight.profile", "MoOSUI.profile", "MoOSUILight.profile",
             "MoOSUI2.profile", "MoOSUI2Light.profile"):
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
for package in ("org.moos.nova.clock",):
    root = ROOT / "system_files/usr/share/plasma/plasmoids" / package
    require((root / "metadata.json").is_file() and
            (root / "contents/ui/main.qml").is_file(),
            f"missing complete Plasma package: {package}")
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
require("WallpaperPluginId=org.kde.image" in login_config,
        "the login screen must select a wallpaper plugin, or the greeter draws Plasma's default")

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

# SDDM is DEAD on this base: Kinoite 44 boots plasmalogin, so the moos-nova SDDM
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
for adw_needle in ("moos-ui2-dark.css", "moos-ui2-light.css", "gtk-4.0/gtk.css"):
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

wallpaper = ROOT / "system_files/usr/share/wallpapers/NovaHorizonII"
for relative in (
    "metadata.json", "contents/screenshot.png",
    "contents/images/3840x2160.png", "contents/images/3440x1440.png",
    "contents/images/2560x1600.png", "contents/images_dark/3840x2160.png",
    "contents/images_dark/3440x1440.png", "contents/images_dark/2560x1600.png",
):
    require((wallpaper / relative).is_file(), f"missing wallpaper asset: {relative}")

ui_wallpaper = ROOT / "system_files/usr/share/wallpapers/MoOSUIAtmosphere"
for relative in (
    "metadata.json", "contents/screenshot.png",
    "contents/images/3840x2160.png", "contents/images/3440x1440.png",
    "contents/images/2560x1600.png", "contents/images_dark/3840x2160.png",
    "contents/images_dark/3440x1440.png", "contents/images_dark/2560x1600.png",
):
    require((ui_wallpaper / relative).is_file(), f"missing MoOS UI wallpaper asset: {relative}")

# The requested visual break from Nova is measurable: the operative pair may not
# retain Nova's cyan/blue focus tokens, and the light canvas may not fall back to
# glaring 255,255,255. Comments are stripped so prose cannot satisfy the gate.
for scheme in ("MoOSUIDark", "MoOSUILight"):
    palette = code(read(f"system_files/usr/share/color-schemes/{scheme}.colors"))
    require("34,211,238" not in palette and "46,123,255" not in palette,
            f"{scheme} must use the orchid/apricot MoOS UI accents, not Nova cyan/blue")
require("BackgroundNormal=255,255,255" not in
        code(read("system_files/usr/share/color-schemes/MoOSUILight.colors")),
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
require("plymouth-set-default-theme moos-nova" in build,
        "image build must select MoOS Plymouth")
require("grep -qx 'Theme=moos-nova' /etc/plymouth/plymouthd.conf" in build,
        "image build must fail if the active Plymouth selector is not MoOS")
require("final initramfs contains the Fedora BGRT/spinner branding path" in build,
        "image build must reject Fedora BGRT/spinner paths in initramfs")

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
plymouth_theme = code(
    read("system_files/usr/share/plymouth/themes/moos-nova/moos-nova.plymouth")
)
ui2_palette = json.loads(read("artwork/moos-ui2/palette.json"))["dark"]
def rgb(value: str) -> str:
    """Normalise `0x14191C`, `0X14191c` and `#14191C` to the same six hex digits."""
    return value.strip().lower().removeprefix("0x").removeprefix("#")


for key, token in (("BackgroundStartColor", "canvas"),
                   ("BackgroundEndColor", "canvas"),
                   ("ProgressBarBackgroundColor", "card"),
                   ("ProgressBarForegroundColor", "primary")):
    expected = ui2_palette[token]
    actual = re.search(rf"^{key}=(\S+)", plymouth_theme, re.MULTILINE)
    require(actual is not None, f"the boot splash declares no {key}")
    if actual is not None:
        require(rgb(actual.group(1)) == rgb(expected),
                f"the boot splash's {key} is {actual.group(1)}, but MoOS UI2's `{token}` is "
                f"{expected}: the first screen of the boot would not be the colour of the "
                f"desktop it boots into")

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
):
    text = code(read(launcher))
    require("/usr/bin/moos-qml-shell" in text and f"--app-id {app_id}" in text,
            f"{launcher} must EXEC moos-qml-shell with --app-id {app_id}, or its window "
            f"carries the QML runtime's app_id and the taskbar shows the generic Qt icon")

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
    "system_files/usr/share/plasma/plasmoids/org.moos.ui2.dashboard/metadata.json",
    "system_files/usr/share/plasma/plasmoids/org.moos.ui2.dashboard/contents/ui/main.qml",
    "system_files/usr/share/plasma/plasmoids/org.moos.nova.deskclock/metadata.json",
    "system_files/usr/share/plasma/plasmoids/org.moos.nova.deskclock/contents/ui/main.qml",
):
    require((ROOT / asset).is_file(), f"a desktop dashboard package is missing {asset}")
require("want_widget=org.moos.ui2.dashboard" in apply_theme_code
        and "d.addWidget(TARGET, 80, 70, TARGET_WIDTH, TARGET_HEIGHT)" in apply_theme_code,
        "new and existing users must both receive the selected MoOS dashboard through "
        "the parameterised per-containment migration")
require("org.moos.nova.deskclock" in apply_theme_code,
        "the UI2 dashboard migration must retain the old package as a safe source/rollback")
build_script_code = code(read("build_files/build.sh"))
require("plasmawindowed org.moos.ui2.dashboard" in build_script_code,
        "the image build must load the UI2 plasmoid through Plasma's real package runtime; "
        "pure-QML app smoke tests do not exercise PlasmoidItem or KPackage imports")
normalized_build_script = " ".join(build_script_code.replace("\\", " ").split())
require("dbus-run-session -- plasmawindowed org.moos.ui2.dashboard" in
        normalized_build_script,
        "the headless plasmoid smoke needs a session bus; without one even KDE's stock "
        "digital clock exits silently and the gate tests the container, not the package")
for qml_runtime_failure in ("typeerror", "unable to assign", "binding loop"):
    require(qml_runtime_failure in build_script_code,
            "the dashboard smoke must reject live QML %s diagnostics; plasmawindowed can "
            "stay alive while one card is blank" % qml_runtime_failure)

# The clock and the rings are ONE applet, and they have to stay one. A desktop
# applet's position lives in a resolution-keyed ItemGeometries string on the
# CONTAINMENT, not on the applet, and the geometry passed to addWidget() is
# transient — so two applets that must sit together drift apart the first time the
# shell restarts, and the second one lands on top of the folder icons.
deskclock = code(
    read("system_files/usr/share/plasma/plasmoids/org.moos.nova.deskclock/contents/ui/main.qml"),
    "slash",
)
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
    "gpu/gpu0/usage",
}
for sensor in re.findall(r'sensorId:\s*"([^"]+)"', deskclock):
    require(sensor in KNOWN_SENSORS,
            f"the desk clock reads sensor '{sensor}', which is not in the verified list "
            f"{sorted(KNOWN_SENSORS)}. Check it against `kstatsviewer --list` — an invented "
            f"sensor id draws an empty ring and never says why")
require(len(re.findall(r'sensorId:\s*"', deskclock)) >= 3,
        "the desk clock must show CPU, memory and GPU")

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

for clock in ("org.moos.nova.clock", "org.moos.nova.deskclock"):
    qml = code(
        read(f"system_files/usr/share/plasma/plasmoids/{clock}/contents/ui/main.qml"), "slash"
    )
    require("PlasmaCore.Theme" not in qml,
            f"{clock}: Plasma 6 has no PlasmaCore.Theme — org.kde.plasma.core exposes Types "
            f"only. Binding a colour to it is undefined at runtime and the applet silently "
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

if errors:
    print("MoOS user-experience gate failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print("MoOS user-experience gate passed")
