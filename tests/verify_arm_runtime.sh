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
# SSH and cloud-init can become ready before the display manager transaction.
# Wait for the actual desktop and MoOS store owner with a hard deadline; a
# one-shot sample here caused run 34581668929 to reject a healthy late boot.
desktop_deadline=$((SECONDS + 360))
while [ "$SECONDS" -lt "$desktop_deadline" ]; do
    graphical_state="$(systemctl is-active graphical.target 2>/dev/null || true)"
    display_state="$(systemctl is-active display-manager.service 2>/dev/null || true)"
    store_state="$(systemctl is-active moos-flatpak-init.service 2>/dev/null || true)"
    store_result="$(systemctl show -p Result --value moos-flatpak-init.service 2>/dev/null || true)"
    store_status="$(systemctl show -p ExecMainStatus --value moos-flatpak-init.service 2>/dev/null || true)"
    if [ "$graphical_state" = active ] && [ "$display_state" = active ] \
            && [ "$store_state" = active ] && [ "$store_result" = success ] \
            && [ "$store_status" = 0 ]; then
        break
    fi
    [ "$store_result" != failed ] || break
    sleep 3
done
if [ "${graphical_state:-}" != active ] || [ "${display_state:-}" != active ] \
        || [ "${store_state:-}" != active ] || [ "${store_result:-}" != success ] \
        || [ "${store_status:-}" != 0 ]; then
    systemctl status --no-pager --full graphical.target display-manager.service \
        moos-flatpak-init.service >&2 || true
    journalctl --no-pager -b -u display-manager.service \
        -u moos-flatpak-init.service -n 160 >&2 || true
    echo "ARM RUNTIME FATAL: desktop/store readiness deadline expired" >&2
    exit 1
fi
[ "$(systemctl is-enabled moos-flatpak-init.service)" = enabled ]
[ "$(systemctl is-enabled flatpak-add-fedora-repos.service)" = masked ]
# Observe first-boot store state before Flatpak can initialize it implicitly.
[ -s /var/lib/flatpak/repo/config ]
[ -s /var/lib/flatpak/repo/flathub.trustedkeys.gpg ]
[ "$(flatpak config --system --get extra-languages)" = 'ar;en;de' ]
store_remotes="$(flatpak remotes --system --show-disabled --columns=name)"
[ "$store_remotes" = flathub ]
store_details="$(flatpak remotes --system --show-disabled --columns=name,url,options)"
grep -Fx $'flathub\thttps://dl.flathub.org/repo/' <<<"$store_details" >/dev/null
grep -q '^gpg-verify=true$' /var/lib/flatpak/repo/config
printf 'store=initialized\nstore-languages=ar;en;de\n'
[ -s /var/lib/authselect/checksum ]
authselect check
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
# moos-hardware-adapt is started by its timer 45 s after the desktop, so a single
# `systemctl --failed` sample can see it before it has run, or while it is still running,
# and pass a boot whose adaptation fails later. Wait for its first pass to finish:
# RemainAfterExit=yes leaves a finished pass `active` and a failed one `failed`. Result is
# already `success` before the unit has ever started, so only ActiveState ends the wait.
# The deadline outlasts the timer's OnActiveSec plus the unit's TimeoutStartSec
# (tests/test_moos_arm.py ties the three numbers together).
hwadapt_deadline=$((SECONDS + 720))
while [ "$SECONDS" -lt "$hwadapt_deadline" ]; do
    hwadapt_active="$(systemctl is-active moos-hardware-adapt.service 2>/dev/null || true)"
    case "$hwadapt_active" in active|failed) break ;; esac
    sleep 3
done
hwadapt_result="$(systemctl show -p Result --value moos-hardware-adapt.service 2>/dev/null || true)"
[ "${hwadapt_active:-}" = "active" ] && [ "$hwadapt_result" = "success" ] || {
    systemctl status --no-pager --full moos-hardware-adapt.service moos-hardware-adapt.timer >&2 || true
    journalctl --no-pager -b -u moos-hardware-adapt.service -n 120 >&2 || true
    cat /run/moos-hardware-adapt.log >&2 2>/dev/null || true
    echo "ARM RUNTIME FATAL: moos-hardware-adapt did not finish its first pass (state=${hwadapt_active:-unknown} result=${hwadapt_result:-unknown})" >&2
    exit 1
}
printf 'hardware_adapt=%s\n' "$hwadapt_active"
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
