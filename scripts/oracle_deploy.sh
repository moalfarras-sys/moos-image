#!/usr/bin/env bash
# Oracle MoOS ARM deploy helper — free tier A1 only.
# Requires valid ~/.oci/config (tenancy + region filled in).
set -euo pipefail

OCI="${OCI_CLI:-$HOME/.local/bin/oci}"
CONFIG="${OCI_CONFIG:-$HOME/.oci/config}"
BOOTSTRAP_QCOW="${MOOS_ORACLE_QCOW:-/var/home/moos/moos-release-build/moos-arm-bootstrap.qcow2}"
SHAPE="VM.Standard.A1.Flex"
OCPUS="${MOOS_ORACLE_OCPUS:-1}"
MEMORY_GB="${MOOS_ORACLE_MEMORY_GB:-6}"
BOOT_GB="${MOOS_ORACLE_BOOT_GB:-50}"
COMPARTMENT="${MOOS_ORACLE_COMPARTMENT:-}"
BUCKET="${MOOS_ORACLE_BUCKET:-moos-arm-import}"
INSTANCE_NAME="${MOOS_ORACLE_INSTANCE:-moos-arm-oracle}"
CREDENTIAL_FILE="${MOOS_ORACLE_CREDENTIAL_FILE:-$HOME/.local/share/moos-oracle/management-password.credential}"
SSH_PUBLIC_KEY_FILE="${MOOS_ORACLE_SSH_PUBLIC_KEY:-$HOME/.ssh/moos_cloud.pub}"
RETRY_SECONDS="${MOOS_ORACLE_RETRY_SECONDS:-120}"
MAX_CYCLES="${MOOS_ORACLE_MAX_CYCLES:-0}"
ORACLE_METADATA_DIR=""

log() { printf '[oracle-deploy] %s\n' "$*"; }
die() { log "FATAL: $*"; exit 1; }

require_oci() {
    [ -x "$OCI" ] || die "OCI CLI missing at $OCI"
    [ -r "$CONFIG" ] || die "OCI config is missing or unreadable: $CONFIG"
    if grep -q '__TENANCY_OCID_REQUIRED__\|__REGION_REQUIRED__' "$CONFIG"; then
        die "Fill tenancy OCID and region in $CONFIG first"
    fi
    # Do not leave the function with grep's expected no-match status. Under
    # `set -e`, the old implementation exited silently here on every valid
    # configuration before it ran a single OCI request.
    return 0
}

verify_free_tier() {
    log "Checking tenancy quotas and existing A1 usage (host capacity is known only by a launch attempt)..."
    while IFS= read -r availability_domain; do
        [ -n "$availability_domain" ] || continue
        log "Availability domain: $availability_domain"
        "$OCI" limits resource-availability get \
            --service-name compute \
            --limit-name standard-a1-core-count \
            --availability-domain "$availability_domain" \
            --compartment-id "$(compartment)" \
            --query 'data.{available:available,used:used,"fractional-availability":"fractional-availability"}' \
            --output table
    done < <(ads)
    "$OCI" compute instance list --compartment-id "$(compartment)" --all \
        --query 'data[*].{name:"display-name",shape:shape,state:"lifecycle-state"}' \
        --output table
}

tenancy() {
    awk -F= '/^tenancy=/{gsub(/[[:space:]]/, "", $2); print $2; exit}' "$CONFIG"
}

compartment() {
    if [ -n "$COMPARTMENT" ]; then echo "$COMPARTMENT"; return; fi
    # The tenancy OCID is the root compartment OCID. There is no child
    # compartment named "root" for the old query to discover.
    tenancy
}

ads() {
    "$OCI" iam availability-domain list --compartment-id "$(tenancy)" \
        --query 'data[*].name' --raw-output | python3 -c \
        'import json, sys; print("\n".join(json.load(sys.stdin)))'
}

fault_domains() {
    local availability_domain="$1"
    "$OCI" iam fault-domain list \
        --compartment-id "$(tenancy)" \
        --availability-domain "$availability_domain" \
        --query 'data[*].name' --raw-output | python3 -c \
        'import json, sys; print("\n".join(json.load(sys.stdin)))'
}

ensure_uefi_capability() {
    local image_id="$1" schema_id global_version schema_data firmware
    [ -n "$image_id" ] && [ "$image_id" != null ] || die "missing custom image OCID"

    # OCI inferred BIOS for the boot-proven AArch64 QCOW2. An Ampere instance
    # then looked RUNNING in the control plane while producing no serial output,
    # no SSH and no health signal. Firmware cannot be overridden at instance
    # launch; it must be fixed on the custom image capability schema.
    schema_data='{"Compute.Firmware":{"defaultValue":"UEFI_64","descriptorType":"enumstring","source":"IMAGE","values":["BIOS","UEFI_64"]}}'
    global_version=$("$OCI" compute global-image-capability-schema list --all \
        --query 'data[0]."current-version-name"' --raw-output)
    schema_id=$("$OCI" compute image-capability-schema list --image-id "$image_id" \
        --query 'data[0].id' --raw-output)

    if [ -n "$schema_id" ] && [ "$schema_id" != null ]; then
        "$OCI" compute image-capability-schema update \
            --image-capability-schema-id "$schema_id" \
            --schema-data "$schema_data" \
            --force \
            --wait-for-state ACTIVE >/dev/null
    else
        "$OCI" compute image-capability-schema create \
            --compartment-id "$(compartment)" \
            --image-id "$image_id" \
            --global-image-capability-schema-version-name "$global_version" \
            --display-name moos-arm-uefi64 \
            --schema-data "$schema_data" \
            --wait-for-state ACTIVE >/dev/null
    fi

    firmware=$("$OCI" compute image-capability-schema list --image-id "$image_id" \
        --query 'data[0]."schema-data"."Compute.Firmware"."default-value"' --raw-output)
    [ "$firmware" = UEFI_64 ] || die "custom image firmware capability is $firmware, expected UEFI_64"
    log "Custom image capability verified: firmware=UEFI_64"
}

credential_init() {
    command -v systemd-creds >/dev/null 2>&1 || die "systemd-creds is required"
    command -v openssl >/dev/null 2>&1 || die "openssl is required"
    if [ -e "$CREDENTIAL_FILE" ] && [ "${MOOS_ORACLE_ROTATE_CREDENTIAL:-0}" != 1 ]; then
        die "credential already exists: $CREDENTIAL_FILE (set MOOS_ORACLE_ROTATE_CREDENTIAL=1 to replace it)"
    fi
    install -d -m0700 "$(dirname "$CREDENTIAL_FILE")"
    local password
    password=$(openssl rand -base64 27 | tr -d '\n')
    printf '%s' "$password" | systemd-creds encrypt \
        --name=moos-oracle-management-password - "$CREDENTIAL_FILE" >/dev/null
    chmod 0600 "$CREDENTIAL_FILE"
    log "Encrypted management credential created: $CREDENTIAL_FILE"
}

write_user_data() {
    local output="$1"
    [ -r "$CREDENTIAL_FILE" ] || die "missing encrypted credential: $CREDENTIAL_FILE (run credential-init)"
    [ -r "$SSH_PUBLIC_KEY_FILE" ] || die "missing SSH public key: $SSH_PUBLIC_KEY_FILE"
    command -v systemd-creds >/dev/null 2>&1 || die "systemd-creds is required"
    command -v openssl >/dev/null 2>&1 || die "openssl is required"

    local password password_hash
    password=$(systemd-creds decrypt --name=moos-oracle-management-password "$CREDENTIAL_FILE" -)
    password_hash=$(printf '%s' "$password" | openssl passwd -6 -stdin)
    umask 077
    printf '#cloud-config\nchpasswd:\n  expire: false\n  users:\n    - {name: moos, password: "%s", type: hash}\n' \
        "$password_hash" > "$output"
}

running_instance_id() {
    "$OCI" compute instance list --compartment-id "$(compartment)" --all --output json | \
        jq -r --arg name "$INSTANCE_NAME" \
        '.data | map(select(."display-name" == $name and ."lifecycle-state" == "RUNNING")) | .[0].id // "null"'
}

cleanup_instance_metadata() {
    local base="${XDG_RUNTIME_DIR:-/var/tmp}"
    case "${ORACLE_METADATA_DIR:-}" in
        "$base"/moos-oracle-metadata.*)
            [ ! -d "$ORACLE_METADATA_DIR" ] || rm -rf -- "$ORACLE_METADATA_DIR"
            ;;
    esac
    ORACLE_METADATA_DIR=""
}

capacity_watch() {
    local image_id="$1" subnet_id="$2" user_data_file cycle=0 running_id launch_json state instance_id firmware public_ip fault_domain
    [ -n "$image_id" ] && [ "$image_id" != null ] || die "capacity-watch needs an image OCID"
    [ -n "$subnet_id" ] && [ "$subnet_id" != null ] || die "capacity-watch needs a subnet OCID"
    case "$OCPUS:$MEMORY_GB:$BOOT_GB:$RETRY_SECONDS:$MAX_CYCLES" in
        *[!0-9.:]*) die "capacity-watch numeric settings are invalid" ;;
    esac

    ensure_uefi_capability "$image_id"
    ORACLE_METADATA_DIR=$(mktemp -d -p "${XDG_RUNTIME_DIR:-/var/tmp}" moos-oracle-metadata.XXXXXX)
    user_data_file="$ORACLE_METADATA_DIR/user-data.yaml"
    write_user_data "$user_data_file"
    trap cleanup_instance_metadata EXIT
    trap 'exit 0' INT TERM
    while :; do
        cycle=$((cycle + 1))
        log "capacity cycle=$cycle utc=$(date -u +%FT%TZ)"
        running_id=$(running_instance_id 2>/dev/null || true)
        if [ -n "$running_id" ] && [ "$running_id" != null ]; then
            public_ip=$("$OCI" compute instance list-vnics --instance-id "$running_id" \
                --query 'data[0]."public-ip"' --raw-output)
            log "SUCCESS existing instance=$running_id public_ip=$public_ip"
            return 0
        fi

        while IFS= read -r availability_domain; do
            [ -n "$availability_domain" ] || continue
            while IFS= read -r fault_domain; do
                [ -n "$fault_domain" ] || continue
                log "Trying $availability_domain / $fault_domain: $SHAPE, $OCPUS OCPU, ${MEMORY_GB}GB RAM"
                if launch_json=$("$OCI" compute instance launch \
                    --availability-domain "$availability_domain" \
                    --fault-domain "$fault_domain" \
                    --compartment-id "$(compartment)" \
                    --display-name "$INSTANCE_NAME" \
                    --hostname-label "$INSTANCE_NAME" \
                    --shape "$SHAPE" \
                    --shape-config "{\"ocpus\":$OCPUS,\"memoryInGBs\":$MEMORY_GB}" \
                    --subnet-id "$subnet_id" \
                    --assign-public-ip true \
                    --image-id "$image_id" \
                    --boot-volume-size-in-gbs "$BOOT_GB" \
                    --ssh-authorized-keys-file "$SSH_PUBLIC_KEY_FILE" \
                    --user-data-file "$user_data_file" \
                    --wait-for-state RUNNING \
                    --wait-for-state TERMINATED \
                    --wait-interval-seconds 10 \
                    --max-wait-seconds 300 \
                    --output json); then
                    state=$(printf '%s' "$launch_json" | jq -r '.data."lifecycle-state"')
                    instance_id=$(printf '%s' "$launch_json" | jq -r '.data.id')
                    firmware=$(printf '%s' "$launch_json" | jq -r '.data."launch-options".firmware')
                    log "Launch result: state=$state firmware=$firmware instance=$instance_id"
                    if [ "$state" = RUNNING ]; then
                        [ "$firmware" = UEFI_64 ] || die "running instance firmware is $firmware, expected UEFI_64"
                        sleep 5
                        public_ip=$("$OCI" compute instance list-vnics --instance-id "$instance_id" \
                            --query 'data[0]."public-ip"' --raw-output)
                        log "SUCCESS instance=$instance_id public_ip=$public_ip"
                        return 0
                    fi
                else
                    log "Launch request failed in $availability_domain / $fault_domain; continuing"
                fi
            done < <(fault_domains "$availability_domain")
        done < <(ads)

        if [ "$MAX_CYCLES" -gt 0 ] && [ "$cycle" -ge "$MAX_CYCLES" ]; then
            die "all availability domains were full for $cycle cycle(s)"
        fi
        log "All availability and fault domains are full; retrying in $RETRY_SECONDS seconds"
        sleep "$RETRY_SECONDS"
    done
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
        if ! "$OCI" os bucket get --name "$BUCKET" >/dev/null 2>&1; then
            "$OCI" os bucket create --compartment-id "$(compartment)" --name "$BUCKET" >/dev/null
        fi
        object="moos-arm-bootstrap.qcow2"
        log "Uploading qcow2 (this takes a while)..."
        "$OCI" os object put --bucket-name "$BUCKET" --file "$BOOTSTRAP_QCOW" --name "$object" --part-size 128
        namespace=$("$OCI" os ns get --query 'data' --raw-output)
        image_id=$("$OCI" compute image import from-object \
            --compartment-id "$(compartment)" \
            --display-name "moos-arm-bootstrap" \
            --launch-mode PARAVIRTUALIZED \
            --operating-system "MoOS" \
            --source-object-name "$object" \
            --bucket-name "$BUCKET" \
            --namespace-name "$namespace" \
            --wait-for-state AVAILABLE \
            --query 'data.id' --raw-output)
        ensure_uefi_capability "$image_id"
        echo "IMAGE_ID=$image_id"
        ;;
    image-uefi)
        require_oci
        ensure_uefi_capability "${2:-}"
        ;;
    credential-init)
        credential_init
        ;;
    capacity-watch)
        require_oci
        capacity_watch "${2:-}" "${3:-}"
        ;;
    *)
        echo "usage: $0 verify|upload-import|image-uefi IMAGE_OCID|credential-init|capacity-watch IMAGE_OCID SUBNET_OCID" >&2
        exit 2
        ;;
esac
