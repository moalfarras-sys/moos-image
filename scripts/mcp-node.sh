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

runner=()
if command -v npx >/dev/null 2>&1; then
    runner=(npx)
elif command -v flatpak-spawn >/dev/null 2>&1 && flatpak-spawn --host true 2>/dev/null; then
    runner=(flatpak-spawn --host npx)
fi

if ((${#runner[@]})); then
    # VS Code launched from the desktop need not inherit .bashrc exports. If
    # MCP expanded its default browser path, reuse mcp-setup's stable browser.
    # Never override an explicit caller path or read a credential/profile file.
    args=("$@")
    for ((i = 0; i + 1 < ${#args[@]}; i++)); do
        if [[ ${args[i]} == --executablePath &&
              ${args[i+1]} == /opt/google/chrome/chrome &&
              -x ${HOME}/.cache/moos-mcp/chrome ]]; then
            args[i+1]="${HOME}/.cache/moos-mcp/chrome"
        fi
    done
    exec "${runner[@]}" "${args[@]}"
fi

cat >&2 <<'MESSAGE'
MoOS: no Node runtime for this MCP server.
  On the MoOS station: run `just workstation-check` in a host terminal.
  Install the development Node runtime in user space or a development container;
  do not layer packages onto the signed operating-system deployment.
  Elsewhere: install Node 20 or newer so `npx` is on PATH.
MESSAGE
exit 127
