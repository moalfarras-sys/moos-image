#!/usr/bin/bash
# =============================================================================
# curate_app_menu.sh — what the application menu and System Settings offer.
#
# ONE script, written for every edition. build.sh (moos, moos-nvidia, moos-cloud) calls it
# after its last package transaction:
#
#     bash /ctx/curate_app_menu.sh / || exit 1
#
# Until 2026-09-24 every step below lived inline in build.sh, so the ARM menu kept
# Plasma's own "System Settings" beside "MoOS Settings", plus "Info Center" and
# "Dolphin" (wave audit, map-menu gap 1). Each step is a no-op when its file is
# absent — ARM ships no nvidia-settings, no KDE Connect and no firewall-config — and
# ONE gate at the end reads the finished tree, never the lists above it.
#
# ARM does not run it YET. build-arm.sh belongs to the ARM owner; the change it needs is
# handed off (2026-09-24): delete its own `_disc` sed rewrite of org.kde.discover.desktop
# (which renames Discover's "Updates" action "Mo Store" too — this script's gate fails that)
# and call this script, with the line above, after `cp -a /moos-overlay/. /` and its last
# package install. Nothing below may depend on ARM running it: the Firewall page is staged
# in /usr/share/moos and only step (4) installs it, so an ARM image gets no page rather than
# a dead one.
#
# usage: curate_app_menu.sh [ROOT]
#   ROOT defaults to /. tests/test_foreign_app_menus.py runs this exact script
#   on a fixture tree and proves every gate below fails when its rule breaks.
# =============================================================================
set -euo pipefail

ROOT="${1:-/}"
ROOT="${ROOT%/}"                       # "/" -> "" so paths stay absolute
APPS="${ROOT}/usr/share/applications"
EXTERNAL_MODULES="${ROOT}/usr/share/plasma/systemsettings/externalmodules"
STAGED_MODULES="${ROOT}/usr/share/moos/settings-external-modules"
[ -d "$APPS" ] || { echo "curate_app_menu: ${APPS} does not exist"; exit 1; }

# -----------------------------------------------------------------------------
# (1) The app menu holds the system's apps and MoOS's apps. Nothing else.
# -----------------------------------------------------------------------------
# The owner's rule, in his words: what ships is the essential system + what we built, and the
# user chooses the rest. What he actually got was a menu with the base distribution's debug
# tools in it and the same app listed twice.
#
# Two of these are literal DUPLICATES — the thing he complained about:
#   * kdesystemsettings.desktop is `Exec=systemsettings`, the same command, with the same icon,
#     as systemsettings.desktop. The base ships it for people running KDE apps under another
#     desktop, and it carries no OnlyShowIn, so on a KDE-only OS BOTH entries appear. Two
#     "System Settings" side by side, opening the identical window.
#   * KWrite is Kate with features removed; shipping both is offering the user a choice between
#     an editor and a worse version of the same editor.
#
# The next group are the base's diagnostics — a crash-dump browser, a journal viewer, a
# debug-flag editor, a menu editor. They are the tooling of somebody building a distribution,
# not of somebody using one. Krfb goes too: it is a second, worse screen-sharing app standing
# next to Mo PC Remote, which is the one MoOS actually built.
#
# Added 2026-09-24 (the "nothing duplicated" wave), measured visible on the booted station:
#   * htop, nvtop, btop++ — three terminal monitors beside System Monitor. btop is installed on
#     purpose (build.sh c7) and all three still run from Konsole; they are not menu apps.
#   * KFind — a second file search beside the launcher's own search and Files' search bar.
#   * Help Center — the upstream handbooks, a menu entry a MoOS user never reaches for.
#   * Firewall (firewall-config) — a GTK settings window outside Settings. It stays one click
#     away INSIDE MoOS Settings → Security & Privacy (step 4), which is where a person looks.
#
# NoDisplay, never `rm`: the packages stay installed and every one of these still runs from a
# terminal or a .desktop launch. This decides what the MENU offers, and nothing else.
MENU_HIDDEN=(
    kdesystemsettings.desktop
    org.kde.kwrite.desktop
    org.kde.drkonqi.coredump.gui.desktop
    org.kde.kdebugsettings.desktop
    org.kde.kjournaldbrowser.desktop
    org.kde.kmenuedit.desktop
    org.kde.krfb.desktop
    org.kde.krfb.virtualmonitor.desktop
    org.kde.kdeconnect.sms.desktop
    org.kde.kdeconnect.nonplasma.desktop
    htop.desktop
    nvtop.desktop
    btop.desktop
    org.kde.kfind.desktop
    org.kde.khelpcenter.desktop
    firewall-config.desktop
)

hide_from_menu() {
    local f="${APPS}/$1"
    [ -f "$f" ] || return 0                      # not installed in this edition; fine
    # Idempotent — but only the [Desktop Entry] group decides visibility. The old
    # `grep -q '^NoDisplay=true'` accepted the line from ANY group and would have left the
    # entry visible; the gate below would then fail the build.
    awk '/^\[/ { group = $0 } group == "[Desktop Entry]" && /^NoDisplay=true/ { found = 1 }
         END { exit !found }' "$f" && return 0
    sed -i '/^NoDisplay=/d' "$f"
    sed -i '0,/^\[Desktop Entry\]/s//[Desktop Entry]\nNoDisplay=true/' "$f"
}

for entry in "${MENU_HIDDEN[@]}"; do
    hide_from_menu "$entry"
done

# -----------------------------------------------------------------------------
# (2) The menu says MoOS, or it says nothing
# -----------------------------------------------------------------------------
# (1) hid the duplicates and the distribution's debug tools. It did not touch the entries that
# are KEPT, and on 2026-09-20 the MoOS application menu was still offering, in the owner's own
# Arabic session:
#
#   Dolphin / دولفين              the file manager, named after a KDE project
#   KDE Connect / جسر كِيدِي         another desktop's name, twice, in the label
#   KDE Partition Manager / مدير أقسام كِيدِي
#   Info Center                   a second hardware-information app
#   System Settings / إعدادات النّظام  A SECOND SETTINGS APP, beside MoOS Settings
#
# Hiding all of them is wrong: a person needs a file manager and a disk tool. So each entry is
# given MoOS's name and MoOS's icon, and the ones only ever REACHED THROUGH MoOS Settings leave
# the menu. What opens is the same program; what the person reads is MoOS.
#
# Only the [Desktop Entry] group is rewritten. Dolphin ships Desktop Actions ("Open a New
# Window") and Discover ships "Updates"; their own Name= lines are what a blind sed overwrote,
# which is how a rebrand turned Discover's Updates action into a second item called "Mo Store".
moos_rebrand_entry() {
    python3 - "$1" "$2" "$3" "$4" "$5" "${6:-keep-metadata}" <<'MOOSREBRAND'
import sys
path, en, ar, icon, hide, metadata = sys.argv[1:7]
try:
    lines = open(path, encoding="utf-8").read().splitlines()
except FileNotFoundError:
    raise SystemExit(0)
out, group, wrote_name, wrote_icon, wrote_hide = [], 0, False, False, False
for line in lines:
    if line.startswith("["):
        if group == 1:
            if not wrote_name:
                out += ["Name=" + en, "Name[ar]=" + ar]; wrote_name = True
            if not wrote_icon and icon:
                out.append("Icon=" + icon); wrote_icon = True
            if not wrote_hide and hide == "hide":
                out.append("NoDisplay=true"); wrote_hide = True
        group += 1
        out.append(line)
        continue
    if group != 1:
        out.append(line)
        continue
    # A launcher model may show GenericName as a subtitle or use it for search.
    # Keeping its unlocalised upstream value made the file look rebranded while
    # "System Settings" was still user-visible (and made the image gate bite).
    # MoOS entries need one clear product label, so remove the whole secondary
    # name family instead of leaving an English-only alias behind.
    if line.startswith("Name[") or line.startswith("GenericName=") or line.startswith("GenericName["):
        continue
    # A hidden vendor control panel still has metadata that launchers and file
    # inspectors can index. Its translated comments name the underlying X11
    # utility even after Name= is replaced, so the NVIDIA-only call below drops
    # that vendor vocabulary instead of leaking it through search/subtitles.
    if metadata == "strip-metadata" and (
            line.startswith("Comment=") or line.startswith("Comment[")
            or line.startswith("Keywords=") or line.startswith("Keywords[")):
        continue
    if line.startswith("Name="):
        if wrote_name:
            continue
        out += ["Name=" + en, "Name[ar]=" + ar]; wrote_name = True
        continue
    if line.startswith("Icon=") and icon:
        if wrote_icon:
            continue
        out.append("Icon=" + icon); wrote_icon = True
        continue
    if line.startswith("NoDisplay="):
        continue
    out.append(line)
if group == 1:
    if not wrote_name:
        out += ["Name=" + en, "Name[ar]=" + ar]
    if not wrote_icon and icon:
        out.append("Icon=" + icon)
    if not wrote_hide and hide == "hide":
        out.append("NoDisplay=true")
elif hide == "hide" and not wrote_hide:
    raise SystemExit("moos_rebrand_entry: could not place NoDisplay in " + path)
open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
MOOSREBRAND
}

#                  file                                English          Arabic           icon                     menu
moos_rebrand_entry "${APPS}/org.kde.dolphin.desktop"          "Files"          "الملفات"        "moos-folder-symbolic"   show
moos_rebrand_entry "${APPS}/org.kde.kdeconnect.app.desktop"   "Phone"          "الهاتف"         "moos-phone-symbolic"    show
moos_rebrand_entry "${APPS}/org.kde.partitionmanager.desktop" "Disks"          "الأقراص"        "moos-storage-symbolic"  show
# The ONE settings entry (wave decision D2). It used to be hidden here while a second
# launcher, org.moos.settings.desktop, stood in the menu — but the window that opens is
# systemsettings (its Wayland app_id is "systemsettings", from upstream's
# setDesktopFileName), so the task bar grouped it under THIS entry, with a different icon,
# and the dock showed two settings tasks. Now this entry is the front door: MoOS's name,
# MoOS's icon, Exec=moos-settings (step 3), the upstream Meta+I shortcut kept (the
# /usr/share/kglobalaccel/systemsettings.desktop symlink points at this very file).
moos_rebrand_entry "${APPS}/systemsettings.desktop"           "MoOS Settings"  "إعدادات MoOS"   "moos-control-center"    show
moos_rebrand_entry "${APPS}/org.kde.kinfocenter.desktop"      "System Report"  "تقرير النظام"   "moos-system-symbolic"   hide
# Found by asking the launcher's own model rather than reading files: a SIXTH
# entry, "NVIDIA X Server Settings", sitting under النظام beside the other two.
# It is the proprietary driver's X11 control panel — on a Wayland session most
# of its pages cannot do anything, and MoOS Settings already reports the GPU on
# its device page. It leaves the menu and keeps MoOS's words for the task bar.
# Only the NVIDIA editions install it, so the helper's own file check is what
# makes this a no-op everywhere else.
moos_rebrand_entry "${APPS}/nvidia-settings.desktop"          "Graphics Card"  "كرت الشاشة"     "moos-gpu-symbolic"      hide strip-metadata
# Discover keeps its engine (appstream deep links, .flatpakref files) but leaves every menu:
# Mo Store (org.moos.store.desktop) is the one storefront. The MoOS name and icon stay on the
# hidden entry so a Discover window that does open (a .flatpakref) groups under MoOS words.
# Header only: Discover's own "Updates" action keeps its name and its translations.
moos_rebrand_entry "${APPS}/org.kde.discover.desktop"         "Mo Store"       "متجر MoOS"      "mo-store"               hide

# -----------------------------------------------------------------------------
# (3) MoOS Settings opens MoOS, and its jump list points at MoOS's own pages
# -----------------------------------------------------------------------------
# Exec=moos-settings opens the MoOS overview inside the same System Settings window
# (moos-settings ends in `exec systemsettings <module>`, and systemsettings forwards a module
# id to its running instance by itself). The words and search keywords are the ones the old
# org.moos.settings.desktop front door answered to, so a search that found MoOS Settings
# yesterday finds it today. Of the upstream jump-list actions, "Global Theme" duplicated
# MoOS's own theme page — applying a look through the bare module skips what moos-theme pins
# (GTK, sounds, kdedefaults; AGENTS.md) — so it now opens MoOS Themes. The other four
# (Users, Screen Locking, Power Management, Display Configuration) are native pages MoOS
# does not duplicate and stay exactly as upstream wrote them. "Update" is added first: it is
# the MoOS page a person opens most.
python3 - "${APPS}/systemsettings.desktop" <<'MOOSSETTINGS'
import sys
path = sys.argv[1]
try:
    lines = open(path, encoding="utf-8").read().splitlines()
except FileNotFoundError:
    raise SystemExit(0)

HEADER = {
    "Exec": ["Exec=moos-settings"],
    "Comment": ["Comment=See your device at a glance and shape every part of MoOS",
                "Comment[ar]=شاهد حالة جهازك وتحكّم بكل جزء من MoOS"],
    "Keywords": ["Keywords=settings;control;system;network;display;privacy;recovery;MoOS;",
                 "Keywords[ar]=إعدادات;تحكم;نظام;شبكة;شاشة;خصوصية;استعادة;"],
}
THEMES = ["Name=MoOS Themes", "Name[ar]=ثيمات MoOS",
          "Exec=moos-settings --section=appearance"]
UPDATE = ["[Desktop Action moos-update]", "Name=Update", "Name[ar]=التحديث",
          "Icon=system-software-update", "Exec=moos-settings --section=update"]


def family(line: str) -> str:
    key = line.split("=", 1)[0].strip()
    return key.split("[", 1)[0]


out, group, written = [], "", set()
for line in lines:
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        group = stripped[1:-1]
        out.append(line)
        continue
    if "=" not in line or stripped.startswith("#"):
        out.append(line)
        continue
    key = family(line)
    if group == "Desktop Entry":
        if key in HEADER:
            if key not in written:
                out += HEADER[key]
                written.add(key)
            continue
        if key == "Actions":
            actions = [a for a in line.split("=", 1)[1].split(";") if a and a != "moos-update"]
            out.append("Actions=" + ";".join(["moos-update", *actions]) + ";")
            continue
    elif group == "Desktop Action kcm-lookandfeel":
        if key in ("Name", "Exec"):
            if "themes" not in written:
                out += THEMES
                written.add("themes")
            continue
    out.append(line)

text = "\n".join(out)
if "[Desktop Action moos-update]" not in text:
    text = text.rstrip("\n") + "\n\n" + "\n".join(UPDATE)
open(path, "w", encoding="utf-8").write(text + "\n")
MOOSSETTINGS

# -----------------------------------------------------------------------------
# (4) System Settings' external modules: offered where their program ships, and nowhere else
# -----------------------------------------------------------------------------
# /usr/share/plasma/systemsettings/externalmodules/*.desktop is where System Settings looks
# for pages that launch a separate application (see moos-firewall.desktop for the evidence).
# Upstream's loader reads each file through KService and does NOT honour TryExec, so a module
# whose program is absent in this edition would sit in the sidebar and do nothing. The overlay
# is shared by every edition; the program is not (firewall-config: x86 base only). So MoOS's
# pages are STAGED in /usr/share/moos/settings-external-modules/, which System Settings never
# reads, and installed here only where their program resolves. Any installed module whose
# program is missing (a package's own, or one a later edition dropped) is removed, and the
# gate below proves every survivor resolves and every page that can work is offered.
resolve_program() {
    local prog="$1" dir
    case "$prog" in
        /*) [ -x "${ROOT}${prog}" ] && return 0 || return 1 ;;
    esac
    for dir in usr/bin usr/sbin; do
        [ -x "${ROOT}/${dir}/${prog}" ] && return 0
    done
    return 1
}
module_program() {
    # One process, no pipe: `sed | head` under pipefail is the SIGPIPE trap AGENTS.md
    # records (a producer killed by head's early exit reads as a failure).
    local prog
    prog="$(awk '/^TryExec=/ { sub(/^TryExec=/, ""); print; exit }' "$1")"
    [ -n "$prog" ] || prog="$(awk '/^Exec=/ { sub(/^Exec=/, ""); print $1; exit }' "$1")"
    printf '%s' "$prog"
}
if [ -d "$STAGED_MODULES" ]; then
    for module in "$STAGED_MODULES"/*.desktop; do
        [ -f "$module" ] || continue
        prog="$(module_program "$module")"
        if [ -n "$prog" ] && resolve_program "$prog"; then
            install -D -m 0644 "$module" "${EXTERNAL_MODULES}/${module##*/}"
        else
            echo "curate_app_menu: ${module##*/} opens '${prog}', which this edition does not ship; not offered"
        fi
    done
fi
if [ -d "$EXTERNAL_MODULES" ]; then
    for module in "$EXTERNAL_MODULES"/*.desktop; do
        [ -f "$module" ] || continue
        prog="$(module_program "$module")"
        if [ -z "$prog" ] || ! resolve_program "$prog"; then
            echo "curate_app_menu: ${module##*/} opens '${prog}', which this edition does not ship; removed"
            rm -f "$module"
        fi
    done
fi

# -----------------------------------------------------------------------------
# (5) THE GATE — ask the finished files, never the lists above
# -----------------------------------------------------------------------------
# A typo'd filename above hides nothing and says nothing; a base update that renames an entry
# does the same. So the gate reads what a launcher will read, and fails the build — it does
# not warn — because a second settings app or another desktop's name in the menu is exactly
# the defect this script exists for.
python3 - "${ROOT:-/}" "${MENU_HIDDEN[*]}" <<'MOOSMENUGATE'
import os
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
hidden_list = sys.argv[2].split()
apps = root / "usr/share/applications"
fails: list[str] = []


def groups(path: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    current = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = out.setdefault(line[1:-1], {})
            continue
        if current is not None and "=" in line:
            key, value = line.split("=", 1)
            current.setdefault(key.strip(), value.strip())
    return out


def header(path: Path) -> dict[str, str]:
    return groups(path).get("Desktop Entry", {})


def visible(entry: dict[str, str]) -> bool:
    return (entry.get("NoDisplay", "").lower() != "true"
            and entry.get("Hidden", "").lower() != "true")


def program(entry: dict[str, str]) -> str:
    words = entry.get("Exec", "").split()
    while words and (words[0] == "env" or ("=" in words[0] and not words[0].startswith("/"))):
        words.pop(0)
    return os.path.basename(words[0]) if words else ""


def resolves(prog: str) -> bool:
    if not prog:
        return False
    if prog.startswith("/"):
        return os.access(root / prog.lstrip("/"), os.X_OK)
    return any(os.access(root / d / prog, os.X_OK) for d in ("usr/bin", "usr/sbin"))


# (1) Every entry the list hides is hidden in the file itself.
for name in hidden_list:
    path = apps / name
    if path.is_file() and visible(header(path)):
        fails.append(f"GATE FAIL: {name} is still shown in the menu — it duplicates an app "
                     "MoOS already has, or it is a tool no menu should offer")

# D2: exactly one visible settings entry, and it is systemsettings.desktop.
SETTINGS_PROGRAMS = {"systemsettings", "systemsettings5", "moos-settings", "kinfocenter",
                     "kcmshell6", "kcmshell5"}
settings_entries = sorted(
    path.name for path in apps.glob("*.desktop")
    if visible(header(path)) and program(header(path)) in SETTINGS_PROGRAMS)
if settings_entries != ["systemsettings.desktop"]:
    fails.append("GATE FAIL: the menu must hold exactly one settings entry, "
                 "systemsettings.desktop (MoOS Settings); it holds "
                 f"{settings_entries or 'none'}")

settings = apps / "systemsettings.desktop"
if settings.is_file():
    parsed = groups(settings)
    entry = parsed.get("Desktop Entry", {})
    for key, want in (("Name", "MoOS Settings"), ("Name[ar]", "إعدادات MoOS"),
                      ("Icon", "moos-control-center")):
        if entry.get(key) != want:
            fails.append(f"GATE FAIL: MoOS Settings has {key}={entry.get(key)!r}, not {want!r} "
                         "— the one settings entry must wear MoOS's name and icon")
    if any(k.startswith("GenericName") for k in entry):
        fails.append("GATE FAIL: MoOS Settings still carries a GenericName — launchers show it "
                     "as a subtitle, and upstream's reads 'System Settings'")
    if program(entry) != "moos-settings" or not resolves("moos-settings"):
        fails.append("GATE FAIL: MoOS Settings does not run an installed moos-settings "
                     f"(Exec={entry.get('Exec')!r}) — the one settings entry would open "
                     "upstream's start page, or nothing")
    if "Meta+I" not in entry.get("X-KDE-Shortcuts", ""):
        fails.append("GATE FAIL: MoOS Settings lost its Meta+I shortcut")
    for action in [a for a in entry.get("Actions", "").split(";") if a]:
        body = parsed.get(f"Desktop Action {action}")
        if body is None:
            fails.append(f"GATE FAIL: MoOS Settings lists the action {action!r} but has no such "
                         "group — a dead jump-list item")
            continue
        if program(body) not in ("systemsettings", "moos-settings") or not resolves(program(body)):
            fails.append(f"GATE FAIL: MoOS Settings action {action!r} runs "
                         f"{body.get('Exec')!r}, not an installed settings host")
        if not body.get("Name[ar]"):
            fails.append(f"GATE FAIL: MoOS Settings action {action!r} has no Arabic name")
else:
    fails.append("GATE FAIL: systemsettings.desktop is missing — the image has no settings entry")

# (2) Kept entries wear MoOS's words, in both languages; the ones MoOS Settings reaches leave.
# Every word a launcher can show or search, in every language — not only Name. The inline gate
# this replaced matched the whole [Desktop Entry] header, so a base update that put "KDE
# Connect" into a kept entry's Comment or Keywords failed the build; a Name-only check would
# ship it. Exec/Icon/X-DBUS-* legitimately carry "dolphin" and are not text a person reads.
# Arabic is compared without its diacritics: the menu the owner saw read "جسر كِيدِي".
FOREIGN_NAMES = ("Dolphin", "KDE Connect", "KDE Partition", "System Settings", "Info Center",
                 "NVIDIA X Server", "كيدي", "دولفين")
TEXT_FAMILIES = ("Name", "GenericName", "Comment", "Keywords", "X-KDE-Keywords",
                 "X-GNOME-FullName")
ARABIC_MARKS = dict.fromkeys([*range(0x064B, 0x0660), 0x0670, 0x0640])


def plain(text: str) -> str:
    return " ".join(text.translate(ARABIC_MARKS).casefold().split())


def header_text(path: Path) -> list[tuple[str, str]]:
    """Every (key, value) of the [Desktop Entry] group whose family a launcher shows or
    searches — each line, duplicates included, all languages."""
    out, group = [], None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            group = line[1:-1]
            continue
        if group == "Desktop Entry" and "=" in line:
            key, value = (part.strip() for part in line.split("=", 1))
            if key.split("[", 1)[0] in TEXT_FAMILIES:
                out.append((key, value))
    return out


FOREIGN_PLAIN = tuple(plain(word) for word in FOREIGN_NAMES)
for name, must_show in (("org.kde.dolphin.desktop", True),
                        ("org.kde.kdeconnect.app.desktop", True),
                        ("org.kde.partitionmanager.desktop", True),
                        ("systemsettings.desktop", True),
                        ("org.kde.kinfocenter.desktop", False),
                        ("nvidia-settings.desktop", False)):
    path = apps / name
    if not path.is_file():
        continue
    entry = header(path)
    shown = visible(entry)
    if shown != must_show:
        fails.append(f"GATE FAIL: {name} is {'shown in' if shown else 'hidden from'} the menu — "
                     + ("MoOS Settings is the one settings app" if shown
                        else "a person needs this tool; renaming it is the fix, not hiding it"))
    for key, value in header_text(path):
        if any(word in plain(value) for word in FOREIGN_PLAIN):
            fails.append(f"GATE FAIL: {name} still wears another desktop's name in the menu: "
                         f"{key}={value!r}")
    if not entry.get("Name[ar]"):
        fails.append(f"GATE FAIL: {name} has no Arabic name; an Arabic session would read English")

# One storefront; Discover is an engine, not an updater that races MoOS's.
discover = apps / "org.kde.discover.desktop"
if discover.is_file():
    parsed = groups(discover)
    entry = parsed.get("Desktop Entry", {})
    if visible(entry) or entry.get("Name") != "Mo Store" or entry.get("Icon") != "mo-store":
        fails.append("GATE FAIL: Discover's entry must be hidden and wear Mo Store's name and "
                     "icon — the menu would show two storefronts")
    for group, body in parsed.items():
        if group.startswith("Desktop Action") and body.get("Name") == "Mo Store":
            fails.append(f"GATE FAIL: Discover's [{group}] is named 'Mo Store' — a rebrand "
                         "leaked out of the header into a jump-list action")
# Swept, never looked up by one file name or one binary path: MoOS's overlay replaces the
# notifier's autostart entry by its exact name, and that file always exists and always says
# Hidden=true — so checking it alone would stay green after an upstream rename left the real
# entry autostarting beside an orphaned override (review finding, 2026-09-24).
DISCOVER_UPDATER = re.compile(r"DiscoverNotifier|plasma-discover\b.*--(headless-update|mode update)")
for directory in ("etc/xdg/autostart", "usr/share/autostart"):
    for path in sorted((root / directory).glob("*.desktop")):
        entry = header(path)
        if (DISCOVER_UPDATER.search(entry.get("Exec", ""))
                and entry.get("Hidden", "").lower() != "true"):
            fails.append(f"GATE FAIL: {directory}/{path.name} starts Discover's updater at login "
                         f"({entry.get('Exec')!r}) — a second updater beside MoOS's signed "
                         "update authority")
# The policy is required on every image, not only where one binary path exists: the overlay
# ships it to every edition, and a check that runs only when /usr/libexec/DiscoverNotifier is
# exactly there goes quiet the day upstream moves it.
policy = root / "etc/xdg/PlasmaDiscoverUpdates"
value = groups(policy).get("Global", {}).get("UseUnattendedUpdates") if policy.is_file() else None
if value != "false":
    fails.append("GATE FAIL: /etc/xdg/PlasmaDiscoverUpdates does not set "
                 f"UseUnattendedUpdates=false (it is {value!r}) — Discover may install "
                 "updates on its own schedule")
# And the policy must still be what Discover reads. Measured on plasma-discover-notifier 6.7.5:
# /usr/libexec/DiscoverNotifier carries "PlasmaDiscoverUpdates" (UTF-16) and
# "UseUnattendedUpdates". A notifier that names neither reads its switch from somewhere else,
# and MoOS's file would be a policy nobody obeys — re-measure before shipping it.
notifiers = {path for pattern in ("usr/libexec/DiscoverNotifier", "usr/libexec/*/DiscoverNotifier",
                                  "usr/bin/DiscoverNotifier", "usr/lib*/libexec/DiscoverNotifier")
             for path in root.glob(pattern) if path.is_file()}
for directory in ("usr/share/applications", "etc/xdg/autostart", "usr/share/autostart"):
    for path in (root / directory).glob("*.desktop"):
        words = header(path).get("Exec", "").split()
        if words and words[0].startswith("/") and os.path.basename(words[0]) == "DiscoverNotifier":
            binary = root / words[0].lstrip("/")
            if binary.is_file():
                notifiers.add(binary)
for binary in sorted(notifiers):
    data = binary.read_bytes()
    unread = [name for name in ("PlasmaDiscoverUpdates", "UseUnattendedUpdates")
              if name.encode() not in data and name.encode("utf-16-le") not in data]
    if unread:
        fails.append(f"GATE FAIL: /{binary.relative_to(root)} no longer names {unread} — "
                     "/etc/xdg/PlasmaDiscoverUpdates may not be what Discover reads any more; "
                     "re-measure where its unattended-update switch lives")

# (4) Every external module in the Settings sidebar opens a program this image ships.
categories = set()
for path in (root / "usr/share/systemsettings/categories").glob("*.desktop"):
    category = header(path).get("X-KDE-System-Settings-Category")
    if category:
        categories.add(category)
external = root / "usr/share/plasma/systemsettings/externalmodules"
for path in sorted(external.glob("*.desktop")) if external.is_dir() else []:
    entry = header(path)
    if not resolves(program(entry)):
        fails.append(f"GATE FAIL: Settings module {path.name} runs {entry.get('Exec')!r}, which "
                     "is not installed — a sidebar page that does nothing")
    if not entry.get("Name") or not entry.get("Name[ar]"):
        fails.append(f"GATE FAIL: Settings module {path.name} needs Name and Name[ar]")
    parent = entry.get("X-KDE-System-Settings-Parent-Category", "")
    if parent not in categories:
        fails.append(f"GATE FAIL: Settings module {path.name} names category {parent!r}, which "
                     "System Settings does not have — the page would never appear")
# A page MoOS staged for an installed program is offered, not left in the staging directory
# System Settings never reads.
staged = root / "usr/share/moos/settings-external-modules"
for path in sorted(staged.glob("*.desktop")) if staged.is_dir() else []:
    if resolves(program(header(path))) and not (external / path.name).is_file():
        fails.append(f"GATE FAIL: {path.name} is staged and {program(header(path))!r} is "
                     "installed, but System Settings does not offer the page")
# Hiding the firewall from the menu must not leave it unreachable.
if resolves("firewall-config") and not (external / "moos-firewall.desktop").is_file():
    fails.append("GATE FAIL: firewall-config is installed and hidden from the menu, but "
                 "MoOS Settings has no Firewall page — the firewall would be unreachable")

if fails:
    print("\n".join(fails))
    raise SystemExit(1)
print(f"curate_app_menu: menu gate OK (settings entry: systemsettings.desktop; "
      f"{len(hidden_list)} entries kept out of the menu)")
MOOSMENUGATE
