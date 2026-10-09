#!/usr/bin/env bash
# Reviewed upstream asset: https://github.com/sigstore/cosign/releases/tag/v3.1.3
# Shared by the ARM desktop and recovery builds, never run on the workstation.
set -euo pipefail

destination="${1:?pass the in-image cosign destination}"
version="3.1.3"
digest="c5d324e091826b0d7a78eb16fef316450b4eb9aaec045611c08ba06f5e73220a"
temporary="$(mktemp)"
trap 'rm -f -- "$temporary"' EXIT

curl --fail --show-error --location --connect-timeout 15 --max-time 600 \
    --proto '=https' --proto-redir '=https' \
    "https://github.com/sigstore/cosign/releases/download/v${version}/cosign-linux-arm64" \
    -o "$temporary"
# The bytes must match the reviewed pin before they are executable or installed.
printf '%s  %s\n' "$digest" "$temporary" | sha256sum --check --status
chmod 0700 "$temporary"
details="$("$temporary" version)"
grep -Eq "^GitVersion:[[:space:]]+v${version//./\.}$" <<<"$details"
grep -Eq '^Platform:[[:space:]]+linux/arm64$' <<<"$details"
install -D -m0755 "$temporary" "$destination"
printf 'MoOS ARM verifier: cosign %s; reviewed SHA-256 verified.\n' "$version"
