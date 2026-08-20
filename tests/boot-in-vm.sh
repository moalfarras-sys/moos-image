#!/usr/bin/env bash
# Boot a built MoOS image in a VM and photograph what it actually shows.
#
# This is the test that found every user-visible defect in this repo that the build gates
# missed — the "Welcome to Plasma Desktop" first screen, the login screen still using Plasma's
# wallpaper because SDDM is not even installed, the boot splash that never appeared. All of
# those shipped with a green build. None of them survived one look at a screenshot.
#
#   usage:  tests/boot-in-vm.sh [image]        (default: moos:latest, from LOCAL podman storage)
#
# Output: PNGs of the boot, from firmware to the login screen, in ./vm-shots/.
#
# It needs /dev/kvm, a few GB of disk, and about half an hour. QEMU runs inside a container so
# nothing has to be installed on the host — which matters, because on an rpm-ostree host
# installing qemu means layering a package and rebooting.
set -euo pipefail

IMAGE="${1:-localhost/moos:latest}"
WORK="${WORK:-$PWD/vm-build}"
SHOTS="${SHOTS:-$PWD/vm-shots}"
HERE="$(cd "$(dirname "$0")" && pwd)"

command -v podman >/dev/null || { echo "podman is required"; exit 1; }
[ -w /dev/kvm ] || { echo "no writable /dev/kvm — the VM would be unusably slow"; exit 1; }

# bootc-image-builder runs rootful, so the image has to be in root's storage.
echo ">>> copying ${IMAGE} into root storage"
sudo skopeo copy \
    "containers-storage:[overlay@${HOME}/.local/share/containers/storage]${IMAGE}" \
    "containers-storage:${IMAGE}"

echo ">>> building a bootable disk"
rm -rf "${WORK}"; mkdir -p "${WORK}"
sudo podman run --rm --privileged --security-opt label=type:unconfined_t \
    -v "${WORK}":/output \
    -v /var/lib/containers/storage:/var/lib/containers/storage \
    -v "${HERE}/../bib/config.toml":/config.toml:ro \
    quay.io/centos-bootc/bootc-image-builder@sha256:2b52843ea2bfda73b0a08d97e76b734393b1d3a804681b9fabb26723bd3a2f0b \
    --type qcow2 --local "${IMAGE}"
sudo chown -R "$(id -u):$(id -g)" "${WORK}"

echo ">>> building the QEMU container"
podman build -t moos-qemu:latest -f - . >/dev/null <<'EOF'
FROM registry.fedoraproject.org/fedora:44
RUN dnf -y install --setopt=install_weak_deps=False \
      qemu-system-x86-core qemu-img edk2-ovmf socat ImageMagick && dnf clean all
EOF

echo ">>> booting, and photographing the boot"
rm -rf "${SHOTS}"; mkdir -p "${SHOTS}"
podman run --rm --security-opt label=disable --device /dev/kvm \
    -v "${WORK}/qcow2":/disk \
    -v "${SHOTS}":/shots \
    moos-qemu:latest bash -c '
set -euo pipefail
cp /usr/share/edk2/ovmf/OVMF_VARS.fd /tmp/vars.fd
# -vga std, not virtio-vga: qemu-system-x86-core does not ship the virtio VGA device.
qemu-system-x86_64 \
    -machine q35,accel=kvm -cpu host -smp 4 -m 4096 \
    -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/ovmf/OVMF_CODE.fd \
    -drive if=pflash,format=raw,file=/tmp/vars.fd \
    -drive file=/disk/disk.qcow2,format=qcow2,if=virtio \
    -vga std -netdev user,id=n0 -device e1000,netdev=n0 \
    -display none -monitor unix:/tmp/mon.sock,server,nowait \
    -daemonize -pidfile /tmp/vm.pid

last=0
for t in 10 25 40 60 80 100 125 150 180 220 260; do
    sleep $(( t - last )); last=$t
    n="$(printf "%03d" "$t")s"
    printf "screendump /shots/%s.ppm\n" "$n" | socat - UNIX-CONNECT:/tmp/mon.sock >/dev/null 2>&1 || true
    if [ -s "/shots/${n}.ppm" ]; then
        magick "/shots/${n}.ppm" "/shots/${n}.png" && rm -f "/shots/${n}.ppm"
        echo "  ${t}s"
    fi
done
kill "$(cat /tmp/vm.pid)" 2>/dev/null || true
'

echo
echo ">>> screenshots in ${SHOTS}"
echo "    Look at them. In particular: is the first screen MoOS, is the boot splash MoOS,"
echo "    and does the login screen use the MoOS wallpaper? Every one of those has been"
echo "    wrong here while the build was green."
