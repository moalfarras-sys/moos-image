#!/usr/bin/env bash
# LOOK at a first-party app from source, off the station: render it under Xvfb with Mesa's
# software GL and the KDE platform theme, so Kirigami.Theme reads a real MoOS colour scheme.
#
#   scripts/review/render-app.sh moai  /tmp/moai-ar.png  --lang=ar
#   scripts/review/render-app.sh store /tmp/store.png    --scheme=MoOSUI2AuroraLight --w=1100 --h=700
#   scripts/review/render-app.sh moai  /tmp/x.png        --harness=tests/qml/some-review.qml
#
# <app> is a directory under system_files/usr/share/moos/apps. Needs setup-review-distro.sh once.
# This is SOURCE-HARNESS evidence: it finds binding errors, clipping, contrast and RTL mistakes.
# It is not the installed app and not a desktop review; say which one you ran.
set -uo pipefail
[ "$#" -ge 2 ] || { sed -n '2,12p' "$0"; exit 2; }
APP="$1"; OUT="$(realpath -m "$2")"; shift 2
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCHEME=MoOSUI2Aurora
HARNESS="$ROOT/scripts/review/render-app.qml"
PASS=()
for arg in "$@"; do
    case "$arg" in
        --scheme=*) SCHEME="${arg#--scheme=}" ;;
        --harness=*) HARNESS="$(realpath "${arg#--harness=}")" ;;
        *) PASS+=("$arg") ;;
    esac
done
MAIN="$ROOT/system_files/usr/share/moos/apps/$APP/main.qml"
[ -f "$MAIN" ] || { echo "render-app: no such app: $APP" >&2; exit 2; }
[ -f "$ROOT/system_files/usr/share/color-schemes/$SCHEME.colors" ] || { echo "render-app: no such scheme: $SCHEME" >&2; exit 2; }

# A private home and runtime directory: a review must never read or write a real profile.
WORK="$(mktemp -d "${TMPDIR:-/tmp}/moos-render.XXXXXX")"
trap 'rm -rf -- "$WORK"' EXIT
export HOME="$WORK/home" XDG_CONFIG_HOME="$WORK/home/.config" XDG_CACHE_HOME="$WORK/home/.cache"
export XDG_DATA_HOME="$WORK/home/.local/share" XDG_RUNTIME_DIR="$WORK/run"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"
# The session defaults plus the scheme inlined, which is what applying a Global Theme writes.
case "$SCHEME" in *Light|*Daylight) ICONS=MoOSUI2AuroraLight ;; *) ICONS=MoOSUI2Aurora ;; esac
{ cat "$ROOT/system_files/etc/xdg/kdeglobals"; echo
  cat "$ROOT/system_files/usr/share/color-schemes/$SCHEME.colors"
  printf '\n[Icons]\nTheme=%s\n' "$ICONS"; } \
    | sed -E "s/^ColorScheme=.*/ColorScheme=$SCHEME/" > "$XDG_CONFIG_HOME/kdeglobals"
unset WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS DISPLAY
export QT_QPA_PLATFORMTHEME=kde XDG_CURRENT_DESKTOP=KDE KDE_SESSION_VERSION=6 KDE_FULL_SESSION=true
export QML_IMPORT_PATH="$ROOT/system_files/usr/lib64/qt6/qml" QML_DISABLE_DISK_CACHE=1
export QML_XHR_ALLOW_FILE_READ=1 QT_QUICK_CONTROLS_STYLE=org.kde.desktop LIBGL_ALWAYS_SOFTWARE=1
export QT_LOGGING_RULES='qt.qpa.*=false;kf.*=false;qt.svg=false'
RUNTIME="$(command -v qml-qt6 || command -v qml6 || command -v qml)" || { echo "render-app: no QML runtime" >&2; exit 2; }
# Ports nobody listens on: the app must draw its honest "not reachable" state, not hang.
timeout 120 dbus-run-session -- xvfb-run -a -s "-screen 0 2560x1600x24" \
    "$RUNTIME" "$HARNESS" -- --src="$MAIN" --out="$OUT" \
    --gateway-port 65001 --control-port 65002 --agent-port 65003 "${PASS[@]}" > "$WORK/log" 2>&1
status=$?
[ -f "$OUT" ] && echo "rendered $OUT" || echo "NO FRAME (exit $status)"
# The runtime log is half the review: a binding error does not stop a window from opening.
grep -E "^file://|TypeError|ReferenceError|Unable to assign|is not defined|RENDER FAIL" "$WORK/log" \
    | sed -E "s#file://$ROOT/##" | sort | uniq -c | sort -rn | head -25
exit "$status"
