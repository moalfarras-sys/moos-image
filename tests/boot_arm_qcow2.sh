#!/usr/bin/env bash
# Boot the final ARM QCOW2 users download, provision it without a shared
# password, inspect the running system, reboot it, and power it off cleanly.
#
# CI remains headless by default. Developers can see and use the same proof VM:
#   MOOS_ARM_DISPLAY=gtk MOOS_ARM_VISUAL_HOLD=1 \
#     tests/boot_arm_qcow2.sh IMAGE.qcow2 IMAGE@sha256:... EVIDENCE_DIR
# The visual login password is random, exists only in the disposable overlay,
# and is printed once. Touch EVIDENCE_DIR/continue after interactive QA to let
# the normal reboot/second-boot/poweroff proof resume.
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
display_backend="${MOOS_ARM_DISPLAY:-none}"
visual_hold="${MOOS_ARM_VISUAL_HOLD:-0}"
case "$display_backend" in
    none) qemu_display=( -display none ) ;;
    gtk)
        [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] || {
            echo "ARM BOOT FATAL: GTK visual mode needs a graphical host session" >&2
            exit 1
        }
        qemu_display=( -display "gtk,gl=off,zoom-to-fit=on,show-tabs=off" )
        ;;
    *)
        echo "ARM BOOT FATAL: MOOS_ARM_DISPLAY must be 'none' or 'gtk'" >&2
        exit 2
        ;;
esac
case "$visual_hold" in
    0|1) ;;
    *) echo "ARM BOOT FATAL: MOOS_ARM_VISUAL_HOLD must be 0 or 1" >&2; exit 2 ;;
esac
[ "$display_backend" != none ] || [ "$visual_hold" = 0 ] || {
    echo "ARM BOOT FATAL: visual hold requires MOOS_ARM_DISPLAY=gtk" >&2
    exit 2
}
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
lock_password=true
visual_password=""
visual_password_field=""
if [ "$display_backend" != none ]; then
    visual_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(15))')"
    lock_password=false
    # Put the password in the users record that unlocks the account. A separate
    # chpasswd module runs later, so cloud-init 26 reports the earlier
    # lock_passwd:false record as degraded even when chpasswd eventually fixes
    # it. The visual gate must not invent a warning the release image does not
    # have. URL-safe output has no YAML metacharacters.
    visual_password_field="    plain_text_passwd: ${visual_password}"
fi
cat > "$work/user-data" <<EOF
#cloud-config
users:
  - name: moos
    gecos: MoOS ARM release gate
    groups: [wheel]
    shell: /bin/bash
    lock_passwd: ${lock_password}
${visual_password_field}
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
if [ -n "$visual_password" ]; then
    printf '%s\n' \
        "ARM VISUAL LOGIN: user=moos password=${visual_password}" \
        "ARM VISUAL NOTE: credential exists only in this disposable proof overlay"
fi
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
    -device virtio-keyboard-pci \
    -device virtio-tablet-pci \
    -netdev "user,id=net0,hostfwd=tcp:127.0.0.1:${port}-:22" \
    -device virtio-net-pci,netdev=net0 \
    -serial "file:$serial" \
    -monitor "unix:$monitor,server=on,wait=off" \
    "${qemu_display[@]}" >"$qemu_log" 2>&1 &
qemu_pid=$!

ssh_base=(
    ssh -p "$port" -i "$work/id_ed25519"
    -o BatchMode=yes -o IdentitiesOnly=yes
    -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
    -o ConnectTimeout=5 -o ServerAliveInterval=5
    moos@127.0.0.1
)
fatal_serial_pattern='Kernel panic|Entering emergency mode|You are in emergency mode|dracut.*emergency|Dependency failed for .*sysroot|emergency\.service|emergency\.target'
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

if ! run_runtime_gate first; then
    if [ "$visual_hold" = 1 ]; then
        continue_file="$evidence/continue"
        printf '%s\n' \
            "ARM VISUAL FAILED: the GTK window is intentionally left open for diagnosis." \
            "Inspect the screen/journal, then run: touch '$continue_file'"
        while [ ! -e "$continue_file" ]; do
            kill -0 "$qemu_pid" 2>/dev/null || break
            sleep 1
        done
        [ ! -e "$continue_file" ] || unlink "$continue_file"
    fi
    exit 1
fi
runtime="$(cat "$evidence/runtime-first-boot.txt")"
first_boot_id="$(printf '%s\n' "$runtime" | sed -n 's/^boot_id=//p')"
[ -n "$first_boot_id" ] || { echo "ARM BOOT FATAL: first boot ID was not captured" >&2; exit 1; }

for _ in $(seq 1 60); do [ -S "$monitor" ] && break; sleep 0.25; done
[ -S "$monitor" ] || { echo "ARM BOOT FATAL: QEMU monitor is unavailable" >&2; exit 1; }
# Plasma Login Manager hides the authentication form after idle timeout.
# A headless screendump taken without waking it can be a black frame with only
# the cursor while runtime still reports graphical=active — that already shipped
# as false visual proof for freeze 70aff7a9. Wake the greeter the same way the
# UTM interactive gate does, then reject flat captures.
printf 'sendkey shift\n' | socat - UNIX-CONNECT:"$monitor" >/dev/null
printf 'sendkey spc\n' | socat - UNIX-CONNECT:"$monitor" >/dev/null
sleep 5
guest_ppm="$work/graphical-guest.ppm"
guest_capture_ok=0
if printf 'screendump %s\n' "$guest_ppm" | socat - UNIX-CONNECT:"$monitor" >/dev/null 2>&1 \
    && [ -s "$guest_ppm" ]; then
    convert "$guest_ppm" "$evidence/graphical.png"
    guest_capture_ok=1
fi
if [ "$guest_capture_ok" -eq 0 ]; then
    echo "ARM BOOT FATAL: QEMU monitor screendump produced no frame" >&2
    exit 1
fi
[ -s "$evidence/graphical.png" ] || { echo "ARM BOOT FATAL: graphical PNG evidence is empty" >&2; exit 1; }
stddev="$(convert "$evidence/graphical.png" -colorspace gray -format '%[fx:standard_deviation]' info:)"
if [ "${MOOS_ARM_SKIP_VISUAL_GATE:-0}" = 1 ]; then
    echo "ARM VISUAL SKIP: stddev gate bypassed (MOOS_ARM_SKIP_VISUAL_GATE=1)"
else
python3 - "$stddev" <<'PY'
import sys
value = float(sys.argv[1])
# 0.01 still passes a near-black cursor-only frame (freeze 70aff7a9 measured
# ~0.011). Real MoOS greeter/desktop frames are well above 0.04.
if value < 0.02:
    raise SystemExit(f"ARM BOOT FATAL: graphical evidence is blank/flat (stddev={value})")
print(f"graphical screenshot stddev={value:.6f}")
PY
fi

if [ "$visual_hold" = 1 ]; then
    continue_file="$evidence/continue"
    printf '%s\n' \
        "ARM VISUAL READY: MoOS reached its runtime gate and the GTK window will stay open." \
        "Use the desktop, then run: touch '$continue_file'"
    while [ ! -e "$continue_file" ]; do
        kill -0 "$qemu_pid" 2>/dev/null || {
            echo "ARM BOOT FATAL: visible QEMU exited during interactive QA" >&2
            exit 1
        }
        sleep 1
    done
    unlink "$continue_file"
fi

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
