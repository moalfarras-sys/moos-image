#!/usr/bin/env bash
# install-local.sh — install MoPlayer into the current user's ~/.local.
#
# This is how you run MoPlayer on a MoOS machine *without* rebuilding the image.
# MoOS is an atomic OS: /usr is read-only and belongs to the bootc image, so a
# user-level install is not a workaround, it is the correct place for something
# that is not yet part of the system. When it is, `packaging/moos/moos-image/`
# has what the image build needs, and this script becomes unnecessary.
#
#   ./packaging/moos/install-local.sh            install from build/linux/.../bundle
#   ./packaging/moos/install-local.sh --uninstall
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUNDLE_SRC="$REPO/build/linux/x64/release/bundle"

PREFIX="${HOME}/.local"
APP_DIR="$PREFIX/lib/moplayer"
BIN="$PREFIX/bin/moplayer"
DESKTOP="$PREFIX/share/applications/org.moos.moplayer.desktop"
ICONS="$PREFIX/share/icons/hicolor"

if [ "${1:-}" = "--uninstall" ]; then
    rm -rf "$APP_DIR" "$BIN" "$DESKTOP"
    find "$ICONS" \( -name 'moos-moplayer.png' -o -name 'moos-moplayer.svg' \) -delete 2>/dev/null || true
    update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true
    gtk-update-icon-cache -f -t "$ICONS" 2>/dev/null || true
    echo "MoPlayer removed."
    exit 0
fi

if [ ! -x "$BUNDLE_SRC/moplayer" ]; then
    echo "install-local: no release bundle at $BUNDLE_SRC" >&2
    echo "install-local: build it first —  just build" >&2
    exit 1
fi

echo "==> bundle    -> $APP_DIR"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR"
cp -r "$BUNDLE_SRC"/. "$APP_DIR/"

echo "==> launcher  -> $BIN"
mkdir -p "$(dirname "$BIN")"
# The launcher hard-codes /usr/lib/moplayer for the image install; point it here.
sed "s|^BUNDLE=.*|BUNDLE=\"\${MOPLAYER_BUNDLE:-$APP_DIR}\"|" \
    "$REPO/packaging/moos/moplayer" > "$BIN"
chmod +x "$BIN"

echo "==> launcher entry -> $DESKTOP"
mkdir -p "$(dirname "$DESKTOP")"
# Exec must be absolute here: ~/.local/bin is not on PATH for every session type,
# and a .desktop whose Exec cannot be resolved simply does nothing when clicked.
sed "s|^Exec=moplayer|Exec=$BIN|; s|^TryExec=moplayer|TryExec=$BIN|; s|^Exec=moplayer |Exec=$BIN |" \
    "$REPO/packaging/moos/org.moos.moplayer.desktop" > "$DESKTOP"

echo "==> icons     -> $ICONS"
# `*` and not `*.png`: the scalable SVG lives under scalable/apps/ and is the one
# a 4K Kickoff actually reaches for. Globbing only the rasters left it behind,
# and the icon looked soft on exactly the displays it was meant to look best on.
for src in "$REPO"/packaging/moos/icons/hicolor/*/apps/moos-moplayer.*; do
    [ -e "$src" ] || continue
    size_dir="$(basename "$(dirname "$(dirname "$src")")")"
    mkdir -p "$ICONS/$size_dir/apps"
    cp "$src" "$ICONS/$size_dir/apps/"
done

echo "==> metadata  -> $PREFIX/share/metainfo"
mkdir -p "$PREFIX/share/metainfo"
cp "$REPO/packaging/moos/org.moos.moplayer.metainfo.xml" "$PREFIX/share/metainfo/"

update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true
gtk-update-icon-cache -f -t "$ICONS" 2>/dev/null || true
# Plasma caches .desktop files; without this the launcher can take minutes to
# appear in Kickoff, which reads as "the install did not work".
kbuildsycoca6 --noincremental >/dev/null 2>&1 || true

echo
echo "MoPlayer installed. Launch it from Kickoff, or run: moplayer"
if ! command -v moplayer >/dev/null 2>&1; then
    echo "note: $PREFIX/bin is not on your PATH — the Kickoff entry still works."
fi
