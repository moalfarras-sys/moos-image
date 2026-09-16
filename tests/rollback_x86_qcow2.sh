#!/usr/bin/env bash
# P0.4 rollback proof: boot the exact sealed x86 QCOW2 on a disposable overlay, leave user data,
# create a second deployment, boot it, roll back with the user-facing `bootc rollback`, and prove
# the previous deployment boots again with the user data intact and the newer one retained.
#
# Root transactions go through the QEMU guest agent (the same channel the ISO install proof uses);
# every claim about the booted system is read back over ephemeral-key SSH inside the real booted
# userspace. The release boot gate (tests/boot_x86_qcow2.sh) deliberately stays SSH-only.
#
# What this proves: the rollback mechanism, deployment ordering, bootloader selection, retained
# deployments, signed origin and /var user data across two deployment switches.
# What it does NOT prove: automatic fallback after a boot that never completes (P1.2).
set -euo pipefail

if [ "$#" -ne 4 ]; then
    echo "usage: $0 IMAGE.qcow2 ghcr.io/moalfarras-sys/<edition>@sha256:... EVIDENCE_DIR SSH_PRIVATE_KEY" >&2
    exit 2
fi

qcow="$(realpath "$1")"
expected_ref="$2"
evidence="$(realpath -m "$3")"
ssh_key="$(realpath "$4" 2>/dev/null || true)"
[[ "$expected_ref" =~ ^ghcr\.io/moalfarras-sys/(moos|moos-nvidia|moos-cloud)@sha256:[0-9a-f]{64}$ ]] || {
    echo "ROLLBACK FATAL: expected image is not an exact official x86 digest" >&2
    exit 2
}
[ -f "$qcow" ] || { echo "ROLLBACK FATAL: missing QCOW2: $qcow" >&2; exit 2; }
[ -f "$ssh_key" ] || { echo "ROLLBACK FATAL: missing CI SSH private key" >&2; exit 2; }
[ "$(stat -c '%a' "$ssh_key")" = 600 ] || {
    echo "ROLLBACK FATAL: CI SSH private key must have mode 0600" >&2
    exit 2
}
[ -c /dev/kvm ] && [ -w /dev/kvm ] || { echo "ROLLBACK FATAL: writable /dev/kvm is required" >&2; exit 2; }
for tool in qemu-img qemu-system-x86_64 sha256sum python3 ssh; do
    command -v "$tool" >/dev/null || { echo "ROLLBACK FATAL: missing host tool: $tool" >&2; exit 2; }
done

ovmf_code=""
ovmf_vars=""
for candidate in /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd \
    /usr/share/edk2/ovmf/OVMF_CODE.fd /usr/share/edk2/x64/OVMF_CODE.4m.fd; do
    paired="${candidate/OVMF_CODE/OVMF_VARS}"
    if [ -f "$candidate" ] && [ -f "$paired" ]; then
        ovmf_code="$candidate"
        ovmf_vars="$paired"
        break
    fi
done
[ -n "$ovmf_code" ] || { echo "ROLLBACK FATAL: no matching OVMF CODE/VARS pair" >&2; exit 2; }

install -d -m0755 "$evidence"
base_tmp="${RUNNER_TEMP:-/var/tmp}"
work="$(mktemp -d -p "$base_tmp" moos-x86-rollback.XXXXXX)"
qemu_pid=""
cleanup() {
    local rc=$?
    trap - EXIT INT TERM
    if [ -n "$qemu_pid" ] && kill -0 "$qemu_pid" 2>/dev/null; then
        kill "$qemu_pid" 2>/dev/null || true
        wait "$qemu_pid" 2>/dev/null || true
    fi
    if [ "$rc" -ne 0 ]; then
        echo "=== serial log (tail) ===" >&2
        tail -n 80 "$evidence/serial.log" >&2 2>/dev/null || true
    fi
    case "$work" in
        "$base_tmp"/moos-x86-rollback.*) rm -rf -- "$work" ;;
    esac
    exit "$rc"
}
trap cleanup EXIT INT TERM

before_sha="$(sha256sum "$qcow" | awk '{print $1}')"
# Every write lands in this overlay; the sealed artifact is only ever a read-only backing file.
qemu-img create -f qcow2 -F qcow2 -b "$qcow" "$work/overlay.qcow2" >/dev/null
cp "$ovmf_vars" "$work/OVMF_VARS.fd"

read -r port_a port_b port_r < <(python3 - <<'PY'
import socket
ports = []
sockets = []
for _ in range(3):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    sockets.append(s)
    ports.append(str(s.getsockname()[1]))
print(" ".join(ports))
PY
)
qga="$work/qga.sock"

qemu-system-x86_64 \
    -machine q35,accel=kvm -cpu host -smp 4 -m 6144 \
    -drive "if=pflash,format=raw,unit=0,readonly=on,file=$ovmf_code" \
    -drive "if=pflash,format=raw,unit=1,file=$work/OVMF_VARS.fd" \
    -drive "file=$work/overlay.qcow2,if=virtio,format=qcow2" \
    -netdev "user,id=n0,hostfwd=tcp:127.0.0.1:${port_a}-:22,hostfwd=tcp:127.0.0.1:${port_b}-:22,hostfwd=tcp:127.0.0.1:${port_r}-:22" \
    -device virtio-net-pci,netdev=n0 \
    -device virtio-serial \
    -chardev "socket,path=$qga,server=on,wait=off,id=qga0" \
    -device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0 \
    -device virtio-vga -display none \
    -serial "file:$evidence/serial.log" \
    >"$evidence/qemu.log" 2>&1 &
qemu_pid=$!

python3 - "$qga" "$qemu_pid" "$expected_ref" "$evidence" "$ssh_key" "$port_a" "$port_b" "$port_r" <<'PY'
import base64
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

qga = sys.argv[1]
qemu_pid = int(sys.argv[2])
expected, evidence, ssh_key = sys.argv[3], Path(sys.argv[4]), sys.argv[5]
ports = {"first": sys.argv[6], "after-new-deployment": sys.argv[7], "after-rollback": sys.argv[8]}
PROBE_KARG = "moos.rollback-probe=1"
sync_serial = 0


def fatal(message):
    raise SystemExit(f"ROLLBACK FATAL: {message}")


def qemu_alive():
    try:
        os.kill(qemu_pid, 0)
        return True
    except OSError:
        return False


def connect_synced(timeout=10.0):
    global sync_serial
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(qga)
        sync_serial += 1
        client.sendall(json.dumps({"execute": "guest-sync-delimited",
                                   "arguments": {"id": sync_serial}}).encode() + b"\n")
        buffer = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            buffer += client.recv(65536)
            if b"\xff" not in buffer:
                continue
            current = buffer.rsplit(b"\xff", 1)[1]
            if b"\n" not in current:
                continue
            if json.loads(current.split(b"\n", 1)[0]).get("return") != sync_serial:
                raise RuntimeError("QGA sync returned the wrong id")
            return client
        raise RuntimeError("QGA sync timed out")
    except Exception:
        client.close()
        raise


def request(payload, timeout=10.0):
    with connect_synced(timeout) as client:
        client.sendall(json.dumps(payload).encode() + b"\n")
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


def require_guest_exec():
    info = request({"execute": "guest-info"})
    enabled = {c.get("name"): c.get("enabled") for c in info.get("supported_commands", [])}
    for name in ("guest-exec", "guest-exec-status", "guest-shutdown"):
        if enabled.get(name) is not True:
            fatal(f"QGA command {name} is unavailable; the rollback proof needs a root channel")


def root_exec(label, argv, timeout=900):
    """Run one fixed root transaction through QGA and keep its full output as evidence."""
    started = request({"execute": "guest-exec",
                       "arguments": {"path": argv[0], "arg": argv[1:], "capture-output": True}})
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = request({"execute": "guest-exec-status", "arguments": {"pid": started["pid"]}})
        if status.get("exited"):
            out = base64.b64decode(status.get("out-data", "")).decode(errors="replace")
            err = base64.b64decode(status.get("err-data", "")).decode(errors="replace")
            (evidence / f"{label}.log").write_text(
                f"$ {' '.join(argv)}\nexit={status.get('exitcode')}\n--- stdout\n{out}--- stderr\n{err}",
                encoding="utf-8")
            if status.get("exitcode") != 0:
                fatal(f"{' '.join(argv)} exited {status.get('exitcode')}: {err or out}")
            return
        time.sleep(3)
    fatal(f"{' '.join(argv)} did not finish within {timeout}s")


def ssh(script, port, args=(), timeout=120):
    completed = subprocess.run(
        ["ssh", "-i", ssh_key, "-p", port,
         "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
         "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
         "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=10",
         "mo@127.0.0.1", "/usr/bin/bash", "-s", "--", *args],
        input=script, text=True, capture_output=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"SSH exited {completed.returncode}: {completed.stderr or completed.stdout}")
    return completed.stdout


READBACK = r'''
set -euo pipefail
python3 - "$HOME/.local/state/moos-rollback-proof/marker" <<'GUEST'
import json, pathlib, subprocess, sys
status = json.loads(subprocess.run(["rpm-ostree", "status", "--json"],
                                   capture_output=True, text=True, check=True).stdout)
deployments = status.get("deployments", [])
booted = next((d for d in deployments if d.get("booted")), {})
marker = pathlib.Path(sys.argv[1])
failed = subprocess.run(["systemctl", "show", "-p", "NFailedUnits", "--value"],
                        capture_output=True, text=True).stdout.strip()
print(json.dumps({
    "boot_id": pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
    "cmdline": pathlib.Path("/proc/cmdline").read_text().split(),
    "system_state": subprocess.run(["systemctl", "is-system-running"],
                                   capture_output=True, text=True).stdout.strip(),
    "failed_units": int(failed or -1),
    "deployments": [{"id": d.get("id"), "checksum": d.get("checksum"), "booted": bool(d.get("booted")),
                     "origin": d.get("container-image-reference")} for d in deployments],
    "booted_id": booted.get("id"),
    "booted_checksum": booted.get("checksum"),
    "booted_origin": booted.get("container-image-reference"),
    "marker": marker.read_text().strip() if marker.is_file() else None,
}))
GUEST
'''


def wait_for_boot(phase, previous_boot_id="", timeout=900):
    """A readback from a NEW boot whose system manager has finished starting."""
    deadline = time.monotonic() + timeout
    last = "no SSH readback yet"
    while time.monotonic() < deadline:
        if not qemu_alive():
            fatal(f"QEMU exited while waiting for the {phase} boot")
        try:
            request({"execute": "guest-ping"})
            state = json.loads(ssh(READBACK, ports[phase]))
            if state["boot_id"] == previous_boot_id:
                last = "guest still reports the previous boot ID"
            elif state["system_state"] in ("running", "degraded"):
                (evidence / f"{phase}.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
                print(f"{phase}: boot {state['boot_id']} deployment {state['booted_id']} "
                      f"state {state['system_state']} failed-units {state['failed_units']}")
                return state
            else:
                last = f"system state {state['system_state']}"
        except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
            last = str(error)
        time.sleep(5)
    fatal(f"the {phase} boot did not become ready: {last}")


def reboot():
    with connect_synced(5) as client:   # guest-shutdown sends no reply on success
        client.sendall(json.dumps({"execute": "guest-shutdown", "arguments": {"mode": "reboot"}}).encode() + b"\n")


def signed(state):
    origin = state.get("booted_origin") or ""
    return origin.startswith("ostree-image-signed:") and "ghcr.io/moalfarras-sys/" in origin


# ── A: the sealed release, with user data written through the normal user session ──────────────
first = wait_for_boot("first")
require_guest_exec()
if len(first["deployments"]) != 1 or PROBE_KARG in first["cmdline"] or not signed(first):
    fatal(f"first boot is not a single signed deployment: {first}")
if first["failed_units"] != 0:
    fatal(f"first boot has {first['failed_units']} failed unit(s)")
token = secrets.token_hex(16)
ssh('set -euo pipefail\ninstall -d -m 0700 "$HOME/.local/state/moos-rollback-proof"\n'
    'printf "%s\\n" "$1" > "$HOME/.local/state/moos-rollback-proof/marker"\nsync\n',
    ports["first"], (token,))

# ── B: a second deployment of the same signed commit that is observably different ──────────────
root_exec("create-new-deployment", ["/usr/bin/rpm-ostree", "kargs", f"--append={PROBE_KARG}"])
reboot()
newer = wait_for_boot("after-new-deployment", first["boot_id"])
if PROBE_KARG not in newer["cmdline"]:
    fatal("the new deployment did not boot (probe karg absent)")
if newer["booted_id"] == first["booted_id"] or len(newer["deployments"]) != 2:
    fatal(f"expected to boot a second deployment: {newer}")
if newer["marker"] != token or not signed(newer):
    fatal("user data or signed origin was lost when switching to the new deployment")

# ── R: the user-facing rollback verb returns to A ─────────────────────────────────────────────
root_exec("bootc-rollback", ["/usr/bin/bootc", "rollback"])
reboot()
rolled = wait_for_boot("after-rollback", newer["boot_id"])
checks = {
    "previous deployment booted": rolled["booted_id"] == first["booted_id"],
    "same signed commit as before": rolled["booted_checksum"] == first["booted_checksum"],
    "probe karg gone": PROBE_KARG not in rolled["cmdline"],
    "newer deployment retained for roll-forward": any(
        d["id"] == newer["booted_id"] and not d["booted"] for d in rolled["deployments"]),
    "user data intact": rolled["marker"] == token,
    "signed origin": signed(rolled),
    "no failed units": rolled["failed_units"] == 0,
}
(evidence / "summary.json").write_text(json.dumps(
    {"expected_image": expected, "checks": checks,
     "deployment_before": first["booted_id"], "deployment_new": newer["booted_id"],
     "deployment_after_rollback": rolled["booted_id"]}, indent=2), encoding="utf-8")
failed = [name for name, ok in checks.items() if not ok]
if failed:
    fatal("rollback proof failed: " + ", ".join(failed))

with connect_synced(5) as client:
    client.sendall(json.dumps({"execute": "guest-shutdown", "arguments": {"mode": "powerdown"}}).encode() + b"\n")
deadline = time.monotonic() + 180
while qemu_alive() and time.monotonic() < deadline:
    time.sleep(2)
if qemu_alive():
    fatal("guest did not power off within 180s")
print("rollback checks: " + ", ".join(checks))
PY
wait "$qemu_pid" 2>/dev/null || true
qemu_pid=""

after_sha="$(sha256sum "$qcow" | awk '{print $1}')"
[ "$before_sha" = "$after_sha" ] || { echo "ROLLBACK FATAL: the sealed QCOW2 was modified" >&2; exit 1; }
printf 'before_sha=%s\nafter_sha=%s\n' "$before_sha" "$after_sha" >"$evidence/artifact-sha.txt"
echo "X86 ROLLBACK OK: new deployment booted, bootc rollback returned to the signed previous deployment with user data intact"
