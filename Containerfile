# =============================================================================
# MoOS Containerfile — builds the MoOS bootc/OCI image
# =============================================================================
# Modeled on ublue-os/image-template conventions:
#   https://github.com/ublue-os/image-template
#
# M0 "Nova Seed" scope:
#   - Base: ghcr.io/ublue-os/kinoite-main:44 (Fedora 44 Atomic, KDE Plasma 6.7+)
#   - os-release branding (NAME/PRETTY_NAME -> MoOS)
#   - uupd background updater installed + timer enabled
#   - Skeleton system_files (theme/SDDM/Plymouth/wallpaper placeholders)
#
# NVIDIA variant: build with
#   podman build --build-arg BASE_IMAGE=ghcr.io/ublue-os/kinoite-nvidia:44 \
#     -t moos-nvidia:latest .
# =============================================================================

# BASE_IMAGE is overridable so the same Containerfile produces both
# "moos" (kinoite-main) and "moos-nvidia" (kinoite-nvidia) images.
ARG BASE_IMAGE=ghcr.io/ublue-os/kinoite-main:44

# -----------------------------------------------------------------------------
# Stage "ctx": build scripts live here and are bind-mounted (NOT copied) into
# the final image at /ctx during the RUN below — the image-template convention.
# This keeps build-only scripts out of the shipped OS image.
# -----------------------------------------------------------------------------
FROM scratch AS ctx
COPY build_files /

# -----------------------------------------------------------------------------
# Main image
# -----------------------------------------------------------------------------
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="MoOS" \
      org.opencontainers.image.description="MoOS — Fedora Atomic (Kinoite lineage) bootc image with the Nova UI identity" \
      org.opencontainers.image.vendor="Moalfarras" \
      org.opencontainers.image.source="https://github.com/moalfarras-sys/moos-image"

# System files are copied verbatim onto / of the image.
# M0: skeleton dirs for org.moos.nova Global Theme, moos-nova SDDM theme,
# moos-nova Plymouth theme, NovaHorizon wallpaper kpackage, /etc/moos.
# Real assets land in Phase 3 (Design) and Phase 5 (Boot & Installer) —
# see ../MOOS_BUILD_WORKFLOW.md.
COPY system_files/ /

# Run the build script:
#   - /ctx is the bind-mounted build_files stage (see above)
#   - /var/cache and /var/log are cache mounts: their contents speed up
#     rebuilds but never persist into the final image (bootc lint requires
#     a clean /var)
#   - /tmp is a tmpfs: scratch space that also never persists
# NOTE: invoked via `bash` (not ./build.sh) on purpose — this repo is edited
# on Windows, where git usually drops the executable bit.
RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    bash /ctx/build.sh

# Final gate: validate that the result is a well-formed bootc container
# (clean /var, valid ostree layout, kernel present, ...). The build FAILS
# here if the image is not deployable — cheap insurance before CI push.
RUN bootc container lint
