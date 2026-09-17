#!/usr/bin/env bash
# LOOK at the MoOS desktop from the SOURCE tree, off the station: the real plasmashell with MoOS's
# shipped layout, plasmoids, scene wallpaper and config, under Xvfb with kwin_x11.
#
#   scripts/review/render-desktop.sh /tmp/desk-ar.png --lang=ar
#   scripts/review/render-desktop.sh /tmp/launcher.png --call=activateLauncherMenu
#   render-desktop.sh <out.png> [--lang=ar|en] [--size=1536x864] [--wallpaper=MoOSUI2Aurora]
#                     [--wait=35] [--script=file.js] [--hub=off] [--call=<PlasmaShell method>]
#                     [--runtime-file=moos-privacy/active-mic-57-Firefox]   (an Island state token)
#                     [--run='notify-send …']   (a command run inside the session before the capture)
#
# WHAT THIS IS NOT: there is no GPU compositing here, so no blur, no translucency, no rounded
# panel corners, no KWin effects or window animations, and it is X11 while MoOS is Wayland.
# It shows the SHELL's composition — scene, Hub, bar, launcher, plasmoids, fonts, RTL — and prints
# the QML runtime's complaints about MoOS's own packages. It is never a desktop review.
# ALSO MISSING: the base icon theme (MoOSUI2) is assembled inside the image build from an
# upstream set, so an icon that comes from it — a stock application's, for one — is blank here.
# A blank STOCK icon in this render is the environment; a blank moos-* icon is a finding.
set -uo pipefail
[ "$#" -ge 1 ] || { sed -n '2,18p' "$0"; exit 2; }
OUT="$(realpath -m "$1")"; shift
ROOT="${MOOS_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
LANGUAGE_CODE=en; SIZE=1536x864; WALLPAPER=MoOSUI2Aurora; WAIT=35; SCRIPT=""; HUB=on; CALL=""; RUN=""; RUNTIME_FILES=()
for arg in "$@"; do
    case "$arg" in
        --lang=*) LANGUAGE_CODE="${arg#--lang=}" ;;
        --size=*) SIZE="${arg#--size=}" ;;
        --wallpaper=*) WALLPAPER="${arg#--wallpaper=}" ;;
        --wait=*) WAIT="${arg#--wait=}" ;;
        --script=*) SCRIPT="$(realpath "${arg#--script=}")" ;;
        --hub=*) HUB="${arg#--hub=}" ;;
        --runtime-file=*) RUNTIME_FILES+=("${arg#--runtime-file=}") ;;   # an empty file under XDG_RUNTIME_DIR (a state token)
        --call=*) CALL="${arg#--call=}" ;;   # a no-argument org.kde.PlasmaShell method, e.g. activateLauncherMenu
        --run=*) RUN="${arg#--run=}" ;;      # a shell command run INSIDE the session before the capture (notify-send …)
    esac
done
case "$LANGUAGE_CODE" in ar) LOCALE=ar_EG.UTF-8 ;; *) LOCALE=en_US.UTF-8 ;; esac
WORK="$(mktemp -d "${TMPDIR:-/tmp}/moos-desktop.XXXXXX")"
trap 'rm -rf -- "$WORK"' EXIT
export HOME="$WORK/home" XDG_CONFIG_HOME="$WORK/home/.config" XDG_CACHE_HOME="$WORK/home/.cache"
export XDG_DATA_HOME="$WORK/home/.local/share" XDG_RUNTIME_DIR="$WORK/run"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"
# MoOS overrides PARTS of stock packages (the shell package's lock screen, explorer, defaults).
# In the image those files land inside the stock directory; here the stock package is copied and
# the MoOS files are laid over it, or KPackage finds a package with no metadata and draws nothing.
MERGED="$WORK/merged-share"; mkdir -p "$MERGED"
cp -a /usr/share/plasma "$MERGED/plasma"
rsync -a "$ROOT/system_files/usr/share/plasma/" "$MERGED/plasma/"
export XDG_DATA_DIRS="$MERGED:$ROOT/system_files/usr/share:/usr/share"
export XDG_CONFIG_DIRS="$ROOT/system_files/etc/xdg:/etc/xdg"
export QML_IMPORT_PATH="$ROOT/system_files/usr/lib64/qt6/qml" QML2_IMPORT_PATH="$ROOT/system_files/usr/lib64/qt6/qml"
export PATH="$ROOT/system_files/usr/bin:$ROOT/system_files/usr/libexec:$PATH"
export LIBGL_ALWAYS_SOFTWARE=1 QT_QPA_PLATFORM=xcb QML_DISABLE_DISK_CACHE=1
export XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true KDE_SESSION_VERSION=6 XDG_SESSION_TYPE=x11
export LC_ALL="$LOCALE" LANG="$LOCALE" LANGUAGE=
unset WAYLAND_DISPLAY DISPLAY DBUS_SESSION_BUS_ADDRESS
IMAGE="$ROOT/system_files/usr/share/wallpapers/$WALLPAPER"
# MoOS plasmoids read state as FILE NAMES under the runtime directory (the Island's Store job,
# privacy and Remote tokens). --runtime-file=moos-store/job-install-running-45-org.mozilla.firefox
for token in "${RUNTIME_FILES[@]}"; do
    case "$token" in /*|*..*) echo "render-desktop: --runtime-file is relative to the runtime dir" >&2; exit 2 ;; esac
    mkdir -p "$XDG_RUNTIME_DIR/$(dirname "$token")" && : > "$XDG_RUNTIME_DIR/$token"
done
cat > "$WORK/scene.js" <<EOS
var ds = desktops();
for (var i = 0; i < ds.length; i++) {
    ds[i].wallpaperPlugin = "org.moos.ui2.wallpaper";
    ds[i].currentConfigGroup = ["Wallpaper", "org.moos.ui2.wallpaper", "General"];
    ds[i].writeConfig("Image", "$IMAGE");
    ds[i].writeConfig("ShowDashboard", $([ "$HUB" = off ] && echo false || echo true));
    ds[i].reloadConfig();
}
print("moos-scene:" + ds.length);
EOS
cat > "$WORK/session.sh" <<'EOS'
#!/usr/bin/env bash
kwin_x11 --replace >"$WORK/kwin.log" 2>&1 &
sleep 3
/usr/libexec/kactivitymanagerd >"$WORK/kamd.log" 2>&1 &   # not on PATH, and D-Bus activation wants systemd
# plasmashell aborts its load when the activity manager is not on the bus yet.
for _ in $(seq 1 40); do
    gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner org.kde.ActivityManager 2>/dev/null | grep -q true && break
    sleep 0.5
done
plasmashell --no-respawn >"$WORK/plasmashell.log" 2>&1 &
sleep "$WAIT"
for js in "$WORK/scene.js" $SCRIPT; do
    gdbus call --session --dest org.kde.plasmashell --object-path /PlasmaShell \
        --method org.kde.PlasmaShell.evaluateScript "$(cat "$js")" >>"$WORK/script.log" 2>&1
    sleep 8
done
if [ -n "$CALL" ]; then
    gdbus call --session --dest org.kde.plasmashell --object-path /PlasmaShell \
        --method "org.kde.PlasmaShell.$CALL" >>"$WORK/script.log" 2>&1
    sleep 5
fi
if [ -n "$RUN" ]; then
    # Backgrounded: a command that waits for the person (notify-send --wait) must not hold the capture.
    bash -c "$RUN" >>"$WORK/run.log" 2>&1 &
    sleep 6
fi
xwd -root -silent | magick xwd:- "$OUT" 2>>"$WORK/shot.log"
EOS
chmod +x "$WORK/session.sh"
export WORK OUT WAIT SCRIPT CALL RUN
timeout 240 dbus-run-session -- xvfb-run -a -s "-screen 0 ${SIZE}x24" "$WORK/session.sh" >"$WORK/session.out" 2>&1
status=$?
[ -s "$OUT" ] && echo "rendered $OUT" || echo "NO FRAME (exit $status)"
cat "$WORK/script.log" 2>/dev/null | head -4
# MoOS's own packages only: the stock shell's chatter about missing services is not a finding.
grep -E "org\.moos|/moos/|MoOS" "$WORK/plasmashell.log" 2>/dev/null \
    | sed -E "s#file://$WORK/merged-share/#usr/share/#" | sort | uniq -c | sort -rn | head -20
[ -n "${MOOS_RENDER_KEEP_LOG:-}" ] && cp "$WORK/plasmashell.log" "$MOOS_RENDER_KEEP_LOG" 2>/dev/null
exit "$status"
