#!/usr/bin/env bash
# Runs inside a booted ARM release candidate. The host boot gate pipes this file
# over SSH so the downloadable disk, not a build container, supplies every fact.
set -euo pipefail

expected="${1:-}"
[[ "$expected" =~ ^ghcr\.io/moalfarras-sys/moos-arm@sha256:[0-9a-f]{64}$ ]] || {
    echo "ARM RUNTIME FATAL: invalid expected image reference" >&2
    exit 1
}

[ "$(uname -m)" = "aarch64" ]
grep -qx 'ID=moos' /etc/os-release
cloud_status="$(cloud-init status --wait --long)"
printf '%s\n' "$cloud_status"
grep -qx 'status: done' <<<"$cloud_status"
grep -qx 'extended_status: done' <<<"$cloud_status"
[ "$(systemctl is-active graphical.target)" = "active" ]
[ "$(systemctl is-active display-manager.service)" = "active" ]
account_path="$(busctl call org.freedesktop.Accounts /org/freedesktop/Accounts \
    org.freedesktop.Accounts FindUserByName s moos)"
[[ "$account_path" == *"/org/freedesktop/Accounts/User"* ]]

# Disk growth is deliberately asynchronous: an imported volume already has
# enough room to provision the account and greeter, and partition notification
# can be slow under ARM TCG/provider storage. Wait for the retrying background
# authority before measuring the physical partition, without putting it back on
# graphical.target's critical path.
growth_deadline=$((SECONDS + 360))
while [ "$SECONDS" -lt "$growth_deadline" ]; do
    growth_active="$(systemctl is-active moos-cloud-grow-root.service 2>/dev/null || true)"
    growth_result="$(systemctl show -p Result --value moos-cloud-grow-root.service 2>/dev/null || true)"
    if [ "$growth_active" = "inactive" ] && [ "$growth_result" = "success" ]; then
        break
    fi
    sleep 3
done
[ "${growth_active:-}" = "inactive" ] && [ "${growth_result:-}" = "success" ] || {
    systemctl status --no-pager --full moos-cloud-grow-root.service >&2 || true
    journalctl --no-pager -u moos-cloud-grow-root.service -n 100 >&2 || true
    echo "ARM RUNTIME FATAL: physical sysroot growth did not complete" >&2
    exit 1
}
failed="$(systemctl --failed --no-legend --plain)"
[ -z "$failed" ] || { printf 'failed units:\n%s\n' "$failed" >&2; exit 1; }
getent hosts ghcr.io >/dev/null

origin="$(rpm-ostree status --json | python3 -c '
import json, sys
for deployment in json.load(sys.stdin).get("deployments", []):
    if deployment.get("booted"):
        print(deployment.get("container-image-reference", ""))
        break
')"
[ "$origin" = "ostree-image-signed:docker://${expected}" ]

python3 - <<'PY'
import json

with open('/etc/containers/policy.json', encoding='utf-8') as source:
    policy = json.load(source)
entry = policy['transports']['docker']['ghcr.io/moalfarras-sys']
assert len(entry) == 1 and entry[0]['type'] == 'sigstoreSigned'
assert entry[0]['keyPath'] == '/etc/pki/containers/moos.pub'
PY

sysroot="$(findmnt -nro SOURCE /sysroot)"
device="${sysroot%%\[*}"
parent="$(lsblk -dnro PKNAME "$device" | tr -d '[:space:]')"
[ -n "$parent" ]
disk="/dev/$parent"
disk_size="$(blockdev --getsize64 "$disk")"
partition_total=0
while read -r child_size; do
    partition_total=$((partition_total + child_size))
done < <(lsblk -bnro SIZE "$disk" | tail -n +2)
tail_bytes=$((disk_size - partition_total))
[ "$tail_bytes" -ge 0 ] && [ "$tail_bytes" -lt 67108864 ]
partition_size="$(blockdev --getsize64 "$device")"
btrfs_usage="$(btrfs filesystem usage -b /sysroot)"
btrfs_size="$(awk '/Device size:/ {print $3; exit}' <<<"$btrfs_usage")"
[ -n "$btrfs_size" ]
delta=$((partition_size - btrfs_size))
[ "$delta" -gt -16777216 ] && [ "$delta" -lt 16777216 ]

printf 'architecture=%s\n' "$(uname -m)"
printf 'os_id=%s\n' "$(sed -n 's/^ID=//p' /etc/os-release)"
printf 'origin=%s\n' "$origin"
printf 'cloud_init=done\n'
printf 'graphical=%s\n' "$(systemctl is-active graphical.target)"
printf 'display_manager=%s\n' "$(systemctl is-active display-manager.service)"
printf 'accounts_user=published\n'
printf 'cloud_grow=success\n'
printf 'failed_units=0\n'
printf 'disk_bytes=%s\n' "$disk_size"
printf 'partition_bytes=%s\n' "$partition_size"
printf 'btrfs_bytes=%s\n' "$btrfs_size"
printf 'tail_bytes=%s\n' "$tail_bytes"
printf 'boot_id=%s\n' "$(cat /proc/sys/kernel/random/boot_id)"
