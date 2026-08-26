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

for tool in qemu-system-aarch64 qemu-img python3 socat convert; do
    command -v "$tool" >/dev/null || { echo "UTM INSTALLER FATAL: need $tool" >&2; exit 1; }
done

mkdir -p "$evidence"
base_tmp="${RUNNER_TEMP:-/var/tmp}"
work="$(mktemp -d -p "$base_tmp" moos-utm-installer.XXXXXX)"
serial="$work/serial.log"
monitor="$work/monitor.sock"
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

python3 - "$archive" "$work/extract" <<'PY'
import pathlib
import sys
import zipfile

archive_path, destination = sys.argv[1:]
root = pathlib.Path(destination).resolve()
root.mkdir()
with zipfile.ZipFile(archive_path) as archive:
    names = set(archive.namelist())
    roots = {
        pathlib.PurePosixPath(name).parts[0]
        for name in names
        if pathlib.PurePosixPath(name).parts
        and pathlib.PurePosixPath(name).parts[0].endswith(".utm")
    }
    if len(roots) != 1 or archive.testzip() is not None:
        raise SystemExit("UTM INSTALLER FATAL: archive root or CRC is invalid")
    bundle_name = roots.pop()
    required = {
        f"{bundle_name}/config.plist",
        f"{bundle_name}/Data/installer.qcow2",
        f"{bundle_name}/Data/target.qcow2",
        f"{bundle_name}/Data/seed.iso",
        f"{bundle_name}/Data/moos-icon.png",
    }
    if not required.issubset(names):
        raise SystemExit("UTM INSTALLER FATAL: archive inventory is incomplete")
    for info in archive.infolist():
        target = (root / info.filename).resolve()
        if root != target and root not in target.parents:
            raise SystemExit("UTM INSTALLER FATAL: archive contains a path escape")
    archive.extractall(root)
(root / "bundle-name.txt").write_text(bundle_name, encoding="utf-8")
PY
bundle_name="$(cat "$work/extract/bundle-name.txt")"
[[ "$bundle_name" =~ ^[A-Za-z0-9._-]+\.utm$ ]] \
    || { echo "UTM INSTALLER FATAL: unsafe bundle directory name" >&2; exit 1; }
bundle="$work/extract/$bundle_name"
data="$bundle/Data"
installer="$data/installer.qcow2"
target="$data/target.qcow2"
[ -f "$installer" ] || { echo "UTM INSTALLER FATAL: installer.qcow2 missing" >&2; exit 1; }
[ -f "$target" ] || { echo "UTM INSTALLER FATAL: target.qcow2 missing" >&2; exit 1; }

python3 - "$bundle/config.plist" <<'PY'
import pathlib
import plistlib
import sys

config = plistlib.loads(pathlib.Path(sys.argv[1]).read_bytes())
system = config.get("System", {})
qemu = config.get("QEMU", {})
network = config.get("Network", [])
drives = [drive.get("ImageName") for drive in config.get("Drive", [])]
if config.get("Backend") != "QEMU" or config.get("ConfigurationVersion") != 4:
    raise SystemExit("UTM INSTALLER FATAL: bundle is not QEMU schema v4")
if system.get("Architecture") != "aarch64" or system.get("Target") != "virt":
    raise SystemExit("UTM INSTALLER FATAL: bundle is not an aarch64 virt machine")
if system.get("MemorySize") != 1536 or system.get("CPUCount") != 2:
    raise SystemExit("UTM INSTALLER FATAL: phone profile is not 1.5 GiB / 2 CPU")
if system.get("JITCacheSize") != 64 or system.get("ForceMulticore") is not False:
    raise SystemExit("UTM INSTALLER FATAL: bounded iPhone TCG profile was lost")
if qemu.get("Hypervisor") is not False or qemu.get("UEFIBoot") is not True:
    raise SystemExit("UTM INSTALLER FATAL: iPhone UEFI/emulation contract was lost")
if not network or network[0].get("Mode") != "Emulated":
    raise SystemExit("UTM INSTALLER FATAL: iPhone portable NAT mode was lost")
if config.get("Display") != [{
    "Hardware": "virtio-ramfb",
    "DynamicResolution": False,
    "NativeResolution": False,
    "UpscalingFilter": "Linear",
    "DownscalingFilter": "Linear",
}]:
    raise SystemExit("UTM INSTALLER FATAL: iPhone display differs from UTM aarch64 default")
if drives != ["installer.qcow2", "target.qcow2", "seed.iso"]:
    raise SystemExit("UTM INSTALLER FATAL: installer drive order changed")
PY

qemu-img check "$installer" | tee "$evidence/installer-qcow2-check.txt"
qemu-img check "$target" | tee "$evidence/target-qcow2-check.txt"

efi_code=""
efi_vars_source=""
for candidate in \
    /usr/share/AAVMF/AAVMF_CODE.no-secboot.fd \
    /usr/share/AAVMF/AAVMF_CODE.fd \
    /usr/share/edk2/aarch64/QEMU_EFI.fd \
    /usr/share/qemu/edk2-aarch64-code.fd; do
    [ -f "$candidate" ] && { efi_code="$candidate"; break; }
done
for candidate in /usr/share/AAVMF/AAVMF_VARS.fd /usr/share/AAVMF/AAVMF_VARS.ms.fd; do
    [ -f "$candidate" ] && { efi_vars_source="$candidate"; break; }
done
[ -n "$efi_code" ] || { echo "UTM INSTALLER FATAL: AArch64 UEFI firmware missing" >&2; exit 1; }
efi_vars="$work/vars.fd"
if [ -n "$efi_vars_source" ]; then
    cp "$efi_vars_source" "$efi_vars"
else
    truncate -s "$(stat -c %s "$efi_code")" "$efi_vars"
fi

: >"$serial"
echo "UTM INSTALLER: booting installer under TCG (no KVM)..."

qemu-system-aarch64 \
    -M virt,highmem=on \
    -cpu max \
    -smp 2 \
    -m 1536 \
    -accel "tcg,tb-size=64" \
    -display none \
    -serial "file:$serial" \
    -monitor "unix:$monitor,server=on,wait=off" \
    -drive if=pflash,format=raw,readonly=on,file="$efi_code" \
    -drive if=pflash,format=raw,file="$efi_vars" \
    -drive "file=$installer,if=virtio,format=qcow2" \
    -drive "file=$target,if=virtio,format=qcow2" \
    -netdev user,id=net0 \
    -device virtio-net-pci,netdev=net0 \
    -device virtio-rng-pci \
    -device virtio-ramfb \
    -device virtio-keyboard-pci \
    -device virtio-tablet-pci \
    -no-reboot &
qemu_pid=$!

deadline=$((SECONDS + 600))
pass_menu=0
while [ "$SECONDS" -lt "$deadline" ]; do
    if grep -Eq '^MOOS_UTM_INSTALLER_MENU_READY\r?$' "$serial" 2>/dev/null; then
        pass_menu=1
        break
    fi
    if ! kill -0 "$qemu_pid" 2>/dev/null; then break; fi
    sleep 5
done

if [ "$pass_menu" -eq 1 ]; then
    for _ in $(seq 1 40); do [ -S "$monitor" ] && break; sleep 0.25; done
    [ -S "$monitor" ] || { echo "UTM INSTALLER FATAL: QEMU monitor missing" >&2; exit 1; }
    sleep 8
    printf 'sendkey shift\n' | socat - UNIX-CONNECT:"$monitor" >/dev/null
    sleep 2
    printf 'screendump %s\n' "$work/installer-menu.ppm" \
        | socat - UNIX-CONNECT:"$monitor" >/dev/null
    [ -s "$work/installer-menu.ppm" ] \
        || { echo "UTM INSTALLER FATAL: installer screenshot missing" >&2; exit 1; }
    convert "$work/installer-menu.ppm" "$evidence/installer-menu.png"
    stddev="$(convert "$evidence/installer-menu.png" -colorspace gray \
        -format '%[fx:standard_deviation]' info:)"
    python3 - "$stddev" <<'PY'
import sys

value = float(sys.argv[1])
if value < 0.02:
    raise SystemExit(f"UTM INSTALLER FATAL: installer screen is blank/flat (stddev={value})")
print(f"installer visual stddev={value:.6f}")
PY
    ! grep -Eqi 'Kernel panic|Entering emergency mode|Reached target emergency\.target' "$serial" \
        || { echo "UTM INSTALLER FATAL: emergency marker in serial log" >&2; exit 1; }
    echo "UTM INSTALLER TCG: installer reached a visible MoOS Installer screen"
    printf '{"installer_menu":"pass","mode":"tcg","memory_mib":1536}\n' \
        > "$evidence/result.json"
else
    echo "UTM INSTALLER TCG FATAL: installer menu not seen within 600s" >&2
    tail -40 "$serial" >&2 || true
    exit 1
fi

kill -TERM "$qemu_pid" 2>/dev/null || true
wait "$qemu_pid" 2>/dev/null || true
qemu_pid=""
exit 0
