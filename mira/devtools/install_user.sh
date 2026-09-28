#!/bin/sh
# Install this Mira source as the owner's user app (~/.local/share/mira/app) and restart it.
#
# The previous install is kept whole in ~/.local/share/mira/app.before-<stamp>; rolling back is
# moving that directory back. Credentials, memory and conversation live in ~/.config/mo-dot and
# are never touched. This is a per-user app install, not a MoOS image change.
#
#   sh devtools/install_user.sh            install + restart
#   sh devtools/install_user.sh --no-restart
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
BASE="$HOME/.local/share/mira"
APP="$BASE/app"
STAMP=$(date +%Y%m%dT%H%M%S)
PY="$BASE/venv/bin/python"

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

if [ "${1:-}" != "--no-restart" ]; then
    # Stop whichever unit runs the old window (autostart or a detached launch), then relaunch
    # detached so the app outlives this shell.
    for unit in $(systemctl --user list-units --type=service --state=running --no-legend --plain \
                  | awk '{print $1}'); do
        case "$(systemctl --user show -p ExecStart --value "$unit" 2>/dev/null)" in
            *"$BASE/app/app.py"*) systemctl --user stop "$unit" && echo "stopped $unit" ;;
        esac
    done
    sleep 1
    if command -v moai-open >/dev/null 2>&1; then
        moai-open "$PY" "$APP/app.py"
    else
        systemd-run --user --collect -- "$PY" "$APP/app.py"
    fi
fi
