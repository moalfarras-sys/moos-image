#!/usr/bin/bash
# Keep Mo Remote's HTTPS certificate present and current.
#
# HTTPS is not cosmetic here. A phone's browser only exposes WebCodecs — and therefore H.264 — and
# the native clipboard in a SECURE CONTEXT, so over plain http the stream silently falls back to
# JPEG and copy/paste stops working. Measured on this machine: JPEG frames of 1.18 MB at 1080p
# against H.264's ~6 Mbit/s for a sharper picture, and every "the remote is slow and blurry"
# report traced back to exactly that. A Tailscale certificate is free, needs no open port and no
# public DNS, so the only reason this ever ran on http was that nothing ever provisioned one:
# TlsManager.Provision() existed and had no caller.
set -euo pipefail

data_dir="${XDG_DATA_HOME:-$HOME/.local/share}/MoRemotePersonal"
tls_dir="$data_dir/tls"

# Only for someone who has actually set Mo Remote up. Provisioning a certificate for a service the
# user has never opened would be doing work — and touching an external CA — on their behalf for no
# reason.
[ -f "$data_dir/config.dat" ] || exit 0

# No tailnet name, no certificate. Exit quietly: this runs on a timer, and a machine that is not on
# Tailscale yet is not a machine with a problem.
host="$(tailscale status --json 2>/dev/null \
        | python3 -c 'import sys,json; print((json.load(sys.stdin).get("Self") or {}).get("DNSName","").rstrip("."))' \
        2>/dev/null || true)"
[ -n "$host" ] || exit 0

mkdir -p "$tls_dir"
fingerprint() { if [ -f "$1" ]; then sha256sum <"$1"; else echo none; fi; }
before="$(fingerprint "$tls_dir/cert.crt")"

# tailscale reuses a still-valid certificate and only re-issues as expiry approaches, so running
# this daily is cheap and keeps renewal from ever becoming a thing the user has to remember.
if ! tailscale cert --cert-file "$tls_dir/cert.crt" --key-file "$tls_dir/cert.key" "$host" >/dev/null 2>&1; then
    # Most likely HTTPS is not enabled for this tailnet. Nothing to repair from here, and plain
    # HTTP still works, so this is not a failure worth a red unit.
    exit 0
fi

printf '%s' "$host" >"$tls_dir/host.txt"
chmod 600 "$tls_dir/cert.key" "$tls_dir/host.txt" 2>/dev/null || true

# Kestrel reads the certificate once, at startup, so a renewed one only reaches the phone after a
# restart. Restart only when it actually changed, and only if the agent is running — a timer that
# bounces a live remote session every day would be its own bug.
if [ "$before" != "$(fingerprint "$tls_dir/cert.crt")" ] \
   && systemctl --user is-active --quiet mo-remote-personal.service; then
    systemctl --user restart mo-remote-personal.service || true
fi
exit 0
