#!/usr/bin/env bash
# QML editor server from the development SDK, including VS Code Flatpak.
# Keep stdio intact; the SDK owns its Qt libraries and the host stays immutable.
set -euo pipefail
sdk_container="${MOOS_SDK_CONTAINER:-moos-dev}"
native_sdk="${MOOS_QML_SDK_DIR:-${HOME}/.local/share/moos-dev-platform/qmlls}"
if [[ -f /run/.toolboxenv ]]; then
    exec /usr/lib64/qt6/bin/qmlls --no-cmake-calls "$@"
elif [[ -f /.flatpak-info ]]; then
    exec flatpak-spawn --host bash "$0" "$@"
elif [[ -x "$native_sdk/bin/qmlls" && -r "$native_sdk/qt-package-version" ]]; then
    # The native SDK contains only qmlls and its compiler library, copied from
    # the reviewed development SDK. Refuse a Qt package transition until that
    # SDK is refreshed; never mix private Qt APIs across versions.
    runtime_version="$(rpm -q --qf '%{VERSION}-%{RELEASE}\n' qt6-qtdeclarative)"
    [[ "$runtime_version" == "$(cat "$native_sdk/qt-package-version")" ]] || {
        echo 'MoOS: refresh the QML development SDK for the installed Qt package.' >&2
        exit 69
    }
    export LD_LIBRARY_PATH="$native_sdk/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    exec "$native_sdk/bin/qmlls" --no-cmake-calls "$@"
elif [[ "$(podman inspect --format '{{.State.Running}}' "$sdk_container" 2>/dev/null)" == true ]]; then
    # Qt's extension gives its executable probe one second. Avoid Toolbox's
    # repeated environment setup once the existing development SDK is ready.
    exec podman exec --interactive --user "$(id -u)" --workdir "$PWD" \
        "$sdk_container" /usr/lib64/qt6/bin/qmlls --no-cmake-calls "$@"
else
    exec /usr/bin/toolbox run --container "$sdk_container" \
        /usr/lib64/qt6/bin/qmlls --no-cmake-calls "$@"
fi
