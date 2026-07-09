#!/usr/bin/env bash
# =============================================================================
# MoOS build.sh — runs INSIDE the container build (see Containerfile RUN).
# M0 "Nova Seed" scope: branding + uupd only. Heavy package work is Phase 4.
# Conventions from ublue-os/image-template: https://github.com/ublue-os/image-template
# =============================================================================

set -euxo pipefail

# -----------------------------------------------------------------------------
# (a) os-release branding
# -----------------------------------------------------------------------------
# /etc/os-release is a symlink to /usr/lib/os-release on Fedora Atomic,
# so we edit the real file in /usr/lib.
#
# M0 deliberately changes ONLY NAME and PRETTY_NAME. Changing ID= away from
# "fedora" can break tooling that keys on ID (dnf/copr repo URL templating,
# Anaconda, third-party install scripts), so the full identity switch
# (ID=moos + ID_LIKE="fedora" + VARIANT="Nova") is deferred to Phase 4
# after testing. See MOOS_DECISIONS.md ADR-015 and
# MOOS_BUILD_WORKFLOW.md (Phase 4).
sed -i 's|^NAME=.*|NAME="MoOS"|' /usr/lib/os-release
sed -i 's|^PRETTY_NAME=.*|PRETTY_NAME="MoOS 0.1 (Nova Seed)"|' /usr/lib/os-release

# TODO(Phase 4, MOOS_DECISIONS.md ADR-015): enable the full identity switch once
# COPR/Anaconda behavior with ID=moos is verified in a VM:
#   sed -i 's|^ID=.*|ID=moos|' /usr/lib/os-release
#   grep -q '^ID_LIKE=' /usr/lib/os-release \
#     || echo 'ID_LIKE="fedora"' >> /usr/lib/os-release
#   sed -i 's|^VARIANT=.*|VARIANT="Nova"|' /usr/lib/os-release
#   sed -i 's|^VARIANT_ID=.*|VARIANT_ID=nova|' /usr/lib/os-release
# NOTE: VERSION_ID stays inherited from the base (Fedora 44) on purpose —
# update tooling uses it to resolve the release.

# Show the result in the CI log for quick verification.
grep -E '^(NAME|PRETTY_NAME|ID|VERSION_ID)=' /usr/lib/os-release

# -----------------------------------------------------------------------------
# (b) uupd — Universal Blue background updater (bootc + Flatpak + distrobox)
# -----------------------------------------------------------------------------
# uupd ships from the ublue-os/packages COPR (https://github.com/ublue-os/uupd).
# The COPR is enabled only for this install and disabled right after, so the
# shipped image does not carry an active third-party repo.
dnf5 -y copr enable ublue-os/packages
dnf5 -y install uupd
dnf5 -y copr disable ublue-os/packages

# -----------------------------------------------------------------------------
# (c) M0 package set — placeholder
# -----------------------------------------------------------------------------
# M0 installs NOTHING beyond uupd. The full MoOS package set is installed in
# Phase 4 (Core OS) — see MOOS_BUILD_WORKFLOW.md. Future candidates:
#
#   dnf5 -y install \
#       waydroid \        # Android layer (Phase 8 wiring, opt-in scripts)
#       ramalama \        # local AI model runner for Mo AI (llama.cpp/Vulkan)
#       wine \            # Windows compatibility (Wine 11.x + NTSYNC)
#       ;
#
# Theming packages (moos-nova-theme, moos-nova-icons, moos-nova-cursors,
# moos-fonts, ...) arrive as first-party RPMs/COPR in Phase 3-4.

# -----------------------------------------------------------------------------
# (c2) Live-ISO support (container-native ISO contract v0.1.0 / Titanoboa)
# -----------------------------------------------------------------------------
# Recipe from the reference implementation for Kinoite bootc live ISOs:
# https://github.com/ondrejbudai/bootc-isos (kinoite/src/build.sh)
# - dracut-live: initramfs must contain dmsquash-live to boot from squashfs
# - livesys-scripts: proper live session (no-ops on installed systems)
# - grub2-efi-x64-cdboot: provides gcdx64.efi required for the ISO's EFI dir
# The ISO config itself ships in system_files:
#   /usr/lib/bootc-image-builder/iso.yaml
# plymouth-plugin-two-step: required by the moos-nova boot theme below
# (Kinoite already ships it via the bgrt/spinner themes — explicit install
# is a harmless guarantee).
dnf5 -y install dracut-live livesys-scripts grub2-efi-x64-cdboot \
    plymouth-plugin-two-step

# MoOS branded boot splash (flicker-free). No -R flag on purpose: the dracut
# run right below regenerates the initramfs anyway, and the plymouth dracut
# module picks up the theme selected here.
plymouth-set-default-theme moos-nova

# Regenerate the initramfs with the live-boot dracut modules.
kver=$(ls /usr/lib/modules | head -1)
DRACUT_NO_XATTR=1 dracut -v --force --zstd --reproducible --no-hostonly \
    --add "dmsquash-live dmsquash-live-autooverlay" \
    "/usr/lib/modules/${kver}/initramfs.img" "${kver}"

# Live session type = KDE Plasma; the services detect live boot and exit
# cleanly on installed systems.
sed -i "s/^livesys_session=.*/livesys_session=kde/" /etc/sysconfig/livesys
systemctl enable livesys.service livesys-late.service

# Titanoboa copies the ISO's EFI dir from /boot/efi/EFI inside the image.
mkdir -p /boot/efi
if ! cp -av /usr/lib/efi/*/*/EFI /boot/efi/ 2>/dev/null; then
    echo "NOTE: /usr/lib/efi layout not found — verifying /boot/efi/EFI already exists"
fi
ls /boot/efi/EFI >/dev/null   # hard-fail here if the EFI dir could not be provisioned

# -----------------------------------------------------------------------------
# (c3) SDDM login theme — moos-nova (based on SilentSDDM)
# -----------------------------------------------------------------------------
# The theme itself ships via system_files:
#   /usr/share/sddm/themes/moos-nova   (selected by /etc/sddm.conf.d/moos.conf)
# SilentSDDM runtime requirements (upstream README, Fedora names):
# - qt6-qtsvg:             SVG icons used across the theme
# - qt6-qtvirtualkeyboard: on-screen keyboard (Arabic input at login)
# - qt6-qtmultimedia:      QtMultimedia import in the theme (video backgrounds)
# - qt6-qtimageformats:    extra image format plugins for backgrounds
# SDDM theme runtime deps (SilentSDDM/moos-nova)
dnf5 -y install qt6-qtsvg qt6-qtvirtualkeyboard qt6-qtmultimedia qt6-qtimageformats

# -----------------------------------------------------------------------------
# (c4) Brand fonts + interim icon theme
# -----------------------------------------------------------------------------
# MoOS brand typography (MOOS_DESIGN: IBM Plex Sans UI / JetBrains Mono code)
# plus Arabic coverage, all from Fedora 44 repos (names verified on
# https://packages.fedoraproject.org):
# - ibm-plex-sans-fonts:        IBM Plex Sans (latin UI font)
# - ibm-plex-sans-arabic-fonts: IBM Plex Sans Arabic (Arabic UI font,
#                               subpackage of the ibm-plex-fonts source pkg)
# - google-noto-sans-arabic-fonts: Noto Sans Arabic fallback (usually already
#                               in Kinoite; explicit install is a no-op then)
# - jetbrains-mono-fonts:       JetBrains Mono (terminal/code font)
# - papirus-icon-theme:         INTERIM icon theme (Papirus-Dark) until the
#                               Nova icon fork exists (Phase 3)
# Fontconfig fallback order ships via system_files:
#   /etc/fonts/conf.d/61-moos-brand.conf
dnf5 -y install ibm-plex-sans-fonts ibm-plex-sans-arabic-fonts \
    google-noto-sans-arabic-fonts jetbrains-mono-fonts papirus-icon-theme

# -----------------------------------------------------------------------------
# (d) Enable services
# -----------------------------------------------------------------------------
# uupd runs from a systemd timer; enabling it here bakes the symlink into the
# image so every deployment gets background updates by default.
systemctl enable uupd.timer

# -----------------------------------------------------------------------------
# (e) Cleanup — required for `bootc container lint` to pass
# -----------------------------------------------------------------------------
# bootc images must not ship content in /var (it is machine-local state).
# During the real build /var/cache is a buildah CACHE MOUNT (see Containerfile)
# that speeds up rebuilds — wiping it unconditionally would defeat its purpose.
# So /var/cache is only cleaned when it is NOT a mountpoint (i.e. someone ran
# this script without the mounts); /var/log is always emptied.
rm -rf /tmp/* || true
mountpoint -q /var/cache || { dnf5 clean all; find /var/cache -mindepth 1 -delete 2>/dev/null || true; }
find /var/log -mindepth 1 -delete 2>/dev/null || true
mkdir -p /var/tmp
chmod 1777 /var/tmp

echo "MoOS build.sh finished OK"
