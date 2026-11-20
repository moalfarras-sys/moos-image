#!/usr/bin/env bash
# Read only PID 1's unit events from the stopped CI guest. A diagnostic error
# is recorded separately from the original boot refusal.
set -euo pipefail
[[ ${GITHUB_ACTIONS:-} == true && $EUID == 0 && $# == 1 ]]
overlay=$(realpath -e -- "$1")
[[ $overlay == /var/tmp/moos-recovery-*/installer.qcow2 && -f $overlay ]]
[[ $(readlink /proc/self/ns/mnt) != "$(readlink /proc/1/ns/mnt)" ]]
modprobe nbd max_part=16
mount_dir=$(mktemp -d)
connected=
cleanup() {
    if mountpoint -q "$mount_dir"; then umount "$mount_dir" || return 1; fi
    if [[ -n $connected ]]; then qemu-nbd --disconnect "$connected" >/dev/null; fi
    rmdir "$mount_dir"
}
trap cleanup EXIT
for node in /sys/class/block/nbd*; do
    [[ ${node##*/} =~ ^nbd[0-9]+$ && ! -s $node/pid && -b /dev/${node##*/} ]] || continue
    if qemu-nbd --read-only --format=qcow2 --connect="/dev/${node##*/}" "$overlay"; then
        connected=/dev/${node##*/}
        break
    fi
done
[[ -n $connected ]]
part=${connected}p3
for _ in {1..40}; do [[ -b $part ]] && break; sleep 0.25; done
[[ -b $part && $(blkid -s TYPE -o value "$part") == btrfs ]]
mount -t btrfs -o ro,nologreplay,nodev,nosuid,noexec,subvol=root "$part" "$mount_dir"
shopt -s nullglob
files=("$mount_dir"/ostree/deploy/*/var/log/journal/*/system.journal)
[[ ${#files[@]} == 1 && $(realpath -e -- "${files[0]}") == "$mount_dir"/* && ! -L ${files[0]} ]]
units=(moos-utm-installer.service getty@tty1.service serial-getty@ttyAMA0.service
       plymouth-quit.service cloud-final.service moos-arm-block-coldplug.service)
matches=()
for unit in "${units[@]}"; do
    if (( ${#matches[@]} )); then matches+=(+); fi
    matches+=(_PID=1 "UNIT=$unit")
done
journalctl --file="${files[0]}" --quiet --no-pager -o short-monotonic -n 160 "${matches[@]}"
