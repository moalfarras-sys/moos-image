#!/bin/bash
# make-preview.sh — render a session-surface QML (Logout portal) from a live
# look-and-feel package with a stubbed ksmserver context, fullscreen on the
# current Wayland session, and capture it with spectacle.
#
# Usage: make-preview.sh <lnf-package-dir> <sdtype:0|1|2|3> <out.png> [seconds] [scheme] [rtl]
#   sdtype: 0=logout 1=reboot 2=halt 3=full picker
#   scheme: KDE color scheme name (default MoOSUI2Dark) so the render wears the
#           package's real palette instead of the invoking session's.
#   rtl:    pass "rtl" to force the Arabic right-to-left layout in the copy.
#
# The stub only exists in a TEMP COPY — shipped QML is never modified.
set -euo pipefail
PKG="$1"; SDTYPE="$2"; OUT="$3"; HOLD="${4:-3}"; SCHEME="${5:-MoOSUI2Dark}"; RTL="${6:-ltr}"
PREVIEW_CACHE="${XDG_CACHE_HOME:-${HOME}/.cache}"
mkdir -p "$PREVIEW_CACHE"
WORK="$(mktemp -d "${PREVIEW_CACHE}/moos-preview.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

cp -r "$PKG/contents/logout" "$WORK/logout"
mkdir -p "$WORK/previews" "$WORK/splash"
cp "$PKG/contents/previews/fullscreenpreview.jpg" "$WORK/previews/" 2>/dev/null || true
cp -r "$PKG/contents/splash/images" "$WORK/splash/images" 2>/dev/null || true

cd "$WORK/logout"
# ShutdownType is a C++ context enum in ksmserver; property names cannot start
# uppercase, so rename its uses to a stub object in this throwaway copy.
sed -i 's/\bShutdownType\./stubShutdownType./g' Logout.qml
# Force the Arabic RTL branch in the throwaway copy when requested — the qml
# runtime's locale is the session's, so previews need an explicit switch.
if [ "$RTL" = "rtl" ]; then
  sed -i 's/Qt\.application\.layoutDirection === Qt\.RightToLeft/true/g' Logout.qml MoOSUI2ActionButton.qml
fi
# Inject stub context as root properties right after the root Item opens.
python3 - "$SDTYPE" <<'PY'
import re, sys
sdtype = sys.argv[1]
src = open("Logout.qml", encoding="utf-8").read()
stub = f"""
    // ── preview-harness stubs (never shipped) ──
    property var stubShutdownType: ({{"ShutdownTypeDefault": 3, "ShutdownTypeReboot": 1, "ShutdownTypeHalt": 2, "ShutdownTypeNone": 0}})
    property int sdtype: {sdtype}
    property var screenGeometry: Qt.rect(0, 0, Screen.width, Screen.height)
    property bool maysd: true
    property bool canLogout: true
    property bool softwareUpdatePending: false
    property var spdMethods: ({{"StandbyState": true, "SuspendState": true, "HibernateState": false}})
"""
# add Screen import
src = src.replace("import QtQuick\n", "import QtQuick\nimport QtQuick.Window\n", 1)
m = re.search(r"^Item \{\n    id: root\n", src, re.M)
assert m, "root Item not found"
src = src[:m.end()] + stub + src[m.end():]
open("Logout.qml", "w", encoding="utf-8").write(src)
PY

cat > runner.qml <<'QML'
import QtQuick
import QtQuick.Window

Window {
    id: win
    visible: true
    visibility: Window.FullScreen
    color: "black"
    Loader { anchors.fill: parent; source: "Logout.qml" }
}
QML

mkdir -p "$WORK/config"
printf '[General]\nColorScheme=%s\n' "$SCHEME" > "$WORK/config/kdeglobals"
export XDG_CONFIG_HOME="$WORK/config"
export QT_QPA_PLATFORMTHEME=kde
export QT_QPA_PLATFORM=wayland
QML_RUNTIME="${QML_RUNTIME:-}"
if [ -z "$QML_RUNTIME" ]; then
  for candidate in qml-qt6 qml6 qml; do
    if command -v "$candidate" >/dev/null 2>&1; then
      QML_RUNTIME="$(command -v "$candidate")"
      break
    fi
  done
fi
[ -n "$QML_RUNTIME" ] || {
  echo "capture FAILED: no Qt 6 QML runtime is installed" >&2
  exit 1
}
"$QML_RUNTIME" runner.qml &
QPID=$!
sleep "$HOLD"
kill -0 "$QPID" 2>/dev/null || {
  wait "$QPID" 2>/dev/null || true
  echo "capture FAILED: the QML preview exited before capture" >&2
  exit 1
}
spectacle -b -f -n -o "$OUT" 2>/dev/null || grim "$OUT" 2>/dev/null || true
sleep 1
kill "$QPID" 2>/dev/null || true
wait "$QPID" 2>/dev/null || true
[ -s "$OUT" ] && echo "captured: $OUT" || { echo "capture FAILED" >&2; exit 1; }
