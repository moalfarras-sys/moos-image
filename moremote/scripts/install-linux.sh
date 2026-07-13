#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
APP="$HOME/.local/lib/mo-remote-personal"
DATA="$HOME/.local/share/applications"
SYSTEMD="$HOME/.config/systemd/user"
"$ROOT/scripts/build-linux.sh"
mkdir -p "$APP" "$DATA" "$SYSTEMD" "$HOME/.local/share/icons/hicolor/512x512/apps"
rm -rf "$APP"/*
cp -a "$ROOT/dist-linux/." "$APP/"
cp "$ROOT/Logo.png" "$HOME/.local/share/icons/hicolor/512x512/apps/moos-pc-remote.png"
sed "s|@APP@|$APP|g" "$ROOT/linux/mo-remote-personal.desktop.in" > "$DATA/mo-remote-personal.desktop"
sed "s|@APP@|$APP|g" "$ROOT/linux/mo-remote-personal.service.in" > "$SYSTEMD/mo-remote-personal.service"
chmod 755 "$APP/MoRemotePersonal" "$DATA/mo-remote-personal.desktop"
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload
  systemctl --user enable mo-remote-personal.service
  # --now does not restart an already-running unit, leaving old binaries and
  # environment variables active after an upgrade.
  systemctl --user restart mo-remote-personal.service
elif command -v flatpak-spawn >/dev/null 2>&1; then
  flatpak-spawn --host systemctl --user daemon-reload
  flatpak-spawn --host systemctl --user enable mo-remote-personal.service
  flatpak-spawn --host systemctl --user restart mo-remote-personal.service
else
  printf 'Warning: enable mo-remote-personal.service manually.\n' >&2
fi
command -v update-desktop-database >/dev/null && update-desktop-database "$DATA" || true
printf 'Installed Mo Remote Personal for Linux.\n'
