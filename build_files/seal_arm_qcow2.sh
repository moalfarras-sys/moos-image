#!/usr/bin/env bash
# Compatibility entry point for the ARM release workflow.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$script_dir/seal_release_qcow2.sh" arm64 "$@"
