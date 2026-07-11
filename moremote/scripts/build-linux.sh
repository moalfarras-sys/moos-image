#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DOTNET=${DOTNET:-$HOME/.local/share/dotnet/dotnet}
OUT="$ROOT/dist-linux"
rm -rf "$OUT"
"$DOTNET" publish "$ROOT/agent-linux/MoRemoteLinux.csproj" -c Release -r linux-x64 --self-contained true -o "$OUT"
printf 'Built Linux application: %s\n' "$OUT/MoRemotePersonal"
