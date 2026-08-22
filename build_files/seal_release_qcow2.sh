#!/usr/bin/env bash
# Inspect a BIB disk, bind it to its verified signed digest, and remove only
# builder-injected serial arguments that would leak into the released UX.
set -euo pipefail

if [ "$#" -ne 3 ]; then
    echo "usage: $0 TARGET_ARCH IMAGE.qcow2 ghcr.io/moalfarras-sys/EDITION@sha256:..." >&2
    exit 2
fi
if [ "$(id -u)" -ne 0 ]; then
    echo "MOOS DISK FATAL: sealing a QCOW2 requires root" >&2
    exit 1
fi

target_arch="$1"
qcow="$(readlink -f "$2")"
expected_image="$3"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
case "$target_arch" in arm64|x86_64) ;; *) echo "MOOS DISK FATAL: invalid target architecture" >&2; exit 2 ;; esac
[ -f "$qcow" ] || { echo "MOOS DISK FATAL: missing QCOW2: $qcow" >&2; exit 1; }
for tool in qemu-img qemu-nbd lsblk blkid mount umount udevadm python3; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "MOOS DISK FATAL: required tool is missing: $tool" >&2
        exit 1
    }
done

qemu-img check "$qcow"
modprobe nbd max_part=16
nbd=""
for candidate in /sys/class/block/nbd*; do
    [ -e "$candidate" ] || continue
    [ -s "$candidate/pid" ] && continue
    device="/dev/${candidate##*/}"
    [ -b "$device" ] || continue
    nbd="$device"
    break
done
[ -n "$nbd" ] || { echo "MOOS DISK FATAL: no free NBD device" >&2; exit 1; }
[[ "$nbd" =~ ^/dev/nbd[0-9]+$ ]] || {
    echo "MOOS DISK FATAL: refusing unexpected NBD path: $nbd" >&2
    exit 1
}

base_tmp="${RUNNER_TEMP:-/var/tmp}"
mount_root="$(mktemp -d -p "$base_tmp" moos-release-root.XXXXXX)"
mount_boot="$(mktemp -d -p "$base_tmp" moos-release-boot.XXXXXX)"
connected=0
cleanup() {
    local rc=$?
    trap - EXIT INT TERM
    set +e
    mountpoint -q "$mount_boot" && umount "$mount_boot"
    mountpoint -q "$mount_root" && umount "$mount_root"
    [ "$connected" -eq 1 ] && qemu-nbd --disconnect "$nbd" >/dev/null 2>&1
    rmdir "$mount_boot" "$mount_root" 2>/dev/null
    exit "$rc"
}
trap cleanup EXIT INT TERM

qemu-nbd --connect="$nbd" "$qcow"
connected=1
# udevadm settle alone does NOT prove the partition scan produced device
# nodes: on a runner still digesting the disk-builder's I/O, settle can
# return while the partition probe is still pending, and the 2026-08-21
# release proof failed exactly here on a disk whose GPT provably contained
# all three partitions. Ask the kernel for the nodes, then wait for them.
udevadm trigger --settle "$nbd" 2>/dev/null || udevadm trigger "$nbd" 2>/dev/null || true
for _ in $(seq 1 30); do
    partition_count="$(lsblk -rpn -o TYPE "$nbd" 2>/dev/null | grep -c '^part$' || true)"
    [ "$partition_count" -ge 3 ] && break
    udevadm settle 2>/dev/null || true
    partprobe "$nbd" >/dev/null 2>&1 || blockdev --rereadpt "$nbd" >/dev/null 2>&1 || true
    sleep 1
done
[ "$partition_count" -ge 3 ] || {
    echo "MOOS DISK FATAL: partition scan found only $partition_count partitions on $nbd" >&2
    exit 1
}
udevadm settle 2>/dev/null || true
layout_json="$(lsblk --json --paths --output NAME,TYPE,FSTYPE "$nbd")"
roles_output="$(printf '%s\n' "$layout_json" | python3 "$script_dir/resolve_release_partitions.py" --nbd "$nbd")" || exit 1
mapfile -t release_partitions <<< "$roles_output"
[ "${#release_partitions[@]}" -eq 3 ] || {
    echo "MOOS DISK FATAL: partition resolver returned an invalid result" >&2
    exit 1
}
efi="${release_partitions[0]}"
boot="${release_partitions[1]}"
root="${release_partitions[2]}"
for partition in "$efi" "$boot" "$root"; do
    [ -b "$partition" ] || {
        echo "MOOS DISK FATAL: resolved partition is missing: $partition" >&2
        exit 1
    }
done

mount -o subvol=root "$root" "$mount_root"
mount "$boot" "$mount_boot"
python3 "$script_dir/seal_arm_deployment.py" \
    --root "$mount_root" \
    --boot "$mount_boot" \
    --target-arch "$target_arch" \
    --expected-image "$expected_image"
sync -f "$mount_root"
sync -f "$mount_boot"
umount "$mount_boot"
umount "$mount_root"
qemu-nbd --disconnect "$nbd"
connected=0
qemu-img check "$qcow"
echo "MOOS DISK OK: partition layout, signed deployment origin and BLS arguments are sealed"
