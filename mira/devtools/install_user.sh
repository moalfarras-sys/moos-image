#!/bin/sh
# Install this Mira source as the owner's user app (~/.local/share/mira/app) and restart it.
#
# The previous install is kept whole in ~/.local/share/mira/app.before-<stamp>; rolling back is
# moving that directory back. Credentials, memory and conversation live in ~/.config/mo-dot and
# are never touched. This is a per-user app install, not a MoOS image change.
#
# Mira is the MoOS assistant: this also gives her Mo AI's entry points for this user —
# ~/.local/bin/mira and a `moai` shim (first on the session PATH), and an org.moos.moai.desktop
# override (name Mira, Mo AI's icon, Meta+Space). Mo AI's services keep running as her executor.
#
#   sh devtools/install_user.sh                 install + restart
#   sh devtools/install_user.sh --no-restart
#   sh devtools/install_user.sh --restore-moai  give the launcher back to the old Mo AI window
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
BASE="$HOME/.local/share/mira"
APP="$BASE/app"
STAMP=$(date +%Y%m%dT%H%M%S)
PY="$BASE/venv/bin/python"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"

refresh_menus() {
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" 2>/dev/null || true
    command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 >/dev/null 2>&1 || true
}

if [ "${1:-}" = "--restore-moai" ]; then
    rm -f "$BIN/moai" "$APPS/org.moos.moai.desktop"
    refresh_menus
    echo "restored: moai and Meta+Space open the system Mo AI window again (Mira stays at $BIN/mira)"
    exit 0
fi

[ -x "$PY" ] || { echo "missing $PY" >&2; exit 1; }
"$PY" -m py_compile "$SRC"/*.py
if [ -d "$APP" ]; then
    cp -a "$APP" "$BASE/app.before-$STAMP"
    echo "backup: $BASE/app.before-$STAMP"
fi
mkdir -p "$APP"
# Mirror the source tree, leaving caches behind; the previous files stay in the backup only.
find "$APP" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
tar -C "$SRC" --exclude='__pycache__' --exclude='*.pyc' -cf - . | tar -C "$APP" -xf -
echo "installed: $(cd "$APP" && ls | wc -l) entries from $SRC"

# Wake models that ship with Mira, served to the Echo from here (it checks size and SHA-256).
MODELS="$BASE/wake-models"
mkdir -p "$MODELS" && chmod 700 "$MODELS"
for model in "$SRC"/wake_training/mira_ar_v2.tflite "$SRC"/wake_training/mira_ar_v2.json; do
    [ -f "$model" ] && install -m 644 "$model" "$MODELS/"
done

# Mo AI's entry points are Mira's.
mkdir -p "$BIN" "$APPS"
sed -e "s|@PY@|$PY|" -e "s|@APP@|$APP|" "$SRC/desktop/mira.in" > "$BIN/mira.tmp" && chmod 755 "$BIN/mira.tmp" && mv "$BIN/mira.tmp" "$BIN/mira"
install -m 755 "$SRC/desktop/moai" "$BIN/moai"
sed "s|@BIN@|$BIN|g" "$SRC/desktop/org.moos.moai.desktop.in" > "$APPS/org.moos.moai.desktop"
# One launcher, not two: the earlier stand-alone entry stays hidden.
if [ -f "$APPS/mira.desktop" ]; then
    printf '[Desktop Entry]\nType=Application\nName=Mira\nNoDisplay=true\nExec=%s/mira\n' "$BIN" > "$APPS/mira.desktop"
fi
AUTOSTART="$HOME/.config/autostart/mira.desktop"
if [ -f "$AUTOSTART" ]; then
    # Keep how the owner chose to start: Mira's Settings writes `--background` (the tray, no window).
    # The launcher is named by its absolute path in TryExec and Exec: the user manager's autostart
    # generator does not search ~/.local/bin.
    bg=""
    grep -q -- '--background' "$AUTOSTART" && bg=" --background"
    printf '[Desktop Entry]\nType=Application\nName=Mira\nName[ar]=ميرا\nTryExec=%s/mira\nExec=%s/mira%s\nIcon=moos-moai\nTerminal=false\nX-GNOME-Autostart-enabled=true\n' "$BIN" "$BIN" "$bg" > "$AUTOSTART"
fi
refresh_menus
echo "launcher: $BIN/mira · moai shim · $APPS/org.moos.moai.desktop"

if [ "${1:-}" != "--no-restart" ]; then
    # Stop whichever unit runs the old window (autostart or a detached launch), then relaunch
    # detached so the app outlives this shell.
    for unit in $(systemctl --user list-units --type=service --state=running --no-legend --plain \
                  | awk '{print $1}'); do
        case "$(systemctl --user show -p ExecStart --value "$unit" 2>/dev/null)" in
            *"$BASE/app/app.py"*|*"$BIN/mira"*) systemctl --user stop "$unit" && echo "stopped $unit" ;;
        esac
    done
    # A window opened from the launcher lives in a scope, not a service: end it the same way.
    pkill -TERM -f "$APP/app.py" 2>/dev/null && echo "stopped the launcher-started window" || true
    sleep 1
    if command -v moai-open >/dev/null 2>&1; then
        moai-open "$BIN/mira"
    else
        systemd-run --user --collect -- "$BIN/mira"
    fi
fi
