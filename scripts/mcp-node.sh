#!/usr/bin/env bash
# Run an npx-based MCP server from wherever the agent happens to live.
#
# WHY THIS EXISTS
#
# On the MoOS development station the coding agent runs inside the VS Code
# FLATPAK, whose /usr is the runtime's, not the machine's. Node is installed on
# the host (/usr/bin/npx), so `npx` works in a terminal and the agent still saw
#
#     chrome-devtools (ENOENT): "Executable not found in $PATH: npx"
#     image-gen (ENOENT): "Executable not found in $PATH: npx"
#     sequential-thinking (ENOENT): "Executable not found in $PATH: npx"
#
# — three servers dead in every session, which is why nobody used them. Off the
# station (Windows + WSL, a plain Linux checkout, CI) there is no Flatpak and
# `npx` is simply on PATH.
#
# So this picks whichever is true here: npx if it resolves, otherwise the host's
# npx through the Flatpak portal. It changes no server's arguments and adds no
# credential path; it only answers "where does node live from here".
set -euo pipefail

if command -v npx >/dev/null 2>&1; then
    exec npx "$@"
fi
if command -v flatpak-spawn >/dev/null 2>&1 && flatpak-spawn --host true 2>/dev/null; then
    exec flatpak-spawn --host npx "$@"
fi

cat >&2 <<'MESSAGE'
MoOS: no Node runtime for this MCP server.
  On MoOS/Fedora:  sudo rpm-ostree install nodejs-npm   (then reboot)
  Elsewhere:       install Node 20 or newer so `npx` is on PATH.
MESSAGE
exit 127
