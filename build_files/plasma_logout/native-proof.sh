#!/usr/bin/env bash
# Runs inside the disposable SDK stage, never the development station's bus.
set -euxo pipefail
ulimit -c 0
_logout_proof=/work/logout-native-proof
mkdir -p "${_logout_proof}/fixed" "${_logout_proof}/home/.config" "${_logout_proof}/runtime"
chmod 0700 "${_logout_proof}/runtime"
_logout_rpm="$(python3 - <<'PY'
import json
from pathlib import Path
m=json.loads(Path('/out/manifest.json').read_text())
p=[i for i in m['packages'] if i['name']=='plasma-workspace']
assert len(p)==1
print('/out/'+p[0]['file'])
PY
)"
(cd "${_logout_proof}/fixed"; rpm2cpio "${_logout_rpm}" | cpio -idm --no-absolute-filenames --no-preserve-owner './usr/bin/plasma-shutdown')
# Prevent the private worker's default session saver from spawning unrelated apps.
printf '[General]\nloginMode=emptySession\n' > "${_logout_proof}/home/.config/ksmserverrc"
g++ -std=c++17 -O2 -fstack-protector-strong /src/native-proof.cpp \
    -o "${_logout_proof}/native-proof" $(pkg-config --cflags --libs Qt6Core Qt6DBus)
unset DISPLAY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS
export HOME="${_logout_proof}/home" XDG_CONFIG_HOME="${_logout_proof}/home/.config"
export XDG_RUNTIME_DIR="${_logout_proof}/runtime" XDG_STATE_HOME="${_logout_proof}/home/state"
export XDG_DATA_HOME="${_logout_proof}/home/data" XDG_CACHE_HOME="${_logout_proof}/home/cache"
dbus-run-session -- "${_logout_proof}/native-proof" /usr/bin/plasma-shutdown old
for _logout_case in fixed rejected cancelled; do
    dbus-run-session -- "${_logout_proof}/native-proof" \
        "${_logout_proof}/fixed/usr/bin/plasma-shutdown" "${_logout_case}"
done
mkdir -p /out/proof
sha256sum /usr/bin/plasma-shutdown "${_logout_proof}/fixed/usr/bin/plasma-shutdown" \
    > /out/proof/native-worker-sha256.txt
