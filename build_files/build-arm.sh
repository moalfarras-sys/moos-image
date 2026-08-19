#!/usr/bin/env bash
# =============================================================================
# build-arm.sh — the MoOS aarch64 edition (moos-arm)
# =============================================================================
#
# WHY THIS FILE EXISTS SEPARATELY FROM build.sh
#
#   The x86_64 image is built FROM ghcr.io/ublue-os/kinoite-main:44, which is
#   published for amd64 ONLY — there is no arm64 manifest, so `podman build
#   --platform linux/arm64` against it cannot work at all. The ARM edition
#   therefore starts from quay.io/fedora/fedora-bootc:44, which is a bare bootc
#   base with no desktop in it, and has to bring up Plasma itself.
#
#   That could have been done by teaching build.sh a fourth edition. It is not,
#   deliberately. build.sh is ~4 000 lines that assume the Kinoite base is
#   already there and assume x86: an NVIDIA akmods stage, i686 multilib, a
#   gaming host stack, and two prebuilt binaries (Mo Remote linux-x64, MoPlayer's
#   Flutter bundle) that do not exist for aarch64. Threading a new guard through
#   all of that would put the owner's daily-driver image one editing mistake away
#   from breaking, to serve a second architecture that cannot share most of it.
#   So the ARM edition is isolated: nothing here can regress the x86 build.
#
#   WHAT IS SHARED IS THE PART THAT MATTERS. system_files/ — the entire MoOS
#   identity: the UI2 look-and-feel, every QML surface, the icon and theme trees,
#   the Plymouth boot animation, the service units, Mo AI — is architecture
#   independent (verified: not one ELF binary in 112 MB of it) and is copied
#   verbatim by Containerfile.arm. This script does the package-dependent wiring
#   around it, exactly as build.sh does for x86.
#
# WHAT IT TARGETS
#   * Oracle Cloud Infrastructure, Ampere A1 (VM.Standard.A1.Flex) — the Always
#     Free aarch64 shape. Everything OCI-specific is in section (5).
#   * UTM on Apple silicon and on iPhone/iPad. Same qcow2, no changes.
#   * Any other aarch64 UEFI machine or VM.
#
# FAIL LOUDLY, NEVER SILENTLY
#   Every gate here exits non-zero with the reason. An ARM image that boots to a
#   black screen because a package quietly was not there is worse than a build
#   that stops and says which one.
# =============================================================================
set -euo pipefail

MOOS_EDITION="${MOOS_IMAGE_NAME:-moos-arm}"
echo "=== MoOS ARM build: edition=${MOOS_EDITION} arch=$(uname -m) ==="

[ "$(uname -m)" = "aarch64" ] || {
    echo "FATAL: build-arm.sh is running on $(uname -m), not aarch64."
    echo "       Build it with --platform linux/arm64 (or on an arm64 runner);"
    echo "       an emulated build here would silently produce x86 binaries in"
    echo "       the qml shell stage."
    exit 1
}

# -----------------------------------------------------------------------------
# (1) The desktop
# -----------------------------------------------------------------------------
# A CURATED list, not @kde-desktop-environment. The group pulls the whole Fedora
# KDE application set — games, PIM, education — which on the Always Free Ampere
# shape is several GB of image nobody asked for, and the owner asked for a light
# edition. This is Plasma 6 on Wayland plus exactly what MoOS's own surfaces
# need to run.
#
# install_weak_deps=False for the same reason: it is what keeps a desktop image
# from dragging in a recommends closure twice its size.
echo "=== (1) Plasma Wayland ==="
_PLASMA=(
    plasma-workspace plasma-workspace-wayland plasma-desktop
    kwin kwin-wayland kwin-wayland-libs
    systemsettings kscreen kscreenlocker
    plasma-nm plasma-pa plasma-systemmonitor
    xdg-desktop-portal-kde xdg-desktop-portal
    qt6-qtwayland qt6-qtsvg qt6-qtdeclarative qt6-qtmultimedia qt6-qtimageformats
    kf6-kirigami kf6-kirigami-addons kf6-qqc2-desktop-style
    dolphin konsole ark kate
    breeze breeze-icon-theme
    pipewire pipewire-pulseaudio wireplumber
    NetworkManager NetworkManager-wifi
    plymouth plymouth-plugin-script plymouth-plugin-two-step plymouth-system-theme
    dracut-network
    python3 python3-gobject
    fontconfig gtk4 libadwaita
    mesa-dri-drivers mesa-libEGL mesa-libgbm
    openssh-server cloud-init cloud-utils-growpart
    firewalld flatpak openssl sudo
)
dnf5 -y install --setopt=install_weak_deps=False "${_PLASMA[@]}"

# Fonts: MoOS's UI is IBM Plex, and its Arabic surfaces are first-class (the
# owner's own locale). A desktop that falls back to a substitute face for Arabic
# is a broken desktop, not a cosmetic issue, so these are not optional.
dnf5 -y install --setopt=install_weak_deps=False \
    ibm-plex-sans-fonts ibm-plex-sans-arabic-fonts ibm-plex-mono-fonts \
    google-noto-sans-fonts google-noto-sans-arabic-fonts \
    google-noto-color-emoji-fonts
dnf5 -y install langpacks-ar langpacks-en

# -----------------------------------------------------------------------------
# (2) The login manager
# -----------------------------------------------------------------------------
# MoOS pins its login scene through /usr/lib/plasmalogin/, and system_files ships
# that configuration. Plasma Login Manager is therefore REQUIRED, not one of two
# options: falling back to SDDM would produce a machine that logs in but with a
# stock greeter, i.e. a MoOS that does not look like MoOS, and it would do so
# without failing anything.
echo "=== (2) login manager ==="
if ! dnf5 -y install --setopt=install_weak_deps=False plasma-login-manager; then
    echo "FATAL: plasma-login-manager is not available in this Fedora."
    echo "       MoOS's greeter configuration (system_files/usr/lib/plasmalogin/)"
    echo "       targets it specifically. Candidates present in the repos:"
    dnf5 -q search 'plasma*login*' 2>/dev/null || true
    dnf5 -q search sddm 2>/dev/null | head -5 || true
    exit 1
fi

# -----------------------------------------------------------------------------
# (3) Remote access — the only way anyone sees this desktop on a cloud VM
# -----------------------------------------------------------------------------
# An Ampere instance has no monitor. Without this the ARM edition is a desktop
# nobody can look at, which is the whole point of the edition.
#
# KRDP, not xrdp: MoOS's session is Wayland, and KRDP is KDE's own RDP server
# driving the running Plasma session through the portal. xrdp on Wayland means
# starting a SECOND, X11 session — a different desktop from the one that booted.
#
# It is installed but NOT enabled, and no password is set here. A service
# listening on 3389 with a build-time credential would be a backdoor shipped to
# every user of this image. `moos-arm-remote` (section 6) turns it on with a
# password the owner chooses, once, over SSH.
echo "=== (3) remote access ==="
if ! dnf5 -y install --setopt=install_weak_deps=False krdp; then
    echo "WARNING: krdp is not in this Fedora's repos — the ARM edition will ship"
    echo "         with SSH only and no graphical remote. moos-arm-remote will say so."
    touch /usr/lib/moos/no-krdp
fi

# Package payloads are allowed to overwrite vendor defaults during installation.
# The MoOS overlay is the final authority, so restore it only after the LAST dnf
# transaction. Without this, transaction order decides whether the session,
# greeter and theme are MoOS or Fedora — and a green source-tree gate cannot see
# that difference.
test -d /moos-overlay/usr/share || {
    echo "FATAL: the pristine system_files overlay is not mounted at /moos-overlay"
    exit 1
}
cp -a /moos-overlay/. /

systemctl enable NetworkManager.service sshd.service firewalld.service
# Fedora 44's documented PLM switch uses --force because the graphical-login
# alias may still point at a display manager inherited from a package preset.
systemctl enable --force plasmalogin.service
systemctl set-default graphical.target

# Defence in depth around the public cloud VM. SSH is the only service exposed
# by the image. KRDP remains reachable through an SSH tunnel to localhost; this
# image never opens 3389 on the host firewall.
firewall-offline-cmd --set-default-zone=public
firewall-offline-cmd --zone=public --add-service=ssh
firewall-offline-cmd --zone=public --remove-service=rdp 2>/dev/null || true

# SSH: keys only. Oracle injects the instance's public key through cloud-init,
# so password authentication buys nothing and costs a brute-force surface on a
# machine with a public IP.
install -D -m0644 /dev/stdin /etc/ssh/sshd_config.d/10-moos-arm.conf <<'SSHD'
# MoOS ARM: the instance has a public IP, so the front door is keys only.
# Oracle's metadata service hands the instance's public key to cloud-init, which
# installs it for the default user — there is nothing a password would add here
# except an attack surface.
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
SSHD

# -----------------------------------------------------------------------------
# (4) The boot animation
# -----------------------------------------------------------------------------
# Same theme, same frames, same script as x86 — it arrived with system_files.
# What differs is that this base has no Plymouth theme selected at all.
echo "=== (4) boot splash ==="
_MOOS=/usr/share/plymouth/themes/moos
test -f "${_MOOS}/moos.script" || {
    echo "FATAL: the moos Plymouth theme did not arrive from system_files"; exit 1
}
# Gate every asset the script loads, derived from the script itself — the same
# check build.sh runs, and for the same reason: a missing image drops the whole
# splash to Plymouth's text console, with every other check still green.
_missing=0
for _f in $(grep -oE 'Image\("[^"]+"\)' "${_MOOS}/moos.script" | sed 's/^Image("//; s/")$//' | sort -u); do
    test -f "${_MOOS}/${_f}" || { echo "GATE FAIL: moos.script loads missing ${_f}"; _missing=1; }
done
[ "${_missing}" -eq 0 ] || exit 1

plymouth-set-default-theme moos
sed -i 's/^Theme=.*/Theme=moos/' /usr/share/plymouth/plymouthd.defaults 2>/dev/null || true
install -D -m0644 /dev/stdin /etc/plymouth/plymouthd.conf <<'PLY'
[Daemon]
Theme=moos
ShowDelay=0
DeviceTimeout=8
PLY

# -----------------------------------------------------------------------------
# (5) Oracle Cloud Infrastructure
# -----------------------------------------------------------------------------
echo "=== (5) Oracle Cloud (Ampere A1) ==="
# The datasource list is pinned rather than left to detection. Left to detect,
# cloud-init probes every datasource in turn and each miss costs seconds on a
# boot the owner asked to be fast; worse, on a first boot with no network yet it
# can settle on None and never install the SSH key, which locks the owner out of
# their own instance.
#   Oracle      — OCI's IMDS. The one that actually applies on the target.
#   ConfigDrive — UTM/QEMU and anything that hands config in on a disk.
#   NoCloud     — a seed ISO, which is how a local test rig injects a key.
#   None        — last, so a machine with no metadata at all still finishes
#                 booting instead of hanging on a datasource that is not coming.
install -D -m0644 /dev/stdin /etc/cloud/cloud.cfg.d/10-moos-arm.cfg <<'CLOUDCFG'
datasource_list: [ Oracle, ConfigDrive, NoCloud, None ]
# Oracle attaches a boot volume that is larger than the imported image (50 GB by
# default on the Always Free tier, against a ~10 GB image). Without growpart the
# machine boots with the image's original small root and fills up.
growpart:
  mode: auto
  devices: ['/']
  ignore_growroot_disabled: false
resize_rootfs: true
# The default user. Oracle's own images use `opc`; MoOS uses `moos` so the same
# name works on OCI, on UTM and on bare metal, and so that documentation does not
# have to fork per platform.
#
# There is deliberately no NOPASSWD sudo rule. Membership in wheel uses Fedora's
# normal password-authenticated sudo policy. Oracle launch user-data sets a
# unique management password; the SSH key remains the only network login method
# because sshd disables password authentication above. Do not pre-expire the
# password: with both password and keyboard-interactive SSH disabled, forcing a
# password change during the key login can lock the account out before sudo works.
system_info:
  default_user:
    name: moos
    gecos: MoOS
    groups: [wheel, video, audio, input, render]
    shell: /bin/bash
CLOUDCFG
systemctl enable cloud-init.service cloud-init-local.service \
    cloud-config.service cloud-final.service

# The serial console. THIS IS THE ARM DIFFERENCE that most cloud images get
# wrong: on x86 the provider's console is ttyS0, and on Ampere/aarch64 it is
# ttyAMA0 (the ARM PL011 UART). An image that only lists ttyS0 gives the owner a
# permanently blank "Serial Console" in the OCI web console — which is the only
# way in when SSH or the network is broken, i.e. exactly when it is needed.
install -D -m0644 /dev/stdin /usr/lib/bootc/kargs.d/50-moos-arm-console.toml <<'KARGS'
# MoOS ARM console + boot appearance.
#
# console=ttyAMA0,115200n8
#     The ARM PL011 UART. This is what Oracle's "Serial Console" and UTM's
#     serial output are attached to. NOT ttyS0 — that is the x86 8250 port and
#     does not exist on Ampere.
# console=tty0
#     Listed SECOND on purpose. The kernel prints to every console= it is given
#     but /dev/console (and therefore the boot's stdout) is the LAST one, so
#     this ordering keeps the graphical console primary for UTM and any machine
#     with a display, while the serial port still receives everything.
# rhgb quiet splash loglevel=3 rd.udev.log_level=3 vt.global_cursor_default=0
#     The same flicker-free set the x86 editions use: Plymouth owns the screen
#     from the first frame and no kernel or udev text scrolls over the MoOS
#     animation.
kargs = [
    "console=ttyAMA0,115200n8",
    "console=tty0",
    "rhgb",
    "quiet",
    "splash",
    "loglevel=3",
    "rd.udev.log_level=3",
    "vt.global_cursor_default=0",
]
KARGS
systemctl enable serial-getty@ttyAMA0.service

# A cloud instance's disk is virtio and its display, if any, is virtio-gpu. The
# base image's dracut is already hostonly=no, but say so explicitly: an image
# that is BUILT on one machine and BOOTED on another must carry every driver it
# could need, and a hostonly initramfs is how a cloud image ends up in dracut's
# emergency shell with no root device.
install -D -m0644 /dev/stdin /usr/lib/dracut/dracut.conf.d/50-moos-arm.conf <<'DRACUT'
hostonly="no"
hostonly_cmdline="no"
add_drivers+=" virtio_blk virtio_net virtio_pci virtio_scsi virtio_gpu virtio_console "
DRACUT

# -----------------------------------------------------------------------------
# (6) moos-arm-remote — turning the graphical remote on, safely
# -----------------------------------------------------------------------------
install -D -m0755 /dev/stdin /usr/bin/moos-arm-remote <<'REMOTE'
#!/usr/bin/env bash
# moos-arm-remote — create the headless Wayland desktop and enable KRDP.
#
# Usage:
#   sudo moos-arm-remote on [user]
#   sudo moos-arm-remote off [user]
#   sudo moos-arm-remote status [user]
#
# KRDP authenticates through PAM with this account's own password. No second
# credential is baked into the image, passed on a command line, or stored in a
# generated unit. The host firewall keeps 3389 closed; reach it through SSH:
#   ssh -N -L 3389:127.0.0.1:3389 moos@<public-ip>
set -euo pipefail

action="${1:-on}"
target="${2:-${SUDO_USER:-moos}}"

if [ -f /usr/lib/moos/no-krdp ]; then
    echo "This image was built without krdp, so there is no graphical remote."
    echo "SSH still works. Rebuild once krdp is available in Fedora aarch64."
    exit 1
fi
[ "$(id -u)" -eq 0 ] || {
    echo "Run with sudo: sudo moos-arm-remote ${action} ${target}" >&2
    exit 1
}
id "$target" >/dev/null 2>&1 || {
    echo "No such account: ${target}" >&2
    exit 1
}
uid="$(id -u "$target")"
home="$(getent passwd "$target" | cut -d: -f6)"
[ -n "$home" ] || { echo "Could not resolve ${target}'s home directory" >&2; exit 1; }

run_user() {
    runuser -u "$target" -- env \
        "HOME=${home}" \
        "XDG_RUNTIME_DIR=/run/user/${uid}" \
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${uid}/bus" \
        "$@"
}

status() {
    run_user systemctl --user --no-pager status \
        moos-arm-desktop.service app-org.kde.krdpserver.service
}

case "$action" in
    status)
        status
        exit
        ;;
    off)
        run_user systemctl --user disable --now app-org.kde.krdpserver.service \
            moos-arm-desktop.service 2>/dev/null || true
        echo "MoOS ARM remote desktop disabled for ${target}."
        exit
        ;;
    on) ;;
    *)
        echo "Usage: sudo moos-arm-remote <on|off|status> [user]" >&2
        exit 2
        ;;
esac

# PAM must have a real password to authenticate an RDP login and to preserve the
# project's password-required privilege boundary. The Oracle deployment user-data
# creates a unique management password; a locked image-default account is refused.
password_state="$(passwd -S "$target" 2>/dev/null | awk '{print $2}')"
case "$password_state" in
    P|PS) ;;
    *)
        echo "The ${target} account has no usable password." >&2
        echo "Recreate the instance with the documented management-password cloud-init user-data." >&2
        exit 1
        ;;
esac

loginctl enable-linger "$target"
systemctl start "user@${uid}.service"
for _ in $(seq 1 30); do
    [ -S "/run/user/${uid}/bus" ] && break
    sleep 1
done
[ -S "/run/user/${uid}/bus" ] || {
    echo "The systemd user bus for ${target} did not start." >&2
    exit 1
}

# KWin's virtual backend needs a DRM allocation device before it offers an
# OpenGL compositor. KRDP cannot capture a QPainter session, so this is a hard
# requirement rather than a cosmetic acceleration.
modprobe vgem
install -D -m0644 /dev/stdin /etc/modules-load.d/moos-arm-vgem.conf <<'MODLOAD'
vgem
MODLOAD
install -D -m0644 /dev/stdin /etc/udev/rules.d/61-moos-arm-vgem.rules <<'UDEV'
SUBSYSTEM=="drm", KERNEL=="card*", DEVPATH=="/devices/faux/vgem/drm/card*", GROUP="render", MODE="0660"
UDEV
udevadm control --reload-rules
udevadm trigger --subsystem-match=drm --action=change

kwin_drop="${home}/.config/systemd/user/plasma-kwin_wayland.service.d"
install -d -o "$target" -g "$target" -m0755 "$kwin_drop"
install -D -o "$target" -g "$target" -m0644 /dev/stdin \
    "${kwin_drop}/20-moos-arm-virtual-output.conf" <<'KWIN'
[Service]
Environment=LIBGL_ALWAYS_SOFTWARE=1
ExecStart=
ExecStart=/usr/bin/kwin_wayland_wrapper --virtual --width 1920 --height 1080
KWIN

desktop_unit="${home}/.config/systemd/user/moos-arm-desktop.service"
install -D -o "$target" -g "$target" -m0644 /dev/stdin "$desktop_unit" <<'DESKTOP'
[Unit]
Description=MoOS ARM headless Plasma Wayland desktop
Wants=dbus.socket
After=dbus.socket

[Service]
Type=simple
Environment=LIBGL_ALWAYS_SOFTWARE=1
ExecStart=/usr/bin/startplasma-wayland
ExecStopPost=/usr/bin/systemctl --user unset-environment DISPLAY WAYLAND_DISPLAY XAUTHORITY
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
DESKTOP

run_user systemctl --user daemon-reload
run_user systemctl --user enable --now moos-arm-desktop.service
for _ in $(seq 1 90); do
    run_user systemctl --user is-active --quiet plasma-workspace.target && break
    sleep 1
done
run_user systemctl --user is-active --quiet plasma-workspace.target || {
    echo "Plasma did not reach plasma-workspace.target for ${target}." >&2
    status || true
    exit 1
}

# This is KDE's documented headless KRDP setup: authorize the server in the
# portal store, generate per-instance TLS material, use the system account via
# PAM, then start the user service. No password appears in argv or a config file.
run_user flatpak permission-set kde-authorized remote-desktop org.kde.krdpserver yes
cert_dir="${home}/.local/share/krdpserver"
install -d -o "$target" -g "$target" -m0700 "$cert_dir"
if [ ! -s "${cert_dir}/krdp.crt" ] || [ ! -s "${cert_dir}/krdp.key" ]; then
    run_user openssl req -nodes -new -x509 \
        -keyout "${cert_dir}/krdp.key" \
        -out "${cert_dir}/krdp.crt" \
        -days 397 -batch
fi
run_user kwriteconfig6 --file krdpserverrc --group General \
    --key Certificate "${cert_dir}/krdp.crt"
run_user kwriteconfig6 --file krdpserverrc --group General \
    --key CertificateKey "${cert_dir}/krdp.key"
run_user kwriteconfig6 --file krdpserverrc --group General \
    --key SystemUserEnabled true
run_user kwriteconfig6 --file krdpserverrc --group General \
    --key LockOnDisconnect true
run_user systemctl --user enable --now app-org.kde.krdpserver.service

echo
echo "MoOS ARM remote desktop is running for ${target}."
echo "Keep port 3389 closed. From your PC run:"
echo "  ssh -N -L 3389:127.0.0.1:3389 ${target}@<public-ip>"
echo "Then connect the RDP client to localhost:3389 with ${target}'s system password."
REMOTE

# -----------------------------------------------------------------------------
# (7) Boot speed
# -----------------------------------------------------------------------------
# The same two wins the x86 editions take, for the same measured reasons.
echo "=== (7) boot speed ==="
# NetworkManager-wait-online gates network-online.target and blocks for up to 30 s
# on a machine whose network is already up; nothing in a MoOS boot needs to wait
# for it.
if [ -f /usr/lib/systemd/system/NetworkManager-wait-online.service ]; then
    systemctl disable NetworkManager-wait-online.service
else
    echo "FATAL: NetworkManager-wait-online.service is gone/renamed — this boot-speed fix now targets nothing"
    exit 1
fi
# systemd-udev-settle is deprecated upstream ("depending on it is a bug") and
# serialises the whole udev coldplug behind the slowest device.
systemctl mask systemd-udev-settle.service 2>/dev/null || true

# dbus-broker's default 90 s start timeout is the root of the slow-boot network
# cascade documented for the x86 editions; system_files ships the drop-in that
# shortens it. Prove it survived the copy rather than assuming.
test -f /usr/lib/systemd/system/dbus-broker.service.d/moos-start-timeout.conf || {
    echo "FATAL: the dbus-broker start-timeout drop-in did not arrive from system_files"; exit 1
}

# The x86 editions compile MoPlayer's Flutter bundle and Mo PC Remote's .NET
# agent in architecture-specific build stages. Those binaries do not exist in
# this deliberately lightweight ARM image. Do not leave launchers that open a
# control panel for a missing backend or a player wrapper with no bundle.
rm -f \
    /usr/bin/moplayer \
    /usr/bin/mo-pc-remote \
    /usr/share/applications/org.moos.moplayer.desktop \
    /usr/share/applications/org.moos.remote.desktop \
    /usr/share/metainfo/org.moos.moplayer.metainfo.xml
install -D -m0644 /dev/stdin /usr/share/doc/moos-arm/OMITTED.md <<'OMITTED'
# Intentionally omitted from MoOS ARM

- MoPlayer: its vendored Flutter Linux bundle is currently built only for x86_64.
- Mo PC Remote: its self-contained .NET agent is currently built only for x86_64.

The ARM cloud path uses KDE KRDP over an SSH tunnel (`moos-arm-remote`) instead.
No non-working launcher is shown for either omitted binary.
OMITTED

# -----------------------------------------------------------------------------
# (8) Identity
# -----------------------------------------------------------------------------
echo "=== (8) identity ==="
mkdir -p /usr/lib/moos
printf '%s\n' "${MOOS_EDITION}" > /usr/lib/moos/edition
printf '%s\n' "aarch64" > /usr/lib/moos/arch

# os-release is what every tool, every login banner and every bug report shows.
# A MoOS that introduces itself as Fedora is not MoOS.
cat > /usr/lib/os-release <<'OSREL'
NAME="MoOS"
PRETTY_NAME="MoOS"
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
CPE_NAME="cpe:/o:moos:moos:44"
VARIANT="MoOS"
VARIANT_ID=moos
OSREL
ln -sf ../usr/lib/os-release /etc/os-release
for _release in /etc/fedora-release /etc/redhat-release /etc/system-release; do
    rm -f "$_release"
    printf 'MoOS\n' > "$_release"
done

# Wayland is the only MoOS session. A package dependency must not quietly add a
# selectable X11 session after the curated list deliberately excluded it.
mapfile -t _x11_sessions < <(
    find /usr/share/xsessions -maxdepth 1 -type f -name '*.desktop' -print 2>/dev/null
)
if [ "${#_x11_sessions[@]}" -gt 0 ]; then
    echo "FATAL: an X11 desktop session reached the ARM image" >&2
    printf '  %s\n' "${_x11_sessions[@]}" >&2
    exit 1
fi
unset -v _x11_sessions

# -----------------------------------------------------------------------------
# (9) Rebuild the initramfs so the splash and the virtio drivers are in it
# -----------------------------------------------------------------------------
echo "=== (9) initramfs ==="
kver="$(rpm -q --qf '%{VERSION}-%{RELEASE}.%{ARCH}\n' kernel-core | tail -1)"
[ -n "${kver}" ] || { echo "FATAL: no kernel-core in the image"; exit 1; }
dracut --no-hostonly --force --reproducible \
    --add "ostree plymouth" \
    "/usr/lib/modules/${kver}/initramfs.img" "${kver}" 2>&1 | tail -20

# GATE: the splash has to actually be inside the initramfs. Everything else can
# be green while it is not, and the failure is only visible on a boot.
lsinitrd "/usr/lib/modules/${kver}/initramfs.img" > /tmp/moos-arm-initrd.txt 2>/dev/null || true
if [ -s /tmp/moos-arm-initrd.txt ]; then
    for _need in 'plymouth/themes/moos/moos.script' 'plymouth/themes/moos/intro1.png' \
                 'plymouth/themes/moos/moos.plymouth'; do
        grep -q "${_need}" /tmp/moos-arm-initrd.txt || {
            echo "FATAL: the initramfs lacks ${_need} — the boot animation would not render"
            exit 1
        }
    done
    grep -qE 'plymouth/(script\.so|script)' /tmp/moos-arm-initrd.txt || {
        echo "FATAL: the initramfs lacks Plymouth's script plugin — the theme cannot render"
        exit 1
    }
    echo "=== initramfs carries the MoOS splash ==="
else
    echo "WARNING: lsinitrd produced nothing; the splash could not be verified here"
fi

# The ARM edition does not get a reduced identity standard. These are the same
# finished-image gates the x86 editions run, after every package and overwrite.
echo "=== (9b) finished-image identity gates ==="
python3 /ctx/verify_identity.py
python3 /ctx/verify_image_experience.py
python3 /ctx/verify_no_foreign_identity.py

# -----------------------------------------------------------------------------
# (10) Clean up so `bootc container lint` passes
# -----------------------------------------------------------------------------
dnf5 clean all
rm -rf /var/cache/* /var/log/* /tmp/* || true
# bootc requires /var to be empty of anything the image is not entitled to own.
find /var -mindepth 1 -maxdepth 1 ! -name 'lib' ! -name 'tmp' -exec rm -rf {} + 2>/dev/null || true

echo "=== MoOS ARM build complete: ${MOOS_EDITION} (aarch64) ==="
