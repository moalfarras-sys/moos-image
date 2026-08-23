#!/usr/bin/env bash
# x86 release-disk entry point; policy lives in the shared disk sealer.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$script_dir/seal_release_qcow2.sh" x86_64 "$@"
