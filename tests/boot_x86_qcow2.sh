#!/usr/bin/env bash
# Boot the exact x86 QCOW2 release through UEFI on a disposable overlay, prove
# the installed MoOS runtime through QGA, reboot it, and power it off cleanly.
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "usage: $0 IMAGE.qcow2 ghcr.io/moalfarras-sys/<edition>@sha256:... [EVIDENCE_DIR]" >&2
    exit 2
fi

qcow="$(realpath "$1")"
expected_ref="$2"
evidence="$(realpath -m "${3:-x86-qcow2-boot-proof}")"
[[ "$expected_ref" =~ ^ghcr\.io/moalfarras-sys/(moos|moos-nvidia|moos-cloud)@sha256:[0-9a-f]{64}$ ]] || {
    echo "X86 QCOW2 FATAL: expected image is not an exact official desktop digest" >&2
    exit 2
}
[ -f "$qcow" ] || { echo "X86 QCOW2 FATAL: missing QCOW2: $qcow" >&2; exit 2; }
for tool in qemu-img qemu-system-x86_64 sha256sum python3; do
    command -v "$tool" >/dev/null || {
        echo "X86 QCOW2 FATAL: required host tool is missing: $tool" >&2
        exit 2
    }
done
if command -v magick >/dev/null; then
    image_tool="magick"
elif command -v convert >/dev/null; then
    image_tool="convert"
else
    echo "X86 QCOW2 FATAL: ImageMagick is unavailable" >&2
    exit 2
fi

install -d -m0755 "$evidence"
base_tmp="${RUNNER_TEMP:-/var/tmp}"
work="$(mktemp -d -p "$base_tmp" moos-x86-qcow2-boot.XXXXXX)"
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
        tail -100 "$evidence/qemu.log" 2>/dev/null >&2 || true
        echo "=== serial log (tail) ===" >&2
        tail -100 "$evidence/serial.log" 2>/dev/null >&2 || true
    fi
    case "$work" in
        "$base_tmp"/moos-x86-qcow2-boot.*) rm -rf -- "$work" ;;
    esac
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
[ -n "$ovmf_code" ] && [ -n "$ovmf_vars" ] || {
    echo "X86 QCOW2 FATAL: no matching OVMF CODE/VARS firmware pair" >&2
    exit 1
}

qemu-img check "$qcow" | tee "$evidence/qcow2-check.txt"
before_sha="$(sha256sum "$qcow" | awk '{print $1}')"
printf 'qcow2=%s\nsha256=%s\nimage=%s\novmf=%s\n' \
    "$qcow" "$before_sha" "$expected_ref" "$ovmf_code" > "$evidence/manifest.txt"
qemu-img create -q -f qcow2 -F qcow2 -b "$qcow" "$work/overlay.qcow2"
cp "$ovmf_vars" "$work/vars.fd"

qga="$work/qga.sock"
monitor="$work/monitor.sock"
qemu-system-x86_64 \
    -machine q35,accel=tcg -cpu Haswell -m 4096 -smp 2 \
    -drive "if=pflash,format=raw,readonly=on,file=$ovmf_code" \
    -drive "if=pflash,format=raw,file=$work/vars.fd" \
    -drive "file=$work/overlay.qcow2,format=qcow2,if=virtio,cache=unsafe" \
    -device virtio-gpu-pci \
    -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
    -device virtio-serial-pci \
    -chardev "socket,path=$qga,server=on,wait=off,id=qga0" \
    -device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0 \
    -monitor "unix:$monitor,server=on,wait=off" \
    -serial "file:$evidence/serial.log" \
    -display none >"$evidence/qemu.log" 2>&1 &
qemu_pid=$!

python3 - "$qga" "$monitor" "$qemu_pid" "$expected_ref" "$evidence" <<'PY'
import base64
import json
import os
from pathlib import Path
import socket
import sys
import time

qga, monitor = sys.argv[1], sys.argv[2]
qemu_pid, expected, evidence = int(sys.argv[3]), sys.argv[4], Path(sys.argv[5])
sync_serial = 0


def qemu_alive():
    try:
        os.kill(qemu_pid, 0)
        return True
    except OSError:
        return False


def read_reply(client, timeout):
    buffer = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        chunk = client.recv(65536)
        if not chunk:
            break
        buffer += chunk
        while b"\n" in buffer:
            raw, buffer = buffer.split(b"\n", 1)
            if not raw.strip(b"\xff \t\r"):
                continue
            reply = json.loads(raw.lstrip(b"\xff"))
            if "error" in reply:
                raise RuntimeError(f"QGA error: {reply['error']}")
            if "return" in reply:
                return reply["return"]
    raise RuntimeError("QGA returned no response")


def sync_client(client, timeout):
    global sync_serial
    sync_serial += 1
    payload = {
        "execute": "guest-sync-delimited",
        "arguments": {"id": sync_serial},
    }
    client.sendall(json.dumps(payload, separators=(",", ":")).encode() + b"\n")
    buffer = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        buffer += client.recv(65536)
        if b"\xff" not in buffer:
            continue
        current = buffer.rsplit(b"\xff", 1)[1]
        if b"\n" not in current:
            continue
        raw = current.split(b"\n", 1)[0]
        reply = json.loads(raw)
        if reply.get("return") != sync_serial:
            raise RuntimeError("QGA sync returned the wrong id")
        return
    raise RuntimeError("QGA sync timed out")


def connect_synced(timeout=10.0):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.settimeout(timeout)
        client.connect(qga)
        sync_client(client, timeout)
        return client
    except Exception:
        client.close()
        raise


def request(payload, timeout=10.0):
    with connect_synced(timeout) as client:
        client.sendall(json.dumps(payload, separators=(",", ":")).encode() + b"\n")
        return read_reply(client, timeout)


def assert_qga_contract():
    info = request({"execute": "guest-info"})
    commands = {
        item.get("name"): item.get("enabled")
        for item in info.get("supported_commands", [])
        if isinstance(item, dict)
    }
    for required in ("guest-exec", "guest-exec-status", "guest-shutdown"):
        if commands.get(required) is not True:
            raise RuntimeError(f"QGA command is unavailable: {required}")


def guest_exec(script, args=(), timeout=180):
    started = request({
        "execute": "guest-exec",
        "arguments": {
            "path": "/usr/bin/bash",
            "arg": ["-lc", script, "--", *args],
            "capture-output": True,
        },
    })
    pid = started["pid"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = request({"execute": "guest-exec-status", "arguments": {"pid": pid}})
        if status.get("exited"):
            stdout = base64.b64decode(status.get("out-data", "")).decode(errors="replace")
            stderr = base64.b64decode(status.get("err-data", "")).decode(errors="replace")
            if status.get("exitcode") != 0:
                raise RuntimeError(
                    f"runtime gate exited {status.get('exitcode')}: {stderr or stdout}"
                )
            return stdout, stderr
        time.sleep(2)
    raise RuntimeError("guest command timed out")


def boot_id_of(output):
    return next(
        (line.split("=", 1)[1] for line in output.splitlines() if line.startswith("boot_id=")),
        "",
    )


def wait_for_runtime(script, previous_id="", timeout=900):
    deadline = time.monotonic() + timeout
    last_error = "QGA has not answered"
    while time.monotonic() < deadline:
        if not qemu_alive():
            raise SystemExit("X86 QCOW2 FATAL: QEMU exited before the runtime gate passed")
        try:
            request({"execute": "guest-ping"})
            assert_qga_contract()
            stdout, stderr = guest_exec(script, (expected,))
            boot_id = boot_id_of(stdout)
            if boot_id and boot_id != previous_id:
                return stdout, stderr, boot_id
            last_error = "guest still reports the previous boot ID"
        except (OSError, ValueError, RuntimeError, KeyError) as error:
            last_error = str(error)
        time.sleep(5)
    raise SystemExit(f"X86 QCOW2 FATAL: runtime did not become ready: {last_error}")


def send_shutdown(mode):
    # QGA intentionally sends no reply for guest-shutdown on success.
    with connect_synced(5) as client:
        payload = {"execute": "guest-shutdown", "arguments": {"mode": mode}}
        client.sendall(json.dumps(payload, separators=(",", ":")).encode() + b"\n")


def screendump(path):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(5)
                client.connect(monitor)
                client.recv(4096)
                client.sendall(f"screendump {path}\n".encode())
                client.recv(4096)
            if path.is_file() and path.stat().st_size:
                return
        except (OSError, socket.timeout):
            pass
        time.sleep(0.5)
    raise SystemExit("X86 QCOW2 FATAL: graphical screendump was not produced")


runtime_gate = r'''
set -euo pipefail
expected="$1"
hostroot=/proc/1/root
system_bus="unix:path=${hostroot}/run/dbus/system_bus_socket"
bus_data() {
    python3 -c 'import json,sys
value=json.load(sys.stdin).get("data", "")
print(value[0] if isinstance(value, list) and value else value)'
}
manager_property() {
    busctl --json=short --address="$system_bus" get-property \
        org.freedesktop.systemd1 /org/freedesktop/systemd1 \
        org.freedesktop.systemd1.Manager "$1" | bus_data
}
unit_property() {
    local unit="$1" property="$2" path
    path="$(busctl --json=short --address="$system_bus" call \
        org.freedesktop.systemd1 /org/freedesktop/systemd1 \
        org.freedesktop.systemd1.Manager GetUnit s "$unit" | bus_data)" || return 1
    busctl --json=short --address="$system_bus" get-property \
        org.freedesktop.systemd1 "$path" org.freedesktop.systemd1.Unit "$property" | bus_data
}
deployed_origin() {
    local origins=()
    shopt -s nullglob
    origins=("$hostroot"/ostree/deploy/*/deploy/*.origin)
    shopt -u nullglob
    [ "${#origins[@]}" -eq 1 ] || return 1
    sed -n 's/^container-image-reference=//p' "${origins[0]}"
}
gate_fail() {
    printf 'runtime-gate=%s\n' "$1" >&2
    # QGA can answer before the installed userspace is ready.  Preserve a small
    # snapshot from the *last* retry so a timed-out release proof distinguishes
    # an early/initramfs answer from a fully booted system with a bad contract.
    printf 'system-state=%s\n' "$(manager_property SystemState 2>/dev/null || true)" >&2
    printf 'root-mount=%s\n' "$(findmnt -n -o SOURCE,FSTYPE / 2>/dev/null || true)" >&2
    printf 'booted-origin=%s\n' "$(deployed_origin 2>/dev/null || true)" >&2
    return 1
}
[ -S "$hostroot/run/dbus/system_bus_socket" ] || gate_fail system-bus
. "$hostroot/etc/os-release"
[ "${ID:-}" = moos ] || gate_fail identity-id
[ "${NAME:-}" = MoOS ] || gate_fail identity-name
[ "$(uname -m)" = x86_64 ] || gate_fail architecture
[ -e "$hostroot/run/ostree-booted" ] || gate_fail ostree-booted
grep -qw rd.live.image /proc/cmdline && gate_fail unexpected-live-boot
[ -e "$hostroot/etc/moos-firstboot-done" ] || gate_fail firstboot-stamp
for unit in graphical.target display-manager.service plasmalogin.service NetworkManager.service; do
    [ "$(unit_property "$unit" ActiveState 2>/dev/null || true)" = active ] \
        || gate_fail "required-system-service-${unit}"
done
[ "$(unit_property display-manager.service Id 2>/dev/null || true)" = plasmalogin.service ] \
    || gate_fail display-manager-identity
grep -q '^mo:' "$hostroot/etc/passwd" || gate_fail provisioned-user
account_path="$(busctl --address="$system_bus" call org.freedesktop.Accounts \
    /org/freedesktop/Accounts org.freedesktop.Accounts FindUserByName s mo)"
[[ "$account_path" == *"/org/freedesktop/Accounts/User"* ]] || gate_fail accounts-service-user
compgen -G "$hostroot/dev/dri/card*" >/dev/null || gate_fail drm-device
login_uid="$(awk -F: '$1 == "plasmalogin" {print $3}' "$hostroot/etc/passwd")"
[ -n "$login_uid" ] || gate_fail greeter-user
pgrep -u "$login_uid" -x kwin_wayland >/dev/null || gate_fail greeter-kwin
ipv4="$(ip -4 -o addr show scope global)"
[ -n "$ipv4" ] || gate_fail network-address
routes="$(ip -4 route show default)"
[[ "$routes" == default\ * ]] || gate_fail network-default-route
for helper in moos-settings moos-update moos-rollback moos-store moai moplayer mo-pc-remote; do
    [ -x "$hostroot/usr/bin/$helper" ] || gate_fail "missing-command-${helper}"
done
origin="$(deployed_origin || true)"
origin_digest="${origin##*@}"
[ "$origin" = "ostree-image-signed:docker://${expected}" ] || gate_fail signed-origin
[ "$origin_digest" = "${expected##*@}" ] || gate_fail origin-digest
python3 - "$hostroot/etc/containers/policy.json" <<'INNER'
import json
import sys
with open(sys.argv[1], encoding='utf-8') as source:
    policy = json.load(source)
entry = policy['transports']['docker']['ghcr.io/moalfarras-sys']
assert len(entry) == 1 and entry[0]['type'] == 'sigstoreSigned'
assert entry[0]['keyPath'] == '/etc/pki/containers/moos.pub'
assert entry[0]['signedIdentity'] == {'type': 'matchRepository'}
INNER
[ "$(manager_property NFailedUnits 2>/dev/null || true)" = 0 ] || gate_fail failed-system-unit
printf 'boot_id=%s\nidentity=%s\narch=%s\norigin=%s\norigin-digest=%s\ngraphical=active\ndisplay-manager=plasmalogin\ngreeter-kwin=active\ndrm=present\nnetwork=active\nqga=active\nfirst-party-commands=7\nfailed-units=0\n' \
    "$(cat /proc/sys/kernel/random/boot_id)" "$PRETTY_NAME" "$(uname -m)" "$origin" "$origin_digest"
'''

first, first_err, first_id = wait_for_runtime(runtime_gate)
(evidence / "runtime-first-boot.txt").write_text(
    first + (("\n=== stderr ===\n" + first_err) if first_err else ""), encoding="utf-8"
)
print(first, end="")
screendump(evidence / "graphical-first-boot.ppm")

send_shutdown("reboot")
second, second_err, second_id = wait_for_runtime(runtime_gate, first_id)
(evidence / "runtime-second-boot.txt").write_text(
    second + (("\n=== stderr ===\n" + second_err) if second_err else ""), encoding="utf-8"
)
print(second, end="")
screendump(evidence / "graphical-second-boot.ppm")
send_shutdown("powerdown")
PY

for _ in $(seq 1 180); do
    kill -0 "$qemu_pid" 2>/dev/null || break
    sleep 1
done
if kill -0 "$qemu_pid" 2>/dev/null; then
    echo "X86 QCOW2 FATAL: guest did not power off within 180s" >&2
    exit 1
fi
wait "$qemu_pid"
qemu_pid=""

python3 - "$evidence/serial.log" "$evidence/serial.plain.log" <<'PY'
import pathlib
import re
import sys
source = pathlib.Path(sys.argv[1]).read_bytes()
ansi = re.compile(rb"\x1b(?:\[[0-?]*[ -/]*[@-~]|[@-_])")
pathlib.Path(sys.argv[2]).write_bytes(ansi.sub(b"", source))
PY
fatal='Kernel panic|Entering emergency mode|You are in emergency mode|Cannot open root device|Failed to mount /sysroot|ostree-prepare-root: .*(fail|error)'
if grep -Eqi "$fatal" "$evidence/serial.plain.log"; then
    echo "X86 QCOW2 FATAL: fatal marker appeared in the serial log" >&2
    exit 1
fi

qemu-img check "$work/overlay.qcow2" | tee "$evidence/overlay-check.txt"
for frame in graphical-first-boot graphical-second-boot; do
    [ -s "$evidence/${frame}.ppm" ] || { echo "X86 QCOW2 FATAL: ${frame} is empty" >&2; exit 1; }
    "$image_tool" "$evidence/${frame}.ppm" "$evidence/${frame}.png"
    stddev="$("$image_tool" "$evidence/${frame}.png" -colorspace gray -format '%[fx:standard_deviation]' info:)"
    python3 - "$frame" "$stddev" <<'PY'
import sys
value = float(sys.argv[2])
if value < 0.01:
    raise SystemExit(f"X86 QCOW2 FATAL: {sys.argv[1]} is blank/flat (stddev={value})")
print(f"{sys.argv[1]} screenshot stddev={value:.6f}")
PY
done

after_sha="$(sha256sum "$qcow" | awk '{print $1}')"
[ "$after_sha" = "$before_sha" ] || {
    echo "X86 QCOW2 FATAL: publishable QCOW2 changed during boot proof" >&2
    exit 1
}
printf 'shutdown=clean\nfinal-sha256=%s\n' "$after_sha" >> "$evidence/runtime-second-boot.txt"
echo "X86 QCOW2 BOOT OK: pristine artifact, UEFI, signed root, graphical greeter, commands, network, reboot and poweroff"
