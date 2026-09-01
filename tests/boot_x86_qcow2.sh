#!/usr/bin/env bash
# Boot the exact x86 QCOW2 release through UEFI on a disposable overlay, prove
# the installed MoOS runtime through ephemeral-key SSH, reboot it through QGA,
# and power it off cleanly. QGA is intentionally not a runtime authority: its
# service mount namespace may not expose the booted OSTree userspace.
set -euo pipefail

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "usage: $0 IMAGE.qcow2 ghcr.io/moalfarras-sys/<edition>@sha256:... EVIDENCE_DIR [SSH_PRIVATE_KEY]" >&2
    exit 2
fi

qcow="$(realpath "$1")"
expected_ref="$2"
evidence="$(realpath -m "${3:-x86-qcow2-boot-proof}")"
ssh_key="$(realpath "${4:-${MOOS_X86_SSH_KEY:-}}" 2>/dev/null || true)"
[[ "$expected_ref" =~ ^ghcr\.io/moalfarras-sys/(moos|moos-nvidia|moos-cloud)@sha256:[0-9a-f]{64}$ ]] || {
    echo "X86 QCOW2 FATAL: expected image is not an exact official desktop digest" >&2
    exit 2
}
[ -f "$qcow" ] || { echo "X86 QCOW2 FATAL: missing QCOW2: $qcow" >&2; exit 2; }
[ -f "$ssh_key" ] || { echo "X86 QCOW2 FATAL: missing CI SSH private key" >&2; exit 2; }
[ "$(stat -c '%a' "$ssh_key")" = 600 ] || {
    echo "X86 QCOW2 FATAL: CI SSH private key must have mode 0600" >&2
    exit 2
}
for tool in qemu-img qemu-system-x86_64 sha256sum python3 ssh; do
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

# Reserve a loopback port only long enough to choose it. Each Actions job has a
# dedicated runner; QEMU's bind below is therefore the sole subsequent owner.
ssh_port="$(python3 - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"

qga="$work/qga.sock"
monitor="$work/monitor.sock"
qemu-system-x86_64 \
    -machine q35,accel=tcg -cpu Haswell -m 4096 -smp 2 \
    -drive "if=pflash,format=raw,readonly=on,file=$ovmf_code" \
    -drive "if=pflash,format=raw,file=$work/vars.fd" \
    -drive "file=$work/overlay.qcow2,format=qcow2,if=virtio,cache=unsafe" \
    -vga virtio \
    -netdev "user,id=n0,hostfwd=tcp:127.0.0.1:${ssh_port}-:22" \
    -device virtio-net-pci,netdev=n0 \
    -device virtio-serial-pci \
    -chardev "socket,path=$qga,server=on,wait=off,id=qga0" \
    -device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0 \
    -monitor "unix:$monitor,server=on,wait=off" \
    -serial "file:$evidence/serial.log" \
    -display none >"$evidence/qemu.log" 2>&1 &
qemu_pid=$!

python3 - "$qga" "$monitor" "$qemu_pid" "$expected_ref" "$evidence" \
    "$ssh_key" "$ssh_port" <<'PY'
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

qga, monitor = sys.argv[1], sys.argv[2]
qemu_pid, expected, evidence = int(sys.argv[3]), sys.argv[4], Path(sys.argv[5])
ssh_key, ssh_port = sys.argv[6], sys.argv[7]
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
    for required in ("guest-shutdown",):
        if commands.get(required) is not True:
            raise RuntimeError(f"QGA command is unavailable: {required}")


def ssh_exec(script, args=(), timeout=180):
    command = [
        "ssh",
        "-i", ssh_key,
        "-p", ssh_port,
        "-o", "BatchMode=yes",
        "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        "-o", "ConnectTimeout=10",
        "mo@127.0.0.1",
        "/usr/bin/bash", "-s", "--", *args,
    ]
    completed = subprocess.run(
        command,
        input=script,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"SSH runtime gate exited {completed.returncode}: "
            f"{completed.stderr or completed.stdout}"
        )
    return completed.stdout, completed.stderr


def boot_id_of(output):
    return next(
        (line.split("=", 1)[1] for line in output.splitlines() if line.startswith("boot_id=")),
        "",
    )


def wait_for_runtime(script, previous_id="", timeout=900):
    deadline = time.monotonic() + timeout
    last_error = "the installed guest has not accepted the ephemeral SSH key"
    while time.monotonic() < deadline:
        if not qemu_alive():
            raise SystemExit("X86 QCOW2 FATAL: QEMU exited before the runtime gate passed")
        try:
            request({"execute": "guest-ping"})
            assert_qga_contract()
            stdout, stderr = ssh_exec(script, (expected,))
            boot_id = boot_id_of(stdout)
            if boot_id and boot_id != previous_id:
                return stdout, stderr, boot_id
            last_error = "guest still reports the previous boot ID"
        except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
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
deployed_origin() {
    local origins=()
    shopt -s nullglob
    origins=(/ostree/deploy/*/deploy/*.origin)
    shopt -u nullglob
    [ "${#origins[@]}" -eq 1 ] || return 1
    sed -n 's/^container-image-reference=//p' "${origins[0]}"
}
gate_fail() {
    printf 'runtime-gate=%s\n' "$1" >&2
    # Preserve a bounded snapshot from the last retry. Unlike QGA command execution,
    # SSH executes inside the actual booted userspace and its mount namespace.
    printf 'system-state=%s\n' "$(systemctl is-system-running 2>/dev/null || true)" >&2
    printf 'root-mount=%s\n' "$(findmnt -n -o SOURCE,FSTYPE / 2>/dev/null || true)" >&2
    printf 'booted-origin=%s\n' "$(deployed_origin 2>/dev/null || true)" >&2
    printf '%s\n' 'failed-units:' >&2
    # Prefer list-units: --failed --plain can print nothing on some systemd
    # builds even when NFailedUnits > 0 (observed on freeze CI).
    systemctl list-units --state=failed --full --no-pager --no-legend 2>/dev/null >&2 || true
    printf '%s\n' 'failed-unit-details:' >&2
    systemctl list-units --state=failed --full --no-pager --no-legend --output=json 2>/dev/null \
        | python3 -c 'import json,sys
try:
    units=json.load(sys.stdin)
except Exception:
    raise SystemExit(0)
for u in units:
    print(u.get("unit") or u.get("Unit") or u)' 2>/dev/null >&2 || true
    if [ -d /run/systemd/failed ]; then
        printf 'failed-unit-files=%s\n' "$(ls -1 /run/systemd/failed 2>/dev/null | tr '\n' ' ')" >&2
    fi
    printf 'n-failed-units=%s\n' "$(systemctl show -p NFailedUnits --value 2>/dev/null || true)" >&2
    printf '%s\n' 'failed-unit-journal:' >&2
    journalctl -b -p warning --no-pager -n 80 2>/dev/null \
        | grep -E 'Failed|failed|zram|hardware-adapt|swap|start-limit' | tail -40 >&2 || true
    if [ -n "${login_uid:-}" ]; then
        printf 'greeter-uid=%s\n' "$login_uid" >&2
        printf '%s\n' 'greeter-processes:' >&2
        ps -u "$login_uid" -o pid=,comm=,args= --sort=pid 2>/dev/null | tail -40 >&2 || true
    fi
    printf '%s\n' 'plasmalogin-status:' >&2
    systemctl status plasmalogin.service --no-pager --full 2>&1 | tail -40 >&2 || true
    printf '%s\n' 'display-manager-journal:' >&2
    journalctl -b -u plasmalogin.service -u display-manager.service \
        -o short-monotonic --no-pager -n 80 2>/dev/null >&2 || true
    return 1
}
. /etc/os-release
[ "${ID:-}" = moos ] || gate_fail identity-id
[ "${NAME:-}" = MoOS ] || gate_fail identity-name
[ "$(uname -m)" = x86_64 ] || gate_fail architecture
[ -e /run/ostree-booted ] || gate_fail ostree-booted
grep -qw rd.live.image /proc/cmdline && gate_fail unexpected-live-boot
[ -e /etc/moos-firstboot-done ] || gate_fail firstboot-stamp
for unit in graphical.target display-manager.service plasmalogin.service NetworkManager.service; do
    [ "$(systemctl show -p ActiveState --value "$unit" 2>/dev/null || true)" = active ] \
        || gate_fail "required-system-service-${unit}"
done
[ "$(systemctl show -p Id --value display-manager.service 2>/dev/null || true)" = plasmalogin.service ] \
    || gate_fail display-manager-identity
grep -q '^mo:' /etc/passwd || gate_fail provisioned-user
account_path="$(busctl call org.freedesktop.Accounts \
    /org/freedesktop/Accounts org.freedesktop.Accounts FindUserByName s mo)"
[[ "$account_path" == *"/org/freedesktop/Accounts/User"* ]] || gate_fail accounts-service-user
compgen -G "/dev/dri/card*" >/dev/null || gate_fail drm-device
# plasma-login-manager declares its greeter through systemd-sysusers.  On a
# fresh bootc deployment nss-systemd resolves that account even when it has no
# literal entry in /etc/passwd, so reading the file directly rejects a real,
# running greeter.  Query NSS, which is also what the service stack uses.
login_uid="$(getent passwd plasmalogin | cut -d: -f3)"
[ -n "$login_uid" ] || gate_fail greeter-user
pgrep -u "$login_uid" -x kwin_wayland >/dev/null || gate_fail greeter-kwin
ipv4="$(ip -4 -o addr show scope global)"
[ -n "$ipv4" ] || gate_fail network-address
routes="$(ip -4 route show default)"
[[ "$routes" == default\ * ]] || gate_fail network-default-route
for helper in moos-settings moos-update moos-rollback moos-store moai moplayer mo-pc-remote; do
    [ -x "/usr/bin/$helper" ] || gate_fail "missing-command-${helper}"
done
origin="$(deployed_origin || true)"
origin_digest="${origin##*@}"
[ "$origin" = "ostree-image-signed:docker://${expected}" ] || gate_fail signed-origin
[ "$origin_digest" = "${expected##*@}" ] || gate_fail origin-digest
python3 - /etc/containers/policy.json <<'INNER'
import json
import sys
with open(sys.argv[1], encoding='utf-8') as source:
    policy = json.load(source)
entry = policy['transports']['docker']['ghcr.io/moalfarras-sys']
assert len(entry) == 1 and entry[0]['type'] == 'sigstoreSigned'
assert entry[0]['keyPath'] == '/etc/pki/containers/moos.pub'
assert entry[0]['signedIdentity'] == {'type': 'matchRepository'}
INNER
[ "$(systemctl show -p NFailedUnits --value 2>/dev/null || true)" = 0 ] || gate_fail failed-system-unit
printf 'boot_id=%s\nidentity=%s\narch=%s\norigin=%s\norigin-digest=%s\ngraphical=active\ndisplay-manager=plasmalogin\ngreeter-kwin=active\ndrm=present\nnetwork=active\nssh=ephemeral-key\nqga=responsive\nfirst-party-commands=7\nfailed-units=0\n' \
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
