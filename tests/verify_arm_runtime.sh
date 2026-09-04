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
set +e
cloud_status="$(cloud-init status --wait --long 2>&1)"
cloud_status_rc=$?
set -e
printf '%s\n' "$cloud_status"
[ "$cloud_status_rc" -eq 0 ] || {
    echo "ARM RUNTIME FATAL: cloud-init reported a degraded/error state (rc=$cloud_status_rc)" >&2
    exit 1
}
grep -qx 'status: done' <<<"$cloud_status"
grep -qx 'extended_status: done' <<<"$cloud_status"
[ "$(systemctl is-active graphical.target)" = "active" ]
[ "$(systemctl is-active display-manager.service)" = "active" ]
account_path="$(busctl call org.freedesktop.Accounts /org/freedesktop/Accounts \
    org.freedesktop.Accounts FindUserByName s moos)"
[[ "$account_path" == *"/org/freedesktop/Accounts/User"* ]]

# A visible greeter without keyboard/pointer devices is not an interactive
# operating system. The first visual ARM run exposed that the old QEMU gate
# reached graphical.target while QEMU itself reported no mouse devices and
# the user could not log in. Prove the exact release VM exposes both input
# classes to the guest before calling its graphical path usable.
input_devices="$(cat /proc/bus/input/devices)"
grep -Fqi 'QEMU Virtio Keyboard' <<<"$input_devices" || {
    echo "ARM RUNTIME FATAL: QEMU virtio keyboard is unavailable" >&2
    exit 1
}
grep -Fqi 'QEMU Virtio Tablet' <<<"$input_devices" || {
    echo "ARM RUNTIME FATAL: QEMU virtio tablet is unavailable" >&2
    exit 1
}

# Fedora bootc is the single physical disk-growth authority. Its stock service
# is Type=simple in the Fedora 44 image, so local-fs.target may continue while
# the helper is still running. Wait for that one owner before measuring the
# partition; never race it with a second growpart implementation.
growth_deadline=$((SECONDS + 360))
while [ "$SECONDS" -lt "$growth_deadline" ]; do
    growth_active="$(systemctl is-active bootc-generic-growpart.service 2>/dev/null || true)"
    growth_result="$(systemctl show -p Result --value bootc-generic-growpart.service 2>/dev/null || true)"
    growth_status="$(systemctl show -p ExecMainStatus --value bootc-generic-growpart.service 2>/dev/null || true)"
    if [ "$growth_active" = "inactive" ] && [ "$growth_result" = "success" ]; then
        break
    fi
    sleep 3
done
[ "${growth_active:-}" = "inactive" ] && [ "${growth_result:-}" = "success" ] || {
    systemctl status --no-pager --full bootc-generic-growpart.service >&2 || true
    journalctl --no-pager -u bootc-generic-growpart.service -n 100 >&2 || true
    echo "ARM RUNTIME FATAL: physical sysroot growth did not complete" >&2
    exit 1
}
[ "${growth_status:-}" = "0" ]
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
assert policy['default'] == [{'type': 'reject'}]
assert policy['transports']['containers-storage'][''] == [
    {'type': 'insecureAcceptAnything'}
]
PY

# Prove the downloadable disk retained the native first-party bundles and all
# of their dynamic linkage. Launching GUI windows belongs to the provisioned
# desktop session; this gate runs over SSH at the greeter, so it verifies the
# executable/runtime boundary without faking a second compositor.
for app in /usr/lib/moplayer/moplayer /usr/lib/mo-remote/MoRemotePersonal; do
    [ -x "$app" ]
    python3 - "$app" <<'PY'
import pathlib
import sys

header = pathlib.Path(sys.argv[1]).read_bytes()[:20]
assert header[:4] == b"\x7fELF"
assert int.from_bytes(header[18:20], "little") == 183
PY
    linkage="$(ldd "$app")"
    if grep -q 'not found' <<<"$linkage"; then
        printf 'unresolved linkage for %s:\n%s\n' "$app" "$linkage" >&2
        exit 1
    fi
done
test -f /usr/share/applications/org.moos.moplayer.desktop
test -f /usr/share/applications/org.moos.remote.desktop

sysroot="$(findmnt -nro SOURCE /sysroot)"
device="${sysroot%%\[*}"
parent="$(lsblk -dnro PKNAME "$device" | tr -d '[:space:]')"
[ -n "$parent" ]
# Read sizes through lsblk (sysfs), not blockdev: this gate runs as the
# provisioned user over SSH and blockdev needs root for /dev/vdX.
# Proven by the 2026-08-20 run: the disk booted perfectly and the gate died
# at exactly this line with "blockdev: cannot open /dev/vda: Permission denied".
disk="/dev/$parent"
disk_size="$(lsblk -bdnro SIZE "$disk")"
partition_total=0
while read -r child_size; do
    partition_total=$((partition_total + child_size))
done < <(lsblk -bnro SIZE "$disk" | tail -n +2)
tail_bytes=$((disk_size - partition_total))
[ "$tail_bytes" -ge 0 ] && [ "$tail_bytes" -lt 67108864 ]
partition_size="$(lsblk -bdnro SIZE "$device")"
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
printf 'interactive_input=virtio-keyboard+tablet\n'
printf 'accounts_user=published\n'
printf 'first_party_arch=aarch64\n'
printf 'first_party_linkage=resolved\n'
printf 'cloud_grow=bootc-success\n'
printf 'failed_units=0\n'
printf 'disk_bytes=%s\n' "$disk_size"
printf 'partition_bytes=%s\n' "$partition_size"
printf 'btrfs_bytes=%s\n' "$btrfs_size"
printf 'tail_bytes=%s\n' "$tail_bytes"
printf 'boot_id=%s\n' "$(cat /proc/sys/kernel/random/boot_id)"
