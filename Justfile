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

# The repo gates — the ones that read what is ABOUT to be shipped.
#
# These existed and nothing ran them. build.sh runs verify_image_experience.py inside the
# container, but the three tests under tests/ were honour-system: not in `just build`, not in
# the CI workflow. Every gate a session added ("a gate now guards this") could go red for
# weeks and no build would notice — which is the same failure AGENTS.md documents for the
# identity gate that ran before `set -e`. A gate that cannot fail a build is a comment.
#
# They run in seconds and need no container, so they go FIRST: a typo in a Konsole group name
# or a Mo AI button pointing at a command that does not exist should cost you 3 seconds, not a
# 20-minute image build.
check:
    python3 tests/verify_user_experience.py
    python3 tests/test_device_plan.py
    python3 tests/test_moai_do.py

# Build the main MoOS image. The base is pinned in the Containerfile on purpose — both
# editions must share it (see the comment there); it is not a build-arg any more.
build: check
    podman build \
        --build-arg IMAGE_NAME={{ image_name }} \
        -t {{ image_name }}:latest \
        .

# Build the NVIDIA edition: the SAME base, with the driver layered on from ublue's akmods
# container. (It used to build FROM ghcr.io/ublue-os/kinoite-nvidia:44 — a tag upstream
# abandoned in May, which silently made the "NVIDIA image" ~589 packages older than the
# generic one.) The akmods tag is pinned to the base image's exact kernel: a kmod built for
# a different kernel does not load, and the machine boots to a black screen.
build-nvidia: check
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

# Re-vendor MoPlayer's source from its own repository.
#
# The image builds MoPlayer from source in a Containerfile stage (see
# `moplayer/VENDORED.md`), so this directory has to be a faithful copy of the app's
# tree. It copies exactly what MoPlayer's git tracks — never the 40 MB build
# output, never .dart_tool, never linux/flutter/ephemeral.
sync-moplayer:
    #!/usr/bin/env bash
    set -euo pipefail
    SRC="${MOPLAYER_SRC:-$(pwd)/../MoPlayerMoOS}"
    [ -f "$SRC/pubspec.yaml" ] || { echo "sync-moplayer: no MoPlayer tree at $SRC" >&2; exit 1; }
    echo "==> syncing from $SRC"
    rm -rf moplayer.tmp && mkdir -p moplayer.tmp
    (cd "$SRC" && git ls-files) | while read -r f; do
        mkdir -p "moplayer.tmp/$(dirname "$f")"
        cp "$SRC/$f" "moplayer.tmp/$f"
    done
    cp moplayer/VENDORED.md moplayer.tmp/VENDORED.md
    rm -rf moplayer && mv moplayer.tmp moplayer
    echo "==> vendored $(find moplayer -type f | wc -l) files ($(du -sh moplayer | cut -f1))"
    echo "    Also copy the launcher/desktop/icons into system_files if they changed:"
    echo "      install -D -m0755 moplayer/packaging/moos/moplayer system_files/usr/bin/moplayer"
