#!/usr/bin/env bash
# setup-dev-box.sh — create the container MoPlayer is built in.
#
# MoOS (Fedora Atomic / bootc) has no compiler and is not supposed to get one:
# layering clang and the GTK headers into the image would put a toolchain on
# every user's desktop to serve one developer. The build therefore happens in a
# distrobox, and the host stays clean.
#
# The one thing that is *not* installed here is libmpv: MoOS already ships it as
# `mpv-libs`, and that is the copy the app links against at runtime. The dev box
# needs the headers (`mpv-libs-devel`) to compile against, nothing more.
set -euo pipefail

BOX="${MOPLAYER_DEV_BOX:-moplayer-dev}"
IMAGE="${MOPLAYER_DEV_IMAGE:-registry.fedoraproject.org/fedora-toolbox:42}"
FLUTTER_VERSION="${FLUTTER_VERSION:-3.35.1}"

if ! command -v distrobox >/dev/null 2>&1; then
    echo "setup-dev-box: distrobox is required (it ships with MoOS)." >&2
    exit 1
fi

if ! podman container exists "$BOX" 2>/dev/null; then
    echo "==> creating $BOX from $IMAGE"
    distrobox create --name "$BOX" --image "$IMAGE" --yes
fi

echo "==> toolchain"
distrobox enter --name "$BOX" -- bash -lc '
set -e
sudo dnf install -y --setopt=install_weak_deps=False \
    clang cmake ninja-build pkg-config gtk3-devel \
    mpv-libs-devel \
    xz zip unzip git curl file which findutils
'

echo "==> Flutter $FLUTTER_VERSION"
distrobox enter --name "$BOX" -- bash -lc "
set -e
DIR=\"\$HOME/.local/flutter\"
if [ ! -x \"\$DIR/bin/flutter\" ]; then
    mkdir -p \"\$HOME/.local\"
    curl -fL --retry 3 -o /tmp/flutter.tar.xz \
        'https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_${FLUTTER_VERSION}-stable.tar.xz'
    tar -xJf /tmp/flutter.tar.xz -C \"\$HOME/.local\"
    rm -f /tmp/flutter.tar.xz
fi
# The SDK is checked out as a git repo owned by another uid inside the box.
git config --global --add safe.directory \"\$DIR\"
export PATH=\"\$DIR/bin:\$PATH\"
flutter config --no-analytics --enable-linux-desktop >/dev/null
flutter --version
"

echo
echo "Ready.  just build   ·   just run   ·   just install"
