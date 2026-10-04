#!/bin/bash
# One measurement of an ISOLATED second compositor.
#
# WHY THIS EXISTS
#
# On a cloud MoOS machine the compositor is the owner's only screen, and Mo PC Remote is how they
# see it. Every question worth asking about that screen — what does a smaller desktop cost, does
# a frame-rate cap help, can another backend stream — used to need the live session: a restart
# that closes the owner's windows, or a second ScreenCast whose consent dialog nobody can answer.
#
# This starts a second `kwin_wayland --virtual` that the owner never sees: its own Wayland socket
# (`wayland-rig`, never `wayland-0`), its own HOME and config (copies of the live kwinrc and
# output configuration, so the effect set is the real one), and NO session bus, so it cannot
# take a D-Bus name from the real compositor. Only PipeWire is shared, which is what lets a plain
# client read the rig's ScreenCast node with no portal and no dialog. A busy window is the
# workload; the consumer is Mo PC Remote's own chain to the encoder.
#
#   rig.sh <compose: O2|O2ES|Q> <stream: off|60|30> [WxH output] [seconds] [WxH encode] [WxH window]
#
#   stream 60 / 30   what the consumer asks the compositor for as max-framerate
#   RIG_RATE=        maxrate (the videorate element alone) | helper (the repository helper's own
#                    FramePacer on top of it) | caps (fixed-rate caps) | none
#   RIG_FPS=         the frame rate the viewer asked for (default 30)
#   RIG_KWIN_ENV=    "A=1 B=2", added to the compositor's environment only
#
# It prints one RESULT line: CPU of the compositor, the workload and the encode path over the
# window, as percent of one core read from each unit's cgroup, and frames delivered and encoded.
# It costs both cores for as long as it runs: say so before running it on an owner's machine.
#
# Read with it on the Oracle A1 on 2026-10-04 (2 vCPU, llvmpipe), docs/DEVELOPMENT_PLAN.md P5.5:
# a QPainter compositor draws the same window for 12% of a core against OpenGL's 72% and offers
# no ScreenCast node; max-framerate=30 saves the compositor nothing and delivers 25 frames a
# second; a 1280x720 desktop gives a quarter more frames for a third less encode work.
set -u
[ $# -ge 2 ] || { sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
COMPOSE=$1; STREAM=$2; OUT=${3:-1920x1080}; SECS=${4:-15}; ENC=${5:-$OUT}; WIN=${6:-1100x720}
case "$COMPOSE" in O2|O2ES|Q) ;; *) echo "RIG: compose is O2, O2ES or Q"; exit 2 ;; esac
case "$STREAM" in off|60|30) ;; *) echo "RIG: stream is off, 60 or 30"; exit 2 ;; esac
for size in "$OUT" "$ENC" "$WIN"; do
    [[ "$size" =~ ^[0-9]{3,4}x[0-9]{3,4}$ ]] || { echo "RIG: a size is WIDTHxHEIGHT, not $size"; exit 2; }
done
[[ "$SECS" =~ ^[0-9]{1,3}$ ]] && [ "$SECS" -ge 6 ] || { echo "RIG: at least 6 seconds"; exit 2; }
W=${OUT%x*}; H=${OUT#*x}
HERE="$(cd "$(dirname "$0")" && pwd)"
R="${XDG_CACHE_HOME:-$HOME/.cache}/moos-compositor-rig"; RT="/run/user/$(id -u)"
SOCKET=wayland-rig
U="moos-kwin-rig-$$"
stop_all() {
    systemctl --user stop "$U-consumer.service" "$U-client.service" "$U.service" 2>/dev/null
    systemctl --user reset-failed "$U*" 2>/dev/null
    rm -f "$RT/$SOCKET" "$RT/$SOCKET.lock"
}
trap stop_all EXIT
rm -rf "$R"; mkdir -p "$R/home/.config" "$R/home/.cache" "$R/home/.local/share"
# The live session's effect set and stored output modes, as COPIES: the rig never writes the originals.
cp "$HOME/.config/kwinrc" "$R/home/.config/kwinrc" 2>/dev/null
cp "$HOME/.config/kwinoutputconfig.json" "$R/home/.config/" 2>/dev/null
rm -f "$RT/$SOCKET" "$RT/$SOCKET.lock"
ISOLATED="-E HOME=$R/home -E XDG_CONFIG_HOME=$R/home/.config -E XDG_CACHE_HOME=$R/home/.cache -E XDG_DATA_HOME=$R/home/.local/share -E DBUS_SESSION_BUS_ADDRESS=unix:path=$R/no-session-bus -E LIBGL_ALWAYS_SOFTWARE=1 -E GALLIUM_DRIVER=llvmpipe -E LP_NUM_THREADS=2 -E QT_QUICK_BACKEND=software -E QT_FORCE_STDERR_LOGGING=1"
KENV=""; for kv in ${RIG_KWIN_ENV:-}; do KENV="$KENV -E $kv"; done
# shellcheck disable=SC2086
systemd-run --user --quiet --unit="$U" --collect $ISOLATED -E KWIN_COMPOSE="$COMPOSE" -E KWIN_WAYLAND_NO_PERMISSION_CHECKS=1 $KENV \
    kwin_wayland --virtual --width "$W" --height "$H" --socket "$SOCKET" --no-lockscreen --no-global-shortcuts --no-kactivities
for _ in $(seq 1 40); do [ -S "$RT/$SOCKET" ] && break; sleep 0.25; done
[ -S "$RT/$SOCKET" ] || { echo "RIG: the compositor did not create its socket"; exit 1; }
CAST=""; [ "$STREAM" = off ] || CAST=Virtual-0
# shellcheck disable=SC2086
systemd-run --user --quiet --unit="$U-client" --collect $ISOLATED -E WAYLAND_DISPLAY="$SOCKET" -E QT_QPA_PLATFORM=wayland \
    -E RIG_CAST_OUTPUT="$CAST" -E RIG_WINDOW="$WIN" -E RIG_SECONDS=$((SECS + 25)) -E PYTHONDONTWRITEBYTECODE=1 \
    python3 -s "$HERE/workload.py"
NODE=""
for _ in $(seq 1 60); do
    sleep 0.25
    journalctl --user -u "$U-client" --no-pager -o cat 2>/dev/null | grep -q "RIG client up" || continue
    [ -z "$CAST" ] && break
    NODE=$(journalctl --user -u "$U-client" --no-pager -o cat 2>/dev/null | sed -n 's/.*RIG node \([0-9]*\).*/\1/p' | tail -1)
    [ -n "$NODE" ] && break
done
systemctl --user is-active --quiet "$U-client.service" || { echo "RIG: the workload is not running"; exit 1; }
if [ -n "$CAST" ]; then
    [ -n "$NODE" ] || { echo "RESULT $COMPOSE out=$OUT stream=$STREAM | NO ScreenCast node from this compositor"; exit 0; }
    CAP=""; [ "$STREAM" = 30 ] && CAP=30
    systemd-run --user --quiet --unit="$U-consumer" --collect -E RIG_MAX_FRAMERATE="$CAP" -E RIG_OUT="$ENC" \
        -E RIG_RATE="${RIG_RATE:-helper}" -E RIG_FPS="${RIG_FPS:-30}" -E PYTHONDONTWRITEBYTECODE=1 -E PYTHONUNBUFFERED=1 \
        python3 -s "$HERE/consumer.py" "$NODE" "$SECS"
    for _ in $(seq 1 80); do journalctl --user -u "$U-consumer" --no-pager -o cat 2>/dev/null | grep -q "RIG consumer measuring" && break; sleep 0.25; done
else
    sleep 3
fi
cpu() { awk '/^usage_usec/{print $2}' "/sys/fs/cgroup$(systemctl --user show "$1" -p ControlGroup --value)/cpu.stat" 2>/dev/null || echo 0; }
k0=$(cpu "$U.service"); c0=$(cpu "$U-client.service"); e0=0; [ -n "$CAST" ] && e0=$(cpu "$U-consumer.service")
D=$((SECS - 3)); sleep "$D"
k1=$(cpu "$U.service"); c1=$(cpu "$U-client.service"); e1=0; [ -n "$CAST" ] && e1=$(cpu "$U-consumer.service")
FR=""; NEG=""
if [ -n "$CAST" ]; then
    for _ in $(seq 1 40); do FR=$(journalctl --user -u "$U-consumer" --no-pager -o cat 2>/dev/null | grep -a "RIG frames" | tail -1); [ -n "$FR" ] && break; sleep 0.25; done
    NEG=$(journalctl --user -u "$U-consumer" --no-pager -o cat 2>/dev/null | grep -a "negotiated" | tail -1 | sed -n 's/.*\(max-framerate=(fraction)[0-9/]*\).*/\1/p')
fi
printf "RESULT %-4s out=%-9s win=%-9s stream=%-3s enc=%-9s rate=%s fps=%s %s| compositor %5.1f%% | workload %5.1f%% | encode path %5.1f%% | %s %s\n" \
    "$COMPOSE" "$OUT" "$WIN" "$STREAM" "$ENC" "${RIG_RATE:-helper}" "${RIG_FPS:-30}" "${RIG_KWIN_ENV:+[$RIG_KWIN_ENV] }" \
    "$(awk "BEGIN{print ($k1-$k0)/$D/10000}")" "$(awk "BEGIN{print ($c1-$c0)/$D/10000}")" "$(awk "BEGIN{print ($e1-$e0)/$D/10000}")" \
    "$(echo "$FR" | sed 's/RIG frames delivered by the compositor: /delivered /; s/ over.*//')" "$NEG"
