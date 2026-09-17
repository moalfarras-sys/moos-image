#!/usr/bin/env bash
# LOOK at MoOS's lock screen from the SOURCE tree: kscreenlocker_greet in its own --testing mode,
# with MoOS's lockscreen QML laid over the stock shell package, under Xvfb.
#   scripts/review/render-lockscreen.sh /tmp/lock-ar.png --lang=ar
#   render-lockscreen.sh <out.png> [--lang=ar|en] [--size=1536x864] [--wallpaper=MoOSUI2Aurora]
#
# The idle state only (clock, date, brand): the password card appears on input, which this does
# not send. Same limits as render-desktop.sh — no compositor effects, X11, source-harness evidence.
# Brand art is opened by ABSOLUTE path (/usr/share/pixmaps/moos-logo.png): setup-review-distro.sh
# links it; without that the brand stage is an empty circle, which is the environment.
set -uo pipefail
OUT="$(realpath -m "$1")"; shift
ROOT="${MOOS_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
LANGUAGE_CODE=en; SIZE=1536x864; WALLPAPER=MoOSUI2Aurora
for arg in "$@"; do
    case "$arg" in
        --lang=*) LANGUAGE_CODE="${arg#--lang=}" ;;
        --size=*) SIZE="${arg#--size=}" ;;
        --wallpaper=*) WALLPAPER="${arg#--wallpaper=}" ;;
    esac
done
case "$LANGUAGE_CODE" in ar) LOCALE=ar_EG.UTF-8 ;; *) LOCALE=en_US.UTF-8 ;; esac
WORK="$(mktemp -d "${TMPDIR:-/tmp}/moos-lock.XXXXXX")"; trap 'rm -rf -- "$WORK"' EXIT
export HOME="$WORK/home" XDG_CONFIG_HOME="$WORK/home/.config" XDG_CACHE_HOME="$WORK/home/.cache"
export XDG_DATA_HOME="$WORK/home/.local/share" XDG_RUNTIME_DIR="$WORK/run"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"
MERGED="$WORK/merged-share"; mkdir -p "$MERGED"
cp -a /usr/share/plasma "$MERGED/plasma"
rsync -a "$ROOT/system_files/usr/share/plasma/" "$MERGED/plasma/"
export XDG_DATA_DIRS="$MERGED:$ROOT/system_files/usr/share:/usr/share"
export XDG_CONFIG_DIRS="$ROOT/system_files/etc/xdg:/etc/xdg"
export QML_IMPORT_PATH="$ROOT/system_files/usr/lib64/qt6/qml" QML2_IMPORT_PATH="$ROOT/system_files/usr/lib64/qt6/qml"
export LIBGL_ALWAYS_SOFTWARE=1 QT_QPA_PLATFORM=xcb QML_DISABLE_DISK_CACHE=1
export XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true KDE_SESSION_VERSION=6 XDG_SESSION_TYPE=x11
export LC_ALL="$LOCALE" LANG="$LOCALE" LANGUAGE=
unset WAYLAND_DISPLAY DISPLAY DBUS_SESSION_BUS_ADDRESS
# What MoOS pins for the lock screen's wallpaper, if the tree ships it; else the scene image.
cat > "$XDG_CONFIG_HOME/kscreenlockerrc" <<EOS
[Greeter]
WallpaperPlugin=org.kde.image

[Greeter][Wallpaper][org.kde.image][General]
Image=$ROOT/system_files/usr/share/wallpapers/$WALLPAPER
EOS
cat > "$WORK/session.sh" <<'EOS'
#!/usr/bin/env bash
/usr/libexec/kscreenlocker_greet --testing >"$WORK/greet.log" 2>&1 &
sleep "${LOCK_WAIT:-12}"
xwd -root -silent | magick xwd:- "$OUT" 2>>"$WORK/shot.log"
EOS
chmod +x "$WORK/session.sh"
export WORK OUT
timeout 120 dbus-run-session -- xvfb-run -a -s "-screen 0 ${SIZE}x24" "$WORK/session.sh" >"$WORK/session.out" 2>&1
[ -s "$OUT" ] && echo "rendered $OUT" || echo "NO FRAME"
grep -E "lockscreen|MoOS|moos|Error|error" "$WORK/greet.log" 2>/dev/null | sed -E "s#file://$WORK/merged-share/#usr/share/#" | sort | uniq -c | sort -rn | head -12
