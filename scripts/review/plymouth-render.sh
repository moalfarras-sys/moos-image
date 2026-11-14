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
for resolution in 640x360 800x480 640x480 1920x1080 3840x2160; do
 Xvfb :99 -screen 0 "${resolution}x24" -nolisten tcp > /review/xvfb.log 2>&1 &
 xpid=$!
 trap 'kill "$xpid" 2>/dev/null || true' EXIT
 for attempt in $(seq 1 50); do test -S /tmp/.X11-unix/X99 && break; sleep .1; done
 DISPLAY=:99 LD_LIBRARY_PATH=/review/lib/usr/lib64 /review/render /review/theme/moos.plymouth /review/lib/usr/lib64/plymouth/ "${ARTIFACT_DIR}/native-${resolution}.ppm"
 if [ "$resolution" = 640x360 ] || [ "$resolution" = 800x480 ] || [ "$resolution" = 640x480 ]; then
  DISPLAY=:99 LD_LIBRARY_PATH=/review/lib/usr/lib64 /review/render /review/theme/moos.plymouth /review/lib/usr/lib64/plymouth/ "${ARTIFACT_DIR}/native-password.ppm" 'Unlock encrypted disk'
  DISPLAY=:99 LD_LIBRARY_PATH=/review/lib/usr/lib64 /review/render /review/theme/moos.plymouth /review/lib/usr/lib64/plymouth/ "${ARTIFACT_DIR}/native-password-update.ppm" 'Unlock encrypted disk' --prompt-update
  DISPLAY=:99 LD_LIBRARY_PATH=/review/lib/usr/lib64 /review/render /review/theme/moos.plymouth /review/lib/usr/lib64/plymouth/ "${ARTIFACT_DIR}/native-arabic.ppm" 'أدخل عبارة المرور لفتح القرص المشفر'
  DISPLAY=:99 LD_LIBRARY_PATH=/review/lib/usr/lib64 /review/render /review/theme/moos.plymouth /review/lib/usr/lib64/plymouth/ "${ARTIFACT_DIR}/native-arabic-zero.ppm" 'أدخل عبارة المرور لفتح القرص المشفر' --prompt-zero
  DISPLAY=:99 LD_LIBRARY_PATH=/review/lib/usr/lib64 /review/render /review/theme/moos.plymouth /review/lib/usr/lib64/plymouth/ "${ARTIFACT_DIR}/native-long.ppm" 'Please enter passphrase for disk MoOS (luks-12345678-1234-1234-1234-123456789abc)!'
  python3 - "$ARTIFACT_DIR" "$resolution" <<'PY'
import sys
from pathlib import Path
def pixels(name):
    with (Path(sys.argv[1]) / name).open('rb') as stream:
        assert stream.readline() == b'P6\n'
        w, h = map(int, stream.readline().split())
        assert stream.readline() == b'255\n'
        return w, h, stream.read()
w, h, resting = pixels('native-' + sys.argv[2] + '.ppm')
w2, h2, updated = pixels('native-password-update.ppm')
assert (w, h) == (w2, h2)
split = w * (h * 3 // 4) * 3
assert resting[:split] == updated[:split], 'typing erased or delayed the resting MoOS composition'
_, _, password = pixels('native-password.ppm')
assert password[split:] != updated[split:], 'the password bullet update has not painted within 200 ms'
print('Native prompt redraw passed: composition retained and changed bullets visible within 200 ms')
# Compare actual painted ink, not image rectangles: zero and four bullets
# use the same prompt and line metrics. In the old layout Arabic and bullets
# painted the same rows despite the passing short English control.
def changed(first, second):
    return [(i // 3 % w, i // 3 // w) for i in range(0, len(first), 3)
            if max(abs(first[i + c] - second[i + c]) for c in range(3)) > 2]
_, _, arabic = pixels('native-arabic.ppm')
_, _, zero = pixels('native-arabic-zero.ppm')
prompt_ink = changed(zero, resting)
bullet_ink = changed(arabic, zero)
assert prompt_ink and bullet_ink, 'native Arabic prompt or password bullets did not paint'
assert min(y for x, y in bullet_ink) > max(y for x, y in prompt_ink), 'password bullets overlap Arabic prompt ink'
assert min(x for x, y in prompt_ink) > 0 and max(x for x, y in prompt_ink) < w - 1
assert max(y for x, y in bullet_ink) < h - 1, 'password bullets touch the lower screen edge'
_, _, long_prompt = pixels('native-long.ppm')
long_ink = changed(long_prompt, resting)
assert long_ink and min(x for x, y in long_ink) > 0 and max(x for x, y in long_ink) < w - 1
print('Native Arabic and password ink remain separate; long prompt fits:', sys.argv[2])
PY
  for case in password password-update arabic arabic-zero long; do
   mv "${ARTIFACT_DIR}/native-${case}.ppm" "${ARTIFACT_DIR}/native-${resolution}-${case}.ppm"
  done
 fi
 kill "$xpid"
 wait "$xpid" || true
 trap - EXIT
done
