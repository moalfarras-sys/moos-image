#!/usr/bin/env bash
# Compile the immutable hardware database into /usr, where bootc image content
# belongs. Leaving the RPM-generated copy in /etc makes every fresh deployment
# satisfy systemd-hwdb-update.service's ConditionNeedsUpdate=/etc. udevd is
# ordered after that service, so a slow VM can exhaust the /boot device timeout
# before persistent-storage rules recreate UUID links after switch-root.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "HWDB FATAL: image hardware database compilation requires root" >&2
    exit 1
fi
command -v systemd-hwdb >/dev/null 2>&1 || {
    echo "HWDB FATAL: systemd-hwdb is missing from the image" >&2
    exit 1
}

# Image-owned overrides must live in /usr. A machine administrator may create
# /etc/udev/hwdb.d later; that correctly re-enables systemd-hwdb-update for the
# local override without imposing the cost on every unmodified MoOS boot.
hwdb_override=""
if [ -d /etc/udev/hwdb.d ]; then
    hwdb_override="$(find /etc/udev/hwdb.d -mindepth 1 -print -quit)"
fi
if [ -n "$hwdb_override" ]; then
    echo "HWDB FATAL: image-owned hwdb source unexpectedly exists under /etc/udev/hwdb.d" >&2
    find /etc/udev/hwdb.d -mindepth 1 -maxdepth 1 -print >&2
    exit 1
fi

systemd-hwdb --usr update
[ -s /usr/lib/udev/hwdb.bin ] || {
    echo "HWDB FATAL: systemd-hwdb did not produce /usr/lib/udev/hwdb.bin" >&2
    exit 1
}
rm -f /etc/udev/hwdb.bin
[ ! -e /etc/udev/hwdb.bin ] || {
    echo "HWDB FATAL: mutable /etc hardware database survived image compilation" >&2
    exit 1
}

# Prove the compiled database is readable, not merely non-empty.
hwdb_probe="$(systemd-hwdb query usb:v1D6Bp0002)"
case "$hwdb_probe" in
    *ID_VENDOR_FROM_DATABASE=*) ;;
    *) echo "HWDB FATAL: compiled database lookup returned no vendor" >&2; exit 1 ;;
esac
echo "HWDB OK: immutable database compiled in /usr; clean boots skip the udev-blocking rebuild"
