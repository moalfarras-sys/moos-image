# =============================================================================
# MoOS Containerfile — builds the MoOS bootc/OCI image
# =============================================================================
# Modeled on ublue-os/image-template conventions:
#   https://github.com/ublue-os/image-template
#
# Current image scope:
#   - Base: ghcr.io/ublue-os/kinoite-main:44 (Fedora Atomic + Plasma)
#   - Complete MoOS identity and Nova desktop/boot/install experience
#   - MoOS system applications, local-first Mo AI and compatibility tooling
#   - Automatic atomic/Flatpak updates and guarded rollback
#
# NVIDIA variant: build with
#   podman build --build-arg IMAGE_NAME=moos-nvidia \
#     --build-arg AKMODS_IMAGE=ghcr.io/ublue-os/akmods-nvidia-open:main-44-<kver> \
#     -t moos-nvidia:latest .
# =============================================================================

# BOTH editions build from the SAME base. This is deliberately NOT a build-arg.
#
# moos-nvidia used to build FROM ghcr.io/ublue-os/kinoite-nvidia:44, selected by a BASE_IMAGE
# arg. That tag is dead upstream — its last build was 2026-05-27 on kernel 7.0.9, while
# kinoite-main:44 is rebuilt daily (7.1.3 as of this commit). So the "NVIDIA image" was really
# a six-week-old system that happened to contain NVIDIA: ~589 packages behind the generic
# edition, on an older kernel. rpm-ostree said exactly that on every boot.
#
# A shared base is not a knob, it is the invariant that keeps the two editions from silently
# drifting apart, so it is pinned here rather than passed in. The driver is layered on top the
# way Bazzite/Bluefin do it: ublue publishes an akmods container per (kernel, driver) pair and
# ships its own installer inside it. Same base, same kernel, zero downgrades — the only
# difference between the editions is the driver.
#
# (A BASE_IMAGE build-arg passed by an older caller is simply unused; buildah warns and moves
# on. Nothing can quietly reintroduce a divergent base.)
# The akmods container: kmod-nvidia built against a specific kernel, plus the matching
# userspace driver.
#
# The kmod and the kernel MUST agree — a module built for another kernel does not load, and
# the machine boots to a black screen. This floating tag tracks the same kernel ublue builds
# kinoite-main against, and build.sh refuses to continue if the two ever disagree, so a drift
# fails the build loudly instead of shipping an unbootable image. Callers that can resolve the
# base image's exact kernel (CI, the Justfile) should pin the exact tag instead.
#
# Declared BEFORE the first FROM on purpose: an ARG used in a FROM must be in the global
# scope. Declared after it, it belongs to that stage, `FROM ${AKMODS_IMAGE}` expands to
# nothing, and buildah fails with "no FROM statement found".
ARG AKMODS_IMAGE=ghcr.io/ublue-os/akmods-nvidia-open:main-44-x86_64

FROM ghcr.io/ublue-os/kinoite-main:44 AS base

# -----------------------------------------------------------------------------
# Stage "ctx": build scripts live here and are bind-mounted (NOT copied) into
# the final image at /ctx during the RUN below — the image-template convention.
# This keeps build-only scripts out of the shipped OS image.
# -----------------------------------------------------------------------------
FROM scratch AS ctx
COPY build_files /

# -----------------------------------------------------------------------------
# Stage "akmods": ublue's NVIDIA kmod + driver RPMs, bind-mounted (not copied) at
# /akmods during the build. The generic edition mounts it and never reads it —
# build.sh only touches it when IMAGE_NAME is moos-nvidia, so nothing NVIDIA ever
# lands in the generic image.
# -----------------------------------------------------------------------------
FROM ${AKMODS_IMAGE} AS akmods

# Build Mo Remote from source. The final MoOS image receives only the
# self-contained runtime, not the SDK or build caches.
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS moremote-build
WORKDIR /src
COPY moremote/ ./
RUN dotnet publish agent-linux/MoRemoteLinux.csproj -c Release -r linux-x64 \
    --self-contained true -o /out

# -----------------------------------------------------------------------------
# Build MoPlayer from source — same pattern as Mo Remote above: the SDK and the
# build tree stay in this stage, and the final image receives only the ~40 MB
# Flutter bundle.
#
# The builder is **Fedora 44**, and that is not incidental. MoPlayer links the
# system's libmpv (`mpv-libs`, which the image already ships for haruna) rather
# than bundling a codec stack of its own — that is the entire reason a video
# player is allowed into the image at all. A binary compiled against Ubuntu's
# libmpv and glibc, then dropped into a Fedora /usr, is a coin flip on a symbol
# version; built against the same Fedora the image is made of, it is not.
#
# Only the *headers* (mpv-libs-devel) are needed here. The library itself is the
# one already in the image, and nothing from this stage but the bundle ships.
FROM registry.fedoraproject.org/fedora:44 AS moplayer-build
ARG FLUTTER_VERSION=3.35.1
RUN dnf -y install --setopt=install_weak_deps=False \
        clang cmake ninja-build pkgconf-pkg-config \
        gtk3-devel mpv-libs-devel libsecret-devel \
        xz zip unzip git curl file which findutils \
    && dnf clean all
RUN curl -fL --retry 3 -o /tmp/flutter.tar.xz \
        "https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_${FLUTTER_VERSION}-stable.tar.xz" \
    && tar -xJf /tmp/flutter.tar.xz -C /opt \
    && rm -f /tmp/flutter.tar.xz
ENV PATH="/opt/flutter/bin:${PATH}"
# The SDK is a git checkout owned by another uid inside the container; without
# this, every flutter command stops to complain about "dubious ownership".
RUN git config --global --add safe.directory /opt/flutter \
    && flutter config --no-analytics --enable-linux-desktop >/dev/null \
    && flutter --version
WORKDIR /src
COPY moplayer/ ./
RUN flutter pub get \
    && flutter build linux --release \
    && mkdir -p /out \
    && cp -r build/linux/x64/release/bundle/. /out/
# A bundle that cannot find its own libraries is a black window, and it fails at
# *run* time, on the user's machine, after the image has shipped. Catch it here.
RUN test -x /out/moplayer \
    && test -f /out/data/icudtl.dat \
    && test -d /out/data/flutter_assets \
    || { echo "GATE FAIL: the MoPlayer bundle is incomplete"; exit 1; }

# -----------------------------------------------------------------------------
# Main image — the shared base pinned at the top of this file.
# -----------------------------------------------------------------------------
FROM base

# IMAGE_NAME (moos | moos-nvidia) so build.sh can bake the matching install ref
# into the Anaconda kickstart — a moos-nvidia image must deploy moos-nvidia, not
# moos (installing the wrong edition is what forced the user's manual bootc
# switch that bricked the machine). Passed as a build-arg by build.yml's matrix.
ARG IMAGE_NAME=moos

LABEL org.opencontainers.image.title="MoOS" \
      org.opencontainers.image.description="MoOS — atomic desktop with the Nova experience" \
      org.opencontainers.image.vendor="Moalfarras" \
      org.opencontainers.image.source="https://github.com/moalfarras-sys/moos-image"

# System files are copied verbatim onto / of the image. This tree contains the
# MoOS identity, Nova desktop/login/boot themes, applications, service units,
# and boot/install configuration. build_files/build.sh performs the package-
# dependent wiring and final validation.
COPY system_files/ /
COPY --from=moremote-build /out/ /usr/lib/mo-remote/
COPY moremote/Logo.png /usr/share/icons/hicolor/512x512/apps/mo-remote-personal.png

# MoPlayer's Flutter bundle: one ELF binary plus the data/ directory it must sit
# beside. /usr/lib/moplayer, and *not* /usr/share/moos/apps/ — build.sh globs
# that directory for `main.qml` and headlessly smoke-tests every app it finds, and
# a Flutter binary swept into that loop breaks it. /usr/bin/moplayer (from
# system_files) is the launcher that runs this bundle from the right cwd.
COPY --from=moplayer-build /out/ /usr/lib/moplayer/

# Run the build script:
#   - /ctx is the bind-mounted build_files stage (see above)
#   - /akmods is the bind-mounted NVIDIA RPM stage (empty for the generic edition)
#   - /var/cache and /var/log are cache mounts: their contents speed up
#     rebuilds but never persist into the final image (bootc lint requires
#     a clean /var)
#   - /tmp is a tmpfs: scratch space that also never persists
# NOTE: invoked via `bash` (not ./build.sh) on purpose — this repo is edited
# on Windows, where git usually drops the executable bit.
RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=bind,from=akmods,source=/,target=/akmods \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    MOOS_IMAGE_NAME="${IMAGE_NAME}" bash /ctx/build.sh

# Final gate: validate that the result is a well-formed bootc container
# (clean /var, valid ostree layout, kernel present, ...). The build FAILS
# here if the image is not deployable — cheap insurance before CI push.
RUN bootc container lint
