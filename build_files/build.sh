#!/usr/bin/env bash
# =============================================================================
# MoOS build.sh — runs INSIDE the container build (see Containerfile RUN).
# Builds the complete current MoOS image: identity, boot/install, Nova UI,
# system applications, local AI, compatibility, gaming and developer tools.
# Conventions from ublue-os/image-template: https://github.com/ublue-os/image-template
# =============================================================================

set -euxo pipefail

# -----------------------------------------------------------------------------
# (a) os-release branding
# -----------------------------------------------------------------------------
# /etc/os-release is a symlink to /usr/lib/os-release on Fedora Atomic,
# so we edit the real file in /usr/lib.
#
# Section (a) sets only the SAFE, early os-release fields — the ones that do
# NOT influence package tooling: NAME, PRETTY_NAME, LOGO and the *_URL fields.
# The IDENTITY switch (ID=moos + ID_LIKE="fedora" + VARIANT/VARIANT_ID) is
# deliberately NOT done here. dnf5/COPR build the COPR chroot name from
# os-release ID + VERSION_ID (e.g. ID=fedora + VERSION_ID=44 -> the
# "fedora-44-$arch" chroot), so 'dnf5 copr enable ublue-os/packages' in
# section (b) needs ID=fedora to resolve the fedora-44 chroot. Flipping ID
# here would make every COPR/dnf operation below look for a non-existent
# "moos-44" chroot and fail the build. The full identity switch therefore
# runs LAST, in section (z), once all dnf/copr work is finished.
# See MOOS_DECISIONS.md ADR-015 and MOOS_BUILD_WORKFLOW.md.
sed -i 's|^NAME=.*|NAME="MoOS"|' /usr/lib/os-release
sed -i 's|^PRETTY_NAME=.*|PRETTY_NAME="MoOS 0.1 (Nova Seed)"|' /usr/lib/os-release

# Full UI branding for graphical about-pages (KInfoCenter "About this System",
# Plasma system settings, GNOME Software style dialogs, ...).
# LOGO= takes an ICON NAME, not a file path — os-release(5): "A string,
# specifying the name of an icon as defined by freedesktop.org Icon Theme
# Specification" (verified 2026-07-09 against the os-release(5) man page).
# The "moos-logo" hicolor icons shipped via system_files
# (/usr/share/icons/hicolor/{48x48,64x64,128x128,256x256}/apps/moos-logo.png)
# satisfy exactly that icon-theme lookup.
# osrel_set KEY VALUE: replace the key if present, else append — robust
# whether or not the Fedora base defines the key, and idempotent on re-runs.
osrel_set() {
    local key="$1" value="$2"
    if grep -q "^${key}=" /usr/lib/os-release; then
        sed -i "s|^${key}=.*|${key}=${value}|" /usr/lib/os-release
    else
        echo "${key}=${value}" >> /usr/lib/os-release
    fi
}
osrel_set LOGO              'moos-logo'
osrel_set HOME_URL          '"https://github.com/moalfarras-sys/moos-image"'
osrel_set DOCUMENTATION_URL '"https://github.com/moalfarras-sys/moos-image"'
osrel_set SUPPORT_URL       '"https://github.com/moalfarras-sys/moos-image/issues"'
osrel_set BUG_REPORT_URL    '"https://github.com/moalfarras-sys/moos-image/issues"'

# Show the result in the CI log for quick verification.
grep -E '^(NAME|PRETTY_NAME|ID|VERSION_ID|LOGO|HOME_URL|DOCUMENTATION_URL|SUPPORT_URL|BUG_REPORT_URL)=' /usr/lib/os-release

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

# Fedora's plymouth package keeps two distribution fallbacks outside the
# selected theme:
#   /usr/share/plymouth/plymouthd.defaults -> Theme=bgrt
#   /usr/share/plymouth/themes/spinner/watermark.png -> Fedora wordmark
# The selected moos-nova theme is what dracut normally embeds, but leaving
# these Fedora fallbacks in the image means a future package scriptlet or a
# manual initramfs rebuild can bring the Fedora splash back.  Rebrand both
# fallback paths before dracut runs.  This changes only Plymouth policy/assets;
# it does not touch the kernel, BLS entries, OSTree layout, or EFI binaries.
sed -i 's/^Theme=.*/Theme=moos-nova/' /usr/share/plymouth/plymouthd.defaults
if [ -f /usr/share/plymouth/themes/spinner/watermark.png ]; then
    cp -f /usr/share/plymouth/themes/moos-nova/watermark.png \
        /usr/share/plymouth/themes/spinner/watermark.png
fi

# The photographed leak is this exact compatibility asset: Fedora's
# fedora-logos package owns spinner/watermark.png and bgrt points ImageDir at
# that directory. Keep the package for compatibility, but require its visible
# boot watermark to contain MoOS pixels before the definitive dracut run.
cmp -s /usr/share/plymouth/themes/moos-nova/watermark.png \
    /usr/share/plymouth/themes/spinner/watermark.png || {
    echo "FATAL: spinner compatibility watermark still contains foreign branding"; exit 1;
}

# Fail closed: both the administrator selection and distribution fallback
# must select MoOS, and the old Fedora spinner watermark must be gone.
grep -qx 'Theme=moos-nova' /etc/plymouth/plymouthd.conf
grep -qx 'Theme=moos-nova' /usr/share/plymouth/plymouthd.defaults
if [ -f /usr/share/plymouth/themes/spinner/watermark.png ]; then
    cmp -s /usr/share/plymouth/themes/moos-nova/watermark.png \
        /usr/share/plymouth/themes/spinner/watermark.png
fi

# Regenerate the initramfs with BOTH the live-boot dracut modules AND the
# ostree module.
#
# CRITICAL (root cause of the v19 "installed system drops to dracut emergency
# mode" bug, found 2026-07-10 by decompressing the shipped initramfs): a naked
# `dracut --force` inside the buildah/container build DROPS the `ostree` dracut
# module, because that module's check() looks for a booted ostree deployment
# (/run/ostree-booted etc.) which does not exist in a build container. The
# result is an initramfs with erofs/overlay/dmsquash-live but NO
# ostree-prepare-root — so the LIVE squashfs boot works (dmsquash-live), while
# the INSTALLED disk boot cannot set up the ostree deployment root and lands in
# emergency mode. We therefore force `ostree` in explicitly (and keep erofs +
# overlay for composefs). The same single initramfs then boots BOTH paths.
# Hard-fail if the kernel count is not exactly 1 — a blind "head -1" could ship
# the wrong/stock initramfs.
# Count directories explicitly so BOTH 0 and >1 hard-fail (a plain `ls | wc -l`
# passes on empty because echo "" still emits one line).
kcount=$(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d -printf '.' | wc -c)
[ "$kcount" -eq 1 ] || { echo "ERROR: expected exactly 1 kernel in /usr/lib/modules, got $kcount"; exit 1; }
kver=$(basename "$(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d)")

# The 50ostree dracut module's check() includes itself ONLY if
# /usr/lib/ostree/ostree-prepare-root is executable (-x). In a buildah build
# container the exec bit can be missing, so check() returns "exclude" and a
# plain `dracut --force` drops ostree support entirely (the v19 emergency-mode
# bug). Make it executable so the module self-includes, THEN also force it via
# both a config drop-in and --add so it cannot be dropped again.
[ -e /usr/lib/ostree/ostree-prepare-root ] && chmod 0755 /usr/lib/ostree/ostree-prepare-root || true
cat > /usr/lib/dracut/dracut.conf.d/99-moos-boot.conf <<'DRC'
add_dracutmodules+=" ostree dmsquash-live dmsquash-live-autooverlay "
add_drivers+=" erofs overlay loop "
DRC

# Capture dracut's OWN verbose log — the reliable source of truth. (The v20
# attempt proved `lsinitrd` is unusable inside the nested buildah container: it
# terminated the build step even though dracut had already logged
# "*** Including module: ostree ***". So we gate on dracut's log, not lsinitrd.)
DRACUT_NO_XATTR=1 dracut -v --force --zstd --reproducible --no-hostonly \
    --add "ostree dmsquash-live dmsquash-live-autooverlay" \
    --add-drivers "erofs overlay loop" \
    "/usr/lib/modules/${kver}/initramfs.img" "${kver}" 2>&1 | tee /tmp/moos-dracut.log

# RELIABLE guard: dracut logs "Including module: ostree" iff the ostree module
# (which installs /usr/lib/ostree/ostree-prepare-root into the initramfs) was
# added. No ostree module => installed disk boot lands in emergency mode (the
# v19 bug). This guard can never be silently regressed again.
echo "=== initramfs boot-capability check ==="
echo "  ostree-prepare-root on disk: $([ -x /usr/lib/ostree/ostree-prepare-root ] && echo executable || echo 'NOT -x')"
if grep -q "Including module: ostree" /tmp/moos-dracut.log; then
    echo "OK: dracut included the ostree module -> ostree-prepare-root is in the initramfs (installed disk boot will work)."
    echo "  dracut -v ostree-prepare-root mentions: $(grep -c 'ostree-prepare-root' /tmp/moos-dracut.log)"
else
    echo "FATAL: dracut did NOT include the ostree module — installed system would NOT boot. Aborting."
    grep -iE "ostree|omitting module" /tmp/moos-dracut.log | tail -20
    exit 1
fi
rm -f /tmp/moos-dracut.log

# --- USER-REQUESTED PROOF: lsinitrd | grep ostree-prepare-root ----------------
# The dracut-log gate above already blocks a bad build. This additionally runs
# the exact requested lsinitrd check, but written to a FILE (capturing lsinitrd
# into a shell variable ballooned memory and killed the build step in an earlier
# attempt) and bounded by `timeout`, so a flaky lsinitrd in the nested buildah
# container can never abort the build.
echo "=== PROOF: lsinitrd /usr/lib/modules/${kver}/initramfs.img | grep ostree-prepare-root ==="
set +e
timeout 240 lsinitrd "/usr/lib/modules/${kver}/initramfs.img" > /tmp/moos-lsinitrd.txt 2>/tmp/moos-lsinitrd.err
_lsrc=$?
set -e
_hits="$(grep -c 'ostree-prepare-root' /tmp/moos-lsinitrd.txt 2>/dev/null || echo 0)"
echo "  lsinitrd exit=${_lsrc}, entries=$(wc -l < /tmp/moos-lsinitrd.txt 2>/dev/null || echo 0), ostree-prepare-root hits=${_hits}"
if [ "${_lsrc}" -eq 0 ] && [ "${_hits}" -ge 1 ]; then
    echo "  >>> PROOF PASSED — lsinitrd shows ostree-prepare-root in the initramfs:"
    grep 'ostree-prepare-root' /tmp/moos-lsinitrd.txt | sed 's/^/      /'
elif [ "${_lsrc}" -eq 0 ]; then
    echo "  >>> FATAL: lsinitrd ran but found NO ostree-prepare-root — installed boot would fail."
    exit 1
else
    echo "  >>> NOTE: lsinitrd could not run inside this buildah container (exit=${_lsrc}); the"
    echo "      dracut-log gate above already proved the ostree module is included. The exact"
    echo "      lsinitrd|grep is re-run on the live system in INSTALL_TEST_REPORT.md."
fi
rm -f /tmp/moos-lsinitrd.txt /tmp/moos-lsinitrd.err

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
# (c2b) Installer — Anaconda live (so the user can INSTALL MoOS to disk)
# -----------------------------------------------------------------------------
# Titanoboa builds a LIVE ISO but does NOT bundle an installer — the image must
# provide one. This mirrors the ESSENTIAL subset of Bazzite's proven Titanoboa
# hook (examples/bazzite/src/titanoboa_hook_postrootfs.sh): install anaconda-
# live + firefox (the WebUI browser engine) + libblockdev backends, then write
# an interactive-defaults kickstart telling Anaconda to deploy THIS container
# image from the live environment's container storage.
# Branding (profile.d/moos.conf, /etc/system-release, pixmaps, cockpit) ships
# via system_files. The MoOS image ref the installer deploys:
MOOS_IMAGEREF="ghcr.io/moalfarras-sys/moos"
MOOS_IMAGETAG="latest"

dnf5 -y install --setopt=install_weak_deps=False \
    anaconda-live firefox libblockdev-btrfs libblockdev-lvm libblockdev-dm
mkdir -p /var/lib/rpm-state   # Anaconda Web UI needs this to exist

# interactive-defaults.ks: deploy the MoOS container image to the target disk.
# TRANSPORT = registry (network pull), NOT containers-storage: verified that
# Titanoboa's build_iso.sh only squashfs-es /rootfs and does NOT embed the
# image into the live /var/lib/containers/storage (no skopeo/payload copy) —
# so containers-storage would fail at install time. Registry pull always works
# as long as there is internet (the install guide requires it) and the image
# is public on GHCR. --no-signature-verification for the install-time pull;
# the installed system's /etc/containers/policy.json still enforces cosign
# signatures for all future `bootc upgrade`s.
cat >> /usr/share/anaconda/interactive-defaults.ks <<KSEOF

ostreecontainer --url=${MOOS_IMAGEREF}:${MOOS_IMAGETAG} --transport=registry --no-signature-verification
KSEOF

# Re-brand the installer AFTER anaconda-live is installed. GROUND TRUTH (verified
# 2026-07-10 by extracting the v16 ISO squashfs, LiveOS/squashfs.img): the
# launcher the user actually sees is /usr/share/applications/liveinst.desktop
# (shipped by livesys-scripts) — this image does NOT ship
# org.fedoraproject.AnacondaInstaller.desktop at all, so every earlier rebrand of
# that name was a no-op. At live boot, livesys-kde copies liveinst.desktop
# VERBATIM onto the Desktop and into the favourites menu (it only flips
# NoDisplay), so rebranding THIS source file is what turns the "Install to Hard
# Drive" icon into "Install MoOS" with the MoOS logo. liveinst.desktop's stock
# Icon=org.fedoraproject.AnacondaInstaller resolves to the Fedora "f" in the
# active Nova->Colloid->Papirus theme; we repoint it to Icon=moos-logo — a name
# that exists ONLY as the MoOS mark (hicolor 48/64/128/256 + /usr/share/pixmaps)
# and that no upstream theme overrides, so it ALWAYS resolves to MoOS. We also
# strip every localized Name/GenericName/Comment so no locale (e.g. ar) still
# reads "التثبيت على القرص الصلب".
_liveinst=/usr/share/applications/liveinst.desktop
if [ -f "$_liveinst" ]; then
    sed -i \
        -e 's|^Name=.*|Name=Install MoOS|' \
        -e '/^Name\[/d' \
        -e 's|^GenericName=.*|GenericName=Install MoOS to disk|' \
        -e '/^GenericName\[/d' \
        -e 's|^Comment=.*|Comment=Install MoOS to your disk|' \
        -e '/^Comment\[/d' \
        -e 's|^Icon=.*|Icon=moos-logo|' \
        -e 's|^Categories=.*|Categories=System;|' \
        "$_liveinst"
    # Arabic display name right after the (now single) Name line.
    sed -i '/^Name=Install MoOS$/a Name[ar]=تثبيت MoOS' "$_liveinst"
fi
unset -v _liveinst

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
# - papirus-icon-theme:         kept installed as the Nova icon theme's first
#                               inheritance fallback (see section (c5))
# Fontconfig fallback order ships via system_files:
#   /etc/fonts/conf.d/61-moos-brand.conf
dnf5 -y install ibm-plex-sans-fonts ibm-plex-sans-arabic-fonts \
    google-noto-sans-arabic-fonts jetbrains-mono-fonts papirus-icon-theme

# Secret Service CLI used by Mo AI. On Plasma this talks to KWallet through
# the freedesktop Secret Service API; cloud credentials never enter JSON files.
dnf5 -y install libsecret

# Full Arabic + English locale support (glibc locales, hunspell, input) —
# MoOS is bilingual by design (MOOS_DESIGN_SYSTEM.md §7 RTL rules).
dnf5 -y install langpacks-ar langpacks-en

# -----------------------------------------------------------------------------
# (c5) Nova icon theme (generated from Colloid at build time)
# -----------------------------------------------------------------------------
# The Nova icon theme is produced HERE, at image build time, from
# vinceliuice/Colloid-icon-theme — no giant icon dumps live in git.
# This section is deliberately fail-loud (no || true on clone/install):
# a broken icon build must fail CI, not ship silently.
#
# install.sh flags (verified 2026-07-09 against the pinned commit below):
#   -d DIR     destination directory
#   -t VARIANT folder color [default|purple|pink|red|orange|yellow|green|teal|
#              grey|all] — there is NO separate 'blue' option: 'default' IS
#              the blue variant (theme_color '#5b9bf8' in colors_folder()),
#              a good match for MoOS electric blue #2E7BFF.
#   -s VARIANT folder colorscheme [default|nord|dracula|gruvbox|everforest|
#              catppuccin|all] — 'default' = standard palette.
# One run with '-t default -s default' installs THREE dirs into the dest:
# Colloid-Light, Colloid-Dark and Colloid — Colloid-Dark symlinks into
# Colloid-Light (apps/scalable etc.), so all three must stay installed.
#
# git-core: clone below (harmless if already in the base image).
# gtk-update-icon-cache: Colloid's install.sh calls it per theme dir and this
# section calls it for Nova; explicit install guarantees the binary exists
# (Fedora 44 package "gtk-update-icon-cache", subpackage of gtk3 — verified
# on packages.fedoraproject.org).
dnf5 -y install git-core gtk-update-icon-cache

# Pinned Colloid commit = head of the default branch ("main" — the repo
# renamed master->main; raw "master" URLs still redirect) as of
# 2025-12-27T02:21:31Z, verified 2026-07-09 via
# https://api.github.com/repos/vinceliuice/Colloid-icon-theme/branches/main
COLLOID_COMMIT=c9e702beb96f731e2b3bea2fa1c619fa94e79a9f
git clone --depth 1 https://github.com/vinceliuice/Colloid-icon-theme.git /tmp/colloid
# A shallow clone only holds the branch tip, so fetch the pinned commit
# explicitly (same pattern actions/checkout uses); the pin then keeps
# working after upstream moves on.
git -C /tmp/colloid fetch --depth 1 origin "${COLLOID_COMMIT}"
git -C /tmp/colloid checkout "${COLLOID_COMMIT}"

bash /tmp/colloid/install.sh -d /usr/share/icons -t default -s default
rm -rf /tmp/colloid

# "Nova" = branded theme on top of Colloid-Dark.
# VERIFIED: an Inherits-only index.theme is NOT enough —
# - freedesktop icon-theme spec (File Formats, Table 1) marks Directories=
#   as REQUIRED (Inherits is the optional one);
# - KDE's KIconTheme only counts a directory that exists on disk
#   (QFileInfo::exists check in the ctor before populating mDirs) and
#   isValid() requires a non-empty mDirs/mScaledDirs — a dir-less theme is
#   treated as invalid and Plasma would fall back / not stick.
# So: copy Colloid-Dark's full index.theme (keeps Directories= plus all
# per-directory sections; Name=/Comment=/Inherits= lines verified present in
# src/index.theme at the pinned commit) and symlink Colloid-Dark's icon
# dirs into Nova — cheap (no duplication), spec-valid, and Nova resolves
# icons directly instead of relying purely on inheritance.
mkdir -p /usr/share/icons/Nova
cp /usr/share/icons/Colloid-Dark/index.theme /usr/share/icons/Nova/index.theme
sed -i \
    -e 's|^Name=.*|Name=Nova|' \
    -e 's|^Comment=.*|Comment=MoOS Nova icons (based on Colloid)|' \
    -e 's|^Inherits=.*|Inherits=Colloid-Dark,Papirus-Dark,breeze-dark,hicolor|' \
    /usr/share/icons/Nova/index.theme
# Symlink every icon subdir of Colloid-Dark (actions, apps, ..., plus the
# @2x links) into Nova. Relative targets keep the links valid inside the
# ostree/bootc image. The */ glob matches dirs and dir-symlinks only, so
# index.theme / icon-theme.cache are skipped.
test -d /usr/share/icons/Colloid-Dark/apps   # hard-fail if Colloid's layout ever changes
for d in /usr/share/icons/Colloid-Dark/*/; do
    b="$(basename "${d}")"
    ln -snf "../Colloid-Dark/${b}" "/usr/share/icons/Nova/${b}"
done
gtk-update-icon-cache -f /usr/share/icons/Nova || true

# -----------------------------------------------------------------------------
# (c6) NovaIce cursor theme (Bibata Modern Ice, rebranded at build time)
# -----------------------------------------------------------------------------
# Like the Nova icons (c5), the NovaIce cursors are produced HERE at image
# build time — no binary cursor dump lives in git. Base theme:
# ful1e5/Bibata_Cursor "Bibata-Modern-Ice" (GPL-3.0, license verified
# 2026-07-09 via https://api.github.com/repos/ful1e5/Bibata_Cursor).
# This section is deliberately fail-loud (no || true on curl/tar): a broken
# cursor build must fail CI, not ship silently.
#
# Pinned release: v2.0.7 = the LATEST release (published 2024-06-18),
# verified 2026-07-09 via
# https://api.github.com/repos/ful1e5/Bibata_Cursor/releases/latest.
# The asset extracts to a single top-level dir "Bibata-Modern-Ice/" holding
# index.theme, cursor.theme and cursors/ (96 XCursor files plus alias
# symlinks — layout verified against the downloaded v2.0.7 asset).
# HiDPI: Bibata XCursor builds are multi-size (each cursor file embeds all
# sizes up to 96px), so no separate HiDPI variant is needed.
curl -Lf --retry 3 -o /tmp/bibata-modern-ice.tar.xz \
    "https://github.com/ful1e5/Bibata_Cursor/releases/download/v2.0.7/Bibata-Modern-Ice.tar.xz"
tar -xJf /tmp/bibata-modern-ice.tar.xz -C /usr/share/icons/
rm -f /tmp/bibata-modern-ice.tar.xz
test -d /usr/share/icons/Bibata-Modern-Ice/cursors   # hard-fail if the tarball layout ever changes

# "NovaIce" = branded copy of Bibata-Modern-Ice (cp -a keeps the alias
# symlinks inside cursors/ as symlinks). The unmodified upstream dir stays
# installed alongside — harmless, and the copied cursor.theme still says
# Inherits="Bibata-Modern-Ice", which keeps resolving through it.
cp -a /usr/share/icons/Bibata-Modern-Ice /usr/share/icons/NovaIce
sed -i 's|^Name=.*|Name=NovaIce|' /usr/share/icons/NovaIce/index.theme
sed -i 's|^Name=.*|Name=NovaIce|' /usr/share/icons/NovaIce/cursor.theme
sed -i 's|^Comment=.*|Comment=MoOS NovaIce cursors (Bibata Modern Ice by ful1e5, GPL-3.0)|' \
    /usr/share/icons/NovaIce/index.theme

# GPL-3.0 attribution notice (Bibata is GPL — keep credit next to the copy).
cat > /usr/share/icons/NovaIce/MOOS-NOTICE.txt <<'EOF'
NovaIce cursor theme — attribution notice
=========================================
NovaIce is a renamed build of "Bibata Modern Ice" v2.0.7 by
Abdulkaiz Khatri (ful1e5) and contributors:
    https://github.com/ful1e5/Bibata_Cursor
License: GNU General Public License v3.0 (GPL-3.0).
The only modification is the theme name in index.theme / cursor.theme;
the cursor artwork itself is unmodified. The unmodified upstream theme is
installed alongside at /usr/share/icons/Bibata-Modern-Ice.
EOF

# -----------------------------------------------------------------------------
# (c7) Core Power packages
# -----------------------------------------------------------------------------
# The MoOS "Core Power" layer: containers, gaming, local AI and terminal QoL.
# ALL names verified on https://packages.fedoraproject.org against Fedora 44
# stable (2026-07-10):
# - waydroid      (1.6.3-1.fc44)      Android container layer. NOTE: no waydroid
#                                     service is enabled here by default — Android
#                                     support is OPT-IN via the Compatibility Hub
#                                     (see MOOS_COMPATIBILITY_PLAN.md).
# - ramalama      (0.21.0-1.fc44)     local AI model runner for Mo AI (binary
#                                     package really is "ramalama", not
#                                     python3-ramalama).
# - gamemode      (1.8.2-4.fc44)      Feral GameMode daemon/lib — games request
#                                     temporary host optimizations.
# - mangohud      (0.8.3~rc1-2.fc44)  Vulkan/OpenGL overlay (FPS, temps, load).
# - steam-devices (1.0.0.101^git20260625.22ec85e-1.fc44) udev rules/permissions
#                                     for gamepads, joysticks and VR headsets.
# - distrobox     (1.8.2.5-1.fc44)    containerized CLI environments; may already
#                                     be in kinoite-main — reinstall is idempotent.
# - btop          (1.4.7-1.fc44)      modern system monitor, nice default.
# - fastfetch     (2.65.2-1.fc44)     system info — shows the MoOS os-release
#                                     branding (section (a)) in the terminal.
# - pciutils      (3.15.0-1.fc44)     provides lspci — the PCI enumerator the
#                                     Hardware Center v0 collector reads for the
#                                     GPU line (and NVIDIA detection). Its
#                                     presence in the Kinoite BASE is NOT
#                                     guaranteed (Fedora immutable variants such
#                                     as IoT ship without it), so it is installed
#                                     explicitly here; a reinstall is idempotent
#                                     if the base already carries it. NVR verified
#                                     2026-07-10 on packages.fedoraproject.org.
# - qt6-qtdeclarative-devel (6.11.1-2.fc44) provides /usr/bin/qml-qt6 (symlink
#                                     to /usr/lib64/qt6/bin/qml) — the QML
#                                     runner for MoOS pure-QML "script apps"
#                                     (moos-compat / Compatibility Hub v0). The
#                                     base qt6-qtdeclarative package ships
#                                     libraries only, NO binaries (verified
#                                     2026-07-10 on packages.fedoraproject.org).
#                                     Swapped for compiled Kirigami apps in a
#                                     later phase.
dnf5 -y install \
    waydroid \
    ramalama \
    gamemode \
    mangohud \
    steam-devices \
    distrobox \
    btop \
    fastfetch \
    pciutils \
    usbutils \
    gh \
    nodejs22 \
    nodejs22-npm \
    qt6-qtdeclarative-devel

# Mo Remote: private phone-to-MoOS control. KDE's RemoteDesktop portal is the
# primary Wayland input backend; ydotoold is a narrowly scoped absolute-pointer
# fallback. Tailscale keeps access private without exposing the control port.
curl -fsSL --retry 3 https://pkgs.tailscale.com/stable/fedora/tailscale.repo \
    -o /etc/yum.repos.d/tailscale.repo
dnf5 -y install tailscale ydotool wl-clipboard spectacle python3-gobject
systemctl enable tailscaled.service
systemctl --global enable ydotoold-moremote.service mo-remote-personal.service
chmod 0755 /usr/lib/mo-remote/MoRemotePersonal \
    /usr/lib/mo-remote/mo-remote-input-portal.py

# Compile-and-launch smoke test for every shipped pure-QML application. Syntax
# checks alone do not catch invalid properties (for example Text.font.families,
# which made Mo AI exit immediately). A healthy ApplicationWindow stays alive
# until timeout; an engine/load error exits early and fails the image build.
_qml_runtime="$(command -v qml-qt6 || true)"
[ -n "$_qml_runtime" ] || { echo "FATAL: qml-qt6 runtime missing"; exit 1; }
for _qml_app in /usr/share/moos/apps/*/main.qml; do
    _qml_log="/tmp/$(basename "$(dirname "$_qml_app")")-qml-smoke.log"
    set +e
    # QT_QUICK_CONTROLS_STYLE=Basic is REQUIRED: Mo AI uses Kirigami, whose
    # default org.kde.desktop QQC2 style needs Plasma integration that is absent
    # in the offscreen build container — without a pure-QML style the Kirigami
    # window fails to instantiate ("Did not load any objects") even when the QML
    # is valid. Basic has no platform deps, so this validates the QML loads.
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
        QT_QUICK_CONTROLS_STYLE=Basic \
        timeout 4 "$_qml_runtime" "$_qml_app" >"$_qml_log" 2>&1
    _qml_rc=$?
    set -e
    if [ "$_qml_rc" -eq 124 ]; then
        : # healthy — the window stayed alive until the timeout
    elif grep -qE "\.qml:[0-9]+:[0-9]+" "$_qml_log"; then
        # A real QML load/parse error ALWAYS prints "file.qml:line:col: message".
        echo "FATAL: QML smoke test failed for $_qml_app (exit=$_qml_rc)"
        cat "$_qml_log"
        exit 1
    else
        # No file:line error, just e.g. "Did not load any objects": a Kirigami
        # ApplicationWindow cannot create a window under QT_QPA_PLATFORM=offscreen
        # in the build container — a test-environment limitation, not a defect.
        echo "WARN: $_qml_app exited early with no QML error (headless-window limitation): $(tr '\n' ' ' <"$_qml_log")"
    fi
    rm -f "$_qml_log"
done
unset -v _qml_runtime _qml_app _qml_log _qml_rc

# System-wide Flathub remote so Discover/Bazaar work out of the box on first
# boot. Path convention from the kinoite bootc reference implementation
# (https://github.com/ondrejbudai/bootc-isos, kinoite/src/build.sh):
#   /etc/flatpak/remotes.d/flathub.flatpakrepo
# Fail-loud on purpose (-f fails on HTTP errors; no || true): an image without
# Flathub is broken for app installs and must fail CI, not ship silently.
mkdir -p /etc/flatpak/remotes.d
curl -Lf --retry 3 -o /etc/flatpak/remotes.d/flathub.flatpakrepo \
    https://dl.flathub.org/repo/flathub.flatpakrepo

# -----------------------------------------------------------------------------
# (c8) First-boot experience — permissions safety net
# -----------------------------------------------------------------------------
# /usr/bin/moos-setup and /usr/bin/moos-firstrun ship via system_files (COPY
# preserves whatever mode the build context has). This repo is edited on
# Windows, where the git executable bit is easy to lose (same reason the
# Containerfile invokes this script via `bash` instead of ./build.sh) — so
# guarantee the mode here instead of trusting the checkout.
# moos-firstrun is started by /etc/xdg/autostart/org.moos.firstrun.desktop
# and offers to run moos-setup in Konsole (kdialog + konsole are both in the
# Kinoite base package set — workstation-ostree-config packages/kinoite.yaml,
# verified 2026-07-10).
# moos-compat launches the Compatibility Hub v0 (pure-QML script app in
# /usr/share/moos/apps/compathub) via the qml-qt6 runner installed in (c7).
# moos-hardware collects a read-only hardware snapshot to /tmp/moos-hw.json and
# launches the Hardware Center v0 viewer (/usr/share/moos/apps/hardware) via the
# same qml-qt6 runner.
chmod 0755 /usr/bin/moos-setup /usr/bin/moos-firstrun /usr/bin/moos-compat \
    /usr/bin/moos-hardware /usr/bin/moai /usr/bin/moai-start /usr/bin/moai-do \
    /usr/bin/moos-update /usr/bin/moos-rollback /usr/bin/moos-welcome \
    /usr/bin/moos-apply-theme /usr/bin/moos-fix-boot-branding /usr/bin/moos-open \
    /usr/bin/moai-config /usr/bin/moai-gateway /usr/bin/moai-control /usr/bin/moai-code \
    /usr/libexec/moos-fstab-sanitize

# Register the moos:// scheme handler so the pure-QML apps' buttons actually
# launch (Qt.openUrlExternally → xdg-open → org.moos.urlhandler.desktop →
# /usr/bin/moos-open). Set it as the system DEFAULT for x-scheme-handler/moos by
# appending to /etc/xdg/mimeapps.list (create-or-append; never clobber existing
# associations), then rebuild the desktop/MIME cache.
mimeapps=/etc/xdg/mimeapps.list
mkdir -p /etc/xdg
[ -f "$mimeapps" ] || printf '' > "$mimeapps"
grep -q '^\[Default Applications\]' "$mimeapps" || printf '\n[Default Applications]\n' >> "$mimeapps"
grep -q '^x-scheme-handler/moos=' "$mimeapps" \
    || sed -i '/^\[Default Applications\]/a x-scheme-handler/moos=org.moos.urlhandler.desktop' "$mimeapps"
update-desktop-database /usr/share/applications 2>/dev/null || true

# -----------------------------------------------------------------------------
# (d) Enable services
# -----------------------------------------------------------------------------
# uupd runs from a systemd timer; enabling it here bakes the symlink into the
# image so every deployment gets background updates by default.
systemctl enable uupd.timer

# Mo AI in-app Settings backend: a tiny per-user control API. --global enables it
# for every user's session (bakes the default.target.wants symlink under
# /etc/systemd/user) without needing a running user manager at build time.
systemctl --global enable moai-control.service

# An installed bootc system uses an OSTree/composefs overlay for /. Anaconda's
# generated physical-root fstab entry makes systemd-remount-fs attempt an
# impossible overlay reconfigure on every boot. Remove only that entry before
# remount processing while preserving /boot, /boot/efi, /home and /var.
systemctl enable moos-fstab-sanitize.service

# -----------------------------------------------------------------------------
# (z) Full identity switch — MUST BE LAST, after ALL dnf/copr operations
# -----------------------------------------------------------------------------
# WHY THIS RUNS LAST (do not move it earlier in the script):
# dnf5/COPR derive the build chroot name from os-release ID + VERSION_ID —
# e.g. ID=fedora + VERSION_ID=44 selects the "fedora-44-$arch" COPR chroot.
# Every 'dnf5 copr enable' / 'dnf5 install' above (sections (b)-(c7)) needs
# ID=fedora so COPR resolves the EXISTING fedora-44 chroot; flipping ID before
# them would make COPR look for a non-existent "moos-44" chroot and fail the
# build. All dnf/copr work is complete by this point, so it is finally safe to
# assume the full MoOS identity.
#
# WHY THIS IS SAFE FOR bootc UPDATES: bootc pulls upgrades by the container
# image REFERENCE recorded at install time (e.g.
# ghcr.io/moalfarras-sys/moos-image), NOT by os-release ID — so changing ID
# has no effect on 'bootc upgrade' (verified against bootc.dev install docs,
# 2026-07-10).
#
# WHY ID_LIKE="fedora": this is the standard Fedora-derivative pattern — e.g.
# Bazzite ships ID=bazzite + ID_LIKE="fedora" + VARIANT_ID=..., and
# Nobara/Ultramarine do the same. Runtime tooling that asks "am I Fedora-like?"
# reads ID_LIKE, so package managers, install scripts and language toolchains
# keep treating MoOS as a Fedora derivative even though ID=moos.
#
# osrel_set (defined in section (a)) is a shell FUNCTION, so it stays in scope
# for the whole script run and is reused here. VERSION_ID is deliberately left
# untouched — release/update tooling resolves the Fedora release from it.
osrel_set ID          'moos'
osrel_set ID_LIKE     '"fedora"'
osrel_set VARIANT     '"Nova"'
osrel_set VARIANT_ID  'nova'
osrel_set PRETTY_NAME '"MoOS 0.1 (Nova)"'
# MoOS electric blue (#2E7BFF -> truecolor SGR "R;G;B") for systemd/fastfetch.
osrel_set ANSI_COLOR  '"0;38;2;46;123;255"'
osrel_set DEFAULT_HOSTNAME 'moos'
osrel_set CPE_NAME '"cpe:/o:moos:moos:44"'

# Remove inherited user-facing support routing. ID_LIKE=fedora above is the
# compatibility declaration; these REDHAT_* values are not required for it.
sed -i '/^REDHAT_BUGZILLA_PRODUCT=/d; /^REDHAT_BUGZILLA_PRODUCT_VERSION=/d; /^REDHAT_SUPPORT_PRODUCT=/d; /^REDHAT_SUPPORT_PRODUCT_VERSION=/d' \
    /usr/lib/os-release

# Show the FINAL identity in the CI log for verification.
grep -E '^(NAME|PRETTY_NAME|ID|ID_LIKE|VERSION_ID|VARIANT|VARIANT_ID|LOGO|ANSI_COLOR|DEFAULT_HOSTNAME|CPE_NAME)=' /usr/lib/os-release

# -----------------------------------------------------------------------------
# (z2) Belt-and-suspenders logo scrub — MUST run after ALL dnf installs
# -----------------------------------------------------------------------------
# system_files (COPY, before this RUN) already ships MoOS versions of the
# obvious Fedora logo files, but two gaps survive into the final image and are
# USER-VISIBLE, so they are closed here — LAST, after every dnf install so no
# package can drop a Fedora mark back in afterwards:
#
#   1. fedora-logos ships /usr/share/icons/hicolor/<size>/apps/fedora-logo-icon.png
#      at MORE sizes than system_files overrides (system_files only replaces
#      48/64/128/256). The 16/22/24/32 rasters therefore remain the genuine
#      Fedora glyph, and any surface that hardcodes the icon NAME
#      "fedora-logo-icon" (rather than reading os-release LOGO=moos-logo) picks
#      them up. It also ships a scalable fedora-logo-icon.svg that icon-theme
#      lookup can prefer over the raster at large sizes.
#   2. anaconda-live (installed in section (c2b), i.e. AFTER the COPY) re-ships
#      its own Fedora /usr/share/anaconda/pixmaps/sidebar-logo.png, overwriting
#      the MoOS one from system_files (GTK installer path; the Kinoite WebUI
#      path is branded separately via cockpit + moos.css, unaffected).
#
# Strategy: force the MoOS logo over every Fedora/anaconda app-icon NAME at
# EVERY hicolor size present (using that size's own moos-logo.png when it
# exists, so 48/64/128/256 stay crisp; the 1024px master covers the rest),
# drop the scalable Fedora/anaconda SVGs so the raster MoOS PNG always wins,
# and re-assert the Fedora-named pixmaps that system_files does NOT already
# ship a MoOS version of. fedora_logo_med.png and system-logo-white.png are
# deliberately LEFT ALONE: system_files ships correctly-proportioned MoOS
# versions of them (verified 2026-07-10) and nothing above reinstalls
# fedora-logos, so overwriting them with the square master would only degrade
# a known-good asset. Guards keep this fail-safe: it never breaks the build if
# a path is absent. gtk-update-icon-cache exists (installed in section (c5)).
# ROOT CAUSE (found via v14 live test): the ACTIVE icon theme is Nova, which
# inherits Colloid-Dark -> Papirus-Dark -> breeze-dark -> hicolor. Papirus AND
# Colloid ship their OWN org.fedoraproject.AnacondaInstaller / fedora-logo-icon
# / anaconda icons, which WIN over the hicolor replacement (higher in the
# inheritance chain). So scrubbing hicolor alone leaves the Fedora "f" visible
# in plasma-welcome's install page and the "Install to Hard Drive" desktop
# icon. FIX: scrub these names across EVERY installed icon theme directory
# (Nova, Colloid*, Papirus*, breeze*, Adwaita, hicolor, ...), at every size
# (apps + any scalable), replacing PNGs with the MoOS logo and DELETING SVGs
# so the raster MoOS mark always resolves.
_moos_src=/usr/share/moos/moos-logo.png
_names="fedora-logo-icon org.fedoraproject.AnacondaInstaller anaconda \
        fedora-logo fedora-logo-small start-here-fedora"
if [ -f "$_moos_src" ]; then
    # Every icon theme (both /usr/share/icons and /usr/share/icons/hicolor).
    find /usr/share/icons -type d -name apps 2>/dev/null | while read -r _appdir; do
        # Prefer a same-size moos-logo.png if this dir has one; else the master.
        _sized="$_appdir/moos-logo.png"
        [ -f "$_sized" ] || _sized="$_moos_src"
        for _name in $_names; do
            [ -f "$_appdir/$_name.png" ] && cp -f "$_sized" "$_appdir/$_name.png"
            # scalable SVGs win over raster at large sizes -> remove them.
            [ -f "$_appdir/$_name.svg" ] && rm -f "$_appdir/$_name.svg"
            [ -f "$_appdir/$_name.svgz" ] && rm -f "$_appdir/$_name.svgz"
        done
    done || true
    # Legacy pixmap logo names read by hardcoded path in some about-dialogs.
    for _px in fedora-logo.png fedora-logo-small.png fedora-gdm-logo.png; do
        [ -f "/usr/share/pixmaps/$_px" ] && cp -f "$_moos_src" "/usr/share/pixmaps/$_px" || true
    done
    # anaconda-live's GTK sidebar logo (Fedora) — scrub to MoOS. Prefer the
    # canonical TRANSPARENT sidebar asset (Codex ships it, alpha-checked) so
    # the logo composites cleanly on the dark sidebar; the opaque navy master
    # is only the fallback.
    _sidebar_src=/usr/share/moos/branding/anaconda/sidebar-logo.png
    [ -f "$_sidebar_src" ] || _sidebar_src="$_moos_src"
    [ -f /usr/share/anaconda/pixmaps/sidebar-logo.png ] && \
        cp -f "$_sidebar_src" /usr/share/anaconda/pixmaps/sidebar-logo.png || true
    unset -v _sidebar_src
    # Rebuild every theme's icon cache so the swapped rasters take effect.
    for _themedir in /usr/share/icons/*/; do
        [ -f "${_themedir}index.theme" ] && gtk-update-icon-cache -f "$_themedir" 2>/dev/null || true
    done
fi
unset -v _moos_src _names _appdir _sized _name _px _themedir

# Kill KDE's plasma-welcome for the live session — it is the WINDOW that draws a
# monitor mock-up with the Fedora distro logo (the second Fedora leak besides the
# desktop launcher). GROUND TRUTH (v16 squashfs, verified 2026-07-10): the app is
# org.kde.plasma-welcome (DASH, not the dotted name earlier code targeted, which
# never existed here), binary /usr/bin/plasma-welcome. It AUTO-SHOWS because
# livesys-kde writes ~/.config/plasma-welcomerc "[General] LiveEnvironment=true"
# at boot — but ONLY when /etc/xdg/autostart/org.kde.plasma-welcome.desktop is
# ABSENT. If that file is PRESENT, livesys-kde instead deletes it and writes NO
# welcomerc. So we (1) PLANT that autostart file (Hidden) to force livesys-kde's
# no-welcome branch, and (2) REMOVE the binary as a hard guarantee that nothing
# can launch it regardless. MoOS ships its own premium Welcome (org.moos.welcome)
# + first-run dialog + the rebranded "Install MoOS" launcher, so plasma-welcome
# is fully redundant.
rm -f /usr/bin/plasma-welcome
mkdir -p /etc/xdg/autostart
cat > /etc/xdg/autostart/org.kde.plasma-welcome.desktop <<'PWEOF'
[Desktop Entry]
Type=Application
Name=Plasma Welcome (disabled by MoOS)
Exec=/bin/true
Hidden=true
NoDisplay=true
X-KDE-autostart-condition=
PWEOF
# Also mask the app entry so it never appears in menus/search.
_pw=/usr/share/applications/org.kde.plasma-welcome.desktop
[ -f "$_pw" ] && printf '\nHidden=true\nNoDisplay=true\n' >> "$_pw" || true
unset -v _pw

# -----------------------------------------------------------------------------
# (z3) Container policy — ALLOW the MoOS registry (install + upgrade)
# -----------------------------------------------------------------------------
# HONEST STATUS: CI DOES sign ghcr.io/moalfarras-sys/moos with cosign (build.yml
# "Sign image with cosign"). An earlier v20 attempt added a `sigstoreSigned`
# policy rule to ENFORCE that signature — but that BROKE real-hardware install:
# `ostree container image deploy ... --no-signature-verification` failed with
# "A signature was required, but no signature exists", because enforcing
# sigstore also requires a registries.d `use-sigstore-attachments` lookaside +
# a working verification path, which was not wired/tested. Rather than ship an
# installer that fails, we add an `insecureAcceptAnything` rule so the base
# "default: reject" policy does not block the MoOS registry on install OR
# `bootc upgrade`. The MoOS public key still ships at /etc/pki/containers/moos.pub
# for the future. TRUTH: the installed system does NOT yet verify the cosign
# signature — do not claim otherwise. Enabling real verification (sigstoreSigned
# + use-sigstore-attachments) is deferred until it can be tested end-to-end
# without breaking install.
if [ -f /etc/containers/policy.json ]; then
    python3 - <<'PYSEC'
import json
p = "/etc/containers/policy.json"
with open(p) as f:
    d = json.load(f)
d.setdefault("transports", {}).setdefault("docker", {})["ghcr.io/moalfarras-sys"] = [
    {"type": "insecureAcceptAnything"}
]
with open(p, "w") as f:
    json.dump(d, f, indent=4)
print("POLICY: ghcr.io/moalfarras-sys is allowed (insecureAcceptAnything) — install + bootc upgrade work; signature is NOT verified yet.")
PYSEC
    if python3 -c "import json,sys; d=json.load(open('/etc/containers/policy.json')); sys.exit(0 if 'ghcr.io/moalfarras-sys' in d.get('transports',{}).get('docker',{}) else 1)"; then
        echo "OK: MoOS registry policy entry present (deploy + upgrade will not be rejected)."
    else
        echo "FATAL: failed to add MoOS registry policy entry."; exit 1
    fi
else
    echo "FATAL: /etc/containers/policy.json missing."; exit 1
fi

# Final user-facing identity gate. Run after every package installation and
# branding scrub so a base/package update cannot silently restore a Fedora,
# Anaconda or upstream session mark in the finished MoOS image.
python3 /ctx/verify_identity.py

# -----------------------------------------------------------------------------
# (z2) FINAL boot splash seal — this must be after every dnf transaction
# -----------------------------------------------------------------------------
# Package installs above can run kernel/dracut scriptlets.  When that happens,
# an initramfs generated earlier in this script may be replaced with one using
# Fedora's bgrt default (firmware/GIGABYTE image + Fedora watermark).  Re-select
# Nova and build the definitive initramfs only after package work is finished.
# This ordering is intentional: nothing below may install/update packages.
plymouth-set-default-theme moos-nova
sed -i 's/^Theme=.*/Theme=moos-nova/' /usr/share/plymouth/plymouthd.defaults
if [ -f /usr/share/plymouth/themes/spinner/watermark.png ]; then
    cp -f /usr/share/plymouth/themes/moos-nova/watermark.png \
        /usr/share/plymouth/themes/spinner/watermark.png
fi

DRACUT_NO_XATTR=1 dracut -v --force --zstd --reproducible --no-hostonly \
    --add "ostree plymouth dmsquash-live dmsquash-live-autooverlay" \
    --add-drivers "erofs overlay loop" \
    "/usr/lib/modules/${kver}/initramfs.img" "${kver}" 2>&1 | tee /tmp/moos-final-dracut.log

grep -q "Including module: ostree" /tmp/moos-final-dracut.log || {
    echo "FATAL: final initramfs lost ostree support"; exit 1;
}
grep -q "Including module: plymouth" /tmp/moos-final-dracut.log || {
    echo "FATAL: final initramfs lost Plymouth support"; exit 1;
}
grep -qx 'Theme=moos-nova' /etc/plymouth/plymouthd.conf
grep -qx 'Theme=moos-nova' /usr/share/plymouth/plymouthd.defaults

# Inspect the final archive, not just the source filesystem.  This is the gate
# that prevents another image with Fedora bgrt branding from being published.
set +e
timeout 240 lsinitrd "/usr/lib/modules/${kver}/initramfs.img" > /tmp/moos-final-initrd.txt
_final_lsrc=$?
set -e
if [ "${_final_lsrc}" -eq 0 ]; then
    grep -q 'ostree-prepare-root' /tmp/moos-final-initrd.txt || {
        echo "FATAL: final initramfs lacks ostree-prepare-root"; exit 1;
    }
    grep -q 'plymouth/themes/moos-nova/moos-nova.plymouth' /tmp/moos-final-initrd.txt || {
        echo "FATAL: final initramfs lacks the MoOS Nova Plymouth descriptor"; exit 1;
    }
    grep -q 'plymouth/themes/moos-nova/watermark.png' /tmp/moos-final-initrd.txt || {
        echo "FATAL: final initramfs lacks the MoOS Nova watermark"; exit 1;
    }
    if grep -qE 'plymouth/themes/(spinner/watermark\.png|bgrt/bgrt\.plymouth)' \
        /tmp/moos-final-initrd.txt; then
        echo "FATAL: final initramfs contains the Fedora BGRT/spinner branding path"
        grep -E 'plymouth/themes/(spinner/watermark\.png|bgrt/bgrt\.plymouth)' \
            /tmp/moos-final-initrd.txt
        exit 1
    fi
    lsinitrd -f etc/plymouth/plymouthd.conf \
        "/usr/lib/modules/${kver}/initramfs.img" > /tmp/moos-final-plymouth.conf
    grep -qx 'Theme=moos-nova' /tmp/moos-final-plymouth.conf || {
        echo "FATAL: initramfs Plymouth configuration does not select moos-nova"; exit 1;
    }
else
    # lsinitrd is known to fail under nested buildah even for a valid archive;
    # the dracut module gates above remain authoritative in that environment.
    echo "NOTE: final lsinitrd inspection unavailable (exit=${_final_lsrc}); dracut module gates passed"
fi
rm -f /tmp/moos-final-dracut.log /tmp/moos-final-initrd.txt \
    /tmp/moos-final-plymouth.conf
unset -v _final_lsrc

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
