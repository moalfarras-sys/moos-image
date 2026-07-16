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

    # The plugin the drop-in names must actually be installed. plasma-login-wallpaper
    # loads it as a KPackage by id; an id that resolves to nothing draws a BLACK login
    # screen with every other check still green. Read the value, then require the
    # package's main.qml on disk — a relationship, not a constant, so swapping the
    # scene later keeps this gate honest.
    plugin_id = re.search(r"^WallpaperPluginId=(\S+)", login_conf, re.MULTILINE)
    require(plugin_id is not None, "WallpaperPluginId has no value in the login drop-in")
    if plugin_id is not None and not plugin_id.group(1).startswith("org.kde."):
        require(Path(f"/usr/share/plasma/wallpapers/{plugin_id.group(1)}/contents/ui/main.qml").is_file(),
                f"the login screen names wallpaper plugin {plugin_id.group(1)} but no such "
                "package is installed — the first screen after boot would be black")

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
    require("plasmalogin.conf.d" in _fb and "Autologin" in _fb,
            "moos-firstboot does not configure autologin — the passwordless choice would not work")
    # Never ship an empty password (pam_unix rejects it and it breaks sudo/polkit).
    require("passwd -l" in _fb,
            "moos-firstboot must lock (not empty) the password in the passwordless path")
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
    require("acctUser" in _iq and "acctPassword" in _iq,
            "the installer has no account screen (username / password choice)")
    require("moalfarras.space" in _iq,
            "the installer's finish screen does not carry the moalfarras.space signature")
# The QR asset the finish screen shows must ship.
require(Path("/usr/share/moos/apps/installer/qr-moalfarras.png").is_file(),
        "the installer QR code asset is missing")

# The name is MoOS, not "MoOS 44": no release file may carry the bare Fedora version.
for _rel in ("/etc/system-release", "/etc/redhat-release", "/etc/fedora-release"):
    p = Path(_rel)
    if p.is_file():
        require(p.read_text(encoding="utf-8").strip() == "MoOS",
                f"{_rel} is not exactly 'MoOS' — it still shows a version/foreign name")

if errors:
    raise SystemExit("MoOS image-experience gate failed:\n - " + "\n - ".join(errors))
print("MoOS image-experience gate passed")
