#!/usr/bin/bash
# Execute installed Store/native ABI controls in private profiles, not an owner job.
set -euo pipefail
[ -s /ctx/test_flatpak_transaction_signals.py ] || {
    echo 'GATE FAIL: native Flatpak transaction proof driver is missing'
    exit 1
}
transaction_log="$(mktemp /tmp/moos-flatpak-transaction.XXXXXX.log)"
trap 'rm -f "$transaction_log"' EXIT
set +e
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -s /ctx/test_flatpak_transaction_signals.py --installed >"$transaction_log" 2>&1
transaction_exit=$?
set -e
if [ "$transaction_exit" -ne 0 ]; then
    cat "$transaction_log"
    echo 'GATE FAIL: installed native Flatpak transaction proof failed'
    exit "$transaction_exit"
fi
grep -qx 'MOOS_IMAGE_FLATPAK_TRANSACTION_PASS' "$transaction_log" || {
    cat "$transaction_log"
    echo 'GATE FAIL: native Flatpak transaction proof did not execute'
    exit 1
}
echo 'MOOS_IMAGE_FLATPAK_TRANSACTION_PASS'
