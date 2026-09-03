#!/usr/bin/env bash
# Install the exact final MoOS ISO OFFLINE, detach it, and prove the installed disk.
#
# This is deliberately separate from boot_live_iso.sh. A healthy live desktop does
# not prove that the destructive installer can consume the embedded image, seed an
# account, write a bootable EFI disk, or survive its first reboot. The target is a
# disposable qcow2 created here; the publishable ISO is opened read-only and its
# hash must remain unchanged.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/qemu_virgl_env.sh
. "$script_dir/qemu_virgl_env.sh"

iso="${1:-}"
expected_ref="${2:-}"
evidence="${3:-}"

[ -f "$iso" ] || { echo "ISO INSTALL FATAL: final ISO is missing: $iso" >&2; exit 2; }
[[ "$expected_ref" =~ ^ghcr\.io/moalfarras-sys/(moos|moos-nvidia)@sha256:[0-9a-f]{64}$ ]] \
    || { echo "ISO INSTALL FATAL: expected image ref is not an exact official digest" >&2; exit 2; }
[ -n "$evidence" ] || { echo "ISO INSTALL FATAL: evidence directory is required" >&2; exit 2; }
for tool in qemu-img qemu-system-x86_64 sha256sum socat python3 ssh ssh-keygen; do
    command -v "$tool" >/dev/null \
        || { echo "ISO INSTALL FATAL: missing host tool: $tool" >&2; exit 2; }
done

iso="$(realpath "$iso")"
install -d -m0755 "$evidence"
evidence="$(realpath "$evidence")"
work_base="${RUNNER_TEMP:-/tmp}"
work="$(mktemp -d -p "$work_base" moos-iso-install.XXXXXX)"
qemu_pid=""
xvfb_pid=""

cleanup() {
    local rc=$?
    trap - EXIT INT TERM
    if [ -n "$qemu_pid" ] && kill -0 "$qemu_pid" 2>/dev/null; then
        kill "$qemu_pid" 2>/dev/null || true
        wait "$qemu_pid" 2>/dev/null || true
    fi
    moos_stop_virgl_display
    if [ "$rc" -ne 0 ]; then
        echo "=== QEMU log (tail) ===" >&2
        tail -100 "$evidence/qemu-installed.log" "$evidence/qemu-live-install.log" \
            2>/dev/null >&2 || true
        echo "=== installed serial (tail) ===" >&2
        tail -120 "$evidence/serial-installed.log" 2>/dev/null >&2 || true
        echo "=== live install status ===" >&2
        tail -80 "$evidence/install.status" 2>/dev/null >&2 || true
        echo "=== installer log ===" >&2
        tail -120 "$evidence/installer.log" 2>/dev/null >&2 || true
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
    || { echo "ISO INSTALL FATAL: no matching OVMF CODE/VARS firmware pair" >&2; exit 1; }
cp "$ovmf_vars" "$work/vars.fd"

before_sha="$(sha256sum "$iso" | awk '{print $1}')"
test_password="$(python3 - <<'PY'
import secrets
import string
alphabet = string.ascii_lowercase + string.digits
print("".join(secrets.choice(alphabet) for _ in range(20)))
PY
)"
ssh_key="$work/moos-iso-ci-key"
ssh-keygen -q -t ed25519 -N '' -C moos-ci-runtime-proof -f "$ssh_key"
chmod 0600 "$ssh_key"
ssh_public_key="$(cat "$ssh_key.pub")"
ssh_port="$(python3 - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
printf 'iso=%s\nsha256=%s\nimage=%s\novmf=%s\ntarget-size=36G\nnetwork-during-install=disabled\n' \
    "$iso" "$before_sha" "$expected_ref" "$ovmf_code" > "$evidence/manifest.txt"

qemu-img create -q -f qcow2 "$work/installed.qcow2" 36G
moos_start_virgl_display "$work" "$evidence"

start_qemu() {
    local phase="$1"
    shift
    qga="$work/qga.sock"
    monitor="$work/monitor.sock"
    rm -f "$qga" "$monitor"
    # VirGL keeps both the live and installed compositors on the same real 3D
    # guest path while Xvfb captures the mapped GTK pixels users would see.
    LIBGL_ALWAYS_SOFTWARE=1 qemu-system-x86_64 \
        -name "$MOOS_QEMU_WINDOW_TITLE" \
        -machine q35,accel=kvm -cpu host -m 4096 -smp 2 \
        -drive "if=pflash,format=raw,readonly=on,file=$ovmf_code" \
        -drive "if=pflash,format=raw,file=$work/vars.fd" \
        -drive "file=$work/installed.qcow2,format=qcow2,if=virtio,cache=unsafe" \
        "$@" \
        -device virtio-vga-gl \
        -netdev "user,id=n0,hostfwd=tcp:127.0.0.1:${ssh_port}-:22" \
        -device virtio-net-pci,netdev=n0 \
        -device virtio-serial-pci \
        -chardev "socket,path=$qga,server=on,wait=off,id=qga0" \
        -device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0 \
        -monitor "unix:$monitor,server=on,wait=off" \
        -serial "file:$evidence/serial-${phase}.log" \
        -display gtk,gl=on,show-menubar=off,show-tabs=off,window-close=off \
        >"$evidence/qemu-${phase}.log" 2>&1 &
    qemu_pid=$!
}

wait_for_poweroff() {
    local label="$1"
    for _ in $(seq 1 180); do
        kill -0 "$qemu_pid" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "$qemu_pid" 2>/dev/null; then
        echo "ISO INSTALL FATAL: ${label} did not power off within 180s" >&2
        return 1
    fi
    wait "$qemu_pid"
    qemu_pid=""
}

# First boot: the network device exists so the installed OS can be tested later,
# but NetworkManager is stopped before the installer starts. Success therefore
# proves the exact embedded containers-storage image, not a registry fallback.
start_qemu live-install \
    -drive "file=$iso,media=cdrom,format=raw,readonly=on" -boot order=d

python3 - "$qga" "$qemu_pid" "$expected_ref" "$test_password" "$evidence" \
    "$ssh_public_key" <<'PY'
import base64
import json
import os
from pathlib import Path
import socket
import sys
import time

qga, qemu_pid, expected, password, evidence_arg, proof_key = sys.argv[1:]
qemu_pid = int(qemu_pid)
evidence = Path(evidence_arg)


def alive():
    try:
        os.kill(qemu_pid, 0)
        return True
    except OSError:
        return False


def request(payload, timeout=10.0):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(qga)
        client.sendall(json.dumps(payload, separators=(",", ":")).encode() + b"\n")
        data = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data += client.recv(65536)
            while b"\n" in data:
                raw, data = data.split(b"\n", 1)
                if not raw.strip():
                    continue
                reply = json.loads(raw.lstrip(b"\xff"))
                if "error" in reply:
                    raise RuntimeError(str(reply["error"]))
                if "return" in reply:
                    return reply["return"]
    raise RuntimeError("QGA returned no response")


def wait_qga(seconds=900):
    deadline = time.monotonic() + seconds
    last = "not ready"
    while time.monotonic() < deadline:
        if not alive():
            raise SystemExit("ISO INSTALL FATAL: live QEMU exited before QGA")
        try:
            request({"execute": "guest-ping"})
            return
        except (OSError, ValueError, RuntimeError) as error:
            last = str(error)
            time.sleep(5)
    raise SystemExit(f"ISO INSTALL FATAL: live QGA timeout: {last}")


def exec_wait(script, args, timeout):
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
            return status.get("exitcode", 1), stdout, stderr
        time.sleep(5)
    raise SystemExit("ISO INSTALL FATAL: installer did not finish within 45 minutes")


wait_qga()
install = r'''
set -euo pipefail
expected="$1"
password="$2"
proof_key="$3"
grep -qw rd.live.image /proc/cmdline
node=/dev/vda
[ -b "$node" ]
cache=/var/home/liveuser/.cache/moos-installer
install -d -m0700 -o liveuser -g liveuser "$cache"
python3 - "$cache/recipe.json" "$password" <<'INNER'
import json, os, sys
path, password = sys.argv[1:]
with open(path, "w", encoding="utf-8") as stream:
    json.dump({
        "node": "/dev/vda", "username": "moosci", "fullname": "MoOS ISO Gate",
        "password": password, "keymap": "us", "xkblayout": "us",
        "locale": "en_US.UTF-8", "timezone": "UTC",
    }, stream)
os.chmod(path, 0o600)
INNER
chown liveuser:liveuser "$cache/recipe.json"
printf '{"liveNode":"/dev/sr0","disks":[{"node":"/dev/vda","isLive":false}]}\n' \
    > "$cache/disks.json"
chown liveuser:liveuser "$cache/disks.json"
offline_ref="$(tr -d '\r\n' < /usr/lib/moos/install-imageref)"
podman image exists "$offline_ref"
source_digest="$(tr -d '\r\n' < /usr/lib/moos/install-source-digest)"
[ "$source_digest" = "${expected##*@}" ]
nmcli networking off
systemctl stop NetworkManager.service
! ip route show default | grep -q .
PKEXEC_UID="$(id -u liveuser)" /usr/bin/moos-install-to-disk "$cache/install.status"
grep -qx DONE "$cache/install.status"
! grep -q '^FAIL ' "$cache/install.status"
grep -Fq 'source: local containers-storage (offline)' /tmp/moos-install-to-disk.log
! grep -Fq 'source: registry (online)' /tmp/moos-install-to-disk.log
[ ! -e "$cache/recipe.json" ]

# Add a one-boot CI access fixture to this disposable target only. The shipped
# image keeps this unit disabled and requires all three markers: VM, kernel
# argument, and an ephemeral key carrying the explicit proof comment.
root_part="$(lsblk -nrpo NAME,FSTYPE "$node" | awk '$2=="btrfs" {print $1; exit}')"
[ -n "$root_part" ]
proof_root=/run/moos-iso-ci-target
install -d -m0755 "$proof_root"
mount -o subvol=root "$root_part" "$proof_root"
proof_home="$proof_root/var/home/moosci"
install -d -m0700 "$proof_home/.ssh"
printf '%s\n' "$proof_key" > "$proof_home/.ssh/authorized_keys"
chmod 0600 "$proof_home/.ssh/authorized_keys"
chown -R 1000:1000 "$proof_home"
deployment="$(find "$proof_root/ostree/deploy" -mindepth 3 -maxdepth 3 \
    -type d -name '*.0' -print -quit)"
[ -n "$deployment" ]
wants="$deployment/etc/systemd/system/multi-user.target.wants"
install -d -m0755 "$wants"
ln -s /usr/lib/systemd/system/moos-ci-runtime-proof.service \
    "$wants/moos-ci-runtime-proof.service"
python3 - "$proof_root" <<'INNER'
from pathlib import Path
import sys

root = Path(sys.argv[1])
entries = sorted(root.glob("boot/loader*/entries/*.conf"))
if not entries:
    raise SystemExit("no installed BLS entry for the ISO CI proof marker")
for entry in entries:
    lines = entry.read_text(encoding="utf-8").splitlines()
    indexes = [i for i, line in enumerate(lines) if line.startswith("options ")]
    if len(indexes) != 1:
        raise SystemExit(f"invalid BLS options in {entry}")
    index = indexes[0]
    options = lines[index].split()[1:]
    if "moos.ci-runtime-proof=1" not in options:
        options.append("moos.ci-runtime-proof=1")
    lines[index] = "options " + " ".join(options)
    entry.write_text("\n".join(lines) + "\n", encoding="utf-8")
INNER
sync -f "$proof_home/.ssh/authorized_keys"
umount "$proof_root"
lsblk -nrpo NAME,FSTYPE,PARTLABEL "$node"
printf 'install=done\nsource=embedded-offline\nnetwork=disabled\ntarget=%s\nci-proof=ephemeral-ssh\n' "$node"
'''
code, out, err = exec_wait(install, [expected, password, proof_key], 2700)
(evidence / "install.status").write_text(out + ("\n=== stderr ===\n" + err if err else ""))
if code != 0:
    raise SystemExit(f"ISO INSTALL FATAL: installer gate exited {code}: {err or out}")

for guest_path, host_name in (
    ("/tmp/moos-install-to-disk.log", "installer.log"),
    ("/var/home/liveuser/.cache/moos-installer/install.status", "installer-status.raw"),
):
    code, out, err = exec_wait("cat -- \"$1\"", [guest_path], 30)
    (evidence / host_name).write_text(out + ("\n=== stderr ===\n" + err if err else ""))

try:
    request({"execute": "guest-shutdown", "arguments": {"mode": "powerdown"}}, timeout=3)
except (OSError, RuntimeError, socket.timeout):
    pass
PY

wait_for_poweroff "live installer"

# Second phase has NO CD-ROM argument. If the target depends on the ISO, QEMU
# cannot hide that by choosing the live medium again.
start_qemu installed -boot order=c

python3 - "$qga" "$monitor" "$qemu_pid" "$expected_ref" "$test_password" "$evidence" \
    "$ssh_key" "$ssh_port" <<'PY'
import base64
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

qga, monitor, qemu_pid, expected, password, evidence_arg, ssh_key, ssh_port = sys.argv[1:]
qemu_pid = int(qemu_pid)
evidence = Path(evidence_arg)


def alive():
    try:
        os.kill(qemu_pid, 0)
        return True
    except OSError:
        return False


def request(payload, timeout=10.0):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(qga)
        client.sendall(json.dumps(payload, separators=(",", ":")).encode() + b"\n")
        data = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data += client.recv(65536)
            while b"\n" in data:
                raw, data = data.split(b"\n", 1)
                if not raw.strip():
                    continue
                reply = json.loads(raw.lstrip(b"\xff"))
                if "error" in reply:
                    raise RuntimeError(str(reply["error"]))
                if "return" in reply:
                    return reply["return"]
    raise RuntimeError("QGA returned no response")


def wait_qga(seconds=1000):
    deadline = time.monotonic() + seconds
    last = "not ready"
    while time.monotonic() < deadline:
        if not alive():
            raise SystemExit("ISO INSTALL FATAL: installed QEMU exited before QGA")
        try:
            request({"execute": "guest-ping"})
            return
        except (OSError, ValueError, RuntimeError) as error:
            last = str(error)
            time.sleep(5)
    raise SystemExit(f"ISO INSTALL FATAL: installed QGA timeout: {last}")


def ssh_exec(script, args=(), timeout=180):
    command = [
        "ssh", "-i", ssh_key, "-p", ssh_port,
        "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=10",
        "moosci@127.0.0.1", "/usr/bin/bash", "-s", "--", *args,
    ]
    completed = subprocess.run(
        command, input=script, text=True, capture_output=True,
        timeout=timeout, check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def gate_until(script, args, seconds, label):
    deadline = time.monotonic() + seconds
    last = "not run"
    while time.monotonic() < deadline:
        code, out, err = ssh_exec(script, args, 60)
        if code == 0:
            return out
        last = err or out or f"exit {code}"
        time.sleep(5)
    raise SystemExit(f"ISO INSTALL FATAL: {label}: {last}")


def hmp(commands):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(monitor)
        client.recv(4096)
        client.sendall(("\n".join(commands) + "\n").encode())


def capture(path):
    log = evidence / f"{path.stem}-capture.log"
    windows = evidence / f"{path.stem}-windows.txt"
    hmp(["sendkey shift"])
    time.sleep(2)
    tree = subprocess.run(
        ["xwininfo", "-display", os.environ["DISPLAY"], "-root", "-tree"],
        text=True, capture_output=True, check=False,
    )
    windows.write_text(tree.stdout + tree.stderr, encoding="utf-8")
    window = subprocess.run(
        ["xwininfo", "-display", os.environ["DISPLAY"], "-name",
         os.environ["MOOS_QEMU_WINDOW_TITLE"], "-int"],
        text=True, capture_output=True, check=False,
    )
    match = re.search(r"Window id:\s+(\d+)", window.stdout)
    if window.returncode != 0 or not match:
        log.write_text(
            f"xwininfo rc={window.returncode}\n{window.stdout}{window.stderr}",
            encoding="utf-8",
        )
        raise SystemExit(f"ISO INSTALL FATAL: QEMU window was not found: {path.name}")
    result = subprocess.run(
        ["import", "-silent", "-display", os.environ["DISPLAY"],
         "-window", match.group(1), str(path)],
        text=True, capture_output=True, timeout=30, check=False,
    )
    log.write_text(
        f"rc={result.returncode}\n{result.stdout}{result.stderr}", encoding="utf-8"
    )
    if result.returncode != 0 or not path.is_file() or not path.stat().st_size:
        raise SystemExit(f"ISO INSTALL FATAL: mapped GTK capture failed: {path.name}")


runtime = r'''
set -euo pipefail
expected="$1"
! grep -qw rd.live.image /proc/cmdline
. /etc/os-release
[ "${ID:-}" = moos ]
[ "$(uname -m)" = x86_64 ]
[ -e /etc/moos-firstboot-done ]
[ ! -e /etc/moos-setup.conf ]
id moosci >/dev/null
systemctl is-active graphical.target display-manager.service plasmalogin.service NetworkManager.service qemu-guest-agent.service
origin="$(rpm-ostree status --json)"
grep -Fq "ostree-image-signed:docker://${expected}" <<<"$origin"
failed="$(systemctl --failed --no-legend --plain)"
[ -z "$failed" ]
for app in moai moos-store moos-update moos-rollback moos-settings moplayer mo-pc-remote; do
    command -v "$app" >/dev/null
done
printf 'boot=installed\nidentity=%s\nuser=moosci\ngraphical=active\ndisplay-manager=active\norigin=%s\nfailed-units=0\n' \
    "$PRETTY_NAME" "$expected"
'''

wait_qga()
first = gate_until(runtime, [expected], 1000, "installed first boot never became healthy")
(evidence / "installed-first-boot.txt").write_text(first)

# Wake Plasma Login Manager's idle clock page and capture the actual password
# surface before interaction. Only a lowercase/digit disposable password is used,
# so HMP never needs layout-dependent punctuation.
hmp(["sendkey shift"])
time.sleep(2)
capture(evidence / "installed-login.ppm")
hmp([*(f"sendkey {char}" for char in password), "sendkey ret"])

desktop = r'''
set -euo pipefail
user="$(id -un)"
[ "$user" = moosci ]
uid="$(id -u)"
pgrep -u "$uid" -x kwin_wayland
pgrep -u "$uid" -x plasmashell
env XDG_RUNTIME_DIR="/run/user/${uid}" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${uid}/bus" \
    systemctl --user is-active plasma-workspace.target
user_failed="$(env XDG_RUNTIME_DIR="/run/user/${uid}" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${uid}/bus" \
    systemctl --user --failed --no-legend --plain)"
[ -z "$user_failed" ]
printf 'login=plasma-login-manager\ndesktop=usable\nkwin=active\nplasmashell=active\nuser-failed-units=0\n'
'''
desktop_out = gate_until(desktop, [], 900, "PLM login did not reach the desktop")
(evidence / "desktop-session.txt").write_text(desktop_out)

open_app = r'''
set -euo pipefail
label="$1"
shift
uid="$(id -u moosci)"
runtime="/run/user/${uid}"
as_user() {
    env HOME=/var/home/moosci XDG_RUNTIME_DIR="$runtime" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=${runtime}/bus" "$@"
}
opened="$(as_user moai-open "$@")"
unit="$(sed -n 's/.*unit \([^)]*\)).*/\1/p' <<<"$opened")"
[ -n "$unit" ]
for _ in $(seq 1 90); do
    if as_user systemctl --user is-active --quiet "$unit"; then
        printf '%s=%s\nunit=%s\n' "$label" opened "$unit"
        exit 0
    fi
    sleep 1
done
exit 1
'''

close_app = r'''
set -euo pipefail
unit="$1"
uid="$(id -u moosci)"
runtime="/run/user/${uid}"
for _ in $(seq 1 45); do
    if ! env HOME=/var/home/moosci XDG_RUNTIME_DIR="$runtime" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=${runtime}/bus" \
        systemctl --user is-active --quiet "$unit"; then
        exit 0
    fi
    sleep 1
done
exit 1
'''

app_specs = (
    ("dolphin", "dolphin"),
    ("konsole", "konsole"),
    ("moos-settings", "moos-settings"),
    ("mo-ai", "moai"),
    ("mo-store", "moos-store"),
    ("updater", "moos-update"),
    ("recovery", "moos-rollback"),
    ("themes", "moos-theme-picker"),
    ("moplayer", "moplayer"),
    ("mo-pc-remote", "mo-pc-remote"),
)
app_proof = []
for label, executable in app_specs:
    first = gate_until(open_app, [label, executable], 150, f"{label} did not open")
    unit = next((line.removeprefix("unit=") for line in first.splitlines()
                 if line.startswith("unit=")), "")
    if not unit:
        raise SystemExit(f"ISO INSTALL FATAL: {label} returned no runtime unit")
    time.sleep(2)
    capture(evidence / ("installed-app-" + label + ".ppm"))
    hmp(["sendkey alt-f4"])
    gate_until(close_app, [unit], 60, f"{label} did not close")

    second = gate_until(open_app, [label, executable], 150, f"{label} did not reopen")
    second_unit = next((line.removeprefix("unit=") for line in second.splitlines()
                        if line.startswith("unit=")), "")
    if not second_unit or second_unit == unit:
        raise SystemExit(f"ISO INSTALL FATAL: {label} reopen did not create a new unit")
    app_proof.append(f"{label}=opened-closed-reopened")
    if label == app_specs[-1][0]:
        time.sleep(2)
        capture(evidence / "installed-desktop-apps.ppm")
    hmp(["sendkey alt-f4"])
    gate_until(close_app, [second_unit], 60, f"reopened {label} did not close")

user_health = r'''
set -euo pipefail
uid="$(id -u)"
runtime="/run/user/${uid}"
failed="$(env XDG_RUNTIME_DIR="$runtime" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=${runtime}/bus" \
    systemctl --user --failed --no-legend --plain)"
[ -z "$failed" ]
'''
gate_until(user_health, [], 60, "first-party app smoke left failed user units")
(evidence / "app-smoke.txt").write_text("\n".join(app_proof) + "\n")

code, boot_id, error = ssh_exec("cat /proc/sys/kernel/random/boot_id")
if code != 0:
    raise SystemExit(f"ISO INSTALL FATAL: cannot read first boot id: {error}")
boot_id = boot_id.strip()
try:
    request({"execute": "guest-shutdown", "arguments": {"mode": "reboot"}}, timeout=3)
except (OSError, RuntimeError, socket.timeout):
    pass

# The monitor/QEMU process persists across this real guest reboot. Require a new
# kernel boot_id before accepting QGA again, then rerun the full installed gate.
deadline = time.monotonic() + 1000
while time.monotonic() < deadline:
    if not alive():
        raise SystemExit("ISO INSTALL FATAL: QEMU exited during installed reboot")
    try:
        request({"execute": "guest-ping"})
        code, current, _ = ssh_exec("cat /proc/sys/kernel/random/boot_id", timeout=20)
        if code == 0 and current.strip() and current.strip() != boot_id:
            break
    except (OSError, ValueError, RuntimeError):
        pass
    time.sleep(5)
else:
    raise SystemExit("ISO INSTALL FATAL: installed reboot never produced a new boot id")

second = gate_until(runtime, [expected], 900, "installed second boot never became healthy")
(evidence / "installed-second-boot.txt").write_text(second + "reboot=clean\n")
try:
    request({"execute": "guest-shutdown", "arguments": {"mode": "powerdown"}}, timeout=3)
except (OSError, RuntimeError, socket.timeout):
    pass
PY

wait_for_poweroff "installed system"

for ppm in "$evidence"/*.ppm; do
    [ -e "$ppm" ] || continue
    png="${ppm%.ppm}.png"
    if command -v magick >/dev/null; then
        magick "$ppm" "$png"
    elif command -v convert >/dev/null; then
        convert "$ppm" "$png"
    else
        echo "ISO INSTALL FATAL: ImageMagick is unavailable" >&2
        exit 2
    fi
    rm -f "$ppm"
    stddev="$(magick "$png" -colorspace gray -format '%[fx:standard_deviation]' info: 2>/dev/null \
        || convert "$png" -colorspace gray -format '%[fx:standard_deviation]' info:)"
    python3 - "$stddev" "$png" <<'PY'
import sys
value = float(sys.argv[1])
if value < 0.01:
    raise SystemExit(f"ISO INSTALL FATAL: visual evidence is blank: {sys.argv[2]} (stddev={value})")
PY
done

qemu-img check "$work/installed.qcow2" | tee "$evidence/installed-qcow2-check.txt"
after_sha="$(sha256sum "$iso" | awk '{print $1}')"
[ "$after_sha" = "$before_sha" ] \
    || { echo "ISO INSTALL FATAL: final ISO changed during install proof" >&2; exit 1; }
printf 'reboot=clean\nsecond-boot=healthy\npoweroff=clean\nfinal-iso-sha256=%s\n' \
    "$after_sha" >> "$evidence/installed-second-boot.txt"
echo "ISO INSTALL PASS: offline install, ISO detached, PLM login, desktop/apps, reboot, poweroff"
