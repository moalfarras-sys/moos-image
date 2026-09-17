#!/usr/bin/env bash
# Run gates against the UNCOMMITTED working tree when the checkout sits on a filesystem that
# cannot hold it faithfully — a Windows drive seen from WSL (drvfs) reports every file as
# executable, so tests/test_exec_bits.py and the unit-mode checks would pass or fail for nothing.
#
# The tree is mirrored onto a native filesystem and given the modes GIT records, then the named
# gates run there with no display, no session bus and an isolated locale.
#
#   scripts/review/mirror-gates.sh                       # bash tests/repo-gates.sh
#   scripts/review/mirror-gates.sh tests/test_app_drop.py tests/test_moos_inspect.py
#   MOOS_MIRROR=/var/tmp/moos-work scripts/review/mirror-gates.sh …
set -uo pipefail
SRC="$(cd "$(dirname "$0")/../.." && pwd)"
DST="${MOOS_MIRROR:-$HOME/.cache/moos-mirror}"
mkdir -p "$DST"
rsync -a --delete --exclude '.git/' --exclude 'moplayer/build/' --exclude 'node_modules/' "$SRC"/ "$DST"/
cd "$DST"
find . -type f -exec chmod 0644 {} + 2>/dev/null
git -C "$SRC" ls-files -s | awk '$1=="100755"{ $1=$2=$3=""; sub(/^ +/,""); print }' \
    | while IFS= read -r file; do [ -f "$file" ] && chmod 0755 "$file"; done
# A script added since the last commit is not in the index yet: give `#!` files under the two
# executable directories their bit, which is exactly the rule tests/test_exec_bits.py enforces.
for dir in system_files/usr/bin system_files/usr/libexec; do
    find "$dir" -type f -exec sh -c 'head -c2 "$1" | grep -q "^#!" && chmod 0755 "$1"' _ {} \; 2>/dev/null
done
unset DISPLAY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS
export LC_ALL=C.UTF-8
[ "$#" -gt 0 ] || set -- tests/repo-gates.sh
status=0
for gate in "$@"; do
    case "$gate" in *.sh) runner=bash ;; *) runner=python3 ;; esac
    started=$(date +%s)
    if "$runner" "$gate" > "$DST/.last-gate.log" 2>&1; then
        printf 'PASS %-52s %3ss  %s\n' "$gate" "$(( $(date +%s) - started ))" "$(tail -1 "$DST/.last-gate.log" | cut -c1-90)"
    else
        printf 'FAIL %s\n' "$gate"
        tail -30 "$DST/.last-gate.log" | sed 's/^/     /'
        status=1
    fi
done
exit "$status"
