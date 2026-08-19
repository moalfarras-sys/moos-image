#!/usr/bin/env bash
# =============================================================================
# MoOS ARM build.sh — runs INSIDE the ARM container build
# =============================================================================
# ADR-020: ARM edition for Oracle Cloud Ampere A1 and UTM.
#
# The Containerfile.arm handles package installation, identity branding,
# and system_files copy. This script handles the post-install wiring
# that requires shell logic: Plymouth theme registration, initramfs
# regeneration, service enablement, and identity verification.
#
# Key differences from x86 build.sh:
#   - No NVIDIA driver (no akmods)
#   - No MoPlayer or Mo Remote (no aarch64 binaries)
#   - No gaming stack (gamescope/gamemode/mangohud)
#   - Serial console + cloud-init for Oracle Cloud
#   - Software rendering (no GPU)
# =============================================================================

set -euxo pipefail

MOOS_EDITION="${MOOS_IMAGE_NAME:-moos-arm}"
echo "=== post-install wiring for ARM edition: ${MOOS_EDITION} ==="

# ── (a) Plymouth — register theme and embed in initramfs ─────────────────────
# The moos theme assets arrive via system_files COPY. Plymouth's defaults
# file still points at the Fedora bgrt/spinner fallback — overwrite it.
# This MUST run before dracut so the initramfs embeds the correct theme.

# Set the MoOS theme as default.
plymouth-set-default-theme moos

# Gate: verify the theme and all seven sprites landed in the image.
_MOOS=/usr/share/plymouth/themes/moos
for _f in moos.script logo.png ring.png ring2.png head.png glow.png particle.png pulse.png; do
    test -f "${_MOOS}/${_f}" || {
        echo "GATE FAIL: moos theme is missing ${_f} — the Script splash would abort to text"
        exit 1
    }
done
echo "=== plymouth: moos Script theme present ==="
ls -1 "${_MOOS}" | grep -vE 'README' | sed 's/^/    /'

# Rebrand Fedora's distribution fallbacks so they cannot bring back a foreign splash.
sed -i 's/^Theme=.*/Theme=moos/' /usr/share/plymouth/plymouthd.defaults
if [ -f /usr/share/plymouth/themes/spinner/watermark.png ]; then
    cp -f "${_MOOS}/logo.png" /usr/share/plymouth/themes/spinner/watermark.png
fi

# Fail closed: both admin selection and distribution fallback must select MoOS.
grep -qx 'Theme=moos' /etc/plymouth/plymouthd.conf
grep -qx 'Theme=moos' /usr/share/plymouth/plymouthd.defaults

# ── (a2) Plymouth quit — retain splash for seamless desktop handoff ───────────
# Without --retain-splash, Plymouth tears down its last frame when it exits,
# causing 4-5 seconds of black screen before KWin draws its first frame.
# --retain-splash keeps the last Plymouth frame standing until KWin's modeset.
mkdir -p /usr/lib/systemd/system/plymouth-quit.service.d
cat > /usr/lib/systemd/system/plymouth-quit.service.d/10-moos-retain-splash.conf <<'DROPIN'
[Service]
ExecStart=
ExecStart=-/usr/bin/plymouth quit --retain-splash
DROPIN

# ── (a3) Boot splash kernel arguments ────────────────────────────────────────
# rhgb = Plymouth graphical boot; quiet = suppress kernel log;
# splash = graphics flag; loglevel/rd.udev.log_level = minimal noise;
# vt.global_cursor_default=0 = no blinking cursor during handoffs.
mkdir -p /usr/lib/bootc/kargs.d
cat > /usr/lib/bootc/kargs.d/10-moos-boot-splash.toml <<'KARGS'
kargs = [
    "rhgb",
    "quiet",
    "splash",
    "loglevel=3",
    "rd.udev.log_level=3",
    "vt.global_cursor_default=0",
]
KARGS

# ── (b) Regenerate initramfs with Plymouth embedded ──────────────────────────
# dracut must see the moos theme and embed it into the initramfs so Plymouth
# draws from the very first moment — not from the real root where it would
# start AFTER a text-mode initramfs.
kver=$(ls /usr/lib/modules/ | grep -v 'debug' | head -1)
if [ -n "$kver" ]; then
    echo "=== regenerating initramfs for kernel ${kver} ==="
    DRACUT_NO_XATTR=1 dracut -v --force --zstd --reproducible --no-hostonly \
        "/usr/lib/modules/${kver}/initramfs.img" "${kver}" 2>&1 | tail -5

    # Gate: Plymouth module must be in the initramfs.
    _lsinitrd=$(lsinitrd "/usr/lib/modules/${kver}/initramfs.img" 2>/dev/null || true)
    if echo "$_lsinitrd" | grep -q "plymouth"; then
        echo "OK: plymouth is in initramfs"
    else
        echo "WARNING: plymouth not confirmed in initramfs — splash may not render early"
    fi
    echo "=== initramfs regenerated ==="
fi

# ── (c) Service enablement ───────────────────────────────────────────────────
systemctl enable sshd.service
systemctl enable cloud-init.service
systemctl enable moos-firstboot-growpart.service 2>/dev/null || true

# Disable unnecessary services for cloud/ARM.
systemctl disable bluetooth.service 2>/dev/null || true
systemctl disable cups.service 2>/dev/null || true
systemctl disable fwupd-refresh.service 2>/dev/null || true

# ── (d) Software rendering configuration ─────────────────────────────────────
mkdir -p /etc/xdg/plasma-workspace/env
cat > /etc/xdg/plasma-workspace/env/moos-arm-rendering.sh <<'ENV'
#!/bin/bash
export KWIN_FORCE_SW_OPENGL=1
export MESA_GL_VERSION_OVERRIDE=3.3
ENV
chmod +x /etc/xdg/plasma-workspace/env/moos-arm-rendering.sh

# ── (e) GRUB configuration ───────────────────────────────────────────────────
mkdir -p /etc/default/grub.d
cat > /etc/default/grub.d/50-moos-arm.conf <<'GRUB'
GRUB_TIMEOUT=0
GRUB_CMDLINE_LINUX="console=tty0 console=ttyAMA0,115200n8"
GRUB_TERMINAL="serial"
GRUB_SERIAL_COMMAND="serial --speed=115200 --unit=0 --word=8 --parity=no --stop=1"
GRUB

# ── (f) Final identity check ────────────────────────────────────────────────
_source_id=$(grep '^ID=' /usr/lib/os-release | head -1)
if [ "$_source_id" != "ID=moos" ]; then
    echo "FATAL: os-release ID is '${_source_id}', expected 'ID=moos'"
    exit 1
fi
echo "=== identity check passed: $(grep '^PRETTY_NAME=' /usr/lib/os-release) ==="

# ── (g) Clean up ─────────────────────────────────────────────────────────────
dnf5 clean all
rm -rf /var/cache/dnf /var/log/dnf.log /var/log/dnf.librepo.log

echo "=== ARM post-install wiring complete ==="
