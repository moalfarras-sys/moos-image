#!/usr/bin/env bash
# Prepare a DISPOSABLE Fedora development distro (WSL2, Toolbx, a container or a VM) so an agent
# that is NOT on the MoOS station can still run the repository gates and LOOK at first-party QML.
#
# It installs the same Qt 6 / KDE Frameworks QML stack the image uses, the MoOS fonts, and links
# the checkout's /usr/share/moos assets, icon themes and colour schemes into place, so a
# first-party app renders from SOURCE with the MoOS palette instead of Qt's defaults.
#
# This is a review aid. It is never run on a MoOS host (the host is immutable and needs none of
# it), it proves nothing about an image, and a frame it renders is "source harness" evidence in
# the sense of skills/moos-engineering/references/live-development.md — not a desktop review.
#
#   sudo scripts/review/setup-review-distro.sh            # idempotent
set -euo pipefail

if [ -e /run/ostree-booted ]; then
    echo "setup-review-distro: this is an image-based host; use a Toolbx/Distrobox container instead" >&2
    exit 2
fi
[ "$(id -u)" -eq 0 ] || { echo "setup-review-distro: run as root inside the development distro" >&2; exit 2; }
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

dnf -y -q install --skip-unavailable --setopt=install_weak_deps=False \
    python3 python3-pillow git-core rsync nodejs just ShellCheck \
    qt6-qtdeclarative qt6-qtdeclarative-devel qt6-qtbase-gui qt6-qtsvg qt6-qtshadertools \
    qt6-qt5compat qt6-qtmultimedia qt6-qtwayland qt6-qtimageformats \
    kf6-kirigami kf6-kirigami-addons kf6-qqc2-desktop-style kf6-kiconthemes kf6-breeze-icons \
    breeze-icon-theme plasma-integration kf6-kcolorscheme kf6-kconfig kf6-frameworkintegration \
    mesa-dri-drivers mesa-libGL mesa-libEGL xorg-x11-server-Xvfb dbus-daemon bubblewrap \
    ibm-plex-sans-fonts ibm-plex-sans-arabic-fonts jetbrains-mono-fonts google-noto-sans-arabic-fonts

# render-desktop.sh runs the REAL shell: plasmashell with kwin_x11 under Xvfb. Keep this set on
# ONE version with Qt (`dnf upgrade` first): applets built against another Qt refuse to load
# ("undefined symbol … Qt_6.x_PRIVATE_API") and the desktop comes up empty.
dnf -y -q install --skip-unavailable \
    plasma-workspace plasma-desktop libplasma kwin-x11 kactivitymanagerd plasma-nm plasma-pa \
    plasma-sdk kscreenlocker xwd ImageMagick glib2

# Assets the apps open by absolute path, and the themes Kirigami resolves by name. Symlinks into
# the checkout keep them current; pass a native-filesystem mirror as $1 when the checkout lives
# on a slow or mode-less mount (see mirror-gates.sh).
TREE="${1:-$ROOT}"
ln -sfn "$TREE/system_files/usr/share/moos" /usr/share/moos
for theme in "$TREE"/system_files/usr/share/icons/MoOSUI2*; do
    ln -sfn "$theme" "/usr/share/icons/$(basename "$theme")"
done
mkdir -p /usr/share/color-schemes /usr/share/icons/hicolor
for scheme in "$TREE"/system_files/usr/share/color-schemes/*.colors; do
    ln -sfn "$scheme" "/usr/share/color-schemes/$(basename "$scheme")"
done
rsync -a "$TREE/system_files/usr/share/icons/hicolor/" /usr/share/icons/hicolor/
# The image builds a base icon theme named MoOSUI2 from Colloid at build time; it is not in the
# tree. Here it is an alias, so `Inherits=MoOSUI2` resolves to real icons instead of placeholders.
if [ ! -e /usr/share/icons/MoOSUI2/index.theme ]; then
    mkdir -p /usr/share/icons/MoOSUI2
    printf '[Icon Theme]\nName=MoOSUI2 (review alias)\nInherits=breeze-dark,breeze,hicolor\nDirectories=\n' \
        > /usr/share/icons/MoOSUI2/index.theme
fi
fc-cache -f >/dev/null 2>&1 || true
echo "review distro ready: $(rpm -q qt6-qtdeclarative kf6-kirigami | tr '\n' ' ')"
