#!/usr/bin/bash
# MoOS in System Settings — the image gate, shared by build.sh and build-arm.sh so
# the x86 and ARM images are held to the same contract.
#
#  1. Every module the KCM stage built (/usr/share/moos/settings-modules.list) is
#     installed, the five core modules are in that list, and the MoOS category
#     overlay that groups them exists.
#  2. The upstream Software Update and About this System modules are removed with
#     their menu aliases, wherever under plasma/kcms the plugin lives: each would be
#     a second update or about entry beside the MoOS group.
#  3. Every module LOADS. kcmshell6 keeps running when a page fails to load — it
#     shows an error page — so exit 124 alone proves nothing (measured). The verdict
#     is all three: still alive at the timeout, no QML error line, and the backend's
#     MOOS_KCM_READY marker, which it prints only once the page was constructed.
#     Offscreen, on a private session bus, with a private HOME and XDG tree.
set -euo pipefail

plugins="$(qtpaths6 --query QT_INSTALL_PLUGINS)"
kcm_dir="$plugins/plasma/kcms/systemsettings"
list=/usr/share/moos/settings-modules.list
category=/usr/share/systemsettings/categories/settings-moos.desktop

[ -s "$list" ] \
    || { echo "GATE FAIL: $list is missing — the MoOS System Settings modules did not install"; exit 1; }
for core in kcm_moos kcm_moos_update kcm_moos_whatsnew kcm_moos_remote kcm_moos_recovery; do
    grep -qx "$core" "$list" \
        || { echo "GATE FAIL: $core is not among the built MoOS System Settings modules"; exit 1; }
done
modules=()
while IFS= read -r module; do
    [ -n "$module" ] || continue
    case "$module" in
        kcm_moos|kcm_moos_[a-z]*) ;;
        *) echo "GATE FAIL: '$module' in $list is not a MoOS module id"; exit 1 ;;
    esac
    [ -s "$kcm_dir/$module.so" ] \
        || { echo "GATE FAIL: MoOS System Settings module $module did not install"; exit 1; }
    modules+=("$module")
done <"$list"
[ -s "$category" ] \
    || { echo "GATE FAIL: the MoOS group of System Settings ($category) is missing"; exit 1; }
grep -qx 'X-KDE-System-Settings-Category=moos' "$category" \
    || { echo "GATE FAIL: $category does not declare the moos category"; exit 1; }

for duplicate in kcm_updates kcm_about-distro; do
    find "$plugins/plasma/kcms" -name "$duplicate.so" -delete
    rm -f "/usr/share/applications/$duplicate.desktop"
    left="$(find "$plugins/plasma/kcms" -name "$duplicate.so")"
    [ -z "$left" ] && [ ! -e "/usr/share/applications/$duplicate.desktop" ] \
        || { echo "GATE FAIL: the duplicate module $duplicate remains: $left"; exit 1; }
done

command -v kcmshell6 >/dev/null 2>&1 \
    || { echo "GATE FAIL: kcmshell6 is required to load-test the MoOS System Settings modules"; exit 1; }
command -v dbus-run-session >/dev/null 2>&1 \
    || { echo "GATE FAIL: dbus-run-session is required to load-test the MoOS System Settings modules"; exit 1; }
home="$(mktemp -d /tmp/moos-kcm-home.XXXXXX)"
for module in "${modules[@]}"; do
    runtime="$(mktemp -d /tmp/moos-kcm-runtime.XXXXXX)"
    chmod 0700 "$runtime"
    log="$(mktemp /tmp/moos-kcm-load.XXXXXX.log)"
    set +e
    dbus-run-session -- env -u DISPLAY -u WAYLAND_DISPLAY \
        HOME="$home" XDG_RUNTIME_DIR="$runtime" \
        XDG_CONFIG_HOME="$home/.config" XDG_DATA_HOME="$home/.local/share" \
        XDG_CACHE_HOME="$home/.cache" XDG_STATE_HOME="$home/.local/state" \
        QT_QPA_PLATFORM=offscreen QT_FORCE_STDERR_LOGGING=1 QML_DISABLE_DISK_CACHE=1 \
        timeout --kill-after=5s 10 kcmshell6 "$module" >"$log" 2>&1
    rc=$?
    set -e
    errors="$(grep -E 'Error loading QML|is not a type|ReferenceError|TypeError|module .* is not installed|Unable to assign|Cannot assign' "$log" || true)"
    ready="$(grep -cx ".*MOOS_KCM_READY $module" "$log" || true)"
    if [ "$rc" -ne 124 ] || [ -n "$errors" ] || [ "$ready" -lt 1 ]; then
        echo "FATAL: the System Settings module '$module' did not load cleanly (exit=$rc, ready=$ready)."
        echo "       It would open as an error page for the owner. Its own output follows:"
        cat "$log"
        exit 1
    fi
    rm -rf "$runtime" "$log"
done
rm -rf "$home"
echo "MoOS System Settings modules: ${#modules[@]} installed, grouped and loaded (${modules[*]})"
