# =============================================================================
# MoOS Justfile — local inner-loop recipes (run inside WSL2 with podman 5.x)
# =============================================================================
# IMAGE builds are the ONLY thing supported locally/WSL2.
# ISO/disk-image recipes are deliberately ABSENT: ISO builds are CI-only
# (.github/workflows/build-iso.yml) because the osbuild/ISO tooling does not
# work on the WSL2 kernel. Offline fallback: a real Fedora VM in Hyper-V.
# CI owns ISO and disk-image production; these recipes are the local OCI loop.
# =============================================================================

image_name := "moos"
base_main := "ghcr.io/ublue-os/kinoite-main:44"

# List available recipes
default:
    @just --list

# Build the main MoOS image. The base is pinned in the Containerfile on purpose — both
# editions must share it (see the comment there); it is not a build-arg any more.
build:
    podman build \
        --build-arg IMAGE_NAME={{ image_name }} \
        -t {{ image_name }}:latest \
        .

# Build the NVIDIA edition: the SAME base, with the driver layered on from ublue's akmods
# container. (It used to build FROM ghcr.io/ublue-os/kinoite-nvidia:44 — a tag upstream
# abandoned in May, which silently made the "NVIDIA image" ~589 packages older than the
# generic one.) The akmods tag is pinned to the base image's exact kernel: a kmod built for
# a different kernel does not load, and the machine boots to a black screen.
build-nvidia:
    #!/usr/bin/env bash
    set -euo pipefail
    kernel="$(skopeo inspect docker://{{ base_main }} | jq -er '.Labels["ostree.linux"]')"
    echo "base kernel: ${kernel}"
    podman build \
        --build-arg IMAGE_NAME={{ image_name }}-nvidia \
        --build-arg "AKMODS_IMAGE=ghcr.io/ublue-os/akmods-nvidia-open:main-44-${kernel}" \
        -t {{ image_name }}-nvidia:latest \
        .

# Re-run the bootc lint against the built image (the Containerfile already
# runs it as the final build stage; this is for ad-hoc re-checks)
lint:
    podman run --rm {{ image_name }}:latest bootc container lint

# Remove locally built MoOS images
clean:
    -podman rmi -f {{ image_name }}:latest {{ image_name }}-nvidia:latest
