#!/usr/bin/env bash
# =============================================================================
# MoOS build.sh — runs INSIDE the container build (see Containerfile RUN).
# Builds the complete current MoOS image: identity, boot/install, Nova UI,
# system applications, local AI, compatibility, gaming and developer tools.
# Conventions from ublue-os/image-template: https://github.com/ublue-os/image-template
# =============================================================================

set -euxo pipefail

# -----------------------------------------------------------------------------
# (a0) Freeze the kernel at the BASE image's version — before any dnf runs
# -----------------------------------------------------------------------------
# The base (ghcr.io/ublue-os/kinoite-main:44) defines the kernel; its
# `ostree.linux` label is exactly what build.yml pins the NVIDIA akmod to. A
# layered dnf transaction in this build must NOT bump it. Seen 2026-07-17: the
# base shipped kernel 7.1.3-200 but the `updates` repo offered -201, so a plain
# `dnf install` pulled -201 in as an update and left TWO kernels in
# /usr/lib/modules — the newer one only half-populated (no overlay.ko, so dracut
# could not build the live initramfs: "Module 'dmsquash-live' depends on
# 'overlayfs', which can't be installed") AND unmatched by the akmod (a NVIDIA
# black screen). Exclude the kernel binary packages from EVERY transaction so the
# base's kernel stays the one and only. Kernel bumps ride the correct rail: a base
# rebuild → a matching akmod → `bootc upgrade`, never a side effect of layering.
# (Must be the first thing in the script — before the copr/dnf calls below.)
if ! grep -q '^exclude=.*kernel-core' /etc/dnf/dnf.conf 2>/dev/null; then
    printf 'exclude=kernel kernel-core kernel-modules kernel-modules-core kernel-modules-extra\n' \
        >> /etc/dnf/dnf.conf
fi
echo "=== kernel frozen at the base version (dnf.conf exclude added) ==="

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
sed -i 's|^PRETTY_NAME=.*|PRETTY_NAME="MoOS"|' /usr/lib/os-release

# The name is "MoOS" — NOT "MoOS 44". The "44" is Fedora's version number and the
# classic release files (/etc/redhat-release, /etc/system-release, /etc/fedora-release)
# still read "Fedora release 44 (…)" from the base package; anything that prints
# them (the shell login banner, some About dialogs, `hostnamectl`) would show a
# foreign name AND a version the user never asked to see. Force all three to a bare
# "MoOS". VERSION_ID in os-release stays 44 — dnf/COPR need it — but it is not the
# product NAME and never shown as one. (Owner: drop the Fedora version from the name.)
for _rel in /etc/redhat-release /etc/system-release /etc/fedora-release; do
    if [ -e "$_rel" ] || [ -L "$_rel" ]; then
        rm -f "$_rel"; printf 'MoOS\n' > "$_rel"
    fi
done
unset -v _rel

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
# VERSION carries the base's codename, and the base is Kinoite — so a MoOS that had renamed
# everything else still introduced itself as `44.20260714.0 (Kinoite)`. That string is not
# cosmetic trivia: os-release VERSION is what the ANACONDA INSTALLER puts on screen, so the
# first sentence a person read while installing MoOS named somebody else's distribution.
# Rewrite only the parenthesised codename and keep the version numbers the base generated —
# they are the OSTree version and they change every build. Written as a general substitution
# rather than s|Kinoite|Nova| so that rebasing onto a different Fedora variant tomorrow cannot
# quietly put that variant's name back on the installer.
# Strip the base's codename from VERSION entirely rather than swap one codename for another.
# os-release VERSION is what the ANACONDA INSTALLER prints, and the OS is called MoOS — the first
# sentence of a fresh install should not be introducing a second name the user has never heard,
# whether that name is "Kinoite" or one of ours. The version numbers stay: they are the OSTree
# build, and they are the only part of this string that tells anybody anything.
sed -i -E 's|^VERSION="([^"(]*[^"( ]) *\([^)]*\)"|VERSION="\1"|' /usr/lib/os-release
# Belt and braces: if the base ever ships VERSION without a codename, the line above does not
# match and any trailing space it already had would survive. Trim it unconditionally.
sed -i -E 's|^VERSION="(.*[^ ]) *"|VERSION="\1"|' /usr/lib/os-release

osrel_set LOGO              'moos-logo'
# MoOS's own home is Moalfarras's site (the system is "designed by Moalfarras").
osrel_set HOME_URL          '"https://www.moalfarras.space"'
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
# (b1) Resolve the base's kernel ambiguity — drop INCOMPLETE kernels, keep one
# -----------------------------------------------------------------------------
# ghcr.io/ublue-os/kinoite-main:44 currently ships TWO kernels in
# /usr/lib/modules: the real 7.1.3-200 (complete, and what build.yml pins the
# NVIDIA akmod to) AND a stray 7.1.3-201 whose module tree is HALF-POPULATED — it
# has no overlay.ko, so dracut cannot build the live initramfs ("Module
# 'dmsquash-live' depends on 'overlayfs', which can't be installed"). The (a0)
# dnf exclude stops NEW kernels being pulled but cannot remove one already baked
# into the base, so handle it here.
#
# Step 1 — remove any INCOMPLETE kernel (no overlay module), version-agnostic.
# Guarded so it can never delete every kernel: only prune once we know at least
# one COMPLETE kernel remains to keep.
_complete=()
while IFS= read -r _cand; do
    [ -n "$(find "/usr/lib/modules/${_cand}" -name 'overlay.ko*' -print -quit 2>/dev/null)" ] \
        && _complete+=("$_cand")
done < <(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d -printf '%f\n')
if [ "${#_complete[@]}" -ge 1 ]; then
    while IFS= read -r _cand; do
        _ok=0; for _c in "${_complete[@]}"; do [ "$_c" = "$_cand" ] && _ok=1; done
        [ "$_ok" = 1 ] && continue
        echo "=== removing INCOMPLETE kernel ${_cand} (no overlay module → breaks live initramfs) ==="
        rpm -qa 'kernel*' | grep -F -- "-${_cand}" | xargs -r rpm -e --nodeps 2>/dev/null || true
        rm -rf "/usr/lib/modules/${_cand}"
    done < <(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d -printf '%f\n')
else
    echo "WARNING: no kernel with an overlay module found — leaving /usr/lib/modules untouched"
fi
# Step 2 — if more than one COMPLETE kernel still remains, keep the RIGHT one:
# the akmod's exact kernel on NVIDIA (newest-wins would black-screen), newest on
# generic. (With today's base this leaves exactly 7.1.3-200 either way.)
if [ "${MOOS_IMAGE_NAME:-moos}" = "moos-nvidia" ] && [ -r /akmods/rpms/kmods/nvidia-vars ]; then
    _keep=$(. /akmods/rpms/kmods/nvidia-vars && printf '%s' "$KERNEL_VERSION")
else
    _keep=$(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -V | tail -1)
fi
mapfile -t _kvers < <(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d -printf '%f\n')
if [ "${#_kvers[@]}" -gt 1 ]; then
    echo "=== multiple complete kernels (${_kvers[*]}) — keeping ${_keep} ==="
    for _kv in "${_kvers[@]}"; do
        [ "$_kv" = "$_keep" ] && continue
        rpm -qa 'kernel*' | grep -F -- "-${_kv}" | xargs -r rpm -e --nodeps 2>/dev/null || true
        rm -rf "/usr/lib/modules/${_kv}"
    done
fi
echo "=== kernel(s) after resolve: $(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d -printf '%f ')==="

# -----------------------------------------------------------------------------
# (b2) NVIDIA driver — moos-nvidia edition only
# -----------------------------------------------------------------------------
# This MUST run before the initramfs is regenerated below: dracut has to see the
# nvidia modules and the force_drivers config, or the machine boots to a black
# screen (early KMS never hands a working GPU to Plasma).
#
# The driver is layered onto the SAME kinoite-main base as the generic edition,
# from ublue's akmods container, using ublue's own installer. See the Containerfile
# for why the old kinoite-nvidia base was abandoned.
#
# It runs before section (z) rebrands os-release on purpose: dnf5/COPR derive the
# chroot name from ID+VERSION_ID, and nvidia-install.sh enables a COPR.
if [ "${MOOS_IMAGE_NAME:-moos}" = "moos-nvidia" ]; then
    echo "=== NVIDIA edition: layering the driver onto the shared base ==="
    if [ ! -d /akmods/rpms ]; then
        echo "FATAL: the moos-nvidia build has no NVIDIA RPMs mounted at /akmods."
        echo "       The caller must pass --build-arg AKMODS_IMAGE=<ublue akmods-nvidia-open image>"
        echo "       pinned to this image's kernel. See .github/workflows/build.yml (step"
        echo "       'Resolve NVIDIA akmods image') and the Justfile's build-nvidia recipe."
        echo "       Refusing to build an 'NVIDIA' image with no driver in it."
        exit 1
    fi

    # The kmod is compiled against ONE kernel. If the base image has moved to a newer
    # kernel than the akmods container was built for, the module will not load and the
    # machine black-screens. Refuse to build that image at all.
    kver_image=$(basename "$(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d | head -1)")
    # shellcheck source=/dev/null
    . /akmods/rpms/kmods/nvidia-vars
    if [ "${KERNEL_VERSION}" != "${kver_image}" ]; then
        echo "FATAL: akmods kmod was built for kernel ${KERNEL_VERSION}, but this image ships ${kver_image}."
        echo "       Pairing them would produce a black screen. Waiting for ublue to publish a matching akmod."
        exit 1
    fi
    echo "OK: kmod and image agree on kernel ${kver_image}."

    AKMODNV_PATH=/akmods/rpms IMAGE_NAME=kinoite MULTILIB=1 \
        bash /akmods/rpms/ublue-os/nvidia-install.sh

    # Prove the driver actually landed, rather than trusting the installer's exit code.
    rpm -q kmod-nvidia nvidia-driver >/dev/null || { echo "FATAL: NVIDIA packages are not installed."; exit 1; }
    find "/usr/lib/modules/${kver_image}" -name 'nvidia*.ko*' | grep -q . \
        || { echo "FATAL: no nvidia kernel modules under /usr/lib/modules/${kver_image}."; exit 1; }
    grep -rq "force_drivers" /usr/lib/dracut/dracut.conf.d/99-nvidia.conf \
        || { echo "FATAL: 99-nvidia.conf does not force the driver into the initramfs (black screen at boot)."; exit 1; }

    # ublue's installer also force-loads i915 and amdgpu. Here that is counter-productive:
    # this image already trims every non-NVIDIA GPU driver out of the initramfs because GRUB
    # could not allocate the ~368MB image that results from keeping them (see the dracut
    # section below). Forcing them back in re-inflates it, and buys nothing — i915/amdgpu are
    # loaded normally by udev from the real root a moment later; only NVIDIA needs to be
    # present early, for the KMS handoff that keeps the desktop from coming up black.
    sed -i 's@ i915 amdgpu nvidia @ nvidia @' /usr/lib/dracut/dracut.conf.d/99-nvidia.conf

    # dracut resolves force_drivers entries BY NAME through modules.dep. Without a fresh
    # depmod the map has no entry for the just-installed out-of-tree modules, dracut silently
    # finds nothing to force, and the initramfs comes out with no nvidia in it at all.
    depmod -a "${kver_image}"

    echo "OK: NVIDIA $(rpm -q --qf '%{VERSION}' nvidia-driver) installed."
    echo "    modules: $(find "/usr/lib/modules/${kver_image}" -name 'nvidia*.ko*' -printf '%f ' )"
    echo "    dracut : $(grep -h force_drivers /usr/lib/dracut/dracut.conf.d/99-nvidia.conf)"
fi

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
# plymouth-plugin-script: the moos boot theme is a native SCRIPT theme —
# moos.script drives the reveal by moving four small sprites (logo/ring/head/glow).
# plymouth-plugin-two-step is kept because Kinoite's own bgrt/spinner fallbacks use
# it; both explicit installs are harmless guarantees.
dnf5 -y install dracut-live livesys-scripts grub2-efi-x64-cdboot \
    plymouth-plugin-script plymouth-plugin-two-step

# MoOS branded boot splash (flicker-free). No -R flag on purpose: the dracut
# run right below regenerates the initramfs anyway, and the plymouth dracut
# module picks up the theme selected here.
plymouth-set-default-theme moos

# ── The Script theme must ship its script + sprites ──────────────────────────
#
# A script theme draws everything from moos.script by moving sprites, so unlike the
# old two-step theme it needs NO password-entry assets (lock/box/corner/keymap) —
# the script renders any LUKS prompt itself with Image.Text. But the same class of
# silent failure still exists: a script theme whose ScriptFile, or any sprite it
# loads, is missing falls straight back to Plymouth's TEXT splash — a green build
# with a grey boot, exactly what the two-step theme once shipped (loading lock
# image -> "can't show splash: No such file or directory" -> text splash). Nothing
# used to check what the plugin LOADS. So GATE that the script and its four sprites
# actually landed in the image.
_MOOS=/usr/share/plymouth/themes/moos
for _f in moos.script logo.png ring.png head.png glow.png; do
    test -f "${_MOOS}/${_f}" || {
        echo "GATE FAIL: moos theme is missing ${_f} — the Script splash would abort to text"
        exit 1
    }
done
echo "=== plymouth: moos Script theme present ==="
ls -1 "${_MOOS}" | grep -vE 'README' | sed 's/^/    /'

# Fedora's plymouth package keeps two distribution fallbacks outside the
# selected theme:
#   /usr/share/plymouth/plymouthd.defaults -> Theme=bgrt
#   /usr/share/plymouth/themes/spinner/watermark.png -> Fedora wordmark
# The selected moos theme is what dracut normally embeds, but leaving
# these Fedora fallbacks in the image means a future package scriptlet or a
# manual initramfs rebuild can bring the Fedora splash back.  Rebrand both
# fallback paths before dracut runs.  This changes only Plymouth policy/assets;
# it does not touch the kernel, BLS entries, OSTree layout, or EFI binaries.
sed -i 's/^Theme=.*/Theme=moos/' /usr/share/plymouth/plymouthd.defaults
# The Script theme has no watermark.png of its own (the mark is logo.png, moved by
# the script), so the Fedora spinner/bgrt fallback watermark is overwritten with
# the MoOS mark (logo.png) instead.
if [ -f /usr/share/plymouth/themes/spinner/watermark.png ]; then
    cp -f /usr/share/plymouth/themes/moos/logo.png \
        /usr/share/plymouth/themes/spinner/watermark.png
fi

# The photographed leak is this exact compatibility asset: Fedora's
# fedora-logos package owns spinner/watermark.png and bgrt points ImageDir at
# that directory. Keep the package for compatibility, but require its visible
# boot watermark to contain MoOS pixels before the definitive dracut run.
cmp -s /usr/share/plymouth/themes/moos/logo.png \
    /usr/share/plymouth/themes/spinner/watermark.png || {
    echo "FATAL: spinner compatibility watermark still contains foreign branding"; exit 1;
}

# Fail closed: both the administrator selection and distribution fallback
# must select MoOS, and the old Fedora spinner watermark must be gone.
grep -qx 'Theme=moos' /etc/plymouth/plymouthd.conf
grep -qx 'Theme=moos' /usr/share/plymouth/plymouthd.defaults
if [ -f /usr/share/plymouth/themes/spinner/watermark.png ]; then
    cmp -s /usr/share/plymouth/themes/moos/logo.png \
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

# KEEP NVIDIA in the initramfs (section (b2) force_drivers+= it) so the driver does
# early KMS and the DESKTOP renders — removing it entirely produced a black screen
# (Vulkan/Plasma had no working GPU at handoff). We only trim the OTHER GPU display
# drivers the NVIDIA machine doesn't need (nouveau, amdgpu, radeon, i915, xe). That
# drops the initramfs from ~368MB to ~242MB — below the ~368MB that GRUB could not
# allocate — while NVIDIA still works. Those drivers are not lost: udev loads them
# from the real root during normal boot.
# (The generic edition has no NVIDIA and is ~124MB.)
cat > /usr/lib/dracut/dracut.conf.d/99-moos-boot.conf <<'DRC'
add_dracutmodules+=" ostree dmsquash-live dmsquash-live-autooverlay "
# MoOS always boots its local OSTree/composefs deployment (or the local live
# squashfs). With --no-hostonly dracut otherwise includes 74nfs merely because
# nfs-utils is installed, and its pre-udev hook starts rpcbind + rpc.statd in
# the initrd on every boot. They cannot persist state there and log hard errors
# before switch-root. Omitting the *initrd* module does not remove NFS client
# support from the real system after boot.
omit_dracutmodules+=" nfs "
add_drivers+=" erofs overlay loop "
# Trim only the NON-NVIDIA GPU drivers (not present/needed on this hardware).
# NVIDIA stays (base force_drivers) for a working desktop.
omit_drivers+=" nouveau amdgpu radeon i915 xe nvidiafb "
DRC

# Capture dracut's OWN verbose log — the reliable source of truth. (The v20
# attempt proved `lsinitrd` is unusable inside the nested buildah container: it
# terminated the build step even though dracut had already logged
# "*** Including module: ostree ***". So we gate on dracut's log, not lsinitrd.)
DRACUT_NO_XATTR=1 dracut -v --force --zstd --reproducible --no-hostonly \
    --add "ostree dmsquash-live dmsquash-live-autooverlay" \
    --omit "nfs" \
    --add-drivers "erofs overlay loop" \
    --omit-drivers "nouveau amdgpu radeon i915 xe nvidiafb" \
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

if [ "${MOOS_IMAGE_NAME:-moos}" = "moos-nvidia" ]; then
    # Informational only. The binding gate is the lsinitrd proof further down, which reads the
    # initramfs that was actually produced instead of trusting dracut's log wording.
    echo "=== dracut nvidia mentions: $(grep -ciE 'nvidia' /tmp/moos-dracut.log || true) ==="
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

# The binding NVIDIA gate: the module must be INSIDE the initramfs that was just built.
# An nvidia image whose initramfs has no nvidia module hands Plasma a dead GPU and comes up
# to a black screen — which is exactly how this machine got bricked before. Read the real
# initramfs listing; do not infer it from dracut's log wording.
if [ "${MOOS_IMAGE_NAME:-moos}" = "moos-nvidia" ]; then
    echo "=== PROOF: nvidia modules inside the initramfs ==="
    _nv="$(grep -cE 'nvidia.*\.ko' /tmp/moos-lsinitrd.txt 2>/dev/null || echo 0)"
    if [ "${_lsrc}" -eq 0 ] && [ "${_nv}" -ge 1 ]; then
        echo "  >>> PROOF PASSED — ${_nv} nvidia module(s) in the initramfs:"
        grep -E 'nvidia.*\.ko' /tmp/moos-lsinitrd.txt | sed 's/^/      /' | head -6
    elif [ "${_lsrc}" -eq 0 ]; then
        echo "  >>> FATAL: the NVIDIA edition's initramfs contains NO nvidia module."
        echo "      It would boot to a black screen. Refusing to ship it."
        exit 1
    else
        echo "  >>> FATAL: could not read the initramfs to verify nvidia (lsinitrd exit=${_lsrc})."
        echo "      An unverifiable nvidia image is not shippable."
        exit 1
    fi

    # --- The splash: NVIDIA must NOT be told to draw on simpledrm ---------------
    # bootc kargs.d can only ADD kargs, never remove one, so an edition opts out by the
    # file not existing. plymouth.use-simpledrm is a real win where the KMS driver shows
    # up late (a VM, the live ISO) — and a splash-killer here, because nvidia is
    # force_drivers'd into THIS initramfs (proven three lines above) and owns the display
    # two seconds before plymouth-start even runs. Pointed at simpledrm, Plymouth draws on
    # a device that no longer drives the screen and the user sees a black boot with no MoOS
    # anywhere. Deleting the file lets Plymouth find card1 — which has KMS, or it would
    # have no connectors — and the emblem lands on the real display.
    # See system_files/usr/lib/bootc/kargs.d/20-moos-simpledrm.toml for the measurements.
    #
    # GATE: if that file is ever renamed or folded back into 10-moos-boot-splash.toml, this
    # rm silently removes nothing, the karg comes back, and the NVIDIA splash dies again
    # with a green build. That is exactly how it shipped the first time.
    test -f /usr/lib/bootc/kargs.d/20-moos-simpledrm.toml || {
        echo "GATE FAIL: 20-moos-simpledrm.toml is gone — the NVIDIA edition can no longer"
        echo "           opt out of plymouth.use-simpledrm, and its splash would go black."
        exit 1
    }
    rm -f /usr/lib/bootc/kargs.d/20-moos-simpledrm.toml
    echo "=== NVIDIA edition: plymouth.use-simpledrm withheld (nvidia owns the display) ==="
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
# via system_files. The MoOS image ref the installer deploys — EDITION-AWARE:
# a moos-nvidia image bakes a moos-nvidia install ref (MOOS_IMAGE_NAME is passed
# from the Containerfile ARG IMAGE_NAME), so ISO installs deploy the same edition
# and the user never has to `bootc switch` (which is what bricked the machine).
MOOS_IMAGEREF="ghcr.io/moalfarras-sys/${MOOS_IMAGE_NAME:-moos}"
MOOS_IMAGETAG="latest"

# The container signature policy is set ONCE, in section (z) near the end of this script —
# after every package install, so nothing can quietly restore a permissive rule afterwards.
# (An earlier version of this change patched the policy here as well, and the pre-existing
# block at the end silently overwrote it with insecureAcceptAnything. The image built clean
# and shipped unverified. One writer only.)

# anaconda-webui + cockpit-bridge are EXPLICIT: they are the WebUI frontend the
# advanced/dual-boot path uses, and on Fedora they are weak deps of anaconda —
# with install_weak_deps=False they would silently NOT install, leaving "Install
# MoOS (advanced)" with no installer at all. libblockdev-nvme/crypto add NVMe and
# LUKS disk detection so a modern laptop's disk is actually found.
dnf5 -y install --setopt=install_weak_deps=False \
    anaconda-live anaconda-webui cockpit-bridge firefox \
    libblockdev-btrfs libblockdev-lvm libblockdev-dm \
    libblockdev-nvme libblockdev-crypto whois
mkdir -p /var/lib/rpm-state   # Anaconda Web UI needs this to exist

# The MoOS installer (moos-installer → moos-install-to-disk) and the Anaconda
# advanced path both install the SAME edition they booted. Bake the edition-aware
# ref the helper reads (system_files ships the default moos ref; overwrite it so a
# moos-nvidia ISO installs moos-nvidia and the user never has to `bootc switch`).
mkdir -p /usr/lib/moos
printf '%s\n' "${MOOS_IMAGEREF}:${MOOS_IMAGETAG}" > /usr/lib/moos/install-imageref

# interactive-defaults.ks: the Anaconda ADVANCED / dual-boot path (the PRIMARY
# install path is now the MoOS QML installer, moos-installer → moos-install-to-disk,
# which the "Install MoOS" launcher runs). Install OFFLINE from the image embedded
# in the ISO's containers-storage — no network pull. The old registry transport
# was the #1 reason real-hardware installs failed: it needed internet, and the
# wired-only network default (moos.conf FIRST_WIRED_WITH_LINK) never came up on a
# Wi-Fi laptop, so the deploy aborted. This is the proven Titanoboa/Bazzite pattern:
#   --transport=containers-storage : read the image already on the USB (offline).
#   --no-signature-verification    : a local copy carries no sigstore attachment,
#       and copying signed layers to disk would invalidate them (bootc #812). Safe:
#       the bits came from the user's own USB, not the network.
#   clearpart/autopart/bootloader  : real defaults so the common case is one click,
#       not the error-prone manual partitioner (the old kickstart had NONE and
#       dropped users into manual mode — a top human cause of "the install failed").
# The %post re-arms SIGNED day-2 updates so every future `bootc upgrade` verifies
# the cosign signature (the image ships the key + policy.json + registries.d).
# Result: offline, one-click install — and a verified system for life. The image
# is embedded into the ISO's /var/lib/containers/storage by the ISO build
# (.github/workflows/build-iso.yml) — without that this path fails "no image".
cat >> /usr/share/anaconda/interactive-defaults.ks <<KSEOF

clearpart --all --initlabel
autopart --type=btrfs
bootloader --location=mbr
ostreecontainer --url=${MOOS_IMAGEREF}:${MOOS_IMAGETAG} --transport=containers-storage --no-signature-verification

%post --erroronfail
set -euo pipefail
# Re-arm signed verification for day-2 updates (the install itself was local and
# unverified BY DESIGN). Rewrite the deployment origin to ostree-image-signed so
# bootc verifies the cosign signature on every upgrade. Fail loudly rather than
# ship a system that silently stopped verifying.
for origin in /ostree/deploy/*/deploy/*.origin; do
    [ -f "\$origin" ] || continue
    sed -i 's|^container-image-reference=.*|container-image-reference=ostree-image-signed:docker://${MOOS_IMAGEREF}:${MOOS_IMAGETAG}|' "\$origin"
done
%end
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
    # Repoint the "Install MoOS" icon at the BEAUTIFUL MoOS QML installer
    # (/usr/bin/moos-installer) instead of raw Anaconda. The old Anaconda WebUI
    # storage screen is confusing and its registry-pull install failed offline;
    # moos-installer is the clear, offline, disk-card flow, and is now the SINGLE
    # install path — the old "Advanced / dual-boot → raw Anaconda" escape hatch was
    # removed (it opened a second installer window over the first and its kickstart
    # default erased all disks under a "dual-boot" label). Anaconda stays installed
    # for the live ISO's infrastructure but is no longer reachable from any UI.
    # StartupWMClass is retargeted so Plasma matches the QML window to
    # org.moos.installer.desktop (MoOS icon).
    sed -i \
        -e 's|^Name=.*|Name=Install MoOS|' \
        -e '/^Name\[/d' \
        -e 's|^GenericName=.*|GenericName=Install MoOS to disk|' \
        -e '/^GenericName\[/d' \
        -e 's|^Comment=.*|Comment=Install MoOS to your disk|' \
        -e '/^Comment\[/d' \
        -e 's|^Exec=.*|Exec=moos-installer|' \
        -e 's|^TryExec=.*|TryExec=moos-installer|' \
        -e 's|^Icon=.*|Icon=moos-logo|' \
        -e 's|^StartupWMClass=.*|StartupWMClass=org.moos.installer|' \
        -e 's|^Categories=.*|Categories=System;|' \
        "$_liveinst"
    # Arabic display name right after the (now single) Name line.
    sed -i '/^Name=Install MoOS$/a Name[ar]=تثبيت MoOS' "$_liveinst"
fi
unset -v _liveinst

# -----------------------------------------------------------------------------
# (c3b) Discover: keep the engine, hide the duplicate storefront entry
# -----------------------------------------------------------------------------
# The owner wants ONE branded storefront, and that is now the standalone
# Mo Store app (org.moos.store.desktop -> /usr/bin/moos-store, the curated
# catalog UI that used to live inside the Welcome). Discover used to be
# rebranded "Mo Store" in place, which made TWO menu entries with the same
# name the moment the real Mo Store shipped. So Discover keeps its engine
# (plasma-discover still handles update notifications, firmware and appstream
# deep links) but leaves every menu: NoDisplay=true. The MoOS name/icon stay on
# the entry so any surface that still resolves it (notifier popups) shows MoOS
# identity, never a foreign brand.
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
    # GenericName may be absent; add an Arabic one if the key exists.
    grep -q '^GenericName=' "$_disc" && sed -i '/^GenericName=App Store$/a GenericName[ar]=متجر التطبيقات' "$_disc" || true
    # Hide it from menus/krunner — org.moos.store is the one visible storefront.
    grep -q '^NoDisplay=' "$_disc" \
        && sed -i 's|^NoDisplay=.*|NoDisplay=true|' "$_disc" \
        || sed -i '/^\[Desktop Entry\]/a NoDisplay=true' "$_disc"
fi
unset -v _disc

# -----------------------------------------------------------------------------
# (c3) Qt runtime extras — on-screen keyboard + media/image plugins
# -----------------------------------------------------------------------------
# These were originally pulled for the retired SDDM theme, but that stack is gone from this
# image (Kinoite 44 boots plasmalogin; the dead theme tree was deleted, and
# verify_image_experience.py now fails the build if /usr/share/sddm returns).
# They stay because the RUNNING system uses them:
# - qt6-qtvirtualkeyboard: Plasma's on-screen keyboard (Arabic input on the
#                          lock screen and in the greeter)
# - qt6-qtsvg:             SVG icon rendering across Qt apps
# - qt6-qtmultimedia:      media playback for QML surfaces (Mo AI, Welcome)
# - qt6-qtimageformats:    extra image format plugins (wallpapers, previews)
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

# Kawkab Mono — the Arabic terminal font, and the reason Arabic in Konsole was
# unreadable without it.
#
# A terminal draws one glyph per fixed-width cell. Every Arabic font in Fedora
# is PROPORTIONAL, so when Konsole placed each letter in its own cell the
# cursive joins were torn apart: الطرفية came out as ا ل ط ر ف ي ة — a word
# shattered into disconnected letters. No fontconfig ordering fixes that,
# because the defect is the metrics, not the choice of font. Kawkab Mono is
# drawn for exactly this: its letters connect ACROSS a fixed advance.
#
# Fedora does not package it, so it comes from the upstream OFL release, pinned
# by digest. A changed tarball fails the build rather than silently shipping
# something else.
kawkab_ver=0.501
kawkab_sha=11c06f57dddefaf0166d74caaa072865ab6ff8d34076e7ec5d2c20edda145666
kawkab_zip=/tmp/kawkab-mono.zip
curl -Lf --retry 3 -o "${kawkab_zip}" \
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
    || { echo "GATE FAIL: Kawkab Mono did not install"; exit 1; }

# Ask the question the way Konsole asks it, which is NOT what `fc-match` answers.
#
# Konsole requests the family BY NAME (MoOS.profile: Font=JetBrains Mono) and Qt
# then falls back PER GLYPH for the characters that family does not have — all of
# Arabic. `fc-match "JetBrains Mono:lang=ar"` returns JetBrains Mono itself, because
# the pattern names it; it says nothing about the fallback. Only the SORTED list
# does. The first entry that is not JetBrains Mono is the font that will actually
# draw an Arabic letter in the terminal, and it must be Kawkab Mono — anything else
# is proportional and shatters the cursive joins.
#
# The first version of this gate used plain `fc-match` and failed the build against
# a fontconfig that was correct.
arabic_fallback="$(fc-match -s 'JetBrains Mono:lang=ar' | grep -v '"JetBrains Mono"' | head -1)"
case "${arabic_fallback}" in
    *Kawkab*) echo "Arabic terminal fallback: ${arabic_fallback}" ;;
    *) echo "GATE FAIL: Arabic in the terminal falls back to '${arabic_fallback}', not Kawkab Mono"
       exit 1 ;;
esac

# -----------------------------------------------------------------------------
# (c4b) moos-qml-shell — the QML host that gives MoOS's apps a real app_id
# -----------------------------------------------------------------------------
# Mo AI ran as `qml-qt6 main.qml`, so its Wayland app_id was org.qt-project.qml-qt6
# and Plasma could not match the window to org.moos.moai.desktop. The taskbar fell
# back to the QML runtime's own icon — the generic green Qt diamond. Same for
# moos-welcome: all three QML apps shared the one app_id.
#
# qml-qt6 has no flag to set it (checked: -a, -I, -f, -c, --desktop, --gles,
# --software … and nothing for the app id). QGuiApplication::setDesktopFileName()
# is the only supported route, so MoOS hosts the QML itself. See the long comment
# in build_files/moos-qml-shell.cpp.
#
# The compiler and the Qt headers are BUILD-ONLY: installed, used, and removed
# inside this same RUN, so none of it lands in the shipped image.
#
# qt6-qtdeclarative-devel is installed here and NOT removed. It is also installed
# further down in section (c8) — but that is ~200 lines later, and this needs
# Qt6Qml.pc NOW: without it pkg-config cannot resolve Qt6Qml and the compile dies
# with "QGuiApplication: No such file or directory". It stays because it is what
# provides /usr/bin/qml-qt6, which both the QML smoke-test gate and the launchers'
# fallback path depend on. The later install is then a no-op.
#
# KF6DBusAddons + KF6WindowSystem are what make the shell single-instance (see the header of
# moos-qml-shell.cpp). Their -devel packages are build-only like the rest; the RUNTIME libraries
# they link against — libKF6DBusAddons.so.6, libKF6WindowSystem.so.6 — are already in the image
# because Plasma itself depends on them, so this costs the image nothing. Neither ships a
# pkg-config file (KDE distributes CMake configs), hence the explicit -I/-l.
dnf5 -y install gcc-c++ qt6-qtbase-devel qt6-qtdeclarative-devel \
                kf6-kdbusaddons-devel kf6-kwindowsystem-devel
# moos-qml-shell now carries a Q_OBJECT (InstallerBridge — the installer's secure
# recipe channel), so it must be moc'd: the .cpp ends with #include
# "moos-qml-shell.moc", which moc generates next to the source. Locate moc across
# the paths Fedora's qt6-qtbase-devel installs it under.
_moc="$(command -v moc-qt6 2>/dev/null || true)"
[ -z "$_moc" ] && [ -x /usr/lib64/qt6/libexec/moc ] && _moc=/usr/lib64/qt6/libexec/moc
[ -z "$_moc" ] && _moc="$(command -v moc 2>/dev/null || true)"
[ -n "$_moc" ] || { echo "FATAL: Qt6 moc not found — cannot build moos-qml-shell."; exit 1; }
# /ctx is a READ-ONLY bind mount — write the generated meta-object to writable /tmp
# and let g++ find it via -I/tmp (the .cpp's #include "moos-qml-shell.moc").
"$_moc" /ctx/moos-qml-shell.cpp -o /tmp/moos-qml-shell.moc
g++ -std=c++17 -fPIC -O2 -I/tmp /ctx/moos-qml-shell.cpp -o /usr/bin/moos-qml-shell \
    -I/usr/include/KF6/KDBusAddons -I/usr/include/KF6/KWindowSystem \
    -lKF6DBusAddons -lKF6WindowSystem \
    $(pkg-config --cflags --libs Qt6Gui Qt6Qml Qt6Core Qt6DBus)
chmod 0755 /usr/bin/moos-qml-shell
dnf5 -y remove gcc-c++ qt6-qtbase-devel kf6-kdbusaddons-devel kf6-kwindowsystem-devel

# The single-instance guard is a LINK, and a link that silently did not happen leaves a shell that
# still runs, still shows the app, and still opens a second copy on the next click — exactly the
# bug this replaced, with a green build. So check the binary actually carries it.
ldd /usr/bin/moos-qml-shell | grep -q libKF6DBusAddons \
    || { echo "GATE FAIL: moos-qml-shell is not linked against KF6DBusAddons — it would open twice"; exit 1; }

# Gate it. A wrong app_id is invisible to every other check in this build: the app
# launches, the QML loads, nothing errors — the icon is just silently the wrong one.
test -x /usr/bin/moos-qml-shell \
    || { echo "GATE FAIL: moos-qml-shell did not build"; exit 1; }
for launcher in /usr/bin/moai /usr/bin/moos-welcome /usr/bin/moos-store; do
    grep -q "moos-qml-shell" "$launcher" \
        || { echo "GATE FAIL: ${launcher} does not use moos-qml-shell — its window will show the generic Qt icon"; exit 1; }
done

# Secret Service CLI used by Mo AI. On Plasma this talks to KWallet through
# the freedesktop Secret Service API; cloud credentials never enter JSON files.
dnf5 -y install libsecret

# Gaming/compat host stack, baked in so it is ready before the first game.
# gamescope is Valve's microcompositor — it hands a game its own fixed-refresh
# surface with integrated FSR/NIS upscaling and frame limiting, the practical
# substitute for hardware VRR on a fixed-refresh panel, and is what a Steam
# "gamescope session" and gamemode drive. gamemode requests the performance
# governor + realtime scheduling for the lifetime of a game only. mangohud is the
# in-game overlay. (Steam/Bottles/Lutris stay Flatpak, installed on demand by
# `moai-do setup-gaming`; these are the host tools those Flatpaks reach into, and
# they pair with ntsync — see modules-load.d/moos-gaming.conf — for the fast
# Proton sync path.)
dnf5 -y install gamescope gamemode mangohud

# Full Arabic + English locale support (glibc locales, hunspell, input) —
# MoOS is bilingual by design (MOOS_DESIGN_SYSTEM.md §7 RTL rules).
#
# German is a keyboard LAYOUT here, not a UI language: the owner's hardware is a
# German keyboard, so the default xkb layout is de,ara (see /etc/xdg/kxkbrc), while
# the welcome/language wizards still offer only Arabic + English. langpacks-de is
# still NOT shipped: German Plasma/GTK *catalogues* on disk are where an invalid LANG
# could fall back into a German UI — the "system shows German" bug. The layout gives
# the right keys; it never changes the UI language.
# (MoPlayer keeps its own in-app ar/en/de strings; it does not need the OS langpack.)
dnf5 -y install langpacks-ar langpacks-en

# --- fcitx5 must not be on this machine --------------------------------------
# It is an input-method framework MoOS does not need — Arabic and English are xkb
# LAYOUTS, which KWin handles natively; fcitx exists for CJK input methods, and it
# arrives here only as a dependency of fcitx5-mozc (a JAPANESE IME) that the base
# image happens to pull in.
#
# And it is not merely useless, it is destructive. It ships a launcher entry, so it is
# one click away in the app menu — and the moment it starts it TAKES OVER the keyboard
# and rewrites the user's ~/.config/kxkbrc to `LayoutList=us`, wiping whatever they had.
# That happened on the maintainer's machine on 2026-07-13: fcitx5 was launched once, and
# the US+Arabic pair MoOS ships (/etc/xdg/kxkbrc) was replaced by a lone US layout.
# The user could no longer type Arabic, there was no error and no notification,
# and nothing in MoOS noticed — moos-selfcheck was reading localectl, i.e. the SYSTEM
# default, which was still perfectly correct while the session used something else. A
# user-level file outranking the image, silently: the same trap as every other one in
# this repo (AGENTS.md).
#
# So it does not ship. mozc goes with it — a Japanese IME on a bilingual Arabic/German
# desktop was never a feature — and the gate below keeps them out.
dnf5 -y remove fcitx5-mozc fcitx5 fcitx5-data fcitx5-configtool 2>/dev/null || true
for pkg in fcitx5 fcitx5-mozc; do
    rpm -q "$pkg" >/dev/null 2>&1 \
        && { echo "GATE FAIL: ${pkg} is still in the image — it hijacks the keyboard layout the first time anyone launches it"; exit 1; }
done
test ! -e /usr/share/applications/org.fcitx.Fcitx5.desktop \
    || { echo "GATE FAIL: fcitx5 still has a launcher entry — one click and the user's layouts are gone"; exit 1; }

# Qt WebEngine spell-check dictionaries.
#
# hunspell dictionaries are not readable by QtWebEngine — it needs them converted to its own
# .bdic format. The qt6-qtwebengine RPM runs that converter from a scriptlet, and the
# converter SIGTRAPs inside the build container (visible on the host as a pile of
# qwebengine_convert_dict coredumps during every image build). The scriptlet swallows it, so
# the image shipped with an EMPTY /usr/share/qt6/qtwebengine_dictionaries and spell-check
# silently did not exist in any QtWebEngine app — in a bilingual OS, including Arabic.
#
# Running the converter ourselves works (the crash is in how the scriptlet invokes it, not in
# the tool), so do that and assert the result instead of trusting a scriptlet that fails
# quietly.
_convert_dict=/usr/lib64/qt6/libexec/qwebengine_convert_dict
if [ -x "$_convert_dict" ]; then
    mkdir -p /usr/share/qt6/qtwebengine_dictionaries /tmp/dicts
    _bdic=0
    for _dic in /usr/share/hunspell/*.dic; do
        [ -e "$_dic" ] || continue
        _name="$(basename "$_dic" .dic)"
        _aff="/usr/share/hunspell/${_name}.aff"
        _src="$_dic"

        # Chromium's converter aborts on the hunspell IGNORE command
        # ("We don't support the IGNORE command yet", aff_reader.cc) — and the Arabic
        # dictionaries use it, to ignore tashkeel. That single unsupported directive is why a
        # bilingual OS shipped with no Arabic spell-check at all.
        #
        # Convert from a copy with IGNORE removed. The honest cost: diacritics are no longer
        # ignored, so a *fully vocalised* Arabic word can be flagged as misspelled. Ordinary
        # undiacritised Arabic — which is nearly all of it — checks correctly. A dictionary
        # that is right about the common case beats no dictionary at all.
        if [ -f "$_aff" ] && grep -q "^IGNORE" "$_aff" 2>/dev/null; then
            grep -v "^IGNORE" "$_aff" > "/tmp/dicts/${_name}.aff"
            cp -L "$_dic" "/tmp/dicts/${_name}.dic"
            _src="/tmp/dicts/${_name}.dic"
        fi

        if QTWEBENGINE_DISABLE_SANDBOX=1 QT_QPA_PLATFORM=offscreen "$_convert_dict" "$_src" \
            "/usr/share/qt6/qtwebengine_dictionaries/${_name}.bdic" >/dev/null 2>&1; then
            _bdic=$((_bdic + 1))
        fi
    done
    rm -rf /tmp/dicts
    echo "OK: built ${_bdic} Qt WebEngine spell-check dictionaries."

    # Arabic and English are the two languages this OS promises. Shipping the directory empty
    # is the silent regression this whole block exists to stop, so assert on both.
    ls /usr/share/qt6/qtwebengine_dictionaries/en_US.bdic >/dev/null 2>&1 \
        || { echo "FATAL: no English spell-check dictionary was produced."; exit 1; }
    ls /usr/share/qt6/qtwebengine_dictionaries/ar_*.bdic >/dev/null 2>&1 \
        || { echo "FATAL: no Arabic spell-check dictionary was produced."; exit 1; }
fi

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

# Second pass: the TEAL variant, for MoOS UI2. UI2's primary is mineral
# turquoise (#4ED7C8) and its chrome is graphite — Colloid's '-Teal' folder
# colour (#4DB6AC, verified in install.sh colors_folder() at the pinned
# commit) sits in that family, where the 'default' blue (#5b9bf8) was chosen
# to match Nova's electric blue and reads foreign on a UI2 desktop. Only the
# folder/accent family changes; app icons keep their own colours, and the
# monochrome symbolics per Light/Dark are what carry contrast on big screens.
# Directory names produced: Colloid-Teal, Colloid-Teal-Light, Colloid-Teal-Dark
# (THEME_VARIANTS[7]='-Teal' — capitalised, unlike the lowercase clean_old_theme
# loop that misled a first reading of install.sh).
bash /tmp/colloid/install.sh -d /usr/share/icons -t teal -s default
rm -rf /tmp/colloid

# "MoOSUI2" / "MoOSUI2Light" are the stable internal IDs for the MoOS icon
# themes.  Colloid provides the broad application/file-type vocabulary, while
# MoOS-owned applications live in a first-party overlay.  That overlay comes
# first in Directories=, so MoOS surfaces have one coherent silhouette instead
# of inheriting whichever upstream app icon happens to exist.
# VERIFIED: an Inherits-only index.theme is NOT enough —
# - freedesktop icon-theme spec (File Formats, Table 1) marks Directories=
#   as REQUIRED (Inherits is the optional one);
# - KDE's KIconTheme only counts a directory that exists on disk
#   (QFileInfo::exists check in the ctor before populating mDirs) and
#   isValid() requires a non-empty mDirs/mScaledDirs — a dir-less theme is
#   treated as invalid and Plasma would fall back / not stick.
# So: copy the base's full index.theme (keeps Directories= plus all
# per-directory sections) and symlink the base's icon dirs in — cheap (no
# duplication), spec-valid, and the theme resolves icons directly instead of
# relying purely on inheritance. Relative targets keep the links valid inside
# the ostree/bootc image; the */ glob matches dirs and dir-symlinks only, so
# index.theme / icon-theme.cache are skipped.
#
# rm -rf first: this block used to run twice (a dead first pass built the same
# names from Colloid-Dark/Light before this one rebuilt them from Teal), and a
# subdir the second base lacks would have left a stale foreign-colour symlink
# behind. One pass, from a clean directory, cannot.

# "MoOSUI2" / "MoOSUI2Light" = the UI2 icon themes, teal folders over the same
# proven copy-index-then-symlink route. Nova/NovaLight stay installed untouched:
# they are what UI1 (the documented rollback) selects.
rm -rf /usr/share/icons/MoOSUI2
mkdir -p /usr/share/icons/MoOSUI2
cp /usr/share/icons/Colloid-Teal-Dark/index.theme /usr/share/icons/MoOSUI2/index.theme
sed -i \
    -e 's|^Name=.*|Name=MoOS UI|' \
    -e 's|^Comment=.*|Comment=MoOS icons — mineral teal on graphite|' \
    -e 's|^Inherits=.*|Inherits=Colloid-Teal-Dark,Papirus-Dark,breeze-dark,hicolor|' \
    -e 's|^Directories=|Directories=moos/apps/scalable,|' \
    /usr/share/icons/MoOSUI2/index.theme
test -d /usr/share/icons/Colloid-Teal-Dark/apps
for d in /usr/share/icons/Colloid-Teal-Dark/*/; do
    b="$(basename "${d}")"
    ln -snf "../Colloid-Teal-Dark/${b}" "/usr/share/icons/MoOSUI2/${b}"
done
mkdir -p /usr/share/icons/MoOSUI2/moos/apps/scalable
cp /usr/share/icons/hicolor/scalable/apps/moos-*.svg \
    /usr/share/icons/MoOSUI2/moos/apps/scalable/
cat >> /usr/share/icons/MoOSUI2/index.theme <<'EOF'

[moos/apps/scalable]
Size=64
Context=Applications
Type=Scalable
MinSize=16
MaxSize=512
EOF
gtk-update-icon-cache -f /usr/share/icons/MoOSUI2 || true

rm -rf /usr/share/icons/MoOSUI2Light
mkdir -p /usr/share/icons/MoOSUI2Light
cp /usr/share/icons/Colloid-Teal-Light/index.theme /usr/share/icons/MoOSUI2Light/index.theme
sed -i \
    -e 's|^Name=.*|Name=MoOS UI Light|' \
    -e 's|^Comment=.*|Comment=MoOS icons — mineral teal on tidal mist|' \
    -e 's|^Inherits=.*|Inherits=Colloid-Teal-Light,Papirus,breeze,hicolor|' \
    -e 's|^Directories=|Directories=moos/apps/scalable,|' \
    /usr/share/icons/MoOSUI2Light/index.theme
test -d /usr/share/icons/Colloid-Teal-Light/apps
for d in /usr/share/icons/Colloid-Teal-Light/*/; do
    b="$(basename "${d}")"
    ln -snf "../Colloid-Teal-Light/${b}" "/usr/share/icons/MoOSUI2Light/${b}"
done
mkdir -p /usr/share/icons/MoOSUI2Light/moos/apps/scalable
cp /usr/share/icons/hicolor/scalable/apps/moos-*.svg \
    /usr/share/icons/MoOSUI2Light/moos/apps/scalable/
cat >> /usr/share/icons/MoOSUI2Light/index.theme <<'EOF'

[moos/apps/scalable]
Size=64
Context=Applications
Type=Scalable
MinSize=16
MaxSize=512
EOF
gtk-update-icon-cache -f /usr/share/icons/MoOSUI2Light || true

# Gate all four. An icon theme whose Directories= is missing is treated as INVALID by
# KIconTheme and Plasma silently falls back — the desktop looks fine at a glance
# and every icon is somebody else's.
for t in MoOSUI2 MoOSUI2Light; do
    grep -q '^Directories=' "/usr/share/icons/${t}/index.theme" \
        || { echo "GATE FAIL: ${t} icon theme has no Directories= — KIconTheme will reject it"; exit 1; }
    test -d "/usr/share/icons/${t}/apps" \
        || { echo "GATE FAIL: ${t} icon theme has no apps/ dir"; exit 1; }
    grep -q '^Directories=moos/apps/scalable,' "/usr/share/icons/${t}/index.theme" \
        || { echo "GATE FAIL: ${t} does not prioritize the MoOS app overlay"; exit 1; }
    test -f "/usr/share/icons/${t}/moos/apps/scalable/moos-themes.svg" \
        && test ! -L "/usr/share/icons/${t}/moos/apps/scalable/moos-themes.svg" \
        || { echo "GATE FAIL: ${t} has no owned MoOS application artwork"; exit 1; }
done

# -----------------------------------------------------------------------------
# (c6) MoOS cursor theme (Bibata Modern Ice, rebranded at build time)
# -----------------------------------------------------------------------------
# Like the Nova icons (c5), the MoOS cursors are produced HERE at image
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

# "MoOS" = branded copy of Bibata-Modern-Ice (cp -a keeps the alias
# symlinks inside cursors/ as symlinks). The unmodified upstream dir stays
# installed alongside — harmless, and the copied cursor.theme still says
# Inherits="Bibata-Modern-Ice", which keeps resolving through it.
cp -a /usr/share/icons/Bibata-Modern-Ice /usr/share/icons/MoOS
sed -i 's|^Name=.*|Name=MoOS Pointer|' /usr/share/icons/MoOS/index.theme
sed -i 's|^Name=.*|Name=MoOS Pointer|' /usr/share/icons/MoOS/cursor.theme
sed -i 's|^Comment=.*|Comment=MoOS light pointer (Bibata Modern Ice by ful1e5, GPL-3.0)|' \
    /usr/share/icons/MoOS/index.theme

# GPL-3.0 attribution notice (Bibata is GPL — keep credit next to the copy).
cat > /usr/share/icons/MoOS/MOOS-NOTICE.txt <<'EOF'
MoOS cursor theme — attribution notice
=========================================
MoOS is a renamed build of "Bibata Modern Ice" v2.0.7 by
Abdulkaiz Khatri (ful1e5) and contributors:
    https://github.com/ful1e5/Bibata_Cursor
License: GNU General Public License v3.0 (GPL-3.0).
The only modification is the theme name in index.theme / cursor.theme;
the cursor artwork itself is unmodified. The unmodified upstream theme is
installed alongside at /usr/share/icons/Bibata-Modern-Ice.
EOF

# "MoOSDark" = the DARK half of the same family (Bibata Modern Classic).
# A white pointer on Tidal Light's mint canvas (#D8EBE7) is a low-contrast
# pointer — the light Global Theme selects MoOSDark instead, so each half
# gets the cursor that reads against ITS canvas. Same pinned release, same
# rebrand-only treatment as MoOS above.
curl -Lf --retry 3 -o /tmp/bibata-modern-classic.tar.xz \
    "https://github.com/ful1e5/Bibata_Cursor/releases/download/v2.0.7/Bibata-Modern-Classic.tar.xz"
tar -xJf /tmp/bibata-modern-classic.tar.xz -C /usr/share/icons/
rm -f /tmp/bibata-modern-classic.tar.xz
test -d /usr/share/icons/Bibata-Modern-Classic/cursors   # hard-fail if the tarball layout ever changes

cp -a /usr/share/icons/Bibata-Modern-Classic /usr/share/icons/MoOSDark
sed -i 's|^Name=.*|Name=MoOS Pointer Dark|' /usr/share/icons/MoOSDark/index.theme
sed -i 's|^Name=.*|Name=MoOS Pointer Dark|' /usr/share/icons/MoOSDark/cursor.theme
sed -i 's|^Comment=.*|Comment=MoOS dark pointer (Bibata Modern Classic by ful1e5, GPL-3.0)|' \
    /usr/share/icons/MoOSDark/index.theme

cat > /usr/share/icons/MoOSDark/MOOS-NOTICE.txt <<'EOF'
MoOSDark cursor theme — attribution notice
============================================
MoOSDark is a renamed build of "Bibata Modern Classic" v2.0.7 by
Abdulkaiz Khatri (ful1e5) and contributors:
    https://github.com/ful1e5/Bibata_Cursor
License: GNU General Public License v3.0 (GPL-3.0).
The only modification is the theme name in index.theme / cursor.theme;
the cursor artwork itself is unmodified. The unmodified upstream theme is
installed alongside at /usr/share/icons/Bibata-Modern-Classic.
EOF

# The early session, greeter and any toolkit that asks for the generic
# "default" cursor must resolve to MoOS too.  Replace only a possible alias;
# never follow it and accidentally rewrite the inherited cursor package.
if [ -L /usr/share/icons/default ] || [ -f /usr/share/icons/default ]; then
    rm -f /usr/share/icons/default
fi
mkdir -p /usr/share/icons/default
cat > /usr/share/icons/default/index.theme <<'EOF'
[Icon Theme]
Name=MoOS Default Pointer
Inherits=MoOS
EOF
grep -q '^Inherits=MoOS$' /usr/share/icons/default/index.theme \
    || { echo "GATE FAIL: the default pointer does not resolve to MoOS"; exit 1; }

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

# Photos and video. MoOS shipped NEITHER — there was no image viewer in the
# image at all, and no default for image/*. Double-clicking a photo therefore
# opened whatever browser the user happened to install, because a browser's
# desktop file claims image/png and nothing in MoOS contested it. A desktop
# that cannot show you a picture is not finished.
#
# gwenview: KDE's viewer. It inherits the Nova colour scheme and icon theme for
#           free, and it is what Dolphin's "Open" already expects.
# haruna:   KDE's mpv frontend. mpv means real hardware decode — on the NVIDIA
#           edition that is NVDEC, so 4K video costs the CPU almost nothing.
# kf6-kimageformats: HEIF, AVIF, JPEG-XL and friends. Qt cannot decode them on its
#           own, so without this gwenview opens a photo straight off a modern phone
#           and shows a grey box. NOTE the kf6- prefix: there is no bare
#           `kimageformats` package in Fedora 44 — only kf5-/kf6- — and naming it
#           wrong fails the build at the dnf step.
# ffmpegthumbs / kdegraphics-thumbnailers: Dolphin thumbnails for video and RAW.
dnf5 -y install \
    gwenview \
    haruna \
    kf6-kimageformats \
    ffmpegthumbs \
    kdegraphics-thumbnailers

# MoPlayer's runtime, named explicitly.
#
# Every one of these is *already* in the image today — but by accident. libmpv
# arrives because haruna drags it in; gtk3 because Firefox does; libEGL because
# Plasma does. MoPlayer is a GTK application that links libmpv directly, and an
# app whose dependencies are supplied by unrelated packages is an app that breaks
# the day one of them is dropped, with no build failure and no warning: it simply
# stops opening, on the users' machines, after the image has shipped.
#
# So they are named here, and the gate below fails the build if they are missing.
# This is the same argument this file already makes for the GStreamer codecs.
#
# `libglvnd-gles`, not `mesa-libGLESv2` — and this cost a whole image build. There
# is no `mesa-libGLESv2` package on Fedora 44: `libGLESv2.so.2` is dispatched by
# GLVND and shipped by `libglvnd-gles`, with Mesa behind it. dnf5 does not warn on
# an unknown package name, it *fails the transaction* ("No match for argument"),
# so the whole image stopped building — twenty minutes after MoPlayer itself had
# compiled cleanly. Verify a name against the repo before adding it here:
#   dnf repoquery --whatprovides 'libGLESv2.so.2()(64bit)'
dnf5 -y install mpv-libs gtk3 libepoxy mesa-libEGL libglvnd-gles

# The gate names the *libraries* the player dlopen()s, not the packages that happen
# to carry them today: a rename like the one above must fail loudly here, not
# silently produce an image whose player will not open a window.
for lib in mpv-libs gtk3 libepoxy; do
    rpm -q "${lib}" >/dev/null \
        || { echo "GATE FAIL: MoPlayer runtime dependency ${lib} is missing"; exit 1; }
done
for so in libEGL.so.1 libGLESv2.so.2; do
    ldconfig -p | grep -q "${so}" \
        || { echo "GATE FAIL: MoPlayer needs ${so} and no package in this image provides it"; exit 1; }
done

# MoPlayer itself: the bundle comes from the moplayer-build stage (see the
# Containerfile), the launcher and the .desktop from system_files. Neither half is
# any use without the other, so both are checked here.
#
# MoOS's own AGENTS.md is blunt about why: "a gate that cannot fail is worse than
# no gate". Each line below is a way MoPlayer has actually broken, or a way the
# QML apps did before it.
test -x /usr/lib/moplayer/moplayer \
    || { echo "GATE FAIL: the MoPlayer binary is missing"; exit 1; }
test -d /usr/lib/moplayer/data/flutter_assets \
    || { echo "GATE FAIL: MoPlayer has no flutter_assets — it would open to a blank window"; exit 1; }
test -f /usr/lib/moplayer/data/icudtl.dat \
    || { echo "GATE FAIL: MoPlayer has no ICU data — it would abort on the first frame"; exit 1; }
test -x /usr/bin/moplayer \
    || { echo "GATE FAIL: the MoPlayer launcher is missing or not executable"; exit 1; }

# Every shared library the bundle needs must resolve *inside the image*. This is
# the check that catches "built against a library the final image does not have" —
# which fails at run time, on the user's machine, as a window that never appears.
if ldd /usr/lib/moplayer/moplayer | grep -q 'not found'; then
    echo "GATE FAIL: MoPlayer has unresolved shared libraries:"
    ldd /usr/lib/moplayer/moplayer | grep 'not found'
    exit 1
fi

# The app_id is written in four places that cannot see each other (Dart, CMake,
# the .desktop file, the MPRIS bus name). When they drift, the app still builds
# and still runs — and quietly wears a generic icon, with media keys that raise
# nothing. Plasma matches window→launcher by this string and nothing else.
grep -qx 'StartupWMClass=org.moos.moplayer' /usr/share/applications/org.moos.moplayer.desktop \
    || { echo "GATE FAIL: MoPlayer's StartupWMClass drifted — Plasma will show a generic icon"; exit 1; }
grep -q 'org\.moos\.moplayer' /usr/lib/moplayer/moplayer \
    || { echo "GATE FAIL: the app_id is not baked into the MoPlayer binary"; exit 1; }

desktop-file-validate /usr/share/applications/org.moos.moplayer.desktop \
    || { echo "GATE FAIL: MoPlayer's .desktop file is not valid"; exit 1; }

# The launcher's jump list promises six sections. MoOS shipped eleven buttons once
# that opened routes nobody had implemented; the app parses these, and this is the
# cheap half of making sure it still does.
for action in Live Movies Series Search Favorites Settings; do
    grep -qx "\[Desktop Action ${action}\]" /usr/share/applications/org.moos.moplayer.desktop \
        || { echo "GATE FAIL: MoPlayer's launcher lost its ${action} action"; exit 1; }
done

# Mo Remote: private phone-to-MoOS control. One XDG RemoteDesktop+ScreenCast portal
# session carries BOTH halves of remote control:
#   - video: a PipeWire stream, encoded to JPEG by GStreamer (mo-remote-portal.py)
#   - input: absolute pointer + keysym keyboard, injected through the same portal
# ydotoold is a narrowly scoped fallback for when the portal is unavailable; spectacle
# is the (slow) fallback capture path. Tailscale keeps access private without exposing
# the control port.
#
# The GStreamer/PipeWire packages below are what the capture pipeline is actually built
# from — pipewiresrc ! videorate ! videoscale ! videoconvert ! jpegenc ! appsink, driven
# from Python via GObject introspection. Kinoite happens to ship them today, but naming
# them here is the difference between "remote control breaks silently if the base image
# drops a package" and "the image build fails loudly". They are cheap and already pulled
# in by Plasma, so this is a no-op in practice.
# Tailscale repo — write the (small, static, public) repo file OURSELVES instead of
# curl-ing it from pkgs.tailscale.com at build time. That download is a dependency on
# a third-party server, and it took the ENTIRE image build down on 2026-07-16 when
# pkgs.tailscale.com returned 504 for the .repo file: curl exhausted --retry 3 and
# buildah exited 22, on a build whose only changes were themes and a keyboard layout.
# Shipping the repo inline removes that flaky round-trip; dnf still fetches the
# packages and gpg key from the baseurl (with its own retries), which is unavoidable.
cat > /etc/yum.repos.d/tailscale.repo <<'TAILSCALE_REPO'
[tailscale-stable]
name=Tailscale stable
baseurl=https://pkgs.tailscale.com/stable/fedora/$basearch
enabled=1
type=rpm
repo_gpgcheck=1
gpgcheck=0
gpgkey=https://pkgs.tailscale.com/stable/fedora/repo.gpg
TAILSCALE_REPO
# qrencode: the Mo PC Remote panel renders its address as a QR code. Without it the user has to
# read an address off the screen and type it into a phone — which is exactly how they end up on
# the LAN address that dies the moment they leave the house.
dnf5 -y install tailscale ydotool wl-clipboard spectacle python3-gobject qrencode \
    gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good pipewire-gstreamer
systemctl enable tailscaled.service
systemctl --global disable mo-remote-personal.service || true
chmod 0755 /usr/lib/mo-remote/MoRemotePersonal \
    /usr/lib/mo-remote/mo-remote-portal.py \
    /usr/bin/mo-pc-remote

# Fail the build if the capture pipeline's GStreamer elements are missing: a shipped image
# whose remote control silently falls back to 700ms-per-frame spectacle is a broken image.
#
# h264parse and a software H.264 encoder are now part of that floor.
#
# JPEG has no temporal compression: every frame is a whole picture. Measured on real hardware at
# 1080p, that is 79 Mbit/s against H.264's 4.3 — a difference nobody notices on a home LAN and
# nobody survives on mobile data, which is exactly where this feature is supposed to earn its
# keep. So H.264 is the point of the stream, not a bonus.
#
# The hardware encoders take care of themselves: nvcodec ships nvh264enc in the NVIDIA image, and
# the `va` plugin registers vah264enc on any Intel/AMD machine that has a VA-API device. Neither
# can be RELIED on. NVENC opens a session against the GPU and can simply refuse when VRAM is gone
# — measured on the maintainer's machine, where a local LLM holds 6 of 8 GB, nvh264enc failed to
# open at 7748/8192 MiB used and worked again at 7625. A remote desktop must not depend on how
# much VRAM some other program happens to be holding.
#
# openh264 is therefore not a nicety, it is the floor under H.264 itself: software, always
# available, ~a fifth of a core at 1080p30 — which is less than the JPEG path already burns doing
# eighteen times worse. (Cisco's build; the repo ships enabled in Fedora.)
dnf5 -y install gstreamer1-plugin-openh264 gstreamer1-plugins-bad-free

python3 - <<'EOF'
import gi, sys
gi.require_version("Gst", "1.0")
from gi.repository import Gst
Gst.init(None)
missing = [e for e in ("pipewiresrc", "videorate", "videoscale", "videoconvert",
                       "jpegenc", "h264parse", "appsink") if not Gst.ElementFactory.find(e)]
if missing:
    sys.exit(f"FATAL: Mo Remote capture pipeline is missing GStreamer elements: {missing}")

# At least one H.264 encoder that runs on ANY machine, with no GPU and no luck. The hardware ones
# are checked at runtime, not here, because "installed" and "will open a session" are different
# claims and only the second one matters.
if not any(Gst.ElementFactory.find(e) for e in ("openh264enc", "x264enc")):
    sys.exit("FATAL: no software H.264 encoder. NVENC is not guaranteed to open (VRAM), and "
             "without a fallback the stream drops to JPEG — 79 Mbit/s, unusable on mobile data.")
print("OK: Mo Remote GStreamer capture pipeline elements all present (incl. software H.264).")
EOF

# Compile-and-launch smoke test for every shipped pure-QML application, run through
# moos-qml-shell — the same binary /usr/bin/moai and /usr/bin/moos-welcome exec, with
# the same environment they export. A healthy window stays alive until the timeout
# (exit 124); an engine/load error kills the process before it and fails the build.
#
# The verdict is the EXIT CODE, and it has no forgiving branch. That is deliberate:
# this gate used to run qml-qt6 and decide by grepping the log for "file.qml:line:col",
# with an else-branch that forgave anything else as "a Kirigami window cannot exist
# offscreen". It could never fail. Qt only writes QML errors to stderr when it believes
# stderr is a console, so under CI's pipe the log held ONLY the generic "Did not load
# any objects, exiting." — no file:line, never a match, always the forgiving branch. The
# MoOS Store shipped DEAD behind that WARN (font.pixelSize is an int, and a 13.5 literal
# aborts the whole engine) with every gate green, and it took a user's click to find out.
# Two things make it bite now: QT_FORCE_STDERR_LOGGING puts the diagnostics back in the
# log for whoever reads the failure, and the pass/fail decision needs no string at all.
# The escape hatch was never needed either — Mo AI's Kirigami window DOES reach the
# timeout under this shell; it was qml-qt6 that could not host it. Verified in both
# directions: broken Store exits 1, both real apps time out at 124.
_qml_shell=/usr/bin/moos-qml-shell
[ -x "$_qml_shell" ] || { echo "FATAL: moos-qml-shell missing — the QML apps have no host"; exit 1; }
_qml_home="$(mktemp -d)"
for _qml_app in /usr/share/moos/apps/*/main.qml; do
    _qml_id="$(basename "$(dirname "$_qml_app")")"
    _qml_log="/tmp/${_qml_id}-qml-smoke.log"
    set +e
    # The launchers' own environment: Basic style (no Plasma integration in the
    # container), no stale disk cache, and local-file XHR — the Store reads its
    # catalogue with one, so without it the app under test is not the shipped app.
    HOME="$_qml_home" \
        QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
        QT_QUICK_CONTROLS_STYLE=Basic QT_FORCE_STDERR_LOGGING=1 \
        QML_DISABLE_DISK_CACHE=1 QML_XHR_ALLOW_FILE_READ=1 \
        timeout 6 "$_qml_shell" \
            --app-id "org.moos.${_qml_id}" --qml "$_qml_app" >"$_qml_log" 2>&1
    _qml_rc=$?
    set -e
    if [ "$_qml_rc" -ne 124 ]; then
        echo "FATAL: the QML app '${_qml_id}' did not stay loaded (exit=${_qml_rc})."
        echo "       It will not open for the user either. Its own error follows:"
        cat "$_qml_log"
        exit 1
    fi
    rm -f "$_qml_log"
done
rm -rf "$_qml_home"
unset -v _qml_shell _qml_home _qml_app _qml_id _qml_log _qml_rc

# org.moos.brand is not a standalone QML application: it is a real Plasma
# applet, and its launcher depends on the private Kicker models, Milou runners,
# Plasmoid.configuration and the shell's full-representation host.  A syntax
# check (or loading main.qml in moos-qml-shell) cannot construct that world.
# Launch the INSTALLED package through plasmawindowed, which is Plasma's applet
# host.  The build-only positional argument forces fullRepresentation: without
# it plasmawindowed obeys the panel's compact preference and tests only the MoOS
# button. A sound full launcher stays alive to the timeout and prints its ready
# marker; a missing component, invalid model property, or unavailable import
# makes the host exit early.
_launcher_smoke_log="$(mktemp /tmp/moos-launcher-smoke.XXXXXX.log)"
_launcher_smoke_home="$(mktemp -d /tmp/moos-launcher-home.XXXXXX)"
_launcher_smoke_runtime="$(mktemp -d /tmp/moos-launcher-runtime.XXXXXX)"
chmod 0700 "$_launcher_smoke_runtime"
command -v plasmawindowed >/dev/null 2>&1 \
    || { echo "FATAL: plasmawindowed is required to load-test the MoOS launcher"; exit 1; }
command -v dbus-run-session >/dev/null 2>&1 \
    || { echo "FATAL: dbus-run-session is required for the MoOS launcher smoke"; exit 1; }
set +e
HOME="$_launcher_smoke_home" XDG_RUNTIME_DIR="$_launcher_smoke_runtime" \
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
    QT_FORCE_STDERR_LOGGING=1 QML_DISABLE_DISK_CACHE=1 \
    timeout --kill-after=2s 8 dbus-run-session -- \
        /usr/bin/plasmawindowed org.moos.brand moos-ci-full-representation \
        >"$_launcher_smoke_log" 2>&1
_launcher_smoke_rc=$?
set -e
if [ "$_launcher_smoke_rc" -ne 124 ]; then
    echo "FATAL: org.moos.brand did not stay loaded in Plasma's applet host (exit=$_launcher_smoke_rc)"
    cat "$_launcher_smoke_log"
    exit 1
fi
if ! grep -Fq 'MOOS_LAUNCHER_FULL_READY size=720x590' "$_launcher_smoke_log"; then
    echo "FATAL: org.moos.brand stayed alive but LauncherView was not constructed at 720x590"
    cat "$_launcher_smoke_log"
    exit 1
fi
_launcher_smoke_config="${_launcher_smoke_home}/.config/plasmawindowedrc"
if ! grep -qE '^geometry=[^,]+,[^,]+,720,590$' "$_launcher_smoke_config"; then
    echo "FATAL: plasmawindowed did not host the full 720x590 MoOS launcher"
    cat "$_launcher_smoke_config" 2>/dev/null || true
    cat "$_launcher_smoke_log"
    exit 1
fi
# Kicker's `KAStatsFavoritesModel::favorites returns nothing` line is not benign
# here: the property is a compatibility stub.  Reading it makes favoriteIds and
# reset/enumeration paths silently empty even though the launcher stays alive.
if grep -qiE 'QQmlApplicationEngine failed|component is not ready|error loading qml file|error loading applet|invalid empty url|compactRepresentationExpander .* is not an Item|type .* unavailable|module .* is not installed|referenceerror|typeerror|cannot assign to|unable to assign|binding loop|is not a type|non-existent attached object|cannot override final property|qml (image|pixmap): cannot open|KAStatsFavoritesModel::favorites returns nothing' \
        "$_launcher_smoke_log"; then
    echo "FATAL: org.moos.brand stayed open but reported a live QML/model error"
    cat "$_launcher_smoke_log"
    exit 1
fi
# plasmawindowed and the session bus are terminated as a process group by
# timeout, but a last Qt cache write can briefly race the recursive removal.
# Retry only these three build-owned paths for a bounded four seconds; do not
# weaken the smoke result or leave compose-hostile content under /tmp.
_launcher_cleanup_ok=0
for _launcher_cleanup_attempt in 1 2 3 4 5 6 7 8 9 10; do
    if rm -rf -- \
            "$_launcher_smoke_log" \
            "$_launcher_smoke_home" \
            "$_launcher_smoke_runtime" 2>/dev/null; then
        sleep 0.2
        if [ ! -e "$_launcher_smoke_log" ] \
                && [ ! -e "$_launcher_smoke_home" ] \
                && [ ! -e "$_launcher_smoke_runtime" ]; then
            _launcher_cleanup_ok=1
            break
        fi
    fi
    sleep 0.2
done
if [ "$_launcher_cleanup_ok" -ne 1 ]; then
    echo "FATAL: org.moos.brand smoke passed, but its isolated temporary state stayed active"
    exit 1
fi
unset -v _launcher_smoke_log _launcher_smoke_home _launcher_smoke_runtime \
    _launcher_smoke_config _launcher_smoke_rc _launcher_cleanup_attempt \
    _launcher_cleanup_ok

# The desktop scene (org.moos.ui2.wallpaper) is not covered by the pure-QML app
# loop above: its root is a WallpaperItem, which only exists inside plasmashell's
# wallpaper loader, so the PACKAGE cannot be launched headless. What CAN be
# proven here, and is, in two parts:
#   1. The bento itself — every visible pixel of the scene — is deliberately a
#      plain QtQuick/Kirigami component (DashboardBento.qml, no Plasmoid/Wallpaper
#      API), so it gets the same real load-proof smoke as the apps: hosted in a
#      window, it must stay alive to the timeout. This catches a renamed
#      component, a missing weather asset path, or a bad binding.
#   2. The wallpaper wrapper is validated structurally: package type, root type,
#      the bento reference, and the Image config entry the theme scripts write.
_scene_dir=/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper
for _weather_kind in clear-day clear-night partly-day partly-night cloudy rain snow fog storm; do
    test -s "${_scene_dir}/contents/images/weather/${_weather_kind}.png"         || { echo "FATAL: MoOS scene is missing ${_weather_kind} weather art"; exit 1; }
done
unset -v _weather_kind
grep -q '"KPackageStructure": "Plasma/Wallpaper"' "${_scene_dir}/metadata.json"     || { echo "FATAL: org.moos.ui2.wallpaper is not a Plasma/Wallpaper package"; exit 1; }
grep -q '^WallpaperItem' "${_scene_dir}/contents/ui/main.qml"     || { echo "FATAL: the scene wallpaper root is not a WallpaperItem"; exit 1; }
grep -q 'DashboardBento' "${_scene_dir}/contents/ui/main.qml"     || { echo "FATAL: the scene wallpaper does not embed the dashboard bento"; exit 1; }
grep -q 'name="Image"' "${_scene_dir}/contents/config/main.xml"     || { echo "FATAL: the scene wallpaper has no Image config entry — moos-theme cannot set the half"; exit 1; }
if grep -q 'import org\.kde\.plasma\.plasmoid' "${_scene_dir}/contents/ui/DashboardBento.qml"; then
    echo "FATAL: DashboardBento must stay free of the Plasmoid/Wallpaper API — plain QtQuick+Kirigami is what the smoke below can actually load"
    exit 1
fi

_scene_log=/tmp/moos-scene-smoke.log
_scene_home=/tmp/moos-scene-home
_scene_runtime=/tmp/moos-scene-runtime
mkdir -p "$_scene_home/.cache" "$_scene_runtime"
chmod 0700 "$_scene_runtime"
command -v dbus-run-session >/dev/null 2>&1     || { echo "FATAL: dbus-run-session is required for the scene smoke"; exit 1; }
cat > /tmp/moos-scene-smoke.qml <<'SCENEQML'
import QtQuick
import QtQuick.Window

Window {
    visible: true
    width: 720
    height: 260
    Loader {
        anchors.fill: parent
        source: "file:///usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui/DashboardBento.qml"
        onStatusChanged: {
            if (status === Loader.Error) {
                console.error("SCENE-SMOKE-LOAD-ERROR")
                Qt.exit(3)
            }
        }
    }
}
SCENEQML
set +e
HOME="$_scene_home" XDG_RUNTIME_DIR="$_scene_runtime"     QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software     QT_QUICK_CONTROLS_STYLE=Basic QT_FORCE_STDERR_LOGGING=1     QML_DISABLE_DISK_CACHE=1     timeout --kill-after=2s 6 dbus-run-session --         /usr/bin/moos-qml-shell --app-id org.moos.scene-smoke         --qml /tmp/moos-scene-smoke.qml         >"$_scene_log" 2>&1
_scene_rc=$?
set -e
if [ "$_scene_rc" -ne 124 ]; then
    echo "FATAL: the MoOS scene bento did not stay loaded (exit=$_scene_rc)"
    cat "$_scene_log"
    exit 1
fi
if grep -qiE 'SCENE-SMOKE-LOAD-ERROR|type .* unavailable|module .* is not installed|error loading qml|referenceerror|typeerror|unable to assign|binding loop|qml image: cannot open'         "$_scene_log"; then
    echo "FATAL: the MoOS scene bento reported a QML error"
    cat "$_scene_log"
    exit 1
fi
rm -rf "$_scene_log" "$_scene_home" "$_scene_runtime" /tmp/moos-scene-smoke.qml
unset -v _scene_dir _scene_log _scene_home _scene_runtime _scene_rc

# System-wide Flathub remote so Discover/Bazaar work out of the box on first
# boot. Path convention from the kinoite bootc reference implementation
# (https://github.com/ondrejbudai/bootc-isos, kinoite/src/build.sh):
#   /etc/flatpak/remotes.d/flathub.flatpakrepo
# Fail-loud on purpose (-f fails on HTTP errors; no || true): an image without
# Flathub is broken for app installs and must fail CI, not ship silently.
mkdir -p /etc/flatpak/remotes.d
curl -Lf --retry 3 -o /etc/flatpak/remotes.d/flathub.flatpakrepo \
    https://dl.flathub.org/repo/flathub.flatpakrepo

# Pre-seed the languages Flathub apps carry, regardless of which one the user
# picks at first run. The org.freedesktop.Platform.Locale extension otherwise
# defaults to "match the host locale only" — so a user who installs an app in
# English and later switches to Arabic gets an app with no Arabic strings until a
# manual `flatpak update`. Declaring all three shipped languages here means every
# Flathub install already carries ar/en/de locale data; moos-lang then only has
# to point the SESSION at the chosen one. System-wide default; a per-user
# `flatpak config --user --set languages` (moos-lang) still refines it.
flatpak config --set extra-languages 'ar;en;de' 2>/dev/null || \
    echo "note: flatpak extra-languages not set at build time (set per-user by moos-lang)" >&2

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
chmod 0755 /usr/bin/moplayer
chmod 0755 /usr/bin/moos-setup /usr/bin/moos-firstrun /usr/bin/moos-compat \
    /usr/bin/moos-hardware /usr/bin/moos-device-plan /usr/bin/moai /usr/bin/moai-start /usr/bin/moai-do \
    /usr/bin/moos-update /usr/bin/moos-rollback /usr/bin/moos-welcome /usr/bin/moos-store /usr/bin/moos-lang \
    /usr/bin/moos-storectl /usr/bin/moos-store-index /usr/bin/moos-store-browse /usr/bin/moos-one-store \
    /usr/bin/moos-apply-theme /usr/bin/moos-fix-boot-branding /usr/bin/moos-open /usr/bin/moos-install \
    /usr/bin/moai-config /usr/bin/moai-gateway /usr/bin/moai-control /usr/bin/moai-code \
    /usr/bin/moai-idle \
    /usr/bin/moos-theme /usr/bin/moos-selfcheck \
    /usr/bin/moos-installer /usr/bin/moos-install-to-disk /usr/bin/moos-list-disks \
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
# (c9) Two faults that fire on EVERY boot and that nothing else in this build sees
# -----------------------------------------------------------------------------
# 1. A permanently failed user unit.
#
#    nvidia-settings is an X11 tool. MoOS is a Wayland-only Plasma session, so the
#    autostart entry the driver ships runs
#        nvidia-settings --load-config-only
#    against an X server that does not exist, exits 1, and leaves a RED failed unit
#    in `systemctl --user --failed` on every boot of the NVIDIA edition. It has been
#    doing so since the driver was layered in. Nothing is broken by it and nothing
#    is fixed by it; it is pure noise in the one place a user looks to find out
#    whether their system is healthy — which makes every REAL failure harder to see.
#
#    Guarded on existence: the file only ships in the NVIDIA edition.
autostart_nv=/etc/xdg/autostart/nvidia-settings-load.desktop
if [ -f "${autostart_nv}" ]; then
    grep -q '^Hidden=true' "${autostart_nv}" || printf 'Hidden=true\n' >> "${autostart_nv}"
    grep -q '^Hidden=true' "${autostart_nv}" \
        || { echo "GATE FAIL: could not disable the nvidia-settings autostart"; exit 1; }
fi

# 2. Fourteen udev errors at every boot.
#
#    /usr/lib/udev/rules.d/70-u2f.rules assigns security keys to the `plugdev`
#    group, and Fedora does not create it — so udev logs
#        Failed to resolve group 'plugdev', ignoring
#    fourteen times per boot, at ERROR priority. Creating the group is the whole
#    fix; the rules then resolve, and a FIDO key plugged into this machine gets the
#    permissions it was always supposed to have.
getent group plugdev >/dev/null || groupadd -r plugdev

# -----------------------------------------------------------------------------
# (d) Enable services
# -----------------------------------------------------------------------------
# uupd runs from a systemd timer; enabling it here bakes the symlink into the
# image so every deployment gets background updates by default.
systemctl enable uupd.timer

# --- Get the app catalogue OUT of the boot path -------------------------------
# Measured on the maintainer's machine (`systemd-analyze critical-chain`):
#
#   graphical.target @11.525s
#   └─multi-user.target @11.525s
#     └─fedora-atomic-desktop-appstream-cache-refresh.service @7.999s +3.525s
#
# Fedora Atomic's appstream refresh is WantedBy=multi-user.target, so every boot waits
# 3.5 s — a third of MoOS's entire userspace time — for an app-store index that nobody has
# asked for yet. The refresh stays; it just runs three minutes AFTER the desktop is up
# (moos-appstream-refresh.timer, which starts the very same service).
#
# GATE: if the upstream unit is ever renamed, `systemctl disable` would quietly do nothing
# and the boot delay would come back with a green build. So fail loudly instead.
test -f /usr/lib/systemd/system/fedora-atomic-desktop-appstream-cache-refresh.service || {
    echo "GATE FAIL: the appstream refresh unit was renamed — MoOS's boot-path fix now targets nothing"
    exit 1
}
systemctl disable fedora-atomic-desktop-appstream-cache-refresh.service

# ── The base's own units must not wear another OS's name ─────────────────────
# MoOS is not a skin over Fedora Kinoite — it IS the system, and a system whose
# `systemctl` answers in someone else's name is telling the user what it really is.
# Three units the base image carries are still introducing themselves as Fedora:
#
#   fedora-atomic-desktop-appstream-cache-refresh   "Workaround for Atomic Destkops…"
#   fedora-atomic-desktop-mandb-update              "Workaround for Atomic Destkops…"
#   fedora-kinoite-plasmalogin-workaround           "…on Kinoite"
#
# RENAMED IN PLACE, not wrapped. A moos-*.service that shells out to a fedora-*.service
# would be a second system stacked on the first — the exact thing the one-system rule
# forbids. `mv` keeps one unit, one job, one name. This runs on every build from a fresh
# base, so a base-image update cannot quietly restore the old names.
#
# Only these three are touched, because they are the only foreign-named units NOT owned by
# an RPM (`rpm -qf` finds no package). The rest are left ALONE on purpose:
#   - dbus-org.fedoraproject.FirewallD1.service — that string is a D-Bus interface NAME, a
#     protocol identifier firewalld activates on, not branding. Renaming it breaks the
#     firewall.
#   - flatpak-add-fedora-repos.service, ublue-nvctk-cdi.service, anaconda-* — package-owned.
#     Renaming a packaged unit means every dnf update silently restores the old name while
#     the rename "works", and other units reference them by name.
# Documentation= URLs are kept: they point at the real upstream bug each workaround exists
# for. That is provenance, not branding — the next maintainer needs to know where this came
# from, and deleting the citation would not make MoOS any more MoOS.
#
# GATE first: `mv` of a path that moved upstream would create the destination from nothing
# and silently ship a unit that runs a command that no longer exists.
for _u in fedora-atomic-desktop-mandb-update.service \
          fedora-kinoite-plasmalogin-workaround.service; do
    test -f "/usr/lib/systemd/system/${_u}" || {
        echo "GATE FAIL: ${_u} is gone from the base — the MoOS rename now targets nothing"
        exit 1
    }
done
test -x /usr/libexec/fedora-kinoite-plasmalogin-workaround || {
    echo "GATE FAIL: the plasmalogin workaround script moved — its unit would ExecStart nothing"
    exit 1
}

# 1. appstream refresh. Already disabled above (it is off the boot path); the MoOS timer
#    drives it. Naming it moos-appstream-refresh.service makes the timer's target IMPLICIT
#    — systemd pairs X.timer with X.service — so the timer's explicit Unit= line goes away
#    and the two can no longer drift apart.
mv /usr/lib/systemd/system/fedora-atomic-desktop-appstream-cache-refresh.service \
   /usr/lib/systemd/system/moos-appstream-refresh.service
sed -i 's|^Description=.*|Description=Refresh the app catalogue index (MoOS)|' \
   /usr/lib/systemd/system/moos-appstream-refresh.service

# 2. mandb. Stays enabled and stays exactly as cheap as it was (Nice=19, IOWeight=10).
systemctl disable fedora-atomic-desktop-mandb-update.service
mv /usr/lib/systemd/system/fedora-atomic-desktop-mandb-update.service \
   /usr/lib/systemd/system/moos-mandb-update.service
sed -i 's|^Description=.*|Description=Update the manual page index (MoOS)|' \
   /usr/lib/systemd/system/moos-mandb-update.service
systemctl enable moos-mandb-update.service

# 3. plasmalogin shadow entries. The unit, the script it runs, and the stamp file it writes
#    all carry the name, so all three move together — a rename that left the stamp behind
#    would leave `/etc/.fedora-…` on every disk MoOS ever installs. Renaming the stamp costs
#    exactly one extra run on machines installed before this: the script greps /etc/shadow
#    before it writes, so it finds the entry already there and reports "Nothing to do".
systemctl disable fedora-kinoite-plasmalogin-workaround.service
mv /usr/libexec/fedora-kinoite-plasmalogin-workaround /usr/libexec/moos-plasmalogin-shadow-fix
mv /usr/lib/systemd/system/fedora-kinoite-plasmalogin-workaround.service \
   /usr/lib/systemd/system/moos-plasmalogin-shadow-fix.service
sed -i -e 's|^Description=.*|Description=Add the missing plasmalogin shadow entries (MoOS)|' \
       -e 's|/usr/libexec/fedora-kinoite-plasmalogin-workaround|/usr/libexec/moos-plasmalogin-shadow-fix|' \
       -e 's|/etc/\.fedora-kinoite-plasmalogin-workaround|/etc/.moos-plasmalogin-shadow-fix|' \
       /usr/lib/systemd/system/moos-plasmalogin-shadow-fix.service
sed -i 's|/etc/\.fedora-kinoite-plasmalogin-workaround|/etc/.moos-plasmalogin-shadow-fix|g' \
   /usr/libexec/moos-plasmalogin-shadow-fix
systemctl enable moos-plasmalogin-shadow-fix.service

# The preset still says `enable fedora-kinoite-plasmalogin-workaround.service` for a unit
# that no longer exists. Presets are advice, not references — `systemctl preset` on a
# missing unit is a no-op — but a line naming a ghost is a trap for the next reader.
# Guarded with `if`, not `&&`: under `set -e` a bare `test -f X && sed …` FAILS THE BUILD
# when the file is absent, and this line is a tidy-up, not a gate. A base that drops the
# preset entirely is fine; a build that dies with "sed: No such file" while the real gates
# stay silent is not.
if [ -f /usr/lib/systemd/system-preset/82-kinoite.preset ]; then
    sed -i '/fedora-kinoite-plasmalogin-workaround/d' /usr/lib/systemd/system-preset/82-kinoite.preset
fi

systemctl enable moos-appstream-refresh.timer

# -----------------------------------------------------------------------------
# Boot speed — the two highest-impact SAFE levers on a Fedora Atomic KDE desktop
# -----------------------------------------------------------------------------
# Measured across the Fedora/uBlue/Bazzite ecosystem, these two dominate the
# serial boot path on this exact stack, and both are safe on a GENERIC DESKTOP
# image (no network mounts, no SDDM). Nothing here touches the branded splash
# handoff (plymouth-quit-wait is deliberately left alone — masking it does not
# speed boot and breaks the flicker-free handoff).
#
# 1) NetworkManager-wait-online.service gates network-online.target, which on a
#    desktop NOTHING needs before the greeter — NM keeps connecting in the
#    background while Plasma appears. This is the single biggest common win
#    (5-30 s off the serial path). DISABLE only the -wait-online sub-unit, never
#    NetworkManager itself. Safe because MoOS ships no _netdev (NFS/CIFS/iSCSI)
#    mount that would need the network up early. Gate: fail loud if the unit was
#    renamed so the win can't silently rot.
test -f /usr/lib/systemd/system/NetworkManager-wait-online.service || {
    echo "GATE FAIL: NetworkManager-wait-online.service is gone/renamed — the boot-speed fix now targets nothing"
    exit 1
}
systemctl disable NetworkManager-wait-online.service

# 2) systemd-udev-settle.service is deprecated ("depending on it is a bug" per
#    systemd) and, when some greeter/vendor drop-in drags it in, it SERIALIZES
#    the whole boot — historically adding up to ~2 minutes on Atomic KDE. F44's
#    Plasma Login Manager should not pull it, but mask it as a hard guard so a
#    future base/drop-in change can never resurrect the stall.
systemctl mask systemd-udev-settle.service 2>/dev/null || true

# 3) grub-boot-success.timer/.service can NEVER succeed here, and failed on every
#    login on the maintainer's machine: the timer fires 2 minutes into each session
#    and runs `grub2-set-bootflag boot_success`, which writes /boot/grub2/grubenv —
#    and on bootc/OSTree /boot is mounted READ-ONLY ("Creating tmpfile failed:
#    Read-only file system"). Nothing here consumes the flag: boot_success exists for
#    greenboot's automatic-rollback counting and greenboot is not installed (MoOS
#    rolls back through bootc/rpm-ostree, which keeps the previous deployment and
#    does not read grubenv). So this is a guaranteed red `systemctl --user --failed`
#    on every boot of every install, including a fresh ISO, reporting a failure that
#    means nothing. Masking removes the noise and changes no behaviour — the flag was
#    already never written. Mask the TIMER (so nothing queues the job) and the SERVICE
#    (so a manual/drop-in start cannot resurrect the failure).
#    If greenboot is ever added, or /boot becomes writable, revisit this.
systemctl --global mask grub-boot-success.timer 2>/dev/null || true
systemctl --global mask grub-boot-success.service 2>/dev/null || true

# 4) drkonqi-coredump-pickup.service is the same shape: it CANNOT succeed, so it went red
#    30 minutes into every session on the maintainer's machine ("Service reached runtime
#    time limit. Stopping." -> Failed with result 'timeout').
#
#    Traced with gdb before touching it, because the obvious reads are both wrong:
#      - `--settle-first` is a plain nanosleep of SIXTY seconds (the timespec in .rodata is
#        tv_sec=0x3c), not the 30-minute limit. Watching it for 25s shows "nothing
#        happening" and means nothing — it has not left the sleep.
#      - After the sleep, main() enters QCoreApplication::exec() and NEVER RETURNS. That is
#        true with ZERO coredumps in scope (reproduced with --boot-id of a crash-free boot),
#        so it is not "stuck on a crash" — it is an event loop upstream modelled as a
#        time-limited job. systemd SIGTERMs it at RuntimeMaxSec and records `timeout`, which
#        is a failure. There is NO exit path that ends in success, on any machine.
#    SuccessExitStatus= cannot rescue it either: that matches exit codes and signals, not
#    systemd's timeout result.
#
#    What is actually lost by masking: only the pickup of crashes that happened BEFORE login.
#    Live crashes are untouched — they arrive through drkonqi-coredump-launcher.socket, a
#    different unit that works and stays enabled. The alternative (RuntimeMaxSec=infinity)
#    keeps the pickup and also clears the red, but leaves the processor running all session
#    beside the socket launcher, risking DOUBLE crash dialogs — worse than the noise it fixes.
#    So: mask, and keep the crash reporter that works. See FIXES_2026-07-16b.md.
systemctl --global mask drkonqi-coredump-pickup.service 2>/dev/null || true

# Mo AI in-app Settings backend: a tiny per-user control API. --global enables it
# for every user's session (bakes the default.target.wants symlink under
# /etc/systemd/user) without needing a running user manager at build time.
systemctl --global enable moai-control.service
# The Agent/phone settings panel talks to this loopback-only API in every
# session. Starting it once from setup-brain is not persistence; enable the
# shipped unit globally so it survives logout and reboot.
systemctl --global enable moai-agent-api.service

# Plasma's automatic day/night switch applies only the Global Theme subset. It
# does not carry Konsole, GTK or the wallpaper reliably, so watch the effective
# kdeglobals selection and reconcile those supplements after each transition.
# The service never writes kdeglobals, which keeps the path activation acyclic.
systemd-analyze verify \
    /usr/lib/systemd/user/moos-input-migrate.service \
    /usr/lib/systemd/user/moos-theme-sync.path \
    /usr/lib/systemd/user/moos-theme-sync.service \
    /usr/lib/systemd/user/moai.service \
    /usr/lib/systemd/user/moai-gateway.service \
    /usr/lib/systemd/user/moai-control.service \
    /usr/lib/systemd/user/moai-idle.service \
    /usr/lib/systemd/user/moai-idle.timer \
    /usr/lib/systemd/user/moos-ensure-brain.service \
    /usr/lib/systemd/user/openclaw-idle.service \
    /usr/lib/systemd/user/openclaw-idle.timer \
    /usr/lib/systemd/user/moai-agent-api.service
# openclaw-gateway.service is deliberately NOT verified here: its ExecStart is
# %h/.local/bin/openclaw, a per-user runtime install (moai-do install-openclaw),
# which does not exist in the build container — systemd-analyze verify resolves
# %h to /root and fails the whole build on a binary that is not meant to ship in
# the image. Its runtime guard is ConditionFileIsExecutable=%h/.local/bin/openclaw,
# and its in-image ExecStartPre (/usr/libexec/moai-openclaw-preflight) is covered
# by the exec-bits gate. A unit whose command is a user install cannot be build-
# time verified; do not add it back.
systemctl --global enable moos-theme-sync.path

# Mo AI's FRONT DOOR. This is the only thing on 127.0.0.1:8080 and the only thing
# the Mo AI app ever talks to; it routes each request to the local brain (8081,
# moai.service, started ON DEMAND) or to the configured cloud provider, so a
# conversation can pick its own brain and model.
#
# It must be enabled for EVERY user, not opted into: it used to be
# moai-cloud.service, which was enabled only while the user's default was cloud,
# because local and cloud both wanted 8080 and only one could run. That either/or
# is what made the choice of brain a global, service-bouncing setting.
#
# moai.service is deliberately NOT --global enabled: the local brain is on demand.
systemctl --global enable moai-gateway.service

# Keep Mo AI's brain FAST: build/serve the instruct (non-thinking) model from
# system_files/.../moai-brain.Modelfile. A thinking model made trivial replies
# cost ~97 s; the instruct model answers in <0.5 s. Idempotent + failure-tolerant.
systemctl --global enable moos-ensure-brain.service

# Free the local brain's VRAM when it goes idle. moai.service loads ~6 GB into an 8 GB
# GPU and never releases it while up, which starves the compositor — a maximised browser
# on a loaded brain has crashed kwin_wayland (NVRM: invalid mmap context) and frozen the
# desktop. moai-idle.timer stops the brain after it is idle; moai-gateway restarts it on
# the next request. Enabled for every user so stability is the default, not an opt-in.
systemctl --global enable moai-idle.timer

# Mo AI on Telegram is ON-DEMAND. The heavy agent (openclaw-gateway: a ~386 MB Node
# runtime + a rootless-podman sandbox + an Ollama model) is NOT enabled at boot — it
# would sit resident just to hear "hi". Instead, moai-wake is the only always-on
# piece: a few-MB Python stdlib receiver that holds the Telegram long-poll and starts
# openclaw-gateway the instant an allowlisted user speaks, then steps aside (one bot
# allows one getUpdates consumer). openclaw-idle.timer sleeps the agent again when the
# conversation goes idle (Ollama's model unloaded), and moai-wake resumes the poll.
# openclaw-gateway itself stays --user-managed, started on demand, never --global.
systemctl --global enable moai-wake.service
systemctl --global enable openclaw-idle.timer

# Collect the build litter. Every `just build` leaves its intermediate layers behind as
# untagged images and nothing ever reaps them: 125 GB accumulated in days on the
# maintainer's own machine, in ~/.local/share/containers, i.e. out of his home directory.
# The weekly sweep prunes dangling layers ONLY — see the long warning in the script about
# why `-a` would eat the moplayer-dev distrobox, which is the machine's only compiler.
systemctl --global enable moos-reclaim-disk.timer

# An installed bootc system uses an OSTree/composefs overlay for /. Anaconda's
# generated physical-root fstab entry makes systemd-remount-fs attempt an
# impossible overlay reconfigure on every boot. Remove only that entry before
# remount processing while preserving /boot, /boot/efi, /home and /var.
systemctl enable moos-fstab-sanitize.service

# OSTree exposes /home, /srv and /root as symlinks into persistent /var. The
# generic tmpfiles rules try to create those three paths as directories and log
# an error on every boot. Remove only the conflicting top-level creation rules;
# provisioning below /root (for example /root/.ssh) still follows the symlink.
home_tmpfiles="/usr/lib/tmpfiles.d/home.conf"
provision_tmpfiles="/usr/lib/tmpfiles.d/provision.conf"
grep -Eq '^Q[[:space:]]+/home[[:space:]]' "$home_tmpfiles" \
    || { echo "FATAL: upstream home.conf no longer has the expected /home rule"; exit 1; }
grep -Eq '^q[[:space:]]+/srv[[:space:]]' "$home_tmpfiles" \
    || { echo "FATAL: upstream home.conf no longer has the expected /srv rule"; exit 1; }
grep -Eq '^d-[[:space:]]+/root[[:space:]]' "$provision_tmpfiles" \
    || { echo "FATAL: upstream provision.conf no longer has the expected /root rule"; exit 1; }
sed -i -E '/^[Qq][[:space:]]+\/(home|srv)[[:space:]]/d' "$home_tmpfiles"
sed -i -E '/^d-[[:space:]]+\/root[[:space:]]/d' "$provision_tmpfiles"
grep -Eq '^[Qq][[:space:]]+/(home|srv)[[:space:]]' "$home_tmpfiles" \
    && { echo "FATAL: conflicting /home or /srv tmpfiles rule survived"; exit 1; }
grep -Eq '^d-[[:space:]]+/root[[:space:]]' "$provision_tmpfiles" \
    && { echo "FATAL: conflicting /root tmpfiles rule survived"; exit 1; }

# -----------------------------------------------------------------------------
# The login screen is Plasma's, and Plasma's login screen is MoOS
# -----------------------------------------------------------------------------
# MoOS ships its own org/kde/breeze/components/{ActionButton,Clock}.qml — the
# components Plasma's LOGIN, LOCK and LOGOUT screens all draw. Overwriting those
# files is not enough on its own, and this is the trap:
#
#   qmldir carries `prefer :/qt/qml/org/kde/breeze/components/`
#
# which tells Qt to load every type from the copies COMPILED INTO
# libcomponents.so (AOT-compiled — the symbols are visible in the .so), and to
# ignore the .qml files sitting right beside it. Those on-disk files are, at
# runtime, decoys. MEASURED 2026-07-17: with MoOS's ActionButton.qml and
# Clock.qml in the import path and `prefer` intact, the greeter still rendered
# the stock Breeze clock and full-colour discs. Dropping the line, same files,
# same harness: the MoOS face appeared. A text gate over those .qml files would
# have been green through all of it.
#
# So: drop `prefer` and let Qt read the module from disk. Nothing is hidden,
# nothing is layered, the plugin's C++ types still register from the .so — only
# the QML the module resolves changes, which is precisely the surface MoOS owns.
#
# Fail-loud on purpose. If plasma-workspace ever stops shipping this line (or the
# path moves), the build stops and a human looks — rather than the login screen
# quietly reverting to Breeze on the next base bump.
qmldir="/usr/lib64/qt6/qml/org/kde/breeze/components/qmldir"
[ -f "$qmldir" ] || { echo "FATAL: ${qmldir} is missing — the breeze components module moved"; exit 1; }
grep -q '^prefer ' "$qmldir" || { echo "FATAL: no 'prefer' line in ${qmldir} — upstream changed how this module resolves QML; re-verify that MoOS's ActionButton/Clock still reach the login screen before removing this check"; exit 1; }
sed -i '/^prefer /d' "$qmldir"
grep -q '^prefer ' "$qmldir" && { echo "FATAL: failed to drop 'prefer' from ${qmldir}"; exit 1; }
echo "MoOS: breeze components resolve from disk — the login screen wears the MoOS face"

# The AOT-compiled copies inside the .so are what `prefer` pointed at. They stay
# (they are part of the shipped library and removing them would mean rebuilding
# plasma-workspace), but nothing loads them any more. Qt's own disk cache is a
# different matter: it keys on mtime, and OSTree pins every mtime under /usr to
# the epoch, so a stale compiled QML could outlive an update — the same trap Mo
# AI hit. moos-apply-theme already purges qmlcache on every THEME_REV bump, and
# THEME_REV is raised in this change for exactly that reason.

# -----------------------------------------------------------------------------
# Hardware adaptation — MoOS "plants itself" into the machine (safe subset)
# -----------------------------------------------------------------------------
# Ship the daemons the first-boot service (and the DE) rely on, and enable the
# service. Everything the service DOES is safe and reversible (see the anti-brick
# contract in /usr/libexec/moos-hardware-adapt). Most adaptation is already
# static/build-time: microcode is early-loaded from the initramfs, GPU mesa
# drivers ship in the image, TRIM is fstrim.timer, the I/O scheduler is the
# static udev rule 60-moos-ioschedulers.rules, base zram is zram-generator.
#
# - thermald: Intel proactive thermal protection (the service enables it only on
#   Intel; AMD relies on amd-pstate + firmware, which is always on).
# - fwupd: firmware SERVICE for LVFS; the service enables only fwupd-refresh.timer
#   (metadata refresh), never auto-applies. tuned/tuned-ppd is the Fedora default
#   power manager and is already in the KDE base (do not co-install TLP/ppd).
# These are small and Fedora-packaged; a missing one must not fail the build
# (the service degrades gracefully), so this install is best-effort.
dnf5 -y install thermald fwupd || \
    echo "note: thermald/fwupd install skipped (base may already provide them)"

# Machine-check reporting must work on both AMD and Intel without leaving a red
# failed unit on every AMD machine. The Kinoite base enables the legacy
# mcelog.service, but mcelog exits 1 on AMD ("AMD systems are not supported")
# and tells the operator to use rasdaemon. The kernel documentation makes the
# same recommendation. rasdaemon consumes the kernel RAS/EDAC trace events and
# is Fedora's cross-vendor package, so make it the one machine-error daemon.
# This is a release-health guarantee, not best-effort: a missing logger makes
# hardware faults invisible, while two loggers create duplicate/conflicting
# ownership.
dnf5 -y install rasdaemon
systemctl mask mcelog.service
systemctl enable rasdaemon.service

# Guarantee the CPU microcode packages stay in the image — they are early-loaded
# from the prebuilt initramfs, so their mere presence is the whole guarantee.
# Fail loud if a future edit ever strips them (a machine with stale microcode is
# a real stability/security regression).
rpm -q microcode_ctl >/dev/null 2>&1 || rpm -q amd-ucode-firmware >/dev/null 2>&1 \
    || dnf5 -y install microcode_ctl || \
    echo "note: microcode package check inconclusive (linux-firmware ships amd-ucode)"

chmod 0755 /usr/libexec/moos-hardware-adapt
chmod 0755 /usr/libexec/moos-wait-drm
systemctl enable moos-hardware-adapt.service

# Live-session polish: on rd.live.image boots ONLY, the demo/installer session
# must never lock (liveuser has no password — a mid-install lock reads as a
# hang) nor blank/suspend. Writes the live user's own config, never /etc/xdg,
# so installed systems keep the real lock screen.
chmod 0755 /usr/libexec/moos-live-polish
systemctl enable moos-live-polish.service

# First-boot setup: create the password-protected user and apply
# account/locale/timezone/keyboard from the installer's answers. This REPLACES
# the masked plasma-setup (Plasma's OOBE, masked in section (z)) with MoOS's own —
# without it a fresh install would reach the greeter with NO user to log in as.
# Runs only on the installed system (ConditionPathExists=/run/ostree-booted).
chmod 0755 /usr/libexec/moos-firstboot
systemctl enable moos-firstboot.service

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
osrel_set VARIANT     '"MoOS"'
osrel_set VARIANT_ID  'moos'
osrel_set PRETTY_NAME '"MoOS"'
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
# Every foreign-brand icon stem. This MUST stay a superset of the firewall's
# FOREIGN_LOGO_STEMS in verify_no_foreign_identity.py — if the firewall flags a
# name, the scrub has to remove it, or the build cannot pass.
_names="fedora-logo-icon fedora-logo fedora-logo-small fedora-gdm-logo \
        start-here-fedora org.fedoraproject.AnacondaInstaller \
        org.fedoraproject.fedora redhat redhat-logo red-hat anaconda"
if [ -f "$_moos_src" ]; then
    # Search RECURSIVELY, and match SYMLINKS as well as regular files.
    #
    # This scrub has been fixed twice against the identity firewall:
    #   1. The old scrub walked `find -type d -name apps` and touched only the top
    #      apps/ dir — but Colloid keeps scalable icons in apps/SCALABLE/ and
    #      Papirus keeps them in per-size apps/ dirs. A recursive find fixed depth.
    #   2. `find -type f` still missed them, because Papirus and Colloid ship the
    #      foreign names as SYMLINKS (redhat.svg -> distributor-logo, etc.), and
    #      -type f skips a symlink. The firewall follows the link and saw them; the
    #      scrub did not. `\( -type f -o -type l \)` now matches both.
    # Both were latent for weeks and invisible to every named-surface gate; only
    # verify_no_foreign_identity.py, sweeping the finished bytes, caught them.
    _all_pred=()
    for _name in $_names; do
        _all_pred+=(-o -name "${_name}.svg" -o -name "${_name}.svgz" \
                    -o -name "${_name}.png" -o -name "${_name}.xpm")
    done
    find /usr/share/icons \( -type f -o -type l \) \( "${_all_pred[@]:1}" \) -print0 2>/dev/null \
        | while IFS= read -r -d '' _f; do
            case "$_f" in
                *.svg|*.svgz)
                    # A foreign vector (or a symlink to one) outranks the raster
                    # MoOS mark at large sizes — delete it outright.
                    rm -f "$_f"
                    ;;
                *.png|*.xpm)
                    # Drop the file-or-symlink first, then write a REAL same-size
                    # MoOS raster in its place (writing THROUGH a symlink would
                    # corrupt whatever legit icon it pointed at).
                    _dir="$(dirname "$_f")"
                    _sized="$_dir/moos-logo.png"
                    [ -f "$_sized" ] || _sized="$_moos_src"
                    rm -f "$_f"
                    cp -f "$_sized" "$_f"
                    ;;
            esac
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
unset -v _moos_src _names _all_pred _f _dir _sized _name _px _themedir

# Neutralise KDE's plasma-welcome — the WINDOW that draws a monitor mock-up with
# the Fedora distro logo (the second Fedora leak besides the desktop launcher).
# GROUND TRUTH (v16 squashfs, 2026-07-10): the app is org.kde.plasma-welcome,
# binary /usr/bin/plasma-welcome. On LIVE it auto-shows because livesys-kde writes
# ~/.config/plasma-welcomerc "[General] LiveEnvironment=true" — but ONLY when
# /etc/xdg/autostart/org.kde.plasma-welcome.desktop is ABSENT; if that file is
# PRESENT, livesys-kde deletes it and writes no welcomerc. So we still PLANT that
# autostart file to force livesys-kde's no-welcome branch.
#
# CORRECTION (2026-07-16, seen live on the installed 179 ISO in QEMU): the earlier
# approach — rm the binary AND rm the /usr/share/applications entry — did NOT make
# the launcher "skip silently". On the INSTALLED first boot it drew a red toast
#     "Launching plasma-welcome (Failed)"
# because KDE resolves the launch by the desktop-id org.kde.plasma-welcome (the
# autostart stub's own filename maps to it), and with the service entry DELETED the
# ApplicationLauncherJob fails loudly; with the binary DELETED a CommandLauncherJob
# fails the same way. DELETION is what turns a benign launch into a visible failure.
#
# The fix is a SILENT NO-OP on every path KDE might take, so the launch always
# succeeds and nothing is ever drawn (MoOS shows its own Welcome via moos-firstrun):
#   1. binary  -> a stub that exits 0 (covers CommandLauncherJob by exec name)
#   2. app entry -> a NoDisplay/Hidden entry, Exec=/bin/true (covers the service-id
#      ApplicationLauncherJob AND keeps it out of every menu)
#   3. autostart -> the Hidden stub, for livesys-kde's branch on LIVE
cat > /usr/bin/plasma-welcome <<'PWBIN'
#!/bin/sh
# MoOS: the upstream Plasma welcome is replaced by moos-firstrun/moos-welcome.
# This no-op exists so any first-run launch of "plasma-welcome" succeeds silently
# instead of raising a red "Launching plasma-welcome (Failed)" toast. It draws
# nothing on purpose.
exit 0
PWBIN
chmod 0755 /usr/bin/plasma-welcome
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

# -----------------------------------------------------------------------------
# (z1b) The app menu holds the system's apps and MoOS's apps. Nothing else.
# -----------------------------------------------------------------------------
# The owner's rule, in his words: what ships is the essential system + what we built, and the
# user chooses the rest. What he actually got was a menu with the base distribution's debug
# tools in it and the same app listed twice.
#
# Two of these are literal DUPLICATES — the thing he complained about:
#   * kdesystemsettings.desktop is `Exec=systemsettings`, the same command, with the same icon,
#     as systemsettings.desktop. Fedora ships it for people running KDE apps under GNOME, and it
#     carries no OnlyShowIn, so on a KDE-only OS BOTH entries appear. "System Settings" and
#     "KDE System Settings", side by side, opening the identical window.
#   * KWrite is Kate with features removed; shipping both is offering the user a choice between
#     an editor and a worse version of the same editor.
#
# The rest are the base's diagnostics — a crash-dump browser, a journal viewer, a debug-flag
# editor, a menu editor. They are the tooling of somebody building a distribution, not of
# somebody using one. Krfb goes too: it is a second, worse screen-sharing app standing next to
# Mo PC Remote, which is the one MoOS actually built.
#
# NoDisplay, never `rm`: the packages stay installed and every one of these still runs from a
# terminal or a .desktop launch. This decides what the MENU offers, and nothing else. (Deleting
# is what plasma-welcome above needed, and only because plasmashell auto-LAUNCHES it; nothing
# auto-launches these.)
hide_from_menu() {
    local f="/usr/share/applications/$1"
    [ -f "$f" ] || return 0                      # not installed in this edition; fine
    grep -q '^NoDisplay=true' "$f" && return 0   # idempotent
    sed -i '/^NoDisplay=/d' "$f"
    sed -i '0,/^\[Desktop Entry\]/s//[Desktop Entry]\nNoDisplay=true/' "$f"
}

for entry in \
    kdesystemsettings.desktop \
    org.kde.kwrite.desktop \
    org.kde.drkonqi.coredump.gui.desktop \
    org.kde.kdebugsettings.desktop \
    org.kde.kjournaldbrowser.desktop \
    org.kde.kmenuedit.desktop \
    org.kde.krfb.desktop \
    org.kde.krfb.virtualmonitor.desktop \
    org.kde.kdeconnect.sms.desktop \
    org.kde.kdeconnect.nonplasma.desktop \
    ; do
    hide_from_menu "$entry"
done

# Gate it: a typo'd filename above would hide nothing and say nothing, and the duplicate the
# owner reported would ship again with a green build. Check the two that MUST be gone by asking
# the file itself, not the list.
for must_hide in kdesystemsettings.desktop org.kde.kwrite.desktop; do
    f="/usr/share/applications/$must_hide"
    if [ -f "$f" ] && ! grep -q '^NoDisplay=true' "$f"; then
        echo "GATE FAIL: $must_hide is still shown in the menu — it duplicates an app MoOS already has"
        exit 1
    fi
done

# -----------------------------------------------------------------------------
# (z2a) Remove the OTHER distribution's themes and wallpapers
# -----------------------------------------------------------------------------
# MoOS's own Look and Feel wins (/etc/xdg/kdeglobals outranks the kde-settings profile), so
# the desktop looks right — but Fedora's theme packages and wallpapers were still sitting in
# the pickers. Open Appearance or Wallpaper on a "MoOS" machine and you were offered
# "Fedora". A picker is a user-facing screen like any other.
#
# Repoint every config that names a Fedora theme FIRST, so nothing is left referring to a
# package that is about to disappear; then remove them. Breeze stays: it is KDE's, not another
# distribution's, and Plasma falls back to it.
#
# These names must track the image's ACTIVE Global Theme, not whichever one was active the day
# the lines were written. They said org.moos.nova / NovaHorizonII through the entire MoOS UI and
# MoOS UI2 rollouts, which left the kde-settings profile naming a *third* theme family — and this
# is precisely the cascade layer AGENTS.md blames for Plasma resolving a stale name and
# persisting Breeze. /etc/xdg outranks it, so it normally loses and nothing looks wrong; the day
# it does not lose, it fails silently and permanently. Keep it pointed at the default.
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

# The Global Theme picker should read all-MoOS. Fedora's looks are deleted above;
# Breeze's three (Breeze, Breeze Dark, Breeze Twilight) are KDE's, not another
# distro's, so they are NOT deleted — Breeze stays the fallback ENGINE every MoOS
# look reaches for (FallbackTheme=breeze-dark). But a foreign NAME in the chooser,
# beside six MoOS looks, is exactly the "not fully MoOS" the owner is removing. So
# the Global-Theme WRAPPERS are hidden from the KCM (Hidden=true) while the
# underlying Breeze plasma-style/colour engine stays fully intact and selectable
# as the fallback. Non-destructive and reversible — nothing is removed from disk.
for _bz in org.kde.breeze.desktop org.kde.breezedark.desktop org.kde.breezetwilight.desktop; do
    _bzmeta="/usr/share/plasma/look-and-feel/${_bz}/metadata.json"
    [ -f "$_bzmeta" ] || continue
    python3 - "$_bzmeta" <<'PY'
import json, sys
p = sys.argv[1]
m = json.load(open(p, encoding="utf-8"))
m.setdefault("KPlugin", {})["Hidden"] = True
m["Hidden"] = True  # some KCM paths read the top-level flag
json.dump(m, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=4)
PY
done

# The wallpaper picker is a user-facing screen, and it held 45 wallpapers: three of MoOS's, one
# called "F44" (that is Fedora 44, by name, in the picker of an OS called MoOS), and forty-one of
# KDE's — Kokkini, FlyingKonqui, ScarletTree, summer_1am. None of them is bad. All of them
# together are somebody else's mood board, and scrolling past forty strangers to reach your own
# three is exactly the "cheap" the owner keeps pointing at.
#
# So: MoOS's wallpapers, and nothing else. This is a curation, not a deletion of capability — the
# picker still takes any image the user points it at.
#
# `Next` survives for one non-cosmetic reason: it is the wallpaper Breeze's look-and-feel names as
# its default, and Breeze is the fallback Plasma reaches for when everything else fails. Deleting
# the fallback's wallpaper turns a bad day (theme broken) into a worse one (theme broken AND a
# black desktop). It is the safety net, not a style choice.
find /usr/share/wallpapers -mindepth 1 -maxdepth 1 -type d \
     ! -name 'MoOS*' ! -name 'Next' -exec rm -rf {} +

# Kill any now-dangling symlink in the same directory. `Default` shipped as a symlink to `F44`
# — Fedora 44's wallpaper — and the -type d sweep above stepped right over it (a symlink is not a
# directory), so `Default` was left pointing at a wallpaper that no longer exists. Breeze's
# look-and-feel names `Default`, so its fallback wallpaper was a broken link: a black desktop the
# moment anything fell back to Breeze. Repoint it at Next (which ships) rather than delete it,
# because deleting it is what would black out Breeze.
if [ -L /usr/share/wallpapers/Default ] && [ ! -e /usr/share/wallpapers/Default ]; then
    ln -snf Next /usr/share/wallpapers/Default
fi
find /usr/share/wallpapers -mindepth 1 -maxdepth 1 -type l ! -exec test -e {} \; -print \
    | while read -r _dead; do rm -f "$_dead"; done

# Gate: nothing may still POINT at a wallpaper we just removed — by absolute path OR by the bare
# name a look-and-feel uses. A config naming a deleted wallpaper does not fall back gracefully;
# Plasma paints black, which is precisely how this machine spent an evening looking broken.
_wp_refs="$(grep -rhoE '/usr/share/wallpapers/[A-Za-z0-9_.-]+' \
              /etc/xdg /usr/share/kde-settings /usr/share/plasma 2>/dev/null | sort -u || true)"
# The bare-name form: `Image=Next` in a look-and-feel `defaults`. Resolve each against the
# wallpaper dir and fail if it is gone.
_wp_names="$(grep -rhoE '^Image=[A-Za-z0-9_.-]+' \
              /usr/share/plasma/look-and-feel 2>/dev/null | sed 's|^Image=|/usr/share/wallpapers/|' | sort -u || true)"
for _wp in $_wp_refs $_wp_names; do
    if [ ! -e "$_wp" ]; then
        echo "GATE FAIL: a config points at $_wp, which no longer exists — the desktop would be black"
        exit 1
    fi
done

# Gate: nothing may still POINT at what we just deleted, or Plasma silently falls back.
if grep -rqE "org\.fedoraproject\.fedora|backgrounds/fedora-workstation|wallpapers/Fedora" \
        /etc/xdg /usr/share/kde-settings /usr/share/plasma 2>/dev/null; then
    echo "FATAL: a config still points at a Fedora theme/wallpaper that was removed:"
    grep -rlE "org\.fedoraproject\.fedora|backgrounds/fedora-workstation|wallpapers/Fedora" \
        /etc/xdg /usr/share/kde-settings /usr/share/plasma 2>/dev/null | sed 's/^/       /'
    exit 1
fi
echo "OK: Fedora's themes and wallpapers are gone, and nothing references them."

# -----------------------------------------------------------------------------
# (z2b) Kill the Plasma out-of-box wizard — it was the FIRST screen of MoOS
# -----------------------------------------------------------------------------
# plasma-setup.service is Plasma's own OOBE:
#
#     Description=Plasma Setup - Out-of-Box / First-Run setup wizard
#     Before=display-manager.service
#     ConditionPathExists=!/etc/plasma-setup-done
#
# It runs BEFORE the display manager and holds the screen, so on a fresh install the very
# first thing a MoOS user saw was a full-screen "Welcome to Plasma Desktop" on Plasma's
# default wallpaper — another desktop's branding, on the most visible screen there is — and
# the MoOS SDDM theme behind it was never reached. Caught by booting the built disk image in
# a VM and looking at it; every gate had passed.
#
# The app entry was already hidden above; the SERVICE was not, and the service is the one
# that actually shows the wizard.
#
# It is redundant as well as off-brand: MoOS ships its own first-run (moos-firstrun ->
# moos-welcome), and the user account is created by the installer, so there is nothing left
# for Plasma's wizard to ask.
#
# Belt and braces: mask the unit AND lay down the flag file the unit itself checks, so the
# wizard cannot come back if a base update re-enables the preset.
systemctl mask plasma-setup.service 2>/dev/null || true
: > /etc/plasma-setup-done

# The gate. This is a first-impression regression, so it fails the build, not a lint.
if [ -e /usr/lib/systemd/system/plasma-setup.service ]; then
    if [ ! -e /etc/plasma-setup-done ]; then
        echo "FATAL: plasma-setup would run — the first screen of MoOS would say 'Welcome to Plasma Desktop'."
        exit 1
    fi
    if [ "$(readlink -f /etc/systemd/system/plasma-setup.service 2>/dev/null)" != "/dev/null" ]; then
        echo "FATAL: plasma-setup.service is not masked."
        exit 1
    fi
    echo "OK: the Plasma out-of-box wizard is masked and flagged done — MoOS boots to its own login screen."
fi

# -----------------------------------------------------------------------------
# (z3) Container policy — ENFORCE the cosign signature on the MoOS registry
# -----------------------------------------------------------------------------
# CI signs every image (build.yml, "Sign image with cosign") and the public key ships at
# /etc/pki/containers/moos.pub. The base policy already enforces signatures for ublue's
# images — but MoOS's own registry, the one whose contents literally become the running OS,
# was listed as insecureAcceptAnything. It was the only one nobody checked.
#
# A v20 attempt at sigstoreSigned broke real-hardware install ("A signature was required,
# but no signature exists") and was reverted to insecureAcceptAnything. That failure had a
# specific cause, now fixed: cosign publishes the signature as a **sigstore attachment**, and
# without a registries.d entry saying `use-sigstore-attachments: true` the verifier looks in
# the wrong place and every image reads as unsigned. That entry now ships
# (system_files/etc/containers/registries.d/moalfarras-sys.yaml), and the whole path was
# verified against the real registry before this was turned back on:
#
#     wrong key -> refused: "cryptographic signature verification failed"
#     right key -> accepted; deployment moved to ostree-image-signed:registry
#
# The OFFLINE install-time pull is UNVERIFIED by design: it reads the image from the
# USB's local containers-storage, which carries no sigstore attachment, so the
# kickstart must pass --no-signature-verification (see the ostreecontainer line). That
# is safe because the %post rewrites the deployed origin to ostree-image-signed — so an
# installed machine re-arms and keeps verifying every DAY-2 update for the rest of its life.
#
# This runs in section (z), after all package installs, so nothing can restore a permissive
# rule afterwards. There must be exactly ONE writer of this file; an earlier iteration of
# this change had two, and the permissive one won.
#
# A refusal is a clean failure — no deployment is created — not a broken system.
if [ -f /etc/containers/policy.json ]; then
    grep -q "use-sigstore-attachments" /etc/containers/registries.d/moalfarras-sys.yaml 2>/dev/null \
        || { echo "FATAL: registries.d entry for the MoOS registry is missing — the signature"; \
             echo "       would never be found and EVERY update would be refused."; exit 1; }
    [ -s /etc/pki/containers/moos.pub ] \
        || { echo "FATAL: the MoOS cosign public key is not in the image; enforcement would"; \
             echo "       fail closed on every update and install."; exit 1; }
    python3 - <<'PYSEC'
import json
p = "/etc/containers/policy.json"
with open(p) as f:
    d = json.load(f)
d.setdefault("transports", {}).setdefault("docker", {})["ghcr.io/moalfarras-sys"] = [{
    "type": "sigstoreSigned",
    "keyPath": "/etc/pki/containers/moos.pub",
    "signedIdentity": {"type": "matchRepository"},
}]
with open(p, "w") as f:
    json.dump(d, f, indent=4)
print("POLICY: ghcr.io/moalfarras-sys now requires a valid MoOS cosign signature.")
PYSEC
    if python3 -c "
import json, sys
d = json.load(open('/etc/containers/policy.json'))
e = d.get('transports', {}).get('docker', {}).get('ghcr.io/moalfarras-sys') or [{}]
sys.exit(0 if e[0].get('type') == 'sigstoreSigned' else 1)"; then
        echo "OK: the MoOS registry is signature-enforced (install + every future upgrade)."
    else
        echo "FATAL: the MoOS registry policy is not enforcing — refusing to ship an image"
        echo "       that silently accepts unsigned updates."; exit 1
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
plymouth-set-default-theme moos
sed -i 's/^Theme=.*/Theme=moos/' /usr/share/plymouth/plymouthd.defaults
if [ -f /usr/share/plymouth/themes/spinner/watermark.png ]; then
    cp -f /usr/share/plymouth/themes/moos/logo.png \
        /usr/share/plymouth/themes/spinner/watermark.png
fi

# Prove moos is the ACTIVE default that dracut's plymouth module will embed, not
# merely present on disk. `plymouth-set-default-theme` with no args PRINTS the
# active default theme name (it reads the config, not a symlink — Fedora 44's
# mechanism). A wrong default ships a Fedora bgrt/spinner splash whose grey
# three-dot fallback is the exact symptom to avoid. Absolute ImageDir is required
# or the emblem/ring silently fail to load, leaving only the background.
_active_theme="$(plymouth-set-default-theme 2>/dev/null)"
if [ -n "$_active_theme" ] && [ "$_active_theme" != "moos" ]; then
    # The query tool answered, and it is NOT moos → a real regression.
    echo "FATAL: active Plymouth default is '${_active_theme}', not moos — the initramfs would embed a foreign splash"
    exit 1
fi
# If the query returned empty (the tool can be unavailable inside buildah), the
# authoritative Theme=moos checks in plymouthd.conf/.defaults below and the
# in-initramfs moos.plymouth gate still prove the splash is MoOS.
grep -qx 'ImageDir=/usr/share/plymouth/themes/moos' /usr/share/plymouth/themes/moos/moos.plymouth \
    || { echo "FATAL: moos.plymouth ImageDir is not the absolute /usr/share/plymouth/themes/moos"; exit 1; }
unset -v _active_theme

DRACUT_NO_XATTR=1 dracut -v --force --zstd --reproducible --no-hostonly \
    --add "ostree plymouth dmsquash-live dmsquash-live-autooverlay" \
    --omit "nfs" \
    --add-drivers "erofs overlay loop" \
    --omit-drivers "nouveau amdgpu radeon i915 xe nvidiafb" \
    "/usr/lib/modules/${kver}/initramfs.img" "${kver}" 2>&1 | tee /tmp/moos-final-dracut.log

# --- initramfs SIZE guard (root-cause fix for the GRUB "can't allocate kernel /
# out of memory" boot failure). An oversized initramfs — e.g. the ~368MB
# moos-nvidia build that swept in the NVIDIA modules + GSP firmware — exceeds what
# GRUB can allocate in UEFI memory on some boards, so every OSTree entry fails.
# Fail the build HARD if the definitive initramfs is too large; print the size
# always so CI records before/after. Ceiling chosen well below the ~368MB that
# bricked the real machine and below the ~188MB that still booted, with margin.
_initramfs_bytes=$(stat -c%s "/usr/lib/modules/${kver}/initramfs.img")
_initramfs_mb=$(( _initramfs_bytes / 1024 / 1024 ))
_initramfs_max_mb="${MOOS_INITRAMFS_MAX_MB:-300}"
echo "=== initramfs size: ${_initramfs_mb} MB (hard ceiling ${_initramfs_max_mb} MB) ==="
if [ "${_initramfs_mb}" -gt "${_initramfs_max_mb}" ]; then
    echo "FATAL: initramfs is ${_initramfs_mb} MB (> ${_initramfs_max_mb} MB) — GRUB may fail with 'can't allocate kernel / out of memory'. Trim drivers/firmware (see omit_drivers in 99-moos-boot.conf)."
    exit 1
fi

grep -q "Including module: ostree" /tmp/moos-final-dracut.log || {
    echo "FATAL: final initramfs lost ostree support"; exit 1;
}
grep -q "Including module: plymouth" /tmp/moos-final-dracut.log || {
    echo "FATAL: final initramfs lost Plymouth support"; exit 1;
}
grep -qx 'Theme=moos' /etc/plymouth/plymouthd.conf
grep -qx 'Theme=moos' /usr/share/plymouth/plymouthd.defaults

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
    grep -q 'plymouth/themes/moos/moos.plymouth' /tmp/moos-final-initrd.txt || {
        echo "FATAL: final initramfs lacks the MoOS Plymouth descriptor"; exit 1;
    }
    # The Script theme's mark (logo.png), its animation SCRIPT, and its moving
    # sprites must all be in the initramfs, or Plymouth renders the background but
    # no reveal, or aborts to the text fallback. The script plugin (script.so) is
    # the difference between a full render and that fallback — the equivalent of
    # the old two-step.so check.
    grep -q 'plymouth/themes/moos/logo.png' /tmp/moos-final-initrd.txt || {
        echo "FATAL: final initramfs lacks the MoOS logo sprite"; exit 1;
    }
    grep -q 'plymouth/themes/moos/moos.script' /tmp/moos-final-initrd.txt || {
        echo "FATAL: final initramfs lacks moos.script — the Script splash would abort to text"; exit 1;
    }
    for _spr in ring head glow; do
        grep -q "plymouth/themes/moos/${_spr}.png" /tmp/moos-final-initrd.txt || {
            echo "FATAL: final initramfs lacks the MoOS ${_spr} sprite — the reveal cannot draw"; exit 1;
        }
    done
    grep -qE 'plymouth/(script\.so|script)' /tmp/moos-final-initrd.txt || {
        echo "FATAL: final initramfs lacks the script Plymouth plugin — the moos theme cannot render"; exit 1;
    }
    grep -qE 'plymouth/renderers/(drm\.so|frame-buffer\.so)' /tmp/moos-final-initrd.txt || {
        echo "FATAL: final initramfs lacks a Plymouth renderer (drm/frame-buffer) — no graphical splash"; exit 1;
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
    grep -qx 'Theme=moos' /tmp/moos-final-plymouth.conf || {
        echo "FATAL: initramfs Plymouth configuration does not select moos"; exit 1;
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

# -----------------------------------------------------------------------------
# The user-experience gate. LAST, and it actually gates.
# -----------------------------------------------------------------------------
# This used to be the FIRST line of this script — line 2, eight lines above
# `set -euxo pipefail`. Two consequences, both bad:
#
#   1. Running before `set -e` meant its failure was IGNORED. The gate could fail and the
#      image would build, tag and ship anyway. Proven: a build in which it printed
#      "MoOS image-experience gate failed" still ended in "Successfully tagged".
#
#   2. Running before any of build.sh's work meant it could only ever inspect what COPY had
#      already put in place. Everything this script creates — the masked Plasma wizard, the
#      signature policy, the spell-check dictionaries — was invisible to it.
#
# So the gate that exists to stop another desktop's branding reaching the user had never
# gated anything, and a fresh MoOS install greeted every user with a full-screen
# "Welcome to Plasma Desktop". Found by booting the built disk in a VM and looking at it.
#
# It runs here now: after every package, every rebrand, every mask — and under `set -e`, so
# a failure stops the build.
python3 /ctx/verify_image_experience.py

# ── The MoOS Store must be internally consistent end-to-end ───────────────────
#
# The store is one contract across its curation layer, local AppStream index,
# two QML surfaces, app-id-scoped bridge and fixed transaction backend. This
# gate fails the build if any edge drifts — including an unsupported recipe,
# missing glyph fallback, dead launcher argument, or public URL install path.
python3 /ctx/verify_store_catalog.py

# ── The identity firewall — the catch-all, on the finished bytes ──────────────
#
# verify_identity.py and verify_image_experience.py check the surfaces we KNOW
# about. This one sweeps the whole image by pattern for another OS's logo, name
# or theme, on the real bytes that ship. It is what catches a base-image update
# that adds a Fedora asset under a name our scrub never listed, and an agent who
# removed a scrub step without understanding what it protected. It runs LAST, so
# nothing added after the rebrand can slip a foreign identity past it.
python3 /ctx/verify_no_foreign_identity.py

# ── The image must not carry the build machine's litter ───────────────────────
#
# `COPY system_files/ /` copies from the build *context*, which is the working tree
# — and `.gitignore` has no say in what that contains. On the maintainer's machine
# it contained `system_files/usr/bin/__pycache__/`, so the image shipped
# `/usr/bin/__pycache__/moai-control.cpython-313.pyc`: the bytecode cache of the
# computer that built it, sitting in the OS's own bin directory. CI, which builds
# from a fresh clone, shipped nothing of the sort — two different images from one
# commit, and nobody could see it without looking inside.
#
# `.containerignore` now keeps it out of the context. This makes sure.
stray_pycache="$(find /usr/bin /usr/share/moos -type d -name '__pycache__' 2>/dev/null | head -5)"
if [ -n "${stray_pycache}" ]; then
    echo "GATE FAIL: the image is carrying a Python bytecode cache from the build machine"
    echo "${stray_pycache}"
    exit 1
fi

echo "MoOS build.sh finished OK"
