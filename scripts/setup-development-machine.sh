#!/usr/bin/env bash
# Read-only workstation preflight. SDK installation stays an explicit task;
# image builds already use the pinned toolchains in the Containerfiles.
set -euo pipefail

usage() {
    printf '%s\n' \
        'Usage: bash scripts/setup-development-machine.sh [--check]' \
        'Inspect the development host without installing, repairing or launching apps.' \
        'VS Code Flatpak delegates to the host using flatpak-spawn.' \
        'Exit 0: inspection completed with source/build tools present; notes may remain.' \
        'Exit 1: a required source/build tool is missing or host access failed.' \
        'This is a capability inventory, not an image, SDK build or hardware acceptance test.'
}

case "${1:---check}" in
    --help|-h) usage; exit 0 ;;
    --check) ;;
    *) usage >&2; exit 2 ;;
esac
if (( $# > 1 )); then usage >&2; exit 2; fi

# /usr and /var inside the editor are the Flatpak runtime, not the installed OS.
# Resolve the shared checkout before delegating; never pass shell code or secrets.
script_path="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/$(basename -- "${BASH_SOURCE[0]}")"
if [[ -f /.flatpak-info ]]; then
    if ! command -v flatpak-spawn >/dev/null 2>&1; then
        printf 'FAIL  Host access: flatpak-spawn is unavailable. Run this check in Konsole.\n' >&2
        exit 1
    fi
    printf 'INFO  VS Code Flatpak detected; inspecting the host.\n'
    exec flatpak-spawn --host bash "$script_path" --check
fi

missing=0
note_count=0
pass() { printf 'OK    %-19s %s\n' "$1" "$2"; }
note() { printf 'NOTE  %-19s %s\n' "$1" "$2"; note_count=$((note_count + 1)); }
fail() { printf 'FAIL  %-19s %s\n' "$1" "$2"; missing=$((missing + 1)); }

printf 'MoOS development workstation — read-only capability check\n'
for dev_tool in git bash python3 just podman buildah jq; do
    if dev_path="$(command -v "$dev_tool")" && [[ -x "$dev_path" ]]; then
        pass "$dev_tool" "$dev_path"
    else
        fail "$dev_tool" 'Missing source/image-build prerequisite; provision before running its recipe.'
    fi
done

for dev_tool in node npm; do
    if dev_path="$(command -v "$dev_tool")" && [[ -x "$dev_path" ]]; then
        pass "$dev_tool" "$dev_path (Mo Remote web tooling)"
    else
        note "$dev_tool" 'Needed for native Mo Remote web development; image build uses its own toolchain.'
    fi
done

for dev_tool in rg shellcheck; do
    if dev_path="$(command -v "$dev_tool")" && [[ -x "$dev_path" ]]; then
        pass "$dev_tool" "$dev_path"
    else
        note "$dev_tool" 'Optional host CLI absent; an editor extension does not install a host command.'
    fi
done

# Do not invoke moos-verify-origin: its normal job can repair the installed origin.
# Instead use the same positive official-reference grammar against the actual
# booted .origin file. A local, foreign or unreadable origin is never called signed.
signed_re='^ostree-image-signed:docker://ghcr\.io/moalfarras-sys/(moos|moos-nvidia|moos-cloud|moos-arm)(@sha256:[0-9a-f]{64}|:[A-Za-z0-9][A-Za-z0-9._-]*)$'
if command -v rpm-ostree >/dev/null 2>&1 && command -v jq >/dev/null 2>&1 \
        && command -v timeout >/dev/null 2>&1; then
    status="$(timeout 10 rpm-ostree status --json 2>/dev/null || true)"
    booted="$(jq -r '
        first(.deployments[]? | select(.booted == true)) as $d
        | [$d.osname, $d.checksum, ($d.serial | tostring)] | @tsv
    ' <<<"$status" 2>/dev/null || true)"
    IFS=$'\t' read -r stateroot checksum serial <<<"$booted"
    if [[ "$stateroot" =~ ^[A-Za-z0-9._-]+$ && "$stateroot" != . && "$stateroot" != .. \
            && "$checksum" =~ ^[0-9a-f]{64}$ && "$serial" =~ ^[0-9]+$ ]]; then
        origin="/ostree/deploy/${stateroot}/deploy/${checksum}.${serial}.origin"
        if [[ -r "$origin" ]]; then
            ref="$(sed -n 's/^container-image-reference=//p' "$origin")"
            if [[ "$ref" =~ $signed_re ]]; then
                pass 'Booted origin' 'Official MoOS signature-enforcing transport (read from deployment origin).'
            else
                note 'Booted origin' 'Local, unverified or foreign origin; no changes made.'
            fi
        else
            note 'Booted origin' 'Origin file is unreadable; signature enforcement not proven.'
        fi
    else
        note 'Booted origin' 'No valid booted deployment found; signature enforcement not proven.'
    fi
else
    note 'Booted origin' 'rpm-ostree/jq/timeout unavailable; installed-origin check not possible.'
fi

# / is a small immutable composefs view; /var is on the actual writable disk.
if disk_free_kib="$(LC_ALL=C df -Pk /var 2>/dev/null | awk 'NR == 2 {print $4}')" \
        && [[ "$disk_free_kib" =~ ^[0-9]+$ ]]; then
    disk_free_gib=$((disk_free_kib / 1024 / 1024))
    if (( disk_free_gib >= 60 )); then
        pass '/var free space' "${disk_free_gib} GiB available; build artifacts belong on this disk."
    else
        note '/var free space' "${disk_free_gib} GiB available; allow at least 60 GiB for image/VM work (estimate)."
    fi
else
    note '/var free space' 'Unable to measure the writable disk.'
fi

if [[ -r /dev/kvm && -w /dev/kvm ]]; then
    pass 'KVM device' 'Current user can access /dev/kvm; a VM boot is still required.'
else
    note 'KVM device' 'Current user cannot access /dev/kvm; tests/boot-in-vm.sh needs KVM.'
fi

if [[ -x /usr/bin/moos-qml-shell ]]; then
    pass 'MoOS QML runtime' '/usr/bin/moos-qml-shell (presence only; no app launched)'
else
    note 'MoOS QML runtime' 'Native MoOS QML runner absent; runtime preview needs an installed MoOS image.'
fi
qml_lint=''
for dev_tool in qmllint6 qmllint-qt6 qmllint /usr/lib64/qt6/bin/qmllint /usr/lib/qt6/bin/qmllint; do
    if dev_path="$(command -v "$dev_tool")" && [[ -x "$dev_path" ]]; then
        qml_lint="$dev_path"
        break
    fi
done
if [[ -n "$qml_lint" ]]; then
    pass 'QML lint' "$qml_lint"
else
    note 'QML lint' 'Host Qt development tools absent; image QML launch gates still run during builds.'
fi

dotnet_path=''
for dev_tool in dotnet "${HOME}/.local/share/dotnet/dotnet" "${HOME}/.dotnet/dotnet"; do
    if dev_path="$(command -v "$dev_tool")" && [[ -x "$dev_path" ]]; then
        dotnet_path="$dev_path"
        break
    fi
done
if [[ -n "$dotnet_path" ]] && command -v timeout >/dev/null 2>&1; then
    # --list-sdks is handled by the native muxer, without SDK first-run setup.
    sdk_list="$(timeout 10 "$dotnet_path" --list-sdks 2>/dev/null || true)"
    if [[ "$sdk_list" =~ (^|$'\n')10\.[0-9]+\.[0-9]+[[:space:]] ]]; then
        pass '.NET 10 SDK' "$dotnet_path; add its directory to PATH for just dotnet-check."
    else
        note '.NET SDK' 'No .NET 10 SDK found; an editor-provided runtime is not sufficient.'
    fi
else
    note '.NET SDK' 'No native SDK found on PATH, ~/.local/share/dotnet or ~/.dotnet; image builds supply .NET 10.'
fi

flutter_path=''
for dev_tool in flutter "${HOME}/flutter/bin/flutter"; do
    if dev_path="$(command -v "$dev_tool")" && [[ -x "$dev_path" ]]; then
        flutter_path="$dev_path"
        break
    fi
done
if [[ -n "$flutter_path" ]]; then
    pass 'Flutter launcher' "$flutter_path (presence only; SDK/dependency readiness not proven)"
else
    note 'Flutter launcher' 'Absent from PATH and ~/flutter/bin; image builds supply the MoPlayer toolchain.'
fi
# flutter --version/doctor can download or update SDK caches; never run them here.

if command -v gh >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
    if GH_PROMPT_DISABLED=1 timeout 15 gh auth status --hostname github.com >/dev/null 2>&1; then
        pass 'GitHub auth' 'Configured and accepted; account/token output suppressed.'
    else
        note 'GitHub auth' 'Unavailable or validation failed; run gh auth login in a host terminal when publishing.'
    fi
else
    note 'GitHub auth' 'gh/timeout unavailable; GitHub access not checked.'
fi

printf '\nEditor recommendations: .vscode/extensions.json (install only for the components you edit).\n'
printf 'Next checks: just check; just build (or the matching edition); just dotnet-check after SDK setup.\n'
printf 'Result: %s missing source/build prerequisites; %s notes. No settings or packages changed.\n' "$missing" "$note_count"
(( missing == 0 ))
