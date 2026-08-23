#!/usr/bin/env bash
# Boot MoOS-UTM-Installer under QEMU TCG (no KVM) — installer menu + optional net install.
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "usage: $0 MoOS-UTM-Installer.utm.zip [EVIDENCE_DIR]" >&2
    exit 2
fi

archive="$(readlink -f "$1")"
evidence="$(readlink -m "${2:-utm-installer-tcg-proof}")"
[ -f "$archive" ] || { echo "UTM INSTALLER FATAL: missing $archive" >&2; exit 1; }

for tool in qemu-system-aarch64 qemu-img python3 unzip; do
    command -v "$tool" >/dev/null || { echo "UTM INSTALLER FATAL: need $tool" >&2; exit 1; }
done

mkdir -p "$evidence"
base_tmp="${RUNNER_TEMP:-/var/tmp}"
work="$(mktemp -d -p "$base_tmp" moos-utm-installer.XXXXXX)"
serial="$work/serial.log"
qemu_pid=""

cleanup() {
    status=$?
    if [ -n "$qemu_pid" ] && kill -0 "$qemu_pid" 2>/dev/null; then
        kill -TERM "$qemu_pid" 2>/dev/null || true
        wait "$qemu_pid" 2>/dev/null || true
    fi
    [ -f "$serial" ] && cp "$serial" "$evidence/serial.log" 2>/dev/null || true
    rm -rf "$work"
    exit "$status"
}
trap cleanup EXIT INT TERM

unzip -q "$archive" -d "$work/extract"
bundle="$(find "$work/extract" -name '*.utm' -type d | head -1)"
[ -n "$bundle" ] || { echo "UTM INSTALLER FATAL: no .utm bundle in zip" >&2; exit 1; }
data="$bundle/Data"
installer="$data/installer.qcow2"
target="$data/target.qcow2"
[ -f "$installer" ] || { echo "UTM INSTALLER FATAL: installer.qcow2 missing" >&2; exit 1; }

efi_code="/usr/share/edk2/aarch64/QEMU_EFI.fd"
efi_vars="$work/vars.fd"
[ -f "$efi_code" ] || efi_code="/usr/share/qemu/edk2-aarch64-code.fd"
[ -f "$efi_code" ] || { echo "UTM INSTALLER FATAL: AArch64 UEFI firmware missing" >&2; exit 1; }
cp -f "$efi_code" "$work/code.fd" 2>/dev/null || true
truncate -s 64M "$efi_vars" 2>/dev/null || dd if=/dev/zero of="$efi_vars" bs=1M count=64 status=none

: >"$serial"
echo "UTM INSTALLER: booting installer under TCG (no KVM)..."

qemu-system-aarch64 \
    -M virt,highmem=on \
    -cpu max \
    -smp 2 \
    -m 3072 \
    -accel tcg \
    -display none \
    -serial "file:$serial" \
    -monitor none \
    -drive if=pflash,format=raw,readonly=on,file="$work/code.fd" \
    -drive if=pflash,format=raw,file="$efi_vars" \
    -drive "file=$installer,if=virtio,format=qcow2" \
    -drive "file=$target,if=virtio,format=qcow2" \
    -netdev user,id=net0 \
    -device virtio-net-pci,netdev=net0 \
    -device virtio-rng-pci \
    -device virtio-gpu-pci \
    -device virtio-keyboard-pci \
    -device virtio-tablet-pci \
    -no-reboot &
qemu_pid=$!

deadline=$((SECONDS + 600))
pass_menu=0
while [ "$SECONDS" -lt "$deadline" ]; do
    if grep -q "MoOS Installer" "$serial" 2>/dev/null; then
        pass_menu=1
        break
    fi
    if ! kill -0 "$qemu_pid" 2>/dev/null; then break; fi
    sleep 5
done

kill -TERM "$qemu_pid" 2>/dev/null || true
wait "$qemu_pid" 2>/dev/null || true
qemu_pid=""

if [ "$pass_menu" -eq 1 ]; then
    echo "UTM INSTALLER TCG: installer reached MoOS Installer screen"
    echo '{"installer_menu":"pass","mode":"tcg"}' > "$evidence/result.json"
    exit 0
fi

echo "UTM INSTALLER TCG FATAL: installer menu not seen within 600s" >&2
tail -40 "$serial" >&2 || true
exit 1
