#!/usr/bin/env python3
"""Fail the image build when active user-facing MoOS selectors regress."""

import os
from pathlib import Path
import re


def text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def config(raw: str) -> str:
    """Strip KConfig comments so a gate cannot be satisfied by the prose explaining it.

    Every config in this repo documents the bug it prevents, so the string a gate searches for
    is usually sitting in a comment two lines above the fix. `tests/verify_user_experience.py`
    has carried a `code()` helper for exactly this reason; this file had none, and its login
    screen gate asserted a wallpaper name that its own drop-in explains at length.
    """
    return "\n".join(
        line for line in raw.splitlines() if not line.lstrip().startswith("#")
    )


def source(raw: str, prefix: str = "//") -> str:
    """Strip source comments before asserting implementation tokens.

    Store and Welcome deliberately document the security boundary they enforce.
    Searching the raw source would therefore let that documentation satisfy a
    gate after the real call had been removed — the same green-but-broken class
    of failure as searching comments in KConfig above.
    """
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
    return "\n".join(
        line for line in raw.splitlines()
        if not line.lstrip().startswith(prefix)
    )


errors = []


def require(ok: bool, message: str) -> None:
    if not ok:
        errors.append(message)


# The boot splash must actually appear. Plymouth only draws its graphical theme when the
# kernel command line carries `rhgb`; without it, it falls back to text and the user watches
# systemd scroll past instead of seeing MoOS. The image shipped no kargs at all, so the splash
# depended on whatever the installer happened to write — booting the built disk in a VM showed
# raw systemd text and no splash. bootc kargs.d makes it part of the image.
kargs = list(Path("/usr/lib/bootc/kargs.d").glob("*.toml")) if Path("/usr/lib/bootc/kargs.d").exists() else []
kargs_text = "".join(p.read_text(encoding="utf-8") for p in kargs)
require("rhgb" in kargs_text,
        "the image does not request rhgb — Plymouth would not draw the MoOS splash")
require("quiet" in kargs_text,
        "the image does not request quiet — kernel logs would scroll over the splash")

# The splash it draws must be MoOS's, in the initramfs as well as on disk — the initramfs is
# what owns the screen before the root filesystem is even mounted.
require("Theme=moos" in text("/usr/share/plymouth/plymouthd.defaults"),
        "Plymouth's default theme is not moos")

# The LIVE ISO boot config (this file ships in the image; Titanoboa consumes it).
# It must carry rd.live.overlay.overlayfs=1 — without it the live writable layer
# is a small fixed dm-snapshot COW that fills to 100% within minutes and makes
# systemd freeze ('Freezing execution'). It must also match the installed
# system's flicker-free set so the live boot is not noisier than an install.
iso_yaml = Path("/usr/lib/bootc-image-builder/iso.yaml")
if iso_yaml.is_file():
    iso_text = iso_yaml.read_text(encoding="utf-8")
    require("rd.live.overlay.overlayfs=1" in iso_text,
            "the live ISO kargs lack rd.live.overlay.overlayfs=1 — the live session's COW "
            "would fill and systemd would freeze")
    for karg in ("loglevel=3", "rd.udev.log_level=3", "splash", "plymouth.use-simpledrm"):
        require(karg in iso_text,
                f"the live ISO kargs lack '{karg}' — the live boot is noisier than an installed MoOS")

# Hardware adaptation service must be ENABLED (its multi-user.target.wants symlink
# present), not merely shipped — a first-boot adapter that is never wanted never
# runs. `systemctl enable` in the build lands the symlink under /etc; check both
# /etc and /usr so the gate is robust to how the image records enablement.
hw_wants = [
    Path("/etc/systemd/system/multi-user.target.wants/moos-hardware-adapt.service"),
    Path("/usr/lib/systemd/system/multi-user.target.wants/moos-hardware-adapt.service"),
]
require(any(p.exists() or p.is_symlink() for p in hw_wants),
        "moos-hardware-adapt.service is not enabled (no multi-user.target.wants symlink) — "
        "the hardware adaptation would never run")

# Machine-check logging has one cross-vendor owner. mcelog exits failed on AMD
# CPUs, while Fedora's rasdaemon consumes the kernel RAS/EDAC trace events on
# supported AMD and Intel hardware.
mcelog_mask = Path("/etc/systemd/system/mcelog.service")
require(mcelog_mask.is_symlink() and os.readlink(mcelog_mask) == "/dev/null",
        "mcelog.service is not masked — AMD systems would boot with a failed unit")
rasdaemon_wants = [
    Path("/etc/systemd/system/multi-user.target.wants/rasdaemon.service"),
    Path("/usr/lib/systemd/system/multi-user.target.wants/rasdaemon.service"),
]
require(Path("/usr/sbin/rasdaemon").is_file() or Path("/usr/bin/rasdaemon").is_file(),
        "rasdaemon is missing — machine-check errors would have no cross-vendor logger")
require(any(p.exists() or p.is_symlink() for p in rasdaemon_wants),
        "rasdaemon.service is installed but not enabled")

# The display manager must not race a slow GPU driver. udevadm settle can return
# before /dev/dri/card* exists, at which point the greeter KWin fails once and
# leaves a black tty while the parent service still reports active.
drm_wait = Path("/usr/libexec/moos-wait-drm")
drm_dropin = Path(
    "/usr/lib/systemd/system/plasmalogin.service.d/10-moos-wait-drm.conf"
)
require(drm_wait.is_file() and os.access(drm_wait, os.X_OK),
        "the executable login DRM preflight is missing")
if drm_wait.is_file():
    drm_wait_text = drm_wait.read_text(encoding="utf-8")
    require('"$drm_dir"/card*' in drm_wait_text and "MOOS_DRM_WAIT_STEPS" in drm_wait_text,
            "the login DRM preflight is not card-number-agnostic and bounded")
require(drm_dropin.is_file()
        and "ExecStartPre=/usr/libexec/moos-wait-drm"
        in drm_dropin.read_text(encoding="utf-8"),
        "Plasma Login Manager is not wired to wait for a usable DRM card")

# The static I/O-scheduler udev rule (the build-time half of hardware adaptation)
# must ship and pick a scheduler per device type.
iosched = Path("/usr/lib/udev/rules.d/60-moos-ioschedulers.rules")
require(iosched.is_file(), "the MoOS I/O-scheduler udev rule is missing")
if iosched.is_file():
    rules = iosched.read_text(encoding="utf-8")
    require("nvme" in rules and 'scheduler}="none"' in rules,
            "the I/O-scheduler rule does not set 'none' for NVMe")

# The first screen a new MoOS user sees must be MoOS. plasma-setup.service is Plasma's
# out-of-box wizard; it runs Before=display-manager.service and holds the screen, so it — not
# the MoOS SDDM theme — was what greeted every fresh install: a full-screen "Welcome to Plasma
# Desktop" on Plasma's default wallpaper. Hiding the plasma-welcome *app* did nothing; the
# service is what shows it.
if Path("/usr/lib/systemd/system/plasma-setup.service").exists():
    require(Path("/etc/plasma-setup-done").exists(),
            "the Plasma out-of-box wizard would run and greet the user as 'Plasma Desktop'")
    require(Path("/etc/systemd/system/plasma-setup.service").is_symlink()
            and os.readlink("/etc/systemd/system/plasma-setup.service") == "/dev/null",
            "plasma-setup.service is not masked")

unit = text("/usr/lib/systemd/user/mo-remote-personal.service")
require("ConditionUser=!@system" in unit, "Mo Remote can start for system users")
require("WantedBy=plasma-workspace.target" in unit, "Mo Remote is not Plasma-scoped")
require("WantedBy=default.target" not in unit, "Mo Remote is attached to default.target")
require("WAYLAND_DISPLAY=wayland-0" not in unit, "Mo Remote guesses a Wayland socket")

# A Global Theme Apply (GUI or CLI) carries colours and decoration but NEVER the
# MoOS wallpaper scene, Konsole, GTK or the lock screen — LookAndFeelManager does
# not read them from a package's defaults. The path unit watches kdeglobals (which
# changes on every Apply) and its service reconciles those supplements for whatever
# MoOS look is now current; a GUI pick of "MoOS Nova" that leaves the old wallpaper
# is exactly the green-but-broken failure this guards. A perfect service that is
# not enabled is the same class of invisible fix.
theme_path = text("/usr/lib/systemd/user/moos-theme-sync.path")
theme_service = text("/usr/lib/systemd/user/moos-theme-sync.service")
theme_bin = text("/usr/bin/moos-theme")
require("PathChanged=%h/.config/kdeglobals" in theme_path,
        "the theme supplement watcher does not observe kdeglobals")
require("WantedBy=plasma-workspace.target" in theme_path,
        "the theme watcher is not scoped to the Plasma workspace")
require("ExecStart=/usr/bin/moos-theme reconcile" in theme_service,
        "the theme watcher does not invoke the full-theme reconciler "
        "(a GUI Global Theme pick would leave the wallpaper unchanged)")
require("reconcile()" in theme_bin,
        "moos-theme has no reconcile entry point")
# A Global Theme Apply can REBUILD the desktop containment a few seconds after it
# rewrites kdeglobals, dropping the MoOS wallpaper scene onto org.kde.image with no
# second trigger (the watch only sees kdeglobals) — the "pick a theme, wallpaper
# doesn't follow" bug. reconcile must arm a post-apply watchdog that re-verifies the
# live scene and re-applies it across that rebuild window.
require("settle_desktop_scene" in theme_bin,
        "reconcile has no post-rebuild scene watchdog — a Global Theme pick can "
        "strand the desktop on org.kde.image with no MoOS wallpaper")
# reconcile must handle the MANUAL family too, not only the sunrise/sunset halves —
# otherwise picking Nova/Amethyst/Midnight/Aurora in System Settings still strands
# the wallpaper. Assert the manual family is matched inside reconcile's own scope.
_recon = theme_bin.split("reconcile() {", 1)[-1].split("\n}\n", 1)[0]
for _fam in ("NOVA_LNF", "AMETHYST_LNF", "MIDNIGHT_LNF", "AURORA_LNF"):
    require(_fam in _recon,
            f"reconcile does not carry supplements for a manual pick of ${_fam}")
theme_want = Path("/etc/systemd/user/plasma-workspace.target.wants/moos-theme-sync.path")
require(theme_want.is_symlink()
        and theme_want.resolve() == Path("/usr/lib/systemd/user/moos-theme-sync.path"),
        "moos-theme-sync.path is shipped but not globally enabled for users")

# The reconcile above only STRANDS the wallpaper if the value it writes still
# reaches a real image. That is the desktop wallpaper PLUGIN's job: its
# resolveImage() turns the package DIRECTORY moos-theme hands it into a concrete
# master file. It once named only MoOSUI2Tide and MoOSUI2Graphite, so every other
# theme — Midnight/Nova/Amethyst/Aurora/Arena/Forge/Scholar/Daylight and all
# *Light — fell through to the bare directory, which QML Image cannot open: the
# desktop dropped to a flat colour with NO wallpaper (only Graphite<->Tidal was
# QEMU-tested, so it shipped). Guard the general resolver, and that every shipped
# package actually carries the two masters the resolver maps to.
_wp_src = text("/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui/main.qml")
require('indexOf("MoOSUI2")' in _wp_src,
        "the wallpaper plugin resolver names specific themes only — a new or renamed "
        "MoOS theme would resolve to a bare directory and show no wallpaper")
_pkgs = sorted(Path("/usr/share/wallpapers").glob("MoOSUI2*"))
require(len(_pkgs) >= 2, "no MoOS wallpaper packages are installed")
for _pkg in _pkgs:
    require((_pkg / "contents/images_dark/3840x2160.jpg").is_file()
            and (_pkg / "contents/images/3840x2160.jpg").is_file(),
            f"{_pkg.name} lacks a master the wallpaper resolver maps to "
            "(needs both contents/images/ and contents/images_dark/ 3840x2160.jpg)")

# Each MoOS QML app must pin its running window to its launcher, or the dock shows
# the pinned icon PLUS a second entry for the window (a "duplicate window"). These
# two set their Wayland app_id through moos-qml-shell, but if that shell is ever
# missing the launcher falls back to bare qml-qt6 (app_id org.qt-project.qml-qt6)
# and the duplicate returns — StartupWMClass is the fallback/XWayland safety net.
for _app in ("store", "moai"):
    _de = text(f"/usr/share/applications/org.moos.{_app}.desktop")
    require(f"StartupWMClass=org.moos.{_app}" in _de,
            f"org.moos.{_app}.desktop has no StartupWMClass=org.moos.{_app} — its "
            "window can show as a duplicate dock icon")

# Remote control must ship the PipeWire capture path. The old implementation spawned
# spectacle once per frame — 630ms a frame, i.e. ~1fps, which is what made the phone feel
# broken. If the helper is missing, or is not the PipeWire one, the image would silently
# regress to that. Assert on the real artifacts, not on their absence.
agent = Path("/usr/lib/mo-remote/MoRemotePersonal")
require(agent.is_file(), "Mo Remote agent binary is missing from the image")
helper = Path("/usr/lib/mo-remote/mo-remote-portal.py")
require(helper.is_file(), "Mo Remote portal helper is missing from the image")
if helper.is_file():
    portal = helper.read_text(encoding="utf-8")
    require("pipewiresrc" in portal, "Mo Remote does not capture through PipeWire")
    require("NotifyPointerMotionAbsolute" in portal,
            "Mo Remote does not position the pointer absolutely")
    require("cursor_mode" in portal, "Mo Remote does not control the stream cursor mode")

desktop_dir = Path("/usr/share/applications")
remote_launchers = []
for path in desktop_dir.glob("*.desktop"):
    value = path.read_text(encoding="utf-8", errors="replace")
    if re.search(r"^Name=Mo (?:PC )?Remote(?: Personal)?$", value, re.MULTILINE):
        remote_launchers.append(path.name)
require(remote_launchers == ["org.moos.remote.desktop"],
        f"expected one Mo Remote launcher, found {remote_launchers}")
native = text("/usr/bin/mo-pc-remote")
require('UNIT = "mo-remote-personal.service"' in native,
        "Mo PC Remote does not manage its MoPC backend")
plan = text("/usr/bin/moos-device-plan")
require('"missing_recommended_apps"' in plan and '"nvidia-image"' in plan,
        "hardware-aware first-boot plan is missing")
router = text("/usr/bin/moos-open")
require("do/smart-setup" in router and "do/install-nvidia" in router,
        "smart setup routes are missing")

# The LOGIN SCREEN. Gate the display manager that is actually installed, not the one we wish
# were.
#
# Fedora Kinoite 44 replaced SDDM with plasma-login-manager: `sddm` is not installed at all
# and display-manager.service points at plasmalogin.service. MoOS still shipped an SDDM theme
# and an SDDM config, and this gate asserted "Current=moos" in that config — and passed.
# Meanwhile the real login screen showed Plasma's default wallpaper. A green check on a file
# nobody reads is worse than no check: it buys false confidence.
#
# So: find the display manager, then assert on ITS configuration.
dm = Path("/etc/systemd/system/display-manager.service")
dm_target = os.path.realpath(dm) if dm.exists() else ""
require(dm_target != "", "no display manager is enabled — the system would boot to a console")

if "plasmalogin" in dm_target:
    drop_ins = list(Path("/usr/lib/plasmalogin/plasmalogin.conf.d").glob("*.conf")) \
        if Path("/usr/lib/plasmalogin/plasmalogin.conf.d").exists() else []
    require(drop_ins != [],
            "the login screen has no MoOS drop-in at all — it would show Plasma's default")
    login_conf = config("\n".join(p.read_text(encoding="utf-8") for p in drop_ins))
    require("WallpaperPluginId" in login_conf,
            "the login screen has no MoOS wallpaper configured — it would show Plasma's default")
    effective_login_conf = login_conf
    etc_login_dir = Path("/etc/plasmalogin.conf.d")
    if etc_login_dir.exists():
        effective_login_conf += "\n" + config("\n".join(
            p.read_text(encoding="utf-8") for p in etc_login_dir.glob("*.conf")
        ))
    require(re.search(r"^\s*\[Autologin\]\s*$", effective_login_conf, re.MULTILINE) is None,
            "the installed image enables automatic sign-in; MoOS must always show "
            "the password greeter")

    # The plugin the drop-in names must actually be installed. plasma-login-wallpaper
    # loads it as a KPackage by id; an id that resolves to nothing draws a BLACK login
    # screen with every other check still green. Read the value, then require the
    # package's main.qml on disk — a relationship, not a constant, so swapping the
    # scene later keeps this gate honest.
    plugin_id = re.search(r"^WallpaperPluginId=(\S+)", login_conf, re.MULTILINE)
    require(plugin_id is not None, "WallpaperPluginId has no value in the login drop-in")
    if plugin_id is not None and not plugin_id.group(1).startswith("org.kde."):
        login_scene_qml = Path(
            f"/usr/share/plasma/wallpapers/{plugin_id.group(1)}/contents/ui/main.qml"
        )
        require(login_scene_qml.is_file(),
                f"the login screen names wallpaper plugin {plugin_id.group(1)} but no such "
                "package is installed — the first screen after boot would be black")
        if login_scene_qml.is_file():
            scene_code = "\n".join(
                line for line in login_scene_qml.read_text(encoding="utf-8").splitlines()
                if not line.lstrip().startswith("//")
            )
            for expensive in ("Repeater", "Animation", "ShaderEffect", "Canvas"):
                require(expensive not in scene_code,
                        f"the login wallpaper uses {expensive}; the password boundary "
                        "must render immediately under software fallback")
            require("anchors.left: parent.left" in scene_code
                    and "anchors.top: parent.top" in scene_code,
                    "the login brand is not confined to its safe corner and can "
                    "overlap the centred password surface")

    # The login screen is the FIRST surface of the running system, and the ONLY themed surface a
    # Global Theme cannot reach: LookAndFeelManager runs inside the user's session, long after the
    # greeter has drawn. So it is pinned by hand in the image — and a hand-pinned value is exactly
    # the kind that gets left behind by a theme rollout.
    #
    # It WAS left behind: this gate used to assert the string "NovaHorizon", so when UI2 moved the
    # lock screen to MoOSUI2Graphite and forgot the greeter, the gate stayed green while the user
    # booted into a Nova login screen and a Graphite desktop. Asserting a hard-coded name is what
    # made that invisible.
    #
    # So do not name a wallpaper here. Read the one the LOCK screen uses and require the login
    # screen to use the same one. The two first screens of the system now cannot drift apart, and
    # the next theme family gets this for free.
    lock_conf = config(text("/etc/xdg/kscreenlockerrc"))
    lock_wallpaper = re.search(r"^Image=.*/wallpapers/([A-Za-z0-9_.-]+)",
                               lock_conf, re.MULTILINE)
    require(lock_wallpaper is not None,
            "the lock screen names no wallpaper package, so the login screen cannot be matched to it")
    require(f"/wallpapers/{lock_wallpaper.group(1)}" in login_conf,
            f"the login screen does not use the lock screen's wallpaper "
            f"({lock_wallpaper.group(1)}) — the first screen after boot is off-brand")

    # ── The greeter's own face, and the one line that decides whether it loads ──
    #
    # The wallpaper was only ever half the login screen. The other half — the
    # clock, and the Sleep/Restart/Shut Down buttons — comes from
    # org.kde.breeze.components, which the compiled greeter instantiates and
    # which the LOCK and LOGOUT screens draw from too. MoOS ships its own
    # ActionButton.qml and Clock.qml there, so all three doorways read as one
    # system.
    #
    # But shipping those files is NOT what makes them load. The module's qmldir
    # carries `prefer :/qt/qml/…`, which points Qt at the copies AOT-compiled
    # into libcomponents.so and makes the on-disk .qml decoys. MEASURED
    # 2026-07-17: MoOS's components in the import path with `prefer` intact →
    # stock Breeze rendered anyway. build.sh drops the line; this gate is what
    # stops it silently coming back (a base bump reinstalling plasma-workspace
    # would restore it, and every file check here would stay green while the
    # login screen reverted to Breeze).
    #
    # So assert the DECIDER, not just the files: no prefer line, and the MoOS
    # components present beside it.
    breeze_components = Path("/usr/lib64/qt6/qml/org/kde/breeze/components")
    require(breeze_components.is_dir(),
            "org.kde.breeze.components is missing — the login, lock and logout "
            "screens all draw their buttons from it")
    qmldir = breeze_components / "qmldir"
    require(qmldir.is_file(), "the breeze components module has no qmldir")
    require(not re.search(r"^prefer ", qmldir.read_text(encoding="utf-8"), re.MULTILINE),
            "org.kde.breeze.components/qmldir still has its `prefer :/qt/qml/…` "
            "line, so Qt loads the components COMPILED INTO libcomponents.so and "
            "ignores MoOS's ActionButton.qml/Clock.qml on disk — the login screen "
            "silently reverts to Breeze's full-colour discs while every file check "
            "stays green. build.sh must drop that line.")
    for own in ("ActionButton.qml", "Clock.qml", "UserDelegate.qml"):
        body = (breeze_components / own)
        require(body.is_file(),
                f"MoOS's {own} is missing from org.kde.breeze.components — the "
                "greeter would draw Breeze's")
        require("MoOS" in body.read_text(encoding="utf-8"),
                f"{own} in org.kde.breeze.components is not MoOS's version — the "
                "login screen's clock/buttons/avatar are stock Plasma")

    # A Behavior on a `readonly property` does not warn: QML rejects the WHOLE
    # component, silently — "Did not load any objects", no error line, and on the
    # login screen that means a greeter with no avatar at all. It shipped for
    # exactly one edit of UserDelegate.qml, qmllint passed it, and only rendering
    # it caught it. Cheap check, catastrophic failure.
    for own in ("ActionButton.qml", "Clock.qml", "UserDelegate.qml"):
        text_of = (breeze_components / own).read_text(encoding="utf-8")
        for prop in re.findall(r"readonly\s+property\s+\w+\s+(\w+)", text_of):
            require(re.search(rf"Behavior\s+on\s+{prop}\b", text_of) is None,
                    f"{own} puts a Behavior on the readonly property `{prop}`. QML "
                    "rejects that by failing the entire component with no error "
                    "message — the login screen would draw no avatar/button at all.")

    # Login and lock are not two copies of the same state machine. The lock
    # screen owns the clock; a cold boot owns authentication. Keeping the login
    # clock enabled adds an idle layout before the password layout and competes
    # with the wallpaper's brand in the same top-centre region.
    require(re.search(r"^ShowClock=false", login_conf, re.MULTILINE),
            "Plasma Login Manager must present the password surface directly; "
            "its idle clock page is a second login layout and can overlap branding")
else:
    # There is deliberately no SDDM branch any more. SDDM is not installed on this
    # base (plasmalogin replaced it), the dead theme tree it kept alive is gone,
    # and a display manager this gate has never verified must fail the build, not
    # pass it on a config file nobody reads.
    require(False, f"unknown display manager: {dm_target} — its branding is unverified")

# The pickers are user-facing screens too. MoOS's own Look and Feel wins, so the desktop looked
# right — but Appearance and Wallpaper still OFFERED "Fedora" on a machine called MoOS.
for gone in ("/usr/share/plasma/look-and-feel/org.fedoraproject.fedora.desktop",
             "/usr/share/plasma/look-and-feel/org.fedoraproject.fedoradark.desktop",
             "/usr/share/plasma/look-and-feel/org.fedoraproject.fedoralight.desktop",
             "/usr/share/wallpapers/Fedora",
             "/usr/share/backgrounds/fedora-workstation"):
    require(not Path(gone).exists(),
            f"another distribution's theme/wallpaper is still offered to the user: {gone}")

selectors = {
    "lock screen": text("/etc/xdg/kscreenlockerrc"),
    "look and feel": text("/usr/share/plasma/look-and-feel/org.moos.ui2/contents/defaults"),
}
for surface, value in selectors.items():
    require(re.search(r"fedora|bgrt|spinner", value, re.IGNORECASE) is None,
            f"foreign branding is active in {surface}")
require("MoOSUI2Graphite" in selectors["lock screen"],
        "lock screen does not use MoOS UI2 Graphite")
require(Path("/usr/share/wallpapers/MoOSUI2Graphite/contents/images_dark/3840x2160.jpg").is_file(),
        "MoOS UI2 Graphite wallpaper master is missing")
require(Path("/usr/share/wallpapers/MoOSUI2Tide/contents/images/3840x2160.jpg").is_file(),
        "MoOS UI2 Tidal wallpaper master is missing")
require(Path("/usr/share/plasma/look-and-feel/org.moos.ui2.light/contents/defaults").is_file(),
        "MoOS UI2 light Global Theme is missing")
require(Path("/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui/main.qml").is_file(),
        "the MoOS scene wallpaper plugin is missing")
require(Path("/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui/DashboardBento.qml").is_file(),
        "the MoOS dashboard bento is missing from the scene wallpaper")
# The shell defaults are what make NEW desktop containments (first boot, the
# live ISO) come up on the scene plugin without waiting for a login script.
shell_defaults = Path("/usr/share/plasma/shells/org.kde.plasma.desktop/contents/defaults")
require(shell_defaults.is_file()
        and "Wallpaper=org.moos.ui2.wallpaper" in config(text(str(shell_defaults))),
        "the desktop shell defaults do not select org.moos.ui2.wallpaper — "
        "a fresh desktop would boot without the MoOS scene (no dashboard)")

# There is ONE MoOS look now (dark + light). The older Nova and UI generations used to ship
# alongside it as "explicit rollback themes" — which is what put six MoOS themes in System
# Settings and five Nova wallpapers in the picker. They are gone. This gate now enforces their
# ABSENCE, so a stray reintroduction fails the build instead of quietly offering the user a
# second, older MoOS to choose from. (Version rollback — going back to the previous OS — is a
# separate thing entirely, and it still works: it is `bootc rollback`, in MoOS Recovery.)
for removed in (
    "/usr/share/plasma/look-and-feel/org.moos.nova",
    "/usr/share/plasma/look-and-feel/org.moos.nova.light",
    "/usr/share/plasma/look-and-feel/org.moos.ui",
    "/usr/share/plasma/look-and-feel/org.moos.ui.light",
    "/usr/share/plasma/plasmoids/org.moos.nova.deskclock",
    # The dashboard-as-a-desktop-WIDGET generation: as an applet it always drew
    # on top of the Folder View icons (three shipped fixes only moved the
    # collision). It lives inside org.moos.ui2.wallpaper now — a reintroduced
    # applet package would put the collision back.
    "/usr/share/plasma/plasmoids/org.moos.ui2.dashboard",
    # Orphan of the deleted UI1 generation — it polluted the wallpaper picker.
    "/usr/share/wallpapers/MoOSUIAtmosphere",
):
    require(not Path(removed).exists(),
            f"a superseded MoOS theme generation is still installed: {removed}")
# The SDDM login stack is DEAD WEIGHT on this base: Kinoite 44 replaced SDDM with
# plasma-login-manager, so ~60 theme files and a config shipped for a greeter that
# is never installed. This gate used to *require* that theme's background — a green
# check on a file nobody reads. Now it requires the whole stack stays gone: the
# real login screen is plasmalogin's, verified above against the lock screen.
for dead_sddm in ("/usr/share/sddm", "/etc/sddm.conf.d"):
    require(not Path(dead_sddm).exists(),
            f"dead SDDM login stack is shipping again: {dead_sddm} — "
            "plasmalogin is the display manager; nothing reads SDDM files")

control = text("/usr/bin/moai-control")
gateway = text("/usr/bin/moai-gateway")
require('"cloud_key":' not in control, "Mo AI persists cloud credentials in JSON")
require('c.get("cloud_key")' not in gateway, "Mo AI reads plaintext credentials")
require("secret-tool" in control and "secret-tool" in gateway,
        "Mo AI does not use Secret Service")
require('had_legacy_key = "cloud_key" in data' in control,
        "Mo AI does not fully migrate legacy credential fields")

# ONE visible storefront: the standalone Mo Store app (org.moos.store — the
# curated catalog UI). Discover keeps its engine for update notifications and
# firmware, but its menu entry is hidden and MoOS-branded, so no menu ever
# shows two storefronts and no surface ever shows a foreign store name.
store_entry_path = Path("/usr/share/applications/org.moos.store.desktop")
require(store_entry_path.is_file(),
        "org.moos.store.desktop is missing — Mo Store is not in the menu")
if store_entry_path.is_file():
    store_entry = config(text(str(store_entry_path)))
    require("Name=Mo Store" in store_entry,
            "the store app is not named 'Mo Store'")
    require("Exec=moos-store" in store_entry,
            "org.moos.store.desktop does not launch moos-store")
    require("Icon=moos-store" in store_entry,
            "the store app does not use the moos-store icon")
require(Path("/usr/share/icons/hicolor/256x256/apps/moos-store.png").is_file(),
        "the moos-store icon is missing — the store would fall back to a generic icon")
disc = Path("/usr/share/applications/org.kde.discover.desktop")
if disc.is_file():
    disc_entry = config(text(str(disc)))
    require("NoDisplay=true" in disc_entry,
            "Discover's menu entry is visible — the menu would show two storefronts")
    require("Name=Mo Store" in disc_entry,
            "the hidden Discover entry is not MoOS-branded — a notifier popup could show a foreign store name")
    require("Icon=mo-store" in disc_entry,
            "the hidden Discover entry does not use the mo-store icon")
    require(Path("/usr/share/icons/hicolor/256x256/apps/mo-store.png").is_file(),
            "the mo-store icon is missing — notifier surfaces would fall back to a generic icon")

# Mo Store is one trusted chain: the launcher builds a local AppStream index,
# signals completion through a sidecar, and gives the read-only QML both that
# index and the backend's atomic job document.  The old catalogue fired a public
# moos://store/install URL; any web page can invoke that scheme, so it can open
# the Store but it must never be an authority for a software change.
store_qml_path = Path("/usr/share/moos/apps/store/main.qml")
store_launcher_path = Path("/usr/bin/moos-store")
store_index_path = Path("/usr/bin/moos-store-index")
store_backend_path = Path("/usr/bin/moos-storectl")
for _store_path, _store_message in (
    (store_qml_path, "the Mo Store QML is missing"),
    (store_launcher_path, "the Mo Store launcher is missing"),
    (store_index_path, "the Mo Store AppStream indexer is missing"),
    (store_backend_path, "the trusted Mo Store transaction backend is missing"),
):
    require(_store_path.is_file(), _store_message)
for _store_executable in (store_launcher_path, store_index_path, store_backend_path):
    if _store_executable.is_file():
        require(os.access(_store_executable, os.X_OK),
                f"{_store_executable} is not executable")

if store_launcher_path.is_file():
    _store_launcher = config(text(str(store_launcher_path)))
    require('CACHEDIR="${XDG_CACHE_HOME:-$HOME/.cache}/moos-store"' in _store_launcher
            and 'INDEX="${CACHEDIR}/index.json"' in _store_launcher
            and 'JOB="${CACHEDIR}/job.json"' in _store_launcher
            and 'READY="${CACHEDIR}/index.ready"' in _store_launcher,
            "Mo Store does not keep its index, job and ready state in one user cache namespace")
    require("/usr/bin/moos-store-index" in _store_launcher
            and "--catalog /usr/share/moos/store/catalog.json" in _store_launcher
            and '--output "$INDEX"' in _store_launcher,
            "Mo Store does not rebuild the unified AppStream/curated index it displays")
    require(': >"$READY"' in _store_launcher,
            "Mo Store does not clear a stale ready sidecar before rebuilding its index")
    require(re.search(
                r"if\s+/usr/bin/moos-store-index\b.*?;\s*then.*?>\"\$READY\"",
                _store_launcher, re.DOTALL) is not None,
            "Mo Store marks the index ready without requiring a successful index build")
    require('--index="$INDEX"' in _store_launcher
            and '--job="$JOB"' in _store_launcher
            and '--ready="$READY"' in _store_launcher,
            "Mo Store does not pass the index, job and ready sidecar paths to its QML")
    require("/usr/bin/moos-qml-shell" in _store_launcher
            and "--app-id org.moos.store" in _store_launcher,
            "Mo Store does not run under the app id that enables its private StoreBridge")

if store_index_path.is_file():
    _store_index = source(text(str(store_index_path)), "#")
    for _token, _message in (
        ("def appstream_sources(", "the Store indexer no longer reads local AppStream metadata"),
        ("def official_flatpak_origins(", "the Store indexer no longer limits automatic discovery to configured origins"),
        ("official_only=args.appstream_root is None", "automatic Store discovery accepts orphan or custom AppStream origins"),
        ("def build_index(", "the Store indexer has no unified-index builder"),
        ("def atomic_write_json(", "the Store indexer can expose a partially-written index"),
        ("os.replace(temporary, path)", "the Store indexer does not atomically publish its completed index"),
    ):
        require(_token in _store_index, _message)

if store_backend_path.is_file():
    _store_backend = source(text(str(store_backend_path)), "#")
    require('"job.json"' in _store_backend
            and '"action": self.action' in _store_backend
            and '"started_at": now' in _store_backend,
            "the Store backend no longer publishes the action/time schema its QML correlates")
    require("def _atomic_bytes(" in _store_backend
            and "os.replace(temporary, path)" in _store_backend,
            "the Store backend can expose a partially-written job.json")

if store_qml_path.is_file():
    _store_qml = source(text(str(store_qml_path)))
    require("MoosStore.installApps(ids)" in _store_qml
            and "MoosStore.removeApp(app.id)" in _store_qml
            and "MoosStore.updateApps()" in _store_qml,
            "Mo Store software actions do not cross the private StoreBridge")
    require("moos://store/install/" not in _store_qml,
            "Mo Store still authorizes installation through the public moos: URL scheme")
    require('argValue("--index=")' in _store_qml
            and 'argValue("--job=")' in _store_qml
            and 'argValue("--ready=")' in _store_qml
            and "indexBuildReady()" in _store_qml
            and "if (win.indexBuildReady())" in _store_qml,
            "Mo Store does not wait on the ready sidecar before accepting a rebuilt index")
    for _token in (
        "expectedAction",
        "expectedIds",
        "previousJobId",
        "requestEpoch",
        "matchesExpectedJob(document)",
        "document.started_at",
        "document.action !== win.expectedAction",
        "items.length !== win.expectedIds.length",
        "items[j].id === win.expectedIds[i]",
        "started + 1000 < win.requestEpoch",
    ):
        require(_token in _store_qml,
                f"Mo Store does not correlate job.json to its request ({_token} missing)")
    require('win.expectJob("install", ids)' in _store_qml
            and 'win.expectJob("remove", [app.id])' in _store_qml
            and 'win.expectJob("update", [])' in _store_qml,
            "Mo Store can display stale job.json state for an unrelated software action")
    require("MoosStore.openSystemUpdater()" in _store_qml
            and "moos://app/updater" not in _store_qml,
            "the MoOS image update card does not use the trusted fixed StoreBridge updater")
    require(Path("/usr/bin/moos-update").is_file()
            and os.access("/usr/bin/moos-update", os.X_OK),
            "the trusted MoOS image updater opened by Mo Store is missing or not executable")

# The bridge source is the exact /ctx file compiled into /usr/bin/moos-qml-shell
# earlier in build.sh.  Gate its allowlist and fixed argv boundary here: checking
# that the binary merely exists would still pass if every Store button were dead
# or if the bridge had accidentally become available to arbitrary QML.
store_bridge_source = Path("/ctx/moos-qml-shell.cpp")
require(store_bridge_source.is_file(),
        "the StoreBridge source used to build moos-qml-shell is unavailable to the final gate")
if store_bridge_source.is_file():
    _store_bridge = source(text(str(store_bridge_source)))
    for _token in (
        "class StoreBridge",
        "Q_INVOKABLE bool installApps",
        "Q_INVOKABLE bool removeApp",
        "Q_INVOKABLE bool updateApps",
        "Q_INVOKABLE bool openSystemUpdater",
        'QStringLiteral("/usr/bin/moos-storectl")',
        'QStringLiteral("/usr/bin/moos-update")',
        'appId == QLatin1String("org.moos.store")',
        'appId == QLatin1String("org.moos.welcome")',
        'QStringLiteral("MoosStore")',
        "StoreBridge storeBridge(storeBridgeEnabled)",
        "if (storeBridgeEnabled)",
    ):
        require(_token in _store_bridge,
                f"moos-qml-shell lost required StoreBridge contract token {_token!r}")
    require("QProcess::startDetached" in _store_bridge
            and 'QStringList args{QStringLiteral("install")}' in _store_bridge,
            "StoreBridge does not use the fixed moos-storectl argv process boundary")
    require('QStringLiteral("/bin/sh")' not in _store_bridge
            and 'QStringLiteral("bash")' not in _store_bridge,
            "StoreBridge gained a shell execution path")

_store_router = config(router)
require("store/install" not in _store_router,
        "moos-open still exposes public store/install — a web page could trigger installation")

# ── The MoOS installer (the live-USB disk installer) ──────────────────────────
# "Install MoOS" must launch the beautiful MoOS QML installer (moos-installer),
# not raw Anaconda, and every piece it needs must be present. The old registry-pull
# install failed on real hardware; these gates lock in the offline, one-click flow.
for _p, _msg in [
    ("/usr/bin/moos-installer", "the MoOS installer launcher is missing"),
    ("/usr/bin/moos-install-to-disk", "the privileged install helper is missing"),
    ("/usr/bin/moos-list-disks", "the disk-probe helper is missing"),
    ("/usr/share/moos/apps/installer/main.qml", "the installer QML front-end is missing"),
    ("/usr/share/polkit-1/rules.d/49-moos-installer.rules", "the installer polkit rule is missing — the install step could not elevate"),
    ("/usr/lib/moos/install-imageref", "the edition-aware install image ref is missing"),
]:
    require(Path(_p).is_file(), _msg)

liveinst = Path("/usr/share/applications/liveinst.desktop")
if liveinst.is_file():
    _li = config(text(str(liveinst)))
    require("Exec=moos-installer" in _li,
            "'Install MoOS' does not launch moos-installer — it would open the confusing Anaconda screen")
    require("Name=Install MoOS" in _li, "the installer launcher is not named 'Install MoOS'")

# Anti-footgun contract on the destructive helper: it MUST refuse to run outside a
# live boot and MUST refuse the live boot medium itself, or a stray invocation
# could wipe an installed machine's disk. Enforced at build time.
helper = Path("/usr/bin/moos-install-to-disk")
if helper.is_file():
    _h = text(str(helper))
    require("rd.live.image" in _h and "not-live" in _h,
            "moos-install-to-disk lacks the live-only guard — it could wipe an installed system's disk")
    require("live-node" in _h and "live_parent" in _h,
            "moos-install-to-disk lacks the boot-medium guard — it could wipe the USB it booted from")
    # The target disk must come from the trusted recipe, NOT argv/URL, or a drive-by
    # moos:// URL could aim a --wipe at an attacker-chosen internal disk.
    require("no-recipe" in _h and "DISKS_JSON" in _h,
            "moos-install-to-disk takes its target from argv/URL — a drive-by moos:// URL could wipe an arbitrary disk")
    # The install must re-arm SIGNED day-2 verification (else updates go unverified).
    require("ostree-image-signed" in _h,
            "moos-install-to-disk does not re-arm signed day-2 verification after install")
    require("/usr/lib/systemd/systemd-update-done --root=" in _h
            and ".updated" in _h,
            "moos-install-to-disk does not mark the deployed caches current — "
            "the first password greeter would wait for a cold ldconfig rebuild")
    require(Path("/usr/lib/systemd/systemd-update-done").is_file(),
            "systemd-update-done is absent, so the installer cannot create the "
            "documented ConditionNeedsUpdate stamp")
_open = Path("/usr/bin/moos-open")
if _open.is_file():
    _o = text(str(_open))
    require("installer/begin)" in _o and "installer/disk/" not in _o,
            "moos-open still routes a disk node from the URL — the target must come from the recipe, not the URL")

# The install must be OFFLINE from the embedded image and re-arm signed day-2
# updates. The kickstart is assembled by build.sh; assert the offline contract.
ks = Path("/usr/share/anaconda/interactive-defaults.ks")
if ks.is_file():
    _ks = text(str(ks))
    require("--transport=containers-storage" in _ks,
            "the kickstart still pulls from the registry — install fails with no network")
    require("ostree-image-signed:" in _ks,
            "the kickstart does not re-arm signed day-2 updates in %post")
    require("autopart" in _ks,
            "the kickstart has no autopart — users are dropped into manual partitioning")

# ── First-boot account setup (bootc installs no user; we create it on first boot) ─
require(Path("/usr/libexec/moos-firstboot").is_file(),
        "moos-firstboot is missing — a fresh install would reach the greeter with NO user")
require(Path("/usr/lib/systemd/system/moos-firstboot.service").is_file(),
        "moos-firstboot.service is missing")
require(
    Path("/etc/systemd/system/multi-user.target.wants/moos-firstboot.service").exists()
    or Path("/usr/lib/systemd/system/multi-user.target.wants/moos-firstboot.service").exists(),
    "moos-firstboot.service is not enabled — the first-boot user setup would never run",
)
fb = Path("/usr/libexec/moos-firstboot")
if fb.is_file():
    _fb = text(str(fb))
    require("useradd" in _fb and "chpasswd" in _fb,
            "moos-firstboot does not create the user / set the password")
    require("autologin" not in _fb.lower() and "plasmalogin.conf.d" not in _fb,
            "moos-firstboot must always leave the password greeter enabled")
    require("account recipe has no password hash" in _fb,
            "moos-firstboot must reject an account recipe without a password hash")
    require("NOPASSWD" not in _fb and "49-moos-passwordless.rules" not in _fb,
            "moos-firstboot must never create passwordless sudo/polkit access")
    require("sddm" not in _fb.lower(),
            "moos-firstboot must not recreate a retired SDDM login stack")
fb_unit = text("/usr/lib/systemd/system/moos-firstboot.service")
require("sddm" not in fb_unit.lower(),
        "moos-firstboot.service still orders against retired SDDM")
# plasma-setup (Fedora KDE's own OOBE) must stay masked, or it double-runs with ours.
require(Path("/etc/plasma-setup-done").exists()
        or Path("/etc/systemd/system/plasma-setup.service").is_symlink(),
        "plasma-setup is not neutralised — the first-run OOBE could be the foreign KDE one")

# The installer must actually feed the account to first boot: the QML hands answers
# to the privileged helper via the moos-qml-shell bridge (never a moos:// URL).
inst_qml = Path("/usr/share/moos/apps/installer/main.qml")
if inst_qml.is_file():
    _iq = text(str(inst_qml))
    require("MoosInstaller.writeRecipe" in _iq,
            "the installer does not hand the account recipe to the helper (no secure bridge call)")
    require("acctUser" in _iq and "acctPass" in _iq,
            "the installer has no secure username / password account screen")
    require("acctPass.length >= 8" in _iq,
            "the installer must require a real password before installation")
    require("acctAutologin" not in _iq and "autologin:" not in _iq.lower(),
            "the installer must not expose an automatic-sign-in choice")
    require("moalfarras.space" in _iq,
            "the installer's finish screen does not carry the moalfarras.space signature")
# The QR asset the finish screen shows must ship.
require(Path("/usr/share/moos/apps/installer/qr-moalfarras.png").is_file(),
        "the installer QR code asset is missing")

# Welcome owns the live landing experience, then hands off to the one installer
# window. After installation it is autostarted once for the password-authenticated
# user, and every app choice uses Mo Store's real install/status contract.
welcome = Path("/usr/share/moos/apps/welcome/main.qml")
welcome_launcher = Path("/usr/bin/moos-welcome")
firstrun = Path("/usr/bin/moos-firstrun")
firstrun_desktop = Path("/etc/xdg/autostart/org.moos.firstrun.desktop")
require(welcome.is_file() and welcome_launcher.is_file()
        and firstrun.is_file() and firstrun_desktop.is_file(),
        "the integrated Welcome / installer first-run chain is incomplete")
if welcome.is_file():
    _wq = source(text(str(welcome)))
    require("handoffToInstaller" in _wq and "moos://installer/open" in _wq
            and "onTriggered: Qt.quit()" in _wq,
            "the live Welcome must close after handing off to the installer")
    require("Object.keys(win.picks)" in _wq
            and "MoosStore.installApps(ids)" in _wq
            and 'readonly property string jobPath: win.cacheDir + "/job.json"' in _wq,
            "Welcome app choices are not wired to the private Mo Store transaction")
    require("moos://store/install/" not in _wq,
            "Welcome still authorizes installation through the public moos: URL scheme")
    for _token in (
        "previousJobId",
        "requestEpoch",
        "matchesInstallJob(document)",
        'document.action !== "install"',
        "document.started_at",
        "doc.job_id === win.previousJobId",
        "items.length !== win.queue.length",
        "items[j].id === win.queue[i]",
        "started + 1000 < win.requestEpoch",
    ):
        require(_token in _wq,
                f"Welcome does not correlate job.json to its install request ({_token} missing)")
    require('doc.state === "success"' in _wq
            and 'doc.state === "partial"' in _wq
            and 'doc.state === "failed"' in _wq
            and "installHadFailures" in _wq,
            "Welcome does not surface real success/partial/failure state from job.json")
if welcome_launcher.is_file():
    _wl = text(str(welcome_launcher))
    require('rd.live.image' in _wl and '--live="$LIVE"' in _wl
            and '--cache="$CACHEDIR"' in _wl,
            "the Welcome launcher does not distinguish live and installed sessions")
    require("/usr/bin/moos-qml-shell" in _wl
            and "--app-id org.moos.welcome" in _wl,
            "Welcome does not run under the app id that enables its private StoreBridge")
if firstrun.is_file() and firstrun_desktop.is_file():
    _fr = text(str(firstrun))
    _frd = text(str(firstrun_desktop))
    require("moos-firstrun-done" in _fr and "moos-welcome && exit 0" in _fr
            and "Exec=/usr/bin/moos-firstrun" in _frd,
            "Welcome is not guaranteed exactly once on the installed user's first login")

# The name is MoOS, not "MoOS 44": no release file may carry the bare Fedora version.
for _rel in ("/etc/system-release", "/etc/redhat-release", "/etc/fedora-release"):
    p = Path(_rel)
    if p.is_file():
        require(p.read_text(encoding="utf-8").strip() == "MoOS",
                f"{_rel} is not exactly 'MoOS' — it still shows a version/foreign name")

if errors:
    raise SystemExit("MoOS image-experience gate failed:\n - " + "\n - ".join(errors))
print("MoOS image-experience gate passed")
