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


def kconfig_value(text: str, section: str, key: str) -> str:
    """Read one exact KConfig key without leaking into a later section."""
    section_match = re.search(
        rf"(?ms)^\[{re.escape(section)}\]\s*$\n(.*?)(?=^\[|\Z)",
        text,
    )
    if section_match is None:
        return ""
    key_match = re.search(
        rf"(?m)^{re.escape(key)}\s*=\s*(.*?)\s*$",
        section_match.group(1),
    )
    return key_match.group(1) if key_match is not None else ""


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
require("/usr/libexec/moos-wayland-display" in unit,
        "Mo Remote must resolve and probe a live Wayland socket")

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

# First-party GTK surfaces must follow the SAME active ColorScheme as Plasma,
# including all family accents — a binary Graphite/Tidal guess makes fourteen of
# sixteen theme choices look half-applied.  Selection foreground is the only
# colour KDE pairs with the accent; generated hue endpoints are not safe.
gtk_ui2 = code(read("system_files/usr/lib/moos/moos_ui2.py"))
require(all(token in gtk_ui2 for token in (
            "def palette_from_color_scheme(",
            "def active_color_scheme(",
            "def find_color_scheme(",
            'on_accent = colour(selection, "ForegroundNormal")',
            "def watch_kdeglobals(",
            "monitor_directory(",
            "class UI2StyleController:",
            "self._monitor = watch_kdeglobals(self.schedule_restyle",
            "self._style_controller = UI2StyleController(self._css)",
        )),
        "first-party GTK must parse the active KDE .colors file, take on_accent "
        "from Selection.ForegroundNormal, and live-restyle on kdeglobals changes")
_gtk_suggested = gtk_ui2.split(
    "window.moos-ui2 button.suggested-action", 1
)[1].split("}", 1)[0] if "window.moos-ui2 button.suggested-action" in gtk_ui2 else ""
require("background-color: @ui2_primary" in _gtk_suggested
        and "linear-gradient" not in _gtk_suggested,
        "GTK suggested buttons must put Selection foreground on its paired flat "
        "Selection background; the secondary gradient endpoint reaches only 3.01:1")

# The three-second Mo PC Remote poll used to execute systemctl/Tailscale/qrencode
# serially on GTK's main thread (as many as nine 5-second timeouts). Collect on one
# daemon worker, coalesce bursts, and marshal immutable results through idle_add.
remote_code = code(native_remote)
require("class CoalescingWorker:" in remote_code
        and "GLib.idle_add" in remote_code
        and "collect_remote_snapshot" in remote_code
        and "self._refresh_worker.request()" in remote_code
        and "self.style_controller=UI2StyleController(self.style_provider)" in remote_code,
        "Mo PC Remote must use the shared live GTK theme controller and a "
        "GLib.idle_add coalescing refresh worker")
try:
    _remote_tree = ast.parse(native_remote)
    _remote_app = next(node for node in _remote_tree.body
                       if isinstance(node, ast.ClassDef) and node.name == "App")
    _remote_apply = next(node for node in _remote_app.body
                         if isinstance(node, ast.FunctionDef)
                         and node.name == "_apply_refresh")
    _remote_apply_calls = {
        node.func.id for node in ast.walk(_remote_apply)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
except (SyntaxError, StopIteration):
    _remote_apply_calls = {"invalid-remote-source"}
require(not (_remote_apply_calls & {
            "run", "active", "tailscale_url", "qr_png",
            "collect_remote_snapshot", "open", "invalid-remote-source",
        }),
        "Mo PC Remote's GTK apply path still performs blocking I/O instead of "
        "consuming the worker snapshot")
gtk_runtime_test = "python3 tests/test_moos_gtk_runtime.py"
require(gtk_runtime_test in read("Justfile")
        and gtk_runtime_test in read(".github/workflows/build.yml"),
        "the 16-palette/live-restyle/non-blocking GTK gate must run locally and in CI")

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
# The member may sit anywhere in the do/* alternation arm, so accept it followed by
# either `|` (another member after it) or `)` (it is last). The invariant is that
# do/remote-anywhere is one of the arms forwarded to moai-do, not its position.
require('remote-anywhere)' in router_remote or 'remote-anywhere|' in router_remote,
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
require('remote/restart) remote_ctl try-restart' in router_remote,
        "remote/restart must be a no-op while access is off; a public URL must "
        "not start an inactive remote-control service")
require("do_remote_anywhere()" in do_remote and 'remote-anywhere) do_remote_anywhere' in do_remote,
        "moai-do must DEFINE and DISPATCH do_remote_anywhere — the Tailscale "
        "serve path that makes Mo PC Remote reachable from mobile data")

# THE RESCUE MUST USE THE RIGHT COMMAND. `moai-do rollback` and the Recovery app must run
# the SAME thing, and on a bootc system that is `bootc rollback`, not `rpm-ostree rollback`.
# They are not interchangeable: rpm-ostree reverts to "the previously booted tree", while
# bootc reorders the boot entries and explicitly discards a staged (queued) upgrade. With an
# update already staged by uupd or `moai-do update` — the normal state of this machine
# overnight — the wrong one can leave the deployment unchanged while the action still prints
# that the next boot will use the previous version. A rescue that lies is worse than no rescue.
require("run_priv bootc rollback" in do_remote,
        "moai-do rollback must run `bootc rollback` (what the Recovery app runs), not "
        "`rpm-ostree rollback` — with a staged update the two do different things and the "
        "rescue can silently no-op")
# The staged-update warning must read the JSON, where every deployment carries a "staged"
# boolean. The first version grepped the HUMAN output of `rpm-ostree status` for "Staged",
# which it does not reliably print — so the warning could never fire and was decoration on a
# screen that changes which OS boots next.
require(re.search(r'rpm-ostree status --json[^|]*\|', do_remote),
        "moai-do rollback must detect a staged deployment from `rpm-ostree status --json`; "
        "grepping the human-readable status for 'Staged' never matches, so the warning that a "
        "queued update is about to be discarded would never appear")
require("bootc" in code(read("system_files/usr/bin/moos-rollback")),
        "the Recovery app must drive bootc rollback, so the GUI and the assistant agree")
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
for icon in ["moos-moai"]:
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
            # 2026-07-30: Mo AI is the one mark with NO tile — the siblings' tiles
            # are re-inked for all 16 palettes and this artwork carries its own
            # light, so a plate under it would put a second, competing colour
            # behind the assistant on every theme. What it still owes the family
            # is optical weight: the raw master's solid alpha spans 949 of its
            # 1024 canvas against the siblings' 880 px plate, and shipped raw it
            # bulged out of the dock row. The wrapper must scale it onto that
            # span. tests/test_moos_app_icons.py measures the rendered footprint;
            # this is the markup half. Regenerate with artwork/generate_moai_icon.py.
            require('<image x="37" y="37" width="950" height="950"' in svg,
                    "moos-moai.svg no longer seats the commissioned master on the family's "
                    "880px optical span — the raw orb renders larger than every sibling and "
                    "breaks the dock's size grid (regenerate with artwork/generate_moai_icon.py)")
            require('<rect' not in svg,
                    "moos-moai.svg grew a tile. The commissioned orb is deliberately "
                    "tile-less: every sibling plate is re-inked per palette and a plate "
                    "here would fight the artwork on every theme")
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

# Mo Store must make a whole filtered section installable with one reviewed
# selection, and must SHOW the resolved source for every app. Both drive the
# unified index/transaction plumbing rather than a second storefront.
require('"Add this section"' in store_qml
        and "function addMany(ids)" in store_qml
        and "win.addMany(ids)" in store_qml,
        "Mo Store must offer a per-section 'Add all' that carts the whole category")
require("function sourceLabel(app)" in store_qml
        and 'install.kind === "npm"' in store_qml
        and 'install.kind === "web"' in store_qml
        and '"Flathub"' in store_qml
        and "SourceBadge { app: card.app }" in store_qml,
        "Mo Store cards must show each app's resolved source")
require("property var installedOverrides" in store_qml
        and "property var installedScopeOverrides" in store_qml
        and "function applyJobInstalledState(document)" in store_qml
        and 'document.action === "remove"' in store_qml
        and '"Already installed system-wide"' in store_qml
        and '"Already installed for this user"' in store_qml,
        "Mo Store must keep install/remove state accurate until its local index reloads")
require(store_qml.count("MoosStore.refreshIndex()") == 1
        and "function maybeRefreshCatalog(force)" in store_qml
        and "if (win.hasFlatpakCatalog()) return" in store_qml
        and "if (!force && win.catalogRefreshRequested) return" in store_qml
        and 'win.expectJob("refresh-index", ["flathub"])' in store_qml,
        "Mo Store must refresh AppStream only when the full local catalogue is "
        "missing (or after an explicit retry), never after every app operation")
require("&& !win.jobIsActive()" in store_qml
        and "&& !win.jobIsTerminal()" in store_qml
        and "anchors.bottomMargin > -100 && win.pickCount === 0" not in store_qml,
        "real transaction progress and Cancel must replace the selection shelf "
        "while an install is running, including partial/failed jobs")
# The Updates page used to be a button and nothing else: it could not tell the
# user WHAT was pending, so "Update apps now" was a leap of faith. It must now
# name every app, and must distinguish "not checked yet" from "nothing pending"
# — showing 0 before looking is a lie the user cannot detect.
require("function updateItems()" in store_qml
        and "function checkUpdates()" in store_qml
        and "MoosStore.checkUpdates()" in store_qml
        and 'property string updatesState: "unknown"' in store_qml,
        "Mo Store's Updates page must ask the backend what is pending")
require('"بانتظار التحديث"' in store_qml
        and '"Waiting to update"' in store_qml
        and "model: win.updatesState === \"known\" ? win.updateItems() : []" in store_qml,
        "Mo Store must LIST the apps that have updates, not just offer a button")
require('win.updatesState === "known" && win.updates.count === 0' in store_qml
        and 'win.updatesState === "unknown"' in store_qml
        and '"Could not check for updates"' in store_qml,
        "Mo Store must distinguish unknown / none / failed on the Updates page "
        "instead of rendering every one of them as 'up to date'")
require("win.updatesState = \"unknown\"" in store_qml
        and 'document.action === "update"' in store_qml,
        "installing, removing or updating must invalidate the pending-update "
        "answer — a stale list outlives the transaction that changed it")
store_qml_code = code(store_qml, "slash")
require('function removeSelected(app) {\n        if (win.jobIsActive())' in store_qml_code
        and re.search(
            r"visible:\s*win\.canRemove\(win\.selectedApp\).*?"
            r"enabled:\s*!win\.jobIsActive\(\)",
            store_qml_code,
            re.DOTALL,
        ) is not None,
        "Mo Store must disable removal while another transaction owns the backend; "
        "a busy result cannot replace the active job document")
require("win.openSourceEngine(updateCard.modelData.action)" in store_qml_code
        and "MoosStore.openEngine(updateCard.modelData.action)" not in store_qml_code,
        "every Updates-page engine button must use the correlated job helper, "
        "not fire a detached backend job with no visible result")
require('"Shared components have updates."' in store_qml_code
        and "win.updateComponentCount() > 0" in store_qml_code,
        "the Updates page must not say everything is current while Flatpak "
        "runtimes or shared components still have pending updates")
require(re.search(
            r"id:\s*jobProgressIndeterminate\b.*?"
            r"SequentialAnimation\s+on\s+x\s*\{\s*"
            r"running:\s*jobProgressIndeterminate\.visible\b.*?"
            r"to:\s*jobProgressTrack\.width\b",
            store_qml_code,
            re.DOTALL,
        ) is not None,
        "Mo Store's indeterminate job bar must use explicit item IDs; `parent` "
        "inside SequentialAnimation is undefined and breaks the live QML scene")
require("visible: win.selectedApp !== null && !!win.selectedApp.license" in store_qml_code
        and re.search(
            r"visible:\s*win\.selectedApp\s*!==\s*null\s*&&\s*"
            r"\(win\.selectedApp\.requires_review",
            store_qml_code,
        ) is not None,
        "Mo Store detail visibility must always evaluate to a boolean; null/string "
        "bindings produce live QML type-assignment errors")
require("function pickedWebCount()" in store_qml_code
        and "function onlyWebPicks()" in store_qml_code
        and '"Review external website"' in store_qml_code
        and '"Open official website"' in store_qml_code
        and '"Continue with "' in store_qml_code,
        "external website recipes must say that they open a publisher page rather "
        "than presenting the action as an in-store installation")
require('"Update components now"' in store_qml_code
        and '"Open MoOS Updater"' in store_qml_code
        and '"Open firmware updates"' in store_qml_code,
        "Updates-page buttons must name the distinct action they perform instead "
        "of showing the same ambiguous Open label")
require('"io.github.kolunmi.Bazaar"' in store_qml_code
        and '"Install & open engine"' in store_qml_code,
        "the optional Bazaar engine button must disclose that its first use "
        "installs software before opening it")
require(re.search(
            r"visible:\s*win\.jobIsActive\(\).*?"
            r"enabled:\s*!win\.waitingForJob.*?"
            r"label:\s*win\.rtl\s*\?\s*\"إلغاء\"\s*:\s*\"Cancel\"",
            store_qml_code,
            re.DOTALL,
        ) is not None,
        "Mo Store must not let a Starting-state Cancel click target the stale "
        "job document from the preceding transaction")
require(re.search(
            r'item\.message\s*\|\|\s*""\)\s*===\s*"Already installed system-wide".*?'
            r'nextScopes\[item\.id\]\s*=\s*\["system"\]',
            store_qml_code,
            re.DOTALL,
        ) is not None,
        "an already-installed system Flatpak must retain its system scope in "
        "live store state so the UI does not offer a non-functional Remove action")
require(re.search(
            r"function\s+canRemove\(app\)\s*\{.*?"
            r"installedScopeOverrides\[app\.id\]\s*!==\s*undefined\)\s*"
            r"return\s+win\.installedScopeOverrides\[app\.id\]"
            r"\.indexOf\(\"user\"\)\s*>=\s*0",
            store_qml_code,
            re.DOTALL,
        ) is not None,
        "a live scope override must decide canRemove before legacy catalogue "
        "fallbacks; ['system'] must never expose a Remove button")
storectl_text = read("system_files/usr/bin/moos-storectl")
require("def check_updates(" in storectl_text
        and "def update_candidates(" in storectl_text
        and '"check-updates"' in storectl_text,
        "the trusted backend must expose a read-only pending-update report")

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

# Installing an app must not silently change unrelated user preferences. Browser
# choice remains an explicit desktop setting, never a side effect of Store.
storectl = read("system_files/usr/bin/moos-storectl")
require("xdg-settings set default-web-browser" not in storectl,
        "Mo Store must not silently make a newly installed browser the default")

# Mo AI's tokens follow Kirigami.Theme, for the same measured reason as Mo Store and Welcome.
#
# This gate used to require `root.palette.base` and friends, and the comment in Mo AI explained
# that the bindings were "deliberately owned by ApplicationWindow.palette" so a Global Theme
# change would follow at runtime. The intent was exactly right; the mechanism never delivered it.
# A bare `palette` on a QQuickWindow resolves to Qt's built-in defaults, not the KDE scheme —
# measured, an app on palette.* rendered accent #45A7D7 (Breeze blue) while an app on
# Kirigami.Theme rendered #006D67 (the MoOS teal) in the same session.
#
# Mo AI was missed in the first pass of that migration precisely because this gate was green:
# the other three apps use `win.palette` and Mo AI uses `root.palette`, so a grep for the former
# reported Mo AI clean while 33 references sat in it.
#
# The Nova identifiers are load-bearing and stay; only what they resolve to changed.
for token, role in {
    "surface0": "Kirigami.Theme.backgroundColor",
    "surface1": "Kirigami.Theme.alternateBackgroundColor",
    "chrome": "Kirigami.Theme.backgroundColor",
    "textHi": "Kirigami.Theme.textColor",
    "textLo": "Kirigami.Theme.disabledTextColor",
    "novaBlue": "Kirigami.Theme.highlightColor",
    "novaCyan": "Kirigami.Theme.linkColor",
    "novaViolet": "Kirigami.Theme.visitedLinkColor",
    # accentText was born "onAccent" — but a property named on<Capitalized> next to a sibling
    # property of the matching name is signal-handler syntax to QML: the binding is swallowed
    # as a handler body and the color property silently stays at its default, #000000. Three
    # apps rendered pure-black labels on the teal accent while this gate was green, because
    # the gate checked the binding EXISTED, and it did — as a handler. Measured before/after:
    # the Welcome CTA label went (0,0,0) -> (225,240,236) on rename alone.
    "accentText": "Kirigami.Theme.highlightedTextColor",
}.items():
    require(re.search(
        rf"readonly\s+property\s+color\s+{token}\s*:\s*{re.escape(role)}\b",
        moai_palette_code,
    ) is not None,
            f"Mo AI's {token} token must follow {role} — a bare `palette` does not resolve the "
            f"MoOS colour scheme and silently falls back to Qt's Breeze blue")
require(re.search(r"readonly\s+property\s+color\s+hairline\s*:\s*Qt\.rgba\(", moai_palette_code)
        is not None,
        "Mo AI's hairline must be a low-alpha tint of the text colour; separatorColor is #FFFFFF "
        "in every colour set of this scheme and would delete every hairline on a light page")
require("root.palette." not in moai_palette_code,
        "Mo AI still reads root.palette.* — a half-migrated window mixes the MoOS theme with Qt "
        "defaults. This is exactly how it was missed the first time: the other apps use "
        "`win.palette`, so a grep for that reported Mo AI clean.")

# The same semantic tokens hold on BOTH catalog surfaces: Mo Store (the
# standalone storefront, apps/store) and the Welcome onboarding wizard
# (apps/welcome). A hard-coded canvas in either one reopens the "two dark-blue
# applications on a light theme" bug.
#
# THE SOURCE CHANGED FROM `win.palette` TO `Kirigami.Theme`, AND THAT IS THE POINT.
#
# This gate used to require `win.palette.base` and friends. Its intent was right — follow the
# user's theme, never a fixed palette — but it named a mechanism that does not actually do
# that. Measured on one session, one scheme (MoOSUI2Light, selection #006D67), two MoOS apps
# rendered at the same moment:
#
#   theme picker (Kirigami.Theme, 31 refs)   surface #DFEFEA   accent #006D67   <- MoOS teal
#   welcome      (win.palette.*, 11 refs)    surface #FFFFFF   accent #45A7D7   <- Breeze blue
#
# A bare `palette` on a QQuickWindow does not resolve the KDE colour scheme; it falls back to
# Qt's built-in defaults. Setting QT_QPA_PLATFORMTHEME=kde does not change it either (tested:
# the button stayed #45A7D7). So the old gate was green while MoOS's own windows wore a blue
# that appears in no MoOS palette, inside a mint MoOS frame — the exact "two applications on a
# light theme" failure this block exists to prevent, passing its own check.
#
# The requirement is therefore stricter now, not looser: the token must bind to Kirigami.Theme,
# AND the file must contain no `win.palette.` at all, so nobody half-migrates a surface.
for surface_label, palette_code in (("Mo Store", store_palette_code),
                                    ("MoOS Welcome", welcome_palette_code)):
    for token, role in {
        "canvas": "Kirigami.Theme.backgroundColor",
        "surface": "Kirigami.Theme.alternateBackgroundColor",
        "chrome": "Kirigami.Theme.backgroundColor",
        "txt": "Kirigami.Theme.textColor",
        "txt2": "Kirigami.Theme.disabledTextColor",
        "blue": "Kirigami.Theme.highlightColor",
        "cyan": "Kirigami.Theme.linkColor",
        "violet": "Kirigami.Theme.visitedLinkColor",
        "accentText": "Kirigami.Theme.highlightedTextColor",  # renamed from onAccent — see above
    }.items():
        require(re.search(
            rf"readonly\s+property\s+color\s+{token}\s*:\s*{re.escape(role)}\b",
            palette_code,
        ) is not None,
                f"{surface_label}'s {token} token must follow {role} — a bare `palette` does not "
                f"resolve the MoOS colour scheme and silently falls back to Qt's Breeze blue")
    # outline is deliberately NOT Kirigami.Theme.separatorColor: that renders #FFFFFF in all
    # five colour sets of this scheme, so binding to it deletes every hairline on a light page.
    require(re.search(r"readonly\s+property\s+color\s+outline\s*:\s*Qt\.rgba\(", palette_code)
            is not None,
            f"{surface_label}'s outline must be a low-alpha tint of the text colour. "
            f"Kirigami.Theme.separatorColor is #FFFFFF in every colour set of this scheme — an "
            f"invisible border on a light canvas")
    require("win.palette." not in palette_code,
            f"{surface_label} still reads win.palette.* somewhere — a half-migrated surface mixes "
            f"the MoOS theme with Qt defaults in one window")

# The trap must never come back under its old name. `onAccent` beside a sibling `accent` is
# signal-handler syntax to QML, not a property binding: with a script expression the binding is
# swallowed as a handler body (colour silently stays #000000); with a literal it is a compile
# error. Ban the name outright in every app, declarations and references alike.
for guard_label, guard_text in (
        ("Mo AI", moai_qml),
        ("MoOS Welcome", welcome_qml),
        ("Mo Store", store_qml),
        ("MoOS Installer", read("system_files/usr/share/moos/apps/installer/main.qml"))):
    require("onAccent" not in guard_text,
            f"{guard_label} says `onAccent` somewhere — that name next to a sibling `accent` is a "
            f"signal handler, not a binding, and the colour silently stays #000000. The token is "
            f"`accentText`.")

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

# ── Device onboarding buttons must reach real Plasma settings routes ─────────
#
# USB receivers work as soon as they are plugged in; Bluetooth devices need
# pairing. The Welcome explains that distinction and opens the exact settings
# page it names. Gate the whole QML -> URL router -> KCM-id relationship so these
# cannot become polished-looking buttons that only raise "unknown action".
welcome_devices = code(read("system_files/usr/share/moos/apps/welcome/main.qml"), "slash")
router_devices = code(router)
for device_route, settings_app, kcm_id in (
    ("bluetooth", "systemsettings", "kcm_bluetooth"),
    ("usb", "kinfocenter", "kcm_usb"),
    ("keyboard", "systemsettings", "kcm_keyboard"),
    ("mouse", "systemsettings", "kcm_mouse"),
):
    require(f'moos://settings/{device_route}"' in welcome_devices,
            f"the Welcome must offer a real {device_route} settings action")
    device_arm = re.search(
        rf"(?ms)^\s{{4}}settings/{re.escape(device_route)}\)(.*?);;",
        router_devices,
    )
    require(device_arm is not None
            and re.search(
                rf"\bgui\s+{re.escape(settings_app)}\s+{re.escape(kcm_id)}"
                rf"(?:\s|;|$)",
                device_arm.group(1),
            ) is not None,
            f"moos-open must send settings/{device_route} to "
            f"{settings_app}'s {kcm_id} module")
require("id: overallInstallTrack" in welcome_devices
        and "id: overallInstallIndeterminate" in welcome_devices
        and "running: overallInstallIndeterminate.visible" in welcome_devices
        and "overallInstallTrack.width" in welcome_devices
        and "parent.parent.width" not in welcome_devices,
        "the Welcome's indeterminate install bar must use explicit item IDs; "
        "`parent` is undefined inside SequentialAnimation and stops the live motion")

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

# ── Office documents must have somewhere to go ────────────────────────────────
#
# MEASURED on the shipped image before this existed: `xdg-mime query default` returned
# NOTHING for all seven of .docx/.xlsx/.pptx/.doc/.xls/.odt/.rtf. A Word file a colleague
# sent did nothing at all when double-clicked — the same failure the .exe had, and the
# same three pieces have to line up or it silently comes back.
_apply_theme_code = code(read("system_files/usr/bin/moos-apply-theme"))
_OFFICE_MIMES = (
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.oasis.opendocument.text",
    "application/rtf",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.oasis.opendocument.presentation",
)
for _m in _OFFICE_MIMES:
    require(_m in runner_desktop,
            f"org.moos.runforeign.desktop must claim {_m} — without it the double-click has "
            f"nowhere to go and does nothing, which is exactly the bug this closed")
    require(f"{_m}=org.moos.runforeign.desktop" in system_mimeapps,
            f"/etc/xdg/mimeapps.list must default {_m} to the MoOS runner")
    require(_m in _apply_theme_code,
            f"moos-apply-theme must pin {_m} in the user's mimeapps.list — that file outranks "
            f"/etc/xdg, so existing users would keep the broken 'no default'")
require("org.libreoffice.LibreOffice" in runner,
        "moos-run-foreign must offer the one-time LibreOffice install for office documents. "
        "MoOS ships no office suite on purpose (~700 MB); the runner is the bridge to the "
        "store, and without it these types fail silently again.")
require("apps/install/" in runner,
        "moos-run-foreign must route the office install through moos://apps/install/, the "
        "existing confirmed+Polkit path — never a bare flatpak install")
# .csv must NOT cost a 700 MB download: it is text, and kate is already in the image.
require("text/csv=org.kde.kate.desktop" in system_mimeapps,
        "text/csv must default to kate. Routing it through the office runner would ask the "
        "user to install 700 MB to read a comma-separated file — worse than the status quo.")
require("csv" not in [seg.strip() for seg in re.findall(r"^\s*([a-z|]+)\)", runner, re.M)
                      for seg in seg.split("|")],
        "moos-run-foreign now handles .csv itself — it should not: kate opens it instantly "
        "and the runner would offer a 700 MB install instead")

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

# A LIST NOBODY RENDERS IS A FEATURE NOBODY HAS. defaultRepairs describes itself as "always
# shown, and the fallback before a diagnose run has returned", but it was declared and never
# referenced again — so the safe repair menu did not exist until the backend returned fixes,
# and anything added to the list (the read-only diagnostics among them) reached no user. The
# Repeater must fall back to it, and the delegate must render `label` as well as `title`, or
# the fallback entries appear to the user as bare ids.
# Asserted against COMMENT-STRIPPED code: this file's own comments name defaultRepairs while
# explaining the fix, and a raw-text count is satisfied by that prose while the list is dead —
# the precise trap this repo keeps re-learning.
_moai_code = code(moai_qml, "slash")
require(_moai_code.count("defaultRepairs") >= 2,
        "Mo AI declares defaultRepairs but never renders it — the safe repair menu is dead "
        "code, and every action added to it is invisible to the user")
# The exact three-way expression, not merely the word `label`: four unrelated delegates in this
# file already use modelData.label, so a looser check passes while the REPAIR delegate has
# regressed to title-or-id and renders the fallback entries as bare action ids.
require(re.search(r"modelData\.title\s*\|\|\s*modelData\.label\s*\|\|\s*modelData\.id", _moai_code),
        "the repair delegate must render `title || label || id` — the backend's fixes carry "
        "`title` and defaultRepairs carries `label`, so dropping either renders bare action ids")

# THE TWO REPAIR MENUS MUST AGREE. The panel shows the app's defaultRepairs until a diagnosis
# returns, then REPLACES it with moai-control's list. So an action present in only one of them
# vanishes (or appears) the moment the user presses "افحص الآن" — which is what happened to the
# rescue and diagnostic actions: they were added to the app and not to the backend, so running a
# diagnosis deleted them from the menu.
_qml_repairs = re.findall(r'\{\s*id:\s*"([a-z-]+)"\s*,\s*label:', _moai_code)
_control_repairs = re.findall(r'\{"id":\s*"([a-z-]+)",\s*"label":', code(read("system_files/usr/bin/moai-control")))
require(_qml_repairs and _control_repairs and set(_qml_repairs) == set(_control_repairs),
        "Mo AI's defaultRepairs and moai-control's /diagnose fixes list have drifted: "
        f"only in the app {sorted(set(_qml_repairs) - set(_control_repairs))}, "
        f"only in the backend {sorted(set(_control_repairs) - set(_qml_repairs))}. "
        "Running a diagnosis swaps one list for the other, so anything missing from either "
        "appears or disappears under the user.")
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
require("/usr/libexec/moai-local-engine" in headroom
        and 'systemctl --user stop "$BRAIN_UNIT"' in headroom
        and "nvidia-smi" in headroom,
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

# ONE KEYBOARD LIST, FOUR PLACES THAT MUST AGREE.
#
# The image ships the available layouts in /etc/xdg/kxkbrc and
# /etc/X11/xorg.conf.d/00-keyboard.conf, and moos-selfcheck compares the live session
# against the former. But moos-firstboot OVERWRITES 00-keyboard.conf with its own
# XKBLAYOUT, and the installer supplies that value from xkbForLang(). Both still said
# `de,ara` after the image moved to `de,us,ara`, so a machine nobody had touched failed
# MoOS's own keyboard check on first boot — the drift was written at birth. Pin all four
# to the image's list rather than to a literal here, so the next change moves them together.
_image_layouts = re.search(r"(?m)^LayoutList=([a-z,]+)\s*$",
                           read("system_files/etc/xdg/kxkbrc"))
require(_image_layouts, "/etc/xdg/kxkbrc must declare LayoutList — it is the image's "
                        "definition of which keyboard layouts exist")
_layouts = _image_layouts.group(1)
require(f'"XkbLayout" "{_layouts}"' in read("system_files/etc/X11/xorg.conf.d/00-keyboard.conf"),
        f"00-keyboard.conf must offer the same layouts as kxkbrc ({_layouts}); the X11 layout and "
        f"the Plasma layout list describe one keyboard")
_xkb_fn = re.search(r"function\s+xkbForLang\s*\(\s*\)\s*\{([^}]*)\}", installer_qml)
require(_xkb_fn and _layouts in _xkb_fn.group(1),
        f"the installer's xkbForLang() must produce the image's layout list ({_layouts}). "
        f"moos-firstboot overwrites 00-keyboard.conf with it, so anything else replaces the "
        f"image's own file and the machine fails its keyboard check on first boot")
require(re.search(rf'XKBLAYOUT="{re.escape(_layouts)}"',
                  code(read("system_files/usr/libexec/moos-firstboot"))),
        f"moos-firstboot's XKBLAYOUT default must be the image's layout list ({_layouts}) — it is "
        f"what an unattended install writes over 00-keyboard.conf")

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
require("for _f in moos.script logo.png ring.png ring2.png head.png glow.png particle.png pulse.png" in build_sh,
        "build.sh must PROVE the script + ALL SEVEN sprites landed — a missing ScriptFile or "
        "sprite silently drops the boot to the text splash, with every other gate green")
for _asset in ("moos.script", "logo.png", "ring.png", "ring2.png", "head.png", "glow.png",
               "particle.png", "pulse.png"):
    require((theme_dir / _asset).is_file(),
            f"the moos Script theme must ship {_asset} — the splash aborts to text without it")
_moos_cfg = (theme_dir / "moos.plymouth").read_text(encoding="utf-8")
require("ModuleName=script" in _moos_cfg,
        "moos.plymouth must select the script module")
require("ScriptFile=/usr/share/plymouth/themes/moos/moos.script" in _moos_cfg,
        "moos.plymouth must point ScriptFile at moos.script")
_moos_script = (theme_dir / "moos.script").read_text(encoding="utf-8")
for _spr in ('Image("logo.png")', 'Image("ring.png")', 'Image("ring2.png")', 'Image("head.png")',
             'Image("glow.png")', 'Image("particle.png")', 'Image("pulse.png")'):
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
# The provider config must be WRITTEN, and it must point at THIS ACCOUNT'S gateway.
#
# This used to demand the literal "127.0.0.1:8080/v1", and that literal was the bug: 8080
# is uid 1000's gateway, so on a machine with a second account the config pointed the
# second tenant's coding agent at the FIRST tenant's gateway — the one process holding the
# cloud API key. The requirement is therefore stated as the property (a loopback gateway
# URL built from the INJECTED per-user port), which is strictly stronger than the literal:
# it still fails if the config write is dropped, and now also fails if the port is
# hardcoded back.
require("opencode.json" in do_code, "moai-do install-opencode must WRITE the provider config "
        "— an agent installed with no provider is indistinguishable from a broken one")
require(re.search(r'baseURL"\s*:\s*"http://127\.0\.0\.1:\$\{?\w*[Gg]w_?[Pp]ort\}?/v1"', do_code)
        or re.search(r'baseURL"\s*:\s*"http://127\.0\.0\.1:\$\{MOAI_GATEWAY_PORT[^}]*\}/v1"', do_code),
        "moai-do install-opencode must point the provider at THIS account's gateway, built from "
        "the injected MOAI_GATEWAY_PORT — a hardcoded 8080 sends a second tenant's agent to "
        "uid 1000's gateway and its cloud key")
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
# uupd is the OTHER unpriced background updater, and on this machine it is now the more
# expensive of the two: 1min 16.195s in `systemd-analyze blame`, top of the list. Its timer
# is OnCalendar=04:00 Persistent=true, so a desktop that was off at 4 AM runs it inside the
# first fifteen minutes of the session — the same window the flatpak updater was moved out
# of. Fixing one and leaving the other is fixing half a boot.
# And the update that runs must be able to report success. uupd's Brew module is on by
# default and points at /home/linuxbrew/.linuxbrew/bin/brew — a path MoOS never creates,
# because MoOS does not ship Homebrew. The module therefore fails on every machine, every
# night, and uupd ends the whole run with "Updates finished with errors!" while the image,
# the Flatpaks and the distroboxes all updated perfectly. Observed on this machine:
# `module_fail … "Context":"Brew Update"` in the boot's uupd journal.
#
# An updater that always reports failure is an updater nobody reads — the night something
# genuinely breaks looks exactly like every other night.
_uupd_cfg = json.loads(read("system_files/etc/uupd/config.json"))
require(_uupd_cfg["modules"]["brew"]["disable"] is True,
        "uupd's Brew module must be disabled — MoOS ships no Homebrew, so the module can "
        "only ever fail and make every automatic update report errors")
for _mod in ("distrobox", "flatpak", "system"):
    require(_uupd_cfg["modules"][_mod]["disable"] is False,
            f"uupd's {_mod} module must stay enabled — disabling it silently stops that "
            "half of the update")

# EXACTLY ONE UPDATER MAY BE ENABLED.
#
# The base image enables rpm-ostreed-automatic.timer, and it was left running beside uupd:
# measured on the maintainer's machine BOTH were enabled and active, and `rpm-ostree upgrade`
# reported "note: automatic updates (stage) are enabled". Two updaters on one OSTree sysroot
# contend for the same transaction lock, so when both fire one of them just fails.
#
# Worse, the second one defeats a deliberate policy. uupd is conditional — the config above
# refuses to update below 20% battery, above 50% CPU or 90% memory, or while the network is
# busy — and its drop-in keeps it off the login path. rpm-ostreed-automatic honours none of
# that: 1h after boot and then daily, whatever the user is doing. It also stages deployments
# outside the path `moai-do update` and Recovery are built around, which is how a staged
# update appears that nobody asked for.
_build_sh = read("build_files/build.sh")     # build_script is defined further down this file
require("systemctl enable uupd.timer" in _build_sh,
        "uupd must be the enabled updater — it is the one MoOS configures and guards")
for _rival in ("rpm-ostreed-automatic.timer", "bootc-fetch-apply-updates.timer"):
    require(re.search(rf"systemctl disable {re.escape(_rival)}", _build_sh),
            f"{_rival} must be explicitly disabled in the image. uupd already covers the "
            f"system image (its config has \"system\": {{\"disable\": false}}), so leaving a "
            f"second updater enabled only adds a lock fight and an unguarded update that "
            f"ignores MoOS's battery/CPU/memory/network conditions.")
# uupd unmarshals this file STRICTLY: one key it does not know and it refuses to start at
# all — "'config.Config' has invalid keys" — which is worse than the failing module this
# file exists to silence. Learned the hard way: a JSON block explaining WHY brew is off,
# added for the next reader, made the updater refuse to run on a shipped image.
#
# JSON has no comments. The reasoning lives here and in the commit, and the config stays
# exactly the shape the tool accepts.
require(set(_uupd_cfg) <= {"checks", "modules"},
        f"unknown top-level key in uupd's config ({sorted(set(_uupd_cfg) - {'checks', 'modules'})}) "
        "— uupd rejects the whole file and stops updating, it does not ignore extras")
require(set(_uupd_cfg["modules"]) <= {"brew", "distrobox", "flatpak", "system"},
        "unknown module key in uupd's config — uupd refuses to start on any key it does "
        "not know")
require(set(_uupd_cfg["checks"]) <= {"hardware"},
        "unknown checks key in uupd's config — same strict unmarshal, same refusal")

uupd_idle = code(read("system_files/usr/lib/systemd/system/uupd.service.d/moos-idle.conf"))
require("CPUSchedulingPolicy=idle" in uupd_idle and "IOSchedulingClass=idle" in uupd_idle,
        "uupd must run at idle CPU and I/O priority — its timer fires straight after boot on "
        "any machine that was off at 04:00, i.e. exactly while the user opens their first "
        "windows")

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
require("moai-credential-store" in gateway,
        "the gateway must read the key from Mo AI's private XDG store, not config.json")

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

# Arabic from a phone is two separate contracts: getting the characters INTO the desktop, and
# getting the phone keyboard to commit them once rather than streaming composition edits.
#
# The first contract used to be "map Arabic to XKB's legacy 0x05xx keysyms". That was measured
# against a live KWin 6.7 session on a `de,ara` keymap and it is false: KWin resolves a keysym
# against the ACTIVE group only, so 'م' arrived as keycode 247 / keyval 0x1008ffb5 — a key that
# types nothing — while the D-Bus call reported success. Capitals failed the same way ('Z' typed
# 'z'), because the shift level is never applied. So Arabic is typed by borrowing the clipboard,
# which is layout-independent and carries any Unicode exactly, and this gate pins THAT — including
# the paste shortcut, because Ctrl+V is not paste in a terminal and Arabic into Konsole was
# silently doing nothing at all.
text_keysym = read("moremote/agent-linux/TextKeysym.cs")
input_injector = read("moremote/agent-linux/InputInjector.cs")
remote_screen = read("moremote/controller/src/ui/RemoteScreen.tsx")
require("ClipboardBridge.SetText" in input_injector and '"Shift", "Insert"' in input_injector,
        "Arabic must be typed via a clipboard borrow pasted with Shift+Insert (Ctrl+V is not "
        "paste in a terminal)")
require("_borrowedClip" in input_injector,
        "the clipboard borrow must be returned — typing must not silently eat the user's clipboard")
require("0x05c1" not in text_keysym,
        "legacy 0x05xx Arabic keysyms are measured NOT to work on KWin; do not reintroduce them")
require("onCompositionStart" in remote_screen and "onCompositionEnd" in remote_screen
        and "composingRef.current" in remote_screen,
        "the phone keyboard must send committed Arabic/IME text once, not stream composition edits")
require('type = "keysyms"' in input_injector and 'elif t == "keysyms":' in portal,
        "committed phone text must cross the helper pipe as one ordered keysym batch")
remote_ws = read("moremote/controller/src/lib/ws.ts")
gestures = read("moremote/controller/src/lib/gestures.ts")
# Coalescing is adaptive, because the two typing paths cost wildly different amounts. Keysym text
# must still go out within one 60 Hz frame — English typing does not get slower to serve Arabic —
# while text needing a clipboard borrow batches into words rather than one round trip per letter.
require("FAST_FLUSH_MS = 12" in remote_ws,
        "phone text the agent can type by keysym must still flush within one 60 Hz frame")
require("CLIPBOARD_FLUSH_MS" in remote_ws and "FAST_TEXT" in remote_ws,
        "text needing a clipboard borrow must batch into words, not one borrow per letter")
require("Continue below and deliver this first meaningful delta" in gestures,
        "touch must deliver its first meaningful movement instead of feeling sticky")
# The touch slop is a RANGE, not a literal. This assertion used to also require
# "MOVE_THRESHOLD = 5", bundled in with the sticky-movement check it has nothing to do with — and
# 5 CSS px is not a slop, it is a rounding error. A thumb travels that far before it has finished
# landing, which committed the gesture to "scroll", and onUp had no case for "scroll", so an ordinary
# tap sent no click AT ALL. Two tests pinned that value and both were holding the bug in place.
#
# What must hold is that the number sits in the band every touch platform picked for the same
# tap-versus-swipe decision (iOS ~10pt, Android scaled touch slop ~8dp), and that a gesture which
# crossed the line can still be rescued as a tap when it ends.
_slop = re.search(r"MOVE_THRESHOLD = (\d+)", gestures)
require(bool(_slop) and 8 <= int(_slop.group(1)) <= 20,
        "the touch slop must be a real slop (8..20 CSS px), not a rounding error that eats taps")
require('case "scroll":' in gestures and "TAP_RESCUE_MS" in gestures,
        "a short, small gesture must still be rescued as a tap — otherwise a wobbled tap sends nothing")

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
# THE PROPERTY, NOT THE EXPRESSION THAT USED TO CARRY IT.
#
# This asserted the literal `_portal.SetStreaming(!_sessionH264.IsEmpty)`, and that pinned the gate
# to one implementation of the rule instead of to the rule. "Somebody is watching" got STRICTER —
# a connected viewer whose page is hidden (phone in a pocket, tab in the background) is connected
# and is not watching, and the old expression counted it. Measured on this machine, a backgrounded
# tab had 7.3 MB of frames sitting unread in its receive buffer: the encoder was running, the
# compositor was copying, and nobody was looking at any of it.
#
# So the gate now checks what it always meant: that streaming is driven by a predicate over the
# viewers, that an empty room is never streamed to, and that silence from a client is read as
# "watching" — because an older controller never sends the flag, and a viewer that is starved of
# frames for not answering a question it was never asked is the worse failure of the two.
require(re.search(r"_portal\.SetStreaming\((?!false)\w", capture_code),
        "the encoder must run exactly while somebody is watching — no more, and no less")
require("public void SessionWatching(Guid id, bool watching)" in capture_code,
        "a viewer must be able to say it has stopped looking, or a phone in a pocket keeps paying "
        "for frames nobody sees")
require("if (_sessionH264.IsEmpty) return false;" in capture_code,
        "an empty room must never be judged to be watching")
require("if (!_sessionWatching.TryGetValue(id, out var w) || w) return true;" in capture_code,
        "a client that never sends the flag counts as WATCHING — an older controller must not be "
        "starved of frames for not answering a question it has never heard")
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
# THE MANIFEST MUST NOT FORCE THE PHONE TO ROTATE.
#
# This gate used to REQUIRE orientation:"landscape", on the reasoning that a desktop fitted
# into a portrait phone is a stamp between two black bars. That reasoning is about the
# PICTURE, and the manifest does not control the picture — it controls the PHONE. Android
# and Chrome apply the manifest's orientation to every launch of the INSTALLED app, and this
# app actively tells the user to "Add to Home Screen", so the installed case is the common
# one. The result was a phone that spun sideways on its own every time the remote opened,
# which the owner reported twice and explicitly asked to control themselves.
#
# So the gate is inverted, not deleted: the requirement is now that the manifest never pins
# an orientation. The picture problem it was really about is solved where it belongs — in
# the app, by the Sideways lock the user chooses (see shouldRotate in RemoteScreen.tsx).
_manifest_orientation = re.search(r'"orientation"\s*:\s*"([a-z-]+)"', manifest)
require(_manifest_orientation is None or _manifest_orientation.group(1) == "any",
        "the shipped web app manifest pins orientation="
        f"{_manifest_orientation.group(1) if _manifest_orientation else '?'} — that force-rotates "
        "the phone on every launch of the installed app, which is the bug the owner reported. "
        "Use \"any\" and let the user choose with the Sideways lock.")

control = read("system_files/usr/bin/moai-control")
gateway = read("system_files/usr/bin/moai-gateway")
require('"cloud_key":' not in control,
        "Mo AI must not persist cloud_key in JSON")
require('c.get("cloud_key")' not in gateway,
        "Mo AI gateway must not read plaintext cloud_key from JSON")
credential_store = read("system_files/usr/libexec/moai-credential-store")
require("moai-credential-store" in control and "moai-credential-store" in gateway,
        "Mo AI cloud credentials must use its private XDG store")
require("secret-tool" not in control and "secret-tool" not in gateway,
        "Mo AI's runtime must not activate KWallet through Secret Service")
require("0o700" in credential_store and "0o600" in credential_store
        and "os.replace" in credential_store and "O_NOFOLLOW" in credential_store,
        "Mo AI's private credential store must enforce directory/file permissions, "
        "atomic replacement and no-follow reads")
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
require("superseded by the hero's premium suggestion cards" not in _moai_qml,
        "Mo AI still instantiates its hidden superseded starter panel")

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
require('route == "/pull"' in code(control)
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
        and "ALLOWED_LOCAL_UNITS" in gateway_code
        and '"11434" if LOCAL_BACKEND == "ollama" else "8081"' in gateway_code,
        "moai-gateway must keep 8080 as the front door and derive the selected "
        "allowlisted local engine's real port (RamaLama 8081 / Ollama 11434)")

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
require('UNIT="$("$ENGINE_HELPER" unit)"' in idle_watch
        and 'systemctl --user stop "$UNIT"' in idle_watch,
        "moai-idle must STOP the selected allowlisted local engine when idle — a "
        "watchdog that only measures idleness frees no VRAM")
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
        and 'low.startswith("cloud:")' in gateway_code
        and 'low.startswith("hybrid:")' in gateway_code,
        "moai-gateway must route on the request's model field: local:<m> / cloud:<m> / hybrid")
require('mode in ("local", "cloud", "hybrid")' in gateway_code
        and 'brain = mode if mode in' in gateway_code,
        "a request that names no brain must fall back to the configured default in "
        "config.json (local, cloud or hybrid), or every existing client breaks. "
        "Gate the assignment in resolve(), not only a mode expression elsewhere.")

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
require("let selectedRoute = root.route" in moai_qml
        and "model: selectedRoute" in moai_qml,
        "Mo AI must send the chosen route (or the locally installed VL route selected for "
        "an attached image) as the request's model field")
require("function pickRoute(" in moai_qml and "root.pickRoute(" in moai_qml
        and "function loadModels()" in moai_qml and "root.loadModels()" in moai_qml,
        "Mo AI must offer the brain/model picker and populate it from moai-control")

# moai-start writes the EnvironmentFile that outranks the unit. If it defaults the
# port to 8080 again, every `moai-start` puts the local brain back on top of the
# front door — which is the bug this whole change is undoing. (Gating for the
# literal "MOAI_PORT=8080" is not enough: the file writes MOAI_PORT=$PORT, so the
# 8080 never appears as a string.)
moai_start_code = code(read("system_files/usr/bin/moai-start"))
require('/usr/libexec/moai-local-engine' in moai_start_code
        and 'PORT="${MOAI_PORT:-$("$ENGINE_HELPER" port)}"' in moai_start_code,
        "moai-start must take the selected allowlisted engine and its port from "
        "the shared resolver; it must never put a migrated Ollama machine back on RamaLama")
require('if [ "$BACKEND" = "ramalama" ]; then\n            systemctl --user disable --now "$SERVICE"'
        in moai_start_code
        and 'systemctl --user stop "$SERVICE"' in moai_start_code,
        "moai-start stop must disable the native RamaLama unit but only stop a "
        "generated Quadlet service; systemctl cannot disable a generated unit")
require('if [ "$BACKEND" = "ramalama" ]; then\n    systemctl --user enable --now "$SERVICE"'
        in moai_start_code
        and 'systemctl --user start "$SERVICE"' in moai_start_code
        and 'systemctl --user is-active --quiet "$SERVICE"' in moai_start_code,
        "moai-start must start and verify a generated Ollama Quadlet instead of "
        "trying the unsupported enable --now operation")
build_script = read("build_files/build.sh")
# These units all ship in the image and start /usr binaries, so build.sh can
# systemd-analyze verify them. openclaw-gateway.service is deliberately NOT in
# this list: its ExecStart is %h/.local/bin/openclaw, a per-user runtime install
# (moai-do install-openclaw) that is not in the image, so systemd-analyze verify
# resolves %h to /root and fails the whole build. A unit whose command is a user
# install cannot be build-time verified; its runtime guard is
# ConditionFileIsExecutable and its in-image ExecStartPre is covered elsewhere.
for runtime_unit in (
    "moai.service", "moai-gateway.service", "moai-control.service",
    "moai-idle.service", "moai-idle.timer", "moos-ensure-brain.service",
    "moos-ensure-brain.timer",
    "openclaw-idle.service", "openclaw-idle.timer", "moai-agent-api.service",
):
    require(f"/usr/lib/systemd/user/{runtime_unit}" in build_script,
            f"the image build must systemd-verify Mo AI runtime unit {runtime_unit}")

# NOTHING SLOW MAY SIT ON THE PATH BETWEEN LOGIN AND THE DESKTOP.
#
# moos-ensure-brain is Type=oneshot with RemainAfterExit, so any target that Wants it
# WAITS for it to exit. It was WantedBy=default.target, and it queries the model backend,
# which is slow whether or not there is work to do. Measured on the maintainer's machine:
#
#     default.target @9.440s
#     └─moos-ensure-brain.service @1.490s +7.949s
#
# — 7.9 of the session's 9.4 seconds, to log "brain already correct — nothing to do". Its
# own unit file says "never let it block the session"; the Install section was what made it
# do exactly that. It is started by moos-ensure-brain.timer now, and must not go back.
_ensure_brain_unit = read("system_files/usr/lib/systemd/user/moos-ensure-brain.service")
require("WantedBy=default.target" not in code(_ensure_brain_unit, "hash"),
        "moos-ensure-brain.service is WantedBy=default.target again. It is a Type=oneshot, so "
        "the session waits for it to finish — that put ~8 seconds of model queries between the "
        "user logging in and their desktop appearing. Start it from moos-ensure-brain.timer.")
require("systemctl --global enable moos-ensure-brain.timer" in build_script,
        "the image must enable moos-ensure-brain.timer — without it the brain reconcile never "
        "runs at all, since the service no longer has an [Install] section")
_ensure_brain_timer = code(
    read("system_files/usr/lib/systemd/user/moos-ensure-brain.timer"), "hash")
require("OnStartupSec=" in _ensure_brain_timer,
        "moos-ensure-brain.timer must fire relative to session start (OnStartupSec), so the "
        "reconcile still happens every login — just after the desktop, not before it")
require("systemctl --global enable moai-agent-api.service" in build_script,
        "the Agent settings API must persist across logout/reboot for every user")
agent_api_unit = code(
    read("system_files/usr/lib/systemd/user/moai-agent-api.service"), "hash")
require("ExecStartPre=-/usr/libexec/moai-openclaw-bootstrap --existing-only"
        in agent_api_unit,
        "existing OpenClaw users must receive the preserving schema migration "
        "without creating configs for accounts that never installed the agent")
agent_api_code = code(read("system_files/usr/bin/moai-agent-api"))
control_http_code = code(read("system_files/usr/bin/moai-control"))
require('API_HEADER = "X-Moai-Agent"' in agent_api_code
        and "MAX_BODY_BYTES = 1024 * 1024" in agent_api_code
        and 'self.headers.get("Transfer-Encoding")' in agent_api_code
        and 'self.headers.get_all("Content-Length")' in agent_api_code
        and 'self.send_header("X-Frame-Options", "DENY")' in agent_api_code
        and "Content-Security-Policy" in agent_api_code,
        "the credential-writing Agent API must require its non-CORS header, bound "
        "request bodies before reading, reject transfer encoding, and deny framing")
require('self.headers.get("X-Moai-Control") != "1"' in control_http_code
        and "MAX_BODY_BYTES = 1024 * 1024" in control_http_code
        and 'self.headers.get("Transfer-Encoding")' in control_http_code
        and 'self.headers.get_all("Content-Length")' in control_http_code
        and "CONFIG_LOCK = threading.RLock()" in control_http_code
        and "os.replace(tmp_name, CFG)" in control_http_code,
        "moai-control must enforce the same loopback browser boundary and commit "
        "private settings atomically under a process-wide lock")
require("property bool agentStatusLoaded" in moai_qml
        and "readonly property bool agentMachineConfigured" in moai_qml
        and "readonly property bool agentReady" in moai_qml
        and "moos://do/install-openclaw" in moai_qml
        and "moos://do/setup-brain" in moai_qml
        and "enabled: root.agentReady && !root.agentBusy" in moai_qml,
        "the Agent panel must read real installation/configuration status, offer "
        "working setup actions for missing pieces, and disable chat until ready")
openclaw_bootstrap = code(
    read("system_files/usr/libexec/moai-openclaw-bootstrap"))
require('"type": "cli"' in openclaw_bootstrap
        and '"args": ["{{MediaPath}}"]' in openclaw_bootstrap
        and 'object_at(object_at(tools, "media"), "audio")' in openclaw_bootstrap
        and 'legacy_audio.pop("transcription", None)' in openclaw_bootstrap
        and '"audio.transcription"' not in openclaw_bootstrap,
        "OpenClaw voice input must use the current tools.media.audio CLI schema "
        "and migrate the retired audio.transcription key before validation")
openclaw_unit = code(
    read("system_files/usr/lib/systemd/user/openclaw-gateway.service"), "hash")
require("ExecStartPre=/usr/libexec/moai-openclaw-preflight" in openclaw_unit
        and "Requires=ollama.service" not in openclaw_unit
        and "Requires=moai-brain.service" not in openclaw_unit
        and "Restart=always" in openclaw_unit,
        "the phone agent must resolve either allowlisted Ollama Quadlet at runtime")
openclaw_idle = code(read("system_files/usr/bin/openclaw-idle"))
require('c.get("enabled") is True' in openclaw_idle
        and 'if [ "$keep_gateway" != 1 ]; then' in openclaw_idle
        and 'if [ "$resident" = "0" ] && [ "$keep_gateway" != 1 ]; then'
        in openclaw_idle,
        "a configured WhatsApp Web channel must keep its only inbound receiver "
        "alive while Ollama's own keep-alive unloads the idle model")
moai_wake = code(read("system_files/usr/bin/moai-wake"))
require("if started.returncode != 0:" in moai_wake
        and "if not gateway_active():" in moai_wake
        and "if start_gateway():" in moai_wake
        and "send_start_failure" in moai_wake,
        "the Telegram wake receiver must verify the real gateway start before "
        "claiming success, and must report a failed start without retrying forever")
ensure_brain_code = code(read("system_files/usr/bin/moos-ensure-brain"))
require("os.chmod(tmp,0o600)" in ensure_brain_code
        and "os.replace(tmp,p)" in ensure_brain_code,
        "the OpenClaw context migration must preserve credential-file privacy "
        "when atomically rewriting openclaw.json")
moai_idle_code = code(read("system_files/usr/bin/moai-idle"))
require("systemctl --user is-active --quiet openclaw-gateway.service"
        in moai_idle_code
        and "case \"$openclaw_primary\" in" in moai_idle_code
        and "cloud/*) : ;;" in moai_idle_code,
        "moai-idle must defer local-primary Ollama teardown while OpenClaw is "
        "active; openclaw-idle owns the required gateway-before-engine ordering")

brain_quadlet = read("system_files/usr/share/moos/containers/moai-brain.container")
speech_quadlet = read("system_files/usr/share/moos/containers/speaches.container")
require("AddDevice=nvidia.com/gpu=all" not in brain_quadlet
        and "SecurityLabelDisable=true" not in brain_quadlet
        and "# MOOS_NVIDIA_CDI_INSERT" in brain_quadlet,
        "the shared local-brain template must start on generic/Intel/AMD/VM "
        "systems; NVIDIA-only CDI directives may be inserted only after runtime detection")
for runtime_quadlet, runtime_name in (
    (brain_quadlet, "local brain"),
    (speech_quadlet, "speech engine"),
):
    runtime_lines = {line.strip() for line in runtime_quadlet.splitlines()}
    require("[Install]" not in runtime_lines
            and "WantedBy=default.target" not in runtime_lines,
            f"the {runtime_name} Quadlet must stay on demand instead of starting "
            "at every login")
moai_do_code = code(read("system_files/usr/bin/moai-do"))
require("nvidia-ctk cdi list" in moai_do_code
        and "nvidia-smi --query-gpu=name" in moai_do_code
        and "installed_model_quadlet" in moai_do_code
        and "AddDevice=nvidia.com/gpu=all" in moai_do_code,
        "setup-brain must add NVIDIA CDI acceleration only when both the driver "
        "and the exact CDI device are present")
require('run_priv /usr/bin/loginctl enable-linger "$login_user"' in moai_do_code
        and moai_do_code.count(
            'loginctl show-user "$login_user" -p Linger --value') >= 2,
        "setup-brain must explicitly authorize and verify linger; silently ignoring "
        "its Polkit failure makes the phone agent disappear after logout")
require("http://127.0.0.1:11434/api/tags" in moai_do_code
        and '"default" in names' in moai_do_code
        and "strip_legacy_moos_quadlet_autostart" in moai_do_code
        and moai_do_code.index("restart moos-ensure-brain.service")
            < moai_do_code.index("http://127.0.0.1:11434/api/tags")
            < moai_do_code.index("MOAI_LOCAL_UNIT=$model_unit")
            < moai_do_code.index('echo "${G}✓ جاهز | ready${N}"'),
        "setup-brain must verify Ollama really contains the routed default model "
        "before committing its route or claiming that the phone agent is ready, "
        "and migrate only the known legacy always-on Quadlets")

# The versioned migration is what makes the redesign visible to existing users.
apply_theme = read("system_files/usr/bin/moos-apply-theme")
apply_theme_code = code(apply_theme)
require("THEME_REV=28" in apply_theme_code,
        "MoOS visual schema must migrate existing users to the themed lock screen")
require('[ "$lockscreen" = "$wallpaper_package" ]' in apply_theme_code,
        "THEME_REV 28 must read back the exact lock wallpaper package, not a prefix")
require('[ "$lock_image" = "$wallpaper_package" ] || return 1' in code(read("system_files/usr/bin/moos-theme")),
        "manual/automatic theme switching must reject a light/dark lock wallpaper mismatch")
require(
    "local_icons=" in apply_theme_code
    and "moos-*" in apply_theme_code
    and "MoOSUI2*" in apply_theme_code
    and "icon-theme.cache" in apply_theme_code,
    "THEME_REV 27 must purge ~/.local/share/icons/MoOSUI2* and hicolor moos-* overrides "
    "so baked app marks from /usr win over live-preview residue",
)
# Rev 12 carries a rewritten desk widget (weather + rolling digits), and a plasmoid does not
# reach an existing user by being newer. OSTree pins every mtime under /usr to the epoch and
# Qt's qmlcache is keyed on mtime, so plasmashell happily keeps executing the COMPILED OLD
# widget after the upgrade — the file changed, the cache did not notice, and the user sees
# last month's clock. apply-theme purges the QML caches on every THEME_REV.
require("qmlcache" in apply_theme_code,
        "moos-apply-theme must purge the QML disk cache on a THEME_REV bump — OSTree's frozen "
        "mtimes mean a rebuilt plasmoid is invisible to qmlcache, and the old widget keeps "
        "running")

# Existing users never re-run layout.js.  Their live panel becomes the new
# one-launcher architecture only through this revisioned migration.  Require
# creation-before-removal: if the new package fails to add, keeping Kickoff for
# one more login is preferable to removing the user's only launcher.
brand_add_pos = apply_theme_code.find('addWidget("org.moos.brand")')
kickoff_capture_pos = apply_theme_code.find('w.type == "org.kde.plasma.kickoff"')
brand_guard_pos = apply_theme_code.find("if (brandWidget != null)", kickoff_capture_pos)
brand_reload_pos = apply_theme_code.find("brandWidget.reloadConfig()", brand_guard_pos)
kickoff_remove_pos = apply_theme_code.find("kickoffWidget.remove()", brand_guard_pos)
require(brand_add_pos >= 0 and kickoff_capture_pos >= 0
        and "brandWidget = wsScan[b]" in apply_theme_code
        and "brandWidget = brand" in apply_theme_code
        and brand_guard_pos >= 0 and brand_reload_pos >= 0 and kickoff_remove_pos >= 0
        and apply_theme_code.count("kickoffWidget.remove()") == 1
        and brand_add_pos < kickoff_capture_pos < brand_guard_pos
        < brand_reload_pos < kickoff_remove_pos,
        "THEME_REV 21 must ensure org.moos.brand exists before removing the old Kickoff "
        "from an existing user's panel")
require(re.search(r"--key\s+popupWidth\s+792\b", apply_theme_code) is not None
        and re.search(r"--key\s+popupHeight\s+576\b", apply_theme_code) is not None,
        "the existing org.moos.brand applet's shell-owned popup geometry must migrate to "
        "792x576; QML implicitWidth/Height cannot override persisted appletsrc values")

# evaluateScript returning over D-Bus proves only that the JavaScript finished;
# its guarded applet operations may all have failed.  Revision 21 therefore has
# a second event-loop readback with a machine-readable sentinel.  The permanent
# version marker is allowed only after that sentinel was parsed as OK=1, or one
# transient Plasma/package failure would suppress every future retry.
launcher_ok_init_pos = apply_theme_code.find("launcher_migration_ok=0")
launcher_state_pos = apply_theme_code.find('launcher_migration_state="$(')
launcher_sentinel_pos = apply_theme_code.find("MOOS_LAUNCHER_MIGRATION_OK=", launcher_state_pos)
launcher_invariant_pos = apply_theme_code.find(
    "panelBrands == 1 && panelLegacy == 0 && panelConfigured == 1",
    launcher_state_pos,
)
launcher_parse_pos = apply_theme_code.find(
    "grep -q 'MOOS_LAUNCHER_MIGRATION_OK=1'", launcher_sentinel_pos,
)
launcher_ok_set_pos = apply_theme_code.find("launcher_migration_ok=1", launcher_parse_pos)
marker_launcher_guard_pos = apply_theme_code.find(
    '[ "${launcher_migration_ok:-0}" = "1" ]', launcher_ok_set_pos,
)
version_marker_touch_pos = apply_theme_code.find('touch "$marker"', marker_launcher_guard_pos)
require(launcher_ok_init_pos >= 0 and launcher_state_pos > launcher_ok_init_pos
        and launcher_sentinel_pos > launcher_state_pos
        and launcher_invariant_pos > launcher_state_pos
        and launcher_parse_pos > launcher_sentinel_pos
        and launcher_ok_set_pos > launcher_parse_pos
        and marker_launcher_guard_pos > launcher_ok_set_pos
        and version_marker_touch_pos > marker_launcher_guard_pos
        and apply_theme_code.count('touch "$marker"') == 1,
        "THEME_REV 21 must read the live panel back through its "
        "MOOS_LAUNCHER_MIGRATION_OK sentinel and must not write the permanent "
        "version marker unless that readback produced OK=1")

# A retry can begin with the revision's tray restart marker already present:
# the first attempt may have restarted Plasma for an unrelated dock/tray write
# while leaving the launcher migration incomplete.  Track actual launcher
# mutations, and invalidate that stale restart marker only after a successful
# live readback.  Conversely, an already-converged retry must not restart the
# shell on every login.
launcher_changed_init_pos = apply_theme_code.find("launcher_changed=0", launcher_ok_init_pos)
launcher_force_init_pos = apply_theme_code.find(
    "launcher_force_restart=0", launcher_changed_init_pos,
)
launcher_mutation_pos = apply_theme_code.find(
    'launcher_mutation_state="$(' , launcher_force_init_pos,
)
launcher_changed_sentinel_pos = apply_theme_code.find(
    "MOOS_LAUNCHER_CHANGED=", launcher_mutation_pos,
)
launcher_changed_parse_pos = apply_theme_code.find(
    "MOOS_LAUNCHER_CHANGED=[1-9][0-9]*", launcher_changed_sentinel_pos,
)
launcher_changed_set_pos = apply_theme_code.find(
    "launcher_changed=1", launcher_changed_parse_pos,
)
launcher_force_set_pos = apply_theme_code.find(
    "launcher_force_restart=1", launcher_ok_set_pos,
)
tray_marker_pos = apply_theme_code.find('tray_marker="${state_dir}/', launcher_force_set_pos)
launcher_force_guard_pos = apply_theme_code.find(
    '[ "${launcher_force_restart:-0}" = "1" ]', tray_marker_pos,
)
tray_marker_remove_pos = apply_theme_code.find(
    'rm -f "$tray_marker"', launcher_force_guard_pos,
)
tray_restart_pos = apply_theme_code.find(
    '[ ! -e "$tray_marker" ]', tray_marker_remove_pos,
)
require(launcher_changed_init_pos > launcher_ok_init_pos
        and launcher_force_init_pos > launcher_changed_init_pos
        and launcher_mutation_pos > launcher_force_init_pos
        and apply_theme_code.count("launcherChanged++") >= 3
        and launcher_changed_sentinel_pos > launcher_mutation_pos
        and launcher_changed_parse_pos > launcher_changed_sentinel_pos
        and launcher_changed_set_pos > launcher_changed_parse_pos
        and launcher_force_set_pos > launcher_ok_set_pos
        and tray_marker_pos > launcher_force_set_pos
        and launcher_force_guard_pos > tray_marker_pos
        and tray_marker_remove_pos > launcher_force_guard_pos
        and tray_restart_pos > tray_marker_remove_pos,
        "launcher retries must force one Plasma restart after a real, verified Brand/client/"
        "Kickoff mutation, while an already-converged retry must keep the restart marker")

# The live diagnostics must measure the same surface the migration owns.  A
# user may intentionally place Kicker/KickerDash on a side or top panel; MoOS
# manages bottom panels and replaces only the old default Kickoff there.
post_update_check = code(read("tests/post-update-check.sh"))
for runtime_check, check_name in (
    (selfcheck, "moos-selfcheck"),
    (post_update_check, "post-update-check"),
):
    launcher_check_start = runtime_check.find("launcher_runtime_state()")
    launcher_check_end = runtime_check.find("head_", launcher_check_start + 1)
    launcher_check = runtime_check[launcher_check_start:launcher_check_end]
    require(launcher_check_start >= 0
            and 'location != "bottom"' in launcher_check
            and 'print("bottom="' in launcher_check
            and 'kind == "org.kde.plasma.kickoff"' in launcher_check
            and "org.kde.plasma.kicker" not in launcher_check
            and "org.kde.plasma.kickerdash" not in launcher_check
            and 'currentConfigGroup = []' in launcher_check
            and "panelBrands == 1 && panelLegacy == 0 && panelSized == 1" in launcher_check
            and '";valid=" + valid' in launcher_check
            and 'brand_count" = "$bottom_count' in runtime_check
            and 'sized_count" = "$brand_count' in runtime_check
            and 'valid_count" = "$bottom_count' in runtime_check,
            f"{check_name} must validate one sized Brand and no old Kickoff per managed "
            "bottom panel, while ignoring intentional top/side Kicker launchers")

# A package staged under ~/.local/share outranks the new image forever.  Brand
# and Hero Clock were both staged during live visual work, so they belong in the
# same MoOS-owned cleanup list as the other first-party plasmoids.
shadow_cleanup_start = apply_theme_code.find('user_share="${XDG_DATA_HOME:-$HOME/.local/share}"')
shadow_cleanup_end = apply_theme_code.find("tray_marker=", shadow_cleanup_start)
shadow_cleanup = apply_theme_code[shadow_cleanup_start:shadow_cleanup_end]
for shadowed_plasmoid in ("org.moos.brand", "org.moos.heroclock"):
    require(f'"plasma/plasmoids/{shadowed_plasmoid}"' in shadow_cleanup,
            f"moos-apply-theme must remove a user-local {shadowed_plasmoid} copy that "
            "would otherwise shadow every future image update")

PALETTE_ICON_OVERLAYS = (
    "MoOSUI2Amethyst", "MoOSUI2AmethystLight",
    "MoOSUI2Arena", "MoOSUI2ArenaLight",
    "MoOSUI2Aurora", "MoOSUI2AuroraLight",
    "MoOSUI2Daylight",
    "MoOSUI2Forge", "MoOSUI2ForgeLight",
    "MoOSUI2Midnight",
    "MoOSUI2Nova", "MoOSUI2NovaLight",
    "MoOSUI2Scholar", "MoOSUI2ScholarLight",
)
for icon_overlay in PALETTE_ICON_OVERLAYS:
    require(
        f'"icons/{icon_overlay}"' in shadow_cleanup,
        f"moos-apply-theme must remove a user-local {icon_overlay} icon package "
        "that would permanently shadow the palette bridge in the image",
    )
    # Delimiter-aware: "icons/MoOSUI2Nova" is a substring of
    # "icons/MoOSUI2NovaLight", so a plain `in` can never bite for the six
    # dark palettes whose Light sibling is also listed.
    require(
        re.search(rf"icons/{re.escape(icon_overlay)}(?![A-Za-z])", selfcheck)
        is not None,
        f"moos-selfcheck must report a user-local {icon_overlay} shadow",
    )
require(
    'want_ico="$want_sty"' in selfcheck,
    "moos-selfcheck must validate each family member's palette-specific icon "
    "overlay rather than accepting the shared dark/light base",
)

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

# KIconLoader renders a normal themed SVG with the fallback colours embedded in
# that icon package. Reusing MoOSUI2/MoOSUI2Light for every family member made
# Arena's dark launcher draw the light fallback ink almost black. The Global
# Theme must therefore select the symbolic overlay named after its own Plasma
# style; the overlay inherits the broad base vocabulary separately.
for package in FAMILY_LNF:
    defaults = code(read(
        f"system_files/usr/share/plasma/look-and-feel/{package}/contents/defaults"
    ))
    family_style = kconfig_value(defaults, "plasmarc][Theme", "name")
    family_icons = kconfig_value(defaults, "kdeglobals][Icons", "Theme")
    require(
        family_style and family_icons == family_style,
        f"{package} must select its own palette-matched symbolic icon overlay "
        f"({family_style or 'missing style'}); found {family_icons or 'missing icon theme'}",
    )
    if package not in ("org.moos.ui2", "org.moos.ui2.light"):
        family_scheme = kconfig_value(
            defaults, "kdeglobals][General", "ColorScheme"
        )
        require(
            family_scheme == family_style,
            f"{package} icon/style palette {family_style or 'missing'} must match "
            f"its colour scheme {family_scheme or 'missing'}",
        )

require(
    apply_theme_code.count('expected_icons="$expected_style"') == 5
    and apply_theme_code.count('want_icons="$want_style"') == 5,
    "moos-apply-theme must validate and pin every non-base family member's "
    "palette-specific icon overlay instead of collapsing them to MoOSUI2 dark/light",
)

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
# The two base halves must each NAME their own wallpaper. This gate used to assert the
# opposite, on the belief that a [Wallpaper] here makes LookAndFeelManager force
# org.kde.image onto every containment. That is not what Plasma 6.7.3 does:
# KLookAndFeelManager::save() never reads this group (verified in plasma-workspace's
# source and in the shipped libklookandfeel.so.6.7.3, where the "Wallpaper"/"Image"
# literals are referenced only from packageContents() and remove()), and it only rebuilds
# the desktop layout for packages shipping contents/layouts/, which no MoOS look does.
# What the key DOES drive is libkworkspace's DefaultWallpaper::defaultWallpaperPackage()
# — the fallback org.kde.image and the Wallpaper KCM use — so without it, picking a MoOS
# theme in System Settings left the user's previous wallpaper in place.
for half, wallpaper in (("org.moos.ui2", "MoOSUI2Graphite"),
                        ("org.moos.ui2.light", "MoOSUI2Tide")):
    lnf_defaults = code(
        read(f"system_files/usr/share/plasma/look-and-feel/{half}/contents/defaults"))
    require(f"[Wallpaper]\nImage={wallpaper}" in lnf_defaults,
            f"{half}/contents/defaults does not name {wallpaper} as its wallpaper — "
            f"applying this Global Theme would leave the previous wallpaper in place")
    require((ROOT / f"system_files/usr/share/wallpapers/{wallpaper}").is_dir(),
            f"{half} names wallpaper package {wallpaper}, which is not shipped")

# moos-apply-theme repairs the look the user is ON, not the one MoOS prefers. Dragging a
# user who chose Light back to Dark on every login is not protection, it is the bug.
require("target_lnf()" in apply_theme_code and "theme_intact()" in apply_theme_code,
        "the self-heal must accept EITHER MoOS look and repair to the one the user chose")

ui_migrate = read("system_files/usr/bin/moos-ui-migrate")
require("MOOS_THEME_REV=10" in ui_migrate and "MOAI_UI_REV=3" in ui_migrate,
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
require("migrate_legacy_keyboard()" in ui_migrate
        and "keyboard-layout-v2.done" in ui_migrate
        and "LayoutList=de,ara" in ui_migrate
        and 'LayoutList "de,us,ara"' in ui_migrate
        and 'VariantList ",,"' in ui_migrate
        and 'DisplayNames "DE,,ع"' in ui_migrate,
        "the exact previous de,ara keyboard shadow must migrate to de,us,ara")
require(ui_migrate.index("migrate_legacy_keyboard") <
        ui_migrate.index('[ -e "$marker" ] && exit 0'),
        "the keyboard shadow repair needs its own marker and must run before "
        "the theme revision gate")
# The wallet-removal migration may copy one already-unlocked Mo AI key before it
# stops KWallet. It must not activate the service, write a wallet item, or touch
# any other credential.
require(ui_migrate.count("secret-tool lookup service org.moos.MoAI account cloud") == 1,
        "wallet removal must preserve only Mo AI's already-unlocked legacy key")
require("secret-tool store" not in ui_migrate and "secret-tool clear" not in ui_migrate,
        "UI migration must never write or delete Secret Service items")
for agent_surface in (
    read("system_files/usr/share/moos/apps/moai/main.qml"),
    read("system_files/usr/share/moos/apps/moai-agent/console.html"),
):
    require("1142563280" not in agent_surface,
            "a maintainer Telegram id must never ship as user-facing placeholder data")

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
require("library=org.kde.kwin.aurorae.v2" in kwinrc,
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
# ── One launcher, one engine: org.moos.brand IS the MoOS menu ───────────────
#
# The old panel contained two adjacent controls: org.moos.brand opened a glance
# card while Kickoff opened applications/search.  A visual redesign could make
# that look like one control without making it one.  Gate the relationship
# instead: the package in the layout is the package that advertises Plasma's
# launcher capability, and no second launcher is added beside it.
layout_code = code(re.sub(r"/\*.*?\*/", "", layout, flags=re.DOTALL), "slash")
panel_applets = re.findall(r'addWidget\(\s*"([^"]+)"\s*\)', layout_code)
require(panel_applets.count("org.moos.brand") == 1,
        "the default panel must add org.moos.brand exactly once")
legacy_panel_launchers = {
    "org.kde.plasma.kickoff", "org.kde.plasma.kicker", "org.kde.plasma.kickerdash",
}.intersection(panel_applets)
require(not legacy_panel_launchers,
        f"a second KDE launcher is back in the default panel: {sorted(legacy_panel_launchers)}; "
        "org.moos.brand must be the one MoOS launcher")
require("org.moos.nova.launcher" not in panel_applets,
        "the retired Nova launcher must not compete with org.moos.brand")
require('addWidget("org.moos.nova.clock")' in layout_code,
        "new users must receive the compact Nova clock")

# An existing profile receives this root-group geometry through the revisioned
# migration. A fresh profile never runs that migration against a pre-existing
# applet, so layout.js must seed the same shell-owned values itself. Writing
# them while currentConfigGroup is still General silently puts them where the
# popup host never reads them.
launcher_layout_pos = layout_code.find('var launcher = panel.addWidget("org.moos.brand")')
launcher_general_group_pos = layout_code.find(
    'launcher.currentConfigGroup = ["General"]', launcher_layout_pos,
)
launcher_root_group_pos = layout_code.find(
    "launcher.currentConfigGroup = []", launcher_general_group_pos,
)
launcher_popup_width_pos = layout_code.find(
    'launcher.writeConfig("popupWidth", 792)', launcher_root_group_pos,
)
launcher_popup_height_pos = layout_code.find(
    'launcher.writeConfig("popupHeight", 576)', launcher_popup_width_pos,
)
require(launcher_layout_pos >= 0 and launcher_general_group_pos > launcher_layout_pos
        and launcher_root_group_pos > launcher_general_group_pos
        and launcher_popup_width_pos > launcher_root_group_pos
        and launcher_popup_height_pos > launcher_popup_width_pos,
        "the fresh-profile org.moos.brand launcher must leave General and seed its "
        "shell-owned root popup geometry at 792x576; otherwise live selfcheck fails "
        "until the user manually opens or resizes the menu")

brand_root = ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.brand"
brand_metadata_path = brand_root / "metadata.json"
brand_metadata = json.loads(brand_metadata_path.read_text(encoding="utf-8")) \
    if brand_metadata_path.is_file() else {}
brand_id = brand_metadata.get("KPlugin", {}).get("Id")
brand_provides = set(brand_metadata.get("X-Plasma-Provides", []))
require(brand_id == "org.moos.brand" and brand_id in panel_applets,
        "the panel launcher and the org.moos.brand metadata id must name the same package")
require(brand_provides == {"org.moos.brand", "org.kde.plasma.launchermenu"},
        "org.moos.brand must advertise exactly its brand identity and Plasma's "
        "org.kde.plasma.launchermenu capability — Meta/launcher activation depends on it")

for package in ("org.moos.nova.clock", "org.moos.brand", "org.moos.heroclock"):
    root = ROOT / "system_files/usr/share/plasma/plasmoids" / package
    require((root / "metadata.json").is_file() and
            (root / "contents/ui/main.qml").is_file(),
            f"missing complete Plasma package: {package}")

brand_main_qml = code(read(
    "system_files/usr/share/plasma/plasmoids/org.moos.brand/contents/ui/main.qml"
), style="slash")
brand_qml_files = sorted((brand_root / "contents/ui").glob("*.qml"))
brand_qml = "\n".join(code(path.read_text(encoding="utf-8"), "slash")
                       for path in brand_qml_files)
launcher_view_qml = code(read(
    "system_files/usr/share/plasma/plasmoids/org.moos.brand/contents/ui/LauncherView.qml"
), style="slash")
require("if (root.expanded)" in brand_main_qml and "if (expanded)" not in brand_main_qml,
        "the brand applet must qualify root.expanded; the bare signal argument "
        "uses deprecated parameter injection and warns on every Plasma login")
require('text: "MoOS"' in brand_main_qml
        and 'root.rtl ? "مساحة الأوامر" : "COMMAND"' in brand_main_qml
        and "moos-search-symbolic" in brand_main_qml,
        "the one panel launcher must visibly remain the MoOS wordmark, Command "
        "Canvas caption and search affordance")

# Search and browsing are native model operations, not shell commands wearing a
# search field.  Each engine is instantiated in main.qml and handed to the full
# representation; this catches both a missing engine and a beautiful but dead UI.
launcher_models = {
    "Milou.ResultsModel": "searchModel: searchResults",
    "Kicker.RootModel": "applicationsModel: root.appsModel",
    "Kicker.RecentUsageModel": "recentUsageModel: recentModel",
    "Kicker.ComputerModel": "placesModel: computerModel",
    "Kicker.SystemModel": "sessionModel: systemModel",
}
for model_type, handoff in launcher_models.items():
    require(model_type in brand_main_qml and handoff in brand_main_qml,
            f"the MoOS launcher must instantiate {model_type} and hand that exact model "
            "to its visible full representation")
for visible_model in (
    "model: view.searchModel", "model: view.applicationsModel",
    "model: view.favoritesModel", "model: view.recentUsageModel",
    "model: view.placesModel", "model: view.sessionModel",
):
    require(visible_model in brand_qml,
            f"the launcher declares a native model but does not render it: {visible_model}")

# The recent strip is a deliberately short horizontal shelf below the pinned
# grid.  Qt 6's implicit layout size policy can otherwise let its nested
# ColumnLayout consume all spare height, turning each recent item into a tall,
# mostly-empty slab even though its preferred height is correct.
recent_visibility_pos = launcher_view_qml.find(
    "visible: Plasmoid.configuration.showRecent",
)
recent_layout_start = launcher_view_qml.rfind(
    "ColumnLayout {", 0, recent_visibility_pos,
)
recent_layout = launcher_view_qml[recent_layout_start:recent_visibility_pos]
require(recent_layout_start >= 0
        and "Layout.fillHeight: false" in recent_layout
        and "Layout.minimumHeight: Layout.preferredHeight" in recent_layout
        and "Layout.maximumHeight: Layout.preferredHeight" in recent_layout,
        "the recent-items shelf must be height-locked; allowing it to absorb the Home "
        "page's spare height produces giant empty cards in the live launcher")
require("queryString: root.searchQuery" in brand_main_qml
        and "searchResults.run(searchResults.index(" in brand_main_qml
        and "text: view.launcher.searchQuery" in brand_qml
        and "onTextEdited: view.launcher.searchQuery = text" in brand_qml,
        "launcher search must bind the typed query to Milou and execute Milou's result; "
        "opening a second launcher or interpolating the query into a command is not search")
require("sourceModel.trigger(" in brand_main_qml,
        "applications, recent items, places and session actions must execute through their "
        "own Kicker model so desktop actions and system semantics remain intact")
require("Kicker.SimpleFavoritesModel" in brand_main_qml
        and "launcherDestinations.trigger(" in brand_main_qml,
        "the launcher settings/theme buttons must activate desktop entries through Kicker; "
        "applications: is an internal Kicker URL, not a registered desktop URL scheme")
require('Qt.openUrlExternally("applications:' not in brand_main_qml
        and "Qt.openUrlExternally('applications:" not in brand_main_qml,
        "desktop actions must not use the unregistered applications: URL scheme")
require("activateLauncherMenu" not in brand_main_qml
        and "runner.connectSource" not in brand_main_qml,
        "org.moos.brand must contain the launcher internally, not forward to Kickoff or a "
        "free-form executable DataSource")
require('"moos-ci-full-representation"' in brand_main_qml
        and "preferredRepresentation: root.smokeFullRepresentation" in brand_main_qml,
        "the launcher needs a build-only full-representation mode; plasmawindowed otherwise "
        "loads only the compact panel button and gives the launcher a false green smoke")
require("Layout.minimumWidth: implicitWidth" in launcher_view_qml
        and "Layout.minimumHeight: implicitHeight" in launcher_view_qml
        and "MOOS_LAUNCHER_FULL_READY size=" in launcher_view_qml,
        "the full launcher must enforce and report its unclipped 792x576 representation to "
        "the plasmawindowed smoke")
# Commercial shell language: a 20px outer rhythm, 40px affordances, functional
# text no smaller than 11px, and four columns that still ride the type ramp.
# An early four-column launcher was rejected because it drove labels down to
# 7–10px; the current one is only acceptable because every pixelSize below
# stays on the 11+ type tokens — that pairing is what this gate holds, and
# densifying past four columns remains out.
_launcher_tokens = {
    "space1": 4, "space2": 8, "space3": 12, "space4": 16, "space5": 20,
    "space6": 24,
    "radiusS": 8, "radiusM": 12, "radiusL": 16, "radiusXL": 24,
    "targetSize": 40, "typeCaption": 11, "typeSecondary": 13,
    "typeBody": 14, "typeEmphasis": 15, "typeSubheading": 18, "typeTitle": 20,
}
require(all(f"readonly property int {name}: {value}" in launcher_view_qml
            for name, value in _launcher_tokens.items())
        and "anchors.margins: view.space5" in launcher_view_qml,
        "the launcher must use the unified 4px spacing, 8/12/16/24 radii, "
        "40px target and 11/13/14/15/18/20 type tokens")
require("Press Meta to open" not in launcher_view_qml
        and "يفتح بزر Meta" not in launcher_view_qml
        and launcher_view_qml.count(
            "cellWidth: Math.max(1, Math.floor(width / 4))"
        ) == 2
        and re.search(
            r"cellWidth:.*width\s*/\s*(?:[5-9]|\d{2,})", launcher_view_qml
        ) is None,
        "the open launcher must drop the redundant Meta pill and keep the calm "
        "four-column Pinned/Applications rhythm on the 11px+ type ramp")
_launcher_type_expressions = re.findall(
    r"font\.pixelSize\s*:\s*([^\n]+)", launcher_view_qml
)
require("readonly property string uiFontFamily: Qt.application.font.family"
        in launcher_view_qml
        and re.search(r'font\.family\s*:\s*"', launcher_view_qml) is None
        and _launcher_type_expressions
        and all("type" in expression for expression in _launcher_type_expressions)
        and launcher_view_qml.count("view.targetSize") >= 24,
        "launcher text must follow the session font and its readable type roles, "
        "while custom pointer affordances retain at least 40px targets")
require("readonly property string uiFontFamily: Qt.application.font.family"
        in brand_main_qml
        and re.search(r'font\.family\s*:\s*"', brand_main_qml) is None
        and "font.pixelSize: Math.max(11, Math.round(compact.height * 0.20))"
            in brand_main_qml,
        "the dock launcher must follow the session font and never shrink its "
        "functional caption below 11px")
# plasmashell already enables inherited LayoutMirroring for an RTL session.
# Manually swapping physical left/right anchors inside that tree mirrors twice:
# the navigation rail stayed physically left and the pin affordance stayed right
# in both languages.  Express each edge once in logical LTR source order.
require(re.search(r"anchors\.(?:left|right)\s*:\s*view\.rtl\s*\?",
                  launcher_view_qml) is None
        and "anchors.left: parent.left" in launcher_view_qml
        and "anchors.right: parent.right" in launcher_view_qml,
        "the launcher must use inherited logical anchors once; rtl-conditional "
        "left/right anchors are double-mirrored by plasmashell")

# Favorites are user state.  Defining helper functions is not enough: require a
# second occurrence in the composed UI so pin/unpin/reorder are reachable from
# controls, and require all of them to operate on RootModel.favoritesModel.
for operation, model_call in (
    ("toggleFavorite(", ("addFavorite(", "removeFavorite(")),
    ("moveFavorite(", ("moveRow(",)),
):
    require(brand_qml.count(operation) >= 2 and all(call in brand_main_qml for call in model_call),
            f"launcher favorite operation {operation.rstrip('(')!r} must be reachable in the "
            "UI and persist through Kicker's favorites model")
require("favoritesModel.favorites" not in brand_main_qml
        and "favorites.favorites" not in brand_main_qml,
        "KAStatsFavoritesModel.favorites is a compatibility stub that returns nothing; "
        "enumerating it makes favorite markers/reset silently empty (proven in plasmawindowed)")

# Every Plasmoid.configuration property the QML reads must exist in a schema.
# ConfigPropertyMap lets an absent key look plausible until assignment, when the
# applet warns and forgets the value after restart.
brand_config_path = brand_root / "contents/config/main.xml"
brand_config = brand_config_path.read_text(encoding="utf-8") \
    if brand_config_path.is_file() else ""
require(brand_config_path.is_file(),
        "the launcher uses persistent favorites/page settings but has no contents/config/main.xml")
for config_key in sorted(set(re.findall(r"Plasmoid\.configuration\.([A-Za-z_]\w*)",
                                       brand_qml))):
    require(re.search(rf'<entry\s+name="{re.escape(config_key)}"(?:\s|>)', brand_config) is not None,
            f"launcher config key {config_key!r} is used by QML but absent from main.xml")
shipped_favorites_block = re.search(
    r"readonly property var shippedFavorites:\s*\[(.*?)\]", brand_main_qml, re.DOTALL,
)
favorite_default = re.search(
    r'<entry\s+name="favoriteApps"[^>]*>.*?<default>(.*?)</default>',
    brand_config, re.DOTALL,
)
qml_shipped_favorites = re.findall(r'"([^"]+)"', shipped_favorites_block.group(1)) \
    if shipped_favorites_block else []
schema_shipped_favorites = [item.strip() for item in favorite_default.group(1).split(",")] \
    if favorite_default else []
require(qml_shipped_favorites and qml_shipped_favorites == schema_shipped_favorites,
        "the QML shippedFavorites order and main.xml favoriteApps default must be identical; "
        "fresh profiles and reset-to-default must not seed two different launchers")

# The launcher is a theme surface shared by every UI2 family member.  A literal
# palette here can look right in Graphite and become unreadable in Tidal/Aurora.
require("Kirigami.Theme" in brand_qml,
        "the MoOS launcher must derive its palette from Kirigami.Theme")
require(re.search(r"['\"]#[0-9A-Fa-f]{3,8}['\"]", brand_qml) is None,
        "the MoOS launcher contains a hard-coded hex colour instead of a theme role")

# Milou can only return the whole visible home when Baloo indexes it.  The
# kde-settings profile inherited below /etc/xdg explicitly excludes $HOME, so
# merely enabling Baloo is insufficient: MoOS must both include the root and
# clear that inherited exclusion, while keeping hidden files out of results.
baloo_path = ROOT / "system_files/etc/xdg/baloofilerc"
baloo_config = code(baloo_path.read_text(encoding="utf-8")) if baloo_path.is_file() else ""
include_home = re.search(r"^folders\[\$e\]=(.*)$", baloo_config, re.MULTILINE)
exclude_home = re.search(r"^exclude folders(?:\[\$e\])?=(.*)$", baloo_config, re.MULTILINE)
require("[Basic Settings]" in baloo_config and "Indexing-Enabled=true" in baloo_config,
        "Baloo must be enabled in /etc/xdg/baloofilerc for launcher file search")
require(include_home is not None and "$HOME" in include_home.group(1),
        "Baloo must include visible $HOME, not only the standard media folders")
require(exclude_home is not None and "$HOME" not in exclude_home.group(1),
        "MoOS must clear kde-settings' inherited '$HOME' exclusion or the launcher finds no files")
require("only basic indexing=false" in baloo_config,
        "Baloo content indexing must stay on so launcher search reaches file contents too")
require("index hidden folders=false" in baloo_config,
        "launcher search must cover visible HOME without leaking hidden config/cache files")
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
require("Math.min(root.width" in logout_qml,
        "the logout command sheet must stay responsive — its width bound to the "
        "screen so the vertical action rows never overflow on a narrow display")

# ── Doorway polish regressions (2026-07-21), each gated on the code, not prose ─
# 1) The lock-screen date must not use Qt.formatDate(date, locale, string): the
#    3-arg form silently discards the format string and applies the locale's own
#    LongFormat, so the English date rendered month-first ("July 21" not
#    "21 July"). The fix is Qt.locale(...).toString(date, fmt).
_moosclock = code(read("system_files/usr/share/plasma/shells/org.kde.plasma.desktop/"
                       "contents/lockscreen/MoOSClock.qml"), style="slash")
require("Qt.formatDate" not in _moosclock and ".toString(" in _moosclock,
        "MoOSClock must render its date with Qt.locale(...).toString(date, fmt), "
        "never Qt.formatDate(date, locale, string) — the 3-arg form discards the "
        "format string and the lock date reverts to month-first. (The count was "
        "`>= 2` while the clock printed the date TWICE, hardcoded ar over hardcoded "
        "en, so an English session got an Arabic date it could not read and an "
        "Arabic one got the same day said twice. It prints ONE date in the session "
        "locale now, so there is one call; the ban on the 3-arg form is what this "
        "gate is actually for and it is unchanged.)")
# 2) The logout action button's background turns highlightColor when emphasized
#    or pressed; a highlightColor glyph vanishes into it (the primary Cancel
#    button did exactly this). The non-destructive icon colour must switch to a
#    contrasting role on emphasized/down.
_action_btn = code(read("system_files/usr/share/plasma/look-and-feel/org.moos.ui2/"
                        "contents/logout/MoOSUI2ActionButton.qml"), style="slash")
require("control.emphasized || control.down" in _action_btn
        and "highlightedTextColor" in _action_btn,
        "the logout action icon is not emphasized/down-aware — an accent glyph on "
        "an accent fill makes the Cancel icon invisible")
# Selection foreground is paired only with Selection background.  The old
# accentA→accentB fill put the glyph over a generated hue with no foreground
# contract; destructive actions then reused Selection foreground on the negative
# role.  Keep accentB as rim-only and bind each flat fill to its measured ink.
require(re.search(r"filledInk:\s*control\.destructive\s*"
                  r"\?\s*Kirigami\.Theme\.backgroundColor\s*"
                  r":\s*Kirigami\.Theme\.highlightedTextColor",
                  _action_btn, re.DOTALL) is not None
        and "color: control.filled\n                    ? control.accentA" in _action_btn
        and "border.color: control.filled\n                    ? control.accentB" in _action_btn
        and "? control.filledInk" in _action_btn
        and "filledGrad" not in _action_btn,
        "filled logout orbs must put their glyph on one scheme-paired flat fill: "
        "Selection ink/accent for normal actions, Complementary background/negative "
        "for destructive actions; accentB is decorative rim only")

_lock_main = code(read("system_files/usr/share/plasma/shells/"
                       "org.kde.plasma.desktop/contents/lockscreen/MainBlock.qml"),
                  style="slash")
_unlock_start = _lock_main.find("id: loginButton")
_unlock_end = _lock_main.find("component FailableLabel", _unlock_start)
_unlock = _lock_main[_unlock_start:_unlock_end]
require(_unlock_start >= 0 and _unlock_end > _unlock_start
        and "color: sessionManager.accentA" in _unlock
        and "color: Kirigami.Theme.highlightedTextColor" in _unlock
        and "scale: loginButton.down ? 0.94 : 1.0" in _unlock
        and "gradient: Gradient" not in _unlock
        and re.search(r'color\s*:\s*["\']white["\']|'
                      r'Qt\.rgba\(\s*1\s*,\s*1\s*,\s*1\s*,', _unlock) is None,
        "the lock-screen Unlock glyph must use the scheme's selected ink on flat "
        "accentA; literal white/accentB gradients fall below 3:1 in seven themes")
# 3) Every MoOS doorway uses one Tidal Horizon geometry and the ACTIVE theme.
#    The component is code-native and byte-identical across Splash, Login, Lock
#    and Logout; each host supplies semantic accent/ink/surface roles. Doorway
#    motion is one finite reveal, never an idle animation that burns GPU while
#    the user waits at a security/session surface.
_splash = code(read("system_files/usr/share/plasma/look-and-feel/org.moos.ui2/"
                    "contents/splash/Splash.qml"), style="slash")
_portal = code(read("artwork/tidal-portal/TidalHorizon.qml"), style="slash")
require("Kirigami.Theme.linkColor" in _splash,
        "the splash portal lost the family secondary role — it must use "
        "Kirigami.Theme.linkColor so every family member tracks its own secondary")
_splash_stage = _splash.split("onStageChanged:", 1)[1].split(
    "Rectangle {", 1
)[0] if "onStageChanged:" in _splash else ""
_splash_static = _splash.split("function showStaticFrame()", 1)[1].split(
    "onMotionEnabledChanged:", 1
)[0] if "function showStaticFrame()" in _splash else ""
require(re.search(r"if\s*\(stage\s*===\s*2\)\s*\{.*?"
                  r"if\s*\(root\.motionEnabled\)\s*\{\s*"
                  r"revealAnimation\.restart\(\);\s*\}\s*else\s*\{\s*"
                  r"root\.showStaticFrame\(\);",
                  _splash_stage, re.DOTALL) is not None
        and re.search(r"stage\s*>=\s*5\)\s*\{\s*"
                      r"revealAnimation\.stop\(\);",
                      _splash_stage, re.DOTALL) is not None
        and all(token in _splash_static for token in (
            "revealAnimation.stop()", "content.opacity = 1",
            "contentShift.y = 0", "portal.reveal = 1",
        ))
        and _splash.count("loops: Animation.Infinite") == 0
        and _splash.count("id: revealAnimation") == 1
        and "progressMotion" not in _splash
        and re.search(r"Behavior on width\s*\{\s*NumberAnimation\s*\{\s*"
                      r"duration:\s*root\.motionEnabled\s*\?\s*260\s*:\s*0",
                      _splash) is not None
        and "opacity: root.stage >= 5 ? 0 : 1" in _splash
        and "TidalHorizon {" in _splash
        and "accentA: root.accentA" in _splash
        and "accentB: root.accentB" in _splash
        and all(retired not in _splash for retired in (
            "ringReveal", "shineSweep", "bloomFlash", "particleBurst",
            "typewriterTimer", "logoBreathe", "outroAnimation",
        )),
        "the splash must own exactly one gated finite reveal; "
        "animations-off must land directly on the complete static branded frame")
_logout_code = code(logout_qml, style="slash")
require("TidalHorizon {" in _logout_code
        and "accentA: root.accent" in _logout_code
        and "accentB: root.accentB" in _logout_code
        and "parent.width * 0.96" in _logout_code
        and "parent.height * 1.80" in _logout_code
        and "Kirigami.Units.gridUnit * 50" in _logout_code
        and "Animation.Infinite" not in _logout_code
        and re.search(r"#[0-9A-Fa-f]{3,8}\b", _logout_code) is None,
        "Logout must frame its compact command island with the live-accent Tidal "
        "Horizon, carry no hard-coded palette, and settle after finite entry motion")

# An Animator is a QObject, not an Item, so `target: parent` resolves to NULL.
# Every doorway animator pins a concrete Item and the portal reveal itself is a
# finite NumberAnimation.
require("target: wallpaper" in _logout_code
        and "target: portal" in _logout_code
        and 'property: "reveal"' in _logout_code
        and "target: parent" not in _logout_code,
        "logout entry motion must target concrete ids; target: parent inside an "
        "Animator is null and silently leaves a doorway invisible")
require(all(token in _portal for token in (
            "property color accentA", "property color accentB",
            "property color ink", "property color surface",
            "readonly property real horizonY",
            "readonly property real crestY", "PathCubic", "PathMove",
        ))
        and all(token not in _portal for token in (
            "Timer {", "Animation.Infinite", "MouseArea {", "ShaderEffect",
        )),
        "the canonical Tidal Horizon must stay pure, theme-fed geometry with no "
        "input, shader, timer or self-running animation")

# Dismissing the power screen must stay deliberate. The scene-wide MouseArea
# used to call cancelRequested(), and the sheet's "blocker" was declared
# acceptedButtons: Qt.NoButton — which makes a MouseArea decline every button
# and let the press fall straight through, so a click on the clock, the heading
# or the gaps between the orbs cancelled a pending shutdown. Exactly two paths
# may emit it: the Escape Action and the Cancel orb (plus the declaration).
require(_logout_code.count("cancelRequested()") == 3
        and "acceptedButtons: Qt.NoButton" not in _logout_code,
        "the logout screen must dismiss only on the Cancel orb and Escape — a "
        "third cancelRequested() call site, or a Qt.NoButton 'blocker', means a "
        "stray click on the sheet can cancel a shutdown again")
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
# code() is not optional here: the file's own comments explain this bug and therefore
# contain the very wallpaper name being asserted. Gate the config, not the prose.
#
# /usr/lib/plasmalogin/defaults.conf, NOT the vendor drop-in directory. Disassembled from
# /usr/libexec/plasma-login-greeter 2026-07-27: the four sources are merged as
#   KSharedConfig::openConfig("/etc/plasmalogin.conf")
#   addConfigSources(*.conf in /etc/plasmalogin.conf.d)
#   addConfigSources("/usr/lib/plasmalogin/defaults.conf")
#   addConfigSources(*.conf in /usr/lib/plasmalogin/plasmalogin.conf.d)
# and KConfig gives an EARLIER addConfigSources call priority over a later one (kconfig.h:
# "The settings in sources will also be overridden by the sources provided by any previous
# calls to addConfigSources()"), with the constructor file overriding all of them. So the
# vendor drop-in directory MoOS used to ship in is the WEAKEST of the four layers — below
# even stock Fedora's defaults.conf. defaults.conf is the slot upstream's own README (line
# 58) names for distro defaults and the strongest layer the image may own; /etc is the
# administrator's.
login_defaults = ROOT / "system_files/usr/lib/plasmalogin/defaults.conf"
require(login_defaults.is_file(),
        "the image does not own /usr/lib/plasmalogin/defaults.conf — the login screen would "
        "fall back to Fedora's, whose Image=file:///usr/share/wallpapers/Fedora/ points at a "
        "directory this build deletes")
login_config = code(login_defaults.read_text(encoding="utf-8"))
# One value, one file. Repeating a greeter key in the weaker vendor drop-in directory is how
# the login wallpaper drifted a whole release behind the lock screen's.
_weak_login_dir = ROOT / "system_files/usr/lib/plasmalogin/plasmalogin.conf.d"
_weak_login = code("\n".join(
    p.read_text(encoding="utf-8") for p in sorted(_weak_login_dir.glob("*.conf"))
)) if _weak_login_dir.is_dir() else ""
require("WallpaperPluginId" not in _weak_login and "ShowClock" not in _weak_login,
        "a greeter key is duplicated into /usr/lib/plasmalogin/plasmalogin.conf.d, the "
        "lowest of the four config layers — two files carrying one value is exactly how the "
        "login screen and the lock screen drifted apart before")
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
# ...and every OTHER variant must follow the same halves. The loop above reads
# exactly two look-and-feels; MoOS ships sixteen. A new palette added with the
# pointers the wrong way round — or with a cursor theme nobody builds — would
# have sailed through, because no gate ever looked at it. The canvas a variant
# paints is decided by its `.light` suffix, so the cursor it may name is decided
# too: there are only two legal answers and this says which is which.
#
# This is the name-level half of the check, and it is deliberately not the whole
# one. It can only prove a variant agrees with `org.moos.ui2`; it cannot prove
# `org.moos.ui2` itself is right, because the cursor themes do not exist in the
# repo — build.sh copies them from Bibata. The pixels are measured in
# `build_files/verify_image_experience.py`, which runs inside the image where
# they do exist. Together: this one catches a mis-paired variant in seconds on
# every push, that one catches an inverted pair on arithmetic.
lnf_dir = ROOT / "system_files/usr/share/plasma/look-and-feel"
checked_variants = 0
for variant_defaults in sorted(lnf_dir.glob("org.moos.ui2*/contents/defaults")):
    variant_name = variant_defaults.parent.parent.name
    variant_match = re.search(r"^cursorTheme=(\S+)$",
                              read(str(variant_defaults.relative_to(ROOT))), re.MULTILINE)
    require(variant_match is not None,
            f"{variant_name} names no cursor theme — Plasma would substitute its own pointer")
    if variant_match is None:
        continue
    expected_half = "org.moos.ui2.light" if variant_name.endswith(".light") else "org.moos.ui2"
    require(variant_match.group(1) == ui2_cursors[expected_half],
            f"{variant_name} names cursor {variant_match.group(1)}, but every "
            f"{'light' if variant_name.endswith('.light') else 'dark'} canvas must use "
            f"{ui2_cursors[expected_half]} — this one gets a low-contrast pointer")
    checked_variants += 1
require(checked_variants >= 8,
        f"only {checked_variants} look-and-feel variants were cursor-checked — the palette "
        "variants are unguarded")

cursor_switcher = code(read("system_files/usr/bin/moos-theme"))
cursor_build = code(read("build_files/build.sh"))
for cursor_name in ui2_cursors.values():
    require(f"cursor={cursor_name}" in cursor_switcher,
            f"moos-theme never selects {cursor_name} — the LNF defaults and the "
            "switcher would fight over the pointer")
    require(f"/usr/share/icons/{cursor_name}" in cursor_build,
            f"build.sh never creates {cursor_name} — the defaults would name a "
            "cursor that does not exist and Plasma would fall back")

# A control the keyboard can reach must also have a NAME a screen reader can say.
#
# Adding activeFocusOnTab and an Accessible.Button role made the wizards completable, but a role
# without a name announces "button" — twelve times in a row on Welcome, with nothing to tell them
# apart. orca and at-spi2-core are both installed on MoOS, so that gap is reachable, not theoretical.
#
# The names are not invented: each one binds to the SAME expression as the control's own visible
# label, which is what WCAG's "label in name" asks for. Three had to be written by hand because
# they could not be derived safely — a theme card that shows a colour swatch and no word (named
# from the model's en/ar fields), and two labels split across lines by a ternary. A wrong name is
# worse than none, so nothing here is a guess.
for qml_app in sorted((ROOT / "system_files/usr/share/moos").glob("**/main.qml")):
    qml_src = code(read(str(qml_app.relative_to(ROOT))), style="slash")
    app_label = qml_app.parent.name
    tab_stops = len(re.findall(r"activeFocusOnTab\s*:\s*true", qml_src))
    if not tab_stops:
        continue
    names = len(re.findall(r"Accessible\.name\s*:", qml_src))
    require(names >= tab_stops,
            f"{app_label} has {tab_stops} tab stop(s) but only {names} Accessible.name — a "
            f"screen reader would announce an anonymous \"button\". Bind the name to the same "
            f"expression as the control's visible label")

# Containers scale with the type they hold, or the type outgrows them.
#
# Making font.pixelSize responsive was only half the job. At 2.2x the shipped font, Welcome's
# primary button stayed exactly 116px tall while its label grew — and the crop showed the Arabic
# hamza on "لنبدأ" clipped off by the button's top edge. A control whose text scales and whose box
# does not is a control that eventually cuts its own label in half.
#
# Every Layout.preferredHeight / implicitHeight / preferredWidth / implicitWidth literal now goes
# through the same fs() helper as the type, so the box and the text move together. Spacers scale
# too, deliberately: vertical rhythm belongs to the type scale, not to a fixed pixel grid.
#
# Neutral at the shipped 10pt (Welcome: 0 differing pixels across button, pills, headline and
# progress dots) and at 22pt the same button measures 197px instead of 116px with the label
# comfortably inside.
for qml_app in sorted((ROOT / "system_files/usr/share/moos").glob("**/main.qml")):
    qml_src = code(read(str(qml_app.relative_to(ROOT))), style="slash")
    app_label = qml_app.parent.name
    raw_boxes = re.findall(
        r"\b(?:Layout\.preferredHeight|Layout\.preferredWidth|implicitHeight|implicitWidth)\s*:\s*(\d+)\b",
        qml_src)
    require(not raw_boxes,
            f"{app_label} sets a container size to a literal ({', '.join(sorted(set(raw_boxes))[:6])}"
            f"{'...' if len(set(raw_boxes)) > 6 else ''}) — the text inside it scales with the "
            f"user's font and the box does not, so the label eventually clips. Wrap it in fs()")

# Anything reachable by Tab must SHOW that it has focus. WCAG 2.4.7.
#
# Mo Store was the only MoOS app supporting Tab at all — five component types declared
# activeFocusOnTab — and exactly ONE of them drew anything when focused (the search field, whose
# border thickens). The other four moved an invisible cursor: a keyboard user could tab through
# the entire storefront with no idea where they were.
#
# The fix is a shared `FocusRing` inline component, not a QtQuick.Controls style. There is no
# MoOS style module to put one in (these apps run QT_QUICK_CONTROLS_STYLE=Basic), and a Controls
# style could not reach them anyway: every focusable here is a bare Rectangle with hand-rolled
# TapHandler and Keys handlers, which no Controls style ever touches.
#
# This gate counts rather than inspects structure, because QML nesting is not reliably parseable
# with a regex: if a file declares N tab stops it must contain at least N focus indicators, where
# an indicator is either a FocusRing instance or a visual property bound to activeFocus.
for qml_app in sorted((ROOT / "system_files/usr/share/moos").glob("**/main.qml")):
    qml_src = code(read(str(qml_app.relative_to(ROOT))), style="slash")
    app_label = qml_app.parent.name
    tab_stops = len(re.findall(r"activeFocusOnTab\s*:\s*true", qml_src))
    if not tab_stops:
        continue
    rings = len(re.findall(r"^\s*FocusRing\s*\{", qml_src, re.M))
    # Count RINGS ONLY, one per declared tab stop.
    #
    # The first version of this also credited any visual bound to activeFocus, and that made it
    # useless: the search field binds TWO properties (border.width and border.color) to its own
    # focus, so deleting a whole FocusRing still left the arithmetic satisfied and the gate green
    # with a control that showed nothing. Two bindings on ONE control are not two indicators.
    #
    # Requiring the shared component instead of "some binding somewhere" is also the better rule
    # on its own terms: one focus treatment across the app rather than five hand-rolled ones.
    require(rings >= tab_stops,
            f"{app_label} declares {tab_stops} tab stop(s) but instantiates only {rings} "
            f"FocusRing. A control the keyboard can reach and cannot show is a WCAG 2.4.7 "
            f"failure — add `FocusRing {{ }}` inside it")

# ...and they must not override the user's font SIZE either.
#
# 294 text items carried a hardcoded `font.pixelSize`, so the size control in System Settings >
# Fonts moved every application on the machine except this operating system's own. That is the
# first control someone with low vision reaches for, and MoOS was the one thing ignoring it.
#
# Every size now goes through the root's fs() helper, which multiplies by
# Qt.application.font.pointSize / 10. The reference is POINT size because MoOS ships
# `IBM Plex Sans,10` in /etc/xdg/kdeglobals and points do not move with DPI — measured on this
# 4K display, Qt reports pointSize 10 / pixelSize 13, so the ratio is exactly 1.0 at the default
# on any screen and changes only when the USER changes the setting.
#
# Proven in both directions rather than assumed. At the shipped 10pt, Welcome renders with 0
# differing pixels across headline, subtitle, language pills, primary button, skip link and
# progress dots. Under an isolated XDG_CONFIG_HOME at 15pt and again at 22pt (2.2x), the type
# scales, the subtitle reflows, and nothing clips or overlaps.
for qml_app in sorted((ROOT / "system_files/usr/share/moos").glob("**/main.qml")):
    qml_src = code(read(str(qml_app.relative_to(ROOT))), style="slash")
    app_label = qml_app.parent.name
    raw_sizes = re.findall(r"font\.pixelSize\s*:\s*(\d+)\b", qml_src)
    require(not raw_sizes,
            f"{app_label} sets font.pixelSize to a literal ({', '.join(sorted(set(raw_sizes))[:6])}"
            f"{'...' if len(set(raw_sizes)) > 6 else ''}) — that ignores the font size the user chose. "
            f"Wrap it in the root's fs() helper so the whole UI scales with System Settings > Fonts")

# MoOS's own apps must not override the user's font.
#
# `font.family: "IBM Plex Sans"` was written out at 194 text items across Welcome, Mo Store and
# the Installer, and Mo AI centralised the same literal in one property. Measured, that string is
# ALREADY the system font — kdeglobals General font is `IBM Plex Sans,10,...`, Qt hands apps
# "IBM Plex Sans" at 13px, and 61-moos-brand.conf maps sans-serif to it as well. So the literal
# changed nothing about how MoOS looks and did exactly one thing: it overrode the font the user
# chose, in the four applications this operating system ships and nowhere else. Someone who picks
# a larger or more legible face in System Settings watched every app obey except MoOS's own.
#
# The tree already contained the proof it was unnecessary: the theme picker sets no font.family
# at all and renders in the brand face regardless, because the brand face IS the system face.
#
# Removing it was verified to be visually neutral, not assumed: Welcome rendered before and after
# and diffed per region — headline, subtitle, language pills, primary button, skip link and
# progress dots all 0 differing pixels. (The hero halo differs because it is an animation caught
# at a different frame.)
#
# A monospace literal is a different case and is allowed: code and logs want a fixed face, and
# JetBrains Mono is the system `fixed` font by the same argument.
for qml_app in sorted((ROOT / "system_files/usr/share/moos").glob("**/main.qml")):
    # style="slash": QML comments are //, and the default here strips # instead. Without
    # this the comment ABOVE explaining the literal satisfies the search for the literal,
    # and the gate fails on files that are correct.
    qml_src = code(read(str(qml_app.relative_to(ROOT))), style="slash")
    app_label = qml_app.parent.name
    for bad_family in re.findall(r'font\.family:\s*"([^"]+)"', qml_src):
        require("mono" in bad_family.lower(),
                f"{app_label} hardcodes font.family \"{bad_family}\" — that overrides the font the "
                f"user chose in System Settings. Bind to the root's `uiFont` property, which is "
                f"Qt.application.font.family, so MoOS follows the system face like every other app")

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

containerfile = read("Containerfile")
require(
    build.count("curl -Lf --retry 5 --retry-all-errors") >= 4
    and "curl -Lf --retry 3" not in build,
    "build-time asset downloads must retry connection resets, not only HTTP "
    "errors — a transient GitHub reset otherwise aborts an entire image build",
)
require(
    "curl -fL --retry 5 --retry-all-errors" in containerfile,
    "the Flutter SDK download must retry all transient curl failures",
)
require(
    'io.artifacthub.package.readme-url="https://raw.githubusercontent.com/'
    'moalfarras-sys/moos-image/main/README.md"' in containerfile,
    "the published image must override the base image's Artifact Hub README "
    "with MoOS-owned metadata",
)
require(
    'io.artifacthub.package.logo-url="https://raw.githubusercontent.com/'
    'moalfarras-sys/moos-image/main/system_files/usr/share/pixmaps/moos-logo.png"'
    in containerfile,
    "the published image must override the base image's Artifact Hub logo "
    "with the MoOS mark",
)
require("grep -qx 'Theme=moos' /etc/plymouth/plymouthd.conf" in build,
        "image build must fail if the active Plymouth selector is not MoOS")

# ── the boot must not go black between the splash and the desktop ────────────
# Repo-side twin of the image gate in verify_image_experience.py. Measured on the owner's
# machine 2026-07-27: `plymouth quit` at 16:52:24.269, KWin's DRM backend at 16:52:28.728.
# The drop-in is the whole fix; there is nothing else in the tree that keeps the splash up.
_retain = ROOT / "system_files/usr/lib/systemd/system/plymouth-quit.service.d/10-moos-retain-splash.conf"
require(_retain.is_file(),
        "system_files must ship the plymouth-quit retain-splash drop-in — without it the boot "
        "shows 4.5s of black between the MoOS splash and the first desktop frame")
if _retain.is_file():
    _retain_src = code(_retain.read_text(encoding="utf-8"))
    require("quit --retain-splash" in _retain_src,
            "the plymouth-quit drop-in must run `plymouth quit --retain-splash`")
    require(any(line.strip() == "ExecStart=" for line in _retain_src.splitlines()),
            "the plymouth-quit drop-in must reset ExecStart= before adding its own — ExecStart "
            "is a list, and the stock quit would otherwise run first and blank the screen")

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
# not from a .plymouth key. It must be the UI2 canvas #14191C — the colour the desktop
# opens on — and FLAT: a gradient cannot line up with a wallpaper it knows nothing about,
# and the seam is exactly the hue break this gate exists to stop. The previous version of
# this gate pinned Nova's navy #070B16/#04060A, which is what kept the splash out of the
# UI2 rollout: measured 2026-07-27, the splash painted navy, the desktop graphite and the
# Arena splash #0B0714, so every boot broke hue at the handoff. Derive the floats from the
# canvas token instead of retyping them, exactly as the comment above this block asks.
moos_script_src = read("system_files/usr/share/plymouth/themes/moos/moos.script")
_canvas = "14191C"
_ground = ", ".join(f"{int(_canvas[i:i + 2], 16) / 255:.3f}" for i in (0, 2, 4))
require(f"Window.SetBackgroundTopColor({_ground})" in moos_script_src,
        f"the boot splash's top background is not the UI2 canvas #{_canvas} "
        f"(expected Window.SetBackgroundTopColor({_ground}))")
require(f"Window.SetBackgroundBottomColor({_ground})" in moos_script_src,
        f"the boot splash's bottom background is not the UI2 canvas #{_canvas} — the ground "
        f"must be FLAT, or the splash-to-desktop seam shows")

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
for lock_file in ("LockScreenUi.qml", "MoOSClock.qml", "TidalHorizon.qml"):
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
require("TidalHorizon {" in lock_ui
        and "accentA: lockScreenUi.accentA" in lock_ui
        and "accentB: lockScreenUi.accentB" in lock_ui
        and "Animation.Infinite" not in lock_ui,
        "the lock screen must share the finite, live-theme Tidal Horizon and must "
        "not run decorative loops while the machine is locked")
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
require(re.search(r"MoOSClock\s*\{(?:[^{}]|\{[^{}]*\})*anchors\.(?:left|right):\s*parent\.(?:left|right)",
                  lock_ui, re.DOTALL) is not None
        or ("anchors.left: lockScreenUi.rtl ? undefined : parent.left" in lock_ui
            and "anchors.right: lockScreenUi.rtl ? parent.right : undefined" in lock_ui),
        "the lock clock must anchor to a top CORNER (a hero, off the centred brand) "
        "so it never draws through the MoOS emblem and wordmark on a tall panel")
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
require("Layout.preferredWidth: loginButton.Layout.preferredHeight * 1.28" in mainblock
        and "radius: height * 0.30" in mainblock
        and "width: parent.width * 0.30" in mainblock
        and "width: parent.width * 0.42" in mainblock,
        "the lock-screen Unlock action must be the compact Tidal Portal key; a "
        "square circular button breaks the session control family")
# ── Any pre-baked brand sprite still named by QML must travel with that QML.
#    Doorway identity is now code-native and static; this remains a guard for
#    components outside the doorway that intentionally retain a shipped sprite.
#    A QML that references images/glow-cyan.png
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
        "the logout screen must isolate the active-language phrase; without "
        "Unicode bidi isolation RTL moves punctuation and counts")
_logout_formatter = _logout_code.split(
    "function bilingual(arabic, english)", 1
)[1].split("function shortLabel", 1)[0]
require(' + "  ·  " + ' not in _logout_formatter
        and re.search(r"\bar\s*\+.*\ben\b|\ben\s*\+.*\bar\b",
                      _logout_formatter, re.DOTALL) is None,
        "Logout must draw only the session language; concatenating Arabic and "
        "English on every heading, warning and description creates visual noise")
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
login_wallpaper = code(read(
    "system_files/usr/share/plasma/wallpapers/org.moos.ui2.greeter/contents/ui/main.qml"
), style="slash")
login_action = read(
    "system_files/usr/lib64/qt6/qml/org/kde/breeze/components/ActionButton.qml"
)
login_clock = read(
    "system_files/usr/lib64/qt6/qml/org/kde/breeze/components/Clock.qml"
)
require("TidalHorizon {" in login_wallpaper
        and "Animation.Infinite" not in login_wallpaper
        and "Timer {" not in login_wallpaper
        and "ShaderEffect" not in login_wallpaper,
        "the plasma-login wallpaper must identify MoOS with a static Tidal Horizon "
        "without layering a second animated UI over the compiled greeter")
require("The Tidal Portal key" in login_action
        and "radius: height * 0.30" in login_action
        and "IBM Plex Sans Arabic" in login_action,
        "the compiled plasma-login controls must use the shared MoOS portal-key "
        "geometry and typography instead of generic circular Breeze actions")
require("trackSeconds: false" in login_clock
        and "Animation.Infinite" not in login_clock
        and 'text: ":"' in login_clock
        and "Locale.LongFormat" in login_clock
        and "sessionLocale.dateFormat(Locale.LongFormat)" in login_clock
        and "LayoutMirroring.enabled: false" in login_clock
        and "layoutDirection: Qt.LeftToRight" in login_clock,
        "the login clock must be one static MoOS editorial face: active-locale "
        "date, accent colon, minute precision, semantic LTR time and no idle animation")

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
    "contents/splash/TidalHorizon.qml",
    "contents/logout/Logout.qml",
    "contents/logout/MoOSUI2ActionButton.qml",
    "contents/logout/TidalHorizon.qml",
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
normalized_build_script = " ".join(build_script_code.replace("\\", " ").split())

# The launcher uses APIs that only exist in a Plasma applet host.  It must be
# instantiated as the installed PACKAGE, under a session bus; qmlformat/qmllint
# cannot catch a wrong Kicker property or a missing LauncherView component.
require("dbus-run-session -- /usr/bin/plasmawindowed org.moos.brand "
        "moos-ci-full-representation" in normalized_build_script,
        "the image build must force org.moos.brand's full LauncherView through plasmawindowed "
        "under an isolated session bus, not load only its compact panel button")
require('_launcher_smoke_rc" -ne 124' in build_script_code,
        "the launcher smoke must accept only a process that stayed alive to the timeout; "
        "an early clean exit is still a dead applet")
require("MOOS_LAUNCHER_FULL_READY size=792x576" in build_script_code
        and re.search(r"geometry=.*792,576", build_script_code) is not None,
        "the launcher smoke must prove both LauncherView construction and plasmawindowed's "
        "real 792x576 full-representation geometry")
for launcher_runtime_failure in (
    "component is not ready", "error loading qml file", "invalid empty url",
    "compactrepresentationexpander .* is not an item", "type .* unavailable",
    "module .* is not installed", "referenceerror", "typeerror",
    "unable to assign", "binding loop", "is not a type",
    "qml (image|pixmap): cannot open",
    "kastatsfavoritesmodel::favorites returns nothing",
):
    require(launcher_runtime_failure.lower() in build_script_code.lower(),
            "the launcher smoke must reject live QML diagnostic %r; a Plasma host can "
            "stay alive while the search or one page is broken" % launcher_runtime_failure)

# The bento is deliberately plain QtQuick/Kirigami so the build can genuinely
# LOAD it (a WallpaperItem root only exists inside plasmashell). The smoke hosts
# DashboardBento in a window via moos-qml-shell under a real session bus and
# rejects the live QML diagnostics; the wallpaper wrapper is checked structurally.
require("moos-scene-smoke.qml" in build_script_code
        and "DashboardBento.qml" in build_script_code,
        "the image build must load the scene bento through a real QML host; "
        "a package that only exists on disk is not a package that loads")
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
# THE CONTRACT FLIPPED HERE, DELIBERATELY (THEME_REV 24). This gate used to require
# the portal's Id IN the hide list. The hide was built on the theory that hidden items
# surface when they turn Active — measured false on Plasma 6: a live remote-control
# session showed no indicator anywhere on screen while its SNI sat Active behind the
# collapse arrow. On an OS that ships Mo PC Remote, the portal item is the one
# at-a-glance "your screen is being watched" signal. Unlisted, Plasma shows it by
# Status: invisible while Passive, in the tray while a session is Active.
require("xdg-desktop-portal-kde" not in apply_theme_code,
        "the portal's remote-control indicator must NOT be hidden — hidden SNIs do not "
        "surface when they turn Active (measured on Plasma 6), so hiding it blinds the "
        "user to an active remote-control session")
# The bridge, by contrast, stays hidden — and SNIs match on their OWN Id, which is the
# app's TRANSLATED name on some builds. Every measured variant must be listed, and the
# OS's own first-class locale was the one missing.
for bridge_id in ("xwaylandvideobridge", "Xwayland Video Bridge",
                  "Xwayland-Video-Bruecke", "جسر فيديو ويلاند_اكس"):
    require(bridge_id in apply_theme_code,
            f"the Xwayland bridge hide-list is missing the Id variant {bridge_id!r} — "
            f"SNIs match on their translated Id, so a missing locale variant pops the "
            f"icon into the curated tray for exactly that locale's users")

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
require(re.search(r"layoutDirection\s*:\s*root\.rtl\s*\?", panel_clock) is None,
        "the panel clock must inherit plasmashell RTL exactly once; forcing RTL on "
        "its RowLayouts reverses the already-mirrored order a second time")

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
#
# `bootc install` is gated the same way and for the same reason. The cloud converter
# installs MoOS over a running Debian with `bootc install to-existing-root`, and that
# call lands an origin exactly as permanently as a switch does.
#
# libexec is scanned as well as bin. The first version of this gate read only
# system_files/usr/bin, so a `bootc switch` anywhere else was unguarded — which is
# where the self-healing rebind below actually lives.
# What is actually required is the OUTCOME — the install ends up on a signed origin —
# and there are two legitimate ways to reach it. `moos-install-to-disk` uses the second
# one: it runs `bootc install to-disk` plainly and then rewrites the deployment origin
# to `ostree-image-signed:docker://…`, matching what the Anaconda %post does. Gating on
# the flag alone called that file broken when it is correct. Assert the outcome, and
# accept either proof.
_SWITCH = re.compile(r"bootc\s+(?:switch|install)\b([^\n;|&]*)")
_sigpolicy_dirs = ["system_files/usr/bin", "system_files/usr/libexec"]
for _dirname in _sigpolicy_dirs:
    _dir = ROOT / _dirname
    if not _dir.is_dir():
        continue
    for _tool in sorted(_dir.iterdir()):
        if not _tool.is_file():
            continue
        try:
            _text = _tool.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # Join shell line-continuations first: the converter spreads its flags over
        # five lines, and a regex that stops at the newline would read the argument
        # list as `to-existing-root` alone and pass a call that enforces nothing.
        _stripped = code(_text)
        _joined = re.sub(r"\\\n\s*", " ", _stripped)
        # The rewrite has to name the signed transport in real code, not in a comment,
        # for it to count as the second proof.
        _rearms_origin = "ostree-image-signed:" in _stripped
        for _args in _SWITCH.findall(_joined):
            require("--enforce-container-sigpolicy" in _args or _rearms_origin,
                    f"{_dirname}/{_tool.name} runs `bootc switch`/`bootc install` without "
                    "--enforce-container-sigpolicy, and never rewrites the origin to "
                    "ostree-image-signed:. Both commands REPLACE the origin, so this leaves "
                    "ostree-unverified-registry: and the machine — and every later upgrade — "
                    "stops verifying signatures for the life of the install. "
                    f"Offending arguments: `bootc …{_args.rstrip()}`")


# ── An install that ALREADY lost its signature must repair itself ─────────────
#
# The gate above can only protect installs that have not happened yet, and the cloud
# conversion path defeats it outright: MOOS_CLOUD_PLAN §2(أ) recommends
# `system-reinstall-bootc`, which builds its own `bootc install to-existing-root`
# command line and — as of 1.16.4 — has no --enforce-container-sigpolicy and no
# passthrough for one. Every server converted that way, including the maintainer's,
# boots MoOS and verifies nothing, for the life of the install, because the origin
# persists.
#
# `bootc status` cannot be used to notice this: on an unverified install it prints
# transport "registry" and a correct-looking image ref, byte-identical to a verified
# one. The origin file is the only place the truth is recorded.
#
# So the image repairs itself at boot, and these three pieces have to stay wired
# together — the script, the unit that runs it, and the enforcing switch inside it.
_origin_fix = read("system_files/usr/libexec/moos-verify-origin")
require("--enforce-container-sigpolicy" in code(_origin_fix),
        "moos-verify-origin no longer passes --enforce-container-sigpolicy — it is the "
        "only thing that puts a converted server back on the signed update train.")
require("ostree-unverified-registry:" in _origin_fix,
        "moos-verify-origin no longer looks for the `ostree-unverified-registry:` prefix, "
        "which is the only on-disk evidence that an install stopped verifying signatures.")

_origin_unit = read("system_files/usr/lib/systemd/system/moos-verify-origin.service")
require("ExecStart=/usr/libexec/moos-verify-origin" in _origin_unit,
        "moos-verify-origin.service does not run /usr/libexec/moos-verify-origin.")
require("WantedBy=multi-user.target" in _origin_unit,
        "moos-verify-origin.service is not wanted by any target, so it never runs and a "
        "converted server keeps taking unverified updates.")


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

# KWin owns Num Lock on Wayland. Its kcminputrc enum is 0=on, 1=off,
# 2=unchanged, and it evaluates the preference only when that KWin process
# starts. This one system default therefore covers Plasma Login Manager's KWin
# and the user's session while leaving the physical Num Lock key free after
# startup. A repeating service or a synthetic key press would break that
# contract; pin the native preference instead.
input_defaults = code(read("system_files/etc/xdg/kcminputrc"), "hash")
keyboard_defaults = re.search(
    r"(?ms)^\[Keyboard\]\s*$.*?(?=^\[|\Z)", input_defaults
)
require(keyboard_defaults is not None
        and re.search(r"(?m)^NumLock\s*=\s*0\s*$",
                      keyboard_defaults.group(0)) is not None,
        "kcminputrc must set [Keyboard] NumLock=0: KWin's native startup-on "
        "preference for both the login greeter and user session")

# The default above loses to a stale per-user file. Run a scoped, marker-backed
# repair before both KWin processes, then get out of the way: later preference
# changes and every physical Num Lock key press remain the user's.
numlock_migrate = code(read("system_files/usr/bin/moos-ui-migrate"))
numlock_unit = code(read(
    "system_files/usr/lib/systemd/user/moos-input-migrate.service"
))
require("migrate_startup_numlock()" in numlock_migrate
        and "numlock-startup-v1.done" in numlock_migrate
        and re.search(
            r"(?ms)case\s+\"\$old_value\"\s+in.*?1\|2\).*?"
            r"kwriteconfig6\s+--file\s+\"\$tmp\"\s+--group\s+Keyboard"
            r"\s+--key\s+NumLock\s+0",
            numlock_migrate,
        ) is not None,
        "existing users need a one-time, narrowly scoped NumLock 1|2 -> 0 "
        "migration; /etc/xdg alone loses to ~/.config/kcminputrc")
require("numlock-startup-v1.done" in numlock_migrate
        and '[ -e "$input_marker" ] && return 0' in numlock_migrate,
        "the NumLock repair has no apply-once marker, so it could overwrite a "
        "preference the user chooses later")
require("ExecStart=/usr/bin/moos-ui-migrate --input-only" in numlock_unit,
        "the pre-KWin input service must use the bounded input-only migration path")
for kwin_surface, dropin_rel in (
    (
        "user Wayland session",
        "system_files/usr/lib/systemd/user/plasma-kwin_wayland.service.d/"
        "10-moos-input-migrate.conf",
    ),
    (
        "Plasma Login Manager greeter",
        "system_files/usr/lib/systemd/user/"
        "plasma-login-kwin_wayland.service.d/10-moos-input-migrate.conf",
    ),
):
    numlock_dropin = code(read(dropin_rel))
    require("Wants=moos-input-migrate.service" in numlock_dropin
            and "After=moos-input-migrate.service" in numlock_dropin,
            f"the NumLock migration must finish before KWin starts in the "
            f"{kwin_surface}")
for forbidden_numlock_force in (
    "KWIN_FORCE_NUM_LOCK_EVALUATION",
    "ydotool",
    "numlockx",
    "xset",
):
    require(forbidden_numlock_force not in numlock_migrate
            and forbidden_numlock_force not in numlock_unit,
            "NumLock must remain manually toggleable; persistent forcing is "
            f"forbidden ({forbidden_numlock_force})")

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
store_browse = code(read("system_files/usr/bin/moos-store-browse"), "hash")
store_backend = code(read("system_files/usr/bin/moos-storectl"), "hash")
store_setup = code(read("system_files/usr/bin/moos-setup"), "hash")
require("moos-storectl open-engine bazaar" in store_browse,
        "the Bazaar compatibility launcher must delegate to the trusted backend")
require("BAZAAR_ID" in store_backend
        and "self.adapter.install_many" in store_backend
        and "ONE_STORE" in store_backend,
        "the trusted backend must install Bazaar through verified libflatpak and "
        "hide its launcher before opening it")
require("moos-one-store" in store_setup,
        "system setup can install Bazaar, so it must keep its launcher hidden")
bazaar_migration = read(
    "system_files/usr/lib/tmpfiles.d/moos-bazaar-overrides.conf"
)
require(
    "r /var/lib/flatpak/overrides/io.github.kolunmi.Bazaar"
    in bazaar_migration
    and "filesystems=host-etc" not in bazaar_migration,
    "upgrades must remove Bazaar's obsolete persistent host-/etc permission",
)

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
_fr_on = _fr.split("fast_on() {", 1)[1].split("\n}", 1)[0]
_fr_off = _fr.split("fast_off() {", 1)[1].split("\n}", 1)[0]
require('[ -f "$STATE" ]' in _fr_on
        and _fr_on.index('[ -f "$STATE" ]') < _fr_on.index("set_effect Plugins"),
        "Fast Remote ON must be idempotent before it overwrites the saved brain/layout")
require('[ ! -f "$STATE" ]' in _fr_off
        and _fr_off.index('[ ! -f "$STATE" ]') < _fr_off.index("set_effect Plugins"),
        "Fast Remote OFF must be a no-op when no ON snapshot exists")

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
    for p in sorted((ROOT / "system_files/usr/lib/plasmalogin").rglob("*.conf"))
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
        and "MoosStore.installApps(ids)" in _welcome
        and 'doc.state === "success"' in _welcome
        and 'doc.state === "failed"' in _welcome
        and "installHadFailures" in _welcome,
        "Welcome selections must use the private Mo Store transaction and "
        "surface both success and failure from job.json")
require("moos://store/install/" not in _welcome,
        "Welcome must never authorize software changes through the public URL scheme")
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
require("MOOS_PLASMALOGIN_CONF" in _drm_wait
        and "WallpaperPluginId=org.kde.hunyango" in _drm_wait
        and ".moos-legacy-hunyango" in _drm_wait
        and ".moos-keep" in _drm_wait,
        "the login preflight must neutralise the exact stock Hunyango key, keep a backup, "
        "and honour an administrator opt-out; /etc/plasmalogin.conf is the KConfig main "
        "file and outranks every layer the image ships, defaults.conf included")
# The repair is COSMETIC and runs from ExecStartPre of a unit with Restart=always and
# StartLimitBurst=2. A non-zero exit there does not report a problem — it burns the restart
# budget twice and leaves the machine with no login screen at all. The only exit 1 in this
# script may be the DRM timeout.
require(_drm_wait.count("exit 1") == 1 and "no DRM card appeared" in _drm_wait,
        "moos-wait-drm has an exit 1 outside the DRM timeout — a failed cosmetic login "
        "wallpaper repair would permanently kill the display manager")
require("ExecStartPre=/usr/libexec/moos-wait-drm" in _login_drm_dropin,
        "plasmalogin.service must run the DRM preflight before starting KWin")
require("chmod 0755 /usr/libexec/moos-wait-drm" in _build,
        "build.sh must make the login DRM preflight executable")

require("/usr/lib/plasmalogin/defaults.conf" in _build
        and "GATE FAIL: /usr/lib/plasmalogin/defaults.conf is not MoOS's" in _build,
        "build.sh must re-assert after its package transactions that MoOS still owns the "
        "login distro-defaults slot; system_files is copied BEFORE build.sh runs, so a dnf5 "
        "transaction pulling kde-settings-plasmalogin would restore Fedora's file")

# Run build.sh's login-defaults gate HERE, against the file that is about to ship,
# instead of discovering it 18 minutes into an image build. The first CI run after
# that gate landed failed on a CORRECT file: the gate grepped the raw bytes for
# "wallpapers/Fedora", and MoOS's own defaults.conf DOCUMENTS the dangling Fedora
# path it replaced — so the paragraph explaining the fix tripped the gate that
# enforces it. Both halves are simulated the way build.sh now does it: comments
# stripped first, exactly like the config()/code() helpers this file already has.
_login_defaults = ROOT / "system_files/usr/lib/plasmalogin/defaults.conf"
require(_login_defaults.is_file(),
        "MoOS must own /usr/lib/plasmalogin/defaults.conf — upstream documents it as THE "
        "distro-defaults slot, and it outranks the plasmalogin.conf.d drop-in MoOS used to "
        "ship in (measured from the greeter binary: an earlier addConfigSources call wins)")
if _login_defaults.is_file():
    _login_defaults_cfg = code(_login_defaults.read_text(encoding="utf-8"))
    require(any(line.startswith("WallpaperPluginId=org.moos.")
                for line in _login_defaults_cfg.splitlines()),
            "the login defaults must name a MoOS greeter wallpaper plugin")
    require("wallpapers/Fedora" not in _login_defaults_cfg,
            "the login defaults still POINT at /usr/share/wallpapers/Fedora, a directory "
            "build.sh deletes — a dangling login wallpaper. (Naming it in a comment is "
            "fine and expected; this reads the config, not the prose.)")
require("/usr/lib/tmpfiles.d/moos-plasmalogin-greeter.conf" in _build
        and "/usr/share/moos/plasmalogin/kdeglobals" in _build,
        "build.sh must provision the plasmalogin greeter account's palette deterministically; "
        "unprovisioned, /var/lib/plasmalogin decides the login chrome's colours")
require("r! /var/lib/plasmalogin/.config/kdeglobals" in _build,
        "the greeter palette tmpfiles rule needs a boot-only `r!` before its `C+`: measured on "
        "systemd 259.8, `C+` does NOT replace an existing file, so the rule would be a no-op on "
        "every machine that already carries the wrong palette — which is the bug it fixes")
require("carries an active greeter key that" in _build
        and "WallpaperPluginId|Theme|Background|Image|ShowClock" in _build,
        "build.sh must reject an ACTIVE greeter key in /etc/plasmalogin.conf — that "
        "file outranks every MoOS login layer. It must NOT assert the file is absent: "
        "the base ships it as a fully-commented template, so 'absent' fails every build")

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

# First-party QML no longer manufactures private base64 SVG libraries at
# runtime. Every control glyph resolves through the owned symbolic icon theme
# and the shared SymbolIcon component; this is both cheaper and keeps one
# geometry/palette contract across Welcome, Installer and Store.
for _glyph_qml in (
    "system_files/usr/share/moos/apps/installer/main.qml",
    "system_files/usr/share/moos/apps/store/main.qml",
    "system_files/usr/share/moos/apps/welcome/main.qml",
):
    _glyph_text = code(read(_glyph_qml), "slash")
    require("TextEncoder" not in _glyph_text,
            f"{_glyph_qml} must not use browser-only TextEncoder in QML")
    require("Qt.btoa" not in _glyph_text and "data:image/svg+xml" not in _glyph_text,
            f"{_glyph_qml} must not rebuild first-party glyphs as data-URL SVGs")
    require('import "../ui" as MoOSUi' in _glyph_text
            and "component Glyph: MoOSUi.SymbolIcon" in _glyph_text,
            f"{_glyph_qml} must consume the shared MoOS symbolic icon layer")

# ── No MoOS surface may animate forever without a guard ──────────────────────
# The dashboard has had this contract for a while (test_moos_ui2.py enforces it for
# every wallpaper/plasmoid QML file). The APPS never did, and that is exactly where
# it broke: Mo Store's rail status dot carried `loops: Animation.Infinite` with no
# `running:` at all, so it pulsed for the entire life of the window. One 8 px dot is
# not the cost — holding the QML render loop at full frame rate and repainting a 4K
# window is, and it measured ~11% of a CPU core on an idle desktop, paid by any
# session that merely had the Store restored behind other windows.
#
# So the contract now covers every QML MoOS ships: an endless animation must say
# when it runs. `running:` may name any condition (visibility, readiness, focus);
# what is forbidden is having none.
_infinite = re.compile(r"loops\s*:\s*Animation\.Infinite")
for _qml_root in ("system_files/usr/share/moos/apps",
                  "system_files/usr/share/plasma/plasmoids",
                  "system_files/usr/share/plasma/wallpapers",
                  "system_files/usr/share/plasma/shells",
                  "system_files/usr/share/plasma/look-and-feel"):
    for _qml in sorted(Path(_qml_root).rglob("*.qml")):
        # Strip // comments first: every one of these gates forbids or requires a
        # token that the comment EXPLAINING the fix has to be able to name. A
        # WHY comment quoting `running: true` is not an ungated animation.
        _text = code(_qml.read_text(encoding="utf-8"), style="slash")
        for _loop in _infinite.finditer(_text):
            _window = _text[max(0, _loop.start() - 320):_loop.end() + 320]
            require(
                re.search(r"running\s*:", _window) is not None,
                f"{_qml}:{_text[:_loop.start()].count(chr(10)) + 1} animates forever with "
                "no `running:` guard — an unguarded infinite animation keeps the render "
                "loop at full frame rate for as long as the surface exists",
            )

# ── The cloud edition is a third image, not a second project ─────────────────
# MOOS_CLOUD_PLAN.md §1: moos-cloud shares this tree, these gates and this signing
# key with the two desktop editions, because a second repository means every fix
# gets made twice or forgotten once. That only holds if the wiring is actually
# there — a build recipe nobody can run and a matrix row that does not exist are
# how a "third edition" quietly becomes documentation.
_build_sh_raw = read("build_files/build.sh")
require("is_cloud()" in _build_sh_raw and "is_desktop()" in _build_sh_raw,
        "build.sh must define is_cloud/is_desktop predicates — a dozen inline string "
        "comparisons is how one of them ends up misspelled and silently builds the "
        "wrong edition")
require('moos|moos-nvidia|moos-cloud)' in _build_sh_raw,
        "build.sh must reject an unknown edition name outright — an unrecognised "
        "MOOS_IMAGE_NAME currently falls through to a desktop build that exits 0")
require("if is_desktop; then\n    dnf5 -y install gamescope" in _build_sh_raw,
        "the gaming host stack must be desktop-only — a headless VPS has no display "
        "and no controller to justify it")
require("_core_power+=(waydroid gamemode mangohud steam-devices)" in _build_sh_raw,
        "waydroid and the gamepad/VR udev rules must be desktop-only in the Core "
        "Power list")
for _cloud_promise, _why in (
    ("systemctl enable sshd.service", "a headless server with sshd off is unreachable"),
    ("PasswordAuthentication no", "a public IPv4 with password auth is a brute-force queue"),
    ("console=ttyS0", "without a serial console a failed boot is invisible to the provider's rescue"),
    ("serial-getty@ttyS0.service", "the serial console needs a getty to be usable, not just kernel output"),
    ('"blurEnabled": "false"', "llvmpipe cannot afford blur — a cloud VM renders on the CPU"),
):
    require(_cloud_promise in _build_sh_raw,
            f"build.sh's cloud section must set `{_cloud_promise}` — {_why}")

_workflow = read(".github/workflows/build.yml")

# EVERY edition, from ONE push, or "we all share one tree" is a slogan.
#
# The whole argument for keeping three editions in one repository (MOOS_CLOUD_PLAN
# §1) is that a fix lands once and reaches every machine. That is only true while
# every edition is a row in the same matrix, built from the same checkout of the
# same commit. Drop a row and that edition simply stops moving: no error, no failed
# job, just an image tag that quietly stays at whatever it was, while `main` and the
# other editions march on. The owner would keep shipping fixes and keep wondering
# why one machine never changed.
#
# moos-nvidia is the dangerous one to lose, because it is the maintainer's own
# daily driver — the machine AGENTS.md opens by warning about.
for _edition, _who in (
    ("moos",        "the generic desktop edition"),
    ("moos-nvidia", "the maintainer's own daily-driver machine"),
    ("moos-cloud",  "every server converted with moos-cloud-convert"),
):
    require(f"image_name: {_edition}" in _workflow,
            f"the CI matrix no longer builds {_edition}. That edition stops receiving "
            f"every fix merged from now on, silently — nothing fails, the tag just "
            f"stops moving. This one is {_who}.")

# One checkout per run, and the signing step keyed on the matrix name, is what makes
# the three images the SAME source rather than three things that happen to be built
# nearby. A hardcoded IMAGE_NAME in the signing step would sign one edition's digest
# under another's name.
require("cosign sign -y --key env://COSIGN_PRIVATE_KEY" in _workflow
        and '"${IMAGE_REGISTRY}/${IMAGE_NAME}@${DIGEST}"' in _workflow,
        "each matrix job must sign ITS OWN image name and digest. A literal image "
        "name here signs one edition's bytes under another edition's tag, and the "
        "installed systems enforce that signature.")
require("build-cloud:" in read("Justfile"),
        "the Justfile must carry a build-cloud recipe, or the edition can only be "
        "built by hand-typing the build args")

# ── KWallet is opt-out at the OS layer, not merely unused by one app ─────────
# First-party apps own private XDG stores, so the image must neither advertise a
# Secret portal nor start/unlock a wallet at login.
_portals = read("system_files/etc/xdg-desktop-portal/kde-portals.conf")
require("impl.portal.Secret" not in _portals,
        "MoOS must not advertise KWallet as its Secret portal")
_walletrc = code(read("system_files/etc/xdg/kwalletrc"))
require(re.search(r"^\s*Enabled\s*=\s*false\s*$", _walletrc, re.MULTILINE) is not None,
        "/etc/xdg/kwalletrc must keep KWallet disabled for fresh profiles")
require(not (ROOT / "system_files/usr/lib/systemd/user/moos-secret-service.service").exists(),
        "the old ksecretd compatibility unit must not ship")
_build = code(read("build_files/build.sh"))
require("systemctl --global mask moos-secret-service.service" in _build
        and "plasma-kwallet-pam.service" in _build,
        "the image must mask both the former compatibility service and PAM wallet helper")
require("remove --no-autoremove" in _build and "kwalletmanager5" in _build
        and "pam-kwallet" in _build,
        "the wallet manager UI and PAM auto-unlocker must be removed without "
        "autoremoving Plasma dependencies")

# Existing users carry Enabled=true from the brief wallet-enabled release.
_ui_migrate = code(read("system_files/usr/bin/moos-ui-migrate"))
for _wallet_migration_promise in (
    "disable_wallet_v2",
    "wallet-disabled-v2.done",
    "--key Enabled false",
    "systemctl --user mask --now moos-secret-service.service",
    "org.freedesktop.secrets",
    "moai-credential-store",
):
    require(_wallet_migration_promise in _ui_migrate,
            f"the existing-user wallet repair is incomplete: missing "
            f"{_wallet_migration_promise!r}")

# A running wallet must stay visible in diagnostics.
_selfcheck = code(read("system_files/usr/bin/moos-selfcheck"))
require("freedesktop" in _selfcheck and "secrets" in _selfcheck
        and "kwalletd" in _selfcheck and "ksecretd" in _selfcheck
        and "ListNames" in _selfcheck,
        "moos-selfcheck must ask the session bus whether a disabled wallet is "
        "still active")

# ── The vendored MoPlayer must be buildable by the Flutter the image pins ────
# moplayer/ is a copy of a live project, and a live project is being opened in an
# editor. A Flutter SDK newer than the pinned one rewrites pubspec.lock's `sdks:`
# floor on any `pub get` — observed here as `dart: ">=3.9.0 <4.0.0"` becoming
# `">=3.12.0 <4.0.0"` when the workstation moved to Flutter 3.44.8 while the
# Containerfile was still building with 3.35.1.
#
# Commit that and the image build dies inside the container at `flutter pub get`,
# twenty minutes in, with a version-solving error that says nothing about the
# editor that caused it. This gate costs milliseconds and names the cause.
#
# The map is deliberately explicit: bumping FLUTTER_VERSION means adding its Dart
# version here, which is the moment to re-vendor the lock as well.
_FLUTTER_TO_DART = {
    "3.35.1": (3, 9, 0),
    "3.44.8": (3, 12, 2),
}
_containerfile = read("Containerfile")
_flutter_pin = re.search(r"ARG FLUTTER_VERSION=([0-9.]+)", _containerfile)
require(_flutter_pin is not None,
        "the Containerfile must pin FLUTTER_VERSION — an unpinned SDK builds a "
        "different MoPlayer every day")
if _flutter_pin:
    _pinned = _flutter_pin.group(1)
    require(_pinned in _FLUTTER_TO_DART,
            f"Flutter is pinned to {_pinned} but tests/verify_user_experience.py does not "
            "know which Dart that ships — add it to _FLUTTER_TO_DART and re-vendor "
            "moplayer/pubspec.lock with that SDK")
    if _pinned in _FLUTTER_TO_DART:
        _lock_floor = re.search(r'dart:\s*">=\s*([0-9]+)\.([0-9]+)\.([0-9]+)',
                                read("moplayer/pubspec.lock"))
        require(_lock_floor is not None,
                "moplayer/pubspec.lock has no readable dart SDK floor")
        if _lock_floor:
            _floor = tuple(int(g) for g in _lock_floor.groups())
            require(_floor <= _FLUTTER_TO_DART[_pinned],
                    f"moplayer/pubspec.lock demands Dart >={'.'.join(map(str, _floor))} but the "
                    f"image builds with Flutter {_pinned} (Dart "
                    f"{'.'.join(map(str, _FLUTTER_TO_DART[_pinned]))}) — a newer local SDK "
                    "rewrote the lock; restore it from MoPlayer's committed copy")

# #14 CI must verify the signature against the SAME public key the OS enforces.
# (The theme-safety and UI2 gates already run transitively via this file's own
# subprocess invocations above, so they are wired — no separate build.yml entry.)
_byml = read(".github/workflows/build.yml")
require("cosign verify --key cosign.pub" in _byml,
        "build.yml must verify the signature against the OS-enforced public key")


# ── A private desktop must share the user's session bus ───────────────────────
#
# `moos-cloud-desktop own <user>` gives a second developer their own virtual Plasma.
# Wrapping that compositor in `dbus-run-session` is the intuitive way to give a
# headless session a bus, and it silently removes the user's input.
#
# dbus-run-session makes a NEW bus (/tmp/dbus-XXXXXXXX); the systemd --user manager
# stays on /run/user/$uid/bus. startplasma-wayland asks org.freedesktop.systemd1 — on
# the SESSION bus — to start the systemd-managed session; on a private bus that name
# does not exist, so it falls back to legacy startup and plasma-workspace.target never
# runs. graphical-session.target is BindsTo that target, so it stays inactive, so
# xdg-desktop-portal is refused ("Dependency failed for Portal service", every 30s) —
# and the portal is Mo PC Remote's PRIMARY input path, with ydotoold/uinput only a
# fallback that a seatless session cannot use either.
#
# Measured on the real server: the second developer's desktop streamed video and
# accepted no keyboard or mouse at all, with `systemctl --failed` empty throughout.
# ── "Animations off" has to reach the endless ones ────────────────────────────
#
# Anything that loops Animation.Infinite inside plasmashell runs for the entire
# uptime of the session. Gated on `visible` alone it keeps running when the user —
# or the whole cloud edition — has asked for no motion, and it is never reported,
# because a busy rasterizer is not an error.
#
# org.moos.heroclock shipped three of them (breathing glow, breathing emblem,
# spinning comet ring) all gated `running: hero.visible`. The RotationAnimator is
# the worst of the three: Animator types run on the RENDER thread, so it asks the
# compositor for frames while the main thread sits idle — profiling the main loop
# shows nothing and the cost appears as a saturated llvmpipe. Same shape as the Mo
# Store rail dot that burned a core to blink (aee2724).
#
# It matters most on MoOS Cloud, which sets AnimationDurationFactor=0 precisely so
# ambient motion stops: there every pixel is rasterised on the CPU and nobody is
# looking at the emblem.
#
# The gate: a `running:` on an infinite loop must consult something motion-related,
# not merely whether the item is on screen. Kirigami.Units.longDuration is what the
# factor actually moves, so a gate built on it is the honest one.
#
# AND IT HAS TO BE `> 1`, NOT `> 0` — this gate spent its whole life asserting the
# off-by-one that made every MoOS motion gate a no-op. Kirigami FLOORS longDuration
# at 1 when AnimationDurationFactor is 0; it never reaches 0. So `> 0` is true even
# with animations fully disabled, and "animations off" stopped nothing anywhere in
# MoOS — the wallpaper, the bento, the hero clock, all of it kept running. KDE's own
# code says so in the only way that matters: all three shipped BusyIndicator.qml
# (org/kde/breeze, org/kde/desktop, org/kde/plasma/components) gate their infinite
# spinner on `longDuration > 1`, and RejectPasswordPathAnimation.qml writes
# `longDuration <= 1 ? 1 : 600`. `> 0` remains correct for a ONE-SHOT transition,
# where a 1 ms duration is harmless; it is only wrong as a gate for an endless one.
# This gate now requires `> 1` and REJECTS `> 0` in a motion-gate definition, so the
# bug cannot be reintroduced by copying an old line.
#
# The roots also have to cover every surface that ships an endless animation, not
# just the two that were noticed first. The lock screen — the surface that stays up
# for HOURS — ran six unguarded infinite animations at a measured 4% of a core, and
# the power screen ran three, because neither shells/ nor look-and-feel/ was ever
# scanned here.
_MOTION_ROOTS = ("system_files/usr/share/plasma/plasmoids",
                 "system_files/usr/share/plasma/wallpapers",
                 "system_files/usr/share/plasma/shells",
                 "system_files/usr/share/plasma/look-and-feel",
                 # The MoOS apps were the blind spot: Mo AI alone shipped TWELVE
                 # unguarded Animation.Infinite loops (the idle-orb breathing, the
                 # thinking halo, ambient particles), and Welcome — which autostarts
                 # on every first login — ran two on the first screen a new user
                 # sees. None were scanned here, so all of it passed green while
                 # "disable animations" stopped none of it.
                 "system_files/usr/share/moos/apps")
_INFINITE = re.compile(r"loops:\s*Animation\.Infinite")
for _root_name in _MOTION_ROOTS:
    _root_dir = ROOT / _root_name
    if not _root_dir.is_dir():
        continue
    for _qml in sorted(_root_dir.rglob("*.qml")):
        _text = code(_qml.read_text(encoding="utf-8", errors="replace"), style="slash")
        if not _INFINITE.search(_text):
            continue
        _rel = _qml.relative_to(ROOT)
        # The file must be connected to a motion gate — either by DEFINING one on
        # Kirigami.Units.longDuration, or by taking `motionEnabled` from its parent.
        # The wallpaper's cards (SystemCard, WeatherScene, GlassCard) do the latter:
        # DashboardBento owns the gate and passes it down, which is correct and which
        # a stricter check here wrongly called broken.
        require("Kirigami.Units.longDuration > 1" in _text or "motionEnabled" in _text,
                f"{_rel} loops Animation.Infinite but is wired to no motion gate at all "
                "— it neither defines one on Kirigami.Units.longDuration nor accepts a "
                "motionEnabled from its parent. With animations off it keeps running for "
                "the whole session — on the cloud edition that is a rasterizer burning "
                "CPU on a desktop nobody is looking at, reported by nothing.")
        # The off-by-one, refused by name. A file may still write `> 0` for a
        # one-shot Behavior/transition, so only a MOTION GATE is rejected: a
        # `motionEnabled` definition, or the `running:` of an endless loop.
        for _bad in re.finditer(r"(motionEnabled[^\n]*|running:[^\n]*)"
                                r"Kirigami\.Units\.longDuration\s*>\s*0", _text):
            require(False,
                    f"{_rel} gates motion on `Kirigami.Units.longDuration > 0`: "
                    "Kirigami floors longDuration at 1, never 0, so that expression is "
                    "true even with animations fully disabled and the gate never fires. "
                    "Use `> 1`, as KDE's own three BusyIndicator.qml do.")
        for _m in _INFINITE.finditer(_text):
            _block = _text[max(0, _m.start() - 400):_m.start() + 400]
            _running = re.search(r"running:\s*([^\n]+)", _block)
            if not _running:
                continue
            _expr = _running.group(1)
            require("motionEnabled" in _expr or "longDuration" in _expr,
                    f"{_rel} has an Animation.Infinite whose `running:` is "
                    f"`{_expr.strip()}` — that does not consult the motion gate, so "
                    "'animations off' never stops it.")

# ── A motion gate must be CONNECTED, not merely present ───────────────────────
#
# The previous gate proved the word `motionEnabled` appears. DashboardBento showed
# that is not enough: it declared
#
#     readonly property bool motionEnabled: root.visible && Kirigami.Units.longDuration > 0
#
# — its own gate, invented locally, consulting neither the plugin's AmbientMotion/
# MotionMode key nor a value handed down by a parent. So it satisfied every check
# here while eight infinite card animations stayed unreachable: `moos-theme motion
# still` could not stop a single one of them, and neither could Plasma's own
# "disable animations". `readonly` made it worse — even the parent could not
# override it.
#
# The rule: a file that DEFINES motionEnabled must root that definition in
# something the user can actually change. WHICH root is legitimate depends on what
# the surface has:
#
#   * A KPackage that ships contents/config/main.xml (the wallpaper, the brand
#     plasmoid) has its OWN motion key, so its gate must consult it. This is the
#     DashboardBento case — the key existed, the bento just never looked at it.
#   * A surface with no plugin configuration at all (the splash, the logout screen,
#     the lock screen, the clock plasmoids) has exactly one honest signal: Plasma's
#     animation-speed setting, i.e. `Kirigami.Units.longDuration > 1`.
#
# `visible` alone is never a motion gate under either rule — it is the shape of the
# bug.
# Capture the WHOLE expression, not just its first physical line. `[^\n]+`
# stops at the first newline, so a gate that is correct but wrapped across
# lines is judged by where its author put the line break: DashboardBento's
# `motionEnabled: root.visible\n && root.resolvedMotionMode > 0 ...` read to
# this gate as the bare `root.visible` bug it is meant to catch. A QML binding
# continues while the line ends in an operator or the next line starts with one.
_MOTION_DEF = re.compile(
    r"property\s+bool\s+motionEnabled\s*:\s*((?:[^\n]*(?:&&|\|\||\?|:)\s*\n\s*)*[^\n]+)")
for _root_name in _MOTION_ROOTS:
    _root_dir = ROOT / _root_name
    if not _root_dir.is_dir():
        continue
    for _qml in sorted(_root_dir.rglob("*.qml")):
        _text = code(_qml.read_text(encoding="utf-8", errors="replace"), style="slash")
        # Walk up to the KPackage root to see whether this surface owns a config
        # schema; contents/ui/foo.qml -> contents/config/main.xml.
        _pkg_config = next(
            (parent / "contents/config/main.xml" for parent in _qml.parents
             if (parent / "contents/config/main.xml").is_file()), None)
        for _def in _MOTION_DEF.finditer(_text):
            _expr = _def.group(1).strip()
            if _pkg_config is not None:
                # The message below has always offered a second legitimate shape —
                # a pure CONSUMER that takes the policy from its parent — but the
                # code never implemented it. DashboardBento is exactly that case
                # and cannot use `required property`: build.sh loads it in a bare
                # Loader for the QML smoke gate, where a required property nobody
                # sets is a load error. Accept a definition rooted in a property
                # the parent feeds, as long as that property names the key.
                require("configuration." in _expr or "MotionMode" in _expr
                        or "AmbientMotion" in _expr
                        or re.search(r"property\s+int\s+\w*MotionMode\b", _text),
                        f"{_qml.relative_to(ROOT)} defines `motionEnabled: {_expr}` "
                        "while its package ships a config schema at "
                        f"{_pkg_config.relative_to(ROOT)} — the gate must consult that "
                        "key (MotionMode/AmbientMotion). A file that only CONSUMES "
                        "motion must take it as a `required property` from its parent "
                        "instead of inventing its own.")
            else:
                require("longDuration > 1" in _expr,
                        f"{_qml.relative_to(ROOT)} defines `motionEnabled: {_expr}` — "
                        "this surface has no config schema, so its only honest motion "
                        "signal is Plasma's animation speed: "
                        "`Kirigami.Units.longDuration > 1`.")


# ── Two humans, one machine: separate front doors, ONE brain ──────────────────
#
# Mo AI's three services are per-USER and were on fixed ports, which is correct for
# one human per machine and silently wrong the moment `moos-cloud-dev` adds a
# second developer to a shared server. Measured live with two accounts:
# moalfarras's moai-agent-api FAILED on "[Errno 98] Address already in use", while
# momo's control and gateway reported ACTIVE and spun for ever on "port 8080 busy,
# retrying in 2s" — green and non-functional.
#
# Worse than a crash: `runuser -u momo -- curl http://127.0.0.1:8080/v1/models`
# ANSWERED. The second developer's Mo AI was reaching the first's gateway, the one
# component designed to be the only thing that ever sees the cloud API key. There
# is no local auth to stop it — X-Moai-Agent/X-Moai-Control guard against web
# pages, not against another account.
_ports_gen = read("system_files/usr/lib/systemd/user-environment-generators/60-moai-ports")
_ports_code = code(_ports_gen)
for _var in ("MOAI_GATEWAY_PORT", "MOAI_CONTROL_PORT", "MOAI_AGENT_PORT"):
    require(_var in _ports_code,
            f"60-moai-ports no longer emits {_var}, so that service falls back to its "
            "fixed port and two accounts on one machine collide again.")
require("(uid - 1000)" in _ports_code,
        "60-moai-ports must derive the offset from the uid — that is what keeps uid 1000 "
        "(every single-user desktop, including the maintainer's) on exactly the ports it "
        "has always used while giving a second account its own.")

# THE SHARED-BRAIN INVARIANT. Read this before 'fixing' the generator for symmetry.
#
# MOAI_LOCAL_PORT is deliberately NOT offset. The gateway decides whether to start
# the engine with local_online() — an HTTP probe of 127.0.0.1:<LOCAL_PORT>, not a
# systemd query. Because every account probes the SAME 8081, the first chat that
# needs the brain starts it and every other account's gateway finds it already
# answering and forwards to it. One model resident in RAM for the whole server.
#
# Offset this one "for consistency" and each account silently loads its own copy —
# on a 15 GB box with a 7B model that is the difference between working and
# swapping to death, and nothing would report it as an error.
require("MOAI_LOCAL_PORT" not in _ports_code,
        "60-moai-ports sets MOAI_LOCAL_PORT. It must NOT: the local brain is shared on "
        "8081 by design, and giving each account its own port makes each one load a "
        "SEPARATE copy of the model into RAM, with no error anywhere to say so.")

# The app has to be told which door is its own, or the whole scheme is theatre: the
# services would move and the UI would keep opening 8080.
_moai_launcher = code(read("system_files/usr/bin/moai"))
for _flag in ("--gateway-port", "--control-port", "--agent-port"):
    require(_flag in _moai_launcher,
            f"the moai launcher does not pass {_flag} to the app. The services would "
            "listen on this account's ports while the UI still opened the first "
            "account's — which is exactly the cross-user leak this replaced.")
_moai_qml_ports = read("system_files/usr/share/moos/apps/moai/main.qml")
require('root.argPort("--gateway-port"' in _moai_qml_ports
        and 'root.argPort("--control-port"' in _moai_qml_ports
        and 'root.argPort("--agent-port"' in _moai_qml_ports,
        "main.qml must resolve all three endpoints through argPort(). A hardcoded "
        "127.0.0.1:8080 in the app sends the second developer to the first one's "
        "gateway however carefully the services were separated.")
require('"http://127.0.0.1:8080/v1/chat/completions"' not in _moai_qml_ports,
        "main.qml still hardcodes the gateway URL — the per-user port scheme cannot work "
        "while the app ignores it.")


# ── Mo AI's brain: the right model for the machine, and neither Modelfile lost ──
#
# moos-ensure-brain picks between two brains by measured VRAM, and each names its
# own base. Nothing else in the tree would notice if a Modelfile went missing:
# the script is failure-tolerant by design, so a missing file means it quietly
# leaves whatever brain is there — which on a fresh machine is none.
_brain = read("system_files/usr/bin/moos-ensure-brain")
_mf_cpu = read("system_files/usr/share/moos/containers/moai-brain.Modelfile")
_mf_gpu = read("system_files/usr/share/moos/containers/moai-brain-gpu.Modelfile")

require("FROM qwen2.5:7b-instruct" in _mf_cpu,
        "the CPU Modelfile no longer builds from qwen2.5:7b-instruct — the measured "
        "fast, non-thinking brain for a GPU-less machine (MoOS Cloud).")
require("FROM qwen3:8b" in _mf_gpu,
        "the GPU Modelfile no longer builds from qwen3:8b — the measured best Arabic, "
        "code and repair brain, and the only one of the two that wants a real card.")
for _name, _mf in (("moai-brain.Modelfile", _mf_cpu), ("moai-brain-gpu.Modelfile", _mf_gpu)):
    require("PARAMETER num_ctx 24576" in _mf,
            f"{_name} no longer sets num_ctx 24576. The SAME model serves OpenClaw, whose "
            f"system+tools prompt alone is ~11.5k tokens: at a smaller window every Telegram "
            f"turn dies with 'Context overflow (precheck)'. moos-ensure-brain reconciles "
            f"openclaw.json to this exact number, so the two cannot drift apart.")
    require('SYSTEM ""' in _mf,
            f"{_name} bakes a SYSTEM prompt. main.qml sends the real Mo AI prompt plus live "
            f"machine context; a baked one is what made an earlier brain answer in Arabic "
            f"even when it was asked in English.")
# Only the FROM line, not the prose: both Modelfiles deliberately NAME
# qwen2.5-coder in a comment to record why it must not be used.
require(not any(ln.strip().lower().startswith("from") and "coder" in ln.lower()
                for mf in (_mf_cpu, _mf_gpu) for ln in mf.splitlines()),
        "a Modelfile now builds FROM a coder model. qwen2.5-coder:7b was MEASURED and "
        "rejected: excellent one-liners, broken Arabic — it emitted a non-phrase and "
        "invented an `lsof -m` flag. And qwen3-coder's smallest tag is ~19 GB of weights, "
        "which does not fit the 8 GB card this image targets.")
require('grep -qi "$want"' in _brain,
        "moos-ensure-brain's 'already correct?' check is hardcoded to one model family "
        "again. On a GPU machine that declares the correct qwen3:8b brain wrong and "
        "rebuilds it down to the CPU model on every single login.")
require("nvidia-smi" in _brain and "7500" in _brain,
        "moos-ensure-brain no longer picks the brain by measured VRAM. A card under ~7.5 GB "
        "cannot hold qwen3:8b resident, and a spilled model on this image took the whole "
        "desktop down with it (moos-gpu-headroom exists because of NVRM: invalid mmap context).")

_own = read("system_files/usr/bin/moos-cloud-desktop")
_own_code = code(_own)
require("dbus-run-session" not in _own_code,
        "moos-cloud-desktop runs the private compositor under `dbus-run-session`. That "
        "puts Plasma on a different session bus from the systemd --user manager, so "
        "plasma-workspace.target never starts, graphical-session.target stays inactive, "
        "xdg-desktop-portal is refused for ever — and the second user's desktop accepts "
        "no keyboard or mouse input, with nothing showing as failed.")
require("DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/" in _own_code,
        "moos-cloud-desktop must point the private desktop at the user's REAL session "
        "bus (/run/user/$uid/bus) — it is what makes startplasma-wayland take the "
        "systemd path, and therefore what makes the portal (and input) work.")
# ── The RemoteDesktop grant a seatless desktop cannot click for itself ────────
#
# Read off a working account, not guessed: a grant is an entry in the permission
# store keyed by the RESTORE TOKEN (a random string), carrying KDE's session data
# blob — plus that same token in ~/.config/MoRemote/portal-restore-token. Seeding
# either half alone does nothing, and an entry keyed anything but the token is
# never looked up. That is exactly why an earlier `flatpak permission-set
# remote-desktop ... moos-pc-remote` looked like it silently failed: it wrote an
# entry, under a key the portal never reads, with no data.
_grant = read("system_files/usr/lib/moos/moos_portal_grant.py")
# A second desktop with no HTTPS name is a QUIETLY worse product, not a broken
# one: canDecodeH264() requires window.isSecureContext, so over plain http the
# phone falls back to JPEG — ~79 Mbit/s at 1080p against H.264's ~4.3 — and the
# clipboard and PWA install disappear with it. Nothing reports any of that.
require("tailscale serve --bg --https=" in _own_code,
        "moos-cloud-desktop no longer publishes an HTTPS name for the private desktop. "
        "Without a secure context Mo PC Remote loses WebCodecs and drops to JPEG, which "
        "is survivable on a LAN and unusable on mobile data.")
require("8443 + uid - 1001" in _own_code,
        "the private desktop's HTTPS port is no longer derived clear of the agent's own "
        "port. Serving --https on the port the agent already binds does NOT terminate TLS: "
        "the tailnet address answers the app in cleartext and curl reports 'wrong version "
        "number' — a secure-looking URL that is not one. Measured, not theorised.")
require("grant-input) need_root" in _own_code,
        "moos-cloud-desktop lost its grant-input command. Without it the second desktop's "
        "input cannot be turned on at all: the portal wants one interactive approval and a "
        "--virtual session has nobody to give it.")
require("portal-restore-token" in _grant,
        "moos_portal_grant.py no longer writes the restore token to the file the agent "
        "reads. The permission-store entry alone is a grant nobody ever asks for.")
require('get_type_string() == "()"' in _grant,
        "moos_portal_grant.py no longer rejects an entry with empty session data. An entry "
        "without KDE's blob is the exact broken shape this replaces — the portal ignores it "
        "and prompts anyway, on a screen nobody can click.")
require("Gio.bus_get_sync" in _grant and "new_for_address_sync" not in _grant,
        "moos_portal_grant.py connects to a bus ADDRESS instead of its own session bus. A "
        "user's bus is 0700 and dbus-broker authenticates the peer uid, so one process "
        "cannot reach both accounts — that is why this is a dump/apply pair.")
require("ExecStartPre=-/usr/bin/moos-ui-migrate --input-only" in _own_code,
        "the private desktop starts kwin_wayland by hand, so it inherits NONE of the "
        "drop-ins on plasma-kwin_wayland.service — and every pre-KWin repair MoOS does "
        "(Num Lock default, legacy keyboard migration, the XDG data directories whose "
        "absence keeps ksycoca rebuilding at ~79% of a core) was skipped for the second "
        "developer alone. It must run the same one-shot every other session runs.")

# A directory that is in XDG_DATA_DIRS and does not exist never matches its
# recorded timestamp, so KSycoca answers "rebuild" for ever — a full, synchronous
# rebuild every time anything looks up a service. flatpak's user-environment
# generator puts the exports dir in XDG_DATA_DIRS for every account; it exists
# only once that account has installed something. See MOOS_ROADMAP.md item 6.
for _xdg_dir in ("/applications", "/icons", "/flatpak/exports/share/applications"):
    require(f'{{XDG_DATA_HOME:-$HOME/.local/share}}{_xdg_dir}"' in _ui_migrate
            or f'XDG_DATA_HOME:-$HOME/.local/share}}{_xdg_dir}' in _ui_migrate,
            f"moos-ui-migrate no longer ensures ~/.local/share{_xdg_dir} exists. An "
            f"unstattable directory in XDG_DATA_DIRS is what keeps KSycoca rebuilding.")
require(_ui_migrate.index("XDG_DATA_HOME:-$HOME/.local/share}/applications")
        < _ui_migrate.index('[ "${1:-}" = "--input-only" ] && exit 0'),
        "the XDG data directories are created AFTER the --input-only early exit, so the "
        "one invocation that runs before KWin — the only one that can stop the session "
        "from starting a doomed sycoca — never creates them.")

if errors:
    print("MoOS user-experience gate failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print("MoOS user-experience gate passed")
