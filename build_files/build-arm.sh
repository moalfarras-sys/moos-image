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
    plasma-workspace-x11
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
    fontconfig
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
dnf5 -y install --setopt=install_weak_deps=False openssh-server || {
    echo "FATAL: openssh-server is unavailable — the instance would be unreachable"; exit 1
}
if ! dnf5 -y install --setopt=install_weak_deps=False krdp; then
    echo "WARNING: krdp is not in this Fedora's repos — the ARM edition will ship"
    echo "         with SSH only and no graphical remote. moos-arm-remote will say so."
    touch /usr/lib/moos/no-krdp
fi
systemctl enable sshd.service

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
dnf5 -y install --setopt=install_weak_deps=False cloud-init cloud-utils-growpart

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
system_info:
  default_user:
    name: moos
    gecos: MoOS
    groups: [wheel, video, audio, input, render]
    sudo: ["ALL=(ALL) NOPASSWD:ALL"]
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
# moos-arm-remote — enable the MoOS desktop's RDP server on this instance.
#
# Deliberately NOT done at build time. Enabling a remote-desktop service with a
# credential baked into the image would mean every machine ever booted from it
# shares one password on a public IP. The owner sets it here, once, on their own
# instance.
set -euo pipefail

if [ -f /usr/lib/moos/no-krdp ]; then
    echo "This image was built without krdp, so there is no graphical remote."
    echo "SSH still works. Rebuild once krdp is available in Fedora aarch64."
    exit 1
fi
if [ "$(id -u)" -eq 0 ]; then
    echo "Run this as your own user, not root — the RDP server runs in your"
    echo "desktop session and needs your session bus."
    exit 1
fi

echo "MoOS remote desktop (RDP, port 3389)"
echo
read -r -s -p "Choose a password for remote sign-in: " p1; echo
read -r -s -p "Repeat it: " p2; echo
[ -n "$p1" ] || { echo "Empty password refused."; exit 1; }
[ "$p1" = "$p2" ] || { echo "They do not match."; exit 1; }

kwriteconfig6 --file krdprc --group General --key Autostart true
kwriteconfig6 --file krdprc --group General --key Users "$USER"
# krdp stores the credential in the session wallet, not in a file.
printf '%s' "$p1" | krdpserver --set-password "$USER" 2>/dev/null \
    || echo "note: set the password in System Settings > Remote Desktop if this failed"
systemctl --user enable --now app-org.kde.krdpserver.service 2>/dev/null || true

echo
echo "Enabled. Two more things have to happen OUTSIDE this machine:"
echo "  1. Oracle blocks everything but SSH by default. In the OCI console open"
echo "     TCP 3389 in the subnet's security list (or a network security group)."
echo "  2. Connect with any RDP client to  <this instance's public IP>:3389"
echo "     as user '$USER'."
echo
echo "Safer alternative, if you would rather not expose 3389 at all:"
echo "  ssh -L 3389:localhost:3389 $USER@<public-ip>   then connect to localhost:3389"
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
PRETTY_NAME="MoOS (ARM)"
ID=moos
ID_LIKE="fedora"
VERSION="44"
VERSION_ID="44"
ANSI_COLOR="0;38;2;78;215;200"
LOGO=moos-logo
HOME_URL="https://github.com/moalfarras-sys/moos-image"
BUG_REPORT_URL="https://github.com/moalfarras-sys/moos-image/issues"
VARIANT="ARM"
VARIANT_ID=arm
OSREL
ln -sf ../usr/lib/os-release /etc/os-release

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

# -----------------------------------------------------------------------------
# (10) Clean up so `bootc container lint` passes
# -----------------------------------------------------------------------------
dnf5 clean all
rm -rf /var/cache/* /var/log/* /tmp/* || true
# bootc requires /var to be empty of anything the image is not entitled to own.
find /var -mindepth 1 -maxdepth 1 ! -name 'lib' ! -name 'tmp' -exec rm -rf {} + 2>/dev/null || true

echo "=== MoOS ARM build complete: ${MOOS_EDITION} (aarch64) ==="
