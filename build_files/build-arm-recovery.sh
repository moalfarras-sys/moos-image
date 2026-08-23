#!/usr/bin/env bash
# =============================================================================
# build-arm-recovery.sh — slim MoOS UTM net-installer / recovery environment
# =============================================================================
# NOT the full MoOS desktop. Ships only what is needed to:
#   - boot under UTM iPhone (TCG/aarch64 virt)
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
    plymouth plymouth-plugin-script
)
dnf5 -y install --setopt=install_weak_deps=False "${_RECOVERY[@]}"
install_cosign

echo "=== (2) identity (minimal) ==="
# Keep os-release MoOS-branded if finalize script exists; otherwise patch ID only.
if [ -x /usr/libexec/moos-finalize-arm-recovery.sh ]; then
    /usr/libexec/moos-finalize-arm-recovery.sh
else
    if [ -f /etc/os-release ]; then
        sed -i 's/^NAME=.*/NAME="MoOS Installer"/' /etc/os-release
        sed -i 's/^PRETTY_NAME=.*/PRETTY_NAME="MoOS Installer (recovery)"/' /etc/os-release
    fi
fi

echo "=== (3) cloud-init + serial ==="
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
add_drivers+=" virtio_blk virtio_net virtio_pci virtio_scsi virtio_gpu virtio_console "
DRACUT

echo "=== (4) gates ==="
for cmd in bootc skopeo cosign jq curl lsblk; do
    command -v "$cmd" >/dev/null || { echo "FATAL: missing $cmd"; exit 1; }
done
[ -x /usr/libexec/moos-utm-net-install ] || { echo "FATAL: moos-utm-net-install missing"; exit 1; }
[ -x /usr/libexec/moos-utm-installer-menu ] || { echo "FATAL: moos-utm-installer-menu missing"; exit 1; }
[ -r /etc/pki/containers/moos.pub ] || { echo "FATAL: MoOS cosign public key missing"; exit 1; }
[ -r /usr/share/moos/release/arm-latest.json ] || { echo "FATAL: arm-latest.json missing"; exit 1; }

echo "=== MoOS ARM recovery build complete ==="
