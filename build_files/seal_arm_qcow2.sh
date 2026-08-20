#!/usr/bin/env bash
# Mount a bootc-image-builder ARM QCOW2, seal its exact signed origin, and
# remove builder-injected foreign kernel arguments before release.
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "usage: $0 IMAGE.qcow2 ghcr.io/moalfarras-sys/moos-arm@sha256:..." >&2
    exit 2
fi
if [ "$(id -u)" -ne 0 ]; then
    echo "ARM DISK FATAL: sealing a QCOW2 requires root" >&2
    exit 1
fi

qcow="$(readlink -f "$1")"
expected_image="$2"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

[ -f "$qcow" ] || { echo "ARM DISK FATAL: missing QCOW2: $qcow" >&2; exit 1; }
for tool in qemu-img qemu-nbd lsblk blkid mount umount udevadm python3; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "ARM DISK FATAL: required tool is missing: $tool" >&2
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
[ -n "$nbd" ] || { echo "ARM DISK FATAL: no free NBD device" >&2; exit 1; }
[[ "$nbd" =~ ^/dev/nbd[0-9]+$ ]] || {
    echo "ARM DISK FATAL: refusing unexpected NBD path: $nbd" >&2
    exit 1
}

mount_root="$(mktemp -d -p "${RUNNER_TEMP:-/var/tmp}" moos-arm-root.XXXXXX)"
mount_boot="$(mktemp -d -p "${RUNNER_TEMP:-/var/tmp}" moos-arm-boot.XXXXXX)"
connected=0
cleanup() {
    set +e
    mountpoint -q "$mount_boot" && umount "$mount_boot"
    mountpoint -q "$mount_root" && umount "$mount_root"
    [ "$connected" -eq 1 ] && qemu-nbd --disconnect "$nbd" >/dev/null 2>&1
    rmdir "$mount_boot" "$mount_root" 2>/dev/null
}
trap cleanup EXIT INT TERM

qemu-nbd --connect="$nbd" "$qcow"
connected=1
udevadm settle

efi="${nbd}p1"
boot="${nbd}p2"
root="${nbd}p3"
for partition in "$efi" "$boot" "$root"; do
    [ -b "$partition" ] || {
        echo "ARM DISK FATAL: expected partition is missing: $partition" >&2
        exit 1
    }
done
[ "$(blkid -o value -s TYPE "$efi")" = "vfat" ] || {
    echo "ARM DISK FATAL: partition 1 is not the EFI filesystem" >&2; exit 1;
}
[ "$(blkid -o value -s TYPE "$boot")" = "ext4" ] || {
    echo "ARM DISK FATAL: partition 2 is not the boot filesystem" >&2; exit 1;
}
[ "$(blkid -o value -s TYPE "$root")" = "btrfs" ] || {
    echo "ARM DISK FATAL: partition 3 is not the btrfs sysroot" >&2; exit 1;
}

mount -o subvol=root "$root" "$mount_root"
mount "$boot" "$mount_boot"
python3 "$script_dir/seal_arm_deployment.py" \
    --root "$mount_root" \
    --boot "$mount_boot" \
    --expected-image "$expected_image"
sync -f "$mount_root"
sync -f "$mount_boot"
umount "$mount_boot"
umount "$mount_root"
qemu-nbd --disconnect "$nbd"
connected=0
qemu-img check "$qcow"
echo "ARM DISK OK: partition layout, signed deployment origin and BLS arguments are sealed"
