#!/usr/bin/env bash
# Boot the final ARM QCOW2 users download, provision it without a shared
# password, inspect the running system, reboot it, and power it off cleanly.
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "usage: $0 IMAGE.qcow2 ghcr.io/moalfarras-sys/moos-arm@sha256:... [EVIDENCE_DIR]" >&2
    exit 2
fi

qcow="$(readlink -f "$1")"
expected_image="$2"
evidence="$(readlink -m "${3:-arm-boot-proof}")"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
runtime_gate="$script_dir/verify_arm_runtime.sh"
[[ "$expected_image" =~ ^ghcr\.io/moalfarras-sys/moos-arm@sha256:[0-9a-f]{64}$ ]] || {
    echo "ARM BOOT FATAL: expected image is not the official digest reference" >&2
    exit 1
}
[ -f "$qcow" ] || { echo "ARM BOOT FATAL: missing QCOW2: $qcow" >&2; exit 1; }
[ -r "$runtime_gate" ] || { echo "ARM BOOT FATAL: missing runtime gate" >&2; exit 1; }

for tool in qemu-img qemu-system-aarch64 cloud-localds ssh ssh-keygen socat python3 convert; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "ARM BOOT FATAL: required tool is missing: $tool" >&2
        exit 1
    }
done

mkdir -p "$evidence"
base_tmp="${RUNNER_TEMP:-/var/tmp}"
work="$(mktemp -d -p "$base_tmp" moos-arm-boot.XXXXXX)"
serial="$work/serial.log"
qemu_log="$work/qemu.log"
monitor="$work/monitor.sock"
screenshot="$work/graphical.ppm"
qemu_pid=""

save_evidence() {
    cp "$serial" "$evidence/serial.log" 2>/dev/null || true
    cp "$qemu_log" "$evidence/qemu.log" 2>/dev/null || true
    cp "$screenshot" "$evidence/graphical.ppm" 2>/dev/null || true
    [ -s "$screenshot" ] && convert "$screenshot" "$evidence/graphical.png" 2>/dev/null || true
    qemu-img info --output=json "$qcow" > "$evidence/qcow2-info.json" 2>/dev/null || true
}
stop_qemu() {
    if [ -n "$qemu_pid" ] && kill -0 "$qemu_pid" 2>/dev/null; then
        if [ -S "$monitor" ]; then
            printf 'quit\n' | socat - UNIX-CONNECT:"$monitor" >/dev/null 2>&1 || true
        fi
        for _ in $(seq 1 20); do
            kill -0 "$qemu_pid" 2>/dev/null || break
            sleep 0.25
        done
        kill -TERM "$qemu_pid" 2>/dev/null || true
        wait "$qemu_pid" 2>/dev/null || true
    fi
}
cleanup() {
    status=$?
    save_evidence
    stop_qemu
    case "$work" in
        "$base_tmp"/moos-arm-boot.*) rm -rf -- "$work" ;;
    esac
    exit "$status"
}
trap cleanup EXIT INT TERM

qemu-img check "$qcow" | tee "$evidence/qcow2-check.txt"
qemu-img create -q -f qcow2 -F qcow2 -b "$qcow" "$work/overlay.qcow2"
base_size="$(qemu-img info --output=json "$qcow" | python3 -c 'import json,sys; print(json.load(sys.stdin)["virtual-size"])')"
# Prove first-boot growth on a disposable overlay; never alter the artifact.
qemu-img resize -q "$work/overlay.qcow2" "$((base_size + 1073741824))"

ssh-keygen -q -t ed25519 -N '' -f "$work/id_ed25519"
public_key="$(cat "$work/id_ed25519.pub")"
cat > "$work/user-data" <<EOF
#cloud-config
users:
  - name: moos
    gecos: MoOS ARM release gate
    groups: [wheel]
    shell: /bin/bash
    lock_passwd: true
    ssh_authorized_keys:
      - ${public_key}
disable_root: true
ssh_pwauth: false
write_files:
  - path: /etc/sudoers.d/99-moos-arm-release-gate
    owner: root:root
    permissions: '0440'
    content: |
      moos ALL=(root) NOPASSWD: /usr/bin/systemctl reboot, /usr/bin/systemctl poweroff
final_message: MOOS_ARM_CLOUD_INIT_COMPLETE
EOF
cat > "$work/meta-data" <<EOF
instance-id: moos-arm-release-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}
local-hostname: moos-arm-release
EOF
cloud-localds "$work/seed.iso" "$work/user-data" "$work/meta-data"

firmware_code=""
firmware_vars=""
for candidate in /usr/share/AAVMF/AAVMF_CODE.no-secboot.fd /usr/share/AAVMF/AAVMF_CODE.fd; do
    [ -f "$candidate" ] && { firmware_code="$candidate"; break; }
done
for candidate in /usr/share/AAVMF/AAVMF_VARS.fd /usr/share/AAVMF/AAVMF_VARS.ms.fd; do
    [ -f "$candidate" ] && { firmware_vars="$candidate"; break; }
done
[ -n "$firmware_code" ] && [ -n "$firmware_vars" ] || {
    echo "ARM BOOT FATAL: AAVMF UEFI firmware is unavailable" >&2
    exit 1
}
cp "$firmware_vars" "$work/AAVMF_VARS.fd"

port="${MOOS_ARM_SSH_PORT:-2222}"
python3 - "$port" <<'PY'
import socket
import sys

with socket.socket() as sock:
    sock.bind(("127.0.0.1", int(sys.argv[1])))
PY

if [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
    accelerator=( -accel kvm -cpu host )
else
    accelerator=( -accel "tcg,thread=multi" -cpu cortex-a72 )
fi

qemu-system-aarch64 \
    -machine virt "${accelerator[@]}" -smp 4 -m 4096 \
    -drive "if=pflash,format=raw,readonly=on,file=$firmware_code" \
    -drive "if=pflash,format=raw,file=$work/AAVMF_VARS.fd" \
    -drive "file=$work/overlay.qcow2,format=qcow2,if=virtio,cache=unsafe" \
    -drive "file=$work/seed.iso,format=raw,if=virtio,readonly=on" \
    -device virtio-gpu-pci \
    -netdev "user,id=net0,hostfwd=tcp:127.0.0.1:${port}-:22" \
    -device virtio-net-pci,netdev=net0 \
    -serial "file:$serial" \
    -monitor "unix:$monitor,server=on,wait=off" \
    -display none >"$qemu_log" 2>&1 &
qemu_pid=$!

ssh_base=(
    ssh -p "$port" -i "$work/id_ed25519"
    -o BatchMode=yes -o IdentitiesOnly=yes
    -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
    -o ConnectTimeout=5 -o ServerAliveInterval=5
    moos@127.0.0.1
)
fatal_serial_pattern='Kernel panic|Entering emergency mode|You are in emergency mode|dracut.*emergency|Dependency failed for .*sysroot|Started emergency\.service|Reached target emergency\.target'
wait_for_ssh() {
    deadline=$((SECONDS + 900))
    while [ "$SECONDS" -lt "$deadline" ]; do
        kill -0 "$qemu_pid" 2>/dev/null || {
            echo "ARM BOOT FATAL: QEMU exited before SSH became usable" >&2
            return 1
        }
        if [ -s "$serial" ] && grep -E "$fatal_serial_pattern" "$serial" >/dev/null; then
            echo "ARM BOOT FATAL: fatal boot marker in serial log" >&2
            return 1
        fi
        if "${ssh_base[@]}" true >/dev/null 2>&1; then
            return 0
        fi
        sleep 3
    done
    echo "ARM BOOT FATAL: SSH did not become usable within 15 minutes" >&2
    return 1
}

wait_for_ssh
run_runtime_gate() {
    local phase="$1"
    local output="$evidence/runtime-${phase}-boot.txt"
    local diagnostics="$evidence/runtime-${phase}-diagnostics.txt"
    if "${ssh_base[@]}" bash -s -- "$expected_image" < "$runtime_gate" >"$output" 2>&1; then
        cat "$output"
        return 0
    fi
    cat "$output" >&2
    "${ssh_base[@]}" 'cloud-init status --long; systemctl status --no-pager --full bootc-generic-growpart.service; journalctl --no-pager -u bootc-generic-growpart.service -n 150; findmnt /sysroot; lsblk -o NAME,TYPE,PKNAME,PARTN,SIZE,FSTYPE,MOUNTPOINTS; btrfs filesystem usage -b /sysroot; systemctl --failed --no-pager --plain' \
        >"$diagnostics" 2>&1 || true
    cat "$diagnostics" >&2
    echo "ARM BOOT FATAL: ${phase}-boot runtime gate failed" >&2
    return 1
}

run_runtime_gate first
runtime="$(cat "$evidence/runtime-first-boot.txt")"
first_boot_id="$(printf '%s\n' "$runtime" | sed -n 's/^boot_id=//p')"
[ -n "$first_boot_id" ] || { echo "ARM BOOT FATAL: first boot ID was not captured" >&2; exit 1; }

for _ in $(seq 1 60); do [ -S "$monitor" ] && break; sleep 0.25; done
[ -S "$monitor" ] || { echo "ARM BOOT FATAL: QEMU monitor is unavailable" >&2; exit 1; }
printf 'screendump %s\n' "$screenshot" | socat - UNIX-CONNECT:"$monitor" >/dev/null
[ -s "$screenshot" ] || { echo "ARM BOOT FATAL: graphical screendump is empty" >&2; exit 1; }
convert "$screenshot" "$evidence/graphical.png"
[ -s "$evidence/graphical.png" ] || { echo "ARM BOOT FATAL: graphical PNG evidence is empty" >&2; exit 1; }

"${ssh_base[@]}" sudo -n /usr/bin/systemctl reboot >/dev/null 2>&1 || true
went_down=0
for _ in $(seq 1 90); do
    if ! "${ssh_base[@]}" true >/dev/null 2>&1; then went_down=1; break; fi
    sleep 1
done
[ "$went_down" -eq 1 ] || { echo "ARM BOOT FATAL: guest did not leave SSH for reboot" >&2; exit 1; }
wait_for_ssh
run_runtime_gate second
runtime="$(cat "$evidence/runtime-second-boot.txt")"
second_boot_id="$(printf '%s\n' "$runtime" | sed -n 's/^boot_id=//p')"
[ -n "$second_boot_id" ] && [ "$second_boot_id" != "$first_boot_id" ] || {
    echo "ARM BOOT FATAL: reboot returned the original boot ID" >&2
    exit 1
}

"${ssh_base[@]}" sudo -n /usr/bin/systemctl poweroff >/dev/null 2>&1 || true
deadline=$((SECONDS + 180))
while kill -0 "$qemu_pid" 2>/dev/null && [ "$SECONDS" -lt "$deadline" ]; do sleep 1; done
if kill -0 "$qemu_pid" 2>/dev/null; then
    echo "ARM BOOT FATAL: guest did not power off cleanly" >&2
    exit 1
fi
wait "$qemu_pid"
qemu_pid=""

if grep -E "$fatal_serial_pattern" "$serial" >/dev/null; then
    echo "ARM BOOT FATAL: fatal marker appeared in the completed serial log" >&2
    exit 1
fi
grep -q 'reboot: Power down' "$serial" || {
    echo "ARM BOOT FATAL: serial log lacks clean kernel power-down proof" >&2
    exit 1
}
save_evidence
echo "ARM QCOW2 BOOT OK: UEFI, signed OSTree root, cloud provisioning, network, graphical login, growth, reboot and poweroff"
