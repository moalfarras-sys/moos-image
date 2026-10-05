#!/usr/bin/env bash
# LOOK at MoOS's session surfaces (lock, logout, login) rendered from THIS worktree by the real
# Plasma greeter binaries, without touching the owner's desktop or the installed system.
#
#   scripts/station/session-review/review.sh shots.txt [out-dir]
#
# shots.txt: one shot per line, `<lock|logout|login> <name> [key=value ...]` — the keys are
# documented at the top of in-container.sh. PNGs and each surface's log land in out-dir
# (default ~/.cache/moos-session-review/out; the VS Code Flatpak's /tmp is not the host's).
#
# It runs a throwaway container from a local image that carries stock Plasma + Xvfb
# (MOOS_REVIEW_IMAGE), lays system_files over it the way the image build does, and borrows the
# station's installed fonts and icon themes read-only, because the image build generates those.
# REVIEW_OVERLAY=0 with MOOS_REVIEW_IMAGE=<a built MoOS image that has Xvfb added> renders the
# image's own files instead: what was built, not what is in the tree.
# Source-harness evidence on X11 with software GL: no KWin blur, no Wayland layer-shell, and
# not the station's GPU. It answers "does it load, fit and read", never "is it fast".
set -euo pipefail
SHOTS="$(realpath "$1")"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$(realpath -m "${2:-$HOME/.cache/moos-session-review/out}")"
IMAGE="${MOOS_REVIEW_IMAGE:-localhost/moos-plymouth-render:20261004}"
HOST=()
if [ -e /.flatpak-info ]; then HOST=(flatpak-spawn --host); fi
# A built MoOS image carries its own fonts and icon themes; a stock Plasma borrows the station's.
BORROWED=(-v /usr/share/fonts:/usr/share/fonts:ro -v /usr/share/icons:/usr/share/icons:ro)
if [ "${REVIEW_OVERLAY:-1}" = 0 ]; then BORROWED=(); fi
mkdir -p "$OUT" "$HOME/.cache/moos-session-review"
WORK="$(mktemp -d "$HOME/.cache/moos-session-review/work.XXXXXX")"
cp "$SHOTS" "$WORK/shots.txt"
"${HOST[@]}" podman run --rm --network=none --security-opt label=disable \
    --userns=keep-id --user 0:0 \
    --env REVIEW_UID="$(id -u)" --env SEAM_SET="${SEAM_SET:-}" \
    --env LOGIN_WALLPAPER="${LOGIN_WALLPAPER:-0}" --env REVIEW_USERS="${REVIEW_USERS:-1}" \
    --env REVIEW_OVERLAY="${REVIEW_OVERLAY:-1}" \
    -v "$ROOT":/src:ro -v "$OUT":/out -v "$WORK":/work \
    "${BORROWED[@]}" \
    --entrypoint bash "$IMAGE" /src/scripts/station/session-review/in-container.sh
echo "out: $OUT   (work kept for logs: $WORK)"
