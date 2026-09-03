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
#   already there and assume x86: an NVIDIA akmods stage, i686 multilib, and a
#   gaming host stack. Threading a new guard through all of that would put the
#   owner's daily-driver image one editing mistake away from breaking. The two
#   first-party compiled apps instead have native arm64 stages in Containerfile.arm.
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
    # Fedora 44 merged plasma-workspace-wayland into plasma-workspace
    # (changelog 2025-06-25). rpm -q plasma-workspace-wayland is therefore
    # empty even when Wayland is present; startplasma-wayland ships here.
    plasma-workspace plasma-desktop plasma-milou
    kwin kwin-wayland kwin-libs
    systemsettings kscreen kscreenlocker
    plasma-nm plasma-pa plasma-systemmonitor
    # MoOS routes to these backends from Store and Command Center. Shipping the
    # QML cards without their executables/KCMs creates polished dead buttons.
    plasma-discover plasma-discover-flatpak plasma-discover-kns
    kinfocenter bluedevil plasma-print-manager flatpak-kcm
    xdg-desktop-portal-kde xdg-desktop-portal
    qt6-qtwayland qt6-qtsvg qt6-qtdeclarative qt6-qtmultimedia qt6-qtimageformats
    kf6-kirigami kf6-kirigami-addons kf6-qqc2-desktop-style
    dolphin konsole ark kate gwenview haruna kf6-baloo-file
    plasma-breeze breeze-icon-theme
    pipewire pipewire-pulseaudio wireplumber
    NetworkManager NetworkManager-wifi
    plymouth plymouth-plugin-script plymouth-plugin-two-step plymouth-system-theme
    dracut-network
    python3 python3-gobject
    fontconfig gtk3 gtk4 libadwaita mpv-libs
    mesa-dri-drivers mesa-libEGL mesa-libgbm
    openssh-server cloud-init cloud-utils-growpart
    firewalld flatpak openssl sudo
    # Architecture-independent MoOS desktop assets are generated after the
    # final RPM transaction by finalize_moos_desktop.sh.
    git-core curl tar xz gtk-update-icon-cache
    # Same local-brain engine as x86. The model remains an explicit download;
    # only the small routing/control services start with the user session.
    ramalama
    # Day-2 updates resolve a mutable release tag to an exact signed digest.
    # fedora-bootc supplies rpm-ostree today, but both tools are explicit product
    # dependencies rather than accidental base-image contents.
    rpm-ostree skopeo
    # Native Mo PC Remote runtime. Encoders are capability-probed and JPEG is
    # the real fallback when a virtual GPU exposes no hardware codec.
    ydotool wl-clipboard grim spectacle python3-websockets poppler-utils qrencode
    gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good
    gstreamer1-plugins-bad-free pipewire-gstreamer
)

# Mo PC Remote publishes its authenticated loopback agent through Tailscale
# Serve. The first real Oracle A1 deployment proved that all of the remote
# desktop UI and services can be present while the ARM image has no `tailscale`
# binary at all, leaving the owner with no secure browser URL. Keep the same
# small, static repository definition as the x86 build; dnf still verifies the
# repository metadata and installs the native aarch64 RPM.
cat > /etc/yum.repos.d/tailscale.repo <<'TAILSCALE_REPO'
[tailscale-stable]
name=Tailscale stable
baseurl=https://pkgs.tailscale.com/stable/fedora/$basearch
enabled=1
type=rpm
repo_gpgcheck=1
gpgcheck=1
gpgkey=https://pkgs.tailscale.com/stable/fedora/repo.gpg
TAILSCALE_REPO
_PLASMA+=(tailscale)
dnf5 -y install --setopt=install_weak_deps=False "${_PLASMA[@]}"

# cosign is not always packaged for aarch64 — install the static binary when needed.
if ! command -v cosign >/dev/null 2>&1; then
    if ! dnf5 -y install --setopt=install_weak_deps=False cosign 2>/dev/null; then
        curl -fsSL "https://github.com/sigstore/cosign/releases/download/v2.4.1/cosign-linux-arm64" \
            -o /usr/bin/cosign
        chmod +x /usr/bin/cosign
    fi
fi
command -v cosign >/dev/null || { echo "FATAL: cosign unavailable for UTM net install"; exit 1; }

# Prefer a portable software H.264 encoder when Fedora's Cisco repository has
# one for aarch64. The helper auditions PLAYING state and automatically falls
# back to JPEG when the factory is absent or unusable on the VM.
dnf5 -y install --allowerasing openh264 gstreamer1-plugin-openh264 \
    || echo "ARM NOTE: OpenH264 unavailable; Mo PC Remote will capability-fallback to JPEG"

# Fonts: MoOS's UI is IBM Plex, and its Arabic surfaces are first-class (the
# owner's own locale). A desktop that falls back to a substitute face for Arabic
# is a broken desktop, not a cosmetic issue, so these are not optional.
dnf5 -y install --setopt=install_weak_deps=False \
    ibm-plex-sans-fonts ibm-plex-sans-arabic-fonts ibm-plex-mono-fonts \
    google-noto-sans-fonts google-noto-sans-arabic-fonts \
    google-noto-color-emoji-fonts jetbrains-mono-fonts
dnf5 -y install langpacks-ar langpacks-en

# Kawkab Mono — the Arabic terminal font, pinned by digest exactly like the
# x86 build (build_files/build.sh section (c4)). Without it, the fontconfig
# rule /etc/fonts/conf.d/61-moos-brand.conf ships in the ARM image pointing at
# a family that does not exist there: JetBrains Mono (no Arabic glyphs) falls
# through to a proportional Arabic face and Konsole renders الطرفية as
# ا ل ط ر ف ي ة — connected cursive shattered into loose letters. Arabic is a
# first-class MoOS surface; an ARM Konsole that cannot draw it is broken, not
# a cosmetic gap. The digest pin means a changed upstream tarball fails the
# build instead of silently shipping something else.
kawkab_ver=0.501
kawkab_sha=11c06f57dddefaf0166d74caaa072865ab6ff8d34076e7ec5d2c20edda145666
kawkab_zip=$(mktemp)
curl -Lf --retry 5 --retry-all-errors --retry-delay 2 --connect-timeout 30 \
    -o "${kawkab_zip}" \
    "https://github.com/aiaf/kawkab-mono/releases/download/v${kawkab_ver}/kawkab-mono-${kawkab_ver}.zip"
echo "${kawkab_sha}  ${kawkab_zip}" | sha256sum -c -
mkdir -p /usr/share/fonts/kawkab-mono
python3 -m zipfile -e "${kawkab_zip}" /tmp/
install -m 0644 "/tmp/kawkab-mono-${kawkab_ver}"/KawkabMono-*.ttf /usr/share/fonts/kawkab-mono/
install -m 0644 "/tmp/kawkab-mono-${kawkab_ver}/OFL.txt" /usr/share/fonts/kawkab-mono/
rm -rf "${kawkab_zip}" "/tmp/kawkab-mono-${kawkab_ver}"
fc-cache -f /usr/share/fonts/kawkab-mono
# Gate it: a missing terminal font is invisible until an Arabic user types.
test -f /usr/share/fonts/kawkab-mono/KawkabMono-Regular.ttf \
    || { echo "GATE FAIL: Kawkab Mono did not install on ARM"; exit 1; }
# Ask the question the way Konsole asks it (sorted fallback list, see the
# x86 build.sh commentary for why plain fc-match answers the wrong question):
# the first non-JetBrains-Mono face for Arabic must be Kawkab Mono.
arabic_fallback="$(fc-match -s 'JetBrains Mono:lang=ar' | grep -v '"JetBrains Mono"' | head -1)"
case "${arabic_fallback}" in
    *Kawkab*) : ;;
    *) echo "GATE FAIL: Arabic terminal fallback is '${arabic_fallback}', expected Kawkab Mono"; exit 1 ;;
esac

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
dnf5 -y install --setopt=install_weak_deps=False krdp || {
    echo "FATAL: krdp is unavailable — an Oracle desktop with no graphical access"
    echo "       is not a releasable MoOS ARM image."
    exit 1
}

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

# system_files is architecture-independent, but its broad icon themes, pointer
# binaries and plasma-login account palette are generated at image build time.
# The first boot-proven ARM image skipped this x86-owned step: the greeter drew
# only wallpaper/language, logged missing MoOSUI2/MoOS pointer themes, and kept
# the compiled Breeze QML preference. Finalize the SAME desktop contract here.
bash /ctx/finalize_moos_desktop.sh

# Mo AI is one system on every architecture. Its pure-QML frontend always talks
# to these loopback authorities, so leaving them disabled makes the ARM window
# open while every live status/settings request is dead. The local model service
# itself stays on-demand and no model is downloaded in the image.
for unit in \
    moai-gateway.service moai-control.service moai-agent-api.service \
    moai-wake.service moai-idle.timer openclaw-idle.timer \
    moos-ensure-brain.timer moos-theme-sync.path \
    moos-cloud-audio.service moos-update-ready.timer moos-reclaim-disk.timer; do
    test -f "/usr/lib/systemd/user/${unit}" || {
        echo "FATAL: shared user authority is missing: ${unit}"
        exit 1
    }
done
systemd-analyze verify \
    /usr/lib/systemd/user/moai-gateway.service \
    /usr/lib/systemd/user/moai-control.service \
    /usr/lib/systemd/user/moai-agent-api.service \
    /usr/lib/systemd/user/moai-wake.service
systemctl --global enable \
    moai-gateway.service moai-control.service moai-agent-api.service \
    moai-wake.service moai-idle.timer openclaw-idle.timer \
    moos-ensure-brain.timer moos-theme-sync.path \
    moos-cloud-audio.service moos-update-ready.timer moos-reclaim-disk.timer

systemctl enable NetworkManager.service sshd.service firewalld.service tailscaled.service
systemctl enable moos-auto-update.timer
# moos-image-update is the only OS deployment writer. The Fedora bootc base
# enables its own mutable-tag fetch timer, so disable both upstream rivals on
# ARM just as the shared x86 build does. Serial boot proof caught this timer
# active in the finished ARM disk even though the source gates were green.
systemctl disable rpm-ostreed-automatic.timer 2>/dev/null || true
systemctl disable bootc-fetch-apply-updates.timer 2>/dev/null || true
# Fedora 44's documented PLM switch uses --force because the graphical-login
# alias may still point at a display manager inherited from a package preset.
systemctl enable --force plasmalogin.service
systemctl set-default graphical.target

# QEMU virtio-gpu proof VMs need software GL for plasmalogin's KWin. Without it
# runtime reports graphical=active while screendump stays near-black (~0.011 stddev).
[ -x /usr/libexec/moos-greeter-gl-env ] || {
    echo "FATAL: moos-greeter-gl-env is missing — ARM greeter cannot fall back to software GL"
    exit 1
}
install -D -m0644 /dev/stdin \
    /usr/lib/systemd/system/plasmalogin.service.d/20-moos-arm-greeter-gl.conf <<'PLMDROP'
[Service]
ExecStartPre=-/usr/libexec/moos-greeter-gl-env
PLMDROP
install -D -m0644 /dev/stdin \
    /usr/lib/systemd/user/plasma-login-kwin_wayland.service.d/10-moos-arm-greeter-gl.conf <<'KWINDROP'
[Service]
EnvironmentFile=-/run/moos/plasmalogin-kwin.env
Environment=LIBGL_ALWAYS_SOFTWARE=1
Environment=GALLIUM_DRIVER=llvmpipe
# UTM/QEMU must paint the real virtio scanout. A display-less Oracle machine
# receives the virtual backend from the same display-aware launcher.
ExecStart=
ExecStart=/usr/libexec/moos-arm-greeter-kwin
KWINDROP
for _greeter_unit in plasma-login.service plasma-wallpaper.service; do
    install -D -m0644 /dev/stdin \
        "/usr/lib/systemd/user/${_greeter_unit}.d/10-moos-arm-software-scenegraph.conf" <<'QTSOFTWARE'
[Service]
Environment=QT_QUICK_BACKEND=software
QTSOFTWARE
done
unset -v _greeter_unit
install -D -m0644 /dev/stdin /etc/environment.d/60-moos-arm-llvmpipe.conf <<'LLVMPIPE'
# MoOS ARM: software rendering for every user session, including plasmalogin.
LIBGL_ALWAYS_SOFTWARE=1
GALLIUM_DRIVER=llvmpipe
LP_NUM_THREADS=2
QT_QUICK_BACKEND=software
LLVMPIPE
install -D -m0644 /dev/stdin /etc/modules-load.d/moos-arm-vgem.conf <<'MODLOAD'
vgem
MODLOAD

# Defence in depth around the public cloud VM. SSH is the only service exposed
# by the image. KRDP remains reachable through an SSH tunnel to localhost; this
# image never opens 3389 on the host firewall.
if [ "$(firewall-offline-cmd --get-default-zone)" != "public" ]; then
    firewall-offline-cmd --set-default-zone=public
fi
if ! firewall-offline-cmd --zone=public --query-service=ssh >/dev/null; then
    firewall-offline-cmd --zone=public --add-service=ssh
fi
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
# The local cloud-init stage runs before the system D-Bus. Its stock hostname
# module calls hostnamectl there and permanently marks first boot degraded.
# Preserve during cloud-init; moos-cloud-hostname applies the validated provider
# name after metadata and D-Bus are both ready.
preserve_hostname: true
# Oracle attaches a boot volume that is larger than the imported image (50 GB by
# default on the Always Free tier, against a ~10 GB image). Without growpart the
# machine boots with the image's original small root and fills up.
# The stock modules see composefs at `/` on bootc and therefore try to resize
# `/dev/composefs`. Fedora bootc already owns the correct physical-/sysroot
# implementation in bootc-generic-growpart; do not add a second growpart writer.
growpart:
  # YAML 1.1 treats an unquoted `off` as Boolean false. cloud-init 26 warns
  # that the Boolean form is deprecated, so keep the required string type.
  mode: "off"
resize_rootfs: false
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
    # Only wheel is a persistent privilege group.  Desktop device access is
    # granted per active seat through logind/uaccess.  Some minimal ARM images
    # do not create the legacy audio/video/input/render groups, and naming them
    # here makes cloud-init abort before it can install the SSH key.
    groups: [wheel]
    shell: /bin/bash
CLOUDCFG
systemctl enable cloud-init-network.service cloud-init-local.service \
    cloud-config.service cloud-final.service
# One disk-growth authority only. The first boot proof caught the custom MoOS
# helper racing Fedora bootc's already-enabled growpart service against the same
# mounted root partition; the duplicate timed out and left the release red.
test -f /usr/lib/systemd/system/bootc-generic-growpart.service || {
    echo "FATAL: Fedora bootc's physical root grow service is missing"
    exit 1
}
systemctl enable bootc-generic-growpart.service
systemctl enable moos-arm-block-coldplug.service
install -D -m0644 /dev/stdin /etc/systemd/system.conf.d/moos-arm-device-timeout.conf <<'TIMEOUT'
# Slow aarch64 virt (TCG proof VMs) can miss boot-partition UUID links for up
# to ~60s while moos-arm-block-coldplug republishes them. The default 45s device
# timeout sent the release gate to emergency mode even when coldplug was running.
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
systemctl enable moos-cloud-hostname.service
systemctl enable moos-cloud-account-ready.service

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
# Image composition has no syslog socket. Console/file output remains captured by
# CI, so do not ask dracut to emit a misleading "No /dev/log" error.
sysloglvl="0"
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
# The greeter has no interactive seat ACL before authentication. Give its
# dedicated user group access to the real virtio scanout without opening DRM
# devices to accounts outside the standard video/render groups.
SUBSYSTEM=="drm", KERNEL=="card*", GROUP="video", MODE="0660"
SUBSYSTEM=="drm", KERNEL=="renderD*", GROUP="render", MODE="0660"
SUBSYSTEM=="drm", KERNEL=="card*", DEVPATH=="/devices/faux/vgem/drm/card*", GROUP="render", MODE="0660"
UDEV
for _group in video render; do
    getent group "${_group}" >/dev/null 2>&1 \
        || { echo "FATAL: ARM DRM group ${_group} is missing"; exit 1; }
    usermod -aG "${_group}" plasmalogin
done
unset -v _group
udevadm control --reload-rules
udevadm trigger --subsystem-match=drm --action=change

kwin_drop="${home}/.config/systemd/user/plasma-kwin_wayland.service.d"
install -d -o "$target" -g "$target" -m0755 "$kwin_drop"
install -D -o "$target" -g "$target" -m0644 /dev/stdin \
    "${kwin_drop}/20-moos-arm-virtual-output.conf" <<'KWIN'
[Service]
Environment=LIBGL_ALWAYS_SOFTWARE=1
ExecStart=
# This remains a Wayland-native session. Xwayland is the compatibility bridge
# used by ksmserver and older developer apps; omitting it leaves the desktop
# visible but crashes session management and several tray helpers at every login.
ExecStart=/usr/bin/kwin_wayland_wrapper --virtual --width 1920 --height 1080 --xwayland
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

# The shared x86 desktop policy contains game-specific preemption and Intel
# split-lock arguments. They have no measured ARM benefit, and one names an
# x86-only mechanism, so the architecture layer must not carry them into an
# Ampere/UTM kernel command line. mokernel also declares them only on x86_64.
rm -f /usr/lib/bootc/kargs.d/30-moos-latency.toml

# dbus-broker's default 90 s start timeout is the root of the slow-boot network
# cascade documented for the x86 editions; system_files ships the drop-in that
# shortens it. Prove it survived the copy rather than assuming.
test -f /usr/lib/systemd/system/dbus-broker.service.d/moos-start-timeout.conf || {
    echo "FATAL: the dbus-broker start-timeout drop-in did not arrive from system_files"; exit 1
}

# Both first-party apps arrive from native aarch64 build stages. Remote remains
# opt-in exactly like x86: the panel starts its service explicitly, so a fresh
# cloud/UTM desktop pays zero idle daemon cost.
chmod 0755 /usr/lib/mo-remote/MoRemotePersonal \
    /usr/lib/mo-remote/mo-remote-portal.py \
    /usr/bin/mo-pc-remote \
    /usr/bin/moplayer
systemctl --global disable mo-remote-personal.service 2>/dev/null || true

# -----------------------------------------------------------------------------
# (8) Identity
# -----------------------------------------------------------------------------
echo "=== (8) identity ==="
mkdir -p /usr/lib/moos
printf '%s\n' "${MOOS_EDITION}" > /usr/lib/moos/edition
printf '%s\n' "aarch64" > /usr/lib/moos/arch

# shim reads this UTF-16 CSV when firmware creates its persistent boot entry.
# The signed loader stays in its required vendor directory; its visible label
# is MoOS on ARM just as it is on x86.
python3 /ctx/rewrite_firmware_label.py

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

# Plasma packages re-ship fedora-logos after the first COPY of system_files.
# The overlay restores MoOS files that exist in the tree, but fedora-logos
# still owns extra sizes and SVG names that system_files never overrode.
# The x86 image closes that in build.sh section (z2). Without the same seal
# here, verify_identity.py fails on fedora-logo-icon.png remaining Fedora art —
# proven on the native aarch64 runner, 2026-08-19.
_moos_src=/usr/share/moos/moos-logo.png
[ -f "$_moos_src" ] || _moos_src=/usr/share/pixmaps/moos-logo.png
[ -f "$_moos_src" ] || {
    echo "FATAL: the canonical MoOS logo is missing; identity cannot be sealed"
    exit 1
}
_names="fedora-logo-icon fedora-logo fedora-logo-small fedora-gdm-logo \
        start-here-fedora org.fedoraproject.AnacondaInstaller \
        org.fedoraproject.fedora redhat redhat-logo red-hat anaconda"
_all_pred=()
for _name in $_names; do
    _all_pred+=(-o -name "${_name}.svg" -o -name "${_name}.svgz" \
                -o -name "${_name}.png" -o -name "${_name}.xpm")
done
find /usr/share/icons \( -type f -o -type l \) \( "${_all_pred[@]:1}" \) -print0 2>/dev/null \
    | while IFS= read -r -d '' _f; do
        case "$_f" in
            *.svg|*.svgz) rm -f "$_f" ;;
            *.png|*.xpm)
                _dir="$(dirname "$_f")"
                _sized="$_dir/moos-logo.png"
                [ -f "$_sized" ] || _sized="$_moos_src"
                rm -f "$_f"
                cp -f "$_sized" "$_f"
                ;;
        esac
    done || true
for _px in fedora-logo.png fedora-logo-small.png fedora-gdm-logo.png; do
    [ -f "/usr/share/pixmaps/$_px" ] && cp -f "$_moos_src" "/usr/share/pixmaps/$_px" || true
done
for _themedir in /usr/share/icons/*/; do
    [ -f "${_themedir}index.theme" ] && {
        gtk-update-icon-cache -f "$_themedir" 2>/dev/null \
            || gtk4-update-icon-cache -f "$_themedir" 2>/dev/null \
            || true
    }
done
unset -v _moos_src _names _all_pred _f _dir _sized _name _px _themedir

# plasma-welcome is not in the ARM package list, but identity gates still
# require the silent no-op stub so a leftover KDE first-run job cannot toast.
# Match build.sh: cat + chmod, not `install /dev/stdin` (install may seek).
cat > /usr/bin/plasma-welcome <<'PWBIN'
#!/bin/sh
# MoOS ARM: the upstream Plasma welcome is replaced by moos-firstrun/moos-welcome.
# This no-op exists so any first-run launch of "plasma-welcome" succeeds silently.
exit 0
PWBIN
chmod 0755 /usr/bin/plasma-welcome
mkdir -p /etc/xdg/autostart /usr/share/applications
cat > /usr/share/applications/org.kde.plasma-welcome.desktop <<'PWAPP'
[Desktop Entry]
Type=Application
Name=Plasma Welcome (disabled by MoOS)
Comment=Replaced by the MoOS Welcome (moos-firstrun)
Exec=/bin/true
Icon=moos-logo
Terminal=false
NoDisplay=true
Hidden=true
OnlyShowIn=KDE;
PWAPP
cat > /etc/xdg/autostart/org.kde.plasma-welcome.desktop <<'PWEOF'
[Desktop Entry]
Type=Application
Name=Plasma Welcome (disabled by MoOS)
Exec=/bin/true
Hidden=true
NoDisplay=true
X-KDE-autostart-condition=
PWEOF

# Keep the package-management engine for updates, but expose only Mo Store as a
# storefront. ARM previously skipped the x86 rewrite and showed both launchers.
_disc=/usr/share/applications/org.kde.discover.desktop
if [ -f "$_disc" ]; then
    sed -i \
        -e '/^Name\[/d' \
        -e 's|^Name=.*|Name=Mo Store|' \
        -e '/^GenericName\[/d' \
        -e 's|^GenericName=.*|GenericName=App Store|' \
        -e 's|^Icon=.*|Icon=mo-store|' \
        "$_disc"
    sed -i '/^Name=Mo Store$/a Name[ar]=متجر MoOS' "$_disc"
    grep -q '^GenericName=' "$_disc" \
        && sed -i '/^GenericName=App Store$/a GenericName[ar]=متجر التطبيقات' "$_disc" \
        || true
    grep -q '^NoDisplay=' "$_disc" \
        && sed -i 's|^NoDisplay=.*|NoDisplay=true|' "$_disc" \
        || sed -i '/^\[Desktop Entry\]/a NoDisplay=true' "$_disc"
fi
unset -v _disc

# Fedora's Global Themes and wallpapers arrive with plasma-desktop on the
# bootc base. x86 closes this in build.sh (z2a). Left in place they appear
# in the Appearance picker as "Fedora" — proven on the native aarch64
# runner after identity and ARM gates already passed, 2026-08-19.
_kde_profile=/usr/share/kde-settings/kde-profile/default/xdg
if [ -f "${_kde_profile}/kdeglobals" ]; then
    sed -i 's|^LookAndFeelPackage=.*|LookAndFeelPackage=org.moos.ui2|' "${_kde_profile}/kdeglobals"
fi
if [ -f "${_kde_profile}/kscreenlockerrc" ]; then
    sed -i 's|/usr/share/backgrounds/fedora-workstation.*|/usr/share/wallpapers/MoOSUI2Graphite|' \
        "${_kde_profile}/kscreenlockerrc"
    sed -i 's|/usr/share/wallpapers/Fedora.*|/usr/share/wallpapers/MoOSUI2Graphite|' \
        "${_kde_profile}/kscreenlockerrc"
fi
rm -rf /usr/share/plasma/look-and-feel/org.fedoraproject.fedora.desktop \
       /usr/share/plasma/look-and-feel/org.fedoraproject.fedoradark.desktop \
       /usr/share/plasma/look-and-feel/org.fedoraproject.fedoralight.desktop \
       /usr/share/wallpapers/Fedora \
       /usr/share/backgrounds/fedora-workstation
if grep -rqE "org\.fedoraproject\.fedora|backgrounds/fedora-workstation|wallpapers/Fedora" \
        /etc/xdg /usr/share/kde-settings /usr/share/plasma 2>/dev/null; then
    echo "FATAL: a config still points at a Fedora theme/wallpaper that was removed:"
    grep -rlE "org\.fedoraproject\.fedora|backgrounds/fedora-workstation|wallpapers/Fedora" \
        /etc/xdg /usr/share/kde-settings /usr/share/plasma 2>/dev/null | sed 's/^/       /'
    exit 1
fi
unset -v _kde_profile

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
# (8b) Container policy — every day-2 ARM update must verify its signature
# -----------------------------------------------------------------------------
grep -q "use-sigstore-attachments" /etc/containers/registries.d/moalfarras-sys.yaml \
    || { echo "FATAL: ARM lacks the sigstore attachment registry mapping"; exit 1; }
[ -s /etc/pki/containers/moos.pub ] \
    || { echo "FATAL: ARM lacks the MoOS container signing public key"; exit 1; }
[ -f /etc/containers/policy.json ] \
    || { echo "FATAL: ARM lacks /etc/containers/policy.json"; exit 1; }
python3 - <<'PYSEC'
import json

path = "/etc/containers/policy.json"
with open(path, encoding="utf-8") as source:
    policy = json.load(source)
docker = policy.setdefault("transports", {}).setdefault("docker", {})
# bootc rejects a policy whose global fallback is insecure, even if this exact
# registry has a signed rule. Preserve normal user pulls at docker's transport
# fallback while making the top-level policy fail closed.
policy["default"] = [{"type": "reject"}]
docker[""] = [{"type": "insecureAcceptAnything"}]
docker["ghcr.io/moalfarras-sys"] = [{
    "type": "sigstoreSigned",
    "keyPath": "/etc/pki/containers/moos.pub",
    "signedIdentity": {"type": "matchRepository"},
}]
# Disk composition imports the already-pulled candidate from BIB's private
# root containers-storage. That local transport cannot carry registry sigstore
# attachments; the installed docker origin remains digest-pinned and
# signature-enforced for every network update.
policy.setdefault("transports", {})["containers-storage"] = {
    "": [{"type": "insecureAcceptAnything"}],
}
with open(path, "w", encoding="utf-8") as target:
    json.dump(policy, target, indent=4)
PYSEC
python3 - <<'PYSEC'
import json

entry = json.load(open("/etc/containers/policy.json", encoding="utf-8"))[
    "transports"
]["docker"]["ghcr.io/moalfarras-sys"]
policy = json.load(open("/etc/containers/policy.json", encoding="utf-8"))
if len(entry) != 1 or entry[0].get("type") != "sigstoreSigned":
    raise SystemExit("FATAL: ARM registry policy does not require sigstoreSigned")
if entry[0].get("keyPath") != "/etc/pki/containers/moos.pub":
    raise SystemExit("FATAL: ARM registry policy does not use the MoOS public key")
if policy.get("default") != [{"type": "reject"}]:
    raise SystemExit("FATAL: ARM container policy has a permissive global default")
if policy.get("transports", {}).get("docker", {}).get("") != [
    {"type": "insecureAcceptAnything"}
]:
    raise SystemExit("FATAL: ARM ordinary user container pulls lost their docker fallback")
if policy.get("transports", {}).get("containers-storage", {}).get("") != [
    {"type": "insecureAcceptAnything"}
]:
    raise SystemExit("FATAL: ARM local disk composition cannot import containers-storage")
PYSEC

# -----------------------------------------------------------------------------
# (9) Rebuild the initramfs so the splash and the virtio drivers are in it
# -----------------------------------------------------------------------------
echo "=== (9) initramfs ==="
# Fedora's package transaction writes the compiled hwdb into /etc. On a fresh
# bootc deployment /etc is newer than the image and systemd rebuilds that 14 MB
# database before it starts real-root udevd. The ARM release proof measured the
# consequence under TCG: /boot, /boot/efi and ttyAMA0 device units expired while
# udevd was still blocked. Compile the immutable database into /usr once here;
# local administrator overrides still re-enable the upstream update service.
bash /ctx/compile_system_hwdb.sh
kver="$(rpm -q --qf '%{VERSION}-%{RELEASE}.%{ARCH}\n' kernel-core | tail -1)"
[ -n "${kver}" ] || { echo "FATAL: no kernel-core in the image"; exit 1; }
# bootc keeps /root as a symlink to mutable /var/roothome, while an image build
# deliberately leaves /var empty. dracut resolves that root home while composing
# its passwd payload; with a dangling target it logs a false-success ERROR for
# `/root`. Materialize it only for the compose, then restore the clean /var
# contract before bootc lint.
install -d -m0700 /var/roothome
dracut --no-hostonly --force --reproducible \
    --add "ostree plymouth" \
    "/usr/lib/modules/${kver}/initramfs.img" "${kver}" 2>&1 | tail -20
rmdir /var/roothome

# GATE: the splash has to actually be inside the initramfs. Everything else can
# be green while it is not, and the failure is only visible on a boot.
lsinitrd "/usr/lib/modules/${kver}/initramfs.img" > /tmp/moos-arm-initrd.txt 2>/dev/null \
    || { echo "FATAL: lsinitrd could not inspect the deployed ARM initramfs"; exit 1; }
[ -s /tmp/moos-arm-initrd.txt ] \
    || { echo "FATAL: lsinitrd produced no ARM initramfs inventory"; exit 1; }
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
grep -q 'ostree-prepare-root' /tmp/moos-arm-initrd.txt || {
    echo "FATAL: the ARM initramfs lacks ostree-prepare-root — deployed root cannot mount"
    exit 1
}
# Fedora's aarch64 kernel deliberately compiles the root-disk, PCI transport and
# console virtio drivers into vmlinux. A built-in has no .ko to put in initramfs,
# so testing only the archive invents a failure on the exact kernel that boots.
# Prove every required driver through modinfo; loadable drivers must additionally
# be present in the initramfs inventory.
for _driver in virtio_blk virtio_pci virtio_scsi virtio_net virtio_gpu virtio_console; do
    _driver_file="$(modinfo -k "${kver}" -F filename "${_driver}" 2>/dev/null)" || {
        echo "FATAL: the ARM kernel does not provide ${_driver}"
        exit 1
    }
    if [ "${_driver_file}" = "(builtin)" ]; then
        grep -qE "/${_driver}\\.ko$" "/usr/lib/modules/${kver}/modules.builtin" || {
            echo "FATAL: modinfo claims ${_driver} is built-in but modules.builtin disagrees"
            exit 1
        }
        echo "       ${_driver}: built into the ARM kernel"
    else
        _driver_basename="${_driver_file##*/}"
        grep -qF "${_driver_basename}" /tmp/moos-arm-initrd.txt || {
            echo "FATAL: the ARM initramfs lacks ${_driver} (${_driver_basename})"
            exit 1
        }
        echo "       ${_driver}: ${_driver_basename} in initramfs"
    fi
done
unset -v _driver _driver_file _driver_basename
echo "=== initramfs carries OSTree, virtio and the MoOS splash ==="

# The ARM edition does not get a reduced identity standard. These are the same
# identity and foreign-brand gates the x86 editions run, plus ARM-specific
# finished-image checks. The profile only removes requirements for the Live
# installer and the two intentionally omitted x86 binaries; it does not weaken
# the shared session, application, logo or theme identity checks.
echo "=== (9b) finished-image identity gates ==="
grep -q 'ExecStartPre=-/usr/libexec/moos-greeter-gl-env' \
    /usr/lib/systemd/system/plasmalogin.service.d/20-moos-arm-greeter-gl.conf \
    || { echo "GATE FAIL: ARM plasmalogin must run moos-greeter-gl-env before the greeter"; exit 1; }
grep -q 'LIBGL_ALWAYS_SOFTWARE=1' \
    /usr/lib/systemd/user/plasma-login-kwin_wayland.service.d/10-moos-arm-greeter-gl.conf \
    /etc/environment.d/60-moos-arm-llvmpipe.conf \
    || { echo "GATE FAIL: ARM login greeter must force software GL for virtio proof VMs"; exit 1; }
grep -q 'GALLIUM_DRIVER=llvmpipe' \
    /usr/lib/systemd/user/plasma-login-kwin_wayland.service.d/10-moos-arm-greeter-gl.conf \
    /etc/environment.d/60-moos-arm-llvmpipe.conf \
    || { echo "GATE FAIL: ARM login greeter must select llvmpipe through Gallium"; exit 1; }
if grep -qE "printf 'MESA_LOADER_DRIVER_OVERRIDE=llvmpipe|^Environment=MESA_LOADER_DRIVER_OVERRIDE=llvmpipe|^MESA_LOADER_DRIVER_OVERRIDE=llvmpipe" \
    /usr/lib/systemd/user/plasma-login-kwin_wayland.service.d/10-moos-arm-greeter-gl.conf \
    /etc/environment.d/60-moos-arm-llvmpipe.conf; then
    echo "GATE FAIL: forcing Mesa's llvmpipe loader detaches KWin from the DRM scanout"
    exit 1
fi
grep -qx 'QT_QUICK_BACKEND=software' /etc/environment.d/60-moos-arm-llvmpipe.conf \
    || { echo "GATE FAIL: ARM sessions must use Qt Quick's bounded software renderer"; exit 1; }
grep -q 'ExecStart=/usr/libexec/moos-arm-greeter-kwin' \
    /usr/lib/systemd/user/plasma-login-kwin_wayland.service.d/10-moos-arm-greeter-gl.conf \
    || { echo "GATE FAIL: ARM display-aware greeter launcher is missing"; exit 1; }
grep -q '/sys/class/drm/card\*-\*/status' /usr/libexec/moos-arm-greeter-kwin \
    && grep -q '\[ -r "$dri_node" \].*\[ -w "$dri_node" \]' /usr/libexec/moos-arm-greeter-kwin \
    && grep -q 'KWIN_DRM_DEVICES="$dri_node"' /usr/libexec/moos-arm-greeter-kwin \
    && grep -q -- '--virtual --width 1920 --height 1080' /usr/libexec/moos-arm-greeter-kwin \
    || { echo "GATE FAIL: ARM greeter must distinguish UTM displays from a headless VPS"; exit 1; }
id -nG plasmalogin | grep -qw video \
    && id -nG plasmalogin | grep -qw render \
    || { echo "GATE FAIL: ARM login greeter cannot open the virtio DRM nodes"; exit 1; }
grep -qxF 'vgem' /etc/modules-load.d/moos-arm-vgem.conf \
    || { echo "GATE FAIL: ARM must load vgem for greeter/desktop GL"; exit 1; }
grep -q 'DefaultDeviceTimeoutSec=120' /etc/systemd/system.conf.d/moos-arm-device-timeout.conf \
    || { echo "GATE FAIL: ARM must extend device timeout for slow virt boot"; exit 1; }
grep -q 'Requires=moos-arm-block-coldplug.service' \
    /usr/lib/systemd/system/boot.mount.d/moos-arm-coldplug.conf \
    /usr/lib/systemd/system/boot-efi.mount.d/moos-arm-coldplug.conf \
    || { echo "GATE FAIL: ARM boot mounts must wait for block coldplug"; exit 1; }
command -v cosign >/dev/null 2>&1 \
    || { echo "GATE FAIL: cosign must ship for UTM net install"; exit 1; }
[ -x /usr/libexec/moos-utm-net-install ] \
    || { echo "GATE FAIL: moos-utm-net-install missing"; exit 1; }
[ -x /usr/libexec/moos-utm-installer-menu ] \
    || { echo "GATE FAIL: moos-utm-installer-menu missing"; exit 1; }
[ -r /usr/share/moos/release/arm-latest.json ] \
    || { echo "GATE FAIL: arm-latest.json missing"; exit 1; }
MOOS_IDENTITY_PROFILE=arm-cloud python3 /ctx/verify_identity.py
python3 /ctx/verify_arm_image.py
python3 /ctx/verify_no_foreign_identity.py

# -----------------------------------------------------------------------------
# (10) Clean up so `bootc container lint` passes
# -----------------------------------------------------------------------------
dnf5 clean all
rm -rf /var/cache/* /var/log/* /tmp/* || true
# bootc requires /var to be empty of anything the image is not entitled to own.
find /var -mindepth 1 -maxdepth 1 ! -name 'lib' ! -name 'tmp' -exec rm -rf {} + 2>/dev/null || true

echo "=== MoOS ARM build complete: ${MOOS_EDITION} (aarch64) ==="
