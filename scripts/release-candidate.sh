#!/usr/bin/env bash
# One command per release batch (RELEASE.md, "دفعات الإصدار").
#
# Builds the signed candidate from one fixed revision, runs every boot proof in parallel on the
# exact digests the build signed, waits for all of them, and prints the promotion command — or, with
# --promote, dispatches it after re-checking that main still carries the candidate's exact tree.
#
# It never re-runs a job (promotion accepts run_attempt 1 only) and never moves a tag itself.
#
#   scripts/release-candidate.sh                 # build + proofs from main, print promotion
#   scripts/release-candidate.sh --promote       # ... and promote when every x86 proof passed
#   scripts/release-candidate.sh --ref BRANCH    # prove a branch without promoting (no --promote)
set -euo pipefail

ref="main"
promote=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --ref) ref="${2:?--ref needs a branch}"; shift 2 ;;
        --promote) promote=1; shift ;;
        -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
        *) echo "release-candidate: unknown argument: $1" >&2; exit 2 ;;
    esac
done
if [ "$promote" -eq 1 ] && [ "$ref" != "main" ]; then
    echo "release-candidate: --promote is only valid for main" >&2
    exit 2
fi
for tool in gh git; do
    command -v "$tool" >/dev/null || { echo "release-candidate: $tool is required" >&2; exit 2; }
done

git fetch -q origin "$ref"
revision="$(git rev-parse "origin/$ref")"
echo "candidate revision: $revision ($ref)"
work="$(mktemp -d "${TMPDIR:-/var/tmp}/moos-release-candidate.XXXXXX")"
trap 'rm -rf -- "$work"' EXIT

dispatch() {
    local workflow="$1"; shift
    local output url id
    output="$(gh workflow run "$workflow" --ref "$ref" "$@" 2>&1)" || {
        echo "release-candidate: dispatch of $workflow failed: $output" >&2
        return 1
    }
    url="$(grep -Eo 'https://github\.com/[^ ]+/actions/runs/[0-9]+' <<<"$output" | tail -n1)"
    [ -n "$url" ] || { echo "release-candidate: $workflow returned no run URL: $output" >&2; return 1; }
    id="${url##*/}"
    # A run for another revision would make every later proof meaningless.
    [ "$(gh run view "$id" --json headSha --jq .headSha)" = "$revision" ] || {
        echo "release-candidate: run $id of $workflow is not on $revision" >&2
        return 1
    }
    echo "$id"
}

wait_run() {
    local id="$1" label="$2" state="" try
    gh run watch "$id" --exit-status --interval 60 >/dev/null 2>&1 || true
    # `gh run watch` also exits non-zero when the API is unreachable. The
    # 2026-09-17 W2 release printed FAIL for two QCOW2 proofs that had in fact
    # succeeded, only because the host lost api.github.com while watching. The
    # verdict is therefore the run's own recorded status, re-read until the API
    # answers and the run is complete — never the watcher's exit code.
    for try in $(seq 1 120); do
        state="$(gh run view "$id" --json status,conclusion,attempt \
            --jq '.status + " " + (.conclusion // "") + " " + (.attempt|tostring)' 2>/dev/null)" || state=""
        case "$state" in
            "completed "*) break ;;
        esac
        sleep 60
    done
    if [ "$state" = "completed success 1" ]; then
        echo "PASS $label (run $id)"
        return 0
    fi
    echo "FAIL $label (run $id, state: ${state:-unreadable})"
    return 1
}

build_id="$(dispatch build.yml)"
echo "signed build: run $build_id"
wait_run "$build_id" "signed x86 build" || exit 1

declare -A ref_of
for edition in moos moos-nvidia moos-cloud; do
    gh run download "$build_id" -n "moos-candidate-proof-$edition" -D "$work/$edition" >/dev/null
    proof="$work/$edition/candidate.txt"
    repository="$(sed -n 's/^repository=//p' "$proof")"
    digest="$(sed -n 's/^digest=//p' "$proof")"
    [ "$(sed -n 's/^revision=//p' "$proof")" = "$revision" ] \
        && [ "$(sed -n 's/^signature=//p' "$proof")" = verified ] \
        && [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || {
            echo "release-candidate: $edition candidate proof is not a verified $revision digest" >&2
            exit 1
        }
    ref_of[$edition]="$repository@$digest"
    echo "candidate $edition: ${ref_of[$edition]}"
done

disk_id="$(dispatch build-disk.yml -f "image-ref=${ref_of[moos]}")"
nvidia_disk_id="$(dispatch build-disk.yml -f "image-ref=${ref_of[moos-nvidia]}")"
cloud_disk_id="$(dispatch build-disk.yml -f "image-ref=${ref_of[moos-cloud]}")"
iso_id="$(dispatch build-iso.yml -f "image_ref=${ref_of[moos]}")"
arm_id="$(dispatch build-arm.yml)"
echo "proofs: generic $disk_id, nvidia $nvidia_disk_id, cloud $cloud_disk_id, iso $iso_id, arm $arm_id"

declare -A pid_of
for pair in "generic-qcow2:$disk_id" "nvidia-qcow2:$nvidia_disk_id" "cloud-qcow2:$cloud_disk_id" "iso:$iso_id" "arm:$arm_id"; do
    wait_run "${pair#*:}" "${pair%%:*}" > "$work/${pair%%:*}.result" &
    pid_of[${pair%%:*}]=$!
done
x86_ok=1
for label in generic-qcow2 nvidia-qcow2 cloud-qcow2 iso arm; do
    status=0
    wait "${pid_of[$label]}" || status=$?
    cat "$work/$label.result"
    if [ "$status" -ne 0 ] && [ "$label" != arm ]; then x86_ok=0; fi
done

promotion=(gh workflow run promote-x86.yml --ref main
    -f "revision=$revision" -f "build_run_id=$build_id" -f "disk_run_id=$disk_id"
    -f "nvidia_disk_run_id=$nvidia_disk_id" -f "cloud_disk_run_id=$cloud_disk_id" -f "iso_run_id=$iso_id")

if [ "$x86_ok" -ne 1 ]; then
    echo "release-candidate: at least one x86 proof failed; nothing is promoted" >&2
    exit 1
fi
printf 'promotion:'; printf ' %q' "${promotion[@]}"; echo
if [ "$promote" -eq 1 ]; then
    git fetch -q origin main
    [ "$(git rev-parse "$revision^{tree}")" = "$(git rev-parse 'origin/main^{tree}')" ] || {
        echo "release-candidate: main moved away from the candidate tree; start a new cycle" >&2
        exit 1
    }
    "${promotion[@]}"
fi
