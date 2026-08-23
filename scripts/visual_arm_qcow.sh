#!/usr/bin/env bash
# Visual ARM QA — boot with GTK, capture REAL screenshots via QEMU monitor (not CI grim).
set -euo pipefail

QCOW="${1:?usage: visual_arm_qcow.sh IMAGE.qcow2}"
DIGEST="${2:-ghcr.io/moalfarras-sys/moos-arm@sha256:e6eb73d2f449bbfe76d9aa24e3aa88fc933706f1752c1b6c6db78698e81ce090}"
PROOF="${3:-/var/home/moos/Desktop/MoOS-Release/PROOF}"
mkdir -p "$PROOF"

export MOOS_ARM_DISPLAY=gtk
export MOOS_ARM_VISUAL_HOLD=1
export MOOS_ARM_SSH_PORT=2223

evidence="$(mktemp -d /var/tmp/moos-arm-visual.XXXXXX)"
echo "Evidence dir: $evidence"

# Boot in background via the release gate script (runtime proof + GTK window).
tests/boot_arm_qcow2.sh "$QCOW" "$DIGEST" "$evidence" &
boot_pid=$!

capture_monitor() {
    local name="$1" monitor="$2"
    local ppm="$evidence/${name}.ppm"
    printf 'screendump %s\n' "$ppm" | socat - UNIX-CONNECT:"$monitor" >/dev/null 2>&1 || return 1
    [ -s "$ppm" ] && convert "$ppm" "$PROOF/${name}.png" && rm -f "$ppm"
}

# Wait for SSH / greeter, then screendump from monitor socket inside evidence.
deadline=$((SECONDS + 900))
monitor=""
while [ "$SECONDS" -lt "$deadline" ]; do
    monitor="$(find "$evidence" -name 'monitor.sock' 2>/dev/null | head -1)"
    [ -n "$monitor" ] && [ -S "$monitor" ] && break
    kill -0 "$boot_pid" 2>/dev/null || break
    sleep 5
done

if [ -n "$monitor" ] && [ -S "$monitor" ]; then
    sleep 30
    capture_monitor arm-boot "$monitor" || true
    printf 'sendkey shift\nsendkey spc\n' | socat - UNIX-CONNECT:"$monitor" >/dev/null 2>&1 || true
    sleep 8
    capture_monitor arm-greeter "$monitor" || true
    sleep 15
    capture_monitor arm-desktop "$monitor" || true
fi

echo "Touch $evidence/continue when done inspecting the GTK window."
wait "$boot_pid" || {
    echo "Boot script exit non-zero — inspect $evidence"
    exit 1
}

echo "Visual ARM proof saved under $PROOF (arm-*.png)"
