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
require("Theme=moos-nova" in text("/usr/share/plymouth/plymouthd.defaults"),
        "Plymouth's default theme is not moos-nova")

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

# Plasma's day/night switch applies only a subset of a Global Theme. The path
# unit is what carries wallpaper/Konsole/GTK after an automatic transition; a
# perfect service file that is not enabled is another green-but-invisible fix.
theme_path = text("/usr/lib/systemd/user/moos-theme-sync.path")
theme_service = text("/usr/lib/systemd/user/moos-theme-sync.service")
require("PathChanged=%h/.config/kdeglobals" in theme_path,
        "the automatic-theme supplement watcher does not observe kdeglobals")
require("WantedBy=plasma-workspace.target" in theme_path,
        "the automatic-theme watcher is not scoped to the Plasma workspace")
require("ExecStart=/usr/bin/moos-theme sync-auto" in theme_service,
        "the automatic-theme watcher does not invoke the bounded supplement sync")
theme_want = Path("/etc/systemd/user/plasma-workspace.target.wants/moos-theme-sync.path")
require(theme_want.is_symlink()
        and theme_want.resolve() == Path("/usr/lib/systemd/user/moos-theme-sync.path"),
        "moos-theme-sync.path is shipped but not globally enabled for users")

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
# and an SDDM config, and this gate asserted "Current=moos-nova" in that config — and passed.
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
require(Path("/usr/share/plasma/plasmoids/org.moos.ui2.dashboard/contents/ui/main.qml").is_file(),
        "MoOS UI2 dashboard is missing")

# UI1 is the explicit rollback, not dead development debris. A UI2 image that
# deletes it breaks the recovery path promised by `moos-theme ui1-*`.
for fallback in (
    "/usr/share/plasma/look-and-feel/org.moos.ui/contents/defaults",
    "/usr/share/plasma/look-and-feel/org.moos.ui.light/contents/defaults",
    "/usr/share/plasma/plasmoids/org.moos.nova.deskclock/contents/ui/main.qml",
):
    require(Path(fallback).is_file(), f"MoOS UI1 rollback asset is missing: {fallback}")
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

if errors:
    raise SystemExit("MoOS image-experience gate failed:\n - " + "\n - ".join(errors))
print("MoOS image-experience gate passed")
