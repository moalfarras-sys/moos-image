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
require("THEME_REV=10" in apply_theme_code, "Nova visual schema must be revision 10")

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

xdg_kdeglobals = code(read("system_files/etc/xdg/kdeglobals"))
require("AutomaticLookAndFeel=false" in xdg_kdeglobals,
        "the day/night switch ships off; changing the look at sunset is a choice, not a default")
require("DefaultDarkLookAndFeel=org.moos.nova" in xdg_kdeglobals
        and "DefaultLightLookAndFeel=org.moos.nova.light" in xdg_kdeglobals,
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
    read("system_files/usr/share/plasma/look-and-feel/org.moos.nova.light/contents/defaults")
)
require("ColorScheme=NovaLight" in light_lnf and "name=NovaLight" in light_lnf,
        "the light Global Theme must select the light colour scheme and Plasma style")
require("theme=__aurorae__svg__MoOSNovaLight" in light_lnf,
        "the light Global Theme must select the light window decoration — Aurorae has no "
        "ColorScheme stylesheet, so a light desktop with the dark decoration writes "
        "near-white title text onto a near-white title bar")
require("Theme=NovaLight" in light_lnf,
        "the light Global Theme must select the light icon theme — Nova's symbolics are "
        "drawn light for a dark panel and vanish on porcelain")
require("Image=NovaAurora" in light_lnf,
        "the light Global Theme must not ship the navy wallpaper")

light_style = code(read("system_files/usr/share/plasma/desktoptheme/NovaLight/plasmarc"))
require("FallbackTheme=Nova" in light_style,
        "NovaLight must fall back to Nova for its SVGs; duplicating the artwork is how "
        "the two styles drift apart")
require((ROOT / "system_files/usr/share/plasma/desktoptheme/NovaLight/colors").is_file(),
        "NovaLight must ship its own colour palette")
for asset in (
    "system_files/usr/share/aurorae/themes/MoOSNovaLight/decoration.svg",
    "system_files/usr/share/aurorae/themes/MoOSNovaLight/MoOSNovaLightrc",
    "system_files/usr/share/color-schemes/NovaLight.colors",
    "system_files/usr/share/konsole/NovaLight.colorscheme",
    "system_files/usr/share/konsole/MoOSLight.profile",
):
    require((ROOT / asset).is_file(), f"the light theme is missing {asset}")

# The light decoration is GENERATED from the dark one. If someone hand-edits it, the
# two silently diverge — so the generator has to stay in the repo and stay wired to
# both themes.
generator = code(read("artwork/generate_nova_light.py"))
require("MoOSNovaLight" in generator and "DECORATION_COLORS" in generator,
        "the light decoration must be generated from the dark one, not hand-maintained — "
        "a hand-copied decoration diverges the next time the dark one is touched")

light_deco = code(read("system_files/usr/share/aurorae/themes/MoOSNovaLight/MoOSNovaLightrc"))
require("ActiveTextColor=16,24,40,255" in light_deco,
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
    "system_files/usr/share/plasma/plasmoids/org.moos.nova.deskclock/metadata.json",
    "system_files/usr/share/plasma/plasmoids/org.moos.nova.deskclock/contents/ui/main.qml",
):
    require((ROOT / asset).is_file(), f"the desktop clock is missing {asset}")
require('addWidget("org.moos.nova.deskclock"' in apply_theme_code,
        "new and existing users must both receive the desktop clock")

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

if errors:
    print("MoOS user-experience gate failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print("MoOS user-experience gate passed")
