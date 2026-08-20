#!/usr/bin/env bash
# Boot the exact final MoOS live ISO read-only and prove its runtime through QGA.
set -euo pipefail

iso="${1:-}"
expected_ref="${2:-}"
evidence="${3:-}"

[ -f "$iso" ] || { echo "ISO BOOT FATAL: final ISO is missing: $iso" >&2; exit 2; }
[[ "$expected_ref" =~ ^ghcr\.io/moalfarras-sys/(moos|moos-nvidia)@sha256:[0-9a-f]{64}$ ]] \
    || { echo "ISO BOOT FATAL: expected image ref is not an exact official digest" >&2; exit 2; }
[ -n "$evidence" ] || { echo "ISO BOOT FATAL: evidence directory is required" >&2; exit 2; }
for tool in qemu-system-x86_64 sha256sum socat python3; do
    command -v "$tool" >/dev/null \
        || { echo "ISO BOOT FATAL: missing host tool: $tool" >&2; exit 2; }
done

iso="$(realpath "$iso")"
install -d -m0755 "$evidence"
evidence="$(realpath "$evidence")"
work="$(mktemp -d /tmp/moos-live-iso-boot.XXXXXX)"
qemu_pid=""

cleanup() {
    local rc=$?
    trap - EXIT INT TERM
    if [ -n "$qemu_pid" ] && kill -0 "$qemu_pid" 2>/dev/null; then
        kill "$qemu_pid" 2>/dev/null || true
        wait "$qemu_pid" 2>/dev/null || true
    fi
    if [ "$rc" -ne 0 ]; then
        echo "=== QEMU log (tail) ===" >&2
        tail -80 "$evidence/qemu.log" 2>/dev/null >&2 || true
        echo "=== guest serial (tail) ===" >&2
        tail -80 "$evidence/serial.log" 2>/dev/null >&2 || true
    fi
    rm -rf -- "$work"
    exit "$rc"
}
trap cleanup EXIT INT TERM

ovmf_code=""
ovmf_vars=""
while IFS= read -r candidate; do
    paired="${candidate/OVMF_CODE/OVMF_VARS}"
    if [ -f "$paired" ]; then
        ovmf_code="$candidate"
        ovmf_vars="$paired"
        break
    fi
done < <(find /usr/share -type f -name 'OVMF_CODE*.fd' -print 2>/dev/null | sort)
[ -n "$ovmf_code" ] && [ -n "$ovmf_vars" ] \
    || { echo "ISO BOOT FATAL: no matching OVMF CODE/VARS firmware pair" >&2; exit 1; }
cp "$ovmf_vars" "$work/vars.fd"

before_sha="$(sha256sum "$iso" | awk '{print $1}')"
printf 'iso=%s\nsha256=%s\nimage=%s\novmf=%s\n' \
    "$iso" "$before_sha" "$expected_ref" "$ovmf_code" > "$evidence/manifest.txt"

qga="$work/qga.sock"
monitor="$work/monitor.sock"
qemu-system-x86_64 \
    -machine q35,accel=tcg -cpu Haswell -m 4096 -smp 2 \
    -drive "if=pflash,format=raw,readonly=on,file=$ovmf_code" \
    -drive "if=pflash,format=raw,file=$work/vars.fd" \
    -drive "file=$iso,media=cdrom,format=raw,readonly=on" \
    -boot order=d \
    -device virtio-gpu-pci \
    -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
    -device virtio-serial-pci \
    -chardev "socket,path=$qga,server=on,wait=off,id=qga0" \
    -device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0 \
    -monitor "unix:$monitor,server=on,wait=off" \
    -serial "file:$evidence/serial.log" \
    -display none >"$evidence/qemu.log" 2>&1 &
qemu_pid=$!

# The ISO intentionally has no ttyS0 karg. QGA observes the exact final ISO
# without editing GRUB, the kernel command line, or a byte of the artifact.
python3 - "$qga" "$qemu_pid" "$expected_ref" "$evidence/runtime.txt" <<'PY'
import base64
import json
import os
import socket
import sys
import time

qga, qemu_pid, expected, output_path = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]


def qemu_alive():
    try:
        os.kill(qemu_pid, 0)
        return True
    except OSError:
        return False


def request(payload, timeout=8.0):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(qga)
        client.sendall(json.dumps(payload, separators=(",", ":")).encode() + b"\n")
        buffer = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            chunk = client.recv(65536)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                raw, buffer = buffer.split(b"\n", 1)
                if not raw.strip():
                    continue
                reply = json.loads(raw.lstrip(b"\xff"))
                if "error" in reply:
                    raise RuntimeError(f"QGA error: {reply['error']}")
                if "return" in reply:
                    return reply["return"]
    raise RuntimeError("QGA returned no response")


deadline = time.monotonic() + 900
last_error = "guest agent has not answered"
while time.monotonic() < deadline:
    if not qemu_alive():
        raise SystemExit("ISO BOOT FATAL: QEMU exited before QGA became ready")
    try:
        request({"execute": "guest-ping"})
        break
    except (OSError, ValueError, RuntimeError) as error:
        last_error = str(error)
        time.sleep(5)
else:
    raise SystemExit(f"ISO BOOT FATAL: QGA did not become ready in 900s: {last_error}")

runtime_gate = r'''
set -euo pipefail
expected="$1"
grep -qw rd.live.image /proc/cmdline
. /etc/os-release
[ "${ID:-}" = moos ]
[ "${NAME:-}" = MoOS ]
[ "$(uname -m)" = x86_64 ]
systemctl is-active graphical.target display-manager.service NetworkManager.service
getent passwd liveuser
pgrep -u liveuser -x kwin_wayland
pgrep -u liveuser -x plasmashell
test -x /usr/bin/moos-installer
offline_ref="$(tr -d '\r\n' < /usr/lib/moos/install-imageref)"
podman image exists "$offline_ref"
actual_digest="$(podman image inspect --format '{{.Digest}}' "$offline_ref")"
[ "$actual_digest" = "${expected##*@}" ]
failed="$(systemctl --failed --no-legend --plain)"
[ -z "$failed" ]
printf 'boot=live\nidentity=%s\narch=%s\ngraphical=active\ndisplay-manager=active\nnetwork=active\nuser=liveuser\nkwin=active\nplasmashell=active\ninstaller=present\noffline-ref=%s\noffline-digest=%s\nfailed-units=0\n' \
    "$PRETTY_NAME" "$(uname -m)" "$offline_ref" "$actual_digest"
'''
started = request({
    "execute": "guest-exec",
    "arguments": {
        "path": "/usr/bin/bash",
        "arg": ["-lc", runtime_gate, "--", expected],
        "capture-output": True,
    },
})
pid = started["pid"]
deadline = time.monotonic() + 180
while time.monotonic() < deadline:
    status = request({"execute": "guest-exec-status", "arguments": {"pid": pid}})
    if status.get("exited"):
        stdout = base64.b64decode(status.get("out-data", "")).decode(errors="replace")
        stderr = base64.b64decode(status.get("err-data", "")).decode(errors="replace")
        with open(output_path, "w", encoding="utf-8") as stream:
            stream.write(stdout)
            if stderr:
                stream.write("\n=== stderr ===\n" + stderr)
        if status.get("exitcode") != 0:
            raise SystemExit(
                f"ISO BOOT FATAL: runtime gate exited {status.get('exitcode')}: {stderr or stdout}"
            )
        print(stdout, end="")
        break
    time.sleep(2)
else:
    raise SystemExit("ISO BOOT FATAL: QGA runtime gate timed out")
PY

printf 'screendump %s\n' "$evidence/graphical.ppm" \
    | socat - "UNIX-CONNECT:$monitor" >/dev/null
[ -s "$evidence/graphical.ppm" ] \
    || { echo "ISO BOOT FATAL: graphical screendump is empty" >&2; exit 1; }
if command -v magick >/dev/null; then
    image_tool="magick"
elif command -v convert >/dev/null; then
    image_tool="convert"
else
    echo "ISO BOOT FATAL: ImageMagick is unavailable" >&2
    exit 2
fi
"$image_tool" "$evidence/graphical.ppm" "$evidence/graphical.png"
rm -f "$evidence/graphical.ppm"
stddev="$("$image_tool" "$evidence/graphical.png" -colorspace gray \
    -format '%[fx:standard_deviation]' info:)"
python3 - "$stddev" <<'PY'
import sys
value = float(sys.argv[1])
if value < 0.01:
    raise SystemExit(f"ISO BOOT FATAL: graphical evidence is blank/flat (stddev={value})")
print(f"graphical screenshot stddev={value:.6f}")
PY

# guest-shutdown intentionally sends no reply on success. QEMU process exit is
# the proof that the exact live system completed a clean poweroff path.
python3 - "$qga" <<'PY'
import json
import socket
import sys
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.settimeout(5)
    client.connect(sys.argv[1])
    payload = {"execute": "guest-shutdown", "arguments": {"mode": "powerdown"}}
    client.sendall(json.dumps(payload, separators=(",", ":")).encode() + b"\n")
PY

for _ in $(seq 1 120); do
    kill -0 "$qemu_pid" 2>/dev/null || break
    sleep 1
done
if kill -0 "$qemu_pid" 2>/dev/null; then
    echo "ISO BOOT FATAL: guest did not power off within 120s" >&2
    exit 1
fi
wait "$qemu_pid"
qemu_pid=""

after_sha="$(sha256sum "$iso" | awk '{print $1}')"
[ "$after_sha" = "$before_sha" ] \
    || { echo "ISO BOOT FATAL: the final ISO changed during its boot proof" >&2; exit 1; }
printf 'shutdown=clean\nfinal-sha256=%s\n' "$after_sha" >> "$evidence/runtime.txt"
echo "ISO BOOT PASS: UEFI live desktop, installer, exact offline image, visual frame, clean shutdown"
