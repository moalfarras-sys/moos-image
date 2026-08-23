#!/usr/bin/env bash
# Build slim recovery qcow2 + MoOS-UTM-Installer.utm.zip locally.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${MOOS_RELEASE_DIR:-/var/home/moos/Desktop/MoOS-Release}"
RECOVERY_TAG="${MOOS_RECOVERY_TAG:-moos-arm-recovery:local}"
BUILD_DIR="${MOOS_BIB_DIR:-/var/tmp/moos-recovery-bib}"
PLATFORM="${MOOS_ARM_PLATFORM:-linux/arm64}"

mkdir -p "$OUT_DIR" "$BUILD_DIR/output" "$BUILD_DIR/config"

echo "=== Building recovery container ($PLATFORM) ==="
podman build --platform "$PLATFORM" -f "$ROOT/Containerfile.arm-recovery" -t "$RECOVERY_TAG" "$ROOT"
sudo podman tag "$RECOVERY_TAG" "$RECOVERY_TAG" 2>/dev/null || \
    sudo podman tag "localhost/${RECOVERY_TAG}" "$RECOVERY_TAG"

cat > "$BUILD_DIR/config/config.toml" <<'TOML'
[[customizations.filesystem]]
mountpoint = "/"
minsize = "4 GiB"
TOML

echo "=== bootc-image-builder recovery qcow2 ==="
sudo podman run --rm --privileged --pull=newer \
    --security-opt label=type:unconfined_t \
    -v "$BUILD_DIR/output":/output \
    -v "$BUILD_DIR/config/config.toml":/config.toml:ro \
    -v /var/lib/containers/storage:/var/lib/containers/storage \
    quay.io/centos-bootc/bootc-image-builder@sha256:2b52843ea2bfda73b0a08d97e76b734393b1d3a804681b9fabb26723bd3a2f0b \
    --type qcow2 --rootfs btrfs --config /config.toml --target-arch arm64 --local "$RECOVERY_TAG"

RECOVERY_QCOW="$(find "$BUILD_DIR/output" -name '*.qcow2' -print -quit)"
[ -n "$RECOVERY_QCOW" ] || { echo "FATAL: no recovery qcow2"; exit 1; }
echo "recovery qcow2: $RECOVERY_QCOW ($(du -h "$RECOVERY_QCOW" | awk '{print $1}'))"

ZIP="$OUT_DIR/MoOS-UTM-Installer.utm.zip"
python3 "$ROOT/artwork/generate_utm_installer.py" \
    --installer-qcow2 "$RECOVERY_QCOW" \
    --iphone \
    --output "$OUT_DIR/MoOS-UTM-Installer.utm" \
    --zip "$ZIP"

sha256sum "$ZIP" | tee "$OUT_DIR/MoOS-UTM-Installer.utm.zip.sha256"
du -h "$ZIP"
