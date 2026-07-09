# =============================================================================
# MoOS Justfile — local inner-loop recipes (run inside WSL2 with podman 5.x)
# =============================================================================
# IMAGE builds are the ONLY thing supported locally/WSL2.
# ISO/disk-image recipes are deliberately ABSENT: ISO builds are CI-only
# (.github/workflows/build-iso.yml) because the osbuild/ISO tooling does not
# work on the WSL2 kernel. Offline fallback: a real Fedora VM in Hyper-V.
# See MOOS_BUILD_WORKFLOW.md (Phase 5).
# =============================================================================

image_name := "moos"
base_main := "ghcr.io/ublue-os/kinoite-main:44"
base_nvidia := "ghcr.io/ublue-os/kinoite-nvidia:44"

# List available recipes
default:
    @just --list

# Build the main MoOS image (kinoite-main base)
build:
    podman build \
        --build-arg BASE_IMAGE={{ base_main }} \
        -t {{ image_name }}:latest \
        .

# Build the NVIDIA variant (kinoite-nvidia base, proprietary drivers baked in)
build-nvidia:
    podman build \
        --build-arg BASE_IMAGE={{ base_nvidia }} \
        -t {{ image_name }}-nvidia:latest \
        .

# Re-run the bootc lint against the built image (the Containerfile already
# runs it as the final build stage; this is for ad-hoc re-checks)
lint:
    podman run --rm {{ image_name }}:latest bootc container lint

# Remove locally built MoOS images
clean:
    -podman rmi -f {{ image_name }}:latest {{ image_name }}-nvidia:latest
