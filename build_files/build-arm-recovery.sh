#!/usr/bin/env bash
# =============================================================================
# build-arm-recovery.sh — slim MoOS UTM net-installer / recovery environment
# =============================================================================
# NOT the full MoOS desktop. Ships only what is needed to:
#   - boot under UTM iPhone (TCG/aarch64 virt) with MoOS identity (no Fedora splash)
#   - discover + cosign-verify + bootc-install signed moos-arm to a 2nd disk
#   - show the installer menu on tty1 + serial (ttyAMA0)
# =============================================================================
set -euo pipefail

MOOS_EDITION="${MOOS_IMAGE_NAME:-moos-arm-recovery}"
echo "=== MoOS ARM recovery build: edition=${MOOS_EDITION} arch=$(uname -m) ==="

[ "$(uname -m)" = "aarch64" ] || {
    echo "FATAL: build-arm-recovery.sh must run on aarch64 (native or podman --platform linux/arm64)"
    exit 1
}

echo "=== (1) installer tooling ==="
install_cosign() {
    command -v cosign >/dev/null 2>&1 && return 0
    if dnf5 -y install --setopt=install_weak_deps=False cosign 2>/dev/null; then
        return 0
    fi
    local ver="2.4.1"
    curl -fsSL "https://github.com/sigstore/cosign/releases/download/v${ver}/cosign-linux-arm64" \
        -o /usr/bin/cosign
    chmod +x /usr/bin/cosign
}
_RECOVERY=(
    NetworkManager-wifi
    cloud-init
    newt efibootmgr btrfs-progs
    systemd-resolved
    openssl sudo which findutils
    mesa-dri-drivers
    plymouth plymouth-plugin-script plymouth-plugin-two-step
)
dnf5 -y install --setopt=install_weak_deps=False "${_RECOVERY[@]}"
install_cosign

echo "=== (2) boot splash (MoOS — no Fedora on screen) ==="
_MOOS=/usr/share/plymouth/themes/moos
test -f "${_MOOS}/moos.script" || {
    echo "FATAL: the moos Plymouth theme did not arrive from system_files"
    exit 1
}
_missing=0
for _f in $(grep -oE 'Image\("[^"]+"\)' "${_MOOS}/moos.script" | sed 's/^Image("//; s/")$//' | sort -u); do
    test -f "${_MOOS}/${_f}" || { echo "GATE FAIL: moos.script loads missing ${_f}"; _missing=1; }
done
[ "${_missing}" -eq 0 ] || exit 1
# A UTF-8 BOM at byte 0 makes Plymouth's parser reject the whole script while
# plugin.c reports success — a pure BLACK splash with every other gate green.
# See build.sh for the proof against Fedora 44's real parser (2026-08-24).
for _tf in "${_MOOS}"/*; do
    [ -f "${_tf}" ] || continue
    _sig="$(head -c 3 "${_tf}" | od -An -tx1)"
    case "${_sig}" in
        *ef*bb*bf*)
            echo "GATE FAIL: ${_tf} starts with a UTF-8 BOM — Plymouth rejects the whole theme and boots a BLACK splash"
            exit 1
            ;;
    esac
done

plymouth-set-default-theme moos
sed -i 's/^Theme=.*/Theme=moos/' /usr/share/plymouth/plymouthd.defaults 2>/dev/null || true
install -D -m0644 /dev/stdin /etc/plymouth/plymouthd.conf <<'PLY'
[Daemon]
Theme=moos
ShowDelay=0
DeviceTimeout=8
PLY
if [ -f /usr/share/plymouth/themes/spinner/watermark.png ]; then
    cp -f "${_MOOS}/logo.png" /usr/share/plymouth/themes/spinner/watermark.png
fi
if [ -f /usr/share/plymouth/themes/spinner/watermark.png ]; then
    cmp -s "${_MOOS}/logo.png" /usr/share/plymouth/themes/spinner/watermark.png || {
        echo "FATAL: spinner compatibility watermark still contains foreign branding"
        exit 1
    }
fi
grep -qx 'Theme=moos' /etc/plymouth/plymouthd.conf
grep -qx 'Theme=moos' /usr/share/plymouth/plymouthd.defaults 2>/dev/null || true

echo "=== (3) identity ==="
# A recovery disk that introduces itself as Fedora is not MoOS.
cat > /usr/lib/os-release <<'OSREL'
NAME="MoOS"
PRETTY_NAME="MoOS Installer"
ID=moos
ID_LIKE="fedora"
VERSION="44"
VERSION_ID="44"
ANSI_COLOR="0;38;2;78;215;200"
LOGO=moos-logo
HOME_URL="https://www.moalfarras.space"
DOCUMENTATION_URL="https://github.com/moalfarras-sys/moos-image"
SUPPORT_URL="https://github.com/moalfarras-sys/moos-image/issues"
BUG_REPORT_URL="https://github.com/moalfarras-sys/moos-image/issues"
DEFAULT_HOSTNAME="moos"
VARIANT="MoOS Installer"
VARIANT_ID=moos-installer
OSREL
ln -sf ../usr/lib/os-release /etc/os-release
for _release in /etc/fedora-release /etc/redhat-release /etc/system-release; do
    rm -f "$_release"
    printf 'MoOS\n' > "$_release"
done
_moos_mark="${_MOOS}/logo.png"
for _px in fedora-logo.png fedora-logo-small.png fedora-gdm-logo.png fedora_logo_med.png; do
    [ -f "/usr/share/pixmaps/${_px}" ] && cp -f "$_moos_mark" "/usr/share/pixmaps/${_px}" || true
done
unset -v _release _px _moos_mark

echo "=== (4) cloud-init + serial ==="
install -D -m0644 /dev/stdin /etc/cloud/cloud.cfg.d/99-moos-recovery.cfg <<'CLOUDCFG'
system_info:
  default_user:
    name: moos
    lock_passwd: false
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: [wheel]
    shell: /bin/bash
CLOUDCFG
systemctl enable cloud-init-local.service cloud-init-network.service \
    cloud-config.service cloud-final.service
systemctl enable NetworkManager.service
systemctl enable moos-utm-installer.service
systemctl enable serial-getty@ttyAMA0.service

# ARM block coldplug — same fix as build-arm.sh lines 378-393.
# Without this, VirtIO disk UUID symlinks aren't published before fstab mount
# units start. systemd-fstab-generator retries fill the journal, and the boot
# stalls or floods kmsg — the exact failure observed on real iPhone at ~42s.
systemctl enable moos-arm-block-coldplug.service
install -D -m0644 /dev/stdin /etc/systemd/system.conf.d/moos-arm-device-timeout.conf <<'TIMEOUT'
# Slow aarch64 virt (iPhone TCG/JIT) can take >45s for UUID links to appear
# after coldplug re-triggers udev. Default 45s device timeout sends the system
# to emergency mode even when coldplug is actively running.
[Manager]
DefaultDeviceTimeoutSec=120
TIMEOUT
for _mount in boot.mount boot-efi.mount; do
    install -D -m0644 /dev/stdin \
        "/usr/lib/systemd/system/${_mount}.d/moos-arm-coldplug.conf" <<'MOUNT'
[Unit]
After=moos-arm-block-coldplug.service
Requires=moos-arm-block-coldplug.service
MOUNT
done

install -D -m0644 /dev/stdin /usr/lib/bootc/kargs.d/50-moos-arm-console.toml <<'KARGS'
kargs = [
    "console=ttyAMA0,115200n8",
    "console=tty0",
    "rhgb",
    "quiet",
    "splash",
    "loglevel=3",
]
KARGS

install -D -m0644 /dev/stdin /usr/lib/dracut/dracut.conf.d/50-moos-arm.conf <<'DRACUT'
hostonly="no"
hostonly_cmdline="no"
sysloglvl="0"
add_drivers+=" virtio_blk virtio_net virtio_pci virtio_scsi virtio_gpu virtio_console "
DRACUT

echo "=== (5) initramfs with MoOS plymouth ==="
kver="$(rpm -q --qf '%{VERSION}-%{RELEASE}.%{ARCH}\n' kernel-core | tail -1)"
[ -n "${kver}" ] || { echo "FATAL: no kernel-core in recovery image"; exit 1; }
install -d -m0700 /var/roothome
dracut --no-hostonly --force --reproducible \
    --add "ostree plymouth" \
    "/usr/lib/modules/${kver}/initramfs.img" "${kver}" 2>&1 | tail -20
rmdir /var/roothome

lsinitrd "/usr/lib/modules/${kver}/initramfs.img" > /tmp/moos-recovery-initrd.txt 2>/dev/null \
    || { echo "FATAL: lsinitrd could not inspect recovery initramfs"; exit 1; }
for _need in 'plymouth/themes/moos/moos.script' 'plymouth/themes/moos/intro1.png' \
             'plymouth/themes/moos/moos.plymouth'; do
    grep -q "${_need}" /tmp/moos-recovery-initrd.txt || {
        echo "FATAL: recovery initramfs lacks ${_need} — boot would show foreign splash"
        exit 1
    }
done
grep -qE 'plymouth/(script\.so|script)' /tmp/moos-recovery-initrd.txt || {
    echo "FATAL: recovery initramfs lacks Plymouth script plugin"
    exit 1
}

echo "=== (6) gates ==="
for cmd in bootc skopeo cosign jq curl lsblk; do
    command -v "$cmd" >/dev/null || { echo "FATAL: missing $cmd"; exit 1; }
done
[ -x /usr/libexec/moos-utm-net-install ] || { echo "FATAL: moos-utm-net-install missing"; exit 1; }
[ -x /usr/libexec/moos-utm-installer-menu ] || { echo "FATAL: moos-utm-installer-menu missing"; exit 1; }
[ -r /etc/pki/containers/moos.pub ] || { echo "FATAL: MoOS cosign public key missing"; exit 1; }
[ -r /usr/share/moos/release/arm-latest.json ] || { echo "FATAL: arm-latest.json missing"; exit 1; }
grep -qx 'NAME="MoOS"' /usr/lib/os-release || { echo "FATAL: os-release NAME is not MoOS"; exit 1; }
! grep -qi 'fedora release' /etc/fedora-release 2>/dev/null || {
    echo "FATAL: /etc/fedora-release still names Fedora"
    exit 1
}
# iPhone boot-bug gates: the fstab-generator flood was caused by these being absent.
[ -f /etc/systemd/system.conf.d/moos-arm-device-timeout.conf ] || {
    echo "FATAL: ARM device timeout config missing — iPhone boot will flood"
    exit 1
}
grep -q 'DefaultDeviceTimeoutSec=120' /etc/systemd/system.conf.d/moos-arm-device-timeout.conf || {
    echo "FATAL: device timeout is not 120s"
    exit 1
}
[ -x /usr/libexec/moos-arm-block-coldplug ] || {
    echo "FATAL: moos-arm-block-coldplug script missing"
    exit 1
}

echo "=== MoOS ARM recovery build complete ==="
