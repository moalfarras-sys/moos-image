#!/usr/bin/env bash
# Prove the exact packaged three-drive recovery menu; never install.
set -euo pipefail
exec python3 "$(dirname "$(readlink -f "$0")")/arm_recovery_boot.py" "$@"
