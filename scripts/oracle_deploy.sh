#!/usr/bin/env bash
# Oracle MoOS ARM deploy helper — free tier A1 only.
# Requires valid ~/.oci/config (tenancy + region filled in).
set -euo pipefail

OCI="${OCI_CLI:-$HOME/.local/share/oci-venv/bin/oci}"
CONFIG="${OCI_CONFIG:-$HOME/.oci/config}"
PROOF_DIR="/var/home/moos/Desktop/MoOS-Release/PROOF/ORACLE"
CHECKPOINT="/var/home/moos/Desktop/MoOS-Release/ORACLE-PROOF.txt"

# Signed ARM digest from CI run 32641534900 @ 196f8679
TARGET_DIGEST="sha256:e1ace22c3a6a207f2bcd3507fe98f2071bdb9a9d6bd3bfbf7de03e1d0de28601"
TARGET_REF="ghcr.io/moalfarras-sys/moos-arm@${TARGET_DIGEST}"
BOOTSTRAP_QCOW="${MOOS_ORACLE_QCOW:-/var/home/moos/moos-release-build/moos-arm-bootstrap.qcow2}"
SHAPE="VM.Standard.A1.Flex"
OCPUS="${MOOS_ORACLE_OCPUS:-2}"
MEMORY_GB="${MOOS_ORACLE_MEMORY_GB:-12}"
BOOT_GB="${MOOS_ORACLE_BOOT_GB:-50}"
COMPARTMENT="${MOOS_ORACLE_COMPARTMENT:-}"
BUCKET="${MOOS_ORACLE_BUCKET:-moos-arm-import}"
INSTANCE_NAME="${MOOS_ORACLE_INSTANCE:-moos-arm-oracle}"

log() { printf '[oracle-deploy] %s\n' "$*"; }
die() { log "FATAL: $*"; exit 1; }

require_oci() {
    [ -x "$OCI" ] || die "OCI CLI missing at $OCI"
    grep -q '__TENANCY_OCID_REQUIRED__\|__REGION_REQUIRED__' "$CONFIG" && \
        die "Fill tenancy OCID and region in $CONFIG first"
}

verify_free_tier() {
    log "Checking tenancy limits and existing A1 usage..."
    "$OCI" limits resource-availability list \
        --service-name compute \
        --limit-name standard-a1-core-count \
        --availability-domain "$(ad)" \
        --compartment-id "$(tenancy)" \
        --output table
    "$OCI" compute instance list --compartment-id "$(compartment)" --all \
        --query 'data[*].{name:"display-name",shape:shape,state:"lifecycle-state"}' \
        --output table
}

tenancy() {
    awk -F= '/^tenancy=/{print $2; exit}' "$CONFIG"
}

compartment() {
    if [ -n "$COMPARTMENT" ]; then echo "$COMPARTMENT"; return; fi
    "$OCI" iam compartment list --compartment-id-in-subtree true \
        --query 'data[?name==`root`].id | [0]' --raw-output
}

ad() {
    "$OCI" iam availability-domain list --compartment-id "$(tenancy)" \
        --query 'data[0].name' --raw-output
}

cmd="${1:-verify}"
case "$cmd" in
    verify)
        require_oci
        log "Region: $(awk -F= '/^region=/{print $2}' "$CONFIG")"
        verify_free_tier
        ;;
    upload-import)
        require_oci
        [ -f "$BOOTSTRAP_QCOW" ] || die "missing qcow2: $BOOTSTRAP_QCOW"
        log "Ensuring bucket $BUCKET..."
        "$OCI" os bucket create --compartment-id "$(compartment)" --name "$BUCKET" 2>/dev/null || true
        object="moos-arm-bootstrap.qcow2"
        log "Uploading qcow2 (this takes a while)..."
        "$OCI" os object put --bucket-name "$BUCKET" --file "$BOOTSTRAP_QCOW" --name "$object" --part-size 128
        par=$("$OCI" os preauth-request create --access-type ObjectRead \
            --bucket-name "$BUCKET" --name moos-import-par --object-name "$object" \
            --time-expires "$(date -u -d '+2 hours' +%Y-%m-%dT%H:%M:%SZ)" \
            --query 'data."access-uri"' --raw-output)
        region=$(awk -F= '/^region=/{print $2}' "$CONFIG")
        namespace=$("$OCI" os ns get --query 'data' --raw-output)
        url="https://objectstorage.${region}.oraclecloud.com${par}"
        log "Import URL ready (PAR, 2h)"
        image_id=$("$OCI" compute image import-from-object \
            --compartment-id "$(compartment)" \
            --display-name "moos-arm-bootstrap" \
            --launch-mode PARAVIRTUALIZED \
            --operating-system "Oracle Linux" \
            --source-object-name "$object" \
            --bucket-name "$BUCKET" \
            --namespace-name "$namespace" \
            --query 'data.id' --raw-output 2>/dev/null || true)
        echo "IMAGE_ID=${image_id:-pending_manual_import}"
        echo "PAR_URL=${url}"
        ;;
    *)
        echo "usage: $0 verify|upload-import" >&2
        exit 2
        ;;
esac
