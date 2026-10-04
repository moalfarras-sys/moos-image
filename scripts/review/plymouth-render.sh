#!/bin/bash
# Run INSIDE a disposable SDK containing the rebuilt /out RPMs, gcc,
# plymouth-devel and Xvfb. Mount repository read-only at /repo, artifacts at
# /evidence, disable network and coredumps. Never use the owner's DISPLAY/bus.
# Captures native pixel buffers, not a composited simulation or boot proof.
set -euo pipefail
if [ ! -e /run/.containerenv ] && [ ! -e /.dockerenv ]; then
 echo "Refusing to render against the owner desktop; use the review SDK" >&2
 exit 2
fi
ulimit -c 0
THEME_SOURCE=${THEME_SOURCE:-/repo/system_files/usr/share/plymouth/themes/moos}
ARTIFACT_DIR=${ARTIFACT_DIR:-/evidence}
mkdir -p /review/theme /review/lib "$ARTIFACT_DIR"
cp "$THEME_SOURCE"/* /review/theme/
cat > /review/theme/moos.plymouth <<'THEME'
[Plymouth Theme]
Name=MoOS
ModuleName=script
[script]
ImageDir=/review/theme
ScriptFile=/review/theme/moos.script
THEME
for package in /out/plymouth-core-libs-*.rpm /out/plymouth-plugin-script-*.rpm; do
 (cd /review/lib; rpm2cpio "$package" | cpio -idm --quiet --no-absolute-filenames --no-preserve-owner)
done
gcc -Wall -Wextra -Werror -I/usr/include/plymouth-1/ply -I/usr/include/plymouth-1/ply-splash-core /repo/scripts/review/plymouth-render.c -o /review/render -l:libply-splash-core.so.5 -l:libply.so.5
for resolution in 640x480 1920x1080 3840x2160; do
 Xvfb :99 -screen 0 "${resolution}x24" -nolisten tcp > /review/xvfb.log 2>&1 &
 xpid=$!
 trap 'kill "$xpid" 2>/dev/null || true' EXIT
 for attempt in $(seq 1 50); do test -S /tmp/.X11-unix/X99 && break; sleep .1; done
 DISPLAY=:99 LD_LIBRARY_PATH=/review/lib/usr/lib64 /review/render /review/theme/moos.plymouth /review/lib/usr/lib64/plymouth/ "${ARTIFACT_DIR}/native-${resolution}.ppm"
 if [ "$resolution" = 640x480 ]; then
  DISPLAY=:99 LD_LIBRARY_PATH=/review/lib/usr/lib64 /review/render /review/theme/moos.plymouth /review/lib/usr/lib64/plymouth/ "${ARTIFACT_DIR}/native-password.ppm" 'Unlock encrypted disk'
 fi
 kill "$xpid"
 wait "$xpid" || true
 trap - EXIT
done
