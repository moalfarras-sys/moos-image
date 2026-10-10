#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python_bin=${COMMUNITY_PYTHON:-python3}
"$python_bin" -m unittest community.test_service community.test_releases community.test_transport community.test_proxy -v
if [[ ${1:-} == --native ]]; then
    # An explicit native check fails if Qt is unavailable; it never calls a skip a pass.
    native_home=$(mktemp -d "${TMPDIR:-/var/tmp}/moos-community-native.XXXXXX")
    trap 'rm -rf -- "$native_home"' EXIT
    mkdir -m 0700 "$native_home/runtime"
    dbus-run-session -- env HOME="$native_home" XDG_CONFIG_HOME="$native_home/config" \
        XDG_DATA_HOME="$native_home/data" XDG_CACHE_HOME="$native_home/cache" \
        XDG_RUNTIME_DIR="$native_home/runtime" DISPLAY= WAYLAND_DISPLAY= \
        XDG_CURRENT_DESKTOP= QT_QPA_PLATFORMTHEME= QT_QPA_PLATFORM=offscreen \
        QT_QUICK_BACKEND=software QT_QUICK_CONTROLS_STYLE=Basic \
        "$python_bin" -m unittest community.test_client -v
fi
