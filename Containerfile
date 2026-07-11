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

# Build Mo Remote from source. The final MoOS image receives only the
# self-contained runtime, not the SDK or build caches.
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS moremote-build
WORKDIR /src
COPY moremote/ ./
RUN dotnet publish agent-linux/MoRemoteLinux.csproj -c Release -r linux-x64 \
    --self-contained true -o /out

# -----------------------------------------------------------------------------
# Main image
# -----------------------------------------------------------------------------
FROM ${BASE_IMAGE}

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
    MOOS_IMAGE_NAME="${IMAGE_NAME}" bash /ctx/build.sh

# Final gate: validate that the result is a well-formed bootc container
# (clean /var, valid ostree layout, kernel present, ...). The build FAILS
# here if the image is not deployable — cheap insurance before CI push.
RUN bootc container lint
