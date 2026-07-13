#!/usr/bin/env bash
# raise.sh — bring the MoPlayer window to the front, on Plasma Wayland.
#
# Why this exists: KWin refuses to let a window launched from a script steal
# focus, which is correct behaviour and completely defeats screenshot-based QA —
# every capture came back showing the editor that was already in front. There is
# no `xdotool` under Wayland, so the compositor has to be asked directly.
#
# The window is matched on `resourceClass`, which is the Wayland app_id — the
# same string as AppConfig.appId, linux/CMakeLists.txt's APPLICATION_ID, and the
# .desktop file's StartupWMClass. If this script ever stops finding the window,
# that is not a bug in the script: it means those four have drifted apart, and
# test/app_identity_test.dart should have caught it.
set -euo pipefail

APP_ID="${1:-org.moos.moplayer}"

script=$(mktemp --suffix=.js)
trap 'rm -f "$script"' EXIT
cat > "$script" <<EOF
workspace.windowList().forEach(w => {
    if (w.resourceClass === "$APP_ID") {
        w.minimized = false;
        workspace.activeWindow = w;
    }
});
EOF

id=$(gdbus call --session --dest org.kde.KWin --object-path /Scripting \
        --method org.kde.kwin.Scripting.loadScript "$script" \
     | grep -oE '[0-9]+' | head -1)

if [ -z "${id:-}" ]; then
    echo "raise: KWin refused the script (is this a Plasma session?)" >&2
    exit 1
fi

gdbus call --session --dest org.kde.KWin --object-path "/Scripting/Script$id" \
    --method org.kde.kwin.Script.run >/dev/null

# KWin keeps a loaded script around; unload it so repeated QA runs do not pile up
# hundreds of dead script objects on the compositor.
gdbus call --session --dest org.kde.KWin --object-path /Scripting \
    --method org.kde.kwin.Scripting.unloadScript "$script" >/dev/null 2>&1 || true
