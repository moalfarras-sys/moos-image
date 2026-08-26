#!/usr/bin/env bash
# Boot the exact ready-to-import UTM archive, consume its real NoCloud seed,
# log in through Plasma Login Manager, open native first-party applications and
# power off. This complements boot_arm_qcow2.sh: the raw disk gate proves two
# boots; this gate proves the public UTM configuration/provisioning contract.
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "usage: $0 MoOS-ARM.utm.zip IMAGE@sha256:... [EVIDENCE_DIR]" >&2
    exit 2
fi

archive="$(readlink -f "$1")"
expected_image="$2"
evidence="$(readlink -m "${3:-arm-utm-boot-proof}")"
display_backend="${MOOS_ARM_UTM_DISPLAY:-none}"
visual_hold="${MOOS_ARM_UTM_VISUAL_HOLD:-0}"
[[ "$expected_image" =~ ^ghcr\.io/moalfarras-sys/moos-arm@sha256:[0-9a-f]{64}$ ]] || {
    echo "ARM UTM FATAL: expected image is not the official digest reference" >&2
    exit 1
}
[ -f "$archive" ] || { echo "ARM UTM FATAL: missing archive: $archive" >&2; exit 1; }
case "$display_backend" in
    none) qemu_display=( -display none ) ;;
    gtk)
        [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] || {
            echo "ARM UTM FATAL: GTK mode needs a graphical host session" >&2
            exit 1
        }
        qemu_display=( -display "gtk,gl=off,zoom-to-fit=on,show-tabs=off" )
        ;;
    *) echo "ARM UTM FATAL: MOOS_ARM_UTM_DISPLAY must be none or gtk" >&2; exit 2 ;;
esac
case "$visual_hold" in 0|1) ;; *) echo "ARM UTM FATAL: visual hold must be 0 or 1" >&2; exit 2 ;; esac
[ "$display_backend" != none ] || [ "$visual_hold" = 0 ] || {
    echo "ARM UTM FATAL: visual hold requires GTK mode" >&2
    exit 2
}

for tool in qemu-img qemu-system-aarch64 python3 socat convert isoinfo; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "ARM UTM FATAL: required tool is missing: $tool" >&2
        exit 1
    }
done

mkdir -p "$evidence"
base_tmp="${RUNNER_TEMP:-/var/tmp}"
work="$(mktemp -d -p "$base_tmp" moos-arm-utm-boot.XXXXXX)"
serial="$work/serial.raw.log"
qemu_log="$work/qemu.log"
monitor="$work/monitor.sock"
serial_socket="$work/serial.sock"
qemu_pid=""

save_evidence() {
    if [ -f "$serial" ]; then
        sed -E '/^MOOS_ARM_FIRST_BOOT_PASSWORD_BEGIN$/,/^MOOS_ARM_FIRST_BOOT_PASSWORD_END$/ {
            s/^(password=).*/\1[REDACTED]/
        }' "$serial" > "$evidence/serial.log" 2>/dev/null || true
    fi
    cp "$qemu_log" "$evidence/qemu.log" 2>/dev/null || true
    for ppm in "$work"/*.ppm; do
        [ -s "$ppm" ] || continue
        name="$(basename "${ppm%.ppm}")"
        cp "$ppm" "$evidence/${name}.ppm" 2>/dev/null || true
        convert "$ppm" "$evidence/${name}.png" 2>/dev/null || true
    done
}
stop_qemu() {
    if [ -n "$qemu_pid" ] && kill -0 "$qemu_pid" 2>/dev/null; then
        [ ! -S "$monitor" ] || printf 'quit\n' | socat - UNIX-CONNECT:"$monitor" >/dev/null 2>&1 || true
        for _ in $(seq 1 20); do kill -0 "$qemu_pid" 2>/dev/null || break; sleep 0.25; done
        kill -TERM "$qemu_pid" 2>/dev/null || true
        wait "$qemu_pid" 2>/dev/null || true
    fi
}
cleanup() {
    status=$?
    save_evidence
    stop_qemu
    case "$work" in "$base_tmp"/moos-arm-utm-boot.*) rm -rf -- "$work" ;; esac
    exit "$status"
}
trap cleanup EXIT INT TERM

# Python's stdlib extracts without an extra dependency and rejects path escapes.
python3 - "$archive" "$work" "$expected_image" <<'PY'
import hashlib
import json
import pathlib
import plistlib
import sys
import zipfile

archive_path, destination, expected_image = sys.argv[1:]
root = pathlib.Path(destination).resolve()
with zipfile.ZipFile(archive_path) as archive:
    names = set(archive.namelist())
    bundle_roots = {
        pathlib.PurePosixPath(name).parts[0]
        for name in names
        if pathlib.PurePosixPath(name).parts
        and pathlib.PurePosixPath(name).parts[0].endswith(".utm")
    }
    if len(bundle_roots) != 1:
        raise SystemExit("ARM UTM FATAL: archive must contain exactly one .utm bundle")
    bundle_name = bundle_roots.pop()
    required = {
        f"{bundle_name}/config.plist",
        f"{bundle_name}/manifest.json",
        f"{bundle_name}/Data/moos-arm.qcow2",
        f"{bundle_name}/Data/seed.iso",
    }
    if not required.issubset(names) or archive.testzip() is not None:
        raise SystemExit("ARM UTM FATAL: archive inventory or CRC is invalid")
    for info in archive.infolist():
        target = (root / info.filename).resolve()
        if root != target and root not in target.parents:
            raise SystemExit("ARM UTM FATAL: archive contains a path escape")
    archive.extractall(root)

bundle = root / bundle_name
manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
config = plistlib.loads((bundle / "config.plist").read_bytes())
if manifest.get("source_image") != expected_image:
    raise SystemExit("ARM UTM FATAL: manifest source image mismatch")
if config.get("Backend") != "QEMU" or config.get("ConfigurationVersion") != 4:
    raise SystemExit("ARM UTM FATAL: configuration is not QEMU schema v4")
if config.get("System", {}).get("Architecture") != "aarch64":
    raise SystemExit("ARM UTM FATAL: configuration is not aarch64")
memory_mib = config.get("System", {}).get("MemorySize")
cpu_count = config.get("System", {}).get("CPUCount")
hypervisor = config.get("QEMU", {}).get("Hypervisor")
jit_cache_mib = config.get("System", {}).get("JITCacheSize")
if memory_mib not in (1536, 4096) or cpu_count not in (2, 4):
    raise SystemExit("ARM UTM FATAL: CPU/RAM differs from a supported release profile")
if memory_mib == 1536:
    if cpu_count != 2 or jit_cache_mib != 64:
        raise SystemExit("ARM UTM FATAL: phone profile lost its bounded JIT cache")
    if config["QEMU"].get("Hypervisor") is not False:
        raise SystemExit("ARM UTM FATAL: phone profile incorrectly requires a hypervisor")
elif cpu_count != 4 or jit_cache_mib != 0:
    raise SystemExit("ARM UTM FATAL: desktop profile differs from its release contract")
if config["System"].get("ForceMulticore") is not False:
    raise SystemExit("ARM UTM FATAL: bundle forces an unsafe emulation mode")
if config.get("Network", [{}])[0].get("Mode") != "Emulated":
    raise SystemExit("ARM UTM FATAL: bundle lost portable QEMU networking")
if config.get("Display", [{}])[0].get("Hardware") != "virtio-ramfb":
    raise SystemExit("ARM UTM FATAL: bundle differs from UTM's aarch64 display")
if [drive.get("ImageName") for drive in config.get("Drive", [])] != ["moos-arm.qcow2", "seed.iso"]:
    raise SystemExit("ARM UTM FATAL: disk order differs from the release contract")
disk = bundle / "Data/moos-arm.qcow2"
digest = hashlib.sha256()
with disk.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
if digest.hexdigest() != manifest.get("disk", {}).get("sha256"):
    raise SystemExit("ARM UTM FATAL: extracted disk SHA does not match manifest")
(root / "bundle-name.txt").write_text(bundle_name, encoding="utf-8")
(root / "memory-mib.txt").write_text(str(memory_mib), encoding="ascii")
(root / "cpu-count.txt").write_text(str(cpu_count), encoding="ascii")
(root / "hypervisor.txt").write_text("1" if hypervisor else "0", encoding="ascii")
(root / "jit-cache-mib.txt").write_text(str(jit_cache_mib), encoding="ascii")
PY

bundle_name="$(cat "$work/bundle-name.txt")"
memory_mib="$(cat "$work/memory-mib.txt")"
cpu_count="$(cat "$work/cpu-count.txt")"
hypervisor="$(cat "$work/hypervisor.txt")"
jit_cache_mib="$(cat "$work/jit-cache-mib.txt")"
[[ "$bundle_name" =~ ^[A-Za-z0-9._-]+\.utm$ ]] \
    || { echo "ARM UTM FATAL: unsafe bundle directory name" >&2; exit 1; }
[[ "$memory_mib" =~ ^(1536|4096)$ && "$cpu_count" =~ ^(2|4)$ ]] \
    || { echo "ARM UTM FATAL: unsafe CPU/RAM profile" >&2; exit 1; }
[[ "$hypervisor" =~ ^(0|1)$ ]] \
    || { echo "ARM UTM FATAL: unsafe hypervisor profile" >&2; exit 1; }
[[ "$jit_cache_mib" =~ ^(0|64)$ ]] \
    || { echo "ARM UTM FATAL: unsafe JIT cache profile" >&2; exit 1; }
bundle="$work/$bundle_name"
qcow="$bundle/Data/moos-arm.qcow2"
seed="$bundle/Data/seed.iso"
qemu-img check "$qcow" | tee "$evidence/qcow2-check.txt"
isoinfo -d -i "$seed" | tee "$evidence/seed-iso.txt"
isoinfo -d -i "$seed" | grep -Eq '^Volume id:[[:space:]]+cidata$' || {
    echo "ARM UTM FATAL: seed volume is not cidata" >&2
    exit 1
}
isoinfo -R -i "$seed" -x /user-data > "$work/user-data"
isoinfo -R -i "$seed" -x /meta-data > "$work/meta-data"
for contract in \
    'MOOS_ARM_FIRST_BOOT_PASSWORD_BEGIN' \
    '/dev/ttyAMA0' \
    "runcmd:" \
    "ssh_pwauth: false" \
    "disable_root: true"; do
    grep -F "$contract" "$work/user-data" >/dev/null || {
        echo "ARM UTM FATAL: seed lacks contract: $contract" >&2
        exit 1
    }
done
! grep -Eq '(plain_text_passwd|hashed_passwd|password:[[:space:]]+[^$<{])' "$work/user-data" || {
    echo "ARM UTM FATAL: public seed contains a credential" >&2
    exit 1
}

qemu-img create -q -f qcow2 -F qcow2 -b "$qcow" "$work/overlay.qcow2"
firmware_code=""
firmware_vars=""
for candidate in /usr/share/AAVMF/AAVMF_CODE.no-secboot.fd /usr/share/AAVMF/AAVMF_CODE.fd; do
    [ -f "$candidate" ] && { firmware_code="$candidate"; break; }
done
for candidate in /usr/share/AAVMF/AAVMF_VARS.fd /usr/share/AAVMF/AAVMF_VARS.ms.fd; do
    [ -f "$candidate" ] && { firmware_vars="$candidate"; break; }
done
[ -n "$firmware_code" ] && [ -n "$firmware_vars" ] || {
    echo "ARM UTM FATAL: AAVMF firmware is unavailable" >&2
    exit 1
}
cp "$firmware_vars" "$work/AAVMF_VARS.fd"

if [ "$hypervisor" = 1 ] && [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
    accelerator=( -accel kvm -cpu host )
else
    tb_size="$jit_cache_mib"
    [ "$tb_size" -gt 0 ] || tb_size=$((memory_mib / 4))
    accelerator=( -accel "tcg,tb-size=${tb_size}" -cpu cortex-a72 )
fi

# UTM's QEMU-only virtio-ramfb wraps this PCI virtio GPU after firmware.
# Stock CI QEMU lacks the wrapper; config.plist was validated above and this
# equivalent device proves the guest's real post-boot scanout path.
qemu-system-aarch64 \
    -machine virt "${accelerator[@]}" -smp "$cpu_count" -m "$memory_mib" \
    -drive "if=pflash,format=raw,readonly=on,file=$firmware_code" \
    -drive "if=pflash,format=raw,file=$work/AAVMF_VARS.fd" \
    -drive "file=$work/overlay.qcow2,format=qcow2,if=virtio,cache=unsafe" \
    -drive "file=$seed,format=raw,if=virtio,readonly=on" \
    -device virtio-gpu-pci \
    -device qemu-xhci,id=usb -device usb-kbd,bus=usb.0 -device usb-tablet,bus=usb.0 \
    -audiodev driver=none,id=audio0 -device intel-hda -device hda-duplex,audiodev=audio0 \
    -netdev user,id=net0 -device virtio-net-pci,netdev=net0 \
    -chardev "socket,id=serial0,path=$serial_socket,server=on,wait=off,logfile=$serial,logappend=on" \
    -serial chardev:serial0 \
    -monitor "unix:$monitor,server=on,wait=off" \
    "${qemu_display[@]}" >"$qemu_log" 2>&1 &
qemu_pid=$!

# The controller never prints or stores the credential. Its only durable serial
# copy is redacted by save_evidence before upload.
python3 - \
    "$serial_socket" "$serial" "$monitor" "$work" "$expected_image" \
    "$qemu_pid" "$visual_hold" "$evidence/continue" <<'PY'
import os
import pathlib
import re
import socket
import sys
import time

serial_socket, serial_log, monitor_socket, work_arg, expected_image, qemu_pid, visual_hold, continue_arg = sys.argv[1:]
work = pathlib.Path(work_arg)
pid = int(qemu_pid)

def alive():
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

deadline = time.monotonic() + 1200
password = None
while time.monotonic() < deadline:
    if not alive():
        raise SystemExit("ARM UTM FATAL: QEMU exited before provisioning completed")
    text = pathlib.Path(serial_log).read_text(encoding="utf-8", errors="replace") if pathlib.Path(serial_log).exists() else ""
    match = re.search(
        r"MOOS_ARM_FIRST_BOOT_PASSWORD_BEGIN\r?\nuser=moos\r?\npassword=([A-Za-z0-9]{20})\r?\nMOOS_ARM_FIRST_BOOT_PASSWORD_END",
        text,
    )
    if match and "MOOS_ARM_FIRST_BOOT_READY" in text:
        password = match.group(1)
        break
    if re.search(r"Kernel panic|Entering emergency mode|Reached target emergency\.target", text, re.I):
        raise SystemExit("ARM UTM FATAL: emergency marker in serial log")
    time.sleep(2)
if password is None:
    raise SystemExit("ARM UTM FATAL: guest never emitted its VM-unique serial credential")

def recv_until(sock, pattern, timeout=120):
    regex = re.compile(pattern, re.S)
    data = ""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        sock.settimeout(min(1.0, max(0.1, end - time.monotonic())))
        try:
            chunk = sock.recv(65536)
        except socket.timeout:
            continue
        if not chunk:
            raise RuntimeError("serial socket closed")
        data += chunk.decode("utf-8", errors="replace")
        if regex.search(data):
            return data
    raise TimeoutError(f"serial timeout waiting for {pattern!r}")

serial = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
serial.connect(serial_socket)
serial.sendall(b"\n")
recv_until(serial, r"login:\s*$", 90)
serial.sendall(b"moos\n")
recv_until(serial, r"Password:\s*$", 30)
serial.sendall(password.encode() + b"\n")
serial.sendall(b"echo __MOOS_SERIAL_LOGIN_READY__\n")
recv_until(serial, r"__MOOS_SERIAL_LOGIN_READY__", 45)

counter = 0
def command(shell_command, timeout=120):
    global counter
    counter += 1
    marker = f"__MOOS_CMD_{counter}__"
    payload = f"({shell_command}); rc=$?; printf '\\n{marker}%s\\n' \"$rc\"\n"
    serial.sendall(payload.encode())
    output = recv_until(serial, re.escape(marker) + r"([0-9]+)\r?\n", timeout)
    match = re.search(re.escape(marker) + r"([0-9]+)\r?\n", output)
    if match is None or match.group(1) != "0":
        raise RuntimeError(f"guest command failed: {shell_command}")
    return output

checks = [
    "test \"$(uname -m)\" = aarch64",
    "test -e /run/ostree-booted",
    "cloud-init status --wait | grep -Eq 'status: (done|degraded)'",
    "systemctl is-active --quiet graphical.target display-manager.service",
    "test -z \"$(systemctl --failed --no-legend --plain)\"",
    "bootc status --json | grep -F -- " + repr(expected_image),
]
for check in checks:
    command(check, 180)

def hmp(command_text):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(monitor_socket)
    sock.settimeout(2)
    try:
        sock.recv(4096)
    except socket.timeout:
        pass
    sock.sendall((command_text + "\n").encode())
    time.sleep(0.15)
    sock.close()

def screenshot(name):
    target = work / f"{name}.ppm"
    hmp(f"screendump {target}")
    end = time.monotonic() + 20
    while time.monotonic() < end:
        if target.exists() and target.stat().st_size > 1024:
            return
        time.sleep(0.2)
    raise RuntimeError(f"empty screenshot: {name}")

def send_text(value):
    for char in value:
        if char.isupper():
            key = "shift-" + char.lower()
        else:
            key = char.lower()
        hmp("sendkey " + key)
        time.sleep(0.035)

# The PLM card deliberately sleeps after inactivity. Wake it, capture the real
# greeter, then use its focused password field instead of bypassing PAM.
hmp("sendkey shift")
time.sleep(2)
screenshot("utm-login")
hmp("sendkey ctrl-a")
send_text(password)
hmp("sendkey ret")

desktop_deadline = time.monotonic() + 240
while time.monotonic() < desktop_deadline:
    try:
        command("pgrep -u moos -x kwin_wayland >/dev/null && pgrep -u moos -x plasmashell >/dev/null", 15)
        break
    except Exception:
        time.sleep(3)
else:
    raise RuntimeError("Plasma desktop did not start after graphical PAM login")
time.sleep(8)
command("test -z \"$(systemctl --user --failed --no-legend --plain)\"")
screenshot("utm-desktop")

apps = [
    ("settings", "moos-settings"),
    ("moplayer", "moplayer"),
    ("remote", "mo-pc-remote"),
]
app_log = []
for name, executable in apps:
    unit_file = f"$XDG_RUNTIME_DIR/moos-utm-{name}.unit"
    command(
        "export XDG_RUNTIME_DIR=/run/user/$(id -u); "
        "export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus; "
        f"opened=$(moai-open {executable}); "
        "unit=$(printf '%s\\n' \"$opened\" | sed -n 's/.*unit \\([^)]*\\)).*/\\1/p'); "
        f"test -n \"$unit\" && printf '%s\\n' \"$unit\" > {unit_file}"
    )
    app_deadline = time.monotonic() + 90
    while time.monotonic() < app_deadline:
        try:
            command(
                "export XDG_RUNTIME_DIR=/run/user/$(id -u); "
                "export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus; "
                f"systemctl --user is-active --quiet \"$(cat {unit_file})\"",
                10,
            )
            break
        except Exception:
            time.sleep(2)
    else:
        raise RuntimeError(f"{name} did not open")
    time.sleep(3)
    screenshot("utm-app-" + name)
    hmp("sendkey alt-f4")
    close_deadline = time.monotonic() + 45
    while time.monotonic() < close_deadline:
        try:
            command(
                "export XDG_RUNTIME_DIR=/run/user/$(id -u); "
                "export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus; "
                f"! systemctl --user is-active --quiet \"$(cat {unit_file})\"",
                10,
            )
            break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError(f"{name} did not close")
    command(
        "export XDG_RUNTIME_DIR=/run/user/$(id -u); "
        "export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus; "
        f"old=$(cat {unit_file}); opened=$(moai-open {executable}); "
        "unit=$(printf '%s\\n' \"$opened\" | sed -n 's/.*unit \\([^)]*\\)).*/\\1/p'); "
        f"test -n \"$unit\" && test \"$unit\" != \"$old\" && printf '%s\\n' \"$unit\" > {unit_file}"
    )
    reopen_deadline = time.monotonic() + 90
    while time.monotonic() < reopen_deadline:
        try:
            command(
                "export XDG_RUNTIME_DIR=/run/user/$(id -u); "
                "export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus; "
                f"systemctl --user is-active --quiet \"$(cat {unit_file})\"",
                10,
            )
            break
        except Exception:
            time.sleep(2)
    else:
        raise RuntimeError(f"{name} did not reopen")
    app_log.append(f"{name}=opened-closed-reopened")
    hmp("sendkey alt-f4")
    time.sleep(1)

(work / "app-smoke.txt").write_text("\n".join(app_log) + "\n", encoding="utf-8")
(work / "runtime.txt").write_text(
    "provisioning=guest-generated-serial-credential\n"
    "login=plasma-login-manager-pam\n"
    "desktop=usable\n"
    "system-failed-units=0\n"
    "user-failed-units=0\n",
    encoding="utf-8",
)

if visual_hold == "1":
    continue_path = pathlib.Path(continue_arg)
    print(
        "ARM UTM VISUAL READY: exact public bundle is open after real login/app smoke.\n"
        f"Inspect and use it, then run: touch '{continue_path}'",
        flush=True,
    )
    while not continue_path.exists():
        if not alive():
            raise RuntimeError("visible UTM-equivalent QEMU exited during interaction")
        time.sleep(1)
    continue_path.unlink()

# Password enters sudo over the private serial socket and is never logged.
serial.sendall(b"sudo -S systemctl poweroff >/dev/null 2>&1\n")
recv_until(serial, r"password for moos", 30)
serial.sendall(password.encode() + b"\n")
password = ""
serial.close()
PY

cp "$work/runtime.txt" "$evidence/runtime.txt"
cp "$work/app-smoke.txt" "$evidence/app-smoke.txt"

deadline=$((SECONDS + 180))
while kill -0 "$qemu_pid" 2>/dev/null && [ "$SECONDS" -lt "$deadline" ]; do sleep 1; done
if kill -0 "$qemu_pid" 2>/dev/null; then
    echo "ARM UTM FATAL: guest did not power off cleanly" >&2
    exit 1
fi
wait "$qemu_pid"
qemu_pid=""
grep -q 'reboot: Power down' "$serial" || {
    echo "ARM UTM FATAL: serial lacks clean power-down proof" >&2
    exit 1
}
save_evidence
for proof in runtime.txt app-smoke.txt utm-login.png utm-desktop.png \
    utm-app-settings.png utm-app-moplayer.png utm-app-remote.png serial.log; do
    [ -s "$evidence/$proof" ] || { echo "ARM UTM FATAL: missing proof: $proof" >&2; exit 1; }
done
for frame in utm-login.png utm-desktop.png utm-app-settings.png \
    utm-app-moplayer.png utm-app-remote.png; do
    stddev="$(convert "$evidence/$frame" -colorspace gray -format '%[fx:standard_deviation]' info:)"
    python3 - "$frame" "$stddev" <<'PY'
import sys

name, value_text = sys.argv[1:]
value = float(value_text)
if value < 0.02:
    raise SystemExit(f"ARM UTM FATAL: {name} is blank/flat (stddev={value})")
print(f"{name}: visual stddev={value:.6f}")
PY
done
echo "ARM UTM BOOT OK: exact bundle, unique serial credential, PLM login, desktop, native apps and poweroff"
